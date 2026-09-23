import asyncio
from dataclasses import replace

import pytest

from voice_service.broker import Broker, ServiceError
from voice_service.cloud import CloudError
from voice_service.config import Settings
from tests.fake_worker import worker
from tests.test_broker import ready


class CloudFixture:
    """Explicit simulated cloud control behavior, never a production fallback."""
    def __init__(self,delay=.01,error=None):
        self.delay,self.error=delay,error
        self.calls=[]
        self.cancelled=0
    def available(self): return True
    def status(self): return {'state':'configured','message':'TEST FIXTURE'}
    async def run(self,kind,payload):
        self.calls.append((kind,payload))
        try:
            await asyncio.sleep(self.delay)
        except asyncio.CancelledError:
            self.cancelled+=1
            raise
        if self.error: raise self.error
        return {'provider':'cloud_test_fixture','result':{'text':'fixture'},'metrics':{'provider_elapsed_ms':10}}


def route(asr='local',tts='local',audio=False,text=False):
    return {'asr':asr,'tts':tts,'allow_audio_upload':audio,'allow_text_upload':text}


def test_four_combinations_turn_snapshot_idempotence_and_permissions():
    async def scenario():
        cloud=CloudFixture()
        broker=Broker(Settings(),worker,cloud)
        await broker.start()
        try:
            await ready(broker)
            session=broker.new_session()['session_id']
            for index,(asr,tts) in enumerate((('local','local'),('local','cloud'),('cloud','local'),('cloud','cloud'))):
                broker.set_routing(session,route(asr,tts,True,True))
                turn=broker.next_turn(session)['turn_id']
                for kind in ('asr','tts'):
                    payload={'audio':b'fixture'} if kind=='asr' else {'text':'fixture'}
                    job=broker.submit(session,turn,f'{index}-{kind}',kind,payload)
                    await job.done.wait()
                    assert job.status=='completed'
                    assert (job.public()['provider']=='cloud_test_fixture') == (job.mode=='cloud')
                    assert broker.submit(session,turn,f'{index}-{kind}',kind,payload) is job
            assert len(cloud.calls)==4
            broker.set_routing(session,route())
            turn=broker.next_turn(session)['turn_id']
            broker.set_routing(session,route('cloud','cloud',True,True))
            job=broker.submit(session,turn,'frozen','asr',{'audio':b'fixture'})
            await job.done.wait()
            assert job.mode=='local'
            broker.set_routing(session,route('cloud','cloud',False,True))
            turn=broker.next_turn(session)['turn_id']
            with pytest.raises(ServiceError) as err:
                broker.submit(session,turn,'forbidden','asr',{'audio':b'fixture'})
            assert err.value.code=='UPLOAD_PERMISSION_REQUIRED'
            broker.new_session(replace=True)
            assert broker.routing==route()
        finally: await broker.close()
    asyncio.run(scenario())


def test_revocation_cancels_cloud_immediately_and_worker_survives():
    async def scenario():
        cloud=CloudFixture(delay=2)
        broker=Broker(Settings(),worker,cloud)
        await broker.start()
        try:
            await ready(broker)
            pid=broker.process.pid
            session=broker.new_session()['session_id']
            broker.set_routing(session,route(tts='cloud',text=True))
            turn=broker.next_turn(session)['turn_id']
            job=broker.submit(session,turn,'cancel','tts',{'text':'fixture'})
            while not cloud.calls: await asyncio.sleep(.01)
            broker.set_routing(session,route(tts='cloud',text=False))
            await asyncio.wait_for(job.done.wait(),.1)
            await asyncio.sleep(.03)
            assert job.status=='cancelled' and not job.value and cloud.cancelled==1
            assert broker.process.pid==pid and broker.process.is_alive()
        finally: await broker.close()
    asyncio.run(scenario())


def test_cloud_failure_limit_and_independence_from_local_loading():
    async def scenario():
        cloud=CloudFixture(error=CloudError(429,'CLOUD_RATE_LIMIT','fixture limit'))
        broker=Broker(replace(Settings(),cloud_request_limit=1),worker,cloud)
        # Dispatch without starting a local model process at all.
        broker.task=asyncio.create_task(broker._dispatch())
        try:
            session=broker.new_session()['session_id']
            broker.set_routing(session,route(tts='cloud',text=True))
            turn=broker.next_turn(session)['turn_id']
            job=broker.submit(session,turn,'limited','tts',{'text':'fixture'})
            await asyncio.wait_for(job.done.wait(),1)
            assert job.error['code']=='CLOUD_RATE_LIMIT' and len(cloud.calls)==1
            with pytest.raises(ServiceError) as err:
                broker.submit(session,turn,'again','tts',{'text':'fixture'})
            assert err.value.code=='CLOUD_SESSION_LIMIT'
            assert broker.process is None
        finally: await broker.close()
    asyncio.run(scenario())


def test_shutdown_after_cloud_cancel_cannot_swallow_dispatch_cancellation():
    async def scenario():
        cloud=CloudFixture(delay=2)
        broker=Broker(Settings(),worker,cloud)
        broker.task=asyncio.create_task(broker._dispatch())
        session=broker.new_session()['session_id']
        broker.set_routing(session,route(tts='cloud',text=True))
        turn=broker.next_turn(session)['turn_id']
        broker.submit(session,turn,'closing','tts',{'text':'fixture'})
        while not cloud.calls: await asyncio.sleep(.001)
        broker.cancel(session,'closing',turn)
        await asyncio.wait_for(broker.close(),.2)
        assert broker.task.done()
    asyncio.run(scenario())

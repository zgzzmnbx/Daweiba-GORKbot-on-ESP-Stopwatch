import asyncio
import time
from dataclasses import replace
import pytest
from voice_service.broker import Broker, ServiceError
from voice_service.config import Settings
from tests.fake_worker import worker


async def ready(broker):
    for _ in range(500):
        if broker.engines["asr"]["state"] == "ready":
            return
        await asyncio.sleep(0.02)
    raise AssertionError("test worker did not become ready")


def test_cancel_idempotency_turns_and_session_isolation():
    async def scenario():
        broker = Broker(Settings(), worker)
        await broker.start()
        try:
            await ready(broker)
            s = broker.new_session()["session_id"]
            t = broker.next_turn(s)["turn_id"]
            j = broker.submit(s, t, "one", "asr", {"audio": b"fixture"})
            assert broker.submit(s, t, "one", "asr", {"audio": b"fixture"}) is j
            with pytest.raises(ServiceError) as e:
                broker.submit(s, t, "one", "asr", {"audio": b"different"})
            assert e.value.code == "REQUEST_CONFLICT"
            await asyncio.sleep(0.05)
            start = time.monotonic()
            broker.cancel(s, "one", t)
            await j.done.wait()
            assert time.monotonic() - start < 0.1
            await asyncio.sleep(0.35)
            assert j.status == "cancelled" and not j.value
            broker.cancel(s, "before-upload", t)
            j2 = broker.submit(s, t, "before-upload", "asr", {"audio": b"fixture"})
            assert j2.status == "cancelled"
            new_turn = broker.next_turn(s)["turn_id"]
            with pytest.raises(ServiceError):
                broker.submit(s, t, "stale", "asr", {"audio": b"fixture"})
            j3 = broker.submit(s, new_turn, "new", "asr", {"audio": b"fixture"})
            await j3.done.wait()
            assert j3.status == "completed"
            s2 = broker.new_session(replace=True)["session_id"]
            with pytest.raises(ServiceError) as e:
                broker.get(s, "new")
            assert e.value.status == 401
            assert s2 != s
        finally:
            await broker.close()
    asyncio.run(scenario())


def test_queue_bound_and_worker_timeout_recovery():
    async def scenario():
        broker = Broker(replace(Settings(), asr_timeout=0.06), worker)
        await broker.start()
        try:
            await ready(broker)
            s = broker.new_session()["session_id"]; t = broker.next_turn(s)["turn_id"]
            first = broker.submit(s, t, "timeout", "asr", {"audio": b"fixture"})
            await asyncio.sleep(0.02)
            broker.submit(s, t, "queued1", "asr", {"audio": b"fixture"})
            broker.submit(s, t, "queued2", "asr", {"audio": b"fixture"})
            with pytest.raises(ServiceError) as e:
                broker.submit(s, t, "overflow", "asr", {"audio": b"fixture"})
            assert e.value.status == 429
            await first.done.wait()
            assert first.error["code"] == "ENGINE_TIMEOUT"
            broker.next_turn(s)
            await ready(broker)
            assert broker.process.is_alive()
        finally:
            await broker.close()
    asyncio.run(scenario())

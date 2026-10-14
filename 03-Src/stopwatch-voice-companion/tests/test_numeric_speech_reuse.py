import asyncio

from companion import speech_cache
from test_speech_cache import Voice
from test_external_protocol import system,notice,settled


def test_external_amount_and_risk_count_reuse_is_by_content_not_event_id(tmp_path,monkeypatch):
    monkeypatch.setattr(speech_cache,'cache_dir',lambda:tmp_path/'audio')
    monkeypatch.setattr('companion.external._pc_dynamic_speech',lambda audio,guard:'completed_by_os')
    async def run():
        control,external=system(tmp_path)
        control.voice=Voice();control.voice.session='current';control.turn=1
        control.speech={'cloud_voice':'Cherry','speed':1.0,'request_voice':True}
        amount={'value':'12345.67','currency':'CNY','unit':'yuan','basis':'tax_included',
                'calculation_status':'unconfirmed','attempt':'attempt'}
        async def send(sequence,text,*,mode='auto',summary=amount):
            payload=notice(sequence=sequence,display_target='none',speech={'text':text,'mode':mode},amount_summary=summary)
            await external.accept('astra',payload);await settled(external)
            assert external.read('astra',payload.event_id)['delivery']['speech']=='completed_by_os'
        text='含税金额 12345.67 元，发现 2 项风险。'
        await send(1,text);await send(2,text)
        assert control.voice.calls==[text] and control.fixed_speech_hits==1
        changed_count='含税金额 12345.67 元，发现 3 项风险。'
        await send(3,changed_count)
        changed_amount='含税金额 12346.67 元，发现 2 项风险。'
        await send(4,changed_amount,summary={**amount,'value':'12346.67'})
        assert control.voice.calls==[text,changed_count,changed_amount]
        await send(5,text,mode='tts')
        assert control.voice.calls[-1]==text and len(control.voice.calls)==4
        await external.close()
    asyncio.run(run())

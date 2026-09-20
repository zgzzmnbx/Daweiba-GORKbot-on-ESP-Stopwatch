import asyncio

import pytest
from stopwatch_ble import BleExpressionClient, BleConsoleError, STATUS_UUID
from test_ble_expression_console import FakeClient, FakeDevice


def test_wrong_expression_receipt_is_not_success_and_does_not_read_stale_status():
    class Wrong(FakeClient):
        async def read_gatt_char(self, characteristic):
            raise AssertionError('must not read stale characteristic')
    async def run():
        controller = BleExpressionClient(client_factory=Wrong, status_timeout=.01)
        await controller.connect(FakeDevice())
        with pytest.raises(BleConsoleError, match='超时'):
            await controller.send_command('idle')  # FakeClient only returns OK:HAPPY.
        assert not controller.connected
    asyncio.run(run())


def test_old_connection_callback_ignored_even_for_same_expression():
    async def run():
        controller = BleExpressionClient(client_factory=FakeClient, status_timeout=.01)
        await controller.connect(FakeDevice())
        old = controller.client.notify_callback
        await controller.disconnect(); await controller.connect(FakeDevice())
        old(STATUS_UUID, b'OK:HAPPY')
        assert controller._status_queue.empty()
        await controller.disconnect()
    asyncio.run(run())


def test_text_transaction_cannot_interleave_expression_or_clear():
    class Slow(FakeClient):
        async def write_gatt_char(self, *args, **kwargs):
            await asyncio.sleep(.001)
            await super().write_gatt_char(*args, **kwargs)
    async def run():
        controller = BleExpressionClient(client_factory=Slow)
        await controller.connect(FakeDevice()); client = controller.client
        await asyncio.gather(controller.send_text('中'*24), controller.send_command('happy'), controller.clear_text())
        payloads = [entry[1] for entry in client.writes]
        assert [x[0] for x in payloads[:7]] == [0xF0, 0xF1, 0xF1, 0xF1, 0xF1, 0xF1, 0xF2]
        assert payloads[7] == b'happy' and payloads[8] == b'\xF3'
        await controller.disconnect()
    asyncio.run(run())


def test_transport_drop_is_unknown_not_success_or_automatic_replay():
    created = []
    class Drop(FakeClient):
        def __init__(self, *args, **kwargs): super().__init__(*args, **kwargs); created.append(self)
        async def write_gatt_char(self, *args, **kwargs):
            self.writes.append(args)
            raise OSError('lost link')
    async def run():
        controller = BleExpressionClient(client_factory=Drop)
        await controller.connect(FakeDevice())
        with pytest.raises(BleConsoleError, match='未确认'): await controller.send_command('happy')
        assert not controller.connected and len(created) == 1 and len(created[0].writes) == 1
    asyncio.run(run())


def test_busy_refusal_is_not_acknowledged_or_retried():
    class Busy(FakeClient):
        async def write_gatt_char(self, *args, **kwargs):
            self.writes.append(args)
            self.notify_callback(STATUS_UUID,b'ERR:BUSY')
    async def run():
        controller = BleExpressionClient(client_factory=Busy)
        await controller.connect(FakeDevice()); client=controller.client
        with pytest.raises(BleConsoleError, match='ERR:BUSY'): await controller.send_command('happy')
        assert len(client.writes) == 1
        await controller.disconnect()
    asyncio.run(run())

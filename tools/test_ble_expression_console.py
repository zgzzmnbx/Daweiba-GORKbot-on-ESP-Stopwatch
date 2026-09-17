import asyncio
import importlib.util
import pathlib
import sys
import unittest


MODULE_PATH = pathlib.Path(__file__).with_name("ble-expression-console.py")
SPEC = importlib.util.spec_from_file_location("ble_expression_console", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class FakeAdvertisement:
    service_uuids = [MODULE.SERVICE_UUID]
    rssi = -42


class FakeDevice:
    name = MODULE.DEVICE_NAME
    address = "AA:BB:CC:DD:EE:FF"


class FakeService:
    def get_characteristic(self, uuid):
        return uuid if uuid in (MODULE.COMMAND_UUID, MODULE.STATUS_UUID) else None


class FakeServices:
    def get_service(self, uuid):
        return FakeService() if uuid == MODULE.SERVICE_UUID else None


class FakeClient:
    def __init__(self, device, pair, disconnected_callback):
        self.device = device
        self.pair = pair
        self.disconnected_callback = disconnected_callback
        self.is_connected = False
        self.services = FakeServices()
        self.notify_callback = None
        self.writes = []

    async def connect(self):
        self.is_connected = True

    async def start_notify(self, _characteristic, callback):
        self.notify_callback = callback

    async def write_gatt_char(self, characteristic, payload, response):
        self.writes.append((characteristic, bytes(payload), response))
        self.notify_callback(MODULE.STATUS_UUID, b"OK:HAPPY")

    async def read_gatt_char(self, _characteristic):
        return b"OK:HAPPY"

    async def disconnect(self):
        self.is_connected = False


class BleConsoleTests(unittest.TestCase):
    def test_normalize_command_and_protocol_limit(self):
        self.assertEqual(MODULE.normalize_command(" Happy "), "happy")
        self.assertEqual(MODULE.normalize_command("PINGPONG happy"), "pingpong happy")
        with self.assertRaises(MODULE.BleConsoleError):
            MODULE.normalize_command("not-an-expression")
        with self.assertRaises(MODULE.BleConsoleError):
            MODULE.normalize_command("pingpong nope")
        with self.assertRaises(MODULE.BleConsoleError):
            MODULE.normalize_command("x" * (MODULE.MAX_COMMAND_BYTES + 1))

    def test_all_23_expression_names_and_playback_modes(self):
        self.assertEqual(len(MODULE.EXPRESSIONS), 23)
        for expression in MODULE.EXPRESSIONS:
            self.assertEqual(MODULE.normalize_command(expression), expression)
            self.assertEqual(MODULE.normalize_command(f"once {expression}"), f"once {expression}")
            self.assertEqual(MODULE.normalize_command(f"loop {expression}"), f"loop {expression}")
            self.assertEqual(
                MODULE.normalize_command(f"pingpong {expression}"),
                f"pingpong {expression}",
            )

    def test_parse_status(self):
        self.assertEqual(MODULE.parse_status(b"OK:HAPPY"), "OK:HAPPY")
        with self.assertRaises(MODULE.BleConsoleError):
            MODULE.parse_status(b"\xff")

    def test_scan_filters_service(self):
        class Scanner:
            @classmethod
            async def discover(cls, timeout, return_adv):
                return {
                    "good": (FakeDevice(), FakeAdvertisement()),
                }

        targets = asyncio.run(MODULE.scan_targets(scanner=Scanner))
        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0].address, FakeDevice.address)

    def test_connect_and_write_receipt(self):
        created = []

        def factory(*args, **kwargs):
            client = FakeClient(*args, **kwargs)
            created.append(client)
            return client

        async def scenario():
            controller = MODULE.BleExpressionClient(
                client_factory=factory, status_timeout=0.1
            )
            await controller.connect(MODULE.Target(FakeDevice(), FakeDevice.name, FakeDevice.address))
            status = await controller.send_command("happy")
            self.assertEqual(status, "OK:HAPPY")
            self.assertEqual(created[0].writes[0][1], b"happy")
            self.assertTrue(created[0].writes[0][2])
            await controller.disconnect()

        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()

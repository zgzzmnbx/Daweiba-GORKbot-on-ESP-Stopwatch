"""Startup BLE selection and explicit user-operation precedence, without hardware."""
import asyncio
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from companion import robot as robot_module
from companion.app import create_app
from companion.robot import Robot


class FakeBle:
    def __init__(self):
        self.connected = False
        self.connections = []

    async def connect(self, target):
        self.connections.append(target.address)
        self.connected = True

    async def disconnect(self):
        self.connected = False


class FakeSound:
    async def attach(self, client):
        pass

    async def detach(self):
        pass


def target(address):
    return SimpleNamespace(address=address, name="GorkBot-SW")


@pytest.mark.parametrize("addresses,preferred,selected,error", [
    (["A"], "", "A", ""),
    (["A", "B"], "b", "B", ""),
    (["A", "B"], "", None, "多台"),
    (["A"], "B", None, "已配置"),
    ([], "", None, "未发现"),
])
def test_startup_selects_only_unambiguous_advertised_target(
    monkeypatch, addresses, preferred, selected, error
):
    async def fake_scan(**kwargs):
        assert kwargs["timeout"] == 5
        return [target(address) for address in addresses]

    monkeypatch.setattr(robot_module, "scan_targets", fake_scan)

    async def run():
        ble = FakeBle()
        robot = Robot(client=ble, sound=FakeSound())
        robot.start_auto_connect(preferred)
        await robot.auto_task
        assert ble.connections == ([selected] if selected else [])
        assert (error in robot.snapshot()["error"]) if error else robot.snapshot()["connected"]
        await robot.close()

    asyncio.run(run())


def test_manual_disconnect_preempts_pending_startup_scan(monkeypatch):
    entered, release = asyncio.Event(), asyncio.Event()

    async def fake_scan(**kwargs):
        entered.set()
        await release.wait()
        return [target("A")]

    monkeypatch.setattr(robot_module, "scan_targets", fake_scan)

    async def run():
        ble = FakeBle()
        robot = Robot(client=ble, sound=FakeSound())
        robot.start_auto_connect()
        await entered.wait()
        manual = asyncio.create_task(robot.disconnect())
        await asyncio.sleep(0)
        release.set()
        await manual
        assert robot.auto_task.cancelled()
        assert ble.connections == []
        assert not robot.snapshot()["connected"]
        await robot.close()

    asyncio.run(run())


def test_manual_disconnect_cancels_inflight_auto_connection(monkeypatch):
    class SlowBle(FakeBle):
        def __init__(self):
            super().__init__()
            self.entered = asyncio.Event()
            self.release = asyncio.Event()

        async def connect(self, target):
            self.entered.set()
            await self.release.wait()
            await super().connect(target)

    async def fake_scan(**kwargs):
        return [target("A")]

    monkeypatch.setattr(robot_module, "scan_targets", fake_scan)

    async def run():
        ble = SlowBle()
        robot = Robot(client=ble, sound=FakeSound())
        robot.start()
        robot.start_auto_connect()
        await ble.entered.wait()
        await asyncio.wait_for(robot.disconnect(), 1)
        ble.release.set()
        await asyncio.sleep(0.05)
        assert ble.connections == []
        assert not robot.enabled and robot.target is None
        assert not robot.snapshot()["connected"]
        await robot.close()

    asyncio.run(run())


def test_background_retries_initial_failure_and_later_drop(monkeypatch):
    monkeypatch.setattr(robot_module, "RECONNECT_INITIAL_DELAY", .01)
    monkeypatch.setattr(robot_module, "RECONNECT_MAX_DELAY", .02)
    monkeypatch.setattr(robot_module, "CONNECTION_POLL_SECONDS", .01)

    class FlakyBle(FakeBle):
        async def connect(self, selected):
            self.connections.append(selected.address)
            if len(self.connections) == 1:
                raise OSError("temporary radio failure")
            self.connected = True

    async def fake_scan(**kwargs):
        return [target("A")]

    monkeypatch.setattr(robot_module, "scan_targets", fake_scan)

    async def until(predicate):
        for _ in range(100):
            if predicate():
                return
            await asyncio.sleep(.01)
        raise AssertionError("BLE supervisor did not reach expected state")

    async def run():
        ble = FlakyBle()
        robot = Robot(client=ble, sound=FakeSound())
        robot.start_auto_connect()
        await robot.auto_task
        await until(lambda: ble.connected)
        assert ble.connections == ["A", "A"]
        ble.connected = False
        await until(lambda: len(ble.connections) == 3 and ble.connected)
        await robot.disconnect()
        attempts = len(ble.connections)
        await asyncio.sleep(.05)
        assert len(ble.connections) == attempts and not ble.connected
        await robot.close()

    asyncio.run(run())


def test_startup_scan_error_is_visible_and_injected_controller_does_not_scan(monkeypatch):
    async def failing_scan(**kwargs):
        raise RuntimeError("Bluetooth unavailable")

    monkeypatch.setattr(robot_module, "scan_targets", failing_scan)

    async def run():
        robot = Robot(client=FakeBle(), sound=FakeSound())
        robot.start_auto_connect()
        await robot.auto_task
        assert "自动连接失败" in robot.snapshot()["error"]
        await robot.close()

    asyncio.run(run())

    from test_companion import FakeRobot, FakeVoice
    from companion.control import Controller

    with TestClient(create_app(controller=Controller(FakeVoice(), FakeRobot())),
                    base_url="http://127.0.0.1:8766") as client:
        assert client.get("/api/health").json()["robot"]["connected"] is False


def test_auto_connect_config_is_boolean():
    with pytest.raises(ValueError, match="auto_connect_device"):
        create_app({"auto_connect_device": "false"})
    with pytest.raises(ValueError, match="auto_connect_voice"):
        create_app({"auto_connect_voice": "false"})


def test_health_exposes_voice_startup_policy():
    from test_companion import FakeRobot, FakeVoice
    from companion.control import Controller

    with TestClient(create_app({"auto_connect_voice": False},
                               controller=Controller(FakeVoice(), FakeRobot())),
                    base_url="http://127.0.0.1:8766") as client:
        assert client.get("/api/health").json()["auto_connect_voice"] is False


def test_lifespan_starts_auto_connect_independently_of_voice_and_respects_opt_out(monkeypatch):
    started = []
    monkeypatch.setattr(Robot, "start_auto_connect", lambda self, address="": started.append(address))
    with TestClient(create_app({"device_address": "AA:BB"}),
                    base_url="http://127.0.0.1:8766"):
        assert started == ["AA:BB"]
    with TestClient(create_app({"auto_connect_device": False}),
                    base_url="http://127.0.0.1:8766"):
        assert started == ["AA:BB"]

#!/usr/bin/env python3
"""Windows Bleak console for the GorkBot StopWatch BLE expression service.

The device must be put into its local 120-second pairing window first.  This
client deliberately performs one foreground scan and one foreground command
at a time; it never connects to a fixed MAC address or runs a background scan.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Optional


DEVICE_NAME = "GorkBot-SW"
SERVICE_UUID = "48f1a001-8a75-4db6-9c18-590f7e9b0a01"
COMMAND_UUID = "48f1a002-8a75-4db6-9c18-590f7e9b0a01"
STATUS_UUID = "48f1a003-8a75-4db6-9c18-590f7e9b0a01"
MAX_COMMAND_BYTES = 20
STATUS_TIMEOUT_SECONDS = 2.0
TEXT_MAX_BYTES = 72
TEXT_MAX_CHARACTERS = 24
TEXT_CHUNK_BYTES = 17
TEXT_BEGIN = 0xF0
TEXT_CHUNK = 0xF1
TEXT_COMMIT = 0xF2
TEXT_CLEAR = 0xF3

EXPRESSIONS = (
    "idle",
    "listening",
    "thinking",
    "happy",
    "happy-work",
    "excited",
    "curious",
    "confused",
    "angry",
    "surprised",
    "sad",
    "sleepy",
    "dizzy",
    "sleeping",
    "waking",
    "searching",
    "working",
    "bored",
    "suspicious",
    "proud",
    "shy",
    "laughing",
    "scared",
    "celebrate",
)
_EXPRESSION_SET = frozenset(EXPRESSIONS)
_MODES = frozenset(("once", "loop", "pingpong"))


class BleConsoleError(RuntimeError):
    """An expected, user-actionable BLE console error."""


@dataclass(frozen=True)
class Target:
    device: Any
    name: str
    address: str
    rssi: Optional[int] = None


def _load_bleak() -> tuple[Any, Any]:
    try:
        from bleak import BleakClient, BleakScanner
    except ImportError as exc:  # pragma: no cover - exercised by CLI only
        raise BleConsoleError(
            "缺少 bleak；请先运行 tools\\start-ble-expression-console.cmd"
        ) from exc
    return BleakClient, BleakScanner


def normalize_command(text: str) -> str:
    """Normalize and validate one protocol command before it reaches BLE."""

    if not isinstance(text, str):
        raise BleConsoleError("命令必须是文本")
    command = text.strip().lower()
    if not command:
        raise BleConsoleError("命令不能为空")
    if any(character not in "abcdefghijklmnopqrstuvwxyz -" for character in command):
        raise BleConsoleError("命令只能包含英文小写字母、连字符和单个空格")
    if command.startswith("loop ") or command.startswith("once "):
        mode, expression = command.split(" ", 1)
        if expression not in _EXPRESSION_SET:
            raise BleConsoleError(f"未知表情：{expression}")
        command = f"{mode} {expression}"
    elif command.startswith("pingpong "):
        expression = command[len("pingpong ") :]
        if expression not in _EXPRESSION_SET:
            raise BleConsoleError(f"未知表情：{expression}")
    elif command not in _EXPRESSION_SET:
        raise BleConsoleError(f"未知表情：{command}")
    encoded = command.encode("ascii")
    if len(encoded) > MAX_COMMAND_BYTES:
        raise BleConsoleError(
            f"命令超过 BLE 限制：{len(encoded)} > {MAX_COMMAND_BYTES} bytes"
        )
    return command


def parse_status(payload: bytes | bytearray | str) -> str:
    if isinstance(payload, str):
        status = payload
    else:
        try:
            status = bytes(payload).decode("ascii")
        except (UnicodeDecodeError, TypeError) as exc:
            raise BleConsoleError("设备返回了非 ASCII 状态") from exc
    status = status.strip()
    try:
        encoded = status.encode("ascii")
    except UnicodeEncodeError as exc:
        raise BleConsoleError("设备返回了非 ASCII 状态") from exc
    if not status or len(encoded) > 20:
        raise BleConsoleError("设备返回了无效状态")
    return status


def text_packets(text: str, transaction_id: int) -> list[tuple[bytes, str]]:
    """Split one UTF-8 bubble into acknowledged writes of at most 20 bytes."""

    message = text.strip()
    if not message or not all(character.isprintable() for character in message):
        raise BleConsoleError("文字不能为空，也不能包含换行或控制字符")
    if len(message) > TEXT_MAX_CHARACTERS or any(ord(c) > 0xFFFF for c in message):
        raise BleConsoleError("气泡最多 24 个字符，暂不支持 emoji")
    encoded = message.encode("utf-8")
    if len(encoded) > TEXT_MAX_BYTES:
        raise BleConsoleError("文字的 UTF-8 编码最多 72 字节")
    if not 1 <= transaction_id <= 255:
        raise ValueError("transaction_id must be in 1..255")
    packets = [
        (bytes((TEXT_BEGIN, transaction_id, len(encoded))),
         f"OK:BEGIN:{transaction_id}")
    ]
    for sequence, start in enumerate(range(0, len(encoded), TEXT_CHUNK_BYTES)):
        payload = encoded[start : start + TEXT_CHUNK_BYTES]
        packets.append(
            (bytes((TEXT_CHUNK, transaction_id, sequence)) + payload,
             f"OK:PART:{transaction_id}:{sequence}")
        )
    packets.append(
        (bytes((TEXT_COMMIT, transaction_id)), f"OK:TEXT:{transaction_id}")
    )
    return packets


def _advertised_service_uuids(advertisement: Any) -> set[str]:
    values = getattr(advertisement, "service_uuids", None) or ()
    return {str(value).lower() for value in values}


def _device_target(device: Any, advertisement: Any = None) -> Target:
    name = getattr(device, "name", None) or getattr(device, "address", "unknown")
    rssi = getattr(advertisement, "rssi", None)
    if rssi is None:
        rssi = getattr(device, "rssi", None)
    return Target(
        device=device,
        name=str(name),
        address=str(getattr(device, "address", device)),
        rssi=rssi,
    )


async def scan_targets(
    timeout: float = 10.0,
    scanner: Any = None,
) -> list[Target]:
    """Perform one scan and return only devices advertising our service."""

    if scanner is None:
        _, scanner = _load_bleak()
    discovered = await scanner.discover(timeout=timeout, return_adv=True)
    targets: list[Target] = []
    seen: set[str] = set()
    entries: Iterable[tuple[Any, Any]]
    if isinstance(discovered, dict):
        entries = discovered.values()
    else:  # Compatibility with older Bleak versions/mocks.
        entries = ((device, None) for device in discovered)
    for entry in entries:
        if isinstance(entry, tuple):
            device, advertisement = entry
        else:
            device, advertisement = entry, None
        if advertisement is not None and SERVICE_UUID not in _advertised_service_uuids(
            advertisement
        ):
            continue
        if advertisement is None:
            advertised = getattr(device, "metadata", {}).get("uuids", ())
            if SERVICE_UUID not in {str(value).lower() for value in advertised}:
                continue
        target = _device_target(device, advertisement)
        if target.address.lower() in seen:
            continue
        seen.add(target.address.lower())
        targets.append(target)
    return targets


class BleExpressionClient:
    """One connected StopWatch controller with notification-backed receipts."""

    def __init__(
        self,
        client_factory: Optional[Callable[..., Any]] = None,
        status_timeout: float = STATUS_TIMEOUT_SECONDS,
    ) -> None:
        self._client_factory = client_factory
        self._status_timeout = status_timeout
        self.client: Any = None
        self.command_characteristic: Any = COMMAND_UUID
        self.status_characteristic: Any = STATUS_UUID
        self._status_queue: Optional[asyncio.Queue[str]] = None
        self._disconnected = False
        self._next_text_id = 1

    @property
    def connected(self) -> bool:
        return bool(self.client is not None and getattr(self.client, "is_connected", False))

    def _on_disconnected(self, _client: Any) -> None:
        self._disconnected = True

    async def connect(self, target: Target | Any) -> None:
        if self.connected:
            return
        device = target.device if isinstance(target, Target) else target
        if self._client_factory is None:
            bleak_client, _ = _load_bleak()
            factory = bleak_client
        else:
            factory = self._client_factory
        self._disconnected = False
        self._status_queue = asyncio.Queue()
        self.client = factory(
            device,
            pair=True,
            disconnected_callback=self._on_disconnected,
        )
        try:
            await self.client.connect()
            services = getattr(self.client, "services", None)
            service = services.get_service(SERVICE_UUID) if services is not None else None
            if service is None:
                raise BleConsoleError("已连接，但未发现目标 GATT 服务")
            command = service.get_characteristic(COMMAND_UUID)
            status = service.get_characteristic(STATUS_UUID)
            if command is None or status is None:
                raise BleConsoleError("GATT 服务缺少命令或状态特征")
            self.command_characteristic = command
            self.status_characteristic = status
            await self.client.start_notify(
                self.status_characteristic, self._on_status_notification
            )
        except BleConsoleError:
            await self.disconnect()
            raise
        except Exception as exc:
            await self.disconnect()
            raise BleConsoleError(
                "连接失败：请确认 Pair 窗口、Windows 蓝牙和绑定状态"
            ) from exc

    def _on_status_notification(self, _characteristic: Any, payload: Any) -> None:
        if self._status_queue is None:
            return
        try:
            status = parse_status(payload)
        except BleConsoleError:
            return
        self._status_queue.put_nowait(status)

    async def _read_status(self) -> Optional[str]:
        if not self.connected:
            return None
        try:
            value = await self.client.read_gatt_char(self.status_characteristic)
            return parse_status(value)
        except Exception:
            return None

    async def send_command(self, text: str) -> str:
        command = normalize_command(text)
        if not self.connected or self._status_queue is None:
            raise BleConsoleError("尚未连接 StopWatch")
        while not self._status_queue.empty():
            self._status_queue.get_nowait()
        payload = command.encode("ascii")
        for attempt in range(2):
            try:
                await self.client.write_gatt_char(
                    self.command_characteristic, payload, response=True
                )
            except Exception as exc:
                raise BleConsoleError(f"BLE 写入失败：{exc}") from exc
            try:
                return await asyncio.wait_for(
                    self._status_queue.get(), timeout=self._status_timeout
                )
            except asyncio.TimeoutError:
                read_status = await self._read_status()
                if read_status is not None:
                    return read_status
                if attempt == 0 and self.connected and not self._disconnected:
                    continue
                raise BleConsoleError("等待设备状态回执超时")
        raise BleConsoleError("BLE 命令未获得回执")

    async def _send_text_packet(self, payload: bytes, expected_status: str) -> str:
        if not self.connected or self._status_queue is None:
            raise BleConsoleError("尚未连接 StopWatch")
        while not self._status_queue.empty():
            self._status_queue.get_nowait()
        try:
            await self.client.write_gatt_char(
                self.command_characteristic, payload, response=True
            )
        except Exception as exc:
            raise BleConsoleError(f"文字写入失败：{exc}") from exc
        deadline = asyncio.get_running_loop().time() + self._status_timeout
        while True:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                raise BleConsoleError("等待文字回执超时；本次显示结果未确认")
            try:
                status = await asyncio.wait_for(self._status_queue.get(), remaining)
            except asyncio.TimeoutError as exc:
                raise BleConsoleError("等待文字回执超时；本次显示结果未确认") from exc
            if status == expected_status:
                return status
            if status.startswith("ERR:"):
                if status == "ERR:BAD_CMD":
                    raise BleConsoleError("设备不支持文字气泡；请先写入 v0.5.0 固件")
                raise BleConsoleError(f"设备拒绝文字：{status}")

    async def send_text(self, text: str) -> str:
        transaction_id = self._next_text_id
        packets = text_packets(text, transaction_id)
        self._next_text_id = 1 if transaction_id == 255 else transaction_id + 1
        receipt = ""
        for payload, expected in packets:
            receipt = await self._send_text_packet(payload, expected)
        return receipt

    async def clear_text(self) -> str:
        return await self._send_text_packet(bytes((TEXT_CLEAR,)), "OK:CLEAR")

    async def disconnect(self) -> None:
        if self.client is None:
            return
        try:
            if getattr(self.client, "is_connected", False):
                await self.client.disconnect()
        finally:
            self.client = None
            self._status_queue = None
            self._disconnected = False


def _print_targets(targets: list[Target]) -> None:
    if not targets:
        print("未发现 GorkBot-SW；请确认设备已打开 BLE Pair 窗口，且 Windows 蓝牙已开启。")
        return
    print("发现目标：")
    for index, target in enumerate(targets, 1):
        rssi = f", RSSI {target.rssi} dBm" if target.rssi is not None else ""
        print(f"  {index}. {target.name}  {target.address}{rssi}")


async def _choose_target(targets: list[Target], address: Optional[str]) -> Target:
    if address:
        matches = [target for target in targets if target.address.lower() == address.lower()]
        if not matches:
            raise BleConsoleError(f"本次扫描未找到指定地址：{address}")
        return matches[0]
    if len(targets) == 1:
        return targets[0]
    if not targets:
        raise BleConsoleError("没有可连接的目标")
    while True:
        choice = (await asyncio.to_thread(input, "选择目标编号（q 退出）：")).strip()
        if choice.lower() == "q":
            raise BleConsoleError("用户取消连接")
        if choice.isdigit() and 1 <= int(choice) <= len(targets):
            return targets[int(choice) - 1]
        print("请输入列表中的编号。")


def _print_help() -> None:
    print(":help  显示帮助")
    print(":list  列出 24 个可用表情")
    print(":q     断开并退出")
    print(":say 文字   在角色头上显示气泡约 10 秒（最多 24 字符）")
    print(":clear      立即清除气泡")
    print("命令示例：happy / loop happy / once happy / pingpong happy")


async def run_console(address: Optional[str] = None, scan_timeout: float = 10.0) -> int:
    print("请先在 StopWatch 本地 Bluetooth 页面打开 BLE，再打开 Pair 窗口。")
    targets = await scan_targets(scan_timeout)
    _print_targets(targets)
    target = await _choose_target(targets, address)
    controller = BleExpressionClient()
    try:
        print(f"正在连接 {target.name} ({target.address}) …")
        await controller.connect(target)
        print("已连接；状态特征通知已订阅。输入 :help 查看命令。")
        while True:
            line = (await asyncio.to_thread(input, "ble> ")).strip()
            if not line:
                continue
            if line == ":q":
                return 0
            if line == ":help":
                _print_help()
                continue
            if line == ":list":
                print("  " + "  ".join(EXPRESSIONS))
                continue
            try:
                if line.startswith(":say "):
                    status = await controller.send_text(line[5:])
                elif line == ":say":
                    raise BleConsoleError("用法：:say 你好，今天加油")
                elif line == ":clear":
                    status = await controller.clear_text()
                else:
                    status = await controller.send_command(line)
                print(f"<- {status}")
            except BleConsoleError as exc:
                print(f"错误：{exc}")
    except (EOFError, KeyboardInterrupt):
        print()
        return 0
    finally:
        await controller.disconnect()


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--address", help="仅连接本次扫描中匹配的 BLE 地址")
    parser.add_argument("--scan-timeout", type=float, default=10.0)
    args = parser.parse_args(argv)
    try:
        return asyncio.run(run_console(args.address, args.scan_timeout))
    except (BleConsoleError, OSError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

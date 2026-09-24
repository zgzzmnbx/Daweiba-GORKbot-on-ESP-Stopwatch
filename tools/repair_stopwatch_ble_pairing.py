"""Repair this PC's stale StopWatch bond without using Windows Settings.

On the Watch, clear the old binding and open its two-minute Pair window first.
This command changes Windows pairing only with an explicit --apply argument.
"""
import argparse
import asyncio
from pathlib import Path
import tomllib

from bleak import BleakClient

from stopwatch_ble import BleExpressionClient, BleConsoleError, scan_targets


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "03-Src/stopwatch-voice-companion/config.local.toml"


def configured_address() -> str:
    if not CONFIG.exists():
        return ""
    data = tomllib.loads(CONFIG.read_text(encoding="utf-8-sig"))
    address = data.get("device_address", "")
    return address if isinstance(address, str) else ""


def select_target(targets, address: str):
    candidates = [target for target in targets if target.name == "GorkBot-SW"]
    if address:
        candidates = [target for target in candidates
                      if target.address.casefold() == address.casefold()]
    if len(candidates) != 1:
        raise BleConsoleError("未发现唯一且匹配的 GorkBot-SW；电脑配对记录未改动")
    return candidates[0]


async def repair(address: str) -> None:
    target = select_target(await scan_targets(timeout=5), address)
    print(f"找到目标 {target.address}；正在从程序内取消 Windows 旧配对", flush=True)
    await BleakClient(target.device).unpair()
    print("旧配对已取消；正在从程序内重新配对", flush=True)
    await asyncio.sleep(2)
    target = select_target(await scan_targets(timeout=5), address)
    client = BleExpressionClient()
    try:
        await client.connect(target)
        print("重新配对成功，目标 GATT 服务已发现。手表可退出 Settings。", flush=True)
    finally:
        await client.disconnect()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--address", default=configured_address(),
                        help="Watch 的 BLE 地址；默认读取本机 config.local.toml")
    parser.add_argument("--apply", action="store_true",
                        help="执行 Windows 取消旧配对和程序内重新配对")
    args = parser.parse_args()
    if not args.apply:
        parser.print_help()
        print("\n先在 Watch 上清除旧绑定并打开 Pair 窗口，再加 --apply 执行。")
        return
    asyncio.run(repair(args.address))


if __name__ == "__main__":
    main()

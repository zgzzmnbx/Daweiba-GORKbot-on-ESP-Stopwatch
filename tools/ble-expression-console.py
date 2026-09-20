"""Backward-compatible console entry point; protocol lives in stopwatch_ble."""
from stopwatch_ble import *  # noqa: F401,F403
from stopwatch_ble import main

if __name__ == "__main__":
    raise SystemExit(main())

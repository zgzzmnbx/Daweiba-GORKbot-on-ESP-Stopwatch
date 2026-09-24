"""Recovery tool must never unpair the wrong or ambiguous Watch."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

MODULE_PATH = Path(__file__).with_name("repair_stopwatch_ble_pairing.py")
SPEC = importlib.util.spec_from_file_location("repair_stopwatch_ble_pairing", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def device(name, address):
    return SimpleNamespace(name=name, address=address)


def test_repair_requires_exact_configured_address():
    selected = MODULE.select_target(
        [device("GorkBot-SW", "OTHER"), device("GorkBot-SW", "28:84:85:44:6C:01")],
        "28:84:85:44:6c:01")
    assert selected.address == "28:84:85:44:6C:01"
    with pytest.raises(MODULE.BleConsoleError, match="未发现唯一"):
        MODULE.select_target([device("GorkBot-SW", "OTHER")], "28:84:85:44:6C:01")


def test_repair_refuses_ambiguous_or_wrong_name():
    with pytest.raises(MODULE.BleConsoleError, match="未发现唯一"):
        MODULE.select_target([device("GorkBot-SW", "A"), device("GorkBot-SW", "B")], "")
    with pytest.raises(MODULE.BleConsoleError, match="未发现唯一"):
        MODULE.select_target([device("Other", "A")], "")

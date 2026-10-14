from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tools"))

# Mock BLE/audio tests must never read this user's real encrypted Wi-Fi policy.
import pytest
from pathlib import Path

@pytest.fixture(autouse=True)
def isolated_default_network(monkeypatch, tmp_path):
    from companion.network_store import NetworkStore
    import companion.network_manager as manager
    default=Path(manager.__file__).resolve().parents[1]/'network.local.json'
    original=NetworkStore.load
    def load(store):
        if store.path==default:
            store.path=tmp_path/'isolated-network.local.json'
        return original(store)
    monkeypatch.setattr(NetworkStore,'load',load)

@pytest.fixture(autouse=True)
def isolated_default_external_clients(monkeypatch,tmp_path):
    from companion.external import ClientRegistry
    original=ClientRegistry.__init__
    def initialize(registry,path=None):
        original(registry,path if path is not None else tmp_path/'isolated-external.local.json')
    monkeypatch.setattr(ClientRegistry,'__init__',initialize)

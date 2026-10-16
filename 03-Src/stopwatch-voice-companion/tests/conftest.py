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


@pytest.fixture(autouse=True)
def isolated_app_codex_defaults(monkeypatch, tmp_path):
    """Startup monitoring must not touch real sessions/hooks or launch Codex in tests."""
    import companion.app as app
    source, hooks, rpc, preferences = app.JsonlSource, app.HookSpool, app.QuotaRPC, app._codex_preferences
    default_hooks = app.PROJECT_ROOT / 'Codex-Temp' / 'codex-sentinel-hook-queue'
    monkeypatch.setattr(app, 'JsonlSource', lambda root=None:
                        source(root if root is not None else tmp_path / 'sessions'))
    monkeypatch.setattr(app, 'HookSpool', lambda folder:
                        hooks(tmp_path / 'hooks' if Path(folder) == default_hooks else folder))
    monkeypatch.setattr(app, 'QuotaRPC', lambda executable='codex':
                        rpc(str(tmp_path / 'missing-codex.exe') if executable == 'codex' else executable))
    monkeypatch.setattr(app, '_codex_preferences', lambda path:
                        preferences(tmp_path / 'codex.json' if path == app.ROOT / 'codex-sentinel.local.json' else path))

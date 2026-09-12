import os
import sys
import tempfile

import pytest

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

# Redirect ALL runtime state (clients, campaigns, memory, config) to a
# per-run temp dir. Tests must never write to the working tree — a leaked
# test client profile once shipped inside a customer release zip.
os.environ["BRANDFORGE_DATA_DIR"] = tempfile.mkdtemp(prefix="brandforge_test_state_")

# Generous limits for tests
os.environ.setdefault("BRANDFORGE_RATE_CHAT", "100000")
os.environ.setdefault("BRANDFORGE_RATE_SWARM", "100000")
os.environ.setdefault("BRANDFORGE_RATE_TOOL", "100000")
os.environ.setdefault("BRANDFORGE_RATE_WS", "100000")


@pytest.fixture()
def client(tmp_path, monkeypatch):
    import server
    monkeypatch.setenv('BRANDFORGE_DATA_DIR',str(tmp_path/'runtime'))
    for name in ('_engine','_pm','_cm','_tools','_approvals'):
        monkeypatch.setattr(server,name,None)
    server._rate_limit_store.clear()
    from fastapi.testclient import TestClient
    with TestClient(server.app) as c:
        c.headers["X-BrandForge-Token"] = c.get("/api/session").json()["capability"]
        yield c


@pytest.fixture()
def engine():
    from engines.ai_engine import get_engine
    return get_engine(provider="offline")


@pytest.fixture(autouse=True)
def unit_network_is_local_only(monkeypatch):
    """Mock third-party APIs explicitly; unit tests may use real loopback servers."""
    import socket
    import ipaddress
    original = socket.socket.connect
    def connect(sock, address):
        if isinstance(address, tuple):
            host = address[0]
            try: local = host == 'localhost' or ipaddress.ip_address(host).is_loopback
            except ValueError: local = False
            if not local:
                raise OSError('External network disabled in unit tests; supply an explicit transport fixture')
        return original(sock, address)
    monkeypatch.setattr(socket.socket, 'connect', connect)

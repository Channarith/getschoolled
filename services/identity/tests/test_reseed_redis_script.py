"""Tests for scripts/identity_reseed_redis.py (QA aliases + raw Redis fallback)."""

from __future__ import annotations

import importlib.util
import json
import socket
import threading
from pathlib import Path

from identity.store import AccountStore

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "identity_reseed_redis.py"


def _load_reseed_module():
    spec = importlib.util.spec_from_file_location("identity_reseed_redis", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_register_qa_aliases_enables_qa3_login():
    mod = _load_reseed_module()
    store = AccountStore()
    store.create("qa-pro@salareen.com", "QaTest123", display_name="QA Pro")
    mod._register_qa_aliases(store)
    assert store.authenticate("qa3", "QaTest123") is not None


def test_bootstrap_compat_registers_all_qa_aliases(monkeypatch):
    mod = _load_reseed_module()
    monkeypatch.setenv("SEED_DEFAULT_ADMIN", "0")
    monkeypatch.setenv("SEED_QA_ACCOUNTS", "1")
    store = AccountStore()
    stats = mod._bootstrap(store)
    assert stats["qa_count"] == 3
    assert store.authenticate("qa1", "QaTest123") is not None
    assert store.authenticate("qa2", "QaTest123") is not None
    assert store.authenticate("qa3", "QaTest123") is not None


def test_raw_redis_set_get_roundtrip():
    mod = _load_reseed_module()
    received = {}

    def handle(conn: socket.socket) -> None:
        file = conn.makefile("rb")
        while True:
            line = file.readline()
            if not line:
                break
            if line.startswith(b"*"):
                count = int(line[1:3])
                parts = []
                for _ in range(count):
                    ln = file.readline()
                    n = int(ln[1:-2])
                    parts.append(file.read(n + 2)[:n].decode())
                cmd = parts[0].upper()
                if cmd == "PING":
                    conn.sendall(b"+PONG\r\n")
                elif cmd == "SET":
                    received[parts[1]] = parts[2]
                    conn.sendall(b"+OK\r\n")
                elif cmd == "GET":
                    val = received.get(parts[1])
                    if val is None:
                        conn.sendall(b"$-1\r\n")
                    else:
                        b = val.encode()
                        conn.sendall(f"${len(b)}\r\n".encode() + b + b"\r\n")
        conn.close()

    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]
    thread = threading.Thread(target=lambda: handle(server.accept()[0]), daemon=True)
    thread.start()

    client = mod._RawRedis(f"redis://127.0.0.1:{port}/0")
    assert client.ping()
    payload = json.dumps({"hello": "world"})
    assert client.set(mod.REDIS_KEY, payload)
    assert client.get(mod.REDIS_KEY) == payload
    client.close()
    server.close()

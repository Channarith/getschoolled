"""Put the service ``src`` on sys.path so ``import orchestrator.*`` resolves."""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.abspath(os.path.join(_HERE, "..", "src"))
for _p in (_SRC, _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)


# Bypass the internal-auth gate by default in tests. Specific tests
# that exercise the gate clear this env via monkeypatch.
os.environ.setdefault("INTERNAL_AUTH_DISABLED", "1")

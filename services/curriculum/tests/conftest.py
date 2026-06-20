"""Put the service ``src`` on sys.path so ``import curriculum.*`` resolves."""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.abspath(os.path.join(_HERE, "..", "src"))
for _p in (_SRC, _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Bypass the homework internal-only auth gate by default in tests. Tests
# that specifically verify the gate (test_homework_internal_only.py)
# clear this env at module load via pytest.fixture so they exercise the
# real production behaviour.
os.environ.setdefault("INTERNAL_AUTH_DISABLED", "1")

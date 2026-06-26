"""Put the service ``src`` on sys.path so ``import orchestrator.*`` resolves."""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.abspath(os.path.join(_HERE, "..", "src"))
for _p in (_SRC, _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Disable rate limiting + share-clock cache for tests; the platform-wide
# limiter is unit-tested in packages/shared and would otherwise flake
# busy service test suites that issue hundreds of requests per session.
os.environ.setdefault("RATE_LIMIT_DISABLED", "1")

# Bypass the internal-auth gate by default in tests. Specific tests
# that exercise the gate clear this env via monkeypatch.
os.environ.setdefault("INTERNAL_AUTH_DISABLED", "1")

# Keep live-class sessions in-process for tests so a stray REDIS_URL in the
# environment can't make the suite talk to a real Redis. Tests that exercise the
# store factory override this via monkeypatch.
os.environ.setdefault("SESSION_BACKEND", "memory")

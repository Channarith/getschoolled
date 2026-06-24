"""Put the service ``src`` (and packages/shared) on sys.path for imports."""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.abspath(os.path.join(_HERE, "..", "src"))
_SHARED = os.path.abspath(os.path.join(_HERE, "..", "..", "..", "packages", "shared", "src"))
for _p in (_SRC, _SHARED, _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Disable rate limiting + share-clock cache for tests; the platform-wide
# limiter is unit-tested in packages/shared and would otherwise flake
# busy service test suites that issue hundreds of requests per session.
os.environ.setdefault("RATE_LIMIT_DISABLED", "1")

# Bypass the internal-auth gate by default in tests. Specific tests
# that exercise the gate clear this env via monkeypatch.
os.environ.setdefault("INTERNAL_AUTH_DISABLED", "1")

# Don't auto-seed the default admin during tests (keeps account state
# deterministic); the seed is unit-tested directly via store.seed_admin().
os.environ.setdefault("SEED_DEFAULT_ADMIN", "0")
os.environ.setdefault("SEED_QA_ACCOUNTS", "0")

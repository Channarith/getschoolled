"""Put the service ``src`` on sys.path so ``import curriculum.*`` resolves."""

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

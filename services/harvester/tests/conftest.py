import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT / "services" / "harvester" / "src"))
sys.path.insert(0, str(_ROOT / "packages" / "shared" / "src"))

# Disable rate limiting + share-clock cache for tests; the platform-wide
# limiter is unit-tested in packages/shared and would otherwise flake
# busy service test suites that issue hundreds of requests per session.
os.environ.setdefault("RATE_LIMIT_DISABLED", "1")

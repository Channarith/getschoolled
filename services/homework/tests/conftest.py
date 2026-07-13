import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT / "services" / "homework" / "src"))
sys.path.insert(0, str(_ROOT / "packages" / "shared" / "src"))

# Disable rate limiting for tests (consistent with the other service suites).
os.environ.setdefault("RATE_LIMIT_DISABLED", "1")

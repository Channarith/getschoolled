import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT / "services" / "harvester" / "src"))
sys.path.insert(0, str(_ROOT / "packages" / "shared" / "src"))

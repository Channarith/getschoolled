"""Make aoep_shared importable with the standard library only.

aoep_shared/__init__.py imports pydantic-based config, which a bare system python3 on the Spark or the
iBuyPower may not have. The fleet tools (queue, worker, status, shard_seeds) are stdlib only, so when
the real package cannot be imported we register an empty stand-in package that just points at the
source folder; submodules such as aoep_shared.fleet_queue then import normally.
"""
import sys
import types
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "packages" / "shared" / "src"


def bootstrap() -> None:
    if str(SRC) not in sys.path:
        sys.path.insert(0, str(SRC))
    if "aoep_shared" in sys.modules:
        return
    try:
        import aoep_shared  # noqa: F401
    except Exception:
        for name in [m for m in sys.modules if m == "aoep_shared" or m.startswith("aoep_shared.")]:
            del sys.modules[name]
        stub = types.ModuleType("aoep_shared")
        stub.__path__ = [str(SRC / "aoep_shared")]  # type: ignore[attr-defined]
        sys.modules["aoep_shared"] = stub


bootstrap()

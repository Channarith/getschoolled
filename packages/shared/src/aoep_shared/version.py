"""Single source of truth for the running version.

Resolution order:
  1. ``AOEP_VERSION`` env var (set in containers / k8s).
  2. The repo ``VERSION`` file (found by walking up from this module and CWD,
     plus the conventional container path ``/app/VERSION``).
  3. Installed package metadata for ``aoep-shared``.
  4. ``0.0.0+unknown`` as a last resort.

``VERSION`` is bumped by scripts/build_release.py, so every service and the web
app report the same version without hand-editing.
"""

from __future__ import annotations

import functools
import os
from pathlib import Path
from typing import Optional


def _read_version_file() -> Optional[str]:
    here = Path(__file__).resolve()
    bases = [here.parent, *here.parents, Path.cwd(), *Path.cwd().parents]
    candidates = [b / "VERSION" for b in bases]
    candidates.append(Path("/app/VERSION"))
    seen: set[Path] = set()
    for path in candidates:
        if path in seen:
            continue
        seen.add(path)
        try:
            if path.is_file():
                text = path.read_text(encoding="utf-8").strip()
                if text:
                    return text
        except OSError:
            continue
    return None


@functools.lru_cache(maxsize=1)
def get_version() -> str:
    env = os.environ.get("AOEP_VERSION")
    if env and env.strip():
        return env.strip()
    from_file = _read_version_file()
    if from_file:
        return from_file
    try:
        from importlib.metadata import version as _meta_version

        return _meta_version("aoep-shared")
    except Exception:  # noqa: BLE001
        return "0.0.0+unknown"

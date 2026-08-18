"""Load repo ``config/local.env`` (+ optional ``.env.local``) into ``os.environ``.

Theodore labs and some tools historically required a manual

    set -a; . config/local.env; set +a

before ``uvicorn``. Operators who skipped that saw ``local-fallback`` teaching
text and device-only TTS even when ``XAI_API_KEY`` / ``ELEVENLABS_API_KEY`` were
present in ``config/local.env``.

Rules (safe for compose/k8s where the real secret is already in the process):

1. Never overwrite a non-empty variable already present in ``os.environ``.
2. Never apply an empty value — blank ``XAI_API_KEY=`` lines in the example
   file must not clear a key that was set earlier (the example used to declare
   the key three times; last-wins blank was a footgun).
3. Prefer ``config/local.env``, then overlay ``.env.local`` when present.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, Mapping, MutableMapping, Optional


def _find_repo_root(start: Optional[Path] = None) -> Optional[Path]:
    here = (start or Path.cwd()).resolve()
    for candidate in (here, *here.parents):
        if (candidate / "config" / "local.env").is_file():
            return candidate
        if (candidate / "config" / "local.env.example").is_file() and (
            candidate / "VERSION"
        ).is_file():
            return candidate
    # Cloud / monorepo layout: packages/shared -> repo root
    shared = Path(__file__).resolve().parents[3]  # .../packages/shared/src/aoep_shared
    # Path: aoep_shared -> src -> shared -> packages -> repo
    repo = Path(__file__).resolve().parents[4]
    if (repo / "config").is_dir():
        return repo
    if (shared.parent.parent.parent / "config").is_dir():
        return shared.parent.parent.parent
    return None


def _parse_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return out
    for line in raw.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("export "):
            s = s[len("export ") :].strip()
        if "=" not in s:
            continue
        key, _, value = s.partition("=")
        key = key.strip()
        if not key:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        out[key] = value
    return out


def apply_env_map(
    values: Mapping[str, str],
    *,
    environ: Optional[MutableMapping[str, str]] = None,
    overwrite: bool = False,
) -> list[str]:
    """Merge ``values`` into ``environ``. Returns keys newly applied."""
    env = os.environ if environ is None else environ
    applied: list[str] = []
    for key, value in values.items():
        if not value:
            # Skip blanks — they must never clear an existing secret.
            continue
        existing = env.get(key, "")
        if existing and not overwrite:
            continue
        env[key] = value
        applied.append(key)
    return applied


def load_repo_env(
    *,
    root: Optional[Path] = None,
    environ: Optional[MutableMapping[str, str]] = None,
    files: Optional[Iterable[str]] = None,
    overwrite: bool = False,
) -> dict[str, object]:
    """Load AOEP env files into the process. Idempotent and safe to call often."""
    env = os.environ if environ is None else environ
    repo = root or _find_repo_root()
    report: dict[str, object] = {
        "repo_root": str(repo) if repo else "",
        "files": [],
        "applied": [],
        "xai_configured": bool((env.get("XAI_API_KEY") or "").strip()),
        "elevenlabs_configured": bool((env.get("ELEVENLABS_API_KEY") or "").strip()),
        "speech_base_url": (env.get("SPEECH_BASE_URL") or env.get("TTS_BASE_URL") or "").strip(),
    }
    if repo is None:
        return report

    names = list(files) if files is not None else ["config/local.env", ".env.local"]
    applied_all: list[str] = []
    loaded_files: list[str] = []
    for name in names:
        path = repo / name
        if not path.is_file():
            continue
        loaded_files.append(str(path))
        applied_all.extend(
            apply_env_map(_parse_env_file(path), environ=env, overwrite=overwrite)
        )

    report["files"] = loaded_files
    report["applied"] = applied_all
    report["xai_configured"] = bool((env.get("XAI_API_KEY") or "").strip())
    report["elevenlabs_configured"] = bool((env.get("ELEVENLABS_API_KEY") or "").strip())
    report["speech_base_url"] = (
        env.get("SPEECH_BASE_URL") or env.get("TTS_BASE_URL") or ""
    ).strip()
    # Prefer a current Grok chat model when the env left XAI_MODEL blank/retired.
    # Soft-upgrade also rewrites explicit retired slugs so labs stop calling
    # grok-2-1212 after operators copy an old local.env.
    _retired = {
        "",
        "grok-2",
        "grok-2-1212",
        "grok-2-latest",
        "grok-beta",
        "grok-4",
    }
    model = (env.get("XAI_MODEL") or "").strip()
    if model in _retired:
        env["XAI_MODEL"] = "grok-4.3"
    text_model = (env.get("XAI_TEXT_MODEL") or "").strip()
    if text_model in _retired:
        env["XAI_TEXT_MODEL"] = "grok-4.3"
    return report


def ensure_lab_env() -> dict[str, object]:
    """Convenience entry for Theodore lab ``main`` modules."""
    return load_repo_env()


def speech_readiness(*, environ: Optional[MutableMapping[str, str]] = None) -> dict[str, object]:
    """Compact status block for lab ``/health`` endpoints."""
    env = os.environ if environ is None else environ
    return {
        "xai_configured": bool((env.get("XAI_API_KEY") or "").strip()),
        "elevenlabs_configured": bool((env.get("ELEVENLABS_API_KEY") or "").strip()),
        "speech_base_url": (
            env.get("SPEECH_BASE_URL") or env.get("TTS_BASE_URL") or ""
        ).strip(),
        "xai_model": (env.get("XAI_MODEL") or env.get("XAI_TEXT_MODEL") or "grok-4.3").strip()
        or "grok-4.3",
    }

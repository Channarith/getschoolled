"""Speaker registry: one directory per person under GS_VOICES_DIR with consent.json, samples/ and enrollment.json."""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path

REQUIRED_SCOPES = ("commercial_use", "model_training", "course_narration")
ROLES = ("owner", "employee")
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,40}$")


class ConsentError(RuntimeError):
    pass


def voices_dir() -> Path:
    return Path(os.environ.get("GS_VOICES_DIR") or Path.home() / "voices").expanduser()


def sha256_file(path: Path | str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def speaker_dir(speaker: str, base: Path | None = None) -> Path:
    if not SLUG_RE.match(speaker or ""):
        raise ConsentError(f"speaker id {speaker!r} must be a lowercase slug (letters, digits, - or _)")
    return (base or voices_dir()) / speaker


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass


def record_consent(speaker: str, name: str, role: str, signed_form: Path | str, scopes=REQUIRED_SCOPES,
                   base: Path | None = None, date: str | None = None) -> dict:
    """Record that a person signed the consent form. The signed form (scan or PDF) must exist: its hash is stored."""
    if role not in ROLES:
        raise ConsentError(f"role must be one of {ROLES}")
    missing = [s for s in REQUIRED_SCOPES if s not in scopes]
    if missing:
        raise ConsentError(f"consent must cover {', '.join(REQUIRED_SCOPES)}; missing {', '.join(missing)}")
    form = Path(signed_form)
    if not form.is_file() or form.stat().st_size < 100:
        raise ConsentError(f"signed consent form not found at {form}: get the form signed first")
    d = speaker_dir(speaker, base)
    (d / "forms").mkdir(parents=True, exist_ok=True)
    kept = d / "forms" / form.name
    kept.write_bytes(form.read_bytes())
    rec = {"speaker": speaker, "name": name, "role": role, "date": date or time.strftime("%Y-%m-%d"),
           "scopes": list(scopes), "revocable": True, "revoked": False, "form_file": kept.name,
           "form_sha256": sha256_file(kept), "samples": {}}
    _write(d / "consent.json", rec)
    return rec


def load_consent(speaker: str, base: Path | None = None) -> dict:
    path = speaker_dir(speaker, base) / "consent.json"
    if not path.is_file():
        raise ConsentError(f"no consent record for {speaker!r}: refusing. Get the form signed and run 'consent' first")
    return _read(path)


def revoke(speaker: str, base: Path | None = None) -> None:
    rec = load_consent(speaker, base)
    rec["revoked"], rec["revoked_on"] = True, time.strftime("%Y-%m-%d")
    _write(speaker_dir(speaker, base) / "consent.json", rec)


def require_consent(speaker: str, scope: str = "course_narration", base: Path | None = None) -> dict:
    """Return the consent record only if it is valid for ``scope``; otherwise raise ConsentError. Also re-hashes the
    form and every enrolled sample, so edited or swapped audio is refused."""
    rec = load_consent(speaker, base)
    d = speaker_dir(speaker, base)
    if rec.get("revoked"):
        raise ConsentError(f"consent for {speaker!r} was revoked on {rec.get('revoked_on')}: refusing")
    if scope not in rec.get("scopes", []):
        raise ConsentError(f"consent for {speaker!r} does not cover {scope!r}")
    form = d / "forms" / rec.get("form_file", "")
    if not form.is_file() or sha256_file(form) != rec.get("form_sha256"):
        raise ConsentError(f"signed form for {speaker!r} is missing or changed: refusing")
    for rel, info in rec.get("samples", {}).items():
        p = d / rel
        if not p.is_file() or sha256_file(p) != info["sha256"]:
            raise ConsentError(f"sample {rel} for {speaker!r} is missing or changed since enrollment: refusing")
    return rec


def add_sample(speaker: str, wav: Path, transcript: str, lang: str, base: Path | None = None) -> dict:
    """Register an already-processed sample. Refuses without a valid consent record."""
    rec = require_consent(speaker, "model_training", base)
    d = speaker_dir(speaker, base)
    rel = f"samples/{wav.name}"
    if wav.resolve().parent != (d / "samples").resolve():
        raise ConsentError("sample must live in the speaker's samples directory")
    rec["samples"][rel] = {"sha256": sha256_file(wav), "transcript": transcript.strip(), "lang": lang}
    _write(d / "consent.json", rec)
    return rec


def list_speakers(base: Path | None = None) -> list[str]:
    root = base or voices_dir()
    return sorted(p.name for p in root.iterdir() if (p / "consent.json").is_file()) if root.is_dir() else []


def primary_sample(speaker: str, base: Path | None = None) -> tuple[Path, str, str]:
    """(wav path, transcript, lang) of the first enrolled sample, after consent is verified."""
    rec = require_consent(speaker, "course_narration", base)
    if not rec["samples"]:
        raise ConsentError(f"{speaker!r} has consent but no enrolled sample yet: run 'enroll'")
    rel, info = sorted(rec["samples"].items())[0]
    return speaker_dir(speaker, base) / rel, info["transcript"], info["lang"]

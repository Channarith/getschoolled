"""Custom presenter voices registered from reference audio samples."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence

CLONE_VOICE_PREFIX = "clone:"


@dataclass
class VoiceProfile:
    """A named voice cloned or synthesized from a reference recording."""

    id: str
    label: str
    sample_path: str
    language: str = "en"
    description: str = ""
    tts_engine: str = "clone"
    present_mode: str = ""
    wpm_factor: float = 1.0
    tts_rate: str = "+0%"
    elevenlabs_voice_id: str = ""
    meta: dict = field(default_factory=dict)

    @property
    def voice_token(self) -> str:
        return f"{CLONE_VOICE_PREFIX}{self.id}"

    def resolved_sample(self, *, repo_root: Optional[Path] = None) -> Path:
        p = Path(self.sample_path).expanduser()
        if p.is_file():
            return p.resolve()
        if repo_root:
            under = (repo_root / p).resolve()
            if under.is_file():
                return under
        env_root = voice_roots(repo_root)[0] if voice_roots(repo_root) else Path.cwd()
        for root in voice_roots(repo_root):
            for candidate in (
                root / self.id / "sample.wav",
                root / self.id / "sample.mp3",
                root / self.id / "sample.m4a",
                root / self.id / Path(self.sample_path).name,
            ):
                if candidate.is_file():
                    return candidate.resolve()
        raise FileNotFoundError(
            f"voice sample not found for {self.id!r}: {self.sample_path} "
            f"(searched under {env_root})"
        )

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict, *, base_dir: Optional[Path] = None) -> "VoiceProfile":
        d = dict(data)
        vid = str(d.pop("id", "")).strip()
        if not vid:
            raise ValueError("voice profile requires id")
        sample = str(d.pop("sample_path", "sample.wav")).strip()
        if base_dir and not Path(sample).is_absolute():
            sample_path = base_dir / sample
            if sample_path.is_file():
                sample = str(sample_path)
        return cls(id=vid, sample_path=sample, **d)


def voice_roots(repo_root: Optional[Path] = None) -> List[Path]:
    roots: List[Path] = []
    env = os.environ.get("AOEP_VOICE_DIR", "").strip()
    if env:
        roots.append(Path(env).expanduser())
    cache = Path(os.environ.get("AOEP_CACHE_DIR", "~/.cache/aoep")).expanduser() / "voices"
    roots.append(cache)
    if repo_root:
        roots.append(Path(repo_root) / "voices")
    seen: set[str] = set()
    out: List[Path] = []
    for r in roots:
        key = str(r.resolve()) if r.exists() else str(r)
        if key not in seen:
            seen.add(key)
            out.append(r)
    return out


def _load_profile_file(path: Path) -> Optional[VoiceProfile]:
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return VoiceProfile.from_dict(data, base_dir=path.parent)


def discover_voice_profiles(*, repo_root: Optional[Path] = None) -> Dict[str, VoiceProfile]:
    profiles: Dict[str, VoiceProfile] = {}
    for root in voice_roots(repo_root):
        if not root.is_dir():
            continue
        for profile_json in root.glob("*/profile.json"):
            try:
                prof = _load_profile_file(profile_json)
                if prof:
                    profiles[prof.id] = prof
            except (json.JSONDecodeError, ValueError, OSError):
                continue
        for profile_json in root.glob("*.voice.json"):
            try:
                prof = _load_profile_file(profile_json)
                if prof:
                    profiles[prof.id] = prof
            except (json.JSONDecodeError, ValueError, OSError):
                continue
    return profiles


def get_voice_profile(
    voice_id: str,
    *,
    repo_root: Optional[Path] = None,
) -> Optional[VoiceProfile]:
    key = voice_id.strip()
    if key.startswith(CLONE_VOICE_PREFIX):
        key = key[len(CLONE_VOICE_PREFIX):]
    key = key.lower().replace(" ", "_").replace("-", "_")
    return discover_voice_profiles(repo_root=repo_root).get(key)


def list_voice_profiles(*, repo_root: Optional[Path] = None) -> List[dict]:
    rows = []
    for p in sorted(discover_voice_profiles(repo_root=repo_root).values(), key=lambda x: x.id):
        row = p.to_dict()
        row["voice_token"] = p.voice_token
        try:
            row["sample_resolved"] = str(p.resolved_sample(repo_root=repo_root))
        except FileNotFoundError:
            row["sample_resolved"] = None
        rows.append(row)
    return rows


def save_voice_profile(
    profile: VoiceProfile,
    *,
    repo_root: Optional[Path] = None,
    out_root: Optional[Path] = None,
) -> Path:
    root = out_root or (voice_roots(repo_root)[-1] if repo_root else voice_roots()[0])
    dest = Path(root) / profile.id
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / "profile.json"
    path.write_text(json.dumps(profile.to_dict(), indent=2) + "\n", encoding="utf-8")
    return path


def parse_voice_token(voice: str) -> tuple[str, Optional[str]]:
    """Return (engine_hint, profile_id) when voice is ``clone:<id>``."""
    v = (voice or "").strip()
    if v.startswith(CLONE_VOICE_PREFIX):
        return "clone", v[len(CLONE_VOICE_PREFIX):]
    return "", None

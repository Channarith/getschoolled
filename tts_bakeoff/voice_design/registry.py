"""tts_manifest/stock_voices.json: the stock voices, and where a voice's frozen reference lives.

A stock voice is DEFINED in git (gender, age, timbre, optional accent, a seed) and FROZEN on the machine that renders it: the designed clip is
kept as <assets>/_stock/<id>/ref.wav with a ref.json sidecar (sha256, description, seed, take). Every later synthesis clones from that wav, so
the voice stays the same across runs and machines that copy the file. The wav is not committed (like voice-assets).
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from .prompt import AGES, GENDERS, TIMBRES, TONES, build_description

ROOT = Path(__file__).resolve().parents[2]
STOCK = ROOT / "tts_manifest" / "stock_voices.json"
LICENSE_NOTE = ("VoxCPM2 (OpenBMB), Apache-2.0, free for commercial use. Forbidden: impersonation, fraud, disinformation. "
                "AI-generated audio must be clearly labeled. A designed voice is synthetic: no person's recording or consent is involved.")
AI_LABEL = "AI-generated voice (designed with VoxCPM2)"
NEUTRAL = "neutral"


class StockError(RuntimeError):
    pass


def assets_dir(path: str | Path | None = None) -> Path:
    return Path(path or os.environ.get("GS_VOICE_ASSETS") or Path.home() / "voice-assets")


def load(path: Path = STOCK) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def voices(path: Path = STOCK) -> list[dict]:
    return load(path)["voices"]


def get(base_id: str, path: Path = STOCK) -> dict:
    for v in voices(path):
        if v["id"] == base_id:
            return v
    raise StockError(f"unknown stock voice {base_id!r}: add it to tts_manifest/stock_voices.json")


def split_id(voice_id: str) -> tuple[str, str]:
    """'stock-f-young-warm~professional' -> ('stock-f-young-warm', 'professional'); a bare id is the neutral voice."""
    base, _, tone = voice_id.partition("~")
    return base, (tone or NEUTRAL)


def variant_id(base_id: str, tone: str | None) -> str:
    return base_id if tone in (None, "", NEUTRAL) else f"{base_id}~{tone}"


def description_for(entry: dict, tone: str | None = None) -> str:
    return build_description(entry["g"], entry["age"], entry["timbre"], entry.get("accent"), None if tone in (None, NEUTRAL) else tone)


def seed_for(entry: dict, tone: str | None) -> int:
    """One stable seed per (voice, tone): the base seed plus the tone's position, so tones of a voice differ but are reproducible."""
    order = [NEUTRAL, *TONES]
    return int(entry["seed"]) + 100 * order.index(tone or NEUTRAL)


def ref_dir(voice_id: str, root: Path | None = None) -> Path:
    return assets_dir(root) / "_stock" / voice_id.replace("~", "--")


def ref_paths(voice_id: str, root: Path | None = None) -> tuple[Path, Path]:
    d = ref_dir(voice_id, root)
    return d / "ref.wav", d / "ref.json"


def sha256_file(path: Path | str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def frozen_meta(voice_id: str, root: Path | None = None) -> dict | None:
    """The sidecar of a frozen reference whose wav is intact, else None."""
    wav, side = ref_paths(voice_id, root)
    if not (wav.is_file() and side.is_file()):
        return None
    try:
        meta = json.loads(side.read_text(encoding="utf-8"))
    except ValueError:
        return None
    return meta if meta.get("sha256") == sha256_file(wav) else None


def require_frozen(voice_id: str, root: Path | None = None) -> tuple[Path, dict]:
    meta = frozen_meta(voice_id, root)
    if meta is None:
        raise StockError(f"{voice_id}: no intact frozen reference under {ref_dir(voice_id, root)} "
                         f"(run: python3 -m tts_bakeoff.voice_design freeze --voices {split_id(voice_id)[0]})")
    return ref_paths(voice_id, root)[0], meta


def validate_registry(path: Path = STOCK) -> list[str]:
    """Problems with the committed registry (empty list = fine): used by the tests so a bad edit cannot ship."""
    problems, seen = [], set()
    doc = load(path)
    for v in doc.get("voices", []):
        vid = v.get("id", "?")
        if vid in seen:
            problems.append(f"{vid}: duplicate id")
        seen.add(vid)
        if v.get("g") not in GENDERS or v.get("age") not in AGES or v.get("timbre") not in TIMBRES:
            problems.append(f"{vid}: gender/age/timbre not in the closed vocabulary")
            continue
        if v.get("gender") != ("female" if v["g"] == "f" else "male"):
            problems.append(f"{vid}: gender field does not match g")
        if v.get("age") == "child":
            problems.append(f"{vid}: child-like voices stay out of the registry until the owner approves them")
        try:
            if v.get("description") != description_for(v):
                problems.append(f"{vid}: description is not the one built from its fields")
        except ValueError as exc:
            problems.append(f"{vid}: {exc}")
        for t in v.get("tones", []):
            if t not in TONES:
                problems.append(f"{vid}: unknown tone {t!r}")
        if not isinstance(v.get("seed"), int):
            problems.append(f"{vid}: seed must be an integer")
    return problems

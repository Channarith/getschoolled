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

DESIGN_LANGS = ("en", "yue")      # the language a voice can be DESIGNED in (its frozen reference is spoken in it); 'en' is the default
METHODS = {"en-ref": None, "yue-ref": "yue"}   # how a language is cloned from the frozen reference: from the English one, or the Cantonese one

ROOT = Path(__file__).resolve().parents[2]
STOCK = ROOT / "tts_manifest" / "stock_voices.json"
LICENSE_NOTE = ("VoxCPM2 (OpenBMB), Apache-2.0, free for commercial use. Forbidden: impersonation, fraud, disinformation. "
                "AI-generated audio must be clearly labeled. A designed voice is synthetic: no person's recording or consent is involved.")
AI_LABEL = "AI-generated voice (designed with VoxCPM2)"
NEUTRAL = "neutral"
TONES_ORDER = tuple(TONES)   # the nine tones in their fixed order (seed_for and the review sheet rely on it)


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


def split_full(voice_id: str) -> tuple[str, str, str | None]:
    """'stock-f-young-warm.yue~cute' -> ('stock-f-young-warm', 'cute', 'yue'): base[.design_lang][~tone]. design_lang None = designed in English."""
    head, _, tone = voice_id.partition("~")
    base, _, dlang = head.partition(".")
    if dlang and dlang not in DESIGN_LANGS:
        raise StockError(f"{voice_id!r}: unknown design language {dlang!r} (one of {', '.join(DESIGN_LANGS)})")
    return base, (tone or NEUTRAL), (dlang or None)


def split_id(voice_id: str) -> tuple[str, str]:
    """'stock-f-young-warm~professional' -> ('stock-f-young-warm', 'professional'); a bare id is the neutral voice."""
    base, tone, _ = split_full(voice_id)
    return base, tone


def variant_id(base_id: str, tone: str | None, design_lang: str | None = None) -> str:
    head = f"{base_id}.{design_lang}" if design_lang and design_lang != "en" else base_id
    return head if tone in (None, "", NEUTRAL) else f"{head}~{tone}"


def description_for(entry: dict, tone: str | None = None) -> str:
    return build_description(entry["g"], entry["age"], entry["timbre"], entry.get("accent"), None if tone in (None, NEUTRAL) else tone)


def seed_for(entry: dict, tone: str | None, design_lang: str | None = None) -> int:
    """One stable seed per (voice, tone, design language): the base seed plus the tone's position (+50 for a Cantonese design), so variants differ
    but are reproducible."""
    order = [NEUTRAL, *TONES]
    return int(entry["seed"]) + 100 * order.index(tone or NEUTRAL) + (50 if design_lang and design_lang != "en" else 0)


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


def save(doc: dict, path: Path = STOCK) -> None:
    Path(path).write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def cleared(entry: dict, lang: str) -> dict | None:
    """The record of a native speaker approving this voice in ``lang`` (who, when, which tones, which cloning method), or None."""
    return (entry.get("cleared") or {}).get(lang)


def reference_id(voice_id: str, lang: str | None, path: Path = STOCK, root: Path | None = None) -> str:
    """The frozen reference to clone from for ``lang``: the Cantonese-designed one when the native speaker cleared that voice with method
    'yue-ref' for the language (and it is frozen here), else the voice's own (English-designed) reference."""
    base, tone, dlang = split_full(voice_id)
    if dlang is None and lang:
        rec = cleared(get(base, path), lang)
        target = METHODS.get((rec or {}).get("method"))
        if target:
            cand = variant_id(base, tone, target)
            if frozen_meta(cand, root) is not None:
                return cand
    return voice_id


def clear(base_id: str, lang: str, by: str, tones: list[str] | None = None, method: str = "en-ref", note: str = "",
          path: Path = STOCK, today: str | None = None) -> dict:
    """Record that a native speaker listened to ``base_id`` in ``lang`` and approved it (and which tone variants). Nothing is cleared by default."""
    import time

    if not (by or "").strip():
        raise StockError("clear needs --by: the name of the native speaker who listened")
    if method not in METHODS:
        raise StockError(f"unknown method {method!r} (one of {', '.join(METHODS)})")
    doc = load(path)
    entry = next((v for v in doc["voices"] if v["id"] == base_id), None)
    if entry is None:
        raise StockError(f"unknown stock voice {base_id!r}")
    tones = [t for t in (tones or []) if t != NEUTRAL]
    bad = [t for t in tones if t not in entry.get("tones", [])]
    if bad:
        raise StockError(f"{base_id} has no tone(s) {', '.join(bad)}")
    rec = {"by": by.strip(), "on": today or time.strftime("%Y-%m-%d"), "method": method, "tones": tones, "note": note.strip()}
    entry.setdefault("cleared", {})[lang] = rec
    entry["langs"] = sorted({*entry.get("langs", []), lang}, key=lambda x: (x != "en", x))
    entry.setdefault("quality", {})[lang] = rec["note"] or f"cleared by {rec['by']} on {rec['on']}"
    save(doc, path)
    return rec


VOICES_JSON = ROOT / "tts_manifest" / "voices.json"


def activate(base_id: str, voices_path: Path = VOICES_JSON, path: Path = STOCK) -> None:
    """active=true in voices.json: only for a voice a native speaker has cleared in at least one language."""
    if not (get(base_id, path).get("cleared") or {}):
        raise StockError(f"{base_id}: not cleared in any language yet (run `clear` or `apply-review` first); it stays inactive")
    doc = json.loads(Path(voices_path).read_text(encoding="utf-8"))
    entry = next((v for v in doc["voices"] if v["id"] == base_id), None)
    if entry is None:
        raise StockError(f"{base_id} is not in {voices_path}")
    entry["active"] = True
    Path(voices_path).write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def unclear(base_id: str, lang: str, path: Path = STOCK) -> bool:
    doc = load(path)
    entry = next((v for v in doc["voices"] if v["id"] == base_id), None)
    if entry is None or lang not in entry.get("langs", []):
        return False
    entry["langs"] = [x for x in entry["langs"] if x != lang]
    (entry.get("cleared") or {}).pop(lang, None)
    (entry.get("quality") or {}).pop(lang, None)
    save(doc, path)
    return True


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
        for lang, rec in (v.get("cleared") or {}).items():
            if lang not in v.get("langs", []):
                problems.append(f"{vid}: cleared in {lang} but {lang} is not in langs")
            if not (rec.get("by") or "").strip() or rec.get("method") not in METHODS:
                problems.append(f"{vid}: cleared[{lang}] needs a 'by' and a method in {list(METHODS)}")
            if any(t not in v.get("tones", []) for t in rec.get("tones", [])):
                problems.append(f"{vid}: cleared[{lang}] lists a tone the voice does not have")
    labels = [v.get("label") for v in doc.get("voices", [])]
    if len(labels) != len(set(labels)):
        problems.append("duplicate labels")
    seeds = [v.get("seed") for v in doc.get("voices", [])]
    if len(seeds) != len(set(seeds)):
        problems.append("duplicate seeds: two voices would start from the same random state")
    return problems

"""Plan of pre-rendered edge-tts clips for the demos: which lines x which picker voices x which tones, in tiers.

  python3 -m tts_bakeoff.demo_voice.edge_render plan            # counts and size estimate per tier, nothing rendered

A clip lives at <assets>/edge.<EdgeVoiceName>[~<tone>]/<lang>/<hash>.mp3, the same <lang>/<hash> addressing the company-voice clips use
(clip_hash.py). The voices are the ones the account-menu picker lists (aoep_shared.voice_catalog, one per real edge voice).
Tones are the voice_types presets plus the 13 professional/cute/anime blends, applied as edge-tts rate/pitch/volume.

Tiers (the math is honest: lines x voices x tones multiplies fast, so everything is tiered and resumable):
  1  Driver's Ed (English) x every English picker voice (neutral) + the default female, default male and Andrew x all tones
  2  Driver's Ed translated into the demo languages x every picker voice of that language (neutral) + its default F/M x all tones
  3  the other demos (landing, On the Go, Vision Play) with the same voice/tone scheme, in every language they have lines for
  4  Driver's Ed in the remaining picker languages (needs translations first)

INTERNAL NOTE: edge-tts is an unofficial client of Microsoft's Edge Read Aloud service. Serving its output live is one thing; shipping it
as stored files is a bigger step. The licensed route to the same neural voices is Azure AI Speech (same voice names).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from tts_bakeoff.voice_types import BLEND_WEIGHTS, PRESETS, blend

from .clip_hash import clip_hash
from .manifest import MANIFEST

def _voice_catalog():
    """aoep_shared's package init needs pydantic; the renderer's venv only has edge-tts, so load the catalog module by path then."""
    try:
        from aoep_shared.voice_catalog import VOICE_CATALOG

        return VOICE_CATALOG
    except ImportError:
        import importlib.util

        path = Path(__file__).resolve().parents[2] / "packages" / "shared" / "src" / "aoep_shared" / "voice_catalog.py"
        spec = importlib.util.spec_from_file_location("_voice_catalog", path)
        mod = importlib.util.module_from_spec(spec)
        import sys

        sys.modules["_voice_catalog"] = mod   # dataclasses resolves the module through sys.modules
        spec.loader.exec_module(mod)
        return mod.VOICE_CATALOG


VOICE_CATALOG = _voice_catalog()
NEUTRAL = "neutral"
DEMO_LANGS = ("es", "zh", "yue", "vi", "th", "km", "sw", "hi")
DRIVERS_ED = "drivers_ed"
PRESET_TONES = tuple(PRESETS)                                   # professional, warm, calm, energetic, cute, anime, tough, heavy, light
BLEND_TONES = tuple(f"blend-{k}" for k in BLEND_WEIGHTS)         # blend-professional75-cute25, ...
TONES = PRESET_TONES + BLEND_TONES                               # 22 non-neutral tones
EXTRA_TONE_VOICES = {"en": ("en-US-AndrewNeural",)}

# Speech rate (characters per second) per clip language and the edge-tts mp3 bit rate (48 kbit/s mono): size estimate only.
CPS = {"zh": 4.5, "yue": 4.5, "ja": 4.5, "ko": 5.5, "th": 10.0, "km": 9.0, "hi": 12.0, "bn": 12.0, "ur": 12.0, "ar": 11.0, "fa": 11.0, "he": 11.0}
BYTES_PER_SECOND = 6000


@dataclass(frozen=True)
class Voice:
    edge: str
    lang: str          # the clip language the picker lists it under ("yue" for the Hong Kong voices)
    gender: str
    label: str
    catalog_ids: tuple


@dataclass(frozen=True)
class Item:
    tier: int
    demo: str
    lang: str
    text: str
    hash: str
    edge: str
    tone: str

    @property
    def variant(self) -> str:
        return variant_dir(self.edge, self.tone)

    @property
    def rel(self) -> str:
        return f"{self.variant}/{self.lang}/{self.hash}.mp3"


def variant_dir(edge: str, tone: str = NEUTRAL) -> str:
    return f"edge.{edge}" if tone == NEUTRAL else f"edge.{edge}~{tone}"


def clip_lang_of(language: str, locale: str) -> str:
    return "yue" if (locale or "").lower().startswith(("zh-hk", "zh-mo")) else (language or "en").split("-")[0].lower()


def catalog_voices() -> dict[str, list[Voice]]:
    """Unique edge voices per clip language, in catalog order (the picker already hides the duplicate regional labels)."""
    by_edge: dict[str, dict] = {}
    for v in VOICE_CATALOG:
        e = by_edge.setdefault(v.edge_voice, {"v": v, "ids": []})
        e["ids"].append(v.id)
    out: dict[str, list[Voice]] = {}
    for edge, e in by_edge.items():
        v = e["v"]
        lang = clip_lang_of(v.language, v.locale)
        out.setdefault(lang, []).append(Voice(edge, lang, v.gender, v.label, tuple(e["ids"])))
    return out


def default_pair(voices: list[Voice]) -> list[Voice]:
    first = {}
    for v in voices:
        first.setdefault(v.gender, v)
    return [first[g] for g in ("female", "male") if g in first]


def tone_voices(lang: str, voices: list[Voice]) -> list[Voice]:
    chosen = default_pair(voices)
    for edge in EXTRA_TONE_VOICES.get(lang, ()):
        for v in voices:
            if v.edge == edge and v not in chosen:
                chosen.append(v)
    return chosen


def prosody(tone: str) -> dict:
    """edge-tts keyword arguments for a tone ({} for neutral)."""
    if tone == NEUTRAL:
        return {}
    if tone in PRESETS:
        rate, pitch, volume = PRESETS[tone]
    elif tone.startswith("blend-") and tone[6:] in BLEND_WEIGHTS:
        rate, pitch, volume = blend(BLEND_WEIGHTS[tone[6:]])
    else:
        raise KeyError(f"unknown tone {tone!r}")
    return {"rate": rate, "pitch": pitch, "volume": volume}


def estimate_bytes(lang: str, text: str) -> int:
    return int(max(len(text), 1) / CPS.get(lang, 14.0) * BYTES_PER_SECOND) + 600


def lines_of(demo_filter, langs, manifest_path: Path = MANIFEST, translations: bool = True) -> dict[str, list[dict]]:
    """{lang: [{demo, text, hash}]} from the manifest (and the reviewed/unreviewed translations, which it also embeds)."""
    rows = json.loads(Path(manifest_path).read_text(encoding="utf-8"))["clips"]
    out: dict[str, list[dict]] = {}
    seen = set()
    for r in rows:
        if demo_filter(r["demo"]) and (langs is None or r["lang"] in langs):
            key = (r["lang"], r["hash"])
            if key not in seen:
                seen.add(key)
                out.setdefault(r["lang"], []).append({"demo": r["demo"], "text": r["text"], "hash": r["hash"]})
    if translations:
        from . import translations as tr

        for r in tr.clips(set(langs) if langs else None):
            if not demo_filter(r["demo"]):
                continue
            h = clip_hash(r["lang"], r["text"])
            key = (r["lang"], h)
            if key not in seen:
                seen.add(key)
                out.setdefault(r["lang"], []).append({"demo": r["demo"], "text": r["text"], "hash": h})
    return out


def _items(tier: int, per_lang: dict[str, list[dict]], voices_by_lang: dict[str, list[Voice]]) -> list[Item]:
    out: list[Item] = []
    for lang, lines in per_lang.items():
        voices = voices_by_lang.get(lang, [])
        if not voices:
            continue
        tv = tone_voices(lang, voices)
        for line in lines:
            for v in voices:
                out.append(Item(tier, line["demo"], lang, line["text"], line["hash"], v.edge, NEUTRAL))
            for v in tv:
                for tone in TONES:
                    out.append(Item(tier, line["demo"], lang, line["text"], line["hash"], v.edge, tone))
    return out


def build(tiers=(1, 2, 3, 4), manifest_path: Path = MANIFEST) -> list[Item]:
    vbl = catalog_voices()
    items: list[Item] = []
    if 1 in tiers:
        items += _items(1, lines_of(lambda d: d == DRIVERS_ED, {"en"}, manifest_path, translations=False), vbl)
    if 2 in tiers:
        items += _items(2, lines_of(lambda d: d == DRIVERS_ED, set(DEMO_LANGS), manifest_path), vbl)
    if 3 in tiers:
        items += _items(3, lines_of(lambda d: d != DRIVERS_ED, None, manifest_path), vbl)
    if 4 in tiers:
        rest = set(vbl) - {"en", *DEMO_LANGS}
        items += _items(4, lines_of(lambda d: d == DRIVERS_ED, rest, manifest_path), vbl)
    seen, uniq = set(), []
    for it in items:                       # a line can be in several tiers (same demo text in two demos): render once
        if it.rel not in seen:
            seen.add(it.rel)
            uniq.append(it)
    return uniq


def summarize(items: list[Item]) -> dict:
    tiers: dict[int, dict] = {}
    for it in items:
        t = tiers.setdefault(it.tier, {"clips": 0, "bytes": 0, "langs": {}})
        t["clips"] += 1
        t["bytes"] += estimate_bytes(it.lang, it.text)
        t["langs"][it.lang] = t["langs"].get(it.lang, 0) + 1
    return {"tiers": tiers, "clips": len(items), "bytes": sum(t["bytes"] for t in tiers.values())}

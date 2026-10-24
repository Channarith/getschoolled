"""Synthetic demo run for the listening lab: three fake voices, two languages, real run layout, real scores.

No GPU, no model, only numpy. The three voice folders reuse real adapter names (voxcpm2, cosyvoice2,
fish_speech15) so the license badges are exercised; meta.json marks every one of them demo=true and the page
shows a DEMO DATA banner, so nobody mistakes these tones for real model output.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from .. import asr as asr_mod
from ..adapters.base import write_wav
from ..adapters.mock import MockAdapter
from ..build_sentences import load
from ..score_bakeoff import score_model

DEMO_LANGS = ("en", "km")
DEMO_LIMIT = 6
# folder name -> (base pitch shift Hz, seconds per char, vibrato depth)
VOICES = {
    "voxcpm2": (40.0, 0.055, 0.35),
    "cosyvoice2": (0.0, 0.065, 0.15),
    "fish_speech15": (-30.0, 0.075, 0.55),
}


class DemoVoice(MockAdapter):
    name = "demo"

    def __init__(self, shift: float, spc: float, vibrato: float, **options):
        super().__init__(**options)
        self.shift, self.spc, self.vibrato = shift, spc, vibrato

    def _synth(self, text: str, lang: str, out_wav: Path) -> int:
        import numpy as np

        rate = 16000
        n = max(1, int(len(text) * self.spc * rate))
        t = np.arange(n) / rate
        f0 = 150.0 + self.shift + (sum(ord(c) for c in text) % 60)
        wobble = 1.0 + 0.02 * np.sin(2 * np.pi * 5.0 * t)
        phase = 2 * np.pi * np.cumsum(f0 * wobble) / rate
        tone = np.sin(phase) + 0.5 * np.sin(2 * phase) + 0.25 * np.sin(3 * phase)
        syllables = 0.55 + 0.45 * np.sin(2 * np.pi * (3.0 + 2 * self.vibrato) * t) ** 2
        fade = np.minimum(1.0, np.minimum(t, t[-1] - t) * 40)
        write_wav(out_wav, 0.22 * tone * syllables * fade, rate)
        return rate


def make_demo(dest: Path) -> Path:
    """Write the demo run into dest (created) and return it. Deterministic."""
    dest.mkdir(parents=True, exist_ok=True)
    for model, (shift, spc, vib) in VOICES.items():
        adapter = DemoVoice(shift, spc, vib)
        root = dest / model
        root.mkdir(parents=True, exist_ok=True)
        (root / "meta.json").write_text(json.dumps({
            "model": model, "demo": True, "options": {}, "host": "demo", "started": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        }, indent=2), encoding="utf-8")
        with (root / "manifest.jsonl").open("w", encoding="utf-8") as mf:
            for lang in DEMO_LANGS:
                for item in load(lang, DEMO_LIMIT):
                    wav = root / lang / f"{item['id']}.wav"
                    row = {"model": model, "lang": lang, "id": item["id"], "text": item["text"], "wav": wav.relative_to(dest).as_posix()}
                    row.update(adapter.synthesize(item["text"], lang, wav))
                    row["status"] = "ok"
                    mf.write(json.dumps(row, ensure_ascii=False) + "\n")
        (root / "scores.jsonl").write_text("", encoding="utf-8")
        score_model(dest, model, asr_mod.get("fake:0.05"))
    return dest

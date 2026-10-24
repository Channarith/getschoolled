"""Voice types for edge-tts: accents, genders and character presets, as a listening set for the lab.

  python3 -m tts_bakeoff.voice_types --out runs/2026-10-25-voices [--groups accents,styles,blends] [--list]

Accents and genders are real voices the service offers (list: edge_tts.list_voices). Character presets (professional,
warm, cute, anime, tough, heavy, light, energetic, calm) are PROSODY shaping (rate, pitch, volume) on those voices: they
approximate a character, they do not create one. The service also tags a few voices itself ('Cute', 'Lively', 'Sunshine',
'Professional'): those are included as-is. Singlish is the Singapore voice reading text written in Singlish.

INTERNAL REFERENCE ONLY: edge-tts is an unofficial client of Microsoft's Edge Read Aloud service (see docs/tts-bakeoff.txt);
the licensed route to the same neural voices is Azure AI Speech.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from .adapters import get

PRESETS = {  # name: (rate, pitch, volume)
    "professional": ("-3%", "+0Hz", "+0%"),
    "warm": ("-8%", "-2Hz", "+0%"),
    "calm": ("-12%", "-4Hz", "-5%"),
    "energetic": ("+12%", "+6Hz", "+5%"),
    "cute": ("+8%", "+30Hz", "+0%"),
    "anime": ("+18%", "+40Hz", "+10%"),
    "tough": ("-4%", "-18Hz", "+10%"),
    "heavy": ("-15%", "-30Hz", "+0%"),
    "light": ("+4%", "+14Hz", "-10%"),
}

BLEND_PARTS = ("professional", "cute", "anime")
BLEND_WEIGHTS = {  # label: {preset: weight}; pairs at 25/50/75, plus all three and three leaning blends
    **{f"{a}{w}-{b}{100 - w}": {a: w, b: 100 - w} for i, a in enumerate(BLEND_PARTS) for b in BLEND_PARTS[i + 1:] for w in (75, 50, 25)},
    "pro34-cute33-anime33": {"professional": 34, "cute": 33, "anime": 33},
    "pro60-cute20-anime20": {"professional": 60, "cute": 20, "anime": 20},
    "cute60-pro20-anime20": {"cute": 60, "professional": 20, "anime": 20},
    "anime60-pro20-cute20": {"anime": 60, "professional": 20, "cute": 20},
}
BLEND_VOICES = {
    "en": [("en-US-AvaNeural", None), ("en-GB-SoniaNeural", None), ("en-US-AnaNeural", None)],
    "ja": [("ja-JP-NanamiNeural", "こんにちは！今日のレッスンへようこそ。一緒に分数の比べ方を学びましょう。")],
    "zh": [("zh-CN-XiaoxiaoNeural", None), ("zh-CN-XiaoyiNeural", None)],
    "es": [("es-MX-DaliaNeural", None)],
}


def blend(weights: dict[str, int]) -> tuple[str, str, str]:
    """Weighted average of the presets' rate (%), pitch (Hz) and volume (%)."""
    total = sum(weights.values())
    out = []
    for i, unit in enumerate(("%", "Hz", "%")):
        v = sum(float(PRESETS[n][i].rstrip("%Hz")) * w for n, w in weights.items()) / total
        out.append(f"{int(round(v)):+d}{unit}")
    return tuple(out)  # type: ignore[return-value]


# group -> {lang code in the lab: [(voice short name, accent/label)]}
ACCENTS = {
    "en": [("en-US-AvaNeural", "American F"), ("en-US-AndrewNeural", "American M"), ("en-US-AnaNeural", "American 'Cute' child-like F"),
           ("en-GB-SoniaNeural", "British F"), ("en-GB-LibbyNeural", "British F 2"), ("en-GB-MaisieNeural", "British girl F"),
           ("en-GB-RyanNeural", "British M"), ("en-GB-ThomasNeural", "British M 2"),
           ("en-AU-NatashaNeural", "Australian F"), ("en-AU-WilliamMultilingualNeural", "Australian M"),
           ("en-SG-LunaNeural", "Singapore F"), ("en-SG-WayneNeural", "Singapore M"),
           ("en-IN-NeerjaNeural", "Indian F"), ("en-IN-PrabhatNeural", "Indian M"),
           ("en-IE-EmilyNeural", "Irish F"), ("en-IE-ConnorNeural", "Irish M"),
           ("en-NZ-MollyNeural", "New Zealand F"), ("en-NZ-MitchellNeural", "New Zealand M"),
           ("en-CA-ClaraNeural", "Canadian F"), ("en-CA-LiamNeural", "Canadian M"),
           ("en-ZA-LeahNeural", "South African F"), ("en-ZA-LukeNeural", "South African M"),
           ("en-HK-YanNeural", "Hong Kong F"), ("en-PH-RosaNeural", "Philippine F"),
           ("en-NG-EzinneNeural", "Nigerian F"), ("en-KE-AsiliaNeural", "Kenyan F")],
    "es": [("es-MX-DaliaNeural", "Mexican F"), ("es-MX-JorgeNeural", "Mexican M"), ("es-ES-ElviraNeural", "Spain F"),
           ("es-ES-AlvaroNeural", "Spain M"), ("es-AR-ElenaNeural", "Argentine F"), ("es-AR-TomasNeural", "Argentine M"),
           ("es-CO-SalomeNeural", "Colombian F"), ("es-CO-GonzaloNeural", "Colombian M"), ("es-CL-CatalinaNeural", "Chilean F"),
           ("es-US-PalomaNeural", "US Spanish F"), ("es-US-AlonsoNeural", "US Spanish M")],
    "zh": [("zh-CN-XiaoxiaoNeural", "Mandarin F warm"), ("zh-CN-XiaoyiNeural", "Mandarin F lively"), ("zh-CN-YunjianNeural", "Mandarin M passionate"),
           ("zh-CN-YunxiNeural", "Mandarin M sunshine"), ("zh-CN-YunxiaNeural", "Mandarin 'Cute' boy"),
           ("zh-CN-YunyangNeural", "Mandarin M professional"), ("zh-TW-HsiaoChenNeural", "Taiwan F"), ("zh-TW-HsiaoYuNeural", "Taiwan F 2"),
           ("zh-TW-YunJheNeural", "Taiwan M"), ("zh-CN-liaoning-XiaobeiNeural", "Liaoning dialect F"), ("zh-CN-shaanxi-XiaoniNeural", "Shaanxi dialect F")],
    "yue": [("zh-HK-HiuMaanNeural", "Cantonese F"), ("zh-HK-HiuGaaiNeural", "Cantonese F 2"), ("zh-HK-WanLungNeural", "Cantonese M")],
}
TEXTS = {  # lang -> {voice-prefix or None: text}; every one is an unreviewed sample sentence
    "en": {None: "Hello! Welcome to your lesson. Today we will learn how to compare fractions.",
           "en-SG": "Wah, today's lesson not so difficult one lah. You try first, can? If wrong, no problem, we do again."},
    "es": {None: "¡Hola! Bienvenido a tu lección. Hoy aprenderemos a comparar fracciones."},
    "zh": {None: "你好！欢迎来到今天的课程。我们一起学习怎样比较分数。", "zh-TW": "你好！歡迎來到今天的課程。我們一起學習怎樣比較分數。"},
    "yue": {None: "你好！歡迎嚟到今日嘅課堂。我哋一齊學點樣比較分數，唔難㗎，跟住我讀啦。"},
}
STYLE_VOICES = {  # (lab language, voice, sentence)
    "en": [("en-US-AvaNeural", None), ("en-US-AndrewNeural", None), ("en-GB-SoniaNeural", None)],
    "es": [("es-MX-DaliaNeural", None)], "zh": [("zh-CN-XiaoxiaoNeural", None)], "yue": [("zh-HK-HiuMaanNeural", None)],
    "km": [("km-KH-SreymomNeural", "សូមស្វាគមន៍មកកាន់មេរៀនរបស់អ្នក។"), ("km-KH-PisethNeural", "សូមស្វាគមន៍មកកាន់មេរៀនរបស់អ្នក។")],
    "th": [("th-TH-PremwadeeNeural", "ยินดีต้อนรับสู่บทเรียนของคุณ"), ("th-TH-NiwatNeural", "ยินดีต้อนรับสู่บทเรียนของคุณ")],
    "vi": [("vi-VN-HoaiMyNeural", "Chào mừng bạn đến với bài học."), ("vi-VN-NamMinhNeural", "Chào mừng bạn đến với bài học.")],
}


def text_for(lang: str, voice: str) -> str:
    options = TEXTS[lang]
    for prefix, text in options.items():
        if prefix and voice.startswith(prefix):
            return text
    return options[None]


def jobs(groups: set[str]):
    if "accents" in groups:
        for lang, voices in ACCENTS.items():
            for voice, label in voices:
                yield {"model": voice, "lang": lang, "id": "A01", "voice": voice, "text": text_for(lang, voice), "label": label}
    if "blends" in groups:
        for lang, voices in BLEND_VOICES.items():
            for voice, text in voices:
                for label, weights in BLEND_WEIGHTS.items():
                    rate, pitch, volume = blend(weights)
                    yield {"model": f"{voice}~blend-{label}", "lang": lang, "id": "B01", "voice": voice, "rate": rate, "pitch": pitch,
                           "volume": volume, "text": text or text_for(lang, voice), "label": f"{voice.split('-', 2)[2].replace('Neural', '')} · {label}"}
    if "styles" in groups:
        for lang, voices in STYLE_VOICES.items():
            for voice, text in voices:
                for name, (rate, pitch, volume) in PRESETS.items():
                    yield {"model": f"{voice}~{name}", "lang": lang, "id": "S01", "voice": voice, "rate": rate, "pitch": pitch,
                           "volume": volume, "text": text or text_for(lang, voice), "label": f"{voice.split('-', 2)[2].replace('Neural', '')} · {name}"}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("--groups", default="accents,styles")
    ap.add_argument("--list", action="store_true", help="print the plan and exit")
    ap.add_argument("--delay", type=float, default=0.5, help="seconds between requests (the service rate-limits)")
    args = ap.parse_args(argv)
    plan = list(jobs(set(args.groups.split(","))))
    if args.list:
        print(f"{len(plan)} clips"); [print(j["lang"], j["model"], "|", j["label"]) for j in plan]; return 0
    out = Path(args.out)
    done = {}
    stats = {"ok": 0, "skipped": 0, "failed": 0}
    for j in plan:
        wav = out / j["model"] / j["lang"] / f"{j['id']}.wav"
        mdir = out / j["model"]
        mdir.mkdir(parents=True, exist_ok=True)
        if wav.exists() and wav.stat().st_size > 2000:
            stats["skipped"] += 1
            continue
        opts = {k: j[k] for k in ("voice", "rate", "pitch", "volume") if k in j}
        try:
            r = get("edge_tts", **opts).synthesize(j["text"], j["lang"], wav)
            row = {"model": j["model"], "lang": j["lang"], "id": j["id"], "text": j["text"], "wav": f"{j['model']}/{j['lang']}/{j['id']}.wav",
                   "duration_s": r["duration_s"], "synth_s": r["synth_s"], "sample_rate": r["sample_rate"], "rtf": r["rtf"], "status": "ok",
                   "label": j["label"]}
            stats["ok"] += 1
        except Exception as exc:  # noqa: BLE001
            row = {"model": j["model"], "lang": j["lang"], "id": j["id"], "text": j["text"], "status": "failed", "error": str(exc)[:160], "label": j["label"]}
            stats["failed"] += 1
        with (mdir / "manifest.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        (mdir / "meta.json").write_text(json.dumps({"model": j["model"], "options": opts, "label": j["label"], "started": time.strftime("%Y-%m-%dT%H:%M:%S")}, indent=1))
        print(f"[{stats['ok'] + stats['skipped'] + stats['failed']}/{len(plan)}] {row['status']} {j['lang']} {j['model']}", flush=True)
        time.sleep(args.delay)
    print(json.dumps(stats))
    return 0 if stats["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

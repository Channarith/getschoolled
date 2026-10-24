import json

import pytest

from tts_bakeoff import edge_catalog as ec
from tts_bakeoff import sentence_set as ss
from tts_bakeoff.build_sentences import load, ordered_ids
from tts_bakeoff.edge_all import build_plan
from tts_bakeoff.sentences_master import LANGS, SENTENCES
from tts_bakeoff.snapshot_edge_voices import normalize
from tts_bakeoff.voice_types import PRESETS

DOC = json.loads(ec.SNAPSHOT.read_text(encoding="utf-8"))
VOICES = DOC["voices"]
CATALOG = DOC["catalog"]


def test_snapshot_parser_keeps_the_services_own_tags():
    raw = {"Name": "x", "ShortName": "en-US-AnaNeural", "Gender": "Female", "Locale": "en-US", "SuggestedCodec": "audio-24khz-48kbitrate-mono-mp3",
           "FriendlyName": "Microsoft Ana Online (Natural)", "Status": "GA",
           "VoiceTag": {"ContentCategories": ["Cartoon", "Conversation"], "VoicePersonalities": ["Cute"]}}
    assert normalize(raw) == {"name": "en-US-AnaNeural", "locale": "en-US", "gender": "Female", "friendly": "Microsoft Ana Online (Natural)", "status": "GA",
                              "personalities": ["Cute"], "categories": ["Cartoon", "Conversation"], "codec": "audio-24khz-48kbitrate-mono-mp3"}
    bare = normalize({"ShortName": "km-KH-PisethNeural", "Gender": "Male", "Locale": "km-KH"})
    assert bare["personalities"] == [] and bare["categories"] == [] and bare["name"] == "km-KH-PisethNeural"


def test_snapshot_is_complete_and_catalog_is_derived_from_it():
    assert DOC["count"] == len(VOICES) == len({v["name"] for v in VOICES}) and len(VOICES) > 300
    assert all(v["gender"] in {"Female", "Male"} and v["name"].startswith(v["locale"]) for v in VOICES)
    assert CATALOG == json.loads(json.dumps(ec.derive(VOICES), ensure_ascii=False)), "edge_voices.json catalog is stale: rerun snapshot_edge_voices"
    assert DOC["retrieved"][:2] == "20"


def test_platform_list_matches_the_shared_language_module():
    from aoep_shared.languages import SUPPORTED_LANGUAGES

    assert ec.PLATFORM == SUPPORTED_LANGUAGES and len(ec.PLATFORM) == 27


def test_every_platform_language_has_a_default_voice_or_a_stated_reason():
    for code in ec.PLATFORM:
        e = CATALOG[code]
        assert e["platform"] and e["name"] and e["native"]
        if e["status"] == "voice":
            names = {v["name"] for v in VOICES}
            assert e["default"]["female"] in names and e["default"]["male"] in names, code
            assert e["default"]["female"].startswith(e["primary_locale"].split("-")[0])
        else:
            assert e["status"] == "no_voice" and e["reason"], code
    assert all(CATALOG[c]["status"] == "voice" for c in ec.PLATFORM)  # as of the snapshot: all 27 have an edge voice


def test_languages_without_a_voice_say_so_and_never_get_a_fake_default():
    nov = [e for e in CATALOG.values() if e["status"] == "no_voice"]
    assert {e["code"] for e in nov} == set(ec.NO_VOICE) and nov
    for e in nov:
        assert e["reason"] and e["alternative"] and e["default"] == {"female": None, "male": None} and e["regions"] == []
        assert not [v for v in VOICES if v["locale"].split("-")[0] == e["code"]]


def test_regional_accents_are_listed():
    def locales(code):
        return {r["locale"] for r in CATALOG[code]["regions"]}

    assert {"fr-FR", "fr-CA", "fr-BE", "fr-CH"} <= locales("fr")
    assert {"de-DE", "de-AT", "de-CH"} <= locales("de")
    assert {"pt-BR", "pt-PT"} <= locales("pt")
    assert {"zh-CN", "zh-TW"} <= locales("zh")
    assert len(locales("ar")) >= 10 and len(locales("en")) >= 10 and len(locales("es")) >= 10
    assert CATALOG["yue"]["default"]["female"] == "zh-HK-HiuMaanNeural"
    for e in CATALOG.values():
        for r in e["regions"]:
            assert r["voices"] and (r["female"] or r["male"])


def test_extras_cover_the_languages_edge_offers():
    extras = [c for c, e in CATALOG.items() if not e["platform"] and e["status"] == "voice"]
    for code in ["yue", "ms", "fil", "my", "lo", "ta", "te", "ne", "si", "gu", "kn", "mr", "ml", "am", "zu", "af", "bg", "hr", "hu", "ro", "sk", "sl", "sr", "lt",
                 "lv", "et", "fi", "sv", "da", "nb", "is", "ca", "gl", "cy", "mt", "ga", "ka", "az", "kk", "uz", "mn", "ps", "so", "jv", "su", "mk", "sq", "bs"]:
        assert code in extras, code
    assert len(extras) >= 45 and len(ec.PLATFORM) + len(extras) >= 72


def test_pinned_voices_are_real_and_unchanged():
    names = {v["name"] for v in VOICES}
    for code, pair in ec.PINNED.items():
        assert set(pair) <= names, code
        assert tuple(CATALOG[code]["default"].values()) == pair


# ---------- sentences ----------

SPOKEN = [c for c, e in CATALOG.items() if e["status"] == "voice"]


@pytest.mark.parametrize("lang", SPOKEN)
def test_sentence_file_is_valid_for_every_language_with_a_voice(lang):
    rows = ss.load10(lang)
    assert [r["id"] for r in rows] == list(ss.SET10), lang
    for r in rows:
        assert r["text"].strip() and r["lang"] == lang
        assert ss.problems(lang, r, SENTENCES[r["id"]]["en"]) == [], (lang, r["id"], r["text"])
        if lang not in ss.FULL_SET_LANGS:
            assert r["source"] == ss.SOURCE and r["review_status"] == "unreviewed" and r["ref_en"] == SENTENCES[r["id"]]["en"]


def test_existing_eight_languages_are_reused_exactly():
    assert set(LANGS) == ss.FULL_SET_LANGS
    for lang in LANGS:
        full = {r["id"]: r for r in load(lang)}
        for r in ss.load10(lang):
            assert r == full[r["id"]]
    assert set(ss.SET10) <= set(ordered_ids()) and len(ss.SET10) == 10
    assert [i[0] for i in ss.SET10[:8]] == list("SMLNDPVQ")


def test_scripts_are_what_they_claim_across_languages():
    expect = {"ar": (0x600, 0x6FF), "he": (0x590, 0x5FF), "th": (0xE00, 0xE7F), "lo": (0xE80, 0xEFF), "my": (0x1000, 0x109F), "ka": (0x10A0, 0x10FF),
              "am": (0x1200, 0x137F), "si": (0xD80, 0xDFF), "ta": (0xB80, 0xBFF), "ru": (0x400, 0x4FF), "ja": (0x3040, 0x30FF), "ko": (0xAC00, 0xD7AF)}
    for lang, (lo, hi) in expect.items():
        text = " ".join(r["text"] for r in ss.load10(lang))
        assert sum(lo <= ord(c) <= hi for c in text) > 20, lang
    assert ss.problems("th", {"id": "S01", "text": "Welcome to your lesson, everyone."}, "Welcome to your lesson.")  # English is caught


def test_validator_catches_bad_translations():
    en = SENTENCES["N01"]["en"]
    assert ss.problems("fr", {"id": "N01", "text": ""}, en) == ["empty"]
    assert any("unchanged" in p for p in ss.problems("fr", {"id": "N01", "text": en}, en))
    assert any("number" in p for p in ss.problems("fr", {"id": "N01", "text": "Il y a 30 élèves dans la classe."}, en))
    assert ss.problems("fr", {"id": "N01", "text": "Il y a 25 élèves dans la classe."}, en) == []
    assert any("markup" in p for p in ss.problems("fr", {"id": "S01", "text": "**Bienvenue** à votre leçon."}, "Welcome to your lesson."))


# ---------- the render plan ----------

def test_plan_counts_match_the_catalog():
    plan, models = build_plan(CATALOG, VOICES)
    spoken = [e for e in CATALOG.values() if e["status"] == "voice"]
    defaults = sum(1 for e in spoken for g in ("female", "male") if e["default"][g])
    covered = {v for e in spoken for v in e["default"].values() if v}
    regional = sum(1 for e in spoken for r in e["regions"] for v in r["voices"] if v not in covered)
    kinds = {k: sum(1 for j in plan if models[j["model"]]["kind"] == k) for k in ("default", "style", "regional")}
    assert kinds == {"default": defaults * 10, "style": len(spoken) * len(PRESETS) * 2, "regional": regional}
    assert len(plan) == sum(kinds.values()) > 3000
    assert len({(j["model"], j["lang"], j["id"]) for j in plan}) == len(plan)
    assert {j["lang"] for j in plan} == set(SPOKEN)
    assert {j["id"] for j in plan} == set(ss.SET10) | {"A01"}


def test_plan_has_every_voice_of_every_language_exactly_once():
    plan, models = build_plan(CATALOG, VOICES)
    plain = {m["voice"] for m in models.values() if m["kind"] != "style"}
    in_lang = {v["name"] for v in VOICES if CATALOG_LANG(v) in set(SPOKEN)}
    assert plain == in_lang
    for j in plan:
        assert "NO_" not in j["model"] and j["text"].strip()
        if "~" in j["model"]:
            assert j["id"] in {"S01", "Q01"} and {"rate", "pitch", "volume"} <= set(j)
            assert j["voice"] == CATALOG[j["lang"]]["default"]["female"]


def test_plan_can_be_limited_to_some_languages():
    plan, _ = build_plan(CATALOG, VOICES, {"km", "ar"})
    assert {j["lang"] for j in plan} == {"km", "ar"}


def test_coverage_report_lists_every_language_and_counts_a_run(tmp_path):
    from tts_bakeoff.coverage_report import render, run_status

    plan, models = build_plan(CATALOG, VOICES, {"km"})
    model = plan[0]["model"]
    ok = {"model": model, "lang": "km", "id": plan[0]["id"], "status": "ok", "wav": "x.wav"}
    bad = {"model": model, "lang": "km", "id": plan[1]["id"], "status": "failed", "error": "x"}
    (tmp_path / model).mkdir()
    (tmp_path / model / "manifest.jsonl").write_text(json.dumps(ok) + "\n" + json.dumps(bad) + "\n", encoding="utf-8")
    s = run_status(tmp_path, plan)["km"]
    assert (s["planned"], s["ok"], s["failed"], s["pending"]) == (len(plan), 1, 1, len(plan) - 2)
    text = render(DOC, tmp_path)
    for code in ec.PLATFORM:
        assert any(line.startswith(code + " ") for line in text.splitlines()), code
    assert "LANGUAGES WITH NO EDGE VOICE" in text and "Basque" in text and "Nearest alternative" in text and "FAILED CLIPS" in text
    assert "1 failed" in text and "unreviewed" in text and "Azure AI Speech" in text


def CATALOG_LANG(v):
    return "yue" if v["locale"] == "zh-HK" else v["locale"].split("-")[0]


def test_lab_embeds_the_language_catalog_and_every_sentence_set():
    from tts_bakeoff.lab import lab_data

    data = lab_data()
    codes = [x["code"] for x in data["languages"]]
    assert codes[:27] == list(ec.PLATFORM) and len(codes) >= 75
    assert {x["code"] for x in data["languages"] if x["rtl"]} == {"ar", "he", "ur", "fa", "ps"}
    assert set(SPOKEN) <= set(data["sentences"])
    assert next(x for x in data["languages"] if x["code"] == "eu")["status"] == "no_voice"

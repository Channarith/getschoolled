import json
from pathlib import Path

import pytest

from tts_bakeoff.demo_voice import manifest as mf
from tts_bakeoff.demo_voice import render as rd
from tts_bakeoff.demo_voice import translations as tr
from tts_bakeoff.demo_voice.clip_hash import clip_hash
from tts_bakeoff.voice_clone import registry


@pytest.fixture
def registry_here(monkeypatch, tmp_path_factory):
    """publish refuses on a machine without consent records; these tests stub the consent check, so stand a registry in."""
    reg = tmp_path_factory.mktemp("consent-registry")
    (reg / "wei-miao").mkdir()
    (reg / "wei-miao" / "consent.json").write_text("{}", encoding="utf-8")
    monkeypatch.setenv("GS_VOICES_DIR", str(reg))


@pytest.fixture
def tdir(tmp_path, monkeypatch):
    monkeypatch.setattr(tr, "TRANS_DIR", tmp_path / "translations")
    return tmp_path / "translations"


def _src(n=3):
    return [{"src": f"h{i}", "demo": "vision_play", "en": f"What is the capital of country number {i}?"} for i in range(n)]


def test_problems_checks_script_markup_unchanged_numbers():
    en = "What is the square root of 144?"
    assert tr.problems("yue", en, "一百四十四嘅平方根係幾多？") == []          # Chinese numerals for digits are fine
    assert tr.problems("yue", en, "") == ["empty"]
    assert "not Chinese script" in tr.problems("yue", en, "What is the root of one hundred forty four")
    assert "unchanged from English" in tr.problems("es", en, en)
    assert "markup" in tr.problems("yue", en, "<b>你好</b>")
    assert "numbers differ" in tr.problems("es", en, "¿Cuál es la raíz cuadrada?")
    assert tr.problems("es", en, "¿Cuál es la raíz cuadrada de 144?") == []


def test_translate_language_regenerates_failures_once_and_marks_unreviewed(tdir):
    calls = []

    def fake(lang, batch, key):
        calls.append([s["src"] for s in batch])
        good = {s["src"]: f"問題 {s['src']}？" for s in batch}
        if len(calls) == 1:
            good["h1"] = ""                       # fails the first time, fixed on the regeneration pass
        return good, {"prompt_tokens": 10, "completion_tokens": 20}

    usage = {"in": 0, "out": 0, "calls": 0}
    failed = tr.translate_language("yue", _src(), "k", usage, caller=fake)
    assert failed == [] and calls == [["h0", "h1", "h2"], ["h1"]] and usage["calls"] == 2
    items = tr.load("yue")["items"]
    assert {v["status"] for v in items.values()} == {"unreviewed"} and set(items) == {"h0", "h1", "h2"}
    assert tr.pending("yue", _src(4)) == [_src(4)[3]]


def test_translate_language_reports_lines_that_keep_failing(tdir):
    failed = tr.translate_language("yue", _src(2), "k", {"in": 0, "out": 0, "calls": 0}, caller=lambda l, b, k: ({"h0": "好"}, {}))
    assert failed == ["h1"] and list(tr.load("yue")["items"]) == ["h0"]


def _seed(tdir, texts):
    doc = {"lang": "yue", "source": tr.SOURCE, "model": "m", "items": {}}
    for i, t in enumerate(texts):
        doc["items"][f"h{i}"] = {"demo": "vision_play", "en": f"English line number {i}", "text": t, "status": "unreviewed"}
    tr.save(doc)


def test_apply_review_marks_ok_fixed_needs_fix_and_records_reviewer(tdir, tmp_path):
    _seed(tdir, ["甲", "乙", "丙", "丁"])
    dec = tmp_path / "d.json"
    dec.write_text(json.dumps({"lang": "yue", "reviewer": "Wei Miao", "decisions": {
        "h0": {"status": "ok", "text": "甲"}, "h1": {"status": "fixed", "text": "乙乙"}, "h2": {"status": "needs_fix", "text": "丙"},
        "h3": {"status": "ok", "text": "plain english now"}, "nope": {"status": "ok", "text": "x"}}}), encoding="utf-8")
    counts = tr.apply_review(dec)
    items = tr.load("yue")["items"]
    assert counts == {"ok": 1, "fixed": 1, "needs_fix": 2, "unknown": 1}
    assert items["h1"]["text"] == "乙乙" and items["h1"]["status"] == "fixed" and items["h1"]["reviewer"] == "Wei Miao"
    assert items["h3"]["status"] == "needs_fix" and items["h3"]["text"] == "丁"     # an edit that fails the checks is not accepted
    with pytest.raises(SystemExit):
        dec.write_text(json.dumps({"lang": "yue", "decisions": {}}), encoding="utf-8")
        tr.apply_review(dec)                                                           # no reviewer name: refused


def test_manifest_gets_every_translation_except_needs_fix(tdir):
    _seed(tdir, ["甲", "乙", "丙"])
    doc = tr.load("yue")
    doc["items"]["h2"]["status"] = "needs_fix"
    doc["items"]["h1"]["status"] = "ok"
    tr.save(doc)
    rows = tr.clips()
    assert sorted((r["text"], r["status"]) for r in rows) == [("乙", "ok"), ("甲", "unreviewed")]


def test_refresh_offline_merges_translations_and_voices_idempotently(tdir, tmp_path):
    _seed(tdir, ["甲", "乙"])
    base = tmp_path / "m.json"
    base.write_text(json.dumps({"version": 1, "languages": ["en"], "voices": [], "clips": [
        {"id": "x:en:1", "demo": "x", "lang": "en", "text": "hi", "hash": clip_hash("en", "hi")},
        {"id": "x:yue:old", "demo": "x", "lang": "yue", "text": "舊", "hash": "old", "status": "unreviewed"}]}), encoding="utf-8")
    a = mf.refresh_offline(base)
    base.write_text(json.dumps(a), encoding="utf-8")
    b = mf.refresh_offline(base)
    assert a == b and a["languages"] == ["en", "yue"] and [v["id"] for v in a["voices"] if v.get("kind") != "stock"] == ["channarith", "wei-miao", "wei"]
    yue = [c for c in a["clips"] if c["lang"] == "yue"]
    assert sorted(c["text"] for c in yue) == ["乙", "甲"] and all(c["hash"] == clip_hash("yue", c["text"]) for c in yue)   # stale 'old' clip dropped


def test_committed_manifest_has_three_voices_each_with_its_own_language_and_cantonese_lines():
    m = json.loads(mf.MANIFEST.read_text(encoding="utf-8"))
    people = [v for v in m["voices"] if v.get("kind") != "stock"]
    by = {v["id"]: v for v in people}
    assert list(by) == ["channarith", "wei-miao", "wei"]
    assert all(v.get("gender") in ("male", "female") for v in m["voices"])   # publish() reads this list: no gender here means no same-gender fallback
    stock = [v for v in m["voices"] if v.get("kind") == "stock"]
    assert [v["id"] for v in stock if v.get("default")] == ["stock-f-young-warm"] and stock[0]["active"] is True   # Sage: the owner's default Salane Voice
    assert all(v["active"] is False for v in stock if not v.get("default"))   # every other designed voice waits for a listener's clearance
    assert (by["channarith"]["primary_lang"], by["wei-miao"]["primary_lang"], by["wei"]["primary_lang"]) == ("en", "en", "yue")
    assert by["wei"]["speaker"] == "wei" and by["wei-miao"]["speaker"] == "wei-miao" and all(v["model"] == "voxcpm2" for v in m["voices"])
    assert len({v["speaker"] for v in people}) == 3                      # three people/ids, never merged
    assert "yue" in m["languages"] and len([c for c in m["clips"] if c["lang"] == "yue" and c["demo"] == "vision_play"]) >= 300
    assert all(c["status"] in tr.IN_MANIFEST for c in m["clips"] if c["lang"] == "yue" and c["demo"] == "vision_play")


class _Fake:
    languages = {"en", "yue"}

    def __init__(self):
        self.calls = []

    def synthesize(self, text, lang, out):
        self.calls.append(lang)
        Path(out).write_bytes(b"RIFF" + b"0" * 800)


def _m():
    rows = [("en", "one"), ("en", "two"), ("yue", "甲"), ("yue", "乙")]
    clips = [{"id": f"d:{l}:{clip_hash(l, t)}", "demo": "d", "lang": l, "text": t, "hash": clip_hash(l, t)} for l, t in rows]
    clips[2]["status"], clips[3]["status"] = "unreviewed", "ok"
    return {"voices": [{"id": "wei-miao", "label": "Wei Miao", "speaker": "wei-miao", "model": "voxcpm2", "active": True, "primary_lang": "yue"}], "clips": clips}


def test_render_does_the_voices_own_language_first_and_tags_translation_status(tmp_path, monkeypatch, registry_here):
    monkeypatch.setattr(registry, "require_consent", lambda *a, **k: {})
    monkeypatch.setattr(rd, "voice_cfg", lambda v: _m()["voices"][0])
    ad = _Fake()
    s = rd.run("wei-miao", tmp_path, None, None, None, _m(), ad, lambda w, m: Path(m).write_bytes(Path(w).read_bytes()))
    assert s["ok"] == 4 and ad.calls[:2] == ["yue", "yue"] and ad.calls[2:] == ["en", "en"]
    sidecars = {json.loads(p.read_text(encoding="utf-8"))["text"]: json.loads(p.read_text(encoding="utf-8")) for p in (tmp_path / "wei-miao").glob("*/*.json")}
    assert sidecars["甲"]["translation_status"] == "unreviewed" and sidecars["乙"]["translation_status"] == "ok" and "translation_status" not in sidecars["one"]
    idx_all = json.loads((tmp_path / "wei-miao" / "index.json").read_text())["clips"]
    assert len(idx_all["yue"]) == 2
    rd.publish(tmp_path, _m(), check_consent=lambda s: True, reviewed_only=True)
    assert len(json.loads((tmp_path / "wei-miao" / "index.json").read_text())["clips"]["yue"]) == 1     # the unreviewed machine line is held back
    doc = json.loads((tmp_path / "voices.json").read_text())["voices"][0]
    assert doc["primary_lang"] == "yue" and doc["active"] is True


def test_published_label_comes_from_the_consent_record(tmp_path, monkeypatch):
    monkeypatch.setattr(registry, "load_consent", lambda s, base=None: {"name": "苗 偉"})
    doc = rd.publish(tmp_path, _m(), check_consent=lambda s: True)["voices"][0]
    assert doc["label"] == "苗 偉 (Cantonese)" and doc["ai_label"] == "AI-generated voice of 苗 偉"
    monkeypatch.setattr(registry, "load_consent", lambda s, base=None: (_ for _ in ()).throw(registry.ConsentError("x")))
    assert rd.publish(tmp_path, _m(), check_consent=lambda s: True)["voices"][0]["label"] == "Wei Miao (Cantonese)"


def test_status_reports_clips_per_voice_and_language(tmp_path):
    (tmp_path / "wei-miao" / "yue").mkdir(parents=True)
    (tmp_path / "wei-miao" / "yue" / "a.mp3").write_bytes(b"x" * 600)
    st = rd.status(tmp_path, _m())
    assert st == {"wei-miao": {"en": [0, 2], "yue": [1, 2]}}


def test_demo_render_defaults_to_the_voices_own_languages_and_flags_cross_lingual(tmp_path, monkeypatch, registry_here):
    monkeypatch.setattr(registry, "require_consent", lambda *a, **k: {})
    monkeypatch.setattr(rd, "voice_cfg", lambda v: _m()["voices"][0])
    monkeypatch.setattr(rd, "speaker_languages", lambda s: ["yue"])
    assert rd.own_langs(_m()["voices"][0]) == {"yue"}
    monkeypatch.setattr(rd, "speaker_languages", lambda s: (_ for _ in ()).throw(registry.ConsentError("none")))
    assert rd.own_langs(_m()["voices"][0]) == {"yue"}                       # falls back to the voice's primary_lang
    rd.run("wei-miao", tmp_path, None, None, None, _m(), _Fake(), lambda w, m: Path(m).write_bytes(Path(w).read_bytes()), own={"yue"})
    side = {json.loads(p.read_text(encoding="utf-8"))["lang"]: json.loads(p.read_text(encoding="utf-8")) for p in (tmp_path / "wei-miao").glob("*/*.json")}
    assert side["en"]["cross_lingual"] is True and "cross_lingual" not in side["yue"]

import json
from pathlib import Path

import pytest

from tts_bakeoff.demo_voice import manifest as mf
from tts_bakeoff.demo_voice import render as rd
from tts_bakeoff.demo_voice import verify as vf
from tts_bakeoff.demo_voice.clip_hash import clip_hash, normalize
from tts_bakeoff.voice_clone import registry

VECTORS = Path(__file__).resolve().parents[2] / "tts_manifest" / "hash_vectors.json"


def test_hash_vectors_and_normalization():
    for case in json.loads(VECTORS.read_text(encoding="utf-8"))["cases"]:
        assert clip_hash(case["lang"], case["text"]) == case["hash"]
    assert clip_hash("en", "  Hello \n world ") == clip_hash("en-GB", "Hello world")
    assert normalize("a b　c") == "a b c"
    assert clip_hash("en", "x") != clip_hash("es", "x")


def test_committed_manifest_is_consistent():
    m = json.loads(mf.MANIFEST.read_text(encoding="utf-8"))
    assert m["voices"][0]["id"] == "channarith" and m["clips"]
    assert len({c["id"] for c in m["clips"]}) == len(m["clips"])
    for c in m["clips"]:
        assert c["hash"] == clip_hash(c["lang"], c["text"])


def test_vision_play_extracts_literals_only(tmp_path):
    (tmp_path / "a.js").write_text(
        'setPrompt("Freeze!","Hold still like a statue!");\n'
        'setPrompt(`Trace ${l}`,"x","y");\n'
        'setPrompt("Hi","there","Say this aloud");\nspeak("Play time is up.");\nspeak(`n ${n}`);\n', encoding="utf-8")
    (tmp_path / "quiz_bank.json").write_text(json.dumps({"4-6": [{"q": "What is 2+2?", "a": "4"}]}), encoding="utf-8")
    texts = {c["text"] for c in mf.vision_play(tmp_path)}
    assert texts == {"Freeze!. Hold still like a statue!", "Say this aloud", "Play time is up.", "What is 2+2?"}


def test_on_the_go_matches_the_player_line_and_skips_untranslated(monkeypatch):
    course = {"body_locale": "es", "segments": [{"heading": "Visión", "text": "Hola."}, {"heading": "1", "text": "123"}]}
    monkeypatch.setattr(mf, "_get_json", lambda url: course if "locale=es" in url else {"body_locale": "en", "segments": []})
    rows = mf.on_the_go(["es", "km"], "http://x", log=lambda *_: None)
    assert [r["text"] for r in rows] == ["Visión. Hola."] and rows[0]["lang"] == "es"


class FakeAdapter:
    languages = {"en", "es"}

    def __init__(self):
        self.calls = []

    def synthesize(self, text, lang, out):
        self.calls.append((lang, text))
        Path(out).write_bytes(b"RIFF" + b"0" * 800)


def _manifest():
    clips = [{"id": f"d:{l}:{clip_hash(l, t)}", "demo": "d", "lang": l, "text": t, "hash": clip_hash(l, t)}
             for l, t in [("en", "one"), ("en", "two"), ("es", "tres"), ("km", "bai")]]
    return {"voices": [{"id": "channarith", "label": "Channarith", "speaker": "channarith", "model": "voxcpm2", "active": True}], "clips": clips}


def _convert(wav, mp3):
    Path(mp3).write_bytes(Path(wav).read_bytes())


@pytest.fixture
def consented(monkeypatch):
    state = {"ok": True}

    def req(speaker, scope="course_narration", base=None):
        if not state["ok"]:
            raise registry.ConsentError("revoked")
        return {}
    monkeypatch.setattr(registry, "require_consent", req)
    return state


def test_render_skips_unsupported_and_existing_then_publishes(tmp_path, consented):
    m, ad = _manifest(), FakeAdapter()
    s = rd.run("channarith", tmp_path, None, None, None, m, ad, _convert)
    assert s == {"ok": 3, "skipped_existing": 0, "skipped_unsupported": 1, "failed": 0}
    sidecar = json.loads(next((tmp_path / "channarith" / "en").glob("*.json")).read_text(encoding="utf-8"))
    assert sidecar["ai_generated"] and sidecar["label"] == "AI-generated voice of Channarith" and sidecar["speaker"] == "channarith"
    again = rd.run("channarith", tmp_path, None, None, None, m, FakeAdapter(), _convert)
    assert again["ok"] == 0 and again["skipped_existing"] == 3
    idx = json.loads((tmp_path / "channarith" / "index.json").read_text())
    assert sorted(idx["clips"]) == ["en", "es"] and len(idx["clips"]["en"]) == 2
    assert json.loads((tmp_path / "voices.json").read_text())["voices"][0]["active"] is True
    assert [c["lang"] for c in vf.missing(tmp_path, m, "channarith", "voxcpm2")] == ["km"]   # the fake adapter never speaks km


def test_shards_partition_the_work(tmp_path, consented):
    m = _manifest()
    a = rd.run("channarith", tmp_path / "a", "0/2", None, None, m, FakeAdapter(), _convert)
    b = rd.run("channarith", tmp_path / "b", "1/2", None, None, m, FakeAdapter(), _convert)
    assert a["ok"] + b["ok"] + a["skipped_unsupported"] + b["skipped_unsupported"] == 4


def test_no_consent_no_audio_and_revocation_hides_voice(tmp_path, consented):
    m = _manifest()
    rd.run("channarith", tmp_path, None, None, None, m, FakeAdapter(), _convert)
    consented["ok"] = False
    with pytest.raises(registry.ConsentError):
        rd.run("channarith", tmp_path / "other", None, None, None, m, FakeAdapter(), _convert)
    doc = rd.publish(tmp_path, m, check_consent=lambda s: False)
    assert doc["voices"][0]["active"] is False
    assert json.loads((tmp_path / "channarith" / "index.json").read_text())["clips"] == {}
    assert rd.prune_revoked(tmp_path, check_consent=lambda s: False) == ["channarith"]
    assert not (tmp_path / "channarith").exists()


def test_vision_play_vector_copy_is_identical():
    lab = Path(__file__).resolve().parents[2] / "subrepos" / "theodore_children_webcam_lab" / "tests" / "hash_vectors.json"
    assert lab.read_bytes() == VECTORS.read_bytes()


def test_mobile_test_vectors_are_in_sync():
    mobile = (Path(__file__).resolve().parents[2] / "apps" / "mobile" / "src" / "__tests__" / "cloneVoice.test.ts").read_text(encoding="utf-8")
    for case in json.loads(VECTORS.read_text(encoding="utf-8"))["cases"]:
        assert case["hash"] in mobile


def test_landing_lines_are_in_the_manifest_and_shipped_as_default_clips():
    import json
    from pathlib import Path

    from tts_bakeoff.demo_voice import manifest as mf
    from tts_bakeoff.demo_voice.clip_hash import clip_hash, normalize

    rows = mf.landing()
    assert [r["demo"] for r in rows] == ["landing"] * len(rows) and len(rows) == 3
    committed = json.loads(mf.MANIFEST.read_text(encoding="utf-8"))
    in_manifest = {(c["lang"], c["hash"]) for c in committed["clips"] if c["demo"] == "landing"}
    web = Path(mf.ROOT) / "apps" / "web" / "public" / "landing-voice" / "salane"
    index = json.loads((web / "index.json").read_text(encoding="utf-8"))
    for r in rows:
        h = clip_hash(r["lang"], normalize(r["text"]))
        assert (r["lang"], h) in in_manifest
        assert h in index["clips"][r["lang"]]
        assert (web / r["lang"] / f"{h}.mp3").stat().st_size > 2000


def test_drivers_ed_presentation_lines_are_in_the_manifest() -> None:
    from tts_bakeoff.demo_voice import manifest as mf
    lines = mf.drivers_ed()
    assert len(lines) >= 40 and all(r["demo"] == "drivers_ed" and r["lang"] == "en" for r in lines)
    committed = json.loads(mf.MANIFEST.read_text(encoding="utf-8"))
    clips = [c for c in committed["clips"] if c["demo"] == "drivers_ed"]
    assert len(clips) == len({mf.normalize(r["text"]) for r in lines})
    # The slide the owner saw in the demo ("California learner's permit") is spoken, so it must be a clip.
    assert any("provisional instruction permit in California" in c["text"] for c in clips)


def test_drivers_ed_capture_collapses_duplicates(monkeypatch) -> None:
    from tts_bakeoff.demo_voice import manifest as mf
    slide = {"narration": "Slow down in fog.", "activity_prompt": "Name one rule.", "quiz_spec": {"prompt": "Why slow down?", "choices": ["Less sight", "No reason"]}}
    course = {"category": "driver_education", "language": "en", "slides": [slide]}
    monkeypatch.setattr(mf, "_get_json", lambda url: {"courses": [course, course, {"category": "food", "language": "en", "slides": [slide]}]})
    assert mf.drivers_ed_capture("https://example.test") == ["Slow down in fog.", "Name one rule.", "Why slow down?", "Less sight", "No reason"]

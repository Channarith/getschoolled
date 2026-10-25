"""publish and the uploader must never silently switch company voices off (the 2026-10-25 incident: publish ran on the Mac, which has no
consent records, so Channarith, Wei Miao and Wei were published inactive with empty indexes and the voice pickers lost them)."""
import json
from pathlib import Path

import pytest

from tts_bakeoff.demo_voice import assets as A
from tts_bakeoff.demo_voice import render as rd


def manifest():
    clips = [{"id": f"d:en:{i}", "demo": "d", "lang": "en", "text": f"line {i}", "hash": f"{i:014x}"} for i in range(10)]
    voices = [{"id": "channarith", "label": "Channarith", "speaker": "channarith", "model": "voxcpm2", "active": True, "primary_lang": "en"},
              {"id": "wei", "label": "Wei", "speaker": "wei", "model": "voxcpm2", "active": True, "primary_lang": "yue"}]
    return {"voices": voices, "clips": clips}


def make_clips(root: Path, voice: str, lang: str, n: int, start: int = 0):
    d = root / voice / lang
    d.mkdir(parents=True, exist_ok=True)
    for i in range(start, start + n):
        (d / f"{i:014x}.mp3").write_bytes(b"ID3" + b"x" * 600)
    return root


def write_index(root: Path, voice: str, clips: dict):
    (root / voice).mkdir(parents=True, exist_ok=True)
    (root / voice / "index.json").write_text(json.dumps({"voice": voice, "ext": "mp3", "clips": clips}), encoding="utf-8")


def previous_doc(*on):
    return {"voices": [{"id": v, "active": True} for v in on]}


def by_id(doc):
    return {v["id"]: v for v in doc["voices"]}


def test_publish_without_a_consent_registry_refuses_and_changes_nothing(tmp_path, monkeypatch):
    monkeypatch.setenv("GS_VOICES_DIR", str(tmp_path / "no-voices-here"))
    root = tmp_path / "assets"
    make_clips(root, "channarith", "en", 4)
    write_index(root, "channarith", {"en": [f"{i:014x}" for i in range(4)]})
    before = (root / "channarith" / "index.json").read_text()
    with pytest.raises(rd.PublishError) as exc:
        rd.publish(root, manifest())
    assert "Spark" in str(exc.value) and "--trust-previous" in str(exc.value)
    assert (root / "channarith" / "index.json").read_text() == before
    assert not (root / "voices.json").exists()


def test_cli_publish_refusal_is_an_error_exit(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("GS_VOICES_DIR", str(tmp_path / "empty"))
    (tmp_path / "empty").mkdir()
    assert rd.main(["publish", "--assets", str(tmp_path / "assets")]) == 2
    assert "publish refused" in capsys.readouterr().err


def test_trust_previous_keeps_voices_that_were_on_and_never_switches_one_on(tmp_path, monkeypatch):
    monkeypatch.setenv("GS_VOICES_DIR", str(tmp_path / "none"))
    root = tmp_path / "assets"
    make_clips(root, "channarith", "en", 5)
    make_clips(root, "wei", "yue", 3)
    notes = []
    doc = rd.publish(root, manifest(), trust_previous=previous_doc("channarith"), report=notes)
    voices = by_id(doc)
    assert voices["channarith"]["active"] is True          # was on: kept
    assert voices["wei"]["active"] is False                # was not on: cannot be verified here, so never switched on
    assert len(json.loads((root / "channarith" / "index.json").read_text())["clips"]["en"]) == 5
    assert any("wei" in n and "OFF" in n for n in notes) and any("channarith" in n and "kept ON" in n for n in notes)


def test_trust_previous_never_lists_a_revoked_voice(tmp_path, monkeypatch):
    monkeypatch.setenv("GS_VOICES_DIR", str(tmp_path / "none"))
    root = tmp_path / "assets"
    make_clips(root, "channarith", "en", 5)
    (root / "channarith" / "REVOKED").write_text("revoked", encoding="utf-8")
    doc = rd.publish(root, manifest(), trust_previous=previous_doc("channarith"))
    assert by_id(doc)["channarith"]["active"] is False
    assert json.loads((root / "channarith" / "index.json").read_text())["clips"] == {}   # on purpose: a revoked voice lists nothing


def test_revoked_consent_with_a_registry_present_switches_the_voice_off_on_purpose(tmp_path):
    root = tmp_path / "assets"
    make_clips(root, "channarith", "en", 3)
    write_index(root, "channarith", {"en": [f"{i:014x}" for i in range(3)]})
    doc = rd.publish(root, manifest(), check_consent=lambda speaker: False)
    assert by_id(doc)["channarith"]["active"] is False
    assert json.loads((root / "channarith" / "index.json").read_text())["clips"] == {}


def test_an_empty_index_never_replaces_a_non_empty_one_unless_allowed(tmp_path):
    root = tmp_path / "assets"
    write_index(root, "channarith", {"en": [f"{i:014x}" for i in range(6)]})   # published list, but no clip files found now
    notes = []
    doc = rd.publish(root, manifest(), check_consent=lambda speaker: True, report=notes)
    assert by_id(doc)["channarith"]["active"] is True
    assert len(json.loads((root / "channarith" / "index.json").read_text())["clips"]["en"]) == 6   # kept
    assert any("EMPTY" in n and "channarith" in n for n in notes)
    rd.publish(root, manifest(), check_consent=lambda speaker: True, allow_empty_index=["channarith"])
    assert json.loads((root / "channarith" / "index.json").read_text())["clips"] == {}


def test_summary_warns_when_an_active_voice_covers_under_90_percent(tmp_path):
    root = tmp_path / "assets"
    m = manifest()
    write_index(root, "channarith", {"en": [c["hash"] for c in m["clips"][:4]]})   # 4 of 10 lines
    write_index(root, "wei", {"en": [c["hash"] for c in m["clips"]]})              # all 10
    doc = {"voices": [{"id": "channarith", "active": True}, {"id": "wei", "active": True}, {"id": "off", "active": False}]}
    rows = {r["id"]: r for r in rd.summarize(doc, root, m)}
    assert rows["channarith"]["coverage"] == 40 and rows["wei"]["coverage"] == 100
    table, warns = rd.format_summary(list(rows.values()))
    assert "channarith" in table and "40%" in table
    assert len(warns) == 1 and "channarith" in warns[0] and "40%" in warns[0] and "same-gender" in warns[0]


# ---------------------------------------------------------------------------- uploader
def doc_of(**on):
    return {"voices": [{"id": k, "active": v} for k, v in on.items()]}


def test_diff_lists_voices_switched_off_and_clips_per_voice():
    local = doc_of(channarith=False, wei=True)
    local_idx = {"wei": {"clips": {"yue": ["a", "b", "c"]}}, "channarith": {"clips": {}}}
    remote = doc_of(channarith=True, wei=True)
    remote_idx = {"channarith": {"clips": {"en": ["1", "2"]}}, "wei": {"clips": {"yue": ["a", "b"]}}}
    d = A.publish_diff(local, local_idx, remote, remote_idx)
    assert d["deactivated"] == ["channarith"] and d["activated"] == []
    assert d["added"] == {"wei": 1} and d["removed"] == {"channarith": 2}
    text = A.format_diff(d)
    assert "switched OFF: channarith" in text and "wei: +1" in text and "channarith: +0 clips listed, -2" in text


def test_sanity_refuses_deactivation_and_halved_indexes_unless_allowed():
    d = {"activated": [], "deactivated": ["channarith"], "added": {}, "removed": {}, "shrunk": ["wei"]}
    problems = A.sanity_problems(d)
    assert len(problems) == 2 and "--allow-deactivate channarith" in problems[0] and "less than half" in problems[1]
    assert A.sanity_problems(d, allow_deactivate=["channarith"], allow_shrink=True) == []


def _assets_with(tmp_path, local_voices, local_clips):
    (tmp_path / "voices.json").write_text(json.dumps(local_voices), encoding="utf-8")
    for vid, clips in local_clips.items():
        make_clips(tmp_path, vid, "en", len(clips))
        write_index(tmp_path, vid, {"en": clips})
    return tmp_path


def test_dry_run_prints_the_diff_and_exits_nonzero_when_a_live_voice_would_go_dark(tmp_path, monkeypatch, capsys):
    root = _assets_with(tmp_path, doc_of(channarith=False), {"channarith": []})
    monkeypatch.setattr(A, "remote_state", lambda s: (doc_of(channarith=True), {"channarith": {"clips": {"en": ["1", "2", "3"]}}}))
    assert A.main(["sync", "--assets", str(root), "--dry-run"]) == 2
    out = capsys.readouterr()
    assert "switched OFF: channarith" in out.out and "refusing to upload" in out.err
    assert "nothing uploaded" not in out.out   # it stopped before the aws plan


def test_allow_deactivate_lets_an_intended_withdrawal_through(tmp_path, monkeypatch, capsys):
    root = _assets_with(tmp_path, doc_of(channarith=False), {"channarith": []})
    monkeypatch.setattr(A, "remote_state", lambda s: (doc_of(channarith=True), {"channarith": {"clips": {"en": ["1"]}}}))
    assert A.main(["sync", "--assets", str(root), "--dry-run", "--allow-deactivate", "channarith"]) == 0
    assert "dry run: nothing uploaded" in capsys.readouterr().out


def test_an_index_that_would_halve_is_refused(tmp_path, monkeypatch, capsys):
    root = _assets_with(tmp_path, doc_of(channarith=True), {"channarith": ["0000000000000a"]})
    remote_clips = [f"{i:014x}" for i in range(10)]
    monkeypatch.setattr(A, "remote_state", lambda s: (doc_of(channarith=True), {"channarith": {"clips": {"en": remote_clips}}}))
    assert A.main(["sync", "--assets", str(root), "--dry-run"]) == 2
    assert "less than half" in capsys.readouterr().err


def test_unreachable_published_list_refuses_a_real_upload_but_not_a_dry_run(tmp_path, monkeypatch, capsys):
    root = _assets_with(tmp_path, doc_of(channarith=True), {"channarith": ["0000000000000a"]})

    def boom(s):
        raise A.SanityCheckUnavailable("offline")
    monkeypatch.setattr(A, "remote_state", boom)
    assert A.main(["sync", "--assets", str(root), "--dry-run"]) == 0
    assert "safety check was skipped" in capsys.readouterr().out
    monkeypatch.setenv("VOICE_ASSETS_ACCESS_KEY", "AKIATEST")
    monkeypatch.setenv("VOICE_ASSETS_SECRET_KEY", "SECRETTEST")
    assert A.main(["sync", "--assets", str(root)]) == 2
    assert "refusing to upload" in capsys.readouterr().err


def test_fetch_public_json_treats_404_as_nothing_published_yet(monkeypatch):
    import urllib.error

    def raise_404(req, timeout=0):
        raise urllib.error.HTTPError(req.full_url, 404, "nope", {}, None)
    monkeypatch.setattr(A.urllib.request, "urlopen", raise_404)
    assert A.fetch_public_json("https://example.invalid/voices.json") is None

    def raise_500(req, timeout=0):
        raise urllib.error.HTTPError(req.full_url, 500, "boom", {}, None)
    monkeypatch.setattr(A.urllib.request, "urlopen", raise_500)
    with pytest.raises(A.SanityCheckUnavailable):
        A.fetch_public_json("https://example.invalid/voices.json")


def test_a_render_on_a_machine_without_consent_records_keeps_its_clips_and_leaves_voices_json_alone(tmp_path, monkeypatch, capsys):
    from tts_bakeoff.voice_clone import registry

    class Fake:
        languages = {"en"}

        def synthesize(self, text, lang, out):
            Path(out).write_bytes(b"RIFF" + b"0" * 800)

    monkeypatch.setenv("GS_VOICES_DIR", str(tmp_path / "none"))                      # no consent records on this machine
    monkeypatch.setattr(registry, "require_consent", lambda *a, **k: {})            # but synthesis is allowed (stubbed)
    root = tmp_path / "assets"
    root.mkdir()
    published = json.dumps(doc_of(channarith=True))
    (root / "voices.json").write_text(published, encoding="utf-8")
    m = manifest()
    stats = rd.run("channarith", root, None, {"en"}, 3, m, Fake(), lambda w, mp3: Path(mp3).write_bytes(Path(w).read_bytes()))
    assert stats["ok"] == 3 and stats["failed"] == 0                               # the render finishes and keeps its clips
    assert len(list((root / "channarith" / "en").glob("*.mp3"))) == 3
    assert (root / "voices.json").read_text() == published                           # the published list was not rewritten (no voice switched off)
    assert "voices.json was NOT rewritten" in capsys.readouterr().out

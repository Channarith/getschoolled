import json
import os
import threading
import time

import pytest

from tts_bakeoff.adapters.cosyvoice2 import CosyVoice2Adapter
from tts_bakeoff.adapters.voxcpm2 import VoxCPM2Adapter
from tts_bakeoff.voice_clone import bakeoff, profile, progress, runner, status

from .test_voice_profile import _speaker


def _two(tmp_path):
    _speaker(tmp_path, [("en.wav", "en", 60, 30, False, None)], name="Wei Miao", speaker="wei-miao")
    _speaker(tmp_path, [("yue.wav", "yue", 60, 30, False, None)], name="Wei", speaker="wei")


def _rows(out, vid):
    return [json.loads(l) for l in (out / vid / "manifest.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]


def test_rerun_skips_finished_clips_and_force_regenerates(tmp_path):
    _two(tmp_path)
    out = tmp_path / "out"
    kw = dict(base=tmp_path, gpu=False, takes=1, clean=False)
    first = bakeoff.synthesize_all(out, ["wei-miao"], ["mock"], ["en", "es"], 2, **kw)
    assert first["ok"] == 4 and first["skipped_existing"] == 0
    wavs = sorted((out / "mock~wei-miao").rglob("*.wav"))
    stamp = {p: p.stat().st_mtime_ns for p in wavs}
    again = bakeoff.synthesize_all(out, ["wei-miao"], ["mock"], ["en", "es"], 2, **kw)
    assert again["ok"] == 0 and again["skipped_existing"] == 4
    assert {p: p.stat().st_mtime_ns for p in wavs} == stamp          # nothing was rewritten
    assert len(_rows(out, "mock~wei-miao")) == 4                       # and no duplicate rows
    forced = bakeoff.synthesize_all(out, ["wei-miao"], ["mock"], ["en", "es"], 2, force=True, **kw)
    assert forced["ok"] == 4 and len(_rows(out, "mock~wei-miao")) == 4  # compacted: one row per clip


def test_failed_or_tiny_clips_are_redone_but_good_ones_kept(tmp_path):
    _two(tmp_path)
    out = tmp_path / "out"
    kw = dict(base=tmp_path, gpu=False, takes=1, clean=False)
    bakeoff.synthesize_all(out, ["wei-miao"], ["mock"], ["en"], 3, **kw)
    root = out / "mock~wei-miao"
    rows = _rows(root.parent, "mock~wei-miao")
    bad_wav = root.parent / rows[0]["wav"]
    bad_wav.write_bytes(b"RIFF")                                       # truncated file: smaller than a real clip
    rows[1]["status"] = "failed"
    (root / "manifest.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    counts = bakeoff.synthesize_all(out, ["wei-miao"], ["mock"], ["en"], 3, **kw)
    assert counts["ok"] == 2 and counts["skipped_existing"] == 1
    assert bad_wav.stat().st_size > progress.MIN_WAV_BYTES
    assert [r["status"] for r in _rows(out, "mock~wei-miao")] == ["ok", "ok", "ok"]


def test_all_means_every_supported_language_own_language_first():
    vox = runner.ordered_languages(set(VoxCPM2Adapter.languages), ["yue"])
    assert len(vox) == 31 and vox[0] == "yue" and set(vox) == VoxCPM2Adapter.languages
    assert {"ja", "ko", "ar", "fil", "nb", "my", "lo"} <= set(vox)       # the model card's languages, under our codes
    cosy = runner.ordered_languages(set(CosyVoice2Adapter.languages), ["en"])
    assert cosy[0] == "en" and set(cosy) == CosyVoice2Adapter.languages and "yue" not in cosy
    assert VoxCPM2Adapter.languages <= runner.sentence_langs() and CosyVoice2Adapter.languages <= runner.sentence_langs()


def test_langs_all_on_run_is_supported_but_tones_keep_the_demo_set():
    assert bakeoff._langs_arg("all", supported=True) == runner.SUPPORTED
    assert bakeoff._langs_arg("all") == list(profile.ALL_LANGS) and bakeoff._langs_arg("") is None


def test_plan_default_is_own_language_and_all_adds_cross_lingual(tmp_path):
    _two(tmp_path)
    own = runner.make_plan(["wei", "wei-miao"], ["mock"], None, tmp_path)
    assert sorted((u.speaker, u.lang) for u in own.units) == [("wei", "yue"), ("wei-miao", "en")] or own.unsupported == 1
    allp = runner.make_plan(["wei-miao"], ["mock"], runner.SUPPORTED, tmp_path)
    langs = [u.lang for u in allp.units]
    assert langs[0] == "en" and len(langs) == len(set(langs)) > 5


def test_clamp_workers_respects_the_memory_gate():
    assert runner.clamp_workers(4, ["voxcpm2"], 69.0) == (4, "")
    n, note = runner.clamp_workers(4, ["voxcpm2"], 30.0)
    assert n == 1 and "reduced 4 -> 1" in note
    assert runner.clamp_workers(4, ["voxcpm2"], 30.0, strict=True)[0] == 0
    assert runner.clamp_workers(3, ["voxcpm2"], 14.0)[0] == 1            # always at least one worker unless strict
    assert runner.clamp_workers(5, ["voxcpm2"], None) == (5, "")         # not Linux: nothing to measure
    assert runner.clamp_workers(5, ["mock"], 20.0) == (5, "")


def test_parallel_workers_share_the_work_and_leave_one_row_per_clip(tmp_path, monkeypatch):
    _two(tmp_path)
    monkeypatch.setenv("GS_VOICES_DIR", str(tmp_path))
    out = tmp_path / "out"
    counts = bakeoff.synthesize_all(out, ["wei", "wei-miao"], ["mock"], ["en", "es", "vi"], 2, base=tmp_path, gpu=False, takes=1,
                                    clean=False, workers=2)
    assert counts["ok"] == 12 and counts["failed"] == 0                 # 2 speakers x 3 languages x 2 sentences
    for vid in ("mock~wei", "mock~wei-miao"):
        rows = _rows(out, vid)
        assert len(rows) == 6 and len({r["wav"] for r in rows}) == 6 and all(r["status"] == "ok" for r in rows)
        assert all((out / r["wav"]).stat().st_size > progress.MIN_WAV_BYTES for r in rows)
    ws = progress.read_workers(out)
    assert len(ws) == 2 and all(w["finished"] for w in ws) and sum(w["done"] for w in ws) == 12 and all(w["done"] > 0 for w in ws)
    summary = json.loads((out / "progress.json").read_text())
    assert summary["clips_total"] == 12 and summary["clips_done"] == 12 and summary["running"] is False
    again = bakeoff.synthesize_all(out, ["wei", "wei-miao"], ["mock"], ["en", "es", "vi"], 2, base=tmp_path, gpu=False, takes=1, clean=False, workers=2)
    assert again["ok"] == 0 and again["skipped_existing"] == 12


def test_workers_never_exceed_the_units(tmp_path):
    _two(tmp_path)
    out = tmp_path / "out"
    counts = bakeoff.synthesize_all(out, ["wei-miao"], ["mock"], ["en"], 1, base=tmp_path, gpu=False, takes=1, clean=False, workers=8)
    assert counts["ok"] == 1 and len(progress.read_workers(out)) == 1    # one unit: in-process, no subprocess


def test_status_reports_done_incomplete_and_running(tmp_path):
    _two(tmp_path)
    out = tmp_path / "out"
    bakeoff.synthesize_all(out, ["wei-miao"], ["mock"], ["en", "es"], 2, base=tmp_path, gpu=False, takes=1, clean=False)

    class A:
        pass

    a = A()
    a.out, a.speakers, a.models, a.langs, a.limit = str(out), "", "", "", 3
    lines, verdict = status.report(a)
    assert verdict == "DONE" and lines[-1] == "DONE" and any("mock~wei-miao" in l and "4/4" in l for l in lines)
    victim = next((out / "mock~wei-miao" / "es").glob("*.wav"))
    victim.unlink()
    lines, verdict = status.report(a)
    assert verdict.startswith("INCOMPLETE (1 clip(s) missing") and any("to do: es 1/2" in l for l in lines)
    w = json.loads((out / progress.PROGRESS_DIR / "worker-0.json").read_text())
    w.update(finished=False, pid=os.getpid(), current={"speaker": "wei-miao", "model": "mock", "lang": "es"}, recent_clip_seconds=[2.0])
    (out / progress.PROGRESS_DIR / "worker-0.json").write_text(json.dumps(w))
    lines, verdict = status.report(a)
    assert verdict == "RUNNING" and any(l.startswith("ETA: 2s") for l in lines) and any("now: wei-miao / mock / es" in l for l in lines)


def test_status_without_a_plan_shows_what_exists(tmp_path):
    out = tmp_path / "out"
    (out / "voxcpm2~x").mkdir(parents=True)
    (out / "voxcpm2~x" / "en").mkdir()
    (out / "voxcpm2~x" / "en" / "S01.wav").write_bytes(b"x" * 5000)
    (out / "voxcpm2~x" / "manifest.jsonl").write_text(json.dumps({"lang": "en", "id": "S01", "wav": "voxcpm2~x/en/S01.wav", "status": "ok"}) + "\n")

    class A:
        pass

    a = A()
    a.out, a.speakers, a.models, a.langs, a.limit = str(out), "", "", "", 3
    lines, verdict = status.report(a)
    assert verdict == "DONE" and any("voxcpm2~x" in l and "en:1" in l for l in lines)


def test_one_model_is_shared_by_every_speakers_adapter(monkeypatch):
    class Inner:
        options: dict = {}
        def __init__(self):
            self._model = None
        def synthesize(self, *a, **k):
            self._model = self._model or object()
            return {}

    monkeypatch.setattr(profile.ProfileAdapter, "use", lambda self, lang: None)
    profile.MODEL_CACHE.pop("fake-model", None)
    first = profile.ProfileAdapter(Inner(), "a", cache_key="fake-model")
    first.synthesize("hi", "en", "x.wav")
    second = profile.ProfileAdapter(Inner(), "b", cache_key="fake-model")
    assert second.inner._model is first.inner._model is profile.MODEL_CACHE["fake-model"]   # loaded once, reused
    profile.MODEL_CACHE.pop("fake-model", None)


def test_synthesis_is_serialized_across_threads(monkeypatch):
    state = {"now": 0, "max": 0}
    guard = threading.Lock()

    class Inner:
        options: dict = {}
        _model = None
        def synthesize(self, *a, **k):
            with guard:
                state["now"] += 1
                state["max"] = max(state["max"], state["now"])
            time.sleep(0.03)
            with guard:
                state["now"] -= 1
            return {}

    monkeypatch.setattr(profile.ProfileAdapter, "use", lambda self, lang: None)
    ad = profile.ProfileAdapter(Inner(), "a")
    ts = [threading.Thread(target=ad.synthesize, args=("t", "en", "x.wav")) for _ in range(6)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert state["max"] == 1                                              # one GPU synthesis at a time; the CPU stage runs outside the lock

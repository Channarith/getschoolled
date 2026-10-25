import json
import math
import wave
from pathlib import Path

import pytest

np = pytest.importorskip("numpy")

from tts_bakeoff.adapters.base import Adapter, write_wav  # noqa: E402
from tts_bakeoff.voice_clone import bakeoff, clean, enroll, registry  # noqa: E402

RATE = 24000


LINE = "Good morning and welcome to today's lesson, we will start with something simple and then build."   # ~6 s of speech


def speech(secs=6.0, seed=0, hiss=0.0, hum=0.0, clicks=0):
    """Voiced, syllable-gated harmonic signal with pauses; optional white hiss, 50 Hz mains hum and impulse clicks."""
    rng = np.random.default_rng(seed)
    t = np.arange(int(secs * RATE)) / RATE
    f0 = 130 + 25 * np.sin(2 * math.pi * 0.7 * t)
    phase = 2 * math.pi * np.cumsum(f0) / RATE
    voiced = sum(np.sin(k * phase) / k for k in range(1, 12))
    gate = (np.sin(2 * math.pi * 1.6 * t) > -0.2).astype(float)
    gate = np.convolve(gate, np.ones(480) / 480, mode="same")
    x = 0.25 * gate * voiced
    if hiss:
        x = x + hiss * rng.standard_normal(len(t))
    if hum:
        x = x + hum * (np.sin(2 * math.pi * 50 * t) + 0.7 * np.sin(2 * math.pi * 100 * t) + 0.5 * np.sin(2 * math.pi * 150 * t))
    positions = rng.choice(np.arange(2000, len(t) - 2000), size=clicks, replace=False) if clicks else []
    for p in positions:
        x[p] += rng.choice([-0.6, 0.6])
    return x.astype("float32"), sorted(int(p) for p in positions)


def test_declick_finds_and_fixes_injected_clicks():
    dirty, pos = speech(clicks=12)
    ref, _ = speech()
    found = clean.find_clicks(dirty, RATE)
    assert len(found) >= 10
    fixed, n = clean.declick(dirty, RATE)
    assert n >= 10 and len(clean.find_clicks(fixed, RATE)) <= 1
    assert np.abs(fixed - ref).max() < 0.25 and np.abs(fixed - ref).mean() < np.abs(dirty - ref).mean()


def test_clean_speech_has_no_clicks():
    x, _ = speech()
    assert clean.find_clicks(x, RATE) == []


def test_gate_lowers_hiss_without_moving_tone_colour():
    x, _ = speech(hiss=0.01)
    y, rep = clean.clean_synthesis(x, RATE)
    assert rep["kept_cleaned"], rep["reasons"]
    assert rep["after"]["noise_floor_dbfs"] < rep["before"]["noise_floor_dbfs"] - 3
    assert rep["timbre_shift_db"] <= clean.TIMBRE_LIMIT_DB["synthesis"]
    assert len(y) == len(x)


def test_hum_is_detected_and_notched():
    x, _ = speech(hum=0.02)
    base, db, notches = clean.detect_hum(x, RATE)
    assert base == 50 and db > 15 and 100 in notches
    y, rep = clean.clean_reference(x, RATE)
    assert rep["after"]["hum_db"] < rep["before"]["hum_db"] - 8


def test_steady_voice_is_not_mistaken_for_hum():
    x, _ = speech()
    assert clean.detect_hum(x, RATE)[0] is None


def test_reference_keeps_original_when_cleaning_would_change_the_voice():
    x, _ = speech()
    muffled = np.convolve(x, np.ones(24) / 24, mode="same").astype("float32")
    assert clean.timbre_shift_db(x, muffled, RATE) > clean.TIMBRE_LIMIT_DB["reference"]


def test_overprocessing_is_refused(monkeypatch):
    x, _ = speech(hiss=0.01)
    monkeypatch.setattr(clean, "spectral_gate", lambda a, r, s, f: np.convolve(a, np.ones(24) / 24, mode="same").astype("float32"))
    y, rep = clean.clean_reference(x, RATE)
    assert not rep["kept_cleaned"] and np.array_equal(y, x) and rep["reasons"]


def test_clipping_and_clean_score(tmp_path):
    clipped = np.clip(speech()[0] * 6, -1, 1)
    assert clean.analyze(clipped, RATE)["clip_pct"] > 0.5
    good = clean.analyze(speech()[0], RATE)["score"]
    assert clean.analyze(speech(hiss=0.02, hum=0.03, clicks=15, seed=2)[0], RATE)["score"] > good + 5


def test_error_rate():
    assert clean.error_rate("the cat sat down", "the cat sat down") == 0
    assert clean.error_rate("the cat sat down", "the bat sat") == pytest.approx(0.5)
    assert clean.error_rate("你好世界", "你好世", chars=True) == pytest.approx(0.25)


def test_clean_file_in_place_keeps_raw_and_is_idempotent(tmp_path):
    p = tmp_path / "en" / "S01.wav"
    p.parent.mkdir()
    write_wav(p, speech(hiss=0.01, clicks=6)[0], RATE)
    original = p.read_bytes()
    rep = clean.clean_file(p)
    assert rep["kept_cleaned"] and p.read_bytes() != original
    assert (p.parent / ".raw" / "S01.wav").read_bytes() == original
    assert (p.parent / ".raw" / "S01.clean.json").exists()
    once = p.read_bytes()
    assert clean.clean_file(p).get("skipped")
    assert p.read_bytes() == once
    clean.clean_file(p, force=True)
    assert p.read_bytes() == once and (p.parent / ".raw" / "S01.wav").read_bytes() == original


def test_cli_single_file_and_folder(tmp_path, capsys):
    src, dst = tmp_path / "a.wav", tmp_path / "b.wav"
    write_wav(src, speech(hiss=0.01, hum=0.02, clicks=5)[0], RATE)
    assert clean.main(["--in", str(src), "--out", str(dst)]) == 0
    out = capsys.readouterr().out
    assert "before" in out and "after" in out and "noise score" in out
    assert dst.exists() and not (tmp_path / ".raw").exists()
    run = tmp_path / "run"
    write_wav(run / "m" / "en" / "S01.wav", speech(clicks=4)[0], RATE)
    assert clean.main(["--dir", str(run)]) == 0
    assert (run / "m" / "en" / ".raw" / "S01.wav").exists()


class Takes(Adapter):
    name = "takes"
    languages = {"en"}

    def __init__(self, signals):
        super().__init__()
        self.signals, self.calls = signals, 0

    def synthesize(self, text, lang, out_wav):
        x = self.signals[self.calls % len(self.signals)]
        self.calls += 1
        write_wav(out_wav, x, RATE)
        return {"duration_s": len(x) / RATE, "synth_s": 0.1, "sample_rate": RATE, "rtf": 0.1}


def test_best_of_n_picks_the_cleanest_take(tmp_path):
    noisy = speech(hiss=0.02, hum=0.03, clicks=15, seed=3)[0]
    ok = speech(seed=4)[0]
    ad = Takes([noisy, ok, speech(clicks=8, seed=5)[0]])
    out = tmp_path / "m" / "en" / "S01.wav"
    row = clean.synthesize_best_of(ad, LINE, "en", out, takes=3, clean=True)
    assert ad.calls == 3 and row["chosen_take"] == 1 and row["takes"] == 3
    side = json.loads((out.parent / ".raw" / "S01.clean.json").read_text())
    assert [t["take"] for t in side["takes"]] == [0, 1, 2] and side["chosen"] == 1
    assert out.exists() and (out.parent / ".raw" / "S01.wav").exists()
    assert not list((out.parent / ".raw").glob("*.take*.wav"))


def test_opt_out_is_the_plain_single_call(tmp_path):
    ad = Takes([speech()[0]])
    out = tmp_path / "S01.wav"
    row = clean.synthesize_best_of(ad, LINE, "en", out, takes=1, clean=False)
    assert ad.calls == 1 and out.exists() and not (tmp_path / ".raw").exists() and "takes" not in row


def test_takes_without_cleaning_keeps_the_best_take_only(tmp_path):
    ad = Takes([speech(clicks=15, seed=6)[0], speech(seed=7)[0]])
    out = tmp_path / "S01.wav"
    row = clean.synthesize_best_of(ad, LINE, "en", out, takes=2, clean=False)
    assert row["chosen_take"] == 1 and out.exists() and not (tmp_path / ".raw" / "S01.wav").exists()


def test_one_failed_take_is_tolerated(tmp_path):
    class Flaky(Takes):
        def synthesize(self, text, lang, out_wav):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("boom")
            return super().synthesize(text, lang, out_wav)

    out = tmp_path / "S01.wav"
    row = clean.synthesize_best_of(Flaky([speech()[0]]), LINE, "en", out, takes=2, clean=True)
    assert out.exists() and row["takes"] == 1


def test_enroll_prepare_cleans_keeps_raw_and_can_opt_out(tmp_path):
    x, _ = speech(secs=30, hiss=0.003, hum=0.01, clicks=10)
    src = tmp_path / "me.wav"
    write_wav(src, x, RATE)
    info = enroll.prepare(src, tmp_path / "samples" / "me.wav")
    assert info["cleaned"] is True and isinstance(info["warnings"], list)
    assert (tmp_path / "samples" / ".raw" / "me.wav").exists()
    enroll.prepare(src, tmp_path / "s2" / "me.wav", clean=False)
    assert not (tmp_path / "s2" / ".raw").exists()


def test_env_opt_out(monkeypatch):
    monkeypatch.setenv("GS_CLONE_CLEAN", "0")
    assert clean.enabled() is False
    monkeypatch.setenv("GS_CLONE_TAKES", "99")
    assert clean.default_takes() == 8


def test_bakeoff_run_writes_best_take_and_sidecars(tmp_path, monkeypatch):
    monkeypatch.setenv("GS_VOICES_DIR", str(tmp_path / "voices"))
    base = tmp_path / "voices"
    form = tmp_path / "f.pdf"
    form.write_bytes(b"%PDF signed " * 20)
    registry.record_consent("alice", "Alice Tran", "employee", form, base=base)
    src = tmp_path / "a.wav"
    write_wav(src, speech(secs=30, seed=9)[0], RATE)
    dest = base / "alice" / "samples" / "a.wav"
    enroll.prepare(src, dest)
    registry.add_sample("alice", dest, "hello this is my recorded sample sentence", "en", base)
    out = tmp_path / "out"
    counts = bakeoff.synthesize_all(out, ["alice"], ["mock"], ["en"], 1, base=base, gpu=False, takes=2, clean=True)
    assert counts["ok"] == 1 and counts["failed"] == 0
    rows = [json.loads(line) for line in (out / "mock~alice" / "manifest.jsonl").read_text().splitlines()]
    assert rows[0]["status"] == "ok" and rows[0]["takes"] == 2
    assert (out / "mock~alice" / "en" / ".raw").is_dir()

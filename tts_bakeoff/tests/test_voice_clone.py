import json
import math
import wave
from pathlib import Path

import pytest

np = pytest.importorskip("numpy")

from tts_bakeoff.voice_clone import bakeoff, enroll, registry, synth  # noqa: E402


def _speech(path: Path, secs=30, noise=0.001):
    rate = 24000
    t = np.arange(int(secs * rate)) / rate
    rng = np.random.default_rng(1)
    env = (np.sin(2 * math.pi * 2 * t) > -0.3).astype(float)
    x = 0.3 * env * np.sin(2 * math.pi * 150 * t) + noise * rng.standard_normal(len(t))
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())
    return path


@pytest.fixture
def base(tmp_path, monkeypatch):
    monkeypatch.setenv("GS_VOICES_DIR", str(tmp_path / "voices"))
    return tmp_path / "voices"


@pytest.fixture
def form(tmp_path):
    f = tmp_path / "signed.pdf"
    f.write_bytes(b"%PDF signed form " * 20)
    return f


def _enrolled(base, form, tmp_path):
    registry.record_consent("alice", "Alice Tran", "employee", form, base=base)
    src = _speech(tmp_path / "alice.wav")
    dest = base / "alice" / "samples" / "alice.wav"
    enroll.prepare(src, dest)
    registry.add_sample("alice", dest, "hello this is my recorded sample sentence", "en", base)


def test_no_consent_refuses(base):
    with pytest.raises(registry.ConsentError):
        registry.require_consent("bob", base=base)
    with pytest.raises(registry.ConsentError):
        synth.build_adapter("mock", "bob", base, gpu=False)


def test_consent_needs_real_form_and_all_scopes(base, tmp_path, form):
    with pytest.raises(registry.ConsentError):
        registry.record_consent("alice", "A", "employee", tmp_path / "missing.pdf", base=base)
    with pytest.raises(registry.ConsentError):
        registry.record_consent("alice", "A", "employee", form, scopes=("course_narration",), base=base)
    with pytest.raises(registry.ConsentError):
        registry.record_consent("alice", "A", "contractor", form, base=base)


def test_enroll_requires_consent(base, tmp_path):
    (base / "carol" / "samples").mkdir(parents=True)
    w = _speech(base / "carol" / "samples" / "c.wav")
    with pytest.raises(registry.ConsentError):
        registry.add_sample("carol", w, "x", "en", base)


def test_sample_checks(tmp_path):
    with pytest.raises(enroll.SampleError):
        enroll.prepare(_speech(tmp_path / "short.wav", secs=5), tmp_path / "o.wav")
    with pytest.raises(enroll.SampleError):
        enroll.prepare(_speech(tmp_path / "noisy.wav", noise=0.2), tmp_path / "o.wav")
    info = enroll.prepare(_speech(tmp_path / "ok.wav"), tmp_path / "o.wav")
    assert enroll.MIN_S <= info["seconds"] <= enroll.MAX_S and info["sample_rate"] == 24000


def test_revoke_and_tamper(base, form, tmp_path):
    _enrolled(base, form, tmp_path)
    assert registry.require_consent("alice", base=base)["role"] == "employee"
    s = base / "alice" / "samples" / "alice.wav"
    s.write_bytes(s.read_bytes() + b"\0\0")
    with pytest.raises(registry.ConsentError, match="changed"):
        registry.require_consent("alice", base=base)
    _enrolled_fresh = base / "alice" / "consent.json"
    rec = json.loads(_enrolled_fresh.read_text()); rec["samples"] = {}; _enrolled_fresh.write_text(json.dumps(rec))
    registry.revoke("alice", base)
    with pytest.raises(registry.ConsentError, match="revoked"):
        registry.require_consent("alice", base=base)


def test_bakeoff_writes_lab_run(base, form, tmp_path):
    _enrolled(base, form, tmp_path)
    out = tmp_path / "clones"
    counts = bakeoff.synthesize_all(out, ["alice", "mallory"], ["mock"], ["en"], 2, base=base, gpu=False)
    assert counts["ok"] == 2 and counts["refused"] == 1
    meta = json.loads((out / "mock~alice" / "meta.json").read_text())
    assert meta["clone"] and meta["consented"] and meta["speaker"] == "alice"
    assert not (out / "mock~mallory").exists()
    rows = [json.loads(line) for line in (out / "mock~alice" / "manifest.jsonl").read_text().splitlines()]
    assert all((out / r["wav"]).is_file() for r in rows)


def test_unknown_model_is_not_a_clone_model(base, form, tmp_path):
    _enrolled(base, form, tmp_path)
    with pytest.raises(registry.ConsentError):
        synth.build_adapter("edge_tts", "alice", base, gpu=False)

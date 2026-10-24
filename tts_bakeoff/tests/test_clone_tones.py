import json
import math
import shutil
import wave
from pathlib import Path

import pytest

np = pytest.importorskip("numpy")

from tts_bakeoff.adapters.cosyvoice2 import CosyVoice2Adapter  # noqa: E402
from tts_bakeoff.adapters.voxcpm2 import VoxCPM2Adapter  # noqa: E402
from tts_bakeoff.voice_clone import registry, tones  # noqa: E402
from tts_bakeoff.voice_types import BLEND_WEIGHTS, PRESETS  # noqa: E402
from tts_bakeoff.tests.test_voice_clone import _enrolled, base, form  # noqa: E402,F401

needs_ffmpeg = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")


def _tone_wav(path: Path, hz=200.0, secs=2.0, rate=24000):
    t = np.arange(int(secs * rate)) / rate
    x = 0.3 * np.sin(2 * math.pi * hz * t)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
        w.writeframes((x * 32767).astype("<i2").tobytes())
    return path


def _read(path: Path):
    with wave.open(str(path), "rb") as w:
        rate, n = w.getframerate(), w.getnframes()
        return np.frombuffer(w.readframes(n), dtype="<i2").astype("float64") / 32768.0, rate


def _peak_hz(x, rate):
    spec = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    return np.argmax(spec) * rate / len(x)


@pytest.fixture
def addendum(tmp_path):
    f = tmp_path / "stylized-signed.pdf"
    f.write_bytes(b"%PDF signed stylized addendum " * 10)
    return f


def test_every_preset_and_blend_is_defined_and_capped():
    assert set(tones.TONES) == set(PRESETS) | set(BLEND_WEIGHTS)
    for t in tones.TONES.values():
        assert abs(t.semitones) <= tones.MAX_SEMITONES + 1e-9
        assert abs(t.tempo - 1) <= tones.MAX_TEMPO + 1e-9
        assert abs(t.tilt_db) <= tones.MAX_TILT_DB + 1e-9 and abs(t.gain_db) <= tones.MAX_GAIN_DB + 1e-9


def test_blend_lies_between_its_parents():
    pro, cute, mix = tones.TONES["professional"], tones.TONES["cute"], tones.TONES["professional50-cute50"]
    assert pro.semitones < mix.semitones < cute.semitones
    assert tones.TONES["professional75-cute25"].semitones < mix.semitones < tones.TONES["professional25-cute75"].semitones
    assert tones.TONES["anime"].semitones > tones.TONES["cute"].semitones > 0 > tones.TONES["heavy"].semitones


def test_model_side_prompts():
    assert "cute" in tones.vox_style(tones.TONES["cute"])
    mix = tones.vox_style(tones.TONES["pro60-cute20-anime20"])
    assert mix.startswith("mostly ") and "cute" in mix and "anime" in mix
    inst = tones.cosy_instruct(tones.TONES["anime"])
    assert inst.endswith("<|endofprompt|>") and tones.cosy_instruct(tones.TONES["professional50-cute50"]).count("<|endofprompt|>") == 1


@needs_ffmpeg
@pytest.mark.parametrize("name", ["cute", "anime", "heavy", "tough", "professional50-cute50"])
def test_dsp_shifts_pitch_by_the_expected_ratio_and_keeps_duration(tmp_path, name):
    src = _tone_wav(tmp_path / "in.wav")
    out = tones.apply_tone_dsp(src, tmp_path / "out.wav", name)
    x0, r0 = _read(src)
    x1, r1 = _read(out)
    t = tones.TONES[name]
    assert r1 == r0
    assert _peak_hz(x1, r1) / _peak_hz(x0, r0) == pytest.approx(2 ** (t.semitones / 12), rel=0.02)
    assert (len(x1) / r1) == pytest.approx((len(x0) / r0) / t.tempo, rel=0.03)
    assert np.abs(x1).max() <= 0.96


@needs_ffmpeg
def test_neutral_is_a_copy(tmp_path):
    src = _tone_wav(tmp_path / "in.wav")
    out = tones.apply_tone_dsp(src, tmp_path / "o.wav", "neutral")
    assert out.read_bytes() == src.read_bytes()


def test_unknown_tone_refused(base, form, tmp_path):
    _enrolled(base, form, tmp_path)
    with pytest.raises(registry.ConsentError, match="unknown tone"):
        tones.require_tone_consent("alice", "dubstep", base)


def test_stylized_tone_needs_its_own_signed_addendum(base, form, tmp_path, addendum):
    _enrolled(base, form, tmp_path)
    tones.require_tone_consent("alice", "neutral", base)               # base consent is enough for the natural voice
    with pytest.raises(registry.ConsentError, match="stylized_versions"):
        tones.require_tone_consent("alice", "cute", base)
    with pytest.raises(registry.ConsentError):
        registry.grant_scope("alice", "stylized_versions", tmp_path / "missing.pdf", base)
    rec = registry.grant_scope("alice", "stylized_versions", addendum, base)
    assert rec["scope_grants"]["stylized_versions"]["form_sha256"]
    tones.require_tone_consent("alice", "cute", base)
    registry.revoke_scope("alice", "stylized_versions", base)          # withdraw the addendum alone
    tones.require_tone_consent("alice", "neutral", base)
    with pytest.raises(registry.ConsentError):
        tones.require_tone_consent("alice", "anime", base)


def test_changed_addendum_and_full_revoke_block_tones(base, form, tmp_path, addendum):
    _enrolled(base, form, tmp_path)
    registry.grant_scope("alice", "stylized_versions", addendum, base)
    kept = next((base / "alice" / "forms").glob("stylized_versions-*"))
    kept.write_bytes(kept.read_bytes() + b"x")
    with pytest.raises(registry.ConsentError, match="addendum"):
        tones.require_tone_consent("alice", "cute", base)
    kept.write_bytes(kept.read_bytes()[:-1])
    tones.require_tone_consent("alice", "cute", base)
    registry.revoke("alice", base)
    with pytest.raises(registry.ConsentError, match="revoked"):
        tones.require_tone_consent("alice", "neutral", base)


def test_stylized_scope_cannot_ride_on_the_base_form(base, form):
    with pytest.raises(registry.ConsentError):
        registry.record_consent("alice", "A", "employee", form, scopes=(*registry.REQUIRED_SCOPES, "stylized_versions"), base=base)
    with pytest.raises(registry.ConsentError):
        registry.grant_scope("alice", "commercial_use", form, base)


@needs_ffmpeg
def test_run_tones_writes_a_lab_set_and_refuses_without_the_scope(base, form, tmp_path, addendum):
    _enrolled(base, form, tmp_path)
    registry.record_consent("bob", "Bob", "employee", form, base=base)  # no sample needed to be refused for tones
    out = tmp_path / "tones"
    names = ["neutral", "cute", "professional50-cute50"]
    counts = tones.run_tones(out, ["alice"], ["mock"], ["en"], names, ["dsp", "model"], 1, base=base, gpu=False)
    assert counts["ok"] == 1 and counts["refused"] == 2           # only the neutral clip; both tones refused
    assert not any(p.name.startswith("mock~alice~") for p in out.iterdir())
    registry.grant_scope("alice", "stylized_versions", addendum, base)
    counts = tones.run_tones(out, ["alice"], ["mock"], ["en"], names, ["dsp", "model"], 1, base=base, gpu=False)
    assert counts["failed"] == 0 and counts["refused"] == 0
    dirs = sorted(p.name for p in out.iterdir())
    assert "mock~alice~dsp-cute" in dirs and "mock~alice~model-cute" in dirs and "mock~alice~dsp-professional50-cute50" in dirs
    assert "mock~alice~model-professional50-cute50" not in dirs   # blends are not sent to the model unless asked
    meta = json.loads((out / "mock~alice~dsp-professional50-cute50" / "meta.json").read_text())
    assert meta["clone"] and meta["consented"] and meta["kind"] == "style" and meta["style"] == "blend-professional50-cute50"
    assert meta["voice"] == "mock~alice" and meta["stylized"] and meta["tone_params"]["semitones"] > 0
    for row in (json.loads(x) for x in (out / "mock~alice~dsp-cute" / "manifest.jsonl").read_text().splitlines()):
        assert (out / row["wav"]).is_file() and row["tone"] == "cute"


@needs_ffmpeg
def test_render_tone_clip_gates_both_mechanisms(base, form, tmp_path, addendum):
    _enrolled(base, form, tmp_path)
    for mech in ("dsp", "model"):
        with pytest.raises(registry.ConsentError):
            tones.render_tone_clip("alice", "mock", "hello there", "en", "anime", mech, tmp_path / f"{mech}.wav", base, gpu=False)
    registry.grant_scope("alice", "stylized_versions", addendum, base)
    for mech in ("dsp", "model"):
        res = tones.render_tone_clip("alice", "mock", "hello there", "en", "anime", mech, tmp_path / f"{mech}.wav", base, gpu=False)
        assert res["tone"] == "anime" and (tmp_path / f"{mech}.wav").is_file()


class _Stub:
    sample_rate = 24000

    def __init__(self):
        self.calls = []

    def generate(self, **kw):
        self.calls.append(("generate", kw))
        return np.zeros(2400, dtype="float32")

    def inference_instruct2(self, *a, **kw):
        self.calls.append(("instruct2", a))
        return iter(())

    def inference_zero_shot(self, *a, **kw):
        self.calls.append(("zero_shot", a))
        return iter(())

    def inference_cross_lingual(self, *a, **kw):
        self.calls.append(("cross_lingual", a))
        return iter(())


def test_voxcpm2_style_uses_controllable_cloning(tmp_path):
    ad = VoxCPM2Adapter(reference_wav="ref.wav", reference_text="what I said", style="cute, sweet voice")
    ad._model = _Stub()
    ad._synth("hello", "en", tmp_path / "o.wav")
    kw = ad._model.calls[0][1]
    assert kw["text"] == "(cute, sweet voice)hello" and kw["reference_wav_path"] == "ref.wav"
    assert "prompt_wav_path" not in kw and "prompt_text" not in kw
    plain = VoxCPM2Adapter(reference_wav="ref.wav", reference_text="what I said")
    plain._model = _Stub()
    plain._synth("hello", "en", tmp_path / "p.wav")
    kw = plain._model.calls[0][1]
    assert kw["text"] == "hello" and kw["prompt_wav_path"] == "ref.wav" and kw["prompt_text"] == "what I said"


def test_cosyvoice2_instruct_switches_the_call():
    inst = tones.cosy_instruct(tones.TONES["cute"])
    ad = CosyVoice2Adapter(instruct=inst, prompt_text="x", prompt_lang="en")
    m = _Stub()
    ad._infer(m, "hello", "en", "PROMPT")
    assert m.calls[-1][0] == "instruct2" and m.calls[-1][1] == ("hello", inst, "PROMPT")
    plain = CosyVoice2Adapter(prompt_text="x", prompt_lang="en")
    plain._infer(m, "hello", "en", "PROMPT")
    assert m.calls[-1][0] == "zero_shot"
    plain._infer(m, "hello", "es", "PROMPT")
    assert m.calls[-1][0] == "cross_lingual"

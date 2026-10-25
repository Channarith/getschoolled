import json
import math
import wave
from pathlib import Path

import pytest

np = pytest.importorskip("numpy")

from tts_bakeoff.adapters.cosyvoice2 import CosyVoice2Adapter  # noqa: E402
from tts_bakeoff.adapters.voxcpm2 import VoxCPM2Adapter  # noqa: E402
from tts_bakeoff.voice_clone import bakeoff, clean, profile, registry  # noqa: E402

RATE = 24000
SENTENCE = "Good morning and welcome to today's lesson, we will start with something simple and then build."   # about 6 s spoken


def _wav(path: Path, secs: float, seed=1, noise=0.001):
    t = np.arange(int(secs * RATE)) / RATE
    rng = np.random.default_rng(seed)
    env = (np.sin(2 * math.pi * 2 * t) > -0.3).astype(float)
    x = 0.3 * env * np.sin(2 * math.pi * 150 * t) + noise * rng.standard_normal(len(t))
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(RATE)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())
    return path


def _speaker(tmp_path, speaker="wei", name="Wei", lang="yue", takes=None, session_secs=60):
    form = tmp_path / "form.txt"
    form.write_text("signed " * 40, encoding="utf-8")
    registry.record_consent(speaker, name, "employee", form, base=tmp_path, evidence={"consent_language": lang})
    d = registry.speaker_dir(speaker, tmp_path)
    for pid, secs in (takes or {}).items():
        _wav(d / "raw" / lang / f"{pid}.wav", secs, seed=len(pid) + int(secs))
    sess = _wav(d / "samples" / f"web-{lang}.wav", session_secs)
    registry.add_sample(speaker, sess, "joined transcript of all eight prompts", lang, tmp_path,
                        extra={"seconds": session_secs, "snr_db": 30.0, "cleaned": False})
    return d


# ---- (4) audio/text ratio and round-trip checks
def test_speech_rate_check_flags_takes_that_cannot_belong_to_their_text():
    ok = clean.speech_rate_check(SENTENCE, "en", 6.5)
    assert ok["verdict"] == "ok"
    assert clean.speech_rate_check(SENTENCE, "en", 45)["verdict"] == "too long"      # the 'audio_text_ratio=6.4' kind of take
    assert clean.speech_rate_check(SENTENCE, "en", 0.5)["verdict"] == "too short"
    assert clean.speech_rate_check("歡迎嚟上堂，今日我哋學習分數。", "yue", 4.0)["verdict"] == "ok"
    assert clean.speech_rate_check("歡迎嚟上堂，今日我哋學習分數。", "yue", 30)["verdict"] == "too long"


def _take(path, secs):
    _wav(path, secs)


class _Adapter:
    name = "fake"
    languages = {"en"}

    def __init__(self, secs_per_take):
        self.secs, self.n = list(secs_per_take), 0

    def synthesize(self, text, lang, out_wav):
        secs = self.secs[min(self.n, len(self.secs) - 1)]
        self.n += 1
        _take(Path(out_wav), secs)
        return {"duration_s": secs, "synth_s": 0.1, "sample_rate": RATE, "rtf": 0.1}


def test_best_of_prefers_a_take_that_fits_and_rejects_when_none_do(tmp_path):
    row = clean.synthesize_best_of(_Adapter([40, 6.5, 41]), SENTENCE, "en", tmp_path / "a.wav", takes=3, clean=False)
    assert row["chosen_take"] == 1 and row["rate_verdict"] == "ok" and (tmp_path / "a.wav").is_file()
    with pytest.raises(clean.TakeMismatch, match="rejected"):
        clean.synthesize_best_of(_Adapter([40, 41, 42]), SENTENCE, "en", tmp_path / "b.wav", takes=3, clean=False)
    assert not (tmp_path / "b.wav").exists() and not list((tmp_path / clean.HOLD).glob("*take*"))         # nothing written, no leftovers
    with pytest.raises(clean.TakeMismatch):
        clean.synthesize_best_of(_Adapter([40]), SENTENCE, "en", tmp_path / "c.wav", takes=1, clean=False)      # the plain single-call path too
    assert clean.synthesize_best_of(_Adapter([6.5]), SENTENCE, "en", tmp_path / "d.wav", takes=1, clean=False)["rate_verdict"] == "ok"


def test_round_trip_error_rejects_a_take_in_a_language_whisper_handles():
    x = (0.02 * np.random.default_rng(3).standard_normal(RATE * 6)).astype("float32")
    assert clean.analyze(x, RATE, wer=0.9, text=SENTENCE, lang="en")["mismatch"] is True
    assert clean.analyze(x, RATE, wer=0.9, text="ខ្ញុំស្រឡាញ់អ្នក" * 3, lang="km")["mismatch"] is False      # km: ASR too weak to veto
    assert clean.analyze(x, RATE, wer=0.1, text=SENTENCE, lang="en")["mismatch"] is False


# ---- (3) VoxCPM2 reference mode
class _FakeModel:
    def __init__(self):
        self.calls = []

    def generate(self, **kw):
        self.calls.append(kw)
        return np.zeros(RATE, dtype="float32")


def _vox(tmp_path, **options):
    a = VoxCPM2Adapter(reference_wav=str(tmp_path / "ref.wav"), reference_text="exact words", **options)
    a._model = _FakeModel()
    return a


def test_voxcpm2_continue_uses_the_transcript_and_reference_mode_does_not(tmp_path, capsys):
    a = _vox(tmp_path, ref_mode="continue")
    info = a.synthesize("hello", "en", tmp_path / "o.wav")
    kw = a._model.calls[0]
    assert kw["prompt_wav_path"].endswith("ref.wav") and kw["prompt_text"] == "exact words" and "reference_wav_path" not in kw
    assert info["ref_mode"] == "continue" and "ref-mode=continue" in capsys.readouterr().out
    b = _vox(tmp_path, ref_mode="reference")
    info = b.synthesize("hello", "en", tmp_path / "o2.wav")
    kw = b._model.calls[0]
    assert kw["reference_wav_path"].endswith("ref.wav") and "prompt_text" not in kw and "prompt_wav_path" not in kw and info["ref_mode"] == "reference"
    c = _vox(tmp_path, style="cute, bright")
    assert c.synthesize("hello", "en", tmp_path / "o3.wav")["ref_mode"] == "reference" and c._model.calls[0]["text"] == "(cute, bright)hello"
    assert _vox(tmp_path).synthesize("hi", "en", tmp_path / "o4.wav")["ref_mode"] == "continue"            # legacy default unchanged
    with pytest.raises(ValueError):
        _vox(tmp_path, ref_mode="bogus").synthesize("hi", "en", tmp_path / "o5.wav")


def test_decide_ref_mode_continues_only_for_same_language_exact_short_references():
    mk = lambda **k: profile.Reference(Path("r.wav"), "t", k.pop("lang", "yue"), "r", "same-language", 30, False, k.pop("seconds", 11), k.pop("role", "reference"), k.pop("exact", True))  # noqa: E731
    assert profile.decide_ref_mode(mk(), "yue") == "continue"
    assert profile.decide_ref_mode(mk(), "en") == "reference"                     # another language: audio only
    assert profile.decide_ref_mode(mk(exact=False, role="session", seconds=60), "yue") == "reference"   # long concatenation, transcript not known exact
    assert profile.decide_ref_mode(mk(seconds=40), "yue") == "reference"          # too long to be an utterance
    assert profile.decide_ref_mode(mk(), "yue", "reference") == "reference" and profile.decide_ref_mode(mk(exact=False), "yue", "continue") == "continue"


def test_profile_adapter_sets_the_mode_per_sentence_and_the_flag_reaches_build_adapter(tmp_path, monkeypatch):
    from tts_bakeoff.voice_clone import synth

    d = _speaker(tmp_path, takes={"yue-1": 11})
    profile.build_reference("wei", "yue", tmp_path)
    inner = VoxCPM2Adapter()
    inner._model = _FakeModel()
    ad = profile.ProfileAdapter(inner, "wei", tmp_path)
    ad.synthesize("你好", "yue", tmp_path / "a.wav")
    ad.synthesize("hello", "en", tmp_path / "b.wav")
    assert inner._model.calls[0].get("prompt_text") and "reference_wav_path" in inner._model.calls[1] and "prompt_text" not in inner._model.calls[1]
    assert ad.last_reference.role == "reference" and d.is_dir()
    monkeypatch.setenv("GS_CLONE_REF_MODE", "reference")
    assert synth.build_adapter("mock", "wei", tmp_path, gpu=False).ref_mode == "reference"
    assert synth.build_adapter("mock", "wei", tmp_path, gpu=False, ref_mode="continue").ref_mode == "continue"
    with pytest.raises(ValueError):
        profile.ProfileAdapter(inner, "wei", tmp_path, ref_mode="nope")


def test_bakeoff_ref_mode_flag_sets_the_environment(tmp_path, monkeypatch):
    monkeypatch.delenv("GS_CLONE_REF_MODE", raising=False)
    monkeypatch.setenv("GS_VOICES_DIR", str(tmp_path))
    _speaker(tmp_path)
    bakeoff.main(["run", "--out", str(tmp_path / "o"), "--speakers", "wei", "--models", "mock", "--langs", "en", "--limit", "1", "--no-gpu",
                  "--ref-mode", "reference"])
    import os

    assert os.environ["GS_CLONE_REF_MODE"] == "reference"
    monkeypatch.delenv("GS_CLONE_REF_MODE", raising=False)


# ---- (1)+(2) one short exact-transcript reference per language
def test_reference_is_one_clean_utterance_with_its_exact_prompt_text(tmp_path):
    from tts_bakeoff.voice_clone.enroll_ui.prompts import PROMPT_SETS

    d = _speaker(tmp_path, takes={"yue-1": 3, "yue-2": 25, "yue-3": 11, "yue-4": 7})
    dry = profile.build_reference("wei", "yue", tmp_path, dry_run=True)
    assert dry["take"] == "yue-3" and dry["written"] is False and not (d / "samples" / "ref-yue.wav").exists()
    assert any("yue-1: too short" in r for r in dry["rejected"]) and any("yue-2: too long" in r for r in dry["rejected"])
    res = profile.build_reference("wei", "yue", tmp_path)
    info = registry.load_consent("wei", tmp_path)["samples"]["samples/ref-yue.wav"]
    assert res["written"] and info["role"] == "reference" and info["transcript_exact"] is True and info["source_take"] == "yue-3"
    assert info["transcript"] == PROMPT_SETS["yue"][2]["text"] and 8 <= info["seconds"] <= 14 and info["lang"] == "yue"
    ref = profile.choose_reference("wei", "yue", tmp_path)
    assert ref.rel == "samples/ref-yue.wav" and ref.role == "reference" and ref.exact           # beats the 60 s session recording
    assert profile.choose_reference("wei", "en", tmp_path).rel == "samples/ref-yue.wav"        # cross-lingual still picks the short reference
    again = profile.build_reference("wei", "yue", tmp_path)                                    # re-running replaces it, no duplicate
    assert again["written"] and list(registry.load_consent("wei", tmp_path)["samples"]).count("samples/ref-yue.wav") == 1


def test_reference_clips_do_not_inflate_the_fine_tune_minutes_or_the_language_list(tmp_path):
    _speaker(tmp_path, takes={"yue-3": 11})
    before = profile.readiness("wei", "voxcpm2", tmp_path)["languages"]["yue"]["clean_minutes"]
    profile.build_reference("wei", "yue", tmp_path)
    after = profile.readiness("wei", "voxcpm2", tmp_path)
    assert after["languages"]["yue"]["clean_minutes"] == before == 1.0 and after["languages"]["yue"]["samples"] == 1
    assert profile.speaker_languages("wei", tmp_path) == ["yue"]


def test_no_usable_take_says_why_and_needs_consent(tmp_path):
    _speaker(tmp_path, takes={"yue-1": 2})
    res = profile.build_reference("wei", "yue", tmp_path)
    assert res["written"] is False and "no usable take" in res["reason"] and any("too short" in r for r in res["rejected"])
    assert profile.build_references("wei", tmp_path)[0]["lang"] == "yue"
    registry.revoke("wei", tmp_path)
    with pytest.raises(registry.ConsentError):
        profile.build_reference("wei", "yue", tmp_path)


# ---- CosyVoice 2: the weights path that made the run fail from another folder
def test_cosyvoice_model_dir_is_absolute_and_check_reports_missing_weights(tmp_path, monkeypatch):
    for k in ("COSYVOICE_MODEL_DIR", "COSYVOICE_REPO", "COSYVOICE_URL"):
        monkeypatch.delenv(k, raising=False)
    assert Path(CosyVoice2Adapter().model_dir()).is_absolute() and CosyVoice2Adapter().model_dir().endswith("pretrained_models/CosyVoice2-0.5B")
    monkeypatch.setenv("COSYVOICE_REPO", str(tmp_path / "repo"))
    assert CosyVoice2Adapter().model_dir() == str(tmp_path / "repo" / "pretrained_models" / "CosyVoice2-0.5B")
    monkeypatch.setenv("COSYVOICE_MODEL_DIR", "/x/y")
    assert CosyVoice2Adapter().model_dir() == "/x/y" and CosyVoice2Adapter(model_dir="/z").model_dir() == "/z"
    monkeypatch.setenv("COSYVOICE_MODEL_DIR", str(tmp_path / "missing"))
    assert any("model weights not found" in p for p in CosyVoice2Adapter().check()["problems"])


def test_doctor_names_what_is_missing_and_the_fix(tmp_path, monkeypatch):
    from tts_bakeoff.voice_clone import doctor

    monkeypatch.setenv("COSYVOICE_REPO", str(tmp_path / "nope"))
    monkeypatch.delenv("COSYVOICE_MODEL_DIR", raising=False)
    r = doctor.diagnose("cosyvoice2")
    assert r["ok"] is False and any("repo not found" in p for p in r["problems"]) and any("git clone --recursive" in f for f in r["fixes"])
    assert any("does not list Cantonese" in n for n in r["notes"])
    assert doctor.main(["--model", "cosyvoice2"]) == 1
    script = Path(__file__).resolve().parents[2] / "scripts" / "run_voice_clone.sh"
    assert "COSYVOICE_MODEL_DIR" in script.read_text(encoding="utf-8")


def test_split_text_and_chunk_limit_follow_the_8gb_card():
    from tts_bakeoff.adapters.voxcpm2 import chunk_limit, split_text

    assert split_text("Stop.", 80) == ["Stop."] and split_text("Stop.", 0) == ["Stop."]
    parts = split_text("One sentence here. Another sentence follows after it.", 24)
    assert len(parts) >= 2 and all(len(part) <= 24 for part in parts)
    assert chunk_limit({}, total_bytes=8 * 1024**3) == 80
    assert chunk_limit({}, total_bytes=80 * 1024**3) == 0
    assert chunk_limit({"chunk_chars": 40}, total_bytes=8 * 1024**3) == 40


def test_oom_retries_a_paragraph_in_pieces(tmp_path):
    calls = []

    class M:
        def generate(self, **kw):
            calls.append(kw["text"])
            if len(kw["text"]) > 80:
                raise RuntimeError("CUDA out of memory. Tried to allocate 156.00 MiB")
            return np.ones(100, dtype="float32")

    text = ("If safe, move out of traffic and turn on hazards. "
            "Call 911 for injuries. Exchange names, contact, license, and insurance info.")
    ad = VoxCPM2Adapter(reference_wav=str(tmp_path / "ref.wav"), ref_mode="reference", chunk_chars=0)
    ad._model = M()
    ad.synthesize(text, "en", tmp_path / "o.wav")
    assert calls[0] == text
    assert all(len(piece) <= 80 for piece in calls[1:]) and len(calls) > 1
    assert (tmp_path / "o.wav").stat().st_size > 500


def test_tight_gpu_speaks_a_long_line_in_short_pieces(tmp_path, monkeypatch):
    from tts_bakeoff.adapters import voxcpm2 as vx

    monkeypatch.setattr(vx, "_cuda_total_bytes", lambda: 8 * 1024**3)
    calls = []

    class M:
        def generate(self, **kw):
            calls.append(kw["text"])
            assert len(kw["text"]) <= 80
            return np.ones(80, dtype="float32")

    text = "A" * 200
    ad = VoxCPM2Adapter(reference_wav="ref.wav", ref_mode="reference")
    ad._model = M()
    ad.synthesize(text, "en", tmp_path / "o.wav")
    assert "".join(calls) == text and len(calls) == 3

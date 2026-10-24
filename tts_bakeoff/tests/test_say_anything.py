"""'Say anything' panel: consent gating, validation, dedupe, queue state, AI-generated labelling. The synthesizer is a stub."""
from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.error
import urllib.request

import pytest

from tts_bakeoff.voice_clone import bakeoff, registry
from tts_bakeoff.voice_clone import enroll_ui as ui
from tts_bakeoff.tests.test_enroll_ui import call, enrolled, record_all, server  # noqa: F401  (fixture re-export)

STUB = """
import pathlib, sys, time, wave
wav = pathlib.Path(sys.argv[1]); delay = float(sys.argv[2]); wait_file = sys.argv[3]
if wait_file != "-":
    time.sleep(delay)
wav.with_suffix(".running").touch()
time.sleep(delay)
with wave.open(str(wav), "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(b"\\x01\\x00" * 2400)
wav.with_suffix(".running").unlink()
"""


@pytest.fixture
def gpu(monkeypatch):
    """A CUDA host whose synthesizer is a stub that writes a tiny WAV; returns the list of launched commands."""
    monkeypatch.setattr(ui, "cuda_host", lambda: True)
    monkeypatch.setattr(ui, "_SAY", {})
    launched = []

    def launch(argv, env, log):
        launched.append(argv)
        return subprocess.Popen([sys.executable, "-c", STUB, argv[5], "0.0", "-"])
    monkeypatch.setattr(ui, "_launch", launch)
    return launched


def ready(server):  # noqa: F811
    url, _ = server
    speaker = enrolled(server)
    record_all(url, speaker)
    code, r = call(url, f"/api/enroll/{speaker}", {"lang": "en"})
    assert code == 200 and r["ok"], r
    return url, speaker


def wait_state(url, job_id, want, secs=15):
    end = time.time() + secs
    while time.time() < end:
        _, r = call(url, "/api/say")
        job = next(j for j in r["jobs"] if j["id"] == job_id)
        if job["state"] == want:
            return job
        time.sleep(0.1)
    raise AssertionError(f"job stayed {job['state']!r}, wanted {want!r}")


def say(url, speaker, **over):
    body = {"model": "voxcpm2", "lang": "en", "text": "Hello from the test."}
    body.update(over)
    return call(url, f"/api/say/{speaker}", body)


def test_unknown_and_revoked_speakers_are_refused(server, gpu):  # noqa: F811
    url, speaker = ready(server)
    assert say(url, "nobody")[0] == 403
    assert call(url, f"/api/revoke/{speaker}", {"typed_name": "Alice Tran"})[0] == 200
    code, r = say(url, speaker)
    assert code == 403 and "revoked" in r["error"].lower()
    assert gpu == []


def test_needs_a_sample(server, gpu):  # noqa: F811
    url, _ = server
    speaker = enrolled(server)
    code, r = say(url, speaker)
    assert code == 400 and "sample" in r["error"]


@pytest.mark.parametrize("over,needle", [({"text": "x" * 501}, "500"), ({"text": "   "}, "type the words"),
                                         ({"model": "edge_tts"}, "model must be"), ({"model": "cosyvoice2", "lang": "vi"}, "does not speak")])
def test_validation(server, gpu, over, needle):  # noqa: F811
    url, speaker = ready(server)
    code, r = say(url, speaker, **over)
    assert code == 400 and needle in r["error"]
    assert gpu == []


def test_text_at_the_limit_is_accepted(server, gpu):  # noqa: F811
    url, speaker = ready(server)
    assert say(url, speaker, text="y" * 500)[0] == 200


def test_without_cuda_shows_the_command(server, monkeypatch):  # noqa: F811
    url, speaker = ready(server)
    monkeypatch.setattr(ui, "_SAY", {})
    code, r = say(url, speaker, text="it's a test")
    assert code == 200 and r["started"] is False
    assert "run_voice_say.sh voxcpm2" in r["command"] and "it'" in r["command"] and "CUDA" in r["reason"]


def test_state_progression_and_audio(server, gpu, monkeypatch):  # noqa: F811
    def slow(argv, env, log):
        return subprocess.Popen([sys.executable, "-c", STUB, argv[5], "1.0", "queued"])
    monkeypatch.setattr(ui, "_launch", slow)
    url, speaker = ready(server)
    code, r = say(url, speaker)
    assert code == 200 and r["started"] is True and r["state"] == "waiting for GPU lock"
    job_id = r["id"]
    wait_state(url, job_id, "running")
    done = wait_state(url, job_id, "done")
    assert done["label"] == "AI-generated voice of Alice Tran" and done["audio"].endswith(f"{job_id}.wav")
    req = urllib.request.Request(url + done["audio"], headers={"X-Enroll": "1"})
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200 and resp.headers["Content-Type"] == "audio/wav" and resp.headers["X-AI-Generated"] == "true"
        assert resp.read()[:4] == b"RIFF"


def test_second_clip_for_same_speaker_and_model_is_refused(server, gpu, monkeypatch):  # noqa: F811
    monkeypatch.setattr(ui, "_launch", lambda argv, env, log: subprocess.Popen([sys.executable, "-c", STUB, argv[5], "1.5", "queued"]))
    url, speaker = ready(server)
    first = say(url, speaker)[1]
    code, r = say(url, speaker, text="another")
    assert code == 409 and "already" in r["error"]
    assert say(url, speaker, model="cosyvoice2")[0] == 200   # another model is a different job
    wait_state(url, first["id"], "done", 20)
    assert say(url, speaker, text="after the first finished")[0] == 200


def test_withdrawn_consent_stops_playback(server, gpu):  # noqa: F811
    url, speaker = ready(server)
    job_id = say(url, speaker)[1]["id"]
    done = wait_state(url, job_id, "done")
    assert call(url, f"/api/revoke/{speaker}", {"typed_name": "Alice Tran"})[0] == 200
    req = urllib.request.Request(url + done["audio"], headers={"X-Enroll": "1"})
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(req)
    assert e.value.code == 403
    _, r = call(url, "/api/say")
    assert r["jobs"][0]["state"] == "withdrawn" and "audio" not in r["jobs"][0]


def test_cli_say_writes_an_ai_generated_sidecar(tmp_path, monkeypatch):
    base = tmp_path / "voices"
    monkeypatch.setenv("GS_VOICES_DIR", str(base))
    form = tmp_path / "form.txt"
    form.write_text("signed consent form " * 20)
    registry.record_consent("alice", "Alice Tran", "employee", form, base=base)
    wav = registry.speaker_dir("alice", base) / "samples" / "ref.wav"
    wav.parent.mkdir(parents=True, exist_ok=True)
    import wave
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(b"\x01\x00" * 24000)
    registry.add_sample("alice", wav, "a reference transcript", "en", base)
    out = tmp_path / "say" / "one.wav"
    meta = bakeoff.say_once("alice", "mock", "en", "  hello   there ", out, base, gpu=False)
    side = json.loads(out.with_suffix(".json").read_text())
    assert side["ai_generated"] is True and side["label"] == "AI-generated voice of Alice Tran"
    assert side["text"] == "hello there" and meta["speaker"] == "alice"
    assert out.is_file() and not out.with_suffix(".running").exists()
    registry.revoke("alice", base)
    with pytest.raises(registry.ConsentError):
        bakeoff.say_once("alice", "mock", "en", "hello", tmp_path / "two.wav", base, gpu=False)

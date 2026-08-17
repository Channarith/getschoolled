"""Regression tests for the 2026-08-17 audit (shared vision/presence/TTS).

- MED-9   FaceGallery rejected mismatched embedding dimensions (a short
          embedding poisoned the prototype and made identify() raise IndexError).
- HIGH-3  The consent set was stored on the provider singleton; concurrent
          requests could swap each other's consent. It is now threaded through.
- HIGH-2  WebcamPresenceTracker.on_return could never fire at any
          return_threshold_s > 0.
- LOW-14  PresenceTracker confirmed ABSENT one away_grace window too early.
- MED-10  Model downloads/gallery saves used fixed temp names (clobbering).
- MED-7   elevenlabs_tts escaped its ElevenLabsError contract on read timeouts.
"""

import time

import pytest


# MED-9 -------------------------------------------------------------------- #

def test_gallery_rejects_mismatched_embedding_dimension():
    from aoep_shared.vision.gallery import FaceGallery

    g = FaceGallery()
    g.enroll("alice", [0.1] * 128)
    with pytest.raises(ValueError, match="dimension"):
        g.enroll("alice", [0.5, 0.5, 0.5])
    # identify still works after the rejected enroll.
    m = g.identify([0.1] * 128)
    assert m.matched and m.student_id == "alice"


def test_gallery_identify_fails_fast_on_query_dim_mismatch():
    from aoep_shared.vision.gallery import FaceGallery

    g = FaceGallery()
    g.enroll("alice", [0.1] * 128)
    with pytest.raises(ValueError, match="dimension"):
        g.identify([0.1] * 64)


def test_gallery_from_dict_self_heals_poisoned_data():
    from aoep_shared.vision.gallery import FaceGallery

    poisoned = {
        "match_threshold": 0.5,
        "embeddings": {"alice": [[0.1] * 128, [0.5, 0.5, 0.5]]},
    }
    g = FaceGallery.from_dict(poisoned)
    m = g.identify([0.1] * 128)
    assert m.matched and m.student_id == "alice"


# HIGH-3 ------------------------------------------------------------------- #

def test_consent_gate_is_per_request_not_singleton_state():
    from aoep_shared.config import AppConfig, DeployMode
    from aoep_shared.providers.base import EmbeddedFace
    from aoep_shared.providers.vision import LocalVisionProvider

    prov = LocalVisionProvider(AppConfig(deploy_mode=DeployMode.LOCAL, region="us"))
    # Orthogonal embeddings so only the true match clears the cosine threshold.
    prov.gallery().enroll("alice", [1.0, 0.0, 0.0])
    prov.gallery().enroll("bob", [0.0, 1.0, 0.0])

    face = EmbeddedFace(embedding=[0.0, 1.0, 0.0], landmarks=[], bbox=None, frame_size=None)
    # Request A consents only alice; request B consents only bob. Running A
    # after B must not match bob — the consent set is threaded, not shared.
    prov.analyze_embedding([face], consented_student_ids=["bob"])
    obs_a = prov.analyze_embedding([face], consented_student_ids=["alice"])
    assert obs_a[0].matched_student_id is None
    obs_b = prov.analyze_embedding([face], consented_student_ids=["bob"])
    assert obs_b[0].matched_student_id == "bob"
    # No per-request state may linger on the provider.
    assert not hasattr(prov, "_consented")


# HIGH-2 ------------------------------------------------------------------- #

def test_on_return_fires_at_default_threshold():
    from aoep_shared.vision.webcam_presence import WebcamPresenceTracker

    returned = []
    t = WebcamPresenceTracker(
        absence_threshold_s=0.05,
        return_threshold_s=0.10,  # the production default is 1.0 (> 0)
        on_return=lambda m: returned.append(m.return_events),
    )
    t.update(face_count=1, silhouette_confidence=0.0)
    time.sleep(0.08)  # long enough to confirm ABSENT
    t.update(face_count=0, silhouette_confidence=0.0)
    assert t.state.value == "absent"
    time.sleep(0.12)  # absence now longer than return_threshold_s
    t.update(face_count=1, silhouette_confidence=0.0)
    assert returned, "on_return never fired (the pre-fix behavior)"
    assert t.metrics.return_events == 1


def test_on_return_skipped_for_brief_absence_blip():
    from aoep_shared.vision.webcam_presence import WebcamPresenceTracker

    returned = []
    t = WebcamPresenceTracker(
        absence_threshold_s=0.05,
        return_threshold_s=60.0,  # only long absences earn a welcome-back
        on_return=lambda m: returned.append(m.return_events),
    )
    t.update(face_count=1, silhouette_confidence=0.0)
    time.sleep(0.08)
    t.update(face_count=0, silhouette_confidence=0.0)
    assert t.state.value == "absent"
    t.update(face_count=1, silhouette_confidence=0.0)  # brief blip -> no event
    assert not returned
    assert t.state.value == "present_face"


# LOW-14 ------------------------------------------------------------------- #

def test_absent_confirmed_after_time_in_away_not_after_last_presence():
    from aoep_shared.presence import PresenceFrame, PresenceState, PresenceTracker

    t = PresenceTracker("p1", away_grace_s=10.0, absent_confirm_s=30.0)
    t0 = time.monotonic()
    t.push(PresenceFrame(face_present=True, silhouette_present=False, timestamp=t0))
    # 10s later: enters AWAY (grace elapsed).
    s = t.push(PresenceFrame(face_present=False, silhouette_present=False, timestamp=t0 + 10.0))
    assert s.state == PresenceState.AWAY
    # 35s after last presence: old code confirmed ABSENT (30s after presence);
    # the documented behavior is 30s in AWAY -> ABSENT at t0+40.
    s = t.push(PresenceFrame(face_present=False, silhouette_present=False, timestamp=t0 + 35.0))
    assert s.state == PresenceState.AWAY
    s = t.push(PresenceFrame(face_present=False, silhouette_present=False, timestamp=t0 + 40.0))
    assert s.state == PresenceState.ABSENT


# MED-10 ------------------------------------------------------------------- #

def test_model_download_cleans_temp_file_on_failure(tmp_path, monkeypatch):
    import urllib.request

    from aoep_shared.vision import models

    def boom(url, dest):
        raise OSError("simulated network failure")

    monkeypatch.setattr(urllib.request, "urlretrieve", boom)
    dest = str(tmp_path / "model.onnx")
    with pytest.raises(OSError):
        models._download("https://example.invalid/x", dest)
    # No .part temp file may be left behind.
    assert list(tmp_path.iterdir()) == []


def test_gallery_save_uses_unique_temp_files(tmp_path):
    from aoep_shared.vision.gallery import FaceGallery

    g = FaceGallery()
    g.enroll("alice", [0.1, 0.2])
    path = str(tmp_path / "gallery.json")
    g.save_json(path)
    g.save_json(path)  # second save must not trip over a stale temp file
    loaded = FaceGallery.load_json(path)
    assert loaded.count("alice") == 1


# Segfault guard (found during the audit) ----------------------------------- #

_TINY_JPEG = bytes.fromhex(
    "ffd8ffe000104a46494600010100000100010000ffdb004300030202030202030303"
    "0304030304050805050404050a070706080c0a0c0c0b0a0b0b0d0e12100d0e110e0b"
    "0b1016101113141515150c0f171816141812141514ffdb0043010304040504050905"
    "0509140d0b0d14141414141414141414141414141414141414141414141414141414"
    "141414141414141414141414141414141414141414141414ffc00011080001000103"
    "012200021101031101ffc40014000100000000000000000000000000000000000000"
    "08ffc4001410010000000000000000000000000000000000000000ffc40014010100"
    "00000000000000000000000000000000000008ffc400141101000000000000000000"
    "00000000000000000000ffda000c03010002110311003f00b2c001ffd9"
)


def test_tiny_frame_does_not_crash_silhouette_detector():
    """A 1x1/corrupt frame used to segfault OpenCV HOG (window 64x128 > frame),
    killing the whole webcam process. Now it returns a normal result."""
    pytest.importorskip("cv2")
    from aoep_shared.silhouette import SilhouetteDetector

    d = SilhouetteDetector()
    result = d.analyze(_TINY_JPEG)
    assert result.present in (True, False)  # any answer, as long as we survive


def test_wide_short_frame_does_not_crash_silhouette_signals():
    """The second HOG call site (vision/silhouette_signals.py) only upscaled on
    the larger dimension, so a 240x80 frame (height < 128 window) segfaulted."""
    pytest.importorskip("cv2")
    import numpy as np

    from aoep_shared.vision.silhouette_signals import detect_silhouette

    for h, w in ((80, 240), (60, 200), (1, 1)):
        frame = np.zeros((h, w, 3), dtype=np.uint8)
        sig = detect_silhouette(frame, prefer_hog=True)
        assert sig.present in (True, False)


# AbsenceTracker dead silhouette arm (audit 2026-08-17) ---------------------- #

def test_low_attention_with_silhouette_takes_silhouette_path():
    from aoep_shared.vision.absence import (
        PRESENCE_SILHOUETTE,
        AbsenceTracker,
        FramePresenceInput,
    )
    from aoep_shared.vision.silhouette_signals import SilhouetteSignals

    tracker = AbsenceTracker("p1")
    sil = SilhouetteSignals(person_count=1, present=True, confidence=0.9, observations=[])
    decision = tracker.update(
        FramePresenceInput(face_count=1, attention=0.0, silhouette=sil, liveness_ok=True)
    )
    assert decision.state == PRESENCE_SILHOUETTE
    assert decision.reason == "low_attention"


# xAI voice client (audit 2026-08-17) ---------------------------------------- #

def test_xai_voice_client_audio_model_default_and_disable():
    from aoep_shared.xai_voice import XAIVoiceClient

    # Default construction enables the documented default audio model.
    assert XAIVoiceClient(api_key="k")._audio_model == "grok-2-audio"
    # Explicit empty string disables audio.
    assert XAIVoiceClient(api_key="k", audio_model="")._audio_model == ""


def test_xai_audio_response_reads_transcript(monkeypatch):
    from aoep_shared import xai_voice

    body = {
        "choices": [{"message": {"content": None, "audio": {
            "data": "QUJD", "transcript": "Hello student",
        }}, "finish_reason": "stop"}],
        "model": "grok-2-audio",
        "usage": {},
    }

    class _Resp:
        def read(self):
            import json as _json
            return _json.dumps(body).encode()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(xai_voice.urllib.request, "urlopen", lambda *a, **k: _Resp())
    client = xai_voice.XAIVoiceClient(api_key="sk-test")
    resp = client.chat(
        [xai_voice.ConversationMessage(role="user", content="hi")], audio=True
    )
    assert resp.text == "Hello student"
    assert resp.has_audio


def test_absence_prompt_does_not_evict_real_history():
    from aoep_shared import xai_grok_voice

    agent = xai_grok_voice.GrokVoiceAgent(api_key="sk-test", max_history=2)
    agent._history = [
        xai_grok_voice.GrokMessage(role="user", content="q0"),
        xai_grok_voice.GrokMessage(role="assistant", content="a0"),
        xai_grok_voice.GrokMessage(role="user", content="q1"),
        xai_grok_voice.GrokMessage(role="assistant", content="a1"),
    ]

    def fake_call(messages, *, model):
        agent._history.append(xai_grok_voice.GrokMessage(role="user", content="abs"))
        agent._history.append(xai_grok_voice.GrokMessage(role="assistant", content="prompt"))
        if len(agent._history) > agent._max_history * 2:
            agent._history = agent._history[-(agent._max_history * 2):]
        return xai_grok_voice.GrokResponse(
            text="come back", model="m",
            usage_prompt_tokens=0, usage_completion_tokens=0, latency_ms=0.0,
        )

    agent._call = fake_call  # type: ignore[assignment]
    agent.generate_absence_prompt(12.0)
    contents = [m.content for m in agent._history]
    assert contents == ["q0", "a0", "q1", "a1"], contents


# PresenceTracker PARTIAL spam (audit 2026-08-17) ---------------------------- #

def test_partial_event_fires_once_not_per_frame():
    from aoep_shared.presence import PresenceEvent, PresenceTracker

    events = []
    t = PresenceTracker("p1", on_event=lambda s: events.append(s.event))
    for _ in range(5):
        t.push(__import__("aoep_shared.presence", fromlist=["PresenceFrame"]).PresenceFrame(
            face_present=False, silhouette_present=True))
    partials = [e for e in events if e == PresenceEvent.PARTIAL]
    assert len(partials) == 1, f"PARTIAL fired {len(partials)} times for 5 frames"


# Warm-up age-out on undecodable frames (audit 2026-08-17) ------------------- #

def test_undecodable_frames_age_out_of_warmup():
    cv2 = pytest.importorskip("cv2")
    from aoep_shared.vision.silhouette import SilhouetteDetector

    d = SilhouetteDetector()
    for _ in range(20):
        d.process_frame(b"not a real image")
    assert d._frames_seen >= 20, "undecodable frames never aged the warm-up counter"


# Ephemeral-token error hygiene (audit 2026-08-17) --------------------------- #

def test_ephemeral_token_errors_do_not_embed_response_body(monkeypatch):
    from aoep_shared import xai_realtime

    monkeypatch.setattr(xai_realtime, "_http_post", lambda *a, **k: b'{"secret_token_value": "xai-abc123"}')
    with pytest.raises(xai_realtime.XaiVoiceError) as exc:
        xai_realtime.mint_ephemeral_token(api_key="sk-test")
    assert "xai-abc123" not in str(exc.value)
    assert "secret_token_value" not in str(exc.value)


# MED-7 -------------------------------------------------------------------- #

def test_elevenlabs_http_post_wraps_read_timeouts(monkeypatch):
    import urllib.request

    from aoep_shared import elevenlabs_tts

    def timeout(*a, **k):
        raise TimeoutError("read timed out")

    monkeypatch.setattr(urllib.request, "urlopen", timeout)
    with pytest.raises(elevenlabs_tts.ElevenLabsError):
        elevenlabs_tts._http_post("https://api.elevenlabs.io/x", data=b"{}", headers={}, timeout=1)

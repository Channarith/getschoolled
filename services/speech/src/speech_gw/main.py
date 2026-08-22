"""Speech gateway FastAPI app.

Exposes language coverage and the TTS engine-routing decision (native XTTS vs
cloud-TTS fallback). Actual ASR/MT/TTS inference is delegated to the
SpeechProvider, which requires loaded models and is therefore not exercised by
the offline tests.
"""

from __future__ import annotations

import os

from aoep_shared.env_bootstrap import ensure_lab_env
from aoep_shared.languages import SUPPORTED_LANGUAGES
from aoep_shared.live_audio_agents import install_live_audio_routes
from aoep_shared.service import create_service
from aoep_shared.translation import is_pair_supported, plan_delivery
from fastapi import HTTPException, Response
from pydantic import BaseModel

# Load config/local.env (+ .env.local) so XAI_API_KEY / ELEVENLABS_API_KEY
# are present when the gateway is started without scripts/run_local_service.sh.
ensure_lab_env()

app = create_service("speech")
install_live_audio_routes(app, lab_name="Salareen classroom")


class LanguagesResponse(BaseModel):
    languages: list[str]
    count: int


class TtsEngineResponse(BaseModel):
    language: str
    engine: str


@app.get("/languages", response_model=LanguagesResponse)
def languages() -> LanguagesResponse:
    return LanguagesResponse(
        languages=list(SUPPORTED_LANGUAGES), count=len(SUPPORTED_LANGUAGES)
    )


@app.get("/tts/engine", response_model=TtsEngineResponse)
def tts_engine(language: str) -> TtsEngineResponse:
    try:
        provider = app.state.factory.speech()
        return TtsEngineResponse(language=language, engine=provider.tts_engine(language))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"speech provider unavailable: {exc}")


def _active_tts_engine() -> str:
    """Which neural engine will render narration audio right now."""
    from aoep_shared import cosyvoice_tts, elevenlabs_tts
    from aoep_shared.meeting.natural_tts import _edge_tts_available

    if cosyvoice_tts.cosyvoice_configured(getattr(app.state.config, "cosyvoice_url", "")):
        return "cosyvoice"
    if elevenlabs_tts.elevenlabs_configured(app.state.config.elevenlabs_api_key):
        return "elevenlabs"
    if _edge_tts_available():
        return "edge-tts"
    return "none"


class TtsStatusResponse(BaseModel):
    available: bool
    engine: str
    # Per-engine availability + a human hint, so "why is narration robotic?" is
    # answerable without guesswork. Robotic audio == no neural engine here, so the
    # client used the on-device (browser) voice.
    engines: dict = {}
    hint: str = ""


@app.get("/tts/status", response_model=TtsStatusResponse)
def tts_status() -> TtsStatusResponse:
    """Let web/mobile clients decide whether to fetch neural audio or fall back
    to on-device speech synthesis (avoids a wasted round-trip per narration).

    Also reports which neural engines are configured so operators can see why
    narration sounds robotic (= no neural engine, so the client used the
    on-device voice)."""
    from aoep_shared import cosyvoice_tts, elevenlabs_tts
    from aoep_shared.meeting.natural_tts import _edge_tts_available

    cfg = app.state.config
    engines = {
        "cosyvoice": cosyvoice_tts.cosyvoice_configured(getattr(cfg, "cosyvoice_url", "")),
        "elevenlabs": elevenlabs_tts.elevenlabs_configured(cfg.elevenlabs_api_key),
        "edge_tts": _edge_tts_available(),
    }
    engine = _active_tts_engine()
    if engine != "none":
        hint = (
            f"Neural TTS active via {engine}. If audio is still robotic, the client "
            "may be on its on-device fallback — check the browser Network tab for a "
            "successful POST /tts (200, X-TTS-Engine header)."
        )
    else:
        hint = (
            "No neural TTS engine is available, so clients fall back to the robotic "
            "on-device voice. Enable one: install edge-tts (free; already pinned in "
            "the speech image's requirements — redeploy) and allow egress to the "
            "edge-tts endpoint, and/or set ELEVENLABS_API_KEY (most natural)."
        )
    return TtsStatusResponse(available=engine != "none", engine=engine, engines=engines, hint=hint)


class TtsRequest(BaseModel):
    text: str
    language: str = "en"
    voice_style: str = "standard"
    voice: str = ""          # voice_catalog id (accent/language), e.g. "en_gb_f"
    instructor: str = ""     # instructor personality id, e.g. "kind" / "strict"
    slang: bool = True       # apply the voice's regional dialect/slang to the text


@app.get("/tts/voices")
def tts_voices() -> dict:
    """The catalog of narration voices (accents/languages) for a UI picker."""
    from aoep_shared.voice_catalog import catalog_grouped

    return {"groups": catalog_grouped()}


@app.get("/tts/instructors")
def tts_instructors() -> dict:
    """The catalog of instructor personalities (kind/strict/child/cartoon/…)."""
    from aoep_shared.instructors import list_instructors

    return {"instructors": list_instructors()}


@app.get("/tts")
def tts_get(text: str, language: str = "en", voice_style: str = "standard",
            voice: str = "", instructor: str = "", slang: bool = True) -> Response:
    """GET variant so mobile (expo-av) can load audio directly from a URI.

    NOTE: passing lesson text as a URL query parameter exposes it in server
    logs. This is a known issue; prefer POST /tts for sensitive text.
    """
    # Limit query-param text length to reduce log exposure of lesson content.
    if len(text) > 1000:
        raise HTTPException(
            status_code=413,
            detail="text exceeds 1000-character limit for GET /tts; use POST /tts instead",
        )
    return _render_tts(text, language=language, voice_style=voice_style, voice=voice,
                       instructor=instructor, slang=slang)


@app.post("/tts")
def tts(req: TtsRequest) -> Response:
    """Render narration to natural MP3 audio in the chosen accent + personality.

    A ``voice`` id (from /tts/voices) selects an accent (British, Texan,
    Australian, Mandarin, Mexican Spanish, …); an ``instructor`` id (from
    /tts/instructors) shapes the personality/delivery (kind, strict, child,
    cartoon, …); ``slang`` applies the region's phrasing. Engine order:
    ElevenLabs -> edge-tts neural -> 501 (client on-device fallback).
    """
    return _render_tts(req.text, language=req.language, voice_style=req.voice_style,
                       voice=req.voice, instructor=req.instructor, slang=req.slang)


def _render_tts(text: str, *, language: str, voice_style: str,
                voice: str = "", instructor: str = "", slang: bool = True) -> Response:
    text = (text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required")
    cfg = app.state.config
    headers = {"Cache-Control": "no-store"}

    from aoep_shared.voice_catalog import resolve_voice

    chosen = resolve_voice(voice, language=language)
    edge_voice = chosen.edge_voice if chosen else ""
    eleven_voice_id = chosen.elevenlabs_voice_id if chosen else ""
    speak_lang = chosen.language if chosen else language

    # Instructor personality shapes delivery (prosody) + ElevenLabs style preset.
    from aoep_shared.instructors import resolve_instructor

    persona = resolve_instructor(instructor)
    edge_rate = persona.edge_rate if persona else "+0%"
    edge_pitch = persona.edge_pitch if persona else "+0Hz"
    if persona:
        voice_style = persona.voice_style

    # Regional slang: rewrite the narration in the voice's dialect flavor.
    # Applied BEFORE truncation so the expansion doesn't push us past the limit.
    if slang and chosen and chosen.dialect:
        try:
            from aoep_shared.dialect import humanize_narration

            text = humanize_narration(text, chosen.dialect, language=speak_lang)
        except Exception:
            pass  # slang is best-effort; never fail narration over it

    # Truncate after slang expansion so provider character limits are respected.
    if len(text) > 5000:
        text = text[:5000]

    # 0) CosyVoice 2 (self-hosted) is preferred when configured. The instructor's
    #    tone hint becomes the natural-language instruction (instruct2 mode).
    from aoep_shared import cosyvoice_tts

    try:
        cosyvoice_ready = cosyvoice_tts.cosyvoice_configured(getattr(cfg, "cosyvoice_url", ""))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"invalid cosyvoice_url: {exc}")

    if cosyvoice_ready:
        try:
            audio, ctype = cosyvoice_tts.synthesize(
                text, base_url=cfg.cosyvoice_url, language=speak_lang,
                speaker=(chosen.cosyvoice_speaker if chosen else ""),
                instruct=(persona.tone_hint if persona else ""),
                api_key=getattr(cfg, "cosyvoice_api_key", ""),
            )
            return Response(content=audio, media_type=ctype or "audio/wav",
                            headers={**headers, "X-TTS-Engine": "cosyvoice"})
        except Exception:
            pass  # fall through to ElevenLabs / edge-tts / client fallback

    from aoep_shared import elevenlabs_tts

    el_ready = elevenlabs_tts.elevenlabs_configured(cfg.elevenlabs_api_key)

    # 1) ElevenLabs when a specific EL voice is mapped, OR when no accent-specific
    #    edge voice is requested (EL is the most natural default).
    if el_ready and (eleven_voice_id or not edge_voice):
        try:
            audio = elevenlabs_tts.synthesize(
                text, api_key=cfg.elevenlabs_api_key, language=speak_lang,
                style=voice_style, voice_id=eleven_voice_id, model=cfg.elevenlabs_model,
            )
            return Response(content=audio, media_type="audio/mpeg",
                            headers={**headers, "X-TTS-Engine": "elevenlabs"})
        except Exception:
            # Any engine error (HTTP, timeout, truncated read) falls through to
            # the next engine — a single failing engine must never 500 narration.
            pass

    # 2) edge-tts neural — TRUE per-accent voices (British/Aussie/Mandarin/…).
    import tempfile
    from pathlib import Path

    from aoep_shared.meeting.natural_tts import synthesize_neural

    _fd, _tmp_str = tempfile.mkstemp(suffix=".mp3")
    os.close(_fd)  # close immediately; we only need the path
    tmp = Path(_tmp_str)
    try:
        if synthesize_neural(text, tmp, language=speak_lang, voice=edge_voice,
                             rate=edge_rate, pitch=edge_pitch):
            data = tmp.read_bytes()
            return Response(content=data, media_type="audio/mpeg",
                            headers={**headers, "X-TTS-Engine": "edge-tts"})
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass

    # 3) ElevenLabs default as a last resort (e.g. edge-tts not installed).
    if el_ready:
        try:
            audio = elevenlabs_tts.synthesize(
                text, api_key=cfg.elevenlabs_api_key, language=speak_lang,
                style=voice_style, model=cfg.elevenlabs_model,
            )
            return Response(content=audio, media_type="audio/mpeg",
                            headers={**headers, "X-TTS-Engine": "elevenlabs"})
        except Exception:
            pass

    # 4) No server engine — client uses on-device speech synthesis.
    raise HTTPException(
        status_code=501,
        detail="no server TTS engine configured; use client speech synthesis",
    )


# --------------------------------------------------------------------------- #
# Phase 2 - multilingual delivery routing + translation
# --------------------------------------------------------------------------- #
class StudentLang(BaseModel):
    student_id: str
    language: str


class DeliveryPlanRequest(BaseModel):
    lesson_language: str = "en"
    students: list[StudentLang] = []


class DeliveryPlanItem(BaseModel):
    student_id: str
    language: str
    supported: bool
    translate: bool
    translation_supported: bool
    tts_engine: str


class DeliveryPlanResponse(BaseModel):
    lesson_language: str
    plans: list[DeliveryPlanItem]


@app.post("/delivery/plan", response_model=DeliveryPlanResponse)
def delivery_plan(req: DeliveryPlanRequest) -> DeliveryPlanResponse:
    try:
        plans = plan_delivery(
            req.lesson_language, [(s.student_id, s.language) for s in req.students]
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return DeliveryPlanResponse(
        lesson_language=req.lesson_language,
        plans=[DeliveryPlanItem(**p.__dict__) for p in plans],
    )


class TranslateRequest(BaseModel):
    text: str
    source: str
    target: str


@app.post("/translate")
def translate(req: TranslateRequest) -> dict:
    if not is_pair_supported(req.source, req.target):
        raise HTTPException(
            status_code=422,
            detail=f"unsupported language pair {req.source}->{req.target}",
        )
    provider = app.state.factory.speech()
    try:
        translated = provider.translate(req.text, source=req.source, target=req.target)
    except NotImplementedError as exc:
        # Pair is valid; the NLLB model just isn't loaded in this environment.
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"translation failed: {exc}")
    return {"source": req.source, "target": req.target, "text": translated}


# --------------------------------------------------------------------------- #
# Language learning: 20+ languages, multi-skill, gamified
# --------------------------------------------------------------------------- #
@app.get("/learn/languages")
def learn_languages() -> dict:
    from aoep_shared.language_learning import language_list

    langs = language_list()
    return {"languages": langs, "count": len(langs)}


@app.get("/learn/{language}/course")
def learn_course(language: str) -> dict:
    from aoep_shared.language_learning import course_outline

    if language not in SUPPORTED_LANGUAGES:
        raise HTTPException(status_code=404, detail="unsupported language")
    return course_outline(language)


@app.get("/learn/{language}/phrases")
def learn_phrases(language: str, category: str | None = None) -> dict:
    from aoep_shared.language_learning import phrases_for

    if language not in SUPPORTED_LANGUAGES:
        raise HTTPException(status_code=404, detail="unsupported language")
    return {"language": language, "phrases": phrases_for(language, category)}


@app.get("/learn/{language}/vocabulary")
def learn_vocabulary(language: str, category: str | None = None) -> dict:
    from aoep_shared.language_learning import vocabulary_for

    if language not in SUPPORTED_LANGUAGES:
        raise HTTPException(status_code=404, detail="unsupported language")
    words = vocabulary_for(language, category)
    return {"language": language, "vocabulary": words, "count": len(words)}


@app.get("/learn/{language}/slang")
def learn_slang(language: str) -> dict:
    from aoep_shared.slang import all_entries

    entries = [e for e in all_entries() if e.language == language]
    return {"language": language, "entries": [
        {
            "phrase": e.phrase, "meaning": e.meaning, "region": e.region,
            "kind": e.kind, "register": e.register,
        }
        for e in entries]}


@app.get("/learn/{language}/dialogues")
def learn_dialogues(language: str) -> dict:
    from aoep_shared.language_learning import dialogues_for

    if language not in SUPPORTED_LANGUAGES:
        raise HTTPException(status_code=404, detail="unsupported language")
    return {"language": language, "dialogues": dialogues_for(language)}


@app.get("/learn/{language}/songs")
def learn_songs(language: str) -> dict:
    from aoep_shared.language_learning import songs_for

    if language not in SUPPORTED_LANGUAGES:
        raise HTTPException(status_code=404, detail="unsupported language")
    return {"language": language, "songs": songs_for(language)}


@app.get("/learn/{language}/music-videos")
def learn_music_videos(language: str) -> dict:
    from aoep_shared.language_learning import music_videos_for

    if language not in SUPPORTED_LANGUAGES:
        raise HTTPException(status_code=404, detail="unsupported language")
    return {"language": language, "music_videos": music_videos_for(language)}


@app.get("/learn/{language}/music-video-challenge")
def learn_music_video_challenge(language: str, video_id: str | None = None) -> dict:
    from aoep_shared.language_learning import music_video_challenge

    if language not in SUPPORTED_LANGUAGES:
        raise HTTPException(status_code=404, detail="unsupported language")
    return music_video_challenge(language, video_id=video_id)


@app.get("/learn/{language}/media-challenge")
def learn_media_challenge(language: str, study_size: int = 10, seed: int | None = None) -> dict:
    from aoep_shared.language_learning import media_listening_challenge

    if language not in SUPPORTED_LANGUAGES:
        raise HTTPException(status_code=404, detail="unsupported language")
    return media_listening_challenge(language, study_size=study_size, seed=seed)


@app.get("/learn/{language}/reading-story")
def learn_reading_story(language: str) -> dict:
    from aoep_shared.language_learning import reading_story

    if language not in SUPPORTED_LANGUAGES:
        raise HTTPException(status_code=404, detail="unsupported language")
    return reading_story(language)


class ExplainWordRequest(BaseModel):
    language: str
    word_id: str


@app.post("/learn/explain-word")
def learn_explain_word(req: ExplainWordRequest) -> dict:
    from aoep_shared.language_learning import explain_story_word

    if req.language not in SUPPORTED_LANGUAGES:
        raise HTTPException(status_code=404, detail="unsupported language")
    result = explain_story_word(req.language, req.word_id)
    if not result["found"]:
        raise HTTPException(status_code=404, detail="word not found")
    return result


class ExerciseRequest(BaseModel):
    language: str
    skill: str = "vocabulary"
    n: int = 5


@app.post("/learn/exercise")
def learn_exercise(req: ExerciseRequest) -> dict:
    from aoep_shared import language_learning as ll

    if req.language not in SUPPORTED_LANGUAGES:
        raise HTTPException(status_code=404, detail="unsupported language")
    n = max(
        1,
        min(
            req.n,
            100
            if req.skill in ("conversation", "story", "slang", "idioms")
            else 10
            if req.skill in ("media-listening", "music-video")
            else 8,
        ),
    )
    if req.skill == "listening":
        return ll.listening_exercise(req.language, n=n)
    if req.skill in ("match", "phrases"):
        return ll.match_exercise(req.language, n=n)
    if req.skill in ("pronunciation", "shadowing"):
        return ll.pronunciation_prompt(req.language)
    if req.skill == "grammar":
        return {"skill": "grammar", "language": req.language, "tip": ll.grammar_tip(req.language)}
    if req.skill == "culture":
        return {"skill": "culture", "language": req.language, "note": ll.culture_note(req.language)}
    if req.skill == "reading":
        return ll.reading_story(req.language)
    if req.skill in ("conversation", "story"):
        return ll.dialogue_exercise(req.language, n=n)
    if req.skill in ("slang", "idioms"):
        return ll.slang_exercise(req.language, n=n)
    if req.skill == "songs":
        return {
            "skill": "songs", "language": req.language,
            "songs": ll.songs_for(req.language),
        }
    if req.skill == "media-listening":
        return ll.media_listening_challenge(req.language, study_size=n)
    if req.skill == "music-video":
        return ll.music_video_challenge(req.language)
    return ll.vocabulary_exercise(req.language, n=n)


class PronounceRequest(BaseModel):
    target: str
    heard: str = ""
    mouth_openness: float | None = None


@app.post("/learn/pronounce")
def learn_pronounce(req: PronounceRequest) -> dict:
    """Score a pronunciation attempt (ASR transcript or typed) + vision mouth tip."""
    from aoep_shared.language_learning import assess_pronunciation

    return assess_pronunciation(req.target, req.heard, mouth_openness=req.mouth_openness)


class MusicVideoScoreRequest(BaseModel):
    language: str
    video_id: str = ""
    section_id: str
    translation: str = ""


@app.post("/learn/music-video/score")
def learn_music_video_score(req: MusicVideoScoreRequest) -> dict:
    """RAG-score a music-video section translation for gist (not word-for-word)."""
    from aoep_shared.language_learning import score_music_video_section

    if req.language not in SUPPORTED_LANGUAGES:
        raise HTTPException(status_code=404, detail="unsupported language")
    return score_music_video_section(
        req.language,
        video_id=req.video_id,
        section_id=req.section_id,
        translation=req.translation,
    )


# --------------------------------------------------------------------------- #
# xAI Grok Voice Agent (Speech-to-Speech realtime) — ephemeral client secrets
# --------------------------------------------------------------------------- #


class VoiceTokenRequest(BaseModel):
    """Mint an ephemeral xAI realtime client secret for web/mobile browsers.

    The API key never leaves the speech service; clients connect to
    ``wss://api.x.ai/v1/realtime`` with the short-lived token.
    """

    mode: str = "solo"  # solo | group | self_teach | theodore | …
    lesson_context: str = ""
    learner_names: list[str] = []
    expires_seconds: int = 300
    instructions: str = ""


@app.get("/voice/status")
def voice_status() -> dict:
    """Whether xAI Grok Voice is configured for Theodore / self-teach S2S."""
    from aoep_shared.xai_realtime import REALTIME_WS, xai_configured

    cfg = app.state.config
    # Pass the config value explicitly (including "") so we do NOT fall through
    # to a process-env XAI_API_KEY when the AppConfig field is blank.
    api_key = getattr(cfg, "xai_api_key", "") or ""
    configured = xai_configured(api_key)
    return {
        "available": configured,
        "engine": "xai-grok-voice" if configured else "none",
        "model": getattr(cfg, "xai_voice_model", "grok-voice-latest") or "grok-voice-latest",
        "voice": (
            getattr(cfg, "xai_voice_id", "")
            or getattr(cfg, "xai_voice", "")
            or getattr(cfg, "xai_voice_name", "")
            or "eve"
        ),
        "realtime_ws": REALTIME_WS,
        "hint": (
            "xAI Grok Voice ready — clients mint an ephemeral token via POST /voice/token."
            if configured
            else "Set XAI_API_KEY in aoep-secrets / config/local.env to enable Grok Voice Agents."
        ),
    }


@app.post("/voice/token")
def voice_token(req: VoiceTokenRequest) -> dict:
    """Mint an ephemeral xAI client secret + Theodore/self-teach session.update.

    Web/mobile call this once (or on reconnect), then open the realtime
    WebSocket with ``sec-websocket-protocol: xai-client-secret.<token>``.
    """
    from aoep_shared.xai_realtime import (
        XaiVoiceError,
        build_voice_session,
        mint_ephemeral_token,
        presence_tool_schema,
        xai_configured,
    )

    cfg = app.state.config
    api_key = getattr(cfg, "xai_api_key", "") or ""
    model = getattr(cfg, "xai_voice_model", "grok-voice-latest") or "grok-voice-latest"
    voice_id = (
        getattr(cfg, "xai_voice_id", "")
        or getattr(cfg, "xai_voice", "")
        or getattr(cfg, "xai_voice_name", "")
        or "eve"
    )
    if not xai_configured(api_key):
        raise HTTPException(
            status_code=503,
            detail="XAI_API_KEY is not configured on the speech service",
        )
    voice_cfg = build_voice_session(
        req.mode,
        voice=voice_id,
        model=model,
        lesson_context=req.lesson_context or "",
        learner_names=list(req.learner_names or []),
        instructions=req.instructions or "",
    )
    voice_cfg.tools = [presence_tool_schema()]
    locked_session = dict(voice_cfg.session_update_event()["session"])
    locked_session["model"] = model
    try:
        token = mint_ephemeral_token(
            api_key=api_key,
            expires_seconds=req.expires_seconds,
            model=model,
            allow_mock=False,
            session=locked_session,
        )
    except XaiVoiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {
        "token": token.to_dict(),
        "session_update": voice_cfg.session_update_event(),
        "mode": req.mode,
        "xai_configured": True,
        "engine": "xai-grok-voice",
    }

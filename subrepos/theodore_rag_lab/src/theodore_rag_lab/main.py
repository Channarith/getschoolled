"""FastAPI app for the Theodore RAG auto-tune lab."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

# Load config/local.env so XAI_API_KEY / ELEVENLABS_API_KEY / SPEECH_BASE_URL
# work without a manual `set -a; . config/local.env` in every shell.
try:
    from aoep_shared.env_bootstrap import ensure_lab_env

    ensure_lab_env()
except Exception:  # noqa: BLE001 — labs must still boot offline / without shared
    pass


from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field

from aoep_shared import lab_tts
from aoep_shared.current_awareness import research_current_topic
from aoep_shared.factory import build_factory
from aoep_shared.live_audio_agents import inject_client, install_live_audio_routes

from .bakeoff_loop import get_runner
from .corpus_lab import (
    apply_review,
    corpus_stats,
    export_llm_jsonl,
    export_packs,
    list_review,
    run_train_update,
)
from .dictionary_lab import (
    dialect_probe,
    dictionary_browse,
    dictionary_search,
    feedback_snapshot,
    grade_regurgitation,
    lab_catalog,
    regurgitation_deck,
    sala_reply,
    submit_feedback,
)
from .sala_validation import default_validation
from .qualify_page import render_qualify_page
from .rag_tuning import PRESETS, RagTuning
from .read_aloud_lab import read_aloud_next, read_aloud_progress, read_aloud_score
from .voice_queue import get_voice_queue

app = FastAPI(title="Theodore RAG Lab", version="0.2.0")
install_live_audio_routes(app, lab_name="Theodore RAG Lab")
_FACTORY = build_factory()


@app.get("/", response_class=HTMLResponse)
@app.get("/lab", response_class=HTMLResponse)
def qualify() -> HTMLResponse:
    return HTMLResponse(inject_client(render_qualify_page()))


class TuningPatch(BaseModel):
    knobs: dict[str, Any] = Field(default_factory=dict)


class TrainStart(BaseModel):
    hours: float = Field(default=1.0, gt=0.0, le=24.0)


class DialectProbeReq(BaseModel):
    text: str = "Welcome! We will walk through the lesson. Take your time. Nice work."
    dialect: str = "us_south"
    language: str = "en"
    title: str = "Practice"


class RegurgitateGrade(BaseModel):
    phrase: str
    answer: str
    language: str = "en"
    region: str = "global"
    dialect: str = ""
    learn: bool = True


class FeedbackReq(BaseModel):
    phrase: str
    meaning: str
    language: str = "en"
    region: str = "global"
    kind: str = "idiom"
    action: str = "correct"
    dialect: str = ""
    note: str = ""


class CurrentAwarenessReq(BaseModel):
    question: str = Field(min_length=3, max_length=500)


@app.get("/health")
def health() -> dict[str, Any]:
    runner = get_runner()
    cat = lab_catalog()
    readiness: dict[str, Any] = {}
    try:
        from aoep_shared.env_bootstrap import speech_readiness

        readiness = speech_readiness()
    except Exception:  # noqa: BLE001
        pass
    return {
        "ok": True,
        "service": "theodore-rag-lab",
        "docs": len(runner.index) if runner.index is not None else 0,
        "golden": len(runner.examples),
        "tuning": runner.tuning.to_dict(),
        "lexicon_total": cat["lexicon"].get("total", 0),
        "dialects": len(cat["dialects"]),
        "feedback_events": cat["feedback"].get("events", 0),
        "features": [
            "rag_tuning",
            "dictionary",
            "dictionary_corpus",
            "read_aloud",
            "dialects",
            "regurgitation",
            "feedback_learning",
            "live_current_awareness",
            "voice_queue",
            "training_drop",
        ],
        "corpus": corpus_stats(),
        "current_awareness_live": any(
            getattr(engine, "engine", "") != "mock"
            for engine in _FACTORY.current_news_engines()
        ),
        **readiness,
    }


@app.get("/api/rag/tuning")
def get_tuning() -> dict[str, Any]:
    runner = get_runner()
    return {
        "knobs": runner.tuning.to_dict(),
        "presets": sorted(PRESETS.keys()),
    }


@app.patch("/api/rag/tuning")
def patch_tuning(req: TuningPatch) -> dict[str, Any]:
    runner = get_runner()
    try:
        runner.tuning = runner.tuning.patched(req.knobs)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"knobs": runner.tuning.to_dict()}


@app.post("/api/rag/tuning/preset/{name}")
def apply_preset(name: str) -> dict[str, Any]:
    runner = get_runner()
    try:
        runner.tuning = RagTuning.preset(name)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"preset": name, "knobs": runner.tuning.to_dict()}


@app.post("/api/rag/eval")
def run_eval(details: bool = False) -> dict[str, Any]:
    runner = get_runner()
    report = runner.evaluate_once(include_details=details)
    return {"report": report, "tuning": runner.tuning.to_dict()}


@app.get("/api/rag/sweep")
def run_sweep() -> dict[str, Any]:
    runner = get_runner()
    return {"results": runner.sweep()}


@app.post("/api/rag/train/start")
def train_start(req: TrainStart) -> dict[str, Any]:
    runner = get_runner()
    return runner.start(hours=req.hours)


@app.post("/api/rag/train/run-blocking")
def train_blocking(req: TrainStart) -> dict[str, Any]:
    """Short synchronous bakeoff for CI / scripts (caps rounds)."""
    runner = get_runner()
    hours = min(float(req.hours), 0.05)
    try:
        return runner.run_blocking(hours=hours)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/api/rag/train/status")
def train_status() -> dict[str, Any]:
    return get_runner().status()


@app.post("/api/rag/train/stop")
def train_stop() -> dict[str, Any]:
    return get_runner().stop()


@app.get("/api/rag/champion")
def champion() -> dict[str, Any]:
    return get_runner().status().get("champion") or {}


@app.get("/api/rag/telemetry")
def telemetry() -> dict[str, Any]:
    return get_runner().telemetry.snapshot()


@app.post("/api/current-awareness/research")
def current_awareness(req: CurrentAwarenessReq) -> dict[str, Any]:
    result = research_current_topic(
        req.question,
        _FACTORY.current_news_engines(),
        config=_FACTORY.config,
    )
    return result.to_dict()


@app.get("/api/dictionary")
def api_dictionary(
    q: str = "",
    language: str = "",
    region: str = "",
    kind: str = "",
    limit: int = Query(default=40, ge=1, le=200),
) -> dict[str, Any]:
    if not any((q, language, region, kind)):
        return dictionary_browse(limit=limit)
    return dictionary_search(q=q, language=language, region=region, kind=kind, limit=limit)


@app.get("/api/dialects")
def api_dialects() -> dict[str, Any]:
    return lab_catalog()


@app.post("/api/dialects/probe")
def api_dialect_probe(req: DialectProbeReq) -> dict[str, Any]:
    return dialect_probe(req.text, req.dialect, language=req.language, title=req.title)


class VoiceTurnReq(BaseModel):
    text: str = ""
    dialect: str = "us_south"
    language: str = "en"
    voice: str = ""


@app.post("/api/voice-agent/turn")
def api_voice_agent_turn(req: VoiceTurnReq) -> dict[str, Any]:
    """Sala's spoken reply for a dialect test. The browser plays it through /api/tts."""
    return sala_reply(req.text, req.dialect, language=req.language, voice=req.voice)


class VoiceCheckReq(BaseModel):
    action: str = "pass"
    heard: str = ""
    reply: str = ""
    corrected: str = ""
    dialect: str = ""
    language: str = "en"
    voice: str = ""


@app.get("/api/voice-agent/validation")
def api_voice_validation() -> dict[str, Any]:
    return default_validation().summary()


@app.post("/api/voice-agent/validation")
def api_voice_validation_record(req: VoiceCheckReq) -> dict[str, Any]:
    try:
        return default_validation().record(
            action=req.action,
            heard=req.heard,
            reply=req.reply,
            corrected=req.corrected,
            dialect=req.dialect,
            language=req.language,
            voice=req.voice,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


class TtsReq(BaseModel):
    text: str = ""
    language: str = "en"
    voice: str = ""
    style: str = "warm"


# macOS `say` voices that actually differ by region. Used when edge-tts cannot
# reach its voice host, so Listen still plays on the speakers.
_SAY_VOICES = {
    "en-GB": ("Shelley", "Daniel"),
    "en-AU": ("Karen", "Karen"),
    "en-IE": ("Moira", "Moira"),
    "en-IN": ("Tara", "Rishi"),
    "en-ZA": ("Tessa", "Tessa"),
    "en-US": ("Samantha", "Fred"),
    "zh-HK": ("Sinji", "Sinji"),
    "zh-CN": ("Tingting", "Tingting"),
    "zh-TW": ("Meijia", "Meijia"),
    "ja-JP": ("Kyoko", "Kyoko"),
    "ko-KR": ("Yuna", "Yuna"),
    "es-ES": ("Mónica", "Mónica"),
    "es-MX": ("Paulina", "Paulina"),
    "fr-FR": ("Thomas", "Thomas"),
    "fr-CA": ("Amélie", "Amélie"),
    "pt-BR": ("Luciana", "Luciana"),
    "pt-PT": ("Joana", "Joana"),
    "hi-IN": ("Lekha", "Lekha"),
    "th-TH": ("Kanya", "Kanya"),
    "vi-VN": ("Linh", "Linh"),
    "de-DE": ("Anna", "Anna"),
}
# Southern wording uses the newer macOS US voices. Samantha reads the line
# like a compact announcement and makes the accent sound fake.
_SAY_BY_VOICE = {
    "en_us_south_f": "Flo (English (US))",
    "en_us_south_m": "Reed (English (US))",
}


def _say_voice_name(voice_id: str, language: str = "en") -> str:
    """Pick an installed macOS voice for a catalog id."""
    from aoep_shared.voice_catalog import get_voice

    if voice_id in _SAY_BY_VOICE:
        return _SAY_BY_VOICE[voice_id]
    chosen = get_voice(voice_id)
    base = (language or "en").split("-")[0]
    locale = (chosen.locale if chosen else "") or {
        "en": "en-US",
        "zh": "zh-CN",
        "yue": "zh-HK",
        "th": "th-TH",
        "vi": "vi-VN",
        "km": "km-KH",
        "tl": "fil-PH",
        "ja": "ja-JP",
        "ko": "ko-KR",
        "es": "es-ES",
        "fr": "fr-FR",
        "pt": "pt-BR",
        "hi": "hi-IN",
        "de": "de-DE",
    }.get(base, "")
    if not locale:
        return ""
    gender = chosen.gender if chosen else "female"
    pair = _SAY_VOICES.get(locale)
    if pair is None:
        if locale.lower().startswith("en"):
            pair = ("Samantha", "Fred")
        else:
            return ""
    return pair[1] if gender == "male" else pair[0]


def _macos_preview(text: str, voice_id: str, language: str) -> tuple[bytes, str, str] | None:
    """Render with macOS `say` so the browser can play the file on the speakers."""
    if not shutil.which("say"):
        return None
    say_voice = _say_voice_name(voice_id, language)
    if not say_voice:
        return None
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        aiff = folder / "line.aiff"
        wav = folder / "line.wav"
        try:
            subprocess.run(
                ["say", "-v", say_voice, "-o", str(aiff), text],
                check=True,
                capture_output=True,
                timeout=20,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
            return None
        if shutil.which("afconvert"):
            try:
                subprocess.run(
                    ["afconvert", "-f", "WAVE", "-d", "LEI16@22050", str(aiff), str(wav)],
                    check=True,
                    capture_output=True,
                    timeout=20,
                )
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
                wav = aiff
        else:
            wav = aiff
        if not wav.is_file():
            return None
        audio = wav.read_bytes()
    if len(audio) <= 4096:
        # macOS `say` writes a 4096-byte header when the synthesizer is blocked
        # and puts no samples in it. Playing that file is silence.
        return None
    mime = "audio/wav" if wav.suffix == ".wav" else "audio/aiff"
    return audio, mime, say_voice


def _sala_preview(text: str, language: str) -> tuple[bytes, str, str, str]:
    """Play Sala on the local speakers.

    Live Sala is xAI voice Ara. That session is refused when the team is out
    of credits, so this preview uses CosyVoice when it is configured and
    otherwise a local speaker voice.
    """
    from aoep_shared import cosyvoice_tts

    lang = (language or "en").split("-")[0] or "en"
    if lang != "en":
        from aoep_shared.voice_catalog import default_voice_for_language

        chosen = default_voice_for_language(lang)
        voice_id = chosen.id if chosen else ""
        audio, mime, engine = lab_tts.synthesize(text, language=lang, voice=voice_id)
        return audio, mime, engine, f"Sala speaks {lang} with {voice_id or 'the language voice'}"
    speaker = (os.environ.get("SALA_COSYVOICE_SPEAKER") or "sala").strip() or "sala"
    note = "local Sala preview; the xAI Grok socket is retired"
    if cosyvoice_tts.cosyvoice_configured():
        try:
            audio, mime = cosyvoice_tts.synthesize(
                text, language=language or "en", speaker=speaker,
            )
            return audio, mime, "cosyvoice", "CosyVoice Sala"
        except Exception:  # noqa: BLE001 — local speaker voice still plays
            pass
    try:
        audio, mime, engine = lab_tts.synthesize(text, language="en", voice="en_us_f")
    except lab_tts.ProviderUnavailable:
        spoken = _macos_preview(text, "en_us_f", "en")
        if spoken is None:
            raise
        audio, mime, say_voice = spoken
        return audio, mime, "macos-say", f"{note} ({say_voice})"
    return audio, mime, engine, note


def _tts_response(text: str, language: str, voice: str, style: str) -> Response:
    clean = (text or "").strip()
    if not clean:
        raise HTTPException(status_code=422, detail="tts text is empty")
    note = ""
    try:
        if (voice or "").strip().lower() in {"sala", "salane"}:
            audio, mime, engine, note = _sala_preview(clean, language)
        else:
            audio, mime, engine = lab_tts.synthesize(
                clean, language=language, style=style, voice=voice,
            )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except lab_tts.ProviderUnavailable as exc:
        spoken = _macos_preview(clean, voice or "en_us_f", language)
        if spoken is None:
            raise HTTPException(status_code=501, detail=str(exc)) from exc
        audio, mime, say_voice = spoken
        engine = "macos-say"
        note = f"macOS {say_voice}"
    headers = {
        "X-TTS-Engine": engine,
        "X-TTS-Voice": (voice or "")[:80],
        "Cache-Control": "no-store",
    }
    if note:
        headers["X-TTS-Note"] = note
    return Response(content=audio, media_type=mime, headers=headers)


@app.get("/api/tts/status")
def api_tts_status() -> dict[str, Any]:
    status = lab_tts.tts_status()
    status["speaker_preview"] = True
    status["sala_preview"] = (
        "Hear Sala plays on your speakers without xAI. "
        "Live Sala is xAI voice Ara and stays off when that team is out of credits."
    )
    return status


@app.get("/api/tts")
def api_tts_get(
    text: str = "",
    language: str = "en",
    voice: str = "",
    style: str = "warm",
) -> Response:
    return _tts_response(text, language, voice, style)


@app.post("/api/tts")
def api_tts_post(req: TtsReq) -> Response:
    return _tts_response(req.text, req.language, req.voice, req.style)


@app.get("/api/regurgitate/deck")
def api_regurgitate_deck(
    dialect: str = "",
    region: str = "",
    language: str = "",
    n: int = Query(default=8, ge=1, le=30),
) -> dict[str, Any]:
    return regurgitation_deck(dialect=dialect, region=region, language=language, n=n)


@app.post("/api/regurgitate/grade")
def api_regurgitate_grade(req: RegurgitateGrade) -> dict[str, Any]:
    return grade_regurgitation(
        phrase=req.phrase,
        answer=req.answer,
        language=req.language,
        region=req.region,
        dialect=req.dialect,
        learn=req.learn,
    )


@app.get("/api/feedback")
def api_feedback_get() -> dict[str, Any]:
    return feedback_snapshot()


@app.post("/api/feedback")
def api_feedback_post(req: FeedbackReq) -> dict[str, Any]:
    try:
        return submit_feedback(
            phrase=req.phrase,
            meaning=req.meaning,
            language=req.language,
            region=req.region,
            kind=req.kind,
            action=req.action,
            dialect=req.dialect,
            note=req.note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


class CorpusTrainReq(BaseModel):
    force: bool = False
    language: str = "en"
    synth: bool = False
    ship_packs: bool = False


class CorpusReviewReq(BaseModel):
    entry_id: str
    action: str = "confirm"
    gloss_en: str = ""
    note: str = ""
    inflections: dict[str, str] = Field(default_factory=dict)


class ReadAloudNextReq(BaseModel):
    language: str = "en"
    learner_id: str = "local"
    seed: int | None = None


class ReadAloudScoreReq(BaseModel):
    sentence: str
    heard: str = ""
    target_forms: list[str] = Field(default_factory=list)
    mouth_openness: float | None = None
    language: str = "en"
    learner_id: str = "local"


@app.get("/api/corpus/stats")
def api_corpus_stats() -> dict[str, Any]:
    return corpus_stats()


@app.post("/api/corpus/train-update")
def api_corpus_train_update(req: CorpusTrainReq) -> dict[str, Any]:
    return run_train_update(
        force=req.force,
        language=req.language or "en",
        synth=req.synth,
        ship_packs=req.ship_packs,
    )


@app.get("/api/corpus/review")
def api_corpus_review_list(limit: int = Query(default=40, ge=1, le=200)) -> dict[str, Any]:
    return list_review(limit=limit)


@app.post("/api/corpus/review")
def api_corpus_review_apply(req: CorpusReviewReq) -> dict[str, Any]:
    try:
        return apply_review(
            entry_id=req.entry_id,
            action=req.action,
            gloss_en=req.gloss_en,
            note=req.note,
            inflections=req.inflections or None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/corpus/export-packs")
def api_corpus_export_packs(ship: bool = False) -> dict[str, Any]:
    return export_packs(ship=ship)


@app.post("/api/corpus/export-llm")
def api_corpus_export_llm() -> dict[str, Any]:
    return export_llm_jsonl()


@app.post("/api/read-aloud/next")
def api_read_aloud_next(req: ReadAloudNextReq) -> dict[str, Any]:
    result = read_aloud_next(
        language=req.language or "en",
        learner_id=req.learner_id or "local",
        seed=req.seed,
    )
    if result.get("error") == "no_sentences":
        raise HTTPException(
            status_code=404,
            detail="no curriculum sentences — POST /api/corpus/train-update first",
        )
    return result


@app.post("/api/read-aloud/score")
def api_read_aloud_score(req: ReadAloudScoreReq) -> dict[str, Any]:
    return read_aloud_score(
        sentence=req.sentence,
        heard=req.heard,
        target_forms=req.target_forms,
        mouth_openness=req.mouth_openness,
        language=req.language or "en",
        learner_id=req.learner_id or "local",
    )


@app.get("/api/read-aloud/progress")
def api_read_aloud_progress(learner_id: str = "local") -> dict[str, Any]:
    return read_aloud_progress(learner_id=learner_id or "local")


class VoiceQueueStart(BaseModel):
    pools: list[str] = Field(default_factory=list)
    workers: int = Field(default=1, ge=1, le=12)
    max_urls: int | None = Field(default=None, ge=1)
    max_channels: int | None = Field(default=None, ge=1)
    include_news: bool = False
    min_videos: int = Field(default=1, ge=1)


@app.get("/api/voice/queue")
def api_voice_queue() -> dict[str, Any]:
    return get_voice_queue().snapshot()


@app.post("/api/voice/queue/start")
def api_voice_queue_start(req: VoiceQueueStart) -> dict[str, Any]:
    from aoep_shared.cosyvoice_ingest.queue import VoiceQueueBusy

    try:
        return get_voice_queue().start(
            pools=req.pools,
            workers=req.workers,
            max_urls=req.max_urls,
            max_channels=req.max_channels,
            include_news=req.include_news,
            min_videos=req.min_videos,
        )
    except VoiceQueueBusy as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/voice/queue/stop")
def api_voice_queue_stop() -> dict[str, Any]:
    return get_voice_queue().stop()


class TrainingDropReq(BaseModel):
    links: list[str] = Field(default_factory=list)
    language: str = "en"
    expand_limit: int = Field(default=20, ge=0, le=500)
    fetch_pages: bool = False


def _stage_drop(**kwargs: Any) -> dict[str, Any]:
    from aoep_shared.training_intake import drop_training

    report = drop_training(**kwargs)
    _add_dropped_docs()
    return report


def _add_dropped_docs() -> None:
    from aoep_shared.rag import Document
    from aoep_shared.training_intake import iter_rag_texts

    runner = get_runner()
    index = runner.index
    if index is None:
        return
    have = {doc.doc_id for doc in getattr(index, "_docs", [])}
    for doc_id, title, text in iter_rag_texts():
        if doc_id in have:
            continue
        index.add(Document.from_text(doc_id, title, text))


@app.get("/api/training/drop")
def api_training_drop_status() -> dict[str, Any]:
    from aoep_shared.training_intake import intake_summary

    return intake_summary()


@app.post("/api/training/drop")
def api_training_drop(req: TrainingDropReq) -> dict[str, Any]:
    return _stage_drop(
        links=req.links,
        language=req.language or "en",
        expand_limit=req.expand_limit,
        fetch_pages=req.fetch_pages,
    )


@app.post("/api/training/drop/upload")
async def api_training_drop_upload(request: Request) -> dict[str, Any]:
    form = await request.form()
    payloads: list[tuple[str, bytes]] = []
    for upload in form.getlist("files"):
        if not hasattr(upload, "read"):
            continue
        payloads.append((getattr(upload, "filename", None) or "upload", await upload.read()))
    expand_raw = str(form.get("expand_limit") or "20")
    try:
        expand_limit = int(expand_raw)
    except ValueError:
        expand_limit = 20
    fetch_raw = str(form.get("fetch_pages") or "false")
    return _stage_drop(
        links=_split_form_links(str(form.get("links") or "")),
        files=payloads,
        language=str(form.get("language") or "en"),
        expand_limit=max(0, min(500, expand_limit)),
        fetch_pages=fetch_raw.strip().lower() in {"1", "true", "yes", "on"},
    )


def _split_form_links(links: str) -> list[str]:
    return [line.strip() for line in (links or "").splitlines() if line.strip()]


@app.post("/api/training/drop/train")
def api_training_drop_train(max_urls: int | None = None) -> dict[str, Any]:
    import threading

    from aoep_shared.training_intake import intake_root, train_dropped

    holder: dict[str, Any] = {}

    def _run() -> None:
        try:
            holder["report"] = train_dropped(max_urls=max_urls)
        except Exception as exc:  # noqa: BLE001
            holder["report"] = {"ok": False, "detail": str(exc)}
        path = intake_root() / "voice_train_status.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(holder["report"], default=str), encoding="utf-8")

    threading.Thread(target=_run, name="training-drop", daemon=True).start()
    return {"ok": True, "started": True, "root": str(intake_root())}


def main() -> None:
    import uvicorn

    uvicorn.run("theodore_rag_lab.main:app", host="0.0.0.0", port=8095, reload=False)


if __name__ == "__main__":
    main()

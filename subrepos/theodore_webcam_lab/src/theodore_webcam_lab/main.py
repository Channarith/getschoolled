from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from .analysis import AnalyzerPolicy, WebcamSessionAnalyzer
from .games import WebcamLearningGameEngine
from .live_metrics import LiveMetricsStore
from .types import (
    AudioAnswerAssessment,
    ClassEvaluation,
    ClassMode,
    LiveSessionMetricsResponse,
    SupportedLanguage,
    VoiceResponse,
    VoiceQuestion,
    WebcamGameResult,
    WebcamGameType,
    WebcamLearningChallenge,
    WebcamSignal,
)
from .voice_agents import XaiVoiceAgent

app = FastAPI(
    title="Theodore Webcam Lab",
    version="0.1.0",
    description=(
        "Private-ready sandbox for Theodore webcam image recognition "
        "and xAI-backed natural responses."
    ),
)

_analyzer = WebcamSessionAnalyzer(policy=AnalyzerPolicy())
_game_engine = WebcamLearningGameEngine(_analyzer)
_live_metrics_store = LiveMetricsStore()
_voice_agent = XaiVoiceAgent.from_env()


class WebcamEvaluationRequest(BaseModel):
    session_id: str = Field(min_length=1)
    mode: ClassMode = ClassMode.SOLO
    signals: list[WebcamSignal] = Field(default_factory=list)
    expected_participant_ids: list[str] = Field(default_factory=list)


class VoiceRequest(BaseModel):
    class_mode: ClassMode = ClassMode.SOLO
    learner_message: str = Field(min_length=1)
    language_code: str = Field(default="en", min_length=2, max_length=8)
    context: str = ""


class VoiceQuestionRequest(BaseModel):
    class_mode: ClassMode = ClassMode.SOLO
    language_code: str = Field(default="en", min_length=2, max_length=8)
    topic: str = Field(min_length=1)
    difficulty: str = Field(default="medium")
    context: str = ""


class AudioAnswerRequest(BaseModel):
    class_mode: ClassMode = ClassMode.SOLO
    language_code: str = Field(default="en", min_length=2, max_length=8)
    question: str = Field(min_length=1)
    audio_transcript: str = Field(min_length=1)
    expected_answer: str = ""
    context: str = ""


class ChallengeRequest(BaseModel):
    session_id: str = Field(min_length=1)
    mode: ClassMode = ClassMode.SOLO
    learning_prompt: str = Field(min_length=1)
    participant_ids: list[str] = Field(default_factory=list)
    preferred_game_type: WebcamGameType | None = None


class ChallengeAttemptRequest(BaseModel):
    challenge_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    mode: ClassMode = ClassMode.SOLO
    signals: list[WebcamSignal] = Field(default_factory=list)
    expected_participant_ids: list[str] = Field(default_factory=list)


@app.get("/health")
def health() -> dict[str, str]:
    return {"service": "theodore-webcam-lab", "status": "ok"}


@app.get("/api/theodore/voice/languages", response_model=list[SupportedLanguage])
def voice_languages() -> list[SupportedLanguage]:
    return _voice_agent.supported_languages()


@app.post("/api/theodore/webcam/evaluate", response_model=ClassEvaluation)
def evaluate_webcam(req: WebcamEvaluationRequest) -> ClassEvaluation:
    evaluation = _analyzer.evaluate(
        session_id=req.session_id,
        mode=req.mode,
        signals=req.signals,
        expected_participant_ids=req.expected_participant_ids,
    )
    updated_at_ms = max([item.timestamp_ms for item in req.signals], default=0)
    _live_metrics_store.record(
        session_id=req.session_id,
        evaluation=evaluation,
        updated_at_ms=updated_at_ms,
    )
    return evaluation


@app.get(
    "/api/theodore/webcam/live-metrics/{session_id}",
    response_model=LiveSessionMetricsResponse,
)
def live_metrics(session_id: str) -> LiveSessionMetricsResponse:
    try:
        return _live_metrics_store.snapshot(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="session metrics not found")


@app.get("/theodore/webcam/live-monitor/{session_id}", response_class=HTMLResponse)
def live_monitor_page(session_id: str) -> HTMLResponse:
    page = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Theodore Live Monitor - {session_id}</title>
  <style>
    body {{ margin: 0; font-family: Arial, sans-serif; background: #0f172a; color: #e2e8f0; }}
    .layout {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; padding: 12px; }}
    .panel {{ background: #111827; border: 1px solid #334155; border-radius: 8px; padding: 10px; }}
    .panel h2 {{ margin: 0 0 8px 0; font-size: 16px; }}
    .summary-grid {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; }}
    .metric {{ background: #1f2937; border-radius: 6px; padding: 6px; font-size: 12px; }}
    .metric .v {{ font-size: 16px; font-weight: bold; margin-top: 4px; }}
    .windows {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 12px; }}
    .student {{ background: #1f2937; border: 1px solid #334155; border-radius: 8px; padding: 8px; }}
    .student h3 {{ margin: 0 0 6px 0; font-size: 14px; }}
    .kv {{ display: flex; justify-content: space-between; font-size: 12px; margin: 3px 0; }}
    progress {{ width: 100%; height: 9px; }}
    .alerts li {{ margin-bottom: 6px; font-size: 12px; }}
    canvas {{ width: 100%; height: 72px; background: #0b1220; border-radius: 6px; margin-top: 8px; }}
  </style>
</head>
<body>
  <div class="layout">
    <div class="panel">
      <h2>Session {session_id}</h2>
      <div id="state"></div>
      <div class="summary-grid" id="summary"></div>
    </div>
    <div class="panel">
      <h2>Lesson Alerts</h2>
      <ul class="alerts" id="alerts"></ul>
    </div>
  </div>
  <div class="panel" style="margin:0 12px 12px 12px;">
    <h2>Student Windows (Live Metrics)</h2>
    <div class="windows" id="windows"></div>
  </div>
  <script>
    const sessionId = {session_id!r};
    const endpoint = `/api/theodore/webcam/live-metrics/${{sessionId}}`;

    function drawLines(canvas, seriesList, colors) {{
      const ctx = canvas.getContext('2d');
      const w = canvas.width = canvas.clientWidth * window.devicePixelRatio;
      const h = canvas.height = canvas.clientHeight * window.devicePixelRatio;
      ctx.clearRect(0, 0, w, h);
      ctx.strokeStyle = '#334155';
      ctx.strokeRect(0, 0, w, h);
      for (let s = 0; s < seriesList.length; s++) {{
        const vals = seriesList[s];
        if (!vals || vals.length < 2) continue;
        ctx.beginPath();
        ctx.strokeStyle = colors[s];
        for (let i = 0; i < vals.length; i++) {{
          const x = (i / (vals.length - 1)) * (w - 8) + 4;
          const y = (1 - Math.max(0, Math.min(1, vals[i]))) * (h - 8) + 4;
          if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        }}
        ctx.stroke();
      }}
    }}

    function pct(v) {{ return `${{Math.round((v || 0) * 100)}}%`; }}
    function num(v, digits=2) {{ return v === null || v === undefined ? 'n/a' : Number(v).toFixed(digits); }}

    async function refresh() {{
      let res;
      try {{
        res = await fetch(endpoint, {{ cache: 'no-store' }});
      }} catch (err) {{
        document.getElementById('state').textContent = 'Waiting for metrics stream...';
        return;
      }}
      if (!res.ok) {{
        document.getElementById('state').textContent = 'No metrics yet. Start posting /evaluate frames.';
        return;
      }}
      const data = await res.json();
      document.getElementById('state').innerHTML =
        `<div class="kv"><span>Training paused</span><strong>${{data.training_paused}}</strong></div>` +
        `<div class="kv"><span>Pause reason</span><strong>${{data.pause_reason || 'none'}}</strong></div>` +
        `<div class="kv"><span>Updated at</span><strong>${{data.updated_at_ms}}</strong></div>`;

      const s = data.quality_summary || {{}};
      document.getElementById('summary').innerHTML = `
        <div class="metric"><div>Avg distance (m)</div><div class="v">${{num(s.avg_distance_from_camera_m)}}</div></div>
        <div class="metric"><div>Light quality</div><div class="v">${{pct(s.avg_light_quality_score)}}</div></div>
        <div class="metric"><div>Image quality</div><div class="v">${{pct(s.avg_image_detection_quality_score)}}</div></div>
        <div class="metric"><div>Behavior score</div><div class="v">${{pct(s.avg_expression_behavior_score)}}</div></div>
        <div class="metric"><div>Mic quality</div><div class="v">${{num(s.avg_microphone_quality_score, 2)}}</div></div>
        <div class="metric"><div>Noise filter</div><div class="v">${{num(s.avg_noise_filter_effectiveness_score, 2)}}</div></div>
      `;

      const alerts = data.lesson_alerts || [];
      document.getElementById('alerts').innerHTML = alerts.length
        ? alerts.map(a => `<li><strong>[${{a.level}}]</strong> ${{a.message}} <em>${{a.action || ''}}</em></li>`).join('')
        : '<li>No lesson alerts</li>';

      const windows = (data.participants || []).map((p) => `
        <div class="student">
          <h3>Window #${{p.window_index}} · ${{p.participant_id}}</h3>
          <div class="kv"><span>State</span><strong>${{p.latest.state}}</strong></div>
          <div class="kv"><span>Distance (m)</span><strong>${{num(p.latest.distance_from_camera_m)}}</strong></div>
          <div class="kv"><span>Light</span><strong>${{pct(p.latest.light_quality_score)}}</strong></div>
          <progress value="${{p.latest.light_quality_score || 0}}" max="1"></progress>
          <div class="kv"><span>Image quality</span><strong>${{pct(p.latest.image_detection_quality_score)}}</strong></div>
          <progress value="${{p.latest.image_detection_quality_score || 0}}" max="1"></progress>
          <div class="kv"><span>Behavior</span><strong>${{pct(p.latest.expression_behavior_score)}}</strong></div>
          <progress value="${{p.latest.expression_behavior_score || 0}}" max="1"></progress>
          <div class="kv"><span>Mic quality</span><strong>${{num(p.latest.microphone_quality_score)}}</strong></div>
          <progress value="${{p.latest.microphone_quality_score || 0}}" max="1"></progress>
          <div class="kv"><span>Noise filter</span><strong>${{num(p.latest.noise_filter_effectiveness_score)}}</strong></div>
          <progress value="${{p.latest.noise_filter_effectiveness_score || 0}}" max="1"></progress>
          <div class="kv"><span>Expression</span><strong>${{p.latest.dominant_expression}}</strong></div>
          <div class="kv"><span>Cheating</span><strong>${{p.latest.suspected_cheating}}</strong></div>
          <canvas id="chart-${{p.participant_id.replace(/[^a-zA-Z0-9_-]/g, '_')}}"></canvas>
        </div>
      `).join('');
      document.getElementById('windows').innerHTML = windows || '<div>No participant windows yet.</div>';

      (data.participants || []).forEach((p) => {{
        const id = `chart-${{p.participant_id.replace(/[^a-zA-Z0-9_-]/g, '_')}}`;
        const canvas = document.getElementById(id);
        if (!canvas) return;
        drawLines(
          canvas,
          [
            p.light_quality_score || [],
            p.image_detection_quality_score || [],
            p.microphone_quality_score || [],
          ],
          ['#22c55e', '#60a5fa', '#f59e0b']
        );
      }});
    }}
    refresh();
    setInterval(refresh, 1000);
  </script>
</body>
</html>"""
    return HTMLResponse(page)


@app.post(
    "/api/theodore/webcam/games/challenge",
    response_model=WebcamLearningChallenge,
)
def create_challenge(req: ChallengeRequest) -> WebcamLearningChallenge:
    return _game_engine.create_challenge(
        session_id=req.session_id,
        mode=req.mode,
        learning_prompt=req.learning_prompt,
        participant_ids=req.participant_ids,
        preferred_game_type=req.preferred_game_type,
    )


@app.post(
    "/api/theodore/webcam/games/attempt",
    response_model=WebcamGameResult,
)
def attempt_challenge(req: ChallengeAttemptRequest) -> WebcamGameResult:
    try:
        return _game_engine.score_attempt(
            challenge_id=req.challenge_id,
            session_id=req.session_id,
            mode=req.mode,
            signals=req.signals,
            expected_participant_ids=req.expected_participant_ids,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.post("/api/theodore/voice/respond", response_model=VoiceResponse)
def voice_respond(req: VoiceRequest) -> VoiceResponse:
    try:
        return _voice_agent.respond(
            learner_message=req.learner_message,
            class_mode=req.class_mode,
            language_code=req.language_code,
            context=req.context,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.post("/api/theodore/voice/ask-question", response_model=VoiceQuestion)
def voice_ask_question(req: VoiceQuestionRequest) -> VoiceQuestion:
    try:
        return _voice_agent.ask_question(
            class_mode=req.class_mode,
            language_code=req.language_code,
            topic=req.topic,
            difficulty=req.difficulty,
            context=req.context,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.post(
    "/api/theodore/voice/absorb-audio-answer",
    response_model=AudioAnswerAssessment,
)
def voice_absorb_audio_answer(req: AudioAnswerRequest) -> AudioAnswerAssessment:
    try:
        return _voice_agent.absorb_audio_answer(
            class_mode=req.class_mode,
            language_code=req.language_code,
            question=req.question,
            audio_transcript=req.audio_transcript,
            expected_answer=req.expected_answer,
            context=req.context,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

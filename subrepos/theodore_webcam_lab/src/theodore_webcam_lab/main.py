from __future__ import annotations

import html
import json

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from .analysis import AnalyzerPolicy, WebcamSessionAnalyzer
from .imaging import analyze_luminance_grid
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
from .vision_tuning import PRESETS, VisionTuning
from .voice_tuning import PRESETS as VOICE_PRESETS
from .voice_tuning import VoiceTuning
from .voice_agents import XaiVoiceAgent

app = FastAPI(
    title="Theodore Webcam Lab",
    version="0.1.0",
    description=(
        "Private-ready sandbox for Theodore webcam image recognition "
        "and xAI-backed natural responses."
    ),
)

_analyzer = WebcamSessionAnalyzer(
    policy=AnalyzerPolicy.from_env(), tuning=VisionTuning.from_env()
)
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
    session_id: str = ""
    fast_mode: bool = True
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


def _js_string_literal(value: str) -> str:
    """Render a Python string as a JS literal that cannot break out of a <script> block."""
    encoded = json.dumps(value)
    for char, escape in (("<", "\\u003c"), (">", "\\u003e"), ("&", "\\u0026")):
        encoded = encoded.replace(char, escape)
    return encoded


_MONITOR_CSS = """
    body { margin: 0; font-family: Arial, sans-serif; background: #0f172a; color: #e2e8f0; }
    .layout { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; padding: 12px; }
    .panel { background: #111827; border: 1px solid #334155; border-radius: 8px; padding: 10px; }
    .panel h2 { margin: 0 0 8px 0; font-size: 16px; }
    .summary-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; }
    .metric { background: #1f2937; border-radius: 6px; padding: 6px; font-size: 12px; }
    .metric .v { font-size: 16px; font-weight: bold; margin-top: 4px; }
    .windows {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 12px;
    }
    .student { background: #1f2937; border: 1px solid #334155; border-radius: 8px; padding: 8px; }
    .student h3 { margin: 0 0 6px 0; font-size: 14px; }
    .kv { display: flex; justify-content: space-between; font-size: 12px; margin: 3px 0; }
    progress { width: 100%; height: 9px; }
    .alerts li { margin-bottom: 6px; font-size: 12px; }
    select, button, input[type=range] { font-size: 11px; }
    button { cursor: pointer; background: #334155; color: #e2e8f0;
             border: 1px solid #475569; border-radius: 4px; padding: 2px 8px; }
    /* Camera beside tuning: video on the left, knobs on the right, both visible. */
    .stage { display: grid; grid-template-columns: minmax(320px, 1fr) minmax(340px, 1fr);
             gap: 12px; padding: 12px; align-items: start; }
    #cam { width: 100%; max-height: 300px; background: #000; border-radius: 6px;
           object-fit: cover; transform: scaleX(-1); }
    .camrow { display: flex; gap: 6px; align-items: center; margin-top: 6px; flex-wrap: wrap; }
    .pill { font-size: 10px; padding: 1px 6px; border-radius: 999px;
            background: #1f2937; border: 1px solid #334155; }
    .pill.bad { background: #7f1d1d; border-color: #b91c1c; }
    .pill.good { background: #14532d; border-color: #166534; }
    .tabs { display: flex; gap: 6px; margin-bottom: 6px; }
    .tabs button.active { background: #1d4ed8; border-color: #3b82f6; }
    /* Compact: knobs scroll inside a fixed height so the camera stays on screen. */
    .knobscroll { max-height: 300px; overflow-y: auto; padding-right: 4px; }
    .knob { display: grid; grid-template-columns: 1.35fr 1.6fr 0.45fr; gap: 5px;
            align-items: center; font-size: 10px; margin: 1px 0; }
    .knob input[type=range] { height: 12px; }
    details > summary { cursor: pointer; font-size: 11px; margin: 4px 0 2px;
                        color: #93c5fd; }
    canvas { width: 100%; height: 72px; background: #0b1220; border-radius: 6px; margin-top: 8px; }
"""

_MONITOR_JS = """
    const sessionId = __SESSION_ID_JSON__;
    const endpoint = `/api/theodore/webcam/live-metrics/${encodeURIComponent(sessionId)}`;

    function esc(value) {
      return String(value === null || value === undefined ? '' : value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
    }

    function drawLines(canvas, seriesList, colors) {
      const ctx = canvas.getContext('2d');
      const w = canvas.width = canvas.clientWidth * window.devicePixelRatio;
      const h = canvas.height = canvas.clientHeight * window.devicePixelRatio;
      ctx.clearRect(0, 0, w, h);
      ctx.strokeStyle = '#334155';
      ctx.strokeRect(0, 0, w, h);
      for (let s = 0; s < seriesList.length; s++) {
        const vals = seriesList[s] || [];
        if (vals.length < 2) continue;
        ctx.beginPath();
        ctx.strokeStyle = colors[s];
        let penDown = false;
        for (let i = 0; i < vals.length; i++) {
          const raw = vals[i];
          if (raw === null || raw === undefined) { penDown = false; continue; }
          const x = (i / (vals.length - 1)) * (w - 8) + 4;
          const y = (1 - Math.max(0, Math.min(1, raw))) * (h - 8) + 4;
          if (!penDown) { ctx.moveTo(x, y); penDown = true; } else { ctx.lineTo(x, y); }
        }
        ctx.stroke();
      }
    }

    function pct(v) {
      if (v === null || v === undefined) return 'n/a';
      return `${Math.round(v * 100)}%`;
    }

    function num(v, digits = 2) {
      if (v === null || v === undefined) return 'n/a';
      return Number(v).toFixed(digits);
    }

    function bar(v) {
      return `<progress value="${v === null || v === undefined ? 0 : v}" max="1"></progress>`;
    }

    async function refresh() {
      let res;
      try {
        res = await fetch(endpoint, { cache: 'no-store' });
      } catch (err) {
        document.getElementById('state').textContent = 'Waiting for metrics stream...';
        return;
      }
      if (!res.ok) {
        document.getElementById('state').textContent =
          'No metrics yet. Start posting /evaluate frames.';
        return;
      }
      const data = await res.json();
      document.getElementById('state').innerHTML =
        `<div class="kv"><span>Training paused</span><strong>${data.training_paused}` +
        `</strong></div>` +
        `<div class="kv"><span>Pause reason</span><strong>${esc(data.pause_reason || 'none')}` +
        `</strong></div>` +
        `<div class="kv"><span>Updated at</span><strong>${esc(data.updated_at_ms)}</strong></div>`;

      const s = data.quality_summary || {};
      document.getElementById('summary').innerHTML = `
        <div class="metric"><div>Avg distance (m)</div>
          <div class="v">${num(s.avg_distance_from_camera_m)}</div></div>
        <div class="metric"><div>Light quality</div>
          <div class="v">${pct(s.avg_light_quality_score)}</div></div>
        <div class="metric"><div>Image quality</div>
          <div class="v">${pct(s.avg_image_detection_quality_score)}</div></div>
        <div class="metric"><div>Behavior score</div>
          <div class="v">${pct(s.avg_expression_behavior_score)}</div></div>
        <div class="metric"><div>Mic quality</div>
          <div class="v">${num(s.avg_microphone_quality_score)}</div></div>
        <div class="metric"><div>Noise filter</div>
          <div class="v">${num(s.avg_noise_filter_effectiveness_score)}</div></div>
      `;

      const gates = (data.quality_summary || {}).quality_flag_counts || {};
      const gateText = Object.keys(gates).length
        ? Object.entries(gates).map(([k, v]) => `${k}=${v}`).join(', ')
        : 'none';
      document.getElementById('gatecounts').textContent = gateText;

      const alerts = data.lesson_alerts || [];
      document.getElementById('alerts').innerHTML = alerts.length
        ? alerts.map(a => `<li><strong>[${esc(a.level)}]</strong> ${esc(a.message)} ` +
            `<em>${esc(a.action || '')}</em></li>`).join('')
        : '<li>No lesson alerts</li>';

      const windows = (data.participants || []).map((p) => `
        <div class="student">
          <h3>Window #${esc(p.window_index)} - ${esc(p.participant_id)}</h3>
          <div class="kv"><span>State</span><strong>${esc(p.latest.state)}</strong></div>
          <div class="kv"><span>Distance (m)</span>
            <strong>${num(p.latest.distance_from_camera_m)}</strong></div>
          <div class="kv"><span>Light</span>
            <strong>${pct(p.latest.light_quality_score)}</strong></div>
          ${bar(p.latest.light_quality_score)}
          <div class="kv"><span>Image quality</span>
            <strong>${pct(p.latest.image_detection_quality_score)}</strong></div>
          ${bar(p.latest.image_detection_quality_score)}
          <div class="kv"><span>Behavior</span>
            <strong>${pct(p.latest.expression_behavior_score)}</strong></div>
          ${bar(p.latest.expression_behavior_score)}
          <div class="kv"><span>Mic quality</span>
            <strong>${num(p.latest.microphone_quality_score)}</strong></div>
          ${bar(p.latest.microphone_quality_score)}
          <div class="kv"><span>Noise filter</span>
            <strong>${num(p.latest.noise_filter_effectiveness_score)}</strong></div>
          ${bar(p.latest.noise_filter_effectiveness_score)}
          <div class="kv"><span>Expression</span>
            <strong>${esc(p.latest.dominant_expression)}</strong></div>
          <div class="kv"><span>Cheating</span>
            <strong>${p.latest.suspected_cheating}</strong></div>
          <canvas data-chart-for="${esc(p.participant_id)}"></canvas>
        </div>
      `).join('');
      document.getElementById('windows').innerHTML =
        windows || '<div>No participant windows yet.</div>';

      (data.participants || []).forEach((p) => {
        const canvas = document.querySelector(
          `canvas[data-chart-for="${CSS.escape(p.participant_id)}"]`
        );
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
      });
    }
    // Knobs surfaced as live sliders: the ones operators reach for first when
    // detection quality looks wrong in the room they are actually in. Grouped so
    // the panel stays short enough to sit beside the camera.
    const VISION_TUNABLE = [
      ['light_min_quality', 0, 1, 0.01],
      ['light_underexposed_luma', 0, 1, 0.01],
      ['light_overexposed_luma', 0, 1, 0.01],
      ['sobel_binary_threshold', 0, 1, 0.01],
      ['sobel_min_edge_density', 0, 0.5, 0.005],
      ['sharpness_min_quality', 0, 1, 0.01],
      ['distance_reference_face_ratio', 0.02, 0.6, 0.01],
      ['distance_too_far_m', 0.5, 4, 0.05],
      ['gaze_down_min_threshold', 0, 1, 0.01],
      ['typing_activity_min_threshold', 0, 1, 0.01],
      ['keyboard_typing_audio_min_threshold', 0, 1, 0.01],
      ['audio_min_mic_quality', 0, 1, 0.01],
      ['audio_max_noise_level_db', 20, 100, 1],
      ['audio_min_snr_db', 0, 40, 0.5],
    ];

    const VOICE_TUNABLE = [
      ['reply_temperature_fast', 0, 2, 0.05],
      ['reply_max_tokens_fast', 16, 512, 8],
      ['reply_max_sentences', 1, 8, 1],
      ['question_temperature', 0, 2, 0.05],
      ['assessment_temperature', 0, 2, 0.05],
      ['fast_timeout_s', 1, 30, 0.5],
      ['cache_ttl_s', 1, 120, 1],
      ['max_history_turns', 1, 12, 1],
    ];

    // Which knob set the panel is editing: 'vision' or 'voice'.
    let tuningScope = 'vision';
    const scopeConfig = {
      vision: { base: '/api/theodore/vision/tuning', knobs: VISION_TUNABLE },
      voice: { base: '/api/theodore/voice/tuning', knobs: VOICE_TUNABLE },
    };

    function setStatus(text) {
      document.getElementById('tuning-status').textContent = text;
    }

    async function patchKnob(name, value) {
      const res = await fetch(scopeConfig[tuningScope].base, {
        method: 'PATCH',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ knobs: { [name]: Number(value) } }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}));
        setStatus(`rejected: ${esc(detail.detail || res.status)}`);
        return false;
      }
      setStatus(`${name} = ${value}`);
      return true;
    }

    function renderKnobs(knobs) {
      const host = document.getElementById('knobs');
      host.innerHTML = scopeConfig[tuningScope].knobs.map(([name, min, max, step]) => `
        <div class="knob">
          <span title="${esc(name)}">${esc(name)}</span>
          <input type="range" data-knob="${esc(name)}" min="${min}" max="${max}"
                 step="${step}" value="${knobs[name]}" />
          <strong data-knob-value="${esc(name)}">${knobs[name]}</strong>
        </div>
      `).join('');
      host.querySelectorAll('input[data-knob]').forEach((input) => {
        input.addEventListener('input', (event) => {
          const name = event.target.dataset.knob;
          const readout = host.querySelector(`[data-knob-value="${name}"]`);
          if (readout) readout.textContent = event.target.value;
        });
        input.addEventListener('change', async (event) => {
          await patchKnob(event.target.dataset.knob, event.target.value);
        });
      });
    }

    async function loadTuning() {
      const res = await fetch(scopeConfig[tuningScope].base, { cache: 'no-store' });
      if (!res.ok) return;
      const data = await res.json();
      const select = document.getElementById('preset');
      select.innerHTML = (data.presets || [])
        .map((p) => `<option value="${esc(p)}">${esc(p)}</option>`).join('');
      renderKnobs(data.knobs || {});
    }

    function selectScope(scope) {
      tuningScope = scope;
      document.getElementById('tab-vision').classList.toggle('active', scope === 'vision');
      document.getElementById('tab-voice').classList.toggle('active', scope === 'voice');
      loadTuning();
    }
    document.getElementById('tab-vision')
      .addEventListener('click', () => selectScope('vision'));
    document.getElementById('tab-voice')
      .addEventListener('click', () => selectScope('voice'));

    document.getElementById('apply-preset').addEventListener('click', async () => {
      const name = document.getElementById('preset').value;
      const res = await fetch(
        `${scopeConfig[tuningScope].base}/preset/${encodeURIComponent(name)}`,
        { method: 'POST' }
      );
      setStatus(res.ok ? `preset applied: ${name}` : `preset failed: ${res.status}`);
      if (res.ok) await loadTuning();
    });

    // ---------------- Camera -> luminance grid -> live gates ----------------
    // Frames are downsampled to a small grid and posted to /evaluate, so the very
    // same Sobel/exposure knobs being dragged above are applied to real video.
    const GRID_W = 48;
    const GRID_H = 36;
    const camVideo = document.getElementById('cam');
    const grab = document.getElementById('grab');
    let camStream = null;
    let camTimer = null;
    let patternPhase = 0;
    let usingPattern = false;

    function setCamState(text, kind) {
      const el = document.getElementById('cam-state');
      el.textContent = text;
      el.className = 'pill' + (kind ? ' ' + kind : '');
    }

    function luminanceGrid() {
      grab.width = GRID_W;
      grab.height = GRID_H;
      const ctx = grab.getContext('2d', { willReadFrequently: true });
      if (usingPattern) {
        // Deterministic moving bars: lets tuning be exercised where no camera
        // exists (CI boxes, VMs) without pretending a camera is present.
        patternPhase = (patternPhase + 1) % GRID_W;
        for (let x = 0; x < GRID_W; x++) {
          const on = ((x + patternPhase) % 8) < 4;
          ctx.fillStyle = on ? '#d8d8d8' : '#202020';
          ctx.fillRect(x, 0, 1, GRID_H);
        }
      } else {
        if (!camVideo.videoWidth) return null;
        ctx.drawImage(camVideo, 0, 0, GRID_W, GRID_H);
      }
      const data = ctx.getImageData(0, 0, GRID_W, GRID_H).data;
      const rows = [];
      for (let y = 0; y < GRID_H; y++) {
        const row = [];
        for (let x = 0; x < GRID_W; x++) {
          const i = (y * GRID_W + x) * 4;
          // Rec. 601 luma keeps the reading comparable to what a client would send.
          row.push((0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2]) / 255);
        }
        rows.push(row);
      }
      return rows;
    }

    async function sampleFrame() {
      const grid = luminanceGrid();
      if (!grid) return;
      const body = {
        session_id: sessionId,
        mode: 'solo',
        signals: [{
          participant_id: 'camera-local',
          timestamp_ms: Date.now() % 100000000,
          face_count: 1,
          liveness_state: 'live',
          foreground_ratio: 0.4,
          motion_score: 0.2,
          luminance_grid: grid,
        }],
      };
      let res;
      try {
        res = await fetch('/api/theodore/webcam/evaluate', {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify(body),
        });
      } catch (err) {
        setCamState('post failed', 'bad');
        return;
      }
      if (!res.ok) { setCamState('evaluate ' + res.status, 'bad'); return; }
      const data = await res.json();
      const p = (data.participants || []).find((x) => x.participant_id === 'camera-local');
      if (!p) return;
      document.getElementById('cam-readings').innerHTML = [
        ['sharpness', num(p.sharpness_score)],
        ['edge density', num(p.edge_density, 3)],
        ['light', pct(p.light_quality_score)],
        ['image q', pct(p.image_detection_quality_score)],
        ['confidence', pct(p.recognition_confidence)],
      ].map(([k, v]) => `<span class="pill">${esc(k)}: ${esc(v)}</span>`).join(' ');
      const gates = p.quality_flags || [];
      const gateEl = document.getElementById('cam-gates');
      gateEl.textContent = gates.length ? gates.join(', ') : 'all passing';
      gateEl.style.color = gates.length ? '#fca5a5' : '#86efac';
    }

    function startSampling() {
      if (camTimer) clearInterval(camTimer);
      camTimer = setInterval(sampleFrame, 500);
    }

    function stopCamera() {
      if (camTimer) { clearInterval(camTimer); camTimer = null; }
      if (camStream) { camStream.getTracks().forEach((t) => t.stop()); camStream = null; }
      camVideo.srcObject = null;
      usingPattern = false;
      setCamState('idle');
    }

    document.getElementById('cam-start').addEventListener('click', async () => {
      stopCamera();
      setCamState('requesting...');
      try {
        camStream = await navigator.mediaDevices.getUserMedia({
          video: { width: 640, height: 480 }, audio: false,
        });
      } catch (err) {
        // No camera / permission denied is expected on servers and CI boxes.
        setCamState('camera unavailable', 'bad');
        document.getElementById('cam-note').textContent =
          'getUserMedia failed (' + (err && err.name ? err.name : 'error') +
          '). Use "Test pattern" to tune without a camera.';
        return;
      }
      camVideo.srcObject = camStream;
      usingPattern = false;
      setCamState('live', 'good');
      document.getElementById('cam-note').textContent = '';
      startSampling();
    });

    document.getElementById('cam-pattern').addEventListener('click', () => {
      stopCamera();
      usingPattern = true;
      setCamState('test pattern', 'good');
      document.getElementById('cam-note').textContent =
        'Synthetic moving bars: exercises the same Sobel/exposure path as a camera.';
      startSampling();
    });

    document.getElementById('cam-stop').addEventListener('click', stopCamera);

    loadTuning();
    refresh();
    setInterval(refresh, 1000);
"""

_MONITOR_PAGE_TEMPLATE = (
    """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Theodore Live Monitor - __SESSION_TITLE__</title>
  <style>"""
    + _MONITOR_CSS
    + """  </style>
</head>
<body>
  <div class="layout">
    <div class="panel">
      <h2>Session __SESSION_TITLE__</h2>
      <div id="state"></div>
      <div class="summary-grid" id="summary"></div>
    </div>
    <div class="panel">
      <h2>Lesson Alerts</h2>
      <ul class="alerts" id="alerts"></ul>
    </div>
  </div>

  <div class="stage">
    <div class="panel">
      <h2>Camera</h2>
      <video id="cam" autoplay muted playsinline></video>
      <canvas id="grab" style="display:none;"></canvas>
      <div class="camrow">
        <button id="cam-start" type="button">Start camera</button>
        <button id="cam-stop" type="button">Stop</button>
        <button id="cam-pattern" type="button">Test pattern</button>
        <span class="pill" id="cam-state">idle</span>
      </div>
      <div class="camrow" id="cam-readings"></div>
      <div class="kv"><span>Live gates</span><strong id="cam-gates">-</strong></div>
      <div class="kv"><span id="cam-note" style="font-size:10px;color:#94a3b8;"></span></div>
    </div>

    <div class="panel">
      <h2>Tuning</h2>
      <div class="tabs">
        <button id="tab-vision" class="active" type="button">Vision</button>
        <button id="tab-voice" type="button">Voice (xAI)</button>
      </div>
      <div class="kv">
        <span>Preset</span>
        <span>
          <select id="preset"></select>
          <button id="apply-preset" type="button">Apply</button>
        </span>
      </div>
      <div class="knobscroll" id="knobs"></div>
      <div class="kv"><span>Failed gates (class)</span><strong id="gatecounts">-</strong></div>
      <div class="kv"><span id="tuning-status" style="font-size:10px;"></span></div>
    </div>
  </div>
  <div class="panel" style="margin:0 12px 12px 12px;">
    <h2>Student Windows (Live Metrics)</h2>
    <div class="windows" id="windows"></div>
  </div>
  <script>"""
    + _MONITOR_JS
    + """  </script>
</body>
</html>"""
)


class TuningPatchRequest(BaseModel):
    """Partial tuning update; omitted knobs keep their current value."""

    knobs: dict[str, float] = Field(default_factory=dict)


class ImagingAnalyzeRequest(BaseModel):
    luminance_grid: list[list[float]] = Field(min_length=3)


@app.get("/api/theodore/vision/tuning")
def get_vision_tuning() -> dict[str, object]:
    return {
        "knobs": _analyzer.tuning.to_dict(),
        "presets": sorted(PRESETS),
        "env_prefix": "AOEP_VISION_",
    }


@app.patch("/api/theodore/vision/tuning")
def patch_vision_tuning(req: TuningPatchRequest) -> dict[str, object]:
    """Adjust recognition knobs live, without restarting the service."""
    try:
        updated = _analyzer.tuning.patched(req.knobs)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    _analyzer.tuning = updated
    return {"knobs": updated.to_dict(), "applied": sorted(req.knobs)}


@app.post("/api/theodore/vision/tuning/preset/{name}")
def apply_vision_preset(name: str) -> dict[str, object]:
    try:
        preset = VisionTuning.preset(name)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    _analyzer.tuning = preset
    return {"preset": name.strip().lower(), "knobs": preset.to_dict()}


@app.get("/api/theodore/voice/tuning")
def get_voice_tuning() -> dict[str, object]:
    return {
        "knobs": _voice_agent.tuning.to_dict(),
        "presets": sorted(VOICE_PRESETS),
        "env_prefix": "XAI_TUNE_",
        "model": {"fast": _voice_agent.fast_model, "full": _voice_agent.model},
    }


@app.patch("/api/theodore/voice/tuning")
def patch_voice_tuning(req: TuningPatchRequest) -> dict[str, object]:
    """Adjust xAI generation/latency knobs live, without restarting the service."""
    try:
        updated = _voice_agent.tuning.patched(req.knobs)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    _voice_agent.tuning = updated
    return {"knobs": updated.to_dict(), "applied": sorted(req.knobs)}


@app.post("/api/theodore/voice/tuning/preset/{name}")
def apply_voice_preset(name: str) -> dict[str, object]:
    try:
        preset = VoiceTuning.preset(name)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    _voice_agent.tuning = preset
    return {"preset": name.strip().lower(), "knobs": preset.to_dict()}


@app.post("/api/theodore/vision/imaging/analyze")
def analyze_imaging(req: ImagingAnalyzeRequest) -> dict[str, object]:
    """Run Sobel edge + exposure analysis on a luminance grid using active tuning."""
    try:
        analysis = analyze_luminance_grid(req.luminance_grid, tuning=_analyzer.tuning)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "width": analysis.width,
        "height": analysis.height,
        "backend": analysis.backend,
        "mean_luminance": analysis.mean_luminance,
        "underexposed_ratio": analysis.underexposed_ratio,
        "overexposed_ratio": analysis.overexposed_ratio,
        "mean_gradient": analysis.mean_gradient,
        "percentile_gradient": analysis.percentile_gradient,
        "edge_density": analysis.edge_density,
        "sharpness_score": analysis.sharpness_score,
        "light_quality_score": analysis.light_quality_score,
        "blurry": analysis.blurry,
        "low_edge_detail": analysis.low_edge_detail,
        "underexposed": analysis.underexposed,
        "overexposed": analysis.overexposed,
        "flags": analysis.flags,
        "signal_fields": analysis.to_signal_fields(),
    }


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
        raise HTTPException(status_code=404, detail="session metrics not found") from None


@app.get("/theodore/webcam/live-monitor/{session_id}", response_class=HTMLResponse)
def live_monitor_page(session_id: str) -> HTMLResponse:
    safe_title = html.escape(session_id)
    return HTMLResponse(
        _MONITOR_PAGE_TEMPLATE.replace("__SESSION_TITLE__", safe_title).replace(
            "__SESSION_ID_JSON__", _js_string_literal(session_id)
        )
    )


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
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/theodore/voice/respond", response_model=VoiceResponse)
def voice_respond(req: VoiceRequest) -> VoiceResponse:
    try:
        return _voice_agent.respond(
            learner_message=req.learner_message,
            class_mode=req.class_mode,
            language_code=req.language_code,
            session_id=req.session_id,
            fast_mode=req.fast_mode,
            context=req.context,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


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
        raise HTTPException(status_code=422, detail=str(exc)) from exc


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
        raise HTTPException(status_code=422, detail=str(exc)) from exc

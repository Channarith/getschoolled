/*
 * Theodore webcam lab demo client.
 *
 * Renders one camera tile per learner (a real webcam, or a deterministic
 * simulated classroom so the pipeline is demonstrable on machines with no
 * camera), pushes frames to the lab service, and drives the Grok voice agent.
 *
 * Voice has two paths. With XAI_API_KEY set the browser opens a WebSocket
 * straight to wss://api.x.ai/v1/realtime using a server-minted ephemeral
 * token, streams 24 kHz PCM both ways, and answers Grok's function calls out
 * of the live class state. Without a key it falls back to text turns plus the
 * on-device speech synthesiser so the loop is still fully demonstrable.
 */

const API = "";
const FRAME_WIDTH = 480;
const FRAME_HEIGHT = 360;
const FRAME_INTERVAL_MS = 250;
const PCM_RATE = 24000;

const state = {
  sessionId: "",
  mode: "solo",
  source: "simulated",
  running: false,
  tiles: [],
  timer: null,
  busy: false,
  webcamStream: null,
  voice: { mode: "idle", ws: null, audio: null, mic: null, playhead: 0, spoken: new Set() },
};

const el = (id) => document.getElementById(id);
const tilesEl = el("tiles");
const cueLogEl = el("cue-log");
const voiceLogEl = el("voice-log");

/* ---------------------------------------------------------------- scene */

function buildBackdrop(seed) {
  const canvas = document.createElement("canvas");
  canvas.width = FRAME_WIDTH;
  canvas.height = FRAME_HEIGHT;
  const ctx = canvas.getContext("2d");

  const wall = ctx.createLinearGradient(0, 0, FRAME_WIDTH, 0);
  wall.addColorStop(0, "#454c58");
  wall.addColorStop(1, "#6b7484");
  ctx.fillStyle = wall;
  ctx.fillRect(0, 0, FRAME_WIDTH, FRAME_HEIGHT);

  ctx.fillStyle = "#a9b0a5";
  ctx.fillRect(FRAME_WIDTH * 0.62, FRAME_HEIGHT * 0.08, FRAME_WIDTH * 0.32, FRAME_HEIGHT * 0.37);
  ctx.fillStyle = "#767f92";
  ctx.fillRect(FRAME_WIDTH * 0.05, FRAME_HEIGHT * 0.16, FRAME_WIDTH * 0.25, FRAME_HEIGHT * 0.26);
  ctx.fillStyle = "#3a3d44";
  ctx.fillRect(0, FRAME_HEIGHT * 0.82, FRAME_WIDTH, FRAME_HEIGHT * 0.18);

  // Deterministic speckle: the background must be identical frame to frame or
  // calibration never settles.
  let s = seed * 7919 + 13;
  const rand = () => {
    s = (s * 1103515245 + 12345) & 0x7fffffff;
    return s / 0x7fffffff;
  };
  const image = ctx.getImageData(0, 0, FRAME_WIDTH, FRAME_HEIGHT);
  for (let i = 0; i < image.data.length; i += 4) {
    const n = (rand() - 0.5) * 10;
    image.data[i] = Math.max(0, Math.min(255, image.data[i] + n));
    image.data[i + 1] = Math.max(0, Math.min(255, image.data[i + 1] + n));
    image.data[i + 2] = Math.max(0, Math.min(255, image.data[i + 2] + n));
  }
  ctx.putImageData(image, 0, 0);
  return canvas;
}

function drawPerson(ctx, phase) {
  const sway = Math.sin(phase) * 1.5;
  const cx = FRAME_WIDTH * 0.5 + sway;
  const bodyW = FRAME_WIDTH * 0.24;
  const bodyH = FRAME_HEIGHT * 0.62;
  const top = FRAME_HEIGHT - bodyH + sway;
  const headRy = bodyW * 0.34;
  const headRx = bodyW * 0.28;
  const headCy = top + headRy;

  ctx.fillStyle = "#20242c";
  ctx.beginPath();
  ctx.ellipse(cx, headCy, headRx, headRy, 0, 0, Math.PI * 2);
  ctx.fill();

  const shoulderY = headCy + headRy * 1.25;
  ctx.beginPath();
  ctx.moveTo(cx - bodyW / 2, shoulderY + bodyH * 0.06);
  ctx.lineTo(cx - bodyW * 0.34, shoulderY);
  ctx.lineTo(cx + bodyW * 0.34, shoulderY);
  ctx.lineTo(cx + bodyW / 2, shoulderY + bodyH * 0.06);
  ctx.lineTo(cx + bodyW * 0.4, FRAME_HEIGHT);
  ctx.lineTo(cx - bodyW * 0.4, FRAME_HEIGHT);
  ctx.closePath();
  ctx.fill();
}

/* ----------------------------------------------------------------- tiles */

function makeTile(index, participantId, displayName) {
  const node = document.createElement("div");
  node.className = "tile";
  node.innerHTML = `
    <header>
      <strong>${displayName}</strong>
      <span class="badge" data-role="badge">idle</span>
    </header>
    <div class="stage">
      <canvas data-role="source" width="${FRAME_WIDTH}" height="${FRAME_HEIGHT}"></canvas>
      <canvas class="overlay" data-role="overlay" width="${FRAME_WIDTH}" height="${FRAME_HEIGHT}"></canvas>
    </div>
    <div class="tile-meta">
      <div>state<b data-role="state">—</b></div>
      <div>human score<b data-role="score">—</b></div>
      <div>away<b data-role="away">0s</b></div>
    </div>
    <div class="row buttons" style="margin-top:10px">
      <button data-role="toggle">Step away</button>
    </div>`;
  tilesEl.appendChild(node);

  const tile = {
    index,
    participantId,
    displayName,
    node,
    source: node.querySelector('[data-role="source"]'),
    overlay: node.querySelector('[data-role="overlay"]'),
    badge: node.querySelector('[data-role="badge"]'),
    stateEl: node.querySelector('[data-role="state"]'),
    scoreEl: node.querySelector('[data-role="score"]'),
    awayEl: node.querySelector('[data-role="away"]'),
    toggle: node.querySelector('[data-role="toggle"]'),
    backdrop: buildBackdrop(index + 1),
    atDesk: false,
    phase: Math.random() * 6,
    video: null,
    useWebcam: false,
  };

  tile.toggle.addEventListener("click", () => {
    tile.atDesk = !tile.atDesk;
    tile.toggle.textContent = tile.atDesk ? "Step away" : "Sit at desk";
    tile.toggle.classList.toggle("away", !tile.atDesk);
  });
  tile.toggle.textContent = "Sit at desk";
  tile.toggle.classList.add("away");
  return tile;
}

function renderTile(tile) {
  const ctx = tile.source.getContext("2d");
  if (tile.useWebcam && tile.video && tile.video.readyState >= 2) {
    ctx.drawImage(tile.video, 0, 0, FRAME_WIDTH, FRAME_HEIGHT);
    return;
  }
  ctx.drawImage(tile.backdrop, 0, 0);
  if (tile.atDesk) {
    tile.phase += 0.12;
    drawPerson(ctx, tile.phase);
  }
}

function drawOverlay(tile, body) {
  const ctx = tile.overlay.getContext("2d");
  ctx.clearRect(0, 0, FRAME_WIDTH, FRAME_HEIGHT);
  const observation = body.observation || {};
  const shapes = observation.silhouettes || [];
  const present = body.presence && body.presence.state === "present";
  ctx.lineWidth = 3;
  ctx.strokeStyle = present ? "#3ddc84" : "#ffb454";
  ctx.font = "bold 13px Inter, sans-serif";
  shapes.forEach((s) => {
    const [x, y, w, h] = s.bbox;
    ctx.strokeRect(x, y, w, h);
    ctx.fillStyle = present ? "#3ddc84" : "#ffb454";
    ctx.fillRect(x, Math.max(0, y - 18), 96, 18);
    ctx.fillStyle = "#08111c";
    ctx.fillText(`silhouette ${s.human_score.toFixed(2)}`, x + 5, Math.max(12, y - 5));
  });
  if (observation.calibrating) {
    ctx.fillStyle = "rgba(8, 17, 28, 0.75)";
    ctx.fillRect(0, FRAME_HEIGHT - 30, FRAME_WIDTH, 30);
    ctx.fillStyle = "#93a2b8";
    ctx.fillText("calibrating background…", 10, FRAME_HEIGHT - 11);
  } else if (!shapes.length) {
    ctx.fillStyle = "rgba(8, 17, 28, 0.75)";
    ctx.fillRect(0, FRAME_HEIGHT - 30, FRAME_WIDTH, 30);
    ctx.fillStyle = "#ff6b6b";
    ctx.fillText("no learner detected", 10, FRAME_HEIGHT - 11);
  }
}

function updateTileMeta(tile, body) {
  const presence = body.presence || {};
  const stateName = presence.state || "—";
  tile.badge.textContent = stateName;
  tile.badge.className = `badge ${stateName}`;
  tile.stateEl.textContent = stateName;
  tile.scoreEl.textContent = (body.observation && body.observation.confidence
    ? body.observation.confidence
    : 0
  ).toFixed(2);
  tile.awayEl.textContent = `${Math.round(presence.absent_seconds || 0)}s`;
}

/* ------------------------------------------------------------------- api */

async function api(path, options) {
  const response = await fetch(`${API}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`${response.status} ${detail.slice(0, 200)}`);
  }
  return response.json();
}

/* ------------------------------------------------------------------ logs */

function logCue(cue) {
  if (cueLogEl.querySelector(".empty")) cueLogEl.innerHTML = "";
  const li = document.createElement("li");
  if (cue.severity === "warn") li.classList.add("warn");
  const time = new Date().toLocaleTimeString();
  li.innerHTML = `<div class="action">${cue.action.replace(/_/g, " ")} · ${time}</div>
    <div>${cue.headline}</div>
    ${cue.speech ? `<div class="speech">“${cue.speech}”</div>` : ""}`;
  cueLogEl.prepend(li);
  while (cueLogEl.children.length > 40) cueLogEl.lastChild.remove();
}

function logVoice(role, text) {
  if (!text) return;
  if (voiceLogEl.querySelector(".empty")) voiceLogEl.innerHTML = "";
  const li = document.createElement("li");
  li.className = role === "user" ? "user" : "";
  li.innerHTML = `<div class="action">${role === "user" ? "Learner" : "Theodore"}</div>
    <div class="speech">${text}</div>`;
  voiceLogEl.prepend(li);
  while (voiceLogEl.children.length > 40) voiceLogEl.lastChild.remove();
}

function setPill(id, text, kind) {
  const pill = el(id);
  pill.textContent = text;
  pill.className = `pill ${kind}`;
}

/* --------------------------------------------------------------- session */

function rosterFor(mode) {
  if (mode === "group") {
    return [
      { participant_id: "ana", display_name: "Ana" },
      { participant_id: "ben", display_name: "Ben" },
      { participant_id: "cy", display_name: "Cy" },
    ];
  }
  return [{ participant_id: "learner-1", display_name: "Maya" }];
}

async function attachWebcam(tile) {
  if (!state.webcamStream) {
    state.webcamStream = await navigator.mediaDevices.getUserMedia({
      video: { width: FRAME_WIDTH, height: FRAME_HEIGHT },
      audio: false,
    });
  }
  const video = document.createElement("video");
  video.srcObject = state.webcamStream;
  video.muted = true;
  video.playsInline = true;
  await video.play();
  tile.video = video;
  tile.useWebcam = true;
  tile.toggle.disabled = true;
  tile.toggle.textContent = "Live camera";
}

async function startSession() {
  const mode = el("mode").value;
  const source = el("source").value;
  const roster = rosterFor(mode);

  const created = await api("/v1/sessions", {
    method: "POST",
    body: JSON.stringify({
      mode,
      lesson_title: el("lesson").value,
      checkpoint: el("checkpoint").value,
      participants: roster,
    }),
  });

  state.sessionId = created.session_id;
  state.mode = mode;
  state.source = source;
  state.running = true;
  tilesEl.innerHTML = "";
  state.tiles = roster.map((p, i) => makeTile(i, p.participant_id, p.display_name));

  if (source === "webcam") {
    try {
      await attachWebcam(state.tiles[0]);
      el("hint").textContent =
        "Tile 1 is your real camera; remaining tiles stay simulated. Step out of frame to trigger an absence.";
    } catch (error) {
      el("hint").textContent = `Camera unavailable (${error.message}); using the simulated classroom.`;
    }
  }

  setPill("pill-session", `session ${state.sessionId} · ${mode}`, "pill-ok");
  el("btn-start").textContent = "Restart session";
  el("btn-recalibrate").disabled = false;
  el("btn-end").disabled = false;
  el("btn-voice").disabled = false;
  el("btn-ask").disabled = false;

  if (state.timer) clearInterval(state.timer);
  state.timer = setInterval(pump, FRAME_INTERVAL_MS);

  showVoiceConfig().catch(() => {});
}

async function showVoiceConfig() {
  const params = new URLSearchParams({
    session_id: state.sessionId,
    participant_id: state.tiles.length ? state.tiles[0].participantId : "",
  });
  const plan = await api(`/v1/voice/session-config?${params.toString()}`);
  el("voice-config").textContent = JSON.stringify(plan.session_update, null, 2);
}

async function pump() {
  if (!state.running || state.busy) return;
  state.busy = true;
  try {
    for (const tile of state.tiles) {
      renderTile(tile);
      const image = tile.source.toDataURL("image/jpeg", 0.6);
      const body = await api(`/v1/sessions/${state.sessionId}/frames`, {
        method: "POST",
        body: JSON.stringify({ participant_id: tile.participantId, image }),
      });
      drawOverlay(tile, body);
      updateTileMeta(tile, body);
      (body.cues || []).forEach(handleCue);
      renderAttendance(body);
    }
  } catch (error) {
    setPill("pill-service", `service error: ${error.message}`, "pill-bad");
  } finally {
    state.busy = false;
  }
}

function renderAttendance(body) {
  const paused = body.lesson_paused;
  const held = body.class_held;
  const bits = [];
  bits.push(`lesson <b>${paused ? "paused" : "running"}</b>`);
  if (state.mode === "group") bits.push(`class <b>${held ? "on attendance hold" : "live"}</b>`);
  el("attendance").innerHTML = bits.join(" · ");
}

function handleCue(cue) {
  logCue(cue);
  if (cue.voice_turn && cue.speech) speakLine(cue.speech);
}

async function endSession() {
  if (!state.sessionId) return;
  state.running = false;
  clearInterval(state.timer);
  const report = await api(`/v1/sessions/${state.sessionId}`, { method: "DELETE" });
  const rows = report.participants
    .map(
      (p) =>
        `${p.display_name}: ${Math.round(p.present_seconds)}s present, ` +
        `${Math.round(p.absent_seconds)}s away, ${p.absence_count} absence(s)`,
    )
    .join(" · ");
  logCue({
    action: "session_report",
    severity: "info",
    headline: `Session report — ${rows}`,
    speech: "",
  });
  setPill("pill-session", "no session", "pill-idle");
  el("btn-recalibrate").disabled = true;
  el("btn-end").disabled = true;
  state.sessionId = "";
}

/* ------------------------------------------------------------------ voice */

function speakLine(text) {
  logVoice("assistant", text);
  if (state.voice.mode === "realtime" && state.voice.ws && state.voice.ws.readyState === 1) {
    // Presence lines must be delivered verbatim, so use xAI's force_message
    // extension rather than asking the model to improvise them.
    state.voice.ws.send(
      JSON.stringify({
        type: "conversation.item.create",
        item: {
          type: "force_message",
          role: "assistant",
          interruptible: false,
          content: [{ type: "output_text", text }],
        },
      }),
    );
    return;
  }
  if (!("speechSynthesis" in window)) return;
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.rate = 1.02;
  utterance.pitch = 1.0;
  window.speechSynthesis.speak(utterance);
}

async function refreshVoiceStatus() {
  try {
    const status = await api("/v1/voice/status");
    const configured = status.configured;
    setPill("pill-voice", `voice: ${status.mode}`, configured ? "pill-ok" : "pill-warn");
    el("voice-status").innerHTML = configured
      ? `xAI configured — speech-to-speech via <code>${status.voice_model}</code>, voice
         <b>${status.voice}</b>. Tools: ${status.tools.join(", ")}.`
      : `No <code>XAI_API_KEY</code> set, so the agent runs in offline fallback: text turns plus
         the on-device voice. Set the key to open a live Grok speech-to-speech session
         (<code>${status.voice_model}</code>).`;
  } catch (error) {
    setPill("pill-voice", "voice: unavailable", "pill-bad");
    el("voice-status").textContent = `Voice status failed: ${error.message}`;
  }
}

function pcm16ToBase64(int16) {
  const bytes = new Uint8Array(int16.buffer);
  let binary = "";
  for (let i = 0; i < bytes.length; i += 1) binary += String.fromCharCode(bytes[i]);
  return btoa(binary);
}

function base64ToPcm16(value) {
  const binary = atob(value);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
  return new Int16Array(bytes.buffer);
}

function downsampleToPcm16(input, inputRate) {
  const ratio = inputRate / PCM_RATE;
  const length = Math.floor(input.length / ratio);
  const output = new Int16Array(length);
  for (let i = 0; i < length; i += 1) {
    const sample = input[Math.floor(i * ratio)] || 0;
    output[i] = Math.max(-1, Math.min(1, sample)) * 0x7fff;
  }
  return output;
}

function playPcm(int16) {
  const voice = state.voice;
  if (!voice.audio) voice.audio = new AudioContext({ sampleRate: PCM_RATE });
  const ctx = voice.audio;
  const buffer = ctx.createBuffer(1, int16.length, PCM_RATE);
  const channel = buffer.getChannelData(0);
  for (let i = 0; i < int16.length; i += 1) channel[i] = int16[i] / 0x8000;
  const node = ctx.createBufferSource();
  node.buffer = buffer;
  node.connect(ctx.destination);
  const startAt = Math.max(ctx.currentTime, voice.playhead);
  node.start(startAt);
  voice.playhead = startAt + buffer.duration;
}

async function connectVoice() {
  el("btn-voice").disabled = true;
  const plan = await api("/v1/voice/session", {
    method: "POST",
    body: JSON.stringify({
      session_id: state.sessionId,
      participant_id: state.tiles.length ? state.tiles[0].participantId : "",
    }),
  });
  el("voice-config").textContent = JSON.stringify(plan.session_update, null, 2);

  if (plan.fallback) {
    state.voice.mode = "fallback";
    el("voice-status").innerHTML +=
      " <b>Connected in fallback mode</b> — typed questions are answered and spoken locally.";
    el("btn-voice-stop").disabled = false;
    logVoice("assistant", "Voice agent ready in offline fallback mode.");
    return;
  }

  const ws = new WebSocket(plan.url, [plan.subprotocol]);
  state.voice.ws = ws;
  state.voice.mode = "realtime";

  ws.addEventListener("open", async () => {
    ws.send(JSON.stringify(plan.session_update));
    el("btn-voice-stop").disabled = false;
    logVoice("assistant", "Connected to Grok speech-to-speech.");
    await startMic(ws);
  });

  ws.addEventListener("message", (event) => onVoiceEvent(JSON.parse(event.data)));
  ws.addEventListener("close", () => {
    state.voice.mode = "idle";
    el("btn-voice").disabled = false;
    el("btn-voice-stop").disabled = true;
  });
  ws.addEventListener("error", () => logVoice("assistant", "Voice socket error."));
}

async function startMic(ws) {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  const ctx = new AudioContext();
  const source = ctx.createMediaStreamSource(stream);
  const processor = ctx.createScriptProcessor(4096, 1, 1);
  source.connect(processor);
  processor.connect(ctx.destination);
  processor.onaudioprocess = (event) => {
    if (ws.readyState !== 1) return;
    const pcm = downsampleToPcm16(event.inputBuffer.getChannelData(0), ctx.sampleRate);
    ws.send(
      JSON.stringify({ type: "input_audio_buffer.append", audio: pcm16ToBase64(pcm) }),
    );
  };
  state.voice.mic = { stream, ctx, processor };
}

async function onVoiceEvent(event) {
  switch (event.type) {
    case "response.output_audio.delta":
    case "response.audio.delta":
      playPcm(base64ToPcm16(event.delta));
      break;
    case "response.output_audio_transcript.done":
    case "response.audio_transcript.done":
      logVoice("assistant", event.transcript);
      break;
    case "conversation.item.input_audio_transcription.completed":
      logVoice("user", event.transcript);
      break;
    case "response.function_call_arguments.done": {
      let args = {};
      try {
        args = JSON.parse(event.arguments || "{}");
      } catch (error) {
        args = {};
      }
      const outcome = await api("/v1/voice/tool", {
        method: "POST",
        body: JSON.stringify({
          session_id: state.sessionId,
          name: event.name,
          arguments: args,
        }),
      });
      state.voice.ws.send(
        JSON.stringify({
          type: "conversation.item.create",
          item: {
            type: "function_call_output",
            call_id: event.call_id,
            output: JSON.stringify(outcome.result),
          },
        }),
      );
      // Let the current utterance finish before asking for the next turn,
      // otherwise the two responses talk over each other.
      const wait = Math.max(0, state.voice.playhead - (state.voice.audio?.currentTime || 0));
      setTimeout(() => {
        if (state.voice.ws && state.voice.ws.readyState === 1) {
          state.voice.ws.send(JSON.stringify({ type: "response.create" }));
        }
      }, wait * 1000);
      break;
    }
    case "error":
      logVoice("assistant", `xAI error: ${JSON.stringify(event.error || event)}`);
      break;
    default:
      break;
  }
}

function disconnectVoice() {
  const voice = state.voice;
  if (voice.ws) voice.ws.close();
  if (voice.mic) {
    voice.mic.processor.disconnect();
    voice.mic.stream.getTracks().forEach((t) => t.stop());
    voice.mic = null;
  }
  voice.mode = "idle";
  el("btn-voice").disabled = false;
  el("btn-voice-stop").disabled = true;
  logVoice("assistant", "Voice agent disconnected.");
}

async function ask() {
  const input = el("ask");
  const transcript = input.value.trim();
  if (!transcript) return;
  input.value = "";
  logVoice("user", transcript);

  if (state.voice.mode === "realtime" && state.voice.ws && state.voice.ws.readyState === 1) {
    state.voice.ws.send(
      JSON.stringify({
        type: "conversation.item.create",
        item: {
          type: "message",
          role: "user",
          content: [{ type: "input_text", text: transcript }],
        },
      }),
    );
    state.voice.ws.send(JSON.stringify({ type: "response.create" }));
    return;
  }

  const reply = await api("/v1/voice/respond", {
    method: "POST",
    body: JSON.stringify({
      transcript,
      session_id: state.sessionId,
      participant_id: state.tiles.length ? state.tiles[0].participantId : "",
    }),
  });
  speakLine(reply.text);
}

/* ------------------------------------------------------------------- boot */

async function boot() {
  try {
    const health = await api("/health");
    setPill("pill-service", `service: ${health.status}`, "pill-ok");
  } catch (error) {
    setPill("pill-service", "service: unreachable", "pill-bad");
  }
  await refreshVoiceStatus();
}

el("btn-start").addEventListener("click", () => startSession().catch((e) => {
  el("hint").textContent = `Could not start: ${e.message}`;
}));
el("btn-end").addEventListener("click", () => endSession().catch(() => {}));
el("btn-recalibrate").addEventListener("click", () =>
  api(`/v1/sessions/${state.sessionId}/recalibrate`, {
    method: "POST",
    body: JSON.stringify({ participant_id: "" }),
  }).catch(() => {}),
);
el("btn-voice").addEventListener("click", () => connectVoice().catch((e) => {
  el("voice-status").textContent = `Voice connect failed: ${e.message}`;
  el("btn-voice").disabled = false;
}));
el("btn-voice-stop").addEventListener("click", disconnectVoice);
el("btn-ask").addEventListener("click", () => ask().catch(() => {}));
el("ask").addEventListener("keydown", (e) => {
  if (e.key === "Enter") ask().catch(() => {});
});

boot();

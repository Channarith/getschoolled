(() => {
  "use strict";
  // The phone WebView also lifts quiet playback. This flag tells that cover
  // the widget already sets its own phone gain, so the two do not stack.
  window.__SALAREEN_LIVE_GAIN__ = true;

  // One native speech-to-speech control shared by every Theodore lab. It never
  // calls /tts: microphone PCM goes directly to xAI/Gemini using a one-use
  // server-minted credential, and returned PCM is scheduled gaplessly.
  function liveAudioUrl(path) {
    const base = window.AOEP_LIVE_AUDIO_BASE || "";
    return base + path;
  }

  const state = {
    ws: null, stream: null, source: null, processor: null, silent: null,
    ctx: null, speaker: null, playDestination: null, provider: "",
    inputRate: 16000, outputRate: 24000, nextPlayAt: 0, playing: new Set(),
    connected: false, stopping: false, dropOutput: false,
    recognitionPaused: false, lastUserAt: 0, idleTimer: null, speechEndTimer: null,
    agentSpeaking: false, micRms: 0, voiceLevel: 0, levelTimer: null, outputGain: null,
    outputComp: null,
    userTalking: false, micSink: null, activityKey: "", activityAt: 0,
  };

  const host = document.createElement("div");
  host.id = "theodore-live-audio";
  const root = host.attachShadow({ mode: "open" });
  root.innerHTML = `
    <style>
      :host{all:initial}
      .box{position:fixed;z-index:2147483646;left:12px;right:auto;bottom:max(18px, env(safe-area-inset-bottom));
        display:flex;flex-wrap:wrap;align-items:center;gap:6px;width:min(260px,calc(100vw - 24px));
        min-height:56px;height:auto;padding:8px 8px 8px 4px;border:1px solid #5eead4;border-radius:18px;
        background:#07111ef2;color:#f8fafc;box-shadow:0 8px 18px #0008;
        font:700 13px/1.3 system-ui,sans-serif;touch-action:none;cursor:grab}
      .box.placed{right:auto;bottom:auto}
      .box.docked{left:12px;right:auto;bottom:max(18px, env(safe-area-inset-bottom))}
      .box.dragging{cursor:grabbing}
      .row{display:flex;align-items:center;gap:6px;margin:0}
      .lead{display:contents}
      select{position:absolute;width:1px;height:1px;margin:-1px;padding:0;overflow:hidden;clip:rect(0 0 0 0);border:0}
      .copy{flex:1;min-width:0;display:flex;flex-direction:column;gap:2px}
      .voice-name{color:#e7fbff;letter-spacing:.02em}
      .status{color:#99f6e4;font-weight:600}
      .caption{flex-basis:100%;margin:0;color:#e2e8f0;font-weight:500;max-height:2.6em;overflow:hidden}
      .caption:empty{display:none}
      .dot{width:8px;height:8px;border-radius:50%;background:#64748b;flex:none}
      .dot.on{background:#34d399;box-shadow:0 0 8px #34d399}
      button{cursor:pointer}
      .toggle{width:40px;height:40px;border:0;border-radius:50%;padding:0;font-size:0;color:transparent;flex:none;
        background:#102029 center/22px 22px no-repeat;
        background-image:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'><path fill='%23e7fbff' d='M12 14a3 3 0 0 0 3-3V6a3 3 0 0 0-6 0v5a3 3 0 0 0 3 3zm5-3a5 5 0 0 1-10 0H5a7 7 0 0 0 6 6.92V21h2v-3.08A7 7 0 0 0 19 11h-2z'/></svg>")}
      .toggle.live{background-color:#065f46;
        background-image:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'><path fill='%23fff' d='M3 9v6h4l5 4V5L7 9H3zm13.5 3a4.5 4.5 0 0 0-2.5-4.03v8.05A4.5 4.5 0 0 0 16.5 12zM14 3.23v2.06a7 7 0 0 1 0 13.42v2.06a9 9 0 0 0 0-17.54z'/></svg>")}
      .toggle:disabled{opacity:.45}
      .close{width:28px;height:28px;padding:0;border:0;border-radius:50%;background:#172033;color:#fff;
        font:700 16px/28px system-ui,sans-serif;flex:none}
      .hidden{display:none}
      .show-again{display:none;position:fixed;z-index:2147483646;left:12px;
        bottom:max(18px, env(safe-area-inset-bottom));min-height:40px;padding:0 14px;border-radius:14px;
        border:1px solid #5eead4;background:#07111ef2;color:#e7fbff;font:700 13px/40px system-ui,sans-serif}
      :host(.voice-hidden) .box{display:none !important}
      :host(.voice-hidden) .show-again{display:inline-block}
    </style>
    <button class="show-again" type="button">Show Sala</button>
    <div class="box" data-drag-chip="1" title="Drag Salane Voice. Tap the microphone to start or stop.">
      <div class="row">
        <i class="dot"></i>
        <select aria-label="Live audio provider"><option value="">Checking…</option></select>
        <button class="toggle" disabled aria-label="Start live voice">Start live voice</button>
        <div class="copy">
          <span class="voice-name">Salane Voice</span>
          <div class="status">Sala is not connected</div>
        </div>
        <button class="close" title="Hide live audio control" aria-label="Hide live audio control">×</button>
      </div>
      <div class="caption" aria-live="polite"></div>
    </div>`;
  document.body.append(host);

  const $ = (selector) => root.querySelector(selector);
  function syncDock() {
    const dock = document.body.classList.contains("phone-embed")
      || document.body.classList.contains("phone-play")
      || document.body.classList.contains("audio-only");
    $(".box")?.classList.toggle("docked", dock);
  }
  syncDock();
  new MutationObserver(syncDock).observe(document.body, {attributes: true, attributeFilter: ["class"]});
  const select = $("select"), toggle = $(".toggle"), status = $(".status");
  const caption = $(".caption"), dot = $(".dot"), voiceName = $(".voice-name");
  const chip = $(".box");
  $(".close").onclick = (event) => {
    event.stopPropagation();
    stop();
    host.classList.add("voice-hidden");
  };
  $(".show-again").onclick = (event) => {
    event.stopPropagation();
    host.classList.remove("voice-hidden");
  };

  function placeChip(left, top) {
    if (!chip) return;
    const width = chip.offsetWidth || 68;
    const height = chip.offsetHeight || 68;
    const x = Math.max(8, Math.min(window.innerWidth - width - 8, left));
    const y = Math.max(64, Math.min(window.innerHeight - height - 8, top));
    chip.style.left = x + "px";
    chip.style.top = y + "px";
    chip.style.right = "auto";
    chip.style.bottom = "auto";
    chip.classList.add("placed");
    try { localStorage.setItem("aoep.liveAudio.pos", JSON.stringify({left: x, top: y})); } catch (_) {}
  }
  try {
    const saved = JSON.parse(localStorage.getItem("aoep.liveAudio.pos") || "null");
    if (saved && Number.isFinite(saved.left) && Number.isFinite(saved.top)) placeChip(saved.left, saved.top);
  } catch (_) {}
  if (chip) {
    let drag = null;
    chip.addEventListener("pointerdown", (event) => {
      if (event.button !== 0) return;
      if (event.target.closest(".close")) return;
      const rect = chip.getBoundingClientRect();
      drag = {
        id: event.pointerId, x: event.clientX, y: event.clientY,
        left: rect.left, top: rect.top, moved: false,
      };
      chip.classList.add("dragging");
    });
    chip.addEventListener("pointermove", (event) => {
      if (!drag || event.pointerId !== drag.id) return;
      const dx = event.clientX - drag.x;
      const dy = event.clientY - drag.y;
      if (!drag.moved && Math.hypot(dx, dy) < 8) return;
      if (!drag.moved) {
        drag.moved = true;
        try { chip.setPointerCapture(event.pointerId); } catch (_) {}
      }
      placeChip(drag.left + dx, drag.top + dy);
      event.preventDefault();
    });
    const endDrag = (event) => {
      if (!drag || event.pointerId !== drag.id) return;
      const moved = drag.moved;
      drag = null;
      chip.classList.remove("dragging");
      if (!moved) return;
      const swallow = (click) => {
        click.preventDefault();
        click.stopPropagation();
      };
      chip.addEventListener("click", swallow, {capture: true, once: true});
    };
    chip.addEventListener("pointerup", endDrag);
    chip.addEventListener("pointercancel", endDrag);
  }

  function explainStartFailure(error) {
    const raw = String(error?.message || error || "");
    if (/credits|monthly spending|spending limit/i.test(raw)) {
      return "xAI is out of credits for this team, so live Sala cannot start. Use Listen or Hear Sala to play a voice on your speakers.";
    }
    if (/xAI HTTP 403|does not have permission/i.test(raw)) {
      return "xAI refused live Sala. Use Listen or Hear Sala to play a voice on your speakers.";
    }
    return `Could not start live audio: ${raw.slice(0, 220)}`;
  }
  function setStatus(text) {
    const live = Boolean(state.connected);
    const who = live ? "Sala is connected" : "Sala is not connected";
    if (voiceName) voiceName.textContent = "Salane Voice";
    const shown = text ? `${who}. ${text}` : who;
    status.textContent = shown;
    if (!toggle) return;
    toggle.title = shown;
    toggle.setAttribute("aria-label", shown || "Live voice");
  }
  function connectionChime(ok) {
    try {
      const Ctx = window.AudioContext || window.webkitAudioContext;
      if (!Ctx) return;
      const ctx = new Ctx();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "sine";
      osc.frequency.value = ok ? 880 : 196;
      gain.gain.setValueAtTime(0.0001, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.08, ctx.currentTime + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + (ok ? 0.16 : 0.28));
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 0.3);
      osc.onended = () => { void ctx.close(); };
    } catch (_) {}
  }
  function setNativeAudioActive(active) {
    window.__THEODORE_LIVE_AUDIO_ACTIVE__ = Boolean(active);
    if (active && "speechSynthesis" in window) speechSynthesis.cancel();
    window.dispatchEvent(new CustomEvent("theodore-live-audio", {
      detail: {active: Boolean(active), provider: active ? state.provider : ""},
    }));
  }
  function bytesToBase64(bytes) {
    let out = "";
    const step = 0x8000;
    for (let i = 0; i < bytes.length; i += step) {
      out += String.fromCharCode(...bytes.subarray(i, i + step));
    }
    return btoa(out);
  }
  function pcm16Base64(samples) {
    const pcm = new Int16Array(samples.length);
    for (let i = 0; i < samples.length; i++) {
      const value = Math.max(-1, Math.min(1, samples[i]));
      pcm[i] = value < 0 ? value * 32768 : value * 32767;
    }
    return bytesToBase64(new Uint8Array(pcm.buffer));
  }
  function resample(input, sourceRate, targetRate) {
    if (sourceRate === targetRate) return input;
    const ratio = sourceRate / targetRate;
    const out = new Float32Array(Math.max(1, Math.floor(input.length / ratio)));
    for (let i = 0; i < out.length; i++) {
      const start = Math.floor(i * ratio);
      const end = Math.min(input.length, Math.floor((i + 1) * ratio));
      let sum = 0;
      for (let j = start; j < end; j++) sum += input[j];
      out[i] = sum / Math.max(1, end - start);
    }
    return out;
  }
  function clearPlayback() {
    for (const source of state.playing) {
      try { source.stop(); } catch (_) {}
    }
    state.playing.clear();
    state.nextPlayAt = state.ctx?.currentTime || 0;
  }
  function noteAgentSpeaking() {
    if (!state.agentSpeaking) {
      state.agentSpeaking = true;
      window.dispatchEvent(new CustomEvent("theodore-live-audio-speech", {
        detail: {speaking: true, text: caption.textContent || ""},
      }));
    }
    clearTimeout(state.speechEndTimer);
    state.speechEndTimer = setTimeout(() => {
      if (state.playing.size) return;
      state.agentSpeaking = false;
      state.voiceLevel = 0;
      window.dispatchEvent(new CustomEvent("theodore-live-audio-level", {
        detail: {level: 0},
      }));
      window.dispatchEvent(new CustomEvent("theodore-live-audio-speech", {
        detail: {speaking: false, text: ""},
      }));
    }, 700);
  }
  let lastCommandKey = "";
  let lastCommandAt = 0;
  function noteUtterance(role, text) {
    const said = String(text || "").trim();
    if (!said) return;
    if (role === "user") state.lastUserAt = Date.now();
    const intent = typeof aoepLiveAudioIntent === "function"
      ? aoepLiveAudioIntent(said, role)
      : null;
    window.dispatchEvent(new CustomEvent("theodore-live-audio-utterance", {
      detail: {role, text: said, command: Boolean(intent)},
    }));
    if (!intent) return;
    // The learner's request and the agent's reply often use the same words.
    // One screen change covers both.
    const key = intent.action + "\n" + (intent.target || "");
    const now = Date.now();
    if (key === lastCommandKey && now - lastCommandAt < 1600) return;
    lastCommandKey = key;
    lastCommandAt = now;
    window.dispatchEvent(new CustomEvent("theodore-live-audio-action", {
      detail: {
        action: intent.action,
        target: intent.target || "",
        role: role,
        text: said,
      },
    }));
  }
  function noteMic(float32) {
    let sum = 0;
    let n = 0;
    for (let i = 0; i < float32.length; i += 8) {
      sum += float32[i] * float32[i];
      n += 1;
    }
    const rms = Math.sqrt(sum / Math.max(1, n));
    state.micRms = state.micRms * 0.65 + rms * 0.35;
  }
  function userIsLoud() { return state.micRms >= 0.035; }
  function noteUserTalking(talking) {
    const next = Boolean(talking);
    if (state.userTalking === next) return;
    state.userTalking = next;
    window.dispatchEvent(new CustomEvent("theodore-live-audio-user", {
      detail: {talking: next},
    }));
  }
  function publishLevel(level) {
    state.voiceLevel = Math.max(0, Math.min(1, level));
    if (state.levelTimer) return;
    state.levelTimer = setTimeout(() => {
      state.levelTimer = null;
      window.dispatchEvent(new CustomEvent("theodore-live-audio-level", {
        detail: {level: state.voiceLevel},
      }));
    }, 50);
  }
  function beginInterrupt() {
    if (state.recognitionPaused) return;
    // The agent's own voice can trip server VAD. Only a louder mic is the learner.
    if (state.playing.size && !userIsLoud()) return;
    state.dropOutput = true;
    clearPlayback();
    noteUserTalking(true);
  }
  function acceptAgentAudio() {
    if (state.recognitionPaused) return;
    state.dropOutput = false;
    noteUserTalking(false);
    void followSpeakers();
  }
  function playPcm(base64, rate = state.outputRate) {
    if (!state.ctx || !base64 || state.recognitionPaused || state.dropOutput) return;
    const raw = atob(base64);
    const bytes = new Uint8Array(raw.length);
    for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
    const pcm = new Int16Array(bytes.buffer, bytes.byteOffset, Math.floor(bytes.byteLength / 2));
    if (!pcm.length || state.dropOutput) return;
    const floats = new Float32Array(pcm.length);
    for (let i = 0; i < pcm.length; i++) floats[i] = pcm[i] / 32768;
    let energy = 0;
    for (let i = 0; i < floats.length; i += 16) energy += floats[i] * floats[i];
    publishLevel(Math.min(1, Math.sqrt(energy / Math.max(1, Math.floor(floats.length / 16))) * 5));
    const buffer = state.ctx.createBuffer(1, floats.length, rate);
    buffer.copyToChannel(floats, 0);
    const source = state.ctx.createBufferSource();
    source.buffer = buffer;
    source.connect(state.outputGain || state.ctx.destination);
    // Scheduling chunks on one continuous timeline prevents per-chunk clicks,
    // overlap, and the stammering heard when each TTS/audio chunk calls play().
    const at = Math.max(state.ctx.currentTime + 0.025, state.nextPlayAt);
    source.start(at);
    state.nextPlayAt = at + buffer.duration;
    state.playing.add(source);
    source.onended = () => state.playing.delete(source);
    noteAgentSpeaking();
  }
  function sendMic(float32) {
    noteMic(float32);
    if (state.recognitionPaused) return;
    if (state.ws?.readyState !== WebSocket.OPEN || !state.connected) return;
    const pcm = pcm16Base64(resample(float32, state.ctx.sampleRate, state.inputRate));
    if (state.provider === "xai") {
      state.ws.send(JSON.stringify({type:"input_audio_buffer.append",audio:pcm}));
    } else {
      state.ws.send(JSON.stringify({realtimeInput:{audio:{
        data:pcm,mimeType:`audio/pcm;rate=${state.inputRate}`
      }}}));
    }
  }
  const BLUETOOTH_INPUT = /bluetooth|airpod|headset|hands-free|handset|beats|bose/i;
  function micConstraints(deviceId) {
    // autoGainControl pumps the mic and ducks speaker volume. Leave it off.
    // echoCancellation stays on so a laptop mic does not howl through speakers.
    const audio = {
      echoCancellation:true,noiseSuppression:true,autoGainControl:false,channelCount:1,
    };
    if (deviceId) audio.deviceId = {exact: deviceId};
    return {audio, video:false};
  }
  async function openSpeakerSafeMic() {
    // Opening the mic on a Bluetooth speaker switches it from music playback
    // (A2DP) to a phone-call profile. That profile is quiet, mono, and drops
    // out. Prefer the computer's own microphone and leave the speakers alone.
    let stream = await navigator.mediaDevices.getUserMedia(micConstraints());
    let inputs = [];
    try {
      const devices = await navigator.mediaDevices.enumerateDevices();
      inputs = devices.filter((device) => device.kind === "audioinput" && device.deviceId);
    } catch (_) {}
    const track = stream.getAudioTracks()[0];
    const activeId = track?.getSettings?.().deviceId || "";
    const label = (inputs.find((device) => device.deviceId === activeId)?.label) || track?.label || "";
    if (!BLUETOOTH_INPUT.test(label)) return stream;
    const builtin = inputs.find((device) => {
      if (!device.deviceId || device.deviceId === "default" || device.deviceId === "communications") return false;
      return !BLUETOOTH_INPUT.test(device.label || "");
    });
    if (!builtin) return stream;
    stream.getTracks().forEach((item) => item.stop());
    try {
      return await navigator.mediaDevices.getUserMedia(micConstraints(builtin.deviceId));
    } catch (_) {
      return navigator.mediaDevices.getUserMedia(micConstraints());
    }
  }
  function speakerStatus() {
    const label = state.stream?.getAudioTracks?.()[0]?.label || "";
    const base = "You can interrupt. Theodore stops, listens, then answers at full volume.";
    if (!label) return base;
    if (BLUETOOTH_INPUT.test(label)) {
      return base + " This microphone is the Bluetooth device, so those speakers may get quieter.";
    }
    return base + " The computer microphone is on, so Bluetooth speakers stay loud.";
  }
  function playbackGain() {
    // A phone speaker with the mic open is much quieter than a laptop.
    // Lift only that case. Desktop stays at unity so a room is not blasted.
    const edge = Math.min(window.innerWidth || 1200, window.innerHeight || 1200);
    const touch = (navigator.maxTouchPoints || 0) > 0;
    return edge <= 900 && touch ? 2.6 : 1;
  }
  function wirePlayback() {
    state.outputGain = state.ctx.createGain();
    state.outputGain.gain.value = playbackGain();
    state.outputComp = state.ctx.createDynamicsCompressor();
    state.outputComp.threshold.value = -10;
    state.outputComp.knee.value = 8;
    state.outputComp.ratio.value = 3;
    state.outputComp.attack.value = 0.003;
    state.outputComp.release.value = 0.2;
    state.outputGain.connect(state.outputComp);
    state.outputComp.connect(state.ctx.destination);
  }
  async function followSpeakers() {
    if (!state.ctx) return;
    if (state.outputGain) state.outputGain.gain.value = playbackGain();
    if (typeof state.ctx.setSinkId === "function") {
      try { await state.ctx.setSinkId(""); } catch (_) {}
    }
    try { await state.ctx.resume(); } catch (_) {}
  }
  async function startMic() {
    state.stream = await openSpeakerSafeMic();
    state.source = state.ctx.createMediaStreamSource(state.stream);
    // Pull the mic graph without mixing it into the speakers. A zero-gain
    // connection to the speakers still makes Bluetooth duck the lesson.
    state.micSink = state.ctx.createMediaStreamDestination();
    if (state.ctx.audioWorklet) {
      const worklet = `
        class TheodoreMic extends AudioWorkletProcessor {
          process(inputs) {
            const channel = inputs[0] && inputs[0][0];
            if (channel && channel.length) this.port.postMessage(channel.slice());
            return true;
          }
        }
        registerProcessor("theodore-mic", TheodoreMic);`;
      const url = URL.createObjectURL(new Blob([worklet], {type:"application/javascript"}));
      try {
        await state.ctx.audioWorklet.addModule(url);
        state.processor = new AudioWorkletNode(state.ctx, "theodore-mic");
        state.processor.port.onmessage = (event) => sendMic(new Float32Array(event.data));
      } catch (_) {
        state.processor = state.ctx.createScriptProcessor(2048, 1, 1);
        state.processor.onaudioprocess = (event) => {
          sendMic(new Float32Array(event.inputBuffer.getChannelData(0)));
        };
      } finally {
        URL.revokeObjectURL(url);
      }
    } else {
      // Old WebViews only. Modern Chrome/Safari use the non-blocking worklet.
      state.processor = state.ctx.createScriptProcessor(2048, 1, 1);
      state.processor.onaudioprocess = (event) => {
        sendMic(new Float32Array(event.inputBuffer.getChannelData(0)));
      };
    }
    state.source.connect(state.processor);
    state.processor.connect(state.micSink);
  }
  function handleXai(event) {
    const type = String(event.type || "");
    if (type === "session.updated") state.connected = true;
    if (type === "input_audio_buffer.speech_started") {
      state.lastUserAt = Date.now();
      beginInterrupt();
    }
    if (type === "input_audio_buffer.speech_stopped" || type === "input_audio_buffer.committed") {
      acceptAgentAudio();
    }
    if (type === "response.created") acceptAgentAudio();
    if (type === "response.output_audio.delta" || type === "response.audio.delta") {
      playPcm(String(event.delta || ""));
    }
    if (type.includes("transcript") && event.delta) caption.textContent += String(event.delta);
    if (type.endsWith("transcript.done") || type.endsWith("transcription.completed")) {
      const said = String(event.transcript || event.text || caption.textContent);
      caption.textContent = said;
      const role = type.includes("input") ? "user" : "agent";
      noteUtterance(role, said);
    }
  }
  function handleGemini(event) {
    if (event.setupComplete !== undefined) state.connected = true;
    const server = event.serverContent || {};
    if (server.interrupted) {
      beginInterrupt();
      if (!server.modelTurn) return;
    }
    if (server.modelTurn?.parts?.length) state.dropOutput = false;
    for (const part of server.modelTurn?.parts || []) {
      if (part.inlineData?.data) playPcm(part.inlineData.data, 24000);
    }
    if (server.inputTranscription?.text) {
      caption.textContent = `You: ${server.inputTranscription.text}`;
      noteUtterance("user", server.inputTranscription.text);
    }
    if (server.outputTranscription?.text) {
      caption.textContent = `Theodore: ${server.outputTranscription.text}`;
      noteUtterance("agent", server.outputTranscription.text);
    }
    if (event.error?.message) setStatus(`Gemini Live error: ${event.error.message}`);
    if (event.goAway) setStatus("Gemini Live session is ending; stop and reconnect.");
  }
  let localRec = null;
  function stopLocalRec() {
    const rec = localRec;
    localRec = null;
    try { rec?.abort(); } catch (_) { try { rec?.stop(); } catch (_) {} }
  }
  function startLocalSala() {
    const Rec = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!Rec) {
      setStatus("This browser has no speech recognition. Use Ask Sala on the Dialects tab.");
      return false;
    }
    stopLocalRec();
    localRec = new Rec();
    localRec.lang = window.AOEP_SALA_LOCALE || document.documentElement.lang || "en-US";
    localRec.interimResults = false;
    localRec.continuous = false;
    state.connected = true;
    state.provider = "sala";
    toggle.classList.add("live");
    dot.classList.add("on");
    toggle.disabled = false;
    caption.textContent = "";
    setStatus("Listening. Speak, then pause.");
    localRec.onresult = (event) => {
      const said = String(event.results?.[0]?.[0]?.transcript || "").trim();
      if (!said) {
        state.connected = false;
        toggle.classList.remove("live");
        dot.classList.remove("on");
        setStatus("Did not catch that. Try again.");
        return;
      }
      caption.textContent = `You: ${said}`;
      setStatus("Heard you. Sala is replying.");
      window.dispatchEvent(new CustomEvent("theodore-sala-heard", { detail: { text: said } }));
    };
    localRec.onerror = (event) => {
      state.connected = false;
      toggle.classList.remove("live");
      dot.classList.remove("on");
      const denied = event?.error === "not-allowed";
      setStatus(denied
        ? "Microphone permission was blocked."
        : "Could not hear you. Use Ask Sala on the Dialects tab.");
    };
    try {
      localRec.start();
      return true;
    } catch (_) {
      state.connected = false;
      toggle.classList.remove("live");
      dot.classList.remove("on");
      setStatus("Could not start the microphone.");
      return false;
    }
  }
  async function start() {
    const provider = select.value;
    if (!provider || provider === "sala") return startLocalSala();
    toggle.disabled = true;
    setStatus(`Connecting ${select.selectedOptions[0].textContent}…`);
    try {
      state.provider = provider;
      state.inputRate = provider === "xai" ? 24000 : 16000;
      state.outputRate = 24000;
      // Ask for the microphone before minting a short-lived token. An adult
      // may leave the permission sheet open, otherwise wasting the credential.
      // Do not lock this context to 16 kHz or 24 kHz. Bluetooth speakers play
      // music at 48 kHz; a phone-call rate makes them quiet and choppy. The
      // mic is resampled down to the agent rate below.
      state.ctx = new AudioContext({latencyHint:"playback"});
      await state.ctx.resume();
      wirePlayback();
      await startMic();
      await followSpeakers();
      const pageLang = (document.documentElement.lang || "").trim();
      const response = await fetch(liveAudioUrl("/api/live-audio/token"), {
        method:"POST",headers:{"content-type":"application/json"},
        body:JSON.stringify({
          provider,
          language: pageLang,
        }),
      });
      if (!response.ok) throw new Error((await response.text()).slice(0, 240));
      const config = await response.json();
      if (config.use_xai === false) {
        await stop(config.hint || "This language uses the lesson voice, not Grok.");
        return false;
      }
      state.inputRate = Number(config.input_rate) || (provider === "xai" ? 24000 : 16000);
      state.outputRate = Number(config.output_rate) || 24000;
      state.ws = provider === "xai"
        ? new WebSocket(config.websocket_url, [config.websocket_protocol])
        : new WebSocket(config.websocket_url);
      state.ws.onopen = () => {
        setNativeAudioActive(true);
        state.recognitionPaused = false;
        window.__THEODORE_LIVE_AUDIO_HOLD__ = false;
        armIdleWatch();
        state.ws.send(JSON.stringify(config.setup));
        toggle.disabled = false; toggle.textContent = "Stop live voice";
        toggle.classList.add("live"); dot.classList.add("on");
        setStatus(speakerStatus());
        connectionChime(true);
      };
      state.ws.onmessage = (message) => {
        try {
          const event = JSON.parse(message.data);
          provider === "xai" ? handleXai(event) : handleGemini(event);
        } catch (_) {}
      };
      state.ws.onerror = () => {
        connectionChime(false);
        setStatus("Live audio connection error. Check provider key/network.");
      };
      state.ws.onclose = () => {
        if (!state.stopping) {
          connectionChime(false);
          stop("Live audio disconnected.");
        }
      };
      return true;
    } catch (error) {
      await stop(explainStartFailure(error));
      return false;
    }
  }
  function setRecognitionPaused(paused) {
    state.recognitionPaused = Boolean(paused);
    window.__THEODORE_LIVE_AUDIO_HOLD__ = state.recognitionPaused;
    if (state.recognitionPaused) {
      state.dropOutput = true;
      state.agentSpeaking = false;
      if (state.outputGain) state.outputGain.gain.value = 0;
      clearPlayback();
      if (state.ws && state.ws.readyState === WebSocket.OPEN && state.provider === "xai") {
        try { state.ws.send(JSON.stringify({ type: "response.cancel" })); } catch (_) {}
      }
      window.dispatchEvent(new CustomEvent("theodore-live-audio-speech", {
        detail: {speaking: false, text: ""},
      }));
    } else {
      state.dropOutput = false;
      if (state.outputGain) state.outputGain.gain.value = playbackGain();
      state.lastUserAt = Date.now();
    }
    window.dispatchEvent(new CustomEvent("theodore-live-audio", {
      detail: {
        active: Boolean(state.connected),
        paused: state.recognitionPaused,
        provider: state.connected ? state.provider : "",
      },
    }));
  }
  function armIdleWatch() {
    clearInterval(state.idleTimer);
    state.lastUserAt = Date.now();
    state.idleTimer = setInterval(() => {
      if (!state.connected || state.recognitionPaused) return;
      if (Date.now() - state.lastUserAt < 60000) return;
      state.lastUserAt = Date.now();
      window.dispatchEvent(new CustomEvent("theodore-live-audio-idle", {
        detail: {silent_ms: 60000},
      }));
    }, 5000);
  }
  async function stop(message = "Live audio off. Lab TTS/device speech may resume.") {
    state.stopping = true;
    stopLocalRec();
    clearInterval(state.idleTimer);
    state.idleTimer = null;
    setNativeAudioActive(false);
    state.recognitionPaused = false;
    window.__THEODORE_LIVE_AUDIO_HOLD__ = false;
    clearPlayback();
    try { state.processor?.disconnect(); } catch (_) {}
    try { state.source?.disconnect(); } catch (_) {}
    try { state.micSink?.disconnect(); } catch (_) {}
    try { state.silent?.disconnect(); } catch (_) {}
    for (const track of state.stream?.getTracks?.() || []) track.stop();
    if (state.provider === "gemini" && state.ws?.readyState === WebSocket.OPEN) {
      try { state.ws.send(JSON.stringify({realtimeInput:{audioStreamEnd:true}})); } catch (_) {}
    }
    try { state.ws?.close(); } catch (_) {}
    try { state.outputGain?.disconnect(); } catch (_) {}
    try { state.outputComp?.disconnect(); } catch (_) {}
    try { await state.ctx?.close(); } catch (_) {}
    Object.assign(state, {
      ws:null,stream:null,source:null,processor:null,silent:null,micSink:null,ctx:null,
      outputGain:null,outputComp:null,connected:false,nextPlayAt:0,
      stopping:false,dropOutput:false,micRms:0,voiceLevel:0,userTalking:false,
    });
    toggle.textContent = "Start live voice"; toggle.classList.remove("live");
    dot.classList.remove("on"); toggle.disabled = !select.value; setStatus(message);
  }
  function noteActivity(detail) {
    const prompt = String(detail && detail.prompt || "").trim();
    if (state.recognitionPaused) return;
    if (!prompt || !state.ws || state.ws.readyState !== WebSocket.OPEN) return;
    const key = String((detail && detail.id) || prompt);
    const now = Date.now();
    const force = Boolean(detail && detail.force);
    // Same activity id within 2.5s is a duplicate. A new id (new rhyme word,
    // next slide) must always replace the previous target immediately.
    if (!force && key === state.activityKey && now - state.activityAt < 2500) return;
    state.activityKey = key;
    state.activityAt = now;
    const line = prompt.slice(0, 1800);
    if (state.provider === "gemini") {
      // Drop any in-flight model turn so a stale prompt cannot finish speaking.
      try {
        state.ws.send(JSON.stringify({clientContent: {turns: [], turnComplete: true}}));
      } catch (_) {}
      clearPlayback();
      state.ws.send(JSON.stringify({
        clientContent: {
          turns: [{role: "user", parts: [{text:
            "The activity on screen just changed. Use only this current activity. "
            + "Ignore earlier words or prompts. " + line}]}],
          turnComplete: true,
        },
      }));
      return;
    }
    // Cancel the previous response, then lock session instructions to the
    // on-screen activity so a celebrate turn cannot keep asking for the old word.
    try { state.ws.send(JSON.stringify({ type: "response.cancel" })); } catch (_) {}
    clearPlayback();
    state.dropOutput = false;
    try {
      state.ws.send(JSON.stringify({
        type: "session.update",
        session: {
          instructions: (
            "You are Theodore, a warm teacher. The on-screen activity is authoritative. "
            + "Coach only that activity. Never ask for a previous target word or prompt. "
            + "Keep turns short. Do not reveal the answer.\n\n"
            + "Current activity on screen:\n" + line
          ),
        },
      }));
    } catch (_) {}
    state.ws.send(JSON.stringify({
      type: "response.create",
      response: {instructions: line},
    }));
  }
  window.TheodoreLiveAudio = {
    pauseRecognition() { setRecognitionPaused(true); },
    resumeRecognition() { if (state.connected) setRecognitionPaused(false); },
    openMic() { return openSpeakerSafeMic(); },
    noteActivity(detail) { noteActivity(detail); },
    setHidden(hidden) {
      host.classList.toggle("voice-hidden", Boolean(hidden));
      if (hidden && state.ws) stop("Live audio off.");
    },
    start() {
      if (state.ws || localRec) return Promise.resolve(true);
      return start();
    },
    stop() { return stop(); },
    showReply(text) {
      caption.textContent = `Sala: ${text || ""}`;
      state.connected = true;
      setStatus("Playing the reply on your speakers.");
    },
    finishReply() {
      state.connected = false;
      toggle.classList.remove("live");
      dot.classList.remove("on");
      setStatus("Reply finished. Tap the microphone to talk again.");
    },
  };
  navigator.mediaDevices?.addEventListener?.("devicechange", () => { void followSpeakers(); });
  toggle.onclick = () => (state.ws || localRec) ? stop() : start();
  select.onchange = () => { if (state.ws || localRec) stop(); toggle.disabled = !select.value; };

  fetch(liveAudioUrl("/api/live-audio/status"), {cache:"no-store"}).then(async (response) => {
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    select.innerHTML = "";
    const providers = data.providers || {};
    const ready = Object.entries(providers).filter(([, row]) => row.available);
    if (!ready.length) {
      const option = document.createElement("option");
      option.value = "sala";
      option.textContent = "Salane Voice";
      select.append(option);
      select.value = "sala";
      toggle.disabled = false;
      setStatus("Tap the microphone, speak, then pause. Sala replies in the dialect selected on this page.");
      return;
    }
    for (const [id, row] of ready) {
      const option = document.createElement("option");
      option.value = id; option.textContent = row.label || id;
      if (id === data.default) option.selected = true;
      select.append(option);
    }
    toggle.disabled = !select.value;
    setStatus(data.note || "Tap the microphone to talk to Sala.");
  }).catch((error) => {
    select.innerHTML = '<option value="">Live audio unavailable</option>';
    setStatus(`Live audio status failed: ${error.message}`);
  });
})();

(() => {
  "use strict";

  // One native speech-to-speech control shared by every Theodore lab. It never
  // calls /tts: microphone PCM goes directly to xAI/Gemini using a one-use
  // server-minted credential, and returned PCM is scheduled gaplessly.
  const state = {
    ws: null, stream: null, source: null, processor: null, silent: null,
    ctx: null, speaker: null, playDestination: null, provider: "",
    inputRate: 16000, outputRate: 24000, nextPlayAt: 0, playing: new Set(),
    connected: false, stopping: false, dropOutput: false,
  };

  const host = document.createElement("div");
  host.id = "theodore-live-audio";
  const root = host.attachShadow({ mode: "open" });
  root.innerHTML = `
    <style>
      :host{all:initial} .box{position:fixed;z-index:2147483646;right:14px;bottom:14px;
        width:min(330px,calc(100vw - 28px));padding:10px;border:1px solid #5eead4;
        border-radius:16px;background:#07111ef2;color:#f8fafc;box-shadow:0 16px 45px #0009;
        font:700 13px/1.3 system-ui,sans-serif}
      .row{display:flex;align-items:center;gap:8px}.title{flex:1;color:#5eead4;font-weight:900}
      select,button{border:1px solid #ffffff55;border-radius:10px;background:#172033;color:#fff;
        padding:7px 9px;font:inherit}button{cursor:pointer}.live{background:#047857}
      .dot{width:9px;height:9px;border-radius:50%;background:#64748b}.dot.on{background:#34d399;
        box-shadow:0 0 12px #34d399}.status{margin-top:7px;color:#cbd5e1;font-size:11px}
      .caption{margin-top:5px;max-height:42px;overflow:auto;color:#fde68a;font-weight:600}
      .hidden{display:none}.close{padding:3px 7px;background:transparent}
    </style>
    <div class="box">
      <div class="row"><i class="dot"></i><span class="title">Live audio agent</span>
        <button class="close" title="Hide live audio control">×</button></div>
      <div class="row" style="margin-top:8px">
        <select aria-label="Live audio provider"><option value="">Checking…</option></select>
        <button class="toggle" disabled>Start live voice</button>
      </div>
      <div class="status">Checking native audio providers…</div>
      <div class="caption" aria-live="polite"></div>
    </div>`;
  document.body.append(host);

  const $ = (selector) => root.querySelector(selector);
  const select = $("select"), toggle = $(".toggle"), status = $(".status");
  const caption = $(".caption"), dot = $(".dot");
  $(".close").onclick = () => { stop(); host.remove(); };

  function setStatus(text) { status.textContent = text; }
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
  function playPcm(base64, rate = state.outputRate) {
    if (!state.ctx || !base64) return;
    const raw = atob(base64);
    const bytes = new Uint8Array(raw.length);
    for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
    const pcm = new Int16Array(bytes.buffer, bytes.byteOffset, Math.floor(bytes.byteLength / 2));
    if (!pcm.length || state.dropOutput) return;
    const floats = new Float32Array(pcm.length);
    for (let i = 0; i < pcm.length; i++) floats[i] = pcm[i] / 32768;
    const buffer = state.ctx.createBuffer(1, floats.length, rate);
    buffer.copyToChannel(floats, 0);
    const source = state.ctx.createBufferSource();
    source.buffer = buffer;
    source.connect(state.playDestination || state.ctx.destination);
    // Scheduling chunks on one continuous timeline prevents per-chunk clicks,
    // overlap, and the stammering heard when each TTS/audio chunk calls play().
    const at = Math.max(state.ctx.currentTime + 0.025, state.nextPlayAt);
    source.start(at);
    state.nextPlayAt = at + buffer.duration;
    state.playing.add(source);
    source.onended = () => state.playing.delete(source);
  }
  function sendMic(float32) {
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
  async function startMic() {
    state.stream = await navigator.mediaDevices.getUserMedia({
      audio:{echoCancellation:true,noiseSuppression:true,autoGainControl:true},
      video:false,
    });
    state.source = state.ctx.createMediaStreamSource(state.stream);
    state.silent = state.ctx.createGain();
    state.silent.gain.value = 0;
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
    // ScriptProcessor must be connected to run; zero gain prevents mic echo.
    state.processor.connect(state.silent);
    state.silent.connect(state.ctx.destination);
  }
  function handleXai(event) {
    const type = String(event.type || "");
    if (type === "session.updated") state.connected = true;
    if (type === "input_audio_buffer.speech_started") {
      state.dropOutput = true; clearPlayback(); // true barge-in
    }
    if (type === "response.created") state.dropOutput = false;
    if (type === "response.output_audio.delta" || type === "response.audio.delta") {
      playPcm(String(event.delta || ""));
    }
    if (type.includes("transcript") && event.delta) caption.textContent += String(event.delta);
    if (type.endsWith("transcript.done")) caption.textContent = String(event.transcript || event.text || caption.textContent);
  }
  function handleGemini(event) {
    if (event.setupComplete !== undefined) state.connected = true;
    const server = event.serverContent || {};
    if (server.interrupted) {
      state.dropOutput = true; clearPlayback(); return;
    }
    if (server.modelTurn?.parts?.length) state.dropOutput = false;
    for (const part of server.modelTurn?.parts || []) {
      if (part.inlineData?.data) playPcm(part.inlineData.data, 24000);
    }
    if (server.inputTranscription?.text) caption.textContent = `You: ${server.inputTranscription.text}`;
    if (server.outputTranscription?.text) caption.textContent = `Theodore: ${server.outputTranscription.text}`;
    if (event.error?.message) setStatus(`Gemini Live error: ${event.error.message}`);
    if (event.goAway) setStatus("Gemini Live session is ending; stop and reconnect.");
  }
  async function start() {
    const provider = select.value;
    if (!provider) return;
    toggle.disabled = true;
    setStatus(`Connecting ${select.selectedOptions[0].textContent}…`);
    try {
      state.provider = provider;
      state.inputRate = provider === "xai" ? 24000 : 16000;
      state.outputRate = 24000;
      // Ask for the microphone before minting a short-lived token. An adult
      // may leave the permission sheet open, otherwise wasting the credential.
      try {
        state.ctx = new AudioContext({
          latencyHint:"interactive", sampleRate:state.inputRate,
        });
      } catch (_) {
        state.ctx = new AudioContext({latencyHint:"interactive"});
      }
      await state.ctx.resume();
      state.playDestination = state.ctx.createMediaStreamDestination();
      state.speaker = new Audio();
      state.speaker.autoplay = true;
      state.speaker.srcObject = state.playDestination.stream;
      await state.speaker.play().catch(() => {});
      await startMic();
      const response = await fetch("/api/live-audio/token", {
        method:"POST",headers:{"content-type":"application/json"},
        body:JSON.stringify({
          provider,
        }),
      });
      if (!response.ok) throw new Error((await response.text()).slice(0, 240));
      const config = await response.json();
      state.inputRate = Number(config.input_rate) || (provider === "xai" ? 24000 : 16000);
      state.outputRate = Number(config.output_rate) || 24000;
      state.ws = provider === "xai"
        ? new WebSocket(config.websocket_url, [config.websocket_protocol])
        : new WebSocket(config.websocket_url);
      state.ws.onopen = () => {
        setNativeAudioActive(true);
        state.ws.send(JSON.stringify(config.setup));
        toggle.disabled = false; toggle.textContent = "Stop live voice";
        toggle.classList.add("live"); dot.classList.add("on");
        setStatus("Mic → native audio agent → speaker. TTS is off.");
      };
      state.ws.onmessage = (message) => {
        try {
          const event = JSON.parse(message.data);
          provider === "xai" ? handleXai(event) : handleGemini(event);
        } catch (_) {}
      };
      state.ws.onerror = () => setStatus("Live audio connection error. Check provider key/network.");
      state.ws.onclose = () => { if (!state.stopping) stop("Live audio disconnected."); };
    } catch (error) {
      await stop(`Could not start live audio: ${error?.message || error}`);
    }
  }
  async function stop(message = "Live audio off. Lab TTS/device speech may resume.") {
    state.stopping = true;
    setNativeAudioActive(false);
    clearPlayback();
    try { state.processor?.disconnect(); } catch (_) {}
    try { state.source?.disconnect(); } catch (_) {}
    try { state.silent?.disconnect(); } catch (_) {}
    for (const track of state.stream?.getTracks?.() || []) track.stop();
    if (state.provider === "gemini" && state.ws?.readyState === WebSocket.OPEN) {
      try { state.ws.send(JSON.stringify({realtimeInput:{audioStreamEnd:true}})); } catch (_) {}
    }
    try { state.ws?.close(); } catch (_) {}
    try { state.speaker?.pause(); state.speaker.srcObject = null; } catch (_) {}
    for (const track of state.playDestination?.stream?.getTracks?.() || []) track.stop();
    try { await state.ctx?.close(); } catch (_) {}
    Object.assign(state, {
      ws:null,stream:null,source:null,processor:null,silent:null,ctx:null,
      speaker:null,playDestination:null,connected:false,nextPlayAt:0,
      stopping:false,dropOutput:false,
    });
    toggle.textContent = "Start live voice"; toggle.classList.remove("live");
    dot.classList.remove("on"); toggle.disabled = !select.value; setStatus(message);
  }
  toggle.onclick = () => state.ws ? stop() : start();
  select.onchange = () => { if (state.ws) stop(); toggle.disabled = !select.value; };

  fetch("/api/live-audio/status", {cache:"no-store"}).then(async (response) => {
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    select.innerHTML = '<option value="">Choose live agent</option>';
    for (const [id, row] of Object.entries(data.providers || {})) {
      const option = document.createElement("option");
      option.value = id; option.textContent = row.label || id;
      option.disabled = !row.available;
      if (id === data.default && row.available) option.selected = true;
      select.append(option);
    }
    toggle.disabled = !select.value;
    setStatus(data.note || "Choose a native speech-to-speech agent.");
  }).catch((error) => {
    select.innerHTML = '<option value="">Live audio unavailable</option>';
    setStatus(`Live audio status failed: ${error.message}`);
  });
})();

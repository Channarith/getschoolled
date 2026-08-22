"""Self-contained browser UI for webcam/microphone realtime translation."""

from __future__ import annotations


CSS = r"""
:root { color-scheme: dark; --bg:#08111f; --panel:#101d30; --line:#263d5c;
  --text:#e8f2ff; --muted:#94abc7; --accent:#24c8a5; --blue:#4f9cf9;
  --warn:#f4b942; --bad:#ff7272; }
* { box-sizing:border-box; }
body { margin:0; background:radial-gradient(circle at 15% 0,#173251,var(--bg) 42%);
  color:var(--text); font:15px/1.45 Inter,system-ui,sans-serif; min-height:100vh; }
header { padding:22px 26px 18px; border-bottom:1px solid var(--line); background:#08111fdd; }
h1 { margin:0; font-size:27px; } header p { margin:5px 0 0; color:var(--muted); }
.grid { display:grid; grid-template-columns:minmax(330px,.9fr) minmax(380px,1.1fr);
  gap:14px; padding:14px; max-width:1500px; margin:auto; }
@media(max-width:900px){.grid{grid-template-columns:1fr}}
.panel { background:var(--panel); border:1px solid var(--line); border-radius:14px; padding:14px; }
.panel h2 { margin:0 0 10px; font-size:17px; color:#b6d8ff; }
.row { display:flex; gap:8px; align-items:center; flex-wrap:wrap; margin:8px 0; }
label { color:var(--muted); font-size:12px; }
select,input,textarea,button { font:inherit; }
select,input,textarea { color:var(--text); background:#081423; border:1px solid var(--line);
  border-radius:8px; padding:7px 9px; }
select { min-width:150px; } input.grow { flex:1; min-width:180px; }
button { color:#04261f; background:var(--accent); border:0; border-radius:8px;
  font-weight:750; padding:8px 12px; cursor:pointer; }
button.secondary { background:#213955; color:var(--text); border:1px solid #355778; }
button.danger { background:#6d2b37; color:#fff; }
button:disabled { opacity:.45; cursor:not-allowed; }
video { width:100%; aspect-ratio:16/9; border-radius:12px; background:#02060a;
  object-fit:cover; border:1px solid var(--line); }
.statusbar { display:flex; gap:7px; flex-wrap:wrap; margin:9px 0; }
.badge { border:1px solid var(--line); border-radius:999px; padding:3px 8px;
  color:var(--muted); font-size:11px; }
.badge.ok { border-color:#23836f; background:#113a33; color:#9ef5df; }
.badge.warn { border-color:#8b6c2f; background:#40351b; color:#ffe09b; }
.badge.bad { border-color:#7d333a; background:#401d24; color:#ffb2b2; }
.meter { height:12px; background:#06101c; border:1px solid var(--line); border-radius:99px; overflow:hidden; }
.meter>div { height:100%; width:0; background:linear-gradient(90deg,#25c8a6,#f4b942,#ff7272); transition:width .08s; }
.note { padding:9px 10px; background:#0a1728; border-left:3px solid var(--blue);
  border-radius:7px; color:var(--muted); font-size:12px; margin:9px 0; }
.note.warn { border-color:var(--warn); color:#ffe2a4; }
.feed { max-height:570px; overflow:auto; display:flex; flex-direction:column; gap:9px; }
.card { border:1px solid var(--line); border-radius:11px; padding:11px; background:#0b1727; }
.card.interim { opacity:.62; border-style:dashed; }
.theodore-card { border-color:#6d57ba; background:linear-gradient(135deg,#211b43,#101d30); }
.theodore-card .translation { color:#ddd4ff; }
.meta { display:flex; gap:8px; color:var(--muted); font-size:11px; margin-bottom:5px; }
.source { color:#c8d8ec; font-size:13px; }
.translation { font-size:19px; font-weight:650; margin-top:5px; unicode-bidi:plaintext; }
.warning { color:#ffd485; font-size:11px; margin-top:5px; }
.empty { color:var(--muted); text-align:center; padding:55px 12px; }
#manual-text { min-height:60px; width:100%; resize:vertical; }
.privacy { font-size:11px; color:#8ba0b9; }
.connected { color:#8ff4dd; }
"""


JS = r"""
const $ = (id) => document.getElementById(id);
let langs = [];
let stream = null;
let recognition = null;
let recorder = null;
let audioContext = null;
let processedStream = null;
let audioAnalyser = null;
let meterFrame = 0;
let audioPolicy = {
  capture_window_ms:1200, auto_detect_window_ms:2000, highpass_hz:80,
  lowpass_hz:7500, noise_gate_margin_db:9, absolute_gate_db:-48,
  min_speech_ratio:.12, calibration_ms:900,
  compressor:{threshold_db:-30,knee_db:18,ratio:4,attack_s:.003,release_s:.18}
};
let noiseFloorDb = -60;
let gateThresholdDb = -48;
let calibrationValues = [];
let calibrationUntil = 0;
let windowSpeechFrames = 0;
let windowTotalFrames = 0;
let windowPeakDb = -100;
let activeAudioDevice = '';
let deviceListenerInstalled = false;
let serverTurnBuffer = [];
let serverTurnLanguage = 'en';
let socket = null;
let running = false;
let manualStop = false;
let lastInterim = null;
let providerInfo = {};
let captureEpoch = 0;
let activeSourceLanguage = 'es';

function status(text, cls='') {
  $('run-state').textContent = text;
  $('run-state').className = 'badge ' + cls;
}
function esc(text) {
  return String(text ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}
function sessionId() {
  return ($('session-id').value.trim() || 'translation-demo').replace(/[^a-zA-Z0-9_-]/g,'-');
}
function wsBase() { return `${location.protocol==='https:'?'wss':'ws'}://${location.host}`; }

async function api(path, options) {
  const r = await fetch(path, options);
  const body = await r.json().catch(()=>({}));
  if (!r.ok) throw new Error(body.detail || `${r.status} ${r.statusText}`);
  return body;
}

async function loadLanguages() {
  const data = await api('/api/languages'); langs = data.languages || [];
  $('source-lang').innerHTML = `<option value="auto">Auto-detect (server Whisper)</option>` +
    langs.map(l=>`<option value="${l.code}">${esc(l.name)} (${l.code})</option>`).join('');
  $('target-lang').innerHTML = langs.map(l=>`<option value="${l.code}">${esc(l.name)} (${l.code})</option>`).join('');
  $('theodore-lang').innerHTML = '<option value="same">Same as learner</option>' +
    langs.map(l=>`<option value="${l.code}">${esc(l.name)} (${l.code})</option>`).join('');
  const q = new URLSearchParams(location.search);
  $('source-lang').value = q.get('source') || 'es';
  $('target-lang').value = q.get('target') || 'en';
  $('role').value = q.get('role') || 'speaker';
  $('session-id').value = q.get('session') || 'translation-demo';
  activeSourceLanguage = $('source-lang').value;
}

async function loadTheodore() {
  const data=await api('/api/theodore/status');
  $('theodore-state').textContent=data.live_xai_configured?'Theodore: live xAI':'Theodore: teaching fallback';
  $('theodore-state').className='badge '+(data.live_xai_configured?'ok':'warn');
}

async function loadAudioPolicy() {
  audioPolicy = await api('/api/audio-policy');
  $('window-ms').value = String(audioPolicy.capture_window_ms);
  $('filter-state').textContent = `filter: ${audioPolicy.highpass_hz}–${audioPolicy.lowpass_hz}Hz`;
}

async function loadProviders() {
  const p = await api('/api/providers'); providerInfo = p;
  $('asr-state').textContent = p.remote_asr_configured ? 'Whisper: ready' : 'Whisper: not configured';
  $('asr-state').className = 'badge ' + (p.remote_asr_configured?'ok':'warn');
  const translation = p.translation_gateway_configured ? 'NLLB: ready' :
    (p.xai_translation_configured ? 'xAI translate: ready' : 'Translation: phrasebook/source fallback');
  $('mt-state').textContent = translation;
  $('mt-state').className = 'badge ' + ((p.translation_gateway_configured||p.xai_translation_configured)?'ok':'warn');
  $('capture-engine').querySelector('[value=server]').disabled = !p.remote_asr_configured;
  $('auto-note').style.display = p.remote_asr_configured ? 'none' : 'block';
}

async function refreshAudioDevices(requestPermission=false) {
  if(!navigator.mediaDevices?.enumerateDevices) {
    $('device-state').textContent='device selection unsupported'; return;
  }
  let temporary=null;
  if(requestPermission&&!stream) {
    temporary=await navigator.mediaDevices.getUserMedia({audio:true,video:false});
  }
  try {
    const previous=$('audio-device').value;
    const devices=(await navigator.mediaDevices.enumerateDevices()).filter(d=>d.kind==='audioinput');
    const seen=new Set(); const rows=[];
    for(const device of devices) {
      if(!device.deviceId||device.deviceId==='default'||seen.has(device.deviceId)) continue;
      seen.add(device.deviceId); rows.push(device);
    }
    $('audio-device').innerHTML='<option value="">System default microphone</option>'+rows.map((d,i)=>
      `<option value="${esc(d.deviceId)}">${esc(d.label||`Microphone ${i+1} (allow permission for name)`)}</option>`
    ).join('');
    const stillPresent=previous&&rows.some(d=>d.deviceId===previous);
    $('audio-device').value=stillPresent?previous:'';
    if(previous&&!stillPresent) {
      activeAudioDevice=''; status('Selected microphone disconnected; using system default','warn');
      if(running) await switchAudioDevice();
    }
    $('device-state').textContent=`${rows.length||devices.length} microphone input(s)`;
  } finally {
    temporary?.getTracks().forEach(t=>t.stop());
  }
  if(!deviceListenerInstalled&&navigator.mediaDevices?.addEventListener) {
    navigator.mediaDevices.addEventListener('devicechange',()=>refreshAudioDevices(false).catch(()=>{}));
    deviceListenerInstalled=true;
  }
}

function selectedDeviceNeedsServer() {
  return Boolean($('audio-device').value);
}

async function switchAudioDevice() {
  const next=$('audio-device').value;
  if(next&&!providerInfo.remote_asr_configured) {
    $('audio-device').value=activeAudioDevice;
    throw new Error('Direct Bluetooth/USB selection requires server Whisper. Set it as the OS default or configure ASR_BASE_URL.');
  }
  if(next&&$('capture-engine').value!=='server') {
    $('capture-engine').value='server';
    status('Selected microphone uses server Whisper (browser ASR only uses OS default)','warn');
  }
  activeAudioDevice=$('audio-device').value;
  if(!running||$('role').value!=='speaker') return;
  captureEpoch+=1; manualStop=true;
  try{recognition?.stop()}catch(_){}; try{if(recorder?.state==='recording')recorder.stop()}catch(_){};
  stream?.getTracks().forEach(t=>t.stop()); processedStream?.getTracks().forEach(t=>t.stop());
  stream=null; processedStream=null; audioAnalyser=null;
  if(meterFrame)cancelAnimationFrame(meterFrame); try{await audioContext?.close()}catch(_){}; audioContext=null;
  await openWebcam(); startCapture();
}

async function ensureSession() {
  const payload = {
    session_id: sessionId(), source_language:$('source-lang').value,
    target_languages:[$('target-lang').value], translate_interim:false,
    theodore_auto_reply:$('theodore-auto').checked,
    theodore_language:$('theodore-lang').value,
    theodore_mode:$('theodore-mode').value
  };
  try {
    await api('/api/sessions',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(payload)});
  } catch (e) {
    if (!String(e.message).includes('already exists')) throw e;
  }
}

function connectSocket() {
  return new Promise((resolve, reject) => {
    if (socket) { try { socket.close(); } catch(_){} }
    const q = new URLSearchParams({
      role:$('role').value, target:$('target-lang').value,
      source:$('source-lang').value, participant:$('participant').value || 'guest'
    });
    socket = new WebSocket(`${wsBase()}/ws/sessions/${encodeURIComponent(sessionId())}?${q}`);
    const timer = setTimeout(() => reject(new Error('Translation feed connection timed out')), 5000);
    socket.onopen = () => {
      clearTimeout(timer); $('socket-state').textContent='feed: connected';
      $('socket-state').className='badge ok'; resolve();
    };
    socket.onclose = () => { $('socket-state').textContent='feed: disconnected'; $('socket-state').className='badge warn'; };
    socket.onerror = () => { clearTimeout(timer); reject(new Error('WebSocket connection failed')); };
    socket.onmessage = (evt) => {
      const msg=JSON.parse(evt.data);
      if(msg.type==='translation') (msg.events||[]).forEach(renderEvent);
      if(msg.type==='theodore_reply') renderTheodoreReply(msg.reply);
      if(msg.type==='presence') $('presence').textContent = Object.entries(msg.connected||{}).map(([k,v])=>`${k}:${v}`).join(' · ');
      if(msg.type==='config') $('session-source').textContent = `session input: ${msg.config.source_language}`;
      if(msg.type==='connected') {
        (msg.history||[]).forEach(renderEvent);
        (msg.theodore_replies||[]).forEach(renderTheodoreReply);
        $('presence').textContent = Object.entries(msg.session.connected||{}).map(([k,v])=>`${k}:${v}`).join(' · ');
      }
      if(msg.type==='error') status(msg.detail,'bad');
    };
  });
}

function sendTranscript(text, isFinal, provider='browser-speech-recognition', confidence=0, sourceOverride='') {
  text=(text||'').trim(); if(!text || !socket || socket.readyState!==1) return;
  const source=sourceOverride||$('source-lang').value;
  if(source==='auto'){ status('Manual/browser transcript needs a specific input language','bad'); return; }
  socket.send(JSON.stringify({type:'transcript',text,source_language:source,
    is_final:isFinal,end_of_turn:Boolean(isFinal),confidence,asr_provider:provider,
    speaker_id:$('participant').value||'learner'}));
}

function renderEvent(e) {
  if(!e.is_final) {
    if(lastInterim) lastInterim.remove();
  } else if(lastInterim) { lastInterim.remove(); lastInterim=null; }
  const card=document.createElement('div'); card.className='card'+(e.is_final?'':' interim');
  const direction = langs.find(l=>l.code===e.target_language)?.rtl ? 'rtl' : 'auto';
  card.innerHTML=`<div class="meta"><span>#${e.sequence}</span><span>${esc(e.speaker_id)}</span>
    <span>${esc(e.source_language)} → ${esc(e.target_language)}</span><span>${esc(e.translation_provider)}</span>
    <span>${e.latency_ms||0}ms</span></div>
    <div class="source">${esc(e.source_text)}</div>
    <div class="translation" dir="${direction}">${esc(e.translated_text)}</div>
    ${e.warning?`<div class="warning">⚠ ${esc(e.warning)}</div>`:''}`;
  const empty=$('empty'); if(empty) empty.remove();
  $('feed').prepend(card); if(!e.is_final) lastInterim=card;
  if(e.is_final && $('speak-output').checked) speakTranslation(e);
}

function renderTheodoreReply(reply) {
  const card=document.createElement('div'); card.className='card theodore-card';
  const row=langs.find(l=>l.code===reply.language);
  card.innerHTML=`<div class="meta"><strong>🎓 Theodore</strong><span>${esc(reply.mode)}</span>
    <span>${esc(row?.name||reply.language)}</span><span>${esc(reply.provider)}</span><span>${reply.latency_ms||0}ms</span></div>
    <div class="translation" dir="${row?.rtl?'rtl':'auto'}">${esc(reply.text)}</div>
    ${reply.warning?`<div class="warning">⚠ ${esc(reply.warning)}</div>`:''}`;
  const empty=$('empty'); if(empty) empty.remove(); $('feed').prepend(card);
  lastTheodoreReply=reply;
  if($('speak-theodore').checked) speakTheodore(reply);
}
let lastTheodoreReply=null;
// Server neural audio when the lab has an engine, else the device voice. Probed
// once (serverTts) so a lab with no TTS configured never pays a round-trip per
// reply. The device voice is missing or robotic for most of the 27 languages,
// which is why server audio is preferred rather than merely offered.
let serverTts={available:false,engine:''};
let theodoreAudio=null;

async function loadTtsStatus() {
  try { serverTts=await api('/api/tts/status'); } catch(_) { serverTts={available:false,engine:''}; }
  $('theodore-audio-state').textContent=serverTts.available
    ? `Theodore voice: ${serverTts.engine}` : 'Theodore voice: device';
}

function stopTheodoreAudio() {
  window.speechSynthesis?.cancel();
  if(theodoreAudio){ theodoreAudio.pause(); theodoreAudio=null; }
  $('theodore-audio-state').textContent='Theodore audio stopped';
}
window.addEventListener('theodore-live-audio',(event)=>{
  if(event.detail?.active){stopTheodoreAudio();stopTranslatedAudio();}
});

async function speakTheodore(reply) {
  if(!reply.text || window.__THEODORE_LIVE_AUDIO_ACTIVE__) return;
  const row=langs.find(l=>l.code===reply.language);
  const name=row?.name||reply.language;
  const rate=Number($('theodore-rate').value||.95);
  stopTheodoreAudio();

  if(serverTts.available) {
    try {
      const url=`/api/tts?text=${encodeURIComponent(reply.text)}`+
        `&language=${encodeURIComponent(reply.language)}&style=warm`;
      const res=await fetch(url);
      // 501 means "no engine here" — fall through to the device voice rather
      // than leaving Theodore silent.
      if(res.ok) {
        const engine=res.headers.get('X-TTS-Engine')||serverTts.engine;
        const blob=await res.blob();
        theodoreAudio=new Audio(URL.createObjectURL(blob));
        theodoreAudio.playbackRate=rate;
        $('theodore-audio-state').textContent=`speaking ${name} · ${engine}`;
        theodoreAudio.onended=()=>{$('theodore-audio-state').textContent=`Theodore voice: ${engine}`};
        await theodoreAudio.play();
        return;
      }
      if(res.status===501) serverTts.available=false;
    } catch(_) { /* fall back to the device voice below */ }
  }

  if(!window.speechSynthesis) {
    $('theodore-audio-state').textContent='no voice available on this device';
    return;
  }
  const utter=new SpeechSynthesisUtterance(reply.text);
  utter.lang=row?.bcp47||reply.language;
  utter.rate=rate; window.speechSynthesis.speak(utter);
  $('theodore-audio-state').textContent=`speaking ${name} · device voice`;
  utter.onend=()=>{$('theodore-audio-state').textContent='Theodore audio ready'};
}
async function updateTheodoreConfig() {
  await api(`/api/sessions/${encodeURIComponent(sessionId())}`,{
    method:'PATCH',headers:{'content-type':'application/json'},body:JSON.stringify({
      theodore_auto_reply:$('theodore-auto').checked,
      theodore_language:$('theodore-lang').value,
      theodore_mode:$('theodore-mode').value
    })
  }).catch(()=>{});
}
async function requestTheodore(text, sourceLanguage) {
  text=(text||'').trim(); if(!text)return;
  await api(`/api/sessions/${encodeURIComponent(sessionId())}/theodore/reply`,{
    method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({
      text,source_language:sourceLanguage||activeSourceLanguage,
      reply_language:$('theodore-lang').value,mode:$('theodore-mode').value,
      speaker_id:$('participant').value||'learner'
    })
  });
}

function speakTranslation(event) {
  if(window.__THEODORE_LIVE_AUDIO_ACTIVE__ || !window.speechSynthesis || !event.translated_text) return;
  const utter=new SpeechSynthesisUtterance(event.translated_text);
  const row=langs.find(l=>l.code===event.target_language);
  utter.lang=row?.bcp47||event.target_language;
  utter.rate=Number($('speech-rate').value||1);
  window.speechSynthesis.speak(utter);
  $('audio-state').textContent=`speaking ${row?.name||event.target_language}`;
  utter.onend=()=>{$('audio-state').textContent='translated audio ready'};
}
function stopTranslatedAudio() {
  window.speechSynthesis?.cancel(); $('audio-state').textContent='translated audio stopped';
}

async function openWebcam() {
  if(stream) return stream;
  const audioConstraints={
    echoCancellation:{ideal:true}, noiseSuppression:{ideal:true},
    autoGainControl:{ideal:true}, channelCount:{ideal:1}, sampleRate:{ideal:16000},
    latency:{ideal:.01}
  };
  const deviceId=$('audio-device').value;
  if(deviceId) audioConstraints.deviceId={exact:deviceId};
  stream=await navigator.mediaDevices.getUserMedia({
    video:{width:{ideal:960},height:{ideal:540},aspectRatio:{ideal:16/9}},
    audio:audioConstraints
  });
  $('preview').srcObject=stream; await startAudioPipeline(stream);
  const track=stream.getAudioTracks()[0]; const settings=track?.getSettings?.()||{};
  $('active-device').textContent=`active: ${track?.label||'system default'} · ${settings.sampleRate||'?'}Hz · ${settings.channelCount||1}ch`;
  activeAudioDevice=deviceId;
  await refreshAudioDevices(false);
  // enumerateDevices may rebuild options; restore the active device if present.
  if(activeAudioDevice&&[...$('audio-device').options].some(o=>o.value===activeAudioDevice))
    $('audio-device').value=activeAudioDevice;
  return stream;
}

async function startAudioPipeline(s) {
  const AC=window.AudioContext||window.webkitAudioContext;
  if(!AC){ processedStream=s; return; }
  audioContext=new AC({latencyHint:'interactive',sampleRate:audioPolicy.sample_rate_hz||16000});
  await audioContext.resume();
  const source=audioContext.createMediaStreamSource(s);
  const highpass=audioContext.createBiquadFilter(); highpass.type='highpass'; highpass.frequency.value=audioPolicy.highpass_hz;
  const lowpass=audioContext.createBiquadFilter(); lowpass.type='lowpass'; lowpass.frequency.value=audioPolicy.lowpass_hz;
  const compressor=audioContext.createDynamicsCompressor();
  compressor.threshold.value=audioPolicy.compressor.threshold_db;
  compressor.knee.value=audioPolicy.compressor.knee_db;
  compressor.ratio.value=audioPolicy.compressor.ratio;
  compressor.attack.value=audioPolicy.compressor.attack_s;
  compressor.release.value=audioPolicy.compressor.release_s;
  audioAnalyser=audioContext.createAnalyser(); audioAnalyser.fftSize=512; audioAnalyser.smoothingTimeConstant=.25;
  const dest=audioContext.createMediaStreamDestination();
  source.connect(highpass).connect(lowpass).connect(compressor);
  compressor.connect(audioAnalyser); compressor.connect(dest);
  processedStream=new MediaStream([...s.getVideoTracks(),...dest.stream.getAudioTracks()]);
  calibrationValues=[]; calibrationUntil=performance.now()+audioPolicy.calibration_ms;
  startMeter();
  $('filter-state').textContent=`filter: echo/NS + ${audioPolicy.highpass_hz}–${audioPolicy.lowpass_hz}Hz + compressor`;
}

function startMeter() {
  if(!audioAnalyser) return;
  const data=new Float32Array(audioAnalyser.fftSize);
  const tick=()=>{
    audioAnalyser.getFloatTimeDomainData(data);
    let sum=0; for(const sample of data) sum+=sample*sample;
    const rms=Math.sqrt(sum/data.length); const db=Math.max(-100,20*Math.log10(rms||1e-5));
    if(performance.now()<calibrationUntil) {
      calibrationValues.push(db);
      const sorted=[...calibrationValues].sort((a,b)=>a-b);
      noiseFloorDb=sorted[Math.floor(sorted.length*.2)]??-60;
    }
    gateThresholdDb=Math.max(audioPolicy.absolute_gate_db,noiseFloorDb+audioPolicy.noise_gate_margin_db);
    if(recorder?.state==='recording') {
      windowTotalFrames+=1; windowPeakDb=Math.max(windowPeakDb,db);
      if(db>=gateThresholdDb) windowSpeechFrames+=1;
    }
    const level=Math.max(0,Math.min(100,(db+70)*1.65)); $('meter-fill').style.width=`${level}%`;
    $('noise-state').textContent=`noise ${noiseFloorDb.toFixed(0)}dB · gate ${gateThresholdDb.toFixed(0)}dB`;
    meterFrame=requestAnimationFrame(tick);
  }; tick();
}

function recognitionCtor() { return window.SpeechRecognition||window.webkitSpeechRecognition||null; }
function startBrowserRecognition(epoch) {
  const Ctor=recognitionCtor(); if(!Ctor) throw new Error('Browser speech recognition unavailable; configure server Whisper.');
  const sourceAtStart=activeSourceLanguage;
  if(sourceAtStart==='auto') throw new Error('Auto-detect requires server Whisper; browser recognition needs a language hint.');
  manualStop=false; recognition=new Ctor();
  const row=langs.find(l=>l.code===sourceAtStart); recognition.lang=row?.bcp47||sourceAtStart;
  recognition.continuous=true; recognition.interimResults=true;
  recognition.onresult=(event)=>{
    if(epoch!==captureEpoch) return;
    for(let i=event.resultIndex;i<event.results.length;i++){
      const result=event.results[i]; const alt=result[0]||{};
      sendTranscript(alt.transcript||'',Boolean(result.isFinal),'browser-speech-recognition',Number(alt.confidence||0),sourceAtStart);
    }
  };
  recognition.onerror=(e)=>status(`Recognition: ${e.error||'error'}`,'bad');
  recognition.onend=()=>{ if(running&&!manualStop&&epoch===captureEpoch){ try{recognition.start()}catch(_){setTimeout(()=>{if(epoch===captureEpoch)recognition.start()},300)} } };
  recognition.start(); status(`Listening in ${row?.name||sourceAtStart}`,'ok');
}

function mimeType() {
  for(const m of ['audio/webm;codecs=opus','audio/webm','audio/mp4']) if(MediaRecorder.isTypeSupported?.(m)) return m;
  return 'audio/webm';
}
function captureWindowMs(source) {
  const selected=Number($('window-ms').value||audioPolicy.capture_window_ms);
  return source==='auto' ? Math.max(selected,audioPolicy.auto_detect_window_ms) : selected;
}
async function recordOneWindow(epoch) {
  if(!running||!stream||epoch!==captureEpoch) return;
  const chunks=[]; const type=mimeType(); const sourceAtStart=activeSourceLanguage;
  const windowMs=captureWindowMs(sourceAtStart); const captureStarted=performance.now();
  windowSpeechFrames=0; windowTotalFrames=0; windowPeakDb=-100;
  recorder=new MediaRecorder(processedStream||stream,{mimeType:type});
  recorder.ondataavailable=e=>{if(e.data.size)chunks.push(e.data)};
  recorder.onstop=async()=>{
    if(chunks.length && epoch===captureEpoch){
      const blob=new Blob(chunks,{type});
      const speechRatio=windowSpeechFrames/Math.max(1,windowTotalFrames);
      const gateOn=$('noise-gate').checked;
      const enoughSpeech=(windowTotalFrames<3)||(
        windowPeakDb>=gateThresholdDb && speechRatio>=audioPolicy.min_speech_ratio
      );
      $('vad-state').textContent=`voice ${(speechRatio*100).toFixed(0)}% · peak ${windowPeakDb.toFixed(0)}dB`;
      if(!gateOn||enoughSpeech) {
        const form=new FormData();
        form.append('audio',blob,type.includes('mp4')?'chunk.mp4':'chunk.webm');
        form.append('source_language',sourceAtStart); form.append('speaker_id',$('participant').value||'learner');
        const uploadStarted=performance.now();
        try { const res=await api(`/api/sessions/${encodeURIComponent(sessionId())}/audio`,{method:'POST',body:form});
          const detected=res.transcript.language; const row=langs.find(l=>l.code===detected);
          const totalMs=Math.round(performance.now()-captureStarted);
          const networkMs=Math.round(performance.now()-uploadStarted);
          const mtMs=Math.max(0,...(res.events||[]).map(e=>e.latency_ms||0));
          $('last-asr').textContent=`ASR (${row?.name||detected}): ${res.transcript.text}`;
          serverTurnBuffer.push(res.transcript.text); serverTurnBuffer=serverTurnBuffer.slice(-8);
          serverTurnLanguage=detected;
          $('detected-state').textContent=`detected: ${row?.name||detected}`;
          $('detected-state').className='badge ok';
          $('latency-state').textContent=`capture ${windowMs} · ASR ${res.transcript.duration_ms} · MT ${mtMs} · total ${totalMs}ms`;
          $('latency-state').className='badge '+(totalMs<2500?'ok':'warn');
          $('network-state').textContent=`request ${networkMs}ms`;
        } catch(e){ status(e.message,'bad'); }
      } else {
        $('last-asr').textContent=`Silence/noise skipped (${(speechRatio*100).toFixed(0)}% above gate)`;
        $('latency-state').textContent='no upload · 0 ASR cost'; $('latency-state').className='badge ok';
        // Silence closes the server-ASR learner turn. Reply once to the joined
        // speech windows instead of interrupting after every 0.8–2.0s chunk.
        if($('theodore-auto').checked&&serverTurnBuffer.length) {
          const learnerTurn=serverTurnBuffer.join(' '); serverTurnBuffer=[];
          requestTheodore(learnerTurn,serverTurnLanguage).catch(e=>status(e.message,'bad'));
        }
      }
    }
    if(running&&epoch===captureEpoch) recordOneWindow(epoch);
  };
  recorder.start(); setTimeout(()=>{
    if(recorder?.state==='recording'&&epoch===captureEpoch)recorder.stop()
  },windowMs);
  status(sourceAtStart==='auto'?`Listening · auto-detect · ${windowMs}ms windows`:`Whisper ${sourceAtStart} · ${windowMs}ms windows`,'ok');
}

function selectedCaptureEngine() {
  const requested=$('capture-engine').value;
  if(selectedDeviceNeedsServer()) return 'server';
  if(activeSourceLanguage==='auto') return 'server';
  if(requested==='server'||(requested==='auto'&&!recognitionCtor())) return 'server';
  return 'browser';
}
function startCapture() {
  captureEpoch += 1; const epoch=captureEpoch;
  manualStop=false;
  const engine=selectedCaptureEngine();
  if(engine==='server') {
    if(!providerInfo.remote_asr_configured) throw new Error('Auto-detect/server ASR requires ASR_BASE_URL. Choose a language for browser recognition.');
    $('capture-engine').value='server'; recordOneWindow(epoch);
  } else startBrowserRecognition(epoch);
}
async function switchInputLanguage() {
  const next=$('source-lang').value;
  if(next==='auto'&&!providerInfo.remote_asr_configured) {
    $('source-lang').value=activeSourceLanguage;
    status('Auto-detect needs server Whisper (ASR_BASE_URL)','bad'); return;
  }
  activeSourceLanguage=next;
  await api(`/api/sessions/${encodeURIComponent(sessionId())}`,{
    method:'PATCH',headers:{'content-type':'application/json'},
    body:JSON.stringify({source_language:next})
  }).catch(()=>{});
  $('session-source').textContent=`session input: ${next}`;
  if(!running||$('role').value!=='speaker') return;
  captureEpoch += 1; manualStop=true;
  try{recognition?.stop()}catch(_){};
  try{if(recorder?.state==='recording')recorder.stop()}catch(_){};
  startCapture();
}
async function switchCaptureEngine() {
  if(!running||$('role').value!=='speaker') return;
  captureEpoch += 1; manualStop=true;
  try{recognition?.stop()}catch(_){};
  try{if(recorder?.state==='recording')recorder.stop()}catch(_){};
  startCapture();
}

async function start() {
  activeSourceLanguage=$('source-lang').value;
  if(activeSourceLanguage==='auto'&&!providerInfo.remote_asr_configured)
    throw new Error('Auto-detect requires server Whisper. Set ASR_BASE_URL or choose an input language.');
  if($('audio-device').value&&!providerInfo.remote_asr_configured)
    throw new Error('Direct Bluetooth/USB microphone selection requires ASR_BASE_URL. Otherwise set that mic as your OS default.');
  serverTurnBuffer=[];
  await ensureSession(); await connectSocket();
  if($('role').value!=='speaker'){ status('Viewing translations','ok'); return; }
  await openWebcam(); running=true; startCapture();
}
function stop() {
  running=false; serverTurnBuffer=[]; captureEpoch+=1; manualStop=true; try{recognition?.stop()}catch(_){}; try{if(recorder?.state==='recording')recorder.stop()}catch(_){};
  stream?.getTracks().forEach(t=>t.stop()); processedStream?.getTracks().forEach(t=>t.stop());
  stream=null; processedStream=null; audioAnalyser=null; $('preview').srcObject=null;
  if(meterFrame)cancelAnimationFrame(meterFrame); try{audioContext?.close()}catch(_){}; audioContext=null;
  try{socket?.close()}catch(_){}; socket=null; status('Stopped','');
}
function shareViewer() {
  const q=new URLSearchParams({session:sessionId(),role:$('share-role').value,target:$('target-lang').value,source:$('source-lang').value});
  const url=`${location.origin}/lab?${q}`; navigator.clipboard?.writeText(url); $('share-url').value=url;
}

$('start').onclick=()=>start().catch(e=>status(e.message,'bad'));
$('stop').onclick=stop;
$('send-manual').onclick=()=>sendTranscript($('manual-text').value,true,'manual-test',1);
$('share').onclick=shareViewer;
$('stop-audio').onclick=stopTranslatedAudio;
$('stop-theodore-audio').onclick=stopTheodoreAudio;
$('replay-theodore').onclick=()=>{ if(lastTheodoreReply) speakTheodore(lastTheodoreReply); };
$('theodore-auto').onchange=()=>updateTheodoreConfig();
$('theodore-lang').onchange=()=>updateTheodoreConfig();
$('theodore-mode').onchange=()=>updateTheodoreConfig();
$('ask-theodore').onclick=()=>requestTheodore(
  $('manual-text').value,$('source-lang').value==='auto'?serverTurnLanguage:$('source-lang').value
).catch(e=>status(e.message,'bad'));
$('source-lang').onchange=()=>switchInputLanguage().catch(e=>status(e.message,'bad'));
$('audio-device').onchange=()=>switchAudioDevice().catch(e=>status(e.message,'bad'));
$('refresh-devices').onclick=()=>refreshAudioDevices(true).catch(e=>status(e.message,'bad'));
$('capture-engine').onchange=()=>switchCaptureEngine().catch(e=>status(e.message,'bad'));
$('role').onchange=()=>{ $('speaker-controls').style.display=$('role').value==='speaker'?'block':'none'; };
loadLanguages().then(()=>Promise.all([loadProviders(),loadAudioPolicy(),loadTheodore(),loadTtsStatus(),refreshAudioDevices(false)])).then(()=>{ $('role').onchange(); }).catch(e=>status(e.message,'bad'));
"""


def render_lab_page() -> str:
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Theodore Audio Translation Lab</title><style>{CSS}</style></head>
<body><header><h1>Theodore Audio Translation Lab</h1>
<p>Webcam/microphone speech → realtime transcript → 27-language translation feed for Theodore, teachers, or customers.</p></header>
<div class="grid"><section class="panel"><h2>Live source</h2>
<div class="row"><label>Session<br/><input id="session-id" value="translation-demo"/></label>
<label>I am<br/><select id="role"><option value="speaker">Speaker / learner</option><option value="theodore">Theodore</option><option value="teacher">Teacher</option><option value="customer">Customer</option><option value="viewer">Viewer</option></select></label>
<label>Name<br/><input id="participant" value="learner"/></label></div>
<div class="row"><label>Spoken language (change anytime)<br/><select id="source-lang"></select></label>
<label>Translate for me into<br/><select id="target-lang"></select></label></div>
<div class="row"><label>Microphone input (Bluetooth / USB / built-in)<br/><select id="audio-device"><option value="">System default microphone</option></select></label>
<button id="refresh-devices" class="secondary">Allow / refresh microphones</button>
<span id="device-state" class="badge">devices: permission needed</span><span id="active-device" class="badge">active: system default</span></div>
<div id="auto-note" class="note warn">Auto-detect needs server Whisper (`ASR_BASE_URL`). Browser recognition requires a selected language. Direct Bluetooth/USB selection also uses server Whisper; browser Web Speech can only use the OS default mic.</div>
<div id="speaker-controls"><video id="preview" autoplay muted playsinline></video>
<div class="meter"><div id="meter-fill"></div></div>
<div class="row"><label>Capture engine<br/><select id="capture-engine"><option value="auto">Auto (browser first)</option><option value="browser">Browser realtime ASR</option><option value="server">Server Whisper chunks</option></select></label>
<label>Server latency<br/><select id="window-ms"><option value="800">Fast · 0.8s</option><option value="1200" selected>Balanced · 1.2s</option><option value="2000">Accuracy · 2.0s</option></select></label>
<label><input id="noise-gate" type="checkbox" checked/> Skip silence/noise</label>
<button id="start">Start webcam + translation</button><button id="stop" class="danger">Stop</button></div></div>
<div class="statusbar"><span id="run-state" class="badge">Idle</span><span id="socket-state" class="badge">feed: disconnected</span><span id="asr-state" class="badge">ASR…</span><span id="mt-state" class="badge">translation…</span><span id="session-source" class="badge">session input</span><span id="detected-state" class="badge">detected: —</span><span id="filter-state" class="badge">filter…</span><span id="noise-state" class="badge">noise…</span><span id="vad-state" class="badge">voice…</span></div>
<div class="statusbar"><span id="latency-state" class="badge">latency: —</span><span id="network-state" class="badge">request: —</span></div>
<div id="last-asr" class="note">Browser mode provides low-latency interim text. Server mode uses filtered 0.8–2.0 second complete audio windows; Auto uses at least 2 seconds for reliable language ID.</div>
<h2>Debug without a microphone</h2><textarea id="manual-text" placeholder="Type a sentence in the selected spoken language…"></textarea>
<div class="row"><button id="send-manual" class="secondary">Send transcript</button></div>
<div class="note warn">Raw audio is held in memory only for ASR and is never saved by this lab. Use headphones to reduce teacher/audio echo.</div>
<p class="privacy">Browser recognition may use your browser/OS speech service. Server Whisper uses ASR_BASE_URL. Confirm data policy before real customer use.</p></section>
<section class="panel"><h2>Teacher / Theodore / customer feed</h2>
<div class="row"><label><input id="theodore-auto" type="checkbox" checked/> Theodore replies after each learner turn</label>
<label>Teach mode <select id="theodore-mode"><option value="teach">Teach + check</option><option value="answer">Answer directly</option><option value="coach">Coach with a hint</option><option value="clarify">Clarify simply</option></select></label>
<label>Reply language <select id="theodore-lang"></select></label></div>
<div class="row"><label><input id="speak-theodore" type="checkbox" checked/> Speak Theodore aloud</label>
<label>Speed <input id="theodore-rate" type="number" value="0.95" min="0.6" max="1.3" step="0.05" style="width:65px"/></label>
<button id="ask-theodore" class="secondary">Ask Theodore using debug text</button>
<button id="replay-theodore" class="secondary">Say it again</button>
<button id="stop-theodore-audio" class="secondary">Stop Theodore audio</button>
<span id="theodore-state" class="badge">Theodore…</span><span id="theodore-audio-state" class="badge">Theodore audio ready</span></div>
<div class="row"><span class="connected" id="presence"></span>
<label><input id="speak-output" type="checkbox"/> Speak translated audio</label>
<label>Speed <input id="speech-rate" type="number" value="1" min="0.6" max="1.4" step="0.1" style="width:65px"/></label>
<button id="stop-audio" class="secondary">Stop audio</button><span id="audio-state" class="badge">device voice</span>
<label>Share as <select id="share-role"><option value="teacher">teacher</option><option value="theodore">Theodore</option><option value="customer">customer</option><option value="viewer">viewer</option></select></label>
<button id="share" class="secondary">Copy viewer link</button><input id="share-url" class="grow" readonly/></div>
<div id="feed" class="feed"><div id="empty" class="empty">Translations will appear here in realtime.<br/>Open a viewer link on another browser to test delivery.</div></div>
</section></div><script>{JS}</script></body></html>"""

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
let meterFrame = 0;
let socket = null;
let running = false;
let manualStop = false;
let lastInterim = null;

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
  for (const id of ['source-lang','target-lang']) {
    $(id).innerHTML = langs.map(l=>`<option value="${l.code}">${esc(l.name)} (${l.code})</option>`).join('');
  }
  const q = new URLSearchParams(location.search);
  $('source-lang').value = q.get('source') || 'es';
  $('target-lang').value = q.get('target') || 'en';
  $('role').value = q.get('role') || 'speaker';
  $('session-id').value = q.get('session') || 'translation-demo';
}

async function loadProviders() {
  const p = await api('/api/providers');
  $('asr-state').textContent = p.remote_asr_configured ? 'Whisper: ready' : 'Whisper: not configured';
  $('asr-state').className = 'badge ' + (p.remote_asr_configured?'ok':'warn');
  const translation = p.translation_gateway_configured ? 'NLLB: ready' :
    (p.xai_translation_configured ? 'xAI translate: ready' : 'Translation: phrasebook/source fallback');
  $('mt-state').textContent = translation;
  $('mt-state').className = 'badge ' + ((p.translation_gateway_configured||p.xai_translation_configured)?'ok':'warn');
  $('capture-engine').querySelector('[value=server]').disabled = !p.remote_asr_configured;
}

async function ensureSession() {
  const payload = {
    session_id: sessionId(), source_language:$('source-lang').value,
    target_languages:[$('target-lang').value], translate_interim:false
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
      if(msg.type==='presence') $('presence').textContent = Object.entries(msg.connected||{}).map(([k,v])=>`${k}:${v}`).join(' · ');
      if(msg.type==='connected') {
        (msg.history||[]).forEach(renderEvent);
        $('presence').textContent = Object.entries(msg.session.connected||{}).map(([k,v])=>`${k}:${v}`).join(' · ');
      }
      if(msg.type==='error') status(msg.detail,'bad');
    };
  });
}

function sendTranscript(text, isFinal, provider='browser-speech-recognition', confidence=0) {
  text=(text||'').trim(); if(!text || !socket || socket.readyState!==1) return;
  socket.send(JSON.stringify({type:'transcript',text,source_language:$('source-lang').value,
    is_final:isFinal,confidence,asr_provider:provider,speaker_id:$('participant').value||'learner'}));
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

function speakTranslation(event) {
  if(!window.speechSynthesis || !event.translated_text) return;
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
  stream=await navigator.mediaDevices.getUserMedia({
    video:{width:{ideal:960},height:{ideal:540},aspectRatio:{ideal:16/9}},
    audio:{echoCancellation:true,noiseSuppression:true,autoGainControl:true}
  });
  $('preview').srcObject=stream; startMeter(stream); return stream;
}

function startMeter(s) {
  const AC=window.AudioContext||window.webkitAudioContext; if(!AC) return;
  audioContext=new AC(); const analyser=audioContext.createAnalyser(); analyser.fftSize=256;
  audioContext.createMediaStreamSource(s).connect(analyser); const data=new Uint8Array(analyser.frequencyBinCount);
  const tick=()=>{ analyser.getByteFrequencyData(data); const avg=data.reduce((a,b)=>a+b,0)/data.length;
    $('meter-fill').style.width=`${Math.min(100,avg*1.5)}%`; meterFrame=requestAnimationFrame(tick); }; tick();
}

function recognitionCtor() { return window.SpeechRecognition||window.webkitSpeechRecognition||null; }
function startBrowserRecognition() {
  const Ctor=recognitionCtor(); if(!Ctor) throw new Error('Browser speech recognition unavailable; configure server Whisper.');
  manualStop=false; recognition=new Ctor();
  const row=langs.find(l=>l.code===$('source-lang').value); recognition.lang=row?.bcp47||$('source-lang').value;
  recognition.continuous=true; recognition.interimResults=true;
  recognition.onresult=(event)=>{
    for(let i=event.resultIndex;i<event.results.length;i++){
      const result=event.results[i]; const alt=result[0]||{};
      sendTranscript(alt.transcript||'',Boolean(result.isFinal),'browser-speech-recognition',Number(alt.confidence||0));
    }
  };
  recognition.onerror=(e)=>status(`Recognition: ${e.error||'error'}`,'bad');
  recognition.onend=()=>{ if(running&&!manualStop){ try{recognition.start()}catch(_){setTimeout(()=>recognition.start(),300)} } };
  recognition.start(); status('Listening + translating','ok');
}

function mimeType() {
  for(const m of ['audio/webm;codecs=opus','audio/webm','audio/mp4']) if(MediaRecorder.isTypeSupported?.(m)) return m;
  return 'audio/webm';
}
async function recordOneWindow() {
  if(!running||!stream) return; const chunks=[]; const type=mimeType();
  recorder=new MediaRecorder(stream,{mimeType:type}); recorder.ondataavailable=e=>{if(e.data.size)chunks.push(e.data)};
  recorder.onstop=async()=>{
    if(chunks.length){ const blob=new Blob(chunks,{type}); const form=new FormData();
      form.append('audio',blob,type.includes('mp4')?'chunk.mp4':'chunk.webm');
      form.append('source_language',$('source-lang').value); form.append('speaker_id',$('participant').value||'learner');
      try { const res=await api(`/api/sessions/${encodeURIComponent(sessionId())}/audio`,{method:'POST',body:form});
        $('last-asr').textContent=`ASR: ${res.transcript.text}`;
      } catch(e){ status(e.message,'bad'); }
    }
    if(running) recordOneWindow();
  };
  recorder.start(); setTimeout(()=>{if(recorder?.state==='recording')recorder.stop()},3500);
  status('Recording 3.5s Whisper windows','ok');
}

async function start() {
  await ensureSession(); await connectSocket();
  if($('role').value!=='speaker'){ status('Viewing translations','ok'); return; }
  await openWebcam(); running=true;
  const requested=$('capture-engine').value;
  if(requested==='server'||(requested==='auto'&&!recognitionCtor())) recordOneWindow();
  else startBrowserRecognition();
}
function stop() {
  running=false; manualStop=true; try{recognition?.stop()}catch(_){}; try{if(recorder?.state==='recording')recorder.stop()}catch(_){};
  stream?.getTracks().forEach(t=>t.stop()); stream=null; $('preview').srcObject=null;
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
$('role').onchange=()=>{ $('speaker-controls').style.display=$('role').value==='speaker'?'block':'none'; };
loadLanguages().then(loadProviders).then(()=>{ $('role').onchange(); }).catch(e=>status(e.message,'bad'));
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
<div class="row"><label>Spoken language<br/><select id="source-lang"></select></label>
<label>Translate for me into<br/><select id="target-lang"></select></label></div>
<div id="speaker-controls"><video id="preview" autoplay muted playsinline></video>
<div class="meter"><div id="meter-fill"></div></div>
<div class="row"><label>Capture engine<br/><select id="capture-engine"><option value="auto">Auto (browser first)</option><option value="browser">Browser realtime ASR</option><option value="server">Server Whisper chunks</option></select></label>
<button id="start">Start webcam + translation</button><button id="stop" class="danger">Stop</button></div></div>
<div class="statusbar"><span id="run-state" class="badge">Idle</span><span id="socket-state" class="badge">feed: disconnected</span><span id="asr-state" class="badge">ASR…</span><span id="mt-state" class="badge">translation…</span></div>
<div id="last-asr" class="note">Browser mode sends transcript text only. Server mode sends ephemeral 3.5-second audio windows to configured Whisper.</div>
<h2>Debug without a microphone</h2><textarea id="manual-text" placeholder="Type a sentence in the selected spoken language…"></textarea>
<div class="row"><button id="send-manual" class="secondary">Send transcript</button></div>
<div class="note warn">Raw audio is held in memory only for ASR and is never saved by this lab. Use headphones to reduce teacher/audio echo.</div>
<p class="privacy">Browser recognition may use your browser/OS speech service. Server Whisper uses ASR_BASE_URL. Confirm data policy before real customer use.</p></section>
<section class="panel"><h2>Teacher / Theodore / customer feed</h2>
<div class="row"><span class="connected" id="presence"></span>
<label><input id="speak-output" type="checkbox"/> Speak translated audio</label>
<label>Speed <input id="speech-rate" type="number" value="1" min="0.6" max="1.4" step="0.1" style="width:65px"/></label>
<button id="stop-audio" class="secondary">Stop audio</button><span id="audio-state" class="badge">device voice</span>
<label>Share as <select id="share-role"><option value="teacher">teacher</option><option value="theodore">Theodore</option><option value="customer">customer</option><option value="viewer">viewer</option></select></label>
<button id="share" class="secondary">Copy viewer link</button><input id="share-url" class="grow" readonly/></div>
<div id="feed" class="feed"><div id="empty" class="empty">Translations will appear here in realtime.<br/>Open a viewer link on another browser to test delivery.</div></div>
</section></div><script>{JS}</script></body></html>"""

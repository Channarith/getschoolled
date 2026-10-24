"use strict";
(function () {
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  let cfg = null;
  const st = { name: "", role: "employee", speaker: "", lang: "en", proof: null, mode: "voice", takes: {}, busy: false };

  async function api(path, opts = {}) {
    const init = { method: opts.method || "GET", headers: {} };
    if (init.method === "POST") init.headers["X-Enroll"] = "1";
    if (opts.json !== undefined) { init.headers["Content-Type"] = "application/json"; init.body = JSON.stringify(opts.json); }
    if (opts.body !== undefined) { init.headers["Content-Type"] = "audio/wav"; init.body = opts.body; }
    const r = await fetch(path, init);
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(data.error || `request failed (${r.status})`);
    return data;
  }

  /* ---------- microphone: one stream, raw PCM captured through WebAudio, encoded to 16-bit WAV ---------- */
  const mic = {
    ctx: null, chunks: null, meters: [],
    async enable() {
      if (this.ctx) return;
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        throw new Error("This page has no microphone access. Open it as http://localhost:<port>/ (use the ssh -L tunnel), not by IP address.");
      }
      const stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: false, noiseSuppression: false, autoGainControl: false } });
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      const src = ctx.createMediaStreamSource(stream);
      const proc = ctx.createScriptProcessor(4096, 1, 1);
      proc.onaudioprocess = (e) => {
        const d = e.inputBuffer.getChannelData(0);
        let peak = 0;
        for (let i = 0; i < d.length; i++) { const a = Math.abs(d[i]); if (a > peak) peak = a; }
        this.meters.forEach((m) => { m.value = Math.min(1, peak * 1.4); });
        if (this.chunks) this.chunks.push(new Float32Array(d));
      };
      src.connect(proc);
      proc.connect(ctx.destination);
      this.ctx = ctx;
      this.stream = stream;
    },
    begin() { this.chunks = []; },
    end() {
      const parts = this.chunks || [];
      this.chunks = null;
      let n = 0; parts.forEach((p) => { n += p.length; });
      const x = new Float32Array(n); let o = 0; parts.forEach((p) => { x.set(p, o); o += p.length; });
      return { samples: x, rate: this.ctx.sampleRate };
    },
  };

  function encodeWav(samples, rate) {
    const buf = new ArrayBuffer(44 + samples.length * 2);
    const v = new DataView(buf);
    const w = (o, s) => { for (let i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i)); };
    w(0, "RIFF"); v.setUint32(4, 36 + samples.length * 2, true); w(8, "WAVE"); w(12, "fmt ");
    v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true); v.setUint32(24, rate, true);
    v.setUint32(28, rate * 2, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true); w(36, "data"); v.setUint32(40, samples.length * 2, true);
    for (let i = 0; i < samples.length; i++) { const s = Math.max(-1, Math.min(1, samples[i])); v.setInt16(44 + i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true); }
    return new Blob([buf], { type: "audio/wav" });
  }

  function analyze(x, rate) {
    let peak = 0, clipped = 0;
    for (let i = 0; i < x.length; i++) { const a = Math.abs(x[i]); if (a > peak) peak = a; if (a >= 0.999) clipped++; }
    const frame = Math.max(1, Math.floor(rate * 0.03)), k = Math.floor(x.length / frame), e = [];
    for (let f = 0; f < k; f++) { let s = 0; for (let i = 0; i < frame; i++) { const v = x[f * frame + i]; s += v * v; } e.push(s / frame + 1e-12); }
    e.sort((a, b) => a - b);
    const d = Math.max(1, Math.floor(k / 10));
    const mean = (a) => a.reduce((s, v) => s + v, 0) / a.length;
    const snr = k >= 10 ? 10 * Math.log10(mean(e.slice(-d)) / mean(e.slice(0, d))) : 0;
    const warnings = [];
    if (x.length / rate < 2) warnings.push("too short: read the whole line");
    if (clipped > 5 || peak >= 0.999) warnings.push("clipping: move back from the microphone");
    if (peak < 0.05) warnings.push("very quiet: speak up or move closer");
    if (k >= 10 && snr < cfg.min_snr_db) warnings.push("background noise is high: find a quieter spot");
    return { seconds: x.length / rate, peak, snr, warnings };
  }

  const toB64 = (blob) => new Promise((res, rej) => { const r = new FileReader(); r.onload = () => res(String(r.result).split(",")[1]); r.onerror = rej; r.readAsDataURL(blob); });

  /* ---------- navigation ---------- */
  function step(n) {
    for (let i = 1; i <= 4; i++) $("s" + i).hidden = i !== n;
    document.querySelectorAll("#steps li").forEach((li) => {
      const s = Number(li.dataset.s);
      li.className = s === n ? "on" : s < n ? "past" : "";
    });
  }
  function tab(which) {
    $("wizard").hidden = which !== "wizard"; $("list").hidden = which !== "list"; $("say").hidden = which !== "say";
    $("tab-wizard").classList.toggle("on", which === "wizard"); $("tab-list").classList.toggle("on", which === "list"); $("tab-say").classList.toggle("on", which === "say");
    if (which === "list") loadList();
    if (which === "say") loadSay().catch((e) => { $("say-err").textContent = e.message; });
  }

  /* ---------- step 1 and 2: who and consent ---------- */
  $("to-consent").onclick = async () => {
    $("e1").textContent = "";
    st.name = $("name").value.replace(/\s+/g, " ").trim(); st.role = $("role").value;
    if (st.name.length < 2) { $("e1").textContent = "Enter the person's full name."; return; }
    try { $("statement").textContent = (await api("/api/statement?name=" + encodeURIComponent(st.name))).text; }
    catch (e) { $("e1").textContent = e.message; return; }
    $("consent-text").textContent = cfg.consent_text;
    document.querySelectorAll("#agreements input").forEach((c) => { c.checked = false; });
    $("typed").value = ""; st.proof = null; $("proof-audio").hidden = true; $("proof-info").textContent = "";
    step(2);
  };
  $("back1").onclick = () => step(1);

  function setMode(m) {
    st.mode = m;
    $("m-voice").classList.toggle("on", m === "voice"); $("m-form").classList.toggle("on", m === "form");
    $("proof-voice").hidden = m !== "voice"; $("proof-form").hidden = m !== "form";
  }
  $("m-voice").onclick = () => setMode("voice");
  $("m-form").onclick = () => setMode("form");

  let proofRec = false;
  $("proof-rec").onclick = async () => {
    $("e2").textContent = "";
    try { await mic.enable(); } catch (e) { $("e2").textContent = e.message; return; }
    mic.meters = [$("proof-meter")]; mic.begin(); proofRec = true;
    $("proof-rec").disabled = true; $("proof-stop").disabled = false; $("proof-info").textContent = "recording...";
  };
  $("proof-stop").onclick = () => {
    if (!proofRec) return;
    proofRec = false;
    const { samples, rate } = mic.end();
    const a = analyze(samples, rate);
    st.proof = encodeWav(samples, rate);
    $("proof-rec").disabled = false; $("proof-stop").disabled = true; $("proof-rec").textContent = "Record again";
    $("proof-audio").src = URL.createObjectURL(st.proof); $("proof-audio").hidden = false;
    $("proof-info").textContent = `${a.seconds.toFixed(1)} s` + (a.warnings.length ? " - " + a.warnings.join("; ") : " - ok");
    $("proof-meter").value = 0;
  };

  $("submit-consent").onclick = async () => {
    $("e2").textContent = "";
    const agreements = {};
    document.querySelectorAll("#agreements input").forEach((c) => { agreements[c.dataset.a] = c.checked; });
    const payload = { name: st.name, role: st.role, typed_name: $("typed").value, agreements, text_sha256: cfg.consent_text_sha256 };
    if (st.mode === "form") {
      payload.existing_form_path = $("form-path").value;
      if (!payload.existing_form_path.trim()) { $("e2").textContent = "Enter the path of the signed form."; return; }
    } else {
      if (!st.proof) { $("e2").textContent = "Record the spoken statement first."; return; }
      payload.proof_wav_b64 = await toB64(st.proof);
    }
    $("submit-consent").disabled = true;
    try {
      const r = await api("/api/consent", { method: "POST", json: payload });
      st.speaker = r.speaker; st.takes = {};
      startRecording();
    } catch (e) { $("e2").textContent = e.message; }
    $("submit-consent").disabled = false;
  };

  /* ---------- step 3: record the lines ---------- */
  function startRecording(existingTakes) {
    st.takes = {};
    (existingTakes || []).forEach((id) => { st.takes[id] = { uploaded: true }; });
    $("lang").innerHTML = Object.entries(cfg.langs).map(([k, v]) => `<option value="${k}"${k === st.lang ? " selected" : ""}>${esc(v)}</option>`).join("");
    buildLines();
    $("e3").textContent = ""; $("ok3").textContent = "";
    step(3);
    tab("wizard");
  }
  $("lang").onchange = () => { st.lang = $("lang").value; st.takes = {}; buildLines(); };
  $("mic-on").onclick = async () => {
    try { await mic.enable(); mic.meters = [$("meter")]; $("mic-info").textContent = "microphone is on: speak and watch the bar"; $("mic-on").disabled = true; }
    catch (e) { $("e3").textContent = e.message; }
  };

  let recording = null;
  function buildLines() {
    $("draft-note").hidden = !cfg.draft_langs.includes(st.lang);
    const ol = $("lines"); ol.innerHTML = "";
    cfg.prompts[st.lang].forEach((p, i) => {
      const li = document.createElement("li"); li.id = "line-" + p.id;
      li.innerHTML = `<div class="n">Line ${i + 1} of ${cfg.prompts[st.lang].length}</div><div class="t">${esc(p.text)}</div>
        <div class="rec-row"><button type="button" class="r">Record</button><button type="button" class="s" disabled>Stop</button>
        <audio class="a" controls hidden></audio><span class="hint i"></span></div><div class="warn w"></div>`;
      li.querySelector(".r").onclick = () => recLine(p.id);
      li.querySelector(".s").onclick = () => stopLine(p.id);
      ol.appendChild(li);
    });
    refreshLines();
  }
  function refreshLines() {
    const ps = cfg.prompts[st.lang]; let cur = true, secs = 0;
    ps.forEach((p) => {
      const li = $("line-" + p.id), t = st.takes[p.id];
      li.classList.toggle("done", !!t);
      li.classList.toggle("cur", !t && cur);
      if (!t && cur) cur = false;
      if (t && t.seconds) secs += t.seconds;
      if (t && !li.querySelector(".i").textContent) li.querySelector(".i").textContent = "saved";
    });
    const n = Object.keys(st.takes).length;
    $("total").textContent = `${n} of ${ps.length} lines recorded` + (secs ? ` (${secs.toFixed(0)} s)` : "");
    $("finish").disabled = n < ps.length;
  }
  async function recLine(id) {
    $("e3").textContent = "";
    if (recording) return;
    try { await mic.enable(); } catch (e) { $("e3").textContent = e.message; return; }
    mic.meters = [$("meter")]; $("mic-on").disabled = true;
    recording = id; mic.begin();
    const li = $("line-" + id);
    li.querySelector(".r").disabled = true; li.querySelector(".s").disabled = false; li.querySelector(".i").textContent = "recording...";
    li.querySelector(".w").textContent = "";
  }
  async function stopLine(id) {
    if (recording !== id) return;
    recording = null;
    const { samples, rate } = mic.end();
    const li = $("line-" + id), a = analyze(samples, rate);
    li.querySelector(".r").disabled = false; li.querySelector(".r").textContent = "Re-record"; li.querySelector(".s").disabled = true;
    const blob = encodeWav(samples, rate);
    const au = li.querySelector(".a"); au.src = URL.createObjectURL(blob); au.hidden = false;
    li.querySelector(".w").textContent = a.warnings.join("; ");
    li.querySelector(".i").textContent = `${a.seconds.toFixed(1)} s, uploading...`;
    delete st.takes[id]; refreshLines();
    try {
      const r = await api(`/api/take/${st.speaker}/${st.lang}/${id}`, { method: "POST", body: blob });
      st.takes[id] = { seconds: r.seconds, uploaded: true };
      li.querySelector(".i").textContent = `${r.seconds.toFixed(1)} s saved`;
      const w = (r.warnings || []).concat(a.warnings.filter((x) => !(r.warnings || []).includes(x)));
      li.querySelector(".w").textContent = w.join("; ");
    } catch (e) { li.querySelector(".i").textContent = ""; li.querySelector(".w").textContent = e.message; }
    refreshLines();
  }
  $("finish").onclick = async () => {
    $("e3").textContent = ""; $("ok3").textContent = "";
    $("finish").disabled = true;
    try {
      const r = await api("/api/enroll/" + st.speaker, { method: "POST", json: { lang: st.lang } });
      if (!r.ok) { $("e3").textContent = "Not accepted: " + r.error + " Re-record the lines that had warnings."; $("finish").disabled = false; return; }
      $("done-msg").textContent = `${st.name || st.speaker} is enrolled: ${r.seconds} s of speech, ${r.snr_db} dB signal-to-noise. You can now test the voice under Enrolled voices.`;
      step(4);
    } catch (e) { $("e3").textContent = e.message; $("finish").disabled = false; }
  };
  $("another").onclick = () => { $("name").value = ""; step(1); };
  $("see-list").onclick = () => tab("list");

  /* ---------- enrolled voices ---------- */
  async function loadList() {
    const box = $("speakers");
    let data;
    try { data = await api("/api/speakers"); } catch (e) { box.textContent = e.message; return; }
    $("root-note").textContent = `Stored in ${data.root} on this machine only.`;
    if (!data.speakers.length) { box.innerHTML = '<p class="hint">Nobody is enrolled yet.</p>'; return; }
    box.innerHTML = "";
    data.speakers.forEach((s) => {
      const div = document.createElement("div"); div.className = "sp"; div.dataset.speaker = s.speaker;
      const samples = s.samples.map((x) => `${esc(x.lang)} ${x.seconds ? x.seconds + " s" : ""}`).join(", ") || "no sample yet";
      div.innerHTML = `<div><span class="name">${esc(s.name)}</span><span class="tag ${s.revoked ? "bad" : ""}">${s.revoked ? "withdrawn " + esc(s.revoked_on || "") : "consented"}</span></div>
        <div class="hint">${esc(s.role)} - consent ${esc(s.date)} via ${esc(s.method)} - samples: ${samples}</div>
        <div class="row act"></div><div class="out hint"></div>`;
      const act = div.querySelector(".act"), out = div.querySelector(".out");
      if (!s.revoked) {
        const rec = document.createElement("button"); rec.textContent = "Record / re-record"; rec.className = "b-rec";
        rec.onclick = () => { st.speaker = s.speaker; st.name = s.name; startRecording(s.takes[st.lang] || []); };
        const sel = document.createElement("select"); sel.style.width = "auto";
        sel.innerHTML = cfg.models.map((m) => `<option>${m}</option>`).join("");
        const syn = document.createElement("button"); syn.textContent = "Synthesize test"; syn.className = "b-synth";
        syn.disabled = !s.samples.length;
        syn.onclick = () => synth(s.speaker, sel.value, out, data.cuda);
        const wd = document.createElement("button"); wd.textContent = "Withdraw consent"; wd.className = "b-withdraw";
        wd.onclick = () => withdrawUi(s, out);
        act.append(rec, sel, syn, wd);
      }
      box.appendChild(div);
    });
  }
  function withdrawUi(s, out) {
    out.innerHTML = `Type <b>${esc(s.name)}</b> to withdraw their consent. New audio with this voice stops at once.
      <div class="row"><input class="wn" autocomplete="off"><button class="wgo" type="button">Withdraw</button></div><span class="err"></span>`;
    out.querySelector(".wgo").onclick = async () => {
      try { await api("/api/revoke/" + s.speaker, { method: "POST", json: { typed_name: out.querySelector(".wn").value } }); loadList(); }
      catch (e) { out.querySelector(".err").textContent = e.message; }
    };
  }
  async function synth(speaker, model, out, cuda) {
    out.textContent = "starting...";
    try {
      const r = await api("/api/synth/" + speaker, { method: "POST", json: { model } });
      if (!r.started) { out.innerHTML = `${esc(r.reason)}.<br>On the Spark, from the repo: <code>${esc(r.command)}</code>`; return; }
      const poll = async () => {
        const j = await api("/api/synth/" + speaker);
        out.innerHTML = `${esc(j.state)} (${esc(j.model || model)})` + (j.state === "done" ? `. Listen: <code>${esc(j.listen)}</code>` : "") +
          (j.log_tail ? `<pre>${esc(j.log_tail)}</pre>` : "");
        if (j.state === "running") setTimeout(poll, 4000);
      };
      poll();
    } catch (e) { out.textContent = e.message; }
  }

  /* ---------- say anything ---------- */
  let sayTimer = null, lastSay = "";
  async function loadSay() {
    const data = await api("/api/speakers");
    const ok = data.speakers.filter((s) => !s.revoked && s.samples.length);
    const sp = $("say-speaker"), keep = sp.value;
    sp.innerHTML = ok.map((s) => `<option value="${esc(s.speaker)}">${esc(s.name)}</option>`).join("") || '<option value="">nobody enrolled</option>';
    if (keep) sp.value = keep;
    $("say-model").innerHTML = cfg.models.map((m) => `<option>${esc(m)}</option>`).join("");
    fillSayLangs();
    $("say-go").disabled = !ok.length;
    $("say-note").textContent = data.cuda ? "" : "This machine has no CUDA GPU: the page will show the command to run on the Spark.";
    refreshSay();
  }
  function fillSayLangs() {
    const langs = cfg.say_langs[$("say-model").value] || [], keep = $("say-lang").value;
    $("say-lang").innerHTML = langs.map((l) => `<option value="${l}">${esc(cfg.lang_names[l] || l)}</option>`).join("");
    if (langs.includes(keep)) $("say-lang").value = keep;
  }
  async function refreshSay() {
    clearTimeout(sayTimer);
    let r;
    try { r = await api("/api/say"); } catch (e) { return; }
    const box = $("say-history"), sig = JSON.stringify(r.jobs);
    const active = r.jobs.some((j) => j.state === "running" || j.state === "waiting for GPU lock");
    if (!active && /already/.test($("say-err").textContent)) $("say-err").textContent = "";
    if (sig === lastSay) { if (active) sayTimer = setTimeout(refreshSay, 3000); return; }
    lastSay = sig;
    if (!r.jobs.length) { box.innerHTML = '<p class="hint">Nothing yet.</p>'; return; }
    box.innerHTML = "";
    r.jobs.forEach((j) => {
      const d = document.createElement("div"); d.className = "say-item"; d.dataset.id = j.id; d.dataset.state = j.state;
      d.innerHTML = `<div class="ai">${esc(j.label)}</div><div>${esc(j.text)}</div>
        <div class="meta">${esc(j.model)} - ${esc(cfg.lang_names[j.lang] || j.lang)} - ${esc(j.created)} - <span class="state ${esc(j.state)}">${esc(j.state)}</span></div>` +
        (j.audio ? `<audio controls preload="auto" src="${j.audio}"></audio><a href="${j.audio}" download="${esc(j.speaker)}-${esc(j.id)}.wav">Download</a>` : "") +
        (j.log_tail ? `<pre>${esc(j.log_tail)}</pre>` : "");
      box.appendChild(d);
    });
    if (active) sayTimer = setTimeout(refreshSay, 3000);
  }
  $("say-model").onchange = fillSayLangs;
  $("say-text").oninput = () => { $("say-count").textContent = `${$("say-text").value.length} / ${cfg.say_max_chars}`; };
  $("say-go").onclick = async () => {
    $("say-err").textContent = ""; $("say-note").textContent = "";
    $("say-go").disabled = true;
    try {
      const r = await api("/api/say/" + $("say-speaker").value, { method: "POST", json: { model: $("say-model").value, lang: $("say-lang").value, text: $("say-text").value } });
      if (!r.started) $("say-note").innerHTML = `${esc(r.reason)}.<br>On the Spark, from the repo: <code>${esc(r.command)}</code>`;
      else refreshSay();
    } catch (e) { $("say-err").textContent = e.message; }
    $("say-go").disabled = false;
  };

  $("tab-wizard").onclick = () => tab("wizard");
  $("tab-list").onclick = () => tab("list");
  $("tab-say").onclick = () => tab("say");

  api("/api/config").then((c) => { cfg = c; step(1); }).catch((e) => { $("e1").textContent = e.message; });
})();

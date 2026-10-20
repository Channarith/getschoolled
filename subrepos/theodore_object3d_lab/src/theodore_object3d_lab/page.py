"""Browser console for the live 3D camera lab."""

from __future__ import annotations

from .live import CONTROL_SPEC, LiveControls


def render_page() -> str:
    controls = LiveControls()
    image = "\n".join(_field(spec, controls) for spec in CONTROL_SPEC if spec["group"] == "image")
    depth = "\n".join(_field(spec, controls) for spec in CONTROL_SPEC if spec["group"] == "depth")
    return (
        "<!doctype html>\n<html lang=\"en\">\n<head>\n"
        "  <meta charset=\"utf-8\" />\n"
        "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />\n"
        "  <title>Theodore Object3D Lab</title>\n"
        "  <style>\n" + _CSS + "\n  </style>\n</head>\n<body>\n"
        + _html(image, depth)
        + "\n  <script>\n" + _JS + "\n  </script>\n</body>\n</html>\n"
    )


def _field(spec: dict, controls: LiveControls) -> str:
    key = spec["id"]
    value = getattr(controls, key)
    if spec["kind"] == "check":
        checked = " checked" if value else ""
        return (
            f'<label class="check"><input data-control="{key}" type="checkbox"{checked}/>'
            f"{spec['label']}</label>"
        )
    if spec["kind"] == "select":
        options = []
        for opt_value, label in spec["options"]:
            selected = " selected" if float(opt_value) == float(value) else ""
            options.append(f'<option value="{opt_value}"{selected}>{label}</option>')
        return (
            f'<label class="slider"><span>{spec["label"]}</span>'
            f'<select data-control="{key}">{"".join(options)}</select><span></span></label>'
        )
    shown = value
    step = float(spec["step"])
    if step < 1:
        shown = f"{float(value):.2f}"
    return (
        f'<label class="slider"><span>{spec["label"]}</span>'
        f'<input data-control="{key}" type="range" min="{spec["min"]}" max="{spec["max"]}" '
        f'step="{spec["step"]}" value="{value}"/>'
        f'<span id="{key}-v">{shown}</span></label>'
    )


def _html(image: str, depth: str) -> str:
    return f"""
  <header>
    <div>
      <h1>Theodore Object3D Lab</h1>
      <p>The camera stays on. Both cameras draw object boxes: depth when the picture has it, color when it does not. Freeze the color image, click a box, and name it. New angles are saved until that object leaves the frame.</p>
    </div>
    <div class="toolbar">
      <label>Camera
        <select data-control="camera" id="camera">
          <option value="realsense" selected>RealSense</option>
          <option value="oak">OAK-D</option>
        </select>
      </label>
      <label>Quality
        <select data-control="quality" id="quality">
          <option value="clear" selected>Clear</option>
          <option value="smooth">Smooth</option>
          <option value="fast">Fast</option>
        </select>
      </label>
      <label>Detector
        <select data-control="detector" id="detector">
          <option value="auto" selected>Auto</option>
          <option value="depth">Depth</option>
          <option value="color">Color</option>
          <option value="coco">COCO</option>
        </select>
      </label>
      <button class="primary" id="btn-live" type="button">Stop live</button>
      <button id="btn-devices" type="button">Devices</button>
      <button id="btn-tools" type="button">Tools</button>
      <button id="btn-bench" type="button">Synthetic bench</button>
    </div>
    <div class="chips">
      <span class="pill" id="chip-mode">starting</span>
      <span class="pill" id="chip-fps"></span>
      <span class="pill" id="chip-usb"></span>
    </div>
  </header>
  <div class="stage" id="stage">
    <figure>
      <img id="color" alt="Live color" />
      <figcaption><span>Color</span><span id="color-cap">Freeze, then click an object box.</span></figcaption>
    </figure>
    <figure>
      <img id="depth" alt="Live depth" />
      <figcaption><span>Depth</span><span id="depth-cap">Waiting for a frame.</span></figcaption>
    </figure>
  </div>
  <div class="answer" id="answer">Starting the camera.</div>
  <div class="objects" id="objects"></div>
  <div class="controls">
    <section class="panel">
      <h2>Image</h2>
      <p class="hint">Exposure, white balance, and sharpness change the camera. CLAHE and sharpen change only the preview.</p>
      {image}
      <div class="row"><button id="btn-reset" type="button">Reset image and depth</button></div>
    </section>
    <section class="panel">
      <h2>Depth</h2>
      <p class="hint">High density fills more of the picture. Laser and the preset apply to the RealSense. The color under the holes is not a distance.</p>
      {depth}
    </section>
    <section class="panel">
      <h2>Ask</h2>
      <div class="row">
        <input id="question" type="text" value="how far is it?" />
        <button class="primary" id="btn-ask" type="button">Ask</button>
      </div>
      <div class="row">
        <input id="sign" type="text" placeholder="sign text" />
        <input id="target" type="text" value="en" />
      </div>
      <h2>Label for training</h2>
      <p class="hint" id="capture-note">Freeze the color image, click a box, and name it. Angles are saved until that object leaves the frame.</p>
      <div class="row">
        <button id="btn-freeze" type="button">Freeze frame</button>
        <button class="primary" id="btn-capture" type="button">Label and capture angles</button>
        <button id="btn-capture-stop" type="button">Stop capture</button>
      </div>
      <h2>Enroll</h2>
      <div class="row">
        <input id="label" type="text" placeholder="label" value="object" />
        <input id="maker" type="text" placeholder="maker" />
        <input id="year" type="number" placeholder="year" />
      </div>
      <div class="row">
        <input id="celsius" type="number" placeholder="C" />
        <input id="smell" type="text" placeholder="smell" />
        <input id="texture" type="text" placeholder="texture" />
      </div>
      <div class="row">
        <button id="btn-enroll" type="button">Enroll nearest</button>
        <button id="btn-enroll-synth" type="button">Enroll synthetic</button>
      </div>
    </section>
  </div>
  <details class="raw">
    <summary>Details</summary>
    <pre class="out" id="out">Ready.</pre>
  </details>
"""


_CSS = """
  :root { --bg:#07141a; --panel:#10242c; --ink:#e7f6f8; --muted:#8eb0b8; --accent:#3ec6c6; --line:#1e4c56; }
  * { box-sizing:border-box; }
  body { margin:0; min-height:100vh; color:var(--ink); font-family:"Trebuchet MS","Segoe UI",sans-serif;
    background: radial-gradient(900px 480px at 0% -10%, #14515a 0%, transparent 55%), var(--bg); }
  header { padding:1rem 1.25rem .25rem; display:flex; flex-direction:column; gap:.65rem; }
  header h1 { margin:0; font-size:1.55rem; }
  header p { margin:.35rem 0 0; color:var(--muted); max-width:52rem; }
  .toolbar, .row, .chips { display:flex; flex-wrap:wrap; gap:.45rem; align-items:center; }
  label { color:var(--muted); font-size:.85rem; display:flex; gap:.35rem; align-items:center; }
  button, select, input[type="text"], input[type="number"] {
    font:inherit; border-radius:10px; border:1px solid #2d6a74; background:#0c1c22; color:var(--ink); padding:.45rem .7rem; }
  button { cursor:pointer; }
  button.primary { background:#0e6e72; border-color:var(--accent); font-weight:700; }
  button:disabled { opacity:.55; cursor:wait; }
  .pill { padding:.15rem .55rem; border-radius:999px; border:1px solid #2d6a74; color:#b7ece8; font-size:.75rem; }
  .stage { display:grid; grid-template-columns:1fr 1fr; gap:.75rem; padding:.75rem 1.25rem 0; }
  @media (max-width:900px){ .stage, .controls { grid-template-columns:1fr; } }
  .stage figure { margin:0; background:#061014; border:1px solid var(--line); border-radius:16px; overflow:hidden; }
  .stage img { width:100%; aspect-ratio:4/3; object-fit:contain; background:#061014; display:block; cursor:crosshair; }
  .stage.frozen figure:first-child { outline:2px solid var(--accent); outline-offset:2px; }
  .stage figcaption { display:flex; justify-content:space-between; gap:.75rem; padding:.45rem .75rem .7rem;
    color:var(--muted); font-size:.78rem; }
  .stage figcaption span:last-child { text-align:right; }
  .answer { margin:.75rem 1.25rem 0; padding:.85rem 1rem; border-radius:14px; background:#10242c;
    border:1px solid var(--line); font-size:1.15rem; min-height:3.2rem; }
  .objects { display:flex; flex-wrap:wrap; gap:.4rem; padding:.55rem 1.25rem 0; }
  .obj { border:1px solid #2d6a74; border-radius:999px; padding:.2rem .65rem; color:#d5f4f2; font-size:.82rem; cursor:pointer; }
  .obj.picked { border-color:var(--accent); color:#fff; }
  .controls { display:grid; grid-template-columns:1.1fr 1.1fr .9fr; gap:.75rem; padding:.75rem 1.25rem 1rem; }
  .panel { background:color-mix(in srgb, var(--panel) 92%, black); border:1px solid var(--line); border-radius:16px; padding:.85rem 1rem 1rem; }
  .panel h2 { margin:0 0 .35rem; font-size:1rem; color:var(--accent); }
  .hint { margin:0 0 .55rem; color:var(--muted); font-size:.78rem; }
  .slider { display:grid; grid-template-columns:8.2rem 1fr 3.2rem; gap:.4rem; align-items:center; margin:.22rem 0; }
  .slider input[type="range"] { width:100%; accent-color:#3ec6c6; }
  .slider span:last-child { text-align:right; color:var(--ink); }
  .check { display:inline-flex; margin:.15rem .7rem .15rem 0; }
  .panel .row input { width:7.2rem; }
  #question { width:14rem; }
  .raw { margin:0 1.25rem 5rem; color:var(--muted); }
  .out { margin:.4rem 0 0; max-height:24vh; overflow:auto; padding:.75rem; border-radius:12px;
    background:#061014; border:1px solid var(--line); color:#d7f3f4; font:12px/1.45 ui-monospace,Menlo,Consolas,monospace;
    white-space:pre-wrap; }
"""


_JS = """
const answer = document.getElementById("answer");
const out = document.getElementById("out");
let liveOn = true;
let imageTimer = 0;
let controlTimer = 0;
let restartLive = false;
let lastSeq = -1;
let silence = false;
let frozen = false;
let selectedIndex = null;

function payload() {
  const body = {};
  document.querySelectorAll("[data-control]").forEach((el) => {
    if (el.type === "checkbox") body[el.dataset.control] = el.checked;
    else if (el.type === "range") body[el.dataset.control] = Number(el.value);
    else body[el.dataset.control] = el.value;
  });
  return body;
}
function syncDisabled() {
  const rs = document.getElementById("camera").value === "realsense";
  const auto = document.querySelector("[data-control=auto_exposure]").checked;
  const awb = document.querySelector("[data-control=auto_white_balance]").checked;
  const autoRange = document.querySelector("[data-control=auto_range]").checked;
  const lock = {
    exposure: !rs || auto,
    gain: !rs || auto,
    brightness: !rs,
    contrast: !rs,
    sharpness: !rs,
    saturation: !rs,
    auto_exposure: !rs,
    auto_white_balance: !rs,
    white_balance: !rs || awb,
    backlight: !rs,
    preset: !rs,
    laser: !rs,
    emitter: !rs,
    near_m: autoRange,
    far_m: autoRange
  };
  Object.entries(lock).forEach(([key, disabled]) => {
    const el = document.querySelector(`[data-control="${key}"]`);
    if (el) el.disabled = disabled;
  });
}
function setLiveButton() {
  const button = document.getElementById("btn-live");
  button.textContent = liveOn ? "Stop live" : "Start live";
}
function showFrames() {
  const n = Date.now();
  document.getElementById("color").src = "/api/object3d/live/frame.jpg?view=color&n=" + n;
  document.getElementById("depth").src = "/api/object3d/live/frame.jpg?view=depth&n=" + n;
}
function armImages() {
  if (imageTimer || frozen) return;
  showFrames();
  imageTimer = setInterval(() => {
    if (!liveOn || frozen) return;
    showFrames();
  }, 170);
}
function applyHold(isFrozen) {
  const button = document.getElementById("btn-freeze");
  button.textContent = isFrozen ? "Resume live" : "Freeze frame";
  document.getElementById("stage").classList.toggle("frozen", isFrozen);
  if (frozen === isFrozen) return;
  frozen = isFrozen;
  if (isFrozen) {
    clearInterval(imageTimer);
    imageTimer = 0;
    showFrames();
  } else {
    selectedIndex = null;
    armImages();
  }
}
function framePoint(img, event) {
  const rect = img.getBoundingClientRect();
  const nw = img.naturalWidth || img.width;
  const nh = img.naturalHeight || img.height;
  if (!nw || !nh) return null;
  const scale = Math.min(rect.width / nw, rect.height / nh);
  const dw = nw * scale;
  const dh = nh * scale;
  const ox = (rect.width - dw) / 2;
  const oy = (rect.height - dh) / 2;
  const x = (event.clientX - rect.left - ox) / dw;
  const y = (event.clientY - rect.top - oy) / dh;
  if (x < 0 || y < 0 || x > 1 || y > 1) return null;
  return {x: x, y: y};
}
function paintCapture(data) {
  const note = document.getElementById("capture-note");
  const cap = (data && data.capture) || {};
  if (!cap.label) {
    note.textContent = "Freeze the color image, click a box, and name it. Angles are saved until that object leaves the frame.";
    return;
  }
  if (cap.active) {
    note.textContent = "Capturing " + cap.label + " · " + cap.saved + " views. Turn it for another angle. Saving stops when it leaves the frame.";
    return;
  }
  const why = cap.reason ? " " + cap.reason + "." : "";
  note.textContent = cap.saved + " views of " + cap.label + " saved." + why;
}
async function post(url, body) {
  const res = await fetch(url, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(body || {})
  });
  const data = await res.json();
  out.textContent = JSON.stringify(data, null, 2);
  return data;
}
async function startLive() {
  liveOn = true;
  setLiveButton();
  document.getElementById("btn-live").disabled = true;
  answer.textContent = "Starting the camera.";
  armImages();
  const body = payload();
  let data = {ok: false, error: "start failed"};
  try {
    data = await post("/api/object3d/live/start", {camera: body.camera, quality: body.quality});
  } catch (err) {
    data = {ok: false, error: String(err)};
  }
  document.getElementById("btn-live").disabled = false;
  if (!data.ok) {
    liveOn = false;
    setLiveButton();
    answer.textContent = data.error || "The camera did not start.";
    return;
  }
  answer.textContent = "Live. Ask about the nearest object.";
  paintStatus(data);
}
async function stopLive() {
  liveOn = false;
  setLiveButton();
  const data = await post("/api/object3d/live/stop", {});
  paintStatus(data);
  answer.textContent = "Live is off. The last frame stays on screen.";
}
function paintStatus(data) {
  document.getElementById("chip-mode").textContent = data.mode || (data.running ? "live" : "stopped");
  document.getElementById("chip-fps").textContent = data.fps ? data.fps + " fps" : "";
  document.getElementById("chip-usb").textContent = data.usb ? ("USB " + data.usb) : "";
  if (data.note) document.getElementById("color-cap").textContent = data.note;
  const stats = data.stats || {};
  const bits = [];
  if (stats.coverage != null) bits.push(Math.round(stats.coverage * 100) + "% measured");
  if (stats.scene_near_m != null) bits.push(stats.scene_near_m + "–" + stats.scene_far_m + " m");
  if (stats.hint) bits.push(stats.hint);
  document.getElementById("depth-cap").textContent = bits.join(" · ") || "Waiting for a frame.";
  if (data.frozen != null) applyHold(!!data.frozen);
  if (Object.prototype.hasOwnProperty.call(data, "selected")) selectedIndex = data.selected;
  if (data.seq != null && data.seq !== lastSeq) {
    lastSeq = data.seq;
    renderObjects(data.observations || []);
  }
  paintCapture(data);
}
function renderObjects(rows) {
  const host = document.getElementById("objects");
  host.replaceChildren();
  if (!rows.length) {
    const empty = document.createElement("div");
    empty.className = "obj";
    empty.textContent = "No object in range yet.";
    host.appendChild(empty);
    return;
  }
  rows.slice(0, 6).forEach((obs, index) => {
    const card = document.createElement("div");
    card.className = "obj" + (index === selectedIndex ? " picked" : "");
    const dist = obs.distance_m == null ? "no depth" : Number(obs.distance_m).toFixed(2) + " m";
    const how = obs.source || obs.kind || "";
    card.textContent = (obs.name || obs.label || "object") + " · " + dist + " · " + how;
    card.onclick = () => selectObject(index, obs);
    host.appendChild(card);
  });
}
async function selectObject(index, obs) {
  const data = await post("/api/object3d/live/select", {index: index});
  if (!data.ok) {
    answer.textContent = data.error || "That object is not in this frame.";
    return;
  }
  selectedIndex = data.index;
  applyHold(true);
  if (obs && obs.label && obs.label !== "object") {
    document.getElementById("label").value = obs.label;
  }
  renderObjects(data.observations || []);
  answer.textContent = "Selected " + (data.name || data.label || "object") + ". Name it, then capture angles.";
}
async function pollStatus() {
  try {
    const data = await (await fetch("/api/object3d/live/status")).json();
    paintStatus(data);
    if (data.error && !data.running && liveOn) {
      liveOn = false;
      setLiveButton();
      answer.textContent = data.error;
    }
  } catch (err) {
    /* the next poll retries */
  }
}
function scheduleControls() {
  clearTimeout(controlTimer);
  controlTimer = setTimeout(async () => {
    const doRestart = restartLive && liveOn;
    restartLive = false;
    await post("/api/object3d/live/controls", payload());
    if (doRestart) await startLive();
  }, 220);
}
document.querySelectorAll("[data-control]").forEach((el) => {
  const event = el.type === "range" ? "input" : "change";
  el.addEventListener(event, () => {
    if (silence) return;
    const value = document.getElementById(el.dataset.control + "-v");
    if (value && el.type === "range") value.textContent = el.value;
    syncDisabled();
    if (el.dataset.control === "camera" || el.dataset.control === "quality") restartLive = true;
    scheduleControls();
  });
});
document.getElementById("btn-live").onclick = () => liveOn ? stopLive() : startLive();
document.getElementById("btn-devices").onclick = () => post("/api/object3d/devices");
document.getElementById("btn-tools").onclick = () => post("/api/object3d/tools");
document.getElementById("btn-bench").onclick = async () => {
  const data = await post("/api/object3d/bench", {});
  answer.textContent = data.ok ? "Synthetic bench passed." : "Synthetic bench failed.";
};
document.getElementById("btn-ask").onclick = async () => {
  const data = await post("/api/object3d/ask", {
    question: document.getElementById("question").value,
    sign: document.getElementById("sign").value,
    target: document.getElementById("target").value
  });
  answer.textContent = data.answer || data.error || "No answer.";
  if (data.observations) renderObjects(data.observations);
};
document.getElementById("btn-reset").onclick = async () => {
  const data = await post("/api/object3d/live/reset", {});
  silence = true;
  Object.entries(data.controls || {}).forEach(([key, value]) => {
    const el = document.querySelector(`[data-control="${key}"]`);
    if (!el || key === "camera" || key === "quality" || key === "detector") return;
    if (el.type === "checkbox") el.checked = !!value;
    else el.value = value;
    const shown = document.getElementById(key + "-v");
    if (shown) shown.textContent = el.value;
  });
  silence = false;
  syncDisabled();
};
function enroll(camera) {
  const year = document.getElementById("year").value;
  const celsius = document.getElementById("celsius").value;
  return post("/api/object3d/enroll", {
    label: document.getElementById("label").value,
    maker: document.getElementById("maker").value,
    year: year ? Number(year) : 0,
    celsius: celsius === "" ? null : Number(celsius),
    smell: document.getElementById("smell").value,
    texture: document.getElementById("texture").value,
    camera: camera,
    detector: document.getElementById("detector").value
  }).then((data) => {
    answer.textContent = data.ok ? "Enrolled " + (data.labels || []).join(", ") : (data.error || "Enroll failed.");
    if (data.observations) renderObjects(data.observations);
  });
}
document.getElementById("color").onclick = async (event) => {
  const point = framePoint(event.currentTarget, event);
  if (!point) return;
  if (!frozen) {
    const held = await post("/api/object3d/live/freeze", {frozen: true});
    applyHold(!!held.frozen);
    answer.textContent = "Frame held. Click the object box.";
    return;
  }
  const data = await post("/api/object3d/live/pick", point);
  if (!data.ok) {
    answer.textContent = data.error || "Click an object box.";
    return;
  }
  selectedIndex = data.index;
  if (data.label && data.label !== "object") document.getElementById("label").value = data.label;
  showFrames();
  renderObjects(data.observations || []);
  answer.textContent = "Selected " + (data.name || data.label || "object") + ". Name it, then capture angles.";
};
document.getElementById("btn-freeze").onclick = async () => {
  const data = await post("/api/object3d/live/freeze", {frozen: !frozen});
  applyHold(!!data.frozen);
  answer.textContent = data.frozen ? "Frame held. Click an object on the color image." : "Live.";
};
document.getElementById("btn-capture").onclick = async () => {
  const label = document.getElementById("label").value.trim();
  if (!label) {
    answer.textContent = "Type a label first.";
    return;
  }
  const year = document.getElementById("year").value;
  const celsius = document.getElementById("celsius").value;
  const data = await post("/api/object3d/live/label", {
    label: label,
    index: selectedIndex,
    maker: document.getElementById("maker").value,
    year: year ? Number(year) : 0,
    celsius: celsius === "" ? null : Number(celsius),
    smell: document.getElementById("smell").value,
    texture: document.getElementById("texture").value
  });
  if (!data.ok) {
    answer.textContent = data.error || "Could not save that label.";
    return;
  }
  applyHold(false);
  paintCapture(data);
  answer.textContent = "Saving angles of " + data.capture.label + ". Turn it, then take it out of the frame to stop.";
};
document.getElementById("btn-capture-stop").onclick = async () => {
  const data = await post("/api/object3d/live/capture/stop", {});
  paintCapture(data);
  answer.textContent = data.capture && data.capture.saved
    ? data.capture.saved + " views saved."
    : "Capture stopped.";
};
document.getElementById("btn-enroll").onclick = () => enroll(document.getElementById("camera").value);
document.getElementById("btn-enroll-synth").onclick = () => enroll("");
syncDisabled();
setLiveButton();
startLive();
setInterval(pollStatus, 800);
"""

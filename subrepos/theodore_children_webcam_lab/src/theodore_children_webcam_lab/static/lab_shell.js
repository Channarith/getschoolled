// Minimal play shell shared by EVERY Vision Play game (demo and signed-in, phone and desktop).
//
// The play screen shows only: the scene, the Sala avatar, ONE combined widget (top right), a tiny Air touch | Screen touch pill,
// and a thin progress line at the very top. Everything else (game choice, pace, voice, typing, help, exit) lives in the
// widget's menu. Double-tap anywhere on the scene toggles full screen. Add ?classic=1 to get the old controls back.
const PARAMS = (() => { try { return new URLSearchParams(location.search); } catch (_) { return new URLSearchParams(); } })();
const CLASSIC = PARAMS.get("classic") === "1";
const POS_KEY = "lab_widget_pos_v1";
const $ = (id) => document.getElementById(id);

function post(message) {
  try { window.ReactNativeWebView?.postMessage(JSON.stringify(message)); } catch (_) { /* not inside the app */ }
  try { if (window.parent && window.parent !== window) window.parent.postMessage(message, "*"); } catch (_) { /* no parent */ }
}

function button(id, label, text, extraClass = "") {
  const el = document.createElement("button");
  el.type = "button"; el.id = id; el.className = `lab-btn ${extraClass}`.trim();
  el.setAttribute("aria-label", label); el.title = label; el.textContent = text;
  return el;
}

export function mountLabShell() {
  const play = $("play");
  if (CLASSIC || !play || $("lab-widget")) return null;
  document.body.classList.add("lab-minimal");
  let verbose = false;
  try { verbose = localStorage.getItem("gs_diag_verbose") === "1"; } catch (_) { /* storage blocked */ }
  if (PARAMS.get("debug") === "1" || verbose) document.body.classList.add("lab-debug");

  // ---- thin progress line, very top of the screen ----
  const progress = document.createElement("div");
  progress.id = "lab-progress"; progress.setAttribute("role", "progressbar");
  progress.setAttribute("aria-label", "Game progress"); progress.setAttribute("aria-valuemin", "0"); progress.setAttribute("aria-valuemax", "100");
  progress.setAttribute("aria-valuenow", "0");
  progress.innerHTML = "<i></i>";
  play.prepend(progress);
  let lastPercent = -1;
  window.addEventListener("lab:progress", (event) => {
    const pct = Math.max(0, Math.min(100, Math.round(Number(event.detail?.percent) || 0)));
    if (pct === lastPercent) return;
    lastPercent = pct;
    progress.firstElementChild.style.width = `${pct}%`;
    progress.setAttribute("aria-valuenow", String(pct));
    progress.title = `${pct}%`;
  });

  // ---- the one combined widget ----
  const widget = document.createElement("div");
  widget.id = "lab-widget"; widget.setAttribute("role", "group"); widget.setAttribute("aria-label", "Play controls");
  const handle = button("lab-handle", "Drag to move", "⋮⋮", "lab-handle");
  const dot = document.createElement("span");
  dot.id = "lab-dot"; dot.className = "lab-dot"; dot.setAttribute("role", "status"); dot.setAttribute("aria-label", "Camera not started");
  const mic = button("lab-mic", "Answer with your voice", "🎤");
  const cam = button("lab-cam", "Camera on or off", "📷");
  const more = button("lab-more", "Game menu", "⋯");
  more.setAttribute("aria-haspopup", "true"); more.setAttribute("aria-expanded", "false");
  widget.append(handle, dot);
  const clock = $("play-clock");
  if (clock) widget.append(clock);
  widget.append(mic, cam, more);
  play.append(widget);

  // ---- menu sheet: every choice lives here ----
  const menu = document.createElement("div");
  menu.id = "lab-menu"; menu.setAttribute("role", "dialog"); menu.setAttribute("aria-label", "Game menu");
  const controls = play.querySelector(".controls");
  const extras = document.createElement("div");
  extras.className = "lab-row";
  for (const id of ["clone-voice-slot", "mute"]) { const el = $(id); if (el) extras.append(el); }
  const actions = document.createElement("div");
  actions.className = "lab-row lab-actions";
  const how = button("lab-how", "How to play", "How to play", "lab-wide");
  const check = button("lab-check", "Camera check", "Camera check", "lab-wide");
  const exit = button("lab-exit", "Exit the game", "Exit", "lab-wide");
  actions.append(how, check, exit);
  menu.append(extras);
  if (controls) menu.append(controls);
  menu.append(actions);
  play.append(menu);

  function setMenu(open) {
    menu.classList.toggle("open", open);
    more.setAttribute("aria-expanded", String(open));
  }
  more.addEventListener("click", (event) => { event.stopPropagation(); setMenu(!menu.classList.contains("open")); });
  document.addEventListener("pointerdown", (event) => {
    if (!menu.classList.contains("open")) return;
    if (event.target.closest?.("#lab-menu,#lab-widget")) return;
    setMenu(false);
  });
  document.addEventListener("keydown", (event) => { if (event.key === "Escape") setMenu(false); });

  mic.addEventListener("click", () => ($("mic") || $("hear"))?.click());
  cam.addEventListener("click", () => {
    const api = window.labShellApi;
    if (api) api.setCamera(!api.cameraOn());
  });
  window.addEventListener("lab:camera", (event) => {
    const on = Boolean(event.detail?.on);
    cam.setAttribute("aria-pressed", String(!on)); cam.classList.toggle("off", !on);
    cam.textContent = on ? "📷" : "🚫";
  });
  how.addEventListener("click", () => { setMenu(false); document.querySelector(".pq-help, .gt-help")?.click(); });
  check.addEventListener("click", () => {
    setMenu(false);
    if (window.ReactNativeWebView || (window.parent && window.parent !== window)) post({type: "salareen-camera-check"});
    else window.open("/diag/vision", "_blank", "noopener");
  });
  exit.addEventListener("click", () => {
    setMenu(false);
    if (window.ReactNativeWebView || (window.parent && window.parent !== window)) post({type: "salareen-exit"});
    else $("home")?.click();
  });

  // ---- tiny status: only when tracking is loading for a while, or unavailable ----
  const status = document.createElement("div");
  status.id = "lab-status"; status.setAttribute("role", "status"); status.hidden = true;
  play.append(status);
  let loadingTimer = 0;
  window.addEventListener("lab:health", (event) => {
    const state = event.detail?.state;
    clearTimeout(loadingTimer);
    dot.dataset.state = state || "";
    if (state === "ready") {
      status.hidden = true; dot.setAttribute("aria-label", "Camera tracking ready");
    } else if (state === "touch") {
      status.textContent = "Camera tracking is off here. Just touch the screen to play.";
      status.hidden = false; dot.setAttribute("aria-label", "Playing by touch");
      setTimeout(() => { if (dot.dataset.state === "touch") status.hidden = true; }, 7000);
    } else {
      dot.setAttribute("aria-label", "Getting camera ready");
      loadingTimer = setTimeout(() => { status.textContent = "Getting the camera ready. You can already touch the screen."; status.hidden = false; }, 5000);
    }
  });

  // ---- drag the widget; remember where it was left ----
  try {
    const saved = JSON.parse(sessionStorage.getItem(POS_KEY) || "null");
    if (saved && Number.isFinite(saved.x) && Number.isFinite(saved.y)) place(saved.x, saved.y);
  } catch (_) { /* storage blocked */ }
  function place(x, y) {
    const w = widget.offsetWidth || 160; const h = widget.offsetHeight || 44;
    const nx = Math.max(4, Math.min(window.innerWidth - w - 4, x));
    const ny = Math.max(4, Math.min(window.innerHeight - h - 4, y));
    widget.style.left = `${nx}px`; widget.style.top = `${ny}px`; widget.style.right = "auto";
    return {x: nx, y: ny};
  }
  let drag = null;
  handle.addEventListener("pointerdown", (event) => {
    const rect = widget.getBoundingClientRect();
    drag = {id: event.pointerId, dx: event.clientX - rect.left, dy: event.clientY - rect.top};
    handle.setPointerCapture?.(event.pointerId);
    event.preventDefault();
  });
  handle.addEventListener("pointermove", (event) => {
    if (!drag || event.pointerId !== drag.id) return;
    place(event.clientX - drag.dx, event.clientY - drag.dy);
  });
  const endDrag = (event) => {
    if (!drag || event.pointerId !== drag.id) return;
    const rect = widget.getBoundingClientRect();
    try { sessionStorage.setItem(POS_KEY, JSON.stringify({x: rect.left, y: rect.top})); } catch (_) { /* storage blocked */ }
    drag = null;
  };
  handle.addEventListener("pointerup", endDrag);
  handle.addEventListener("pointercancel", endDrag);
  window.addEventListener("resize", () => { const r = widget.getBoundingClientRect(); if (widget.style.left) place(r.left, r.top); });

  // ---- double-tap anywhere on the scene = full screen (dblclick is never sent on iOS or in web views) ----
  const stage = $("stage");
  let lastTap = null;
  stage?.addEventListener("pointerdown", (event) => {
    if (event.target.closest?.("button,select,input,a,.pq-target,.pq-help,#lab-widget,#lab-menu,.pq-tutorial,.pq-win,.gt-overlay,.gt-help,#touch-mode")) { lastTap = null; return; }
    const now = performance.now();
    if (lastTap && now - lastTap.t < 320 && Math.hypot(event.clientX - lastTap.x, event.clientY - lastTap.y) < 42) {
      lastTap = null;
      $("fullscreen")?.click();
      return;
    }
    lastTap = {t: now, x: event.clientX, y: event.clientY};
  }, true);

  // ---- Sala: the avatar is the way to ask ----
  document.addEventListener("click", (event) => {
    if (event.target.closest?.(".pq-sala")) ($("mic") || $("hear"))?.click();
  });
  return {widget, menu, progress, status};
}

if (typeof document !== "undefined") {
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", () => mountLabShell(), {once: true});
  else mountLabShell();
}

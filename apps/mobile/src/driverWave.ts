/**
 * On the Go opens the studio lesson inside the app. That page still paints
 * pictures, captions, and quiz text on older site builds. This script hides
 * that lesson and leaves a waveform, and it keeps the camera from pausing
 * the class when the driver looks at the road.
 */
export function driverWaveScript(): string {
  return `(function(){
    if (!/[?&]presentation=audio(?:&|$)/.test(location.search)) return;
    var css = [
      "html.salareen-drive-wave, html.salareen-drive-wave body { background:#070b14 !important; overflow:hidden !important; }",
      "html.salareen-drive-wave .study-bg,",
      "html.salareen-drive-wave header.mast,",
      "html.salareen-drive-wave .library-panel,",
      "html.salareen-drive-wave #teach-title,",
      "html.salareen-drive-wave .lesson-window-controls,",
      "html.salareen-drive-wave .teacher-stage-grid,",
      "html.salareen-drive-wave .lesson-stage-content,",
      "html.salareen-drive-wave #lesson-caption,",
      "html.salareen-drive-wave #quiz-box,",
      "html.salareen-drive-wave #game-box,",
      "html.salareen-drive-wave .sample-banner,",
      "html.salareen-drive-wave .sample-clock,",
      "html.salareen-drive-wave .proceed-cue,",
      "html.salareen-drive-wave .page-welcome,",
      "html.salareen-drive-wave .lesson-toolbar,",
      "html.salareen-drive-wave .talk-panel,",
      "html.salareen-drive-wave #theodore-live-audio,",
      "html.salareen-drive-wave #student-cam,",
      "html.salareen-drive-wave .toast,",
      "html.salareen-drive-wave #review-root,",
      "html.salareen-drive-wave .picture-stage,",
      "html.salareen-drive-wave .lesson-photo,",
      "html.salareen-drive-wave .theodore-avatar-wrap { display:none !important; }",
      "#salareen-drive-wave { position:fixed; inset:0; z-index:2147483646; display:flex;",
      "align-items:center; justify-content:center; gap:7px; padding:0 8vw;",
      "background:#070b14; }",
      "#salareen-drive-wave i { display:block; width:9px; border-radius:99px;",
      "background:linear-gradient(180deg,#e8fdff,#3ec6e0); height:18px;",
      "transform-origin:center; animation:salareenWave .8s ease-in-out infinite; }",
      "#salareen-drive-wave i:nth-child(odd) { animation-delay:.14s; height:28px; }",
      "#salareen-drive-wave i:nth-child(3n) { animation-delay:.28s; height:46px; }",
      "#salareen-drive-wave i:nth-child(4n) { animation-delay:.07s; height:36px; }",
      "@keyframes salareenWave { 50% { transform:scaleY(1.8); } }",
      "@media (prefers-reduced-motion: reduce) { #salareen-drive-wave i { animation:none !important; } }"
    ].join("");
    var style = document.createElement("style");
    style.textContent = css;
    (document.head || document.documentElement).appendChild(style);
    document.documentElement.classList.add("salareen-drive-wave");
    if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
      var origGum = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
      navigator.mediaDevices.getUserMedia = function(constraints) {
        if (constraints && constraints.video) {
          return Promise.reject(new Error("camera stays off in On the Go"));
        }
        return origGum(constraints);
      };
    }
    var origFetch = window.fetch;
    if (typeof origFetch === "function") {
      window.fetch = function(input, init) {
        var url = typeof input === "string" ? input : (input && input.url) || "";
        if (url.indexOf("/learn/camera") >= 0) {
          return Promise.resolve(new Response(JSON.stringify({hold:false, state:"present"}), {
            status: 200,
            headers: {"content-type":"application/json"}
          }));
        }
        return origFetch.apply(this, arguments);
      };
    }
    function studioWaveReady() {
      var stage = document.getElementById("audio-stage");
      if (!stage) return false;
      var cs = getComputedStyle(stage);
      return cs.position === "fixed" && cs.display !== "none";
    }
    function mount() {
      if (studioWaveReady()) {
        var stale = document.getElementById("salareen-drive-wave");
        if (stale) stale.remove();
        return;
      }
      if (document.getElementById("salareen-drive-wave")) return;
      var wave = document.createElement("div");
      wave.id = "salareen-drive-wave";
      wave.setAttribute("aria-label", "Audio playing");
      for (var n = 0; n < 17; n++) wave.appendChild(document.createElement("i"));
      wave.addEventListener("click", function() {
        var pause = document.getElementById("btn-pause");
        if (pause) pause.click();
      });
      (document.body || document.documentElement).appendChild(wave);
    }
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", mount);
    else mount();
    var ticks = 0;
    var timer = setInterval(function() {
      ticks += 1;
      mount();
      if (studioWaveReady() || ticks > 40) clearInterval(timer);
    }, 500);
  })(); true;`;
}

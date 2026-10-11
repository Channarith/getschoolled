/**
 * On the Go opens the studio lesson inside the app. That page still paints
 * pictures, captions, and quiz text on older site builds. This script hides
 * that lesson and leaves a waveform. The webcam stays on so presence can
 * see the learner.
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
      "@media (prefers-reduced-motion: reduce) { #salareen-drive-wave i { animation:none !important; } }",
      "html.salareen-drive-wave #theodore-live-audio { display:block !important; visibility:visible !important; pointer-events:auto !important; }",
      "html.salareen-drive-wave #student-cam { display:block !important; visibility:visible !important; pointer-events:auto !important;",
      "position:fixed !important; z-index:2147483647 !important; top:max(64px, env(safe-area-inset-top)) !important;",
      "right:12px !important; left:auto !important; width:112px !important; }",
      "html.salareen-drive-wave #course-map { display:flex !important; position:fixed !important; z-index:2147483647 !important;",
      "left:12px !important; right:12px !important; bottom:max(84px, calc(72px + env(safe-area-inset-bottom))) !important; }",
      "#salareen-drive-choices { position:fixed; z-index:2147483647; top:max(8px, env(safe-area-inset-top));",
      "left:10px; right:10px; display:flex; gap:8px; }",
      "#salareen-drive-choices label { flex:1; min-width:0; display:flex; flex-direction:column; gap:4px;",
      "color:#d7e7ea; font:600 11px/1.2 system-ui,sans-serif; }",
      "#salareen-drive-choices select { width:100%; min-height:40px; border-radius:10px; border:1px solid #24515c;",
      "background:#101820; color:#f4fbff; font-size:15px; }"
    ].join("");
    var style = document.createElement("style");
    style.textContent = css;
    (document.head || document.documentElement).appendChild(style);
    document.documentElement.classList.add("salareen-drive-wave");
    function keepPresence() {
      var box = document.getElementById("student-cam");
      var video = document.getElementById("student-cam-video");
      if (!box || !video) return;
      if (box.parentElement !== document.body) document.body.appendChild(box);
      box.hidden = false;
      var tracks = video.srcObject && video.srcObject.getVideoTracks ? video.srcObject.getVideoTracks() : [];
      if (tracks.some(function(track) { return track.readyState === "live"; })) return;
      if (window.__SALAREEN_PRESENCE_OURS__ || !navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) return;
      window.__SALAREEN_PRESENCE_OURS__ = true;
      navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" }, audio: false }).then(function(stream) {
        var current = video.srcObject && video.srcObject.getVideoTracks ? video.srcObject.getVideoTracks() : [];
        if (current.some(function(track) { return track.readyState === "live"; })) {
          stream.getTracks().forEach(function(track) { track.stop(); });
          window.__SALAREEN_PRESENCE_OURS__ = false;
          return;
        }
        video.srcObject = stream;
        video.play().catch(function() {});
        box.hidden = false;
        watchPresence(video, stream);
      }).catch(function() {
        window.__SALAREEN_PRESENCE_OURS__ = false;
        var status = document.getElementById("student-cam-status");
        if (status) status.textContent = "Camera is required. Allow it to continue.";
      });
    }
    function watchPresence(video, owned) {
      if (window.__SALAREEN_PRESENCE_WATCH__) return;
      window.__SALAREEN_PRESENCE_WATCH__ = true;
      var Detector = window.FaceDetector;
      var detector = typeof Detector === "function" ? new Detector({ fastMode: true, maxDetectedFaces: 1 }) : null;
      setInterval(function() {
        if (video.srcObject !== owned) {
          owned.getTracks().forEach(function(track) { track.stop(); });
          window.__SALAREEN_PRESENCE_OURS__ = false;
          return;
        }
        var status = document.getElementById("student-cam-status");
        function paint(present) {
          if (status) status.textContent = present ? "Present." : "No face in the camera.";
        }
        if (!detector || video.readyState < 2) {
          paint(video.readyState >= 2);
          return;
        }
        detector.detect(video).then(function(faces) {
          var seen = !!(faces && faces.length);
          paint(seen);
          var learner = "";
          try { learner = localStorage.getItem("studio_learner_id") || ""; } catch (e) {}
          fetch("/api/studio/learn/camera", {
            method: "POST",
            headers: { "content-type": "application/json" },
            body: JSON.stringify({
              session_id: "studio-teach-audio:" + (learner || "learner"),
              participant_id: learner || "learner",
              timestamp_ms: Date.now(),
              signal: {
                face_count: seen ? faces.length : 0,
                liveness_state: seen ? "live" : "missing",
                detector_source: "face_detector",
                screen_focus_score: document.visibilityState === "hidden" ? 0.15 : 1
              }
            })
          }).catch(function() {});
        }).catch(function() { paint(video.readyState >= 2); });
      }, 1000);
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
    function option(value, label) {
      var node = document.createElement("option");
      node.value = value;
      node.textContent = label;
      return node;
    }
    function mountChoices() {
      if (document.getElementById("drive-bar") || document.getElementById("salareen-drive-choices")) return;
      var lang = document.getElementById("teach-lang") || document.getElementById("teach-lang-stage");
      var items = document.querySelectorAll("#library-list .item[data-lib]");
      if ((!lang || !lang.options || !lang.options.length) && !items.length) return;
      var bar = document.createElement("div");
      bar.id = "salareen-drive-choices";
      var courseLabel = document.createElement("label");
      courseLabel.appendChild(document.createTextNode("Course"));
      var course = document.createElement("select");
      course.setAttribute("aria-label", "Course");
      for (var i = 0; i < items.length; i++) {
        var id = items[i].getAttribute("data-lib") || "";
        var title = items[i].querySelector("strong");
        course.appendChild(option(id, title ? title.textContent : id));
        if (items[i].classList.contains("active")) course.value = id;
      }
      course.addEventListener("change", function() {
        var match = document.querySelector('#library-list .item[data-lib="' + course.value + '"]');
        if (match) match.click();
      });
      courseLabel.appendChild(course);
      var langLabel = document.createElement("label");
      langLabel.appendChild(document.createTextNode("Language"));
      var langPick = document.createElement("select");
      langPick.setAttribute("aria-label", "Lesson language");
      if (lang) {
        for (var n = 0; n < lang.options.length; n++) {
          langPick.appendChild(option(lang.options[n].value, lang.options[n].text));
        }
        langPick.value = lang.value;
        langPick.addEventListener("change", function() {
          lang.value = langPick.value;
          lang.dispatchEvent(new Event("change", {bubbles: true}));
        });
      }
      langLabel.appendChild(langPick);
      bar.appendChild(courseLabel);
      bar.appendChild(langLabel);
      (document.body || document.documentElement).appendChild(bar);
    }
    function mountProgress() {
      if (document.getElementById("course-map") || document.getElementById("salareen-course-map")) return;
      var dock = document.createElement("aside");
      dock.id = "salareen-course-map";
      dock.style.cssText = "position:fixed;z-index:2147483647;left:12px;right:12px;bottom:max(84px, calc(72px + env(safe-area-inset-bottom)));display:flex;flex-direction:column;gap:6px;max-height:38vh;padding:10px 12px;border-radius:16px;border:1px solid #5eead4;background:#07111ef2;color:#f8fafc;font:600 13px/1.3 system-ui,sans-serif";
      var head = document.createElement("div");
      head.id = "salareen-course-percent";
      head.textContent = "0% of the course";
      var toggle = document.createElement("button");
      toggle.type = "button";
      toggle.textContent = "Outline";
      var list = document.createElement("div");
      list.hidden = true;
      toggle.addEventListener("click", function() { list.hidden = !list.hidden; });
      head.appendChild(toggle);
      dock.appendChild(head);
      dock.appendChild(list);
      (document.body || document.documentElement).appendChild(dock);
      function paintPercent() {
        var adapt = document.getElementById("teach-adapt");
        var text = adapt ? adapt.textContent || "" : "";
        var found = text.match(/(\\d+)% of the course/);
        if (found) head.firstChild.textContent = found[1] + "% of the course ";
      }
      setInterval(paintPercent, 1000);
      var params = new URLSearchParams(location.search);
      var courseId = params.get("course") || "";
      if (!courseId) return;
      fetch("/api/studio/courses/" + encodeURIComponent(courseId)).then(function(response) {
        return response.ok ? response.json() : null;
      }).then(function(course) {
        var slides = course && course.slides || [];
        slides.forEach(function(slide, index) {
          var button = document.createElement("button");
          button.type = "button";
          button.textContent = (index + 1) + ". " + (slide.title || "Slide");
          button.style.cssText = "display:block;width:100%;text-align:left;margin:4px 0";
          button.addEventListener("click", function() {
            var title = slide.title || "";
            if (window.TheodoreLiveAudio && window.TheodoreLiveAudio.noteActivity) {
              window.TheodoreLiveAudio.noteActivity({
                id: "open-" + title,
                prompt: "The learner skipped to this part of the course. Read it aloud, then wait. " + title
              });
            }
            fetch("/api/studio/teach/topic", {
              method: "POST",
              headers: {"content-type": "application/json"},
              body: JSON.stringify({session_id: "studio-teach-audio", text: title})
            }).catch(function() {});
          });
          list.appendChild(button);
        });
      }).catch(function() {});
    }
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", mount);
    else mount();
    var ticks = 0;
    var timer = setInterval(function() {
      ticks += 1;
      mount();
      mountChoices();
      mountProgress();
      keepPresence();
      if ((studioWaveReady() && document.getElementById("drive-bar")) || ticks > 40) clearInterval(timer);
    }, 500);
  })(); true;`;
}

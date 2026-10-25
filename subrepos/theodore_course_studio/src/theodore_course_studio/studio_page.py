"""Embedded Course Studio dashboard (review + teach)."""

from __future__ import annotations

STUDIO_CSS = """

  body.theme-study { margin:0; color:#241c16;
    font-family: "Iowan Old Style", Palatino, "Palatino Linotype", Georgia, serif;
    background:
      radial-gradient(ellipse at 18% -8%, rgba(255,248,230,.95), transparent 46%),
      radial-gradient(ellipse at 100% 0%, rgba(196,154,90,.28), transparent 34%),
      linear-gradient(180deg, #f8f3ea 0%, #f3e7d6 48%, #eadcc8 100%); }
  button, select, input, textarea, .meta, .status, .review-overlay, .lesson-toolbar {
    font-family: "Avenir Next", "Segoe UI", sans-serif; }
  .study-bg { position:fixed; inset:0; z-index:0; pointer-events:none; overflow:hidden; }
  .study-bg .shelf { position:absolute; top:0; height:100%; width:92px; opacity:.34; }
  .study-bg .shelf-left { left:0; }
  .study-bg .shelf-right { right:0; transform:scaleX(-1); }
  .study-bg .wash { position:absolute; inset:0;
    background:linear-gradient(90deg, rgba(248,243,234,.2), rgba(248,243,234,.72) 8%, rgba(248,243,234,.72) 92%, rgba(248,243,234,.2)); }
  header, .layout { position:relative; z-index:1; }
  header.mast { display:flex; gap:24px; align-items:center; justify-content:space-between;
    margin:18px 22px 0; padding:22px 26px; border-radius:22px;
    background:linear-gradient(135deg, rgba(255,252,247,.94), rgba(255,246,232,.9));
    border:1px solid rgba(90,62,32,.12);
    box-shadow:0 16px 40px rgba(70,46,22,.08); }
  header h1 { margin:0; font-size:34px; letter-spacing:-0.02em; color:#1e3a5f; font-weight:650; }
  header .eyebrow { margin:0 0 4px; color:#8c5a2b; font:600 12px "Avenir Next", "Segoe UI", sans-serif;
    letter-spacing:.14em; text-transform:uppercase; }
  header p { margin:8px 0 0; color:#5c5146; font-size:16px; line-height:1.45; max-width:46rem; }
  .mast-art { flex:0 0 168px; }
  .mast-art svg { width:168px; height:112px; display:block; }
  .layout { display:grid; grid-template-columns: 1.05fr 1.15fr; gap:16px; padding:16px 22px 28px; }
  body.public-course header.mast { display:none; }
  html:has(body.public-course), body.public-course { height:100%; }
  body.public-course { overflow:hidden; }
  body.public-course .layout {
    display:flex; flex-direction:column; height:100%; min-height:0;
    box-sizing:border-box; padding:8px; gap:8px;
  }
  body.public-course .library-panel { flex:0 0 auto; padding:8px 12px; }
  body.public-course .library-panel h2,
  body.public-course .library-panel > .row,
  body.public-course .library-panel > .status,
  body.public-course #library-list { display:none; }
  .library-bar { display:none; }
  body.public-course .library-bar { display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
  body.public-course .library-bar select { min-width:min(100%, 16rem); max-width:24rem; }
  body.public-course.library-collapsed .library-panel { display:none; }
  body.public-course .layout > .panel:not(.library-panel) {
    flex:1 1 auto; min-height:0; display:flex; flex-direction:column;
  }
  body.public-course #teach-stage-home {
    flex:1 1 auto; min-height:0; display:flex; flex-direction:column;
  }
  body.public-course .teach-stage { flex:1 1 auto; min-height:0; overflow:auto; }
  #library-show { display:none; position:fixed; top:12px; left:12px; z-index:40; }
  body.public-course.library-collapsed #library-show { display:inline-flex; }
  body.chrome-hidden #library-show,
  body.audio-only #library-show { display:none !important; }
  @media (max-width: 980px) {
    .layout { grid-template-columns: 1fr; }
    .study-bg .shelf, .mast-art { display:none; }
    header.mast { margin:12px; padding:18px; }
  }
  .panel { background:rgba(255,252,247,.92); border:1px solid rgba(90,62,32,.12); border-radius:22px;
           padding:16px 16px 14px; box-shadow:0 14px 36px rgba(70,46,22,.07); }
  .panel h2 { margin:0 0 10px; font-size:20px; color:#1e3a5f; display:flex; align-items:center; gap:8px; }
  .panel h2 .mark { width:28px; height:28px; display:inline-grid; place-items:center; }
  .row { display:flex; gap:8px; flex-wrap:wrap; align-items:center; margin:6px 0; }
  button, select, input, textarea { font: 15px/1.2 "Avenir Next", "Segoe UI", sans-serif; }
  button { background:#1e3a5f; color:#f8f4ec; border:1px solid #162c49; border-radius:999px;
           padding:9px 16px; cursor:pointer; box-shadow:0 6px 14px rgba(30,58,95,.16); }
  button.secondary { background:#fffaf3; color:#1e3a5f; border-color:#e0d2bf; box-shadow:none; }
  button.danger { background:#8c3a2f; border-color:#6e2d24; color:#fff8f4; }
  select, input { background:#fffaf3; color:#241c16; border:1px solid #e0d2bf; border-radius:12px;
                  padding:7px 10px; }
  textarea { width:100%; min-height:72px; background:#fffaf3; color:#241c16;
             border:1px solid #e0d2bf; border-radius:12px; padding:8px; }
  label { color:#5c5146; font-family:"Avenir Next", "Segoe UI", sans-serif; font-size:14px; }
  .pill { font-size:11px; padding:2px 8px; border-radius:999px; border:1px solid #e0d2bf; background:#fff6e8; color:#5c3b1e; }
  .pill.good, .pill.ready { background:#e7f3ea; border-color:#8fbf9b; color:#1d4d35; }
  .pill.bad { background:#fde8e4; border-color:#e7b2a8; color:#8c3a2f; }
  .pill.moderate { background:#fff1d6; border-color:#e7c98a; color:#8c5a2b; }
  .modality-row { display:none; flex-wrap:wrap; gap:6px; margin:8px 0; }
  .examples-box { display:none; margin-top:10px; padding:12px 14px; border-radius:14px;
                  background:#fff6e8; border:1px solid #ead7b8; font-size:16px; line-height:1.45; color:#3a3128; }
  .examples-box ol { margin:6px 0 0 1.1rem; padding:0; }
  .examples-box li { margin:4px 0; }
  .list { max-height:280px; overflow:auto; font-size:15px; }
  .library { max-height:calc(100vh - 250px); padding-right:4px; }
  .item { display:flex; gap:12px; align-items:center; padding:12px; margin:0 0 8px;
          border:1px solid transparent; border-radius:16px; cursor:pointer; background:#fffdf9; }
  .item .mark { width:46px; height:46px; border-radius:14px; display:grid; place-items:center; flex:none;
                background:#f4eadc; color:#1e3a5f; }
  .item .mark svg { width:28px; height:28px; display:block; }
  .item.featured { border-color:#e7d3a4; background:linear-gradient(90deg,#fff8ea,#fffdf9); }
  .item.featured .mark { background:#1e3a5f; color:#f8f1e4; }
  .item .focus { display:inline-block; margin-left:8px; color:#8c5a2b; font-size:11px;
                 letter-spacing:.08em; text-transform:uppercase; font-family:"Avenir Next", "Segoe UI", sans-serif; }
  .item:hover, .item.active { background:#f7f1e6; border-color:#d9c7a6; }
  .item.active { box-shadow:inset 3px 0 0 #1e3a5f; }
  .item .meta { color:#6d5e50; font-size:13px; margin-top:3px; font-family:"Avenir Next", "Segoe UI", sans-serif; }
  .pages { max-height:220px; overflow:auto; }
  .page { display:flex; gap:8px; align-items:flex-start; padding:6px 0; border-bottom:1px solid #24362d; }
  .page.rejected { opacity:0.55; text-decoration: line-through; }
  .comments { max-height:180px; overflow:auto; font-size:12px; }
  .comment { padding:6px 0; border-bottom:1px solid #24362d; }
    .teach-stage { position:relative; min-height:280px; background:#fffaf3; border:1px solid #eadcc8; border-radius:18px; padding:18px 18px 18px 22px;
                   box-shadow:inset 5px 0 0 #8c3a2f;
                   animation: fadeUp 0.65s ease; }
    .teach-stage.anim { animation: fadeUp 0.65s ease; }
    @keyframes fadeUp { from { opacity:0; transform:translateY(10px); } to { opacity:1; transform:none; } }
    .teach-stage h3 { margin:0 0 10px; padding-right:300px; font-size:28px; color:#1e3a5f; letter-spacing:-0.02em; }
    .page-welcome { display:grid; justify-items:center; text-align:center; gap:8px; padding:18px 8px 8px; color:#5c5146; }
    .page-welcome[hidden] { display:none !important; }
    .page-welcome svg { width:min(100%, 280px); height:auto; }
    .page-welcome p { margin:0; max-width:28rem; font-size:18px; line-height:1.45; }
    .proceed-cue { display:flex; align-items:center; justify-content:space-between; gap:14px;
      margin:14px 0 4px; padding:12px 14px; border-radius:16px; background:#1e3a5f; color:#fff;
      position:sticky; bottom:8px; z-index:4; box-shadow:0 10px 24px rgba(30,58,95,.22); }
    .proceed-cue p { margin:0; font-size:16px; line-height:1.35; }
    .proceed-cue button { border:0; border-radius:999px; background:#f4d48a; color:#1e3a5f;
      padding:10px 18px; font:700 15px Arial,sans-serif; cursor:pointer; white-space:nowrap; }
    .proceed-cue button[aria-pressed="true"] { background:#d9ffe8; }
    .presenter-overlay .proceed-cue { margin:12px 20px 6px; }
    .teach-stage .body { font-size:18px; line-height:1.55; color:#2c241c; }
    .teach-stage .narr { margin-top:14px; padding:10px 12px; border-radius:12px; background:#f7f1e6;
                         color:#5c3b1e; font-style:italic; }
    .lesson-window-controls { position:absolute; top:12px; right:12px; z-index:8; display:flex; align-items:center; gap:7px; }
    .lesson-window-controls .lesson-lang { display:flex; align-items:center; gap:6px; margin:0;
                                           color:#fffaf3; font:700 12px "Avenir Next", "Segoe UI", sans-serif; }
    .lesson-window-controls select { height:38px; max-width:12rem; padding:0 8px; border-radius:10px;
                                     background:rgba(30,58,95,.92); color:#fffaf3; border:1px solid rgba(255,255,255,.28);
                                     box-shadow:0 3px 12px rgba(20,16,12,.22); }
    .lesson-window-controls button { min-width:42px; height:38px; padding:5px 9px; border-radius:10px;
                                     background:rgba(30,58,95,.92); color:#fffaf3; border:1px solid rgba(255,255,255,.28);
                                     box-shadow:0 3px 12px rgba(20,16,12,.22); font-weight:800; }
    .lesson-window-controls button:hover { background:#274c78; }
    .lesson-window-controls button.is-off { background:rgba(74,64,56,.76); color:#d8cec2; text-decoration:line-through; }
    .teach-stage.captions-off .lesson-stage-content > :not(#proceed-cue) { display:none; }
    .absorb-note { margin-top:10px; padding:10px 12px; border-radius:12px; background:#fff6e0;
                   border:1px solid #e7c98a; color:#6a4b16; font:600 14px "Avenir Next", "Segoe UI", sans-serif; }
    .absorb-note[hidden] { display:none !important; }
    .teacher-stage-grid { display:grid; grid-template-columns:minmax(180px, 34%) 1fr;
                          gap:14px; align-items:stretch; position:relative; }
    .teacher-stage-grid .storyboard-stage { grid-column:2; grid-row:1 / span 2; }
    .teacher-stage-grid.has-storyboard { grid-template-columns:minmax(180px, 34%) 1fr; }
    .storyboard-stage { width:100%; aspect-ratio:16/9; border-radius:14px; overflow:hidden; margin:0 0 12px;
                         background:linear-gradient(160deg,#0b1220 0%,#1e293b 55%,#0f766e 140%);
                         box-shadow:0 6px 20px rgba(15,23,42,.28); line-height:0; }
    .storyboard-stage svg { width:100%; height:auto; display:block; }
    .storyboard-stage[hidden] { display:none !important; }
    .lesson-photo { display:none; position:relative; width:100%; aspect-ratio:16/9; overflow:hidden;
      border-radius:14px; margin:0 0 12px; background:#101820; }
    .lesson-photo.is-shown { display:block; }
    .lesson-photo-motion { width:100%; height:100%; }
    .lesson-photo img { width:100%; height:100%; object-fit:cover; display:block; }
    .teacher-stage-grid.has-photo .lesson-photo { grid-column:2; grid-row:1 / span 2; margin:0; min-height:300px; }
    .teacher-stage-grid.has-photo .storyboard-stage,
    .teacher-stage-grid.has-photo .visual-timeline-stage { display:none !important; }
    .teacher-stage-grid.has-visual-timeline .visual-timeline-stage:not([hidden]),
    .presenter-overlay.has-visual-timeline .visual-timeline-stage:not([hidden]) { display:block !important; }
    .teacher-stage-grid.has-visual-timeline .lesson-photo,
    .presenter-overlay.has-visual-timeline .lesson-photo { display:none !important; }
    .lesson-photo[data-effect="fade"].is-in .lesson-photo-motion { animation:pptFade .7s ease both; }
    .lesson-photo[data-effect="fly"].is-in .lesson-photo-motion { animation:pptFly .75s cubic-bezier(.2,.7,.2,1) both; }
    .lesson-photo[data-effect="wipe"].is-in .lesson-photo-motion { animation:pptWipe .8s ease both; }
    .lesson-photo[data-effect="zoom"].is-in .lesson-photo-motion { animation:pptZoom .8s ease both; }
    .lesson-photo[data-effect="cover"].is-in .lesson-photo-motion { animation:pptCover .7s cubic-bezier(.2,.7,.2,1) both; }
    .lesson-photo[data-effect="split"].is-in .lesson-photo-motion { animation:pptSplit .7s ease both; }
    .lesson-photo.is-in img { animation:kenBurns 18s ease-in-out .8s alternate infinite; }
    .ppt-title { animation:pptFlyUp .55s ease both; }
    .teach-stage.voice-animation { animation:voiceStage .65s ease; }
    @keyframes voiceStage { from { filter:saturate(1.35) brightness(1.12); } to { filter:none; } }
    @keyframes pptFade { from { opacity:0; } to { opacity:1; } }
    @keyframes pptFly { from { opacity:0; transform:translateX(22%); } to { opacity:1; transform:none; } }
    @keyframes pptWipe { from { clip-path:inset(0 100% 0 0); } to { clip-path:inset(0); } }
    @keyframes pptZoom { from { opacity:0; transform:scale(1.22); } to { opacity:1; transform:none; } }
    @keyframes pptCover { from { transform:translateY(100%); } to { transform:none; } }
    @keyframes pptSplit { from { clip-path:inset(46% 0 46% 0); } to { clip-path:inset(0); } }
    @keyframes pptFlyUp { from { opacity:0; transform:translateY(26px); } to { opacity:1; transform:none; } }
    @keyframes kenBurns { from { transform:scale(1) translate3d(0,0,0); } to { transform:scale(1.08) translate3d(-1.5%,-1%,0); } }
    .presenter-overlay.has-photo .lesson-photo.is-shown { position:absolute; inset:0; z-index:0; margin:0;
      aspect-ratio:unset; border-radius:0; min-height:0; }
    .presenter-overlay.has-photo .storyboard-stage,
    .presenter-overlay.has-photo .visual-timeline-stage,
    .presenter-overlay.has-photo .picture-stage { display:none !important; }
    .presenter-overlay.has-visual-timeline .visual-timeline-stage:not([hidden]),
    .teacher-stage-grid.has-visual-timeline .visual-timeline-stage:not([hidden]) { display:block !important; }
    .presenter-overlay.has-photo .lesson-stage-content {
      background:linear-gradient(to top, rgba(8,12,20,.88), rgba(8,12,20,.45) 70%, transparent); }
    .visual-timeline-stage { grid-column:2; grid-row:1 / span 2; position:relative; width:100%;
      min-height:300px; aspect-ratio:16/9; border-radius:14px; overflow:hidden;
      background:linear-gradient(145deg,#f8f4ea,#e9f2ee); box-shadow:0 6px 20px rgba(15,23,42,.18); }
    .visual-timeline-stage[hidden] { display:none !important; }
    .visual-layer { position:absolute; inset:0; display:grid; place-items:center; padding:5%;
      opacity:0; transform:translateY(16px) scale(.98); transition:opacity .45s ease,transform .45s ease;
      color:#182b3a; font:700 clamp(18px,3vw,42px)/1.15 "Avenir Next","Segoe UI",sans-serif;
      text-align:center; }
    .visual-layer.is-active { opacity:1; transform:none; }
    .visual-layer img { width:100%; height:100%; object-fit:contain; border-radius:12px; }
    .visual-layer[data-transition="slide-left"] { transform:translateX(12%); }
    .visual-layer[data-transition="slide-right"] { transform:translateX(-12%); }
    .visual-layer[data-transition="zoom"] { transform:scale(.78); }
    .visual-layer[data-transition="pan"] img { transform:scale(1.08); transition:transform 6s linear; }
    .visual-layer[data-transition="pan"].is-active img { transform:scale(1); }
    .visual-layer .visual-label { padding:.45em .7em; border-radius:12px; background:rgba(255,255,255,.9);
      box-shadow:0 3px 14px rgba(15,23,42,.16); }
    .timeline-style-label { display:none; }
    .visual-timeline-stage.layout-compare:not([hidden]) { display:grid !important;
      grid-template-columns:1fr; align-content:start; gap:12px; padding:22px 5vw 18px;
      aspect-ratio:auto; min-height:0; overflow:auto; }
    .visual-timeline-stage.layout-compare .visual-layer.kind-picture,
    .visual-timeline-stage.layout-compare .visual-layer.kind-storyboard,
    .visual-timeline-stage.layout-compare .visual-layer.kind-video { position:absolute; inset:0; opacity:0; pointer-events:none; }
    .visual-timeline-stage.layout-compare .visual-layer.kind-title { display:none; }
    .visual-timeline-stage.layout-compare .visual-layer.kind-body,
    .visual-timeline-stage.layout-compare .visual-layer.kind-callout {
      position:relative; inset:auto; grid-column:1 / -1; opacity:0;
      font-size:clamp(17px, 1.7vw, 22px); font-weight:600; line-height:1.45; text-align:left; }
    .visual-timeline-stage.layout-compare .visual-layer.kind-body.is-active,
    .visual-timeline-stage.layout-compare .visual-layer.kind-callout.is-active { opacity:1; transform:none; }
    .visual-timeline-stage.layout-compare .visual-layer .visual-label { max-width:44rem; }
    .visual-timeline-stage[data-layout="road-scene"] { background:#dbe7f3; }
    .visual-timeline-stage[data-layout="road-scene"] .visual-layer.kind-storyboard { padding:0; transform:none; }
    .visual-timeline-stage[data-layout="road-scene"] .visual-layer.kind-storyboard svg { width:100%; height:100%; display:block; }
    .visual-timeline-stage[data-layout="road-scene"] .visual-layer.kind-video { padding:0; transform:none; background:#0a1628; }
    .visual-timeline-stage[data-layout="road-scene"] .visual-layer.kind-video video { width:100%; height:100%; object-fit:cover; display:block; }
    .visual-timeline-stage[data-layout="road-scene"] .visual-layer.kind-keypoints { place-items:end start; padding:3% 3.5%;
      text-align:left; pointer-events:none; }
    .road-points { max-width:min(62%, 36rem); padding:.6em .9em .7em; border-radius:14px;
      background:rgba(15,23,42,.88); color:#f8fafc; box-shadow:0 8px 24px rgba(15,23,42,.3);
      font:600 clamp(13px,1.5vw,21px)/1.3 "Avenir Next","Segoe UI",sans-serif; }
    .road-points h4 { margin:0 0 .3em; font-size:1.12em; color:#fde68a; }
    .road-points ol { margin:0; padding-left:1.2em; }
    .road-points li { margin:.12em 0; opacity:.6; }
    .road-points li.is-done { opacity:.82; }
    .road-points li.is-now { opacity:1; color:#ffffff; }
    .teach-stage.has-road-scene #teach-body,
    .teach-stage.has-road-scene #teach-narr,
    .teach-stage.has-road-scene #teach-examples { display:none !important; }
    #resume-retry { position:absolute; left:50%; bottom:16%; transform:translateX(-50%); z-index:60;
      min-height:48px; padding:.6em 1.2em; border-radius:999px; border:0; background:#0f766e; color:#fff;
      font:700 16px/1.2 system-ui,sans-serif; box-shadow:0 8px 22px rgba(15,23,42,.35); cursor:pointer; }
    #resume-retry[hidden] { display:none !important; }
    body.phone-embed #resume-retry {
      position:fixed; left:50%; transform:translateX(-50%);
      bottom:calc(148px + env(safe-area-inset-bottom, 0px) + 8px); z-index:80;
    }
    body.phone-embed.public-course #resume-retry {
      bottom:calc(72px + env(safe-area-inset-bottom, 0px) + 8px);
    }
    body.chrome-hidden #resume-retry,
    body.drive-chrome-hidden #resume-retry { z-index:90; }
    .has-readable-card #teach-body,
    .has-readable-card #teach-narr,
    .has-readable-card #teach-activity { display:none !important; }
    .teach-stage:has(#quiz-box:not([style*="none"])) .visual-timeline-stage,
    .teach-stage:has(#game-box:not([style*="none"])) .visual-timeline-stage,
    .teach-stage:has(#quiz-box:not([style*="none"])) > h3,
    .teach-stage:has(#game-box:not([style*="none"])) > h3,
    .teach-stage:has(#quiz-box:not([style*="none"])) #teach-body,
    .teach-stage:has(#game-box:not([style*="none"])) #teach-body,
    .teach-stage:has(#quiz-box:not([style*="none"])) #teach-narr,
    .teach-stage:has(#game-box:not([style*="none"])) #teach-narr,
    .teach-stage:has(#quiz-box:not([style*="none"])) #teach-activity,
    .teach-stage:has(#game-box:not([style*="none"])) #teach-activity,
    .teach-stage:has(#quiz-box:not([style*="none"])) #teach-examples,
    .teach-stage:has(#game-box:not([style*="none"])) #teach-examples,
    .teach-stage:has(#quiz-box:not([style*="none"])) #proceed-cue,
    .teach-stage:has(#game-box:not([style*="none"])) #proceed-cue,
    .teach-stage:has(#quiz-box:not([style*="none"])) .sample-banner,
    .teach-stage:has(#game-box:not([style*="none"])) .sample-banner,
    .teach-stage:has(#quiz-box:not([style*="none"])) .absorb-note,
    .teach-stage:has(#game-box:not([style*="none"])) .absorb-note { display:none !important; }
    .student-cam:not(.is-hidden) .student-cam-status { display:none; }
    .attention-aside { margin:8px 0 0; padding:8px 12px; border-radius:12px; background:#f4f8ff;
      border:1px solid #c9d7ee; color:#1e3a5f; font:600 14px "Avenir Next","Segoe UI",sans-serif; }
    .attention-aside[hidden] { display:none !important; }
    .teach-stage.is-awake .visual-timeline-stage { background:linear-gradient(145deg,#fff7e8,#e7f7ff); }
    .teach-stage.is-awake .visual-layer { transition-duration:.2s; }
    .teach-stage.is-refocus .visual-timeline-stage { background:linear-gradient(160deg,#f4f7ff,#e7fff4); }
    .teach-stage.is-awake .visual-layer.is-active,
    .teach-stage.is-refocus .visual-layer.is-active { animation:attentionLift .9s ease; }
    @keyframes attentionLift { from { transform:translateY(10px) scale(.96); } to { transform:none; } }
    .storyboard-concept { font-size:14px; color:#5c5146; margin:8px 0 10px; line-height:1.4; }
    .theodore-avatar-wrap { position:relative; min-height:390px; overflow:hidden; border-radius:18px;
                            background:radial-gradient(ellipse at 50% 60%,rgba(68,214,255,.2),rgba(5,24,34,.72) 65%);
                            border:1px solid rgba(94,224,255,.38); box-shadow:inset 0 0 30px rgba(59,215,255,.14); }
    #theodore-avatar { position:absolute; inset:0; }
    #theodore-avatar canvas { width:100%; height:100%; display:block; filter:drop-shadow(0 0 14px rgba(86,224,255,.5)); }
    .theodore-avatar-wrap:has(#theodore-avatar[data-avatar-rig="portrait"]) {
      background:radial-gradient(ellipse at 50% 72%, #fff8ee, #f4e4cf 72%);
      border-color:rgba(140,90,43,.28); box-shadow:inset 0 0 28px rgba(255,244,220,.55); }
    .theodore-avatar-wrap:has(#theodore-avatar[data-avatar-rig="portrait"]) canvas { filter:drop-shadow(0 16px 14px rgba(62,36,18,.22)); }
    .theodore-avatar-wrap:has(#theodore-avatar[data-avatar-rig="portrait"]) .avatar-label {
      color:#4a3424; background:rgba(255,248,236,.9); }
    .avatar-label { position:absolute; left:9px; right:9px; bottom:8px; z-index:2; padding:5px 8px;
                    border-radius:999px; text-align:center; color:#c9f7ff; background:rgba(3,23,32,.72);
                    font:600 11px Arial,sans-serif; letter-spacing:.03em; pointer-events:none; }
    .theodore-avatar-fallback { position:absolute; inset:0; display:grid; place-items:center; color:#8feaff; }
    .fallback-head { position:absolute; top:23%; width:92px; height:105px; border-radius:48% 48% 44% 44%;
                     background:rgba(115,225,255,.42); border:2px solid rgba(190,248,255,.78);
                     box-shadow:0 0 24px #4ad9ff; }
    .fallback-head:before,.fallback-head:after { content:""; position:absolute; top:31px; width:28px; height:42px;
                     border-radius:50%; background:rgba(115,225,255,.42); border:2px solid rgba(190,248,255,.68); }
    .fallback-head:before { left:-24px; } .fallback-head:after { right:-24px; }
    .fallback-head i { position:absolute; top:36px; width:10px; height:5px; border-radius:50%; background:#123744; }
    .fallback-head i:first-child { left:24px; } .fallback-head i:nth-child(2) { right:24px; }
    .fallback-head b { position:absolute; left:33px; top:65px; width:25px; height:10px; border-bottom:3px solid #123744;
                       border-radius:0 0 50% 50%; }
    .fallback-crown { position:absolute; z-index:2; top:10%; font-size:58px; color:#f7dc83; text-shadow:0 0 12px #f4ce65; }
    .fallback-body { position:absolute; top:50%; width:128px; height:170px; border-radius:48% 48% 18% 18%;
                     background:rgba(94,211,246,.34); border:2px solid rgba(190,248,255,.65); }
    .fallback-body span { position:absolute; top:24px; width:44px; height:150px; border-radius:28px;
                          background:rgba(94,211,246,.34); border:2px solid rgba(190,248,255,.55); }
    .fallback-body span:first-child { left:-35px; transform:rotate(8deg); }
    .fallback-body span:last-child { right:-35px; transform:rotate(-8deg); }
    .fallback-glow { position:absolute; bottom:6%; width:75%; height:20px; border-radius:50%;
                     background:rgba(73,219,255,.3); filter:blur(10px); }
    .theodore-avatar-fallback[data-state="speaking"] .fallback-head b { animation:fallbackTalk .28s infinite alternate; }
    .theodore-avatar-fallback[data-state="celebrate"] .fallback-body { animation:fallbackCelebrate .7s ease-in-out 2; }
    @keyframes fallbackTalk { to { height:18px; width:17px; left:37px; } }
    @keyframes fallbackCelebrate { 50% { transform:translateY(-9px) scale(1.03); } }
    .lesson-stage-content { min-width:0; }
    /* Presenter mode: a fixed overlay that also takes the real display through the
       Fullscreen API, so Theodore is not boxed inside the dashboard column. */
    .presenter-overlay { position:fixed; inset:0; z-index:9999; display:none;
                         background:
                           radial-gradient(ellipse at 50% 0%, rgba(255,228,180,.28), transparent 42%),
                           linear-gradient(180deg, #3a2c22 0%, #1c1612 100%); }
    .presenter-overlay.show { display:block; }
    .presenter-overlay .presenter-body { position:absolute; inset:0; overflow:hidden; }
    .presenter-overlay #teach-stage { position:absolute; inset:0; margin:0; padding:0;
                                      border:0; border-radius:0; background:transparent; box-shadow:none;
                                      display:flex; flex-direction:column; min-height:0; }
    .presenter-overlay #teach-stage h3 { flex:0 0 auto; margin:0; padding:18px 340px 12px 30px;
                                         font-size:clamp(22px,3vw,40px); color:#f8f1e4; }
    /* Serenity layout: full-bleed animated storyboard with Theodore as a PiP hologram overlay. */
    .presenter-overlay .teacher-stage-grid { flex:1 1 auto; min-height:0; display:block; position:relative; }
    .presenter-overlay .storyboard-stage { position:absolute; inset:0; aspect-ratio:unset; margin:0;
                                           border-radius:0; z-index:0; box-shadow:none; }
    .presenter-overlay .visual-timeline-stage { position:absolute; inset:0; aspect-ratio:unset;
      min-height:0; border-radius:0; z-index:0; box-shadow:none; }
    .presenter-overlay .theodore-avatar-wrap { position:absolute; left:2.4%; bottom:7%;
                                               width:min(24vw,280px); height:min(42vh,360px);
                                               min-height:220px; z-index:3; border-radius:18px;
                                               background:radial-gradient(ellipse at 50% 64%,rgba(68,214,255,.22),rgba(4,18,26,.55) 70%);
                                               border:1px solid rgba(94,224,255,.45);
                                               box-shadow:0 0 40px rgba(59,215,255,.18), inset 0 0 24px rgba(59,215,255,.12); }
    .presenter-overlay .lesson-stage-content { position:absolute; left:0; right:0; bottom:0; z-index:2;
                                               height:auto; max-height:42%; overflow:auto;
                                               padding:14px 30px 22px;
                                               background:linear-gradient(transparent,rgba(36,26,18,.78) 18%,rgba(28,20,14,.94));
                                               backdrop-filter:blur(8px); border:0; color:#f6efe4; }
    .presenter-overlay .teach-stage .body, .presenter-overlay .teach-stage .narr { color:#f6efe4; background:transparent; }
    .presenter-overlay .lesson-window-controls { position:fixed; top:14px; right:16px; }
    .student-cam { position:fixed; z-index:10020; width:min(148px, 36vw); max-width:calc(100vw - 24px);
                   top:max(12px, env(safe-area-inset-top));
                   left:max(12px, env(safe-area-inset-left)); right:auto;
                   border-radius:12px; overflow:hidden; background:rgba(12,10,8,.72);
                   border:1px solid rgba(255,255,255,.28); box-shadow:0 8px 22px rgba(0,0,0,.35);
                   cursor:grab; touch-action:none; user-select:none; }
    .student-cam.is-dragging { cursor:grabbing; box-shadow:0 14px 32px rgba(0,0,0,.45); }
    .student-cam.is-hidden { width:auto; }
    .student-cam video { display:block; width:100%; aspect-ratio:16/9; object-fit:cover;
                         transform:scaleX(-1); background:#000; }
    .student-cam-track { position:absolute; top:0; left:0; width:100%; aspect-ratio:16/9;
                         transform:scaleX(-1); pointer-events:none; z-index:1; }
    .student-cam.is-hidden .student-cam-track { display:none !important; }
    .student-cam.is-hidden video { position:absolute; width:160px; height:90px; opacity:0; pointer-events:none; }
    .student-cam-hide { position:absolute; right:6px; bottom:6px; z-index:2; margin:0; padding:4px 8px;
                        border-radius:999px; border:1px solid rgba(255,255,255,.35);
                        background:rgba(0,0,0,.62); color:#fff; font:700 11px Arial,sans-serif;
                        cursor:pointer; touch-action:auto; }
    .student-cam.is-hidden .student-cam-hide { position:relative; right:auto; bottom:auto; margin:6px; }
    .student-cam-note { display:none; margin:0; padding:0 8px 8px; color:#f6efe4; font-size:11px; line-height:1.35; }
    .student-cam.is-hidden .student-cam-note { display:block; }
    .student-cam-status { margin:0; padding:6px 8px 8px; color:#f6efe4; font:700 11px Arial,sans-serif; line-height:1.35; }
    .presenter-overlay .lesson-toolbar { position:absolute; top:62px; right:18px; z-index:5; }
    body.chrome-hidden .mast,
    body.chrome-hidden .library-panel,
    body.chrome-hidden #lesson-toolbar,
    body.chrome-hidden #talk-panel,
    body.chrome-hidden .lesson-lang,
    body.chrome-hidden #btn-captions { display:none !important; }
    body.chrome-hidden .layout { display:block; }
    body.chrome-hidden #btn-chrome { display:inline-block !important; }
    /* Voice-first "Sala only" mode. Collapses every secondary control so the
       learner sees only the lesson stage; the overlay (course_voice.js) adds
       a 'Sala listening' pill, consent card, and optional 'Type to Sala' FAB.
       The classic chrome returns on a long-press (750 ms) or after three
       missed voice commands in 15 s, or when the learner says "show controls". */
    body.aoep-voice-first .mast,
    body.aoep-voice-first .library-panel,
    body.aoep-voice-first #library-show,
    body.aoep-voice-first #lesson-toolbar,
    body.aoep-voice-first #talk-panel,
    body.aoep-voice-first .lesson-lang,
    body.aoep-voice-first .lesson-window-controls,
    body.aoep-voice-first #course-progress-hide,
    body.aoep-voice-first #course-progress-show,
    body.aoep-voice-first #course-map-toggle,
    body.aoep-voice-first #course-map-gap,
    body.aoep-voice-first #drive-bar,
    body.aoep-voice-first #btn-chrome { display:none !important; }
    body.aoep-voice-first .layout { display:block; }
    body.aoep-voice-first .panel { background:transparent; border:0; box-shadow:none; padding:0; }
    body.aoep-voice-first .teach-stage { cursor:zoom-in; user-select:none; }
    /* Demo (?demo=1): only the lesson and the avatar. Sala is the control. */
    body.demo-clean #course-price,
    body.demo-clean #sample-banner,
    body.demo-clean #course-map,
    body.demo-clean #page-welcome p,
    body.demo-clean #proceed-cue,
    body.demo-clean #teach-title,
    body.demo-clean .lesson-toolbar,
    body.demo-clean .talk-panel,
    body.demo-clean .sala-pill,
    body.demo-clean .sala-consent,
    body.demo-clean .avatar-hide-btn,
    body.demo-clean .avatar-label,
    body.demo-clean .avatar-drag-handle,
    body.demo-clean .avatar-resize-handle { display:none !important; }
    body.demo-clean .theodore-avatar-wrap { cursor:pointer; }
    body.demo-clean #theodore-avatar { background:url(/api/studio/voice-overlay/sala-gold.png) center/contain no-repeat; filter:drop-shadow(0 8px 16px rgba(201,167,122,.35)); }
    body.demo-clean #theodore-avatar > * { display:none !important; }
    body.demo-clean .theodore-avatar-wrap.sala-giggle #theodore-avatar { background-image:url(/api/studio/voice-overlay/sala-giggle.png); animation:salaGiggle .72s ease; }
    @keyframes salaGiggle { 30% { transform:scale(1.06,.92); } 62% { transform:scale(.98,1.05); } }
    body.demo-clean .theodore-avatar-wrap.sala-listening { box-shadow:0 0 0 2px rgba(212,184,138,.85); border-radius:18px; }
    /* Demo: the slide fills the whole screen (like full screen), the logo avatar is a small corner picture. */
    html body.demo-clean { margin:0; padding:0; }
    html body.demo-clean .teach-stage { position:relative; height:100vh; height:100dvh; min-height:100dvh; padding:0; border:0;
      border-radius:0; overflow:hidden; background:#0f172a; }
    html body.demo-clean #teach-stage-home, html body.demo-clean .panel { height:100%; }
    html body.demo-clean .teacher-stage-grid { position:absolute; inset:0; display:block; }
    html body.demo-clean .visual-timeline-stage, html body.demo-clean .storyboard-stage {
      position:absolute; inset:0; width:100%; height:100%; aspect-ratio:unset; min-height:0 !important;
      max-height:none !important; margin:0; border-radius:0; box-shadow:none; z-index:0; }
    html body.demo-clean #theodore-live-audio { position:fixed; left:10px; right:140px; top:10px; bottom:auto; width:auto;
      max-width:none; height:auto; z-index:7; pointer-events:none; }
    html body.demo-clean #theodore-live-audio > * { pointer-events:auto; }
    /* Short landscape phones: keep the corner pictures small. */
    @media (max-height:520px) {
      html body.demo-clean.demo-clean.demo-clean .theodore-avatar-wrap { width:64px !important; height:84px !important; right:8px !important; bottom:8px !important; }
      html body.demo-clean #theodore-live-audio { display:none !important; }
      html body.demo-clean .lesson-stage-content { padding:8px 84px 8px 12px; max-height:34%; }
      html body.demo-clean.demo-clean.demo-clean .theodore-avatar-wrap { display:block !important; visibility:visible !important; }
    html body.demo-clean #student-cam { width:72px; }
    }
    /* Portrait phones: slide on top, a strip below for the avatar and the question. */
    @media (max-width:760px) {
      html body.demo-clean .visual-timeline-stage, html body.demo-clean .storyboard-stage,
      html body.demo-clean .lesson-photo { bottom:132px; height:auto; }
      html body.demo-clean #theodore-live-audio { display:none !important; }
      html body.demo-clean .lesson-stage-content { min-height:132px; max-height:none; padding:10px 112px 12px 12px;
        background:#0f172a; display:flex; align-items:center; }
      html body.demo-clean .lesson-stage-content > * { margin:0; }
      html body.demo-clean.demo-clean.demo-clean .theodore-avatar-wrap { bottom:10px !important; }
    }
    html body.demo-clean .lesson-photo { position:absolute; inset:0; margin:0; min-height:0; z-index:0; }
    html body.demo-clean.demo-clean.demo-clean .theodore-avatar-wrap { position:absolute !important; right:12px !important;
      bottom:12px !important; top:auto !important; left:auto !important; width:clamp(64px,min(18vw,18vh),108px) !important;
      height:clamp(84px,min(24vw,24vh),140px) !important; min-height:0 !important; z-index:6; border-radius:0;
      background:transparent; border:0; box-shadow:none; opacity:.78; }
    html body.demo-clean .lesson-stage-content { position:absolute; left:0; right:0; bottom:0; z-index:3; max-height:42%;
      overflow:auto; padding:12px 130px 14px 16px; background:linear-gradient(transparent,rgba(15,23,42,.82) 25%,rgba(15,23,42,.94));
      color:#f6efe4; border:0; }
    html body.demo-clean #student-cam { left:10px; right:auto; top:10px; bottom:auto; width:92px; z-index:7; }
    html body.demo-clean #sample-clock { top:10px; left:12px; right:auto; min-width:0; padding:0; border-radius:0;
      background:transparent; box-shadow:none; text-align:left; }
    html body.demo-clean #sample-clock span { font:600 14px/1 system-ui,sans-serif; color:rgba(255,255,255,.55); letter-spacing:0; }
    html body.demo-clean #sample-clock small { display:none; }
    /* Full course (course-clean, set with demo-clean by course_voice.js when access=full): the lesson plus ONE movable
       widget (#course-widget: Salane Voice + webcam + a small menu). Everything else is hidden. The layout rules
       above are shared with the demo; only what differs lives here. */
    html body.course-clean.course-clean.course-clean.course-clean .theodore-avatar-wrap,
    body.course-clean #teach-title,
    body.course-clean #toast,
    body.course-clean #attention-aside,
    body.course-clean .sala-help,
    body.course-clean #proceed-cue { display:none !important; }
    #course-widget { position:fixed; z-index:10030; left:8px; top:8px; width:min(236px, calc(100vw - 16px)); box-sizing:border-box;
      background:rgba(11,16,32,.92); color:#f6efe4; border:1px solid rgba(212,175,55,.6); border-radius:16px;
      box-shadow:0 10px 28px rgba(0,0,0,.45); font:600 13px/1.35 system-ui,sans-serif; }
    #course-widget .cw-bar { display:flex; align-items:center; gap:4px; padding:4px 6px; }
    #course-widget .cw-grip { flex:none; width:44px; height:44px; border:0; border-radius:12px; background:transparent; color:#d4af37;
      font:900 18px/1 system-ui,sans-serif; letter-spacing:-2px; cursor:grab; touch-action:none; }
    #course-widget .cw-grip:active { cursor:grabbing; }
    /* The status is a small dot (green listening, red muted, amber waiting or paused); the words live in its tooltip. */
    #course-widget .cw-status { position:relative; flex:1; min-width:0; margin:0; height:14px; display:flex; align-items:center; }
    #course-widget .cw-status::before { content:""; width:10px; height:10px; border-radius:50%; background:#eab308; }
    #course-widget .cw-status[data-state="on"]::before { background:#22c55e; box-shadow:0 0 8px #22c55e; }
    #course-widget .cw-status[data-state="muted"]::before { background:#f87171; }
    #course-widget .cw-status[data-kind="paused"]::before { background:#fbbf24; box-shadow:0 0 8px #fbbf24; }
    #course-widget .cw-sr { position:absolute; width:1px; height:1px; overflow:hidden; clip:rect(0 0 0 0); white-space:nowrap; }
    /* Only the camera picture, no captions or buttons of its own, inside the panel. */
    #course-widget .student-cam-hide, #course-widget .student-cam-status, #course-widget .student-cam-note { display:none !important; }
    #course-widget .cw-btn { flex:none; width:44px; height:44px; border:0; border-radius:12px; background:rgba(255,255,255,.08); color:#f6efe4;
      font:800 18px/1 system-ui,sans-serif; cursor:pointer; }
    #course-widget .cw-btn:focus-visible, #course-widget .cw-grip:focus-visible, #course-widget .cw-menu [role="menuitem"]:focus-visible { outline:2px solid #fde047; outline-offset:2px; }
    #course-widget .cw-body { padding:0 6px 6px; }
    #course-widget[data-collapsed="1"] .cw-body { height:0; padding:0; overflow:hidden; opacity:0; pointer-events:none; }
    #course-widget .cw-cam { border-radius:12px; overflow:hidden; }
    html body.course-clean #course-widget #student-cam { position:relative !important; width:100% !important; max-width:none !important;
      left:auto !important; top:auto !important; right:auto !important; bottom:auto !important; margin:0; box-shadow:none; border-radius:12px; z-index:auto; }
    #course-widget .cw-voice { margin-top:6px; }
    html body.course-clean #course-widget #theodore-live-audio { position:static !important; left:auto !important; right:auto !important; top:auto !important;
      bottom:auto !important; width:auto !important; display:block !important; pointer-events:auto; }
    #course-widget .cw-voice:empty, #course-widget .cw-cam:empty { display:none; }
    #course-widget .cw-menu { padding:4px 6px 8px; display:grid; gap:4px; border-top:1px solid rgba(255,255,255,.12); }
    #course-widget .cw-menu[hidden] { display:none; }
    #course-widget .cw-menu [role="menuitem"], #course-widget .cw-menu select, #course-widget .cw-menu .cw-info { min-height:44px; box-sizing:border-box; border:0; border-radius:10px;
      background:rgba(255,255,255,.08); color:#f6efe4; font:700 14px/1.2 system-ui,sans-serif; text-align:left; padding:0 12px; display:flex; align-items:center; }
    #course-widget .cw-menu .cw-info { background:transparent; color:#cbd5e1; font-weight:600; }
    #course-widget .cw-menu select { width:100%; }
    /* Demo: the same widget, top-right, with the 10-minute timer inside it. The demo hides the live-audio pill and puts the camera
       and the clock in the top-left corner on their own; inside the widget they sit in its normal flow instead. */
    html body.demo-widget #course-widget #student-cam { position:relative !important; width:100% !important; max-width:none !important;
      left:auto !important; top:auto !important; right:auto !important; bottom:auto !important; margin:0; box-shadow:none; border-radius:12px; z-index:auto; }
    html body.demo-widget #course-widget #theodore-live-audio { position:static !important; left:auto !important; right:auto !important; top:auto !important;
      bottom:auto !important; width:auto !important; display:block !important; pointer-events:auto; }
    html body.demo-widget #course-widget #sample-clock { position:static !important; display:flex; align-items:baseline; justify-content:space-between; gap:8px;
      min-width:0; margin:0 0 6px; padding:2px 6px; border-radius:0; background:transparent; box-shadow:none; text-align:left; }
    html body.demo-widget #course-widget #sample-clock[hidden] { display:none !important; }
    html body.demo-widget #course-widget #sample-clock span { font:800 20px/1 ui-monospace, "SFMono-Regular", Menlo, monospace; color:#f6efe4; letter-spacing:.03em; }
    html body.demo-widget #course-widget #sample-clock small { display:none; margin:0; font:700 10px/1.2 system-ui,sans-serif; color:#cbd5e1; letter-spacing:.08em; text-transform:uppercase; }
    #course-widget .cw-clock:empty { display:none; }
    html body.demo-widget .sala-help { display:none !important; }
    @media (prefers-reduced-motion: reduce) { #course-widget, #course-widget * { transition:none !important; animation:none !important; } }
    /* Demo tutorial and help button. */
    .sala-help { position:fixed; right:14px; top:92px; z-index:2147483000; width:40px; height:40px; border-radius:50%; border:0;
      background:#fde047; color:#1e1b4b; font:900 20px/1 system-ui,sans-serif; cursor:pointer; box-shadow:0 4px 14px rgba(0,0,0,.35); }
    .sala-rotate { position:fixed; left:50%; top:14px; transform:translateX(-50%); z-index:90; padding:8px 14px; border-radius:99px;
      background:rgba(15,23,42,.92); color:#fde68a; font:800 14px/1.2 system-ui,sans-serif; border:2px solid #fde047; text-align:center; max-width:88vw; }
    .sala-tutorial { position:fixed; inset:0; z-index:2147483200; display:grid; place-items:center; padding:14px; background:rgba(2,6,23,.82); }
    /* Driver's Ed demo opening: the page that embeds us shows a video behind the tutorial and
       holds the lesson (including the first slide, "California learner's permit") until the
       video is done. Only the tutorial and the ? button stay visible, over a see-through page. */
    html.sala-intro-hold, html.sala-intro-hold body { background:transparent !important; }
    html.sala-intro-hold body > *:not(.sala-tutorial):not(.sala-help) { visibility:hidden !important; }
    html.sala-intro-hold .sala-tutorial { background:rgba(2,6,23,.55); }
    .sala-tutorial .card { box-sizing:border-box; width:min(calc(100vw - 28px),520px); max-height:94vh; overflow:auto; padding:20px 20px 16px; border-radius:24px;
      background:linear-gradient(160deg,#312e81,#1e1b4b); border:3px solid #fde047; color:#f1f5f9; text-align:center;
      font:500 16px/1.45 system-ui,"Avenir Next","Segoe UI",sans-serif; box-shadow:0 20px 60px rgba(0,0,0,.6); }
    .sala-tutorial .card.has-frame { width:min(calc(100vw - 28px),440px); padding:10px 10px 14px; background:#0a1628; }
    .sala-tutorial img.frame { width:100%; height:auto; max-height:min(72vh,760px); object-fit:contain; display:block; border-radius:16px; background:#0a1628; }
    .sala-tutorial img.frame.portrait { width:auto; max-width:min(52vw,220px); max-height:46vh; margin:8px auto; }
    .sala-tutorial h2 { margin:6px 0 10px; color:#fde68a; font:900 clamp(22px,6vw,30px)/1.15 system-ui,sans-serif; }
    .sala-tutorial p { margin:8px 0; }
    .sala-tutorial .icon { font-size:46px; line-height:60px; }
    .sala-tutorial ul { list-style:none; margin:8px 0; padding:0; display:flex; flex-wrap:wrap; gap:6px; justify-content:center; }
    .sala-tutorial li { padding:4px 10px; border-radius:99px; background:rgba(255,255,255,.12); border:1px solid rgba(253,224,71,.5); font-weight:700; font-size:14px; }
    .sala-tutorial .dots { display:flex; gap:6px; justify-content:center; }
    .sala-tutorial .dots i { width:9px; height:9px; border-radius:50%; background:#475569; }
    .sala-tutorial .dots i.on { background:#fde047; transform:scale(1.3); }
    .sala-tutorial .actions { display:flex; gap:10px; justify-content:center; margin-top:14px; }
    .sala-tutorial button { min-height:44px; padding:0 20px; border:0; border-radius:99px; font:900 16px/1 system-ui,sans-serif; cursor:pointer; background:#e2e8f0; color:#1e1b4b; }
    .sala-tutorial button.go { background:#fde047; }
    body.aoep-voice-revealed .sala-pill,
    body.aoep-voice-revealed .sala-consent { display:none !important; }
    .sala-pill:focus-visible,
    .sala-type-pill:focus-visible,
    .sala-consent-accept:focus-visible { outline:2px solid #f8d44c; outline-offset:2px; }
    .presenter-overlay .storyboard-concept { display:none; }
    .presenter-overlay .picture-stage { display:none; }
    .presenter-overlay .teach-stage .body { font-size:clamp(16px,1.5vw,23px); max-width:72rem; }
    .presenter-overlay .avatar-label { left:50%; right:auto; transform:translateX(-50%);
                                       bottom:12px; white-space:nowrap; }
    .presenter-overlay.has-storyboard .theodore-avatar-wrap { left:2.4%; bottom:calc(42% + 12px);
                                                             height:min(34vh,320px); }
    .presenter-overlay.has-visual-timeline .theodore-avatar-wrap { left:2.4%; bottom:calc(42% + 12px);
      height:min(34vh,320px); }
    .presenter-overlay:not(.has-storyboard):not(.has-visual-timeline) .theodore-avatar-wrap { left:2%; bottom:9%; width:28%; height:82%; }
    .presenter-overlay:not(.has-storyboard):not(.has-visual-timeline) .lesson-stage-content { left:28%; right:0; bottom:0; top:0;
                                                                      max-height:none; background:rgba(28,20,14,.78); }
    .presenter-exit { position:absolute; top:14px; right:16px; z-index:3; }
    /* Avatar hidden unless body.avatar-on. No !important here: the show/hide
       toggle has to be able to win, and `hidden` has to keep working. */
    body:not(.avatar-on) .theodore-avatar-wrap { display:none; }
    .teacher-stage-grid, .teacher-stage-grid.has-storyboard { grid-template-columns:1fr; }
    .teacher-stage-grid .storyboard-stage { grid-column:1; grid-row:auto; }
    .teacher-stage-grid .visual-timeline-stage { grid-column:1; grid-row:auto; }
    .presenter-overlay:not(.has-storyboard):not(.has-visual-timeline) .lesson-stage-content { left:0; right:0; top:0; max-height:none; }
    body.avatar-on .teacher-stage-grid,
    body.avatar-on .teacher-stage-grid.has-storyboard { grid-template-columns:minmax(180px, 34%) 1fr; }
    body.avatar-on .teacher-stage-grid .storyboard-stage { grid-column:2; grid-row:1 / span 2; }
    body.avatar-on .teacher-stage-grid .visual-timeline-stage { grid-column:2; grid-row:1 / span 2; }
    body.avatar-on .presenter-overlay:not(.has-storyboard):not(.has-visual-timeline) .lesson-stage-content { left:28%; top:0; max-height:none; }
    /* Once the avatar has been dragged it is "placed": one fixed-position code
       path for both the dashboard and the presenter overlay, so the drag does
       not have to out-specify the left/bottom rules each mode sets. */
    body.avatar-placed .teacher-stage-grid,
    body.avatar-placed .teacher-stage-grid.has-storyboard { grid-template-columns:1fr; }
    body.avatar-placed .teacher-stage-grid .storyboard-stage { grid-column:1; grid-row:auto; }
    .teacher-stage-grid.has-photo .lesson-photo { grid-column:1; grid-row:auto; min-height:240px; }
    body.avatar-on .teacher-stage-grid.has-photo { grid-template-columns:minmax(180px, 34%) 1fr; }
    body.avatar-on .teacher-stage-grid.has-photo .lesson-photo { grid-column:2; grid-row:1 / span 2; min-height:300px; }
    .presenter-overlay.has-photo .teacher-stage-grid { position:absolute; inset:0; }
    .presenter-overlay.has-photo #teach-stage h3 { position:relative; z-index:4; color:#fff;
      text-shadow:0 2px 12px rgba(0,0,0,.55);
      background:linear-gradient(rgba(8,12,20,.72), transparent); }
    .presenter-overlay.has-photo .lesson-stage-content,
    body.avatar-on .presenter-overlay.has-photo .lesson-stage-content {
      left:0; right:0; top:auto; bottom:0; height:auto; max-height:38%;
      background:linear-gradient(transparent, rgba(8,12,20,.55) 18%, rgba(8,12,20,.9));
    }
    /* The avatar-on rules above set top:0 with higher specificity, which
       paints the captions and Start under the lesson toolbar. Repeat those
       selectors last so the caption bar and Start stay on the bottom edge. */
    .presenter-overlay:not(.has-storyboard):not(.has-visual-timeline) .lesson-stage-content,
    body.avatar-on .presenter-overlay:not(.has-storyboard):not(.has-visual-timeline) .lesson-stage-content,
    .presenter-overlay.has-visual-timeline .lesson-stage-content,
    body.avatar-on .presenter-overlay.has-visual-timeline .lesson-stage-content,
    .presenter-overlay.has-photo .lesson-stage-content,
    body.avatar-on .presenter-overlay.has-photo .lesson-stage-content {
      left:0; right:0; top:auto; bottom:0; height:auto; max-height:42%;
      z-index:4; pointer-events:auto; overflow:auto;
      display:flex; flex-direction:column;
    }
    .presenter-overlay .lesson-stage-content::before { content:""; margin-top:auto; }
    .presenter-overlay .proceed-cue {
      order:20; position:sticky; bottom:0; z-index:8; margin:10px 0 0;
      pointer-events:auto;
    }
    .presenter-overlay .proceed-cue button { position:relative; z-index:9; }
    .presenter-overlay .theodore-avatar-wrap,
    .presenter-overlay:not(.has-storyboard):not(.has-visual-timeline) .theodore-avatar-wrap,
    .presenter-overlay.has-photo .theodore-avatar-wrap,
    body.avatar-on .presenter-overlay.has-photo .theodore-avatar-wrap {
      bottom:calc(42% + 12px); height:min(34vh, 320px);
    }
    .presenter-overlay.has-photo .theodore-avatar-wrap,
    body.avatar-on .presenter-overlay.has-photo .theodore-avatar-wrap {
      left:2.4%; bottom:calc(38% + 12px); width:min(24vw,280px); height:min(34vh,320px);
    }
    .avatar-drag-handle { position:absolute; top:0; left:0; right:0; height:30px; z-index:4;
                          display:flex; align-items:center; justify-content:center; gap:5px;
                          cursor:grab; touch-action:none; color:#bdf0ff;
                          background:linear-gradient(rgba(4,24,34,.72), transparent);
                          border-radius:18px 18px 0 0; }
    .avatar-drag-handle:focus-visible { outline:2px solid #8feaff; outline-offset:-2px; }
    .avatar-drag-handle span { display:block; width:26px; height:3px; border-radius:3px;
                               background:currentColor; opacity:.65; }
    .theodore-avatar-wrap.dragging .avatar-drag-handle { cursor:grabbing; }
    .avatar-resize-handle { position:absolute; right:0; bottom:0; width:22px; height:22px; z-index:4;
                            cursor:nwse-resize; touch-action:none;
                            background:linear-gradient(135deg, transparent 52%, rgba(141,234,255,.75) 52%);
                            border-radius:0 0 18px 0; }
    .avatar-resize-handle:focus-visible { outline:2px solid #8feaff; outline-offset:-2px; }
    /* The default min-height would otherwise out-rank the inline height the
       resize grip writes, so the box would refuse to shrink past 390px. */
    /* min-height would otherwise out-rank the inline height the resize grip
       writes, and content-box would make the 1px border drift the stored box
       2px away from the rendered one on every save/restore round trip. */
    body.avatar-placed .theodore-avatar-wrap { min-height:0; box-sizing:border-box; }
    .avatar-hide-btn { position:absolute; top:3px; right:5px; z-index:5; width:22px; height:22px;
                       padding:0; border-radius:50%; font-size:13px; line-height:1;
                       background:rgba(4,24,34,.75); color:#bdf0ff; border:1px solid rgba(141,234,255,.4);
                       box-shadow:none; cursor:pointer; }
    body.presenting { overflow:hidden; }
    @media (max-width:760px) {
      .presenter-overlay .theodore-avatar-wrap { width:min(34vw,210px); height:min(30vh,240px);
                                                   left:3%; bottom:44%; }
      .presenter-overlay.has-storyboard .theodore-avatar-wrap { bottom:calc(46% + 8px); height:min(28vh,220px); }
      .presenter-overlay .lesson-stage-content { max-height:46%; padding:10px 16px 18px; }
    }
    .kids-builder { background:linear-gradient(135deg,#fff7ed,#fef3c7); color:#172554;
                    border:3px solid #f59e0b; border-radius:16px; padding:14px; margin-bottom:16px; }
    .kids-builder h2 { color:#7c2d12; font-size:22px; }
    .kids-builder p { margin:6px 0 10px; }
    .kids-builder select, .kids-builder input { background:#fff; color:#172554; border-color:#f59e0b; }
    .kids-builder button { background:#ea580c; border-color:#c2410c; font-weight:700; }
    .cert-builder { background:linear-gradient(135deg,#ecfeff,#e0f2fe); color:#0c4a6e;
                    border:3px solid #0284c7; border-radius:16px; padding:14px; margin-bottom:16px; }
    .cert-builder h2 { color:#075985; font-size:20px; margin:0 0 6px; }
    .cert-builder p { margin:6px 0 10px; font-size:13px; }
    .cert-builder select { background:#fff; color:#0c4a6e; border-color:#0284c7; }
    .cert-builder button { background:#0369a1; border-color:#075985; font-weight:700; }
    .checkpoint-box { margin-top:12px; padding:12px; border-radius:10px; background:#1e3a5f;
                      border:1px solid #3b82f6; display:none; }
    .checkpoint-box.show { display:block; }
    .checkpoint-box .row { margin-top:8px; }
    .picture-stage { margin:10px 0; display:grid; grid-template-columns:1fr 1fr; gap:10px; }
    .picture-stage img { width:100%; aspect-ratio:16/9; object-fit:contain; border-radius:16px;
                         background:#fff; border:1px solid #eadcc8; box-shadow:0 8px 20px rgba(70,46,22,.08); }
    .picture-stage img[hidden] { display:none; }
    .picture-stage:not(:has(img:not([hidden]))) { display:none; }
    .kids-words { font-size:28px !important; line-height:1.25 !important; text-align:center;
                  font-family:Arial,sans-serif; font-weight:700; padding:8px; }
    .activity { margin-top:8px; padding:10px 14px; border-radius:999px; background:#fff1d6;
                color:#5c3b1e; border:1px solid #e7c98a; font:700 15px "Avenir Next", "Segoe UI", sans-serif; text-align:center; }
    .lang-warning { margin-top:8px; padding:8px 10px; border-radius:12px; background:#fff6e0;
                    border:1px solid #e7c98a; color:#6a4b16; font-size:14px; }
    .sample-banner { margin-top:8px; padding:10px 12px; border-radius:12px; background:#eef2ff;
                     border:1px solid #6366f1; color:#1e1b4b; font-size:14px; font-weight:700; }
    .sample-banner.is-ended { background:#fff6e8; border-color:#e7c98a; color:#5c3b1e; font-size:16px; }
    .sample-clock { position:fixed; top:12px; right:12px; z-index:40; min-width:7.2rem;
                    padding:10px 14px 8px; border-radius:16px; background:#1e1b4b; color:#fff;
                    text-align:center; box-shadow:0 10px 28px rgba(30,27,75,.28); }
    .sample-clock[hidden] { display:none !important; }
    .sample-clock span { display:block; font:800 32px/1 ui-monospace, "SFMono-Regular", Menlo, monospace;
                         font-variant-numeric:tabular-nums; letter-spacing:0.03em; }
    .sample-clock small { display:block; margin-top:4px; font:700 11px/1.2 "Avenir Next", "Segoe UI", sans-serif;
                          letter-spacing:.08em; text-transform:uppercase; opacity:.85; }
    body.audio-only #btn-avatar,
    body.audio-only .avatar-choice-label,
    body.audio-only .theodore-avatar-wrap,
    body.audio-only .picture-stage,
    body.audio-only .lesson-photo,
    body.audio-only #teach-storyboard,
    body.audio-only #teach-visual-timeline,
    body.audio-only #teach-body,
    body.audio-only #teach-narr,
    body.audio-only #teach-activity,
    body.audio-only #teach-examples,
    body.audio-only .page-welcome,
    body.audio-only .storyboard-concept { display:none !important; }
    .audio-stage { display:none; }
    body.audio-only .audio-stage {
      position:relative; display:flex; flex-direction:column; align-items:center; justify-content:center;
      gap:18px; min-height:min(46vh, 420px); margin:4px 0 12px; padding:28px 16px 22px;
      border-radius:22px; background:radial-gradient(ellipse at 50% 42%, #2a3a52, #121820 72%);
    }
    .audio-avatar { position:relative; width:112px; height:112px; border-radius:50%;
      background:radial-gradient(circle at 38% 32%, #ffe7b0, #c4893a 62%, #8c5a2b);
      box-shadow:0 0 0 10px rgba(143,234,255,.18); }
    .audio-avatar i, .audio-avatar b { position:absolute; display:block; }
    .audio-avatar i { top:42px; width:12px; height:12px; border-radius:50%; background:#1e3a5f; }
    .audio-avatar i:first-child { left:30px; }
    .audio-avatar i:nth-child(2) { right:30px; }
    .audio-avatar b { left:38px; top:68px; width:36px; height:14px; border-bottom:3px solid #1e3a5f;
      border-radius:0 0 20px 20px; }
    body.is-speaking .audio-avatar { box-shadow:0 0 0 14px rgba(143,234,255,.38); }
    .audio-bars { display:none; align-items:flex-end; gap:7px; height:74px; }
    #audio-stage[data-look="bars"] .audio-bars { display:flex; }
    .audio-bars i { width:9px; border-radius:99px; background:#8feaff;
      height:calc(14px + var(--level, .15) * 52px); transform-origin:bottom center;
      animation:audioBar 1.05s ease-in-out infinite; animation-play-state:paused; }
    body.is-speaking .audio-bars i { animation-play-state:running; }
    .audio-bars i:nth-child(2) { animation-delay:.1s; }
    .audio-bars i:nth-child(3) { animation-delay:.2s; }
    .audio-bars i:nth-child(4) { animation-delay:.05s; }
    .audio-bars i:nth-child(5) { animation-delay:.18s; }
    .audio-bars i:nth-child(6) { animation-delay:.28s; }
    .audio-bars i:nth-child(7) { animation-delay:.12s; }
    @keyframes audioBar { 50% { transform:scaleY(1.7); } }
    body.audio-only .student-cam { position:absolute; top:12px; left:12px; width:88px; z-index:3; }
    body.phone-embed.audio-only .audio-stage {
      padding-left:108px; max-height:calc(100dvh - 300px); margin-bottom:12px;
    }
    body.phone-embed .lesson-caption { position:relative; z-index:6; }
    #lesson-caption[hidden] { display:none !important; }
    .lesson-caption { display:none; margin:8px 0 0; padding:8px 12px; border-radius:12px;
      background:#1e3a5f; color:#fffaf3; font:600 16px/1.35 "Avenir Next", "Segoe UI", sans-serif;
      max-height:4.4em; overflow:hidden; }
    body.phone-embed .teach-stage:not(.captions-off) #lesson-caption:not([hidden]) { display:block; }
    @media (max-width:700px) {
      .picture-stage { grid-template-columns:1fr; }
      .teacher-stage-grid { grid-template-columns:1fr; }
      .theodore-avatar-wrap { min-height:320px; }
    }
    /* In-app and phone lesson. The course stays on screen with the Start,
       Pause, and Talk buttons reachable. The library sits underneath. */
    body.phone-embed .layout { display:flex; flex-direction:column; padding:8px 8px 156px; }
    body.phone-embed .library-panel { order:2; max-height:28vh; overflow:auto; }
    body.phone-embed.public-course .layout { padding:8px; height:100%; }
    body.phone-embed.public-course .library-panel { order:0; max-height:none; overflow:visible; }
    body.phone-embed.public-course .lesson-toolbar { bottom:8px; }
    body.phone-embed.public-course .teach-stage { min-height:0; flex:1 1 auto; }
    body.phone-embed .layout > .panel:not(.library-panel) { order:1; }
    body.phone-embed .theodore-avatar-wrap { min-height:160px; }
    body.phone-embed button, body.phone-embed select { min-height:44px; }
    body.phone-embed .lesson-window-controls {
      position:static; width:100%; flex-wrap:wrap; justify-content:flex-start; margin:0 0 8px;
    }
    body.phone-embed .teach-stage h3 { padding-right:0; font-size:clamp(22px, 6vw, 30px); line-height:1.15; }
    body.phone-embed .lesson-window-controls #sample-clock {
      position:static; margin-left:auto; min-width:4.6rem; padding:6px 8px 4px;
    }
    body.phone-embed .sample-clock span { font-size:20px; }
    body.phone-embed .lesson-toolbar { position:sticky; bottom:148px; z-index:7; flex-wrap:wrap;
      background:#fffaf3; padding:8px 0; }
    body.phone-embed .proceed-cue, body.audio-only .proceed-cue { position:relative; bottom:auto; }
    body.phone-embed .teach-stage { min-height:46vh; }
    body.phone-embed:not(.audio-only):not(.presenting) .visual-timeline-stage,
    body.phone-embed:not(.audio-only):not(.presenting) .lesson-photo.is-shown,
    body.phone-embed:not(.audio-only):not(.presenting) .storyboard-stage {
      max-height:min(48vh, calc(100dvh - 320px)); min-height:160px;
    }
    body.phone-embed .teach-stage.captions-off .visual-layer.kind-title,
    body.phone-embed .teach-stage.captions-off .visual-layer.kind-text,
    body.phone-embed .teach-stage.captions-off .timeline-style-label,
    body.phone-embed .teach-stage:not(.captions-off) #teach-body,
    body.phone-embed .teach-stage:not(.captions-off) #teach-narr,
    body.phone-embed .teach-stage:not(.captions-off) #teach-activity,
    body.phone-embed .teach-stage:not(.captions-off) #teach-examples,
    body.phone-embed .teach-stage:not(.captions-off) .visual-layer.kind-title,
    body.phone-embed .teach-stage:not(.captions-off) .visual-layer.kind-text { display:none !important; }
    body.phone-embed .teach-stage.captions-off #quiz-box,
    body.phone-embed .teach-stage.captions-off #game-box,
    body.audio-only .teach-stage.captions-off #quiz-box,
    body.audio-only .teach-stage.captions-off #game-box { display:none !important; }
    body.phone-embed .teach-stage.captions-off .visual-timeline-stage.layout-compare .visual-layer.kind-picture,
    body.phone-embed .teach-stage.captions-off .visual-timeline-stage.layout-compare .visual-layer.kind-image,
    body.phone-embed .teach-stage.captions-off .visual-timeline-stage.layout-compare .visual-layer.kind-video,
    body.phone-embed .teach-stage.captions-off .visual-timeline-stage.layout-compare .visual-layer.kind-storyboard {
      position:absolute; inset:0; opacity:0;
    }
    body.phone-embed .teach-stage.captions-off .visual-timeline-stage.layout-compare .visual-layer.kind-picture.is-active,
    body.phone-embed .teach-stage.captions-off .visual-timeline-stage.layout-compare .visual-layer.kind-image.is-active,
    body.phone-embed .teach-stage.captions-off .visual-timeline-stage.layout-compare .visual-layer.kind-video.is-active,
    body.phone-embed .teach-stage.captions-off .visual-timeline-stage.layout-compare .visual-layer.kind-storyboard.is-active {
      opacity:1;
    }
    body.phone-embed #quiz-box, body.phone-embed #game-box {
      position:relative; z-index:5; max-height:30vh; overflow:auto;
    }
    body.phone-embed .visual-timeline-stage.layout-compare .visual-layer.kind-picture,
    body.phone-embed .visual-timeline-stage.layout-compare .visual-layer.kind-image,
    body.phone-embed .visual-timeline-stage.layout-compare .visual-layer.kind-video,
    body.phone-embed .visual-timeline-stage.layout-compare .visual-layer.kind-storyboard {
      position:absolute; inset:0; opacity:0;
    }
    body.phone-embed .visual-timeline-stage.layout-compare .visual-layer.kind-picture.is-active,
    body.phone-embed .visual-timeline-stage.layout-compare .visual-layer.kind-image.is-active,
    body.phone-embed .visual-timeline-stage.layout-compare .visual-layer.kind-video.is-active {
      opacity:1;
    }
    body.phone-embed .visual-timeline-stage.layout-compare .visual-layer.kind-storyboard,
    body.phone-embed .visual-timeline-stage.layout-compare .visual-layer.kind-storyboard.is-active,
    body.phone-embed .teach-stage.captions-off .visual-timeline-stage.layout-compare .visual-layer.kind-storyboard.is-active {
      opacity:0;
    }
    body.phone-embed .teach-stage:has(#quiz-box:not([style*="none"])) #quiz-box,
    body.phone-embed .teach-stage:has(#game-box:not([style*="none"])) #game-box {
      max-height:none;
    }
    .teach-stage.captions-off .lesson-stage-content > #sample-clock { display:inline-flex; }
    @media (prefers-reduced-motion: reduce) {
      .teach-stage, .teach-stage.anim, .theodore-avatar-fallback * { animation:none !important; }
      .visual-layer, .visual-layer img, .lesson-photo img, .lesson-photo-motion, .ppt-title {
        animation:none !important; transition:none !important; transform:none !important; }
    }
    .quiz-box, .game-box { margin-top:12px; padding:12px; border:1px solid #ead7b8; border-radius:16px; background:#fff6e8; color:#241c16; }
    .quiz-box button, .game-box button { display:block; width:100%; text-align:left; margin:6px 0;
      background:#fffaf3; color:#1e3a5f; border-color:#e0d2bf; box-shadow:none; border-radius:12px; }
    .quiz-correction { margin-top:10px; padding:12px; border-radius:12px;
      background:#fffaf3; border-left:4px solid #8c3a2f; }
    .quiz-correction strong { color:#8c3a2f; }
    .quiz-correction p { margin:6px 0 0; }
    .status { font-size:13px; color:#6d5e50; min-height:16px; font-family:"Avenir Next", "Segoe UI", sans-serif; }
    #teach-adapt { display:none; }
    #review-root { position:fixed; top:92px; left:22px; z-index:10060; }
    .review-toggle { position:static; }
    .review-overlay { display:none; width:min(360px, calc(100vw - 32px));
                      max-height:min(72vh, 720px); overflow:auto; padding:14px 16px 16px;
                      border-radius:18px; background:rgba(255,250,242,.88); color:#241c16;
                      border:1px solid rgba(90,62,32,.16); backdrop-filter:blur(14px);
                      box-shadow:0 18px 48px rgba(70,46,22,.16); font-size:13px; line-height:1.4; }
    .review-overlay.show { display:block; }
    .review-head { display:flex; justify-content:space-between; align-items:center; gap:8px; margin-bottom:4px; }
    .review-overlay h2 { margin:0; font-size:18px; color:#1e3a5f; }
    .review-overlay h3 { margin:12px 0 6px; font-size:11px; letter-spacing:.08em; text-transform:uppercase; color:#8c5a2b; }
    .review-overlay p { margin:0; color:#5c5146; }
    .review-overlay dl { margin:0; display:grid; grid-template-columns:auto 1fr; gap:3px 12px; }
    .review-overlay dt { color:#6d5e50; }
    .review-overlay dd { margin:0; text-align:right; }
    .talk-panel { margin-top:12px; padding:14px 16px; border-radius:16px;
                  background:#fffaf3; border:1px solid #e0d2bf; color:#241c16; }
    .talk-panel h2 { margin:0 0 4px; font-size:18px; color:#1e3a5f; }
    .talk-panel p { margin:0 0 10px; color:#5c5146; font-size:14px; }
    .talk-panel textarea { width:100%; min-height:72px; resize:vertical; }
    .talk-reply { margin:10px 0; min-height:1.2em; color:#1e3a5f; font-size:15px; }
    button.is-listening { background:#8c3a2f; color:#fffaf3; border-color:#8c3a2f; }
    .quiz-box button.mic-btn, .game-box button.mic-btn { display:inline-block; width:auto; margin-top:8px; }
    .game-box .challenge-hero { display:flex; justify-content:center; margin:10px 0; font-size:40px; }
    .game-box .challenge-hero img, .game-box .challenge-face img { max-width:140px; max-height:96px; display:block; }
    .game-box .challenge-grid { display:flex; flex-wrap:wrap; gap:8px; margin-top:8px; }
    .game-box .challenge-grid button, .game-box button.challenge-choice {
      width:auto; min-width:92px; max-width:180px; display:inline-flex; flex-direction:column;
      align-items:center; justify-content:center; text-align:center; margin:0; gap:4px;
    }
    .game-box button.challenge-choice.is-picked { outline:2px solid #1e3a5f; }
    .game-box .challenge-glyph { font-size:32px; line-height:1.1; }
    .game-box .challenge-row { display:flex; flex-wrap:wrap; gap:8px; align-items:center; margin:8px 0; }
    .game-box .challenge-row select { min-width:140px; }
    .heard { margin:8px 0 0; font-size:13px; color:#5c5146; }
    .score-row { display:grid; grid-template-columns:1fr auto; gap:2px 8px; margin:5px 0; }
    .score-row .meter { grid-column:1 / -1; height:6px; border-radius:99px; background:rgba(30,58,95,.12); overflow:hidden; }
    .score-row .meter > span { display:block; height:100%; background:#1e3a5f; }
  .toast { position:fixed; right:18px; bottom:18px; background:#fffaf3; color:#241c16; border:1px solid #e0d2bf;
           padding:12px 14px; border-radius:14px; display:none; max-width:360px;
           box-shadow:0 12px 30px rgba(70,46,22,.16); z-index:10070; }
  .lesson-toolbar { margin-top:10px; }
  .avatar-choice-label { display:inline-flex; align-items:center; gap:7px; padding:0 10px;
                         min-height:38px; border:1px solid #d8c6ad; border-radius:10px;
                         background:rgba(255,250,243,.94); color:#4b3826; font-size:12px; font-weight:700; }
  .avatar-choice-label select { min-width:128px; border:0; padding:5px 22px 5px 4px;
                                background:transparent; color:#241c16; font-weight:600; }
  #btn-present::before, #btn-pause::before, #btn-review::before {
    content:""; display:inline-block; width:15px; height:15px; margin-right:7px; vertical-align:-2px;
    background:currentColor; }
  #btn-present::before { -webkit-mask:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'><path fill='black' d='M2 3.5A1.5 1.5 0 0 1 3.5 2h9A1.5 1.5 0 0 1 14 3.5v9a1.5 1.5 0 0 1-1.5 1.5h-9A1.5 1.5 0 0 1 2 12.5v-9zm5.2 1.3v6.4l4-3.2-4-3.2z'/></svg>") center / contain no-repeat; mask:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'><path fill='black' d='M2 3.5A1.5 1.5 0 0 1 3.5 2h9A1.5 1.5 0 0 1 14 3.5v9a1.5 1.5 0 0 1-1.5 1.5h-9A1.5 1.5 0 0 1 2 12.5v-9zm5.2 1.3v6.4l4-3.2-4-3.2z'/></svg>") center / contain no-repeat; }
  #btn-pause::before { -webkit-mask:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'><path fill='black' d='M4 2h3v12H4zM9 2h3v12H9z'/></svg>") center / contain no-repeat; mask:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'><path fill='black' d='M4 2h3v12H4zM9 2h3v12H9z'/></svg>") center / contain no-repeat; }
  #btn-pause.is-paused::before { -webkit-mask:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'><path fill='black' d='M4 2.5v11l9-5.5-9-5.5z'/></svg>") center / contain no-repeat; mask:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'><path fill='black' d='M4 2.5v11l9-5.5-9-5.5z'/></svg>") center / contain no-repeat; }
  #btn-review::before { -webkit-mask:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'><path fill='black' d='M3 2h7l3 3v9a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V3a1 1 0 0 1 1-1zm6 1.2V6h2.6L9 3.2zM4 8h8v1.2H4V8zm0 2.4h6V12H4v-1.6z'/></svg>") center / contain no-repeat; mask:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'><path fill='black' d='M3 2h7l3 3v9a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V3a1 1 0 0 1 1-1zm6 1.2V6h2.6L9 3.2zM4 8h8v1.2H4V8zm0 2.4h6V12H4v-1.6z'/></svg>") center / contain no-repeat; }
  .toast.show { display:block; }
  /* On the Go. The driver hears the class. The screen is only a waveform. */
  body.audio-only { background:#070b14 !important; overflow:hidden; }
  body.audio-only .study-bg,
  body.audio-only header.mast,
  body.audio-only .library-panel,
  body.audio-only #teach-title,
  body.audio-only .lesson-window-controls,
  body.audio-only .teacher-stage-grid,
  body.audio-only .lesson-stage-content,
  body.audio-only #lesson-caption,
  body.audio-only #quiz-box,
  body.audio-only #game-box,
  body.audio-only .sample-banner,
  body.audio-only .proceed-cue,
  body.audio-only .page-welcome,
  body.audio-only .lesson-toolbar,
  body.audio-only .talk-panel,
  body.audio-only .toast,
  body.audio-only #review-root,
  body.audio-only .picture-stage,
  body.audio-only .lesson-photo,
  body.audio-only .theodore-avatar-wrap,
  body.audio-only .audio-avatar { display:none !important; }
  body.audio-only .layout,
  body.audio-only .panel,
  body.audio-only #teach-stage-home,
  body.audio-only .teach-stage {
    background:transparent !important; border:0 !important; box-shadow:none !important;
    padding:0 !important; margin:0 !important; min-height:100dvh;
  }
  body.audio-only .audio-stage {
    position:fixed !important; inset:0 !important; z-index:30;
    display:flex !important; align-items:center; justify-content:center;
    min-height:100dvh !important; max-height:none !important;
    margin:0 !important; padding:0 8vw !important; border-radius:0 !important;
    background:#070b14 !important;
  }
  body.audio-only .audio-bars { height:32vh; gap:7px; align-items:center; }
  body.audio-only .audio-bars i {
    width:9px; border-radius:99px;
    height:calc(16px + var(--level, .22) * 24vh);
    background:linear-gradient(180deg,#e8fdff,#3ec6e0);
    animation-duration:.8s;
  }
  body.audio-only .audio-bars i:nth-child(odd) { animation-delay:.14s; }
  body.audio-only .audio-bars i:nth-child(3n) { animation-delay:.28s; }
  body.audio-only .audio-bars i:nth-child(4n) { animation-delay:.07s; }
  @media (prefers-reduced-motion: reduce) {
    body.audio-only .audio-bars i,
    body.audio-only .voice-mouth .lip-opening,
    body.audio-only .voice-ripple i,
    body.audio-only .voice-lantern i,
    body.audio-only .face-mouth-wrap,
    body.audio-only .face-eye { animation:none !important; }
  }
  .voice-line, .voice-mouth, .voice-ripple, .voice-lantern, .voice-face { display:none; }
  #audio-stage[data-look="line"] .voice-line { display:block; width:min(920px, 86vw); height:min(28vh, 220px); }
  #audio-stage[data-look="mouth"] .voice-mouth { display:block; }
  #audio-stage[data-look="ripple"] .voice-ripple { display:block; }
  #audio-stage[data-look="lantern"] .voice-lantern { display:block; }
  #audio-stage[data-look^="face-"] .voice-face { display:block; width:min(280px, 68vw); height:auto; }
  .voice-mouth { position:relative; width:min(280px, 64vw); height:150px; }
  .voice-mouth .lip-upper, .voice-mouth .lip-lower { position:absolute; left:6%; right:6%; height:46px; z-index:2; }
  .voice-mouth .lip-upper { top:22px; border-radius:80px 80px 16px 16px; background:linear-gradient(#e7a8ad, #c96b74); }
  .voice-mouth .lip-lower { bottom:22px; border-radius:16px 16px 80px 80px; background:linear-gradient(#c96b74, #a85460); }
  .voice-mouth .lip-opening {
    position:absolute; z-index:1; left:22%; right:22%; top:50%; transform:translateY(-50%);
    border-radius:50%; background:#3a1824; height:calc(8px + var(--level, .12) * 52px);
  }
  body.is-speaking .voice-mouth .lip-opening { animation:lipGap .42s ease-in-out infinite; }
  @keyframes lipGap { 50% { height:calc(18px + var(--level, .2) * 58px); } }
  .voice-ripple { position:relative; width:220px; height:220px; }
  .voice-ripple b, .voice-ripple i { position:absolute; border-radius:50%; }
  .voice-ripple b {
    inset:38%; background:#8feaff;
    transform:scale(calc(.85 + var(--level, .1) * .5));
    box-shadow:0 0 24px rgba(143,234,255,.35);
  }
  .voice-ripple i { inset:18%; border:2px solid rgba(143,234,255,.5); animation:voiceRipple 2.8s ease-out infinite; }
  .voice-ripple i:nth-child(3) { animation-delay:.9s; }
  .voice-ripple i:nth-child(4) { animation-delay:1.8s; }
  body.is-speaking .voice-ripple i { animation-duration:1.7s; }
  @keyframes voiceRipple {
    0% { transform:scale(calc(.55 + var(--level, 0) * .3)); opacity:.65; }
    100% { transform:scale(calc(1.35 + var(--level, .15) * .45)); opacity:0; }
  }
  .voice-lantern i {
    display:block; width:148px; height:148px; border-radius:50%;
    background:radial-gradient(circle at 40% 34%, #fff8e4, #f0b429 46%, #c2410c 80%);
    box-shadow:0 0 calc(18px + var(--level, .1) * 70px) rgba(240,180,41,.4);
    transform:scale(calc(.94 + var(--level, .08) * .22));
  }
  body.is-speaking .voice-lantern i { animation:lanternGlow 1.8s ease-in-out infinite; }
  @keyframes lanternGlow { 50% { filter:brightness(1.08); transform:scale(calc(1.02 + var(--level, .15) * .16)); } }
  #audio-stage[data-look="face-amina"] { --skin:#8d5524; --lip:#c4848a; --hair:#1b120c; }
  #audio-stage[data-look="face-mei"] { --skin:#f0c9a0; --lip:#d7a0a6; --hair:#24180f; }
  #audio-stage[data-look="face-luis"] { --skin:#c68642; --lip:#c98980; --hair:#3a2414; }
  #audio-stage[data-look="face-amara"] { --skin:#5c3317; --lip:#a86a72; --hair:#140e0a; }
  #audio-stage[data-look="face-noah"] { --skin:#f3d2b5; --lip:#e0a8ad; --hair:#c4a574; }
  #audio-stage[data-look="face-priya"] { --skin:#a56b3c; --lip:#c47d78; --hair:#1a120c; }
  .face-skin, .face-ear { fill:var(--skin, #e6b48a); }
  .face-brow { fill:none; stroke:var(--hair, #1a120c); stroke-width:2.6; stroke-linecap:round; }
  .face-nose { fill:none; stroke:rgba(40,24,16,.35); stroke-width:2.2; stroke-linecap:round; }
  .face-hair-fill { fill:var(--hair, #1a120c); }
  .face-lip { fill:var(--lip, #d08990); }
  .voice-face .hair, .face-glasses { visibility:hidden; }
  #audio-stage[data-look="face-amina"] .hair-coils,
  #audio-stage[data-look="face-mei"] .hair-bangs,
  #audio-stage[data-look="face-luis"] .hair-crop,
  #audio-stage[data-look="face-amara"] .hair-natural,
  #audio-stage[data-look="face-noah"] .hair-crop,
  #audio-stage[data-look="face-priya"] .hair-long,
  #audio-stage[data-look="face-noah"] .face-glasses { visibility:visible; }
  .face-mouth-wrap { transform-box:fill-box; transform-origin:center;
    transform:scaleY(calc(.42 + var(--level, .08) * 1.7)); }
  body.is-speaking .face-mouth-wrap { animation:mouthOpen .46s ease-in-out infinite; }
  @keyframes mouthOpen {
    0%, 100% { transform:scaleY(calc(.4 + var(--level, .1) * .7)); }
    50% { transform:scaleY(calc(.9 + var(--level, .2) * 1.35)); }
  }
  .face-eye { transform-box:fill-box; transform-origin:center; animation:faceBlink 7.5s infinite; }
  @keyframes faceBlink { 0%, 92%, 100% { transform:scaleY(1); } 96% { transform:scaleY(.12); } }
  body:not(.audio-only) #drive-bar { display:none !important; }
  body.audio-only #theodore-live-audio { display:block !important; }
  body.audio-only #student-cam {
    display:block !important; position:fixed !important; z-index:50;
    top:max(64px, calc(8px + env(safe-area-inset-top))); right:12px; left:auto !important;
    width:min(132px, 34vw);
  }
  body.audio-only #drive-bar {
    position:fixed; z-index:40; top:max(10px, env(safe-area-inset-top));
    left:12px; right:12px; display:flex; flex-wrap:wrap; gap:8px;
  }
  body.audio-only #drive-bar label {
    flex:1 1 140px; min-width:0; display:flex; flex-direction:column; gap:4px;
    color:#d7e7ea; font:600 11px/1.2 "Avenir Next", "Segoe UI", sans-serif;
  }
  body.audio-only #drive-bar select {
    width:100%; min-height:40px; border-radius:10px; border:1px solid #24515c;
    background:#101820; color:#f4fbff; padding:0 8px; font-size:15px;
  }
  .course-map { position:fixed; z-index:10030; left:auto;
    right:max(12px, env(safe-area-inset-right));
    bottom:max(12px, env(safe-area-inset-bottom));
    display:flex; flex-direction:column; align-items:flex-end; gap:8px;
    width:auto; max-width:min(340px, calc(100vw - 24px)); max-height:none;
    padding:0; border:0; border-radius:0; background:transparent; color:#f8fafc;
    box-shadow:none; pointer-events:none; }
  .course-map > * { pointer-events:auto; }
  .course-map[hidden] { display:none !important; }
  .course-map-dock { display:flex; align-items:flex-end; gap:8px; }
  .course-progress-cluster { position:relative; }
  .course-progress-ring { position:relative; width:58px; height:58px; padding:0;
    border-radius:50%; border:1px solid #5eead4; background:#07111ef2; color:#99f6e4;
    box-shadow:0 8px 20px #0006; display:grid; place-items:center; }
  .course-progress-ring svg { position:absolute; inset:0; width:100%; height:100%; }
  .course-progress-ring strong { position:relative; z-index:1; pointer-events:none;
    font:800 11px/1 "Avenir Next", "Segoe UI", sans-serif; }
  .ring-track { fill:none; stroke:rgba(255,255,255,.28); stroke-width:3; }
  .ring-value { fill:none; stroke:#2dd4bf; stroke-width:3; stroke-linecap:round;
    stroke-dasharray:97.39; stroke-dashoffset:97.39; }
  .course-progress-hide, .course-progress-show { width:28px; height:28px; padding:0;
    border-radius:50%; font:800 13px/1 "Avenir Next", "Segoe UI", sans-serif; }
  .course-progress-hide { position:absolute; top:-6px; right:-6px; z-index:2; }
  .course-map.progress-hidden .course-progress-cluster { display:none !important; }
  #course-progress-show[hidden] { display:none !important; }
  .course-map.progress-hidden #course-progress-show { display:inline-grid !important; place-items:center; }
  .course-map-panel { width:min(320px, calc(100vw - 24px)); max-height:42vh; overflow:auto;
    padding:10px 12px; border-radius:16px; border:1px solid #5eead4; background:#07111ef2;
    box-shadow:0 10px 24px #0008; }
  .course-map-panel[hidden] { display:none !important; }
  .course-map-count { display:block; margin:0 0 6px; font-size:13px; color:#e2e8f0; }
  .course-map-toggle { min-height:36px; }
  .course-map-scrub { width:100%; accent-color:#2dd4bf; }
  .course-map-list { margin:0; padding:0; list-style:none; overflow:auto; }
  .course-map-list button { display:block; width:100%; text-align:left; margin:4px 0;
    background:#102029; color:#f8fafc; border-color:#24515c; }
  .course-map-list button.is-current { border-color:#5eead4; color:#99f6e4; }
  .course-map-list button.is-gap { border-style:dashed; color:#fde68a; }
  .course-map-list .chapter { margin:8px 0 2px; font-size:11px; letter-spacing:.06em;
    text-transform:uppercase; color:#94a3b8; }
  body.audio-only .course-map { z-index:40;
    bottom:max(84px, calc(72px + env(safe-area-inset-bottom))); }
  body.audio-only #sample-clock {
    display:inline-flex !important; position:fixed !important; z-index:60;
    top:max(8px, env(safe-area-inset-top)); right:12px; left:auto;
    flex-direction:column; align-items:flex-end; padding:8px 10px; border-radius:14px;
    background:#07111ef2; border:1px solid #5eead4; color:#f8fafc; pointer-events:none;
  }
  body.audio-only #sample-clock[hidden] { display:none !important; }
  #course-price { position:fixed; z-index:60; left:12px;
    top:max(64px, calc(52px + env(safe-area-inset-top)));
    min-height:40px; padding:0 12px; border-radius:14px; border:1px solid #5eead4;
    background:#07111ef2; color:#e7fbff; font:700 13px/40px "Avenir Next", "Segoe UI", sans-serif; }
  #course-price[hidden] { display:none !important; }
  #pay-screen { position:fixed; inset:0; z-index:80; display:none; align-items:center;
    justify-content:center; background:#070b14cc; padding:18px; }
  #pay-screen.is-open { display:flex; }
  #pay-screen form { width:min(420px, 100%); padding:18px; border-radius:18px;
    border:1px solid #5eead4; background:#07111e; color:#f8fafc; }
  #pay-screen h2 { margin:0 0 8px; }
  #pay-price { margin:0 0 8px; font:800 36px/1 "Avenir Next", "Segoe UI", sans-serif; color:#99f6e4; }
  #pay-screen .row { display:flex; gap:8px; margin-top:14px; }
  #pay-screen button { min-height:44px; }
  #presence-hold {
    position:fixed; z-index:10050; left:50%; top:max(72px, calc(56px + env(safe-area-inset-top)));
    transform:translateX(-50%); width:min(560px, calc(100vw - 24px)); margin:0; padding:14px 16px;
    border-radius:16px; background:#1c1408f2; border:1px solid #f59e0b; color:#fde68a;
    font:700 16px/1.45 "Avenir Next", "Segoe UI", sans-serif; text-align:center; pointer-events:none;
    transition: transform .28s ease, opacity .28s ease, width .28s ease, padding .28s ease, top .28s ease;
  }
  #presence-hold[hidden] { display:none !important; }
  /* Full-screen focus: park chrome at the edge after the idle timer. Content stays clear. */
  body.audio-only.drive-chrome-hidden #drive-bar,
  body.audio-only.drive-chrome-hidden #theodore-live-audio,
  body.audio-only.drive-chrome-hidden #course-map,
  body.audio-only.drive-chrome-hidden #course-price,
  body.audio-only.drive-chrome-hidden #attention-aside,
  body.audio-only.drive-chrome-hidden #lesson-toolbar,
  body.audio-only.drive-chrome-hidden #talk-panel,
  body.audio-only.drive-chrome-hidden .lesson-window-controls,
  body.audio-only.drive-chrome-hidden .student-cam-status,
  body.audio-only.drive-chrome-hidden .student-cam-note,
  body.presenting.drive-chrome-hidden #theodore-live-audio,
  body.presenting.drive-chrome-hidden #course-map,
  body.presenting.drive-chrome-hidden #course-price,
  body.presenting.drive-chrome-hidden #attention-aside,
  body.presenting.drive-chrome-hidden #lesson-toolbar,
  body.presenting.drive-chrome-hidden #talk-panel,
  body.presenting.drive-chrome-hidden .lesson-window-controls,
  body.presenting.drive-chrome-hidden .student-cam-status,
  body.presenting.drive-chrome-hidden .student-cam-note,
  body.presenting.drive-chrome-hidden .avatar-label { display:none !important; }
  /* The 10-minute free-trial clock stays visible even when chrome is parked. */
  body.audio-only.drive-chrome-hidden #sample-clock:not([hidden]),
  body.presenting.drive-chrome-hidden #sample-clock:not([hidden]) {
    display:inline-flex !important; position:fixed !important; z-index:10055;
    top:max(8px, env(safe-area-inset-top)); right:12px; left:auto;
    flex-direction:column; align-items:flex-end; pointer-events:none;
  }
  /* Keep a slim top-edge presence chip so the hold is still visible without covering the lesson. */
  body.presenting.drive-chrome-hidden #presence-hold:not([hidden]),
  body.audio-only.drive-chrome-hidden #presence-hold:not([hidden]) {
    display:block !important;
    top:max(6px, env(safe-area-inset-top));
    left:12px; right:auto; transform:none;
    width:auto; max-width:min(42vw, 280px);
    padding:6px 10px; border-radius:999px;
    font-size:12px; line-height:1.25; text-align:left;
    opacity:.92; pointer-events:none;
  }
  #fs-chrome-edge {
    display:none; position:fixed; z-index:10060;
    top:50%; right:0; transform:translateY(-50%);
    width:22px; min-height:88px; padding:10px 4px;
    border:1px solid rgba(94,224,255,.45); border-right:0;
    border-radius:12px 0 0 12px;
    background:rgba(7,17,30,.88); color:#c9f7ff;
    font:700 11px/1.1 "Avenir Next", "Segoe UI", sans-serif;
    letter-spacing:.04em; writing-mode:vertical-rl; text-orientation:mixed;
    cursor:pointer; touch-action:manipulation;
  }
  #fs-chrome-edge:hover, #fs-chrome-edge:focus-visible {
    width:28px; background:rgba(12,28,44,.96); outline:none;
  }
  body.presenting.drive-chrome-hidden #fs-chrome-edge,
  body.audio-only.drive-chrome-hidden #fs-chrome-edge { display:block; }
  body.presenting:not(.drive-chrome-hidden) #fs-chrome-edge,
  body.audio-only:not(.drive-chrome-hidden) #fs-chrome-edge { display:none; }

    /* Project Serenity holographic teacher (demo + full courses). */
    .theodore-avatar-wrap:has(#theodore-avatar[data-avatar-persona="serenity"]) {
      background:radial-gradient(ellipse at 50% 55%, rgba(68,214,255,.28), rgba(5,24,34,.82) 68%);
      border-color:rgba(94,224,255,.45); box-shadow:inset 0 0 34px rgba(59,215,255,.22); }
    .theodore-avatar-wrap:has(#theodore-avatar[data-avatar-persona="serenity"]) canvas {
      filter:drop-shadow(0 0 16px rgba(86,224,255,.55)) saturate(1.08); }
    .theodore-avatar-wrap:has(#theodore-avatar[data-avatar-persona="serenity"]) .avatar-label {
      color:#c9f7ff; background:rgba(3,23,32,.78); }

  /* Learner player: the course fills the screen. Avatar, camera, and progress float. */
  #btn-start-voice { position:absolute; width:1px; height:1px; padding:0; margin:-1px;
    overflow:hidden; clip:rect(0,0,0,0); clip-path:inset(50%); white-space:nowrap; border:0; }
  #btn-start-voice:focus-visible { position:fixed; clip:auto; clip-path:none; width:auto; height:auto;
    margin:0; padding:8px 14px; overflow:visible; z-index:10040;
    left:max(12px, env(safe-area-inset-left)); bottom:max(12px, env(safe-area-inset-bottom)); }
  body.presenting .presenter-overlay.show,
  .presenter-overlay.show { inset:0; width:100%; height:100%; min-height:100dvh; }
  .presenter-overlay.show .teacher-stage-grid,
  body.presenting .presenter-overlay .teacher-stage-grid { position:absolute; inset:0; height:auto; min-height:0; }
  body.presenting .presenter-overlay .storyboard-stage,
  body.presenting .presenter-overlay .visual-timeline-stage,
  body.presenting .presenter-overlay .lesson-photo.is-shown,
  body.phone-embed.presenting .presenter-overlay .storyboard-stage,
  body.phone-embed.presenting .presenter-overlay .visual-timeline-stage,
  body.phone-embed.presenting .presenter-overlay .lesson-photo.is-shown {
    position:absolute; inset:0; width:auto; height:auto; max-height:none; min-height:0;
    aspect-ratio:auto; margin:0; border-radius:0; }
  body.presenting .presenter-overlay .storyboard-stage svg { width:100%; height:100%; max-height:none; display:block; }
  .presenter-overlay.show #teach-stage h3 { position:absolute; z-index:5; left:0; right:0; top:0;
    margin:0; pointer-events:none;
    padding:max(10px, env(safe-area-inset-top)) min(42vw, 220px) 8px max(14px, env(safe-area-inset-left)); }
  .presenter-overlay.show .lesson-window-controls { top:max(8px, env(safe-area-inset-top));
    right:max(8px, env(safe-area-inset-right)); }
  body.avatar-on .presenter-overlay .theodore-avatar-wrap,
  body.avatar-on .presenter-overlay.has-storyboard .theodore-avatar-wrap,
  body.avatar-on .presenter-overlay.has-visual-timeline .theodore-avatar-wrap,
  body.avatar-on .presenter-overlay.has-photo .theodore-avatar-wrap,
  body.avatar-on .presenter-overlay:not(.has-storyboard):not(.has-visual-timeline) .theodore-avatar-wrap,
  body.public-course .theodore-avatar-wrap,
  body.phone-embed .theodore-avatar-wrap {
    width:118px; height:156px; min-height:0; max-height:none; z-index:12; pointer-events:auto;
    left:max(10px, env(safe-area-inset-left)); right:auto; top:auto;
    bottom:max(18px, env(safe-area-inset-bottom)); }
  body.public-course.avatar-on .teacher-stage-grid,
  body.public-course.avatar-on .teacher-stage-grid.has-storyboard,
  body.phone-embed.avatar-on .teacher-stage-grid,
  body.phone-embed.avatar-on .teacher-stage-grid.has-storyboard { grid-template-columns:1fr; }
  body.public-course.avatar-on .teacher-stage-grid .storyboard-stage,
  body.phone-embed.avatar-on .teacher-stage-grid .storyboard-stage { grid-column:1; grid-row:auto; }
  body.public-course:not(.presenting) .theodore-avatar-wrap,
  body.phone-embed:not(.presenting) .theodore-avatar-wrap { position:absolute; z-index:6; }
  .presenter-overlay .avatar-label { left:4px; right:4px; transform:none; white-space:normal;
    font-size:9px; line-height:1.25; bottom:4px; max-width:none; }
  body.presenting .presenter-overlay .lesson-stage-content,
  body.avatar-on.presenting .presenter-overlay .lesson-stage-content,
  body.avatar-on.presenting .presenter-overlay:not(.has-storyboard):not(.has-visual-timeline) .lesson-stage-content,
  body.avatar-on.presenting .presenter-overlay.has-visual-timeline .lesson-stage-content,
  body.avatar-on.presenting .presenter-overlay.has-photo .lesson-stage-content {
    left:0; right:0; top:auto; bottom:0; height:auto; max-height:none; z-index:4;
    pointer-events:none; background:linear-gradient(transparent, rgba(8,12,20,.78) 72%);
    padding:8px 16px max(10px, env(safe-area-inset-bottom)); }
  body.presenting .presenter-overlay .lesson-stage-content > * { pointer-events:auto; }
  body.presenting.drive-chrome-hidden .lesson-stage-content {
    background:transparent !important; backdrop-filter:none !important; pointer-events:none; }
  body.presenting.drive-chrome-hidden #proceed-cue,
  body.presenting.drive-chrome-hidden #lesson-caption,
  body.presenting.drive-chrome-hidden #teach-body,
  body.presenting.drive-chrome-hidden #teach-narr,
  body.presenting.drive-chrome-hidden #teach-examples,
  body.presenting.drive-chrome-hidden .storyboard-concept,
  body.presenting.drive-chrome-hidden .sample-banner,
  body.presenting.drive-chrome-hidden #absorb-note,
  body.presenting.drive-chrome-hidden .page-welcome,
  body.presenting.drive-chrome-hidden .theodore-avatar-wrap,
  body.presenting.drive-chrome-hidden #teach-title,
  body.audio-only.drive-chrome-hidden #proceed-cue,
  body.audio-only.drive-chrome-hidden #lesson-caption { display:none !important; }
  body.presenting.drive-chrome-hidden #student-cam,
  body.audio-only.drive-chrome-hidden #student-cam {
    opacity:0 !important; pointer-events:none !important; }
  body.presenting:not(.drive-chrome-hidden) #student-cam,
  body.audio-only:not(.drive-chrome-hidden) #student-cam { opacity:1; pointer-events:auto; }


"""

STUDIO_JS = """

    const $ = (id) => document.getElementById(id);
    // Set true to show the 3D teacher again. Narration stays on either way.
    const SHOW_AVATAR = true;
    // SHOW_AVATAR is only the first-visit default now; the toggle below persists
    // the learner's own choice, along with where they dragged him.
    const AVATAR_PREF_KEY = 'theodore.studio.avatar.v4-compact';
    const AVATAR_MIN_W = 88;
    const AVATAR_MIN_H = 112;
    let avatarPrefs = {};
    let avatarVisible = false;
    let avatarInitPromise = null;
    let avatarHomeParent = null;
    let avatarHomeNext = null;
    let avatarCatalog = {};
    let selectedAvatarId = 'serenity';
    let selectedSource = null;
    let selectedCourse = null;
    let teachSession = 'studio-teach-1';
    let pagesCache = [];
    let teachLanguage = 'en';
    let languageNames = {};
    let serverAudio = null;
    let neuralObjectUrl = null;
    let courseVoiceGender = 'female';
    let narrationGenderOverride = '';   // gender of the chosen company voice while its clip is missing
    let lastTeachPayload = null;
    let earlyOptions = [];
    let certOptions = [];
    function studioSpokenCode(code) {
      const raw = String(code || '').trim().toLowerCase().replace(/_/g, '-');
      if (!raw) return 'en';
      if (
        raw === 'yue' || raw.indexOf('yue-') === 0 ||
        raw === 'zh-hk' || raw.indexOf('zh-hk') === 0 ||
        raw === 'zh-mo' || raw.indexOf('zh-mo') === 0 ||
        raw === 'cantonese'
      ) return 'yue';
      if (raw === 'km' || raw.indexOf('km-') === 0) return 'km';
      if (raw === 'en-gb' || raw.indexOf('en-gb') === 0 || raw === 'en-uk' || raw.indexOf('en-uk') === 0) return 'en-GB';
      if (raw === 'en-au' || raw.indexOf('en-au') === 0) return 'en-AU';
      if (raw === 'en-sg' || raw.indexOf('en-sg') === 0 || raw === 'singlish') return 'en-SG';
      return raw.split('-')[0] || 'en';
    }
    const studioQuery = new URLSearchParams(location.search);
    teachLanguage = studioSpokenCode(studioQuery.get('lang') || teachLanguage);
    const requestedAccess = (studioQuery.get('access') || '').trim().toLowerCase();
    const registeredFlag = studioQuery.get('registered') === '1';
    const enrollmentStatus = (studioQuery.get('enrollment') || '').trim();
    const adminFlag = studioQuery.get('admin') === '1';
    const pinnedCourse = (studioQuery.get('course') || '').trim();
    if (pinnedCourse) document.body.classList.add('public-course');
    const audioOnly = (studioQuery.get('presentation') || '').trim().toLowerCase() === 'audio';
    function teachAccessFields() {
      return {
        access: requestedAccess,
        registered: registeredFlag || adminFlag,
        enrollment_status: enrollmentStatus,
        is_admin: adminFlag,
      };
    }
    const TRIAL_ENDED = 'Your free 10-minute trial has ended. Thanks for spending time with the lesson. Pay for the course when you want to keep going.';
    let sampleTimer = 0;
    let sampleTick = 0;
    function sampleIsComplete() {
      return !!(lastTeachPayload && lastTeachPayload.sample && lastTeachPayload.sample.complete);
    }
    function trialEndedMessage(payload) {
      const sample = (payload && payload.sample) || {};
      if (sample.complete && sample.message) return sample.message;
      return TRIAL_ENDED;
    }
    function formatSampleClock(ms) {
      const total = Math.max(0, Math.ceil(ms / 1000));
      const minutes = Math.floor(total / 60);
      const seconds = total % 60;
      return minutes + ':' + String(seconds).padStart(2, '0');
    }
    function sampleRemainMs(payload) {
      const started = payload && payload.session && payload.session.started_at_ms;
      const minutes = (payload && payload.sample && payload.sample.minutes) || 10;
      if (!started) return null;
      return started + minutes * 60000 - Date.now();
    }
    function stopSampleClock() {
      if (sampleTimer) { clearTimeout(sampleTimer); sampleTimer = 0; }
      if (sampleTick) { clearInterval(sampleTick); sampleTick = 0; }
    }
    function endSampleTrial(payload) {
      stopSampleClock();
      const base = payload || lastTeachPayload || {};
      lastTeachPayload = base;
      base.access_mode = 'sample';
      base.sample = Object.assign({}, base.sample || {}, {
        complete: true,
        continue_allowed: false,
        minutes: (base.sample && base.sample.minutes) || 10,
        message: trialEndedMessage(base),
      });
      lecturePaused = true;
      if ($('btn-pause')) setPauseButton(true);
      stopSpeech();
      window.TheodoreLiveAudio?.pauseRecognition();
      paintSampleBanner(base);
      openPayScreen();
    }
    let payBusy = false;
    function openPayScreen() {
      const screen = $('pay-screen');
      const price = $('course-price');
      if (price && price.parentElement !== document.body) document.body.appendChild(price);
      if (screen && screen.parentElement !== document.body) document.body.appendChild(screen);
      if (!screen) return;
      screen.hidden = false;
      screen.classList.add('is-open');
      const status = $('pay-status');
      if (status) status.textContent = '';
    }
    function closePayScreen() {
      const screen = $('pay-screen');
      if (!screen) return;
      screen.classList.remove('is-open');
      screen.hidden = true;
    }
    async function beginCoursePayment(method) {
      if (payBusy) return;
      const status = $('pay-status');
      const courseId = (lastTeachPayload && lastTeachPayload.session && lastTeachPayload.session.course_id)
        || pinnedCourse;
      if (!courseId) {
        if (status) status.textContent = 'Open a course, then pay $19.99 for the full class.';
        return;
      }
      payBusy = true;
      if (status) status.textContent = 'Opening the secure payment page…';
      try {
        const data = await api('/api/studio/pay/checkout', {
          method: 'POST',
          headers: {'content-type': 'application/json'},
          body: JSON.stringify({
            course_id: courseId,
            learner_id: (learnerId || '').replace(/:audio$/, ''),
            method: method,
            title: (selectedCourse && selectedCourse.title) || 'Full course',
            return_url: location.href,
          }),
        });
        if (!data.url) throw new Error('The payment page did not open.');
        location.assign(data.url);
      } catch (error) {
        payBusy = false;
        if (status) status.textContent = String(error.message || error);
      }
    }
    async function confirmCoursePayment() {
      const params = new URLSearchParams(location.search);
      if (params.get('paid') !== '1') return;
      const sessionId = params.get('session_id') || params.get('token') || '';
      if (!sessionId) return;
      const status = $('pay-status');
      openPayScreen();
      if (status) status.textContent = 'Confirming the $19.99 payment…';
      try {
        await api('/api/studio/pay/confirm', {
          method: 'POST',
          headers: {'content-type': 'application/json'},
          body: JSON.stringify({ session_id: sessionId }),
        });
        params.delete('paid');
        params.delete('session_id');
        params.delete('token');
        params.delete('PayerID');
        params.set('access', 'full');
        params.set('registered', '1');
        params.set('enrollment', 'paid');
        location.replace(location.pathname + '?' + params.toString());
      } catch (error) {
        if (status) status.textContent = String(error.message || error);
      }
    }
    function armSampleClock(payload) {
      stopSampleClock();
      if (!payload || payload.access_mode !== 'sample') return;
      if (payload.sample && payload.sample.complete) return;
      const remain = sampleRemainMs(payload);
      if (remain == null) return;
      if (remain <= 0) { endSampleTrial(payload); return; }
      const tick = () => {
        const left = sampleRemainMs(payload);
        if (left == null) return;
        if (left <= 0) { endSampleTrial(payload); return; }
        paintSampleBanner(payload);
      };
      tick();
      sampleTick = setInterval(tick, 1000);
      sampleTimer = setTimeout(() => endSampleTrial(payload), remain);
    }
    function paintSampleBanner(payload) {
      const banner = $('sample-banner');
      const clock = $('sample-clock');
      const timeEl = $('sample-clock-time');
      const sample = (payload && payload.sample) || {};
      const mode = (payload && payload.access_mode) || '';
      const show = mode === 'sample' || (!payload && requestedAccess === 'sample');
      const remain = show && !sample.complete ? sampleRemainMs(payload) : null;
      if (clock && timeEl) {
        const ticking = show && !sample.complete;
        parkSampleClock();
        clock.hidden = !ticking;
        if (ticking) {
          const ms = remain == null
            ? ((sample.minutes || 10) * 60000)
            : Math.max(0, remain);
          timeEl.textContent = formatSampleClock(ms);
        }
      }
      if (!banner) return;
      const ended = !!(show && sample.complete);
      banner.style.display = ended ? 'block' : 'none';
      banner.classList.toggle('is-ended', ended);
      banner.textContent = ended
        ? trialEndedMessage(payload)
        : '';
      const priceBtn = $('course-price');
      if (priceBtn) {
        if (priceBtn.parentElement !== document.body) document.body.appendChild(priceBtn);
        priceBtn.hidden = mode !== 'sample';
      }
    }
    function resolveLearnerId() {
      try {
        const params = new URLSearchParams(location.search);
        const student = (params.get('student') || params.get('profile') || '').trim();
        const account = (params.get('account') || '').trim();
        const remember = (id) => {
          localStorage.setItem('studio_learner_id', id);
          return id;
        };
        if (student) return remember('stu:' + student);
        if (account) return remember('acct:' + account);
        const profile = (localStorage.getItem('aoep_student_id') || '').trim();
        const acct = (localStorage.getItem('aoep_account_id') || '').trim();
        if (profile && profile !== 'anon-student') return 'stu:' + profile;
        if (acct) return 'acct:' + acct;
        let saved = localStorage.getItem('studio_learner_id');
        if (!saved) {
          saved = 'browser-' + (window.crypto && crypto.randomUUID ? crypto.randomUUID() : String(Date.now()));
          localStorage.setItem('studio_learner_id', saved);
        }
        return saved;
      } catch (err) {
        return 'learner-demo';
      }
    }
    let learnerId = resolveLearnerId();
    if (audioOnly) {
      if (!learnerId.endsWith(':audio')) learnerId += ':audio';
      teachSession = 'studio-teach-audio';
      document.body.classList.add('public-course', 'audio-only');
      document.body.dataset.driveChrome = '1';
      const waveStage = $('teach-stage');
      if (waveStage) waveStage.classList.add('captions-off');
    }
    let theodoreAvatar = null;
    // The lesson plays straight through. Pause is the only hold.
    let lecturePaused = false;
    let liveCourseHold = false;
    let topicSyncing = false;
    let pendingTopic = '';
    let topicTimer = null;
    let learningHold = false;
    let learningHoldReason = '';
    let learningCheckOpen = false;
    let attentionShiftUntil = 0;
    let attentionResume = '';
    let attentionFullBody = '';
    let talkOpen = false;
    let autoAdvanceTimer = null;
    let advancing = false;
    let speechGen = 0;
    let playToken = 0;
    let playbackWatchdog = null;
    let stallTimer = null;
    let speechHold = false;
    let talkReplyActive = false;
    let finishUtterance = null;
    let teachEpoch = 0;
    let preloadedSlideAudio = null;
    let preloadedSlideUrl = '';
    let micStream = null;
    let visualTimeline = null;
    let visualCueIndex = -1;
    let visualTimers = [];
    // Recovery only. Healthy clips advance on `ended`, then ABSORB_MS.
    const WATCHDOG_GRACE_MS = 2500;
    const STALL_RECOVER_MS = 6000;
    const SLIDE_TRANSITION_MS = 700;
    // Quiet time after the voice finishes so the page can be studied.
    const ABSORB_MS = 12000;
    let library = [];
    let activeCourse = null;
    let lessonCursor = 0;
    let slideVariety = 'straight';
    let lastCheckPassed = null;
    let beatHandled = false;
    let reviewOpen = false;
    let captionsEnabled = false;
    const reviewScores = { quizzes: [], games: [] };
    const RESUME_FETCH_MS = 8000;
    const RESUME_VERIFY_MS = 6000;
    const ADVANCE_TIMEOUT_MS = 15000;
    const WAKE_GAP_MS = 20000;
    const CAMERA_MUTE_AWAY_MS = 1500;
    let lastPlaybackAt = 0;
    let lastSpeakRequestAt = 0;
    let resumeStartedAt = 0;
    let advancePromise = null;
    let lifecycleTickAt = Date.now();

    // Must stay self-contained: tests/test_lesson_resume.py runs this factory in node.
    function createLessonLifecycle(io) {
      const st = { away: false, wasPlaying: false, token: 0, run: null, failed: false };
      function away(source) {
        if (st.away) return false;
        st.away = true;
        st.wasPlaying = !!(st.failed || io.isPlaying());
        st.token += 1;
        st.run = null;
        io.onAway(String(source || 'away'), st.wasPlaying);
        return true;
      }
      function back(source, opts) {
        const force = !!(opts && opts.force);
        const label = String(source || 'return');
        if (!force && io.isHidden()) return Promise.resolve('hidden');
        if (st.run && !force) return st.run;
        if (!st.away && !st.failed && !force) {
          io.refresh(label);
          return Promise.resolve('steady');
        }
        const want = force || st.failed || st.wasPlaying;
        st.away = false;
        st.token += 1;
        const token = st.token;
        const stale = () => token !== st.token;
        const run = (async () => {
          try {
            await Promise.resolve();
            await io.restoreMedia(label, token);
            if (stale()) return 'stale';
            if (!want || io.isPaused()) {
              st.failed = false;
              io.clearFailure();
              return 'paused';
            }
            const payload = await io.reconcile(label, token);
            if (stale()) return 'stale';
            const played = payload ? await io.continueLesson(payload, label, token) : false;
            if (stale()) return 'stale';
            const ok = played === 'quiet' || (played === 'played' && await io.verify(token));
            if (stale()) return 'stale';
            if (!ok) {
              st.failed = true;
              io.showFailure(label);
              return 'failed';
            }
            st.failed = false;
            io.clearFailure();
            return 'resumed';
          } catch (error) {
            if (stale()) return 'stale';
            st.failed = true;
            io.showFailure(label, error);
            return 'failed';
          } finally {
            if (st.run === run) st.run = null;
          }
        })();
        st.run = run;
        return run;
      }
      return {
        away: away,
        back: back,
        isAway: () => st.away,
        busy: () => !!st.run,
        failed: () => st.failed,
        token: () => st.token,
      };
    }

    const lessonLife = createLessonLifecycle({
      isHidden: () => document.visibilityState === 'hidden',
      isPlaying: () => lessonIsPlaying(),
      isPaused: () => lecturePaused || sampleIsComplete() || !lessonTurnLoaded(),
      onAway: (source) => noteLessonAway(source),
      refresh: () => refreshLessonMedia(),
      restoreMedia: () => restoreLessonMedia(),
      reconcile: () => reconcileLessonForResume(),
      continueLesson: (payload) => continueLessonAfterReturn(payload),
      verify: (token) => verifyLessonPlayback(token, resumeStartedAt),
      showFailure: () => showResumeRetry(),
      clearFailure: () => hideResumeRetry(),
    });

    function presenterLabel(presenter) {
      const name = presenter?.label || 'Serenity';
      if (presenter?.source === 'gemini-serenity' || name === 'Serenity') {
        return 'Serenity · holographic AI teacher';
      }
      return presenter?.kind === 'portrait' ? `${name} · cartoon teacher` : `${name} · 3D teacher`;
    }

    async function initTheodoreAvatar() {
      const host = $('theodore-avatar');
      if (!host) return null;
      if (avatarInitPromise) return avatarInitPromise;
      avatarInitPromise = (async () => {
        try {
          const module = await import('/api/studio/avatar/avatar_runtime.js');
          theodoreAvatar = await module.createTheodoreAvatar(host, {
            assetBase: '/api/studio/avatar',
            motionIntensity: 0.42,
            persona: selectedAvatarId
          });
          theodoreAvatar.setReducedMotion(
            !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches));
          const presenter = avatarCatalog[selectedAvatarId];
          $('avatar-state').textContent = host.dataset.avatarReady === 'fallback'
            ? 'Theodore · accessible silhouette'
            : presenterLabel(presenter);
        } catch (error) {
          host.innerHTML = '<div class="theodore-avatar-fallback" role="img" aria-label="Theodore teacher silhouette"><div class="fallback-crown">♜</div><div class="fallback-head"><i></i><i></i><b></b></div><div class="fallback-body"><span></span><span></span></div><div class="fallback-glow"></div></div>';
          $('avatar-state').textContent = 'Theodore · accessible silhouette';
        }
        return theodoreAvatar;
      })();
      return avatarInitPromise;
    }

    // A transformed ancestor becomes the containing block for position:fixed, and
    // .teach-stage.anim animates a transform on every slide change. Left where he
    // is, a placed Theodore would jump by the stage's offset for 0.65s each slide,
    // and his saved coordinates would be stage-relative instead of viewport-relative.
    // So a placed Theodore is hoisted out of that subtree entirely. In presenter
    // mode the host is the overlay, because it is the fullscreen element and
    // anything outside it would not render.
    function avatarPlacedHost() {
      return presenterActive() ? $('presenter-overlay') : document.body;
    }

    function rehomeAvatar(wrap) {
      if (avatarPrefs.placed) {
        const host = avatarPlacedHost();
        if (host && wrap.parentElement !== host) host.appendChild(wrap);
      } else if (avatarHomeParent && wrap.parentElement !== avatarHomeParent) {
        avatarHomeParent.insertBefore(wrap, avatarHomeNext);
      }
    }

    function loadAvatarPrefs() {
      try {
        const raw = window.localStorage.getItem(AVATAR_PREF_KEY);
        return raw ? JSON.parse(raw) : {};
      } catch (error) {
        return {};
      }
    }

    function saveAvatarPrefs() {
      try {
        window.localStorage.setItem(AVATAR_PREF_KEY, JSON.stringify(avatarPrefs));
      } catch (error) {
        /* Private browsing denies writes; the session still works, it just forgets. */
      }
    }

    async function loadAvatarChoices() {
      const data = await api('/api/studio/presenter/manifest');
      avatarCatalog = data.models || {};
      if (avatarPrefs.presenterChosen && avatarCatalog[avatarPrefs.presenter]) {
        selectedAvatarId = avatarPrefs.presenter;
      } else if (avatarCatalog[data.default_model]) {
        selectedAvatarId = data.default_model;
      } else if (avatarCatalog.serenity) {
        selectedAvatarId = 'serenity';
      } else {
        selectedAvatarId = Object.keys(avatarCatalog)[0] || 'student';
      }
      courseVoiceGender = avatarCatalog[selectedAvatarId]?.voice_gender || courseVoiceGender;
    }

    async function chooseAvatar(presenterId) {
      if (!avatarCatalog[presenterId]) return;
      selectedAvatarId = presenterId;
      avatarPrefs.presenter = presenterId;
      avatarPrefs.presenterChosen = true;
      saveAvatarPrefs();
      courseVoiceGender = avatarCatalog[presenterId]?.voice_gender || courseVoiceGender;
      if (!avatarVisible) setAvatarVisible(true);
      await initTheodoreAvatar();
      await theodoreAvatar?.setPersona(presenterId);
      $('avatar-state').textContent = presenterLabel(avatarCatalog[presenterId]);
      requestAnimationFrame(() => theodoreAvatar?.resize());
    }

    // Keep the box reachable even if the window shrank since it was placed.
    function readSafeInsets() {
      let probe = document.getElementById('safe-inset-probe');
      if (!probe) {
        probe = document.createElement('div');
        probe.id = 'safe-inset-probe';
        probe.setAttribute('aria-hidden', 'true');
        probe.style.cssText = 'position:fixed;visibility:hidden;pointer-events:none;padding:env(safe-area-inset-top) env(safe-area-inset-right) env(safe-area-inset-bottom) env(safe-area-inset-left)';
        (document.body || document.documentElement).appendChild(probe);
      }
      const cs = getComputedStyle(probe);
      return {
        top: parseFloat(cs.paddingTop) || 0,
        right: parseFloat(cs.paddingRight) || 0,
        bottom: parseFloat(cs.paddingBottom) || 0,
        left: parseFloat(cs.paddingLeft) || 0,
      };
    }

    function clampAvatarBox() {
      const wrap = $('theodore-avatar-wrap');
      if (!wrap || !avatarPrefs.placed) return;
      const safe = readSafeInsets();
      const w = Math.min(Math.max(avatarPrefs.w || wrap.offsetWidth, AVATAR_MIN_W), window.innerWidth - safe.left - safe.right);
      const h = Math.min(Math.max(avatarPrefs.h || wrap.offsetHeight, AVATAR_MIN_H), window.innerHeight - safe.top - safe.bottom);
      avatarPrefs.w = w;
      avatarPrefs.h = h;
      avatarPrefs.x = Math.min(Math.max(avatarPrefs.x || 0, safe.left), Math.max(window.innerWidth - w - safe.right, safe.left));
      avatarPrefs.y = Math.min(Math.max(avatarPrefs.y || 0, safe.top), Math.max(window.innerHeight - h - safe.bottom, safe.top));
      wrap.style.left = avatarPrefs.x + 'px';
      wrap.style.top = avatarPrefs.y + 'px';
      wrap.style.width = w + 'px';
      wrap.style.height = h + 'px';
    }

    function applyAvatarPlacement() {
      const wrap = $('theodore-avatar-wrap');
      if (!wrap) return;
      document.body.classList.toggle('avatar-placed', !!avatarPrefs.placed);
      rehomeAvatar(wrap);
      if (avatarPrefs.placed) {
        wrap.style.position = 'fixed';
        wrap.style.right = 'auto';
        wrap.style.bottom = 'auto';
        wrap.style.zIndex = '10050';
        clampAvatarBox();
      } else {
        // Hand the box back to whichever mode's stylesheet owns it.
        wrap.style.position = '';
        wrap.style.left = '';
        wrap.style.top = '';
        wrap.style.right = '';
        wrap.style.bottom = '';
        wrap.style.width = '';
        wrap.style.height = '';
        wrap.style.zIndex = '';
      }
      requestAnimationFrame(() => theodoreAvatar?.resize());
    }

    function setAvatarVisible(on, persist) {
      avatarVisible = !!on;
      document.body.classList.toggle('avatar-on', avatarVisible);
      const btn = $('btn-avatar');
      if (btn) {
        btn.setAttribute('aria-pressed', avatarVisible ? 'true' : 'false');
        btn.textContent = avatarVisible ? lessonChrome().hideAvatar : lessonChrome().showAvatar;
      }
      if (persist !== false) {
        avatarPrefs.on = avatarVisible;
        saveAvatarPrefs();
      }
      if (avatarVisible) {
        applyAvatarPlacement();
        initTheodoreAvatar();
        theodoreAvatar?.setEnabled(true);
        requestAnimationFrame(() => theodoreAvatar?.resize());
      } else {
        theodoreAvatar?.setEnabled(false);
      }
    }

    // First move freezes the current on-screen box, then switches to fixed, so
    // drag and keyboard share one coordinate system in both modes.
    function ensureAvatarPlaced() {
      const wrap = $('theodore-avatar-wrap');
      if (!wrap || avatarPrefs.placed) return;
      const box = wrap.getBoundingClientRect();
      avatarPrefs.placed = true;
      avatarPrefs.x = box.left;
      avatarPrefs.y = box.top;
      avatarPrefs.w = box.width;
      avatarPrefs.h = box.height;
      applyAvatarPlacement();
    }

    function moveAvatarBy(dx, dy) {
      ensureAvatarPlaced();
      if (!avatarPrefs.placed) return;
      avatarPrefs.x += dx;
      avatarPrefs.y += dy;
      clampAvatarBox();
      saveAvatarPrefs();
    }

    function resetAvatarPlacement() {
      avatarPrefs.placed = false;
      delete avatarPrefs.x; delete avatarPrefs.y;
      delete avatarPrefs.w; delete avatarPrefs.h;
      saveAvatarPrefs();
      applyAvatarPlacement();
      toast('Theodore is back in his usual spot.');
    }

    function initAvatarDrag() {
      const wrap = $('theodore-avatar-wrap');
      const handle = $('avatar-drag-handle');
      const grip = $('avatar-resize-handle');
      if (!wrap || !handle || !grip) return;
      avatarHomeParent = wrap.parentElement;
      avatarHomeNext = wrap.nextSibling;
      let mode = null;
      let startX = 0, startY = 0, baseX = 0, baseY = 0, baseW = 0, baseH = 0;

      const onMove = (event) => {
        if (!mode) return;
        const dx = event.clientX - startX;
        const dy = event.clientY - startY;
        if (mode === 'drag') {
          avatarPrefs.x = baseX + dx;
          avatarPrefs.y = baseY + dy;
        } else {
          avatarPrefs.w = Math.max(baseW + dx, AVATAR_MIN_W);
          avatarPrefs.h = Math.max(baseH + dy, AVATAR_MIN_H);
        }
        clampAvatarBox();
      };

      const onUp = (event) => {
        if (!mode) return;
        mode = null;
        wrap.classList.remove('dragging');
        window.removeEventListener('pointermove', onMove);
        window.removeEventListener('pointerup', onUp);
        window.removeEventListener('pointercancel', onUp);
        theodoreAvatar?.resize();
        saveAvatarPrefs();
      };

      const begin = (event, nextMode) => {
        if (event.button != null && event.button !== 0) return;
        event.preventDefault();
        ensureAvatarPlaced();
        mode = nextMode;
        startX = event.clientX; startY = event.clientY;
        baseX = avatarPrefs.x; baseY = avatarPrefs.y;
        baseW = avatarPrefs.w; baseH = avatarPrefs.h;
        wrap.classList.add('dragging');
        window.addEventListener('pointermove', onMove);
        window.addEventListener('pointerup', onUp);
        window.addEventListener('pointercancel', onUp);
      };

      handle.addEventListener('pointerdown', (e) => begin(e, 'drag'));
      grip.addEventListener('pointerdown', (e) => begin(e, 'resize'));
      handle.addEventListener('dblclick', resetAvatarPlacement);

      const nudge = (event) => {
        const step = event.shiftKey ? 1 : 12;
        const keys = { ArrowLeft:[-step,0], ArrowRight:[step,0], ArrowUp:[0,-step], ArrowDown:[0,step] };
        if (keys[event.key]) {
          event.preventDefault();
          moveAvatarBy(keys[event.key][0], keys[event.key][1]);
        } else if (event.key === 'Home') {
          // Not Escape: in presenter mode the browser takes Escape to leave
          // fullscreen, so it would silently reset the placement as well.
          event.preventDefault();
          resetAvatarPlacement();
        }
      };
      handle.addEventListener('keydown', nudge);
      window.addEventListener('resize', clampAvatarBox);
    }

    function presenterActive() {
      const overlay = $('presenter-overlay');
      return !!(overlay && overlay.classList.contains('show'));
    }

    let driveChromeTimer = 0;
    let driveChromeWasHidden = false;
    // Full-screen / on-the-go: clear overlapping controls so the lesson is readable.
    const FS_CHROME_HIDE_MS = 2000;
    function parkSampleClock() {
      // Keep the trial clock out of lesson-window-controls so drive-chrome-hidden
      // cannot hide the 10-minute timer with the options strip.
      const clock = $('sample-clock');
      if (clock && clock.parentElement !== document.body) document.body.appendChild(clock);
    }
    function focusModeActive() {
      return document.body.classList.contains('audio-only') || presenterActive()
        || !!document.fullscreenElement;
    }
    function setDriveChromeHidden(hidden) {
      const wasHidden = document.body.classList.contains('drive-chrome-hidden');
      document.body.classList.toggle('drive-chrome-hidden', !!hidden);
      const edge = $('fs-chrome-edge');
      if (edge) {
        edge.hidden = !hidden || !focusModeActive();
        edge.setAttribute('aria-expanded', String(!hidden));
      }
      if (wasHidden && !hidden) requestAnimationFrame(() => theodoreAvatar?.resize());
    }
    function revealDriveChrome() {
      if (!focusModeActive()) return;
      setDriveChromeHidden(false);
      // Also tuck the language / CC / options strip after the same idle window.
      if (presenterActive() || document.fullscreenElement) setStudioChromeHidden(false);
      clearTimeout(driveChromeTimer);
      driveChromeTimer = setTimeout(() => {
        setDriveChromeHidden(true);
        if (presenterActive() || document.fullscreenElement) setStudioChromeHidden(true);
      }, FS_CHROME_HIDE_MS);
    }
    function setStudioChromeHidden(hidden) {
      document.body.classList.toggle('chrome-hidden', !!hidden);
      const btn = $('btn-chrome');
      if (!btn) return;
      const show = presenterActive() || !!hidden || !!document.fullscreenElement
        || document.body.classList.contains('phone-embed');
      btn.hidden = !show;
      btn.textContent = hidden ? lessonChrome().showOptions : lessonChrome().hideOptions;
      btn.setAttribute('aria-pressed', String(!!hidden));
      btn.title = hidden ? lessonChrome().showOptions : lessonChrome().hideOptions;
    }

    function updateLessonWindowControls() {
      const fullscreen = $('btn-fullscreen');
      if (fullscreen) {
        fullscreen.textContent = presenterActive() ? '×' : '⛶';
        fullscreen.setAttribute(
          'aria-label',
          presenterActive() ? 'Exit full screen lesson' : 'Expand lesson to full screen'
        );
        fullscreen.title = presenterActive() ? 'Exit full screen' : 'Full screen';
      }
      const captions = $('btn-captions');
      if (captions) {
        captions.classList.toggle('is-off', !captionsEnabled);
        captions.setAttribute('aria-pressed', String(captionsEnabled));
        captions.setAttribute(
          'aria-label',
          captionsEnabled ? 'Hide lesson captions' : 'Show lesson captions'
        );
        captions.title = captionsEnabled ? 'Hide captions' : 'Show captions';
      }
    }

    let studentCamStream = null;
    let studentCamTimer = 0;
    let studentAwayTimer = 0;
    let studentCamBusy = false;
    let cameraSawFrame = false;
    let cameraWatchStarted = 0;
    let studentCamGrid = null;
    let faceDetector = null;

    function setLearningStatus(text) {
      const status = $('student-cam-status');
      if (status) status.textContent = text;
    }

    function detectPhoneFromGrid(grid, gazeDown) {
      if (!grid || !grid.length || !grid[0]) return { below: false, ear: false };
      const h = grid.length;
      const w = grid[0].length;
      const y0 = Math.floor(h * 0.42);
      const x0 = Math.floor(w * 0.15);
      const x1 = Math.floor(w * 0.85);
      let bright = 0, dark = 0, n = 0, sum = 0, sum2 = 0;
      for (let y = y0; y < h; y += 1) {
        for (let x = x0; x < x1; x += 1) {
          const v = grid[y][x];
          n += 1; sum += v; sum2 += v * v;
          if (v > 0.55) bright += 1;
          if (v < 0.22) dark += 1;
        }
      }
      const mean = n ? sum / n : 0;
      const variance = n ? Math.max(0, sum2 / n - mean * mean) : 0;
      const brightRatio = n ? bright / n : 0;
      const darkRatio = n ? dark / n : 0;
      const litScreen = brightRatio >= 0.08 && variance >= 0.008;
      const darkDevice = darkRatio >= 0.12 && variance >= 0.006 && mean <= 0.52;
      const below = gazeDown >= 0.45 && (litScreen || darkDevice);
      const yEarEnd = Math.floor(h * 0.65);
      const xLeftEdge = Math.floor(w * 0.22);
      const xRightStart = Math.floor(w * 0.78);
      let darkLeft = 0, totalLeft = 0, darkRight = 0, totalRight = 0;
      for (let y = 0; y < yEarEnd; y += 1) {
        for (let x = 0; x < xLeftEdge; x += 1) {
          totalLeft += 1;
          if (grid[y][x] < 0.18) darkLeft += 1;
        }
        for (let x = xRightStart; x < w; x += 1) {
          totalRight += 1;
          if (grid[y][x] < 0.18) darkRight += 1;
        }
      }
      const leftRatio = totalLeft ? darkLeft / totalLeft : 0;
      const rightRatio = totalRight ? darkRight / totalRight : 0;
      const ear = Math.abs(leftRatio - rightRatio) > 0.35
        && Math.max(leftRatio, rightRatio) > 0.55
        && gazeDown < 0.30;
      return { below: below, ear: ear };
    }

    function detectHandsOnFace(grid, gazeDown, facePresent) {
      if (!grid || grid.length < 8 || !facePresent) return 0;
      const h = grid.length;
      const w = grid[0].length;
      let chinDark = 0, chinN = 0;
      for (let y = Math.floor(h * 0.62); y < Math.min(h, Math.floor(h * 0.86)); y += 1) {
        for (let x = Math.floor(w * 0.28); x < Math.floor(w * 0.72); x += 1) {
          chinN += 1;
          if (grid[y][x] < 0.27) chinDark += 1;
        }
      }
      const chinScore = Math.max(0, Math.min(1, ((chinN ? chinDark / chinN : 0) - 0.07) / 0.22));
      let leftSum = 0, leftN = 0, rightSum = 0, rightN = 0;
      for (let y = Math.floor(h * 0.30); y < Math.floor(h * 0.65); y += 1) {
        for (let x = Math.floor(w * 0.08); x < Math.floor(w * 0.33); x += 1) { leftSum += grid[y][x]; leftN += 1; }
        for (let x = Math.floor(w * 0.67); x < Math.floor(w * 0.92); x += 1) { rightSum += grid[y][x]; rightN += 1; }
      }
      const asym = Math.abs((leftN ? leftSum / leftN : 0.5) - (rightN ? rightSum / rightN : 0.5));
      const asymScore = Math.max(0, Math.min(1, (asym - 0.04) / 0.18));
      const faceVals = [];
      for (let y = Math.floor(h * 0.10); y < Math.floor(h * 0.75); y += 1) {
        for (let x = Math.floor(w * 0.22); x < Math.floor(w * 0.78); x += 1) faceVals.push(grid[y][x]);
      }
      const faceMean = faceVals.reduce((a, b) => a + b, 0) / Math.max(1, faceVals.length);
      const faceVar = faceVals.reduce((a, v) => a + (v - faceMean) ** 2, 0) / Math.max(1, faceVals.length);
      const varScore = Math.max(0, Math.min(1, (0.065 - Math.sqrt(faceVar)) / 0.038));
      const gazeBoost = gazeDown > 0.20 ? 1 + Math.min(0.35, (gazeDown - 0.20) * 1.2) : 1;
      return Math.max(0, Math.min(1, (chinScore * 0.48 + asymScore * 0.28 + varScore * 0.24) * gazeBoost));
    }

    function luminanceGrid(ctx, width, height) {
      const cols = 64;
      const rows = 36;
      const data = ctx.getImageData(0, 0, width, height).data;
      const grid = [];
      let sum = 0;
      let count = 0;
      let motion = 0;
      for (let y = 0; y < rows; y += 1) {
        const row = [];
        for (let x = 0; x < cols; x += 1) {
          const px = Math.min(width - 1, Math.floor((x + 0.5) * width / cols));
          const py = Math.min(height - 1, Math.floor((y + 0.5) * height / rows));
          const i = (py * width + px) * 4;
          const luma = (0.2126 * data[i] + 0.7152 * data[i + 1] + 0.0722 * data[i + 2]) / 255;
          row.push(Math.round(luma * 1000) / 1000);
          sum += luma;
          count += 1;
          if (studentCamGrid && studentCamGrid[y] && studentCamGrid[y][x] != null) {
            motion += Math.abs(luma - studentCamGrid[y][x]);
          }
        }
        grid.push(row);
      }
      studentCamGrid = grid;
      return {
        grid: grid,
        light: count ? sum / count : 0,
        motion: count ? Math.min(1, motion / count) : 0,
        foreground: count ? grid.flat().filter((v) => v > 0.18).length / count : 0,
      };
    }

    let meshReady = false;
    let meshEyesClosedSince = 0;
    let lessonFaceMesh = null;
    let lessonFaceMeshPromise = null;
    let lessonHandMesh = null;
    let lessonHandPromise = null;
    let lessonHandFailed = false;
    let lessonPoseMesh = null;
    let lessonPosePromise = null;
    let lessonPoseFailed = false;
    let lessonDetectTs = 0;
    let lessonTrackCache = null;
    let studentTrackOn = false;
    let studentTrackTimer = 0;
    function nextLessonDetectTs() {
      const now = performance.now();
      lessonDetectTs = Math.max(lessonDetectTs + 1, now);
      return lessonDetectTs;
    }
    const OWNER_FP_IDX = [33, 263, 1, 61, 291, 10, 152];
    let lessonOwner = {
      enrolled: false, enrollStartedMs: 0, fingerprint: null, lastBox: null, displayName: '',
    };
    try {
      const savedOwner = JSON.parse(localStorage.getItem('studio.faceid.v1') || 'null');
      if (savedOwner && Array.isArray(savedOwner.fingerprint) && savedOwner.fingerprint.length >= 4) {
        lessonOwner = {
          enrolled: true, enrollStartedMs: 0,
          fingerprint: savedOwner.fingerprint.map(Number),
          lastBox: savedOwner.lastBox || null,
          displayName: String(savedOwner.name || 'Learner'),
        };
      }
    } catch (_) {}

    function blendMap(blendshapes, index) {
      const entry = blendshapes && blendshapes[index];
      const cats = entry && (entry.categories || entry);
      const out = {};
      if (!cats || !cats.forEach) return out;
      cats.forEach((item) => {
        const name = item.categoryName || item.displayName || '';
        if (name) out[name] = Number(item.score) || 0;
      });
      return out;
    }

    async function ensureLessonFaceMesh() {
      if (lessonFaceMesh) return lessonFaceMesh;
      if (lessonFaceMeshPromise) return lessonFaceMeshPromise;
      lessonFaceMeshPromise = (async () => {
        const src = {
          esm: 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/+esm',
          wasm: 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/wasm',
          model: 'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task',
        };
        try {
          const vision = await import(src.esm);
          const fileset = await vision.FilesetResolver.forVisionTasks(src.wasm);
          for (const delegate of ['GPU', 'CPU']) {
            try {
              lessonFaceMesh = await vision.FaceLandmarker.createFromOptions(fileset, {
                baseOptions: { modelAssetPath: src.model, delegate: delegate },
                runningMode: 'VIDEO',
                numFaces: 3,
                outputFaceBlendshapes: true,
              });
              lessonFaceMesh._contours = vision.FaceLandmarker.FACE_LANDMARKS_CONTOURS
                || vision.FaceLandmarker.FACE_LANDMARKS_FACE_OVAL;
              lessonFaceMesh._oval = vision.FaceLandmarker.FACE_LANDMARKS_FACE_OVAL;
              lessonFaceMesh._lips = vision.FaceLandmarker.FACE_LANDMARKS_LIPS;
              meshReady = true;
              return lessonFaceMesh;
            } catch (_) {}
          }
        } catch (_) {}
        return null;
      })();
      return lessonFaceMeshPromise;
    }

    function lessonFaceBox(pts) {
      if (!pts || !pts.length) return null;
      let minX = 1, maxX = 0, minY = 1, maxY = 0;
      pts.forEach((p) => {
        if (!p) return;
        if (p.x < minX) minX = p.x; if (p.x > maxX) maxX = p.x;
        if (p.y < minY) minY = p.y; if (p.y > maxY) maxY = p.y;
      });
      return { x: minX, y: minY, w: Math.max(0, maxX - minX), h: Math.max(0, maxY - minY) };
    }

    function lessonBoxIoU(a, b) {
      if (!a || !b) return 0;
      const x0 = Math.max(a.x, b.x), y0 = Math.max(a.y, b.y);
      const x1 = Math.min(a.x + a.w, b.x + b.w), y1 = Math.min(a.y + a.h, b.y + b.h);
      const inter = Math.max(0, x1 - x0) * Math.max(0, y1 - y0);
      if (inter <= 0) return 0;
      const union = a.w * a.h + b.w * b.h - inter;
      return union > 0 ? inter / union : 0;
    }

    function lessonFacePrint(pts) {
      if (!pts) return null;
      const left = pts[33], right = pts[263];
      if (!left || !right) return null;
      const iod = Math.hypot(right.x - left.x, right.y - left.y);
      if (iod < 1e-6) return null;
      const midX = (left.x + right.x) / 2, midY = (left.y + right.y) / 2;
      const out = [];
      for (let i = 0; i < OWNER_FP_IDX.length; i++) {
        const p = pts[OWNER_FP_IDX[i]];
        if (!p) return null;
        out.push((p.x - midX) / iod, (p.y - midY) / iod);
      }
      return out;
    }

    function lessonPrintDistance(a, b) {
      if (!a || !b || a.length !== b.length) return 1;
      let acc = 0;
      for (let i = 0; i < a.length; i++) acc += (a[i] - b[i]) * (a[i] - b[i]);
      return Math.sqrt(acc / a.length);
    }

    function lessonOwnerScore(pts) {
      const box = lessonFaceBox(pts);
      const iou = lessonBoxIoU(box, lessonOwner.lastBox);
      const fpPart = Math.max(0, 1 - lessonPrintDistance(lessonFacePrint(pts), lessonOwner.fingerprint) / 0.38);
      return Math.max(0, Math.min(1, 0.45 * iou + 0.55 * fpPart));
    }

    function pickLessonOwner(faces, nowMs) {
      const name = lessonOwner.displayName || (typeof learnerId === 'string' && learnerId) || 'Learner';
      if (!faces.length) {
        return {
          index: -1, owner_enrolled: lessonOwner.enrolled, owner_match: null,
          match_score: 0, secondary_count: 0, display_name: name,
        };
      }
      if (!lessonOwner.enrolled) {
        let idx = 0, bestArea = -1;
        faces.forEach((pts, i) => {
          const box = lessonFaceBox(pts);
          const area = box ? box.w * box.h : 0;
          if (area > bestArea) { bestArea = area; idx = i; }
        });
        if (lessonOwner.fingerprint || lessonOwner.lastBox) {
          let bestI = -1, bestScore = -1;
          faces.forEach((pts, i) => {
            const score = lessonOwnerScore(pts);
            if (score > bestScore) { bestScore = score; bestI = i; }
          });
          if (bestI >= 0 && bestScore >= 0.28) idx = bestI;
          else lessonOwner.enrollStartedMs = nowMs;
        } else {
          lessonOwner.enrollStartedMs = nowMs;
        }
        const box = lessonFaceBox(faces[idx]);
        const fp = lessonFacePrint(faces[idx]);
        if (!lessonOwner.enrollStartedMs) lessonOwner.enrollStartedMs = nowMs;
        lessonOwner.lastBox = box;
        if (fp) lessonOwner.fingerprint = fp.slice();
        if ((nowMs - lessonOwner.enrollStartedMs) >= 1500 && fp && box) {
          lessonOwner.enrolled = true;
          lessonOwner.displayName = name;
          try {
            localStorage.setItem('studio.faceid.v1', JSON.stringify({
              name: name, fingerprint: fp.slice(), lastBox: box, savedAt: nowMs,
            }));
          } catch (_) {}
          return {
            index: idx, owner_enrolled: true, owner_match: true, match_score: 1,
            secondary_count: Math.max(0, faces.length - 1), display_name: name,
          };
        }
        return {
          index: idx, owner_enrolled: false, owner_match: null, match_score: 0,
          secondary_count: Math.max(0, faces.length - 1), display_name: name,
        };
      }
      let bestI = 0, bestScore = -1;
      faces.forEach((pts, i) => {
        const score = lessonOwnerScore(pts);
        if (score > bestScore) { bestScore = score; bestI = i; }
      });
      if (bestScore >= 0.55) {
        const box = lessonFaceBox(faces[bestI]);
        const fp = lessonFacePrint(faces[bestI]);
        if (box && lessonOwner.lastBox) {
          const lb = lessonOwner.lastBox;
          lessonOwner.lastBox = {
            x: 0.7 * lb.x + 0.3 * box.x, y: 0.7 * lb.y + 0.3 * box.y,
            w: 0.7 * lb.w + 0.3 * box.w, h: 0.7 * lb.h + 0.3 * box.h,
          };
        } else if (box) lessonOwner.lastBox = box;
        if (fp && lessonOwner.fingerprint && lessonPrintDistance(fp, lessonOwner.fingerprint) <= 0.38) {
          lessonOwner.fingerprint = lessonOwner.fingerprint.map((v, i) => 0.85 * v + 0.15 * fp[i]);
        }
        return {
          index: bestI, owner_enrolled: true, owner_match: true, match_score: bestScore,
          secondary_count: Math.max(0, faces.length - 1), display_name: name,
        };
      }
      return {
        index: -1, owner_enrolled: true, owner_match: false, match_score: Math.max(0, bestScore),
        secondary_count: faces.length, display_name: name,
      };
    }

    function meshFacial(result) {
      const faces = (result && result.faceLandmarks) || [];
      const pick = pickLessonOwner(faces, Date.now());
      const owner = {
        owner_face_enrolled: !!pick.owner_enrolled,
        owner_face_match: pick.owner_match,
        owner_match_score: pick.match_score,
        owner_face_name: pick.display_name || null,
      };
      if (!faces.length) {
        meshEyesClosedSince = 0;
        return Object.assign({
          face_count: 0,
          secondary_face_count: 0,
          detector_source: 'face_mesh',
          liveness_state: 'missing',
          gaze_frontal: 0.1,
          gaze_down_score: 0.05,
          gaze_left_score: 0,
          gaze_right_score: 0,
          expression_label: 'unknown',
          eyes_closed_score: 0,
          yawn_score: 0,
          face_size_ratio: null,
          face_pts: null,
        }, owner);
      }
      if (pick.owner_enrolled && pick.owner_match === false) {
        meshEyesClosedSince = 0;
        return Object.assign({
          face_count: faces.length,
          secondary_face_count: pick.secondary_count,
          detector_source: 'face_mesh',
          liveness_state: 'live',
          gaze_frontal: 0,
          gaze_down_score: 0,
          gaze_left_score: 0,
          gaze_right_score: 0,
          expression_label: 'unknown',
          eyes_closed_score: 0,
          yawn_score: 0,
          face_size_ratio: null,
          face_pts: null,
        }, owner);
      }
      const faceIndex = pick.index >= 0 ? pick.index : 0;
      const pts = faces[faceIndex];
      const bs = blendMap(result.faceBlendshapes, faceIndex);
      const nose = pts[1];
      const leftEye = pts[33];
      const rightEye = pts[263];
      let gazeFrontal = 0.85;
      let gazeLeft = 0;
      let gazeRight = 0;
      if (nose && leftEye && rightEye) {
        const midX = (leftEye.x + rightEye.x) / 2;
        const shift = (nose.x - midX) * 8;
        gazeFrontal = Math.max(0, Math.min(1, 1 - Math.abs(nose.x - midX) * 6));
        if (shift < -0.15) gazeLeft = Math.max(0, Math.min(1, (-shift - 0.15) / 0.5));
        if (shift > 0.15) gazeRight = Math.max(0, Math.min(1, (shift - 0.15) / 0.5));
      }
      const lookDown = ((bs.eyeLookDownLeft || 0) + (bs.eyeLookDownRight || 0)) / 2;
      const lookUp = ((bs.eyeLookUpLeft || 0) + (bs.eyeLookUpRight || 0)) / 2;
      const blink = ((bs.eyeBlinkLeft || 0) + (bs.eyeBlinkRight || 0)) / 2;
      const gazeDown = Math.max(0, Math.min(1, (lookDown - lookUp - 0.25) / 0.5));
      const now = Date.now();
      const lidsDown = blink >= 0.45;
      if (!lidsDown) meshEyesClosedSince = 0;
      else if (!meshEyesClosedSince) meshEyesClosedSince = now;
      const eyesClosed = lidsDown && now - meshEyesClosedSince >= 400;
      if (eyesClosed) gazeFrontal = Math.min(gazeFrontal, 0.25);
      const smile = ((bs.mouthSmileLeft || 0) + (bs.mouthSmileRight || 0)) / 2;
      const jaw = bs.jawOpen || 0;
      const browUp = bs.browInnerUp || 0;
      const yawn = Math.max(0, Math.min(1, jaw * 1.15 * (1 - smile * 1.2) * (1 - Math.max(0, browUp - 0.22) * 1.4)));
      const yawning = yawn >= 0.48 && yawn >= smile + 0.1 && jaw >= 0.4;
      let faceH = 0.3;
      if (pts.length) {
        let minY = 1;
        let maxY = 0;
        pts.forEach((p) => { if (p.y < minY) minY = p.y; if (p.y > maxY) maxY = p.y; });
        faceH = Math.max(0.05, Math.min(0.9, maxY - minY));
      }
      return Object.assign({
        face_count: faces.length,
        secondary_face_count: pick.secondary_count,
        detector_source: 'face_mesh',
        liveness_state: 'live',
        gaze_frontal: gazeFrontal,
        gaze_down_score: gazeDown,
        gaze_left_score: gazeLeft,
        gaze_right_score: gazeRight,
        expression_label: yawning ? 'yawning' : 'neutral',
        eyes_closed_score: eyesClosed ? Math.max(0.6, blink) : Math.min(blink, 0.3),
        yawn_score: yawning ? Math.max(yawn, 0.62) : yawn,
        face_size_ratio: faceH,
        face_pts: pts,
      }, owner);
    }

    async function ensureLessonHands() {
      if (lessonHandMesh) return lessonHandMesh;
      if (lessonHandFailed) return null;
      if (lessonHandPromise) return lessonHandPromise;
      lessonHandPromise = (async () => {
        try {
          const vision = await import('https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/+esm');
          const fileset = await vision.FilesetResolver.forVisionTasks(
            'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/wasm'
          );
          const model = 'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task';
          for (const delegate of ['GPU', 'CPU']) {
            try {
              lessonHandMesh = await vision.HandLandmarker.createFromOptions(fileset, {
                baseOptions: { modelAssetPath: model, delegate: delegate },
                runningMode: 'VIDEO',
                numHands: 2,
              });
              lessonHandMesh._links = vision.HandLandmarker.HAND_CONNECTIONS;
              return lessonHandMesh;
            } catch (_) {}
          }
        } catch (_) {}
        lessonHandFailed = true;
        return null;
      })();
      return lessonHandPromise;
    }

    async function ensureLessonPose() {
      if (lessonPoseMesh) return lessonPoseMesh;
      if (lessonPoseFailed) return null;
      if (lessonPosePromise) return lessonPosePromise;
      lessonPosePromise = (async () => {
        try {
          const vision = await import('https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/+esm');
          const fileset = await vision.FilesetResolver.forVisionTasks(
            'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/wasm'
          );
          const model = 'https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task';
          for (const delegate of ['GPU', 'CPU']) {
            try {
              lessonPoseMesh = await vision.PoseLandmarker.createFromOptions(fileset, {
                baseOptions: { modelAssetPath: model, delegate: delegate },
                runningMode: 'VIDEO',
                numPoses: 1,
              });
              lessonPoseMesh._links = vision.PoseLandmarker.POSE_CONNECTIONS;
              return lessonPoseMesh;
            } catch (_) {}
          }
        } catch (_) {}
        lessonPoseFailed = true;
        return null;
      })();
      return lessonPosePromise;
    }

    function handsCoveringFace(hands, facePts) {
      if (!hands || !hands.length || !facePts || !facePts.length) return 0;
      let minX = 1, maxX = 0, minY = 1, maxY = 0;
      facePts.forEach((p) => {
        if (p.x < minX) minX = p.x; if (p.x > maxX) maxX = p.x;
        if (p.y < minY) minY = p.y; if (p.y > maxY) maxY = p.y;
      });
      const cx = (minX + maxX) / 2, cy = (minY + maxY) / 2;
      const rx = Math.max(1e-4, (maxX - minX) / 2) * 1.15;
      const ry = Math.max(1e-4, (maxY - minY) / 2) * 1.15;
      let best = 0;
      hands.forEach((pts) => {
        let inside = 0;
        pts.forEach((p) => {
          const dx = (p.x - cx) / rx, dy = (p.y - cy) / ry;
          if (dx * dx + dy * dy <= 1) inside += 1;
        });
        best = Math.max(best, inside / Math.max(1, pts.length));
      });
      return Math.max(0, Math.min(1, (best - 0.15) / 0.40));
    }

    function handsBelowFace(hands, facePts) {
      if (!hands || !hands.length || !facePts || !facePts.length) return 0;
      let faceMaxY = 0, faceMinY = 1;
      facePts.forEach((p) => {
        if (p.y > faceMaxY) faceMaxY = p.y;
        if (p.y < faceMinY) faceMinY = p.y;
      });
      const chinLine = faceMaxY - (faceMaxY - faceMinY) * 0.05;
      let best = 0;
      hands.forEach((pts) => {
        let below = 0;
        pts.forEach((p) => { if (p.y > chinLine) below += 1; });
        best = Math.max(best, below / Math.max(1, pts.length));
      });
      return Math.max(0, Math.min(1, (best - 0.35) / 0.50));
    }

    async function lessonHandSample(video, facePts) {
      const hl = await ensureLessonHands();
      if (!hl || !video || !video.videoWidth) return null;
      let result;
      try { result = hl.detectForVideo(video, nextLessonDetectTs()); }
      catch (_) { return null; }
      const hands = (result && result.landmarks) || [];
      if (!hands.length) return { hands_on_face_score: 0, hand_below: 0 };
      return {
        hands_on_face_score: handsCoveringFace(hands, facePts),
        hand_below: handsBelowFace(hands, facePts),
      };
    }

    function lessonLinkPairs(list) {
      const out = [];
      if (!list || !list.length) return out;
      for (let i = 0; i < list.length; i++) {
        const link = list[i];
        const a = link && link.start != null ? link.start : link && link[0];
        const b = link && link.end != null ? link.end : link && link[1];
        if (a != null && b != null) out.push([a, b]);
      }
      return out;
    }

    function lessonTrackXY(nx, ny, video, w, h) {
      const vw = video.videoWidth || 1;
      const vh = video.videoHeight || 1;
      const scale = Math.max(w / vw, h / vh);
      const dw = vw * scale;
      const dh = vh * scale;
      return { x: (w - dw) / 2 + nx * dw, y: (h - dh) / 2 + ny * dh };
    }

    function strokeLessonLinks(ctx, pts, links, color, video, w, h, width) {
      if (!pts || !links || !links.length) return;
      ctx.save();
      ctx.strokeStyle = color;
      ctx.lineWidth = width;
      ctx.lineJoin = 'round';
      ctx.lineCap = 'round';
      ctx.beginPath();
      links.forEach((pair) => {
        const a = pts[pair[0]];
        const b = pts[pair[1]];
        if (!a || !b) return;
        const pa = lessonTrackXY(a.x, a.y, video, w, h);
        const pb = lessonTrackXY(b.x, b.y, video, w, h);
        ctx.moveTo(pa.x, pa.y);
        ctx.lineTo(pb.x, pb.y);
      });
      ctx.stroke();
      ctx.restore();
    }

    function drawLessonFingers(ctx, pts, video, w, h) {
      ctx.save();
      ctx.fillStyle = '#fff7ed';
      [4, 8, 12, 16, 20].forEach((index) => {
        const tip = pts[index];
        if (!tip) return;
        const p = lessonTrackXY(tip.x, tip.y, video, w, h);
        ctx.beginPath();
        ctx.arc(p.x, p.y, Math.max(2.5, w * 0.012), 0, Math.PI * 2);
        ctx.fill();
      });
      ctx.restore();
    }

    function paintLessonFallback(ctx, box, video, w, h) {
      if (!box) return;
      const x0 = lessonTrackXY(box.x / (video.videoWidth || 1), box.y / (video.videoHeight || 1), video, w, h);
      const x1 = lessonTrackXY((box.x + box.width) / (video.videoWidth || 1), (box.y + box.height) / (video.videoHeight || 1), video, w, h);
      const bw = x1.x - x0.x;
      const bh = x1.y - x0.y;
      ctx.save();
      ctx.strokeStyle = '#67e8f9';
      ctx.lineWidth = Math.max(1.5, w * 0.01);
      ctx.beginPath();
      ctx.ellipse(x0.x + bw / 2, x0.y + bh * 0.48, Math.abs(bw) * 0.42, Math.abs(bh) * 0.48, 0, 0, Math.PI * 2);
      ctx.stroke();
      ctx.beginPath();
      ctx.ellipse(x0.x + bw * 0.32, x0.y + bh * 0.38, Math.abs(bw) * 0.08, Math.abs(bh) * 0.045, 0, 0, Math.PI * 2);
      ctx.ellipse(x0.x + bw * 0.68, x0.y + bh * 0.38, Math.abs(bw) * 0.08, Math.abs(bh) * 0.045, 0, 0, Math.PI * 2);
      ctx.moveTo(x0.x + bw * 0.32, x0.y + bh * 0.68);
      ctx.quadraticCurveTo(x0.x + bw * 0.5, x0.y + bh * 0.76, x0.x + bw * 0.68, x0.y + bh * 0.68);
      ctx.stroke();
      ctx.restore();
    }

    async function paintStudentTracking() {
      if (!studentTrackOn) return;
      try {
      const video = $('student-cam-video');
      const canvas = $('student-cam-track');
      const box = $('student-cam');
      const shown = box && !box.hidden && !box.classList.contains('is-hidden')
        && getComputedStyle(box).display !== 'none' && document.visibilityState !== 'hidden';
      const videoLive = video && video.readyState >= 2 && video.videoWidth
        && document.visibilityState !== 'hidden';
      if (videoLive) {
        let w = 1;
        let h = 1;
        let ctx = null;
        if (shown && canvas) {
          w = Math.max(1, Math.round((canvas.clientWidth || 176) * Math.min(2, window.devicePixelRatio || 1)));
          h = Math.max(1, Math.round((canvas.clientHeight || 99) * Math.min(2, window.devicePixelRatio || 1)));
          if (canvas.width !== w || canvas.height !== h) {
            canvas.width = w;
            canvas.height = h;
          }
          ctx = canvas.getContext('2d');
          if (ctx) ctx.clearRect(0, 0, w, h);
        }
        {
          const width = Math.max(1.5, w * 0.008);
          const faceMarker = await ensureLessonFaceMesh();
          const handMarker = await ensureLessonHands();
          const poseMarker = await ensureLessonPose();
          let faceResult = null;
          let handResult = null;
          let poseResult = null;
          try { if (faceMarker) faceResult = faceMarker.detectForVideo(video, nextLessonDetectTs()); }
          catch (_) { faceResult = null; }
          try { if (handMarker) handResult = handMarker.detectForVideo(video, nextLessonDetectTs()); }
          catch (_) { handResult = null; }
          try { if (poseMarker) poseResult = poseMarker.detectForVideo(video, nextLessonDetectTs()); }
          catch (_) { poseResult = null; }
          const faces = (faceResult && faceResult.faceLandmarks) || [];
          const facial = faceResult ? meshFacial(faceResult) : null;
          const hands = (handResult && handResult.landmarks) || [];
          const facePts = facial && facial.face_pts;
          let seenBox = false;
          lessonTrackCache = {
            at: Date.now(),
            facial: facial && facial.face_count > 0 ? facial : null,
            seenPose: !!(poseResult && poseResult.landmarks && poseResult.landmarks.length),
            seenHands: hands.length > 0,
            seenBox: false,
            handTrack: hands.length ? {
              hands_on_face_score: handsCoveringFace(hands, facePts),
              hand_below: handsBelowFace(hands, facePts),
            } : { hands_on_face_score: 0, hand_below: 0 },
          };
          if (ctx) {
            (poseResult && poseResult.landmarks || []).forEach((pts) => {
              strokeLessonLinks(ctx, pts, lessonLinkPairs(poseMarker && poseMarker._links), '#5eead4', video, w, h, width);
            });
            faces.forEach((pts) => {
              strokeLessonLinks(ctx, pts, lessonLinkPairs(faceMarker && (faceMarker._contours || faceMarker._oval)), '#67e8f9', video, w, h, width);
              strokeLessonLinks(ctx, pts, lessonLinkPairs(faceMarker && faceMarker._lips), '#fb7185', video, w, h, Math.max(width, 2));
            });
            hands.forEach((pts) => {
              strokeLessonLinks(ctx, pts, lessonLinkPairs(handMarker && handMarker._links), '#fbbf24', video, w, h, width);
              drawLessonFingers(ctx, pts, video, w, h);
            });
          }
          if (!faces.length && !hands.length && !(poseResult && poseResult.landmarks && poseResult.landmarks.length)) {
            const DetectorCtor = window.FaceDetector;
            if (typeof DetectorCtor === 'function') {
              try {
                if (!faceDetector) faceDetector = new DetectorCtor({ fastMode: true, maxDetectedFaces: 1 });
                const found = await faceDetector.detect(video);
                if (found[0] && found[0].boundingBox) {
                  seenBox = true;
                  if (ctx) paintLessonFallback(ctx, found[0].boundingBox, video, w, h);
                }
              } catch (_) {}
            }
          }
          if (lessonTrackCache) lessonTrackCache.seenBox = seenBox;
          const personSeen = !!(
            (lessonTrackCache && lessonTrackCache.facial && lessonTrackCache.facial.face_count > 0)
            || (lessonTrackCache && (lessonTrackCache.seenPose || lessonTrackCache.seenHands || lessonTrackCache.seenBox))
          );
          noteStudentInFrame(personSeen);
        }
      }
      } catch (_) { /* one missed frame must not stop the outline */ }
      if (studentTrackOn) studentTrackTimer = window.setTimeout(() => { void paintStudentTracking(); }, 90);
    }

    function startStudentTracking() {
      if (studentTrackOn) return;
      studentTrackOn = true;
      void paintStudentTracking();
    }

    function stopStudentTracking() {
      studentTrackOn = false;
      if (studentTrackTimer) {
        window.clearTimeout(studentTrackTimer);
        studentTrackTimer = 0;
      }
    }

    async function studentCameraSample() {
      if (studentCamBusy || !lastTeachPayload) return;
      if (!cameraWatchStarted) cameraWatchStarted = Date.now();
      const video = $('student-cam-video');
      if (!studentCamStream && video && video.srcObject) studentCamStream = video.srcObject;
      const canvas = $('student-cam-sample');
      const hiddenTab = document.visibilityState === 'hidden';
      const live = !hiddenTab && video && canvas && video.readyState >= 2 && video.videoWidth;
      if (live) cameraSawFrame = true;
      else if (!cameraSawFrame && !hiddenTab && Date.now() - cameraWatchStarted < 8000) {
        setLearningStatus('Starting camera…');
        return;
      }
      studentCamBusy = true;
      try {
        let faces = [];
        let detectorFailed = false;
        let facial = null;
        let freshTrack = false;
        let sample = { grid: null, light: 0, motion: 0, foreground: 0 };
        const DetectorCtor = window.FaceDetector;
        const detectorRan = typeof DetectorCtor === 'function';
        if (live) {
          canvas.width = 64;
          canvas.height = 36;
          const ctx = canvas.getContext('2d', { willReadFrequently: true });
          if (ctx) {
            ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
            sample = luminanceGrid(ctx, canvas.width, canvas.height);
          }
          freshTrack = !!(lessonTrackCache && (Date.now() - lessonTrackCache.at) < 800);
          if (freshTrack && lessonTrackCache.facial && lessonTrackCache.facial.face_count > 0) {
            facial = lessonTrackCache.facial;
          }
          if (!facial) {
            const landmarker = await Promise.race([
              ensureLessonFaceMesh(),
              new Promise((resolve) => setTimeout(() => resolve(null), 1200)),
            ]);
            if (landmarker) {
              try { facial = meshFacial(landmarker.detectForVideo(video, nextLessonDetectTs())); }
              catch (_) { facial = null; }
            }
          }
          if (facial && !(facial.face_count > 0)) facial = null;
          if (!facial && detectorRan) {
            try {
              if (!faceDetector) faceDetector = new DetectorCtor({ fastMode: true, maxDetectedFaces: 3 });
              faces = await faceDetector.detect(video);
            } catch (_) {
              faces = [];
              detectorFailed = true;
            }
          }
        }
        const box = faces[0] && faces[0].boundingBox;
        const frameW = video && video.videoWidth ? video.videoWidth : 1;
        const frameH = video && video.videoHeight ? video.videoHeight : 1;
        let gazeFrontal = null;
        let gazeDown = 0;
        let faceRatio = null;
        if (box && !hiddenTab) {
          const cx = (box.x + box.width / 2) / frameW;
          const cy = (box.y + box.height / 2) / frameH;
          const offX = Math.abs(cx - 0.5);
          if (offX >= 0.22) gazeFrontal = Math.max(0, Math.min(1, 1 - offX * 2.2));
          if (cy >= 0.72) gazeDown = Math.max(0, Math.min(1, (cy - 0.62) / 0.28));
          faceRatio = Math.max(0, Math.min(1, Math.max(box.width / frameW, box.height / frameH)));
        }
        const phoneGaze = facial ? facial.gaze_down_score : gazeDown;
        const phone = sample.grid ? detectPhoneFromGrid(sample.grid, phoneGaze) : { below: false, ear: false };
        const hands = detectHandsOnFace(sample.grid, phoneGaze, (facial ? facial.face_count : faces.length) > 0 && !hiddenTab);
        let detectorSource = 'coarse';
        if (!detectorFailed && (hiddenTab || !live || detectorRan)) detectorSource = 'face_detector';
        const signal = {
          face_count: (live && !hiddenTab) ? faces.length : 0,
          secondary_face_count: Math.max(0, faces.length - 1),
          liveness_state: (live && faces.length && !hiddenTab) ? 'live' : 'missing',
          foreground_ratio: sample.foreground,
          motion_score: sample.motion,
          gaze_down_score: faces.length && gazeDown >= 0.55 ? gazeDown : null,
          face_size_ratio: faceRatio,
          hands_on_face_score: hands > 0 ? Math.round(hands * 1000) / 1000 : null,
          phone_visible: !!(phone.below || phone.ear),
          screen_focus_score: hiddenTab ? 0.15 : 1,
          mean_luminance: sample.grid ? sample.light : null,
          luminance_grid: sample.grid,
        };
        if (gazeFrontal != null) signal.gaze_frontal = gazeFrontal;
        if (detectorSource) signal.detector_source = detectorSource;
        if (facial) {
          const facePts = facial.face_pts || null;
          signal.face_count = facial.face_count;
          signal.secondary_face_count = facial.secondary_face_count;
          signal.liveness_state = hiddenTab ? 'missing' : facial.liveness_state;
          signal.detector_source = 'face_mesh';
          signal.gaze_frontal = facial.gaze_frontal;
          signal.gaze_down_score = facial.gaze_down_score;
          signal.gaze_left_score = facial.gaze_left_score;
          signal.gaze_right_score = facial.gaze_right_score;
          signal.face_size_ratio = facial.face_size_ratio;
          signal.expression_label = facial.expression_label;
          signal.eyes_closed_score = facial.eyes_closed_score;
          signal.yawn_score = facial.yawn_score;
          signal.owner_face_enrolled = !!facial.owner_face_enrolled;
          if (facial.owner_face_match === true || facial.owner_face_match === false) {
            signal.owner_face_match = facial.owner_face_match;
          }
          if (facial.owner_match_score != null) signal.owner_match_score = facial.owner_match_score;
          if (facial.owner_face_name) signal.owner_face_name = facial.owner_face_name;
          delete signal.luminance_grid;
          const handTrack = (freshTrack && lessonTrackCache && lessonTrackCache.handTrack)
            ? lessonTrackCache.handTrack
            : (live ? await lessonHandSample(video, facePts) : null);
          if (handTrack && handTrack.hands_on_face_score > 0.05) {
            signal.hands_on_face_score = Math.round(handTrack.hands_on_face_score * 1000) / 1000;
          }
          if (handTrack && handTrack.hand_below >= 0.55) signal.phone_visible = true;
        }
        const bodySeen = freshTrack && lessonTrackCache && (
          lessonTrackCache.seenPose || lessonTrackCache.seenHands || lessonTrackCache.seenBox
        );
        if (!(signal.face_count > 0) && bodySeen && !hiddenTab) {
          signal.face_count = 1;
          signal.secondary_face_count = 0;
          signal.liveness_state = 'live';
          signal.detector_source = 'pose';
          signal.foreground_ratio = Math.max(signal.foreground_ratio || 0, 0.35);
          delete signal.luminance_grid;
          delete signal.gaze_frontal;
          delete signal.gaze_down_score;
        } else if (faces.length && signal.detector_source !== 'face_mesh') {
          delete signal.luminance_grid;
        }
        const seenNow = signal.face_count > 0 && signal.liveness_state !== 'missing' && !hiddenTab;
        noteStudentInFrame(seenNow);
        if (seenNow && !learningHold) {
          setLearningStatus(signal.detector_source === 'face_mesh'
            ? lessonChrome().mesh
            : lessonChrome().present);
        }
        const data = await api('/api/studio/learn/camera', {
          method: 'POST', headers: { 'content-type': 'application/json' },
          body: JSON.stringify({
            session_id: cameraSessionId(),
            participant_id: learnerId,
            timestamp_ms: Date.now(),
            signal: signal,
          }),
        });
        applyLearningHold(data);
        applyAttentionShift(data);
      } catch (_) {
        if (studentStillAway()) pauseLessonForAbsence(PRESENCE_PAUSE);
      } finally {
        studentCamBusy = false;
      }
    }

    function cameraSessionId() {
      return (teachSession || 'studio') + ':' + (learnerId || 'learner');
    }

    function holdGroup(reason) {
      if (/phone|eyes_away|owner|multiple|attention|cheat/.test(reason || '')) return 'integrity';
      if (/dark|quality|far/.test(reason || '')) return 'camera';
      return 'away';
    }

    let PRESENCE_PAUSE = "We detected that you left the camera. The lesson is paused and will resume when you return.";
    let PRESENCE_RESUME = "You're back on the camera. We'll continue from the same place.";
    const LESSON_CHROME = {
      en: {
        course: "Course", language: "Language", look: "Look", motion: "Motion", faces: "Faces",
        bars: "Bars", line: "Frequency line", mouth: "Talking mouth", ripple: "Soft ripples", lantern: "Lantern",
        library: "Course library", choose: "Choose a course to begin.",
        hideCourses: "Hide courses", showCourses: "Courses",
        yourLesson: "Your lesson", clickStart: "Tap the lesson to start.",
        clickContinue: "Tap the lesson to continue.",
        start: "Start", pause: "Pause", resume: "Resume", ask: "Ask", hide: "Hide",
        hideOptions: "Hide options", showOptions: "Show options", showCaptions: "Show captions",
        startOver: "Start over", showAvatar: "Show Avatar", hideAvatar: "Hide Avatar",
        askTitle: "Ask about this course",
        askBody: "Ask a question or leave a comment. Theodore answers only about this training.",
        askPlaceholder: "Ask about a rule, a sign, or this page. You can type or speak.",
        speak: "Speak", send: "Send", close: "Close",
        nextGap: "Next gap", outline: "Outline", freeTrial: "free trial",
        absorb: "Take a moment with this page. The next one waits so you can study it.",
        cameraNote: "Camera stays on. The lesson pauses if you leave the camera.",
        watching: "Looking for you.",
        present: "You're here.",
        mesh: "Watching.",
        pauseLine: "We detected that you left the camera. The lesson is paused and will resume when you return.",
        resumeLine: "You're back on the camera. We'll continue from the same place."
      },
      zh: {
        course: "课程", language: "语言", look: "样子", motion: "动态", faces: "面孔",
        bars: "音柱", line: "频率线", mouth: "说话的嘴", ripple: "柔和波纹", lantern: "灯笼",
        library: "课程库", choose: "选一门课开始。",
        hideCourses: "隐藏课程", showCourses: "课程",
        yourLesson: "你的课", clickStart: "点击课程开始。",
        clickContinue: "点击课程继续。",
        start: "开始", pause: "暂停", resume: "继续", ask: "提问", hide: "隐藏",
        hideOptions: "隐藏选项", showOptions: "显示选项", showCaptions: "显示字幕",
        startOver: "重新开始", showAvatar: "显示头像", hideAvatar: "隐藏头像",
        askTitle: "问问这门课",
        askBody: "提问或留言。Theodore 只回答这门课的内容。",
        askPlaceholder: "问问规则、标志或这一页。可以打字，也可以说。",
        speak: "说话", send: "发送", close: "关闭",
        nextGap: "下一处缺口", outline: "大纲", freeTrial: "免费试听",
        absorb: "先看一会儿这一页。下一页会等你，方便你学习。",
        cameraNote: "摄像头保持开启。离开画面时课程会暂停。",
        watching: "正在观察是否有人。",
        present: "人在，正在学习。",
        mesh: "人在。面部网格正在观察。",
        pauseLine: "我们检测到你离开了摄像头。课程已暂停，你回来后会继续。",
        resumeLine: "你回到摄像头前了。我们从同一个地方继续。"
      },
      yue: {
        course: "課程", language: "語言", look: "樣", motion: "動態", faces: "面孔",
        bars: "音柱", line: "頻率線", mouth: "講緊嘢嘅嘴", ripple: "柔和波紋", lantern: "燈籠",
        library: "課程庫", choose: "揀一堂課開始。",
        hideCourses: "隱藏課程", showCourses: "課程",
        yourLesson: "你嘅課", clickStart: "撳課程開始。",
        clickContinue: "撳課程繼續。",
        start: "開始", pause: "暫停", resume: "繼續", ask: "提問", hide: "隱藏",
        hideOptions: "隱藏選項", showOptions: "顯示選項", showCaptions: "顯示字幕",
        startOver: "重新開始", showAvatar: "顯示頭像", hideAvatar: "隱藏頭像",
        askTitle: "問下呢堂課",
        askBody: "提問或者留言。Theodore 只答呢堂課嘅內容。",
        askPlaceholder: "問下規則、標誌或者呢一頁。可以打字，亦可以講。",
        speak: "講嘢", send: "發送", close: "關閉",
        nextGap: "下一個缺口", outline: "大綱", freeTrial: "免費試聽",
        absorb: "先睇一陣呢一頁。下一頁會等你，方便你學。",
        cameraNote: "鏡頭保持開住。離開畫面嗰陣課程會暫停。",
        watching: "睇緊有冇人。",
        present: "人喺度，學緊。",
        mesh: "人喺度。面部網格睇緊。",
        pauseLine: "我哋偵測到你離開咗鏡頭。課程已暫停，你返嚟之後會繼續。",
        resumeLine: "你返到鏡頭前面。我哋由同一個地方繼續。"
      },
      km: {
        course: "វគ្គសិក្សា", language: "ភាសា", look: "រូបរាង", motion: "ចលនា", faces: "មុខ",
        bars: "របារ", line: "បន្ទាត់ប្រេកង់", mouth: "មាត់និយាយ", ripple: "រលកទន់", lantern: "គោម",
        library: "បណ្ណាល័យវគ្គ", choose: "ជ្រើសវគ្គមួយដើម្បីចាប់ផ្តើម។",
        hideCourses: "លាក់វគ្គ", showCourses: "វគ្គ",
        yourLesson: "មេរៀនរបស់អ្នក", clickStart: "ចុចមេរៀនដើម្បីចាប់ផ្តើម។",
        clickContinue: "ចុចមេរៀនដើម្បីបន្ត។",
        start: "ចាប់ផ្តើម", pause: "ផ្អាក", resume: "បន្ត", ask: "សួរ", hide: "លាក់",
        hideOptions: "លាក់ជម្រើស", showOptions: "បង្ហាញជម្រើស", showCaptions: "បង្ហាញអក្សររត់",
        startOver: "ចាប់ផ្តើមឡើងវិញ", showAvatar: "បង្ហាញរូបតំណាង", hideAvatar: "លាក់រូបតំណាង",
        askTitle: "សួរអំពីវគ្គនេះ",
        askBody: "សួរសំណួរ ឬទុកមតិ។ Theodore ឆ្លើយតែអំពីការបណ្តុះបណ្តាលនេះ។",
        askPlaceholder: "សួរអំពីច្បាប់ សញ្ញា ឬទំព័រនេះ។ អ្នកអាចវាយ ឬនិយាយ។",
        speak: "និយាយ", send: "ផ្ញើ", close: "បិទ",
        nextGap: "ចន្លោះបន្ទាប់", outline: "គ្រោង", freeTrial: "សាកល្បងឥតគិតថ្លៃ",
        absorb: "ចំណាយពេលជាមួយទំព័រនេះ។ ទំព័របន្ទាប់រង់ចាំដើម្បីឱ្យអ្នកសិក្សា។",
        cameraNote: "កាមេរ៉ានៅបើក។ មេរៀនផ្អាកប្រសិនបើអ្នកចេញពីកាមេរ៉ា។",
        watching: "កំពុងមើលវត្តមាន។",
        present: "មានវត្តមាន និងកំពុងរៀន។",
        mesh: "មានវត្តមាន។ សំណាញ់មុខកំពុងមើល។",
        pauseLine: "យើងបានរកឃើញថាអ្នកបានចេញពីកាមេរ៉ា។ មេរៀនបានផ្អាក ហើយនឹងបន្តពេលអ្នកត្រឡប់មកវិញ។",
        resumeLine: "អ្នកបានត្រឡប់មកកាមេរ៉ាវិញ។ យើងនឹងបន្តពីកន្លែងដដែល។"
      }
    };
    function lessonChrome(code) {
      const key = studioSpokenCode(code || teachLanguage || "en");
      return LESSON_CHROME[key] || LESSON_CHROME.en;
    }
    function paintLessonChrome(code) {
      const pack = lessonChrome(code);
      document.querySelectorAll("[data-i18n]").forEach((el) => {
        const key = el.getAttribute("data-i18n");
        if (!key || pack[key] == null) return;
        if (el.id === "btn-pause") {
          el.textContent = el.classList.contains("is-paused") ? pack.resume : pack.pause;
          return;
        }
        if (el.id === "btn-avatar") {
          el.textContent = document.body.classList.contains("avatar-on") ? pack.hideAvatar : pack.showAvatar;
          return;
        }
        if (el.id === "btn-chrome") {
          const hidden = document.body.classList.contains("chrome-hidden");
          el.textContent = hidden ? pack.showOptions : pack.hideOptions;
          el.title = el.textContent;
          return;
        }
        el.textContent = pack[key];
      });
      document.querySelectorAll("[data-i18n-label]").forEach((el) => {
        const key = el.getAttribute("data-i18n-label");
        if (key && pack[key] != null) el.setAttribute("label", pack[key]);
      });
      document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
        const key = el.getAttribute("data-i18n-placeholder");
        if (key && pack[key] != null) el.setAttribute("placeholder", pack[key]);
      });
      PRESENCE_PAUSE = pack.pauseLine;
      PRESENCE_RESUME = pack.resumeLine;
      const status = $("student-cam-status");
      if (!status) return;
      const known = [];
      Object.keys(LESSON_CHROME).forEach((name) => {
        const row = LESSON_CHROME[name];
        known.push(row.watching, row.present, row.mesh, row.pauseLine);
      });
      if (known.indexOf(status.textContent) >= 0) {
        if (learningHold) status.textContent = pack.pauseLine;
        else if (studentWasPresent) status.textContent = pack.present;
        else status.textContent = pack.watching;
      }
    }
    let studentWasPresent = false;
    let lastStudentSeenAt = 0;
    let studentBackSince = 0;
    let studentGoneSince = 0;
    let returnGraceUntil = 0;
    // A camera coming back from the background needs a moment to deliver frames.
    const RETURN_GRACE_MS = 3500;
    const ABSENCE_HOLD_MS = 600;
    // Face/contour mesh flickers; require a short solid return before auto-resume.
    const PRESENCE_RESUME_MS = 900;
    const PRESENCE_MISS_GRACE_MS = 350;
    const PRESENCE_PHONE = "Looks like you might be looking down at a phone. The lesson is still here when you look up.";
    const PRESENCE_AWAY = "Look back at the screen when you can. I'll keep going from here.";
    let glanceNoted = '';

    function glanceKind(reason, data) {
      if (data && data.absent) return '';
      const text = String(reason || '');
      if (/phone|gaze_down|looking_at_phone|pitch/.test(text)) return 'phone';
      if (/eyes_away|looking_away|yaw/.test(text)) return 'away';
      return '';
    }

    function rememberStudioPresence(kind) {
      try {
        const key = 'studio-presence-log';
        const rows = JSON.parse(localStorage.getItem(key) || '[]');
        const next = Array.isArray(rows) ? rows : [];
        next.push({ kind: kind, at: Date.now(), session: teachSession || '' });
        localStorage.setItem(key, JSON.stringify(next.slice(-30)));
      } catch (err) { /* a local note is enough when no profile store is wired */ }
    }

    function cameraIsLive() {
      if (studentCamStream) return true;
      const video = $('student-cam-video');
      const tracks = video && video.srcObject && video.srcObject.getVideoTracks
        ? video.srcObject.getVideoTracks() : [];
      return tracks.some((track) => track.readyState === 'live');
    }

    function learnerLocallyBack() {
      return !!(studentBackSince && (Date.now() - studentBackSince) >= PRESENCE_RESUME_MS);
    }

    function noteStudentInFrame(seen) {
      if (seen) {
        studentWasPresent = true;
        studentGoneSince = 0;
        if (!learningHold) {
          lastStudentSeenAt = Date.now();
          studentBackSince = 0;
          return;
        }
        // On an away-hold, mesh/contours mean the learner returned — debounce,
        // then resume here. Do not wait on the server hold flag; applyLearningHold
        // used to early-return into pause while lastStudentSeenAt was still stale.
        if (!studentBackSince) studentBackSince = Date.now();
        if (learnerLocallyBack()) {
          lastStudentSeenAt = Date.now();
          if (holdGroup(learningHoldReason) === 'away') {
            resumeLessonAfterPresence();
          }
        }
        return;
      }
      if (!studentGoneSince) studentGoneSince = Date.now();
      // Ignore brief mesh dropouts so a one-frame miss does not reset the return timer.
      if (Date.now() - studentGoneSince < PRESENCE_MISS_GRACE_MS) return;
      studentBackSince = 0;
      if (studentStillAway()) pauseLessonForAbsence(PRESENCE_PAUSE);
    }

    function watchStudentPresence() {
      if (document.visibilityState === 'hidden') {
        studentBackSince = 0;
        studentGoneSince = Date.now();
        if (studentStillAway()) pauseLessonForAbsence(PRESENCE_PAUSE);
        return;
      }
      const cache = lessonTrackCache;
      if (!cache || Date.now() - cache.at > 400) return;
      const seen = !!(
        (cache.facial && cache.facial.face_count > 0)
        || cache.seenPose || cache.seenHands || cache.seenBox
      );
      noteStudentInFrame(seen);
    }

    function studentStillAway() {
      if (!studentWasPresent || !lastStudentSeenAt) return false;
      if (learnerLocallyBack()) return false;
      if (document.visibilityState !== 'hidden' && Date.now() < returnGraceUntil) return false;
      if (!cameraIsLive() && document.visibilityState !== 'hidden') return false;
      return Date.now() - lastStudentSeenAt >= ABSENCE_HOLD_MS;
    }

    function showPresenceBanner(line) {
      const banner = $('presence-hold');
      if (!banner) return;
      banner.hidden = false;
      banner.textContent = line;
    }

    function hidePresenceBanner() {
      const banner = $('presence-hold');
      if (!banner) return;
      banner.hidden = true;
    }

    function pauseLessonForAbsence(line) {
      const message = line || PRESENCE_PAUSE;
      showPresenceBanner(message);
      setLearningStatus(message);
      const already = learningHold && holdGroup(learningHoldReason) === 'away';
      learningHold = true;
      learningHoldReason = 'no_learner_detected';
      window.TheodoreLiveAudio?.pauseRecognition?.();
      clearAutoAdvance();
      theodoreAvatar?.setState('listening');
      document.body.classList.add('presence-held');
      if (already) return;
      stopSpeech();
      rememberStudioPresence('left_frame');
      sayPresenceLine(message);
    }

    function resumeLessonAfterPresence() {
      if (!learningHold) {
        hidePresenceBanner();
        document.body.classList.remove('presence-held');
        return;
      }
      learningHold = false;
      learningHoldReason = '';
      studentBackSince = 0;
      studentGoneSince = 0;
      lastStudentSeenAt = Date.now();
      document.body.classList.remove('presence-held');
      hidePresenceBanner();
      setLearningStatus(PRESENCE_RESUME);
      rememberStudioPresence('returned');
      if (!lecturePaused && !learningCheckOpen) sayPresenceLine(PRESENCE_RESUME, continueSameLesson);
      else if (!lecturePaused) continueSameLesson();
    }

    function continueSameLesson() {
      if (learningHold || lessonLife.isAway()) return;
      if (window.TheodoreLiveAudio && window.__THEODORE_LIVE_AUDIO_ACTIVE__) {
        window.TheodoreLiveAudio.resumeRecognition?.();
        // The agent's last turn was cancelled on pause; re-anchor it to this slide.
        if (lastTeachPayload) syncVoiceToSlide(lastTeachPayload, { force: true });
        return;
      }
      const turn = (lastTeachPayload && (lastTeachPayload.turn || lastTeachPayload)) || {};
      speakText(turn.narration || turn.display_body || '', lastTeachPayload && lastTeachPayload.tts);
    }

    function sayPresenceLine(line, after) {
      window.TheodoreLiveAudio?.pauseRecognition?.();
      stopSpeech();
      const gen = speechGen;
      let finished = false;
      const done = () => {
        if (finished) return;
        finished = true;
        if (after && gen === speechGen) after();
      };
      setTimeout(() => {
        if (!window.speechSynthesis) {
          done();
          return;
        }
        try {
          const utter = new SpeechSynthesisUtterance(line);
          utter.onend = done;
          utter.onerror = done;
          window.speechSynthesis.speak(utter);
          window.setTimeout(done, Math.min(8000, 1400 + String(line || '').length * 40));
        } catch (_) {
          done();
        }
      }, 60);
    }

    function showGlance(kind) {
      const aside = $('attention-aside');
      const line = kind === 'phone' ? PRESENCE_PHONE : PRESENCE_AWAY;
      if (aside) {
        aside.hidden = false;
        aside.dataset.glance = '1';
        aside.textContent = line;
      }
      setLearningStatus(line);
      if (glanceNoted !== kind) {
        glanceNoted = kind;
        rememberStudioPresence(kind);
      }
    }

    function clearGlance() {
      const aside = $('attention-aside');
      if (aside && aside.dataset.glance) {
        aside.hidden = true;
        aside.textContent = '';
        delete aside.dataset.glance;
      }
      glanceNoted = '';
    }

    function absenceHold(data) {
      if (!data) return false;
      if (data.absent) return true;
      return /no_learner|absence_grace|temporarily_missing/.test(String(data.reason || ''));
    }

    function applyLearningHold(data) {
      const status = $('student-cam-status');
      // Local face/contour return wins over a lagging server "still absent" hold.
      if (learnerLocallyBack() && learningHold && holdGroup(learningHoldReason) === 'away') {
        resumeLessonAfterPresence();
      }
      if (studentStillAway()) {
        pauseLessonForAbsence(PRESENCE_PAUSE);
        return;
      }
      if (data && data.hold && absenceHold(data) && !studentWasPresent) {
        setLearningStatus(lessonChrome().watching);
        return;
      }
      // Server may still report absent for a tick after the face is back; treat
      // local return + absence hold as "back" so we do not re-pause.
      const backFromAbsence = (
        (data && data.hold && absenceHold(data) && studentWasPresent)
        || learnerLocallyBack()
      );
      if (!data || !data.hold || backFromAbsence) {
        clearGlance();
        if (learningHold && holdGroup(learningHoldReason) === 'away') {
          resumeLessonAfterPresence();
        } else if (learningHold) {
          learningHold = false;
          learningHoldReason = '';
          hidePresenceBanner();
          document.body.classList.remove('presence-held');
          setLearningStatus('Present. Continuing the same lesson.');
          rememberStudioPresence('returned');
          if (!lecturePaused && !learningCheckOpen) sayPresenceLine(PRESENCE_RESUME, continueSameLesson);
        } else if (status && !status.textContent) {
          setLearningStatus(lessonChrome().watching);
        } else if (data && data.state === 'present') {
          setLearningStatus(meshReady ? lessonChrome().mesh : lessonChrome().present);
        }
        return;
      }
      const reason = data.reason || 'paused';
      const glance = glanceKind(reason, data);
      if (glance) {
        showGlance(glance);
        return;
      }
      clearGlance();
      hidePresenceBanner();
      setLearningStatus(PRESENCE_PAUSE);
      if (learningHold && holdGroup(learningHoldReason) === holdGroup(reason)) return;
      learningHold = true;
      learningHoldReason = reason;
      clearAutoAdvance();
      theodoreAvatar?.setState('listening');
      document.body.classList.add('presence-held');
      rememberStudioPresence('left_frame');
      sayPresenceLine(data.speech || PRESENCE_PAUSE);
    }

    function firstLessonSentence(text) {
      const flat = String(text || '').replace(/\\s+/g, ' ').trim();
      const match = flat.match(/^.{12,}?[.។!?]/);
      return (match && match[0]) || flat;
    }

    function applyAttentionShift(data) {
      const stage = $('teach-stage');
      const aside = $('attention-aside');
      const body = $('teach-body');
      if (!data || data.hold || learningHold || learningCheckOpen || lecturePaused || talkOpen) return;
      const delivery = data.delivery;
      if (!delivery) {
        if (stage) stage.classList.remove('is-awake', 'is-refocus');
        const host = $('teach-visual-timeline');
        if (host) delete host.dataset.energy;
        if (aside && !attentionResume) {
          aside.hidden = true;
          aside.textContent = '';
        }
        if (body && attentionFullBody) body.textContent = attentionFullBody;
        attentionFullBody = '';
        return;
      }
      if (stage) {
        stage.classList.remove('is-awake', 'is-refocus');
        stage.classList.add(delivery.mode === 'wake' ? 'is-awake' : 'is-refocus');
      }
      const host = $('teach-visual-timeline');
      if (host) {
        host.dataset.energy = delivery.style || 'brisk';
        host.querySelectorAll('.visual-layer').forEach((layer) => {
          layer.dataset.transition = delivery.mode === 'wake' ? 'zoom' : 'slide-left';
        });
      }
      const turn = (lastTeachPayload && (lastTeachPayload.turn || lastTeachPayload)) || {};
      const idea = currentSectionWords() || firstLessonSentence(turn.narration || turn.display_body || turn.title || '');
      if (idea && body) {
        if (!attentionFullBody) attentionFullBody = body.textContent || idea;
        body.textContent = idea;
      }
      const adapt = data.adapt;
      if (!adapt || !adapt.speech) return;
      const now = Date.now();
      if (now < attentionShiftUntil) return;
      attentionShiftUntil = now + 42000;
      if (aside) {
        aside.hidden = false;
        aside.textContent = adapt.speech;
      }
      setLearningStatus(delivery.mode === 'wake'
        ? 'Keeping this to one idea.'
        : 'Changing the picture so this stays clear.');
      const english = String(teachLanguage || 'en').toLowerCase().slice(0, 2) === 'en';
      if (english) {
        attentionResume = idea;
        speakText(adapt.speech, null, true, 'adapt');
        return;
      }
      if (idea) speakText(idea, null, false, 'adapt-resume');
    }

    async function ensureStudentCamera() {
      if (studentCamStream) {
        const box = $('student-cam');
        if (box) box.hidden = false;
        if (!restoreStudentCamPosition()) defaultStudentCamPosition();
        if (!studentCamTimer) studentCamTimer = window.setInterval(() => { void studentCameraSample(); }, 1000);
        if (!studentAwayTimer) studentAwayTimer = window.setInterval(watchStudentPresence, 200);
        startStudentTracking();
        return;
      }
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) return;
      try {
        studentCamStream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: 'user', width: { ideal: 640 }, height: { ideal: 360 } },
          audio: false,
        });
        watchCameraStream(studentCamStream);
        const video = $('student-cam-video');
        if (video) {
          video.srcObject = studentCamStream;
          await video.play().catch(() => {});
        }
        const box = $('student-cam');
        if (box) box.hidden = false;
        if (!restoreStudentCamPosition()) defaultStudentCamPosition();
        if (!studentCamTimer) studentCamTimer = window.setInterval(() => { void studentCameraSample(); }, 1000);
        if (!studentAwayTimer) studentAwayTimer = window.setInterval(watchStudentPresence, 200);
        startStudentTracking();
      } catch (error) {
        setLearningStatus('Camera is required. Allow it to continue.');
        if (!studentCamTimer) studentCamTimer = window.setInterval(() => { void studentCameraSample(); }, 1000);
        if (!studentAwayTimer) studentAwayTimer = window.setInterval(watchStudentPresence, 200);
      }
    }

    function setStudentCamHidden(hidden) {
      const box = $('student-cam');
      if (!box) return;
      box.classList.toggle('is-hidden', hidden);
      const video = $('student-cam-video');
      // Hide the preview only. Never stop the camera tracks.
      if (video) {
        video.setAttribute('aria-hidden', hidden ? 'true' : 'false');
        if (video.srcObject && video.paused) video.play().catch(() => {});
      }
      const button = $('student-cam-hide');
      if (!button) return;
      button.textContent = hidden ? 'Show camera' : 'Hide';
      button.setAttribute('aria-pressed', String(hidden));
      button.title = hidden
        ? 'Show your camera preview. The camera stays on either way.'
        : 'Hide the preview. The camera stays on.';
      const left = parseFloat(box.style.left);
      const top = parseFloat(box.style.top);
      if (Number.isFinite(left) && Number.isFinite(top)) clampStudentCam(left, top);
    }

    function lessonIsPlaying() {
      return lessonTurnLoaded() && !lecturePaused && !sampleIsComplete();
    }

    function withTimeout(promise, ms, fallback) {
      let timer = 0;
      return Promise.race([
        Promise.resolve(promise),
        new Promise((resolve) => { timer = setTimeout(() => resolve(fallback), ms); }),
      ]).finally(() => clearTimeout(timer));
    }

    function apiTimed(path, opts, ms) {
      if (typeof AbortController !== 'function') return api(path, opts);
      const ctl = new AbortController();
      const timer = setTimeout(() => ctl.abort(), ms);
      return api(path, Object.assign({}, opts || {}, { signal: ctl.signal }))
        .finally(() => clearTimeout(timer));
    }

    function lessonSlideKey(payload) {
      if (!payload) return '';
      const turn = payload.turn || payload;
      return String(payload.path_pos ?? '') + '|' + String(payload.slide_index ?? turn.slide_index ?? '');
    }

    function liveAgentReady() {
      const live = window.TheodoreLiveAudio;
      const status = live && typeof live.status === 'function' ? live.status() : null;
      if (status) return !!(status.connected && status.socketOpen);
      return !!window.__THEODORE_LIVE_AUDIO_ACTIVE__;
    }

    function noteLessonAway() {
      clearAutoAdvance();
      stopSpeech();
      window.TheodoreLiveAudio?.pauseRecognition?.();
      hideResumeRetry();
    }

    function clearAwayHoldForReturn() {
      if (!learningHold || holdGroup(learningHoldReason) !== 'away') return false;
      learningHold = false;
      learningHoldReason = '';
      document.body.classList.remove('presence-held');
      hidePresenceBanner();
      setLearningStatus(PRESENCE_RESUME);
      rememberStudioPresence('returned');
      return true;
    }

    function refreshLessonMedia() {
      const video = $('student-cam-video');
      if (video && video.srcObject && video.paused) video.play().catch(() => {});
      try {
        const pending = window.TheodoreLiveAudio?.resumeAudio?.();
        if (pending && pending.catch) pending.catch(() => {});
      } catch (_) {}
    }

    async function restoreLessonMedia() {
      resumeStartedAt = Date.now();
      returnGraceUntil = resumeStartedAt + RETURN_GRACE_MS;
      studentBackSince = 0;
      studentGoneSince = 0;
      if (studentWasPresent) lastStudentSeenAt = resumeStartedAt;
      clearAwayHoldForReturn();
      if (lastTeachPayload) {
        const tracks = studentCamStream && studentCamStream.getVideoTracks ? studentCamStream.getVideoTracks() : [];
        if (studentCamStream && !tracks.some((track) => track.readyState === 'live')) {
          try { studentCamStream.getTracks().forEach((track) => track.stop()); } catch (_) {}
          studentCamStream = null;
          const stale = $('student-cam-video');
          if (stale) stale.srcObject = null;
        }
        await withTimeout(ensureStudentCamera().catch(() => null), 3000, null);
        const video = $('student-cam-video');
        if (video && video.srcObject && video.paused) {
          await withTimeout(video.play().catch(() => null), 1500, null);
        }
      }
      const live = window.TheodoreLiveAudio;
      if (live && typeof live.resumeAudio === 'function') {
        await withTimeout(live.resumeAudio().catch(() => null), 1500, null);
      }
    }

    async function reconcileLessonForResume() {
      if (advancePromise) await withTimeout(advancePromise.catch(() => null), RESUME_FETCH_MS, null);
      if (!teachSession) return null;
      try {
        return await apiTimed('/api/studio/teach/current', {
          method: 'POST', headers: { 'content-type': 'application/json' },
          body: JSON.stringify({ session_id: teachSession }),
        }, RESUME_FETCH_MS);
      } catch (error) {
        if (!/missing/i.test(String((error && error.message) || ''))) throw error;
        await startTeach({ resume: true });
        return { rendered_by_start: true };
      }
    }

    function continueLessonAfterReturn(payload) {
      if (payload.rendered_by_start) return 'played';
      if (learningHold) return 'quiet';
      if (talkOpen || learningCheckOpen) {
        window.TheodoreLiveAudio?.resumeRecognition?.();
        if (learningCheckOpen && spokenActivityPrompt) armSpokenActivity(spokenActivity, spokenActivityPrompt);
        return 'quiet';
      }
      if (payload.sample && payload.sample.complete) {
        renderTeach(payload);
        return 'quiet';
      }
      if (lessonSlideKey(payload) !== lessonSlideKey(lastTeachPayload)) {
        renderTeach(payload);
        return 'played';
      }
      if (lastSpeakRequestAt >= resumeStartedAt) return 'played';
      if (beatHandled) {
        continueAfterActivity().catch((error) => toast(String(error.message || error)));
        return 'quiet';
      }
      const absorb = $('absorb-note');
      if (absorb && !absorb.hidden) {
        window.TheodoreLiveAudio?.resumeRecognition?.();
        scheduleAutoAdvance(ABSORB_MS);
        return 'quiet';
      }
      if (liveAgentReady()) {
        window.TheodoreLiveAudio?.resumeRecognition?.();
        syncVoiceToSlide(lastTeachPayload, { force: true });
        return 'played';
      }
      const turn = lastTeachPayload.turn || lastTeachPayload;
      speakText(turn.narration || turn.display_body || '', lastTeachPayload.tts);
      return 'played';
    }

    function verifyLessonPlayback(token, startedAt) {
      return new Promise((resolve) => {
        const until = Date.now() + RESUME_VERIFY_MS;
        const tick = () => {
          if (token !== lessonLife.token()) return resolve(true);
          if (lecturePaused || learningHold || sampleIsComplete() || talkOpen || learningCheckOpen) return resolve(true);
          if (lastPlaybackAt >= startedAt) return resolve(true);
          if (liveAgentReady() && !window.__THEODORE_LIVE_AUDIO_HOLD__) return resolve(true);
          if (Date.now() >= until) return resolve(false);
          setTimeout(tick, 250);
        };
        tick();
      });
    }

    function showResumeRetry() {
      stopSpeech();
      clearAutoAdvance();
      const btn = $('resume-retry');
      if (btn) btn.hidden = false;
      setLearningStatus('The lesson could not continue on its own. Tap to continue.');
    }

    function hideResumeRetry() {
      const btn = $('resume-retry');
      if (btn) btn.hidden = true;
    }

    function lifecycleReturn(source, opts) {
      lifecycleTickAt = Date.now();
      return lessonLife.back(source, opts);
    }

    function watchCameraStream(stream) {
      if (!stream || stream.__lessonWatched || !stream.getVideoTracks) return;
      stream.__lessonWatched = true;
      stream.getVideoTracks().forEach((track) => {
        let muteTimer = 0;
        track.addEventListener('mute', () => {
          clearTimeout(muteTimer);
          muteTimer = setTimeout(() => {
            if (track.muted && track.readyState === 'live') lessonLife.away('camera-muted');
          }, CAMERA_MUTE_AWAY_MS);
        });
        track.addEventListener('unmute', () => {
          clearTimeout(muteTimer);
          void lifecycleReturn('camera-unmuted');
        });
        track.addEventListener('ended', () => {
          clearTimeout(muteTimer);
          if (studentCamStream !== stream) return;
          studentCamStream = null;
          const video = $('student-cam-video');
          if (video && video.srcObject === stream) video.srcObject = null;
          if (document.visibilityState === 'hidden') {
            lessonLife.away('camera-ended');
            return;
          }
          if (lastTeachPayload) ensureStudentCamera().catch(() => {});
        });
      });
    }

    function stopStudentCamera() {
      stopStudentTracking();
      if (studentCamTimer) {
        window.clearInterval(studentCamTimer);
        studentCamTimer = 0;
      }
      if (studentAwayTimer) {
        window.clearInterval(studentAwayTimer);
        studentAwayTimer = 0;
      }
      if (studentCamStream) {
        studentCamStream.getTracks().forEach((track) => track.stop());
        studentCamStream = null;
      }
      const video = $('student-cam-video');
      if (video) video.srcObject = null;
      const box = $('student-cam');
      if (!box) return;
      box.hidden = true;
      box.classList.remove('is-hidden');
    }

    function pinStudioCamera() {
      const box = $('student-cam');
      if (!box || !audioOnly) return;
      box.style.left = '';
      box.style.top = '';
      box.style.right = '';
      box.style.bottom = '';
    }

    function placeStudentCam() {
      const cam = $('student-cam');
      const overlay = $('presenter-overlay');
      if (!cam || !overlay) return;
      if (cam.closest('#course-widget')) return;
      if (presenterActive()) {
        if (cam.parentElement !== overlay) overlay.appendChild(cam);
        if (!restoreStudentCamPosition()) defaultStudentCamPosition();
        return;
      }
      if (audioOnly) {
        if (cam.parentElement !== document.body) document.body.appendChild(cam);
        pinStudioCamera();
        return;
      }
      if (cam.parentElement !== document.body) document.body.appendChild(cam);
      if (!restoreStudentCamPosition()) defaultStudentCamPosition();
    }

    function clampStudentCam(left, top) {
      const box = $('student-cam');
      if (!box) return null;
      const safe = readSafeInsets();
      const pad = 8;
      const width = box.offsetWidth || 148;
      const height = Math.max(box.offsetHeight || 112, 64);
      const minX = pad + safe.left;
      const minY = pad + safe.top;
      const maxX = Math.max(minX, window.innerWidth - width - pad - safe.right);
      const maxY = Math.max(minY, window.innerHeight - height - pad - safe.bottom);
      const x = Math.max(minX, Math.min(maxX, left));
      const y = Math.max(minY, Math.min(maxY, top));
      box.style.left = x + 'px';
      box.style.top = y + 'px';
      box.style.right = 'auto';
      box.style.bottom = 'auto';
      return { left: x, top: y };
    }

    function defaultStudentCamPosition() {
      const box = $('student-cam');
      if (!box) return null;
      const safe = readSafeInsets();
      const width = box.offsetWidth || 148;
      const left = Math.max(safe.left + 8, 12);
      const top = safe.top + 12;
      return clampStudentCam(Math.min(left, window.innerWidth - width - 8), top);
    }

    function restoreStudentCamPosition() {
      const box = $('student-cam');
      if (!box || box.hidden || audioOnly) return false;
      try {
        const saved = JSON.parse(localStorage.getItem('studio.cam.pos') || 'null');
        if (!saved || typeof saved.left !== 'number' || typeof saved.top !== 'number') return false;
        clampStudentCam(saved.left, saved.top);
        return true;
      } catch (_) {
        return false;
      }
    }

    function enableStudentCamDrag() {
      const box = $('student-cam');
      if (!box || box.dataset.dragReady) return;
      box.dataset.dragReady = '1';
      let drag = null;
      box.addEventListener('pointerdown', (event) => {
        if (document.body.classList.contains('audio-only')) return;
        if (event.button !== 0) return;
        if (event.target.closest('button, a, input, textarea, select')) return;
        if (box.closest('#course-widget')) return;
        const rect = box.getBoundingClientRect();
        drag = {
          id: event.pointerId,
          dx: event.clientX - rect.left,
          dy: event.clientY - rect.top,
        };
        box.classList.add('is-dragging');
        try { box.setPointerCapture(event.pointerId); } catch (_) {}
        event.preventDefault();
      });
      box.addEventListener('pointermove', (event) => {
        if (!drag || event.pointerId !== drag.id) return;
        const pos = clampStudentCam(event.clientX - drag.dx, event.clientY - drag.dy);
        if (!pos) return;
        try { localStorage.setItem('studio.cam.pos', JSON.stringify(pos)); } catch (_) {}
      });
      const endDrag = (event) => {
        if (!drag || event.pointerId !== drag.id) return;
        drag = null;
        box.classList.remove('is-dragging');
      };
      box.addEventListener('pointerup', endDrag);
      box.addEventListener('pointercancel', endDrag);
      window.addEventListener('resize', () => {
        const left = parseFloat(box.style.left);
        const top = parseFloat(box.style.top);
        if (!Number.isFinite(left) || !Number.isFinite(top)) return;
        const pos = clampStudentCam(left, top);
        if (!pos) return;
        try { localStorage.setItem('studio.cam.pos', JSON.stringify(pos)); } catch (_) {}
      });
    }

    function enterPresenterMode() {
      if (presenterActive()) return;
      $('presenter-body').appendChild($('teach-stage'));
      $('presenter-overlay').classList.add('show');
      placeStudentCam();
      void ensureStudentCamera();
      const reviewRoot = $('review-root');
      if (reviewRoot) $('presenter-overlay').appendChild(reviewRoot);
      document.body.classList.add('presenting');
      const overlay = $('presenter-overlay');
      if (overlay.requestFullscreen) overlay.requestFullscreen().catch(() => {});
      // A placed Theodore lives outside the stage, so he has to cross into the
      // fullscreen element himself or he simply would not be rendered.
      applyAvatarPlacement();
      updateLessonWindowControls();
      setStudioChromeHidden(document.body.classList.contains('chrome-hidden'));
      revealDriveChrome();
      // The renderer sizes off the container, which just changed by a lot.
      requestAnimationFrame(() => theodoreAvatar?.resize());
    }

    function exitPresenterMode() {
      if (!presenterActive()) return;
      $('teach-stage-home').appendChild($('teach-stage'));
      $('presenter-overlay').classList.remove('show');
      const reviewRoot = $('review-root');
      if (reviewRoot) document.body.appendChild(reviewRoot);
      document.body.classList.remove('presenting');
      placeStudentCam();
      if (!lastTeachPayload) stopStudentCamera();
      if (document.fullscreenElement && document.exitFullscreen) {
        document.exitFullscreen().catch(() => {});
      }
      applyAvatarPlacement();
      updateLessonWindowControls();
      setStudioChromeHidden(false);
      if (!document.body.classList.contains('audio-only')) setDriveChromeHidden(false);
      requestAnimationFrame(() => theodoreAvatar?.resize());
    }

    function togglePresenterMode() {
      if (presenterActive()) exitPresenterMode();
      else enterPresenterMode();
    }

    function arrangePhoneLesson() {
      if (!document.body.classList.contains('phone-embed')) return;
      // Park the trial clock on the body so chrome-hide cannot tuck it away.
      parkSampleClock();
    }

    function setCaptionsEnabled(enabled) {
      if (document.body.classList.contains('audio-only')) enabled = false;
      captionsEnabled = !!enabled;
      $('teach-stage').classList.toggle('captions-off', !captionsEnabled);
      paintLessonCaption();
      updateLessonWindowControls();
    }

    function toast(msg) {
      const el = $('toast');
      el.textContent = msg;
      el.classList.add('show');
      setTimeout(() => el.classList.remove('show'), 3200);
    }
    function setPauseButton(paused) {
      const btn = $('btn-pause');
      if (!btn) return;
      btn.textContent = paused ? lessonChrome().resume : lessonChrome().pause;
      btn.classList.toggle('is-paused', !!paused);
    }

    function courseIcon(course) {
      if (course.id === 'drivers-ed') {
        return '<svg viewBox="0 0 48 48" aria-hidden="true"><circle cx="24" cy="24" r="15" fill="none" stroke="currentColor" stroke-width="3"/><circle cx="24" cy="24" r="3.5" fill="currentColor"/><path d="M24 9v7M24 32v7M9 24h7M32 24h7" stroke="currentColor" stroke-width="3" stroke-linecap="round"/></svg>';
      }
      if (course.id === 'food-safety') {
        return '<svg viewBox="0 0 48 48" aria-hidden="true"><ellipse cx="24" cy="31" rx="14" ry="5" fill="none" stroke="currentColor" stroke-width="3"/><path d="M12 31c2 8 22 8 24 0" fill="none" stroke="currentColor" stroke-width="3"/><path d="M18 16c0 6 12 6 12 0" fill="none" stroke="currentColor" stroke-width="3"/><path d="M20 16V9M24 16V7M28 16V9" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/></svg>';
      }
      return '<svg viewBox="0 0 48 48" aria-hidden="true"><path d="M8 12h13c2.2 1.6 4.4 1.6 6.4 0H40v24H27.4c-2 1.6-4.2 1.6-6.4 0H8V12z" fill="none" stroke="currentColor" stroke-width="3" stroke-linejoin="round"/><path d="M24 13.5v21" stroke="currentColor" stroke-width="2.4"/></svg>';
    }
    function esc(s) {
      return String(s ?? '').replace(/[&<>"']/g, (c) => ({
        '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
      })[c]);
    }
    function qualityPill(q) {
      const cls = ({good:'good', better:'good', bad:'bad', moderate:'moderate'}[q] || '');
      return `<span class="pill ${cls}">${esc(q)}</span>`;
    }

    async function api(path, opts) {
      const res = await fetch(path, opts);
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || res.statusText || 'request failed');
      const method = String((opts && opts.method) || 'GET').toUpperCase();
      if (method !== 'GET' && window.ReactNativeWebView && String(path).indexOf('/api/studio/') === 0) {
        try {
          window.ReactNativeWebView.postMessage(JSON.stringify({
            type: 'salareen-telemetry',
            event: { activity_id: 'course-studio', outcome: 'success' }
          }));
        } catch (err) {}
      }
      return data;
    }

    // Slow routes answer 202 with a job; poll it with a gentle backoff until it finishes.
    async function apiJob(path, opts, onProgress) {
      const started = await api(path, opts);
      if (!started.job_id) return started;
      let wait = 1000;
      for (;;) {
        const job = await api(started.status_url || ('/api/studio/jobs/' + started.job_id));
        if (job.state === 'done') return job.result;
        if (job.state === 'failed') throw new Error((job.error && job.error.message) || job.message || 'The job did not finish');
        if (onProgress) onProgress(job);
        await new Promise((resolve) => setTimeout(resolve, wait));
        wait = Math.min(5000, Math.round(wait * 1.4));
      }
    }

    async function refreshCorpus() {
      const data = await api('/api/studio/corpus');
      const box = $('corpus-list');
      box.innerHTML = (data.documents || []).map((d) => `
        <div class="item" data-id="${esc(d.source_id)}">
          <div><strong>${esc(d.title_guess || d.filename)}</strong> ${qualityPill(d.quality_label)}
            ${d.incorporate ? '<span class="pill good">incorporate</span>' : ''}</div>
          <div class="meta">${esc(d.category)} · ${esc(d.ext)} · ${esc(d.filename)}</div>
        </div>`).join('') || '<div class="item">No corpus yet — run training scan.</div>';
      box.querySelectorAll('.item[data-id]').forEach((el) => {
        el.onclick = () => selectSource(el.getAttribute('data-id'));
      });
      $('corpus-stats').textContent =
        `${data.count || 0} docs · incorporate ${data.incorporate_count || 0} · reject ${data.reject_count || 0}`;
    }

    async function selectSource(id) {
      selectedSource = id;
      $('corpus-list').querySelectorAll('.item').forEach((el) => {
        el.classList.toggle('active', el.getAttribute('data-id') === id);
      });
      const data = await api('/api/studio/sources/' + encodeURIComponent(id));
      $('source-title').textContent = data.document.title_guess || data.document.filename;
      $('source-meta').innerHTML = qualityPill(data.document.quality_label) +
        ` <span class="pill">${esc(data.document.category)}</span>`;
      pagesCache = data.pages || [];
      renderPages();
      renderComments(data.comments || []);
    }

    function renderPages() {
      const box = $('page-list');
      box.innerHTML = pagesCache.map((p) => `
        <div class="page ${p.marked_reject ? 'rejected' : ''}">
          <div style="flex:1">
            <div><strong>p${p.index + 1}</strong> ${esc(p.title)}</div>
            <div class="meta">${esc((p.text || '').slice(0, 160))}</div>
          </div>
          <button class="secondary" data-like="${p.index}">Keep</button>
          <button class="danger" data-reject="${p.index}">Reject ⌀</button>
        </div>`).join('') || '<div class="meta">No pages extracted (install pypdf / python-pptx).</div>';
      box.querySelectorAll('[data-like]').forEach((b) => b.onclick = () => markPage(+b.dataset.like, false));
      box.querySelectorAll('[data-reject]').forEach((b) => b.onclick = () => markPage(+b.dataset.reject, true));
    }

    async function markPage(pageIndex, reject) {
      if (!selectedSource) return;
      await api('/api/studio/pages/verdict', {
        method: 'POST', headers: {'content-type':'application/json'},
        body: JSON.stringify({ source_id: selectedSource, page_index: pageIndex, marked_reject: reject })
      });
      const p = pagesCache.find((x) => x.index === pageIndex);
      if (p) p.marked_reject = reject;
      renderPages();
      toast(reject ? 'Page marked reject (circle+line style)' : 'Page kept');
    }

    function renderComments(rows) {
      $('comment-list').innerHTML = rows.map((c) => `
        <div class="comment"><strong>${esc(c.author)}</strong>
          ${c.page_index != null ? ' · p'+(c.page_index+1) : ''}
          <div>${esc(c.body)}</div></div>`).join('') || '<div class="meta">No comments yet.</div>';
    }

    async function postComment() {
      if (!selectedSource) return toast('Select a source first');
      const body = $('comment-body').value.trim();
      if (!body) return;
      const pageRaw = $('comment-page').value.trim();
      const page_index = pageRaw === '' ? null : Math.max(0, parseInt(pageRaw, 10) - 1);
      await api('/api/studio/comments', {
        method:'POST', headers:{
          'content-type':'application/json',
          ...(localStorage.getItem('aoep_token')
            ? {'authorization':'Bearer ' + localStorage.getItem('aoep_token')}
            : {})
        },
        body: JSON.stringify({ source_id: selectedSource, body, page_index, author: 'reviewer' })
      });
      $('comment-body').value = '';
      const data = await api('/api/studio/sources/' + encodeURIComponent(selectedSource));
      renderComments(data.comments || []);
      toast('Comment saved for training');
    }

    async function runTraining() {
      $('train-status').textContent = 'Scanning corpus…';
      const data = await apiJob('/api/studio/training/run', {
        method:'POST', headers:{'content-type':'application/json'},
        body: JSON.stringify({ extract_text: true, seed_page_hints: true })
      }, (job) => { $('train-status').textContent = (job.message || 'Scanning corpus') + '…'; });
      $('train-status').textContent =
        `Run ${data.run_id}: scanned ${data.documents_scanned}, incorporate ${data.incorporate_ids.length}, reject ${data.reject_ids.length}, review queue ${data.review_queue_ids.length}`;
      await refreshCorpus();
      await refreshCourses();
      toast('Training run complete');
    }

    async function runOfflineTrainer() {
      $('train-status').textContent = 'Offline trainer running (no network)…';
      const data = await apiJob('/api/studio/training/offline', {
        method:'POST', headers:{'content-type':'application/json'},
        body: JSON.stringify({ epochs: 25, run_scan: true, fit_passes: 2 })
      }, (job) => { $('train-status').textContent = 'Offline trainer running… ' + Math.round((job.elapsed_seconds || 0)) + 's'; });
      $('train-status').textContent =
        `Offline ${data.run_id}: epochs ${data.epoch}, best ${Number(data.best_course_score || 0).toFixed(3)}, ${data.status}`;
      await refreshCourses();
      toast('Offline trainer finished — course builds now use the learned model');
    }

    async function buildCourse() {
      const category = $('build-category').value;
      const title = $('build-title').value.trim() || null;
      teachLanguage = $('teach-lang').value || 'en';
      const data = await apiJob('/api/studio/courses/build', {
        method:'POST', headers:{'content-type':'application/json'},
        body: JSON.stringify({
          category: category || null, title, max_slides: 12,
          only_incorporate: true, language: teachLanguage
        })
      }, (job) => { toast((job.message || 'Building your course') + '…'); });
      selectedCourse = data.course_id;
      await refreshCourses();
      toast('Course built: ' + data.course_id + ' · lang ' + (data.language || teachLanguage));
    }

    async function loadCertOptions() {
      const data = await api('/api/studio/certification/options');
      certOptions = data.courses || [];
      const track = $('cert-track');
      if (!track) return;
      track.innerHTML = (data.tracks || []).map((row) =>
        `<option value="${esc(row.code)}">${esc(row.name)} (${esc(row.jurisdiction)})</option>`
      ).join('');
      track.value = data.default_track || 'ca_dmv_permit';
      renderCertLessons();
    }

    async function loadLibrary() {
      const [cert, early] = await Promise.all([
        api('/api/studio/certification/options'),
        api('/api/studio/early-learning/options')
      ]);
      certOptions = cert.courses || [];
      earlyOptions = early.courses || [];
      const driver = certOptions.filter((row) => row.track === 'ca_dmv_permit');
      const food = certOptions.filter((row) => row.track === 'alameda_food_handler');
      library = [
        {
          id: 'drivers-ed',
          title: "Driver's ed",
          detail: 'California permit prep · ' + driver.length + ' lessons, including 140 traffic signs · Full course $19.99',
          kind: 'cert',
          lessons: driver,
          featured: true
        },
        {
          id: 'food-safety',
          title: 'Food safety',
          detail: 'California food handler prep · ' + food.length + ' modules in order · Full course $19.99',
          kind: 'cert',
          lessons: food,
          featured: true
        }
      ];
      earlyOptions.forEach((row) => {
        library.push({
          id: 'early-' + row.level + '-' + row.topic_id,
          title: row.title,
          detail: (row.level_name || row.level) + ' · ' + (row.subject || 'Early learning'),
          kind: 'early',
          lessons: [row],
          featured: false
        });
      });
      renderLibrary();
      if (pinnedCourse) {
        document.body.classList.add('public-course');
        const pinned = library.find((row) => row.id === pinnedCourse);
        if (!pinned) toast('That course is not on this page.');
        else await openLibraryCourse(pinnedCourse);
      }
    }

    function renderLibrary() {
      const box = $('library-list');
      if (!box) return;
      box.innerHTML = library.map((course) => `
        <div class="item${course.featured ? ' featured' : ''}${activeCourse && activeCourse.id === course.id ? ' active' : ''}" data-lib="${esc(course.id)}">
          <div class="mark">${courseIcon(course)}</div>
          <div>
            <div><strong>${esc(course.title)}</strong>${course.featured ? '<span class="focus">Start here</span>' : ''}</div>
            <div class="meta">${esc(course.detail)}</div>
          </div>
        </div>`).join('');
      box.querySelectorAll('.item[data-lib]').forEach((el) => {
        el.onclick = () => openLibraryCourse(el.getAttribute('data-lib'));
      });
      const picker = $('drive-course');
      if (picker) {
        const current = activeCourse && activeCourse.id;
        picker.innerHTML = library.map((course) =>
          `<option value="${esc(course.id)}">${esc(course.title)}</option>`
        ).join('');
        if (current && library.some((course) => course.id === current)) picker.value = current;
        picker.onchange = () => {
          const id = picker.value;
          if (!id || (activeCourse && activeCourse.id === id)) return;
          openLibraryCourse(id);
        };
      }
      const shelf = $('library-picker');
      if (shelf) {
        const currentId = activeCourse && activeCourse.id;
        shelf.innerHTML = library.map((course) =>
          `<option value="${esc(course.id)}">${esc(course.title)}</option>`
        ).join('');
        if (currentId && library.some((course) => course.id === currentId)) shelf.value = currentId;
        shelf.onchange = () => {
          const id = shelf.value;
          if (!id || (activeCourse && activeCourse.id === id)) return;
          openLibraryCourse(id);
        };
      }
    }

    function setLibraryCollapsed(collapsed) {
      document.body.classList.toggle('library-collapsed', !!collapsed);
      const show = $('library-show');
      if (show) show.hidden = !collapsed;
      const hide = $('library-hide');
      if (hide) hide.setAttribute('aria-pressed', collapsed ? 'true' : 'false');
      try { localStorage.setItem('aoep-library-collapsed', collapsed ? '1' : '0'); } catch (err) {}
    }

    async function openLibraryCourse(id) {
      const course = library.find((row) => row.id === id);
      if (!course || !course.lessons.length) return toast('That course has no lessons yet');
      activeCourse = course;
      lessonCursor = 0;
      reviewScores.quizzes = [];
      reviewScores.games = [];
      slidesSinceCheck = 0;
      lastCheckPassed = null;
      lecturePaused = false;
      if ($('btn-pause')) setPauseButton(false);
      renderLibrary();
      await teachLibraryLesson();
    }

    function fullDriversProgram() {
      return !!(activeCourse && activeCourse.id === 'drivers-ed' && requestedAccess !== 'sample');
    }

    async function teachLibraryLesson() {
      const lesson = activeCourse && activeCourse.lessons[lessonCursor];
      const wholeProgram = fullDriversProgram();
      if (!wholeProgram && !lesson) return;
      teachLanguage = ($('teach-lang') && $('teach-lang').value) || teachLanguage || 'en';
      const now = $('library-now');
      if (now) {
        now.textContent = wholeProgram
          ? activeCourse.title + ' · ' + activeCourse.lessons.length + ' classes'
          : activeCourse.title + ' · part ' + (lessonCursor + 1) +
            ' of ' + activeCourse.lessons.length + ' · ' + (lesson.title || '');
      }
      let data;
      if (wholeProgram) {
        data = await api('/api/studio/courses/certification-program', {
          method:'POST', headers:{'content-type':'application/json'},
          body: JSON.stringify({
            track: 'ca_dmv_permit',
            language: teachLanguage
          })
        });
        selectedCourse = data.course_id;
        await startTeach({ resume: true, focusGaps: false });
        return;
      }
      if (activeCourse.kind === 'cert') {
        data = await api('/api/studio/courses/certification', {
          method:'POST', headers:{'content-type':'application/json'},
          body: JSON.stringify({
            track: lesson.track,
            lesson_id: lesson.lesson_id,
            language: teachLanguage
          })
        });
      } else {
        data = await api('/api/studio/courses/early-learning', {
          method:'POST', headers:{'content-type':'application/json'},
          body: JSON.stringify({
            level: lesson.level,
            topic_id: lesson.topic_id,
            language: teachLanguage
          })
        });
      }
      selectedCourse = data.course_id;
      await startTeach({ resume: true });
    }

    function renderCertLessons() {
      const track = $('cert-track').value;
      const rows = certOptions.filter((row) => row.track === track);
      $('cert-lesson').innerHTML = rows.map((row) =>
        `<option value="${esc(row.lesson_id)}">${esc(row.title)} · ~${row.estimated_minutes} min</option>`
      ).join('');
    }

    async function buildCertCourse() {
      teachLanguage = $('teach-lang').value || 'en';
      const data = await api('/api/studio/courses/certification', {
        method:'POST', headers:{'content-type':'application/json'},
        body: JSON.stringify({
          track: $('cert-track').value,
          lesson_id: $('cert-lesson').value,
          language: teachLanguage
        })
      });
      selectedCourse = data.course_id;
      await refreshCourses();
      toast('Certification prep ready: ' + (data.title || data.course_id) +
        ' · picture + motion on each page');
      await startTeach({ resume: true });
    }

    async function loadEarlyOptions() {
      const data = await api('/api/studio/early-learning/options');
      earlyOptions = data.courses || [];
      const level = $('kids-level');
      level.innerHTML = (data.levels || []).map((row) =>
        `<option value="${esc(row.code)}">${esc(row.name)}</option>`
      ).join('');
      level.value = data.default_level || 'pre_k';
      renderEarlyTopics();
    }

    function renderEarlyTopics() {
      const level = $('kids-level').value;
      const rows = earlyOptions.filter((row) => row.level === level);
      $('kids-topic').innerHTML = rows.map((row) =>
        `<option value="${esc(row.topic_id)}">${esc(row.title)} — ${esc(row.description)}</option>`
      ).join('');
    }

    async function buildEarlyCourse() {
      teachLanguage = $('teach-lang').value || 'en';
      const data = await api('/api/studio/courses/early-learning', {
        method:'POST', headers:{'content-type':'application/json'},
        body: JSON.stringify({
          level: $('kids-level').value,
          topic_id: $('kids-topic').value,
          language: teachLanguage
        })
      });
      selectedCourse = data.course_id;
      await refreshCourses();
      await startTeach();
      toast(`Made ${data.title} · ${data.slides.length} picture-led screens`);
    }

    async function refreshCourses() {
      const data = await api('/api/studio/courses');
      const box = $('course-list');
      if (!box) return;
      box.innerHTML = (data.courses || []).map((c) => `
        <div class="item" data-cid="${esc(c.course_id)}">
          <div><strong>${esc(c.title)}</strong> <span class="pill">${esc(c.category)}</span>
            <span class="pill">${esc(c.language || 'en')}</span></div>
          <div class="meta">${esc(c.course_id)} · ${c.slides.length} slides · ${esc(c.status)}</div>
        </div>`).join('') || '<div class="item">No courses yet.</div>';
      box.querySelectorAll('.item[data-cid]').forEach((el) => {
        el.onclick = () => { selectedCourse = el.getAttribute('data-cid'); startTeach(); };
      });
    }

    function languageSelects() {
      return ['teach-lang', 'teach-lang-stage', 'drive-lang'].map($).filter(Boolean);
    }

    function syncLanguageSelects() {
      languageSelects().forEach((sel) => { sel.value = teachLanguage; });
    }

    function applyTeachLanguage(code) {
      teachLanguage = code || 'en';
      syncLanguageSelects();
      paintLessonChrome(teachLanguage);
      if (activeCourse) teachLibraryLesson().catch((e) => toast(String(e.message || e)));
    }

    async function loadLanguages() {
      const data = await api('/api/studio/languages');
      const rows = (data.languages || []).slice();
      if (!rows.some((l) => l.code === 'yue')) {
        const zhAt = rows.findIndex((l) => l.code === 'zh');
        const cantonese = { code: 'yue', name: 'Cantonese' };
        if (zhAt >= 0) rows.splice(zhAt + 1, 0, cantonese);
        else rows.push(cantonese);
      }
      rows.forEach((l) => { languageNames[l.code] = l.name; });
      const enAt = rows.findIndex((l) => l.code === 'en');
      if (enAt >= 0) {
        rows[enAt] = Object.assign({}, rows[enAt], { name: 'American English' });
        languageNames.en = 'American English';
      }
      let insertAt = enAt >= 0 ? enAt + 1 : rows.length;
      [
        { code: 'en-GB', name: 'British English' },
        { code: 'en-AU', name: 'Australian English' },
        { code: 'en-SG', name: 'Singlish' },
      ].forEach((row) => {
        if (rows.some((l) => l.code === row.code)) return;
        rows.splice(insertAt, 0, row);
        languageNames[row.code] = row.name;
        insertAt += 1;
      });
      const html = rows.map((l) =>
        `<option value="${esc(l.code)}">${esc(l.name)} (${esc(l.code)})</option>`
      ).join('');
      const selects = languageSelects();
      if (!selects.length) return;
      selects.forEach((sel) => { sel.innerHTML = html; });
      syncLanguageSelects();
    }

    function languageLabel(code) {
      return esc(languageNames[code] || code || 'English');
    }

    async function refreshVoiceStatus() {
      const data = await api('/api/studio/voice/status');
      const v = data.voice || {};
      const t = data.tts || {};
      const status = $('voice-status');
      if (!status) return;
      const brain = v.provider === 'supergrok'
        ? `SuperGrok (${v.model || 'grok-4.7'})`
        : `xAI: ${v.provider || 'local-fallback'}` +
          (v.xai_available ? ' (live key)' : ' (offline fallback)');
      status.textContent =
        brain +
        ` · TTS: ${t.engine || 'device'}` +
        ` · langs: ${data.languages || 0}`;
    }

    function profileFromForm() {
      const num = (id, fallback) => {
        const el = $(id);
        return el ? +el.value : fallback;
      };
      return {
        engagement: num('pf-engagement', 0.7),
        literacy: num('pf-literacy', 0.6),
        attention: num('pf-attention', 0.7),
        fatigue: num('pf-fatigue', 0.2),
        confusion: num('pf-confusion', 0.2),
        pace_preference: num('pf-pace', 0.5),
        accessibility_need: num('pf-access', 0.3),
        learn_from_images: num('pf-img', 0.7),
        learn_from_text: num('pf-text', 0.7),
        learn_from_video: num('pf-video', 0.7),
        learn_from_examples: num('pf-examples', 0.75),
        learn_from_quiz: num('pf-quiz', 0.55),
        learn_from_games: num('pf-games', 0.55),
        learn_from_activity: num('pf-activity', 0.5),
      };
    }

    async function startTeach(opts) {
      opts = opts || {};
      if (!selectedCourse) return toast('Select or build a course first');
      lecturePaused = false;
      if ($('btn-pause')) setPauseButton(false);
      teachLanguage = $('teach-lang').value || 'en';
      const data = await api('/api/studio/teach/start', {
        method:'POST', headers:{
          'content-type':'application/json',
          ...(localStorage.getItem('aoep_token')
            ? {'authorization':'Bearer ' + localStorage.getItem('aoep_token')}
            : {})
        },
        body: JSON.stringify({
          session_id: teachSession, course_id: selectedCourse, profile: profileFromForm(),
          learner_id: learnerId,
          focus_gaps: !!(opts && opts.focusGaps === false) ? false : true, known_objective_ids: [],
          language: teachLanguage, use_voice_agent: true,
          voice_gender: courseVoiceGender,
          resume: opts.resume !== false,
          ...teachAccessFields()
        })
      });
      renderTeach(data);
      if (data.resume_message) toast(data.resume_message);
      else if (data.bookmark_available) toast('Saved place found — use Resume saved to continue');
      else toast('Theodore teaching · ' + (data.language || teachLanguage) +
        (data.voice ? ' · ' + data.voice.provider : ''));
    }

    async function runTrialDemo() {
      teachLanguage = $('teach-lang').value || 'en';
      const data = await api('/api/studio/teach/trial-run', {
        method:'POST', headers:{'content-type':'application/json'},
        body: JSON.stringify({
          session_id: teachSession,
          language: teachLanguage,
          learner_id: learnerId,
          profile: profileFromForm(),
          ...teachAccessFields(),
        })
      });
      selectedCourse = data.course_id;
      await refreshCourses();
      renderTeach(data);
      const kinds = (data.segment_kinds || []).join(' → ');
      toast('Trial demo · ' + (data.language || teachLanguage) + ' · ' + kinds);
    }

    async function resumeTeach() {
      if (!selectedCourse) return toast('Select a course first');
      await startTeach({ resume: true });
    }

    async function startOverTeach() {
      if (!selectedCourse) return toast('Select a course first');
      await startTeach({ resume: false });
    }

    async function continueSession() {
      lecturePaused = false;
      if ($('btn-pause')) setPauseButton(false);
      const data = await api('/api/studio/teach/continue', {
        method:'POST', headers:{'content-type':'application/json'},
        body: JSON.stringify({ session_id: teachSession })
      });
      renderTeach(data);
      toast('Continuing this block');
    }

    async function comeBackLater() {
      lecturePaused = true;
      stopSpeech();
      if ($('btn-pause')) setPauseButton(true);
      const data = await api('/api/studio/teach/come-back-later', {
        method:'POST', headers:{'content-type':'application/json'},
        body: JSON.stringify({ session_id: teachSession })
      });
      $('checkpoint-box').classList.remove('show');
      toast(data.message || 'Saved — come back later');
    }

    function lessonTurnLoaded() {
      const turn = lastTeachPayload && lastTeachPayload.turn;
      return !!(turn && (turn.narration || turn.title || turn.display_body));
    }

    function slideCaptionText(payload) {
      const p = payload || lastTeachPayload;
      if (!p) return '';
      const turn = p.turn || p;
      const provider = (p.voice && p.voice.provider) || 'slide';
      return 'Theodore (' + provider + '): ' + (turn.narration || '');
    }

    function currentSectionWords() {
      if (!visualTimeline || visualCueIndex < 0) return '';
      const cue = (visualTimeline.cues || [])[visualCueIndex];
      return cue ? String(cue.caption || '').trim() : '';
    }

    function paintLessonCaption(payload) {
      const el = $('lesson-caption');
      if (!el) return;
      const p = payload || lastTeachPayload;
      const turn = (p && (p.turn || p)) || {};
      const words = currentSectionWords();
      const activity = String((p && p.activity_prompt) || '').trim();
      const line = words || activity || firstLessonSentence(turn.narration || turn.display_body || '');
      el.textContent = line;
      const quiz = $('quiz-box');
      const game = $('game-box');
      const quizOpen = (quiz && quiz.style.display === 'block') || (game && game.style.display === 'block');
      el.hidden = !(captionsEnabled && line && !talkOpen && !quizOpen);
    }

    function applySectionCaption() {
      paintLessonCaption();
      if (talkOpen) return;
      if ($('quiz-box')?.querySelector('.quiz-correction')) return;
      const words = currentSectionWords();
      if (!words) return;
      const body = $('teach-body');
      if (body) body.textContent = words;
      const narr = $('teach-narr');
      if (!narr || !lastTeachPayload) return;
      const provider = (lastTeachPayload.voice && lastTeachPayload.voice.provider) || 'slide';
      narr.textContent = 'Theodore (' + provider + '): ' + words;
    }

    function restoreLessonAvatar() {
      const script = (lastTeachPayload && lastTeachPayload.avatar) || { state: 'presenting', cues: [] };
      if (!theodoreAvatar) return;
      if (theodoreAvatar.setScript) theodoreAvatar.setScript(script);
      else theodoreAvatar.setState('idle');
    }

    function openTalk() {
      if (!lessonTurnLoaded()) return toast('Start a course first');
      talkOpen = true;
      stopSpeech();
      const panel = $('talk-panel');
      if (panel) panel.hidden = false;
      const box = $('voice-ask');
      if (box) box.focus();
    }

    function closeTalk() {
      talkOpen = false;
      stopStudentMic();
      const panel = $('talk-panel');
      if (panel) panel.hidden = true;
      const narr = $('teach-narr');
      if (narr) narr.textContent = slideCaptionText();
      applySectionCaption();
      // Do not read the slide again. A second speakText stacks another
      // narration on top of the one already in flight or just finished.
      const stopReply = speechHold && talkReplyActive;
      if (stopReply) stopSpeech();
      if (lecturePaused || beatHandled) return;
      if (!stopReply && serverAudio && !serverAudio.paused && !serverAudio.ended) return;
      if (!stopReply && window.speechSynthesis && window.speechSynthesis.speaking) return;
      scheduleAutoAdvance(ABSORB_MS);
    }

    let studentRec = null;
    let micReady = false;

    function speechCtor() {
      return window.SpeechRecognition || window.webkitSpeechRecognition || null;
    }

    function recognitionLang() {
      const code = String(teachLanguage || 'en').toLowerCase();
      const map = {
        en:'en-US', es:'es-ES', fr:'fr-FR', de:'de-DE', it:'it-IT', pt:'pt-BR',
        nl:'nl-NL', pl:'pl-PL', ru:'ru-RU', uk:'uk-UA', tr:'tr-TR', ar:'ar-SA',
        he:'he-IL', hi:'hi-IN', bn:'bn-IN', ur:'ur-PK', fa:'fa-IR', zh:'zh-CN',
        yue:'zh-HK', ja:'ja-JP', ko:'ko-KR', vi:'vi-VN', th:'th-TH', id:'id-ID', sw:'sw-KE',
        el:'el-GR', cs:'cs-CZ', km:'km-KH'
      };
      return map[code] || code;
    }

    function releaseMicStream() {
      if (!micStream) return;
      try { micStream.getTracks().forEach((track) => track.stop()); } catch (_) {}
      micStream = null;
    }

    function clearListeningButtons() {
      document.querySelectorAll('button.is-listening').forEach((el) => {
        el.classList.remove('is-listening');
        if (el.dataset.label) el.textContent = el.dataset.label;
      });
    }

    function stopStudentMic() {
      const rec = studentRec;
      studentRec = null;
      if (rec) {
        try { rec.onresult = null; rec.onerror = null; rec.onend = null; } catch (_) {}
        try { rec.abort(); } catch (_) { try { rec.stop(); } catch (_) {} }
      }
      releaseMicStream();
      clearListeningButtons();
    }

    async function ensureMic() {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        toast('This browser cannot use the microphone. Type instead.');
        return false;
      }
      if (micReady) return true;
      try {
        const stream = window.TheodoreLiveAudio && window.TheodoreLiveAudio.openMic
          ? await window.TheodoreLiveAudio.openMic()
          : await navigator.mediaDevices.getUserMedia({
            audio: {echoCancellation:true, noiseSuppression:true, autoGainControl:false, channelCount:1},
            video: false,
          });
        // Permission probe only. Hold it until the recognizer is running, then
        // stopStudentMic releases the hardware so the indicator does not stick.
        micStream = stream;
        micReady = true;
        return true;
      } catch (_) {
        releaseMicStream();
        toast('Allow the microphone to speak your question or answer.');
        return false;
      }
    }

    async function listenOnce(onText, button) {
      const Ctor = speechCtor();
      if (!Ctor) {
        toast('This browser cannot hear speech. Type your question or answer.');
        return;
      }
      if (window.__THEODORE_LIVE_AUDIO_ACTIVE__ && !window.__THEODORE_LIVE_AUDIO_HOLD__) {
        toast('Just speak. You can interrupt Theodore — he stops, listens, then answers.');
        window.TheodoreLiveAudio?.resumeRecognition();
        return;
      }
      const ok = await ensureMic();
      if (!ok) return;
      stopSpeech();
      stopStudentMic();
      const rec = new Ctor();
      studentRec = rec;
      rec.lang = recognitionLang();
      rec.interimResults = true;
      rec.continuous = false;
      rec.maxAlternatives = 1;
      if (button) {
        button.dataset.label = button.dataset.label || button.textContent;
        button.classList.add('is-listening');
        button.textContent = 'Listening…';
      }
      let finalText = '';
      rec.onresult = (event) => {
        let interim = '';
        const results = event.results || [];
        for (let i = event.resultIndex || 0; i < results.length; i++) {
          const piece = (results[i][0] && results[i][0].transcript) || '';
          if (results[i].isFinal) finalText += piece;
          else interim += piece;
        }
        const heard = (finalText || interim).trim();
        const last = results[results.length - 1];
        const isFinal = !!(last && last.isFinal) || !!finalText;
        if (heard) onText(heard, isFinal && !!finalText);
      };
      const finishRec = () => {
        if (button) {
          button.classList.remove('is-listening');
          if (button.dataset.label) button.textContent = button.dataset.label;
        }
        if (studentRec === rec) studentRec = null;
        releaseMicStream();
      };
      rec.onerror = (event) => {
        const err = (event && event.error) || '';
        if (err === 'not-allowed' || err === 'service-not-allowed') {
          micReady = false;
          toast('Allow the microphone, then tap Speak again.');
        } else if (err === 'no-speech') toast('No speech heard. Try again.');
        else if (err && err !== 'aborted') toast('Could not hear that. Try again or type.');
        finishRec();
      };
      rec.onend = () => finishRec();
      try { rec.start(); }
      catch (_) {
        finishRec();
        toast('Tap Speak again to start the microphone.');
      }
    }

    function spokenWords(text) {
      return String(text || '').toLowerCase().replace(/[^a-z0-9 ]/g, ' ').replace(/\\s+/g, ' ').trim();
    }

    function matchSpokenChoice(spoken, choices) {
      const said = spokenWords(spoken);
      if (!said) return -1;
      const letters = { a:0, b:1, c:2, d:3, e:4, f:5 };
      const ordinals = {
        one:0, first:0, two:1, second:1, three:2, third:2,
        four:3, fourth:3, five:4, fifth:4, six:5, sixth:5
      };
      if (Object.prototype.hasOwnProperty.call(letters, said) && letters[said] < choices.length) return letters[said];
      if (Object.prototype.hasOwnProperty.call(ordinals, said) && ordinals[said] < choices.length) return ordinals[said];
      const fillers = { the:1, number:1, option:1, choice:1, answer:1, please:1, its:1, it:1, is:1 };
      const tokens = said.split(' ').filter((word) => word && !fillers[word]);
      if (tokens.length === 1 && Object.prototype.hasOwnProperty.call(ordinals, tokens[0]) && ordinals[tokens[0]] < choices.length) {
        return ordinals[tokens[0]];
      }
      if (tokens.length === 1 && Object.prototype.hasOwnProperty.call(letters, tokens[0]) && letters[tokens[0]] < choices.length) {
        return letters[tokens[0]];
      }
      const numbered = said.match(/^(?:number|option|choice|answer)?\\s*(\\d+)$/);
      const num = numbered ? parseInt(numbered[1], 10) : parseInt(said, 10);
      if (num >= 1 && num <= choices.length && String(num) === said.replace(/\\D/g, '')) return num - 1;
      let best = -1;
      let bestScore = 0;
      choices.forEach((choice, index) => {
        const words = spokenWords(choice).split(' ').filter((word) => word.length > 2);
        const score = words.filter((word) => said.includes(word)).length;
        if (score > bestScore) { bestScore = score; best = index; }
      });
      return bestScore > 0 ? best : -1;
    }

    let spokenActivity = null;
    let spokenActivityPrompt = '';
    function clearSpokenActivity() {
      spokenActivity = null;
      spokenActivityPrompt = '';
    }
    function armSpokenActivity(handler, prompt) {
      spokenActivity = typeof handler === 'function' ? handler : null;
      const line = String(prompt || '').trim();
      spokenActivityPrompt = line;
      if (!line || !window.TheodoreLiveAudio || !window.TheodoreLiveAudio.noteActivity) return;
      window.TheodoreLiveAudio.noteActivity({
        id: line.slice(0, 160),
        prompt: 'A game is on the screen. Ask for the answer in one short sentence and wait. Do not reveal the correct answer. ' + line
      });
    }
    function applySpokenActivity(text, role) {
      if (role !== 'user' || typeof spokenActivity !== 'function') return false;
      const heard = $('game-heard') || $('quiz-heard') || $('summary-sync-heard');
      if (heard) heard.textContent = 'Heard: ' + text;
      return spokenActivity(text) === true;
    }
    function saidCheck(text) {
      const said = spokenWords(text);
      return said === 'check' || said === 'done' || said === 'submit' || said === 'finished' ||
        said === 'check order' || said === 'check my answer';
    }

    function speakQuestion() {
      if (!lessonTurnLoaded()) return toast('Start a course first');
      if (!talkOpen) openTalk();
      let sent = false;
      const box = $('voice-ask');
      listenOnce((text, isFinal) => {
        if (box) box.value = text;
        if (isFinal && !sent && text.trim()) {
          sent = true;
          stopStudentMic();
          askTheodore().catch((e) => toast(String(e.message || e)));
        }
      }, $('btn-talk-mic'));
    }

    async function askTheodore() {
      const box = $('voice-ask');
      const msg = (box && box.value || '').trim();
      if (sampleIsComplete()) return toast(trialEndedMessage(lastTeachPayload));
      if (!msg) return toast('Ask a question about this course');
      if (!lessonTurnLoaded()) return toast('Start a course first');
      const epoch = teachEpoch;
      stopSpeech();
      stopStudentMic();
      theodoreAvatar?.setState('thinking');
      let data;
      try {
        data = await api('/api/studio/teach/voice/respond', {
          method:'POST', headers:{'content-type':'application/json'},
          body: JSON.stringify({ session_id: teachSession, message: msg })
        });
      } catch (error) {
        if (epoch === teachEpoch) restoreLessonAvatar();
        throw error;
      }
      if (epoch !== teachEpoch) return;
      if (data.sample && data.sample.complete) {
        endSampleTrial(Object.assign({}, lastTeachPayload || {}, data));
        toast(trialEndedMessage(data));
        return;
      }
      const voice = data.voice || {};
      const reply = voice.message || '';
      if (!reply) {
        restoreLessonAvatar();
        return toast('Theodore had no answer. Try again.');
      }
      const slot = $('talk-reply');
      if (slot) slot.textContent = reply;
      $('teach-narr').textContent = reply;
      const avatar = data.avatar || (data.turn && data.turn.avatar);
      if (avatar) theodoreAvatar?.setScript(avatar);
      else restoreLessonAvatar();
      // Talk is on demand: data.tts has no baked clip, so this POSTs /api/studio/tts.
      speakText(reply, data.tts, true, 'talk');
      if (box) box.value = '';
      queueLiveTopic(msg);
    }

    function clearAutoAdvance() {
      if (autoAdvanceTimer) {
        clearTimeout(autoAdvanceTimer);
        autoAdvanceTimer = null;
      }
    }

    function isLastSlide(payload) {
      const p = payload || lastTeachPayload;
      if (!p || !Array.isArray(p.path) || !p.path.length) return true;
      return (p.path_pos || 0) >= p.path.length - 1;
    }

    function narrationDwellMs(text) {
      const words = String(text || '').trim().split(/\\s+/).filter(Boolean).length;
      // ~140 words a minute, with a floor so a short scene still finishes its move.
      return Math.min(90000, Math.max(4500, words * 430));
    }

    function pageDifficulty(payload) {
      const turn = (payload && (payload.turn || payload)) || {};
      const text = String(turn.display_body || turn.narration || '');
      const words = text.trim().split(/\\s+/).filter(Boolean).length;
      // A short sign page is easier to hold. A long rule page needs a sooner check.
      if (words >= 90) return 'hard';
      if (words <= 45) return 'easy';
      return 'medium';
    }

    function checkGapFor(payload) {
      if (lastCheckPassed === false) return 4;
      const level = pageDifficulty(payload);
      if (level === 'hard') return 4;
      if (level === 'easy') return 8;
      return 6;
    }

    function pickLearnVariety(payload) {
      // Activities are authored by the server. The browser must never randomly
      // invent a quiz that the narration did not schedule.
      const pos = Number(payload && payload.path_pos) || 0;
      return (payload && payload.examples && payload.examples.length && pos % 3 === 1)
        ? 'examples' : 'straight';
    }

    function pctLabel(value) {
      const n = Number(value);
      if (!Number.isFinite(n)) return '—';
      return Math.round(Math.max(0, Math.min(1, n)) * 100) + '%';
    }

    function scoreRow(label, value) {
      const n = Number(value);
      if (!Number.isFinite(n)) return '';
      const width = Math.max(0, Math.min(100, Math.round(n * 100)));
      return `<div class="score-row"><span>${esc(label)}</span><b>${pctLabel(n)}</b><div class="meter"><span style="width:${width}%"></span></div></div>`;
    }

    function averageScore(rows) {
      if (!rows.length) return null;
      return rows.reduce((sum, row) => sum + Number(row.score || 0), 0) / rows.length;
    }

    function noteScore(kind, score, passed) {
      const bucket = kind === 'game' ? reviewScores.games : reviewScores.quizzes;
      bucket.push({ score: Number(score) || 0, passed: !!passed });
      lastCheckPassed = !!passed;
      if (reviewOpen) renderReview();
    }

    function toggleReview(force) {
      reviewOpen = typeof force === 'boolean' ? force : !reviewOpen;
      const panel = $('review-overlay');
      if (panel) panel.classList.toggle('show', reviewOpen);
      const btn = $('btn-review');
      if (btn) {
        btn.setAttribute('aria-pressed', reviewOpen ? 'true' : 'false');
        btn.textContent = reviewOpen ? 'Hide review' : 'Review';
      }
      if (reviewOpen) renderReview();
    }

    function renderReview() {
      const body = $('review-body');
      if (!body) return;
      const payload = lastTeachPayload;
      if (!payload) {
        body.innerHTML = '<p>Start a course. Features and scores show up here while it plays.</p>';
        return;
      }
      const turn = payload.turn || {};
      const kit = payload.learning_kit || {};
      const prog = payload.progress || {};
      const profile = turn.profile_snapshot || {};
      const features = [
        ['Storyboard', kit.has_storyboard],
        ['Picture', kit.has_picture],
        ['Video', kit.has_video],
        ['Examples', kit.has_examples],
        ['Quiz', kit.has_quiz],
        ['Game', kit.has_game],
        ['Activity', kit.has_activity]
      ].filter((row) => row[1]).map((row) => row[0]);
      const variety = { straight: 'Narration', examples: 'Examples', quiz: 'Quiz', game: 'Game' }[slideVariety] || slideVariety;
      const preferred = (kit.preferred || []).join(', ');
      const slideNo = (payload.path_pos || 0) + 1;
      const slideCount = (payload.path || []).length || 1;
      const lesson = activeCourse
        ? (lessonCursor + 1) + ' / ' + activeCourse.lessons.length
        : '—';
      const lastQuiz = reviewScores.quizzes[reviewScores.quizzes.length - 1];
      const lastGame = reviewScores.games[reviewScores.games.length - 1];
      const quizAvg = averageScore(reviewScores.quizzes);
      const gameAvg = averageScore(reviewScores.games);
      const profileRows = [
        ['Engagement', 'engagement'],
        ['Literacy', 'literacy'],
        ['Attention', 'attention'],
        ['Fatigue', 'fatigue'],
        ['Confusion', 'confusion'],
        ['Pace', 'pace_preference'],
        ['Accessibility', 'accessibility_need'],
        ['Images', 'learn_from_images'],
        ['Text', 'learn_from_text'],
        ['Video', 'learn_from_video'],
        ['Examples', 'learn_from_examples'],
        ['Quiz', 'learn_from_quiz'],
        ['Games', 'learn_from_games'],
        ['Activity', 'learn_from_activity']
      ];
      body.innerHTML = `
        <h3>This screen</h3>
        <dl>
          <dt>Learning</dt><dd>${esc(variety)}</dd>
          <dt>Features</dt><dd>${esc(features.join(', ') || 'Voice')}</dd>
          <dt>Preferred</dt><dd>${esc(preferred || '—')}</dd>
          <dt>Objective</dt><dd>${esc((payload.objective && payload.objective.title) || '—')}</dd>
          <dt>Slide</dt><dd>${slideNo} / ${slideCount}</dd>
          <dt>Lesson</dt><dd>${esc(String(lesson))}</dd>
          <dt>Language</dt><dd>${esc(payload.spoken_language || payload.language || '')}</dd>
          <dt>Adaptations</dt><dd>${esc((turn.adaptations_applied || []).join(', ') || 'none')}</dd>
        </dl>
        <h3>Progress</h3>
        <dl>
          <dt>Known</dt><dd>${prog.known || 0}</dd>
          <dt>Gaps</dt><dd>${prog.gaps || 0}</dd>
          <dt>Objectives</dt><dd>${prog.total_objectives || 0}</dd>
          <dt>Completed slides</dt><dd>${prog.completed_slides || 0}</dd>
          <dt>Elapsed</dt><dd>${(payload.checkpoint && payload.checkpoint.elapsed_minutes) || 0} min</dd>
        </dl>
        <h3>Scores</h3>
        ${lastQuiz ? `<dl><dt>Last quiz</dt><dd>${pctLabel(lastQuiz.score)} ${lastQuiz.passed ? 'passed' : 'missed'}</dd></dl>` : '<p>No quiz yet this course.</p>'}
        ${lastGame ? `<dl><dt>Last game</dt><dd>${pctLabel(lastGame.score)} ${lastGame.passed ? 'passed' : 'missed'}</dd></dl>` : ''}
        ${quizAvg === null ? '' : scoreRow('Quiz average', quizAvg)}
        ${gameAvg === null ? '' : scoreRow('Game average', gameAvg)}
        <div id="review-engagement"></div>
        <h3>Profile</h3>
        ${profileRows.map((row) => scoreRow(row[0], profile[row[1]])).join('')}
      `;
      if (reviewOpen) refreshReviewTelemetry();
    }

    async function refreshReviewTelemetry() {
      if (!reviewOpen) return;
      try {
        const data = await api('/api/studio/telemetry');
        const slot = $('review-engagement');
        if (!slot || !reviewOpen) return;
        slot.innerHTML = scoreRow('Engagement', data.engagement_score) +
          `<dl><dt>Slides taught</dt><dd>${data.slides_taught || 0}</dd>
             <dt>Quizzes</dt><dd>${data.quizzes_passed || 0} / ${data.quizzes_started || 0}</dd>
             <dt>Games</dt><dd>${data.games_passed || 0} / ${data.games_started || 0}</dd>
             <dt>Avg quiz</dt><dd>${pctLabel(data.avg_quiz_score)}</dd>
             <dt>Avg game</dt><dd>${pctLabel(data.avg_game_score)}</dd></dl>`;
      } catch (_) {}
    }

    function scheduleAutoAdvance(delayMs) {
      clearAutoAdvance();
      if (sampleIsComplete()) return;
      if (learningHold || learningCheckOpen || lecturePaused || beatHandled || talkOpen) return;
      if (lessonLife.isAway()) return;
      autoAdvanceTimer = setTimeout(() => {
        autoAdvanceTimer = null;
        finishSlideBeat();
      }, delayMs);
    }

    function finishSlideBeat() {
      if (learningHold) return;
      if (lecturePaused || beatHandled) return;
      const checkpoint = (lastTeachPayload && lastTeachPayload.activity_checkpoint) || {};
      if (sampleIsComplete() && !checkpoint.due) return;
      beatHandled = true;
      clearAutoAdvance();
      if (checkpoint.due) {
        presentActivityCheckpoint(checkpoint);
        return;
      }
      continueAfterActivity();
    }

    function presentCompareQuiz(checkpoint) {
      const compare = (checkpoint && checkpoint.compare) || {};
      const box = $('quiz-box');
      const prompt = compare.prompt || checkpoint.prompt || 'Compare the two ideas and pick the one that fits.';
      const correctText = compare.correct_side === 'right' ? (compare.right || '') : (compare.left || '');
      learningCheckOpen = true;
      clearAutoAdvance();
      box.style.display = 'block';
      box.innerHTML = `<div class="quiz-correction" role="status">
        <strong>${esc(prompt)}</strong>
        <div class="challenge-grid">
          <button type="button" class="challenge-choice" data-voice-choice data-side="left">${esc(compare.left || '')}</button>
          <button type="button" class="challenge-choice" data-voice-choice data-side="right">${esc(compare.right || '')}</button>
        </div>
      </div>`;
      speakText(prompt, null, true, 'learn-check');
      const grade = (side) => {
        clearSpokenActivity();
        const ok = side === compare.correct_side;
        box.innerHTML = `<div class="quiz-correction${ok ? ' is-correct' : ''}">
          <strong>${ok ? 'Correct' : 'Not quite'}</strong>
          <p>${esc(ok ? correctText : ('The matching idea is: ' + correctText))}</p>
          <button type="button" class="primary" id="compare-continue">Continue</button>
        </div>`;
        speakText(ok ? 'Correct. ' + correctText : 'The matching idea is ' + correctText, null, true, 'learn-check');
        const next = box.querySelector('#compare-continue');
        if (next) next.onclick = () => {
          box.style.display = 'none';
          learningCheckOpen = false;
          continueAfterActivity();
        };
      };
      box.querySelectorAll('[data-side]').forEach((button) => {
        button.onclick = () => grade(button.dataset.side);
      });
      armSpokenActivity((text) => {
        const index = matchSpokenChoice(text, [compare.left || '', compare.right || '']);
        if (index < 0) return false;
        grade(index === 0 ? 'left' : 'right');
        return true;
      }, prompt + ' Left: ' + (compare.left || '') + '. Right: ' + (compare.right || ''));
    }

    function presentActivityCheckpoint(checkpoint) {
      if (checkpoint && checkpoint.activity === 'compare' && checkpoint.compare) {
        presentCompareQuiz(checkpoint);
        return;
      }
      if (checkpoint && (checkpoint.activity === 'quiz' || checkpoint.kind === 'summary_quiz')) {
        learningCheckOpen = true;
        clearAutoAdvance();
        summaryQuizInteractive().catch((error) => {
          learningCheckOpen = false;
          toast(String(error.message || error));
        });
        return;
      }
      if (checkpoint && checkpoint.activity === 'game') {
        learningCheckOpen = true;
        playGame().catch((error) => {
          learningCheckOpen = false;
          toast(String(error.message || error));
        });
        return;
      }
      const box = $('quiz-box');
      const prompt = checkpoint.prompt || 'Check what you remember before continuing.';
      learningCheckOpen = true;
      clearAutoAdvance();
      box.style.display = 'block';
      box.innerHTML = `<div class="quiz-correction" role="status">
        <strong>${esc(prompt)}</strong>
        <p class="heard">Say one idea from this page in your own words. The lesson continues only after that answer connects.</p>
        <textarea id="learn-check-text" rows="2" placeholder="The idea I just learned is…"></textarea>
        <button type="button" class="primary" id="learn-check-send">Submit answer</button>
        <button type="button" class="secondary" id="learn-check-mic">Speak</button>
      </div>`;
      speakText(prompt + ' Tell me one idea from this page before we continue.', null, true, 'learn-check');
      box.querySelector('#learn-check-send').onclick = () => {
        submitLearningCheck(box.querySelector('#learn-check-text').value, checkpoint)
          .catch((error) => toast(String(error.message || error)));
      };
      box.querySelector('#learn-check-mic').onclick = () => listenForLearningCheck(checkpoint);
    }

    function lessonTextForCheck() {
      const turn = (lastTeachPayload && (lastTeachPayload.turn || lastTeachPayload)) || {};
      return [turn.title, turn.narration, turn.display_body].filter(Boolean).join(' ');
    }

    async function submitLearningCheck(spoken, checkpoint) {
      const text = String(spoken || '').trim();
      if (!text) return toast('Say or type one idea from the page.');
      const data = await api('/api/studio/learn/check', {
        method: 'POST', headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          session_id: cameraSessionId(),
          lesson_text: lessonTextForCheck(),
          spoken: text,
          language: (lastTeachPayload && lastTeachPayload.spoken_language) || teachLanguage || 'en',
          spoken_language: teachLanguage || 'en',
        }),
      });
      if (data.speech) speakText(data.speech, null, true, 'learn-check');
      if (!data.accepted) {
        toast(data.speech || 'That answer does not connect yet.');
        return;
      }
      learningCheckOpen = false;
      const box = $('quiz-box');
      if (box) box.style.display = 'none';
      if (checkpoint && checkpoint.kind === 'summary_quiz') summaryQuizInteractive();
      else continueAfterActivity();
    }

    function listenForLearningCheck(checkpoint) {
      const Rec = window.SpeechRecognition || window.webkitSpeechRecognition;
      const field = $('learn-check-text');
      if (!Rec) {
        toast('This browser has no speech recognition. Type the idea instead.');
        if (field) field.focus();
        return;
      }
      const rec = new Rec();
      rec.lang = recognitionLang();
      rec.onresult = (event) => {
        const said = event.results && event.results[0] && event.results[0][0]
          ? event.results[0][0].transcript : '';
        if (field) field.value = said;
        submitLearningCheck(said, checkpoint).catch((error) => toast(String(error.message || error)));
      };
      rec.onerror = () => toast('I could not hear that. Type the idea instead.');
      try { rec.start(); } catch (_) { toast('Type the idea instead.'); }
    }

    async function continueAfterActivity() {
      if (lecturePaused || advancing) return;
      clearAutoAdvance();
      if (!isLastSlide()) {
        await nextSlide({ auto: true });
        return;
      }
      const program = lastTeachPayload && lastTeachPayload.progress
        && typeof lastTeachPayload.progress.program_percent === 'number';
      if (!program && activeCourse && lessonCursor < activeCourse.lessons.length - 1) {
        lessonCursor += 1;
        await teachLibraryLesson();
        return;
      }
      const name = activeCourse ? activeCourse.title : 'Lesson';
      toast(name + ' complete');
    }

    function onNarrationEnded(gen) {
      if (gen !== speechGen) return;
      theodoreAvatar?.stopSpeaking();
      if (window.__THEODORE_LIVE_AUDIO_ACTIVE__) {
        if (liveCourseHold) {
          liveCourseHold = false;
          window.TheodoreLiveAudio?.resumeRecognition();
        }
        return;
      }
      showAbsorb(true);
      scheduleAutoAdvance(ABSORB_MS);
    }

    function showAbsorb(on) {
      const note = $('absorb-note');
      if (note) note.hidden = !on;
    }

    async function nextSlide(opts) {
      clearSpokenActivity();
      const automatic = !!(opts && opts.auto);
      if (sampleIsComplete()) {
        endSampleTrial(lastTeachPayload);
        if (!automatic) toast(trialEndedMessage(lastTeachPayload));
        return;
      }
      if (learningHold) {
        if (!automatic) toast('Come back to the camera before the lesson continues.');
        return;
      }
      if (learningCheckOpen) {
        if (!automatic) toast('Answer the learning check before continuing.');
        return;
      }
      if (automatic && (lecturePaused || advancing || isLastSlide())) return;
      if (!teachSession) return;
      if (advancing || lessonLife.isAway()) return;
      clearAutoAdvance();
      advancing = true;
      stopSpeech();
      theodoreAvatar?.setState('idle');
      const token = lessonLife.token();
      const pending = apiTimed('/api/studio/teach/advance', {
        method:'POST', headers:{'content-type':'application/json'},
        body: JSON.stringify({ session_id: teachSession })
      }, ADVANCE_TIMEOUT_MS);
      advancePromise = pending;
      try {
        const data = await pending;
        // A return-to-lesson resume reconciles with the server itself.
        if (token === lessonLife.token() && !lessonLife.isAway()) renderTeach(data);
      } finally {
        if (advancePromise === pending) advancePromise = null;
        advancing = false;
      }
    }

    function onDriveWaveTap() {
      if (lessonLife.failed() || (learningHold && holdGroup(learningHoldReason) === 'away')) {
        void lifecycleReturn('tap', { force: true });
        return;
      }
      if (learningHold) {
        pauseLessonForAbsence(PRESENCE_PAUSE);
        return;
      }
      if (sampleIsComplete()) {
        endSampleTrial(lastTeachPayload);
        return;
      }
      if (document.body.classList.contains('is-speaking') && !lecturePaused) {
        toggleLecturePause();
        return;
      }
      if (lecturePaused) {
        toggleLecturePause();
        return;
      }
      readCurrentAloud();
    }

    function toggleLecturePause() {
      if (sampleIsComplete()) {
        lecturePaused = true;
        endSampleTrial(lastTeachPayload);
        return;
      }
      if (learningHold && lecturePaused) return;
      lecturePaused = !lecturePaused;
      if (lecturePaused) {
        stopSpeech();
        theodoreAvatar?.setState('paused');
        setPauseButton(true);
        window.TheodoreLiveAudio?.pauseRecognition();
        return;
      }
      setPauseButton(false);
      window.TheodoreLiveAudio?.resumeRecognition();
      const live = window.__THEODORE_LIVE_AUDIO_ACTIVE__ && !window.__THEODORE_LIVE_AUDIO_HOLD__;
      if (!live) readCurrentAloud();
    }

    const VOICE_EFFECTS = ['fade', 'fly', 'wipe', 'zoom', 'cover', 'split'];
    let voiceEffectAt = 0;
    let spokenExampleAt = -1;

    function cycleLessonAnimation() {
      const stage = $('teach-stage');
      if (stage) {
        stage.classList.remove('voice-animation');
        void stage.offsetWidth;
        stage.classList.add('voice-animation');
      }
      const img = $('lesson-photo-img');
      const url = img && img.getAttribute('src');
      if (!url) return;
      voiceEffectAt = (voiceEffectAt + 1) % VOICE_EFFECTS.length;
      paintLessonPhoto(url, VOICE_EFFECTS[voiceEffectAt], img.alt || 'Lesson photograph');
    }

    function showSpokenExample() {
      const payload = lastTeachPayload || {};
      const examples = payload.topic_examples || payload.examples || [];
      const exBox = $('teach-examples');
      if (!exBox || !examples.length) {
        cycleLessonAnimation();
        return;
      }
      spokenExampleAt = (spokenExampleAt + 1) % examples.length;
      const line = examples[spokenExampleAt];
      exBox.style.display = 'block';
      exBox.innerHTML = '<strong>Example</strong><ol><li>' + esc(line) + '</li></ol>';
      cycleLessonAnimation();
    }

    function applyLiveAudioAction(detail) {
      const action = detail && detail.action;
      if (!action || lecturePaused) return false;
      if ((action === 'next' || action === 'next_section') && teachSession) {
        nextSlide().catch((error) => toast(String(error.message || error)));
        return true;
      }
      if (action === 'example' && teachSession) {
        showSpokenExample();
        return true;
      }
      if (action === 'animation') {
        cycleLessonAnimation();
        return true;
      }
      if ((action === 'next_game' || action === 'game') && teachSession) {
        playGame().catch((error) => toast(String(error.message || error)));
        return true;
      }
      return false;
    }

    function queueLiveTopic(text) {
      pendingTopic = text;
      clearTimeout(topicTimer);
      topicTimer = setTimeout(() => {
        topicTimer = null;
        syncLiveTopic().catch((error) => toast(String(error.message || error)));
      }, 800);
    }

    async function syncLiveTopic() {
      if (!teachSession || lecturePaused) return;
      if (topicSyncing) return;
      topicSyncing = true;
      try {
        while (pendingTopic) {
          const text = pendingTopic;
          pendingTopic = '';
          const data = await api('/api/studio/teach/topic', {
            method:'POST', headers:{'content-type':'application/json'},
            body: JSON.stringify({ session_id: teachSession, text: text })
          });
          if (data.dynamic) {
            liveCourseHold = false;
            renderTeach(data);
            showTopicExamples(data);
            showQuestionSources(data);
            continue;
          }
          if (!data.matched) {
            paintCompletion(data);
            continue;
          }
          if (lastTeachPayload && data.slide_index === lastTeachPayload.slide_index) {
            paintCompletion(data);
            showTopicExamples(data);
            continue;
          }
          liveCourseHold = false;
          renderTeach(data);
          showTopicExamples(data);
        }
      } finally {
        topicSyncing = false;
      }
    }

    async function resumeUncoveredCourse() {
      if (!teachSession || lecturePaused || liveCourseHold) return;
      liveCourseHold = true;
      window.TheodoreLiveAudio?.pauseRecognition();
      const data = await api('/api/studio/teach/resume-uncovered', {
        method:'POST', headers:{'content-type':'application/json'},
        body: JSON.stringify({ session_id: teachSession })
      });
      renderTeach(data);
      showTopicExamples(data);
      paintCompletion(data);
      if (data.course_complete) {
        liveCourseHold = false;
        window.TheodoreLiveAudio?.resumeRecognition();
        toast('Every section of this course has been covered');
        return;
      }
      const turn = data.turn || {};
      speakText(turn.narration || turn.display_body || '', data.tts, false, 'course-resume');
    }

    function paintCompletion(payload) {
      const prog = (payload && payload.progress) || {};
      if (typeof prog.completion_percent !== 'number') return;
      const line = $('teach-adapt');
      if (!line) return;
      const mark = ' · ' + prog.completion_percent + '% of the course';
      if (!line.textContent.includes('% of the course')) line.textContent += mark;
    }

    function coursePlacePercent(payload) {
      const path = (payload && payload.path) || [];
      const total = path.length || Number(payload && payload.progress && payload.progress.path_length) || 0;
      if (!total) return 0;
      const pos = Number(payload && payload.path_pos) || 0;
      return Math.round(((pos + 1) / total) * 100);
    }

    function paintCourseMap(payload) {
      const map = $('course-map');
      if (!map || !payload || !Array.isArray(payload.path) || !payload.path.length) return;
      const total = payload.path.length;
      const pos = Math.max(0, Math.min(total - 1, Number(payload.path_pos) || 0));
      const place = coursePlacePercent(payload);
      const progress = payload.progress || {};
      const covered = typeof progress.covered_percent === 'number'
        ? progress.covered_percent
        : progress.completion_percent;
      map.hidden = false;
      const percent = $('course-map-percent');
      const count = $('course-map-count');
      const fill = $('course-map-fill');
      const scrub = $('course-map-scrub');
      const programPct = typeof progress.program_percent === 'number' ? progress.program_percent : null;
      const classPct = typeof progress.class_percent === 'number' ? progress.class_percent : null;
      const shown = programPct != null ? programPct : (typeof covered === 'number' ? covered : place);
      if (percent) percent.textContent = shown + '%';
      const slideLabel = (count && count.textContent) ? count.textContent : ('Slide ' + (pos + 1) + ' of ' + total);
      if (count) {
        if (programPct != null) {
          const className = progress.class_title || 'This class';
          const classNo = (Number(progress.class_index) || 0) + 1;
          const classTotal = progress.class_count || 1;
          count.textContent = 'Class ' + classNo + ' of ' + classTotal + ' · ' + className +
            ' · class ' + classPct + '% · program ' + programPct + '%';
        } else {
          const coveredMark = typeof covered === 'number' ? ' · covered ' + covered + '%' : '';
          count.textContent = 'Slide ' + (pos + 1) + ' of ' + total + coveredMark;
        }
      }
      const ringLabel = (count && count.textContent ? count.textContent : slideLabel) + ', ' + shown + '%';
      const ring = $('course-progress-ring');
      if (ring) {
        ring.setAttribute('aria-label', ringLabel);
        ring.title = ringLabel;
      }
      if (count) count.title = ringLabel;
      if (fill) {
        const ringLen = 97.39;
        const pct = Math.max(0, Math.min(100, Number(shown) || 0));
        if (fill.tagName && fill.tagName.toLowerCase() === 'circle') {
          fill.style.strokeDasharray = String(ringLen);
          fill.style.strokeDashoffset = String(ringLen * (1 - pct / 100));
        } else {
          fill.style.width = shown + '%';
        }
      }
      const gapBtn = $('course-map-gap');
      if (gapBtn) gapBtn.hidden = programPct == null || payload.access_mode === 'sample';
      if (scrub) {
        scrub.max = String(total - 1);
        scrub.value = String(pos);
      }
      const list = $('course-map-list');
      if (!list) return;
      const rows = Array.isArray(payload.outline) && payload.outline.length
        ? payload.outline
        : payload.path.map((_, index) => ({
            path_pos: index,
            title: 'Slide ' + (index + 1),
            chapter: 1,
            chapter_start: index === 0,
            current: index === pos,
          }));
      list.innerHTML = rows.map((row) => {
        const heading = row.chapter_start
          ? '<div class="chapter">' + esc(row.chapter_title || ('Chapter ' + row.chapter)) + '</div>' : '';
        const cls = [row.current ? 'is-current' : '', row.gap ? 'is-gap' : ''].filter(Boolean).join(' ');
        return heading + '<li><button type="button" data-path-pos="' + row.path_pos + '"' +
          (cls ? ' class="' + cls + '"' : '') + '>' +
          (row.path_pos + 1) + '. ' + esc(row.title || 'Slide') +
          (row.gap ? ' · gap' : '') + '</button></li>';
      }).join('');
    }

    async function jumpToPath(pathPos) {
      if (!teachSession || sampleIsComplete()) return;
      clearAutoAdvance();
      stopSpeech();
      const data = await api('/api/studio/teach/goto', {
        method:'POST', headers:{'content-type':'application/json'},
        body: JSON.stringify({ session_id: teachSession, path_pos: pathPos })
      });
      renderTeach(data);
    }

    function syncVoiceToSlide(payload, opts) {
      if (lecturePaused || sampleIsComplete() || lessonLife.isAway()) return;
      if (!window.__THEODORE_LIVE_AUDIO_ACTIVE__ || window.__THEODORE_LIVE_AUDIO_HOLD__) return;
      if (!window.TheodoreLiveAudio || !window.TheodoreLiveAudio.noteActivity) return;
      const turn = (payload && (payload.turn || payload)) || {};
      const narration = String(turn.narration || turn.display_body || turn.title || '').trim();
      if (!narration) return;
      const title = String(turn.title || '');
      const force = !!(opts && opts.force);
      lastSpeakRequestAt = Date.now();
      window.TheodoreLiveAudio.noteActivity({
        id: 'slide-' + String(payload.slide_index ?? payload.path_pos ?? title),
        force: force,
        prompt: (force ? 'The learner just came back. Pick up on this same slide from the start. ' : '') +
          'Stay on this lesson slide. Read it aloud, then wait. Do not change the subject. Title: ' +
          title + '. ' + narration
      });
    }

    function showTopicExamples(payload) {
      const examples = (payload && (payload.topic_examples || payload.examples)) || [];
      const exBox = $('teach-examples');
      if (!exBox || !examples.length || !(payload.show_examples || payload.topic_jump)) return;
      exBox.style.display = 'block';
      exBox.innerHTML = '<strong>Example</strong><ol>' +
        examples.map((line) => `<li>${esc(line)}</li>`).join('') + '</ol>';
    }

    function showQuestionSources(payload) {
      const exBox = $('teach-examples');
      const sources = (payload && payload.sources) || [];
      if (!exBox || !sources.length) return;
      const links = sources.map((row) => {
        const url = String(row.url || '');
        const title = esc(row.title || url);
        if (!url.startsWith('https://')) return `<li>${title}</li>`;
        return `<li><a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${title}</a></li>`;
      }).join('');
      exBox.style.display = 'block';
      exBox.innerHTML += '<strong>From the web</strong><ul>' + links + '</ul>';
    }

    async function applyProfile() {
      const data = await api('/api/studio/teach/profile', {
        method:'POST', headers:{'content-type':'application/json'},
        body: JSON.stringify({ session_id: teachSession, profile: profileFromForm() })
      });
      renderTeach(data);
      toast('Profile adaptations applied');
    }

    let pendingPop = null;
    let pendingGame = null;

      async function popQuiz() {
      stopSpeech();
      clearSpokenActivity();
      theodoreAvatar?.setState('ask');
      pendingPop = await api('/api/studio/teach/pop-quiz', {
        method:'POST', headers:{'content-type':'application/json'},
        body: JSON.stringify({ session_id: teachSession })
      });
      const box = $('quiz-box');
      box.style.display = 'block';
      box.innerHTML = `<strong>${esc(pendingPop.prompt)}</strong>` +
        (pendingPop.choices || []).map((c, i) =>
          `<button type="button" data-i="${i}">${esc(c)}</button>`).join('') +
        `<button type="button" class="secondary mic-btn" id="quiz-mic">Speak your answer</button>` +
        `<p class="heard" id="quiz-heard"></p>`;
      let submitting = false;
      const submitQuiz = async (index) => {
        clearSpokenActivity();
        if (submitting) return;
        submitting = true;
        box.querySelectorAll('button').forEach((button) => { button.disabled = true; });
        const res = await api('/api/studio/teach/pop-answer', {
          method:'POST', headers:{'content-type':'application/json'},
          body: JSON.stringify({ session_id: teachSession, selected_index: index })
        });
        stopStudentMic();
        const passed = !!(res.result && res.result.passed);
        noteScore('quiz', passed ? 1 : 0, passed);
        theodoreAvatar?.setState(passed ? 'celebrate' : 'encouraging');
        const correction = res.correction || {};
        const correctIndex = Number.isInteger(correction.correct_index)
          ? correction.correct_index : pendingPop.correct_index;
        const correctChoice = correction.correct_choice ||
          ((pendingPop.choices || [])[correctIndex] || '');
        const selectedChoice = correction.selected_choice ||
          ((pendingPop.choices || [])[index] || '');
        const explanation = correction.explanation ||
          ('The key learning point is: ' + correctChoice);
        box.querySelectorAll('button[data-i]').forEach((b) => {
          const i = +b.dataset.i;
          if (i === correctIndex) b.classList.add('choice-correct');
          else if (i === index) b.classList.add('choice-wrong');
        });
        box.querySelector('#quiz-mic')?.remove();
        const spokenAnswer = correctChoice.replace(/[.!?]+$/, '');
        const correctionText = passed
          ? 'Correct! ' + spokenAnswer + '. ' + explanation
          : 'Not quite. You chose: ' + selectedChoice.replace(/[.!?]+$/, '') +
            '. The correct answer is: ' + spokenAnswer + '. ' + explanation;
        const panel = document.createElement('div');
        panel.className = 'quiz-correction' + (passed ? ' is-correct' : '');
        panel.setAttribute('role', 'status');
        panel.innerHTML = passed
          ? `<strong>Correct!</strong>
          <p><b>Your answer:</b> ${esc(correctChoice)}</p>
          <p><b>Why:</b> ${esc(explanation)}</p>
          <p class="heard">The course continues automatically.</p>`
          : `<strong>Not quite.</strong>
          <p><b>You chose:</b> ${esc(selectedChoice)}</p>
          <p><b>Correct answer:</b> ${esc(correctChoice)}</p>
          <p><b>Why:</b> ${esc(explanation)}</p>
          <p class="heard">Listen to the explanation. The course continues automatically.</p>`;
        box.appendChild(panel);
        toast(passed ? 'Correct' : 'Incorrect');
        $('teach-narr').textContent = correctionText;
        speakText(correctionText, null, true);
        clearAutoAdvance();
        autoAdvanceTimer = setTimeout(() => {
          autoAdvanceTimer = null;
          box.style.display = 'none';
          continueAfterActivity();
        }, narrationDwellMs(correctionText) + 5000);
      };
      box.querySelectorAll('button[data-i]').forEach((b) => {
        b.onclick = () => submitQuiz(+b.dataset.i);
      });
      const quizMic = box.querySelector('#quiz-mic');
        if (quizMic) quizMic.onclick = () => {
        listenOnce((text, isFinal) => {
          const heard = box.querySelector('#quiz-heard');
          if (heard) heard.textContent = 'Heard: ' + text;
          if (!isFinal) return;
          const index = matchSpokenChoice(text, pendingPop.choices || []);
          if (index < 0) return toast('Say the choice, or a number like 1 or 2.');
          submitQuiz(index);
        }, quizMic);
      };
      armSpokenActivity((text) => {
        const index = matchSpokenChoice(text, pendingPop.choices || []);
        if (index < 0) return false;
        submitQuiz(index);
        return true;
      }, (pendingPop.prompt || 'Quiz') + '. Choices: ' + (pendingPop.choices || []).join(', '));
    }

    async function summaryQuiz() {
      stopSpeech();
      theodoreAvatar?.setState('ask');
      const quiz = await api('/api/studio/teach/summary-quiz', {
        method:'POST', headers:{'content-type':'application/json'},
        body: JSON.stringify({ session_id: teachSession })
      });
      const answers = {};
      for (const q of (quiz.questions || [])) {
        const choice = window.prompt(q.prompt + '\\n\\n' + q.choices.map((c,i)=>`${i+1}. ${c}`).join('\\n'));
        if (choice === null) continue;
        const idx = Math.min(q.choices.length - 1, Math.max(0, (parseInt(choice, 10) || 1) - 1));
        answers[q.question_id] = idx;
      }
      const graded = await api('/api/studio/teach/summary-grade', {
        method:'POST', headers:{'content-type':'application/json'},
        body: JSON.stringify({ session_id: teachSession, answers })
      });
      toast(graded.passed
        ? `Summary passed ${graded.correct}/${graded.total}`
        : `Summary needs work ${graded.correct}/${graded.total} — review weak points`);
      noteScore('quiz', graded.total ? graded.correct / graded.total : 0, graded.passed);
      theodoreAvatar?.setState(graded.passed ? 'celebrate' : 'encouraging');
      const byId = {};
      for (const a of (graded.attempts || [])) byId[a.question_id] = a;
      const rows = (quiz.questions || []).map((q) => {
        const a = byId[q.question_id] || {};
        const picked = (q.choices || [])[a.selected_index];
        const right = (q.choices || [])[q.correct_index] || '';
        return `<div class="quiz-correction${a.correct ? ' is-correct' : ''}">
          <strong>${a.correct ? 'Correct' : 'Incorrect'} — ${esc(q.prompt)}</strong>
          ${a.correct ? '' : `<p><b>You chose:</b> ${esc(picked || 'No answer')}</p>`}
          <p><b>Correct answer:</b> ${esc(right)}</p>
          <p><b>Why:</b> ${esc(q.explanation || right)}</p>
        </div>`;
      }).join('');
      const box = $('quiz-box');
      box.style.display = 'block';
      box.innerHTML = `<strong>Summary: ${graded.correct}/${graded.total} correct</strong>${rows}
        <button type="button" class="primary" id="summary-continue">Continue</button>`;
      box.querySelector('#summary-continue').onclick = () => {
        box.style.display = 'none';
        continueAfterActivity();
      };
    }

    async function summaryQuizInteractive() {
      stopSpeech();
      theodoreAvatar?.setState('ask');
      const quiz = await api('/api/studio/teach/summary-quiz', {
        method:'POST', headers:{'content-type':'application/json'},
        body: JSON.stringify({ session_id: teachSession })
      });
      const questions = quiz.questions || [];
      const answers = {};
      const box = $('quiz-box');
      box.style.display = 'block';
      if (!questions.length) {
        box.style.display = 'none';
        continueAfterActivity();
        return;
      }
      let at = 0;

      const finish = async () => {
        clearSpokenActivity();
        stopSpeech();
        const graded = await api('/api/studio/teach/summary-grade', {
          method:'POST', headers:{'content-type':'application/json'},
          body: JSON.stringify({ session_id: teachSession, answers })
        });
        const byId = {};
        for (const attempt of (graded.attempts || [])) byId[attempt.question_id] = attempt;
        const rows = questions.map((q) => {
          const attempt = byId[q.question_id] || {};
          const picked = (q.choices || [])[attempt.selected_index] || 'No answer';
          const right = (q.choices || [])[q.correct_index] || '';
          return `<div class="quiz-correction${attempt.correct ? ' is-correct' : ''}">
            <strong>${attempt.correct ? 'Correct' : 'Incorrect'} — ${esc(q.prompt)}</strong>
            ${attempt.correct ? '' : `<p><b>You chose:</b> ${esc(picked)}</p>`}
            <p><b>Correct answer:</b> ${esc(right)}</p>
            <p><b>Why:</b> ${esc(q.explanation || right)}</p>
          </div>`;
        }).join('');
        box.innerHTML = `<strong>Summary: ${graded.correct}/${graded.total} correct</strong>${rows}
          <button type="button" class="primary" id="summary-continue-sync">Continue</button>`;
        noteScore('quiz', graded.total ? graded.correct / graded.total : 0, graded.passed);
        theodoreAvatar?.setState(graded.passed ? 'celebrate' : 'encouraging');
        const spokenFeedback = `You answered ${graded.correct} of ${graded.total} correctly. ` +
          questions.map((q) => {
            const attempt = byId[q.question_id] || {};
            const right = (q.choices || [])[q.correct_index] || '';
            return `${attempt.correct ? 'Correct' : 'Incorrect'}: ${q.prompt}. ` +
              `The answer is ${right}. ${q.explanation || ''}`;
          }).join(' ');
        speakText(spokenFeedback, null, true, 'checkpoint');
        box.querySelector('#summary-continue-sync').onclick = () => {
          stopSpeech();
          box.style.display = 'none';
          continueAfterActivity();
        };
      };

      const show = () => {
        const q = questions[at];
        const choices = q.choices || [];
        box.innerHTML = `<div class="quiz-progress">Question ${at + 1} of ${questions.length}</div>
          <strong>${esc(q.prompt)}</strong>` +
          choices.map((choice, i) => `<button type="button" data-sync-choice="${i}">${esc(choice)}</button>`).join('') +
          `<button type="button" class="secondary mic-btn" id="summary-sync-mic">Speak your answer</button>
          <p class="heard" id="summary-sync-heard"></p>`;
        const spokenQuestion = q.prompt + '. ' +
          choices.map((choice, i) => `Option ${i + 1}: ${choice}`).join('. ');
        speakText(spokenQuestion, null, true, 'checkpoint');
        const choose = (index) => {
          answers[q.question_id] = index;
          at += 1;
          if (at >= questions.length) finish();
          else show();
        };
        box.querySelectorAll('button[data-sync-choice]').forEach((button) => {
          button.onclick = () => choose(+button.dataset.syncChoice);
        });
        box.querySelector('#summary-sync-mic').onclick = () => {
          listenOnce((text, isFinal) => {
            const heard = box.querySelector('#summary-sync-heard');
            if (heard) heard.textContent = 'Heard: ' + text;
            if (!isFinal) return;
            const index = matchSpokenChoice(text, choices);
            if (index < 0) return toast('Say the choice, or a number.');
            choose(index);
          }, box.querySelector('#summary-sync-mic'));
        };
        armSpokenActivity((text) => {
          const index = matchSpokenChoice(text, choices);
          if (index < 0) return false;
          choose(index);
          return true;
        }, q.prompt + '. Choices: ' + choices.join(', '));
      };
      show();
    }

    function challengeVisual(card, revealLabel) {
      const item = card || {};
      const url = item.image_url || '';
      const glyph = item.glyph || '';
      const label = item.label || item.alt || item.name || '';
      let face = '';
      if (url) face += `<img alt="${esc(item.alt || label)}" src="${esc(url)}">`;
      if (glyph) face += `<span class="challenge-glyph">${esc(glyph)}</span>`;
      if (revealLabel || (!url && !glyph)) face += `<span class="challenge-label">${esc(label)}</span>`;
      return `<span class="challenge-face">${face}</span>`;
    }

    async function gradeVisual(response) {
      clearSpokenActivity();
      const res = await api('/api/studio/teach/game-grade', {
        method:'POST', headers:{'content-type':'application/json'},
        body: JSON.stringify({
          session_id: teachSession,
          challenge: pendingGame,
          response: response
        })
      });
      learningCheckOpen = false;
      stopStudentMic();
      toast(res.feedback || (res.passed ? 'Game passed' : 'Try again'));
      noteScore('game', res.score, res.passed);
      theodoreAvatar?.setState(res.passed ? 'celebrate' : 'encouraging');
      const box = $('game-box');
      if (box) box.style.display = 'none';
      continueAfterActivity();
    }

    function paintVisualChallenge(box, kind, payload) {
      const lead = (lastTeachPayload && lastTeachPayload.activity_checkpoint && lastTeachPayload.activity_checkpoint.prompt) || '';
      const head = `<strong>${esc(pendingGame.prompt || 'Your turn.')}</strong>` +
        (lead ? `<p class="heard">${esc(lead)}</p>` : '');
      if (kind === 'image_to_word' && payload.image && (payload.options || []).length) {
        box.innerHTML = head +
          `<div class="challenge-hero">${challengeVisual(payload.image, false)}</div>` +
          `<div class="challenge-grid">` +
          payload.options.map((choice, i) =>
            `<button type="button" class="challenge-choice" data-i="${i}">${esc(choice)}</button>`).join('') +
          `</div><button type="button" class="secondary mic-btn" id="game-mic">Speak your answer</button><p class="heard" id="game-heard"></p>`;
        const choose = (index) => gradeVisual({ selected_index: index });
        box.querySelectorAll('button[data-i]').forEach((b) => { b.onclick = () => choose(+b.dataset.i); });
        const mic = box.querySelector('#game-mic');
        if (mic) mic.onclick = () => listenOnce((text, isFinal) => {
          const heard = box.querySelector('#game-heard');
          if (heard) heard.textContent = 'Heard: ' + text;
          if (!isFinal) return;
          const index = matchSpokenChoice(text, payload.options);
          if (index < 0) return toast('Say the word, or a number like 1 or 2.');
          choose(index);
        }, mic);
        armSpokenActivity((text) => {
          const index = matchSpokenChoice(text, payload.options);
          if (index < 0) return false;
          choose(index);
          return true;
        }, (pendingGame.prompt || 'Say the matching word') + '. Choices: ' + payload.options.join(', '));
        return true;
      }
      if (kind === 'word_to_image' && (payload.images || []).length) {
        box.innerHTML = head + `<div class="challenge-grid">` +
          payload.images.map((card) =>
            `<button type="button" class="challenge-choice" data-id="${esc(card.id)}">${challengeVisual(card, false)}</button>`).join('') +
          `</div>`;
        box.querySelectorAll('button[data-id]').forEach((b) => {
          b.onclick = () => gradeVisual({ selected_id: b.dataset.id });
        });
        const pictureLabels = payload.images.map((card) => card.label || card.alt || card.name || card.id || '');
        armSpokenActivity((text) => {
          const index = matchSpokenChoice(text, pictureLabels);
          if (index < 0) return false;
          gradeVisual({ selected_id: payload.images[index].id });
          return true;
        }, pendingGame.prompt || 'Say the picture that matches.');
        return true;
      }
      if (kind === 'hotspot' && (payload.regions || []).length) {
        const picture = payload.image ? `<div class="challenge-hero">${challengeVisual(payload.image, false)}</div>` : '';
        box.innerHTML = head + picture + `<div class="challenge-grid">` +
          payload.regions.map((region) =>
            `<button type="button" class="challenge-choice" data-region="${esc(region.id)}">${esc(region.name || region.id)}</button>`).join('') +
          `</div>`;
        box.querySelectorAll('button[data-region]').forEach((b) => {
          b.onclick = () => gradeVisual({ region: b.dataset.region });
        });
        const regionNames = payload.regions.map((region) => region.name || region.id);
        armSpokenActivity((text) => {
          const index = matchSpokenChoice(text, regionNames);
          if (index < 0) return false;
          gradeVisual({ region: payload.regions[index].id });
          return true;
        }, (pendingGame.prompt || 'Say the spot') + '. Spots: ' + regionNames.join(', '));
        return true;
      }
      if (kind === 'classify' && (payload.items || []).length && (payload.categories || []).length) {
        box.innerHTML = head + payload.items.map((item) =>
          `<div class="challenge-row"><span>${challengeVisual(item, true)}</span>
            <select data-item="${esc(item.id)}">` +
            `<option value="">Choose a group</option>` +
            payload.categories.map((name) => `<option value="${esc(name)}">${esc(name)}</option>`).join('') +
          `</select></div>`).join('') +
          `<button type="button" class="primary" id="visual-submit">Check groups</button>`;
        box.querySelector('#visual-submit').onclick = () => {
          const assignments = {};
          let missing = false;
          box.querySelectorAll('select[data-item]').forEach((sel) => {
            if (!sel.value) missing = true;
            assignments[sel.dataset.item] = sel.value;
          });
          if (missing) return toast('Put every item in a group first.');
          gradeVisual({ assignments: assignments });
        };
        return true;
      }
      if ((kind === 'sort' || kind === 'picture_order')) {
        const rows = kind === 'picture_order' ? (payload.cards_shown || []) : (payload.items || []);
        const shown = kind === 'sort'
          ? (payload.order_shown || []).map((id) => rows.find((row) => row.id === id)).filter(Boolean)
          : rows;
        if (shown.length < 2) return false;
        box.innerHTML = head +
          `<p class="heard">Click the items in order.</p><div class="challenge-grid" id="visual-order"></div>` +
          `<button type="button" class="primary" id="visual-submit">Check order</button>` +
          `<button type="button" id="visual-reset">Reset</button>`;
        const picked = [];
        const list = box.querySelector('#visual-order');
        function paint() {
          list.innerHTML = shown.map((row) => {
            const used = picked.includes(row.id);
            return `<button type="button" class="challenge-choice" data-id="${esc(row.id)}" ${used ? 'disabled' : ''}>${challengeVisual(row, true)}</button>`;
          }).join('') + (picked.length
            ? `<div class="heard">Order: ${picked.map((id) => esc((shown.find((row) => row.id === id) || {}).label || id)).join(' → ')}</div>`
            : '');
          list.querySelectorAll('button[data-id]').forEach((b) => {
            b.onclick = () => { if (!picked.includes(b.dataset.id)) { picked.push(b.dataset.id); paint(); } };
          });
        }
        paint();
        box.querySelector('#visual-reset').onclick = () => { picked.length = 0; paint(); };
        box.querySelector('#visual-submit').onclick = () => {
          if (picked.length !== shown.length) return toast('Put every item in order first.');
          gradeVisual({ ordered_ids: picked.slice() });
        };
        const orderLabels = shown.map((row) => row.label || row.name || row.id || '');
        armSpokenActivity((text) => {
          if (saidCheck(text)) {
            if (picked.length !== shown.length) return false;
            gradeVisual({ ordered_ids: picked.slice() });
            return true;
          }
          const index = matchSpokenChoice(text, orderLabels);
          if (index < 0 || picked.includes(shown[index].id)) return false;
          picked.push(shown[index].id);
          paint();
          return true;
        }, (pendingGame.prompt || 'Say the items in order') + '. Items: ' + orderLabels.join(', '));
        return true;
      }
      if (kind === 'label_placement' && (payload.targets || []).length && (payload.labels || []).length) {
        const picture = payload.image ? `<div class="challenge-hero">${challengeVisual(payload.image, false)}</div>` : '';
        box.innerHTML = head + picture + payload.targets.map((target) =>
          `<div class="challenge-row"><span>${esc(target.name || target.id)}</span>
            <select data-target="${esc(target.id)}">` +
            `<option value="">Choose a label</option>` +
            payload.labels.map((label) => `<option value="${esc(label)}">${esc(label)}</option>`).join('') +
          `</select></div>`).join('') +
          `<button type="button" class="primary" id="visual-submit">Check labels</button>`;
        box.querySelector('#visual-submit').onclick = () => {
          const placements = {};
          let missing = false;
          box.querySelectorAll('select[data-target]').forEach((sel) => {
            if (!sel.value) missing = true;
            placements[sel.dataset.target] = sel.value;
          });
          if (missing) return toast('Place a label on every spot first.');
          gradeVisual({ placements: placements });
        };
        return true;
      }
      if (kind === 'spot_difference') {
        const spots = (payload.differences || []).concat(payload.decoys || []).slice();
        if (!spots.length) return false;
        for (let i = spots.length - 1; i > 0; i--) {
          const j = Math.floor(Math.random() * (i + 1));
          const swap = spots[i];
          spots[i] = spots[j];
          spots[j] = swap;
        }
        const sides = [payload.left, payload.right].filter(Boolean);
        box.innerHTML = head +
          `<div class="challenge-grid">` +
          sides.map((card) => `<div class="challenge-choice">${challengeVisual(card, false)}</div>`).join('') +
          `</div><p class="heard">Select every difference.</p><div class="challenge-grid" id="spot-list">` +
          spots.map((spot) =>
            `<button type="button" class="challenge-choice" data-spot="${esc(spot.id)}">${esc(spot.region || spot.id)}</button>`).join('') +
          `</div><button type="button" class="primary" id="visual-submit">Check differences</button>`;
        const picked = [];
        box.querySelectorAll('button[data-spot]').forEach((b) => {
          b.onclick = () => {
            const id = b.dataset.spot;
            const at = picked.indexOf(id);
            if (at >= 0) picked.splice(at, 1);
            else picked.push(id);
            b.classList.toggle('is-picked', picked.includes(id));
          };
        });
        box.querySelector('#visual-submit').onclick = () => {
          if (!picked.length) return toast('Select at least one difference.');
          gradeVisual({ selected_ids: picked.slice() });
        };
        const spotNames = spots.map((spot) => spot.region || spot.id || '');
        armSpokenActivity((text) => {
          if (saidCheck(text)) {
            if (!picked.length) return false;
            gradeVisual({ selected_ids: picked.slice() });
            return true;
          }
          const index = matchSpokenChoice(text, spotNames);
          if (index < 0) return false;
          const id = spots[index].id;
          const button = box.querySelector(`button[data-spot="${id}"]`);
          if (button) button.click();
          return true;
        }, (pendingGame.prompt || 'Say each difference, then say check') + '. Differences: ' + spotNames.join(', '));
        return true;
      }
      if (kind === 'memory_pairs' && (payload.cards_shown || []).length) {
        const cards = payload.cards_shown;
        box.innerHTML = head +
          `<p class="heard">Pick two cards that belong together.</p><div class="challenge-grid" id="memory-grid"></div>` +
          `<button type="button" id="visual-reset">Reset</button>` +
          `<button type="button" class="primary" id="visual-submit">Check pairs</button>`;
        const matches = [];
        let first = '';
        const grid = box.querySelector('#memory-grid');
        function paint() {
          grid.innerHTML = cards.map((card) => {
            const used = matches.some((pair) => pair[0] === card.id || pair[1] === card.id);
            const on = first === card.id;
            return `<button type="button" class="challenge-choice${on ? ' is-picked' : ''}" data-id="${esc(card.id)}" ${used ? 'disabled' : ''}>${challengeVisual(card, false)}</button>`;
          }).join('');
          grid.querySelectorAll('button[data-id]').forEach((b) => {
            b.onclick = () => {
              const id = b.dataset.id;
              if (!first) { first = id; paint(); return; }
              if (first === id) { first = ''; paint(); return; }
              matches.push([first, id]);
              first = '';
              paint();
            };
          });
        }
        paint();
        box.querySelector('#visual-reset').onclick = () => { matches.length = 0; first = ''; paint(); };
        box.querySelector('#visual-submit').onclick = () => {
          if (!matches.length) return toast('Match at least one pair first.');
          gradeVisual({ matches: matches.map((pair) => pair.slice()) });
        };
        return true;
      }
      return false;
    }

    async function playGame() {
      stopSpeech();
      clearSpokenActivity();
      theodoreAvatar?.setState('ask');
      learningCheckOpen = true;
      try {
        pendingGame = await api('/api/studio/teach/game', {
          method:'POST', headers:{'content-type':'application/json'},
          body: JSON.stringify({ session_id: teachSession })
        });
      } catch (error) {
        learningCheckOpen = false;
        throw error;
      }
      const box = $('game-box');
      box.style.display = 'block';
      const kind = pendingGame.kind || (pendingGame.payload && pendingGame.payload.kind) || '';
      const payload = pendingGame.payload || {};
      const lead = (lastTeachPayload && lastTeachPayload.activity_checkpoint && lastTeachPayload.activity_checkpoint.prompt) || '';
      speakText((lead ? lead + ' ' : '') + (pendingGame.prompt || 'Your turn.'), null, true, 'game');
      if (paintVisualChallenge(box, kind, payload)) {
        if (!spokenActivity) armSpokenActivity(() => false, pendingGame.prompt || 'Use the game on the screen.');
        return;
      }
      // Multimodal kits use order_steps (reorder) as well as match_term (pick one).
      if (kind === 'order_steps' || (payload.steps_shown && payload.steps_shown.length)) {
        const steps = (payload.steps_shown || []).slice();
        box.innerHTML = `<strong>${esc(pendingGame.prompt)}</strong>
          <p style="font-size:12px;opacity:.85;margin:8px 0;">Click steps in the correct order, or say them (first → last).</p>
          <div id="order-steps"></div>
          <button type="button" id="order-submit" class="primary" style="margin-top:8px;">Check order</button>
          <button type="button" id="order-reset" style="margin-top:8px;">Reset</button>
          <button type="button" class="secondary mic-btn" id="game-mic">Speak the next step</button>
          <p class="heard" id="game-heard"></p>`;
        const list = box.querySelector('#order-steps');
        const picked = [];
        function paint() {
          list.innerHTML = steps.map((s, i) => {
            const used = picked.includes(i);
            return `<button type="button" data-si="${i}" ${used ? 'disabled' : ''} style="display:block;width:100%;text-align:left;margin:4px 0;opacity:${used ? 0.45 : 1}">${esc(s)}</button>`;
          }).join('') + (picked.length
            ? `<div style="margin-top:8px;font-size:12px;">Order: ${picked.map((i) => esc(steps[i])).join(' → ')}</div>`
            : '');
          list.querySelectorAll('button[data-si]').forEach((b) => {
            b.onclick = () => {
              const i = +b.dataset.si;
              if (!picked.includes(i)) { picked.push(i); paint(); }
            };
          });
        }
        paint();
        box.querySelector('#order-reset').onclick = () => { picked.length = 0; paint(); };
        const orderMic = box.querySelector('#game-mic');
        if (orderMic) orderMic.onclick = () => {
          listenOnce((text, isFinal) => {
            const heard = box.querySelector('#game-heard');
            if (heard) heard.textContent = 'Heard: ' + text;
            if (!isFinal) return;
            const before = picked.length;
            const said = spokenWords(text);
            const hits = [];
            steps.forEach((step, index) => {
              if (picked.includes(index)) return;
              const words = spokenWords(step).split(' ').filter((word) => word.length > 3);
              if (!words.length) return;
              const overlap = words.filter((word) => said.includes(word)).length;
              if (overlap >= Math.min(2, words.length) || (words.length === 1 && said.includes(words[0]))) {
                const pos = said.indexOf(words[0]);
                hits.push({ index, pos: pos < 0 ? 999 : pos });
              }
            });
            hits.sort((a, b) => a.pos - b.pos);
            hits.forEach((hit) => { if (!picked.includes(hit.index)) picked.push(hit.index); });
            paint();
            if (picked.length === before) toast('Say the next step the way it is written.');
          }, orderMic);
        };
        box.querySelector('#order-submit').onclick = async () => {
          if (picked.length !== steps.length) {
            toast('Pick every step in order first');
            return;
          }
          clearSpokenActivity();
          const ordered = picked.map((i) => steps[i]);
          const res = await api('/api/studio/teach/game-grade', {
            method:'POST', headers:{'content-type':'application/json'},
            body: JSON.stringify({
              session_id: teachSession,
              challenge: pendingGame,
              response: { ordered_steps: ordered }
            })
          });
          learningCheckOpen = false;
          toast(res.feedback || (res.passed ? 'Game passed' : 'Try again'));
          noteScore('game', res.score, res.passed);
          theodoreAvatar?.setState(res.passed ? 'celebrate' : 'encouraging');
          box.style.display = 'none';
          clearSpokenActivity();
          continueAfterActivity();
        };
        armSpokenActivity((text) => {
          if (saidCheck(text)) {
            const submit = box.querySelector('#order-submit');
            if (submit) submit.click();
            return true;
          }
          const before = picked.length;
          const said = spokenWords(text);
          const hits = [];
          steps.forEach((step, index) => {
            if (picked.includes(index)) return;
            const words = spokenWords(step).split(' ').filter((word) => word.length > 3);
            if (!words.length) return;
            const overlap = words.filter((word) => said.includes(word)).length;
            if (overlap >= Math.min(2, words.length) || (words.length === 1 && said.includes(words[0]))) {
              const pos = said.indexOf(words[0]);
              hits.push({ index, pos: pos < 0 ? 999 : pos });
            }
          });
          hits.sort((a, b) => a.pos - b.pos);
          hits.forEach((hit) => { if (!picked.includes(hit.index)) picked.push(hit.index); });
          paint();
          return picked.length > before;
        }, (pendingGame.prompt || 'Say the steps in order') + '. Steps: ' + steps.join(', '));
        return;
      }
      const opts = payload.options || [];
      box.innerHTML = `<strong>${esc(pendingGame.prompt)}</strong>` +
        opts.map((c, i) => `<button type="button" data-i="${i}">${esc(c)}</button>`).join('') +
        `<button type="button" class="secondary mic-btn" id="game-mic">Speak your answer</button>` +
        `<p class="heard" id="game-heard"></p>`;
      const submitGame = async (index) => {
        clearSpokenActivity();
        const res = await api('/api/studio/teach/game-grade', {
          method:'POST', headers:{'content-type':'application/json'},
          body: JSON.stringify({
            session_id: teachSession,
            challenge: pendingGame,
            response: { selected_index: index }
          })
        });
        learningCheckOpen = false;
        stopStudentMic();
        toast(res.feedback || (res.passed ? 'Game passed' : 'Try again'));
        noteScore('game', res.score, res.passed);
        theodoreAvatar?.setState(res.passed ? 'celebrate' : 'encouraging');
        box.style.display = 'none';
        continueAfterActivity();
      };
      box.querySelectorAll('button[data-i]').forEach((b) => {
        b.onclick = () => submitGame(+b.dataset.i);
      });
      const gameMic = box.querySelector('#game-mic');
      if (gameMic) gameMic.onclick = () => {
        listenOnce((text, isFinal) => {
          const heard = box.querySelector('#game-heard');
          if (heard) heard.textContent = 'Heard: ' + text;
          if (!isFinal) return;
          const index = matchSpokenChoice(text, opts);
          if (index < 0) return toast('Say the choice, or a number like 1 or 2.');
          submitGame(index);
        }, gameMic);
      };
      armSpokenActivity((text) => {
        const index = matchSpokenChoice(text, opts);
        if (index < 0) return false;
        submitGame(index);
        return true;
      }, (pendingGame.prompt || 'Say your answer') + '. Choices: ' + opts.join(', '));
    }

    function clearPlaybackWatchdog() {
      if (playbackWatchdog) {
        clearTimeout(playbackWatchdog);
        playbackWatchdog = null;
      }
    }

    function clearStallTimer() {
      if (stallTimer) {
        clearTimeout(stallTimer);
        stallTimer = null;
      }
    }

    function nextPlayToken() {
      playToken += 1;
      clearPlaybackWatchdog();
      clearStallTimer();
      return playToken;
    }

    function armDurationWatchdog(gen, token, durationMs) {
      clearPlaybackWatchdog();
      const ms = Number(durationMs);
      if (!Number.isFinite(ms) || ms <= 0 || gen !== speechGen || token !== playToken) return;
      playbackWatchdog = setTimeout(() => {
        playbackWatchdog = null;
        if (gen !== speechGen || token !== playToken) return;
        if (serverAudio) {
          try { serverAudio.onended = null; serverAudio.pause(); } catch (_) {}
        }
        if (window.speechSynthesis) {
          try { window.speechSynthesis.cancel(); } catch (_) {}
        }
        if (typeof finishUtterance === 'function') finishUtterance(gen, token);
      }, ms + WATCHDOG_GRACE_MS);
    }

    function isBlobUrl(src) {
      return typeof src === 'string' && src.indexOf('blob:') === 0;
    }

    function releaseAudioUrl(src) {
      // Remote manifest URLs must stay cached for the next slide. Only blob
      // URLs we created for a live POST /api/studio/tts clip are revocable.
      if (!isBlobUrl(src)) return;
      try { URL.revokeObjectURL(src); } catch (_) {}
    }

    async function keepLessonAudioOnSpeakers() {
      const audio = serverAudio;
      if (!audio || audio.ended) return;
      audio.volume = 1;
      if (typeof audio.setSinkId === 'function') {
        try { await audio.setSinkId(''); } catch (_) {}
      }
      if (audio.paused && audio.currentTime > 0) {
        try { await audio.play(); } catch (_) {}
      }
    }
    if (navigator.mediaDevices && navigator.mediaDevices.addEventListener) {
      navigator.mediaDevices.addEventListener('devicechange', () => {
        keepLessonAudioOnSpeakers();
      });
    }

    function detachServerAudio() {
      clearStallTimer();
      const audio = serverAudio;
      if (!audio) return;
      serverAudio = null;
      try {
        audio.onended = null;
        audio.onerror = null;
        audio.onstalled = null;
        audio.onloadedmetadata = null;
        audio.onplaying = null;
        audio.ontimeupdate = null;
        audio.pause();
        audio.removeAttribute('src');
        audio.load();
      } catch (_) {}
    }

    function manifestClip(ttsMeta) {
      if (!ttsMeta || !ttsMeta.audio_url) return null;
      const durationMs = Number(ttsMeta.duration_ms);
      if (!Number.isFinite(durationMs) || durationMs <= 0) return null;
      return { url: String(ttsMeta.audio_url), durationMs: durationMs };
    }

    function nextSlideAudioUrl(ttsMeta) {
      if (!ttsMeta) return '';
      return String(ttsMeta.next_audio_url || ttsMeta.next_slide_audio_url || '').trim();
    }

    function preloadNextSlideAudio(url) {
      const next = String(url || '').trim();
      if (!next) return;
      if (preloadedSlideUrl === next && preloadedSlideAudio) return;
      preloadedSlideUrl = next;
      const audio = new Audio();
      audio.preload = 'auto';
      audio.src = next;
      try { audio.load(); } catch (_) {}
      preloadedSlideAudio = audio;
    }

    function takePreloadedAudio(url) {
      if (preloadedSlideAudio && preloadedSlideUrl === url) {
        const audio = preloadedSlideAudio;
        preloadedSlideAudio = null;
        preloadedSlideUrl = '';
        return audio;
      }
      const audio = new Audio();
      audio.preload = 'auto';
      audio.src = url;
      return audio;
    }

    function stopSpeech() {
      speechGen += 1;
      playToken += 1;
      speechHold = false;
      talkReplyActive = false;
      finishUtterance = null;
      clearAutoAdvance();
      clearPlaybackWatchdog();
      clearStallTimer();
      visualTimers.forEach((timer) => clearTimeout(timer));
      visualTimers = [];
      if (window.speechSynthesis) window.speechSynthesis.cancel();
      detachServerAudio();
      releaseAudioUrl(neuralObjectUrl);
      neuralObjectUrl = null;
      theodoreAvatar?.stopSpeaking();
      document.body.classList.remove('is-speaking');
    }

    let liveVoiceStart = null;
    function lessonNarration(kind) {
      return !kind || kind === 'course-resume' || kind === 'backup';
    }
    function speakText(text, ttsMeta, holdLesson, kind) {
      if (sampleIsComplete()) return;
      if (lessonLife.isAway()) return;
      if (learningHold && kind !== 'guard' && kind !== 'learn-check') return;
      if (learningCheckOpen && kind !== 'learn-check' && kind !== 'guard' && kind !== 'checkpoint') return;
      if (kind !== 'adapt' && kind !== 'adapt-resume' && kind !== 'guard') attentionResume = '';
      if (lecturePaused && !holdLesson) return;
      if (window.__THEODORE_LIVE_AUDIO_ACTIVE__ && !window.__THEODORE_LIVE_AUDIO_HOLD__) {
        if (kind !== 'talk') {
          if (lessonNarration(kind)) syncVoiceToSlide(lastTeachPayload);
          return;
        }
        window.TheodoreLiveAudio?.pauseRecognition();
      }
      stopSpeech();
      lastSpeakRequestAt = Date.now();
      const spoken = text || '';
      const gen = speechGen;
      const talkReply = kind === 'talk';
      speechHold = !!holdLesson;
      talkReplyActive = !!holdLesson && talkReply;
      // Silent mode still walks the slides. Pause is the only thing that holds.
      const speakToggle = $('auto-speak');
      if (!holdLesson && speakToggle && !speakToggle.checked) {
        startEstimatedVisualTimeline(narrationDwellMs(spoken));
        scheduleAutoAdvance(narrationDwellMs(spoken));
        return;
      }
      if (holdLesson && speakToggle && !speakToggle.checked) {
        speechHold = false;
        talkReplyActive = false;
        if (kind === 'adapt' && attentionResume) {
          const next = attentionResume;
          attentionResume = '';
          speakText(next, null, false, 'adapt-resume');
        }
        return;
      }
      if (!holdLesson && lessonNarration(kind) && kind !== 'backup' && window.TheodoreLiveAudio?.start) {
        lastSpeakRequestAt = Date.now();
        if (!liveVoiceStart) {
          liveVoiceStart = (async () => {
            const waitUntilLive = async () => {
              const until = Date.now() + 4000;
              while (!window.__THEODORE_LIVE_AUDIO_ACTIVE__ && Date.now() < until) {
                await new Promise((resolve) => setTimeout(resolve, 200));
              }
            };
            let started = await window.TheodoreLiveAudio.start();
            if (started === false && !window.__THEODORE_LIVE_AUDIO_ACTIVE__) {
              await new Promise((resolve) => setTimeout(resolve, 700));
              if (!window.__THEODORE_LIVE_AUDIO_ACTIVE__) started = await window.TheodoreLiveAudio.start();
            }
            if (started !== false) await waitUntilLive();
            return !!window.__THEODORE_LIVE_AUDIO_ACTIVE__;
          })().finally(() => { liveVoiceStart = null; });
        }
        const startGen = speechGen;
        liveVoiceStart.then((ok) => {
          if (!ok && startGen === speechGen) speakText(text, ttsMeta, holdLesson, 'backup');
        });
        return;
      }
      let settled = false;
      finishUtterance = (genCheck, tokenCheck) => {
        if (settled || genCheck !== speechGen || tokenCheck !== playToken) return;
        settled = true;
        clearPlaybackWatchdog();
        clearStallTimer();
        if (holdLesson) {
          speechHold = false;
          talkReplyActive = false;
          theodoreAvatar?.stopSpeaking();
          if (kind === 'adapt' && attentionResume) {
            const next = attentionResume;
            attentionResume = '';
            speakText(next, null, false, 'adapt-resume');
          }
          if (kind === 'talk') window.TheodoreLiveAudio?.resumeRecognition();
          return;
        }
        onNarrationEnded(genCheck);
      };
      // The voice picked in the account menu wins over the baked course narration: a company voice plays its
      // pre-rendered clip (any miss falls back to the edge voice, then the course voice); an edge voice is rendered
      // on demand in that voice. Nothing is spoken by the browser's own voice unless every server path fails.
      const choice = (!holdLesson && window.SalaVoiceChoice) ? window.SalaVoiceChoice.chosen() : { custom: '', edge: '' };
      const choiceLang = (ttsMeta && ttsMeta.language) || teachLanguage || 'en';
      const choiceEdge = (!holdLesson && window.SalaVoiceChoice) ? window.SalaVoiceChoice.edgeVoiceFor(choiceLang) : '';
      const picked = !!(choice.custom || choiceEdge);
      const clip = (holdLesson || picked) ? null : manifestClip(ttsMeta);
      const upcoming = picked ? '' : nextSlideAudioUrl(ttsMeta);
      narrationGenderOverride = '';
      if (choice.custom) {
        // No clip yet (or any playback problem): speak with a server voice of the SAME gender as the chosen company voice.
        const withCustomGender = () => window.SalaVoiceChoice.customGender().catch(() => '').then((g) => {
          narrationGenderOverride = g || '';
          if (gen === speechGen && !settled) playOnDemand();
        });
        window.SalaVoiceChoice.cloneClipUrl(choiceLang, spoken).then((url) => {
          if (gen !== speechGen || settled) return;
          if (url) playManifest(url, 0, 0);
          else withCustomGender();
        }).catch(() => { if (gen === speechGen && !settled) withCustomGender(); });
      } else if (clip) playManifest(clip.url, clip.durationMs, 0);
      else playOnDemand();
      if (upcoming && (!clip || upcoming !== clip.url)) preloadNextSlideAudio(upcoming);

      function playManifest(url, durationMs, attempt) {
        if (gen !== speechGen || settled) return;
        const token = nextPlayToken();
        const bound = bindClip(takePreloadedAudio(url), token, durationMs, () => {
          if (gen !== speechGen || settled) return;
          if (attempt < 1) playManifest(url, durationMs, attempt + 1);
          else playOnDemand();
        });
        theodoreAvatar?.speak(spoken, bound.audio);
        startClip(bound);
      }

      function playOnDemand() {
        if (gen !== speechGen || settled) return;
        clearPlaybackWatchdog();
        detachServerAudio();
        fetchLockedVoice(spoken, ttsMeta).then((src) => {
          if (gen !== speechGen || settled) {
            releaseAudioUrl(src);
            return;
          }
          releaseAudioUrl(neuralObjectUrl);
          neuralObjectUrl = src;
          const token = nextPlayToken();
          const bound = bindClip(takePreloadedAudio(src), token, 0, () => playDevice());
          theodoreAvatar?.speak(spoken, bound.audio);
          startClip(bound);
        }).catch(() => {
          if (gen === speechGen && !settled) playDevice();
        });
      }

      function playDevice() {
        if (gen !== speechGen || settled) return;
        const token = nextPlayToken();
        detachServerAudio();
        releaseAudioUrl(neuralObjectUrl);
        neuralObjectUrl = null;
        if (!window.speechSynthesis || !spoken) {
          theodoreAvatar?.stopSpeaking();
          if (!holdLesson) armDurationWatchdog(gen, token, narrationDwellMs(spoken));
          return;
        }
        const u = new SpeechSynthesisUtterance(spoken);
        u.lang = recognitionLang();
        u.volume = 1;
        const voices = window.speechSynthesis.getVoices ? window.speechSynthesis.getVoices() : [];
        const wanted = String(u.lang || 'en').toLowerCase();
        const primary = wanted.split('-')[0];
        const exact = (voices || []).filter((voice) => {
          const tag = String(voice.lang || '').toLowerCase().replace(/_/g, '-');
          return tag === wanted || tag.startsWith(wanted);
        });
        // zh-HK must not fall through to the first zh-CN voice.
        const same = exact.length || wanted.startsWith('zh-')
          ? exact
          : (voices || []).filter((voice) => String(voice.lang || '').toLowerCase().split('-')[0] === primary);
        if (!same.length && primary !== 'en') {
          setLearningStatus('This device has no ' + languageLabel(teachLanguage || primary) + ' voice. Allow the lesson voice to load.');
          theodoreAvatar?.stopSpeaking();
          if (!holdLesson) armDurationWatchdog(gen, token, narrationDwellMs(spoken));
          return;
        }
        const maleName = /male|\b(guy|daniel|alex|fred|aaron|oliver|james|brian|arthur|eric)\b/i;
        const femaleName = /female|\b(samantha|aria|victoria|karen|allison|ava|susan|zoe|moira|tessa|fiona|serena|jenny)\b/i;
        const tutorFemale = courseVoiceGender !== 'male';
        const pool = tutorFemale ? same.filter((voice) => !maleName.test(voice.name || '')) : same;
        const candidates = pool.length ? pool : same;
        const namePattern = tutorFemale ? femaleName : maleName;
        const named = candidates.find((voice) => namePattern.test(voice.name || ''));
        const chosen = named || candidates[0];
        if (chosen) u.voice = chosen;
        if (tutorFemale) u.rate = 0.96;
        u.onboundary = (event) => {
          const charIndex = event.charIndex || 0;
          theodoreAvatar?.speechBoundary(charIndex);
          if (!holdLesson && visualTimeline && spoken.length) {
            syncVisualTimeline((Number(visualTimeline.duration_s) || 1) * charIndex / spoken.length);
          }
        };
        u.onstart = () => { lastPlaybackAt = Date.now(); };
        u.onend = () => {
          document.body.classList.remove('is-speaking');
          finishUtterance(gen, token);
        };
        u.onerror = () => {
          theodoreAvatar?.stopSpeaking();
          if (!holdLesson && gen === speechGen && token === playToken && !settled) {
            armDurationWatchdog(gen, token, narrationDwellMs(spoken));
          }
        };
        if (!holdLesson) armDurationWatchdog(gen, token, narrationDwellMs(spoken));
        theodoreAvatar?.speak(spoken);
        document.body.classList.add('is-speaking');
        try { window.speechSynthesis.speak(u); }
        catch (_) { u.onerror(); }
      }

      function bindClip(audio, token, durationMs, onFail) {
        detachServerAudio();
        serverAudio = audio;
        audio.volume = 1;
        let failed = false;
        let knownDurationMs = Number(durationMs) || 0;
        const alreadyMs = Number(audio.duration) * 1000;
        if (Number.isFinite(alreadyMs) && alreadyMs > 0 && alreadyMs !== Infinity) {
          knownDurationMs = alreadyMs;
        }
        const fail = () => {
          if (failed || settled || gen !== speechGen || token !== playToken) return;
          if (audio !== serverAudio) return;
          failed = true;
          clearPlaybackWatchdog();
          clearStallTimer();
          onFail();
        };
        const armForClip = () => {
          if (holdLesson || gen !== speechGen || token !== playToken || settled) return;
          const elapsed = (Number(audio.currentTime) || 0) * 1000;
          if (knownDurationMs > 0) {
            armDurationWatchdog(gen, token, Math.max(250, knownDurationMs - elapsed));
            return;
          }
          if (!playbackWatchdog) armDurationWatchdog(gen, token, narrationDwellMs(spoken));
        };
        audio.onloadedmetadata = () => {
          const ms = Number(audio.duration) * 1000;
          if (!Number.isFinite(ms) || ms <= 0 || ms === Infinity) return;
          knownDurationMs = ms;
          if (!audio.paused) armForClip();
        };
        audio.onplaying = () => {
          lastPlaybackAt = Date.now();
          clearStallTimer();
          armForClip();
          document.body.classList.add('is-speaking');
        };
        audio.ontimeupdate = () => {
          clearStallTimer();
          if (!holdLesson) syncVisualTimeline(visualTimeForAudio(audio));
        };
        audio.onstalled = () => {
          const at = audio.currentTime || 0;
          clearStallTimer();
          stallTimer = setTimeout(() => {
            stallTimer = null;
            if (audio !== serverAudio || gen !== speechGen || token !== playToken || settled) return;
            if (audio.currentTime > at + 0.05) return;
            fail();
          }, STALL_RECOVER_MS);
        };
        audio.onended = () => {
          document.body.classList.remove('is-speaking');
          if (!holdLesson) {
            syncVisualTimeline(Number(visualTimeline?.duration_s) || Number(audio.duration) || 0);
          }
          finishUtterance(gen, token);
        };
        audio.onerror = () => fail();
        return { audio: audio, fail: fail };
      }

      function startClip(bound) {
        let started = false;
        const audio = bound.audio;
        const previousPlaying = audio.onplaying;
        audio.onplaying = () => {
          started = true;
          if (typeof previousPlaying === 'function') previousPlaying();
        };
        let pending = null;
        try { pending = audio.play(); }
        catch (_) { bound.fail(); return; }
        clearStallTimer();
        stallTimer = setTimeout(() => {
          stallTimer = null;
          if (started || audio !== serverAudio || gen !== speechGen || settled) return;
          bound.fail();
        }, STALL_RECOVER_MS);
        if (pending && typeof pending.catch === 'function') pending.catch(() => bound.fail());
      }
    }

    function startEstimatedVisualTimeline(durationMs) {
      visualTimers.forEach((timer) => clearTimeout(timer));
      visualTimers = [];
      if (!visualTimeline || !Array.isArray(visualTimeline.cues)) return;
      const authored = Math.max(0.001, Number(visualTimeline.duration_s) || 1);
      const actual = Math.max(1, Number(durationMs) || authored * 1000);
      syncVisualTimeline(0, true);
      visualTimeline.cues.forEach((cue) => {
        const delay = Math.max(0, (Number(cue.start_s) || 0) / authored * actual);
        visualTimers.push(setTimeout(() => syncVisualTimeline(Number(cue.start_s) || 0), delay));
      });
    }

    function visualTimeForAudio(audio) {
      const at = Math.max(0, Number(audio && audio.currentTime) || 0);
      const audioDuration = Number(audio && audio.duration);
      const authored = Number(visualTimeline && visualTimeline.duration_s);
      if (
        Number.isFinite(audioDuration) && audioDuration > 0 &&
        Number.isFinite(authored) && authored > 0
      ) {
        return at / audioDuration * authored;
      }
      return at;
    }

    function fetchLockedVoice(text, ttsMeta) {
      const language = (ttsMeta && ttsMeta.language) || teachLanguage || 'en';
      const gender = narrationGenderOverride || courseVoiceGender || (ttsMeta && ttsMeta.voice_gender) || 'female';
      const voice = (!narrationGenderOverride && window.SalaVoiceChoice) ? window.SalaVoiceChoice.edgeVoiceFor(language) : '';
      // The picked tone applies to the course/edge voice; a company-voice fallback keeps the plain voice (stylized clones need their own consent).
      const tone = (!narrationGenderOverride && window.SalaVoiceChoice && window.SalaVoiceChoice.tone) ? window.SalaVoiceChoice.tone() : '';
      const attempt = (n) => fetch('/api/studio/tts', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ text: text, language: language, gender: gender, voice: voice, tone: tone })
      }).then((res) => {
        if (res.status === 204) { const none = new Error('no voice engine'); none.noEngine = true; throw none; }
        if (!res.ok) throw new Error('tts ' + res.status);
        return res.blob();
      }).then((blob) => {
        if (!blob || !blob.size) throw new Error('empty voice clip');
        return URL.createObjectURL(blob);
      }).catch((err) => {
        if (n >= 2 || (err && err.noEngine)) throw err;
        return new Promise((resolve) => setTimeout(resolve, 600 * (n + 1)))
          .then(() => attempt(n + 1));
      });
      return attempt(0);
    }
    function paintProceedCue() {
      const text = $('proceed-cue-text');
      const btn = $('btn-start-voice');
      const chrome = lessonChrome();
      const live = !!window.__THEODORE_LIVE_AUDIO_ACTIVE__;
      const label = live ? 'Continue the lesson' : 'Start or continue the lesson';
      if (text) text.textContent = live ? chrome.clickContinue : chrome.clickStart;
      if (btn) {
        btn.textContent = live ? 'Continue' : 'Start';
        btn.setAttribute('aria-label', label);
        btn.setAttribute('aria-pressed', live ? 'true' : 'false');
      }
      const stage = $('teach-stage');
      if (stage) stage.setAttribute('aria-label', label + '. Press Enter or Space.');
    }

    async function proceedFromCourse() {
      if (lessonLife.failed() || (learningHold && holdGroup(learningHoldReason) === 'away')) {
        await lifecycleReturn('tap', { force: true });
        return;
      }
      if (sampleIsComplete()) {
        await proceedByClick();
        return;
      }
      const hadSession = !!teachSession;
      if (!window.__THEODORE_LIVE_AUDIO_ACTIVE__) {
        try { await proceedByVoice(); }
        catch (error) { toast(String(error.message || error)); }
      }
      if (hadSession) await proceedByClick();
    }

    async function proceedByClick() {
      if (sampleIsComplete()) {
        endSampleTrial(lastTeachPayload);
        toast(trialEndedMessage(lastTeachPayload));
        return;
      }
      if (advancing) return;
      if (lecturePaused) {
        lecturePaused = false;
        setPauseButton(false);
        window.TheodoreLiveAudio?.resumeRecognition();
      }
      if (!teachSession) {
        const first = library.find((row) => row.featured) || library[0];
        if (!first) return toast('Choose a course on the left.');
        await openLibraryCourse(first.id);
        return;
      }
      await nextSlide();
    }

    async function proceedByVoice() {
      if (learningHold) {
        pauseLessonForAbsence(PRESENCE_PAUSE);
        return;
      }
      if (sampleIsComplete()) {
        endSampleTrial(lastTeachPayload);
        toast(trialEndedMessage(lastTeachPayload));
        return;
      }
      const started = await window.TheodoreLiveAudio?.start?.();
      if (started === false) toast('Voice is not ready yet. Press Start again in a moment.');
      if (!teachSession) {
        const first = library.find((row) => row.featured) || library[0];
        if (first) await openLibraryCourse(first.id);
      }
      paintProceedCue();
    }

    window.addEventListener('theodore-live-audio', (event) => {
      paintProceedCue();
      if (learningHold) return;
      if (event.detail?.active && !event.detail?.paused && !window.__THEODORE_LIVE_AUDIO_HOLD__) {
        stopSpeech();
        if (lastTeachPayload) syncVoiceToSlide(lastTeachPayload);
      }
      if (event.detail?.active && spokenActivityPrompt) {
        setTimeout(() => {
          if (!spokenActivityPrompt || !window.TheodoreLiveAudio || !window.TheodoreLiveAudio.noteActivity) return;
          window.TheodoreLiveAudio.noteActivity({
            id: spokenActivityPrompt.slice(0, 160),
            prompt: 'A game is on the screen. Ask for the answer in one short sentence and wait. Do not reveal the correct answer. ' + spokenActivityPrompt
          });
        }, 700);
      }
    });
    window.addEventListener('theodore-live-audio-speech', (event) => {
      const speaking = !!(event.detail && event.detail.speaking);
      document.body.classList.toggle('is-speaking', speaking && !lecturePaused);
      if (lecturePaused) return;
      if (speaking) {
        lastPlaybackAt = Date.now();
        theodoreAvatar?.speak(event.detail.text || ' ');
        return;
      }
      theodoreAvatar?.stopSpeaking();
    });
    let voiceLevel = 0.12;
    let voiceLevelFresh = 0;
    let voicePhase = 0;
    let voiceLineOn = false;
    const AUDIO_LOOKS = ['bars', 'line', 'mouth', 'ripple', 'lantern', 'face-amina', 'face-mei', 'face-luis', 'face-amara', 'face-noah', 'face-priya'];
    function showVoiceLevel(level, fresh) {
      const next = Math.max(0, Math.min(1, Number(level) || 0));
      voiceLevel = next;
      if (fresh) voiceLevelFresh = Date.now();
      const stage = $('audio-stage');
      if (stage) stage.style.setProperty('--level', next.toFixed(3));
      const bars = $('audio-bars');
      if (bars) bars.style.setProperty('--level', next.toFixed(3));
    }
    function paintVoiceLine() {
      const path = $('voice-line-path');
      if (!path) return;
      const speaking = document.body.classList.contains('is-speaking');
      const amp = speaking ? 10 + Math.max(voiceLevel, 0.18) * 62 : 6;
      voicePhase += speaking ? 0.22 : 0.04;
      let d = '';
      for (let x = 0; x <= 600; x += 10) {
        const y = 90 + Math.sin(x / 26 + voicePhase) * amp * (0.65 + 0.35 * Math.sin(x / 80 + voicePhase * 0.5));
        d += (x ? 'L' : 'M') + x + ' ' + y.toFixed(1);
      }
      path.setAttribute('d', d);
    }
    function tickVoiceLine() {
      if (!voiceLineOn) return;
      paintVoiceLine();
      requestAnimationFrame(tickVoiceLine);
    }
    function applyAudioLook(id) {
      const look = AUDIO_LOOKS.indexOf(id) >= 0 ? id : 'bars';
      const stage = $('audio-stage');
      if (stage) stage.dataset.look = look;
      const picker = $('drive-look');
      if (picker && picker.value !== look) picker.value = look;
      try { localStorage.setItem('audio-lab-look', look); } catch (err) { /* the choice can stay for this visit */ }
      if (look === 'line' && !voiceLineOn) {
        voiceLineOn = true;
        tickVoiceLine();
      } else if (look !== 'line') voiceLineOn = false;
    }
    window.addEventListener('theodore-live-audio-level', (event) => {
      const level = Number(event.detail && event.detail.level) || 0;
      showVoiceLevel(level, true);
      if (!lecturePaused && level > 0.03) document.body.classList.add('is-speaking');
      if (lecturePaused) return;
      theodoreAvatar?.setVoiceLevel(level);
    });
    setInterval(() => {
      if (!document.body.classList.contains('audio-only')) return;
      if (Date.now() - voiceLevelFresh < 160) return;
      if (voiceLevel < 0.09) return;
      showVoiceLevel(voiceLevel * 0.8, false);
    }, 90);
    window.addEventListener('theodore-live-audio-user', (event) => {
      if (lecturePaused) return;
      if (event.detail && event.detail.talking) theodoreAvatar?.setState('listening');
      else if (!theodoreAvatar?.speaking) theodoreAvatar?.setState('idle');
    });
    window.addEventListener('theodore-live-audio-utterance', (event) => {
      const text = event.detail && event.detail.text;
      const role = event.detail && event.detail.role;
      if (!text || lecturePaused || (event.detail && event.detail.command)) return;
      if (role === 'user' && spokenActivity) {
        applySpokenActivity(text, role);
        return;
      }
      queueLiveTopic(text);
    });
    window.addEventListener('theodore-live-audio-action', (event) => {
      const detail = event.detail || {};
      if (applyLiveAudioAction(detail)) return;
      if (detail.text && !lecturePaused) queueLiveTopic(detail.text);
    });
    window.addEventListener('theodore-live-audio-idle', () => {
      resumeUncoveredCourse().catch((error) => toast(String(error.message || error)));
    });

    function paintLessonPhoto(url, effect, alt) {
      const frame = $('lesson-photo');
      const img = $('lesson-photo-img');
      const stage = $('teach-stage');
      const overlay = $('presenter-overlay');
      const grid = $('teacher-stage-grid');
      if (!frame || !img) return;
      const on = Boolean(url);
      frame.hidden = !on;
      frame.classList.toggle('is-shown', on);
      if (stage) stage.classList.toggle('has-photo', on);
      if (overlay) overlay.classList.toggle('has-photo', on);
      if (grid) grid.classList.toggle('has-photo', on);
      if (!on) {
        img.removeAttribute('src');
        return;
      }
      img.alt = alt || 'Lesson photograph';
      if (img.getAttribute('src') !== url) img.src = url;
      frame.dataset.effect = effect || 'fade';
      frame.classList.remove('is-in');
      void frame.offsetWidth;
      frame.classList.add('is-in');
      const title = $('teach-title');
      if (title) {
        title.classList.remove('ppt-title');
        void title.offsetWidth;
        title.classList.add('ppt-title');
      }
    }

    function clearVisualTimeline() {
      visualTimeline = null;
      visualCueIndex = -1;
      const stage = $('teach-stage');
      const overlay = $('presenter-overlay');
      if (stage) stage.classList.remove('has-readable-card', 'has-road-scene');
      if (overlay) overlay.classList.remove('has-readable-card', 'has-road-scene');
      const host = $('teach-visual-timeline');
      if (!host) return;
      host.hidden = true;
      host.innerHTML = '';
      host.removeAttribute('data-style');
      host.removeAttribute('data-layout');
      host.classList.remove('layout-compare');
    }

    function renderVisualTimeline(payload) {
      const timeline = payload && payload.visual_timeline;
      const cues = timeline && Array.isArray(timeline.cues) ? timeline.cues : [];
      if (!cues.length) {
        clearVisualTimeline();
        return false;
      }
      const host = $('teach-visual-timeline');
      if (!host) return false;
      visualTimeline = timeline;
      visualCueIndex = -1;
      host.innerHTML = '';
      host.hidden = false;
      host.dataset.style = timeline.presentation_style_id || payload.presentation_style_id || 'layered';
      host.dataset.layout = timeline.layout || '';
      host.classList.toggle('layout-compare', timeline.layout === 'compare');
      const roadScene = timeline.layout === 'road-scene';
      $('teach-stage')?.classList.toggle('has-road-scene', roadScene);
      $('presenter-overlay')?.classList.toggle('has-road-scene', roadScene);
      if (timeline.style_label) {
        const badge = document.createElement('p');
        badge.className = 'timeline-style-label';
        badge.textContent = String(timeline.style_label);
        host.appendChild(badge);
      }
      cues.forEach((cue, cueIndex) => {
        const layers = Array.isArray(cue.layers) && cue.layers.length
          ? cue.layers : [{ kind: cue.kind, text: cue.text, url: cue.url, alt: cue.alt }];
        layers.forEach((layer, layerIndex) => {
          const el = document.createElement('div');
          el.className = 'visual-layer';
          el.dataset.cue = String(cueIndex);
          if (layer.persistent) el.dataset.persist = '1';
          el.dataset.transition = layer.transition || cue.transition || 'fade';
          el.style.zIndex = String(Number(layer.z_index ?? layerIndex) || 0);
          const kind = String(layer.kind || 'text');
          el.classList.add('kind-' + (kind.replace(/[^a-z0-9_-]/gi, '') || 'text'));
          const url = String(layer.url || layer.src || '');
          const text = String(layer.text || layer.label || cue.text || '');
          if ((kind === 'image' || kind === 'picture') && url) {
            const image = document.createElement('img');
            image.src = url;
            image.alt = String(layer.alt || text || '');
            image.loading = 'eager';
            el.appendChild(image);
          } else if (kind === 'video' && url) {
            const clip = document.createElement('video');
            clip.src = url;
            clip.muted = true;
            clip.defaultMuted = true;
            clip.autoplay = true;
            clip.loop = true;
            clip.playsInline = true;
            clip.setAttribute('muted', '');
            clip.setAttribute('playsinline', '');
            clip.setAttribute('aria-label', String(layer.alt || 'Lesson video'));
            el.appendChild(clip);
            clip.play().catch(() => {});
          } else if ((kind === 'svg' || kind === 'storyboard') && String(layer.svg || layer.content || '').trim().startsWith('<svg')) {
            el.innerHTML = String(layer.svg || layer.content);
            el.setAttribute('role', 'img');
            el.setAttribute('aria-label', String(layer.alt || text || 'Lesson diagram'));
          } else if (kind === 'keypoints' && Array.isArray(layer.items) && layer.items.length) {
            const card = document.createElement('div');
            card.className = 'road-points';
            if (layer.title) {
              const heading = document.createElement('h4');
              heading.textContent = String(layer.title);
              card.appendChild(heading);
            }
            const list = document.createElement('ol');
            const now = Number(layer.active) || 0;
            layer.items.forEach((item, itemIndex) => {
              const li = document.createElement('li');
              li.textContent = String(item);
              if (itemIndex < now) li.classList.add('is-done');
              if (itemIndex === now) {
                li.classList.add('is-now');
                li.setAttribute('aria-current', 'step');
              }
              list.appendChild(li);
            });
            card.appendChild(list);
            el.appendChild(card);
          } else {
            const label = document.createElement('div');
            label.className = 'visual-label';
            label.textContent = text;
            el.appendChild(label);
          }
          host.appendChild(el);
        });
      });
      syncVisualTimeline(0, true);
      return true;
    }

    function activeVisualCueIndex(atSeconds) {
      const cues = visualTimeline.cues;
      const at = Math.max(0, Number(atSeconds) || 0);
      let active = 0;
      let bestStart = -1;
      let found = false;
      for (let i = 0; i < cues.length; i += 1) {
        const cue = cues[i] || {};
        const start = Number(cue.start_s) || 0;
        const duration = Math.max(0.001, Number(cue.duration_s) || 0.001);
        if (at < start || at >= start + duration) continue;
        if (!found || start >= bestStart) {
          found = true;
          bestStart = start;
          active = i;
        }
      }
      if (found) return active;
      bestStart = -1;
      for (let i = 0; i < cues.length; i += 1) {
        const start = Number((cues[i] || {}).start_s) || 0;
        if (start <= at && start >= bestStart) {
          bestStart = start;
          active = i;
        }
      }
      return active;
    }

    function syncVisualTimeline(atSeconds, force) {
      if (!visualTimeline || !Array.isArray(visualTimeline.cues) || !visualTimeline.cues.length) return;
      const active = activeVisualCueIndex(atSeconds);
      if (!force && active === visualCueIndex) return;
      visualCueIndex = active;
      const host = $('teach-visual-timeline');
      const cue = visualTimeline.cues[active] || {};
      if (host) {
        const hold = visualTimeline.layout === 'compare';
        host.querySelectorAll('.visual-layer').forEach((layer) => {
          const index = Number(layer.dataset.cue);
          const words = layer.classList.contains('kind-title')
            || layer.classList.contains('kind-body')
            || layer.classList.contains('kind-callout')
            || layer.classList.contains('kind-text')
            || layer.classList.contains('kind-storyboard');
          const on = layer.dataset.persist === '1' || ((words || !hold) ? index === active : index <= active);
          layer.classList.toggle('is-active', on);
        });
        const readable = !!host.querySelector(
          '.visual-layer.is-active.kind-body, .visual-layer.is-active.kind-callout, .visual-layer.is-active.kind-text'
        );
        $('teach-stage').classList.toggle('has-readable-card', readable);
        $('presenter-overlay').classList.toggle('has-readable-card', readable);
        const label = cue.caption || cue.alt;
        if (label) host.setAttribute('aria-label', String(label));
      }
      applySectionCaption();
    }

    function renderTeach(payload) {
      teachEpoch += 1;
      if (!payload.dynamic) {
        stopSpeech();
        stopStudentMic();
        const staleReply = $('talk-reply');
        if (staleReply) staleReply.textContent = '';
        const staleQuiz = $('quiz-box');
        const staleGame = $('game-box');
        if (staleQuiz) { staleQuiz.style.display = 'none'; staleQuiz.innerHTML = ''; }
        if (staleGame) { staleGame.style.display = 'none'; staleGame.innerHTML = ''; }
      }
      lastTeachPayload = payload;
      beatHandled = false;
      showAbsorb(false);
      slideVariety = pickLearnVariety(payload);
      const turn = payload.turn || payload;
      if (payload.voice_gender) courseVoiceGender = payload.voice_gender;
      theodoreAvatar?.setScript(payload.avatar || { state:'presenting', cues:[] });
      const stage = $('teach-stage');
      stage.classList.remove('anim');
      void stage.offsetWidth;
      stage.classList.add('anim');
      $('teach-title').textContent = turn.title || '—';
      const welcome = $('page-welcome');
      if (welcome) welcome.hidden = true;
      $('teach-body').textContent = turn.display_body || '';
      $('teach-body').classList.toggle('kids-words',
        (payload.media || []).some((m) => m.kind === 'image'));
      const media = payload.media || [];
      const picture = media.find((m) => m.kind === 'image');
      const motion = media.find((m) => m.kind === 'video');
      const pictureEl = $('teach-picture');
      const motionEl = $('teach-motion');
      const storyboardEl = $('teach-storyboard');
      const storyConceptEl = $('teach-storyboard-concept');
      const sbSvg = payload.storyboard_svg || '';
      const photoUrl = String(payload.photo_url || '');
      const hasVisualTimeline = renderVisualTimeline(payload);
      const usePhoto = Boolean(photoUrl) && !hasVisualTimeline;
      const hasStoryboard = !usePhoto && !hasVisualTimeline && Boolean(sbSvg.trim());
      paintLessonPhoto(usePhoto ? photoUrl : '', payload.photo_transition || 'fade', turn.title || '');
      stage.classList.toggle('has-storyboard', hasStoryboard);
      stage.classList.toggle('has-visual-timeline', hasVisualTimeline);
      $('presenter-overlay').classList.toggle('has-storyboard', hasStoryboard);
      $('presenter-overlay').classList.toggle('has-visual-timeline', hasVisualTimeline);
      $('teacher-stage-grid').classList.toggle('has-storyboard', hasStoryboard);
      $('teacher-stage-grid').classList.toggle('has-visual-timeline', hasVisualTimeline);
      if (usePhoto) {
        storyboardEl.hidden = true;
        storyboardEl.innerHTML = '';
        storyConceptEl.hidden = true;
        pictureEl.hidden = true;
        motionEl.hidden = true;
        pictureEl.src = '';
        motionEl.src = '';
      } else if (hasVisualTimeline) {
        storyboardEl.hidden = true;
        storyboardEl.innerHTML = '';
        storyConceptEl.hidden = true;
        pictureEl.hidden = true;
        motionEl.hidden = true;
        pictureEl.src = '';
        motionEl.src = '';
      } else if (hasStoryboard) {
        storyboardEl.hidden = false;
        storyboardEl.innerHTML = sbSvg;
        storyboardEl.setAttribute('data-scene', payload.storyboard_scene_id || '');
        storyboardEl.setAttribute('aria-label',
          payload.storyboard_concept || turn.title || 'Animated lesson storyboard');
        const concept = payload.storyboard_concept || '';
        if (concept) {
          storyConceptEl.textContent = concept;
          storyConceptEl.hidden = false;
        } else {
          storyConceptEl.textContent = '';
          storyConceptEl.hidden = true;
        }
        pictureEl.hidden = true;
        motionEl.hidden = true;
        pictureEl.src = '';
        motionEl.src = '';
      } else if (payload.example_svg) {
        storyboardEl.hidden = false;
        storyboardEl.innerHTML = payload.example_svg;
        storyboardEl.setAttribute('aria-label', (turn.title || 'Example') + ' example');
        storyConceptEl.hidden = true;
        pictureEl.hidden = true;
        motionEl.hidden = true;
        pictureEl.src = '';
        motionEl.src = '';
        stage.classList.add('has-storyboard');
      } else {
        storyboardEl.hidden = true;
        storyboardEl.innerHTML = '';
        storyConceptEl.hidden = true;
        storyConceptEl.textContent = '';
        const playMotion = Boolean(motion);
        pictureEl.hidden = playMotion || !picture;
        pictureEl.src = picture ? picture.url : '';
        pictureEl.alt = picture ? (picture.caption || picture.title || '') : '';
        motionEl.hidden = !playMotion;
        motionEl.src = motion ? motion.url : '';
        motionEl.alt = motion ? (motion.caption || motion.title || '') : '';
      }
      const videoBtn = $('btn-video');
      if (videoBtn) {
        videoBtn.disabled = !motion || hasStoryboard;
        videoBtn.textContent = (motion && !hasStoryboard) ? 'Show picture' : 'Watch video';
      }
      $('teach-activity').textContent = payload.activity_prompt || '';
      $('teach-activity').style.display = payload.activity_prompt ? 'block' : 'none';
      const examples = payload.topic_examples || payload.examples || [];
      const exBox = $('teach-examples');
      const showExamples = examples.length && (
        slideVariety === 'examples' || payload.show_examples || payload.topic_jump
      );
      if (exBox && showExamples) {
        exBox.style.display = 'block';
        exBox.innerHTML = '<strong>Examples</strong><ol>' +
          examples.map((e) => `<li>${esc(e)}</li>`).join('') + '</ol>';
      } else if (exBox) {
        exBox.style.display = 'none';
        exBox.innerHTML = '';
      }
      const modBox = $('teach-modalities');
      if (modBox) { modBox.style.display = 'none'; modBox.innerHTML = ''; }
      if ($('btn-pop')) $('btn-pop').disabled = !teachSession;
      if ($('btn-game')) $('btn-game').disabled = !teachSession;
      $('teach-narr').textContent = slideCaptionText(payload);
      paintLessonCaption(payload);
      applySectionCaption();
      const adapt = (turn.adaptations_applied || []).join(', ') || 'no adaptations';
      const prog = payload.progress || {};
      const obj = payload.objective ? payload.objective.title : '';
      const lang = payload.language || teachLanguage;
      const spoken = payload.spoken_language || lang;
      const lessonText = $('teach-stage').querySelector('.lesson-stage-content');
      const rtl = ['ar', 'fa', 'he', 'ur'].includes(spoken);
      lessonText.setAttribute('lang', spoken || 'en');
      lessonText.setAttribute('dir', rtl ? 'rtl' : 'ltr');
      const coveredPct = typeof prog.covered_percent === 'number'
        ? prog.covered_percent
        : prog.completion_percent;
      const covered = typeof coveredPct === 'number'
        ? ` · ${coveredPct}% of the course` : '';
      $('teach-adapt').textContent =
        `${adapt} · lang ${esc(lang)} · focus: ${esc(obj)} · known ${prog.known || 0} / gaps ${prog.gaps || 0}${covered}`;
      const warn = $('lang-warning');
      const notices = [];
      if (payload.disclaimer) notices.push('ℹ ' + payload.disclaimer);
      if (spoken !== lang) {
        // Coverage is per-slide, so the voice follows the words rather than
        // reading English aloud with the requested language's voice.
        notices.push('⚠ This screen is not translated yet — shown and read aloud in ' +
          languageLabel(spoken) + '.');
      } else if (payload.translation_source === 'xai') {
        notices.push('ℹ Machine-translated by Grok — review before classroom use.');
      } else if (payload.translation_source === 'curated' && payload.translation_note) {
        notices.push('ℹ ' + payload.translation_note);
      }
      warn.textContent = notices.join('  ');
      warn.style.display = notices.length ? 'block' : 'none';
      const box = $('checkpoint-box');
      if (box) box.classList.remove('show');
      attentionFullBody = '';
      renderReview();
      placeStudentCam();
      void ensureStudentCamera();
      paintSampleBanner(payload);
      paintCourseMap(payload);
      armSampleClock(payload);
      if (payload.sample && payload.sample.complete) {
        lecturePaused = true;
        if ($('btn-pause')) setPauseButton(true);
        stopSpeech();
        return;
      }
      if (payload.dynamic) {
        if (window.__THEODORE_LIVE_AUDIO_ACTIVE__ && !window.__THEODORE_LIVE_AUDIO_HOLD__) {
          theodoreAvatar?.speak(turn.narration || turn.display_body || turn.title || '');
          syncVoiceToSlide(payload);
        }
        return;
      }
      if (window.__THEODORE_LIVE_AUDIO_ACTIVE__ && !window.__THEODORE_LIVE_AUDIO_HOLD__) {
        theodoreAvatar?.speak(turn.narration || turn.display_body || turn.title || '');
        syncVoiceToSlide(payload);
        return;
      }
      speakText(turn.narration || turn.display_body || '', payload.tts);
    }

    function readCurrentAloud() {
      if (!lastTeachPayload) return toast('Start a lesson first');
      const turn = lastTeachPayload.turn || lastTeachPayload;
      speakText(turn.narration || turn.display_body || '', lastTeachPayload.tts);
    }

    function watchCurrentVideo() {
      const motion = $('teach-motion');
      const picture = $('teach-picture');
      if (!motion.src) return toast('No video clip for this screen');
      const showing = !motion.hidden;
      motion.hidden = showing;
      picture.hidden = !showing;
      $('btn-video').textContent = showing ? 'Watch video' : 'Show picture';
    }

    const on = (id, event, fn) => { const el = $(id); if (el) el.addEventListener(event, fn); };
    on('btn-train', 'click', () => runTraining().catch((e) => toast(String(e.message || e))));
    on('btn-offline', 'click', () => runOfflineTrainer().catch((e) => toast(String(e.message || e))));
    on('btn-comment', 'click', () => postComment().catch((e) => toast(String(e.message || e))));
    on('btn-build', 'click', () => buildCourse().catch((e) => toast(String(e.message || e))));
    on('btn-kids-build', 'click', () => buildEarlyCourse().catch((e) => toast(String(e.message || e))));
    on('kids-level', 'change', renderEarlyTopics);
    on('btn-cert-build', 'click', () => buildCertCourse().catch((e) => toast(String(e.message || e))));
    on('cert-track', 'change', renderCertLessons);
    on('btn-teach', 'click', () => startTeach().catch((e) => toast(String(e.message || e))));
    on('btn-resume', 'click', () => resumeTeach().catch((e) => toast(String(e.message || e))));
    on('btn-start-over', 'click', () => startOverTeach().catch((e) => toast(String(e.message || e))));
    on('btn-next', 'click', () => nextSlide().catch((e) => toast(String(e.message || e))));
    on('course-map-gap', 'click', () => {
      resumeUncoveredCourse().catch((e) => toast(String(e.message || e)));
    });
    on('course-map-toggle', 'click', () => {
      const panel = $('course-map-panel');
      if (!panel) return;
      panel.hidden = !panel.hidden;
      const btn = $('course-map-toggle');
      if (btn) {
        btn.setAttribute('aria-expanded', panel.hidden ? 'false' : 'true');
        btn.textContent = panel.hidden ? 'Outline' : 'Hide outline';
      }
    });
    on('course-progress-hide', 'click', () => {
      const map = $('course-map');
      if (map) map.classList.add('progress-hidden');
    });
    on('course-progress-show', 'click', () => {
      const map = $('course-map');
      if (map) map.classList.remove('progress-hidden');
    });
    on('course-map-scrub', 'change', () => {
      const scrub = $('course-map-scrub');
      if (!scrub) return;
      jumpToPath(Number(scrub.value)).catch((e) => toast(String(e.message || e)));
    });
    on('course-map-list', 'click', (event) => {
      const button = event.target.closest('button[data-path-pos]');
      if (!button) return;
      jumpToPath(Number(button.getAttribute('data-path-pos'))).catch((e) => toast(String(e.message || e)));
    });
    on('course-price', 'click', () => openPayScreen());
    on('pay-card', 'click', () => { beginCoursePayment('card'); });
    on('pay-paypal', 'click', () => { beginCoursePayment('paypal'); });
    on('pay-close', 'click', () => closePayScreen());
    confirmCoursePayment();
    on('btn-pause', 'click', () => toggleLecturePause());
    on('btn-fullscreen', 'click', togglePresenterMode);
    on('library-hide', 'click', () => setLibraryCollapsed(true));
    on('library-show', 'click', () => setLibraryCollapsed(false));
    try {
      if (localStorage.getItem('aoep-library-collapsed') === '1') setLibraryCollapsed(true);
    } catch (err) {}
    on('btn-chrome', 'click', () => {
      const hide = !document.body.classList.contains('chrome-hidden');
      setStudioChromeHidden(hide);
      if (focusModeActive()) {
        if (hide) setDriveChromeHidden(true);
        else revealDriveChrome();
      }
    });
    on('fs-chrome-edge', 'click', () => {
      driveChromeWasHidden = true;
      revealDriveChrome();
    });
    // Swipe inward from the right edge to pull chrome back in full screen.
    let edgeSwipe = null;
    document.addEventListener('pointerdown', (event) => {
      if (!focusModeActive() || !document.body.classList.contains('drive-chrome-hidden')) return;
      if (event.clientX < window.innerWidth - 28) return;
      edgeSwipe = { id: event.pointerId, x: event.clientX, y: event.clientY };
    }, true);
    document.addEventListener('pointerup', (event) => {
      if (!edgeSwipe || event.pointerId !== edgeSwipe.id) return;
      const dx = edgeSwipe.x - event.clientX;
      const dy = Math.abs(edgeSwipe.y - event.clientY);
      edgeSwipe = null;
      if (dx > 36 && dy < 80) {
        driveChromeWasHidden = true;
        revealDriveChrome();
      }
    }, true);
    window.addEventListener('message', (event) => {
      const data = event.data;
      if (!data || data.type !== 'salareen-chrome') return;
      setStudioChromeHidden(!!data.hidden);
    });
    on('student-cam-hide', 'click', () => {
      const box = $('student-cam');
      setStudentCamHidden(!(box && box.classList.contains('is-hidden')));
    });
    enableStudentCamDrag();
    on('btn-captions', 'click', () => setCaptionsEnabled(!captionsEnabled));
    let proceedClickTimer = null;
    if (audioOnly) {
      parkSampleClock();
      revealDriveChrome();
      let savedLook = 'bars';
      try { savedLook = localStorage.getItem('audio-lab-look') || 'bars'; } catch (err) { savedLook = 'bars'; }
      applyAudioLook(savedLook);
    }
    on('drive-look', 'change', (event) => applyAudioLook(event.target.value));
    document.addEventListener('pointerdown', () => {
      const audio = document.body.classList.contains('audio-only');
      if (!audio && !presenterActive() && !document.fullscreenElement) return;
      driveChromeWasHidden = document.body.classList.contains('drive-chrome-hidden');
      revealDriveChrome();
    }, true);
    document.addEventListener('pointermove', () => {
      if (!focusModeActive()) return;
      revealDriveChrome();
    }, true);
    on('teach-stage', 'click', (event) => {
      if (document.body.classList.contains('audio-only')) {
        if (event.target.closest('button, input, select, textarea, a, label, #drive-bar, #course-map, #student-cam, #theodore-live-audio')) return;
        if (driveChromeWasHidden) return;
        onDriveWaveTap();
        return;
      }
      if (event.target.closest('button, input, select, textarea, a, label, .lesson-window-controls, .lesson-toolbar, .talk-panel, .quiz-box, .game-box, .activity, .theodore-avatar-wrap, #student-cam, #course-map')) return;
      if ((presenterActive() || document.fullscreenElement) && driveChromeWasHidden) return;
      clearTimeout(proceedClickTimer);
      proceedClickTimer = setTimeout(() => {
        proceedClickTimer = null;
        proceedFromCourse().catch((error) => toast(String(error.message || error)));
      }, 280);
    });
    on('teach-stage', 'keydown', (event) => {
      if (event.key !== 'Enter' && event.key !== ' ' && event.code !== 'Space') return;
      if (event.repeat) return;
      if (document.body.classList.contains('audio-only')) return;
      if (event.target.closest('button, input, select, textarea, a, label')) return;
      event.preventDefault();
      proceedFromCourse().catch((error) => toast(String(error.message || error)));
    });
    on('teach-stage', 'dblclick', (event) => {
      if (document.body.classList.contains('audio-only')) return;
      if (event.target.closest('button, input, select, textarea, a, .lesson-window-controls')) return;
      clearTimeout(proceedClickTimer);
      proceedClickTimer = null;
      togglePresenterMode();
    });
    on('btn-start-voice', 'click', (event) => {
      event.stopPropagation();
      proceedFromCourse().catch((error) => toast(String(error.message || error)));
    });
    on('btn-continue', 'click', () => continueSession().catch((e) => toast(String(e.message || e))));
    on('btn-later', 'click', () => comeBackLater().catch((e) => toast(String(e.message || e))));
    on('btn-profile', 'click', () => applyProfile().catch((e) => toast(String(e.message || e))));
    on('btn-read', 'click', readCurrentAloud);
    on('btn-video', 'click', watchCurrentVideo);
    on('btn-talk', 'click', openTalk);
    on('btn-talk-close', 'click', closeTalk);
    on('btn-talk-send', 'click', () => askTheodore().catch((e) => toast(String(e.message || e))));
    on('btn-talk-mic', 'click', () => speakQuestion());
    on('voice-ask', 'keydown', (ev) => {
      if (ev.key === 'Enter' && !ev.shiftKey) {
        ev.preventDefault();
        askTheodore().catch((e) => toast(String(e.message || e)));
      }
    });
    on('teach-voice-gender', 'change', (ev) => {
      courseVoiceGender = ev.target.value || 'female';
      if (teachSession && lastTeachPayload) startTeach().catch(() => {});
    });
    on('teach-lang', 'change', (event) => applyTeachLanguage(event.target.value));
    on('teach-lang-stage', 'change', (event) => applyTeachLanguage(event.target.value));
    on('drive-lang', 'change', (event) => applyTeachLanguage(event.target.value));
    // Every way back to the lesson funnels into one single-flight resume.
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'hidden') lessonLife.away('hidden');
      else void lifecycleReturn('visible');
    });
    window.addEventListener('pagehide', () => lessonLife.away('pagehide'));
    window.addEventListener('pageshow', (event) => {
      void lifecycleReturn(event.persisted ? 'pageshow-bfcache' : 'pageshow');
    });
    document.addEventListener('freeze', () => lessonLife.away('freeze'));
    document.addEventListener('resume', () => { void lifecycleReturn('resume'); });
    window.addEventListener('focus', () => { void lifecycleReturn('focus'); });
    function onAppState(state) {
      const value = String(state || '');
      if (value === 'background' || value === 'inactive') lessonLife.away('app-' + value);
      else if (value === 'active') void lifecycleReturn('app-active');
    }
    window.addEventListener('salareen-app-state', (event) => onAppState(event.detail && event.detail.state));
    window.addEventListener('message', (event) => {
      const data = event.data;
      if (event.source !== window.parent && event.source !== window) return;
      if (data && data.type === 'salareen-app-state') onAppState(data.state);
    });
    on('student-cam-video', 'playing', () => { void lifecycleReturn('camera-playing'); });
    on('student-cam-video', 'loadeddata', () => { void lifecycleReturn('camera-loadeddata'); });
    // Timers stop while the device sleeps; a long gap between ticks means the screen just woke.
    setInterval(() => {
      const now = Date.now();
      const gap = now - lifecycleTickAt;
      lifecycleTickAt = now;
      if (gap < WAKE_GAP_MS || document.visibilityState === 'hidden') return;
      lessonLife.away('sleep');
      void lifecycleReturn('wake');
    }, 1000);
    on('resume-retry', 'click', (event) => {
      event.stopPropagation();
      void lifecycleReturn('tap', { force: true });
    });
    paintLessonChrome(teachLanguage);
    paintProceedCue();
    // Escape leaves fullscreen without telling us, so follow the browser back.
    document.addEventListener('fullscreenchange', () => {
      if (!document.fullscreenElement) exitPresenterMode();
    });
    on('btn-avatar', 'click', () => setAvatarVisible(!avatarVisible));
    on('btn-avatar-hide', 'click', () => setAvatarVisible(false));

    avatarPrefs = loadAvatarPrefs();
    selectedAvatarId = avatarPrefs.presenterChosen && avatarPrefs.presenter
      ? avatarPrefs.presenter
      : 'serenity';
    initAvatarDrag();
    setAvatarVisible(
      typeof avatarPrefs.on === 'boolean' ? avatarPrefs.on : SHOW_AVATAR, false);
    paintSampleBanner(null);
    arrangePhoneLesson();
    loadLanguages().catch(() => {});
    loadAvatarChoices().catch((error) => toast(String(error.message || error)));
    loadLibrary().catch((e) => toast(String(e.message || e)));
    updateLessonWindowControls();

"""

def render_studio_page() -> str:
    return (
        """<!doctype html>\n<html lang="en">\n<head>\n  <meta charset="utf-8" />\n  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />\n  <title>Theodore Course Studio</title>\n  <style>\n"""
        + STUDIO_CSS
        + """</style>
  <script type="importmap">
    {"imports":{"three":"/api/studio/avatar/three.module.js"}}
  </script>
</head>
<body class="theme-study">
  <script>if(/[?&]embed=mobile(?:&|$)/.test(location.search)||matchMedia("(max-width:760px)").matches)document.body.classList.add("phone-embed");</script>
  <script>try{if(/[?&]intro=1(?:&|$)/.test(location.search)&&/[?&]demo=1(?:&|$)/.test(location.search)&&parent!==window&&sessionStorage.getItem("salareen.driversEdIntro.seen.v1")!=="1")document.documentElement.classList.add("sala-intro-hold");}catch(e){}</script>
  <script src="/api/studio/voice-overlay/friendly_error.js" data-watch="^/api/studio/" data-ignore="/tts|/voice|/live-audio|/avatar"></script>
  <div class="study-bg" aria-hidden="true">
    <svg class="shelf shelf-left" viewBox="0 0 92 720" preserveAspectRatio="xMidYMin slice">
      <g fill="#1e3a5f"><rect x="8" y="24" width="16" height="150" rx="2"/><rect x="28" y="40" width="13" height="134" rx="2"/><rect x="46" y="18" width="18" height="156" rx="2"/><rect x="68" y="36" width="14" height="138" rx="2"/></g>
      <g fill="#8c3a2f"><rect x="10" y="200" width="18" height="148" rx="2"/><rect x="32" y="214" width="12" height="134" rx="2"/><rect x="48" y="196" width="16" height="152" rx="2"/><rect x="68" y="208" width="14" height="140" rx="2"/></g>
      <g fill="#2f5d46"><rect x="8" y="376" width="15" height="146" rx="2"/><rect x="27" y="390" width="17" height="132" rx="2"/><rect x="48" y="370" width="13" height="152" rx="2"/><rect x="65" y="384" width="16" height="138" rx="2"/></g>
      <g fill="#c4a15a"><rect x="12" y="552" width="14" height="140" rx="2"/><rect x="30" y="566" width="18" height="126" rx="2"/><rect x="52" y="548" width="12" height="144" rx="2"/><rect x="68" y="560" width="15" height="132" rx="2"/></g>
    </svg>
    <svg class="shelf shelf-right" viewBox="0 0 92 720" preserveAspectRatio="xMidYMin slice">
      <g fill="#1e3a5f"><rect x="8" y="24" width="16" height="150" rx="2"/><rect x="28" y="40" width="13" height="134" rx="2"/><rect x="46" y="18" width="18" height="156" rx="2"/><rect x="68" y="36" width="14" height="138" rx="2"/></g>
      <g fill="#8c3a2f"><rect x="10" y="200" width="18" height="148" rx="2"/><rect x="32" y="214" width="12" height="134" rx="2"/><rect x="48" y="196" width="16" height="152" rx="2"/><rect x="68" y="208" width="14" height="140" rx="2"/></g>
      <g fill="#2f5d46"><rect x="8" y="376" width="15" height="146" rx="2"/><rect x="27" y="390" width="17" height="132" rx="2"/><rect x="48" y="370" width="13" height="152" rx="2"/><rect x="65" y="384" width="16" height="138" rx="2"/></g>
      <g fill="#c4a15a"><rect x="12" y="552" width="14" height="140" rx="2"/><rect x="30" y="566" width="18" height="126" rx="2"/><rect x="52" y="548" width="12" height="144" rx="2"/><rect x="68" y="560" width="15" height="132" rx="2"/></g>
    </svg>
    <div class="wash"></div>
  </div>
  <header class="mast">
    <div>
      <p class="eyebrow">Study hall</p>
      <h1>Theodore Course Studio</h1>
      <p>Pick a course from the shelf. Theodore reads it with you, one page at a time.
         Driver's ed and food safety are the first two books.</p>
    </div>
    <div class="mast-art" aria-hidden="true">
      <svg viewBox="0 0 168 112">
        <rect x="8" y="78" width="152" height="10" rx="3" fill="#e7d3a8"/>
        <rect x="18" y="28" width="22" height="52" rx="2" fill="#1e3a5f"/>
        <rect x="44" y="20" width="18" height="60" rx="2" fill="#8c3a2f"/>
        <rect x="66" y="34" width="26" height="46" rx="2" fill="#2f5d46"/>
        <rect x="96" y="24" width="16" height="56" rx="2" fill="#c4a15a"/>
        <path d="M118 70c8-22 28-22 36 0" fill="none" stroke="#8c5a2b" stroke-width="3"/>
        <circle cx="136" cy="28" r="10" fill="#f4d48a" stroke="#8c5a2b" stroke-width="2"/>
        <rect x="132" y="38" width="8" height="28" rx="2" fill="#8c5a2b"/>
        <path d="M24 36h10M48 30h10M72 44h14" stroke="#f8f1e4" stroke-width="2"/>
      </svg>
    </div>
  </header>
  <div class="layout">
    <div class="panel library-panel">
      <div class="library-bar">
        <label><span data-i18n="library">Course library</span>
          <select id="library-picker" aria-label="Course library"></select>
        </label>
        <button id="library-hide" class="secondary" type="button" aria-pressed="false" data-i18n="hideCourses">Hide courses</button>
      </div>
      <h2><span class="mark" aria-hidden="true"><svg viewBox="0 0 28 28" width="22" height="22"><path d="M4 6h8c1.4 1 2.8 1 4 0h8v16h-8c-1.2 1-2.6 1-4 0H4V6z" fill="none" stroke="#1e3a5f" stroke-width="1.8"/><path d="M14 7v14" stroke="#1e3a5f" stroke-width="1.4"/></svg></span> <span data-i18n="library">Course library</span></h2>
      <div class="row">
        <label><span data-i18n="language">Language</span> <select id="teach-lang" style="min-width:12rem"></select></label>
      </div>
      <div class="status" id="library-now" data-i18n="choose">Choose a course to begin.</div>
      <div class="list library" id="library-list"></div>
    </div>
    <button id="library-show" class="secondary" type="button" hidden data-i18n="showCourses">Courses</button>
    <div class="panel">
      <div id="teach-stage-home">
      <div class="teach-stage captions-off" id="teach-stage" tabindex="0" aria-keyshortcuts="Enter Space" aria-label="Start or continue the lesson. Press Enter or Space.">
        <div id="drive-bar" class="drive-bar">
          <label><span data-i18n="course">Course</span>
            <select id="drive-course" aria-label="Course"></select>
          </label>
          <label><span data-i18n="language">Language</span>
            <select id="drive-lang" aria-label="Lesson language"></select>
          </label>
          <label><span data-i18n="look">Look</span>
            <select id="drive-look" aria-label="Animation">
              <optgroup data-i18n-label="motion" label="Motion">
                <option value="bars" data-i18n="bars">Bars</option>
                <option value="line" data-i18n="line">Frequency line</option>
                <option value="mouth" data-i18n="mouth">Talking mouth</option>
                <option value="ripple" data-i18n="ripple">Soft ripples</option>
                <option value="lantern" data-i18n="lantern">Lantern</option>
              </optgroup>
              <optgroup data-i18n-label="faces" label="Faces">
                <option value="face-amina">Amina</option>
                <option value="face-mei">Mei</option>
                <option value="face-luis">Luis</option>
                <option value="face-amara">Amara</option>
                <option value="face-noah">Noah</option>
                <option value="face-priya">Priya</option>
              </optgroup>
            </select>
          </label>
        </div>
        <div class="lesson-window-controls" aria-label="Lesson window controls">
          <label class="lesson-lang"><span data-i18n="language">Language</span>
            <select id="teach-lang-stage" aria-label="Lesson language"></select>
          </label>
          <button id="btn-captions" class="is-off" type="button" aria-pressed="false" aria-label="Show lesson captions" title="Show captions">CC</button>
          <button id="btn-chrome" type="button" hidden aria-pressed="false" title="Hide options" data-i18n="hideOptions">Hide options</button>
          <button id="btn-fullscreen" type="button" aria-label="Expand lesson to full screen" title="Full screen">⛶</button>
        </div>
        <h3 id="teach-title" data-i18n="yourLesson">Your lesson</h3>
        <div class="audio-stage" id="audio-stage" data-look="bars" aria-label="Audio playing">
          <div class="audio-bars" id="audio-bars" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i></div>
          <svg class="voice-line" viewBox="0 0 600 180" preserveAspectRatio="none" aria-hidden="true">
            <path id="voice-line-path" fill="none" stroke="#8feaff" stroke-width="3.5" stroke-linecap="round"></path>
          </svg>
          <div class="voice-mouth" aria-hidden="true"><i class="lip-upper"></i><i class="lip-opening"></i><i class="lip-lower"></i></div>
          <div class="voice-ripple" aria-hidden="true"><b></b><i></i><i></i><i></i></div>
          <div class="voice-lantern" aria-hidden="true"><i></i></div>
          <svg class="voice-face" viewBox="0 0 200 250" aria-hidden="true">
            <g class="hair hair-coils face-hair-fill"><circle cx="48" cy="78" r="18"/><circle cx="72" cy="50" r="18"/><circle cx="100" cy="42" r="20"/><circle cx="128" cy="50" r="18"/><circle cx="152" cy="78" r="18"/><circle cx="38" cy="108" r="16"/><circle cx="162" cy="108" r="16"/></g>
            <g class="hair hair-natural face-hair-fill"><ellipse cx="100" cy="96" rx="90" ry="74"/></g>
            <g class="hair hair-long face-hair-fill"><path d="M52 108 Q48 42 100 34 Q152 42 148 108 Q170 48 176 214 Q148 198 138 128 Q100 78 62 128 Q52 198 24 214 Q30 48 52 108"/></g>
            <path d="M28 248 Q28 198 72 186 Q100 178 128 186 Q172 198 172 248" fill="#163044"/>
            <ellipse class="face-ear" cx="38" cy="132" rx="12" ry="16"/>
            <ellipse class="face-ear" cx="162" cy="132" rx="12" ry="16"/>
            <ellipse class="face-skin" cx="100" cy="132" rx="64" ry="76"/>
            <path class="face-brow" d="M64 114 Q76 106 88 114"/>
            <path class="face-brow" d="M112 114 Q124 106 136 114"/>
            <path class="face-nose" d="M100 134 Q108 150 100 158"/>
            <g class="hair hair-bangs face-hair-fill"><path d="M42 118 Q54 46 100 40 Q146 46 158 118 Q136 86 100 92 Q64 86 42 118"/></g>
            <g class="hair hair-crop face-hair-fill"><path d="M46 124 Q54 52 100 46 Q146 52 154 124 Q136 102 100 106 Q64 102 46 124"/></g>
            <ellipse class="face-eye" cx="76" cy="128" rx="7" ry="8" fill="#1c140f"/>
            <ellipse class="face-eye" cx="124" cy="128" rx="7" ry="8" fill="#1c140f"/>
            <circle cx="78" cy="126" r="2" fill="#fff" opacity=".85"/>
            <circle cx="126" cy="126" r="2" fill="#fff" opacity=".85"/>
            <g class="face-glasses" fill="none" stroke="#d7e7ea" stroke-width="2.4"><circle cx="76" cy="128" r="14"/><circle cx="124" cy="128" r="14"/><path d="M90 128 H110"/></g>
            <g class="face-mouth-wrap">
              <ellipse cx="100" cy="166" rx="14" ry="8" fill="#4a2030"/>
              <path class="face-lip" d="M84 162 Q100 156 116 162 Q100 176 84 162"/>
            </g>
          </svg>
        </div>
        <aside id="course-map" class="course-map" hidden>
          <div id="course-map-panel" class="course-map-panel" hidden>
            <p id="course-map-count" class="course-map-count">Slide 1 of 1</p>
            <input id="course-map-scrub" class="course-map-scrub" type="range" min="0" max="0" value="0" aria-label="Skip to a part of the course" />
            <ol id="course-map-list" class="course-map-list"></ol>
          </div>
          <div class="course-map-dock">
            <div class="course-progress-cluster">
              <button type="button" id="course-progress-ring" class="course-progress-ring" aria-label="Course progress" title="Course progress">
                <svg viewBox="0 0 36 36" aria-hidden="true">
                  <circle class="ring-track" cx="18" cy="18" r="15.5"></circle>
                  <circle id="course-map-fill" class="ring-value" cx="18" cy="18" r="15.5" transform="rotate(-90 18 18)"></circle>
                </svg>
                <strong id="course-map-percent">0%</strong>
              </button>
              <button id="course-progress-hide" class="course-progress-hide" type="button" aria-label="Hide progress" title="Hide progress">×</button>
            </div>
            <button id="course-progress-show" class="course-progress-show" type="button" hidden aria-label="Show progress" title="Show progress">%</button>
            <button id="course-map-gap" class="course-map-toggle" type="button" hidden data-i18n="nextGap">Next gap</button>
            <button id="course-map-toggle" class="course-map-toggle" type="button" aria-expanded="false" data-i18n="outline">Outline</button>
          </div>
        </aside>
        <div class="teacher-stage-grid" id="teacher-stage-grid">
          <div id="teach-visual-timeline" class="visual-timeline-stage" hidden
               aria-live="polite" aria-label="Lesson visual sequence"></div>
          <div id="teach-storyboard" class="storyboard-stage" hidden aria-hidden="true"></div>
          <div class="lesson-photo" id="lesson-photo" hidden>
            <div class="lesson-photo-motion"><img id="lesson-photo-img" alt="" /></div>
          </div>
          <div class="theodore-avatar-wrap" id="theodore-avatar-wrap">
            <div class="avatar-drag-handle" id="avatar-drag-handle" role="button" tabindex="0"
                 aria-label="Move Theodore. Arrow keys nudge, Home resets, double-click resets."
                 title="Drag to move · arrow keys nudge · double-click to reset"><span></span></div>
            <button class="avatar-hide-btn" id="btn-avatar-hide" type="button" aria-label="Hide Theodore">✕</button>
            <div id="theodore-avatar" aria-hidden="true"></div>
            <div class="avatar-resize-handle" id="avatar-resize-handle" role="button" tabindex="0"
                 aria-label="Resize Theodore" title="Drag to resize"></div>
            <div class="avatar-label" id="avatar-state" role="status" aria-live="polite">Theodore · loading 3D teacher…</div>
          </div>
          <div class="lesson-stage-content">
            <div class="storyboard-concept" id="teach-storyboard-concept" hidden></div>
            <div class="picture-stage">
              <img id="teach-picture" hidden alt="" />
              <img id="teach-motion" hidden alt="" />
            </div>
            <div class="page-welcome" id="page-welcome">
              <svg viewBox="0 0 280 150" aria-hidden="true">
                <rect x="18" y="28" width="150" height="98" rx="8" fill="#fff" stroke="#e0d2bf"/>
                <path d="M34 48h70M34 66h92M34 84h80M34 102h54" stroke="#d9c7a6" stroke-width="4" stroke-linecap="round"/>
                <path d="M168 78c10-28 36-28 46 0" fill="none" stroke="#8c5a2b" stroke-width="3"/>
                <circle cx="191" cy="36" r="14" fill="#f4d48a" stroke="#8c5a2b" stroke-width="2"/>
                <rect x="185" y="50" width="12" height="34" rx="3" fill="#8c5a2b"/>
                <rect x="214" y="96" width="46" height="8" rx="3" fill="#1e3a5f"/>
                <rect x="220" y="70" width="10" height="26" rx="2" fill="#8c3a2f"/>
                <rect x="234" y="62" width="12" height="34" rx="2" fill="#2f5d46"/>
              </svg>
              <p data-i18n="clickStart">Tap the lesson to start.</p>
            </div>
            <div class="proceed-cue" id="proceed-cue">
              <p id="proceed-cue-text" data-i18n="clickContinue">Tap the lesson to continue.</p>
              <button id="btn-start-voice" type="button" data-i18n="start" aria-label="Start or continue the lesson">Start</button>
            </div>
            <div class="body" id="teach-body"></div>
            <p id="attention-aside" class="attention-aside" hidden></p>
            <div class="modality-row" id="teach-modalities"></div>
            <div class="examples-box" id="teach-examples"></div>
            <div class="lang-warning" id="lang-warning" style="display:none"></div>
            <div class="sample-clock" id="sample-clock" hidden title="Free demo: time left">
              <span id="sample-clock-time">10:00</span>
              <small data-i18n="freeTrial">free trial</small>
            </div>
            <div class="sample-banner" id="sample-banner" style="display:none" role="status"></div>
            <div class="activity" id="teach-activity" style="display:none"></div>
            <div class="narr" id="teach-narr"></div>
            <div class="absorb-note" id="absorb-note" hidden data-i18n="absorb">Take a moment with this page. The next one waits so you can study it.</div>
            <div class="status" id="teach-adapt"></div>
          </div>
        </div>
        <p class="lesson-caption" id="lesson-caption" hidden></p>
        <button id="resume-retry" type="button" hidden aria-live="polite">Tap to continue the lesson</button>
        <div class="quiz-box" id="quiz-box" style="display:none"></div>
        <div class="game-box" id="game-box" style="display:none"></div>
        <div class="row lesson-toolbar" id="lesson-toolbar">
          <button id="btn-pause" class="secondary" type="button" data-i18n="pause">Pause</button>
          <button id="btn-start-over" class="secondary" type="button" title="Begin this course again for this account or profile" data-i18n="startOver">Start over</button>
          <button id="btn-talk" type="button" data-i18n="ask">Ask</button>
          <button class="secondary" id="btn-avatar" type="button" aria-pressed="false"
                  aria-controls="theodore-avatar-wrap" data-i18n="showAvatar">Show Avatar</button>
        </div>
        <div class="talk-panel" id="talk-panel" hidden>
          <h2 data-i18n="askTitle">Ask about this course</h2>
          <p data-i18n="askBody">Ask a question or leave a comment. Theodore answers only about this training.</p>
          <textarea id="voice-ask" rows="3" data-i18n-placeholder="askPlaceholder" placeholder="Ask about a rule, a sign, or this page. You can type or speak."></textarea>
          <div class="talk-reply" id="talk-reply"></div>
          <div class="row">
            <button id="btn-talk-mic" type="button" data-i18n="speak">Speak</button>
            <button id="btn-talk-send" type="button" data-i18n="send">Send</button>
            <button class="secondary" id="btn-talk-close" type="button" data-i18n="close">Close</button>
          </div>
        </div>
      </div>
      </div>
    </div>
  </div>
  <div class="presenter-overlay" id="presenter-overlay" aria-label="Full screen lesson">
    <div class="presenter-body" id="presenter-body"></div>
    <div id="student-cam" class="student-cam" hidden title="Drag to move the camera">
      <video id="student-cam-video" autoplay muted playsinline aria-label="Your camera"></video>
      <canvas id="student-cam-track" class="student-cam-track" aria-hidden="true"></canvas>
      <canvas id="student-cam-sample" hidden></canvas>
      <button type="button" id="student-cam-hide" class="student-cam-hide" aria-pressed="false"
              title="Hide the preview. The camera stays on." data-i18n="hide">Hide</button>
      <p id="student-cam-status" class="student-cam-status">Watching for presence.</p>
      <p class="student-cam-note" data-i18n="cameraNote">Camera stays on. The lesson pauses if you leave the camera.</p>
    </div>
  </div>
  <p id="presence-hold" role="status" aria-live="assertive" hidden></p>
  <button id="fs-chrome-edge" type="button" hidden aria-expanded="true"
          title="Show options" aria-label="Show options from the edge">Options</button>
  <button id="course-price" type="button" hidden>Full course $19.99</button>
  <div id="pay-screen" hidden>
    <form>
      <h2>Full course</h2>
      <p id="pay-price">$19.99</p>
      <p id="pay-copy">One payment of $19.99 unlocks the rest of this class.</p>
      <div class="row">
        <button id="pay-card" type="button">Credit card</button>
        <button id="pay-paypal" type="button">PayPal</button>
      </div>
      <p id="pay-status" role="status"></p>
      <button id="pay-close" class="secondary" type="button">Not now</button>
    </form>
  </div>
  <div class="toast" id="toast"></div>
  <script>"""
        + STUDIO_JS
        + """\n</script>
  <!-- Voice-first "Sala only" overlay. Reads ?voicefirst=0 to disable
       and ?typemode=1 to show the accessibility type-to-ask pill. -->
  <script src="/api/studio/voice-overlay/voice_choice.js"></script>
  <script type="module" src="/api/studio/voice-overlay/course_voice.js" defer></script>
</body>\n</html>\n"""
    )

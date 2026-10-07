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
  body.public-course .library-panel { display:none; }
  body.public-course .layout { grid-template-columns:1fr; padding:8px; }
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
    .teach-stage.captions-off .lesson-stage-content { display:none; }
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
    .lesson-photo[data-effect="fade"].is-in .lesson-photo-motion { animation:pptFade .7s ease both; }
    .lesson-photo[data-effect="fly"].is-in .lesson-photo-motion { animation:pptFly .75s cubic-bezier(.2,.7,.2,1) both; }
    .lesson-photo[data-effect="wipe"].is-in .lesson-photo-motion { animation:pptWipe .8s ease both; }
    .lesson-photo[data-effect="zoom"].is-in .lesson-photo-motion { animation:pptZoom .8s ease both; }
    .lesson-photo[data-effect="cover"].is-in .lesson-photo-motion { animation:pptCover .7s cubic-bezier(.2,.7,.2,1) both; }
    .lesson-photo[data-effect="split"].is-in .lesson-photo-motion { animation:pptSplit .7s ease both; }
    .lesson-photo.is-in img { animation:kenBurns 18s ease-in-out .8s alternate infinite; }
    .ppt-title { animation:pptFlyUp .55s ease both; }
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
    .student-cam { position:fixed; z-index:10001; top:88px; left:16px; width:176px; max-width:34vw;
                   border-radius:12px; overflow:hidden; background:rgba(12,10,8,.72);
                   border:1px solid rgba(255,255,255,.28); box-shadow:0 8px 22px rgba(0,0,0,.35);
                   cursor:grab; touch-action:none; user-select:none; }
    .student-cam.is-dragging { cursor:grabbing; box-shadow:0 14px 32px rgba(0,0,0,.45); }
    .student-cam.is-hidden { width:auto; }
    .student-cam video { display:block; width:100%; aspect-ratio:16/9; object-fit:cover;
                         transform:scaleX(-1); background:#000; }
    .student-cam.is-hidden video { position:absolute; width:8px; height:8px; opacity:0; }
    .student-cam-hide { position:absolute; right:6px; bottom:6px; z-index:2; margin:0; padding:4px 8px;
                        border-radius:999px; border:1px solid rgba(255,255,255,.35);
                        background:rgba(0,0,0,.62); color:#fff; font:700 11px Arial,sans-serif;
                        cursor:pointer; touch-action:auto; }
    .student-cam.is-hidden .student-cam-hide { position:relative; right:auto; bottom:auto; margin:6px; }
    .student-cam-note { display:none; margin:0; padding:0 8px 8px; color:#f6efe4; font-size:11px; line-height:1.35; }
    .student-cam.is-hidden .student-cam-note { display:block; }
    .student-cam-status { margin:0; padding:6px 8px 8px; color:#f6efe4; font:700 11px Arial,sans-serif; line-height:1.35; }
    .presenter-overlay .lesson-toolbar { position:absolute; top:62px; right:18px; z-index:5; }
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
    @media (max-width:700px) {
      .picture-stage { grid-template-columns:1fr; }
      .teacher-stage-grid { grid-template-columns:1fr; }
      .theodore-avatar-wrap { min-height:320px; }
    }
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

"""

STUDIO_JS = """

    const $ = (id) => document.getElementById(id);
    // Set true to show the 3D teacher again. Narration stays on either way.
    const SHOW_AVATAR = false;
    // SHOW_AVATAR is only the first-visit default now; the toggle below persists
    // the learner's own choice, along with where they dragged him.
    const AVATAR_PREF_KEY = 'theodore.studio.avatar';
    const AVATAR_MIN_W = 150;
    const AVATAR_MIN_H = 190;
    let avatarPrefs = {};
    let avatarVisible = false;
    let avatarInitPromise = null;
    let avatarHomeParent = null;
    let avatarHomeNext = null;
    let avatarCatalog = {};
    let selectedAvatarId = 'amina';
    let selectedSource = null;
    let selectedCourse = null;
    let teachSession = 'studio-teach-1';
    let pagesCache = [];
    let teachLanguage = 'en';
    let languageNames = {};
    let serverAudio = null;
    let neuralObjectUrl = null;
    let courseVoiceGender = 'female';
    let lastTeachPayload = null;
    let earlyOptions = [];
    let certOptions = [];
    const studioQuery = new URLSearchParams(location.search);
    const requestedAccess = (studioQuery.get('access') || '').trim().toLowerCase();
    const registeredFlag = studioQuery.get('registered') === '1';
    const enrollmentStatus = (studioQuery.get('enrollment') || '').trim();
    const adminFlag = studioQuery.get('admin') === '1';
    const pinnedCourse = (studioQuery.get('course') || '').trim();
    function teachAccessFields() {
      return {
        access: requestedAccess,
        registered: registeredFlag || adminFlag,
        enrollment_status: enrollmentStatus,
        is_admin: adminFlag,
      };
    }
    function sampleIsComplete() {
      return !!(lastTeachPayload && lastTeachPayload.sample && lastTeachPayload.sample.complete);
    }
    function paintSampleBanner(payload) {
      const banner = $('sample-banner');
      if (!banner) return;
      const sample = (payload && payload.sample) || {};
      const mode = (payload && payload.access_mode) || '';
      const show = mode === 'sample' || (!payload && requestedAccess === 'sample');
      banner.style.display = show ? 'block' : 'none';
      banner.textContent = show
        ? (sample.message || '10-minute sample. A registered learner who has paid for the class takes the full course.')
        : '';
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

    function presenterLabel(presenter) {
      const name = presenter?.label || 'Student';
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
      if (!avatarCatalog[selectedAvatarId] || !avatarPrefs.presenterChosen) {
        selectedAvatarId = data.default_model || Object.keys(avatarCatalog)[0] || 'student';
      }
      const select = $('avatar-choice');
      if (!select) return;
      select.innerHTML = Object.entries(avatarCatalog).map(([id, model]) =>
        `<option value="${esc(id)}">${esc(model.label || id)}</option>`
      ).join('');
      select.value = selectedAvatarId;
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
    function clampAvatarBox() {
      const wrap = $('theodore-avatar-wrap');
      if (!wrap || !avatarPrefs.placed) return;
      const w = Math.min(Math.max(avatarPrefs.w || wrap.offsetWidth, AVATAR_MIN_W), window.innerWidth);
      const h = Math.min(Math.max(avatarPrefs.h || wrap.offsetHeight, AVATAR_MIN_H), window.innerHeight);
      avatarPrefs.w = w;
      avatarPrefs.h = h;
      avatarPrefs.x = Math.min(Math.max(avatarPrefs.x || 0, 0), Math.max(window.innerWidth - w, 0));
      avatarPrefs.y = Math.min(Math.max(avatarPrefs.y || 0, 0), Math.max(window.innerHeight - h, 0));
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
        btn.textContent = avatarVisible ? 'Hide Theodore' : 'Show Theodore';
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
              return lessonHandMesh;
            } catch (_) {}
          }
        } catch (_) {}
        lessonHandFailed = true;
        return null;
      })();
      return lessonHandPromise;
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
      try { result = hl.detectForVideo(video, performance.now()); }
      catch (_) { return null; }
      const hands = (result && result.landmarks) || [];
      if (!hands.length) return { hands_on_face_score: 0, hand_below: 0 };
      return {
        hands_on_face_score: handsCoveringFace(hands, facePts),
        hand_below: handsBelowFace(hands, facePts),
      };
    }

    async function studentCameraSample() {
      if (studentCamBusy || !lastTeachPayload) return;
      if (!cameraWatchStarted) cameraWatchStarted = Date.now();
      const video = $('student-cam-video');
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
          const landmarker = await ensureLessonFaceMesh();
          if (landmarker) {
            try { facial = meshFacial(landmarker.detectForVideo(video, performance.now())); }
            catch (_) { facial = null; }
          }
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
          const handTrack = live ? await lessonHandSample(video, facePts) : null;
          if (handTrack && handTrack.hands_on_face_score > 0.05) {
            signal.hands_on_face_score = Math.round(handTrack.hands_on_face_score * 1000) / 1000;
          }
          if (handTrack && handTrack.hand_below >= 0.55) signal.phone_visible = true;
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
        /* A failed sample must not stop the lesson by itself. */
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

    function applyLearningHold(data) {
      const status = $('student-cam-status');
      if (!data || !data.hold) {
        if (learningHold) {
          learningHold = false;
          learningHoldReason = '';
          setLearningStatus('Present. The lesson can continue.');
          toast('You are back. Continuing the lesson.');
          if (!lecturePaused && !learningCheckOpen) readCurrentAloud();
        } else if (status && !status.textContent) {
          setLearningStatus('Watching for presence.');
        } else if (data && data.state === 'present') {
          setLearningStatus(meshReady ? 'Present. Face mesh is watching.' : 'Present and learning.');
        }
        return;
      }
      const reason = data.reason || 'paused';
      setLearningStatus((data.suspected_cheating ? 'Paused: ' : 'Paused until you are here. ') + reason);
      if (learningHold && holdGroup(learningHoldReason) === holdGroup(reason)) return;
      learningHold = true;
      learningHoldReason = reason;
      clearAutoAdvance();
      stopSpeech();
      theodoreAvatar?.setState('listening');
      if (data.speech) speakText(data.speech, null, true, 'guard');
      toast(data.speech || 'The lesson is paused.');
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
      const idea = firstLessonSentence(turn.narration || turn.display_body || turn.title || '');
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
        restoreStudentCamPosition();
        return;
      }
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) return;
      try {
        studentCamStream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: 'user', width: { ideal: 640 }, height: { ideal: 360 } },
          audio: false,
        });
        const video = $('student-cam-video');
        if (video) {
          video.srcObject = studentCamStream;
          await video.play().catch(() => {});
        }
        const box = $('student-cam');
        if (box) box.hidden = false;
        restoreStudentCamPosition();
        if (!studentCamTimer) studentCamTimer = window.setInterval(() => { void studentCameraSample(); }, 1000);
      } catch (error) {
        setLearningStatus('Camera is required. Allow it to continue.');
        if (!studentCamTimer) studentCamTimer = window.setInterval(() => { void studentCameraSample(); }, 1000);
      }
    }

    function setStudentCamHidden(hidden) {
      const box = $('student-cam');
      if (!box) return;
      box.classList.toggle('is-hidden', hidden);
      const video = $('student-cam-video');
      if (video) video.setAttribute('aria-hidden', hidden ? 'true' : 'false');
      const button = $('student-cam-hide');
      if (!button) return;
      button.textContent = hidden ? 'Show camera' : 'Hide';
      button.setAttribute('aria-pressed', String(hidden));
      button.title = hidden
        ? 'Show your camera preview. The camera stays on either way.'
        : 'Hide the preview. The camera stays on.';
    }

    function stopStudentCamera() {
      if (studentCamTimer) {
        window.clearInterval(studentCamTimer);
        studentCamTimer = 0;
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

    function placeStudentCam() {
      const cam = $('student-cam');
      const overlay = $('presenter-overlay');
      if (!cam || !overlay) return;
      const home = presenterActive() ? overlay : document.body;
      if (cam.parentElement !== home) home.appendChild(cam);
      restoreStudentCamPosition();
    }

    function clampStudentCam(left, top) {
      const box = $('student-cam');
      if (!box) return null;
      const width = box.offsetWidth || 176;
      const height = box.offsetHeight || 148;
      const maxX = Math.max(8, window.innerWidth - width - 8);
      const maxY = Math.max(8, window.innerHeight - height - 8);
      const x = Math.max(8, Math.min(maxX, left));
      const y = Math.max(8, Math.min(maxY, top));
      box.style.left = x + 'px';
      box.style.top = y + 'px';
      box.style.right = 'auto';
      return { left: x, top: y };
    }

    function restoreStudentCamPosition() {
      const box = $('student-cam');
      if (!box || box.hidden) return;
      try {
        const saved = JSON.parse(localStorage.getItem('studio.cam.pos') || 'null');
        if (!saved || typeof saved.left !== 'number' || typeof saved.top !== 'number') return;
        clampStudentCam(saved.left, saved.top);
      } catch (_) {}
    }

    function enableStudentCamDrag() {
      const box = $('student-cam');
      if (!box || box.dataset.dragReady) return;
      box.dataset.dragReady = '1';
      let drag = null;
      box.addEventListener('pointerdown', (event) => {
        if (event.button !== 0) return;
        if (event.target.closest('button, a, input, textarea, select')) return;
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
      requestAnimationFrame(() => theodoreAvatar?.resize());
    }

    function togglePresenterMode() {
      if (presenterActive()) exitPresenterMode();
      else enterPresenterMode();
    }

    function setCaptionsEnabled(enabled) {
      captionsEnabled = !!enabled;
      $('teach-stage').classList.toggle('captions-off', !captionsEnabled);
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
      btn.textContent = paused ? 'Resume' : 'Pause';
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
      return data;
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
        method:'POST', headers:{'content-type':'application/json'},
        body: JSON.stringify({ source_id: selectedSource, body, page_index, author: 'reviewer' })
      });
      $('comment-body').value = '';
      const data = await api('/api/studio/sources/' + encodeURIComponent(selectedSource));
      renderComments(data.comments || []);
      toast('Comment saved for training');
    }

    async function runTraining() {
      $('train-status').textContent = 'Scanning corpus…';
      const data = await api('/api/studio/training/run', {
        method:'POST', headers:{'content-type':'application/json'},
        body: JSON.stringify({ extract_text: true, seed_page_hints: true })
      });
      $('train-status').textContent =
        `Run ${data.run_id}: scanned ${data.documents_scanned}, incorporate ${data.incorporate_ids.length}, reject ${data.reject_ids.length}, review queue ${data.review_queue_ids.length}`;
      await refreshCorpus();
      await refreshCourses();
      toast('Training run complete');
    }

    async function runOfflineTrainer() {
      $('train-status').textContent = 'Offline trainer running (no network)…';
      const data = await api('/api/studio/training/offline', {
        method:'POST', headers:{'content-type':'application/json'},
        body: JSON.stringify({ epochs: 25, run_scan: true, fit_passes: 2 })
      });
      $('train-status').textContent =
        `Offline ${data.run_id}: epochs ${data.epoch}, best ${Number(data.best_course_score || 0).toFixed(3)}, ${data.status}`;
      await refreshCourses();
      toast('Offline trainer finished — course builds now use the learned model');
    }

    async function buildCourse() {
      const category = $('build-category').value;
      const title = $('build-title').value.trim() || null;
      teachLanguage = $('teach-lang').value || 'en';
      const data = await api('/api/studio/courses/build', {
        method:'POST', headers:{'content-type':'application/json'},
        body: JSON.stringify({
          category: category || null, title, max_slides: 12,
          only_incorporate: true, language: teachLanguage
        })
      });
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
          detail: 'California permit prep · ' + driver.length + ' lessons, including 140 traffic signs',
          kind: 'cert',
          lessons: driver,
          featured: true
        },
        {
          id: 'food-safety',
          title: 'Food safety',
          detail: 'California food handler prep · ' + food.length + ' modules in order',
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
      if (pinnedCourse) {
        document.body.classList.add('public-course');
        library = library.filter((row) => row.id === pinnedCourse);
      }
      renderLibrary();
      if (pinnedCourse) {
        if (!library.length) toast('That course is not on this page.');
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

    async function teachLibraryLesson() {
      const lesson = activeCourse && activeCourse.lessons[lessonCursor];
      if (!lesson) return;
      teachLanguage = ($('teach-lang') && $('teach-lang').value) || teachLanguage || 'en';
      const now = $('library-now');
      if (now) {
        now.textContent = activeCourse.title + ' · part ' + (lessonCursor + 1) +
          ' of ' + activeCourse.lessons.length + ' · ' + (lesson.title || '');
      }
      let data;
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
      return ['teach-lang', 'teach-lang-stage'].map($).filter(Boolean);
    }

    function syncLanguageSelects() {
      languageSelects().forEach((sel) => { sel.value = teachLanguage; });
    }

    function applyTeachLanguage(code) {
      teachLanguage = code || 'en';
      syncLanguageSelects();
      if (activeCourse) teachLibraryLesson().catch((e) => toast(String(e.message || e)));
    }

    async function loadLanguages() {
      const data = await api('/api/studio/languages');
      (data.languages || []).forEach((l) => { languageNames[l.code] = l.name; });
      const html = (data.languages || []).map((l) =>
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
        method:'POST', headers:{'content-type':'application/json'},
        body: JSON.stringify({
          session_id: teachSession, course_id: selectedCourse, profile: profileFromForm(),
          learner_id: learnerId,
          focus_gaps: true, known_objective_ids: [],
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
        ja:'ja-JP', ko:'ko-KR', vi:'vi-VN', th:'th-TH', id:'id-ID', sw:'sw-KE',
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
      autoAdvanceTimer = setTimeout(() => {
        autoAdvanceTimer = null;
        finishSlideBeat();
      }, delayMs);
    }

    function finishSlideBeat() {
      if (learningHold) return;
      if (sampleIsComplete()) return;
      if (lecturePaused || beatHandled) return;
      beatHandled = true;
      clearAutoAdvance();
      const checkpoint = (lastTeachPayload && lastTeachPayload.activity_checkpoint) || {};
      if (checkpoint.due) {
        presentActivityCheckpoint(checkpoint);
        return;
      }
      continueAfterActivity();
    }

    function presentActivityCheckpoint(checkpoint) {
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
      if (activeCourse && lessonCursor < activeCourse.lessons.length - 1) {
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
      const automatic = !!(opts && opts.auto);
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
      clearAutoAdvance();
      advancing = true;
      stopSpeech();
      theodoreAvatar?.setState('idle');
      try {
        const data = await api('/api/studio/teach/advance', {
          method:'POST', headers:{'content-type':'application/json'},
          body: JSON.stringify({ session_id: teachSession })
        });
        renderTeach(data);
      } finally {
        advancing = false;
      }
    }

    function toggleLecturePause() {
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

    function showTopicExamples(payload) {
      const examples = (payload && (payload.topic_examples || payload.examples)) || [];
      const exBox = $('teach-examples');
      if (!exBox || !examples.length || !(payload.show_examples || payload.topic_jump)) return;
      exBox.style.display = 'block';
      exBox.innerHTML = '<strong>Example</strong><ol>' +
        examples.map((line) => `<li>${esc(line)}</li>`).join('') + '</ol>';
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
      if (paintVisualChallenge(box, kind, payload)) return;
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
          continueAfterActivity();
        };
        return;
      }
      const opts = payload.options || [];
      box.innerHTML = `<strong>${esc(pendingGame.prompt)}</strong>` +
        opts.map((c, i) => `<button type="button" data-i="${i}">${esc(c)}</button>`).join('') +
        `<button type="button" class="secondary mic-btn" id="game-mic">Speak your answer</button>` +
        `<p class="heard" id="game-heard"></p>`;
      const submitGame = async (index) => {
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
    }

    function speakText(text, ttsMeta, holdLesson, kind) {
      if (learningHold && kind !== 'guard' && kind !== 'learn-check') return;
      if (learningCheckOpen && kind !== 'learn-check' && kind !== 'guard' && kind !== 'checkpoint') return;
      if (kind !== 'adapt' && kind !== 'adapt-resume' && kind !== 'guard') attentionResume = '';
      if (lecturePaused && !holdLesson) return;
      if (window.__THEODORE_LIVE_AUDIO_ACTIVE__ && !window.__THEODORE_LIVE_AUDIO_HOLD__) {
        if (kind !== 'talk') return;
        window.TheodoreLiveAudio?.pauseRecognition();
      }
      stopSpeech();
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
      const clip = holdLesson ? null : manifestClip(ttsMeta);
      const upcoming = nextSlideAudioUrl(ttsMeta);
      if (clip) playManifest(clip.url, clip.durationMs, 0);
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
        u.lang = (ttsMeta && ttsMeta.language) || teachLanguage || 'en';
        u.volume = 1;
        const voices = window.speechSynthesis.getVoices ? window.speechSynthesis.getVoices() : [];
        const lang = String(u.lang || 'en').slice(0, 2).toLowerCase();
        const same = (voices || []).filter((voice) => String(voice.lang || '').toLowerCase().startsWith(lang));
        if (!same.length && lang !== 'en') {
          setLearningStatus('This device has no ' + languageLabel(lang) + ' voice. Allow the lesson voice to load.');
          theodoreAvatar?.stopSpeaking();
          if (!holdLesson) armDurationWatchdog(gen, token, narrationDwellMs(spoken));
          return;
        }
        const maleName = /male|\b(guy|daniel|alex|fred|aaron|oliver|james|brian|arthur|eric)\b/i;
        const femaleName = /female|\b(samantha|aria|victoria|karen|allison|ava|susan|zoe|moira|tessa|fiona|serena|jenny)\b/i;
        const tutorFemale = courseVoiceGender !== 'male';
        const pool = tutorFemale ? same.filter((voice) => !maleName.test(voice.name || '')) : same;
        const candidates = pool.length ? pool : same;
        const wanted = tutorFemale ? femaleName : maleName;
        const named = candidates.find((voice) => wanted.test(voice.name || ''));
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
        u.onend = () => finishUtterance(gen, token);
        u.onerror = () => {
          theodoreAvatar?.stopSpeaking();
          if (!holdLesson && gen === speechGen && token === playToken && !settled) {
            armDurationWatchdog(gen, token, narrationDwellMs(spoken));
          }
        };
        if (!holdLesson) armDurationWatchdog(gen, token, narrationDwellMs(spoken));
        theodoreAvatar?.speak(spoken);
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
          clearStallTimer();
          armForClip();
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
      const gender = courseVoiceGender || (ttsMeta && ttsMeta.voice_gender) || 'female';
      const attempt = (n) => fetch('/api/studio/tts', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ text: text, language: language, gender: gender })
      }).then((res) => {
        if (!res.ok) throw new Error('tts ' + res.status);
        return res.blob();
      }).then((blob) => {
        if (!blob || !blob.size) throw new Error('empty voice clip');
        return URL.createObjectURL(blob);
      }).catch((err) => {
        if (n >= 2) throw err;
        return new Promise((resolve) => setTimeout(resolve, 600 * (n + 1)))
          .then(() => attempt(n + 1));
      });
      return attempt(0);
    }
    function paintProceedCue() {
      const text = $('proceed-cue-text');
      const btn = $('btn-start-voice');
      if (!text || !btn) return;
      const live = !!window.__THEODORE_LIVE_AUDIO_ACTIVE__;
      text.textContent = live
        ? 'Speak to Theodore, or click the screen to continue.'
        : 'Click the screen to continue, or press Start and speak.';
      btn.textContent = live ? 'Listening' : 'Start';
      btn.setAttribute('aria-pressed', live ? 'true' : 'false');
    }

    async function proceedByClick() {
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
      if (event.detail?.active && !event.detail?.paused && !window.__THEODORE_LIVE_AUDIO_HOLD__) stopSpeech();
    });
    window.addEventListener('theodore-live-audio-speech', (event) => {
      if (lecturePaused) return;
      if (event.detail?.speaking) {
        theodoreAvatar?.speak(event.detail.text || ' ');
        return;
      }
      theodoreAvatar?.stopSpeaking();
    });
    window.addEventListener('theodore-live-audio-level', (event) => {
      if (lecturePaused) return;
      theodoreAvatar?.setVoiceLevel(Number(event.detail && event.detail.level) || 0);
    });
    window.addEventListener('theodore-live-audio-user', (event) => {
      if (lecturePaused) return;
      if (event.detail && event.detail.talking) theodoreAvatar?.setState('listening');
      else if (!theodoreAvatar?.speaking) theodoreAvatar?.setState('idle');
    });
    window.addEventListener('theodore-live-audio-utterance', (event) => {
      const text = event.detail && event.detail.text;
      if (!text || lecturePaused) return;
      queueLiveTopic(text);
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
      const host = $('teach-visual-timeline');
      if (!host) return;
      host.hidden = true;
      host.innerHTML = '';
      host.removeAttribute('data-style');
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
      cues.forEach((cue, cueIndex) => {
        const layers = Array.isArray(cue.layers) && cue.layers.length
          ? cue.layers : [{ kind: cue.kind, text: cue.text, url: cue.url, alt: cue.alt }];
        layers.forEach((layer, layerIndex) => {
          const el = document.createElement('div');
          el.className = 'visual-layer';
          el.dataset.cue = String(cueIndex);
          el.dataset.transition = layer.transition || cue.transition || 'fade';
          el.style.zIndex = String(Number(layer.z_index ?? layerIndex) || 0);
          const kind = String(layer.kind || 'text');
          const url = String(layer.url || layer.src || '');
          const text = String(layer.text || layer.label || cue.text || '');
          if ((kind === 'image' || kind === 'picture') && url) {
            const image = document.createElement('img');
            image.src = url;
            image.alt = String(layer.alt || text || '');
            image.loading = 'eager';
            el.appendChild(image);
          } else if (kind === 'svg' && String(layer.svg || layer.content || '').trim().startsWith('<svg')) {
            el.innerHTML = String(layer.svg || layer.content);
            el.setAttribute('role', 'img');
            el.setAttribute('aria-label', String(layer.alt || text || 'Lesson diagram'));
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

    function syncVisualTimeline(atSeconds, force) {
      if (!visualTimeline || !Array.isArray(visualTimeline.cues)) return;
      const at = Math.max(0, Number(atSeconds) || 0);
      let active = 0;
      for (let i = 0; i < visualTimeline.cues.length; i += 1) {
        const cue = visualTimeline.cues[i] || {};
        const start = Number(cue.start_s) || 0;
        const duration = Math.max(0.001, Number(cue.duration_s) || 0.001);
        if (at >= start && at < start + duration) active = i;
        else if (at >= start) active = i;
      }
      if (!force && active === visualCueIndex) return;
      visualCueIndex = active;
      const host = $('teach-visual-timeline');
      if (!host) return;
      host.querySelectorAll('.visual-layer').forEach((layer) => {
        layer.classList.toggle('is-active', Number(layer.dataset.cue) === active);
      });
      const cue = visualTimeline.cues[active] || {};
      if (cue.alt) host.setAttribute('aria-label', String(cue.alt));
    }

    function renderTeach(payload) {
      teachEpoch += 1;
      stopSpeech();
      stopStudentMic();
      const staleReply = $('talk-reply');
      if (staleReply) staleReply.textContent = '';
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
      const usePhoto = Boolean(photoUrl);
      if (usePhoto) clearVisualTimeline();
      const hasVisualTimeline = !usePhoto && renderVisualTimeline(payload);
      const hasStoryboard = !usePhoto && !hasVisualTimeline && Boolean(sbSvg.trim());
      paintLessonPhoto(photoUrl, payload.photo_transition || 'fade', turn.title || '');
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
      const adapt = (turn.adaptations_applied || []).join(', ') || 'no adaptations';
      const prog = payload.progress || {};
      const obj = payload.objective ? payload.objective.title : '';
      const lang = payload.language || teachLanguage;
      const spoken = payload.spoken_language || lang;
      const lessonText = $('teach-stage').querySelector('.lesson-stage-content');
      const rtl = ['ar', 'fa', 'he', 'ur'].includes(spoken);
      lessonText.setAttribute('lang', spoken || 'en');
      lessonText.setAttribute('dir', rtl ? 'rtl' : 'ltr');
      const covered = typeof prog.completion_percent === 'number'
        ? ` · ${prog.completion_percent}% of the course` : '';
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
      if (payload.sample && payload.sample.complete) {
        lecturePaused = true;
        if ($('btn-pause')) setPauseButton(true);
        stopSpeech();
        return;
      }
      if (window.__THEODORE_LIVE_AUDIO_ACTIVE__ && !window.__THEODORE_LIVE_AUDIO_HOLD__) {
        theodoreAvatar?.speak(turn.narration || turn.display_body || turn.title || '');
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
    on('btn-pause', 'click', () => toggleLecturePause());
    on('btn-fullscreen', 'click', togglePresenterMode);
    on('student-cam-hide', 'click', () => {
      const box = $('student-cam');
      setStudentCamHidden(!(box && box.classList.contains('is-hidden')));
    });
    enableStudentCamDrag();
    on('btn-captions', 'click', () => setCaptionsEnabled(!captionsEnabled));
    let proceedClickTimer = null;
    on('teach-stage', 'click', (event) => {
      if (event.target.closest('button, input, select, textarea, a, label, .lesson-window-controls, .lesson-toolbar, .talk-panel, .quiz-box, .game-box, .activity, .theodore-avatar-wrap')) return;
      clearTimeout(proceedClickTimer);
      proceedClickTimer = setTimeout(() => {
        proceedClickTimer = null;
        proceedByClick().catch((error) => toast(String(error.message || error)));
      }, 280);
    });
    on('teach-stage', 'dblclick', (event) => {
      if (event.target.closest('button, input, select, textarea, a, .lesson-window-controls')) return;
      clearTimeout(proceedClickTimer);
      proceedClickTimer = null;
      togglePresenterMode();
    });
    on('btn-start-voice', 'click', (event) => {
      event.stopPropagation();
      proceedByVoice().catch((error) => toast(String(error.message || error)));
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
    on('avatar-choice', 'change', (ev) => {
      chooseAvatar(ev.target.value).catch((error) => toast(String(error.message || error)));
    });
    on('teach-lang', 'change', (event) => applyTeachLanguage(event.target.value));
    on('teach-lang-stage', 'change', (event) => applyTeachLanguage(event.target.value));
    // Escape leaves fullscreen without telling us, so follow the browser back.
    document.addEventListener('fullscreenchange', () => {
      if (!document.fullscreenElement) exitPresenterMode();
    });
    on('btn-avatar', 'click', () => setAvatarVisible(!avatarVisible));
    on('btn-avatar-hide', 'click', () => setAvatarVisible(false));

    avatarPrefs = loadAvatarPrefs();
    selectedAvatarId = avatarPrefs.presenterChosen && avatarPrefs.presenter
      ? avatarPrefs.presenter
      : 'student';
    initAvatarDrag();
    setAvatarVisible(
      typeof avatarPrefs.on === 'boolean' ? avatarPrefs.on : SHOW_AVATAR, false);
    paintSampleBanner(null);
    loadLanguages().catch(() => {});
    loadAvatarChoices().catch((error) => toast(String(error.message || error)));
    loadLibrary().catch((e) => toast(String(e.message || e)));
    updateLessonWindowControls();

"""

def render_studio_page() -> str:
    return (
        """<!doctype html>\n<html lang="en">\n<head>\n  <meta charset="utf-8" />\n  <meta name="viewport" content="width=device-width, initial-scale=1" />\n  <title>Theodore Course Studio</title>\n  <style>\n"""
        + STUDIO_CSS
        + """</style>
  <script type="importmap">
    {"imports":{"three":"/api/studio/avatar/three.module.js"}}
  </script>
</head>
<body class="theme-study">
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
      <h2><span class="mark" aria-hidden="true"><svg viewBox="0 0 28 28" width="22" height="22"><path d="M4 6h8c1.4 1 2.8 1 4 0h8v16h-8c-1.2 1-2.6 1-4 0H4V6z" fill="none" stroke="#1e3a5f" stroke-width="1.8"/><path d="M14 7v14" stroke="#1e3a5f" stroke-width="1.4"/></svg></span> Course library</h2>
      <div class="row">
        <label>Language <select id="teach-lang" style="min-width:12rem"></select></label>
      </div>
      <div class="status" id="library-now">Choose a course to begin.</div>
      <div class="list library" id="library-list"></div>
    </div>
    <div class="panel">
      <div id="teach-stage-home">
      <div class="teach-stage captions-off" id="teach-stage">
        <div class="lesson-window-controls" aria-label="Lesson window controls">
          <label class="lesson-lang">Language
            <select id="teach-lang-stage" aria-label="Lesson language"></select>
          </label>
          <button id="btn-captions" class="is-off" type="button" aria-pressed="false" aria-label="Show lesson captions" title="Show captions">CC</button>
          <button id="btn-fullscreen" type="button" aria-label="Expand lesson to full screen" title="Full screen">⛶</button>
        </div>
        <h3 id="teach-title">Your lesson</h3>
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
              <p>Click the screen to start, or press Start and speak.</p>
            </div>
            <div class="proceed-cue" id="proceed-cue">
              <p id="proceed-cue-text">Click the screen to continue, or press Start and speak.</p>
              <button id="btn-start-voice" type="button">Start</button>
            </div>
            <div class="body" id="teach-body"></div>
            <p id="attention-aside" class="attention-aside" hidden></p>
            <div class="modality-row" id="teach-modalities"></div>
            <div class="examples-box" id="teach-examples"></div>
            <div class="lang-warning" id="lang-warning" style="display:none"></div>
            <div class="sample-banner" id="sample-banner" style="display:none" role="status"></div>
            <div class="activity" id="teach-activity" style="display:none"></div>
            <div class="narr" id="teach-narr"></div>
            <div class="absorb-note" id="absorb-note" hidden>Take a moment with this page. The next one waits so you can study it.</div>
            <div class="status" id="teach-adapt"></div>
          </div>
        </div>
        <div class="quiz-box" id="quiz-box" style="display:none"></div>
        <div class="game-box" id="game-box" style="display:none"></div>
        <div class="row lesson-toolbar" id="lesson-toolbar">
          <button id="btn-pause" class="secondary" type="button">Pause</button>
          <button id="btn-start-over" class="secondary" type="button" title="Begin this course again for this account or profile">Start over</button>
          <button id="btn-talk" type="button">Talk</button>
          <button class="secondary" id="btn-avatar" type="button" aria-pressed="false"
                  aria-controls="theodore-avatar-wrap">Show Theodore</button>
          <label class="avatar-choice-label" for="avatar-choice">Presenter
            <select id="avatar-choice" aria-label="Choose a 3D lesson presenter">
              <option value="student">Student</option>
            </select>
          </label>
        </div>
        <div class="talk-panel" id="talk-panel" hidden>
          <h2>Talk about this course</h2>
          <p>Ask a question or leave a comment. Theodore answers only about this training.</p>
          <textarea id="voice-ask" rows="3" placeholder="Ask about a rule, a sign, or this page. You can type or speak."></textarea>
          <div class="talk-reply" id="talk-reply"></div>
          <div class="row">
            <button id="btn-talk-mic" type="button">Speak</button>
            <button id="btn-talk-send" type="button">Send</button>
            <button class="secondary" id="btn-talk-close" type="button">Close</button>
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
      <canvas id="student-cam-sample" hidden></canvas>
      <button type="button" id="student-cam-hide" class="student-cam-hide" aria-pressed="false"
              title="Hide the preview. The camera stays on.">Hide</button>
      <p id="student-cam-status" class="student-cam-status">Watching for presence.</p>
      <p class="student-cam-note">Camera stays on. The lesson pauses if you leave or look away.</p>
    </div>
  </div>
  <div class="toast" id="toast"></div>
  <script>"""
        + STUDIO_JS
        + """\n</script>\n</body>\n</html>\n"""
    )

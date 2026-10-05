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
    .storyboard-concept { font-size:14px; color:#5c5146; margin:8px 0 10px; line-height:1.4; }
    .theodore-avatar-wrap { position:relative; min-height:390px; overflow:hidden; border-radius:18px;
                            background:radial-gradient(ellipse at 50% 60%,rgba(68,214,255,.2),rgba(5,24,34,.72) 65%);
                            border:1px solid rgba(94,224,255,.38); box-shadow:inset 0 0 30px rgba(59,215,255,.14); }
    #theodore-avatar { position:absolute; inset:0; }
    #theodore-avatar canvas { width:100%; height:100%; display:block; filter:drop-shadow(0 0 14px rgba(86,224,255,.5)); }
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
    .presenter-overlay .lesson-toolbar { position:absolute; top:62px; right:18px; z-index:5; }
    .presenter-overlay .storyboard-concept { display:none; }
    .presenter-overlay .picture-stage { display:none; }
    .presenter-overlay .teach-stage .body { font-size:clamp(16px,1.5vw,23px); max-width:72rem; }
    .presenter-overlay .avatar-label { left:50%; right:auto; transform:translateX(-50%);
                                       bottom:12px; white-space:nowrap; }
    .presenter-overlay.has-storyboard .theodore-avatar-wrap { left:2.4%; bottom:calc(42% + 12px);
                                                             height:min(34vh,320px); }
    .presenter-overlay:not(.has-storyboard) .theodore-avatar-wrap { left:2%; bottom:9%; width:28%; height:82%; }
    .presenter-overlay:not(.has-storyboard) .lesson-stage-content { left:28%; right:0; bottom:0; top:0;
                                                                      max-height:none; background:rgba(28,20,14,.78); }
    .presenter-exit { position:absolute; top:14px; right:16px; z-index:3; }
    /* Avatar hidden unless body.avatar-on. No !important here: the show/hide
       toggle has to be able to win, and `hidden` has to keep working. */
    body:not(.avatar-on) .theodore-avatar-wrap { display:none; }
    .teacher-stage-grid, .teacher-stage-grid.has-storyboard { grid-template-columns:1fr; }
    .teacher-stage-grid .storyboard-stage { grid-column:1; grid-row:auto; }
    .presenter-overlay:not(.has-storyboard) .lesson-stage-content { left:0; right:0; top:0; max-height:none; }
    body.avatar-on .teacher-stage-grid,
    body.avatar-on .teacher-stage-grid.has-storyboard { grid-template-columns:minmax(180px, 34%) 1fr; }
    body.avatar-on .teacher-stage-grid .storyboard-stage { grid-column:2; grid-row:1 / span 2; }
    body.avatar-on .presenter-overlay:not(.has-storyboard) .lesson-stage-content { left:28%; top:0; max-height:none; }
    /* Once the avatar has been dragged it is "placed": one fixed-position code
       path for both the dashboard and the presenter overlay, so the drag does
       not have to out-specify the left/bottom rules each mode sets. */
    body.avatar-placed .teacher-stage-grid,
    body.avatar-placed .teacher-stage-grid.has-storyboard { grid-template-columns:1fr; }
    body.avatar-placed .teacher-stage-grid .storyboard-stage { grid-column:1; grid-row:auto; }
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
    @media (max-width:700px) {
      .picture-stage { grid-template-columns:1fr; }
      .teacher-stage-grid { grid-template-columns:1fr; }
      .theodore-avatar-wrap { min-height:320px; }
    }
    @media (prefers-reduced-motion: reduce) {
      .teach-stage, .teach-stage.anim, .theodore-avatar-fallback * { animation:none !important; }
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
    let learnerId = 'learner-demo';
    let theodoreAvatar = null;
    // The lesson plays straight through. Pause is the only hold.
    let lecturePaused = false;
    let talkOpen = false;
    let autoAdvanceTimer = null;
    let advancing = false;
    let speechGen = 0;
    const SLIDE_TRANSITION_MS = 700;
    // Quiet time after the voice finishes so the page can be studied.
    const ABSORB_MS = 12000;
    let library = [];
    let activeCourse = null;
    let lessonCursor = 0;
    let slideVariety = 'straight';
    let slidesSinceCheck = 0;
    let lastCheckPassed = null;
    let beatHandled = false;
    let reviewOpen = false;
    let captionsEnabled = false;
    const reviewScores = { quizzes: [], games: [] };

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
            : `${presenter?.label || 'Presenter'} · 3D teacher`;
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
      if (!avatarCatalog[selectedAvatarId]) {
        selectedAvatarId = data.default_model || Object.keys(avatarCatalog)[0] || 'amina';
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
      saveAvatarPrefs();
      courseVoiceGender = avatarCatalog[presenterId]?.voice_gender || courseVoiceGender;
      if (!avatarVisible) setAvatarVisible(true);
      await initTheodoreAvatar();
      await theodoreAvatar?.setPersona(presenterId);
      $('avatar-state').textContent =
        `${avatarCatalog[presenterId]?.label || 'Presenter'} · 3D teacher`;
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

    function enterPresenterMode() {
      if (presenterActive()) return;
      $('presenter-body').appendChild($('teach-stage'));
      $('presenter-overlay').classList.add('show');
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
      renderLibrary();
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
      await startTeach({ resume: false });
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
      await startTeach({ resume: false });
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
      status.textContent =
        `xAI: ${v.provider || 'local-fallback'}` +
        (v.xai_available ? ' (live key)' : ' (offline fallback)') +
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
          resume: !!opts.resume
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

    function openTalk() {
      if (!teachSession) return toast('Start a course first');
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
      if (!lecturePaused) readCurrentAloud();
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
        he:'he-IL', hi:'hi-IN', zh:'zh-CN', ja:'ja-JP', ko:'ko-KR', vi:'vi-VN',
        th:'th-TH', id:'id-ID', km:'km-KH'
      };
      return map[code] || code;
    }

    function stopStudentMic() {
      if (studentRec) {
        try { studentRec.onresult = null; studentRec.onerror = null; studentRec.onend = null; studentRec.stop(); } catch (_) {}
        studentRec = null;
      }
      document.querySelectorAll('button.is-listening').forEach((el) => {
        el.classList.remove('is-listening');
        if (el.dataset.label) el.textContent = el.dataset.label;
      });
    }

    async function ensureMic() {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        toast('This browser cannot use the microphone. Type instead.');
        return false;
      }
      if (micReady) return true;
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        stream.getTracks().forEach((track) => track.stop());
        micReady = true;
        return true;
      } catch (_) {
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
      rec.onerror = (event) => {
        const err = (event && event.error) || '';
        if (err === 'not-allowed' || err === 'service-not-allowed') {
          micReady = false;
          toast('Allow the microphone, then tap Speak again.');
        } else if (err === 'no-speech') toast('No speech heard. Try again.');
        else if (err && err !== 'aborted') toast('Could not hear that. Try again or type.');
      };
      rec.onend = () => {
        if (button) {
          button.classList.remove('is-listening');
          if (button.dataset.label) button.textContent = button.dataset.label;
        }
        if (studentRec === rec) studentRec = null;
      };
      try { rec.start(); }
      catch (_) { toast('Tap Speak again to start the microphone.'); }
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
      if (!teachSession) return toast('Start a course first');
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
      if (!teachSession) return toast('Start a course first');
      stopSpeech();
      theodoreAvatar?.setState('thinking');
      const data = await api('/api/studio/teach/voice/respond', {
        method:'POST', headers:{'content-type':'application/json'},
        body: JSON.stringify({ session_id: teachSession, message: msg })
      });
      const voice = data.voice || {};
      const reply = voice.message || '';
      const slot = $('talk-reply');
      if (slot) slot.textContent = reply;
      $('teach-narr').textContent = reply;
      if (data.turn && data.turn.avatar) theodoreAvatar?.setScript(data.turn.avatar);
      speakText(reply, data.tts, true);
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
      // Teach straight through. A quiz or game waits 4 slides on hard pages
      // and up to 8 on easy ones, instead of stopping after every page.
      slidesSinceCheck += 1;
      if (slidesSinceCheck < checkGapFor(payload)) {
        return Math.random() < 0.45 ? 'examples' : 'straight';
      }
      slidesSinceCheck = 0;
      return Math.random() < 0.5 ? 'quiz' : 'game';
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
      if (lecturePaused || beatHandled || talkOpen) return;
      autoAdvanceTimer = setTimeout(() => {
        autoAdvanceTimer = null;
        finishSlideBeat();
      }, delayMs);
    }

    function finishSlideBeat() {
      if (lecturePaused || beatHandled) return;
      beatHandled = true;
      clearAutoAdvance();
      if (slideVariety === 'quiz') {
        popQuiz().catch(() => continueAfterActivity());
        return;
      }
      if (slideVariety === 'game') {
        playGame().catch(() => continueAfterActivity());
        return;
      }
      continueAfterActivity();
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
      showAbsorb(true);
      scheduleAutoAdvance(ABSORB_MS);
    }

    function showAbsorb(on) {
      const note = $('absorb-note');
      if (note) note.hidden = !on;
    }

    async function nextSlide(opts) {
      const automatic = !!(opts && opts.auto);
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
        return;
      }
      setPauseButton(false);
      readCurrentAloud();
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
        if (passed) {
          toast('Correct');
          box.style.display = 'none';
          await continueAfterActivity();
          return;
        }
        const correction = res.correction || {};
        const correctChoice = correction.correct_choice ||
          ((pendingPop.choices || [])[pendingPop.correct_index] || '');
        const explanation = correction.explanation ||
          ('The key learning point is: ' + correctChoice);
        const correctionText = 'Not quite. The correct answer is: ' +
          correctChoice + '. ' + explanation;
        box.innerHTML = `<div class="quiz-correction" role="status">
          <strong>Not quite — here is the correction.</strong>
          <p><b>Correct answer:</b> ${esc(correctChoice)}</p>
          <p><b>Why:</b> ${esc(explanation)}</p>
          <p class="heard">Listen to the explanation. The course continues automatically.</p>
        </div>`;
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
      continueAfterActivity();
    }

    async function playGame() {
      stopSpeech();
      theodoreAvatar?.setState('ask');
      pendingGame = await api('/api/studio/teach/game', {
        method:'POST', headers:{'content-type':'application/json'},
        body: JSON.stringify({ session_id: teachSession })
      });
      const box = $('game-box');
      box.style.display = 'block';
      const kind = pendingGame.kind || (pendingGame.payload && pendingGame.payload.kind) || '';
      const payload = pendingGame.payload || {};
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

    function stopSpeech() {
      speechGen += 1;
      clearAutoAdvance();
      if (window.speechSynthesis) window.speechSynthesis.cancel();
      if (serverAudio) {
        try { serverAudio.onended = null; serverAudio.onerror = null; } catch (_) {}
        try { serverAudio.pause(); } catch (_) {}
        serverAudio = null;
      }
      if (neuralObjectUrl) {
        try { URL.revokeObjectURL(neuralObjectUrl); } catch (_) {}
        neuralObjectUrl = null;
      }
      theodoreAvatar?.stopSpeaking();
    }

    function speakText(text, ttsMeta, holdLesson) {
      if (lecturePaused && !holdLesson) return;
      if (window.__THEODORE_LIVE_AUDIO_ACTIVE__) return;
      stopSpeech();
      const spoken = text || '';
      const gen = speechGen;
      // Silent mode still walks the slides. Pause is the only thing that holds.
      const speakToggle = $('auto-speak');
      if (!holdLesson && speakToggle && !speakToggle.checked) {
        scheduleAutoAdvance(narrationDwellMs(spoken));
        return;
      }
      if (holdLesson && speakToggle && !speakToggle.checked) return;
      // If the browser never fires "ended", still leave time to study the page.
      // A Talk reply stays on this page; it does not start the next slide.
      if (!holdLesson) scheduleAutoAdvance(narrationDwellMs(spoken) + ABSORB_MS);
      // One neural voice for the whole course. Retry that voice before the
      // browser's built-in voice, which is a different speaker.
      const done = () => {
        if (gen !== speechGen) return;
        if (holdLesson) theodoreAvatar?.stopSpeaking();
        else onNarrationEnded(gen);
      };
      const playServer = (src) => {
        serverAudio = new Audio(src);
        serverAudio.onended = done;
        theodoreAvatar?.speak(spoken, serverAudio);
        return serverAudio.play();
      };
      const playDevice = () => {
        if (!window.speechSynthesis) return;
        const u = new SpeechSynthesisUtterance(spoken);
        u.lang = (ttsMeta && ttsMeta.language) || teachLanguage || 'en';
        const voices = window.speechSynthesis.getVoices ? window.speechSynthesis.getVoices() : [];
        const lang = String(u.lang || 'en').slice(0, 2).toLowerCase();
        const same = (voices || []).filter((voice) => String(voice.lang || '').toLowerCase().startsWith(lang));
        const wanted = courseVoiceGender === 'male' ? /male|guy|daniel|alex/i : /female|samantha|aria|victoria|karen/i;
        const named = same.find((voice) => wanted.test(voice.name || ''));
        if (named || same[0]) u.voice = named || same[0];
        u.onboundary = (event) => theodoreAvatar?.speechBoundary(event.charIndex || 0);
        u.onend = done;
        u.onerror = () => theodoreAvatar?.stopSpeaking();
        theodoreAvatar?.speak(spoken);
        window.speechSynthesis.speak(u);
      };
      fetchLockedVoice(spoken, ttsMeta).then((src) => {
        if (gen !== speechGen) {
          try { URL.revokeObjectURL(src); } catch (_) {}
          return;
        }
        neuralObjectUrl = src;
        playServer(src).catch(() => { if (gen === speechGen) playDevice(); });
      }).catch(() => { if (gen === speechGen) playDevice(); });
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
    window.addEventListener('theodore-live-audio', (event) => {
      if (event.detail?.active) stopSpeech();
    });

    function renderTeach(payload) {
      stopStudentMic();
      lastTeachPayload = payload;
      beatHandled = false;
      showAbsorb(false);
      slideVariety = pickLearnVariety(payload);
      const turn = payload.turn || payload;
      if (payload.voice_gender) {
        courseVoiceGender = payload.voice_gender;
        theodoreAvatar?.setPersona(payload.voice_gender);
      }
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
      const hasStoryboard = Boolean(sbSvg.trim());
      stage.classList.toggle('has-storyboard', hasStoryboard);
      $('presenter-overlay').classList.toggle('has-storyboard', hasStoryboard);
      $('teacher-stage-grid').classList.toggle('has-storyboard', hasStoryboard);
      if (hasStoryboard) {
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
      const examples = payload.examples || [];
      const exBox = $('teach-examples');
      if (exBox && examples.length && slideVariety === 'examples') {
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
      const provider = (payload.voice && payload.voice.provider) || 'slide';
      $('teach-narr').textContent = 'Theodore (' + provider + '): ' + (turn.narration || '');
      const adapt = (turn.adaptations_applied || []).join(', ') || 'no adaptations';
      const prog = payload.progress || {};
      const obj = payload.objective ? payload.objective.title : '';
      const lang = payload.language || teachLanguage;
      const spoken = payload.spoken_language || lang;
      const lessonText = $('teach-stage').querySelector('.lesson-stage-content');
      const rtl = ['ar', 'fa', 'he', 'ur'].includes(spoken);
      lessonText.setAttribute('lang', spoken || 'en');
      lessonText.setAttribute('dir', rtl ? 'rtl' : 'ltr');
      $('teach-adapt').textContent =
        `${adapt} · lang ${esc(lang)} · focus: ${esc(obj)} · known ${prog.known || 0} / gaps ${prog.gaps || 0}`;
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
      renderReview();
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
    on('btn-next', 'click', () => nextSlide().catch((e) => toast(String(e.message || e))));
    on('btn-pause', 'click', () => toggleLecturePause());
    on('btn-fullscreen', 'click', togglePresenterMode);
    on('btn-captions', 'click', () => setCaptionsEnabled(!captionsEnabled));
    on('teach-stage', 'dblclick', (event) => {
      if (event.target.closest('button, input, select, textarea, a, .lesson-window-controls')) return;
      togglePresenterMode();
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
    selectedAvatarId = avatarPrefs.presenter || 'amina';
    initAvatarDrag();
    setAvatarVisible(
      typeof avatarPrefs.on === 'boolean' ? avatarPrefs.on : SHOW_AVATAR, false);
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
          <div id="teach-storyboard" class="storyboard-stage" hidden aria-hidden="true"></div>
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
              <p>Choose a course on the left. Theodore will read each page aloud.</p>
            </div>
            <div class="body" id="teach-body"></div>
            <div class="modality-row" id="teach-modalities"></div>
            <div class="examples-box" id="teach-examples"></div>
            <div class="lang-warning" id="lang-warning" style="display:none"></div>
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
          <button id="btn-talk" type="button">Talk</button>
          <button class="secondary" id="btn-avatar" type="button" aria-pressed="false"
                  aria-controls="theodore-avatar-wrap">Show Theodore</button>
          <label class="avatar-choice-label" for="avatar-choice">Presenter
            <select id="avatar-choice" aria-label="Choose a 3D lesson presenter">
              <option value="amina">Amina</option>
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
  </div>
  <div class="toast" id="toast"></div>
  <script>"""
        + STUDIO_JS
        + """\n</script>\n</body>\n</html>\n"""
    )

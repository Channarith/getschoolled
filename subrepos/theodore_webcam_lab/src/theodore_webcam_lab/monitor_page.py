"""Embedded live-monitor dashboard (CSS + JS + HTML).

Kept as one module so every knob, metric, and button stays in sync with the
FastAPI routes in ``main.py``.
"""

from __future__ import annotations

from theodore_webcam_lab.absence_phrases import ABSENCE_PHRASES

MONITOR_CSS = """
    body { margin: 0; font-family: Arial, sans-serif; background: #0f172a; color: #e2e8f0; }
    .layout { display: grid; grid-template-columns: 1.2fr 1fr; gap: 12px; padding: 12px; }
    .panel { background: #111827; border: 1px solid #334155; border-radius: 8px; padding: 10px; }
    .panel h2 { margin: 0 0 8px 0; font-size: 16px; }
    .panel h3 { margin: 10px 0 6px; font-size: 13px; color: #93c5fd; }
    .summary-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; }
    .metric { background: #1f2937; border-radius: 6px; padding: 6px; font-size: 12px; }
    .metric .v { font-size: 16px; font-weight: bold; margin-top: 4px; }
    .windows { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 12px; }
    .student { background: #1f2937; border: 1px solid #334155; border-radius: 8px; padding: 8px;
               transition: box-shadow 0.2s, border-color 0.2s; }
    .student.cheating { border-color: #ef4444; box-shadow: 0 0 0 2px rgba(239,68,68,0.35); }
    .student.silhouette { border-color: #f59e0b; }
    .student.flash { box-shadow: 0 0 0 3px rgba(59,130,246,0.7); }
    .student h3 { margin: 0 0 6px 0; font-size: 14px; color: #e2e8f0; }
    .kv { display: flex; justify-content: space-between; font-size: 12px; margin: 3px 0; gap: 8px; }
    progress { width: 100%; height: 9px; }
    .alerts { list-style: none; padding: 0; margin: 0; max-height: 280px; overflow-y: auto; }
    .alerts li { margin-bottom: 8px; font-size: 12px; background: #1f2937; border: 1px solid #334155;
                 border-radius: 6px; padding: 8px; }
    .alerts li.high { border-color: #ef4444; background: #3f1d1d; }
    .alerts li.medium { border-color: #f59e0b; background: #3b2f14; }
    .alerts li.acked { opacity: 0.55; }
    .alerts .actions { display: flex; gap: 6px; margin-top: 6px; flex-wrap: wrap; }
    select, button, input[type=range], input[type=text], input[type=number], textarea {
      font-size: 11px; }
    button { cursor: pointer; background: #334155; color: #e2e8f0;
             border: 1px solid #475569; border-radius: 4px; padding: 2px 8px; }
    button.primary { background: #1d4ed8; border-color: #3b82f6; }
    button:disabled { opacity: 0.5; cursor: default; }
    .stage { display: grid; grid-template-columns: minmax(320px, 1.05fr) minmax(300px, 1fr) minmax(280px, 0.95fr);
             gap: 12px; padding: 12px; align-items: start; }
    @media (max-width: 1100px) {
      .stage { grid-template-columns: 1fr; }
    }
    .voice-status { font-size: 11px; margin: 6px 0; padding: 6px 8px; border-radius: 6px;
                    border: 1px solid #334155; background: #0b1220; color: #cbd5e1; }
    .voice-status.live { border-color: #166534; color: #86efac; }
    .voice-status.fallback { border-color: #d97706; color: #fde68a; }
    .gatesblock.flash { animation: gateflash 0.7s ease; }
    @keyframes gateflash {
      0% { box-shadow: 0 0 0 0 rgba(251, 191, 36, 0.0); }
      35% { box-shadow: 0 0 0 3px rgba(251, 191, 36, 0.55); }
      100% { box-shadow: 0 0 0 0 rgba(251, 191, 36, 0.0); }
    }
    /* Standard webcam preview: 16:9 HD Ready (720p). Full HD 1080p is requested
       from the device; the frame stays 16:9 so the picture is never stretched. */
    .cam-frame { position: relative; width: 100%; max-width: 720px; aspect-ratio: 16 / 9;
                 background: #000; border-radius: 6px; overflow: hidden;
                 border: 1px solid #334155; }
    #cam, #cam-overlay, #pattern-canvas { position: absolute; inset: 0; width: 100%; height: 100%; }
    #cam { object-fit: contain; transform: scaleX(-1); background: #000; }
    #cam-overlay { z-index: 2; pointer-events: none; }
    #pattern-canvas { z-index: 1; display: none; pointer-events: none; }
    .cam-res { position: absolute; left: 8px; bottom: 8px; z-index: 3; font-size: 10px;
               padding: 2px 6px; border-radius: 4px; background: rgba(15,23,42,0.75);
               border: 1px solid #475569; color: #cbd5e1; }
    .cam-sil-toggle { position: absolute; top: 8px; right: 8px; z-index: 4;
                      display: flex; align-items: center; gap: 8px; padding: 6px 10px;
                      border-radius: 6px; background: rgba(15, 23, 42, 0.88);
                      border: 1px solid #475569; color: #e2e8f0; font-size: 12px;
                      cursor: pointer; user-select: none; pointer-events: auto; }
    .cam-sil-toggle:hover { border-color: #94a3b8; background: rgba(30, 41, 59, 0.95); }
    .cam-sil-toggle .sw { width: 34px; height: 18px; border-radius: 999px;
                          background: #475569; position: relative; flex-shrink: 0;
                          transition: background 0.15s ease; }
    .cam-sil-toggle .sw::after { content: ''; position: absolute; top: 2px; left: 2px;
                                 width: 14px; height: 14px; border-radius: 50%;
                                 background: #f8fafc; transition: transform 0.15s ease; }
    .cam-sil-toggle.on .sw { background: #ca8a04; }
    .cam-sil-toggle.on .sw::after { transform: translateX(16px); }
    .cam-sil-toggle.on { border-color: #ca8a04; color: #fde68a; }
    .cam-contour-toggle { top: 8px; left: 8px; right: auto; }
    .cam-contour-toggle.on { border-color: #22d3ee; color: #a5f3fc; }
    .cam-contour-toggle.on .sw { background: #0891b2; }
    .face-id-panel { margin-top: 8px; border: 1px solid #334155; border-radius: 6px;
      padding: 8px 10px; background: #0b1220; }
    .face-id-panel h4 { margin: 0 0 6px; font-size: 11px; color: #93c5fd; font-weight: 700;
      letter-spacing: 0.04em; text-transform: uppercase; }
    .face-id-panel .face-id-row { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
    .face-id-panel input[type=text] { width: 140px; background: #0b1220; color: #e2e8f0;
      border: 1px solid #475569; border-radius: 4px; padding: 4px 8px; font-size: 12px; }
    .face-id-panel button { font-size: 11px; padding: 3px 8px; }
    .face-id-panel .face-id-status { margin-top: 6px; font-size: 11px; color: #94a3b8; }
    .face-id-panel .face-id-status.ok { color: #86efac; }
    .face-id-panel .face-id-status.warn { color: #fde68a; }
    .face-id-panel .face-id-status.bad { color: #fca5a5; }
    .tilt-lab { margin-top: 8px; border: 1px solid #334155; border-radius: 6px;
                padding: 8px 10px; background: #0b1220; }
    .tilt-lab h4 { margin: 0 0 6px; font-size: 11px; color: #93c5fd; font-weight: 700;
                   letter-spacing: 0.05em; text-transform: uppercase; }
    .tilt-row { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; }
    .tilt-row + .tilt-row { margin-top: 6px; }
    .tilt-lab button { font-size: 11px; padding: 3px 8px; }
    .tilt-lab input[type=number] { width: 58px; background: #0b1220; color: #e2e8f0;
                                   border: 1px solid #334155; border-radius: 4px;
                                   font-size: 11px; padding: 2px 4px; }
    .tilt-chip { font-size: 11px; padding: 2px 7px; border-radius: 999px;
                 border: 1px solid #475569; background: rgba(15,23,42,0.75);
                 color: #cbd5e1; font-variant-numeric: tabular-nums; }
    .tilt-chip.hot { border-color: #ef4444; color: #fca5a5; }
    .tilt-chip.warm { border-color: #f59e0b; color: #fde68a; }
    .tilt-chip.cool { border-color: #22c55e; color: #86efac; }
    .tilt-hint { font-size: 11px; color: #94a3b8; line-height: 1.4; }
    .facial-hud { margin-top: 8px; display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; }
    .audio-hud { margin-top: 6px; display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
    .facial-card { border: 1px solid #334155; border-radius: 6px; padding: 8px 10px;
                   background: #0b1220; }
    .facial-card .lbl { font-size: 10px; color: #94a3b8; text-transform: uppercase;
                        letter-spacing: 0.04em; }
    .facial-card .val { font-size: 18px; font-weight: 700; margin-top: 2px; }
    .facial-card .sub { font-size: 11px; color: #cbd5e1; margin-top: 2px; }
    .facial-card.mood-happy .val { color: #86efac; }
    .facial-card.mood-sad .val { color: #fca5a5; }
    .facial-card.mood-yawning .val { color: #fbbf24; }
    .facial-card.mood-neutral .val { color: #e2e8f0; }
    .facial-card.mood-unknown .val { color: #94a3b8; }
    .facial-card.attn-looking .val { color: #86efac; }
    .facial-card.attn-eyes_away .val { color: #fbbf24; }
    .facial-card.attn-distracted .val { color: #fb923c; }
    .facial-card.attn-inattentive .val { color: #fbbf24; }
    .facial-card.attn-yawning .val { color: #fbbf24; }
    .facial-card.attn-eyes_closed .val { color: #f87171; }
    .facial-card.attn-away_from_webcam .val { color: #f87171; }
    .facial-card.beh-focused .val { color: #86efac; }
    .facial-card.beh-yawning .val { color: #fbbf24; }
    .facial-card.beh-distracted .val { color: #fb923c; }
    .facial-card.beh-inattentive .val { color: #fbbf24; }
    .facial-card.beh-drowsy .val { color: #f87171; }
    .facial-card.beh-away .val { color: #f87171; }
    .facial-card.dist-lidar .val { color: #67e8f9; }
    .facial-card.dist-face_size .val { color: #93c5fd; }
    .facial-card.dist-none .val { color: #94a3b8; }
    @media (max-width: 900px) {
      .facial-hud { grid-template-columns: 1fr 1fr; }
    }
    .camrow { display: flex; gap: 6px; align-items: center; margin-top: 6px; flex-wrap: wrap; }
    .pill { font-size: 10px; padding: 1px 6px; border-radius: 999px;
            background: #1f2937; border: 1px solid #334155; }
    .pill.bad { background: #7f1d1d; border-color: #b91c1c; }
    .pill.good { background: #14532d; border-color: #166534; }
    .pill.warn { background: #78350f; border-color: #d97706; }
    .tabs { display: flex; gap: 6px; margin-bottom: 6px; flex-wrap: wrap; }
    .tabs button.active { background: #1d4ed8; border-color: #3b82f6; }
    .knobscroll { max-height: 360px; overflow-y: auto; padding-right: 4px; }
    .knob { display: grid; grid-template-columns: 1.5fr 1.4fr 0.5fr; gap: 5px;
            align-items: center; font-size: 10px; margin: 1px 0; }
    .knob input[type=range] { height: 12px; }
    details.knobgroup { margin: 6px 0; border-top: 1px solid #334155; padding-top: 4px; }
    details.knobgroup > summary { cursor: pointer; font-size: 11px; color: #93c5fd; margin-bottom: 4px; }
    .gatesblock { margin-top: 6px; border-top: 1px solid #334155; padding-top: 5px; }
    .gateslabel { font-size: 10px; color: #94a3b8; margin-bottom: 2px; }
    .gateshelp { font-size: 10px; color: #64748b; margin-top: 4px; line-height: 1.35; }
    #cam-gates, #gatecounts { font-size: 11px; font-weight: bold; word-break: break-word; }
    #cam-gates.pass { color: #86efac; }
    #cam-gates.fail { color: #fca5a5; }
    canvas.chart { width: 100%; height: 72px; background: #0b1220; border-radius: 6px; margin-top: 8px; }
    .legend { font-size: 10px; color: #94a3b8; margin-top: 4px; line-height: 1.45; }
    .legend .sw { display: inline-block; width: 10px; height: 3px; border-radius: 1px;
                  margin-right: 4px; vertical-align: middle; }
    .chart-title { font-size: 10px; color: #94a3b8; margin-top: 10px; margin-bottom: 2px; }
    .statusline { font-size: 10px; color: #93c5fd; min-height: 13px; margin-top: 4px; }
    .toast { position: fixed; right: 16px; bottom: 16px; max-width: 420px; z-index: 40;
             background: #1e3a8a; border: 1px solid #60a5fa; border-radius: 8px;
             padding: 10px 12px; font-size: 12px; box-shadow: 0 8px 24px rgba(0,0,0,0.4);
             display: none; }
    .toast.show { display: block; }
    .theodore-action { position: fixed; inset: 0; z-index: 80; display: none;
                       align-items: center; justify-content: center; padding: 20px;
                       background: rgba(2, 6, 23, 0.78); backdrop-filter: blur(5px); }
    .theodore-action.show { display: flex; animation: action-fade 0.2s ease-out; }
    .theodore-action-card { width: min(680px, 94vw); position: relative; overflow: hidden;
                            display: grid; grid-template-columns: 210px 1fr; gap: 22px;
                            align-items: center; padding: 26px; border-radius: 24px;
                            border: 2px solid #38bdf8; color: #e0f2fe;
                            background: radial-gradient(circle at 18% 20%, #164e63 0, #0f172a 48%, #020617 100%);
                            box-shadow: 0 24px 80px rgba(0,0,0,.65), 0 0 34px rgba(56,189,248,.25); }
    .theodore-action-card::before { content: ''; position: absolute; inset: -45%;
                                    background: conic-gradient(from 90deg, transparent, rgba(56,189,248,.13), transparent 30%);
                                    animation: action-rays 7s linear infinite; pointer-events: none; }
    .theodore-avatar-wrap { position: relative; min-height: 210px; display: grid; place-items: center; }
    .theodore-avatar { position: relative; z-index: 2; width: 150px; height: 165px;
                       border-radius: 48% 48% 44% 44%; background: #b96f42;
                       border: 5px solid #fbbf24; box-shadow: inset 0 -16px 0 rgba(91,42,24,.20),
                       0 0 0 8px rgba(251,191,36,.12), 0 16px 35px rgba(0,0,0,.35);
                       animation: theodore-breathe 1.8s ease-in-out infinite; }
    .theodore-crown { position: absolute; z-index: 3; top: -27px; left: 25px; width: 92px; height: 48px;
                      background: #fbbf24; clip-path: polygon(0 100%, 3% 27%, 27% 67%, 49% 5%, 72% 67%, 97% 27%, 100% 100%);
                      filter: drop-shadow(0 3px 4px rgba(0,0,0,.35)); }
    .theodore-eye { position: absolute; top: 62px; width: 18px; height: 11px;
                    border-radius: 50%; background: #111827; animation: theodore-blink 4.6s infinite; }
    .theodore-eye.left { left: 35px; } .theodore-eye.right { right: 35px; }
    .theodore-nose { position: absolute; top: 78px; left: 67px; width: 12px; height: 20px;
                     border: 3px solid rgba(67,29,15,.55); border-top: 0; border-left: 0;
                     border-radius: 0 0 8px 0; }
    .theodore-mouth { position: absolute; left: 54px; top: 111px; width: 38px; height: 8px;
                      border-radius: 0 0 22px 22px; background: #4c1d1d;
                      border-bottom: 3px solid #fecaca; transition: height .08s, top .08s; }
    .theodore-action.speaking .theodore-mouth { animation: theodore-talk .18s ease-in-out infinite alternate; }
    .theodore-medallion { position: absolute; z-index: 4; bottom: -10px; left: 51px; width: 42px; height: 42px;
                          display: grid; place-items: center; border-radius: 50%; color: #082f49;
                          background: #fde68a; border: 4px solid #f59e0b; font-size: 23px; font-weight: 900; }
    .theodore-action-icon { position: absolute; z-index: 5; right: 0; top: 10px; font-size: 52px;
                            filter: drop-shadow(0 5px 8px rgba(0,0,0,.45)); }
    .theodore-action.effect-shield .theodore-action-icon { animation: shield-pop .7s ease-out both; }
    .theodore-action.effect-wave .theodore-action-icon { animation: action-wave .55s ease-in-out infinite alternate; transform-origin: 20% 90%; }
    .theodore-action.effect-scan .theodore-avatar-wrap::after,
    .theodore-action.effect-spotlight .theodore-avatar-wrap::after {
      content: ''; position: absolute; z-index: 1; inset: 5px; border: 3px solid #22d3ee;
      border-radius: 50%; animation: action-scan 1.2s ease-out infinite; }
    .theodore-action.effect-celebrate .theodore-action-icon { animation: action-celebrate .7s ease-in-out infinite alternate; }
    .theodore-action.effect-heart .theodore-action-icon { animation: action-heart .8s ease-in-out infinite; }
    .theodore-action.effect-refocus .theodore-action-icon { animation: action-refocus 1s ease-in-out infinite; }
    .theodore-action-copy { position: relative; z-index: 2; }
    .theodore-action-kicker { color: #67e8f9; font-size: 12px; font-weight: 800;
                              text-transform: uppercase; letter-spacing: .12em; }
    .theodore-action-title { margin: 5px 0 9px; color: #fef3c7; font-size: clamp(23px, 4vw, 34px); line-height: 1.08; }
    .theodore-action-body { color: #bae6fd; font-size: 14px; margin-bottom: 12px; }
    .theodore-speech { position: relative; margin: 12px 0 16px; padding: 14px 16px;
                       border-radius: 14px; background: rgba(255,255,255,.95); color: #172554;
                       font-size: 17px; line-height: 1.4; font-weight: 650; }
    .theodore-speech::before { content: ''; position: absolute; left: -13px; top: 24px;
                               border-width: 9px 14px 9px 0; border-style: solid;
                               border-color: transparent rgba(255,255,255,.95) transparent transparent; }
    .theodore-action-controls { display: flex; gap: 8px; flex-wrap: wrap; }
    .theodore-action-controls button { padding: 7px 12px; font-size: 12px; }
    .theodore-action-controls .speak { background: #0369a1; border-color: #38bdf8; }
    @media (max-width: 620px) {
      .theodore-action-card { grid-template-columns: 1fr; text-align: center; padding: 20px; }
      .theodore-avatar-wrap { min-height: 175px; }
      .theodore-speech::before { display: none; }
      .theodore-action-controls { justify-content: center; }
    }
    @media (prefers-reduced-motion: reduce) {
      .theodore-action *, .theodore-action-card::before { animation-duration: .001ms !important;
                                                           animation-iteration-count: 1 !important; }
    }
    @keyframes action-fade { from { opacity: 0; transform: scale(.97); } }
    @keyframes action-rays { to { transform: rotate(360deg); } }
    @keyframes theodore-breathe { 50% { transform: translateY(-4px) rotate(-1deg); } }
    @keyframes theodore-blink { 0%,45%,49%,100% { transform: scaleY(1); } 47% { transform: scaleY(.08); } }
    @keyframes theodore-talk { from { height: 8px; top: 111px; } to { height: 24px; top: 105px; } }
    @keyframes shield-pop { 0% { transform: scale(.2) rotate(-25deg); } 70% { transform: scale(1.2) rotate(5deg); } }
    @keyframes action-wave { to { transform: rotate(24deg); } }
    @keyframes action-scan { from { transform: scale(.65); opacity: .9; } to { transform: scale(1.15); opacity: 0; } }
    @keyframes action-celebrate { to { transform: translateY(-12px) rotate(14deg) scale(1.1); } }
    @keyframes action-heart { 50% { transform: scale(1.25); } }
    @keyframes action-refocus { 50% { transform: scale(1.18); filter: drop-shadow(0 0 16px #fbbf24); } }
    .banner { margin: 0 12px; padding: 8px 10px; border-radius: 6px; font-size: 12px;
              background: #1e293b; border: 1px solid #475569; }
    .banner.cheat { background: #3f1d1d; border-color: #ef4444; color: #fecaca; }
    .banner.pause { background: #3b2f14; border-color: #f59e0b; color: #fde68a;
                    font-size: 14px; font-weight: 700; }
    .cam-pause-overlay { position: absolute; inset: 0; z-index: 5; display: none;
                         align-items: center; justify-content: center; flex-direction: column;
                         gap: 8px; background: rgba(15, 23, 42, 0.72);
                         pointer-events: none; text-align: center; padding: 16px; }
    .cam-pause-overlay.show { display: flex; }
    .cam-pause-overlay .pause-title { font-size: clamp(22px, 5vw, 36px); font-weight: 800;
                                      color: #fde68a; letter-spacing: 0.04em; }
    .cam-pause-overlay .pause-sub { font-size: 13px; color: #e2e8f0; max-width: 28rem;
                                    line-height: 1.35; }
    .cam-frame.paused { border-color: #f59e0b; box-shadow: 0 0 0 2px rgba(245, 158, 11, 0.45); }
    .tools { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; padding: 0 12px 12px; }
    .tools textarea { width: 100%; min-height: 54px; background: #0b1220; color: #e2e8f0;
                      border: 1px solid #334155; border-radius: 4px; }
    .log { font-size: 11px; max-height: 140px; overflow-y: auto; background: #0b1220;
           border-radius: 4px; padding: 6px; white-space: pre-wrap; }
    label.check { font-size: 11px; display: inline-flex; gap: 4px; align-items: center; }
    .tuning-help { font-size: 11px; color: #94a3b8; line-height: 1.4; margin: 6px 0 8px; }
    .tuning-effect { margin-top: 8px; border: 1px solid #334155; border-radius: 6px;
                     padding: 8px 10px; background: #0b1220; font-size: 11px; }
    .tuning-effect h3 { margin: 0 0 6px; font-size: 12px; color: #93c5fd; }
    .tuning-effect .row { display: flex; justify-content: space-between; gap: 8px; margin: 2px 0; }
    .tuning-effect .hit { color: #fca5a5; }
    .tuning-effect .ok { color: #86efac; }
    .integrity-hud { display: grid; grid-template-columns: repeat(5, 1fr); gap: 6px; margin-top: 8px; }
    @media (max-width: 900px) {
      .integrity-hud { grid-template-columns: 1fr 1fr; }
      .facial-hud { grid-template-columns: 1fr 1fr; }
    }
    .facial-card.attn-eyes_closed .val { color: #f87171; }
    .obs-panel { margin-top: 10px; border: 1px solid #334155; border-radius: 8px;
                 background: #0b1220; padding: 10px; }
    .obs-panel h3 { margin: 0 0 6px; font-size: 13px; color: #93c5fd; }
    .obs-top { display: flex; justify-content: space-between; gap: 10px; flex-wrap: wrap;
               align-items: flex-start; margin-bottom: 8px; }
    .obs-labels .big { font-size: 18px; font-weight: 800; color: #e2e8f0; text-transform: capitalize; }
    .obs-labels .sub { font-size: 11px; color: #94a3b8; margin-top: 2px; }
    .obs-pose-box { width: 64px; height: 64px; border-radius: 50%; border: 1px solid #475569;
                    position: relative; background: radial-gradient(circle at center, #1e293b, #0f172a); }
    .obs-pose-needle { position: absolute; left: 50%; top: 50%; width: 4px; height: 22px;
                       background: #38bdf8; border-radius: 2px; transform-origin: 50% 100%;
                       transform: translate(-50%, -50%); }
    .obs-bars { display: grid; grid-template-columns: 1fr 1fr; gap: 4px 12px; }
    .obs-bar-row { display: grid; grid-template-columns: 72px 1fr; gap: 6px; align-items: center;
                   font-size: 10px; color: #94a3b8; text-transform: uppercase; }
    .obs-track { height: 7px; background: #1f2937; border-radius: 999px; overflow: hidden; }
    .obs-fill { height: 100%; width: 0%; background: linear-gradient(90deg, #22d3ee, #34d399); }
    .obs-fill.warn { background: linear-gradient(90deg, #fbbf24, #f97316); }
    .obs-fill.bad { background: linear-gradient(90deg, #fb7185, #ef4444); }
    .obs-events { margin-top: 8px; max-height: 120px; overflow-y: auto; font-size: 11px; }
    .obs-ev { padding: 3px 0; border-bottom: 1px solid #1e293b; color: #cbd5e1; }
    .obs-ev .t { color: #64748b; margin-right: 6px; }
    .obs-ev.high { color: #fca5a5; }
    .obs-ev.medium { color: #fde68a; }
    .integrity-card { border: 1px solid #334155; border-radius: 6px; padding: 6px 8px; background: #0b1220; }
    .integrity-card .lbl { font-size: 10px; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.04em; }
    .integrity-card .val { font-size: 15px; font-weight: 700; margin-top: 2px; color: #94a3b8; }
    .integrity-card.alert-low .val { color: #86efac; }
    .integrity-card.alert-med .val { color: #fbbf24; }
    .integrity-card.alert-high { border-color: #ef4444; background: #2d0f0f; }
    .integrity-card.alert-high .val { color: #f87171; }
    .integrity-status { font-size: 11px; margin-top: 4px; color: #94a3b8; min-height: 16px; }
    .integrity-status.warn { color: #fbbf24; font-weight: bold; }
    .integrity-status.alert { color: #f87171; font-weight: bold; }
"""

# Knob groups: every VisionTuning + VoiceTuning + AnalyzerPolicy field the UI exposes.
VISION_KNOB_GROUPS = [
    (
        "Lighting",
        [
            ("light_underexposed_luma", 0, 1, 0.01),
            ("light_overexposed_luma", 0, 1, 0.01),
            ("light_max_clipped_black_ratio", 0, 1, 0.01),
            ("light_max_clipped_white_ratio", 0, 1, 0.01),
            ("light_min_quality", 0, 1, 0.01),
            ("light_default_quality", 0, 1, 0.01),
        ],
    ),
    (
        "Sharpness / Sobel",
        [
            ("sobel_binary_threshold", 0, 1, 0.01),
            ("sobel_min_edge_density", 0, 0.5, 0.005),
            ("sharpness_reference_gradient", 0.05, 1, 0.01),
            ("sharpness_min_quality", 0, 1, 0.01),
            ("sharpness_gradient_percentile", 50, 100, 1),
        ],
    ),
    (
        "Distance",
        [
            ("distance_reference_face_ratio", 0.02, 0.6, 0.01),
            ("distance_reference_metres", 0.3, 3, 0.05),
            ("distance_min_face_ratio", 0.02, 0.4, 0.01),
            ("distance_min_metres", 0.2, 2, 0.05),
            ("distance_max_metres", 1, 6, 0.1),
            ("distance_too_close_m", 0.2, 2, 0.05),
            ("distance_too_far_m", 0.5, 4, 0.05),
        ],
    ),
    (
        "Detection",
        [
            ("silhouette_foreground_threshold", 0.5, 1, 0.01),
            ("silhouette_motion_threshold", 0, 0.5, 0.01),
            ("silhouette_consecutive_frames", 1, 10, 1),
            ("gaze_frontal_min_threshold", 0, 1, 0.01),
            ("gaze_down_min_threshold", 0, 1, 0.01),
            ("eyes_closed_min_threshold", 0, 1, 0.01),
            ("yawn_min_threshold", 0, 1, 0.01),
            ("attention_min_threshold", 0, 1, 0.01),
            ("distraction_min_threshold", 0, 1, 0.01),
            ("typing_activity_min_threshold", 0, 1, 0.01),
            ("keyboard_typing_audio_min_threshold", 0, 1, 0.01),
            ("hands_on_face_min_threshold", 0, 1, 0.01),
            ("hands_on_face_min_hold_ms", 0, 20000, 250),
            ("phone_visible_min_hold_ms", 0, 20000, 250),
            ("posture_release_grace_ms", 0, 5000, 100),
            ("excitement_min_threshold", 0, 1, 0.01),
            ("interest_min_threshold", 0, 1, 0.01),
            ("dozing_min_threshold", 0, 1, 0.01),
            ("interest_min_hold_ms", 0, 10000, 100),
            ("dozing_min_hold_ms", 0, 10000, 100),
            ("excitement_attention_boost", 0, 1, 0.01),
            ("interest_attention_boost", 0, 1, 0.01),
            ("external_music_min_threshold", 0, 1, 0.01),
            ("external_music_min_hold_ms", 0, 10000, 100),
            ("held_object_min_threshold", 0, 1, 0.01),
            ("held_object_min_hold_ms", 0, 10000, 100),
        ],
    ),
    (
        "Image scoring",
        [
            ("image_detection_confidence_weight", 0, 1, 0.01),
            ("image_liveness_weight", 0, 1, 0.01),
            ("image_no_face_penalty", 0, 1, 0.01),
            ("image_default_confidence_with_face", 0, 1, 0.01),
            ("image_default_confidence_no_face", 0, 1, 0.01),
            ("image_min_quality", 0, 1, 0.01),
        ],
    ),
    (
        "Behavior scoring",
        [
            ("behavior_happy_weight", 0, 1, 0.01),
            ("behavior_known_expression_weight", 0, 1, 0.01),
            ("behavior_unknown_expression_weight", 0, 1, 0.01),
            ("behavior_focus_weight", 0, 1, 0.01),
            ("behavior_integrity_weight", 0, 1, 0.01),
        ],
    ),
    (
        "Audio",
        [
            ("audio_snr_floor_db", 0, 30, 0.5),
            ("audio_snr_span_db", 5, 50, 0.5),
            ("audio_noise_clean_db", 10, 60, 1),
            ("audio_noise_loud_db", 40, 100, 1),
            ("audio_clipping_penalty", 0, 5, 0.1),
            ("audio_min_mic_quality", 0, 1, 0.01),
            ("audio_min_noise_filter_effectiveness", 0, 1, 0.01),
            ("audio_max_noise_level_db", 20, 100, 1),
            ("audio_min_snr_db", 0, 40, 0.5),
        ],
    ),
]

VOICE_KNOB_GROUPS = [
    (
        "Replies",
        [
            ("reply_temperature_fast", 0, 2, 0.05),
            ("reply_temperature_full", 0, 2, 0.05),
            ("reply_max_tokens_fast", 16, 512, 8),
            ("reply_max_tokens_full", 16, 1024, 8),
            ("reply_max_sentences", 1, 8, 1),
        ],
    ),
    (
        "Questions / assessment",
        [
            ("question_temperature", 0, 2, 0.05),
            ("question_max_tokens", 32, 1024, 8),
            ("assessment_temperature", 0, 2, 0.05),
            ("assessment_max_tokens", 32, 1024, 8),
        ],
    ),
    (
        "Latency / memory",
        [
            ("fast_timeout_s", 1, 30, 0.5),
            ("full_timeout_s", 1, 60, 0.5),
            ("cache_ttl_s", 1, 120, 1),
            ("max_history_turns", 1, 12, 1),
        ],
    ),
]

POLICY_KNOBS = [
    ("absence_grace_ms", 500, 180000, 500),
    ("gaze_away_grace_ms", 500, 120000, 500),
    ("pause_training_no_presence_ms", 500, 30000, 500),
    ("solo_max_faces", 1, 5, 1),
    ("max_tracked_sessions", 8, 2048, 8),
]


def _js_knob_groups(groups: list) -> str:
    """Serialize knob groups for embedding in JS without a JSON dependency in the template."""
    import json

    return json.dumps(groups)


def _js_absence_phrases() -> str:
    """Serialize ABSENCE_PHRASES to a JSON string for embedding in the monitor JS."""
    import json

    return json.dumps(ABSENCE_PHRASES)


MONITOR_JS = (
    """
    const sessionId = __SESSION_ID_JSON__;
    const liveCamSessionId = sessionId + '__livecam';
    const endpoint = `/api/theodore/webcam/live-metrics/${encodeURIComponent(sessionId)}`;
    // True only when the server actually mounted /vendor/vision. Without local
    // assets that path 404s, so trying it first just delays the CDN that works
    // for everyone — which is what stopped the face mesh from showing up.
    const VISION_LOCAL_ASSETS = __VISION_LOCAL_ASSETS__;
    const VISION_GROUPS = __VISION_GROUPS__;
    const VOICE_GROUPS = __VOICE_GROUPS__;
    const POLICY_KNOBS = __POLICY_KNOBS__;
    let knownAlertKeys = new Set();
    let highlightParticipant = '';
    let tuningScope = 'vision';
    let activeChallenge = null;
    let visionKnobs = {};
    let lastLiveCamParticipant = null;

    function esc(value) {
      return String(value === null || value === undefined ? '' : value)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
    }
    function clamp01(value) {
      const n = Number(value);
      if (!Number.isFinite(n)) return 0;
      return n < 0 ? 0 : (n > 1 ? 1 : n);
    }
    // WebcamSignal fields the server constrains to 0..1. Anything outside that
    // range fails the whole POST with a 422, so every frame is clamped on the way out.
    const UNIT_SIGNAL_FIELDS = [
      'foreground_ratio', 'motion_score', 'attention', 'expression_confidence',
      'gaze_frontal', 'gaze_down_score', 'gaze_up_score', 'gaze_left_score', 'gaze_right_score',
      'eyes_closed_score', 'yawn_score',
      'hands_on_face_score', 'body_motion_score', 'fidget_score', 'brow_raise_score',
      'smile_score', 'screen_focus_score', 'typing_activity_score',
      'keyboard_typing_audio_score', 'face_size_ratio', 'light_quality_score',
      'image_detection_confidence', 'noise_filter_effectiveness_score',
      'microphone_input_level_score', 'mic_clipping_ratio', 'sharpness_score',
      'edge_density', 'mean_luminance', 'underexposed_ratio', 'overexposed_ratio',
      'face_motion_energy', 'hand_gesture_energy', 'head_sag_rate',
      'excitement_score', 'interest_score', 'dozing_score',
      'external_music_score', 'phone_in_hand_score', 'held_object_score',
      'owner_match_score',
    ];
    function clampSignal(signal) {
      UNIT_SIGNAL_FIELDS.forEach((field) => {
        const value = signal[field];
        if (value === null || value === undefined) return;
        signal[field] = clamp01(value);
      });
      return signal;
    }
    function toast(message) {
      const el = document.getElementById('toast');
      el.textContent = message;
      el.classList.add('show');
      clearTimeout(toast._t);
      toast._t = setTimeout(() => el.classList.remove('show'), 5000);
    }
    function pct(v) {
      if (v === null || v === undefined) return 'n/a';
      return `${Math.round(v * 100)}%`;
    }
    function num(v, digits = 2) {
      if (v === null || v === undefined) return 'n/a';
      return Number(v).toFixed(digits);
    }
    function bar(v) {
      return `<progress value="${v === null || v === undefined ? 0 : v}" max="1"></progress>`;
    }
    function alertKey(a) { return `${a.code || ''}:${a.participant_id || '-'}`; }

    let currentActionSpeech = '';

    function closeTheodoreAction() {
      const stage = document.getElementById('theodore-action');
      if (!stage) return;
      stage.classList.remove('show', 'speaking');
      stage.setAttribute('aria-hidden', 'true');
      if ('speechSynthesis' in window) speechSynthesis.cancel();
    }

    function speakCurrentAction() {
      if (currentActionSpeech) speakTheodore(currentActionSpeech, voiceLangCode());
    }

    function presentTheodoreAction(presentation, fallbackText) {
      const p = presentation || {};
      const stage = document.getElementById('theodore-action');
      if (!stage) return;
      const effect = String(p.visual_effect || 'announce').replace(/[^a-z_-]/gi, '');
      stage.className = `theodore-action show effect-${effect}`;
      stage.setAttribute('aria-hidden', 'false');
      document.getElementById('theodore-action-icon').textContent = p.visual_icon || '✨';
      document.getElementById('theodore-action-title').textContent =
        p.visual_title || 'Theodore takes action';
      document.getElementById('theodore-action-body').textContent =
        p.visual_body || fallbackText || 'The lesson action is underway.';
      currentActionSpeech = p.speech_text || fallbackText || 'I am taking care of it.';
      document.getElementById('theodore-action-speech').textContent = currentActionSpeech;
      // An explicit action click permits browser TTS. Respect Auto-speak and keep
      // a replay button visible so audio is never a one-shot hidden side effect.
      if (autoSpeak()) speakCurrentAction();
    }

    document.getElementById('theodore-action-speak').addEventListener('click', speakCurrentAction);
    document.getElementById('theodore-action-close').addEventListener('click', closeTheodoreAction);
    document.getElementById('theodore-action').addEventListener('click', (ev) => {
      if (ev.target === ev.currentTarget) closeTheodoreAction();
    });
    document.addEventListener('keydown', (ev) => {
      if (ev.key === 'Escape') closeTheodoreAction();
    });

    function drawLines(canvas, seriesList, colors) {
      const ctx = canvas.getContext('2d');
      const w = canvas.width = canvas.clientWidth * window.devicePixelRatio;
      const h = canvas.height = canvas.clientHeight * window.devicePixelRatio;
      ctx.clearRect(0, 0, w, h);
      ctx.strokeStyle = '#334155';
      ctx.strokeRect(0, 0, w, h);
      for (let s = 0; s < seriesList.length; s++) {
        const vals = seriesList[s] || [];
        if (vals.length < 2) continue;
        ctx.beginPath();
        ctx.strokeStyle = colors[s];
        let penDown = false;
        for (let i = 0; i < vals.length; i++) {
          const raw = vals[i];
          if (raw === null || raw === undefined) { penDown = false; continue; }
          const x = (i / (vals.length - 1)) * (w - 8) + 4;
          const y = (1 - Math.max(0, Math.min(1, raw))) * (h - 8) + 4;
          if (!penDown) { ctx.moveTo(x, y); penDown = true; } else { ctx.lineTo(x, y); }
        }
        ctx.stroke();
      }
    }

    async function runAlertAction(a) {
      const res = await fetch('/api/theodore/webcam/alerts/action', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          code: a.code || 'unknown',
          action: a.action || '',
          participant_id: a.participant_id || '',
          message: a.message || '',
        }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) { toast('Action failed: ' + (body.detail || res.status)); return; }
      toast(body.summary || 'Lesson action completed');
      presentTheodoreAction(
        body.details && body.details.presentation,
        body.summary || 'Lesson action completed',
      );
      if (body.details && body.details.challenge_id) {
        activeChallenge = body.details;
        document.getElementById('game-status').textContent =
          `Active challenge: ${body.details.challenge_title} (${body.details.challenge_id})`;
      }
      if (a.participant_id) {
        highlightParticipant = a.participant_id;
        const card = document.querySelector(`[data-participant="${CSS.escape(a.participant_id)}"]`);
        if (card) {
          card.classList.add('flash');
          card.scrollIntoView({ behavior: 'smooth', block: 'center' });
          setTimeout(() => card.classList.remove('flash'), 1800);
        }
      }
      refresh();
    }

    // Absence announcer — Theodore's timed voice check-ins when a participant is missing.
    // Solo mode: waits indefinitely, cycling through periodic nudges.
    // Group mode: boots the participant after 3 minutes.
    const absenceAnnouncer = (() => {
      const _state = {};  // participant_id -> { sinceMs, milestone, booted }
      const AP = __ABSENCE_PHRASES__;

      function _pick(bucket) {
        const arr = AP[bucket];
        return arr[Math.floor(Math.random() * arr.length)];
      }
      function _phrase(bucket, name, isGroup) {
        // boot_group / final_solo split handled at call-site; other buckets just replace {n}
        return _pick(bucket).replace(/\\{n\\}/g, name);
      }

      // Milestone timing stays unchanged; bucket names map to phrase lists.
      const MILESTONES = [
        { ms:      0, bucket: 'immediate' },
        { ms:  10000, bucket: 'check_10s' },
        { ms:  30000, bucket: 'check_30s' },
        { ms:  60000, bucket: 'check_60s' },
        { ms:  90000, bucket: 'check_90s' },
        { ms: 120000, bucket: 'check_120s' },
        { ms: 180000, bucket: null },  // bucket chosen dynamically: boot_group vs final_solo
      ];
      const SOLO_REPEAT_MS = 45000;  // cycle nudges every 45 s in solo mode

      function _humanName(id) {
        return id.replace(/[-_]/g, ' ').replace(/\\b\\w/g, (c) => c.toUpperCase());
      }

      async function _boot(participantId) {
        try {
          await fetch('/api/theodore/webcam/session/boot-participant', {
            method: 'POST',
            headers: { 'content-type': 'application/json' },
            body: JSON.stringify({ session_id: sessionId, participant_id: participantId }),
          });
        } catch (_) {}
        toast(`${_humanName(participantId)} has been removed from the session.`);
      }

      return {
        update(absentIds, mode, extras) {
          const now = Date.now();
          const isGroup = mode === 'group';
          extras = extras || {};
          let spokeThisTick = false;  // at most one announcement spoken per refresh tick

          // Welcome back anyone who returned
          for (const id of Object.keys(_state)) {
            if (!absentIds.includes(id) && !_state[id].booted) {
              const name = _humanName(id);
              const msg = _pick('welcome_back').replace(/\\{n\\}/g, name);
              speakTheodore(msg);
              toast(msg);
            }
          }
          for (const id of Object.keys(_state)) {
            if (!absentIds.includes(id)) delete _state[id];
          }

          for (const id of absentIds) {
            if (!_state[id]) _state[id] = { sinceMs: now, milestone: -1, booted: false, soloCycle: 0, lastSoloMs: 0 };
            const s = _state[id];
            if (s.booted) continue;
            const gone = now - s.sinceMs;
            const name = _humanName(id);

            // Advance through milestones — always process ALL absent participants,
            // but only speak once per refresh tick (spokeThisTick guard).
            const nextIdx = s.milestone + 1;
            if (nextIdx < MILESTONES.length && gone >= MILESTONES[nextIdx].ms) {
              s.milestone = nextIdx;
              if (!spokeThisTick) {
                let text;
                if (MILESTONES[nextIdx].bucket === null) {
                  // Final milestone: boot in group mode, wait forever in solo mode
                  const bucket = isGroup ? 'boot_group' : 'final_solo';
                  text = _pick(bucket).replace(/\\{n\\}/g, name);
                } else {
                  text = _phrase(MILESTONES[nextIdx].bucket, name);
                }
                // Prefer an explicit pause line when training just paused for absence.
                if (nextIdx === 0 && extras.trainingPaused) {
                  text = _pick('immediate').replace(/\\{n\\}/g, name);
                }
                speakTheodore(text, voiceLangCode());
                toast(text);
                spokeThisTick = true;
              }
              // Boot in group mode at the final milestone (3 min) regardless of speech
              if (nextIdx === MILESTONES.length - 1 && isGroup) {
                s.booted = true;
                _boot(id);
              }
            }

            // Solo mode: keep cycling gentle nudges after all milestones pass
            if (!isGroup && s.milestone >= MILESTONES.length - 1) {
              if (!spokeThisTick && now - s.lastSoloMs >= SOLO_REPEAT_MS) {
                s.lastSoloMs = now;
                const msg = _pick('solo_cycle').replace(/\\{n\\}/g, name);
                s.soloCycle++;
                speakTheodore(msg, voiceLangCode());
                toast(msg);
                spokeThisTick = true;
              }
            }
          }
        },
      };
    })();

    let metricsRefreshTimer = null;
    let labOffline = false;
    let metricsFailStreak = 0;

    function setTextSafe(id, text) {
      const el = document.getElementById(id);
      if (el) el.textContent = text;
    }
    function setHtmlSafe(id, html) {
      const el = document.getElementById(id);
      if (el) el.innerHTML = html;
    }

    function stopMetricsPolling() {
      if (metricsRefreshTimer) {
        clearInterval(metricsRefreshTimer);
        metricsRefreshTimer = null;
      }
    }

    function markLabOffline(reason) {
      if (labOffline) return;
      labOffline = true;
      stopMetricsPolling();
      try { if (typeof stopCamera === 'function') stopCamera(); } catch (_) {}
      setTextSafe('state', reason || 'Lab server offline — refresh after restarting.');
    }

    async function refresh() {
      if (labOffline || document.getElementById('state') == null) {
        stopMetricsPolling();
        return;
      }
      let res;
      try { res = await fetch(endpoint, { cache: 'no-store' }); }
      catch (err) {
        metricsFailStreak += 1;
        setTextSafe('state', 'Lab server unreachable — waiting to reconnect…');
        // After a few refused polls (typical when the process was killed), stop
        // hammering the closed port so DevTools is not flooded with errors.
        if (metricsFailStreak >= 3) {
          markLabOffline('Lab server stopped. Restart uvicorn, then reload this page.');
        }
        return;
      }
      metricsFailStreak = 0;
      if (labOffline || document.getElementById('state') == null) return;
      const data = res.ok ? await res.json().catch(() => null) : null;
      // An unseeded session answers 200 with updated_at_ms 0 and no participants.
      if (!data || !data.updated_at_ms) {
        setHtmlSafe('state',
          'No metrics yet. Click <strong>Load solo demo (1 student)</strong> or use Start camera.');
        const banner = document.getElementById('cheat-banner');
        if (banner) banner.style.display = 'none';
        return;
      }
      const acked = new Set(data.acknowledged_alert_keys || []);
      const s = data.quality_summary || {};
      setHtmlSafe('state',
        `<div class="kv"><span>Training paused</span><strong>${data.training_paused}</strong></div>` +
        `<div class="kv"><span>Pause reason</span><strong>${esc(data.pause_reason || 'none')}</strong></div>` +
        `<div class="kv"><span>Mode</span><strong>${esc(data.mode)}</strong></div>` +
        `<div class="kv"><span>Updated at</span><strong>${esc(data.updated_at_ms)}</strong></div>` +
        `<div class="kv"><span>No-one present (ms)</span><strong>${esc(data.no_one_present_for_ms || 0)}</strong></div>` +
        `<div class="kv"><span>Silhouettes</span><strong>${esc((data.silhouette_participant_ids || []).join(', ') || 'none')}</strong></div>` +
        `<div class="kv"><span>Cheating</span><strong>${esc((data.suspected_cheating_participant_ids || []).join(', ') || 'none')}</strong></div>` +
        `<div class="kv"><span>Happy</span><strong>${esc((data.happy_participant_ids || []).join(', ') || 'none')}</strong></div>` +
        `<div class="kv"><span>Absent</span><strong>${esc((data.absent_participant_ids || []).join(', ') || 'none')}</strong></div>` +
        `<div class="kv"><span>Watchlist</span><strong>${esc((data.watchlist || []).join(', ') || 'none')}</strong></div>` +
        `<div class="kv"><span>Rejoin requests</span><strong>${esc((data.rejoin_requests || []).join(', ') || 'none')}</strong></div>` +
        `<div class="kv"><span>Expressions</span><strong>${esc(JSON.stringify(data.expression_counts || {}))}</strong></div>`);

      const cheatIds = data.suspected_cheating_participant_ids || [];
      const banner = document.getElementById('cheat-banner');
      if (banner) {
      if (cheatIds.length) {
        banner.style.display = 'block';
        banner.className = 'banner cheat';
        banner.textContent = `Integrity alert: possible cheating for ${cheatIds.join(', ')}.`;
      } else if (data.training_paused) {
        banner.style.display = 'block';
        banner.className = 'banner pause';
        const why = data.pause_reason === 'original_user_not_present'
          ? 'Original learner not in frame — lesson paused.'
          : (data.pause_reason === 'owner_face_mismatch'
            ? 'Camera owner mismatch — another person may have substituted. Lesson paused.'
            : (data.pause_reason === 'camera_quality'
              ? 'Camera quality is too poor to continue — improve lighting/focus, or remove this webcam.'
              : (data.pause_reason === 'pitch_dark_needs_light'
                ? 'It is too dark. Trying auto-brightness — please turn on a light before continuing.'
                : (data.pause_reason === 'too_far_from_camera'
                  ? 'You are too far from the camera. Please move closer to continue the class.'
                  : (data.pause_reason === 'attention_integrity'
                    ? 'Looking away from the lesson — please look at the screen to continue.'
                    : 'Away from webcam — lesson paused. Please return to the camera.')))));
            ? 'Face ID mismatch — enrolled learner is not in frame. Teaching paused until they return.'
            : 'Away from webcam — lesson paused. Please return to the camera.');
        banner.textContent = '⏸ ' + why;
        if (data.pause_reason === 'pitch_dark_needs_light') {
          void tryAutoLighting();
          maybeAnnounceIntegrity('dark',
            'It is too dark to continue. I tried brightening the camera — please turn on a light.');
        } else if (data.pause_reason === 'too_far_from_camera') {
          maybeAnnounceIntegrity('far',
            'You are too far from the camera to take this class. Please move closer.');
        } else if (data.pause_reason === 'camera_quality') {
          maybeAnnounceIntegrity('quality',
            'Camera quality is too poor to continue. Improve the lighting or focus, or switch cameras.');
        } else if (data.pause_reason === 'attention_integrity') {
          maybeAnnounceIntegrity('away',
            'Please look at the lesson on screen. Looking away counts as not paying attention.');
        }
      } else {
        banner.style.display = 'none';
      }
      }

      // Session-level pause / absent → spoken Theodore nudges (quick defaults ~1s).
      // Only announce for real absences, or no-learner pause (not wrong-user swap).
      let announceIds = data.absent_participant_ids || [];
      if (!announceIds.length && data.training_paused
          && data.pause_reason === 'no_learner_detected') {
        // Only synthesise an entry when we have a real known ID — never use a
        // generic placeholder like 'learner' that would corrupt the announcer state.
        const first = (data.participants || [])[0];
        const knownId = (first && first.participant_id) || data.original_participant_id || '';
        if (knownId) announceIds = [knownId];
      }
      absenceAnnouncer.update(announceIds, data.mode || 'solo', {
        trainingPaused: !!data.training_paused,
        pauseReason: data.pause_reason || '',
      });

      if (document.getElementById('summary') == null) {
        stopMetricsPolling();
        return;
      }

      setHtmlSafe('summary', `
        <div class="metric"><div>Participants</div><div class="v">${esc(s.participants_count || (data.participants || []).length)}</div></div>
        <div class="metric"><div>Avg distance (m)</div><div class="v">${num(s.avg_distance_from_camera_m)}</div></div>
        <div class="metric"><div>Light quality</div><div class="v">${pct(s.avg_light_quality_score)}</div></div>
        <div class="metric"><div>Image quality</div><div class="v">${pct(s.avg_image_detection_quality_score)}</div></div>
        <div class="metric"><div>Behavior</div><div class="v">${pct(s.avg_expression_behavior_score)}</div></div>
        <div class="metric"><div>Mic quality</div><div class="v">${num(s.avg_microphone_quality_score)}</div></div>
        <div class="metric"><div>Noise filter</div><div class="v">${num(s.avg_noise_filter_effectiveness_score)}</div></div>
        <div class="metric"><div>Recognition</div><div class="v">${pct(s.avg_recognition_confidence)}</div></div>
      `);

      const gates = s.quality_flag_counts || {};
      setTextSafe('gatecounts', Object.keys(gates).length
        ? Object.entries(gates).map(([k, v]) => `${k}=${v}`).join(', ') : 'none');

      const windowById = {};
      (data.group_student_windows || []).forEach((w) => { windowById[w.participant_id] = w; });

      const alerts = data.lesson_alerts || [];
      const fresh = [];
      alerts.forEach((a) => {
        const key = alertKey(a);
        if (!knownAlertKeys.has(key) && !acked.has(key)) fresh.push(a);
        knownAlertKeys.add(key);
      });
      if (fresh.length) toast(`New lesson alert [${fresh[0].level}] ${fresh[0].message}`);

      setHtmlSafe('alerts', alerts.length
        ? alerts.map((a) => {
            const key = alertKey(a);
            const isAcked = acked.has(key);
            return `<li class="${esc(a.level || '')}${isAcked ? ' acked' : ''}">
              <strong>[${esc(a.level)}]</strong> ${esc(a.message)}
              <div style="margin-top:4px;color:#93c5fd;">Action: ${esc((a.action || 'none').replace(/_/g, ' '))}</div>
              <div class="actions">
                <button type="button" class="primary" data-alert-act="${esc(key)}" ${isAcked ? 'disabled' : ''}>
                  ${isAcked ? 'Done' : 'Run lesson action'}
                </button>
                ${a.participant_id ? `<button type="button" data-alert-jump="${esc(a.participant_id)}">Show student</button>` : ''}
              </div>
            </li>`;
          }).join('')
        : '<li>No lesson alerts</li>');

      document.querySelectorAll('[data-alert-act]').forEach((btn) => {
        btn.addEventListener('click', () => {
          const a = alerts.find((row) => alertKey(row) === btn.getAttribute('data-alert-act'));
          if (a) runAlertAction(a);
        });
      });
      document.querySelectorAll('[data-alert-jump]').forEach((btn) => {
        btn.addEventListener('click', () => {
          const id = btn.getAttribute('data-alert-jump');
          const card = document.querySelector(`[data-participant="${CSS.escape(id)}"]`);
          if (card) {
            card.classList.add('flash');
            card.scrollIntoView({ behavior: 'smooth', block: 'center' });
            setTimeout(() => card.classList.remove('flash'), 1800);
          }
        });
      });

      setTextSafe('action-log',
        (data.action_log || []).slice().reverse().map((e) =>
          `${e.timestamp_ms}: ${e.summary}`).join('\\n') || 'No actions yet.');
      document.getElementById('private-msgs').textContent =
        (data.private_messages || []).slice().reverse().map((m) =>
          `${m.participant_id}: ${m.body}`).join('\\n') || 'No private messages.';

      const windows = (data.participants || []).map((p) => {
        const latest = p.latest || {};
        const win = windowById[p.participant_id] || {};
        const cheating = !!latest.suspected_cheating;
        const sil = !!latest.silhouette_detected;
        const classes = ['student'];
        if (cheating) classes.push('cheating');
        if (sil) classes.push('silhouette');
        const reasons = (latest.cheating_reasons || []).join(', ') || 'none';
        const flags = (latest.quality_flags || []).join(', ') || 'none';
        return `
        <div class="${classes.join(' ')}" data-participant="${esc(p.participant_id)}">
          <h3>Window #${esc(p.window_index)} - ${esc(p.participant_id)}
            ${cheating ? '<span class="pill bad">CHEATING</span>' : ''}
            ${sil ? '<span class="pill warn">SILHOUETTE</span>' : ''}
            ${win.needs_intervention ? '<span class="pill warn">INTERVENE</span>' : ''}
          </h3>
          <div class="kv"><span>State</span><strong>${esc(latest.state)}</strong></div>
          <div class="kv"><span>Expression</span><strong>${esc(latest.dominant_expression)} (${num(latest.expression_confidence)})</strong></div>
          <div class="kv"><span>Eyes away (ms)</span><strong>${esc(latest.eyes_away_for_ms || 0)}</strong></div>
          <div class="kv"><span>Severity</span><strong>${esc(win.severity || 'none')}</strong></div>
          <div class="kv"><span>Window note</span><strong>${esc(win.message || '—')}</strong></div>
          <div class="kv"><span>Reason</span><strong>${esc(latest.reason || '—')}</strong></div>
          <div class="kv"><span>Face count</span><strong>${esc(latest.face_count)}</strong></div>
          <div class="kv"><span>Distance (m)</span><strong>${num(latest.distance_from_camera_m)}</strong></div>
          <div class="kv"><span>Distance source</span><strong>${esc(latest.distance_source || 'none')}</strong></div>
          <div class="kv"><span>Light</span><strong>${pct(latest.light_quality_score)}</strong></div>
          ${bar(latest.light_quality_score)}
          <div class="kv"><span>Image quality</span><strong>${pct(latest.image_detection_quality_score)}</strong></div>
          ${bar(latest.image_detection_quality_score)}
          <div class="kv"><span>Behavior</span><strong>${pct(latest.expression_behavior_score)}</strong></div>
          ${bar(latest.expression_behavior_score)}
          <div class="kv"><span>Mic quality</span><strong>${num(latest.microphone_quality_score)}</strong></div>
          ${bar(latest.microphone_quality_score)}
          <div class="kv"><span>Noise filter</span><strong>${num(latest.noise_filter_effectiveness_score)}</strong></div>
          ${bar(latest.noise_filter_effectiveness_score)}
          <div class="kv"><span>Recognition</span><strong>${pct(latest.recognition_confidence)}</strong></div>
          ${bar(latest.recognition_confidence)}
          <div class="kv"><span>Sharpness</span><strong>${num(latest.sharpness_score)}</strong></div>
          <div class="kv"><span>Edge density</span><strong>${num(latest.edge_density, 3)}</strong></div>
          <div class="kv"><span>SNR / noise dB</span><strong>${num(latest.audio_snr_db)} / ${num(latest.audio_noise_level_db)}</strong></div>
          <div class="kv"><span>Absent (ms)</span><strong>${esc(latest.absent_for_ms || 0)}</strong></div>
          <div class="kv"><span>Typing audio</span><strong>${!!latest.keyboard_typing_audio_detected}</strong></div>
          <div class="kv"><span>Cheating</span><strong>${cheating}</strong></div>
          <div class="kv"><span>Cheating reasons</span><strong>${esc(reasons)}</strong></div>
          <div class="kv"><span>Quality flags</span><strong>${esc(flags)}</strong></div>
          <div class="kv"><span>Silhouette</span><strong>${sil} (streak ${esc(latest.silhouette_streak || 0)})</strong></div>
          <div class="chart-title">Trend chart (recent frames) — higher line = better / closer</div>
          <canvas class="chart" data-chart-for="${esc(p.participant_id)}"></canvas>
          <div class="legend">
            <span><i class="sw" style="background:#22c55e"></i>green = lighting quality</span>
            &nbsp;·&nbsp;
            <span><i class="sw" style="background:#60a5fa"></i>blue = image quality</span>
            &nbsp;·&nbsp;
            <span><i class="sw" style="background:#f59e0b"></i>amber = mic quality</span><br>
            <span><i class="sw" style="background:#c084fc"></i>violet = behavior</span>
            &nbsp;·&nbsp;
            <span><i class="sw" style="background:#22d3ee"></i>cyan = distance (closer = higher)</span>
            &nbsp;·&nbsp;
            <span><i class="sw" style="background:#f472b6"></i>pink = noise filter</span>
          </div>
        </div>`;
      }).join('');
      setHtmlSafe('windows', windows || '<div>No participant windows yet.</div>');

      (data.participants || []).forEach((p) => {
        const canvas = document.querySelector(`canvas[data-chart-for="${CSS.escape(p.participant_id)}"]`);
        if (!canvas) return;
        const dist = (p.distance_from_camera_m || []).map((v) => v == null ? null : Math.min(1, v / 3));
        drawLines(canvas, [
          p.light_quality_score || [],
          p.image_detection_quality_score || [],
          p.microphone_quality_score || [],
          p.expression_behavior_score || [],
          dist,
          p.noise_filter_effectiveness_score || [],
        ], ['#22c55e', '#60a5fa', '#f59e0b', '#c084fc', '#22d3ee', '#f472b6']);
      });
    }

    function setStatus(text) {
      document.getElementById('tuning-status').textContent = text;
    }
    function updateTuningEffect(p, knobs, note) {
      const host = document.getElementById('tuning-effect');
      if (!host) return;
      if (!p) {
        host.innerHTML = '<h3>Tuning → live webcam</h3><div>Start the camera, then drag a slider or pick a preset — no Apply needed. Knobs change scoring thresholds — not the video picture.</div>';
        return;
      }
      const k = knobs || visionKnobs || {};
      const flags = new Set(p.quality_flags || []);
      const row = (label, reading, threshold, failed) =>
        `<div class="row"><span>${esc(label)}</span><strong class="${failed ? 'hit' : 'ok'}">${esc(reading)} vs limit ${esc(threshold)}</strong></div>`;
      host.innerHTML = `<h3>Tuning → live webcam</h3>
        <div style="color:#94a3b8;margin-bottom:6px;">${esc(note || 'Compared against active Vision knobs')}</div>
        ${row('Lighting', pct(p.light_quality_score), pct(k.light_min_quality), flags.has('lighting_below_min_quality'))}
        ${row('Sharpness', num(p.sharpness_score), num(k.sharpness_min_quality), flags.has('image_blurry'))}
        ${row('Image quality', pct(p.image_detection_quality_score), pct(k.image_min_quality), flags.has('detection_quality_low'))}
        ${row('Distance (m)', num(p.distance_from_camera_m), num(k.distance_too_close_m) + '–' + num(k.distance_too_far_m),
          flags.has('too_close_to_camera') || flags.has('too_far_from_camera'))}
        ${row('Mic quality', pct(p.microphone_quality_score), pct(k.audio_min_mic_quality), flags.has('microphone_quality_low'))}
        ${row('Noise filter', pct(p.noise_filter_effectiveness_score), pct(k.audio_min_noise_filter_effectiveness), flags.has('noise_filter_weak'))}
        <div class="row"><span>Failed checks</span><strong class="${flags.size ? 'hit' : 'ok'}">${esc(flags.size ? [...flags].join(', ') : 'none — all passed')}</strong></div>`;
    }

    function explainTuningResult(body, headline, opts) {
      const quiet = !!(opts && opts.quiet);
      const changed = Object.keys(body.changed_knobs || {});
      const flags = body.quality_flag_counts || {};
      const sessions = body.rescored_sessions || [];
      if (body.active_tuning) visionKnobs = body.active_tuning;
      const flagText = Object.keys(flags).length
        ? Object.entries(flags).map(([k, v]) => `${k}=${v}`).join(', ') : 'none';
      document.getElementById('gatecounts').textContent = flagText;
      if (body.live_camera) {
        lastLiveCamParticipant = body.live_camera;
        updateTuningEffect(body.live_camera, visionKnobs, quiet
          ? 'Live re-score while dragging'
          : 'Re-scored last webcam frame with new knobs');
        const camFlags = body.live_camera.quality_flags || [];
        const gateEl = document.getElementById('cam-gates');
        if (gateEl) {
          if (camFlags.length) {
            gateEl.textContent = 'Failed: ' + camFlags.join(', ');
            gateEl.className = 'fail';
          } else {
            gateEl.textContent = 'All quality checks passed';
            gateEl.className = 'pass';
          }
          const block = gateEl.closest('.gatesblock');
          if (block) { block.classList.remove('flash'); void block.offsetWidth; block.classList.add('flash'); }
        }
      } else if (!sessions.length && !quiet) {
        toast('No webcam/demo frame cached yet — Start camera or Load solo demo, then move a slider.');
      }
      const msg = [
        headline,
        changed.length ? `changed ${changed.length} knobs` : null,
        sessions.length ? `re-scored ${sessions.length} session(s)` : 'start camera (or Load demo) so knobs have a frame to re-score',
        body.live_camera
          ? ('live camera: ' + ((body.live_camera.quality_flags || []).join(', ') || 'all checks passed'))
          : null,
        `class gates: ${flagText}`,
      ].filter(Boolean).join(' · ');
      setStatus(msg);
      if (!quiet) toast(msg);
      if (typeof camTimer !== 'undefined' && camTimer) sampleFrame();
    }

    function flatKnobs(groups) {
      const out = [];
      groups.forEach(([, rows]) => rows.forEach((row) => out.push(row)));
      return out;
    }

    let knobPatchTimer = null;
    let knobPatchSeq = 0;
    async function patchKnob(base, name, value, opts) {
      const quiet = !!(opts && opts.quiet);
      const seq = ++knobPatchSeq;
      const res = await fetch(base, {
        method: 'PATCH',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ knobs: { [name]: Number(value) } }),
      });
      if (seq !== knobPatchSeq) return false;
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}));
        setStatus(`rejected: ${esc(detail.detail || res.status)}`);
        return false;
      }
      const body = await res.json();
      if (base.indexOf('/vision/') >= 0 || base.indexOf('/policy') >= 0) {
        explainTuningResult(body, `${name} = ${value}`, { quiet });
        if (!quiet) await refresh();
      } else {
        setStatus(`${name} = ${value} (voice — try Theodore reply below)`);
        if (!quiet) toast(`Voice knob ${name} = ${value}`);
      }
      return true;
    }

    function scheduleKnobPatch(base, name, value) {
      clearTimeout(knobPatchTimer);
      knobPatchTimer = setTimeout(() => {
        patchKnob(base, name, value, { quiet: true });
      }, 120);
    }

    function renderKnobGroups(host, groups, knobs, base) {
      host.innerHTML = groups.map(([title, rows]) => `
        <details class="knobgroup" open>
          <summary>${esc(title)} (${rows.length})</summary>
          ${rows.map(([name, min, max, step]) => `
            <div class="knob">
              <span title="${esc(name)}">${esc(name)}</span>
              <input type="range" data-knob="${esc(name)}" min="${min}" max="${max}"
                     step="${step}" value="${knobs[name]}" />
              <strong data-knob-value="${esc(name)}">${knobs[name]}</strong>
            </div>`).join('')}
        </details>`).join('');
      host.querySelectorAll('input[data-knob]').forEach((input) => {
        input.addEventListener('input', (event) => {
          const readout = host.querySelector(`[data-knob-value="${event.target.dataset.knob}"]`);
          if (readout) readout.textContent = event.target.value;
          scheduleKnobPatch(base, event.target.dataset.knob, event.target.value);
        });
      });
    }

    async function applySelectedPreset() {
      const name = document.getElementById('preset').value;
      if (!name || tuningScope === 'policy') return;
      if (tuningScope === 'voice') {
        const res = await fetch(`/api/theodore/voice/tuning/preset/${encodeURIComponent(name)}`, { method: 'POST' });
        toast(res.ok ? `Voice preset "${name}" applied — try a reply below` : `Voice preset failed`);
        if (res.ok) await loadTuning();
        return;
      }
      const res = await fetch(`/api/theodore/vision/tuning/preset/${encodeURIComponent(name)}`, { method: 'POST' });
      if (!res.ok) { toast(`Vision preset failed (${res.status})`); return; }
      explainTuningResult(await res.json(), `vision preset "${name}" applied`);
      await loadTuning();
      await refresh();
    }

    async function loadTuning() {
      const base = tuningScope === 'policy'
        ? '/api/theodore/vision/policy'
        : (tuningScope === 'voice'
          ? '/api/theodore/voice/tuning'
          : '/api/theodore/vision/tuning');
      const res = await fetch(base, { cache: 'no-store' });
      if (!res.ok) return;
      const data = await res.json();
      const select = document.getElementById('preset');
      const presetWrap = document.getElementById('preset-wrap');
      if (tuningScope === 'policy') {
        presetWrap.style.display = 'none';
        renderKnobGroups(document.getElementById('knobs'), [['Timing / session', POLICY_KNOBS]], data.knobs || {}, base);
        setStatus(`policy timing knobs (${Object.keys(data.knobs || {}).length})`);
        return;
      }
      presetWrap.style.display = '';
      const keep = data.active_preset || select.value;
      select.innerHTML = (data.presets || []).map((p) =>
        `<option value="${esc(p)}">${esc(p)}</option>`).join('');
      if (keep && (data.presets || []).includes(keep)) select.value = keep;
      const groups = tuningScope === 'voice' ? VOICE_GROUPS : VISION_GROUPS;
      renderKnobGroups(document.getElementById('knobs'), groups, data.knobs || {}, base);
      if (tuningScope === 'vision') {
        visionKnobs = data.knobs || {};
        updateTuningEffect(lastLiveCamParticipant, visionKnobs);
      }
      const model = data.model ? ` · models ${data.model.fast}/${data.model.full}` : '';
      setStatus(`${tuningScope} knobs loaded${data.active_preset ? ' · preset ' + data.active_preset : ''}${model}`);
    }

    function selectScope(scope) {
      tuningScope = scope;
      ['vision', 'voice', 'policy'].forEach((name) => {
        document.getElementById('tab-' + name).classList.toggle('active', scope === name);
      });
      loadTuning();
    }
    document.getElementById('tab-vision').addEventListener('click', () => selectScope('vision'));
    document.getElementById('tab-voice').addEventListener('click', () => selectScope('voice'));
    document.getElementById('tab-policy').addEventListener('click', () => selectScope('policy'));

    document.getElementById('preset').addEventListener('change', () => applySelectedPreset());

    document.getElementById('demo-seed').addEventListener('click', async () => {
      await seedDemo('solo');
    });
    document.getElementById('demo-seed-group').addEventListener('click', async () => {
      await seedDemo('group');
    });
    async function seedDemo(scenario) {
      const degraded = document.getElementById('demo-degraded').checked;
      const res = await fetch('/api/theodore/webcam/demo/seed', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, frames: 12, degraded, scenario }),
      });
      if (!res.ok) { toast('Demo seed failed'); return; }
      const body = await res.json();
      const ids = (body.participant_ids || []).join(',') || 'none';
      if (scenario === 'solo') {
        toast(`Solo demo: 1 student (${ids})` + (degraded ? ' · degraded' : '') +
          ' — not your webcam; use Start camera for the live feed.');
      } else {
        toast(`Group demo: 3 simulated students (${ids})` + (degraded ? ' · degraded' : '') +
          `; cheating=${(body.cheating_participant_ids||[]).join(',')||'none'}` +
          `; silhouette=${(body.silhouette_participant_ids||[]).join(',')||'none'}`);
      }
      knownAlertKeys = new Set();
      refresh();
    }
    document.getElementById('demo-roll').addEventListener('click', async () => {
      const degraded = document.getElementById('demo-degraded').checked;
      const interval = Number(document.getElementById('demo-interval').value || 1);
      const scenario = document.getElementById('demo-scenario-group').checked ? 'group' : 'solo';
      const res = await fetch('/api/theodore/webcam/demo/roll/start', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, degraded, interval_s: interval, scenario }),
      });
      toast(res.ok
        ? (`Live ${scenario} demo feed started` + (scenario === 'group' ? ' (3 simulated students)' : ' (1 student)'))
        : 'Could not start feed');
    });
    document.getElementById('demo-stop').addEventListener('click', async () => {
      await fetch('/api/theodore/webcam/demo/roll/stop', {
        method: 'POST', headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId }),
      });
      toast('Live demo feed stopped');
    });

    // Language selector — populated from /api/theodore/voice/languages on load
    let _voiceLangs = [];
    async function loadVoiceLanguages() {
      try {
        const res = await fetch('/api/theodore/voice/languages', { cache: 'no-store' });
        if (!res.ok) return;
        _voiceLangs = await res.json();
        const sel = document.getElementById('voice-lang');
        sel.innerHTML = _voiceLangs.map((l) =>
          `<option value="${esc(l.code)}">${esc(l.name)} (${esc(l.code)})</option>`
        ).join('');
        sel.value = 'en';
      } catch (_) {}
      await loadVoiceStatus();
    }
    async function loadVoiceStatus() {
      const el = document.getElementById('voice-status');
      if (!el) return;
      try {
        const res = await fetch('/api/theodore/voice/status', { cache: 'no-store' });
        if (!res.ok) { el.textContent = 'Voice status unavailable'; return; }
        const s = await res.json();
        const live = !!s.xai_api_key_configured;
        el.className = 'voice-status ' + (live ? 'live' : 'fallback');
        el.innerHTML = live
          ? `<strong>xAI Grok live</strong> · model ${esc(s.model)} · ${esc(s.languages)} languages · TTS: ${(s.tts_engine_chain||[]).join(' → ') || 'device'}`
          : `<strong>xAI key missing</strong> — local-fallback text. Set <code>XAI_API_KEY</code> and restart for live Grok. ${esc(s.languages)} languages still work · spoken audio prefers neural TTS when configured.`;
      } catch (_) {
        el.textContent = 'Could not load voice status';
      }
    }
    function voiceLangCode() {
      return document.getElementById('voice-lang').value || 'en';
    }

    // Theodore speech — neural TTS first (gateway/ElevenLabs/edge), device fallback
    let serverTts = {available: false, engine: ''};
    let theodoreAudio = null;
    async function loadTtsStatus() {
      try {
        const res = await fetch('/api/tts/status', { cache: 'no-store' });
        if (res.ok) serverTts = await res.json();
      } catch (_) { serverTts = {available: false, engine: ''}; }
    }
    loadTtsStatus();
    function stopTheodoreAudio() {
      if (theodoreAudio) {
        try { theodoreAudio.pause(); theodoreAudio.src = ''; } catch (_) {}
        theodoreAudio = null;
      }
      if ('speechSynthesis' in window) speechSynthesis.cancel();
      const actionStage = document.getElementById('theodore-action');
      if (actionStage) actionStage.classList.remove('speaking');
    }
    async function speakTheodore(text, langCode) {
      if (!text) return;
      const cleaned = String(text).replace(/^\[[^\]]+\]\s*/, '');
      stopTheodoreAudio();
      const actionStage = document.getElementById('theodore-action');
      const markSpeaking = (on) => {
        if (actionStage && actionStage.classList.contains('show')) {
          actionStage.classList.toggle('speaking', !!on);
        }
      };
      if (serverTts.available) {
        try {
          const lang = langCode || voiceLangCode() || 'en';
          const res = await fetch(
            `/api/tts?text=${encodeURIComponent(cleaned)}&language=${encodeURIComponent(lang)}&style=warm`
          );
          if (res.status === 501) {
            serverTts.available = false;
          } else if (res.ok) {
            const blob = await res.blob();
            theodoreAudio = new Audio(URL.createObjectURL(blob));
            theodoreAudio.onplay = () => markSpeaking(true);
            theodoreAudio.onended = () => markSpeaking(false);
            theodoreAudio.onerror = () => markSpeaking(false);
            await theodoreAudio.play();
            return;
          }
        } catch (_) { /* device fallback */ }
      }
      if (!('speechSynthesis' in window) || !cleaned) return;
      const utter = new SpeechSynthesisUtterance(cleaned);
      utter.lang = langCode || voiceLangCode() || 'en';
      utter.rate = 0.92;
      utter.pitch = 1.0;
      utter.volume = 1.0;
      const voices = speechSynthesis.getVoices() || [];
      const want = (utter.lang || 'en').slice(0, 2).toLowerCase();
      const match = voices.find((v) => (v.lang || '').toLowerCase().startsWith(want))
        || voices.find((v) => (v.lang || '').toLowerCase().startsWith('en'));
      if (match) utter.voice = match;
      utter.onstart = () => markSpeaking(true);
      utter.onend = () => markSpeaking(false);
      utter.onerror = () => markSpeaking(false);
      speechSynthesis.speak(utter);
    }
    function autoSpeak() { return document.getElementById('voice-autospeak').checked; }

    // Voice try panel (xAI Grok + language)
    document.getElementById('voice-ask').addEventListener('click', async () => {
      const topic = document.getElementById('voice-topic').value || 'fractions';
      const lang = voiceLangCode();
      const res = await fetch('/api/theodore/voice/ask-question', {
        method: 'POST', headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ class_mode: 'solo', language_code: lang, topic }),
      });
      const body = await res.json().catch(() => ({}));
      document.getElementById('voice-out').textContent = res.ok
        ? `Q: ${body.question}\\nHint: ${body.hint}\\nprovider=${body.provider} lang=${body.language_code} fallback=${body.fallback_used}`
        : JSON.stringify(body);
      if (res.ok && autoSpeak()) speakTheodore(body.question, lang);
    });
    document.getElementById('voice-reply').addEventListener('click', async () => {
      const msg = document.getElementById('voice-msg').value || 'Can you explain that again?';
      const lang = voiceLangCode();
      const res = await fetch('/api/theodore/voice/respond', {
        method: 'POST', headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ class_mode: 'solo', language_code: lang, learner_message: msg, session_id: sessionId }),
      });
      const body = await res.json().catch(() => ({}));
      document.getElementById('voice-out').textContent = res.ok
        ? `${body.message}\\nprovider=${body.provider} style=${body.communication_style} fallback=${body.fallback_used} tts=${(body.tts_engine_chain||[]).join('→')}`
        : JSON.stringify(body);
      if (res.ok && autoSpeak()) speakTheodore(body.message, lang);
    });
    document.getElementById('voice-speak').addEventListener('click', () => {
      const text = document.getElementById('voice-out').textContent.split('\\n')[0];
      speakTheodore(text, voiceLangCode());
    });
    document.getElementById('voice-stop-speak').addEventListener('click', () => {
      stopTheodoreAudio();
    });
    document.getElementById('voice-absorb').addEventListener('click', async () => {
      const transcript = document.getElementById('voice-msg').value || '';
      const lang = voiceLangCode();
      const res = await fetch('/api/theodore/voice/absorb-audio-answer', {
        method: 'POST', headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          class_mode: 'solo',
          language_code: lang,
          question: document.getElementById('voice-topic').value || 'Explain the idea in your own words',
          audio_transcript: transcript,
          expected_answer: 'a short clear explanation',
        }),
      });
      const body = await res.json().catch(() => ({}));
      const line = body.feedback_message || body.feedback || body.summary || body.message || JSON.stringify(body);
      document.getElementById('voice-out').textContent = res.ok
        ? `Absorb: ${line}\\nunderstood=${body.understood} score=${body.correctness_score} provider=${body.provider}`
        : JSON.stringify(body);
      if (res.ok && autoSpeak()) speakTheodore(line, lang);
    });

    document.getElementById('tuning-prove').addEventListener('click', async () => {
      // Make scoring effect unmistakable: tighten light gate → expect FAIL, then restore.
      if (!lastLiveCamParticipant && !(typeof camTimer !== 'undefined' && camTimer)) {
        toast('Start camera (or Load solo demo) first so knobs have a frame to score.');
      }
      const tight = await fetch('/api/theodore/vision/tuning', {
        method: 'PATCH', headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ knobs: { light_min_quality: 0.99, image_min_quality: 0.99 } }),
      });
      const body = await tight.json().catch(() => ({}));
      explainTuningResult(body, 'prove: tightened light/image gates');
      const flags = (body.live_camera && body.live_camera.quality_flags) || [];
      toast(flags.length
        ? ('Tuning works — camera now fails: ' + flags.join(', '))
        : (body.rescored_sessions && body.rescored_sessions.length
          ? 'Re-scored demo frames — check Failed quality checks / student windows'
          : 'No frame cached yet. Start camera, wait 1s, click Prove again.'));
      setTimeout(async () => {
        const res = await fetch('/api/theodore/vision/tuning/preset/balanced', { method: 'POST' });
        if (res.ok) explainTuningResult(await res.json(), 'prove: restored balanced preset');
        await loadTuning();
      }, 2200);
    });

    // Shutdown — stop polls BEFORE wiping the DOM so refresh cannot throw on null nodes.
    document.getElementById('shutdown-btn').addEventListener('click', async () => {
      if (!confirm('Shut down the lab server and free the port?')) return;
      labOffline = true;
      stopMetricsPolling();
      stopCamera();
      try { await fetch('/admin/shutdown', { method: 'POST' }); } catch (_) {}
      document.body.innerHTML = '<div style="padding:60px;text-align:center;font-family:Arial,sans-serif;color:#94a3b8;background:#0f172a;min-height:100vh;">'
        + '<h2 style="color:#e2e8f0;">Theodore Lab shut down</h2>'
        + '<p>The server has stopped and the port is free.</p>'
        + '<p style="font-size:12px;">Run <code style="background:#1f2937;padding:2px 6px;border-radius:4px;">python3 -m uvicorn theodore_webcam_lab.main:app --app-dir subrepos/theodore_webcam_lab/src --host 0.0.0.0 --port 8015</code> to restart.</p>'
        + '</div>';
    });
    window.addEventListener('pagehide', () => {
      labOffline = true;
      stopMetricsPolling();
      try { if (typeof stopCamera === 'function') stopCamera(); } catch (_) {}
    });

    // Games panel
    document.getElementById('game-issue').addEventListener('click', async () => {
      const res = await fetch('/api/theodore/webcam/games/challenge', {
        method: 'POST', headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          mode: 'group',
          learning_prompt: document.getElementById('game-prompt').value || 'Stay focused on the lesson.',
          participant_ids: ['student-a', 'student-b'],
        }),
      });
      const body = await res.json();
      if (!res.ok) { toast('Challenge failed'); return; }
      activeChallenge = body;
      document.getElementById('game-status').textContent =
        `${body.title}: ${body.instruction} [${body.challenge_id}]`;
      toast('Challenge issued: ' + body.title);
    });
    document.getElementById('game-attempt').addEventListener('click', async () => {
      if (!activeChallenge || !activeChallenge.challenge_id) {
        toast('Issue a challenge first');
        return;
      }
      const res = await fetch('/api/theodore/webcam/games/attempt', {
        method: 'POST', headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          challenge_id: activeChallenge.challenge_id,
          session_id: sessionId,
          mode: 'group',
          signals: [{
            participant_id: 'student-a',
            timestamp_ms: Date.now() % 100000000,
            face_count: 1,
            liveness_state: 'live',
            gaze_frontal: 0.9,
            gaze_down_score: 0.05,
            expression_label: 'happy',
            phone_visible: false,
          }],
        }),
      });
      const body = await res.json();
      document.getElementById('game-status').textContent = res.ok
        ? `${body.passed ? 'PASSED' : 'FAILED'} Δ${body.score_delta} total=${body.total_score} streak=${body.streak} — ${body.feedback}`
        : (body.detail || 'attempt failed');
      toast(res.ok ? (body.passed ? 'Challenge passed' : 'Challenge failed') : 'Attempt error');
    });

    // Camera path — HD Ready / Full HD 16:9
    const CAM_IDEAL_W = 1920, CAM_IDEAL_H = 1080;  // Full HD request
    const CAM_FALLBACK_W = 1280, CAM_FALLBACK_H = 720;  // HD Ready
    const GRID_W = 64, GRID_H = 36;  // 16:9 downsample for Sobel
    // Test pattern: a camera-free way to drive the Sobel/exposure gates. Each
    // stage is tuned against the default VisionTuning so it trips exactly the
    // flags named in `expects` - sweeping them proves the gates really fire.
    // `sigma` is Gaussian blur in GRID pixels; `dark`/`light` are 0..255 luma.
    const PATTERN_PERIOD_GRID = 8;   // bar period, in grid pixels
    const PATTERN_STAGE_FRAMES = 7;  // ~2.1s per stage at the 300ms sample rate
    const PATTERN_STAGES = [
      { name: 'sharp · well lit', dark: 71, light: 184, sigma: 0,
        expects: 'baseline — no gates should trip' },
      { name: 'mild blur', dark: 71, light: 184, sigma: 1,
        expects: 'sharpness falls, still above the floor' },
      { name: 'heavy blur', dark: 71, light: 184, sigma: 2,
        expects: 'image_blurry + low_edge_detail' },
      { name: 'low contrast', dark: 104, light: 150, sigma: 0,
        expects: 'low_edge_detail (sharp, but no usable detail)' },
      // Kept high-contrast on purpose so these two isolate the lighting gates
      // instead of also tripping low_edge_detail.
      { name: 'underexposed', dark: 10, light: 92, sigma: 0,
        expects: 'lighting_underexposed + lighting_below_min_quality' },
      { name: 'overexposed', dark: 175, light: 255, sigma: 0,
        expects: 'lighting_overexposed + lighting_below_min_quality' },
    ];
    const camVideo = document.getElementById('cam');
    const grab = document.getElementById('grab');
    const overlay = document.getElementById('cam-overlay');
    const patternCanvas = document.getElementById('pattern-canvas');
    const camFrame = document.querySelector('.cam-frame');
    let camStream = null, camTimer = null, patternPhase = 0;
    let lastAutoLightAt = 0;
    async function tryAutoLighting() {
      // Best-effort continuous exposure / brightness when the room is pitch dark.
      if (!camStream) return;
      const now = Date.now();
      if (now - lastAutoLightAt < 8000) return;
      lastAutoLightAt = now;
      const track = camStream.getVideoTracks()[0];
      if (!track || !track.getCapabilities || !track.applyConstraints) return;
      let caps = {};
      try { caps = track.getCapabilities() || {}; } catch (_) { return; }
      const advanced = {};
      if (caps.exposureMode && caps.exposureMode.includes && caps.exposureMode.includes('continuous')) {
        advanced.exposureMode = 'continuous';
      }
      if (caps.whiteBalanceMode && caps.whiteBalanceMode.includes && caps.whiteBalanceMode.includes('continuous')) {
        advanced.whiteBalanceMode = 'continuous';
      }
      if (caps.exposureCompensation && typeof caps.exposureCompensation.max === 'number' && caps.exposureCompensation.max > 0) {
        advanced.exposureCompensation = Math.min(caps.exposureCompensation.max, 0.7);
      }
      if (caps.brightness && typeof caps.brightness.min === 'number' && typeof caps.brightness.max === 'number') {
        advanced.brightness = (caps.brightness.min + caps.brightness.max) / 2 + (caps.brightness.max - caps.brightness.min) * 0.15;
      }
      if (!Object.keys(advanced).length) return;
      try {
        await track.applyConstraints({ advanced: [advanced] });
        toast('Tried auto-brighten the camera — please also turn on a room light.');
      } catch (_) {
        try { await track.applyConstraints(advanced); } catch (__) {}
      }
    }
    let usingPattern = false, usingSilhouette = false, lastSilhouetteDetected = false;
    let silhouetteGuideOn = true;
    let audioCtx = null, audioAnalyser = null, audioSource = null, audioData = null;
    let audioRmsHistory = [];
    let lastAudioSample = null;
    let noiseSuppressionOn = null;
    let clickAnalyser = null, clickData = null;
    let clickNoiseFloor = 0.003, clickPrevRms = 0;
    let clickEvents = [];
    let toneActiveMs = 0, ringtoneLatchUntil = 0;
    let voiceActiveMs = 0;
    let musicActiveMs = 0;
    // The click/ringtone detector runs on its own fast timer: the 300ms video
    // cadence only exposes ~21ms of audio per tick (a 7% duty cycle), which is
    // far too sparse to catch a keystroke transient or the onset of a ring.
    const AUDIO_POLL_MS = 25;
    let audioPollTimer = null;
    let rawMicStream = null, rawMicSource = null;
    let clickSourceRaw = false;
    let clickBins = null;
    let clickLevelDb = -120, clickFloorDb = -120;
    let clickPrevFreq = null, tonePeakBin = -1;
    const silToggle = document.getElementById('cam-sil-toggle');
    const silToggleLabel = document.getElementById('cam-sil-toggle-label');

    // --- Stare geometry lab --------------------------------------------------
    // Looking at a phone and looking at a low-mounted laptop webcam both pitch the
    // head down, so an absolute angle cannot separate them. What does separate them
    // is tilt measured FROM WHERE THE LEARNER ACTUALLY SITS (the neutral
    // calibration) compared against the angle THIS screen needs from THIS distance:
    // theta_screen = atan(y_screen / D). The leftover is the residual, and a
    // residual near zero means the learner is on the lesson band.
    //
    // These formulas are duplicated from stare_geometry.py because the lab needs
    // them before the round trip; tests/test_stare_geometry.py parses this JS and
    // asserts the two sides produce the same numbers.
    // v2: a v1 neutral was captured against the old pitch (face height in frame),
    // so restoring one would offset the new gauge by tens of degrees. Any change
    // to what raw pitch means has to retire stored calibrations with it.
    const TILT_STORE_KEY = 'twl.tilt.calibration.v2';
    const TILT_SMOOTH_FRAMES = 3;
    const STARE_MIN_DISTANCE_M = 0.25;
    const STARE_RESIDUAL_SOFT_DEG = 12;
    const STARE_PHONE_RESIDUAL_DEG = 14;
    const STARE_RESIDUAL_SPAN_DEG = 16;
    const STARE_GAZE_DOWN_DEADBAND_DEG = 6;
    const STARE_GAZE_DOWN_SPAN_DEG = 30;
    const STARE_LAYOUTS = {
      laptop_14: { label: '14" laptop', yScreen: 0.14 },
      laptop_16: { label: '16" laptop', yScreen: 0.18 },
      external_monitor_webcam_top: { label: 'Monitor, webcam on top', yScreen: 0.24 },
    };
    // Enough frames to average out landmark jitter, few enough that the gauge is
    // live about a second after the face appears.
    const TILT_AUTO_NEUTRAL_FRAMES = 12;
    // Sign learning: the matrix and landmark pose paths disagree on which way
    // head_pose_pitch runs, so correlate it against the geometric proxy (whose
    // sign is fixed by construction) instead of asking the operator.
    const TILT_SIGN_WINDOW = 40;
    const TILT_SIGN_MIN_SPREAD_DEG = 4;
    let tiltNeutralDeg = null;
    let tiltDownSign = -1;
    let tiltSignCalibrated = false;
    let tiltTripDeg = 20;
    let tiltRawDeg = null, tiltDownDeg = null;
    let tiltPeakDown = null, tiltPeakUp = null;
    let tiltRawHistory = [];
    let tiltGazeDown = null;
    let tiltNeutralAuto = false;
    let tiltNeutralSamples = [];
    let tiltPoseSource = null;
    let stareLayoutKey = 'laptop_16';
    let stareYScreenM = STARE_LAYOUTS.laptop_16.yScreen;
    let stareDistanceM = null;
    let stareExpectedDeg = null, stareResidualDeg = null;
    let stareMatch = null, starePhone = null, stareGazeDown = null;
    let tiltSignPitchSamples = [], tiltSignGeomSamples = [];

    function loadTiltCalibration() {
      try {
        const stored = JSON.parse(localStorage.getItem(TILT_STORE_KEY) || 'null');
        if (!stored) return;
        if (Number.isFinite(stored.neutral)) tiltNeutralDeg = stored.neutral;
        if (stored.sign === 1 || stored.sign === -1) {
          tiltDownSign = stored.sign;
          tiltSignCalibrated = !!stored.signCalibrated;
        }
        if (Number.isFinite(stored.trip)) tiltTripDeg = stored.trip;
        if (STARE_LAYOUTS[stored.layout]) stareLayoutKey = stored.layout;
        stareYScreenM = Number.isFinite(stored.yScreen)
          ? stored.yScreen : STARE_LAYOUTS[stareLayoutKey].yScreen;
      } catch (_) { /* private mode / disabled storage */ }
    }

    function saveTiltCalibration() {
      try {
        localStorage.setItem(TILT_STORE_KEY, JSON.stringify({
          neutral: tiltNeutralAuto ? null : tiltNeutralDeg, sign: tiltDownSign,
          signCalibrated: tiltSignCalibrated, trip: tiltTripDeg,
          layout: stareLayoutKey, yScreen: stareYScreenM,
        }));
      } catch (_) { /* non-fatal */ }
    }

    function resetTiltPeaks() {
      tiltPeakDown = null;
      tiltPeakUp = null;
      // Drop the smoothing window too: leftover frames from the previous pose
      // would otherwise bleed into the next trial's peak.
      tiltRawHistory = [];
      renderTiltLab();
    }

    function expectedScreenPitchDeg(distanceM) {
      if (distanceM == null || !Number.isFinite(distanceM) || distanceM <= 0) return null;
      const d = Math.max(distanceM, STARE_MIN_DISTANCE_M);
      return Math.atan(stareYScreenM / d) * (180 / Math.PI);
    }

    function screenMatchScore(residual) {
      if (residual == null) return null;
      return clamp01(1 - Math.abs(residual) / STARE_RESIDUAL_SOFT_DEG);
    }

    function phoneStareScore(residual) {
      if (residual == null) return null;
      return clamp01((residual - STARE_PHONE_RESIDUAL_DEG) / STARE_RESIDUAL_SPAN_DEG);
    }

    function gazeDownFromResidual(residual) {
      if (residual == null) return null;
      return clamp01((residual - STARE_GAZE_DOWN_DEADBAND_DEG) / STARE_GAZE_DOWN_SPAN_DEG);
    }

    // --- Trajectory attention (face/hand history) ---------------------------
    // Mirrored by trajectory_geometry.py; parity-tested in test_trajectory_geometry.py.
    const TRAJ_HISTORY_MAX = 12;  // ~3.6 s at 300 ms sample rate
    const TRAJ_GLOBAL_MOTION_SUPPRESS = 0.55;
    const TRAJ_FACE_ENERGY_REF = 0.35;
    const TRAJ_HAND_ENERGY_REF = 0.55;
    const TRAJ_SAG_REF_DEG_PER_S = 8;
    let faceLandmarkHistory = [];
    let lastTrajectory = null;

    function trajMeanSpeed(history, getter) {
      if (!history || history.length < 3) return 0;
      let sum = 0, n = 0;
      for (let i = 1; i < history.length; i++) {
        const prev = history[i - 1], cur = history[i];
        const a = getter(prev), b = getter(cur);
        if (a == null || b == null) continue;
        const dt = Math.max(1, cur.t - prev.t) / 1000;
        sum += Math.abs(b - a) / dt;
        n += 1;
      }
      return n ? sum / n : 0;
    }

    function trajFaceMotionEnergy(history) {
      if (!history || history.length < 3) return 0;
      const size = history.reduce((s, h) => s + Math.max(0.05, h.faceSize), 0) / history.length;
      const scaled = (getter) => trajMeanSpeed(history, getter) / size;
      const energy = (scaled((h) => h.noseY) + scaled((h) => h.browY)
        + scaled((h) => h.chinY) + scaled((h) => h.eyeMidX) * 0.5) / 3.5;
      return clamp01(energy / TRAJ_FACE_ENERGY_REF);
    }

    function trajHandGestureEnergy(history) {
      if (!history || history.length < 3) return 0;
      const energy = Math.max(
        trajMeanSpeed(history, (h) => h.handWristY),
        trajMeanSpeed(history, (h) => h.handTipY),
      );
      return clamp01(energy / TRAJ_HAND_ENERGY_REF);
    }

    function trajHeadSagRate(history) {
      const pitched = (history || []).filter((h) => h.pitch != null && Number.isFinite(h.pitch));
      if (pitched.length < 3) return 0;
      const first = pitched[0], last = pitched[pitched.length - 1];
      const dt = Math.max(1, last.t - first.t) / 1000;
      let rate = Math.max(0, last.pitch - first.pitch) / dt;
      let steps = 0, down = 0;
      for (let i = 1; i < pitched.length; i++) {
        const d = pitched[i].pitch - pitched[i - 1].pitch;
        steps += 1;
        if (d > 0.05) down += 1;
      }
      if (steps && down / steps < 0.55) rate *= 0.35;
      return clamp01(rate / TRAJ_SAG_REF_DEG_PER_S);
    }

    function trajExcitementScore(faceE, handE, globalMotion, brow, smile) {
      if (globalMotion >= TRAJ_GLOBAL_MOTION_SUPPRESS) return 0;
      const burst = Math.max(faceE, handE * 0.85);
      const express = Math.max(brow || 0, smile || 0) * 0.35;
      const shaped = clamp01((burst - 0.18) / 0.55) * (1 - clamp01((burst - 0.85) / 0.20));
      return clamp01(shaped * 0.75 + express + faceE * 0.15);
    }

    function trajInterestScore(faceSizeDelta, gazeFrontal, brow, faceE, globalMotion, fidget) {
      if (globalMotion >= TRAJ_GLOBAL_MOTION_SUPPRESS || (fidget || 0) >= 0.70) return 0;
      const lean = clamp01(faceSizeDelta / 0.08);
      const quiet = 1 - clamp01((faceE - 0.25) / 0.55);
      return clamp01(0.45 * lean + 0.30 * clamp01(gazeFrontal || 0)
        + 0.15 * (brow || 0) + 0.10 * quiet);
    }

    function trajDozingScore(sag, faceE, eyesClosed) {
      const still = 1 - clamp01(faceE / 0.40);
      let base = 0.55 * sag + 0.35 * still + 0.25 * clamp01(eyesClosed || 0);
      if (sag < 0.15 && (eyesClosed || 0) < 0.35) base *= 0.25;
      return clamp01(base);
    }

    function trajExternalMusicScore(elevated, flux, prominence, steadyPeak, speechRatio, sharpAttack, musicActiveMs) {
      if (sharpAttack || !elevated) return 0;
      let musical = (flux >= 2.0 || !steadyPeak) && prominence < 14.0;
      if (speechRatio > 0.62 && flux < 2.0) musical = false;
      if (!musical) return 0;
      return clamp01(musicActiveMs / 2000);
    }

    function trajHeldObjectScore(phoneGrid, phoneStare, handBelow, lowerBlob) {
      const grid = clamp01(phoneGrid || 0);
      const stare = clamp01(phoneStare || 0);
      const hand = clamp01(handBelow || 0);
      const blob = clamp01(lowerBlob || 0);
      if (grid < 0.20 && stare < 0.25 && blob < 0.25) return 0;
      return clamp01(Math.max(
        grid * 0.55 + hand * 0.45,
        stare * 0.70 + hand * 0.30,
        blob * 0.50 + hand * 0.40,
      ));
    }

    function pushTrajectorySample(sample) {
      faceLandmarkHistory.push(sample);
      while (faceLandmarkHistory.length > TRAJ_HISTORY_MAX) faceLandmarkHistory.shift();
    }

    function computeTrajectoryFeatures(opts) {
      const history = faceLandmarkHistory;
      if (!history.length || (opts && opts.detector !== 'face_mesh')) {
        lastTrajectory = null;
        return null;
      }
      const faceE = trajFaceMotionEnergy(history);
      const handE = trajHandGestureEnergy(history);
      const sag = trajHeadSagRate(history);
      const last = history[history.length - 1];
      const first = history[0];
      const faceSizeDelta = last.faceSize - first.faceSize;
      const reading = {
        face_motion_energy: faceE,
        hand_gesture_energy: handE,
        head_sag_rate: sag,
        excitement_score: trajExcitementScore(
          faceE, handE, opts.globalMotion || 0, last.brow, last.smile),
        interest_score: trajInterestScore(
          faceSizeDelta, last.gazeFrontal, last.brow, faceE,
          opts.globalMotion || 0, opts.fidget || 0),
        dozing_score: trajDozingScore(sag, faceE, opts.eyesClosed || 0),
      };
      lastTrajectory = reading;
      return reading;
    }

    // Which way does head_pose_pitch grow when the head goes down? Compare its
    // spread against the geometric proxy over a rolling window; they move
    // together (+1) or opposite (-1). Falls back to the assumed sign until the
    // learner has actually moved enough for the answer to mean anything.
    function learnTiltSign(rawPitch, geomPitch) {
      if (tiltSignCalibrated || geomPitch == null || rawPitch == null) return;
      tiltSignPitchSamples.push(rawPitch);
      tiltSignGeomSamples.push(geomPitch);
      if (tiltSignPitchSamples.length > TILT_SIGN_WINDOW) {
        tiltSignPitchSamples.shift();
        tiltSignGeomSamples.shift();
      }
      if (tiltSignPitchSamples.length < TILT_SIGN_WINDOW) return;
      const spread = (arr) => Math.max(...arr) - Math.min(...arr);
      if (spread(tiltSignGeomSamples) < TILT_SIGN_MIN_SPREAD_DEG) return;
      if (spread(tiltSignPitchSamples) < TILT_SIGN_MIN_SPREAD_DEG) return;
      const mean = (arr) => arr.reduce((a, b) => a + b, 0) / arr.length;
      const mp = mean(tiltSignPitchSamples), mg = mean(tiltSignGeomSamples);
      let cov = 0;
      for (let i = 0; i < tiltSignPitchSamples.length; i++) {
        cov += (tiltSignPitchSamples[i] - mp) * (tiltSignGeomSamples[i] - mg);
      }
      if (cov === 0) return;
      tiltDownSign = cov > 0 ? 1 : -1;
      tiltSignCalibrated = true;
      saveTiltCalibration();
    }

    function updateTiltLab(facial, distanceM) {
      const raw = facial ? facial.head_pose_pitch : null;
      const geom = facial ? facial.head_pitch_geom_deg : null;
      const poseSource = facial ? (facial.pose_source || null) : null;
      if (raw == null || !Number.isFinite(Number(raw))) {
        tiltRawDeg = null;
        tiltDownDeg = null;
        tiltRawHistory = [];
        stareExpectedDeg = null; stareResidualDeg = null;
        stareMatch = null; starePhone = null; stareGazeDown = null;
        renderTiltLab();
        return;
      }
      // A neutral learned against one pose source means nothing to the other.
      if (tiltPoseSource && poseSource && poseSource !== tiltPoseSource && tiltNeutralAuto) {
        tiltNeutralDeg = null;
        tiltNeutralSamples = [];
      }
      if (poseSource) tiltPoseSource = poseSource;
      tiltRawHistory.push(Number(raw));
      if (tiltRawHistory.length > TILT_SMOOTH_FRAMES) tiltRawHistory.shift();
      tiltRawDeg = tiltRawHistory.reduce((a, b) => a + b, 0) / tiltRawHistory.length;
      tiltGazeDown = (facial.gaze_down_score != null) ? Number(facial.gaze_down_score) : null;
      if (Number.isFinite(Number(geom))) learnTiltSign(tiltRawDeg, Number(geom));
      // Auto-neutral: the gauge used to sit blank until someone pressed Set
      // neutral, so the only mark on it was the trip line and it read as a needle
      // frozen at 20 degrees. Seed a neutral from the first steady second of
      // tracking instead; Set neutral still overrides it.
      if (tiltNeutralDeg == null) {
        tiltNeutralSamples.push(tiltRawDeg);
        if (tiltNeutralSamples.length >= TILT_AUTO_NEUTRAL_FRAMES) {
          const sorted = tiltNeutralSamples.slice().sort((a, b) => a - b);
          tiltNeutralDeg = sorted[Math.floor(sorted.length / 2)];
          tiltNeutralAuto = true;
          tiltNeutralSamples = [];
        }
      }
      if (tiltNeutralDeg != null) {
        tiltDownDeg = (tiltRawDeg - tiltNeutralDeg) * tiltDownSign;
        if (tiltPeakDown == null || tiltDownDeg > tiltPeakDown) tiltPeakDown = tiltDownDeg;
        if (tiltPeakUp == null || tiltDownDeg < tiltPeakUp) tiltPeakUp = tiltDownDeg;
      } else {
        tiltDownDeg = null;
      }
      if (distanceM != null && Number.isFinite(Number(distanceM))) stareDistanceM = Number(distanceM);
      recomputeStare();
    }

    // Also called when the layout controls change, so editing y_screen updates
    // the residual and the overlay marker without waiting for the next frame.
    function recomputeStare() {
      stareExpectedDeg = expectedScreenPitchDeg(stareDistanceM);
      stareResidualDeg = (tiltDownDeg != null && stareExpectedDeg != null)
        ? tiltDownDeg - stareExpectedDeg : null;
      stareMatch = screenMatchScore(stareResidualDeg);
      starePhone = phoneStareScore(stareResidualDeg);
      stareGazeDown = gazeDownFromResidual(stareResidualDeg);
      renderTiltLab();
      if (camTimer) refreshSilhouetteGuide();
    }

    function tiltDeg(value, digits) {
      if (value == null || !Number.isFinite(value)) return '—';
      const d = digits == null ? 1 : digits;
      return (value >= 0 ? '+' : '') + value.toFixed(d) + '°';
    }

    function renderTiltLab() {
      const set = (id, text, cls) => {
        const el = document.getElementById(id);
        if (!el) return;
        el.textContent = text;
        el.className = 'tilt-chip' + (cls ? ' ' + cls : '');
      };
      const suffix = tiltSignCalibrated ? '' : ' (direction assumed)';
      set('tilt-down', tiltDownDeg == null
        ? (tiltRawDeg == null ? 'down —' : 'down — calibrating')
        : 'down ' + tiltDeg(tiltDownDeg) + suffix);
      set('tilt-raw', 'raw pitch ' + tiltDeg(tiltRawDeg)
        + (tiltNeutralDeg != null
          ? ' · neutral ' + tiltDeg(tiltNeutralDeg) + (tiltNeutralAuto ? ' (auto)' : '')
          : ''));
      set('tilt-gaze', 'gaze_down ' + (tiltGazeDown == null ? '—' : tiltGazeDown.toFixed(2)));
      set('tilt-peak', 'peak down ' + tiltDeg(tiltPeakDown) + ' / up ' + tiltDeg(tiltPeakUp));
      set('stare-distance', 'D ' + (stareDistanceM == null ? '—' : stareDistanceM.toFixed(2) + ' m'));
      set('stare-expected', 'θ_screen ' + tiltDeg(stareExpectedDeg)
        + ' · y ' + stareYScreenM.toFixed(2) + ' m');
      set('stare-residual', 'residual ' + tiltDeg(stareResidualDeg));
      set('stare-scores', 'match ' + (stareMatch == null ? '—' : stareMatch.toFixed(2))
        + ' · phone-stare ' + (starePhone == null ? '—' : starePhone.toFixed(2)));

      if (tiltDownDeg == null) {
        set('tilt-verdict', tiltRawDeg == null ? 'no face yet' : 'learning neutral…');
      } else if (stareResidualDeg == null) {
        set('tilt-verdict', 'no distance yet — start the camera');
      } else if (starePhone > 0) {
        set('tilt-verdict', 'staring below the screen', 'hot');
      } else if (stareResidualDeg >= STARE_RESIDUAL_SOFT_DEG) {
        set('tilt-verdict', 'past the lesson band', 'warm');
      } else {
        set('tilt-verdict', 'on the lesson band', 'cool');
      }
    }

    // Vertical protractor down the right edge of the video: degrees below the
    // calibrated neutral, with the trip line and the trial peak marked.
    function drawTiltGauge() {
      if (tiltRawDeg == null) return;
      const { w, h } = syncOverlaySize();
      const ctx = overlay.getContext('2d');
      const top = h * 0.14, bottom = h * 0.86;
      const cx = w - Math.max(46, w * 0.085);
      const minDeg = -20, maxDeg = 60;   // up ... down
      const yFor = (deg) => top + ((Math.max(minDeg, Math.min(maxDeg, deg)) - minDeg)
        / (maxDeg - minDeg)) * (bottom - top);
      const tickPx = Math.max(9, Math.round(w * 0.016));
      const labelPx = Math.max(10, Math.round(w * 0.017));
      const barW = Math.max(4, w * 0.006);

      ctx.save();
      ctx.fillStyle = 'rgba(8, 12, 20, 0.72)';
      ctx.fillRect(cx - Math.max(30, w * 0.055), top - tickPx * 2.4,
        Math.max(64, w * 0.11), (bottom - top) + tickPx * 4.4);

      ctx.strokeStyle = 'rgba(148, 163, 184, 0.85)';
      ctx.lineWidth = Math.max(1.5, w * 0.0022);
      ctx.beginPath();
      ctx.moveTo(cx, top);
      ctx.lineTo(cx, bottom);
      ctx.stroke();

      ctx.font = `${tickPx}px Arial, sans-serif`;
      ctx.textBaseline = 'middle';
      for (let deg = minDeg; deg <= maxDeg; deg += 10) {
        const y = yFor(deg);
        const major = deg % 20 === 0;
        ctx.beginPath();
        ctx.moveTo(cx - (major ? barW * 2.2 : barW), y);
        ctx.lineTo(cx + (major ? barW * 2.2 : barW), y);
        ctx.strokeStyle = deg === 0 ? '#e2e8f0' : 'rgba(148, 163, 184, 0.7)';
        ctx.lineWidth = deg === 0 ? Math.max(2, w * 0.003) : Math.max(1, w * 0.0016);
        ctx.stroke();
        if (major) {
          ctx.fillStyle = deg === 0 ? '#e2e8f0' : '#94a3b8';
          ctx.textAlign = 'right';
          ctx.fillText(String(deg), cx - barW * 3, y);
        }
      }

      // Trip line the operator is evaluating.
      const tripY = yFor(tiltTripDeg);
      ctx.setLineDash([Math.max(5, w * 0.01), Math.max(4, w * 0.007)]);
      ctx.strokeStyle = '#ef4444';
      ctx.lineWidth = Math.max(1.5, w * 0.0022);
      ctx.beginPath();
      ctx.moveTo(cx - barW * 2.6, tripY);
      ctx.lineTo(cx + barW * 3.4, tripY);
      ctx.stroke();
      ctx.setLineDash([]);

      // Where the lesson band actually sits for this seat: atan(y_screen / D).
      // The needle resting on this line is "watching the lesson"; well below it
      // is a stare the screen does not explain.
      if (stareExpectedDeg != null) {
        const ey = yFor(stareExpectedDeg);
        ctx.strokeStyle = 'rgba(129, 140, 248, 0.95)';
        ctx.lineWidth = Math.max(1.5, w * 0.0024);
        ctx.beginPath();
        ctx.moveTo(cx - barW * 3.4, ey);
        ctx.lineTo(cx + barW * 3.4, ey);
        ctx.stroke();
        const bandDeg = Math.min(STARE_RESIDUAL_SOFT_DEG, maxDeg - stareExpectedDeg);
        if (bandDeg > 0) {
          ctx.fillStyle = 'rgba(129, 140, 248, 0.20)';
          ctx.fillRect(cx - barW * 3.4, yFor(stareExpectedDeg - bandDeg),
            barW * 6.8, yFor(stareExpectedDeg + bandDeg) - yFor(stareExpectedDeg - bandDeg));
        }
        ctx.font = `${Math.max(8, Math.round(tickPx * 0.8))}px Arial, sans-serif`;
        ctx.textAlign = 'left';
        ctx.fillStyle = '#c7d2fe';
        ctx.fillText('screen', cx + barW * 4, ey);
      }

      // Furthest tilt of the current trial.
      if (tiltPeakDown != null) {
        const py = yFor(tiltPeakDown);
        ctx.fillStyle = 'rgba(251, 191, 36, 0.95)';
        ctx.beginPath();
        ctx.moveTo(cx + barW * 1.2, py);
        ctx.lineTo(cx + barW * 3.4, py - barW * 1.1);
        ctx.lineTo(cx + barW * 3.4, py + barW * 1.1);
        ctx.closePath();
        ctx.fill();
      }

      if (tiltDownDeg != null) {
        const y = yFor(tiltDownDeg);
        const hot = tiltDownDeg >= tiltTripDeg;
        ctx.fillStyle = hot ? '#f87171' : '#5eead4';
        ctx.beginPath();
        ctx.moveTo(cx - barW * 1.2, y);
        ctx.lineTo(cx - barW * 3.6, y - barW * 1.3);
        ctx.lineTo(cx - barW * 3.6, y + barW * 1.3);
        ctx.closePath();
        ctx.fill();
        ctx.beginPath();
        ctx.arc(cx, y, barW * 0.9, 0, Math.PI * 2);
        ctx.fill();

        ctx.font = `bold ${labelPx}px Arial, sans-serif`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'alphabetic';
        ctx.fillStyle = hot ? '#fecaca' : '#99f6e4';
        ctx.fillText(tiltDeg(tiltDownDeg, 0), cx, top - tickPx * 0.9);
      }
      ctx.font = `${tickPx}px Arial, sans-serif`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'alphabetic';
      ctx.fillStyle = '#94a3b8';
      ctx.fillText('tilt', cx, bottom + tickPx * 2.6);
      ctx.restore();
    }

    function setCamState(text, kind) {
      const el = document.getElementById('cam-state');
      el.textContent = text;
      el.className = 'pill' + (kind ? ' ' + kind : '');
    }

    function setCamResolutionLabel(text) {
      const el = document.getElementById('cam-res');
      if (el) el.textContent = text;
    }

    // Quick away-from-webcam UX for the live camera panel (does not wait on the
    // main metrics poll). Local wall-clock + server training_paused / ABSENT.
    const LIVE_AWAY_NOTIFY_MS = 700;
    const LIVE_AWAY_REANNOUNCE_MS = 12_000;
    const LIVE_ABSENCE_PHRASES = __ABSENCE_PHRASES__;
    const liveAway = {
      sinceMs: 0, announced: false, paused: false, sawFace: false, lastAnnounceMs: 0,
    };
    let liveCamClockOriginMs = 0;
    function liveCamTimestampMs() {
      if (!liveCamClockOriginMs) liveCamClockOriginMs = Date.now();
      return Math.max(1, Date.now() - liveCamClockOriginMs);
    }
    function setLiveAwayOverlay(on, detail) {
      const overlayEl = document.getElementById('cam-pause-overlay');
      const sub = document.getElementById('cam-pause-sub');
      if (camFrame) camFrame.classList.toggle('paused', !!on);
      if (overlayEl) overlayEl.classList.toggle('show', !!on);
      if (sub && detail) sub.textContent = detail;
      liveAway.paused = !!on;
    }
    function resetLiveAway(full) {
      liveAway.sinceMs = 0;
      liveAway.announced = false;
      setLiveAwayOverlay(false);
      if (full) {
        liveAway.sawFace = false;
        liveAway.lastAnnounceMs = 0;
        liveCamClockOriginMs = 0;
      }
    }
    function notifyLiveAway(p, facial, evalData) {
      if (usingSilhouette || usingPattern) return;
      if ((facial && facial.face_count > 0) || (p && p.face_count > 0)) {
        liveAway.sawFace = true;
      }
      // Wait until the learner has been seen once so camera warm-up does not false-pause.
      if (!liveAway.sawFace) return;
      const noFace = !!(facial && facial.face_count === 0) || !!(p && p.face_count === 0);
      const serverPaused = !!(evalData && evalData.training_paused);
      const serverAbsent = !!(p && p.state === 'absent');
      const now = Date.now();
      if (!(noFace || serverPaused || serverAbsent)) {
        if (liveAway.paused) {
          const back = 'Welcome back — lesson resumed.';
          toast(back);
          if (autoSpeak()) speakTheodore(back, voiceLangCode());
          setCamState('live', 'good');
        }
        resetLiveAway(false);
        return;
      }
      if (!liveAway.sinceMs) liveAway.sinceMs = now;
      const goneMs = now - liveAway.sinceMs;
      const shouldPause = serverPaused || serverAbsent || goneMs >= LIVE_AWAY_NOTIFY_MS;
      if (!shouldPause) {
        setCamState('away… ' + (Math.round(goneMs / 100) / 10) + 's', 'warn');
        return;
      }
      const secs = Math.max(1, Math.round(((p && p.absent_for_ms) ? p.absent_for_ms : goneMs) / 1000));
      const detail = (evalData && evalData.pause_reason === 'owner_face_mismatch')
        ? ('Face ID mismatch — ' + ((facial && facial.owner_face_name) || 'enrolled learner')
           + ' is not in frame. Teaching paused.')
        : (serverPaused
          ? 'Lesson paused — no learner in the camera frame.'
          : ('Away from webcam (~' + secs + 's). Please step back into view.'));
      setLiveAwayOverlay(true, detail);
      setCamState(
        (evalData && evalData.pause_reason === 'owner_face_mismatch')
          ? 'PAUSED — Face ID' : 'PAUSED — away',
        'bad'
      );
      const canAnnounce = !liveAway.announced
        || (now - liveAway.lastAnnounceMs) >= LIVE_AWAY_REANNOUNCE_MS;
      if (canAnnounce) {
        liveAway.announced = true;
        liveAway.lastAnnounceMs = now;
        const bucket = (LIVE_ABSENCE_PHRASES && LIVE_ABSENCE_PHRASES.immediate) || [];
        let msg = 'I noticed you stepped away from the webcam. Lesson paused — come back when you are ready.';
        if (bucket.length) {
          msg = bucket[Math.floor(Math.random() * bucket.length)].replace(/\\{n\\}/g, 'you');
        }
        toast('⏸ ' + msg);
        if (autoSpeak()) speakTheodore(msg, voiceLangCode());
      }
    }

    function syncSilhouetteToggleUi() {
      if (!silToggle) return;
      silToggle.classList.toggle('on', silhouetteGuideOn);
      silToggle.setAttribute('aria-pressed', silhouetteGuideOn ? 'true' : 'false');
      if (silToggleLabel) {
        silToggleLabel.textContent = silhouetteGuideOn ? 'Guide on' : 'Guide off';
      }
    }

    function clearSilhouetteOverlay() {
      const { w, h } = syncOverlaySize();
      overlay.getContext('2d').clearRect(0, 0, w, h);
    }

    function refreshSilhouetteGuide() {
      // The person outline is a framing aid for a real camera. Over the test
      // pattern there is nobody to frame, and drawing it there is what made the
      // pattern look like "a black screen with a silhouette".
      if (usingPattern) {
        drawPatternCaption();
        return;
      }
      if (silhouetteGuideOn) drawSilhouetteGuide(lastSilhouetteDetected);
      else clearSilhouetteOverlay();
      drawFaceContoursOnOverlay();
      drawHandContoursOnOverlay();
      // Last: drawSilhouetteGuide clears the overlay, so the gauge has to come
      // after it or it is wiped on the next frame.
      drawTiltGauge();
    }

    function drawPatternCaption() {
      const { w, h } = syncOverlaySize();
      const ctx = overlay.getContext('2d');
      ctx.clearRect(0, 0, w, h);
      const stage = currentPatternStage();
      const titlePx = Math.max(13, Math.round(w * 0.026));
      const subPx = Math.max(11, Math.round(w * 0.018));
      const title = 'Test pattern · ' + stage.name;
      const sub = 'expect: ' + stage.expects;
      const pad = Math.max(10, Math.round(w * 0.012));
      ctx.font = `bold ${titlePx}px Arial, sans-serif`;
      const tw = Math.max(ctx.measureText(title).width, (() => {
        ctx.font = `${subPx}px Arial, sans-serif`;
        return ctx.measureText(sub).width;
      })());
      // Anchored above the resolution chip: the contour/guide toggles own the
      // top corners, so a top-left caption lands underneath them.
      const boxH = titlePx + subPx + 14;
      const top = h - boxH - Math.max(34, Math.round(h * 0.12));
      ctx.fillStyle = 'rgba(8, 12, 20, 0.82)';
      ctx.fillRect(pad - 4, top, tw + 14, boxH);
      ctx.font = `bold ${titlePx}px Arial, sans-serif`;
      ctx.fillStyle = '#93c5fd';
      ctx.fillText(title, pad, top + titlePx + 4);
      ctx.font = `${subPx}px Arial, sans-serif`;
      ctx.fillStyle = '#cbd5e1';
      ctx.fillText(sub, pad, top + titlePx + subPx + 8);
    }

    function syncOverlaySize() {
      const rect = camFrame.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      const cssW = Math.max(2, Math.round(rect.width) || CAM_FALLBACK_W);
      const cssH = Math.max(2, Math.round(rect.height) || Math.round(cssW * 9 / 16));
      const w = Math.round(cssW * dpr);
      const h = Math.round(cssH * dpr);
      if (overlay.width !== w || overlay.height !== h) {
        overlay.width = w;
        overlay.height = h;
      }
      return { w, h, cssW, cssH };
    }

    function personPath(ctx, w, h) {
      const cx = w * 0.5;
      const bodyW = w * 0.34;
      const bodyH = h * 0.78;
      const top = h - bodyH;
      const headRy = bodyW * 0.36;
      const headRx = bodyW * 0.30;
      const headCy = top + headRy * 1.05;
      ctx.beginPath();
      ctx.ellipse(cx, headCy, headRx, headRy, 0, 0, Math.PI * 2);
      ctx.moveTo(cx - bodyW * 0.48, headCy + headRy * 1.15);
      ctx.lineTo(cx - bodyW * 0.32, headCy + headRy * 0.95);
      ctx.lineTo(cx + bodyW * 0.32, headCy + headRy * 0.95);
      ctx.lineTo(cx + bodyW * 0.48, headCy + headRy * 1.15);
      ctx.lineTo(cx + bodyW * 0.42, h);
      ctx.lineTo(cx - bodyW * 0.42, h);
      ctx.closePath();
    }

    function drawSilhouetteGuide(detected) {
      // Optional framing reference only — behavior scan uses the FULL camera frame.
      // Users do not need to fit inside the outline; it just hints "stay visible".
      const { w, h } = syncOverlaySize();
      const ctx = overlay.getContext('2d');
      ctx.clearRect(0, 0, w, h);
      if (!silhouetteGuideOn) return;
      // Light outer wash (not a hard "must fit here" cutout).
      ctx.fillStyle = 'rgba(8, 12, 20, 0.22)';
      ctx.fillRect(0, 0, w, h);
      ctx.save();
      personPath(ctx, w, h);
      ctx.clip();
      ctx.clearRect(0, 0, w, h);
      ctx.restore();
      personPath(ctx, w, h);
      ctx.lineWidth = Math.max(2.5, w * 0.005);
      ctx.setLineDash([Math.max(8, w * 0.018), Math.max(6, w * 0.012)]);
      ctx.strokeStyle = detected ? '#3ddc84' : 'rgba(251, 191, 36, 0.85)';
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = detected ? 'rgba(61, 220, 132, 0.10)' : 'rgba(251, 191, 36, 0.08)';
      personPath(ctx, w, h);
      ctx.fill();
      const fontPx = Math.max(12, Math.round(w * 0.024));
      const line2Px = Math.max(11, Math.round(w * 0.018));
      const label = detected
        ? 'in frame · full camera scanned for behavior'
        : 'framing guide (optional) — stay somewhere in the camera';
      const sub = 'you do not need to match this outline';
      const pad = Math.max(10, Math.round(w * 0.012));
      ctx.font = `bold ${fontPx}px Arial, sans-serif`;
      const tw = Math.max(ctx.measureText(label).width, (() => {
        ctx.font = `${line2Px}px Arial, sans-serif`;
        return ctx.measureText(sub).width;
      })());
      const boxH = fontPx + line2Px + 14;
      ctx.fillStyle = 'rgba(8, 12, 20, 0.82)';
      ctx.fillRect(pad - 4, pad - 4, tw + 14, boxH);
      ctx.font = `bold ${fontPx}px Arial, sans-serif`;
      ctx.fillStyle = detected ? '#86efac' : '#fde68a';
      ctx.fillText(label, pad, pad + fontPx);
      ctx.font = `${line2Px}px Arial, sans-serif`;
      ctx.fillStyle = '#cbd5e1';
      ctx.fillText(sub, pad, pad + fontPx + line2Px + 4);
    }

    function paintSilhouettePattern() {
      const w = patternCanvas.width = CAM_FALLBACK_W;
      const h = patternCanvas.height = CAM_FALLBACK_H;
      const ctx = patternCanvas.getContext('2d');
      ctx.fillStyle = '#d8dee9';
      ctx.fillRect(0, 0, w, h);
      const cx = w * 0.5 + Math.sin(patternPhase / 8) * 6;
      const bodyW = w * 0.70;
      const bodyH = h * 0.95;
      const top = h - bodyH;
      ctx.fillStyle = '#10141c';
      ctx.beginPath();
      ctx.ellipse(cx, top + bodyW * 0.14, bodyW * 0.14, bodyW * 0.16, 0, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillRect(cx - bodyW * 0.30, top + bodyW * 0.24, bodyW * 0.60, bodyH);
      patternCanvas.style.display = 'block';
      camVideo.style.visibility = 'hidden';
    }

    function currentPatternStage() {
      const i = Math.floor(patternPhase / PATTERN_STAGE_FRAMES) % PATTERN_STAGES.length;
      return PATTERN_STAGES[i];
    }

    // Gaussian blur of a square wave, in closed form: attenuate each odd
    // harmonic by exp(-2*pi^2*sigma^2*f^2). Doing it analytically rather than via
    // ctx.filter keeps sigma expressed in GRID pixels, which is the scale the
    // Sobel gate actually measures, and behaves identically in every browser.
    function patternHarmonics(sigmaGrid) {
      const out = [];
      for (let k = 1; k <= 9; k += 2) {
        const f = k / PATTERN_PERIOD_GRID;
        const atten = Math.exp(-2 * Math.PI * Math.PI * sigmaGrid * sigmaGrid * f * f);
        out.push({ k, amp: (2 / (k * Math.PI)) * atten });
      }
      return out;
    }

    function paintTestPattern() {
      const w = patternCanvas.width = CAM_FALLBACK_W;
      const h = patternCanvas.height = CAM_FALLBACK_H;
      const ctx = patternCanvas.getContext('2d');
      const stage = currentPatternStage();
      // Exact 20x box downsample to the 64x36 grid, so what is displayed is
      // precisely what gets scored.
      const periodPx = (w / GRID_W) * PATTERN_PERIOD_GRID;
      const shift = (patternPhase % PATTERN_PERIOD_GRID) / PATTERN_PERIOD_GRID;
      const hard = stage.sigma < 0.05;
      const harmonics = hard ? null : patternHarmonics(stage.sigma);
      for (let x = 0; x < w; x++) {
        const u = ((x / periodPx) + shift) % 1;
        let profile;
        if (hard) {
          profile = u < 0.5 ? 1 : 0;
        } else {
          profile = 0.5;
          for (const harm of harmonics) profile += harm.amp * Math.sin(2 * Math.PI * harm.k * u);
          profile = Math.max(0, Math.min(1, profile));
        }
        const v = Math.round(stage.dark + (stage.light - stage.dark) * profile);
        ctx.fillStyle = `rgb(${v}, ${v}, ${v})`;
        ctx.fillRect(x, 0, 1, h);
      }
      patternCanvas.style.display = 'block';
      camVideo.style.visibility = 'hidden';
    }

    function luminanceGrid() {
      grab.width = GRID_W;
      grab.height = GRID_H;
      const ctx = grab.getContext('2d', { willReadFrequently: true });
      if (usingSilhouette) {
        paintSilhouettePattern();
        ctx.drawImage(patternCanvas, 0, 0, GRID_W, GRID_H);
      } else if (usingPattern) {
        // Sample the same canvas the user is looking at; the old code drew the
        // bars straight into the offscreen grid and left a hidden canvas over a
        // stopped <video>, so the preview was just black.
        paintTestPattern();
        ctx.drawImage(patternCanvas, 0, 0, GRID_W, GRID_H);
      } else {
        patternCanvas.style.display = 'none';
        camVideo.style.visibility = 'visible';
        if (!camVideo.videoWidth) return null;
        ctx.drawImage(camVideo, 0, 0, GRID_W, GRID_H);
      }
      const data = ctx.getImageData(0, 0, GRID_W, GRID_H).data;
      const rows = [];
      for (let y = 0; y < GRID_H; y++) {
        const row = [];
        for (let x = 0; x < GRID_W; x++) {
          const i = (y * GRID_W + x) * 4;
          row.push((0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2]) / 255);
        }
        rows.push(row);
      }
      return rows;
    }

    function estimateForeground(grid) {
      let dark = 0, n = 0;
      for (const row of grid) for (const v of row) { n += 1; if (v < 0.35) dark += 1; }
      return n ? dark / n : 0;
    }

    function stopAudioMeter() {
      if (audioPollTimer) { clearInterval(audioPollTimer); audioPollTimer = null; }
      try { if (audioSource) audioSource.disconnect(); } catch (_) {}
      try { if (audioAnalyser) audioAnalyser.disconnect(); } catch (_) {}
      try { if (rawMicSource) rawMicSource.disconnect(); } catch (_) {}
      try { if (rawMicStream) rawMicStream.getTracks().forEach((t) => t.stop()); } catch (_) {}
      try { if (audioCtx && audioCtx.state !== 'closed') audioCtx.close(); } catch (_) {}
      audioCtx = null; audioAnalyser = null; audioSource = null; audioData = null;
      audioRmsHistory = []; lastAudioSample = null; noiseSuppressionOn = null;
      try { if (clickAnalyser) clickAnalyser.disconnect(); } catch(_) {}
      clickAnalyser = null; clickData = null; clickBins = null;
      rawMicStream = null; rawMicSource = null; clickSourceRaw = false;
      resetClickDetectorState();
    }

    function resetClickDetectorState() {
      clickNoiseFloor = 0.003; clickPrevRms = 0; clickEvents = [];
      toneActiveMs = 0; ringtoneLatchUntil = 0; voiceActiveMs = 0; musicActiveMs = 0;
      clickLevelDb = -120; clickFloorDb = -120;
      clickPrevFreq = null; tonePeakBin = -1;
    }

    // The processed WebRTC track (echoCancellation/noiseSuppression/autoGainControl)
    // is what we want for noise-filter scoring, but browser noise suppression is
    // explicitly designed to delete keystrokes and ringtones — the exact events the
    // click detector looks for. Grab a second, unprocessed capture for detection.
    async function openRawMicStream() {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) return null;
      try {
        return await navigator.mediaDevices.getUserMedia({
          audio: {
            echoCancellation: false,
            noiseSuppression: false,
            autoGainControl: false,
            channelCount: 1,
          },
        });
      } catch (_) {
        return null;
      }
    }

    async function startAudioMeter(stream) {
      stopAudioMeter();
      const tracks = stream.getAudioTracks();
      if (!tracks.length) return false;
      const settings = tracks[0].getSettings ? tracks[0].getSettings() : {};
      noiseSuppressionOn = settings.noiseSuppression;
      if (noiseSuppressionOn == null && tracks[0].getConstraints) {
        const c = tracks[0].getConstraints();
        if (c && c.noiseSuppression != null) noiseSuppressionOn = !!c.noiseSuppression;
      }
      try {
        const AC = window.AudioContext || window.webkitAudioContext;
        audioCtx = new AC();
        // Autoplay policy can leave the context suspended; a suspended analyser
        // reports silence forever, which silently disables every audio detector.
        if (audioCtx.state === 'suspended') { try { await audioCtx.resume(); } catch (_) {} }
        audioSource = audioCtx.createMediaStreamSource(stream);
        audioAnalyser = audioCtx.createAnalyser();
        audioAnalyser.fftSize = 2048;
        audioAnalyser.smoothingTimeConstant = 0.8;
        audioSource.connect(audioAnalyser);

        clickAnalyser = audioCtx.createAnalyser();
        clickAnalyser.fftSize = 1024;
        clickAnalyser.smoothingTimeConstant = 0;
        clickAnalyser.minDecibels = -110;
        clickAnalyser.maxDecibels = -10;

        rawMicStream = await openRawMicStream();
        if (rawMicStream) {
          rawMicSource = audioCtx.createMediaStreamSource(rawMicStream);
          rawMicSource.connect(clickAnalyser);
          clickSourceRaw = true;
        } else {
          audioSource.connect(clickAnalyser);
          clickSourceRaw = false;
        }

        const bins = clickAnalyser.frequencyBinCount;
        clickData = { time: new Float32Array(clickAnalyser.fftSize), freq: new Float32Array(bins) };
        const binHz = (audioCtx.sampleRate / 2) / bins;
        const binOf = (hz) => Math.max(0, Math.min(bins - 1, Math.round(hz / binHz)));
        clickBins = {
          count: bins,
          bandLo: binOf(250), bandHi: binOf(9000),
          speechLo: binOf(300), speechHi: binOf(3400),
          hfLo: binOf(2500), hfHi: binOf(9000),
          toneLo: binOf(300), toneHi: binOf(5000),
        };
        resetClickDetectorState();
        audioData = new Float32Array(audioAnalyser.fftSize);
        audioPollTimer = setInterval(pollAudioDetector, AUDIO_POLL_MS);
        return true;
      } catch (_) {
        stopAudioMeter();
        return false;
      }
    }

    function sampleMicAudio() {
      if (!audioAnalyser || !audioData) return null;
      audioAnalyser.getFloatTimeDomainData(audioData);
      let sumSq = 0, clipped = 0;
      for (let i = 0; i < audioData.length; i++) {
        const v = audioData[i];
        sumSq += v * v;
        if (Math.abs(v) >= 0.98) clipped += 1;
      }
      const rms = Math.sqrt(sumSq / audioData.length);
      audioRmsHistory.push(rms);
      if (audioRmsHistory.length > 40) audioRmsHistory.shift();
      const sorted = audioRmsHistory.slice().sort((a, b) => a - b);
      const p20 = sorted[Math.max(0, Math.floor(sorted.length * 0.2))] || rms;
      const p90 = sorted[Math.min(sorted.length - 1, Math.floor(sorted.length * 0.9))] || rms;
      // Map RMS to approximate dBFS-ish noise floor / peaks (relative).
      const toDb = (x) => 20 * Math.log10(Math.max(1e-6, x));
      const noiseDb = Math.max(20, Math.min(85, 70 + toDb(p20)));  // quiet room ~30–45
      const peakDb = Math.max(20, Math.min(90, 70 + toDb(p90)));
      const snrDb = Math.max(0, Math.min(40, peakDb - noiseDb + (p90 > p20 * 2.5 ? 8 : 2)));
      const micLevel = Math.max(0, Math.min(1, (toDb(rms) + 60) / 50));
      const clipRatio = clipped / audioData.length;
      // Noise filter: browser NS on + quiet floor + usable SNR.
      const noiseQ = Math.max(0, Math.min(1, (70 - noiseDb) / 40));
      const snrQ = Math.max(0, Math.min(1, (snrDb - 5) / 25));
      let filter = 0.35 * noiseQ + 0.35 * snrQ + 0.15 * (1 - Math.min(1, clipRatio * 8));
      if (noiseSuppressionOn === true) filter = Math.min(1, filter * 0.65 + 0.40);
      else if (noiseSuppressionOn === false) filter = filter * 0.7;
      else filter = Math.min(1, filter + 0.08);
      lastAudioSample = {
        microphone_input_level_score: Math.round(micLevel * 1000) / 1000,
        audio_noise_level_db: Math.round(noiseDb * 10) / 10,
        audio_snr_db: Math.round(snrDb * 10) / 10,
        mic_clipping_ratio: Math.round(clipRatio * 10000) / 10000,
        noise_filter_effectiveness_score: Math.round(filter * 1000) / 1000,
        noise_suppression: noiseSuppressionOn,
      };
      return lastAudioSample;
    }

    // Runs every AUDIO_POLL_MS so the analyser's ~21ms window tiles the stream
    // continuously. Accumulates rolling evidence; sampleClickDetector() only reads it.
    function pollAudioDetector() {
      if (!clickAnalyser || !clickData || !clickBins) return;
      const now = Date.now();
      clickAnalyser.getFloatTimeDomainData(clickData.time);
      clickAnalyser.getFloatFrequencyData(clickData.freq);

      let sumSq = 0, peak = 0;
      for (let i = 0; i < clickData.time.length; i++) {
        const v = clickData.time[i];
        sumSq += v * v;
        if (Math.abs(v) > peak) peak = Math.abs(v);
      }
      const rms = Math.sqrt(sumSq / clickData.time.length);

      // Background floor: drop quickly toward quiet, rise slowly, so a burst of
      // typing can never raise the floor above the very transients it must detect.
      if (rms < clickNoiseFloor) clickNoiseFloor += (rms - clickNoiseFloor) * 0.25;
      else clickNoiseFloor += (rms - clickNoiseFloor) * 0.002;
      clickNoiseFloor = Math.max(0.0002, Math.min(0.05, clickNoiseFloor));
      clickLevelDb = 20 * Math.log10(Math.max(1e-7, rms));
      clickFloorDb = 20 * Math.log10(Math.max(1e-7, clickNoiseFloor));

      const b = clickBins;
      let bandPower = 0, bandCount = 0;
      let speechPower = 0, speechCount = 0;
      let hfPower = 0, hfCount = 0;
      let peakDb = -Infinity, peakBin = -1, bandPeakDb = -Infinity;
      const toneDbs = [];
      for (let i = b.bandLo; i <= b.bandHi; i++) {
        const db = clickData.freq[i];
        const pw = Math.pow(10, db / 10);
        bandPower += pw; bandCount += 1;
        if (db > bandPeakDb) bandPeakDb = db;
        if (i >= b.speechLo && i <= b.speechHi) { speechPower += pw; speechCount += 1; }
        if (i >= b.hfLo && i <= b.hfHi) { hfPower += pw; hfCount += 1; }
        if (i >= b.toneLo && i <= b.toneHi) {
          toneDbs.push(db);
          if (db > peakDb) { peakDb = db; peakBin = i; }
        }
      }
      const speechRatio = bandPower > 0 ? (speechPower / bandPower) : 0;
      const hfRatio = bandPower > 0 ? (hfPower / bandPower) : 0;

      // Spectral flux is the tone-vs-voice discriminator: a ring holds the same
      // spectrum frame to frame while speech is never still. Only bins within
      // 30 dB of the peak count — bins down at the noise floor swing several dB
      // on their own and would drown the real signal.
      let flux = 0;
      if (clickPrevFreq) {
        const fluxGate = bandPeakDb - 30;
        let acc = 0, n = 0;
        for (let i = b.bandLo; i <= b.bandHi; i++) {
          const cur = clickData.freq[i], prv = clickPrevFreq[i];
          if (cur < fluxGate && prv < fluxGate) continue;
          acc += Math.abs(cur - prv); n += 1;
        }
        flux = n ? acc / n : 0;
      }
      if (!clickPrevFreq) clickPrevFreq = new Float32Array(clickData.freq.length);
      clickPrevFreq.set(clickData.freq);

      // Peak prominence over the band median separates a narrow-band ring
      // (>14 dB) from broadband speech or room noise.
      let prominence = 0;
      if (toneDbs.length) {
        const sortedDbs = toneDbs.slice().sort((x, y) => x - y);
        const medianDb = sortedDbs[Math.floor(sortedDbs.length / 2)];
        if (Number.isFinite(peakDb) && Number.isFinite(medianDb)) prominence = peakDb - medianDb;
      }

      const elevated = rms > clickNoiseFloor * 2.2;

      // Keystrokes are sharp broadband attacks with strong high-frequency energy,
      // which is what separates them from a voice onset.
      const prev = clickPrevRms;
      clickPrevRms = rms;
      const sharpAttack = rms > clickNoiseFloor * 3.0 && rms > prev * 1.7;
      if (sharpAttack && peak < 0.99 && hfRatio > 0.18) {
        const last = clickEvents.length ? clickEvents[clickEvents.length - 1] : 0;
        if (now - last >= 60) clickEvents.push(now);
      }
      const cutoff4s = now - 4000;
      while (clickEvents.length && clickEvents[0] < cutoff4s) clickEvents.shift();

      // Ringtone: a prominent peak that stays put. A melody steps between notes,
      // so stability is only required within a note, which is long enough at 25ms
      // polling to clear the hold; a moving voice never accumulates.
      const steadyPeak = tonePeakBin >= 0 && Math.abs(peakBin - tonePeakBin) <= 2;
      tonePeakBin = peakBin;
      const tonal = elevated && prominence > 14 && peakBin >= 0 && steadyPeak && flux < 2.5;
      toneActiveMs = Math.max(0, Math.min(1500,
        toneActiveMs + (tonal ? AUDIO_POLL_MS : -AUDIO_POLL_MS * 0.8)));
      // Ring cadences pause for seconds between bursts; latch so the verdict
      // does not flicker off in the gap.
      if (toneActiveMs >= 350) ringtoneLatchUntil = now + 6000;

      const voiceLike = rms > clickNoiseFloor * 2.0
        && speechRatio > 0.45 && hfRatio < 0.45 && !tonal
        && (flux > 1.2 || prominence < 14);
      voiceActiveMs = Math.max(0, Math.min(4000,
        voiceActiveMs + (voiceLike ? AUDIO_POLL_MS : -AUDIO_POLL_MS * 0.5)));

      // Outside music: broadband / moving spectrum — opposite of a ringtone.
      // Sustained elevation without keystroke attacks; pure speech stays on
      // the phone-call path. Music-with-vocals still scores as ambient music.
      const sharpThisTick = sharpAttack && peak < 0.99 && hfRatio > 0.18;
      const musical = elevated && !sharpThisTick && !tonal
        && (flux >= 2.0 || !steadyPeak) && prominence < 14.0
        && !(speechRatio > 0.62 && flux < 2.0);
      musicActiveMs = Math.max(0, Math.min(5000,
        musicActiveMs + (musical ? AUDIO_POLL_MS : -AUDIO_POLL_MS * 0.6)));
    }

    // The verdicts latch for seconds while the 300ms loop keeps firing, so the
    // toast needs its own cooldown or it repeats ~20 times per event.
    const audioToastAt = {};
    function maybeToastAudio(key, message) {
      const now = Date.now();
      if (audioToastAt[key] && now - audioToastAt[key] < 8000) return;
      audioToastAt[key] = now;
      toast(message);
    }

    function sampleClickDetector() {
      if (!clickAnalyser || !clickData) {
        return {
          keyboardScore: 0, ringtone: false, phonecall: false, clickRate: 0,
          levelDb: -120, externalMusicScore: 0,
        };
      }
      const now = Date.now();
      const cutoff4s = now - 4000;
      while (clickEvents.length && clickEvents[0] < cutoff4s) clickEvents.shift();
      const clickRate = clickEvents.length / 4;
      return {
        keyboardScore: Math.min(1, clickRate / 4),
        clickRate,
        ringtone: now < ringtoneLatchUntil,
        phonecall: voiceActiveMs >= 1800,
        // musicActiveMs only accumulates when the musical heuristic is true.
        externalMusicScore: clamp01(musicActiveMs / 2000),
        musicActiveMs,
        levelDb: clickLevelDb,
        floorDb: clickFloorDb,
        rawMic: clickSourceRaw,
      };
    }

    function detectPhoneFromGrid(grid, gazeDown) {
      // iPhones are often dark (case/screen off) OR bright (lit screen). Old logic
      // only looked for bright blobs, so looking down at a phone never fired.
      const h = grid.length, w = grid[0].length;
      const y0 = Math.floor(h * 0.42);
      const x0 = Math.floor(w * 0.15);
      const x1 = Math.floor(w * 0.85);
      let bright = 0, dark = 0, n = 0, sum = 0, sum2 = 0;
      for (let y = y0; y < h; y++) {
        for (let x = x0; x < x1; x++) {
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
      // Looking hard down at a phone often has no bright blob (dark case / screen off).
      const lookingHardDown = gazeDown >= 0.40;
      const below = gazeDown >= 0.22 && (litScreen || darkDevice || lookingHardDown);

      const yEarEnd = Math.floor(h * 0.65);
      const xLeftEdge = Math.floor(w * 0.22);
      const xRightStart = Math.floor(w * 0.78);
      let darkLeft = 0, totalLeft = 0, darkRight = 0, totalRight = 0;
      for (let y = 0; y < yEarEnd; y++) {
        for (let x = 0; x < xLeftEdge; x++) {
          totalLeft++;
          if (grid[y][x] < 0.18) darkLeft++;
        }
        for (let x = xRightStart; x < w; x++) {
          totalRight++;
          if (grid[y][x] < 0.18) darkRight++;
        }
      }
      const darkLeftRatio = totalLeft ? darkLeft / totalLeft : 0;
      const darkRightRatio = totalRight ? darkRight / totalRight : 0;
      const ear = (darkLeftRatio > 0.40 || darkRightRatio > 0.40) && gazeDown < 0.30;

      return {
        below, ear, litScreen, darkDevice,
        score: Math.max(brightRatio, darkRatio, lookingHardDown ? gazeDown : 0),
      };
    }

    // Detect hand(s) resting on the face — chin-rest, cheek-prop, head-in-hands.
    // Returns a 0..1 score; 0.5+ indicates a sustained tired/bored posture.
    // Algorithm uses three complementary luminance-grid signals combined into one score.
    function detectHandsOnFace(grid, gazeDown, facePresent) {
      if (!grid || grid.length < 8 || !facePresent) return 0;
      const h = grid.length, w = grid[0].length;

      // 1. Chin-rest: dark mass in lower-central face area where a hand would sit.
      //    When the chin rests on a hand, the lower face/chin region shows extra dark
      //    occlusion below the lips (dark hand vs lighter background).
      let chinDark = 0, chinN = 0;
      const cY0 = Math.floor(h * 0.62), cX0 = Math.floor(w * 0.28), cX1 = Math.floor(w * 0.72);
      for (let y = cY0; y < Math.min(h, Math.floor(h * 0.86)); y++) {
        for (let x = cX0; x < cX1; x++) { chinN++; if (grid[y][x] < 0.27) chinDark++; }
      }
      const chinDarkRatio = chinN ? chinDark / chinN : 0;
      const chinScore = Math.max(0, Math.min(1, (chinDarkRatio - 0.07) / 0.22));

      // 2. Cheek asymmetry: one side much darker than the other — a hand on one cheek
      //    creates a strong left/right luminance imbalance in the middle face region.
      let leftSum = 0, leftN = 0, rightSum = 0, rightN = 0;
      const mY0 = Math.floor(h * 0.30), mY1 = Math.floor(h * 0.65);
      for (let y = mY0; y < mY1; y++) {
        for (let x = Math.floor(w * 0.08); x < Math.floor(w * 0.33); x++) { leftSum += grid[y][x]; leftN++; }
        for (let x = Math.floor(w * 0.67); x < Math.floor(w * 0.92); x++) { rightSum += grid[y][x]; rightN++; }
      }
      const leftMean = leftN ? leftSum / leftN : 0.5;
      const rightMean = rightN ? rightSum / rightN : 0.5;
      const asymScore = Math.max(0, Math.min(1, (Math.abs(leftMean - rightMean) - 0.04) / 0.18));

      // 3. Reduced face variance: hands covering features flatten the typical face
      //    contrast (eyes/nose/mouth structure disappears under a palm).
      const faceVals = [];
      for (let y = Math.floor(h * 0.10); y < Math.floor(h * 0.75); y++) {
        for (let x = Math.floor(w * 0.22); x < Math.floor(w * 0.78); x++) faceVals.push(grid[y][x]);
      }
      const faceMean = faceVals.reduce((a, b) => a + b, 0) / Math.max(1, faceVals.length);
      const faceVar = faceVals.reduce((a, v) => a + (v - faceMean) ** 2, 0) / Math.max(1, faceVals.length);
      const faceStd = Math.sqrt(faceVar);
      // Typical face: std 0.07–0.18. Covered face drops to <0.05.
      const varScore = Math.max(0, Math.min(1, (0.065 - faceStd) / 0.038));

      // Combine — chin-rest dominates, cheek asymmetry and variance suppression support it.
      // A mild gaze-down modifier boosts when the head is also drooping (tired posture).
      const gazeBoost = gazeDown > 0.20 ? 1.0 + Math.min(0.35, (gazeDown - 0.20) * 1.2) : 1.0;
      const combined = (chinScore * 0.48 + asymScore * 0.28 + varScore * 0.24) * gazeBoost;
      return Math.max(0, Math.min(1, combined));
    }

    // Seconds a posture must hold before it counts, read from the live knobs so
    // the HUD countdown always matches what the server is actually enforcing.
    function holdSeconds(knob) {
      const ms = Number(visionKnobs && visionKnobs[knob]);
      return Math.round((Number.isFinite(ms) ? ms : 5000) / 1000);
    }

    function updateIntegrityHud(signals) {
      const {
        gazeDown, gazeDownMs, eyesClosed, eyesClosedMs,
        handsOnFaceScore = 0, handsOnFaceMs = 0, handsOnFaceConfirmed = false,
        handCount = 0, phoneForMs = 0,
        keyboardScore, phoneBelow, phoneEar, ringtone, phonecall, suspected,
        clickRate = 0, micLevelDb = null, micRaw = false,
        musicScore = 0, musicDetected = false, musicForMs = 0,
        heldScore = 0, heldDetected = false, heldForMs = 0,
        excitement = 0, interest = 0, dozing = 0,
      } = signals;

      const gazeCard = document.getElementById('integrity-gaze');
      const gazeVal = document.getElementById('integrity-gaze-val');
      if (gazeCard && gazeVal) {
        const gazeLevel = gazeDown >= 0.48 ? 'alert-high' : (gazeDown >= 0.30 ? 'alert-med' : 'alert-low');
        gazeCard.className = 'integrity-card ' + gazeLevel;
        const sec = gazeDownMs > 0 ? (gazeDownMs / 1000).toFixed(1) : 0;
        gazeVal.textContent = Math.round(gazeDown * 100) + '%' + (gazeDownMs > 0 ? ' · ' + sec + 's' : '');
      }

      const closedCard = document.getElementById('integrity-eyes');
      const closedVal = document.getElementById('integrity-eyes-val');
      if (closedCard && closedVal) {
        const closedLevel = eyesClosed ? 'alert-high' : 'alert-low';
        closedCard.className = 'integrity-card ' + closedLevel;
        const sec = eyesClosedMs > 0 ? (eyesClosedMs / 1000).toFixed(1) + 's' : '';
        closedVal.textContent = eyesClosed ? ('closed' + (sec ? ' · ' + sec : '')) : 'open';
      }

      // A dead mic and a silent room look identical in a bare percentage, so the
      // audio cards fall back to the live input level to stay diagnosable.
      const micDead = micLevelDb == null || micLevelDb <= -119;
      const micHint = micDead ? 'mic off' : (Math.round(micLevelDb) + ' dB' + (micRaw ? '' : ' · filtered'));

      const kbCard = document.getElementById('integrity-keyboard');
      const kbVal = document.getElementById('integrity-keyboard-val');
      if (kbCard && kbVal) {
        kbCard.className = 'integrity-card ' + (keyboardScore >= 0.5 ? 'alert-high' : (keyboardScore > 0 ? 'alert-med' : 'alert-low'));
        kbVal.textContent = keyboardScore > 0
          ? (Math.round(keyboardScore * 100) + '% · ' + clickRate.toFixed(1) + '/s')
          : micHint;
      }

      // Both cards below show "building" while the streak is still short of the
      // hold window, so a brief glance or gesture reads as pending, not a hit.
      const devCard = document.getElementById('integrity-device');
      const devVal = document.getElementById('integrity-device-val');
      if (devCard && devVal) {
        const phoneHold = holdSeconds('phone_visible_min_hold_ms');
        // Server hold already gates ear+below+call into phone_visible; raw ear
        // alone must not paint alert-high before the streak completes.
        const confirmed = phoneBelow;
        devCard.className = 'integrity-card ' + (confirmed ? 'alert-high' : (phoneForMs > 0 ? 'alert-med' : 'alert-low'));
        devVal.textContent = confirmed && phoneEar ? 'near ear'
          : (confirmed ? ('below face · ' + (phoneForMs / 1000).toFixed(0) + 's')
            : (phoneForMs > 0 ? ((phoneForMs / 1000).toFixed(1) + 's / ' + phoneHold + 's') : 'none'));
      }

      const handsCard = document.getElementById('integrity-hands');
      const handsVal = document.getElementById('integrity-hands-val');
      if (handsCard && handsVal) {
        const handsHold = holdSeconds('hands_on_face_min_hold_ms');
        const building = handsOnFaceMs > 0 && !handsOnFaceConfirmed;
        handsCard.className = 'integrity-card '
          + (handsOnFaceConfirmed ? 'alert-high' : (building ? 'alert-med' : 'alert-low'));
        handsVal.textContent = handsOnFaceConfirmed
          ? (Math.round(handsOnFaceScore * 100) + '% · ' + (handsOnFaceMs / 1000).toFixed(0) + 's')
          : (building ? ((handsOnFaceMs / 1000).toFixed(1) + 's / ' + handsHold + 's')
            : (handCount > 0 ? (handCount + ' hand' + (handCount > 1 ? 's' : '') + ' in frame') : 'none'));
      }

      const callCard = document.getElementById('integrity-call');
      const callVal = document.getElementById('integrity-call-val');
      if (callCard && callVal) {
        callCard.className = 'integrity-card ' + (phonecall ? 'alert-high' : (ringtone ? 'alert-med' : 'alert-low'));
        callVal.textContent = phonecall ? 'call active' : (ringtone ? 'ringtone ♪' : micHint);
      }

      // Record-only: outside music and held objects — no spoken coaching / pause.
      const musicCard = document.getElementById('integrity-music');
      const musicVal = document.getElementById('integrity-music-val');
      if (musicCard && musicVal) {
        musicCard.className = 'integrity-card ' + (musicDetected ? 'alert-med' : (musicScore > 0.2 ? 'alert-med' : 'alert-low'));
        musicVal.textContent = musicDetected
          ? ('outside music · ' + (musicForMs / 1000).toFixed(0) + 's')
          : (musicScore > 0.05
            ? (Math.round(musicScore * 100) + '%' + (musicForMs > 0 ? ' · ' + (musicForMs / 1000).toFixed(1) + 's' : ''))
            : micHint);
      }
      const heldCard = document.getElementById('integrity-held');
      const heldVal = document.getElementById('integrity-held-val');
      if (heldCard && heldVal) {
        heldCard.className = 'integrity-card ' + (heldDetected ? 'alert-med' : (heldScore > 0.25 ? 'alert-med' : 'alert-low'));
        heldVal.textContent = heldDetected
          ? ('object in hand · ' + (heldForMs / 1000).toFixed(0) + 's')
          : (heldScore > 0.05 ? (Math.round(heldScore * 100) + '%') : 'none');
      }
      const trajCard = document.getElementById('integrity-traj');
      const trajVal = document.getElementById('integrity-traj-val');
      if (trajCard && trajVal) {
        const hot = dozing >= 0.48 ? 'alert-med' : ((excitement >= 0.42 || interest >= 0.45) ? 'alert-low' : 'alert-low');
        trajCard.className = 'integrity-card ' + hot;
        trajVal.textContent = 'ex ' + Math.round((excitement || 0) * 100)
          + '% · in ' + Math.round((interest || 0) * 100)
          + '% · doz ' + Math.round((dozing || 0) * 100) + '%';
      }

      const statusEl = document.getElementById('integrity-status');
      if (statusEl) {
        if (suspected) {
          statusEl.className = 'integrity-status alert';
          statusEl.textContent = '⚠ Integrity alert — phone / eyes away';
        } else if (eyesClosed && eyesClosedMs >= 1500) {
          statusEl.className = 'integrity-status alert';
          statusEl.textContent = '😴 Eyes closed — please look at the lesson';
        } else if (phoneBelow && gazeDownMs >= 2000) {
          statusEl.className = 'integrity-status alert';
          statusEl.textContent = '📱 Looking down at a phone — please return to the webcam';
        } else if (gazeDown >= 0.42 && gazeDownMs >= 1500) {
          statusEl.className = 'integrity-status warn';
          statusEl.textContent = '👀 Distracted / looking away — refocus on the camera';
        } else if (phonecall) {
          statusEl.className = 'integrity-status warn';
          statusEl.textContent = '📞 Phone call – lesson paused';
        } else {
          statusEl.className = 'integrity-status';
          statusEl.textContent = 'Monitoring yawn, distraction, attention, gaze, and phone';
        }
      }
    }

    function updateObservatoryHud(p) {
      const adv = (p && p.advanced_behavior) || {};
      const setBar = (id, score) => {
        const el = document.getElementById(id);
        if (!el) return;
        const v = Math.max(0, Math.min(1, Number(score) || 0));
        el.style.width = Math.round(v * 100) + '%';
        el.parentElement && el.parentElement.setAttribute('title', Math.round(v * 100) + '%');
      };
      setBar('obs-eng', adv.engagement_index);
      setBar('obs-flow', adv.flow_score);
      setBar('obs-conf', 0);  // confused detection removed — keep slot for layout stability
      setBar('obs-bore', adv.boredom_score);
      setBar('obs-fat', adv.fatigue_score);
      setBar('obs-cur', adv.curiosity_score);
      setBar('obs-fid', adv.fidget_score);
      setBar('obs-multi', adv.multitask_score);
      setBar('obs-exc', adv.excitement_score);
      setBar('obs-int', adv.interest_score);
      setBar('obs-doz', adv.dozing_score);
      const labelEl = document.getElementById('obs-label');
      if (labelEl) labelEl.textContent = (adv.observatory_label || p.behavior_label || '—').replace(/_/g, ' ');
      const cogEl = document.getElementById('obs-cognitive');
      if (cogEl) cogEl.textContent = (adv.cognitive_label || '—').replace(/_/g, ' ');
      const hintEl = document.getElementById('obs-hint');
      if (hintEl) hintEl.textContent = adv.timeline_hint || 'Start camera for live cognitive fusion';
      const poseEl = document.getElementById('obs-pose');
      if (poseEl) {
        const pitch = adv.head_pose_pitch, yaw = adv.head_pose_yaw, roll = adv.head_pose_roll;
        poseEl.textContent = (pitch == null && yaw == null)
          ? 'pose n/a'
          : ('P ' + Number(pitch || 0).toFixed(0) + '° · Y ' + Number(yaw || 0).toFixed(0) + '° · R ' + Number(roll || 0).toFixed(0) + '°');
      }
      const needle = document.getElementById('obs-pose-needle');
      if (needle) {
        const yaw = Number(adv.head_pose_yaw || 0);
        const pitch = Number(adv.head_pose_pitch || 0);
        needle.style.transform = 'translate(-50%,-50%) rotate(' + yaw + 'deg) translateY(' + Math.max(-18, Math.min(18, pitch * 0.35)) + 'px)';
      }
      const confEl = document.getElementById('obs-confidence');
      if (confEl) confEl.textContent = adv.confidence != null ? Math.round(adv.confidence * 100) + '% conf' : '';
      const events = Array.isArray(adv.events) ? adv.events : [];
      events.forEach((ev) => {
        observatoryEvents.push(ev);
        if (observatoryEvents.length > 24) observatoryEvents.shift();
      });
      const log = document.getElementById('obs-events');
      if (log) {
        const rows = observatoryEvents.slice().reverse().slice(0, 10).map((ev) => {
          const t = ev.timestamp_ms ? new Date(ev.timestamp_ms).toLocaleTimeString() : '';
          return '<div class="obs-ev ' + esc(ev.level || '') + '"><span class="t">' + esc(t) + '</span> '
            + '<strong>' + esc(ev.code || '') + '</strong> ' + esc(ev.message || '') + '</div>';
        });
        log.innerHTML = rows.length ? rows.join('') : '<div class="obs-ev">No behavior events yet.</div>';
      }
      if ((adv.fatigue_score || 0) >= 0.62) {
        maybeAnnounceIntegrity('fatigue', 'You seem tired. Take a short stretch if you need to, then refocus.');
      } else if ((adv.engagement_index || 0) >= 0.78) {
        maybeAnnounceIntegrity('engage', 'Great focus — keep that energy going.');
      }
    }

    function updateAudioHud(p, audio) {
      const micEl = document.getElementById('audio-mic');
      const noiseEl = document.getElementById('audio-noise');
      if (!micEl || !noiseEl) return;
      const mic = p && p.microphone_quality_score != null ? p.microphone_quality_score
        : (audio && audio.microphone_input_level_score);
      const filt = p && p.noise_filter_effectiveness_score != null ? p.noise_filter_effectiveness_score
        : (audio && audio.noise_filter_effectiveness_score);
      micEl.textContent = mic == null ? 'n/a' : (Math.round(mic * 100) + '%');
      noiseEl.textContent = filt == null ? 'n/a' : (Math.round(filt * 100) + '%');
      document.getElementById('audio-mic-sub').textContent =
        audio && audio.audio_snr_db != null
          ? ('SNR ' + audio.audio_snr_db.toFixed(1) + ' dB · noise ' + audio.audio_noise_level_db.toFixed(1) + ' dB')
          : 'speak to raise SNR';
      const ns = audio && audio.noise_suppression;
      document.getElementById('audio-noise-sub').textContent =
        ns === true ? 'browser noise suppression on'
          : (ns === false ? 'noise suppression off' : 'estimated from mic noise floor + SNR');
    }

    // --- Facial contour / landmark mood tracking ---------------------------
    let faceContoursOn = true;
    let faceLandmarker = null;
    let faceLandmarkerPromise = null;
    let faceLandmarkerAttempts = 0;
    let faceLandmarkerRetryAtMs = 0;
    let lastFaceContours = null;  // { pts, connections, mood, secondaryBoxes, ownerStatus }
    let handLandmarker = null;
    let handLandmarkerFailed = false;
    let handLandmarkerPromise = null;
    // Named Face ID (parity with face_owner.py). Detect up to N faces, enroll the
    // first stable person as Face ID, then mesh/score only that person — strangers
    // are secondary (yellow ovals) and do not drive attention/mood/teaching.
    const FACE_OWNER_MAX_FACES = 4;
    const OWNER_ENROLL_HOLD_MS = 1500;
    const OWNER_MATCH_IOU_MIN = 0.22;
    const OWNER_MATCH_FP_MAX = 0.38;
    // Above the IoU-only ceiling (0.45): continuity alone can never pass.
    const OWNER_MATCH_SCORE_MIN = 0.55;
    // Softer gate while holding the first-seen Face ID candidate.
    const OWNER_ENROLL_SCORE_MIN = 0.28;
    // Identity veto: below this fingerprint sub-score it is not the owner.
    const OWNER_MATCH_FP_MIN = 0.25;
    // Template adapts only on a strong identity match.
    const OWNER_ADAPT_FP_MIN = 0.5;
    const OWNER_FP_IDX = [33, 263, 1, 61, 291, 10, 152];
    const FACE_ID_STORAGE_KEY = 'twl.faceid.v1';
    let lastDetectedFaces = null;
    let faceOwnerState = {
      enrolled: false, enrollStartedMs: 0, fingerprint: null, lastBox: null,
      matchScore: 0, displayName: '',
    };

    function quietMediaPipeConsole() {
      if (window.__aoepMpQuiet) return;
      window.__aoepMpQuiet = true;
      const origErr = console.error.bind(console);
      const origWarn = console.warn.bind(console);
      const origLog = console.log.bind(console);
      // MediaPipe WASM writes INFO/WARN via stderr → console.error with stacks.
      const noise = /(?:^|[\\s[])(?:[WI]\\d{4}\\b|vision_wasm|XNNPACK|gl_context|FaceBlendshapes|Graph successfully|OpenGL error checking|TensorFlow Lite|face_landmarker_graph|Created TensorFlow)/i;
      function isNoise(args) {
        try {
          for (let i = 0; i < Math.min(args.length, 3); i++) {
            const s = typeof args[i] === 'string' ? args[i] : String(args[i] || '');
            if (noise.test(s)) return true;
          }
        } catch (_) {}
        return false;
      }
      console.error = function (...args) {
        if (isNoise(args)) { console.debug.apply(console, args); return; }
        origErr.apply(console, args);
      };
      console.warn = function (...args) {
        if (isNoise(args)) { console.debug.apply(console, args); return; }
        origWarn.apply(console, args);
      };
      console.log = function (...args) {
        if (isNoise(args)) { console.debug.apply(console, args); return; }
        origLog.apply(console, args);
      };
    }
    quietMediaPipeConsole();

    function loadFaceIdProfile() {
      try {
        const raw = localStorage.getItem(FACE_ID_STORAGE_KEY);
        if (!raw) return null;
        const data = JSON.parse(raw);
        if (!data || !Array.isArray(data.fingerprint) || data.fingerprint.length < 4) return null;
        return {
          name: String(data.name || '').trim() || 'Learner',
          fingerprint: data.fingerprint.map(Number),
          lastBox: data.lastBox && typeof data.lastBox.x === 'number' ? data.lastBox : null,
        };
      } catch (_) { return null; }
    }

    function saveFaceIdProfile() {
      if (!faceOwnerState.enrolled || !faceOwnerState.fingerprint) return;
      try {
        localStorage.setItem(FACE_ID_STORAGE_KEY, JSON.stringify({
          name: faceOwnerState.displayName || 'Learner',
          fingerprint: faceOwnerState.fingerprint.slice(),
          lastBox: faceOwnerState.lastBox,
          savedAt: Date.now(),
        }));
      } catch (_) {}
    }

    function clearFaceIdProfile() {
      try { localStorage.removeItem(FACE_ID_STORAGE_KEY); } catch (_) {}
      faceOwnerState = {
        enrolled: false, enrollStartedMs: 0, fingerprint: null, lastBox: null,
        matchScore: 0, displayName: '',
      };
      lastDetectedFaces = null;
      updateFaceIdUi('cleared');
    }

    function resetFaceOwner(opts) {
      const keepProfile = !(opts && opts.clearProfile);
      const saved = keepProfile ? loadFaceIdProfile() : null;
      faceOwnerState = {
        enrolled: !!(saved && saved.fingerprint),
        enrollStartedMs: 0,
        fingerprint: saved ? saved.fingerprint.slice() : null,
        lastBox: saved && saved.lastBox ? Object.assign({}, saved.lastBox) : null,
        matchScore: 0,
        displayName: saved ? (saved.name || 'Learner') : '',
      };
      if (!keepProfile) lastDetectedFaces = null;
      updateFaceIdUi();
    }

    function updateFaceIdUi(hint) {
      const nameEl = document.getElementById('face-id-name');
      const statusEl = document.getElementById('face-id-status');
      if (nameEl && document.activeElement !== nameEl) {
        nameEl.value = faceOwnerState.displayName || '';
      }
      if (!statusEl) return;
      statusEl.className = 'face-id-status';
      if (hint === 'cleared') {
        statusEl.textContent = 'Face ID cleared — first person on camera will enroll after ~1.5s, or use Enroll now.';
        statusEl.classList.add('warn');
        return;
      }
      if (!faceOwnerState.enrolled) {
        statusEl.textContent = 'No Face ID yet — sit in view ~1.5s to enroll the first person, or Enroll now.';
        statusEl.classList.add('warn');
        return;
      }
      const who = faceOwnerState.displayName || 'Learner';
      statusEl.textContent = 'Face ID locked: ' + who
        + ' — only this person counts for attention/behavior; others are ignored for teaching.';
      statusEl.classList.add('ok');
    }

    function faceBoxFromPts(pts) {
      if (!pts || !pts.length) return null;
      let minX = 1, maxX = 0, minY = 1, maxY = 0;
      pts.forEach((p) => {
        if (!p) return;
        if (p.x < minX) minX = p.x; if (p.x > maxX) maxX = p.x;
        if (p.y < minY) minY = p.y; if (p.y > maxY) maxY = p.y;
      });
      return { x: minX, y: minY, w: Math.max(0, maxX - minX), h: Math.max(0, maxY - minY) };
    }

    function boxIoU(a, b) {
      if (!a || !b) return 0;
      const x0 = Math.max(a.x, b.x), y0 = Math.max(a.y, b.y);
      const x1 = Math.min(a.x + a.w, b.x + b.w), y1 = Math.min(a.y + a.h, b.y + b.h);
      const inter = Math.max(0, x1 - x0) * Math.max(0, y1 - y0);
      if (inter <= 0) return 0;
      const union = a.w * a.h + b.w * b.h - inter;
      return union > 0 ? inter / union : 0;
    }

    function faceFingerprint(pts) {
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

    function fingerprintDistance(a, b) {
      if (!a || !b || a.length !== b.length) return 1;
      let acc = 0;
      for (let i = 0; i < a.length; i++) acc += (a[i] - b[i]) * (a[i] - b[i]);
      return Math.sqrt(acc / a.length);
    }

    function largestFaceIndex(faces) {
      let bestI = 0, bestA = -1;
      for (let i = 0; i < faces.length; i++) {
        const box = faceBoxFromPts(faces[i]);
        const area = box ? box.w * box.h : 0;
        if (area > bestA) { bestA = area; bestI = i; }
      }
      return bestI;
    }

    function matchScoreForFace(pts, state) {
      const box = faceBoxFromPts(pts);
      const iou = boxIoU(box, state.lastBox);
      const fp = faceFingerprint(pts);
      const fpDist = fingerprintDistance(fp, state.fingerprint);
      const fpPart = Math.max(0, 1 - fpDist / Math.max(OWNER_MATCH_FP_MAX, 1e-6));
      return Math.max(0, Math.min(1, 0.45 * iou + 0.55 * fpPart));
    }

    function matchScoreForFace(pts, state) {
      return matchPartsForFace(pts, state).score;
    }

    function bestFaceIndex(faces, state, minScore) {
      let bestI = -1, bestScore = -1;
      for (let i = 0; i < faces.length; i++) {
        const score = matchScoreForFace(faces[i], state);
        if (score > bestScore) { bestScore = score; bestI = i; }
      }
      if (bestI < 0 || bestScore < minScore) return { index: -1, score: Math.max(0, bestScore) };
      return { index: bestI, score: bestScore };
    }

    function pickOwnerFace(faces, nowMs) {
      const faceCount = faces.length;
      const displayName = faceOwnerState.displayName || '';
      if (!faceCount) {
        return {
          index: -1, owner_enrolled: faceOwnerState.enrolled,
          // Empty frame is absence, not substitution.
          owner_match: null,
          match_score: 0, secondary_count: 0, face_count: 0, display_name: displayName,
        };
      }
      if (!faceOwnerState.enrolled) {
        const hasCandidate = !!(faceOwnerState.fingerprint || faceOwnerState.lastBox);
        if (hasCandidate) {
          const best = bestFaceIndex(faces, faceOwnerState, OWNER_ENROLL_SCORE_MIN);
          if (best.index < 0) {
            const idx = largestFaceIndex(faces);
            faceOwnerState.enrollStartedMs = nowMs;
            faceOwnerState.lastBox = faceBoxFromPts(faces[idx]);
            const fp = faceFingerprint(faces[idx]);
            faceOwnerState.fingerprint = fp ? fp.slice() : null;
            return {
              index: idx, owner_enrolled: false, owner_match: null, match_score: 0,
              secondary_count: Math.max(0, faceCount - 1), face_count: faceCount,
              display_name: displayName,
            };
          }
          const idx = best.index;
          const box = faceBoxFromPts(faces[idx]);
          const fp = faceFingerprint(faces[idx]);
          if (!faceOwnerState.enrollStartedMs) faceOwnerState.enrollStartedMs = nowMs;
          faceOwnerState.lastBox = box;
          if (fp) faceOwnerState.fingerprint = fp.slice();
          if ((nowMs - faceOwnerState.enrollStartedMs) >= OWNER_ENROLL_HOLD_MS && fp && box) {
            faceOwnerState.enrolled = true;
            faceOwnerState.matchScore = 1;
            if (!(faceOwnerState.displayName || '').trim()) {
              const nameEl = document.getElementById('face-id-name');
              faceOwnerState.displayName = ((nameEl && nameEl.value) || '').trim() || 'Learner';
            }
            saveFaceIdProfile();
            updateFaceIdUi();
            return {
              index: idx, owner_enrolled: true, owner_match: true, match_score: 1,
              secondary_count: Math.max(0, faceCount - 1), face_count: faceCount,
              display_name: faceOwnerState.displayName,
            };
          }
          return {
            index: idx, owner_enrolled: false, owner_match: null, match_score: best.score,
            secondary_count: Math.max(0, faceCount - 1), face_count: faceCount,
            display_name: displayName,
          };
        }
        const idx = largestFaceIndex(faces);
        const box = faceBoxFromPts(faces[idx]);
        const fp = faceFingerprint(faces[idx]);
        faceOwnerState.enrollStartedMs = nowMs;
        faceOwnerState.lastBox = box;
        faceOwnerState.fingerprint = fp ? fp.slice() : null;
        return {
          index: idx, owner_enrolled: false, owner_match: null, match_score: 0,
          secondary_count: Math.max(0, faceCount - 1), face_count: faceCount,
          display_name: displayName,
        };
      }
      let bestI = 0, bestScore = -1;
      for (let i = 0; i < faces.length; i++) {
        const score = matchScoreForFace(faces[i], faceOwnerState);
        if (score > bestScore) { bestScore = score; bestI = i; }
      }
      const matched = bestScore >= OWNER_MATCH_SCORE_MIN;
      if (matched) {
        const box = faceBoxFromPts(faces[bestI]);
        if (box) {
          const lb = faceOwnerState.lastBox;
          faceOwnerState.lastBox = lb
            ? { x: 0.7 * lb.x + 0.3 * box.x, y: 0.7 * lb.y + 0.3 * box.y,
                w: 0.7 * lb.w + 0.3 * box.w, h: 0.7 * lb.h + 0.3 * box.h }
            : box;
          const fp = faceFingerprint(faces[bestI]);
          if (fp && faceOwnerState.fingerprint) {
            faceOwnerState.fingerprint = faceOwnerState.fingerprint.map(
              (v, i) => 0.85 * v + 0.15 * fp[i]
            );
          }
        }
        faceOwnerState.matchScore = bestScore;
        return {
          index: bestI, owner_enrolled: true, owner_match: true, match_score: bestScore,
          secondary_count: Math.max(0, faceCount - 1), face_count: faceCount,
          display_name: faceOwnerState.displayName || displayName,
        };
      }
      // Stranger in frame — do not hand metrics to them (index=-1).
      const raw = bestFaceIndex(faces, faceOwnerState, 0);
      faceOwnerState.matchScore = Math.max(0, raw.score);
      return {
        index: -1, owner_enrolled: true, owner_match: false,
        match_score: Math.max(0, raw.score),
        secondary_count: faceCount, face_count: faceCount,
        display_name: faceOwnerState.displayName || displayName,
      };
    }

    function enrollFaceIdNow() {
      const nameEl = document.getElementById('face-id-name');
      const name = ((nameEl && nameEl.value) || '').trim() || 'Learner';
      if (!lastDetectedFaces || !lastDetectedFaces.length) {
        toast('Start the camera and face the lens, then Enroll Face ID.');
        return;
      }
      let idx = -1;
      if (faceOwnerState.fingerprint || faceOwnerState.lastBox) {
        const best = bestFaceIndex(lastDetectedFaces, faceOwnerState, OWNER_ENROLL_SCORE_MIN);
        idx = best.index;
      }
      if (idx < 0) idx = largestFaceIndex(lastDetectedFaces);
      const pts = lastDetectedFaces[idx];
      const box = faceBoxFromPts(pts);
      const fp = faceFingerprint(pts);
      if (!box || !fp) {
        toast('Could not read a face mesh — move closer and try again.');
        return;
      }
      faceOwnerState.enrolled = true;
      faceOwnerState.displayName = name;
      faceOwnerState.fingerprint = fp.slice();
      faceOwnerState.lastBox = box;
      faceOwnerState.matchScore = 1;
      faceOwnerState.enrollStartedMs = Date.now();
      saveFaceIdProfile();
      updateFaceIdUi();
      toast('Face ID enrolled: ' + name + ' — teaching tracks only this person.');
    }

    function secondaryBoxesFromFaces(faces, ownerIdx) {
      const boxes = [];
      for (let i = 0; i < faces.length; i++) {
        if (i === ownerIdx) continue;
        const box = faceBoxFromPts(faces[i]);
        if (box) boxes.push(box);
      }
      return boxes;
    }
    // { hands: [[{x,y}]], connections: [[i,j]], labels: ['Left'|'Right'] } — null when
    // no hand is in frame, which is what keeps hand contours off the overlay.
    let lastHandContours = null;
    let moodHistory = [];
    // Attention and behaviour flicker frame to frame (~3 samples/sec), so — like
    // mood — they are smoothed over a short rolling window instead of shown raw.
    let attnHistory = [];
    let behaviorHistory = [];
    let attnScoreHistory = [];
    let distractScoreHistory = [];
    const BEHAVIOR_SMOOTH_WINDOW = 8;  // ~2.4s at the 300ms sample rate
    let lastLumaFlat = null;
    let motionEma = 0.15;
    const observatoryEvents = [];
    const contourToggle = document.getElementById('cam-contour-toggle');
    const contourToggleLabel = document.getElementById('cam-contour-toggle-label');

    // Which detector is actually producing the numbers on screen. Behavior claims
    // (eyes closed, gaze, mood) are only trustworthy under 'face_mesh'; anything
    // else must be shown as degraded instead of silently guessing.
    const DETECTOR_LABELS = {
      starting: ['detector: loading face mesh…', 'warn'],
      face_mesh: ['detector: face mesh (accurate)', 'good'],
      face_detector: ['detector: face box only (no eye/mood)', 'warn'],
      coarse: ['detector: coarse — eye/mood disabled', 'bad'],
      off: ['detector: off (pattern/silhouette)', 'warn'],
    };
    let detectorSource = 'starting';
    let detectorDetail = '';

    function setDetectorStatus(source, detail) {
      detectorSource = source;
      detectorDetail = detail || '';
      const el = document.getElementById('cam-detector');
      if (!el) return;
      const [text, tone] = DETECTOR_LABELS[source] || DETECTOR_LABELS.coarse;
      el.textContent = text;
      el.className = 'pill ' + tone;
      el.title = detectorDetail
        || 'Face mesh gives real eye/gaze/expression tracking. Without it the lab '
           + 'reports presence only and stops guessing per-feature behavior.';
    }

    // Order matters. An explicit override always wins; self-hosted is only tried
    // when the server confirms the assets exist (otherwise the 404 just stalls
    // loading); the public CDN is the default that works out of the box. Getting
    // this wrong is what made the face mesh — and with it the contours and mood —
    // stop appearing: self-hosted-first 404'd on every session before the CDN.
    function visionAssetSources() {
      const override = (typeof window !== 'undefined' && window.AOEP_VISION_ASSETS) || '';
      const sources = [];
      if (override) {
        sources.push({
          label: 'override',
          esm: override.replace(/\\/$/, '') + '/tasks-vision.mjs',
          wasm: override.replace(/\\/$/, '') + '/wasm',
          model: override.replace(/\\/$/, '') + '/face_landmarker.task',
        });
      }
      if (VISION_LOCAL_ASSETS) {
        sources.push({
          label: 'self-hosted',
          esm: '/vendor/vision/tasks-vision.mjs',
          wasm: '/vendor/vision/wasm',
          model: '/vendor/vision/face_landmarker.task',
        });
      }
      sources.push({
        label: 'cdn',
        esm: 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/+esm',
        wasm: 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/wasm',
        model: 'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task',
      });
      return sources;
    }

    function syncContourToggleUi() {
      if (!contourToggle) return;
      contourToggle.classList.toggle('on', faceContoursOn);
      contourToggle.setAttribute('aria-pressed', faceContoursOn ? 'true' : 'false');
      if (contourToggleLabel) {
        contourToggleLabel.textContent = faceContoursOn ? 'Contours on' : 'Contours off';
      }
    }
    if (contourToggle) {
      contourToggle.addEventListener('click', (ev) => {
        ev.preventDefault();
        faceContoursOn = !faceContoursOn;
        syncContourToggleUi();
        if (!faceContoursOn) { lastFaceContours = null; lastHandContours = null; }
        refreshSilhouetteGuide();
      });
      syncContourToggleUi();
    }

    const FACE_LANDMARKER_MAX_ATTEMPTS = 8;
    const FACE_LANDMARKER_RETRY_MS = 15000;

    async function buildFaceLandmarker(src) {
      quietMediaPipeConsole();
      const vision = await import(/* webpackIgnore: true */ src.esm);
      const fileset = await vision.FilesetResolver.forVisionTasks(src.wasm);
      // GPU fails on some Macs / browsers; fall back to CPU so blink + look-down still work.
      let lastErr = null;
      for (const delegate of ['GPU', 'CPU']) {
        try {
          const lm = await vision.FaceLandmarker.createFromOptions(fileset, {
            baseOptions: { modelAssetPath: src.model, delegate },
            runningMode: 'VIDEO',
            // Multi-face so we can lock onto the enrolled owner instead of faces[0].
            numFaces: FACE_OWNER_MAX_FACES,
            outputFaceBlendshapes: true,
            outputFacialTransformationMatrixes: true,
          });
          lm._CONNECTIONS = [].concat(
            vision.FaceLandmarker.FACE_LANDMARKS_FACE_OVAL || [],
            vision.FaceLandmarker.FACE_LANDMARKS_LIPS || [],
            vision.FaceLandmarker.FACE_LANDMARKS_LEFT_EYE || [],
            vision.FaceLandmarker.FACE_LANDMARKS_RIGHT_EYE || [],
            vision.FaceLandmarker.FACE_LANDMARKS_LEFT_EYEBROW || [],
            vision.FaceLandmarker.FACE_LANDMARKS_RIGHT_EYEBROW || [],
          );
          lm._delegate = delegate;
          lm._assetLabel = src.label;
          return lm;
        } catch (err) {
          lastErr = err;
          console.warn('Face landmarker ' + src.label + '/' + delegate + ' failed', err);
        }
      }
      throw lastErr || new Error('FaceLandmarker init failed');
    }

    async function ensureFaceLandmarker() {
      if (faceLandmarker) return faceLandmarker;
      if (faceLandmarkerPromise) return faceLandmarkerPromise;
      // A transient network/proxy hiccup must not disable face tracking for the
      // whole session, so retry on a backoff instead of failing permanently.
      const now = Date.now();
      if (faceLandmarkerAttempts > 0 && now < faceLandmarkerRetryAtMs) return null;
      if (faceLandmarkerAttempts >= FACE_LANDMARKER_MAX_ATTEMPTS) return null;
      faceLandmarkerAttempts += 1;
      faceLandmarkerPromise = (async () => {
        const errors = [];
        for (const src of visionAssetSources()) {
          try {
            faceLandmarker = await buildFaceLandmarker(src);
            setDetectorStatus('face_mesh',
              'face mesh via ' + src.label + ' (' + faceLandmarker._delegate + ')');
            return faceLandmarker;
          } catch (err) {
            errors.push(src.label + ': ' + (err && err.message ? err.message : err));
          }
        }
        console.warn('Face landmarker unavailable', errors);
        faceLandmarker = null;
        faceLandmarkerPromise = null;
        faceLandmarkerRetryAtMs = Date.now() + FACE_LANDMARKER_RETRY_MS;
        const exhausted = faceLandmarkerAttempts >= FACE_LANDMARKER_MAX_ATTEMPTS;
        setDetectorStatus(('FaceDetector' in window) ? 'face_detector' : 'coarse',
          'face mesh did not load (' + errors.join(' | ') + ').'
          + (exhausted ? ' Giving up; reload after self-hosting assets.'
                       : ' Retrying every 15s.'));
        return null;
      })();
      return faceLandmarkerPromise;
    }

    function blendshapeMap(blendshapes, idx) {
      const out = {};
      if (!blendshapes || !blendshapes.length) return out;
      const entry = blendshapes[(idx == null || idx < 0) ? 0 : idx] || blendshapes[0];
      const cats = (entry && entry.categories) || [];
      cats.forEach((c) => { out[c.categoryName] = c.score; });
      return out;
    }

    async function ensureHandLandmarker() {
      if (handLandmarker) return handLandmarker;
      if (handLandmarkerFailed) return null;
      if (handLandmarkerPromise) return handLandmarkerPromise;
      handLandmarkerPromise = (async () => {
        try {
          const vision = await import('https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/+esm');
          const fileset = await vision.FilesetResolver.forVisionTasks(
            'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/wasm'
          );
          const modelPath =
            'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task';
          let lastErr = null;
          for (const delegate of ['GPU', 'CPU']) {
            try {
              handLandmarker = await vision.HandLandmarker.createFromOptions(fileset, {
                baseOptions: { modelAssetPath: modelPath, delegate },
                runningMode: 'VIDEO',
                numHands: 2,
              });
              handLandmarker._CONNECTIONS = (vision.HandLandmarker.HAND_CONNECTIONS || [])
                .map((c) => [c.start, c.end]);
              return handLandmarker;
            } catch (err) {
              lastErr = err;
              console.warn('Hand landmarker ' + delegate + ' failed', err);
            }
          }
          throw lastErr || new Error('HandLandmarker init failed');
        } catch (err) {
          console.warn('Hand landmarker unavailable', err);
          handLandmarkerFailed = true;
          handLandmarker = null;
          return null;
        }
      })();
      return handLandmarkerPromise;
    }

    // Detect hands and, when a face is present, how much of the hand sits on the
    // face. Returns null when no hand is in frame so nothing is drawn.
    async function trackHands(facePts) {
      if (usingSilhouette || usingPattern || !camVideo.videoWidth) {
        lastHandContours = null;
        return null;
      }
      const hl = await ensureHandLandmarker();
      if (!hl) {
        lastHandContours = null;
        return null;
      }
      const result = hl.detectForVideo(camVideo, performance.now());
      const hands = result.landmarks || [];
      if (!hands.length) {
        lastHandContours = null;
        return { hand_count: 0, hands_on_face_score: 0 };
      }
      const labels = (result.handedness || []).map((h) => (h && h[0] && h[0].categoryName) || '');
      lastHandContours = { hands, connections: hl._CONNECTIONS || [], labels };
      return {
        hand_count: hands.length,
        hands_on_face_score: handsOnFaceFromLandmarks(hands, facePts),
      };
    }

    // Fraction of hand landmarks that fall inside the face's bounding ellipse,
    // padded slightly so a chin-rest or cheek-prop counts. Real geometry, not a
    // luminance guess: a hand beside the head no longer reads as "hands on face".
    function handsOnFaceFromLandmarks(hands, facePts) {
      if (!hands || !hands.length || !facePts || !facePts.length) return 0;
      let minX = 1, maxX = 0, minY = 1, maxY = 0;
      facePts.forEach((p) => {
        if (p.x < minX) minX = p.x;
        if (p.x > maxX) maxX = p.x;
        if (p.y < minY) minY = p.y;
        if (p.y > maxY) maxY = p.y;
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
      // A resting hand puts roughly half its 21 landmarks over the face; scale so
      // that reads ~1.0 and a stray fingertip stays well under the threshold.
      return clamp01((best - 0.15) / 0.40);
    }

    // How much of each hand sits below the face midline (phone / object in lap).
    function handBelowFaceFromLandmarks(hands, facePts) {
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
      return clamp01((best - 0.35) / 0.50);
    }

    function handWristTipFromContours() {
      if (!lastHandContours || !lastHandContours.hands || !lastHandContours.hands.length) {
        return { wristY: null, tipY: null, wristX: null };
      }
      const pts = lastHandContours.hands[0];
      const wrist = pts[0], tip = pts[12] || pts[8];
      return {
        wristY: wrist ? wrist.y : null,
        tipY: tip ? tip.y : null,
        wristX: wrist ? wrist.x : null,
      };
    }

    function drawHandContoursOnOverlay() {
      if (!faceContoursOn || !lastHandContours || !lastHandContours.hands.length) return;
      const { w, h } = syncOverlaySize();
      const ctx = overlay.getContext('2d');
      const connections = lastHandContours.connections || [];
      ctx.save();
      ctx.lineWidth = Math.max(1.5, w * 0.0028);
      lastHandContours.hands.forEach((pts, index) => {
        const color = index === 0 ? '#a78bfa' : '#f0abfc';
        ctx.strokeStyle = color;
        ctx.fillStyle = color;
        ctx.globalAlpha = 0.95;
        connections.forEach((pair) => {
          const a = pts[pair[0]], b = pts[pair[1]];
          if (!a || !b) return;
          ctx.beginPath();
          ctx.moveTo((1 - a.x) * w, a.y * h);
          ctx.lineTo((1 - b.x) * w, b.y * h);
          ctx.stroke();
        });
        // Fingertips + wrist, so the pose is readable at a glance.
        [0, 4, 8, 12, 16, 20].forEach((i) => {
          const p = pts[i];
          if (!p) return;
          ctx.beginPath();
          ctx.arc((1 - p.x) * w, p.y * h, Math.max(2, w * 0.0042), 0, Math.PI * 2);
          ctx.fill();
        });
        const wrist = pts[0];
        const label = (lastHandContours.labels || [])[index];
        if (wrist && label) {
          ctx.globalAlpha = 0.85;
          ctx.font = Math.max(10, Math.round(w * 0.016)) + 'px Arial, sans-serif';
          ctx.fillText(label, (1 - wrist.x) * w + 6, wrist.y * h - 6);
        }
      });
      ctx.restore();
    }

    function headPoseFromMatrix(matrices, idx) {
      // MediaPipe facialTransformationMatrixes: column-major 4x4.
      if (!matrices || !matrices.length) return null;
      const raw = matrices[(idx == null || idx < 0) ? 0 : idx] || matrices[0];
      if (!raw) return null;
      const data = raw.data || raw;
      if (!data || data.length < 16) return null;
      const r00 = data[0], r01 = data[4], r02 = data[8];
      const r10 = data[1], r11 = data[5], r12 = data[9];
      const r20 = data[2], r21 = data[6], r22 = data[10];
      const pitch = Math.atan2(-r12, r22) * (180 / Math.PI);
      const yaw = Math.atan2(r02, Math.sqrt(r00 * r00 + r01 * r01)) * (180 / Math.PI);
      const roll = Math.atan2(-r01, r00) * (180 / Math.PI);
      return {
        head_pose_pitch: Math.max(-90, Math.min(90, pitch)),
        head_pose_yaw: Math.max(-90, Math.min(90, yaw)),
        head_pose_roll: Math.max(-90, Math.min(90, roll)),
      };
    }

    // Scale-invariant pitch proxy — mirrored by stare_geometry.geometric_pitch_deg
    // in Python and pinned by tests/test_stare_geometry.py. Positive = down.
    // It scores what fraction of the hairline->chin span sits above the eye line:
    // tilting down rotates the top of the skull toward the camera and foreshortens
    // the chin, so the fraction grows. Being a ratio, sitting closer cannot move
    // it - the pitch this replaced was (chin_y - forehead_y - 0.32) * 140, which
    // is face height in frame, i.e. it reported distance as if it were tilt.
    const STARE_NEUTRAL_UPPER_FRACTION = 0.42;
    const STARE_FRACTION_DEG_PER_UNIT = 250;
    const STARE_GEOM_PITCH_LIMIT_DEG = 60;

    function geometricPitchDeg(upper, lower) {
      const total = upper + lower;
      if (!Number.isFinite(total) || total <= 1e-6) return null;
      const fraction = upper / total;
      const deg = (fraction - STARE_NEUTRAL_UPPER_FRACTION) * STARE_FRACTION_DEG_PER_UNIT;
      return Math.max(-STARE_GEOM_PITCH_LIMIT_DEG, Math.min(STARE_GEOM_PITCH_LIMIT_DEG, deg));
    }

    // Spans are projected onto the face's own vertical axis (perpendicular to the
    // eye line) so head roll cancels, and x is rescaled by the frame aspect first
    // because landmark x/y are normalized by width/height separately.
    function facePitchFromLandmarks(pts, aspect) {
      if (!pts) return null;
      const left = pts[33], right = pts[263], chin = pts[152], forehead = pts[10];
      if (!left || !right || !chin || !forehead) return null;
      const ar = (Number.isFinite(aspect) && aspect > 0) ? aspect : 1;
      const ex = (right.x - left.x) * ar, ey = right.y - left.y;
      const elen = Math.hypot(ex, ey);
      if (elen <= 1e-6) return null;
      let vx = -ey / elen, vy = ex / elen;
      const midX = ((left.x + right.x) / 2) * ar, midY = (left.y + right.y) / 2;
      const along = (p) => (p.x * ar - midX) * vx + (p.y - midY) * vy;
      if (along(chin) < 0) { vx = -vx; vy = -vy; }
      const lower = along(chin);
      const upper = -along(forehead);
      return geometricPitchDeg(upper, lower);
    }

    function headPoseFromLandmarks(pts, aspect) {
      if (!pts || pts.length < 300) return null;
      const nose = pts[1], left = pts[33], right = pts[263], chin = pts[152], forehead = pts[10];
      if (!nose || !left || !right || !chin || !forehead) return null;
      const midX = (left.x + right.x) / 2;
      const yaw = (nose.x - midX) * 120;
      const pitch = facePitchFromLandmarks(pts, aspect);
      if (pitch == null) return null;
      const roll = Math.atan2(right.y - left.y, right.x - left.x) * (180 / Math.PI);
      return {
        head_pose_pitch: Math.max(-60, Math.min(60, pitch)),
        head_pose_yaw: Math.max(-60, Math.min(60, yaw)),
        head_pose_roll: Math.max(-45, Math.min(45, roll)),
      };
    }

    function motionFromGrid(grid) {
      const flat = [];
      for (let y = 0; y < grid.length; y += 2) {
        for (let x = 0; x < grid[y].length; x += 2) flat.push(grid[y][x]);
      }
      let delta = 0.12;
      if (lastLumaFlat && lastLumaFlat.length === flat.length) {
        let sum = 0;
        for (let i = 0; i < flat.length; i++) sum += Math.abs(flat[i] - lastLumaFlat[i]);
        delta = Math.max(0, Math.min(1, (sum / flat.length) * 8));
      }
      lastLumaFlat = flat;
      motionEma = motionEma * 0.65 + delta * 0.35;
      return Math.max(0, Math.min(1, motionEma));
    }

    function emotionFromBlendshapes(bs) {
      const smile = ((bs.mouthSmileLeft || 0) + (bs.mouthSmileRight || 0)) / 2;
      const frown = ((bs.mouthFrownLeft || 0) + (bs.mouthFrownRight || 0)) / 2;
      const jaw = bs.jawOpen || 0;
      const browDown = ((bs.browDownLeft || 0) + (bs.browDownRight || 0)) / 2;
      const browUp = bs.browInnerUp || 0;
      const funnel = bs.mouthFunnel || 0;
      // Yawn = jaw wide open without a smile / surprise-brow spike.
      const yawn = Math.max(0, Math.min(1,
        jaw * 1.15 * (1 - smile * 1.2) * (1 - Math.max(0, browUp - 0.22) * 1.4) + funnel * 0.25
      ));
      let expression_label = 'neutral';
      let expression_confidence = 0.45;
      if (yawn >= 0.48 && yawn >= smile + 0.10 && jaw >= 0.40) {
        expression_label = 'yawning';
        expression_confidence = Math.min(0.96, 0.50 + yawn * 0.48);
      } else if (smile >= 0.35 && smile > frown + 0.08) {
        expression_label = 'happy';
        expression_confidence = Math.min(0.98, 0.50 + smile * 0.55);
      } else if (frown >= 0.28 && frown >= smile) {
        expression_label = 'sad';
        expression_confidence = Math.min(0.95, 0.48 + frown * 0.55);
      } else if (jaw >= 0.35 && browUp >= 0.25 && yawn < 0.45) {
        expression_label = 'surprised';
        expression_confidence = Math.min(0.92, 0.45 + jaw * 0.4);
      } else if (browDown >= 0.40 && frown >= 0.15) {
        expression_label = 'angry';
        expression_confidence = Math.min(0.90, 0.42 + browDown * 0.4);
      }
      return {
        expression_label,
        expression_confidence,
        smile_score: smile,
        sad_score: frown,
        yawn_score: yawn,
        source: 'face_contours',
      };
    }

    function emotionFromLandmarkGeometry(lms) {
      // MediaPipe indices: mouth corners 61/291, upper/lower lip 13/14, eyes 33/263
      const L = (i) => lms[i];
      if (!lms || lms.length < 300) return null;
      const left = L(61), right = L(291), upper = L(13), lower = L(14);
      const le = L(33), re = L(263);
      if (!left || !right || !upper || !lower || !le || !re) return null;
      const mouthW = Math.hypot(right.x - left.x, right.y - left.y);
      const eyeW = Math.hypot(re.x - le.x, re.y - le.y) || 1e-6;
      const mouthOpen = Math.hypot(lower.x - upper.x, lower.y - upper.y) / eyeW;
      const mouthMidY = (left.y + right.y) / 2;
      const lipMidY = (upper.y + lower.y) / 2;
      // Corners above lip midline ⇒ smile; below ⇒ frown (y grows downward).
      const curve = (lipMidY - mouthMidY) / eyeW;
      const widthRatio = mouthW / eyeW;
      let smile = Math.max(0, Math.min(1, curve * 8 + (widthRatio - 1.15) * 1.2));
      let sad = Math.max(0, Math.min(1, -curve * 8 + Math.max(0, 1.05 - widthRatio) * 1.4));
      const yawn = Math.max(0, Math.min(1, (mouthOpen - 0.18) / 0.35 * (1 - smile)));
      let expression_label = 'neutral', expression_confidence = 0.42;
      if (yawn >= 0.50 && mouthOpen >= 0.30 && yawn >= smile + 0.08) {
        expression_label = 'yawning'; expression_confidence = 0.48 + yawn * 0.42;
      } else if (smile >= 0.42 && smile > sad + 0.06) {
        expression_label = 'happy'; expression_confidence = 0.48 + smile * 0.45;
      } else if (sad >= 0.40 && sad > smile) {
        expression_label = 'sad'; expression_confidence = 0.46 + sad * 0.45;
      } else if (mouthOpen >= 0.28 && yawn < 0.45) {
        expression_label = 'surprised'; expression_confidence = 0.45 + mouthOpen * 0.4;
      }
      return {
        expression_label,
        expression_confidence,
        smile_score: smile,
        sad_score: sad,
        yawn_score: yawn,
        source: 'face_contours',
      };
    }

    // A blink lasts ~100-300 ms. The old check called any single frame with the
    // lids down "eyes closed", so ordinary blinking clamped attention to 12% and
    // started the drowsy timer. Require a sustained closure in wall-clock time.
    const EYES_CLOSED_MIN_MS = 900;
    let eyesClosedSinceMs = 0;

    function sustainedEyesClosed(lidsDown, nowMs) {
      if (!lidsDown) {
        eyesClosedSinceMs = 0;
        return false;
      }
      if (!eyesClosedSinceMs) {
        eyesClosedSinceMs = nowMs;
        return false;
      }
      return (nowMs - eyesClosedSinceMs) >= EYES_CLOSED_MIN_MS;
    }

    function smoothMood(label, confidence) {
      moodHistory.push({ label, confidence });
      if (moodHistory.length > 6) moodHistory.shift();
      const counts = {};
      moodHistory.forEach((m) => {
        counts[m.label] = (counts[m.label] || 0) + (m.confidence || 0.4);
      });
      let best = label, bestScore = -1;
      Object.keys(counts).forEach((k) => {
        if (counts[k] > bestScore) { bestScore = counts[k]; best = k; }
      });
      const avgConf = moodHistory.reduce((a, m) => a + m.confidence, 0) / moodHistory.length;
      return { expression_label: best, expression_confidence: Math.min(0.99, avgConf) };
    }

    // Rolling most-frequent label over the window — a single odd frame cannot flip
    // the shown state, but a sustained change wins within a couple of seconds.
    function smoothLabel(history, label) {
      history.push(label);
      if (history.length > BEHAVIOR_SMOOTH_WINDOW) history.shift();
      const counts = {};
      history.forEach((l) => { counts[l] = (counts[l] || 0) + 1; });
      let best = label, bestScore = -1;
      Object.keys(counts).forEach((k) => {
        if (counts[k] > bestScore) { bestScore = counts[k]; best = k; }
      });
      return best;
    }

    function smoothScore(history, value) {
      const n = Number(value);
      if (!Number.isFinite(n)) return null;
      history.push(n);
      if (history.length > BEHAVIOR_SMOOTH_WINDOW) history.shift();
      return history.reduce((a, b) => a + b, 0) / history.length;
    }

    function resetBehaviorSmoothing() {
      attnHistory = [];
      behaviorHistory = [];
      attnScoreHistory = [];
      distractScoreHistory = [];
    }

    function drawDetectorFaceContour(box, mood) {
      // Fallback contour when MediaPipe is offline: face oval + eye/mouth lines.
      const { w, h } = syncOverlaySize();
      const vw = camVideo.videoWidth || 1, vh = camVideo.videoHeight || 1;
      // box is in video pixels; flip X for mirrored preview
      const x = (1 - (box.x + box.width) / vw) * w;
      const y = (box.y / vh) * h;
      const bw = (box.width / vw) * w;
      const bh = (box.height / vh) * h;
      const ctx = overlay.getContext('2d');
      const color = ({ happy: '#4ade80', sad: '#f87171', neutral: '#67e8f9',
        surprised: '#fbbf24', angry: '#fb7185', yawning: '#f59e0b' })[mood] || '#67e8f9';
      ctx.save();
      ctx.strokeStyle = color;
      ctx.lineWidth = Math.max(2, w * 0.003);
      ctx.beginPath();
      ctx.ellipse(x + bw / 2, y + bh * 0.48, bw * 0.42, bh * 0.48, 0, 0, Math.PI * 2);
      ctx.stroke();
      ctx.beginPath();
      ctx.ellipse(x + bw * 0.32, y + bh * 0.38, bw * 0.10, bh * 0.05, 0, 0, Math.PI * 2);
      ctx.ellipse(x + bw * 0.68, y + bh * 0.38, bw * 0.10, bh * 0.05, 0, 0, Math.PI * 2);
      ctx.stroke();
      ctx.beginPath();
      const my = y + bh * 0.68;
      const mx0 = x + bw * 0.30, mx1 = x + bw * 0.70;
      const bend = mood === 'happy' ? bh * 0.06 : (mood === 'sad' ? -bh * 0.06 : 0);
      ctx.moveTo(mx0, my);
      ctx.quadraticCurveTo((mx0 + mx1) / 2, my + bend, mx1, my);
      ctx.stroke();
      ctx.restore();
    }

    function drawFaceContoursOnOverlay() {
      if (!faceContoursOn || !lastFaceContours) return;
      if (lastFaceContours.fallbackBox) {
        drawDetectorFaceContour(lastFaceContours.fallbackBox, lastFaceContours.mood || 'neutral');
        return;
      }
      const { w, h } = syncOverlaySize();
      const ctx = overlay.getContext('2d');
      // Secondary faces: yellow dashed ovals so the operator sees everyone, not only the owner mesh.
      (lastFaceContours.secondaryBoxes || []).forEach((box) => {
        if (!box) return;
        ctx.save();
        ctx.strokeStyle = '#fbbf24';
        ctx.setLineDash([6, 4]);
        ctx.lineWidth = Math.max(2, w * 0.003);
        ctx.beginPath();
        const cx = (1 - (box.x + box.w / 2)) * w;
        const cy = (box.y + box.h / 2) * h;
        ctx.ellipse(cx, cy, (box.w * w) * 0.48, (box.h * h) * 0.52, 0, 0, Math.PI * 2);
        ctx.stroke();
        ctx.restore();
      });
      if (!lastFaceContours.pts) return;
      const pts = lastFaceContours.pts;
      const mood = lastFaceContours.mood || 'neutral';
      const mismatch = lastFaceContours.ownerStatus === 'mismatch';
      const color = mismatch ? '#f87171' : (({
        happy: '#4ade80', sad: '#f87171', surprised: '#fbbf24',
        angry: '#fb7185', neutral: '#67e8f9', unknown: '#94a3b8',
      })[mood] || '#67e8f9');
      ctx.save();
      ctx.lineWidth = Math.max(1.5, w * 0.0025);
      ctx.strokeStyle = color;
      ctx.globalAlpha = 0.95;
      (lastFaceContours.connections || []).forEach((pair) => {
        const a = pair.start != null ? pair.start : pair[0];
        const b = pair.end != null ? pair.end : pair[1];
        if (!pts[a] || !pts[b]) return;
        ctx.beginPath();
        ctx.moveTo((1 - pts[a].x) * w, pts[a].y * h);
        ctx.lineTo((1 - pts[b].x) * w, pts[b].y * h);
        ctx.stroke();
      });
      ctx.fillStyle = color;
      [33, 263, 61, 291, 13, 14].forEach((i) => {
        const p = pts[i];
        if (!p) return;
        ctx.beginPath();
        ctx.arc((1 - p.x) * w, p.y * h, Math.max(2, w * 0.004), 0, Math.PI * 2);
        ctx.fill();
      });
      const label = (lastFaceContours.displayName || '').trim();
      if (label && !mismatch) {
        let minY = 1, minX = 1, maxX = 0;
        pts.forEach((p) => {
          if (!p) return;
          if (p.y < minY) minY = p.y;
          if (p.x < minX) minX = p.x;
          if (p.x > maxX) maxX = p.x;
        });
        const lx = (1 - (minX + maxX) / 2) * w;
        const ly = Math.max(14, minY * h - 10);
        ctx.font = 'bold 12px ui-sans-serif, system-ui, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillStyle = 'rgba(15, 23, 42, 0.72)';
        const tw = ctx.measureText(label).width + 10;
        ctx.fillRect(lx - tw / 2, ly - 12, tw, 16);
        ctx.fillStyle = '#e2e8f0';
        ctx.fillText(label, lx, ly);
      }
      ctx.restore();
    }

    async function trackFaceContoursAndMood() {
      if (usingSilhouette || usingPattern || !camVideo.videoWidth) {
        lastFaceContours = null;
        setDetectorStatus('off', 'synthetic source — no real face to track');
        return null;
      }
      const lm = await ensureFaceLandmarker();
      if (lm) {
        const result = lm.detectForVideo(camVideo, performance.now());
        const faces = result.faceLandmarks || [];
        if (!faces.length) {
          lastDetectedFaces = null;
          lastFaceContours = null;
          moodHistory = [];
          eyesClosedSinceMs = 0;
          resetBehaviorSmoothing();
          setDetectorStatus('face_mesh', 'face mesh running — no face in frame');
          return {
            face_count: 0, expression_label: 'unknown', expression_confidence: 0.55,
            gaze_frontal: 0.12, gaze_down_score: 0.2, face_size_ratio: null,
            attention: 'away_from_webcam', source: 'face_contours',
            owner_face_enrolled: faceOwnerState.enrolled,
            owner_face_match: null,
            owner_face_name: faceOwnerState.displayName || null,
            owner_match_score: 0,
            secondary_face_count: 0,
          };
        }
        lastDetectedFaces = faces;
        const pick = pickOwnerFace(faces, Date.now());
        // Face ID mismatch: strangers do not drive mood/attention/teaching metrics.
        if (pick.owner_enrolled && pick.owner_match === false) {
          const statusEl = document.getElementById('face-id-status');
          if (statusEl) {
            statusEl.className = 'face-id-status bad';
            statusEl.textContent = 'Face ID mismatch — '
              + (pick.display_name || faceOwnerState.displayName || 'enrolled learner')
              + ' not in frame. Teaching paused; other faces ignored.';
          }
          lastFaceContours = {
            pts: null, connections: [], mood: 'unknown',
            secondaryBoxes: faces.map((f) => faceBoxFromPts(f)).filter(Boolean),
            ownerStatus: 'mismatch',
            displayName: pick.display_name || faceOwnerState.displayName || '',
          };
          return {
            face_count: faces.length,
            expression_label: 'unknown',
            expression_confidence: 0,
            gaze_frontal: 0,
            gaze_down_score: 0,
            eyes_closed_score: 0,
            yawn_score: 0,
            face_size_ratio: null,
            attention: 'away_from_webcam',
            source: 'face_contours',
            owner_face_enrolled: true,
            owner_face_match: false,
            owner_face_name: pick.display_name || faceOwnerState.displayName || null,
            owner_match_score: pick.match_score,
            secondary_face_count: pick.secondary_count,
          };
        }
        const faceIdx = pick.index >= 0 ? pick.index : 0;
        const pts = faces[faceIdx];
        const ownerStatus = !pick.owner_enrolled ? 'enrolling'
          : (pick.owner_match ? 'owner' : 'mismatch');
        if (pick.owner_enrolled && pick.owner_match) {
          updateFaceIdUi();
        }
        setDetectorStatus('face_mesh',
          'face mesh tracking (' + (lm._assetLabel || 'assets') + '/' + (lm._delegate || '?')
          + ') · ' + faces.length + ' face' + (faces.length === 1 ? '' : 's')
          + ' · ' + ownerStatus
          + (pick.display_name ? (' · ' + pick.display_name) : ''));
        const bs = blendshapeMap(result.faceBlendshapes, faceIdx);
        let mood = Object.keys(bs).length
          ? emotionFromBlendshapes(bs)
          : emotionFromLandmarkGeometry(pts);
        if (!mood) mood = { expression_label: 'neutral', expression_confidence: 0.4, source: 'face_contours' };
        mood = { ...mood, ...smoothMood(mood.expression_label, mood.expression_confidence) };
        const connections = (lm._CONNECTIONS || []).map((c) => [c.start, c.end]);
        lastFaceContours = {
          pts, connections, mood: mood.expression_label,
          secondaryBoxes: secondaryBoxesFromFaces(faces, faceIdx),
          ownerStatus,
          displayName: pick.display_name || faceOwnerState.displayName || '',
        };
        const nose = pts[1], leftEye = pts[33], rightEye = pts[263];
        let gaze_frontal = 0.85;
        if (nose && leftEye && rightEye) {
          const midX = (leftEye.x + rightEye.x) / 2;
          gaze_frontal = Math.max(0, Math.min(1, 1 - Math.abs(nose.x - midX) * 6));
        }
        const lookDown = ((bs.eyeLookDownLeft || 0) + (bs.eyeLookDownRight || 0)) / 2;
        const lookUp = ((bs.eyeLookUpLeft || 0) + (bs.eyeLookUpRight || 0)) / 2;
        const blinkL = bs.eyeBlinkLeft || 0;
        const blinkR = bs.eyeBlinkRight || 0;
        const blink = (blinkL + blinkR) / 2;
        // Eye-gaze cue only, as a *difference* with a dead band: every seated
        // learner has the nose below the eye line and a resting eyeLookDown of
        // 0.2-0.3, and the old scoring turned both into "looking down" (a learner
        // staring straight at the monitor read 0.55). Head-pose truth comes from
        // the stare residual, which sampleFrame folds in after calibration.
        // Clamped: the server rejects any 0..1 signal above 1.0 with a 422.
        const gaze_down = clamp01((lookDown - lookUp - 0.25) / 0.5);
        const lids_down = blink >= 0.45 || Math.min(blinkL, blinkR) >= 0.40;
        const eyes_closed = sustainedEyesClosed(lids_down, Date.now());
        if (eyes_closed) gaze_frontal = Math.min(gaze_frontal, 0.25);
        const yawn_score = Math.max(mood.yawn_score || 0, (mood.expression_label === 'yawning') ? 0.62 : 0);
        const yawning = yawn_score >= 0.48 || mood.expression_label === 'yawning';
        let attention = 'looking';
        if (eyes_closed) attention = 'eyes_closed';
        else if (yawning) attention = 'yawning';
        else if (gaze_down >= 0.38 || gaze_frontal < 0.40) attention = 'eyes_away';
        const faceH = Math.max(...pts.map((p) => p.y)) - Math.min(...pts.map((p) => p.y));
        const aspect = (camVideo.videoWidth && camVideo.videoHeight)
          ? (camVideo.videoWidth / camVideo.videoHeight) : 1;
        // Kept alongside the pose: the geometric proxy has a guaranteed sign
        // (positive = down), which is what teaches the stare lab which way the
        // matrix pitch runs instead of making the operator press "Set down".
        const geomPitch = facePitchFromLandmarks(pts, aspect);
        const matrixPose = headPoseFromMatrix(result.facialTransformationMatrixes, faceIdx);
        const pose = matrixPose || headPoseFromLandmarks(pts, aspect) || {};
        const brow_raise = bs.browInnerUp || 0;
        const smile = mood.smile_score != null ? mood.smile_score
          : (((bs.mouthSmileLeft || 0) + (bs.mouthSmileRight || 0)) / 2);
        // Do not invent "confused" from raised brows — resting faces vary widely
        // and a neutral brow raise is not pedagogical confusion.
        const expression_label = yawning ? 'yawning' : mood.expression_label;
        return {
          face_count: faces.length,
          expression_label,
          expression_confidence: mood.expression_confidence,
          gaze_frontal,
          gaze_down_score: gaze_down,
          // Report the debounced decision, not the raw per-frame lid score: the
          // server thresholds this field at 0.45 and would otherwise reintroduce
          // blink sensitivity we just filtered out.
          eyes_closed_score: eyes_closed ? Math.max(0.60, blink) : Math.min(blink, 0.30),
          eyes_closed_raw_score: blink,
          eyes_closed,
          yawn_score,
          brow_raise_score: brow_raise,
          smile_score: smile,
          face_size_ratio: Math.max(0.05, Math.min(0.9, faceH)),
          attention,
          source: 'face_contours',
          sad_score: mood.sad_score,
          head_pitch_geom_deg: geomPitch,
          pose_source: matrixPose ? 'matrix' : 'landmarks',
          owner_face_enrolled: !!pick.owner_enrolled,
          owner_face_match: pick.owner_match,
          owner_face_name: pick.display_name || faceOwnerState.displayName || null,
          owner_match_score: pick.match_score,
          secondary_face_count: pick.secondary_count,
          ...pose,
        };
      }
      // Fallback: FaceDetector box + mouth-curve contour (no MediaPipe).
      if ('FaceDetector' in window && camVideo.videoWidth) {
        try {
          if (!window.__twFaceDetector) {
            window.__twFaceDetector = new FaceDetector({
              fastMode: false, maxDetectedFaces: FACE_OWNER_MAX_FACES,
            });
          }
          const faces = await window.__twFaceDetector.detect(camVideo);
          setDetectorStatus('face_detector',
            'browser FaceDetector box only — eye/gaze/mood claims are suppressed');
          if (!faces.length) {
            lastFaceContours = null;
            eyesClosedSinceMs = 0;
            return {
              face_count: 0, expression_label: 'unknown', expression_confidence: 0.5,
              gaze_frontal: 0.1, gaze_down_score: 0.2, face_size_ratio: null,
              attention: 'away_from_webcam', source: 'face_detector',
              owner_face_enrolled: faceOwnerState.enrolled,
              owner_face_match: null,
              owner_match_score: 0, secondary_face_count: 0,
            };
          }
          // Prefer largest box (closest to "owner" heuristic without landmarks).
          let best = faces[0], bestA = 0;
          faces.forEach((f) => {
            const b = f.boundingBox;
            const a = (b.width || 0) * (b.height || 0);
            if (a > bestA) { bestA = a; best = f; }
          });
          const box = best.boundingBox;
          return {
            face_count: faces.length, box, source: 'face_detector',
            owner_face_enrolled: false, owner_face_match: null,
            owner_match_score: null, secondary_face_count: Math.max(0, faces.length - 1),
          };
        } catch (_) {}
      }
      setDetectorStatus('coarse',
        'no face-mesh and no browser FaceDetector — presence only, '
        + 'per-feature behavior (eyes, gaze, mood) is not reported');
      return null;
    }

    function estimateFacialFromGrid(grid) {
      const h = grid.length, w = grid[0].length;
      const vals = [];
      for (let y = Math.floor(h * 0.08); y < Math.floor(h * 0.78); y++) {
        for (let x = Math.floor(w * 0.22); x < Math.floor(w * 0.78); x++) vals.push(grid[y][x]);
      }
      const mean = vals.reduce((a, b) => a + b, 0) / Math.max(1, vals.length);
      const std = Math.sqrt(vals.reduce((a, b) => a + (b - mean) * (b - mean), 0) / Math.max(1, vals.length));
      let darkN = 0, darkY = 0, darkX = 0;
      const thr = mean - 0.04;
      const cr0 = Math.floor(h * 0.08), cr1 = Math.floor(h * 0.78);
      const cc0 = Math.floor(w * 0.22), cc1 = Math.floor(w * 0.78);
      for (let y = cr0; y < cr1; y++) for (let x = cc0; x < cc1; x++) {
        if (grid[y][x] < thr) { darkN++; darkY += y; darkX += x; }
      }
      const darkRatio = darkN / Math.max(1, (cr1 - cr0) * (cc1 - cc0));
      const facePresent = std >= 0.045 && darkRatio >= 0.04 && darkRatio <= 0.72;
      if (!facePresent) {
        return { face_count: 0, expression_label: 'unknown', expression_confidence: 0.55,
          gaze_frontal: 0.12, gaze_down_score: 0.15, face_size_ratio: null, attention: 'away_from_webcam' };
      }
      const cy = darkY / darkN / Math.max(1, h - 1);
      const cx = darkX / darkN / Math.max(1, w - 1);
      const gaze_down = Math.max(0, Math.min(1, (cy - 0.38) / 0.42));
      const gaze_frontal = Math.max(0, Math.min(1, 1 - Math.abs(cx - 0.5) * 2.4 - Math.max(0, gaze_down - 0.55) * 0.35));
      // Mouth-band horizontal edges → smile proxy
      let mouthEdges = 0, mouthN = 0, mouthSum = 0, cheekSum = 0, cheekN = 0, eyeSum = 0, eyeN = 0;
      for (let y = Math.floor(h * 0.50); y < Math.floor(h * 0.70); y++) {
        for (let x = Math.floor(w * 0.32); x < Math.floor(w * 0.68) - 1; x++) {
          mouthEdges += Math.abs(grid[y][x + 1] - grid[y][x]); mouthN++; mouthSum += grid[y][x];
        }
      }
      for (let y = Math.floor(h * 0.38); y < Math.floor(h * 0.55); y++) {
        for (let x = Math.floor(w * 0.22); x < Math.floor(w * 0.78); x++) { cheekSum += grid[y][x]; cheekN++; }
      }
      for (let y = Math.floor(h * 0.12); y < Math.floor(h * 0.38); y++) {
        for (let x = Math.floor(w * 0.28); x < Math.floor(w * 0.72); x++) { eyeSum += grid[y][x]; eyeN++; }
      }
      const me = mouthN ? mouthEdges / mouthN : 0;
      const mouthMean = mouthN ? mouthSum / mouthN : 0;
      const cheekMean = cheekN ? cheekSum / cheekN : 0;
      const eyeMean = eyeN ? eyeSum / eyeN : 0;
      const smileRaw = Math.max(0, Math.min(1, (me - 0.035) / 0.08 + Math.max(0, mouthMean - cheekMean) * 1.8));
      const smile = smileRaw * Math.max(0, 1 - Math.max(0, gaze_down - 0.20) / 0.50);
      const sad = Math.max(0, Math.min(1, Math.max(0, (cheekMean - eyeMean) * 2.2) + Math.max(0, 0.05 - me) * 8 + Math.max(0, 0.55 - smile) * 0.35));
      let expression_label = 'neutral', expression_confidence = 0.45;
      if (smile >= 0.55 && smile >= sad + 0.08) { expression_label = 'happy'; expression_confidence = 0.45 + smile * 0.5; }
      else if (sad >= 0.52 && sad > smile + 0.05) { expression_label = 'sad'; expression_confidence = 0.42 + sad * 0.5; }
      // Eye state is deliberately NOT guessed here. The old edge-contrast proxy
      // (low horizontal detail in a fixed 16-38% band == closed lids) fires on any
      // soft or low-contrast webcam image and reported "eyes closed" for minutes
      // while the learner was looking straight at the camera. Only real landmarks
      // (MediaPipe blendshapes) may claim eye state; see trackFaceContoursAndMood.
      const eyes_closed_score = null;
      const eyes_closed = false;
      // Grid yawn: dark mouth cavity relative to cheeks + weak smile edges.
      const yawn_score = Math.max(0, Math.min(1,
        Math.max(0, (cheekMean - mouthMean) * 2.6)
        + Math.max(0, 0.045 - me) * 5.5
        + Math.max(0, 0.35 - smile) * 0.35
        - smile * 0.55
      ));
      const yawning = yawn_score >= 0.55 && yawn_score >= smile + 0.08;
      if (yawning) { expression_label = 'yawning'; expression_confidence = 0.45 + yawn_score * 0.45; }
      const attention = yawning
        ? 'yawning'
        : ((gaze_down >= 0.45 || gaze_frontal < 0.35) ? 'eyes_away' : 'looking');
      // Linear face size from dark-pixel bbox (larger face ⇒ closer to camera).
      let minX = w, minY = h, maxX = -1, maxY = -1;
      for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
        if (grid[y][x] < thr) {
          if (x < minX) minX = x; if (y < minY) minY = y;
          if (x > maxX) maxX = x; if (y > maxY) maxY = y;
        }
      }
      let face_size_ratio = Math.max(0.05, Math.min(0.45, darkRatio * 1.8));
      // Normalised (0..1) face box for the coarse contour overlay. Lets the user
      // still see a tracked outline + mood colour when the mesh cannot load,
      // without claiming landmark-grade accuracy.
      let grid_box = null;
      if (maxX >= minX && maxY >= minY) {
        const boxW = (maxX - minX + 1) / w;
        const boxH = (maxY - minY + 1) / h;
        face_size_ratio = Math.max(0.04, Math.min(0.85, Math.max(boxW * 0.85, boxH * 0.55)));
        grid_box = {
          x: minX / w,
          y: minY / h,
          width: (maxX - minX + 1) / w,
          height: (maxY - minY + 1) / h,
        };
      }
      return {
        face_count: 1, expression_label, expression_confidence,
        gaze_frontal, gaze_down_score: gaze_down,
        eyes_closed_score, eyes_closed, yawn_score,
        face_size_ratio,
        grid_box,
        attention,
        distance_from_camera_m: null,
        distance_source: null,
        // "Something person-shaped is in frame", not a tracked face. Callers must
        // not promote coarse output into confident per-feature behavior claims.
        coarse: true,
        source: 'coarse',
      };
    }

    // Clean "no face in frame" reading. Built fresh instead of spreading over the
    // coarse grid estimate, so stale grid scores cannot leak out alongside
    // face_count 0 (that combination produced "absent" + "eyes closed for 39.9s").
    function noFaceFacial(source) {
      return {
        face_count: 0,
        expression_label: 'unknown',
        expression_confidence: 0.55,
        gaze_frontal: null,
        gaze_down_score: null,
        eyes_closed_score: null,
        eyes_closed: false,
        yawn_score: null,
        smile_score: null,
        sad_score: null,
        brow_raise_score: null,
        face_size_ratio: null,
        attention: 'away_from_webcam',
        distance_from_camera_m: null,
        distance_source: null,
        source: source || 'none',
      };
    }

    async function sampleLidarDistanceMeters() {
      // 1) Native / Capacitor / app bridge (phones with LiDAR).
      try {
        if (window.AOEPLidar && typeof window.AOEPLidar.getDistanceMeters === 'function') {
          const m = await window.AOEPLidar.getDistanceMeters();
          if (typeof m === 'number' && m > 0.05 && m < 8) return { meters: m, source: 'lidar' };
        }
      } catch (_) {}
      // 2) Depth MediaStreamTrack (rare USB / phone depth cameras).
      try {
        if (camStream) {
          const depthTrack = camStream.getVideoTracks().find((t) => {
            const label = (t.label || '').toLowerCase();
            const settings = t.getSettings ? t.getSettings() : {};
            return label.includes('depth') || label.includes('lidar') || settings.depth === true;
          });
          if (depthTrack && 'ImageCapture' in window) {
            const cap = new ImageCapture(depthTrack);
            if (cap.grabFrame) {
              const frame = await cap.grabFrame();
              const c = document.createElement('canvas');
              c.width = frame.width; c.height = frame.height;
              const ctx = c.getContext('2d');
              ctx.drawImage(frame, 0, 0);
              const px = ctx.getImageData(Math.floor(frame.width / 2), Math.floor(frame.height / 2), 1, 1).data;
              // Many depth previews encode metres*scale in luma; treat 1..250 as cm→m heuristic.
              const raw = px[0];
              if (raw > 1) {
                const meters = raw < 40 ? raw / 10 : raw / 100;
                if (meters > 0.15 && meters < 6) return { meters, source: 'lidar' };
              }
            }
          }
        }
      } catch (_) {}
      // 3) WebXR depth-sensing when an AR session already exists.
      try {
        if (navigator.xr && window.__twXrDepthMeters) {
          const m = await window.__twXrDepthMeters();
          if (typeof m === 'number' && m > 0.05 && m < 8) return { meters: m, source: 'lidar' };
        }
      } catch (_) {}
      return null;
    }

    async function estimateFacialExperience(grid) {
      let facial = estimateFacialFromGrid(grid);
      const contourMood = await trackFaceContoursAndMood();
      if (contourMood) {
        if (contourMood.face_count === 0) {
          // A real detector ran and saw nobody: drop the coarse grid reading
          // entirely rather than merging over it.
          facial = noFaceFacial(contourMood.source);
        } else if (contourMood.expression_label) {
          facial = {
            ...facial,
            ...contourMood,
            face_size_ratio: contourMood.face_size_ratio || facial.face_size_ratio,
          };
        } else if (contourMood.box) {
          const box = contourMood.box;
          const linear = Math.max(box.width / camVideo.videoWidth, box.height / camVideo.videoHeight);
          facial = {
            ...facial,
            face_count: 1,
            face_size_ratio: Math.max(0.04, Math.min(0.9, linear)),
            source: 'face_detector',
          };
          lastFaceContours = {
            pts: null,
            connections: null,
            mood: facial.expression_label || 'neutral',
            fallbackBox: box,
          };
        }
      }
      // The landmark mesh is the strongest detector we have. When it is tracking a
      // face, the coarse FaceDetector box must not run: a single missed box used to
      // wipe good landmark data and flip a present learner to "away from webcam".
      const meshTracked = facial.source === 'face_contours' && (facial.face_count || 0) > 0;
      if (!meshTracked && !usingSilhouette && !usingPattern && camVideo.videoWidth && ('FaceDetector' in window)) {
        try {
          if (!window.__twFaceDetector) window.__twFaceDetector = new FaceDetector({
            fastMode: true, maxDetectedFaces: FACE_OWNER_MAX_FACES,
          });
          const faces = await window.__twFaceDetector.detect(camVideo);
          if (!faces.length) {
            facial = noFaceFacial('face_detector');
          } else {
            const box = faces[0].boundingBox;
            // Linear size vs window frame (NOT area) — larger face ⇒ closer.
            const linear = Math.max(
              box.width / camVideo.videoWidth,
              box.height / camVideo.videoHeight,
            );
            const cy = (box.y + box.height / 2) / camVideo.videoHeight;
            const cx = (box.x + box.width / 2) / camVideo.videoWidth;
            const gaze_down = Math.max(0, Math.min(1, (cy - 0.35) / 0.4));
            const gaze_frontal = Math.max(0, Math.min(1, 1 - Math.abs(cx - 0.5) * 2.2));
            const attn = facial.eyes_closed
              ? 'eyes_closed'
              : ((gaze_down >= 0.45 || gaze_frontal < 0.35)
                  ? 'eyes_away'
                  : (facial.attention || 'looking'));
            facial = {
              ...facial,
              face_count: faces.length,
              face_size_ratio: Math.max(0.04, Math.min(0.9, linear)),
              gaze_down_score: Math.max(facial.gaze_down_score || 0, gaze_down * 0.85),
              gaze_frontal: Math.min(facial.gaze_frontal || 1, gaze_frontal),
              attention: attn,
            };
          }
        } catch (_) { /* FaceDetector optional */ }
      }
      // Coarse visual fallback: no mesh and no FaceDetector, but the grid sees a
      // person. Draw an approximate oval + mood-coloured mouth so the operator
      // still gets visible face tracking and a mood read instead of a blank card.
      // This is a UX affordance only — the detector badge still says "coarse" and
      // no eye/gaze/distance behaviour is claimed from it.
      if (
        !meshTracked && !usingSilhouette && !usingPattern &&
        faceContoursOn && facial.source === 'coarse' &&
        (facial.face_count || 0) > 0 && facial.grid_box &&
        camVideo.videoWidth
      ) {
        const gb = facial.grid_box;
        lastFaceContours = {
          pts: null,
          connections: null,
          mood: facial.expression_label || 'neutral',
          fallbackBox: {
            x: gb.x * camVideo.videoWidth,
            y: gb.y * camVideo.videoHeight,
            width: gb.width * camVideo.videoWidth,
            height: gb.height * camVideo.videoHeight,
          },
        };
      }
      const lidar = (!usingSilhouette && !usingPattern) ? await sampleLidarDistanceMeters() : null;
      if (lidar) {
        facial.distance_from_camera_m = lidar.meters;
        facial.distance_source = 'lidar';
      }
      if (usingSilhouette) {
        facial = { face_count: 0, expression_label: 'unknown', expression_confidence: 0.2,
          gaze_frontal: 0.2, gaze_down_score: 0.1, face_size_ratio: null, attention: 'away_from_webcam',
          distance_from_camera_m: null, distance_source: null };
      }
      return facial;
    }

    function updateFacialHud(p, facial) {
      const mood = (p && p.dominant_expression) || (facial && facial.expression_label) || 'unknown';
      const conf = (p && p.expression_confidence != null) ? p.expression_confidence : (facial && facial.expression_confidence);
      const awayMs = (p && p.eyes_away_for_ms) || 0;
      const closedMs = (p && p.eyes_closed_for_ms) || 0;
      const yawnMs = (p && p.yawn_for_ms) || 0;
      const inattMs = (p && p.inattentive_for_ms) || 0;
      const absent = !!(p && (p.state === 'absent' || p.face_count === 0));
      let behavior = (p && p.behavior_label) || 'unknown';
      let attn = 'looking';
      if (absent) attn = 'away_from_webcam';
      else if ((facial && facial.eyes_closed) || closedMs > 0) attn = 'eyes_closed';
      else if (behavior === 'yawning' || yawnMs > 0 || (facial && facial.attention === 'yawning')) attn = 'yawning';
      else if (behavior === 'distracted') attn = 'distracted';
      else if (behavior === 'inattentive' || inattMs >= 4000) attn = 'inattentive';
      else if (awayMs > 0 || (facial && facial.attention === 'eyes_away')) attn = 'eyes_away';
      else if (facial && facial.attention) attn = facial.attention;
      // Absence is reported immediately (and clears the window); otherwise both
      // the attention and behaviour labels are the rolling majority, so a lone
      // noisy frame no longer swings the card.
      if (absent) {
        resetBehaviorSmoothing();
      } else {
        attn = smoothLabel(attnHistory, attn);
        behavior = smoothLabel(behaviorHistory, behavior);
      }
      const attnScore = absent
        ? (p && p.attention_score)
        : smoothScore(attnScoreHistory, p && p.attention_score);
      const distractScore = absent
        ? (p && p.distraction_score)
        : smoothScore(distractScoreHistory, p && p.distraction_score);
      const moodCard = document.getElementById('facial-mood-card');
      const attnCard = document.getElementById('facial-attn-card');
      const behCard = document.getElementById('facial-beh-card');
      const distCard = document.getElementById('facial-dist-card');
      moodCard.className = 'facial-card mood-' + mood;
      attnCard.className = 'facial-card attn-' + attn;
      if (behCard) behCard.className = 'facial-card beh-' + behavior;
      document.getElementById('facial-mood').textContent = mood;
      const moodSrc = (facial && facial.source) || 'grid';
      const SRC_LABELS = { face_contours: 'facial contours', coarse: 'coarse heuristic' };
      document.getElementById('facial-mood-sub').textContent = (usingPattern || usingSilhouette)
        // Synthetic frames have no face on purpose; say so instead of looking broken.
        ? (usingPattern ? 'test pattern' : 'silhouette demo')
          + ' · synthetic frame, no face to read · exercising the quality gates'
        : 'confidence ' + (conf == null ? 'n/a' : Math.round(conf * 100) + '%') +
          ' · ' + (SRC_LABELS[moodSrc] || moodSrc) +
          ' · behavior ' + pct(p && p.expression_behavior_score);
      const attnLabel = ({
        looking: 'looking', eyes_away: 'eyes away', eyes_closed: 'eyes closed',
        yawning: 'yawning', distracted: 'distracted', inattentive: 'not paying attention',
        away_from_webcam: 'away from webcam',
      })[attn] || attn;
      document.getElementById('facial-attn').textContent = attnLabel;
      if (behCard) {
        const behLabel = ({
          focused: 'focused', yawning: 'yawning', distracted: 'distracted',
          inattentive: 'not paying attention', drowsy: 'drowsy', away: 'away',
        })[behavior] || behavior;
        document.getElementById('facial-beh').textContent = behLabel;
        const attnPct = (attnScore != null) ? Math.round(attnScore * 100) + '%' : 'n/a';
        const distPct = (distractScore != null) ? Math.round(distractScore * 100) + '%' : 'n/a';
        document.getElementById('facial-beh-sub').textContent =
          'avg attention ' + attnPct + ' · avg distraction ' + distPct +
          (inattMs ? (' · ' + (inattMs / 1000).toFixed(1) + 's') : '');
      }
      const dist = (p && p.distance_from_camera_m != null) ? p.distance_from_camera_m : null;
      // Same D the stare lab needs for atan(y_screen / D).
      if (dist != null) stareDistanceM = Number(dist);
      const src = (p && p.distance_source) || (facial && facial.distance_source) || (dist != null ? 'face_size' : 'none');
      distCard.className = 'facial-card dist-' + src;
      document.getElementById('facial-dist').textContent = dist == null ? 'n/a' : (Number(dist).toFixed(2) + ' m');
      document.getElementById('facial-dist-sub').textContent =
        src === 'lidar' ? 'LiDAR / depth camera'
          : (src === 'face_size' ? ('face size in frame' + (facial && facial.face_size_ratio != null ? (' · ratio ' + Number(facial.face_size_ratio).toFixed(2)) : ''))
            : 'move closer so your face fills more of the window');
      document.getElementById('facial-attn-sub').textContent =
        closedMs ? ('eyes closed for ' + (closedMs / 1000).toFixed(1) + 's')
          : (yawnMs ? ('yawning for ' + (yawnMs / 1000).toFixed(1) + 's')
            : (awayMs ? ('eyes away for ' + (awayMs / 1000).toFixed(1) + 's') : 'on-camera attention'));
    }

    const integrityAnnounce = { phoneAt: 0, closedAt: 0, awayAt: 0, yawnAt: 0, inattAt: 0, distractAt: 0, ownerAt: 0 };
    function maybeAnnounceIntegrity(kind, message) {
      const now = Date.now();
      const last = integrityAnnounce[kind] || 0;
      if (now - last < 12000) return;
      integrityAnnounce[kind] = now;
      toast(message);
      if (autoSpeak()) speakTheodore(message, voiceLangCode());
    }

    // Finite numbers pass through; anything unmeasured becomes null.
    function num(value) {
      return (typeof value === 'number' && isFinite(value)) ? value : null;
    }

    async function sampleFrame() {
      if (labOffline) return;
      refreshSilhouetteGuide();
      const grid = luminanceGrid();
      if (!grid) return;
      patternPhase += 1;
      const foreground = estimateForeground(grid);
      const motion = usingSilhouette ? 0.02 : motionFromGrid(grid);
      const facial = await estimateFacialExperience(grid);
      // Distance comes from LiDAR when present, otherwise from the face-size
      // estimate the server returned for the previous frame (stareDistanceM
      // keeps the last value) — one frame of lag on a seat that barely moves.
      updateTiltLab(usingPattern || usingSilhouette ? null : facial,
        facial ? facial.distance_from_camera_m : null);
      // Head-pose truth for "looking down" is the stare residual: how far below
      // the lesson band this seat is actually staring. The eye-blendshape cue
      // stays as a floor for eyes-down-without-head-movement.
      if (stareGazeDown != null) {
        facial.gaze_down_score = clamp01(Math.max(stareGazeDown, facial.gaze_down_score || 0));
      }
      const audio = sampleMicAudio();
      const signal = {
            participant_id: 'camera-local',
            timestamp_ms: liveCamTimestampMs(),
            face_count: usingSilhouette ? 0 : facial.face_count,
            liveness_state: usingSilhouette ? 'unknown' : (facial.face_count > 0 ? 'live' : 'unknown'),
            owner_face_enrolled: !!(facial.owner_face_enrolled),
            owner_face_match: facial.owner_face_match == null ? null : !!facial.owner_face_match,
            owner_face_name: facial.owner_face_name || faceOwnerState.displayName || null,
            owner_match_score: signalNum(facial.owner_match_score),
            secondary_face_count: usingSilhouette ? 0 : Math.max(0, facial.secondary_face_count || 0),
            foreground_ratio: usingSilhouette ? Math.max(0.96, foreground) : Math.min(0.55, Math.max(0.25, foreground)),
            motion_score: motion,
            body_motion_score: motion,
            fidget_score: Math.max(0, Math.min(1, (motion - 0.12) * 2.4)),
            expression_label: facial.expression_label,
            expression_confidence: facial.expression_confidence,
            gaze_frontal: facial.gaze_frontal,
            gaze_down_score: facial.gaze_down_score,
            gaze_up_score: (stareResidualDeg != null && stareResidualDeg < -6)
              ? clamp01((-stareResidualDeg - 6) / 30) : null,
            gaze_left_score: (facial.head_pose_yaw != null && facial.head_pose_yaw < -10)
              ? clamp01((-facial.head_pose_yaw - 10) / 30) : null,
            gaze_right_score: (facial.head_pose_yaw != null && facial.head_pose_yaw > 10)
              ? clamp01((facial.head_pose_yaw - 10) / 30) : null,
            stare_residual_deg: num(stareResidualDeg),
            // null (not 0) when no real detector measured it, so the server can
            // tell "measured as open" apart from "nobody looked".
            eyes_closed_score: num(facial.eyes_closed_score),
            yawn_score: num(facial.yawn_score),
            brow_raise_score: num(facial.brow_raise_score),
            smile_score: num(facial.smile_score),
            detector_source: detectorSource,
            head_pose_pitch: facial.head_pose_pitch,
            head_pose_yaw: facial.head_pose_yaw,
            head_pose_roll: facial.head_pose_roll,
            screen_focus_score: (typeof document !== 'undefined' && document.visibilityState === 'visible') ? 1.0 : 0.15,
            attention: Math.max(0, Math.min(1,
              (facial.gaze_frontal || 0.5) * (1 - (facial.gaze_down_score || 0) * 0.7)
              * ((facial.eyes_closed || facial.attention === 'eyes_closed') ? 0.15 : 1)
              * ((facial.attention === 'yawning' || (facial.yawn_score || 0) >= 0.48) ? 0.45 : 1)
            )),
            face_size_ratio: facial.face_size_ratio,
            distance_from_camera_m: facial.distance_from_camera_m,
            distance_source: facial.distance_source,
            luminance_grid: grid,
      };
      if (audio) {
        signal.microphone_input_level_score = audio.microphone_input_level_score;
        signal.audio_noise_level_db = audio.audio_noise_level_db;
        signal.audio_snr_db = audio.audio_snr_db;
        signal.mic_clipping_ratio = audio.mic_clipping_ratio;
        signal.noise_filter_effectiveness_score = audio.noise_filter_effectiveness_score;
      }
      const clickResult = sampleClickDetector();
      const phoneDet = detectPhoneFromGrid(grid, facial.gaze_down_score || 0);
      const handTrack = await trackHands(lastFaceContours && lastFaceContours.pts);
      // Landmark score needs face points; without them (FaceDetector-only path)
      // fall back to the luminance heuristic even when the hand model loaded.
      const handsScore = (handTrack && lastFaceContours && lastFaceContours.pts)
        ? handTrack.hands_on_face_score
        : detectHandsOnFace(grid, facial.gaze_down_score || 0, (facial.face_count || 0) > 0);
      const handBelow = (handTrack && lastFaceContours && lastFaceContours.pts)
        ? handBelowFaceFromLandmarks(lastHandContours && lastHandContours.hands, lastFaceContours.pts)
        : 0;
      // Trajectory history from face mesh landmarks only.
      if (detectorSource === 'face_mesh' && lastFaceContours && lastFaceContours.pts) {
        const pts = lastFaceContours.pts;
        const nose = pts[1], left = pts[33], right = pts[263], chin = pts[152], brow = pts[10];
        const ht = handWristTipFromContours();
        if (nose && left && right && chin && brow) {
          pushTrajectorySample({
            t: Date.now(),
            noseY: nose.y,
            browY: brow.y,
            chinY: chin.y,
            eyeMidX: (left.x + right.x) / 2,
            eyeMidY: (left.y + right.y) / 2,
            faceSize: Math.max(0.05, facial.face_size_ratio || (chin.y - brow.y)),
            pitch: facial.head_pose_pitch,
            brow: facial.brow_raise_score || 0,
            smile: facial.smile_score || 0,
            gazeFrontal: facial.gaze_frontal || 0.5,
            handWristY: ht.wristY,
            handTipY: ht.tipY,
            handWristX: ht.wristX,
          });
        }
      } else if (!usingPattern && !usingSilhouette) {
        faceLandmarkHistory = [];
      }
      const fidget = Math.max(0, Math.min(1, (motion - 0.12) * 2.4));
      const traj = computeTrajectoryFeatures({
        detector: detectorSource,
        globalMotion: motion,
        fidget,
        eyesClosed: facial.eyes_closed_score || 0,
      });
      if (traj) {
        signal.face_motion_energy = traj.face_motion_energy;
        signal.hand_gesture_energy = traj.hand_gesture_energy;
        signal.head_sag_rate = traj.head_sag_rate;
        signal.excitement_score = traj.excitement_score;
        signal.interest_score = traj.interest_score;
        signal.dozing_score = traj.dozing_score;
      }
      const phoneGridScore = Math.max(
        phoneDet.below ? (phoneDet.score || 0.7) : 0,
        phoneDet.ear ? 0.55 : 0,
      );
      const held = trajHeldObjectScore(
        phoneGridScore,
        starePhone || 0,
        handBelow,
        phoneDet.below ? 0.6 : 0,
      );
      signal.keyboard_typing_audio_score = clickResult.keyboardScore;
      signal.external_music_score = clickResult.externalMusicScore > 0.05
        ? Math.round(clickResult.externalMusicScore * 1000) / 1000 : null;
      signal.phone_visible = phoneDet.below || phoneDet.ear || clickResult.phonecall;
      signal.hands_on_face_score = handsScore > 0.05 ? Math.round(handsScore * 1000) / 1000 : null;
      signal.phone_in_hand_score = held > 0.05 && phoneGridScore >= 0.35
        ? Math.round(held * 1000) / 1000 : null;
      signal.held_object_score = held > 0.05 ? Math.round(held * 1000) / 1000 : null;
      signal.typing_activity_score = Math.max(
          Math.max(0, Math.min(1, ((facial.gaze_down_score || 0) - 0.12) * 1.9)),
          phoneDet.below ? 0.70 : 0
      );
      // Redraw before the round trip so face + hand contours keep up with the
      // video even when the POST is slow or fails.
      refreshSilhouetteGuide();
      const res = await fetch('/api/theodore/webcam/evaluate', {
        method: 'POST', headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          session_id: liveCamSessionId, mode: 'solo', persist_live_metrics: false,
          signals: [clampSignal(signal)],
        }),
      }).catch(() => null);
      if (!res || !res.ok) {
        setCamState(res ? ('evaluate ' + res.status) : 'post failed', 'bad');
        if (res) {
          const detail = await res.json().catch(() => null);
          if (detail) console.warn('evaluate rejected the frame', detail);
        }
        return;
      }
      const data = await res.json();
      const p = (data.participants || []).find((x) => x.participant_id === 'camera-local');
      if (!p) return;
      lastSilhouetteDetected = !!p.silhouette_detected;
      refreshSilhouetteGuide();
      updateFacialHud(p, facial);
      updateAudioHud(p, audio);
      updateObservatoryHud(p);
      updateIntegrityHud({
          gazeDown: facial.gaze_down_score || 0,
          gazeDownMs: p.eyes_away_for_ms || 0,
          eyesClosed: !!(facial.eyes_closed || (p.eyes_closed_for_ms > 0)),
          eyesClosedMs: p.eyes_closed_for_ms || 0,
          handsOnFaceScore: handsScore,
          handsOnFaceMs: p.hands_on_face_for_ms || 0,
          // Hold time is the source of truth; behavior_label is mutually exclusive
          // with drowsy/yawning so it can miss a confirmed hands-on-face streak.
          handsOnFaceConfirmed: (p.hands_on_face_for_ms || 0)
            >= holdSeconds('hands_on_face_min_hold_ms') * 1000,
          handCount: handTrack ? handTrack.hand_count : 0,
          phoneForMs: p.phone_visible_for_ms || 0,
          keyboardScore: clickResult.keyboardScore,
          clickRate: clickResult.clickRate || 0,
          micLevelDb: clickResult.levelDb,
          micRaw: clickResult.rawMic,
          phoneBelow: !!p.phone_visible,
          phoneEar: phoneDet.ear,
          ringtone: clickResult.ringtone,
          phonecall: clickResult.phonecall,
          suspected: !!p.suspected_cheating,
          cheatingReasons: p.cheating_reasons || [],
          musicScore: clickResult.externalMusicScore || 0,
          musicDetected: !!p.external_music_detected,
          musicForMs: p.external_music_for_ms || 0,
          heldScore: Math.max(p.held_object_score || 0, p.phone_in_hand_score || 0, held || 0),
          heldDetected: !!p.held_object_detected,
          heldForMs: p.held_object_for_ms || 0,
          excitement: p.excitement_score || (traj && traj.excitement_score) || 0,
          interest: p.interest_score || (traj && traj.interest_score) || 0,
          dozing: p.dozing_score || (traj && traj.dozing_score) || 0,
      });
      // Hands-on-face stays in telemetry + the integrity HUD only — no spoken
      // coaching. Resting a chin on a hand is normal and should not interrupt.
      if ((p.eyes_closed_for_ms || 0) >= 1500) {
        maybeAnnounceIntegrity('closed', 'I notice your eyes are closed. Please open them and look at the lesson.');
      } else if (facial && facial.owner_face_enrolled && facial.owner_face_match === false
                 && (facial.face_count || 0) > 0) {
        const who = facial.owner_face_name || faceOwnerState.displayName || 'the enrolled learner';
        maybeAnnounceIntegrity('owner',
          'A different person is in front of the camera. Teaching is paused until '
          + who + ' returns.');
      } else if ((p.yawn_for_ms || 0) >= 1500) {
        maybeAnnounceIntegrity('yawn', 'I notice you are yawning. Take a quick stretch if you need to, then refocus on the lesson.');
      } else if (p.phone_visible && (p.eyes_away_for_ms || 0) >= 2000) {
        maybeAnnounceIntegrity('phone', 'It looks like you are looking at your phone. Please return your attention to the webcam.');
      } else if ((p.behavior_label === 'distracted' || (p.distraction_score || 0) >= 0.55) && (p.eyes_away_for_ms || 0) >= 2500) {
        maybeAnnounceIntegrity('distract', 'You seem distracted. Please look back at the camera and stay with the lesson.');
      } else if ((p.inattentive_for_ms || 0) >= 4000) {
        maybeAnnounceIntegrity('inatt', 'It looks like you are not paying attention. Please refocus on the lesson.');
      } else if ((p.eyes_away_for_ms || 0) >= 2500) {
        maybeAnnounceIntegrity('away', 'Please look back at the camera so we can continue.');
      }
      if (clickResult.phonecall) maybeToastAudio('call', '📞 Phone call detected – lesson paused.');
      else if (clickResult.ringtone) maybeToastAudio('ring', '🔔 Ringtone detected.');
      lastLiveCamParticipant = p;
      updateTuningEffect(p, visionKnobs, 'Live frame scored with current Vision knobs');
      notifyLiveAway(p, facial, data);
      document.getElementById('cam-readings').innerHTML = [
        ['mood', p.dominant_expression],
        ['behavior', p.behavior_label || '—'],
        ['attention', pct(p.attention_score)],
        ['distraction', pct(p.distraction_score)],
        ['attn', (p.face_count === 0 ? 'away' : (p.eyes_away_for_ms > 0 ? 'eyes away' : 'looking'))],
        ['paused', data.training_paused ? 'yes' : 'no'],
        ['state', p.state],
        ['sharpness', num(p.sharpness_score)], ['edge', num(p.edge_density, 3)],
        ['light', pct(p.light_quality_score)], ['image', pct(p.image_detection_quality_score)],
        ['confidence', pct(p.recognition_confidence)], ['silhouette', p.silhouette_detected ? 'yes' : 'no'],
        ['faces', facial ? facial.face_count : p.face_count],
        ['Face ID', facial && facial.owner_face_enrolled
          ? ((facial.owner_face_name || faceOwnerState.displayName || 'Learner')
             + (facial.owner_face_match ? ' · locked' : ' · mismatch'))
          : 'enrolling'],
        ['distance', num(p.distance_from_camera_m)], ['engagement', pct(p.expression_behavior_score)],
        ['mic', pct(p.microphone_quality_score)], ['noise filter', pct(p.noise_filter_effectiveness_score)],
      ].map(([k, v]) => `<span class="pill">${esc(k)}: ${esc(v)}</span>`).join(' ');
      const gates = p.quality_flags || [];
      const gateEl = document.getElementById('cam-gates');
      if (gates.length) {
        gateEl.textContent = 'Failed: ' + gates.join(', ');
        gateEl.className = 'fail';
      } else {
        gateEl.textContent = 'All quality checks passed';
        gateEl.className = 'pass';
      }
    }

    function startSampling() {
      if (camTimer) clearInterval(camTimer);
      lastSilhouetteDetected = false;
      resetFaceOwner({ clearProfile: false });
      resetLiveAway(true);
      refreshSilhouetteGuide();
      camTimer = setInterval(sampleFrame, 300);
      sampleFrame();
    }

    function stopCamera() {
      if (camTimer) { clearInterval(camTimer); camTimer = null; }
      if (camStream) { camStream.getTracks().forEach((t) => t.stop()); camStream = null; }
      stopAudioMeter();
      camVideo.srcObject = null; usingPattern = false; usingSilhouette = false;
      lastSilhouetteDetected = false;
      resetFaceOwner({ clearProfile: false });
      resetLiveAway(true);
      patternCanvas.style.display = 'none'; camVideo.style.visibility = 'visible';
      clearSilhouetteOverlay();
      setCamResolutionLabel('idle · target 1920×1080 (16:9)');
      setCamState('idle');
      updateAudioHud(null, null);
    }

    async function openCameraStream() {
      const audioConstraints = [
        { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
        { echoCancellation: true, noiseSuppression: true },
        true,
      ];
      const videoAttempts = [
        // Prefer a depth-capable track when the UA exposes one (LiDAR phones / depth cams).
        { width: { ideal: CAM_IDEAL_W }, height: { ideal: CAM_IDEAL_H }, aspectRatio: { ideal: 16 / 9 },
          advanced: [{ depth: true }] },
        { width: { ideal: CAM_IDEAL_W }, height: { ideal: CAM_IDEAL_H }, aspectRatio: { ideal: 16 / 9 } },
        { width: { ideal: CAM_FALLBACK_W }, height: { ideal: CAM_FALLBACK_H }, aspectRatio: { ideal: 16 / 9 } },
        { width: CAM_FALLBACK_W, height: CAM_FALLBACK_H },
      ];
      let lastErr = null;
      for (const video of videoAttempts) {
        for (const audio of audioConstraints) {
          try {
            return await navigator.mediaDevices.getUserMedia({ video, audio });
          } catch (err) {
            lastErr = err;
          }
        }
        // Fall back to video-only if mic permission is denied.
        try {
          return await navigator.mediaDevices.getUserMedia({ video, audio: false });
        } catch (err) {
          lastErr = err;
        }
      }
      throw lastErr || new Error('getUserMedia failed');
    }

    document.getElementById('cam-start').addEventListener('click', async () => {
      stopCamera(); setCamState('requesting...');
      try {
        camStream = await openCameraStream();
      } catch (err) {
        setCamState('camera unavailable', 'bad');
        document.getElementById('cam-note').textContent = 'Use Test pattern or Silhouette demo.';
        return;
      }
      camVideo.srcObject = camStream;
      const track = camStream.getVideoTracks()[0];
      const settings = track && track.getSettings ? track.getSettings() : {};
      const rw = settings.width || camVideo.videoWidth || CAM_FALLBACK_W;
      const rh = settings.height || camVideo.videoHeight || CAM_FALLBACK_H;
      const hasMic = await startAudioMeter(camStream);
      setCamResolutionLabel(`${rw}×${rh} · 16:9 webcam` + (hasMic ? ' · mic on' : ' · mic off'));
      setCamState('live', 'good');
      document.getElementById('cam-note').textContent =
        (hasMic
          ? 'HD 16:9 + mic. Noise filter uses browser noiseSuppression + live SNR. '
          : 'HD 16:9 preview (no mic). Allow microphone to score noise filter. ')
        + 'The outline is only a framing guide — behavior uses the full camera frame.';
      startSampling();
    });
    document.getElementById('cam-pattern').addEventListener('click', () => {
      stopCamera(); usingPattern = true; patternPhase = 0;
      setCamState('test pattern', 'good');
      setCamResolutionLabel(`${CAM_FALLBACK_W}×${CAM_FALLBACK_H} · test pattern`);
      document.getElementById('cam-note').textContent =
        'No camera needed. Sweeps sharp → blurred → low contrast → under/over exposed '
        + '(~2s each) so you can watch Live gates trip and clear. Drag a sharpness or '
        + 'lighting slider to move the point where each stage fails.';
      startSampling();
    });
    document.getElementById('cam-silhouette').addEventListener('click', () => {
      stopCamera(); usingSilhouette = true; setCamState('silhouette demo', 'good');
      setCamResolutionLabel(`${CAM_FALLBACK_W}×${CAM_FALLBACK_H} · silhouette demo`);
      document.getElementById('cam-note').textContent =
        'Filled person, no face — should trip silhouette detection after a few frames.';
      startSampling();
    });
    document.getElementById('cam-stop').addEventListener('click', stopCamera);
    document.getElementById('face-id-enroll')?.addEventListener('click', () => {
      enrollFaceIdNow();
    });
    document.getElementById('face-id-clear')?.addEventListener('click', () => {
      clearFaceIdProfile();
      toast('Face ID cleared.');
    });
    document.getElementById('face-id-name')?.addEventListener('change', () => {
      const nameEl = document.getElementById('face-id-name');
      const name = ((nameEl && nameEl.value) || '').trim();
      if (!name) return;
      faceOwnerState.displayName = name;
      if (faceOwnerState.enrolled) saveFaceIdProfile();
      updateFaceIdUi();
    });
    resetFaceOwner({ clearProfile: false });
    document.getElementById('class-gate-run')?.addEventListener('click', () => {
      const grid = luminanceGrid();
      const out = document.getElementById('class-gate-result');
      if (!out) return;
      if (!grid) {
        out.textContent = 'blocked_no_face — start the camera or a Test pattern first.';
        return;
      }
      const night = !!document.getElementById('class-gate-night')?.checked;
      // Mirror apps/web cameraLighting DEFAULT / NIGHT_VISION thresholds.
      const t = night
        ? { under: 0.08, over: 0.82, maxBlack: 0.45, maxWhite: 0.12, minLight: 0.12, minSharp: 0.12, minEdge: 0.008 }
        : { under: 0.22, over: 0.82, maxBlack: 0.18, maxWhite: 0.12, minLight: 0.35, minSharp: 0.30, minEdge: 0.035 };
      const flat = grid.flat();
      const mean = flat.reduce((a, b) => a + b, 0) / flat.length;
      const underRatio = flat.filter((v) => v <= t.under).length / flat.length;
      const overRatio = flat.filter((v) => v >= t.over).length / flat.length;
      const underexposed = mean <= t.under || underRatio > t.maxBlack;
      const overexposed = mean >= t.over || overRatio > t.maxWhite;
      // Coarse sharpness: neighbour absolute diffs (lab already has server Sobel).
      let edge = 0, n = 0;
      for (let y = 1; y < grid.length - 1; y++) {
        for (let x = 1; x < grid[0].length - 1; x++) {
          const g = Math.abs(grid[y][x] - grid[y][x - 1]) + Math.abs(grid[y][x] - grid[y - 1][x]);
          if (g > 0.12) edge += 1;
          n += 1;
        }
      }
      const edgeDensity = n ? edge / n : 0;
      const blurry = edgeDensity < t.minEdge;
      const mid = grid.slice(8, 28).flatMap((row) => row.slice(16, 48));
      const mMean = mid.reduce((a, b) => a + b, 0) / Math.max(1, mid.length);
      const mVar = mid.reduce((a, b) => a + (b - mMean) ** 2, 0) / Math.max(1, mid.length);
      const face = usingPattern ? false : (mVar > 0.004 && mMean > 0.08 && mMean < 0.92);
      let verdict = 'ready';
      if (!face && !usingPattern) verdict = 'blocked_no_face';
      else if (usingPattern && (underexposed || overexposed || blurry)) {
        verdict = underexposed ? 'blocked_dark' : (overexposed ? 'blocked_bright' : 'blocked_blurry');
      } else if (underexposed && !night) verdict = 'blocked_dark';
      else if (overexposed) verdict = 'blocked_bright';
      else if (blurry && !night) verdict = 'blocked_blurry';
      else if (night) verdict = 'ready';
      out.textContent = `${verdict} · mean=${mean.toFixed(2)} · edges=${edgeDensity.toFixed(3)} · face=${face ? 'yes' : 'no'}${night ? ' · night vision' : ''}`;
      toast('Class lighting gate: ' + verdict);
    });
    if (silToggle) {
      silToggle.addEventListener('click', (ev) => {
        ev.preventDefault();
        silhouetteGuideOn = !silhouetteGuideOn;
        syncSilhouetteToggleUi();
        refreshSilhouetteGuide();
      });
      syncSilhouetteToggleUi();
    }
    const tiltNeutralBtn = document.getElementById('tilt-set-neutral');
    if (tiltNeutralBtn) {
      tiltNeutralBtn.addEventListener('click', () => {
        if (tiltRawDeg == null) { toast('No face detected yet — start the camera first.'); return; }
        tiltNeutralDeg = tiltRawDeg;
        tiltNeutralAuto = false;
        tiltNeutralSamples = [];
        resetTiltPeaks();
        saveTiltCalibration();
        toast('Neutral set at raw pitch ' + tiltDeg(tiltNeutralDeg) + '. Tilt is now measured from here.');
      });
    }
    const tiltDownBtn = document.getElementById('tilt-set-down');
    if (tiltDownBtn) {
      tiltDownBtn.addEventListener('click', () => {
        if (tiltRawDeg == null) { toast('No face detected yet — start the camera first.'); return; }
        if (tiltNeutralDeg == null) { toast('Set neutral first, then look down and press this.'); return; }
        const delta = tiltRawDeg - tiltNeutralDeg;
        if (Math.abs(delta) < 3) {
          toast('That reads the same as neutral — tilt further down and press again.');
          return;
        }
        tiltDownSign = delta > 0 ? 1 : -1;
        tiltSignCalibrated = true;
        resetTiltPeaks();
        saveTiltCalibration();
        toast('Down direction locked. That pose reads ' + tiltDeg(Math.abs(delta)) + ' below neutral.');
      });
    }
    const tiltResetBtn = document.getElementById('tilt-reset-peak');
    if (tiltResetBtn) tiltResetBtn.addEventListener('click', resetTiltPeaks);
    const tiltTripInput = document.getElementById('tilt-trip');
    if (tiltTripInput) {
      tiltTripInput.addEventListener('input', () => {
        const v = Number(tiltTripInput.value);
        if (Number.isFinite(v) && v > 0) {
          tiltTripDeg = v;
          saveTiltCalibration();
          renderTiltLab();
          refreshSilhouetteGuide();
        }
      });
    }
    const stareLayoutSelect = document.getElementById('stare-layout');
    const stareYScreenInput = document.getElementById('stare-yscreen');
    if (stareLayoutSelect) {
      stareLayoutSelect.addEventListener('change', () => {
        const preset = STARE_LAYOUTS[stareLayoutSelect.value];
        if (!preset) return;
        stareLayoutKey = stareLayoutSelect.value;
        stareYScreenM = preset.yScreen;
        if (stareYScreenInput) stareYScreenInput.value = stareYScreenM.toFixed(2);
        saveTiltCalibration();
        recomputeStare();
      });
    }
    if (stareYScreenInput) {
      stareYScreenInput.addEventListener('input', () => {
        const v = Number(stareYScreenInput.value);
        if (!Number.isFinite(v) || v <= 0) return;
        stareYScreenM = v;
        saveTiltCalibration();
        recomputeStare();
      });
    }
    loadTiltCalibration();
    if (tiltTripInput) tiltTripInput.value = String(tiltTripDeg);
    if (stareLayoutSelect) stareLayoutSelect.value = stareLayoutKey;
    if (stareYScreenInput) stareYScreenInput.value = stareYScreenM.toFixed(2);
    renderTiltLab();

    if (window.ResizeObserver) {
      new ResizeObserver(() => {
        if (camTimer) refreshSilhouetteGuide();
      }).observe(camFrame);
    }
    setCamResolutionLabel('idle · target 1920×1080 (16:9)');

    loadTuning();
    loadVoiceLanguages();
    refresh();
    metricsRefreshTimer = setInterval(refresh, 1000);

"""
    .replace("__VISION_GROUPS__", _js_knob_groups(VISION_KNOB_GROUPS))
    .replace("__VOICE_GROUPS__", _js_knob_groups(VOICE_KNOB_GROUPS))
    .replace("__POLICY_KNOBS__", _js_knob_groups(POLICY_KNOBS))
    .replace("__ABSENCE_PHRASES__", _js_absence_phrases())
)

MONITOR_PAGE_TEMPLATE = (
    """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Theodore Live Monitor - __SESSION_TITLE__</title>
  <link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='7' fill='%230f172a'/%3E%3Ccircle cx='16' cy='16' r='8' fill='none' stroke='%2367e8f9' stroke-width='2.5'/%3E%3Ccircle cx='16' cy='16' r='3' fill='%2367e8f9'/%3E%3C/svg%3E" />
  <style>"""
    + MONITOR_CSS
    + """</style>
</head>
<body>
  <div style="display:flex;align-items:center;justify-content:space-between;padding:5px 12px;background:#0b1220;border-bottom:1px solid #334155;position:sticky;top:0;z-index:50;">
    <span style="font-size:11px;color:#94a3b8;">Theodore Lab &rsaquo; <strong style="color:#e2e8f0;">__SESSION_TITLE__</strong></span>
    <button id="shutdown-btn" type="button" style="background:#7f1d1d;border-color:#b91c1c;color:#fca5a5;font-size:11px;" title="Stop the server and free the port">&#x2715;&nbsp;Shut down server</button>
  </div>
  <div class="layout">
    <div class="panel">
      <h2>Session __SESSION_TITLE__</h2>
      <div class="tuning-help" style="margin-top:0;">
        Your physical webcam is one solo learner (Camera panel below).
        Demo buttons inject <em>simulated</em> frames — solo = 1 student, group = 3 students
        (healthy / cheating / silhouette) for the dashboard, not three cameras.
      </div>
      <div id="state"></div>
      <div class="summary-grid" id="summary"></div>
      <div class="camrow" style="margin-top:8px;">
        <button id="demo-seed" class="primary" type="button" title="One simulated learner — matches a single webcam">Load solo demo (1 student)</button>
        <button id="demo-seed-group" type="button" title="Three simulated students for group monitoring features">Load group demo (3 students)</button>
        <button id="demo-roll" type="button">Start live feed</button>
        <button id="demo-stop" type="button">Stop feed</button>
        <label class="check"><input id="demo-scenario-group" type="checkbox" /> Roll as group (3)</label>
        <label class="check"><input id="demo-degraded" type="checkbox" /> Degraded room</label>
        <label class="check">Interval <input id="demo-interval" type="number" min="0.2" max="5" step="0.2" value="1" style="width:48px;" />s</label>
      </div>
    </div>
    <div class="panel">
      <h2>Lesson Alerts</h2>
      <ul class="alerts" id="alerts"></ul>
      <h3>Action log</h3>
      <div class="log" id="action-log">No actions yet.</div>
      <h3>Private messages</h3>
      <div class="log" id="private-msgs">No private messages.</div>
    </div>
  </div>
  <div id="cheat-banner" class="banner" style="display:none;"></div>

  <div class="stage">
    <div class="panel">
      <h2>Camera</h2>
      <div class="cam-frame">
        <video id="cam" autoplay muted playsinline></video>
        <canvas id="pattern-canvas"></canvas>
        <canvas id="cam-overlay"></canvas>
        <div id="cam-res" class="cam-res">idle · target 1920×1080 (16:9)</div>
        <div id="cam-pause-overlay" class="cam-pause-overlay" aria-live="assertive">
          <div class="pause-title">PAUSED</div>
          <div class="pause-sub" id="cam-pause-sub">Away from webcam — return to continue.</div>
        </div>
        <button type="button" id="cam-contour-toggle" class="cam-sil-toggle cam-contour-toggle on"
                aria-pressed="true" title="Show facial contour lines used for mood tracking">
          <span class="sw" aria-hidden="true"></span>
          <span id="cam-contour-toggle-label">Contours on</span>
        </button>
        <button type="button" id="cam-sil-toggle" class="cam-sil-toggle on"
                aria-pressed="true"
                title="Optional framing guide. You do not need to fit inside it — the full frame is scanned for behavior.">
          <span class="sw" aria-hidden="true"></span>
          <span id="cam-sil-toggle-label">Guide on</span>
        </button>
      </div>
      <canvas id="grab" style="display:none;"></canvas>
      <div class="camrow">
        <button id="cam-start" type="button">Start camera</button>
        <button id="cam-stop" type="button">Stop</button>
        <button id="cam-pattern" type="button">Test pattern</button>
        <button id="cam-silhouette" type="button">Silhouette demo</button>
        <span class="pill" id="cam-state">idle</span>
        <span class="pill warn" id="cam-detector"
              title="Which detector is producing the numbers below.">detector: loading face mesh…</span>
      </div>
      <div class="camrow" id="cam-readings"></div>
      <div class="face-id-panel" id="face-id-panel">
        <h4>Face ID (named profile)</h4>
        <div class="face-id-row">
          <input type="text" id="face-id-name" maxlength="80" placeholder="Learner name"
                 autocomplete="name" aria-label="Face ID display name" />
          <button type="button" id="face-id-enroll"
                  title="Overwrite Face ID with the person currently in view">Enroll now</button>
          <button type="button" id="face-id-clear"
                  title="Clear Face ID so the next person can enroll">Clear</button>
        </div>
        <div class="face-id-status warn" id="face-id-status">
          No Face ID yet — start the camera; the first stable person enrolls after ~1.5s.
        </div>
      </div>
      <div class="tilt-lab" id="tilt-lab">
        <h4>Stare geometry lab</h4>
        <div class="tilt-row">
          <span class="tilt-chip" id="tilt-down">down —</span>
          <span class="tilt-chip" id="tilt-raw">raw pitch —</span>
          <span class="tilt-chip" id="tilt-gaze">gaze_down —</span>
          <span class="tilt-chip" id="tilt-verdict">no face yet</span>
        </div>
        <div class="tilt-row">
          <span class="tilt-chip" id="stare-distance">D —</span>
          <span class="tilt-chip" id="stare-expected">θ_screen —</span>
          <span class="tilt-chip" id="stare-residual">residual —</span>
          <span class="tilt-chip" id="stare-scores">match — · phone-stare —</span>
        </div>
        <div class="tilt-row">
          <label class="tilt-hint" for="stare-layout">Device layout</label>
          <select id="stare-layout">
            <option value="laptop_14">14" laptop</option>
            <option value="laptop_16" selected>16" laptop</option>
            <option value="external_monitor_webcam_top">Monitor, webcam on top</option>
          </select>
          <label class="tilt-hint" for="stare-yscreen">y_screen (m)</label>
          <input type="number" id="stare-yscreen" min="0.02" max="0.60" step="0.01" value="0.18">
          <span class="tilt-hint">webcam → middle of the lesson band. Edit until looking
            at mid-screen reads residual ≈ 0 for your seat.</span>
        </div>
        <div class="tilt-row">
          <span class="tilt-chip" id="tilt-peak">peak down — / up —</span>
          <button type="button" id="tilt-set-neutral">Set neutral (look at screen)</button>
          <button type="button" id="tilt-set-down">Set down (look at phone)</button>
          <button type="button" id="tilt-reset-peak">Reset peaks</button>
        </div>
        <div class="tilt-row">
          <label class="tilt-hint" for="tilt-trip">Trip line</label>
          <input type="number" id="tilt-trip" min="1" max="80" step="1" value="20">
          <span class="tilt-hint">degrees below neutral — nothing is enforced yet, this only
            marks the line on the gauge so you can see which trials would fall past it.</span>
        </div>
        <div class="tilt-hint" id="tilt-hint">
          The gauge self-starts: after about a second of tracking it takes the pose
          you are holding as neutral, so tilt is measured from where you actually
          sit rather than from level. Sit normally and press <strong>Set neutral</strong>
          to pin it yourself. The indigo <strong>screen</strong> band on the gauge is
          the angle this seat needs to see mid-screen — θ_screen = atan(y_screen / D)
          — so a needle inside the band is watching the lesson and a needle well
          below it is a stare the screen does not explain (that is the residual).
          <strong>Peak</strong> records the furthest tilt of a trial, so you can
          compare a phone glance against a mid-screen glance. Nothing here enforces
          anything yet; it is a measuring instrument.
        </div>
      </div>
      <div class="facial-hud" id="facial-hud">
        <div class="facial-card mood-unknown" id="facial-mood-card">
          <div class="lbl">Mood</div>
          <div class="val" id="facial-mood">—</div>
          <div class="sub" id="facial-mood-sub">facial contour lines track smile / frown</div>
        </div>
        <div class="facial-card attn-looking" id="facial-attn-card">
          <div class="lbl">Attention</div>
          <div class="val" id="facial-attn">—</div>
          <div class="sub" id="facial-attn-sub">looking · eyes away · yawn · left frame</div>
        </div>
        <div class="facial-card beh-focused" id="facial-beh-card">
          <div class="lbl">Behavior</div>
          <div class="val" id="facial-beh">—</div>
          <div class="sub" id="facial-beh-sub">focused · yawning · distracted · not paying attention</div>
        </div>
        <div class="facial-card dist-none" id="facial-dist-card">
          <div class="lbl">Distance</div>
          <div class="val" id="facial-dist">n/a</div>
          <div class="sub" id="facial-dist-sub">LiDAR if available · else face size</div>
        </div>
      </div>
      <div class="audio-hud" id="audio-hud">
        <div class="facial-card" id="audio-mic-card">
          <div class="lbl">Mic quality</div>
          <div class="val" id="audio-mic">n/a</div>
          <div class="sub" id="audio-mic-sub">enable mic with Start camera</div>
        </div>
        <div class="facial-card" id="audio-noise-card">
          <div class="lbl">Noise filter</div>
          <div class="val" id="audio-noise">n/a</div>
          <div class="sub" id="audio-noise-sub">browser noise suppression + SNR</div>
        </div>
      </div>
      <div class="integrity-hud">
        <div class="integrity-card alert-low" id="integrity-gaze">
          <div class="lbl">Looking down</div>
          <div class="val" id="integrity-gaze-val">—</div>
        </div>
        <div class="integrity-card alert-low" id="integrity-eyes">
          <div class="lbl">Eyes</div>
          <div class="val" id="integrity-eyes-val">open</div>
        </div>
        <div class="integrity-card alert-low" id="integrity-keyboard">
          <div class="lbl">Keyboard audio</div>
          <div class="val" id="integrity-keyboard-val">—</div>
        </div>
        <div class="integrity-card alert-low" id="integrity-device">
          <div class="lbl">Phone in frame</div>
          <div class="val" id="integrity-device-val">—</div>
        </div>
        <div class="integrity-card alert-low" id="integrity-hands">
          <div class="lbl">Hands on face</div>
          <div class="val" id="integrity-hands-val">—</div>
        </div>
        <div class="integrity-card alert-low" id="integrity-call">
          <div class="lbl">Phone / ringtone</div>
          <div class="val" id="integrity-call-val">—</div>
        </div>
        <div class="integrity-card alert-low" id="integrity-music">
          <div class="lbl">Outside music</div>
          <div class="val" id="integrity-music-val">—</div>
        </div>
        <div class="integrity-card alert-low" id="integrity-held">
          <div class="lbl">Held object</div>
          <div class="val" id="integrity-held-val">—</div>
        </div>
        <div class="integrity-card alert-low" id="integrity-traj">
          <div class="lbl">Trajectory</div>
          <div class="val" id="integrity-traj-val">—</div>
        </div>
      </div>
      <div class="integrity-status" id="integrity-status">Start camera to monitor yawn, distraction, gaze, closed eyes, hands on face, phone use, outside music, and held objects.</div>
      <div class="card" style="margin-top:10px;padding:10px">
        <h3 style="margin:0 0 6px">Class lighting gate</h3>
        <p class="muted" style="margin:0 0 8px;font-size:12px">
          Same pre-class Camera and lighting check used on web/mobile. Score the
          live camera (or Test pattern exposure stages) before a lesson would start.
        </p>
        <label style="font-size:12px;display:flex;gap:6px;align-items:center;margin-bottom:8px">
          <input type="checkbox" id="class-gate-night" /> Night vision
        </label>
        <button type="button" id="class-gate-run">Simulate class gate</button>
        <div id="class-gate-result" class="muted" style="margin-top:8px;font-size:12px">Not run yet</div>
      </div>
      <div class="obs-panel" id="obs-panel">
        <h3>Behavior Observatory</h3>
        <div class="obs-top">
          <div class="obs-labels">
            <div class="big" id="obs-label">—</div>
            <div class="sub">cognitive: <span id="obs-cognitive">—</span> · <span id="obs-confidence"></span></div>
            <div class="sub" id="obs-hint">Start camera for live cognitive fusion</div>
            <div class="sub" id="obs-pose">pose n/a</div>
          </div>
          <div class="obs-pose-box" title="Head pose compass (yaw/pitch)">
            <div class="obs-pose-needle" id="obs-pose-needle"></div>
          </div>
        </div>
        <div class="obs-bars">
          <div class="obs-bar-row"><span>Engage</span><div class="obs-track"><div class="obs-fill" id="obs-eng"></div></div></div>
          <div class="obs-bar-row"><span>Flow</span><div class="obs-track"><div class="obs-fill" id="obs-flow"></div></div></div>
          <div class="obs-bar-row" style="display:none" aria-hidden="true"><span>Confused</span><div class="obs-track"><div class="obs-fill warn" id="obs-conf"></div></div></div>
          <div class="obs-bar-row"><span>Bored</span><div class="obs-track"><div class="obs-fill warn" id="obs-bore"></div></div></div>
          <div class="obs-bar-row"><span>Fatigue</span><div class="obs-track"><div class="obs-fill bad" id="obs-fat"></div></div></div>
          <div class="obs-bar-row"><span>Curious</span><div class="obs-track"><div class="obs-fill" id="obs-cur"></div></div></div>
          <div class="obs-bar-row"><span>Fidget</span><div class="obs-track"><div class="obs-fill warn" id="obs-fid"></div></div></div>
          <div class="obs-bar-row"><span>Multitask</span><div class="obs-track"><div class="obs-fill bad" id="obs-multi"></div></div></div>
          <div class="obs-bar-row"><span>Excited</span><div class="obs-track"><div class="obs-fill" id="obs-exc"></div></div></div>
          <div class="obs-bar-row"><span>Interest</span><div class="obs-track"><div class="obs-fill" id="obs-int"></div></div></div>
          <div class="obs-bar-row"><span>Dozing</span><div class="obs-track"><div class="obs-fill bad" id="obs-doz"></div></div></div>
        </div>
        <div class="obs-events" id="obs-events">No behavior events yet.</div>
      </div>
      <div class="gatesblock">
        <div class="gateslabel">Camera quality checks</div>
        <div id="cam-gates">Waiting for camera…</div>
        <div class="gateshelp">
          This is a pass/fail checklist for the current frame (lighting, blur, distance,
          detection quality). Green text means every check passed — it is not a score line
          and not related to mood or cheating. If something fails, the failing check names
          appear in red (for example lighting_underexposed or image_blurry).
        </div>
      </div>
      <div class="kv"><span id="cam-note" style="font-size:10px;color:#94a3b8;"></span></div>
    </div>

    <div class="panel">
      <h2>Tuning</h2>
      <div class="tabs">
        <button id="tab-vision" class="active" type="button">Vision (all knobs)</button>
        <button id="tab-voice" type="button">Voice</button>
        <button id="tab-policy" type="button">Timing policy</button>
      </div>
      <div class="kv" id="preset-wrap">
        <span>Preset</span>
        <span>
          <select id="preset" title="Applies immediately when you change it"></select>
          <span class="pill good" style="font-size:10px;">live</span>
        </span>
      </div>
      <div id="tuning-status" class="statusline"></div>
      <div class="tuning-help">
        Vision knobs change how the <strong>server scores</strong> your webcam
        (pass/fail thresholds for light, blur, distance, mic). They do
        <strong>not</strong> change the video picture. Start the camera, then
        drag a slider or pick a preset — watch <em>Camera quality checks</em> and
        <em>Tuning → live webcam</em> flip when a threshold is crossed.
      </div>
      <div class="camrow">
        <button id="tuning-prove" class="primary" type="button" title="Temporarily tighten light/image gates so you can see FAIL, then restore">
          Prove knobs work
        </button>
      </div>
      <div id="tuning-effect" class="tuning-effect">
        <h3>Tuning → live webcam</h3>
        <div>Start the camera, then drag a slider or pick a preset — no Apply needed.</div>
      </div>
      <div class="knobscroll" id="knobs"></div>
      <div class="gatesblock">
        <div class="gateslabel">Failed quality checks (whole class)</div>
        <div id="gatecounts">-</div>
        <div class="gateshelp">Counts of students currently failing a quality check. “none” means nobody is failing those lighting/blur/distance gates.</div>
      </div>
    </div>

    <div class="panel" id="voice-panel">
      <h2>xAI Theodore voice agent</h2>
      <div id="voice-status" class="voice-status fallback">Loading voice status…</div>
      <div class="camrow" style="align-items:center;gap:6px;">
        <label class="check" for="voice-lang">Language</label>
        <select id="voice-lang" title="Teaching language for xAI replies + spoken pronunciation"
                style="font-size:11px;background:#1f2937;color:#e2e8f0;border:1px solid #334155;border-radius:4px;padding:2px 4px;min-width:9rem;"></select>
        <input id="voice-topic" type="text" value="fractions" placeholder="question topic" style="flex:1;" />
        <button id="voice-ask" type="button">Ask question</button>
      </div>
      <textarea id="voice-msg">Can you explain that again more slowly?</textarea>
      <div class="camrow">
        <button id="voice-reply" class="primary" type="button">Get reply</button>
        <button id="voice-absorb" type="button" title="Score a spoken/typed answer transcript">Absorb answer</button>
        <label class="check"><input id="voice-autospeak" type="checkbox" checked /> Auto-speak</label>
      </div>
      <div class="log" id="voice-out">Voice output appears here.</div>
      <div class="camrow" style="margin-top:4px;">
        <button id="voice-speak" type="button">&#x1F50A; Speak again</button>
        <button id="voice-stop-speak" type="button">&#x23F9; Stop</button>
      </div>
      <div class="tuning-help">xAI writes the reply; spoken audio uses your device voice matched to the selected language (ElevenLabs/edge-tts when a speech gateway is configured).</div>
    </div>
  </div>

  <div class="tools">
    <div class="panel">
      <h2>Webcam games</h2>
      <textarea id="game-prompt">Stay focused while we check integrity.</textarea>
      <div class="camrow">
        <button id="game-issue" class="primary" type="button">Issue challenge</button>
        <button id="game-attempt" type="button">Score focused attempt</button>
      </div>
      <div class="log" id="game-status">No active challenge.</div>
    </div>
    <div class="panel">
      <h2>Student Windows</h2>
      <p style="font-size:11px;color:#94a3b8;margin:0;">Full windows render below. Charts include light, image, mic, behavior, distance, noise.</p>
    </div>
  </div>

  <div class="panel" style="margin:0 12px 12px 12px;">
    <h2>Student Windows (Live Metrics)</h2>
    <div class="windows" id="windows"></div>
  </div>
  <div id="theodore-action" class="theodore-action" role="dialog" aria-modal="true"
       aria-labelledby="theodore-action-title" aria-hidden="true">
    <div class="theodore-action-card">
      <div class="theodore-avatar-wrap" aria-hidden="true">
        <div class="theodore-avatar">
          <div class="theodore-crown"></div>
          <div class="theodore-eye left"></div>
          <div class="theodore-eye right"></div>
          <div class="theodore-nose"></div>
          <div class="theodore-mouth"></div>
          <div class="theodore-medallion">S</div>
        </div>
        <div id="theodore-action-icon" class="theodore-action-icon">✨</div>
      </div>
      <div class="theodore-action-copy">
        <div class="theodore-action-kicker">Theodore is taking action</div>
        <h2 id="theodore-action-title" class="theodore-action-title">Theodore takes action</h2>
        <div id="theodore-action-body" class="theodore-action-body"></div>
        <div id="theodore-action-speech" class="theodore-speech" aria-live="assertive"></div>
        <div class="theodore-action-controls">
          <button id="theodore-action-speak" class="speak" type="button">🔊 Say it again</button>
          <button id="theodore-action-close" type="button">Continue lesson</button>
        </div>
      </div>
    </div>
  </div>
  <div id="toast" class="toast" role="status"></div>
  <script>"""
    + MONITOR_JS
    + """</script>
</body>
</html>"""
)

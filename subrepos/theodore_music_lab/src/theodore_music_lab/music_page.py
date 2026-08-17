"""Embedded Music Lab player.

Featured MP3s with a karaoke bouncing ball, word-level highlighting, a
per-line translation always visible in any of the 26+ languages, an Ask-AI box
that works while the track plays, short lyric clips, and curated lyric videos.
"""

from __future__ import annotations

from urllib.parse import quote

# A quaver on the lab's night-blue tile. It is inlined in the page head so a
# browser never falls back to requesting /favicon.ico, and served at that path
# too for the pages that are pure JSON (/health, /docs).
FAVICON_SVG = (
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'>"
    "<rect width='32' height='32' rx='7' fill='#0f172a'/>"
    "<path d='M13 7v13.2a3.6 3.6 0 1 0 2 3.2V11l7-2V6z' fill='#fbbf24'/>"
    "</svg>"
)
_FAVICON_DATA_URI = "data:image/svg+xml," + quote(FAVICON_SVG, safe="")


def render_music_page() -> str:
    return (
        "<!doctype html>\n<html lang=\"en\">\n<head>\n"
        "  <meta charset=\"utf-8\" />\n"
        "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />\n"
        "  <title>Theodore Music Lab</title>\n"
        # Without a declared icon a browser requests /favicon.ico and logs a 404.
        "  <link rel=\"icon\" href=\"" + _FAVICON_DATA_URI + "\" />\n"
        "  <style>\n"
        + _CSS
        + "\n  </style>\n</head>\n<body>\n"
        + _HTML
        + "\n  <script>\n"
        + _JS
        + "\n  </script>\n</body>\n</html>\n"
    )


_CSS = """
  :root { --bg:#0f172a; --panel:#1e293b; --ink:#f8fafc; --muted:#94a3b8; --accent:#38bdf8;
          --warm:#fbbf24; --good:#34d399; }
  * { box-sizing:border-box; }
  body { margin:0; min-height:100vh; color:var(--ink); font-family:"Trebuchet MS","Segoe UI",sans-serif;
    background: radial-gradient(1200px 600px at 10% -10%, #1d4ed6 0%, transparent 55%),
                radial-gradient(900px 500px at 100% 0%, #0ea5e9 0%, transparent 50%), var(--bg); }
  header { padding:1.25rem 1.5rem .5rem; }
  header h1 { margin:0; font-size:1.75rem; }
  header p { margin:.35rem 0 0; color:var(--muted); max-width:46rem; }
  .layout { display:grid; gap:1rem; padding:1rem 1.5rem 2rem; grid-template-columns:minmax(230px,290px) 1fr; }
  .layout > .stack { display:grid; gap:1rem; align-content:start; }
  .bottom { display:grid; gap:1rem; grid-template-columns:1fr 1fr 1fr; }
  @media (max-width:980px){ .layout { grid-template-columns:1fr; } .bottom { grid-template-columns:1fr; } }
  .panel { background:color-mix(in srgb, var(--panel) 92%, black); border:1px solid #334155;
    border-radius:18px; padding:1rem; }
  .panel h2 { margin:0 0 .75rem; font-size:1rem; color:var(--accent); }
  .song-card { display:block; width:100%; text-align:left; margin:0 0 .55rem; padding:.75rem .85rem;
    border-radius:12px; cursor:pointer; background:#0f172a; border:1px solid #334155; color:var(--ink); }
  .song-card.active { border-color:var(--accent); box-shadow:0 0 0 1px var(--accent); }
  .song-card strong { display:block; }
  .song-card span { color:var(--muted); font-size:.8rem; }
  /* ---------- storyboard stage ---------- */
  .stage { position:relative; overflow:hidden; border-radius:18px; aspect-ratio:16/9;
    min-height:300px; background:linear-gradient(160deg,#0c4a6e,#1e293b 55%,#0f172a);
    border:1px solid #334155; }
  .stage.theater { position:fixed; inset:0; z-index:60; width:100vw; height:100vh;
    aspect-ratio:auto; border-radius:0; border:0; }
  body.theater-on { overflow:hidden; }
  .camera { position:absolute; inset:-5%; will-change:transform; }
  .backdrop, .backdrop svg, .cast { position:absolute; inset:0; width:100%; height:100%; }
  .backdrop svg { display:block; }
  .sprite { position:absolute; height:calc(var(--h,20) * var(--s,1) * 1%);
    transform:translate(-50%,-100%); }
  .sprite-motion, .sprite-fit, .sprite svg { height:100%; width:auto; }
  .sprite-motion { display:block; }
  .stage:not(.playing) .camera, .stage:not(.playing) .cast *,
  .stage:not(.playing) .backdrop * { animation-play-state:paused; }
  /* camera moves */
  .cam-push-in { animation:camPushIn var(--cam-dur,10s) ease-in-out both; }
  .cam-pull-out { animation:camPullOut var(--cam-dur,10s) ease-in-out both; }
  .cam-pan-right { animation:camPanRight var(--cam-dur,10s) linear both; }
  .cam-pan-left { animation:camPanLeft var(--cam-dur,10s) linear both; }
  .cam-ken-burns { animation:camKenBurns var(--cam-dur,10s) ease-in-out both; }
  .cam-zoom-punch { animation:camZoomPunch var(--cam-dur,10s) ease-in-out both; }
  .cam-tilt-up { animation:camTiltUp var(--cam-dur,10s) ease-in-out both; }
  .cam-dolly-shake { animation:camDollyShake var(--cam-dur,10s) ease-in-out both; }
  @keyframes camPushIn { from{transform:scale(1.02)} to{transform:scale(1.24)} }
  @keyframes camPullOut { from{transform:scale(1.26)} to{transform:scale(1.02)} }
  @keyframes camPanRight { from{transform:scale(1.16) translateX(-3.5%)}
    to{transform:scale(1.16) translateX(3.5%)} }
  @keyframes camPanLeft { from{transform:scale(1.16) translateX(3.5%)}
    to{transform:scale(1.16) translateX(-3.5%)} }
  @keyframes camKenBurns { from{transform:scale(1.06) translate(-1.5%,1.5%)}
    to{transform:scale(1.2) translate(1.5%,-1.5%)} }
  @keyframes camZoomPunch { 0%{transform:scale(1.04)} 22%{transform:scale(1.2)}
    46%{transform:scale(1.07)} 70%{transform:scale(1.22)} 100%{transform:scale(1.1)} }
  @keyframes camTiltUp { from{transform:scale(1.18) translateY(4.5%)}
    to{transform:scale(1.18) translateY(-4.5%)} }
  @keyframes camDollyShake { 0%{transform:scale(1.1) translate(0,0)}
    25%{transform:scale(1.13) translate(-.8%,.5%)} 50%{transform:scale(1.16) translate(.8%,-.4%)}
    75%{transform:scale(1.13) translate(-.5%,-.6%)} 100%{transform:scale(1.18) translate(0,0)} }
  /* character + prop motion */
  .m-bob { animation:mBob 2.2s ease-in-out infinite; }
  .m-float { animation:mFloat 5s ease-in-out infinite; }
  .m-hop { animation:mHop 1.1s ease-in-out infinite; }
  .m-sway { animation:mSway 3.4s ease-in-out infinite; }
  .m-walk { animation:mBob 1s ease-in-out infinite; }
  .m-drive { animation:mDrive 2.6s ease-in-out infinite; }
  .m-turn { animation:mTurn 3.2s ease-in-out infinite; }
  .m-cross-right { animation:mCrossRight 9s linear infinite; }
  .m-cross-left { animation:mCrossLeft 9s linear infinite; }
  .m-shine .figure { animation:mSpinSlow 22s linear infinite; transform-box:fill-box;
    transform-origin:center; }
  .m-wave .arm-r { animation:armWave .9s ease-in-out infinite; }
  .m-point-up .arm-r { animation:armPointUp 2.4s ease-in-out infinite; }
  .m-point-down .arm-r { animation:armPointDown 2.4s ease-in-out infinite; }
  .m-walk .leg-l, .m-walk .leg-r { animation:legSwing .8s ease-in-out infinite; }
  .m-walk .leg-r { animation-delay:-.4s; }
  .m-walk .arm-l, .m-walk .arm-r { animation:armSwing .8s ease-in-out infinite; }
  .m-walk .arm-r { animation-delay:-.4s; }
  .sprite .arm-l, .sprite .arm-r, .sprite .leg-l, .sprite .leg-r, .sprite .tail,
  .sprite .wheel, .sprite .door, .sprite .crown, .sprite .figure {
    transform-box:fill-box; }
  .sprite .arm-l, .sprite .arm-r, .sprite .leg-l, .sprite .leg-r { transform-origin:top center; }
  .sprite .wheel, .sprite .crown { transform-origin:center; }
  .sprite .door { transform-origin:left center; }
  .m-spin .wheel, .m-drive .wheel, .m-cross-right .wheel, .m-cross-left .wheel {
    animation:wheelSpin .9s linear infinite; }
  .m-spin .door, .m-drive .door { animation:doorOpen 3s ease-in-out infinite; }
  .m-hop .tail, .m-bob .tail { animation:tailWag .5s ease-in-out infinite; }
  .m-fall { animation:mSway 6s ease-in-out infinite; }
  .m-fall .drop { animation:dropFall .9s linear infinite; }
  .sprite .crown { animation:crownBreathe 4.5s ease-in-out infinite; }
  .drop { animation:dropFall 1.2s linear infinite; }
  .twinkle { animation:twinkle 2.8s ease-in-out infinite; }
  .beam { animation:beamSweep 7s ease-in-out infinite alternate; transform-box:fill-box;
    transform-origin:top center; }
  .puff { animation:puffUp 2.4s ease-out infinite; }
  .dash { animation:dashRun 4s linear infinite; }
  @keyframes mBob { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-4%)} }
  @keyframes mFloat { 0%,100%{transform:translate(0,0) rotate(-2deg)}
    50%{transform:translate(3%,-8%) rotate(2deg)} }
  @keyframes mHop { 0%,100%{transform:translateY(0) scaleY(1)}
    35%{transform:translateY(-12%) scaleY(1.04)} 60%{transform:translateY(0) scaleY(.96)} }
  @keyframes mSway { 0%,100%{transform:rotate(-2.5deg)} 50%{transform:rotate(2.5deg)} }
  @keyframes mDrive { 0%,100%{transform:translate(-2%,0)} 50%{transform:translate(2%,-1.5%)} }
  @keyframes mTurn { 0%,100%{transform:scaleX(1)} 50%{transform:scaleX(-1)} }
  @keyframes mCrossRight { from{transform:translateX(-160%)} to{transform:translateX(160%)} }
  @keyframes mCrossLeft { from{transform:translateX(160%)} to{transform:translateX(-160%)} }
  @keyframes mSpinSlow { to{transform:rotate(360deg)} }
  @keyframes armWave { 0%,100%{transform:rotate(8deg)} 50%{transform:rotate(148deg)} }
  @keyframes armSwing { 0%,100%{transform:rotate(-16deg)} 50%{transform:rotate(16deg)} }
  @keyframes armPointUp { 0%,100%{transform:rotate(6deg)} 45%,65%{transform:rotate(172deg)} }
  @keyframes armPointDown { 0%,100%{transform:rotate(4deg)} 45%,65%{transform:rotate(-24deg)} }
  @keyframes legSwing { 0%,100%{transform:rotate(-14deg)} 50%{transform:rotate(14deg)} }
  @keyframes wheelSpin { to{transform:rotate(360deg)} }
  @keyframes doorOpen { 0%,40%{transform:scaleX(1)} 55%,80%{transform:scaleX(.18)}
    100%{transform:scaleX(1)} }
  @keyframes tailWag { 0%,100%{transform:rotate(-12deg)} 50%{transform:rotate(16deg)} }
  @keyframes crownBreathe { 0%,100%{transform:scale(1)} 50%{transform:scale(1.05)} }
  @keyframes dropFall { 0%{transform:translateY(0);opacity:0}
    20%{opacity:1} 100%{transform:translateY(70px);opacity:0} }
  @keyframes twinkle { 0%,100%{opacity:.25} 50%{opacity:1} }
  @keyframes beamSweep { from{transform:rotate(-7deg)} to{transform:rotate(7deg)} }
  @keyframes puffUp { 0%{transform:translateY(0);opacity:.9}
    100%{transform:translateY(-40px) scale(1.7);opacity:0} }
  @keyframes dashRun { to{stroke-dashoffset:-240} }
  /* stage furniture */
  .scene-tag { position:absolute; top:.7rem; left:.9rem; padding:.3rem .7rem; border-radius:999px;
    background:rgba(2,6,23,.62); color:#e2e8f0; font-size:.78rem; letter-spacing:.02em;
    animation:tagIn .5s ease-out both; }
  @keyframes tagIn { from{opacity:0;transform:translateY(-6px)} to{opacity:1;transform:none} }
  .stage-tools { position:absolute; top:.6rem; right:.8rem; display:flex; gap:.4rem;
    align-items:center; flex-wrap:wrap; justify-content:flex-end; max-width:70%;
    background:rgba(2,6,23,.55); border-radius:999px; padding:.3rem .5rem; }
  .stage-tools label { color:#e2e8f0; font-size:.78rem; display:inline-flex; gap:.3rem;
    align-items:center; }
  .dots { display:flex; gap:.25rem; }
  .dots button { padding:.1rem .42rem; font-size:.72rem; border-radius:8px; background:#0f172a;
    border:1px solid #475569; color:var(--muted); }
  .dots button.on { background:var(--accent); border-color:var(--accent); color:#04202f;
    font-weight:700; }
  .captions { position:absolute; left:0; right:0; bottom:0; padding:2.6rem 1rem .9rem;
    background:linear-gradient(transparent, rgba(2,6,23,.55) 42%, rgba(2,6,23,.92)); }
  .cap-ball { position:absolute; left:0; top:0; width:16px; height:16px; opacity:0;
    pointer-events:none; transition:transform .16s ease-out, opacity .2s; }
  .cap-ball .dot { width:16px; height:16px; border-radius:50%; animation:ballhop .5s ease-in-out infinite;
    background:radial-gradient(circle at 32% 30%, #fff, var(--warm) 60%, #b45309);
    box-shadow:0 0 12px rgba(251,191,36,.7); }
  .cap-ball.on { opacity:1; }
  .stage.theater .cap-ball, .stage.theater .cap-ball .dot { width:26px; height:26px; }
  .cap-narration { color:#cbd5e1; font-size:.86rem; margin-bottom:.3rem; }
  /* padding-top leaves the bouncing ball its own lane above the words */
  .cap-line { font-size:1.4rem; font-weight:800; line-height:1.5; padding-top:1.4rem; }
  .cap-line .w { padding:.05rem .2rem; }
  .cap-tr { color:var(--good); font-size:1rem; }
  .cap-next { color:#94a3b8; font-size:.9rem; margin-top:.2rem; }
  .stage.theater .captions { padding:4rem 3rem 2.2rem; }
  .stage.theater .cap-narration { font-size:1.25rem; }
  .stage.theater .cap-line { font-size:2.6rem; padding-top:2.2rem; }
  .stage.theater .cap-tr { font-size:1.6rem; }
  .stage.theater .cap-next { font-size:1.2rem; }
  .stage.theater .scene-tag { font-size:1rem; top:1.4rem; left:2rem; }
  .stage.theater .stage-tools { top:1.3rem; right:2rem; }
  .fallback-orb { position:absolute; inset:0; display:grid; place-items:center; }
  .stage:not(.no-board) .fallback-orb { display:none; }
  .stage.no-board .camera, .stage.no-board .captions, .stage.no-board .scene-tag { display:none; }
  .orb { width:110px; height:110px; border-radius:50%;
    background:radial-gradient(circle at 30% 30%,#fff,var(--accent) 45%,transparent 70%); opacity:.85; }
  .stage.playing .orb { animation:bounce 1.1s ease-in-out infinite; }
  .symbol { position:absolute; font-size:3.4rem; text-shadow:0 8px 24px rgba(0,0,0,.35); }
  .stage.playing .symbol { animation:bob 1.2s ease-in-out infinite; }
  @keyframes bounce { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-18px)} }
  @keyframes bob { 0%,100%{transform:translateY(0) scale(1)} 50%{transform:translateY(-10px) scale(1.05)} }
  @keyframes ballhop { 0%,100%{transform:translateY(0) scale(1)} 45%{transform:translateY(-9px) scale(1.12)} }
  @media (prefers-reduced-motion: reduce) {
    .camera, .cast *, .backdrop * { animation:none !important; }
  }
  .controls { display:flex; flex-wrap:wrap; gap:.5rem; align-items:center; margin-top:.85rem; }
  .controls label { color:var(--muted); font-size:.85rem; display:inline-flex; gap:.35rem; align-items:center; }
  button, select, input[type=text] { font:inherit; border-radius:10px; border:1px solid #475569;
    background:#0f172a; color:var(--ink); padding:.45rem .8rem; }
  button { cursor:pointer; }
  button.primary { background:#0284c7; border-color:#38bdf8; font-weight:700; }
  button.ghost { padding:.3rem .6rem; font-size:.8rem; }
  button:disabled { opacity:.45; cursor:not-allowed; }
  audio { width:100%; margin-top:.65rem; }
  .lyrics { position:relative; margin-top:.85rem; max-height:clamp(320px, 46vh, 520px);
    overflow:auto; overscroll-behavior:contain; padding:1.6rem .75rem .75rem;
    border-radius:14px; background:#0f172a; border:1px solid #334155; }
  .line { padding:.4rem .5rem .3rem; border-radius:10px; transition:background .2s; }
  .line.active { background:color-mix(in srgb, var(--accent) 14%, transparent); }
  /* Queued during the instrumental intro: readable, but clearly not being sung yet. */
  .line.upcoming { background:transparent; box-shadow:inset 0 0 0 1px #334155; }
  .line.upcoming .words { color:#94a3b8; }
  .line .section { font-size:.66rem; text-transform:uppercase; letter-spacing:.08em; color:var(--accent); opacity:.8; }
  .line .words { color:var(--muted); font-size:1.05rem; line-height:1.9; }
  .line.active .words { color:var(--ink); }
  .w { padding:.05rem .18rem; border-radius:6px; transition:color .15s, background .15s; }
  .w.sung { color:var(--warm); }
  .w.now { background:var(--warm); color:#0f172a; font-weight:800; }
  .line.done .words { color:color-mix(in srgb, var(--warm) 70%, #64748b); }
  .line .tr { font-size:.9rem; color:var(--good); margin-top:.1rem; }
  .line .tr:empty { display:none; }
  #ball { position:absolute; left:0; top:0; width:18px; height:18px; pointer-events:none; opacity:0;
    transition:transform .16s ease-out, opacity .2s; }
  #ball .dot { width:18px; height:18px; border-radius:50%; animation:ballhop .5s ease-in-out infinite;
    background:radial-gradient(circle at 32% 30%, #fff, var(--warm) 60%, #b45309);
    box-shadow:0 0 12px rgba(251,191,36,.7); }
  #ball.on { opacity:1; }
  .now-line { padding:.65rem .8rem; border-radius:12px; background:#122033; border:1px solid #334155; }
  .now-line .en { font-weight:700; }
  .now-line .target { color:var(--good); font-size:1.05rem; margin-top:.2rem; }
  .badge { display:inline-block; font-size:.68rem; text-transform:uppercase; letter-spacing:.06em;
    padding:.12rem .45rem; border-radius:999px; border:1px solid #475569; color:var(--muted); margin-left:.4rem; }
  .badge.curated { color:#a7f3d0; border-color:#34d399; }
  .badge.llm, .badge.cached { color:#bfdbfe; border-color:#60a5fa; }
  .badge.lexicon { color:#fde68a; border-color:#fbbf24; }
  .chips { display:flex; flex-wrap:wrap; gap:.35rem; margin-top:.55rem; }
  .chip { font-size:.8rem; padding:.25rem .55rem; border-radius:999px; background:#0f172a; border:1px solid #475569; }
  .chip b { color:var(--good); font-weight:700; }
  .examples { margin:.6rem 0 0; padding-left:1.1rem; color:var(--muted); font-size:.88rem; }
  .examples li { margin:.15rem 0; }
  .ask-row { display:flex; gap:.5rem; margin-top:.5rem; }
  .ask-row input { flex:1; }
  .answer { margin-top:.65rem; padding:.7rem .85rem; border-radius:12px; background:#0f172a;
    border:1px solid #334155; white-space:pre-wrap; min-height:3rem; }
  .pronounce-target { padding:.65rem .8rem; border-radius:12px; background:#122033;
    border:1px solid #334155; margin-bottom:.55rem; }
  .pronounce-target .label { font-size:.72rem; text-transform:uppercase; letter-spacing:.04em;
    color:var(--muted); }
  .pronounce-target .say { font-weight:700; font-size:1.05rem; margin-top:.2rem; }
  .pronounce-target .hint { color:var(--muted); font-size:.82rem; margin-top:.25rem; }
  .pronounce-row { display:flex; flex-wrap:wrap; gap:.45rem; align-items:center; margin:.45rem 0; }
  .pronounce-row input[type=text] { flex:1; min-width:10rem; }
  .score-card { margin-top:.55rem; padding:.7rem .85rem; border-radius:12px; background:#0f172a;
    border:1px solid #334155; }
  .score-card.pass { border-color:#34d399; }
  .score-card.retry { border-color:#fbbf24; }
  .score-card .stars { color:#fbbf24; letter-spacing:.1em; font-size:1.1rem; }
  .word-chip { display:inline-block; margin:.15rem .2rem 0 0; padding:.15rem .45rem;
    border-radius:999px; font-size:.78rem; border:1px solid #334155; }
  .word-chip.ok { background:#064e3b; border-color:#34d399; color:#a7f3d0; }
  .word-chip.missed, .word-chip.wrong { background:#7c2d12; border-color:#fb923c; color:#fed7aa; }
  .word-chip.extra { background:#334155; color:#cbd5e1; }
  .btn-mic.listening { background:#b91c1c; border-color:#f87171; color:#fff; }
  .clip { display:block; width:100%; text-align:left; margin:0 0 .45rem; padding:.55rem .7rem;
    border-radius:10px; background:#0f172a; border:1px solid #334155; color:var(--ink); cursor:pointer; }
  .clip strong { display:block; font-size:.92rem; }
  .clip span { color:var(--muted); font-size:.76rem; }
  .clip.active { border-color:var(--warm); box-shadow:0 0 0 1px var(--warm); }
  .videos { display:grid; gap:.6rem; }
  .video { padding:.7rem .85rem; border-radius:12px; background:#0f172a; border:1px solid #334155; }
  .video strong { display:block; }
  .video p { margin:.25rem 0 .5rem; color:var(--muted); font-size:.85rem; }
  .video a { color:var(--accent); margin-right:.9rem; }
  .video iframe { width:100%; aspect-ratio:16/9; border:0; border-radius:10px; margin-top:.5rem; }
  .embed-stage { display:grid; gap:.75rem; }
  .embed-player { position:relative; width:100%; aspect-ratio:16/9; background:#020617;
    border-radius:14px; overflow:hidden; border:1px solid #334155; }
  .embed-player.portrait { aspect-ratio:9/16; max-height:min(70vh, 640px); margin:0 auto;
    width:min(100%, 360px); }
  .embed-player iframe, .embed-player #yt-host, .embed-player video {
    width:100%; height:100%; border:0; object-fit:contain; background:#000; }
  .embed-tools { display:flex; flex-wrap:wrap; gap:.45rem; align-items:center; }
  .embed-tools label { font-size:.85rem; color:var(--muted); }
  .verse-list { display:grid; gap:.45rem; max-height:320px; overflow:auto; }
  .verse { text-align:left; width:100%; padding:.55rem .7rem; border-radius:10px;
    background:#0f172a; border:1px solid #334155; color:var(--ink); cursor:pointer; }
  .verse.active { border-color:var(--warm); box-shadow:0 0 0 1px var(--warm); }
  .verse strong { display:block; font-size:.9rem; }
  .verse .tr { color:var(--good); font-size:.82rem; margin-top:.15rem; }
  .verse .meta { font-size:.72rem; }
  .pause-card { padding:.75rem .9rem; border-radius:12px; background:#111827; border:1px solid #fbbf24; }
  .pause-card h3 { margin:0 0 .35rem; font-size:1rem; color:#fde68a; }
  .q-list { display:grid; gap:.45rem; margin-top:.55rem; }
  .q-item { padding:.55rem .7rem; border-radius:10px; background:#0f172a; border:1px solid #334155; }
  .q-item .kind { font-size:.7rem; text-transform:uppercase; letter-spacing:.04em; color:#fbbf24; }
  .q-item .ans { margin-top:.35rem; color:var(--muted); display:none; }
  .q-item.open .ans { display:block; color:var(--good); }
  .embed-picker { display:grid; gap:.45rem; }
  .embed-pick { display:flex; gap:.7rem; align-items:center; text-align:left; width:100%;
    padding:.5rem .65rem; border-radius:12px; background:#0f172a; border:1px solid #334155;
    color:var(--ink); cursor:pointer; }
  .embed-pick.active { border-color:var(--accent); }
  .embed-pick img { width:72px; height:40px; object-fit:cover; border-radius:6px; background:#020617; }
  .embed-pick strong { display:block; font-size:.88rem; }
  .meta { color:var(--muted); font-size:.85rem; margin-top:.35rem; }
  .toast { position:fixed; right:1rem; bottom:1rem; display:none; background:#0f766e;
    border:1px solid #5eead4; padding:.7rem .9rem; border-radius:10px; }
  .toast.show { display:block; }
"""

_HTML = """
  <header>
    <h1>Theodore Music Lab</h1>
    <p>Follow the bouncing ball, watch each word light up as it is sung, and read the
       translation of every line in any of 26+ languages. Say or sing each line into the
       mic to check your pronunciation, embed YouTube movie lessons, and ask the AI about
       a line at any time — while the song or clip is still playing.</p>
  </header>
  <div class="layout">
    <div class="stack">
      <aside class="panel">
        <h2>Featured songs</h2>
        <div id="song-list">Loading…</div>
        <div class="meta" id="catalog-meta"></div>
      </aside>
      <aside class="panel">
        <h2>Short lyric clips</h2>
        <div id="clip-list" class="meta">Loading…</div>
      </aside>
    </div>
    <div class="stack">
      <main class="panel">
        <h2 id="now-title">Choose a song</h2>
        <div class="meta" id="now-meta"></div>
        <div class="stage no-board" id="stage" data-anim="pulse">
          <div class="camera" id="camera">
            <div class="backdrop" id="backdrop" aria-hidden="true"></div>
            <div class="cast" id="cast" aria-hidden="true"></div>
          </div>
          <div class="fallback-orb">
            <div class="orb" aria-hidden="true"></div>
            <div class="symbol" id="stage-symbol">♪</div>
          </div>
          <div class="scene-tag" id="scene-tag"></div>
          <div class="stage-tools">
            <button class="ghost" id="btn-stage-play" type="button">Play</button>
            <button class="ghost" id="btn-theater" type="button">Full screen</button>
            <label><input type="checkbox" id="sing-lang" /> <span id="sing-label">Sing in
              Spanish</span></label>
            <label><input type="checkbox" id="narrate" /> Narrate scenes</label>
            <span class="dots" id="scene-dots"></span>
          </div>
          <div class="captions" id="captions">
            <div class="cap-ball" id="cap-ball"><div class="dot"></div></div>
            <div class="cap-narration" id="cap-narration"></div>
            <div class="cap-line" id="cap-line"></div>
            <div class="cap-tr" id="cap-tr"></div>
            <div class="cap-next" id="cap-next"></div>
          </div>
        </div>
        <div class="controls">
          <button class="primary" id="btn-play" type="button" disabled>Play</button>
          <button id="btn-pause" type="button" disabled>Pause</button>
          <button id="btn-restart" type="button" disabled>Restart</button>
          <label>Translation <select id="meaning-lang"></select></label>
          <label><input type="checkbox" id="show-inline" checked /> Show every line</label>
          <label>Sync
            <button class="ghost" id="sync-back" type="button">−0.25s</button>
            <span id="sync-value">0.00s</span>
            <button class="ghost" id="sync-fwd" type="button">+0.25s</button>
            <button class="ghost" id="sync-reset" type="button">Reset</button>
          </label>
          <span class="meta" id="timing-source"></span>
        </div>
        <audio id="player" controls preload="metadata"></audio>
        <div class="lyrics" id="lyrics">
          <div id="ball"><div class="dot"></div></div>
        </div>
        <div class="meta" id="tier-meta"></div>
      </main>
      <div class="bottom">
        <section class="panel">
          <h2>This line, translated</h2>
          <div class="now-line" id="now-line">Press play — the current line and its
            translation appear here.</div>
          <div class="chips" id="now-vocab"></div>
          <ul class="examples" id="now-examples"></ul>
        </section>
        <section class="panel">
          <h2>Say / sing this line</h2>
          <p class="meta">Practise the English lyric or the translation, then get a score
            and corrections before the next line.</p>
          <div class="pronounce-target" id="pronounce-target">
            <div class="label">Line to say</div>
            <div class="say" id="pronounce-say">Choose a song and press play.</div>
            <div class="hint" id="pronounce-hint"></div>
          </div>
          <div class="pronounce-row">
            <label><input type="radio" name="practice-mode" id="practice-en" value="english"
              checked /> English lyric</label>
            <label><input type="radio" name="practice-mode" id="practice-tr" value="translation" />
              My language</label>
          </div>
          <div class="pronounce-row">
            <button class="ghost" id="btn-hear-model" type="button">Hear model</button>
            <button class="primary btn-mic" id="btn-mic" type="button">Speak line</button>
            <button class="ghost" id="btn-check-typed" type="button">Check typed</button>
          </div>
          <div class="pronounce-row">
            <input type="text" id="pronounce-heard"
              placeholder="Or type what you said / sang…" />
          </div>
          <div class="meta" id="pronounce-status">Mic uses the browser speech recognizer
            when available.</div>
          <div class="score-card" id="pronounce-result" hidden></div>
        </section>
        <section class="panel">
          <h2>Ask the AI about the lyrics</h2>
          <div class="meta" id="ask-context">No line selected yet.</div>
          <div class="ask-row">
            <input type="text" id="ask-input" placeholder="e.g. Why does it say 'go round and round'?" />
            <button class="primary" id="ask-send" type="button">Ask</button>
          </div>
          <div class="chips" id="ask-quick"></div>
          <div class="answer" id="ask-answer">Answers stay grounded in the lyrics of the
            line you are on.</div>
        </section>
      </div>
      <section class="panel">
        <h2>YouTube movie lessons</h2>
        <p class="meta">Embed a short film or legend, pause on each verse, answer grammar and
          vocabulary prompts, then ask the AI anything about that line — translated into
          your language.</p>
        <div class="embed-picker" id="embed-picker">Loading…</div>
        <div class="embed-stage" id="embed-stage" hidden>
          <div class="embed-player" id="embed-player-box"><div id="yt-host"></div>
            <video id="local-video" playsinline controls preload="metadata" hidden></video></div>
          <div class="embed-tools">
            <button class="primary" id="btn-embed-play" type="button">Play</button>
            <button class="ghost" id="btn-embed-pause" type="button">Pause</button>
            <button class="ghost" id="btn-embed-continue" type="button">Continue after ask</button>
            <label><input type="checkbox" id="auto-pause" checked /> Pause at each verse</label>
            <span class="meta" id="embed-meta"></span>
          </div>
          <div class="pause-card" id="pause-card" hidden>
            <h3 id="pause-title">Paused for learning</h3>
            <div id="pause-line"></div>
            <div class="tr" id="pause-tr"></div>
            <div class="chips" id="pause-vocab"></div>
            <div class="q-list" id="pause-questions"></div>
            <div class="ask-row" style="margin-top:.65rem">
              <input type="text" id="embed-ask-input"
                placeholder="Ask about grammar, vocabulary, or this verse…" />
              <button class="primary" id="embed-ask-send" type="button">Ask</button>
            </div>
            <div class="chips" id="embed-ask-quick"></div>
            <div class="answer" id="embed-ask-answer">Answers stay grounded in the paused verse.</div>
          </div>
          <div class="verse-list" id="verse-list"></div>
        </div>
      </section>
      <section class="panel">
        <h2>Lyric videos</h2>
        <div class="videos" id="video-list">Loading…</div>
      </section>
    </div>
  </div>
  <div class="toast" id="toast"></div>
"""

_JS = r"""
  const $ = (id) => document.getElementById(id);
  const SYMBOLS = { travel: "\u2708\uFE0F", bus: "\uD83D\uDE8C", words: "\uD83D\uDD24", pulse: "\u266A" };
  const QUICK_ASKS = [
    "What does this line mean?",
    "How do I say this in my language?",
    "Why is it worded this way?",
    "How do I pronounce it?",
  ];

  const CAMERAS = ["push-in", "pull-out", "pan-right", "pan-left", "ken-burns",
    "zoom-punch", "tilt-up", "dolly-shake"];

  let featured = [];
  let current = null;
  let timings = null;
  let translation = null;
  let clips = [];
  let board = null;
  let singPlan = null;
  let singingLineNo = 0;
  let singBackedFrom = null;
  let embeds = [];
  let currentEmbed = null;
  let activeVerseNo = 0;
  let ytPlayer = null;
  let ytReady = false;
  let ytPoll = 0;
  let localVideo = null;
  let usingLocalVideo = false;
  let firedPauses = new Set();
  let pauseLocked = false;
  const EMBED_QUICK = [
    "What does this verse mean?",
    "Explain the grammar here",
    "Which vocabulary should I learn?",
    "Give me an example sentence",
  ];

  // A listener's sync nudge is remembered per song: ears differ, and a device
  // with slow audio output needs the same correction on every visit.
  const SYNC_STORAGE_KEY = "twl.sync.v1";
  let syncOffset = 0;
  let activeLineNo = 0;
  let activeWordKey = "";
  let activeClip = null;
  let activeSceneId = "";
  let activeSceneIndex = -1;
  let ducked = false;
  let duckedFrom = 1;
  let rafId = 0;
  const trCache = new Map();

  function toast(msg) {
    const el = $("toast");
    el.textContent = msg;
    el.classList.add("show");
    setTimeout(() => el.classList.remove("show"), 2400);
  }
  async function api(path, opts) {
    const res = await fetch(path, opts);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  }
  function post(path, body) {
    return api(path, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    });
  }
  function esc(s) {
    return String(s === null || s === undefined ? "" : s).replace(/[&<>"']/g, (c) => (
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]
    ));
  }
  function lang() { return $("meaning-lang").value || "en"; }
  function trRow(lineNo) {
    if (!translation) return null;
    return translation.lines.find((r) => r.line_no === lineNo) || null;
  }

  /* ---------- rendering ---------- */

  function renderSongList() {
    const box = $("song-list");
    box.innerHTML = featured.map((s) => `
      <button type="button" class="song-card ${current && current.song_id === s.song_id ? "active" : ""}"
        data-id="${esc(s.song_id)}">
        <strong>${esc(s.title_en)}</strong>
        <span>${esc(s.topic)} \u00b7 ${s.line_count} lines \u00b7 MP3</span>
      </button>`).join("") || "<div class='meta'>No featured songs found.</div>";
    box.querySelectorAll(".song-card").forEach((btn) => {
      btn.onclick = () => selectSong(btn.getAttribute("data-id"));
    });
  }

  function renderLyrics() {
    if (!current || !timings) return;
    const inline = $("show-inline").checked;
    const rows = timings.lines.map((row) => {
      const words = row.words.map((w) =>
        `<span class="w" data-no="${row.line_no}" data-i="${w.index}">${esc(w.text)}</span>`
      ).join(" ");
      const tr = inline ? esc((trRow(row.line_no) || {}).translation || "") : "";
      return `<div class="line" data-no="${row.line_no}">
        ${row.section ? `<div class="section">${esc(row.section)}</div>` : ""}
        <div class="words">${words}</div>
        <div class="tr">${tr}</div>
      </div>`;
    }).join("");
    const box = $("lyrics");
    box.innerHTML = `<div id="ball"><div class="dot"></div></div>` + rows;
    box.querySelectorAll(".line").forEach((el) => {
      el.onclick = () => {
        const no = Number(el.getAttribute("data-no"));
        const row = timings.lines.find((r) => r.line_no === no);
        if (row) $("player").currentTime = Math.max(0, row.start - syncOffset);
        setActiveLine(no, true);
      };
    });
    activeLineNo = 0;
    activeWordKey = "";
    // The rebuilt rows carry no state classes, so the count-in must re-apply its own.
    countInLineNo = 0;
  }

  function renderTierMeta() {
    if (!translation) { $("tier-meta").textContent = ""; return; }
    const t = translation.tiers || {};
    const parts = Object.keys(t).map((k) => `${t[k]} ${k}`);
    const review = translation.needs_native_review ? " \u00b7 pending native review" : "";
    const llm = translation.llm_available ? "" : " \u00b7 set XAI_API_KEY for full-sentence machine translation";
    $("tier-meta").textContent =
      `${translation.language_name}: ${translation.line_count} lines translated (${parts.join(", ")})${review}${llm}`;
  }

  function renderNowLine(lineNo) {
    const row = trRow(lineNo);
    const timed = timings ? timings.lines.find((r) => r.line_no === lineNo) : null;
    if (!row || !timed) return;
    const tier = row.tier || "english";
    $("now-line").innerHTML =
      `<div class="en">${esc(row.text)}<span class="badge ${esc(tier)}">${esc(tier)}</span></div>
       <div class="target">${esc(row.translation)}</div>
       <div class="meta">${esc(row.note || "")}</div>`;
    const vocab = (row.vocabulary || []).filter((v) => v.target);
    $("now-vocab").innerHTML = vocab.map((v) =>
      `<span class="chip">${esc(v.en)} = <b>${esc(v.target)}</b></span>`).join("");
    const examples = (row.vocabulary || []).filter((v) => v.example_en).slice(0, 3);
    $("now-examples").innerHTML = examples.map((v) =>
      `<li>${esc(v.example_en)}</li>`).join("");
    $("ask-context").textContent = `Asking about line ${lineNo}: "${row.text}"`;
    refreshPronounceTarget();
  }

  function practiceMode() {
    const tr = $("practice-tr");
    return (tr && tr.checked) ? "translation" : "english";
  }

  function refreshPronounceTarget() {
    const say = $("pronounce-say");
    const hint = $("pronounce-hint");
    if (!say || !hint) return;
    const row = trRow(activeLineNo);
    if (!row) {
      say.textContent = "Choose a song and press play.";
      hint.textContent = "";
      return;
    }
    const mode = practiceMode();
    const target = mode === "translation" ? (row.translation || row.text) : row.text;
    say.textContent = target;
    hint.textContent = mode === "translation"
      ? `Say this in ${translation ? translation.language_name : "your language"} (line ${activeLineNo}).`
      : `Sing or say the English lyric (line ${activeLineNo}).`;
  }

  function renderPronounceResult(result) {
    const box = $("pronounce-result");
    if (!box) return;
    box.hidden = false;
    box.className = "score-card " + (result.passed ? "pass" : "retry");
    const stars = "\u2605".repeat(result.stars || 0) + "\u2606".repeat(Math.max(0, 3 - (result.stars || 0)));
    const chips = (result.words || []).map((w) => {
      const label = w.status === "extra" ? (w.heard || "") : (w.word || w.heard || "");
      if (!label) return "";
      return `<span class="word-chip ${esc(w.status)}">${esc(label)}</span>`;
    }).join("");
    const tips = (result.corrections || []).map((c) =>
      `<li>${esc(c.tip)}</li>`).join("");
    box.innerHTML =
      `<div class="stars">${stars}</div>
       <div><strong>${result.score}/100</strong> \u00b7 ${esc(result.feedback)}</div>
       <div class="meta" style="margin-top:.35rem">Heard: ${esc(result.heard || "(nothing)")}</div>
       <div style="margin-top:.45rem">${chips}</div>
       <div class="meta" style="margin-top:.45rem">${esc(result.mouth_tip || "")}</div>
       <div class="meta">${esc(result.syllables || "")}</div>
       ${tips ? `<ul class="examples">${tips}</ul>` : ""}`;
  }

  async function checkPronunciation(heard) {
    if (!current || !activeLineNo) {
      toast("Pick a song line first");
      return;
    }
    const text = (heard || "").trim();
    if (!text) {
      toast("Say or type the line first");
      return;
    }
    $("pronounce-status").textContent = "Checking pronunciation\u2026";
    try {
      const result = await post("/api/music/pronounce", {
        song_id: current.song_id,
        line_no: activeLineNo,
        heard: text,
        target_lang: lang(),
        practice: practiceMode(),
      });
      $("pronounce-heard").value = result.heard || text;
      renderPronounceResult(result);
      $("pronounce-status").textContent = result.passed
        ? "Passed — try the next line, or sing it with the track."
        : "Not quite — use the tips, Hear model, then try again.";
      toast(result.passed
        ? `Pronunciation ${result.score}/100`
        : `Try again \u00b7 ${result.score}/100`);
    } catch (err) {
      $("pronounce-status").textContent = String(err.message || err);
    }
  }

  function hearPronounceModel() {
    const row = trRow(activeLineNo);
    if (!row) { toast("Pick a line first"); return; }
    const mode = practiceMode();
    const text = mode === "translation" ? (row.translation || row.text) : row.text;
    const code = mode === "translation" ? lang() : "en";
    const tag = mode === "translation"
      ? ((singPlan && singPlan.voice_tag) || lang())
      : "en-US";
    if (!canSpeak(code, tag)) { toast("No voice available for this language"); return; }
    // Slower than the sung rate: this is the model to copy.
    speak(text, { lang: code, tag: tag, rate: 0.92 });
  }

  let pronounceRec = null;
  let micListening = false;

  function speechRecognizer() {
    const Ctor = window.SpeechRecognition || window.webkitSpeechRecognition;
    return Ctor ? new Ctor() : null;
  }

  function stopMic() {
    micListening = false;
    const btn = $("btn-mic");
    if (btn) btn.classList.remove("listening");
    if (pronounceRec) {
      try { pronounceRec.stop(); } catch (_) {}
    }
  }

  function startMic() {
    const rec = speechRecognizer();
    if (!rec) {
      $("pronounce-status").textContent =
        "Speech recognition is not available here — type what you said, then Check typed.";
      $("pronounce-heard").focus();
      return;
    }
    const player = $("player");
    if (player && !player.paused) player.pause();
    stopSinging();
    cancelSpeech();
    pronounceRec = rec;
    rec.lang = practiceMode() === "translation"
      ? ((singPlan && singPlan.voice_tag) || lang())
      : "en-US";
    rec.interimResults = true;
    rec.continuous = false;
    rec.maxAlternatives = 1;
    micListening = true;
    $("btn-mic").classList.add("listening");
    $("pronounce-status").textContent = "Listening\u2026 say the line clearly.";
    let finalText = "";
    rec.onresult = (ev) => {
      let interim = "";
      for (let i = ev.resultIndex; i < ev.results.length; i++) {
        const chunk = ev.results[i][0].transcript;
        if (ev.results[i].isFinal) finalText += chunk + " ";
        else interim += chunk;
      }
      $("pronounce-heard").value = (finalText + interim).trim();
    };
    rec.onerror = (ev) => {
      stopMic();
      $("pronounce-status").textContent = "Mic error: " + (ev.error || "unknown")
        + " — you can still type the line.";
    };
    rec.onend = () => {
      const was = micListening;
      stopMic();
      const heard = ($("pronounce-heard").value || "").trim();
      if (was && heard) checkPronunciation(heard);
      else if (was) $("pronounce-status").textContent = "No speech heard — try again or type it.";
    };
    try { rec.start(); }
    catch (_) {
      stopMic();
      $("pronounce-status").textContent = "Could not start the mic — check browser permission.";
    }
  }

  function renderClips() {
    const box = $("clip-list");
    if (!clips.length) { box.textContent = "No clips for this song."; return; }
    box.innerHTML = clips.map((c) => `
      <button type="button" class="clip ${activeClip && activeClip.clip_id === c.clip_id ? "active" : ""}"
        data-id="${esc(c.clip_id)}">
        <strong>${esc(c.title)}</strong>
        <span>${esc(c.focus)} \u00b7 ${Math.round(c.duration_sec)}s</span>
      </button>`).join("");
    box.querySelectorAll(".clip").forEach((btn) => {
      btn.onclick = () => playClip(btn.getAttribute("data-id"));
    });
  }

  function renderVideos(rows) {
    const box = $("video-list");
    if (!rows.length) { box.textContent = "No videos configured."; return; }
    box.innerHTML = rows.map((v) => `
      <div class="video" data-id="${esc(v.video_id)}">
        <strong>${esc(v.title)}<span class="badge">${esc(v.kind)}</span></strong>
        <p>${esc(v.note)}</p>
        <a href="${esc(v.url)}" target="_blank" rel="noopener">Watch on ${esc(v.provider)}</a>
        ${v.lyrics_url ? `<a href="${esc(v.lyrics_url)}" target="_blank" rel="noopener">Printed lyrics</a>` : ""}
        ${v.embed_url ? `<button class="ghost" type="button" data-embed="${esc(v.embed_url)}">Play here</button>` : ""}
        <div class="slot"></div>
      </div>`).join("");
    box.querySelectorAll("button[data-embed]").forEach((btn) => {
      btn.onclick = () => {
        const slot = btn.parentElement.querySelector(".slot");
        slot.innerHTML = `<iframe src="${btn.getAttribute("data-embed")}" allowfullscreen
          title="Lyric video" loading="lazy"></iframe>`;
        btn.disabled = true;
      };
    });
  }

  /* ---------- YouTube embeds: pause, ask, translate ---------- */

  function loadYtApi() {
    return new Promise((resolve) => {
      if (window.YT && window.YT.Player) { resolve(); return; }
      const prior = window.onYouTubeIframeAPIReady;
      window.onYouTubeIframeAPIReady = () => {
        if (typeof prior === "function") prior();
        resolve();
      };
      if (![...document.scripts].some((s) => (s.src || "").includes("youtube.com/iframe_api"))) {
        const tag = document.createElement("script");
        tag.src = "https://www.youtube.com/iframe_api";
        document.head.appendChild(tag);
      }
    });
  }

  function stopYtPoll() {
    if (ytPoll) { clearInterval(ytPoll); ytPoll = 0; }
  }

  function startYtPoll() {
    stopYtPoll();
    ytPoll = setInterval(checkVersePause, 250);
  }

  function getPlayhead() {
    if (usingLocalVideo && localVideo) return localVideo.currentTime || 0;
    if (ytPlayer && ytReady) {
      try { return ytPlayer.getCurrentTime() || 0; } catch (_) { return 0; }
    }
    return 0;
  }

  function pauseMedia() {
    if (usingLocalVideo && localVideo) { localVideo.pause(); return; }
    if (ytPlayer && ytReady) { try { ytPlayer.pauseVideo(); } catch (_) { /* ignore */ } }
  }

  function playMedia() {
    if (usingLocalVideo && localVideo) {
      localVideo.play().catch(() => toast("Press play on the video once"));
      return;
    }
    if (ytPlayer && ytReady) {
      try { ytPlayer.playVideo(); } catch (_) { toast("Press play on the video once"); }
    }
  }

  function seekMedia(sec) {
    if (usingLocalVideo && localVideo) {
      localVideo.currentTime = Math.max(0, sec);
      localVideo.pause();
      return;
    }
    if (ytPlayer && ytReady) {
      try {
        ytPlayer.seekTo(Math.max(0, sec), true);
        ytPlayer.pauseVideo();
      } catch (_) { /* ignore */ }
    }
  }

  function checkVersePause() {
    if (!currentEmbed || !$("auto-pause").checked || pauseLocked) return;
    const t = getPlayhead();
    for (const verse of currentEmbed.verses || []) {
      const pauseAt = Number(verse.pause_sec);
      if (!pauseAt || firedPauses.has(verse.verse_no)) continue;
      if (t >= pauseAt - 0.15) {
        firedPauses.add(verse.verse_no);
        pauseMedia();
        showPauseCard(verse.verse_no, true);
        toast(`Paused at line ${verse.verse_no} — read, ask, then Continue`);
        return;
      }
    }
    let current = null;
    for (const verse of currentEmbed.verses || []) {
      if (t >= verse.start_sec) current = verse;
    }
    if (current && current.verse_no !== activeVerseNo && !pauseLocked) {
      activeVerseNo = current.verse_no;
      markVerseActive(activeVerseNo);
    }
  }

  function markVerseActive(verseNo) {
    $("verse-list").querySelectorAll(".verse").forEach((el) => {
      el.classList.toggle("active", Number(el.getAttribute("data-no")) === verseNo);
    });
  }

  function renderEmbedPicker() {
    const box = $("embed-picker");
    if (!embeds.length) { box.textContent = "No embeds configured."; return; }
    box.innerHTML = embeds.map((e) => `
      <button type="button" class="embed-pick ${currentEmbed && currentEmbed.embed_id === e.embed_id ? "active" : ""}"
        data-id="${esc(e.embed_id)}">
        ${e.thumbnail_url ? `<img src="${esc(e.thumbnail_url)}" alt="" loading="lazy" />` : ""}
        <span>
          <strong>${esc(e.title)}<span class="badge">${esc(e.kind)}</span></strong>
          <span class="meta">${esc(e.channel)} \u00b7 ${e.verse_count} pause points
            ${e.has_pause_ask ? "\u00b7 pause & ask" : ""}</span>
        </span>
      </button>`).join("");
    box.querySelectorAll(".embed-pick").forEach((btn) => {
      btn.onclick = () => selectEmbed(btn.getAttribute("data-id"));
    });
  }

  function renderVerses() {
    const box = $("verse-list");
    if (!currentEmbed || !(currentEmbed.verses || []).length) {
      box.innerHTML = "<div class='meta'>This item is a playlist pointer — open a lesson above to pause and ask.</div>";
      return;
    }
    box.innerHTML = currentEmbed.verses.map((v) => `
      <button type="button" class="verse ${v.verse_no === activeVerseNo ? "active" : ""}"
        data-no="${v.verse_no}">
        <strong>Line ${v.verse_no} \u00b7 ${esc(v.section || v.focus)} \u00b7 ${esc(v.source_lang || "")}
          \u00b7 ${Math.round(v.start_sec)}s</strong>
        <span>${esc(v.text)}</span>
        <div class="tr">${esc(v.translation)}</div>
        ${v.text_en && v.source_lang === "km" ? `<div class="meta">${esc(v.text_en)}</div>` : ""}
      </button>`).join("");
    box.querySelectorAll(".verse").forEach((btn) => {
      btn.onclick = () => {
        const no = Number(btn.getAttribute("data-no"));
        seekVerse(no);
        showPauseCard(no, false);
      };
    });
  }

  function showPauseCard(verseNo, locked) {
    if (!currentEmbed) return;
    const verse = currentEmbed.verses.find((v) => v.verse_no === verseNo);
    if (!verse) return;
    activeVerseNo = verseNo;
    pauseLocked = !!locked;
    markVerseActive(verseNo);
    $("pause-card").hidden = false;
    $("pause-title").textContent = locked
      ? `Paused at line ${verseNo} — read & ask`
      : `Line ${verseNo} — grammar & vocabulary`;
    $("pause-line").textContent = verse.text;
    const bits = [verse.translation];
    if (verse.text_en && verse.source_lang === "km" && verse.translation !== verse.text_en) {
      bits.push(verse.text_en);
    }
    $("pause-tr").textContent = bits.filter(Boolean).join(" · ");
    $("pause-vocab").innerHTML = (verse.vocabulary || []).filter((r) => r.target).slice(0, 8).map((r) =>
      `<span class="chip"><b>${esc(r.en)}</b> \u2192 ${esc(r.target)}</span>`).join("");
    $("pause-questions").innerHTML = (verse.questions || []).map((q, i) => `
      <div class="q-item" data-i="${i}">
        <div class="kind">${esc(q.kind)}</div>
        <div>${esc(q.prompt_translation || q.prompt)}</div>
        <button class="ghost" type="button" data-reveal="${i}">Show answer</button>
        <div class="ans">${esc(q.answer_translation || q.answer)}</div>
      </div>`).join("");
    $("pause-questions").querySelectorAll("button[data-reveal]").forEach((btn) => {
      btn.onclick = () => {
        const item = btn.closest(".q-item");
        item.classList.add("open");
        btn.remove();
      };
    });
    $("embed-ask-answer").textContent = "Ask about this verse, or reveal a prepared answer above.";
  }

  function clearPlayers() {
    stopYtPoll();
    usingLocalVideo = false;
    localVideo = $("local-video");
    localVideo.pause();
    localVideo.removeAttribute("src");
    localVideo.load();
    localVideo.hidden = true;
    $("yt-host").hidden = false;
    $("yt-host").innerHTML = "";
    $("embed-player-box").classList.remove("portrait");
    if (ytPlayer && ytPlayer.destroy) {
      try { ytPlayer.destroy(); } catch (_) { /* ignore */ }
      ytPlayer = null;
    }
    ytReady = false;
  }

  function wireLocalVideo() {
    localVideo = $("local-video");
    localVideo.onplay = () => { pauseLocked = false; startYtPoll(); };
    localVideo.onpause = () => { stopYtPoll(); };
    localVideo.onended = () => { stopYtPoll(); };
    localVideo.ontimeupdate = () => {
      if (!document.hidden) checkVersePause();
    };
  }

  async function ensureLocalPlayer(videoUrl, portrait) {
    clearPlayers();
    usingLocalVideo = true;
    localVideo = $("local-video");
    $("yt-host").hidden = true;
    localVideo.hidden = false;
    if (portrait) $("embed-player-box").classList.add("portrait");
    wireLocalVideo();
    localVideo.src = videoUrl;
    await new Promise((resolve) => {
      const done = () => { localVideo.removeEventListener("loadedmetadata", done); resolve(); };
      localVideo.addEventListener("loadedmetadata", done);
      localVideo.load();
    });
  }

  async function ensureYtPlayer(youtubeId) {
    clearPlayers();
    await loadYtApi();
    return new Promise((resolve) => {
      ytPlayer = new YT.Player("yt-host", {
        videoId: youtubeId,
        playerVars: {
          enablejsapi: 1,
          rel: 0,
          modestbranding: 1,
          playsinline: 1,
          origin: window.location.origin,
        },
        events: {
          onReady: () => { ytReady = true; resolve(ytPlayer); },
          onStateChange: (ev) => {
            if (ev.data === YT.PlayerState.PLAYING) {
              pauseLocked = false;
              startYtPoll();
            } else if (ev.data === YT.PlayerState.PAUSED || ev.data === YT.PlayerState.ENDED) {
              stopYtPoll();
            }
          },
        },
      });
    });
  }

  async function selectEmbed(embedId) {
    currentEmbed = await api(`/api/music/embeds/${encodeURIComponent(embedId)}` +
      `?target_lang=${encodeURIComponent(lang())}&allow_llm=false`);
    activeVerseNo = currentEmbed.verses[0] ? currentEmbed.verses[0].verse_no : 0;
    firedPauses = new Set();
    pauseLocked = false;
    $("embed-stage").hidden = false;
    $("embed-meta").textContent =
      `${currentEmbed.channel} \u00b7 ${currentEmbed.verse_count} lines \u00b7 ${currentEmbed.topic}`;
    renderEmbedPicker();
    renderVerses();
    $("pause-card").hidden = true;
    if (currentEmbed.video_url) {
      await ensureLocalPlayer(currentEmbed.video_url, currentEmbed.kind === "local-karaoke");
      if (activeVerseNo) showPauseCard(activeVerseNo, false);
    } else if (currentEmbed.youtube_id && currentEmbed.has_pause_ask) {
      await ensureYtPlayer(currentEmbed.youtube_id);
      if (activeVerseNo) showPauseCard(activeVerseNo, false);
    } else if (currentEmbed.playlist_url) {
      clearPlayers();
      $("yt-host").innerHTML =
        `<div class="meta" style="padding:1rem">Open the playlist on YouTube, then come back and
         pick a lesson with pause points.
         <a href="${esc(currentEmbed.playlist_url)}" target="_blank" rel="noopener">Open playlist</a></div>`;
    }
  }

  function seekVerse(verseNo) {
    if (!currentEmbed) return;
    const verse = currentEmbed.verses.find((v) => v.verse_no === verseNo);
    if (!verse) return;
    activeVerseNo = verseNo;
    seekMedia(verse.start_sec);
    markVerseActive(verseNo);
  }

  async function askEmbed(question) {
    if (!currentEmbed || !currentEmbed.has_pause_ask) return;
    const q = (question || $("embed-ask-input").value || "").trim();
    if (!q) return;
    $("embed-ask-answer").textContent = "Thinking…";
    try {
      const data = await post("/api/music/embeds/ask", {
        embed_id: currentEmbed.embed_id,
        question: q,
        verse_no: activeVerseNo || null,
        target_lang: lang(),
        allow_llm: true,
      });
      $("embed-ask-answer").textContent = data.answer;
      $("embed-ask-input").value = "";
    } catch (e) {
      $("embed-ask-answer").textContent = String(e.message || e);
    }
  }

  async function loadEmbeds() {
    const data = await api(`/api/music/embeds?target_lang=${encodeURIComponent(lang())}`);
    embeds = data.embeds || [];
    renderEmbedPicker();
    if (currentEmbed) {
      const still = embeds.find((e) => e.embed_id === currentEmbed.embed_id);
      if (still) await selectEmbed(still.embed_id);
    }
  }

  /* ---------- karaoke loop ---------- */

  /* Word classes are painted per frame for the active line only, so every line
     change must re-settle the others — otherwise jumping backwards leaves later
     lines looking already sung. */
  function repaintLineStates(lineNo, t) {
    const box = $("lyrics");
    box.querySelectorAll(".line").forEach((el) => {
      const no = Number(el.getAttribute("data-no"));
      const row = timings ? timings.lines.find((r) => r.line_no === no) : null;
      el.classList.toggle("active", no === lineNo);
      el.classList.toggle("done", !!row && no !== lineNo && row.end <= t);
      if (no !== lineNo) {
        el.querySelectorAll(".w").forEach((s) => s.classList.remove("now", "sung"));
      }
    });
  }

  // A singer needs to read ahead, so the box scrolls while LOOKAHEAD_LINES upcoming
  // lines are still below the active one instead of waiting for the bottom edge.
  const LOOKAHEAD_LINES = 2;

  function keepLineVisible(el, smooth) {
    const box = $("lyrics");
    let lead = 0;
    let next = el.nextElementSibling;
    for (let i = 0; i < LOOKAHEAD_LINES && next; i += 1) {
      lead += next.offsetHeight;
      next = next.nextElementSibling;
    }
    const top = el.offsetTop;
    const leadBottom = top + el.offsetHeight + lead;
    const viewTop = box.scrollTop;
    let target = null;
    if (leadBottom > viewTop + box.clientHeight) target = leadBottom - box.clientHeight;
    else if (top < viewTop) target = top - 8;
    if (target === null) return;
    box.scrollTo({ top: Math.max(0, target), behavior: smooth === false ? "auto" : "smooth" });
  }

  function setActiveLine(lineNo, scroll, speak) {
    if (lineNo === activeLineNo) return;
    activeLineNo = lineNo;
    const player = $("player");
    repaintLineStates(lineNo, player.currentTime + syncOffset);
    const el = $("lyrics").querySelector(`.line[data-no="${lineNo}"]`);
    if (el && scroll !== false) keepLineVisible(el, !player.paused);
    renderNowLine(lineNo);
    renderCaption(lineNo);
    // The intro shows the first line to read ahead of; singing it there would
    // run the translated voice ahead of the recording.
    if (speak !== false) speakLine(lineNo);
  }

  function moveBall(span) {
    const ball = $("ball");
    if (!span) { ball.classList.remove("on"); return; }
    const x = span.offsetLeft + span.offsetWidth / 2 - 9;
    const y = span.offsetTop - 20;
    ball.style.transform = `translate(${x}px, ${y}px)`;
    ball.classList.add("on");
  }

  function moveCapBall(span) {
    const ball = $("cap-ball");
    if (!span) { ball.classList.remove("on"); return; }
    const size = ball.offsetWidth || 16;
    const x = span.offsetLeft + span.offsetWidth / 2 - size / 2;
    const y = span.offsetTop - size - 4;
    ball.style.transform = `translate(${x}px, ${y}px)`;
    ball.classList.add("on");
  }

  function paintWords(row, t) {
    const box = $("lyrics");
    const cap = $("cap-line");
    let activeSpan = null;
    let activeCapSpan = null;
    let key = "";
    row.words.forEach((w) => {
      const capSpan = cap.querySelector(`.w[data-i="${w.index}"]`);
      if (capSpan) {
        const capNow = t >= w.start && t < w.end;
        capSpan.classList.toggle("now", capNow);
        capSpan.classList.toggle("sung", t >= w.end);
        if (capNow) activeCapSpan = capSpan;
      }
      const span = box.querySelector(`.w[data-no="${row.line_no}"][data-i="${w.index}"]`);
      if (!span) return;
      const isNow = t >= w.start && t < w.end;
      span.classList.toggle("now", isNow);
      span.classList.toggle("sung", t >= w.end);
      if (isNow) { activeSpan = span; key = `${row.line_no}:${w.index}`; }
    });
    if (!activeSpan && row.words.length) {
      const last = row.words[row.words.length - 1];
      if (t >= last.end) {
        activeSpan = box.querySelector(`.w[data-no="${row.line_no}"][data-i="${last.index}"]`);
        key = `${row.line_no}:${last.index}`;
      }
    }
    if (key !== activeWordKey) {
      activeWordKey = key;
      moveBall(activeSpan);
      moveCapBall(activeCapSpan || cap.querySelector(".w.sung:last-of-type"));
    }
  }

  function clearWordPaint() {
    const box = $("lyrics");
    $("cap-line").querySelectorAll(".w").forEach((s) => s.classList.remove("now", "sung"));
    box.querySelectorAll(".w").forEach((s) => s.classList.remove("now", "sung"));
    box.querySelectorAll(".line.done").forEach((el) => el.classList.remove("done"));
    activeWordKey = "";
    $("ball").classList.remove("on");
    $("cap-ball").classList.remove("on");
  }

  /* ---------- storyboard: backdrops, cast, camera, captions ---------- */

  function spriteHtml(member) {
    const svg = (board && board.sprites[member.kind]) || "";
    if (!svg) return "";
    const fit = [];
    if (member.flip) fit.push("scaleX(-1)");
    if (member.rot) fit.push(`rotate(${member.rot}deg)`);
    const style = `left:${member.x}%; top:${member.y}%; --s:${member.scale};` +
      ` --h:${member.height_pct || 20};`;
    const motionStyle = member.delay ? ` style="animation-delay:${member.delay}s"` : "";
    const fitStyle = fit.length ? ` style="transform:${fit.join(" ")}"` : "";
    return `<div class="sprite" style="${style}" data-kind="${esc(member.kind)}">` +
      `<div class="sprite-motion m-${esc(member.motion)}"${motionStyle}>` +
      `<div class="sprite-fit"${fitStyle}>${svg}</div></div></div>`;
  }

  function markSceneDots() {
    $("scene-dots").querySelectorAll("button").forEach((b) => {
      b.classList.toggle("on", Number(b.getAttribute("data-i")) === activeSceneIndex);
    });
  }

  function setScene(scene, force) {
    if (!scene) return;
    if (scene.scene_id === activeSceneId && !force) return;
    activeSceneId = scene.scene_id;
    activeSceneIndex = scene.index;
    $("backdrop").innerHTML = (board && board.backdrops[scene.backdrop]) || "";
    $("cast").innerHTML = scene.cast.map(spriteHtml).join("");
    $("scene-tag").textContent =
      `Scene ${scene.index + 1}/${board.scene_count} \u00b7 ${scene.title} \u00b7 ${scene.camera}`;
    $("cap-narration").textContent = scene.narration;
    const cam = $("camera");
    CAMERAS.forEach((name) => cam.classList.remove(`cam-${name}`));
    cam.style.setProperty("--cam-dur", `${Math.max(4, scene.duration).toFixed(2)}s`);
    void cam.offsetWidth;
    cam.classList.add(`cam-${scene.camera}`);
    markSceneDots();
    if ($("narrate").checked) speakNarration(scene);
  }

  function syncScene(t) {
    if (!board || !board.scenes.length) return;
    let scene = board.scenes.find((s) => t >= s.start && t < s.end);
    if (!scene) scene = t < board.scenes[0].start ? board.scenes[0] : board.scenes[board.scenes.length - 1];
    setScene(scene, false);
  }

  function renderCaption(lineNo) {
    const row = timings ? timings.lines.find((r) => r.line_no === lineNo) : null;
    const line = current ? current.lines.find((l) => l.line_no === lineNo) : null;
    if (!row || !line) { $("cap-line").innerHTML = ""; $("cap-tr").textContent = ""; return; }
    $("cap-line").innerHTML = row.words.map((w) =>
      `<span class="w" data-i="${w.index}">${esc(w.text)}</span>`).join(" ");
    const tr = trRow(lineNo);
    $("cap-tr").textContent = tr && tr.translation ? tr.translation : "";
    // While counting in, this line is the caption's tail — a "next line" hint here
    // would overwrite the countdown whenever the storyboard repaints.
    if (countInLineNo) return;
    const next = current.lines.find((l) => l.line_no === lineNo + 1);
    const nextTr = next ? trRow(next.line_no) : null;
    $("cap-next").textContent = next
      ? `\u2192 ${next.text}${nextTr && nextTr.translation ? ` \u00b7 ${nextTr.translation}` : ""}`
      : "";
  }

  /* ---------- speech: server neural voices first, device voice as fallback ----------

     A device can only speak the languages its OS shipped — macOS has no Khmer
     voice at all — so "Sing in Khmer" used to refuse outright. The server renders
     any of the 27 languages with a neural voice and the browser plays the MP3;
     the device voice remains the fallback when the server cannot render. */

  let serverVoices = null;
  let ttsAudio = null;
  let ttsToken = 0;
  let ttsFellBack = false;

  async function probeServerVoices() {
    try { serverVoices = await api("/api/music/tts/status"); }
    catch (_) { serverVoices = { available: false, engine: "none" }; }
    return serverVoices;
  }

  function serverVoicesReady() {
    return !!(serverVoices && serverVoices.available);
  }

  function voiceFor(tag) {
    const synth = window.speechSynthesis;
    if (!synth) return null;
    const voices = synth.getVoices() || [];
    const want = String(tag || "").toLowerCase().replace("_", "-");
    const base = want.split("-")[0];
    return voices.find((v) => (v.lang || "").toLowerCase().replace("_", "-") === want)
      || voices.find((v) => (v.lang || "").toLowerCase().replace("_", "-").startsWith(base))
      || null;
  }

  function canSpeak(langCode, tag) {
    return serverVoicesReady() || !!voiceFor(tag || langCode);
  }

  // Stops BOTH engines. Every pause/seek/stop path must call this, or server
  // audio would keep singing over the recording.
  function cancelSpeech() {
    ttsToken += 1;
    if (window.speechSynthesis) window.speechSynthesis.cancel();
    if (ttsAudio) {
      try { ttsAudio.pause(); } catch (_) { /* not started yet */ }
      ttsAudio.removeAttribute("src");
    }
  }

  function speakOnDevice(text, tag, rate, onDone) {
    const synth = window.speechSynthesis;
    if (!synth) return false;
    const utter = new SpeechSynthesisUtterance(text);
    utter.lang = tag || "en-US";
    utter.rate = rate || 1;
    // A tagged voice is better, but an engine that rejects the object should
    // still speak the line from the language tag alone.
    try {
      const voice = voiceFor(utter.lang);
      if (voice) utter.voice = voice;
    } catch (_) { /* keep utter.lang */ }
    if (onDone) { utter.onend = onDone; utter.onerror = onDone; }
    synth.speak(utter);
    return true;
  }

  function speak(text, opts) {
    const line = String(text || "").trim();
    const o = opts || {};
    const done = typeof o.onend === "function" ? o.onend : null;
    cancelSpeech();
    if (!line) { if (done) done(); return; }
    if (serverVoicesReady()) {
      if (!ttsAudio) ttsAudio = new Audio();
      const token = ttsToken;
      const stale = () => token !== ttsToken;
      ttsAudio.onended = () => { if (!stale() && done) done(); };
      ttsAudio.onerror = () => {
        // 501 (no engine, empty cache) or offline: try the device voice, and say
        // so once — silence with no explanation is what "not working" felt like.
        if (stale()) return;
        if (!ttsFellBack) {
          ttsFellBack = true;
          toast("Neural voice unavailable \u2014 using this device's voice");
        }
        if (!speakOnDevice(line, o.tag, o.rate, done) && done) done();
      };
      ttsAudio.src = `/api/music/tts?lang=${encodeURIComponent(o.lang || "en")}` +
        `&rate=${encodeURIComponent(Number(o.rate || 1).toFixed(2))}` +
        `&text=${encodeURIComponent(line)}`;
      const playing = ttsAudio.play();
      if (playing && playing.catch) playing.catch(() => { /* onerror handles it */ });
      return;
    }
    if (!speakOnDevice(line, o.tag, o.rate, done) && done) done();
  }

  function speakNarration(scene) {
    if (!scene.narration) return;
    const player = $("player");
    const code = scene.narration_language || "en";
    if (!canSpeak(code, code === "en" ? "en-US" : code)) return;
    if (!ducked) { duckedFrom = player.volume; ducked = true; }
    player.volume = Math.min(duckedFrom, 0.3);
    const restore = () => {
      if (!ducked) return;
      ducked = false;
      player.volume = duckedFrom;
    };
    speak(scene.narration, {
      lang: code,
      tag: code === "en" ? "en-US" : code,
      rate: 0.98,
      onend: restore,
    });
  }

  /* ---------- sing along in the learner's language ---------- */

  async function loadSingPlan() {
    singPlan = null;
    singingLineNo = 0;
    if (!current) return;
    const player = $("player");
    const duration = Number.isFinite(player.duration) && player.duration > 0 ? player.duration : 0;
    singPlan = await api(`/api/music/sing/${encodeURIComponent(current.song_id)}` +
      `?target_lang=${encodeURIComponent(lang())}` +
      (duration ? `&duration=${duration.toFixed(2)}` : ""));
  }

  function speakLine(lineNo) {
    if (!singPlan || !$("sing-lang").checked) return;
    // Sing-along follows the recording: a paused player must stay silent, or the
    // pause handler's cancel is undone by the next tick and the line sings on.
    if ($("player").paused) return;
    if (lineNo === singingLineNo) return;
    const row = singPlan.lines.find((r) => r.line_no === lineNo);
    if (!row || !row.speak) return;
    singingLineNo = lineNo;
    speak(row.speak, {
      lang: singPlan.language,
      tag: singPlan.voice_tag,
      rate: row.rate,
    });
  }

  function stopSinging() {
    cancelSpeech();
    singingLineNo = 0;
    const player = $("player");
    if (singBackedFrom !== null) { player.volume = singBackedFrom; singBackedFrom = null; }
  }

  async function toggleSinging() {
    const box = $("sing-lang");
    if (!box.checked) { stopSinging(); return; }
    if ($("narrate").checked) { $("narrate").checked = false; }
    try {
      await loadSingPlan();
    } catch (e) {
      box.checked = false;
      toast(String(e.message || e));
      return;
    }
    // Ticking the box while the first song is still loading leaves no plan.
    if (!singPlan) {
      box.checked = false;
      toast("Pick a song first");
      return;
    }
    if (!canSpeak(singPlan.language, singPlan.voice_tag)) {
      box.checked = false;
      toast(`No ${singPlan.language_name} voice on this device and the neural ` +
            `voice service is unavailable`);
      return;
    }
    const player = $("player");
    singBackedFrom = player.volume;
    player.volume = singPlan.backing_volume;
    const via = serverVoicesReady() ? "neural voice" : "device voice";
    toast(singPlan.word_by_word
      ? `${singPlan.language_name}: word by word (no full-line translation yet)`
      : `Singing in ${singPlan.language_name} (${via}) \u00b7 English is now the ` +
        `backing track`);
    speakLine(activeLineNo);
  }

  function refreshSingLabel() {
    const name = ($("meaning-lang").selectedOptions[0] || {}).textContent || "";
    $("sing-label").textContent = `Sing in ${name.replace(" \u2713", "").trim()}`;
  }

  function toggleTheater(on) {
    const stage = $("stage");
    const want = on === undefined ? !stage.classList.contains("theater") : !!on;
    stage.classList.toggle("theater", want);
    document.body.classList.toggle("theater-on", want);
    $("btn-theater").textContent = want ? "Exit full screen" : "Full screen";
    if (want && !document.fullscreenElement && stage.requestFullscreen) {
      stage.requestFullscreen().catch(() => undefined);
    }
    if (!want && document.fullscreenElement && document.exitFullscreen) {
      document.exitFullscreen().catch(() => undefined);
    }
  }

  function syncStore() {
    try { return JSON.parse(localStorage.getItem(SYNC_STORAGE_KEY) || "{}") || {}; }
    catch (_) { return {}; }
  }

  function saveSync() {
    if (!current) return;
    const store = syncStore();
    if (syncOffset) store[current.song_id] = syncOffset;
    else delete store[current.song_id];
    try { localStorage.setItem(SYNC_STORAGE_KEY, JSON.stringify(store)); }
    catch (_) { /* private mode: the nudge just won't outlive the tab */ }
  }

  function loadSync() {
    const saved = current ? Number(syncStore()[current.song_id]) : 0;
    syncOffset = Number.isFinite(saved) ? saved : 0;
    showSync();
  }

  // Latest line already started at t (null during the intro).
  function lineBefore(t) {
    if (!timings) return null;
    let found = null;
    for (const row of timings.lines) {
      if (row.start <= t) found = row; else break;
    }
    return found;
  }

  /* Songs open on instrumental bars — the travel words wait 3.1s. Highlighting
     line 1 there put the ball on a lyric nobody was singing yet, which reads as
     "the lyrics start too early", so the intro queues the line and counts in. */
  let countInLineNo = 0;

  function showCountIn(t) {
    const first = timings.lines[0];
    if (!first) return;
    if (countInLineNo !== first.line_no) {
      countInLineNo = first.line_no;
      activeLineNo = 0;
      clearWordPaint();
      $("lyrics").querySelectorAll(".line").forEach((el) => {
        el.classList.remove("active");
        const no = Number(el.getAttribute("data-no"));
        el.classList.toggle("upcoming", no === first.line_no);
      });
      // Read-ahead text without paint: the stage stays full, nothing looks sung.
      renderNowLine(first.line_no);
      renderCaption(first.line_no);
      clearWordPaint();
    }
    // Re-asserted rather than cached: loading the storyboard repaints the caption.
    const away = Math.ceil(Math.max(0, first.start - t));
    const label = away > 0 ? `Singing starts in ${away}\u2026` : "";
    const cap = $("cap-next");
    if (cap.textContent !== label) cap.textContent = label;
  }

  function clearCountIn() {
    if (!countInLineNo) return;
    countInLineNo = 0;
    $("lyrics").querySelectorAll(".line.upcoming").forEach((el) => {
      el.classList.remove("upcoming");
    });
  }

  function tick() {
    const player = $("player");
    if (!timings) return;
    const t = player.currentTime + syncOffset;
    syncScene(t);
    if (activeClip && player.currentTime >= activeClip.end_sec) {
      player.pause();
      activeClip = null;
      renderClips();
    }
    let row = timings.lines.find((r) => t >= r.start && t < r.end);
    if (!row && timings.lines.length) {
      // Measured timings leave the instrumental bars empty. Hold the line that
      // was just sung instead of snapping to the end of the song.
      row = lineBefore(t);
    }
    if (row) {
      clearCountIn();
      setActiveLine(row.line_no, true);
      // Also speak when the line was already showing through a rest.
      speakLine(row.line_no);
      paintWords(row, t);
    } else {
      showCountIn(t);
    }
    if (!player.paused && !player.ended) rafId = requestAnimationFrame(tick);
  }

  function startLoop() {
    cancelAnimationFrame(rafId);
    rafId = requestAnimationFrame(tick);
  }

  // requestAnimationFrame is throttled in background tabs, so timeupdate keeps
  // the line, the scene and the captions honest while the tab is hidden.
  function syncActiveLineFromPlayer() {
    if (document.hidden || $("player").paused) tick();
  }

  /* ---------- data loading ---------- */

  async function loadTranslation() {
    if (!current) return;
    const key = `${current.song_id}|${lang()}`;
    if (trCache.has(key)) {
      translation = trCache.get(key);
    } else {
      translation = await post("/api/music/translate", {
        song_id: current.song_id, target_lang: lang(), allow_llm: true,
      });
      trCache.set(key, translation);
    }
    renderTierMeta();
  }

  async function loadClips() {
    if (!current) return;
    const data = await api(`/api/music/clips?song_id=${encodeURIComponent(current.song_id)}` +
      `&target_lang=${encodeURIComponent(lang())}`);
    clips = data.clips || [];
    renderClips();
  }

  async function loadTimings() {
    if (!current) return;
    const player = $("player");
    const duration = Number.isFinite(player.duration) && player.duration > 0 ? player.duration : 0;
    timings = await api(`/api/music/timing/${encodeURIComponent(current.song_id)}` +
      (duration ? `?duration=${duration.toFixed(2)}` : ""));
    const el = $("timing-source");
    if (el) {
      el.textContent = timings.aligned
        ? `Lyrics aligned to the vocals \u00b7 sings from ${timings.lead_in_sec.toFixed(1)}s`
        : "Lyrics timed by syllable estimate";
    }
  }

  async function loadStoryboard() {
    const stage = $("stage");
    board = null;
    activeSceneId = "";
    activeSceneIndex = -1;
    if (!current) return;
    const player = $("player");
    const duration = Number.isFinite(player.duration) && player.duration > 0 ? player.duration : 0;
    try {
      board = await api(`/api/music/storyboard/${encodeURIComponent(current.song_id)}` +
        `?target_lang=${encodeURIComponent(lang())}` +
        (duration ? `&duration=${duration.toFixed(2)}` : ""));
    } catch (_) {
      board = null;
    }
    if (!board || !board.scenes.length) {
      stage.classList.add("no-board");
      $("scene-dots").innerHTML = "";
      $("btn-theater").disabled = true;
      return;
    }
    stage.classList.remove("no-board");
    $("btn-theater").disabled = false;
    $("scene-dots").innerHTML = board.scenes.map((s) =>
      `<button type="button" data-i="${s.index}" title="${esc(s.title)}">${s.index + 1}</button>`
    ).join("");
    $("scene-dots").querySelectorAll("button").forEach((b) => {
      b.onclick = () => {
        const scene = board.scenes[Number(b.getAttribute("data-i"))];
        if (!scene) return;
        $("player").currentTime = Math.max(0, scene.start - syncOffset);
        setScene(scene, true);
      };
    });
    const at = board.scenes.find((s) => {
      const t = $("player").currentTime + syncOffset;
      return t >= s.start && t < s.end;
    });
    setScene(at || board.scenes[0], true);
  }

  async function selectSong(songId) {
    const player = $("player");
    player.pause();
    cancelAnimationFrame(rafId);
    activeClip = null;
    stopSinging();
    current = await api("/api/music/songs/" + encodeURIComponent(songId));
    loadSync();
    $("now-title").textContent = current.title_en;
    $("now-meta").textContent =
      `${current.topic} \u00b7 ${current.lines.length} lines \u00b7 ${current.license}`;
    const anim = current.animation || "pulse";
    $("stage").dataset.anim = anim;
    $("stage").classList.remove("playing");
    $("stage-symbol").textContent = SYMBOLS[anim] || "\u266A";
    player.src = current.audio_url || "";
    ["btn-play", "btn-pause", "btn-restart"].forEach((id) => { $(id).disabled = !player.src; });
    await loadTimings();
    await loadTranslation();
    renderLyrics();
    // Paused at 0:00 the song has not started, so queue line 1 rather than
    // lighting it up as if it were being sung.
    showCountIn(0);
    renderSongList();
    await loadStoryboard();
    if ($("sing-lang").checked) {
      try { await loadSingPlan(); } catch (_) { $("sing-lang").checked = false; }
    }
    await Promise.all([loadClips(), loadVideos()]);
    // The storyboard and sing plan repaint the captions, so the count-in goes last.
    if (!activeLineNo) showCountIn(player.currentTime + syncOffset);
  }

  async function loadVideos() {
    const id = current ? current.song_id : "";
    const data = await api(`/api/music/videos?song_id=${encodeURIComponent(id)}`);
    renderVideos(data.videos || []);
  }

  async function playClip(clipId) {
    const clip = clips.find((c) => c.clip_id === clipId);
    if (!clip) return;
    const player = $("player");
    activeClip = clip;
    renderClips();
    player.currentTime = Math.max(0, clip.start_sec - syncOffset);
    try {
      await player.play();
      startLoop();
      toast(`Clip: ${clip.title}`);
    } catch (_) {
      toast("Tap play once, then choose the clip again");
    }
  }

  /* ---------- ask AI ---------- */

  async function askAI(question) {
    if (!current) return;
    const q = (question || $("ask-input").value || "").trim();
    if (!q) { toast("Type a question first"); return; }
    $("ask-answer").textContent = "Thinking\u2026";
    try {
      const data = await post("/api/music/ask", {
        song_id: current.song_id,
        question: q,
        line_no: activeLineNo || 1,
        target_lang: lang(),
      });
      const source = data.provider === "xai" ? "Grok" : "offline teacher";
      $("ask-answer").innerHTML = `${esc(data.answer)}
        <div class="meta">${esc(source)} \u00b7 grounded in lines ${data.cited_lines.join(", ")}</div>`;
    } catch (e) {
      $("ask-answer").textContent = String(e.message || e);
    }
  }

  /* ---------- wiring ---------- */

  $("btn-play").onclick = async () => {
    const player = $("player");
    if (!player.src) return;
    activeClip = null;
    try {
      await player.play();
      startLoop();
    } catch (_) {
      toast("Could not play audio \u2014 press Play again");
    }
  };
  $("btn-pause").onclick = () => { $("player").pause(); };
  $("btn-restart").onclick = async () => {
    const player = $("player");
    activeClip = null;
    player.currentTime = 0;
    clearWordPaint();
    try { await player.play(); startLoop(); } catch (_) { /* user gesture needed */ }
  };
  $("player").addEventListener("play", () => {
    $("stage").classList.add("playing");
    $("btn-stage-play").textContent = "Pause";
    startLoop();
  });
  $("player").addEventListener("pause", () => {
    $("stage").classList.remove("playing");
    $("btn-stage-play").textContent = "Play";
    cancelAnimationFrame(rafId);
    cancelSpeech();
    singingLineNo = 0;
  });
  $("player").addEventListener("ended", () => {
    $("stage").classList.remove("playing");
    $("btn-stage-play").textContent = "Play";
    cancelAnimationFrame(rafId);
    clearWordPaint();
    cancelSpeech();
    singingLineNo = 0;
  });
  $("player").addEventListener("seeked", () => {
    activeWordKey = "";
    // A seek lands mid-line: forget what was sung so the new line speaks again.
    singingLineNo = 0;
    cancelSpeech();
    repaintLineStates(activeLineNo, $("player").currentTime + syncOffset);
    tick();
  });
  $("player").addEventListener("timeupdate", syncActiveLineFromPlayer);
  $("player").addEventListener("loadedmetadata", async () => {
    await loadTimings();
    renderLyrics();
    if (activeLineNo) { const no = activeLineNo; activeLineNo = 0; setActiveLine(no, false); }
    else showCountIn($("player").currentTime + syncOffset);
    await loadStoryboard();
  });
  $("meaning-lang").onchange = async () => {
    refreshSingLabel();
    await loadTranslation();
    renderLyrics();
    const no = activeLineNo || (current && current.lines[0] ? current.lines[0].line_no : 0);
    activeLineNo = 0;
    if (no) setActiveLine(no, false);
    if ($("sing-lang").checked) { stopSinging(); await loadSingPlan(); }
    await Promise.all([loadClips(), loadStoryboard(), loadEmbeds()]);
  };
  $("sing-lang").onchange = () => { toggleSinging(); };
  $("btn-theater").onclick = () => toggleTheater();
  $("btn-embed-play").onclick = () => {
    pauseLocked = false;
    playMedia();
  };
  $("btn-embed-pause").onclick = () => {
    pauseMedia();
    if (activeVerseNo) showPauseCard(activeVerseNo, true);
  };
  $("btn-embed-continue").onclick = () => {
    pauseLocked = false;
    $("pause-card").hidden = true;
    playMedia();
  };
  $("embed-ask-send").onclick = () => askEmbed();
  $("embed-ask-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter") askEmbed();
  });
  $("embed-ask-quick").innerHTML = EMBED_QUICK.map((q) =>
    `<button class="chip" type="button" data-q="${esc(q)}">${esc(q)}</button>`).join("");
  $("embed-ask-quick").querySelectorAll("button").forEach((b) => {
    b.onclick = () => askEmbed(b.getAttribute("data-q"));
  });

  async function togglePlay() {
    const player = $("player");
    if (!player.src) return;
    if (player.paused) {
      try { await player.play(); startLoop(); } catch (_) { toast("Press play again"); }
    } else {
      player.pause();
    }
  }
  $("btn-stage-play").onclick = () => togglePlay();
  $("narrate").onchange = () => {
    if ($("narrate").checked && $("sing-lang").checked) {
      $("sing-lang").checked = false;
      stopSinging();
    }
    if (!$("narrate").checked) {
      cancelSpeech();
      if (ducked) { ducked = false; $("player").volume = duckedFrom; }
      return;
    }
    const scene = board && board.scenes.find((s) => s.scene_id === activeSceneId);
    if (scene) speakNarration(scene);
  };
  document.addEventListener("fullscreenchange", () => {
    if (!document.fullscreenElement && $("stage").classList.contains("theater")) {
      toggleTheater(false);
    }
  });
  document.addEventListener("keydown", (e) => {
    const typing = /^(INPUT|TEXTAREA|SELECT)$/.test((e.target && e.target.tagName) || "");
    if (typing) return;
    if (e.key === "f" || e.key === "F") toggleTheater();
    if (e.key === "Escape" && $("stage").classList.contains("theater")) toggleTheater(false);
    if (e.key === " " || e.code === "Space") { e.preventDefault(); togglePlay(); }
  });
  $("show-inline").onchange = () => {
    const no = activeLineNo;
    renderLyrics();
    if (no) setActiveLine(no, false);
  };
  function showSync() {
    const sign = syncOffset >= 0 ? "" : "\u2212";
    $("sync-value").textContent = `${sign}${Math.abs(syncOffset).toFixed(2)}s`;
  }
  function setSync(delta) {
    syncOffset = Math.round((syncOffset + delta) * 100) / 100;
    showSync();
    saveSync();
    activeWordKey = "";
    repaintLineStates(activeLineNo, $("player").currentTime + syncOffset);
    tick();
  }
  $("sync-back").onclick = () => setSync(-0.25);
  $("sync-fwd").onclick = () => setSync(0.25);
  $("sync-reset").onclick = () => {
    syncOffset = 0;
    showSync();
    saveSync();
    activeWordKey = "";
    repaintLineStates(activeLineNo, $("player").currentTime);
    tick();
  };
  $("ask-send").onclick = () => askAI();
  $("ask-input").addEventListener("keydown", (e) => { if (e.key === "Enter") askAI(); });
  $("btn-hear-model").onclick = () => hearPronounceModel();
  $("btn-mic").onclick = () => {
    if (micListening) { stopMic(); return; }
    startMic();
  };
  $("btn-check-typed").onclick = () => checkPronunciation($("pronounce-heard").value);
  $("pronounce-heard").addEventListener("keydown", (e) => {
    if (e.key === "Enter") checkPronunciation($("pronounce-heard").value);
  });
  ["practice-en", "practice-tr"].forEach((id) => {
    const el = $(id);
    if (el) el.onchange = () => {
      refreshPronounceTarget();
      const box = $("pronounce-result");
      if (box) box.hidden = true;
    };
  });

  (async function boot() {
    // Chrome fills the voice list asynchronously; ask early so the sing toggle
    // does not report "no voice" on a first click.
    if (window.speechSynthesis) window.speechSynthesis.getVoices();
    // Probed once, not per line: the sing toggle needs to know whether the
    // server can render a language the device has no voice for.
    await probeServerVoices();
    $("ask-quick").innerHTML = QUICK_ASKS.map((q) =>
      `<button class="chip" type="button" data-q="${esc(q)}">${esc(q)}</button>`).join("");
    $("ask-quick").querySelectorAll("button").forEach((b) => {
      b.onclick = () => askAI(b.getAttribute("data-q"));
    });
    const langs = await api("/api/music/languages");
    const cat = langs.catalog || [];
    // Every language is selectable; the groups say which ones have hand-authored
    // sentences, because a bare tick beside six of them read as "only these six".
    const full = cat.filter((row) => row.curated);
    const glossed = cat.filter((row) => !row.curated);
    const optionsFor = (rows) => rows.map((row) =>
      `<option value="${esc(row.code)}">${esc(row.name)}</option>`).join("");
    $("meaning-lang").innerHTML = [
      ["Full-line translations", full],
      ["Word-by-word glosses", glossed],
    ].filter(([, rows]) => rows.length).map(([label, rows]) =>
      `<optgroup label="${esc(label)} (${rows.length})">${optionsFor(rows)}</optgroup>`
    ).join("");
    $("meaning-lang").value = "es";
    refreshSingLabel();
    const data = await api("/api/music/featured");
    featured = data.songs || [];
    const voiceNote = serverVoicesReady()
      ? ` \u00b7 neural voices for ${serverVoices.languages} languages`
      : " \u00b7 singing uses this device's installed voices";
    $("catalog-meta").textContent =
      `${featured.length} featured with audio \u00b7 ${langs.count || 26} translation ` +
      `languages \u00b7 ${full.length} with full-line sentences${voiceNote}`;
    renderSongList();
    await loadEmbeds();
    if (featured[0]) await selectSong(featured[0].song_id);
  })().catch((e) => toast(String(e.message || e)));
"""

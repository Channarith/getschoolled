"""HTML shell for the children webcam lab."""

from __future__ import annotations

FAVICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
<rect width="64" height="64" rx="16" fill="#6d28d9"/><path d="M12 35Q32 7 52 35Q32 58 12 35" fill="#fde68a"/>
<circle cx="25" cy="31" r="3" fill="#312e81"/><circle cx="39" cy="31" r="3" fill="#312e81"/>
<path d="M25 41Q32 47 39 41" fill="none" stroke="#312e81" stroke-width="3" stroke-linecap="round"/></svg>"""


def render_children_page(asset_tag: str = "") -> str:
    """The page shell.

    ``asset_tag`` is appended to the script and stylesheet URLs. Without it a
    browser happily reuses a cached ``app.js`` after an update, which looks
    exactly like "the fix did nothing" — and because static files are read from
    disk while this HTML comes from the running process, a stale page can also
    end up paired with a newer script.
    """
    return _PAGE.replace("__ASSET_TAG__", f"?v={asset_tag}" if asset_tag else "")


_PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
  <title>Theodore's Webcam Play Lab</title>
  <link rel="stylesheet" href="/static/app.css__ASSET_TAG__">
</head>
<body>
  <main id="app">
    <section id="setup" class="setup">
      <div class="theodore-card">
        <div class="theodore" aria-hidden="true"><span class="ear left"></span><span class="ear right"></span><span class="face">ʕ•ᴥ•ʔ</span></div>
        <div><p class="eyebrow">THEODORE'S WEBCAM PLAY LAB</p><h1>Move, make faces, trace, and laugh!</h1>
        <p>Camera games for ages 4–10. Video stays in this browser. No recordings or Face ID.</p></div>
      </div>
      <div class="setup-grid">
        <label>Age group<select id="age"><option value="4-6">4–6</option><option value="7-10" selected>7–10</option></select></label>
        <label>Theme<select id="theme"><option value="mix">Mix everything</option><option value="cuddly">Cuddly</option><option value="hero">Hero & adventure</option></select></label>
        <label class="check"><input id="seated" type="checkbox"> Seated-only movement</label>
        <label class="check"><input id="share" type="checkbox"> Share anonymous lab stats</label>
      </div>
      <div class="privacy"><strong>Adult check:</strong> Make a clear play space. Camera landmarks and speech audio are processed by the browser; our server never receives camera frames or audio.</div>
      <button id="start" class="primary">Allow camera and start playing</button>
      <button id="demo" class="secondary">Try pointer demo without camera</button>
    </section>

    <section id="play" class="play hidden" aria-live="polite">
      <div class="topbar">
        <button id="home" aria-label="Back to setup">⌂</button>
        <div class="brand">Theodore Play Lab</div>
        <div class="score"><span id="stars">☆☆☆</span><span id="fun-score">Fun 0</span><span id="combo">Combo 0</span></div>
        <button id="mute" aria-pressed="false">🔊</button>
        <button id="fullscreen">⛶</button>
      </div>
      <div id="stage" class="stage">
        <video id="camera" autoplay playsinline muted></video>
        <div id="guide-layer" class="guide-layer" aria-hidden="true">
          <span id="guide-glyph" class="guide-glyph">A</span>
          <i id="guide-start" class="guide-start"></i>
        </div>
        <canvas id="overlay"></canvas>
        <div id="sprite-layer" class="sprite-layer" aria-hidden="true"></div>
        <div id="target" class="target hidden"></div>
        <div id="prompt" class="prompt"><strong id="prompt-title">Choose a game</strong><span id="prompt-copy">Theodore is ready!</span></div>
        <div id="countdown" class="countdown hidden"></div>
        <div id="vision-status" class="vision-status">Camera off</div>
        <div id="vision-readout" class="vision-readout" aria-live="off">
          <span id="face-readout">Face: waiting</span>
          <span id="hand-readout">Hands: waiting</span>
          <span id="distance-readout">Distance: waiting</span>
          <span id="motion-readout">Motion: 0 px</span>
          <span id="trace-readout">Trace: 0%</span>
          <span id="game-readout">Gesture: waiting</span>
        </div>
      </div>
      <details class="vision-tools" open>
        <summary>Vision testing overlays</summary>
        <div class="vision-switches">
          <label><input id="show-guide" type="checkbox" checked> Letter / character</label>
          <label><input id="show-face" type="checkbox" checked> Face contour</label>
          <label><input id="show-hands" type="checkbox" checked> Hand skeletons</label>
          <label><input id="show-trail" type="checkbox" checked> Hand movement trail</label>
          <label><input id="show-measures" type="checkbox" checked> Distance & measurements</label>
          <label><input id="show-readout" type="checkbox" checked> Live recognition readout</label>
        </div>
        <p>Face processing means landmark and expression detection only. It does not identify who you are.</p>
      </details>
      <div class="controls">
        <select id="game" aria-label="Game">
          <optgroup label="Learn">
            <option value="trace-letter">Trace a letter</option><option value="trace-picture">Trace a picture</option>
            <option value="say-letter">Say the letter</option>
          </optgroup>
          <optgroup label="Face & hands">
            <option value="oh-behave">Oh behave</option><option value="heart">Make hearts</option>
            <option value="idea">I have an idea</option><option value="fist-bump">Fist bump</option>
            <option value="wow">Wow face</option><option value="blow-kiss">Blow a kiss</option>
            <option value="wink">Wink challenge</option><option value="make-pose">Make a hero pose</option>
            <option value="balloon">Pop balloons</option>
            <option value="fish">Catch flying fish</option><option value="popcorn">Catch popcorn</option>
          </optgroup>
          <optgroup label="Move">
            <option value="fruit-cut">Fruit cut</option><option value="air-drums">Air drums</option>
            <option value="bird-flap">Flap like a bird</option><option value="head-bop">Head bop</option>
            <option value="face-chase">Face chase</option><option value="stand-sit">Stand up, sit down</option>
            <option value="dance-freeze">Dance freeze</option><option value="rainbow-reach">Rainbow reach</option>
          </optgroup>
        </select>
        <label>Letter<select id="letter"></select></label>
        <button id="play-game" class="primary">Play</button>
        <button id="hear">Hear Theodore</button>
        <button id="mic">🎤 Say it</button>
        <input id="typed" placeholder="Type what was said">
        <button id="check">Check typed</button>
        <button id="undo">Undo</button>
      </div>
      <details class="dashboard"><summary>Parent Fun dashboard</summary>
        <div id="dashboard"></div><button id="clear-data">Clear progress & analytics</button>
      </details>
    </section>
  </main>
  <script type="module" src="/static/app.js__ASSET_TAG__"></script>
</body>
</html>"""

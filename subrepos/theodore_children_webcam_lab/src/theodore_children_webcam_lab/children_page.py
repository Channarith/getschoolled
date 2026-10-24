"""HTML shell for the children webcam lab."""

from __future__ import annotations

from .game_engine import GAME_MENU

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
    groups = []
    for label, games in GAME_MENU:
        options = "".join(
            f'<option value="{game_id}">{title}</option>'
            for game_id, title in games
        )
        groups.append(f'<optgroup label="{label}">{options}</optgroup>')
    game_select = (
        '<label>Game<select id="game" aria-label="Choose a Play Lab game">'
        + "".join(groups)
        + "</select></label>"
    )
    return (
        _PAGE.replace("__GAME_SELECT__", game_select)
        .replace("__ASSET_TAG__", f"?v={asset_tag}" if asset_tag else "")
    )


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
        <img class="sala-hero" src="/static/sala-hero.png" alt="Sala, your guide" width="120" height="160">
        <div><p class="eyebrow" data-i18n="eyebrow">THEODORE'S WEBCAM PLAY LAB</p><h1 data-i18n="headline">Move, make faces, color, and laugh!</h1>
        <p data-i18n="intro">Camera games and listening games for ages 4–10. Video stays in this browser. No recordings or Face ID.</p></div>
      </div>
      <div class="setup-grid">
        <label><span data-i18n="age">Age group</span><select id="age"><option value="4-6">4–6</option><option value="7-10" selected>7–10</option><option value="11-17">11–17</option><option value="adult">Adult 18+</option></select></label>
        <label><span data-i18n="theme">Theme</span><select id="theme"><option value="mix" data-i18n="mix">Mix everything</option><option value="cuddly" data-i18n="cuddly">Cuddly</option><option value="hero" data-i18n="hero">Hero & adventure</option></select></label>
        <label class="check"><input id="seated" type="checkbox"> <span data-i18n="seated">Seated-only movement</span></label>
        <label class="check"><input id="share" type="checkbox"> <span data-i18n="share">Share anonymous lab stats</span></label>
      </div>
      <div class="privacy" data-i18n="privacy"><strong>Adult check:</strong> Make a clear play space. Camera landmarks and speech audio are processed by the browser; our server never receives camera frames or audio.</div>
      <button id="start" class="primary" data-i18n="start">Allow camera and start playing</button>
      <button id="demo" class="secondary" data-i18n="demo">Try pointer demo without camera</button>
      <button id="vision-check-open" class="linklike" type="button">Camera trouble? Run the camera check</button>
    </section>

    <section id="play" class="play hidden" aria-live="polite">
      <div class="topbar">
        <button id="home" aria-label="Back to setup">⌂</button>
        <div class="brand">Theodore Play Lab</div>
        <div class="score"><span id="stars">☆☆☆</span><span id="fun-score">Fun 0</span><span id="combo">Combo 0</span></div>
        <button id="mute" aria-pressed="false">🔊</button>
        <span id="clone-voice-slot" class="clone-voice-slot"></span>
        <button id="chrome-toggle" type="button" hidden aria-pressed="false">Hide options</button>
        <div id="touch-mode" class="touch-mode" role="radiogroup" hidden aria-label="Air touch selected. Screen touch is also available.">
          <button id="touch-air" type="button" data-touch="air" role="radio" aria-checked="true">Air touch</button>
          <button id="touch-screen" type="button" data-touch="screen" role="radio" aria-checked="false">Screen touch</button>
        </div>
        <button id="fullscreen">⛶</button>
      </div>
      <div id="stage" class="stage" role="region" aria-labelledby="stage-label" aria-describedby="stage-desc">
        <p id="stage-label" class="sr-only">Play Lab camera stage</p>
        <p id="stage-desc" class="sr-only">Camera games run here. Video stays in your browser; use the game selector below to choose an activity.</p>
        <video id="camera" autoplay playsinline muted aria-label="Play Lab camera preview"></video>
        <button id="sala-ask" type="button" aria-label="Tap Sala to ask">Sala</button>
        <div id="guide-layer" class="guide-layer" aria-hidden="true">
          <span id="guide-glyph" class="guide-glyph">A</span>
          <i id="guide-start" class="guide-start"></i>
        </div>
        <canvas id="overlay"></canvas>
        <div id="sprite-layer" class="sprite-layer" aria-hidden="true"></div>
        <div id="target" class="target hidden"></div>
        <div id="prompt" class="prompt"><strong id="prompt-title">Choose a game</strong><span id="prompt-copy">Theodore is ready!</span></div>
        <p id="presence-note" class="presence-note" hidden></p>
        <div id="countdown" class="countdown hidden" aria-live="polite" aria-label="Time left"></div>
        <div id="play-clock" class="play-clock" hidden aria-live="polite" aria-label="Play session time left">
          <span id="play-clock-time">10:00</span>
          <small>play time</small>
        </div>
        <div id="vision-status" class="vision-status">Camera off</div>
        <div id="vision-readout" class="vision-readout" aria-live="off">
          <span id="face-readout">Face: waiting</span>
          <span id="hand-readout">Hands: waiting</span>
          <span id="distance-readout">Distance: waiting</span>
          <span id="motion-readout">Motion: 0 px</span>
          <span id="trace-readout">Trace: 0%</span>
          <span id="game-readout">Gesture: waiting</span>
        </div>
        <div id="screen-catcher" class="screen-catcher" hidden></div>
        <iframe id="karaoke-frame" class="karaoke-frame hidden" title="Karaoke sing-along" allow="autoplay; fullscreen"></iframe>
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
      <p id="spoken-words" class="spoken-words hidden" aria-live="polite"></p>
      <div class="controls">
__GAME_SELECT__
        <label id="letter-control">Letter<select id="letter"></select></label>
        <label>Pace<select id="pace" aria-label="How long to wait after a success">
          <option value="patient" selected>Patient</option>
          <option value="steady">Steady</option>
          <option value="quick">Quick</option>
        </select></label>
        <label id="mirror-pace-control" class="hidden">Challenge pace<select id="mirror-pace" aria-label="Vision challenge pace">
          <option value="easy">Easy</option>
          <option value="family" selected>Family</option>
          <option value="sharp">Sharp</option>
        </select></label>
        <span id="ninja-technique-control" class="hidden ninja-controls">
          <label>Element<select id="ninja-element" aria-label="Ninja Weave element"></select></label>
          <label>Technique<select id="ninja-technique" aria-label="Ninja Weave technique"></select></label>
          <span id="ninja-progress" class="ninja-progress" aria-live="polite"></span>
        </span>
        <button id="play-game" class="primary" data-i18n="play">Play</button>
        <button id="hear" data-i18n="hear">Hear Theodore</button>
        <button id="mic" data-i18n="say">🎤 Say it</button>
        <input id="typed" placeholder="Type what was said">
        <button id="check">Check typed</button>
        <button id="undo">Undo</button>
        <label id="words-toggle" class="check hidden"><input id="show-words" type="checkbox" aria-label="Show the words Theodore said"> Words</label>
      </div>
      <details class="dashboard"><summary>Parent Fun dashboard</summary>
        <div id="dashboard"></div><button id="clear-data">Clear progress & analytics</button>
      </details>
    </section>
  </main>
  <script>
  (function () {
    var raw = "";
    try {
      raw = (new URLSearchParams(location.search).get("lang") || "").trim().toLowerCase().replace(/_/g, "-");
    } catch (e) {}
    var lang = raw;
    if (lang === "yue" || lang.indexOf("yue-") === 0 || lang === "zh-hk" || lang.indexOf("zh-hk") === 0 || lang === "zh-mo" || lang.indexOf("zh-mo") === 0 || lang === "cantonese") lang = "yue";
    else if (lang === "km" || lang.indexOf("km-") === 0) lang = "km";
    else lang = lang.split("-")[0] || "";
    if (!lang || lang === "en") return;
    var chrome = {
      zh: {
        eyebrow: "西奥多的摄像头游戏室", headline: "动一动，做鬼脸，涂颜色，笑出来！",
        intro: "适合 4–10 岁的摄像头游戏和聆听游戏。视频留在这个浏览器里。不录音，也不做人脸识别。",
        age: "年龄组", theme: "主题", mix: "全部混合", cuddly: "软萌", hero: "英雄与冒险",
        seated: "只做坐着的动作", share: "分享匿名实验数据",
        privacy: "成人确认：留出安全的活动空间。摄像头关键点和语音由浏览器处理；我们的服务器收不到画面或声音。",
        start: "允许摄像头并开始玩", demo: "不用摄像头，试试指针演示",
        play: "开始", hear: "听西奥多说", say: "🎤 说出来",
        pauseLine: "我们检测到你离开了摄像头。游戏已暂停，你回来后会继续。",
        resumeLine: "你回到摄像头前了。我们从同一个地方继续。"
      },
      yue: {
        eyebrow: "西奧多嘅鏡頭遊戲室", headline: "郁一郁，做鬼臉，填顏色，笑出嚟！",
        intro: "適合 4–10 歲嘅鏡頭遊戲同聆聽遊戲。影片留喺呢個瀏覽器。唔錄音，亦唔做人臉識別。",
        age: "年齡組", theme: "主題", mix: "全部混合", cuddly: "軟萌", hero: "英雄同冒險",
        seated: "只做坐住嘅動作", share: "分享匿名實驗數據",
        privacy: "成人確認：留出安全嘅活動空間。鏡頭關鍵點同語音由瀏覽器處理；我哋嘅伺服器收唔到畫面或者聲音。",
        start: "允許鏡頭並開始玩", demo: "唔使鏡頭，試下指標示範",
        play: "開始", hear: "聽西奧多講", say: "🎤 講出嚟",
        pauseLine: "我哋偵測到你離開咗鏡頭。遊戲已暫停，你返嚟之後會繼續。",
        resumeLine: "你返到鏡頭前面。我哋由同一個地方繼續。"
      },
      km: {
        eyebrow: "បន្ទប់លេងកាមេរ៉ារបស់ Theodore", headline: "កម្រើក ធ្វើមុខ លាបពណ៌ ហើយសើច!",
        intro: "ល្បែងកាមេរ៉ា និងល្បែងស្តាប់សម្រាប់អាយុ ៤–១០។ វីដេអូនៅក្នុងកម្មវិធីរុករកនេះ។ គ្មានការថត ឬស្គាល់មុខ។",
        age: "ក្រុមអាយុ", theme: "រូបរាង", mix: "លាយទាំងអស់", cuddly: "គួរឱ្យស្រឡាញ់", hero: "វីរបុរស និងដំណើរផ្សងព្រេង",
        seated: "ចលនាពេលអង្គុយប៉ុណ្ណោះ", share: "ចែករំលែកស្ថិតិមន្ទីរពិសោធន៍អនាមិក",
        privacy: "ការពិនិត្យមនុស្សធំ៖ រៀបកន្លែងលេងឱ្យច្បាស់។ ចំណុចកាមេរ៉ា និងសំឡេងដំណើរការដោយកម្មវិធីរុករក។ ម៉ាស៊ីនមេរបស់យើងមិនទទួលរូប ឬសំឡេង។",
        start: "អនុញ្ញាតកាមេរ៉ា ហើយចាប់ផ្តើមលេង", demo: "សាកល្បងទ្រនិចដោយគ្មានកាមេរ៉ា",
        play: "លេង", hear: "ស្តាប់ Theodore", say: "🎤 និយាយ",
        pauseLine: "យើងបានរកឃើញថាអ្នកបានចេញពីកាមេរ៉ា។ ល្បែងបានផ្អាក ហើយនឹងបន្តពេលអ្នកត្រឡប់មកវិញ។",
        resumeLine: "អ្នកបានត្រឡប់មកកាមេរ៉ាវិញ។ យើងនឹងបន្តពីកន្លែងដដែល។"
      }
    };
    var pack = chrome[lang] || (lang === "zh" ? chrome.zh : null);
    if (pack) {
      window.__LAB_CHROME = pack;
      document.querySelectorAll("[data-i18n]").forEach(function (el) {
        var key = el.getAttribute("data-i18n");
        if (key && pack[key]) el.textContent = pack[key];
      });
    }
    var bcp = lang === "yue" ? "zh-HK" : (lang === "km" ? "km-KH" : lang);
    try { document.documentElement.lang = lang; } catch (e) {}
    var orig = window.fetch;
    if (typeof orig === "function") {
      window.fetch = function (input, init) {
        if (typeof input === "string" && input.indexOf("/api/tts?") >= 0) {
          if (/[?&]language=/.test(input)) input = input.replace(/([?&]language=)[^&]*/, "$1" + encodeURIComponent(lang));
          else input += (input.indexOf("?") >= 0 ? "&" : "?") + "language=" + encodeURIComponent(lang);
        }
        return orig.call(this, input, init);
      };
    }
    ["SpeechRecognition", "webkitSpeechRecognition"].forEach(function (name) {
      var Ctor = window[name];
      if (typeof Ctor !== "function") return;
      function Wrapped() {
        var rec = new Ctor();
        try { rec.lang = bcp; } catch (e) {}
        try {
          Object.defineProperty(rec, "lang", { configurable: true, get: function () { return bcp; }, set: function () {} });
        } catch (e) {}
        return rec;
      }
      Wrapped.prototype = Ctor.prototype;
      window[name] = Wrapped;
    });
  })();
  </script>
  <script src="/static/friendly_error.js__ASSET_TAG__" data-watch="^/api/child/" data-ignore="/tts"></script>
  <script type="module" src="/static/app.js__ASSET_TAG__"></script>
</body>
</html>"""

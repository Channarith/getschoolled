/* Runtime for the labs (children lab, course studio, voice pages): show the friendly
   screen over the page when an important API call fails, and quietly retry transient
   failures first. Needs ART, COPY, PAGE_CSS, KIND_MOOD, classifyStatus in scope. */
var STATE = {el: null, timer: null, lastShown: 0, installed: false};

function pickLocale() {
  var tags = [];
  try { tags.push(document.documentElement.lang); } catch (e) {}
  try { tags = tags.concat(navigator.languages || [navigator.language]); } catch (e) {}
  for (var i = 0; i < tags.length; i += 1) {
    var base = String(tags[i] || "").toLowerCase().split("-")[0];
    if (COPY[base]) return base;
  }
  return "en";
}

function copyFor(kind, locale) {
  var loc = COPY[locale] || COPY.en;
  var fallback = COPY.en;
  var k = (loc[kind] || fallback[kind] || fallback.oops);
  var common = Object.assign({}, fallback.common, loc.common || {});
  return {k: k, common: common};
}

function ensureStyle() {
  if (document.getElementById("sfe-style")) return;
  var style = document.createElement("style");
  style.id = "sfe-style";
  style.textContent = PAGE_CSS;
  document.head.appendChild(style);
}

function hide() {
  if (STATE.timer) { clearInterval(STATE.timer); STATE.timer = null; }
  if (STATE.el && STATE.el.parentNode) STATE.el.parentNode.removeChild(STATE.el);
  if (STATE.restore && STATE.restore.focus) { try { STATE.restore.focus(); } catch (e) {} }
  STATE.el = null;
  STATE.restore = null;
}

/** options: {status, kind, retry: async () => boolean, autoRetrySeconds, onClose, container, homeHref} */
function show(options) {
  var opts = options || {};
  var offline = typeof navigator !== "undefined" && navigator.onLine === false;
  var kind = opts.kind || classifyStatus(opts.status, {offline: offline}) || "oops";
  var locale = pickLocale();
  var c = copyFor(kind, locale);
  ensureStyle();
  hide();
  STATE.restore = document.activeElement;
  var screen = document.createElement("div");
  screen.className = "sfe-screen";
  screen.setAttribute("role", "alert");
  screen.setAttribute("data-sfe-kind", kind);
  screen.setAttribute("data-testid", "friendly-error");
  var home = opts.homeHref || "/";
  var code = opts.status ? c.common.status.replace("{code}", String(opts.status)) : "";
  screen.innerHTML = '<div class="sfe-stars"></div><div class="sfe-card">' + ART[KIND_MOOD[kind] || "calm"] +
    '<h1 class="sfe-title"></h1><p class="sfe-body"></p><p class="sfe-hint"></p><p class="sfe-note" aria-live="polite"></p>' +
    '<div class="sfe-actions"><button type="button" class="sfe-btn sfe-primary" data-sfe="retry"></button>' +
    '<a class="sfe-btn" data-sfe="home"></a><button type="button" class="sfe-btn" data-sfe="back"></button></div>' +
    '<span class="sfe-code"></span></div>';
  var q = function (sel) { return screen.querySelector(sel); };
  q(".sfe-title").textContent = c.k.title;
  q(".sfe-body").textContent = c.k.body;
  q(".sfe-hint").textContent = c.k.hint;
  q(".sfe-code").textContent = code;
  var retryBtn = q('[data-sfe="retry"]');
  retryBtn.textContent = c.common.tryAgain;
  if (kind === "notfound" || kind === "notimpl") {
    retryBtn.style.display = "none";
    q('[data-sfe="home"]').className += " sfe-primary";
  }
  q('[data-sfe="home"]').textContent = c.common.home;
  q('[data-sfe="home"]').setAttribute("href", home);
  q('[data-sfe="back"]').textContent = c.common.back;
  var note = q(".sfe-note");
  var busy = false;
  var tryNow = function () {
    if (busy) return;
    busy = true;
    note.textContent = c.common.checking;
    Promise.resolve(typeof opts.retry === "function" ? opts.retry() : false).then(function (ok) {
      busy = false;
      if (ok || typeof opts.retry !== "function") {
        hide();
        if (typeof opts.onClose === "function") opts.onClose(ok);
      } else {
        note.textContent = c.common.stillDown;
        startCountdown();
      }
    }, function () { busy = false; note.textContent = c.common.stillDown; startCountdown(); });
  };
  var startCountdown = function () {
    if (STATE.timer) { clearInterval(STATE.timer); STATE.timer = null; }
    var seconds = Number(opts.autoRetrySeconds) || 0;
    if (!seconds || typeof opts.retry !== "function" || (kind !== "network" && kind !== "offline")) return;
    var left = seconds;
    STATE.timer = setInterval(function () {
      left -= 1;
      if (left <= 0) { clearInterval(STATE.timer); STATE.timer = null; tryNow(); return; }
      note.textContent = c.common.retryIn.replace("{n}", String(left));
    }, 1000);
    note.textContent = c.common.retryIn.replace("{n}", String(left));
  };
  retryBtn.addEventListener("click", tryNow);
  q('[data-sfe="back"]').addEventListener("click", function () {
    hide();
    if (typeof opts.onClose === "function") opts.onClose(false);
    try { if (history.length > 1) history.back(); } catch (e) {}
  });
  screen.addEventListener("keydown", function (event) {
    if (event.key === "Escape") { hide(); if (typeof opts.onClose === "function") opts.onClose(false); }
  });
  (opts.container || document.body).appendChild(screen);
  STATE.el = screen;
  STATE.lastShown = Date.now();
  (kind === "notfound" || kind === "notimpl" ? q('[data-sfe="home"]') : retryBtn).focus();
  startCountdown();
  return screen;
}

function sleep(ms) { return new Promise(function (resolve) { setTimeout(resolve, ms); }); }

/** Wrap window.fetch for matching URLs: retry transient failures quietly, then show the screen. */
function watchFetch(options) {
  var opts = options || {};
  if (STATE.installed || typeof window === "undefined" || !window.fetch) return;
  STATE.installed = true;
  var match = opts.match || /^\/api\//;
  var ignore = opts.ignore || null;
  var original = window.fetch.bind(window);
  var cooldownMs = opts.cooldownMs || 15000;
  // A 404 or 501 from a background call is usually expected, so only hard failures interrupt play.
  var showKinds = opts.showKinds || ["network", "oops", "offline"];
  window.fetch = async function (input, init) {
    var url = typeof input === "string" ? input : (input && input.url) || "";
    var path = url;
    try { var u = new URL(url, location.href); path = u.origin === location.origin ? u.pathname + u.search : ""; } catch (e) { path = ""; }
    if (!path || !match.test(path) || (ignore && ignore.test(path))) return original(input, init);
    var method = String((init && init.method) || (input && input.method) || "GET").toUpperCase();
    var attempts = method === "GET" || method === "HEAD" ? 3 : 1;
    var last = null;
    for (var i = 0; i < attempts; i += 1) {
      try {
        var response = await original(input, init);
        var kind = classifyStatus(response.status, {});
        if (!kind || response.ok) return response;
        last = {status: response.status, response: response};
        if (kind !== "network" && kind !== "oops") break;
      } catch (error) {
        if (error && error.name === "AbortError") throw error;
        last = {status: 0, error: error};
      }
      if (i < attempts - 1) await sleep(500 * (i + 1) * (i + 1));
    }
    var lastKind = last ? classifyStatus(last.status, {}) : null;
    if (last && showKinds.indexOf(lastKind) >= 0 && Date.now() - STATE.lastShown > cooldownMs && (!STATE.el)) {
      var failedUrl = path;
      show({
        status: last.status,
        autoRetrySeconds: 15,
        retry: method === "GET" || method === "HEAD" ? function () {
          return original(failedUrl, {method: "GET", cache: "no-store"}).then(function (r) { return r.ok; }, function () { return false; });
        } : null,
      });
    }
    if (last && last.response) return last.response;
    throw last && last.error ? last.error : new TypeError("Network request failed");
  };
}

function enableOfflineBanner() {
  if (typeof window === "undefined") return;
  window.addEventListener("offline", function () { show({kind: "offline", autoRetrySeconds: 0}); });
  window.addEventListener("online", function () { if (STATE.el && STATE.el.getAttribute("data-sfe-kind") === "offline") hide(); });
}

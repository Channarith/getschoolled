// The voice the visitor picked in the account menu (same origin, so the same localStorage as the web app):
//   aoep_demo_voice   = a consented company voice id, or "default"
//   aoep_drive_voice  = an edge-tts voice id such as en-US-AriaNeural, or "" for the automatic voice
// Company voices are never cloned live: a clip is looked up by voice + language + a hash of the exact text and any miss
// falls back to the edge voice (or the default narration). The hash must stay identical to apps/web/app/lib/cloneVoice.ts
// and tts_bakeoff/demo_voice/clip_hash.py.
(function () {
  "use strict";
  var CLONE_KEY = "aoep_demo_voice";
  var EDGE_KEY = "aoep_drive_voice";
  var EDGE_ID = /^[a-z]{2,3}(-[A-Za-z0-9]+)+Neural$/;
  var WS = /[ \t\n\r\f\v\u00a0\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]+/g;

  function assetsBase() {
    var fromUrl = "";
    try { fromUrl = new URLSearchParams(window.location.search || "").get("voiceassets") || ""; } catch (_) { /* ignore */ }
    if (!/^(https:\/\/[A-Za-z0-9.-]+(:\d+)?)?\/[A-Za-z0-9._\/-]*$/.test(fromUrl)) fromUrl = "";
    return (fromUrl || "/voice-assets").replace(/\/$/, "");
  }

  function clipHash(lang, text) {
    var primary = String(lang || "en").split(/[-_]/)[0].toLowerCase();
    var s = primary + "\u241f" + String(text || "").normalize("NFC").replace(WS, " ").trim();
    var h1 = 0xdeadbeef, h2 = 0x41c6ce57;
    for (var i = 0; i < s.length; i++) {
      var ch = s.charCodeAt(i);
      h1 = Math.imul(h1 ^ ch, 2654435761);
      h2 = Math.imul(h2 ^ ch, 1597334677);
    }
    h1 = Math.imul(h1 ^ (h1 >>> 16), 2246822507);
    h1 ^= Math.imul(h2 ^ (h2 >>> 13), 3266489909);
    h2 = Math.imul(h2 ^ (h2 >>> 16), 2246822507);
    h2 ^= Math.imul(h1 ^ (h1 >>> 13), 3266489909);
    return (4294967296 * (2097151 & h2) + (h1 >>> 0)).toString(16).padStart(14, "0");
  }

  function chosen() {
    var custom = "", edge = "";
    try { custom = window.localStorage.getItem(CLONE_KEY) || ""; edge = window.localStorage.getItem(EDGE_KEY) || ""; } catch (_) { /* private mode */ }
    if (custom === "default") custom = "";
    if (!EDGE_ID.test(edge)) edge = "";
    return { custom: custom, edge: edge };
  }

  // The edge voice only counts when it speaks the lesson's language (an English voice must not read a Khmer lesson).
  function edgeVoiceFor(lang) {
    var edge = chosen().edge;
    if (!edge) return "";
    var want = String(lang || "en").toLowerCase().replace(/_/g, "-");
    var have = edge.toLowerCase();
    if (want === "yue" || want === "zh-hk") return have.indexOf("zh-hk") === 0 ? edge : "";
    return have.split("-")[0] === want.split("-")[0] ? edge : "";
  }

  var voicesPromise = null;
  var indexes = {};
  function activeVoices() {
    if (!voicesPromise) {
      voicesPromise = fetch(assetsBase() + "/voices.json", { cache: "no-store" })
        .then(function (r) { return r.ok ? r.json() : { voices: [] }; })
        .then(function (j) { return Array.isArray(j && j.voices) ? j.voices.filter(function (v) { return v && v.active; }) : []; })
        .catch(function () { return []; });
    }
    return voicesPromise;
  }
  function loadIndex(voice) {
    if (!indexes[voice]) {
      indexes[voice] = fetch(assetsBase() + "/" + encodeURIComponent(voice) + "/index.json")
        .then(function (r) { return r.ok ? r.json() : null; })
        .catch(function () { return null; });
    }
    return indexes[voice];
  }

  // URL of the pre-rendered clip for the chosen company voice, or null.
  function cloneClipUrl(lang, text) {
    var voice = chosen().custom;
    if (!voice || !String(text || "").trim()) return Promise.resolve(null);
    return activeVoices().then(function (voices) {
      // Consent withdrawn => no longer listed => no clip.
      if (!voices.some(function (v) { return v.id === voice; })) return null;
      return loadIndex(voice).then(function (index) {
        if (!index) return null;
        var l = String(lang || "en").split(/[-_]/)[0].toLowerCase();
        var h = clipHash(l, text);
        if (index.clips && index.clips[l] && index.clips[l].indexOf(h) >= 0) {
          return assetsBase() + "/" + encodeURIComponent(voice) + "/" + l + "/" + h + "." + (index.ext || "mp3");
        }
        window.__cloneVoiceMisses = window.__cloneVoiceMisses || [];
        window.__cloneVoiceMisses.push({ demo: "miss", lang: l, text: String(text) });
        return null;
      });
    });
  }

  // Gender ("male" | "female" | "") of the chosen company voice, so a missing clip falls back to an edge voice of the same gender.
  function customGender() {
    var voice = chosen().custom;
    if (!voice) return Promise.resolve("");
    return activeVoices().then(function (voices) {
      var v = voices.filter(function (x) { return x.id === voice; })[0];
      return v && (v.gender === "male" || v.gender === "female") ? v.gender : "";
    });
  }

  window.SalaVoiceChoice = { chosen: chosen, edgeVoiceFor: edgeVoiceFor, cloneClipUrl: cloneClipUrl, clipHash: clipHash, customGender: customGender };
})();

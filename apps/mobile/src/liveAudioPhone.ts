/**
 * The vision arcade and studio pages load the live-audio chip from the site.
 * Older builds pin a wide text panel over the game. This runs in the phone
 * WebView first: it lifts quiet playback, and it shrinks that panel into a
 * draggable icon until the site itself ships the small chip.
 */
export function liveAudioPhoneScript(): string {
  return `(function(){
    if (window.__SALAREEN_PHONE_AUDIO__) return;
    window.__SALAREEN_PHONE_AUDIO__ = true;
    var proto = window.AudioNode && AudioNode.prototype;
    if (proto && !proto.__salareenBoost && typeof proto.connect === "function") {
      var origConnect = proto.connect;
      var boosts = new WeakMap();
      function boostFor(ctx) {
        var node = boosts.get(ctx);
        if (node) return node;
        node = ctx.createGain();
        node.gain.value = 2.6;
        node.__salareenBoostNode = true;
        origConnect.call(node, ctx.destination);
        boosts.set(ctx, node);
        return node;
      }
      proto.connect = function(dest) {
        if (this && this.__salareenBoostNode) return origConnect.apply(this, arguments);
        if (!window.__SALAREEN_LIVE_GAIN__ && dest && window.AudioDestinationNode &&
            dest instanceof AudioDestinationNode && this && this.context) {
          return origConnect.call(this, boostFor(this.context));
        }
        return origConnect.apply(this, arguments);
      };
      proto.__salareenBoost = true;
    }
    var mic = "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'><path fill='%23e7fbff' d='M12 14a3 3 0 0 0 3-3V6a3 3 0 0 0-6 0v5a3 3 0 0 0 3 3zm5-3a5 5 0 0 1-10 0H5a7 7 0 0 0 6 6.92V21h2v-3.08A7 7 0 0 0 19 11h-2z'/></svg>";
    var speaker = "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'><path fill='%23fff' d='M3 9v6h4l5 4V5L7 9H3zm13.5 3a4.5 4.5 0 0 0-2.5-4.03v8.05A4.5 4.5 0 0 0 16.5 12zM14 3.23v2.06a7 7 0 0 1 0 13.42v2.06a9 9 0 0 0 0-17.54z'/></svg>";
    function place(box, left, top) {
      var w = box.offsetWidth || 68;
      var h = box.offsetHeight || 68;
      var x = Math.max(8, Math.min(window.innerWidth - w - 8, left));
      var y = Math.max(8, Math.min(window.innerHeight - h - 8, top));
      box.style.left = x + "px";
      box.style.top = y + "px";
      box.style.right = "auto";
      box.style.bottom = "auto";
      box.classList.add("placed");
      try { localStorage.setItem("aoep.liveAudio.pos", JSON.stringify({left:x, top:y})); } catch (e) {}
    }
    function arm(host) {
      var root = host.shadowRoot;
      if (!root) return;
      var box = root.querySelector(".box");
      if (!box || box.getAttribute("data-drag-chip") === "1" || box.dataset.phoneChip === "1") return;
      box.dataset.phoneChip = "1";
      var style = document.createElement("style");
      style.textContent = [
        ".box{width:68px !important;height:68px !important;padding:0 !important;border-radius:50% !important;",
        "right:12px !important;left:auto !important;bottom:max(18px, env(safe-area-inset-bottom)) !important;",
        "overflow:visible !important;touch-action:none !important;cursor:grab}",
        ".box.docked{width:68px !important;height:68px !important;left:auto !important;right:12px !important}",
        ".box.placed{right:auto !important;bottom:auto !important}",
        ".title,.status,.caption,select{position:absolute !important;width:1px !important;height:1px !important;",
        "overflow:hidden !important;clip:rect(0,0,0,0) !important}",
        ".toggle{width:68px !important;height:68px !important;border-radius:50% !important;border:0 !important;",
        "padding:0 !important;font-size:0 !important;color:transparent !important;",
        "background:#07111e center/30px 30px no-repeat !important;background-image:url(\\"" + mic + "\\") !important}",
        ".toggle.live{background-color:#065f46 !important;background-image:url(\\"" + speaker + "\\") !important}",
        ".close{position:absolute;top:-6px;right:-6px;width:20px;height:20px;padding:0;border-radius:50%;",
        "border:0;background:#172033;color:#fff;font:700 13px/20px system-ui,sans-serif}"
      ].join("");
      root.appendChild(style);
      try {
        var saved = JSON.parse(localStorage.getItem("aoep.liveAudio.pos") || "null");
        if (saved && isFinite(saved.left) && isFinite(saved.top)) place(box, saved.left, saved.top);
      } catch (e) {}
      var drag = null;
      box.addEventListener("pointerdown", function(event) {
        if (event.button !== 0) return;
        if (event.target.closest && event.target.closest(".close")) return;
        var rect = box.getBoundingClientRect();
        drag = {id: event.pointerId, x: event.clientX, y: event.clientY, left: rect.left, top: rect.top, moved: false};
      });
      box.addEventListener("pointermove", function(event) {
        if (!drag || event.pointerId !== drag.id) return;
        var dx = event.clientX - drag.x;
        var dy = event.clientY - drag.y;
        if (!drag.moved && Math.hypot(dx, dy) < 8) return;
        drag.moved = true;
        place(box, drag.left + dx, drag.top + dy);
        event.preventDefault();
      });
      function endDrag(event) {
        if (!drag || event.pointerId !== drag.id) return;
        var moved = drag.moved;
        drag = null;
        if (!moved) return;
        box.addEventListener("click", function(click) {
          click.preventDefault();
          click.stopPropagation();
        }, {capture: true, once: true});
      }
      box.addEventListener("pointerup", endDrag);
      box.addEventListener("pointercancel", endDrag);
    }
    function scan() {
      var host = document.getElementById("theodore-live-audio");
      if (host) arm(host);
    }
    if (document.documentElement) {
      new MutationObserver(scan).observe(document.documentElement, {childList: true, subtree: true});
    }
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", scan);
    else scan();
  })(); true;`;
}

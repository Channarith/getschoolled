// Strip anything executable from generated SVG before it is injected into the page.
// String based on purpose: it runs on the server render too, where there is no DOM.

const BLOCKED_ELEMENTS = ["script", "foreignobject", "iframe", "object", "embed", "audio", "video", "animate", "set", "handler"];
const EVENT_ATTR = /[\s/"']on[a-z0-9_-]+\s*=\s*("[^"]*"|'[^']*'|[^\s>]*)/gi;
const HREF_ATTR = /\s(?:xlink:)?href\s*=\s*("([^"]*)"|'([^']*)'|([^\s>]*))/gi;

function stripElements(input: string): string {
  let out = input;
  for (const tag of BLOCKED_ELEMENTS) {
    const paired = new RegExp(`<\\s*${tag}\\b[\\s\\S]*?<\\s*/\\s*${tag}\\s*>`, "gi");
    const open = new RegExp(`<\\s*/?\\s*${tag}\\b[^>]*>?`, "gi");
    out = out.replace(paired, "").replace(open, "");
  }
  return out;
}

export function sanitizeSvg(svg: string): string {
  let out = String(svg ?? "");
  for (let i = 0; i < 6; i += 1) {
    const before = out;
    out = stripElements(out)
      .replace(EVENT_ATTR, "")
      .replace(HREF_ATTR, (match, _all, dq, sq, bare) => {
        const value = String(dq ?? sq ?? bare ?? "").trim();
        return value.startsWith("#") || /^data:image\/(png|jpe?g|gif|webp);/i.test(value) ? match : "";
      })
      .replace(/javascript\s*:/gi, "")
      .replace(/<!ENTITY[\s\S]*?>/gi, "");
    if (out === before) break;
  }
  return out;
}

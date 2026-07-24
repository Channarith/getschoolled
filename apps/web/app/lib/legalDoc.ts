import fs from "fs";
import path from "path";

/** Load a legal document shipped inside apps/web (Docker-safe). */
export function loadLegalDoc(filename: string): string {
  const candidates = [
    path.join(process.cwd(), "content", "legal", filename),
    path.join(process.cwd(), "apps", "web", "content", "legal", filename),
  ];
  for (const p of candidates) {
    try {
      if (fs.existsSync(p)) return fs.readFileSync(p, "utf8");
    } catch {
      /* try next */
    }
  }
  throw new Error(`Legal document not found: ${filename}`);
}

/** Split plain-text legal docs into title + body paragraphs for rendering. */
export function formatLegalBody(raw: string): { title: string; paragraphs: string[] } {
  const lines = raw.replace(/\r\n/g, "\n").split("\n");
  const title = (lines[0] || "Legal").trim();
  const paragraphs: string[] = [];
  let buf: string[] = [];
  const flush = () => {
    const text = buf.join(" ").replace(/\s+/g, " ").trim();
    if (text) paragraphs.push(text);
    buf = [];
  };
  for (const line of lines.slice(1)) {
    if (/^=+$/.test(line.trim())) continue;
    if (!line.trim()) {
      flush();
      continue;
    }
    buf.push(line.trim());
  }
  flush();
  return { title, paragraphs };
}

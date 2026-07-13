// Intro animation variants — each is a self-contained canvas renderer driven by a
// normalized progress value p (0..1). The IntroSequence component owns the loop,
// sizing and audio; variants just paint a frame. Designed to look premium:
// starfield warp, particle assembly, neon rings, aurora, confetti, constellation.

import { clamp, lerp, rand } from "./gameEngine2d";

export type Ctx2D = CanvasRenderingContext2D;

export type IntroVariant = {
  id: string;
  name: string;
  melody: number;
  render: (ctx: Ctx2D, w: number, h: number, p: number, logo: HTMLImageElement | null, S: Record<string, unknown>) => void;
};

const BRAND = "Salareen";
const easeOut = (x: number) => 1 - Math.pow(1 - x, 3);
const easeInOut = (x: number) => (x < 0.5 ? 2 * x * x : 1 - Math.pow(-2 * x + 2, 2) / 2);

function fillBg(ctx: Ctx2D, w: number, h: number, a: string, b: string): void {
  const g = ctx.createLinearGradient(0, 0, w, h);
  g.addColorStop(0, a); g.addColorStop(1, b);
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, w, h);
}

/** Logo mark + wordmark reveal, shared by every variant (staged near the end). */
function reveal(ctx: Ctx2D, w: number, h: number, p: number, logo: HTMLImageElement | null, opts: { from?: number } = {}): void {
  const from = opts.from ?? 0.5;
  if (p < from) return;
  const q = clamp((p - from) / (1 - from), 0, 1);
  const overshoot = 1 + Math.sin(Math.min(1, q * 1.3) * Math.PI) * 0.12;
  const scale = lerp(0.55, 1, easeOut(clamp(q * 1.4, 0, 1))) * overshoot;
  const cx = w / 2, cy = h / 2 - h * 0.04;
  const size = Math.min(w, h) * 0.28 * scale;

  ctx.save();
  ctx.globalAlpha = clamp(q * 1.6, 0, 1);
  ctx.shadowColor = "rgba(167,139,250,0.9)";
  ctx.shadowBlur = 40 * q;
  if (logo && logo.complete && logo.naturalWidth > 0) {
    ctx.drawImage(logo, cx - size / 2, cy - size / 2, size, size);
  } else {
    // Fallback mark: glowing rounded diamond.
    ctx.fillStyle = "#a78bfa";
    ctx.translate(cx, cy); ctx.rotate(Math.PI / 4);
    ctx.fillRect(-size / 2, -size / 2, size, size);
    ctx.setTransform(1, 0, 0, 1, 0, 0);
  }
  ctx.restore();

  // Wordmark.
  const wq = clamp((p - (from + 0.15)) / (1 - (from + 0.15)), 0, 1);
  if (wq > 0) {
    ctx.save();
    ctx.globalAlpha = wq;
    ctx.fillStyle = "#f5f3ff";
    ctx.textAlign = "center"; ctx.textBaseline = "middle";
    ctx.font = `600 ${Math.min(w, h) * 0.075}px system-ui, -apple-system, sans-serif`;
    ctx.shadowColor = "rgba(34,211,238,0.7)"; ctx.shadowBlur = 24 * wq;
    ctx.fillText(BRAND, cx, cy + size * 0.85 + Math.min(w, h) * 0.02);
    ctx.restore();
  }
}

type Star = { x: number; y: number; z: number; pz: number };
type P = { x: number; y: number; vx: number; vy: number; a: number; c: string; r: number; sx?: number; sy?: number };
type Node = { a: number; r: number; s: number; x: number; y: number };

export const INTRO_VARIANTS: IntroVariant[] = [
  {
    id: "hyperspace", name: "Hyperspace", melody: 0,
    render(ctx, w, h, p, logo, S) {
      fillBg(ctx, w, h, "#05030f", "#0a0620");
      const cx = w / 2, cy = h / 2;
      let stars = S.stars as Star[] | undefined;
      if (!stars) { stars = Array.from({ length: 320 }, () => ({ x: rand(-w, w), y: rand(-h, h), z: rand(1, w), pz: 0 })); S.stars = stars; }
      const speed = lerp(28, 4, easeInOut(p)) + (p > 0.7 ? 0 : 0);   // decelerate into the reveal
      ctx.save();
      ctx.translate(cx, cy);
      for (const s of stars) {
        s.pz = s.z;
        s.z -= speed;
        if (s.z < 1) { s.x = rand(-w, w); s.y = rand(-h, h); s.z = w; s.pz = w; }
        const sx = (s.x / s.z) * w, sy = (s.y / s.z) * w;
        const px = (s.x / s.pz) * w, py = (s.y / s.pz) * w;
        const r = clamp((1 - s.z / w) * 2.4, 0.2, 2.6);
        ctx.strokeStyle = `rgba(180,200,255,${clamp(1 - s.z / w, 0.1, 0.9)})`;
        ctx.lineWidth = r;
        ctx.beginPath(); ctx.moveTo(px, py); ctx.lineTo(sx, sy); ctx.stroke();
      }
      ctx.restore();
      reveal(ctx, w, h, p, logo, { from: 0.55 });
    },
  },
  {
    id: "assemble", name: "Particle Assembly", melody: 1,
    render(ctx, w, h, p, logo, S) {
      fillBg(ctx, w, h, "#0a0620", "#131033");
      const cx = w / 2, cy = h / 2 - h * 0.04;
      let ps = S.ps as P[] | undefined;
      if (!ps) {
        ps = Array.from({ length: 240 }, () => {
          const a = rand(0, Math.PI * 2), rad = Math.min(w, h) * rand(0.28, 0.42);
          return { x: cx + Math.cos(a) * (Math.max(w, h)), y: cy + Math.sin(a) * (Math.max(w, h)), vx: 0, vy: 0, a, r: rand(1.4, 3.2), c: Math.random() < 0.5 ? "#a78bfa" : "#22d3ee", sx: cx + Math.cos(a) * rad, sy: cy + Math.sin(a) * rad };
        });
        S.ps = ps;
      }
      const t = easeInOut(clamp(p / 0.6, 0, 1));
      ctx.save();
      ctx.globalCompositeOperation = "lighter";
      for (const q of ps) {
        const x = lerp(q.x, q.sx!, t), y = lerp(q.y, q.sy!, t);
        ctx.globalAlpha = clamp(0.3 + t * 0.7, 0, 1);
        ctx.fillStyle = q.c;
        ctx.shadowColor = q.c; ctx.shadowBlur = 8;
        ctx.beginPath(); ctx.arc(x, y, q.r, 0, Math.PI * 2); ctx.fill();
      }
      ctx.restore();
      reveal(ctx, w, h, p, logo, { from: 0.5 });
    },
  },
  {
    id: "neon", name: "Neon Rings", melody: 2,
    render(ctx, w, h, p, logo) {
      fillBg(ctx, w, h, "#0b0518", "#1a0730");
      const cx = w / 2, cy = h / 2 - h * 0.04;
      const max = Math.min(w, h) * 0.6;
      ctx.save();
      ctx.globalCompositeOperation = "lighter";
      const colors = ["#22d3ee", "#a78bfa", "#f472b6"];
      for (let i = 0; i < 6; i++) {
        const phase = (p * 2 + i / 6) % 1;
        const r = phase * max;
        ctx.globalAlpha = clamp(1 - phase, 0, 1) * 0.8;
        ctx.strokeStyle = colors[i % colors.length];
        ctx.lineWidth = 3;
        ctx.shadowColor = colors[i % colors.length]; ctx.shadowBlur = 22;
        ctx.beginPath(); ctx.arc(cx, cy, r + 4, 0, Math.PI * 2); ctx.stroke();
      }
      ctx.restore();
      reveal(ctx, w, h, p, logo, { from: 0.5 });
    },
  },
  {
    id: "aurora", name: "Aurora", melody: 3,
    render(ctx, w, h, p, logo) {
      fillBg(ctx, w, h, "#02040f", "#071226");
      ctx.save();
      ctx.globalCompositeOperation = "lighter";
      const bands = [["#34d399", 0.0], ["#22d3ee", 0.33], ["#a78bfa", 0.66]] as const;
      for (const [color, off] of bands) {
        ctx.beginPath();
        for (let x = 0; x <= w; x += 8) {
          const y = h * 0.5 + Math.sin(x * 0.008 + p * 6 + off * 10) * h * 0.16 + Math.sin(x * 0.02 + p * 4) * h * 0.05;
          if (x === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        }
        ctx.lineTo(w, h); ctx.lineTo(0, h); ctx.closePath();
        const g = ctx.createLinearGradient(0, h * 0.3, 0, h);
        g.addColorStop(0, color + "88"); g.addColorStop(1, "transparent");
        ctx.fillStyle = g; ctx.globalAlpha = 0.5; ctx.fill();
      }
      ctx.restore();
      reveal(ctx, w, h, p, logo, { from: 0.45 });
    },
  },
  {
    id: "confetti", name: "Confetti Pop", melody: 4,
    render(ctx, w, h, p, logo, S) {
      fillBg(ctx, w, h, "#120a24", "#241145");
      const cx = w / 2, cy = h / 2;
      let ps = S.ps as P[] | undefined;
      const palette = ["#f472b6", "#22d3ee", "#a78bfa", "#facc15", "#34d399", "#fb7185"];
      if (!ps) {
        ps = Array.from({ length: 180 }, () => {
          const a = rand(0, Math.PI * 2), sp = rand(4, 15);
          return { x: cx, y: cy, vx: Math.cos(a) * sp, vy: Math.sin(a) * sp - 4, a: rand(0, Math.PI), c: palette[Math.floor(rand(0, palette.length))], r: rand(3, 7) };
        });
        S.ps = ps;
      }
      ctx.save();
      for (const q of ps) {
        q.x += q.vx; q.y += q.vy; q.vy += 0.28; q.vx *= 0.99; q.a += 0.2;
        ctx.globalAlpha = clamp(1 - p * 0.6, 0.2, 1);
        ctx.fillStyle = q.c;
        ctx.save(); ctx.translate(q.x, q.y); ctx.rotate(q.a);
        ctx.fillRect(-q.r, -q.r * 0.5, q.r * 2, q.r); ctx.restore();
      }
      ctx.restore();
      reveal(ctx, w, h, p, logo, { from: 0.38 });
    },
  },
  {
    id: "constellation", name: "Constellation", melody: 5,
    render(ctx, w, h, p, logo, S) {
      fillBg(ctx, w, h, "#03060f", "#0a1024");
      const cx = w / 2, cy = h / 2 - h * 0.04;
      let nodes = S.nodes as Node[] | undefined;
      if (!nodes) {
        nodes = Array.from({ length: 26 }, () => ({ a: rand(0, Math.PI * 2), r: Math.min(w, h) * rand(0.12, 0.44), s: rand(0.3, 0.9) * (Math.random() < 0.5 ? 1 : -1), x: 0, y: 0 }));
        S.nodes = nodes;
      }
      for (const n of nodes) {
        n.a += n.s * 0.01;
        n.x = cx + Math.cos(n.a) * n.r;
        n.y = cy + Math.sin(n.a) * n.r * 0.8;
      }
      ctx.save();
      ctx.strokeStyle = "rgba(96,165,250,0.35)"; ctx.lineWidth = 1;
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const dx = nodes[i].x - nodes[j].x, dy = nodes[i].y - nodes[j].y;
          const d = Math.hypot(dx, dy);
          if (d < Math.min(w, h) * 0.16) {
            ctx.globalAlpha = clamp(1 - d / (Math.min(w, h) * 0.16), 0, 1) * 0.6;
            ctx.beginPath(); ctx.moveTo(nodes[i].x, nodes[i].y); ctx.lineTo(nodes[j].x, nodes[j].y); ctx.stroke();
          }
        }
      }
      ctx.globalAlpha = 1;
      for (const n of nodes) {
        ctx.fillStyle = "#93c5fd"; ctx.shadowColor = "#60a5fa"; ctx.shadowBlur = 10;
        ctx.beginPath(); ctx.arc(n.x, n.y, 2.6, 0, Math.PI * 2); ctx.fill();
      }
      ctx.restore();
      reveal(ctx, w, h, p, logo, { from: 0.5 });
    },
  },
];

export function pickRandomVariant(): IntroVariant {
  return INTRO_VARIANTS[Math.floor(Math.random() * INTRO_VARIANTS.length)];
}

export function variantById(id: string | undefined | null): IntroVariant | undefined {
  return INTRO_VARIANTS.find((v) => v.id === id);
}

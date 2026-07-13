// Lightweight 2D canvas game engine for the arcade.
//
// A small, reusable foundation so mini-games are real graphical games (animated,
// DPR-crisp, particle FX, fixed-timestep loop) instead of DOM widgets. No deps.

export type Ctx2D = CanvasRenderingContext2D;

export const rand = (a: number, b: number) => a + Math.random() * (b - a);
export const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v));
export const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
export const dist2 = (ax: number, ay: number, bx: number, by: number) => (ax - bx) ** 2 + (ay - by) ** 2;

/** DPR-aware canvas surface that stays crisp and tracks its CSS size. */
export class Surface {
  ctx: Ctx2D;
  width = 0;
  height = 0;
  dpr = 1;
  private ro?: ResizeObserver;

  constructor(private canvas: HTMLCanvasElement) {
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("2D canvas not supported");
    this.ctx = ctx;
    this.resize();
    if (typeof ResizeObserver !== "undefined") {
      this.ro = new ResizeObserver(() => this.resize());
      this.ro.observe(canvas);
    }
  }

  resize(): void {
    const rect = this.canvas.getBoundingClientRect();
    this.dpr = Math.min(2, Math.max(1, window.devicePixelRatio || 1));
    this.width = Math.max(1, Math.round(rect.width));
    this.height = Math.max(1, Math.round(rect.height));
    this.canvas.width = Math.round(this.width * this.dpr);
    this.canvas.height = Math.round(this.height * this.dpr);
    this.ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
  }

  dispose(): void {
    this.ro?.disconnect();
  }
}

/** Fixed-ish game loop with a capped dt (so a background tab can't fast-forward). */
export class GameLoop {
  private raf = 0;
  private last = 0;
  private running = false;

  constructor(private step: (dt: number) => void) {}

  start(): void {
    if (this.running) return;
    this.running = true;
    this.last = performance.now();
    const frame = (now: number) => {
      if (!this.running) return;
      const dt = Math.min(0.05, (now - this.last) / 1000);   // cap at 50ms
      this.last = now;
      this.step(dt);
      this.raf = requestAnimationFrame(frame);
    };
    this.raf = requestAnimationFrame(frame);
  }

  stop(): void {
    this.running = false;
    if (this.raf) cancelAnimationFrame(this.raf);
    this.raf = 0;
  }
}

export type Particle = {
  x: number; y: number; vx: number; vy: number;
  life: number; maxLife: number; size: number; color: string; gravity: number;
};

/** Simple additive particle system for explosions / sparkles / trails. */
export class Particles {
  private items: Particle[] = [];

  get count(): number { return this.items.length; }

  burst(x: number, y: number, color: string, n = 18, opts: { speed?: number; size?: number; gravity?: number; life?: number } = {}): void {
    const speed = opts.speed ?? 180;
    for (let i = 0; i < n; i++) {
      const a = rand(0, Math.PI * 2);
      const s = rand(speed * 0.3, speed);
      this.items.push({
        x, y, vx: Math.cos(a) * s, vy: Math.sin(a) * s,
        life: opts.life ?? rand(0.4, 0.9), maxLife: opts.life ?? 0.9,
        size: opts.size ?? rand(2, 5), color, gravity: opts.gravity ?? 220,
      });
    }
  }

  update(dt: number): void {
    for (const p of this.items) {
      p.vy += p.gravity * dt;
      p.x += p.vx * dt;
      p.y += p.vy * dt;
      p.life -= dt;
    }
    this.items = this.items.filter((p) => p.life > 0);
  }

  draw(ctx: Ctx2D): void {
    ctx.save();
    ctx.globalCompositeOperation = "lighter";
    for (const p of this.items) {
      const a = clamp(p.life / p.maxLife, 0, 1);
      ctx.globalAlpha = a;
      ctx.fillStyle = p.color;
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.restore();
  }
}

/** Rounded-rect path helper (juicy UI panels/entities). */
export function roundRect(ctx: Ctx2D, x: number, y: number, w: number, h: number, r: number): void {
  const rr = Math.min(r, w / 2, h / 2);
  ctx.beginPath();
  ctx.moveTo(x + rr, y);
  ctx.arcTo(x + w, y, x + w, y + h, rr);
  ctx.arcTo(x + w, y + h, x, y + h, rr);
  ctx.arcTo(x, y + h, x, y, rr);
  ctx.arcTo(x, y, x + w, y, rr);
  ctx.closePath();
}

/** A twinkling starfield background (drawn each frame). */
export class Starfield {
  private stars: { x: number; y: number; z: number; s: number }[] = [];
  constructor(count = 90) {
    for (let i = 0; i < count; i++) {
      this.stars.push({ x: Math.random(), y: Math.random(), z: rand(0.2, 1), s: rand(0.5, 1.8) });
    }
  }
  draw(ctx: Ctx2D, w: number, h: number, t: number): void {
    for (const st of this.stars) {
      const tw = 0.5 + 0.5 * Math.sin(t * 2 * st.z + st.x * 10);
      ctx.globalAlpha = 0.25 + 0.6 * tw * st.z;
      ctx.fillStyle = "#cbd5ff";
      ctx.beginPath();
      ctx.arc(st.x * w, st.y * h, st.s * st.z, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.globalAlpha = 1;
  }
}

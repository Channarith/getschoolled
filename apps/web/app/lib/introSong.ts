// Procedural intro "song" via the Web Audio API — no audio asset needed, works
// offline, and gives each intro animation its own short jingle. Autoplay policies
// block sound without a user gesture, so play() calls resume() and fails soft
// (the visual intro still runs silently until the user replays it from Settings).

type Note = [midi: number, start: number, dur: number, gain?: number];

type Melody = { lead: Note[]; bass: Note[]; wave: OscillatorType; bassWave: OscillatorType };

const midiToFreq = (m: number) => 440 * Math.pow(2, (m - 69) / 12);

// A handful of bright, pleasant jingles (times in seconds). Index maps to an
// animation variant so the music matches the mood.
export const MELODIES: Melody[] = [
  // 0 — triumphant major arpeggio (hyperspace)
  {
    wave: "triangle", bassWave: "sine",
    lead: [[72, 0, 0.22], [76, 0.2, 0.22], [79, 0.4, 0.22], [84, 0.6, 0.5], [79, 1.1, 0.25], [84, 1.35, 0.9]],
    bass: [[48, 0, 1.1], [43, 1.1, 1.2]],
  },
  // 1 — shimmering rise (particle assemble)
  {
    wave: "sine", bassWave: "triangle",
    lead: [[67, 0, 0.3], [71, 0.28, 0.3], [74, 0.56, 0.3], [79, 0.84, 0.3], [83, 1.12, 0.9]],
    bass: [[52, 0, 1.0], [55, 1.0, 1.2]],
  },
  // 2 — neon pulse (rings)
  {
    wave: "sawtooth", bassWave: "sine",
    lead: [[69, 0, 0.18, 0.5], [69, 0.25, 0.18, 0.5], [76, 0.5, 0.3], [74, 0.85, 0.25], [81, 1.15, 0.8]],
    bass: [[45, 0, 0.5], [45, 0.5, 0.5], [50, 1.0, 1.2]],
  },
  // 3 — dreamy aurora
  {
    wave: "sine", bassWave: "sine",
    lead: [[74, 0, 0.6, 0.5], [78, 0.5, 0.6, 0.5], [81, 1.0, 1.1, 0.55]],
    bass: [[50, 0, 1.4], [57, 1.2, 1.2]],
  },
  // 4 — playful confetti bounce
  {
    wave: "square", bassWave: "triangle",
    lead: [[72, 0, 0.16, 0.4], [76, 0.18, 0.16, 0.4], [79, 0.36, 0.16, 0.4], [84, 0.54, 0.16, 0.4], [88, 0.72, 0.5, 0.45], [84, 1.2, 0.6, 0.4]],
    bass: [[48, 0, 0.5], [48, 0.6, 0.5], [55, 1.1, 0.9]],
  },
  // 5 — constellation chimes
  {
    wave: "triangle", bassWave: "sine",
    lead: [[76, 0, 0.4, 0.45], [83, 0.35, 0.4, 0.45], [79, 0.75, 0.4, 0.45], [86, 1.1, 1.0, 0.5]],
    bass: [[52, 0, 1.2], [47, 1.2, 1.2]],
  },
];

export class IntroSong {
  private ctx: AudioContext | null = null;
  private nodes: AudioNode[] = [];

  private ensureCtx(): AudioContext | null {
    if (typeof window === "undefined") return null;
    const AC = window.AudioContext || (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!AC) return null;
    if (!this.ctx) this.ctx = new AC();
    return this.ctx;
  }

  /** Best-effort play; returns true if audio actually started. */
  play(melodyIndex: number): boolean {
    const ctx = this.ensureCtx();
    if (!ctx) return false;
    ctx.resume?.().catch(() => { /* blocked by autoplay policy */ });

    const master = ctx.createGain();
    master.gain.value = 0.0001;
    master.gain.setValueAtTime(0.0001, ctx.currentTime);
    master.gain.exponentialRampToValueAtTime(0.6, ctx.currentTime + 0.08);

    // A gentle feedback delay adds sparkle/space without an impulse response.
    const delay = ctx.createDelay();
    delay.delayTime.value = 0.16;
    const fb = ctx.createGain();
    fb.gain.value = 0.28;
    const wet = ctx.createGain();
    wet.gain.value = 0.35;
    master.connect(delay); delay.connect(fb); fb.connect(delay); delay.connect(wet);
    master.connect(ctx.destination); wet.connect(ctx.destination);
    this.nodes = [master, delay, fb, wet];

    const m = MELODIES[melodyIndex % MELODIES.length];
    const t0 = ctx.currentTime + 0.05;
    for (const [midi, start, dur, g] of m.lead) this.voice(ctx, master, m.wave, midiToFreq(midi), t0 + start, dur, g ?? 0.5, true);
    for (const [midi, start, dur, g] of m.bass) this.voice(ctx, master, m.bassWave, midiToFreq(midi), t0 + start, dur, g ?? 0.35, false);
    return ctx.state === "running";
  }

  private voice(ctx: AudioContext, out: AudioNode, wave: OscillatorType, freq: number, start: number, dur: number, peak: number, detune: boolean): void {
    const g = ctx.createGain();
    g.gain.setValueAtTime(0.0001, start);
    g.gain.exponentialRampToValueAtTime(peak, start + 0.015);
    g.gain.exponentialRampToValueAtTime(0.0001, start + dur);
    g.connect(out);
    const osc = ctx.createOscillator();
    osc.type = wave; osc.frequency.value = freq;
    osc.connect(g); osc.start(start); osc.stop(start + dur + 0.05);
    if (detune) {
      const osc2 = ctx.createOscillator();
      osc2.type = wave; osc2.frequency.value = freq; osc2.detune.value = 6;
      const g2 = ctx.createGain();
      g2.gain.setValueAtTime(0.0001, start);
      g2.gain.exponentialRampToValueAtTime(peak * 0.5, start + 0.02);
      g2.gain.exponentialRampToValueAtTime(0.0001, start + dur);
      osc2.connect(g2); g2.connect(out);
      osc2.start(start); osc2.stop(start + dur + 0.05);
    }
  }

  stop(): void {
    if (!this.ctx) return;
    const now = this.ctx.currentTime;
    try {
      const master = this.nodes[0] as GainNode | undefined;
      master?.gain.cancelScheduledValues(now);
      master?.gain.setTargetAtTime(0.0001, now, 0.05);
    } catch { /* */ }
    const ctx = this.ctx;
    this.ctx = null;
    this.nodes = [];
    setTimeout(() => ctx.close().catch(() => { /* */ }), 400);
  }
}

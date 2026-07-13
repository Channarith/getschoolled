// Chunked streaming voice pipeline for real-time conversational agents.
//
// Goal: sub-second "time to first byte" of audio. Instead of waiting for the LLM
// to finish a sentence and the TTS to render the whole clip, we:
//   1. take LLM tokens as they stream in,
//   2. cut them into tiny speakable chunks (an aggressive first chunk of ~3 words,
//      then phrase-sized chunks at punctuation / a word cap),
//   3. synthesize each chunk immediately (prefetch) and play them strictly in
//      order, gaplessly, so the user hears the answer while later chunks render.
//
// SpeechChunker is pure (unit-tested); StreamingVoice owns ordered playback.

export type Playable = { play: () => Promise<void>; cancel: () => void };

export type ChunkOpts = {
  firstChunkWords?: number;  // emit the first chunk this small for low latency
  minWords?: number;         // don't emit a mid-answer chunk shorter than this...
  maxWords?: number;         // ...but never buffer more than this before emitting
};

const PUNCT = /[.!?,;:]$/;

export class SpeechChunker {
  private buf = "";
  private emitted = 0;

  constructor(private opts: ChunkOpts = {}) {}

  /** Add streamed text; return any speakable chunks now ready. */
  feed(delta: string): string[] {
    this.buf += delta;
    const out: string[] = [];
    let c: string | null;
    while ((c = this._take()) !== null) out.push(c);
    return out;
  }

  /** Remaining buffered text (call once the stream ends). */
  flush(): string | null {
    const rest = this.buf.trim();
    this.buf = "";
    if (rest) this.emitted += 1;
    return rest || null;
  }

  private _words(): RegExpMatchArray[] {
    return [...this.buf.matchAll(/\S+/g)];
  }

  private _cut(words: RegExpMatchArray[], i: number): string {
    const end = (words[i].index ?? 0) + words[i][0].length;
    const chunk = this.buf.slice(0, end).trim();
    this.buf = this.buf.slice(end);
    this.emitted += 1;
    return chunk;
  }

  private _take(): string | null {
    const words = this._words();
    if (!words.length) return null;
    const firstWords = this.opts.firstChunkWords ?? 3;
    const minWords = this.opts.minWords ?? 4;
    const maxWords = this.opts.maxWords ?? 9;

    if (this.emitted === 0) {
      // First chunk: get audio out ASAP. Emit at the earliest punctuation within
      // the first `firstWords`, else emit exactly `firstWords` words.
      const limit = Math.min(firstWords, words.length);
      for (let i = 0; i < limit; i++) {
        if (PUNCT.test(words[i][0])) return this._cut(words, i);
      }
      if (words.length >= firstWords) return this._cut(words, firstWords - 1);
      return null;
    }

    // Subsequent chunks: prefer a phrase boundary once we have >= minWords,
    // otherwise cut at the word cap so we never lag behind the stream.
    for (let i = minWords - 1; i < words.length; i++) {
      if (PUNCT.test(words[i][0])) return this._cut(words, i);
    }
    if (words.length >= maxWords) return this._cut(words, maxWords - 1);
    return null;
  }
}

/**
 * Plays synthesized chunks strictly in order, gaplessly. `synth` is called the
 * moment a chunk is enqueued (so audio for chunk N renders while chunk N-1 is
 * still playing); playback of chunk N waits only for its own audio + the prior
 * chunk to finish.
 */
export class StreamingVoice {
  private jobs: Promise<Playable>[] = [];
  private idx = 0;
  private running = false;
  private stopped = false;
  private current: Playable | null = null;

  constructor(private synth: (text: string) => Promise<Playable>) {}

  enqueue(text: string): void {
    if (this.stopped || !text.trim()) return;
    const job = Promise.resolve()
      .then(() => this.synth(text))
      .catch(() => ({ play: async () => {}, cancel: () => {} } as Playable));
    this.jobs.push(job);
    void this._pump();
  }

  private async _pump(): Promise<void> {
    if (this.running) return;
    this.running = true;
    try {
      while (this.idx < this.jobs.length && !this.stopped) {
        const playable = await this.jobs[this.idx];
        this.idx += 1;
        if (this.stopped) { playable.cancel(); break; }
        this.current = playable;
        await playable.play();
        this.current = null;
      }
    } finally {
      this.running = false;
    }
  }

  stop(): void {
    this.stopped = true;
    try { this.current?.cancel(); } catch { /* */ }
    this.current = null;
  }

  /** Resolve once every enqueued chunk has finished playing. */
  async drained(): Promise<void> {
    while (!this.stopped && (this.running || this.idx < this.jobs.length)) {
      await new Promise((r) => setTimeout(r, 25));
    }
  }
}

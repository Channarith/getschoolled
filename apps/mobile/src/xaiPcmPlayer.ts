import { Audio } from "expo-av";
import * as FileSystem from "expo-file-system";

import { concatBytes, decodeBase64, encodeBase64, pcm16ToWav } from "./xaiPcm";
import { ensureSpeechAudioSession } from "./tts";

export type PcmQueue = {
  push(base64Pcm: string): void;
  /** Play whatever is buffered, then run `after` when that audio finishes. */
  flush(after?: () => void): void;
  stop(): void;
};

export function createPcmQueue(): PcmQueue {
  let gen = 0;
  let pending: Uint8Array[] = [];
  let timer: ReturnType<typeof setTimeout> | null = null;
  let chain: Promise<void> = Promise.resolve();
  let sound: Audio.Sound | null = null;

  async function play(pcm: Uint8Array, token: number): Promise<void> {
    if (!pcm.length || token !== gen || !FileSystem.cacheDirectory) return;
    const wav = pcm16ToWav(pcm);
    const file = `${FileSystem.cacheDirectory}xai-voice-${token}-${Date.now()}.wav`;
    await FileSystem.writeAsStringAsync(file, encodeBase64(wav), { encoding: "base64" });
    if (token !== gen) {
      await FileSystem.deleteAsync(file, { idempotent: true }).catch(() => undefined);
      return;
    }
    await ensureSpeechAudioSession();
    const created = await Audio.Sound.createAsync({ uri: file }, { shouldPlay: true });
    sound = created.sound;
    const durationMs = Math.min(120000, Math.max(1000, (pcm.length / 2 / 24000) * 1000 + 750));
    await new Promise<void>((resolve) => {
      const timer = setTimeout(resolve, durationMs);
      const done = () => {
        clearTimeout(timer);
        resolve();
      };
      created.sound.setOnPlaybackStatusUpdate((status) => {
        if (token !== gen) {
          done();
          return;
        }
        if (!status.isLoaded) {
          if (status.error) done();
          return;
        }
        if (status.didJustFinish) done();
      });
    });
    await created.sound.unloadAsync().catch(() => undefined);
    if (sound === created.sound) sound = null;
    await FileSystem.deleteAsync(file, { idempotent: true }).catch(() => undefined);
  }

  function take(): Uint8Array {
    if (timer) {
      clearTimeout(timer);
      timer = null;
    }
    const chunk = concatBytes(pending);
    pending = [];
    return chunk;
  }

  function enqueuePlay(pcm: Uint8Array, after?: () => void): void {
    const token = gen;
    chain = chain.then(async () => {
      if (token !== gen) return;
      if (pcm.length) await play(pcm, token).catch(() => undefined);
      if (token === gen) after?.();
    });
  }

  return {
    push(base64Pcm: string) {
      const chunk = decodeBase64(base64Pcm);
      if (!chunk.length) return;
      pending.push(chunk);
      if (!timer) {
        timer = setTimeout(() => {
          timer = null;
          const pcm = take();
          if (pcm.length) enqueuePlay(pcm);
        }, 160);
      }
    },
    flush(after?: () => void) {
      const pcm = take();
      enqueuePlay(pcm, after);
    },
    stop() {
      gen += 1;
      pending = [];
      if (timer) {
        clearTimeout(timer);
        timer = null;
      }
      const current = sound;
      sound = null;
      if (current) void current.stopAsync().catch(() => undefined);
    },
  };
}

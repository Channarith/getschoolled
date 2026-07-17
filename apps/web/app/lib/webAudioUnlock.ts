/**
 * Chrome/Safari block AudioContext until a user gesture. LiveKit calls
 * acquireAudioContext() during room.connect(), which runs in a useEffect —
 * outside the click handler that joined the room. Pre-create + resume a shared
 * context synchronously inside the gesture handler, then pass it to LiveKit.
 */

type AudioCtor = typeof AudioContext;

function audioCtor(): AudioCtor | null {
  if (typeof window === "undefined") return null;
  const w = window as Window & {
    AudioContext?: AudioCtor;
    webkitAudioContext?: AudioCtor;
  };
  return w.AudioContext ?? w.webkitAudioContext ?? null;
}

let sharedCtx: AudioContext | null = null;

/** Call synchronously from click/tap/keydown handlers before any await. */
export function unlockWebAudio(): AudioContext | null {
  const Ctor = audioCtor();
  if (!Ctor) return null;
  if (!sharedCtx || sharedCtx.state === "closed") {
    sharedCtx = new Ctor();
  }
  if (sharedCtx.state === "suspended") {
    void sharedCtx.resume().catch(() => undefined);
  }
  return sharedCtx;
}

export function getSharedAudioContext(): AudioContext | null {
  return sharedCtx;
}

/** Best-effort resume — must run inside a user-gesture handler. */
export async function resumeSharedAudioContext(): Promise<boolean> {
  const ctx = unlockWebAudio();
  if (!ctx) return false;
  if (ctx.state === "running") return true;
  try {
    await ctx.resume();
  } catch {
    return false;
  }
  return (ctx.state as string) === "running";
}

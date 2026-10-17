/** Live speech-to-speech engine for Sala (Salane vs optional xAI Grok). */

export type LiveVoiceEngine = "salane" | "xai";

const STORAGE_KEY = "aoep_live_voice_engine";

export function getLiveVoiceEngine(): LiveVoiceEngine {
  if (typeof window === "undefined") return "salane";
  try {
    const raw = (localStorage.getItem(STORAGE_KEY) || "").trim().toLowerCase();
    return raw === "xai" ? "xai" : "salane";
  } catch {
    return "salane";
  }
}

export function setLiveVoiceEngine(engine: LiveVoiceEngine): LiveVoiceEngine {
  try {
    localStorage.setItem(STORAGE_KEY, engine);
  } catch {
    /* private mode */
  }
  return engine;
}

/** Value sent to POST /speech/voice/token — only xAI requests include engine. */
export function voiceTokenEngineField(engine: LiveVoiceEngine): { engine?: string } {
  return engine === "xai" ? { engine: "xai" } : {};
}

/**
 * xAI Grok Voice Agent client for Theodore / self-teach speech-to-speech.
 *
 * Flow:
 *  1. GET  /speech/voice/status     — is XAI_API_KEY configured server-side?
 *  2. POST /speech/voice/token      — mint ephemeral client secret (key never
 *                                     reaches the browser)
 *  3. Open wss://api.x.ai/v1/realtime with
 *     sec-websocket-protocol: xai-client-secret.<token>
 *  4. Send session_update from the token response, then stream mic PCM /
 *     play assistant audio deltas.
 *
 * Falls back cleanly when the speech service reports available=false.
 */

import { SPEECH_URL } from "./api";

export type XaiVoiceStatus = {
  available: boolean;
  engine: string;
  model: string;
  voice: string;
  realtime_ws: string;
  hint: string;
  display_name?: string;
  short_name?: string;
};

/** Salane Voice (Sala) is the CosyVoice class voice. */
export function isSalaneEngine(engine: string | undefined): boolean {
  return (engine || "").trim().toLowerCase().startsWith("salane");
}

export type XaiVoiceToken = {
  value: string;
  expires_at: number;
  mock: boolean;
  model: string;
  websocket_url: string;
  websocket_protocol: string;
};

export type XaiSpokenLanguage = {
  requested: string;
  engine: string;
  use_xai: boolean;
  xai_language: string;
  instructions: string;
  edge_voice: string;
  hint: string;
  reason: string;
};

export type XaiVoiceTokenResponse = {
  token: XaiVoiceToken | null;
  session_update: {
    type: string;
    session: Record<string, unknown>;
  } | null;
  mode: string;
  xai_configured: boolean;
  engine: string;
  display_name?: string;
  short_name?: string;
  /** False for Khmer and Cantonese on xAI, and for Salane Voice (CosyVoice). */
  use_xai?: boolean;
  spoken_language?: XaiSpokenLanguage;
  hint?: string;
};

/** Khmer and Cantonese are narrated by the speech gateway, not the Grok socket.
 * xAI speech-to-speech has no Khmer voice (it sounded Thai) and no Cantonese
 * code (an ignored hint auto-detects Mandarin). */
export function xaiSpeaksLocale(language: string | undefined): boolean {
  const raw = (language || "").trim().toLowerCase().replace(/_/g, "-");
  if (!raw) return true;
  if (raw === "km" || raw.startsWith("km-")) return false;
  if (
    raw === "yue" || raw.startsWith("yue-") ||
    raw === "zh-hk" || raw.startsWith("zh-hk") ||
    raw === "zh-mo" || raw.startsWith("zh-mo") ||
    raw === "cantonese"
  ) return false;
  return true;
}

export type XaiVoiceMode = "solo" | "group" | "self_teach" | "theodore_solo" | "theodore_group";

export async function getXaiVoiceStatus(): Promise<XaiVoiceStatus> {
  const r = await fetch(`${SPEECH_URL}/voice/status`, { cache: "no-store" });
  if (!r.ok) {
    return {
      available: false,
      engine: "none",
      model: "",
      voice: "",
      realtime_ws: "wss://api.x.ai/v1/realtime",
      hint: `voice/status HTTP ${r.status}`,
    };
  }
  return r.json();
}

export async function mintXaiVoiceToken(opts: {
  mode?: XaiVoiceMode | string;
  lesson_context?: string;
  learner_names?: string[];
  expires_seconds?: number;
  instructions?: string;
  category?: string;
  topic?: string;
  course_id?: string;
  language?: string;
  /** Send engine:"xai" only when the user opted in; omit for default Salane Voice. */
  engine?: "xai" | "salane" | "";
}): Promise<XaiVoiceTokenResponse> {
  const body: Record<string, unknown> = {
    mode: opts.mode || "solo",
    lesson_context: opts.lesson_context || "",
    learner_names: opts.learner_names || [],
    expires_seconds: opts.expires_seconds ?? 300,
    instructions: opts.mode === "drive" ? "" : (opts.instructions || ""),
    category: opts.category || "",
    topic: opts.topic || "",
    course_id: opts.course_id || "",
    language: opts.language || "",
  };
  if ((opts.engine || "").trim().toLowerCase() === "xai") {
    body.engine = "xai";
  }
  const r = await fetch(`${SPEECH_URL}/voice/token`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    const detail = await r.text().catch(() => "");
    throw new Error(`xAI voice token failed (${r.status}): ${detail.slice(0, 200)}`);
  }
  return r.json();
}

export type XaiVoiceSessionHandlers = {
  onOpen?: () => void;
  onClose?: (ev: CloseEvent) => void;
  onError?: (err: Event | Error) => void;
  onEvent?: (event: Record<string, unknown>) => void;
  /** PCM16 base64 chunks from the assistant (24 kHz by default). */
  onAudioDelta?: (base64Pcm: string) => void;
  onTranscriptDelta?: (text: string) => void;
  onTranscriptDone?: (text: string) => void;
};

/**
 * Open a browser WebSocket to xAI realtime using an ephemeral token.
 * Browser WebSockets cannot set Authorization headers — use the protocol list.
 */
export function connectXaiVoiceSession(
  tokenResponse: XaiVoiceTokenResponse,
  handlers: XaiVoiceSessionHandlers = {},
): WebSocket {
  const { token, session_update } = tokenResponse;
  if (!token || !session_update) {
    throw new Error("xAI voice session was not minted for this language");
  }
  const url = token.websocket_url || `wss://api.x.ai/v1/realtime?model=${token.model || "grok-voice-latest"}`;
  const protocol = token.websocket_protocol || `xai-client-secret.${token.value}`;
  const ws = new WebSocket(url, [protocol]);

  ws.binaryType = "arraybuffer";

  ws.onopen = () => {
    try {
      ws.send(JSON.stringify(session_update));
    } catch (err) {
      handlers.onError?.(err instanceof Error ? err : new Error(String(err)));
    }
    handlers.onOpen?.();
  };

  ws.onmessage = (ev) => {
    let event: Record<string, unknown>;
    try {
      event = typeof ev.data === "string" ? JSON.parse(ev.data) : {};
    } catch {
      return;
    }
    handlers.onEvent?.(event);
    const type = String(event.type || "");
    if (
      type === "response.output_audio.delta" ||
      type === "response.audio.delta"
    ) {
      const delta = String(event.delta || "");
      if (delta) handlers.onAudioDelta?.(delta);
    }
    if (
      type === "response.output_audio_transcript.delta" ||
      type === "response.audio_transcript.delta"
    ) {
      handlers.onTranscriptDelta?.(String(event.delta || ""));
    }
    if (
      type === "response.output_audio_transcript.done" ||
      type === "response.audio_transcript.done"
    ) {
      handlers.onTranscriptDone?.(String(event.transcript || event.text || ""));
    }
  };

  ws.onerror = (ev) => handlers.onError?.(ev);
  ws.onclose = (ev) => handlers.onClose?.(ev);
  return ws;
}

/** Append mic PCM16 (base64) to the realtime input buffer. */
export function appendInputAudio(ws: WebSocket, base64Pcm16: string): void {
  if (ws.readyState !== WebSocket.OPEN) return;
  ws.send(
    JSON.stringify({
      type: "input_audio_buffer.append",
      audio: base64Pcm16,
    }),
  );
}

/** Send a text user turn (useful when mic isn't available yet). */
export function sendTextTurn(ws: WebSocket, text: string): void {
  if (ws.readyState !== WebSocket.OPEN) return;
  ws.send(
    JSON.stringify({
      type: "conversation.item.create",
      item: {
        type: "message",
        role: "user",
        content: [{ type: "input_text", text }],
      },
    }),
  );
  ws.send(JSON.stringify({ type: "response.create" }));
}

export function closeXaiVoiceSession(ws: WebSocket | null | undefined): void {
  if (!ws) return;
  try {
    if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
      ws.close();
    }
  } catch {
    /* ignore */
  }
}

const pcmPlayAt = new WeakMap<AudioContext, number>();

/** Drop a previous utterance's schedule so the next reply starts immediately. */
export function resetPcmPlayback(ctx: AudioContext | null | undefined): void {
  if (ctx) pcmPlayAt.delete(ctx);
}

/**
 * Decode base64 PCM16 LE @ 24 kHz and schedule it on one timeline.
 * The AudioContext stays at the device rate; locking it to 24 kHz, or calling
 * start() on every chunk at once, is what made the tutor sound choppy.
 */
export async function playPcm16Base64(
  base64: string,
  ctx: AudioContext,
  sampleRate = 24000,
): Promise<void> {
  const raw = atob(base64);
  const bytes = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
  const samples = new Int16Array(bytes.buffer, bytes.byteOffset, Math.floor(bytes.byteLength / 2));
  if (!samples.length) return;
  const float = new Float32Array(samples.length);
  for (let i = 0; i < samples.length; i++) float[i] = samples[i] / 32768;
  const buffer = ctx.createBuffer(1, float.length, sampleRate);
  buffer.copyToChannel(float, 0);
  const src = ctx.createBufferSource();
  src.buffer = buffer;
  src.connect(ctx.destination);
  const queued = pcmPlayAt.get(ctx) || 0;
  const at = Math.max(ctx.currentTime + 0.02, queued);
  src.start(at);
  pcmPlayAt.set(ctx, at + buffer.duration);
  await new Promise<void>((resolve) => {
    src.onended = () => resolve();
  });
}

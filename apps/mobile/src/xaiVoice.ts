/**
 * xAI Grok Voice Agent helpers for mobile (Theodore / self-teach).
 *
 * Mints an ephemeral client secret from the speech gateway so the API key
 * never ships in the app binary. React Native WebSocket supports the
 * sec-websocket-protocol list the same way browsers do.
 */

import { SPEECH_URL } from "./config";

export type XaiVoiceStatus = {
  available: boolean;
  engine: string;
  model: string;
  voice: string;
  realtime_ws: string;
  hint: string;
};

export type XaiVoiceToken = {
  value: string;
  expires_at: number;
  mock: boolean;
  model: string;
  websocket_url: string;
  websocket_protocol: string;
};

export type XaiVoiceTokenResponse = {
  token: XaiVoiceToken;
  session_update: {
    type: string;
    session: Record<string, unknown>;
  };
  mode: string;
  xai_configured: boolean;
  engine: string;
};

export type XaiVoiceMode = "solo" | "group" | "self_teach" | "theodore_solo" | "theodore_group";

export async function getXaiVoiceStatus(): Promise<XaiVoiceStatus> {
  try {
    const r = await fetch(`${SPEECH_URL}/voice/status`);
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
    return await r.json();
  } catch (err) {
    return {
      available: false,
      engine: "none",
      model: "",
      voice: "",
      realtime_ws: "wss://api.x.ai/v1/realtime",
      hint: err instanceof Error ? err.message : "voice/status unreachable",
    };
  }
}

export async function mintXaiVoiceToken(opts: {
  mode?: XaiVoiceMode | string;
  lesson_context?: string;
  learner_names?: string[];
  expires_seconds?: number;
  instructions?: string;
}): Promise<XaiVoiceTokenResponse> {
  const r = await fetch(`${SPEECH_URL}/voice/token`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      mode: opts.mode || "solo",
      lesson_context: opts.lesson_context || "",
      learner_names: opts.learner_names || [],
      expires_seconds: opts.expires_seconds ?? 300,
      instructions: opts.instructions || "",
    }),
  });
  if (!r.ok) {
    const detail = await r.text().catch(() => "");
    throw new Error(`xAI voice token failed (${r.status}): ${detail.slice(0, 200)}`);
  }
  return r.json();
}

export type XaiVoiceSessionHandlers = {
  onOpen?: () => void;
  onClose?: (code: number, reason: string) => void;
  onError?: (err: unknown) => void;
  onEvent?: (event: Record<string, unknown>) => void;
  onAudioDelta?: (base64Pcm: string) => void;
  onTranscriptDelta?: (text: string) => void;
  onTranscriptDone?: (text: string) => void;
};

export function connectXaiVoiceSession(
  tokenResponse: XaiVoiceTokenResponse,
  handlers: XaiVoiceSessionHandlers = {},
): WebSocket {
  const { token, session_update } = tokenResponse;
  const url =
    token.websocket_url ||
    `wss://api.x.ai/v1/realtime?model=${token.model || "grok-voice-latest"}`;
  const protocol = token.websocket_protocol || `xai-client-secret.${token.value}`;
  const ws = new WebSocket(url, [protocol]);

  ws.onopen = () => {
    try {
      ws.send(JSON.stringify(session_update));
    } catch (err) {
      handlers.onError?.(err);
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
    if (type === "response.output_audio.delta" || type === "response.audio.delta") {
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
  ws.onclose = (ev) => handlers.onClose?.(ev.code ?? 0, ev.reason || "");
  return ws;
}

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

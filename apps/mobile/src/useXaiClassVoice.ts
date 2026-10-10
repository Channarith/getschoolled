import { useCallback, useEffect, useRef, useState } from "react";

import { createPcmQueue, type PcmQueue } from "./xaiPcmPlayer";
import {
  cancelXaiResponse,
  closeXaiVoiceSession,
  connectXaiVoiceSession,
  getXaiVoiceStatus,
  mintXaiVoiceToken,
  sendTextTurn,
  type XaiVoiceMode,
} from "./xaiVoice";

export type XaiSpeakOpts = {
  onDone?: () => void;
  fallback?: () => void;
};

type Queued = XaiSpeakOpts & { id: string; text: string; gen: number };

/**
 * Connects Theodore's xAI Grok voice once class is allowed to start.
 * Speech is queued until the socket is open. If the speech service has no
 * XAI_API_KEY, each request runs `fallback` (device narration) instead.
 */
export function useXaiClassVoice(
  active: boolean,
  session: {
    mode: XaiVoiceMode;
    context: string;
    learnerName?: string;
    onTranscript?: (text: string) => void;
  },
) {
  const [phase, setPhase] = useState<"idle" | "checking" | "live" | "unavailable">("idle");
  const [hint, setHint] = useState("");
  const sessionRef = useRef(session);
  sessionRef.current = session;
  const wsRef = useRef<WebSocket | null>(null);
  const pcmRef = useRef<PcmQueue | null>(null);
  const queueRef = useRef<Queued[]>([]);
  const inflightRef = useRef<Queued | null>(null);
  const sentRef = useRef<Set<string>>(new Set());
  const genRef = useRef(0);
  const finishedGenRef = useRef<number | null>(null);
  const heardAudioForRef = useRef<number | null>(null);
  const phaseRef = useRef(phase);
  phaseRef.current = phase;

  const finishInflight = useCallback((gen: number) => {
    const current = inflightRef.current;
    inflightRef.current = null;
    if (current && current.gen === gen) current.onDone?.();
    const ws = wsRef.current;
    const next = queueRef.current.shift();
    if (!next || !ws || ws.readyState !== WebSocket.OPEN) return;
    inflightRef.current = next;
    sentRef.current.add(next.id);
    sendTextTurn(ws, next.text);
  }, []);

  const drainFallback = useCallback(() => {
    const pending = queueRef.current.splice(0);
    inflightRef.current = null;
    for (const item of pending) {
      sentRef.current.add(item.id);
      item.fallback?.();
    }
  }, []);

  useEffect(() => {
    if (!active) {
      setPhase("idle");
      return;
    }
    let cancelled = false;
    setPhase("checking");
    pcmRef.current = createPcmQueue();
    (async () => {
      const status = await getXaiVoiceStatus();
      if (cancelled) return;
      if (!status.available) {
        setPhase("unavailable");
        setHint(status.hint || "Grok voice needs XAI_API_KEY on the speech service.");
        drainFallback();
        return;
      }
      try {
        const current = sessionRef.current;
        const token = await mintXaiVoiceToken({
          mode: current.mode,
          lesson_context: current.context,
          learner_names: current.learnerName ? [current.learnerName] : [],
        });
        if (cancelled) return;
        const ws = connectXaiVoiceSession(token, {
          onOpen: () => {
            if (cancelled) return;
            setPhase("live");
            setHint("Theodore is using Grok voice.");
            const next = queueRef.current.shift();
            if (!next) return;
            inflightRef.current = next;
            sentRef.current.add(next.id);
            sendTextTurn(ws, next.text);
          },
          onAudioDelta: (chunk) => {
            const gen = inflightRef.current?.gen;
            if (gen != null) heardAudioForRef.current = gen;
            pcmRef.current?.push(chunk);
          },
          onTranscriptDone: (text) => {
            if (text) sessionRef.current.onTranscript?.(text);
          },
          onEvent: (event) => {
            const type = String(event.type || "");
            if (type !== "response.done" && type !== "response.output_audio.done") return;
            const gen = inflightRef.current?.gen;
            if (gen == null || heardAudioForRef.current !== gen || finishedGenRef.current === gen) return;
            finishedGenRef.current = gen;
            pcmRef.current?.flush(() => {
              if (inflightRef.current?.gen === gen) finishInflight(gen);
            });
          },
          onError: () => {
            if (!cancelled) setHint("Grok voice connection error — check the speech service.");
          },
          onClose: () => {
            if (cancelled) return;
            wsRef.current = null;
            if (phaseRef.current === "live") {
              setPhase("unavailable");
              setHint("Grok voice disconnected.");
              drainFallback();
            }
          },
        });
        wsRef.current = ws;
      } catch (err) {
        if (cancelled) return;
        setPhase("unavailable");
        setHint(err instanceof Error ? err.message : "Could not start Grok voice.");
        drainFallback();
      }
    })();
    return () => {
      cancelled = true;
      pcmRef.current?.stop();
      pcmRef.current = null;
      closeXaiVoiceSession(wsRef.current);
      wsRef.current = null;
      inflightRef.current = null;
      queueRef.current = [];
      sentRef.current = new Set();
    };
  }, [active, session.mode, drainFallback, finishInflight]);

  const interrupt = useCallback(() => {
    genRef.current += 1;
    inflightRef.current = null;
    queueRef.current = [];
    heardAudioForRef.current = null;
    cancelXaiResponse(wsRef.current);
    pcmRef.current?.stop();
    pcmRef.current = createPcmQueue();
  }, []);

  const speakLatest = useCallback((id: string, text: string, opts: XaiSpeakOpts = {}) => {
    const spoken = text.trim();
    if (!spoken || sentRef.current.has(id)) return;
    const item: Queued = { id, text: spoken, gen: genRef.current + 1, ...opts };
    genRef.current = item.gen;
    if (!active || phaseRef.current === "unavailable") {
      sentRef.current.add(id);
      opts.fallback?.();
      return;
    }
    const ws = wsRef.current;
    if (phaseRef.current === "live" && ws && ws.readyState === WebSocket.OPEN) {
      cancelXaiResponse(ws);
      heardAudioForRef.current = null;
      pcmRef.current?.stop();
      pcmRef.current = createPcmQueue();
      inflightRef.current = item;
      queueRef.current = [];
      sentRef.current.add(id);
      sendTextTurn(ws, spoken);
      return;
    }
    queueRef.current = queueRef.current.filter((queued) => queued.id !== id).concat(item);
  }, [active]);

  return {
    phase,
    live: phase === "live",
    hint,
    speakLatest,
    interrupt,
  };
}

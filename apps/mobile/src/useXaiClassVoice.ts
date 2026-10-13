import { useCallback, useEffect, useRef, useState } from "react";

import { speakNatural, stopSpeech } from "./tts";
import {
  audioJustStarted,
  createSpeakPlan,
  noteAgentFailure,
  noteAudio,
  noteResponseEnd,
  requestSpeak,
  takeQueuedForSend,
  takeUnheardForFallback,
  type PlannedTurn,
  type SpeakPlan,
} from "./xaiSpeakPlan";
import { createPcmQueue, type PcmQueue } from "./xaiPcmPlayer";
import { SERENITY_NAME, SERENITY_VOICE_INSTRUCTIONS } from "./serenity";
import {
  cancelXaiResponse,
  closeXaiVoiceSession,
  connectXaiVoiceSession,
  getXaiVoiceStatus,
  isSalaneEngine,
  mintXaiVoiceToken,
  sendTextTurn,
  xaiSpeaksLocale,
  type XaiVoiceMode,
} from "./xaiVoice";

export type XaiSpeakOpts = {
  onDone?: () => void;
  fallback?: () => void;
};

/**
 * Connects Serenity's xAI Grok voice once class is allowed to start.
 * Each line is spoken once. If the speech service has no voice agent, or the
 * socket drops before any audio arrives, `fallback` (device narration) runs
 * instead. Audio that already started is not spoken again on device.
 */
export function useXaiClassVoice(
  active: boolean,
  session: {
    mode: XaiVoiceMode | "drive";
    context: string;
    learnerName?: string;
    language?: string;
    onTranscript?: (text: string) => void;
    category?: string;
    topic?: string;
    courseId?: string;
  },
) {
  const [phase, setPhase] = useState<"idle" | "checking" | "live" | "unavailable">("idle");
  const [hint, setHint] = useState("");
  const sessionRef = useRef(session);
  sessionRef.current = session;
  const wsRef = useRef<WebSocket | null>(null);
  const pcmRef = useRef<PcmQueue | null>(null);
  const planRef = useRef<SpeakPlan>(createSpeakPlan());
  const optsRef = useRef<Map<string, XaiSpeakOpts>>(new Map());

  const runFallback = useCallback((turns: PlannedTurn[]) => {
    if (!turns.length) return;
    pcmRef.current?.stop();
    cancelXaiResponse(wsRef.current);
    stopSpeech();
    for (const turn of turns) {
      const opts = optsRef.current.get(turn.id);
      optsRef.current.delete(turn.id);
      opts?.fallback?.();
    }
  }, []);

  useEffect(() => {
    if (!active) {
      planRef.current = createSpeakPlan();
      setPhase("idle");
      return;
    }
    let cancelled = false;
    const plan = createSpeakPlan();
    plan.phase = "checking";
    planRef.current = plan;
    setPhase("checking");
    pcmRef.current = createPcmQueue();
    (async () => {
      const status = await getXaiVoiceStatus();
      if (cancelled || planRef.current !== plan) return;
      if (isSalaneEngine(status.engine) && status.available) {
        plan.phase = "live";
        setPhase("live");
        setHint("Sala is using Salane Voice.");
        const next = takeQueuedForSend(plan);
        if (next) {
          stopSpeech();
          speakNatural(next.text, {
            locale: sessionRef.current.language || "en",
            onDone: () => optsRef.current.get(next.id)?.onDone?.(),
          });
        }
        return;
      }
      const currentLanguage = sessionRef.current.language || "";
      if (!xaiSpeaksLocale(currentLanguage)) {
        plan.phase = "unavailable";
        setPhase("unavailable");
        const raw = currentLanguage.trim().toLowerCase();
        setHint(
          raw === "km" || raw.startsWith("km-")
            ? "Khmer uses a Cambodian voice, not Grok."
            : "Cantonese uses a Hong Kong voice, not Grok.",
        );
        runFallback(takeUnheardForFallback(plan));
        return;
      }
      if (!status.available) {
        plan.phase = "unavailable";
        setPhase("unavailable");
        setHint(status.hint || "Grok voice needs XAI_API_KEY on the speech service.");
        runFallback(takeUnheardForFallback(plan));
        return;
      }
      try {
        const current = sessionRef.current;
        const token = await mintXaiVoiceToken({
          mode: current.mode,
          lesson_context: current.context,
          learner_names: current.learnerName ? [current.learnerName] : [],
          language: current.language || "",
          category: current.category || "",
          topic: current.topic || "",
          course_id: current.courseId || "",
          instructions: SERENITY_VOICE_INSTRUCTIONS,
        });
        if (cancelled || planRef.current !== plan) return;
        if (token.use_xai === false || !token.token || !token.session_update) {
          plan.phase = "unavailable";
          setPhase("unavailable");
          setHint(token.spoken_language?.hint || "This language uses the lesson voice, not Grok.");
          runFallback(takeUnheardForFallback(plan));
          return;
        }
        const ws = connectXaiVoiceSession(token, {
          onOpen: () => {
            if (cancelled || planRef.current !== plan) return;
            setPhase("live");
            setHint(`${SERENITY_NAME} is using Grok voice.`);
            const next = takeQueuedForSend(plan);
            if (!next) return;
            stopSpeech();
            sendTextTurn(ws, next.text);
          },
          onAudioDelta: (chunk) => {
            const gen = plan.inflight?.gen ?? null;
            const heardBefore = plan.heardGen;
            if (noteAudio(plan, gen) === "drop") return;
            if (audioJustStarted(plan, gen, heardBefore)) stopSpeech();
            pcmRef.current?.push(chunk);
          },
          onTranscriptDone: (text) => {
            if (text) sessionRef.current.onTranscript?.(text);
          },
          onEvent: (event) => {
            const type = String(event.type || "");
            const status = String(
              (event.response as { status?: string } | undefined)?.status
              || event.status
              || "",
            );
            if (type === "error" || status === "failed" || status === "incomplete") {
              const failed = noteAgentFailure(plan);
              if (failed) {
                runFallback([failed]);
                return;
              }
            }
            if (type !== "response.done" && type !== "response.output_audio.done") return;
            if (noteResponseEnd(plan) !== "finish") return;
            const gen = plan.inflight?.gen;
            pcmRef.current?.flush(() => {
              if (plan.inflight?.gen !== gen) return;
              const done = plan.inflight;
              plan.inflight = null;
              const opts = done ? optsRef.current.get(done.id) : undefined;
              if (done) optsRef.current.delete(done.id);
              opts?.onDone?.();
              if (plan.inflight || plan.phase !== "live") return;
              const socket = wsRef.current;
              if (!socket || socket.readyState !== WebSocket.OPEN) return;
              const next = takeQueuedForSend(plan);
              if (!next) return;
              stopSpeech();
              sendTextTurn(socket, next.text);
            });
          },
          onError: () => {
            if (cancelled || planRef.current !== plan) return;
            setHint("Grok voice connection error — check the speech service.");
            plan.phase = "unavailable";
            setPhase("unavailable");
            runFallback(takeUnheardForFallback(plan));
          },
          onClose: () => {
            if (cancelled || planRef.current !== plan) return;
            wsRef.current = null;
            if (plan.phase === "idle") return;
            plan.phase = "unavailable";
            setPhase("unavailable");
            setHint("Grok voice disconnected.");
            runFallback(takeUnheardForFallback(plan));
          },
        });
        wsRef.current = ws;
      } catch (err) {
        if (cancelled || planRef.current !== plan) return;
        plan.phase = "unavailable";
        setPhase("unavailable");
        setHint(err instanceof Error ? err.message : "Could not start Grok voice.");
        runFallback(takeUnheardForFallback(plan));
      }
    })();
    return () => {
      cancelled = true;
      pcmRef.current?.stop();
      pcmRef.current = null;
      closeXaiVoiceSession(wsRef.current);
      wsRef.current = null;
    };
  }, [active, session.mode, session.language, session.courseId, session.category, session.topic, runFallback]);

  const interrupt = useCallback(() => {
    const plan = planRef.current;
    plan.gen += 1;
    if (plan.inflight) {
      plan.sent.add(plan.inflight.id);
      plan.finishedGen = plan.inflight.gen;
      plan.inflight = null;
    }
    for (const queued of plan.queue) plan.sent.add(queued.id);
    plan.queue = [];
    plan.heardGen = null;
    cancelXaiResponse(wsRef.current);
    pcmRef.current?.stop();
    pcmRef.current = createPcmQueue();
    stopSpeech();
  }, []);

  const speakLatest = useCallback((id: string, text: string, opts: XaiSpeakOpts = {}) => {
    const plan = planRef.current;
    optsRef.current.set(id, opts);
    const ws = wsRef.current;
    const salane = plan.phase === "live" && !ws;
    const canSend = salane || Boolean(ws && ws.readyState === WebSocket.OPEN && plan.phase === "live");
    const decision = requestSpeak(plan, id, text, active, canSend);
    if (decision.kind === "ignore") return;
    optsRef.current.set(id, opts);
    if (decision.kind === "queue") return;
    if (decision.kind === "fallback") {
      runFallback([decision.turn]);
      return;
    }
    stopSpeech();
    cancelXaiResponse(ws);
    pcmRef.current?.stop();
    pcmRef.current = createPcmQueue();
    if (salane) {
      speakNatural(decision.turn.text, {
        locale: sessionRef.current.language || "en",
        onDone: () => opts.onDone?.(),
      });
      return;
    }
    if (ws) sendTextTurn(ws, decision.turn.text);
  }, [active, runFallback]);

  return {
    phase,
    live: phase === "live",
    hint,
    speakLatest,
    interrupt,
  };
}

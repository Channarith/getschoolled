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
import { useT } from "./i18n";
import { SERENITY_VOICE_INSTRUCTIONS } from "./serenity";
import {
  loadVoiceAgentChoice,
  publicVoiceError,
  subscribeVoiceAgent,
  type VoiceAgentChoice,
} from "./voiceAgentPref";
import {
  cancelXaiResponse,
  closeXaiVoiceSession,
  connectXaiVoiceSession,
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
 * Class voice for Sala or the xAI Voice Agent.
 * Sala narrates through the speech gateway. xAI uses a server-minted
 * ephemeral session. If xAI cannot start, the hook reports the error and
 * does not narrate with Sala instead. Audio that already started is not
 * spoken again.
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
  agentOverride?: VoiceAgentChoice,
) {
  const { t } = useT();
  const [phase, setPhase] = useState<"idle" | "checking" | "live" | "unavailable">("idle");
  const [hint, setHint] = useState("");
  const [storedChoice, setStoredChoice] = useState<VoiceAgentChoice | null>(null);
  const choice = agentOverride ?? storedChoice;
  const sessionRef = useRef(session);
  sessionRef.current = session;
  const wsRef = useRef<WebSocket | null>(null);
  const pcmRef = useRef<PcmQueue | null>(null);
  const planRef = useRef<SpeakPlan>(createSpeakPlan());
  const optsRef = useRef<Map<string, XaiSpeakOpts>>(new Map());
  const agentRef = useRef<VoiceAgentChoice>(choice ?? "sala");
  agentRef.current = choice ?? "sala";

  const runFallback = useCallback((turns: PlannedTurn[]) => {
    if (!turns.length) return;
    pcmRef.current?.stop();
    cancelXaiResponse(wsRef.current);
    stopSpeech();
    for (const turn of turns) {
      const opts = optsRef.current.get(turn.id);
      optsRef.current.delete(turn.id);
      if (agentRef.current === "xai") continue;
      opts?.fallback?.();
    }
  }, []);

  useEffect(() => {
    if (agentOverride) return;
    let cancelled = false;
    void loadVoiceAgentChoice().then((next) => {
      if (!cancelled) setStoredChoice(next);
    });
    const unsubscribe = subscribeVoiceAgent((next) => {
      if (!cancelled) setStoredChoice(next);
    });
    return () => {
      cancelled = true;
      unsubscribe();
    };
  }, [agentOverride]);

  useEffect(() => {
    if (!active) {
      planRef.current = createSpeakPlan();
      setPhase("idle");
      return;
    }
    if (choice == null) {
      setPhase("checking");
      return;
    }
    let cancelled = false;
    const plan = createSpeakPlan();
    plan.phase = "checking";
    planRef.current = plan;
    setPhase("checking");
    pcmRef.current = createPcmQueue();
    const selected = choice;
    agentRef.current = selected;
    (async () => {
      if (cancelled || planRef.current !== plan) return;
      if (selected === "sala") {
        plan.phase = "live";
        setPhase("live");
        setHint(t("voice.salaLive"));
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
      setHint(t("voice.xaiChecking"));
      const currentLanguage = sessionRef.current.language || "";
      if (!xaiSpeaksLocale(currentLanguage)) {
        plan.phase = "unavailable";
        setPhase("unavailable");
        setHint(t("voice.xaiLanguage"));
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
          engine: "xai",
        });
        if (cancelled || planRef.current !== plan) return;
        if (token.use_xai === false || !token.token || !token.session_update) {
          plan.phase = "unavailable";
          setPhase("unavailable");
          setHint(publicVoiceError(
            token.spoken_language?.hint || token.hint || "",
            t("voice.xaiLanguage"),
          ));
          runFallback(takeUnheardForFallback(plan));
          return;
        }
        const ws = connectXaiVoiceSession(token, {
          onOpen: () => {
            if (cancelled || planRef.current !== plan) return;
            setPhase("live");
            setHint(t("voice.xaiLive"));
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
                if (agentRef.current === "xai") setHint(t("voice.xaiUnavailable"));
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
            setHint(t("voice.xaiUnavailable"));
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
            setHint(t("voice.xaiDisconnected"));
            runFallback(takeUnheardForFallback(plan));
          },
        });
        wsRef.current = ws;
      } catch (err) {
        if (cancelled || planRef.current !== plan) return;
        plan.phase = "unavailable";
        setPhase("unavailable");
        setHint(publicVoiceError(
          err instanceof Error ? err.message : "",
          t("voice.xaiUnavailable"),
        ));
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
  }, [active, choice, session.mode, session.language, session.courseId, session.category, session.topic, runFallback, t]);

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
    const salane = agentRef.current !== "xai" && plan.phase === "live" && !ws;
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
  }, [active, choice, runFallback]);

  return {
    phase,
    live: phase === "live",
    hint,
    speakLatest,
    interrupt,
    agent: choice ?? "sala",
  };
}

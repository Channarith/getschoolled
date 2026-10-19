"use client";

// Sala-only course player voice overlay.
//
// A single self-contained React component that owns the always-listening mic,
// routes transcripts through the local-only courseVoiceIntent parser, and
// surfaces a minimal UI:
//   • a visible "Sala listening" pill that doubles as the mute toggle,
//   • a one-time consent card on first use (never auto-starts the mic),
//   • an optional semi-transparent "Type to Sala" pill gated by the
//     accessibility.typetoask_mode feature flag, for learners who cannot
//     speak.
//
// Design intent:
//   • Transcripts stay in the browser. The parser runs locally and only the
//     matched CourseVoiceIntent (never the raw text) is handed to the caller.
//   • The mic DOES NOT auto-start on mount. The user must consent once per
//     device; the consent is remembered under aoep_course_voice_consent_v1.
//   • Muting is a client-side toggle. Unmuting is intentionally not voice-
//     controllable (that would defeat the mute). Users click the pill.
//   • The caller gets onMiss() every time the recognizer heard words we
//     could not classify. The player uses that to count 3-in-15s misses
//     and reveal the classic chrome as a safety net.

import { useCallback, useEffect, useRef, useState } from "react";

import {
  parseCourseVoiceIntent,
  type CourseVoiceIntent,
} from "../lib/courseVoiceIntent";

type SpeechRec = {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  onresult:
    | ((event: {
        resultIndex: number;
        results: {
          length: number;
          [i: number]: {
            isFinal?: boolean;
            length: number;
            [j: number]: { transcript?: string };
          };
        };
      }) => void)
    | null;
  onerror: ((event: { error?: string }) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
};

const CONSENT_KEY = "aoep_course_voice_consent_v1";

export type CourseVoiceOverlayProps = {
  /** Called with every confidently matched intent. */
  onIntent: (intent: CourseVoiceIntent) => void;
  /**
   * Called with the raw transcript whenever the recognizer heard something
   * speech-like but the parser could not classify it. The player uses this
   * to count misses and surface the classic chrome as a safety net.
   */
  onMiss?: (transcript: string) => void;
  /** BCP-47 locale for speech recognition. Defaults to "en-US". */
  locale?: string;
  /**
   * When true, show a semi-transparent "Type to Sala" pill that opens a
   * one-line input. Enabled via the accessibility.typetoask_mode flag so
   * learners who cannot speak can still issue the same intents.
   */
  showTypeToAsk?: boolean;
  /** When false, hide the overlay entirely (e.g. during a modal). */
  enabled?: boolean;
};

export default function CourseVoiceOverlay({
  onIntent,
  onMiss,
  locale = "en-US",
  showTypeToAsk = false,
  enabled = true,
}: CourseVoiceOverlayProps) {
  const [consented, setConsented] = useState<boolean>(() => {
    if (typeof window === "undefined") return false;
    try { return window.localStorage.getItem(CONSENT_KEY) === "1"; } catch { return false; }
  });
  const [muted, setMuted] = useState(false);
  const [listening, setListening] = useState(false);
  const [supported, setSupported] = useState<boolean | null>(null);
  const [typedOpen, setTypedOpen] = useState(false);
  const [typedValue, setTypedValue] = useState("");
  const recognitionRef = useRef<SpeechRec | null>(null);
  const onIntentRef = useRef(onIntent);
  const onMissRef = useRef(onMiss);
  const localeRef = useRef(locale);
  useEffect(() => { onIntentRef.current = onIntent; }, [onIntent]);
  useEffect(() => { onMissRef.current = onMiss; }, [onMiss]);
  useEffect(() => { localeRef.current = locale; }, [locale]);

  // Capability probe — true only when the browser exposes the Web Speech API.
  useEffect(() => {
    if (typeof window === "undefined") { setSupported(false); return; }
    const w = window as unknown as {
      SpeechRecognition?: new () => SpeechRec;
      webkitSpeechRecognition?: new () => SpeechRec;
    };
    setSupported(Boolean(w.SpeechRecognition || w.webkitSpeechRecognition));
  }, []);

  const dispatch = useCallback(
    (text: string) => {
      const trimmed = (text || "").trim();
      if (!trimmed) return;
      const intent = parseCourseVoiceIntent(trimmed);
      if (intent) {
        if (intent.kind === "mute_mic") {
          setMuted(true);
          return;
        }
        onIntentRef.current(intent);
        return;
      }
      onMissRef.current?.(trimmed);
    },
    [],
  );

  // The actual Web Speech recognizer loop. Starts only when the three gates
  // are all green: enabled by the player, user has consented, mic is not
  // muted, and the browser supports the API.
  useEffect(() => {
    if (!enabled || !consented || muted || !supported) return;
    if (typeof window === "undefined") return;
    const w = window as unknown as {
      SpeechRecognition?: new () => SpeechRec;
      webkitSpeechRecognition?: new () => SpeechRec;
    };
    const Ctor = w.SpeechRecognition || w.webkitSpeechRecognition;
    if (!Ctor) return;
    let stopped = false;
    const rec = new Ctor();
    rec.lang = localeRef.current || "en-US";
    rec.interimResults = false;
    rec.continuous = true;
    rec.onresult = (event) => {
      const start = event.resultIndex ?? 0;
      for (let i = start; i < event.results.length; i += 1) {
        const first = event.results[i]?.[0];
        if (!first) continue;
        const transcript = (first.transcript || "").trim();
        if (!transcript) continue;
        dispatch(transcript);
      }
    };
    rec.onerror = (event) => {
      // "no-speech" / "aborted" are normal; keep the loop alive.
      if (!event?.error || event.error === "no-speech" || event.error === "aborted") return;
      // "not-allowed" means the user revoked mic permission — give up until
      // they explicitly re-consent.
      if (event.error === "not-allowed") {
        stopped = true;
        setConsented(false);
        try { window.localStorage.removeItem(CONSENT_KEY); } catch { /* non-fatal */ }
      }
    };
    rec.onend = () => {
      if (stopped) { setListening(false); return; }
      // Chrome occasionally ends the stream on long silence; restart.
      try { rec.start(); } catch { setListening(false); }
    };
    recognitionRef.current = rec;
    try {
      rec.start();
      setListening(true);
    } catch {
      setListening(false);
    }
    return () => {
      stopped = true;
      setListening(false);
      rec.onresult = null;
      rec.onerror = null;
      rec.onend = null;
      try { rec.stop(); } catch { /* non-fatal */ }
      recognitionRef.current = null;
    };
  }, [enabled, consented, muted, supported, dispatch]);

  const handleConsent = () => {
    try { window.localStorage.setItem(CONSENT_KEY, "1"); } catch { /* non-fatal */ }
    setMuted(false);
    setConsented(true);
  };

  const toggleMute = () => setMuted((m) => !m);

  const submitTyped = () => {
    const text = typedValue.trim();
    setTypedValue("");
    setTypedOpen(false);
    if (!text) return;
    // Typed commands go through the same parser so the mobile and web paths
    // honor the same vocabulary. A free-form question still becomes an "ask".
    dispatch(text);
  };

  if (!enabled) return null;

  // Shared container: fixed overlay anchored to the viewport, never captures
  // pointer events outside its small controls (so the course stage behind it
  // still receives taps and double-clicks).
  return (
    <div
      aria-live="polite"
      style={{
        position: "fixed",
        inset: 0,
        pointerEvents: "none",
        zIndex: 50,
      }}
    >
      {!consented ? (
        <ConsentCard supported={supported} onAccept={handleConsent} />
      ) : (
        <ListeningPill
          listening={listening}
          muted={muted}
          supported={supported}
          onToggleMute={toggleMute}
        />
      )}

      {showTypeToAsk ? (
        <>
          <button
            type="button"
            onClick={() => setTypedOpen((o) => !o)}
            aria-label="Type a command for Sala"
            style={{
              position: "absolute",
              right: 16,
              bottom: 16,
              padding: "10px 14px",
              borderRadius: 999,
              border: "1px solid rgba(255,255,255,0.4)",
              background: "rgba(15,23,42,0.45)",
              color: "rgba(255,255,255,0.9)",
              fontSize: 13,
              cursor: "pointer",
              backdropFilter: "blur(6px)",
              pointerEvents: "auto",
            }}
          >
            ⌨ Type to Sala
          </button>
          {typedOpen ? (
            <form
              onSubmit={(e) => { e.preventDefault(); submitTyped(); }}
              style={{
                position: "absolute",
                right: 16,
                bottom: 60,
                display: "flex",
                gap: 6,
                padding: 8,
                borderRadius: 10,
                background: "rgba(15,23,42,0.9)",
                boxShadow: "0 8px 24px rgba(0,0,0,0.35)",
                pointerEvents: "auto",
              }}
            >
              <input
                autoFocus
                value={typedValue}
                onChange={(e) => setTypedValue(e.target.value)}
                placeholder="pause, next, captions on, …"
                aria-label="Type a command"
                style={{
                  minWidth: 220,
                  padding: "8px 10px",
                  borderRadius: 6,
                  border: "1px solid rgba(255,255,255,0.3)",
                  background: "rgba(0,0,0,0.4)",
                  color: "#fff",
                  fontSize: 14,
                }}
              />
              <button
                type="submit"
                style={{
                  padding: "8px 12px",
                  borderRadius: 6,
                  border: 0,
                  background: "#4f46e5",
                  color: "#fff",
                  fontWeight: 600,
                  cursor: "pointer",
                }}
              >
                Send
              </button>
            </form>
          ) : null}
        </>
      ) : null}
    </div>
  );
}

function ConsentCard({
  supported,
  onAccept,
}: {
  supported: boolean | null;
  onAccept: () => void;
}) {
  const text = supported === false
    ? "Voice commands aren't supported in this browser. Open the classic controls to continue."
    : "Sala can run this course by voice. Tap once to let her listen; she'll only act on commands like \"pause\", \"next\", \"captions on\".";
  return (
    <div
      style={{
        position: "absolute",
        left: "50%",
        bottom: 24,
        transform: "translateX(-50%)",
        maxWidth: 420,
        padding: "12px 16px",
        borderRadius: 14,
        background: "rgba(15,23,42,0.88)",
        color: "#fff",
        fontSize: 14,
        lineHeight: 1.35,
        boxShadow: "0 10px 30px rgba(0,0,0,0.35)",
        display: "flex",
        flexDirection: "column",
        gap: 8,
        pointerEvents: "auto",
      }}
    >
      <div>{text}</div>
      {supported !== false ? (
        <button
          type="button"
          onClick={onAccept}
          style={{
            alignSelf: "flex-start",
            padding: "8px 14px",
            borderRadius: 999,
            border: 0,
            background: "#4f46e5",
            color: "#fff",
            fontWeight: 600,
            cursor: "pointer",
          }}
        >
          Let Sala listen
        </button>
      ) : null}
    </div>
  );
}

function ListeningPill({
  listening,
  muted,
  supported,
  onToggleMute,
}: {
  listening: boolean;
  muted: boolean;
  supported: boolean | null;
  onToggleMute: () => void;
}) {
  const label = !supported
    ? "Voice unavailable"
    : muted
      ? "Mic muted — tap to resume"
      : listening
        ? "Sala listening"
        : "Starting Sala…";
  const dot = muted ? "#f87171" : listening ? "#22c55e" : "#eab308";
  return (
    <button
      type="button"
      onClick={onToggleMute}
      aria-label={muted ? "Unmute Sala's microphone" : "Mute Sala's microphone"}
      aria-pressed={muted}
      style={{
        position: "absolute",
        left: "50%",
        bottom: 20,
        transform: "translateX(-50%)",
        display: "inline-flex",
        alignItems: "center",
        gap: 8,
        padding: "8px 14px",
        borderRadius: 999,
        border: "1px solid rgba(255,255,255,0.25)",
        background: "rgba(15,23,42,0.6)",
        color: "#fff",
        fontSize: 13,
        cursor: "pointer",
        backdropFilter: "blur(6px)",
        pointerEvents: "auto",
      }}
    >
      <span
        aria-hidden="true"
        style={{
          display: "inline-block",
          width: 10,
          height: 10,
          borderRadius: "50%",
          background: dot,
          boxShadow: muted ? "none" : `0 0 0 4px ${dot}22`,
        }}
      />
      <span>{label}</span>
    </button>
  );
}

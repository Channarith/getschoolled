// Mobile Sala-only voice-first overlay.
//
// Lives above LessonScreen when voice-first mode is active (the new default).
// Owns:
//   * the always-listening recognizer (via startAmbientListening/stopAmbientListening),
//   * a visible "Sala listening" pill that doubles as the mute toggle,
//   * one consent toast on first use,
//   * an optional semi-transparent "Type to Sala" FAB (gated by
//     accessibility.typetoask_mode so learners who cannot speak can issue the
//     same intents),
//   * the long-press / 3-missed-in-15s safety net that reveals classic chrome.
//
// The actual intent parsing is delegated to parseCourseVoiceIntent so the web
// Course Studio overlay, the web parent app, and this screen all share one
// grammar. Transcripts never leave the device; only the matched intent is
// handed to onIntent.

import { useCallback, useEffect, useRef, useState } from "react";
import {
  AccessibilityInfo, Keyboard, StyleSheet, Text, TextInput,
  TouchableOpacity, View,
} from "react-native";

import {
  parseCourseVoiceIntent,
  type CourseVoiceIntent,
} from "../courseVoiceIntent";
import {
  startAmbientListening, stopAmbientListening,
} from "../voiceAssistant";

const MISS_WINDOW_MS = 15_000;
const MISS_LIMIT = 3;

export type VoiceFirstOverlayProps = {
  /** When false the overlay renders nothing and tears down the mic. */
  active: boolean;
  /** BCP-47 locale used by the recognizer. */
  locale: string;
  /** When true, show the semi-transparent "Type to Sala" FAB. */
  typeToAsk?: boolean;
  /** Fires once per matched intent. */
  onIntent: (intent: CourseVoiceIntent) => void;
  /** Fires when the overlay wants to reveal classic chrome. */
  onRevealChrome: (reason: "misses" | "voice" | "long-press" | "unsupported") => void;
};

type Phase = "idle" | "consent" | "listening" | "muted" | "unsupported";

/**
 * All intent handling is kept outside this component. The overlay only parses
 * and forwards; the hosting screen (LessonScreen) owns the actual lesson
 * actions. We expose a tiny imperative API via onIntent so tests can drive it
 * without needing a real recognizer.
 */
export default function VoiceFirstOverlay({
  active, locale, typeToAsk = false, onIntent, onRevealChrome,
}: VoiceFirstOverlayProps) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [typedOpen, setTypedOpen] = useState(false);
  const [typedValue, setTypedValue] = useState("");
  const [screenReader, setScreenReader] = useState(false);
  const missesRef = useRef<number[]>([]);

  // Phase is purely UI; the parent decides whether the overlay is "active".
  useEffect(() => {
    if (!active) {
      stopAmbientListening();
      setPhase("idle");
      return;
    }
    if (phase === "idle") setPhase("consent");
  }, [active, phase]);

  useEffect(() => {
    let mounted = true;
    AccessibilityInfo.isScreenReaderEnabled()
      .then((on) => { if (mounted) setScreenReader(Boolean(on)); })
      .catch(() => { /* non-fatal */ });
    const sub = AccessibilityInfo.addEventListener("screenReaderChanged", (on) => {
      setScreenReader(Boolean(on));
    });
    return () => { mounted = false; try { sub.remove?.(); } catch { /* older RN */ } };
  }, []);

  const recordMiss = useCallback(() => {
    const now = Date.now();
    missesRef.current = missesRef.current.filter((t) => now - t <= MISS_WINDOW_MS);
    missesRef.current.push(now);
    if (missesRef.current.length >= MISS_LIMIT) {
      missesRef.current = [];
      onRevealChrome("misses");
    }
  }, [onRevealChrome]);

  const dispatch = useCallback((intent: CourseVoiceIntent) => {
    if (intent.kind === "mute_mic") {
      stopAmbientListening();
      setPhase("muted");
      return;
    }
    if (intent.kind === "show_controls") {
      onRevealChrome("voice");
      return;
    }
    onIntent(intent);
  }, [onIntent, onRevealChrome]);

  const startListening = useCallback(async () => {
    const ok = await startAmbientListening({
      locale,
      onResult: (text) => {
        const intent = parseCourseVoiceIntent(text);
        if (!intent) { recordMiss(); return; }
        dispatch(intent);
      },
      onError: (code) => {
        if (code === "unavailable" || code === "permission_denied") {
          setPhase("unsupported");
          onRevealChrome("unsupported");
        }
      },
    });
    setPhase(ok ? "listening" : "unsupported");
    if (!ok) onRevealChrome("unsupported");
  }, [locale, dispatch, recordMiss, onRevealChrome]);

  const unmute = useCallback(() => { void startListening(); }, [startListening]);

  const submitTyped = useCallback(() => {
    const text = String(typedValue || "").trim();
    setTypedValue("");
    setTypedOpen(false);
    Keyboard.dismiss();
    if (!text) return;
    const intent = parseCourseVoiceIntent(text);
    if (!intent) { recordMiss(); return; }
    dispatch(intent);
  }, [typedValue, dispatch, recordMiss]);

  useEffect(() => {
    return () => { stopAmbientListening(); };
  }, []);

  if (!active) return null;

  // Consent card: shown once before we touch the mic. A screen reader user gets
  // a persistent "type to Sala" affordance even if typeToAsk is off.
  if (phase === "consent") {
    return (
      <View style={styles.wrap} pointerEvents="box-none" accessible={false}>
        <View style={styles.consentCard}>
          <Text style={styles.consentText}>
            Sala can run this course by voice. Tap once to let her listen.
            She will only act on commands like "pause", "next", or "captions on".
          </Text>
          <TouchableOpacity
            accessibilityRole="button"
            accessibilityLabel="Let Sala listen"
            style={styles.primaryBtn}
            onPress={() => { void startListening(); }}
          >
            <Text style={styles.primaryBtnText}>Let Sala listen</Text>
          </TouchableOpacity>
          <TouchableOpacity
            accessibilityRole="button"
            accessibilityLabel="Show classic controls"
            onPress={() => onRevealChrome("voice")}
          >
            <Text style={styles.linkText}>I'd rather use buttons</Text>
          </TouchableOpacity>
        </View>
      </View>
    );
  }

  const showTyped = typeToAsk || screenReader || phase === "muted" || phase === "unsupported";
  const pillLabel = phase === "muted"
    ? "Mic muted — tap to resume"
    : phase === "unsupported"
      ? "Voice unavailable"
      : "Sala listening";

  return (
    <View style={styles.wrap} pointerEvents="box-none" accessible={false}>
      {phase !== "unsupported" ? (
        <TouchableOpacity
          accessibilityRole="button"
          accessibilityLabel={phase === "muted" ? "Unmute Sala" : "Mute Sala"}
          style={styles.pill}
          onPress={() => (phase === "muted" ? unmute() : (stopAmbientListening(), setPhase("muted")))}
        >
          <View style={[styles.dot, {
            backgroundColor: phase === "muted" ? "#f87171" : "#22c55e",
          }]} />
          <Text style={styles.pillText}>{pillLabel}</Text>
        </TouchableOpacity>
      ) : null}

      {showTyped ? (
        <View style={styles.typedWrap} accessible={false}>
          {typedOpen ? (
            <View style={styles.typedForm}>
              <TextInput
                value={typedValue}
                onChangeText={setTypedValue}
                placeholder="pause, next, captions on, …"
                placeholderTextColor="rgba(255,255,255,0.5)"
                style={styles.typedInput}
                autoFocus
                returnKeyType="send"
                onSubmitEditing={submitTyped}
                accessibilityLabel="Type a command for Sala"
              />
              <TouchableOpacity
                accessibilityRole="button"
                accessibilityLabel="Send command"
                style={styles.sendBtn}
                onPress={submitTyped}
              >
                <Text style={styles.sendBtnText}>Send</Text>
              </TouchableOpacity>
            </View>
          ) : (
            <TouchableOpacity
              accessibilityRole="button"
              accessibilityLabel="Type a command for Sala"
              style={styles.typedPill}
              onPress={() => setTypedOpen(true)}
            >
              <Text style={styles.typedPillText}>⌨ Type to Sala</Text>
            </TouchableOpacity>
          )}
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    position: "absolute",
    left: 0, right: 0, top: 0, bottom: 0,
    pointerEvents: "box-none",
    zIndex: 60,
  },
  pill: {
    position: "absolute",
    bottom: 24,
    alignSelf: "center",
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 999,
    backgroundColor: "rgba(15,23,42,0.6)",
    borderColor: "rgba(255,255,255,0.25)",
    borderWidth: 1,
  },
  dot: { width: 10, height: 10, borderRadius: 5, marginRight: 8 },
  pillText: { color: "#fff", fontSize: 13 },
  consentCard: {
    position: "absolute",
    bottom: 32, left: 16, right: 16,
    backgroundColor: "rgba(15,23,42,0.9)",
    padding: 16, borderRadius: 16, gap: 10,
  },
  consentText: { color: "#fff", fontSize: 14, lineHeight: 20 },
  primaryBtn: {
    alignSelf: "flex-start",
    paddingVertical: 10, paddingHorizontal: 16,
    backgroundColor: "#4f46e5", borderRadius: 999,
  },
  primaryBtnText: { color: "#fff", fontWeight: "700" },
  linkText: { color: "rgba(226,232,240,0.85)", textDecorationLine: "underline" },
  typedWrap: { position: "absolute", right: 16, bottom: 20 },
  typedPill: {
    paddingVertical: 10, paddingHorizontal: 14,
    borderRadius: 999,
    backgroundColor: "rgba(15,23,42,0.45)",
    borderColor: "rgba(255,255,255,0.4)",
    borderWidth: 1,
  },
  typedPillText: { color: "rgba(255,255,255,0.9)", fontSize: 13 },
  typedForm: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    backgroundColor: "rgba(15,23,42,0.9)",
    padding: 8, borderRadius: 12,
  },
  typedInput: {
    minWidth: 220,
    paddingHorizontal: 10, paddingVertical: 6,
    borderRadius: 8,
    backgroundColor: "rgba(0,0,0,0.4)",
    color: "#fff", fontSize: 14,
    borderColor: "rgba(255,255,255,0.3)",
    borderWidth: 1,
  },
  sendBtn: {
    paddingVertical: 8, paddingHorizontal: 12,
    borderRadius: 8, backgroundColor: "#4f46e5",
  },
  sendBtnText: { color: "#fff", fontWeight: "700" },
});

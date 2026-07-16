import { Audio, type AVPlaybackStatus } from "expo-av";
import { LinearGradient } from "expo-linear-gradient";
import { useEffect, useRef, useState } from "react";
import {
  Animated, Easing, Image, Pressable, StyleSheet, Text, View,
} from "react-native";

import { useT } from "../i18n";
import { theme } from "../theme";

/** Jingle clip: 1:32 → ~1:39 in salareen_jingle.mp3 */
const INTRO_START_MS = 92_000;
const INTRO_END_MS = 99_000;

/**
 * Beat engine tempo. The jingle is an upbeat clip; 120 BPM (500ms/beat) reads as
 * a lively danceable tempo and drives every rhythmic hit below. Bumping/dropping
 * this is the single knob for "faster/slower dance".
 */
const BPM = 120;
const BEAT_MS = Math.round(60_000 / BPM);

const PARTY_COLORS = ["#e50914", "#6ea8fe", "#fbbf24", "#34d399", "#a78bfa", "#f472b6"];
const EQ_BARS = 7;
const BAR_H = 46;

// Random visual variants (like the web intro's 6 random animations): the beat
// engine, mascot and jingle stay the same; each variant reskins the backdrop,
// disco blobs, equalizer, floating notes and beat ring so every launch feels
// fresh. One is chosen at random per play.
type IntroVariant = {
  id: string;
  name: string;
  bg: [string, string, string];
  blobs: string[];
  eq: string[];
  notes: string[];
  ring: string;
};

const INTRO_VARIANTS: IntroVariant[] = [
  { id: "disco", name: "Disco", bg: ["#120a2e", "#0b0b16", "#05050b"],
    blobs: ["#e50914", "#6ea8fe", "#a78bfa", "#34d399"], eq: PARTY_COLORS,
    notes: ["🎵", "🎶", "⭐", "✨", "🔥", "🎈", "💫", "🎉"], ring: "#a78bfa" },
  { id: "neon", name: "Neon", bg: ["#0a0f2e", "#0a1030", "#04040a"],
    blobs: ["#22d3ee", "#f472b6", "#a78bfa", "#34d399"],
    eq: ["#22d3ee", "#f472b6", "#a78bfa", "#facc15", "#34d399"],
    notes: ["💠", "✨", "🎧", "🎶", "⚡", "🌟", "🔷", "💜"], ring: "#22d3ee" },
  { id: "aurora", name: "Aurora", bg: ["#04121a", "#071a2b", "#03060a"],
    blobs: ["#34d399", "#22d3ee", "#a78bfa", "#5eead4"],
    eq: ["#34d399", "#22d3ee", "#5eead4", "#a78bfa", "#67e8f9"],
    notes: ["🌌", "✨", "💫", "🎶", "🌠", "❄️", "🟢", "🔵"], ring: "#5eead4" },
  { id: "sunset", name: "Sunset", bg: ["#2a0a1e", "#3b0a1a", "#0a0406"],
    blobs: ["#f97316", "#f43f5e", "#fbbf24", "#fb7185"],
    eq: ["#f97316", "#f43f5e", "#fbbf24", "#fb7185", "#f59e0b"],
    notes: ["🔥", "🌅", "✨", "🎶", "🧡", "⭐", "🎉", "💥"], ring: "#fb7185" },
  { id: "confetti", name: "Confetti Pop", bg: ["#12122e", "#0b0b16", "#05050b"],
    blobs: ["#f472b6", "#facc15", "#34d399", "#6ea8fe"], eq: PARTY_COLORS,
    notes: ["🎉", "🎊", "🎈", "✨", "⭐", "💥", "🥳", "🎇"], ring: "#facc15" },
  { id: "galaxy", name: "Galaxy", bg: ["#0b0620", "#0a0a2a", "#03030a"],
    blobs: ["#818cf8", "#c084fc", "#38bdf8", "#e879f9"],
    eq: ["#818cf8", "#c084fc", "#38bdf8", "#e879f9", "#a5b4fc"],
    notes: ["🌟", "✨", "💫", "🎶", "🪐", "⭐", "🌠", "💜"], ring: "#c084fc" },
];

export function pickIntroVariant(): IntroVariant {
  return INTRO_VARIANTS[Math.floor(Math.random() * INTRO_VARIANTS.length)];
}

export type IntroSplashMode = "intro" | "full";

type Props = {
  mode: IntroSplashMode;
  onFinish: () => void;
};

type NoteState = { id: number; glyph: string; startX: number; drift: number; dir: number };

/** A single music-note / sparkle that floats up from the dancer and fades out. */
function DanceNote({ note, onDone }: { note: NoteState; onDone: (id: number) => void }) {
  const progress = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    const anim = Animated.timing(progress, {
      toValue: 1,
      duration: 1700,
      easing: Easing.out(Easing.quad),
      useNativeDriver: true,
    });
    anim.start(({ finished }) => {
      if (finished) onDone(note.id);
    });
    return () => anim.stop();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const translateY = progress.interpolate({ inputRange: [0, 1], outputRange: [0, -240] });
  const translateX = progress.interpolate({
    inputRange: [0, 1],
    outputRange: [note.startX, note.startX + note.drift],
  });
  const opacity = progress.interpolate({
    inputRange: [0, 0.15, 0.75, 1],
    outputRange: [0, 1, 1, 0],
  });
  const scale = progress.interpolate({ inputRange: [0, 0.25, 1], outputRange: [0.4, 1.15, 1.3] });
  const rotate = progress.interpolate({
    inputRange: [0, 1],
    outputRange: ["0deg", `${note.dir * 45}deg`],
  });

  return (
    <Animated.Text
      style={[
        styles.note,
        { opacity, transform: [{ translateX }, { translateY }, { scale }, { rotate }] },
      ]}
    >
      {note.glyph}
    </Animated.Text>
  );
}

export default function IntroSplashScreen({ mode, onFinish }: Props) {
  const { t } = useT();
  const soundRef = useRef<Audio.Sound | null>(null);
  const finishedRef = useRef(false);
  const [visible, setVisible] = useState(true);
  const [notes, setNotes] = useState<NoteState[]>([]);
  // Pick one random visual variant per play (stable across re-renders).
  const variant = useRef(pickIntroVariant()).current;

  // Entrance / exit.
  const enterScale = useRef(new Animated.Value(0.45)).current;
  const enterOpacity = useRef(new Animated.Value(0)).current;
  const titleY = useRef(new Animated.Value(24)).current;
  const titleOpacity = useRef(new Animated.Value(0)).current;
  const scrimOpacity = useRef(new Animated.Value(1)).current;

  // Beat-driven dance values.
  const bounce = useRef(new Animated.Value(0)).current; // 0 grounded → 1 top of jump
  const pop = useRef(new Animated.Value(0)).current;     // extra scale punch on the hit
  const step = useRef(new Animated.Value(0)).current;    // -1 left … +1 right (dance step)
  const idle = useRef(new Animated.Value(0)).current;    // continuous breathing bob
  const ringPulse = useRef(new Animated.Value(0)).current;
  const blobSpin = useRef(new Animated.Value(0)).current;
  const eqBars = useRef(Array.from({ length: EQ_BARS }, () => new Animated.Value(0.3))).current;

  const beatCount = useRef(0);
  const noteId = useRef(0);

  const spawnNote = () => {
    noteId.current += 1;
    const id = noteId.current;
    const note: NoteState = {
      id,
      glyph: variant.notes[Math.floor(Math.random() * variant.notes.length)],
      startX: (Math.random() - 0.5) * 150,
      drift: (Math.random() - 0.5) * 90,
      dir: Math.random() > 0.5 ? 1 : -1,
    };
    setNotes((prev) => [...prev.slice(-9), note]);
  };

  const removeNote = (id: number) => {
    setNotes((prev) => prev.filter((n) => n.id !== id));
  };

  const doBeat = () => {
    beatCount.current += 1;
    const dir = beatCount.current % 2 === 0 ? 1 : -1;

    Animated.spring(step, {
      toValue: dir,
      friction: 5,
      tension: 130,
      useNativeDriver: true,
    }).start();

    Animated.sequence([
      Animated.timing(bounce, {
        toValue: 1,
        duration: Math.round(BEAT_MS * 0.28),
        easing: Easing.out(Easing.quad),
        useNativeDriver: true,
      }),
      Animated.timing(bounce, {
        toValue: 0,
        duration: Math.round(BEAT_MS * 0.72),
        easing: Easing.bounce,
        useNativeDriver: true,
      }),
    ]).start();

    Animated.sequence([
      Animated.timing(pop, {
        toValue: 1,
        duration: Math.round(BEAT_MS * 0.2),
        easing: Easing.out(Easing.quad),
        useNativeDriver: true,
      }),
      Animated.timing(pop, {
        toValue: 0,
        duration: Math.round(BEAT_MS * 0.8),
        easing: Easing.elastic(1.4),
        useNativeDriver: true,
      }),
    ]).start();

    Animated.sequence([
      Animated.timing(ringPulse, {
        toValue: 1,
        duration: Math.round(BEAT_MS * 0.22),
        useNativeDriver: true,
      }),
      Animated.timing(ringPulse, {
        toValue: 0,
        duration: Math.round(BEAT_MS * 0.78),
        easing: Easing.out(Easing.quad),
        useNativeDriver: true,
      }),
    ]).start();

    // Kick the equalizer bars to fresh random heights on the beat.
    eqBars.forEach((bar) => {
      Animated.timing(bar, {
        toValue: 0.35 + Math.random() * 0.65,
        duration: Math.round(BEAT_MS * 0.5),
        easing: Easing.out(Easing.quad),
        useNativeDriver: true,
      }).start();
    });

    if (beatCount.current % 2 === 0) spawnNote();
  };

  const finish = () => {
    if (finishedRef.current) return;
    finishedRef.current = true;
    Animated.timing(scrimOpacity, {
      toValue: 0,
      duration: 450,
      useNativeDriver: true,
    }).start(() => {
      setVisible(false);
      onFinish();
    });
  };

  useEffect(() => {
    Animated.parallel([
      Animated.spring(enterScale, { toValue: 1, friction: 6, tension: 45, useNativeDriver: true }),
      Animated.timing(enterOpacity, { toValue: 1, duration: 600, useNativeDriver: true }),
      Animated.timing(titleOpacity, { toValue: 1, duration: 800, delay: 250, useNativeDriver: true }),
      Animated.spring(titleY, { toValue: 0, friction: 7, delay: 250, useNativeDriver: true }),
    ]).start();

    // Continuous breathing bob so the dancer feels alive between beats.
    const idleLoop = Animated.loop(
      Animated.sequence([
        Animated.timing(idle, { toValue: 1, duration: 900, easing: Easing.inOut(Easing.sin), useNativeDriver: true }),
        Animated.timing(idle, { toValue: 0, duration: 900, easing: Easing.inOut(Easing.sin), useNativeDriver: true }),
      ]),
    );
    idleLoop.start();

    // Slow disco spin behind the dancer.
    const spinLoop = Animated.loop(
      Animated.timing(blobSpin, { toValue: 1, duration: 12_000, easing: Easing.linear, useNativeDriver: true }),
    );
    spinLoop.start();

    let beatInterval: ReturnType<typeof setInterval> | undefined;
    let introTimer: ReturnType<typeof setTimeout> | undefined;

    const startBeatEngine = () => {
      if (beatInterval) return;
      doBeat();
      beatInterval = setInterval(doBeat, BEAT_MS);
    };

    void (async () => {
      try {
        await Audio.setAudioModeAsync({ playsInSilentModeIOS: true });
        const { sound } = await Audio.Sound.createAsync(
          require("../../assets/audio/salareen_jingle.mp3"),
          { shouldPlay: false, progressUpdateIntervalMillis: 250 },
        );
        soundRef.current = sound;

        const onStatus = (status: AVPlaybackStatus) => {
          if (!status.isLoaded) return;
          if (mode === "intro" && status.positionMillis >= INTRO_END_MS) {
            void sound.stopAsync().catch(() => {});
            finish();
          }
          if (mode === "full" && status.didJustFinish) {
            finish();
          }
        };
        sound.setOnPlaybackStatusUpdate(onStatus);

        if (mode === "intro") {
          await sound.setPositionAsync(INTRO_START_MS);
          await sound.playAsync();
          introTimer = setTimeout(() => finish(), INTRO_END_MS - INTRO_START_MS + 400);
        } else {
          await sound.setPositionAsync(0);
          await sound.playAsync();
        }
        startBeatEngine();
      } catch {
        // No audio? Still dance — the beat engine is self-contained.
        startBeatEngine();
        introTimer = setTimeout(finish, mode === "intro" ? 7000 : 3000);
      }
    })();

    return () => {
      if (introTimer) clearTimeout(introTimer);
      if (beatInterval) clearInterval(beatInterval);
      idleLoop.stop();
      spinLoop.stop();
      void soundRef.current?.unloadAsync();
      soundRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode]);

  if (!visible) return null;

  // Dance transform composition (squash & stretch + bounce + step + tilt).
  const translateY = Animated.add(
    bounce.interpolate({ inputRange: [0, 1], outputRange: [0, -44] }),
    idle.interpolate({ inputRange: [0, 1], outputRange: [0, -8] }),
  );
  const translateX = step.interpolate({ inputRange: [-1, 1], outputRange: [-22, 22] });
  const rotate = step.interpolate({ inputRange: [-1, 1], outputRange: ["-10deg", "10deg"] });
  const scaleX = bounce.interpolate({ inputRange: [0, 0.5, 1], outputRange: [1, 0.94, 0.88] });
  const scaleY = bounce.interpolate({ inputRange: [0, 0.5, 1], outputRange: [1, 1.06, 1.14] });
  const popScale = pop.interpolate({ inputRange: [0, 1], outputRange: [1, 1.1] });

  const shadowScale = bounce.interpolate({ inputRange: [0, 1], outputRange: [1, 0.55] });
  const shadowOpacity = bounce.interpolate({ inputRange: [0, 1], outputRange: [0.4, 0.12] });

  const ringScale = ringPulse.interpolate({ inputRange: [0, 1], outputRange: [0.9, 1.45] });
  const ringOpacity = ringPulse.interpolate({ inputRange: [0, 1], outputRange: [0.55, 0] });

  const spin = blobSpin.interpolate({ inputRange: [0, 1], outputRange: ["0deg", "360deg"] });
  const spinRev = blobSpin.interpolate({ inputRange: [0, 1], outputRange: ["0deg", "-360deg"] });

  return (
    <Animated.View style={[styles.overlay, { opacity: scrimOpacity }]} pointerEvents="box-none">
      <LinearGradient
        colors={variant.bg}
        style={StyleSheet.absoluteFill}
      />
      <Pressable
        style={styles.fill}
        onPress={finish}
        accessibilityRole="button"
        accessibilityLabel={t("intro.skip")}
      >
        {/* Disco blobs spinning behind the dancer. */}
        <Animated.View style={[styles.blobLayer, { transform: [{ rotate: spin }] }]}>
          <View style={[styles.blob, { backgroundColor: variant.blobs[0], top: -30, left: -40 }]} />
          <View style={[styles.blob, { backgroundColor: variant.blobs[1], bottom: -20, right: -50 }]} />
        </Animated.View>
        <Animated.View style={[styles.blobLayer, { transform: [{ rotate: spinRev }] }]}>
          <View style={[styles.blob, { backgroundColor: variant.blobs[2], top: 10, right: -30, opacity: 0.7 }]} />
          <View style={[styles.blob, { backgroundColor: variant.blobs[3], bottom: 0, left: -30, opacity: 0.6 }]} />
        </Animated.View>

        {/* Beat ring that expands on every hit. */}
        <Animated.View
          style={[styles.ring, { borderColor: variant.ring, opacity: ringOpacity, transform: [{ scale: ringScale }] }]}
        />

        {/* Floating music notes. */}
        <View style={styles.noteLayer} pointerEvents="none">
          {notes.map((n) => (
            <DanceNote key={n.id} note={n} onDone={removeNote} />
          ))}
        </View>

        {/* The dancing cartoon mascot. */}
        <Animated.View
          style={[
            styles.dancer,
            { opacity: enterOpacity, transform: [{ scale: enterScale }] },
          ]}
        >
          <Animated.View
            style={{
              transform: [
                { translateX },
                { translateY },
                { rotate },
                { scaleX },
                { scaleY },
                { scale: popScale },
              ],
            }}
          >
            <Image
              source={require("../../assets/bayon_buddy_s_bodhi_512.png")}
              style={styles.mascot}
              resizeMode="contain"
            />
          </Animated.View>
          <Animated.View
            style={[styles.shadow, { opacity: shadowOpacity, transform: [{ scaleX: shadowScale }] }]}
          />
        </Animated.View>

        {/* Equalizer reacting to the beat. */}
        <View style={styles.eqRow} pointerEvents="none">
          {eqBars.map((bar, i) => {
            const barScale = bar.interpolate({ inputRange: [0, 1], outputRange: [0.25, 1] });
            const barShift = bar.interpolate({
              inputRange: [0, 1],
              outputRange: [BAR_H * 0.37, 0],
            });
            return (
              <Animated.View
                key={i}
                  style={[
                  styles.eqBar,
                  {
                    backgroundColor: variant.eq[i % variant.eq.length],
                    transform: [{ translateY: barShift }, { scaleY: barScale }],
                  },
                ]}
              />
            );
          })}
        </View>

        <Animated.View style={{ opacity: titleOpacity, transform: [{ translateY: titleY }] }}>
          <Text style={styles.brand}>Salareen</Text>
          <Text style={styles.khmer}>សាលារៀន</Text>
          <Text style={styles.tagline}>
            {mode === "full" ? t("intro.fullTagline") : t("intro.tagline")}
          </Text>
        </Animated.View>
        <Text style={styles.skip}>{t("intro.skip")}</Text>
      </Pressable>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  overlay: {
    ...StyleSheet.absoluteFillObject,
    zIndex: 9999,
    elevation: 9999,
    backgroundColor: theme.colors.bg,
  },
  fill: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 24,
  },
  blobLayer: {
    position: "absolute",
    width: 300,
    height: 300,
    alignItems: "center",
    justifyContent: "center",
  },
  blob: {
    position: "absolute",
    width: 190,
    height: 190,
    borderRadius: 95,
    opacity: 0.55,
  },
  ring: {
    position: "absolute",
    width: 240,
    height: 240,
    borderRadius: 120,
    borderWidth: 3,
    borderColor: theme.colors.accent,
  },
  noteLayer: {
    position: "absolute",
    width: 260,
    height: 320,
    alignItems: "center",
    justifyContent: "flex-end",
  },
  note: {
    position: "absolute",
    bottom: 40,
    fontSize: 26,
  },
  dancer: {
    alignItems: "center",
    justifyContent: "flex-end",
    marginBottom: 14,
  },
  mascot: { width: 168, height: 224 },
  shadow: {
    width: 120,
    height: 20,
    borderRadius: 60,
    backgroundColor: "#000",
    marginTop: 2,
  },
  eqRow: {
    flexDirection: "row",
    alignItems: "flex-end",
    height: BAR_H,
    gap: 7,
    marginBottom: 22,
  },
  eqBar: {
    width: 8,
    height: BAR_H,
    borderRadius: 4,
  },
  brand: {
    color: theme.colors.text,
    fontSize: 34,
    fontWeight: "800",
    textAlign: "center",
    letterSpacing: 1,
  },
  khmer: {
    color: theme.colors.accent,
    fontSize: 28,
    fontWeight: "700",
    textAlign: "center",
    marginTop: 4,
  },
  tagline: {
    color: theme.colors.muted,
    fontSize: 14,
    textAlign: "center",
    marginTop: 10,
    lineHeight: 20,
  },
  skip: {
    position: "absolute",
    bottom: 48,
    color: theme.colors.muted,
    fontSize: 13,
    fontWeight: "600",
  },
});

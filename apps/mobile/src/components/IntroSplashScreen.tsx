import { Audio, type AVPlaybackStatus } from "expo-av";
import { useEffect, useRef, useState } from "react";
import {
  Animated, Easing, Image, Pressable, StyleSheet, Text, View,
} from "react-native";

import { useT } from "../i18n";
import { theme } from "../theme";

/** Jingle clip: 1:32 → ~1:39 in salareen_jingle.mp3 */
const INTRO_START_MS = 92_000;
const INTRO_END_MS = 99_000;

export type IntroSplashMode = "intro" | "full";

type Props = {
  mode: IntroSplashMode;
  onFinish: () => void;
};

export default function IntroSplashScreen({ mode, onFinish }: Props) {
  const { t } = useT();
  const soundRef = useRef<Audio.Sound | null>(null);
  const finishedRef = useRef(false);
  const [visible, setVisible] = useState(true);

  const logoScale = useRef(new Animated.Value(0.55)).current;
  const logoOpacity = useRef(new Animated.Value(0)).current;
  const ringScale = useRef(new Animated.Value(0.8)).current;
  const ringOpacity = useRef(new Animated.Value(0)).current;
  const glow = useRef(new Animated.Value(0)).current;
  const titleY = useRef(new Animated.Value(24)).current;
  const titleOpacity = useRef(new Animated.Value(0)).current;
  const scrimOpacity = useRef(new Animated.Value(1)).current;

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
      Animated.spring(logoScale, { toValue: 1, friction: 6, tension: 40, useNativeDriver: true }),
      Animated.timing(logoOpacity, { toValue: 1, duration: 700, useNativeDriver: true }),
      Animated.timing(ringOpacity, { toValue: 0.55, duration: 900, useNativeDriver: true }),
      Animated.timing(titleOpacity, { toValue: 1, duration: 800, delay: 200, useNativeDriver: true }),
      Animated.spring(titleY, { toValue: 0, friction: 7, useNativeDriver: true }),
    ]).start();

    const ringLoop = Animated.loop(
      Animated.sequence([
        Animated.parallel([
          Animated.timing(ringScale, { toValue: 1.35, duration: 1800, easing: Easing.out(Easing.quad), useNativeDriver: true }),
          Animated.timing(ringOpacity, { toValue: 0.15, duration: 1800, useNativeDriver: true }),
        ]),
        Animated.parallel([
          Animated.timing(ringScale, { toValue: 0.85, duration: 0, useNativeDriver: true }),
          Animated.timing(ringOpacity, { toValue: 0.55, duration: 0, useNativeDriver: true }),
        ]),
      ]),
    );
    ringLoop.start();

    const glowLoop = Animated.loop(
      Animated.sequence([
        Animated.timing(glow, { toValue: 1, duration: 2200, easing: Easing.inOut(Easing.sin), useNativeDriver: true }),
        Animated.timing(glow, { toValue: 0, duration: 2200, easing: Easing.inOut(Easing.sin), useNativeDriver: true }),
      ]),
    );
    glowLoop.start();

    let introTimer: ReturnType<typeof setTimeout> | undefined;

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
      } catch {
        introTimer = setTimeout(finish, mode === "intro" ? 7000 : 3000);
      }
    })();

    return () => {
      if (introTimer) clearTimeout(introTimer);
      ringLoop.stop();
      glowLoop.stop();
      void soundRef.current?.unloadAsync();
      soundRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode]);

  if (!visible) return null;

  const glowColor = glow.interpolate({
    inputRange: [0, 1],
    outputRange: ["rgba(229,9,20,0.15)", "rgba(110,168,254,0.35)"],
  });

  return (
    <Animated.View style={[styles.overlay, { opacity: scrimOpacity }]} pointerEvents="box-none">
      <Pressable style={styles.fill} onPress={finish} accessibilityRole="button"
        accessibilityLabel={t("intro.skip")}>
        <Animated.View style={[styles.glow, { backgroundColor: glowColor }]} />
        <Animated.View
          style={[
            styles.ring,
            { opacity: ringOpacity, transform: [{ scale: ringScale }] },
          ]}
        />
        <Animated.View style={{ opacity: logoOpacity, transform: [{ scale: logoScale }] }}>
          <Image
            source={require("../../assets/salareen_icon_1024.png")}
            style={styles.logo}
            resizeMode="contain"
          />
        </Animated.View>
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
  glow: {
    position: "absolute",
    width: 320,
    height: 320,
    borderRadius: 160,
  },
  ring: {
    position: "absolute",
    width: 260,
    height: 260,
    borderRadius: 130,
    borderWidth: 2,
    borderColor: theme.colors.accent,
  },
  logo: { width: 140, height: 140, marginBottom: 20 },
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

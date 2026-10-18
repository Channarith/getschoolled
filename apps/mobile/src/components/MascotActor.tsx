/**
 * MascotActor — the animated, scene-aware Salareen "Bayon Buddy" that the
 * setup assistant uses to make onboarding feel alive.
 *
 * Why this exists
 * ---------------
 * `MascotSvg` is a plain, static picture. The setup assistant needs the same
 * mascot to:
 *   - fly in from off-screen and point at a CTA on the sign-in page,
 *   - grow/shrink and pick up age-appropriate accessories as the user scrolls
 *     the age wheel on the "What should we call you?" step,
 *   - act out each learning-mode choice on its own page (watch a video,
 *     teach with a baton, sit on a chair for a presentation, read a book,
 *     tutor a child, play a game), and
 *   - idle-bob/dance between all of the above.
 *
 * Design
 * ------
 * The mascot picture itself stays the same locale-aware WebP that
 * `mascotImageForLocale` returns. We layer prop overlays (📖, 🎮, 🎓, 🪑, …)
 * around the mascot image inside positioned Views, driven by `Animated`
 * values. Everything is pure React Native — no new assets, no SVG, no Lottie
 * — so it works offline, is tiny on disk, and keeps bundle size flat.
 *
 * Testability
 * -----------
 * `poseForAge(age)` is pure and exported so a unit test can pin the morph
 * rules (child → teen → adult → senior) without rendering animations.
 */

import { useEffect, useRef } from "react";
import {
  Animated,
  Easing,
  Image,
  StyleSheet,
  Text,
  View,
  type ImageSourcePropType,
  type ViewStyle,
} from "react-native";

import { useT } from "../i18n";
import { mascotImageForLocale } from "../mascot";

export type MascotPointDirection = "left" | "right" | "down" | "up";

export type MascotScene =
  // Default calm bob — used for pages that do not have a themed scene.
  | { kind: "idle" }
  // Entry animation + a hand pointing at a CTA. Used on sign-in.
  | { kind: "flyin-point"; pointAt?: MascotPointDirection; delay?: number }
  // Bouncy dance — reused for celebratory moments.
  | { kind: "dance" }
  // Scale/accessory morph by age (3–120). Used on the name/age step.
  | { kind: "age-morph"; age: number }
  // Learning-mode scenes (one per survey page).
  | { kind: "video" }        // watching a tiny TV
  | { kind: "teacher" }      // glasses + baton + mini chalkboard
  | { kind: "presentation" } // sitting on a chair watching slides
  | { kind: "reading" }      // reading glasses + an open book
  | { kind: "tutoring" }     // adult-sized mascot next to a small child mascot
  | { kind: "gaming" };      // joystick + zap sparks

type Props = {
  scene: MascotScene;
  size?: number;              // base width in logical pixels
  locale?: string;            // override the auth context locale
  style?: ViewStyle;
};

// Age tiers map directly to visible scale + accessory choice. Kept in a pure
// helper so a test can enumerate the boundaries without touching Animated.
export type AgeTier = "child" | "teen" | "adult" | "senior";

export function tierForAge(age: number): AgeTier {
  if (!Number.isFinite(age)) return "adult";
  if (age < 13) return "child";
  if (age < 20) return "teen";
  if (age < 60) return "adult";
  return "senior";
}

/**
 * Visual pose derived from the age wheel. Pure so tests can assert that
 * dragging the wheel to 7 produces a small-child silhouette, 15 a teen, 42 an
 * adult, and 72 a senior-with-glasses — without mounting Animated.
 */
export function poseForAge(age: number): { tier: AgeTier; scale: number; accessory: string } {
  const tier = tierForAge(age);
  switch (tier) {
    case "child":
      return { tier, scale: 0.65, accessory: "🧒" };
    case "teen":
      return { tier, scale: 0.85, accessory: "🎒" };
    case "adult":
      return { tier, scale: 1.0, accessory: "" };
    case "senior":
      return { tier, scale: 0.95, accessory: "👓" };
  }
}

const DEFAULT_SIZE = 180;

export default function MascotActor({ scene, size = DEFAULT_SIZE, locale, style }: Props) {
  const { locale: ctxLocale } = useT();
  const activeLocale = locale ?? ctxLocale;
  const source: ImageSourcePropType = mascotImageForLocale(activeLocale);

  // Shared idle bob — a tiny vertical sine that reads as "alive".
  const bob = useRef(new Animated.Value(0)).current;
  // Entry fly-in: offset starts off-screen for `flyin-point` and settles.
  const flyIn = useRef(new Animated.Value(0)).current;
  // Pointing finger pulse.
  const pointPulse = useRef(new Animated.Value(0)).current;
  // Scale animation (used by age-morph transitions so growing from
  // child → senior reads as a smooth tween, not a jump cut).
  const scaleAnim = useRef(new Animated.Value(1)).current;

  // Idle bob — always on. Low amplitude so it never fights a scene animation.
  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(bob, { toValue: 1, duration: 1200, easing: Easing.inOut(Easing.sin), useNativeDriver: true }),
        Animated.timing(bob, { toValue: 0, duration: 1200, easing: Easing.inOut(Easing.sin), useNativeDriver: true }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [bob]);

  // Fly-in entry whenever we switch INTO a flyin-point scene.
  useEffect(() => {
    if (scene.kind !== "flyin-point") {
      flyIn.setValue(1);
      pointPulse.stopAnimation();
      pointPulse.setValue(0);
      return;
    }
    flyIn.setValue(0);
    Animated.sequence([
      Animated.delay(scene.delay ?? 150),
      Animated.spring(flyIn, { toValue: 1, friction: 6, tension: 60, useNativeDriver: true }),
    ]).start();
    const pulse = Animated.loop(
      Animated.sequence([
        Animated.timing(pointPulse, { toValue: 1, duration: 650, easing: Easing.out(Easing.quad), useNativeDriver: true }),
        Animated.timing(pointPulse, { toValue: 0, duration: 650, easing: Easing.in(Easing.quad), useNativeDriver: true }),
      ]),
    );
    pulse.start();
    return () => pulse.stop();
  }, [scene, flyIn, pointPulse]);

  // Smoothly tween the age-morph scale when the wheel changes.
  useEffect(() => {
    const target = scene.kind === "age-morph" ? poseForAge(scene.age).scale : 1;
    Animated.timing(scaleAnim, {
      toValue: target,
      duration: 300,
      easing: Easing.out(Easing.cubic),
      useNativeDriver: true,
    }).start();
  }, [scene, scaleAnim]);

  const bobTranslate = bob.interpolate({ inputRange: [0, 1], outputRange: [0, -6] });

  // Direction-aware fly-in offset — the mascot sweeps IN from the pointed-at
  // side so the pointing hand lands beside the CTA naturally.
  const flyInOffsetX = flyIn.interpolate({
    inputRange: [0, 1],
    outputRange: scene.kind === "flyin-point"
      ? (scene.pointAt === "right" ? [220, 0] : scene.pointAt === "left" ? [-220, 0] : [0, 0])
      : [0, 0],
  });
  const flyInOffsetY = flyIn.interpolate({
    inputRange: [0, 1],
    outputRange: scene.kind === "flyin-point"
      ? (scene.pointAt === "up" ? [-220, 0] : scene.pointAt === "down" ? [220, 0] : [0, 0])
      : [0, 0],
  });

  const pointBounce = pointPulse.interpolate({ inputRange: [0, 1], outputRange: [0, 8] });

  const imageHeight = Math.round(size * (512 / 250));

  // Dance adds a slight tilt wobble on top of the idle bob.
  const danceTilt = bob.interpolate({ inputRange: [0, 1], outputRange: ["-6deg", "6deg"] });

  return (
    <Animated.View
      testID="mascot-actor"
      accessibilityLabel={`Salareen mascot: ${scene.kind}`}
      style={[
        styles.root,
        style,
        {
          width: size,
          minHeight: imageHeight + 24,
          transform: [
            { translateX: flyInOffsetX },
            { translateY: Animated.add(flyInOffsetY, bobTranslate) as unknown as Animated.AnimatedInterpolation<number> },
          ],
        },
      ]}
    >
      {renderBackdropProps(scene, size)}

      <Animated.View
        style={{
          transform: scene.kind === "dance"
            ? [{ rotate: danceTilt }, { scale: scaleAnim }]
            : [{ scale: scaleAnim }],
        }}
      >
        <Image
          testID="mascot-actor-image"
          source={source}
          style={{ width: size, height: imageHeight, resizeMode: "contain" }}
          accessibilityLabel="Salareen Bayon Buddy mascot"
        />
      </Animated.View>

      {renderForegroundProps(scene, size, pointBounce)}
    </Animated.View>
  );
}

/**
 * Props drawn BEHIND the mascot image — chairs, chalkboards, tutoring child,
 * tiny TV screens etc. Order matters: behind-props render first so the
 * mascot sits on top.
 */
function renderBackdropProps(scene: MascotScene, size: number) {
  switch (scene.kind) {
    case "teacher":
      return (
        <View style={[styles.backdrop, { width: size * 0.9, left: size * 0.05 }]}>
          <View style={[styles.chalkboard, { height: size * 0.45 }]}>
            <Text style={styles.chalkText}>A B C</Text>
          </View>
        </View>
      );
    case "presentation":
      return (
        <View style={[styles.backdrop, { width: size * 0.9, left: size * 0.05 }]}>
          <View style={[styles.slide, { height: size * 0.4 }]}>
            <Text style={styles.slideText}>📊  📈</Text>
          </View>
        </View>
      );
    case "video":
      return (
        <View style={[styles.backdrop, { width: size * 0.8, left: size * 0.1 }]}>
          <View style={[styles.tv, { height: size * 0.35 }]}>
            <Text style={styles.tvText}>▶︎</Text>
          </View>
        </View>
      );
    case "tutoring":
      // Child mascot sidekick peeks in from the left; main mascot plays the adult.
      return (
        <View style={[styles.sideKick, { left: -size * 0.25 }]}>
          <Text style={{ fontSize: Math.round(size * 0.5) }}>🧒</Text>
        </View>
      );
    default:
      return null;
  }
}

/**
 * Props drawn IN FRONT of the mascot image — hands/pointers, books, joysticks,
 * glasses. Everything is sized relative to the mascot so swapping `size` from
 * 160 to 220 keeps the composition proportional.
 */
function renderForegroundProps(
  scene: MascotScene,
  size: number,
  pointBounce: Animated.AnimatedInterpolation<number>,
) {
  switch (scene.kind) {
    case "flyin-point": {
      const horizontal = scene.pointAt === "left" || scene.pointAt === "right";
      const dir = scene.pointAt ?? "down";
      const emoji = dir === "left" ? "👈" : dir === "right" ? "👉" : dir === "up" ? "☝️" : "👇";
      const transform: any = horizontal
        ? [{ translateX: pointBounce }]
        : [{ translateY: pointBounce }];
      return (
        <Animated.View
          style={[
            styles.pointer,
            dir === "left" ? { left: -size * 0.25 } : null,
            dir === "right" ? { right: -size * 0.25 } : null,
            dir === "up" ? { top: -size * 0.1, alignSelf: "center" } : null,
            dir === "down" ? { bottom: -size * 0.1, alignSelf: "center" } : null,
            { transform },
          ]}
        >
          <Text style={{ fontSize: Math.round(size * 0.35) }}>{emoji}</Text>
        </Animated.View>
      );
    }
    case "age-morph": {
      const accessory = poseForAge(scene.age).accessory;
      if (!accessory) return null;
      return (
        <View style={[styles.accessory, { right: -size * 0.1 }]}>
          <Text style={{ fontSize: Math.round(size * 0.3) }}>{accessory}</Text>
        </View>
      );
    }
    case "teacher":
      return (
        <>
          <View style={[styles.accessory, { right: -size * 0.15 }]}>
            <Text style={{ fontSize: Math.round(size * 0.28) }}>👓</Text>
          </View>
          <View style={[styles.handProp, { bottom: size * 0.3, right: -size * 0.18 }]}>
            <Text style={{ fontSize: Math.round(size * 0.28) }}>📏</Text>
          </View>
        </>
      );
    case "reading":
      return (
        <>
          <View style={[styles.accessory, { right: -size * 0.1 }]}>
            <Text style={{ fontSize: Math.round(size * 0.26) }}>👓</Text>
          </View>
          <View style={[styles.handProp, { bottom: size * 0.1, alignSelf: "center" }]}>
            <Text style={{ fontSize: Math.round(size * 0.42) }}>📖</Text>
          </View>
        </>
      );
    case "presentation":
      return (
        <View style={[styles.handProp, { bottom: 0, alignSelf: "center" }]}>
          <Text style={{ fontSize: Math.round(size * 0.3) }}>🪑</Text>
        </View>
      );
    case "gaming":
      return (
        <>
          <View style={[styles.handProp, { bottom: size * 0.08, alignSelf: "center" }]}>
            <Text style={{ fontSize: Math.round(size * 0.38) }}>🎮</Text>
          </View>
          <View style={[styles.sparks, { right: -size * 0.1, top: size * 0.1 }]}>
            <Text style={{ fontSize: Math.round(size * 0.22) }}>⚡</Text>
          </View>
        </>
      );
    case "video":
      // The TV is behind; add a quiet "watching" cue.
      return (
        <View style={[styles.accessory, { right: -size * 0.08 }]}>
          <Text style={{ fontSize: Math.round(size * 0.22) }}>🍿</Text>
        </View>
      );
    case "tutoring":
      // Little "connection" prop between child & mascot.
      return (
        <View style={[styles.handProp, { bottom: size * 0.4, left: -size * 0.05 }]}>
          <Text style={{ fontSize: Math.round(size * 0.22) }}>💡</Text>
        </View>
      );
    default:
      return null;
  }
}

const styles = StyleSheet.create({
  root: {
    alignItems: "center",
    justifyContent: "flex-end",
    position: "relative",
  },
  backdrop: {
    position: "absolute",
    bottom: 0,
    alignItems: "center",
    justifyContent: "flex-end",
  },
  chalkboard: {
    width: "100%",
    backgroundColor: "#1e3a2b",
    borderRadius: 10,
    borderWidth: 4,
    borderColor: "#8b5a2b",
    alignItems: "center",
    justifyContent: "center",
  },
  chalkText: {
    color: "#f8fafc",
    fontSize: 22,
    fontWeight: "800",
    letterSpacing: 4,
  },
  slide: {
    width: "100%",
    backgroundColor: "#fff8e7",
    borderRadius: 10,
    borderWidth: 2,
    borderColor: "#c9bda7",
    alignItems: "center",
    justifyContent: "center",
  },
  slideText: {
    fontSize: 24,
  },
  tv: {
    width: "100%",
    backgroundColor: "#111827",
    borderRadius: 12,
    borderWidth: 4,
    borderColor: "#374151",
    alignItems: "center",
    justifyContent: "center",
  },
  tvText: {
    color: "#f8fafc",
    fontSize: 28,
    fontWeight: "900",
  },
  sideKick: {
    position: "absolute",
    bottom: 0,
    alignItems: "center",
    justifyContent: "flex-end",
  },
  pointer: {
    position: "absolute",
    alignItems: "center",
    justifyContent: "center",
  },
  accessory: {
    position: "absolute",
    top: 0,
  },
  handProp: {
    position: "absolute",
  },
  sparks: {
    position: "absolute",
  },
});

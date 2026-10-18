"use client";

/**
 * MascotActor — the animated, scene-aware Salareen "Bayon Buddy" that the
 * web setup assistant / onboarding flow uses to make each step feel alive.
 *
 * Mirrors the mobile MascotActor contract
 * (apps/mobile/src/components/MascotActor.tsx) so the two platforms morph
 * the mascot the same way. On the web we drive the animations entirely
 * with CSS keyframes + CSS variables (see MascotActor.module.css) instead
 * of React Native's `Animated`, so bundle size stays flat and the figure
 * paints on first frame without hydration jitter.
 *
 * Scene wiring in onboarding/page.tsx:
 *   account step        → `flyin-point` pointing down at the primary CTA
 *   about step          → `age-morph` with the current wheel age
 *   learn step          → scene for the currently-focused mode card
 *   plan / payment step → `idle`
 */

import { useEffect, useState } from "react";

import { resolveMascot } from "../lib/api";
import {
  DEFAULT_MASCOT_SRC,
  resolveMascotLocal,
} from "../lib/mascot";
import {
  type MascotScene,
  poseForAge,
} from "../lib/mascotPose";
import { useT } from "../lib/i18n";
import styles from "./MascotActor.module.css";

type Props = {
  scene: MascotScene;
  /** Base width in pixels for the mascot image; defaults to 240. */
  size?: number;
  className?: string;
};

const DEFAULT_SIZE = 240;

/**
 * How far the mascot slides in for a `flyin-point` scene, in pixels. The
 * sign matches the pointed-at direction (point right → slide in from the
 * left so the finger lands next to the CTA on the right).
 */
const FLY_IN_OFFSET = 180;

export default function MascotActor({ scene, size = DEFAULT_SIZE, className }: Props) {
  const { locale } = useT();
  const [src, setSrc] = useState<string>(DEFAULT_MASCOT_SRC);

  // Resolve the locale-specific mascot WebP once per locale, with a local
  // fallback if the memory service is unreachable (same contract as
  // MascotImage.tsx — reused for consistency).
  useEffect(() => {
    let cancelled = false;
    resolveMascot(locale)
      .then((res) => {
        if (!cancelled) setSrc(res.path || DEFAULT_MASCOT_SRC);
      })
      .catch(() => {
        if (!cancelled) setSrc(resolveMascotLocal(locale).path);
      });
    return () => {
      cancelled = true;
    };
  }, [locale]);

  const pose = scene.kind === "age-morph" ? poseForAge(scene.age) : null;
  const scale = pose ? pose.scale : 1;
  const accessory = pose ? pose.accessory : "";

  // Translate the fly-in direction into CSS vars the keyframe reads.
  let flyInX = 0;
  let flyInY = 0;
  if (scene.kind === "flyin-point") {
    const dir = scene.pointAt ?? "down";
    if (dir === "right") flyInX = -FLY_IN_OFFSET;
    else if (dir === "left") flyInX = FLY_IN_OFFSET;
    else if (dir === "up") flyInY = FLY_IN_OFFSET;
    else if (dir === "down") flyInY = -FLY_IN_OFFSET;
  }

  const stageStyle = {
    // Scene-driven CSS vars consumed by MascotActor.module.css.
    "--mascot-size": `${size}px`,
    "--mascot-scale": scale.toFixed(3),
    "--fly-in-x": `${flyInX}px`,
    "--fly-in-y": `${flyInY}px`,
  } as React.CSSProperties;

  return (
    <div
      className={[styles.root, className].filter(Boolean).join(" ")}
      data-testid="mascot-actor"
      aria-label={`Salareen mascot: ${scene.kind}`}
      role="img"
    >
      <div
        className={styles.stage}
        data-scene={scene.kind}
        style={stageStyle}
      >
        {renderBackdrop(scene)}

        <span className={styles.shadow} aria-hidden />

        <div className={styles.figure}>
          {/* Static <img>, not next/image, so inline CSS vars drive width
              per scene without next/image's size-locked wrapper. */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={src}
            alt="Salareen Bayon Buddy mascot"
            draggable={false}
            data-testid="mascot-actor-image"
          />
        </div>

        {accessory && (
          <span className={styles.accessory} aria-hidden>
            {accessory}
          </span>
        )}

        {renderForeground(scene)}
      </div>
    </div>
  );
}

/**
 * Props rendered BEHIND the mascot (chalkboard, slide, TV, sidekick).
 * Order matters: these paint first so the mascot sits on top of them.
 */
function renderBackdrop(scene: MascotScene) {
  switch (scene.kind) {
    case "teacher":
      return (
        <div className={styles.backdrop} aria-hidden>
          <div className={styles.chalkboard}>A B C</div>
        </div>
      );
    case "presentation":
      return (
        <div className={styles.backdrop} aria-hidden>
          <div className={styles.slide}>📊 📈</div>
        </div>
      );
    case "video":
      return (
        <div className={styles.backdrop} aria-hidden>
          <div className={styles.tv}>▶︎</div>
        </div>
      );
    case "tutoring":
      return (
        <span className={styles.sidekick} aria-hidden>
          🧒
        </span>
      );
    default:
      return null;
  }
}

/**
 * Props rendered IN FRONT of the mascot (pointer, book, joystick, baton,
 * chair, sparks, popcorn). Sized relative to --mascot-size so swapping
 * `size` from 180 → 320 keeps the composition proportional.
 */
function renderForeground(scene: MascotScene) {
  switch (scene.kind) {
    case "flyin-point": {
      const dir = scene.pointAt ?? "down";
      const emoji =
        dir === "left" ? "👈" :
        dir === "right" ? "👉" :
        dir === "up" ? "☝️" : "👇";
      const posClass =
        dir === "left" ? styles.pointerLeft :
        dir === "right" ? styles.pointerRight :
        dir === "up" ? styles.pointerUp : styles.pointerDown;
      return (
        <span className={`${styles.pointer} ${posClass}`} aria-hidden>
          {emoji}
        </span>
      );
    }
    case "teacher":
      return (
        <span className={`${styles.handProp} ${styles.handPropMid}`} aria-hidden>
          📏
        </span>
      );
    case "reading":
      return (
        <span className={`${styles.handProp} ${styles.handPropLow}`} aria-hidden>
          📖
        </span>
      );
    case "presentation":
      return (
        <span className={`${styles.handProp} ${styles.handPropLow}`} aria-hidden>
          🪑
        </span>
      );
    case "gaming":
      return (
        <>
          <span className={`${styles.handProp} ${styles.handPropLow}`} aria-hidden>
            🎮
          </span>
          <span className={styles.sparks} aria-hidden>
            ⚡
          </span>
        </>
      );
    case "video":
      return (
        <span className={`${styles.handProp} ${styles.handPropMid}`} aria-hidden>
          🍿
        </span>
      );
    case "tutoring":
      return (
        <span className={`${styles.handProp} ${styles.handPropMid}`} aria-hidden>
          💡
        </span>
      );
    default:
      return null;
  }
}

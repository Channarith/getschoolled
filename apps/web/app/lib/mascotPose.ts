/**
 * Pure helpers for the web MascotActor.
 *
 * These are deliberately kept out of the React component so a `node:test`
 * unit test can pin the age-tier boundaries and accessory choices without
 * touching the DOM. Mirrors the mobile MascotActor contract
 * (apps/mobile/src/components/MascotActor.tsx) so the two platforms morph
 * the mascot the same way as the user drags the age wheel.
 */

export type MascotPointDirection = "left" | "right" | "down" | "up";

/**
 * Scenes the MascotActor can play. Each one maps to a slot in the setup
 * assistant / onboarding flow:
 *   - `idle`:              bob only. Default for calm pages (plan, payment).
 *   - `flyin-point`:       slides in from the pointed-at side with an emoji
 *                          finger pulsing beside the primary CTA (sign-in /
 *                          account step).
 *   - `dance`:             bob + wobble tilt (celebratory moment).
 *   - `age-morph`:         scales + swaps a child / backpack / glasses prop
 *                          as the age wheel changes (About you step).
 *   - `video` | `teacher` | `presentation` | `reading` | `tutoring` |
 *     `gaming`:            one scene per learning-mode card; the mascot acts
 *                          out whichever mode has focus on the Learn step.
 */
export type MascotScene =
  | { kind: "idle" }
  | { kind: "flyin-point"; pointAt?: MascotPointDirection; delay?: number }
  | { kind: "dance" }
  | { kind: "age-morph"; age: number }
  | { kind: "video" }
  | { kind: "teacher" }
  | { kind: "presentation" }
  | { kind: "reading" }
  | { kind: "tutoring" }
  | { kind: "gaming" };

export type AgeTier = "child" | "teen" | "adult" | "senior";

/**
 * Age tier boundaries — kept identical to the mobile MascotActor
 * (apps/mobile/src/components/MascotActor.tsx::tierForAge) so a 72-year-old
 * sees the same senior-with-glasses silhouette on web as on mobile.
 */
export function tierForAge(age: number): AgeTier {
  if (!Number.isFinite(age)) return "adult";
  if (age < 13) return "child";
  if (age < 20) return "teen";
  if (age < 60) return "adult";
  return "senior";
}

/**
 * Visual pose for the age-morph scene. `scale` is applied to the mascot
 * image; `accessory` is an emoji drawn as a foreground prop (empty string
 * means no accessory). Pure so tests can assert that 7 → small-child, 15 →
 * teen with backpack, 42 → adult, 72 → senior with glasses.
 */
export function poseForAge(age: number): {
  tier: AgeTier;
  scale: number;
  accessory: string;
} {
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

/**
 * Map a learning-mode id (as used in the onboarding `MODES` array) to its
 * MascotActor scene. Centralised here so the Learn step can simply pass
 * `sceneForMode(focus)` without a long switch.
 */
export function sceneForMode(mode: string): MascotScene {
  switch (mode) {
    case "video":
      return { kind: "video" };
    case "live_teacher":
      return { kind: "teacher" };
    case "presentation":
      return { kind: "presentation" };
    case "reading":
      return { kind: "reading" };
    case "tutoring":
      return { kind: "tutoring" };
    case "gaming":
      return { kind: "gaming" };
    default:
      return { kind: "idle" };
  }
}

"use client";

/**
 * MascotActorChoice — picks between four mascot renderers:
 *   - "meshy"   → MascotMeshy, the real Meshy character (apps/web/public/
 *                 mascot3d/Mascot.glb) playing one of 15 Mixamo-rigged
 *                 skeletal clips (Big_Wave_Hello, Confident_Strut,
 *                 Boom_Dance, Indoor_Swing, …). Scene-aware via the
 *                 sceneToMeshy adapter below. **Default** so onboarding
 *                 and the biometric setup assistant share the same live
 *                 animated character instead of a static image.
 *   - "css"     → the lightweight CSS MascotActor (SSR-safe fallback,
 *                 and the opt-out when WebGL is unavailable)
 *   - "pane"    → the older MascotActor3D canvas (Fox placeholder; kept
 *                 for the age-morph physics prototype only)
 *   - "overlay" → MascotOverlay3D rendered as a fixed full-viewport
 *                 canvas that walks across the page and points at
 *                 `data-mascot-target` elements like a video-game NPC
 *
 * Which one wins is decided client-side so you can flip modes without a
 * server restart. In priority order:
 *   1. URL query `?mascot3d=meshy|overlay|pane|0` (sticky in localStorage)
 *   2. localStorage `aoep.mascot3d` = same values
 *   3. Build-time env `NEXT_PUBLIC_MASCOT_3D` = same values
 *   4. Hard-coded default: "meshy"
 *
 * The WebGL versions can't SSR (no document in Node), so they are loaded
 * via next/dynamic with ssr:false. Server render always falls back to the
 * CSS version for instant first paint, then the client swaps up to the
 * live Meshy character once hydrated.
 */

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import MascotActor from "./MascotActor";
import type { MascotScene } from "../lib/mascotPose";
import type { Expression } from "./mascot3d/expressions";
import type { ClipName } from "./MascotMeshy";

const MascotActor3D = dynamic(() => import("./MascotActor3D"), {
  ssr: false,
  loading: () => null,
});
const MascotOverlay3D = dynamic(() => import("./MascotOverlay3D"), {
  ssr: false,
  loading: () => null,
});
const MascotMeshy = dynamic(() => import("./MascotMeshy"), {
  ssr: false,
  loading: () => null,
});

type Mode = "css" | "pane" | "overlay" | "meshy";

const ENV_MODE: Mode | null = (() => {
  const v = (process.env.NEXT_PUBLIC_MASCOT_3D ?? "").toLowerCase();
  if (v === "meshy") return "meshy";
  if (v === "overlay") return "overlay";
  if (v === "pane") return "pane";
  if (v === "1" || v === "true") return "meshy";  // old "on" alias now
                                                   // means the live mesh
  if (v === "0" || v === "false") return "css";
  return null;
})();

/**
 * Translate a scene from the onboarding/learn flow into (expression, clip)
 * props MascotMeshy understands. Keeps the two component APIs independent
 * so the Meshy animation set can grow without touching MascotScene.
 *
 * Mapping intent (all 15 Mixamo clips are listed in MascotMeshy.CLIP_NAMES
 * — pick one that matches the vibe of the step):
 *   idle         → calm cute, cycling idle rotation (same as setup assistant waits)
 *   flyin-point  → excited Big_Wave_Hello
 *   dance        → excited Boom_Dance (celebrate / fun moment)
 *   age-morph    → curious cycling idle
 *   video        → cute Indoor_Swing (relaxed, "watching")
 *   teacher      → serious Confident_Strut
 *   presentation → serious Big_Wave_Hello (presenting / greeting)
 *   reading      → curious cycling idle (no reading-specific clip yet)
 *   tutoring     → curious Wave_for_Help_1 (approachable 1:1)
 *   gaming       → excited _360_Power_Spin_Jump (energetic)
 */
function sceneToMeshy(scene: MascotScene): {
  expression: Expression;
  clip?: ClipName;
  idleRotation: boolean;
} {
  switch (scene.kind) {
    case "idle":         return { expression: "cute",     idleRotation: true  };
    case "flyin-point":  return { expression: "excited",  clip: "Big_Wave_Hello",      idleRotation: false };
    case "dance":        return { expression: "excited",  clip: "Boom_Dance",          idleRotation: false };
    case "age-morph":    return { expression: "curious",  idleRotation: true  };
    case "video":        return { expression: "cute",     clip: "Indoor_Swing",        idleRotation: false };
    case "teacher":      return { expression: "serious",  clip: "Confident_Strut",     idleRotation: false };
    case "presentation": return { expression: "serious",  clip: "Big_Wave_Hello",      idleRotation: false };
    case "reading":      return { expression: "curious",  idleRotation: true  };
    case "tutoring":     return { expression: "curious",  clip: "Wave_for_Help_1",     idleRotation: false };
    case "gaming":       return { expression: "excited",  clip: "_360_Power_Spin_Jump", idleRotation: false };
  }
}

type Props = {
  scene: MascotScene;
  size?: number;
  className?: string;
  /** For overlay mode — which step is active, drives the tour. */
  step?: string;
};

function normalizeMode(raw: string | null): Mode | null {
  if (!raw) return null;
  const v = raw.toLowerCase();
  if (v === "meshy") return "meshy";
  if (v === "overlay") return "overlay";
  if (v === "pane") return "pane";
  // Historical: "1" / "true" used to mean "turn on the 3D pane"; it now
  // means "turn on the live Meshy animation" (which IS the 3D the user
  // actually wants). CSS stays available via "0" / "false" / "css".
  if (v === "1" || v === "true") return "meshy";
  if (v === "0" || v === "false" || v === "css") return "css";
  return null;
}

/**
 * Steps where no mascot should render at all - not CSS, not 3D pane,
 * not the full-viewport walker. The Learner Check step owns the whole
 * frame (camera preview + face mesh + pose prompts) and the stylized
 * Buddha-fox character was reading as a Buddhist / culturally-coded
 * caricature to users while they stared at their own face on screen.
 * Keeping it off this one step avoids that read without stripping the
 * companion from the rest of onboarding (account / about / learn / plan
 * / payment / complete), where it is genuinely helpful signposting.
 */
const MASCOT_HIDDEN_STEPS = new Set<string>(["identity"]);

export default function MascotActorChoice(props: Props) {
  // SSR renders the CSS version so first paint is instant; the client
  // flips up to Meshy once hydrated. URL / localStorage overrides are
  // applied here so you can switch modes without a server restart.
  const [mode, setMode] = useState<Mode>("css");

  useEffect(() => {
    if (typeof window === "undefined") return;
    const url = new URL(window.location.href);
    const qp = normalizeMode(url.searchParams.get("mascot3d"));
    if (qp) {
      window.localStorage.setItem("aoep.mascot3d", qp);
      setMode(qp);
      return;
    }
    const sticky = normalizeMode(window.localStorage.getItem("aoep.mascot3d"));
    // Default to the "overlay" mode: the full-viewport Meshy character
    // that walks between data-mascot-target elements and dwells with a
    // pointing idle at each one. That is what the user actually wants
    // during onboarding - the mascot visibly moves to the active rating
    // card and asks them to score it, like a game-NPC guide. The
    // in-pane "meshy" mode is still available via ?mascot3d=meshy; CSS
    // stays available via ?mascot3d=0 for SSR + WebGL opt-out.
    setMode(sticky ?? ENV_MODE ?? "overlay");
  }, []);

  if (props.step && MASCOT_HIDDEN_STEPS.has(props.step)) {
    return null;
  }

  if (mode === "meshy") {
    // Wrap in a sized box so the fill:true canvas has something to fill.
    // Matches the old MascotActor's px dimensions so the surrounding
    // layout doesn't shift when the mode flips post-hydration.
    const size = props.size ?? 260;
    const meshyProps = sceneToMeshy(props.scene);
    return (
      <div
        className={props.className}
        style={{ width: size, height: size, position: "relative" }}
        data-mascot-mode="meshy"
      >
        <MascotMeshy {...meshyProps} fill />
      </div>
    );
  }
  if (mode === "overlay") {
    return <MascotOverlay3D scene={props.scene} step={props.step} />;
  }
  if (mode === "pane") {
    return <MascotActor3D scene={props.scene} size={props.size} className={props.className} />;
  }
  return <MascotActor scene={props.scene} size={props.size} className={props.className} />;
}

"use client";

/**
 * MascotActorChoice — picks between three mascot renderers:
 *   - "css"     → the lightweight CSS MascotActor (SSR-safe default)
 *   - "pane"    → MascotActor3D rendered in the left art pane (3D canvas,
 *                 skeletal animation + physics, still contained in a pane)
 *   - "overlay" → MascotOverlay3D rendered as a fixed full-viewport canvas
 *                 that walks across the page and points at
 *                 `data-mascot-target` elements like a video-game NPC
 *
 * Which one wins is decided client-side so you can flip modes without a
 * server restart. In priority order:
 *   1. URL query `?mascot3d=overlay` / `?mascot3d=pane` / `?mascot3d=0`
 *      (sticky in localStorage for the next visit)
 *   2. localStorage `aoep.mascot3d` = "overlay" | "pane" | "0"
 *   3. Build-time env `NEXT_PUBLIC_MASCOT_3D` = "overlay" | "1" | "true"
 *
 * The WebGL versions can't SSR (no document in Node), so they are loaded
 * via next/dynamic with ssr:false. Server render always falls back to the
 * CSS version for instant first paint.
 */

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import MascotActor from "./MascotActor";
import type { MascotScene } from "../lib/mascotPose";

const MascotActor3D = dynamic(() => import("./MascotActor3D"), {
  ssr: false,
  loading: () => null,
});
const MascotOverlay3D = dynamic(() => import("./MascotOverlay3D"), {
  ssr: false,
  loading: () => null,
});

type Mode = "css" | "pane" | "overlay";

const ENV_MODE: Mode | null = (() => {
  const v = (process.env.NEXT_PUBLIC_MASCOT_3D ?? "").toLowerCase();
  if (v === "overlay") return "overlay";
  if (v === "1" || v === "true" || v === "pane") return "pane";
  if (v === "0" || v === "false") return "css";
  return null;
})();

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
  if (v === "overlay") return "overlay";
  if (v === "pane" || v === "1" || v === "true") return "pane";
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
  // SSR renders the CSS version. The 3D decision is computed in the
  // browser so URL / localStorage overrides work without a server restart.
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
    setMode(sticky ?? ENV_MODE ?? "css");
  }, []);

  if (props.step && MASCOT_HIDDEN_STEPS.has(props.step)) {
    return null;
  }

  if (mode === "overlay") {
    return <MascotOverlay3D scene={props.scene} step={props.step} />;
  }
  if (mode === "pane") {
    return <MascotActor3D scene={props.scene} size={props.size} className={props.className} />;
  }
  return <MascotActor scene={props.scene} size={props.size} className={props.className} />;
}

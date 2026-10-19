"use client";

/**
 * MascotActorChoice — picks between the lightweight CSS MascotActor
 * (default) and the real-time 3D MascotActor3D.
 *
 * The 3D version is enabled when ANY of these is true:
 *   - process.env.NEXT_PUBLIC_MASCOT_3D is "1" / "true" (build-time, prod)
 *   - URL has ?mascot3d=1 (runtime, dev/QA — no server restart needed)
 *   - localStorage.getItem("aoep.mascot3d") === "1" (sticky QA toggle)
 *
 * The 3D version uses WebGL (via @react-three/fiber) which cannot run during
 * Next.js SSR, so it is loaded via `next/dynamic` with `ssr: false`. On the
 * server we always render the CSS MascotActor so the first paint is instant
 * and SEO-safe; the 3D canvas hydrates in the browser if the flag is set.
 */

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import MascotActor from "./MascotActor";
import type { MascotScene } from "../lib/mascotPose";

const MascotActor3D = dynamic(() => import("./MascotActor3D"), {
  ssr: false,
  loading: () => null,
});

const ENV_FLAG =
  process.env.NEXT_PUBLIC_MASCOT_3D === "1" ||
  process.env.NEXT_PUBLIC_MASCOT_3D === "true";

type Props = {
  scene: MascotScene;
  size?: number;
  className?: string;
};

export default function MascotActorChoice(props: Props) {
  // SSR renders the 2D CSS version (unconditionally). The 3D decision is
  // computed in the browser so URL / localStorage overrides take effect
  // without a server restart.
  const [use3D, setUse3D] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const url = new URL(window.location.href);
    const qp = url.searchParams.get("mascot3d");
    const sticky = window.localStorage.getItem("aoep.mascot3d");
    if (qp === "1" || qp === "true") {
      window.localStorage.setItem("aoep.mascot3d", "1");
      setUse3D(true);
      return;
    }
    if (qp === "0" || qp === "false") {
      window.localStorage.removeItem("aoep.mascot3d");
      setUse3D(false);
      return;
    }
    setUse3D(ENV_FLAG || sticky === "1");
  }, []);

  if (use3D) {
    return <MascotActor3D {...props} />;
  }
  return <MascotActor {...props} />;
}

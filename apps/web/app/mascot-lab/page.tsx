"use client";

/**
 * /mascot-lab — click-through demo for the real Meshy.ai Bayon Buddy
 * mascot with mood overlays and whole-body motion.
 *
 * The character comes from apps/web/public/mascot3d/Mascot.glb (produced
 * by the user's Meshy image-to-3D run and slimmed via
 * scripts/mascot_meshy_prep.py from 93.7 MB -> 4.4 MB).
 *
 * Expression and motion are driven by MascotMeshy.tsx:
 *   - Motion (idle / walk / run) uses whole-body transforms (hop + lean
 *     + sway). The mesh has no skeleton so there is no leg articulation
 *     until the Mixamo pass lands rigged clips - but a hop reads
 *     clearly as walk/run at the eye level we show the character.
 *   - Expression (cute / serious / angry / sad / crying / excited /
 *     curious / mischievous) uses mood overlays - a per-material
 *     emissive tint, a resting body tilt + lean, an optional scale
 *     pulse, and an optional particle sprite overlay (tears /
 *     sparkles / heat shimmer) rendered near the head.
 *
 * Visit http://localhost:3000/mascot-lab.
 */

import dynamic from "next/dynamic";
import { useState } from "react";

import {
  EXPRESSION_LABELS,
  EXPRESSION_NAMES,
  type Expression,
} from "../components/mascot3d/expressions";
import type { MotionState } from "../components/MascotMeshy";

const MascotMeshy = dynamic(() => import("../components/MascotMeshy"), {
  ssr: false,
  loading: () => <div style={placeholderStyle}>Loading mesh…</div>,
});

const MOTIONS: readonly MotionState[] = ["idle", "walk", "run"] as const;

const page: React.CSSProperties = {
  minHeight: "100vh",
  background: "linear-gradient(180deg, #0b1020 0%, #1a1636 100%)",
  color: "#f5efe0",
  padding: "32px 24px",
  fontFamily:
    "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
};
const headline: React.CSSProperties = {
  margin: 0,
  fontSize: 28,
  fontWeight: 700,
  color: "#e6ae36",
  letterSpacing: "-0.02em",
};
const subhead: React.CSSProperties = {
  marginTop: 6,
  color: "#c8c0a4",
  fontSize: 14,
  maxWidth: 720,
  lineHeight: 1.5,
};
const stageWrap: React.CSSProperties = {
  display: "flex",
  flexWrap: "wrap",
  gap: 32,
  marginTop: 24,
  alignItems: "flex-start",
};
const stage: React.CSSProperties = {
  background: "#0b1020",
  borderRadius: 24,
  border: "1px solid rgba(230,174,54,0.3)",
  padding: 16,
  boxShadow: "0 20px 60px rgba(0,0,0,0.5)",
  flexShrink: 0,
};
const controls: React.CSSProperties = { flex: "1 1 320px", minWidth: 320 };
const sectionTitle: React.CSSProperties = {
  fontSize: 12,
  textTransform: "uppercase",
  letterSpacing: "0.12em",
  color: "#e6ae36",
  margin: "18px 0 10px",
};
const btnRow: React.CSSProperties = {
  display: "flex",
  flexWrap: "wrap",
  gap: 10,
};
const btnBase: React.CSSProperties = {
  padding: "10px 14px",
  borderRadius: 10,
  border: "1px solid rgba(255,255,255,0.15)",
  background: "rgba(255,255,255,0.04)",
  color: "#f5efe0",
  fontSize: 14,
  cursor: "pointer",
  transition: "all 150ms ease",
};
const btnActive: React.CSSProperties = {
  background: "linear-gradient(180deg, #e6ae36 0%, #b48c5f 100%)",
  color: "#1a1004",
  borderColor: "#e6ae36",
  fontWeight: 600,
};
const placeholderStyle: React.CSSProperties = {
  width: 480,
  height: 480,
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  color: "#888",
  background: "#0b1020",
  borderRadius: 24,
};
const row: React.CSSProperties = {
  display: "flex",
  gap: 10,
  alignItems: "center",
  marginTop: 8,
};
const hint: React.CSSProperties = {
  fontSize: 12,
  color: "#9a9282",
  marginTop: 12,
  lineHeight: 1.5,
};

export default function MascotLab() {
  const [expression, setExpression] = useState<Expression>("cute");
  const [motion, setMotion] = useState<MotionState>("idle");
  const [interactive, setInteractive] = useState<boolean>(true);

  return (
    <main style={page}>
      <h1 style={headline}>Bayon Buddy — mascot lab</h1>
      <p style={subhead}>
        Real Meshy.ai-generated mesh ({" "}
        <code>apps/web/public/mascot3d/Mascot.glb</code>, 4.4 MB, 15k
        triangles, PBR textures). Expression and motion are driven by
        mood overlays and whole-body transforms — the mesh has no
        skeleton yet, so pick a motion to see the hop + lean, and pick
        an expression to see the color tint + particles + posture.
        Walking legs will land when the Mixamo rigging pass is merged
        in via <code>scripts/mascot_blender_postprocess.py</code>.
      </p>

      <div style={stageWrap}>
        <div style={stage}>
          <MascotMeshy
            expression={expression}
            motion={motion}
            size={480}
            interactive={interactive}
          />
        </div>

        <div style={controls}>
          <h2 style={sectionTitle}>Expression</h2>
          <div style={btnRow}>
            {EXPRESSION_NAMES.map((name) => {
              const active = expression === name;
              return (
                <button
                  key={name}
                  type="button"
                  onClick={() => setExpression(name)}
                  style={{ ...btnBase, ...(active ? btnActive : null) }}
                  title={EXPRESSION_LABELS[name]}
                >
                  {name}
                </button>
              );
            })}
          </div>

          <h2 style={sectionTitle}>Motion</h2>
          <div style={btnRow}>
            {MOTIONS.map((m) => {
              const active = motion === m;
              return (
                <button
                  key={m}
                  type="button"
                  onClick={() => setMotion(m)}
                  style={{ ...btnBase, ...(active ? btnActive : null) }}
                >
                  {m}
                </button>
              );
            })}
          </div>

          <h2 style={sectionTitle}>Camera</h2>
          <div style={row}>
            <label style={{ fontSize: 13, display: "flex", alignItems: "center", gap: 8 }}>
              <input
                type="checkbox"
                checked={interactive}
                onChange={(e) => setInteractive(e.target.checked)}
              />
              Drag to rotate / scroll to zoom
            </label>
          </div>

          <p style={hint}>
            <strong>Why not a cartoon face swap?</strong> The Meshy mesh
            has a sculpted stone face baked into the geometry. Slapping a
            Canvas2D face plane on it looks like a sticker on a statue.
            Instead each expression tints the stone (angry → warm red,
            sad → cool blue, excited → warm gold), nudges the body
            posture (curious tilts right, sad hunches forward), and
            adds a small particle overlay near the head (tears for
            crying, sparkles for excited, heat shimmer for angry). It
            preserves the carved-stone aesthetic while still giving each
            expression a clear read.
          </p>
          <p style={hint}>
            <strong>Why only a hop, not walking legs?</strong> The mesh
            has no skeleton. Meshy image-to-3D produces static geometry.
            Legs that bend will arrive after the Mixamo pass:{" "}
            <code>docs/mascot-meshy-input/mascot_for_mixamo.fbx</code>{" "}
            is already staged for upload.
          </p>
        </div>
      </div>
    </main>
  );
}

"use client";

/**
 * /mascot-lab — click-through demo for the procedural Buddy mascot.
 *
 * Shows one big preview of the character with buttons to:
 *   - swap through all 8 facial expressions (cute, serious, angry, sad,
 *     crying, excited, curious, mischievous)
 *   - switch between idle / walk / run motion states
 *   - toggle orbit controls so you can drag to rotate the camera
 *
 * No backend, no auth, no feature flag - this is a pure authoring tool
 * so you can see exactly what the character looks like without touching
 * onboarding. Visit:
 *
 *   http://localhost:3000/mascot-lab
 */

import dynamic from "next/dynamic";
import { useState } from "react";

import {
  EXPRESSION_LABELS,
  EXPRESSION_NAMES,
  type Expression,
} from "../components/mascot3d/faceTexture";
import type { MotionState } from "../components/mascot3d/proceduralBuddy";

const MascotProcedural = dynamic(
  () => import("../components/MascotProcedural"),
  { ssr: false, loading: () => <div style={placeholderStyle}>Loading…</div> },
);
const MascotMeshy = dynamic(
  () => import("../components/MascotMeshy"),
  { ssr: false, loading: () => <div style={placeholderStyle}>Loading real mesh…</div> },
);

const MOTIONS: readonly MotionState[] = ["idle", "walk", "run"] as const;
type Renderer = "procedural" | "meshy";

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
  maxWidth: 640,
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
  margin: "16px 0 10px",
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
  const [renderer, setRenderer] = useState<Renderer>("meshy");
  const [expression, setExpression] = useState<Expression>("cute");
  const [motion, setMotion] = useState<MotionState>("idle");
  const [interactive, setInteractive] = useState<boolean>(true);

  return (
    <main style={page}>
      <h1 style={headline}>Bayon Buddy — mascot lab</h1>
      <p style={subhead}>
        Two renderers side-by-side so you can A/B compare them.{" "}
        <strong>meshy</strong> loads the real Meshy.ai-generated character
        from <code>apps/web/public/mascot3d/Mascot.glb</code> (4.4 MB, 15k
        triangles, PBR textures, 1,073,512 → 15,000 tris via Blender
        decimate + Draco, static mesh since Meshy image-to-3D does not rig).{" "}
        <strong>procedural</strong> is the fully code-authored stand-in from{" "}
        <code>proceduralBuddy.ts</code> + <code>faceTexture.ts</code> that
        ships with 8 expressions and walk / idle / run cycles but no sculpted
        geometry.
      </p>

      <div style={stageWrap}>
        <div style={stage}>
          {renderer === "meshy" ? (
            <MascotMeshy size={480} interactive={interactive} />
          ) : (
            <MascotProcedural
              expression={expression}
              motion={motion}
              size={480}
              interactive={interactive}
            />
          )}
        </div>

        <div style={controls}>
          <h2 style={sectionTitle}>Renderer</h2>
          <div style={btnRow}>
            {(["meshy", "procedural"] as const).map((r) => {
              const active = renderer === r;
              return (
                <button
                  key={r}
                  type="button"
                  onClick={() => setRenderer(r)}
                  style={{ ...btnBase, ...(active ? btnActive : null) }}
                >
                  {r === "meshy" ? "Meshy mesh (real)" : "Procedural (code)"}
                </button>
              );
            })}
          </div>

          <h2 style={sectionTitle}>
            Facial expression{" "}
            {renderer === "meshy" && (
              <span style={{ opacity: 0.5, fontSize: 11 }}>
                (procedural only — Meshy mesh has a baked face)
              </span>
            )}
          </h2>
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

          <h2 style={sectionTitle}>
            Motion{" "}
            {renderer === "meshy" && (
              <span style={{ opacity: 0.5, fontSize: 11 }}>
                (procedural only — Meshy mesh is static until Mixamo-rigged)
              </span>
            )}
          </h2>
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
              Drag to rotate (orbit controls)
            </label>
          </div>

          <p style={hint}>
            This character is drawn directly in WebGL from code — no external
            model file, no CDN. Walking is a sin-wave swing of the hip + knee +
            arm pivots; expressions are a Canvas2D texture painted onto a plane
            in front of the head sphere. To ship it as the real mascot, point{" "}
            <code>MascotActorChoice</code> at <code>MascotProcedural</code> for
            a new mode (<code>?mascot3d=procedural</code>) — or export the mesh
            using the workflow in <code>docs/mascot-pipeline.txt</code> and use
            the loaded version instead.
          </p>
        </div>
      </div>
    </main>
  );
}

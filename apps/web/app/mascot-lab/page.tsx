"use client";

/**
 * /mascot-lab — click-through demo for the real Meshy.ai Bayon Buddy
 * mascot. The character ships rigged with 15 baked animation clips
 * (produced from the user's Meshy "All Animations" export, slimmed via
 * scripts/mascot_meshy_prep.py from 124 MB -> 3.1 MB).
 *
 * The lab exposes three driving inputs:
 *   - Expression: 8 moods (color tint + particles + posture)
 *   - Motion: idle / walk / run (plays the default clip for each)
 *   - Specific clip: all 15 animations, one at a time
 *   - Idle rotation: cycles through calm/charming idles every 5s
 *     (what the setup assistant uses during wait moments)
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
import type { ClipName, MotionState } from "../components/MascotMeshy";
import { CLIP_NAMES } from "../components/MascotMeshy";

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
  maxWidth: 760,
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
const controls: React.CSSProperties = { flex: "1 1 360px", minWidth: 320 };
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
  gap: 8,
};
const btnBase: React.CSSProperties = {
  padding: "8px 12px",
  borderRadius: 10,
  border: "1px solid rgba(255,255,255,0.15)",
  background: "rgba(255,255,255,0.04)",
  color: "#f5efe0",
  fontSize: 13,
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
  const [clip, setClip] = useState<ClipName | null>(null);
  const [idleRotation, setIdleRotation] = useState<boolean>(false);
  const [interactive, setInteractive] = useState<boolean>(true);

  return (
    <main style={page}>
      <h1 style={headline}>Bayon Buddy — mascot lab</h1>
      <p style={subhead}>
        Real Meshy.ai-generated character with 15 baked animation clips
        (<code>apps/web/public/mascot3d/Mascot.glb</code>, 3.1 MB,
        12k triangles, PBR textures). The legs actually bend. Motion
        buttons map to default clips; the clip picker lets you preview
        every animation; the idle rotation toggles the setup
        assistant&apos;s wait-moment behavior (cycles through calm
        idles every 5 s).
      </p>

      <div style={stageWrap}>
        <div style={stage}>
          <MascotMeshy
            expression={expression}
            motion={motion}
            clip={clip ?? undefined}
            idleRotation={idleRotation}
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
              const active = motion === m && !clip;
              return (
                <button
                  key={m}
                  type="button"
                  onClick={() => {
                    setMotion(m);
                    setClip(null);
                  }}
                  style={{ ...btnBase, ...(active ? btnActive : null) }}
                >
                  {m}
                </button>
              );
            })}
          </div>
          <div style={row}>
            <label style={{ fontSize: 13, display: "flex", alignItems: "center", gap: 8 }}>
              <input
                type="checkbox"
                checked={idleRotation}
                onChange={(e) => {
                  setIdleRotation(e.target.checked);
                  if (e.target.checked) {
                    setMotion("idle");
                    setClip(null);
                  }
                }}
              />
              Idle rotation (cycle calm idles every 5 s — setup assistant mode)
            </label>
          </div>

          <h2 style={sectionTitle}>Specific clip (overrides motion)</h2>
          <div style={btnRow}>
            {CLIP_NAMES.map((c) => {
              const active = clip === c;
              return (
                <button
                  key={c}
                  type="button"
                  onClick={() => setClip(active ? null : c)}
                  style={{ ...btnBase, ...(active ? btnActive : null) }}
                >
                  {c.replace(/_/g, " ").trim()}
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
            <strong>Expressions</strong> layer on top of whichever clip
            is playing: emissive tint (angry = warm red, sad = cool
            blue, excited = warm gold), optional particle overlay near
            the head (tears for crying, sparkles for excited, heat
            shimmer for angry), and body posture (curious tilts right,
            sad hunches forward, mischievous leans left).
          </p>
          <p style={hint}>
            <strong>Setup assistant mode:</strong> turn on &quot;Idle
            rotation&quot; and the character cycles through{" "}
            Big Wave Hello → Confident Strut → Indoor Swing → Boom Dance →
            Wave for Help → Jump Rope → 360 Spin Jump → Wave for Help 2
            every 5 seconds. That&apos;s the wait-moment behavior for
            the Learner Check / camera + mic setup screens.
          </p>
        </div>
      </div>
    </main>
  );
}

"use client";

/**
 * Setup-assistant Sala: the animated Mascot.glb, filling the art stage.
 * The stage is dark so the cream mesh stays visible. Dragging lifts the
 * character out of the pane so the form stays usable.
 */

import dynamic from "next/dynamic";
import { Component, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import type { MascotScene } from "../lib/mascotPose";
import type { Expression } from "./mascot3d/expressions";
import type { ClipName } from "./MascotMeshy";

const MascotMeshy = dynamic(() => import("./MascotMeshy"), { ssr: false });

const STORAGE_KEY = "aoep.mascot.drag.v2";
const STAGE = "#0c2c4a";

type Frame = { x: number; y: number; size: number };

function sceneToMeshy(scene: MascotScene): {
  expression: Expression;
  clip?: ClipName;
  idleRotation: boolean;
} {
  switch (scene.kind) {
    case "idle":
      return { expression: "cute", idleRotation: true };
    case "flyin-point":
      return { expression: "excited", clip: "Big_Wave_Hello", idleRotation: false };
    case "dance":
      return { expression: "excited", clip: "Boom_Dance", idleRotation: false };
    case "age-morph":
      return { expression: "curious", idleRotation: true };
    case "video":
      return { expression: "cute", clip: "Indoor_Swing", idleRotation: false };
    case "teacher":
      return { expression: "serious", clip: "Confident_Strut", idleRotation: false };
    case "presentation":
      return { expression: "serious", clip: "Big_Wave_Hello", idleRotation: false };
    case "reading":
      return { expression: "curious", idleRotation: true };
    case "tutoring":
      return { expression: "curious", clip: "Wave_for_Help_1", idleRotation: false };
    case "gaming":
      return { expression: "excited", clip: "_360_Power_Spin_Jump", idleRotation: false };
  }
}

function clamp(frame: Frame): Frame {
  const size = Math.max(220, Math.min(frame.size, 560));
  const minVisible = Math.min(180, size);
  const maxX = window.innerWidth - minVisible;
  const maxY = window.innerHeight - minVisible;
  return {
    size,
    x: Math.min(maxX, Math.max(minVisible - size, frame.x)),
    y: Math.min(maxY, Math.max(8, frame.y)),
  };
}

function Mesh({ scene }: { scene: MascotScene }) {
  const meshy = sceneToMeshy(scene);
  return (
    <MascotMeshy
      expression={meshy.expression}
      clip={meshy.clip}
      idleRotation={meshy.idleRotation}
      motion="idle"
      fill
      transparent
    />
  );
}

class MeshBoundary extends Component<{ scene: MascotScene }, { error: string | null }> {
  state = { error: null as string | null };

  static getDerivedStateFromError(error: unknown) {
    return { error: error instanceof Error ? error.message : String(error) };
  }

  render() {
    if (this.state.error) {
      return (
        <p style={{ margin: 24, color: "#f4e2b0", fontSize: 14, lineHeight: 1.4 }}>
          Sala could not load. {this.state.error}
        </p>
      );
    }
    return <Mesh scene={this.props.scene} />;
  }
}

export default function MascotDraggable({ scene }: { scene: MascotScene }) {
  const [floating, setFloating] = useState<Frame | null>(null);
  const [ready, setReady] = useState(false);
  const drag = useRef<{ ox: number; oy: number; size: number } | null>(null);

  useEffect(() => {
    // A saved drag box from an earlier build could sit invisibly over the
    // form and swallow clicks. Always start docked in the stage.
    window.localStorage.removeItem(STORAGE_KEY);
    window.localStorage.removeItem("aoep.mascot.drag");
    setReady(true);
  }, []);

  useEffect(() => {
    const onResize = () => {
      setFloating((current) => (current ? clamp(current) : current));
    };
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  const beginDrag = (event: React.PointerEvent<HTMLDivElement>) => {
    if (event.button !== 0) return;
    // A modal (the consent notice) sits in the top layer. If a hit still
    // reaches this stage, ignore it so the character cannot eat the click.
    if (document.querySelector("dialog[open]")) return;
    const rect = event.currentTarget.getBoundingClientRect();
    const size = floating?.size ?? Math.max(280, Math.min(rect.width, rect.height, 520));
    const originX = floating ? floating.x : rect.left + (rect.width - size) / 2;
    const originY = floating ? floating.y : rect.top + (rect.height - size) / 2;
    const startX = event.clientX;
    const startY = event.clientY;
    const alreadyFloating = floating != null;
    drag.current = {
      ox: event.clientX - originX,
      oy: event.clientY - originY,
      size,
    };

    const move = (pointer: PointerEvent) => {
      const active = drag.current;
      if (!active) return;
      const moved = Math.hypot(pointer.clientX - startX, pointer.clientY - startY);
      if (!alreadyFloating && moved < 6) return;
      setFloating(
        clamp({
          x: pointer.clientX - active.ox,
          y: pointer.clientY - active.oy,
          size: active.size,
        }),
      );
    };
    const up = () => {
      drag.current = null;
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      setFloating((current) => {
        if (current) window.localStorage.setItem(STORAGE_KEY, JSON.stringify(current));
        return current;
      });
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  };

  const dock = () => {
    drag.current = null;
    window.localStorage.removeItem(STORAGE_KEY);
    setFloating(null);
  };

  const label = (
    <span
      style={{
        position: "absolute",
        left: 16,
        bottom: 14,
        zIndex: 2,
        padding: "4px 10px",
        borderRadius: 999,
        background: "rgba(7, 20, 34, 0.72)",
        color: "#f4e2b0",
        fontSize: 12,
        letterSpacing: "0.04em",
        pointerEvents: "none",
      }}
    >
      Drag to move
    </span>
  );

  if (ready && floating && typeof document !== "undefined") {
    return createPortal(
      <div
        role="group"
        aria-label="Setup assistant character. Drag to move. Double-click to put back."
        data-mascot-mode="draggable-mesh"
        onPointerDown={beginDrag}
        onDoubleClick={dock}
        style={{
          position: "fixed",
          left: floating.x,
          top: floating.y,
          width: floating.size,
          height: floating.size,
          zIndex: 40,
          cursor: "grab",
          touchAction: "none",
          userSelect: "none",
          borderRadius: 28,
          overflow: "hidden",
          background: STAGE,
        }}
      >
        <div style={{ position: "absolute", inset: 0, pointerEvents: "none" }}>
          <MeshBoundary scene={scene} />
        </div>
        {label}
      </div>,
      document.body,
    );
  }

  return (
    <div
      role="group"
      aria-label="Setup assistant character. Drag to move."
      data-mascot-mode="draggable-mesh"
      onPointerDown={beginDrag}
      style={{
        position: "absolute",
        inset: 0,
        cursor: "grab",
        touchAction: "none",
        userSelect: "none",
        background: STAGE,
      }}
    >
      <div style={{ position: "absolute", inset: 0, pointerEvents: "none" }}>
        <MeshBoundary scene={scene} />
      </div>
      {label}
    </div>
  );
}

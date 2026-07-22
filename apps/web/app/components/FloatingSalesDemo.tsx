"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { AUTH_EVENT, getToken } from "../lib/api";
import { useFlag } from "../lib/flags";

const WIDTH = 132;
const HEIGHT = 42;
const STORAGE_KEY = "aoep-sales-demo-button-position";

type Point = { x: number; y: number };

function clamp(point: Point): Point {
  if (typeof window === "undefined") return point;
  return {
    x: Math.max(0, Math.min(point.x, window.innerWidth - WIDTH)),
    y: Math.max(0, Math.min(point.y, window.innerHeight - HEIGHT)),
  };
}

export default function FloatingSalesDemo() {
  const enabled = useFlag<boolean>("sales_demo.enabled", true);
  const pathname = usePathname();
  const router = useRouter();
  const [signedIn, setSignedIn] = useState(false);
  const [position, setPosition] = useState<Point>({ x: 14, y: 100 });
  const positionRef = useRef(position);
  const dragRef = useRef<{
    pointerId: number;
    startX: number;
    startY: number;
    origin: Point;
    distance: number;
  } | null>(null);

  useEffect(() => {
    const syncAuth = () => setSignedIn(Boolean(getToken()));
    syncAuth();
    window.addEventListener(AUTH_EVENT, syncAuth);
    window.addEventListener("storage", syncAuth);
    return () => {
      window.removeEventListener(AUTH_EVENT, syncAuth);
      window.removeEventListener("storage", syncAuth);
    };
  }, []);

  useEffect(() => {
    let next = { x: 14, y: window.innerHeight - HEIGHT - 18 };
    try {
      const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null") as Point | null;
      if (stored && Number.isFinite(stored.x) && Number.isFinite(stored.y)) next = stored;
    } catch {
      /* Invalid local position: use the default. */
    }
    next = clamp(next);
    positionRef.current = next;
    setPosition(next);
    const onResize = () => {
      const resized = clamp(positionRef.current);
      positionRef.current = resized;
      setPosition(resized);
    };
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  if (!enabled || !signedIn || pathname === "/demo" || pathname === "/login") return null;

  function move(event: React.PointerEvent<HTMLButtonElement>) {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    const dx = event.clientX - drag.startX;
    const dy = event.clientY - drag.startY;
    drag.distance = Math.max(drag.distance, Math.abs(dx) + Math.abs(dy));
    const next = clamp({ x: drag.origin.x + dx, y: drag.origin.y + dy });
    positionRef.current = next;
    setPosition(next);
  }

  function finish(event: React.PointerEvent<HTMLButtonElement>) {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    dragRef.current = null;
    event.currentTarget.releasePointerCapture(event.pointerId);
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(positionRef.current));
    } catch {
      /* Persistence is optional. */
    }
    if (drag.distance < 8) router.push("/demo");
  }

  return (
    <button
      type="button"
      aria-label="Open Sales Demo"
      title="Drag to move · click to open Sales Demo"
      data-testid="sales-demo-button"
      onPointerDown={(event) => {
        event.currentTarget.setPointerCapture(event.pointerId);
        dragRef.current = {
          pointerId: event.pointerId,
          startX: event.clientX,
          startY: event.clientY,
          origin: positionRef.current,
          distance: 0,
        };
      }}
      onPointerMove={move}
      onPointerUp={finish}
      onPointerCancel={() => { dragRef.current = null; }}
      style={{
        position: "fixed",
        left: position.x,
        top: position.y,
        zIndex: 9997,
        width: WIDTH,
        height: HEIGHT,
        borderRadius: HEIGHT / 2,
        border: "1px solid rgba(165,180,252,.58)",
        background: "rgba(30,27,75,.92)",
        color: "#c7d2fe",
        boxShadow: "0 4px 16px rgba(0,0,0,.28)",
        backdropFilter: "blur(8px)",
        fontSize: 13,
        fontWeight: 800,
        cursor: "grab",
        touchAction: "none",
        userSelect: "none",
      }}
    >
      ✨ Sales Demo
    </button>
  );
}

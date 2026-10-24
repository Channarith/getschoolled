"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { AUTH_EVENT, getToken } from "../lib/api";
import type { Expression } from "./mascot3d/expressions";
import type { ClipName } from "./MascotMeshy";

const LandingMascot = dynamic(() => import("./MascotMeshy"), { ssr: false });

/** A feature card is asking the mascot to explain it. */
export type MascotSpotlight = {
  id: string;
  title: string;
  line: string;
  clip: ClipName;
  expression: Expression;
};

/**
 * DN "Dark Navy" orbital mascot stage.
 *
 * Composition
 * -----------
 * Layer 0 (static backdrop): a nano-banana generated image baked in with
 *   the EXACT three-tier dark-navy pedestal and multi-stroke swirling
 *   cyan + gold orbital rings + sparkle dust the user approved from
 *   the reference mockup. One asset per theme (light = cream bg,
 *   dark = navy bg) so edges blend with the body.
 *
 * Layer 1 (DOM): the warm-gold mascot sits centered on the pedestal top.
 *
 * Layer 2 (DOM, animated): six education icon tiles orbit clockwise on a
 *   tilted ellipse so they trace the painted-in ring. Hovering any tile
 *   pauses the orbit and reveals a short description; clicking navigates.
 *
 * Why the backdrop is a baked image, not SVG + CSS
 * ------------------------------------------------
 * The user explicitly asked for the swirling multi-stroke ring + photoreal
 * three-tier pedestal from the reference. That's trivial as an image and
 * hard as hand-rolled SVG with equal fidelity, so we composite: static
 * image for depth, DOM for interaction (hover tooltips, click, keyboard).
 */

type OrbitTab = {
  /** Where the tile goes for a GUEST. Logged-in users always get the
   *  destination from `authedHref` (or `href` when `authedHref` is
   *  omitted). This keeps the landing honest - guests cannot slip past
   *  gated routes by clicking an orbital tile. */
  href: string;
  /** Optional override destination when the viewer is logged in. */
  authedHref?: string;
  label: string;
  icon: string;   // emoji — crisp at small sizes, no sprite sheet needed
  description: string;
  /** True = destination is open to guests. False = guests get bounced
   *  to /login (and the tile shows a small lock in the tooltip). The
   *  user's request: only "Our Story" works without an account. */
  publicForGuests: boolean;
  /** Not released to users yet: renders as a non-interactive tile. */
  disabled?: boolean;
};

/**
 * Six tiles matching the DN mockup's icon vocabulary (book, chat, play,
 * cap, chess, globe). Each mapped to a real Salareen route.
 *
 * Guest-access policy: Our Story is the only brand/marketing page that
 * does not need an account. Everything else (Vision Play Lab, On the Go,
 * Live Class, Careers, Languages) is product surface and routes guests
 * to /login first. Logged-in users jump straight to the feature.
 */
const TABS: OrbitTab[] = [
  {
    href: "/our-story",
    label: "Our Story",
    icon: "📖",
    description: "Why we built Salareen — a patient teacher for every learner.",
    publicForGuests: true,
  },
  {
    href: "/login",
    authedHref: "/arcade",
    label: "Vision Play Lab",
    icon: "♟️",
    description:
      "Hands-free webcam learning: faces, hands, letters, movement, listening.",
    publicForGuests: false,
  },
  {
    href: "/login",
    authedHref: "/drive",
    label: "On the Go",
    icon: "▶️",
    description:
      "Audio-first courses that talk back. Pause, play, learn hands-free.",
    publicForGuests: false,
  },
  {
    href: "/login",
    authedHref: "/class",
    label: "Live Class",
    icon: "🎓",
    description: "Join real live classes with human teachers and your AI tutor.",
    publicForGuests: false,
  },
  {
    href: "/login",
    authedHref: "/jobs",
    label: "Careers",
    icon: "💬",
    description:
      "Real job openings matched to the exact Salareen classes that get you hired.",
    publicForGuests: false,
  },
  {
    href: "/login",
    authedHref: "/languages",
    label: "Languages",
    icon: "🌐",
    description:
      "27-language live translation studio + fully localized courses.",
    publicForGuests: false,
    disabled: true,
  },
];

const PERIOD_MS = 32000; // one full clockwise revolution (slow enough to read)
// Orbit radii as a fraction of the rendered stage width — MEASURED from
// the painted cyan+gold ring in dn-stage-backdrop.png (bright-ring pixel
// bounds in that 1146x928 asset: rx≈540/1146=0.471, ry≈272/928 but
// re-expressed against width so a single scalar drives both axes, giving
// the painted ring aspect ratio). Keeping these in sync with the artwork
// means the tile orbit traces the painted ring instead of floating off
// it. If the backdrop art changes, re-run the measure script and update.
const RADIUS_X_FRAC = 0.465; // horizontal semi-axis / stage width
const RADIUS_Y_FRAC = 0.235; // vertical semi-axis / stage width (tilt ≈ 0.5)

export default function OrbitalMascotStage({
  spotlight = null,
}: {
  /** Set while a feature card is hovered, focused, or pinned. */
  spotlight?: MascotSpotlight | null;
}) {
  const stageRef = useRef<HTMLDivElement | null>(null);
  const pausedRef = useRef<boolean>(false);
  const stageHoverRef = useRef(false);
  const spotlightRef = useRef(spotlight);
  spotlightRef.current = spotlight;
  const [meshReady, setMeshReady] = useState(false);
  const markMeshReady = useCallback(() => setMeshReady(true), []);
  // Live orbit radii — recomputed from the stage's actual width whenever
  // the stage resizes (ResizeObserver). Starts at 0 and gets filled in
  // on the very first observer callback before the first rAF tick that
  // reads them.
  const radiusRef = useRef<{ x: number; y: number }>({ x: 0, y: 0 });
  const [prefersReduced, setPrefersReduced] = useState(false);
  // Guest vs authed. Guests see all non-"Our Story" tiles route to
  // /login (per TAB.publicForGuests). The AUTH_EVENT listener keeps the
  // tile destinations correct if the user signs in while this component
  // is mounted (e.g. opens /login in another tab).
  const [loggedIn, setLoggedIn] = useState<boolean>(false);
  useEffect(() => {
    const sync = () => setLoggedIn(Boolean(getToken()));
    sync();
    window.addEventListener(AUTH_EVENT, sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener(AUTH_EVENT, sync);
      window.removeEventListener("storage", sync);
    };
  }, []);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const sync = () => setPrefersReduced(mq.matches);
    sync();
    mq.addEventListener("change", sync);
    return () => mq.removeEventListener("change", sync);
  }, []);

  useEffect(() => {
    if (!spotlight) setMeshReady(false);
    pausedRef.current = stageHoverRef.current || Boolean(spotlight);
  }, [spotlight]);

  useEffect(() => {
    const stage = stageRef.current;
    if (!stage) return;
    const tiles = Array.from(
      stage.querySelectorAll<HTMLElement>(".dn-orbit-tile"),
    );
    if (tiles.length === 0) return;

    // Keep the orbit radii in sync with the stage's actual rendered width,
    // so the ring is always a visibly-larger diameter around the mascot
    // (rather than shrinking relative to the stage as the viewport grows).
    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry) return;
      const w = entry.contentRect.width;
      radiusRef.current = { x: w * RADIUS_X_FRAC, y: w * RADIUS_Y_FRAC };
      // On reduced motion we don't rAF — reposition tiles now so a window
      // resize still re-lays-out the frozen ring.
      if (prefersReduced) {
        tiles.forEach((tile, i) => {
          const angle = (i / tiles.length) * Math.PI * 2 - Math.PI / 2;
          applyTileTransform(tile, angle, radiusRef.current);
        });
      }
    });
    observer.observe(stage);

    if (prefersReduced) {
      // Initial snapshot in case the observer hasn't fired yet.
      const w = stage.getBoundingClientRect().width;
      radiusRef.current = { x: w * RADIUS_X_FRAC, y: w * RADIUS_Y_FRAC };
      tiles.forEach((tile, i) => {
        const angle = (i / tiles.length) * Math.PI * 2 - Math.PI / 2;
        applyTileTransform(tile, angle, radiusRef.current);
      });
      return () => observer.disconnect();
    }

    const start = performance.now();
    let raf = 0;
    function tick(now: number) {
      if (!pausedRef.current) {
        const elapsed = (now - start) % PERIOD_MS;
        const progress = elapsed / PERIOD_MS;
        tiles.forEach((tile, i) => {
          const angle =
            (progress + i / tiles.length) * Math.PI * 2 - Math.PI / 2;
          applyTileTransform(tile, angle, radiusRef.current);
        });
      }
      raf = requestAnimationFrame(tick);
    }
    raf = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(raf);
      observer.disconnect();
    };
  }, [prefersReduced]);

  return (
    <div
      ref={stageRef}
      className={`dn-orbit-stage${spotlight ? " is-explaining" : ""}`}
      onMouseEnter={() => {
        stageHoverRef.current = true;
        pausedRef.current = true;
      }}
      onMouseLeave={() => {
        stageHoverRef.current = false;
        pausedRef.current = Boolean(spotlightRef.current);
      }}
      aria-label="Explore Salareen — hover a tile for a preview, click to visit"
    >
      {/* Static backdrop: pedestal + swirling cyan/gold rings + sparkles.
          CSS swaps the light/dark asset by data-theme. */}
      <div className="dn-stage-backdrop" aria-hidden />

      {spotlight && !prefersReduced && (
        <div className="dn-nano-motion" aria-hidden>
          <div className="dn-nano-motion-ring" />
        </div>
      )}

      {/* Mascot — warm-gold focal point, centered on the top slab of the
          pedestal baked into the backdrop. We use the "-pedestal" variant
          whose baked cream ground halo has been recolored to the pedestal
          navy so the figure blends flush onto the top platform instead
          of showing a bright white puck under its base. A feature card
          swaps in the rigged mesh so the same character can wave, swing,
          or strut while explaining. */}
      <div className="dn-orbit-mascot">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src="/bayon-mark-pedestal.webp"
          alt="Salareen mascot — kneeling golden Buddha-child with the S medallion"
          width={210}
          className={spotlight && meshReady ? "is-covered" : undefined}
          style={{
            filter: "drop-shadow(0 24px 36px rgba(10, 22, 40, 0.55))",
          }}
        />
        {spotlight && !prefersReduced && (
          <div className={`dn-orbit-mascot-live${meshReady ? " is-ready" : ""}`}>
            <LandingMascot
              expression={spotlight.expression}
              clip={spotlight.clip}
              transparent
              fill
              onReady={markMeshReady}
            />
          </div>
        )}
      </div>

      <div className="dn-mascot-speech-live" aria-live="polite">
        {spotlight && (
          <div
            key={spotlight.id}
            id="dn-mascot-speech"
            className="dn-mascot-speech"
            role="status"
            data-testid="mascot-speech"
          >
            <strong>
              {spotlight.title}
              <span className="dn-mascot-speech-dots" aria-hidden>
                <i />
                <i />
                <i />
              </span>
            </strong>
            {spotlight.line}
          </div>
        )}
      </div>

      {/* Six orbit tiles — real <Link>s so right-click, cmd-click, and
          keyboard navigation work out of the box. Guest-gated tiles
          route to /login (not the gated feature) so the URL bar never
          lies about what's accessible. Only Our Story is open to
          everyone. */}
      {TABS.map((tab) => {
        if (tab.disabled) {
          return (
            <span
              key={tab.label}
              className="dn-orbit-tile dn-orbit-tile-disabled"
              role="img"
              aria-disabled="true"
              aria-label={`${tab.label} — coming soon. ${tab.description}`}
              tabIndex={0}
            >
              <span className="dn-orbit-tile-icon" aria-hidden>
                {tab.icon}
              </span>
              <span className="dn-orbit-tile-label">{tab.label}</span>
              <span className="dn-orbit-tile-tooltip" role="tooltip">
                <strong>{tab.label}</strong>
                <span style={{ marginLeft: 6, fontSize: 11, opacity: 0.85 }}>
                  Coming soon
                </span>
                <br />
                {tab.description}
              </span>
            </span>
          );
        }
        const gated = !tab.publicForGuests && !loggedIn;
        const href = loggedIn && tab.authedHref ? tab.authedHref : tab.href;
        const aria = gated
          ? `${tab.label} — sign in to open. ${tab.description}`
          : `${tab.label} — ${tab.description}`;
        return (
          <Link
            key={tab.label}
            href={href}
            className={`dn-orbit-tile${gated ? " dn-orbit-tile-locked" : ""}`}
            aria-label={aria}
            data-locked={gated ? "true" : undefined}
          >
            <span className="dn-orbit-tile-icon" aria-hidden>
              {tab.icon}
            </span>
            <span className="dn-orbit-tile-label">{tab.label}</span>
            <span className="dn-orbit-tile-tooltip" role="tooltip">
              <strong>{tab.label}</strong>
              {gated && (
                <span style={{ marginLeft: 6, fontSize: 11, opacity: 0.85 }}>
                  🔒 sign in
                </span>
              )}
              <br />
              {tab.description}
            </span>
          </Link>
        );
      })}
    </div>
  );
}

/**
 * Position + depth-scale a tile at the given radial `angle` using the
 * current (resize-aware) ellipse radii. Pure DOM mutation so the rAF
 * loop stays allocation-free.
 */
function applyTileTransform(
  tile: HTMLElement,
  angle: number,
  radii: { x: number; y: number },
): void {
  const x = Math.cos(angle) * radii.x;
  const y = Math.sin(angle) * radii.y;
  const depth = Math.sin(angle); // +1 at bottom (front), -1 at top (back)
  const scale = 0.72 + ((depth + 1) / 2) * 0.4;    // 0.72 .. 1.12
  const opacity = 0.6 + ((depth + 1) / 2) * 0.4;   // 0.6 .. 1.0
  tile.style.transform =
    `translate(-50%, -50%) translate(${x}px, ${y}px) scale(${scale.toFixed(3)})`;
  tile.style.opacity = opacity.toFixed(3);
  // Front half sits above the mascot (z=3); back half sits below the mascot
  // but above the backdrop (z=1). On hover we jump to 20 via CSS so the
  // tooltip pops above every neighbor.
  tile.style.zIndex = depth >= 0 ? "6" : "1";
}

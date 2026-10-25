"use client";

export type AvatarState = "listening" | "idle" | "muted" | "blocked" | "unsupported" | "signin" | "ended";

type Props = {
  state: AvatarState;
  /** Visible short label under/next to the avatar, already translated. */
  label: string;
  ariaLabel: string;
  onActivate: () => void;
  /** Sign-in state: the avatar is a link to the sign-in page instead of a button. */
  signInHref?: string;
  /** Diameter in px (default 88). The combined widget uses a smaller head. */
  size?: number;
  /** Show the speech-bubble label next to the head (default true). When false the label stays available to screen readers and as a tooltip. */
  showLabel?: boolean;
};

const RING: Record<AvatarState, string> = {
  listening: "#d4af37", idle: "#d4af37", muted: "rgba(212,175,55,.45)", blocked: "#f59e0b", unsupported: "#d4af37", signin: "#d4af37", ended: "rgba(212,175,55,.4)",
};

/**
 * Sala, always on screen. A gold ring pulses and a green mic dot shows while the microphone is listening; muted dims her and slashes the mic.
 * The shared dance and giggle module attaches through `data-sala-avatar`.
 */
export default function OnTheGoAvatar({ state, label, ariaLabel, onActivate, signInHref, size = 88, showLabel = true }: Props) {
  const img = Math.round(size * 0.84);
  const dot = Math.max(16, Math.round(size * 0.3));
  const listening = state === "listening";
  const dim = state === "muted" || state === "ended";
  const inner = (
    <>
      <img
        src="/mascots/sala-gold-cutout.png" alt="" width={img} height={img}
        style={{ width: img, height: img, objectFit: "cover", objectPosition: "50% 4%", borderRadius: "50%", pointerEvents: "none", opacity: dim ? 0.55 : 1, filter: dim ? "grayscale(.6)" : "none" }}
      />
      <span
        aria-hidden data-testid="on-the-go-mic-dot"
        style={{
          position: "absolute", right: 0, bottom: 0, width: dot, height: dot, borderRadius: "50%", display: "grid", placeItems: "center",
          border: "2px solid #0b1020", background: listening ? "#16a34a" : state === "muted" || state === "blocked" ? "#475569" : "#1e293b",
        }}
      >
        <svg width={Math.round(dot * 0.54)} height={Math.round(dot * 0.54)} viewBox="0 0 24 24" fill="none" stroke="#f8fafc" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
          <rect x="9" y="3" width="6" height="11" rx="3" fill={listening ? "#f8fafc" : "none"} />
          <path d="M5 11a7 7 0 0 0 14 0M12 18v3" />
          {(state === "muted" || state === "blocked" || state === "unsupported") && <path d="M4 4l16 16" stroke="#fca5a5" />}
        </svg>
      </span>
    </>
  );
  const common = {
    "data-testid": "on-the-go-mascot",
    "data-sala-avatar": "",
    "data-state": state,
    "aria-label": ariaLabel,
    title: label,
    style: {
      position: "relative" as const, width: size, height: size, padding: 0, borderRadius: "50%", cursor: state === "ended" ? "default" : "pointer",
      display: "grid", placeItems: "center", overflow: "visible", background: "#0b1020", textDecoration: "none",
      border: `3px solid ${RING[state]}`,
      boxShadow: listening ? "0 0 0 6px rgba(212,175,55,.28), 0 8px 24px rgba(0,0,0,.4)" : "0 8px 24px rgba(0,0,0,.4)",
      animation: listening ? "otg-ring-pulse 1.8s ease-in-out infinite" : undefined,
    },
  };
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
      <style>{`@keyframes otg-ring-pulse { 0%,100% { box-shadow: 0 0 0 4px rgba(212,175,55,.35), 0 8px 24px rgba(0,0,0,.4); } 50% { box-shadow: 0 0 0 12px rgba(212,175,55,.08), 0 8px 24px rgba(0,0,0,.4); } }
@media (prefers-reduced-motion: reduce) { [data-sala-avatar]:not(.sala-dancing-calm) { animation: none !important; } }`}</style>
      {state === "signin" && signInHref ? (
        <a href={signInHref} {...common}>{inner}</a>
      ) : (
        <button type="button" disabled={state === "ended"} onClick={onActivate} {...common}>{inner}</button>
      )}
      {!showLabel && label && state !== "ended" && (
        <span data-testid="on-the-go-avatar-label" role="status" aria-live="polite" style={{ position: "absolute", width: 1, height: 1, overflow: "hidden", clip: "rect(0 0 0 0)" }}>{label}</span>
      )}
      {showLabel && label && state !== "ended" && (
        <span
          data-testid="on-the-go-avatar-label" role="status" aria-live="polite"
          style={{ maxWidth: 200, fontSize: 13, lineHeight: 1.25, padding: "6px 10px", borderRadius: 12, background: "rgba(11,16,32,.92)", color: "#f4fbff", border: "1px solid rgba(212,175,55,.5)" }}
        >{label}</span>
      )}
    </div>
  );
}

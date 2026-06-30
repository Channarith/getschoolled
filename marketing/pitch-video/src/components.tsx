import React from "react";
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
  Img,
  staticFile,
} from "remotion";
import { COLORS, FONT } from "./theme";

// Animated deep-navy background with a soft moving aurora + faint grid.
export const Background: React.FC<{ hue?: string }> = ({ hue = COLORS.brand }) => {
  const frame = useCurrentFrame();
  const drift = Math.sin(frame / 40) * 60;
  const drift2 = Math.cos(frame / 55) * 80;
  return (
    <AbsoluteFill style={{ backgroundColor: COLORS.bgDeep }}>
      <AbsoluteFill
        style={{
          background: `radial-gradient(60% 55% at ${50 + drift / 8}% ${30 + drift / 20}%, ${hue}33, transparent 70%), radial-gradient(50% 50% at ${20 + drift2 / 10}% ${80}%, ${COLORS.mint}22, transparent 70%), linear-gradient(160deg, ${COLORS.bg}, ${COLORS.bgDeep})`,
        }}
      />
      <AbsoluteFill
        style={{
          opacity: 0.06,
          backgroundImage: `linear-gradient(${COLORS.text} 1px, transparent 1px), linear-gradient(90deg, ${COLORS.text} 1px, transparent 1px)`,
          backgroundSize: "64px 64px",
          maskImage:
            "radial-gradient(circle at 50% 50%, black 30%, transparent 80%)",
        }}
      />
    </AbsoluteFill>
  );
};

// Wraps a scene with a clean fade-in / fade-out at its edges.
export const SceneWrap: React.FC<{
  children: React.ReactNode;
  durationInFrames: number;
  style?: React.CSSProperties;
}> = ({ children, durationInFrames, style }) => {
  const frame = useCurrentFrame();
  const fadeIn = interpolate(frame, [0, 12], [0, 1], {
    extrapolateRight: "clamp",
  });
  const fadeOut = interpolate(
    frame,
    [durationInFrames - 12, durationInFrames],
    [1, 0],
    { extrapolateLeft: "clamp" }
  );
  return (
    <AbsoluteFill
      style={{
        opacity: Math.min(fadeIn, fadeOut),
        fontFamily: FONT,
        color: COLORS.text,
        ...style,
      }}
    >
      {children}
    </AbsoluteFill>
  );
};

// Spring helper for entrance.
export const useEnter = (delay = 0, config = { damping: 16, mass: 0.7 }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return spring({ frame: frame - delay, fps, config });
};

// Big animated headline word that rises + fades in.
export const Rise: React.FC<{
  children: React.ReactNode;
  delay?: number;
  style?: React.CSSProperties;
}> = ({ children, delay = 0, style }) => {
  const p = useEnter(delay);
  return (
    <div
      style={{
        transform: `translateY(${interpolate(p, [0, 1], [40, 0])}px)`,
        opacity: p,
        ...style,
      }}
    >
      {children}
    </div>
  );
};

// Counts a number up to its target value.
export const CountUp: React.FC<{
  to: number;
  delay?: number;
  duration?: number;
  decimals?: number;
  prefix?: string;
  suffix?: string;
  format?: boolean;
}> = ({
  to,
  delay = 0,
  duration = 40,
  decimals = 0,
  prefix = "",
  suffix = "",
  format = false,
}) => {
  const frame = useCurrentFrame();
  const t = interpolate(frame - delay, [0, duration], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const eased = 1 - Math.pow(1 - t, 3);
  const value = eased * to;
  const text = format
    ? value.toLocaleString("en-US", { maximumFractionDigits: decimals })
    : value.toFixed(decimals);
  return (
    <span>
      {prefix}
      {text}
      {suffix}
    </span>
  );
};

// A device-style frame around a screenshot.
export const DeviceFrame: React.FC<{
  src: string;
  delay?: number;
  width?: number;
  rotate?: number;
}> = ({ src, delay = 0, width = 720, rotate = 0 }) => {
  const p = useEnter(delay, { damping: 18, mass: 0.9 });
  return (
    <div
      style={{
        transform: `translateY(${interpolate(p, [0, 1], [60, 0])}px) scale(${interpolate(
          p,
          [0, 1],
          [0.9, 1]
        )}) rotate(${rotate}deg)`,
        opacity: p,
        width,
        borderRadius: 22,
        padding: 10,
        background: `linear-gradient(180deg, ${COLORS.panel2}, ${COLORS.panel})`,
        border: `1px solid ${COLORS.border}`,
        boxShadow: `0 40px 90px rgba(0,0,0,0.55), 0 0 0 1px rgba(110,168,254,0.15)`,
      }}
    >
      <Img
        src={staticFile(src)}
        style={{
          width: "100%",
          borderRadius: 14,
          display: "block",
        }}
      />
    </div>
  );
};

// Small pill / chip.
export const Chip: React.FC<{
  children: React.ReactNode;
  delay?: number;
  color?: string;
}> = ({ children, delay = 0, color = COLORS.brand }) => {
  const p = useEnter(delay);
  return (
    <div
      style={{
        opacity: p,
        transform: `scale(${interpolate(p, [0, 1], [0.8, 1])})`,
        display: "inline-flex",
        alignItems: "center",
        gap: 12,
        padding: "14px 26px",
        borderRadius: 999,
        background: `${color}1f`,
        border: `1px solid ${color}66`,
        color: COLORS.text,
        fontSize: 30,
        fontWeight: 600,
      }}
    >
      {children}
    </div>
  );
};

export const Kicker: React.FC<{ children: React.ReactNode; color?: string }> = ({
  children,
  color = COLORS.brand,
}) => (
  <div
    style={{
      textTransform: "uppercase",
      letterSpacing: 8,
      fontSize: 26,
      fontWeight: 700,
      color,
    }}
  >
    {children}
  </div>
);

import React from "react";
import {
  AbsoluteFill,
  Img,
  interpolate,
  staticFile,
  useCurrentFrame,
} from "remotion";
import { COLORS } from "./theme";
import {
  Background,
  Chip,
  CountUp,
  DeviceFrame,
  Kicker,
  Rise,
  SceneWrap,
  useEnter,
} from "./components";

const center: React.CSSProperties = {
  justifyContent: "center",
  alignItems: "center",
  textAlign: "center",
};

// ----------------------------------------------------------------------------
// SCENE 1 — HOOK: school hasn't changed in 200 years
// ----------------------------------------------------------------------------
export const Hook: React.FC<{ durationInFrames: number }> = ({
  durationInFrames,
}) => {
  return (
    <SceneWrap durationInFrames={durationInFrames} style={center}>
      <Background hue={COLORS.muted} />
      <div style={{ ...center, display: "flex", flexDirection: "column", gap: 24 }}>
        <Rise delay={4}>
          <Kicker color={COLORS.muted}>The classroom of 1825</Kicker>
        </Rise>
        <Rise delay={10}>
          <div style={{ fontSize: 220, fontWeight: 900, lineHeight: 1 }}>
            <CountUp to={200} delay={12} duration={45} /> years
          </div>
        </Rise>
        <Rise delay={28}>
          <div style={{ fontSize: 48, fontWeight: 600, color: COLORS.muted }}>
            One teacher. One pace. Thirty different minds.
          </div>
        </Rise>
        <DeskRow />
      </div>
    </SceneWrap>
  );
};

const DeskRow: React.FC = () => {
  const p = useEnter(40);
  return (
    <div style={{ display: "flex", gap: 28, marginTop: 30, opacity: p }}>
      {Array.from({ length: 9 }).map((_, i) => (
        <div
          key={i}
          style={{
            width: 70,
            height: 50,
            borderRadius: 8,
            background: i === 6 ? COLORS.panel : COLORS.panel2,
            border: `2px solid ${i === 6 ? COLORS.red : COLORS.border}`,
            opacity: i === 6 ? 0.5 : 1,
          }}
        />
      ))}
    </div>
  );
};

// ----------------------------------------------------------------------------
// SCENE 2 — PROBLEM: one pace fits no one
// ----------------------------------------------------------------------------
export const Problem: React.FC<{ durationInFrames: number }> = ({
  durationInFrames,
}) => {
  const rows = [
    { label: "Races ahead — bored", value: 1, color: COLORS.mint, delay: 12 },
    { label: "Keeps up — for now", value: 0.6, color: COLORS.accent, delay: 22 },
    { label: "Falls behind — left out", value: 0.28, color: COLORS.red, delay: 32 },
  ];
  return (
    <SceneWrap durationInFrames={durationInFrames} style={center}>
      <Background hue={COLORS.red} />
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 36,
          width: 1200,
        }}
      >
        <Rise delay={2}>
          <Kicker color={COLORS.red}>The same lesson, the same speed</Kicker>
        </Rise>
        <div style={{ display: "flex", flexDirection: "column", gap: 26 }}>
          {rows.map((r) => (
            <Bar key={r.label} {...r} />
          ))}
        </div>
        <Rise delay={56}>
          <div style={{ fontSize: 58, fontWeight: 800, marginTop: 14 }}>
            What if <span style={{ color: COLORS.brand }}>every</span> learner had
            their <span style={{ color: COLORS.mint }}>own</span> teacher?
          </div>
        </Rise>
      </div>
    </SceneWrap>
  );
};

const Bar: React.FC<{
  label: string;
  value: number;
  color: string;
  delay: number;
}> = ({ label, value, color, delay }) => {
  const p = useEnter(delay);
  const frame = useCurrentFrame();
  const fill = interpolate(frame - delay, [0, 30], [0, value], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return (
    <div style={{ opacity: p, display: "flex", alignItems: "center", gap: 24 }}>
      <div
        style={{
          width: 420,
          textAlign: "right",
          fontSize: 32,
          fontWeight: 600,
          color: COLORS.muted,
        }}
      >
        {label}
      </div>
      <div
        style={{
          flex: 1,
          height: 30,
          borderRadius: 999,
          background: COLORS.panel,
          overflow: "hidden",
        }}
      >
        <div
          style={{
            width: `${fill * 100}%`,
            height: "100%",
            borderRadius: 999,
            background: color,
          }}
        />
      </div>
    </div>
  );
};

// ----------------------------------------------------------------------------
// SCENE 3 — REVEAL: meet Salareen
// ----------------------------------------------------------------------------
export const Reveal: React.FC<{ durationInFrames: number }> = ({
  durationInFrames,
}) => {
  const mascot = useEnter(6, { damping: 14, mass: 1.1 });
  return (
    <SceneWrap durationInFrames={durationInFrames} style={center}>
      <Background hue={COLORS.brand} />
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 60,
          maxWidth: 1500,
        }}
      >
        <Img
          src={staticFile("brand/mascot.png")}
          style={{
            width: 420,
            filter: "drop-shadow(0 30px 60px rgba(0,0,0,0.5))",
            transform: `scale(${interpolate(mascot, [0, 1], [0.7, 1])}) translateY(${interpolate(
              mascot,
              [0, 1],
              [40, 0]
            )}px)`,
            opacity: mascot,
          }}
        />
        <div style={{ textAlign: "left", display: "flex", flexDirection: "column", gap: 18 }}>
          <Rise delay={16}>
            <Kicker>Salareen — Khmer for “to go to school”</Kicker>
          </Rise>
          <Rise delay={22}>
            <div style={{ fontSize: 150, fontWeight: 900, lineHeight: 1 }}>
              Meet{" "}
              <span
                style={{
                  background: `linear-gradient(90deg, ${COLORS.brand}, ${COLORS.mint})`,
                  WebkitBackgroundClip: "text",
                  WebkitTextFillColor: "transparent",
                }}
              >
                Salareen
              </span>
            </div>
          </Rise>
          <Rise delay={34}>
            <div style={{ fontSize: 56, fontWeight: 700, color: COLORS.text }}>
              Thousands of classes. One AI campus.
            </div>
          </Rise>
          <Rise delay={46}>
            <div style={{ fontSize: 38, fontWeight: 500, color: COLORS.muted, maxWidth: 900 }}>
              A patient, brilliant teacher for every learner — in their language,
              on any device.
            </div>
          </Rise>
        </div>
      </div>
    </SceneWrap>
  );
};

// ----------------------------------------------------------------------------
// SCENE 4 — FEATURES: Netflix for learning, but it actually teaches
// ----------------------------------------------------------------------------
const FEATURES = [
  {
    src: "screens/live_class_grounded_answer.webp",
    title: "An AI tutor that shows its work",
    body: "Cites its sources. Never bluffs.",
    color: COLORS.accent,
  },
  {
    src: "screens/drive_mode_player.webp",
    title: "Class on your commute",
    body: "Hands-free audio — eyes on the road.",
    color: COLORS.mint,
  },
  {
    src: "screens/languages_grid.webp",
    title: "Teaches in your language",
    body: "All 27 of them.",
    color: COLORS.brand,
  },
  {
    src: "screens/careers_match.webp",
    title: "Links lessons to real jobs",
    body: "Learn the skill the role actually needs.",
    color: COLORS.gold,
  },
  {
    src: "screens/kids_mode.webp",
    title: "Safe and playful for kids",
    body: "Games, rewards, guardrails built in.",
    color: COLORS.mint,
  },
];

export const Features: React.FC<{ durationInFrames: number }> = ({
  durationInFrames,
}) => {
  const frame = useCurrentFrame();
  const panelW = 1920;
  // Camera pans across panels; hold on each for a beat.
  const stops = FEATURES.map((_, i) => i * panelW);
  const keyframes = FEATURES.flatMap((_, i) => [i * 33 + 8, i * 33 + 28]);
  const positions = FEATURES.flatMap((_, i) => [stops[i], stops[i]]);
  const x = interpolate(frame, keyframes, positions, {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return (
    <SceneWrap durationInFrames={durationInFrames}>
      <Background hue={COLORS.accent} />
      <AbsoluteFill style={{ paddingTop: 70, alignItems: "center" }}>
        <Rise delay={2}>
          <div style={{ textAlign: "center" }}>
            <Kicker>Like Netflix for learning</Kicker>
            <div style={{ fontSize: 56, fontWeight: 800, marginTop: 10 }}>
              …but it actually teaches.
            </div>
          </div>
        </Rise>
      </AbsoluteFill>
      <AbsoluteFill style={{ top: 300 }}>
        <div
          style={{
            display: "flex",
            transform: `translateX(${-x}px)`,
          }}
        >
          {FEATURES.map((f, i) => (
            <div
              key={f.src}
              style={{
                width: panelW,
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: 28,
              }}
            >
              <DeviceFrame src={f.src} width={760} delay={i * 33 + 6} />
              <div style={{ textAlign: "center" }}>
                <div style={{ fontSize: 52, fontWeight: 800, color: f.color }}>
                  {f.title}
                </div>
                <div style={{ fontSize: 36, fontWeight: 500, color: COLORS.muted }}>
                  {f.body}
                </div>
              </div>
            </div>
          ))}
        </div>
      </AbsoluteFill>
    </SceneWrap>
  );
};

// ----------------------------------------------------------------------------
// SCENE 5 — SAFETY + UNIQUE
// ----------------------------------------------------------------------------
export const Safety: React.FC<{ durationInFrames: number }> = ({
  durationInFrames,
}) => {
  return (
    <SceneWrap durationInFrames={durationInFrames} style={center}>
      <Background hue={COLORS.mint} />
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 40,
          alignItems: "center",
          maxWidth: 1500,
        }}
      >
        <Rise delay={2}>
          <div style={{ fontSize: 76, fontWeight: 900, textAlign: "center" }}>
            No one else puts it{" "}
            <span style={{ color: COLORS.brand }}>all in one campus</span>.
          </div>
        </Rise>
        <div style={{ display: "flex", gap: 24, flexWrap: "wrap", justifyContent: "center" }}>
          <Chip delay={18} color={COLORS.mint}>
            A real teacher reviews where it matters
          </Chip>
          <Chip delay={26} color={COLORS.accent}>
            Private &amp; consent-gated — can run on-device
          </Chip>
          <Chip delay={34} color={COLORS.gold}>
            Helps teachers — never replaces them
          </Chip>
        </div>
        <Rise delay={44}>
          <div style={{ fontSize: 40, color: COLORS.muted, textAlign: "center" }}>
            Built to lift students up — never to put them at risk.
          </div>
        </Rise>
      </div>
    </SceneWrap>
  );
};

// ----------------------------------------------------------------------------
// SCENE 6 — SCALE + COST
// ----------------------------------------------------------------------------
const STATS = [
  {
    value: <CountUp to={5} delay={14} duration={40} suffix="M" />,
    label: "learners a day, ready on day one",
    color: COLORS.brand,
  },
  {
    value: (
      <>
        $<CountUp to={0.0012} delay={20} duration={45} decimals={4} />
      </>
    ),
    label: "cost per learner / month",
    color: COLORS.mint,
  },
  {
    value: <CountUp to={27} delay={26} duration={40} />,
    label: "languages, one platform",
    color: COLORS.gold,
  },
  {
    value: (
      <>
        <CountUp to={6.3} delay={30} duration={40} decimals={1} />
        ms
      </>
    ),
    label: "to answer — fast at any size",
    color: COLORS.accent,
  },
];

export const Scale: React.FC<{ durationInFrames: number }> = ({
  durationInFrames,
}) => {
  return (
    <SceneWrap durationInFrames={durationInFrames} style={center}>
      <Background hue={COLORS.brand} />
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 44,
          alignItems: "center",
        }}
      >
        <Rise delay={2}>
          <div style={{ textAlign: "center" }}>
            <Kicker>Built like a power grid — it grows itself</Kicker>
            <div style={{ fontSize: 62, fontWeight: 900, marginTop: 12 }}>
              From one laptop to millions — same code, anywhere.
            </div>
          </div>
        </Rise>
        <div style={{ display: "flex", gap: 30 }}>
          {STATS.map((s, i) => (
            <Stat key={i} {...s} delay={10 + i * 6} />
          ))}
        </div>
        <Rise delay={48}>
          <div style={{ fontSize: 40, color: COLORS.muted, textAlign: "center" }}>
            A whole campus for the price of one small server — and it plugs into
            the tools schools already use.
          </div>
        </Rise>
      </div>
    </SceneWrap>
  );
};

const Stat: React.FC<{
  value: React.ReactNode;
  label: string;
  color: string;
  delay: number;
}> = ({ value, label, color, delay }) => {
  const p = useEnter(delay, { damping: 18, mass: 0.8 });
  return (
    <div
      style={{
        width: 410,
        padding: "40px 30px",
        borderRadius: 24,
        background: `linear-gradient(180deg, ${COLORS.panel2}, ${COLORS.panel})`,
        border: `1px solid ${color}55`,
        boxShadow: `0 24px 60px rgba(0,0,0,0.45)`,
        opacity: p,
        transform: `translateY(${interpolate(p, [0, 1], [40, 0])}px)`,
        textAlign: "center",
      }}
    >
      <div style={{ fontSize: 96, fontWeight: 900, color }}>{value}</div>
      <div style={{ fontSize: 30, fontWeight: 500, color: COLORS.muted }}>
        {label}
      </div>
    </div>
  );
};

// ----------------------------------------------------------------------------
// SCENE 7 — CLOSE / THE ASK
// ----------------------------------------------------------------------------
export const Close: React.FC<{ durationInFrames: number }> = ({
  durationInFrames,
}) => {
  const mascot = useEnter(6, { damping: 14, mass: 1 });
  const cta = useEnter(40);
  return (
    <SceneWrap durationInFrames={durationInFrames} style={center}>
      <Background hue={COLORS.brand} />
      <div style={{ ...center, display: "flex", flexDirection: "column", gap: 28 }}>
        <Img
          src={staticFile("brand/mascot.png")}
          style={{
            width: 240,
            opacity: mascot,
            transform: `scale(${interpolate(mascot, [0, 1], [0.7, 1])})`,
            filter: "drop-shadow(0 24px 50px rgba(0,0,0,0.5))",
          }}
        />
        <Rise delay={14}>
          <div style={{ fontSize: 170, fontWeight: 900, letterSpacing: -2 }}>
            <span
              style={{
                background: `linear-gradient(90deg, ${COLORS.brand}, ${COLORS.mint})`,
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
              }}
            >
              Salareen
            </span>
          </div>
        </Rise>
        <Rise delay={24}>
          <div style={{ fontSize: 52, fontWeight: 700 }}>
            Education that adapts to every child. Safely.
          </div>
        </Rise>
        <div
          style={{
            opacity: cta,
            transform: `scale(${interpolate(cta, [0, 1], [0.85, 1])})`,
            display: "flex",
            gap: 22,
            alignItems: "center",
            marginTop: 10,
          }}
        >
          <div
            style={{
              padding: "20px 44px",
              borderRadius: 14,
              background: COLORS.red,
              color: "#fff",
              fontSize: 40,
              fontWeight: 800,
            }}
          >
            salareen.com
          </div>
          <div style={{ fontSize: 38, fontWeight: 600, color: COLORS.muted }}>
            Invest in the next 200 years of school.
          </div>
        </div>
      </div>
    </SceneWrap>
  );
};

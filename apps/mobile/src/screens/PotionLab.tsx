// Potion Lab — real-time chemistry ARCADE game (React Native port of the web
// /arcade/chemistry page). Atoms drift around the lab and the player taps the
// right ones to build the target molecule before the clock runs out. Each
// molecule built raises the LEVEL (faster + busier); floating hazards —
// bacteria (lose points) and bombs (game over) — must be avoided.
//
// Difficulty is driven by AGE GROUP (kids|tween|teen|adult): kids get the
// slowest atoms, the simplest molecules and no bombs; adults get fast atoms,
// more complex molecules and bombs from the start. Fully client-side.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  LayoutChangeEvent, Pressable, StyleSheet, Text, View,
} from "react-native";

import PrimaryButton from "../components/PrimaryButton";
import { useAndroidBackTo } from "../hooks/useAndroidBack";
import { getPotionBest, setPotionBest } from "../storage";
import { theme } from "../theme";

type ElementSym = "H" | "O" | "C" | "N" | "Na" | "Cl";

const ELEMENTS: Record<ElementSym, { name: string; color: string }> = {
  H: { name: "Hydrogen", color: "#60a5fa" },
  O: { name: "Oxygen", color: "#f87171" },
  C: { name: "Carbon", color: "#94a3b8" },
  N: { name: "Nitrogen", color: "#facc15" },
  Na: { name: "Sodium", color: "#a78bfa" },
  Cl: { name: "Chlorine", color: "#34d399" },
};
const ALL_ELEMENTS = Object.keys(ELEMENTS) as ElementSym[];

type Molecule = { name: string; formula: string; recipe: Partial<Record<ElementSym, number>> };

const M: Record<string, Molecule> = {
  h2: { name: "Hydrogen Gas", formula: "H\u2082", recipe: { H: 2 } },
  o2: { name: "Oxygen", formula: "O\u2082", recipe: { O: 2 } },
  h2o: { name: "Water", formula: "H\u2082O", recipe: { H: 2, O: 1 } },
  nacl: { name: "Salt", formula: "NaCl", recipe: { Na: 1, Cl: 1 } },
  co2: { name: "Carbon Dioxide", formula: "CO\u2082", recipe: { C: 1, O: 2 } },
  hcl: { name: "Acid", formula: "HCl", recipe: { H: 1, Cl: 1 } },
  n2: { name: "Nitrogen Gas", formula: "N\u2082", recipe: { N: 2 } },
  nh3: { name: "Ammonia", formula: "NH\u2083", recipe: { N: 1, H: 3 } },
  ch4: { name: "Methane", formula: "CH\u2084", recipe: { C: 1, H: 4 } },
  cl2: { name: "Chlorine Gas", formula: "Cl\u2082", recipe: { Cl: 2 } },
  h2o2: { name: "Peroxide", formula: "H\u2082O\u2082", recipe: { H: 2, O: 2 } },
  c2h6: { name: "Ethane", formula: "C\u2082H\u2086", recipe: { C: 2, H: 6 } },
  naoh: { name: "Sodium Hydroxide", formula: "NaOH", recipe: { Na: 1, O: 1, H: 1 } },
  n2o: { name: "Laughing Gas", formula: "N\u2082O", recipe: { N: 2, O: 1 } },
  hocl: { name: "Bleach", formula: "HOCl", recipe: { H: 1, O: 1, Cl: 1 } },
  ccl4: { name: "Carbon Tet", formula: "CCl\u2084", recipe: { C: 1, Cl: 4 } },
};

type AgeKey = "kids" | "tween" | "teen" | "adult";

type Profile = {
  label: string;
  pool: Molecule[];
  startSpeed: number; speedPerLevel: number; maxSpeed: number;
  startCap: number; capPerLevel: number; maxCap: number;
  startTime: number; timePerMolecule: number; wrongPenalty: number;
  spawnBase: number; spawnStep: number; spawnMin: number;
  hazardBase: number; hazardPerLevel: number; hazardMax: number;
  bombsFromLevel: number;
};

const PROFILES: Record<AgeKey, Profile> = {
  kids: {
    label: "Kids", pool: [M.h2, M.o2, M.h2o, M.nacl],
    startSpeed: 9, speedPerLevel: 1.2, maxSpeed: 20,
    startCap: 5, capPerLevel: 0.5, maxCap: 8,
    startTime: 35, timePerMolecule: 9, wrongPenalty: 2,
    spawnBase: 800, spawnStep: 30, spawnMin: 460,
    hazardBase: 0.02, hazardPerLevel: 0.012, hazardMax: 0.14, bombsFromLevel: 999,
  },
  tween: {
    label: "Tweens", pool: [M.h2, M.o2, M.h2o, M.nacl, M.co2, M.hcl],
    startSpeed: 12, speedPerLevel: 2, maxSpeed: 28,
    startCap: 6, capPerLevel: 0.7, maxCap: 10,
    startTime: 32, timePerMolecule: 8, wrongPenalty: 3,
    spawnBase: 680, spawnStep: 38, spawnMin: 380,
    hazardBase: 0.04, hazardPerLevel: 0.025, hazardMax: 0.28, bombsFromLevel: 3,
  },
  teen: {
    label: "Teens", pool: [M.o2, M.h2o, M.nacl, M.co2, M.hcl, M.nh3, M.ch4, M.n2],
    startSpeed: 16, speedPerLevel: 3, maxSpeed: 38,
    startCap: 7, capPerLevel: 1, maxCap: 13,
    startTime: 30, timePerMolecule: 7, wrongPenalty: 3,
    spawnBase: 600, spawnStep: 45, spawnMin: 300,
    hazardBase: 0.06, hazardPerLevel: 0.035, hazardMax: 0.38, bombsFromLevel: 2,
  },
  adult: {
    label: "Adults", pool: [M.co2, M.nh3, M.ch4, M.h2o2, M.c2h6, M.naoh, M.n2o, M.hocl, M.ccl4],
    startSpeed: 12, speedPerLevel: 6, maxSpeed: 56,
    startCap: 8, capPerLevel: 1, maxCap: 16,
    startTime: 30, timePerMolecule: 6, wrongPenalty: 4,
    spawnBase: 560, spawnStep: 55, spawnMin: 240,
    hazardBase: 0.05, hazardPerLevel: 0.055, hazardMax: 0.48, bombsFromLevel: 1,
  },
};

type Kind = "atom" | "bacteria" | "bomb";
type Cell = { id: number; kind: Kind; sym?: ElementSym; x: number; y: number; vx: number; vy: number };

const BACTERIA_POINTS = 12;
const ATOM_SIZE = 46;

type Phase = "intro" | "playing" | "over";
type EndCause = "time" | "bomb";

let _aid = 1;

function randPos() { return { x: 8 + Math.random() * 84, y: 14 + Math.random() * 80 }; }
function randVel(speed: number) {
  const ang = Math.random() * Math.PI * 2;
  return { vx: Math.cos(ang) * speed, vy: Math.sin(ang) * speed };
}

type Props = {
  age: AgeKey;
  onBack: () => void;
};

export default function PotionLab({ age, onBack }: Props) {
  const prof = useMemo(() => PROFILES[age] ?? PROFILES.kids, [age]);
  useAndroidBackTo(onBack);

  const [phase, setPhase] = useState<Phase>("intro");
  const [cells, setCells] = useState<Cell[]>([]);
  const [targetIdx, setTargetIdx] = useState(0);
  const [need, setNeed] = useState<Partial<Record<ElementSym, number>>>({});
  const [score, setScore] = useState(0);
  const [streak, setStreak] = useState(0);
  const [timeLeft, setTimeLeft] = useState(prof.startTime);
  const [built, setBuilt] = useState(0);
  const [best, setBest] = useState(0);
  const [flash, setFlash] = useState<"good" | "bad" | "boom" | "">("");
  const [cause, setCause] = useState<EndCause>("time");

  // Field size (measured) — atoms are positioned in % then converted to px.
  const [field, setField] = useState({ w: 0, h: 0 });
  const onFieldLayout = useCallback((e: LayoutChangeEvent) => {
    const { width, height } = e.nativeEvent.layout;
    setField({ w: width, h: height });
  }, []);

  const needRef = useRef(need);
  const builtRef = useRef(0);
  const capRef = useRef(prof.startCap);
  const speedRef = useRef(prof.startSpeed);
  const scoreRef = useRef(0);
  useEffect(() => { needRef.current = need; }, [need]);
  useEffect(() => { scoreRef.current = score; }, [score]);

  useEffect(() => { void getPotionBest().then(setBest); }, []);

  const pool = prof.pool;
  const target = pool[Math.min(targetIdx, pool.length - 1)];
  const level = built + 1;

  const newAtom = useCallback((sym: ElementSym): Cell => (
    { id: _aid++, kind: "atom", sym, ...randPos(), ...randVel(speedRef.current) }
  ), []);

  const spawnCell = useCallback((): Cell => {
    const lvl = builtRef.current;
    const hazardChance = Math.min(prof.hazardMax, prof.hazardBase + lvl * prof.hazardPerLevel);
    if (Math.random() < hazardChance) {
      const bombAllowed = lvl + 1 >= prof.bombsFromLevel;
      const isBomb = bombAllowed && Math.random() < 0.32;
      return { id: _aid++, kind: isBomb ? "bomb" : "bacteria", ...randPos(), ...randVel(speedRef.current) };
    }
    const needed = (Object.keys(needRef.current) as ElementSym[]).filter((s) => (needRef.current[s] ?? 0) > 0);
    const sym = needed.length && Math.random() < 0.6
      ? needed[Math.floor(Math.random() * needed.length)]
      : ALL_ELEMENTS[Math.floor(Math.random() * ALL_ELEMENTS.length)];
    return newAtom(sym);
  }, [prof, newAtom]);

  // Guarantee every still-needed element has at least one atom on the field, so a
  // recipe is never impossible. If the field is full, evict a distractor/hazard.
  const ensureNeeded = useCallback((list: Cell[]): Cell[] => {
    const needObj = needRef.current;
    const neededSyms = (Object.keys(needObj) as ElementSym[]).filter((s) => (needObj[s] ?? 0) > 0);
    if (!neededSyms.length) return list;
    const present = new Set(list.filter((c) => c.kind === "atom").map((c) => c.sym));
    let next = list;
    for (const sym of neededSyms) {
      if (present.has(sym)) continue;
      const atom = newAtom(sym);
      if (next.length < capRef.current) {
        next = [...next, atom];
      } else {
        const evictIdx = next.findIndex((c) => c.kind !== "atom" || !neededSyms.includes(c.sym as ElementSym));
        if (evictIdx >= 0) { next = next.slice(); next[evictIdx] = atom; }
        else { next = [...next, atom]; }
      }
      present.add(sym);
    }
    return next;
  }, [newAtom]);

  const loadMolecule = useCallback((idx: number) => {
    setTargetIdx(idx);
    setNeed({ ...pool[idx].recipe });
    needRef.current = { ...pool[idx].recipe };
  }, [pool]);

  const startGame = useCallback(() => {
    capRef.current = prof.startCap;
    speedRef.current = prof.startSpeed;
    builtRef.current = 0;
    setScore(0); setStreak(0); setBuilt(0); setTimeLeft(prof.startTime); setCause("time");
    loadMolecule(0);
    let seed: Cell[] = [];
    for (let i = 0; i < prof.startCap; i++) seed.push(spawnCell());
    seed = ensureNeeded(seed);
    setCells(seed);
    setPhase("playing");
  }, [prof, loadMolecule, spawnCell, ensureNeeded]);

  const endGame = useCallback((why: EndCause) => {
    setCause(why);
    setPhase("over");
    void setPotionBest(scoreRef.current).then(setBest);
  }, []);

  // Movement loop.
  useEffect(() => {
    if (phase !== "playing") return;
    let raf = 0;
    let last = Date.now();
    const step = () => {
      const now = Date.now();
      const dt = Math.min(0.05, (now - last) / 1000);
      last = now;
      setCells((list) => list.map((a) => {
        let { x, y, vx, vy } = a;
        x += vx * dt; y += vy * dt;
        if (x < 5) { x = 5; vx = Math.abs(vx); } else if (x > 95) { x = 95; vx = -Math.abs(vx); }
        if (y < 12) { y = 12; vy = Math.abs(vy); } else if (y > 94) { y = 94; vy = -Math.abs(vy); }
        return { ...a, x, y, vx, vy };
      }));
      raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [phase]);

  // Spawner — interval shrinks as the level rises.
  useEffect(() => {
    if (phase !== "playing") return;
    const spawnMs = Math.max(prof.spawnMin, prof.spawnBase - built * prof.spawnStep);
    const id = setInterval(() => {
      setCells((list) => {
        let next = ensureNeeded(list);
        if (next.length < capRef.current) next = [...next, spawnCell()];
        return next;
      });
    }, spawnMs);
    return () => clearInterval(id);
  }, [phase, built, prof, spawnCell, ensureNeeded]);

  // Countdown.
  useEffect(() => {
    if (phase !== "playing") return;
    const id = setInterval(() => {
      setTimeLeft((t) => Math.max(0, Math.round((t - 0.1) * 10) / 10));
    }, 100);
    return () => clearInterval(id);
  }, [phase]);

  useEffect(() => {
    if (phase === "playing" && timeLeft <= 0) endGame("time");
  }, [timeLeft, phase, endGame]);

  const doFlash = useCallback((kind: "good" | "bad" | "boom") => {
    setFlash(kind);
    setTimeout(() => setFlash(""), kind === "boom" ? 400 : 220);
  }, []);

  const clickCell = useCallback((a: Cell) => {
    if (phase !== "playing") return;
    setCells((list) => list.filter((x) => x.id !== a.id));

    if (a.kind === "bomb") { doFlash("boom"); endGame("bomb"); return; }
    if (a.kind === "bacteria") {
      setStreak(0);
      setScore((s) => Math.max(0, s - BACTERIA_POINTS));
      doFlash("bad");
      return;
    }

    const remaining = needRef.current[a.sym as ElementSym] ?? 0;
    if (remaining > 0) {
      const nextNeed = { ...needRef.current, [a.sym as ElementSym]: remaining - 1 };
      needRef.current = nextNeed;
      setNeed(nextNeed);
      setStreak((s) => s + 1);
      setScore((s) => s + 5 + Math.min(streak, 10));
      doFlash("good");
      if ((Object.values(nextNeed) as number[]).every((v) => v <= 0)) {
        const nb = builtRef.current + 1;
        builtRef.current = nb;
        setBuilt(nb);
        speedRef.current = Math.min(prof.maxSpeed, prof.startSpeed + nb * prof.speedPerLevel);
        capRef.current = Math.min(prof.maxCap, Math.floor(prof.startCap + nb * prof.capPerLevel));
        setScore((s) => s + 30 + Math.floor(timeLeft));
        setTimeLeft((t) => t + prof.timePerMolecule);
        setCells((list) => list.map((c) => ({ ...c, vx: c.vx * 1.1, vy: c.vy * 1.1 })));
        let nxt = Math.floor(Math.random() * pool.length);
        if (nxt === targetIdx) nxt = (nxt + 1) % pool.length;
        loadMolecule(nxt);
      }
      setCells((list) => ensureNeeded(list));
    } else {
      setStreak(0);
      setTimeLeft((t) => Math.max(0, t - prof.wrongPenalty));
      doFlash("bad");
    }
  }, [phase, streak, timeLeft, targetIdx, pool, prof, loadMolecule, doFlash, endGame, ensureNeeded]);

  const slots = useMemo(() => {
    const out: { sym: ElementSym; filled: boolean }[] = [];
    for (const sym of Object.keys(target.recipe) as ElementSym[]) {
      const total = target.recipe[sym] ?? 0;
      const left = need[sym] ?? 0;
      for (let i = 0; i < total; i++) out.push({ sym, filled: i < total - left });
    }
    return out;
  }, [target, need]);

  const timePct = Math.max(0, Math.min(100, (timeLeft / prof.startTime) * 100));
  const fieldBorder =
    flash === "good" ? "#34d399"
    : flash === "bad" ? "#ef4444"
    : flash === "boom" ? "#ef4444"
    : theme.colors.border;

  // Convert a cell's %-position to pixels, centering the token on the point.
  const px = (a: Cell) => ({
    left: (a.x / 100) * field.w - ATOM_SIZE / 2,
    top: (a.y / 100) * field.h - ATOM_SIZE / 2,
  });

  return (
    <View style={styles.wrap}>
      <View style={styles.header}>
        <PrimaryButton label="← Back" onPress={onBack} variant="ghost" />
        <Text style={styles.title}>⚗️ Potion Lab</Text>
        <Text style={styles.mode}>{prof.label}</Text>
      </View>

      {/* HUD */}
      <View style={styles.hud}>
        <Text style={styles.hudScore}>⭐ {score}</Text>
        <Text style={styles.hudLevel}>🧪 Level {level}</Text>
        <Text style={styles.hudMuted}>Best: {best}</Text>
        <Text style={[styles.hudStreak, streak >= 3 && styles.hudStreakHot]}>🔥 {streak}</Text>
      </View>
      <View style={styles.timeTrack}>
        <View style={[styles.timeFill, {
          width: `${timePct}%`,
          backgroundColor: timeLeft <= 6 ? "#ef4444" : "#34d399",
        }]} />
      </View>

      {/* Target */}
      <View style={styles.target}>
        <Text style={styles.targetText}>
          Make: {target.name} <Text style={styles.targetFormula}>({target.formula})</Text>
        </Text>
        <View style={styles.slotRow}>
          {slots.map((s, i) => (
            <View key={i} style={[styles.slot, s.filled && styles.slotFilled]}>
              <Text style={[styles.slotText, s.filled && styles.slotTextFilled]}>{s.sym}</Text>
            </View>
          ))}
        </View>
      </View>

      {/* Playfield */}
      <View style={[styles.field, { borderColor: fieldBorder }]} onLayout={onFieldLayout}>
        {phase === "playing" && field.w > 0 && cells.map((a) => {
          const pos = px(a);
          if (a.kind === "atom") {
            const el = ELEMENTS[a.sym as ElementSym];
            return (
              <Pressable key={a.id} onPress={() => clickCell(a)}
                style={[styles.atom, { left: pos.left, top: pos.top, backgroundColor: el.color }]}>
                <Text style={styles.atomText}>{a.sym}</Text>
              </Pressable>
            );
          }
          return (
            <Pressable key={a.id} onPress={() => clickCell(a)}
              style={[styles.atom, styles.hazard,
                a.kind === "bomb" ? styles.bomb : styles.germ,
                { left: pos.left, top: pos.top }]}>
              <Text style={styles.hazardText}>{a.kind === "bomb" ? "💣" : "🦠"}</Text>
            </Pressable>
          );
        })}

        {phase === "intro" && (
          <View style={styles.overlay}>
            <Text style={styles.overlayEmoji}>⚗️</Text>
            <Text style={styles.overlayTitle}>Catch the atoms! ({prof.label})</Text>
            <Text style={styles.overlayBody}>
              Tap the atoms that match the recipe to build the molecule. Each one you build
              levels you up — faster atoms, more chaos! Avoid 🦠 bacteria (lose points)
              {prof.bombsFromLevel < 999 ? " and never tap 💣 bombs (game over)!" : "."}
            </Text>
            <PrimaryButton label="▶ Start" onPress={startGame} variant="netflix" />
          </View>
        )}

        {phase === "over" && (
          <View style={styles.overlay}>
            <Text style={styles.overlayEmoji}>
              {cause === "bomb" ? "💥" : (score >= best && score > 0 ? "🏆" : "🧪")}
            </Text>
            <Text style={styles.overlayTitle}>
              {cause === "bomb" ? "Boom! You tapped a bomb!" : "Time's up!"}
            </Text>
            <Text style={styles.overlayBody}>
              You reached Level {level} with {score} points.
              {score >= best && score > 0 ? " New best! 🎉" : ` Best: ${best}`}
            </Text>
            <PrimaryButton label="🔁 Play again" onPress={startGame} variant="netflix" />
          </View>
        )}
      </View>

      <Text style={styles.footer}>
        Build a molecule for bonus points and +{prof.timePerMolecule}s. 🦠 = lose points
        {prof.bombsFromLevel < 999 ? " · 💣 = game over!" : ""}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, paddingHorizontal: 16, paddingTop: 56, gap: 8 },
  header: { flexDirection: "row", alignItems: "center", gap: 8 },
  title: { color: theme.colors.text, fontSize: 20, fontWeight: "800", flex: 1 },
  mode: { color: "#a78bfa", fontSize: 13, fontWeight: "700" },
  hud: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginTop: 4 },
  hudScore: { color: theme.colors.text, fontWeight: "800", fontSize: 15 },
  hudLevel: { color: "#a78bfa", fontWeight: "800", fontSize: 15 },
  hudMuted: { color: theme.colors.muted, fontSize: 13 },
  hudStreak: { color: theme.colors.muted, fontWeight: "700", fontSize: 14 },
  hudStreakHot: { color: theme.colors.gold },
  timeTrack: { height: 12, borderRadius: 8, backgroundColor: theme.colors.panel2, overflow: "hidden", marginVertical: 4 },
  timeFill: { height: "100%", borderRadius: 8 },
  target: {
    alignItems: "center", gap: 8, marginVertical: 4,
    backgroundColor: "#ffffff", borderRadius: 14, padding: 10,
    borderWidth: 2, borderColor: "#dc2626",
  },
  targetText: { fontWeight: "800", fontSize: 16, color: "#0b1020" },
  targetFormula: { color: "#dc2626" },
  slotRow: { flexDirection: "row", flexWrap: "wrap", gap: 6, justifyContent: "center" },
  slot: {
    width: 26, height: 26, borderRadius: 13, alignItems: "center", justifyContent: "center",
    borderWidth: 2, borderColor: "#dc2626", backgroundColor: "transparent",
  },
  slotFilled: { backgroundColor: "#dc2626" },
  slotText: { fontSize: 12, fontWeight: "800", color: "#dc2626" },
  slotTextFilled: { color: "#ffffff" },
  field: {
    flex: 1, borderRadius: 18, overflow: "hidden", borderWidth: 2,
    backgroundColor: "#0a0f24", marginVertical: 4,
  },
  atom: {
    position: "absolute", width: ATOM_SIZE, height: ATOM_SIZE, borderRadius: ATOM_SIZE / 2,
    alignItems: "center", justifyContent: "center",
    ...theme.shadow.card,
  },
  atomText: { color: "#0b1020", fontWeight: "800", fontSize: 16 },
  hazard: { alignItems: "center", justifyContent: "center" },
  hazardText: { fontSize: 24 },
  germ: { backgroundColor: "#16a34a", borderWidth: 3, borderColor: "rgba(34,197,94,0.5)" },
  bomb: { backgroundColor: "#111827", borderWidth: 3, borderColor: "rgba(239,68,68,0.6)" },
  overlay: {
    ...StyleSheet.absoluteFillObject,
    alignItems: "center", justifyContent: "center", gap: 10, padding: 24,
    backgroundColor: "rgba(8,12,28,0.82)",
  },
  overlayEmoji: { fontSize: 52 },
  overlayTitle: { color: theme.colors.text, fontSize: 18, fontWeight: "800", textAlign: "center" },
  overlayBody: { color: theme.colors.muted, fontSize: 14, textAlign: "center", lineHeight: 20, maxWidth: 460 },
  footer: { color: theme.colors.muted, fontSize: 12, textAlign: "center", marginBottom: 8 },
});

export type { AgeKey as PotionAgeKey };

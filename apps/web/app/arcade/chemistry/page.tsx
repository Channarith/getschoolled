"use client";

// Potion Lab - a real-time chemistry ARCADE game. Atoms drift around the lab and
// the player catches the right ones to build the target molecule before the clock
// runs out. Each molecule built raises the LEVEL (faster + busier), and floating
// hazards - bacteria (lose points) and bombs (game over) - must be avoided.
//
// Difficulty is driven by AGE GROUP (?age=kids|tween|teen|adult): kids get the
// slowest atoms, the simplest molecules and no bombs; adults get fast atoms, more
// complex molecules and bombs from the start. Fully client-side (no backend).

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

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

type Molecule = { name: string; formula: string; emoji: string; recipe: Partial<Record<ElementSym, number>> };

const M: Record<string, Molecule> = {
  h2: { name: "Hydrogen Gas", formula: "H\u2082", emoji: "\u{1F388}", recipe: { H: 2 } },
  o2: { name: "Oxygen", formula: "O\u2082", emoji: "\u{1FAE7}", recipe: { O: 2 } },
  h2o: { name: "Water", formula: "H\u2082O", emoji: "\u{1F4A7}", recipe: { H: 2, O: 1 } },
  nacl: { name: "Salt", formula: "NaCl", emoji: "\u{1F9C2}", recipe: { Na: 1, Cl: 1 } },
  co2: { name: "Carbon Dioxide", formula: "CO\u2082", emoji: "\u2601\uFE0F", recipe: { C: 1, O: 2 } },
  hcl: { name: "Acid", formula: "HCl", emoji: "\u{1F9EA}", recipe: { H: 1, Cl: 1 } },
  n2: { name: "Nitrogen Gas", formula: "N\u2082", emoji: "\u{1F4A8}", recipe: { N: 2 } },
  nh3: { name: "Ammonia", formula: "NH\u2083", emoji: "\u{1F9F4}", recipe: { N: 1, H: 3 } },
  ch4: { name: "Methane", formula: "CH\u2084", emoji: "\u{1F525}", recipe: { C: 1, H: 4 } },
  cl2: { name: "Chlorine Gas", formula: "Cl\u2082", emoji: "\u{1F7E2}", recipe: { Cl: 2 } },
  h2o2: { name: "Peroxide", formula: "H\u2082O\u2082", emoji: "\u{1F9EB}", recipe: { H: 2, O: 2 } },
  c2h6: { name: "Ethane", formula: "C\u2082H\u2086", emoji: "\u26FD", recipe: { C: 2, H: 6 } },
  // Complex (adult) molecules - 3+ atoms and/or 3 different elements.
  naoh: { name: "Sodium Hydroxide", formula: "NaOH", emoji: "\u{1F9FC}", recipe: { Na: 1, O: 1, H: 1 } },
  n2o: { name: "Laughing Gas", formula: "N\u2082O", emoji: "\u{1F604}", recipe: { N: 2, O: 1 } },
  hocl: { name: "Bleach", formula: "HOCl", emoji: "\u{1FAA3}", recipe: { H: 1, O: 1, Cl: 1 } },
  ccl4: { name: "Carbon Tet", formula: "CCl\u2084", emoji: "\u{1F9EF}", recipe: { C: 1, Cl: 4 } },
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
    // Most complex molecules (3+ atoms / 3 elements). Starts SLOW, then ramps hard.
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
const BEST_KEY = "potionlab_best";

type Phase = "intro" | "playing" | "over";
type EndCause = "time" | "bomb";

let _aid = 1;

function randPos() { return { x: 8 + Math.random() * 84, y: 14 + Math.random() * 80 }; }
function randVel(speed: number) {
  const ang = Math.random() * Math.PI * 2;
  return { vx: Math.cos(ang) * speed, vy: Math.sin(ang) * speed };
}

export default function PotionLabPage() {
  const [age, setAge] = useState<AgeKey>("kids");
  const prof = useMemo(() => PROFILES[age], [age]);

  const [phase, setPhase] = useState<Phase>("intro");
  const [cells, setCells] = useState<Cell[]>([]);
  const [targetIdx, setTargetIdx] = useState(0);
  const [need, setNeed] = useState<Partial<Record<ElementSym, number>>>({});
  const [score, setScore] = useState(0);
  const [streak, setStreak] = useState(0);
  const [timeLeft, setTimeLeft] = useState(PROFILES.kids.startTime);
  const [built, setBuilt] = useState(0);
  const [best, setBest] = useState(0);
  const [flash, setFlash] = useState<"good" | "bad" | "boom" | "">("");
  const [cause, setCause] = useState<EndCause>("time");

  const needRef = useRef(need);
  const builtRef = useRef(0);
  const capRef = useRef(prof.startCap);
  const speedRef = useRef(prof.startSpeed);
  useEffect(() => { needRef.current = need; }, [need]);
  useEffect(() => { builtRef.current = built; }, [built]);

  // Pick up the age group from the URL (?age=...), client-side only.
  useEffect(() => {
    const p = new URLSearchParams(window.location.search).get("age");
    if (p && p in PROFILES) setAge(p as AgeKey);
    const b = Number(localStorage.getItem(BEST_KEY) || 0);
    if (b) setBest(b);
  }, []);

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
    setBest((b) => {
      const nb = Math.max(b, score);
      localStorage.setItem(BEST_KEY, String(nb));
      return nb;
    });
  }, [score]);

  // Movement loop.
  useEffect(() => {
    if (phase !== "playing") return;
    let raf = 0;
    let last = performance.now();
    const step = (ts: number) => {
      const dt = Math.min(0.05, (ts - last) / 1000);
      last = ts;
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

  // Spawner - interval shrinks as the level rises.
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
      // Keep the field solvable: make sure required atoms are present after a catch.
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
  const fieldShadow =
    flash === "good" ? "inset 0 0 60px rgba(52,211,153,0.5)"
    : flash === "bad" ? "inset 0 0 60px rgba(239,68,68,0.55)"
    : flash === "boom" ? "inset 0 0 120px rgba(239,68,68,0.9)"
    : undefined;

  return (
    <main className="container" style={{ maxWidth: 820 }}>
      <style>{css}</style>

      <div className="row" style={{ justifyContent: "space-between" }}>
        <h1 style={{ margin: 0 }}>
          {"\u2697\uFE0F"} Potion Lab{" "}
          <span style={{ fontSize: 14, color: "#a78bfa", verticalAlign: "middle" }}>{prof.label} mode</span>
        </h1>
        <Link href="/arcade" className="muted" style={{ fontSize: 14 }}>{"\u2190"} Back to Arcade</Link>
      </div>

      {/* HUD */}
      <div className="row" style={{ justifyContent: "space-between", marginTop: 6 }}>
        <span style={{ fontWeight: 800 }}>{"\u2B50"} {score}</span>
        <span style={{ fontWeight: 800, color: "#a78bfa" }}>{"\u{1F9EA}"} Level {level}</span>
        <span className="muted">Best: {best}</span>
        <span style={{ fontWeight: 700, color: streak >= 3 ? "#fbbf24" : "var(--muted)" }}>
          {"\u{1F525}"} Streak {streak}
        </span>
      </div>
      <div style={{ height: 12, borderRadius: 8, background: "var(--panel-2)", overflow: "hidden", margin: "8px 0 4px" }}>
        <div style={{
          width: `${timePct}%`, height: "100%",
          background: timeLeft <= 6 ? "#ef4444" : "linear-gradient(90deg,#34d399,#60a5fa)",
          transition: "width 0.1s linear",
        }} />
      </div>

      {/* Target */}
      <div className="row" style={{
        justifyContent: "center", gap: 14, margin: "6px 0 10px", flexWrap: "wrap",
        background: "#ffffff", borderRadius: 14, padding: "10px 16px",
        border: "2px solid #dc2626",
      }}>
        <span style={{ fontWeight: 900, fontSize: 18, color: "#0b1020" }}>
          Make: {target.emoji} {target.name} <span style={{ color: "#dc2626" }}>({target.formula})</span>
        </span>
        <span className="row" style={{ gap: 6 }}>
          {slots.map((s, i) => (
            <span key={i} style={{
              width: 26, height: 26, borderRadius: "50%",
              display: "inline-flex", alignItems: "center", justifyContent: "center",
              fontSize: 13, fontWeight: 900,
              color: s.filled ? "#ffffff" : "#dc2626",
              background: s.filled ? "#dc2626" : "transparent",
              border: "2px solid #dc2626",
            }}>{s.sym}</span>
          ))}
        </span>
      </div>

      {/* Playfield */}
      <div className="potion-field" style={{ boxShadow: fieldShadow }}>
        {phase === "playing" && cells.map((a) => {
          if (a.kind === "atom") {
            return (
              <button key={a.id} onClick={() => clickCell(a)} title={ELEMENTS[a.sym as ElementSym].name}
                className="potion-atom" style={{ left: `${a.x}%`, top: `${a.y}%`, background: ELEMENTS[a.sym as ElementSym].color }}>
                {a.sym}
              </button>
            );
          }
          return (
            <button key={a.id} onClick={() => clickCell(a)}
              title={a.kind === "bomb" ? "Bomb - do not tap!" : "Bacteria - avoid!"}
              className={`potion-atom potion-hazard ${a.kind === "bomb" ? "is-bomb" : "is-germ"}`}
              style={{ left: `${a.x}%`, top: `${a.y}%` }}>
              {a.kind === "bomb" ? "\u{1F4A3}" : "\u{1F9A0}"}
            </button>
          );
        })}

        {phase === "intro" && (
          <div className="potion-overlay">
            <div style={{ fontSize: 54 }}>{"\u2697\uFE0F"}</div>
            <h2 style={{ margin: "4px 0" }}>Catch the atoms! <span style={{ color: "#a78bfa" }}>({prof.label})</span></h2>
            <p className="muted" style={{ maxWidth: 460, textAlign: "center" }}>
              Tap the atoms that match the recipe to build the molecule. Each one you
              build levels you up {"\u2014"} <b>faster atoms, more chaos!</b>
              <br />Avoid {"\u{1F9A0}"} <b>bacteria</b> (lose points)
              {prof.bombsFromLevel < 999 ? <> and never tap {"\u{1F4A3}"} <b>bombs</b> (game over)!</> : "."}
            </p>
            <button onClick={startGame} style={primaryBtn}>{"\u25B6"} Start</button>
          </div>
        )}

        {phase === "over" && (
          <div className="potion-overlay">
            <div style={{ fontSize: 54 }}>{cause === "bomb" ? "\u{1F4A5}" : (score >= best && score > 0 ? "\u{1F3C6}" : "\u{1F9EA}")}</div>
            <h2 style={{ margin: "4px 0" }}>{cause === "bomb" ? "Boom! You tapped a bomb!" : "Time\u2019s up!"}</h2>
            <p className="muted" style={{ textAlign: "center" }}>
              You reached <b style={{ color: "var(--text)" }}>Level {level}</b> with{" "}
              <b style={{ color: "var(--text)" }}>{score}</b> points.
              {score >= best && score > 0 ? " New best! \u{1F389}" : ` Best: ${best}`}
            </p>
            <button onClick={startGame} style={primaryBtn}>{"\u{1F501}"} Play again</button>
          </div>
        )}
      </div>

      <p className="muted" style={{ fontSize: 12, textAlign: "center", marginTop: 8 }}>
        Build a molecule for bonus points and +{prof.timePerMolecule}s. {"\u{1F9A0}"} = lose points
        {prof.bombsFromLevel < 999 ? <> {"\u00B7"} {"\u{1F4A3}"} = game over!</> : null}
      </p>
    </main>
  );
}

const primaryBtn: React.CSSProperties = {
  background: "#7c3aed", color: "#fff", padding: "10px 26px", fontWeight: 800, fontSize: 16,
};

const css = `
.potion-field {
  position: relative;
  height: 420px;
  border-radius: 18px;
  overflow: hidden;
  border: 1px solid var(--border);
  background:
    radial-gradient(120% 80% at 50% 0%, rgba(124,58,237,0.18), transparent 60%),
    linear-gradient(180deg, #0d1430, #0a0f24);
  transition: box-shadow 0.12s ease;
}
.potion-atom {
  position: absolute;
  width: 48px; height: 48px;
  transform: translate(-50%, -50%);
  border-radius: 50%;
  border: none;
  color: #0b1020;
  font-weight: 800; font-size: 16px;
  cursor: pointer;
  padding: 0;
  box-shadow: 0 4px 0 rgba(0,0,0,0.3), inset 0 -4px 8px rgba(0,0,0,0.15), inset 0 6px 8px rgba(255,255,255,0.35);
  animation: atom-in 0.2s ease;
  transition: transform 0.06s ease;
}
.potion-atom:hover { transform: translate(-50%, -50%) scale(1.12); }
.potion-atom:active { transform: translate(-50%, -50%) scale(0.9); }
.potion-hazard { font-size: 26px; }
.potion-hazard.is-germ { background: #16a34a; box-shadow: 0 4px 0 rgba(0,0,0,0.3), 0 0 0 3px rgba(34,197,94,0.4); animation: hazard-pulse 0.9s ease-in-out infinite; }
.potion-hazard.is-bomb { background: #111827; box-shadow: 0 4px 0 rgba(0,0,0,0.4), 0 0 0 3px rgba(239,68,68,0.6); animation: hazard-pulse 0.6s ease-in-out infinite; }
.potion-overlay {
  position: absolute; inset: 0;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 8px;
  background: rgba(8,12,28,0.74);
  backdrop-filter: blur(3px);
  text-align: center;
  padding: 20px;
}
@keyframes atom-in { from { transform: translate(-50%,-50%) scale(0.2); } to { transform: translate(-50%,-50%) scale(1); } }
@keyframes hazard-pulse {
  0%,100% { transform: translate(-50%,-50%) scale(1); }
  50% { transform: translate(-50%,-50%) scale(1.14); }
}
@media (prefers-reduced-motion: reduce) { .potion-atom, .potion-hazard { animation: none; } }
`;

"use client";

// Jeopardy! — Classic game show format with educational categories.
// 5 categories × 5 dollar values ($100–$500). Solo or vs-AI mode.
// Double Jeopardy: one random cell is secretly worth 2× (revealed on click).
// AI mode: AI buzzes in after a random 2–5 s delay with 70–85 % accuracy.

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

type Age = "kids" | "tween" | "teen" | "adult";
type Mode = "solo" | "ai";
type Phase = "idle" | "board" | "question" | "done";
type Result = "correct" | "wrong" | null;

type JQ = { q: string; options: string[]; answer: number };
type Cell = { answered: boolean; playerGot: boolean | null; doubleJeopardy: boolean };

const VALUES = [100, 200, 300, 400, 500] as const;

const CATEGORIES: Record<Age, string[]> = {
  kids:  ["Animals", "Colors & Shapes", "Math Fun", "The World", "Silly Science"],
  tween: ["History", "Science", "Math", "Geography", "Pop Culture"],
  teen:  ["World History", "Biology", "Algebra", "Literature", "Technology"],
  adult: ["Economics", "Philosophy", "Advanced Science", "Classic Literature", "World Politics"],
};

// QUESTIONS[age][catIdx][valIdx]  (catIdx 0-4, valIdx 0=$100 … 4=$500)
const QUESTIONS: Record<Age, JQ[][]> = {
  kids: [
    // Animals
    [
      { q: "This big gray animal has a trunk.",                            options: ["Lion",    "Elephant","Giraffe",  "Horse"],      answer: 1 },
      { q: "This animal says 'moo' and gives us milk.",                   options: ["Pig",     "Sheep",   "Cow",      "Chicken"],    answer: 2 },
      { q: "This black-and-white bird can't fly but loves to swim.",      options: ["Eagle",   "Parrot",  "Penguin",  "Flamingo"],   answer: 2 },
      { q: "This animal builds dams out of logs and mud.",                options: ["Otter",   "Beaver",  "Raccoon",  "Fox"],        answer: 1 },
      { q: "The fastest land animal on Earth.",                           options: ["Lion",    "Cheetah", "Leopard",  "Horse"],      answer: 1 },
    ],
    // Colors & Shapes
    [
      { q: "Mixing red and blue makes this color.",                       options: ["Green",   "Purple",  "Orange",   "Pink"],       answer: 1 },
      { q: "A shape with exactly 3 sides.",                               options: ["Square",  "Circle",  "Triangle", "Hexagon"],    answer: 2 },
      { q: "The color of a ripe banana.",                                 options: ["Red",     "Green",   "Blue",     "Yellow"],     answer: 3 },
      { q: "A shape with zero corners.",                                  options: ["Square",  "Triangle","Circle",   "Rectangle"],  answer: 2 },
      { q: "Mixing yellow and blue makes this color.",                    options: ["Orange",  "Green",   "Purple",   "Brown"],      answer: 1 },
    ],
    // Math Fun
    [
      { q: "3 + 4 = ?",                                                  options: ["6",       "7",       "8",        "9"],          answer: 1 },
      { q: "10 − 3 = ?",                                                  options: ["5",       "6",       "7",        "8"],          answer: 2 },
      { q: "2 × 5 = ?",                                                   options: ["7",       "8",       "10",       "12"],         answer: 2 },
      { q: "15 ÷ 3 = ?",                                                  options: ["3",       "4",       "5",        "6"],          answer: 2 },
      { q: "Half of 20 is…",                                              options: ["5",       "8",       "10",       "15"],         answer: 2 },
    ],
    // The World
    [
      { q: "The tallest mountain on Earth.",                              options: ["K2",      "Kilimanjaro","Everest","Denali"],    answer: 2 },
      { q: "The ocean on the west side of the USA.",                      options: ["Atlantic","Indian",  "Arctic",   "Pacific"],    answer: 3 },
      { q: "Kangaroos live on this continent.",                           options: ["Africa",  "Australia","Asia",    "Europe"],     answer: 1 },
      { q: "The largest country in the world by area.",                   options: ["China",   "USA",     "Russia",   "Canada"],     answer: 2 },
      { q: "The Amazon rainforest is on this continent.",                 options: ["Africa",  "Asia",    "S. America","N. America"],answer: 2 },
    ],
    // Silly Science
    [
      { q: "The planet closest to the Sun.",                              options: ["Earth",   "Venus",   "Mercury",  "Mars"],       answer: 2 },
      { q: "Plants need this from the Sun to make food.",                 options: ["Moonlight","Sunlight","Starlight","Firelight"], answer: 1 },
      { q: "Ice is water in this state.",                                 options: ["Gas",     "Liquid",  "Solid",    "Plasma"],     answer: 2 },
      { q: "This gas do we breathe in to stay alive.",                    options: ["CO₂",    "Nitrogen","Oxygen",   "Hydrogen"],   answer: 2 },
      { q: "A caterpillar turns into a…",                                 options: ["Spider",  "Butterfly","Beetle",  "Moth"],       answer: 1 },
    ],
  ],
  tween: [
    // History
    [
      { q: "Year the Titanic sank.",                                      options: ["1905","1912","1920","1898"],                    answer: 1 },
      { q: "First President of the United States.",                       options: ["Adams","Jefferson","Washington","Lincoln"],     answer: 2 },
      { q: "Ancient wonder: giant statue at this Greek island.",          options: ["Crete","Rhodes","Corfu","Delos"],               answer: 1 },
      { q: "The French Revolution began in this decade.",                 options: ["1760s","1770s","1780s","1790s"],                answer: 2 },
      { q: "Magellan's expedition was the first to…",                     options: ["Reach Americas","Circumnavigate globe","Sail Arctic","Map Africa"], answer: 1 },
    ],
    // Science
    [
      { q: "The powerhouse of the cell.",                                 options: ["Nucleus","Ribosome","Mitochondria","Vacuole"],  answer: 2 },
      { q: "Chemical symbol for gold.",                                   options: ["Go","Gd","Au","Ag"],                           answer: 2 },
      { q: "Gravity on Earth pulls at roughly…",                          options: ["5 m/s²","9.8 m/s²","15 m/s²","3.7 m/s²"],    answer: 1 },
      { q: "The layer of Earth we live on.",                              options: ["Mantle","Core","Crust","Magma"],               answer: 2 },
      { q: "Sound travels fastest through…",                              options: ["Vacuum","Air","Water","Steel"],                answer: 3 },
    ],
    // Math
    [
      { q: "7 × 8 = ?",                                                   options: ["54","56","62","48"],                           answer: 1 },
      { q: "The square root of 144.",                                     options: ["10","11","12","14"],                           answer: 2 },
      { q: "0.5 × 40 = ?",                                                options: ["10","15","20","25"],                           answer: 2 },
      { q: "30% of 200 = ?",                                              options: ["40","50","60","70"],                           answer: 2 },
      { q: "A prime number between 20 and 30.",                           options: ["21","23","25","27"],                           answer: 1 },
    ],
    // Geography
    [
      { q: "Capital of Japan.",                                           options: ["Beijing","Seoul","Bangkok","Tokyo"],           answer: 3 },
      { q: "The Nile River flows through this continent.",                options: ["Asia","Africa","Europe","Australia"],          answer: 1 },
      { q: "The smallest continent.",                                     options: ["Europe","Antarctica","Australia","S. America"],answer: 2 },
      { q: "Country shaped like a boot.",                                 options: ["Spain","Greece","Italy","Portugal"],           answer: 2 },
      { q: "The Great Barrier Reef is off the coast of…",                 options: ["USA","Brazil","Australia","S. Africa"],        answer: 2 },
    ],
    // Pop Culture
    [
      { q: "J.K. Rowling's famous wizard school.",                        options: ["Rivendell","Narnia","Hogwarts","Wakanda"],     answer: 2 },
      { q: "'Frozen' features a snow queen named…",                       options: ["Anna","Elsa","Kristoff","Olaf"],              answer: 1 },
      { q: "Minecraft was created by…",                                   options: ["Valve","Mojang","Nintendo","EA"],             answer: 1 },
      { q: "The Avengers assemble in this movie universe.",               options: ["DC","Marvel","Dark Horse","Image"],           answer: 1 },
      { q: "Taylor Swift's debut album came out in…",                     options: ["2004","2006","2008","2010"],                  answer: 1 },
    ],
  ],
  teen: [
    // World History
    [
      { q: "Treaty that ended World War I.",                              options: ["Treaty of Paris","Treaty of Versailles","Treaty of Vienna","Treaty of Berlin"], answer: 1 },
      { q: "The Cold War was primarily between the US and…",              options: ["China","Germany","USSR","Japan"],             answer: 2 },
      { q: "The Renaissance began in this country.",                      options: ["France","England","Spain","Italy"],           answer: 3 },
      { q: "Napoleon was exiled to this island.",                         options: ["Corsica","Elba","Malta","St. Helena"],        answer: 3 },
      { q: "The Berlin Wall fell in…",                                    options: ["1987","1989","1991","1993"],                  answer: 1 },
    ],
    // Biology
    [
      { q: "Plants make food via this process.",                          options: ["Respiration","Photosynthesis","Osmosis","Digestion"],  answer: 1 },
      { q: "DNA is found in this organelle.",                             options: ["Ribosome","Mitochondria","Nucleus","Golgi body"],      answer: 2 },
      { q: "The basic unit of life.",                                     options: ["Tissue","Organ","Cell","Atom"],               answer: 2 },
      { q: "Red blood cells primarily transport…",                        options: ["CO₂ only","O₂ and CO₂","N₂","O₂ only"],      answer: 1 },
      { q: "Meiosis produces cells with how many chromosomes?",           options: ["46","23","92","48"],                          answer: 1 },
    ],
    // Algebra
    [
      { q: "If 2x + 4 = 10, then x = ?",                                 options: ["2","3","4","5"],                              answer: 1 },
      { q: "The slope of y = 3x − 5.",                                    options: ["-5","0","3","5"],                             answer: 2 },
      { q: "x² − 9 = 0 → x = ?",                                         options: ["±2","±3","±4","±9"],                          answer: 1 },
      { q: "Expand (x + 3)².",                                            options: ["x²+6","x²+9","x²+6x+9","x²+3x+9"],          answer: 2 },
      { q: "Vertex form of a parabola.",                                  options: ["y=mx+b","y=a(x−h)²+k","y=ax²+bx+c","y=x²"], answer: 1 },
    ],
    // Literature
    [
      { q: "Author of '1984'.",                                           options: ["Huxley","Bradbury","Orwell","H.G. Wells"],    answer: 2 },
      { q: "Shakespeare's tragedy about a Danish prince.",                options: ["Macbeth","Othello","Hamlet","King Lear"],     answer: 2 },
      { q: "'To Kill a Mockingbird' author.",                             options: ["T. Morrison","Harper Lee","M. Angelou","F. O'Connor"], answer: 1 },
      { q: "The Great Gatsby is set in the…",                             options: ["1910s","1920s","1930s","1940s"],              answer: 1 },
      { q: "Romeo and Juliet's rival families are named…",               options: ["Capulet & Montague","Darcy & Bennet","Lear & Edgar","Hamlet & Ophelia"], answer: 0 },
    ],
    // Technology
    [
      { q: "HTML stands for…",                                            options: ["High Text Markup Language","HyperText Markup Language","HyperText Making Language","High Transfer Markup Language"], answer: 1 },
      { q: "Inventor of the World Wide Web.",                             options: ["Bill Gates","Steve Jobs","Tim Berners-Lee","Linus Torvalds"], answer: 2 },
      { q: "Binary uses how many distinct digits?",                       options: ["2","8","10","16"],                            answer: 0 },
      { q: "Which company makes the iPhone?",                             options: ["Google","Samsung","Apple","Microsoft"],       answer: 2 },
      { q: "An algorithm is…",                                            options: ["A computer brand","A step-by-step procedure","A programming language","A type of network"], answer: 1 },
    ],
  ],
  adult: [
    // Economics
    [
      { q: "GDP stands for…",                                             options: ["Gross Domestic Product","General Debt Protocol","Gross Daily Profit","Global Development Plan"], answer: 0 },
      { q: "The Phillips Curve describes a trade-off between…",           options: ["Growth & debt","Inflation & unemployment","Trade & GDP","Interest & exchange"], answer: 1 },
      { q: "Keynesian economics advocates government spending during…",   options: ["Booms","Recessions","Both equally","Never"],  answer: 1 },
      { q: "Comparative advantage means producing with lower…",          options: ["Absolute superiority","Opportunity cost","Labor cost","Tariffs"], answer: 1 },
      { q: "The Federal Reserve's dual mandate covers…",                 options: ["Growth & exports","Price stability & employment","Trade balance & growth","Debt & savings"], answer: 1 },
    ],
    // Philosophy
    [
      { q: "Descartes: 'I think, therefore…'",                           options: ["I dream","I am","I know","I exist in doubt"],  answer: 1 },
      { q: "Utilitarianism maximizes…",                                   options: ["Individual rights","Total happiness","Virtue","Duty"], answer: 1 },
      { q: "Kant's Categorical Imperative is a theory of…",              options: ["Aesthetics","Ethics/deontology","Metaphysics","Epistemology"], answer: 1 },
      { q: "Plato's cave allegory illustrates reality vs…",              options: ["The state","Perception","The forms","B and C"], answer: 3 },
      { q: "Nietzsche declared 'God is dead' in…",                       options: ["Beyond Good and Evil","Birth of Tragedy","The Gay Science","Thus Spoke Zarathustra"], answer: 2 },
    ],
    // Advanced Science
    [
      { q: "Heisenberg's principle limits knowing simultaneously…",      options: ["Mass & charge","Position & momentum","Energy & time","Spin & color"], answer: 1 },
      { q: "General relativity equates gravity with…",                   options: ["Quantum force","Curvature of spacetime","EM field","Dark energy"], answer: 1 },
      { q: "CRISPR-Cas9 is used for…",                                   options: ["Gene editing","Drug synthesis","Protein folding","Cell imaging"], answer: 0 },
      { q: "The strong nuclear force is mediated by…",                   options: ["Photons","W/Z bosons","Gluons","Gravitons"],   answer: 2 },
      { q: "In thermodynamics, entropy measures…",                       options: ["Temperature","Disorder/randomness","Energy","Pressure"], answer: 1 },
    ],
    // Classic Literature
    [
      { q: "Author of 'War and Peace'.",                                  options: ["Dostoevsky","Chekhov","Pushkin","Tolstoy"],   answer: 3 },
      { q: "'Moby Dick' was written by…",                                 options: ["Hawthorne","Melville","Poe","Twain"],         answer: 1 },
      { q: "Dante's Inferno is the first part of the…",                  options: ["Odyssey","Aeneid","Divine Comedy","Canterbury Tales"], answer: 2 },
      { q: "'Pride and Prejudice' author.",                               options: ["C. Brontë","George Eliot","Jane Austen","E. Brontë"], answer: 2 },
      { q: "Don Quixote was written in…",                                 options: ["French","Italian","Portuguese","Spanish"],    answer: 3 },
    ],
    // World Politics
    [
      { q: "The UN Security Council has how many permanent members?",    options: ["3","4","5","6"],                               answer: 2 },
      { q: "Bretton Woods institutions include…",                        options: ["UN & NATO","WTO & OPEC","IMF & World Bank","G7 & G20"], answer: 2 },
      { q: "Realpolitik is most associated with…",                       options: ["Woodrow Wilson","Otto von Bismarck","Abraham Lincoln","Napoleon Bonaparte"], answer: 1 },
      { q: "The Nuclear Non-Proliferation Treaty aims to…",              options: ["Promote nuclear energy","Limit spread of nuclear weapons","Regulate trade","Protect environment"], answer: 1 },
      { q: "The EU common currency is the…",                             options: ["Pound","Franc","Euro","Drachma"],              answer: 2 },
    ],
  ],
};

// ── helpers ──────────────────────────────────────────────────────────────────

function makeBoard(djCat: number, djVal: number): Cell[][] {
  return Array.from({ length: 5 }, (_, ci) =>
    Array.from({ length: 5 }, (_, vi) => ({
      answered: false,
      playerGot: null,
      doubleJeopardy: ci === djCat && vi === djVal,
    }))
  );
}

function aiAccuracy(age: Age) {
  return { kids: 0.70, tween: 0.75, teen: 0.80, adult: 0.85 }[age];
}

// ── component ─────────────────────────────────────────────────────────────────

export default function JeopardyGame() {
  const [age,  setAge]  = useState<Age>("tween");
  const [mode, setMode] = useState<Mode>("solo");
  const [phase, setPhase] = useState<Phase>("idle");
  const [board, setBoard] = useState<Cell[][]>([]);
  const [score, setScore] = useState(0);
  const [aiScore, setAiScore] = useState(0);
  const [current, setCurrent] = useState<{ cat: number; val: number } | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [result, setResult] = useState<Result>(null);
  const [totalAnswered, setTotalAnswered] = useState(0);

  // mutable refs — avoid stale-closure issues inside setTimeout callbacks
  const aiTimerRef    = useRef<ReturnType<typeof setTimeout> | null>(null);
  const answeredRef   = useRef(false);   // true once player OR ai has answered the current cell
  const scoreRef      = useRef(0);
  const aiScoreRef    = useRef(0);
  const totalRef      = useRef(0);
  const boardRef      = useRef<Cell[][]>([]);

  useEffect(() => {
    const q = new URLSearchParams(window.location.search).get("age");
    if (q === "kids" || q === "tween" || q === "teen" || q === "adult") setAge(q as Age);
  }, []);

  // Keep refs in sync with state
  useEffect(() => { scoreRef.current   = score; },   [score]);
  useEffect(() => { aiScoreRef.current = aiScore; }, [aiScore]);
  useEffect(() => { totalRef.current   = totalAnswered; }, [totalAnswered]);
  useEffect(() => { boardRef.current   = board; }, [board]);

  const start = () => {
    if (aiTimerRef.current) clearTimeout(aiTimerRef.current);
    const djCat = Math.floor(Math.random() * 5);
    const djVal = Math.floor(Math.random() * 5);
    const newBoard = makeBoard(djCat, djVal);
    setBoard(newBoard);
    boardRef.current = newBoard;
    setScore(0); setAiScore(0);
    scoreRef.current = 0; aiScoreRef.current = 0;
    setCurrent(null); setFeedback(null); setResult(null);
    setTotalAnswered(0); totalRef.current = 0;
    setPhase("board");
  };

  const selectCell = (cat: number, val: number) => {
    if (!boardRef.current[cat]?.[val] || boardRef.current[cat][val].answered) return;
    if (aiTimerRef.current) clearTimeout(aiTimerRef.current);
    answeredRef.current = false;
    setCurrent({ cat, val });
    setFeedback(null);
    setResult(null);
    setPhase("question");

    if (mode === "ai") {
      const delay = 2000 + Math.random() * 3000; // 2–5 s
      aiTimerRef.current = setTimeout(() => {
        if (answeredRef.current) return;
        answeredRef.current = true;
        const cell = boardRef.current[cat]?.[val];
        if (!cell || cell.answered) return;
        const pts = VALUES[val] * (cell.doubleJeopardy ? 2 : 1);
        const correct = Math.random() < aiAccuracy(age);
        if (correct) {
          const ns = aiScoreRef.current + pts;
          aiScoreRef.current = ns;
          setAiScore(ns);
          setFeedback(`🤖 AI buzzed in first — Correct! AI +$${pts}`);
        } else {
          const pen = pts / 2;
          const ns = aiScoreRef.current - pen;
          aiScoreRef.current = ns;
          setAiScore(ns);
          setFeedback(`🤖 AI buzzed in — Wrong! AI −$${pen}`);
        }
        markAnswered(cat, val, null);
      }, delay);
    }
  };

  const markAnswered = (cat: number, val: number, playerGot: boolean | null) => {
    setBoard((prev) => {
      const next = prev.map((col) => col.map((c) => ({ ...c })));
      if (next[cat]?.[val]) next[cat][val] = { ...next[cat][val], answered: true, playerGot };
      boardRef.current = next;
      return next;
    });
    const newTotal = totalRef.current + 1;
    totalRef.current = newTotal;
    setTotalAnswered(newTotal);
    setTimeout(() => {
      setCurrent(null);
      setFeedback(null);
      setResult(null);
      setPhase(newTotal >= 25 ? "done" : "board");
    }, 1800);
  };

  const playerPick = (optIdx: number) => {
    if (!current || answeredRef.current) return;
    answeredRef.current = true;
    if (aiTimerRef.current) clearTimeout(aiTimerRef.current);

    const { cat, val } = current;
    const q = QUESTIONS[age][cat][val];
    const cell = boardRef.current[cat]?.[val];
    if (!cell) return;
    const pts = VALUES[val] * (cell.doubleJeopardy ? 2 : 1);
    const correct = optIdx === q.answer;

    if (correct) {
      const ns = scoreRef.current + pts;
      scoreRef.current = ns;
      setScore(ns);
      setResult("correct");
      setFeedback(`✓ Correct! +$${pts}${cell.doubleJeopardy ? " (Double Jeopardy! ⚡)" : ""}`);
      markAnswered(cat, val, true);
    } else {
      const pen = Math.floor(pts / 2);
      const ns = scoreRef.current - pen;
      scoreRef.current = ns;
      setScore(ns);
      setResult("wrong");
      setFeedback(`✗ Wrong — "${q.options[q.answer]}" was correct. −$${pen}`);
      markAnswered(cat, val, false);
    }
  };

  useEffect(() => () => { if (aiTimerRef.current) clearTimeout(aiTimerRef.current); }, []);

  // ── derived ──
  const categories = CATEGORIES[age];
  const currentQ   = current ? QUESTIONS[age][current.cat][current.val] : null;
  const currentCell = current ? boardRef.current[current.cat]?.[current.val] : null;
  const displayPts  = current ? VALUES[current.val] * (currentCell?.doubleJeopardy ? 2 : 1) : 0;

  return (
    <main className="container" style={{ maxWidth: 860, paddingBottom: 48 }}>
      <style>{`
        @keyframes glowGreen {
          0%   { box-shadow: 0 0 0 0 rgba(52,211,153,0); }
          40%  { box-shadow: 0 0 32px 12px rgba(52,211,153,0.9); }
          100% { box-shadow: 0 0 0 0 rgba(52,211,153,0); }
        }
        @keyframes glowRed {
          0%   { box-shadow: 0 0 0 0 rgba(248,113,113,0); }
          40%  { box-shadow: 0 0 32px 12px rgba(248,113,113,0.9); }
          100% { box-shadow: 0 0 0 0 rgba(248,113,113,0); }
        }
        @keyframes djPop {
          0%   { transform: scale(1)    rotate(0deg); }
          30%  { transform: scale(1.22) rotate(-3deg); }
          60%  { transform: scale(1.18) rotate(3deg); }
          100% { transform: scale(1)    rotate(0deg); }
        }
        @keyframes cellFadeIn {
          from { opacity: 0; transform: scale(0.92); }
          to   { opacity: 1; transform: scale(1); }
        }
        .glow-correct { animation: glowGreen 0.9s ease-out forwards; }
        .glow-wrong   { animation: glowRed   0.9s ease-out forwards; }
        .dj-badge     { animation: djPop 0.55s ease-out; display: inline-block; }
        .question-card { animation: cellFadeIn 0.18s ease-out; }
        .jeopardy-btn:not(:disabled):hover {
          background: #2563eb !important;
          transform: scale(1.04);
          transition: transform 0.12s, background 0.12s;
        }
        .opt-btn:not(:disabled):hover {
          border-color: #ffd700 !important;
          background: #1e2a4a !important;
        }
      `}</style>

      {/* ── Header ── */}
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap", marginBottom: 4 }}>
        <h1 style={{ margin: 0, color: "#ffd700", textShadow: "0 2px 8px rgba(0,0,0,0.55)" }}>
          📺 Jeopardy!
        </h1>
        <Link href="/arcade" style={{ marginLeft: "auto", color: "#94a3b8" }}>← Arcade</Link>
      </div>
      <p className="muted" style={{ marginBottom: 16 }}>
        Pick a clue, answer in &ldquo;What is…?&rdquo; form. One cell hides Double Jeopardy (2×). Wrong = −½ pts.
      </p>

      {/* ── Selectors ── */}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 16 }}>
        {(["kids", "tween", "teen", "adult"] as Age[]).map((a) => (
          <button key={a} onClick={() => { setAge(a); setPhase("idle"); }}
            disabled={phase === "board" || phase === "question"}
            style={{ opacity: age === a ? 1 : 0.5 }}>
            {a}
          </button>
        ))}
        <span style={{ width: 1, background: "#334155", alignSelf: "stretch", margin: "0 4px" }} />
        <button onClick={() => { setMode("solo"); setPhase("idle"); }}
          disabled={phase === "board" || phase === "question"}
          style={{ opacity: mode === "solo" ? 1 : 0.5 }}>Solo</button>
        <button onClick={() => { setMode("ai"); setPhase("idle"); }}
          disabled={phase === "board" || phase === "question"}
          style={{ opacity: mode === "ai" ? 1 : 0.5 }}>vs AI 🤖</button>
      </div>

      {/* ── IDLE ── */}
      {phase === "idle" && (
        <div style={{ textAlign: "center", padding: 48 }}>
          <div style={{ fontSize: 60, marginBottom: 12 }}>🎬</div>
          <h2 style={{ color: "#ffd700", marginBottom: 8 }}>Ready to play?</h2>
          <p className="muted" style={{ marginBottom: 28 }}>
            {mode === "ai"
              ? "The AI will buzz in 2–5 s after you open a clue — beat it!"
              : "Answer all 25 clues for the highest score possible."}
          </p>
          <button onClick={start}
            style={{ background: "#1e40af", color: "#ffd700", padding: "14px 36px", fontSize: 20, fontWeight: 700, borderRadius: 12, border: "2px solid #ffd700", cursor: "pointer" }}>
            ▶ Start Game
          </button>
        </div>
      )}

      {/* ── BOARD ── */}
      {(phase === "board" || phase === "question") && (
        <>
          {/* Scoreboard */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
            <span style={{ fontWeight: 700, fontSize: 18, color: "#34d399" }}>
              You: ${score.toLocaleString()}
            </span>
            <span style={{ color: "#64748b", fontSize: 13 }}>
              {board.flatMap((c) => c).filter((c) => c.answered).length}/25 answered
            </span>
            {mode === "ai" && (
              <span style={{ fontWeight: 700, fontSize: 18, color: "#f87171" }}>
                AI: ${aiScore.toLocaleString()}
              </span>
            )}
          </div>

          {/* Board grid */}
          <div style={{
            display: "grid",
            gridTemplateColumns: "repeat(5, 1fr)",
            gap: 5,
            background: "#07111f",
            padding: 5,
            borderRadius: 12,
            border: "2px solid #1e3a8a",
            opacity: phase === "question" ? 0.35 : 1,
            transition: "opacity 0.2s",
            pointerEvents: phase === "question" ? "none" : "auto",
          }}>
            {/* Category headers */}
            {categories.map((cat, ci) => (
              <div key={`cat-${ci}`} style={{
                background: "#0f2060",
                color: "#ffd700",
                fontWeight: 800,
                padding: "12px 4px",
                textAlign: "center",
                fontSize: 11,
                letterSpacing: "0.4px",
                textTransform: "uppercase",
                borderRadius: 5,
                minHeight: 54,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}>
                {cat}
              </div>
            ))}

            {/* Question cells — row-major (valIdx outer, catIdx inner) */}
            {VALUES.flatMap((val, vi) =>
              Array.from({ length: 5 }, (_, ci) => {
                const cell = board[ci]?.[vi];
                if (!cell) return null;
                return (
                  <button
                    key={`${ci}-${vi}`}
                    className="jeopardy-btn"
                    onClick={() => phase === "board" && selectCell(ci, vi)}
                    disabled={cell.answered || phase === "question"}
                    style={{
                      background: cell.answered ? "#111827" : "#1e3a8a",
                      color: cell.answered ? "#334155" : "#ffd700",
                      fontWeight: 800,
                      fontSize: cell.answered ? 16 : 22,
                      padding: "18px 4px",
                      textAlign: "center",
                      borderRadius: 5,
                      border: 0,
                      cursor: cell.answered ? "default" : "pointer",
                      minHeight: 62,
                      transition: "background 0.15s",
                    }}
                  >
                    {cell.answered
                      ? (cell.playerGot === true ? "✓" : cell.playerGot === false ? "✗" : "—")
                      : `$${val}`}
                  </button>
                );
              })
            )}
          </div>
        </>
      )}

      {/* ── QUESTION OVERLAY ── */}
      {phase === "question" && currentQ && current && (
        <div style={{
          position: "fixed",
          inset: 0,
          background: "rgba(0,0,0,0.72)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          zIndex: 50,
          padding: 16,
        }}>
          <div
            className={`question-card${result === "correct" ? " glow-correct" : result === "wrong" ? " glow-wrong" : ""}`}
            style={{
              background: "#0f2060",
              border: `3px solid ${currentCell?.doubleJeopardy ? "#ffd700" : "#1e3a8a"}`,
              borderRadius: 18,
              padding: "28px 28px 32px",
              maxWidth: 560,
              width: "100%",
              boxSizing: "border-box",
            }}
          >
            {/* Value / DJ badge */}
            <div style={{ textAlign: "center", marginBottom: 14 }}>
              {currentCell?.doubleJeopardy && (
                <div className="dj-badge" style={{ color: "#ffd700", fontWeight: 900, fontSize: 15, letterSpacing: 2, marginBottom: 6 }}>
                  ⚡ DOUBLE JEOPARDY! ⚡
                </div>
              )}
              <span style={{ background: "#1e3a8a", color: "#ffd700", fontWeight: 800, padding: "6px 22px", borderRadius: 8, fontSize: 22 }}>
                ${displayPts.toLocaleString()}
              </span>
            </div>

            {/* Category label */}
            <div style={{ textAlign: "center", color: "#64748b", fontSize: 11, textTransform: "uppercase", letterSpacing: 1, marginBottom: 16 }}>
              {categories[current.cat]}
            </div>

            {/* Clue */}
            <div style={{
              background: "#1e3a8a",
              borderRadius: 10,
              padding: "20px 24px",
              textAlign: "center",
              fontSize: 19,
              fontWeight: 700,
              color: "#fff",
              marginBottom: 22,
              lineHeight: 1.4,
            }}>
              {currentQ.q}
            </div>

            {/* Options in "What is X?" format */}
            <div style={{ display: "grid", gap: 10 }}>
              {currentQ.options.map((opt, i) => (
                <button
                  key={i}
                  className="opt-btn"
                  onClick={() => playerPick(i)}
                  disabled={answeredRef.current}
                  style={{
                    background: "#0a1628",
                    color: "#e2e8f0",
                    border: "2px solid #1e40af",
                    borderRadius: 10,
                    padding: "12px 20px",
                    fontSize: 15,
                    textAlign: "left",
                    cursor: answeredRef.current ? "default" : "pointer",
                    opacity: answeredRef.current ? 0.5 : 1,
                  }}
                >
                  <span style={{ color: "#ffd700", fontWeight: 700 }}>What is </span>{opt}?
                </button>
              ))}
            </div>

            {/* Feedback */}
            {feedback && (
              <div style={{
                marginTop: 16,
                padding: "12px 16px",
                borderRadius: 8,
                background: result === "correct"
                  ? "rgba(52,211,153,0.13)"
                  : result === "wrong"
                  ? "rgba(248,113,113,0.13)"
                  : "rgba(148,163,184,0.09)",
                color: result === "correct" ? "#34d399" : result === "wrong" ? "#f87171" : "#cbd5e1",
                fontWeight: 600,
                fontSize: 14,
              }}>
                {feedback}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── DONE ── */}
      {phase === "done" && (
        <div className="card" style={{ textAlign: "center", padding: 40 }}>
          {mode === "ai" ? (
            <>
              <div style={{ fontSize: 56, marginBottom: 12 }}>
                {score > aiScore ? "🏆" : score < aiScore ? "🤖" : "🤝"}
              </div>
              <h2 style={{ color: "#ffd700" }}>
                {score > aiScore ? "You beat the AI!" : score < aiScore ? "AI wins this round!" : "It's a tie!"}
              </h2>
              <p className="muted">
                Your score: <strong style={{ color: "#34d399" }}>${score.toLocaleString()}</strong>
                &ensp;·&ensp;
                AI score: <strong style={{ color: "#f87171" }}>${aiScore.toLocaleString()}</strong>
              </p>
            </>
          ) : (
            <>
              <div style={{ fontSize: 56, marginBottom: 12 }}>
                {score >= 1500 ? "🌟" : score >= 900 ? "🎉" : score >= 400 ? "👍" : "💪"}
              </div>
              <h2 style={{ color: "#ffd700" }}>Board Complete!</h2>
              <p className="muted">
                Final score: <strong style={{ color: "#34d399", fontSize: 22 }}>${score.toLocaleString()}</strong>
              </p>
              <p className="muted" style={{ fontSize: 13 }}>
                {score >= 1500 ? "Outstanding — Jeopardy champion!" : score >= 900 ? "Excellent performance!" : score >= 400 ? "Good effort — try again for more?" : "Keep studying — you'll get there!"}
              </p>
            </>
          )}
          <button onClick={start}
            style={{ marginTop: 20, background: "#1e40af", color: "#ffd700", padding: "12px 32px", fontSize: 18, fontWeight: 700, borderRadius: 10, border: "2px solid #ffd700", cursor: "pointer" }}>
            Play Again
          </button>
        </div>
      )}
    </main>
  );
}

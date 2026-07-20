"use client";

// Creature Catch — Pokémon-inspired educational catching game.
// 12 Knowledge Creatures appear one by one. Answer questions to catch them.
// 3 wrong answers per creature = it escapes. Catch all 12 to win!

import Link from "next/link";
import { useEffect, useState } from "react";

type Age = "kids" | "tween" | "teen" | "adult";
type Q = { prompt: string; options: string[]; answer: number };

const CREATURES = [
  { emoji: "🦊", name: "Foxie",    subject: "Math",       color: "#ea580c" },
  { emoji: "🐉", name: "Drakon",   subject: "Science",    color: "#16a34a" },
  { emoji: "🦋", name: "Fluttra",  subject: "Reading",    color: "#ec4899" },
  { emoji: "🐬", name: "Waverly",  subject: "History",    color: "#0ea5e9" },
  { emoji: "🦅", name: "Skywing",  subject: "Geography",  color: "#7c3aed" },
  { emoji: "🐙", name: "Inkster",  subject: "Technology", color: "#1e40af" },
  { emoji: "🦁", name: "Mane",     subject: "Biology",    color: "#b45309" },
  { emoji: "🐢", name: "Shellby",  subject: "Art",        color: "#0f766e" },
  { emoji: "🐸", name: "Croak",    subject: "Music",      color: "#15803d" },
  { emoji: "🦄", name: "Gleam",    subject: "Space",      color: "#9333ea" },
  { emoji: "🐝", name: "Buzz",     subject: "Economics",  color: "#ca8a04" },
  { emoji: "🐳", name: "Breezer",  subject: "Language",   color: "#0369a1" },
];

const QUESTIONS: Record<string, Record<Age, Q[]>> = {
  Math: {
    kids:  [{ prompt:"3+3=?", options:["5","6","7","8"], answer:1 },{ prompt:"2×4=?", options:["6","7","8","9"], answer:2 }],
    tween: [{ prompt:"7×8=?", options:["54","56","58","64"], answer:1 },{ prompt:"√49=?", options:["6","7","8","9"], answer:1 }],
    teen:  [{ prompt:"3x+6=15, x=?", options:["2","3","4","5"], answer:1 },{ prompt:"log₂8=?", options:["2","3","4","8"], answer:1 }],
    adult: [{ prompt:"∫x dx=?", options:["x+C","x²/2+C","2x+C","x²+C"], answer:1 },{ prompt:"e^(iπ)+1=?", options:["0","1","2","-1"], answer:0 }],
  },
  Science: {
    kids:  [{ prompt:"Plants need this from the Sun.", options:["Darkness","Sunlight","Rain","Wind"], answer:1 },{ prompt:"Ice is water in what state?", options:["Gas","Liquid","Solid","Plasma"], answer:2 }],
    tween: [{ prompt:"Powerhouse of the cell?", options:["Nucleus","Ribosome","Mitochondria","Vacuole"], answer:2 },{ prompt:"H₂O is?", options:["Salt","Water","Air","Sugar"], answer:1 }],
    teen:  [{ prompt:"pH below 7 is?", options:["Neutral","Basic","Acidic","Alkaline"], answer:2 },{ prompt:"DNA carries?", options:["Energy","Genetic info","Oxygen","Enzymes"], answer:1 }],
    adult: [{ prompt:"Entropy tends to?", options:["Decrease","Stay constant","Increase","Oscillate"], answer:2 },{ prompt:"Heisenberg: position and?", options:["Energy","Momentum","Speed","Mass"], answer:1 }],
  },
  Reading: {
    kids:  [{ prompt:"A synonym for 'happy' is?", options:["Sad","Joyful","Angry","Tired"], answer:1 },{ prompt:"A noun names a?", options:["Action","Place/person","Color","Verb"], answer:1 }],
    tween: [{ prompt:"A metaphor is?", options:["Direct comparison without like/as","Rhyme","Exaggeration","Sound word"], answer:0 },{ prompt:"The theme is the story's?", options:["Plot","Setting","Message","Characters"], answer:2 }],
    teen:  [{ prompt:"Dramatic irony: reader knows something the?", options:["Author hides","Character doesn't","Narrator shows","Villain reveals"], answer:1 },{ prompt:"A foil character?", options:["Replaces hero","Contrasts the main character","Adds comedy","Narrates story"], answer:1 }],
    adult: [{ prompt:"Deconstruction challenges?", options:["Genre","Plot","Fixed meaning","Style"], answer:2 },{ prompt:"Stream of consciousness depicts?", options:["External events","Inner thought flow","Dialogue","Description"], answer:1 }],
  },
  History: {
    kids:  [{ prompt:"First US President?", options:["Lincoln","Washington","Jefferson","Adams"], answer:1 },{ prompt:"Great Wall is in?", options:["India","Egypt","China","Japan"], answer:2 }],
    tween: [{ prompt:"Year Titanic sank?", options:["1905","1912","1920","1898"], answer:1 },{ prompt:"French Revolution began in?", options:["1769","1779","1789","1799"], answer:2 }],
    teen:  [{ prompt:"Cold War was between US and?", options:["China","UK","Soviet Union","Germany"], answer:2 },{ prompt:"Year moon landing?", options:["1967","1969","1971","1973"], answer:1 }],
    adult: [{ prompt:"Keynes advocated for?", options:["Austerity","Free markets","Government spending","Gold standard"], answer:2 },{ prompt:"Bretton Woods created?", options:["EU","IMF/World Bank","NATO","WTO"], answer:1 }],
  },
  Geography: {
    kids:  [{ prompt:"Largest ocean?", options:["Atlantic","Indian","Arctic","Pacific"], answer:3 },{ prompt:"Country with Eiffel Tower?", options:["Italy","Spain","France","Germany"], answer:2 }],
    tween: [{ prompt:"Capital of Japan?", options:["Beijing","Seoul","Tokyo","Bangkok"], answer:2 },{ prompt:"Longest river?", options:["Amazon","Mississippi","Nile","Yangtze"], answer:2 }],
    teen:  [{ prompt:"Largest country by area?", options:["China","USA","Russia","Canada"], answer:2 },{ prompt:"Country with most people?", options:["China","India","USA","Indonesia"], answer:1 }],
    adult: [{ prompt:"Suez Canal connects?", options:["Pacific-Atlantic","Red Sea-Med","Black-Caspian","Baltic-North"], answer:1 },{ prompt:"Mercator projection distorts?", options:["Colors","Distances near poles","Coastlines","Longitude"], answer:1 }],
  },
  Technology: {
    kids:  [{ prompt:"CPU stands for?", options:["Central Power Unit","Central Processing Unit","Computer Print Unit","Core Program Unit"], answer:1 },{ prompt:"www stands for?", options:["World Wide Web","Wide World Web","Web World Wide","World Web Wide"], answer:0 }],
    tween: [{ prompt:"HTTP is for?", options:["Email","Web pages","Printing","Storage"], answer:1 },{ prompt:"RAM is?", options:["Permanent storage","Temporary memory","A processor","A network"], answer:1 }],
    teen:  [{ prompt:"Binary: 1010 in decimal?", options:["8","9","10","12"], answer:2 },{ prompt:"Big-O of linear search?", options:["O(1)","O(log n)","O(n)","O(n²)"], answer:2 }],
    adult: [{ prompt:"TCP/IP operates at which layer?", options:["Application","Transport","Network","All"], answer:2 },{ prompt:"RSA is used for?", options:["Compression","Hashing","Public-key encryption","Routing"], answer:2 }],
  },
  Biology: {
    kids:  [{ prompt:"How many legs does a spider have?", options:["6","7","8","10"], answer:2 },{ prompt:"Which is a mammal?", options:["Salmon","Eagle","Dolphin","Ant"], answer:2 }],
    tween: [{ prompt:"Photosynthesis takes place in?", options:["Mitochondria","Nucleus","Chloroplasts","Ribosome"], answer:2 },{ prompt:"Blood type with no antigens?", options:["A","B","AB","O"], answer:3 }],
    teen:  [{ prompt:"Mitosis produces?", options:["4 haploid","2 haploid","2 diploid","4 diploid"], answer:2 },{ prompt:"Enzyme that copies DNA?", options:["RNA polymerase","DNA polymerase","Helicase","Ligase"], answer:1 }],
    adult: [{ prompt:"CRISPR edits?", options:["Proteins","Genes","Cells","Ribosomes"], answer:1 },{ prompt:"Action potential travels via?", options:["Dendrites","Axon","Soma","Synapse"], answer:1 }],
  },
  Art: {
    kids:  [{ prompt:"Mona Lisa was painted by?", options:["Picasso","Da Vinci","Rembrandt","Monet"], answer:1 },{ prompt:"Mixing red+yellow makes?", options:["Purple","Orange","Green","Brown"], answer:1 }],
    tween: [{ prompt:"Impressionism started in?", options:["Germany","USA","France","Italy"], answer:2 },{ prompt:"Cubism was pioneered by?", options:["Monet","Picasso","Rembrandt","Dali"], answer:1 }],
    teen:  [{ prompt:"Renaissance began in?", options:["France","Spain","Italy","England"], answer:2 },{ prompt:"Starry Night is by?", options:["Monet","Van Gogh","Dali","Rembrandt"], answer:1 }],
    adult: [{ prompt:"Bauhaus was a?", options:["Museum","Art+design school","Painting style","French movement"], answer:1 },{ prompt:"Chiaroscuro is?", options:["Sculpture technique","Light-dark contrast","Color theory","Pointillism"], answer:1 }],
  },
  Music: {
    kids:  [{ prompt:"How many strings does a guitar usually have?", options:["4","5","6","7"], answer:2 },{ prompt:"Musical notes go A B C D E F…", options:["H","G","I","J"], answer:1 }],
    tween: [{ prompt:"Tempo measures?", options:["Volume","Speed","Pitch","Rhythm"], answer:1 },{ prompt:"A group of 4 beats is a?", options:["Measure","Note","Scale","Chord"], answer:0 }],
    teen:  [{ prompt:"Major scale has how many notes?", options:["5","6","7","8"], answer:2 },{ prompt:"Beethoven became deaf and still?", options:["Stopped composing","Composed masterpieces","Became a painter","Retired early"], answer:1 }],
    adult: [{ prompt:"Sonata form has exposition, development, and?", options:["Coda","Recapitulation","Bridge","Variation"], answer:1 },{ prompt:"12-tone technique was developed by?", options:["Bach","Beethoven","Schoenberg","Liszt"], answer:2 }],
  },
  Space: {
    kids:  [{ prompt:"Closest planet to the Sun?", options:["Earth","Venus","Mercury","Mars"], answer:2 },{ prompt:"The Sun is a?", options:["Planet","Moon","Star","Comet"], answer:2 }],
    tween: [{ prompt:"Largest planet in our solar system?", options:["Earth","Saturn","Jupiter","Neptune"], answer:2 },{ prompt:"Year humans first landed on the Moon?", options:["1965","1967","1969","1971"], answer:2 }],
    teen:  [{ prompt:"Light year measures?", options:["Time","Distance","Speed","Mass"], answer:1 },{ prompt:"Black hole's escape velocity exceeds?", options:["Sound","Light","Radio waves","Matter"], answer:1 }],
    adult: [{ prompt:"Dark matter makes up ~?% of universe?", options:["5%","15%","27%","68%"], answer:2 },{ prompt:"Hubble's law relates galaxy?", options:["Mass and speed","Distance and recession speed","Size and age","Color and distance"], answer:1 }],
  },
  Economics: {
    kids:  [{ prompt:"Saving money means?", options:["Spending it all","Keeping it for later","Giving it away","Burning it"], answer:1 },{ prompt:"A budget is a plan for?", options:["Money","Food","Travel","Exercise"], answer:0 }],
    tween: [{ prompt:"Supply and demand: high supply with low demand means?", options:["Higher prices","Lower prices","Same prices","No effect"], answer:1 },{ prompt:"A stock is?", options:["A bond","A share in a company","A loan","A tax"], answer:1 }],
    teen:  [{ prompt:"GDP stands for?", options:["General Domestic Product","Gross Domestic Product","Global Development Plan","Government Debt Payment"], answer:1 },{ prompt:"Inflation means prices are?", options:["Falling","Stable","Rising","Random"], answer:2 }],
    adult: [{ prompt:"Opportunity cost is?", options:["Sunk cost","Next-best alternative value","Fixed cost","Marginal cost"], answer:1 },{ prompt:"Keynesian economics emphasizes?", options:["Austerity","Government spending","Free markets","Supply-side"], answer:1 }],
  },
  Language: {
    kids:  [{ prompt:"'Hello' in Spanish is?", options:["Bonjour","Hola","Ciao","Hallo"], answer:1 },{ prompt:"An adjective describes a?", options:["Verb","Noun","Adverb","Preposition"], answer:1 }],
    tween: [{ prompt:"A simile uses 'like' or 'as' to?", options:["Exaggerate","Compare","Rhyme","Describe sound"], answer:1 },{ prompt:"Etymology studies word?", options:["Grammar","Origins","Pronunciation","Spelling"], answer:1 }],
    teen:  [{ prompt:"Passive voice: 'The ball was kicked by John.' Who kicked?", options:["Nobody","John","Ball","Unknown"], answer:1 },{ prompt:"A gerund is a verb used as a?", options:["Adjective","Adverb","Noun","Conjunction"], answer:2 }],
    adult: [{ prompt:"Sapir-Whorf hypothesis suggests language?", options:["Is universal","Shapes thought","Has no grammar","Changes randomly"], answer:1 },{ prompt:"Phoneme vs morpheme: phoneme is?", options:["Smallest meaning unit","Smallest sound unit","Word family","Syllable"], answer:1 }],
  },
};

function getQs(subject: string, age: Age): Q[] {
  return QUESTIONS[subject]?.[age] || [];
}

export default function CreatureCatch() {
  const [age, setAge] = useState<Age>("tween");
  const [caught, setCaught] = useState<boolean[]>(Array(12).fill(false));
  const [idx, setIdx] = useState(0);
  const [hp, setHp] = useState(3);
  const [phase, setPhase] = useState<"idle" | "encounter" | "caught" | "escaped" | "done">("idle");
  const [feedback, setFeedback] = useState("");
  const [qPool, setQPool] = useState<Q[]>([]);
  const [qIdx, setQIdx] = useState(0);
  const [scale, setScale] = useState(1);

  useEffect(() => {
    const q = new URLSearchParams(window.location.search).get("age");
    if (q === "kids" || q === "tween" || q === "teen" || q === "adult") setAge(q as Age);
  }, []);

  function startEncounter(i: number) {
    const pool = getQs(CREATURES[i].subject, age).sort(() => Math.random() - 0.5);
    setQPool(pool); setQIdx(0); setHp(3); setFeedback(""); setPhase("encounter");
  }

  function answer(optIdx: number) {
    const q = qPool[qIdx];
    if (!q) return;
    if (optIdx === q.answer) {
      const next = caught.map((c, i) => i === idx ? true : c);
      setCaught(next); setFeedback(`✅ Correct! You caught ${CREATURES[idx].name}!`);
      setScale(1.3); setTimeout(() => setScale(1), 400);
      setPhase("caught");
      setTimeout(() => {
        if (next.every(Boolean)) { setPhase("done"); return; }
        let nxt = idx + 1; while (nxt < 12 && next[nxt]) nxt++;
        setIdx(nxt < 12 ? nxt : idx); setPhase("idle");
      }, 1300);
    } else {
      const newHp = hp - 1; setHp(newHp);
      if (newHp <= 0) {
        setFeedback(`💨 ${CREATURES[idx].name} escaped!`); setPhase("escaped");
        setTimeout(() => {
          let nxt = idx + 1; while (nxt < 12 && caught[nxt]) nxt++;
          setIdx(nxt < 12 ? nxt : idx); setPhase("idle");
        }, 1300);
      } else {
        setFeedback(`❌ Wrong! ${newHp} chance${newHp === 1 ? "" : "s"} left.`);
        setQIdx((q) => Math.min(q + 1, qPool.length - 1));
      }
    }
  }

  const caughtCount = caught.filter(Boolean).length;
  const c = CREATURES[idx];
  const q = qPool[qIdx];

  return (
    <main style={{ maxWidth: 600, margin: "0 auto", padding: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap", marginBottom: 10 }}>
        <h1 style={{ margin: 0 }}>🦊 Creature Catch</h1>
        <Link href="/arcade" style={{ marginLeft: "auto", color: "#94a3b8" }}>← Arcade</Link>
      </div>
      <p className="muted">Answer questions to catch Knowledge Creatures! 3 wrong answers = it escapes.</p>

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", marginBottom: 12 }}>
        {(["kids", "tween", "teen", "adult"] as Age[]).map((a) => (
          <button key={a} onClick={() => { setAge(a); setCaught(Array(12).fill(false)); setIdx(0); setPhase("idle"); }}
            style={{ opacity: age === a ? 1 : 0.5, fontWeight: age === a ? 700 : 400 }}>{a}</button>
        ))}
        <span style={{ marginLeft: "auto", color: "#fbbf24", fontWeight: 700 }}>{caughtCount}/12 caught</span>
      </div>

      {phase !== "done" && (
        <div style={{ textAlign: "center", padding: "24px 16px", marginBottom: 16,
          background: `linear-gradient(135deg, ${c.color}22, #0f172a)`,
          borderRadius: 16, border: `2px solid ${c.color}55` }}>
          <div style={{ fontSize: 88, transition: "transform 0.3s", display: "inline-block",
            transform: `scale(${scale})${phase === "escaped" ? " translateY(-30px)" : ""}`,
            filter: phase === "escaped" ? "opacity(0.2)" : "none" }}>{c.emoji}</div>
          <div style={{ fontWeight: 700, fontSize: 22, color: c.color }}>{c.name}</div>
          <div style={{ color: "#64748b", fontSize: 13 }}>{c.subject}</div>
          <div style={{ marginTop: 6 }}>{"❤️".repeat(hp)}{"🖤".repeat(3 - hp)}</div>
          {feedback && <div style={{ marginTop: 8, fontWeight: 700, color: feedback.startsWith("✅") ? "#4ade80" : "#f87171" }}>{feedback}</div>}

          {phase === "idle" && (
            <button onClick={() => startEncounter(idx)}
              style={{ marginTop: 14, background: c.color, color: "#fff", padding: "12px 28px",
                fontWeight: 700, borderRadius: 10, border: 0, cursor: "pointer", fontSize: 16 }}>
              🎯 Try to catch {c.name}!
            </button>
          )}

          {phase === "encounter" && q && (
            <div style={{ marginTop: 16, textAlign: "left" }}>
              <div style={{ fontWeight: 600, color: "#e2e8f0", marginBottom: 10 }}>{q.prompt}</div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                {q.options.map((opt, i) => (
                  <button key={i} onClick={() => answer(i)}
                    style={{ padding: "10px", borderRadius: 8, background: "#1e293b", color: "#e2e8f0",
                      border: `1px solid ${c.color}55`, fontWeight: 600, cursor: "pointer" }}>
                    {opt}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: 8 }}>
        {CREATURES.map((cr, i) => (
          <div key={i} style={{ textAlign: "center", padding: "6px 4px", borderRadius: 10,
            background: caught[i] ? `${cr.color}33` : "#1e293b",
            border: `1px solid ${caught[i] ? cr.color : "#334155"}`,
            opacity: caught[i] ? 1 : 0.4, cursor: phase === "idle" && !caught[i] ? "pointer" : "default" }}
            onClick={() => { if (phase === "idle" && !caught[i]) { setIdx(i); } }}>
            <div style={{ fontSize: 26 }}>{caught[i] ? cr.emoji : "❓"}</div>
            <div style={{ fontSize: 9, color: caught[i] ? cr.color : "#64748b", fontWeight: 600 }}>{caught[i] ? cr.name : "???"}</div>
          </div>
        ))}
      </div>

      {phase === "done" && (
        <div style={{ textAlign: "center", padding: 32, marginTop: 16 }}>
          <div style={{ fontSize: 56 }}>{caughtCount === 12 ? "🌟" : "🎉"}</div>
          <h2>{caughtCount === 12 ? "Codex Complete! All 12 caught!" : `You caught ${caughtCount}/12 creatures!`}</h2>
          <button onClick={() => { setCaught(Array(12).fill(false)); setIdx(0); setPhase("idle"); }}
            style={{ background: "#7c3aed", color: "#fff", padding: "12px 28px", fontSize: 18,
              borderRadius: 10, border: 0, cursor: "pointer", fontWeight: 700 }}>
            ▶ Play again
          </button>
        </div>
      )}
    </main>
  );
}

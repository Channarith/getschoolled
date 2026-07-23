"use client";

import Link from "next/link";
import { useState } from "react";

const DISEASES = [
  {
    id: "cancer",
    name: "Cancer",
    emoji: "🎗️",
    color: "#e74c3c",
    description: "Stem cells can be engineered to target and destroy cancer cells.",
    questions: [
      {
        q: "What type of stem cell therapy fights leukemia?",
        opts: ["CAR-T cell therapy", "Insulin therapy", "Dialysis", "Chemotherapy alone"],
        correct: 0,
        fact: "CAR-T cells are genetically engineered to find and kill cancer cells!",
      },
      {
        q: "Where are blood stem cells found?",
        opts: ["Brain", "Bone marrow", "Liver", "Heart"],
        correct: 1,
        fact: "Bone marrow contains hematopoietic stem cells that produce all blood cells.",
      },
    ],
  },
  {
    id: "diabetes",
    name: "Diabetes",
    emoji: "💉",
    color: "#3498db",
    description: "Beta cells from stem cells can replace destroyed insulin-producing cells.",
    questions: [
      {
        q: "Which cells are destroyed in Type 1 Diabetes?",
        opts: ["Alpha cells", "Beta cells", "Delta cells", "Gamma cells"],
        correct: 1,
        fact: "Beta cells in the pancreas produce insulin. Stem cells may replace them!",
      },
      {
        q: "What hormone do beta cells produce?",
        opts: ["Glucagon", "Adrenaline", "Insulin", "Cortisol"],
        correct: 2,
        fact: "Insulin regulates blood sugar. Stem cell-derived beta cells could cure Type 1 Diabetes.",
      },
    ],
  },
  {
    id: "alzheimers",
    name: "Alzheimer's",
    emoji: "🧠",
    color: "#9b59b6",
    description: "Neural stem cells may restore memory and slow brain degeneration.",
    questions: [
      {
        q: "What brain protein accumulates in Alzheimer's?",
        opts: ["Dopamine", "Beta-amyloid plaques", "Serotonin", "Myelin"],
        correct: 1,
        fact: "Amyloid plaques disrupt brain connections. Stem cells may clear them and regrow neurons.",
      },
      {
        q: "What part of the brain is first affected by Alzheimer's?",
        opts: ["Cerebellum", "Hippocampus", "Brain stem", "Frontal lobe"],
        correct: 1,
        fact: "The hippocampus controls memory. Neural stem cell therapy targets this region.",
      },
    ],
  },
  {
    id: "covid",
    name: "COVID-19",
    emoji: "🦠",
    color: "#e67e22",
    description: "Mesenchymal stem cells reduce the deadly cytokine storm in severe COVID-19.",
    questions: [
      {
        q: "What dangerous immune reaction does COVID-19 cause?",
        opts: ["Cytokine storm", "Protein fold", "DNA mutation", "Cell apoptosis"],
        correct: 0,
        fact: "A cytokine storm causes the immune system to attack healthy tissue. MSCs calm this response!",
      },
      {
        q: "What do mesenchymal stem cells (MSCs) do in COVID treatment?",
        opts: ["Kill the virus", "Reduce inflammation", "Produce antibodies", "Replace lung cells"],
        correct: 1,
        fact: "MSCs release anti-inflammatory signals that reduce dangerous lung damage.",
      },
    ],
  },
  {
    id: "aging",
    name: "Aging",
    emoji: "⏳",
    color: "#27ae60",
    description: "Senescent cell removal and stem cell renewal may slow biological aging.",
    questions: [
      {
        q: "What are 'zombie cells' in aging called?",
        opts: ["Stem cells", "Senescent cells", "Progenitor cells", "Pluripotent cells"],
        correct: 1,
        fact: "Senescent cells stop dividing but don't die. Removing them rejuvenates surrounding tissue!",
      },
      {
        q: "What makes stem cells 'pluripotent'?",
        opts: [
          "They can become any cell type",
          "They never divide",
          "They only exist in blood",
          "They cause aging",
        ],
        correct: 0,
        fact: "Pluripotent stem cells (like iPSCs) can become ANY tissue in the body!",
      },
    ],
  },
  {
    id: "skin",
    name: "Skin & Allergies",
    emoji: "🌿",
    color: "#f39c12",
    description: "Skin stem cells regrow damaged tissue. Regulatory T-cells treat severe allergies.",
    questions: [
      {
        q: "What skin condition can stem cells treat via hair follicle regeneration?",
        opts: ["Sunburn", "Alopecia (hair loss)", "Wrinkles", "Freckles"],
        correct: 1,
        fact: "Hair follicle stem cells can be activated to regrow hair in alopecia patients!",
      },
      {
        q: "What immune cells regulate allergic reactions?",
        opts: ["T-regulatory cells", "B cells", "Neutrophils", "Basophils"],
        correct: 0,
        fact: "Stem cell-derived T-regulatory cells can suppress overactive allergic immune responses.",
      },
    ],
  },
];

const TOTAL_POINTS = DISEASES.length * 2 * 20; // 6 diseases × 2 questions × 20 pts = 240

type Question = {
  q: string;
  opts: string[];
  correct: number;
  fact: string;
};

type Disease = {
  id: string;
  name: string;
  emoji: string;
  color: string;
  description: string;
  questions: Question[];
};

type Feedback = {
  correct: boolean;
  fact: string;
};

// ─── Intro Screen ────────────────────────────────────────────────────────────
function IntroScreen({ onStart }: { onStart: () => void }) {
  return (
    <div
      style={{
        minHeight: "100vh",
        background: "#0a0f1e",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: "24px",
        fontFamily: "'Segoe UI', system-ui, sans-serif",
        color: "#e0e6f0",
      }}
    >
      <div
        style={{
          maxWidth: 600,
          textAlign: "center",
        }}
      >
        <div style={{ fontSize: 72, marginBottom: 16 }}>🔬</div>
        <h1
          style={{
            fontSize: "clamp(28px, 5vw, 42px)",
            fontWeight: 800,
            color: "#00d4aa",
            margin: "0 0 12px",
            letterSpacing: "-0.5px",
          }}
        >
          Stem Cell Lab
        </h1>
        <h2
          style={{
            fontSize: "clamp(16px, 3vw, 22px)",
            fontWeight: 400,
            color: "#a0b0c8",
            margin: "0 0 28px",
          }}
        >
          Cure the World
        </h2>
        <p
          style={{
            fontSize: 16,
            lineHeight: 1.7,
            color: "#c0cfe0",
            marginBottom: 32,
          }}
        >
          You are a stem cell researcher. Six deadly diseases threaten humanity. Answer
          science trivia to unlock breakthrough therapies and watch the cures unfold.
          Every correct answer earns{" "}
          <span style={{ color: "#00d4aa", fontWeight: 700 }}>20 Research Points</span>.
          Cure all 6 diseases to save the world!
        </p>

        <div
          style={{
            display: "flex",
            gap: 16,
            justifyContent: "center",
            flexWrap: "wrap",
            marginBottom: 40,
          }}
        >
          {DISEASES.map((d) => (
            <span
              key={d.id}
              style={{
                fontSize: 28,
                filter: "drop-shadow(0 0 8px " + d.color + "88)",
              }}
            >
              {d.emoji}
            </span>
          ))}
        </div>

        <button
          onClick={onStart}
          style={{
            background: "linear-gradient(135deg, #00d4aa, #0097a7)",
            color: "#fff",
            border: "none",
            borderRadius: 12,
            padding: "16px 40px",
            fontSize: 18,
            fontWeight: 700,
            cursor: "pointer",
            boxShadow: "0 0 30px #00d4aa44",
            transition: "transform 0.15s, box-shadow 0.15s",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.transform = "scale(1.05)";
            e.currentTarget.style.boxShadow = "0 0 40px #00d4aa66";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.transform = "scale(1)";
            e.currentTarget.style.boxShadow = "0 0 30px #00d4aa44";
          }}
        >
          🧬 Start Research
        </button>
      </div>
    </div>
  );
}

// ─── Disease Grid ─────────────────────────────────────────────────────────────
function DiseaseGrid({
  researchPoints,
  curedDiseases,
  onSelect,
}: {
  researchPoints: number;
  curedDiseases: Set<string>;
  onSelect: (id: string) => void;
}) {
  const pct = Math.min(100, (researchPoints / TOTAL_POINTS) * 100);
  const allCured = curedDiseases.size === DISEASES.length;

  if (allCured) {
    return (
      <div
        style={{
          minHeight: "100vh",
          background: "#0a0f1e",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          padding: 24,
          fontFamily: "'Segoe UI', system-ui, sans-serif",
          color: "#e0e6f0",
          textAlign: "center",
        }}
      >
        <div style={{ fontSize: 80, marginBottom: 16 }}>🌍</div>
        <h1
          style={{
            fontSize: 42,
            fontWeight: 800,
            color: "#00d4aa",
            margin: "0 0 12px",
          }}
        >
          You&apos;ve changed the world!
        </h1>
        <p style={{ fontSize: 20, color: "#a0b0c8", marginBottom: 24 }}>
          All 6 diseases cured. Humanity is saved.
        </p>
        <div
          style={{
            background: "#0d1929",
            border: "2px solid #00d4aa",
            borderRadius: 16,
            padding: "24px 40px",
            marginBottom: 32,
            boxShadow: "0 0 40px #00d4aa33",
          }}
        >
          <div style={{ fontSize: 14, color: "#a0b0c8", marginBottom: 4 }}>
            Total Research Points
          </div>
          <div style={{ fontSize: 48, fontWeight: 800, color: "#00d4aa" }}>
            {researchPoints}
          </div>
          <div style={{ fontSize: 14, color: "#a0b0c8" }}>out of {TOTAL_POINTS}</div>
        </div>
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap", justifyContent: "center" }}>
          {DISEASES.map((d) => (
            <span key={d.id} style={{ fontSize: 32 }}>
              {d.emoji}
            </span>
          ))}
        </div>
        <Link
          href="/arcade"
          style={{
            marginTop: 32,
            display: "inline-block",
            padding: "12px 28px",
            background: "#1a2540",
            border: "2px solid #00d4aa",
            borderRadius: 10,
            color: "#00d4aa",
            fontWeight: 700,
            textDecoration: "none",
            fontSize: 15,
          }}
        >
          ← Back to Arcade
        </Link>
      </div>
    );
  }

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "#0a0f1e",
        padding: "24px",
        fontFamily: "'Segoe UI', system-ui, sans-serif",
        color: "#e0e6f0",
      }}
    >
      {/* Top bar */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 24,
          flexWrap: "wrap",
          gap: 12,
        }}
      >
        <Link
          href="/arcade"
          style={{
            color: "#00d4aa",
            textDecoration: "none",
            fontWeight: 600,
            fontSize: 14,
          }}
        >
          ← Back to Arcade
        </Link>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: 12, color: "#a0b0c8", marginBottom: 4 }}>
            Research Progress
          </div>
          <div
            style={{
              width: 240,
              height: 10,
              background: "#1a2540",
              borderRadius: 5,
              overflow: "hidden",
              border: "1px solid #2a3a60",
            }}
          >
            <div
              style={{
                height: "100%",
                width: `${pct}%`,
                background: "linear-gradient(90deg, #00d4aa, #0097a7)",
                borderRadius: 5,
                transition: "width 0.5s ease",
              }}
            />
          </div>
          <div style={{ fontSize: 13, color: "#00d4aa", fontWeight: 700, marginTop: 4 }}>
            {researchPoints} / {TOTAL_POINTS} pts
          </div>
        </div>
        <div style={{ fontSize: 14, color: "#a0b0c8" }}>
          Cured: {curedDiseases.size} / {DISEASES.length}
        </div>
      </div>

      <h2
        style={{
          textAlign: "center",
          color: "#00d4aa",
          fontWeight: 800,
          fontSize: 26,
          margin: "0 0 8px",
        }}
      >
        🔬 Choose a Disease to Research
      </h2>
      <p style={{ textAlign: "center", color: "#a0b0c8", margin: "0 0 28px", fontSize: 14 }}>
        Answer both questions correctly to cure each disease
      </p>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))",
          gap: 20,
          maxWidth: 900,
          margin: "0 auto",
        }}
      >
        {DISEASES.map((d) => {
          const cured = curedDiseases.has(d.id);
          return (
            <button
              key={d.id}
              onClick={() => !cured && onSelect(d.id)}
              style={{
                background: "#0d1929",
                border: `2px solid ${cured ? "#00d4aa" : d.color}`,
                borderRadius: 16,
                padding: "24px 20px",
                cursor: cured ? "default" : "pointer",
                textAlign: "left",
                position: "relative",
                overflow: "hidden",
                transition: "transform 0.15s, box-shadow 0.15s",
                boxShadow: cured ? `0 0 20px #00d4aa44` : "none",
                opacity: cured ? 0.85 : 1,
              }}
              onMouseEnter={(e) => {
                if (!cured) {
                  e.currentTarget.style.transform = "translateY(-4px)";
                  e.currentTarget.style.boxShadow = `0 0 20px ${d.color}66`;
                }
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.transform = "translateY(0)";
                e.currentTarget.style.boxShadow = cured ? "0 0 20px #00d4aa44" : "none";
              }}
            >
              {cured && (
                <div
                  style={{
                    position: "absolute",
                    inset: 0,
                    background: "rgba(0, 212, 170, 0.12)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    borderRadius: 14,
                    backdropFilter: "blur(1px)",
                    zIndex: 1,
                  }}
                >
                  <div
                    style={{
                      background: "#00d4aa",
                      color: "#0a0f1e",
                      fontWeight: 800,
                      fontSize: 16,
                      padding: "8px 20px",
                      borderRadius: 8,
                      letterSpacing: 1,
                    }}
                  >
                    ✓ CURED
                  </div>
                </div>
              )}
              <div style={{ fontSize: 40, marginBottom: 12 }}>{d.emoji}</div>
              <div style={{ fontWeight: 700, fontSize: 18, color: d.color, marginBottom: 8 }}>
                {d.name}
              </div>
              <div style={{ fontSize: 13, color: "#a0b0c8", lineHeight: 1.5 }}>
                {d.description}
              </div>
              <div
                style={{
                  marginTop: 16,
                  fontSize: 12,
                  color: cured ? "#00d4aa" : "#6a8099",
                  fontWeight: 600,
                }}
              >
                {cured ? "Research Complete" : `${d.questions.length} questions`}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

// ─── Research Screen ──────────────────────────────────────────────────────────
function ResearchScreen({
  disease,
  questionIndex,
  feedback,
  onAnswer,
  onNext,
  onBack,
}: {
  disease: Disease;
  questionIndex: number;
  feedback: Feedback | null;
  onAnswer: (idx: number) => void;
  onNext: () => void;
  onBack: () => void;
}) {
  const question = disease.questions[questionIndex];
  const isLast = questionIndex === disease.questions.length - 1;

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "#0a0f1e",
        padding: "24px",
        fontFamily: "'Segoe UI', system-ui, sans-serif",
        color: "#e0e6f0",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
      }}
    >
      {/* Back link */}
      <div style={{ width: "100%", maxWidth: 680, marginBottom: 20 }}>
        <button
          onClick={onBack}
          style={{
            background: "transparent",
            border: "none",
            color: "#00d4aa",
            fontWeight: 600,
            fontSize: 14,
            cursor: "pointer",
            padding: 0,
          }}
        >
          ← Back to diseases
        </button>
      </div>

      {/* Disease header */}
      <div
        style={{
          width: "100%",
          maxWidth: 680,
          background: "#0d1929",
          border: `2px solid ${disease.color}`,
          borderRadius: 16,
          padding: "24px",
          marginBottom: 24,
          boxShadow: `0 0 20px ${disease.color}44`,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <span style={{ fontSize: 48 }}>{disease.emoji}</span>
          <div>
            <div style={{ fontWeight: 800, fontSize: 22, color: disease.color }}>
              {disease.name}
            </div>
            <div style={{ fontSize: 13, color: "#a0b0c8", marginTop: 4 }}>
              {disease.description}
            </div>
          </div>
        </div>
        <div style={{ marginTop: 16, display: "flex", gap: 8 }}>
          {disease.questions.map((_, i) => (
            <div
              key={i}
              style={{
                flex: 1,
                height: 4,
                borderRadius: 2,
                background: i < questionIndex ? "#00d4aa" : i === questionIndex ? disease.color : "#1a2540",
                transition: "background 0.3s",
              }}
            />
          ))}
        </div>
        <div style={{ fontSize: 12, color: "#6a8099", marginTop: 6 }}>
          Question {questionIndex + 1} of {disease.questions.length}
        </div>
      </div>

      {/* Question card */}
      <div
        style={{
          width: "100%",
          maxWidth: 680,
          background: "#0d1929",
          border: "2px solid #1a2f50",
          borderRadius: 16,
          padding: "28px",
        }}
      >
        <div style={{ fontWeight: 700, fontSize: 19, lineHeight: 1.5, marginBottom: 24 }}>
          {question.q}
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {question.opts.map((opt, idx) => {
            let bg = "#111d33";
            let border = "2px solid #1a2f50";
            let color = "#c8d8e8";

            if (feedback) {
              if (idx === question.correct) {
                bg = "#0d2e1a";
                border = "2px solid #27ae60";
                color = "#4ade80";
              } else if (idx !== question.correct) {
                bg = "#1e0e0e";
                border = "2px solid #3a1a1a";
                color = "#6a8099";
              }
            }

            return (
              <button
                key={idx}
                onClick={() => !feedback && onAnswer(idx)}
                disabled={!!feedback}
                style={{
                  background: bg,
                  border,
                  borderRadius: 10,
                  padding: "14px 18px",
                  textAlign: "left",
                  color,
                  fontSize: 15,
                  fontWeight: 500,
                  cursor: feedback ? "default" : "pointer",
                  transition: "all 0.2s",
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                }}
                onMouseEnter={(e) => {
                  if (!feedback) {
                    e.currentTarget.style.border = `2px solid ${disease.color}`;
                    e.currentTarget.style.background = "#152040";
                  }
                }}
                onMouseLeave={(e) => {
                  if (!feedback) {
                    e.currentTarget.style.border = "2px solid #1a2f50";
                    e.currentTarget.style.background = "#111d33";
                  }
                }}
              >
                <span
                  style={{
                    width: 26,
                    height: 26,
                    borderRadius: "50%",
                    background: feedback && idx === question.correct ? "#27ae60" : "#1a2f50",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: 12,
                    fontWeight: 700,
                    flexShrink: 0,
                    color: feedback && idx === question.correct ? "#fff" : "#6a8099",
                  }}
                >
                  {String.fromCharCode(65 + idx)}
                </span>
                {opt}
              </button>
            );
          })}
        </div>

        {/* Feedback panel */}
        {feedback && (
          <div
            style={{
              marginTop: 24,
              padding: "16px 20px",
              background: feedback.correct ? "#0a2018" : "#1e0a0a",
              border: `2px solid ${feedback.correct ? "#27ae60" : "#e74c3c"}`,
              borderRadius: 12,
              animation: "fadeIn 0.3s ease",
            }}
          >
            <div
              style={{
                fontWeight: 700,
                fontSize: 16,
                color: feedback.correct ? "#4ade80" : "#f87171",
                marginBottom: 8,
              }}
            >
              {feedback.correct ? "✓ Correct! +20 Research Points" : "✗ Not quite..."}
            </div>
            <div style={{ fontSize: 14, color: "#a0c0b8", lineHeight: 1.6 }}>
              🧬 <em>{feedback.fact}</em>
            </div>
            <button
              onClick={onNext}
              style={{
                marginTop: 16,
                background: feedback.correct
                  ? "linear-gradient(135deg, #00d4aa, #0097a7)"
                  : "linear-gradient(135deg, #e74c3c, #c0392b)",
                color: "#fff",
                border: "none",
                borderRadius: 8,
                padding: "10px 24px",
                fontWeight: 700,
                fontSize: 14,
                cursor: "pointer",
              }}
            >
              {feedback.correct && isLast ? "🎉 Disease Cured!" : "Next Question →"}
            </button>
          </div>
        )}
      </div>

      <style>{`
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(8px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  );
}

// ─── Main Game Component ──────────────────────────────────────────────────────
export default function StemResearchGame() {
  const [showIntro, setShowIntro] = useState(true);
  const [selectedDisease, setSelectedDisease] = useState<string | null>(null);
  const [questionIndex, setQuestionIndex] = useState(0);
  const [researchPoints, setResearchPoints] = useState(0);
  const [curedDiseases, setCuredDiseases] = useState<Set<string>>(new Set());
  const [feedback, setFeedback] = useState<Feedback | null>(null);

  const disease = DISEASES.find((d) => d.id === selectedDisease) ?? null;

  function handleSelectDisease(id: string) {
    setSelectedDisease(id);
    setQuestionIndex(0);
    setFeedback(null);
  }

  function handleAnswer(idx: number) {
    if (!disease) return;
    const question = disease.questions[questionIndex];
    const correct = idx === question.correct;
    if (correct) {
      setResearchPoints((p) => p + 20);
    }
    setFeedback({ correct, fact: question.fact });
  }

  function handleNext() {
    if (!disease) return;
    const isLast = questionIndex === disease.questions.length - 1;

    if (feedback?.correct && isLast) {
      // Disease cured!
      setCuredDiseases((prev) => {
        const next = new Set(prev);
        next.add(disease.id);
        return next;
      });
      setSelectedDisease(null);
      setFeedback(null);
      return;
    }

    if (isLast) {
      // Wrong on last question — restart from first question for this disease
      setQuestionIndex(0);
      setFeedback(null);
      return;
    }

    setQuestionIndex((q) => q + 1);
    setFeedback(null);
  }

  function handleBack() {
    setSelectedDisease(null);
    setFeedback(null);
    setQuestionIndex(0);
  }

  if (showIntro) {
    return <IntroScreen onStart={() => setShowIntro(false)} />;
  }

  if (selectedDisease && disease) {
    return (
      <ResearchScreen
        disease={disease}
        questionIndex={questionIndex}
        feedback={feedback}
        onAnswer={handleAnswer}
        onNext={handleNext}
        onBack={handleBack}
      />
    );
  }

  return (
    <DiseaseGrid
      researchPoints={researchPoints}
      curedDiseases={curedDiseases}
      onSelect={handleSelectDisease}
    />
  );
}

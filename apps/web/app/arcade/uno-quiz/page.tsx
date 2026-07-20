"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

// ─── Types ───────────────────────────────────────────────────────────────────

type UnoColor = "red" | "blue" | "green" | "yellow" | "wild";
type UnoValue = 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | "skip" | "reverse" | "draw2" | "wild" | "wild4";

type UnoCard = {
  id: number;
  color: UnoColor;
  value: UnoValue;
};

type Phase = "intro" | "playing" | "question" | "colorPick" | "playerWon" | "aiWon";
type AgeKey = "kids" | "tween" | "teen" | "adult";

type Question = {
  q: string;
  options: [string, string, string, string];
  answer: number;
};

// ─── Colors ──────────────────────────────────────────────────────────────────

const COLOR_HEX: Record<UnoColor, string> = {
  red: "#dc2626",
  blue: "#2563eb",
  green: "#16a34a",
  yellow: "#eab308",
  wild: "#1f2937",
};

const COLOR_LABEL: Record<UnoColor, string> = {
  red: "Red", blue: "Blue", green: "Green", yellow: "Yellow", wild: "Wild",
};

// ─── Deck Builder ─────────────────────────────────────────────────────────────

let _cardId = 1;

function buildDeck(): UnoCard[] {
  _cardId = 0;
  const cards: UnoCard[] = [];
  const colors: UnoColor[] = ["red", "blue", "green", "yellow"];

  for (const color of colors) {
    cards.push({ id: _cardId++, color, value: 0 });
    for (let n = 1; n <= 9; n++) {
      cards.push({ id: _cardId++, color, value: n as UnoValue });
      cards.push({ id: _cardId++, color, value: n as UnoValue });
    }
    for (const v of ["skip", "reverse", "draw2"] as UnoValue[]) {
      cards.push({ id: _cardId++, color, value: v });
      cards.push({ id: _cardId++, color, value: v });
    }
  }

  for (let i = 0; i < 4; i++) {
    cards.push({ id: _cardId++, color: "wild", value: "wild" });
    cards.push({ id: _cardId++, color: "wild", value: "wild4" });
  }

  return shuffle(cards);
}

function shuffle<T>(arr: T[]): T[] {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

// ─── Question Banks ───────────────────────────────────────────────────────────

const QUESTIONS_KIDS: Question[] = [
  { q: "What is 3 + 4?", options: ["5", "6", "7", "8"], answer: 2 },
  { q: "Which animal says 'Moo'?", options: ["Dog", "Cat", "Cow", "Duck"], answer: 2 },
  { q: "What color is the sky?", options: ["Green", "Blue", "Red", "Yellow"], answer: 1 },
  { q: "How many legs does a spider have?", options: ["4", "6", "8", "10"], answer: 2 },
  { q: "What is 10 - 3?", options: ["5", "6", "7", "8"], answer: 2 },
  { q: "What do bees make?", options: ["Milk", "Honey", "Butter", "Juice"], answer: 1 },
  { q: "What shape has 3 sides?", options: ["Square", "Circle", "Triangle", "Rectangle"], answer: 2 },
  { q: "What is the biggest planet?", options: ["Earth", "Mars", "Jupiter", "Saturn"], answer: 2 },
  { q: "How many days in a week?", options: ["5", "6", "7", "8"], answer: 2 },
  { q: "What do plants need to grow?", options: ["Soda", "Water", "Juice", "Milk"], answer: 1 },
  { q: "What is 5 x 2?", options: ["8", "9", "10", "11"], answer: 2 },
  { q: "Where do fish live?", options: ["Trees", "Deserts", "Water", "Mountains"], answer: 2 },
  { q: "What color is grass?", options: ["Blue", "Green", "Red", "Purple"], answer: 1 },
  { q: "How many sides does a square have?", options: ["3", "4", "5", "6"], answer: 1 },
  { q: "What is the opposite of hot?", options: ["Warm", "Cool", "Cold", "Freezing"], answer: 2 },
  { q: "What do we use to smell?", options: ["Ears", "Eyes", "Nose", "Tongue"], answer: 2 },
  { q: "Which season comes after Winter?", options: ["Summer", "Fall", "Spring", "Rain"], answer: 2 },
  { q: "What is 4 x 3?", options: ["10", "11", "12", "13"], answer: 2 },
  { q: "What do caterpillars turn into?", options: ["Butterflies", "Birds", "Bees", "Beetles"], answer: 0 },
  { q: "How many months in a year?", options: ["10", "11", "12", "13"], answer: 2 },
];

const QUESTIONS_TWEEN: Question[] = [
  { q: "What is the capital of Japan?", options: ["Beijing", "Seoul", "Tokyo", "Bangkok"], answer: 2 },
  { q: "What gas do plants absorb?", options: ["Oxygen", "Nitrogen", "Carbon Dioxide", "Helium"], answer: 2 },
  { q: "Who wrote Romeo and Juliet?", options: ["Dickens", "Shakespeare", "Tolstoy", "Austen"], answer: 1 },
  { q: "What is 15% of 200?", options: ["20", "25", "30", "35"], answer: 2 },
  { q: "What is the speed of light?", options: ["300 km/s", "3000 km/s", "300,000 km/s", "3,000,000 km/s"], answer: 2 },
  { q: "What is photosynthesis?", options: ["Cell division", "Breathing", "Making food from sunlight", "Moving nutrients"], answer: 2 },
  { q: "Who discovered gravity?", options: ["Einstein", "Newton", "Galileo", "Darwin"], answer: 1 },
  { q: "What is the chemical symbol for gold?", options: ["Go", "Au", "Ag", "Gd"], answer: 1 },
  { q: "What continent is Egypt in?", options: ["Asia", "Europe", "Africa", "Australia"], answer: 2 },
  { q: "What is 7 squared?", options: ["42", "47", "49", "56"], answer: 2 },
  { q: "What is a prime number?", options: ["Divisible by 2", "Only divisible by 1 and itself", "Divisible by 3", "An even number"], answer: 1 },
  { q: "What is the powerhouse of the cell?", options: ["Nucleus", "Ribosome", "Mitochondria", "Vacuole"], answer: 2 },
  { q: "What is the synonym of 'Happy'?", options: ["Sad", "Joyful", "Angry", "Tired"], answer: 1 },
  { q: "Which planet is closest to the Sun?", options: ["Venus", "Earth", "Mars", "Mercury"], answer: 3 },
  { q: "What does H2O represent?", options: ["Hydrogen gas", "Salt", "Water", "Oxygen"], answer: 2 },
  { q: "What is the largest continent?", options: ["Africa", "North America", "Asia", "Europe"], answer: 2 },
  { q: "What year did WW2 end?", options: ["1943", "1944", "1945", "1946"], answer: 2 },
  { q: "What is the area of a rectangle 4x6?", options: ["20", "22", "24", "26"], answer: 2 },
  { q: "What is democracy?", options: ["Rule by a king", "Rule by the people", "Rule by the military", "Rule by religion"], answer: 1 },
  { q: "What is a haiku?", options: ["14-line poem", "5-7-5 syllable poem", "Rhyming couplet", "Free verse poem"], answer: 1 },
];

const QUESTIONS_TEEN: Question[] = [
  { q: "What is the derivative of x squared?", options: ["x", "2x", "x squared", "2"], answer: 1 },
  { q: "Who wrote 'The Communist Manifesto'?", options: ["Lenin", "Stalin", "Marx & Engels", "Trotsky"], answer: 2 },
  { q: "What is the atomic number of Carbon?", options: ["4", "6", "8", "12"], answer: 1 },
  { q: "What does DNA stand for?", options: ["Dynamic Nucleic Acid", "Deoxyribonucleic Acid", "Deoxyribose Nucleotide Acid", "Direct Nucleic Assembly"], answer: 1 },
  { q: "What is the Pythagorean theorem?", options: ["a+b=c", "a2+b2=c2", "axb=c2", "a2-b2=c"], answer: 1 },
  { q: "In what year did the French Revolution begin?", options: ["1776", "1789", "1799", "1815"], answer: 1 },
  { q: "What is entropy in thermodynamics?", options: ["Energy stored", "Measure of disorder", "Heat transfer rate", "Work done by system"], answer: 1 },
  { q: "Who developed the theory of relativity?", options: ["Newton", "Bohr", "Einstein", "Heisenberg"], answer: 2 },
  { q: "What is the chemical formula for glucose?", options: ["C6H12O6", "C12H22O11", "CH4", "C2H5OH"], answer: 0 },
  { q: "What literary device is 'The world is a stage'?", options: ["Simile", "Metaphor", "Personification", "Alliteration"], answer: 1 },
  { q: "What is the capital of Australia?", options: ["Sydney", "Melbourne", "Brisbane", "Canberra"], answer: 3 },
  { q: "What is a logarithm?", options: ["Square root", "Power to which base is raised", "Reciprocal of exponent", "Product of factors"], answer: 1 },
  { q: "What is GDP?", options: ["Government Defined Policy", "Gross Domestic Product", "General Demand Price", "Growth Deficit Percentage"], answer: 1 },
  { q: "What is the formula for the area of a circle?", options: ["2 pi r", "pi r squared", "pi d", "2 pi r squared"], answer: 1 },
  { q: "What war did the Treaty of Versailles end?", options: ["World War I", "World War II", "Civil War", "Napoleonic Wars"], answer: 0 },
  { q: "What is the mitochondria's primary function?", options: ["Protein synthesis", "Cellular respiration/ATP production", "Cell division", "Lipid storage"], answer: 1 },
  { q: "What is Schrodinger's Cat thought experiment about?", options: ["Quantum superposition", "Animal rights", "Wave-particle duality", "String theory"], answer: 0 },
  { q: "What is osmosis?", options: ["Active transport of ions", "Passive water movement across membrane", "Diffusion of gases", "Protein channel transport"], answer: 1 },
  { q: "What is hegemony?", options: ["Military victory", "Cultural/political dominance", "Economic growth", "Legal sovereignty"], answer: 1 },
  { q: "Who wrote '1984'?", options: ["Huxley", "Kafka", "Orwell", "Bradbury"], answer: 2 },
];

const QUESTION_BANKS: Record<AgeKey, Question[]> = {
  kids: QUESTIONS_KIDS,
  tween: QUESTIONS_TWEEN,
  teen: QUESTIONS_TEEN,
  adult: QUESTIONS_TEEN,
};

// ─── Helpers ──────────────────────────────────────────────────────────────────

function valueLabel(v: UnoValue): string {
  if (v === "skip") return "SKIP";
  if (v === "reverse") return "REV";
  if (v === "draw2") return "+2";
  if (v === "wild") return "WILD";
  if (v === "wild4") return "+4";
  return String(v);
}

function valueLabelShort(v: UnoValue): string {
  if (v === "skip") return "⦸";
  if (v === "reverse") return "⇄";
  if (v === "draw2") return "+2";
  if (v === "wild") return "★";
  if (v === "wild4") return "+4";
  return String(v);
}

function isSpecialValue(v: UnoValue): boolean {
  return typeof v === "string";
}

function isPlayable(card: UnoCard, topCard: UnoCard, currentColor: UnoColor): boolean {
  if (card.color === "wild") return true;
  if (card.color === currentColor) return true;
  if (card.value === topCard.value) return true;
  return false;
}

function colorMajority(hand: UnoCard[]): UnoColor {
  const counts: Partial<Record<UnoColor, number>> = {};
  for (const c of hand) {
    if (c.color !== "wild") counts[c.color] = (counts[c.color] ?? 0) + 1;
  }
  let best: UnoColor = "red";
  let bestN = 0;
  for (const [col, n] of Object.entries(counts) as [UnoColor, number][]) {
    if (n > bestN) { bestN = n; best = col; }
  }
  return best;
}

// ─── Main Component ───────────────────────────────────────────────────────────

export default function UnoQuiz() {
  const [age, setAge] = useState<AgeKey>("kids");

  const [phase, setPhase] = useState<Phase>("intro");
  const [deck, setDeck] = useState<UnoCard[]>([]);
  const [playerHand, setPlayerHand] = useState<UnoCard[]>([]);
  const [aiHand, setAiHand] = useState<UnoCard[]>([]);
  const [discardPile, setDiscardPile] = useState<UnoCard[]>([]);
  const [currentColor, setCurrentColor] = useState<UnoColor>("red");
  const [isPlayerTurn, setIsPlayerTurn] = useState(true);
  const [pendingCard, setPendingCard] = useState<UnoCard | null>(null);
  const [currentQuestion, setCurrentQuestion] = useState<Question | null>(null);
  const [questionResult, setQuestionResult] = useState<"correct" | "wrong" | null>(null);
  const [message, setMessage] = useState("");
  const [unoShouted, setUnoShouted] = useState(false);
  const [usedQIndices, setUsedQIndices] = useState<number[]>([]);
  const [pendingColorCard, setPendingColorCard] = useState<UnoCard | null>(null);

  const deckRef = useRef<UnoCard[]>([]);
  const aiHandRef = useRef<UnoCard[]>([]);
  const playerHandRef = useRef<UnoCard[]>([]);
  const discardRef = useRef<UnoCard[]>([]);
  const currentColorRef = useRef<UnoColor>("red");
  const pendingPlayerHandRef = useRef<UnoCard[]>([]);

  useEffect(() => { deckRef.current = deck; }, [deck]);
  useEffect(() => { aiHandRef.current = aiHand; }, [aiHand]);
  useEffect(() => { playerHandRef.current = playerHand; }, [playerHand]);
  useEffect(() => { discardRef.current = discardPile; }, [discardPile]);
  useEffect(() => { currentColorRef.current = currentColor; }, [currentColor]);

  useEffect(() => {
    const p = new URLSearchParams(window.location.search).get("age");
    if (p && p in QUESTION_BANKS) setAge(p as AgeKey);
  }, []);

  const questionBank = useMemo(() => QUESTION_BANKS[age], [age]);

  const pickQuestion = useCallback((used: number[]): { q: Question; idx: number } => {
    const available = questionBank.map((_, i) => i).filter((i) => !used.includes(i));
    const pool = available.length > 0 ? available : questionBank.map((_, i) => i);
    const idx = pool[Math.floor(Math.random() * pool.length)];
    return { q: questionBank[idx], idx };
  }, [questionBank]);

  const drawFromDeck = useCallback((
    currentDeck: UnoCard[],
    currentDiscard: UnoCard[],
    count: number
  ): { drawn: UnoCard[]; newDeck: UnoCard[]; newDiscard: UnoCard[] } => {
    let d = [...currentDeck];
    let disc = [...currentDiscard];
    if (d.length < count && disc.length > 1) {
      const top = disc[disc.length - 1];
      const reshuffled = shuffle(disc.slice(0, -1));
      d = [...d, ...reshuffled];
      disc = [top];
    }
    const drawn = d.splice(0, count);
    return { drawn, newDeck: d, newDiscard: disc };
  }, []);

  // ─── Start Game ─────────────────────────────────────────────────────────────

  const startGame = useCallback(() => {
    const freshDeck = buildDeck();
    const pHand = freshDeck.splice(0, 5);
    const aHand = freshDeck.splice(0, 5);
    let startIdx = freshDeck.findIndex((c) => c.color !== "wild");
    if (startIdx < 0) startIdx = 0;
    const [startCard] = freshDeck.splice(startIdx, 1);
    setDeck(freshDeck);
    setPlayerHand(pHand);
    setAiHand(aHand);
    setDiscardPile([startCard]);
    setCurrentColor(startCard.color === "wild" ? "red" : startCard.color);
    setIsPlayerTurn(true);
    setPendingCard(null);
    setPendingColorCard(null);
    setCurrentQuestion(null);
    setQuestionResult(null);
    setMessage("Your turn! Play a card or draw.");
    setUnoShouted(false);
    setUsedQIndices([]);
    setPhase("playing");
  }, []);

  // ─── Apply Card Effect (after correct answer or for AI) ──────────────────────

  const applyEffect = useCallback((
    card: UnoCard,
    chosenColor: UnoColor,
    curDeck: UnoCard[],
    curAiHand: UnoCard[],
    curDiscard: UnoCard[],
    newPlayerHand: UnoCard[]
  ) => {
    let newDeck = [...curDeck];
    let newAiHand = [...curAiHand];
    let newDiscard = [...curDiscard, card];
    let msg = "";
    let skipAiTurn = false;

    if (card.value === "skip") {
      msg = "AI's turn is skipped!";
      skipAiTurn = true;
    } else if (card.value === "reverse") {
      msg = "Reversed! AI is skipped.";
      skipAiTurn = true;
    } else if (card.value === "draw2") {
      const { drawn, newDeck: nd, newDiscard: ndisc } = drawFromDeck(newDeck, newDiscard, 2);
      newDeck = nd; newDiscard = ndisc;
      newAiHand = [...newAiHand, ...drawn];
      msg = "AI draws 2 cards!";
      skipAiTurn = true;
    } else if (card.value === "wild4") {
      const { drawn, newDeck: nd, newDiscard: ndisc } = drawFromDeck(newDeck, newDiscard, 4);
      newDeck = nd; newDiscard = ndisc;
      newAiHand = [...newAiHand, ...drawn];
      msg = "Wild +4! AI draws 4.";
      skipAiTurn = true;
    } else if (card.value === "wild") {
      msg = "";
      skipAiTurn = false;
    }

    const colorMsg = card.value === "wild" || card.value === "wild4"
      ? ` Color: ${COLOR_LABEL[chosenColor]}.` : "";

    setDeck(newDeck);
    setAiHand(newAiHand);
    setDiscardPile(newDiscard);
    setCurrentColor(chosenColor);

    if (newPlayerHand.length === 0) {
      setPhase("playerWon");
      return;
    }

    if (skipAiTurn) {
      setMessage(msg + colorMsg + " Your turn again!");
      setIsPlayerTurn(true);
    } else {
      setMessage((msg + colorMsg).trim() || "AI's turn...");
      setIsPlayerTurn(false);
    }
  }, [drawFromDeck]);

  // ─── Play Card ───────────────────────────────────────────────────────────────

  const playCard = useCallback((card: UnoCard) => {
    if (phase !== "playing" || !isPlayerTurn) return;
    const topCard = discardPile[discardPile.length - 1];
    if (!isPlayable(card, topCard, currentColor)) {
      setMessage("That card can't be played right now.");
      return;
    }

    const newHand = playerHand.filter((c) => c.id !== card.id);

    if (isSpecialValue(card.value)) {
      const { q, idx } = pickQuestion(usedQIndices);
      setCurrentQuestion(q);
      setUsedQIndices((prev) => [...prev, idx]);
      setPendingCard(card);
      pendingPlayerHandRef.current = newHand;
      setQuestionResult(null);
      setPhase("question");
    } else {
      setPlayerHand(newHand);
      const newDiscard = [...discardPile, card];
      const newColor = card.color === "wild" ? currentColor : card.color;
      setDiscardPile(newDiscard);
      setCurrentColor(newColor);
      if (newHand.length === 0) { setPhase("playerWon"); return; }
      setMessage("AI's turn...");
      setIsPlayerTurn(false);
    }
  }, [phase, isPlayerTurn, discardPile, currentColor, playerHand, usedQIndices, pickQuestion]);

  // ─── Answer Question ─────────────────────────────────────────────────────────

  const answerQuestion = useCallback((chosenIdx: number) => {
    if (!currentQuestion || !pendingCard || questionResult !== null) return;
    const correct = chosenIdx === currentQuestion.answer;
    setQuestionResult(correct ? "correct" : "wrong");

    setTimeout(() => {
      setQuestionResult(null);
      setCurrentQuestion(null);

      if (!correct) {
        setPlayerHand([...pendingPlayerHandRef.current, pendingCard]);
        setPendingCard(null);
        setMessage("Not quite! Card returned to hand. Your turn.");
        setPhase("playing");
        setIsPlayerTurn(true);
        return;
      }

      if (pendingCard.value === "wild" || pendingCard.value === "wild4") {
        setPlayerHand(pendingPlayerHandRef.current);
        setPendingColorCard(pendingCard);
        setPendingCard(null);
        setPhase("colorPick");
      } else {
        const newHand = pendingPlayerHandRef.current;
        setPlayerHand(newHand);
        const col = pendingCard.color === "wild" ? currentColorRef.current : pendingCard.color;
        applyEffect(pendingCard, col, deckRef.current, aiHandRef.current, discardRef.current, newHand);
        setPendingCard(null);
        setPhase("playing");
      }
    }, 1000);
  }, [currentQuestion, pendingCard, questionResult, applyEffect]);

  // ─── Color Pick ──────────────────────────────────────────────────────────────

  const pickColor = useCallback((col: UnoColor) => {
    if (!pendingColorCard) return;
    const newHand = playerHandRef.current;
    applyEffect(pendingColorCard, col, deckRef.current, aiHandRef.current, discardRef.current, newHand);
    setPendingColorCard(null);
    setPhase("playing");
  }, [pendingColorCard, applyEffect]);

  // ─── Draw Card ───────────────────────────────────────────────────────────────

  const drawCard = useCallback(() => {
    if (phase !== "playing" || !isPlayerTurn) return;
    const { drawn, newDeck, newDiscard } = drawFromDeck(deck, discardPile, 1);
    if (drawn.length === 0) { setMessage("No cards left to draw!"); return; }
    setDeck(newDeck);
    setDiscardPile(newDiscard);
    const drawnCard = drawn[0];
    const newHand = [...playerHand, drawnCard];
    setPlayerHand(newHand);
    const topCard = discardPile[discardPile.length - 1];
    if (isPlayable(drawnCard, topCard, currentColor)) {
      setMessage(`Drew ${valueLabelShort(drawnCard.value)} (${COLOR_LABEL[drawnCard.color]}) — playable!`);
    } else {
      setMessage(`Drew ${valueLabelShort(drawnCard.value)} — not playable. AI's turn.`);
      setIsPlayerTurn(false);
    }
  }, [phase, isPlayerTurn, deck, discardPile, playerHand, currentColor, drawFromDeck]);

  // ─── AI Turn ─────────────────────────────────────────────────────────────────

  useEffect(() => {
    if (phase !== "playing" || isPlayerTurn) return;

    const timer = setTimeout(() => {
      const ai = aiHandRef.current;
      const top = discardRef.current[discardRef.current.length - 1];
      const col = currentColorRef.current;

      const playable = ai.filter((c) => isPlayable(c, top, col));
      playable.sort((a, b) => (isSpecialValue(b.value) ? 1 : 0) - (isSpecialValue(a.value) ? 1 : 0));

      if (playable.length === 0) {
        const { drawn, newDeck, newDiscard } = drawFromDeck(deckRef.current, discardRef.current, 1);
        setDeck(newDeck);
        setDiscardPile(newDiscard);
        setAiHand([...ai, ...drawn]);
        setMessage("AI draws a card. Your turn!");
        setIsPlayerTurn(true);
        return;
      }

      const card = playable[0];
      const newAiHand = ai.filter((c) => c.id !== card.id);
      setAiHand(newAiHand);

      if (newAiHand.length === 0) {
        setDiscardPile([...discardRef.current, card]);
        setPhase("aiWon");
        return;
      }

      const chosenColor = card.color === "wild" ? colorMajority(newAiHand) : card.color;
      let newDeck = [...deckRef.current];
      let newDiscard = [...discardRef.current, card];
      let newColor = chosenColor;
      let skipPlayer = false;
      let msg = `AI played ${valueLabelShort(card.value)}`;

      if (card.value === "skip") {
        msg += " — your turn is skipped!";
        skipPlayer = true;
      } else if (card.value === "reverse") {
        msg += " — your turn is skipped!";
        skipPlayer = true;
      } else if (card.value === "draw2") {
        const { drawn, newDeck: nd, newDiscard: ndisc } = drawFromDeck(newDeck, newDiscard, 2);
        newDeck = nd; newDiscard = ndisc;
        setPlayerHand((ph) => [...ph, ...drawn]);
        msg += " — you draw 2!";
        skipPlayer = true;
      } else if (card.value === "wild4") {
        const { drawn, newDeck: nd, newDiscard: ndisc } = drawFromDeck(newDeck, newDiscard, 4);
        newDeck = nd; newDiscard = ndisc;
        setPlayerHand((ph) => [...ph, ...drawn]);
        msg += " — you draw 4!";
        skipPlayer = true;
      } else if (card.value === "wild") {
        msg += ` — color: ${COLOR_LABEL[chosenColor]}`;
      }

      setDeck(newDeck);
      setDiscardPile(newDiscard);
      setCurrentColor(newColor);

      if (skipPlayer) {
        setMessage(msg + " AI goes again...");
        setTimeout(() => setIsPlayerTurn(false), 100);
      } else {
        setMessage(msg + ". Your turn!");
        setIsPlayerTurn(true);
      }
    }, 800);

    return () => clearTimeout(timer);
  }, [phase, isPlayerTurn, drawFromDeck]);

  // ─── Derived ─────────────────────────────────────────────────────────────────

  const topCard = discardPile.length > 0 ? discardPile[discardPile.length - 1] : null;
  const showUnoBtn = phase === "playing" && isPlayerTurn && playerHand.length === 2 && !unoShouted;

  // ─── Render Card ─────────────────────────────────────────────────────────────

  const renderCard = (card: UnoCard, onClick?: () => void, disabled?: boolean) => {
    const isWild = card.color === "wild";
    const label = valueLabelShort(card.value);
    return (
      <button
        key={card.id}
        onClick={onClick}
        disabled={disabled}
        className="uno-card"
        style={{
          background: isWild
            ? "linear-gradient(135deg, #dc2626 25%, #2563eb 25% 50%, #16a34a 50% 75%, #eab308 75%)"
            : COLOR_HEX[card.color],
          cursor: onClick && !disabled ? "pointer" : "default",
          opacity: disabled ? 0.5 : 1,
        }}
        title={`${COLOR_LABEL[card.color]} ${label}`}
      >
        <span className="uno-corner uno-corner-tl">{label}</span>
        <span className="uno-center">{label}</span>
        <span className="uno-corner uno-corner-br">{label}</span>
      </button>
    );
  };

  const renderBack = (i: number) => (
    <div key={i} className="uno-card uno-card-back">
      <span className="uno-back-label">UNO</span>
    </div>
  );

  // ─── JSX ─────────────────────────────────────────────────────────────────────

  return (
    <main className="container" style={{ maxWidth: 860 }}>
      <style>{css}</style>

      <div className="row" style={{ justifyContent: "space-between", marginBottom: 4 }}>
        <h1 style={{ margin: 0 }}>
          Uno Quiz{" "}
          <span style={{ fontSize: 14, color: "var(--muted)", verticalAlign: "middle" }}>
            {age.charAt(0).toUpperCase() + age.slice(1)} mode
          </span>
        </h1>
        <Link href="/arcade" className="muted" style={{ fontSize: 14 }}>
          &larr; Back to Arcade
        </Link>
      </div>

      {/* ── INTRO ── */}
      {phase === "intro" && (
        <div className="uno-overlay-box">
          <div style={{ fontSize: 52 }}>&#127183;</div>
          <h2 style={{ margin: "4px 0" }}>Uno Quiz</h2>
          <p className="muted" style={{ maxWidth: 420, textAlign: "center" }}>
            Play Uno against the AI! Number cards play freely. Special cards (Skip, Reverse,
            Draw 2, Wilds) require a correct trivia answer to activate. First to empty their
            hand wins!
          </p>
          <button onClick={startGame} className="uno-btn-primary">
            &#9654; Start Game
          </button>
        </div>
      )}

      {/* ── MAIN GAME ── */}
      {(phase === "playing" || phase === "question" || phase === "colorPick") && (
        <div style={{ position: "relative" }}>

          {/* AI Hand */}
          <div className="uno-section">
            <span className="muted" style={{ fontSize: 13, fontWeight: 600 }}>
              AI Hand &mdash; {aiHand.length} card{aiHand.length !== 1 ? "s" : ""}
              {aiHand.length === 1 ? " — UNO!" : ""}
            </span>
            <div className="uno-hand uno-hand-ai">
              {aiHand.map((_, i) => renderBack(i))}
            </div>
          </div>

          {/* Middle row */}
          <div className="uno-middle">
            {/* Draw pile */}
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
              <span className="muted" style={{ fontSize: 12 }}>Draw Pile ({deck.length})</span>
              <button
                className="uno-card uno-card-back uno-draw-btn"
                onClick={drawCard}
                disabled={phase !== "playing" || !isPlayerTurn}
                title="Draw a card"
              >
                <span className="uno-back-label">UNO</span>
              </button>
            </div>

            {/* Discard pile */}
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
              <span className="muted" style={{ fontSize: 12 }}>Discard</span>
              {topCard && renderCard(topCard)}
              <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 2 }}>
                <div style={{
                  width: 14, height: 14, borderRadius: "50%",
                  background: COLOR_HEX[currentColor],
                  border: "2px solid var(--border)",
                }} />
                <span className="muted" style={{ fontSize: 12 }}>
                  {COLOR_LABEL[currentColor]}
                </span>
              </div>
            </div>

            {/* Status + UNO button */}
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 10, maxWidth: 180 }}>
              {showUnoBtn && (
                <button
                  className="uno-btn-uno"
                  onClick={() => { setUnoShouted(true); setMessage("UNO! Nice!"); }}
                >
                  UNO!
                </button>
              )}
              <div
                className="uno-message"
                style={{ color: isPlayerTurn ? "var(--text)" : "var(--muted)" }}
              >
                {isPlayerTurn ? "Your turn" : "AI thinking..."}{"\n"}{message}
              </div>
            </div>
          </div>

          {/* Player Hand */}
          <div className="uno-section">
            <span className="muted" style={{ fontSize: 13, fontWeight: 600 }}>
              Your Hand &mdash; {playerHand.length} card{playerHand.length !== 1 ? "s" : ""}
            </span>
            <div className="uno-hand">
              {playerHand.map((card) => {
                const playable = topCard ? isPlayable(card, topCard, currentColor) : false;
                const canPlay = phase === "playing" && isPlayerTurn && playable;
                return renderCard(card, canPlay ? () => playCard(card) : undefined, !canPlay);
              })}
              {playerHand.length === 0 && (
                <span className="muted" style={{ fontSize: 13 }}>No cards</span>
              )}
            </div>
            {isPlayerTurn && phase === "playing" && topCard &&
              !playerHand.some((c) => isPlayable(c, topCard, currentColor)) && (
              <p className="muted" style={{ fontSize: 12, margin: "4px 0 0" }}>
                No playable cards &mdash; click the draw pile to draw one.
              </p>
            )}
          </div>

          {/* ── QUESTION OVERLAY ── */}
          {phase === "question" && currentQuestion && (
            <div className="uno-overlay">
              <div className="uno-question-card">
                <p style={{ margin: "0 0 6px", fontSize: 13, color: "var(--muted)" }}>
                  Answer to play your{" "}
                  <strong style={{ color: pendingCard ? COLOR_HEX[pendingCard.color] : "var(--text)" }}>
                    {pendingCard ? valueLabelShort(pendingCard.value) : ""} card
                  </strong>:
                </p>
                <p style={{ margin: "0 0 18px", fontSize: 16, fontWeight: 700 }}>
                  {currentQuestion.q}
                </p>
                <div className="uno-options">
                  {currentQuestion.options.map((opt, i) => {
                    let bg: string = "var(--panel-2)";
                    let border = "1px solid var(--border)";
                    if (questionResult !== null && i === currentQuestion.answer) {
                      bg = "#16a34a"; border = "1px solid #16a34a";
                    }
                    return (
                      <button
                        key={i}
                        className="uno-option-btn"
                        style={{ background: bg, border }}
                        onClick={() => answerQuestion(i)}
                        disabled={questionResult !== null}
                      >
                        <span style={{ fontWeight: 700, marginRight: 8, opacity: 0.7 }}>
                          {["A", "B", "C", "D"][i]}.
                        </span>
                        {opt}
                      </button>
                    );
                  })}
                </div>
                {questionResult && (
                  <p style={{
                    marginTop: 14, fontWeight: 800, fontSize: 15,
                    color: questionResult === "correct" ? "#16a34a" : "#dc2626",
                  }}>
                    {questionResult === "correct"
                      ? "Correct! Card activates!"
                      : "Wrong! Card returns to your hand."}
                  </p>
                )}
              </div>
            </div>
          )}

          {/* ── COLOR PICK OVERLAY ── */}
          {phase === "colorPick" && (
            <div className="uno-overlay">
              <div className="uno-question-card" style={{ textAlign: "center" }}>
                <p style={{ fontWeight: 700, fontSize: 16, margin: "0 0 20px" }}>
                  Choose a color for your Wild:
                </p>
                <div className="uno-color-picker">
                  {(["red", "blue", "green", "yellow"] as UnoColor[]).map((col) => (
                    <button
                      key={col}
                      onClick={() => pickColor(col)}
                      className="uno-color-btn"
                      style={{ background: COLOR_HEX[col] }}
                    >
                      {COLOR_LABEL[col]}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── WIN SCREENS ── */}
      {phase === "playerWon" && (
        <div className="uno-overlay-box">
          <div style={{ fontSize: 52 }}>&#127942;</div>
          <h2 style={{ margin: "4px 0" }}>You Win!</h2>
          <p className="muted">You played all your cards. Well done!</p>
          <button onClick={startGame} className="uno-btn-primary">
            &#8635; Play Again
          </button>
        </div>
      )}

      {phase === "aiWon" && (
        <div className="uno-overlay-box">
          <div style={{ fontSize: 52 }}>&#129302;</div>
          <h2 style={{ margin: "4px 0" }}>AI Wins!</h2>
          <p className="muted">The AI emptied its hand. Try again!</p>
          <button onClick={startGame} className="uno-btn-primary">
            &#8635; Play Again
          </button>
        </div>
      )}

      <p className="muted" style={{ fontSize: 12, textAlign: "center", marginTop: 10 }}>
        Number cards play freely &middot; Special cards need a correct answer to activate
        &middot; Click the draw pile if no cards are playable
      </p>
    </main>
  );
}

// ─── CSS ──────────────────────────────────────────────────────────────────────

const css = `
.uno-card {
  position: relative;
  width: 72px;
  height: 108px;
  border-radius: 12px;
  border: 3px solid rgba(255,255,255,0.28);
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-weight: 900;
  box-shadow: 0 4px 12px rgba(0,0,0,0.35), inset 0 1px 0 rgba(255,255,255,0.2);
  transition: transform 0.1s ease, box-shadow 0.1s ease;
  padding: 0;
}
.uno-card:not([disabled]):hover {
  transform: translateY(-10px) scale(1.07);
  box-shadow: 0 14px 28px rgba(0,0,0,0.45);
  z-index: 3;
}
.uno-card:not([disabled]):active {
  transform: translateY(-2px) scale(0.96);
}
.uno-draw-btn:not([disabled]):hover {
  transform: scale(1.06);
  box-shadow: 0 8px 20px rgba(0,0,0,0.4), 0 0 0 3px #2563eb;
}
.uno-card-back {
  background: #1e3a5f !important;
  border: 3px solid #2563eb !important;
  cursor: default;
}
.uno-back-label {
  font-size: 16px;
  font-weight: 900;
  color: #ef4444;
  font-style: italic;
  letter-spacing: 1px;
  pointer-events: none;
}
.uno-corner {
  position: absolute;
  font-size: 12px;
  font-weight: 900;
  line-height: 1;
  text-shadow: 0 1px 3px rgba(0,0,0,0.5);
}
.uno-corner-tl { top: 5px; left: 7px; }
.uno-corner-br { bottom: 5px; right: 7px; transform: rotate(180deg); }
.uno-center {
  font-size: 1.9rem;
  font-weight: 900;
  text-shadow: 0 2px 6px rgba(0,0,0,0.45);
  pointer-events: none;
}
.uno-section {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin: 10px 0;
}
.uno-hand {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  min-height: 120px;
  align-items: flex-end;
  padding: 10px 12px;
  border-radius: 14px;
  background: var(--panel-2);
  border: 1px solid var(--border);
}
.uno-hand-ai .uno-card {
  width: 50px;
  height: 76px;
}
.uno-hand-ai .uno-back-label { font-size: 12px; }
.uno-middle {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 28px;
  padding: 16px 20px;
  border-radius: 14px;
  background: var(--panel-2);
  border: 1px solid var(--border);
  flex-wrap: wrap;
  margin: 6px 0;
}
.uno-message {
  font-size: 13px;
  font-weight: 600;
  text-align: center;
  white-space: pre-line;
  line-height: 1.4;
}
.uno-btn-primary {
  background: #dc2626;
  color: #fff;
  padding: 12px 30px;
  font-size: 16px;
  font-weight: 800;
  border-radius: 10px;
  border: none;
  cursor: pointer;
  transition: opacity 0.15s, transform 0.1s;
}
.uno-btn-primary:hover { opacity: 0.88; transform: scale(1.03); }
.uno-btn-uno {
  background: #eab308;
  color: #1a1100;
  padding: 8px 22px;
  font-size: 15px;
  font-weight: 900;
  border-radius: 8px;
  border: none;
  cursor: pointer;
  letter-spacing: 1px;
  animation: uno-pulse 0.75s ease-in-out infinite;
}
@keyframes uno-pulse {
  0%,100% { transform: scale(1); }
  50% { transform: scale(1.1); box-shadow: 0 0 16px rgba(234,179,8,0.6); }
}
.uno-overlay-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 14px;
  padding: 44px 24px;
  border-radius: 18px;
  background: var(--panel-2);
  border: 1px solid var(--border);
  text-align: center;
  min-height: 340px;
}
.uno-overlay {
  position: absolute;
  inset: 0;
  background: rgba(0,0,0,0.6);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10;
  border-radius: 14px;
  padding: 16px;
}
.uno-question-card {
  background: #0d1117;
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 24px 28px;
  max-width: 460px;
  width: 100%;
  box-shadow: 0 12px 40px rgba(0,0,0,0.7);
}
.uno-options {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.uno-option-btn {
  background: var(--panel-2);
  color: var(--text);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 11px 14px;
  text-align: left;
  font-size: 14px;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s;
}
.uno-option-btn:hover:not([disabled]) {
  border-color: #2563eb;
  background: rgba(37,99,235,0.14);
}
.uno-color-picker {
  display: flex;
  gap: 14px;
  justify-content: center;
  flex-wrap: wrap;
}
.uno-color-btn {
  width: 80px;
  height: 80px;
  border-radius: 12px;
  border: 3px solid rgba(255,255,255,0.22);
  color: #fff;
  font-weight: 800;
  font-size: 13px;
  cursor: pointer;
  transition: transform 0.12s ease, box-shadow 0.12s ease;
  box-shadow: 0 4px 12px rgba(0,0,0,0.3);
}
.uno-color-btn:hover {
  transform: scale(1.12);
  box-shadow: 0 8px 22px rgba(0,0,0,0.4);
}
@media (max-width: 600px) {
  .uno-card { width: 56px; height: 86px; }
  .uno-center { font-size: 1.4rem; }
  .uno-hand-ai .uno-card { width: 40px; height: 62px; }
  .uno-middle { gap: 14px; padding: 12px; }
  .uno-color-btn { width: 64px; height: 64px; font-size: 11px; }
}
`;

/** Arcade game links — mirrors the web /arcade hub (apps/web/app/arcade/page.tsx). */

export type ArcadeGameEntry = {
  id: string;
  label: string;
  emoji: string;
  /** Path on the web app, e.g. /arcade/jeopardy */
  path: string;
  /** Append ?age= — most games support age scaling on web. */
  ageParam?: boolean;
};

export type ArcadeSection = {
  id: string;
  title: string;
  subtitle: string;
  games: ArcadeGameEntry[];
};

export const ARCADE_SECTIONS: ArcadeSection[] = [
  {
    id: "native",
    title: "In-app games",
    subtitle: "Quizzes, speed rounds, and Potion Lab run inside the Salareen app.",
    games: [],
  },
  {
    id: "kids",
    title: "Kids' games",
    subtitle: "Jeopardy, kart racing, creature catching, and more.",
    games: [
      { id: "jeopardy", label: "Jeopardy!", emoji: "📺", path: "/arcade/jeopardy" },
      { id: "kart-race", label: "Kart Race", emoji: "🏎️", path: "/arcade/kart-race" },
      { id: "creature-catch", label: "Creature Catch", emoji: "🦊", path: "/arcade/creature-catch" },
      { id: "card-match", label: "Card Match", emoji: "🃏", path: "/arcade/card-match" },
      { id: "uno-quiz", label: "Uno Quiz", emoji: "🎴", path: "/arcade/uno-quiz" },
    ],
  },
  {
    id: "discovery",
    title: "Discovery games",
    subtitle: "Spot differences, find hidden items, and reveal artwork.",
    games: [
      { id: "spot-difference", label: "Spot the Difference", emoji: "🔍", path: "/arcade/spot-difference" },
      { id: "hidden-items", label: "Hidden Items", emoji: "🕵️", path: "/arcade/hidden-items" },
      { id: "photo-reveal", label: "Photo Reveal", emoji: "🖼️", path: "/arcade/photo-reveal" },
    ],
  },
  {
    id: "challenge-ai",
    title: "Challenge the AI",
    subtitle: "Quiz duels, board games, and number races vs the bot.",
    games: [
      { id: "challenge-ai", label: "AI hub", emoji: "🤖", path: "/arcade/challenge-ai" },
      { id: "quiz-duel", label: "Quiz Duel", emoji: "⚔️", path: "/arcade/challenge-ai/quiz-duel" },
      { id: "tic-tac-toe", label: "Tic-Tac-Toe", emoji: "⭕", path: "/arcade/challenge-ai/tic-tac-toe" },
      { id: "connect-four", label: "Connect Four", emoji: "🔴", path: "/arcade/challenge-ai/connect-four" },
      { id: "number-duel", label: "Number Duel", emoji: "🔢", path: "/arcade/challenge-ai/number-duel" },
      { id: "ai-duel", label: "AI Duel", emoji: "🧠", path: "/arcade/ai-duel" },
    ],
  },
  {
    id: "featured",
    title: "Featured arcade",
    subtitle: "Geometry, stocks, and classic learning engines.",
    games: [
      { id: "shape-stack", label: "Shape Stack", emoji: "📐", path: "/arcade/shape-stack" },
      { id: "shape-drop", label: "Shape Drop", emoji: "🧱", path: "/arcade/shape-drop" },
      { id: "geo-blocks", label: "Geo Blocks", emoji: "🧊", path: "/arcade/geo-blocks" },
      { id: "geometry-blocks", label: "Geometry Blocks", emoji: "🧩", path: "/arcade/geometry-blocks" },
      { id: "geometry-tetris", label: "Geometry Tetris", emoji: "🟦", path: "/arcade/geometry-tetris" },
      { id: "market-moves", label: "Market Moves", emoji: "📈", path: "/arcade/market-moves" },
      { id: "stocks", label: "Market Mogul", emoji: "💰", path: "/arcade/stocks" },
      { id: "stock-trader", label: "Stock Trader", emoji: "📊", path: "/arcade/stock-trader" },
      { id: "stock-rush", label: "Stock Rush", emoji: "💹", path: "/arcade/stock-rush" },
      { id: "market-catch", label: "Market Catch", emoji: "📉", path: "/arcade/market-catch" },
      { id: "cosmic-catch", label: "Cosmic Catch", emoji: "🪐", path: "/arcade/cosmic-catch" },
      { id: "solar-3d", label: "Solar Quiz · 3D", emoji: "🌌", path: "/arcade/solar-3d", ageParam: false },
    ],
  },
];

export function arcadeWebUrl(webBase: string, path: string, age = "teen"): string {
  const base = webBase.replace(/\/$/, "");
  const normalized = path.startsWith("/") ? path : `/${path}`;
  if (normalized.includes("/solar-3d")) {
    return `${base}${normalized}`;
  }
  const join = normalized.includes("?") ? "&" : "?";
  return `${base}${normalized}${join}age=${encodeURIComponent(age)}`;
}

/**
 * Full machine-vision arcade. Same games as the children webcam lab menu
 * (theodore_children_webcam_lab game_engine.GAME_MENU).
 */

export type VisionGame = {
  id: string;
  label: string;
  emoji: string;
};

export type VisionSection = {
  id: string;
  title: string;
  games: VisionGame[];
};

export const VISION_ARCADE: VisionSection[] = [
  {
    id: "learn",
    title: "Learn",
    games: [
      { id: "trace-letter", label: "Trace a letter", emoji: "✏️" },
      { id: "trace-picture", label: "Trace a picture", emoji: "🖼️" },
      { id: "color-picture", label: "Color the picture", emoji: "🎨" },
      { id: "connect-dots", label: "Connect the dots", emoji: "🔢" },
      { id: "trace-outline", label: "Trace the outline", emoji: "✒️" },
      { id: "say-letter", label: "Say the letter", emoji: "🔤" },
    ],
  },
  {
    id: "listen",
    title: "Listen",
    games: [
      { id: "repeat-after-me", label: "Repeat after me", emoji: "🔁" },
      { id: "pronounce-word", label: "Pronounce the word", emoji: "🗣️" },
      { id: "rhyme-time", label: "Say a rhyme", emoji: "🎵" },
      { id: "listen-answer", label: "Answer what you hear", emoji: "👂" },
      { id: "missing-word", label: "Say the missing word", emoji: "❓" },
      { id: "opposites", label: "Say the opposite", emoji: "↔️" },
      { id: "explain-it", label: "Explain it", emoji: "💬" },
      { id: "sum-it-up", label: "Sum it up", emoji: "📝" },
      { id: "prove-it", label: "Prove you understand", emoji: "✅" },
      { id: "story-order", label: "What happened first", emoji: "📖" },
      { id: "how-many", label: "How many did you hear", emoji: "#️⃣" },
      { id: "same-or-different", label: "Same or different", emoji: "👯" },
      { id: "finish-the-line", label: "Finish the line", emoji: "⏭️" },
      { id: "spell-aloud", label: "Spell what you hear", emoji: "🅰️" },
    ],
  },
  {
    id: "face",
    title: "Face & hands",
    games: [
      { id: "oh-behave", label: "Oh behave", emoji: "😜" },
      { id: "heart", label: "Make hearts", emoji: "💖" },
      { id: "idea", label: "I have an idea", emoji: "☝️" },
      { id: "fist-bump", label: "Fist bump", emoji: "👊" },
      { id: "wow", label: "Wow face", emoji: "😮" },
      { id: "blow-kiss", label: "Blow a kiss", emoji: "😘" },
      { id: "wink", label: "Wink challenge", emoji: "😉" },
      { id: "make-pose", label: "Make a hero pose", emoji: "🦸" },
      { id: "balloon", label: "Pop balloons", emoji: "🎈" },
      { id: "fish", label: "Catch flying fish", emoji: "🐟" },
      { id: "popcorn", label: "Catch popcorn", emoji: "🍿" },
    ],
  },
  {
    id: "move",
    title: "Move",
    games: [
      { id: "fruit-cut", label: "Fruit cut", emoji: "🍉" },
      { id: "air-drums", label: "Air drums", emoji: "🥁" },
      { id: "bird-flap", label: "Flap like a bird", emoji: "🐦" },
      { id: "head-bop", label: "Head bop", emoji: "🙂" },
      { id: "face-chase", label: "Face chase", emoji: "😳" },
      { id: "stand-sit", label: "Stand up, sit down", emoji: "🪑" },
      { id: "dance-freeze", label: "Dance freeze", emoji: "💃" },
      { id: "rainbow-reach", label: "Rainbow reach", emoji: "🌈" },
    ],
  },
];

export function visionGameIds(): string[] {
  return VISION_ARCADE.flatMap((section) => section.games.map((game) => game.id));
}

export function visionLabPath(gameId?: string): string {
  const params = new URLSearchParams({ embed: "mobile" });
  if (gameId) params.set("game", gameId);
  return `/children-lab?${params.toString()}`;
}

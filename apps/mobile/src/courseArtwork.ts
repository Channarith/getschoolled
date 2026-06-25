// Subject-aware poster URLs (mirrors apps/web/app/lib/courseArtwork.ts).

export type CoursePosterInput = {
  title?: string;
  category?: string;
  subject?: string;
  tags?: string[];
  format?: string;
  thumbnail?: string | null;
};

const POSTERS: Record<string, string> = {
  default: "1524995997473-0922192e7427",
  mathematics: "1596495577885-7b0216313667",
  science: "1532094349784-aa2b07712477",
  technology: "1517694712202-8f3797902a10",
  languages: "1524995997473-0922192e7427",
  history: "1539650116574-8a991d6ac6d0",
  business: "1542744173-8c3279b9b0a8",
  finance: "1611974789855-9c98a0f44d0a",
  wellness: "1506126613408-07c158377075",
  cooking: "1556910103-1c02745aae4d",
  geography: "1526778544-fe3699e2b0c0",
  sports: "1461896836934-ffe607f8210a",
  civics: "1577412647305-5365e4eee1d5",
  mindfulness: "1544367567-0f2fcb009e0b",
  arcade: "1511512578047-dfb632b44527",
  audio: "1478737270239-5880992794b7",
  live_class: "1588196749598-0e4a0a5a9843",
  ai: "1677442136019-21780ecad995",
  python: "1526374965328-7f61d4dc18c5",
  fractions: "1635072833038-7c9468ee2294",
  photosynthesis: "1416879595882-ce2fa732bc2c",
  english: "1456514295660-8ba4a0869efa",
  spanish: "1481627834876-b7833e8f5570",
};

const TITLE_RULES: [string, string][] = [
  ["photosynthesis", "photosynthesis"],
  ["fraction", "fractions"],
  ["python", "python"],
  ["ai fluency", "ai"],
  ["english", "english"],
  ["spanish", "spanish"],
  ["algebra", "mathematics"],
  ["chemistry", "science"],
  ["biology", "science"],
  ["history", "history"],
  ["finance", "finance"],
  ["wellness", "wellness"],
  ["business", "business"],
];

function unsplash(photoId: string): string {
  return `https://images.unsplash.com/photo-${photoId}?w=480&h=270&fit=crop&q=80&auto=format`;
}

function categoryKey(category: string, subject: string): string {
  const blob = `${category} ${subject}`.toLowerCase();
  if (blob.includes("math")) return "mathematics";
  if (blob.includes("science")) return "science";
  if (blob.includes("technology")) return "technology";
  if (blob.includes("language")) return "languages";
  if (blob.includes("history")) return "history";
  if (blob.includes("business")) return "business";
  return "";
}

export function coursePosterUrl(input: CoursePosterInput): string {
  const thumb = input.thumbnail;
  if (thumb && /^https?:\/\//.test(thumb)) return thumb;

  const hay = [input.title, input.category, input.subject, ...(input.tags || [])]
    .join(" ").toLowerCase();

  for (const [needle, key] of TITLE_RULES) {
    if (hay.includes(needle)) return unsplash(POSTERS[key] || POSTERS.default);
  }

  const cat = categoryKey(input.category || "", input.subject || "");
  if (cat && POSTERS[cat]) return unsplash(POSTERS[cat]);

  const fmt = (input.format || "").toLowerCase();
  if (fmt === "audio") return unsplash(POSTERS.audio);
  if (fmt === "live_class") return unsplash(POSTERS.live_class);
  if (fmt === "game") return unsplash(POSTERS.arcade);

  return unsplash(POSTERS.default);
}

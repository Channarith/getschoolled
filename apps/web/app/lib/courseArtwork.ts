// Subject-aware poster URLs for course cards (mirrors aoep_shared.course_artwork).

export type CoursePosterInput = {
  title?: string;
  category?: string;
  subject?: string;
  tags?: string[];
  format?: string;
  media_format?: string;
  thumbnail?: string | null;
};

const POSTERS: Record<string, string> = {
  default: "1503676260728-1c00da094a0b",
  mathematics: "1532012197267-da84d127e765",
  science: "1582719471384-894fbb16e074",
  technology: "1516321318423-f06f85e504b3",
  languages: "1481627834876-b7833e8f5570",
  history: "1568667256549-094345857637",
  business: "1522202176988-66273c2fd55f",
  finance: "1554224155-6726b3ff858f",
  wellness: "1571019613454-1cb2f99b2d8b",
  cooking: "1556909114-f6e7ad7d3136",
  geography: "1469474968028-56623f02e42e",
  sports: "1571019613454-1cb2f99b2d8b",
  civics: "1522202176988-66273c2fd55f",
  mindfulness: "1544367567-0f2fcb009e0b",
  arcade: "1611224923853-80b023f02d71",
  audio: "1493225457124-a3eb161ffa5f",
  live_class: "1509062522246-3755977927d7",
  ai: "1677442136019-21780ecad995",
  python: "1526374965328-7f61d4dc18c5",
  fractions: "1554475901-4538ddfbccc2",
  photosynthesis: "1542601906990-b4d3fb778b09",
  english: "1503676260728-1c00da094a0b",
  spanish: "1481627834876-b7833e8f5570",
};

const TITLE_RULES: [string, string][] = [
  ["photosynthesis", "photosynthesis"],
  ["fraction", "fractions"],
  ["python", "python"],
  ["ai fluency", "ai"],
  ["artificial intelligence", "ai"],
  ["machine learning", "ai"],
  ["english", "english"],
  ["spanish", "spanish"],
  ["algebra", "mathematics"],
  ["calculus", "mathematics"],
  ["chemistry", "science"],
  ["biology", "science"],
  ["history", "history"],
  ["finance", "finance"],
  ["wellness", "wellness"],
  ["meditat", "mindfulness"],
  ["cook", "cooking"],
  ["geograph", "geography"],
  ["business", "business"],
  ["sport", "sports"],
];

function unsplash(photoId: string, w = 480, h = 270): string {
  return `https://images.unsplash.com/photo-${photoId}?w=${w}&h=${h}&fit=crop&q=80&auto=format`;
}

export function defaultCoursePosterUrl(): string {
  return unsplash(POSTERS.default);
}

function categoryKey(category: string, subject: string): string {
  const blob = `${category} ${subject}`.toLowerCase();
  if (blob.includes("math")) return "mathematics";
  if (blob.includes("science")) return "science";
  if (blob.includes("technology")) return "technology";
  if (blob.includes("language")) return "languages";
  if (blob.includes("history")) return "history";
  if (blob.includes("business")) return "business";
  if (blob.includes("finance")) return "finance";
  if (blob.includes("wellness")) return "wellness";
  if (blob.includes("cook")) return "cooking";
  if (blob.includes("geograph")) return "geography";
  if (blob.includes("sport")) return "sports";
  if (blob.includes("civic")) return "civics";
  if (blob.includes("mindful")) return "mindfulness";
  return "";
}

function isCustomThumbnail(thumb: string): boolean {
  return /^(https?:\/\/|\/)/.test(thumb) && !thumb.includes("images.unsplash.com/");
}

export function coursePosterUrl(input: CoursePosterInput): string {
  const thumb = input.thumbnail;
  if (thumb && isCustomThumbnail(thumb)) return thumb;

  const hay = [
    input.title, input.category, input.subject, ...(input.tags || []),
  ].join(" ").toLowerCase();

  for (const [needle, key] of TITLE_RULES) {
    if (hay.includes(needle)) return unsplash(POSTERS[key] || POSTERS.default);
  }

  const cat = categoryKey(input.category || "", input.subject || "");
  if (cat && POSTERS[cat]) return unsplash(POSTERS[cat]);

  const fmt = (input.format || input.media_format || "").toLowerCase();
  if (fmt === "audio") return unsplash(POSTERS.audio);
  if (fmt === "live_class" || fmt === "interactive") return unsplash(POSTERS.live_class);
  if (fmt === "game") return unsplash(POSTERS.arcade);

  return unsplash(POSTERS.default);
}

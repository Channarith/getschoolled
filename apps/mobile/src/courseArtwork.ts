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
  default:           "1524995997946-a1176921f0c3", // open textbook on desk
  mathematics:       "1532012197267-da84d127e765",
  science:           "1582719471384-894fbb16e074",
  technology:        "1516321318423-f06f85e504b3",
  languages:         "1481627834876-b7833e8f5570",
  history:           "1568667256549-094345857637",
  business:          "1522202176988-66273c2fd55f",
  finance:           "1554224155-6726b3ff858f",
  wellness:          "1571019613454-1cb2f99b2d8b",
  cooking:           "1556909114-f6e7ad7d3136",
  nutrition:         "1490645935967-10de6ba17061",
  geography:         "1469474968028-56623f02e42e",
  sports:            "1461896836934-ffe607ba8211",
  civics:            "1499750310107-5702e5be0be7",
  mindfulness:       "1544367567-0f2fcb009e0b",
  arcade:            "1611224923853-80b023f02d71",
  audio:             "1493225457124-a3eb161ffa5f",
  live_class:        "1509062522246-3755977927d7",
  ai:                "1677442136019-21780ecad995",
  python:            "1526374965328-7f61d4dc18c5",
  programming:       "1526374965328-7f61d4dc18c5",
  fractions:         "1554475901-4538ddfbccc2",
  photosynthesis:    "1542601906990-b4d3fb778b09",
  english:           "1503676260728-1c00da094a0b",
  spanish:           "1481627834876-b7833e8f5570",
  psychology:        "1559757148-5c350d0d3c56",
  law:               "1589829545856-d10d557cf95f",
  music:             "1493225457124-a3eb161ffa5f",
  // Compliance & workplace safety
  "sexual harassment":"1521737604082-cef6ad4e2052",
  harassment:        "1521737604082-cef6ad4e2052",
  compliance:        "1589829545856-d10d557cf95f",
  osha:              "1578662996442-48f60103fc96",
  "fire safety":     "1544376664-80b17f09d399",
  "food safety":     "1567620905732-2d1ec7ab7445",
  hipaa:             "1576091160550-2173dba999ef",
  healthcare:        "1576091160550-2173dba999ef",
  nursing:           "1576091160550-2173dba999ef",
  "workplace ethics":"1521737604082-cef6ad4e2052",
  diversity:         "1529156069-d5a5ee5e8e26",
  // Nonprofit & social
  nonprofit:         "1529156069-d5a5ee5e8e26",
  advocacy:          "1529156069-d5a5ee5e8e26",
  fundraising:       "1529156069-d5a5ee5e8e26",
  parenting:         "1476703829951-26b5d83cf8d7",
  "child development":"1476703829951-26b5d83cf8d7",
  // Transport, safety, real estate
  driver:            "1449965408869-00c4efcebe50",
  driving:           "1449965408869-00c4efcebe50",
  automotive:        "1449965408869-00c4efcebe50",
  aviation:          "1436891620584-47fd0e3e04a9",
  "real estate":     "1560518883-ce09059eeffa",
  hvac:              "1517420879524-86d64ac2f339",
  "security guard":  "1555636222-cae831e670b3",
  emergency:         "1582719468-702e6f92f86b",
  "first responder": "1582719468-702e6f92f86b",
  cpr:               "1582719468-702e6f92f86b",
  // Leadership, communication
  leadership:        "1522202176988-66273c2fd55f",
  communication:     "1573497491208-6b1acb260507",
  // Design
  photography:       "1502920917128-1aa500764349",
  design:            "1561070791-2526d30994b5",
  marketing:         "1432888498266-38ffec3eaf0a",
};

const TITLE_RULES: [string, string][] = [
  ["photosynthesis",  "photosynthesis"],
  ["fraction",        "fractions"],
  ["python",          "python"],
  ["ai fluency",      "ai"],
  ["english",         "english"],
  ["spanish",         "spanish"],
  ["algebra",         "mathematics"],
  ["chemistry",       "science"],
  ["biology",         "science"],
  ["history",         "history"],
  ["finance",         "finance"],
  ["wellness",        "wellness"],
  ["business",        "business"],
  ["nutrition",       "nutrition"],
  ["cooking",         "cooking"],
  ["music",           "music"],
  ["psychology",      "psychology"],
  ["law",             "law"],
  ["legal",           "law"],
  // Compliance & safety
  ["sexual harass",   "sexual harassment"],
  ["harassment",      "harassment"],
  ["osha",            "osha"],
  ["fire safety",     "fire safety"],
  ["food safety",     "food safety"],
  ["food handler",    "food safety"],
  ["food handling",   "food safety"],
  ["hipaa",           "hipaa"],
  ["nursing",         "nursing"],
  ["pharmacy",        "nursing"],
  ["medical",         "healthcare"],
  ["healthcare",      "healthcare"],
  ["workplace ethics","workplace ethics"],
  ["diversity",       "diversity"],
  // Nonprofit & parenting
  ["nonprofit",       "nonprofit"],
  ["non-profit",      "nonprofit"],
  ["advocacy",        "advocacy"],
  ["fundrais",        "fundraising"],
  ["donor",           "nonprofit"],
  ["grant writ",      "nonprofit"],
  ["parenting",       "parenting"],
  ["child develop",   "child development"],
  ["early childhood", "child development"],
  // Transport, safety, real estate
  ["driver",          "driver"],
  ["driving",         "driving"],
  ["automotive",      "automotive"],
  ["aviation",        "aviation"],
  ["real estate",     "real estate"],
  ["hvac",            "hvac"],
  ["security guard",  "security guard"],
  ["situational",     "security guard"],
  ["emergency",       "emergency"],
  ["first respond",   "first responder"],
  ["cpr",             "cpr"],
  // Leadership & communication
  ["leadership",      "leadership"],
  ["communic",        "communication"],
  ["public speak",    "communication"],
  ["negotiat",        "communication"],
  ["decision mak",    "communication"],
  // Design & marketing
  ["photograph",      "photography"],
  ["ux design",       "design"],
  ["digital market",  "marketing"],
];

function unsplash(photoId: string): string {
  return `https://images.unsplash.com/photo-${photoId}?w=480&h=270&fit=crop&q=80&auto=format`;
}

function isCustomThumbnail(thumb: string): boolean {
  return /^https?:\/\//.test(thumb) && !thumb.includes("images.unsplash.com/");
}

function categoryKey(category: string, subject: string): string {
  const blob = `${category} ${subject}`.toLowerCase();
  // Compliance / safety (check before generic terms)
  if (blob.includes("sexual harass") || blob.includes("harassment")) return "sexual harassment";
  if (blob.includes("osha") || blob.includes("forklift")) return "osha";
  if (blob.includes("fire safety") || blob.includes("fire prevention")) return "fire safety";
  if (blob.includes("food safety") || blob.includes("food handler")) return "food safety";
  if (blob.includes("hipaa")) return "hipaa";
  if (blob.includes("nursing") || blob.includes("pharmacy") || blob.includes("healthcare")) return "healthcare";
  if (blob.includes("workplace ethics") || blob.includes("ethics")) return "workplace ethics";
  if (blob.includes("diversity") || blob.includes("equity") || blob.includes("inclusion")) return "diversity";
  if (blob.includes("compliance")) return "compliance";
  if (blob.includes("security guard") || blob.includes("situational aware")) return "security guard";
  if (blob.includes("emergency") || blob.includes("first respond") || blob.includes("cpr")) return "emergency";
  // Nonprofit & social
  if (blob.includes("nonprofit") || blob.includes("non-profit") || blob.includes("advocacy") || blob.includes("fundrais")) return "nonprofit";
  if (blob.includes("parenting") || blob.includes("child develop") || blob.includes("early childhood")) return "parenting";
  // Transport & real estate
  if (blob.includes("driver") || blob.includes("driving") || blob.includes("automotive")) return "driver";
  if (blob.includes("aviation") || blob.includes("flight") || blob.includes("ifr")) return "aviation";
  if (blob.includes("real estate")) return "real estate";
  if (blob.includes("hvac")) return "hvac";
  // Leadership & communication
  if (blob.includes("leadership")) return "leadership";
  if (blob.includes("communic") || blob.includes("public speak") || blob.includes("negotiat")) return "communication";
  // Standard subjects
  if (blob.includes("math")) return "mathematics";
  if (blob.includes("science")) return "science";
  if (blob.includes("technology")) return "technology";
  if (blob.includes("language")) return "languages";
  if (blob.includes("history")) return "history";
  if (blob.includes("business")) return "business";
  if (blob.includes("finance") || blob.includes("accounting")) return "finance";
  if (blob.includes("nutrition") || blob.includes("food & bev")) return "nutrition";
  if (blob.includes("cook")) return "cooking";
  if (blob.includes("music")) return "music";
  if (blob.includes("psychology")) return "psychology";
  if (blob.includes("law") || blob.includes("legal")) return "law";
  if (blob.includes("wellness") || blob.includes("wellbeing")) return "wellness";
  if (blob.includes("geography")) return "geography";
  if (blob.includes("sport")) return "sports";
  return "";
}

export function coursePosterUrl(input: CoursePosterInput): string {
  const thumb = input.thumbnail;
  if (thumb && isCustomThumbnail(thumb)) return thumb;

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

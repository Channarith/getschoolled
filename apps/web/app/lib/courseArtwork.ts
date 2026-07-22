// Subject-aware poster URLs + inline data-URLs for kids/arcade content.
// Strategy:
//   1. Custom thumbnail stored on the course → use it directly
//   2. Kids or arcade format → cartoon-style gradient data-URL (no external CDN needed)
//   3. Everything else → best-matching Unsplash photo by subject/title/category

export type CoursePosterInput = {
  title?: string;
  category?: string;
  subject?: string;
  tags?: string[];
  format?: string;
  media_format?: string;
  thumbnail?: string | null;
  maturity_rating?: string | null;
};

// ── Unsplash photo IDs keyed by subject ────────────────────────────────────
const POSTERS: Record<string, string> = {
  default:          "1524995997946-a1176921f0c3",   // open textbook on desk (neutral)
  mathematics:      "1635070041078-e363dbe005cb",   // chalkboard with equations
  algebra:          "1635070041078-e363dbe005cb",
  calculus:         "1635070041078-e363dbe005cb",
  geometry:         "1635070041078-e363dbe005cb",
  trigonometry:     "1635070041078-e363dbe005cb",
  statistics:       "1551288049-bebda4e38f71",       // data charts
  science:          "1582719471384-894fbb16e074",   // lab
  biology:          "1530026186672-2cd00ffc50d3",   // cells
  chemistry:        "1603126857599-f6e75efa8dbe",   // flasks
  physics:          "1446776811953-b23d57bd21aa",   // galaxy
  astronomy:        "1446776811953-b23d57bd21aa",
  space:            "1446776811953-b23d57bd21aa",
  technology:       "1516321318423-f06f85e504b3",   // code on screen
  programming:      "1526374965328-7f61d4dc18c5",   // code close-up
  python:           "1526374965328-7f61d4dc18c5",
  javascript:       "1516321318423-f06f85e504b3",
  "data science":   "1551288049-bebda4e38f71",
  "power bi":       "1551288049-bebda4e38f71",
  ai:               "1677442136019-21780ecad995",   // neural net glow
  "machine learning": "1677442136019-21780ecad995",
  "deep learning":  "1677442136019-21780ecad995",
  devops:           "1618401471353-b98afee0b2eb",   // server rack
  cybersecurity:    "1550751827-4bd374c3f58b",       // digital lock
  "it fundamentals":"1461749280684-dccba630e2f6",   // laptop setup
  sap:              "1461749280684-dccba630e2f6",
  "project management": "1454165804606-c3d57bc86b40", // planning board
  languages:        "1481627834876-b7833e8f5570",   // globe / books
  history:          "1568667256549-094345857637",   // old map
  geography:        "1469474968028-56623f02e42e",   // world map
  business:         "1522202176988-66273c2fd55f",   // boardroom
  finance:          "1554224155-6726b3ff858f",       // coins / charts
  economics:        "1554224155-6726b3ff858f",
  "microeconomics": "1554224155-6726b3ff858f",
  "macroeconomics": "1554224155-6726b3ff858f",
  investing:        "1611974789855-9c2a0a7236a3",
  cryptocurrency:   "1639762681485-074b7f938ba0",
  "digital marketing": "1432888498266-38ffec3eaf0a", // phone / social
  "ux design":      "1561070791-2526d30994b5",       // wireframe
  "personal wellbeing": "1571019613454-1cb2f99b2d8b",
  wellness:         "1571019613454-1cb2f99b2d8b",
  cooking:          "1556909114-f6e7ad7d3136",
  nutrition:        "1490645935967-10de6ba17061",
  "arts & culture": "1579783902614-a3fb3927b6a5",   // art gallery
  film:             "1485846234645-a62644f84728",   // cinema
  music:            "1493225457124-a3eb161ffa5f",   // headphones / music
  "world cultures": "1523731407965-2430cd12f5e4",   // diversity
  civics:           "1499750310107-5702e5be0be7",
  sports:           "1461896836934-ffe607ba8211",
  "focus & philosophy": "1544367567-0f2fcb009e0b",
  "true stories & biographies": "1457369804613-52c61a468e7d",
  "productivity & study": "1434030216411-0b793f4b4173",
  entrepreneurship: "1519389950473-47ba0277781c",
  law:              "1589829545856-d10d557cf95f",
  architecture:     "1486325212027-8081e485255e",
  engineering:      "1517420879524-86d64ac2f339",
  psychology:       "1559757148-5c350d0d3c56",
  writing:          "1455390582262-044cdead277a",
  environment:      "1441974231531-c6227db76b6e",
  "social sciences":"1521737604082-cef6ad4e2052",
  language:         "1481627834876-b7833e8f5570",
  "personal development": "1544367567-0f2fcb009e0b",
  fractions:        "1554475901-4538ddfbccc2",
  photosynthesis:   "1542601906990-b4d3fb778b09",
  english:          "1503676260728-1c00da094a0b",
  spanish:          "1481627834876-b7833e8f5570",
  live_class:       "1509062522246-3755977927d7",   // classroom
  audio:            "1493225457124-a3eb161ffa5f",
  "microsoft excel":"1551288049-bebda4e38f71",
  "microsoft word": "1455390582262-044cdead277a",
  "microsoft powerpoint": "1516321318423-f06f85e504b3",
  // ── Compliance & Workplace Safety ───────────────────────────────────────
  "sexual harassment": "1521737604082-cef6ad4e2052",  // professional workplace
  harassment:         "1521737604082-cef6ad4e2052",
  compliance:         "1589829545856-d10d557cf95f",   // gavel / legal
  osha:               "1578662996442-48f60103fc96",   // hard hat / safety
  "fire safety":      "1544376664-80b17f09d399",      // fire extinguisher
  "food safety":      "1567620905732-2d1ec7ab7445",   // food handling / kitchen
  "food handler":     "1567620905732-2d1ec7ab7445",
  hipaa:              "1576091160550-2173dba999ef",   // medical / healthcare
  healthcare:         "1576091160550-2173dba999ef",
  nursing:            "1576091160550-2173dba999ef",
  pharmacy:           "1576091160550-2173dba999ef",
  medical:            "1576091160550-2173dba999ef",
  "workplace ethics": "1521737604082-cef6ad4e2052",
  ethics:             "1521737604082-cef6ad4e2052",
  "diversity":        "1529156069-d5a5ee5e8e26",      // diverse group of people
  "equity":           "1529156069-d5a5ee5e8e26",
  dei:                "1529156069-d5a5ee5e8e26",
  // ── Nonprofit, Parenting & Social Categories ────────────────────────────
  nonprofit:          "1529156069-d5a5ee5e8e26",      // community / people
  "nonprofit management": "1529156069-d5a5ee5e8e26",
  advocacy:           "1529156069-d5a5ee5e8e26",
  fundraising:        "1529156069-d5a5ee5e8e26",
  parenting:          "1476703829951-26b5d83cf8d7",   // parent and child
  "child development":"1476703829951-26b5d83cf8d7",
  "family":           "1476703829951-26b5d83cf8d7",
  // ── Automotive, Transport & Safety Certs ────────────────────────────────
  "driver":           "1449965408869-00c4efcebe50",   // car dashboard / road
  driving:            "1449965408869-00c4efcebe50",
  automotive:         "1449965408869-00c4efcebe50",
  aviation:           "1436891620584-47fd0e3e04a9",   // cockpit / plane
  "real estate":      "1560518883-ce09059eeffa",      // house / property
  hvac:               "1517420879524-86d64ac2f339",   // engineering / technical
  "security guard":   "1555636222-cae831e670b3",      // security professional
  "situational awareness": "1555636222-cae831e670b3",
  "emergency":        "1582719468-702e6f92f86b",      // first responders
  "first responder":  "1582719468-702e6f92f86b",
  cpr:                "1582719468-702e6f92f86b",
  // ── Leadership, HR, Communication ───────────────────────────────────────
  leadership:         "1522202176988-66273c2fd55f",   // meeting / boardroom
  communication:      "1573497491208-6b1acb260507",   // people talking
  "public speaking":  "1573497491208-6b1acb260507",
  negotiation:        "1573497491208-6b1acb260507",
  "decision making":  "1573497491208-6b1acb260507",
  "rapid decision":   "1573497491208-6b1acb260507",
  // ── Digital & Design ────────────────────────────────────────────────────
  photography:        "1502920917128-1aa500764349",   // camera
  design:             "1561070791-2526d30994b5",      // wireframe / design
  marketing:          "1432888498266-38ffec3eaf0a",   // social media / phone
};

// ── Keyword → poster key rules (checked in order against full title+category+tags blob) ─
const TITLE_RULES: [string, string][] = [
  ["photosynthesis", "photosynthesis"],
  ["fraction",       "fractions"],
  ["python",         "python"],
  ["javascript",     "javascript"],
  ["sql",            "programming"],
  ["git ",           "programming"],
  ["devops",         "devops"],
  ["cyber",          "cybersecurity"],
  ["sap ",           "sap"],
  ["power bi",       "power bi"],
  ["powerbi",        "power bi"],
  ["project manag",  "project management"],
  ["digital market", "digital marketing"],
  ["ux design",      "ux design"],
  ["ai fluency",     "ai"],
  ["artificial intelligence", "ai"],
  ["machine learning", "machine learning"],
  ["deep learning",  "deep learning"],
  ["neural network", "deep learning"],
  ["algebra",        "algebra"],
  ["calculus",       "calculus"],
  ["geometry",       "geometry"],
  ["trigonometry",   "trigonometry"],
  ["statistics",     "statistics"],
  ["differential equations", "mathematics"],
  ["linear algebra", "mathematics"],
  ["number theory",  "mathematics"],
  ["math olympiad",  "mathematics"],
  ["problem solving math", "mathematics"],
  ["arithmetic",     "mathematics"],
  ["microeconomics", "microeconomics"],
  ["macroeconomics", "macroeconomics"],
  ["economics",      "economics"],
  ["cryptocurrency", "cryptocurrency"],
  ["blockchain",     "cryptocurrency"],
  ["investing",      "investing"],
  ["english",        "english"],
  ["spanish",        "spanish"],
  ["chemistry",      "chemistry"],
  ["biology",        "biology"],
  ["physics",        "physics"],
  ["astronomy",      "astronomy"],
  ["space",          "space"],
  ["history",        "history"],
  ["finance",        "finance"],
  ["business",       "business"],
  ["well",           "wellness"],
  ["cook",           "cooking"],
  ["nutrition",      "nutrition"],
  ["geograph",       "geography"],
  ["sport",          "sports"],
  ["civic",          "civics"],
  ["music",          "music"],
  ["film",           "film"],
  ["cinema",         "film"],
  ["psychology",     "psychology"],
  ["writing",        "writing"],
  ["architect",      "architecture"],
  ["engineer",       "engineering"],
  ["law",            "law"],
  ["legal",          "law"],
  ["environment",    "environment"],
  ["sustainab",      "environment"],
  ["entrepreneurship", "entrepreneurship"],
  ["excel",          "microsoft excel"],
  ["word ",          "microsoft word"],
  ["powerpoint",     "microsoft powerpoint"],
  // Compliance & workplace safety
  ["sexual harass",  "sexual harassment"],
  ["harassment",     "harassment"],
  ["osha",           "osha"],
  ["fire safety",    "fire safety"],
  ["fire extinguish","fire safety"],
  ["food safety",    "food safety"],
  ["food handler",   "food handler"],
  ["food handling",  "food safety"],
  ["hipaa",          "hipaa"],
  ["nursing",        "nursing"],
  ["pharmacy",       "pharmacy"],
  ["medical ",       "medical"],
  ["healthcare",     "healthcare"],
  ["workplace ethics","workplace ethics"],
  ["diversity",      "diversity"],
  ["equity inclus",  "equity"],
  // Nonprofit & social
  ["nonprofit",      "nonprofit"],
  ["non-profit",     "nonprofit"],
  ["advocacy",       "advocacy"],
  ["fundrais",       "fundraising"],
  ["donor",          "nonprofit"],
  ["grant writ",     "nonprofit"],
  ["volunteer",      "nonprofit"],
  ["parenting",      "parenting"],
  ["child develop",  "child development"],
  ["early childhood","child development"],
  // Transport, safety, real estate
  ["driver",         "driver"],
  ["driving",        "driving"],
  ["automotive",     "automotive"],
  ["aviation",       "aviation"],
  ["flight",         "aviation"],
  ["real estate",    "real estate"],
  ["hvac",           "hvac"],
  ["security guard", "security guard"],
  ["situational aware","situational awareness"],
  ["emergency",      "emergency"],
  ["first respond",  "first responder"],
  ["cpr",            "cpr"],
  // Leadership, communication
  ["leadership",     "leadership"],
  ["communic",       "communication"],
  ["public speak",   "public speaking"],
  ["negotiat",       "negotiation"],
  ["decision mak",   "decision making"],
  // Design, photography, marketing
  ["photograph",     "photography"],
  ["ux design",      "ux design"],
  ["digital market", "digital marketing"],
];

// ── Cartoon-style gradient poster for kids / arcade (pure CSS, no CDN) ─────
// Returns a data-URL SVG so it works fully offline and looks kid-friendly.

type GradientSpec = { from: string; to: string; emoji: string; label?: string };

const ARCADE_SPECS: Record<string, GradientSpec> = {
  jeopardy:    { from: "#1e3a8a", to: "#1d4ed8", emoji: "📺" },
  kart:        { from: "#dc2626", to: "#f59e0b", emoji: "🏎️" },
  racing:      { from: "#dc2626", to: "#f59e0b", emoji: "🏎️" },
  creature:    { from: "#7c3aed", to: "#ec4899", emoji: "🦊" },
  pokemon:     { from: "#7c3aed", to: "#ec4899", emoji: "🦊" },
  "card match":{ from: "#0f766e", to: "#0ea5e9", emoji: "🃏" },
  "uno quiz":  { from: "#dc2626", to: "#f59e0b", emoji: "🎴" },
  uno:         { from: "#dc2626", to: "#f59e0b", emoji: "🎴" },
  "cosmic catch":{ from: "#0ea5e9", to: "#6d28d9", emoji: "🪐" },
  "solar quiz":{ from: "#1e3a8a", to: "#0ea5e9", emoji: "🌌" },
  "potion lab":{ from: "#059669", to: "#047857", emoji: "⚗️" },
  chemistry:   { from: "#059669", to: "#047857", emoji: "⚗️" },
  "geo blocks":{ from: "#4338ca", to: "#6366f1", emoji: "🧊" },
  "shape drop":{ from: "#4f46e5", to: "#6366f1", emoji: "🧱" },
  "connect four":{ from: "#b91c1c", to: "#dc2626", emoji: "🔴" },
  "tic tac toe":{ from: "#0284c7", to: "#0ea5e9", emoji: "⭕" },
  "number duel":{ from: "#ea580c", to: "#f59e0b", emoji: "⚡" },
  "quiz duel": { from: "#7c3aed", to: "#a855f7", emoji: "⚔️" },
  "ai duel":   { from: "#a855f7", to: "#6d28d9", emoji: "🧠" },
  "market":    { from: "#059669", to: "#047857", emoji: "📈" },
  "stock":     { from: "#0f766e", to: "#115e59", emoji: "💰" },
};

const KIDS_SUBJECT_SPECS: Record<string, GradientSpec> = {
  alphabet:    { from: "#7c3aed", to: "#ec4899", emoji: "🔤" },
  phonics:     { from: "#7c3aed", to: "#ec4899", emoji: "🅰️" },
  reading:     { from: "#db2777", to: "#f59e0b", emoji: "📖" },
  writing:     { from: "#ea580c", to: "#facc15", emoji: "✏️" },
  clock:       { from: "#0284c7", to: "#22d3ee", emoji: "🕰️" },
  animals:     { from: "#15803d", to: "#84cc16", emoji: "🦁" },
  objects:     { from: "#c026d3", to: "#f472b6", emoji: "🧸" },
  "connect-the-dots": { from: "#0891b2", to: "#6366f1", emoji: "✨" },
  shapes:      { from: "#4f46e5", to: "#ec4899", emoji: "🔷" },
  math:        { from: "#7c3aed", to: "#0ea5e9", emoji: "🔢" },
  science:     { from: "#059669", to: "#0ea5e9", emoji: "🔬" },
  history:     { from: "#b45309", to: "#d97706", emoji: "📜" },
  geography:   { from: "#0369a1", to: "#0ea5e9", emoji: "🌍" },
  language:    { from: "#dc2626", to: "#f59e0b", emoji: "🗣️" },
  art:         { from: "#ec4899", to: "#f59e0b", emoji: "🎨" },
  music:       { from: "#7c3aed", to: "#ec4899", emoji: "🎵" },
  cooking:     { from: "#d97706", to: "#dc2626", emoji: "🍳" },
  sports:      { from: "#059669", to: "#16a34a", emoji: "⚽" },
  wellness:    { from: "#0ea5e9", to: "#6d28d9", emoji: "🌟" },
  nature:      { from: "#15803d", to: "#0ea5e9", emoji: "🌿" },
  space:       { from: "#1e3a8a", to: "#7c3aed", emoji: "🚀" },
  kids:        { from: "#ec4899", to: "#f59e0b", emoji: "🎉" },
};

function makeCartoonSvg(spec: GradientSpec): string {
  const { from: f, to: t, emoji } = spec;
  const svg = `<svg xmlns='http://www.w3.org/2000/svg' width='480' height='270'>
    <defs>
      <linearGradient id='g' x1='0%' y1='0%' x2='100%' y2='100%'>
        <stop offset='0%' style='stop-color:${f}'/>
        <stop offset='100%' style='stop-color:${t}'/>
      </linearGradient>
      <filter id='blur'><feGaussianBlur stdDeviation='18'/></filter>
    </defs>
    <rect width='480' height='270' fill='url(#g)'/>
    <circle cx='380' cy='50' r='80' fill='white' opacity='0.07' filter='url(#blur)'/>
    <circle cx='80' cy='220' r='60' fill='white' opacity='0.05' filter='url(#blur)'/>
    <text x='50%' y='54%' font-size='82' text-anchor='middle' dominant-baseline='middle'
      font-family='Apple Color Emoji,Segoe UI Emoji,sans-serif'>${emoji}</text>
  </svg>`;
  return `data:image/svg+xml,${encodeURIComponent(svg)}`;
}

function arcadeSpec(hay: string): GradientSpec | null {
  for (const [key, spec] of Object.entries(ARCADE_SPECS)) {
    if (hay.includes(key)) return spec;
  }
  return null;
}

function kidsSubjectSpec(hay: string): GradientSpec | null {
  for (const [key, spec] of Object.entries(KIDS_SUBJECT_SPECS)) {
    if (hay.includes(key)) return spec;
  }
  return KIDS_SUBJECT_SPECS.kids;
}

// ── Helpers ─────────────────────────────────────────────────────────────────

function unsplash(photoId: string, w = 480, h = 270): string {
  return `https://images.unsplash.com/photo-${photoId}?w=${w}&h=${h}&fit=crop&q=80&auto=format`;
}

export function defaultCoursePosterUrl(): string {
  return unsplash(POSTERS.default);
}

function isCustomThumbnail(thumb: string): boolean {
  return /^(https?:\/\/|\/)/.test(thumb) && !thumb.includes("images.unsplash.com/");
}

// ── Main resolver ────────────────────────────────────────────────────────────

export function coursePosterUrl(input: CoursePosterInput): string {
  const thumb = input.thumbnail;
  const fmt = (input.format || input.media_format || "").toLowerCase();
  const hay = [input.title, input.category, input.subject, ...(input.tags ?? [])]
    .join(" ").toLowerCase();

  // Kids courses always get bright pictorial artwork. This check deliberately
  // precedes the backend thumbnail fallback, which may be a generic adult photo.
  if (input.maturity_rating === "kids" || hay.includes("kids academ") || hay.includes("children")) {
    return makeCartoonSvg(kidsSubjectSpec(hay) ?? KIDS_SUBJECT_SPECS.kids);
  }

  if (thumb && isCustomThumbnail(thumb)) return thumb;

  // ── Arcade / game: cartoon gradient ──────────────────────────────────────
  if (fmt === "game" || hay.includes("arcade")) {
    const spec = arcadeSpec(hay);
    return makeCartoonSvg(spec ?? { from: "#7c3aed", to: "#0ea5e9", emoji: "🎮" });
  }

  // ── Title / tag rules (most specific first) ───────────────────────────────
  for (const [needle, key] of TITLE_RULES) {
    if (hay.includes(needle)) {
      const photoId = POSTERS[key];
      return photoId ? unsplash(photoId) : unsplash(POSTERS.default);
    }
  }

  // ── Category fallback ─────────────────────────────────────────────────────
  const catBlob = `${input.category ?? ""} ${input.subject ?? ""}`.toLowerCase();
  for (const [key, photoId] of Object.entries(POSTERS)) {
    if (key.length > 3 && catBlob.includes(key)) return unsplash(photoId);
  }

  // ── Format fallback ───────────────────────────────────────────────────────
  if (fmt === "audio") return unsplash(POSTERS.audio);
  if (fmt === "live_class" || fmt === "interactive") return unsplash(POSTERS.live_class);

  return unsplash(POSTERS.default);
}

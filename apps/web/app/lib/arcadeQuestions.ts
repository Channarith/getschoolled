// Client-side question banks for graphical arcade games (geometry blocks, market catch, AI duel).

export type ArcadeAge = "kids" | "tween" | "teen" | "adult";

export type QuizQ = {
  prompt: string;
  options: string[];
  answerIndex: number;
  explain?: string;
};

const GEOMETRY: Record<ArcadeAge, QuizQ[]> = {
  kids: [
    { prompt: "How many sides does a triangle have?", options: ["2", "3", "4", "5"], answerIndex: 1 },
    { prompt: "A square has how many corners?", options: ["3", "4", "5", "6"], answerIndex: 1 },
    { prompt: "Which shape is round?", options: ["Square", "Triangle", "Circle", "Rectangle"], answerIndex: 2 },
    { prompt: "How many sides does a rectangle have?", options: ["3", "4", "5", "8"], answerIndex: 1 },
    { prompt: "A pentagon has how many sides?", options: ["4", "5", "6", "7"], answerIndex: 1 },
  ],
  tween: [
    { prompt: "Sum of angles in a triangle?", options: ["90°", "180°", "270°", "360°"], answerIndex: 1 },
    { prompt: "A right angle equals…", options: ["45°", "90°", "180°", "360°"], answerIndex: 1 },
    { prompt: "Area of a 5 × 4 rectangle?", options: ["9", "20", "18", "25"], answerIndex: 1 },
    { prompt: "Perimeter of a square with side 3?", options: ["6", "9", "12", "15"], answerIndex: 2 },
    { prompt: "How many sides does a hexagon have?", options: ["5", "6", "7", "8"], answerIndex: 1 },
  ],
  teen: [
    { prompt: "Area of a circle with r = 3? (πr²)", options: ["6π", "9π", "12π", "3π"], answerIndex: 1 },
    { prompt: "Supplementary angles sum to…", options: ["90°", "180°", "270°", "360°"], answerIndex: 1 },
    { prompt: "Volume of a 2×3×4 box?", options: ["9", "12", "24", "48"], answerIndex: 2 },
    { prompt: "A 30-60-90 triangle: shortest side ratio is…", options: ["1 : √3 : 2", "1 : 1 : √2", "2 : 3 : 4", "1 : 2 : 3"], answerIndex: 0 },
    { prompt: "Parallel lines cut by a transversal: alternate interior angles are…", options: ["Equal", "Supplementary", "Complementary", "Random"], answerIndex: 0 },
  ],
  adult: [
    { prompt: "Pythagorean theorem: a² + b² = ?", options: ["c", "c²", "2c", "ab"], answerIndex: 1 },
    { prompt: "Surface area of a cube with side s?", options: ["s³", "6s²", "4s²", "2s²"], answerIndex: 1 },
    { prompt: "Radians in a full circle?", options: ["π", "2π", "3π", "4π"], answerIndex: 1 },
    { prompt: "Law of cosines generalizes…", options: ["Pythagorean theorem", "Area of circle", "Volume of sphere", "Slope formula"], answerIndex: 0 },
    { prompt: "Interior angles of a regular n-gon sum to…", options: ["(n-2)×180°", "n×90°", "360°", "n×180°"], answerIndex: 0 },
  ],
};

const FINANCE: Record<ArcadeAge, QuizQ[]> = {
  kids: [
    { prompt: "Saving money in a piggy bank is…", options: ["Spending", "Saving", "Borrowing", "Gambling"], answerIndex: 1 },
    { prompt: "You earn $5 allowance. Save $2 — how much left to spend?", options: ["$1", "$2", "$3", "$5"], answerIndex: 2 },
    { prompt: "A need is something you…", options: ["Must have to live", "Only want for fun", "Throw away", "Never buy"], answerIndex: 0 },
    { prompt: "Interest is money the bank…", options: ["Takes from you", "Pays you for saving", "Hides", "Burns"], answerIndex: 1 },
    { prompt: "Budget means a plan for…", options: ["Money in and out", "Only spending", "Only gifts", "Taxes only"], answerIndex: 0 },
  ],
  tween: [
    { prompt: "Compound interest grows because you earn on…", options: ["Only principal", "Principal + past interest", "Fees", "Taxes"], answerIndex: 1 },
    { prompt: "A stock is a small piece of…", options: ["A company", "A house", "A car", "A game"], answerIndex: 0 },
    { prompt: "Diversification means…", options: ["One stock only", "Spreading across many assets", "Hiding cash", "Day trading"], answerIndex: 1 },
    { prompt: "ETF stands for…", options: ["Extra Tax Form", "Exchange-Traded Fund", "Electronic Trade Fee", "Equity Time Fund"], answerIndex: 1 },
    { prompt: "Index fund tries to match…", options: ["A market index", "Lottery odds", "One CEO", "Gold only"], answerIndex: 0 },
  ],
  teen: [
    { prompt: "Expense ratio on a fund measures…", options: ["Annual fees %", "Stock price", "Dividend date", "Tax bracket"], answerIndex: 0 },
    { prompt: "Bonds are best described as…", options: ["Ownership shares", "Loans to issuers", "Cryptocurrency", "Insurance"], answerIndex: 1 },
    { prompt: "Dollar-cost averaging means…", options: ["Investing fixed amounts regularly", "Timing the top", "All-in once", "Only bonds"], answerIndex: 0 },
    { prompt: "Historically stocks vs cash long-term tend to…", options: ["Return less", "Return more with volatility", "Stay flat", "Guarantee profit"], answerIndex: 1 },
    { prompt: "Emergency fund target is often…", options: ["$50", "3–6 months expenses", "$1M always", "Zero"], answerIndex: 1 },
  ],
  adult: [
    { prompt: "Sharpe ratio measures return per unit of…", options: ["Risk (volatility)", "Volume", "Dividend", "Inflation only"], answerIndex: 0 },
    { prompt: "Tax-loss harvesting offsets…", options: ["Capital gains with losses", "Income with gifts", "Fees with interest", "Dividends with bonds"], answerIndex: 0 },
    { prompt: "P/E ratio compares price to…", options: ["Earnings per share", "Employees", "Debt only", "Dividend yield"], answerIndex: 0 },
    { prompt: "Asset allocation glide path typically…", options: ["Shifts toward bonds near retirement", "Stays 100% stocks", "Avoids bonds", "Only crypto"], answerIndex: 0 },
    { prompt: "Real return adjusts for…", options: ["Inflation", "Dividends only", "Fees only", "Currency only"], answerIndex: 0 },
  ],
};

export function geometryQuestions(age: ArcadeAge): QuizQ[] {
  return GEOMETRY[age];
}

export function financeQuestions(age: ArcadeAge): QuizQ[] {
  return FINANCE[age];
}

export function randomQuestion(bank: QuizQ[], used: Set<string>): QuizQ {
  const avail = bank.filter((q) => !used.has(q.prompt));
  const pool = avail.length ? avail : bank;
  const q = pool[Math.floor(Math.random() * pool.length)];
  used.add(q.prompt);
  return q;
}

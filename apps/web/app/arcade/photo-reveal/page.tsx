"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

type Age = "kids" | "tween" | "teen" | "adult";
type Phase = "idle" | "playing" | "done";
type AnswerState = "unanswered" | "correct" | "wrong";

interface Question {
  q: string;
  options: string[];
  answer: number;
}

interface Level {
  name: string;
  artName: string;
  cols: number;
  rows: number;
  questions: Question[];
}

const LEVELS: Record<Age, Level> = {
  kids: {
    name: "Easy",
    artName: "Rainbow Valley",
    cols: 6,
    rows: 3,
    questions: [
      { q: "What color comes after red in a rainbow?", options: ["Blue","Orange","Green","Purple"], answer: 1 },
      { q: "How many sides does a triangle have?", options: ["2","3","4","5"], answer: 1 },
      { q: "Which animal is the largest on land?", options: ["Lion","Giraffe","Elephant","Hippo"], answer: 2 },
      { q: "What is 5 + 7?", options: ["10","11","12","13"], answer: 2 },
      { q: "The Sun is a…", options: ["Planet","Moon","Star","Comet"], answer: 2 },
      { q: "How many legs does a spider have?", options: ["4","6","8","10"], answer: 2 },
      { q: "What do caterpillars turn into?", options: ["Bees","Butterflies","Moths","Beetles"], answer: 1 },
      { q: "Which is the biggest ocean?", options: ["Atlantic","Indian","Arctic","Pacific"], answer: 3 },
      { q: "What is 3 × 4?", options: ["7","10","12","14"], answer: 2 },
      { q: "What gas do plants breathe in?", options: ["Oxygen","Nitrogen","CO2","Hydrogen"], answer: 2 },
      { q: "How many days in a week?", options: ["5","6","7","8"], answer: 2 },
      { q: "Which planet is closest to the Sun?", options: ["Venus","Mercury","Earth","Mars"], answer: 1 },
      { q: "What color is the sky on a clear day?", options: ["Green","Blue","Red","Yellow"], answer: 1 },
      { q: "What do bees make?", options: ["Milk","Honey","Sugar","Butter"], answer: 1 },
      { q: "How many months are in a year?", options: ["10","11","12","13"], answer: 2 },
      { q: "What is the opposite of hot?", options: ["Warm","Cold","Wet","Dry"], answer: 1 },
      { q: "Which shape has no corners?", options: ["Square","Triangle","Circle","Rectangle"], answer: 2 },
      { q: "What sound does a cow make?", options: ["Baa","Moo","Oink","Cluck"], answer: 1 },
    ],
  },
  tween: {
    name: "Medium",
    artName: "Underwater Kingdom",
    cols: 6,
    rows: 4,
    questions: [
      { q: "Chemical symbol for water?", options: ["WO","HO","H2O","W2O"], answer: 2 },
      { q: "What is 15% of 200?", options: ["20","25","30","35"], answer: 2 },
      { q: "The Great Wall is in which country?", options: ["Japan","India","China","Korea"], answer: 2 },
      { q: "Photosynthesis produces which gas?", options: ["CO2","N2","O2","H2"], answer: 2 },
      { q: "How many continents on Earth?", options: ["5","6","7","8"], answer: 2 },
      { q: "Who wrote Romeo and Juliet?", options: ["Dickens","Shakespeare","Austen","Twain"], answer: 1 },
      { q: "What is the square root of 81?", options: ["7","8","9","10"], answer: 2 },
      { q: "The Eiffel Tower is in which city?", options: ["Rome","Berlin","London","Paris"], answer: 3 },
      { q: "DNA stands for?", options: ["Dynamic Nucleic Acid","Deoxyribonucleic Acid","Digital Nucleic Array","Direct Nucleic Acid"], answer: 1 },
      { q: "Speed of light is approx?", options: ["200,000 km/s","300,000 km/s","400,000 km/s","150,000 km/s"], answer: 1 },
      { q: "What is the capital of Australia?", options: ["Sydney","Melbourne","Canberra","Perth"], answer: 2 },
      { q: "Which gas makes up most of Earth's atmosphere?", options: ["Oxygen","Carbon Dioxide","Nitrogen","Argon"], answer: 2 },
      { q: "What is 2 to the power of 8?", options: ["128","256","512","64"], answer: 1 },
      { q: "The Amazon River is on which continent?", options: ["Africa","Asia","South America","North America"], answer: 2 },
      { q: "Who painted the Mona Lisa?", options: ["Picasso","da Vinci","Michelangelo","Raphael"], answer: 1 },
      { q: "Which planet has rings?", options: ["Jupiter","Mars","Saturn","Venus"], answer: 2 },
      { q: "What is the powerhouse of the cell?", options: ["Nucleus","Ribosome","Mitochondria","Vacuole"], answer: 2 },
      { q: "Largest prime under 20?", options: ["13","17","19","11"], answer: 2 },
      { q: "What is 144 ÷ 12?", options: ["10","11","12","13"], answer: 2 },
      { q: "How many bones in the adult human body?", options: ["186","196","206","216"], answer: 2 },
      { q: "The first element in the periodic table?", options: ["Helium","Lithium","Hydrogen","Carbon"], answer: 2 },
      { q: "Which ocean is the smallest?", options: ["Atlantic","Pacific","Indian","Arctic"], answer: 3 },
      { q: "What is 7² + 1?", options: ["48","49","50","51"], answer: 2 },
      { q: "Capital of Brazil?", options: ["Rio de Janeiro","São Paulo","Brasília","Manaus"], answer: 2 },
    ],
  },
  teen: {
    name: "Hard",
    artName: "Night Space Scene",
    cols: 8,
    rows: 5,
    questions: [
      { q: "E = mc² — c represents?", options: ["Charge","Speed of light","Constant","Coulomb"], answer: 1 },
      { q: "The mitochondrial matrix produces ATP via?", options: ["Glycolysis","Krebs cycle","ETC","Fermentation"], answer: 1 },
      { q: "Integral of x² dx?", options: ["x³","x³/3","2x","3x²"], answer: 1 },
      { q: "Schrödinger's equation models?", options: ["Gravity","Quantum wave function","EM field","Nuclear force"], answer: 1 },
      { q: "GDP formula?", options: ["C+I+G+NX","C+I-G+NX","C-I+G+NX","C+I+G-NX"], answer: 0 },
      { q: "Author of 'Crime and Punishment'?", options: ["Tolstoy","Chekhov","Dostoevsky","Turgenev"], answer: 2 },
      { q: "Avogadro's number is ~?", options: ["6.02×10²¹","6.02×10²²","6.02×10²³","6.02×10²⁴"], answer: 2 },
      { q: "The Treaty of Westphalia (1648) ended?", options: ["Thirty Years War","Hundred Years War","Seven Years War","Napoleonic Wars"], answer: 0 },
      { q: "log₂(1024) = ?", options: ["8","9","10","11"], answer: 2 },
      { q: "Eigenvalues of [[2,1],[0,3]]?", options: ["2,3","1,2","3,4","0,3"], answer: 0 },
      { q: "The Krebs cycle occurs in the?", options: ["Cytoplasm","Nucleus","Mitochondrial matrix","ER"], answer: 2 },
      { q: "Hegel's dialectic: thesis + antithesis = ?", options: ["Paradox","Synthesis","Theory","Lemma"], answer: 1 },
      { q: "Black hole boundary is called?", options: ["Singularity","Photon sphere","Event horizon","Accretion disk"], answer: 2 },
      { q: "Derivative of ln(x)?", options: ["1/x²","x","1/x","ln(x-1)"], answer: 2 },
      { q: "Which particle has no charge?", options: ["Proton","Electron","Neutron","Positron"], answer: 2 },
      { q: "Capital of Kazakhstan?", options: ["Almaty","Nur-Sultan","Shymkent","Karaganda"], answer: 1 },
      { q: "The Coriolis effect causes?", options: ["Tides","Deflection of moving air","Earthquakes","Volcanic eruptions"], answer: 1 },
      { q: "Second law of thermodynamics?", options: ["Energy is conserved","Entropy increases","F=ma","PV=nRT"], answer: 1 },
      { q: "Which organelle processes proteins via the secretory pathway?", options: ["Lysosome","Vacuole","Golgi apparatus","Mitochondria"], answer: 2 },
      { q: "Fourier transform converts signal from?", options: ["Time to frequency","Space to time","Voltage to current","Phase to amplitude"], answer: 0 },
      { q: "Comparative advantage theory by?", options: ["Adam Smith","Keynes","David Ricardo","Marx"], answer: 2 },
      { q: "Maxwell's equations describe?", options: ["Gravity","Quantum mechanics","Electromagnetism","Thermodynamics"], answer: 2 },
      { q: "lim(x→0) sin(x)/x = ?", options: ["0","∞","1","undefined"], answer: 2 },
      { q: "General relativity describes gravity as?", options: ["A force","Curvature of spacetime","Quantum field","Dark energy"], answer: 1 },
      { q: "Nash equilibrium is a concept in?", options: ["Physics","Economics/Game Theory","Biology","Chemistry"], answer: 1 },
      { q: "Planck's constant unit?", options: ["J/s","J·s","J·m","kg·m/s"], answer: 1 },
      { q: "The Higgs boson gives particles?", options: ["Spin","Charge","Mass","Color"], answer: 2 },
      { q: "Which RNA carries amino acids to the ribosome?", options: ["mRNA","rRNA","tRNA","snRNA"], answer: 2 },
      { q: "Banach-Tarski paradox involves?", options: ["Prime numbers","Non-measurable sets","Fluid dynamics","Graph theory"], answer: 1 },
      { q: "The photoelectric effect proved?", options: ["Wave nature of light","Particle nature of light","Gravity waves","Nuclear fission"], answer: 1 },
      { q: "Oxidation state of O in H₂O₂?", options: ["-2","-1","0","+1"], answer: 1 },
      { q: "First mover advantage relates to?", options: ["Sports","Market strategy","Biology","Physics"], answer: 1 },
      { q: "CRISPR-Cas9 is used for?", options: ["Protein folding","Gene editing","Drug synthesis","Cell imaging"], answer: 1 },
      { q: "Pythagorean theorem: a²+b²=?", options: ["c","c²","2c","c³"], answer: 1 },
      { q: "World War I started in?", options: ["1912","1913","1914","1915"], answer: 2 },
      { q: "Determinant of [[1,2],[3,4]]?", options: ["-2","2","10","-10"], answer: 0 },
      { q: "Speed of sound in air (approx)?", options: ["143 m/s","243 m/s","343 m/s","443 m/s"], answer: 2 },
      { q: "Boltzmann constant relates temperature to?", options: ["Pressure","Energy","Entropy","Frequency"], answer: 1 },
      { q: "Complex number i² = ?", options: ["1","-1","i","-i"], answer: 1 },
      { q: "Keynes advocated spending during?", options: ["Booms","Recessions","Both","Neither"], answer: 1 },
    ],
  },
  adult: {
    name: "Hard",
    artName: "Night Space Scene",
    cols: 8,
    rows: 5,
    questions: [
      { q: "E = mc² — c represents?", options: ["Charge","Speed of light","Constant","Coulomb"], answer: 1 },
      { q: "The mitochondrial matrix produces ATP via?", options: ["Glycolysis","Krebs cycle","ETC","Fermentation"], answer: 1 },
      { q: "Integral of x² dx?", options: ["x³","x³/3","2x","3x²"], answer: 1 },
      { q: "Schrödinger's equation models?", options: ["Gravity","Quantum wave function","EM field","Nuclear force"], answer: 1 },
      { q: "GDP formula?", options: ["C+I+G+NX","C+I-G+NX","C-I+G+NX","C+I+G-NX"], answer: 0 },
      { q: "Author of 'Crime and Punishment'?", options: ["Tolstoy","Chekhov","Dostoevsky","Turgenev"], answer: 2 },
      { q: "Avogadro's number is ~?", options: ["6.02×10²¹","6.02×10²²","6.02×10²³","6.02×10²⁴"], answer: 2 },
      { q: "The Treaty of Westphalia (1648) ended?", options: ["Thirty Years War","Hundred Years War","Seven Years War","Napoleonic Wars"], answer: 0 },
      { q: "log₂(1024) = ?", options: ["8","9","10","11"], answer: 2 },
      { q: "Eigenvalues of [[2,1],[0,3]]?", options: ["2,3","1,2","3,4","0,3"], answer: 0 },
      { q: "The Krebs cycle occurs in the?", options: ["Cytoplasm","Nucleus","Mitochondrial matrix","ER"], answer: 2 },
      { q: "Hegel's dialectic: thesis + antithesis = ?", options: ["Paradox","Synthesis","Theory","Lemma"], answer: 1 },
      { q: "Black hole boundary is called?", options: ["Singularity","Photon sphere","Event horizon","Accretion disk"], answer: 2 },
      { q: "Derivative of ln(x)?", options: ["1/x²","x","1/x","ln(x-1)"], answer: 2 },
      { q: "Which particle has no charge?", options: ["Proton","Electron","Neutron","Positron"], answer: 2 },
      { q: "Capital of Kazakhstan?", options: ["Almaty","Nur-Sultan","Shymkent","Karaganda"], answer: 1 },
      { q: "The Coriolis effect causes?", options: ["Tides","Deflection of moving air","Earthquakes","Volcanic eruptions"], answer: 1 },
      { q: "Second law of thermodynamics?", options: ["Energy is conserved","Entropy increases","F=ma","PV=nRT"], answer: 1 },
      { q: "Which organelle processes proteins via the secretory pathway?", options: ["Lysosome","Vacuole","Golgi apparatus","Mitochondria"], answer: 2 },
      { q: "Fourier transform converts signal from?", options: ["Time to frequency","Space to time","Voltage to current","Phase to amplitude"], answer: 0 },
      { q: "Comparative advantage theory by?", options: ["Adam Smith","Keynes","David Ricardo","Marx"], answer: 2 },
      { q: "Maxwell's equations describe?", options: ["Gravity","Quantum mechanics","Electromagnetism","Thermodynamics"], answer: 2 },
      { q: "lim(x→0) sin(x)/x = ?", options: ["0","∞","1","undefined"], answer: 2 },
      { q: "General relativity describes gravity as?", options: ["A force","Curvature of spacetime","Quantum field","Dark energy"], answer: 1 },
      { q: "Nash equilibrium is a concept in?", options: ["Physics","Economics/Game Theory","Biology","Chemistry"], answer: 1 },
      { q: "Planck's constant unit?", options: ["J/s","J·s","J·m","kg·m/s"], answer: 1 },
      { q: "The Higgs boson gives particles?", options: ["Spin","Charge","Mass","Color"], answer: 2 },
      { q: "Which RNA carries amino acids to the ribosome?", options: ["mRNA","rRNA","tRNA","snRNA"], answer: 2 },
      { q: "Banach-Tarski paradox involves?", options: ["Prime numbers","Non-measurable sets","Fluid dynamics","Graph theory"], answer: 1 },
      { q: "The photoelectric effect proved?", options: ["Wave nature of light","Particle nature of light","Gravity waves","Nuclear fission"], answer: 1 },
      { q: "Oxidation state of O in H₂O₂?", options: ["-2","-1","0","+1"], answer: 1 },
      { q: "First mover advantage relates to?", options: ["Sports","Market strategy","Biology","Physics"], answer: 1 },
      { q: "CRISPR-Cas9 is used for?", options: ["Protein folding","Gene editing","Drug synthesis","Cell imaging"], answer: 1 },
      { q: "Pythagorean theorem: a²+b²=?", options: ["c","c²","2c","c³"], answer: 1 },
      { q: "World War I started in?", options: ["1912","1913","1914","1915"], answer: 2 },
      { q: "Determinant of [[1,2],[3,4]]?", options: ["-2","2","10","-10"], answer: 0 },
      { q: "Speed of sound in air (approx)?", options: ["143 m/s","243 m/s","343 m/s","443 m/s"], answer: 2 },
      { q: "Boltzmann constant relates temperature to?", options: ["Pressure","Energy","Entropy","Frequency"], answer: 1 },
      { q: "Complex number i² = ?", options: ["1","-1","i","-i"], answer: 1 },
      { q: "Keynes advocated spending during?", options: ["Booms","Recessions","Both","Neither"], answer: 1 },
    ],
  },
};

// SVG artworks drawn with SVG primitives
function RainbowValleySVG() {
  return (
    <g>
      <defs>
        <linearGradient id="skyG" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#87CEEB" />
          <stop offset="100%" stopColor="#E0F7FF" />
        </linearGradient>
      </defs>
      <rect x={0} y={0} width={600} height={400} fill="url(#skyG)" />
      {/* Rainbow */}
      {[
        { r: 280, color: "#FF0000" },
        { r: 255, color: "#FF7700" },
        { r: 230, color: "#FFFF00" },
        { r: 205, color: "#00CC00" },
        { r: 180, color: "#0000FF" },
        { r: 155, color: "#8B00FF" },
      ].map(({ r, color }, i) => (
        <path key={i} d={`M ${300 - r} 320 A ${r} ${r} 0 0 1 ${300 + r} 320`}
          fill="none" stroke={color} strokeWidth={24} opacity={0.85} />
      ))}
      {/* Rolling green hills */}
      <path d="M0 280 Q100 220 200 260 Q300 300 400 240 Q500 180 600 240 L600 400 L0 400 Z" fill="#4CAF50" />
      <path d="M0 310 Q150 270 300 300 Q450 330 600 290 L600 400 L0 400 Z" fill="#66BB6A" />
      <path d="M0 340 Q200 320 400 340 Q500 350 600 330 L600 400 L0 400 Z" fill="#81C784" />
      {/* Sun */}
      <circle cx={80} cy={70} r={45} fill="#FFD700" />
      {[0,45,90,135,180,225,270,315].map((a, i) => (
        <line key={i}
          x1={80 + Math.cos(a * Math.PI / 180) * 50} y1={70 + Math.sin(a * Math.PI / 180) * 50}
          x2={80 + Math.cos(a * Math.PI / 180) * 68} y2={70 + Math.sin(a * Math.PI / 180) * 68}
          stroke="#FFD700" strokeWidth={4} strokeLinecap="round" />
      ))}
      {/* Clouds */}
      <ellipse cx={420} cy={80} rx={60} ry={28} fill="white" />
      <ellipse cx={390} cy={88} rx={38} ry={24} fill="white" />
      <ellipse cx={455} cy={88} rx={40} ry={24} fill="white" />
      <ellipse cx={200} cy={50} rx={48} ry={22} fill="white" />
      <ellipse cx={175} cy={58} rx={30} ry={18} fill="white" />
      <ellipse cx={228} cy={58} rx={32} ry={18} fill="white" />
      {/* Trees */}
      {[60, 160, 440, 540].map((x, i) => (
        <g key={i}>
          <rect x={x - 8} y={260 + i % 2 * 20} width={16} height={60} fill="#8B4513" />
          <circle cx={x} cy={248 + i % 2 * 20} r={35} fill="#228B22" />
          <circle cx={x - 15} cy={262 + i % 2 * 20} r={25} fill="#2d8b22" />
          <circle cx={x + 15} cy={262 + i % 2 * 20} r={25} fill="#228B22" />
        </g>
      ))}
      {/* Flowers */}
      {[120, 200, 310, 380, 480].map((x, i) => (
        <g key={i}>
          <line x1={x} y1={360} x2={x} y2={340} stroke="#228B22" strokeWidth={2} />
          <circle cx={x} cy={338} r={9} fill={["#FF69B4", "#FF4500", "#FFD700", "#9370DB", "#00CED1"][i]} />
        </g>
      ))}
      {/* Butterflies */}
      {[{x:250,y:200},{x:380,y:180}].map((b,i) => (
        <g key={i}>
          <ellipse cx={b.x-8} cy={b.y} rx={14} ry={9} fill={i===0?"#FF69B4":"#FFD700"} opacity={0.85} transform={`rotate(-20 ${b.x-8} ${b.y})`} />
          <ellipse cx={b.x+8} cy={b.y} rx={14} ry={9} fill={i===0?"#FF69B4":"#FFD700"} opacity={0.85} transform={`rotate(20 ${b.x+8} ${b.y})`} />
          <ellipse cx={b.x} cy={b.y} rx={3} ry={10} fill="#333" />
        </g>
      ))}
      {/* River */}
      <path d="M0 370 Q100 355 200 365 Q300 375 400 360 Q500 345 600 358 L600 400 L0 400 Z" fill="#4FC3F7" opacity={0.7} />
    </g>
  );
}

function UnderwaterKingdomSVG() {
  return (
    <g>
      <defs>
        <linearGradient id="deepOcean" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#001529" />
          <stop offset="100%" stopColor="#003566" />
        </linearGradient>
      </defs>
      <rect x={0} y={0} width={600} height={400} fill="url(#deepOcean)" />
      {/* Light shafts */}
      {[80, 200, 350, 500].map((x, i) => (
        <polygon key={i} points={`${x},0 ${x + 40},0 ${x + 80},400 ${x + 30},400`}
          fill="white" opacity={0.04} />
      ))}
      {/* Sandy floor */}
      <path d="M0 340 Q200 320 400 345 Q500 358 600 338 L600 400 L0 400 Z" fill="#C8A96E" />
      {/* Castle */}
      <rect x={220} y={220} width={160} height={130} fill="#4a6fa5" />
      <rect x={220} y={205} width={40} height={25} fill="#4a6fa5" />
      <rect x={300} y={200} width={40} height={30} fill="#4a6fa5" />
      <rect x={340} y={205} width={40} height={25} fill="#4a6fa5" />
      <polygon points="220,205 240,175 260,205" fill="#2c4a7a" />
      <polygon points="300,200 320,165 340,200" fill="#2c4a7a" />
      <polygon points="340,205 360,175 380,205" fill="#2c4a7a" />
      <rect x={270} y={290} width={60} height={60} fill="#2c4a7a" />
      <rect x={235} y={240} width={30} height={25} rx={3} fill="#87CEEB" opacity={0.6} />
      <rect x={335} y={240} width={30} height={25} rx={3} fill="#87CEEB" opacity={0.6} />
      {/* Seaweed */}
      {[50, 120, 480, 555].map((x, i) => (
        <g key={i}>
          <path d={`M${x} 400 Q${x - 15} 360 ${x} 330 Q${x + 15} 300 ${x} 270`}
            stroke="#1a7a1a" strokeWidth={6} fill="none" strokeLinecap="round" />
          <ellipse cx={x} cy={268} rx={10} ry={14} fill="#22a022" />
        </g>
      ))}
      {/* Colorful fish */}
      {[
        { x: 80, y: 140, c: "#FF6600", c2: "#FFD700" },
        { x: 500, y: 160, c: "#FF69B4", c2: "#FF1493" },
        { x: 140, y: 280, c: "#4FC3F7", c2: "#0288D1" },
        { x: 450, y: 240, c: "#FFD700", c2: "#FF8C00" },
        { x: 320, y: 130, c: "#9C27B0", c2: "#E040FB" },
      ].map((f, i) => (
        <g key={i}>
          <ellipse cx={f.x} cy={f.y} rx={28} ry={16} fill={f.c} />
          <polygon points={`${f.x - 28},${f.y - 10} ${f.x - 28},${f.y + 10} ${f.x - 42},${f.y}`} fill={f.c2} />
          <circle cx={f.x + 14} cy={f.y - 4} r={5} fill="#111" />
          <circle cx={f.x + 15} cy={f.y - 5} r={2} fill="white" />
          <line x1={f.x - 14} y1={f.y - 14} x2={f.x - 14} y2={f.y + 14} stroke={f.c2} strokeWidth={2} opacity={0.6} />
          <line x1={f.x} y1={f.y - 15} x2={f.x} y2={f.y + 15} stroke={f.c2} strokeWidth={2} opacity={0.6} />
        </g>
      ))}
      {/* Coral */}
      {[150, 420].map((x, i) => (
        <g key={i}>
          {[x - 15, x, x + 15].map((cx, j) => (
            <g key={j}>
              <line x1={cx} y1={400} x2={cx + (j === 1 ? 0 : j === 0 ? -10 : 10)} y2={355} stroke={i === 0 ? "#FF69B4" : "#FF6600"} strokeWidth={5} strokeLinecap="round" />
              <circle cx={cx + (j === 1 ? 0 : j === 0 ? -10 : 10)} cy={353} r={10} fill={i === 0 ? "#FF1493" : "#FF4500"} />
            </g>
          ))}
        </g>
      ))}
      {/* Treasure */}
      <rect x={60} y={350} width={55} height={38} rx={3} fill="#8B4513" />
      <rect x={60} y={350} width={55} height={12} rx={3} fill="#A0522D" />
      <rect x={82} y={350} width={10} height={38} fill="#FFD700" opacity={0.5} />
      <circle cx={87} cy={369} r={6} fill="#FFD700" />
      {/* Bubbles */}
      {[30, 100, 200, 380, 470, 560].map((x, i) => (
        <circle key={i} cx={x} cy={80 + i * 20} r={4 + i % 3} fill="none" stroke="white" strokeWidth={1} opacity={0.25} />
      ))}
      {/* Stingray */}
      <path d="M490 300 Q510 270 530 300 Q510 330 490 300 Z" fill="#555" opacity={0.8} />
      <line x1={530} y1={300} x2={560} y2={310} stroke="#555" strokeWidth={3} strokeLinecap="round" />
    </g>
  );
}

function NightSpaceSVG() {
  return (
    <g>
      <defs>
        <radialGradient id="spaceGrad" cx="50%" cy="40%" r="60%">
          <stop offset="0%" stopColor="#1a0a2e" />
          <stop offset="100%" stopColor="#000005" />
        </radialGradient>
        <radialGradient id="nebulaG" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#7c3aed" stopOpacity="0.4" />
          <stop offset="100%" stopColor="#7c3aed" stopOpacity="0" />
        </radialGradient>
        <radialGradient id="nebulaG2" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#0ea5e9" stopOpacity="0.3" />
          <stop offset="100%" stopColor="#0ea5e9" stopOpacity="0" />
        </radialGradient>
      </defs>
      <rect x={0} y={0} width={600} height={400} fill="url(#spaceGrad)" />
      {/* Nebula clouds */}
      <ellipse cx={150} cy={120} rx={120} ry={80} fill="url(#nebulaG)" />
      <ellipse cx={480} cy={220} rx={100} ry={70} fill="url(#nebulaG2)" />
      <ellipse cx={320} cy={280} rx={140} ry={90} fill="url(#nebulaG)" opacity={0.5} />
      {/* Stars — many sizes */}
      {Array.from({ length: 80 }, (_, i) => ({
        x: (i * 137.508) % 600,
        y: (i * 89.33) % 400,
        r: 0.8 + (i % 3) * 0.7,
        opacity: 0.4 + (i % 5) * 0.12,
      })).map((s, i) => (
        <circle key={i} cx={s.x} cy={s.y} r={s.r} fill="white" opacity={s.opacity} />
      ))}
      {/* Bright stars with sparkle */}
      {[{x:80,y:60},{x:200,y:30},{x:400,y:80},{x:520,y:50},{x:300,y:140},{x:150,y:220}].map((s,i) => (
        <g key={i}>
          <circle cx={s.x} cy={s.y} r={2.5} fill="white" />
          <line x1={s.x-6} y1={s.y} x2={s.x+6} y2={s.y} stroke="white" strokeWidth={1} opacity={0.6} />
          <line x1={s.x} y1={s.y-6} x2={s.x} y2={s.y+6} stroke="white" strokeWidth={1} opacity={0.6} />
        </g>
      ))}
      {/* Milky Way band */}
      <path d="M0 180 Q200 160 400 200 Q500 220 600 190" stroke="white" strokeWidth={40} fill="none" opacity={0.04} />
      {/* Saturn */}
      <ellipse cx={480} cy={90} rx={50} ry={35} fill="#C8A96E" />
      <ellipse cx={480} cy={90} rx={35} ry={23} fill="#DDB87A" />
      <ellipse cx={480} cy={90} rx={65} ry={15} fill="none" stroke="#A08060" strokeWidth={8} opacity={0.7} />
      <ellipse cx={480} cy={90} rx={65} ry={15} fill="none" stroke="#C8A060" strokeWidth={4} opacity={0.5} />
      {/* Jupiter */}
      <circle cx={100} cy={300} r={50} fill="#C88B50" />
      <ellipse cx={100} cy={290} rx={50} ry={8} fill="#A06030" opacity={0.6} />
      <ellipse cx={100} cy={305} rx={50} ry={6} fill="#E0A060" opacity={0.5} />
      <ellipse cx={100} cy={318} rx={50} ry={7} fill="#A06030" opacity={0.5} />
      {/* Great red spot */}
      <ellipse cx={115} cy={308} rx={14} ry={9} fill="#CC4400" opacity={0.8} />
      {/* Moon */}
      <circle cx={300} cy={70} r={38} fill="#E8E8D0" />
      {/* Moon craters */}
      <circle cx={288} cy={60} r={8} fill="#D0D0B8" stroke="#C0C0A8" strokeWidth={1} />
      <circle cx={310} cy={80} r={6} fill="#D0D0B8" stroke="#C0C0A8" strokeWidth={1} />
      <circle cx={295} cy={85} r={4} fill="#D0D0B8" stroke="#C0C0A8" strokeWidth={1} />
      {/* Rocket */}
      <path d="M370 250 Q382 210 370 180 Q358 210 370 250 Z" fill="#E0E0E0" />
      <polygon points="358,250 382,250 390,275 350,275" fill="#CC0000" />
      <rect x={355} y={230} width={8} height={25} fill="#CC0000" transform="rotate(-15 355 230)" />
      <rect x={385} y={230} width={8} height={25} fill="#CC0000" transform="rotate(15 385 230)" />
      <circle cx={370} cy={208} r={8} fill="#87CEEB" opacity={0.8} />
      {/* Rocket exhaust */}
      <path d="M358 275 Q360 295 370 310 Q380 295 382 275 Z" fill="#FF6600" opacity={0.8} />
      <path d="M362 275 Q364 288 370 298 Q376 288 378 275 Z" fill="#FFD700" opacity={0.9} />
      {/* Shooting star */}
      <line x1={530} y1={150} x2={580} y2={120} stroke="white" strokeWidth={2} opacity={0.8} />
      <circle cx={530} cy={150} r={3} fill="white" />
      {/* Distant galaxy */}
      <ellipse cx={200} cy={340} rx={35} ry={12} fill="white" opacity={0.12} />
      <ellipse cx={200} cy={340} rx={20} ry={7} fill="white" opacity={0.18} />
      {/* Astronaut */}
      <circle cx={430} cy={310} r={20} fill="#E0E0E0" />
      <circle cx={430} cy={310} r={14} fill="#87CEEB" opacity={0.7} />
      <ellipse cx={430} cy={335} rx={15} ry={18} fill="#E0E0E0" />
      <rect x={415} y={328} width={8} height={20} rx={4} fill="#E0E0E0" transform="rotate(-20 415 328)" />
      <rect x={437} y={328} width={8} height={20} rx={4} fill="#E0E0E0" transform="rotate(20 437 328)" />
      <rect x={420} y={348} width={8} height={22} rx={4} fill="#E0E0E0" />
      <rect x={432} y={348} width={8} height={22} rx={4} fill="#E0E0E0" />
    </g>
  );
}

function ArtworkSVG({ age }: { age: Age }) {
  if (age === "kids") return <RainbowValleySVG />;
  if (age === "tween") return <UnderwaterKingdomSVG />;
  return <NightSpaceSVG />;
}

export default function PhotoReveal() {
  const [age, setAge] = useState<Age>("kids");
  const [phase, setPhase] = useState<Phase>("idle");
  const level = LEVELS[age];
  const totalTiles = level.cols * level.rows;

  // Shuffled tile reveal order
  const [revealOrder, setRevealOrder] = useState<number[]>([]);
  const [revealedCount, setRevealedCount] = useState(0);
  const [qIdx, setQIdx] = useState(0);
  const [answerState, setAnswerState] = useState<AnswerState>("unanswered");
  const [selectedOpt, setSelectedOpt] = useState<number | null>(null);
  const [score, setScore] = useState(0);
  const [qStartTime, setQStartTime] = useState(0);
  const [wrongStreak, setWrongStreak] = useState(0);
  const answeredRef = useRef(false);

  useEffect(() => {
    const q = new URLSearchParams(window.location.search).get("age");
    if (q === "kids" || q === "tween" || q === "teen" || q === "adult") setAge(q as Age);
  }, []);

  function shuffle(n: number): number[] {
    const arr = Array.from({ length: n }, (_, i) => i);
    for (let i = arr.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [arr[i], arr[j]] = [arr[j], arr[i]];
    }
    return arr;
  }

  const startGame = () => {
    const order = shuffle(totalTiles);
    setRevealOrder(order);
    setRevealedCount(0);
    setQIdx(0);
    setScore(0);
    setAnswerState("unanswered");
    setSelectedOpt(null);
    setWrongStreak(0);
    answeredRef.current = false;
    setQStartTime(Date.now());
    setPhase("playing");
  };

  function pickAnswer(optIdx: number) {
    if (answerState !== "unanswered" || answeredRef.current) return;
    answeredRef.current = true;
    setSelectedOpt(optIdx);
    const q = level.questions[qIdx];
    const correct = optIdx === q.answer;

    if (correct) {
      const elapsed = (Date.now() - qStartTime) / 1000;
      const speedBonus = elapsed < 5 ? 50 : elapsed < 10 ? 25 : 0;
      setScore((s) => s + 100 + speedBonus);
      setAnswerState("correct");
      setWrongStreak(0);
      setTimeout(() => {
        // Reveal a tile
        const newRevealed = revealedCount + 1;
        setRevealedCount(newRevealed);
        const nextQIdx = qIdx + 1;
        if (newRevealed >= totalTiles) {
          setPhase("done");
        } else {
          setQIdx(nextQIdx < level.questions.length ? nextQIdx : nextQIdx % level.questions.length);
          setAnswerState("unanswered");
          setSelectedOpt(null);
          answeredRef.current = false;
          setQStartTime(Date.now());
        }
      }, 1200);
    } else {
      setAnswerState("wrong");
      setWrongStreak((w) => w + 1);
      setTimeout(() => {
        setAnswerState("unanswered");
        setSelectedOpt(null);
        answeredRef.current = false;
        setQStartTime(Date.now());
      }, 1000);
    }
  }

  const currentQ = phase === "playing" ? level.questions[qIdx % level.questions.length] : null;
  const tileW = 600 / level.cols;
  const tileH = 400 / level.rows;
  const revealedSet = new Set(revealOrder.slice(0, revealedCount));
  const progressPct = Math.round((revealedCount / totalTiles) * 100);

  return (
    <main className="container" style={{ maxWidth: 760, paddingBottom: 48 }}>
      <style>{`
        @keyframes tileReveal {
          from { opacity: 1; transform: scale(1); }
          to   { opacity: 0; transform: scale(0.85); }
        }
        @keyframes celebrateArt {
          0%   { filter: brightness(1); }
          50%  { filter: brightness(1.3) saturate(1.5); }
          100% { filter: brightness(1); }
        }
        .tile-revealed { animation: tileReveal 0.5s ease-out forwards; }
        .art-complete  { animation: celebrateArt 1.5s ease-in-out 3; }
      `}</style>

      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap", marginBottom: 4 }}>
        <h1 style={{ margin: 0 }}>Photo Reveal</h1>
        <Link href="/arcade" style={{ marginLeft: "auto", color: "#94a3b8" }}>Back to Arcade</Link>
      </div>
      <p className="muted" style={{ marginBottom: 12 }}>
        Answer questions correctly to reveal the hidden artwork tile by tile!
      </p>

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 16 }}>
        {(["kids", "tween", "teen", "adult"] as Age[]).map((a) => (
          <button key={a} onClick={() => { setAge(a); setPhase("idle"); }}
            disabled={phase === "playing"}
            style={{ opacity: age === a ? 1 : 0.5 }}>
            {a === "kids" ? "Rainbow Valley (Easy)" : a === "tween" ? "Underwater Kingdom (Med)" : a === "teen" ? "Night Space (Hard)" : "Night Space (Hard)"}
          </button>
        ))}
      </div>

      {phase === "idle" && (
        <div style={{ textAlign: "center", padding: 48 }}>
          <div style={{ fontSize: 56, marginBottom: 12 }}>
            {age === "kids" ? "🌈" : age === "tween" ? "🌊" : "🌌"}
          </div>
          <h2 style={{ marginBottom: 8 }}>{level.artName}</h2>
          <p className="muted" style={{ marginBottom: 8 }}>
            {level.cols} x {level.rows} grid = {totalTiles} tiles to reveal
          </p>
          <p className="muted" style={{ marginBottom: 28 }}>
            Answer each question correctly to reveal a tile. Wrong answers get another try. Speed bonus for fast answers!
          </p>
          <button onClick={startGame} style={{ background: "#059669", color: "#fff", padding: "14px 36px", fontSize: 20, fontWeight: 700, borderRadius: 12, border: "none", cursor: "pointer" }}>
            Start Revealing
          </button>
        </div>
      )}

      {(phase === "playing" || phase === "done") && (
        <>
          {/* Score bar */}
          <div style={{ display: "flex", gap: 20, alignItems: "center", marginBottom: 12, padding: "8px 16px", background: "#1e293b", borderRadius: 10, flexWrap: "wrap" }}>
            <span style={{ color: "#34d399", fontWeight: 700 }}>Score: {score}</span>
            <span style={{ color: "#fbbf24" }}>Revealed: {revealedCount}/{totalTiles}</span>
            <div style={{ flex: 1, minWidth: 100, background: "#334155", borderRadius: 20, height: 8 }}>
              <div style={{ width: `${progressPct}%`, background: "linear-gradient(90deg, #059669, #34d399)", height: 8, borderRadius: 20, transition: "width 0.5s" }} />
            </div>
            <span style={{ color: "#94a3b8", fontSize: 13 }}>{progressPct}%</span>
          </div>

          {/* Artwork with tiles */}
          <div style={{ position: "relative", marginBottom: 16, borderRadius: 12, overflow: "hidden", border: "2px solid #334155" }}>
            <svg viewBox="0 0 600 400" style={{ display: "block", width: "100%" }}>
              {/* Artwork underneath */}
              <ArtworkSVG age={age} />
              {/* Tile overlay */}
              {Array.from({ length: totalTiles }, (_, i) => {
                const col = i % level.cols;
                const row = Math.floor(i / level.cols);
                const revealed = revealedSet.has(i);
                return (
                  <rect
                    key={i}
                    x={col * tileW}
                    y={row * tileH}
                    width={tileW - 1}
                    height={tileH - 1}
                    rx={2}
                    fill="#1e293b"
                    stroke="#0f172a"
                    strokeWidth={1}
                    opacity={revealed ? 0 : 1}
                    style={revealed ? { transition: "opacity 0.5s ease-out" } : {}}
                  />
                );
              })}
              {/* Show artwork label */}
              {revealedCount === 0 && (
                <text x={300} y={210} textAnchor="middle" fill="#94a3b8" fontSize={16} fontWeight="bold">
                  {level.artName}
                </text>
              )}
            </svg>
          </div>

          {/* Question */}
          {phase === "playing" && currentQ && (
            <div className="card" style={{ padding: "20px 24px" }}>
              <div style={{ fontSize: 12, color: "#64748b", textTransform: "uppercase", letterSpacing: 1, marginBottom: 8 }}>
                Question {qIdx + 1} &mdash; Answer to reveal a tile
                {wrongStreak > 0 && <span style={{ color: "#f87171", marginLeft: 12 }}>Tries: {wrongStreak}</span>}
              </div>
              <div style={{ fontWeight: 700, fontSize: 18, marginBottom: 16, lineHeight: 1.4 }}>
                {currentQ.q}
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                {currentQ.options.map((opt, i) => {
                  const isSelected = selectedOpt === i;
                  const bg = answerState === "correct" && isSelected
                    ? "#14532d"
                    : answerState === "wrong" && isSelected
                    ? "#450a0a"
                    : isSelected
                    ? "#1e3a5f"
                    : "#1e293b";
                  const border = answerState === "correct" && isSelected
                    ? "2px solid #22c55e"
                    : answerState === "wrong" && isSelected
                    ? "2px solid #ef4444"
                    : "2px solid #334155";
                  return (
                    <button
                      key={i}
                      onClick={() => pickAnswer(i)}
                      disabled={answerState !== "unanswered"}
                      style={{
                        background: bg,
                        border,
                        borderRadius: 10,
                        padding: "12px 16px",
                        color: answerState === "correct" && isSelected ? "#4ade80"
                          : answerState === "wrong" && isSelected ? "#f87171"
                          : "#e2e8f0",
                        fontWeight: 600,
                        fontSize: 15,
                        textAlign: "left",
                        cursor: answerState !== "unanswered" ? "default" : "pointer",
                        transition: "all 0.2s",
                      }}
                    >
                      <span style={{ color: "#64748b", marginRight: 8 }}>{["A","B","C","D"][i]}.</span>
                      {opt}
                    </button>
                  );
                })}
              </div>
              {answerState === "correct" && (
                <div style={{ marginTop: 12, color: "#4ade80", fontWeight: 700 }}>
                  Correct! Revealing a tile...
                </div>
              )}
              {answerState === "wrong" && (
                <div style={{ marginTop: 12, color: "#f87171", fontWeight: 700 }}>
                  Wrong answer &mdash; try again!
                </div>
              )}
            </div>
          )}
        </>
      )}

      {phase === "done" && (
        <div className="card" style={{ textAlign: "center", padding: 36 }}>
          <div style={{ fontSize: 56, marginBottom: 12 }}>{"🎉"}</div>
          <h2 style={{ color: "#34d399" }}>Artwork fully revealed!</h2>
          <h3 style={{ color: "#fbbf24", marginTop: 4 }}>{level.artName}</h3>
          <p className="muted">
            Final score: <strong style={{ color: "#34d399", fontSize: 22 }}>{score}</strong>
          </p>
          <button onClick={startGame} style={{ marginTop: 16, background: "#059669", color: "#fff", padding: "12px 32px", fontSize: 18, fontWeight: 700, borderRadius: 10, border: "none", cursor: "pointer" }}>
            Play Again
          </button>
        </div>
      )}
    </main>
  );
}

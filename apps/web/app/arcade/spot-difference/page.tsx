"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

type Age = "kids" | "tween" | "teen" | "adult";
type Phase = "idle" | "playing" | "done";

interface Difference {
  id: string;
  // bounding box in the 400x300 SVG coordinate space
  cx: number;
  cy: number;
  r: number; // radius for click detection
  label: string;
}

interface Scene {
  name: string;
  diffs: Difference[];
  renderLeft: () => React.ReactNode;
  renderRight: () => React.ReactNode;
}

// ── Kids scene: Animal Park ──────────────────────────────────────────────────
const kidsScene: Scene = {
  name: "Animal Park",
  diffs: [
    { id: "sun_ray",    cx: 340, cy: 40,  r: 30, label: "Sun missing a ray" },
    { id: "cloud",      cx: 80,  cy: 55,  r: 35, label: "Cloud is missing" },
    { id: "tree_color", cx: 300, cy: 140, r: 40, label: "Tree top color changed" },
    { id: "flower",     cx: 180, cy: 255, r: 28, label: "Extra flower" },
    { id: "bird",       cx: 220, cy: 80,  r: 25, label: "Bird is missing" },
  ],
  renderLeft: () => (
    <g>
      {/* Sky */}
      <rect x={0} y={0} width={400} height={300} fill="#87CEEB" />
      {/* Ground */}
      <rect x={0} y={220} width={400} height={80} fill="#90EE90" />
      {/* Path */}
      <ellipse cx={200} cy={270} rx={60} ry={15} fill="#C8A96E" />
      {/* Sun */}
      <circle cx={340} cy={40} r={28} fill="#FFD700" />
      {/* Sun rays - LEFT has all rays */}
      {[0,45,90,135,180,225,270,315].map((a,i) => (
        <line key={i} x1={340 + Math.cos(a*Math.PI/180)*32} y1={40 + Math.sin(a*Math.PI/180)*32}
          x2={340 + Math.cos(a*Math.PI/180)*44} y2={40 + Math.sin(a*Math.PI/180)*44}
          stroke="#FFD700" strokeWidth={3} strokeLinecap="round" />
      ))}
      {/* Cloud 1 - LEFT has this cloud */}
      <ellipse cx={80} cy={55} rx={40} ry={20} fill="white" />
      <ellipse cx={60} cy={60} rx={25} ry={16} fill="white" />
      <ellipse cx={100} cy={60} rx={28} ry={16} fill="white" />
      {/* Cloud 2 */}
      <ellipse cx={200} cy={45} rx={38} ry={18} fill="white" />
      <ellipse cx={182} cy={50} rx={24} ry={14} fill="white" />
      <ellipse cx={218} cy={50} rx={26} ry={14} fill="white" />
      {/* Bird - LEFT has bird */}
      <path d="M215 80 Q220 74 225 80 Q230 74 235 80" stroke="#333" strokeWidth={2} fill="none" />
      {/* Tree 1 - LEFT has GREEN top */}
      <rect x={290} y={160} width={20} height={60} fill="#8B4513" />
      <circle cx={300} cy={140} r={40} fill="#228B22" />
      {/* Tree 2 */}
      <rect x={100} y={170} width={18} height={50} fill="#8B4513" />
      <circle cx={109} cy={152} r={35} fill="#32CD32" />
      {/* House */}
      <rect x={150} y={170} width={80} height={55} fill="#FF6B6B" />
      <polygon points="150,170 230,170 190,130" fill="#8B0000" />
      <rect x={175} y={195} width={18} height={30} fill="#8B4513" /> {/* door */}
      <rect x={195} y={182} width={22} height={18} fill="#87CEEB" rx={2} /> {/* window */}
      {/* Flower 1 - LEFT has this flower */}
      <line x1={180} y1={275} x2={180} y2={255} stroke="#228B22" strokeWidth={2} />
      <circle cx={180} cy={255} r={8} fill="#FF69B4" />
      <circle cx={172} cy={255} r={5} fill="#FF69B4" />
      <circle cx={188} cy={255} r={5} fill="#FF69B4" />
      <circle cx={180} cy={247} r={5} fill="#FF69B4" />
      <circle cx={180} cy={263} r={5} fill="#FF69B4" />
      <circle cx={180} cy={255} r={4} fill="#FFD700" />
      {/* Flower 2 */}
      <line x1={230} y1={275} x2={230} y2={258} stroke="#228B22" strokeWidth={2} />
      <circle cx={230} cy={258} r={7} fill="#FF4500" />
      <circle cx={223} cy={258} r={4} fill="#FF4500" />
      <circle cx={237} cy={258} r={4} fill="#FF4500" />
      <circle cx={230} cy={252} r={4} fill="#FF4500" />
      <circle cx={230} cy={264} r={4} fill="#FF4500" />
      <circle cx={230} cy={258} r={3.5} fill="#FFD700" />
      {/* Cow */}
      <ellipse cx={60} cy={240} rx={28} ry={18} fill="white" />
      <ellipse cx={83} cy={232} rx={14} ry={10} fill="white" />
      <circle cx={88} cy={228} r={5} fill="white" />
      <circle cx={89} cy={226} r={2} fill="#333" />
      {[0,1,2,3].map(i => <rect key={i} x={50+i*10} y={256} width={5} height={14} rx={2} fill="#ccc" />)}
      <ellipse cx={60} cy={240} rx={8} ry={5} fill="#333" opacity={0.3} />
      {/* Duck */}
      <ellipse cx={350} cy={242} rx={20} ry={12} fill="#FFD700" />
      <circle cx={365} cy={236} r={9} fill="#FFD700" />
      <ellipse cx={373} cy={236} rx={7} ry={4} fill="#FF8C00" />
      <circle cx={368} cy={233} r={2} fill="#333" />
    </g>
  ),
  renderRight: () => (
    <g>
      {/* Sky */}
      <rect x={0} y={0} width={400} height={300} fill="#87CEEB" />
      {/* Ground */}
      <rect x={0} y={220} width={400} height={80} fill="#90EE90" />
      {/* Path */}
      <ellipse cx={200} cy={270} rx={60} ry={15} fill="#C8A96E" />
      {/* Sun - RIGHT missing one ray (270deg ray gone) */}
      <circle cx={340} cy={40} r={28} fill="#FFD700" />
      {[0,45,90,135,180,225,315].map((a,i) => (
        <line key={i} x1={340 + Math.cos(a*Math.PI/180)*32} y1={40 + Math.sin(a*Math.PI/180)*32}
          x2={340 + Math.cos(a*Math.PI/180)*44} y2={40 + Math.sin(a*Math.PI/180)*44}
          stroke="#FFD700" strokeWidth={3} strokeLinecap="round" />
      ))}
      {/* Cloud 1 - RIGHT is MISSING this cloud */}
      {/* Cloud 2 */}
      <ellipse cx={200} cy={45} rx={38} ry={18} fill="white" />
      <ellipse cx={182} cy={50} rx={24} ry={14} fill="white" />
      <ellipse cx={218} cy={50} rx={26} ry={14} fill="white" />
      {/* Bird - RIGHT has NO bird */}
      {/* Tree 1 - RIGHT has ORANGE top */}
      <rect x={290} y={160} width={20} height={60} fill="#8B4513" />
      <circle cx={300} cy={140} r={40} fill="#FF8C00" />
      {/* Tree 2 */}
      <rect x={100} y={170} width={18} height={50} fill="#8B4513" />
      <circle cx={109} cy={152} r={35} fill="#32CD32" />
      {/* House */}
      <rect x={150} y={170} width={80} height={55} fill="#FF6B6B" />
      <polygon points="150,170 230,170 190,130" fill="#8B0000" />
      <rect x={175} y={195} width={18} height={30} fill="#8B4513" />
      <rect x={195} y={182} width={22} height={18} fill="#87CEEB" rx={2} />
      {/* Flower 1 - RIGHT has NO flower at 180,255 */}
      {/* Flower 2 */}
      <line x1={230} y1={275} x2={230} y2={258} stroke="#228B22" strokeWidth={2} />
      <circle cx={230} cy={258} r={7} fill="#FF4500" />
      <circle cx={223} cy={258} r={4} fill="#FF4500" />
      <circle cx={237} cy={258} r={4} fill="#FF4500" />
      <circle cx={230} cy={252} r={4} fill="#FF4500" />
      <circle cx={230} cy={264} r={4} fill="#FF4500" />
      <circle cx={230} cy={258} r={3.5} fill="#FFD700" />
      {/* Cow */}
      <ellipse cx={60} cy={240} rx={28} ry={18} fill="white" />
      <ellipse cx={83} cy={232} rx={14} ry={10} fill="white" />
      <circle cx={88} cy={228} r={5} fill="white" />
      <circle cx={89} cy={226} r={2} fill="#333" />
      {[0,1,2,3].map(i => <rect key={i} x={50+i*10} y={256} width={5} height={14} rx={2} fill="#ccc" />)}
      <ellipse cx={60} cy={240} rx={8} ry={5} fill="#333" opacity={0.3} />
      {/* Duck */}
      <ellipse cx={350} cy={242} rx={20} ry={12} fill="#FFD700" />
      <circle cx={365} cy={236} r={9} fill="#FFD700" />
      <ellipse cx={373} cy={236} rx={7} ry={4} fill="#FF8C00" />
      <circle cx={368} cy={233} r={2} fill="#333" />
    </g>
  ),
};

// ── Tween scene: City Street ─────────────────────────────────────────────────
const tweenScene: Scene = {
  name: "City Street",
  diffs: [
    { id: "stop_sign", cx: 360, cy: 130, r: 32, label: "Stop sign missing" },
    { id: "window",    cx: 120, cy: 100, r: 28, label: "Window added/removed" },
    { id: "car_color", cx: 200, cy: 230, r: 40, label: "Car color changed" },
    { id: "lamp",      cx: 290, cy: 160, r: 30, label: "Street lamp different" },
    { id: "cat",       cx: 80,  cy: 250, r: 28, label: "Cat missing" },
    { id: "antenna",   cx: 155, cy: 50,  r: 25, label: "Antenna missing" },
    { id: "tree_pot",  cx: 340, cy: 220, r: 30, label: "Potted tree missing" },
  ],
  renderLeft: () => (
    <g>
      <rect x={0} y={0} width={400} height={300} fill="#B0C4DE" />
      {/* Road */}
      <rect x={0} y={260} width={400} height={40} fill="#555" />
      {/* Dashes */}
      {[0,1,2,3,4].map(i => <rect key={i} x={20+i*80} y={277} width={50} height={5} fill="#FFD700" />)}
      {/* Sidewalk */}
      <rect x={0} y={240} width={400} height={20} fill="#aaa" />
      {/* Building 1 */}
      <rect x={10} y={60} width={130} height={180} fill="#708090" />
      <rect x={10} y={55} width={130} height={10} fill="#5a6570" />
      {/* Windows building 1 - LEFT has window at 120,100 */}
      {[[30,80],[70,80],[110,80],[30,120],[70,120],[110,120],[30,160],[70,160],[110,160],[120,100]].map(([wx,wy],i) => (
        <rect key={i} x={wx} y={wy} width={22} height={18} rx={2} fill="#87CEEB" opacity={0.8} />
      ))}
      {/* Antenna on building 1 - LEFT has antenna */}
      <line x1={155} y1={55} x2={155} y2={30} stroke="#555" strokeWidth={3} />
      <circle cx={155} cy={29} r={4} fill="#f00" />
      {/* Building 2 */}
      <rect x={250} y={80} width={110} height={160} fill="#8B7355" />
      <rect x={250} y={75} width={110} height={10} fill="#7a6040" />
      {[[265,100],[295,100],[325,100],[265,135],[295,135],[325,135],[265,170],[295,170],[325,170]].map(([wx,wy],i) => (
        <rect key={i} x={wx} y={wy} width={20} height={16} rx={2} fill="#FFE4B5" opacity={0.85} />
      ))}
      {/* Door building 2 */}
      <rect x={290} y={205} width={30} height={35} rx={3} fill="#5a3e28" />
      <circle cx={317} cy={223} r={3} fill="#FFD700" />
      {/* Stop sign - LEFT has stop sign */}
      <line x1={360} y1={240} x2={360} y2={140} stroke="#888" strokeWidth={4} />
      <polygon points="345,115 375,115 390,130 390,150 375,165 345,165 330,150 330,130" fill="#CC0000" />
      <text x={360} y={144} textAnchor="middle" fill="white" fontSize={12} fontWeight="bold">STOP</text>
      {/* Street lamp - LEFT has normal lamp */}
      <line x1={290} y1={240} x2={290} y2={150} stroke="#888" strokeWidth={4} />
      <path d="M290 150 Q310 140 320 155" stroke="#888" strokeWidth={4} fill="none" />
      <ellipse cx={322} cy={158} rx={10} ry={6} fill="#FFD700" opacity={0.9} />
      {/* Car - LEFT is RED */}
      <rect x={140} y={220} width={120} height={40} rx={8} fill="#CC0000" />
      <rect x={155} y={208} width={90} height={25} rx={6} fill="#CC3333" />
      <rect x={162} y={211} width={35} height={18} rx={3} fill="#87CEEB" opacity={0.8} />
      <rect x={202} y={211} width={35} height={18} rx={3} fill="#87CEEB" opacity={0.8} />
      <circle cx={165} cy={262} r={14} fill="#333" /><circle cx={165} cy={262} r={8} fill="#888" />
      <circle cx={235} cy={262} r={14} fill="#333" /><circle cx={235} cy={262} r={8} fill="#888" />
      {/* Cat - LEFT has cat */}
      <ellipse cx={80} cy={252} rx={16} ry={11} fill="#888" />
      <circle cx={88} cy={243} r={9} fill="#888" />
      <polygon points="82,236 86,228 90,236" fill="#888" />
      <polygon points="88,236 92,228 96,236" fill="#888" />
      <circle cx={90} cy={244} r={2} fill="#00ff00" />
      <line x1={80} y1={248} x2={60} y2={245} stroke="#888" strokeWidth={1.5} />
      <line x1={80} y1={251} x2={58} y2={252} stroke="#888" strokeWidth={1.5} />
      {/* Potted tree - LEFT has potted tree */}
      <rect x={328} y={225} width={24} height={18} rx={3} fill="#8B4513" />
      <rect x={325} y={221} width={30} height={6} rx={2} fill="#6B3410" />
      <line x1={340} y1={221} x2={340} y2={200} stroke="#228B22" strokeWidth={3} />
      <circle cx={340} cy={195} r={18} fill="#228B22" />
      <circle cx={328} cy={203} r={10} fill="#2E8B22" />
      <circle cx={352} cy={203} r={10} fill="#2E8B22" />
    </g>
  ),
  renderRight: () => (
    <g>
      <rect x={0} y={0} width={400} height={300} fill="#B0C4DE" />
      {/* Road */}
      <rect x={0} y={260} width={400} height={40} fill="#555" />
      {[0,1,2,3,4].map(i => <rect key={i} x={20+i*80} y={277} width={50} height={5} fill="#FFD700" />)}
      {/* Sidewalk */}
      <rect x={0} y={240} width={400} height={20} fill="#aaa" />
      {/* Building 1 */}
      <rect x={10} y={60} width={130} height={180} fill="#708090" />
      <rect x={10} y={55} width={130} height={10} fill="#5a6570" />
      {/* Windows building 1 - RIGHT missing window at 120,100 */}
      {[[30,80],[70,80],[110,80],[30,120],[70,120],[110,120],[30,160],[70,160],[110,160]].map(([wx,wy],i) => (
        <rect key={i} x={wx} y={wy} width={22} height={18} rx={2} fill="#87CEEB" opacity={0.8} />
      ))}
      {/* Antenna - RIGHT has NO antenna */}
      {/* Building 2 */}
      <rect x={250} y={80} width={110} height={160} fill="#8B7355" />
      <rect x={250} y={75} width={110} height={10} fill="#7a6040" />
      {[[265,100],[295,100],[325,100],[265,135],[295,135],[325,135],[265,170],[295,170],[325,170]].map(([wx,wy],i) => (
        <rect key={i} x={wx} y={wy} width={20} height={16} rx={2} fill="#FFE4B5" opacity={0.85} />
      ))}
      <rect x={290} y={205} width={30} height={35} rx={3} fill="#5a3e28" />
      <circle cx={317} cy={223} r={3} fill="#FFD700" />
      {/* Stop sign - RIGHT has NO stop sign */}
      {/* Street lamp - RIGHT lamp HEAD IS DIFFERENT (points other way) */}
      <line x1={290} y1={240} x2={290} y2={150} stroke="#888" strokeWidth={4} />
      <path d="M290 150 Q270 140 260 155" stroke="#888" strokeWidth={4} fill="none" />
      <ellipse cx={258} cy={158} rx={10} ry={6} fill="#FFD700" opacity={0.9} />
      {/* Car - RIGHT is BLUE */}
      <rect x={140} y={220} width={120} height={40} rx={8} fill="#1a56CC" />
      <rect x={155} y={208} width={90} height={25} rx={6} fill="#2060DD" />
      <rect x={162} y={211} width={35} height={18} rx={3} fill="#87CEEB" opacity={0.8} />
      <rect x={202} y={211} width={35} height={18} rx={3} fill="#87CEEB" opacity={0.8} />
      <circle cx={165} cy={262} r={14} fill="#333" /><circle cx={165} cy={262} r={8} fill="#888" />
      <circle cx={235} cy={262} r={14} fill="#333" /><circle cx={235} cy={262} r={8} fill="#888" />
      {/* Cat - RIGHT has NO cat */}
      {/* Potted tree - RIGHT has NO potted tree */}
    </g>
  ),
};

// ── Teen scene: Science Lab ───────────────────────────────────────────────────
const teenScene: Scene = {
  name: "Science Lab",
  diffs: [
    { id: "flask_color",  cx: 80,  cy: 200, r: 35, label: "Flask liquid color changed" },
    { id: "clock",        cx: 330, cy: 70,  r: 30, label: "Clock reading different" },
    { id: "microscope",   cx: 200, cy: 170, r: 35, label: "Microscope lens missing" },
    { id: "periodic",     cx: 340, cy: 200, r: 35, label: "Element symbol changed" },
    { id: "skeleton_arm", cx: 100, cy: 120, r: 35, label: "Skeleton missing arm bone" },
    { id: "beaker",       cx: 270, cy: 220, r: 30, label: "Beaker has extra bubble" },
    { id: "formula",      cx: 200, cy: 60,  r: 40, label: "Formula on board changed" },
    { id: "plant",        cx: 30,  cy: 260, r: 28, label: "Plant pot added/removed" },
  ],
  renderLeft: () => (
    <g>
      {/* Room */}
      <rect x={0} y={0} width={400} height={300} fill="#f0f4f8" />
      {/* Floor */}
      <rect x={0} y={260} width={400} height={40} fill="#ddd" />
      {/* Lab bench */}
      <rect x={20} y={230} width={360} height={15} fill="#8B7355" />
      <rect x={20} y={245} width={360} height={20} fill="#7a6040" />
      {/* Whiteboard - LEFT: E=mc² */}
      <rect x={120} y={20} width={160} height={80} fill="white" stroke="#aaa" strokeWidth={2} />
      <rect x={120} y={20} width={160} height={8} fill="#ccc" />
      <text x={200} y={68} textAnchor="middle" fill="#222" fontSize={22} fontWeight="bold" fontFamily="serif">E = mc²</text>
      {/* Clock - LEFT: shows 10:10 */}
      <circle cx={330} cy={70} r={28} fill="white" stroke="#888" strokeWidth={3} />
      <line x1={330} y1={70} x2={330} y2={48} stroke="#333" strokeWidth={3} strokeLinecap="round" />
      <line x1={330} y1={70} x2={350} y2={80} stroke="#333" strokeWidth={2} strokeLinecap="round" />
      <circle cx={330} cy={70} r={3} fill="#333" />
      {/* Skeleton - LEFT has both arms */}
      <circle cx={100} cy={55} r={18} fill="#f5f5dc" stroke="#999" strokeWidth={1} />
      <rect x={93} y={72} width={14} height={30} rx={4} fill="#f5f5dc" stroke="#999" strokeWidth={1} />
      <rect x={88} y={100} width={8} height={28} rx={3} fill="#f5f5dc" stroke="#999" strokeWidth={1} />
      <rect x={100} y={100} width={8} height={28} rx={3} fill="#f5f5dc" stroke="#999" strokeWidth={1} />
      {/* LEFT arm */}
      <rect x={75} y={74} width={20} height={7} rx={3} fill="#f5f5dc" stroke="#999" strokeWidth={1} />
      <rect x={63} y={80} width={14} height={22} rx={3} fill="#f5f5dc" stroke="#999" strokeWidth={1} />
      {/* RIGHT arm */}
      <rect x={105} y={74} width={20} height={7} rx={3} fill="#f5f5dc" stroke="#999" strokeWidth={1} />
      <rect x={123} y={80} width={14} height={22} rx={3} fill="#f5f5dc" stroke="#999" strokeWidth={1} />
      {/* Skeleton eye slits */}
      <ellipse cx={94} cy={52} rx={4} ry={5} fill="#777" />
      <ellipse cx={106} cy={52} rx={4} ry={5} fill="#777" />
      {/* Flask - LEFT has GREEN liquid */}
      <line x1={80} y1={155} x2={80} y2={175} stroke="#888" strokeWidth={4} />
      <ellipse cx={80} cy={155} rx={12} ry={5} fill="#ddd" stroke="#888" strokeWidth={2} />
      <path d="M68 175 Q55 210 45 225 L115 225 Q105 210 92 175 Z" fill="white" stroke="#888" strokeWidth={2} />
      <path d="M65 200 Q55 218 48 225 L112 225 Q105 218 95 200 Z" fill="#00CC44" opacity={0.7} />
      <ellipse cx={80} cy={200} rx={15} ry={5} fill="#00DD55" opacity={0.5} />
      {/* Bubbles in flask */}
      <circle cx={72} cy={210} r={3} fill="white" opacity={0.6} />
      <circle cx={85} cy={205} r={2} fill="white" opacity={0.6} />
      {/* Microscope - LEFT has lens */}
      <rect x={185} y={225} width={30} height={10} rx={3} fill="#555" />
      <rect x={195} y={210} width={10} height={20} fill="#555" />
      <path d="M195 210 L185 180 L215 180 L205 210 Z" fill="#666" />
      <rect x={188} y={175} width={24} height={8} rx={2} fill="#444" />
      <ellipse cx={200} cy={175} rx={8} ry={4} fill="#87CEEB" opacity={0.9} stroke="#333" strokeWidth={1} />
      <circle cx={200} cy={170} r={6} fill="#555" />
      <ellipse cx={200} cy={167} rx={5} ry={3} fill="#87CEEB" opacity={0.8} />
      {/* Periodic table element - LEFT: Au */}
      <rect x={315} y={175} width={50} height={50} rx={4} fill="#4a90d9" stroke="#2a70b9" strokeWidth={2} />
      <text x={340} y={198} textAnchor="middle" fill="white" fontSize={20} fontWeight="bold">Au</text>
      <text x={340} y={215} textAnchor="middle" fill="white" fontSize={10}>79</text>
      <text x={340} y={225} textAnchor="middle" fill="white" fontSize={8}>Gold</text>
      {/* Beaker - LEFT: 1 bubble */}
      <rect x={253} y={185} width={35} height={45} rx={4} fill="white" stroke="#888" strokeWidth={2} />
      <path d="M258 230 Q253 228 253 225 L253 210 Q260 230 288 230 L288 225 Q288 228 283 230 Z" fill="#87CEEB" opacity={0.6} />
      <rect x={248} y={183} width={44} height={6} rx={2} fill="#aaa" />
      <circle cx={268} cy={210} r={3} fill="white" opacity={0.8} stroke="#87CEEB" strokeWidth={1} />
      {/* Plant - LEFT has plant */}
      <rect x={20} y={250} width={20} height={14} rx={2} fill="#8B4513" />
      <ellipse cx={30} cy={248} rx={8} ry={6} fill="#228B22" />
      <ellipse cx={22} cy={243} rx={7} ry={5} fill="#32CD32" />
      <ellipse cx={38} cy={243} rx={7} ry={5} fill="#32CD32" />
      <line x1={30} y1={250} x2={30} y2={240} stroke="#228B22" strokeWidth={2} />
    </g>
  ),
  renderRight: () => (
    <g>
      {/* Room */}
      <rect x={0} y={0} width={400} height={300} fill="#f0f4f8" />
      {/* Floor */}
      <rect x={0} y={260} width={400} height={40} fill="#ddd" />
      {/* Lab bench */}
      <rect x={20} y={230} width={360} height={15} fill="#8B7355" />
      <rect x={20} y={245} width={360} height={20} fill="#7a6040" />
      {/* Whiteboard - RIGHT: F=ma */}
      <rect x={120} y={20} width={160} height={80} fill="white" stroke="#aaa" strokeWidth={2} />
      <rect x={120} y={20} width={160} height={8} fill="#ccc" />
      <text x={200} y={68} textAnchor="middle" fill="#222" fontSize={22} fontWeight="bold" fontFamily="serif">F = ma</text>
      {/* Clock - RIGHT: shows 3:00 */}
      <circle cx={330} cy={70} r={28} fill="white" stroke="#888" strokeWidth={3} />
      <line x1={330} y1={70} x2={330} y2={48} stroke="#333" strokeWidth={3} strokeLinecap="round" />
      <line x1={330} y1={70} x2={352} y2={70} stroke="#333" strokeWidth={2} strokeLinecap="round" />
      <circle cx={330} cy={70} r={3} fill="#333" />
      {/* Skeleton - RIGHT is MISSING LEFT arm */}
      <circle cx={100} cy={55} r={18} fill="#f5f5dc" stroke="#999" strokeWidth={1} />
      <rect x={93} y={72} width={14} height={30} rx={4} fill="#f5f5dc" stroke="#999" strokeWidth={1} />
      <rect x={88} y={100} width={8} height={28} rx={3} fill="#f5f5dc" stroke="#999" strokeWidth={1} />
      <rect x={100} y={100} width={8} height={28} rx={3} fill="#f5f5dc" stroke="#999" strokeWidth={1} />
      {/* RIGHT arm only */}
      <rect x={105} y={74} width={20} height={7} rx={3} fill="#f5f5dc" stroke="#999" strokeWidth={1} />
      <rect x={123} y={80} width={14} height={22} rx={3} fill="#f5f5dc" stroke="#999" strokeWidth={1} />
      <ellipse cx={94} cy={52} rx={4} ry={5} fill="#777" />
      <ellipse cx={106} cy={52} rx={4} ry={5} fill="#777" />
      {/* Flask - RIGHT has BLUE liquid */}
      <line x1={80} y1={155} x2={80} y2={175} stroke="#888" strokeWidth={4} />
      <ellipse cx={80} cy={155} rx={12} ry={5} fill="#ddd" stroke="#888" strokeWidth={2} />
      <path d="M68 175 Q55 210 45 225 L115 225 Q105 210 92 175 Z" fill="white" stroke="#888" strokeWidth={2} />
      <path d="M65 200 Q55 218 48 225 L112 225 Q105 218 95 200 Z" fill="#0066CC" opacity={0.7} />
      <ellipse cx={80} cy={200} rx={15} ry={5} fill="#0077DD" opacity={0.5} />
      <circle cx={72} cy={210} r={3} fill="white" opacity={0.6} />
      <circle cx={85} cy={205} r={2} fill="white" opacity={0.6} />
      {/* Microscope - RIGHT is MISSING lens */}
      <rect x={185} y={225} width={30} height={10} rx={3} fill="#555" />
      <rect x={195} y={210} width={10} height={20} fill="#555" />
      <path d="M195 210 L185 180 L215 180 L205 210 Z" fill="#666" />
      <rect x={188} y={175} width={24} height={8} rx={2} fill="#444" />
      {/* No lens here */}
      {/* Periodic table element - RIGHT: Ag */}
      <rect x={315} y={175} width={50} height={50} rx={4} fill="#9b59b6" stroke="#7d3c98" strokeWidth={2} />
      <text x={340} y={198} textAnchor="middle" fill="white" fontSize={20} fontWeight="bold">Ag</text>
      <text x={340} y={215} textAnchor="middle" fill="white" fontSize={10}>47</text>
      <text x={340} y={225} textAnchor="middle" fill="white" fontSize={8}>Silver</text>
      {/* Beaker - RIGHT: 2 bubbles */}
      <rect x={253} y={185} width={35} height={45} rx={4} fill="white" stroke="#888" strokeWidth={2} />
      <path d="M258 230 Q253 228 253 225 L253 210 Q260 230 288 230 L288 225 Q288 228 283 230 Z" fill="#87CEEB" opacity={0.6} />
      <rect x={248} y={183} width={44} height={6} rx={2} fill="#aaa" />
      <circle cx={268} cy={210} r={3} fill="white" opacity={0.8} stroke="#87CEEB" strokeWidth={1} />
      <circle cx={278} cy={200} r={3} fill="white" opacity={0.8} stroke="#87CEEB" strokeWidth={1} />
      {/* Plant - RIGHT has NO plant */}
    </g>
  ),
};

const SCENES: Record<Age, Scene[]> = {
  kids:  [kidsScene],
  tween: [tweenScene],
  teen:  [teenScene],
  adult: [teenScene], // reuse teen scene for adult
};

function dist(ax: number, ay: number, bx: number, by: number) {
  return Math.sqrt((ax - bx) ** 2 + (ay - by) ** 2);
}

export default function SpotDifference() {
  const [age, setAge] = useState<Age>("kids");
  const [phase, setPhase] = useState<Phase>("idle");
  const [sceneIdx, setSceneIdx] = useState(0);
  const [found, setFound] = useState<Set<string>>(new Set());
  const [wrongFlash, setWrongFlash] = useState<{ x: number; y: number; side: "L" | "R" } | null>(null);
  const [score, setScore] = useState(0);
  const [elapsed, setElapsed] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    const q = new URLSearchParams(window.location.search).get("age");
    if (q === "kids" || q === "tween" || q === "teen" || q === "adult") setAge(q as Age);
  }, []);

  const scene = SCENES[age]?.[sceneIdx] ?? SCENES["kids"][0];
  const diffs = scene.diffs;

  const startGame = () => {
    setFound(new Set());
    setScore(0);
    setElapsed(0);
    setWrongFlash(null);
    setPhase("playing");
    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = setInterval(() => setElapsed((e) => e + 1), 1000);
  };

  useEffect(() => {
    if (phase === "done" && timerRef.current) clearInterval(timerRef.current);
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [phase]);

  function handleClick(e: React.MouseEvent<SVGSVGElement>, side: "L" | "R") {
    if (phase !== "playing") return;
    const rect = e.currentTarget.getBoundingClientRect();
    const scaleX = 400 / rect.width;
    const scaleY = 300 / rect.height;
    const x = (e.clientX - rect.left) * scaleX;
    const y = (e.clientY - rect.top) * scaleY;

    for (const d of diffs) {
      if (found.has(d.id)) continue;
      if (dist(x, y, d.cx, d.cy) <= d.r) {
        const next = new Set(found);
        next.add(d.id);
        setFound(next);
        setScore((s) => s + 100);
        if (next.size === diffs.length) {
          setPhase("done");
        }
        return;
      }
    }
    // Wrong click
    setScore((s) => Math.max(0, s - 5));
    setWrongFlash({ x: (e.clientX - rect.left) / rect.width * 100, y: (e.clientY - rect.top) / rect.height * 100, side });
    setTimeout(() => setWrongFlash(null), 600);
  }

  const fmt = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

  const svgStyle: React.CSSProperties = {
    width: "100%",
    cursor: phase === "playing" ? "crosshair" : "default",
    border: "2px solid #334155",
    borderRadius: 8,
    display: "block",
    userSelect: "none",
  };

  const FoundOverlay = ({ side }: { side: "L" | "R" }) => (
    <>
      {diffs.map((d) =>
        found.has(d.id) ? (
          <circle key={d.id} cx={d.cx} cy={d.cy} r={d.r}
            fill="none" stroke="#22c55e" strokeWidth={3} opacity={0.9}
            style={{ filter: "drop-shadow(0 0 6px #22c55e)" }} />
        ) : null
      )}
      {wrongFlash && wrongFlash.side === side && (
        <circle cx={wrongFlash.x * 4} cy={wrongFlash.y * 3} r={20}
          fill="none" stroke="#ef4444" strokeWidth={3} opacity={0.8} />
      )}
    </>
  );

  return (
    <main className="container" style={{ maxWidth: 920, paddingBottom: 48 }}>
      <style>{`
        @keyframes celebrate {
          0%   { transform: scale(1) rotate(0deg); }
          25%  { transform: scale(1.15) rotate(-3deg); }
          50%  { transform: scale(1.15) rotate(3deg); }
          100% { transform: scale(1) rotate(0deg); }
        }
        @keyframes diffFound {
          0%   { stroke-width: 3; opacity: 0.5; }
          50%  { stroke-width: 6; opacity: 1; }
          100% { stroke-width: 3; opacity: 0.9; }
        }
      `}</style>

      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap", marginBottom: 4 }}>
        <h1 style={{ margin: 0 }}>Spot the Difference</h1>
        <Link href="/arcade" style={{ marginLeft: "auto", color: "#94a3b8" }}>Back to Arcade</Link>
      </div>
      <p className="muted" style={{ marginBottom: 12 }}>
        Find all differences between the two panels. Click on any difference in either panel!
      </p>

      {/* Age selector */}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 16 }}>
        {(["kids", "tween", "teen", "adult"] as Age[]).map((a) => (
          <button key={a} onClick={() => { setAge(a); setSceneIdx(0); setPhase("idle"); }}
            disabled={phase === "playing"}
            style={{ opacity: age === a ? 1 : 0.5 }}>
            {a === "kids" ? "Kids" : a === "tween" ? "Tween" : a === "teen" ? "Teen" : "Adult"}
          </button>
        ))}
      </div>

      {/* Score bar */}
      {phase !== "idle" && (
        <div style={{ display: "flex", gap: 24, alignItems: "center", marginBottom: 12, padding: "8px 16px", background: "#1e293b", borderRadius: 10 }}>
          <span style={{ color: "#34d399", fontWeight: 700 }}>Score: {score}</span>
          <span style={{ color: "#94a3b8" }}>Time: {fmt(elapsed)}</span>
          <span style={{ color: "#fbbf24" }}>Found: {found.size}/{diffs.length}</span>
          <span style={{ color: "#64748b", fontSize: 13 }}>Scene: {scene.name}</span>
        </div>
      )}

      {/* Idle */}
      {phase === "idle" && (
        <div style={{ textAlign: "center", padding: 48 }}>
          <div style={{ fontSize: 56, marginBottom: 12 }}>?</div>
          <h2 style={{ marginBottom: 8 }}>
            {age === "kids" ? "Find 5 differences in the Animal Park!" :
             age === "tween" ? "Find 7 differences on the City Street!" :
             "Find 8 differences in the Science Lab!"}
          </h2>
          <p className="muted" style={{ marginBottom: 28 }}>
            Click on the differences in either panel. +100 pts each, -5 for wrong clicks.
          </p>
          <button onClick={startGame} style={{ background: "#0891b2", color: "#fff", padding: "14px 36px", fontSize: 20, fontWeight: 700, borderRadius: 12, border: "none", cursor: "pointer" }}>
            Start Game
          </button>
        </div>
      )}

      {/* Game panels */}
      {(phase === "playing" || phase === "done") && (
        <>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 16 }}>
            {/* Left panel */}
            <div style={{ position: "relative" }}>
              <div style={{ textAlign: "center", fontSize: 13, color: "#94a3b8", marginBottom: 4 }}>Panel A</div>
              <svg viewBox="0 0 400 300" style={svgStyle} onClick={(e) => handleClick(e, "L")}>
                {scene.renderLeft()}
                <FoundOverlay side="L" />
              </svg>
            </div>
            {/* Right panel */}
            <div style={{ position: "relative" }}>
              <div style={{ textAlign: "center", fontSize: 13, color: "#94a3b8", marginBottom: 4 }}>Panel B</div>
              <svg viewBox="0 0 400 300" style={svgStyle} onClick={(e) => handleClick(e, "R")}>
                {scene.renderRight()}
                <FoundOverlay side="R" />
              </svg>
            </div>
          </div>

          {/* Difference checklist */}
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 16 }}>
            {diffs.map((d) => (
              <span key={d.id} style={{
                padding: "6px 12px", borderRadius: 20, fontSize: 13,
                background: found.has(d.id) ? "#14532d" : "#1e293b",
                color: found.has(d.id) ? "#4ade80" : "#94a3b8",
                border: `1px solid ${found.has(d.id) ? "#22c55e" : "#334155"}`,
                transition: "all 0.3s",
              }}>
                {found.has(d.id) ? "Found: " : "? "}{d.label}
              </span>
            ))}
          </div>
        </>
      )}

      {/* Done */}
      {phase === "done" && (
        <div className="card" style={{ textAlign: "center", padding: 36 }}>
          <div style={{ fontSize: 56, marginBottom: 12, animation: "celebrate 0.6s ease-out" }}>Done!</div>
          <h2 style={{ color: "#34d399" }}>All differences found!</h2>
          <p className="muted">
            Final score: <strong style={{ color: "#34d399", fontSize: 22 }}>{score}</strong>
            &ensp;&middot;&ensp;Time: <strong>{fmt(elapsed)}</strong>
          </p>
          <button onClick={startGame} style={{ marginTop: 16, background: "#0891b2", color: "#fff", padding: "12px 32px", fontSize: 18, fontWeight: 700, borderRadius: 10, border: "none", cursor: "pointer" }}>
            Play Again
          </button>
        </div>
      )}
    </main>
  );
}

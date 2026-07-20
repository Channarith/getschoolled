"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

type Age = "kids" | "tween" | "teen" | "adult";
type Phase = "idle" | "playing" | "done";

interface HiddenItem {
  id: string;
  label: string;
  emoji: string;
  // click target center in 600x400 SVG space
  cx: number;
  cy: number;
  r: number; // detection radius
}

interface SceneDef {
  name: string;
  bg: string;
  items: HiddenItem[];
  render: (found: Set<string>, glowing: string | null) => React.ReactNode;
}

// ── Underwater Ocean scene ────────────────────────────────────────────────────
const oceanScene: SceneDef = {
  name: "Underwater Ocean",
  bg: "#003366",
  items: [
    { id: "clownfish",    label: "Clown Fish",    emoji: "🐠", cx: 120, cy: 150, r: 28 },
    { id: "starfish",     label: "Starfish",      emoji: "⭐", cx: 490, cy: 310, r: 28 },
    { id: "treasure",     label: "Treasure Chest",emoji: "📦", cx: 300, cy: 350, r: 40 },
    { id: "anchor",       label: "Anchor",        emoji: "⚓", cx: 540, cy: 210, r: 30 },
    { id: "shell",        label: "Shell",         emoji: "🐚", cx: 80,  cy: 345, r: 28 },
    { id: "jellyfish",    label: "Jellyfish",     emoji: "🪼", cx: 420, cy: 100, r: 35 },
    { id: "turtle",       label: "Sea Turtle",    emoji: "🐢", cx: 220, cy: 270, r: 38 },
    { id: "crab",         label: "Crab",          emoji: "🦀", cx: 390, cy: 370, r: 30 },
    { id: "pufferfish",   label: "Puffer Fish",   emoji: "🐡", cx: 530, cy: 150, r: 30 },
    { id: "coral_pink",   label: "Pink Coral",    emoji: "🪸", cx: 160, cy: 360, r: 35 },
  ],
  render: (found, glowing) => (
    <g>
      {/* Ocean background gradient */}
      <defs>
        <linearGradient id="oceanGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#001a33" />
          <stop offset="100%" stopColor="#003366" />
        </linearGradient>
        <radialGradient id="glowGrad" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#22c55e" stopOpacity="0.5" />
          <stop offset="100%" stopColor="#22c55e" stopOpacity="0" />
        </radialGradient>
      </defs>
      <rect x={0} y={0} width={600} height={400} fill="url(#oceanGrad)" />

      {/* Light rays from surface */}
      {[100,200,350,480].map((x,i) => (
        <polygon key={i} points={`${x},0 ${x+30},0 ${x+60},400 ${x+20},400`}
          fill="white" opacity={0.03} />
      ))}

      {/* Sandy floor */}
      <path d="M0 360 Q150 340 300 360 Q450 380 600 355 L600 400 L0 400 Z" fill="#C8A96E" />
      {/* Sand ripples */}
      {[50,150,250,350,450,550].map((x,i) => (
        <ellipse key={i} cx={x} cy={375+i%3*5} rx={25} ry={4} fill="#b8996e" opacity={0.5} />
      ))}

      {/* Seaweed */}
      {[30, 170, 450, 570].map((x, i) => (
        <g key={i}>
          <path d={`M${x} 400 Q${x-15} 360 ${x} 330 Q${x+15} 300 ${x} 270`}
            stroke="#1a5c1a" strokeWidth={6} fill="none" strokeLinecap="round" />
          <ellipse cx={x} cy={268} rx={10} ry={14} fill="#228B22" />
          <path d={`M${x} 380 Q${x+20} 355 ${x+5} 335`}
            stroke="#2d8b2d" strokeWidth={4} fill="none" strokeLinecap="round" />
          <ellipse cx={x+5} cy={333} rx={8} ry={11} fill="#32a832" />
        </g>
      ))}

      {/* Coral formations */}
      {/* Pink coral - item */}
      <g>
        {[155,165,175,160,170].map((x,i) => (
          <line key={i} x1={x} y1={400} x2={x+(i%2===0?-8:8)} y2={350-i*8}
            stroke="#FF69B4" strokeWidth={5} strokeLinecap="round" />
        ))}
        <circle cx={155} cy={352} r={8} fill="#FF69B4" />
        <circle cx={165} cy={342} r={9} fill="#FF1493" />
        <circle cx={175} cy={350} r={7} fill="#FF69B4" />
        <circle cx={160} cy={330} r={8} fill="#FF69B4" />
        <circle cx={170} cy={325} r={10} fill="#FF1493" />
        {glowing === "coral_pink" && <circle cx={160} cy={358} r={35} fill="url(#glowGrad)" />}
        {found.has("coral_pink") && <circle cx={160} cy={358} r={35} fill="none" stroke="#22c55e" strokeWidth={3} opacity={0.9} />}
      </g>

      {/* Orange/red coral right side */}
      {[350,365,378,358,370].map((x,i) => (
        <line key={i} x1={x+230} y1={400} x2={x+230+(i%2===0?-6:10)} y2={355-i*7}
          stroke="#FF6B35" strokeWidth={4} strokeLinecap="round" />
      ))}
      {[580,592,604,586,598].map((x,i) => (
        <circle key={i} cx={x} cy={355-i*7} r={6} fill="#FF6B35" />
      ))}

      {/* Rocks on floor */}
      <ellipse cx={440} cy={378} rx={35} ry={18} fill="#555" />
      <ellipse cx={480} cy={385} rx={20} ry={12} fill="#666" />
      <ellipse cx={200} cy={383} rx={28} ry={14} fill="#666" />
      <ellipse cx={60} cy={380} rx={22} ry={12} fill="#555" />

      {/* CLOWN FISH - item */}
      <g>
        <ellipse cx={120} cy={150} rx={24} ry={14} fill="#FF6600" />
        <ellipse cx={120} cy={150} rx={14} ry={13} fill="#FF6600" />
        <line x1={104} y1={140} x2={104} y2={160} stroke="white" strokeWidth={3} />
        <line x1={120} y1={138} x2={120} y2={162} stroke="white" strokeWidth={3} />
        <line x1={136} y1={141} x2={136} y2={159} stroke="white" strokeWidth={3} />
        <ellipse cx={130} cy={148} rx={6} ry={8} fill="#222" opacity={0.3} />
        <circle cx={113} cy={147} r={4} fill="#222" />
        <circle cx={112} cy={146} r={1.5} fill="white" />
        {glowing === "clownfish" && <circle cx={120} cy={150} r={28} fill="url(#glowGrad)" />}
        {found.has("clownfish") && <circle cx={120} cy={150} r={28} fill="none" stroke="#22c55e" strokeWidth={3} opacity={0.9} />}
      </g>

      {/* JELLYFISH - item */}
      <g>
        <ellipse cx={420} cy={95} rx={30} ry={22} fill="#FF69B4" opacity={0.7} />
        <path d="M395 115 Q400 130 395 145" stroke="#FF69B4" strokeWidth={2} fill="none" opacity={0.6} />
        <path d="M405 118 Q408 135 403 150" stroke="#FF69B4" strokeWidth={2} fill="none" opacity={0.6} />
        <path d="M415 120 Q416 140 413 155" stroke="#FF69B4" strokeWidth={2} fill="none" opacity={0.6} />
        <path d="M425 120 Q426 140 423 155" stroke="#FF69B4" strokeWidth={2} fill="none" opacity={0.6} />
        <path d="M435 118 Q438 135 433 150" stroke="#FF69B4" strokeWidth={2} fill="none" opacity={0.6} />
        <path d="M445 115 Q450 130 445 145" stroke="#FF69B4" strokeWidth={2} fill="none" opacity={0.6} />
        <ellipse cx={420} cy={90} rx={20} ry={14} fill="#FFB6C1" opacity={0.5} />
        {glowing === "jellyfish" && <circle cx={420} cy={100} r={35} fill="url(#glowGrad)" />}
        {found.has("jellyfish") && <circle cx={420} cy={100} r={35} fill="none" stroke="#22c55e" strokeWidth={3} opacity={0.9} />}
      </g>

      {/* SEA TURTLE - item */}
      <g>
        <ellipse cx={220} cy={270} rx={35} ry={26} fill="#2d7a2d" />
        {/* Shell pattern */}
        <ellipse cx={220} cy={270} rx={25} ry={18} fill="#3a9c3a" />
        <line x1={220} y1={252} x2={220} y2={288} stroke="#2d7a2d" strokeWidth={2} />
        <line x1={195} y1={270} x2={245} y2={270} stroke="#2d7a2d" strokeWidth={2} />
        {/* Head */}
        <ellipse cx={253} cy={262} rx={14} ry={11} fill="#4ab04a" />
        <circle cx={259} cy={259} r={3} fill="#111" />
        <circle cx={258} cy={258} r={1} fill="white" />
        {/* Flippers */}
        <ellipse cx={188} cy={255} rx={15} ry={7} fill="#3a9c3a" transform="rotate(-20 188 255)" />
        <ellipse cx={188} cy={285} rx={15} ry={7} fill="#3a9c3a" transform="rotate(20 188 285)" />
        <ellipse cx={252} cy={255} rx={12} ry={6} fill="#3a9c3a" transform="rotate(20 252 255)" />
        <ellipse cx={252} cy={285} rx={12} ry={6} fill="#3a9c3a" transform="rotate(-20 252 285)" />
        {glowing === "turtle" && <circle cx={220} cy={270} r={38} fill="url(#glowGrad)" />}
        {found.has("turtle") && <circle cx={220} cy={270} r={38} fill="none" stroke="#22c55e" strokeWidth={3} opacity={0.9} />}
      </g>

      {/* TREASURE CHEST - item */}
      <g>
        <rect x={265} y={330} width={70} height={48} rx={4} fill="#8B4513" stroke="#5a2d0c" strokeWidth={2} />
        <rect x={265} y={330} width={70} height={14} rx={4} fill="#A0522D" stroke="#5a2d0c" strokeWidth={2} />
        {/* Chest lid arc */}
        <path d="M265 340 Q300 320 335 340" fill="#A0522D" stroke="#5a2d0c" strokeWidth={2} />
        {/* Metal bands */}
        <rect x={295} y={330} width={10} height={48} fill="#FFD700" opacity={0.5} />
        <rect x={265} y={355} width={70} height={6} fill="#FFD700" opacity={0.5} />
        {/* Lock */}
        <rect x={292} y={348} width={16} height={12} rx={3} fill="#FFD700" />
        <path d="M296 348 Q300 338 304 348" fill="none" stroke="#FFD700" strokeWidth={3} />
        {/* Gold coins spilling */}
        <circle cx={285} cy={378} r={7} fill="#FFD700" />
        <circle cx={315} cy={380} r={7} fill="#FFD700" />
        <circle cx={330} cy={375} r={7} fill="#FFD700" />
        <circle cx={272} cy={375} r={6} fill="#FFD700" />
        {glowing === "treasure" && <circle cx={300} cy={350} r={40} fill="url(#glowGrad)" />}
        {found.has("treasure") && <circle cx={300} cy={350} r={40} fill="none" stroke="#22c55e" strokeWidth={3} opacity={0.9} />}
      </g>

      {/* ANCHOR - item */}
      <g>
        <line x1={540} y1={165} x2={540} y2={240} stroke="#888" strokeWidth={6} strokeLinecap="round" />
        <circle cx={540} cy={165} r={10} fill="none" stroke="#888" strokeWidth={5} />
        <line x1={520} y1={175} x2={560} y2={175} stroke="#888" strokeWidth={5} strokeLinecap="round" />
        <path d="M520 240 Q530 255 540 240 Q550 255 560 240" fill="none" stroke="#888" strokeWidth={5} strokeLinecap="round" />
        {glowing === "anchor" && <circle cx={540} cy={210} r={30} fill="url(#glowGrad)" />}
        {found.has("anchor") && <circle cx={540} cy={210} r={30} fill="none" stroke="#22c55e" strokeWidth={3} opacity={0.9} />}
      </g>

      {/* SHELL - item */}
      <g>
        <path d="M80 345 Q55 320 70 360 Q85 385 110 370 Q125 350 100 335 Q85 325 80 345 Z" fill="#FFB6C1" stroke="#FF69B4" strokeWidth={1.5} />
        <path d="M80 345 Q90 335 100 350 Q95 365 80 360 Z" fill="#FF69B4" opacity={0.5} />
        <line x1={85} y1={340} x2={75} y2={368} stroke="#FF1493" strokeWidth={1.5} opacity={0.6} />
        <line x1={92} y1={337} x2={88} y2={370} stroke="#FF1493" strokeWidth={1.5} opacity={0.6} />
        <line x1={99} y1={338} x2={100} y2={368} stroke="#FF1493" strokeWidth={1.5} opacity={0.6} />
        {glowing === "shell" && <circle cx={80} cy={348} r={28} fill="url(#glowGrad)" />}
        {found.has("shell") && <circle cx={80} cy={348} r={28} fill="none" stroke="#22c55e" strokeWidth={3} opacity={0.9} />}
      </g>

      {/* STARFISH - item */}
      <g>
        <polygon points="490,285 497,308 520,310 503,324 510,347 490,333 470,347 477,324 460,310 483,308"
          fill="#FF8C00" stroke="#FF6600" strokeWidth={1.5} />
        <circle cx={490} cy={315} r={8} fill="#FFD700" />
        {glowing === "starfish" && <circle cx={490} cy={315} r={28} fill="url(#glowGrad)" />}
        {found.has("starfish") && <circle cx={490} cy={315} r={28} fill="none" stroke="#22c55e" strokeWidth={3} opacity={0.9} />}
      </g>

      {/* CRAB - item */}
      <g>
        <ellipse cx={390} cy={372} rx={22} ry={14} fill="#CC2200" />
        {/* Eyes */}
        <circle cx={378} cy={363} r={5} fill="#CC2200" />
        <circle cx={402} cy={363} r={5} fill="#CC2200" />
        <circle cx={378} cy={362} r={3} fill="#111" />
        <circle cx={402} cy={362} r={3} fill="#111" />
        {/* Claws */}
        <path d="M368 370 Q355 360 348 370 Q355 378 368 376 Z" fill="#CC2200" />
        <path d="M412 370 Q425 360 432 370 Q425 378 412 376 Z" fill="#CC2200" />
        {/* Legs */}
        {[-2,-1,0,1,2].map(i => (
          <g key={i}>
            <line x1={380+i*5} y1={382} x2={370+i*8} y2={395} stroke="#CC2200" strokeWidth={3} strokeLinecap="round" />
            <line x1={400+i*2} y1={382} x2={410+i*5} y2={395} stroke="#CC2200" strokeWidth={3} strokeLinecap="round" />
          </g>
        ))}
        {glowing === "crab" && <circle cx={390} cy={372} r={30} fill="url(#glowGrad)" />}
        {found.has("crab") && <circle cx={390} cy={372} r={30} fill="none" stroke="#22c55e" strokeWidth={3} opacity={0.9} />}
      </g>

      {/* PUFFER FISH - item */}
      <g>
        <circle cx={530} cy={150} r={26} fill="#FFD700" stroke="#FF8C00" strokeWidth={2} />
        {/* Spikes */}
        {[0,30,60,90,120,150,180,210,240,270,300,330].map((a,i) => (
          <line key={i}
            x1={530 + Math.cos(a*Math.PI/180)*26} y1={150 + Math.sin(a*Math.PI/180)*26}
            x2={530 + Math.cos(a*Math.PI/180)*36} y2={150 + Math.sin(a*Math.PI/180)*36}
            stroke="#FF8C00" strokeWidth={2.5} strokeLinecap="round" />
        ))}
        {/* Eye */}
        <circle cx={542} cy={144} r={7} fill="white" />
        <circle cx={543} cy={144} r={4} fill="#111" />
        <circle cx={544} cy={143} r={1.5} fill="white" />
        {/* Mouth */}
        <path d="M526 156 Q530 160 534 156" stroke="#FF8C00" strokeWidth={2} fill="none" />
        {/* Fins */}
        <ellipse cx={514} cy={142} rx={10} ry={5} fill="#FF8C00" transform="rotate(-30 514 142)" />
        <ellipse cx={514} cy={158} rx={10} ry={5} fill="#FF8C00" transform="rotate(30 514 158)" />
        {glowing === "pufferfish" && <circle cx={530} cy={150} r={30} fill="url(#glowGrad)" />}
        {found.has("pufferfish") && <circle cx={530} cy={150} r={30} fill="none" stroke="#22c55e" strokeWidth={3} opacity={0.9} />}
      </g>

      {/* Bubbles rising */}
      {[60,140,300,400,500,560].map((x,i) => (
        <g key={i}>
          <circle cx={x} cy={200-i*15} r={4+i%3} fill="none" stroke="white" strokeWidth={1} opacity={0.3} />
          <circle cx={x+15} cy={160-i*10} r={3} fill="none" stroke="white" strokeWidth={1} opacity={0.2} />
        </g>
      ))}

      {/* Fish school (not items) */}
      {[{x:320,y:80},{x:340,y:75},{x:360,y:82},{x:330,y:90},{x:350,y:88}].map((f,i) => (
        <g key={i}>
          <ellipse cx={f.x} cy={f.y} rx={10} ry={5} fill="#4FC3F7" opacity={0.8} />
          <polygon points={`${f.x-10},${f.y-4} ${f.x-10},${f.y+4} ${f.x-18},${f.y}`} fill="#4FC3F7" opacity={0.8} />
          <circle cx={f.x+5} cy={f.y-1} r={1.5} fill="#111" opacity={0.7} />
        </g>
      ))}
    </g>
  ),
};

// ── Forest scene (tween/teen) ────────────────────────────────────────────────
const forestScene: SceneDef = {
  name: "Enchanted Forest",
  bg: "#1a2f1a",
  items: [
    { id: "owl",        label: "Owl",          emoji: "🦉", cx: 480, cy: 110, r: 32 },
    { id: "mushroom",   label: "Mushroom",     emoji: "🍄", cx: 130, cy: 320, r: 32 },
    { id: "butterfly",  label: "Butterfly",    emoji: "🦋", cx: 280, cy: 180, r: 30 },
    { id: "fox",        label: "Fox",          emoji: "🦊", cx: 380, cy: 305, r: 38 },
    { id: "beehive",    label: "Beehive",      emoji: "🍯", cx: 165, cy: 140, r: 32 },
    { id: "deer",       label: "Deer",         emoji: "🦌", cx: 490, cy: 280, r: 40 },
    { id: "frog",       label: "Frog",         emoji: "🐸", cx: 75,  cy: 355, r: 28 },
    { id: "acorn",      label: "Acorn",        emoji: "🌰", cx: 340, cy: 360, r: 25 },
    { id: "spider_web", label: "Spider Web",   emoji: "🕸️", cx: 220, cy: 95,  r: 30 },
    { id: "hedgehog",   label: "Hedgehog",     emoji: "🦔", cx: 85,  cy: 240, r: 28 },
  ],
  render: (found, glowing) => (
    <g>
      <defs>
        <linearGradient id="forestGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#0a1a0a" />
          <stop offset="60%" stopColor="#1a3a1a" />
          <stop offset="100%" stopColor="#2d5a2d" />
        </linearGradient>
        <radialGradient id="glowGradF" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#22c55e" stopOpacity="0.5" />
          <stop offset="100%" stopColor="#22c55e" stopOpacity="0" />
        </radialGradient>
      </defs>
      <rect x={0} y={0} width={600} height={400} fill="url(#forestGrad)" />

      {/* Ground */}
      <path d="M0 330 Q200 310 400 330 Q500 340 600 325 L600 400 L0 400 Z" fill="#2d5a2d" />
      <path d="M0 350 Q300 340 600 345 L600 400 L0 400 Z" fill="#3a7a3a" />

      {/* Background trees */}
      {[50,150,350,500,570].map((x,i) => (
        <g key={i}>
          <rect x={x-8} y={200+i%2*20} width={16} height={180} fill="#4a3728" />
          <circle cx={x} cy={190+i%2*20} r={55+i%3*10} fill="#1a4a1a" opacity={0.9} />
          <circle cx={x-15} cy={210+i%2*20} r={40} fill="#1f5a1f" opacity={0.8} />
          <circle cx={x+15} cy={215+i%2*20} r={38} fill="#1a4a1a" opacity={0.8} />
        </g>
      ))}

      {/* Foreground tree with big trunk */}
      <rect x={430} y={100} width={30} height={300} fill="#5a4030" />
      <circle cx={445} cy={100} r={80} fill="#145214" />
      <circle cx={420} cy={120} r={60} fill="#1a6a1a" />
      <circle cx={470} cy={115} r={65} fill="#145214" />

      {/* Left tree */}
      <rect x={100} y={80} width={25} height={320} fill="#5a4030" />
      <circle cx={112} cy={80} r={70} fill="#145214" />
      <circle cx={90} cy={100} r={50} fill="#1a6a1a" />
      <circle cx={135} cy={95} r={55} fill="#145214" />

      {/* Grass tufts */}
      {[20,60,200,300,420,550].map((x,i) => (
        <g key={i}>
          <path d={`M${x} 400 Q${x-8} 370 ${x-5} 350`} stroke="#3a8a3a" strokeWidth={4} fill="none" strokeLinecap="round" />
          <path d={`M${x+5} 400 Q${x+2} 365 ${x+8} 345`} stroke="#2d7a2d" strokeWidth={4} fill="none" strokeLinecap="round" />
          <path d={`M${x+12} 400 Q${x+18} 372 ${x+15} 352`} stroke="#3a8a3a" strokeWidth={3} fill="none" strokeLinecap="round" />
        </g>
      ))}

      {/* Flowers on ground */}
      {[250,310,410,480].map((x,i) => (
        <g key={i}>
          <line x1={x} y1={370} x2={x} y2={345} stroke="#2d7a2d" strokeWidth={2} />
          <circle cx={x} cy={343} r={6} fill={["#FF69B4","#FFD700","#FF4500","#9370DB"][i]} />
        </g>
      ))}

      {/* OWL - item */}
      <g>
        <ellipse cx={480} cy={118} rx={22} ry={28} fill="#8B6914" />
        <ellipse cx={480} cy={108} rx={16} ry={14} fill="#C8A96E" />
        {/* Eyes */}
        <circle cx={473} cy={106} r={8} fill="#FFD700" />
        <circle cx={487} cy={106} r={8} fill="#FFD700" />
        <circle cx={473} cy={106} r={5} fill="#111" />
        <circle cx={487} cy={106} r={5} fill="#111" />
        <circle cx={474} cy={105} r={2} fill="white" />
        <circle cx={488} cy={105} r={2} fill="white" />
        {/* Beak */}
        <polygon points="480,110 476,116 484,116" fill="#FF8C00" />
        {/* Ear tufts */}
        <polygon points="468,95 465,85 473,92" fill="#8B6914" />
        <polygon points="492,95 495,85 487,92" fill="#8B6914" />
        {/* Wings */}
        <ellipse cx={462} cy={122} rx={12} ry={18} fill="#6B5010" />
        <ellipse cx={498} cy={122} rx={12} ry={18} fill="#6B5010" />
        {/* Feet */}
        <line x1={475} y1={145} x2={470} y2={158} stroke="#FF8C00" strokeWidth={3} strokeLinecap="round" />
        <line x1={485} y1={145} x2={490} y2={158} stroke="#FF8C00" strokeWidth={3} strokeLinecap="round" />
        {glowing === "owl" && <circle cx={480} cy={115} r={32} fill="url(#glowGradF)" />}
        {found.has("owl") && <circle cx={480} cy={115} r={32} fill="none" stroke="#22c55e" strokeWidth={3} opacity={0.9} />}
      </g>

      {/* SPIDER WEB - item */}
      <g>
        {[0,45,90,135].map((a,i) => (
          <line key={i} x1={220} y1={95}
            x2={220+Math.cos(a*Math.PI/180)*30} y2={95+Math.sin(a*Math.PI/180)*30}
            stroke="white" strokeWidth={1} opacity={0.7} />
        ))}
        {[0,45,90,135].map((a,i) => (
          <line key={i+4} x1={220} y1={95}
            x2={220+Math.cos((a+180)*Math.PI/180)*30} y2={95+Math.sin((a+180)*Math.PI/180)*30}
            stroke="white" strokeWidth={1} opacity={0.7} />
        ))}
        {[10,18,26].map((r,i) => (
          <circle key={i} cx={220} cy={95} r={r} fill="none" stroke="white" strokeWidth={1} opacity={0.5-i*0.1} />
        ))}
        <circle cx={220} cy={95} r={3} fill="#333" />
        {glowing === "spider_web" && <circle cx={220} cy={95} r={30} fill="url(#glowGradF)" />}
        {found.has("spider_web") && <circle cx={220} cy={95} r={30} fill="none" stroke="#22c55e" strokeWidth={3} opacity={0.9} />}
      </g>

      {/* BEEHIVE - item */}
      <g>
        <ellipse cx={165} cy={145} rx={22} ry={28} fill="#C8A400" />
        {/* Hive stripes */}
        {[-12,-4,4,12].map((y,i) => (
          <path key={i} d={`M${145} ${145+y} Q${165} ${140+y} ${185} ${145+y}`}
            fill="none" stroke="#8B7000" strokeWidth={2} opacity={0.5} />
        ))}
        {/* Entry hole */}
        <ellipse cx={165} cy={168} rx={8} ry={5} fill="#333" />
        {/* Bees */}
        {[{x:190,y:130},{x:200,y:145},{x:185,y:155}].map((b,i) => (
          <g key={i}>
            <ellipse cx={b.x} cy={b.y} rx={6} ry={4} fill="#FFD700" />
            <line x1={b.x-3} y1={b.y} x2={b.x+3} y2={b.y} stroke="#333" strokeWidth={1.5} />
            <ellipse cx={b.x-1} cy={b.y-3} rx={5} ry={2} fill="white" opacity={0.7} transform={`rotate(-30 ${b.x-1} ${b.y-3})`} />
          </g>
        ))}
        {glowing === "beehive" && <circle cx={165} cy={145} r={32} fill="url(#glowGradF)" />}
        {found.has("beehive") && <circle cx={165} cy={145} r={32} fill="none" stroke="#22c55e" strokeWidth={3} opacity={0.9} />}
      </g>

      {/* BUTTERFLY - item */}
      <g>
        {/* Wings */}
        <ellipse cx={263} cy={175} rx={22} ry={16} fill="#FF69B4" opacity={0.85} transform="rotate(-20 263 175)" />
        <ellipse cx={297} cy={175} rx={22} ry={16} fill="#FF69B4" opacity={0.85} transform="rotate(20 297 175)" />
        <ellipse cx={265} cy={188} rx={14} ry={10} fill="#FF1493" opacity={0.7} transform="rotate(20 265 188)" />
        <ellipse cx={295} cy={188} rx={14} ry={10} fill="#FF1493" opacity={0.7} transform="rotate(-20 295 188)" />
        {/* Spots */}
        <circle cx={268} cy={173} r={4} fill="#FFD700" opacity={0.8} />
        <circle cx={292} cy={173} r={4} fill="#FFD700" opacity={0.8} />
        {/* Body */}
        <ellipse cx={280} cy={181} rx={4} ry={14} fill="#333" />
        {/* Antennae */}
        <path d="M278 168 Q272 158 268 152" stroke="#333" strokeWidth={1.5} fill="none" />
        <path d="M282 168 Q288 158 292 152" stroke="#333" strokeWidth={1.5} fill="none" />
        <circle cx={268} cy={151} r={2.5} fill="#FF69B4" />
        <circle cx={292} cy={151} r={2.5} fill="#FF69B4" />
        {glowing === "butterfly" && <circle cx={280} cy={180} r={30} fill="url(#glowGradF)" />}
        {found.has("butterfly") && <circle cx={280} cy={180} r={30} fill="none" stroke="#22c55e" strokeWidth={3} opacity={0.9} />}
      </g>

      {/* HEDGEHOG - item */}
      <g>
        <ellipse cx={85} cy={245} rx={22} ry={16} fill="#8B6914" />
        {/* Spines */}
        {[[-15,-8],[-10,-14],[-4,-16],[2,-14],[8,-8]].map(([dx,dy],i) => (
          <line key={i} x1={85+(dx ?? 0)*0.7} y1={245+(dy ?? 0)*0.5}
            x2={85+(dx ?? 0)*1.5} y2={245+(dy ?? 0)*1.5}
            stroke="#5a4010" strokeWidth={2} strokeLinecap="round" />
        ))}
        {/* Face */}
        <ellipse cx={100} cy={248} rx={12} ry={10} fill="#C8A96E" />
        <ellipse cx={107} cy={246} rx={5} ry={4} fill="#333" />
        <circle cx={107} cy={244} r={2} fill="#111" />
        <circle cx={108} cy={243} r={1} fill="white" />
        {/* Tiny legs */}
        <ellipse cx={75} cy={258} rx={6} ry={4} fill="#8B6914" />
        <ellipse cx={88} cy={260} rx={6} ry={4} fill="#8B6914" />
        {glowing === "hedgehog" && <circle cx={85} cy={245} r={28} fill="url(#glowGradF)" />}
        {found.has("hedgehog") && <circle cx={85} cy={245} r={28} fill="none" stroke="#22c55e" strokeWidth={3} opacity={0.9} />}
      </g>

      {/* MUSHROOM - item */}
      <g>
        <rect x={120} y={318} width={20} height={30} rx={4} fill="#f5e6d3" />
        <ellipse cx={130} cy={320} rx={34} ry={22} fill="#CC0000" />
        <circle cx={122} cy={310} r={6} fill="white" />
        <circle cx={135} cy={307} r={5} fill="white" />
        <circle cx={145} cy={316} r={5} fill="white" />
        <circle cx={118} cy={318} r={4} fill="white" />
        {glowing === "mushroom" && <circle cx={130} cy={322} r={32} fill="url(#glowGradF)" />}
        {found.has("mushroom") && <circle cx={130} cy={322} r={32} fill="none" stroke="#22c55e" strokeWidth={3} opacity={0.9} />}
      </g>

      {/* FOX - item */}
      <g>
        <ellipse cx={380} cy={315} rx={30} ry={20} fill="#FF6B00" />
        {/* Head */}
        <ellipse cx={408} cy={300} rx={18} ry={15} fill="#FF6B00" />
        {/* Ears */}
        <polygon points="398,290 394,275 406,285" fill="#FF6B00" />
        <polygon points="418,290 422,275 410,285" fill="#FF6B00" />
        <polygon points="399,289 396,278 405,285" fill="#FFB6C1" />
        <polygon points="417,289 420,278 411,285" fill="#FFB6C1" />
        {/* Snout */}
        <ellipse cx={420} cy={304} rx={10} ry={7} fill="#f5c6a0" />
        <ellipse cx={423} cy={302} rx={5} ry={3} fill="#333" />
        {/* Eye */}
        <circle cx={412} cy={298} r={4} fill="#111" />
        <circle cx={413} cy={297} r={1.5} fill="white" />
        {/* Tail */}
        <path d="M350 310 Q330 290 340 270 Q355 255 365 275 Q370 295 380 315"
          fill="#FF6B00" stroke="#FF4500" strokeWidth={1} />
        <ellipse cx={340} cy={270} rx={12} ry={10} fill="white" />
        {/* White chest */}
        <ellipse cx={392} cy={318} rx={14} ry={10} fill="#f5f5f5" />
        {/* Legs */}
        <rect x={365} y={330} width={10} height={22} rx={4} fill="#FF5500" />
        <rect x={380} y={333} width={10} height={20} rx={4} fill="#FF5500" />
        <rect x={395} y={330} width={10} height={22} rx={4} fill="#FF5500" />
        {glowing === "fox" && <circle cx={385} cy={308} r={38} fill="url(#glowGradF)" />}
        {found.has("fox") && <circle cx={385} cy={308} r={38} fill="none" stroke="#22c55e" strokeWidth={3} opacity={0.9} />}
      </g>

      {/* FROG - item */}
      <g>
        <ellipse cx={75} cy={360} rx={20} ry={15} fill="#228B22" />
        {/* Eyes */}
        <circle cx={63} cy={348} r={8} fill="#228B22" />
        <circle cx={87} cy={348} r={8} fill="#228B22" />
        <circle cx={63} cy={348} r={5} fill="#111" />
        <circle cx={87} cy={348} r={5} fill="#111" />
        <circle cx={64} cy={347} r={2} fill="white" />
        <circle cx={88} cy={347} r={2} fill="white" />
        {/* Mouth */}
        <path d="M62 357 Q75 365 88 357" fill="none" stroke="#145214" strokeWidth={2} />
        {/* Belly */}
        <ellipse cx={75} cy={363} rx={12} ry={8} fill="#90EE90" />
        {/* Back legs */}
        <path d="M55 368 Q40 380 30 370 Q35 360 45 365" fill="#228B22" />
        <path d="M95 368 Q110 380 120 370 Q115 360 105 365" fill="#228B22" />
        {glowing === "frog" && <circle cx={75} cy={358} r={28} fill="url(#glowGradF)" />}
        {found.has("frog") && <circle cx={75} cy={358} r={28} fill="none" stroke="#22c55e" strokeWidth={3} opacity={0.9} />}
      </g>

      {/* DEER - item */}
      <g>
        <ellipse cx={490} cy={290} rx={24} ry={32} fill="#C8A96E" />
        {/* Head */}
        <ellipse cx={490} cy={258} rx={16} ry={18} fill="#C8A96E" />
        {/* Antlers */}
        <path d="M480 244 Q470 228 462 220 Q472 224 476 235" fill="none" stroke="#8B4513" strokeWidth={3} strokeLinecap="round" />
        <path d="M462 220 Q458 210 465 205" fill="none" stroke="#8B4513" strokeWidth={2} strokeLinecap="round" />
        <path d="M470 228 Q465 215 470 208" fill="none" stroke="#8B4513" strokeWidth={2} strokeLinecap="round" />
        <path d="M500 244 Q510 228 518 220 Q508 224 504 235" fill="none" stroke="#8B4513" strokeWidth={3} strokeLinecap="round" />
        <path d="M518 220 Q522 210 515 205" fill="none" stroke="#8B4513" strokeWidth={2} strokeLinecap="round" />
        <path d="M510 228 Q515 215 510 208" fill="none" stroke="#8B4513" strokeWidth={2} strokeLinecap="round" />
        {/* Eyes & nose */}
        <circle cx={484} cy={256} r={4} fill="#111" />
        <circle cx={485} cy={255} r={1.5} fill="white" />
        <ellipse cx={493} cy={264} rx={5} ry={4} fill="#a0826e" />
        <circle cx={493} cy={263} r={2} fill="#333" />
        {/* Ears */}
        <ellipse cx={476} cy={248} rx={8} ry={14} fill="#C8A96E" transform="rotate(-20 476 248)" />
        <ellipse cx={504} cy={248} rx={8} ry={14} fill="#C8A96E" transform="rotate(20 504 248)" />
        {/* Legs */}
        {[472,482,498,508].map((x,i) => (
          <rect key={i} x={x} y={318} width={8} height={40} rx={4} fill="#a08050" />
        ))}
        {/* White spot */}
        <circle cx={488} cy={280} r={5} fill="white" opacity={0.7} />
        <circle cx={496} cy={272} r={4} fill="white" opacity={0.6} />
        {glowing === "deer" && <circle cx={490} cy={282} r={40} fill="url(#glowGradF)" />}
        {found.has("deer") && <circle cx={490} cy={282} r={40} fill="none" stroke="#22c55e" strokeWidth={3} opacity={0.9} />}
      </g>

      {/* ACORN - item */}
      <g>
        <ellipse cx={340} cy={352} rx={12} ry={16} fill="#8B4513" />
        <ellipse cx={340} cy={340} rx={14} ry={8} fill="#5a3010" />
        <line x1={340} y1={332} x2={340} y2={325} stroke="#5a3010" strokeWidth={2} />
        {glowing === "acorn" && <circle cx={340} cy={350} r={25} fill="url(#glowGradF)" />}
        {found.has("acorn") && <circle cx={340} cy={350} r={25} fill="none" stroke="#22c55e" strokeWidth={3} opacity={0.9} />}
      </g>

      {/* Stars in sky */}
      {[30,90,180,270,400,520].map((x,i) => (
        <circle key={i} cx={x} cy={20+i%3*15} r={1.5} fill="white" opacity={0.6} />
      ))}
      {/* Fireflies */}
      {[200,320,440].map((x,i) => (
        <circle key={i} cx={x} cy={200+i*30} r={3} fill="#FFD700" opacity={0.6} />
      ))}
    </g>
  ),
};

const SCENES: Record<Age, SceneDef> = {
  kids:  oceanScene,
  tween: forestScene,
  teen:  forestScene,
  adult: forestScene,
};

const ITEM_COUNT: Record<Age, number> = {
  kids: 6,
  tween: 8,
  teen: 10,
  adult: 10,
};

export default function HiddenItems() {
  const [age, setAge] = useState<Age>("kids");
  const [phase, setPhase] = useState<Phase>("idle");
  const [found, setFound] = useState<Set<string>>(new Set());
  const [lives, setLives] = useState(3);
  const [score, setScore] = useState(0);
  const [elapsed, setElapsed] = useState(0);
  const [glowing, setGlowing] = useState<string | null>(null);
  const [wrongMsg, setWrongMsg] = useState(false);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  // livesRef keeps a synchronous copy of lives so rapid wrong-clicks consume the correct count
  const livesRef = useRef(3);

  useEffect(() => {
    const q = new URLSearchParams(window.location.search).get("age");
    if (q === "kids" || q === "tween" || q === "teen" || q === "adult") setAge(q as Age);
  }, []);

  const scene = SCENES[age];
  const itemCount = ITEM_COUNT[age];
  const activeItems = scene.items.slice(0, itemCount);

  const startGame = () => {
    setFound(new Set());
    livesRef.current = 3;
    setLives(3);
    setScore(0);
    setElapsed(0);
    setGlowing(null);
    setWrongMsg(false);
    setPhase("playing");
    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = setInterval(() => setElapsed((e) => e + 1), 1000);
  };

  useEffect(() => {
    if (phase === "done" && timerRef.current) clearInterval(timerRef.current);
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [phase]);

  function handleSVGClick(e: React.MouseEvent<SVGSVGElement>) {
    if (phase !== "playing") return;
    const svg = e.currentTarget;
    const rect = svg.getBoundingClientRect();
    const scaleX = 600 / rect.width;
    const scaleY = 400 / rect.height;
    const x = (e.clientX - rect.left) * scaleX;
    const y = (e.clientY - rect.top) * scaleY;

    for (const item of activeItems) {
      if (found.has(item.id)) continue;
      const d = Math.sqrt((x - item.cx) ** 2 + (y - item.cy) ** 2);
      if (d <= item.r) {
        const next = new Set(found);
        next.add(item.id);
        setFound(next);
        setScore((s) => s + 50);
        setGlowing(item.id);
        setTimeout(() => setGlowing(null), 800);
        if (next.size === activeItems.length) {
          setPhase("done");
          if (timerRef.current) clearInterval(timerRef.current);
        }
        return;
      }
    }
    // If the click landed on an item that exists in the scene but isn't active for
    // this difficulty level, ignore it silently — don't penalize the player.
    for (const item of scene.items) {
      if (activeItems.some((ai) => ai.id === item.id)) continue; // active item already checked above
      const d = Math.sqrt((x - item.cx) ** 2 + (y - item.cy) ** 2);
      if (d <= item.r) return; // inactive item: no reward, no penalty
    }

    // Wrong click — use livesRef to avoid stale closure under rapid clicking
    livesRef.current = Math.max(0, livesRef.current - 1);
    setLives(livesRef.current);
    setWrongMsg(true);
    setTimeout(() => setWrongMsg(false), 800);
    if (livesRef.current <= 0) {
      setPhase("done");
      if (timerRef.current) clearInterval(timerRef.current);
    }
  }

  const fmt = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

  return (
    <main className="container" style={{ maxWidth: 800, paddingBottom: 48 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap", marginBottom: 4 }}>
        <h1 style={{ margin: 0 }}>Find the Hidden Items</h1>
        <Link href="/arcade" style={{ marginLeft: "auto", color: "#94a3b8" }}>Back to Arcade</Link>
      </div>
      <p className="muted" style={{ marginBottom: 12 }}>
        Find all hidden items in the scene. Click directly on each item to reveal it!
      </p>

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 16 }}>
        {(["kids", "tween", "teen", "adult"] as Age[]).map((a) => (
          <button key={a} onClick={() => { setAge(a); setPhase("idle"); }}
            disabled={phase === "playing"}
            style={{ opacity: age === a ? 1 : 0.5 }}>
            {a === "kids" ? "Ocean (6 items)" : a === "tween" ? "Forest (8 items)" : a === "teen" ? "Forest (10 items)" : "Forest (10 items)"}
          </button>
        ))}
      </div>

      {phase !== "idle" && (
        <div style={{ display: "flex", gap: 20, alignItems: "center", marginBottom: 10, padding: "8px 16px", background: "#1e293b", borderRadius: 10, flexWrap: "wrap" }}>
          <span style={{ color: "#34d399", fontWeight: 700 }}>Score: {score}</span>
          <span style={{ color: "#94a3b8" }}>Time: {fmt(elapsed)}</span>
          <span style={{ color: "#fbbf24" }}>Found: {found.size}/{activeItems.length}</span>
          <span style={{ color: lives > 1 ? "#f87171" : "#ef4444", fontWeight: 700 }}>
            {"Lives: "}{"❤️".repeat(lives)}{"🖤".repeat(Math.max(0, 3 - lives))}
          </span>
          {wrongMsg && <span style={{ color: "#ef4444", fontWeight: 700 }}>{"Wrong!"}{lives <= 0 ? " Game Over!" : ""}</span>}
        </div>
      )}

      {phase === "idle" && (
        <div style={{ textAlign: "center", padding: 48 }}>
          <div style={{ fontSize: 56, marginBottom: 12 }}>
            {age === "kids" ? "🌊" : "🌲"}
          </div>
          <h2 style={{ marginBottom: 8 }}>
            {age === "kids" ? `Find ${itemCount} items in the Underwater Ocean!` : `Find ${itemCount} items in the Enchanted Forest!`}
          </h2>
          <p className="muted" style={{ marginBottom: 28 }}>
            Click on items in the scene. +50 pts per item, 3 wrong clicks allowed.
          </p>
          <button onClick={startGame} style={{ background: "#7c3aed", color: "#fff", padding: "14px 36px", fontSize: 20, fontWeight: 700, borderRadius: 12, border: "none", cursor: "pointer" }}>
            Start Searching
          </button>
        </div>
      )}

      {(phase === "playing" || phase === "done") && (
        <>
          <div style={{ position: "relative", marginBottom: 16 }}>
            <svg
              viewBox="0 0 600 400"
              style={{ width: "100%", cursor: phase === "playing" ? "crosshair" : "default", borderRadius: 12, display: "block", border: "2px solid #334155" }}
              onClick={handleSVGClick}
            >
              {scene.render(found, glowing)}
            </svg>
          </div>

          {/* Item checklist */}
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 16 }}>
            {activeItems.map((item) => (
              <span key={item.id} style={{
                padding: "6px 12px", borderRadius: 20, fontSize: 14, display: "flex", alignItems: "center", gap: 6,
                background: found.has(item.id) ? "#14532d" : "#1e293b",
                color: found.has(item.id) ? "#4ade80" : "#94a3b8",
                border: `1px solid ${found.has(item.id) ? "#22c55e" : "#334155"}`,
                transition: "all 0.3s",
              }}>
                <span>{item.emoji}</span>
                <span>{item.label}</span>
                {found.has(item.id) && <span style={{ color: "#22c55e" }}>{"✓"}</span>}
              </span>
            ))}
          </div>
        </>
      )}

      {phase === "done" && (
        <div className="card" style={{ textAlign: "center", padding: 36 }}>
          <div style={{ fontSize: 56, marginBottom: 12 }}>
            {found.size === activeItems.length ? "🎉" : "💪"}
          </div>
          <h2 style={{ color: found.size === activeItems.length ? "#34d399" : "#fbbf24" }}>
            {found.size === activeItems.length ? "All items found!" : `Found ${found.size} of ${activeItems.length} items`}
          </h2>
          <p className="muted">
            {"Score: "}<strong style={{ color: "#34d399", fontSize: 20 }}>{score}</strong>
            {" · Time: "}<strong>{fmt(elapsed)}</strong>
          </p>
          <button onClick={startGame} style={{ marginTop: 16, background: "#7c3aed", color: "#fff", padding: "12px 32px", fontSize: 18, fontWeight: 700, borderRadius: 10, border: "none", cursor: "pointer" }}>
            Play Again
          </button>
        </div>
      )}
    </main>
  );
}

"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import * as THREE from "three";

// ─────────────────────────────────────────────────────────────────────────────
// QUESTIONS
// ─────────────────────────────────────────────────────────────────────────────
const QUESTIONS = [
  { id:"m1", subject:"math",      emoji:"🧮", text:"What is 7 × 8?",                                    opts:["54","56","58","64"],             correct:1, xp:10 },
  { id:"m2", subject:"math",      emoji:"🧮", text:"What is √144?",                                     opts:["10","11","12","14"],             correct:2, xp:15 },
  { id:"m3", subject:"math",      emoji:"🧮", text:"What fraction equals 0.5?",                          opts:["1/3","1/4","1/2","2/3"],         correct:2, xp:10 },
  { id:"m4", subject:"math",      emoji:"🧮", text:"How many sides on a hexagon?",                       opts:["5","6","7","8"],                 correct:1, xp:10 },
  { id:"m5", subject:"math",      emoji:"🧮", text:"What is 15% of 200?",                               opts:["25","30","35","40"],             correct:1, xp:15 },
  { id:"m6", subject:"math",      emoji:"🧮", text:"What is 2³?",                                       opts:["6","8","12","16"],               correct:1, xp:15 },
  { id:"s1", subject:"science",   emoji:"🔬", text:"Which planet is closest to the Sun?",               opts:["Venus","Mars","Mercury","Earth"], correct:2, xp:10 },
  { id:"s2", subject:"science",   emoji:"🔬", text:"What gas do plants absorb?",                        opts:["Oxygen","CO₂","Nitrogen","H₂"],  correct:1, xp:10 },
  { id:"s3", subject:"science",   emoji:"🔬", text:"How many bones in an adult human?",                 opts:["186","206","226","246"],         correct:1, xp:20 },
  { id:"s4", subject:"science",   emoji:"🔬", text:"Chemical symbol for water?",                        opts:["H₂O","CO₂","NaCl","O₂"],        correct:0, xp:10 },
  { id:"s5", subject:"science",   emoji:"🔬", text:"Fastest land animal?",                              opts:["Lion","Horse","Cheetah","Eagle"], correct:2, xp:10 },
  { id:"s6", subject:"science",   emoji:"🔬", text:"Center of an atom?",                               opts:["Electron","Proton","Nucleus","Neutron"], correct:2, xp:15 },
  { id:"l1", subject:"language",  emoji:"📚", text:"Synonym for 'happy'?",                             opts:["Sad","Joyful","Angry","Tired"],   correct:1, xp:10 },
  { id:"l2", subject:"language",  emoji:"📚", text:"Plural of 'mouse'?",                               opts:["Mouses","Mice","Mouse","Mousen"], correct:1, xp:10 },
  { id:"l3", subject:"language",  emoji:"📚", text:"'The wind whispered' — what device is this?",      opts:["Simile","Metaphor","Personification","Alliteration"], correct:2, xp:20 },
  { id:"g1", subject:"geography", emoji:"🌍", text:"Capital of France?",                               opts:["London","Berlin","Paris","Madrid"], correct:2, xp:10 },
  { id:"g2", subject:"geography", emoji:"🌍", text:"Largest ocean?",                                   opts:["Atlantic","Indian","Arctic","Pacific"], correct:3, xp:10 },
  { id:"g3", subject:"geography", emoji:"🌍", text:"Which continent is Egypt on?",                     opts:["Asia","Europe","Africa","S. America"], correct:2, xp:10 },
  { id:"g4", subject:"geography", emoji:"🌍", text:"Longest river in the world?",                      opts:["Amazon","Nile","Yangtze","Mississippi"], correct:1, xp:15 },
  { id:"h1", subject:"history",   emoji:"🏛", text:"Year World War II ended?",                         opts:["1943","1944","1945","1946"],     correct:2, xp:15 },
  { id:"h2", subject:"history",   emoji:"🏛", text:"First person to walk on the Moon?",                opts:["Buzz Aldrin","Neil Armstrong","Yuri Gagarin","John Glenn"], correct:1, xp:15 },
  { id:"h3", subject:"history",   emoji:"🏛", text:"Where were the first Olympics held?",              opts:["Rome","Athens","Sparta","Olympia"], correct:3, xp:20 },
] as const;

type Question = typeof QUESTIONS[number];

// ─────────────────────────────────────────────────────────────────────────────
// TERRAIN
// ─────────────────────────────────────────────────────────────────────────────
const WORLD = 60;
const HALF  = WORLD / 2;

function noise(x: number, z: number): number {
  return (
    Math.sin(x * 0.31 + z * 0.21) * 2.5 +
    Math.cos(z * 0.17 - x * 0.13) * 2.0 +
    Math.sin((x + z) * 0.27)      * 1.2 +
    Math.cos((x - z) * 0.41)      * 0.8
  );
}

function getH(hmap: number[][], x: number, z: number): number {
  if (x < 0 || x >= WORLD || z < 0 || z >= WORLD) return 0;
  return hmap[x][z];
}

function buildHeightMap(): number[][] {
  const h: number[][] = [];
  for (let x = 0; x < WORLD; x++) {
    h[x] = [];
    for (let z = 0; z < WORLD; z++) {
      const raw = noise(x, z);
      // Drop edges to water
      const edgeDist = Math.min(x, z, WORLD - 1 - x, WORLD - 1 - z);
      const edge = Math.min(1, edgeDist / 6);
      h[x][z] = Math.max(1, Math.round((raw + 4) * edge));
    }
  }
  return h;
}

function blockColor(x: number, z: number, y: number, maxH: number, isTop: boolean): [number, number, number] {
  const dx = (x - HALF), dz = (z - HALF);
  const dist = Math.sqrt(dx * dx + dz * dz);

  if (maxH >= 7) {
    // Snow peaks
    return isTop ? [0.95, 0.97, 1.0] : [0.82, 0.84, 0.90];
  }
  if (maxH >= 5) {
    // Stone mountains
    return isTop ? [0.60, 0.62, 0.68] : [0.50, 0.52, 0.58];
  }
  if (dist > 23 && z > HALF) {
    // Desert (south)
    return isTop ? [0.94, 0.86, 0.56] : [0.78, 0.70, 0.45];
  }
  if (x < HALF - 18) {
    // Dark forest (west)
    return isTop ? [0.22, 0.48, 0.15] : [0.30, 0.22, 0.12];
  }
  // Grass / dirt
  const shade = 0.9 + (y / 10) * 0.1;
  return isTop
    ? [0.33 * shade, 0.68 * shade, 0.22 * shade]
    : [0.52 * shade, 0.34 * shade, 0.19 * shade];
}

function buildTerrainGeometry(hmap: number[][]): THREE.BufferGeometry {
  const pos: number[] = [], nor: number[] = [], col: number[] = [], idx: number[] = [];
  let vi = 0;

  const face = (
    p0: number[], p1: number[], p2: number[], p3: number[],
    nx: number, ny: number, nz: number,
    r: number, g: number, b: number,
  ) => {
    pos.push(...p0, ...p1, ...p2, ...p3);
    nor.push(nx, ny, nz,  nx, ny, nz,  nx, ny, nz,  nx, ny, nz);
    col.push(r, g, b,  r * 0.95, g * 0.95, b * 0.95,  r * 0.9, g * 0.9, b * 0.9,  r * 0.95, g * 0.95, b * 0.95);
    idx.push(vi, vi + 1, vi + 2,  vi, vi + 2, vi + 3);
    vi += 4;
  };

  for (let x = 0; x < WORLD; x++) {
    for (let z = 0; z < WORLD; z++) {
      const h = hmap[x][z];
      const bx = x - HALF, bz = z - HALF;
      const [tr, tg, tb] = blockColor(x, z, h, h, true);
      const [sr, sg, sb] = blockColor(x, z, h, h, false);

      // TOP
      face([bx,h,bz],[bx+1,h,bz],[bx+1,h,bz+1],[bx,h,bz+1], 0,1,0, tr,tg,tb);

      // SOUTH (+Z)
      const hs = getH(hmap, x, z + 1);
      for (let y = hs; y < h; y++)
        face([bx,y,bz+1],[bx+1,y,bz+1],[bx+1,y+1,bz+1],[bx,y+1,bz+1], 0,0,1, sr*0.85,sg*0.85,sb*0.85);

      // NORTH (-Z)
      const hn = getH(hmap, x, z - 1);
      for (let y = hn; y < h; y++)
        face([bx+1,y,bz],[bx,y,bz],[bx,y+1,bz],[bx+1,y+1,bz], 0,0,-1, sr*0.85,sg*0.85,sb*0.85);

      // EAST (+X)
      const he = getH(hmap, x + 1, z);
      for (let y = he; y < h; y++)
        face([bx+1,y,bz+1],[bx+1,y,bz],[bx+1,y+1,bz],[bx+1,y+1,bz+1], 1,0,0, sr*0.9,sg*0.9,sb*0.9);

      // WEST (-X)
      const hw = getH(hmap, x - 1, z);
      for (let y = hw; y < h; y++)
        face([bx,y,bz],[bx,y,bz+1],[bx,y+1,bz+1],[bx,y+1,bz], -1,0,0, sr*0.9,sg*0.9,sb*0.9);
    }
  }

  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
  geo.setAttribute("normal",   new THREE.Float32BufferAttribute(nor, 3));
  geo.setAttribute("color",    new THREE.Float32BufferAttribute(col, 3));
  geo.setIndex(idx);
  return geo;
}

// ─────────────────────────────────────────────────────────────────────────────
// QUESTION BLOCK POSITIONS
// ─────────────────────────────────────────────────────────────────────────────
const QBLOCK_POSITIONS: [number, number][] = [
  [5, 8], [12, -4], [-7, 7], [-13, -9], [18, 2], [-15, 11], [8, -14],
  [20, -7], [-4, 17], [13, 13], [-17, -4], [4, -18], [22, 14], [-19, 14],
  [-8, -18], [16, -16], [-22, -12], [9, 22], [-5, -5], [25, 5], [-25, -8], [0, -25],
];

// ─────────────────────────────────────────────────────────────────────────────
// THEODORE MESSAGES
// ─────────────────────────────────────────────────────────────────────────────
const THEO_TIPS = [
  "Find the glowing ✨ blocks and press E to answer questions!",
  "Correct answers earn you XP and gems! 💎",
  "Explore the whole world — each zone has different questions!",
  "Every mistake is just another chance to learn! 💪",
  "You're doing amazing — keep going! 🌟",
  "Try heading North for the snowy mountains! 🏔️",
  "The desert to the south has geography questions! 🌵",
  "Did you know? Answering 10 questions in a row is a streak! 🔥",
  "I'm Theodore, your AI guide. Ask me anything in class! 🤖",
];

// ─────────────────────────────────────────────────────────────────────────────
// COMPONENT
// ─────────────────────────────────────────────────────────────────────────────
export default function WorldGame() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const keysRef     = useRef<Record<string, boolean>>({});
  const frameRef    = useRef<number>(0);

  const [started,       setStarted]       = useState(false);
  const [xp,            setXp]            = useState(0);
  const [gems,          setGems]          = useState(0);
  const [zone,          setZone]          = useState("Starter Village");
  const [theoMsg,       setTheoMsg]       = useState(THEO_TIPS[0]);
  const [nearBlock,     setNearBlock]     = useState<string | null>(null);
  const [activeQ,       setActiveQ]       = useState<Question | null>(null);
  const [feedback,      setFeedback]      = useState<{ text: string; ok: boolean } | null>(null);
  const [answered,      setAnswered]      = useState<Set<string>>(() => new Set());
  const [showControls,  setShowControls]  = useState(true);
  const [streak,        setStreak]        = useState(0);

  const activeQRef  = useRef<Question | null>(null);
  const nearRef     = useRef<string | null>(null);
  const answeredRef = useRef<Set<string>>(new Set());
  activeQRef.current  = activeQ;
  nearRef.current     = nearBlock;
  answeredRef.current = answered;

  // Answer handler
  const handleAnswer = useCallback((idx: number) => {
    const q = activeQRef.current;
    if (!q) return;
    const correct = idx === q.correct;
    const newAnswered = new Set(answeredRef.current);
    newAnswered.add(q.id);
    setAnswered(newAnswered);
    setActiveQ(null);
    if (correct) {
      setXp(p => p + q.xp);
      setGems(p => p + Math.ceil(q.xp / 5));
      setStreak(p => p + 1);
      const msgs = ["🌟 Brilliant!", "⭐ Correct!", "🔥 Amazing!", "🏆 Perfect!"];
      setFeedback({ text: `${msgs[Math.floor(Math.random() * msgs.length)]} +${q.xp} XP`, ok: true });
      setTheoMsg(["You're a genius! 🌟", "Incredible answer! 🎉", "I knew you'd get it! ⭐", "Outstanding! 🏆"][Math.floor(Math.random() * 4)]);
    } else {
      setStreak(0);
      setFeedback({ text: `❌ Answer: ${q.opts[q.correct]}`, ok: false });
      setTheoMsg("Every mistake is a lesson! You'll get the next one! 💪");
    }
    setTimeout(() => setFeedback(null), 3000);
  }, []);

  // E key
  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      keysRef.current[e.code] = true;
      if (e.code === "KeyE" && nearRef.current && !activeQRef.current) {
        const q = QUESTIONS.find(q => q.id === nearRef.current && !answeredRef.current.has(q.id));
        if (q) setActiveQ(q);
      }
      if (e.code === "Escape") setActiveQ(null);
    };
    const up = (e: KeyboardEvent) => { keysRef.current[e.code] = false; };
    window.addEventListener("keydown", down);
    window.addEventListener("keyup", up);
    return () => { window.removeEventListener("keydown", down); window.removeEventListener("keyup", up); };
  }, []);

  // THREE.JS INIT
  useEffect(() => {
    if (!started || !canvasRef.current) return;
    const canvas = canvasRef.current;
    let alive = true;

    // ── Renderer ──────────────────────────────────────────────────────────
    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(canvas.clientWidth, canvas.clientHeight);
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.2;
    rendererRef.current = renderer;

    // ── Scene ─────────────────────────────────────────────────────────────
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x87ceeb);
    scene.fog = new THREE.FogExp2(0xa8d8ea, 0.013);

    // ── Sky gradient (simple skybox mesh) ─────────────────────────────────
    const skyGeo = new THREE.SphereGeometry(180, 16, 8);
    const skyMat = new THREE.ShaderMaterial({
      side: THREE.BackSide,
      vertexShader: `varying vec3 vPos; void main() { vPos = position; gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0); }`,
      fragmentShader: `varying vec3 vPos; void main() {
        float t = clamp((vPos.y + 50.0) / 120.0, 0.0, 1.0);
        vec3 sky = mix(vec3(0.53, 0.81, 0.98), vec3(0.18, 0.42, 0.78), t);
        gl_FragColor = vec4(sky, 1.0);
      }`,
    });
    scene.add(new THREE.Mesh(skyGeo, skyMat));

    // ── Lights ────────────────────────────────────────────────────────────
    const ambient = new THREE.AmbientLight(0xd4e8ff, 0.55);
    scene.add(ambient);

    const sun = new THREE.DirectionalLight(0xfff3d6, 1.4);
    sun.position.set(40, 70, 30);
    sun.castShadow = true;
    sun.shadow.mapSize.setScalar(1024);
    sun.shadow.camera.near = 0.5;
    sun.shadow.camera.far = 200;
    sun.shadow.camera.left = sun.shadow.camera.bottom = -60;
    sun.shadow.camera.right = sun.shadow.camera.top = 60;
    sun.shadow.bias = -0.001;
    scene.add(sun);

    const fill = new THREE.HemisphereLight(0x87ceeb, 0x3a6b2a, 0.4);
    scene.add(fill);

    // ── Camera ────────────────────────────────────────────────────────────
    const camera = new THREE.PerspectiveCamera(70, canvas.clientWidth / canvas.clientHeight, 0.1, 200);

    // ── Terrain ───────────────────────────────────────────────────────────
    const hmap = buildHeightMap();
    const tGeo = buildTerrainGeometry(hmap);
    const tMat = new THREE.MeshPhongMaterial({ vertexColors: true, shininess: 4 });
    const terrain = new THREE.Mesh(tGeo, tMat);
    terrain.receiveShadow = true;
    terrain.castShadow = false;
    scene.add(terrain);

    // ── Water ─────────────────────────────────────────────────────────────
    const waterGeo = new THREE.PlaneGeometry(WORLD + 4, WORLD + 4);
    waterGeo.rotateX(-Math.PI / 2);
    const waterMat = new THREE.MeshPhongMaterial({ color: 0x2a80d4, transparent: true, opacity: 0.72, shininess: 80, specular: 0x88bbff });
    const water = new THREE.Mesh(waterGeo, waterMat);
    water.position.y = 1.35;
    scene.add(water);

    // ── Trees ─────────────────────────────────────────────────────────────
    const trunkMat = new THREE.MeshPhongMaterial({ color: 0x5a3a1a });
    const leafMatA = new THREE.MeshPhongMaterial({ color: 0x2d7a18 });
    const leafMatB = new THREE.MeshPhongMaterial({ color: 0x1e6010 });
    for (let i = 0; i < 90; i++) {
      const tx = Math.round((Math.sin(i * 137.508) * 0.5 + 0.5) * (WORLD - 8)) - HALF + 4;
      const tz = Math.round((Math.cos(i * 137.508) * 0.5 + 0.5) * (WORLD - 8)) - HALF + 4;
      const th = hmap[Math.round(tx + HALF)]?.[Math.round(tz + HALF)] ?? 1;
      if (th < 3 || th > 5) continue;
      const trunk = new THREE.Mesh(new THREE.CylinderGeometry(0.28, 0.38, 3, 6), trunkMat);
      trunk.position.set(tx + 0.5, th + 0.5, tz + 0.5);
      trunk.castShadow = true;
      scene.add(trunk);
      const lm = i % 2 === 0 ? leafMatA : leafMatB;
      const leaves = new THREE.Mesh(new THREE.IcosahedronGeometry(1.8, 0), lm);
      leaves.position.set(tx + 0.5, th + 3, tz + 0.5);
      leaves.scale.y = 0.85;
      leaves.castShadow = true;
      scene.add(leaves);
    }

    // ── Player ────────────────────────────────────────────────────────────
    const playerGroup = new THREE.Group();
    const bodyMesh = new THREE.Mesh(
      new THREE.CapsuleGeometry(0.38, 0.75, 4, 8),
      new THREE.MeshPhongMaterial({ color: 0x3b82f6, shininess: 30 }),
    );
    bodyMesh.castShadow = true;
    playerGroup.add(bodyMesh);
    const headMesh = new THREE.Mesh(
      new THREE.SphereGeometry(0.32, 8, 6),
      new THREE.MeshPhongMaterial({ color: 0xfbbf88, shininess: 15 }),
    );
    headMesh.position.y = 0.88;
    headMesh.castShadow = true;
    playerGroup.add(headMesh);

    // Start at center
    const startH = hmap[HALF]?.[HALF] ?? 3;
    playerGroup.position.set(0, startH + 0.9, 0);
    scene.add(playerGroup);

    // ── Theodore NPC ──────────────────────────────────────────────────────
    const theoGroup = new THREE.Group();
    const theoCore = new THREE.Mesh(
      new THREE.SphereGeometry(0.55, 16, 12),
      new THREE.MeshPhongMaterial({ color: 0xfbbf24, emissive: 0x7a5500, shininess: 80, specular: 0xffdd44 }),
    );
    theoCore.castShadow = true;
    theoGroup.add(theoCore);
    // Orbiting ring
    const ring = new THREE.Mesh(
      new THREE.TorusGeometry(0.82, 0.06, 8, 32),
      new THREE.MeshPhongMaterial({ color: 0xfde68a, emissive: 0x7a6000, shininess: 60 }),
    );
    theoGroup.add(ring);
    theoGroup.position.set(3, startH + 2.5, 3);
    scene.add(theoGroup);

    // ── Question Blocks ───────────────────────────────────────────────────
    const qbMat = new THREE.MeshPhongMaterial({ color: 0xfbbf24, emissive: 0x4a3800, shininess: 60 });
    const qbMatDone = new THREE.MeshPhongMaterial({ color: 0x4ade80, emissive: 0x0a3010, shininess: 30 });
    const qbGeo = new THREE.BoxGeometry(0.95, 0.95, 0.95);

    const qblocks: { mesh: THREE.Mesh; id: string; baseY: number }[] = [];
    QBLOCK_POSITIONS.slice(0, QUESTIONS.length).forEach(([qx, qz], i) => {
      const ax = Math.max(-HALF + 2, Math.min(HALF - 2, qx));
      const az = Math.max(-HALF + 2, Math.min(HALF - 2, qz));
      const qh = hmap[Math.round(ax + HALF)]?.[Math.round(az + HALF)] ?? 2;
      const mesh = new THREE.Mesh(qbGeo, qbMat.clone());
      const by = qh + 1.6;
      mesh.position.set(ax, by, az);
      mesh.castShadow = true;
      scene.add(mesh);
      qblocks.push({ mesh, id: QUESTIONS[i].id, baseY: by });
    });

    // ── Camera state ──────────────────────────────────────────────────────
    let camYaw = 0, camPitch = 0.45, camDist = 9;
    let isDragging = false, lastMX = 0, lastMY = 0;
    const camTarget = new THREE.Vector3();

    const onMouseDown = (e: MouseEvent) => { isDragging = true; lastMX = e.clientX; lastMY = e.clientY; };
    const onMouseUp   = () => { isDragging = false; };
    const onMouseMove = (e: MouseEvent) => {
      if (!isDragging) return;
      camYaw   -= (e.clientX - lastMX) * 0.006;
      camPitch -= (e.clientY - lastMY) * 0.004;
      camPitch = Math.max(0.15, Math.min(1.2, camPitch));
      lastMX = e.clientX; lastMY = e.clientY;
    };
    const onWheel = (e: WheelEvent) => {
      camDist = Math.max(4, Math.min(18, camDist + e.deltaY * 0.02));
    };
    const onTouch1 = (e: TouchEvent) => { if (e.touches.length === 1) { isDragging = true; lastMX = e.touches[0].clientX; lastMY = e.touches[0].clientY; } };
    const onTouch2 = () => { isDragging = false; };
    const onTouchM = (e: TouchEvent) => {
      if (!isDragging || e.touches.length !== 1) return;
      camYaw   -= (e.touches[0].clientX - lastMX) * 0.008;
      camPitch -= (e.touches[0].clientY - lastMY) * 0.006;
      camPitch = Math.max(0.15, Math.min(1.2, camPitch));
      lastMX = e.touches[0].clientX; lastMY = e.touches[0].clientY;
    };
    canvas.addEventListener("mousedown",  onMouseDown);
    window.addEventListener("mouseup",    onMouseUp);
    window.addEventListener("mousemove",  onMouseMove);
    canvas.addEventListener("wheel",      onWheel, { passive: true });
    canvas.addEventListener("touchstart", onTouch1, { passive: true });
    window.addEventListener("touchend",   onTouch2);
    canvas.addEventListener("touchmove",  onTouchM, { passive: true });

    // ── Resize ────────────────────────────────────────────────────────────
    const onResize = () => {
      renderer.setSize(canvas.clientWidth, canvas.clientHeight);
      camera.aspect = canvas.clientWidth / canvas.clientHeight;
      camera.updateProjectionMatrix();
    };
    window.addEventListener("resize", onResize);

    // ── Particle bits for question blocks ─────────────────────────────────
    // (simple point sprites)

    // ── GAME LOOP ─────────────────────────────────────────────────────────
    let t = 0;
    let lastTheoFlip = 0;
    const theoTipIdx = { val: 0 };

    const playerVelY = { val: 0 };
    const playerDir  = new THREE.Vector3();
    const moveDir    = new THREE.Vector3();
    const camOffset  = new THREE.Vector3();

    const clock = new THREE.Clock();

    const loop = () => {
      if (!alive) return;
      frameRef.current = requestAnimationFrame(loop);

      const dt = Math.min(clock.getDelta(), 0.05);
      t += dt;

      // ── Player movement ──────────────────────────────────────────────
      const speed = 5.5;
      const camFwd = new THREE.Vector3(-Math.sin(camYaw), 0, -Math.cos(camYaw));
      const camRight = new THREE.Vector3(Math.cos(camYaw), 0, -Math.sin(camYaw));

      moveDir.set(0, 0, 0);
      if (keysRef.current["KeyW"] || keysRef.current["ArrowUp"])    moveDir.addScaledVector(camFwd, 1);
      if (keysRef.current["KeyS"] || keysRef.current["ArrowDown"])  moveDir.addScaledVector(camFwd, -1);
      if (keysRef.current["KeyA"] || keysRef.current["ArrowLeft"])  moveDir.addScaledVector(camRight, -1);
      if (keysRef.current["KeyD"] || keysRef.current["ArrowRight"]) moveDir.addScaledVector(camRight, 1);

      if (moveDir.lengthSq() > 0) {
        moveDir.normalize();
        playerGroup.position.addScaledVector(moveDir, speed * dt);
        // Face movement direction
        playerDir.copy(moveDir);
        const angle = Math.atan2(playerDir.x, playerDir.z);
        playerGroup.rotation.y = angle;
      }

      // Jump
      if ((keysRef.current["Space"] || keysRef.current["KeyJ"]) && Math.abs(playerVelY.val) < 0.05) {
        playerVelY.val = 5.5;
      }

      // Gravity
      playerVelY.val -= 18 * dt;
      playerGroup.position.y += playerVelY.val * dt;

      // Ground clamp
      const px = Math.round(playerGroup.position.x + HALF);
      const pz = Math.round(playerGroup.position.z + HALF);
      const cx = Math.max(0, Math.min(WORLD - 1, px));
      const cz = Math.max(0, Math.min(WORLD - 1, pz));
      const floorY = (hmap[cx]?.[cz] ?? 1) + 0.9;
      if (playerGroup.position.y < floorY) {
        playerGroup.position.y = floorY;
        playerVelY.val = 0;
      }

      // World bounds
      playerGroup.position.x = Math.max(-HALF + 1, Math.min(HALF - 1, playerGroup.position.x));
      playerGroup.position.z = Math.max(-HALF + 1, Math.min(HALF - 1, playerGroup.position.z));

      // ── Camera follow ────────────────────────────────────────────────
      camTarget.lerp(playerGroup.position, 0.12);
      camOffset.set(
        Math.sin(camYaw) * Math.cos(camPitch) * camDist,
        Math.sin(camPitch) * camDist,
        Math.cos(camYaw) * Math.cos(camPitch) * camDist,
      );
      camera.position.copy(camTarget).add(camOffset);
      camera.lookAt(camTarget.x, camTarget.y + 0.6, camTarget.z);

      // ── Theodore follow ──────────────────────────────────────────────
      const toPlayer = playerGroup.position.clone().sub(theoGroup.position);
      toPlayer.y = 0;
      const dist = toPlayer.length();
      if (dist > 4.5) {
        theoGroup.position.addScaledVector(toPlayer.normalize(), Math.min(dist - 4, 3.5) * dt);
      }
      const theoHx = Math.max(0, Math.min(WORLD - 1, Math.round(theoGroup.position.x + HALF)));
      const theoHz = Math.max(0, Math.min(WORLD - 1, Math.round(theoGroup.position.z + HALF)));
      const theoFloor = (hmap[theoHx]?.[theoHz] ?? 1) + 2.2;
      theoGroup.position.y = theoFloor + Math.sin(t * 1.8) * 0.18;
      // Face player
      const faceAngle = Math.atan2(
        playerGroup.position.x - theoGroup.position.x,
        playerGroup.position.z - theoGroup.position.z,
      );
      theoGroup.rotation.y = faceAngle;
      ring.rotation.x = t * 1.2;
      ring.rotation.z = t * 0.8;

      // ── Question blocks ──────────────────────────────────────────────
      let nearestId: string | null = null;
      let nearestDist = 3.8;

      qblocks.forEach(({ mesh, id, baseY }, i) => {
        const done = answeredRef.current.has(id);
        mesh.rotation.y = t * 0.7 + i * 0.4;
        mesh.rotation.x = Math.sin(t * 0.4 + i) * 0.12;
        mesh.position.y = baseY + Math.sin(t * 1.3 + i * 0.8) * 0.22;

        if (done) {
          if ((mesh.material as THREE.MeshPhongMaterial).color.getHex() !== 0x4ade80) {
            mesh.material = qbMatDone;
            mesh.scale.setScalar(1.0);
          }
        } else {
          const d = playerGroup.position.distanceTo(mesh.position);
          if (d < nearestDist) { nearestDist = d; nearestId = id; }
          // Pulse scale
          const pulse = 1 + Math.sin(t * 3 + i) * 0.06;
          mesh.scale.setScalar(pulse);
        }
      });

      if (nearestId !== nearRef.current) setNearBlock(nearestId);

      // ── Zone detection ───────────────────────────────────────────────
      const pp = playerGroup.position;
      let z = "Starter Village";
      if (pp.z < -16) z = pp.x > 10 ? "Stone Mountains" : "Snow Peaks";
      else if (pp.z > 16) z = "Desert Dunes";
      else if (pp.x < -16) z = "Dark Forest";
      else if (pp.x > 16) z = "Eastern Plains";
      setZone(z);

      // ── Theodore tip cycle ───────────────────────────────────────────
      if (t - lastTheoFlip > 18) {
        lastTheoFlip = t;
        theoTipIdx.val = (theoTipIdx.val + 1) % THEO_TIPS.length;
        setTheoMsg(THEO_TIPS[theoTipIdx.val]);
      }

      // ── Water shimmer ────────────────────────────────────────────────
      (water.material as THREE.MeshPhongMaterial).opacity = 0.68 + Math.sin(t * 0.7) * 0.04;

      renderer.render(scene, camera);
    };

    loop();

    return () => {
      alive = false;
      cancelAnimationFrame(frameRef.current);
      renderer.dispose();
      canvas.removeEventListener("mousedown",  onMouseDown);
      window.removeEventListener("mouseup",    onMouseUp);
      window.removeEventListener("mousemove",  onMouseMove);
      canvas.removeEventListener("wheel",      onWheel);
      canvas.removeEventListener("touchstart", onTouch1);
      window.removeEventListener("touchend",   onTouch2);
      canvas.removeEventListener("touchmove",  onTouchM);
      window.removeEventListener("resize",     onResize);
    };
  }, [started]);

  // ─────────────────────────────────────────────────────────────────────────
  // RENDER
  // ─────────────────────────────────────────────────────────────────────────
  const SUBJECT_COLORS: Record<string, string> = {
    math: "#6366f1", science: "#10b981", language: "#f59e0b",
    geography: "#0ea5e9", history: "#ec4899",
  };

  return (
    <div style={{ position: "fixed", inset: 0, background: "#000", overflow: "hidden" }}>
      <canvas
        ref={canvasRef}
        style={{ display: "block", width: "100%", height: "100%", touchAction: "none", cursor: isDragCursor(started) ? "grab" : "default" }}
      />

      {/* ── START SCREEN ───────────────────────────────────────────────── */}
      {!started && (
        <div style={{
          position:"absolute", inset:0, display:"flex", flexDirection:"column",
          alignItems:"center", justifyContent:"center",
          background:"linear-gradient(135deg,rgba(5,7,20,.97) 0%,rgba(20,8,50,.97) 100%)",
        }}>
          <div style={{ fontSize:72, marginBottom:4, filter:"drop-shadow(0 0 24px #6366f1)" }}>🌍</div>
          <h1 style={{ color:"#fff", fontSize:46, fontWeight:900, margin:"0 0 6px", letterSpacing:-1 }}>
            Salareen Worlds
          </h1>
          <p style={{ color:"#a5b4fc", fontSize:17, margin:"0 0 28px", textAlign:"center", maxWidth:400, lineHeight:1.5 }}>
            Explore a living 3D world with Theodore, your AI guide.<br/>
            Find glowing blocks, answer questions, earn XP! 🌟
          </p>
          {/* Subjects */}
          <div style={{ display:"flex", gap:12, marginBottom:28 }}>
            {(["🧮 Math","🔬 Science","📚 Language","🌍 Geography","🏛 History"] as const).map(s => (
              <span key={s} style={{
                background:"rgba(255,255,255,0.07)", borderRadius:20, padding:"5px 12px",
                color:"#cbd5e1", fontSize:13, fontWeight:600,
                border:"1px solid rgba(255,255,255,0.12)",
              }}>{s}</span>
            ))}
          </div>
          {/* Controls */}
          <div style={{
            display:"grid", gridTemplateColumns:"1fr 1fr", gap:"6px 24px",
            marginBottom:28, fontSize:13, color:"#64748b",
          }}>
            <span>⬆⬇⬅➡ / WASD — Move</span>
            <span>🖱 Drag — Rotate camera</span>
            <span>Space — Jump</span>
            <span>E — Answer question</span>
          </div>
          <button
            onClick={() => setStarted(true)}
            style={{
              background:"linear-gradient(135deg,#6366f1,#8b5cf6)",
              color:"#fff", border:"none", borderRadius:16,
              padding:"16px 52px", fontSize:20, fontWeight:900,
              cursor:"pointer", boxShadow:"0 8px 32px rgba(99,102,241,0.5)",
              letterSpacing:0.5,
            }}
          >
            🚀  Start Adventure
          </button>
          <p style={{ color:"#334155", fontSize:12, marginTop:16 }}>
            {QUESTIONS.length} questions · 5 subjects · Infinite exploration
          </p>
        </div>
      )}

      {/* ── IN-GAME HUD ────────────────────────────────────────────────── */}
      {started && (
        <>
          {/* Stats — top left */}
          <div style={{ position:"absolute", top:14, left:14, display:"flex", flexDirection:"column", gap:7 }}>
            <div style={hud()}>
              <div style={{ fontSize:19, fontWeight:800, color:"#fff" }}>⭐ {xp} XP</div>
              <div style={{ fontSize:14, color:"#fbbf24" }}>💎 {gems} gems</div>
              {streak >= 3 && <div style={{ fontSize:12, color:"#f97316" }}>🔥 {streak} streak!</div>}
            </div>
            <div style={hudSm()}>📍 {zone}</div>
            <div style={hudSm()}>✅ {answered.size}/{QUESTIONS.length}</div>
          </div>

          {/* Exit — top right */}
          <a href="/" style={{
            position:"absolute", top:14, right:14,
            ...hudSm() as object, textDecoration:"none", display:"block",
          }}>
            ← Exit
          </a>

          {/* Near-block prompt */}
          {nearBlock && !activeQ && (
            <div style={{
              position:"absolute", bottom:190, left:"50%", transform:"translateX(-50%)",
              background:"rgba(0,0,0,0.82)", backdropFilter:"blur(8px)",
              borderRadius:12, padding:"10px 24px",
              border:"1.5px solid rgba(251,191,36,0.55)",
              color:"#fbbf24", fontSize:16, fontWeight:700,
            }}>
              Press <kbd style={{ background:"#fbbf24", color:"#000", borderRadius:4, padding:"1px 7px", fontWeight:900 }}>E</kbd> to learn ✨
            </div>
          )}

          {/* Theodore */}
          <div style={{
            position:"absolute", bottom:90, left:"50%", transform:"translateX(-50%)",
            display:"flex", alignItems:"center", gap:12,
            background:"rgba(10,7,30,0.88)", backdropFilter:"blur(10px)",
            borderRadius:18, padding:"10px 18px",
            border:"1px solid rgba(251,191,36,0.3)",
            maxWidth:"min(580px,92vw)",
          }}>
            <span style={{ fontSize:30, flexShrink:0, filter:"drop-shadow(0 0 6px #fbbf24)" }}>🟡</span>
            <div>
              <div style={{ color:"#fbbf24", fontSize:10, fontWeight:900, letterSpacing:1.5, marginBottom:2 }}>THEODORE · AI GUIDE</div>
              <div style={{ color:"#e2e8f0", fontSize:14, lineHeight:1.4 }}>{theoMsg}</div>
            </div>
          </div>

          {/* Feedback toast */}
          {feedback && (
            <div style={{
              position:"absolute", top:"42%", left:"50%", transform:"translate(-50%,-50%)",
              background: feedback.ok ? "rgba(16,185,129,0.97)" : "rgba(239,68,68,0.97)",
              color:"#fff", borderRadius:18, padding:"16px 36px",
              fontSize:22, fontWeight:900, textAlign:"center",
              boxShadow:"0 10px 40px rgba(0,0,0,0.4)", zIndex:60,
              whiteSpace:"nowrap",
            }}>
              {feedback.text}
            </div>
          )}

          {/* Controls hint */}
          {showControls && (
            <div style={{
              position:"absolute", bottom:14, right:14,
              ...hudSm() as object, lineHeight:1.8, fontSize:11,
            }}>
              <div style={{ fontWeight:700, color:"#94a3b8", marginBottom:2 }}>Controls</div>
              <div>WASD / Arrows — move</div>
              <div>Drag — rotate camera</div>
              <div>Scroll — zoom</div>
              <div>Space — jump &nbsp; E — interact</div>
              <button onClick={() => setShowControls(false)} style={{ marginTop:6, background:"none", border:"none", color:"#475569", cursor:"pointer", fontSize:10, padding:0 }}>dismiss ✕</button>
            </div>
          )}
        </>
      )}

      {/* ── QUESTION MODAL ──────────────────────────────────────────────── */}
      {activeQ && (
        <div style={{
          position:"absolute", inset:0, display:"flex", alignItems:"center", justifyContent:"center",
          background:"rgba(0,0,0,0.78)", backdropFilter:"blur(6px)", zIndex:50,
        }}>
          <div style={{
            background:"linear-gradient(135deg,#0d1117,#1a1040)",
            borderRadius:22, padding:30, width:"min(500px,92vw)",
            border:`2px solid ${SUBJECT_COLORS[activeQ.subject]}55`,
            boxShadow:`0 24px 64px rgba(0,0,0,0.7), 0 0 0 1px ${SUBJECT_COLORS[activeQ.subject]}22`,
          }}>
            {/* Header */}
            <div style={{ display:"flex", alignItems:"center", gap:12, marginBottom:18 }}>
              <div style={{
                width:46, height:46, borderRadius:14, display:"flex", alignItems:"center", justifyContent:"center",
                background:`${SUBJECT_COLORS[activeQ.subject]}22`,
                fontSize:24, border:`1px solid ${SUBJECT_COLORS[activeQ.subject]}44`,
              }}>
                {activeQ.emoji}
              </div>
              <div>
                <div style={{ color:"#94a3b8", fontSize:11, fontWeight:900, textTransform:"uppercase", letterSpacing:1.5 }}>
                  {activeQ.subject} · +{activeQ.xp} XP
                </div>
                <div style={{ color:SUBJECT_COLORS[activeQ.subject], fontSize:12, fontWeight:700 }}>
                  Question {QUESTIONS.findIndex(q => q.id === activeQ.id) + 1} of {QUESTIONS.length}
                </div>
              </div>
            </div>

            {/* Question */}
            <div style={{ color:"#f1f5f9", fontSize:21, fontWeight:800, marginBottom:22, lineHeight:1.4 }}>
              {activeQ.text}
            </div>

            {/* Options */}
            <div style={{ display:"grid", gap:10 }}>
              {activeQ.opts.map((opt, i) => (
                <button
                  key={i}
                  onClick={() => handleAnswer(i)}
                  style={{
                    background:"rgba(255,255,255,0.05)",
                    border:"1px solid rgba(255,255,255,0.12)",
                    borderRadius:13, padding:"13px 18px",
                    color:"#e2e8f0", fontSize:16, fontWeight:600,
                    textAlign:"left", cursor:"pointer",
                    display:"flex", alignItems:"center", gap:12,
                    transition:"all 0.12s",
                  }}
                  onMouseEnter={e => {
                    (e.currentTarget as HTMLElement).style.background = `${SUBJECT_COLORS[activeQ.subject]}28`;
                    (e.currentTarget as HTMLElement).style.borderColor = SUBJECT_COLORS[activeQ.subject];
                  }}
                  onMouseLeave={e => {
                    (e.currentTarget as HTMLElement).style.background = "rgba(255,255,255,0.05)";
                    (e.currentTarget as HTMLElement).style.borderColor = "rgba(255,255,255,0.12)";
                  }}
                >
                  <span style={{
                    width:30, height:30, borderRadius:8, display:"flex", alignItems:"center", justifyContent:"center",
                    background:"rgba(255,255,255,0.1)", fontSize:13, fontWeight:900, flexShrink:0, color:"#94a3b8",
                  }}>
                    {["A","B","C","D"][i]}
                  </span>
                  {opt}
                </button>
              ))}
            </div>

            <button
              onClick={() => setActiveQ(null)}
              style={{ marginTop:16, background:"none", border:"none", color:"#475569", cursor:"pointer", fontSize:13 }}
            >
              skip for now
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// STYLE HELPERS
// ─────────────────────────────────────────────────────────────────────────────
function hud() {
  return {
    background:"rgba(0,0,0,0.65)", backdropFilter:"blur(10px)",
    borderRadius:12, padding:"10px 16px",
    border:"1px solid rgba(255,255,255,0.1)",
    minWidth:148,
  };
}

function hudSm() {
  return {
    background:"rgba(0,0,0,0.55)", backdropFilter:"blur(8px)",
    borderRadius:10, padding:"6px 14px",
    border:"1px solid rgba(255,255,255,0.08)",
    color:"#64748b", fontSize:13, fontWeight:600,
  };
}

function isDragCursor(started: boolean) { return started; }

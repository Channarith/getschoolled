// @ts-nocheck
"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import * as THREE from "three";
import GameHUD from "./components/HUD";
import {
  generateHeightMap,
  buildTerrainGeometry,
  getTerrainHeight,
} from "./game/terrain";
import { EnemyManager } from "./game/enemies";
import { NPCManager } from "./game/npcs";
import { MountManager } from "./game/mounts";
import { VehicleManager } from "./game/vehicles";
import { CraftingSystem } from "./game/crafting";
import { BuildingSystem } from "./game/building";
import { PlanetSystem } from "./game/planets";
import { CombatSystem } from "./game/combat";
import type { Planet, Quest, ItemType, WeaponType, CraftingRecipe } from "./game/types";
import {
  WORLD_SIZE,
  HALF,
  QUESTION_POSITIONS,
  THEO_TIPS,
  GRAVITY_EARTH,
  GRAVITY_SPACE,
} from "./game/constants";

// ─────────────────────────────────────────────────────────────────────────────
// QUESTIONS (22 inline)
// ─────────────────────────────────────────────────────────────────────────────
const QUESTIONS = [
  { id: "m1", subject: "math",      emoji: "🧮", text: "What is 7 × 8?",                               opts: ["54","56","58","64"],             correct: 1, xp: 10 },
  { id: "m2", subject: "math",      emoji: "🧮", text: "What is √144?",                                opts: ["10","11","12","14"],             correct: 2, xp: 15 },
  { id: "m3", subject: "math",      emoji: "🧮", text: "What fraction equals 0.5?",                    opts: ["1/3","1/4","1/2","2/3"],         correct: 2, xp: 10 },
  { id: "m4", subject: "math",      emoji: "🧮", text: "How many sides on a hexagon?",                 opts: ["5","6","7","8"],                 correct: 1, xp: 10 },
  { id: "m5", subject: "math",      emoji: "🧮", text: "What is 15% of 200?",                         opts: ["25","30","35","40"],             correct: 1, xp: 15 },
  { id: "m6", subject: "math",      emoji: "🧮", text: "What is 2³?",                                 opts: ["6","8","12","16"],               correct: 1, xp: 15 },
  { id: "s1", subject: "science",   emoji: "🔬", text: "Which planet is closest to the Sun?",         opts: ["Venus","Mars","Mercury","Earth"], correct: 2, xp: 10 },
  { id: "s2", subject: "science",   emoji: "🔬", text: "What gas do plants absorb?",                  opts: ["Oxygen","CO₂","Nitrogen","H₂"],  correct: 1, xp: 10 },
  { id: "s3", subject: "science",   emoji: "🔬", text: "How many bones in an adult human?",           opts: ["186","206","226","246"],         correct: 1, xp: 20 },
  { id: "s4", subject: "science",   emoji: "🔬", text: "Chemical symbol for water?",                  opts: ["H₂O","CO₂","NaCl","O₂"],        correct: 0, xp: 10 },
  { id: "s5", subject: "science",   emoji: "🔬", text: "Fastest land animal?",                        opts: ["Lion","Horse","Cheetah","Eagle"], correct: 2, xp: 10 },
  { id: "s6", subject: "science",   emoji: "🔬", text: "Center of an atom?",                         opts: ["Electron","Proton","Nucleus","Neutron"], correct: 2, xp: 15 },
  { id: "l1", subject: "language",  emoji: "📚", text: "Synonym for 'happy'?",                       opts: ["Sad","Joyful","Angry","Tired"],   correct: 1, xp: 10 },
  { id: "l2", subject: "language",  emoji: "📚", text: "Plural of 'mouse'?",                         opts: ["Mouses","Mice","Mouse","Mousen"], correct: 1, xp: 10 },
  { id: "l3", subject: "language",  emoji: "📚", text: "'The wind whispered' — what device is this?", opts: ["Simile","Metaphor","Personification","Alliteration"], correct: 2, xp: 20 },
  { id: "g1", subject: "geography", emoji: "🌍", text: "Capital of France?",                         opts: ["London","Berlin","Paris","Madrid"], correct: 2, xp: 10 },
  { id: "g2", subject: "geography", emoji: "🌍", text: "Largest ocean?",                             opts: ["Atlantic","Indian","Arctic","Pacific"], correct: 3, xp: 10 },
  { id: "g3", subject: "geography", emoji: "🌍", text: "Which continent is Egypt on?",               opts: ["Asia","Europe","Africa","S. America"], correct: 2, xp: 10 },
  { id: "g4", subject: "geography", emoji: "🌍", text: "Longest river in the world?",                opts: ["Amazon","Nile","Yangtze","Mississippi"], correct: 1, xp: 15 },
  { id: "h1", subject: "history",   emoji: "🏛", text: "Year World War II ended?",                   opts: ["1943","1944","1945","1946"],     correct: 2, xp: 15 },
  { id: "h2", subject: "history",   emoji: "🏛", text: "First person to walk on the Moon?",          opts: ["Buzz Aldrin","Neil Armstrong","Yuri Gagarin","John Glenn"], correct: 1, xp: 15 },
  { id: "h3", subject: "history",   emoji: "🏛", text: "Where were the first Olympics held?",        opts: ["Rome","Athens","Sparta","Olympia"], correct: 3, xp: 20 },
] as const;

type Question = (typeof QUESTIONS)[number];

// ─────────────────────────────────────────────────────────────────────────────
// INITIAL STATE FACTORIES
// ─────────────────────────────────────────────────────────────────────────────

function makeInitialInventory(): Partial<Record<ItemType, number>> {
  return {
    wood: 0, stone: 0, herb: 0, crystal: 0,
    starmetal: 0, star_crystal: 0, health_potion: 1,
    portal_key: 0, sword: 0, staff: 0, bow: 0,
    plank: 0, stone_block: 0, crystal_block: 0,
  };
}

function makeInitialQuests(): Quest[] {
  return [
    {
      id: "q_explorer",
      title: "Explorer",
      description: "Answer your first 5 questions",
      objective: "Answer 5 questions",
      progress: 0, target: 0, current: 0,
      goal: 5,
      reward: { xp: 50, gems: 10 },
      completed: false,
    },
    {
      id: "q_gatherer",
      title: "Resource Gatherer",
      description: "Collect 10 resources",
      objective: "Collect 10 resources",
      progress: 0, target: 0, current: 0,
      goal: 10,
      reward: { xp: 40, gems: 8, item: "health_potion" as ItemType },
      completed: false,
    },
    {
      id: "q_crystal_hunter",
      title: "Crystal Hunter",
      description: "Find 3 star crystals",
      objective: "Find 3 star crystals",
      progress: 0, target: 0, current: 0,
      goal: 3,
      reward: { xp: 100, gems: 25, item: "portal_key" as ItemType },
      completed: false,
    },
  ];
}

// ─────────────────────────────────────────────────────────────────────────────
// SUBJECT COLORS
// ─────────────────────────────────────────────────────────────────────────────

const SUBJECT_COLORS: Record<string, string> = {
  math: "#6366f1",
  science: "#10b981",
  language: "#f59e0b",
  geography: "#0ea5e9",
  history: "#ec4899",
};

// ─────────────────────────────────────────────────────────────────────────────
// COMPONENT
// ─────────────────────────────────────────────────────────────────────────────

export default function WorldGame() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const keysRef = useRef<Record<string, boolean>>({});
  const frameRef = useRef<number>(0);
  const mouseRef = useRef<{ buttons: number }>({ buttons: 0 });

  // ── React State ─────────────────────────────────────────────
  const [gameStarted, setGameStarted] = useState(false);

  // Player stats
  const [hp, setHp] = useState(100);
  const [xp, setXp] = useState(0);
  const [gems, setGems] = useState(0);
  const [streak, setStreak] = useState(0);

  // World
  const [planet, setPlanet] = useState<Planet>("earth");
  const [zone, setZone] = useState("Starter Village");
  const [questLog, setQuestLog] = useState<Quest[]>(makeInitialQuests);
  const [inventory, setInventory] = useState<Partial<Record<ItemType, number>>>(makeInitialInventory);
  const [activeWeapon, setActiveWeapon] = useState<WeaponType>("fists");

  // UI panels
  const [craftingOpen, setCraftingOpen] = useState(false);
  const [inventoryOpen, setInventoryOpen] = useState(false);
  const [buildingMode, setBuildingMode] = useState(false);
  const [availableRecipes, setAvailableRecipes] = useState<CraftingRecipe[]>([]);
  const [nearPrompt, setNearPrompt] = useState<string | null>(null);
  const [theoMessage, setTheoMessage] = useState(THEO_TIPS[0]);

  // Dialogue
  const [dialogueLines, setDialogueLines] = useState<string[] | null>(null);
  const [dialogueNpcName, setDialogueNpcName] = useState<string | null>(null);

  // Question
  const [activeQ, setActiveQ] = useState<Question | null>(null);
  const [feedback, setFeedback] = useState<{ text: string; ok: boolean } | null>(null);
  const [answered, setAnswered] = useState<Set<string>>(() => new Set());

  // Planet switch overlay
  const [switchingPlanet, setSwitchingPlanet] = useState(false);

  // ── Refs to avoid stale closures ────────────────────────────
  const activeQRef = useRef<Question | null>(null);
  const answeredRef = useRef<Set<string>>(new Set());
  const nearPromptRef = useRef<string | null>(null);
  const inventoryRef = useRef<Partial<Record<ItemType, number>>>(makeInitialInventory());
  const activeWeaponRef = useRef<WeaponType>("fists");
  const craftingSystemRef = useRef<CraftingSystem | null>(null);
  const buildingSystemRef = useRef<BuildingSystem | null>(null);

  activeQRef.current = activeQ;
  answeredRef.current = answered;
  nearPromptRef.current = nearPrompt;
  inventoryRef.current = inventory;
  activeWeaponRef.current = activeWeapon;

  // ─────────────────────────────────────────────────────────────
  // ANSWER HANDLER
  // ─────────────────────────────────────────────────────────────
  const handleAnswer = useCallback((idx: number) => {
    const q = activeQRef.current;
    if (!q) return;
    const correct = idx === q.correct;
    const newAnswered = new Set(answeredRef.current);
    newAnswered.add(q.id);
    setAnswered(newAnswered);
    setActiveQ(null);
    activeQRef.current = null;

    if (correct) {
      setXp(p => p + q.xp);
      setGems(p => p + Math.ceil(q.xp / 5));
      setStreak(p => p + 1);
      const msgs = ["Brilliant! +", "Correct! +", "Amazing! +", "Perfect! +"];
      const chosen = msgs[Math.floor(Math.random() * msgs.length)];
      setFeedback({ text: `${chosen}${q.xp} XP`, ok: true });
      setTheoMessage(["You're a genius!", "Incredible answer!", "I knew you'd get it!", "Outstanding!"][Math.floor(Math.random() * 4)]);

      // Quest progress: Explorer
      setQuestLog(ql => ql.map(quest => {
        if (quest.id === "q_explorer" && !quest.completed) {
          const progress = Math.min(quest.goal, quest.progress + 1);
          return { ...quest, progress, completed: progress >= quest.goal };
        }
        return quest;
      }));
    } else {
      setStreak(0);
      setFeedback({ text: `Answer: ${q.opts[q.correct]}`, ok: false });
      setTheoMessage("Every mistake is a lesson! You'll get the next one!");
    }
    setTimeout(() => setFeedback(null), 3000);
  }, []);

  // ─────────────────────────────────────────────────────────────
  // CRAFTING HANDLER
  // ─────────────────────────────────────────────────────────────
  const handleCraft = useCallback((recipeId: string) => {
    const cs = craftingSystemRef.current;
    if (!cs) return;
    const result = cs.craft(inventoryRef.current, recipeId);
    if (result.success && result.result) {
      setInventory({ ...inventoryRef.current });
      // Give XP for crafting
      setXp(p => p + 5);
      setFeedback({ text: `Crafted ${result.result?.replace(/_/g, " ")} x${result.qty}!`, ok: true });
      setTimeout(() => setFeedback(null), 2500);
    }
  }, []);

  // ─────────────────────────────────────────────────────────────
  // USE HEALTH POTION
  // ─────────────────────────────────────────────────────────────
  const handleUseHealthPotion = useCallback(() => {
    const inv = inventoryRef.current;
    if ((inv.health_potion ?? 0) <= 0) return;
    inv.health_potion -= 1;
    setInventory({ ...inv });
    setHp(h => Math.min(100, h + 30));
    setFeedback({ text: "Restored 30 HP!", ok: true });
    setTimeout(() => setFeedback(null), 2000);
  }, []);

  // ─────────────────────────────────────────────────────────────
  // THREE.JS GAME SETUP
  // ─────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!gameStarted || !canvasRef.current) return;
    const canvas = canvasRef.current;
    let alive = true;
    let currentPlanet: Planet = "earth";

    // ── Renderer ──────────────────────────────────────────────
    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(canvas.clientWidth, canvas.clientHeight);
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.2;
    rendererRef.current = renderer;

    // ── Scene ─────────────────────────────────────────────────
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x87ceeb);
    scene.fog = new THREE.FogExp2(0xa8d8ea, 0.013);

    // ── Lights ────────────────────────────────────────────────
    const ambient = new THREE.AmbientLight(0xd4e8ff, 0.55);
    scene.add(ambient);

    const sun = new THREE.DirectionalLight(0xfff3d6, 1.4);
    sun.position.set(40, 70, 30);
    sun.castShadow = true;
    sun.shadow.mapSize.setScalar(1024);
    sun.shadow.camera.near = 0.5;
    sun.shadow.camera.far = 250;
    sun.shadow.camera.left  = sun.shadow.camera.bottom = -70;
    sun.shadow.camera.right = sun.shadow.camera.top    =  70;
    sun.shadow.bias = -0.001;
    scene.add(sun);

    const hemi = new THREE.HemisphereLight(0x87ceeb, 0x3a6b2a, 0.4);
    scene.add(hemi);

    // ── Camera ────────────────────────────────────────────────
    const camera = new THREE.PerspectiveCamera(70, canvas.clientWidth / canvas.clientHeight, 0.1, 250);

    // ── Player ────────────────────────────────────────────────
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
    scene.add(playerGroup);

    // ── Theodore (AI companion orb) ────────────────────────────
    const theoGroup = new THREE.Group();
    const theoCore = new THREE.Mesh(
      new THREE.SphereGeometry(0.55, 16, 12),
      new THREE.MeshPhongMaterial({ color: 0xfbbf24, emissive: 0x7a5500, shininess: 80, specular: 0xffdd44 }),
    );
    theoCore.castShadow = true;
    theoGroup.add(theoCore);
    const theoRing = new THREE.Mesh(
      new THREE.TorusGeometry(0.82, 0.06, 8, 32),
      new THREE.MeshPhongMaterial({ color: 0xfde68a, emissive: 0x7a6000, shininess: 60 }),
    );
    theoGroup.add(theoRing);
    const theoGlow = new THREE.PointLight(0xfbbf24, 0.5, 4);
    theoGroup.add(theoGlow);
    scene.add(theoGroup);

    // ── World State ───────────────────────────────────────────
    let hmap = generateHeightMap(WORLD_SIZE, "earth");

    // ── Terrain ───────────────────────────────────────────────
    let terrainMesh: THREE.Mesh | null = null;

    function buildTerrain(planet: Planet): THREE.Mesh {
      const geo = buildTerrainGeometry(hmap, WORLD_SIZE, planet);
      const mat = new THREE.MeshPhongMaterial({ vertexColors: true, shininess: 4 });
      const mesh = new THREE.Mesh(geo, mat);
      mesh.receiveShadow = true;
      // Offset so 0,0 is at world center (hmap is 0..WORLD_SIZE, center at HALF)
      mesh.position.set(-HALF, 0, -HALF);
      scene.add(mesh);
      return mesh;
    }

    terrainMesh = buildTerrain("earth");

    // ── Water ─────────────────────────────────────────────────
    const waterGeo = new THREE.PlaneGeometry(WORLD_SIZE + 4, WORLD_SIZE + 4);
    waterGeo.rotateX(-Math.PI / 2);
    const waterMat = new THREE.MeshPhongMaterial({
      color: 0x2a80d4, transparent: true, opacity: 0.72, shininess: 80, specular: 0x88bbff,
    });
    const water = new THREE.Mesh(waterGeo, waterMat);
    water.position.y = 1.35;
    scene.add(water);

    // ── Trees ─────────────────────────────────────────────────
    const trunkMat = new THREE.MeshPhongMaterial({ color: 0x5a3a1a });
    const leafMatA = new THREE.MeshPhongMaterial({ color: 0x2d7a18 });
    const leafMatB = new THREE.MeshPhongMaterial({ color: 0x1e6010 });
    const treeObjects: THREE.Object3D[] = [];

    function spawnTrees(hmapData: number[][]): void {
      for (const obj of treeObjects) scene.remove(obj);
      treeObjects.length = 0;
      for (let i = 0; i < 90; i++) {
        const tx = Math.round((Math.sin(i * 137.508) * 0.5 + 0.5) * (WORLD_SIZE - 8)) - HALF + 4;
        const tz = Math.round((Math.cos(i * 137.508) * 0.5 + 0.5) * (WORLD_SIZE - 8)) - HALF + 4;
        const th = getTerrainHeight(hmapData, Math.round(tx + HALF), Math.round(tz + HALF), WORLD_SIZE);
        if (th < 3 || th > 5) continue;
        const trunk = new THREE.Mesh(new THREE.CylinderGeometry(0.28, 0.38, 3, 6), trunkMat);
        trunk.position.set(tx + 0.5, th, tz + 0.5);
        trunk.castShadow = true;
        scene.add(trunk);
        treeObjects.push(trunk);
        const lm = i % 2 === 0 ? leafMatA : leafMatB;
        const leaves = new THREE.Mesh(new THREE.IcosahedronGeometry(1.8, 0), lm);
        leaves.position.set(tx + 0.5, th + 2.5, tz + 0.5);
        leaves.scale.y = 0.85;
        leaves.castShadow = true;
        scene.add(leaves);
        treeObjects.push(leaves);
      }
    }
    spawnTrees(hmap);

    // ── Question Blocks ───────────────────────────────────────
    const qbMat = new THREE.MeshPhongMaterial({ color: 0xfbbf24, emissive: 0x4a3800, shininess: 60 });
    const qbMatDone = new THREE.MeshPhongMaterial({ color: 0x4ade80, emissive: 0x0a3010, shininess: 30 });
    const qbGeo = new THREE.BoxGeometry(0.95, 0.95, 0.95);
    let qblocks: { mesh: THREE.Mesh; id: string; baseY: number }[] = [];

    function spawnQBlocks(hmapData: number[][]): void {
      for (const qb of qblocks) scene.remove(qb.mesh);
      qblocks = [];
      QUESTION_POSITIONS.slice(0, QUESTIONS.length).forEach(([qx, qz], i) => {
        const ax = Math.max(-HALF + 2, Math.min(HALF - 2, qx));
        const az = Math.max(-HALF + 2, Math.min(HALF - 2, qz));
        const qh = getTerrainHeight(hmapData, Math.round(ax + HALF), Math.round(az + HALF), WORLD_SIZE);
        const mesh = new THREE.Mesh(qbGeo, qbMat.clone());
        const by = qh + 1.6;
        mesh.position.set(ax, by, az);
        mesh.castShadow = true;
        scene.add(mesh);
        qblocks.push({ mesh, id: QUESTIONS[i].id, baseY: by });
      });
    }
    spawnQBlocks(hmap);

    // ── Game Systems ──────────────────────────────────────────
    const combatSystem = new CombatSystem(scene, sun);
    let enemyManager = new EnemyManager(scene, "earth", hmap, WORLD_SIZE);
    enemyManager.spawnEnemies();
    let npcManager = new NPCManager(scene, "earth", hmap, WORLD_SIZE);
    let mountManager = new MountManager(scene, "earth", hmap, WORLD_SIZE);
    let vehicleManager = new VehicleManager(scene, "earth", hmap, WORLD_SIZE);
    const craftingSystem = new CraftingSystem(scene, hmap, WORLD_SIZE);
    craftingSystem.spawnResourcePickups();
    craftingSystemRef.current = craftingSystem;
    const buildingSystem = new BuildingSystem(scene);
    buildingSystemRef.current = buildingSystem;
    const planetSystem = new PlanetSystem(scene, WORLD_SIZE);
    planetSystem.setupPlanet1(scene, hmap);
    planetSystem.activatePortal();

    // Set player start position
    const startH = getTerrainHeight(hmap, HALF, HALF, WORLD_SIZE);
    playerGroup.position.set(0, startH + 0.9, 0);
    theoGroup.position.set(3, startH + 2.5, 3);

    // ── Camera state ──────────────────────────────────────────
    let camYaw = 0, camPitch = 0.45, camDist = 9;
    let isDragging = false, lastMX = 0, lastMY = 0;
    const camTarget = new THREE.Vector3();
    const camOffset = new THREE.Vector3();

    // ── Physics state ─────────────────────────────────────────
    let velY = 0;
    let jumpCount = 0;
    let isFlipping = false;
    let flipProgress = 0;
    let wasOnGround = true;

    // Attack cooldowns
    let punchCooldown = 0;
    let kickCooldown = 0;
    let magicCooldown = 0;

    // Keys pressed (used for one-shot logic)
    const keyJustDown = new Set<string>();

    // Player facing direction
    const playerFacing = new THREE.Vector3(0, 0, 1);
    const moveDir = new THREE.Vector3();

    // React state throttle
    let lastReactUpdate = 0;
    let playerHp = 100;
    let playerXp = 0;
    let playerGems = 0;
    let playerStreak = 0;
    let currentZone = "Starter Village";
    let invLocal = makeInitialInventory();
    let theoTipIdx = 0;
    let lastTheoFlip = 0;
    let gameTime = 0;

    // ── Mouse events ──────────────────────────────────────────
    const onMouseDown = (e: MouseEvent) => {
      isDragging = true;
      lastMX = e.clientX;
      lastMY = e.clientY;
      mouseRef.current.buttons = e.buttons;

      // Right-click in building mode: place block
      if (e.button === 2 && buildingSystem.isBuilding) {
        e.preventDefault();
        buildingSystem.placeBlock(camera, scene, invLocal);
      }
    };
    const onMouseUp = (e: MouseEvent) => {
      isDragging = false;
      mouseRef.current.buttons = 0;
    };
    const onMouseMove = (e: MouseEvent) => {
      if (!isDragging) return;
      camYaw   -= (e.clientX - lastMX) * 0.006;
      camPitch -= (e.clientY - lastMY) * 0.004;
      camPitch = Math.max(0.12, Math.min(1.3, camPitch));
      lastMX = e.clientX;
      lastMY = e.clientY;
    };
    const onWheel = (e: WheelEvent) => {
      camDist = Math.max(3, Math.min(20, camDist + e.deltaY * 0.02));
    };
    const onContextMenu = (e: Event) => e.preventDefault();

    canvas.addEventListener("mousedown",   onMouseDown);
    window.addEventListener("mouseup",     onMouseUp);
    window.addEventListener("mousemove",   onMouseMove);
    canvas.addEventListener("wheel",       onWheel, { passive: true });
    canvas.addEventListener("contextmenu", onContextMenu);

    // ── Touch events ──────────────────────────────────────────
    const onTouch1 = (e: TouchEvent) => {
      if (e.touches.length === 1) { isDragging = true; lastMX = e.touches[0].clientX; lastMY = e.touches[0].clientY; }
    };
    const onTouch2 = () => { isDragging = false; };
    const onTouchM = (e: TouchEvent) => {
      if (!isDragging || e.touches.length !== 1) return;
      camYaw   -= (e.touches[0].clientX - lastMX) * 0.008;
      camPitch -= (e.touches[0].clientY - lastMY) * 0.006;
      camPitch = Math.max(0.12, Math.min(1.3, camPitch));
      lastMX = e.touches[0].clientX;
      lastMY = e.touches[0].clientY;
    };
    canvas.addEventListener("touchstart", onTouch1, { passive: true });
    window.addEventListener("touchend",   onTouch2);
    canvas.addEventListener("touchmove",  onTouchM, { passive: true });

    // ── Keyboard events ───────────────────────────────────────
    const onKeyDown = (e: KeyboardEvent) => {
      keysRef.current[e.code] = true;
      keyJustDown.add(e.code);

      // ─── E: context-sensitive interact ───────────────────────
      if (e.code === "KeyE") {
        const pos = playerGroup.position;

        // Check NPC proximity
        const nearNPC = npcManager.getNearbyNPC(pos);
        if (nearNPC) {
          const lines = nearNPC.dialogue;
          setDialogueLines(lines);
          setDialogueNpcName(nearNPC.name);
          return;
        }

        // Check mount proximity
        const nearMount = mountManager.getNearbyMount(pos);
        if (nearMount) {
          if (mountManager.isMounted()) {
            mountManager.dismount();
          } else {
            mountManager.mount(nearMount.id);
          }
          return;
        }

        // Check vehicle proximity
        const nearVehicle = vehicleManager.checkNearby(pos);
        if (nearVehicle) {
          if (vehicleManager.activeVehicle !== null) {
            vehicleManager.exitVehicle(playerGroup);
          } else {
            vehicleManager.enterVehicle(nearVehicle, playerGroup);
          }
          return;
        }

        // Check portal
        if (planetSystem.checkPortalProximity(pos)) {
          const hasKey = invLocal.portal_key > 0;
          const hasStars = invLocal.star_crystal >= 3;
          if (hasKey || hasStars) {
            triggerPlanetSwitch();
          }
          return;
        }

        // Question block
        if (nearPromptRef.current && !activeQRef.current) {
          const q = QUESTIONS.find(
            qq => qq.id === nearPromptRef.current && !answeredRef.current.has(qq.id),
          );
          if (q) setActiveQ(q as Question);
        }
      }

      // ─── TAB: toggle inventory / crafting ────────────────────
      if (e.code === "Tab") {
        e.preventDefault();
        setInventoryOpen(v => !v);
        setCraftingOpen(false);
      }

      // ─── B: toggle building mode ──────────────────────────────
      if (e.code === "KeyB") {
        const next = !buildingSystem.isBuilding;
        buildingSystem.toggle();
        setBuildingMode(next);
      }

      // ─── F: open crafting table (or fire laser in rover) ─────
      if (e.code === "KeyF") {
        if (vehicleManager.activeVehicle !== null) {
          vehicleManager.fireLaser();
        } else {
          const recipes = craftingSystem.getAvailableRecipes(invLocal);
          setAvailableRecipes(recipes);
          setCraftingOpen(v => !v);
          setInventoryOpen(false);
        }
      }

      // ─── Q: quick-use health potion ───────────────────────────
      if (e.code === "KeyQ") {
        if (invLocal.health_potion > 0) {
          invLocal.health_potion -= 1;
          playerHp = Math.min(100, playerHp + 30);
          setHp(playerHp);
          setInventory({ ...invLocal });
          setFeedback({ text: "Restored 30 HP!", ok: true });
          setTimeout(() => setFeedback(null), 2000);
        }
      }

      // ─── Escape: close modals ─────────────────────────────────
      if (e.code === "Escape") {
        setActiveQ(null);
        setCraftingOpen(false);
        setInventoryOpen(false);
        setDialogueLines(null);
        setDialogueNpcName(null);
      }
    };

    const onKeyUp = (e: KeyboardEvent) => {
      keysRef.current[e.code] = false;
    };

    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("keyup",   onKeyUp);

    // ── Resize ────────────────────────────────────────────────
    const onResize = () => {
      renderer.setSize(canvas.clientWidth, canvas.clientHeight);
      camera.aspect = canvas.clientWidth / canvas.clientHeight;
      camera.updateProjectionMatrix();
    };
    window.addEventListener("resize", onResize);

    // ── Planet Switch ─────────────────────────────────────────
    async function triggerPlanetSwitch() {
      setSwitchingPlanet(true);
      await new Promise(r => setTimeout(r, 1200));

      // Dispose old systems
      enemyManager.dispose();
      npcManager.dispose();
      mountManager.dispose();
      vehicleManager.dispose();
      if (terrainMesh) { scene.remove(terrainMesh); terrainMesh.geometry.dispose(); }

      // Switch planet
      const newPlanet: Planet = currentPlanet === "earth" ? "space" : "earth";
      currentPlanet = newPlanet;
      setPlanet(newPlanet);

      // Rebuild
      hmap = generateHeightMap(WORLD_SIZE, newPlanet);
      terrainMesh = buildTerrain(newPlanet);

      const newGrav = newPlanet === "space" ? GRAVITY_SPACE : GRAVITY_EARTH;
      const spawnH = getTerrainHeight(hmap, HALF, HALF, WORLD_SIZE);
      playerGroup.position.set(0, spawnH + 0.9, 0);
      velY = 0;

      // Update fog/sky
      if (newPlanet === "space") {
        scene.fog = new THREE.FogExp2(0x050010, 0.006);
        scene.background = new THREE.Color(0x010008);
        ambient.color.setHex(0x441166);
        ambient.intensity = 0.35;
        sun.intensity = 0.6;
        water.visible = false;
      } else {
        scene.fog = new THREE.FogExp2(0xa8d8ea, 0.013);
        scene.background = new THREE.Color(0x87ceeb);
        ambient.color.setHex(0xd4e8ff);
        ambient.intensity = 0.55;
        sun.intensity = 1.4;
        water.visible = true;
      }

      if (newPlanet === "space") {
        planetSystem.setupPlanet2(scene, hmap);
      } else {
        planetSystem.setupPlanet1(scene, hmap);
      }
      planetSystem.activatePortal();

      enemyManager = new EnemyManager(scene, newPlanet, hmap, WORLD_SIZE);
      enemyManager.spawnEnemies();
      npcManager = new NPCManager(scene, newPlanet, hmap, WORLD_SIZE);
      mountManager = new MountManager(scene, newPlanet, hmap, WORLD_SIZE);
      vehicleManager = new VehicleManager(scene, newPlanet, hmap, WORLD_SIZE);
      craftingSystem.spawnResourcePickups();

      spawnTrees(hmap);
      spawnQBlocks(hmap);

      setTheoMessage(
        newPlanet === "space"
          ? "We made it to the Crystal World! Space Wraiths are dangerous here!"
          : "Welcome back to Earth! Your journey continues!",
      );

      await new Promise(r => setTimeout(r, 400));
      setSwitchingPlanet(false);
    }

    // ── GAME LOOP ─────────────────────────────────────────────
    const clock = new THREE.Clock();

    const loop = () => {
      if (!alive) return;
      frameRef.current = requestAnimationFrame(loop);

      const dt = Math.min(clock.getDelta(), 0.05);
      gameTime += dt;

      const keys = keysRef.current;
      const gravity = currentPlanet === "space" ? GRAVITY_SPACE : GRAVITY_EARTH;

      // ── Vehicle/mount speed override ──────────────────────────
      const inVehicle = vehicleManager.activeVehicle !== null;
      const mounted = mountManager.isMounted();
      const speedOverride = inVehicle
        ? (vehicleManager.activeVehicle?.speed ?? 0)
        : mounted
        ? 5.5 * mountManager.getSpeedBonus()
        : 0;

      // ── Player movement ───────────────────────────────────────
      const baseSpeed = speedOverride > 0 ? speedOverride : 5.5;
      const sprint = keys["ShiftLeft"] || keys["ShiftRight"] ? 1.6 : 1.0;
      const speed = baseSpeed * sprint;

      const camFwd   = new THREE.Vector3(-Math.sin(camYaw), 0, -Math.cos(camYaw));
      const camRight = new THREE.Vector3( Math.cos(camYaw), 0, -Math.sin(camYaw));

      moveDir.set(0, 0, 0);
      if (keys["KeyW"] || keys["ArrowUp"])    moveDir.addScaledVector(camFwd,    1);
      if (keys["KeyS"] || keys["ArrowDown"])  moveDir.addScaledVector(camFwd,   -1);
      if (keys["KeyA"] || keys["ArrowLeft"])  moveDir.addScaledVector(camRight, -1);
      if (keys["KeyD"] || keys["ArrowRight"]) moveDir.addScaledVector(camRight,  1);

      if (moveDir.lengthSq() > 0) {
        moveDir.normalize();
        playerGroup.position.addScaledVector(moveDir, speed * dt);
        playerFacing.copy(moveDir);
        playerGroup.rotation.y = Math.atan2(moveDir.x, moveDir.z);
      }

      // ── Gravity & jumping ─────────────────────────────────────
      const onGround = wasOnGround;

      if (keyJustDown.has("Space") || keyJustDown.has("KeyJ")) {
        if (jumpCount < 2) {
          velY = currentPlanet === "space" ? 7.5 : 5.8;
          jumpCount++;
          // Second jump triggers a backflip visual
          if (jumpCount === 2) {
            isFlipping = true;
            flipProgress = 0;
          }
        }
      }

      velY -= gravity * dt;
      playerGroup.position.y += velY * dt;

      // Flip animation (rotate player.rotation.x by 2π over 0.4 s)
      if (isFlipping) {
        const flipSpeed = (Math.PI * 2) / 0.4;
        flipProgress += dt;
        playerGroup.rotation.x = (flipProgress / 0.4) * Math.PI * 2;
        if (flipProgress >= 0.4) {
          isFlipping = false;
          playerGroup.rotation.x = 0;
        }
      }

      // ── Ground clamping ───────────────────────────────────────
      const px = Math.max(0, Math.min(WORLD_SIZE - 1, Math.round(playerGroup.position.x + HALF)));
      const pz = Math.max(0, Math.min(WORLD_SIZE - 1, Math.round(playerGroup.position.z + HALF)));
      const floorH = getTerrainHeight(hmap, px, pz, WORLD_SIZE) + 0.9;

      if (playerGroup.position.y < floorH) {
        playerGroup.position.y = floorH;
        velY = 0;
        jumpCount = 0;
        wasOnGround = true;
      } else {
        wasOnGround = playerGroup.position.y <= floorH + 0.15;
      }

      // World bounds
      playerGroup.position.x = Math.max(-HALF + 1, Math.min(HALF - 1, playerGroup.position.x));
      playerGroup.position.z = Math.max(-HALF + 1, Math.min(HALF - 1, playerGroup.position.z));

      // ── Combat attacks ────────────────────────────────────────
      punchCooldown = Math.max(0, punchCooldown - dt);
      kickCooldown  = Math.max(0, kickCooldown  - dt);
      magicCooldown = Math.max(0, magicCooldown - dt);

      // Punch: Z or left-click
      if ((keyJustDown.has("KeyZ") || (mouseRef.current.buttons & 1 && punchCooldown <= 0)) && punchCooldown <= 0) {
        const weapon = activeWeaponRef.current;
        combatSystem.startAttack("punch", playerGroup.position, playerFacing, weapon);
        punchCooldown = 0.55;
      }
      // Kick: X
      if (keyJustDown.has("KeyX") && kickCooldown <= 0) {
        combatSystem.startAttack("kick", playerGroup.position, playerFacing, activeWeaponRef.current);
        kickCooldown = 0.8;
      }
      // Flip attack: C (in air, uses flip if double-jumped)
      if (keyJustDown.has("KeyC") && !wasOnGround && punchCooldown <= 0) {
        combatSystem.startAttack("flip", playerGroup.position, playerFacing, activeWeaponRef.current);
        punchCooldown = 1.0;
      }
      // Magic: V (if staff equipped)
      if (keyJustDown.has("KeyV") && activeWeaponRef.current === "staff" && magicCooldown <= 0) {
        combatSystem.startAttack("magic", playerGroup.position, playerFacing, "staff");
        magicCooldown = 1.2;
      }

      // ── Camera ───────────────────────────────────────────────
      camTarget.lerp(playerGroup.position, 0.12);
      camOffset.set(
        Math.sin(camYaw) * Math.cos(camPitch) * camDist,
        Math.sin(camPitch) * camDist,
        Math.cos(camYaw) * Math.cos(camPitch) * camDist,
      );
      camera.position.copy(camTarget).add(camOffset);
      camera.lookAt(camTarget.x, camTarget.y + 0.6, camTarget.z);

      // ── Building preview ──────────────────────────────────────
      if (buildingSystem.isBuilding) {
        buildingSystem.updatePreview(camera, scene);
      }

      // ── Enemy update ──────────────────────────────────────────
      const enemyResult = enemyManager.update(dt, playerGroup.position, playerHp);
      if (enemyResult.damage > 0) {
        playerHp = Math.max(0, playerHp - enemyResult.damage);
        combatSystem.spawnShockwave(playerGroup.position, 0xef4444);
        if (playerHp <= 0) {
          // Respawn with half HP
          playerHp = 50;
          playerGroup.position.set(0, getTerrainHeight(hmap, HALF, HALF, WORLD_SIZE) + 0.9, 0);
          setTheoMessage("You were knocked out! Back at the start — keep going!");
        }
      }

      // ── NPC update ────────────────────────────────────────────
      npcManager.update(dt);

      // ── Mount update ──────────────────────────────────────────
      mountManager.update(dt, playerGroup.position, mounted);

      // ── Vehicle update ────────────────────────────────────────
      vehicleManager.update(dt, keys, gameTime, hmap, WORLD_SIZE);

      // ── Crafting pickups ──────────────────────────────────────
      const pickupResult = craftingSystem.update(dt, playerGroup.position);
      if (pickupResult.collected) {
        const item = pickupResult.collected;
        invLocal[item] = (invLocal[item] ?? 0) + 1;
        if (item === "star_crystal") {
          setQuestLog(ql => ql.map(q => {
            if (q.id === "q_crystal_hunter" && !q.completed) {
              const progress = Math.min(q.goal, q.progress + 1);
              return { ...q, progress, completed: progress >= q.goal };
            }
            return q;
          }));
        }
        // Resource gathering quest
        setQuestLog(ql => ql.map(q => {
          if (q.id === "q_gatherer" && !q.completed) {
            const progress = Math.min(q.goal, q.progress + 1);
            return { ...q, progress, completed: progress >= q.goal };
          }
          return q;
        }));
      }

      // ── Planet system update ──────────────────────────────────
      planetSystem.update(dt, gameTime);

      // ── Portal proximity check ────────────────────────────────
      const nearPortal = planetSystem.checkPortalProximity(playerGroup.position, 4.0);
      const hasPortalAccess = invLocal.portal_key > 0 || invLocal.star_crystal >= 3;

      // ── Question block proximity ──────────────────────────────
      let nearestQId: string | null = null;
      let nearestDist = 3.5;

      qblocks.forEach(({ mesh, id, baseY }, i) => {
        const done = answeredRef.current.has(id);
        mesh.rotation.y = gameTime * 0.7 + i * 0.4;
        mesh.rotation.x = Math.sin(gameTime * 0.4 + i) * 0.12;
        mesh.position.y = baseY + Math.sin(gameTime * 1.3 + i * 0.8) * 0.22;

        if (done) {
          // @ts-ignore
          if (mesh.material.color.getHex() !== 0x4ade80) {
            mesh.material = qbMatDone;
            mesh.scale.setScalar(1.0);
          }
        } else {
          const d = playerGroup.position.distanceTo(mesh.position);
          if (d < nearestDist) { nearestDist = d; nearestQId = id; }
          mesh.scale.setScalar(1 + Math.sin(gameTime * 3 + i) * 0.06);
        }
      });

      // ── Near prompt ───────────────────────────────────────────
      let newPrompt: string | null = null;
      const pp = playerGroup.position;

      const nearNPC = npcManager.getNearbyNPC(pp, 3.0);
      const nearMount = mountManager.getNearbyMount(pp, 2.5);
      const nearVehicle = vehicleManager.checkNearby(pp);

      if (nearNPC) {
        newPrompt = `Talk to ${nearNPC.name}`;
      } else if (nearMount && !mountManager.isMounted()) {
        newPrompt = `Mount ${nearMount.type.replace("_", " ")}`;
      } else if (mounted && mountManager.getMountedMount()) {
        newPrompt = "Dismount";
      } else if (nearVehicle && !inVehicle) {
        newPrompt = `Enter ${nearVehicle.type}`;
      } else if (inVehicle) {
        newPrompt = "Exit vehicle";
      } else if (nearPortal && hasPortalAccess) {
        newPrompt = `Enter portal to ${currentPlanet === "earth" ? "Crystal World" : "Earth"}`;
      } else if (nearestQId) {
        newPrompt = "Learn something new";
      }

      if (newPrompt !== nearPromptRef.current) setNearPrompt(newPrompt);

      // ── Theodore follow & tips ────────────────────────────────
      const toPlayer = playerGroup.position.clone().sub(theoGroup.position);
      toPlayer.y = 0;
      const theoDist = toPlayer.length();
      if (theoDist > 4.5) {
        theoGroup.position.addScaledVector(toPlayer.normalize(), Math.min(theoDist - 4, 3.5) * dt);
      }
      const theoHx = Math.max(0, Math.min(WORLD_SIZE - 1, Math.round(theoGroup.position.x + HALF)));
      const theoHz = Math.max(0, Math.min(WORLD_SIZE - 1, Math.round(theoGroup.position.z + HALF)));
      const theoFloor = getTerrainHeight(hmap, theoHx, theoHz, WORLD_SIZE) + 2.2;
      theoGroup.position.y = theoFloor + Math.sin(gameTime * 1.8) * 0.18;
      theoGroup.rotation.y = Math.atan2(
        playerGroup.position.x - theoGroup.position.x,
        playerGroup.position.z - theoGroup.position.z,
      );
      theoRing.rotation.x = gameTime * 1.2;
      theoRing.rotation.z = gameTime * 0.8;

      if (gameTime - lastTheoFlip > 18) {
        lastTheoFlip = gameTime;
        theoTipIdx = (theoTipIdx + 1) % THEO_TIPS.length;
        setTheoMessage(THEO_TIPS[theoTipIdx]);
      }

      // ── Combat system update ──────────────────────────────────
      combatSystem.update(dt);
      combatSystem.tickShockwaves(dt);

      // ── Zone detection ────────────────────────────────────────
      let z = "Starter Village";
      if (pp.z < -16) z = pp.x > 10 ? "Stone Mountains" : "Snow Peaks";
      else if (pp.z > 16) z = "Desert Dunes";
      else if (pp.x < -16) z = "Dark Forest";
      else if (pp.x > 16) z = "Eastern Plains";
      if (pp.y > 7) z = "Mountain Summit";
      if (currentZone !== z) currentZone = z;

      // ── Water shimmer ─────────────────────────────────────────
      (water.material as THREE.MeshPhongMaterial).opacity = 0.68 + Math.sin(gameTime * 0.7) * 0.04;

      // ── Throttled React state update (10 fps) ─────────────────
      if (gameTime - lastReactUpdate > 0.1) {
        lastReactUpdate = gameTime;
        setHp(playerHp);
        setXp(playerXp);
        setGems(playerGems);
        setZone(currentZone);
        setInventory({ ...invLocal });
        // Refresh available recipes when crafting is open (handled when F is pressed)
      }

      // Clear just-down keys
      keyJustDown.clear();

      renderer.render(scene, camera);
    };

    loop();

    console.log("[Worlds] Initialized");

    // ── Cleanup ───────────────────────────────────────────────
    return () => {
      alive = false;
      cancelAnimationFrame(frameRef.current);

      enemyManager.dispose();
      npcManager.dispose();
      mountManager.dispose();
      vehicleManager.dispose();
      buildingSystem.dispose();
      combatSystem.dispose();

      renderer.dispose();
      rendererRef.current = null;
      craftingSystemRef.current = null;
      buildingSystemRef.current = null;

      canvas.removeEventListener("mousedown",   onMouseDown);
      window.removeEventListener("mouseup",     onMouseUp);
      window.removeEventListener("mousemove",   onMouseMove);
      canvas.removeEventListener("wheel",       onWheel);
      canvas.removeEventListener("contextmenu", onContextMenu);
      canvas.removeEventListener("touchstart",  onTouch1);
      window.removeEventListener("touchend",    onTouch2);
      canvas.removeEventListener("touchmove",   onTouchM);
      window.removeEventListener("keydown",     onKeyDown);
      window.removeEventListener("keyup",       onKeyUp);
      window.removeEventListener("resize",      onResize);
    };
  }, [gameStarted]); // eslint-disable-line react-hooks/exhaustive-deps

  // ─────────────────────────────────────────────────────────────
  // RENDER
  // ─────────────────────────────────────────────────────────────
  return (
    <div style={{ position: "fixed", inset: 0, background: "#000", overflow: "hidden" }}>
      {/* Three.js canvas */}
      <canvas
        ref={canvasRef}
        style={{
          display: "block",
          width: "100%",
          height: "100%",
          touchAction: "none",
          cursor: gameStarted ? "crosshair" : "default",
        }}
      />

      {/* ── START SCREEN ──────────────────────────────────────── */}
      {!gameStarted && (
        <div style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          background: "linear-gradient(135deg,rgba(5,7,20,.98) 0%,rgba(18,6,48,.98) 100%)",
        }}>
          <div style={{ fontSize: 80, marginBottom: 6, filter: "drop-shadow(0 0 32px #6366f1)" }}>🌍</div>
          <h1 style={{
            color: "#fff",
            fontSize: 50,
            fontWeight: 900,
            margin: "0 0 8px",
            letterSpacing: -1,
            textShadow: "0 0 40px rgba(99,102,241,0.6)",
          }}>
            Salareen Worlds
          </h1>
          <p style={{
            color: "#a5b4fc",
            fontSize: 17,
            margin: "0 0 28px",
            textAlign: "center",
            maxWidth: 480,
            lineHeight: 1.6,
          }}>
            An open-world educational RPG. Explore 2 planets with Theodore your AI guide,
            fight enemies, mount animals, build structures, and answer 22 questions to earn XP!
          </p>

          {/* Feature badges */}
          <div style={{ display: "flex", flexWrap: "wrap", gap: 10, marginBottom: 28, justifyContent: "center", maxWidth: 520 }}>
            {[
              "🏔 Open World", "⚔️ Combat", "🐴 Mounts", "🚗 Vehicles",
              "🏗 Building", "🧪 Crafting", "🌌 2 Planets", "📚 22 Questions",
              "🤖 AI Guide Theodore", "🏆 Quests",
            ].map(f => (
              <span key={f} style={{
                background: "rgba(99,102,241,0.12)",
                borderRadius: 20,
                padding: "5px 13px",
                color: "#c7d2fe",
                fontSize: 13,
                fontWeight: 600,
                border: "1px solid rgba(99,102,241,0.25)",
              }}>{f}</span>
            ))}
          </div>

          {/* Controls */}
          <div style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: "5px 28px",
            marginBottom: 30,
            fontSize: 13,
            color: "#475569",
          }}>
            <span>WASD — Move</span>
            <span>Shift — Sprint</span>
            <span>Space ×2 — Double Jump</span>
            <span>Z/X/C/V — Attack</span>
            <span>E — Interact</span>
            <span>TAB / F / B — Panels</span>
          </div>

          <button
            onClick={() => setGameStarted(true)}
            style={{
              background: "linear-gradient(135deg,#6366f1,#8b5cf6)",
              color: "#fff",
              border: "none",
              borderRadius: 18,
              padding: "17px 56px",
              fontSize: 21,
              fontWeight: 900,
              cursor: "pointer",
              boxShadow: "0 8px 36px rgba(99,102,241,0.55)",
              letterSpacing: 0.5,
            }}
          >
            Start Adventure
          </button>
          <p style={{ color: "#1e293b", fontSize: 12, marginTop: 18 }}>
            {QUESTIONS.length} questions · 5 subjects · 2 planets · Infinite exploration
          </p>
        </div>
      )}

      {/* ── IN-GAME HUD ───────────────────────────────────────── */}
      {gameStarted && (
        <GameHUD
          hp={hp}
          maxHp={100}
          xp={xp}
          gems={gems}
          streak={streak}
          zone={zone}
          planet={planet}
          questLog={questLog}
          inventory={inventory}
          activeWeapon={activeWeapon}
          answered={answered.size}
          totalQuestions={QUESTIONS.length}
          craftingOpen={craftingOpen}
          availableRecipes={availableRecipes}
          nearPrompt={nearPrompt}
          theoMessage={theoMessage}
          feedback={feedback}
          dialogueLines={dialogueLines}
          dialogueNpcName={dialogueNpcName}
          buildingMode={buildingMode}
          inventoryOpen={inventoryOpen}
          onAnswerQuestion={handleAnswer}
          onCraft={handleCraft}
          onCloseDialogue={() => { setDialogueLines(null); setDialogueNpcName(null); }}
          onToggleCrafting={() => {
            const next = !craftingOpen;
            if (next) setAvailableRecipes(craftingSystem => {
              // trigger re-render only, actual update in game loop
              return availableRecipes;
            });
            setCraftingOpen(next);
            setInventoryOpen(false);
          }}
          onToggleInventory={() => { setInventoryOpen(v => !v); setCraftingOpen(false); }}
          onToggleBuilding={() => {
            const bs = buildingSystemRef.current;
            if (!bs) return;
            const next = !bs.isBuilding;
            bs.toggle();
            setBuildingMode(next);
          }}
          onUseHealthPotion={handleUseHealthPotion}
          onSelectWeapon={w => setActiveWeapon(w)}
        />
      )}

      {/* ── QUESTION MODAL ─────────────────────────────────────── */}
      {activeQ && (
        <div style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "rgba(0,0,0,0.8)",
          backdropFilter: "blur(6px)",
          zIndex: 50,
        }}>
          <div style={{
            background: "linear-gradient(135deg,#0d1117,#1a1040)",
            borderRadius: 24,
            padding: 32,
            width: "min(520px,92vw)",
            border: `2px solid ${SUBJECT_COLORS[activeQ.subject] ?? "#6366f1"}44`,
            boxShadow: `0 24px 64px rgba(0,0,0,0.7), 0 0 0 1px ${SUBJECT_COLORS[activeQ.subject] ?? "#6366f1"}22`,
          }}>
            {/* Header */}
            <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 20 }}>
              <div style={{
                width: 50,
                height: 50,
                borderRadius: 15,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                background: `${SUBJECT_COLORS[activeQ.subject] ?? "#6366f1"}20`,
                fontSize: 26,
                border: `1px solid ${SUBJECT_COLORS[activeQ.subject] ?? "#6366f1"}33`,
              }}>
                {activeQ.emoji}
              </div>
              <div>
                <div style={{ color: "#94a3b8", fontSize: 11, fontWeight: 900, textTransform: "uppercase", letterSpacing: 1.5 }}>
                  {activeQ.subject} · +{activeQ.xp} XP
                </div>
                <div style={{ color: SUBJECT_COLORS[activeQ.subject] ?? "#6366f1", fontSize: 12, fontWeight: 700, marginTop: 2 }}>
                  Question {QUESTIONS.findIndex(q => q.id === activeQ.id) + 1} of {QUESTIONS.length}
                </div>
              </div>
            </div>

            {/* Question text */}
            <div style={{ color: "#f1f5f9", fontSize: 22, fontWeight: 800, marginBottom: 24, lineHeight: 1.45 }}>
              {activeQ.text}
            </div>

            {/* Options */}
            <div style={{ display: "grid", gap: 11 }}>
              {activeQ.opts.map((opt, i) => (
                <button
                  key={i}
                  onClick={() => handleAnswer(i)}
                  style={{
                    background: "rgba(255,255,255,0.04)",
                    border: "1px solid rgba(255,255,255,0.11)",
                    borderRadius: 14,
                    padding: "14px 18px",
                    color: "#e2e8f0",
                    fontSize: 16,
                    fontWeight: 600,
                    textAlign: "left",
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    gap: 13,
                    transition: "all 0.1s",
                  }}
                  onMouseEnter={e => {
                    const el = e.currentTarget as HTMLButtonElement;
                    el.style.background = `${SUBJECT_COLORS[activeQ.subject] ?? "#6366f1"}22`;
                    el.style.borderColor = SUBJECT_COLORS[activeQ.subject] ?? "#6366f1";
                  }}
                  onMouseLeave={e => {
                    const el = e.currentTarget as HTMLButtonElement;
                    el.style.background = "rgba(255,255,255,0.04)";
                    el.style.borderColor = "rgba(255,255,255,0.11)";
                  }}
                >
                  <span style={{
                    width: 32,
                    height: 32,
                    borderRadius: 9,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    background: "rgba(255,255,255,0.09)",
                    fontSize: 13,
                    fontWeight: 900,
                    flexShrink: 0,
                    color: "#94a3b8",
                  }}>
                    {["A", "B", "C", "D"][i]}
                  </span>
                  {opt}
                </button>
              ))}
            </div>

            <button
              onClick={() => setActiveQ(null)}
              style={{
                marginTop: 16,
                background: "none",
                border: "none",
                color: "#475569",
                cursor: "pointer",
                fontSize: 13,
              }}
            >
              skip for now
            </button>
          </div>
        </div>
      )}

      {/* ── PLANET SWITCH OVERLAY ─────────────────────────────── */}
      {switchingPlanet && (
        <div style={{
          position: "absolute",
          inset: 0,
          background: "#000",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          zIndex: 100,
          flexDirection: "column",
          gap: 16,
          animation: "fadeIn 0.3s ease",
        }}>
          <div style={{ fontSize: 64, filter: "drop-shadow(0 0 24px #6366f1)" }}>
            {planet === "earth" ? "🌌" : "🌍"}
          </div>
          <div style={{ color: "#a5b4fc", fontSize: 22, fontWeight: 700, letterSpacing: 1 }}>
            Travelling through the portal...
          </div>
          <div style={{ color: "#334155", fontSize: 14 }}>Hold on tight!</div>
        </div>
      )}
    </div>
  );
}

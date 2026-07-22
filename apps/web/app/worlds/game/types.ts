// ============================================================
// Minecraft + Roblox + RPG Educational Web Game — Core Types
// Three.js-based; no imports from other project files needed.
// ============================================================

// ─────────────────────────────────────────────
// Primitives
// ─────────────────────────────────────────────

export type Vec3 = {
  x: number;
  y: number;
  z: number;
};

// ─────────────────────────────────────────────
// World / Environment
// ─────────────────────────────────────────────

export type Planet = 'earth' | 'space';

export type BiomeType =
  | 'grassland'
  | 'snow'
  | 'desert'
  | 'forest'
  | 'crystal'
  | 'void';

export type BlockType =
  | 'grass'
  | 'dirt'
  | 'stone'
  | 'sand'
  | 'snow'
  | 'wood'
  | 'leaf'
  | 'crystal'
  | 'starmetal'
  | 'glass'
  | 'bedrock';

export interface BlockDef {
  type: BlockType;
  solid: boolean;
  transparent: boolean;
  color: [r: number, g: number, b: number];
  emissive?: boolean;
  hardness: number; // hits required to break
}

// ─────────────────────────────────────────────
// Items & Inventory
// ─────────────────────────────────────────────

export type ItemType =
  | 'wood' | 'stone' | 'crystal' | 'starmetal' | 'herb' | 'star_crystal'
  | 'banana_peel' | 'iron_ore' | 'gold_nugget' | 'moon_dust' | 'void_shard'
  | 'ancient_scroll' | 'healing_potion' | 'health_potion'
  | 'mana_potion' | 'torch' | 'rope' | 'compass' | 'telescope'
  | 'mushroom' | 'feather' | 'bone' | 'gem_ruby' | 'gem_sapphire' | 'gem_emerald'
  | 'portal_fragment' | 'portal_key' | 'star_map' | 'wooden_planks'
  | 'stone_brick' | 'glass_pane' | 'starmetal_ingot'
  | 'sword' | 'staff' | 'bow' | 'plank' | 'stone_block' | 'crystal_block'
  | 'wooden_sword' | 'stone_axe' | 'crystal_staff' | 'star_blade'
  | 'wooden_shield' | 'stone_sword' | 'speed_potion' | 'wooden_fort_wall'
  | 'leather' | 'fur' | 'scale' | 'book' | 'map_fragment';

export interface InventoryItem {
  type: ItemType;
  qty: number;
  icon: string; // emoji or URL path
}

// ─────────────────────────────────────────────
// Crafting
// ─────────────────────────────────────────────

export interface CraftingRecipe {
  id: string;
  inputs?: Partial<Record<ItemType, number>>;
  ingredients?: Partial<Record<ItemType, number>>;  // alias used by some agents
  output: ItemType;
  outputQty: number;
  name: string;
  label?: string;
  description: string;
  icon: string;
  unlockLevel?: number;
  category?: 'weapons' | 'tools' | 'potions' | 'building' | 'misc';
  result?: ItemType;      // alias for output
  resultQty?: number;     // alias for outputQty
}

// Alias used by building.ts agents
export type BuildingBlockType = BlockType;

// ─────────────────────────────────────────────
// Combat
// ─────────────────────────────────────────────

export type WeaponType =
  | 'fists' | 'wooden_sword' | 'stone_axe' | 'crystal_staff'
  | 'star_blade' | 'portal_key'
  | 'sword' | 'staff' | 'bow';  // shorthand aliases used by some agents

export interface WeaponStats {
  type: WeaponType;
  damage: number;
  attackSpeed: number; // attacks per second
  range: number; // world units
  manaCost: number;
  special?: string; // e.g. "freeze", "chain-lightning"
  icon: string;
}

export interface AttackResult {
  hit: boolean;
  damage: number;
  effect?: string; // e.g. "freeze", "burn", "stun", "portal"
  critical?: boolean;
  knockback?: Vec3;
}

// ─────────────────────────────────────────────
// Mounts & Vehicles
// ─────────────────────────────────────────────

export type MountType =
  | 'giraffe'
  | 'buffalo'
  | 'turtle'
  | 'rabbit'
  | 'space_dragon';

export interface MountStats {
  type: MountType;
  speed: number;
  jumpBoost: number;
  special: string;
  icon: string;
  displayName?: string;
  planet?: Planet | 'both';
  unlockCost?: Partial<Record<ItemType, number>>;
  color?: number | string;    // optional used by mounts agent
  speedBonus?: number;        // optional alias for speed boost
}

export type VehicleType = 'rover' | 'space_hopper';

export interface VehicleStats {
  type: VehicleType;
  speed: number;
  boostSpeed: number;
  boostDuration: number; // seconds
  fuelCapacity: number;
  fuelConsumptionRate: number; // units per second
  planet: Planet | 'both';
  icon: string;
}

// ─────────────────────────────────────────────
// Enemies
// ─────────────────────────────────────────────

export type EnemyType =
  | 'goblin'
  | 'stone_golem'
  | 'space_wraith'
  | 'crystal_spider';

export type EnemyState =
  | 'idle'
  | 'patrol'
  | 'chase'
  | 'attack'
  | 'retreat'
  | 'dead';

export interface EnemyConfig {
  type: EnemyType;
  hp: number;
  speed: number;
  damage: number;
  attackRange: number;
  detectionRange: number;
  drops: ItemType[];
  xpReward: number;
  color: [r: number, g: number, b: number] | string;  // tuple or hex string
  attackCooldown?: number;
  biomes?: BiomeType[];
  special?: string;
  isRanged?: boolean;
  projectileSpeed?: number;
}

export interface EnemyInstance {
  id: string;
  config: EnemyConfig;
  state: EnemyState;
  position: Vec3;
  hp: number;
  target?: Vec3; // patrol waypoint or player position
  lastAttackTime?: number; // ms timestamp
}

// ─────────────────────────────────────────────
// NPCs & Dialogue
// ─────────────────────────────────────────────

export type NPCType = 'wizard' | 'merchant' | 'sage' | 'space_elder';

export interface NPCDialogue {
  npcId: string;
  lines: string[];
  secret?: string;
  questId?: string;
  // Extra fields used by some NPC agents
  type?: string;
  name?: string;
  color?: number | string;
  planet?: string;
  dialogue?: NPCDialogue;  // nested alias
}

export interface NPCConfig {
  id: string;
  type: NPCType;
  name: string;
  position: Vec3;
  planet: Planet | 'both';
  biome?: BiomeType;
  dialogue: NPCDialogue;
  shopInventory?: ItemType[]; // if merchant
  icon: string;
}

// ─────────────────────────────────────────────
// Quests
// ─────────────────────────────────────────────

export interface QuestReward {
  xp: number;
  items?: Partial<Record<ItemType, number>>;
  gems?: number;
  weaponUnlock?: WeaponType;
  mountUnlock?: MountType;
}

export interface QuestRewardItem {
  xp: number;
  items?: Partial<Record<ItemType, number>>;
  gems?: number;
  item?: ItemType;              // single item shorthand
  weaponUnlock?: WeaponType;
  mountUnlock?: MountType;
}

export interface Quest {
  id: string;
  title: string;
  description: string;
  objective: string;
  target: number;
  current: number;
  // Aliases used by WorldGame.tsx agent
  goal?: number;
  progress?: number;
  completed: boolean;
  reward: QuestReward | QuestRewardItem;
  npcId?: string;
  prerequisiteQuestId?: string;
  type?: 'kill' | 'collect' | 'build' | 'explore' | 'quiz' | 'craft';
  hidden?: boolean;
}

// ─────────────────────────────────────────────
// Powerups
// ─────────────────────────────────────────────

export type PowerupType =
  | 'speed'
  | 'freeze'
  | 'shield'
  | 'bomb'
  | 'mega_star'
  | 'double_damage';

export interface PowerupConfig {
  type: PowerupType;
  duration: number; // seconds; 0 = instant
  icon: string;
  description: string;
  stackable?: boolean;
}

export interface ActivePowerup {
  type: PowerupType;
  expiresAt: number; // ms timestamp
}

// ─────────────────────────────────────────────
// Skill Tree
// ─────────────────────────────────────────────

export interface SkillNode {
  id: string;
  name: string;
  description: string;
  icon: string;
  maxRank: number;
  currentRank: number;
  cost: number; // skill points per rank
  prerequisiteIds?: string[];
  effect: {
    stat:
      | 'damage'
      | 'speed'
      | 'mana'
      | 'hp'
      | 'xpGain'
      | 'dropRate'
      | 'buildSpeed';
    valuePerRank: number; // flat or percentage depending on stat
  };
}

export interface SkillPath {
  warrior: SkillNode[];
  scholar: SkillNode[];
  explorer: SkillNode[];
}

export interface SkillTree {
  paths: SkillPath;
  availablePoints: number;
  totalSpent: number;
}

// ─────────────────────────────────────────────
// Educational Layer
// ─────────────────────────────────────────────

export type SubjectArea =
  | 'math'
  | 'science'
  | 'history'
  | 'language'
  | 'coding'
  | 'geography';

export interface QuizQuestion {
  id: string;
  subject: SubjectArea;
  question: string;
  choices: string[];
  correctIndex: number;
  explanation: string;
  difficulty: 1 | 2 | 3; // 1=easy, 2=medium, 3=hard
  xpReward: number;
}

// ─────────────────────────────────────────────
// Building / Voxel World
// ─────────────────────────────────────────────

export interface PlacedBlock {
  id: string;
  type: BlockType;
  position: Vec3;
  placedBy?: 'player' | 'world';
}

export interface Chunk {
  cx: number; // chunk x index
  cz: number; // chunk z index
  blocks: Map<string, PlacedBlock>; // key = "x,y,z"
  biome: BiomeType;
  planet: Planet;
  generated: boolean;
}

// ─────────────────────────────────────────────
// Particle / Visual Effects
// ─────────────────────────────────────────────

export type EffectType =
  | 'sparkle'
  | 'explosion'
  | 'heal'
  | 'freeze'
  | 'portal_swirl'
  | 'level_up'
  | 'quest_complete'
  | 'block_break'
  | 'block_place';

export interface VisualEffect {
  id: string;
  type: EffectType;
  position: Vec3;
  color?: [r: number, g: number, b: number];
  duration: number; // ms
  startedAt: number; // ms timestamp
}

// ─────────────────────────────────────────────
// Audio
// ─────────────────────────────────────────────

export type SoundKey =
  | 'block_break'
  | 'block_place'
  | 'attack'
  | 'hurt'
  | 'death'
  | 'level_up'
  | 'quest_complete'
  | 'item_pickup'
  | 'mount_gallop'
  | 'vehicle_engine'
  | 'powerup_collect'
  | 'correct_answer'
  | 'wrong_answer'
  | 'ambient_earth'
  | 'ambient_space';

// ─────────────────────────────────────────────
// Comprehensive Game State
// ─────────────────────────────────────────────

export interface GameState {
  // Player vitals
  hp: number;
  maxHp: number;
  mana: number;
  maxMana: number;
  xp: number;
  level: number;
  gems: number; // premium/bonus currency
  skillPoints: number;
  coins: number; // standard currency for merchants

  // Combat
  activeWeapon: WeaponType;
  weaponsUnlocked: WeaponType[];
  attackCooldownMs: number;
  lastAttackTime: number; // ms timestamp
  isAttacking: boolean;
  isBlocking: boolean;

  // Mount & Vehicle
  activeMounts: MountType[]; // owned mounts; first in list is currently active
  activeMount: MountType | null;
  activeVehicle: VehicleType | null;
  vehicleFuel: number;
  mountsUnlocked: MountType[];
  vehiclesUnlocked: VehicleType[];

  // Inventory & Crafting
  inventory: InventoryItem[];
  maxInventorySlots: number;
  crafted: ItemType[]; // history of item types crafted at least once
  craftingRecipesDiscovered: string[]; // recipe IDs

  // Building
  built: BlockType[]; // types of blocks placed at least once
  blocksPlaced: number;
  blocksDestroyed: number;

  // World
  planet: Planet;
  currentBiome: BiomeType;
  position: Vec3;
  rotation: { yaw: number; pitch: number };
  respawnPoint: Vec3;
  chunksExplored: string[]; // "cx,cz" keys
  biomeVisited: BiomeType[];

  // Quests
  quests: Quest[];
  completedQuestIds: string[];

  // Skills
  skillTree: SkillTree;

  // Education
  answeredQuestions: string[]; // question IDs answered correctly
  wrongAnswers: string[]; // question IDs answered incorrectly (for retry)
  streak: number; // consecutive correct answers (alias: currentStreak)
  currentStreak: number;
  bestStreak: number;
  totalCorrect: number;
  totalQuestions: number;

  // Powerups & Effects
  powerupActive: ActivePowerup | null;
  collectedPowerups: PowerupType[];
  activeEffects: VisualEffect[];

  // NPCs & Social
  npcInteracted: string[]; // NPC IDs already spoken to
  secretsFound: string[]; // secret keys discovered

  // Statistics
  enemiesDefeated: Record<EnemyType, number>;
  distanceTraveled: number;
  playTimeSeconds: number;
  sessionStartTime: number; // ms timestamp
  deaths: number;

  // UI / Meta
  isPaused: boolean;
  isInCutscene: boolean;
  isCrafting: boolean;
  isInDialogue: boolean;
  currentNPCId: string | null;
  currentQuestId: string | null;
  showHUD: boolean;
  showMinimap: boolean;
  muteAudio: boolean;
  musicVolume: number; // 0–1
  sfxVolume: number; // 0–1
}

// ─────────────────────────────────────────────
// Utility / Helper Types
// ─────────────────────────────────────────────

/** A partial game state patch used for incremental updates. */
export type GameStatePatch = Partial<GameState>;

/** Direction constants for movement and block placement. */
export type Direction = 'north' | 'south' | 'east' | 'west' | 'up' | 'down';

/** Generic event emitted from the game loop. */
export interface GameEvent<T = unknown> {
  type: string;
  payload: T;
  timestamp: number; // ms
}

/** Saved snapshot persisted to localStorage / backend. */
export interface SaveData {
  version: string;
  savedAt: number; // ms timestamp
  state: GameState;
  chunks?: Record<string, PlacedBlock[]>; // modified chunk data
}

/** Configuration for spawn rules per biome. */
export interface SpawnRule {
  enemyType: EnemyType;
  biomes: BiomeType[];
  planet: Planet | 'both';
  spawnWeight: number; // relative probability
  maxPerChunk: number;
  minLevel: number; // player level gate
}

/** Leaderboard entry for multiplayer or classroom mode. */
export interface LeaderboardEntry {
  playerId: string;
  displayName: string;
  level: number;
  xp: number;
  streak: number;
  totalCorrect: number;
  rank?: number;
}

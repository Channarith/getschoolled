import type { CraftingRecipe, EnemyConfig, MountStats, NPCDialogue, PowerupConfig, Quest } from './types';

// ─── World ────────────────────────────────────────────────────────────────────
export const WORLD_SIZE = 60;
export const HALF = WORLD_SIZE / 2;
export const GRAVITY_EARTH = 18;
export const GRAVITY_SPACE = 9;

// ─── Crafting Recipes ─────────────────────────────────────────────────────────
export const CRAFTING_RECIPES: CraftingRecipe[] = [
  { id: 'wooden_shield',  name: 'Wooden Shield',    inputs: { wood: 3, stone: 1 },         output: 'sword',          outputQty: 1, icon: '🛡', description: '+20 defense for 30s' },
  { id: 'stone_sword',    name: 'Stone Sword',       inputs: { stone: 4 },                  output: 'wooden_sword',   outputQty: 1, icon: '⚔️',  description: '+15 attack' },
  { id: 'crystal_staff',  name: 'Crystal Staff',     inputs: { crystal: 2, stone: 1 },      output: 'crystal_staff',  outputQty: 1, icon: '🔮', description: 'Ranged magic attack' },
  { id: 'star_blade',     name: 'Star Blade',        inputs: { starmetal: 3 },              output: 'star_blade',     outputQty: 1, icon: '⚡',  description: '+50 attack permanent' },
  { id: 'health_potion',  name: 'Health Potion',     inputs: { herb: 2 },                   output: 'healing_potion', outputQty: 1, icon: '🧪', description: 'Restores 50 HP' },
  { id: 'portal_key',     name: 'Portal Key',        inputs: { crystal: 3, starmetal: 2 },  output: 'portal_key',     outputQty: 1, icon: '🗝️',  description: 'Activates the space portal' },
  { id: 'wooden_wall',    name: 'Wooden Wall',       inputs: { wood: 5 },                   output: 'plank',          outputQty: 3, icon: '🪵', description: 'Building material' },
  { id: 'speed_potion',   name: 'Speed Potion',      inputs: { banana_peel: 1, herb: 1 },   output: 'health_potion',  outputQty: 1, icon: '💨', description: '3x speed for 5s' },
  { id: 'teleport_gem',   name: 'Teleport Gem',      inputs: { crystal: 4 },                output: 'gem_emerald',    outputQty: 1, icon: '💎', description: 'Warp to waypoint' },
  { id: 'moon_brew',      name: 'Moon Brew',         inputs: { moon_dust: 2, herb: 1 },     output: 'mana_potion',    outputQty: 1, icon: '🌙', description: 'Restores 40 mana' },
];

// ─── Mount Stats ──────────────────────────────────────────────────────────────
export const MOUNT_STATS: Record<string, MountStats> = {
  giraffe: {
    type: 'giraffe', speed: 2.5, jumpBoost: 1.3, icon: '🦒',
    displayName: 'Giraffe', special: 'Tall view — see further across the world',
  },
  buffalo: {
    type: 'buffalo', speed: 2.0, jumpBoost: 1.1, icon: '🦬',
    displayName: 'Buffalo', special: 'Charge — can knock enemies back',
  },
  turtle: {
    type: 'turtle', speed: 3.5, jumpBoost: 1.5, icon: '🐢',
    displayName: 'Cosmic Turtle', special: 'Fastest creature in the cosmos — also swims',
  },
  rabbit: {
    type: 'rabbit', speed: 0.8, jumpBoost: 2.0, icon: '🐰',
    displayName: 'Rabbit (Tries Hard)', special: 'Tiny target — very high jump but very slow',
  },
  space_dragon: {
    type: 'space_dragon', speed: 4.0, jumpBoost: 3.0, icon: '🐉',
    displayName: 'Space Dragon', special: 'Brief flight — 3 seconds of air time',
    planet: 'space',
  },
};

// ─── Enemy Configs ────────────────────────────────────────────────────────────
export const ENEMY_CONFIGS: Record<string, EnemyConfig> = {
  goblin: {
    type: 'goblin', hp: 40, speed: 3.2, damage: 8,
    attackRange: 1.8, detectionRange: 12,
    drops: ['wood', 'stone', 'herb'], xpReward: 15,
    color: [0.3, 0.7, 0.2], special: 'Quick small target',
  },
  stone_golem: {
    type: 'stone_golem', hp: 120, speed: 1.5, damage: 25,
    attackRange: 2.5, detectionRange: 8,
    drops: ['stone', 'crystal', 'gem_ruby'], xpReward: 40,
    color: [0.55, 0.55, 0.6], special: 'Ground slam shockwave',
  },
  space_wraith: {
    type: 'space_wraith', hp: 60, speed: 5.0, damage: 15,
    attackRange: 8, detectionRange: 15,
    drops: ['starmetal', 'void_shard', 'moon_dust'], xpReward: 30,
    color: [0.55, 0.0, 0.9], special: 'Ranged projectile', isRanged: true, projectileSpeed: 12,
  },
  crystal_spider: {
    type: 'crystal_spider', hp: 50, speed: 4.0, damage: 12,
    attackRange: 1.5, detectionRange: 10,
    drops: ['crystal', 'gem_sapphire'], xpReward: 20,
    color: [0.0, 0.8, 0.9], special: 'Fast multi-leg movement',
  },
};

// ─── NPC Dialogues ────────────────────────────────────────────────────────────
export const NPC_DIALOGUES: Record<string, NPCDialogue> = {
  wizard: {
    npcId: 'wizard',
    lines: [
      "Greetings, young learner! I am Merlin the Wise.",
      "These lands are filled with knowledge blocks — golden glowing cubes.",
      "Find 3 Star Crystals hidden in the mountains to unlock the Space Portal!",
    ],
    secret: "The turtles are not what they seem. They are cosmic beings who have seen the birth of stars.",
    questId: 'q_crystal_hunter',
  },
  merchant: {
    npcId: 'merchant',
    lines: [
      "Welcome to my shop! I trade in resources and secrets.",
      "Goblins drop wood and stone. Stone Golems drop crystal. Hunt wisely!",
      "I heard there is a hidden cave behind the largest waterfall... treasures inside!",
    ],
    secret: "Behind the giant waterfall to the east lies a cave of crystals. Shhh!",
    questId: 'q_gatherer',
  },
  sage: {
    npcId: 'sage',
    lines: [
      "Young one. To grow in wisdom, one must also grow in strength.",
      "Defeat 5 goblins to prove your worth.",
      "The portal to the stars opens only when 3 Star Crystals align at its base.",
    ],
    secret: "There is a secret biome underground. Dig down at the world center.",
    questId: 'q_explorer',
  },
  space_elder: {
    npcId: 'space_elder',
    lines: [
      "You have crossed the void to reach us. Few have done so.",
      "This world has 3 moons. Each moon grants a different power.",
      "The turtles of your world? They carry star maps in their shells.",
    ],
    secret: "The rings of this planet are made of crushed crystal from a forgotten civilization.",
    questId: 'q_cosmic_voyager',
  },
  tara: {
    npcId: 'tara',
    name: 'Tara',
    type: 'sage',
    color: 0x4caf50,
    planet: 'earth',
    lines: [
      "Hello traveller! I am Tara, keeper of the forest.",
      "The ancient trees here hold many secrets.",
      "Answer my question and I'll share one with you!",
    ],
    secret: "The tallest tree on Earth is a Redwood named Hyperion. It stands over 380 feet tall.",
    questId: 'q_explorer',
  },
  elder: {
    npcId: 'elder',
    name: 'Village Elder',
    type: 'wizard',
    color: 0x8d6e63,
    planet: 'earth',
    lines: [
      "Ah, a young adventurer! I am the Village Elder.",
      "I have lived here for many seasons.",
      "Let me test your knowledge before you continue!",
    ],
    secret: "The capital of Japan is Tokyo — a city of over 13 million people.",
    questId: 'q_gatherer',
  },
};

// ─── Quests ───────────────────────────────────────────────────────────────────
export const DEFAULT_QUESTS: Quest[] = [
  {
    id: 'q_explorer',
    title: 'First Steps',
    description: 'Answer your first 3 questions correctly',
    objective: 'Answer 3 questions',
    target: 3, current: 0, progress: 0, goal: 3, completed: false,
    reward: { xp: 50, items: { wood: 5 } }, npcId: 'sage',
  },
  {
    id: 'q_goblin_slayer',
    title: 'Goblin Slayer',
    description: 'Defeat 5 goblins',
    objective: 'Defeat 5 goblins',
    target: 5, current: 0, progress: 0, goal: 5, completed: false,
    reward: { xp: 80, items: { stone: 10 } }, npcId: 'sage',
  },
  {
    id: 'q_crystal_hunter',
    title: 'Crystal Hunt',
    description: 'Collect 3 Star Crystals hidden in the world',
    objective: 'Find 3 Star Crystals',
    target: 3, current: 0, progress: 0, goal: 3, completed: false,
    reward: { xp: 120, item: 'portal_key' as const }, npcId: 'wizard',
  },
  {
    id: 'q_gatherer',
    title: 'Resource Gatherer',
    description: 'Collect 10 resources',
    objective: 'Pick up 10 resources',
    target: 10, current: 0, progress: 0, goal: 10, completed: false,
    reward: { xp: 60, gems: 15 }, npcId: 'merchant',
  },
  {
    id: 'q_cosmic_voyager',
    title: 'Cosmic Voyager',
    description: 'Reach Planet 2 through the space portal',
    objective: 'Travel to Planet 2',
    target: 1, current: 0, progress: 0, goal: 1, completed: false,
    reward: { xp: 200, gems: 50, mountUnlock: 'space_dragon' }, npcId: 'space_elder',
  },
];

// ─── Powerup Configs ──────────────────────────────────────────────────────────
export const POWERUP_CONFIGS: Record<string, PowerupConfig> = {
  speed:         { type: 'speed',         duration: 5,  icon: '⚡', description: '3× movement speed for 5s', stackable: false },
  freeze:        { type: 'freeze',        duration: 3,  icon: '🧊', description: 'Freezes all nearby enemies for 3s', stackable: false },
  shield:        { type: 'shield',        duration: 4,  icon: '🛡', description: 'Invincible for 4s', stackable: false },
  bomb:          { type: 'bomb',          duration: 0,  icon: '💣', description: 'Instant explosion — damages all nearby enemies' },
  mega_star:     { type: 'mega_star',     duration: 8,  icon: '⭐', description: 'All powerup effects combined for 8s', stackable: false },
  double_damage: { type: 'double_damage', duration: 6,  icon: '🔥', description: '2× damage output for 6s', stackable: false },
};

// ─── Question block positions ─────────────────────────────────────────────────
export const QUESTION_POSITIONS: [number, number][] = [
  [5,8], [12,-4], [-7,7], [-13,-9], [18,2],
  [-15,11], [8,-14], [20,-7], [-4,17], [13,13],
  [-17,-4], [4,-18], [22,14], [-19,14], [-8,-18],
  [16,-16], [-22,-12], [9,22], [-5,-5], [25,5],
  [-25,-8], [0,-25],
];

// ─── Theodore tips ─────────────────────────────────────────────────────────────
export const THEO_TIPS = [
  "Find the ✨ glowing blocks and press E to answer questions!",
  "Correct answers earn XP and gems! 💎",
  "Explore every biome — each has different enemies and questions!",
  "Every mistake is a chance to learn! 💪",
  "You're doing amazing — keep going! 🌟",
  "Try heading North for the snowy mountains! 🏔️",
  "The desert to the south has geography questions! 🌵",
  "Answering 10 in a row starts a streak! 🔥",
  "I'm Theodore, your AI guide. I'll always be nearby! 🤖",
  "Turtles are the fastest creatures in the cosmos 🐢⚡",
  "Press B to toggle building mode! 🏗️",
  "Craft a portal key to travel to Planet 2! 🚀",
];

// ─── XP per level ─────────────────────────────────────────────────────────────
export const XP_PER_LEVEL = [0, 100, 250, 450, 700, 1000, 1350, 1750, 2200, 2700, 3250];

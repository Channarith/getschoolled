// @ts-nocheck
// ============================================================
// CraftingSystem — Three.js RPG world resource pickups, drops,
// and crafting logic.
// ============================================================

import * as THREE from 'three';
import type { ItemType, CraftingRecipe } from './types';
import { CRAFTING_RECIPES } from './constants';

// ─────────────────────────────────────────────
// Internal recipe shape used in constants.ts
// (differs from the CraftingRecipe interface in types.ts)
// ─────────────────────────────────────────────
interface RawRecipe {
  id: string;
  label?: string;
  name?: string;
  ingredients?: Array<{ item: string; qty: number }>;
  inputs?: Partial<Record<string, number>>;
  result?: string;
  output?: string;
  qty?: number;
  outputQty?: number;
  [key: string]: unknown;
}

// ─────────────────────────────────────────────
// Exported interface
// ─────────────────────────────────────────────

export interface ResourcePickup {
  id: string;
  type: ItemType;
  mesh: THREE.Mesh;
  position: THREE.Vector3;
  isPowerup: boolean;
  powerupType?: string;
  animTime: number;
}

// ─────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────

/** Sample the heightmap at world-space (x, z), clamping to valid indices. */
function sampleHeight(
  hmap: number[][],
  x: number,
  z: number,
  worldSize: number,
): number {
  const rows = hmap.length;
  const cols = hmap[0]?.length ?? rows;
  const nx = Math.max(0, Math.min(cols - 1, Math.floor(((x + worldSize / 2) / worldSize) * cols)));
  const nz = Math.max(0, Math.min(rows - 1, Math.floor(((z + worldSize / 2) / worldSize) * rows)));
  return hmap[nz][nx] ?? 0;
}

/** Return a random float in [min, max). */
function rndRange(min: number, max: number): number {
  return min + Math.random() * (max - min);
}

let _pickupCounter = 0;
function nextId(prefix: string): string {
  return `${prefix}_${++_pickupCounter}`;
}

// ─────────────────────────────────────────────
// Geometry / material factories
// ─────────────────────────────────────────────

/** Return a shared material with optional emissive glow. */
function makeMat(
  color: number,
  emissive = 0x000000,
  emissiveIntensity = 0,
): THREE.MeshStandardMaterial {
  return new THREE.MeshStandardMaterial({
    color,
    emissive,
    emissiveIntensity,
    roughness: 0.6,
    metalness: 0.2,
  });
}

// ─────────────────────────────────────────────
// Powerup orb colours / types
// ─────────────────────────────────────────────

const POWERUP_ORBS: Array<{ type: string; color: number; emissive: number }> = [
  { type: 'speed',  color: 0xffe600, emissive: 0xffcc00, },
  { type: 'shield', color: 0x2979ff, emissive: 0x0044ff, },
  { type: 'bomb',   color: 0xff1744, emissive: 0xff4400, },
];

// ─────────────────────────────────────────────
// Resource item definitions
// ─────────────────────────────────────────────

type ResourceDef = {
  type: ItemType;
  color: number;
  emissive: number;
  emissiveIntensity: number;
  geometry: () => THREE.BufferGeometry;
};

const RESOURCE_DEFS: ResourceDef[] = [
  {
    type: 'wood',
    color: 0x8d5524,
    emissive: 0x4a2800,
    emissiveIntensity: 0.1,
    geometry: () => new THREE.BoxGeometry(0.35, 0.35, 0.35),
  },
  {
    type: 'stone',
    color: 0x9e9e9e,
    emissive: 0x555555,
    emissiveIntensity: 0.05,
    geometry: () => new THREE.SphereGeometry(0.2, 6, 6),
  },
  {
    type: 'herb',
    color: 0x43a047,
    emissive: 0x1b5e20,
    emissiveIntensity: 0.2,
    geometry: () => new THREE.ConeGeometry(0.15, 0.35, 6),
  },
  {
    type: 'crystal',
    color: 0x00e5ff,
    emissive: 0x00bcd4,
    emissiveIntensity: 0.5,
    geometry: () => new THREE.OctahedronGeometry(0.2),
  },
];

// Distribution weights (must sum to 1)
const RESOURCE_WEIGHTS = [0.35, 0.30, 0.20, 0.15]; // wood, stone, herb, crystal

function pickWeightedResource(): ResourceDef {
  const r = Math.random();
  let acc = 0;
  for (let i = 0; i < RESOURCE_DEFS.length; i++) {
    acc += RESOURCE_WEIGHTS[i];
    if (r < acc) return RESOURCE_DEFS[i];
  }
  return RESOURCE_DEFS[0];
}

// ─────────────────────────────────────────────
// Internal recipe utilities
// ─────────────────────────────────────────────

function getIngredients(recipe: RawRecipe): Record<string, number> {
  const out: Record<string, number> = {};
  if (Array.isArray(recipe.ingredients)) {
    for (const ing of recipe.ingredients) {
      out[ing.item] = (out[ing.item] ?? 0) + ing.qty;
    }
  } else if (recipe.inputs) {
    for (const [k, v] of Object.entries(recipe.inputs)) {
      if (v != null) out[k] = v;
    }
  }
  return out;
}

function getOutput(recipe: RawRecipe): string {
  return (recipe.result ?? recipe.output ?? '') as string;
}

function getOutputQty(recipe: RawRecipe): number {
  return recipe.qty ?? recipe.outputQty ?? 1;
}

/** Convert a raw constant recipe to the CraftingRecipe interface shape. */
function toPublicRecipe(raw: RawRecipe): CraftingRecipe {
  const inputs = getIngredients(raw) as Partial<Record<ItemType, number>>;
  const output = getOutput(raw) as ItemType;
  return {
    id: raw.id,
    name: (raw.label ?? raw.name ?? raw.id) as string,
    inputs,
    output,
    outputQty: getOutputQty(raw),
    description: (raw.special ?? raw.description ?? '') as string,
    icon: (raw.icon ?? '🔨') as string,
    category: raw.buildingBlock ? 'building' : undefined,
  };
}

// ─────────────────────────────────────────────
// CraftingSystem
// ─────────────────────────────────────────────

export class CraftingSystem {
  private scene: THREE.Scene;
  private hmap: number[][];
  private worldSize: number;

  private pickups: Map<string, ResourcePickup> = new Map();

  constructor(scene: THREE.Scene, hmap: number[][], worldSize: number) {
    this.scene = scene;
    this.hmap = hmap;
    this.worldSize = worldSize;
  }

  // ─────────────────────────────────────────────
  // getPickupMesh
  // ─────────────────────────────────────────────

  getPickupMesh(type: ItemType): THREE.Mesh {
    switch (type) {
      case 'wood':
        return new THREE.Mesh(
          new THREE.BoxGeometry(0.35, 0.35, 0.35),
          makeMat(0x8d5524, 0x4a2800, 0.1),
        );
      case 'stone':
        return new THREE.Mesh(
          new THREE.SphereGeometry(0.2, 6, 6),
          makeMat(0x9e9e9e, 0x555555, 0.05),
        );
      case 'crystal':
        return new THREE.Mesh(
          new THREE.OctahedronGeometry(0.2),
          makeMat(0x00e5ff, 0x00bcd4, 0.5),
        );
      case 'starmetal':
        return new THREE.Mesh(
          new THREE.BoxGeometry(0.3, 0.3, 0.3),
          makeMat(0xffd700, 0xffa000, 0.4),
        );
      case 'herb':
        return new THREE.Mesh(
          new THREE.ConeGeometry(0.15, 0.35, 6),
          makeMat(0x43a047, 0x1b5e20, 0.2),
        );
      case 'star_crystal':
        return new THREE.Mesh(
          new THREE.OctahedronGeometry(0.45),
          new THREE.MeshStandardMaterial({
            color: 0xffffff,
            emissive: 0xaaeeff,
            emissiveIntensity: 1.2,
            roughness: 0.1,
            metalness: 0.8,
            transparent: true,
            opacity: 0.9,
          }),
        );
      default:
        return new THREE.Mesh(
          new THREE.SphereGeometry(0.18, 6, 6),
          makeMat(0xcccccc, 0x888888, 0.1),
        );
    }
  }

  // ─────────────────────────────────────────────
  // clearPickups
  // ─────────────────────────────────────────────

  clearPickups(): void {
    for (const pickup of this.pickups.values()) {
      this.scene.remove(pickup.mesh);
    }
    this.pickups.clear();
  }

  // ─────────────────────────────────────────────
  // spawnResourcePickups
  // ─────────────────────────────────────────────

  spawnResourcePickups(): void {
    this.clearPickups();
    const half = this.worldSize / 2;

    // ── 40 regular resource pickups ──────────────────────────────────────
    const REGULAR_COUNT = 40;
    for (let i = 0; i < REGULAR_COUNT; i++) {
      const x = rndRange(-half * 0.9, half * 0.9);
      const z = rndRange(-half * 0.9, half * 0.9);
      const def = pickWeightedResource();
      this._spawnRegularPickup(def.type, x, z);
    }

    // ── 3 star_crystals on high mountains ────────────────────────────────
    const mountainCandidates = this._findHighPoints(20);
    const starSlots = mountainCandidates.slice(0, 3);
    // Pad with random high-terrain positions if fewer candidates found
    while (starSlots.length < 3) {
      starSlots.push({
        x: rndRange(-half * 0.6, half * 0.6),
        z: rndRange(-half * 0.6, half * 0.6),
      });
    }
    for (const pos of starSlots) {
      this._spawnStarCrystal(pos.x, pos.z);
    }

    // ── 5 powerup orbs ───────────────────────────────────────────────────
    const orbTypes = [...POWERUP_ORBS, ...POWERUP_ORBS.slice(0, 2)]; // 5 orbs, cycling types
    for (let i = 0; i < 5; i++) {
      const x = rndRange(-half * 0.8, half * 0.8);
      const z = rndRange(-half * 0.8, half * 0.8);
      this._spawnPowerupOrb(orbTypes[i], x, z);
    }
  }

  // ─────────────────────────────────────────────
  // update
  // ─────────────────────────────────────────────

  update(
    dt: number,
    playerPosition: THREE.Vector3,
  ): { collected: ItemType | null; powerup: string | null } {
    let collected: ItemType | null = null;
    let powerup: string | null = null;

    const COLLECT_RADIUS = 1.5;

    for (const [id, pickup] of this.pickups) {
      // Animate: rotate + bob
      pickup.animTime += dt;
      pickup.mesh.rotation.y += dt * 1.8;
      pickup.mesh.position.y = pickup.position.y + Math.sin(pickup.animTime * 2.0) * 0.12;

      // Check proximity
      const dx = playerPosition.x - pickup.position.x;
      const dz = playerPosition.z - pickup.position.z;
      const dist2 = dx * dx + dz * dz;

      if (dist2 <= COLLECT_RADIUS * COLLECT_RADIUS) {
        // Auto-collect
        this.scene.remove(pickup.mesh);
        this.pickups.delete(id);

        if (pickup.isPowerup) {
          powerup = pickup.powerupType ?? 'speed';
        } else {
          collected = pickup.type;
        }
        break; // one pickup per frame is enough
      }
    }

    return { collected, powerup };
  }

  // ─────────────────────────────────────────────
  // canCraft
  // ─────────────────────────────────────────────

  canCraft(inventory: Record<ItemType, number>, recipeId: string): boolean {
    const raw = (CRAFTING_RECIPES as RawRecipe[]).find((r) => r.id === recipeId);
    if (!raw) return false;
    const ings = getIngredients(raw);
    for (const [item, qty] of Object.entries(ings)) {
      if ((inventory[item as ItemType] ?? 0) < qty) return false;
    }
    return true;
  }

  // ─────────────────────────────────────────────
  // craft
  // ─────────────────────────────────────────────

  craft(
    inventory: Record<ItemType, number>,
    recipeId: string,
  ): {
    success: boolean;
    result?: ItemType;
    qty?: number;
    consumed?: Record<ItemType, number>;
  } {
    if (!this.canCraft(inventory, recipeId)) {
      return { success: false };
    }

    const raw = (CRAFTING_RECIPES as RawRecipe[]).find((r) => r.id === recipeId)!;
    const ings = getIngredients(raw);
    const consumed: Record<ItemType, number> = {};

    for (const [item, qty] of Object.entries(ings)) {
      const key = item as ItemType;
      inventory[key] = (inventory[key] ?? 0) - qty;
      consumed[key] = qty;
    }

    const resultItem = getOutput(raw) as ItemType;
    const resultQty = getOutputQty(raw);
    inventory[resultItem] = (inventory[resultItem] ?? 0) + resultQty;

    return {
      success: true,
      result: resultItem,
      qty: resultQty,
      consumed,
    };
  }

  // ─────────────────────────────────────────────
  // getAvailableRecipes
  // ─────────────────────────────────────────────

  getAvailableRecipes(inventory: Record<ItemType, number>): CraftingRecipe[] {
    return (CRAFTING_RECIPES as RawRecipe[])
      .filter((r) => this.canCraft(inventory, r.id))
      .map(toPublicRecipe);
  }

  // ─────────────────────────────────────────────
  // spawnDrops
  // ─────────────────────────────────────────────

  spawnDrops(position: THREE.Vector3, drops: ItemType[]): void {
    for (const type of drops) {
      // Scatter drops a little around the death position
      const offsetX = rndRange(-0.8, 0.8);
      const offsetZ = rndRange(-0.8, 0.8);
      const x = position.x + offsetX;
      const z = position.z + offsetZ;
      const y = position.y + 0.3;

      this._addPickup({
        id: nextId('drop'),
        type,
        mesh: this.getPickupMesh(type),
        position: new THREE.Vector3(x, y, z),
        isPowerup: false,
        animTime: Math.random() * Math.PI * 2,
      });
    }
  }

  // ─────────────────────────────────────────────
  // Private helpers
  // ─────────────────────────────────────────────

  private _addPickup(pickup: ResourcePickup): void {
    pickup.mesh.position.copy(pickup.position);
    pickup.mesh.castShadow = true;
    this.scene.add(pickup.mesh);
    this.pickups.set(pickup.id, pickup);
  }

  private _spawnRegularPickup(type: ItemType, x: number, z: number): void {
    const y = sampleHeight(this.hmap, x, z, this.worldSize) + 0.5;
    this._addPickup({
      id: nextId('res'),
      type,
      mesh: this.getPickupMesh(type),
      position: new THREE.Vector3(x, y, z),
      isPowerup: false,
      animTime: Math.random() * Math.PI * 2,
    });
  }

  private _spawnStarCrystal(x: number, z: number): void {
    const y = sampleHeight(this.hmap, x, z, this.worldSize) + 0.7;
    const mesh = this.getPickupMesh('star_crystal');

    // Add a point light to make it really glow
    const light = new THREE.PointLight(0xaaeeff, 1.5, 4);
    light.position.set(0, 0.3, 0);
    mesh.add(light);

    this._addPickup({
      id: nextId('starcrystal'),
      type: 'star_crystal',
      mesh,
      position: new THREE.Vector3(x, y, z),
      isPowerup: false,
      animTime: Math.random() * Math.PI * 2,
    });
  }

  private _spawnPowerupOrb(
    orbDef: { type: string; color: number; emissive: number },
    x: number,
    z: number,
  ): void {
    const y = sampleHeight(this.hmap, x, z, this.worldSize) + 0.6;

    const mesh = new THREE.Mesh(
      new THREE.SphereGeometry(0.28, 12, 12),
      new THREE.MeshStandardMaterial({
        color: orbDef.color,
        emissive: orbDef.emissive,
        emissiveIntensity: 1.0,
        roughness: 0.1,
        metalness: 0.3,
        transparent: true,
        opacity: 0.88,
      }),
    );

    const light = new THREE.PointLight(orbDef.emissive, 1.2, 3.5);
    light.position.set(0, 0, 0);
    mesh.add(light);

    this._addPickup({
      id: nextId('powerup'),
      type: 'crystal', // placeholder ItemType; isPowerup=true takes precedence
      mesh,
      position: new THREE.Vector3(x, y, z),
      isPowerup: true,
      powerupType: orbDef.type,
      animTime: Math.random() * Math.PI * 2,
    });
  }

  /**
   * Sample the heightmap grid and return the top N highest positions
   * so that star_crystals can be placed on mountain peaks.
   */
  private _findHighPoints(n: number): Array<{ x: number; z: number }> {
    const rows = this.hmap.length;
    const cols = this.hmap[0]?.length ?? rows;
    const half = this.worldSize / 2;

    // Collect a sample of grid points with their heights
    const candidates: Array<{ x: number; z: number; h: number }> = [];
    const stride = Math.max(1, Math.floor(rows / 16));

    for (let zi = 0; zi < rows; zi += stride) {
      for (let xi = 0; xi < cols; xi += stride) {
        const h = this.hmap[zi][xi] ?? 0;
        const wx = (xi / cols) * this.worldSize - half;
        const wz = (zi / rows) * this.worldSize - half;
        candidates.push({ x: wx, z: wz, h });
      }
    }

    // Sort descending by height
    candidates.sort((a, b) => b.h - a.h);

    // Take top N, ensuring they aren't too close to each other
    const chosen: Array<{ x: number; z: number }> = [];
    const MIN_SPREAD = this.worldSize * 0.1;

    for (const c of candidates) {
      if (chosen.length >= n) break;
      const tooClose = chosen.some((p) => {
        const dx = p.x - c.x;
        const dz = p.z - c.z;
        return Math.sqrt(dx * dx + dz * dz) < MIN_SPREAD;
      });
      if (!tooClose) {
        chosen.push({ x: c.x, z: c.z });
      }
    }

    return chosen;
  }
}

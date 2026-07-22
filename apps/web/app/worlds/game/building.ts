// ============================================================
// BuildingSystem — Three.js voxel block placement/removal
// ============================================================

import * as THREE from 'three';
import { BlockType } from './types';

// ─────────────────────────────────────────────
// Constants
// ─────────────────────────────────────────────

/** Block types the player can build with. */
export const BUILDABLE_BLOCK_TYPES: BlockType[] = [
  'wood',
  'stone',
  'glass',
  'crystal',
  'starmetal',
  'grass',
];

/**
 * Material cost to place each buildable block type.
 * Keys are ItemType strings drawn from the inventory Record<string, number>.
 */
export const BLOCK_COSTS: Record<BlockType, Record<string, number>> = {
  wood:      { wood: 1 },
  stone:     { stone: 1 },
  glass:     { crystal: 1 },
  crystal:   { crystal: 2 },
  starmetal: { starmetal: 1 },
  grass:     { wood: 1 },
  // Non-buildable types — zero cost (should never be reached via BUILDABLE_BLOCK_TYPES)
  dirt:      {},
  sand:      {},
  snow:      {},
  leaf:      {},
  bedrock:   {},
};

/** Max raycast distance for block placement / removal (world units). */
const RAY_DISTANCE = 10;

// ─────────────────────────────────────────────
// Interfaces
// ─────────────────────────────────────────────

export interface PlacedBlock {
  id: string;
  type: BlockType;
  mesh: THREE.Mesh;
  position: THREE.Vector3;
  gridPos: { x: number; y: number; z: number };
}

// ─────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────

/** Snap a world-space number to the nearest integer grid coordinate. */
function snapToGrid(v: number): number {
  return Math.round(v);
}

/** Build a unique string key for a grid position. */
function gridKey(x: number, y: number, z: number): string {
  return `${x},${y},${z}`;
}

/** Generate a lightweight random ID. */
function uid(): string {
  return Math.random().toString(36).slice(2, 10);
}

// ─────────────────────────────────────────────
// BuildingSystem
// ─────────────────────────────────────────────

export class BuildingSystem {
  placedBlocks: PlacedBlock[] = [];
  selectedBlock: BlockType = 'wood';
  isBuilding: boolean = false;
  previewMesh: THREE.Mesh | null = null;

  private scene: THREE.Scene;
  private raycaster: THREE.Raycaster;

  /** Shared block geometry — reused across all instances. */
  private static readonly BLOCK_GEO = new THREE.BoxGeometry(1, 1, 1);

  /** Cached materials keyed by BlockType. */
  private materialCache = new Map<BlockType, THREE.Material>();

  /** Fast lookup: gridKey → PlacedBlock */
  private gridIndex = new Map<string, PlacedBlock>();

  constructor(scene: THREE.Scene) {
    this.scene = scene;
    this.raycaster = new THREE.Raycaster();
    this.raycaster.far = RAY_DISTANCE;
  }

  // ─────────────────────────────────────────────
  // Mode control
  // ─────────────────────────────────────────────

  /** Toggle building mode on/off. Hides preview mesh when deactivated. */
  toggle(): void {
    this.isBuilding = !this.isBuilding;
    if (!this.isBuilding) {
      this._hidePreview();
    }
  }

  // ─────────────────────────────────────────────
  // Block selection
  // ─────────────────────────────────────────────

  /** Cycle through BUILDABLE_BLOCK_TYPES in the given direction. */
  cycleBlock(direction: 1 | -1): void {
    const idx = BUILDABLE_BLOCK_TYPES.indexOf(this.selectedBlock);
    const next =
      (idx + direction + BUILDABLE_BLOCK_TYPES.length) %
      BUILDABLE_BLOCK_TYPES.length;
    this.selectedBlock = BUILDABLE_BLOCK_TYPES[next];
  }

  setSelectedBlock(type: BlockType): void {
    this.selectedBlock = type;
  }

  // ─────────────────────────────────────────────
  // Preview
  // ─────────────────────────────────────────────

  /**
   * Cast a ray from the camera centre, place a semi-transparent preview cube
   * at the snapped grid position the player is aiming at.
   * Green tint = can place; red = position is occupied.
   */
  updatePreview(camera: THREE.Camera, scene: THREE.Scene): void {
    if (!this.isBuilding) {
      this._hidePreview();
      return;
    }

    const hit = this._raycastBlocks(camera, scene);

    if (!hit) {
      this._hidePreview();
      return;
    }

    const targetPos = this._computePlacementPos(hit);
    if (!targetPos) {
      this._hidePreview();
      return;
    }

    const { x, y, z } = targetPos;
    const occupied = this.gridIndex.has(gridKey(x, y, z));

    // Create or reuse preview mesh
    if (!this.previewMesh) {
      const mat = new THREE.MeshLambertMaterial({
        transparent: true,
        opacity: 0.55,
        depthWrite: false,
      });
      this.previewMesh = new THREE.Mesh(BuildingSystem.BLOCK_GEO, mat);
      this.scene.add(this.previewMesh);
    }

    const mat = this.previewMesh.material as THREE.MeshLambertMaterial;
    mat.color.set(occupied ? 0xff3333 : 0x44ff44);

    this.previewMesh.position.set(x, y, z);
    this.previewMesh.visible = true;
  }

  // ─────────────────────────────────────────────
  // Block placement
  // ─────────────────────────────────────────────

  /**
   * Attempt to place the selected block at the raycast hit position.
   * Deducts material cost from the supplied inventory if successful.
   *
   * @returns `{ placed: true, cost }` on success, `{ placed: false, cost: {} }` on failure.
   */
  placeBlock(
    camera: THREE.Camera,
    scene: THREE.Scene,
    inventory: Record<string, number>,
  ): { placed: boolean; cost: Record<string, number> } {
    const EMPTY = { placed: false, cost: {} };

    if (!this.isBuilding) return EMPTY;

    const hit = this._raycastBlocks(camera, scene);
    if (!hit) return EMPTY;

    const targetPos = this._computePlacementPos(hit);
    if (!targetPos) return EMPTY;

    const { x, y, z } = targetPos;
    const key = gridKey(x, y, z);

    // Cannot place where a block already exists
    if (this.gridIndex.has(key)) return EMPTY;

    // Check and deduct inventory cost
    const cost = BLOCK_COSTS[this.selectedBlock] ?? {};
    for (const [item, qty] of Object.entries(cost)) {
      if ((inventory[item] ?? 0) < qty) return EMPTY;
    }
    for (const [item, qty] of Object.entries(cost)) {
      inventory[item] = (inventory[item] ?? 0) - qty;
    }

    // Build the mesh
    const mat = this.getBlockMaterial(this.selectedBlock);
    const mesh = new THREE.Mesh(BuildingSystem.BLOCK_GEO, mat);
    const worldPos = new THREE.Vector3(x, y, z);
    mesh.position.copy(worldPos);
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    scene.add(mesh);

    const block: PlacedBlock = {
      id: uid(),
      type: this.selectedBlock,
      mesh,
      position: worldPos,
      gridPos: { x, y, z },
    };

    this.placedBlocks.push(block);
    this.gridIndex.set(key, block);

    return { placed: true, cost };
  }

  // ─────────────────────────────────────────────
  // Block removal
  // ─────────────────────────────────────────────

  /**
   * Remove the placed block the player is aiming directly at.
   * Returns the original material cost so the caller can refund the inventory.
   */
  removeBlock(
    camera: THREE.Camera,
    scene: THREE.Scene,
  ): { removed: boolean; returns: Record<string, number> } {
    const EMPTY = { removed: false, returns: {} };

    const hit = this._raycastBlocks(camera, scene);
    if (!hit || !hit.object) return EMPTY;

    // Find which placed block owns this mesh
    const block = this.placedBlocks.find((b) => b.mesh === hit.object);
    if (!block) return EMPTY;

    // Remove from scene & data structures
    scene.remove(block.mesh);
    block.mesh.geometry.dispose();
    // Do NOT dispose shared material from getBlockMaterial cache

    this.placedBlocks = this.placedBlocks.filter((b) => b.id !== block.id);
    this.gridIndex.delete(gridKey(block.gridPos.x, block.gridPos.y, block.gridPos.z));

    const returns = { ...(BLOCK_COSTS[block.type] ?? {}) };
    return { removed: true, returns };
  }

  // ─────────────────────────────────────────────
  // Materials
  // ─────────────────────────────────────────────

  /**
   * Return (and cache) the THREE.Material for a given BlockType.
   *
   * Visual highlights:
   *   crystal   — emissive cyan glow
   *   starmetal — metallic + low roughness
   *   glass     — transparent blue-tint
   */
  getBlockMaterial(type: BlockType): THREE.Material {
    if (this.materialCache.has(type)) {
      return this.materialCache.get(type)!;
    }

    let mat: THREE.Material;

    switch (type) {
      case 'wood':
        mat = new THREE.MeshLambertMaterial({ color: 0x8b5e3c });
        break;

      case 'stone':
        mat = new THREE.MeshLambertMaterial({ color: 0x888888 });
        break;

      case 'grass':
        mat = new THREE.MeshLambertMaterial({ color: 0x4caf50 });
        break;

      case 'glass':
        mat = new THREE.MeshPhongMaterial({
          color: 0xadd8e6,
          transparent: true,
          opacity: 0.35,
          shininess: 120,
          side: THREE.DoubleSide,
          depthWrite: false,
        });
        break;

      case 'crystal':
        mat = new THREE.MeshStandardMaterial({
          color: 0x00e5ff,
          emissive: new THREE.Color(0x00bcd4),
          emissiveIntensity: 0.65,
          roughness: 0.15,
          metalness: 0.2,
          transparent: true,
          opacity: 0.82,
        });
        break;

      case 'starmetal':
        mat = new THREE.MeshStandardMaterial({
          color: 0xb0bec5,
          metalness: 0.95,
          roughness: 0.08,
          envMapIntensity: 1.2,
        });
        break;

      // Fallback for non-buildable block types (dirt, sand, snow, leaf, bedrock)
      case 'dirt':
        mat = new THREE.MeshLambertMaterial({ color: 0x6d4c41 });
        break;
      case 'sand':
        mat = new THREE.MeshLambertMaterial({ color: 0xf4e04d });
        break;
      case 'snow':
        mat = new THREE.MeshLambertMaterial({ color: 0xf5f5f5 });
        break;
      case 'leaf':
        mat = new THREE.MeshLambertMaterial({ color: 0x388e3c });
        break;
      case 'bedrock':
        mat = new THREE.MeshLambertMaterial({ color: 0x212121 });
        break;

      default: {
        const _exhaustive: never = type;
        mat = new THREE.MeshLambertMaterial({ color: 0xffffff });
        void _exhaustive;
      }
    }

    this.materialCache.set(type, mat);
    return mat;
  }

  // ─────────────────────────────────────────────
  // Cleanup
  // ─────────────────────────────────────────────

  /** Remove all placed blocks and dispose GPU resources. */
  dispose(): void {
    for (const block of this.placedBlocks) {
      this.scene.remove(block.mesh);
    }
    this.placedBlocks = [];
    this.gridIndex.clear();

    for (const mat of this.materialCache.values()) {
      mat.dispose();
    }
    this.materialCache.clear();

    this._hidePreview();
    if (this.previewMesh) {
      (this.previewMesh.material as THREE.Material).dispose();
      this.previewMesh = null;
    }
  }

  // ─────────────────────────────────────────────
  // Private helpers
  // ─────────────────────────────────────────────

  /**
   * Fire a ray from the camera centre into the scene.
   * Returns the closest intersection or null.
   */
  private _raycastBlocks(
    camera: THREE.Camera,
    scene: THREE.Scene,
  ): THREE.Intersection | null {
    // NDC (0, 0) = screen centre
    this.raycaster.setFromCamera(new THREE.Vector2(0, 0), camera);

    const candidates = scene.children.filter(
      (obj) => obj !== this.previewMesh && obj instanceof THREE.Mesh,
    ) as THREE.Mesh[];

    const hits = this.raycaster.intersectObjects(candidates, true);
    return hits.length > 0 ? hits[0] : null;
  }

  /**
   * Given a raycast hit on an existing surface, compute the adjacent grid cell
   * where a new block should be placed (face normal offset, snapped to integer).
   */
  private _computePlacementPos(
    hit: THREE.Intersection,
  ): { x: number; y: number; z: number } | null {
    if (!hit.face || !hit.point) return null;

    // Step slightly away from the hit surface along the face normal,
    // then snap to grid so the new block sits in the adjacent cell.
    const normal = hit.face.normal.clone().transformDirection(hit.object.matrixWorld);
    const offset = hit.point.clone().addScaledVector(normal, 0.5);

    return {
      x: snapToGrid(offset.x),
      y: snapToGrid(offset.y),
      z: snapToGrid(offset.z),
    };
  }

  /** Hide and detach the preview mesh without destroying it. */
  private _hidePreview(): void {
    if (this.previewMesh) {
      this.previewMesh.visible = false;
    }
  }
}

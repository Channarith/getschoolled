// @ts-nocheck
// ============================================================
// npcs.ts — NPCManager: spawn, animate, and dialogue system
// ============================================================

import * as THREE from 'three';
import type { NPCType, Planet } from './types';
import { NPC_DIALOGUES } from './constants';

// ─── Public interfaces ────────────────────────────────────────

export interface NPC {
  id: string;
  type: NPCType;
  name: string;
  mesh: THREE.Group;
  position: THREE.Vector3;
  planet: Planet;
  dialogue: string[];
  dialogueIndex: number;
  animTime: number;
  talkBubble: THREE.Mesh | null;
}

// ─── Helpers ──────────────────────────────────────────────────

let _npcCounter = 0;
function nextId(): string {
  return `npc_${++_npcCounter}`;
}

function sampleHeight(hmap: number[][], x: number, z: number, worldSize: number): number {
  const rows = hmap.length;
  if (!rows) return 0;
  const cols = hmap[0]?.length ?? rows;
  const half = worldSize / 2;
  const hx = Math.min(cols - 1, Math.max(0, Math.floor(((x + half) / worldSize) * cols)));
  const hz = Math.min(rows - 1, Math.max(0, Math.floor(((z + half) / worldSize) * rows)));
  return hmap[hz]?.[hx] ?? 0;
}

// Build a simple humanoid NPC mesh
function buildNPCMesh(color: number): THREE.Group {
  const group = new THREE.Group();
  const mat = new THREE.MeshStandardMaterial({ color, roughness: 0.7, metalness: 0.1 });
  const skinMat = new THREE.MeshStandardMaterial({ color: 0xfbbf88, roughness: 0.8 });
  const darkMat = new THREE.MeshStandardMaterial({ color: 0x333333 });

  // Body
  const body = new THREE.Mesh(new THREE.CapsuleGeometry(0.32, 0.6, 4, 8), mat);
  body.position.y = 0.6;
  body.castShadow = true;
  group.add(body);

  // Robe / skirt
  const robe = new THREE.Mesh(
    new THREE.CylinderGeometry(0.42, 0.55, 0.7, 8),
    mat,
  );
  robe.position.y = 0.22;
  robe.castShadow = true;
  group.add(robe);

  // Head
  const head = new THREE.Mesh(new THREE.SphereGeometry(0.28, 8, 6), skinMat);
  head.position.y = 1.22;
  head.castShadow = true;
  group.add(head);

  // Hat / accessory
  const hat = new THREE.Mesh(new THREE.ConeGeometry(0.22, 0.36, 7), darkMat);
  hat.position.y = 1.52;
  hat.castShadow = true;
  group.add(hat);

  // Eyes
  const eyeGeo = new THREE.SphereGeometry(0.045, 5, 5);
  const eyeMat = new THREE.MeshStandardMaterial({ color: 0x111111 });
  const lEye = new THREE.Mesh(eyeGeo, eyeMat);
  lEye.position.set(-0.09, 1.26, 0.25);
  group.add(lEye);
  const rEye = new THREE.Mesh(eyeGeo, eyeMat);
  rEye.position.set(0.09, 1.26, 0.25);
  group.add(rEye);

  return group;
}

// ─── NPCManager ───────────────────────────────────────────────

export class NPCManager {
  private scene: THREE.Scene;
  private planet: Planet;
  private hmap: number[][];
  private worldSize: number;
  private npcs: Map<string, NPC> = new Map();

  constructor(
    scene: THREE.Scene,
    planet: Planet,
    hmap: number[][],
    worldSize: number,
  ) {
    this.scene = scene;
    this.planet = planet;
    this.hmap = hmap;
    this.worldSize = worldSize;
    this._spawnNPCs();
  }

  private _spawnNPCs(): void {
    if (this.planet === 'earth') {
      this._spawnNPC('tara', 8, 6);
      this._spawnNPC('elder', -6, -12);
    } else {
      this._spawnNPC('space_elder', 5, 5);
    }
  }

  private _spawnNPC(configKey: string, wx: number, wz: number): void {
    const cfg = NPC_DIALOGUES[configKey];
    if (!cfg) return;

    const groundY = sampleHeight(this.hmap, wx, wz, this.worldSize);
    const mesh = buildNPCMesh(cfg.color);
    mesh.position.set(wx, groundY, wz);
    this.scene.add(mesh);

    const npc: NPC = {
      id: nextId(),
      type: cfg.type,
      name: cfg.name,
      mesh,
      position: mesh.position.clone(),
      planet: cfg.planet,
      dialogue: [...(cfg.lines ?? [])],
      dialogueIndex: 0,
      animTime: Math.random() * Math.PI * 2,
      talkBubble: null,
    };

    this.npcs.set(npc.id, npc);
  }

  /** Returns NPC within interaction range, or null */
  getNearbyNPC(playerPos: THREE.Vector3, range = 3.0): NPC | null {
    for (const npc of this.npcs.values()) {
      const dx = playerPos.x - npc.position.x;
      const dz = playerPos.z - npc.position.z;
      if (Math.sqrt(dx * dx + dz * dz) <= range) {
        return npc;
      }
    }
    return null;
  }

  /** Returns the next dialogue line for a given NPC */
  advanceDialogue(npcId: string): string | null {
    const npc = this.npcs.get(npcId);
    if (!npc) return null;
    const line = npc.dialogue[npc.dialogueIndex % npc.dialogue.length];
    npc.dialogueIndex = (npc.dialogueIndex + 1) % npc.dialogue.length;
    return line;
  }

  update(dt: number): void {
    for (const npc of this.npcs.values()) {
      npc.animTime += dt;
      // Gentle idle bob
      const groundY = sampleHeight(this.hmap, npc.position.x, npc.position.z, this.worldSize);
      npc.mesh.position.y = groundY + Math.sin(npc.animTime * 1.4) * 0.05;
      // Slowly rotate in place
      npc.mesh.rotation.y += dt * 0.15;
    }
  }

  dispose(): void {
    for (const npc of this.npcs.values()) {
      this.scene.remove(npc.mesh);
    }
    this.npcs.clear();
  }
}

// @ts-nocheck
// ============================================================
// mounts.ts — MountManager: rideable animals for the player
// ============================================================

import * as THREE from 'three';
import type { MountType, Planet } from './types';
import { MOUNT_STATS } from './constants';

// ─── Public interfaces ────────────────────────────────────────

export interface Mount {
  id: string;
  type: MountType;
  mesh: THREE.Group;
  position: THREE.Vector3;
  planet: Planet;
  speedBonus: number;
  animTime: number;
  occupied: boolean;
}

// ─── Helpers ──────────────────────────────────────────────────

let _mountCounter = 0;
function nextId(): string {
  return `mount_${++_mountCounter}`;
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

function buildHorseMesh(color: number): THREE.Group {
  const group = new THREE.Group();
  const mat = new THREE.MeshStandardMaterial({ color, roughness: 0.8, metalness: 0.05 });
  const darkMat = new THREE.MeshStandardMaterial({ color: 0x333333 });

  // Body
  const body = new THREE.Mesh(new THREE.BoxGeometry(1.4, 0.85, 0.65), mat);
  body.position.y = 1.05;
  body.castShadow = true;
  group.add(body);

  // Neck
  const neck = new THREE.Mesh(new THREE.CylinderGeometry(0.2, 0.24, 0.6, 6), mat);
  neck.position.set(0.58, 1.52, 0);
  neck.rotation.z = -0.38;
  neck.castShadow = true;
  group.add(neck);

  // Head
  const head = new THREE.Mesh(new THREE.BoxGeometry(0.46, 0.32, 0.32), mat);
  head.position.set(0.84, 1.72, 0);
  head.castShadow = true;
  group.add(head);

  // Legs
  const legGeo = new THREE.CylinderGeometry(0.1, 0.09, 0.75, 5);
  const legPositions = [
    [-0.42, 0.62, 0.22], [-0.42, 0.62, -0.22],
    [0.42, 0.62, 0.22], [0.42, 0.62, -0.22],
  ];
  for (const [lx, ly, lz] of legPositions) {
    const leg = new THREE.Mesh(legGeo, darkMat);
    leg.position.set(lx, ly, lz);
    leg.castShadow = true;
    group.add(leg);
  }

  // Mane
  const mane = new THREE.Mesh(new THREE.BoxGeometry(0.08, 0.55, 0.12), darkMat);
  mane.position.set(0.6, 1.75, 0);
  group.add(mane);

  return group;
}

function buildWolfMesh(color: number): THREE.Group {
  const group = new THREE.Group();
  const mat = new THREE.MeshStandardMaterial({ color, roughness: 0.9 });
  const eyeMat = new THREE.MeshStandardMaterial({ color: 0xffeb3b, emissive: 0xffeb3b, emissiveIntensity: 0.5 });

  // Body
  const body = new THREE.Mesh(new THREE.BoxGeometry(1.1, 0.55, 0.5), mat);
  body.position.y = 0.72;
  body.castShadow = true;
  group.add(body);

  // Head
  const head = new THREE.Mesh(new THREE.BoxGeometry(0.42, 0.36, 0.38), mat);
  head.position.set(0.62, 0.88, 0);
  head.castShadow = true;
  group.add(head);

  // Snout
  const snout = new THREE.Mesh(new THREE.BoxGeometry(0.28, 0.2, 0.26), mat);
  snout.position.set(0.84, 0.8, 0);
  group.add(snout);

  // Eyes
  const eyeGeo = new THREE.SphereGeometry(0.06, 5, 5);
  const lEye = new THREE.Mesh(eyeGeo, eyeMat);
  lEye.position.set(0.66, 0.94, 0.16);
  group.add(lEye);
  const rEye = new THREE.Mesh(eyeGeo, eyeMat);
  rEye.position.set(0.66, 0.94, -0.16);
  group.add(rEye);

  // Legs
  const legGeo = new THREE.CylinderGeometry(0.09, 0.07, 0.55, 5);
  const legMat = new THREE.MeshStandardMaterial({ color: 0x455a64 });
  const legPos = [
    [-0.32, 0.47, 0.18], [-0.32, 0.47, -0.18],
    [0.32, 0.47, 0.18], [0.32, 0.47, -0.18],
  ];
  for (const [lx, ly, lz] of legPos) {
    const leg = new THREE.Mesh(legGeo, legMat);
    leg.position.set(lx, ly, lz);
    group.add(leg);
  }

  // Tail
  const tail = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.08, 0.5, 5), mat);
  tail.position.set(-0.6, 0.88, 0);
  tail.rotation.z = 0.6;
  group.add(tail);

  return group;
}

function buildSpaceDragonMesh(color: number): THREE.Group {
  const group = new THREE.Group();
  const mat = new THREE.MeshStandardMaterial({
    color,
    roughness: 0.3,
    metalness: 0.5,
    emissive: color,
    emissiveIntensity: 0.2,
  });
  const wingMat = new THREE.MeshStandardMaterial({
    color: 0x7b1fa2,
    transparent: true,
    opacity: 0.75,
    side: THREE.DoubleSide,
  });

  // Body
  const body = new THREE.Mesh(new THREE.CapsuleGeometry(0.4, 1.2, 5, 8), mat);
  body.rotation.z = Math.PI / 2;
  body.position.y = 0.8;
  body.castShadow = true;
  group.add(body);

  // Head
  const head = new THREE.Mesh(new THREE.SphereGeometry(0.36, 8, 6), mat);
  head.position.set(0.9, 1.0, 0);
  head.castShadow = true;
  group.add(head);

  // Wings
  const wingGeo = new THREE.ConeGeometry(1.2, 0.08, 4);
  const leftWing = new THREE.Mesh(wingGeo, wingMat);
  leftWing.position.set(0, 1.0, 0.9);
  leftWing.rotation.set(Math.PI / 2, 0, -0.3);
  group.add(leftWing);

  const rightWing = new THREE.Mesh(wingGeo, wingMat);
  rightWing.position.set(0, 1.0, -0.9);
  rightWing.rotation.set(-Math.PI / 2, 0, -0.3);
  group.add(rightWing);

  // Tail spines
  const spineGeo = new THREE.ConeGeometry(0.08, 0.4, 4);
  for (let i = 0; i < 4; i++) {
    const spine = new THREE.Mesh(spineGeo, mat);
    spine.position.set(-0.35 - i * 0.28, 1.0, 0);
    spine.rotation.z = 0.5;
    group.add(spine);
  }

  // Glowing eyes
  const eyeGeo = new THREE.SphereGeometry(0.08, 6, 6);
  const eyeMat = new THREE.MeshStandardMaterial({
    color: 0x00e5ff,
    emissive: 0x00e5ff,
    emissiveIntensity: 1.5,
  });
  const lEye = new THREE.Mesh(eyeGeo, eyeMat);
  lEye.position.set(0.94, 1.08, 0.16);
  group.add(lEye);
  const rEye = new THREE.Mesh(eyeGeo, eyeMat);
  rEye.position.set(0.94, 1.08, -0.16);
  group.add(rEye);

  // Add a point light glow
  const glow = new THREE.PointLight(0x9c27b0, 0.8, 4.0);
  glow.position.set(0, 1.0, 0);
  group.add(glow);

  return group;
}

function buildMeshForType(type: MountType, color: number): THREE.Group {
  switch (type) {
    case 'giraffe':        return buildHorseMesh(color);
    case 'buffalo':         return buildWolfMesh(color);
    case 'space_dragon': return buildSpaceDragonMesh(color);
  }
}

// ─── MountManager ─────────────────────────────────────────────

export class MountManager {
  private scene: THREE.Scene;
  private planet: Planet;
  private hmap: number[][];
  private worldSize: number;
  private mounts: Map<string, Mount> = new Map();
  private _mountedId: string | null = null;

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
    this._spawnMounts();
  }

  private _spawnMounts(): void {
    if (this.planet === 'earth') {
      this._spawn('giraffe', 14, -8);
      this._spawn('buffalo', -18, 5);
    } else {
      this._spawn('space_dragon', -10, 8);
    }
  }

  private _spawn(type: MountType, wx: number, wz: number): void {
    const cfg = MOUNT_STATS[type];
    const groundY = sampleHeight(this.hmap, wx, wz, this.worldSize);
    const mesh = buildMeshForType(type, cfg.color);
    mesh.position.set(wx, groundY, wz);
    this.scene.add(mesh);

    const mount: Mount = {
      id: nextId(),
      type,
      mesh,
      position: mesh.position.clone(),
      planet: cfg.planet,
      speedBonus: cfg.speedBonus,
      animTime: Math.random() * Math.PI * 2,
      occupied: false,
    };

    this.mounts.set(mount.id, mount);
  }

  /** Returns mount within interaction range, or null */
  getNearbyMount(playerPos: THREE.Vector3, range = 2.5): Mount | null {
    for (const mount of this.mounts.values()) {
      if (mount.occupied) continue;
      const dx = playerPos.x - mount.position.x;
      const dz = playerPos.z - mount.position.z;
      if (Math.sqrt(dx * dx + dz * dz) <= range) {
        return mount;
      }
    }
    return null;
  }

  getMountedMount(): Mount | null {
    if (!this._mountedId) return null;
    return this.mounts.get(this._mountedId) ?? null;
  }

  isMounted(): boolean {
    return this._mountedId !== null;
  }

  mount(mountId: string): boolean {
    const m = this.mounts.get(mountId);
    if (!m || m.occupied) return false;
    m.occupied = true;
    this._mountedId = mountId;
    return true;
  }

  dismount(): void {
    if (!this._mountedId) return;
    const m = this.mounts.get(this._mountedId);
    if (m) m.occupied = false;
    this._mountedId = null;
  }

  getSpeedBonus(): number {
    const m = this.getMountedMount();
    return m ? m.speedBonus : 1.0;
  }

  update(dt: number, playerPos: THREE.Vector3, _isMounted: boolean): void {
    for (const mount of this.mounts.values()) {
      mount.animTime += dt;

      if (mount.occupied && mount.id === this._mountedId) {
        // Follow player
        mount.mesh.position.set(playerPos.x, playerPos.y - 0.5, playerPos.z);
        mount.position.copy(mount.mesh.position);
      } else {
        // Idle animation: gentle bob
        const groundY = sampleHeight(this.hmap, mount.position.x, mount.position.z, this.worldSize);
        mount.mesh.position.y = groundY + Math.sin(mount.animTime * 1.8) * 0.06;
        mount.mesh.rotation.y += dt * 0.1;
      }
    }
  }

  dispose(): void {
    for (const mount of this.mounts.values()) {
      this.scene.remove(mount.mesh);
    }
    this.mounts.clear();
  }
}

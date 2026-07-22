// @ts-nocheck
// ============================================================
// enemies.ts — EnemyManager for Three.js RPG
// Handles spawn, AI states, combat, and mesh lifecycle.
// ============================================================

import * as THREE from 'three';
import type { EnemyType, EnemyState, ItemType, Planet } from './types';
import { ENEMY_CONFIGS } from './constants';

// ─────────────────────────────────────────────
// Public interfaces
// ─────────────────────────────────────────────

export interface Enemy {
  id: string;
  type: EnemyType;
  mesh: THREE.Group;
  healthBar: THREE.Mesh;
  state: EnemyState;
  hp: number;
  maxHp: number;
  position: THREE.Vector3;
  velocity: THREE.Vector3;
  spawnPosition: THREE.Vector3;
  lastAttackTime: number;
  patrolTarget: THREE.Vector3;
  aggroTime: number;
  projectiles: THREE.Mesh[];
}

// ─────────────────────────────────────────────
// Internal helpers
// ─────────────────────────────────────────────

interface RuntimeConfig {
  attackRange: number;
  detectionRange: number;
  attackCooldown: number; // seconds
  retreatHpRatio: number; // fraction of maxHp at which enemy retreats
  patrolRadius: number;
}

interface Shockwave {
  mesh: THREE.Mesh;
  origin: THREE.Vector3;
  radius: number;
  maxRadius: number;
  elapsed: number; // seconds
  duration: number;
}

// Supplement ENEMY_CONFIGS (which stores display/drop data) with combat ranges
const RUNTIME: Record<EnemyType, RuntimeConfig> = {
  goblin:         { attackRange: 1.5,  detectionRange: 12, attackCooldown: 1.2, retreatHpRatio: 0.15, patrolRadius: 8  },
  stone_golem:    { attackRange: 2.5,  detectionRange: 10, attackCooldown: 2.5, retreatHpRatio: 0.10, patrolRadius: 5  },
  space_wraith:   { attackRange: 15.0, detectionRange: 18, attackCooldown: 1.8, retreatHpRatio: 0.20, patrolRadius: 12 },
  crystal_spider: { attackRange: 1.8,  detectionRange: 14, attackCooldown: 1.0, retreatHpRatio: 0.15, patrolRadius: 10 },
};

// Projectile speed (world units / second)
const PROJECTILE_SPEED = 12;
const PROJECTILE_LIFETIME = 3; // seconds

// Track projectile metadata separately (not on Enemy interface)
const projectileMeta = new WeakMap<THREE.Mesh, { velocity: THREE.Vector3; age: number }>();

// ─────────────────────────────────────────────
// Mesh builders
// ─────────────────────────────────────────────

function buildGoblinMesh(): THREE.Group {
  const group = new THREE.Group();
  const green = new THREE.MeshStandardMaterial({ color: 0x4caf50 });
  const dark  = new THREE.MeshStandardMaterial({ color: 0x2e7d32 });
  const white = new THREE.MeshStandardMaterial({ color: 0xffffff });
  const black = new THREE.MeshStandardMaterial({ color: 0x111111 });

  // Body
  const body = new THREE.Mesh(new THREE.BoxGeometry(0.55, 0.65, 0.45), green);
  body.position.y = 0.325;
  body.castShadow = true;
  group.add(body);

  // Head
  const head = new THREE.Mesh(new THREE.BoxGeometry(0.5, 0.45, 0.45), dark);
  head.position.y = 0.875;
  head.castShadow = true;
  group.add(head);

  // Eyes (left, right)
  const eyeGeo = new THREE.SphereGeometry(0.07, 6, 6);
  const leftEye = new THREE.Mesh(eyeGeo, white);
  leftEye.position.set(-0.12, 0.9, 0.23);
  group.add(leftEye);
  const rightEye = new THREE.Mesh(eyeGeo, white);
  rightEye.position.set(0.12, 0.9, 0.23);
  group.add(rightEye);

  // Pupils
  const pupilGeo = new THREE.SphereGeometry(0.035, 5, 5);
  const leftPupil = new THREE.Mesh(pupilGeo, black);
  leftPupil.position.set(-0.12, 0.9, 0.29);
  group.add(leftPupil);
  const rightPupil = new THREE.Mesh(pupilGeo, black);
  rightPupil.position.set(0.12, 0.9, 0.29);
  group.add(rightPupil);

  // Arms
  const armGeo = new THREE.BoxGeometry(0.15, 0.5, 0.15);
  const leftArm = new THREE.Mesh(armGeo, green);
  leftArm.position.set(-0.38, 0.35, 0);
  group.add(leftArm);
  const rightArm = new THREE.Mesh(armGeo, green);
  rightArm.position.set(0.38, 0.35, 0);
  group.add(rightArm);

  return group;
}

function buildStoneGolemMesh(): THREE.Group {
  const group = new THREE.Group();
  const gray     = new THREE.MeshStandardMaterial({ color: 0x9e9e9e, roughness: 0.9 });
  const darkGray = new THREE.MeshStandardMaterial({ color: 0x616161, roughness: 0.95 });
  const orange   = new THREE.MeshStandardMaterial({ color: 0xff6f00, emissive: new THREE.Color(0xff4500), emissiveIntensity: 0.6 });

  // Body (large box)
  const body = new THREE.Mesh(new THREE.BoxGeometry(1.4, 1.8, 1.0), gray);
  body.position.y = 0.9;
  body.castShadow = true;
  group.add(body);

  // Head
  const head = new THREE.Mesh(new THREE.BoxGeometry(1.1, 0.9, 0.9), darkGray);
  head.position.y = 2.25;
  head.castShadow = true;
  group.add(head);

  // Eyes (glowing orange)
  const eyeGeo = new THREE.SphereGeometry(0.12, 7, 7);
  const leftEye = new THREE.Mesh(eyeGeo, orange);
  leftEye.position.set(-0.25, 2.3, 0.46);
  group.add(leftEye);
  const rightEye = new THREE.Mesh(eyeGeo, orange);
  rightEye.position.set(0.25, 2.3, 0.46);
  group.add(rightEye);

  // Arms (thick blocks)
  const armGeo = new THREE.BoxGeometry(0.5, 1.2, 0.5);
  const leftArm = new THREE.Mesh(armGeo, gray);
  leftArm.position.set(-1.0, 0.9, 0);
  group.add(leftArm);
  const rightArm = new THREE.Mesh(armGeo, gray);
  rightArm.position.set(1.0, 0.9, 0);
  group.add(rightArm);

  // Fists
  const fistGeo = new THREE.BoxGeometry(0.55, 0.55, 0.55);
  const leftFist = new THREE.Mesh(fistGeo, darkGray);
  leftFist.position.set(-1.0, 0.2, 0);
  group.add(leftFist);
  const rightFist = new THREE.Mesh(fistGeo, darkGray);
  rightFist.position.set(1.0, 0.2, 0);
  group.add(rightFist);

  return group;
}

function buildSpaceWraithMesh(): THREE.Group {
  const group = new THREE.Group();
  const ghostMat = new THREE.MeshStandardMaterial({
    color: 0x7c4dff,
    emissive: new THREE.Color(0x5e35b1),
    emissiveIntensity: 0.8,
    transparent: true,
    opacity: 0.65,
    side: THREE.DoubleSide,
  });
  const eyeMat = new THREE.MeshStandardMaterial({
    color: 0xe040fb,
    emissive: new THREE.Color(0xce93d8),
    emissiveIntensity: 1.0,
  });

  // Body (elongated sphere)
  const body = new THREE.Mesh(new THREE.SphereGeometry(0.55, 10, 10, 0, Math.PI * 2, 0, Math.PI * 0.7), ghostMat);
  body.scale.y = 1.6;
  body.position.y = 0;
  body.castShadow = false;
  group.add(body);

  // Wispy tail
  const tailGeo = new THREE.ConeGeometry(0.3, 0.9, 6);
  const tail = new THREE.Mesh(tailGeo, ghostMat);
  tail.position.y = -0.5;
  tail.rotation.x = Math.PI; // point downward
  group.add(tail);

  // Eyes
  const eyeGeo = new THREE.SphereGeometry(0.1, 7, 7);
  const leftEye = new THREE.Mesh(eyeGeo, eyeMat);
  leftEye.position.set(-0.18, 0.2, 0.5);
  group.add(leftEye);
  const rightEye = new THREE.Mesh(eyeGeo, eyeMat);
  rightEye.position.set(0.18, 0.2, 0.5);
  group.add(rightEye);

  return group;
}

function buildCrystalSpiderMesh(): THREE.Group {
  const group = new THREE.Group();
  const teal    = new THREE.MeshStandardMaterial({ color: 0x00bcd4, emissive: new THREE.Color(0x006064), emissiveIntensity: 0.3 });
  const crystal = new THREE.MeshStandardMaterial({ color: 0x00e5ff, transparent: true, opacity: 0.85 });

  // Body
  const body = new THREE.Mesh(new THREE.SphereGeometry(0.4, 10, 8), teal);
  body.position.y = 0.4;
  body.castShadow = true;
  group.add(body);

  // Abdomen
  const abdomen = new THREE.Mesh(new THREE.SphereGeometry(0.5, 10, 8), teal);
  abdomen.scale.set(1, 0.75, 1.3);
  abdomen.position.set(0, 0.35, -0.55);
  abdomen.castShadow = true;
  group.add(abdomen);

  // 8 legs
  const legGeo = new THREE.CylinderGeometry(0.04, 0.025, 0.9, 5);
  const angles = [-75, -45, -20, 15, 75 + 180, 45 + 180, 20 + 180, -15 + 180].map(d => (d * Math.PI) / 180);

  angles.forEach((angle, i) => {
    const leg = new THREE.Mesh(legGeo, crystal);
    const side = i < 4 ? -1 : 1;
    leg.rotation.z = side * Math.PI * 0.38;
    leg.rotation.y = angle;
    const xOff = side * 0.38;
    const zOff = (i % 4) * 0.18 - 0.27;
    leg.position.set(xOff, 0.3, zOff);
    group.add(leg);
  });

  // Eyes (multiple, small)
  const eyeGeo = new THREE.SphereGeometry(0.055, 5, 5);
  const eyeMat = new THREE.MeshStandardMaterial({ color: 0xff1744, emissive: new THREE.Color(0xff1744), emissiveIntensity: 0.8 });
  for (let i = -1; i <= 1; i += 2) {
    for (let j = 0; j <= 1; j++) {
      const eye = new THREE.Mesh(eyeGeo, eyeMat);
      eye.position.set(i * (0.1 + j * 0.15), 0.55 - j * 0.1, 0.37 - j * 0.04);
      group.add(eye);
    }
  }

  return group;
}

// Shared health-bar geometry/material (reused per enemy)
const HEALTH_BAR_BG_MAT = new THREE.MeshBasicMaterial({ color: 0x333333 });
const HEALTH_BAR_MAT     = new THREE.MeshBasicMaterial({ color: 0x00e676, side: THREE.DoubleSide });

function buildHealthBar(): { bg: THREE.Mesh; bar: THREE.Mesh } {
  const bgGeo  = new THREE.PlaneGeometry(1.0, 0.1);
  const barGeo = new THREE.PlaneGeometry(1.0, 0.1);
  const bg  = new THREE.Mesh(bgGeo,  HEALTH_BAR_BG_MAT.clone());
  const bar = new THREE.Mesh(barGeo, HEALTH_BAR_MAT.clone());
  bar.position.z = 0.001; // slightly in front of bg
  bg.add(bar);
  return { bg, bar };
}

function buildEnemyMesh(type: EnemyType): THREE.Group {
  switch (type) {
    case 'goblin':         return buildGoblinMesh();
    case 'stone_golem':    return buildStoneGolemMesh();
    case 'space_wraith':   return buildSpaceWraithMesh();
    case 'crystal_spider': return buildCrystalSpiderMesh();
  }
}

function buildProjectileMesh(type: EnemyType): THREE.Mesh {
  // Only space_wraith uses projectiles currently; others could extend here
  const geo  = new THREE.SphereGeometry(0.2, 8, 8);
  const mat  = new THREE.MeshStandardMaterial({
    color: 0xce93d8,
    emissive: new THREE.Color(0xab47bc),
    emissiveIntensity: 1.2,
    transparent: true,
    opacity: 0.9,
  });
  return new THREE.Mesh(geo, mat);
}

// ─────────────────────────────────────────────
// Shockwave ring helper
// ─────────────────────────────────────────────

function buildShockwaveMesh(origin: THREE.Vector3): Shockwave {
  const geo = new THREE.RingGeometry(0, 0.1, 32);
  const mat = new THREE.MeshBasicMaterial({ color: 0x78909c, transparent: true, opacity: 0.8, side: THREE.DoubleSide });
  const mesh = new THREE.Mesh(geo, mat);
  mesh.rotation.x = -Math.PI / 2;
  mesh.position.copy(origin);
  mesh.position.y += 0.05;
  return { mesh, origin: origin.clone(), radius: 0, maxRadius: 6, elapsed: 0, duration: 0.7 };
}

// ─────────────────────────────────────────────
// ID generator
// ─────────────────────────────────────────────

let _idCounter = 0;
function genId(prefix: string): string {
  return `${prefix}_${++_idCounter}_${Date.now()}`;
}

// ─────────────────────────────────────────────
// Spawn position helpers
// ─────────────────────────────────────────────

/** Random position in a disc around a center point. */
function randomInDisc(cx: number, cz: number, radius: number): [number, number] {
  const angle = Math.random() * Math.PI * 2;
  const r     = Math.sqrt(Math.random()) * radius;
  return [cx + Math.cos(angle) * r, cz + Math.sin(angle) * r];
}

// Approximate biome centres for Planet 1 spawn clustering (world centred at 0,0)
const PLANET1_BIOME_ZONES = {
  grassland: { cx:   0, cz:   0 },
  forest:    { cx:  20, cz: -20 },
  crystal:   { cx: -20, cz:  20 },
  stone:     { cx:  25, cz:  25 },
} as const;

const PLANET2_BIOME_ZONES = {
  void:    { cx:  0, cz:  0 },
  crystal: { cx: 15, cz: 15 },
} as const;

// ─────────────────────────────────────────────
// EnemyManager
// ─────────────────────────────────────────────

export class EnemyManager {
  readonly enemies: Enemy[] = [];

  private readonly scene: THREE.Scene;
  private readonly planet: Planet;
  private readonly hmap: number[][];
  private readonly worldSize: number;

  /** Active shockwave rings from Stone Golem slams. */
  private readonly shockwaves: Shockwave[] = [];

  constructor(scene: THREE.Scene, planet: Planet, hmap: number[][], worldSize: number) {
    this.scene     = scene;
    this.planet    = planet;
    this.hmap      = hmap;
    this.worldSize = worldSize;
  }

  // ── Height-map sampling ──────────────────────────────────────────────────

  private sampleHeight(x: number, z: number): number {
    if (!this.hmap.length || !this.hmap[0].length) return 0;
    const rows = this.hmap.length;
    const cols = this.hmap[0].length;
    const half = this.worldSize / 2;
    const hx   = Math.min(cols - 1, Math.max(0, Math.floor(((x + half) / this.worldSize) * cols)));
    const hz   = Math.min(rows - 1, Math.max(0, Math.floor(((z + half) / this.worldSize) * rows)));
    return this.hmap[hz]?.[hx] ?? 0;
  }

  // ── Enemy factory ────────────────────────────────────────────────────────

  private createEnemy(type: EnemyType, wx: number, wz: number): Enemy {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const cfg  = ENEMY_CONFIGS[type] as any;
    const maxHp: number = cfg.hp ?? 50;

    const mesh = buildEnemyMesh(type);

    // Health bar
    const { bg: hbBg, bar: hbBar } = buildHealthBar();
    const hbHeight = type === 'stone_golem' ? 3.2 : type === 'goblin' ? 1.6 : 1.8;
    hbBg.position.set(0, hbHeight, 0);
    hbBg.renderOrder = 999;
    (hbBg.material as THREE.MeshBasicMaterial).depthTest = false;
    (hbBar.material as THREE.MeshBasicMaterial).depthTest = false;
    mesh.add(hbBg);

    const wy = this.sampleHeight(wx, wz);
    // Space wraith hovers
    const yOffset = type === 'space_wraith' ? 1.2 : 0;

    mesh.position.set(wx, wy + yOffset, wz);

    this.scene.add(mesh);

    const pos = mesh.position.clone();

    const enemy: Enemy = {
      id:             genId(type),
      type,
      mesh,
      healthBar:      hbBar,
      state:          'idle',
      hp:             maxHp,
      maxHp,
      position:       pos,
      velocity:       new THREE.Vector3(),
      spawnPosition:  pos.clone(),
      lastAttackTime: 0,
      patrolTarget:   pos.clone(),
      aggroTime:      0,
      projectiles:    [],
    };

    return enemy;
  }

  // ── Spawn ────────────────────────────────────────────────────────────────

  spawnEnemies(): void {
    if (this.planet === 'earth') {
      this._spawnPlanet1();
    } else {
      this._spawnPlanet2();
    }
  }

  private _spawnPlanet1(): void {
    // 8 goblins — grassland / forest zones
    const goblinZones = [PLANET1_BIOME_ZONES.grassland, PLANET1_BIOME_ZONES.forest];
    for (let i = 0; i < 8; i++) {
      const zone = goblinZones[i % goblinZones.length];
      const [x, z] = randomInDisc(zone.cx, zone.cz, 18);
      this.enemies.push(this.createEnemy('goblin', x, z));
    }

    // 3 stone golems — stone / elevated zone
    for (let i = 0; i < 3; i++) {
      const zone = PLANET1_BIOME_ZONES.stone;
      const [x, z] = randomInDisc(zone.cx, zone.cz, 12);
      this.enemies.push(this.createEnemy('stone_golem', x, z));
    }

    // 4 crystal spiders — crystal biome
    for (let i = 0; i < 4; i++) {
      const zone = PLANET1_BIOME_ZONES.crystal;
      const [x, z] = randomInDisc(zone.cx, zone.cz, 14);
      this.enemies.push(this.createEnemy('crystal_spider', x, z));
    }
  }

  private _spawnPlanet2(): void {
    // 6 space wraiths — void zone
    for (let i = 0; i < 6; i++) {
      const zone = PLANET2_BIOME_ZONES.void;
      const [x, z] = randomInDisc(zone.cx, zone.cz, 22);
      this.enemies.push(this.createEnemy('space_wraith', x, z));
    }

    // 3 crystal spiders — crystal zone
    for (let i = 0; i < 3; i++) {
      const zone = PLANET2_BIOME_ZONES.crystal;
      const [x, z] = randomInDisc(zone.cx, zone.cz, 12);
      this.enemies.push(this.createEnemy('crystal_spider', x, z));
    }
  }

  // ── Update ───────────────────────────────────────────────────────────────

  update(
    dt: number,
    playerPosition: THREE.Vector3,
    playerHP: number,
  ): { damage: number; effects: string[] } {
    let totalDamage = 0;
    const effects: string[] = [];
    const now = performance.now() / 1000; // seconds

    const toRemove: string[] = [];

    for (const enemy of this.enemies) {
      if (enemy.state === 'dead') continue;

      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const cfg     = ENEMY_CONFIGS[enemy.type] as any;
      const runtime = RUNTIME[enemy.type];
      const speed: number  = cfg.speed ?? 3;
      const damage: number = cfg.damage ?? 8;

      const distToPlayer = enemy.position.distanceTo(playerPosition);

      // ── State machine ──────────────────────────────────────────────────
      const prevState = enemy.state;

      if (enemy.state !== 'dead') {
        // Retreat when HP is critically low
        if (enemy.hp < enemy.maxHp * runtime.retreatHpRatio && enemy.state !== 'retreat') {
          enemy.state = 'retreat';
        }
        // Chase if player close enough and not retreating
        else if (distToPlayer <= runtime.detectionRange && enemy.state !== 'retreat') {
          if (distToPlayer <= runtime.attackRange) {
            enemy.state = 'attack';
          } else {
            enemy.state = 'chase';
            enemy.aggroTime = now;
          }
        }
        // Lose aggro after 6 seconds out of range
        else if (enemy.state === 'chase' || enemy.state === 'attack') {
          if (distToPlayer > runtime.detectionRange * 1.3) {
            if (now - enemy.aggroTime > 6) {
              enemy.state = 'patrol';
              this._pickPatrolTarget(enemy);
            }
          }
        }
        // Idle → start patrol after short delay
        else if (enemy.state === 'idle') {
          if (Math.random() < dt * 0.4) {
            enemy.state = 'patrol';
            this._pickPatrolTarget(enemy);
          }
        }
      }

      // ── Movement ───────────────────────────────────────────────────────
      switch (enemy.state) {
        case 'patrol':
          this._moveToward(enemy, enemy.patrolTarget, speed * 0.5, dt);
          if (enemy.position.distanceTo(enemy.patrolTarget) < 1.0) {
            this._pickPatrolTarget(enemy);
          }
          break;

        case 'chase':
          this._moveToward(enemy, playerPosition, speed, dt);
          break;

        case 'attack':
          // Stay at attack range — inch forward only if outside melee
          if (distToPlayer > runtime.attackRange * 0.7) {
            this._moveToward(enemy, playerPosition, speed * 0.4, dt);
          }
          break;

        case 'retreat':
          // Move away from player
          {
            const away = enemy.position.clone().sub(playerPosition).normalize();
            this._applyVelocity(enemy, away, speed * 0.7, dt);
          }
          break;

        default:
          break;
      }

      // ── Attack logic ───────────────────────────────────────────────────
      if (enemy.state === 'attack') {
        const timeSinceAttack = now - enemy.lastAttackTime;

        if (timeSinceAttack >= runtime.attackCooldown) {
          if (distToPlayer <= runtime.attackRange) {

            if (enemy.type === 'space_wraith') {
              // Ranged projectile
              this._fireProjectile(enemy, playerPosition);
              effects.push('space_wraith_shot');
            } else if (enemy.type === 'stone_golem') {
              // Ground slam — shockwave ring
              totalDamage += damage;
              this._triggerShockwave(enemy);
              effects.push('golem_slam');
            } else {
              // Melee
              totalDamage += damage;
              effects.push(`${enemy.type}_hit`);
            }

            enemy.lastAttackTime = now;
          }
        }
      }

      // ── Projectile update (space wraith) ──────────────────────────────
      if (enemy.type === 'space_wraith') {
        const survivingProjectiles: THREE.Mesh[] = [];

        for (const proj of enemy.projectiles) {
          const meta = projectileMeta.get(proj);
          if (!meta) continue;

          meta.age += dt;
          if (meta.age > PROJECTILE_LIFETIME) {
            this.scene.remove(proj);
            this._disposeMesh(proj);
            continue;
          }

          proj.position.addScaledVector(meta.velocity, dt);

          // Hit test against player
          if (proj.position.distanceTo(playerPosition) < 0.6) {
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            totalDamage += (ENEMY_CONFIGS['space_wraith'] as any).damage ?? 15;
            effects.push('wraith_projectile_hit');
            this.scene.remove(proj);
            this._disposeMesh(proj);
            continue;
          }

          survivingProjectiles.push(proj);
        }

        enemy.projectiles = survivingProjectiles;
      }

      // ── Floating health bar — always face camera (billboard Y-axis) ───
      // The group's world rotation is updated by the caller (game loop);
      // here we just sync the bar fill.
      this._updateHealthBar(enemy);

      // ── Sync mesh position ────────────────────────────────────────────
      enemy.mesh.position.copy(enemy.position);

      // Face movement direction (yaw only)
      if (enemy.velocity.lengthSq() > 0.001) {
        const angle = Math.atan2(enemy.velocity.x, enemy.velocity.z);
        enemy.mesh.rotation.y = angle;
      }

      // Space wraith: bob up/down and keep hovered
      if (enemy.type === 'space_wraith') {
        const baseY = this.sampleHeight(enemy.position.x, enemy.position.z) + 1.2;
        enemy.mesh.position.y = baseY + Math.sin(now * 2 + enemy.id.length) * 0.25;
        enemy.position.y = enemy.mesh.position.y;
      } else {
        // Snap to terrain
        const terrainY = this.sampleHeight(enemy.position.x, enemy.position.z);
        enemy.position.y = terrainY;
        enemy.mesh.position.y = terrainY;
      }
    }

    // ── Shockwave update ─────────────────────────────────────────────────
    for (let i = this.shockwaves.length - 1; i >= 0; i--) {
      const sw = this.shockwaves[i];
      sw.elapsed += dt;
      const t = sw.elapsed / sw.duration;

      if (t >= 1) {
        this.scene.remove(sw.mesh);
        this._disposeMesh(sw.mesh);
        this.shockwaves.splice(i, 1);
        continue;
      }

      sw.radius = sw.maxRadius * t;
      sw.mesh.scale.setScalar(sw.radius);
      const mat = sw.mesh.material as THREE.MeshBasicMaterial;
      mat.opacity = 0.8 * (1 - t);

      // Damage player if shockwave reaches them
      const distToOrigin = playerPosition.distanceTo(sw.origin);
      if (Math.abs(distToOrigin - sw.radius) < 0.8) {
        // Only trigger once per sweep (checked via a small window)
      }
    }

    // ── Remove dead enemies ───────────────────────────────────────────────
    for (const id of toRemove) {
      this.removeEnemy(id);
    }

    return { damage: totalDamage, effects };
  }

  // ── Movement helpers ─────────────────────────────────────────────────────

  private _moveToward(enemy: Enemy, target: THREE.Vector3, speed: number, dt: number): void {
    const dir = target.clone().sub(enemy.position);
    dir.y = 0;
    const len = dir.length();
    if (len < 0.01) return;
    dir.divideScalar(len);
    this._applyVelocity(enemy, dir, speed, dt);
  }

  private _applyVelocity(enemy: Enemy, dir: THREE.Vector3, speed: number, dt: number): void {
    enemy.velocity.copy(dir).multiplyScalar(speed);
    enemy.position.addScaledVector(enemy.velocity, dt);

    // Clamp within world bounds
    const half = this.worldSize / 2;
    enemy.position.x = Math.max(-half, Math.min(half, enemy.position.x));
    enemy.position.z = Math.max(-half, Math.min(half, enemy.position.z));
  }

  private _pickPatrolTarget(enemy: Enemy): void {
    const runtime = RUNTIME[enemy.type];
    const [x, z]  = randomInDisc(enemy.spawnPosition.x, enemy.spawnPosition.z, runtime.patrolRadius);
    const y        = this.sampleHeight(x, z);
    enemy.patrolTarget.set(x, y, z);
  }

  // ── Ability helpers ──────────────────────────────────────────────────────

  private _fireProjectile(enemy: Enemy, target: THREE.Vector3): void {
    const proj = buildProjectileMesh(enemy.type);
    proj.position.copy(enemy.position).add(new THREE.Vector3(0, 0.5, 0));

    const dir = target.clone().sub(proj.position);
    dir.normalize().multiplyScalar(PROJECTILE_SPEED);

    projectileMeta.set(proj, { velocity: dir, age: 0 });

    this.scene.add(proj);
    enemy.projectiles.push(proj);
  }

  private _triggerShockwave(enemy: Enemy): void {
    const sw = buildShockwaveMesh(enemy.position);
    this.scene.add(sw.mesh);
    this.shockwaves.push(sw);
  }

  // ── Health bar ───────────────────────────────────────────────────────────

  private _updateHealthBar(enemy: Enemy): void {
    const ratio = Math.max(0, enemy.hp / enemy.maxHp);
    enemy.healthBar.scale.x = ratio;
    enemy.healthBar.position.x = (ratio - 1) / 2; // anchor left

    // Colour: green → yellow → red
    const mat = enemy.healthBar.material as THREE.MeshBasicMaterial;
    if (ratio > 0.5) {
      mat.color.setHSL(0.33, 1, 0.45); // green
    } else if (ratio > 0.25) {
      mat.color.setHSL(0.12, 1, 0.50); // yellow-orange
    } else {
      mat.color.setHSL(0, 1, 0.45); // red
    }
  }

  // ── Public API ───────────────────────────────────────────────────────────

  applyDamage(
    enemyId: string,
    damage: number,
  ): { killed: boolean; drops: ItemType[]; xp: number } | null {
    const enemy = this.enemies.find(e => e.id === enemyId);
    if (!enemy || enemy.state === 'dead') return null;

    enemy.hp = Math.max(0, enemy.hp - damage);
    this._updateHealthBar(enemy);

    if (enemy.hp <= 0) {
      enemy.state = 'dead';

      const drops  = this._rollDrops(enemy.type);
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const xp: number = (ENEMY_CONFIGS[enemy.type] as any).xp ?? 10;

      // Delay mesh removal one frame to allow death VFX
      setTimeout(() => this.removeEnemy(enemyId), 0);

      return { killed: true, drops, xp };
    }

    // Chase player when hit
    if (enemy.state === 'idle' || enemy.state === 'patrol') {
      enemy.state    = 'chase';
      enemy.aggroTime = performance.now() / 1000;
    }

    return { killed: false, drops: [], xp: 0 };
  }

  removeEnemy(enemyId: string): void {
    const idx = this.enemies.findIndex(e => e.id === enemyId);
    if (idx === -1) return;

    const enemy = this.enemies[idx];

    // Clean up projectiles
    for (const proj of enemy.projectiles) {
      this.scene.remove(proj);
      this._disposeMesh(proj);
    }
    enemy.projectiles = [];

    // Remove mesh from scene
    this.scene.remove(enemy.mesh);
    enemy.mesh.traverse(child => {
      if ((child as THREE.Mesh).isMesh) {
        this._disposeMesh(child as THREE.Mesh);
      }
    });

    this.enemies.splice(idx, 1);
  }

  getVisibleEnemies(cameraFrustum: THREE.Frustum): Enemy[] {
    return this.enemies.filter(enemy => {
      if (enemy.state === 'dead') return false;
      // Use a bounding sphere centred on the enemy position with generous radius
      const sphere = new THREE.Sphere(enemy.position, 3);
      return cameraFrustum.intersectsSphere(sphere);
    });
  }

  dispose(): void {
    // Remove all enemies
    for (const enemy of [...this.enemies]) {
      this.removeEnemy(enemy.id);
    }

    // Remove active shockwaves
    for (const sw of this.shockwaves) {
      this.scene.remove(sw.mesh);
      this._disposeMesh(sw.mesh);
    }
    this.shockwaves.length = 0;
  }

  // ── Private utilities ────────────────────────────────────────────────────

  private _rollDrops(type: EnemyType): ItemType[] {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const cfg   = ENEMY_CONFIGS[type] as any;
    const drops: ItemType[] = [];

    if (!Array.isArray(cfg.drops)) return drops;

    for (const entry of cfg.drops as [string, number][]) {
      const [item, prob] = entry;
      if (Math.random() < prob) {
        drops.push(item as ItemType);
      }
    }

    return drops;
  }

  private _disposeMesh(mesh: THREE.Mesh | THREE.Object3D): void {
    const m = mesh as THREE.Mesh;
    if (m.geometry) m.geometry.dispose();
    if (m.material) {
      if (Array.isArray(m.material)) {
        m.material.forEach(mat => mat.dispose());
      } else {
        m.material.dispose();
      }
    }
  }
}

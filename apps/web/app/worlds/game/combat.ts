// ============================================================
// combat.ts — CombatSystem: hit effects, damage numbers, VFX
// ============================================================

import * as THREE from 'three';
import type { WeaponType } from './types';

// ─── Public interfaces ────────────────────────────────────────

export interface DamageNumber {
  mesh: THREE.Mesh;
  velocity: THREE.Vector3;
  age: number;
  lifetime: number;
}

export interface HitEffect {
  particles: THREE.Points;
  age: number;
  lifetime: number;
}

export interface AttackInfo {
  type: 'punch' | 'kick' | 'flip' | 'magic' | 'staff_blast';
  weapon: WeaponType;
  damage: number;
  range: number;
  knockback: number;
  color: number;
}

// ─── Attack definitions ───────────────────────────────────────

const ATTACK_DEFS: Record<string, AttackInfo> = {
  punch: {
    type: 'punch',
    weapon: 'fists',
    damage: 12,
    range: 2.0,
    knockback: 2.0,
    color: 0xfbbf24,
  },
  kick: {
    type: 'kick',
    weapon: 'fists',
    damage: 20,
    range: 2.2,
    knockback: 4.0,
    color: 0xf97316,
  },
  flip: {
    type: 'flip',
    weapon: 'fists',
    damage: 30,
    range: 2.5,
    knockback: 5.0,
    color: 0xec4899,
  },
  magic: {
    type: 'magic',
    weapon: 'staff',
    damage: 35,
    range: 12.0,
    knockback: 3.0,
    color: 0x8b5cf6,
  },
  staff_blast: {
    type: 'staff_blast',
    weapon: 'staff',
    damage: 25,
    range: 10.0,
    knockback: 2.5,
    color: 0x06b6d4,
  },
};

// ─── CombatSystem ─────────────────────────────────────────────

export class CombatSystem {
  private scene: THREE.Scene;
  private sun: THREE.DirectionalLight;
  private hitEffects: HitEffect[] = [];
  private damageNumbers: DamageNumber[] = [];
  private _projectiles: Array<{
    mesh: THREE.Mesh;
    velocity: THREE.Vector3;
    age: number;
    damage: number;
    color: number;
  }> = [];

  // Shared geometry for damage number sprites (text quads)
  private _dmgGeo = new THREE.PlaneGeometry(0.5, 0.2);

  constructor(scene: THREE.Scene, sun: THREE.DirectionalLight) {
    this.scene = scene;
    this.sun = sun;
  }

  // ── Attack execution ──────────────────────────────────────────

  /** Perform a melee or ranged attack from the player.
   *  Returns attack info to be used for hit detection. */
  startAttack(
    type: 'punch' | 'kick' | 'flip' | 'magic',
    playerPos: THREE.Vector3,
    playerDir: THREE.Vector3,
    weapon: WeaponType,
  ): AttackInfo {
    let key: string = type;
    if (type === 'magic' && weapon === 'staff') key = 'magic';

    const info = ATTACK_DEFS[key] ?? ATTACK_DEFS['punch'];

    // Melee VFX: short particle burst in front of player
    this._spawnHitBurst(
      playerPos.clone().addScaledVector(playerDir, 1.2),
      info.color,
      8,
    );

    // For magic/staff: spawn a projectile
    if (type === 'magic' && weapon === 'staff') {
      this._spawnProjectile(
        playerPos.clone().addScaledVector(playerDir, 1.0),
        playerDir.clone().normalize(),
        info.damage,
        info.color,
      );
    }

    // Screen flash: briefly boost sun intensity
    const originalIntensity = this.sun.intensity;
    this.sun.intensity = originalIntensity + 0.5;
    setTimeout(() => { this.sun.intensity = originalIntensity; }, 80);

    return info;
  }

  private _spawnProjectile(
    origin: THREE.Vector3,
    dir: THREE.Vector3,
    damage: number,
    color: number,
  ): void {
    const geo = new THREE.SphereGeometry(0.22, 7, 7);
    const mat = new THREE.MeshStandardMaterial({
      color,
      emissive: color,
      emissiveIntensity: 2.0,
      transparent: true,
      opacity: 0.9,
    });
    const mesh = new THREE.Mesh(geo, mat);
    mesh.position.copy(origin);
    this.scene.add(mesh);

    // Point light glow
    const glow = new THREE.PointLight(color, 1.5, 4);
    mesh.add(glow);

    this._projectiles.push({
      mesh,
      velocity: dir.clone().multiplyScalar(18),
      age: 0,
      damage,
      color,
    });
  }

  // ── Hit registration ──────────────────────────────────────────

  /** Register a hit: spawn effects and floating damage number */
  registerHit(
    hitPos: THREE.Vector3,
    damage: number,
    color: number,
    isCritical = false,
  ): void {
    this._spawnHitBurst(hitPos, color, 16);
    this._spawnDamageNumber(hitPos, damage, isCritical, color);
  }

  private _spawnHitBurst(pos: THREE.Vector3, color: number, count: number): void {
    const positions = new Float32Array(count * 3);
    const velocities: THREE.Vector3[] = [];

    for (let i = 0; i < count; i++) {
      positions[i * 3]     = pos.x;
      positions[i * 3 + 1] = pos.y;
      positions[i * 3 + 2] = pos.z;
      velocities.push(new THREE.Vector3(
        (Math.random() - 0.5) * 5,
        Math.random() * 4 + 1,
        (Math.random() - 0.5) * 5,
      ));
    }

    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));

    const mat = new THREE.PointsMaterial({
      color,
      size: 0.14,
      transparent: true,
      opacity: 1.0,
      depthWrite: false,
    });
    const particles = new THREE.Points(geo, mat);
    this.scene.add(particles);

    this.hitEffects.push({
      particles,
      age: 0,
      lifetime: 0.55,
    });

    // Store velocities on geometry for animation
    (geo as any)._velocities = velocities;
  }

  private _spawnDamageNumber(
    pos: THREE.Vector3,
    damage: number,
    isCritical: boolean,
    color: number,
  ): void {
    // Simple colored plane as damage indicator (real text would need a texture/canvas)
    const w = isCritical ? 0.7 : 0.45;
    const geo = new THREE.PlaneGeometry(w, w * 0.4);
    const mat = new THREE.MeshBasicMaterial({
      color: isCritical ? 0xff1744 : color,
      transparent: true,
      opacity: 1.0,
      depthWrite: false,
      side: THREE.DoubleSide,
    });
    const mesh = new THREE.Mesh(geo, mat);
    mesh.position.copy(pos).add(new THREE.Vector3(0, 0.8, 0));
    this.scene.add(mesh);

    this.damageNumbers.push({
      mesh,
      velocity: new THREE.Vector3(
        (Math.random() - 0.5) * 0.5,
        2.0 + (isCritical ? 1.5 : 0),
        (Math.random() - 0.5) * 0.5,
      ),
      age: 0,
      lifetime: isCritical ? 1.4 : 0.9,
    });
  }

  // ── Projectile hit check ──────────────────────────────────────

  /** Check if any projectile hits any target. Returns hits. */
  checkProjectileHits(
    targets: Array<{ position: THREE.Vector3; radius: number; id: string }>,
  ): Array<{ targetId: string; damage: number; pos: THREE.Vector3 }> {
    const results: Array<{ targetId: string; damage: number; pos: THREE.Vector3 }> = [];

    for (const proj of this._projectiles) {
      for (const target of targets) {
        if (proj.mesh.position.distanceTo(target.position) <= target.radius) {
          results.push({
            targetId: target.id,
            damage: proj.damage,
            pos: proj.mesh.position.clone(),
          });
          // Mark projectile for removal
          proj.age = 999;
          this.registerHit(proj.mesh.position.clone(), proj.damage, proj.color);
          break;
        }
      }
    }

    return results;
  }

  // ── Update ────────────────────────────────────────────────────

  update(dt: number): void {
    // Update hit particle bursts
    this.hitEffects = this.hitEffects.filter(fx => {
      fx.age += dt;
      const frac = fx.age / fx.lifetime;
      const pos = fx.particles.geometry.attributes.position as THREE.BufferAttribute;
      const vels = (fx.particles.geometry as any)._velocities as THREE.Vector3[];

      if (vels) {
        for (let i = 0; i < vels.length; i++) {
          (pos.array as Float32Array)[i * 3]     += vels[i].x * dt;
          (pos.array as Float32Array)[i * 3 + 1] += (vels[i].y - 5 * frac) * dt;
          (pos.array as Float32Array)[i * 3 + 2] += vels[i].z * dt;
        }
        pos.needsUpdate = true;
      }

      (fx.particles.material as THREE.PointsMaterial).opacity = Math.max(0, 1 - frac);

      if (fx.age >= fx.lifetime) {
        this.scene.remove(fx.particles);
        fx.particles.geometry.dispose();
        return false;
      }
      return true;
    });

    // Update damage numbers
    this.damageNumbers = this.damageNumbers.filter(dn => {
      dn.age += dt;
      dn.mesh.position.addScaledVector(dn.velocity, dt);
      dn.velocity.y -= 2 * dt; // slow deceleration
      (dn.mesh.material as THREE.MeshBasicMaterial).opacity = Math.max(0, 1 - dn.age / dn.lifetime);
      // Billboard to camera
      dn.mesh.lookAt(dn.mesh.position.clone().add(new THREE.Vector3(0, 0, 1)));

      if (dn.age >= dn.lifetime) {
        this.scene.remove(dn.mesh);
        dn.mesh.geometry.dispose();
        (dn.mesh.material as THREE.Material).dispose();
        return false;
      }
      return true;
    });

    // Update projectiles
    this._projectiles = this._projectiles.filter(proj => {
      proj.age += dt;
      if (proj.age > 3.0) {
        this.scene.remove(proj.mesh);
        proj.mesh.geometry.dispose();
        (proj.mesh.material as THREE.Material).dispose();
        return false;
      }
      proj.mesh.position.addScaledVector(proj.velocity, dt);
      proj.mesh.rotation.y += dt * 4;
      (proj.mesh.material as THREE.MeshStandardMaterial).opacity = Math.max(0, 1 - proj.age / 3.0);
      return true;
    });
  }

  /** Spawn a shockwave ring at the given position (for golem slams, etc.) */
  spawnShockwave(pos: THREE.Vector3, color = 0xfbbf24): void {
    const ringGeo = new THREE.RingGeometry(0.1, 0.4, 24);
    const ringMat = new THREE.MeshBasicMaterial({
      color,
      transparent: true,
      opacity: 0.9,
      side: THREE.DoubleSide,
      depthWrite: false,
    });
    const ring = new THREE.Mesh(ringGeo, ringMat);
    ring.rotation.x = -Math.PI / 2;
    ring.position.copy(pos);
    ring.position.y += 0.05;
    this.scene.add(ring);

    let age = 0;
    const maxR = 5.0;
    const dur = 0.6;

    const animate = (dt: number): boolean => {
      age += dt;
      const t = age / dur;
      const scale = t * maxR / 0.1;
      ring.scale.setScalar(scale);
      (ring.material as THREE.MeshBasicMaterial).opacity = (1 - t) * 0.8;
      if (age >= dur) {
        this.scene.remove(ring);
        ring.geometry.dispose();
        (ring.material as THREE.Material).dispose();
        return false;
      }
      return true;
    };

    // We add it to a temporary list that WorldGame iterates
    this._shockwaveAnimators.push(animate);
  }

  private _shockwaveAnimators: Array<(dt: number) => boolean> = [];

  /** Call from WorldGame to drain one frame of shockwave animations */
  tickShockwaves(dt: number): void {
    this._shockwaveAnimators = this._shockwaveAnimators.filter(fn => fn(dt));
  }

  dispose(): void {
    for (const fx of this.hitEffects) {
      this.scene.remove(fx.particles);
      fx.particles.geometry.dispose();
    }
    for (const dn of this.damageNumbers) {
      this.scene.remove(dn.mesh);
      dn.mesh.geometry.dispose();
      (dn.mesh.material as THREE.Material).dispose();
    }
    for (const proj of this._projectiles) {
      this.scene.remove(proj.mesh);
      proj.mesh.geometry.dispose();
      (proj.mesh.material as THREE.Material).dispose();
    }
    this._dmgGeo.dispose();
    this.hitEffects = [];
    this.damageNumbers = [];
    this._projectiles = [];
    this._shockwaveAnimators = [];
  }
}

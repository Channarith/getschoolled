// ============================================================
// planets.ts — PlanetSystem: environment, sky, moons, portals
// ============================================================

import * as THREE from 'three';
import type { Planet } from './types';

// ─── Public interfaces ────────────────────────────────────────

export interface PortalState {
  mesh: THREE.Group;
  active: boolean;
  position: THREE.Vector3;
  rotationSpeed: number;
}

// ─── PlanetSystem ─────────────────────────────────────────────

export class PlanetSystem {
  private scene: THREE.Scene;
  private worldSize: number;
  private _skyMesh: THREE.Mesh | null = null;
  private _skyMat: THREE.ShaderMaterial | null = null;
  private _moons: THREE.Mesh[] = [];
  private _suns: THREE.Mesh[] = [];
  private _saturnRing: THREE.Mesh | null = null;
  private _portal: PortalState | null = null;
  private _ambientParticles: THREE.Points | null = null;
  private _time = 0;

  constructor(scene: THREE.Scene, worldSize: number) {
    this.scene = scene;
    this.worldSize = worldSize;
  }

  // ── Planet 1: Earth ───────────────────────────────────────────

  setupPlanet1(scene: THREE.Scene, hmap: number[][]): void {
    this._clearExtras();

    // Earth sky gradient
    this._skyMat = new THREE.ShaderMaterial({
      side: THREE.BackSide,
      uniforms: {
        uTime: { value: 0 },
        uTopColor: { value: new THREE.Color(0x1565c0) },
        uBottomColor: { value: new THREE.Color(0x87ceeb) },
      },
      vertexShader: `
        varying vec3 vPos;
        void main() {
          vPos = position;
          gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }
      `,
      fragmentShader: `
        varying vec3 vPos;
        uniform vec3 uTopColor;
        uniform vec3 uBottomColor;
        uniform float uTime;
        void main() {
          float t = clamp((vPos.y + 50.0) / 150.0, 0.0, 1.0);
          vec3 sky = mix(uBottomColor, uTopColor, t);
          // Subtle sun halo
          vec3 sunDir = normalize(vec3(0.6, 0.8, 0.5));
          float sun = pow(max(0.0, dot(normalize(vPos), sunDir)), 80.0);
          sky += vec3(1.0, 0.95, 0.7) * sun * 0.8;
          gl_FragColor = vec4(sky, 1.0);
        }
      `,
    });
    this._skyMesh = new THREE.Mesh(new THREE.SphereGeometry(190, 16, 8), this._skyMat);
    scene.add(this._skyMesh);

    scene.fog = new THREE.FogExp2(0xa8d8ea, 0.013);
    scene.background = new THREE.Color(0x87ceeb);

    // Add sparse clouds
    const cloudMat = new THREE.MeshStandardMaterial({
      color: 0xffffff,
      transparent: true,
      opacity: 0.72,
      roughness: 1,
    });
    for (let i = 0; i < 12; i++) {
      const angle = (i / 12) * Math.PI * 2;
      const radius = 80 + Math.sin(i * 5.3) * 30;
      const cx = Math.cos(angle) * radius;
      const cz = Math.sin(angle) * radius;
      const cy = 35 + Math.sin(i * 2.7) * 8;
      const cloud = new THREE.Mesh(new THREE.SphereGeometry(6 + i % 3 * 3, 6, 4), cloudMat);
      cloud.scale.set(1.8, 0.6, 1.2);
      cloud.position.set(cx, cy, cz);
      scene.add(cloud);
      this._moons.push(cloud); // reuse array for clouds
    }

    // Portal (Earth side)
    this._portal = this._createPortal(scene, 24, 0, 0);
  }

  // ── Planet 2: Space ───────────────────────────────────────────

  setupPlanet2(scene: THREE.Scene, hmap: number[][]): void {
    this._clearExtras();

    // Space nebula sky
    this._skyMat = new THREE.ShaderMaterial({
      side: THREE.BackSide,
      uniforms: {
        uTime: { value: 0 },
      },
      vertexShader: `
        varying vec3 vPos;
        void main() {
          vPos = position;
          gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }
      `,
      fragmentShader: `
        varying vec3 vPos;
        uniform float uTime;
        // Simple pseudo-random
        float hash(float n) { return fract(sin(n) * 43758.5453); }
        void main() {
          vec3 dir = normalize(vPos);
          // Deep space base
          vec3 col = vec3(0.01, 0.0, 0.05);
          // Stars
          float star = step(0.998, hash(dot(floor(dir * 180.0), vec3(127.1, 311.7, 74.4))));
          col += vec3(star) * 1.2;
          // Nebula colour bands
          float nb = sin(dir.x * 4.0 + uTime * 0.02) * cos(dir.z * 3.0 + uTime * 0.015);
          col += vec3(0.12, 0.0, 0.28) * clamp(nb * 0.5 + 0.5, 0.0, 1.0);
          col += vec3(0.0, 0.06, 0.2) * clamp(-nb * 0.5 + 0.5, 0.0, 1.0);
          gl_FragColor = vec4(col, 1.0);
        }
      `,
    });
    this._skyMesh = new THREE.Mesh(new THREE.SphereGeometry(190, 24, 12), this._skyMat);
    scene.add(this._skyMesh);

    scene.fog = new THREE.FogExp2(0x050010, 0.006);
    scene.background = new THREE.Color(0x010008);

    // 3 Moons
    const moonColors = [0xe0e0e0, 0xb3a78b, 0xc7a060];
    const moonDistances = [55, 80, 100];
    const moonSizes = [5.5, 3.8, 8.0];
    for (let i = 0; i < 3; i++) {
      const moonMat = new THREE.MeshStandardMaterial({
        color: moonColors[i],
        roughness: 0.9,
        metalness: 0.0,
      });
      const moon = new THREE.Mesh(new THREE.SphereGeometry(moonSizes[i], 10, 8), moonMat);
      const angle = (i / 3) * Math.PI * 2 + 0.4;
      moon.position.set(
        Math.cos(angle) * moonDistances[i],
        20 + i * 8,
        Math.sin(angle) * moonDistances[i],
      );
      scene.add(moon);
      this._moons.push(moon);
    }

    // 2 Suns (binary star system)
    const sunMat1 = new THREE.MeshStandardMaterial({
      color: 0xffdd00,
      emissive: 0xffaa00,
      emissiveIntensity: 2.0,
      roughness: 0.5,
    });
    const sun1 = new THREE.Mesh(new THREE.SphereGeometry(12, 12, 8), sunMat1);
    sun1.position.set(150, 60, 80);
    scene.add(sun1);
    this._suns.push(sun1);
    scene.add(new THREE.PointLight(0xffcc44, 1.2, 300));

    const sunMat2 = new THREE.MeshStandardMaterial({
      color: 0xff6600,
      emissive: 0xff4400,
      emissiveIntensity: 2.5,
      roughness: 0.5,
    });
    const sun2 = new THREE.Mesh(new THREE.SphereGeometry(7, 10, 8), sunMat2);
    sun2.position.set(-120, 40, -100);
    scene.add(sun2);
    this._suns.push(sun2);
    const redSunLight = new THREE.PointLight(0xff6600, 0.8, 250);
    redSunLight.position.set(-120, 40, -100);
    scene.add(redSunLight);

    // Saturn-like rings
    const ringGeo = new THREE.RingGeometry(35, 60, 64);
    const ringMat = new THREE.MeshStandardMaterial({
      color: 0xc4a259,
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0.55,
      roughness: 0.8,
    });
    this._saturnRing = new THREE.Mesh(ringGeo, ringMat);
    this._saturnRing.position.set(120, -5, -60);
    this._saturnRing.rotation.x = Math.PI / 4;
    scene.add(this._saturnRing);

    // Add the large "planet" body the ring surrounds
    const planetMat = new THREE.MeshStandardMaterial({
      color: 0xd4aa60,
      roughness: 0.6,
    });
    const planetBody = new THREE.Mesh(new THREE.SphereGeometry(22, 14, 10), planetMat);
    planetBody.position.set(120, -5, -60);
    scene.add(planetBody);

    // Ambient particle field (space dust)
    this._spawnSpaceDust(scene);

    // Portal (Space side — return portal)
    this._portal = this._createPortal(scene, -24, 0, 0, 0x00e5ff);
  }

  private _createPortal(
    scene: THREE.Scene,
    x: number,
    y: number,
    z: number,
    color = 0x6366f1,
  ): PortalState {
    const group = new THREE.Group();

    // Outer ring
    const ringMat = new THREE.MeshStandardMaterial({
      color,
      emissive: color,
      emissiveIntensity: 0.8,
      metalness: 0.9,
      roughness: 0.2,
    });
    const outerRing = new THREE.Mesh(new THREE.TorusGeometry(2.4, 0.22, 10, 48), ringMat);
    group.add(outerRing);

    // Inner swirl (portal vortex)
    const vortexMat = new THREE.MeshStandardMaterial({
      color,
      emissive: color,
      emissiveIntensity: 1.5,
      transparent: true,
      opacity: 0.72,
      side: THREE.DoubleSide,
    });
    const vortex = new THREE.Mesh(new THREE.CircleGeometry(2.15, 32), vortexMat);
    group.add(vortex);

    // Inner segments for spiral effect
    for (let i = 0; i < 8; i++) {
      const seg = new THREE.Mesh(
        new THREE.TorusGeometry(0.5 + i * 0.2, 0.05, 4, 16, Math.PI * 0.6),
        new THREE.MeshStandardMaterial({ color, emissive: color, emissiveIntensity: 1.0 }),
      );
      seg.rotation.z = (i / 8) * Math.PI * 2;
      group.add(seg);
    }

    // Portal glow light
    const light = new THREE.PointLight(color, 2.5, 10);
    light.position.set(0, 0, 0);
    group.add(light);

    // Ground position sampling
    group.position.set(x, y + 1.2, z);
    group.rotation.y = Math.PI / 4;
    scene.add(group);

    return {
      mesh: group,
      active: false,
      position: new THREE.Vector3(x, y, z),
      rotationSpeed: 0.8,
    };
  }

  private _spawnSpaceDust(scene: THREE.Scene): void {
    const count = 2000;
    const positions = new Float32Array(count * 3);
    const half = 120;
    for (let i = 0; i < count; i++) {
      positions[i * 3]     = (Math.random() - 0.5) * half * 2;
      positions[i * 3 + 1] = (Math.random() - 0.5) * half * 2;
      positions[i * 3 + 2] = (Math.random() - 0.5) * half * 2;
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    const mat = new THREE.PointsMaterial({
      color: 0xaaeeff,
      size: 0.18,
      transparent: true,
      opacity: 0.7,
      depthWrite: false,
    });
    this._ambientParticles = new THREE.Points(geo, mat);
    scene.add(this._ambientParticles);
  }

  private _clearExtras(): void {
    for (const m of this._moons) this.scene.remove(m);
    for (const s of this._suns) this.scene.remove(s);
    this._moons = [];
    this._suns = [];
    if (this._saturnRing) { this.scene.remove(this._saturnRing); this._saturnRing = null; }
    if (this._skyMesh) { this.scene.remove(this._skyMesh); }
    if (this._ambientParticles) { this.scene.remove(this._ambientParticles); this._ambientParticles = null; }
    if (this._portal) { this.scene.remove(this._portal.mesh); this._portal = null; }
  }

  getPortal(): PortalState | null {
    return this._portal;
  }

  activatePortal(): void {
    if (this._portal) this._portal.active = true;
  }

  checkPortalProximity(playerPos: THREE.Vector3, range = 3.5): boolean {
    if (!this._portal || !this._portal.active) return false;
    return playerPos.distanceTo(this._portal.position) <= range;
  }

  update(dt: number, time: number): void {
    this._time = time;

    // Update sky time uniform
    if (this._skyMat) {
      this._skyMat.uniforms.uTime.value = time;
    }

    // Rotate portal
    if (this._portal) {
      this._portal.mesh.rotation.y += dt * this._portal.rotationSpeed;
      // Pulse portal glow
      const pulse = 0.7 + Math.sin(time * 2.5) * 0.3;
      this._portal.mesh.traverse(obj => {
        if (obj instanceof THREE.Mesh) {
          const mat = obj.material as THREE.MeshStandardMaterial;
          if (mat.emissiveIntensity !== undefined && mat.emissive.r > 0) {
            mat.emissiveIntensity = pulse * 1.5;
          }
        }
      });
    }

    // Slowly orbit moons
    for (let i = 0; i < this._moons.length; i++) {
      const moon = this._moons[i];
      const orbitSpeed = 0.015 + i * 0.008;
      const currentAngle = Math.atan2(moon.position.z, moon.position.x) + orbitSpeed * dt;
      const dist = moon.position.length();
      moon.position.x = Math.cos(currentAngle) * dist;
      moon.position.z = Math.sin(currentAngle) * dist;
      moon.rotation.y += dt * 0.05;
    }

    // Rotate saturn rings
    if (this._saturnRing) {
      this._saturnRing.rotation.z += dt * 0.05;
    }

    // Drift space dust
    if (this._ambientParticles) {
      this._ambientParticles.rotation.y += dt * 0.003;
    }
  }
}

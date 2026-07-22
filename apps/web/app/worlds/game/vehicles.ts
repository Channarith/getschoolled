import * as THREE from "three";

export type VehicleType = "rover" | "space_hopper";

export interface Vehicle {
  id: string;
  type: VehicleType;
  mesh: THREE.Group;
  position: THREE.Vector3;
  rotation: number;
  isOccupied: boolean;
  speed: number;
  jumpBoost: number;
  projectiles: { mesh: THREE.Mesh; velocity: THREE.Vector3; ttl: number }[];
  animTime: number;
}

const VEHICLE_SPEED: Record<VehicleType, number> = { rover: 9, space_hopper: 12 };
const VEHICLE_JUMP: Record<VehicleType, number> = { rover: 1.1, space_hopper: 2.5 };

export class VehicleManager {
  vehicles: Vehicle[] = [];
  activeVehicle: Vehicle | null = null;
  private scene: THREE.Scene;

  constructor(scene: THREE.Scene, planet: "earth" | "space", hmap: number[][], worldSize: number) {
    this.scene = scene;
    this._spawn(planet, hmap, worldSize);
  }

  private _getH(hmap: number[][], x: number, z: number, ws: number): number {
    const h = ws / 2;
    return hmap[Math.max(0, Math.min(ws - 1, Math.round(x + h)))]?.[Math.max(0, Math.min(ws - 1, Math.round(z + h)))] ?? 2;
  }

  private _spawn(planet: "earth" | "space", hmap: number[][], worldSize: number) {
    if (planet === "earth") {
      const v = this._buildRover();
      const h = this._getH(hmap, 3, 3, worldSize);
      v.mesh.position.set(3, h + 0.6, 3);
      v.position.set(3, h + 0.6, 3);
      this.scene.add(v.mesh);
      this.vehicles.push(v);
    } else {
      const v = this._buildSpaceHopper();
      const h = this._getH(hmap, -5, -5, worldSize);
      v.mesh.position.set(-5, h + 0.8, -5);
      v.position.set(-5, h + 0.8, -5);
      this.scene.add(v.mesh);
      this.vehicles.push(v);
    }
  }

  private _buildRover(): Vehicle {
    const group = new THREE.Group();
    const bodyMat = new THREE.MeshPhongMaterial({ color: 0xd4c4a0, shininess: 40 });
    const wheelMat = new THREE.MeshPhongMaterial({ color: 0x333333 });
    const accentMat = new THREE.MeshPhongMaterial({ color: 0xcc2200, emissive: 0x440000 });

    // Chassis
    const chassis = new THREE.Mesh(new THREE.BoxGeometry(1.8, 0.55, 1.1), bodyMat);
    chassis.position.y = 0.5;
    chassis.castShadow = true;
    group.add(chassis);

    // Cockpit dome
    const dome = new THREE.Mesh(new THREE.SphereGeometry(0.5, 10, 7, 0, Math.PI * 2, 0, Math.PI / 2), new THREE.MeshPhongMaterial({ color: 0x88ccff, transparent: true, opacity: 0.65, shininess: 120 }));
    dome.position.set(0, 0.9, 0);
    group.add(dome);

    // 4 wheels
    const wheelGeo = new THREE.CylinderGeometry(0.3, 0.3, 0.25, 10);
    const wheelPositions: [number, number, number][] = [[-0.85, 0.22, 0.55], [0.85, 0.22, 0.55], [-0.85, 0.22, -0.55], [0.85, 0.22, -0.55]];
    wheelPositions.forEach(([x, y, z]) => {
      const w = new THREE.Mesh(wheelGeo, wheelMat);
      w.rotation.z = Math.PI / 2;
      w.position.set(x, y, z);
      w.name = "wheel";
      w.castShadow = true;
      group.add(w);
    });

    // Laser cannon
    const cannon = new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.08, 0.8, 6), accentMat);
    cannon.rotation.x = Math.PI / 2;
    cannon.position.set(0, 0.9, 0.7);
    group.add(cannon);

    // Antenna
    const ant = new THREE.Mesh(new THREE.CylinderGeometry(0.02, 0.02, 0.7, 4), new THREE.MeshPhongMaterial({ color: 0xaaaaaa }));
    ant.position.set(0.4, 1.4, -0.2);
    group.add(ant);

    return { id: "rover_1", type: "rover", mesh: group, position: new THREE.Vector3(), rotation: 0, isOccupied: false, speed: VEHICLE_SPEED.rover, jumpBoost: VEHICLE_JUMP.rover, projectiles: [], animTime: 0 };
  }

  private _buildSpaceHopper(): Vehicle {
    const group = new THREE.Group();
    const bodyMat = new THREE.MeshPhongMaterial({ color: 0xc0c8e0, shininess: 80, specular: 0x888888 });
    const legMat = new THREE.MeshPhongMaterial({ color: 0x808090 });
    const thrusterMat = new THREE.MeshPhongMaterial({ color: 0x4488ff, emissive: 0x002244 });

    // Pod body
    const pod = new THREE.Mesh(new THREE.SphereGeometry(0.7, 10, 8), bodyMat);
    pod.scale.y = 0.75;
    pod.position.y = 0.8;
    pod.castShadow = true;
    group.add(pod);

    // 3 legs
    for (let i = 0; i < 3; i++) {
      const angle = (i / 3) * Math.PI * 2;
      const leg = new THREE.Mesh(new THREE.CylinderGeometry(0.04, 0.06, 0.9, 5), legMat);
      leg.position.set(Math.cos(angle) * 0.55, 0.35, Math.sin(angle) * 0.55);
      leg.rotation.z = Math.cos(angle) * 0.4;
      leg.rotation.x = Math.sin(angle) * 0.4;
      group.add(leg);

      // Foot pad
      const foot = new THREE.Mesh(new THREE.CylinderGeometry(0.15, 0.15, 0.06, 8), legMat);
      foot.position.set(Math.cos(angle) * 0.75, 0, Math.sin(angle) * 0.75);
      group.add(foot);
    }

    // Thruster glow
    const thruster = new THREE.Mesh(new THREE.CylinderGeometry(0.2, 0.35, 0.3, 8), thrusterMat);
    thruster.position.y = 0.2;
    group.add(thruster);

    return { id: "hopper_1", type: "space_hopper", mesh: group, position: new THREE.Vector3(), rotation: 0, isOccupied: false, speed: VEHICLE_SPEED.space_hopper, jumpBoost: VEHICLE_JUMP.space_hopper, projectiles: [], animTime: 0 };
  }

  checkNearby(playerPos: THREE.Vector3): Vehicle | null {
    return this.vehicles.find(v => !v.isOccupied && playerPos.distanceTo(v.mesh.position) < 2.5) ?? null;
  }

  enterVehicle(vehicle: Vehicle, playerGroup: THREE.Group) {
    vehicle.isOccupied = true;
    this.activeVehicle = vehicle;
    // Hide player mesh while in vehicle
    playerGroup.visible = false;
  }

  exitVehicle(playerGroup: THREE.Group) {
    if (!this.activeVehicle) return;
    // Place player next to vehicle
    playerGroup.position.copy(this.activeVehicle.mesh.position).add(new THREE.Vector3(1.5, 0, 0));
    playerGroup.visible = true;
    this.activeVehicle.isOccupied = false;
    this.activeVehicle = null;
  }

  fireLaser() {
    const v = this.activeVehicle;
    if (!v || v.type !== "rover") return;
    const geo = new THREE.CylinderGeometry(0.03, 0.03, 0.8, 4);
    const mat = new THREE.MeshPhongMaterial({ color: 0xff0000, emissive: 0x880000 });
    const bolt = new THREE.Mesh(geo, mat);
    bolt.rotation.x = Math.PI / 2;
    const dir = new THREE.Vector3(0, 0, 1).applyQuaternion(v.mesh.quaternion);
    bolt.position.copy(v.mesh.position).addScaledVector(dir, 1.2).add(new THREE.Vector3(0, 0.9, 0));
    this.scene.add(bolt);
    v.projectiles.push({ mesh: bolt, velocity: dir.clone().multiplyScalar(22), ttl: 1.5 });
  }

  update(dt: number, keys: Record<string, boolean>, time: number, hmap: number[][], worldSize: number): THREE.Vector3 | null {
    const v = this.activeVehicle;
    if (!v) {
      // Idle animations for parked vehicles
      this.vehicles.forEach(veh => {
        veh.animTime += dt;
        veh.mesh.traverse(obj => { if (obj.name === "wheel") obj.rotation.x += dt * 1.5; });
      });
      return null;
    }

    v.animTime += dt;

    // Wheel spin
    v.mesh.traverse(obj => { if (obj.name === "wheel") obj.rotation.x += v.speed * dt * 0.5; });

    // Hover effect for space_hopper
    if (v.type === "space_hopper") {
      v.mesh.position.y += Math.sin(time * 3) * 0.002;
    }

    // Movement
    const speed = v.speed;
    const fwd = new THREE.Vector3(0, 0, 1).applyEuler(new THREE.Euler(0, v.rotation, 0));
    const right = new THREE.Vector3(1, 0, 0).applyEuler(new THREE.Euler(0, v.rotation, 0));

    if (keys["KeyW"] || keys["ArrowUp"])   v.mesh.position.addScaledVector(fwd, speed * dt);
    if (keys["KeyS"] || keys["ArrowDown"]) v.mesh.position.addScaledVector(fwd, -speed * dt);
    if (keys["KeyA"] || keys["ArrowLeft"]) v.rotation += dt * 1.8;
    if (keys["KeyD"] || keys["ArrowRight"]) v.rotation -= dt * 1.8;
    v.mesh.rotation.y = v.rotation;

    // Ground snap
    const half = worldSize / 2;
    const ix = Math.max(0, Math.min(worldSize - 1, Math.round(v.mesh.position.x + half)));
    const iz = Math.max(0, Math.min(worldSize - 1, Math.round(v.mesh.position.z + half)));
    const floorH = (hmap[ix]?.[iz] ?? 1) + (v.type === "space_hopper" ? 0.9 : 0.5);
    v.mesh.position.y = Math.max(floorH, v.mesh.position.y);

    // World bounds
    v.mesh.position.x = Math.max(-half + 1, Math.min(half - 1, v.mesh.position.x));
    v.mesh.position.z = Math.max(-half + 1, Math.min(half - 1, v.mesh.position.z));
    v.position.copy(v.mesh.position);

    // Update projectiles
    v.projectiles = v.projectiles.filter(p => {
      p.ttl -= dt;
      p.mesh.position.addScaledVector(p.velocity, dt);
      if (p.ttl <= 0) { this.scene.remove(p.mesh); p.mesh.geometry.dispose(); return false; }
      return true;
    });

    return v.mesh.position.clone();
  }

  getProjectiles() {
    return this.activeVehicle?.projectiles ?? [];
  }

  dispose() {
    this.vehicles.forEach(v => this.scene.remove(v.mesh));
  }
}

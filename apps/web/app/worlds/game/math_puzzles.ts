import * as THREE from "three";
export interface MathPuzzle { id: string; position: THREE.Vector3; title: string; instruction: string; xpReward: number; solved: boolean; }
export class MathPuzzleManager {
  puzzles: MathPuzzle[] = [
    { id:"p1", position:new THREE.Vector3(-8,0,5),  title:"Balance of Eight", instruction:"7 + ? = 12. What is the missing number?", xpReward:30, solved:false },
    { id:"p2", position:new THREE.Vector3(8,0,-8),  title:"Prime Path", instruction:"Cross only on PRIME numbers: 2,3,5,7,11,13...", xpReward:35, solved:false },
    { id:"p3", position:new THREE.Vector3(-12,0,-12),title:"Fibonacci Leap", instruction:"1,1,2,3,5,8,__ — jump to the missing number!", xpReward:40, solved:false },
    { id:"p4", position:new THREE.Vector3(15,0,0),  title:"Crystal Equation", instruction:"3 × ? = 21 — shoot the correct crystal!", xpReward:30, solved:false },
  ];
  private scene: THREE.Scene;
  private meshes: THREE.Mesh[] = [];
  onSolved?: (id: string, xp: number) => void;
  constructor(scene: THREE.Scene) {
    this.scene = scene;
    this.puzzles.forEach((p,i) => {
      const m = new THREE.Mesh(new THREE.TorusGeometry(0.8,0.12,6,24), new THREE.MeshPhongMaterial({ color:0x00ccff, emissive:0x003344 }));
      m.position.copy(p.position).add(new THREE.Vector3(0,1.5,0));
      m.name = `puzzle_${p.id}`; this.scene.add(m); this.meshes.push(m);
    });
  }
  checkNearby(pp: THREE.Vector3): MathPuzzle | null {
    return this.puzzles.find((p,i) => !p.solved && pp.distanceTo(this.meshes[i]?.position ?? new THREE.Vector3(999,999,999)) < 3.5) ?? null;
  }
  solvePuzzle(id: string) {
    const p = this.puzzles.find(p => p.id === id); if(!p||p.solved) return;
    p.solved = true; const i = this.puzzles.indexOf(p);
    const m = this.meshes[i]; if(m) { (m.material as THREE.MeshPhongMaterial).color.set(0xffd700); }
    this.onSolved?.(id, p.xpReward);
  }
  update(dt: number, time: number) {
    this.meshes.forEach((m,i) => { if(m.parent && !this.puzzles[i].solved) { m.rotation.y += dt*1.0; m.rotation.x = Math.sin(time*0.8+i)*0.15; } });
  }
  dispose() { this.meshes.forEach(m => this.scene.remove(m)); }
}

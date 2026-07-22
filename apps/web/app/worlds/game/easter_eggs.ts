import * as THREE from "three";
export type LeyStoneId = "dawn"|"deep"|"fire"|"stars"|"rain"|"time"|"growth"|"void";
export interface LeyStone { id: LeyStoneId; name: string; description: string; position: THREE.Vector3; found: boolean; secret: string; }

export class EasterEggManager {
  activeStones: Set<LeyStoneId> = new Set();
  stones: LeyStone[] = [
    { id:"dawn",   name:"Stone of Dawn",    description:"Grasslands glow gold.",  position:new THREE.Vector3(16,3,3),   found:false, secret:"The stone remembers the first sunrise." },
    { id:"deep",   name:"Stone of the Deep",description:"Caves bioluminesce.",    position:new THREE.Vector3(0,-4,0),   found:false, secret:"Deep creatures invented light before the sun." },
    { id:"fire",   name:"Stone of Fire",    description:"Snow peaks turn volcanic.",position:new THREE.Vector3(-8,8.5,-20),found:false, secret:"Every mountain is a volcano that hasn't decided yet." },
    { id:"stars",  name:"Stone of Stars",   description:"Surfaces sparkle.",       position:new THREE.Vector3(5,4,5),    found:false, secret:"The rings are made of crushed crystal." },
    { id:"rain",   name:"Stone of Rain",    description:"Blue shimmer everywhere.",position:new THREE.Vector3(22,1.1,-5),found:false, secret:"First rain on Earth lasted 20,000 years." },
    { id:"time",   name:"Stone of Time",    description:"Day/night cycle shift.",  position:new THREE.Vector3(-15,2,8),  found:false, secret:"Time moves differently underground." },
    { id:"growth", name:"Stone of Growth",  description:"Desert blooms green.",    position:new THREE.Vector3(10,1,22),  found:false, secret:"Beneath every desert lies an ancient ocean." },
    { id:"void",   name:"Stone of Void",    description:"Galaxy swirls in sky.",   position:new THREE.Vector3(-10,5,-10),found:false, secret:"More stars than grains of sand on Earth." },
  ];
  private meshes: THREE.Mesh[] = [];
  constructor(private scene: THREE.Scene) { this._spawn(); }
  private _spawn() {
    this.stones.forEach(s => {
      const m = new THREE.Mesh(new THREE.OctahedronGeometry(0.4,0), new THREE.MeshPhongMaterial({ color:0xffdd00, emissive:0x885500, transparent:true, opacity:0.9 }));
      m.position.copy(s.position); m.name = `ley_${s.id}`;
      this.scene.add(m); this.meshes.push(m);
    });
  }
  checkCollection(pp: THREE.Vector3): LeyStone | null {
    for (let i = 0; i < this.stones.length; i++) {
      const s = this.stones[i];
      if (!s.found && pp.distanceTo(s.position) < 1.8) {
        s.found = true; this.activeStones.add(s.id);
        const m = this.meshes[i]; if (m) this.scene.remove(m);
        return s;
      }
    }
    return null;
  }
  getFoundCount() { return this.activeStones.size; }
  update(dt: number, time: number) {
    this.meshes.forEach((m,i) => { if(m.parent){ m.rotation.y += dt*1.2; m.position.y = this.stones[i].position.y + Math.sin(time*1.8+i)*0.12; } });
  }
  dispose() { this.meshes.forEach(m => this.scene.remove(m)); }
}

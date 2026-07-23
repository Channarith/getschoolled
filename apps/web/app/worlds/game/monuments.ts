import * as THREE from "three";
export interface Monument { id: string; name: string; civilization: string; position: THREE.Vector3; mesh: THREE.Group|null; completed: boolean; xpReward: number; easterEggHint: string; }
export class MonumentManager {
  monuments: Monument[] = [
    { id:"pyramid",   name:"Great Pyramid",        civilization:"Ancient Egypt",  position:new THREE.Vector3(18,0,22),   mesh:null, completed:false, xpReward:60, easterEggHint:"Stone of Fire is at a peak rivalling this pyramid's height." },
    { id:"great_wall",name:"Great Wall segment",   civilization:"Chinese Dynasty",position:new THREE.Vector3(-18,0,-18), mesh:null, completed:false, xpReward:60, easterEggHint:"Stone of Time sealed in a Stone Golem near these walls." },
    { id:"colosseum", name:"Colosseum Ruins",       civilization:"Roman Empire",  position:new THREE.Vector3(5,0,-18),  mesh:null, completed:false, xpReward:55, easterEggHint:"Follow gladiators east — Stone of Rain is in the waters." },
    { id:"liberty",   name:"Statue of Liberty",    civilization:"USA / France",   position:new THREE.Vector3(20,0,10),  mesh:null, completed:false, xpReward:50, easterEggHint:"Stone of Growth blooms beneath the desert to the south." },
    { id:"stonehenge",name:"Stonehenge",           civilization:"Ancient Britain", position:new THREE.Vector3(-5,0,15),  mesh:null, completed:false, xpReward:55, easterEggHint:"Aligned with the solstice, like Stone of Dawn at the waterfall." },
  ];
  private scene: THREE.Scene;
  onApproached?: (m: Monument) => void;
  onCompleted?: (m: Monument) => void;
  constructor(scene: THREE.Scene, hmap: number[][], worldSize: number) {
    this.scene = scene;
    this._build(hmap, worldSize);
  }
  private _getH(hmap: number[][], x: number, z: number, ws: number) {
    const h = ws/2; return hmap[Math.max(0,Math.min(ws-1,Math.round(x+h)))]?.[Math.max(0,Math.min(ws-1,Math.round(z+h)))] ?? 2;
  }
  private _build(hmap: number[][], ws: number) {
    this.monuments.forEach(m => {
      const g = new THREE.Group();
      const fh = this._getH(hmap, m.position.x, m.position.z, ws);
      g.position.set(m.position.x, fh, m.position.z);
      // Simple stone pillar cluster
      for (let i = 0; i < 4; i++) {
        const angle = (i/4)*Math.PI*2;
        const pillar = new THREE.Mesh(new THREE.CylinderGeometry(0.2,0.25,2.5,6), new THREE.MeshPhongMaterial({color:0x8a8070}));
        pillar.position.set(Math.cos(angle)*2, 1.25, Math.sin(angle)*2);
        pillar.castShadow = true; g.add(pillar);
      }
      // Central marker
      const marker = new THREE.Mesh(new THREE.OctahedronGeometry(0.5,0), new THREE.MeshPhongMaterial({color:0xffcc44, emissive:0x885500}));
      marker.position.y = 3; g.add(marker);
      this.scene.add(g); m.mesh = g;
    });
  }
  checkNearby(pp: THREE.Vector3): Monument | null {
    return this.monuments.find(m => !m.completed && m.mesh && pp.distanceTo(m.mesh.position) < 5) ?? null;
  }
  complete(id: string) {
    const m = this.monuments.find(m => m.id === id); if (!m || m.completed) return;
    m.completed = true;
    m.mesh?.traverse(obj => { if(obj instanceof THREE.Mesh) (obj.material as THREE.MeshPhongMaterial).emissive.set(0x7a6000); });
    this.onCompleted?.(m);
  }
  update(dt: number, time: number) {
    this.monuments.forEach((m,i) => {
      const marker = m.mesh?.children[m.mesh.children.length-1];
      if (marker) { marker.rotation.y += dt*0.8; (marker as THREE.Mesh).position.y = 3 + Math.sin(time*1.5+i)*0.1; }
    });
  }
  dispose() { this.monuments.forEach(m => { if(m.mesh) this.scene.remove(m.mesh); }); }
}

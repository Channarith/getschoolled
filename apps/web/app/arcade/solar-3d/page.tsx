"use client";

// Solar Quiz 3D — a real WebGL game with Three.js. Eight planets orbit the Sun in
// 3D; answer the prompt by clicking the right planet (raycasting). Correct = the
// planet pulses + score; wrong = a shake. Lights, orbits, starfield — a genuine
// 3D graphics engine, not DOM widgets.

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import * as THREE from "three";

type Planet = {
  name: string; color: number; radius: number; orbit: number; speed: number;
  order: number;   // distance rank from the Sun (1 = closest)
  mesh?: THREE.Mesh;
  angle: number;
};

const PLANETS: Omit<Planet, "mesh" | "angle">[] = [
  { name: "Mercury", color: 0x9c8a7a, radius: 0.28, orbit: 3.2, speed: 0.9, order: 1 },
  { name: "Venus", color: 0xd9a066, radius: 0.42, orbit: 4.2, speed: 0.72, order: 2 },
  { name: "Earth", color: 0x4a90e2, radius: 0.45, orbit: 5.3, speed: 0.6, order: 3 },
  { name: "Mars", color: 0xc1440e, radius: 0.35, orbit: 6.3, speed: 0.5, order: 4 },
  { name: "Jupiter", color: 0xd8b48b, radius: 0.95, orbit: 8.0, speed: 0.32, order: 5 },
  { name: "Saturn", color: 0xe3d3a0, radius: 0.8, orbit: 9.6, speed: 0.26, order: 6 },
  { name: "Uranus", color: 0x9fe0e6, radius: 0.6, orbit: 11.0, speed: 0.2, order: 7 },
  { name: "Neptune", color: 0x3b6fd4, radius: 0.58, orbit: 12.2, speed: 0.16, order: 8 },
];

type Prompt = { text: string; answer: string };

function makePrompt(): Prompt {
  const kind = Math.floor(Math.random() * 3);
  if (kind === 0) {
    const p = PLANETS[Math.floor(Math.random() * PLANETS.length)];
    return { text: `Click ${p.name}`, answer: p.name };
  }
  if (kind === 1) {
    return { text: "Click the planet closest to the Sun", answer: "Mercury" };
  }
  const largest = [...PLANETS].sort((a, b) => b.radius - a.radius)[0];
  return { text: "Click the largest planet", answer: largest.name };
}

export default function Solar3D() {
  const mountRef = useRef<HTMLDivElement>(null);
  const [supported, setSupported] = useState(true);
  const [score, setScore] = useState(0);
  const [prompt, setPrompt] = useState<Prompt>({ text: "", answer: "" });
  const [flash, setFlash] = useState<"ok" | "bad" | "">("");
  const promptRef = useRef<Prompt>({ text: "", answer: "" });

  const nextPrompt = useCallback(() => {
    const p = makePrompt();
    promptRef.current = p;
    setPrompt(p);
  }, []);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return;

    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    } catch {
      setSupported(false);
      return;
    }
    const width = mount.clientWidth || 640;
    const height = mount.clientHeight || 480;
    renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
    renderer.setSize(width, height);
    mount.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(55, width / height, 0.1, 200);
    camera.position.set(0, 11, 17);
    camera.lookAt(0, 0, 0);

    // Lights: the Sun glows; ambient fills shadows.
    scene.add(new THREE.AmbientLight(0x556080, 0.7));
    const sunLight = new THREE.PointLight(0xfff2c0, 2.4, 100);
    scene.add(sunLight);

    // Sun.
    const sun = new THREE.Mesh(
      new THREE.SphereGeometry(1.5, 32, 32),
      new THREE.MeshBasicMaterial({ color: 0xffcc55 }),
    );
    scene.add(sun);
    const glow = new THREE.Mesh(
      new THREE.SphereGeometry(2.1, 32, 32),
      new THREE.MeshBasicMaterial({ color: 0xffaa33, transparent: true, opacity: 0.18 }),
    );
    scene.add(glow);

    // Planets + orbit rings.
    const planets: Planet[] = PLANETS.map((p) => ({ ...p, angle: Math.random() * Math.PI * 2 }));
    for (const p of planets) {
      const mesh = new THREE.Mesh(
        new THREE.SphereGeometry(p.radius, 28, 28),
        new THREE.MeshStandardMaterial({ color: p.color, roughness: 0.85, metalness: 0.1 }),
      );
      mesh.userData.name = p.name;
      p.mesh = mesh;
      scene.add(mesh);
      const ring = new THREE.Mesh(
        new THREE.RingGeometry(p.orbit - 0.02, p.orbit + 0.02, 96),
        new THREE.MeshBasicMaterial({ color: 0x3b3560, side: THREE.DoubleSide, transparent: true, opacity: 0.4 }),
      );
      ring.rotation.x = Math.PI / 2;
      scene.add(ring);
    }

    // Starfield.
    const starGeo = new THREE.BufferGeometry();
    const starPos = new Float32Array(1200 * 3);
    for (let i = 0; i < starPos.length; i++) starPos[i] = (Math.random() - 0.5) * 160;
    starGeo.setAttribute("position", new THREE.BufferAttribute(starPos, 3));
    scene.add(new THREE.Points(starGeo, new THREE.PointsMaterial({ color: 0xa2b8ff, size: 0.25 })));

    const raycaster = new THREE.Raycaster();
    const pointer = new THREE.Vector2();
    let pulse: { mesh: THREE.Mesh; t: number; base: number } | null = null;
    let shake = 0;

    const onClick = (e: MouseEvent) => {
      const rect = renderer.domElement.getBoundingClientRect();
      pointer.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      pointer.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
      raycaster.setFromCamera(pointer, camera);
      const hits = raycaster.intersectObjects(planets.map((p) => p.mesh!).filter(Boolean));
      if (!hits.length) return;
      const name = hits[0].object.userData.name as string;
      if (name === promptRef.current.answer) {
        setScore((s) => s + 10);
        setFlash("ok"); setTimeout(() => setFlash(""), 350);
        pulse = { mesh: hits[0].object as THREE.Mesh, t: 0, base: (hits[0].object as THREE.Mesh).scale.x };
        nextPrompt();
      } else {
        setScore((s) => Math.max(0, s - 3));
        setFlash("bad"); setTimeout(() => setFlash(""), 350);
        shake = 0.5;
      }
    };
    renderer.domElement.addEventListener("click", onClick);

    const onResize = () => {
      const w = mount.clientWidth || width, h = mount.clientHeight || height;
      renderer.setSize(w, h);
      camera.aspect = w / h; camera.updateProjectionMatrix();
    };
    window.addEventListener("resize", onResize);

    nextPrompt();
    const clock = new THREE.Clock();
    let raf = 0;
    const animate = () => {
      raf = requestAnimationFrame(animate);
      const dt = clock.getDelta();
      const t = clock.elapsedTime;
      for (const p of planets) {
        p.angle += p.speed * dt;
        if (p.mesh) {
          p.mesh.position.set(Math.cos(p.angle) * p.orbit, 0, Math.sin(p.angle) * p.orbit);
          p.mesh.rotation.y += dt * 0.5;
        }
      }
      glow.scale.setScalar(1 + Math.sin(t * 2) * 0.03);
      if (pulse) {
        pulse.t += dt;
        const k = 1 + Math.sin(Math.min(Math.PI, pulse.t * 10)) * 0.6;
        pulse.mesh.scale.setScalar(pulse.base * k);
        if (pulse.t > Math.PI / 10) { pulse.mesh.scale.setScalar(pulse.base); pulse = null; }
      }
      // slow orbital camera + shake
      shake = Math.max(0, shake - dt * 1.5);
      const cs = shake * 0.6;
      camera.position.x = Math.sin(t * 0.08) * 4 + (Math.random() - 0.5) * cs;
      camera.position.y = 11 + (Math.random() - 0.5) * cs;
      camera.lookAt(0, 0, 0);
      renderer.render(scene, camera);
    };
    animate();

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", onResize);
      renderer.domElement.removeEventListener("click", onClick);
      renderer.dispose();
      scene.traverse((o) => {
        const m = o as THREE.Mesh;
        m.geometry?.dispose?.();
        const mat = m.material as THREE.Material | THREE.Material[] | undefined;
        if (Array.isArray(mat)) mat.forEach((x) => x.dispose());
        else mat?.dispose?.();
      });
      if (renderer.domElement.parentNode === mount) mount.removeChild(renderer.domElement);
    };
  }, [nextPrompt]);

  return (
    <main style={{ maxWidth: 860, margin: "0 auto", padding: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <h1 style={{ margin: 0 }}>🌌 Solar Quiz 3D</h1>
        <Link href="/arcade" style={{ marginLeft: "auto" }}>← Arcade</Link>
        <Link href="/rewards">Rewards</Link>
      </div>
      <p className="muted">A real 3D scene (Three.js). Read the prompt, then click the correct planet.</p>
      <div style={{
        display: "flex", justifyContent: "space-between", alignItems: "center",
        padding: "8px 12px", borderRadius: 10, marginBottom: 8,
        background: flash === "ok" ? "rgba(52,211,153,0.25)" : flash === "bad" ? "rgba(248,113,113,0.25)" : "rgba(124,58,237,0.18)",
        transition: "background 0.2s",
      }}>
        <strong style={{ fontSize: 18 }}>{prompt.text}</strong>
        <span style={{ fontWeight: 700 }}>Score {score}</span>
      </div>
      {supported ? (
        <div ref={mountRef} style={{ width: "100%", aspectRatio: "16 / 10", borderRadius: 14, overflow: "hidden", border: "1px solid #2d1b4e", background: "#05030f", cursor: "pointer" }} />
      ) : (
        <div className="card">3D (WebGL) isn&apos;t available in this browser. Try the 2D games in the Arcade.</div>
      )}
    </main>
  );
}

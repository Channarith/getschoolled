import * as THREE from "three";
import { GLTFLoader } from "./loaders/GLTFLoader.js";
import { resolveSkeleton, createFaceDriver, applyHologram } from "./avatar_rig.js";

const JOINTS = [
  "AvatarRoot", "Hips", "Spine", "Chest", "Neck", "Head", "Jaw",
  "LeftShoulder", "RightShoulder", "LeftElbow", "RightElbow",
  "LeftWrist", "RightWrist", "LeftFingers", "RightFingers",
  "LeftHip", "RightHip", "LeftKnee", "RightKnee",
  "LeftAnkle", "RightAnkle", "LeftEye", "RightEye",
  "LeftBrow", "RightBrow", "LeftEar", "RightEar", "Crown",
];

const MODELS = {
  female: "presenter_female.glb",
  male: "presenter_male.glb",
};

// Response speed per joint, in rad/s. Heavy joints answer slower, which is what
// produces natural follow-through instead of the whole body snapping at once.
const STIFFNESS = {
  default: 11,
  Hips: 6,
  Spine: 7,
  Chest: 7.5,
  Neck: 9,
  Head: 8,
  Jaw: 26,
  LeftShoulder: 10,
  RightShoulder: 10,
  LeftElbow: 12,
  RightElbow: 12,
  LeftWrist: 15,
  RightWrist: 15,
  LeftFingers: 18,
  RightFingers: 18,
  LeftBrow: 16,
  RightBrow: 16,
  LeftEye: 20,
  RightEye: 20,
};

const clamp = (v, lo = 0, hi = 1) => Math.max(lo, Math.min(hi, v));
const smooth = (v) => v * v * (3 - 2 * v);

/**
 * Critically damped spring. Semi-implicit integration with a clamped step, so a
 * dropped frame slows the motion instead of exploding it.
 */
class Spring {
  constructor(omega) {
    this.omega = omega;
    this.value = 0;
    this.velocity = 0;
  }

  step(target, dt) {
    const k = this.omega;
    this.velocity += (-2 * k * this.velocity - k * k * (this.value - target)) * dt;
    this.value += this.velocity * dt;
    return this.value;
  }
}

function snapshot(nodes) {
  const out = {};
  for (const name of JOINTS) {
    const node = nodes[name];
    if (!node) continue;
    out[name] = {
      position: node.position.clone(),
      rotation: node.rotation.clone(),
      scale: node.scale.clone(),
    };
  }
  return out;
}

/**
 * Target offsets for one frame. Gestures accumulate here and the springs chase
 * these values, so cues blend instead of fighting over the same joint.
 */
class PoseTarget {
  constructor() {
    this.rot = new Map();
    this.pos = new Map();
    this.scale = new Map();
  }

  clear() {
    this.rot.clear();
    this.pos.clear();
    this.scale.clear();
  }

  add(joint, x = 0, y = 0, z = 0, weight = 1) {
    if (!weight) return;
    const current = this.rot.get(joint) || [0, 0, 0];
    current[0] += x * weight;
    current[1] += y * weight;
    current[2] += z * weight;
    this.rot.set(joint, current);
  }

  addPosition(joint, axis, value) {
    const current = this.pos.get(joint) || { x: 0, y: 0, z: 0 };
    current[axis] += value;
    this.pos.set(joint, current);
  }

  addScale(joint, axis, value) {
    const current = this.scale.get(joint) || { x: 0, y: 0, z: 0 };
    current[axis] += value;
    this.scale.set(joint, current);
  }
}

function poseGesture(pose, name, phase, intensity) {
  // A raised-cosine envelope: every gesture eases in and out of rest, so no cue
  // starts or ends on a hard pop.
  const s = Math.sin(Math.PI * clamp(phase));
  const w = s * intensity;
  const rotate = (joint, x, y, z, weight = w) => pose.add(joint, x, y, z, weight);
  switch (name) {
    case "explain":
    case "open-palm":
      rotate("LeftShoulder", -0.22, 0, -0.72);
      rotate("LeftElbow", -0.28, 0, -0.42);
      rotate("LeftWrist", 0.12, 0, -0.18);
      rotate("RightShoulder", -0.16, 0, 0.48, w * 0.7);
      rotate("RightElbow", -0.18, 0, 0.35, w * 0.7);
      break;
    case "point-left":
    case "point-to-slide":
      rotate("LeftShoulder", -0.12, 0.12, -1.2);
      rotate("LeftElbow", 0.05, 0, -0.22);
      rotate("LeftWrist", 0, 0.1, 0.12);
      rotate("LeftFingers", -0.18, 0, 0);
      rotate("Head", 0, -0.28, 0);
      break;
    case "point-right":
      rotate("RightShoulder", -0.12, -0.12, 1.2);
      rotate("RightElbow", 0.05, 0, 0.22);
      rotate("RightWrist", 0, -0.1, -0.12);
      rotate("RightFingers", -0.18, 0, 0);
      rotate("Head", 0, 0.28, 0);
      break;
    case "count":
      rotate("RightShoulder", -0.18, 0, 0.72);
      rotate("RightElbow", -0.45, 0, 0.62);
      rotate("RightWrist", -0.2, 0.1, -0.15);
      rotate("RightFingers", 0.18 * Math.sin(phase * Math.PI * 4), 0, 0);
      break;
    case "compare":
      rotate("LeftShoulder", -0.1, 0, -0.88);
      rotate("RightShoulder", -0.1, 0, 0.88);
      rotate("LeftElbow", -0.28, 0, -0.32);
      rotate("RightElbow", -0.28, 0, 0.32);
      break;
    case "caution":
    case "stop":
      rotate("RightShoulder", -0.35, 0, 0.88);
      rotate("RightElbow", -0.55, 0, 0.48);
      rotate("RightWrist", -0.55, 0, -0.12);
      rotate("Head", 0.08, 0, 0);
      break;
    case "steer":
      rotate("LeftShoulder", -0.62, 0, -0.28);
      rotate("RightShoulder", -0.62, 0, 0.28);
      rotate("LeftElbow", -0.48, 0, -0.16);
      rotate("RightElbow", -0.48, 0, 0.16);
      rotate("Spine", 0, 0.08 * Math.sin(phase * Math.PI * 2), 0);
      break;
    case "shoulder-check":
      rotate("Chest", 0, -0.34, 0);
      rotate("Neck", 0, -0.42, 0);
      rotate("Head", 0, -0.38, 0);
      break;
    case "seatbelt":
      rotate("RightShoulder", -0.18, 0, 0.75);
      rotate("RightElbow", -0.72, 0, 0.42);
      rotate("RightWrist", -0.2, 0, -0.24);
      rotate("Chest", 0, 0, 0.08);
      break;
    case "phone-away":
      rotate("RightShoulder", -0.35, 0, 0.38);
      rotate("RightElbow", -1.05, 0, 0.2);
      rotate("RightWrist", 0.35, 0, -0.2);
      rotate("Head", 0, 0.18, 0);
      break;
    case "wash-hands":
    case "sanitize":
      rotate("LeftShoulder", -0.48, 0, -0.34);
      rotate("RightShoulder", -0.48, 0, 0.34);
      rotate("LeftElbow", -0.72, 0, -0.38);
      rotate("RightElbow", -0.72, 0, 0.38);
      rotate("LeftWrist", 0, 0.45 * Math.sin(phase * Math.PI * 8), 0);
      rotate("RightWrist", 0, -0.45 * Math.sin(phase * Math.PI * 8), 0);
      break;
    case "gloves":
      rotate("LeftShoulder", -0.45, 0, -0.28);
      rotate("RightShoulder", -0.38, 0, 0.38);
      rotate("LeftElbow", -0.7, 0, -0.25);
      rotate("RightElbow", -0.8, 0, 0.28);
      rotate("RightWrist", 0, 0, -0.5);
      break;
    case "thermometer":
      rotate("RightShoulder", -0.48, 0, 0.58);
      rotate("RightElbow", -0.7, 0, 0.45);
      rotate("RightWrist", -0.25, 0, -0.2);
      rotate("Head", 0.12, 0.16, 0);
      break;
    case "ask":
      rotate("Head", -0.08, 0, 0.08);
      rotate("LeftShoulder", -0.14, 0, -0.42);
      rotate("LeftElbow", -0.38, 0, -0.3);
      break;
    case "listen":
      rotate("Head", -0.04, 0, -0.1);
      rotate("Spine", -0.04, 0, 0);
      break;
    case "celebrate":
      rotate("LeftShoulder", -0.1, 0, -1.48);
      rotate("RightShoulder", -0.1, 0, 1.48);
      rotate("LeftElbow", -0.28, 0, -0.28);
      rotate("RightElbow", -0.28, 0, 0.28);
      break;
    case "demonstrate":
      rotate("RightShoulder", -0.24, 0, 0.72);
      rotate("RightElbow", -0.52, 0, 0.42);
      rotate("Chest", 0, -0.12, 0);
      break;
    case "transition":
      rotate("Spine", 0, 0.15, 0);
      rotate("Head", 0, -0.12, 0);
      break;
    default:
      break;
  }
}

// A gentle resting smile is the Serenity signature, so even "neutral" keeps a
// soft upturn rather than a flat line.
const EXPRESSIONS = {
  neutral: { brow: 0.01, smile: 0.24 },
  warm: { brow: 0.03, smile: 0.4 },
  serious: { brow: -0.04, smile: 0.12 },
  concerned: { brow: -0.08, smile: 0.06 },
  curious: { brow: 0.07, smile: 0.28 },
  encouraging: { brow: 0.05, smile: 0.5 },
  celebrating: { brow: 0.09, smile: 0.66 },
};

/**
 * Rim light plus faint circuitry so the hologram reads as a body rather than a
 * flat decal, matching the Serenity concept art's glowing traces.
 */
function applyFresnel(material, strength = 0.85, circuitry = 0.55) {
  material.onBeforeCompile = (shader) => {
    shader.uniforms.fresnelStrength = { value: strength };
    shader.uniforms.circuitStrength = { value: circuitry };
    shader.vertexShader = shader.vertexShader
      .replace("#include <common>", "#include <common>\nvarying vec3 vFresnelNormal;\nvarying vec3 vFresnelView;\nvarying vec3 vFresnelLocal;")
      .replace(
        "#include <fog_vertex>",
        `#include <fog_vertex>
        vFresnelNormal = normalize(mat3(modelMatrix) * objectNormal);
        vFresnelView = normalize(cameraPosition - (modelMatrix * vec4(transformed, 1.0)).xyz);
        vFresnelLocal = transformed;`,
      );
    shader.fragmentShader = shader.fragmentShader
      .replace(
        "#include <common>",
        `#include <common>
        uniform float fresnelStrength;
        uniform float circuitStrength;
        varying vec3 vFresnelNormal;
        varying vec3 vFresnelView;
        varying vec3 vFresnelLocal;
        float circuitLine(float v) {
          float f = abs(fract(v) - 0.5);
          return smoothstep(0.46, 0.5, 1.0 - f);
        }`,
      )
      .replace(
        "#include <dithering_fragment>",
        `#include <dithering_fragment>
        float rim = pow(1.0 - clamp(dot(normalize(vFresnelNormal), normalize(vFresnelView)), 0.0, 1.0), 2.4);
        gl_FragColor.rgb += vec3(0.28, 0.78, 1.0) * rim * fresnelStrength;
        // Thin horizontal + vertical traces, brighter on grazing angles.
        float traces = max(circuitLine(vFresnelLocal.y * 11.0), circuitLine(vFresnelLocal.x * 9.0 + vFresnelLocal.z * 9.0));
        float inner = clamp(dot(normalize(vFresnelNormal), normalize(vFresnelView)), 0.0, 1.0);
        gl_FragColor.rgb += vec3(0.16, 0.62, 0.86) * traces * circuitStrength * (0.35 + inner * 0.5);
        gl_FragColor.a = clamp(gl_FragColor.a + rim * 0.35, 0.0, 1.0);`,
      );
  };
  material.needsUpdate = true;
}

function contactShadow() {
  const material = new THREE.ShaderMaterial({
    transparent: true,
    depthWrite: false,
    uniforms: {},
    vertexShader: `varying vec2 vUvShadow;
      void main() { vUvShadow = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
    fragmentShader: `varying vec2 vUvShadow;
      void main() {
        float d = distance(vUvShadow, vec2(0.5));
        float a = smoothstep(0.5, 0.06, d) * 0.4;
        gl_FragColor = vec4(0.02, 0.14, 0.2, a);
      }`,
  });
  const mesh = new THREE.Mesh(new THREE.PlaneGeometry(2.6, 1.5), material);
  mesh.name = "ContactShadow";
  mesh.rotation.x = -Math.PI / 2;
  // Just below the soles, which now sit exactly on y=0; a positive offset slices
  // a dark ring across the bottom of each foot.
  mesh.position.y = -0.004;
  return mesh;
}

export class TheodoreAvatar {
  constructor(container, options = {}) {
    this.container = container;
    this.assetBase = options.assetBase || "/api/studio/avatar";
    this.motion = options.motion !== false;
    this.motionIntensity = Number(options.motionIntensity ?? 1);
    this.reducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches || false;
    this.persona = options.persona === "male" ? "male" : "female";
    this.state = "loading";
    this.script = { cues: [] };
    this.cueStart = performance.now();
    this.speaking = false;
    this.speechText = "";
    this.speechStart = 0;
    this.speechDuration = 1;
    this.lastBlink = 0;
    this.nextBlink = 2.2;
    this.frame = 0;
    this.lastFrameMs = 0;
    this.nodes = {};
    this.springs = new Map();
    this.pose = new PoseTarget();
    this.face = null;
    this.rig = "procedural";
    this.manifest = null;
    this.disposed = false;
    this.fallback = null;
    this.loader = new GLTFLoader();
  }

  async init() {
    try {
      this.scene = new THREE.Scene();
      this.camera = new THREE.PerspectiveCamera(30, 1, 0.1, 100);
      this.camera.position.set(1.05, 2.45, 8.7);
      this.camera.lookAt(0, 2.05, 0);
      this.renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
      this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.75));
      this.renderer.setClearColor(0x000000, 0);
      this.renderer.outputColorSpace = THREE.SRGBColorSpace;
      this.renderer.domElement.setAttribute("aria-hidden", "true");
      this.container.replaceChildren(this.renderer.domElement);
      this.scene.add(new THREE.HemisphereLight(0xd9fbff, 0x123044, 2.2));
      const key = new THREE.DirectionalLight(0xffffff, 2.1);
      key.position.set(-3, 6, 5);
      this.scene.add(key);
      const rim = new THREE.PointLight(0x39ddff, 4.5, 14);
      rim.position.set(3, 3, 2);
      this.scene.add(rim);
      const fill = new THREE.PointLight(0x9be8ff, 1.6, 12);
      fill.position.set(-2.4, 1.4, 3.2);
      this.scene.add(fill);
      this.scene.add(contactShadow());

      await this.loadManifest();
      await this.loadPersona(this.persona);
      this.resizeObserver = new ResizeObserver(() => this.resize());
      this.resizeObserver.observe(this.container);
      this.resize();
      this.state = "idle";
      this.container.dataset.avatarReady = "true";
      this.lastFrameMs = performance.now();
      this.animate(this.lastFrameMs);
      return this;
    } catch (error) {
      this.state = "fallback";
      this.showFallback();
      console.warn("Theodore 3D avatar unavailable; using silhouette fallback", error);
      return this;
    }
  }

  /**
   * Ask the backend which GLB to use per persona. A dropped-in artist/Meshy
   * model (custom_*.glb, V2 rig) is preferred; absent that we use the
   * procedurally-built presenter. Failure is non-fatal — we fall back to the
   * built-in file names.
   */
  async loadManifest() {
    try {
      const res = await fetch("/api/studio/presenter/manifest", { cache: "no-store" });
      if (res.ok) this.manifest = await res.json();
    } catch (error) {
      this.manifest = null;
    }
  }

  modelUrlFor(persona) {
    const entry = this.manifest?.models?.[persona];
    if (entry?.url) return entry.url;
    return `${this.assetBase}/${MODELS[persona] || MODELS.female}`;
  }

  async loadPersona(persona) {
    const data = await this.loader.loadAsync(this.modelUrlFor(persona));
    if (this.model) {
      this.scene.remove(this.model);
      this.model.traverse((node) => {
        node.geometry?.dispose?.();
        if (Array.isArray(node.material)) node.material.forEach((m) => m.dispose?.());
        else node.material?.dispose?.();
      });
    }
    this.persona = persona;
    this.springs.clear();
    this.model = data.scene;
    this.scene.add(this.model);

    // Resolve whatever rig this GLB uses (ours or the Serenity V2 rig) into our
    // logical joint names, so every teach cue drives it unchanged.
    const resolved = resolveSkeleton(this.model);
    this.nodes = resolved.nodes;
    this.rig = resolved.rig;
    const imported = resolved.rig === "v2";

    this.model.traverse((node) => {
      if (node.isMesh || node.isSkinnedMesh) {
        node.frustumCulled = false;
        if (!node.material) return;
        node.material = Array.isArray(node.material)
          ? node.material.map((m) => m.clone())
          : node.material.clone();
        const mats = Array.isArray(node.material) ? node.material : [node.material];
        for (const material of mats) {
          if (imported) {
            // An artist/Meshy GLB gets the full holographic treatment.
            applyHologram(material);
          } else {
            // Depth writes stay on for the procedural body: it is built from
            // overlapping joint masses and a see-through skin would expose seams.
            material.depthWrite = true;
            if (material.name === "HologramStone" || material.name === "HologramHair") {
              applyFresnel(
                material,
                material.name === "HologramHair" ? 0.45 : 0.85,
                material.name === "HologramHair" ? 0 : 0.6,
              );
            }
          }
        }
      }
    });

    this.face = createFaceDriver(this.model);
    this.basePose = snapshot(this.nodes);
    this.container.dataset.avatarPersona = persona;
    this.container.dataset.avatarRig = this.rig;
  }

  async setPersona(persona) {
    const wanted = persona === "male" ? "male" : "female";
    if (wanted === this.persona || !this.scene) return;
    try {
      await this.loadPersona(wanted);
    } catch (error) {
      console.warn("could not swap presenter model", error);
    }
  }

  showFallback() {
    this.container.dataset.avatarReady = "fallback";
    this.container.innerHTML = `
      <div class="theodore-avatar-fallback" role="img"
        aria-label="Theodore, the Salareen teacher">
        <div class="fallback-crown">♜</div>
        <div class="fallback-head"><i></i><i></i><b></b></div>
        <div class="fallback-body"><span></span><span></span></div>
        <div class="fallback-glow"></div>
      </div>`;
    this.fallback = this.container.firstElementChild;
  }

  resize() {
    if (!this.renderer || !this.camera) return;
    const width = Math.max(1, this.container.clientWidth);
    const height = Math.max(1, this.container.clientHeight);
    this.renderer.setSize(width, height, false);
    this.camera.aspect = width / height;
    // Pull back on narrow panels so the full body still fits the frame.
    const portrait = height > width;
    this.camera.fov = portrait ? 34 : 30;
    this.camera.position.set(1.05, 2.45, portrait ? 9.8 : 8.7);
    this.camera.lookAt(0, 2.05, 0);
    this.camera.updateProjectionMatrix();
  }

  setEnabled(enabled) {
    this.container.hidden = !enabled;
    this.motion = !!enabled;
    if (!enabled) this.stopSpeaking();
  }

  setMotionIntensity(value) {
    this.motionIntensity = clamp(Number(value) || 0, 0, 1.5);
  }

  setReducedMotion(value) {
    this.reducedMotion = !!value;
  }

  setScript(script) {
    this.script = script || { cues: [] };
    this.cueStart = performance.now();
    this.setState(this.script.state || "presenting");
  }

  setState(state) {
    this.state = state || "idle";
    if (this.fallback) this.fallback.dataset.state = this.state;
  }

  speak(text, audio = null) {
    this.speaking = true;
    this.speechText = String(text || "");
    this.speechStart = performance.now();
    this.speechDuration = Math.max(1, this.speechText.split(/\s+/).length / 2.4);
    this.setState("speaking");
    if (audio) {
      const syncDuration = () => {
        if (Number.isFinite(audio.duration) && audio.duration > 0) {
          this.speechDuration = audio.duration;
        }
      };
      audio.addEventListener("loadedmetadata", syncDuration, { once: true });
      audio.addEventListener("ended", () => this.stopSpeaking(), { once: true });
      audio.addEventListener("pause", () => {
        if (!audio.ended) this.stopSpeaking();
      }, { once: true });
      syncDuration();
    }
  }

  speechBoundary(charIndex = 0) {
    if (!this.speaking || !this.speechText) return;
    const fraction = clamp(charIndex / this.speechText.length);
    this.speechStart = performance.now() - fraction * this.speechDuration * 1000;
  }

  stopSpeaking() {
    this.speaking = false;
    if (this.state === "speaking") this.setState("idle");
    if (this.face?.hasVisemes) this.face.setViseme("rest", 1);
    else this.face?.setMouth(0, 0.18);
  }

  spring(key, joint) {
    let value = this.springs.get(key);
    if (!value) {
      value = new Spring(STIFFNESS[joint] ?? STIFFNESS.default);
      this.springs.set(key, value);
    }
    return value;
  }

  /**
   * Every cue overlapping now, each with a fade weight. Blending them means a
   * cue hand-off is a cross-fade rather than a jump between poses.
   */
  activeCues(nowMs) {
    const elapsed = Math.max(0, (nowMs - this.cueStart) / 1000);
    const out = [];
    for (const cue of this.script?.cues || []) {
      const start = Number(cue.start_s || 0);
      const duration = Math.max(0.1, Number(cue.duration_s || 1));
      if (elapsed < start || elapsed > start + duration) continue;
      const phase = (elapsed - start) / duration;
      const fade = Math.min(0.35, duration * 0.3);
      const inWeight = fade > 0 ? clamp((elapsed - start) / fade) : 1;
      const outWeight = fade > 0 ? clamp((start + duration - elapsed) / fade) : 1;
      out.push({ cue, phase, weight: smooth(Math.min(inWeight, outWeight)) });
    }
    return out;
  }

  expressionFor(cues) {
    let name = "warm";
    if (this.state === "celebrate") name = "celebrating";
    else if (this.state === "listening") name = "curious";
    else if (this.state === "thinking") name = "curious";
    else if (this.state === "encouraging") name = "encouraging";
    if (cues.length) {
      const strongest = cues.reduce((a, b) => (b.weight > a.weight ? b : a));
      name = strongest.cue.expression || name;
    }
    return EXPRESSIONS[name] || EXPRESSIONS.warm;
  }

  planFace(t, amount, expression) {
    const pose = this.pose;
    // Idle head and gaze life.
    pose.add("LeftEye", 0, Math.sin(t * 0.67) * 0.025, 0, 1);
    pose.add("RightEye", 0, Math.sin(t * 0.67) * 0.025, 0, 1);
    pose.add("LeftEar", 0, 0, Math.sin(t * 1.3) * 0.018, amount);
    pose.add("RightEar", 0, 0, -Math.sin(t * 1.3) * 0.018, amount);
    pose.add("Crown", 0, 0, Math.sin(t * 0.9) * 0.008, amount);
    pose.addPosition("LeftBrow", "y", expression.brow);
    pose.addPosition("RightBrow", "y", expression.brow);

    const face = this.face;
    if (!face || !face.hasMouth) {
      face?.setExpression(expression.brow, expression.smile);
      return;
    }
    face.beginFrame();
    face.setExpression(expression.brow, expression.smile);

    if (!this.speaking) {
      if (face.hasVisemes) face.setViseme("rest", 1);
      else face.setMouth(0.02, 0.18);
      return;
    }
    const elapsedSpeech = Math.max(0, (performance.now() - this.speechStart) / 1000);
    const scheduled = [...(this.script?.visemes || [])]
      .reverse()
      .find((item) => Number(item.at_s || 0) <= elapsedSpeech);
    if (scheduled) {
      const closed = scheduled.shape === "rest" || scheduled.shape === "mbp";
      const weight = clamp(Number(scheduled.weight ?? 0.8));
      face.setViseme(scheduled.shape, weight);
      pose.add("Jaw", closed ? 0 : 0.05 * weight, 0, 0, 1);
      return;
    }
    const progress = clamp((performance.now() - this.speechStart) / (this.speechDuration * 1000));
    const index = Math.min(
      this.speechText.length - 1,
      Math.max(0, Math.floor(progress * this.speechText.length)),
    );
    const char = (this.speechText[index] || "a").toLowerCase();
    const vowel = /[aeiouyáéíóúüែាិីឹឺុូួើឿៀេែៃោៅ]/u.test(char);
    const wide = /[eiéíីេែៃ]/u.test(char);
    const pulse = 0.45 + Math.abs(Math.sin(t * 11.2)) * 0.55;
    if (face.hasVisemes) {
      face.setViseme(wide ? "ee" : (vowel ? "aa" : "mbp"), (vowel ? 0.85 : 0.4) * pulse);
    } else {
      face.setMouth((vowel ? 0.72 : 0.28) * pulse, wide ? 0.8 : 0.18);
    }
    pose.add("Jaw", (vowel ? 0.055 : 0.018) * pulse, 0, 0, 1);
  }

  applyPose(dt, t) {
    const base = this.basePose;
    for (const [name, rest] of Object.entries(base)) {
      const node = this.nodes[name];
      if (!node) continue;
      const rot = this.pose.rot.get(name) || [0, 0, 0];
      node.rotation.set(
        rest.rotation.x + this.spring(`${name}.rx`, name).step(rot[0], dt),
        rest.rotation.y + this.spring(`${name}.ry`, name).step(rot[1], dt),
        rest.rotation.z + this.spring(`${name}.rz`, name).step(rot[2], dt),
      );
      const pos = this.pose.pos.get(name);
      node.position.set(
        rest.position.x + this.spring(`${name}.px`, name).step(pos ? pos.x : 0, dt),
        rest.position.y + this.spring(`${name}.py`, name).step(pos ? pos.y : 0, dt),
        rest.position.z + this.spring(`${name}.pz`, name).step(pos ? pos.z : 0, dt),
      );
      const scale = this.pose.scale.get(name);
      node.scale.set(
        rest.scale.x * (1 + this.spring(`${name}.sx`, name).step(scale ? scale.x : 0, dt)),
        rest.scale.y * (1 + this.spring(`${name}.sy`, name).step(scale ? scale.y : 0, dt)),
        rest.scale.z * (1 + this.spring(`${name}.sz`, name).step(scale ? scale.z : 0, dt)),
      );
    }

    // Blink rides on top of the eased eye scale so it never looks stepped.
    if (t - this.lastBlink > this.nextBlink) {
      this.lastBlink = t;
      this.nextBlink = 2.4 + Math.random() * 3.4;
    }
    const blinkAge = t - this.lastBlink;
    const blink = blinkAge < 0.17 ? Math.sin(smooth(clamp(blinkAge / 0.17)) * Math.PI) : 0;
    if (this.face?.hasBlink) {
      // Rig has real eyelid blendshapes: drive them instead of squashing eyes.
      this.face.setBlink(blink);
    } else {
      const lid = Math.max(0.08, 1 - blink * 0.92);
      for (const eye of ["LeftEye", "RightEye"]) {
        const node = this.nodes[eye];
        if (node) node.scale.y = (base[eye]?.scale.y ?? 1) * lid;
      }
    }

    this.face?.update(dt);
  }

  animate(nowMs) {
    if (this.disposed) return;
    this.frame = requestAnimationFrame((value) => this.animate(value));
    if (!this.renderer || !this.scene || !this.camera || !this.basePose) return;
    // Clamp the step so a stalled tab resumes smoothly instead of snapping.
    const dt = Math.min(0.05, Math.max(0.001, (nowMs - this.lastFrameMs) / 1000));
    this.lastFrameMs = nowMs;
    const t = nowMs / 1000;
    const amount = this.motion && !this.reducedMotion ? this.motionIntensity : 0.16;

    this.pose.clear();
    const breath = Math.sin(t * 1.7) * 0.015 * amount;
    this.pose.addScale("Chest", "y", breath);
    this.pose.addPosition("Spine", "y", breath * 0.35);
    this.pose.add("Hips", 0, Math.sin(t * 0.43) * 0.025, Math.sin(t * 0.61) * 0.018, amount);
    this.pose.add("Spine", Math.sin(t * 0.52) * 0.012, 0, -Math.sin(t * 0.61) * 0.018, amount);
    this.pose.add("Head", Math.sin(t * 0.47) * 0.018, Math.sin(t * 0.31) * 0.025, 0, amount);

    const cues = this.activeCues(nowMs);
    if (cues.length) {
      for (const { cue, phase, weight } of cues) {
        poseGesture(
          this.pose,
          cue.gesture || "explain",
          phase,
          clamp(Number(cue.intensity ?? 0.8), 0, 1.5) * amount * weight,
        );
        if (cue.gaze === "slide") this.pose.add("Head", 0, -0.32, 0, amount * weight);
        if (cue.gaze === "learner") this.pose.add("Head", 0, 0.08, 0, amount * weight);
      }
    } else if (this.state === "listening") {
      poseGesture(this.pose, "listen", 0.5, amount);
    } else if (this.state === "celebrate") {
      poseGesture(this.pose, "celebrate", (t % 1.5) / 1.5, amount);
    } else if (this.state === "thinking" || this.state === "ask") {
      poseGesture(this.pose, "ask", 0.5, amount);
    } else if (this.state === "encouraging") {
      poseGesture(this.pose, "open-palm", 0.5, amount * 0.7);
    } else if (this.speaking) {
      poseGesture(this.pose, "explain", (t % 2.4) / 2.4, amount * 0.55);
    }

    this.planFace(t, amount, this.expressionFor(cues));
    this.applyPose(dt, t);
    this.renderer.render(this.scene, this.camera);
  }

  dispose() {
    this.disposed = true;
    cancelAnimationFrame(this.frame);
    this.resizeObserver?.disconnect();
    this.scene?.traverse((node) => {
      node.geometry?.dispose?.();
      if (Array.isArray(node.material)) node.material.forEach((m) => m.dispose?.());
      else node.material?.dispose?.();
    });
    this.renderer?.dispose();
  }
}

export async function createTheodoreAvatar(container, options = {}) {
  const avatar = new TheodoreAvatar(container, options);
  await avatar.init();
  return avatar;
}

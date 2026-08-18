import * as THREE from "three";
import { GLTFLoader } from "./loaders/GLTFLoader.js";

const JOINTS = [
  "AvatarRoot", "Hips", "Spine", "Chest", "Neck", "Head", "Jaw",
  "LeftShoulder", "RightShoulder", "LeftElbow", "RightElbow",
  "LeftWrist", "RightWrist", "LeftFingers", "RightFingers",
  "LeftHip", "RightHip", "LeftKnee", "RightKnee",
  "LeftAnkle", "RightAnkle", "LeftEye", "RightEye",
  "LeftBrow", "RightBrow", "LeftEar", "RightEar", "Crown",
];

const clamp = (v, lo = 0, hi = 1) => Math.max(lo, Math.min(hi, v));
const ease = (v) => v * v * (3 - 2 * v);

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

function resetPose(nodes, base) {
  for (const [name, pose] of Object.entries(base)) {
    const node = nodes[name];
    if (!node) continue;
    node.position.copy(pose.position);
    node.rotation.copy(pose.rotation);
    node.scale.copy(pose.scale);
  }
}

function rotate(nodes, name, x = 0, y = 0, z = 0, weight = 1) {
  const node = nodes[name];
  if (!node) return;
  node.rotation.x += x * weight;
  node.rotation.y += y * weight;
  node.rotation.z += z * weight;
}

function poseGesture(nodes, name, phase, intensity) {
  const s = Math.sin(Math.PI * clamp(phase));
  const w = s * intensity;
  switch (name) {
    case "explain":
    case "open-palm":
      rotate(nodes, "LeftShoulder", -0.22, 0, -0.72, w);
      rotate(nodes, "LeftElbow", -0.28, 0, -0.42, w);
      rotate(nodes, "LeftWrist", 0.12, 0, -0.18, w);
      rotate(nodes, "RightShoulder", -0.16, 0, 0.48, w * 0.7);
      rotate(nodes, "RightElbow", -0.18, 0, 0.35, w * 0.7);
      break;
    case "point-left":
    case "point-to-slide":
      rotate(nodes, "LeftShoulder", -0.12, 0.12, -1.2, w);
      rotate(nodes, "LeftElbow", 0.05, 0, -0.22, w);
      rotate(nodes, "LeftWrist", 0, 0.1, 0.12, w);
      rotate(nodes, "Head", 0, -0.28, 0, w);
      break;
    case "point-right":
      rotate(nodes, "RightShoulder", -0.12, -0.12, 1.2, w);
      rotate(nodes, "RightElbow", 0.05, 0, 0.22, w);
      rotate(nodes, "RightWrist", 0, -0.1, -0.12, w);
      rotate(nodes, "Head", 0, 0.28, 0, w);
      break;
    case "count":
      rotate(nodes, "RightShoulder", -0.18, 0, 0.72, w);
      rotate(nodes, "RightElbow", -0.45, 0, 0.62, w);
      rotate(nodes, "RightWrist", -0.2, 0.1, -0.15, w);
      rotate(nodes, "RightFingers", 0.18 * Math.sin(phase * Math.PI * 4), 0, 0, w);
      break;
    case "compare":
      rotate(nodes, "LeftShoulder", -0.1, 0, -0.88, w);
      rotate(nodes, "RightShoulder", -0.1, 0, 0.88, w);
      rotate(nodes, "LeftElbow", -0.28, 0, -0.32, w);
      rotate(nodes, "RightElbow", -0.28, 0, 0.32, w);
      break;
    case "caution":
    case "stop":
      rotate(nodes, "RightShoulder", -0.35, 0, 0.88, w);
      rotate(nodes, "RightElbow", -0.55, 0, 0.48, w);
      rotate(nodes, "RightWrist", -0.55, 0, -0.12, w);
      rotate(nodes, "Head", 0.08, 0, 0, w);
      break;
    case "steer":
      rotate(nodes, "LeftShoulder", -0.62, 0, -0.28, w);
      rotate(nodes, "RightShoulder", -0.62, 0, 0.28, w);
      rotate(nodes, "LeftElbow", -0.48, 0, -0.16, w);
      rotate(nodes, "RightElbow", -0.48, 0, 0.16, w);
      rotate(nodes, "Spine", 0, 0.08 * Math.sin(phase * Math.PI * 2), 0, w);
      break;
    case "shoulder-check":
      rotate(nodes, "Chest", 0, -0.34, 0, w);
      rotate(nodes, "Neck", 0, -0.42, 0, w);
      rotate(nodes, "Head", 0, -0.38, 0, w);
      break;
    case "seatbelt":
      rotate(nodes, "RightShoulder", -0.18, 0, 0.75, w);
      rotate(nodes, "RightElbow", -0.72, 0, 0.42, w);
      rotate(nodes, "RightWrist", -0.2, 0, -0.24, w);
      rotate(nodes, "Chest", 0, 0, 0.08, w);
      break;
    case "phone-away":
      rotate(nodes, "RightShoulder", -0.35, 0, 0.38, w);
      rotate(nodes, "RightElbow", -1.05, 0, 0.2, w);
      rotate(nodes, "RightWrist", 0.35, 0, -0.2, w);
      rotate(nodes, "Head", 0, 0.18, 0, w);
      break;
    case "wash-hands":
    case "sanitize":
      rotate(nodes, "LeftShoulder", -0.48, 0, -0.34, w);
      rotate(nodes, "RightShoulder", -0.48, 0, 0.34, w);
      rotate(nodes, "LeftElbow", -0.72, 0, -0.38, w);
      rotate(nodes, "RightElbow", -0.72, 0, 0.38, w);
      rotate(nodes, "LeftWrist", 0, 0.45 * Math.sin(phase * Math.PI * 8), 0, w);
      rotate(nodes, "RightWrist", 0, -0.45 * Math.sin(phase * Math.PI * 8), 0, w);
      break;
    case "gloves":
      rotate(nodes, "LeftShoulder", -0.45, 0, -0.28, w);
      rotate(nodes, "RightShoulder", -0.38, 0, 0.38, w);
      rotate(nodes, "LeftElbow", -0.7, 0, -0.25, w);
      rotate(nodes, "RightElbow", -0.8, 0, 0.28, w);
      rotate(nodes, "RightWrist", 0, 0, -0.5, w);
      break;
    case "thermometer":
      rotate(nodes, "RightShoulder", -0.48, 0, 0.58, w);
      rotate(nodes, "RightElbow", -0.7, 0, 0.45, w);
      rotate(nodes, "RightWrist", -0.25, 0, -0.2, w);
      rotate(nodes, "Head", 0.12, 0.16, 0, w);
      break;
    case "ask":
      rotate(nodes, "Head", -0.08, 0, 0.08, w);
      rotate(nodes, "LeftShoulder", -0.14, 0, -0.42, w);
      rotate(nodes, "LeftElbow", -0.38, 0, -0.3, w);
      break;
    case "listen":
      rotate(nodes, "Head", -0.04, 0, -0.1, w);
      rotate(nodes, "Spine", -0.04, 0, 0, w);
      break;
    case "celebrate":
      rotate(nodes, "LeftShoulder", -0.1, 0, -1.48, w);
      rotate(nodes, "RightShoulder", -0.1, 0, 1.48, w);
      rotate(nodes, "LeftElbow", -0.28, 0, -0.28, w);
      rotate(nodes, "RightElbow", -0.28, 0, 0.28, w);
      break;
    case "demonstrate":
      rotate(nodes, "RightShoulder", -0.24, 0, 0.72, w);
      rotate(nodes, "RightElbow", -0.52, 0, 0.42, w);
      rotate(nodes, "Chest", 0, -0.12, 0, w);
      break;
    case "transition":
      rotate(nodes, "Spine", 0, 0.15, 0, w);
      rotate(nodes, "Head", 0, -0.12, 0, w);
      break;
    default:
      break;
  }
}

export class TheodoreAvatar {
  constructor(container, options = {}) {
    this.container = container;
    this.assetBase = options.assetBase || "/api/studio/avatar";
    this.motion = options.motion !== false;
    this.motionIntensity = Number(options.motionIntensity ?? 1);
    this.reducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches || false;
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
    this.nodes = {};
    this.disposed = false;
    this.fallback = null;
  }

  async init() {
    try {
      this.scene = new THREE.Scene();
      this.camera = new THREE.PerspectiveCamera(28, 1, 0.1, 100);
      this.camera.position.set(0, 2.15, 8.9);
      this.camera.lookAt(0, 2.05, 0);
      this.renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
      this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.75));
      this.renderer.setClearColor(0x000000, 0);
      this.renderer.outputColorSpace = THREE.SRGBColorSpace;
      this.renderer.domElement.setAttribute("aria-hidden", "true");
      this.container.replaceChildren(this.renderer.domElement);
      this.scene.add(new THREE.HemisphereLight(0xd9fbff, 0x123044, 2.5));
      const key = new THREE.DirectionalLight(0xffffff, 2.2);
      key.position.set(-3, 6, 5);
      this.scene.add(key);
      const rim = new THREE.PointLight(0x39ddff, 5, 12);
      rim.position.set(3, 3, 2);
      this.scene.add(rim);
      const data = await new GLTFLoader().loadAsync(`${this.assetBase}/theodore.glb`);
      this.model = data.scene;
      this.scene.add(this.model);
      this.model.traverse((node) => {
        if (node.name) this.nodes[node.name] = node;
        if (node.isMesh && node.material) {
          node.material = node.material.clone();
          node.material.transparent = true;
          node.material.opacity = node.material.name === "Features" ? 0.9 : 0.74;
          node.material.depthWrite = false;
        }
      });
      this.basePose = snapshot(this.nodes);
      this.mouth = this.nodes.Mouth;
      this.resizeObserver = new ResizeObserver(() => this.resize());
      this.resizeObserver.observe(this.container);
      this.resize();
      this.state = "idle";
      this.container.dataset.avatarReady = "true";
      this.animate(performance.now());
      return this;
    } catch (error) {
      this.state = "fallback";
      this.showFallback();
      console.warn("Theodore 3D avatar unavailable; using silhouette fallback", error);
      return this;
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
    if (this.mouth?.morphTargetInfluences) {
      this.mouth.morphTargetInfluences[0] = 0;
      this.mouth.morphTargetInfluences[1] = 0;
    }
  }

  cueAt(nowMs) {
    const elapsed = Math.max(0, (nowMs - this.cueStart) / 1000);
    for (const cue of this.script?.cues || []) {
      const start = Number(cue.start_s || 0);
      const duration = Math.max(0.1, Number(cue.duration_s || 1));
      if (elapsed >= start && elapsed <= start + duration) {
        return { cue, phase: (elapsed - start) / duration };
      }
    }
    return null;
  }

  applyFace(t) {
    const blinkWindow = t - this.lastBlink;
    if (blinkWindow > this.nextBlink) {
      this.lastBlink = t;
      this.nextBlink = 2.4 + Math.random() * 3.4;
    }
    const blinkAge = t - this.lastBlink;
    const blink = blinkAge < 0.16 ? Math.sin((blinkAge / 0.16) * Math.PI) : 0;
    const eyeY = Math.max(0.08, 1 - blink * 0.92);
    if (this.nodes.LeftEye) this.nodes.LeftEye.scale.y *= eyeY;
    if (this.nodes.RightEye) this.nodes.RightEye.scale.y *= eyeY;
    rotate(this.nodes, "LeftEye", 0, Math.sin(t * 0.67) * 0.025, 0, 1);
    rotate(this.nodes, "RightEye", 0, Math.sin(t * 0.67) * 0.025, 0, 1);
    rotate(this.nodes, "LeftEar", 0, 0, Math.sin(t * 1.3) * 0.018, 1);
    rotate(this.nodes, "RightEar", 0, 0, -Math.sin(t * 1.3) * 0.018, 1);
    rotate(this.nodes, "Crown", 0, 0, Math.sin(t * 0.9) * 0.008, 1);

    if (!this.mouth?.morphTargetInfluences) return;
    if (!this.speaking) {
      this.mouth.morphTargetInfluences[0] *= 0.72;
      this.mouth.morphTargetInfluences[1] = 0.22;
      return;
    }
    const elapsedSpeech = Math.max(0, (performance.now() - this.speechStart) / 1000);
    const scheduled = [...(this.script?.visemes || [])]
      .reverse()
      .find((item) => Number(item.at_s || 0) <= elapsedSpeech);
    if (scheduled) {
      const openShapes = ["aa", "oh", "l", "wq"];
      const wideShapes = ["ee", "fv"];
      const closed = scheduled.shape === "rest" || scheduled.shape === "mbp";
      const weight = clamp(Number(scheduled.weight ?? 0.8));
      this.mouth.morphTargetInfluences[0] = closed ? 0.04 : (openShapes.includes(scheduled.shape) ? 0.78 : 0.35) * weight;
      this.mouth.morphTargetInfluences[1] = wideShapes.includes(scheduled.shape) ? 0.82 * weight : 0.16;
      rotate(this.nodes, "Jaw", closed ? 0 : 0.05 * weight, 0, 0, 1);
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
    const pulse = 0.45 + Math.abs(Math.sin(t * 13.4)) * 0.55;
    this.mouth.morphTargetInfluences[0] = (vowel ? 0.72 : 0.28) * pulse;
    this.mouth.morphTargetInfluences[1] = wide ? 0.8 : 0.18;
    rotate(this.nodes, "Jaw", (vowel ? 0.055 : 0.018) * pulse, 0, 0, 1);
  }

  animate(nowMs) {
    if (this.disposed) return;
    this.frame = requestAnimationFrame((value) => this.animate(value));
    if (!this.renderer || !this.scene || !this.camera || !this.basePose) return;
    const t = nowMs / 1000;
    resetPose(this.nodes, this.basePose);
    const amount = this.motion && !this.reducedMotion ? this.motionIntensity : 0.16;
    const breath = Math.sin(t * 1.7) * 0.015 * amount;
    if (this.nodes.Chest) this.nodes.Chest.scale.y += breath;
    if (this.nodes.Spine) this.nodes.Spine.position.y += breath * 0.35;
    rotate(this.nodes, "Hips", 0, Math.sin(t * 0.43) * 0.025, Math.sin(t * 0.61) * 0.018, amount);
    rotate(this.nodes, "Spine", Math.sin(t * 0.52) * 0.012, 0, -Math.sin(t * 0.61) * 0.018, amount);
    rotate(this.nodes, "Head", Math.sin(t * 0.47) * 0.018, Math.sin(t * 0.31) * 0.025, 0, amount);

    const active = this.cueAt(nowMs);
    if (active) {
      poseGesture(
        this.nodes,
        active.cue.gesture || "explain",
        ease(active.phase),
        clamp(Number(active.cue.intensity ?? 0.8), 0, 1.5) * amount,
      );
      if (active.cue.gaze === "slide") rotate(this.nodes, "Head", 0, -0.32, 0, amount);
      if (active.cue.gaze === "learner") rotate(this.nodes, "Head", 0, 0.08, 0, amount);
    } else if (this.state === "listening") {
      poseGesture(this.nodes, "listen", 0.5, amount);
    } else if (this.state === "celebrate") {
      poseGesture(this.nodes, "celebrate", (t % 1.5) / 1.5, amount);
    } else if (this.state === "thinking") {
      poseGesture(this.nodes, "ask", 0.5, amount);
    } else if (this.state === "ask") {
      poseGesture(this.nodes, "ask", 0.5, amount);
    } else if (this.state === "encouraging") {
      poseGesture(this.nodes, "open-palm", 0.5, amount * 0.7);
    } else if (this.speaking) {
      poseGesture(this.nodes, "explain", (t % 2.4) / 2.4, amount * 0.55);
    }
    this.applyFace(t);
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

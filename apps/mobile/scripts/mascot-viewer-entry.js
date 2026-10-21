/**
 * Bundled into assets/mascot3d/viewer.txt and played inside a WebView.
 * Classic IIFE (no CDN, no ES modules) so iOS and Android WebViews can
 * load it from a file URL next to Mascot.glb and draco_decoder.js.
 */
import * as THREE from "three";
import { DRACOLoader } from "three/examples/jsm/loaders/DRACOLoader.js";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";

const IDLE_ROTATION = [
  "Big_Wave_Hello",
  "Confident_Strut",
  "Indoor_Swing",
  "Boom_Dance",
  "Wave_for_Help_1",
  "Jump_Rope",
  "_360_Power_Spin_Jump",
  "Wave_for_Help_2",
];

function report(err) {
  const msg = String((err && err.message) || err || "mascot failed");
  if (window.ReactNativeWebView) window.ReactNativeWebView.postMessage("error:" + msg);
}

function contrastByte(value) {
  if (value < 0) return 0;
  if (value > 255) return 255;
  return Math.round(value);
}

function gradeStoneByte(value) {
  const darkened = value * 0.88;
  const curved = (darkened - 120) * 1.12 + 120;
  return contrastByte(curved < 22 ? 22 : curved);
}

function sealAtlasHoles(data, width, height) {
  const count = width * height;
  const hole = new Uint8Array(count);
  for (let p = 0, i = 0; p < count; p += 1, i += 4) {
    const max = data[i] > data[i + 1]
      ? (data[i] > data[i + 2] ? data[i] : data[i + 2])
      : (data[i + 1] > data[i + 2] ? data[i + 1] : data[i + 2]);
    hole[p] = max < 8 ? 1 : 0;
  }
  const qx = new Int32Array(count);
  const qy = new Int32Array(count);
  const color = new Uint8Array(count * 3);
  const filled = new Uint8Array(count);
  let tail = 0;
  const push = (x, y, r, g, b) => {
    const p = y * width + x;
    if (!hole[p] || filled[p]) return;
    filled[p] = 1;
    const o = p * 3;
    color[o] = r;
    color[o + 1] = g;
    color[o + 2] = b;
    qx[tail] = x;
    qy[tail] = y;
    tail += 1;
  };
  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const p = y * width + x;
      if (hole[p]) continue;
      const i = p * 4;
      if (x > 0) push(x - 1, y, data[i], data[i + 1], data[i + 2]);
      if (x + 1 < width) push(x + 1, y, data[i], data[i + 1], data[i + 2]);
      if (y > 0) push(x, y - 1, data[i], data[i + 1], data[i + 2]);
      if (y + 1 < height) push(x, y + 1, data[i], data[i + 1], data[i + 2]);
    }
  }
  let head = 0;
  while (head < tail) {
    const x = qx[head];
    const y = qy[head];
    head += 1;
    const o = (y * width + x) * 3;
    const r = color[o];
    const g = color[o + 1];
    const b = color[o + 2];
    if (x > 0) push(x - 1, y, r, g, b);
    if (x + 1 < width) push(x + 1, y, r, g, b);
    if (y > 0) push(x, y - 1, r, g, b);
    if (y + 1 < height) push(x, y + 1, r, g, b);
  }
  for (let p = 0; p < count; p += 1) {
    if (!filled[p]) continue;
    const i = p * 4;
    const o = p * 3;
    data[i] = color[o];
    data[i + 1] = color[o + 1];
    data[i + 2] = color[o + 2];
  }
  for (let pass = 0; pass < 2; pass += 1) {
    const extra = [];
    for (let y = 0; y < height; y += 1) {
      for (let x = 0; x < width; x += 1) {
        const p = y * width + x;
        if (!filled[p]) continue;
        const i = p * 4;
        const r = data[i];
        const g = data[i + 1];
        const b = data[i + 2];
        const around = [
          x > 0 ? p - 1 : -1,
          x + 1 < width ? p + 1 : -1,
          y > 0 ? p - width : -1,
          y + 1 < height ? p + width : -1,
        ];
        for (const n of around) {
          if (n < 0 || filled[n]) continue;
          const j = n * 4;
          const max = data[j] > data[j + 1]
            ? (data[j] > data[j + 2] ? data[j] : data[j + 2])
            : (data[j + 1] > data[j + 2] ? data[j + 1] : data[j + 2]);
          if (max < 48) extra.push(n, r, g, b);
        }
      }
    }
    for (let k = 0; k < extra.length; k += 4) {
      const n = extra[k];
      if (filled[n]) continue;
      filled[n] = 1;
      const j = n * 4;
      data[j] = extra[k + 1];
      data[j + 1] = extra[k + 2];
      data[j + 2] = extra[k + 3];
    }
  }
}

function softenAlbedo(map) {
  const image = map.image;
  if (!image || !image.width || !image.height) return;
  const width = image.width;
  const height = image.height;
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  if (!ctx) return;
  ctx.drawImage(image, 0, 0, width, height);
  const pixels = ctx.getImageData(0, 0, width, height);
  sealAtlasHoles(pixels.data, width, height);
  for (let i = 0; i < pixels.data.length; i += 4) {
    pixels.data[i] = gradeStoneByte(pixels.data[i]);
    pixels.data[i + 1] = gradeStoneByte(pixels.data[i + 1]);
    pixels.data[i + 2] = gradeStoneByte(pixels.data[i + 2]);
  }
  ctx.putImageData(pixels, 0, 0);
  const smooth = document.createElement("canvas");
  smooth.width = width * 2;
  smooth.height = height * 2;
  const smoothCtx = smooth.getContext("2d");
  if (!smoothCtx) {
    map.image = canvas;
  } else {
    smoothCtx.imageSmoothingEnabled = true;
    smoothCtx.imageSmoothingQuality = "high";
    smoothCtx.drawImage(canvas, 0, 0, smooth.width, smooth.height);
    map.image = smooth;
  }
  map.magFilter = THREE.LinearFilter;
  map.minFilter = THREE.LinearMipmapLinearFilter;
  map.generateMipmaps = true;
  map.anisotropy = 8;
  map.needsUpdate = true;
}

function clarifyStone(root) {
  root.traverse((obj) => {
    if (!obj.isMesh || !obj.material) return;
    const mats = Array.isArray(obj.material) ? obj.material : [obj.material];
    for (const mat of mats) {
      if (!mat.isMeshStandardMaterial) continue;
      if (mat.map) softenAlbedo(mat.map);
      mat.metalness = Math.min(mat.metalness ?? 1, 0.08);
      if ((mat.roughness ?? 1) < 0.72) mat.roughness = 0.72;
      mat.envMapIntensity = 0.12;
      mat.transparent = false;
      mat.alphaTest = 0;
      mat.depthWrite = true;
      if (mat.normalScale) mat.normalScale.set(0.45, 0.45);
      mat.needsUpdate = true;
    }
  });
}

function frameCharacter(root, camera) {
  root.updateMatrixWorld(true);
  const box = new THREE.Box3().setFromObject(root);
  const size = box.getSize(new THREE.Vector3());
  const height = Math.max(size.y, 0.001);
  root.scale.multiplyScalar(1.7 / height);
  root.updateMatrixWorld(true);
  const fitted = new THREE.Box3().setFromObject(root);
  const center = fitted.getCenter(new THREE.Vector3());
  root.position.x -= center.x;
  root.position.z -= center.z;
  root.position.y -= fitted.min.y;
  camera.position.set(0, 0.95, 2.55);
  camera.lookAt(0, 0.82, 0);
}

function playNamed(mixer, animations, name) {
  const clip = animations.find((item) => item.name === name) || animations[0];
  if (!clip) return;
  mixer.stopAllAction();
  mixer.clipAction(clip).reset().play();
}

export function start(options) {
  try {
    const modelUrl = (options && options.modelUrl) || "Mascot.glb";
    const requested = (options && options.clip) || "idle";
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setClearColor(0x000000, 0);
    if (THREE.SRGBColorSpace) renderer.outputColorSpace = THREE.SRGBColorSpace;
    document.body.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(30, window.innerWidth / Math.max(window.innerHeight, 1), 0.05, 50);
    scene.add(new THREE.AmbientLight(0xffffff, 0.46));
    scene.add(new THREE.HemisphereLight(0xf3e6cf, 0x3a2e22, 0.38));
    const key = new THREE.DirectionalLight(0xfff1d6, 1.05);
    key.position.set(1.4, 3.6, 2.2);
    scene.add(key);
    const fill = new THREE.DirectionalLight(0xf0e2c4, 0.22);
    fill.position.set(-2.4, 1.1, 1.6);
    scene.add(fill);
    const rim = new THREE.DirectionalLight(0xf4e7cf, 0.18);
    rim.position.set(-0.4, 1.8, -2.6);
    scene.add(rim);

    const draco = new DRACOLoader();
    draco.setDecoderPath("./");
    draco.setDecoderConfig({ type: "js" });
    const loader = new GLTFLoader();
    loader.setDRACOLoader(draco);
    loader.load(modelUrl, (gltf) => {
      const root = gltf.scene;
      clarifyStone(root);
      scene.add(root);
      frameCharacter(root, camera);
      const mixer = new THREE.AnimationMixer(root);
      const clock = new THREE.Clock();
      let index = 0;
      const rotate = requested === "idle";
      playNamed(mixer, gltf.animations, rotate ? IDLE_ROTATION[0] : requested);
      let elapsed = 0;
      const loop = () => {
        requestAnimationFrame(loop);
        const delta = clock.getDelta();
        mixer.update(delta);
        if (rotate) {
          elapsed += delta;
          if (elapsed > 5) {
            elapsed = 0;
            index = (index + 1) % IDLE_ROTATION.length;
            playNamed(mixer, gltf.animations, IDLE_ROTATION[index]);
          }
        }
        renderer.render(scene, camera);
      };
      loop();
      if (window.ReactNativeWebView) window.ReactNativeWebView.postMessage("ready");
    }, undefined, report);

    window.addEventListener("resize", () => {
      camera.aspect = window.innerWidth / Math.max(window.innerHeight, 1);
      camera.updateProjectionMatrix();
      renderer.setSize(window.innerWidth, window.innerHeight);
    });
  } catch (err) {
    report(err);
  }
}

window.addEventListener("error", (event) => report(event.message || event.error));

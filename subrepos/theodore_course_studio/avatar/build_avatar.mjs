import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import * as THREE from "three";
import { GLTFExporter } from "three/addons/exporters/GLTFExporter.js";

const root = path.dirname(fileURLToPath(import.meta.url));
const dist = path.join(root, "..", "src", "theodore_course_studio", "avatar_static");
fs.mkdirSync(dist, { recursive: true });
fs.mkdirSync(path.join(dist, "utils"), { recursive: true });
fs.mkdirSync(path.join(dist, "loaders"), { recursive: true });

// GLTFExporter uses browser FileReader even when exporting an ArrayBuffer.
globalThis.FileReader = class {
  result = null;
  onloadend = null;
  readAsArrayBuffer(blob) {
    blob.arrayBuffer().then((value) => {
      this.result = value;
      if (this.onloadend) this.onloadend();
    });
  }
  readAsDataURL(blob) {
    blob.arrayBuffer().then((value) => {
      this.result = `data:${blob.type};base64,${Buffer.from(value).toString("base64")}`;
      if (this.onloadend) this.onloadend();
    });
  }
};

// A 2.75-head chibi canon matching the chibi-Buddha reference: ~1.5 units of
// skull, ~1.3 of torso, ~1.4 of leg. Total height stays 4.15 units so the runtime
// camera framing is unchanged — only the distribution between skull and body
// moves. At 3.5 heads and above the limbs still read as sticks beside the skull.
const H = 4.15;
const HEADS = 2.75;
const HEAD = H / HEADS;

const Y = {
  top: H,
  headCenter: 3.38,
  chin: 2.64,
  head: 2.68,
  neck: 2.6,
  shoulderLine: 2.48,
  chest: 2.22,
  spine: 1.85,
  hips: 1.42,
  crotch: 1.32,
  shoulder: 2.44,
  elbow: 1.95,
  wrist: 1.55,
  fingers: 1.46,
  hip: 1.38,
  knee: 0.72,
  // Chosen so the squashed sole lands exactly on y=0 rather than hovering.
  ankle: 0.1,
  floor: 0,
};

// One parameter table drives both presenters, so the rig, cue names and every
// choreography script stay identical between them.
const VARIANTS = {
  female: {
    label: "Theodora",
    shoulderHalf: 0.46,
    chestRx: 0.4,
    // Depth matters as much as width here: a torso this shallow beside a spherical
    // head reads as a lollipop in profile.
    chestRz: 0.34,
    bust: 0.03,
    // Widest at the belly, not the chest: the reference silhouette is an egg, so
    // waist > chest here on purpose. A pinched waist reads as gaunt beside a
    // skull this size.
    waistRx: 0.455,
    waistRz: 0.4,
    hipsRx: 0.42,
    hipsRz: 0.35,
    armR: 0.175,
    wristR: 0.135,
    thighR: 0.3,
    ankleR: 0.16,
    // Near-spherical: with ry noticeably larger than rx the skull reads as an egg.
    headRx: 0.755,
    headRy: 0.77,
    headRz: 0.735,
    jawTaper: 0.96,
    neckR: 0.17,
    hair: "long",
    browThickness: 0.032,
    lipFullness: 1.15,
  },
  male: {
    label: "Theodore",
    shoulderHalf: 0.51,
    chestRx: 0.45,
    chestRz: 0.36,
    bust: 0,
    waistRx: 0.49,
    waistRz: 0.42,
    hipsRx: 0.44,
    hipsRz: 0.37,
    armR: 0.19,
    wristR: 0.145,
    thighR: 0.315,
    ankleR: 0.17,
    headRx: 0.775,
    headRy: 0.775,
    headRz: 0.75,
    jawTaper: 0.97,
    neckR: 0.185,
    hair: "short",
    browThickness: 0.038,
    lipFullness: 0.92,
  },
};

const clamp = (v, lo = 0, hi = 1) => Math.max(lo, Math.min(hi, v));
const lerp = (a, b, t) => a + (b - a) * t;
const smooth = (t) => t * t * (3 - 2 * t);

// Forward lean, baked into the bind pose rather than animated, so the presenter
// reads as leaning in to teach even when idle. Zero at the hips so the legs stay
// planted, easing forward toward the crown.
const LEAN = 0.15;

function leanZ(y) {
  return LEAN * smooth(clamp((y - Y.hips) / (Y.top - Y.hips)));
}

// Arms splay outward as they descend so the hands clear the belly instead of
// sinking into it. Bones and skin share this curve, so a raised arm still tracks.
const ARM_SPLAY = 0.095;

function armSplay(v, y) {
  const top = Y.shoulder + v.armR * 1.1;
  const bottom = Y.wrist - 0.01;
  return ARM_SPLAY * smooth(clamp((top - y) / (top - bottom)));
}

function materials() {
  return {
    stone: new THREE.MeshStandardMaterial({
      name: "HologramStone",
      color: 0x86ecff,
      emissive: 0x0f5f7d,
      emissiveIntensity: 0.55,
      roughness: 0.52,
      metalness: 0.05,
      transparent: true,
      // Serenity hologram: translucent body so the storyboard reads through behind Theodore.
      opacity: 0.62,
      depthWrite: false,
    }),
    light: new THREE.MeshStandardMaterial({
      name: "FeatureLight",
      color: 0xeafdff,
      emissive: 0x74d8f0,
      emissiveIntensity: 0.48,
      roughness: 0.3,
      transparent: true,
      opacity: 0.68,
      depthWrite: false,
    }),
    gold: new THREE.MeshStandardMaterial({
      name: "CrownGold",
      color: 0xf4d688,
      emissive: 0x6a4a12,
      emissiveIntensity: 0.4,
      roughness: 0.48,
      metalness: 0.35,
      transparent: true,
      opacity: 0.78,
      depthWrite: false,
    }),
    dark: new THREE.MeshStandardMaterial({
      name: "Features",
      color: 0x0d2732,
      emissive: 0x061821,
      emissiveIntensity: 0.28,
      roughness: 0.7,
      transparent: true,
      opacity: 0.58,
      depthWrite: false,
    }),
    hair: new THREE.MeshStandardMaterial({
      name: "HologramHair",
      color: 0x2fbfe8,
      emissive: 0x0b4a63,
      emissiveIntensity: 0.62,
      roughness: 0.38,
      metalness: 0.1,
      transparent: true,
      opacity: 0.6,
      depthWrite: false,
    }),
  };
}

/**
 * Accumulates one continuous skinned body. Every part is written into shared
 * arrays so the export is a single SkinnedMesh: limbs bend with the bones
 * instead of separating into floating primitives.
 */
class SkinBuilder {
  constructor(boneIndex) {
    this.boneIndex = boneIndex;
    this.position = [];
    this.skinIndex = [];
    this.skinWeight = [];
    this.index = [];
  }

  get count() {
    return this.position.length / 3;
  }

  vertex(x, y, z, weights) {
    this.position.push(x, y, z);
    const entries = weights
      .filter((w) => w[1] > 0.0005)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 4);
    const total = entries.reduce((sum, w) => sum + w[1], 0) || 1;
    for (let i = 0; i < 4; i += 1) {
      const entry = entries[i];
      this.skinIndex.push(entry ? this.boneIndex[entry[0]] : 0);
      this.skinWeight.push(entry ? entry[1] / total : 0);
    }
  }

  face(a, b, c) {
    this.index.push(a, b, c);
  }

  quad(a, b, c, d) {
    this.face(a, b, c);
    this.face(a, c, d);
  }

  geometry() {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.Float32BufferAttribute(this.position, 3));
    geometry.setAttribute("skinIndex", new THREE.Uint16BufferAttribute(this.skinIndex, 4));
    geometry.setAttribute("skinWeight", new THREE.Float32BufferAttribute(this.skinWeight, 4));
    geometry.setIndex(this.index);
    geometry.computeVertexNormals();
    return geometry;
  }
}

/** Linear blend between the two bones bracketing a height, so joints bend smoothly. */
function weightsForY(chain, y) {
  if (y >= chain[0].y) return [[chain[0].bone, 1]];
  const last = chain[chain.length - 1];
  if (y <= last.y) return [[last.bone, 1]];
  for (let i = 0; i < chain.length - 1; i += 1) {
    const upper = chain[i];
    const lower = chain[i + 1];
    if (y <= upper.y && y >= lower.y) {
      const span = upper.y - lower.y || 1;
      const t = smooth(clamp((upper.y - y) / span));
      return [
        [upper.bone, 1 - t],
        [lower.bone, t],
      ];
    }
  }
  return [[last.bone, 1]];
}

function mixWeights(a, b, t) {
  const out = new Map();
  for (const [bone, w] of a) out.set(bone, (out.get(bone) || 0) + w * (1 - t));
  for (const [bone, w] of b) out.set(bone, (out.get(bone) || 0) + w * t);
  return [...out.entries()];
}

/**
 * Lofts a closed vertical tube. Rings share their wrap-around vertices, so the
 * surface is seamless and smooth-shaded with no visible ridge.
 */
function loft(builder, { x = 0, z = 0, yTop, yBottom, rings = 20, radial = 22, profile, chain, capTop = true, capBottom = true }) {
  const start = builder.count;
  for (let ring = 0; ring <= rings; ring += 1) {
    const t = ring / rings;
    const y = lerp(yTop, yBottom, t);
    const [rx, rz, dx = 0, dz = 0] = profile(t, y);
    const weights = chain(y, t);
    for (let seg = 0; seg < radial; seg += 1) {
      const a = (seg / radial) * Math.PI * 2;
      builder.vertex(x + dx + Math.cos(a) * rx, y, z + dz + Math.sin(a) * rz, weights);
    }
  }
  for (let ring = 0; ring < rings; ring += 1) {
    for (let seg = 0; seg < radial; seg += 1) {
      const next = (seg + 1) % radial;
      const a = start + ring * radial + seg;
      const b = start + ring * radial + next;
      const c = start + (ring + 1) * radial + next;
      const d = start + (ring + 1) * radial + seg;
      builder.quad(a, b, c, d);
    }
  }
  if (capTop) {
    const [rxT, rzT, dxT = 0, dzT = 0] = profile(0, yTop);
    const hub = builder.count;
    builder.vertex(x + dxT, yTop + Math.min(rxT, rzT) * 0.35, z + dzT, chain(yTop, 0));
    for (let seg = 0; seg < radial; seg += 1) {
      builder.face(hub, start + ((seg + 1) % radial), start + seg);
    }
  }
  if (capBottom) {
    const base = start + rings * radial;
    const [rxB, rzB, dxB = 0, dzB = 0] = profile(1, yBottom);
    const hub = builder.count;
    builder.vertex(x + dxB, yBottom - Math.min(rxB, rzB) * 0.35, z + dzB, chain(yBottom, 1));
    for (let seg = 0; seg < radial; seg += 1) {
      builder.face(hub, base + seg, base + ((seg + 1) % radial));
    }
  }
}

/**
 * Adds an ellipsoid mass. Used for the joints (deltoid, hip ball, knee) where a
 * plain tube-to-tube junction would leave a visible gap.
 */
function blob(builder, { cx = 0, cy, cz = 0, rx, ry, rz, weights, lat = 14, lon = 18, squash }) {
  const start = builder.count;
  for (let i = 0; i <= lat; i += 1) {
    const phi = (i / lat) * Math.PI;
    for (let j = 0; j < lon; j += 1) {
      const theta = (j / lon) * Math.PI * 2;
      let x = Math.sin(phi) * Math.cos(theta) * rx;
      let y = Math.cos(phi) * ry;
      let z = Math.sin(phi) * Math.sin(theta) * rz;
      if (squash) [x, y, z] = squash(x, y, z);
      builder.vertex(cx + x, cy + y, cz + z, weights);
    }
  }
  for (let i = 0; i < lat; i += 1) {
    for (let j = 0; j < lon; j += 1) {
      const next = (j + 1) % lon;
      const a = start + i * lon + j;
      const b = start + i * lon + next;
      const c = start + (i + 1) * lon + next;
      const d = start + (i + 1) * lon + j;
      builder.quad(a, b, c, d);
    }
  }
}

function buildBones(v) {
  const bones = {};
  const make = (name, parent, position) => {
    const bone = new THREE.Bone();
    bone.name = name;
    bone.position.set(...position);
    if (parent) parent.add(bone);
    bones[name] = bone;
    return bone;
  };

  // The skull is a rigid mass, so it leans by one amount (measured at its centre)
  // rather than shearing. Its bone shares that offset, which keeps every feature
  // attached to it sitting on the face surface.
  const skullLean = leanZ(Y.headCenter);
  const rootBone = make("AvatarRoot", null, [0, 0, 0]);
  const hips = make("Hips", rootBone, [0, Y.hips, leanZ(Y.hips)]);
  const spine = make("Spine", hips, [0, Y.spine - Y.hips, leanZ(Y.spine) - leanZ(Y.hips)]);
  const chest = make("Chest", spine, [0, Y.chest - Y.spine, leanZ(Y.chest) - leanZ(Y.spine)]);
  const neck = make("Neck", chest, [0, Y.neck - Y.chest, leanZ(Y.neck) - leanZ(Y.chest)]);
  const head = make("Head", neck, [0, Y.head - Y.neck, skullLean - leanZ(Y.neck)]);
  // Chibi features cluster low on the face, leaving the tall cranium bare.
  // The jaw pivots near the ear line so the mouth lands between nose and chin.
  make("Jaw", head, [0, Y.headCenter - Y.head - 0.315, 0.07]);
  // A headband around the widest part of the upper skull; placed at the very top
  // it sinks inside the dome and only the petal tips show.
  make("Crown", head, [0, Y.headCenter - Y.head + v.headRy * 0.62, 0]);
  // Feature depths are set so each mesh sits PROUD of the sculpted skull. The
  // body writes depth (so joints read as one solid mass), which means anything
  // tucked inside the surface is occluded and the face renders blank.
  make("LeftEye", head, [-0.275, Y.headCenter - Y.head - 0.12, v.headRz * 0.92]);
  make("RightEye", head, [0.275, Y.headCenter - Y.head - 0.12, v.headRz * 0.92]);
  make("LeftBrow", head, [-0.28, Y.headCenter - Y.head + 0.135, v.headRz * 0.95]);
  make("RightBrow", head, [0.28, Y.headCenter - Y.head + 0.135, v.headRz * 0.95]);
  make("LeftEar", head, [-v.headRx * 0.97, Y.headCenter - Y.head - 0.07, 0]);
  make("RightEar", head, [v.headRx * 0.97, Y.headCenter - Y.head - 0.07, 0]);

  for (const side of ["Left", "Right"]) {
    const sign = side === "Left" ? -1 : 1;
    const splay = (y) => armSplay(v, y);
    const shoulder = make(`${side}Shoulder`, chest, [
      sign * (v.shoulderHalf + splay(Y.shoulder)),
      Y.shoulder - Y.chest,
      leanZ(Y.shoulder) - leanZ(Y.chest),
    ]);
    const elbow = make(`${side}Elbow`, shoulder, [sign * (splay(Y.elbow) - splay(Y.shoulder)), Y.elbow - Y.shoulder, 0]);
    const wrist = make(`${side}Wrist`, elbow, [sign * (splay(Y.wrist) - splay(Y.elbow)), Y.wrist - Y.elbow, 0]);
    make(`${side}Fingers`, wrist, [0, Y.fingers - Y.wrist, 0]);
    const hip = make(`${side}Hip`, hips, [sign * v.hipsRx * 0.52, Y.hip - Y.hips, 0]);
    const knee = make(`${side}Knee`, hip, [0, Y.knee - Y.hip, 0]);
    make(`${side}Ankle`, knee, [0, Y.ankle - Y.knee, 0]);
  }
  return { bones, rootBone };
}

function buildBody(builder, v, bones) {
  const torsoChain = [
    { bone: "Head", y: Y.head },
    { bone: "Neck", y: Y.neck },
    { bone: "Chest", y: Y.chest },
    { bone: "Spine", y: Y.spine },
    { bone: "Hips", y: Y.hips },
  ];

  // Torso: neck base down to the seat, with an elliptical section that narrows
  // at the waist and widens at chest and hips.
  loft(builder, {
    yTop: Y.neck + 0.05,
    yBottom: Y.crotch - 0.02,
    rings: 38,
    radial: 34,
    capTop: false,
    capBottom: true,
    chain: (y) => weightsForY(torsoChain, y),
    profile: (t, y) => {
      const up = clamp((y - Y.crotch) / (Y.neck + 0.05 - Y.crotch));
      let rx;
      let rz;
      if (up > 0.86) {
        const k = smooth((up - 0.86) / 0.14);
        rx = lerp(v.chestRx * 0.86, v.neckR * 1.5, k);
        rz = lerp(v.chestRz * 0.9, v.neckR * 1.5, k);
      } else if (up > 0.62) {
        const k = smooth((up - 0.62) / 0.24);
        rx = lerp(v.waistRx, v.chestRx, k);
        rz = lerp(v.waistRz, v.chestRz, k);
      } else if (up > 0.34) {
        const k = smooth((up - 0.34) / 0.28);
        rx = lerp(v.hipsRx, v.waistRx, k);
        rz = lerp(v.hipsRz, v.waistRz, k);
      } else {
        const k = smooth(up / 0.34);
        rx = lerp(v.hipsRx * 0.82, v.hipsRx, k);
        rz = lerp(v.hipsRz * 0.86, v.hipsRz, k);
      }
      // A gentle forward chest and seat curve keeps the silhouette from reading
      // as a straight tube, on top of the whole-body lean.
      const dz =
        leanZ(y) +
        Math.sin(up * Math.PI) * 0.012 +
        (up > 0.68 ? v.bust * smooth((up - 0.68) / 0.2) : 0);
      return [rx, rz, 0, dz];
    },
  });

  // Shoulder girdle: bridges the torso to the deltoids. Deliberately narrower
  // than the shoulder joints so the deltoid balls round off the silhouette.
  blob(builder, {
    cy: Y.shoulderLine,
    cz: leanZ(Y.shoulderLine),
    rx: v.shoulderHalf * 0.88,
    ry: 0.24,
    rz: v.chestRz * 0.98,
    weights: [["Chest", 1]],
    lat: 20,
    lon: 28,
    squash: (x, y, z) => [x, y * (y < 0 ? 1.5 : 1), z],
  });

  // Neck: short and thick, mostly swallowed by the skull above it.
  loft(builder, {
    yTop: Y.head - 0.06,
    yBottom: Y.shoulderLine - 0.02,
    rings: 10,
    radial: 24,
    capTop: false,
    capBottom: false,
    chain: (y) => weightsForY(torsoChain, y),
    profile: (t, y) => [
      lerp(v.neckR * 0.95, v.neckR * 1.3, smooth(t)),
      lerp(v.neckR * 0.95, v.neckR * 1.36, smooth(t)),
      0,
      leanZ(y),
    ],
  });

  for (const side of ["Left", "Right"]) {
    const sign = side === "Left" ? -1 : 1;
    const armChain = [
      { bone: `${side}Shoulder`, y: Y.shoulder },
      { bone: `${side}Elbow`, y: Y.elbow },
      { bone: `${side}Wrist`, y: Y.wrist },
    ];
    // Deltoid: bridges girdle and arm, weighted mostly to the shoulder bone so
    // it follows the arm when it lifts.
    // Arms hang vertically from the already-leaned shoulder, so they share one
    // constant offset rather than shearing down their length.
    const armLean = leanZ(Y.shoulder);
    const splayShoulder = armSplay(v, Y.shoulder);
    const splayElbow = armSplay(v, Y.elbow);
    const splayWrist = armSplay(v, Y.wrist);
    // Deltoid: a ball cap on the shoulder. It, not the girdle, forms the outer
    // shoulder silhouette — a wide girdle there produces square slab shoulders.
    blob(builder, {
      cx: sign * (v.shoulderHalf + splayShoulder - 0.012),
      cy: Y.shoulder + 0.01,
      cz: armLean,
      rx: v.armR * 1.3,
      ry: v.armR * 1.5,
      rz: v.armR * 1.26,
      weights: [[`${side}Shoulder`, 0.72], ["Chest", 0.28]],
      lat: 18,
      lon: 24,
    });

    loft(builder, {
      x: sign * v.shoulderHalf,
      z: armLean,
      yTop: Y.shoulder + v.armR * 1.1,
      yBottom: Y.wrist - 0.01,
      rings: 26,
      radial: 24,
      capTop: false,
      capBottom: false,
      chain: (y, t) => {
        const base = weightsForY(armChain, y);
        if (t > 0.14) return base;
        return mixWeights(base, [["Chest", 1]], smooth(1 - t / 0.14) * 0.45);
      },
      profile: (t) => {
        const down = smooth(t);
        const r = lerp(v.armR, v.wristR, down);
        // Elbow swell and a slight inward taper toward the wrist.
        const swell = 1 + Math.exp(-(((t - 0.5) / 0.14) ** 2)) * 0.08;
        return [r * swell, r * swell, sign * ARM_SPLAY * down, 0];
      },
    });

    // Elbow mass so a bent arm keeps its volume.
    blob(builder, {
      cx: sign * (v.shoulderHalf + splayElbow),
      cy: Y.elbow,
      cz: armLean,
      rx: v.armR * 0.86,
      ry: v.armR * 0.94,
      rz: v.armR * 0.86,
      weights: [[`${side}Elbow`, 1]],
      lat: 14,
      lon: 20,
    });

    // Hand: a chunky mitt. Chibi hands are nearly as deep as they are wide, so
    // this is a rounded mass rather than the flattened paddle a realistic figure
    // would get.
    blob(builder, {
      cx: sign * (v.shoulderHalf + splayWrist),
      cy: Y.wrist - 0.08,
      cz: armLean + 0.008,
      rx: v.wristR * 1.6,
      ry: 0.15,
      rz: v.wristR * 1.05,
      weights: [[`${side}Wrist`, 1]],
      lat: 16,
      lon: 22,
    });

    const legChain = [
      { bone: `${side}Hip`, y: Y.hip },
      { bone: `${side}Knee`, y: Y.knee },
      { bone: `${side}Ankle`, y: Y.ankle },
    ];
    // Hip ball closes the seat-to-thigh junction, tucked inside the pelvis.
    blob(builder, {
      cx: sign * v.hipsRx * 0.5,
      cy: Y.hip + 0.03,
      rx: v.thighR * 1.02,
      ry: v.thighR * 1.1,
      rz: v.thighR * 0.98,
      weights: [[`${side}Hip`, 0.62], ["Hips", 0.38]],
      lat: 18,
      lon: 24,
    });

    loft(builder, {
      x: sign * v.hipsRx * 0.52,
      yTop: Y.hip + 0.02,
      yBottom: Y.ankle + 0.02,
      rings: 30,
      radial: 24,
      capTop: false,
      capBottom: false,
      chain: (y, t) => {
        const base = weightsForY(legChain, y);
        if (t > 0.1) return base;
        return mixWeights(base, [["Hips", 1]], smooth(1 - t / 0.1) * 0.4);
      },
      profile: (t) => {
        const down = smooth(t);
        const r = lerp(v.thighR, v.ankleR, down);
        const calf = 1 + Math.exp(-(((t - 0.62) / 0.12) ** 2)) * 0.16;
        return [r * calf, r * calf];
      },
    });

    // Knee.
    blob(builder, {
      cx: sign * v.hipsRx * 0.52,
      cy: Y.knee,
      rx: v.thighR * 0.64,
      ry: v.thighR * 0.7,
      rz: v.thighR * 0.64,
      weights: [[`${side}Knee`, 1]],
      lat: 14,
      lon: 20,
    });

    // Foot: a short rounded wedge pointing forward, so the stance is grounded.
    blob(builder, {
      cx: sign * v.hipsRx * 0.52,
      cy: Y.ankle - 0.045,
      cz: 0.06,
      rx: v.ankleR * 1.15,
      ry: 0.1,
      rz: v.ankleR * 1.9,
      weights: [[`${side}Ankle`, 1]],
      lat: 14,
      lon: 22,
      squash: (x, y, z) => [x, Math.max(y, -0.055), z + (y < 0 ? 0.03 : 0)],
    });
  }

  // Head: a near-sphere sculpted into a face. The chibi read comes from keeping
  // it round — only a soft jaw taper and a small chin, no long muzzle.
  const start = builder.count;
  const lat = 44;
  const lon = 52;
  const skullLean = leanZ(Y.headCenter);
  const headChain = [
    { bone: "Head", y: Y.head + 1.2 },
    { bone: "Head", y: Y.chin },
    { bone: "Neck", y: Y.chin - 0.14 },
  ];
  for (let i = 0; i <= lat; i += 1) {
    const phi = (i / lat) * Math.PI;
    for (let j = 0; j < lon; j += 1) {
      const theta = (j / lon) * Math.PI * 2;
      const sx = Math.sin(phi) * Math.cos(theta);
      const sy = Math.cos(phi);
      const sz = Math.sin(phi) * Math.sin(theta);
      let x = sx * v.headRx;
      let y = sy * v.headRy;
      let z = sz * v.headRz;
      // Taper only over the bottom third, so the cranium stays full and round.
      const down = clamp((-sy - 0.35) / 0.65);
      const taper = lerp(1, v.jawTaper, smooth(down));
      x *= taper;
      z *= taper;
      if (z < 0) z *= 0.95;
      // A small rounded chin; no brow ridge, which would harden the face.
      if (sz > 0.25 && sy < -0.3) z += 0.022 * smooth(clamp((sz - 0.25) / 0.75)) * down;
      // Full cheeks just below the eye line.
      if (sy > -0.35 && sy < 0.1) {
        const cheek = smooth(1 - Math.abs(sy + 0.12) / 0.22) * Math.abs(sx) * 0.03;
        x += Math.sign(sx) * cheek;
      }
      const worldY = Y.headCenter + y;
      builder.vertex(x, worldY, z + skullLean, weightsForY(headChain, worldY));
    }
  }
  for (let i = 0; i < lat; i += 1) {
    for (let j = 0; j < lon; j += 1) {
      const next = (j + 1) % lon;
      const a = start + i * lon + j;
      const b = start + i * lon + next;
      const c = start + (i + 1) * lon + next;
      const d = start + (i + 1) * lon + j;
      builder.quad(a, b, c, d);
    }
  }
}

function facialFeatures(scene, v, bones, mats) {
  const attach = (name, geometry, material, boneName, position = [0, 0, 0], scale = [1, 1, 1]) => {
    const value = new THREE.Mesh(geometry, material);
    value.name = name;
    value.position.set(...position);
    value.scale.set(...scale);
    bones[boneName].add(value);
    return value;
  };

  // Eyes: large, round chibi lenses with a big catchlight — the single strongest
  // cue that this is a stylised character rather than a small realistic one.
  for (const side of ["Left", "Right"]) {
    const sign = side === "Left" ? -1 : 1;
    attach(`${side}EyeMesh`, new THREE.SphereGeometry(0.125, 22, 16), mats.dark, `${side}Eye`, [0, 0, 0], [1, 1.05, 0.45]);
    attach(`${side}Catchlight`, new THREE.SphereGeometry(0.036, 12, 10), mats.light, `${side}Eye`, [sign * -0.036, 0.038, 0.032]);
  }
  // Brows sit nearly flat. A pronounced tilt either way turns the serene read
  // into a scowl (inner ends down) or worry (inner ends up).
  const brow = new THREE.CapsuleGeometry(v.browThickness * 0.5, 0.19, 5, 10);
  const leftBrow = attach("LeftBrowMesh", brow, mats.dark, "LeftBrow");
  leftBrow.rotation.z = Math.PI / 2 + 0.06;
  const rightBrow = attach("RightBrowMesh", brow, mats.dark, "RightBrow");
  rightBrow.rotation.z = Math.PI / 2 - 0.06;

  // Ears stay small; scaled up with the skull they would read as handles.
  const ear = new THREE.SphereGeometry(0.098, 14, 12);
  attach("LeftEarMesh", ear, mats.stone, "LeftEar", [0, 0, 0], [0.4, 1.1, 0.72]);
  attach("RightEarMesh", ear, mats.stone, "RightEar", [0, 0, 0], [0.4, 1.1, 0.72]);

  // A button nose — barely more than a highlight, which is what keeps the face
  // childlike instead of adult-in-miniature.
  attach(
    "Nose",
    new THREE.SphereGeometry(0.045, 16, 12),
    mats.stone,
    "Head",
    [0, Y.headCenter - Y.head - 0.285, v.headRz * 0.97],
    [0.7, 0.72, 0.9],
  );

  // Mouth with the morph targets the runtime lip-sync drives. Kept wide and
  // shallow: a rounder mouth at this scale reads as a permanent "oh".
  const mouthGeometry = new THREE.SphereGeometry(0.088, 18, 12);
  const base = mouthGeometry.attributes.position;
  // Curve the corners up in the BASE mesh, not just the smile morph, so the
  // resting face is serene rather than a flat "oh". The morphs below are derived
  // from this curved base, so lip-sync still blends from a smile.
  // The mesh is later scaled ~1.55x in x and ~0.46x in y, which shrinks the
  // apparent curve to under a third — hence the large coefficient here.
  for (let i = 0; i < base.count; i += 1) {
    base.setY(i, base.getY(i) + Math.abs(base.getX(i)) * 1.2);
  }
  base.needsUpdate = true;
  const open = new Float32Array(base.count * 3);
  const wide = new Float32Array(base.count * 3);
  const smile = new Float32Array(base.count * 3);
  for (let i = 0; i < base.count; i += 1) {
    const x = base.getX(i);
    const y = base.getY(i);
    const z = base.getZ(i);
    open[i * 3] = x * 0.78;
    open[i * 3 + 1] = y * 1.9 - 0.012;
    open[i * 3 + 2] = z;
    wide[i * 3] = x * 1.62;
    wide[i * 3 + 1] = y * 0.52;
    wide[i * 3 + 2] = z;
    smile[i * 3] = x * 1.18;
    smile[i * 3 + 1] = y * 0.8 + Math.abs(x) * 0.42;
    smile[i * 3 + 2] = z;
  }
  mouthGeometry.morphAttributes.position = [
    new THREE.Float32BufferAttribute(open, 3),
    new THREE.Float32BufferAttribute(wide, 3),
    new THREE.Float32BufferAttribute(smile, 3),
  ];
  const mouth = attach(
    "Mouth",
    mouthGeometry,
    mats.dark,
    "Jaw",
    [0, -0.105, v.headRz * 0.8],
    [1.55, 0.4 * v.lipFullness, 0.4],
  );
  mouth.morphTargetDictionary = { mouthOpen: 0, mouthWide: 1, mouthSmile: 2 };
  mouth.morphTargetInfluences = [0, 0, 0];

  // Bayon-style crown, the Salareen signature. A straight cylinder z-fights with
  // the domed hair and shows up as a jagged gold squiggle, so the band is a
  // truncated cone matching the skull radius at its own top and bottom edges,
  // sitting clear of the hair's 1.075 offset.
  const bandSy = 0.62;
  const bandHalf = 0.08;
  const skullR = (sy) => Math.sin(Math.acos(clamp(sy, -1, 1))) * v.headRx * 1.13;
  const bandTopR = skullR(bandSy + bandHalf / v.headRy);
  const bandBottomR = skullR(bandSy - bandHalf / v.headRy);
  attach("CrownBand", new THREE.CylinderGeometry(bandTopR, bandBottomR, bandHalf * 2, 24), mats.gold, "Crown");
  attach("CrownLotus", new THREE.ConeGeometry(bandTopR * 0.42, 0.34, 10), mats.gold, "Crown", [0, 0.3, -v.headRz * 0.12]);
  for (let i = 0; i < 5; i += 1) {
    const a = (i / 5) * Math.PI * 2;
    attach(
      `CrownPetal${i}`,
      new THREE.ConeGeometry(0.062, 0.19, 6),
      mats.gold,
      "Crown",
      [Math.sin(a) * bandTopR * 1.02, bandHalf + 0.05, Math.cos(a) * bandTopR * 0.78],
      [1, 1, 0.6],
    );
  }

  // Hair volume: the clearest read of the two presenters at a glance.
  // Hair follows a real hairline: high across the forehead, lower at the nape.
  // A sphere segment leaves a hard panel across the face instead.
  const hairCap = (frontDrop, backDrop) => {
    const positions = [];
    const indices = [];
    const lon = 46;
    const rows = 16;
    for (let i = 0; i <= rows; i += 1) {
      const u = i / rows;
      for (let j = 0; j < lon; j += 1) {
        const theta = (j / lon) * Math.PI * 2;
        // theta 0 points at the face (+z); 1 at the front, 0 at the back.
        const front = smooth((Math.cos(theta) + 1) / 2);
        const drop = lerp(backDrop, frontDrop, front);
        const phi = u * drop;
        // Sit clear of the scalp so the two surfaces do not z-fight into a
        // scalloped edge.
        const rx = v.headRx * 1.075;
        const ry = v.headRy * 1.075;
        const rz = v.headRz * 1.075;
        positions.push(
          Math.sin(phi) * Math.sin(theta) * rx,
          Y.headCenter - Y.head + 0.02 + Math.cos(phi) * ry,
          Math.sin(phi) * Math.cos(theta) * rz - 0.012,
        );
      }
    }
    for (let i = 0; i < rows; i += 1) {
      for (let j = 0; j < lon; j += 1) {
        const next = (j + 1) % lon;
        const a = i * lon + j;
        const b = i * lon + next;
        const c = (i + 1) * lon + next;
        const d = (i + 1) * lon + j;
        indices.push(a, b, c, a, c, d);
      }
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
    geometry.setIndex(indices);
    geometry.computeVertexNormals();
    const material = mats.hair.clone();
    material.name = "HologramHair";
    material.side = THREE.DoubleSide;
    const mesh = new THREE.Mesh(geometry, material);
    mesh.name = "HairCap";
    bones.Head.add(mesh);
    return mesh;
  };

  if (v.hair === "long") {
    hairCap(Math.PI * 0.38, Math.PI * 0.86);
    attach("HairBack", new THREE.CapsuleGeometry(v.headRx * 0.46, 0.42, 8, 18), mats.hair, "Head", [0, Y.headCenter - Y.head - 0.42, -v.headRz * 0.5], [1.35, 1, 0.55]);
  } else {
    hairCap(Math.PI * 0.3, Math.PI * 0.68);
  }

  // Fingers ride the Fingers bone so the count / point gestures still read.
  // Short and thick to match the mitt: slender fingers on a chibi hand look like
  // twigs and disappear at stage distance.
  for (const side of ["Left", "Right"]) {
    for (let i = 0; i < 4; i += 1) {
      const finger = new THREE.Mesh(new THREE.CapsuleGeometry(0.031, 0.062, 4, 8), mats.stone);
      finger.name = `${side}Finger${i}`;
      finger.position.set((i - 1.5) * 0.052, -0.082, 0.01);
      finger.rotation.x = 0.06 * i;
      bones[`${side}Fingers`].add(finger);
    }
    const thumb = new THREE.Mesh(new THREE.CapsuleGeometry(0.035, 0.055, 4, 8), mats.stone);
    thumb.name = `${side}Thumb`;
    thumb.position.set((side === "Left" ? 1 : -1) * 0.09, -0.024, 0.036);
    thumb.rotation.z = (side === "Left" ? -1 : 1) * 0.7;
    bones[`${side}Fingers`].add(thumb);
  }

  // Salareen chest medallion: a gold ring holding an "S" and a leaf, echoing the
  // Serenity concept art. Geometry, not a flat texture, so it catches the rim.
  const medallion = new THREE.Group();
  medallion.name = "SalareenMark";
  // Measured off the WIDEST torso radius: the belly is wider than the chest in
  // this canon, so keying the medallion to chestRz sinks it into the body and it
  // renders as a broken arc.
  medallion.position.set(0, 0.02, Math.max(v.chestRz, v.waistRz) + 0.06);
  const ring = new THREE.Mesh(new THREE.TorusGeometry(0.15, 0.018, 10, 40), mats.gold);
  medallion.add(ring);
  const disc = new THREE.Mesh(new THREE.CircleGeometry(0.108, 32), mats.light);
  disc.position.z = -0.006;
  medallion.add(disc);
  // "S": two stacked half-arcs, the classic serpentine, swept into a tube.
  const sPoints = [];
  for (let i = 0; i <= 20; i += 1) {
    const a = Math.PI * (0.5 + (i / 20) * 1.0); // top bowl, opening right
    sPoints.push(new THREE.Vector3(Math.cos(a) * 0.042, 0.032 + Math.sin(a) * 0.032, 0.012));
  }
  for (let i = 1; i <= 20; i += 1) {
    const a = Math.PI * (1.5 + (i / 20) * 1.0); // bottom bowl, opening left
    sPoints.push(new THREE.Vector3(Math.cos(a) * 0.042, -0.032 + Math.sin(a) * 0.032, 0.012));
  }
  const sMesh = new THREE.Mesh(
    new THREE.TubeGeometry(new THREE.CatmullRomCurve3(sPoints), 40, 0.013, 6, false),
    mats.gold,
  );
  sMesh.name = "MedallionS";
  medallion.add(sMesh);
  // Leaf rising behind the S.
  const leafShape = new THREE.Shape();
  leafShape.moveTo(0, 0);
  leafShape.bezierCurveTo(0.03, 0.03, 0.03, 0.08, 0, 0.11);
  leafShape.bezierCurveTo(-0.03, 0.08, -0.03, 0.03, 0, 0);
  const leaf = new THREE.Mesh(
    new THREE.ExtrudeGeometry(leafShape, { depth: 0.006, bevelEnabled: false }),
    mats.hair,
  );
  leaf.name = "MedallionLeaf";
  leaf.position.set(0, 0.03, 0.008);
  medallion.add(leaf);
  bones.Chest.add(medallion);
}

function buildPresenter(variantName) {
  const v = VARIANTS[variantName];
  const mats = materials();
  const scene = new THREE.Scene();
  scene.name = `Presenter_${v.label}`;
  const rig = new THREE.Group();
  rig.name = "PresenterRig";
  scene.add(rig);

  const { bones, rootBone } = buildBones(v);
  rig.add(rootBone);

  const order = [
    "AvatarRoot", "Hips", "Spine", "Chest", "Neck", "Head", "Jaw", "Crown",
    "LeftEye", "RightEye", "LeftBrow", "RightBrow", "LeftEar", "RightEar",
    "LeftShoulder", "LeftElbow", "LeftWrist", "LeftFingers",
    "RightShoulder", "RightElbow", "RightWrist", "RightFingers",
    "LeftHip", "LeftKnee", "LeftAnkle", "RightHip", "RightKnee", "RightAnkle",
  ];
  const boneList = order.map((name) => bones[name]);
  const boneIndex = Object.fromEntries(order.map((name, i) => [name, i]));

  const builder = new SkinBuilder(boneIndex);
  buildBody(builder, v, bones);

  scene.updateMatrixWorld(true);
  const skeleton = new THREE.Skeleton(boneList);
  const body = new THREE.SkinnedMesh(builder.geometry(), mats.stone);
  body.name = "PresenterBody";
  body.frustumCulled = false;
  rig.add(body);
  body.bind(skeleton);

  facialFeatures(scene, v, bones, mats);

  scene.traverse((value) => {
    if (value.isMesh) value.userData.avatarPart = true;
  });
  scene.userData.presenter = {
    variant: variantName,
    label: v.label,
    height: H,
    headUnit: HEAD,
    heads: HEADS,
    chinY: Y.chin,
    lean: LEAN,
  };
  return scene;
}

async function exportScene(scene, filename) {
  const exporter = new GLTFExporter();
  const binary = await new Promise((resolve, reject) => {
    exporter.parse(scene, resolve, reject, { binary: true, onlyVisible: true });
  });
  const target = path.join(dist, filename);
  fs.writeFileSync(target, Buffer.from(binary));
  return target;
}

const female = await exportScene(buildPresenter("female"), "presenter_female.glb");
const male = await exportScene(buildPresenter("male"), "presenter_male.glb");
// Back-compat: existing callers still request theodore.glb.
fs.copyFileSync(male, path.join(dist, "theodore.glb"));

for (const [source, target] of [
  ["node_modules/three/build/three.module.js", "three.module.js"],
  ["node_modules/three/examples/jsm/loaders/GLTFLoader.js", "loaders/GLTFLoader.js"],
  ["node_modules/three/examples/jsm/utils/BufferGeometryUtils.js", "utils/BufferGeometryUtils.js"],
]) {
  fs.copyFileSync(path.join(root, source), path.join(dist, target));
}
fs.copyFileSync(path.join(root, "avatar_runtime.js"), path.join(dist, "avatar_runtime.js"));
fs.copyFileSync(path.join(root, "avatar_rig.js"), path.join(dist, "avatar_rig.js"));
fs.copyFileSync(path.join(root, "avatar_rig_config_v2.json"), path.join(dist, "avatar_rig_config_v2.json"));
console.log(`Wrote presenter avatars (female + male) to ${dist}`);
console.log(`  ${path.basename(female)} / ${path.basename(male)} / theodore.glb`);

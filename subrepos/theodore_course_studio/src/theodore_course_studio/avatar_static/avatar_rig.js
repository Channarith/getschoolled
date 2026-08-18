import * as THREE from "three";

/**
 * Rig adapter for the Course Studio presenter.
 *
 * The runtime speaks a single set of "logical" joint and face-channel names
 * (Head, LeftElbow, mouthOpen, viseme_aa, ...). Real GLBs use different naming
 * conventions: our own procedural export uses the logical names verbatim, while
 * an artist- or Meshy-generated model built to `avatar_rig_config_v2.json` uses
 * the Serenity V2 rig (UpperArm_L, Hand_R, Eye_L, viseme_*, eyeBlink_L, ...).
 *
 * This module resolves either convention into the logical space so the teach
 * cues drive whatever GLB is loaded. Drop in a V2 GLB and it just works; keep
 * the procedural GLB and nothing changes.
 */

// Logical joint -> ordered candidate node names (first match wins). Matching is
// case-insensitive. The first candidate is always our procedural name; the rest
// cover the V2 rig plus common Mixamo/UE conventions so third-party rigs slot in.
export const BONE_ALIASES = {
  AvatarRoot: ["AvatarRoot", "Root", "Armature", "Skeleton"],
  Hips: ["Hips", "Pelvis", "mixamorigHips"],
  Spine: ["Spine", "Spine1", "spine_01", "mixamorigSpine"],
  Chest: ["Chest", "UpperChest", "Spine2", "spine_02", "spine_03", "mixamorigSpine2"],
  Neck: ["Neck", "neck_01", "mixamorigNeck"],
  Head: ["Head", "head", "mixamorigHead"],
  Jaw: ["Jaw", "jaw"],
  LeftShoulder: ["LeftShoulder", "UpperArm_L", "upperarm_l", "LeftArm", "mixamorigLeftArm"],
  RightShoulder: ["RightShoulder", "UpperArm_R", "upperarm_r", "RightArm", "mixamorigRightArm"],
  LeftElbow: ["LeftElbow", "LowerArm_L", "lowerarm_l", "Forearm_L", "LeftForeArm", "mixamorigLeftForeArm"],
  RightElbow: ["RightElbow", "LowerArm_R", "lowerarm_r", "Forearm_R", "RightForeArm", "mixamorigRightForeArm"],
  LeftWrist: ["LeftWrist", "Hand_L", "hand_l", "LeftHand", "mixamorigLeftHand"],
  RightWrist: ["RightWrist", "Hand_R", "hand_r", "RightHand", "mixamorigRightHand"],
  LeftFingers: ["LeftFingers", "Index_Proximal_L", "Middle_Proximal_L", "index_01_l", "LeftHandIndex1"],
  RightFingers: ["RightFingers", "Index_Proximal_R", "Middle_Proximal_R", "index_01_r", "RightHandIndex1"],
  LeftHip: ["LeftHip", "UpperLeg_L", "thigh_l", "LeftUpLeg", "mixamorigLeftUpLeg"],
  RightHip: ["RightHip", "UpperLeg_R", "thigh_r", "RightUpLeg", "mixamorigRightUpLeg"],
  LeftKnee: ["LeftKnee", "LowerLeg_L", "calf_l", "LeftLeg", "mixamorigLeftLeg"],
  RightKnee: ["RightKnee", "LowerLeg_R", "calf_r", "RightLeg", "mixamorigRightLeg"],
  LeftAnkle: ["LeftAnkle", "Foot_L", "foot_l", "LeftFoot", "mixamorigLeftFoot"],
  RightAnkle: ["RightAnkle", "Foot_R", "foot_r", "RightFoot", "mixamorigRightFoot"],
  LeftEye: ["LeftEye", "Eye_L", "eye_l"],
  RightEye: ["RightEye", "Eye_R", "eye_r"],
  LeftBrow: ["LeftBrow"],
  RightBrow: ["RightBrow"],
  LeftEar: ["LeftEar"],
  RightEar: ["RightEar"],
  Crown: ["Crown"],
};

// Node names that only exist on the V2 rig; used to label which convention a
// loaded GLB follows (purely informational / for the manifest + validator).
const V2_MARKERS = ["upperarm_l", "hand_r", "eye_l", "lowerleg_r"];

// Our text-derived viseme shapes -> the V2 ARKit-style viseme morph. When a GLB
// exposes these blendshapes we drive them directly for accurate lip-sync.
export const VISEME_TO_V2 = {
  rest: "viseme_sil",
  mbp: "viseme_PP",
  fv: "viseme_FF",
  aa: "viseme_aa",
  ee: "viseme_E",
  oh: "viseme_O",
  wq: "viseme_U",
  l: "viseme_nn",
};

// Canonical face channel -> candidate blendshape (morph target) names.
export const FACE_ALIASES = {
  // Procedural mesh exposes mouthOpen/mouthWide/mouthSmile; V2 uses jawOpen/smile.
  mouthOpen: ["mouthOpen", "jawOpen", "viseme_aa", "MouthOpen"],
  mouthWide: ["mouthWide", "viseme_I", "viseme_E", "mouthStretch_L"],
  smile: ["mouthSmile", "smile", "mouthSmile_L", "Smile"],
  browRaise: ["browRaise", "eyebrow_raise", "browInnerUp", "browOuterUp_L"],
  browFurrow: ["browFurrow", "eyebrow_furrow", "browDown_L"],
  blinkL: ["eyeBlink_L", "eyeBlinkLeft", "blink_l"],
  blinkR: ["eyeBlink_R", "eyeBlinkRight", "blink_r"],
};

const lc = (s) => String(s || "").toLowerCase();

/**
 * Resolve a loaded GLB scene into logical joints. Returns:
 *   { nodes, rig, matched, missing }
 * `nodes` maps every logical joint name we could locate to its Object3D, so the
 * runtime can keep addressing joints by logical name regardless of the source.
 */
export function resolveSkeleton(root) {
  const byLower = new Map();
  const present = new Set();
  root.traverse((node) => {
    if (!node.name) return;
    const key = lc(node.name);
    if (!byLower.has(key)) byLower.set(key, node);
    present.add(key);
  });

  const nodes = {};
  const matched = {};
  const missing = [];
  for (const [logical, candidates] of Object.entries(BONE_ALIASES)) {
    let hit = null;
    for (const cand of candidates) {
      const node = byLower.get(lc(cand));
      if (node) {
        hit = node;
        matched[logical] = cand;
        break;
      }
    }
    if (hit) nodes[logical] = hit;
    else missing.push(logical);
  }

  const rig = V2_MARKERS.some((m) => present.has(m)) ? "v2" : "procedural";
  return { nodes, rig, matched, missing };
}

/**
 * Face driver: abstracts mouth/expression/blink over either a procedural mesh
 * (3 morphs + skeletal blink) or a V2 rig (viseme + ARKit blendshapes). It owns
 * only the morph-target channels; skeletal joints stay with the runtime.
 */
export function createFaceDriver(root) {
  const meshes = [];
  root.traverse((n) => {
    if ((n.isMesh || n.isSkinnedMesh) && n.morphTargetDictionary && n.morphTargetInfluences) {
      const lower = {};
      for (const [name, idx] of Object.entries(n.morphTargetDictionary)) lower[lc(name)] = idx;
      meshes.push({ mesh: n, lower });
    }
  });

  const locate = (candidates) => {
    for (const { mesh, lower } of meshes) {
      for (const cand of candidates) {
        const idx = lower[lc(cand)];
        if (idx !== undefined) return { mesh, index: idx };
      }
    }
    return null;
  };

  // Canonical channels we may drive.
  const channels = {};
  for (const [name, cands] of Object.entries(FACE_ALIASES)) {
    const found = locate(cands);
    if (found) channels[name] = found;
  }
  // V2 viseme channels.
  const visemes = {};
  for (const [shape, morph] of Object.entries(VISEME_TO_V2)) {
    const found = locate([morph]);
    if (found) visemes[shape] = found;
  }

  const hasVisemes = Object.keys(visemes).length > 0;
  const hasMouth = !!(channels.mouthOpen || hasVisemes);
  const hasBlink = !!(channels.blinkL || channels.blinkR);
  const mode = hasVisemes ? "v2" : (channels.mouthOpen ? "procedural" : "none");

  // Target + current value per (mesh,index), keyed so multiple channels sharing
  // an index (e.g. viseme_aa doubling as mouthOpen) don't fight.
  const state = new Map();
  const chanKey = (c) => `${c.mesh.uuid}:${c.index}`;
  const setChan = (c, value, rate, transient) => {
    if (!c) return;
    const key = chanKey(c);
    const prev = state.get(key) || { mesh: c.mesh, index: c.index, value: c.mesh.morphTargetInfluences[c.index] || 0, target: 0, rate: 20, transient: true };
    prev.target = value;
    prev.rate = rate;
    prev.transient = transient;
    state.set(key, prev);
    if (transient) frameTargets.add(key);
  };
  // Transient channels (mouth/viseme/blink) relax to 0 when a frame skips them;
  // expression channels (smile/brow) hold their last value.
  const frameTargets = new Set();

  const driver = {
    mode,
    hasMouth,
    hasBlink,
    hasVisemes,
    channels,
    visemes,

    beginFrame() {
      frameTargets.clear();
    },

    // Procedural / generic mouth: open+wide in [0,1].
    setMouth(open, wide) {
      setChan(channels.mouthOpen, open, 22, true);
      setChan(channels.mouthWide, wide, 22, true);
    },

    // V2 viseme: drive the matching viseme morph, relax the others.
    setViseme(shape, weight) {
      if (!hasVisemes) { this.setMouth(shape === "rest" || shape === "mbp" ? 0.04 : 0.6 * weight, shape === "ee" || shape === "fv" ? 0.8 * weight : 0.16); return; }
      for (const [sh, chan] of Object.entries(visemes)) {
        setChan(chan, sh === shape ? weight : 0, 24, true);
      }
    },

    setExpression(brow, smile) {
      setChan(channels.smile, smile, 6, false);
      if (brow >= 0) {
        setChan(channels.browRaise, brow, 12, false);
        setChan(channels.browFurrow, 0, 12, false);
      } else {
        setChan(channels.browFurrow, -brow, 12, false);
        setChan(channels.browRaise, 0, 12, false);
      }
    },

    // amount: 0 open .. 1 fully closed. Only used when hasBlink.
    setBlink(amount) {
      setChan(channels.blinkL, amount, 40, true);
      setChan(channels.blinkR, amount, 40, true);
    },

    // Relax any transient channel not refreshed this frame, then ease all.
    update(dt) {
      for (const [key, ch] of state) {
        if (ch.transient && !frameTargets.has(key)) ch.target = 0;
      }
      for (const ch of state.values()) {
        const rate = 1 - Math.exp(-dt * ch.rate);
        ch.value += (ch.target - ch.value) * rate;
        if (ch.mesh.morphTargetInfluences) ch.mesh.morphTargetInfluences[ch.index] = ch.value;
      }
    },
  };
  return driver;
}

/**
 * Apply the holographic translucent look to an imported material. Unlike the
 * kit's from-scratch ShaderMaterial (which drops skinning/morph support), this
 * injects into a standard material via onBeforeCompile, so a skinned + morphed
 * artist GLB still deforms and lip-syncs while reading as a Salareen hologram.
 */
export function applyHologram(material, opts = {}) {
  const rim = opts.rimStrength ?? 0.9;
  const scan = opts.scanStrength ?? 0.35;
  const tint = opts.tint ?? [0.16, 0.82, 1.0];
  const tintMix = opts.tintMix ?? 0.22;
  material.transparent = true;
  material.opacity = opts.opacity ?? 0.92;
  material.depthWrite = opts.depthWrite ?? true;
  material.onBeforeCompile = (shader) => {
    shader.uniforms.holoRim = { value: rim };
    shader.uniforms.holoScan = { value: scan };
    shader.uniforms.holoTint = { value: new THREE.Vector3(tint[0], tint[1], tint[2]) };
    shader.uniforms.holoTintMix = { value: tintMix };
    shader.vertexShader = shader.vertexShader
      .replace("#include <common>", "#include <common>\nvarying vec3 vHoloN;\nvarying vec3 vHoloV;\nvarying vec3 vHoloL;")
      .replace(
        "#include <fog_vertex>",
        `#include <fog_vertex>
        vHoloN = normalize(mat3(modelMatrix) * objectNormal);
        vHoloV = normalize(cameraPosition - (modelMatrix * vec4(transformed, 1.0)).xyz);
        vHoloL = transformed;`,
      );
    shader.fragmentShader = shader.fragmentShader
      .replace(
        "#include <common>",
        `#include <common>
        uniform float holoRim; uniform float holoScan; uniform vec3 holoTint; uniform float holoTintMix;
        varying vec3 vHoloN; varying vec3 vHoloV; varying vec3 vHoloL;
        float holoLine(float v){ float f = abs(fract(v) - 0.5); return smoothstep(0.46, 0.5, 1.0 - f); }`,
      )
      .replace(
        "#include <dithering_fragment>",
        `#include <dithering_fragment>
        gl_FragColor.rgb = mix(gl_FragColor.rgb, holoTint, holoTintMix);
        float rimT = pow(1.0 - clamp(dot(normalize(vHoloN), normalize(vHoloV)), 0.0, 1.0), 2.2);
        gl_FragColor.rgb += holoTint * rimT * holoRim;
        float scan = holoLine(vHoloL.y * 60.0);
        gl_FragColor.rgb += holoTint * scan * holoScan * 0.5;
        gl_FragColor.a = clamp(gl_FragColor.a + rimT * 0.4, 0.0, 1.0);`,
      );
  };
  material.needsUpdate = true;
  return material;
}

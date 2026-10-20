// Angkor Wat as a walk-up background landmark.
//
// The silhouette is the real plan: a moat, a stone causeway, three terraces,
// cruciform galleries, two libraries, and the quincunx of lotus-bud towers.
// Surfaces use tiled canvas textures (sandstone courses, laterite, roof tiles,
// door shadow, gold leaf) instead of a flat color.

import * as THREE from "three";

interface Bucket {
  positions: number[];
  normals: number[];
  uvs: number[];
}

function bucket(): Bucket {
  return { positions: [], normals: [], uvs: [] };
}

function addTri(
  b: Bucket,
  ax: number, ay: number, az: number,
  bx: number, by: number, bz: number,
  cx: number, cy: number, cz: number,
  nx: number, ny: number, nz: number,
  au: number, av: number,
  bu: number, bv: number,
  cu: number, cv: number,
) {
  b.positions.push(ax, ay, az, bx, by, bz, cx, cy, cz);
  b.normals.push(nx, ny, nz, nx, ny, nz, nx, ny, nz);
  b.uvs.push(au, av, bu, bv, cu, cv);
}

/** Quad a-b-c-d, CCW when looking along the normal. UVs tile in world units. */
function addFace(
  b: Bucket,
  ax: number, ay: number, az: number,
  bx: number, by: number, bz: number,
  cx: number, cy: number, cz: number,
  dx: number, dy: number, dz: number,
  nx: number, ny: number, nz: number,
) {
  const tile = 0.72;
  const u = Math.hypot(bx - ax, by - ay, bz - az) * tile;
  const v = Math.hypot(dx - ax, dy - ay, dz - az) * tile;
  addTri(b, ax, ay, az, bx, by, bz, cx, cy, cz, nx, ny, nz, 0, 0, u, 0, u, v);
  addTri(b, ax, ay, az, cx, cy, cz, dx, dy, dz, nx, ny, nz, 0, 0, u, v, 0, v);
}

function addBox(
  b: Bucket,
  cx: number, cy: number, cz: number,
  sx: number, sy: number, sz: number,
) {
  const hx = sx / 2;
  const hy = sy / 2;
  const hz = sz / 2;
  const x0 = cx - hx;
  const x1 = cx + hx;
  const y0 = cy - hy;
  const y1 = cy + hy;
  const z0 = cz - hz;
  const z1 = cz + hz;
  addFace(b, x0, y1, z1, x1, y1, z1, x1, y1, z0, x0, y1, z0, 0, 1, 0);
  addFace(b, x0, y0, z0, x1, y0, z0, x1, y0, z1, x0, y0, z1, 0, -1, 0);
  addFace(b, x0, y0, z1, x1, y0, z1, x1, y1, z1, x0, y1, z1, 0, 0, 1);
  addFace(b, x1, y0, z0, x0, y0, z0, x0, y1, z0, x1, y1, z0, 0, 0, -1);
  addFace(b, x1, y0, z1, x1, y0, z0, x1, y1, z0, x1, y1, z1, 1, 0, 0);
  addFace(b, x0, y0, z0, x0, y0, z1, x0, y1, z1, x0, y1, z0, -1, 0, 0);
}

function addPrism(
  b: Bucket,
  cx: number, cy: number, cz: number,
  radius: number, height: number, sides = 8,
) {
  const hy = height / 2;
  const top: number[][] = [];
  const bot: number[][] = [];
  for (let i = 0; i < sides; i++) {
    const a = (i / sides) * Math.PI * 2;
    top.push([cx + Math.cos(a) * radius, cy + hy, cz + Math.sin(a) * radius]);
    bot.push([cx + Math.cos(a) * radius, cy - hy, cz + Math.sin(a) * radius]);
  }
  for (let i = 0; i < sides; i++) {
    const j = (i + 1) % sides;
    const mx = (top[i][0] + top[j][0]) / 2 - cx;
    const mz = (top[i][2] + top[j][2]) / 2 - cz;
    const len = Math.hypot(mx, mz) || 1;
    addFace(
      b,
      bot[i][0], bot[i][1], bot[i][2],
      bot[j][0], bot[j][1], bot[j][2],
      top[j][0], top[j][1], top[j][2],
      top[i][0], top[i][1], top[i][2],
      mx / len, 0, mz / len,
    );
  }
  for (let i = 1; i < sides - 1; i++) {
    addTri(
      b,
      top[0][0], top[0][1], top[0][2],
      top[i][0], top[i][1], top[i][2],
      top[i + 1][0], top[i + 1][1], top[i + 1][2],
      0, 1, 0,
      0, 0, 0.4, 0, 0.4, 0.4,
    );
    addTri(
      b,
      bot[0][0], bot[0][1], bot[0][2],
      bot[i + 1][0], bot[i + 1][1], bot[i + 1][2],
      bot[i][0], bot[i][1], bot[i][2],
      0, -1, 0,
      0, 0, 0.4, 0, 0.4, 0.4,
    );
  }
}

function paint(
  draw: (ctx: CanvasRenderingContext2D, size: number) => void,
  colorSpace: boolean,
): THREE.CanvasTexture {
  const size = 256;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("2d canvas unavailable");
  draw(ctx, size);
  const tex = new THREE.CanvasTexture(canvas);
  tex.wrapS = THREE.RepeatWrapping;
  tex.wrapT = THREE.RepeatWrapping;
  tex.anisotropy = 8;
  if (colorSpace) tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}

function noise(ctx: CanvasRenderingContext2D, size: number, alpha: number) {
  const img = ctx.getImageData(0, 0, size, size);
  const data = img.data;
  for (let i = 0; i < data.length; i += 4) {
    const n = (Math.random() - 0.5) * alpha;
    data[i] = Math.max(0, Math.min(255, data[i] + n));
    data[i + 1] = Math.max(0, Math.min(255, data[i + 1] + n));
    data[i + 2] = Math.max(0, Math.min(255, data[i + 2] + n));
  }
  ctx.putImageData(img, 0, 0);
}

function sandstoneMap(): THREE.CanvasTexture {
  return paint((ctx, size) => {
    ctx.fillStyle = "#c4a06a";
    ctx.fillRect(0, 0, size, size);
    const course = 32;
    const block = 48;
    ctx.strokeStyle = "rgba(90, 58, 28, 0.55)";
    ctx.lineWidth = 2;
    for (let y = 0; y < size; y += course) {
      ctx.beginPath();
      ctx.moveTo(0, y + 0.5);
      ctx.lineTo(size, y + 0.5);
      ctx.stroke();
      const shift = (y / course) % 2 === 0 ? 0 : block / 2;
      for (let x = -block; x < size + block; x += block) {
        ctx.beginPath();
        ctx.moveTo(x + shift, y);
        ctx.lineTo(x + shift, y + course);
        ctx.stroke();
      }
    }
    ctx.fillStyle = "rgba(70, 48, 24, 0.18)";
    for (let i = 0; i < 40; i++) {
      ctx.fillRect(Math.random() * size, Math.random() * size, 6 + Math.random() * 14, 2);
    }
    noise(ctx, size, 28);
  }, true);
}

function lateriteMap(): THREE.CanvasTexture {
  return paint((ctx, size) => {
    ctx.fillStyle = "#8d4b32";
    ctx.fillRect(0, 0, size, size);
    ctx.strokeStyle = "rgba(48, 18, 10, 0.6)";
    ctx.lineWidth = 3;
    const course = 40;
    for (let y = 0; y < size; y += course) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(size, y);
      ctx.stroke();
      const shift = (y / course) % 2 === 0 ? 0 : 36;
      for (let x = -72; x < size; x += 72) {
        ctx.beginPath();
        ctx.moveTo(x + shift, y);
        ctx.lineTo(x + shift, y + course);
        ctx.stroke();
      }
    }
    noise(ctx, size, 36);
  }, true);
}

function roofMap(): THREE.CanvasTexture {
  return paint((ctx, size) => {
    ctx.fillStyle = "#6b5344";
    ctx.fillRect(0, 0, size, size);
    for (let y = 0; y < size; y += 10) {
      ctx.fillStyle = y % 20 === 0 ? "#4e3b30" : "#7d6250";
      ctx.fillRect(0, y, size, 8);
      ctx.fillStyle = "rgba(30, 18, 10, 0.35)";
      for (let x = (y / 10) % 2 === 0 ? 0 : 14; x < size; x += 28) {
        ctx.fillRect(x, y, 2, 8);
      }
    }
    noise(ctx, size, 18);
  }, true);
}

function roughnessMap(): THREE.CanvasTexture {
  return paint((ctx, size) => {
    ctx.fillStyle = "#c8c8c8";
    ctx.fillRect(0, 0, size, size);
    ctx.strokeStyle = "#f2f2f2";
    ctx.lineWidth = 3;
    for (let y = 0; y < size; y += 32) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(size, y);
      ctx.stroke();
    }
    noise(ctx, size, 20);
  }, false);
}

function toGeometry(b: Bucket): THREE.BufferGeometry {
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.Float32BufferAttribute(b.positions, 3));
  geo.setAttribute("normal", new THREE.Float32BufferAttribute(b.normals, 3));
  geo.setAttribute("uv", new THREE.Float32BufferAttribute(b.uvs, 2));
  return geo;
}

function material(
  map: THREE.CanvasTexture,
  rough: THREE.CanvasTexture,
  color: number,
): THREE.MeshStandardMaterial {
  return new THREE.MeshStandardMaterial({
    map,
    roughnessMap: rough,
    color,
    roughness: 0.92,
    metalness: 0.02,
  });
}

function addDoor(
  stone: Bucket,
  shadow: Bucket,
  x: number, y: number, z: number,
  face: "z" | "x",
  sign: number,
  w: number, h: number,
) {
  const depth = 0.18;
  if (face === "z") {
    addBox(shadow, x, y, z + sign * 0.02, w * 0.62, h * 0.72, 0.06);
    addBox(stone, x, y + h * 0.42, z + sign * depth, w, 0.16, depth);
    addBox(stone, x - w * 0.42, y, z + sign * depth, 0.16, h, depth);
    addBox(stone, x + w * 0.42, y, z + sign * depth, 0.16, h, depth);
    addBox(stone, x, y - h * 0.46, z + sign * depth, w, 0.12, depth);
  } else {
    addBox(shadow, x + sign * 0.02, y, z, 0.06, h * 0.72, w * 0.62);
    addBox(stone, x + sign * depth, y + h * 0.42, z, depth, 0.16, w);
    addBox(stone, x + sign * depth, y, z - w * 0.42, depth, h, 0.16);
    addBox(stone, x + sign * depth, y, z + w * 0.42, depth, h, 0.16);
    addBox(stone, x + sign * depth, y - h * 0.46, z, depth, 0.12, w);
  }
}

function addColonnade(
  stone: Bucket,
  x0: number, z0: number, x1: number, z1: number,
  y: number, spacing: number,
) {
  const dx = x1 - x0;
  const dz = z1 - z0;
  const len = Math.hypot(dx, dz) || 1;
  const steps = Math.max(2, Math.round(len / spacing));
  for (let i = 0; i <= steps; i++) {
    const t = i / steps;
    const x = x0 + dx * t;
    const z = z0 + dz * t;
    addPrism(stone, x, y + 0.85, z, 0.11, 1.7, 8);
    addBox(stone, x, y + 1.78, z, 0.28, 0.16, 0.28);
  }
  const mx = (x0 + x1) / 2;
  const mz = (z0 + z1) / 2;
  if (Math.abs(dx) >= Math.abs(dz)) {
    addBox(stone, mx, y + 1.95, mz, len + 0.2, 0.18, 0.42);
    addBox(stone, mx, y + 2.18, mz, len + 0.35, 0.22, 0.7);
  } else {
    addBox(stone, mx, y + 1.95, mz, 0.42, 0.18, len + 0.2);
    addBox(stone, mx, y + 2.18, mz, 0.7, 0.22, len + 0.35);
  }
}

function addBalusters(stone: Bucket, x: number, y: number, z: number, alongX: boolean, span: number) {
  const count = Math.max(3, Math.round(span / 0.28));
  for (let i = 0; i < count; i++) {
    const t = (i + 0.5) / count - 0.5;
    const ox = alongX ? t * span : 0;
    const oz = alongX ? 0 : t * span;
    addBox(stone, x + ox, y, z + oz, 0.06, 0.55, 0.06);
  }
}

function addLotusTower(
  stone: Bucket,
  roof: Bucket,
  shadow: Bucket,
  gold: Bucket,
  x: number, z: number, y0: number, scale: number,
) {
  let y = y0;
  const tiers = 4;
  for (let i = 0; i < tiers; i++) {
    const w = (2.15 - i * 0.34) * scale;
    const h = (0.85 - i * 0.08) * scale;
    addBox(stone, x, y + h / 2, z, w, h, w);
    addBox(roof, x, y + h + 0.08 * scale, z, w + 0.38 * scale, 0.16 * scale, w + 0.38 * scale);
    const doorY = y + h * 0.42;
    const face = w / 2;
    addDoor(stone, shadow, x, doorY, z + face, "z", 1, w * 0.7, h * 0.85);
    addDoor(stone, shadow, x, doorY, z - face, "z", -1, w * 0.7, h * 0.85);
    addDoor(stone, shadow, x + face, doorY, z, "x", 1, w * 0.7, h * 0.85);
    addDoor(stone, shadow, x - face, doorY, z, "x", -1, w * 0.7, h * 0.85);
    y += h + 0.16 * scale;
  }
  // Lotus bud: stacked tapered octagons, then a finial.
  const budSteps = 6;
  for (let i = 0; i < budSteps; i++) {
    const r = (0.72 - i * 0.09) * scale;
    const h = 0.38 * scale;
    addPrism(stone, x, y + h / 2, z, Math.max(0.12, r), h, 8);
    y += h * 0.72;
  }
  addPrism(gold, x, y + 0.35 * scale, z, 0.06 * scale, 0.7 * scale, 6);
  addBox(gold, x, y + 0.72 * scale, z, 0.16 * scale, 0.1 * scale, 0.16 * scale);
}

function addGalleryRing(
  stone: Bucket,
  roof: Bucket,
  y: number, halfX: number, halfZ: number,
) {
  addColonnade(stone, -halfX, -halfZ, halfX, -halfZ, y, 0.85);
  addColonnade(stone, -halfX, halfZ, halfX, halfZ, y, 0.85);
  addColonnade(stone, -halfX, -halfZ, -halfX, halfZ, y, 0.85);
  addColonnade(stone, halfX, -halfZ, halfX, halfZ, y, 0.85);
  addBox(roof, 0, y + 2.42, -halfZ, halfX * 2 + 0.5, 0.16, 1.05);
  addBox(roof, 0, y + 2.42, halfZ, halfX * 2 + 0.5, 0.16, 1.05);
  addBox(roof, -halfX, y + 2.42, 0, 1.05, 0.16, halfZ * 2 + 0.5);
  addBox(roof, halfX, y + 2.42, 0, 1.05, 0.16, halfZ * 2 + 0.5);
  addBalusters(stone, 0, y + 0.7, halfZ + 0.35, true, halfX * 2);
  addBalusters(stone, 0, y + 0.7, -halfZ - 0.35, true, halfX * 2);
}

function addSteps(base: Bucket, x: number, z: number, width: number, towardZ: number, count: number) {
  for (let i = 0; i < count; i++) {
    const h = 0.14;
    addBox(
      base,
      x,
      i * h + h / 2,
      z + towardZ * (i * 0.28),
      width - i * 0.08,
      h,
      0.32,
    );
  }
}

/** Quincunx temple, causeway, and moat. The approach faces +Z (toward spawn). */
export function buildAngkorWat(): THREE.Group {
  const stone = bucket();
  const base = bucket();
  const roof = bucket();
  const shadow = bucket();
  const gold = bucket();

  // Moat rim and dark water, open on the south (+Z) for the causeway.
  addBox(base, 0, 0.12, -8.2, 26, 0.24, 1.1);
  addBox(base, -12.2, 0.12, 0.2, 1.1, 0.24, 16);
  addBox(base, 12.2, 0.12, 0.2, 1.1, 0.24, 16);
  addBox(base, -6.2, 0.08, 8.6, 10, 0.16, 1.1);
  addBox(base, 6.2, 0.08, 8.6, 10, 0.16, 1.1);
  addBox(shadow, 0, 0.2, -0.4, 22.5, 0.08, 16);

  // Causeway from the near bank up to the first gate.
  addBox(base, 0, 0.28, 6.4, 2.4, 0.28, 8.2);
  for (let i = 0; i < 9; i++) {
    const z = 2.6 + i * 0.95;
    addPrism(stone, -1.35, 0.7, z, 0.1, 0.9, 6);
    addPrism(stone, 1.35, 0.7, z, 0.1, 0.9, 6);
    addBox(stone, -1.35, 1.22, z, 0.34, 0.14, 0.22);
    addBox(stone, 1.35, 1.22, z, 0.34, 0.14, 0.22);
  }
  addSteps(base, 0, 9.8, 2.6, 1, 5);

  // Outer enclosure and south gopura.
  addBox(stone, 0, 1.15, -6.6, 18.5, 2.1, 0.55);
  addBox(stone, -9.1, 1.15, 0.4, 0.55, 2.1, 14);
  addBox(stone, 9.1, 1.15, 0.4, 0.55, 2.1, 14);
  addBox(stone, -4.6, 1.15, 7.4, 8.2, 2.1, 0.55);
  addBox(stone, 4.6, 1.15, 7.4, 8.2, 2.1, 0.55);
  addBox(roof, 0, 2.35, 7.4, 3.2, 0.7, 1.3);
  addDoor(stone, shadow, 0, 1.15, 7.7, "z", 1, 2.1, 2.3);
  addPrism(stone, 0, 3.15, 7.4, 0.55, 1.1, 8);
  addBox(gold, 0, 3.85, 7.4, 0.18, 0.22, 0.18);

  // Three terraces.
  addBox(base, 0, 0.45, 0.2, 16.2, 0.7, 12.4);
  addBox(base, 0, 1.15, 0.2, 11.4, 0.7, 8.6);
  addBox(stone, 0, 1.85, 0.2, 7.2, 0.7, 5.6);
  addSteps(base, 0, 6.5, 3.2, 1, 6);
  addSteps(base, 0, 4.6, 2.4, 1, 5);
  addSteps(stone, 0, 3.1, 1.8, 1, 4);

  // Cruciform galleries on the middle terrace.
  addGalleryRing(stone, roof, 1.5, 5.2, 3.8);
  addBox(stone, 0, 2.15, 0.2, 6.4, 0.35, 1.15);
  addBox(stone, 0, 2.15, 0.2, 1.15, 0.35, 4.8);

  // Libraries flanking the causeway, a small hall with its own porch.
  for (const sx of [-3.6, 3.6]) {
    addBox(stone, sx, 1.55, 4.6, 1.7, 1.5, 2.2);
    addBox(roof, sx, 2.45, 4.6, 2.05, 0.28, 2.55);
    addDoor(stone, shadow, sx, 1.45, 5.75, "z", 1, 1.15, 1.35);
    addPrism(stone, sx, 2.85, 4.6, 0.28, 0.7, 8);
  }

  // Corner towers and the tall central prasat.
  const deck = 2.2;
  addLotusTower(stone, roof, shadow, gold, -2.15, -1.7, deck, 0.62);
  addLotusTower(stone, roof, shadow, gold, 2.15, -1.7, deck, 0.62);
  addLotusTower(stone, roof, shadow, gold, -2.15, 1.9, deck, 0.62);
  addLotusTower(stone, roof, shadow, gold, 2.15, 1.9, deck, 0.62);
  addLotusTower(stone, roof, shadow, gold, 0, 0.15, deck, 1);

  // Sugar palms along the moat. Trunk plus a fan of fronds.
  for (const [px, pz] of [[-8.4, 6.2], [8.4, 6.2], [-10.2, -4.4], [10.2, -4.4], [-6.5, -7.2], [6.5, -7.2]] as const) {
    addPrism(base, px, 1.6, pz, 0.16, 3.2, 6);
    for (let i = 0; i < 6; i++) {
      const a = (i / 6) * Math.PI * 2;
      addBox(roof, px + Math.cos(a) * 0.7, 3.35, pz + Math.sin(a) * 0.7, 1.3, 0.06, 0.18);
    }
  }

  const rough = roughnessMap();
  const group = new THREE.Group();
  group.name = "AngkorWat";
  const parts: [Bucket, THREE.CanvasTexture, number][] = [
    [stone, sandstoneMap(), 0xffffff],
    [base, lateriteMap(), 0xffffff],
    [roof, roofMap(), 0xffffff],
    [shadow, sandstoneMap(), 0x2a2118],
    [gold, sandstoneMap(), 0xe6c35c],
  ];
  for (const [part, map, color] of parts) {
    if (part.positions.length === 0) continue;
    const mesh = new THREE.Mesh(toGeometry(part), material(map, rough, color));
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    group.add(mesh);
  }
  return group;
}

export function disposeAngkorWat(group: THREE.Object3D) {
  const textures = new Set<THREE.Texture>();
  group.traverse(obj => {
    if (!(obj instanceof THREE.Mesh)) return;
    obj.geometry.dispose();
    const mats = Array.isArray(obj.material) ? obj.material : [obj.material];
    for (const mat of mats) {
      if (mat instanceof THREE.MeshStandardMaterial) {
        if (mat.map) textures.add(mat.map);
        if (mat.roughnessMap) textures.add(mat.roughnessMap);
      }
      mat.dispose();
    }
  });
  textures.forEach(tex => tex.dispose());
}

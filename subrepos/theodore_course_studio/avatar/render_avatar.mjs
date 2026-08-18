/**
 * Offline render check for the presenter GLBs: a small software rasteriser that
 * mirrors avatar_runtime.js framing and lighting, so a proportion change can be
 * eyeballed without a browser or a GPU. Writes PNGs next to this script.
 *
 * Usage: node render_avatar.mjs [outDir]
 */
import fs from "node:fs";
import path from "node:path";
import zlib from "node:zlib";
import { fileURLToPath } from "node:url";

const root = path.dirname(fileURLToPath(import.meta.url));
const dist = path.join(root, "..", "src", "theodore_course_studio", "avatar_static");
const outDir = process.argv[2] ? path.resolve(process.argv[2]) : path.join(root, "preview");
fs.mkdirSync(outDir, { recursive: true });

// ---------- GLB parsing ----------

function readGlb(file) {
  const buf = fs.readFileSync(file);
  const jsonLength = buf.readUInt32LE(12);
  const json = JSON.parse(buf.slice(20, 20 + jsonLength).toString("utf8"));
  return { json, bin: buf.slice(20 + jsonLength + 8) };
}

const IDENTITY = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1];

function multiply(a, b) {
  const out = new Array(16).fill(0);
  for (let col = 0; col < 4; col += 1) {
    for (let row = 0; row < 4; row += 1) {
      let sum = 0;
      for (let k = 0; k < 4; k += 1) sum += a[k * 4 + row] * b[col * 4 + k];
      out[col * 4 + row] = sum;
    }
  }
  return out;
}

function localMatrix(node) {
  if (node.matrix) return node.matrix;
  const m = IDENTITY.slice();
  const t = node.translation || [0, 0, 0];
  const s = node.scale || [1, 1, 1];
  m[0] = s[0];
  m[5] = s[1];
  m[10] = s[2];
  m[12] = t[0];
  m[13] = t[1];
  m[14] = t[2];
  return m;
}

function apply(m, x, y, z) {
  return [
    m[0] * x + m[4] * y + m[8] * z + m[12],
    m[1] * x + m[5] * y + m[9] * z + m[13],
    m[2] * x + m[6] * y + m[10] * z + m[14],
  ];
}

const COMPONENT_READERS = {
  5121: (bin, at) => bin.readUInt8(at),
  5123: (bin, at) => bin.readUInt16LE(at),
  5125: (bin, at) => bin.readUInt32LE(at),
  5126: (bin, at) => bin.readFloatLE(at),
};
const COMPONENT_SIZES = { 5121: 1, 5123: 2, 5125: 4, 5126: 4 };
const TYPE_COUNTS = { SCALAR: 1, VEC2: 2, VEC3: 3, VEC4: 4 };

function readAccessor(json, bin, index) {
  const acc = json.accessors[index];
  const per = TYPE_COUNTS[acc.type];
  const size = COMPONENT_SIZES[acc.componentType];
  const read = COMPONENT_READERS[acc.componentType];
  const view = json.bufferViews[acc.bufferView];
  const base = (view.byteOffset || 0) + (acc.byteOffset || 0);
  const stride = view.byteStride || per * size;
  const out = new Float64Array(acc.count * per);
  for (let i = 0; i < acc.count; i += 1) {
    for (let c = 0; c < per; c += 1) out[i * per + c] = read(bin, base + i * stride + c * size);
  }
  return out;
}

/** Flattens the scene into world-space triangles with a colour per material. */
function collectTriangles(json, bin) {
  const tris = [];
  const walk = (index, parent) => {
    const node = json.nodes[index];
    const m = multiply(parent, localMatrix(node));
    if (node.mesh !== undefined) {
      for (const prim of json.meshes[node.mesh].primitives) {
        const pos = readAccessor(json, bin, prim.attributes.POSITION);
        const idx = prim.indices !== undefined
          ? readAccessor(json, bin, prim.indices)
          : Float64Array.from({ length: pos.length / 3 }, (_, i) => i);
        const mat = json.materials?.[prim.material] || {};
        const base = mat.pbrMetallicRoughness?.baseColorFactor || [1, 1, 1, 1];
        const emissive = mat.emissiveFactor || [0, 0, 0];
        // Skinned vertices are authored in bind space, which for this rig is the
        // rest pose, so the node transform is all that is needed.
        const world = new Float64Array(pos.length);
        for (let i = 0; i < pos.length; i += 3) {
          const [x, y, z] = apply(m, pos[i], pos[i + 1], pos[i + 2]);
          world[i] = x;
          world[i + 1] = y;
          world[i + 2] = z;
        }
        for (let i = 0; i < idx.length; i += 3) {
          tris.push({ a: idx[i] * 3, b: idx[i + 1] * 3, c: idx[i + 2] * 3, pos: world, base, emissive });
        }
      }
    }
    for (const child of node.children || []) walk(child, m);
  };
  for (const n of json.scenes?.[0]?.nodes || []) walk(n, IDENTITY);
  return tris;
}

// ---------- rasteriser ----------

const norm = (v) => {
  const l = Math.hypot(v[0], v[1], v[2]) || 1;
  return [v[0] / l, v[1] / l, v[2] / l];
};
const cross = (a, b) => [
  a[1] * b[2] - a[2] * b[1],
  a[2] * b[0] - a[0] * b[2],
  a[0] * b[1] - a[1] * b[0],
];
const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];

// avatar_runtime.js lights.
const LIGHTS = [
  { dir: norm([-3, 6, 5]), intensity: 0.62 },
  { dir: norm([3, 3, 2]), intensity: 0.4 },
  { dir: norm([-2.4, 1.4, 3.2]), intensity: 0.24 },
];
const AMBIENT = 0.34;

function render(tris, { eye, target, fov, width, height, background }) {
  const f = norm([target[0] - eye[0], target[1] - eye[1], target[2] - eye[2]]);
  const r = norm(cross(f, [0, 1, 0]));
  const u = cross(r, f);
  const tanHalf = Math.tan((fov * Math.PI) / 360);
  const aspect = width / height;

  const color = new Float64Array(width * height * 3);
  for (let i = 0; i < width * height; i += 1) {
    color[i * 3] = background[0];
    color[i * 3 + 1] = background[1];
    color[i * 3 + 2] = background[2];
  }
  const depth = new Float64Array(width * height).fill(Infinity);

  const project = (x, y, z) => {
    const d = [x - eye[0], y - eye[1], z - eye[2]];
    const vz = dot(d, f);
    if (vz <= 0.01) return null;
    const vx = dot(d, r);
    const vy = dot(d, u);
    return [
      ((vx / (vz * tanHalf * aspect)) * 0.5 + 0.5) * width,
      (1 - ((vy / (vz * tanHalf)) * 0.5 + 0.5)) * height,
      vz,
    ];
  };

  for (const tri of tris) {
    const { pos, a, b, c } = tri;
    const p0 = project(pos[a], pos[a + 1], pos[a + 2]);
    const p1 = project(pos[b], pos[b + 1], pos[b + 2]);
    const p2 = project(pos[c], pos[c + 1], pos[c + 2]);
    if (!p0 || !p1 || !p2) continue;

    const e1 = [pos[b] - pos[a], pos[b + 1] - pos[a + 1], pos[b + 2] - pos[a + 2]];
    const e2 = [pos[c] - pos[a], pos[c + 1] - pos[a + 1], pos[c + 2] - pos[a + 2]];
    let n = norm(cross(e1, e2));
    // Two-sided shading: the generated caps are not consistently wound.
    const toEye = norm([eye[0] - pos[a], eye[1] - pos[a + 1], eye[2] - pos[a + 2]]);
    if (dot(n, toEye) < 0) n = [-n[0], -n[1], -n[2]];

    let lit = AMBIENT;
    for (const light of LIGHTS) lit += light.intensity * Math.max(0, dot(n, light.dir));
    // A cheap fresnel rim, matching the runtime's hologram look.
    const rim = Math.pow(1 - Math.max(0, dot(n, toEye)), 2.2) * 0.55;

    const shade = [0, 1, 2].map((i) =>
      Math.min(1, tri.base[i] * lit + tri.emissive[i] * 0.85 + rim * [0.56, 0.9, 1][i]),
    );

    const minX = Math.max(0, Math.floor(Math.min(p0[0], p1[0], p2[0])));
    const maxX = Math.min(width - 1, Math.ceil(Math.max(p0[0], p1[0], p2[0])));
    const minY = Math.max(0, Math.floor(Math.min(p0[1], p1[1], p2[1])));
    const maxY = Math.min(height - 1, Math.ceil(Math.max(p0[1], p1[1], p2[1])));
    const area = (p1[0] - p0[0]) * (p2[1] - p0[1]) - (p2[0] - p0[0]) * (p1[1] - p0[1]);
    if (Math.abs(area) < 1e-9) continue;

    for (let py = minY; py <= maxY; py += 1) {
      for (let px = minX; px <= maxX; px += 1) {
        const sx = px + 0.5;
        const sy = py + 0.5;
        const w0 = ((p1[0] - sx) * (p2[1] - sy) - (p2[0] - sx) * (p1[1] - sy)) / area;
        const w1 = ((p2[0] - sx) * (p0[1] - sy) - (p0[0] - sx) * (p2[1] - sy)) / area;
        const w2 = 1 - w0 - w1;
        if (w0 < 0 || w1 < 0 || w2 < 0) continue;
        const z = w0 * p0[2] + w1 * p1[2] + w2 * p2[2];
        const at = py * width + px;
        if (z >= depth[at]) continue;
        depth[at] = z;
        color[at * 3] = shade[0];
        color[at * 3 + 1] = shade[1];
        color[at * 3 + 2] = shade[2];
      }
    }
  }
  return color;
}

/** Box-downsamples the supersampled buffer for cheap antialiasing. */
function downsample(color, width, height, factor) {
  const w = width / factor;
  const h = height / factor;
  const out = Buffer.alloc(w * h * 3);
  for (let y = 0; y < h; y += 1) {
    for (let x = 0; x < w; x += 1) {
      const acc = [0, 0, 0];
      for (let dy = 0; dy < factor; dy += 1) {
        for (let dx = 0; dx < factor; dx += 1) {
          const at = ((y * factor + dy) * width + x * factor + dx) * 3;
          acc[0] += color[at];
          acc[1] += color[at + 1];
          acc[2] += color[at + 2];
        }
      }
      const n = factor * factor;
      for (let i = 0; i < 3; i += 1) {
        // sRGB-ish gamma so the render reads like the browser output.
        out[(y * w + x) * 3 + i] = Math.round(Math.pow(Math.min(1, acc[i] / n), 1 / 1.6) * 255);
      }
    }
  }
  return { data: out, width: w, height: h };
}

// ---------- PNG ----------

const CRC_TABLE = (() => {
  const table = new Int32Array(256);
  for (let n = 0; n < 256; n += 1) {
    let c = n;
    for (let k = 0; k < 8; k += 1) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    table[n] = c;
  }
  return table;
})();

function crc32(buf) {
  let c = 0xffffffff;
  for (const byte of buf) c = CRC_TABLE[(c ^ byte) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}

function chunk(type, data) {
  const len = Buffer.alloc(4);
  len.writeUInt32BE(data.length);
  const body = Buffer.concat([Buffer.from(type, "ascii"), data]);
  const crc = Buffer.alloc(4);
  crc.writeUInt32BE(crc32(body));
  return Buffer.concat([len, body, crc]);
}

function writePng(file, { data, width, height }) {
  const raw = Buffer.alloc((width * 3 + 1) * height);
  for (let y = 0; y < height; y += 1) {
    raw[y * (width * 3 + 1)] = 0;
    data.copy(raw, y * (width * 3 + 1) + 1, y * width * 3, (y + 1) * width * 3);
  }
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(width, 0);
  ihdr.writeUInt32BE(height, 4);
  ihdr[8] = 8;
  ihdr[9] = 2;
  fs.writeFileSync(
    file,
    Buffer.concat([
      Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
      chunk("IHDR", ihdr),
      chunk("IDAT", zlib.deflateSync(raw, { level: 9 })),
      chunk("IEND", Buffer.alloc(0)),
    ]),
  );
}

// ---------- views ----------

const BG = [0.026, 0.075, 0.11];
const SS = 3;
const VIEWS = {
  // Matches avatar_runtime.js exactly.
  stage: { eye: [1.05, 2.45, 8.7], target: [0, 2.05, 0], fov: 30, width: 380, height: 520 },
  face: { eye: [0.35, 3.62, 2.6], target: [0, 3.5, 0], fov: 34, width: 420, height: 420 },
  side: { eye: [8.2, 2.6, 1.1], target: [0, 2.2, 0], fov: 30, width: 380, height: 520 },
};

for (const variant of ["female", "male"]) {
  const { json, bin } = readGlb(path.join(dist, `presenter_${variant}.glb`));
  const tris = collectTriangles(json, bin);
  for (const [name, view] of Object.entries(VIEWS)) {
    const width = view.width * SS;
    const height = view.height * SS;
    const color = render(tris, { ...view, width, height, background: BG });
    const image = downsample(color, width, height, SS);
    const file = path.join(outDir, `presenter_${variant}_${name}.png`);
    writePng(file, image);
    console.log(`${path.relative(process.cwd(), file)}  ${image.width}x${image.height}  (${tris.length} tris)`);
  }
}

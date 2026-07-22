/**
 * terrain.ts — Three.js voxel terrain for the educational world game.
 *
 * Exports:
 *   generateHeightMap        – noise-based height map per planet
 *   buildTerrainGeometry     – efficient face-culled BufferGeometry with vertex colors
 *   getTerrainHeight         – safe bounds-checked height lookup
 *   getBiomeAt               – biome classification by world position
 *   getBlockColor            – rich per-block color with biome awareness
 */

import * as THREE from 'three';
import type { BiomeType, Planet } from './types';

// ─────────────────────────────────────────────────────────────────────────────
// INTERNAL NOISE UTILITIES
// ─────────────────────────────────────────────────────────────────────────────

/**
 * A fast, deterministic integer hash — no external dependency needed.
 * Returns a value in [0, 1).
 */
function hash2(x: number, y: number): number {
  let h = (x * 374761393 + y * 668265263) >>> 0;
  h ^= h >>> 13;
  h = Math.imul(h, 1274126177) >>> 0;
  h ^= h >>> 16;
  return (h >>> 0) / 0xffffffff;
}

/**
 * Smoothstep interpolation for noise blending.
 */
function smoothstep(t: number): number {
  return t * t * (3 - 2 * t);
}

/**
 * Bilinearly-interpolated value noise in [0, 1].
 * `scale` controls the frequency — smaller → smoother hills.
 */
function valueNoise(wx: number, wz: number, scale: number): number {
  const fx = wx / scale;
  const fz = wz / scale;
  const ix = Math.floor(fx);
  const iz = Math.floor(fz);
  const tx = smoothstep(fx - ix);
  const tz = smoothstep(fz - iz);

  const a = hash2(ix,     iz);
  const b = hash2(ix + 1, iz);
  const c = hash2(ix,     iz + 1);
  const d = hash2(ix + 1, iz + 1);

  return a + (b - a) * tx + (c - a) * tz + (a - b - c + d) * tx * tz;
}

/**
 * Fractional Brownian Motion — layered octaves of value noise.
 * Returns a value in roughly [0, 1].
 */
function fbm(
  wx: number,
  wz: number,
  baseScale: number,
  octaves = 4,
  persistence = 0.5,
): number {
  let value = 0;
  let amplitude = 1;
  let frequency = 1;
  let maxValue = 0;
  for (let i = 0; i < octaves; i++) {
    value    += valueNoise(wx * frequency, wz * frequency, baseScale) * amplitude;
    maxValue += amplitude;
    amplitude *= persistence;
    frequency *= 2;
  }
  return value / maxValue;
}

// ─────────────────────────────────────────────────────────────────────────────
// 1. GENERATE HEIGHT MAP
// ─────────────────────────────────────────────────────────────────────────────

/** Water / void level — columns at or below this are treated as open space. */
export const WATER_LEVEL = 2;

/**
 * Generate a [worldSize × worldSize] height map for the given planet.
 *
 * Planet 'earth':
 *   – fBm-based heights mapped to 1–8
 *   – Edges fade to WATER_LEVEL to create a natural coastline effect
 *
 * Planet 'space':
 *   – Different noise pattern, heights 1–6
 *   – Islands separated by void gaps (modulo masking)
 *   – Occasional tall crystal spires
 */
export function generateHeightMap(worldSize: number, planet: Planet): number[][] {
  const half = worldSize / 2;
  const hmap: number[][] = [];

  for (let z = 0; z < worldSize; z++) {
    hmap[z] = [];
    for (let x = 0; x < worldSize; x++) {
      if (planet === 'earth') {
        // ── Earth ─────────────────────────────────────────────────────────
        const n = fbm(x, z, 12, 5, 0.55);          // primary terrain shape
        const detail = valueNoise(x, z, 4) * 0.15;  // fine rocky detail

        // Raw height in [1, 8]
        let h = Math.round(1 + (n + detail) * 7);
        h = Math.max(1, Math.min(8, h));

        // Coastal edge falloff — distance from world border (normalised 0→1)
        const edgeDist = Math.min(x, z, worldSize - 1 - x, worldSize - 1 - z);
        const edgeNorm = Math.min(1, edgeDist / (worldSize * 0.15));
        if (edgeNorm < 1) {
          // Lerp toward WATER_LEVEL near the coastline
          h = Math.round(WATER_LEVEL + (h - WATER_LEVEL) * smoothstep(edgeNorm));
          h = Math.max(1, h);
        }

        hmap[z][x] = h;
      } else {
        // ── Space / Crystal World ──────────────────────────────────────────
        // A coarser, chunkier noise with a different seed offset
        const n = fbm(x + 1000, z + 1000, 8, 4, 0.6);

        // Island gap mask — use modulo of world position to punch holes
        const islandX = Math.floor(x / (worldSize / 5));
        const islandZ = Math.floor(z / (worldSize / 5));
        const cellLocalX = x % Math.ceil(worldSize / 5);
        const cellLocalZ = z % Math.ceil(worldSize / 5);
        const cellW = Math.ceil(worldSize / 5);

        // Distance from centre of the island cell, normalised [0, 1]
        const cellCx = cellW / 2;
        const cellCz = cellW / 2;
        const distToCenter = Math.sqrt(
          ((cellLocalX - cellCx) / cellCx) ** 2 +
          ((cellLocalZ - cellCz) / cellCz) ** 2,
        );

        // Each island occupies ~70 % of its cell; the rest is void
        const islandRadius = 0.70;
        // Slight per-island variation using hash
        const islandVariance = hash2(islandX * 31, islandZ * 37) * 0.15;
        const effectiveRadius = islandRadius - islandVariance;

        if (distToCenter > effectiveRadius) {
          // Void gap between islands
          hmap[z][x] = 0;
          continue;
        }

        // Island height fade at edges
        const fadeNorm = 1 - distToCenter / effectiveRadius;
        let h = Math.round(1 + n * 5 * smoothstep(fadeNorm));
        h = Math.max(1, Math.min(6, h));

        // Crystal spires: rare tall columns on island centres
        const spireChance = hash2(x * 7 + 13, z * 11 + 17);
        if (distToCenter < 0.2 && spireChance > 0.85) {
          h = 6; // Maximum spire height
        }

        hmap[z][x] = h;
      }
    }
  }

  return hmap;
}

// ─────────────────────────────────────────────────────────────────────────────
// 2. BIOME CLASSIFICATION
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Determine the biome at a given world-space position.
 *
 * Earth biomes use distance from centre + noise for natural variation.
 * Space biomes are either 'crystal' or 'void'.
 */
export function getBiomeAt(
  x: number,
  z: number,
  worldSize: number,
  planet: Planet,
): BiomeType {
  if (planet === 'space') {
    return 'crystal';
  }

  // Normalised position [−1, 1] from world centre
  const nx = (x / worldSize) * 2 - 1;
  const nz = (z / worldSize) * 2 - 1;
  const dist = Math.sqrt(nx * nx + nz * nz); // 0 = centre, ~1.4 = corner

  // Add a biome noise layer so boundaries are organic, not geometric
  const biomeNoise = fbm(x, z, 20, 3, 0.5);

  // Polar snow cap at world edges
  if (dist > 0.75 + biomeNoise * 0.15) return 'snow';

  // Desert band around the south-east quadrant
  if (nx > 0.1 && nz > 0.1 && biomeNoise < 0.45) return 'desert';

  // Forest cluster in the north-west quadrant
  if (nx < -0.1 && nz < -0.1 && biomeNoise > 0.5) return 'forest';

  // Everything else is grassland
  return 'grassland';
}

// ─────────────────────────────────────────────────────────────────────────────
// 3. BLOCK COLOR
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Per-block RGB color [0–1, 0–1, 0–1] with biome awareness and slight random
 * variation so the terrain looks textured rather than flat.
 *
 * @param isTop  Whether this face is the topmost face of the column.
 */
export function getBlockColor(
  x: number,
  z: number,
  height: number,
  maxH: number,
  isTop: boolean,
  planet: Planet,
): [number, number, number] {
  // Tiny per-block jitter in [−0.03, +0.03] for visual noise
  const jitter = (hash2(x * 3 + 7, z * 5 + 11) - 0.5) * 0.06;

  const clamp = (v: number) => Math.max(0, Math.min(1, v));
  const j = (base: number) => clamp(base + jitter);

  if (planet === 'space') {
    // ── Crystal / Space palette ────────────────────────────────────────────
    const heightRatio = maxH > 0 ? height / maxH : 0;

    if (isTop && heightRatio >= 0.85) {
      // Crystal spire tip — bright teal-white
      return [j(0.80), j(0.95), j(0.98)];
    }
    if (isTop && heightRatio >= 0.6) {
      // Crystal mid — vivid teal
      return [j(0.10), j(0.85), j(0.88)];
    }
    if (isTop) {
      // Island surface — purple
      return [j(0.55), j(0.15), j(0.80)];
    }
    // Side / sub-surface — dark indigo
    return [j(0.18), j(0.05), j(0.35)];
  }

  // ── Earth palette — biome-aware ────────────────────────────────────────────
  // We derive biome from position but need worldSize; we approximate via
  // the height and a simple directional bias encoded in the hash.
  const heightRatio = maxH > 1 ? (height - 1) / (maxH - 1) : 0;

  // Snow by altitude
  if (height >= 7) {
    const snowBlend = (height - 6) / 2; // 0 at h=6, 1 at h=8
    const base: [number, number, number] = [
      j(0.90 + snowBlend * 0.07),
      j(0.90 + snowBlend * 0.07),
      j(0.93 + snowBlend * 0.05),
    ];
    return base;
  }

  // Stone for tall columns or side faces at depth
  if (!isTop && height > 4) {
    return [j(0.48), j(0.44), j(0.40)];
  }
  if (!isTop && height > 2) {
    return [j(0.36), j(0.28), j(0.20)]; // dirt sides
  }
  if (!isTop) {
    return [j(0.55), j(0.50), j(0.42)]; // sandy sub-surface
  }

  // Top-face biome colours
  if (height <= WATER_LEVEL + 1) {
    // Sandy beach / shoreline
    return [j(0.85), j(0.80), j(0.52)];
  }

  // Use the height ratio + some positional noise to blend biome look
  const biomeSample = hash2(Math.floor(x / 3), Math.floor(z / 3));

  if (heightRatio > 0.7) {
    // Rocky highland — grey-brown stone
    return [j(0.50), j(0.46), j(0.42)];
  }

  if (biomeSample < 0.25) {
    // Desert / savanna — warm ochre
    return [j(0.76), j(0.62), j(0.28)];
  }

  if (biomeSample > 0.75) {
    // Dense forest — dark rich green
    return [j(0.18), j(0.50), j(0.15)];
  }

  // Grassland default — bright mid-green
  return [j(0.32), j(0.65), j(0.24)];
}

// ─────────────────────────────────────────────────────────────────────────────
// 4. SAFE HEIGHT LOOKUP
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Returns the terrain height at (x, z), clamped to world bounds.
 * Out-of-bounds coordinates return 0 (void / open air).
 */
export function getTerrainHeight(
  hmap: number[][],
  x: number,
  z: number,
  worldSize: number,
): number {
  const xi = Math.floor(x);
  const zi = Math.floor(z);
  if (xi < 0 || xi >= worldSize || zi < 0 || zi >= worldSize) return 0;
  return hmap[zi]?.[xi] ?? 0;
}

// ─────────────────────────────────────────────────────────────────────────────
// 5. BUILD TERRAIN GEOMETRY (face-culled voxel mesh)
// ─────────────────────────────────────────────────────────────────────────────

/**
 * 6 faces × 2 triangles × 3 vertices = 36 index entries per voxel (worst case).
 * We pre-allocate generously and trim at the end.
 */

interface FaceDesc {
  /** Unit normal direction index: 0=+X, 1=−X, 2=+Y, 3=−Y, 4=+Z, 5=−Z */
  dir: 0 | 1 | 2 | 3 | 4 | 5;
  /** Neighbour offset to check for occlusion */
  nx: number;
  ny: number;
  nz: number;
  /** Four corner offsets [x,y,z] for the quad vertices (counter-clockwise from outside) */
  corners: [[number, number, number], [number, number, number], [number, number, number], [number, number, number]];
}

const FACES: FaceDesc[] = [
  // +Y (top)
  {
    dir: 2, nx: 0, ny: 1, nz: 0,
    corners: [[0,1,0],[1,1,0],[1,1,1],[0,1,1]],
  },
  // −Y (bottom) — rarely visible but included for completeness
  {
    dir: 3, nx: 0, ny: -1, nz: 0,
    corners: [[0,0,1],[1,0,1],[1,0,0],[0,0,0]],
  },
  // +X (east)
  {
    dir: 0, nx: 1, ny: 0, nz: 0,
    corners: [[1,0,0],[1,1,0],[1,1,1],[1,0,1]],
  },
  // −X (west)
  {
    dir: 1, nx: -1, ny: 0, nz: 0,
    corners: [[0,0,1],[0,1,1],[0,1,0],[0,0,0]],
  },
  // +Z (south)
  {
    dir: 4, nx: 0, ny: 0, nz: 1,
    corners: [[1,0,1],[1,1,1],[0,1,1],[0,0,1]],
  },
  // −Z (north)
  {
    dir: 5, nx: 0, ny: 0, nz: -1,
    corners: [[0,0,0],[0,1,0],[1,1,0],[1,0,0]],
  },
];

/**
 * Build an efficient face-culled Three.js BufferGeometry for the terrain.
 *
 * Algorithm:
 *   For each column (x, z) iterate y from 1 to height.
 *   For each voxel face, check whether the neighbouring voxel is solid.
 *   Only emit the face if it is exposed to air (or a lower-height neighbour on the
 *   horizontal faces).
 *
 * The geometry uses vertex colours (attribute "color") so no texture is needed.
 */
export function buildTerrainGeometry(
  hmap: number[][],
  worldSize: number,
  planet: Planet,
): THREE.BufferGeometry {
  // We don't know the exact count upfront; use dynamic arrays then convert.
  const positions: number[] = [];
  const colors:    number[] = [];
  const normals:   number[] = [];
  const indices:   number[] = [];

  const NORMALS: [number, number, number][] = [
    [ 1,  0,  0], // +X
    [-1,  0,  0], // −X
    [ 0,  1,  0], // +Y
    [ 0, -1,  0], // −Y
    [ 0,  0,  1], // +Z
    [ 0,  0, -1], // −Z
  ];

  let vertexCount = 0;

  for (let z = 0; z < worldSize; z++) {
    for (let x = 0; x < worldSize; x++) {
      const h = hmap[z]?.[x] ?? 0;
      if (h <= 0) continue; // void / island gap

      // Stack of solid voxels from y=1 to y=h
      for (let y = 1; y <= h; y++) {
        const isTopVoxel = y === h;

        // Find the highest representative height for colour scaling
        const [r, g, b] = getBlockColor(x, z, y, h, isTopVoxel, planet);

        for (const face of FACES) {
          // Check neighbour
          const nx = x + face.nx;
          const ny = y + face.ny;
          const nz = z + face.nz;

          let neighbourSolid = false;

          if (face.ny === 0) {
            // Horizontal face: neighbour is solid if its column height >= y
            const neighbourH = getTerrainHeight(hmap, nx, nz, worldSize);
            neighbourSolid = neighbourH >= y;
          } else if (face.ny === 1) {
            // Top face: neighbour above is solid only if y < h (not the top voxel)
            neighbourSolid = !isTopVoxel; // if y < h there's a voxel above
          } else {
            // Bottom face (ny === −1): always expose unless y > 1 and has voxel below
            neighbourSolid = ny >= 1; // voxel below always exists inside the column
          }

          if (neighbourSolid) continue; // face is hidden — skip

          // Emit quad (2 triangles) for this face
          const baseIdx = vertexCount;
          const norm = NORMALS[face.dir];

          for (const [cx, cy, cz] of face.corners) {
            positions.push(x + cx, y + cy, z + cz);
            normals.push(norm[0], norm[1], norm[2]);
            // Slight per-face ambient occlusion on side faces
            const aoFactor = face.dir <= 1 || face.dir >= 4 ? 0.82 : 1.0;
            colors.push(r * aoFactor, g * aoFactor, b * aoFactor);
            vertexCount++;
          }

          // Two triangles: [0,1,2] and [0,2,3]
          indices.push(baseIdx, baseIdx + 1, baseIdx + 2);
          indices.push(baseIdx, baseIdx + 2, baseIdx + 3);
        }
      }
    }
  }

  const geometry = new THREE.BufferGeometry();

  geometry.setAttribute(
    'position',
    new THREE.Float32BufferAttribute(positions, 3),
  );
  geometry.setAttribute(
    'normal',
    new THREE.Float32BufferAttribute(normals, 3),
  );
  geometry.setAttribute(
    'color',
    new THREE.Float32BufferAttribute(colors, 3),
  );
  geometry.setIndex(indices);

  geometry.computeBoundingBox();
  geometry.computeBoundingSphere();

  return geometry;
}

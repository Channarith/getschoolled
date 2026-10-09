// Coloring pages, numbered dots, and outlines for the vision-arcade picture games.
// Coordinates are fractions of the stage (origin top-left), so a finger tip in
// stage space can be tested without the camera.

function ellipse(cx, cy, rx, ry, steps = 22) {
  const points = [];
  for (let i = 0; i < steps; i += 1) {
    const turn = (i / steps) * Math.PI * 2;
    points.push([cx + Math.cos(turn) * rx, cy + Math.sin(turn) * ry]);
  }
  return points;
}

function star(cx, cy, outer, inner, spikes = 5) {
  const points = [];
  for (let i = 0; i < spikes * 2; i += 1) {
    const radius = i % 2 === 0 ? outer : inner;
    const turn = -Math.PI / 2 + (i * Math.PI) / spikes;
    points.push([cx + Math.cos(turn) * radius, cy + Math.sin(turn) * radius]);
  }
  return points;
}

function heart(cx, cy, scale) {
  const points = [];
  for (let i = 0; i < 28; i += 1) {
    const turn = (i / 28) * Math.PI * 2;
    const x = 16 * Math.sin(turn) ** 3;
    const y = 13 * Math.cos(turn) - 5 * Math.cos(2 * turn) - 2 * Math.cos(3 * turn) - Math.cos(4 * turn);
    points.push([cx + (x / 34) * scale, cy - (y / 34) * scale]);
  }
  return points;
}

function crescent(cx, cy, radius) {
  const points = [];
  const sweep = Math.PI * 1.15;
  const start = -sweep / 2;
  for (let i = 0; i <= 16; i += 1) {
    const turn = start + (i / 16) * sweep;
    points.push([cx + Math.cos(turn) * radius, cy + Math.sin(turn) * radius]);
  }
  for (let i = 16; i >= 0; i -= 1) {
    const turn = start + (i / 16) * sweep;
    points.push([
      cx + Math.cos(turn) * radius * 0.62 + radius * 0.34,
      cy + Math.sin(turn) * radius * 0.78,
    ]);
  }
  return points;
}

function rect(x, y, width, height) {
  return [[x, y], [x + width, y], [x + width, y + height], [x, y + height]];
}

function part(name, colorName, color, points) {
  return { name, colorName, color, points };
}

function picture(word, segments, outline) {
  return { word, segments, outline: outline || segments[0].points };
}

const SCENES = [
  picture("apple", [
    part("apple", "red", "#ef4444", ellipse(0.5, 0.44, 0.16, 0.18)),
    part("leaf", "green", "#22c55e", [[0.52, 0.28], [0.66, 0.2], [0.7, 0.28], [0.56, 0.33]]),
    part("stem", "brown", "#a16207", rect(0.47, 0.24, 0.06, 0.12)),
  ]),
  picture("ball", [
    part("ball", "orange", "#fb923c", ellipse(0.5, 0.44, 0.17, 0.17)),
    part("stripe", "white", "#f8fafc", rect(0.34, 0.4, 0.32, 0.08)),
  ]),
  picture("cat", [
    part("face", "orange", "#fb923c", ellipse(0.5, 0.46, 0.15, 0.14)),
    part("left ear", "pink", "#f472b6", [[0.38, 0.36], [0.34, 0.2], [0.46, 0.32]]),
    part("right ear", "pink", "#f472b6", [[0.62, 0.36], [0.66, 0.2], [0.54, 0.32]]),
    part("nose", "pink", "#fb7185", ellipse(0.5, 0.5, 0.035, 0.028)),
  ]),
  picture("dragon", [
    part("body", "green", "#22c55e", ellipse(0.48, 0.46, 0.18, 0.12)),
    part("wing", "orange", "#fb923c", [[0.42, 0.4], [0.28, 0.22], [0.55, 0.34]]),
    part("fire", "red", "#ef4444", [[0.64, 0.42], [0.78, 0.36], [0.76, 0.48], [0.64, 0.5]]),
  ]),
  picture("elephant", [
    part("body", "gray", "#94a3b8", ellipse(0.46, 0.46, 0.16, 0.14)),
    part("ear", "gray", "#cbd5e1", ellipse(0.34, 0.4, 0.08, 0.1)),
    part("tusk", "white", "#f8fafc", [[0.58, 0.5], [0.7, 0.58], [0.66, 0.62], [0.56, 0.54]]),
  ]),
  picture("fish", [
    part("body", "blue", "#38bdf8", ellipse(0.48, 0.44, 0.16, 0.1)),
    part("tail", "orange", "#fb923c", [[0.3, 0.44], [0.18, 0.32], [0.18, 0.56]]),
    part("eye", "white", "#f8fafc", ellipse(0.56, 0.41, 0.03, 0.03)),
  ]),
  picture("grape", [
    part("grape", "purple", "#a855f7", ellipse(0.46, 0.4, 0.07, 0.07)),
    part("grape", "purple", "#9333ea", ellipse(0.56, 0.4, 0.07, 0.07)),
    part("grape", "purple", "#7e22ce", ellipse(0.51, 0.52, 0.07, 0.07)),
    part("leaf", "green", "#22c55e", [[0.46, 0.3], [0.56, 0.22], [0.6, 0.32]]),
  ]),
  picture("heart", [
    part("heart", "pink", "#f472b6", heart(0.5, 0.46, 0.34)),
    part("shine", "red", "#ef4444", ellipse(0.42, 0.4, 0.04, 0.035)),
  ]),
  picture("ice cream", [
    part("scoop", "pink", "#f472b6", ellipse(0.5, 0.34, 0.12, 0.1)),
    part("cone", "brown", "#a16207", [[0.4, 0.4], [0.6, 0.4], [0.5, 0.66]]),
    part("cherry", "red", "#ef4444", ellipse(0.56, 0.24, 0.035, 0.035)),
  ]),
  picture("jellyfish", [
    part("bell", "purple", "#a855f7", ellipse(0.5, 0.34, 0.14, 0.1)),
    part("tentacles", "pink", "#f472b6", [[0.38, 0.4], [0.34, 0.62], [0.42, 0.58], [0.46, 0.66], [0.52, 0.56], [0.58, 0.66], [0.64, 0.56], [0.62, 0.4]]),
  ]),
  picture("kite", [
    part("kite", "red", "#ef4444", [[0.5, 0.18], [0.68, 0.4], [0.5, 0.62], [0.32, 0.4]]),
    part("cross", "yellow", "#facc15", rect(0.47, 0.24, 0.06, 0.32)),
    part("tail", "blue", "#38bdf8", [[0.5, 0.62], [0.44, 0.74], [0.56, 0.78], [0.5, 0.66]]),
  ]),
  picture("lion", [
    part("mane", "orange", "#fb923c", ellipse(0.5, 0.44, 0.2, 0.18)),
    part("face", "yellow", "#facc15", ellipse(0.5, 0.46, 0.11, 0.1)),
    part("nose", "brown", "#a16207", ellipse(0.5, 0.5, 0.03, 0.025)),
  ], ellipse(0.5, 0.44, 0.2, 0.18)),
  picture("moon", [
    part("moon", "yellow", "#facc15", crescent(0.48, 0.42, 0.18)),
    part("crater", "gray", "#94a3b8", ellipse(0.44, 0.4, 0.035, 0.03)),
  ]),
  picture("nest", [
    part("nest", "brown", "#a16207", [[0.3, 0.4], [0.7, 0.4], [0.62, 0.62], [0.38, 0.62]]),
    part("egg", "blue", "#38bdf8", ellipse(0.44, 0.46, 0.06, 0.08)),
    part("egg", "white", "#f8fafc", ellipse(0.56, 0.46, 0.06, 0.08)),
  ]),
  picture("octopus", [
    part("head", "purple", "#a855f7", ellipse(0.5, 0.36, 0.14, 0.12)),
    part("arms", "pink", "#f472b6", [[0.36, 0.44], [0.28, 0.66], [0.4, 0.6], [0.46, 0.7], [0.54, 0.58], [0.62, 0.7], [0.7, 0.58], [0.64, 0.44]]),
    part("eye", "white", "#f8fafc", ellipse(0.46, 0.34, 0.028, 0.028)),
  ]),
  picture("popcorn", [
    part("bucket", "red", "#ef4444", [[0.36, 0.42], [0.64, 0.42], [0.58, 0.68], [0.42, 0.68]]),
    part("kernel", "yellow", "#facc15", ellipse(0.44, 0.36, 0.07, 0.06)),
    part("kernel", "white", "#f8fafc", ellipse(0.56, 0.34, 0.07, 0.06)),
  ]),
  picture("queen", [
    part("dress", "purple", "#a855f7", [[0.38, 0.42], [0.62, 0.42], [0.68, 0.7], [0.32, 0.7]]),
    part("face", "pink", "#fdba74", ellipse(0.5, 0.34, 0.07, 0.07)),
    part("crown", "yellow", "#facc15", [[0.4, 0.3], [0.42, 0.18], [0.5, 0.28], [0.58, 0.18], [0.6, 0.3]]),
  ]),
  picture("rocket", [
    part("body", "white", "#f8fafc", rect(0.44, 0.28, 0.12, 0.28)),
    part("nose", "red", "#ef4444", [[0.44, 0.28], [0.56, 0.28], [0.5, 0.14]]),
    part("flame", "orange", "#fb923c", [[0.46, 0.56], [0.54, 0.56], [0.5, 0.7]]),
  ]),
  picture("star", [
    part("star", "yellow", "#facc15", star(0.5, 0.44, 0.2, 0.08)),
    part("center", "orange", "#fb923c", ellipse(0.5, 0.44, 0.045, 0.045)),
  ]),
  picture("teddy", [
    part("head", "brown", "#a16207", ellipse(0.5, 0.46, 0.13, 0.12)),
    part("left ear", "brown", "#92400e", ellipse(0.36, 0.32, 0.055, 0.055)),
    part("right ear", "brown", "#92400e", ellipse(0.64, 0.32, 0.055, 0.055)),
    part("snout", "tan", "#fdba74", ellipse(0.5, 0.52, 0.06, 0.045)),
  ]),
  picture("umbrella", [
    part("canopy", "red", "#ef4444", [[0.28, 0.4], [0.36, 0.24], [0.5, 0.18], [0.64, 0.24], [0.72, 0.4]]),
    part("handle", "brown", "#a16207", rect(0.47, 0.4, 0.06, 0.26)),
  ]),
  picture("violin", [
    part("body", "brown", "#a16207", ellipse(0.5, 0.5, 0.12, 0.16)),
    part("neck", "tan", "#fdba74", rect(0.46, 0.2, 0.08, 0.18)),
    part("strings", "black", "#111827", rect(0.485, 0.22, 0.03, 0.36)),
  ]),
  picture("whale", [
    part("body", "blue", "#38bdf8", ellipse(0.48, 0.46, 0.2, 0.12)),
    part("belly", "white", "#f8fafc", ellipse(0.48, 0.52, 0.12, 0.05)),
    part("tail", "blue", "#0284c7", [[0.26, 0.44], [0.14, 0.32], [0.16, 0.5], [0.14, 0.6], [0.28, 0.5]]),
  ]),
  picture("xylophone", [
    part("bar", "red", "#ef4444", rect(0.28, 0.28, 0.1, 0.28)),
    part("bar", "orange", "#fb923c", rect(0.4, 0.32, 0.1, 0.24)),
    part("bar", "yellow", "#facc15", rect(0.52, 0.36, 0.1, 0.2)),
    part("bar", "green", "#22c55e", rect(0.64, 0.4, 0.1, 0.16)),
  ], rect(0.26, 0.26, 0.5, 0.32)),
  picture("yo-yo", [
    part("disc", "red", "#ef4444", ellipse(0.44, 0.44, 0.1, 0.1)),
    part("disc", "blue", "#38bdf8", ellipse(0.56, 0.44, 0.1, 0.1)),
    part("string", "yellow", "#facc15", rect(0.48, 0.44, 0.04, 0.22)),
  ]),
  picture("zebra", [
    part("body", "white", "#f8fafc", ellipse(0.5, 0.46, 0.2, 0.12)),
    part("stripe", "black", "#111827", rect(0.4, 0.36, 0.05, 0.2)),
    part("stripe", "black", "#111827", rect(0.52, 0.36, 0.05, 0.2)),
    part("mane", "black", "#111827", [[0.34, 0.4], [0.28, 0.24], [0.4, 0.36]]),
  ]),
];

const BY_WORD = Object.fromEntries(SCENES.map((scene) => [scene.word, scene]));

export function sceneForWord(word) {
  return BY_WORD[String(word || "").toLowerCase()] || BY_WORD.apple;
}

export function pictureWords() {
  return SCENES.map((scene) => scene.word);
}

export function centroid(points) {
  if (!points?.length) return [0.5, 0.5];
  let x = 0;
  let y = 0;
  for (const point of points) {
    x += point[0];
    y += point[1];
  }
  return [x / points.length, y / points.length];
}

export function pointInPolygon(x, y, polygon) {
  if (!polygon || polygon.length < 3) return false;
  let inside = false;
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i, i += 1) {
    const [xi, yi] = polygon[i];
    const [xj, yj] = polygon[j];
    const crosses = (yi > y) !== (yj > y)
      && x < ((xj - xi) * (y - yi)) / ((yj - yi) || 1e-9) + xi;
    if (crosses) inside = !inside;
  }
  return inside;
}

// Later segments sit on top, so a leaf wins where it overlaps the apple.
export function segmentAt(scene, x, y) {
  const segments = scene?.segments || [];
  for (let index = segments.length - 1; index >= 0; index -= 1) {
    if (pointInPolygon(x, y, segments[index].points)) return index;
  }
  return -1;
}

function pointAlong(outline, t) {
  const count = outline.length;
  let length = 0;
  const edges = [];
  for (let i = 0; i < count; i += 1) {
    const start = outline[i];
    const end = outline[(i + 1) % count];
    const span = Math.hypot(end[0] - start[0], end[1] - start[1]);
    edges.push(span);
    length += span;
  }
  let remain = ((t % 1) + 1) % 1 * (length || 1);
  for (let i = 0; i < count; i += 1) {
    if (remain <= edges[i] || i === count - 1) {
      const span = edges[i] || 1;
      const mix = Math.max(0, Math.min(1, remain / span));
      const start = outline[i];
      const end = outline[(i + 1) % count];
      return [start[0] + (end[0] - start[0]) * mix, start[1] + (end[1] - start[1]) * mix];
    }
    remain -= edges[i];
  }
  return outline[0];
}

export function dotsFor(outline, count) {
  const source = outline || [];
  if (source.length < 2) return [];
  const total = Math.max(4, Number(count) || 8);
  const dots = [];
  for (let i = 0; i < total; i += 1) {
    const [x, y] = pointAlong(source, i / total);
    dots.push({ n: i + 1, x, y });
  }
  return dots;
}

export function dotRadius(ageBand) {
  return ageBand === "4-6" ? 0.075 : 0.05;
}

export function dotHit(dot, x, y, radius) {
  if (!dot) return false;
  return Math.hypot(dot.x - x, dot.y - y) <= radius;
}

export function outlineSamples(outline, count = 18) {
  if (!outline || outline.length < 2) return [];
  const total = Math.max(4, count);
  const samples = [];
  for (let i = 0; i < total; i += 1) samples.push(pointAlong(outline, i / total));
  return samples;
}

export function outlineCoverage(trail, outline, radius) {
  const samples = outlineSamples(outline, 18);
  if (!samples.length || !trail?.length) return 0;
  const reach = Math.max(0.01, Number(radius) || 0.06);
  let hits = 0;
  for (const [x, y] of samples) {
    if (trail.some((point) => Math.hypot((point.x ?? 0) - x, (point.y ?? 0) - y) <= reach)) hits += 1;
  }
  return hits / samples.length;
}

export function outlinePassed(coverage, ageBand) {
  return coverage >= (ageBand === "4-6" ? 0.4 : 0.55);
}

export function colorLine(scene) {
  return (scene?.segments || [])
    .map((segment) => `${segment.name} is ${segment.colorName}`)
    .join(", ");
}

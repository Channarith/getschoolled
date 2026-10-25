// Keeps the MediaPipe files (about 21 MB: two wasm builds, three models) in persistent browser storage.
//
// Why: the HTTP cache of a phone browser or an Android WebView can refuse entries this large, so a camera game
// downloaded the same 9 MB .wasm three times (face, hand and outline tasks each start their own copy) on every
// launch. Here each file is fetched once, stored in the Cache Storage API (IndexedDB where that is missing, as in
// some iPhone WebViews), and handed to MediaPipe from memory. If no storage works, callers fall back to plain URLs.
const VERSION = "0.10.14-1";
const CACHE_NAME = `gs-vision-assets-${VERSION}`;
const BASE = "/vendor/vision";
const SIMD_PROBE = new Uint8Array([0, 97, 115, 109, 1, 0, 0, 0, 1, 5, 1, 96, 0, 1, 123, 3, 2, 1, 0, 10, 10, 1, 8, 0, 65, 0, 253, 15, 253, 98, 11]);

function simdSupported() {
  try { return typeof WebAssembly === "object" && WebAssembly.validate(SIMD_PROBE); } catch (_) { return false; }
}

function idb() {
  return new Promise((resolve, reject) => {
    const open = indexedDB.open("gs-vision-assets", 1);
    open.onupgradeneeded = () => open.result.createObjectStore("files");
    open.onsuccess = () => resolve(open.result);
    open.onerror = () => reject(open.error);
  });
}
const idbRequest = (request) => new Promise((resolve, reject) => { request.onsuccess = () => resolve(request.result); request.onerror = () => reject(request.error); });

const backends = {
  async cacheStorage() {
    if (typeof caches === "undefined") throw new Error("no Cache Storage");
    const cache = await caches.open(CACHE_NAME);
    return {
      name: "cache-storage",
      async get(url) { const hit = await cache.match(url); return hit ? hit.arrayBuffer() : null; },
      async put(url, buffer, type) { await cache.put(url, new Response(buffer.slice(0), { headers: { "content-type": type } })); },
    };
  },
  async indexedDb() {
    if (typeof indexedDB === "undefined") throw new Error("no IndexedDB");
    const db = await idb();
    const store = (mode) => db.transaction("files", mode).objectStore("files");
    return {
      name: "indexeddb",
      async get(url) { return (await idbRequest(store("readonly").get(`${VERSION}:${url}`))) || null; },
      async put(url, buffer) { await idbRequest(store("readwrite").put(buffer.slice(0), `${VERSION}:${url}`)); },
    };
  },
};

async function pickBackend() {
  for (const make of [backends.cacheStorage, backends.indexedDb]) {
    try {
      const backend = await make();
      // A backend can exist but refuse writes (private mode, quota): prove it with a tiny round trip.
      const probe = `${BASE}/.probe`;
      await backend.put(probe, new ArrayBuffer(8), "application/octet-stream");
      if ((await backend.get(probe))?.byteLength === 8) return backend;
    } catch (_) { /* try the next one */ }
  }
  return null;
}

const TYPES = { js: "text/javascript", wasm: "application/wasm" };

/**
 * Returns { files, models, stats }.
 *   files   {wasmLoaderPath, wasmBinaryPath}  blob: URLs for FilesetResolver-style options
 *   models  {face, hand, segment}             Uint8Array (use .slice() per attempt) for baseOptions.modelAssetBuffer
 *   stats   {backend, hits, misses, bytes, networkBytes, ms, perFile}
 */
export async function loadVisionAssets({ segment = true, onFile } = {}) {
  const t0 = performance.now();
  const simd = simdSupported();
  const loader = `${BASE}/wasm/${simd ? "vision_wasm_internal" : "vision_wasm_nosimd_internal"}.js`;
  const wasm = `${BASE}/wasm/${simd ? "vision_wasm_internal" : "vision_wasm_nosimd_internal"}.wasm`;
  const wanted = [["loader", loader, TYPES.js], ["wasm", wasm, TYPES.wasm], ["face", `${BASE}/face_landmarker.task`, "application/octet-stream"], ["hand", `${BASE}/hand_landmarker.task`, "application/octet-stream"]];
  if (segment) wanted.push(["segment", `${BASE}/selfie_segmenter.tflite`, "application/octet-stream"]);
  const backend = await pickBackend();
  const stats = { backend: backend?.name || "none", simd, hits: 0, misses: 0, bytes: 0, networkBytes: 0, perFile: {} };
  const buffers = {};
  for (const [key, url, type] of wanted) {
    const started = performance.now();
    let buffer = null; let from = "network";
    try { buffer = backend ? await backend.get(url) : null; } catch (_) { buffer = null; }
    if (buffer && buffer.byteLength > 1000) { from = "cache"; stats.hits += 1; }
    else {
      stats.misses += 1;
      const response = await fetch(url, { credentials: "same-origin" });
      if (!response.ok) throw new Error(`${url.split("/").pop()}: HTTP ${response.status}`);
      buffer = await response.arrayBuffer();
      stats.networkBytes += buffer.byteLength;
      if (backend) { try { await backend.put(url, buffer, type); } catch (_) { /* quota: still usable this session */ } }
    }
    stats.bytes += buffer.byteLength;
    stats.perFile[key] = { from, bytes: buffer.byteLength, ms: Math.round(performance.now() - started) };
    buffers[key] = buffer;
    onFile?.(key, stats.perFile[key]);
  }
  stats.ms = Math.round(performance.now() - t0);
  const blob = (buffer, type) => URL.createObjectURL(new Blob([buffer], { type }));
  return {
    files: { wasmLoaderPath: blob(buffers.loader, TYPES.js), wasmBinaryPath: blob(buffers.wasm, TYPES.wasm) },
    models: { face: new Uint8Array(buffers.face), hand: new Uint8Array(buffers.hand), segment: buffers.segment ? new Uint8Array(buffers.segment) : null },
    stats,
  };
}

export async function clearVisionAssets() {
  try { await caches?.delete?.(CACHE_NAME); } catch (_) { /* none */ }
  try { indexedDB?.deleteDatabase?.("gs-vision-assets"); } catch (_) { /* none */ }
}

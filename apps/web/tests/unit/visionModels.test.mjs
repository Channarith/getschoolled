import test from "node:test";
import assert from "node:assert/strict";
import {
  fetchVisionModel,
  visionModelCandidateUrls,
  visionModelStaticUrl,
} from "../../app/lib/visionModels.ts";

const YUNET = "face_detection_yunet_2023mar.onnx";
const PERCEPTION = `/perception/vision/models/${YUNET}`;

test("face model candidates prefer the same-origin static file", () => {
  assert.equal(visionModelStaticUrl(YUNET), `/vision-models/${YUNET}`);
  const urls = visionModelCandidateUrls(YUNET, PERCEPTION);
  assert.deepEqual(urls, [`/vision-models/${YUNET}`, PERCEPTION]);
});

test("a failed static fetch is retried once, then the perception URL is used", async () => {
  const calls = [];
  const previous = globalThis.fetch;
  globalThis.fetch = async (url, opts) => {
    calls.push([String(url), opts?.cache]);
    const perception = String(url).includes("/vision/models/");
    const reloaded = opts?.cache === "reload";
    if (perception && reloaded) {
      return new Response(new Uint8Array([9, 8, 7]), { status: 200 });
    }
    return new Response("missing", { status: perception ? 503 : 404 });
  };
  try {
    const bytes = await fetchVisionModel(YUNET, PERCEPTION);
    assert.deepEqual(Array.from(bytes), [9, 8, 7]);
    assert.deepEqual(calls.map((call) => call[1]), ["default", "reload", "default", "reload"]);
    assert.equal(calls[0][0], `/vision-models/${YUNET}`);
    assert.equal(calls[2][0], PERCEPTION);
    assert.equal(calls.some((call) => call[1] === "force-cache"), false);
  } finally {
    globalThis.fetch = previous;
  }
});

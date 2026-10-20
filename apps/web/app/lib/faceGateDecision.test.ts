import assert from "node:assert/strict";
import { decideFaceScan, FACE_SCAN_LIMIT_MS } from "./faceGateDecision";

assert.equal(decideFaceScan(true, 0), "match");
assert.equal(decideFaceScan(true, FACE_SCAN_LIMIT_MS), "match");
assert.equal(decideFaceScan(false, 0), "wait");
assert.equal(decideFaceScan(false, FACE_SCAN_LIMIT_MS - 1), "wait");
assert.equal(decideFaceScan(false, FACE_SCAN_LIMIT_MS), "timeout");
assert.equal(decideFaceScan(false, FACE_SCAN_LIMIT_MS + 5000), "timeout");
assert.equal(decideFaceScan(false, 1000, 1000), "timeout");
assert.equal(decideFaceScan(true, 1000, 1000), "match");

console.log("faceGateDecision ok");

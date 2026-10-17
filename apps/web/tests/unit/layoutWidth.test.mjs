import test from "node:test";
import assert from "node:assert/strict";
import {
  LAYOUT_WIDTH,
  EXPANDED_LAYOUT_MEDIA,
  layoutWidthClass,
  learningModesPerPage,
  isImmersiveSetupPath,
} from "../../app/lib/layoutWidth.ts";

test("layout width class boundaries", () => {
  assert.equal(layoutWidthClass(320), "compact");
  assert.equal(layoutWidthClass(LAYOUT_WIDTH.compactMax), "compact");
  assert.equal(layoutWidthClass(LAYOUT_WIDTH.mediumMin), "medium");
  assert.equal(layoutWidthClass(LAYOUT_WIDTH.mediumMax), "medium");
  assert.equal(layoutWidthClass(LAYOUT_WIDTH.expandedMin), "expanded");
  assert.equal(layoutWidthClass(1920), "expanded");
});

test("learning modes per page matches expanded breakpoint", () => {
  assert.equal(learningModesPerPage(360), 1);
  assert.equal(learningModesPerPage(LAYOUT_WIDTH.mediumMax), 1);
  assert.equal(learningModesPerPage(LAYOUT_WIDTH.expandedMin), 2);
});

test("expanded layout media query documents breakpoint", () => {
  assert.match(EXPANDED_LAYOUT_MEDIA, /840/);
});

test("immersive setup paths", () => {
  assert.equal(isImmersiveSetupPath("/onboarding"), true);
  assert.equal(isImmersiveSetupPath("/onboarding/extra"), true);
  assert.equal(isImmersiveSetupPath("/login"), false);
});

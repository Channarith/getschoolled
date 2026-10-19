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

test("learning modes per page is always one across every viewport", () => {
  // One card per page everywhere — phones, tablets, and desktops — so the
  // MascotActor in the left art pane keeps a full-size, visibly acting
  // stage on wide screens instead of a slim 320px gutter.
  assert.equal(learningModesPerPage(320), 1);
  assert.equal(learningModesPerPage(360), 1);
  assert.equal(learningModesPerPage(LAYOUT_WIDTH.compactMax), 1);
  assert.equal(learningModesPerPage(LAYOUT_WIDTH.mediumMin), 1);
  assert.equal(learningModesPerPage(LAYOUT_WIDTH.mediumMax), 1);
  assert.equal(learningModesPerPage(LAYOUT_WIDTH.expandedMin), 1);
  assert.equal(learningModesPerPage(1024), 1);
  assert.equal(learningModesPerPage(1440), 1);
  assert.equal(learningModesPerPage(1920), 1);
});

test("expanded layout media query documents breakpoint", () => {
  assert.match(EXPANDED_LAYOUT_MEDIA, /840/);
});

test("immersive setup paths", () => {
  assert.equal(isImmersiveSetupPath("/onboarding"), true);
  assert.equal(isImmersiveSetupPath("/onboarding/extra"), true);
  assert.equal(isImmersiveSetupPath("/login"), false);
});

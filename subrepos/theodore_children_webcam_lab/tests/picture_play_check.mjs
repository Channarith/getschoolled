import assert from "node:assert/strict";
import {
  colorLine, dotHit, dotRadius, dotsFor, outlineCoverage, outlinePassed,
  pictureWords, pointInPolygon, sceneForWord, segmentAt,
} from "../src/theodore_children_webcam_lab/static/picture_play.js";

const WORDS = [
  "apple", "ball", "cat", "dragon", "elephant", "fish", "grape", "heart",
  "ice cream", "jellyfish", "kite", "lion", "moon", "nest", "octopus",
  "popcorn", "queen", "rocket", "star", "teddy", "umbrella", "violin",
  "whale", "xylophone", "yo-yo", "zebra",
];

assert.deepEqual(pictureWords(), WORDS);

for (const word of WORDS) {
  const scene = sceneForWord(word);
  assert.ok(scene.segments.length >= 2, `${word} needs more than one color`);
  assert.ok(scene.outline.length >= 4, `${word} needs an outline`);
  for (const segment of scene.segments) {
    assert.ok(segment.colorName, `${word} ${segment.name} needs a recommended color`);
    assert.match(segment.color, /^#[0-9a-f]{6}$/i);
    const [x, y] = segment.points[0];
    assert.ok(x > 0.05 && x < 0.95 && y > 0.05 && y < 0.85, `${word} stays on the page`);
  }
  const dots = dotsFor(scene.outline, 8);
  assert.deepEqual(dots.map((dot) => dot.n), [1, 2, 3, 4, 5, 6, 7, 8]);
}

const apple = sceneForWord("apple");
assert.equal(segmentAt(apple, 0.5, 0.44), 0, "the apple body is red");
assert.equal(apple.segments[segmentAt(apple, 0.62, 0.26)].colorName, "green");
assert.equal(segmentAt(apple, 0.02, 0.02), -1);
assert.match(colorLine(apple), /apple is red/);
assert.match(colorLine(apple), /leaf is green/);

const youngDots = dotsFor(apple.outline, 6);
assert.equal(youngDots.length, 6);
assert.equal(dotHit(youngDots[0], youngDots[0].x, youngDots[0].y, dotRadius("4-6")), true);
assert.equal(dotHit(youngDots[1], youngDots[0].x, youngDots[0].y, dotRadius("7-10")), false);

const along = apple.outline.map(([x, y]) => ({ x, y }));
assert.equal(outlinePassed(outlineCoverage(along, apple.outline, 0.05), "7-10"), true);
assert.equal(outlinePassed(outlineCoverage([{ x: 0.5, y: 0.44 }], apple.outline, 0.05), "4-6"), false);

const heart = sceneForWord("heart");
assert.equal(pointInPolygon(0.5, 0.46, heart.segments[0].points), true);

console.log("picture play OK");

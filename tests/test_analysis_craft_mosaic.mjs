import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { proportionalTreemap } = require("../analysis_view.js");
const epsilon = 1e-9;

function close(actual, expected, message) {
  assert.ok(Math.abs(actual - expected) <= epsilon, `${message}: ${actual} versus ${expected}`);
}

function verifyPartition(weights, aspectRatio) {
  const items = weights.map((weight, index) => ({ label: `Category ${index}`, weight }));
  const original = JSON.stringify(items);
  const positive = items.filter(item => item.weight > 0);
  const total = positive.reduce((sum, item) => sum + item.weight, 0);
  const rectangles = proportionalTreemap(items, aspectRatio);
  assert.equal(JSON.stringify(items), original, "Layout must not change the input cohort");
  assert.equal(rectangles.length, positive.length, "Every positive category has exactly one tile");
  assert.equal(new Set(rectangles.map(rectangle => rectangle.sourceIndex)).size, positive.length);

  for (const rectangle of rectangles) {
    const item = items[rectangle.sourceIndex];
    assert.equal(rectangle.item, item, "A tile retains the correct category identity");
    for (const key of ["x", "y", "width", "height", "areaShare"]) {
      assert.ok(Number.isFinite(rectangle[key]), `${key} must be finite`);
    }
    assert.ok(rectangle.width > 0 && rectangle.height > 0, "Positive categories have positive area");
    assert.ok(rectangle.x >= -epsilon && rectangle.y >= -epsilon, "Tiles stay within the top/left bounds");
    assert.ok(rectangle.x + rectangle.width <= 100 + epsilon, "Tiles stay within the right bound");
    assert.ok(rectangle.y + rectangle.height <= 100 + epsilon, "Tiles stay within the bottom bound");
    close(rectangle.areaShare, item.weight / total, "Area encodes the actual cohort share");
    close(rectangle.width * rectangle.height / 10000, item.weight / total, "Rendered percentage dimensions encode the same share");
  }

  for (let i = 0; i < rectangles.length; i += 1) {
    for (let j = i + 1; j < rectangles.length; j += 1) {
      const a = rectangles[i], b = rectangles[j];
      const overlapWidth = Math.min(a.x + a.width, b.x + b.width) - Math.max(a.x, b.x);
      const overlapHeight = Math.min(a.y + a.height, b.y + b.height) - Math.max(a.y, b.y);
      assert.ok(overlapWidth <= epsilon || overlapHeight <= epsilon, "Tiles must not obscure neighboring categories");
    }
  }
  close(rectangles.reduce((sum, rectangle) => sum + rectangle.areaShare, 0), positive.length ? 1 : 0,
    "The displayed mosaic uses the complete cohort area");
  return rectangles;
}

// Includes the screenshot's 111-report distribution, sparse input, an even
// cohort, and dominant-category cases whose small tiles must retain honest area.
const screenshotWeights = [37, 31, 9, 8, 8, 6, 3, 2, 7];
const cohorts = [
  screenshotWeights, [], [0, 0, 0], [-3, 0, 5, 0, 2], [1],
  Array.from({ length: 24 }, () => 1),
  [1000000, 1, 1, 1, 1], [0.0001, 0, 0.5, 10000, 0.002],
];
for (const aspectRatio of [0.4, 0.75, 1, 2, 3, 5]) {
  for (const weights of cohorts) verifyPartition(weights, aspectRatio);
}

const screenshotItems = screenshotWeights.map((weight, index) => ({ weight, label: index === 2 ? "Triangle" : `Category ${index}` }));
assert.deepEqual(proportionalTreemap(screenshotItems), proportionalTreemap(screenshotItems, 1),
  "Omitting dimensions retains square-layout compatibility");
const squareTriangle = proportionalTreemap(screenshotItems, 1).find(tile => tile.item.label === "Triangle");
const wideTriangle = proportionalTreemap(screenshotItems, 3).find(tile => tile.item.label === "Triangle");
const chartHeight = 280;
assert.ok(squareTriangle.height / 100 * chartHeight < 60, "Fixture reproduces the shallow Triangle strip");
assert.ok(wideTriangle.height / 100 * chartHeight >= 90,
  "Using the wide chart's proportions gives Triangle room for its label and percentage");
close(wideTriangle.areaShare, squareTriangle.areaShare, "Readability improvement must not inflate Triangle's share");

console.log("Craft mosaic: proportional area, category identity, bounds, non-overlap and responsive geometry passed.");

import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const performance = require("../webapp/static_public/playback_performance.js");

assert.deepEqual(
  performance.normalizeResultsWindow(413, 0, 60),
  { start: 0, end: 60, size: 60, total: 413 }
);
assert.deepEqual(
  performance.normalizeResultsWindow(25, 99, 60),
  { start: 0, end: 25, size: 60, total: 25 }
);
assert.deepEqual(
  performance.normalizeResultsWindow(413, 400, 60),
  { start: 353, end: 413, size: 60, total: 413 }
);

const centered = performance.resultsWindowForTarget({
  total: 413,
  currentStart: 0,
  targetIndex: 212,
  windowSize: 60,
  margin: 10,
});
assert.equal(centered.changed, true);
assert.equal(centered.start, 192);
assert.equal(centered.end, 252);
assert.ok(centered.targetIndex >= centered.start && centered.targetIndex < centered.end);

const stable = performance.resultsWindowForTarget({
  total: 413,
  currentStart: 192,
  targetIndex: 220,
  windowSize: 60,
  margin: 10,
});
assert.equal(stable.changed, false);
assert.equal(stable.start, 192);

const shifted = performance.shiftResultsWindow({
  total: 413,
  currentStart: 192,
  direction: 1,
  shift: 40,
  windowSize: 60,
});
assert.equal(shifted.start, 232);
assert.equal(shifted.end, 292);
assert.equal(shifted.changed, true);

const lastWindow = performance.shiftResultsWindow({
  total: 413,
  currentStart: 340,
  direction: 1,
  shift: 40,
  windowSize: 60,
});
assert.equal(lastWindow.start, 353);
assert.equal(lastWindow.end, 413);

const normalTiming = performance.adaptivePlaybackTiming({
  baseIntervalMs: 1200,
  targetIntervalMs: 75,
  stepCostMs: 12,
});
assert.equal(normalTiming.delayMs, 75);
assert.equal(normalTiming.effectiveSpeed, 16);
assert.equal(normalTiming.limited, false);

const limitedTiming = performance.adaptivePlaybackTiming({
  baseIntervalMs: 1200,
  targetIntervalMs: 60,
  stepCostMs: 80,
});
assert.equal(limitedTiming.delayMs, 116);
assert.ok(limitedTiming.effectiveSpeed > 10 && limitedTiming.effectiveSpeed < 11);
assert.equal(limitedTiming.limited, true);

const partitions = performance.weightedSamplePartitions(413, 60);
assert.equal(partitions.length, 60);
assert.equal(
  partitions.reduce((total, partition) => total + partition.weight, 0),
  413,
  "weighted density preview must preserve the exact represented event count"
);
assert.ok(partitions.every((partition) => partition.index >= partition.start));
assert.ok(partitions.every((partition) => partition.index < partition.end));
assert.deepEqual(performance.weightedSamplePartitions(3, 20), [
  { index: 0, start: 0, end: 1, weight: 1 },
  { index: 1, start: 1, end: 2, weight: 1 },
  { index: 2, start: 2, end: 3, weight: 1 },
]);
assert.deepEqual(performance.weightedSamplePartitions(0, 20), []);

console.log("playback performance assertions passed");

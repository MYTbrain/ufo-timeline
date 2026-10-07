import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const view = require("../trace_intersection_feasibility.js");

const cell = {
  crossings: 21,
  opportunityNormalizedLift: 3.4,
  fiveYearBandCount: 4,
  sameCraftCrossings: 5,
  differentCraftCrossings: 7,
  mixedEndpointCraftCrossings: 9,
  craftInvolvementCounts: { triangle: 12, disc_saucer: 9 },
  screeningTier: "limited_candidate",
};

assert.equal(view.metricValue(cell, "lift"), 3.4);
assert.equal(view.metricValue(cell, "raw"), 21);
assert.equal(view.metricValue(cell, "different_craft"), 7);
assert.equal(view.metricValue(cell, "craft", "triangle"), 12);
assert.equal(view.metricValue(cell, "craft", "all_no_lights"), 21);
assert.equal(view.humanSignature("disc_saucer+triangle x cigar_cylinder"), "Disc / saucer + Triangle × Cigar / cylinder");

assert.deepEqual(
  view.filterCells([cell, { ...cell, screeningTier: "descriptive_only" }], {
    metric: "lift",
    minimumTier: "limited_candidate",
  }),
  [cell],
);

assert.equal(view.normalizedMetric(1, { maximum: 4 }, "lift"), 0);
assert.equal(view.normalizedMetric(4, { maximum: 4 }, "lift"), 1);
assert.match(view.heatColor(0.9), /^#/);

console.log("trace intersection feasibility view tests passed");

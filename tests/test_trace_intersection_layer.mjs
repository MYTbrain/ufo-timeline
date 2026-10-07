import assert from "node:assert/strict";
import fs from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";

const require = createRequire(import.meta.url);
const layer = require("../trace_intersection_layer.js");
const dataRoot = path.resolve("data/trace_intersection_feasibility_v1");
const oneKm = JSON.parse(fs.readFileSync(path.join(dataRoot, "strict_25km_7d_buffer1.json"), "utf8"));
const fiveKm = JSON.parse(fs.readFileSync(path.join(dataRoot, "strict_25km_7d_buffer5.json"), "utf8"));

const baseOptions = {
  gridKey: "equal_area_26_km2",
  craftScope: "all_no_lights",
  timeScope: "all_time",
};

const all = layer.aggregateProfile(fiveKm, baseOptions);
assert.equal(layer.cellAreaLabel(all.actualCellAreaKm2), "10 mi²");
assert.equal(all.totalCrossings, fiveKm.intersectionMetrics.proper_interior_crossings);
assert.equal(all.totalCrossings, 363);
assert.equal(all.cells.length, fiveKm.grids.equal_area_26_km2.crossingCells);

const crossCraft = layer.aggregateProfile(fiveKm, { ...baseOptions, craftScope: "cross_craft" });
const sameCraft = layer.aggregateProfile(fiveKm, { ...baseOptions, craftScope: "same_craft" });
assert.equal(crossCraft.totalCrossings + sameCraft.totalCrossings, all.totalCrossings);
assert.ok(crossCraft.totalCrossings > sameCraft.totalCrossings);

const fiveYears = layer.aggregateProfile(fiveKm, { ...baseOptions, timeScope: "within_5_years" });
const tenYears = layer.aggregateProfile(fiveKm, { ...baseOptions, timeScope: "within_10_years" });
const fiftyYears = layer.aggregateProfile(fiveKm, { ...baseOptions, timeScope: "within_50_years" });
assert.ok(fiveYears.totalCrossings < tenYears.totalCrossings);
assert.ok(tenYears.totalCrossings < fiftyYears.totalCrossings);
assert.ok(fiftyYears.totalCrossings < all.totalCrossings);

const timeline = layer.aggregateProfile(fiveKm, {
  ...baseOptions,
  timeScope: "timeline",
  timelineRange: { startOrdinal: 722450, endOrdinal: 722460 },
});
assert.ok(timeline.totalCrossings < all.totalCrossings);

const firstCrossing = fiveKm.crossingRecords[0];
const expectedCell = layer.cellIdForCoordinates(
  firstCrossing[0],
  firstCrossing[1],
  fiveKm.grids.equal_area_26_km2.dimensions
);
assert.ok(/^\d+:\d+$/.test(expectedCell));
const bounds = layer.cellBounds(expectedCell, fiveKm.grids.equal_area_26_km2.dimensions);
assert.ok(firstCrossing[0] >= bounds.south && firstCrossing[0] <= bounds.north);
assert.ok(firstCrossing[1] >= bounds.west && firstCrossing[1] <= bounds.east);

const oneAggregation = layer.aggregateProfile(oneKm, baseOptions);
layer.addBufferSurvival(oneAggregation, all);
assert.ok(oneAggregation.cells.some((cell) => cell.bufferOneKmCrossings > cell.bufferFiveKmCrossings));
assert.ok(all.cells.every((cell) => cell.bufferSurvivalPercent >= 0 && cell.bufferSurvivalPercent <= 100));

const connector = (index, craft, ordinal = 720000) => ({
  index,
  eventIds: [index * 2, index * 2 + 1],
  endpointCrafts: [craft, craft],
  craftClass: craft,
  midOrdinal: ordinal,
});
assert.equal(layer.pairMatches(connector(1, "triangle"), connector(2, "disc_saucer"), {
  craftScope: "cross_craft",
  timeScope: "all_time",
}), true);
assert.equal(layer.pairMatches(connector(1, "triangle"), connector(2, "lights"), {
  craftScope: "all_no_lights",
  timeScope: "all_time",
}), false);

console.log("trace intersection layer tests passed");

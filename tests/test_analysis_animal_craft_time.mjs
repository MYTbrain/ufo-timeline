import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const Spatial = require("../analysis_spatial.js");
const ordinal = iso => Date.parse(iso + "T00:00:00Z") / 86400000 + 719163;
const base = (cluster, iso, craft = "triangle", overrides = {}) => ({
  domain: "animal", lane: "animal_public_marker", contextId: "animal-" + cluster,
  clusterId: cluster, contextOrdinal: ordinal(iso), ufoEventId: "active-1",
  craft, distanceRing: "0_25_km", dayLagBand: "same_day", independentEligible: true,
  dateRole: "observed_reported_date", ...overrides,
});
const compute = (neighbors, extra = {}) => Spatial.computeContextAssociations({
  neighbors, activeRows: [{ eventId: "active-1" }, { eventId: "active-2" }],
  permutationCount: 0, bootstrapCount: 0, ...extra,
}).lanes.find(lane => lane.lane === "animal_public_marker");
const cell = (group, craft, period) => group.cells.find(value => value.row === craft && value.column === String(period));

// Multiple nearby reports, repeated source rows and repeated marker members
// cannot multiply a location/date cluster's count within a craft/period cell.
const neighbors = [
  base("a", "1999-12-31"),
  base("a", "1999-12-31", "triangle", { ufoEventId: "active-2", dayLag: 2 }),
  base("a", "1999-12-31", "triangle", { contextId: "same-location-date-member" }),
  base("a", "1999-12-31", "disc_saucer"),
  base("b", "2001-04-01", "triangle"),
  base("control-only", "2010-01-01", "control_craft", { dateRole: "matched_control_minus_1y" }),
  base("inactive", "2011-01-01", "inactive_craft", { ufoEventId: "not-active" }),
  base("origin", "2012-01-01", "origin_craft", { originUfoExcluded: true }),
  base("publisher", "2013-01-01", "publisher_craft", { originPublisherExcluded: true }),
  base("non-independent", "2014-01-01", "excluded_craft", { independentEligible: false }),
  base("no-neighbor", "2015-01-01", "none", { ufoEventId: "" }),
  base("no-cluster", "2016-01-01", "no_cluster_craft", { clusterId: "" }),
];
const before = JSON.stringify(neighbors);
const lane = compute(neighbors);
const { yearly, decadal } = lane.temporal.craft;
assert.deepEqual(yearly.rows, ["disc_saucer", "triangle"]);
assert.deepEqual(yearly.columns, ["1999", "2001"]);
assert.equal(cell(yearly, "triangle", 1999).observedCount, 1);
assert.equal(cell(yearly, "triangle", 2001).observedCount, 1);
assert.equal(cell(yearly, "disc_saucer", 2001).observedCount, 0, "Zero is a valid count in the observed craft/period domain");
assert.equal(cell(yearly, "disc_saucer", 2001).estimateAvailable, true);
assert.deepEqual(decadal.columns, ["1990", "2000"]);
assert.equal(yearly.metadata.activeReportCount, 2);
assert.equal(yearly.metadata.activeTimedReportCount, 2);
assert.equal(yearly.metadata.activeMembershipCount, 3, "A cluster can belong to more than one neighboring craft category");
assert.equal(yearly.metadata.referenceReportCount, null);
assert.equal(yearly.metadata.excludedControlRowCount, 1);
assert.equal(yearly.metadata.excludedOriginRowCount, 2);
assert.equal(yearly.metadata.excludedNonIndependentRowCount, 1);
assert.equal(yearly.metadata.excludedNoNeighborRowCount, 1);
assert.equal(yearly.metadata.excludedMissingClusterRowCount, 1);
assert.match(yearly.metadata.dateBasis, /animal context marker date, not neighboring UFO date/);
assert.match(yearly.metadata.membershipUnit, /location\/date cluster per neighboring craft\/period/);
assert.equal(JSON.stringify(neighbors), before, "Timeline preparation must not mutate neighbor inputs");
for (const group of [yearly, decadal]) for (const value of group.cells) {
  assert.equal(value.referenceCount, null);
  assert.equal(value.inferenceEligible, false); assert.equal(value.patternFinderEligible, false);
  assert.equal(value.evidenceStatus, "descriptive_only");
  for (const key of ["p", "pValue", "p_value", "q", "qValue", "q_value"]) assert.equal(value[key], null);
}

// Date ranges/conflicting cluster dates are assigned only if the entire known
// span belongs to one period. Missing or corrupt dates never become 1970 or year 1.
const uncertain = compute([
  base("missing", "2000-01-01", "triangle", { contextOrdinal: null }),
  base("fractional", "2000-01-01", "triangle", { contextOrdinal: ordinal("2000-01-01") + .5 }),
  base("beyond-calendar", "2000-01-01", "triangle", { contextOrdinal: 3652060 }),
  base("unknown-precision", "2000-01-01", "triangle", { contextDatePrecision: "unknown" }),
  base("reversed", "2000-01-02", "triangle", { contextEndOrdinal: ordinal("2000-01-01") }),
  base("within-decade", "2001-01-01", "triangle", { contextEndOrdinal: ordinal("2002-12-31"), contextDatePrecision: "range" }),
  base("cross-decade", "2009-12-31", "triangle", { contextEndOrdinal: ordinal("2010-01-01"), contextDatePrecision: "range" }),
  base("collision", "2001-01-01", "disc_saucer"),
  base("collision", "2011-01-01", "disc_saucer"),
  base("year-only", "2012-01-01", "unknown", { contextDatePrecision: "year" }),
]).temporal.craft;
assert.deepEqual(uncertain.yearly.columns, ["2012"]);
assert.equal(uncertain.yearly.metadata.activeUnknownDateCount, 5);
assert.equal(uncertain.yearly.metadata.activeAmbiguousPeriodCount, 3);
assert.equal(uncertain.yearly.metadata.activeUnknownLabelCount, 1);
assert.deepEqual(uncertain.decadal.columns, ["2000", "2010"]);
assert.equal(uncertain.decadal.metadata.activeAmbiguousPeriodCount, 2);
assert.equal(cell(uncertain.decadal, "triangle", 2000).observedCount, 1);
assert.equal(cell(uncertain.yearly, "unknown", 2012).observedCount, 1);

// Full observed domain stays available without rounding dates from the UFO's
// side of a year boundary. Date.parse uses the real statistics-day epoch.
const extremes = compute([
  base("first-day", "0001-01-01", "triangle"),
  base("last-day", "9999-12-31", "triangle"),
  base("context-boundary", "1999-12-31", "disc_saucer", { dayLag: 2 }),
]).temporal.craft;
assert.deepEqual(extremes.yearly.columns, ["1", "1999", "9999"]);
assert.equal(cell(extremes.yearly, "disc_saucer", 1999).observedCount, 1);
assert.ok(!extremes.yearly.columns.includes("2000"));

// Packed artifacts have no date-precision extension: the existing builder
// contract admits exact-day animal public markers before neighbor projection.
const codebook = { contextDomain: ["animal"], contextLane: ["animal_public_marker"],
  distanceRing: ["0_25_km"], dayLagBand: ["same_day"], uncertaintyClass: ["public_marker_ambiguous"],
  ufoCraft: ["triangle"], ufoSource: ["source"], ufoFineSpatialStratum: ["fine"],
  ufoCoarseSpatialStratum: ["coarse"], featureGroup: ["bovine"], dateRole: ["observed_reported_date"],
  contextSourceFamilyGroup: ["source_family"], contextCoarseSpatialStratum: ["coarse"] };
const packed = [0, 0, "animal-packed", "cluster-packed", ordinal("2000-01-01"), "active-1", 100, 0, 0, 0, 0, null, 0, 0, 0, 0, 0, false, false, true, 0, 0, 0];
assert.equal(compute([packed], { codebook }).temporal.craft.yearly.cells[0].observedCount, 1);
assert.deepEqual(compute([]).temporal.craft.yearly.cells, []);
console.log("Animal nearby craft timelines retain independent observed clusters, temporal uncertainty and descriptive-only evidence.");

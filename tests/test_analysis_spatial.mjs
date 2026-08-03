import assert from "node:assert/strict";
import test from "node:test";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const spatial = require("../webapp/static_public/analysis_spatial.js");

function eligibleRow(overrides = {}) {
  return {
    eventId: "event-1",
    mapped: true,
    lat: 35,
    lon: -117,
    analysisCoordinateClass: "source_coordinates",
    datePrecision: "exact_day",
    craftType: "triangle",
    craftConfidence: "high",
    sameDayMatchStrength: "strong",
    duplicateLineage: "",
    source: "source-a",
    analysisYear: 2001,
    sortOrdinal: 730486,
    analysisFiveYearBand: 2000,
    analysisDecade: 2000,
    analysisFineSpatialStratum: "ea12x24:8:4",
    analysisCoarseSpatialStratum: "ea6x12:4:2",
    analysisCoordinatePileCount: 1,
    ...overrides,
  };
}

function inferentialFacility(overrides = {}) {
  return {
    id: "facility-1",
    facilityClass: "military",
    lat: 0,
    lon: 0,
    coordinateConfidence: "high",
    temporalConfidence: "high",
    activeIntervals: [[1900, 2100]],
    inferentialEligible: true,
    ...overrides,
  };
}

function facilityAnalysisRow(overrides = {}) {
  return eligibleRow({
    lat: 0,
    lon: 0.1,
    analysisYear: 2000,
    sortOrdinal: 730486,
    analysisFiveYearBand: 2000,
    analysisDecade: 2000,
    analysisFineSpatialStratum: "ea12x24:6:12",
    analysisCoarseSpatialStratum: "ea6x12:3:6",
    ...overrides,
  });
}

test("great-circle distance is dateline safe", () => {
  const distance = spatial.greatCircleDistanceMeters(0, 179.9, 0, -179.9);
  assert.ok(distance > 20_000 && distance < 23_000, String(distance));
});

test("FDR excludes non-estimable null p-values from the tested family", () => {
  const items = [{ pValue: null, qValue: null }, { pValue: 0.04, qValue: null }];
  spatial.benjaminiHochberg(items);
  assert.equal(items[0].qValue, null);
  assert.equal(items[1].qValue, 0.04);
});

test("uncertain distances are classified conservatively", () => {
  assert.equal(spatial.classifyUncertainDistance(10_000, 1_000, 1_000, 25_000).status, "near");
  assert.equal(spatial.classifyUncertainDistance(40_000, 2_000, 2_000, 25_000).status, "far");
  assert.equal(spatial.classifyUncertainDistance(25_000, 2_000, 2_000, 25_000).status, "ambiguous");
});

test("generalized coordinates, duplicate lineages, and weak dates fail closed", () => {
  assert.equal(spatial.spatialEligibilityReason(eligibleRow()), "eligible");
  assert.equal(spatial.spatialEligibilityReason(eligibleRow({ analysisCoordinateClass: "generalized_coordinates" })), "generalized_coordinates");
  assert.equal(spatial.spatialEligibilityReason(eligibleRow({ duplicateLineage: "duplicate:1" })), "duplicate_lineage");
  assert.equal(spatial.spatialEligibilityReason(eligibleRow({ datePrecision: "year" })), "non_exact_date");
  assert.equal(spatial.spatialEligibilityReason(eligibleRow({ analysisCoordinatePileCount: 10 })), "coordinate_pile");
});

test("packed neighbor distances are decoded from decameters", () => {
  const edge = spatial.normalizeEdge(["1", "2", 2500, 7, true]);
  assert.equal(edge.distanceMeters, 25_000);
  assert.equal(edge.dayGap, 7);
  assert.equal(edge.crossSource, true);
  assert.equal(edge.contractValid, true);
  assert.equal(spatial.normalizeEdge(["a", "b", 10001, 7, true]).contractValid, false);
  assert.equal(spatial.normalizeEdge([Number.MAX_SAFE_INTEGER + 1, 2, 10, 1, true]).contractValid, false);
});

test("packed facility rows decode through the pinned manifest codebook", () => {
  const codes = {
    class: ["claimed_ufo_base", "military", "research_test"],
    coordinatePrecision: ["exact_site"],
    coordinateConfidence: ["high"],
    temporalConfidence: ["high"],
    status: ["active"],
    country: ["US"],
    provenance: ["fixture.geojson"],
  };
  const packed = ["f-1", 1, "Fixture", 1, 2, 0, 0, null, 0, [[1950, null]], 0, 0, 0, true, []];
  const facility = spatial.normalizeFacility(packed, codes);
  assert.equal(facility.facilityClass, "military");
  assert.equal(facility.coordinateConfidence, "high");
  assert.equal(spatial.facilityIsInferential(packed, codes), true);
  assert.equal(spatial.facilityActiveAt(packed, 730486, 2000, codes), "active");
});

test("facility activity supports year intervals and uncertain boundaries", () => {
  const facility = { activeIntervals: [[1950, 2000]] };
  assert.equal(spatial.facilityActiveAt(facility, 730486, 1980), "active");
  assert.equal(spatial.facilityActiveAt(facility, 730486, 2010), "inactive");
  const uncertain = { activeIntervals: [{ startYear: 1950, endYear: 2000, boundaryUncertaintyYears: 2 }] };
  assert.equal(spatial.facilityActiveAt(uncertain, 730486, 1949), "unknown");
});

test("claimed facilities are never inferential", () => {
  assert.equal(spatial.facilityIsInferential({
    facilityClass: "claimed_ufo_base",
    coordinateConfidence: "high",
    temporalConfidence: "high",
    inferentialEligible: true,
    lat: 1,
    lon: 2,
  }), false);
});

test("facility composition uses a source-era-geography adjusted common odds ratio", () => {
  const rows = [];
  let eventId = 0;
  function append(source, longitude, craft, count) {
    for (let index = 0; index < count; index += 1) {
      eventId += 1;
      const region = source === "source-a" ? "region-a" : "region-b";
      rows.push(facilityAnalysisRow({
        eventId: String(eventId),
        source,
        lon: longitude,
        craftType: craft,
        analysisFineSpatialStratum: region,
        analysisCoarseSpatialStratum: region,
      }));
    }
  }
  // Within both source strata the craft odds ratio is exactly 1.0, while the
  // unadjusted pooled odds ratio is about 0.22 (a Simpson's-paradox fixture).
  append("source-a", 0.1, "triangle", 45);
  append("source-a", 0.1, "disc_saucer", 5);
  append("source-a", 1.5, "triangle", 81);
  append("source-a", 1.5, "disc_saucer", 9);
  append("source-b", 0.1, "triangle", 5);
  append("source-b", 0.1, "disc_saucer", 45);
  append("source-b", 1.5, "triangle", 1);
  append("source-b", 1.5, "disc_saucer", 9);
  const result = spatial.computeFacilityContext({
    rows,
    facilities: [inferentialFacility()],
    permutationCount: 19,
    bootstrapCount: 9,
    seed: "facility-cmh-fixture",
  });
  const triangle = result.cells.find((cell) => cell.key === "triangle");
  const rawOddsRatio = (50 * 18) / (50 * 82);
  assert.ok(rawOddsRatio < 0.3);
  assert.ok(Math.abs(triangle.commonOddsRatio - 1) < 1e-9, JSON.stringify(triangle));
  assert.deepEqual(triangle.covariates, ["source", "decade", "coarse_equal_area_geography"]);
  assert.equal(result.commonSupportRate, 1);
  assert.equal(result.primary.permutationCount, 19);
  assert.equal(result.primary.bootstrapCount, 9);
  assert.equal(triangle.sourceSensitivity.evaluatedHoldoutN, 2);
  assert.equal(triangle.regionSensitivity.evaluatedHoldoutN, 2);
  const repeated = spatial.computeFacilityContext({
    rows,
    facilities: [inferentialFacility()],
    permutationCount: 19,
    bootstrapCount: 9,
    seed: "facility-cmh-fixture",
  });
  assert.deepEqual(result, repeated);
});

test("facility candidate indexing prefilters the 70-record inferential pool", () => {
  const facilities = [inferentialFacility()];
  for (let index = 1; index < 70; index += 1) {
    facilities.push(inferentialFacility({
      id: `facility-${index + 1}`,
      lat: 60,
      lon: -175 + ((index * 17) % 350),
    }));
  }
  const rows = [];
  for (let index = 0; index < 200; index += 1) {
    rows.push(facilityAnalysisRow({
      eventId: String(index + 1),
      lon: index < 100 ? 0.1 : 1.5,
      craftType: index % 2 ? "triangle" : "disc_saucer",
    }));
  }
  const result = spatial.computeFacilityContext({
    rows,
    facilities,
    permutationCount: 0,
    bootstrapCount: 0,
  });
  assert.equal(result.inferentialFacilityN, 70);
  assert.equal(result.prefilter.naiveDistanceEvaluationN, 14_000);
  assert.ok(result.prefilter.distanceEvaluationN < result.prefilter.naiveDistanceEvaluationN / 5, JSON.stringify(result.prefilter));
  assert.equal(result.prefilter.packedFacilitySchema[13], "inferentialEligible");
});

test("inactive-at-event facilities are reported as a separate negative control", () => {
  const rows = [];
  for (let index = 0; index < 60; index += 1) {
    rows.push(facilityAnalysisRow({
      eventId: String(index + 1),
      lon: index < 30 ? 0.1 : 1.5,
      craftType: index % 2 ? "triangle" : "disc_saucer",
    }));
  }
  const result = spatial.computeFacilityContext({
    rows,
    facilities: [inferentialFacility({ activeIntervals: [[1900, 1950]] })],
    permutationCount: 9,
    bootstrapCount: 5,
  });
  assert.equal(result.nearTotal, 0);
  assert.equal(result.inactiveFacilityNegativeControlN, 30);
  assert.equal(result.inactiveNegativeControl.nearTotal, 30);
  assert.equal(result.inactiveNegativeControl.covariates.includes("source"), true);
});

test("facility index keeps dateline and high-latitude candidates", () => {
  const rows = [];
  for (let index = 0; index < 50; index += 1) {
    rows.push(facilityAnalysisRow({
      eventId: String(index + 1),
      lat: 85,
      lon: index < 25 ? 179.9 : 160,
      craftType: index % 2 ? "triangle" : "disc_saucer",
      analysisFineSpatialStratum: "polar-fixture",
      analysisCoarseSpatialStratum: "polar-fixture",
    }));
  }
  const result = spatial.computeFacilityContext({
    rows,
    facilities: [inferentialFacility({ lat: 85, lon: -179.9 })],
    permutationCount: 0,
    bootstrapCount: 0,
  });
  assert.equal(result.nearTotal, 25);
  assert.equal(result.comparisonTotal, 25);
});

test("point co-occurrence is deterministic and chronology inputs are irrelevant", () => {
  const rows = [];
  for (let index = 0; index < 40; index += 1) {
    rows.push(eligibleRow({
      eventId: String(index + 1),
      source: index % 2 ? "source-b" : "source-a",
      craftType: index % 3 ? "triangle" : "disc_saucer",
      lat: 35 + (index / 1000),
      analysisCoordinatePileCount: 1,
    }));
  }
  const edges = [];
  for (let index = 0; index < rows.length - 1; index += 1) {
    edges.push([rows[index].eventId, rows[index + 1].eventId, 100, 1, true]);
  }
  const options = {
    rows,
    edges,
    window: spatial.DEFAULT_WINDOWS[0],
    sourceLane: "cross",
    minimumStratumSize: 2,
    permutationCount: 19,
    bootstrapCount: 9,
    seed: "deterministic-fixture",
  };
  const first = spatial.computeCraftCooccurrence({ ...options, chronologySegments: [[1, 2]], traceMode: "all" });
  const second = spatial.computeCraftCooccurrence({ ...options, chronologySegments: [[40, 1]], traceMode: "off" });
  assert.deepEqual(first, second);
  assert.equal(first.qualifyingPairCount, 39);
  assert.match(first.policyWarnings.join(" "), /Chronology connectors are not read/);
});

test("spatial result publishes separate cross-source and same-source lanes", () => {
  const rows = [
    eligibleRow({ eventId: "1", source: "a", craftType: "triangle" }),
    eligibleRow({ eventId: "2", source: "b", craftType: "disc_saucer" }),
    eligibleRow({ eventId: "3", source: "a", craftType: "disc_saucer" }),
  ];
  const result = spatial.computeSpatialAnalysis({
    rows,
    edges: [["1", "2", 100, 1, true], ["1", "3", 100, 1, false]],
    windows: [spatial.DEFAULT_WINDOWS[0]],
    minimumStratumSize: 2,
    permutationCount: 3,
    bootstrapCount: 3,
    facilities: [],
  });
  assert.equal(result.traceInputsRead, false);
  assert.equal(result.cooccurrence.crossSource.length, 1);
  assert.equal(result.cooccurrence.sameSource.length, 1);
});

test("full catalog spatial output is overlap-descriptive and emits no inferential fields", () => {
  const rows = [];
  const edges = [];
  for (let index = 0; index < 60; index += 1) {
    rows.push(eligibleRow({
      eventId: String(index + 1),
      source: index % 2 ? "source-b" : "source-a",
      craftType: index % 3 ? "triangle" : "disc_saucer",
      analysisFineSpatialStratum: "full-catalog-fixture",
      analysisCoarseSpatialStratum: "full-catalog-fixture",
    }));
    if (index > 0) edges.push([String(index), String(index + 1), 100, 1, true]);
  }
  const result = spatial.computeSpatialAnalysis({
    rows,
    edges,
    facilities: [],
    windows: [spatial.DEFAULT_WINDOWS[0]],
    minimumStratumSize: 2,
    permutationCount: 19,
    bootstrapCount: 9,
    baselineMode: "full_catalog",
    inferenceEnabled: false,
  });
  assert.equal(result.baselineMode, "full_catalog");
  assert.equal(result.inferenceEnabled, false);
  assert.equal(result.cooccurrence.crossSource[0].status, "descriptive_only");
  assert.match(result.policyWarnings.join(" "), /p-values, q-values, and Pattern Finder eligibility are disabled/i);
  (function assertDescriptive(value) {
    if (Array.isArray(value)) return value.forEach(assertDescriptive);
    if (!value || typeof value !== "object") return;
    if (Object.prototype.hasOwnProperty.call(value, "pValue")) assert.equal(value.pValue, null);
    if (Object.prototype.hasOwnProperty.call(value, "qValue")) assert.equal(value.qValue, null);
    if (Object.prototype.hasOwnProperty.call(value, "patternFinderEligible")) assert.equal(value.patternFinderEligible, false);
    Object.values(value).forEach(assertDescriptive);
  })(result);
});

test("co-occurrence audits packed edges and publishes source and region holdouts", () => {
  const rows = [];
  for (let index = 0; index < 120; index += 1) {
    rows.push(eligibleRow({
      eventId: String(index + 1),
      source: index < 60 ? "source-a" : "source-b",
      craftType: index % 2 ? "triangle" : "disc_saucer",
      analysisFineSpatialStratum: index % 60 < 30 ? "fine-r1" : "fine-r2",
      analysisCoarseSpatialStratum: index % 60 < 30 ? "region-1" : "region-2",
    }));
  }
  const edges = [];
  for (let index = 0; index < 60; index += 1) {
    edges.push([String(index + 1), String(index + 61), 100, 1, true]);
  }
  edges.push(["61", "1", 100, 1, true]);
  edges.push(["1", "62", 10001, 1, true]);
  const result = spatial.computeCraftCooccurrence({
    rows,
    edges,
    sourceLane: "cross",
    minimumStratumSize: 2,
    permutationCount: 19,
    bootstrapCount: 9,
    seed: "holdout-fixture",
  });
  assert.equal(result.qualifyingPairCount, 60);
  assert.equal(result.edgeAudit.duplicateEdgeCount, 1);
  assert.equal(result.edgeAudit.invalidEdgeCount, 1);
  assert.equal(result.edgeAudit.packedDistanceUnit, "decameters");
  assert.equal(result.sourceStability.evaluatedHoldouts.length, 2);
  assert.equal(result.regionStability.evaluatedHoldouts.length, 2);
  assert.ok(result.cells.every((cell) => "sourceSensitivity" in cell && "regionSensitivity" in cell));
});

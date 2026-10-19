import assert from "node:assert/strict";
import { createRequire } from "node:module";
import fs from "node:fs";
import vm from "node:vm";
const require = createRequire(import.meta.url), Engine = require("../analysis_session_context.js"), Spatial = require("../analysis_spatial.js");
const Session = require("../analysis_session.js");
const clone = value => JSON.parse(JSON.stringify(value));
const cohort = (ids, start, end, extra = {}) => ({ eventIds: ids, reportCount: ids.length, scope: { timeRange: { mode: "window", startOrdinal: start, endOrdinal: end } }, ...extra });
const A = cohort(["1", "2", "3"], 0, 9), B = cohort(["2", "4"], 10, 19);
const groups = { A: { cohort: A, rows: [{ eventId: "1", datePrecision: "exact_day", coordinateSource: "raw_latlong", craftConfidence: "high" }, { eventId: "2", datePrecision: "year" }] },
  B: { cohort: B, rows: [{ eventId: "2", datePrecision: "year" }, { eventId: "4", datePrecision: "unknown" }] } };
const field = (result, key) => { const value = result.dimensions.find(item => item.key === key); assert.ok(value, key); return value; };
const counts = side => Object.fromEntries(side.rows.map(row => [row.key, row.count]));
const context = { crops: [
  { id: "crop1", startOrdinal: 0, endOrdinal: 0, country: "France", lat: 0, lon: 0, morphology: ["disc", "ring"], reviewState: "unreviewed", strictEligible: false, dateRole: "catalog_date", datePrecision: "exact_day", sourceFamilyIds: ["family1"] },
  { id: "shared", startOrdinal: 8, endOrdinal: 11, country: "France", lat: 0, lon: 0, morphology: ["ring"], datePrecision: "range", strictEligible: true },
  { id: "crop2", startOrdinal: 15, endOrdinal: 15, country: "Belgium", lat: 1, lon: 1, morphology: ["disc"], datePrecision: "exact_day" },
  { id: "undated", startOrdinal: null, endOrdinal: null, country: "France", morphology: ["ring"] },
], animals: [{ id: "animal1", startOrdinal: 1, endOrdinal: 1, species: ["bovine"], dateRole: "publication_date", strictEligible: false, coordinateEvidenceClass: "unmapped" },
  { id: "animal2", startOrdinal: 12, endOrdinal: 12, species: ["equine", "bovine"], dateRole: "occurrence_date", strictEligible: true }] };
let result = Engine.compute({ section: "crops", groups, context });
assert.equal(result.status, "ready");
assert.equal(field(result, "crops_morphology").a.totalN, 2, "Independent context denominator is context records, not UFO group count");
assert.deepEqual(counts(field(result, "crops_morphology").a), { disc: 1, ring: 2 });
assert.equal(field(result, "crops_morphology").multiLabel, true);
assert.equal(field(result, "crops_country").b.totalN, 2);
assert.equal(field(result, "crops_country").a.excludedUnknownScopeN, 1);
assert.match(field(result, "crops_dateRole").notes.join(" "), /Publication\/catalog dates retain/);
assert.equal(field(result, "crops_dateRole").a.unknownN, 1, "Unknown date roles do not become formation dates");
result = Engine.compute({ section: "animals", groups, context });
assert.deepEqual(counts(field(result, "animals_species").b), { bovine: 1, equine: 1 });
assert.equal(field(result, "animals_species").b.eligibleN, 1);
assert.deepEqual(counts(field(result, "animals_dateRole").a), { publication_date: 1 });

const scoped = clone(A); scoped.provenance = { capturedSnapshot: { areaFilter: { active: true, shapes: [{ type: "country", country: "Belgium" }] } } };
assert.equal(Engine.scopedContext(context.crops, scoped).rows.length, 0);
const areaOnly = { eventIds: ["1"], scope: { timeRange: { mode: "full" }, areaFilter: { active: true, shapes: [{ type: "rectangle", bounds: { south: -1, north: 0.5, west: -1, east: 0.5 } }] } } };
assert.deepEqual(Engine.scopedContext(context.crops, areaOnly).rows.map(row => row.id), ["crop1", "shared"]);
assert.equal(Engine.scopedContext(context.crops, areaOnly).excludedUnknownScopeN, 1);
const circle = clone(areaOnly); circle.scope.areaFilter.shapes = [{ type: "circle", center: { lat: 0, lng: 0 }, radiusMeters: 1000 }];
assert.equal(Engine.scopedContext(context.crops, circle).rows.length, 2);
const pythonRows = context.crops.map(row => ({ ...row, startOrdinal: row.startOrdinal == null ? null : row.startOrdinal + 719163, endOrdinal: row.endOrdinal == null ? null : row.endOrdinal + 719163 }));
assert.equal(Engine.scopedContext(pythonRows, A, { contextOrdinalEpoch: "statistics_day" }).rows.length, 2);
assert.equal(Engine.scopedContext(context.crops, { eventIds: ["1"], scope: { timeRange: { mode: "full" } } }).status, "unavailable", "An arbitrary ID cohort never invents a whole context catalog join");
const allTime = { eventIds: ["1"], scope: { timeRange: { mode: "full" } }, provenance: { sessionCaptureScope: "current_filters" } };
assert.equal(Engine.scopedContext(context.crops, allTime).rows.length, context.crops.length, "Explicit toolbar All Time captures define the whole independent context catalog, including undated records");
assert.match(Engine.scopedContext(context.crops, allTime).notes.join(" "), /Whole context catalogs can be identical/);
assert.equal(Engine.scopedContext(context.crops, { ...allTime, provenance: { capturedSnapshot: { timeRange: { mode: "full" } } } }).rows.length, context.crops.length);
assert.equal(Engine.scopedContext(context.crops, { ...allTime, scope: { allRecords: true } }).status, "unavailable", "A full collection study cannot inherit unrelated map context dates");
assert.equal(Engine.scopedContext(context.crops, { ...allTime, provenance: { ...allTime.provenance, selectionScope: "all_search_matches" } }).status, "unavailable");
assert.equal(Engine.scopedContext(context.crops, { ...allTime, provenance: { capturedSnapshot: { timeRange: { mode: "full" }, selection: { key: "arbitrary-ids" } } } }).status, "unavailable");
assert.equal(Engine.scopedContext(null, A).status, "unavailable");
const noScope = { A: { cohort: { eventIds: ["1"] }, rows: [] }, B: { cohort: B, rows: [] } };
result = Engine.compute({ section: "crops", groups: noScope, context });
assert.equal(field(result, "crops_country").a.available, false); assert.equal(field(result, "crops_country").a.totalN, null);
assert.equal(field(result, "crops_country").b.available, true);

const point = (id, lat, lon) => ({ eventId: id, lat, lon, ordinal: 719163, year: 1970, craft: "disc_saucer", coordinateEvidence: "source_coordinates" });
context.spatialPoints = [point("1", 0, 0), point("2", 0, 0.1), point("4", 10, 10)];
context.facilities = [
  { id: "active", facilityClass: "military", lat: 0, lon: 0.05, coordinateConfidence: "high", temporalConfidence: "high", inferentialEligible: true, activeIntervals: [{ startYear: 1960, endYear: 1980 }] },
  { id: "inactive", facilityClass: "military", lat: 10, lon: 10, coordinateConfidence: "high", temporalConfidence: "high", inferentialEligible: true, activeIntervals: [{ startYear: 1900, endYear: 1950 }] },
  { id: "unsupported", facilityClass: "military", lat: 10, lon: 10, inferentialEligible: false, activeIntervals: [{ startYear: 1960, endYear: 1980 }] },
];
result = Engine.compute({ section: "facilities", groups, context, settings: { spatialRadiusKm: 100 } });
assert.equal(field(result, "facility_distance").a.eligibleN, 2); assert.equal(field(result, "facility_distance").a.unknownN, 1);
assert.deepEqual(counts(field(result, "facility_radius").b), { beyond_radius: 1, within_radius: 1 }, "Inactive and unqualified sites cannot create near-facility counts");
assert.equal(field(result, "facility_distance").a.totalN, 3);
assert.equal(Engine.compute({ section: "facilities", groups, context: {} }).status, "unavailable");
const boundaryRadius = Spatial.greatCircleDistanceMeters(0, 0, 0, 0.05) / 1000;
context.facilities[0].uncertaintyKm = 1;
assert.ok(counts(field(Engine.compute({ section: "facilities", groups, context, settings: { spatialRadiusKm: boundaryRadius } }), "facility_radius").a).boundary_uncertain > 0);
context.facilities[0].uncertaintyKm = 0;
assert.ok(counts(field(Engine.compute({ section: "facilities", groups, context, settings: { spatialRadiusKm: boundaryRadius } }), "facility_radius").a).within_radius > 0);

context.neighbors = [["1", "2", 1000, 0, true], ["2", "1", 1000, 0, true], ["2", "4", 5000, 2, false], ["1", "4", 8000, 1, false], ["1", "3", -1, 0, false]];
result = Engine.compute({ section: "spatial", groups, context, settings: { spatialRadiusKm: 100 } });
assert.equal(field(result, "spatial_pair_distance").a.totalN, 1, "Undirected duplicate pairs count once and require two captured qualified endpoints");
assert.equal(field(result, "spatial_pair_distance").b.totalN, 1);
assert.equal(field(result, "spatial_neighbor_coverage").a.unknownN, 1);
assert.deepEqual(counts(field(result, "spatial_eligibility").a), { pinned_qualified: 2, outside_pinned_pool: 1 });
assert.match(field(Engine.compute({ section: "spatial", groups, context, settings: { spatialRadiusKm: 500 } }), "spatial_pair_distance").notes.join(" "), /explicitly uses 100 km/);

context.codebooks = { relationshipReconciliation: { relationshipType: ["reported_nearby"], reviewState: ["needs_human_review"], reconciliationStatus: ["reconciled_current"] } };
context.relationships = [["r1", "animal1", 0, "ufo1", 0, 0, 0, "1", 0, false, 1], ["unjoined", "animal1", 0, "old", 0, 0, 0, null, 0, false, 1]];
context.contextNeighbors = [
  { ufoEventId: "1", contextId: "crop1", lane: "crop_locality", dateRole: "observed_catalog_date" },
  { ufoEventId: "1", contextId: "crop1", lane: "crop_locality", dateRole: "matched_control_plus_1y" },
  { ufoEventId: "2", contextId: "crop1", lane: "crop_locality", dateRole: "observed_catalog_date", originUfoExcluded: true },
];
result = Engine.compute({ section: "context", groups, context });
assert.equal(field(result, "relationship_type").a.totalN, 1); assert.equal(field(result, "relationship_type").b.totalN, 0, "Unjoined evidence is never copied to both groups");
assert.equal(field(result, "relationship_coverage").a.unknownN, 2);
assert.deepEqual(counts(field(result, "report_date_precision").a), { exact_day: 1, year: 1 });
assert.equal(field(result, "context_neighbor_lane").a.totalN, 1, "Control rows and originating-source exclusions are not observed pairs");

const report = (id, extra = {}) => ({ eventId: id, canonicalJoinStatus: "validated_id_source_chunk_index", disposition: "direct_report", scope: "occupant_soil_plant", materials: ["soil"], actions: ["taking"], beingTypes: [], source: "fixture", sourceFamily: "family1", provisionalGroup: "provisional1", startOrdinal: 0, endOrdinal: 0, ...extra });
const collectionEvidence = { schemaId: "ufo-collection-evidence-v1", schemaVersion: 1,
  taxonomy: { materials: [{ key: "soil", label: "Soil" }], actions: [{ key: "taking", label: "Taking" }] },
  reports: [report("1"), report("2", { disposition: "ambiguous" }), report("3", { disposition: "adjacent", scope: "traces_only" }), report("4", { canonicalPrimaryDiffers: true }), report("9")],
  cases: [{ caseId: "unjoined", indexedReportIds: [] }], policy: {} };
result = Engine.compute({ section: "encounters", groups, collectionEvidence });
assert.equal(field(result, "collection_coverage").a.eligibleN, 1); assert.equal(field(result, "collection_coverage").a.unknownN, 2);
assert.equal(field(result, "collection_coverage").b.eligibleN, 0); assert.equal(field(result, "collection_coverage").b.heldMemberVariantN, 1);
assert.deepEqual(counts(field(result, "collection_source_family").a), { family1: 1 });
assert.equal(field(result, "collection_versions").b.eligibleN, 2);
result = Engine.compute({ section: "collections", groups, collectionEvidence, settings: { collectionEvidence: "all" } });
assert.equal(field(result, "collection_coverage").a.eligibleN, 3); assert.equal(field(result, "collection_coverage").b.eligibleN, 1);
assert.match(field(result, "collection_coverage").notes.join(" "), /uncertain\/adjacent/);
assert.equal(field(Engine.compute({ section: "collections", groups, collectionEvidence, settings: { collectionEvidence: "all", includeMemberVariants: true } }), "collection_coverage").b.eligibleN, 2);
assert.equal(Engine.compute({ section: "collections", groups }).status, "unavailable");
for (const section of ["crops", "animals", "facilities", "spatial", "context", "collections"]) {
  for (const dimension of Engine.compute({ section, groups, context, collectionEvidence }).dimensions) Session.compareExternalDimension(dimension);
}

const before = JSON.stringify({ groups, context, collectionEvidence });
Engine.compute({ section: "spatial", groups, context }); Engine.compute({ section: "collections", groups, collectionEvidence });
assert.equal(JSON.stringify({ groups, context, collectionEvidence }), before, "Computations cannot mutate held groups, source rows or evidence");
const browser = vm.createContext({}); vm.runInContext(fs.readFileSync("analysis_session_context.js", "utf8"), browser);
assert.equal(browser.UfoAnalysisSessionContext.scopedContext(context.crops, circle, { spatialApi: Spatial }).rows.length, 2, "Worker can inject Spatial after this module loads");
assert.equal(field(browser.UfoAnalysisSessionContext.compute({ section: "facilities", groups, context, spatialApi: Spatial }), "facility_distance").a.eligibleN, 2);
console.log("Context A/B comparisons: independent date/area scopes, missing evidence, collection versions/families, facility policy, unique qualified neighbors, relationship joins and immutable inputs passed.");

import assert from "node:assert/strict";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const map = require("../encounter_map.js");

const report = (id, changes = {}) => ({
  event_id: id, source: "fixture", has_coordinates: true, lat: 10, lon: 105,
  location_precision: "city", coordinate_source: "geocoded",
  encounterEvidenceReady: true, encounterIdentityMismatch: false,
  encounterAbductionCode: 0, encounterBeingMask: 1,
  encounterCraftAssociationCode: 0, ...changes,
});
const abduction = report(1, { encounterAbductionCode: 1, encounterBeingMask: 0 });
const both = report(2, { encounterAbductionCode: 2, encounterCraftAssociationCode: 1 });
const being = report(3, { encounterCraftAssociationCode: 2 });
const unclear = report(4, { encounterAbductionCode: 3, encounterBeingMask: 0 });
const unclearBeing = report(5, { encounterAbductionCode: 3, encounterCraftAssociationCode: 3 });
const noCraft = report("3125527168511206", {
  lat: 10.03, lon: 105.78, type: "Unknown", craft_type_inferred: "non_ufo_context",
  location_precision: "exact_coords", coordinate_source: "source_provided", encounterCraftAssociationCode: 3,
});
const unmapped = report(6, { has_coordinates: false, lat: null, lon: null });
const notIndexed = report(7, { encounterBeingMask: 0 });
const heldIdentity = report(8, { encounterIdentityMismatch: true });
const unavailable = report(9, { encounterEvidenceReady: false });
const original = JSON.stringify([abduction, both, being, unclear, unclearBeing, noCraft, unmapped, notIndexed, heldIdentity, unavailable]);

// Source classifications and guarded narratives remain reported categories;
// unspecified or absent being descriptions never remove an abduction report.
assert.equal(map.classify(abduction).kind, "abduction");
assert.equal(map.classify(both).kind, "both");
assert.equal(map.classify(unclear).kind, "ambiguous");
assert.equal(map.classify(unclear).reportedAbduction, false);
assert.equal(map.classify(unclearBeing).kind, "being");
assert.equal(map.classify(unclearBeing).ambiguousAbduction, true);
assert.equal(map.classify(heldIdentity).ready, false);
assert.equal(map.classify(unavailable).ready, false);
assert.equal(map.classify(report(10, { encounterBeingMask: -1 })).ready, false);
assert.equal(map.classify(report(10, { encounterAbductionCode: "1" })).ready, false);
assert.equal(map.classify(report(10)).sourceBeingMask, null);

// Being-only/no-craft reports are still mapped, without fabricated craft
// associations, inferred locations or an inherited craft-category restriction.
assert.deepEqual(map.pointForEvent(noCraft), {
  lat: 10.03, lon: 105.78, locationPrecision: "exact_coords", coordinateSource: "source_provided", locationDisplay: "",
});
assert.equal(map.describeRelationship(noCraft).key, "none_reported");
assert.equal(map.describeRelationship(noCraft).sameReport, false);
assert.equal(map.describeRelationship(being).coReportedOnly, true);
assert.equal(map.describeRelationship(being).sourceReportedAssociation, false);
assert.equal(map.describeRelationship(both).sourceReportedAssociation, true);
assert.equal(map.describeRelationship(both).canInferFlight, false);
for (const invalid of [null, "", " ", false, true, "not a coordinate", NaN, Infinity]) {
  assert.equal(map.pointForEvent(report(10, { lat: invalid })), null);
  assert.equal(map.pointForEvent(report(10, { lon: invalid })), null);
}
assert.equal(map.pointForEvent(report(10, { lat: 91 })), null);
assert.equal(map.pointForEvent(report(10, { lon: 181 })), null);
assert.equal(map.pointForEvent(report(10, { coordinate_source: "unresolved" })), null);
assert.equal(map.pointForEvent(report(10, { has_coordinates: false })), null);

const events = [abduction, both, being, unclear, unclearBeing, noCraft, unmapped, notIndexed, heldIdentity, unavailable];
const model = map.buildModel(events);
assert.equal(model.cohort.reports, 6);
assert.equal(model.cohort.mapped, 5);
assert.equal(model.cohort.unmapped, 1);
assert.equal(model.cohort.reportedAbductions, 2);
assert.equal(model.cohort.reportedBeings, 5);
assert.equal(model.cohort.ambiguousAbductionMentions, 1);
assert.equal(model.cohort.sourceClassifiedAbductions, 1);
assert.equal(model.cohort.narrativeAbductions, 1);
assert.deepEqual(model.cohort.kinds, { abduction: 1, both: 1, being: 4, ambiguous: 0 });
assert.deepEqual(model.cohort.craftAssociations, { not_established: 2, explicit: 1, co_reported: 1, none_reported: 2 });
assert.deepEqual(model.unmappedEventIds, ["6"]);
assert.equal(model.exclusions.evidenceUnavailable, 2);
assert.equal(model.exclusions.hiddenUnclearMentions, 1);
assert.equal(model.exclusions.notIndexed, 1);
assert.equal(model.rendering.displayedReports, 5);
assert.equal(model.reports.length, model.cohort.reports);
assert.equal(model.reports.find((entry) => entry.eventId === "6").point, null);
assert.equal(JSON.stringify(events), original);

// A display cluster retains source reports individually. Coincident different
// report IDs do not become an incident; repeated same IDs count only once.
assert.equal(map.buildModel([being, being, noCraft]).cohort.reports, 2);
assert.equal(map.buildModel([being, being, noCraft]).exclusions.duplicateEventIds, 1);
const coincident = map.buildModel([report(11), report(12, { source: "other_collection" })]);
assert.equal(coincident.markers.length, 1);
assert.equal(coincident.markers[0].reportCount, 2);
assert.deepEqual(coincident.markers[0].eventIds, ["11", "12"]);
assert.equal(coincident.markers[0].anchorPolicy, "existing_report_coordinate");
assert.deepEqual(coincident.markers[0].counts.sourceCollections, { fixture: 1, other_collection: 1 });
assert.equal(map.buildModel(events, { population: "abduction" }).cohort.reports, 2);
assert.equal(map.buildModel(events, { population: "being" }).cohort.reports, 5);
assert.equal(map.buildModel(events, { population: "both" }).cohort.reports, 1);
assert.equal(map.buildModel(events, { population: "all", includeAmbiguous: true }).cohort.reports, 7);
assert.equal(map.buildModel(events, { population: "ambiguous" }).cohort.reports, 2);
const unavailableModel = map.buildModel(events, { evidenceReady: false });
assert.equal(unavailableModel.status, "unavailable");
assert.equal(unavailableModel.countsAvailable, false);
assert.equal(unavailableModel.reports.length, 0);
assert.equal(unavailableModel.markers.length, 0);
const unusualSource = map.buildModel([report(20, { source: "__proto__", location_precision: "constructor" })]);
assert.equal(Object.getPrototypeOf(unusualSource.cohort.sourceCollections), Object.prototype);
assert.equal(unusualSource.cohort.sourceCollections["__proto__"], 1);
assert.equal(unusualSource.cohort.locationPrecisions.constructor, 1);

// Wrapping viewports include either longitude representation of the dateline,
// while unmapped reports remain in cohort coverage and never enter map bins.
assert.equal(map.inViewport({ lat: 10, lon: 179 }, { north: 20, south: 0, west: 170, east: 190 }), true);
assert.equal(map.inViewport({ lat: 10, lon: -179 }, { north: 20, south: 0, west: 170, east: -170 }), true);
assert.equal(map.inViewport({ lat: 10, lon: 0 }, { north: 20, south: 0, west: 170, east: -170 }), false);
assert.equal(map.inViewport({ lat: 10, lon: -180 }, { north: 20, south: 0, west: 180, east: 200 }), true);
assert.equal(map.inViewport({ lat: 10, lon: 180 }, { north: 20, south: 0, west: -180, east: -160 }), true);
assert.equal(map.inViewport({ lat: 10, lon: -90 }, { north: 20, south: 0, west: -540, east: 540 }), true);
const smallViewport = map.buildModel(events, { viewport: { north: 5, south: -5, west: -180, east: 180 } });
assert.equal(smallViewport.cohort.reports, 6);
assert.equal(smallViewport.viewport.reports, 0);
assert.equal(smallViewport.exclusions.outsideViewport, 5);

// Bounded rendering is aggregation, not point sampling. Every viewport report
// remains in a cluster; representatives are exact source report coordinates.
const crowded = Array.from({ length: 6000 }, (_, index) => report(10000 + index, {
  lat: -80 + (index % 80) * 2, lon: -179 + (Math.floor(index / 80) % 180) * 2,
  encounterAbductionCode: index % 3 === 0 ? 1 : 0,
}));
const bounded = map.buildModel(crowded, { zoom: 11, maxMarkers: 40 });
assert.ok(bounded.markers.length <= 40);
assert.equal(bounded.rendering.displayedReports, 6000);
assert.equal(new Set(bounded.markers.flatMap((entry) => entry.eventIds)).size, 6000);
const crowdedById = new Map(crowded.map((entry) => [String(entry.event_id), entry]));
for (const marker of bounded.markers) {
  const anchor = crowdedById.get(marker.eventId);
  assert.equal(marker.lat, anchor.lat);
  assert.equal(marker.lon, anchor.lon);
}
assert.deepEqual(map.buildModel(crowded.slice().reverse(), { zoom: 11, maxMarkers: 40 }), bounded);
assert.ok(map.buildModel(crowded, { maxMarkers: 1 }).markers.length <= 1);
const brokenProjection = map.buildModel([being, noCraft], { project: () => { throw new Error("projection offline"); } });
assert.equal(brokenProjection.cohort.reports, 2);
assert.equal(brokenProjection.viewport.reports, 2);
assert.equal(brokenProjection.markers.length, 0);
assert.equal(brokenProjection.exclusions.projectionUnavailable, 2);

// Shared report membership does not create a new relationship line. A nearby
// same-day report with a different ID never joins; chronology remains untouched.
const segments = [
  { fromEventId: "2", toEventId: 3, sameDayOrderKnown: false, from: [10, 105], to: [11, 106] },
  { fromEventId: 3, toEventId: noCraft.event_id, sameDayOrderKnown: true },
  { fromEventId: "999", toEventId: 1000, from: [10.03, 105.78], to: [10.03, 105.78] },
  { fromEventId: "4", toEventId: "8" },
  { fromEventId: 2, toEventId: 2000 },
];
const segmentOriginal = JSON.stringify(segments);
const relationships = map.traceEndpointSummary(segments, events);
assert.equal(relationships.inspectedLinks, 5);
assert.equal(relationships.linksWithEncounterEndpoint, 3);
assert.equal(relationships.linksWithBothEncounterEndpoints, 2);
assert.equal(relationships.encounterEndpointReportCount, 3);
assert.deepEqual(relationships.associations, { explicit: 1, co_reported: 1, not_established: 0, none_reported: 1 });
assert.equal(relationships.links[0].relationshipBasis, "same_catalog_report_id");
assert.equal(relationships.links[0].canInferFlight, false);
assert.equal(relationships.links[0].canInferSameCraft, false);
assert.equal(JSON.stringify(segments), segmentOriginal);
assert.equal(JSON.stringify(events), original);

for (const kind of ["abduction", "being", "both", "ambiguous", "mixed"]) {
  const svg = map.markerSvg(kind, { count: 24 });
  assert.match(svg, /<svg/);
  assert.match(svg, /24 reports in this display group/);
  assert.doesNotMatch(svg, /#38bdf8|#22c55e|#f97316|confirmed|flight|alien/);
}
assert.match(map.markerSvg("being", { ambiguousAbduction: true }), /includes an unclear abduction mention/);
assert.match(map.markerSvg("ambiguous"), /stroke-dasharray/);
assert.match(map.markerSvg("<script>"), /Unclear abduction mention/);
assert.doesNotMatch(map.markerSvg("<script>"), /<script>/);
console.log("Encounter map evidence, canonical coordinates, bounded rendering, report identity and relationship guards passed.");

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
let projectionCalls = 0;
const countsOnly = map.buildModel(events, { renderMarkers: false, project() { projectionCalls += 1; throw new Error("must stay off"); } });
assert.equal(projectionCalls, 0, "An off layer must not build map geometry just to retain accurate coverage");
assert.deepEqual(countsOnly.cohort, model.cohort);
assert.deepEqual(countsOnly.viewport, model.viewport);
assert.deepEqual(countsOnly.reports, model.reports);
assert.equal(countsOnly.markers.length, 0);
assert.equal(countsOnly.rendering.markerRenderingEnabled, false);

// Heat rendering aggregates report weights, rather than sampling records or
// manufacturing an average encounter location. Coverage stays independently
// inspectable when a report has no canonical mapped point.
const density = map.buildDensity(crowded, { zoom: 11, maxPoints: 75 });
assert.ok(density.points.length <= 75);
assert.equal(density.points.reduce((sum, point) => sum + point.weight, 0), 6000);
assert.equal(density.rendering.displayedReports, 6000);
assert.equal(new Set(density.points.flatMap((point) => point.eventIds)).size, 6000);
assert.equal(density.rendering.centroidUsed, false);
for (const point of density.points) {
  const anchor = crowdedById.get(point.eventId);
  assert.equal(point.lat, anchor.lat);
  assert.equal(point.lon, anchor.lon);
  assert.equal(point.weight, point.reportCount);
  assert.equal(point.anchorPolicy, "existing_report_coordinate");
}
assert.deepEqual(map.buildDensity(crowded.slice().reverse(), { zoom: 11, maxPoints: 75 }), density);
assert.ok(map.buildDensity(crowded, { zoom: 16, maxPoints: 5000 }).points.length <= 1200);
assert.equal(map.buildDensity(events).cohort.unmapped, 1);
assert.equal(map.buildDensity([being, being, noCraft]).cohort.reports, 2);
assert.equal(map.buildDensity(events, { evidenceReady: false }).points.length, 0);

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
  assert.match(svg, new RegExp('stroke="' + map.KIND_COLORS[kind] + '"'));
  assert.match(svg, /fill="#18232b"/);
}
assert.equal(new Set(map.KINDS.map((entry) => entry.outlineColor)).size, 4, "Categories retain distinct colored outlines and shape cues");
assert.match(map.markerSvg("mixed", { kinds: ["being", "abduction"] }), /fill="#55d4c7"/);
assert.match(map.markerSvg("mixed", { kinds: ["being", "abduction"] }), /fill="#f4b860"/);
assert.match(map.markerSvg("being", { ambiguousAbduction: true }), /includes an unclear abduction mention/);
assert.match(map.markerSvg("ambiguous"), /stroke-dasharray/);
assert.match(map.markerSvg("<script>"), /Unclear abduction mention/);
assert.doesNotMatch(map.markerSvg("<script>"), /<script>/);

const dated = (id, changes = {}) => report(id, {
  lat: 10, lon: 105 + id / 1000, sort_date_iso: "1994-09-16", date_precision: "exact_day",
  encounterOccurrenceDateExcluded: false, ...changes,
});
const datedEvents = [dated(41), dated(42), dated(43)];
const connections = map.buildConnections(datedEvents);
assert.equal(connections.counts.eligibleReports, 3);
assert.equal(connections.counts.adjacentPairs, 2, "Report adjacency must not expand to every possible pair");
assert.equal(connections.segments.length, 2);
assert.deepEqual(connections.segments.map((edge) => edge.eventIds), [["41", "42"], ["42", "43"]]);
for (const edge of connections.segments) {
  assert.equal(edge.sameDayOrderKnown, false, "Identifiers cannot resolve report direction");
  assert.equal(edge.adjacencyBasis, "stable_display_order");
  assert.equal(edge.relationshipBasis, "same_day_same_reported_encounter_category");
  assert.equal(edge.canInferFlight, false);
  assert.equal(edge.canInferSameCraft, false);
  assert.equal(edge.canInferSameBeing, false);
  assert.equal(edge.fromLocationPrecision, "city");
  assert.equal(edge.toLocationPrecision, "city");
  assert.equal(edge.gapDays, 0);
  assert.ok(edge.distanceKm > 0);
}
assert.deepEqual(map.buildConnections(datedEvents.slice().reverse()), connections);
assert.equal(connections.settings.viewportScope, "selected_report_scope");
assert.equal(connections.settings.maxDistanceKm, 250);

// Multiple matching being labels add evidence to one pair, not parallel lines.
// Abduction-only reports form a separate category and require no being label.
const multiLabels = map.buildConnections([dated(51, { encounterBeingMask: 3 }), dated(52, { encounterBeingMask: 3 })]);
assert.equal(multiLabels.segments.length, 1);
assert.deepEqual(multiLabels.segments[0].categoryKeys, ["being:0", "being:1"]);
const unspecifiedMask = 1 << 18;
const unspecifiedConnections = map.buildConnections([
  dated(53, { encounterBeingMask: unspecifiedMask }), dated(54, { encounterBeingMask: unspecifiedMask }),
]);
assert.equal(unspecifiedConnections.segments.length, 0, "Two unspecified descriptions do not identify a shared reported being category");
assert.equal(unspecifiedConnections.omissions.untypedBeingReports, 2);
assert.equal(unspecifiedConnections.counts.eligibleReports, 0);
assert.equal(map.buildConnections([
  dated(53, { encounterBeingMask: unspecifiedMask, encounterAbductionCode: 1 }),
  dated(54, { encounterBeingMask: unspecifiedMask, encounterAbductionCode: 2 }),
]).segments.length, 0, "Being metadata must not be collapsed into the abduction-only connection category");
const greyAndUnspecified = map.buildConnections([
  dated(53, { encounterBeingMask: 1 | unspecifiedMask }), dated(54, { encounterBeingMask: 1 | unspecifiedMask }),
]);
assert.equal(greyAndUnspecified.segments.length, 1);
assert.deepEqual(greyAndUnspecified.segments[0].categoryKeys, ["being:0"]);
assert.equal(map.buildConnections([dated(51), dated(52, { encounterBeingMask: 2 })]).segments.length, 0);
const abductionConnections = map.buildConnections([
  dated(61, { encounterAbductionCode: 1, encounterBeingMask: 0 }),
  dated(62, { encounterAbductionCode: 2, encounterBeingMask: 0 }),
  dated(63, { encounterBeingMask: 1 }),
]);
assert.equal(abductionConnections.segments.length, 1);
assert.deepEqual(abductionConnections.segments[0].categoryKeys, ["abduction_only"]);
assert.equal(map.buildConnections([dated(71), dated(72, { encounterAbductionCode: 2 })], { population: "abduction" }).segments.length, 0);
assert.equal(map.buildConnections([dated(71), dated(72, { encounterAbductionCode: 2 })], { population: "both" }).segments.length, 0);
const noCraftDated = { ...noCraft, sort_date_iso: "1994-09-16", date_precision: "exact_day", encounterOccurrenceDateExcluded: false };
assert.equal(map.buildConnections([dated(71), noCraftDated]).segments.length, 1, "No-craft encounters remain valid reports");

// Calendar comparisons fail closed for unknown, approximate, invalid and held
// dates; ambiguous abduction mentions do not become reported abductions.
const exclusionFixtures = [
  dated(81), dated(82, { date_precision: "month" }), dated(83, { sort_date_iso: "2021-02-29" }),
  dated(84, { encounterOccurrenceDateExcluded: true }), dated(85, { encounterOccurrenceDateExcluded: null }),
  dated(86, { sort_date_iso: null }), dated(87, { has_coordinates: false }),
  dated(88, { encounterAbductionCode: 3, encounterBeingMask: 0 }), dated(89, { encounterIdentityMismatch: true }),
];
const exclusionOriginal = JSON.stringify(exclusionFixtures);
const excludedConnections = map.buildConnections(exclusionFixtures, { includeAmbiguous: true });
assert.equal(excludedConnections.segments.length, 0);
assert.equal(excludedConnections.counts.eligibleReports, 1);
assert.equal(excludedConnections.omissions.nonExactDates, 3);
assert.equal(excludedConnections.omissions.heldDates, 1);
assert.equal(excludedConnections.omissions.dateExclusionsUnavailable, 1);
assert.equal(excludedConnections.omissions.unmapped, 1);
assert.equal(excludedConnections.omissions.ambiguousOnly, 1);
assert.equal(excludedConnections.omissions.evidenceUnavailable, 1);
assert.equal(JSON.stringify(exclusionFixtures), exclusionOriginal);
assert.equal(map.buildConnections([dated(91), dated(92, { sort_date_iso: "1994-09-17" })]).segments.length, 0);
assert.equal(map.buildConnections([dated(91), dated(92, { lat: 70 })]).omissions.beyondDistance, 1);
assert.equal(map.buildConnections([dated(91), dated(92, { lon: dated(91).lon })]).omissions.zeroLengthPairs, 1);
for (const field of ["duplicate_lineage_id", "reviewed_duplicate_cluster_id"]) {
  const sameDuplicate = map.buildConnections([dated(91, { [field]: "reviewed-pair" }), dated(92, { [field]: "reviewed-pair" })]);
  assert.equal(sameDuplicate.segments.length, 0);
  assert.equal(sameDuplicate.omissions.reviewedDuplicatePairs, 1);
  assert.equal(map.buildConnections([dated(91, { [field]: "" }), dated(92, { [field]: "" })]).segments.length, 1);
}
assert.equal(map.buildConnections([dated(91), dated(91), dated(92)]).omissions.duplicateEventIds, 1);

// At least one real report endpoint must be in view. A line merely crossing the
// viewport is not counted as a visible encounter; canonical points are kept.
const narrowViewport = { north: 11, south: 9, west: 105.0905, east: 105.0915 };
const visibleConnections = map.buildConnections([dated(91), dated(92)], { viewport: narrowViewport });
assert.equal(visibleConnections.segments.length, 1);
assert.equal(visibleConnections.settings.viewportScope, "at_least_one_endpoint_visible");
const outsideConnections = map.buildConnections([dated(92), dated(93)], { viewport: narrowViewport });
assert.equal(outsideConnections.segments.length, 0);
assert.equal(outsideConnections.omissions.outsideViewport, 1);
assert.equal(map.buildConnections([dated(101, { lon: 179.9 }), dated(102, { lon: -179.9 })]).segments.length, 1, "Distance wraps the dateline");

// Accepted clocks can improve display adjacency. Even this evidence does not
// orient an edge here: only the native timing resolver can prove direction.
const clocked = map.buildConnections([dated(111), dated(112), dated(113)], {
  getUtcInterval(event) { const startMs = (114 - event.event_id) * 1000; return { startMs, endMs: startMs + 50 }; },
});
assert.deepEqual(clocked.segments.map((edge) => edge.eventIds), [["112", "111"], ["113", "112"]]);
assert.ok(clocked.segments.every((edge) => edge.sourceIntervalsAvailable && edge.adjacencyBasis === "source_interval_display_order" && !edge.sameDayOrderKnown));
assert.equal(map.buildConnections([dated(111), dated(112)], { getUtcInterval() { throw new Error("clock unavailable"); } }).segments[0].adjacencyBasis, "stable_display_order");

const connectionCrowd = Array.from({ length: 3000 }, (_, index) => dated(20000 + index));
const cappedConnections = map.buildConnections(connectionCrowd, { maxSegments: 800 });
assert.equal(cappedConnections.segments.length, 600);
assert.equal(cappedConnections.counts.totalEligible, 2999);
assert.equal(cappedConnections.omissions.segmentCap, 2399);
assert.deepEqual(map.buildConnections(connectionCrowd.slice().reverse(), { maxSegments: 800 }), cappedConnections);
assert.equal(map.buildConnections(connectionCrowd, { evidenceReady: false }).segments.length, 0);
console.log("Encounter map evidence, off-layer geometry, density weights, bounded same-day connections and relationship guards passed.");

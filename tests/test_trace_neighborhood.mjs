import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const neighborhood = require("../webapp/static_public/trace_neighborhood.js");

function segment(from, to, sequenceIndex, extra = {}) {
  return {
    traceId: `${from}->${to}`,
    fromEventId: from,
    toEventId: to,
    eventIds: [from, to],
    from: [sequenceIndex, sequenceIndex * 10],
    to: [sequenceIndex + 1, (sequenceIndex + 1) * 10],
    sequenceIndex,
    bucket: { key: extra.bucket || "gap_le_1" },
    ...extra,
  };
}

const chain = [
  segment("A", "B", 0),
  segment("B", "C", 1),
  segment("C", "D", 2),
  segment("D", "E", 3),
  segment("E", "F", 4),
];
const index = neighborhood.buildAdjacencyIndex(chain, 17);

for (let depth = 1; depth <= 4; depth += 1) {
  const forward = neighborhood.traverseNeighborhood({
    index,
    depth,
    direction: "forward",
    eventSeeds: [{ eventId: "B", regionIds: ["r1"] }],
  });
  assert.deepEqual(
    forward.segments.map((row) => row.traceId),
    chain.slice(1, 1 + depth).map((row) => row.traceId),
    `forward depth ${depth}`,
  );

  const backward = neighborhood.traverseNeighborhood({
    index,
    depth,
    direction: "backward",
    eventSeeds: [{ eventId: "E", regionIds: ["r1"] }],
  });
  assert.deepEqual(
    backward.segments.map((row) => row.traceId),
    chain.slice(Math.max(0, 4 - depth), 4).reverse().map((row) => row.traceId),
    `backward depth ${depth}`,
  );
}

const both = neighborhood.traverseNeighborhood({
  index,
  depth: 2,
  direction: "both",
  eventSeeds: [{ eventId: "C", regionIds: ["r1"] }],
});
assert.deepEqual(both.segments.map((row) => row.traceId), ["B->C", "C->D", "A->B", "D->E"]);
assert.equal(both.segments.find((row) => row.traceId === "B->C").neighborhood.direction, "backward");
assert.equal(both.segments.find((row) => row.traceId === "C->D").neighborhood.direction, "forward");

const bothExpectedByDepth = [
  ["B->C", "C->D"],
  ["B->C", "C->D", "A->B", "D->E"],
  ["B->C", "C->D", "A->B", "D->E", "E->F"],
  ["B->C", "C->D", "A->B", "D->E", "E->F"],
];
for (let depth = 1; depth <= 4; depth += 1) {
  const result = neighborhood.traverseNeighborhood({
    index,
    depth,
    direction: "both",
    eventSeeds: [{ eventId: "C", regionIds: ["crop-radius"] }],
  });
  assert.deepEqual(
    result.segments.map((row) => row.traceId),
    bothExpectedByDepth[depth - 1],
    `bidirectional depth ${depth}`,
  );
}

const traceForward = neighborhood.traverseNeighborhood({
  index,
  depth: 3,
  direction: "forward",
  traceSeeds: [{ traceId: "B->C", regionIds: ["r2"] }],
});
assert.deepEqual(traceForward.segments.map((row) => row.traceId), ["B->C", "C->D", "D->E"]);
assert.deepEqual(traceForward.segments.map((row) => row.neighborhood.hop), [1, 2, 3]);

const traceBoth = neighborhood.traverseNeighborhood({
  index,
  depth: 2,
  direction: "both",
  traceSeeds: [{ traceId: "C->D", regionIds: ["r3"] }],
});
assert.deepEqual(traceBoth.segments.map((row) => row.traceId), ["C->D", "B->C", "D->E"]);
assert.equal(traceBoth.segments[0].neighborhood.direction, "both");

const overlap = neighborhood.traverseNeighborhood({
  index,
  depth: 2,
  direction: "forward",
  eventSeeds: [
    { eventId: "B", regionIds: ["r1"] },
    { eventId: "B", regionIds: ["r2"] },
  ],
  traceSeeds: [{ traceId: "B->C", regionIds: ["r3"] }],
});
assert.deepEqual(overlap.segments.map((row) => row.traceId), ["B->C", "C->D"]);
assert.deepEqual(overlap.segments[0].neighborhood.regionIds, ["r1", "r2", "r3"]);
assert.equal(overlap.segments[0].neighborhood.attributions.length, 3);
assert.equal(overlap.eventIds.has("D"), true, "outside-area endpoint is retained");

const overlappingTraceSeeds = neighborhood.traverseNeighborhood({
  index,
  depth: 4,
  direction: "forward",
  traceSeeds: [
    { traceId: "A->B", regionIds: ["crop-radius"] },
    { traceId: "C->D", regionIds: ["crop-radius"] },
  ],
});
assert.deepEqual(
  overlappingTraceSeeds.segments.map((row) => row.traceId),
  ["A->B", "C->D", "B->C", "D->E", "E->F"],
  "overlapping trace seeds are deduplicated and ordered by their nearest hop",
);
assert.deepEqual(
  overlappingTraceSeeds.segments.find((row) => row.traceId === "C->D").neighborhood.hops,
  [1, 3],
  "a segment reached from multiple seeds retains every hop attribution",
);
assert.deepEqual(
  overlappingTraceSeeds.segments.find((row) => row.traceId === "D->E").neighborhood.hops,
  [2, 4],
  "overlapping expansions preserve both paths without duplicate rendered segments",
);

const duplicateTraceSeed = neighborhood.traverseNeighborhood({
  index,
  depth: 2,
  direction: "both",
  traceSeeds: [
    { traceId: "B->C", regionIds: ["crop-radius"] },
    { traceId: "B->C", regionIds: ["crop-radius"] },
  ],
});
assert.deepEqual(
  duplicateTraceSeed.segments.map((row) => row.traceId),
  ["B->C", "A->B", "C->D"],
  "repeated identical seeds do not duplicate segments",
);
assert.equal(
  duplicateTraceSeed.segments[0].neighborhood.attributions.length,
  2,
  "the seed segment has one attribution per traversal direction, not per duplicate seed",
);

assert.equal(neighborhood.normalizeDepth(0), 1, "hop depth clamps to one");
assert.equal(neighborhood.normalizeDepth(999), 4, "hop depth clamps to four");
assert.equal(neighborhood.normalizeDirection("BACKWARD"), "backward");
assert.equal(neighborhood.normalizeDirection("sideways"), "forward");

const duplicateIndex = neighborhood.buildAdjacencyIndex([...chain, chain[1]], 18);
assert.equal(duplicateIndex.segments.length, chain.length, "duplicate trace IDs are suppressed");

const disconnectedIndex = neighborhood.buildAdjacencyIndex([chain[0], chain[3], chain[4]], 19);
const disconnected = neighborhood.traverseNeighborhood({
  index: disconnectedIndex,
  depth: 4,
  direction: "forward",
  eventSeeds: [{ eventId: "A", regionIds: ["r1"] }],
});
assert.deepEqual(disconnected.segments.map((row) => row.traceId), ["A->B"]);

const empty = neighborhood.traverseNeighborhood({
  index,
  depth: 4,
  direction: "both",
  eventSeeds: [{ eventId: "missing", regionIds: ["r1"] }],
  traceSeeds: [{ traceId: "missing->trace", regionIds: ["r1"] }],
});
assert.equal(empty.segments.length, 0);
assert.equal(empty.events.length, 0);

const matchingCraft = neighborhood.resolveCraftEndpointStyle(
  { craft_type_inferred: "triangle" },
  { craft_type_inferred: "triangle" },
);
assert.equal(matchingCraft.continuous, true);
assert.equal(matchingCraft.fromColor, matchingCraft.toColor);

const mixedCraft = neighborhood.resolveCraftEndpointStyle(
  { craft_type_inferred: "triangle" },
  { craft_type_inferred: "disc_saucer" },
);
assert.equal(mixedCraft.continuous, false);
assert.equal(mixedCraft.fromColor, neighborhood.CRAFT_TYPE_COLORS.triangle);
assert.equal(mixedCraft.toColor, neighborhood.CRAFT_TYPE_COLORS.disc_saucer);

assert.equal(
  neighborhood.CRAFT_TYPE_COLORS.light,
  "#b517ff",
  "Light uses the balanced high-contrast electric violet",
);
const lightToCraft = neighborhood.resolveCraftEndpointStyle(
  { craft_type_inferred: "light" },
  { craft_type_inferred: "disc_saucer" },
);
assert.equal(lightToCraft.continuous, false);
assert.equal(lightToCraft.fromColor, "#b517ff");
assert.equal(lightToCraft.toColor, neighborhood.CRAFT_TYPE_COLORS.disc_saucer);
assert.notEqual(
  lightToCraft.fromColor,
  lightToCraft.toColor,
  "mixed Light-to-craft trace halves remain visually distinct",
);

const unknownCraft = neighborhood.resolveCraftEndpointStyle({}, {});
assert.equal(unknownCraft.fromColor, "#7e8f88");
assert.equal(unknownCraft.toColor, "#7e8f88");

const nearestPoint = neighborhood.nearestPointHit(
  { x: 100, y: 100 },
  [
    { eventId: "far", x: 108, y: 100, radius: 2 },
    { eventId: "near", x: 103, y: 104, radius: 2 },
  ],
  8,
);
assert.equal(nearestPoint.candidate.eventId, "near", "nearest visible point wins an overlapping trace click");
assert.equal(
  neighborhood.nearestPointHit(
    { x: 100, y: 100 },
    [{ eventId: "outside", x: 120, y: 100, radius: 2 }],
    8,
  ),
  null,
  "trace clicks outside the point hit radius remain available to the trace inspector",
);
assert.equal(
  neighborhood.nearestPointHit(
    { x: 100, y: 100 },
    [
      { eventId: "first", x: 105, y: 100, radius: 0 },
      { eventId: "second", x: 95, y: 100, radius: 0 },
    ],
    8,
  ).candidate.eventId,
  "first",
  "equal-distance point hits resolve deterministically by render order",
);

const spatial = neighborhood.buildSpatialIndex(
  [
    { event_id: "A", lat: 0, lon: 179 },
    { event_id: "B", lat: 1, lon: -179 },
    { event_id: "Z", lat: 70, lon: 70 },
  ],
  [segment("A", "B", 0, { from: [0, 179], to: [1, 181] })],
  { cellSizeDegrees: 10 },
);
const spatialCandidates = neighborhood.querySpatialIndex(spatial, [{
  south: -5,
  north: 5,
  west: -182,
  east: -175,
}]);
assert.equal(spatialCandidates.eventIds.has("A"), true, "wrapped point candidate A");
assert.equal(spatialCandidates.eventIds.has("B"), true, "wrapped point candidate B");
assert.equal(spatialCandidates.traceIds.has("A->B"), true, "dateline trace candidate");
assert.equal(spatialCandidates.eventIds.has("Z"), false);

const radiusKm = 50;
const equatorialClip = neighborhood.clipSegmentToCircle(
  { from: [0, -1], to: [0, 1] },
  [0, 0],
  radiusKm,
);
assert.ok(equatorialClip, "a trace crossing the selected radius is clipped");
assert.ok(Math.abs(equatorialClip.startFraction - 0.27517) < 0.0001);
assert.ok(Math.abs(equatorialClip.endFraction - 0.72483) < 0.0001);
assert.ok(Math.abs(equatorialClip.from[1] + 0.44966) < 0.0001);
assert.ok(Math.abs(equatorialClip.to[1] - 0.44966) < 0.0001);
assert.equal(equatorialClip.startInside, false);
assert.equal(equatorialClip.endInside, false);
assert.equal(equatorialClip.fullyContained, false);
assert.equal(equatorialClip.tangent, false);

const startsInsideClip = neighborhood.clipSegmentToCircle(
  { from: [0, 0], to: [0, 1] },
  [0, 0],
  radiusKm,
);
assert.equal(startsInsideClip.startFraction, 0);
assert.ok(Math.abs(startsInsideClip.endFraction - 0.44966) < 0.0001);
assert.equal(startsInsideClip.startInside, true);
assert.equal(startsInsideClip.endInside, false);

const containedClip = neighborhood.clipSegmentToCircle(
  { from: [0, -0.1], to: [0, 0.1] },
  [0, 0],
  radiusKm,
);
assert.deepEqual(
  [containedClip.startFraction, containedClip.endFraction],
  [0, 1],
  "a fully contained trace keeps its complete interval",
);
assert.equal(containedClip.fullyContained, true);

const radiusDegrees = (radiusKm / 6371.0088) * (180 / Math.PI);
const tangentClip = neighborhood.clipSegmentToCircle(
  { from: [radiusDegrees, -1], to: [radiusDegrees, 1] },
  [0, 0],
  radiusKm,
);
assert.ok(tangentClip, "a tangent is an exact geometric intersection");
assert.ok(Math.abs(tangentClip.startFraction - 0.5) < 0.000001);
assert.ok(Math.abs(tangentClip.endFraction - 0.5) < 0.000001);
assert.equal(tangentClip.tangent, true);

assert.equal(
  neighborhood.clipSegmentToCircle(
    { from: [1, -1], to: [1, 1] },
    [0, 0],
    radiusKm,
  ),
  null,
  "a trace outside the radius has no emphasized interval",
);
assert.equal(
  neighborhood.clipSegmentToCircle(
    { from: [0, 0], to: [0, 0] },
    [0, 0],
    radiusKm,
  ).fullyContained,
  true,
  "a zero-length trace inside the radius is retained deterministically",
);
assert.equal(
  neighborhood.clipSegmentToCircle(
    { from: [1, 1], to: [1, 1] },
    [0, 0],
    radiusKm,
  ),
  null,
  "a zero-length trace outside the radius is rejected",
);

const datelineClip = neighborhood.clipSegmentToCircle(
  { from: [0, 179], to: [0, -179] },
  [0, 180],
  radiusKm,
);
assert.ok(datelineClip, "the shortest dateline copy intersects the selected radius");
assert.ok(datelineClip.from[1] > -181 && datelineClip.from[1] < -180);
assert.ok(datelineClip.to[1] > -180 && datelineClip.to[1] < -179);

const highLatitudeDiagonal = neighborhood.clipSegmentToCircle(
  { from: [64, -20], to: [76, 20] },
  [70, 0],
  500,
);
assert.ok(highLatitudeDiagonal, "a high-latitude diagonal crossing is retained");
const highLatitudeEntryDistance = neighborhood.haversineKm(
  [70, 0],
  highLatitudeDiagonal.from,
);
const highLatitudeExitDistance = neighborhood.haversineKm(
  [70, 0],
  highLatitudeDiagonal.to,
);
assert.ok(
  highLatitudeEntryDistance <= 500 && highLatitudeEntryDistance >= 499.999999,
  `high-latitude entry lies on the true 500 km circle (${highLatitudeEntryDistance})`,
);
assert.ok(
  highLatitudeExitDistance <= 500 && highLatitudeExitDistance >= 499.999999,
  `high-latitude exit lies on the true 500 km circle (${highLatitudeExitDistance})`,
);
assert.ok(
  highLatitudeDiagonal.startFraction > 0.26 && highLatitudeDiagonal.startFraction < 0.27,
  "spherical clipping preserves a fraction along the rendered segment",
);
assert.ok(
  highLatitudeDiagonal.endFraction > 0.75 && highLatitudeDiagonal.endFraction < 0.77,
  "spherical clipping preserves the rendered exit fraction",
);
assert.ok(
  highLatitudeDiagonal.geometryMetrics.pathEvaluationCount <= 64,
  `high-latitude clipping stays within the analytic evaluation budget (${highLatitudeDiagonal.geometryMetrics.pathEvaluationCount})`,
);
assert.ok(
  highLatitudeDiagonal.geometryMetrics.exactDistanceEvaluationCount <= 4,
  "exact haversine verification is limited to the returned boundaries",
);

const circleSpatial = neighborhood.buildSpatialIndex(
  [
    { event_id: "inside", lat: 0, lon: 0.1 },
    { event_id: "box-corner", lat: 0.4, lon: 0.4 },
    { event_id: "far", lat: 2, lon: 2 },
  ],
  [
    segment("cross-a", "cross-b", 0, { from: [0, -1], to: [0, 1] }),
    segment("corner-a", "corner-b", 1, { from: [0.4, 0.4], to: [0.4, 0.45] }),
    segment("far-a", "far-b", 2, { from: [2, 1], to: [2, 2] }),
  ],
  { cellSizeDegrees: 2 },
);
const circleCandidates = neighborhood.queryCircleSpatialIndex(circleSpatial, [0, 0], radiusKm);
assert.equal(circleCandidates.candidateEventIds.has("inside"), true);
assert.equal(circleCandidates.candidateEventIds.has("box-corner"), true);
assert.equal(circleCandidates.eventIds.has("inside"), true);
assert.equal(
  circleCandidates.eventIds.has("box-corner"),
  false,
  "bounding-box point candidates are exact-filtered against the circle",
);
assert.equal(circleCandidates.traceIds.has("cross-a->cross-b"), true);
assert.equal(
  circleCandidates.traceIds.has("corner-a->corner-b"),
  false,
  "bounding-box trace candidates are exact-filtered against the circle",
);
assert.ok(
  circleCandidates.traceIntersections.get("cross-a->cross-b").endFraction >
    circleCandidates.traceIntersections.get("cross-a->cross-b").startFraction,
  "exact trace candidates include the clipped interval used for inside-only emphasis",
);
assert.ok(
  circleCandidates.metrics.maxPathEvaluationsPerTrace <= 64,
  `circle queries use a bounded analytic path, not per-trace dense sampling (${circleCandidates.metrics.maxPathEvaluationsPerTrace})`,
);
assert.ok(
  circleCandidates.metrics.maxTotalEvaluationsPerTrace <= 68,
  "per-trace exact geometry work remains bounded independently of wall-clock speed",
);

const circleNetwork = neighborhood.buildNeighborhoodIndex(
  [
    segment("seed-a", "seed-b", 0, { from: [0, -1], to: [0, 1] }),
    segment("seed-b", "hop-c", 1, { from: [0, 1], to: [0, 2] }),
    segment("hop-c", "hop-d", 2, { from: [0, 2], to: [0, 3] }),
    segment("hop-d", "hop-e", 3, { from: [0, 3], to: [0, 4] }),
  ],
  [
    { event_id: "seed-a", lat: 0, lon: -1 },
    { event_id: "seed-b", lat: 0, lon: 1 },
    { event_id: "hop-c", lat: 0, lon: 2 },
    { event_id: "hop-d", lat: 0, lon: 3 },
    { event_id: "hop-e", lat: 0, lon: 4 },
  ],
  21,
  { cellSizeDegrees: 2 },
);
const circleNetworkSeeds = neighborhood.queryCircleSpatialIndex(
  circleNetwork.spatial,
  [0, 0],
  radiusKm,
);
assert.deepEqual(
  Array.from(circleNetworkSeeds.traceIds),
  ["seed-a->seed-b"],
  "only a trace intersecting the radius becomes a direct seed",
);
const circleNetworkResult = neighborhood.traverseNeighborhood({
  index: circleNetwork,
  depth: 3,
  direction: "forward",
  traceSeeds: Array.from(circleNetworkSeeds.traceIds).map((traceId) => ({
    traceId,
    regionIds: ["selected-crop-radius"],
  })),
});
assert.deepEqual(
  circleNetworkResult.segments.map((row) => row.traceId),
  ["seed-a->seed-b", "seed-b->hop-c", "hop-c->hop-d"],
  "hop expansion follows the filtered trace network beyond the selected radius",
);
assert.deepEqual(
  Array.from(circleNetworkSeeds.traceIntersections.keys()),
  ["seed-a->seed-b"],
  "only the direct seed owns an inside-radius clip for bold rendering",
);

const datelineSpatial = neighborhood.buildSpatialIndex(
  [
    { event_id: "date-inside", lat: 0, lon: -179.9 },
    { event_id: "date-outside", lat: 0, lon: -170 },
  ],
  [segment("date-a", "date-b", 0, { from: [0, 179], to: [0, -179] })],
  { cellSizeDegrees: 2 },
);
const datelineCandidates = neighborhood.queryCircleSpatialIndex(
  datelineSpatial,
  [0, 180],
  radiusKm,
);
assert.equal(datelineCandidates.eventIds.has("date-inside"), true);
assert.equal(datelineCandidates.eventIds.has("date-outside"), false);
assert.equal(datelineCandidates.traceIds.has("date-a->date-b"), true);
assert.ok(
  datelineCandidates.bounds.west < -180 && datelineCandidates.bounds.east > -180,
  "circle bounds remain continuous across the dateline",
);

const highLatitudeCenter = [85, 100];
const highLatitudeCandidateRadiusKm = 490;
const highLatitudeAngularRadius = highLatitudeCandidateRadiusKm / 6371.0088;
const highLatitudeCenterRadians = highLatitudeCenter[0] * (Math.PI / 180);
const highLatitudeCandidateLat = Math.asin(
  Math.sin(highLatitudeCenterRadians) / Math.cos(highLatitudeAngularRadius),
) * (180 / Math.PI);
const highLatitudeCandidateLonDelta = Math.asin(
  Math.sin(highLatitudeAngularRadius) / Math.cos(highLatitudeCenterRadians),
) * (180 / Math.PI);
const highLatitudeCandidate = [
  highLatitudeCandidateLat,
  highLatitudeCenter[1] + highLatitudeCandidateLonDelta,
];
const obsoletePlanarLonRadius =
  ((500 / 6371.0088) * (180 / Math.PI)) /
  Math.cos(highLatitudeCenterRadians);
assert.ok(
  highLatitudeCandidateLonDelta > obsoletePlanarLonRadius + 10,
  "the regression candidate lies beyond the old under-sized longitude bound",
);
const highLatitudeSpatial = neighborhood.buildSpatialIndex(
  [{
    event_id: "high-latitude-event",
    lat: highLatitudeCandidate[0],
    lon: highLatitudeCandidate[1],
  }],
  [segment("high-a", "high-b", 0, {
    from: [highLatitudeCandidate[0] - 1, highLatitudeCandidate[1]],
    to: [highLatitudeCandidate[0] + 1, highLatitudeCandidate[1]],
  })],
  { cellSizeDegrees: 2 },
);
const highLatitudeCandidates = neighborhood.queryCircleSpatialIndex(
  highLatitudeSpatial,
  highLatitudeCenter,
  500,
);
assert.equal(
  highLatitudeCandidates.candidateEventIds.has("high-latitude-event"),
  true,
  "the exact spherical-cap bound never loses a high-latitude event candidate",
);
assert.equal(highLatitudeCandidates.eventIds.has("high-latitude-event"), true);
assert.equal(
  highLatitudeCandidates.candidateTraceIds.has("high-a->high-b"),
  true,
  "the exact spherical-cap bound never loses a high-latitude trace candidate",
);
assert.equal(highLatitudeCandidates.traceIds.has("high-a->high-b"), true);
const highLatitudeCandidateClip = highLatitudeCandidates.traceIntersections.get("high-a->high-b");
assert.ok(
  neighborhood.haversineKm(highLatitudeCenter, highLatitudeCandidateClip.from) <= 500,
  "high-latitude candidate entry remains inside the true circle",
);
assert.ok(
  neighborhood.haversineKm(highLatitudeCenter, highLatitudeCandidateClip.to) <= 500,
  "high-latitude candidate exit remains inside the true circle",
);

const polarBounds = neighborhood.circleBounds([89.9, 45], 50);
assert.equal(polarBounds.north, 90);
assert.equal(polarBounds.west, -135);
assert.equal(polarBounds.east, 225);
assert.equal(neighborhood.circleBounds([0, 0], 0), null);
assert.equal(neighborhood.pointInsideCircle([0, 0.1], [0, 0], radiusKm), true);
assert.equal(neighborhood.pointInsideCircle([0.4, 0.4], [0, 0], radiusKm), false);

assert.ok(Math.abs(neighborhood.haversineKm([0, 0], [0, 1]) - 111.195) < 0.1);
assert.deepEqual(neighborhood.midpoint([0, 179], [2, 181]), [1, 180]);

console.log("trace_neighborhood: all assertions passed");

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

assert.ok(Math.abs(neighborhood.haversineKm([0, 0], [0, 1]) - 111.195) < 0.1);
assert.deepEqual(neighborhood.midpoint([0, 179], [2, 181]), [1, 180]);

console.log("trace_neighborhood: all assertions passed");

import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const neighborhood = require("../webapp/static_public/trace_neighborhood.js");

function segment(from, to, sequenceIndex) {
  return {
    traceId: `${from}->${to}`,
    fromEventId: from,
    toEventId: to,
    eventIds: [from, to],
    from: [sequenceIndex, sequenceIndex],
    to: [sequenceIndex + 1, sequenceIndex + 1],
    sequenceIndex,
  };
}

assert.equal(neighborhood.normalizeAreaDepth(undefined), 0);
assert.equal(neighborhood.normalizeAreaDepth("not-a-depth"), 0);
assert.equal(neighborhood.normalizeAreaDepth(-10), 0);
assert.equal(neighborhood.normalizeAreaDepth(0), 0);
assert.equal(neighborhood.normalizeAreaDepth(1.4), 1);
assert.equal(neighborhood.normalizeAreaDepth(3.6), 4);
assert.equal(neighborhood.normalizeAreaDepth(999), 4);
assert.equal(neighborhood.normalizeDepth(0), 1, "shared crop-circle depth still clamps to one");

const chain = [
  segment("A", "B", 0),
  segment("B", "C", 1),
  segment("C", "D", 2),
  segment("D", "E", 3),
];
const index = neighborhood.buildAdjacencyIndex(chain, 42);

const eventOnlyPlan = neighborhood.planAreaZeroHopSelection({
  index,
  eventSeeds: [{ eventId: "B", regionIds: ["event-region"] }],
});
assert.deepEqual(Array.from(eventOnlyPlan.directEventIds), ["B"]);
assert.deepEqual(Array.from(eventOnlyPlan.incidentTraceIds), ["A->B", "B->C"]);
assert.deepEqual(eventOnlyPlan.segments.map((row) => row.traceId), ["A->B", "B->C"]);
assert.equal(eventOnlyPlan.segmentIds.has("C->D"), false, "zero hop never walks beyond immediate incident traces");
assert.equal(eventOnlyPlan.segmentIds.has("D->E"), false, "zero hop never performs a successor walk");
assert.equal(eventOnlyPlan.direction, "direct", "area direction is irrelevant at zero hops");

const combinedPlan = neighborhood.planAreaZeroHopSelection({
  index,
  eventSeeds: [{ eventId: "B", regionIds: ["event-region"] }],
  traceSeeds: [{ traceId: "C->D", regionIds: ["trace-region"] }],
});
assert.deepEqual(Array.from(combinedPlan.directTraceIds), ["C->D"]);
assert.deepEqual(Array.from(combinedPlan.directTraceEndpointIds), ["C", "D"]);
assert.deepEqual(Array.from(combinedPlan.incidentTraceEndpointIds), ["A", "B", "C"]);
assert.deepEqual(combinedPlan.segments.map((row) => row.traceId), ["A->B", "B->C", "C->D"]);
assert.deepEqual(
  combinedPlan.segments.find((row) => row.traceId === "C->D").neighborhood.roles,
  ["direct_trace"],
);
assert.deepEqual(
  combinedPlan.segments.find((row) => row.traceId === "A->B").neighborhood.regionIds,
  ["event-region"],
);
assert.deepEqual(
  combinedPlan.segments.find((row) => row.traceId === "C->D").neighborhood.regionIds,
  ["trace-region"],
);
assert.equal(combinedPlan.metrics.plannedSegments, 3);

const tracesOnly = neighborhood.computeAreaZeroHopSelection({
  plan: combinedPlan,
  selectEvents: false,
  selectTraces: true,
  showSelectedEvents: false,
  showSelectedTraces: true,
  showEventsAssociatedWithSelectedTraces: true,
  showTracesAssociatedWithSelectedEvents: false,
});
assert.deepEqual(Array.from(tracesOnly.selectedEventIds), []);
assert.deepEqual(Array.from(tracesOnly.selectedTraceIds), ["C->D"]);
assert.deepEqual(Array.from(tracesOnly.visibleEventIds), ["C", "D"]);
assert.deepEqual(Array.from(tracesOnly.visibleTraceIds), ["C->D"]);
assert.deepEqual(tracesOnly.visibleTraceSegments.map((row) => row.traceId), ["C->D"]);

const eventsOnly = neighborhood.computeAreaZeroHopSelection({
  plan: combinedPlan,
  selectEvents: true,
  selectTraces: false,
  showSelectedEvents: true,
  showSelectedTraces: false,
  showEventsAssociatedWithSelectedTraces: false,
  showTracesAssociatedWithSelectedEvents: true,
});
assert.deepEqual(Array.from(eventsOnly.selectedEventIds), ["B"]);
assert.deepEqual(Array.from(eventsOnly.selectedTraceIds), []);
assert.deepEqual(Array.from(eventsOnly.visibleEventIds), ["B"]);
assert.deepEqual(Array.from(eventsOnly.visibleTraceIds), ["A->B", "B->C"]);
assert.deepEqual(eventsOnly.visibleTraceSegments.map((row) => row.traceId), ["A->B", "B->C"]);
assert.equal(eventsOnly.visibleEventIds.has("A"), false, "incident trace endpoints do not leak as point markers");
assert.equal(eventsOnly.visibleEventIds.has("C"), false, "outside incident endpoints remain hidden");

const selectedButHidden = neighborhood.computeAreaZeroHopSelection({
  plan: combinedPlan,
  selectEvents: true,
  selectTraces: true,
  showSelectedEvents: false,
  showSelectedTraces: false,
  showEventsFromTraces: false,
  showTracesFromEvents: false,
});
assert.deepEqual(Array.from(selectedButHidden.selectedEventIds), ["B"]);
assert.deepEqual(Array.from(selectedButHidden.selectedTraceIds), ["C->D"]);
assert.equal(selectedButHidden.visibleEventIds.size, 0, "Show event controls remain independent");
assert.equal(selectedButHidden.visibleTraceIds.size, 0, "Show trace controls remain independent");

const overlappingPlan = neighborhood.planAreaZeroHopSelection({
  index,
  eventSeeds: [{ eventId: "C", regionIds: ["event-region"] }],
  traceSeeds: [{ traceId: "C->D", regionIds: ["trace-region"] }],
});
assert.deepEqual(overlappingPlan.segments.map((row) => row.traceId), ["B->C", "C->D"]);
assert.deepEqual(
  overlappingPlan.segments.find((row) => row.traceId === "C->D").neighborhood.roles,
  ["direct_trace", "incident_from_event"],
  "a direct trace that is also incident to an event seed is rendered once",
);
assert.deepEqual(
  overlappingPlan.segments.find((row) => row.traceId === "C->D").neighborhood.regionIds,
  ["event-region", "trace-region"],
);

for (const representation of ["points", "clusters", "heatmap"]) {
  assert.equal(
    neighborhood.resolveAreaEventRepresentation({ requestedMode: representation }),
    representation,
  );
  assert.equal(
    neighborhood.resolveAreaEventRepresentation({ requestedMode: "auto", effectiveMode: representation }),
    representation,
  );
}
assert.equal(neighborhood.resolveAreaEventRepresentation({ requestedMode: "events" }), "points");
assert.equal(neighborhood.resolveAreaEventRepresentation({ requestedMode: "auto" }), "hidden");
assert.equal(
  neighborhood.resolveAreaEventRepresentation({ requestedMode: "points", active: false }),
  "hidden",
);
assert.equal(
  neighborhood.resolveAreaEventRepresentation({ requestedMode: "clusters", showEvents: false }),
  "hidden",
);
assert.equal(neighborhood.resolveAreaEventRepresentation({ requestedMode: "off" }), "hidden");

const pointsToClusters = neighborhood.planAreaEventLayerTransition("points", "clusters");
assert.equal(pointsToClusters.previousRepresentation, "points");
assert.equal(pointsToClusters.nextRepresentation, "clusters");
assert.deepEqual(pointsToClusters.removeRepresentations, ["points", "heatmap"]);
assert.deepEqual(pointsToClusters.clearRepresentations, ["clusters"]);
assert.equal(pointsToClusters.renderRepresentation, "clusters");
assert.deepEqual(pointsToClusters.operations, [
  { type: "remove", representation: "points" },
  { type: "remove", representation: "heatmap" },
  { type: "clear", representation: "clusters" },
  { type: "render", representation: "clusters" },
]);

const autoTransition = neighborhood.planAreaEventLayerTransition({
  previousMode: "auto",
  previousEffectiveMode: "heatmap",
  nextMode: "auto",
  nextEffectiveMode: "clusters",
});
assert.equal(autoTransition.previousRepresentation, "heatmap");
assert.equal(autoTransition.nextRepresentation, "clusters");
assert.equal(autoTransition.changed, true);
assert.equal(autoTransition.removeRepresentations.includes("heatmap"), true);
assert.equal(autoTransition.renderRepresentation, "clusters");

const clustersToHeatmap = neighborhood.planAreaEventLayerTransition("clusters", "heatmap");
assert.deepEqual(clustersToHeatmap.removeRepresentations, ["points", "clusters"]);
assert.deepEqual(clustersToHeatmap.clearRepresentations, ["heatmap"]);
assert.equal(clustersToHeatmap.renderRepresentation, "heatmap");

const hiddenTransition = neighborhood.planAreaEventLayerTransition("heatmap", "hidden");
assert.deepEqual(hiddenTransition.removeRepresentations, ["points", "clusters", "heatmap"]);
assert.deepEqual(hiddenTransition.clearRepresentations, []);
assert.equal(hiddenTransition.renderRepresentation, null);
assert.equal(hiddenTransition.hidden, true);
assert.equal(hiddenTransition.operations.some((operation) => operation.type === "render"), false);

const hiddenToPoints = neighborhood.planAreaEventLayerTransition("hidden", "points");
assert.deepEqual(hiddenToPoints.removeRepresentations, ["clusters", "heatmap"]);
assert.deepEqual(hiddenToPoints.clearRepresentations, ["points"]);
assert.equal(hiddenToPoints.renderRepresentation, "points");

const refreshClusters = neighborhood.planAreaEventLayerTransition("clusters", "clusters");
assert.equal(refreshClusters.changed, false);
assert.deepEqual(refreshClusters.clearRepresentations, ["clusters"]);
assert.equal(refreshClusters.renderRepresentation, "clusters");
assert.equal(
  refreshClusters.removeRepresentations.includes("points") &&
    refreshClusters.removeRepresentations.includes("heatmap"),
  true,
  "same-mode area refresh still removes every non-owning representation",
);

console.log("area_selection_render: all assertions passed");

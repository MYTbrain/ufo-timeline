import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";

function loadWorker(workerPath) {
  const messages = [];
  const self = {
    postMessage(message) {
      messages.push(message);
    },
  };
  const context = {
    ArrayBuffer,
    DataView,
    Map,
    Number,
    Set,
    Math,
    Object,
    String,
    console,
    self,
  };
  vm.runInNewContext(fs.readFileSync(workerPath, "utf8"), context, {
    filename: workerPath,
  });
  assert.equal(typeof self.onmessage, "function");
  return {
    send(message) {
      messages.length = 0;
      self.onmessage({ data: message });
      assert.equal(messages.length, 1);
      return messages[0];
    },
    async sendAsync(message) {
      messages.length = 0;
      self.onmessage({ data: message });
      for (let attempt = 0; attempt < 20 && messages.length === 0; attempt += 1) {
        await new Promise((resolve) => setImmediate(resolve));
      }
      assert.equal(messages.length, 1);
      return messages[0];
    },
  };
}

function classify(worker, segments, classes, radiusMeters = 20000, options = {}) {
  const defaultEvidenceEventIds = segments.flatMap((segment) => [
    segment.fromEventId,
    segment.toEventId,
  ]).filter((eventId) => eventId != null);
  const request = {
    type: "classifyTraceFacilitySegments",
    requestId: "classify",
    scope: "test",
    facilityIndexKey: "fixture-facilities",
    filter: {
      radiusMeters,
      evidenceMode: options.evidenceMode || "source_coordinates",
      classes: Object.assign({
        start: false,
        end: false,
        between: false,
        passes: false,
      }, classes),
    },
    segments,
  };
  if (!options.omitEvidenceIds) {
    request.sourceCoordinateEventIds = Object.prototype.hasOwnProperty.call(options, "sourceCoordinateEventIds")
      ? options.sourceCoordinateEventIds
      : defaultEvidenceEventIds;
    request.exactDateEventIds = Object.prototype.hasOwnProperty.call(options, "exactDateEventIds")
      ? options.exactDateEventIds
      : defaultEvidenceEventIds;
  }
  const response = worker.send(request);
  assert.equal(response.type, "traceFacilitySegmentsClassified");
  return response.result;
}

function normalize(value) {
  return JSON.parse(JSON.stringify(value));
}

const worker = loadWorker("webapp/static_public/trace_facility_worker.js");

const configureResponse = worker.send({
  type: "configureTraceFacilityIndex",
  requestId: "configure",
  facilityIndexKey: "fixture-facilities",
  facilities: [
    { id: "start", facilityKey: "military:start", source: "fixture", lat: 0, lon: 0, temporalKnown: true, startOrdinal: 0, endOrdinal: 100 },
    { id: "end", facilityKey: "research:end", source: "fixture", lat: 0, lon: 1, temporalKnown: true, startOrdinal: 0, endOrdinal: 100 },
    { id: "passes", facilityKey: "claimed:passes", source: "claimedUfoBases", lat: 0, lon: 0.5, temporalKnown: true, startOrdinal: 0, endOrdinal: 100 },
    { id: "anti-west", facilityKey: "military:anti-west", source: "fixture", lat: 0, lon: 179.5, temporalKnown: true, startOrdinal: 0, endOrdinal: 100 },
    { id: "anti-east", facilityKey: "research:anti-east", source: "fixture", lat: 0, lon: -179.5, temporalKnown: true, startOrdinal: 0, endOrdinal: 100 },
    { id: "high-lat", facilityKey: "research:high-lat", source: "fixture", lat: 80, lon: 0, temporalKnown: true, startOrdinal: 0, endOrdinal: 100 },
    { id: "radius-growth", facilityKey: "research:radius-growth", source: "fixture", lat: 0.4, lon: 0.1, temporalKnown: true, startOrdinal: 0, endOrdinal: 100 },
  ],
});
assert.equal(configureResponse.type, "traceFacilityIndexConfigured");
assert.equal(configureResponse.result.facilityCount, 7);

const segments = [
  { traceId: "start", fromEventId: "start-from", toEventId: "start-to", fromSortOrdinal: 10, toSortOrdinal: 20, from: [0, 0.01], to: [1, 1] },
  { traceId: "end", fromEventId: "end-from", toEventId: "end-to", fromSortOrdinal: 10, toSortOrdinal: 20, from: [1, 1], to: [0, 1.01] },
  { traceId: "between", fromEventId: "between-from", toEventId: "between-to", fromSortOrdinal: 10, toSortOrdinal: 20, from: [0, 0.01], to: [0, 1.01] },
  { traceId: "passes", fromEventId: "passes-from", toEventId: "passes-to", fromSortOrdinal: 10, toSortOrdinal: 20, from: [0, -1], to: [0, 2] },
  { traceId: "none", fromEventId: "none-from", toEventId: "none-to", fromSortOrdinal: 10, toSortOrdinal: 20, from: [5, 5], to: [6, 6] },
  { traceId: "antimeridian", fromEventId: "anti-from", toEventId: "anti-to", fromSortOrdinal: 10, toSortOrdinal: 20, from: [0, 179.52], to: [0, -179.52] },
  { traceId: "high-lat-start", fromEventId: "high-from", toEventId: "high-to", fromSortOrdinal: 10, toSortOrdinal: 20, from: [80, 0.04], to: [81, 1] },
  { traceId: "oversized-pass-scan", fromEventId: "wide-from", toEventId: "wide-to", fromSortOrdinal: 10, toSortOrdinal: 20, from: [-89, -90], to: [89, 90] },
];

const allClasses = classify(worker, segments, {
  start: true,
  end: true,
  between: true,
  passes: true,
}, 20000, { evidenceMode: "include_generalized" });
assert.deepEqual(
  normalize(allClasses.matches.map((match) => [match.traceId, match.classKey])),
  [
    ["start", "start"],
    ["end", "end"],
    ["between", "between"],
    ["passes", "passes"],
    ["antimeridian", "between"],
    ["high-lat-start", "start"],
  ]
);
assert.equal(allClasses.stats.candidateSegments, 8);
assert.equal(allClasses.stats.matchedSegments, 6);
assert.equal(allClasses.stats.hiddenSegments, 2);
assert.equal(allClasses.stats.startSegments, 2);
assert.equal(allClasses.stats.endSegments, 1);
assert.equal(allClasses.stats.betweenSegments, 2);
assert.equal(allClasses.stats.passesSegments, 1);
assert.equal(allClasses.stats.passesSkippedSegments, 1);
assert.equal(allClasses.stats.noEndpointMatchSegments, 2);

const facilityKeysByTraceId = new Map(
  allClasses.matches.map((match) => [match.traceId, [...match.facilityKeys].sort()])
);
assert.deepEqual(normalize(facilityKeysByTraceId.get("start")), ["military:start"]);
assert.deepEqual(normalize(facilityKeysByTraceId.get("end")), ["research:end"]);
assert.deepEqual(
  normalize(facilityKeysByTraceId.get("between")),
  ["military:start", "research:end"]
);
assert.deepEqual(
  normalize(facilityKeysByTraceId.get("passes")),
  ["claimed:passes", "military:start", "research:end"]
);
assert.deepEqual(
  normalize(facilityKeysByTraceId.get("antimeridian")),
  ["military:anti-west", "research:anti-east"]
);
assert.deepEqual(normalize(facilityKeysByTraceId.get("high-lat-start")), ["research:high-lat"]);

const startOnly = classify(worker, segments, {
  start: true,
  end: false,
  between: false,
  passes: false,
});
assert.deepEqual(
  normalize(startOnly.matches.map((match) => [match.traceId, match.classKey])),
  [
    ["start", "start"],
    ["high-lat-start", "start"],
  ]
);
assert.equal(startOnly.stats.disabledClassSegments, 3);
assert.equal(startOnly.stats.noEndpointMatchSegments, 3);
assert.equal(startOnly.stats.passesSkippedSegments, 0);

const endOnly = classify(worker, segments, {
  start: false,
  end: true,
  between: false,
  passes: false,
});
assert.deepEqual(
  normalize(endOnly.matches.map((match) => [match.traceId, match.classKey])),
  [
    ["end", "end"],
  ]
);
assert.equal(endOnly.stats.disabledClassSegments, 4);
assert.equal(endOnly.stats.noEndpointMatchSegments, 3);

const betweenOnly = classify(worker, segments, {
  start: false,
  end: false,
  between: true,
  passes: false,
});
assert.deepEqual(
  normalize(betweenOnly.matches.map((match) => [match.traceId, match.classKey])),
  [
    ["between", "between"],
    ["antimeridian", "between"],
  ]
);
assert.equal(betweenOnly.stats.disabledClassSegments, 3);
assert.equal(betweenOnly.stats.noEndpointMatchSegments, 3);

const passesOnly = classify(worker, segments, {
  start: false,
  end: false,
  between: false,
  passes: true,
}, 20000, { evidenceMode: "include_generalized" });
assert.deepEqual(
  normalize(passesOnly.matches.map((match) => [match.traceId, match.classKey])),
  [
    ["passes", "passes"],
  ]
);
assert.equal(passesOnly.stats.disabledClassSegments, 5);
assert.equal(passesOnly.stats.noEndpointMatchSegments, 2);
assert.equal(passesOnly.stats.passesSkippedSegments, 1);

const startEndOnly = classify(worker, segments, {
  start: true,
  end: true,
  between: false,
  passes: false,
});
assert.deepEqual(
  normalize(startEndOnly.matches.map((match) => [match.traceId, match.classKey])),
  [
    ["start", "start"],
    ["end", "end"],
    ["high-lat-start", "start"],
  ]
);
assert.equal(startEndOnly.stats.disabledClassSegments, 2);
assert.equal(startEndOnly.stats.noEndpointMatchSegments, 3);
assert.equal(startEndOnly.stats.passesSkippedSegments, 0);

const betweenPassesOnly = classify(worker, segments, {
  start: false,
  end: false,
  between: true,
  passes: true,
}, 20000, { evidenceMode: "include_generalized" });
assert.deepEqual(
  normalize(betweenPassesOnly.matches.map((match) => [match.traceId, match.classKey])),
  [
    ["between", "between"],
    ["passes", "passes"],
    ["antimeridian", "between"],
  ]
);
assert.equal(betweenPassesOnly.stats.disabledClassSegments, 3);
assert.equal(betweenPassesOnly.stats.noEndpointMatchSegments, 2);
assert.equal(betweenPassesOnly.stats.passesSkippedSegments, 1);

const noClasses = classify(worker, segments, {
  start: false,
  end: false,
  between: false,
  passes: false,
});
assert.deepEqual(normalize(noClasses.matches), []);
assert.equal(noClasses.stats.disabledClassSegments, 5);
assert.equal(noClasses.stats.noEndpointMatchSegments, 3);

const radiusGrowthSegment = [
  { traceId: "radius-growth", fromEventId: "radius-from", toEventId: "radius-to", fromSortOrdinal: 10, toSortOrdinal: 20, from: [0, 0.1], to: [5, 5] },
];
const smallRadius = classify(worker, radiusGrowthSegment, { start: true }, 20000, { evidenceMode: "include_generalized" });
const largeRadius = classify(worker, radiusGrowthSegment, { start: true }, 50000, { evidenceMode: "include_generalized" });
assert.equal(smallRadius.matches.length, 1);
assert.equal(largeRadius.matches.length, 1);
const smallRadiusFacilityKeys = new Set(smallRadius.matches[0].facilityKeys);
const largeRadiusFacilityKeys = new Set(largeRadius.matches[0].facilityKeys);
assert.deepEqual([...smallRadiusFacilityKeys].sort(), ["military:start"]);
assert.deepEqual(
  [...largeRadiusFacilityKeys].sort(),
  ["military:start", "research:radius-growth"]
);
for (const facilityKey of smallRadiusFacilityKeys) {
  assert.equal(largeRadiusFacilityKeys.has(facilityKey), true);
}
assert.ok(largeRadiusFacilityKeys.size > smallRadiusFacilityKeys.size);

const reliabilityWorker = loadWorker("webapp/static_public/trace_facility_worker.js");
const reliabilityConfigure = reliabilityWorker.send({
  type: "configureTraceFacilityIndex",
  requestId: "configure-reliability",
  facilityIndexKey: "fixture-facilities",
  sourceCoordinateEventIds: ["supported-from", "supported-to"],
  exactDateEventIds: ["supported-from", "supported-to"],
  facilities: [
    { id: "active-start", facilityKey: "verified:active-start", source: "military", lat: 0, lon: 0, temporalKnown: true, startOrdinal: 0, endOrdinal: 100 },
    { id: "active-end", facilityKey: "verified:active-end", source: "researchSites", lat: 0, lon: 1, temporalKnown: true, startOrdinal: 0, endOrdinal: 100 },
    { id: "inactive", facilityKey: "verified:inactive", source: "military", lat: 1, lon: 0, temporalKnown: true, startOrdinal: 1000, endOrdinal: 2000 },
    { id: "unknown-date", facilityKey: "verified:unknown-date", source: "researchSites", lat: 2, lon: 0, temporalKnown: false },
    { id: "claimed", facilityKey: "claimed:site", source: "claimedUfoBases", lat: 3, lon: 0, temporalKnown: true, startOrdinal: 0, endOrdinal: 100 },
    { id: "pass-target", facilityKey: "verified:pass-target", source: "military", lat: 4, lon: 0, temporalKnown: true, temporalIntervals: [{ startOrdinal: 0, endOrdinal: 100 }] },
    { id: "boundary", facilityKey: "verified:boundary", source: "military", lat: 6, lon: 0, temporalKnown: true, temporalIntervals: [{ startOrdinal: 0, endOrdinal: 100, startBoundaryEndOrdinal: 10, endBoundaryStartOrdinal: 90 }] },
    { id: "mixed-active", facilityKey: "verified:mixed-active", source: "military", lat: 7, lon: 0, temporalKnown: true, startOrdinal: 0, endOrdinal: 100 },
    { id: "mixed-unknown", facilityKey: "verified:mixed-unknown", source: "researchSites", lat: 7, lon: 0.01, temporalKnown: false },
    { id: "mixed-claimed", facilityKey: "claimed:mixed", source: "claimedUfoBases", lat: 7, lon: 0.02, temporalKnown: true, startOrdinal: 0, endOrdinal: 100 },
    { id: "pass-boundary", facilityKey: "verified:pass-boundary", source: "military", lat: 9, lon: 0, temporalKnown: true, temporalIntervals: [{ startOrdinal: 0, endOrdinal: 100, startBoundaryEndOrdinal: 10 }] },
  ],
});
assert.equal(reliabilityConfigure.type, "traceFacilityIndexConfigured");
assert.equal(reliabilityConfigure.result.sourceCoordinateEventCount, 2);
assert.equal(reliabilityConfigure.result.exactDateEventCount, 2);

const supportedSegment = [{
  traceId: "supported",
  fromEventId: "supported-from",
  toEventId: "supported-to",
  fromSortOrdinal: 10,
  toSortOrdinal: 20,
  from: [0, 0.01],
  to: [5, 5],
}];
const supportedStrict = classify(reliabilityWorker, supportedSegment, { start: true });
assert.equal(supportedStrict.evidenceMode, "source_coordinates");
assert.equal(supportedStrict.matches.length, 1);
assert.equal(supportedStrict.matches[0].evidenceClass, "supported");
assert.deepEqual(normalize(supportedStrict.matches[0].supportedFacilityKeys), ["verified:active-start"]);
assert.deepEqual(normalize(supportedStrict.matches[0].possibleFacilityKeys), []);
assert.equal(supportedStrict.stats.supportedSegments, 1);
assert.equal(supportedStrict.stats.possibleSegments, 0);

const configuredEvidenceStrict = classify(
  reliabilityWorker,
  supportedSegment,
  { start: true },
  20000,
  { omitEvidenceIds: true }
);
assert.equal(configuredEvidenceStrict.matches.length, 1);
assert.equal(configuredEvidenceStrict.matches[0].evidenceClass, "supported");
assert.deepEqual(
  normalize(configuredEvidenceStrict.matches[0].supportedFacilityKeys),
  ["verified:active-start"]
);

const generalizedStrict = classify(
  reliabilityWorker,
  supportedSegment,
  { start: true },
  20000,
  { sourceCoordinateEventIds: [] }
);
assert.equal(generalizedStrict.matches.length, 0);
assert.equal(generalizedStrict.stats.generalizedEndpointSegments, 1);
assert.equal(generalizedStrict.stats.excludedEvidenceSegments, 1);
assert.equal(generalizedStrict.stats.excludedEvidenceReasons.generalized_location, 1);
const generalizedExploratory = classify(
  reliabilityWorker,
  supportedSegment,
  { start: true },
  20000,
  { evidenceMode: "include_generalized", sourceCoordinateEventIds: [] }
);
assert.equal(generalizedExploratory.matches.length, 1);
assert.equal(generalizedExploratory.matches[0].evidenceClass, "possible");
assert.deepEqual(normalize(generalizedExploratory.matches[0].possibleFacilityKeys), ["verified:active-start"]);
assert.equal(generalizedExploratory.stats.possibleSegments, 1);

const nonExactStrict = classify(
  reliabilityWorker,
  supportedSegment,
  { start: true },
  20000,
  { exactDateEventIds: [] }
);
assert.equal(nonExactStrict.matches.length, 0);
assert.equal(nonExactStrict.stats.excludedEvidenceSegments, 1);
assert.equal(nonExactStrict.stats.excludedEvidenceReasons.non_exact_date, 1);
const nonExactExploratory = classify(
  reliabilityWorker,
  supportedSegment,
  { start: true },
  20000,
  { evidenceMode: "include_generalized", exactDateEventIds: [] }
);
assert.equal(nonExactExploratory.matches.length, 1);
assert.equal(nonExactExploratory.matches[0].evidenceClass, "possible");

const unknownDateSegment = [{
  traceId: "unknown-date",
  fromEventId: "unknown-from",
  toEventId: "unknown-to",
  fromSortOrdinal: 10,
  toSortOrdinal: 20,
  from: [2, 0.01],
  to: [5, 5],
}];
const unknownDateStrict = classify(reliabilityWorker, unknownDateSegment, { start: true });
assert.equal(unknownDateStrict.matches.length, 0);
assert.equal(unknownDateStrict.stats.temporalUnknownSegments, 1);
assert.equal(unknownDateStrict.stats.excludedEvidenceSegments, 1);
assert.equal(unknownDateStrict.stats.excludedEvidenceReasons.facility_time_unknown, 1);
const unknownDateExploratory = classify(
  reliabilityWorker,
  unknownDateSegment,
  { start: true },
  20000,
  { evidenceMode: "include_generalized" }
);
assert.equal(unknownDateExploratory.matches[0].evidenceClass, "possible");

const claimedSegment = [{
  traceId: "claimed",
  fromEventId: "claimed-from",
  toEventId: "claimed-to",
  fromSortOrdinal: 10,
  toSortOrdinal: 20,
  from: [3, 0.01],
  to: [5, 5],
}];
const claimedStrict = classify(reliabilityWorker, claimedSegment, { start: true });
assert.equal(claimedStrict.matches.length, 0);
assert.equal(claimedStrict.stats.excludedEvidenceSegments, 1);
assert.equal(claimedStrict.stats.excludedEvidenceReasons.claimed_facility_source, 1);
const claimedExploratory = classify(
  reliabilityWorker,
  claimedSegment,
  { start: true },
  20000,
  { evidenceMode: "include_generalized" }
);
assert.equal(claimedExploratory.matches[0].evidenceClass, "possible");
assert.deepEqual(normalize(claimedExploratory.matches[0].possibleFacilityKeys), ["claimed:site"]);

const inactiveSegment = [{
  traceId: "inactive",
  fromEventId: "inactive-from",
  toEventId: "inactive-to",
  fromSortOrdinal: 10,
  toSortOrdinal: 20,
  from: [1, 0.01],
  to: [5, 5],
}];
const inactiveExploratory = classify(
  reliabilityWorker,
  inactiveSegment,
  { start: true },
  20000,
  { evidenceMode: "include_generalized" }
);
assert.equal(inactiveExploratory.matches.length, 0);
assert.equal(inactiveExploratory.stats.knownInactiveFacilitiesExcluded, 1);

const mixedSegment = [{
  traceId: "mixed",
  fromEventId: "mixed-from",
  toEventId: "mixed-to",
  fromSortOrdinal: 10,
  toSortOrdinal: 20,
  from: [0, 0.01],
  to: [0, 1.01],
}];
const mixedStrict = classify(
  reliabilityWorker,
  mixedSegment,
  { start: true, between: true },
  20000,
  { sourceCoordinateEventIds: ["mixed-from"] }
);
assert.deepEqual(
  normalize(mixedStrict.matches.map((match) => [match.classKey, match.evidenceClass])),
  [["start", "supported"]]
);
const mixedExploratory = classify(
  reliabilityWorker,
  mixedSegment,
  { start: true, between: true },
  20000,
  { evidenceMode: "include_generalized", sourceCoordinateEventIds: ["mixed-from"] }
);
assert.deepEqual(
  normalize(mixedExploratory.matches.map((match) => [match.classKey, match.evidenceClass])),
  [["between", "possible"]]
);
assert.deepEqual(normalize(mixedExploratory.matches[0].supportedFacilityKeys), ["verified:active-start"]);
assert.deepEqual(normalize(mixedExploratory.matches[0].possibleFacilityKeys), ["verified:active-end"]);

function boundaryEndpointSegment(traceId, ordinal) {
  return [{
    traceId,
    fromEventId: traceId + "-from",
    toEventId: traceId + "-to",
    fromSortOrdinal: ordinal,
    toSortOrdinal: ordinal + 1,
    from: [6, 0.01],
    to: [12, 12],
  }];
}

const openingBoundarySegment = boundaryEndpointSegment("opening-boundary", 5);
const openingBoundaryStrict = classify(reliabilityWorker, openingBoundarySegment, { start: true });
assert.equal(openingBoundaryStrict.matches.length, 0);
assert.equal(openingBoundaryStrict.stats.temporalUnknownSegments, 1);
assert.equal(openingBoundaryStrict.stats.excludedEvidenceSegments, 1);
assert.equal(openingBoundaryStrict.stats.excludedEvidenceReasons.facility_time_boundary, 1);
const openingBoundaryExploratory = classify(
  reliabilityWorker,
  openingBoundarySegment,
  { start: true },
  20000,
  { evidenceMode: "include_generalized" }
);
assert.equal(openingBoundaryExploratory.matches.length, 1);
assert.equal(openingBoundaryExploratory.matches[0].evidenceClass, "possible");

const interiorBoundarySegment = boundaryEndpointSegment("boundary-interior", 50);
const interiorBoundaryStrict = classify(reliabilityWorker, interiorBoundarySegment, { start: true });
assert.equal(interiorBoundaryStrict.matches.length, 1);
assert.equal(interiorBoundaryStrict.matches[0].evidenceClass, "supported");
assert.deepEqual(
  normalize(interiorBoundaryStrict.matches[0].supportedFacilityKeys),
  ["verified:boundary"]
);

const closingBoundarySegment = boundaryEndpointSegment("closing-boundary", 95);
const closingBoundaryStrict = classify(reliabilityWorker, closingBoundarySegment, { start: true });
assert.equal(closingBoundaryStrict.matches.length, 0);
assert.equal(closingBoundaryStrict.stats.excludedEvidenceReasons.facility_time_boundary, 1);

const outsideBoundarySegment = boundaryEndpointSegment("boundary-inactive", 150);
const outsideBoundaryExploratory = classify(
  reliabilityWorker,
  outsideBoundarySegment,
  { start: true },
  20000,
  { evidenceMode: "include_generalized" }
);
assert.equal(outsideBoundaryExploratory.matches.length, 0);
assert.equal(outsideBoundaryExploratory.stats.knownInactiveFacilitiesExcluded, 1);

const mixedSameEndpointSegment = [{
  traceId: "mixed-same-endpoint",
  fromEventId: "mixed-same-from",
  toEventId: "mixed-same-to",
  fromSortOrdinal: 20,
  toSortOrdinal: 21,
  from: [7, 0],
  to: [12, 12],
}];
const mixedSameEndpointExploratory = classify(
  reliabilityWorker,
  mixedSameEndpointSegment,
  { start: true },
  20000,
  { evidenceMode: "include_generalized" }
);
assert.equal(mixedSameEndpointExploratory.matches.length, 1);
assert.equal(mixedSameEndpointExploratory.matches[0].evidenceClass, "supported");
assert.deepEqual(
  normalize(mixedSameEndpointExploratory.matches[0].facilityKeys),
  ["verified:mixed-active"]
);
assert.deepEqual(
  normalize(mixedSameEndpointExploratory.matches[0].supportedFacilityKeys),
  ["verified:mixed-active"]
);
assert.deepEqual(normalize(mixedSameEndpointExploratory.matches[0].possibleFacilityKeys), []);

const passSegment = [{
  traceId: "pass-policy",
  fromEventId: "pass-from",
  toEventId: "pass-to",
  fromSortOrdinal: 10,
  toSortOrdinal: 20,
  from: [4, -1],
  to: [4, 1],
}];
const passStrict = classify(reliabilityWorker, passSegment, { passes: true });
assert.equal(passStrict.matches.length, 0);
assert.equal(passStrict.stats.excludedEvidenceSegments, 1);
assert.equal(passStrict.stats.excludedEvidenceReasons.connector_intersection, 1);
const passExploratory = classify(
  reliabilityWorker,
  passSegment,
  { passes: true },
  20000,
  { evidenceMode: "include_generalized" }
);
assert.deepEqual(
  normalize(passExploratory.matches.map((match) => [match.classKey, match.evidenceClass])),
  [["passes", "possible"]]
);

const boundaryPassSegment = [{
  traceId: "pass-boundary-policy",
  fromEventId: "pass-boundary-from",
  toEventId: "pass-boundary-to",
  fromSortOrdinal: 5,
  toSortOrdinal: 20,
  from: [9, -1],
  to: [9, 1],
}];
const boundaryPassExploratory = classify(
  reliabilityWorker,
  boundaryPassSegment,
  { passes: true },
  20000,
  { evidenceMode: "include_generalized" }
);
assert.equal(boundaryPassExploratory.matches.length, 1);
assert.equal(boundaryPassExploratory.matches[0].evidenceClass, "possible");
assert.deepEqual(
  normalize(boundaryPassExploratory.matches[0].possibleFacilityKeys),
  ["verified:pass-boundary"]
);
assert.equal(boundaryPassExploratory.stats.temporalUnknownSegments, 1);

function buildPackedTraceFixture() {
  const bytesPerRow = 32;
  const buffer = new ArrayBuffer(bytesPerRow * 2);
  const view = new DataView(buffer);
  [
    { eventId: 101n, lat: 0, lon: 0.01, sortOrdinal: 10, sequenceIndex: 0 },
    { eventId: 102n, lat: 0, lon: 1.01, sortOrdinal: 20, sequenceIndex: 1 },
  ].forEach((row, rowIndex) => {
    const offset = rowIndex * bytesPerRow;
    view.setBigUint64(offset, row.eventId, true);
    view.setFloat64(offset + 8, row.lat, true);
    view.setFloat64(offset + 16, row.lon, true);
    view.setInt32(offset + 24, row.sortOrdinal, true);
    view.setUint32(offset + 28, row.sequenceIndex, true);
  });
  return {
    buffer,
    metadata: {
      row_count: 2,
      bytes_per_row: bytesPerRow,
      fields: [
        { name: "event_id", type: "uint64", offset: 0 },
        { name: "lat", type: "float64", offset: 8 },
        { name: "lon", type: "float64", offset: 16 },
        { name: "sort_ordinal", type: "int32", offset: 24 },
        { name: "sequence_index", type: "uint32", offset: 28 },
      ],
    },
  };
}

const packedWorker = loadWorker("webapp/static_public/trace_facility_worker.js");
assert.equal(packedWorker.send({
  type: "configureTraceFacilityIndex",
  requestId: "packed-facilities",
  facilityIndexKey: "packed-facilities",
  sourceCoordinateEventIds: ["101"],
  exactDateEventIds: ["101", "102"],
  facilities: [
    { id: "packed-start", facilityKey: "verified:packed-start", source: "military", lat: 0, lon: 0, temporalKnown: true, startOrdinal: 0, endOrdinal: 100 },
    { id: "packed-end", facilityKey: "verified:packed-end", source: "researchSites", lat: 0, lon: 1, temporalKnown: true, startOrdinal: 0, endOrdinal: 100 },
  ],
}).type, "traceFacilityIndexConfigured");
const packedFixture = buildPackedTraceFixture();
const packedIndexResponse = await packedWorker.sendAsync({
  type: "configureTraceEventIndex",
  requestId: "packed-index",
  traceIndexKey: "packed-index",
  metadata: packedFixture.metadata,
  buffer: packedFixture.buffer,
});
assert.equal(packedIndexResponse.type, "traceEventIndexConfigured");

function classifyPacked(evidenceMode) {
  const response = packedWorker.send({
    type: "buildAndClassifyPackedTraceFacilitySegments",
    requestId: "packed-" + evidenceMode,
    traceIndexKey: "packed-index",
    facilityIndexKey: "packed-facilities",
    filter: {
      radiusMeters: 20000,
      evidenceMode,
      classes: { start: true, end: true, between: true, passes: true },
    },
    filteredEventIds: ["101", "102"],
    activeBucketKeys: ["gap_le_30"],
    startOrdinal: 0,
    endOrdinal: 100,
  });
  assert.equal(response.type, "packedTraceFacilitySegmentsBuilt");
  return response.result;
}

const packedStrict = classifyPacked("source_coordinates");
assert.equal(packedStrict.segments.length, 1);
assert.equal(packedStrict.segments[0].facilityTraceClass, "start");
assert.equal(packedStrict.segments[0].facilityTraceEvidenceClass, "supported");
assert.deepEqual(normalize(packedStrict.segments[0].supportedFacilityKeys), ["verified:packed-start"]);
assert.deepEqual(normalize(packedStrict.segments[0].possibleFacilityKeys), []);
const packedExploratory = classifyPacked("include_generalized");
assert.equal(packedExploratory.segments.length, 1);
assert.equal(packedExploratory.segments[0].facilityTraceClass, "between");
assert.equal(packedExploratory.segments[0].facilityTraceEvidenceClass, "possible");
assert.deepEqual(normalize(packedExploratory.segments[0].supportedFacilityKeys), ["verified:packed-start"]);
assert.deepEqual(normalize(packedExploratory.segments[0].possibleFacilityKeys), ["verified:packed-end"]);

console.log("trace facility worker classification assertions passed");

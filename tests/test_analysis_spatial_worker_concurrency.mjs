import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import { createHash, webcrypto } from "node:crypto";

class ControlledSpatialWorker {
  static instances = [];

  constructor(url) {
    this.url = String(url);
    this.onmessage = null;
    this.onerror = null;
    this.messages = [];
    this.terminated = false;
    ControlledSpatialWorker.instances.push(this);
  }

  postMessage(message) {
    this.messages.push(message);
    if (message.type !== "initializeSpatialAnalysis") return;
    queueMicrotask(() => {
      if (this.terminated || typeof this.onmessage !== "function") return;
      this.onmessage({
        data: {
          type: "spatialAnalysisReady",
          executionEpoch: message.executionEpoch,
          estimatorVersion: "controlled-spatial-v2",
        },
      });
    });
  }

  terminate() {
    this.terminated = true;
  }
}

function createHarness(fetch) {
  const messages = [];
  const self = {
    crypto: webcrypto,
    location: { href: "https://example.test/catalog_filter_worker.js" },
    postMessage(message) {
      messages.push(JSON.parse(JSON.stringify(message)));
    },
  };
  const context = vm.createContext({
    Array, Boolean, JSON, Map, Math, Number, Object, Promise, Set, String,
    Response, TextDecoder, URL, Worker: ControlledSpatialWorker,
    console, fetch, queueMicrotask, self,
  });
  for (const path of [
    "webapp/static_public/analysis_stats.js",
    "webapp/static_public/analysis_spatial.js",
    "webapp/static_public/catalog_filter_worker.js",
  ]) {
    vm.runInContext(fs.readFileSync(path, "utf8"), context, { filename: path });
  }
  return {
    messages,
    post(message) {
      self.onmessage({ data: message });
    },
    take(requestId) {
      const index = messages.findIndex((message) => message.requestId === requestId);
      return index === -1 ? null : messages.splice(index, 1)[0];
    },
    async waitFor(predicate, label) {
      for (let attempt = 0; attempt < 100; attempt += 1) {
        const found = messages.find(predicate);
        if (found) return found;
        await new Promise((resolve) => setTimeout(resolve, 2));
      }
      assert.fail(`timed out waiting for ${label}`);
    },
  };
}

const neighborsText = JSON.stringify([]);
const facilitiesText = JSON.stringify([]);
const spatialPointsText = JSON.stringify([]);
const contextNeighborsText = JSON.stringify([]);
const relationshipsText = JSON.stringify([]);
const fixtureArtifact = (file, text, rowSchema) => ({
  file,
  rowCount: 0,
  rowSchema,
  sha256: createHash("sha256").update(text).digest("hex"),
});
const fetch = async (urlValue) => {
  const url = String(urlValue);
  if (url.endsWith("neighbors.json")) return new Response(neighborsText, { status: 200 });
  if (url.endsWith("facilities.json")) return new Response(facilitiesText, { status: 200 });
  if (url.endsWith("spatial-points.json")) return new Response(spatialPointsText, { status: 200 });
  if (url.endsWith("context-neighbors.json")) return new Response(contextNeighborsText, { status: 200 });
  if (url.endsWith("relationships.json")) return new Response(relationshipsText, { status: 200 });
  return new Response("not found", { status: 404 });
};

const harness = createHarness(fetch);
const day = Math.trunc(Date.UTC(2000, 0, 1) / 86400000);
const filters = {
  keyword: "",
  sourceMode: "all",
  typeMode: "all",
  precisionMode: "all",
  selectedSources: [],
  selectedTypes: [],
  selectedPrecisions: [],
  hideLowPrecision: false,
  hideNonExactDates: false,
};
harness.post({
  type: "addCatalogFacetRows",
  requestId: "add",
  rows: [{
    eventId: "1",
    source: "ufocat",
    type: "Triangle",
    visualTypeGroup: "Triangle",
    craftType: "triangle",
    shape: "Triangle",
    craftConfidence: "high",
    craftSource: "shape_normalized",
    sameDayMatchStrength: "strong",
    precision: "exact_coords",
    datePrecision: "exact_day",
    coordinateSource: "raw_latlong",
    sortOrdinal: day,
    lat: 35,
    lon: -117,
    mapped: true,
    country: "US",
    adminRegion: "CA",
  }],
});
assert.equal(harness.take("add").type, "catalogFacetRowsAdded");

harness.post({
  type: "setAnalysisSpatialArtifacts",
  requestId: "setup",
  filterGeneration: 1,
  cancellationGeneration: 0,
  manifest: {
    schemaVersion: 2,
    schemaId: "ufo-timeline-analysis-evidence-artifacts-v2.1.0",
    manifestVersion: "2.1.0",
    releaseId: "concurrency-fixture",
    artifacts: {
      ufoPointNeighbors: fixtureArtifact("neighbors.json", neighborsText, ["left", "right"]),
      facilityAnalysis: fixtureArtifact("facilities.json", facilitiesText, ["id"]),
      ufoSpatialPoints: fixtureArtifact("spatial-points.json", spatialPointsText, ["eventId"]),
      contextUfoNeighbors: fixtureArtifact("context-neighbors.json", contextNeighborsText, ["contextId"]),
      relationshipReconciliation: fixtureArtifact("relationships.json", relationshipsText, ["relationshipId"]),
    },
    counts: {},
  },
  urls: {
    manifest: "https://example.test/data/analysis_v2/manifest.json",
    neighbors: "https://example.test/neighbors.json",
    facilities: "https://example.test/facilities.json",
    spatialPoints: "https://example.test/spatial-points.json",
    contextNeighbors: "https://example.test/context-neighbors.json",
    relationships: "https://example.test/relationships.json",
  },
});
await harness.waitFor((message) => message.requestId === "setup", "spatial setup");
assert.equal(harness.take("setup").type, "analysisSpatialArtifactsSet");
assert.equal(ControlledSpatialWorker.instances.length, 1);
const coldWorker = ControlledSpatialWorker.instances[0];
assert.match(
  coldWorker.url,
  /analysis_spatial_worker\.js\?v=2026-08-04-analysis-geography-binary-v1-ui1$/,
  "the dedicated worker URL pins the v2.2 analytical runtime instead of reusing stale browser code"
);

function computeMessage(requestId, cancellationGeneration, selectedDomains) {
  return {
    type: "computeAnalysis",
    requestId,
    analysisSignature: `${requestId}-signature`,
    filterGeneration: cancellationGeneration,
    cancellationGeneration,
    baselineMode: "other_dates_balanced",
    datasetHash: "concurrency-fixture",
    selectedDomains,
    filters,
    lowPrecisionValues: [],
    timeRangeStartOrdinal: day,
    timeRangeEndOrdinal: day,
    spatialPermutationCount: 499,
    spatialBootstrapCount: 199,
    spatialMinimumStratumSize: 20,
  };
}

harness.post(computeMessage("cold-spatial", 1, ["overview", "spatial"]));
for (let attempt = 0; attempt < 20 && !coldWorker.messages.some((message) => message.type === "computeSpatialAnalysis"); attempt += 1) {
  await new Promise((resolve) => setTimeout(resolve, 2));
}
const coldJob = coldWorker.messages.find((message) => message.type === "computeSpatialAnalysis");
assert.ok(coldJob, "cold spatial work must be delegated to the subordinate worker");
assert.equal(harness.take("cold-spatial"), null, "catalog worker must not publish an incomplete spatial result");

// A core Analysis request remains serviceable while the controlled spatial
// worker is deliberately held outstanding.
harness.post(computeMessage("core-during-spatial", 1, ["overview", "time"]));
const coreDuringSpatial = harness.take("core-during-spatial");
assert.equal(coreDuringSpatial.type, "analysisComputed");
assert.equal(coreDuringSpatial.cancellationGeneration, 1);
assert.equal(coldWorker.terminated, false, "same-generation core work does not need to disturb the spatial lane");

const staleHandler = coldWorker.onmessage;
harness.post(computeMessage("newer-core", 2, ["overview"]));
const cancelled = harness.take("cold-spatial");
assert.equal(cancelled.type, "analysisWorkerError");
assert.equal(cancelled.errorCode, "spatial_analysis_cancelled");
assert.equal(cancelled.cancelled, true);
assert.equal(coldWorker.terminated, true, "superseded synchronous spatial work must be terminated, not merely ignored");
assert.equal(harness.take("newer-core").type, "analysisComputed");

const messageCountBeforeLateResult = harness.messages.length;
staleHandler({
  data: {
    type: "spatialAnalysisComputed",
    jobId: coldJob.jobId,
    cancellationGeneration: 1,
    result: { traceInputsRead: false, staleFixture: true },
  },
});
assert.equal(
  harness.messages.length,
  messageCountBeforeLateResult,
  "a late result from a terminated executor epoch must be rejected"
);

harness.post(computeMessage("explicit-stale", 1, ["overview", "spatial"]));
const explicitStale = harness.take("explicit-stale");
assert.equal(explicitStale.type, "analysisWorkerError");
assert.equal(explicitStale.errorCode, "stale_spatial_request");
assert.equal(explicitStale.cancelled, true);
assert.equal(ControlledSpatialWorker.instances.length, 1, "a stale request must not allocate another worker");

harness.post({
  ...computeMessage("fresh-spatial", 3, ["overview", "spatial"]),
  baselineMode: "full_catalog",
});
for (let attempt = 0; attempt < 30 && ControlledSpatialWorker.instances.length < 2; attempt += 1) {
  await new Promise((resolve) => setTimeout(resolve, 2));
}
const freshWorker = ControlledSpatialWorker.instances[1];
assert.ok(freshWorker, "a fresh spatial generation must recreate the terminated executor");
for (let attempt = 0; attempt < 30 && !freshWorker.messages.some((message) => message.type === "computeSpatialAnalysis"); attempt += 1) {
  await new Promise((resolve) => setTimeout(resolve, 2));
}
const freshJob = freshWorker.messages.find((message) => message.type === "computeSpatialAnalysis");
assert.ok(freshJob);
assert.equal(freshJob.baselineMode, "full_catalog");
assert.equal(freshJob.inferenceEnabled, false);
assert.equal(freshJob.permutationCount, 499);
assert.equal(freshJob.bootstrapCount, 199);
freshWorker.onmessage({
  data: {
    type: "spatialAnalysisComputed",
    jobId: freshJob.jobId,
    cancellationGeneration: 3,
    result: { traceInputsRead: false, fixture: "fresh" },
  },
});
const freshSpatial = harness.take("fresh-spatial");
assert.equal(freshSpatial.type, "analysisComputed");
assert.equal(freshSpatial.result.spatialEvidence.fixture, "fresh");
assert.equal(freshSpatial.result.spatialEvidence.traceInputsRead, false);
assert.equal(freshSpatial.result.spatialEvidence.baselineMode, "full_catalog");
assert.equal(freshSpatial.result.spatialEvidence.inferenceEnabled, false);

harness.post({
  ...computeMessage("whole-corpus-spatial", 4, ["overview", "spatial"]),
  baselineMode: "full_catalog",
  fullTimeRange: true,
  timeRangeMode: "full",
});
for (let attempt = 0; attempt < 30 && !freshWorker.messages.some((message) => message.jobId?.includes("whole-corpus-spatial")); attempt += 1) {
  await new Promise((resolve) => setTimeout(resolve, 2));
}
const wholeCorpusJob = freshWorker.messages.find((message) => message.jobId?.includes("whole-corpus-spatial"));
assert.ok(wholeCorpusJob, "All Time spatial work must remain delegated");
assert.equal(wholeCorpusJob.analysisMode, "whole_corpus_structure");
assert.equal(wholeCorpusJob.comparisonState, "whole_corpus_structure");
assert.equal(wholeCorpusJob.inferenceEnabled, true, "All Time overrides a retained full-catalog selector token");
freshWorker.onmessage({
  data: {
    type: "spatialAnalysisComputed",
    jobId: wholeCorpusJob.jobId,
    cancellationGeneration: 4,
    result: {
      traceInputsRead: false,
      analysisMode: "whole_corpus_structure",
      comparisonState: "whole_corpus_structure",
      cells: [{ pValue: 0.01, qValue: 0.02 }],
    },
  },
});
const wholeCorpusSpatial = harness.take("whole-corpus-spatial");
assert.equal(wholeCorpusSpatial.type, "analysisComputed");
assert.equal(wholeCorpusSpatial.result.spatialEvidence.inferenceEnabled, true);
assert.equal(wholeCorpusSpatial.result.spatialEvidence.cells[0].pValue, 0.01);
assert.equal(wholeCorpusSpatial.result.spatialEvidence.cells[0].qValue, 0.02);

// Exercise the production subordinate-worker envelope independently from the
// controlled concurrency double above.
const subordinateMessages = [];
const subordinateSelf = {
  UfoAnalysisSpatial: {
    ESTIMATOR_VERSION: "subordinate-fixture-v2",
    computeSpatialAnalysis(options) {
      return {
        rowCount: options.rows.length,
        edgeCount: options.edges.length,
        spatialPointCount: options.spatialPoints.length,
        contextNeighborCount: options.contextNeighbors.length,
        facilityCount: options.facilities.length,
        relationshipCount: options.relationships.length,
        codebookCount: Object.keys(options.codebooks).length,
        receivedBaselineMode: options.baselineMode,
        receivedInferenceEnabled: options.inferenceEnabled,
        receivedPermutationCount: options.permutationCount,
        receivedBootstrapCount: options.bootstrapCount,
        traceInputsRead: false,
      };
    },
  },
  postMessage(message) {
    subordinateMessages.push(JSON.parse(JSON.stringify(message)));
  },
};
const subordinateContext = vm.createContext({
  Array, Boolean, JSON, Math, Number, Object, String, self: subordinateSelf,
});
vm.runInContext(
  fs.readFileSync("webapp/static_public/analysis_spatial_worker.js", "utf8"),
  subordinateContext,
  { filename: "webapp/static_public/analysis_spatial_worker.js" }
);
subordinateSelf.onmessage({
  data: {
    type: "initializeSpatialAnalysis",
    executionEpoch: 9,
    edges: [["1", "2"]],
    spatialPoints: [["1"]],
    contextNeighbors: [["crop", "1"]],
    facilities: [{ id: "facility-1" }],
    relationships: [["relationship-1"]],
    codebooks: { fixture: { values: ["one"] } },
    readiness: {},
    artifactHashes: { fixture: "hash" },
  },
});
assert.deepEqual(subordinateMessages.shift(), {
  type: "spatialAnalysisReady",
  executionEpoch: 9,
  estimatorVersion: "subordinate-fixture-v2",
    rowCounts: {
      neighbors: 1,
      spatialPoints: 1,
      configurationPoints: 0,
      configurationNeighbors: 0,
      contextNeighbors: 1,
      facilities: 1,
      relationships: 1,
  },
});
subordinateSelf.onmessage({
  data: {
    type: "computeSpatialAnalysis",
    jobId: "subordinate-job",
    cancellationGeneration: 4,
    rows: [{ eventId: "1" }],
    seed: "fixture",
    baselineMode: "full_catalog",
    inferenceEnabled: false,
    permutationCount: 499,
    bootstrapCount: 199,
  },
});
assert.deepEqual(subordinateMessages.shift(), {
  type: "spatialAnalysisComputed",
  executionEpoch: 9,
  jobId: "subordinate-job",
  cancellationGeneration: 4,
  estimatorVersion: "subordinate-fixture-v2",
  result: {
    rowCount: 1,
    edgeCount: 1,
    spatialPointCount: 1,
    contextNeighborCount: 1,
    facilityCount: 1,
    relationshipCount: 1,
    codebookCount: 1,
    receivedBaselineMode: "full_catalog",
    receivedInferenceEnabled: false,
    receivedPermutationCount: 499,
    receivedBootstrapCount: 199,
    traceInputsRead: false,
    baselineMode: "full_catalog",
    analysisMode: "cohort_comparison",
    comparisonState: "descriptive_overlap",
    inferenceEnabled: false,
  },
});

console.log("analysis spatial worker concurrency assertions passed");

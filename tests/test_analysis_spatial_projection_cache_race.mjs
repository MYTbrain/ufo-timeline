// Reproduce a late dedicated Spatial completion after typed evidence commits.
// Actual worker dispatch, core statistics, finalization and cache functions run;
// only Spatial transport and the already-validated projection commit are fixtures.
// No corpus or generated release is copied.
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";

const statsSource = fs.readFileSync("analysis_stats.js", "utf8");
const workerSource = fs.readFileSync("catalog_filter_worker.js", "utf8");
const fixtureHooks = `
  self.__cacheRaceFixture = {
    enableSpatial() {
      analysisSpatialArtifacts.loaded = true;
      analysisSpatialArtifacts.manifest = {};
      analysisCache.clear();
    },
    key(message) { return analysisCacheKey(message); },
    commitTypedFields() {
      const readiness = { status: "ready_descriptive" };
      analysisDurationArtifact = {
        loaded: true, releaseId: "fixture-duration", artifactHashes: {},
        manifest: { codes: { status: ["exact"], durationBin: ["1_4_minutes"] },
          counts: { normalizedRows: 1 }, readiness, policy: {} }
      };
      analysisTimeOfDayArtifact = {
        loaded: true, releaseId: "fixture-clock", artifactHashes: {},
        manifest: { codes: { status: ["exact_clock"], timeBin: ["evening_18_23"] },
          counts: { typedRows: 1 }, readiness, policy: {} }
      };
      analysisWitnessCountArtifact = {
        loaded: true, releaseId: "fixture-witness", artifactHashes: {},
        manifest: { codes: { status: ["exact_count"], witnessCountBin: ["two"] },
          counts: { bySourceTyped: { nuforc: 1 } }, readiness, policy: {} }
      };
      for (const chunk of chunks) {
        for (const key of ["analysisDurationValueCodes", "analysisDurationStatusCodes",
          "analysisDurationDescriptiveBinCodes", "analysisDurationInferentialBinCodes",
          "analysisTimeOfDayValueCodes", "analysisTimeOfDayStatusCodes",
          "analysisTimeOfDayDescriptiveBinCodes", "analysisTimeOfDayInferentialBinCodes",
          "analysisWitnessCountValueCodes", "analysisWitnessCountStatusCodes", "analysisWitnessCountBinCodes"])
          chunk[key].fill(1);
        chunk.analysisDurationLowerSeconds.fill(120);
        chunk.analysisDurationUpperSeconds.fill(120);
        chunk.analysisTimeOfDayLowerMinutes.fill(1200);
        chunk.analysisTimeOfDayUpperMinutes.fill(1200);
        chunk.analysisWitnessCountExactCounts.fill(2);
      }
      // The production loaders clear both caches when their projections commit.
      analysisCache.clear();
      analysisMatchCache.clear();
    }
  };
`;

function makeWorker(source) {
  const pending = new Map();
  const spatialJobs = [];
  const responses = [];
  let requestNumber = 0;
  class SpatialTransport {
    postMessage(message) {
      if (message.type === "initializeSpatialAnalysis") {
        Promise.resolve().then(() => this.onmessage({ data: { type: "spatialAnalysisReady" } }));
      } else {
        assert.equal(message.type, "computeSpatialAnalysis");
        spatialJobs.push({ transport: this, message });
      }
    }
    terminate() {}
  }
  const self = {
    location: { href: "https://fixture.invalid/catalog_filter_worker.js" },
    postMessage(message) {
      responses.push(message);
      assert.ok(pending.has(message.requestId), "unexpected worker response");
      const resolve = pending.get(message.requestId);
      pending.delete(message.requestId);
      resolve(message);
    }
  };
  const context = vm.createContext({ self, console, Worker: SpatialTransport, URL });
  vm.runInContext(statsSource, context, { filename: "analysis_stats.js" });
  const end = source.lastIndexOf("})();");
  assert.ok(end > 0);
  vm.runInContext(source.slice(0, end) + fixtureHooks + source.slice(end), context,
    { filename: "catalog_filter_worker.js" });
  return {
    fixture: self.__cacheRaceFixture, responses, spatialJobs,
    send(message) {
      return new Promise(resolve => {
        const requestId = "cache-race-" + (++requestNumber);
        pending.set(requestId, resolve);
        self.onmessage({ data: { ...message, requestId } });
      });
    },
    completeSpatial(index) {
      const { transport, message } = spatialJobs[index];
      transport.onmessage({ data: { type: "spatialAnalysisComputed", jobId: message.jobId,
        cancellationGeneration: message.cancellationGeneration,
        result: { analysisMode: "whole_corpus_structure", comparisonState: "whole_corpus_structure" } } });
    }
  };
}

const flush = async () => { for (let i = 0; i < 10; i += 1) await Promise.resolve(); };
const fullRequest = {
  type: "computeAnalysis", generation: 1, filterGeneration: 1, cancellationGeneration: 1,
  analysisPhase: "full", quickMode: false, timeRangeMode: "full", fullTimeRange: true,
  baselineMode: "full_catalog", datasetHash: "same-catalog", estimatorVersion: "same-estimator",
  // The browser already knows these manifest hashes while the loaders run.
  artifactHashes: { durationProjection: "same-duration-hash", timeProjection: "same-clock-hash",
    witnessProjection: "same-witness-hash" },
  filters: { sourceMode: "all", typeMode: "all", precisionMode: "all",
    hideLowPrecision: false, hideNonExactDates: false },
  selectedDomains: ["overview", "time", "sources_quality", "spatial"]
};
function assertLoaded(result) {
  assert.equal(result.time.duration.coverage.active.descriptiveBinnedRows, 1);
  assert.equal(result.time.timeOfDay.coverage.active.descriptiveBinnedRows, 1);
  assert.equal(result.sourcesQuality.witnessCount.coverage.active.exactCountRows, 1);
  assert.equal(result.sourcesQuality.witnessCount.status, "ready_descriptive");
  assert.notEqual(result.time.duration.status, "data_unavailable");
  assert.notEqual(result.time.timeOfDay.status, "data_unavailable");
}

async function runRace(source, expectFixed) {
  const worker = makeWorker(source);
  const added = await worker.send({ type: "addCatalogFacetRows", rows: [{
    eventId: 1, source: "nuforc", type: "light", craftType: "light", datePrecision: "day",
    sortOrdinal: 12000, precision: "city", mapped: true, lat: 40, lon: -100
  }] });
  assert.equal(added.type, "catalogFacetRowsAdded");
  worker.fixture.enableSpatial();
  const oldKey = worker.fixture.key(fullRequest);
  const oldFullPromise = worker.send(fullRequest);
  await flush();
  assert.equal(worker.spatialJobs.length, 1, "full core awaits its dedicated Spatial result");

  worker.fixture.commitTypedFields();
  const loadedKey = worker.fixture.key(fullRequest);
  assert.equal(oldKey !== loadedKey, expectFixed, "worker readiness belongs to the cache identity");
  worker.completeSpatial(0);
  const oldFull = await oldFullPromise;
  assert.equal(oldFull.cacheHit, false);
  assert.equal(oldFull.result.time.duration.status, "data_unavailable");
  assert.equal(oldFull.result.time.timeOfDay.status, "data_unavailable");
  assert.equal(oldFull.result.sourcesQuality.witnessCount.status, "data_unavailable");

  const quick = await worker.send({ ...fullRequest, analysisPhase: "quick", quickMode: true,
    cancellationGeneration: 2, selectedDomains: ["overview", "time", "sources_quality", "context"] });
  assert.equal(quick.type, "analysisComputed", quick.error);
  assert.equal(quick.cacheHit, false);
  assertLoaded(quick.result);
  assert.equal(quick.result.inferenceDeferred, true);

  const newFullPromise = worker.send({ ...fullRequest, cancellationGeneration: 3 });
  await flush();
  if (expectFixed) {
    assert.equal(worker.spatialJobs.length, 2, "loaded full must compute rather than reuse old core");
    worker.completeSpatial(1);
  } else {
    assert.equal(worker.spatialJobs.length, 1, "old cache identity reproduces stale full reuse");
  }
  const newFull = await newFullPromise;
  assert.equal(newFull.cacheHit, !expectFixed);
  assert.equal(newFull.result.inferenceDeferred, false, "the failure was an old full, not a quick/full collision");
  if (expectFixed) {
    assertLoaded(newFull.result);
    const warm = await worker.send({ ...fullRequest, cancellationGeneration: 4 });
    assert.equal(warm.cacheHit, true, "valid warm full caching remains available");
    assertLoaded(warm.result);
  } else {
    assert.equal(newFull.result.time.duration.status, "data_unavailable");
    assert.equal(newFull.result.time.timeOfDay.status, "data_unavailable");
    assert.equal(newFull.result.sourcesQuality.witnessCount.status, "data_unavailable");
  }
}

assert.match(workerSource, /projectionReadiness:\s*\{/);
const oldCacheIdentity = workerSource.replace(/      projectionReadiness: \{[\s\S]*?\r?\n      \},\r?\n/, "");
assert.notEqual(oldCacheIdentity, workerSource);
await runRace(oldCacheIdentity, false); // Demonstrates the reported defect.
await runRace(workerSource, true);       // Exercises the actual repaired runtime.
console.log("Actual worker late-Spatial cache race reproduced; repaired full retains all three loaded projections and warm caching");

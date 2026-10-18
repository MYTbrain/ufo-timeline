import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

const source = readFileSync(new URL("../app.js", import.meta.url), "utf8").replace(/\r\n/g, "\n");
function actualFunction(name) {
  const start = source.search(new RegExp("^  (?:async )?function " + name + "\\(", "m"));
  assert.ok(start >= 0, "Actual app function exists: " + name);
  const next = source.slice(start + 1).search(/\n  (?:async )?function \w+\(/);
  assert.ok(next >= 0, "Actual function has a following boundary: " + name);
  return source.slice(start, start + next + 1).trim();
}
function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
const flush = async () => { for (let index = 0; index < 40; index += 1) await Promise.resolve(); };
function fixture(count = 8) {
  const fetched = [], ingested = [], released = [], requests = new Map(), firstIngest = deferred();
  const manifest = Array.from({ length: count }, (_, index) => ({ id: "summary_" + index, file: "summary_" + index + ".json" }));
  const runtime = { canonicalWebArtifacts: { status: "ready", summaryManifest: manifest,
    summaryShardCache: new Map(), urls: { summaryManifest: "https://data.invalid/summary_manifest.json" } },
    catalogSummaryMemory: { summaryShardCachesReleased: 0 } };
  const startup = { fetchedCatalogShards: 0, loadedCatalogShards: 0, ingestedCatalogShards: 0 };
  const loadedChunkPromises = new Map();
  const context = vm.createContext({ runtime, startup, loadedChunkPromises,
    performance: { now: () => 0 },
    PACKED_POINTS_STATUS: { READY: "ready" }, STARTUP_CATALOG_SHARD_CONCURRENCY: 4,
    STARTUP_PROGRESS: { loadingCatalogStart: 20, loadingCatalogEnd: 40, buildingCatalogStart: 40, buildingCatalogEnd: 80 },
    canonicalWebArtifactSummaryShardUrl: entry => "https://data.invalid/" + entry.file,
    fetchJsonPreferGzipWithRetry: async (url) => {
      const index = Number(/summary_(\d+)/.exec(url)[1]);
      const pending = deferred();
      fetched.push(index); requests.set(index, pending); return pending.promise;
    },
    createStartupError: message => new Error(message), recordStartupDecision() {},
    formatNumber: value => String(value), interpolateProgress: () => 50, setStartupPhase() {}, updateCatalogLoadingMessage() {},
    ingestCatalogShardProgressively: async rows => { const index = rows[0].index; ingested.push(index); if (index === 0) await firstIngest.promise; },
    releaseCanonicalSummaryStringPool() {}, waitForNextFrame: async () => {},
  });
  for (const name of ["canonicalSummaryShardManifestEntry", "ensureCanonicalSummaryShardLoaded", "releaseCanonicalSummaryShardCacheEntry",
    "loadAndIngestCanonicalSummaryShards"]) vm.runInContext(actualFunction(name), context);
  const realRelease = context.releaseCanonicalSummaryShardCacheEntry;
  context.releaseCanonicalSummaryShardCacheEntry = index => { released.push(index); return realRelease(index); };
  return { context, runtime, startup, loadedChunkPromises, fetched, ingested, released, requests, firstIngest };
}

// Priming the next four shards is network work only: hydration still waits for
// the application to call the ordered ingestion pipeline after the map gate.
const primed = fixture();
const earlyFirst = primed.context.ensureCanonicalSummaryShardLoaded(0);
const sameFirst = primed.context.ensureCanonicalSummaryShardLoaded("summary_0");
await flush();
assert.deepEqual(primed.fetched, [0], "Concurrent callers share one source request");
assert.deepEqual(primed.ingested, [], "Prefetching cannot hydrate or mutate the live catalog");
const pipeline = primed.context.loadAndIngestCanonicalSummaryShards();
await flush();
assert.deepEqual(primed.fetched, [0, 1, 2, 3], "The ordered pipeline reuses its prestarted request within a four-shard window");
for (const index of [3, 1, 2]) primed.requests.get(index).resolve([{ index }]);
await flush();
assert.deepEqual(primed.ingested, [], "Out-of-order downloads cannot alter catalog ordering");
assert.equal(primed.fetched.length, 4, "A late first shard cannot cause an unbounded prefetch queue");
const firstRows = [{ index: 0 }];
primed.requests.get(0).resolve(firstRows);
assert.equal(await earlyFirst, firstRows);
assert.equal(await sameFirst, firstRows);
await flush();
assert.deepEqual(primed.ingested, [0]);
assert.equal(primed.fetched.length, 5, "The next download starts during hydration: four pending shards plus one active consumer");
assert.deepEqual(primed.fetched, [0, 1, 2, 3, 4]);
assert.equal(primed.runtime.canonicalWebArtifacts.summaryShardCache.size, 4);
primed.firstIngest.resolve();
await flush();
assert.deepEqual(primed.ingested, [0, 1, 2, 3]);
assert.deepEqual(primed.fetched, [0, 1, 2, 3, 4, 5, 6, 7]);
for (const index of [7, 5, 6, 4]) primed.requests.get(index).resolve([{ index }]);
await pipeline;
assert.deepEqual(primed.ingested, [0, 1, 2, 3, 4, 5, 6, 7]);
assert.deepEqual(primed.released, primed.ingested, "Every consumed decoded shard is released in place");
assert.equal(primed.runtime.canonicalWebArtifacts.summaryShardCache.size, 0);
assert.equal(primed.loadedChunkPromises.size, 0);
assert.equal(primed.startup.ingestedCatalogShards, 8);
assert.equal(primed.runtime.catalogSummaryMemory.summaryShardCachesReleased, 8);

const cached = fixture();
const cacheLoad = cached.context.ensureCanonicalSummaryShardLoaded(2);
const cachedRows = [{ index: 2 }]; cached.requests.get(2).resolve(cachedRows); await cacheLoad;
assert.equal(await cached.context.ensureCanonicalSummaryShardLoaded(2), cachedRows);
assert.equal(cached.fetched.length, 1, "A decoded prefetched shard is reused without another download or parse");
assert.equal(cached.context.releaseCanonicalSummaryShardCacheEntry(2), true);
assert.equal(cached.runtime.canonicalWebArtifacts.summaryShardCache.size, 0);

const retry = fixture();
const failure = new Error("Transient summary request failure");
const failed = retry.context.ensureCanonicalSummaryShardLoaded(1);
retry.requests.get(1).reject(failure);
await assert.rejects(failed, error => error === failure);
assert.equal(retry.loadedChunkPromises.size, 0, "Failed requests do not poison the single-flight cache");
assert.equal(retry.runtime.canonicalWebArtifacts.summaryShardCache.size, 0);
const recovered = retry.context.ensureCanonicalSummaryShardLoaded(1);
retry.requests.get(1).resolve([{ index: 1 }]);
assert.deepEqual(Array.from(await recovered, row => row.index), [1]);
assert.deepEqual(retry.fetched, [1, 1], "A later attempt can recover the failed shard");
await assert.rejects(retry.context.ensureCanonicalSummaryShardLoaded("missing"), /Missing canonical web summary shard/);

console.log("Actual catalog prefetch is single-flight, non-hydrating, bounded to four pending shards plus one active consumer, ordered on ingestion, releasable, and recoverable after request failures.");

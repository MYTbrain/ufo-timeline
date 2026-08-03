import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import { createHash, webcrypto } from "node:crypto";

function loadWorker(workerPath, contextOverrides = {}) {
  const messages = [];
  const { self: selfOverrides = {}, ...globalOverrides } = contextOverrides;
  const self = {
    postMessage(message) {
      messages.push(message);
    },
  };
  Object.assign(self, selfOverrides);
  const context = vm.createContext({
    Array, Boolean, JSON, Map, Math, Number, Object, Set, String, console, self,
    ...globalOverrides,
  });
  vm.runInContext(
    fs.readFileSync("webapp/static_public/analysis_stats.js", "utf8"),
    context,
    { filename: "webapp/static_public/analysis_stats.js" }
  );
  vm.runInContext(
    fs.readFileSync("webapp/static_public/analysis_spatial.js", "utf8"),
    context,
    { filename: "webapp/static_public/analysis_spatial.js" }
  );
  vm.runInContext(fs.readFileSync(workerPath, "utf8"), context, { filename: workerPath });
  assert.equal(typeof self.onmessage, "function");
  return {
    send(message) {
      messages.length = 0;
      self.onmessage({ data: message });
      assert.equal(messages.length, 1);
      return JSON.parse(JSON.stringify(messages[0]));
    },
    async sendAsync(message) {
      messages.length = 0;
      self.onmessage({ data: message });
      for (let attempt = 0; attempt < 100 && messages.length === 0; attempt += 1) {
        await new Promise((resolve) => setTimeout(resolve, 5));
      }
      assert.equal(messages.length, 1);
      return JSON.parse(JSON.stringify(messages[0]));
    },
  };
}

function extractNamedFunctionSource(source, name) {
  const start = source.indexOf(`function ${name}(`);
  assert.notEqual(start, -1, `missing function ${name}`);
  const openingBrace = source.indexOf("{", start);
  let depth = 0;
  for (let index = openingBrace; index < source.length; index += 1) {
    if (source[index] === "{") depth += 1;
    if (source[index] === "}") {
      depth -= 1;
      if (depth === 0) return source.slice(start, index + 1);
    }
  }
  assert.fail(`unterminated function ${name}`);
}

function loadNamedFunction(source, name, contextOverrides = {}) {
  const context = vm.createContext({
    Array, Boolean, JSON, Map, Math, Number, Object, Set, String,
    ...contextOverrides,
  });
  vm.runInContext(`${extractNamedFunctionSource(source, name)}\nthis.__functionUnderTest = ${name};`, context);
  return { context, fn: context.__functionUnderTest };
}

const lowPrecisionValues = [
  "country",
  "state",
  "province",
  "state_province",
  "region",
  "county",
  "approximate",
  "multi_location",
  "unknown",
];

const APP_DAY_1955_08_20 = -5248;
const appUnixDay = (year, month, day) => Math.trunc(Date.UTC(year, month - 1, day) / 86400000);

const rows = [
  {
    eventId: "2606225892387599",
    source: "ufocat",
    type: "Fireball",
    visualTypeGroup: "Light / glow",
    craftType: "light",
    precision: "exact_coords",
    datePrecision: "exact_day",
    sortOrdinal: APP_DAY_1955_08_20,
    lat: 48.8566,
    lon: 2.3522,
    coordinateSource: "raw_latlong",
    craftConfidence: "high",
    craftSource: "shape_normalized",
    sameDayMatchStrength: "strong",
    country: "France",
    adminRegion: "Ile-de-France",
    mapped: true,
    shape: "Fireball",
  },
  {
    eventId: "city-event",
    source: "nuforc",
    type: "Disk",
    visualTypeGroup: "Disc / saucer",
    craftType: "disc_saucer",
    precision: "city",
    datePrecision: "exact_day",
    sortOrdinal: APP_DAY_1955_08_20,
    lat: 43.3,
    lon: 5.4,
    coordinateSource: "geocoded",
    craftConfidence: "medium",
    craftSource: "shape_normalized",
    mapped: true,
    shape: "Disk",
  },
  ...lowPrecisionValues.map((precision, index) => ({
    eventId: `low-${index}`,
    source: "fixture",
    type: "Unknown",
    visualTypeGroup: "Other / unknown",
    craftType: "unknown",
    precision,
    datePrecision: "exact_day",
    sortOrdinal: APP_DAY_1955_08_20,
    lat: null,
    lon: null,
    coordinateSource: "unresolved",
    craftConfidence: "none",
    craftSource: "none",
    mapped: false,
    shape: "Unknown",
  })),
];

const worker = loadWorker("webapp/static_public/catalog_filter_worker.js");
const added = worker.send({
  type: "addCatalogFacetRows",
  requestId: "add",
  rows,
});
assert.equal(added.type, "catalogFacetRowsAdded");
assert.equal(added.rowCount, rows.length);
assert.equal(added.storage.mode, "typed_column_chunks");
assert.equal(added.storage.rows, rows.length);
assert.equal(added.storage.typedBytes, rows.length * 75);
assert.equal(added.storage.analysisDerivedColumns, true);
assert.ok(added.storage.analysisGridKeys >= 2, "typed storage interns derived coordinate-class grid keys");
assert.equal(added.storage.analysisCoordinatePiles, 1, "only source-provided coordinates enter exact-coordinate pile accounting");
assert.ok(added.storage.dictionaries.sameDayMatchStrength >= 2);
assert.ok(added.storage.dictionaries.country >= 2);
assert.equal(added.storage.stringEventIds, rows.length);

const filters = {
  keyword: "",
  sourceMode: "all",
  typeMode: "all",
  precisionMode: "all",
  selectedSources: [],
  selectedTypes: [],
  selectedPrecisions: [],
  hideLowPrecision: true,
  hideNonExactDates: false,
};

const filtered = worker.send({
  type: "computeFilteredCatalogIds",
  requestId: "filter",
  filters,
  lowPrecisionValues,
  catalogExactDayAscending: true,
});
assert.equal(filtered.type, "filteredCatalogIdsComputed");
assert.deepEqual(filtered.result.eventIds, ["2606225892387599", "city-event"]);
assert.deepEqual(filtered.result.legendEventCounts, { light: 1, disc_saucer: 1 });
assert.equal(filtered.result.legendColorMode, "craft_type");

const isolatedDisc = worker.send({
  type: "computeFilteredCatalogIds",
  requestId: "filter-disc",
  filters: {
    ...filters,
    legendEventMode: "subset",
    legendColorMode: "craft_type",
    selectedLegendEventKeys: ["disc_saucer"],
  },
  lowPrecisionValues,
  catalogExactDayAscending: true,
});
assert.deepEqual(isolatedDisc.result.eventIds, ["city-event"]);
assert.deepEqual(
  isolatedDisc.result.legendEventCounts,
  { light: 1, disc_saucer: 1 },
  "isolating a category must not remove the other available legend choices"
);

const additiveSelection = worker.send({
  type: "computeFilteredCatalogIds",
  requestId: "filter-additive",
  filters: {
    ...filters,
    legendEventMode: "subset",
    legendColorMode: "craft_type",
    selectedLegendEventKeys: ["disc_saucer", "light"],
  },
  lowPrecisionValues,
  catalogExactDayAscending: true,
});
assert.deepEqual(additiveSelection.result.eventIds, ["2606225892387599", "city-event"]);

const hiddenAll = worker.send({
  type: "computeFilteredCatalogIds",
  requestId: "filter-none",
  filters: {
    ...filters,
    legendEventMode: "none",
    legendColorMode: "craft_type",
    selectedLegendEventKeys: [],
  },
  lowPrecisionValues,
  catalogExactDayAscending: true,
});
assert.deepEqual(hiddenAll.result.eventIds, []);
assert.deepEqual(hiddenAll.result.legendEventCounts, { light: 1, disc_saucer: 1 });

const facets = worker.send({
  type: "computeCatalogFacetCounts",
  requestId: "facets",
  filters,
  lowPrecisionValues,
  timeRangeStartOrdinal: APP_DAY_1955_08_20,
  timeRangeEndOrdinal: APP_DAY_1955_08_20,
});
assert.equal(facets.type, "catalogFacetCountsComputed");
assert.deepEqual(facets.result.precision, { exact_coords: 1, city: 1 });
assert.deepEqual(facets.result.legendEventCounts, { light: 1, disc_saucer: 1 });
assert.equal(facets.result.legendColorMode, "craft_type");

const isolatedFacets = worker.send({
  type: "computeCatalogFacetCounts",
  requestId: "facets-disc",
  filters: {
    ...filters,
    legendEventMode: "subset",
    legendColorMode: "craft_type",
    selectedLegendEventKeys: ["disc_saucer"],
  },
  lowPrecisionValues,
  timeRangeStartOrdinal: APP_DAY_1955_08_20,
  timeRangeEndOrdinal: APP_DAY_1955_08_20,
});
assert.deepEqual(isolatedFacets.result.type, { Disk: 1 });
assert.deepEqual(isolatedFacets.result.precision, { city: 1 });
assert.deepEqual(
  isolatedFacets.result.legendEventCounts,
  { light: 1, disc_saucer: 1 },
  "facet refreshes must retain legend choices outside the selected subset"
);

const numericWorker = loadWorker("webapp/static_public/catalog_filter_worker.js");
const numericAdded = numericWorker.send({
  type: "addCatalogFacetRows",
  requestId: "numeric-add",
  rows: [{
    eventId: 2606225892387599,
    source: "ufocat",
    type: "Fireball",
    visualTypeGroup: "Light / glow",
    craftType: "light",
    precision: "exact_coords",
    datePrecision: "exact_day",
    sortOrdinal: APP_DAY_1955_08_20,
  }],
});
assert.equal(numericAdded.storage.stringEventIds, 0);
assert.equal(numericAdded.storage.typedBytes, 75);
const numericFiltered = numericWorker.send({
  type: "computeFilteredCatalogIds",
  requestId: "numeric-filter",
  filters: { ...filters, hideLowPrecision: false },
  lowPrecisionValues,
  catalogExactDayAscending: true,
});
assert.deepEqual(numericFiltered.result.eventIds, [2606225892387599]);

const analysis = worker.send({
  type: "computeAnalysis",
  requestId: "analysis",
  analysisSignature: "fixture-analysis-signature",
  filterGeneration: 17,
  baselineMode: "other_dates_matched",
  datasetHash: "fixture-sha256",
  contextReleaseHashes: { cropCircles: "crop-v1" },
  selectedDomains: ["overview", "time", "craft", "geography", "sources_quality"],
  filters: { ...filters, hideLowPrecision: false },
  lowPrecisionValues,
  timeRangeStartOrdinal: APP_DAY_1955_08_20,
  timeRangeEndOrdinal: APP_DAY_1955_08_20,
});
assert.equal(analysis.type, "analysisComputed");
assert.equal(analysis.requestId, "analysis");
assert.equal(analysis.analysisSignature, "fixture-analysis-signature");
assert.equal(analysis.filterGeneration, 17);
assert.equal(analysis.generation, 17);
assert.equal(analysis.baselineMode, "other_dates_balanced");
assert.deepEqual(analysis.contextReleaseHashes, { cropCircles: "crop-v1" });
assert.equal(analysis.result.summary.activeCount, rows.length);
assert.equal(analysis.result.summary.referenceCount, 0);
assert.equal(analysis.result.summary.datasetHash, "fixture-sha256");
assert.equal(analysis.ordinalEpoch, "unix_day");
assert.equal(analysis.result.ordinalEpoch, "unix_day");
assert.equal(analysis.result.time.series.find((datum) => datum.year === 1955).observed, rows.length);
assert.equal(analysis.result.overview.active.sourceCoordinates, 1);
assert.equal(analysis.result.overview.active.generalizedCoordinates, 1);
assert.equal(analysis.result.overview.active.unmapped, lowPrecisionValues.length);

const quickAnalysis = worker.send({
  type: "computeAnalysis",
  requestId: "analysis-quick",
  analysisSignature: "fixture-analysis-signature",
  filterGeneration: 17,
  baselineMode: "other_dates_matched",
  analysisPhase: "quick",
  quickMode: true,
  datasetHash: "fixture-sha256",
  contextReleaseHashes: { cropCircles: "crop-v1" },
  selectedDomains: ["overview", "time", "sources_quality", "context"],
  filters: { ...filters, hideLowPrecision: false },
  lowPrecisionValues,
  timeRangeStartOrdinal: APP_DAY_1955_08_20,
  timeRangeEndOrdinal: APP_DAY_1955_08_20,
});
assert.equal(quickAnalysis.type, "analysisComputed");
assert.equal(quickAnalysis.analysisPhase, "quick");
assert.equal(quickAnalysis.quickMode, true);
assert.equal(quickAnalysis.inferenceDeferred, true);
assert.equal(quickAnalysis.result.inference.status, "deferred");
assert.deepEqual(quickAnalysis.result.patterns, []);
assert.ok(Object.values(quickAnalysis.result.comparisons).every((family) => (
  family.results.length === 0 && family.metadata.bootstrapReplicates === 0
)));

const cachedAnalysis = worker.send({
  type: "computeAnalysis",
  requestId: "analysis-cached",
  filterGeneration: 17,
  baselineMode: "other_dates_matched",
  datasetHash: "fixture-sha256",
  contextReleaseHashes: { cropCircles: "crop-v1" },
  selectedDomains: ["overview", "time", "craft", "geography", "sources_quality"],
  filters: { ...filters, hideLowPrecision: false },
  lowPrecisionValues,
  timeRangeStartOrdinal: APP_DAY_1955_08_20,
  timeRangeEndOrdinal: APP_DAY_1955_08_20,
});
assert.equal(cachedAnalysis.cacheHit, true);

const warmDateAnalysis = worker.send({
  type: "computeAnalysis",
  requestId: "analysis-warm-date",
  filterGeneration: 18,
  baselineMode: "other_dates_matched",
  datasetHash: "fixture-sha256",
  contextReleaseHashes: { cropCircles: "crop-v1" },
  selectedDomains: ["overview", "time", "craft", "geography", "sources_quality"],
  filters: { ...filters, hideLowPrecision: false },
  lowPrecisionValues,
  timeRangeStartOrdinal: APP_DAY_1955_08_20 - 1,
  timeRangeEndOrdinal: APP_DAY_1955_08_20 - 1,
});
assert.equal(warmDateAnalysis.cacheHit, false);
assert.equal(warmDateAnalysis.result.summary.activeCount, 0);
assert.equal(warmDateAnalysis.result.summary.referenceCount, rows.length);
const matchedCacheStorage = worker.send({
  type: "addCatalogFacetRows",
  requestId: "analysis-match-cache-storage",
  generation: 18,
  rows: [],
});
assert.equal(matchedCacheStorage.storage.analysisMatchCacheEntries, 1, "date-only recomputes reuse one non-date match index");

const areaAnalysis = worker.send({
  type: "computeAnalysis",
  requestId: "analysis-area",
  filterGeneration: 18,
  baselineMode: "other_dates_matched",
  datasetHash: "fixture-sha256",
  filters: { ...filters, hideLowPrecision: false },
  lowPrecisionValues,
  areaFilterShapes: [{
    type: "rectangle",
    bounds: { north: 50, south: 48, east: 3, west: 1 },
  }],
  timeRangeStartOrdinal: APP_DAY_1955_08_20,
  timeRangeEndOrdinal: APP_DAY_1955_08_20,
});
assert.equal(areaAnalysis.result.summary.activeCount, 1);
assert.equal(areaAnalysis.result.craft.distribution[0].key, "light");

const inactiveAreaAnalysis = worker.send({
  type: "computeAnalysis",
  requestId: "analysis-empty-area-array",
  filterGeneration: 19,
  baselineMode: "other_dates_matched",
  datasetHash: "fixture-sha256",
  filters: { ...filters, hideLowPrecision: false },
  lowPrecisionValues,
  areaFilterShapes: [],
  timeRangeStartOrdinal: APP_DAY_1955_08_20,
  timeRangeEndOrdinal: APP_DAY_1955_08_20,
});
assert.equal(inactiveAreaAnalysis.result.summary.activeCount, rows.length, "an inactive empty shape list must not hide every point");

const contextSet = worker.send({
  type: "setAnalysisContextProjections",
  requestId: "context",
  filterGeneration: 17,
  contextReleaseHashes: { cropCircles: "crop-v1", animalReports: "animal-v1" },
  manifest: {
    codes: {
      datePrecision: ["unknown", "exact_day"],
      morphologyFamily: ["unknown", "circular"],
      complexityTier: ["unknown", "simple"],
      coordinateClass: ["unknown", "source_coordinates"],
      speciesGroup: ["unknown", "cattle"],
      status: ["unknown", "reviewed"],
    },
    dictionaries: { country: ["unknown", "FR"], cropType: ["unknown", "wheat"] },
  },
  projections: {
    cropCircles: { rows: [["crop-1", 1954, 1954, 1, 1, 1, [1], [1], 1, true, true, false]] },
    animalReports: { rows: [["animal-1", 1954, 1954, 1, [1], false, 1]] },
  },
});
assert.equal(contextSet.type, "analysisContextProjectionsSet");
assert.deepEqual(contextSet.rowCounts, { cropCircles: 1, animalReports: 1 });

const contextAnalysis = worker.send({
  type: "computeAnalysis",
  requestId: "context-analysis",
  filterGeneration: 18,
  baselineMode: "other_dates_matched",
  datasetHash: "fixture-sha256",
  contextReleaseHashes: { cropCircles: "crop-v1", animalReports: "animal-v1" },
  contextLayers: { cropCirclesEnabled: true, animalMutilationsEnabled: true },
  filters: { ...filters, hideLowPrecision: false },
  lowPrecisionValues,
  timeRangeStartOrdinal: appUnixDay(1954, 12, 31),
  timeRangeEndOrdinal: appUnixDay(1955, 12, 30),
});
assert.equal(contextAnalysis.result.context.crops.status, "ready");
assert.equal(contextAnalysis.result.context.crops.morphology[0].label, "circular");
assert.equal(contextAnalysis.result.context.animals.status, "ready");
assert.equal(contextAnalysis.result.context.animals.species[0].label, "cattle");

const ordinalWorker = loadWorker("webapp/static_public/catalog_filter_worker.js");
const appDay2000Feb29 = appUnixDay(2000, 2, 29);
const pythonOrdinal = (appDay) => appDay + 719163;
ordinalWorker.send({
  type: "addCatalogFacetRows",
  requestId: "ordinal-catalog",
  rows: [{
    eventId: "leap-day-ufo",
    source: "fixture",
    type: "Disk",
    visualTypeGroup: "Disc / saucer",
    craftType: "disc_saucer",
    shape: "Disk",
    craftConfidence: "high",
    craftSource: "shape_normalized",
    precision: "exact_coords",
    datePrecision: "exact_day",
    coordinateSource: "raw_latlong",
    sortOrdinal: appDay2000Feb29,
    lat: 40,
    lon: -100,
    mapped: true,
  }],
});
const ordinalContext = ordinalWorker.send({
  type: "setAnalysisContextProjections",
  requestId: "ordinal-context",
  filterGeneration: 100,
  manifest: {
    codes: {
      datePrecision: ["unknown", "exact_day", "month", "year"],
      morphologyFamily: ["unknown"],
      complexityTier: ["unknown"],
      coordinateClass: ["unknown"],
    },
    dictionaries: { country: ["unknown"], cropType: ["unknown"] },
  },
  projections: {
    cropCircles: { rows: [
      ["context-exact", 2000, 2000, 1, 0, 0, [], [], 0, false, false, false, pythonOrdinal(appDay2000Feb29), pythonOrdinal(appDay2000Feb29)],
      ["context-month", 2000, 2000, 2, 0, 0, [], [], 0, false, false, false, pythonOrdinal(appUnixDay(2000, 2, 1)), pythonOrdinal(appDay2000Feb29)],
      ["context-year", 2000, 2000, 3, 0, 0, [], [], 0, false, false, false, pythonOrdinal(appUnixDay(2000, 1, 1)), pythonOrdinal(appUnixDay(2000, 12, 31))],
    ] },
  },
});
assert.equal(ordinalContext.rowCounts.cropCircles, 3);

function computeOrdinalWindow(requestId, generation, startOrdinal, endOrdinal) {
  return ordinalWorker.send({
    type: "computeAnalysis",
    requestId,
    filterGeneration: generation,
    baselineMode: "other_dates_matched",
    datasetHash: "ordinal-fixture-sha256",
    contextLayers: { cropCirclesEnabled: true, animalMutilationsEnabled: false },
    filters: { ...filters, hideLowPrecision: false },
    lowPrecisionValues,
    timeRangeStartOrdinal: startOrdinal,
    timeRangeEndOrdinal: endOrdinal,
  });
}

const exactOrdinalAnalysis = computeOrdinalWindow("ordinal-exact", 101, appDay2000Feb29, appDay2000Feb29);
assert.equal(exactOrdinalAnalysis.ordinalEpoch, "unix_day");
assert.equal(exactOrdinalAnalysis.result.summary.activeCount, 1);
assert.equal(exactOrdinalAnalysis.result.time.series.find((datum) => datum.year === 2000).observed, 1);
assert.equal(exactOrdinalAnalysis.result.context.crops.activeCount, 3, "exact day must overlap exact-, month-, and year-precision context intervals");
assert.deepEqual(exactOrdinalAnalysis.result.baseline.activeRange, {
  start: appDay2000Feb29,
  end: appDay2000Feb29,
});
const year2000Preview = exactOrdinalAnalysis.result.time.series.find((datum) => datum.year === 2000).preview.patch.dateRange;
assert.deepEqual(year2000Preview, {
  startOrdinal: appUnixDay(2000, 1, 1),
  endOrdinal: appUnixDay(2000, 12, 31),
}, "analysis drill-down previews must return to the app's Unix-day epoch");
const februaryPreview = exactOrdinalAnalysis.result.time.monthYear.find((datum) => datum.year === 2000 && datum.month === 2).preview.patch.dateRange;
assert.deepEqual(februaryPreview, {
  startOrdinal: appUnixDay(2000, 2, 1),
  endOrdinal: appDay2000Feb29,
});

const monthOrdinalAnalysis = computeOrdinalWindow("ordinal-month", 102, appUnixDay(2000, 2, 1), appUnixDay(2000, 2, 1));
assert.equal(monthOrdinalAnalysis.result.context.crops.activeCount, 2, "a February day must overlap month- and year-precision context intervals only");
const yearOrdinalAnalysis = computeOrdinalWindow("ordinal-year", 103, appUnixDay(2000, 3, 15), appUnixDay(2000, 3, 15));
assert.equal(yearOrdinalAnalysis.result.context.crops.activeCount, 1, "a March day must overlap only the year-precision context interval");

const previewRoundTrip = computeOrdinalWindow(
  "ordinal-preview-round-trip",
  104,
  year2000Preview.startOrdinal,
  year2000Preview.endOrdinal
);
assert.equal(previewRoundTrip.result.summary.activeCount, 1, "a returned analysis preview must round-trip through the worker boundary without changing calendar dates");
assert.equal(previewRoundTrip.result.time.series.find((datum) => datum.year === 2000).observed, 1);

const projectionText = JSON.stringify({ rows: [["crop-url", 1954, 1954, 1, 1, 1, [1], [1], 1, true, true, true]] });
const projectionHash = createHash("sha256").update(projectionText).digest("hex");
const urlWorker = loadWorker("webapp/static_public/catalog_filter_worker.js", {
  DecompressionStream,
  Response,
  TextDecoder,
  URL,
  fetch: async () => new Response(projectionText, { status: 200 }),
  self: { crypto: webcrypto, location: { href: "https://example.test/catalog_filter_worker.js" } },
});
const urlContext = await urlWorker.sendAsync({
  type: "setAnalysisContextProjections",
  requestId: "url-context",
  filterGeneration: 2,
  manifest: {
    artifacts: {
      cropCircles: { file: "data/analysis_v1/crop_circles.json", sha256: projectionHash },
    },
    codes: { datePrecision: ["unknown", "year"], morphologyFamily: ["unknown", "circle"], complexityTier: ["unknown", "simple"], coordinateClass: ["unknown", "source_coordinates"] },
    dictionaries: { country: ["unknown", "FR"], cropType: ["unknown", "wheat"] },
  },
  urls: { cropCircles: "https://example.test/data/analysis_v1/crop_circles.json" },
});
assert.equal(urlContext.type, "analysisContextProjectionsSet");
assert.equal(urlContext.rowCounts.cropCircles, 1);

const mismatchWorker = loadWorker("webapp/static_public/catalog_filter_worker.js", {
  DecompressionStream,
  Response,
  TextDecoder,
  URL,
  fetch: async () => new Response(projectionText, { status: 200 }),
  self: { crypto: webcrypto, location: { href: "https://example.test/catalog_filter_worker.js" } },
});
const mismatch = await mismatchWorker.sendAsync({
  type: "setAnalysisContextProjections",
  requestId: "url-context-mismatch",
  filterGeneration: 3,
  manifest: { artifacts: { cropCircles: { file: "crop.json", sha256: "0".repeat(64) } } },
  urls: { cropCircles: "https://example.test/crop.json" },
});
assert.equal(mismatch.type, "catalogFacetWorkerError");
assert.match(mismatch.error, /SHA-256 mismatch/);

const analysisV2Manifest = JSON.parse(fs.readFileSync("webapp/static_public/data/analysis_v2/manifest.json", "utf8"));
const spatialFetch = async (urlValue) => {
  const url = new URL(String(urlValue), "https://example.test/");
  const relative = decodeURIComponent(url.pathname).replace(/^\//, "");
  const path = relative.startsWith("data/") ? "webapp/static_public/" + relative : relative;
  if (!fs.existsSync(path)) return new Response("not found", { status: 404 });
  return new Response(fs.readFileSync(path), { status: 200 });
};
const spatialWorker = loadWorker("webapp/static_public/catalog_filter_worker.js", {
  Response,
  TextDecoder,
  URL,
  fetch: spatialFetch,
  self: { crypto: webcrypto, location: { href: "https://example.test/catalog_filter_worker.js" } },
});
const spatialArtifactSetup = await spatialWorker.sendAsync({
  type: "setAnalysisSpatialArtifacts",
  requestId: "spatial-artifacts",
  filterGeneration: 31,
  cancellationGeneration: 7,
  manifest: analysisV2Manifest,
  urls: { manifest: "https://example.test/data/analysis_v2/manifest.json" },
});
assert.equal(spatialArtifactSetup.type, "analysisSpatialArtifactsSet");
assert.equal(spatialArtifactSetup.cancellationGeneration, 7);
assert.equal(spatialArtifactSetup.snapshot.rowCounts.neighbors, 42_575);
assert.equal(spatialArtifactSetup.snapshot.rowCounts.facilities, 1_800);
assert.equal(spatialArtifactSetup.snapshot.rowCounts.relationships, 1_804);
assert.equal(spatialArtifactSetup.snapshot.releaseId, "analysis-evidence-lab-v2-20260803");
assert.equal(spatialArtifactSetup.snapshot.artifactHashes.ufoPointNeighbors, analysisV2Manifest.artifacts.ufoPointNeighbors.sha256);
assert.deepEqual(spatialArtifactSetup.snapshot.relationshipReadiness, {
  key: "relationshipReconciliation",
  label: "Cross-domain relationship reconciliation",
  status: "not_estimable",
  eligibleN: 0,
  totalN: 1_804,
  minimumEligibleN: 25,
  inferenceEnabled: false,
  reasons: [
    "animal_exact_coordinate_contract_unavailable",
    "relationships_not_analyst_adjudicated_for_inference",
    "unresolved_subjects_and_objects_remain_quarantined",
  ],
  releaseHash: analysisV2Manifest.artifacts.relationshipReconciliation.sha256,
  explicitSourceN: 67,
  computedCandidateN: 1_737,
  analystReviewedN: 0,
  quarantinedSubjectN: 460,
  quarantinedObjectN: 24,
  reconciledN: 1_320,
  reconciledCurrentN: 1_069,
  reconciledUnmappedUfoN: 251,
  associationEligibleN: 0,
});

const firstNeighbor = JSON.parse(fs.readFileSync("webapp/static_public/data/analysis_v2/ufo_point_neighbors_v1.json", "utf8"))[0];
const spatialFixtureRows = [
  { eventId: String(firstNeighbor[0]), source: "ufocat", craftType: "triangle", lat: 35, lon: -117 },
  { eventId: String(firstNeighbor[1]), source: "majestic", craftType: "disc_saucer", lat: 35.01, lon: -117.01 },
  { eventId: "spatial-extra-a", source: "ufocat", craftType: "disc_saucer", lat: 35.02, lon: -117.02 },
  { eventId: "spatial-extra-b", source: "majestic", craftType: "triangle", lat: 35.03, lon: -117.03 },
].map((row) => ({
  ...row,
  type: row.craftType,
  visualTypeGroup: row.craftType,
  precision: "exact_coords",
  datePrecision: "exact_day",
  sortOrdinal: APP_DAY_1955_08_20,
  coordinateSource: "raw_latlong",
  craftConfidence: "high",
  craftSource: "shape_normalized",
  sameDayMatchStrength: "strong",
  country: "US",
  adminRegion: "CA",
  mapped: true,
  shape: row.craftType,
}));
spatialWorker.send({ type: "addCatalogFacetRows", requestId: "spatial-rows", rows: spatialFixtureRows });
const spatialComputed = spatialWorker.send({
  type: "computeAnalysis",
  requestId: "spatial-compute",
  analysisSignature: "spatial-signature",
  filterGeneration: 31,
  cancellationGeneration: 8,
  baselineMode: "other_dates_balanced",
  datasetHash: "spatial-fixture",
  selectedDomains: ["overview", "spatial"],
  filters: { ...filters, hideLowPrecision: false },
  lowPrecisionValues,
  timeRangeStartOrdinal: APP_DAY_1955_08_20,
  timeRangeEndOrdinal: APP_DAY_1955_08_20,
  spatialPermutationCount: 3,
  spatialBootstrapCount: 3,
  spatialMinimumStratumSize: 2,
});
assert.equal(spatialComputed.type, "analysisComputed");
assert.equal(spatialComputed.cancellationGeneration, 8);
assert.equal(spatialComputed.result.spatialEvidence.traceInputsRead, false);
assert.equal(spatialComputed.result.spatialEvidence.cooccurrence.crossSource.length, 3);
assert.equal(spatialComputed.result.spatialEvidence.cooccurrence.sameSource.length, 3);
assert.equal(spatialComputed.result.spatialEvidence.readiness.find((row) => row.key === "cropCircles").status, "not_estimable");
assert.equal(spatialComputed.result.spatialEvidence.readiness.find((row) => row.key === "animalReports").status, "not_estimable");
assert.deepEqual(
  spatialComputed.result.spatialEvidence.readiness.find((row) => row.key === "relationshipReconciliation"),
  spatialArtifactSetup.snapshot.relationshipReadiness,
  "decoded relationship lanes and quarantine counts must reach the runtime readiness payload"
);

const fullCatalogSpatial = spatialWorker.send({
  type: "computeAnalysis",
  requestId: "spatial-full-catalog",
  filterGeneration: 32,
  cancellationGeneration: 9,
  baselineMode: "full_catalog",
  datasetHash: "spatial-fixture",
  selectedDomains: ["overview", "spatial"],
  filters: { ...filters, hideLowPrecision: false },
  lowPrecisionValues,
  timeRangeStartOrdinal: APP_DAY_1955_08_20,
  timeRangeEndOrdinal: APP_DAY_1955_08_20,
  spatialPermutationCount: 3,
  spatialBootstrapCount: 3,
  spatialMinimumStratumSize: 2,
});
assert.equal(fullCatalogSpatial.baselineMode, "full_catalog");
assert.equal(fullCatalogSpatial.result.spatialEvidence.baselineMode, "full_catalog");
assert.equal(fullCatalogSpatial.result.spatialEvidence.inferenceEnabled, false);
assert.ok(fullCatalogSpatial.result.spatialEvidence.suppressionReasons.includes("full_catalog_overlap_descriptive_no_inference"));
for (const lane of [
  ...fullCatalogSpatial.result.spatialEvidence.cooccurrence.crossSource,
  ...fullCatalogSpatial.result.spatialEvidence.cooccurrence.sameSource,
]) {
  assert.equal(lane.status, "descriptive_only");
  assert.equal(lane.permutationCount, 3);
  assert.equal(lane.bootstrapCount, 3);
  for (const cell of lane.cells) {
    assert.equal(cell.pValue, null);
    assert.equal(cell.qValue, null);
    assert.equal(cell.patternFinderEligible, false);
  }
}
assert.equal(fullCatalogSpatial.result.spatialEvidence.facility.status, "descriptive_only");

// App-level Analysis regression fixtures. These load the exact production
// functions without evaluating the DOM-heavy application bootstrap.
const appSource = fs.readFileSync("webapp/static_public/app.js", "utf8");
const pointSeedSource = extractNamedFunctionSource(appSource, "currentPointOnlyRegionSelectionSeeds");
for (const prohibited of ["currentChronologicalNeighborhoodIndex", "currentChronologicalNeighborhoodSeeds", "TRACE_NEIGHBORHOOD", "segment"]) {
  assert.equal(pointSeedSource.includes(prohibited), false, `point-only seed path must not use ${prohibited}`);
}
const pointSeedRuntime = {
  activeFilterGeneration: 41,
  neighborhoodSeedCacheKey: "",
  neighborhoodSeedCacheValue: null,
};
const pointSeedState = {
  filterGeneration: 41,
  timelineDataVersion: 9,
  timeRangeStartOrdinal: 0,
  timeRangeEndOrdinal: 100,
  filteredMappedCatalog: [
    { event_id: "inside-point", lat: 10, lon: 10 },
    { event_id: "outside-chronology-neighbor", lat: 20, lon: 20 },
    { event_id: "invalid-point", lat: null, lon: null },
  ],
};
const pointSeedFixture = loadNamedFunction(appSource, "currentPointOnlyRegionSelectionSeeds", {
  runtime: pointSeedRuntime,
  state: pointSeedState,
  catalogEventIdIdentityKey: () => "fixture-catalog",
  regionSelectionShapesSignature: () => "fixture-shape",
  pointMayIntersectAnyRegionShape: () => true,
  regionIdsForPoint: (event) => event.lat === 10 ? ["area-a"] : [],
});
const pointSeeds = pointSeedFixture.fn(
  [{ id: "area-a", type: "rectangle" }],
  [{ north: 11, south: 9, east: 11, west: 9 }]
);
assert.deepEqual(
  JSON.parse(JSON.stringify(pointSeeds.eventSeeds)),
  [{ eventId: "inside-point", regionIds: ["area-a"] }],
  "point-only Analysis areas must exclude an out-of-bounds chronology neighbor"
);
assert.deepEqual(JSON.parse(JSON.stringify(pointSeeds.traceSeeds)), []);
assert.equal(pointSeeds.candidateEventCount, 2, "invalid or unmapped coordinates must not enter the point-only candidate set");
assert.equal(pointSeeds.candidateTraceCount, 0);
assert.equal(pointSeeds.source, "mapped_report_points_only");

const signatureRuntime = { analysisContextManifest: {} };
const signatureFixture = loadNamedFunction(appSource, "analysisComputeCacheKey", {
  runtime: signatureRuntime,
  analysisContextReleaseHashes: () => ({ cropCircles: "crop-a", animalReports: "animal-a" }),
  analysisV2ArtifactHashes: () => ({}),
  analysisCatalogDatasetHash: () => "catalog-a",
});
const baseSnapshot = {
  generation: 17,
  baselineMode: "other_dates_matched",
  timeRange: { mode: "custom", startOrdinal: 10, endOrdinal: 20 },
  filters: { keyword: "alpha", selectedSources: ["source-a"] },
  areaFilter: {
    active: true,
    pointOnly: true,
    shapes: [{ type: "rectangle", bounds: { north: 10, south: 0, east: 10, west: 0 } }],
  },
  contextLayers: { crops: { enabled: true }, animals: { enabled: false } },
  contextReleaseHashes: { cropCircles: "crop-a", animalReports: "animal-a" },
};
const signatureA = signatureFixture.fn(baseSnapshot);
const pendingA = {
  requestId: "request-a",
  generation: 17,
  baselineMode: "other_dates_matched",
  signature: signatureA,
};
const messageA = {
  requestId: "request-a",
  filterGeneration: 17,
  baselineMode: "other_dates_matched",
  analysisSignature: signatureA,
};
const envelopeFixture = loadNamedFunction(appSource, "analysisResponseEnvelopeMatchesCurrentState", {
  window: {
    UfoAnalysisView: {
      analysisRequestEnvelopeMatches(pending, message, currentSignature) {
        return Boolean(
          pending &&
          message.requestId === pending.requestId &&
          Number(message.filterGeneration) === Number(pending.generation) &&
          message.baselineMode === pending.baselineMode &&
          message.analysisSignature === pending.signature &&
          currentSignature === pending.signature
        );
      },
    },
  },
  analysisComputeCacheKey: signatureFixture.fn,
  getAnalysisFilterSnapshot: () => baseSnapshot,
});
assert.equal(envelopeFixture.fn(pendingA, messageA, baseSnapshot), true);
assert.equal(
  envelopeFixture.fn({ ...pendingA, cancellationGeneration: 4 }, { ...messageA, cancellationGeneration: 3 }, baseSnapshot),
  false,
  "a superseded cancellation generation must be rejected even when the filter signature matches"
);

const staleSnapshots = [
  { ...baseSnapshot, filters: { ...baseSnapshot.filters, keyword: "beta" } },
  { ...baseSnapshot, contextLayers: { crops: { enabled: false }, animals: { enabled: false } } },
  { ...baseSnapshot, contextReleaseHashes: { cropCircles: "crop-b", animalReports: "animal-a" } },
  { ...baseSnapshot, areaFilter: { ...baseSnapshot.areaFilter, pointOnly: false } },
  { ...baseSnapshot, areaFilter: { ...baseSnapshot.areaFilter, shapes: [{ type: "rectangle", bounds: { north: 30, south: 20, east: 30, west: 20 } }] } },
];
staleSnapshots.forEach((snapshot) => {
  assert.equal(envelopeFixture.fn(pendingA, messageA, snapshot), false);
});

let debounceCallback = null;
const signatureB = signatureFixture.fn(staleSnapshots[0]);
const pendingB = {
  requestId: "request-b",
  generation: 18,
  baselineMode: "other_dates_matched",
  signature: signatureB,
};
const messageB = {
  requestId: "request-b",
  filterGeneration: 18,
  baselineMode: "other_dates_matched",
  analysisSignature: signatureB,
};
const scheduleRuntime = { analysisPendingRequest: pendingA, analysisDebounceTimerId: 88 };
const scheduleFixture = loadNamedFunction(appSource, "scheduleAnalysisCompute", {
  state: { activeView: "analysis" },
  startup: { initialViewReady: true },
  runtime: scheduleRuntime,
  window: {
    clearTimeout() {},
    setTimeout(callback, delay) {
      assert.equal(delay, 180);
      debounceCallback = callback;
      return 89;
    },
  },
  computeAnalysisForCurrentView() {
    scheduleRuntime.analysisPendingRequest = pendingB;
  },
});
assert.equal(scheduleFixture.fn("filter changed"), true);
assert.equal(scheduleRuntime.analysisPendingRequest, null, "the old request must be invalid before the debounce elapses");
assert.equal(envelopeFixture.fn(scheduleRuntime.analysisPendingRequest, messageA, signatureA), false);
assert.equal(typeof debounceCallback, "function");
debounceCallback();
assert.equal(envelopeFixture.fn(scheduleRuntime.analysisPendingRequest, messageA, signatureB), false, "request A must remain stale after request B starts");
assert.equal(envelopeFixture.fn(scheduleRuntime.analysisPendingRequest, messageB, signatureB), true);

console.log("catalog filter worker assertions passed");

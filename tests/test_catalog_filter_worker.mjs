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
    clearMessages() {
      messages.length = 0;
    },
    dispatch(message) {
      self.onmessage({ data: message });
    },
    async waitFor(requestId) {
      for (let attempt = 0; attempt < 200; attempt += 1) {
        const index = messages.findIndex((message) => message && message.requestId === requestId);
        if (index !== -1) {
          const message = messages.splice(index, 1)[0];
          return JSON.parse(JSON.stringify(message));
        }
        await new Promise((resolve) => setTimeout(resolve, 5));
      }
      assert.fail(`worker response timed out for ${requestId}`);
    },
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
assert.equal(added.storage.typedBytes, rows.length * 138);
assert.equal(added.storage.analysisDerivedColumns, true);
assert.ok(added.storage.analysisGridKeys >= 2, "typed storage interns derived coordinate-class grid keys");
assert.equal(added.storage.analysisCoordinatePiles, 1, "only source-provided coordinates enter exact-coordinate pile accounting");
assert.ok(added.storage.dictionaries.sameDayMatchStrength >= 2);
assert.ok(added.storage.dictionaries.country >= 2);
assert.equal(added.storage.geographyProjection.loaded, false);
assert.equal(added.storage.durationProjection.loaded, false);
assert.equal(added.storage.reportingDelayProjection.loaded, false);
assert.equal(added.storage.timeOfDayProjection.loaded, false);
assert.equal(added.storage.coordinateEvidenceProjection.loaded, false);
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

const countryFiltered = worker.send({
  type: "computeFilteredCatalogIds",
  requestId: "filter-country",
  filters,
  lowPrecisionValues,
  selectedAreaCountry: "France",
  catalogExactDayAscending: true,
});
assert.deepEqual(countryFiltered.result.eventIds, ["2606225892387599"], "country Area Filter routes through the worker-owned geography assignment");

const geographyRows = [
  [0, "2606225892387599", 1, 1, 1, 1, 1, 1],
  [1, "city-event", 2, 1, 1, 1, 1, 2],
];
const geographyText = JSON.stringify(geographyRows);
const geographyHash = createHash("sha256").update(geographyText).digest("hex");
const geographyManifest = {
  schemaVersion: 2,
  manifestVersion: "2.2.0",
  schemaId: "ufo-timeline-analysis-evidence-artifacts-v2.2.0",
  releaseId: "geography-runtime-fixture-v1",
  artifacts: {
    ufoGeography: {
      file: "data/analysis_v2/ufo_geography_v1.json",
      sha256: geographyHash,
      rowCount: geographyRows.length,
      rowSchema: [
        "pointRowIndex", "eventId", "countryCode", "macroregionCode",
        "assignmentSourceCode", "assignmentConfidenceCode", "boundaryStatusCode",
        "coordinateEvidenceCode",
      ],
    },
  },
  codes: {
    ufoGeography: {
      country: ["unknown", "France", "Germany"],
      macroregion: ["unknown", "europe"],
      assignmentSource: ["unknown", "pinned_country_polygon"],
      assignmentConfidence: ["unknown", "inside_polygon"],
      boundaryStatus: ["unknown", "inside_country"],
      coordinateEvidence: ["unknown", "source_coordinates", "generalized_coordinates"],
    },
  },
};
const geographyWorker = loadWorker("webapp/static_public/catalog_filter_worker.js", {
  Response,
  TextDecoder,
  URL,
  fetch: async () => new Response(geographyText, { status: 200 }),
  self: { crypto: webcrypto, location: { href: "https://example.test/catalog_filter_worker.js" } },
});
geographyWorker.send({ type: "addCatalogFacetRows", requestId: "geography-catalog", rows });
const geographySetup = await geographyWorker.sendAsync({
  type: "setAnalysisGeographyArtifact",
  requestId: "geography-setup",
  filterGeneration: 2,
  manifest: geographyManifest,
  urls: { manifest: "https://example.test/data/analysis_v2/manifest.json" },
});
assert.equal(geographySetup.type, "analysisGeographyArtifactSet");
assert.equal(geographySetup.snapshot.appliedRows, 2);
assert.equal(geographySetup.snapshot.rowOrder, "packed_points_input_order_mapped_catalog_subsequence");
const projectedCountryFilter = geographyWorker.send({
  type: "computeFilteredCatalogIds",
  requestId: "filter-projected-country",
  filters,
  lowPrecisionValues,
  selectedAreaCountry: "Germany",
  catalogExactDayAscending: true,
});
assert.deepEqual(
  projectedCountryFilter.result.eventIds,
  ["city-event"],
  "the pinned geography projection is merged into the worker-owned catalog and drives Area Filter selection"
);

const misorderedGeographyRows = geographyRows.map((row) => row.slice());
misorderedGeographyRows[0][1] = "wrong-first-event";
const misorderedText = JSON.stringify(misorderedGeographyRows);
const misorderedManifest = structuredClone(geographyManifest);
misorderedManifest.artifacts.ufoGeography.sha256 = createHash("sha256").update(misorderedText).digest("hex");
const misorderedWorker = loadWorker("webapp/static_public/catalog_filter_worker.js", {
  Response,
  TextDecoder,
  URL,
  fetch: async () => new Response(misorderedText, { status: 200 }),
  self: { crypto: webcrypto, location: { href: "https://example.test/catalog_filter_worker.js" } },
});
misorderedWorker.send({ type: "addCatalogFacetRows", requestId: "misordered-geography-catalog", rows });
const misorderedSetup = await misorderedWorker.sendAsync({
  type: "setAnalysisGeographyArtifact",
  requestId: "misordered-geography-setup",
  filterGeneration: 3,
  manifest: misorderedManifest,
  urls: { manifest: "https://example.test/data/analysis_v2/manifest.json" },
});
assert.equal(misorderedSetup.type, "catalogFacetWorkerError");
assert.match(misorderedSetup.error, /does not match the served mapped-event order/i);

const durationStatusCodes = ["unparsed", "exact", "closed_range", "approximate", "lower_censored", "upper_censored", "ambiguous"];
const durationBinCodes = ["unknown", "under_10_seconds", "10_59_seconds", "1_4_minutes", "5_14_minutes", "15_59_minutes", "1_5_hours", "over_5_hours"];
const rawHash = (value) => createHash("sha256").update(value).digest("hex");
const durationDictionaryRows = [
  [1, rawHash("2 Minutes"), "2 Minutes", 1, 0, 120, 120, 3, 3, 1, 1],
  [2, rawHash("5"), "5", 3, 0, 300, 300, 4, 0, 2, 1],
];
const durationProjectionRows = [
  [0, "2606225892387599", 1, 1],
  [1, "city-event", 0, 1],
];
const durationDictionaryText = JSON.stringify(durationDictionaryRows);
const durationProjectionText = JSON.stringify(durationProjectionRows);
const durationManifest = {
  schemaId: "ufo-timeline-analysis-duration-artifacts-v1.0.0",
  schemaVersion: 1,
  manifestVersion: "1.0.0",
  releaseId: "analysis-duration-v1-fixture",
  artifacts: {
    durationValueDictionary: {
      file: "data/analysis_duration_v1/duration_value_dictionary_v1.json",
      sha256: rawHash(durationDictionaryText),
      gzipSha256: "a".repeat(64),
      rowCount: durationDictionaryRows.length,
      rowSchema: ["sourceCode", "rawValueSha256", "rawValue", "statusCode", "reasonCode", "lowerSeconds", "upperSeconds", "descriptiveBinCode", "inferentialBinCode", "sourceContractCode", "occurrenceCount"],
    },
    durationProjection: {
      file: "data/analysis_duration_v1/duration_projection_v1.json",
      sha256: rawHash(durationProjectionText),
      gzipSha256: "b".repeat(64),
      rowCount: durationProjectionRows.length,
      rowSchema: ["catalogRowIndex", "eventId", "valueCode", "macroregionCode"],
    },
  },
  codes: {
    source: ["unknown", "nuforc", "ufocat"],
    status: durationStatusCodes,
    reason: ["fixture"],
    durationBin: durationBinCodes,
    sourceContract: ["none", "explicit_unit_text_v1", "ufocat_2023_codebook_dur"],
    macroregion: ["unknown", "europe"],
  },
  counts: { catalogRows: rows.length, rawDurationRows: 2, normalizedRows: 2 },
  readiness: { status: "ready_descriptive", assessmentLane: "descriptive_with_runtime_gated_comparisons" },
  policy: { minimumCommonSupport: 0.8, minimumActiveAndReferenceBinN: 20 },
  negativeControls: { leaveOneSourceOut: { interpretation: "fixture" } },
};
const durationWorker = loadWorker("webapp/static_public/catalog_filter_worker.js", {
  Response,
  TextDecoder,
  URL,
  fetch: async (urlValue) => {
    const url = String(urlValue);
    if (url.includes("duration_value_dictionary")) return new Response(durationDictionaryText, { status: 200 });
    if (url.includes("duration_projection")) return new Response(durationProjectionText, { status: 200 });
    return new Response("not found", { status: 404 });
  },
  self: { crypto: webcrypto, location: { href: "https://example.test/catalog_filter_worker.js" } },
});
durationWorker.send({ type: "addCatalogFacetRows", requestId: "duration-catalog", rows });
const durationSetup = await durationWorker.sendAsync({
  type: "setAnalysisDurationArtifact",
  requestId: "duration-setup",
  filterGeneration: 4,
  manifest: durationManifest,
  urls: { manifest: "https://example.test/data/analysis_duration_v1/manifest.json" },
});
assert.equal(durationSetup.type, "analysisDurationArtifactSet");
assert.equal(durationSetup.snapshot.appliedRows, 2);
assert.equal(durationSetup.snapshot.normalizedRows, 2);
assert.equal(durationSetup.snapshot.readinessStatus, "ready_descriptive");
const durationFullCorpus = durationWorker.send({
  type: "computeAnalysis",
  requestId: "duration-full-corpus",
  filterGeneration: 4,
  cancellationGeneration: 1,
  baselineMode: "full_catalog",
  fullTimeRange: true,
  timeRangeMode: "full",
  datasetHash: "duration-worker-fixture",
  selectedDomains: ["time"],
  filters: { ...filters, hideLowPrecision: false },
  lowPrecisionValues,
});
assert.equal(durationFullCorpus.type, "analysisComputed");
assert.equal(durationFullCorpus.result.time.duration.status, "ready_descriptive");
assert.equal(durationFullCorpus.result.time.duration.coverage.active.normalizedRows, 2);
assert.equal(durationFullCorpus.result.time.duration.coverage.active.descriptiveBinnedRows, 2);
assert.deepEqual(durationFullCorpus.result.time.duration.artifactHashes, {
  durationProjection: rawHash(durationProjectionText),
  durationValueDictionary: rawHash(durationDictionaryText),
});

const misorderedDurationProjection = durationProjectionRows.map((row) => row.slice());
misorderedDurationProjection[0][1] = "wrong-duration-event";
const misorderedDurationText = JSON.stringify(misorderedDurationProjection);
const misorderedDurationManifest = structuredClone(durationManifest);
misorderedDurationManifest.artifacts.durationProjection.sha256 = rawHash(misorderedDurationText);
const misorderedDurationWorker = loadWorker("webapp/static_public/catalog_filter_worker.js", {
  Response,
  TextDecoder,
  URL,
  fetch: async (urlValue) => new Response(
    String(urlValue).includes("duration_value_dictionary") ? durationDictionaryText : misorderedDurationText,
    { status: 200 }
  ),
  self: { crypto: webcrypto, location: { href: "https://example.test/catalog_filter_worker.js" } },
});
misorderedDurationWorker.send({ type: "addCatalogFacetRows", requestId: "misordered-duration-catalog", rows });
const misorderedDurationSetup = await misorderedDurationWorker.sendAsync({
  type: "setAnalysisDurationArtifact",
  requestId: "misordered-duration-setup",
  filterGeneration: 5,
  manifest: misorderedDurationManifest,
  urls: { manifest: "https://example.test/data/analysis_duration_v1/manifest.json" },
});
assert.equal(misorderedDurationSetup.type, "catalogFacetWorkerError");
assert.match(misorderedDurationSetup.error, /event ID does not match the served catalog/i);

const reportingDelayStatusCodes = [
  "reported_valid", "posted_fallback_valid", "occurrence_precision_incompatible", "occurrence_unparseable",
  "reported_unparseable", "reported_negative", "posted_unparseable", "posted_negative", "date_role_missing",
];
const reportingDelayBinCodes = ["unknown", "same_day", "one_day", "two_to_three_days"];
const reportingDelayProjectionRows = [
  [0, "2606225892387599", 1, 1, 1, 1, 0, 1, 2],
  [1, "city-event", 2, 1, 1, 1, 5, null, 0],
];
const reportingDelayProjectionText = JSON.stringify(reportingDelayProjectionRows);
const reportingDelayManifest = {
  schemaId: "ufo-timeline-analysis-reporting-delay-artifacts-v1.0.0",
  schemaVersion: 1,
  manifestVersion: "1.0.0",
  releaseId: "analysis-reporting-delay-v1-fixture",
  artifacts: {
    reportingDelayProjection: {
      file: "data/analysis_reporting_delay_v1/reporting_delay_projection_v1.json",
      sha256: rawHash(reportingDelayProjectionText),
      gzipSha256: "c".repeat(64),
      rowCount: reportingDelayProjectionRows.length,
      rowSchema: ["catalogRowIndex", "eventId", "sourceCode", "eraCode", "macroregionCode", "selectedRoleCode", "statusCode", "delayDays", "delayBinCode"],
    },
    roleEvidenceShard000: {
      file: "data/analysis_reporting_delay_v1/reporting_delay_role_evidence_v1_000.json",
      sha256: "d".repeat(64),
      gzipSha256: "e".repeat(64),
      rowCount: reportingDelayProjectionRows.length,
      rowSchema: ["catalogRowIndex", "eventId", "sourceCode", "occurrenceRaw", "occurrencePrecisionCode", "reportedRaw", "postedRaw", "occurrenceOrdinal", "reportedOrdinal", "postedOrdinal", "selectedRoleCode", "statusCode", "reasonCode"],
    },
  },
  artifactGroups: { roleEvidenceShards: ["roleEvidenceShard000"] },
  codes: {
    source: ["unknown", "ufocat", "nuforc"],
    occurrencePrecision: ["", "exact_day"],
    era: ["unknown", "1945_1959"],
    macroregion: ["unknown", "europe"],
    selectedRole: ["none", "reported", "posted"],
    status: reportingDelayStatusCodes,
    reason: ["reported_and_posted_missing", "fixture"],
    delayBin: reportingDelayBinCodes,
  },
  counts: { catalogRows: rows.length, dateRoleEvidenceRows: 2, typedRows: 1 },
  readiness: { status: "ready_descriptive", assessmentLane: "descriptive_with_runtime_gated_comparisons" },
  policy: { minimumCommonSupport: 0.8, minimumActiveAndReferenceBinN: 20 },
  negativeControls: { reportedDateOnlyLane: { rows: 1 }, postedDateOnlyLane: { rows: 1 } },
};
const reportingDelayWorker = loadWorker("webapp/static_public/catalog_filter_worker.js", {
  Response,
  TextDecoder,
  URL,
  fetch: async () => new Response(reportingDelayProjectionText, { status: 200 }),
  self: { crypto: webcrypto, location: { href: "https://example.test/catalog_filter_worker.js" } },
});
reportingDelayWorker.send({ type: "addCatalogFacetRows", requestId: "reporting-delay-catalog", rows });
const reportingDelaySetup = await reportingDelayWorker.sendAsync({
  type: "setAnalysisReportingDelayArtifact",
  requestId: "reporting-delay-setup",
  filterGeneration: 6,
  manifest: reportingDelayManifest,
  urls: { manifest: "https://example.test/data/analysis_reporting_delay_v1/manifest.json" },
});
assert.equal(reportingDelaySetup.type, "analysisReportingDelayArtifactSet");
assert.equal(reportingDelaySetup.snapshot.appliedRows, 2);
assert.equal(reportingDelaySetup.snapshot.typedRows, 1);
assert.equal(reportingDelaySetup.snapshot.readinessStatus, "ready_descriptive");
const reportingDelayFullCorpus = reportingDelayWorker.send({
  type: "computeAnalysis",
  requestId: "reporting-delay-full-corpus",
  filterGeneration: 6,
  cancellationGeneration: 1,
  baselineMode: "full_catalog",
  fullTimeRange: true,
  timeRangeMode: "full",
  datasetHash: "reporting-delay-worker-fixture",
  selectedDomains: ["time"],
  filters: { ...filters, hideLowPrecision: false },
  lowPrecisionValues,
});
assert.equal(reportingDelayFullCorpus.type, "analysisComputed");
assert.equal(reportingDelayFullCorpus.result.time.reportingDelay.status, "ready_descriptive");
assert.equal(reportingDelayFullCorpus.result.time.reportingDelay.coverage.active.dateRoleEvidenceRows, 2);
assert.equal(reportingDelayFullCorpus.result.time.reportingDelay.coverage.active.typedRows, 1);
assert.equal(reportingDelayFullCorpus.result.time.reportingDelay.coverage.active.statusCounts.find((item) => item.status === "reported_negative").rows, 1);
assert.deepEqual(reportingDelayFullCorpus.result.time.reportingDelay.artifactHashes, {
  reportingDelayProjection: rawHash(reportingDelayProjectionText),
  roleEvidenceShard000: "d".repeat(64),
});

const misorderedReportingDelayRows = reportingDelayProjectionRows.map((row) => row.slice());
misorderedReportingDelayRows[0][1] = "wrong-reporting-delay-event";
const misorderedReportingDelayText = JSON.stringify(misorderedReportingDelayRows);
const misorderedReportingDelayManifest = structuredClone(reportingDelayManifest);
misorderedReportingDelayManifest.artifacts.reportingDelayProjection.sha256 = rawHash(misorderedReportingDelayText);
const misorderedReportingDelayWorker = loadWorker("webapp/static_public/catalog_filter_worker.js", {
  Response,
  TextDecoder,
  URL,
  fetch: async () => new Response(misorderedReportingDelayText, { status: 200 }),
  self: { crypto: webcrypto, location: { href: "https://example.test/catalog_filter_worker.js" } },
});
misorderedReportingDelayWorker.send({ type: "addCatalogFacetRows", requestId: "misordered-reporting-delay-catalog", rows });
const misorderedReportingDelaySetup = await misorderedReportingDelayWorker.sendAsync({
  type: "setAnalysisReportingDelayArtifact",
  requestId: "misordered-reporting-delay-setup",
  filterGeneration: 7,
  manifest: misorderedReportingDelayManifest,
  urls: { manifest: "https://example.test/data/analysis_reporting_delay_v1/manifest.json" },
});
assert.equal(misorderedReportingDelaySetup.type, "catalogFacetWorkerError");
assert.match(misorderedReportingDelaySetup.error, /event ID does not match the served catalog/i);

const timeOfDayStatusCodes = ["unparsed", "exact_clock", "approximate_clock", "clock_range", "qualitative_period", "sentinel_ambiguous", "invalid_clock"];
const timeOfDayBinCodes = ["unknown", "night_00_05", "morning_06_11", "afternoon_12_17", "evening_18_23"];
const timeOfDayDictionaryRows = [
  [1, rawHash("21:40 Local"), "21:40 Local", 1, 0, 1300, 1300, 4, 4, 1, 0, 1, 1, 1],
  [2, rawHash("0000"), "0000", 5, 1, null, null, 0, 0, 1, 0, 0, 0, 1],
];
const timeOfDayProjectionRows = [
  [0, "2606225892387599", 1, 1],
  [1, "city-event", 0, 1],
];
const timeOfDayDictionaryText = JSON.stringify(timeOfDayDictionaryRows);
const timeOfDayProjectionText = JSON.stringify(timeOfDayProjectionRows);
const timeOfDayManifest = {
  schemaId: "ufo-timeline-analysis-time-of-day-artifacts-v1.0.0",
  schemaVersion: 1,
  manifestVersion: "1.0.0",
  releaseId: "analysis-time-of-day-v1-fixture",
  artifacts: {
    timeOfDayValueDictionary: {
      file: "data/analysis_time_of_day_v1/time_of_day_value_dictionary_v1.json",
      sha256: rawHash(timeOfDayDictionaryText),
      gzipSha256: "f".repeat(64),
      rowCount: 2,
      rowSchema: ["sourceCode", "rawValueSha256", "rawValue", "statusCode", "reasonCode", "lowerMinute", "upperMinute", "descriptiveBinCode", "inferentialBinCode", "precisionCode", "qualitativePeriodCode", "timezoneLabelCode", "timezoneSemanticsCode", "occurrenceCount"],
    },
    timeOfDayProjectionShard000: {
      file: "data/analysis_time_of_day_v1/time_of_day_projection_v1_000.json",
      sha256: rawHash(timeOfDayProjectionText),
      gzipSha256: "e".repeat(64),
      rowCount: 2,
      rowSchema: ["catalogRowIndex", "eventId", "valueCode", "macroregionCode"],
    },
  },
  artifactGroups: { timeProjectionShards: ["timeOfDayProjectionShard000"] },
  codes: {
    source: ["unknown", "nuforc", "ufocat"],
    status: timeOfDayStatusCodes,
    reason: ["explicit_clock", "midnight_or_noon_source_sentinel"],
    timeBin: timeOfDayBinCodes,
    precision: ["unknown", "minute"],
    qualitativePeriod: [""],
    timezoneLabel: ["", "Local"],
    timezoneSemantics: ["unknown", "local_label_without_offset"],
    macroregion: ["unknown", "europe"],
  },
  counts: { catalogRows: rows.length, rawTimeRows: 2, typedRows: 1 },
  readiness: { status: "ready_descriptive", assessmentLane: "descriptive_with_exact_clock_runtime_gated_comparisons" },
  policy: { minimumCommonSupport: 0.8, minimumActiveAndReferenceBinN: 20 },
  negativeControls: { midnightAndNoonSentinelAudit: { excludedRows: 1 } },
};
const timeOfDayWorker = loadWorker("webapp/static_public/catalog_filter_worker.js", {
  Response,
  TextDecoder,
  URL,
  fetch: async (urlValue) => new Response(
    String(urlValue).includes("value_dictionary") ? timeOfDayDictionaryText : timeOfDayProjectionText,
    { status: 200 }
  ),
  self: { crypto: webcrypto, location: { href: "https://example.test/catalog_filter_worker.js" } },
});
timeOfDayWorker.send({ type: "addCatalogFacetRows", requestId: "time-of-day-catalog", rows });
const timeOfDaySetup = await timeOfDayWorker.sendAsync({
  type: "setAnalysisTimeOfDayArtifact",
  requestId: "time-of-day-setup",
  filterGeneration: 8,
  manifest: timeOfDayManifest,
  urls: { manifest: "https://example.test/data/analysis_time_of_day_v1/manifest.json" },
});
assert.equal(timeOfDaySetup.type, "analysisTimeOfDayArtifactSet");
assert.equal(timeOfDaySetup.snapshot.appliedRows, 2);
assert.equal(timeOfDaySetup.snapshot.typedRows, 1);
assert.equal(timeOfDaySetup.snapshot.readinessStatus, "ready_descriptive");
const timeOfDayFullCorpus = timeOfDayWorker.send({
  type: "computeAnalysis",
  requestId: "time-of-day-full-corpus",
  filterGeneration: 8,
  cancellationGeneration: 1,
  baselineMode: "full_catalog",
  fullTimeRange: true,
  timeRangeMode: "full",
  datasetHash: "time-of-day-worker-fixture",
  selectedDomains: ["time"],
  filters: { ...filters, hideLowPrecision: false },
  lowPrecisionValues,
});
assert.equal(timeOfDayFullCorpus.type, "analysisComputed");
assert.equal(timeOfDayFullCorpus.result.time.timeOfDay.status, "ready_descriptive");
assert.equal(timeOfDayFullCorpus.result.time.timeOfDay.coverage.active.rawTimeRows, 2);
assert.equal(timeOfDayFullCorpus.result.time.timeOfDay.coverage.active.typedRows, 1);
assert.equal(timeOfDayFullCorpus.result.time.timeOfDay.coverage.active.exactInferentialRows, 1);
assert.equal(timeOfDayFullCorpus.result.time.timeOfDay.coverage.active.statusCounts.find((item) => item.status === "sentinel_ambiguous").rows, 1);
assert.equal(timeOfDayFullCorpus.result.time.timeOfDay.patternFinderEligible, false);
assert.deepEqual(timeOfDayFullCorpus.result.time.timeOfDay.artifactHashes, {
  timeOfDayProjectionShard000: rawHash(timeOfDayProjectionText),
  timeOfDayValueDictionary: rawHash(timeOfDayDictionaryText),
});

const coordinateEvidenceProjectionRows = [
  [0, "2606225892387599", 1, 1, 1, 0, 0, 0, 0, 48.8566, 2.3522],
];
const coordinateEvidenceProjectionText = JSON.stringify(coordinateEvidenceProjectionRows);
const coordinateEvidenceManifest = {
  schemaId: "ufo-timeline-analysis-coordinate-evidence-artifacts-v1.0.0",
  schemaVersion: 1,
  manifestVersion: "1.0.0",
  releaseId: "analysis-coordinate-evidence-v1-fixture",
  artifacts: {
    coordinateEvidenceProjection: {
      file: "data/analysis_coordinate_evidence_v1/coordinate_evidence_projection_v1.json",
      sha256: rawHash(coordinateEvidenceProjectionText),
      gzipSha256: "1".repeat(64),
      rowCount: 1,
      rowSchema: ["catalogRowIndex", "eventId", "sourceCode", "eraCode", "macroregionCode", "statusCode", "countryConsistencyCode", "qualityBinCode", "riskFlags", "latitude", "longitude"],
    },
    originalEvidenceShard000: {
      file: "data/analysis_coordinate_evidence_v1/coordinate_original_evidence_v1_000.json",
      sha256: "2".repeat(64),
      gzipSha256: "3".repeat(64),
      rowCount: 1,
      rowSchema: Array.from({ length: 18 }, (_, index) => `field${index}`),
    },
  },
  artifactGroups: { originalEvidenceShards: ["originalEvidenceShard000"] },
  codes: {
    source: ["unknown", "ufocat"],
    era: ["unknown", "1945_1959"],
    macroregion: ["unknown", "europe"],
    status: ["typed_country_consistent", "typed_country_unchecked", "unresolved_lineage_conflict", "country_inconsistent", "invalid_zero_sentinel", "invalid_out_of_range", "invalid_non_numeric", "precision_incompatible", "origin_incompatible"],
    countryConsistency: ["consistent", "inconsistent", "unchecked_no_explicit_country", "unchecked_no_pinned_bounds", "not_applicable_invalid"],
    qualityBin: ["country_consistent", "country_unchecked", "lineage_conflict", "country_inconsistent", "invalid_or_incompatible"],
  },
  counts: {
    catalogRows: rows.length,
    sourceCoordinateRows: 1,
    typedRows: 1,
    byCoordinateOrigin: { geocoded: 1, raw_latlong: 1, unresolved: lowPrecisionValues.length },
  },
  readiness: { status: "ready_descriptive", assessmentLane: "descriptive_with_runtime_gated_comparisons" },
  policy: {
    canonicalEventsMutated: false,
    externalGeocodingUsed: false,
    precisionPromotionAllowed: false,
    generalizedMarkersCountAsSourceCoordinates: false,
    minimumCommonSupport: 0.8,
    minimumActiveAndReferenceBinN: 20,
  },
  negativeControls: { generalizedMarkerExclusion: { rows: 1 }, unresolvedMarkerExclusion: { rows: lowPrecisionValues.length } },
};
const coordinateEvidenceWorker = loadWorker("webapp/static_public/catalog_filter_worker.js", {
  Response,
  TextDecoder,
  URL,
  fetch: async () => new Response(coordinateEvidenceProjectionText, { status: 200 }),
  self: { crypto: webcrypto, location: { href: "https://example.test/catalog_filter_worker.js" } },
});
coordinateEvidenceWorker.send({ type: "addCatalogFacetRows", requestId: "coordinate-evidence-catalog", rows });
const coordinateEvidenceSetup = await coordinateEvidenceWorker.sendAsync({
  type: "setAnalysisCoordinateEvidenceArtifact",
  requestId: "coordinate-evidence-setup",
  filterGeneration: 8,
  manifest: coordinateEvidenceManifest,
  urls: { manifest: "https://example.test/data/analysis_coordinate_evidence_v1/manifest.json" },
});
assert.equal(coordinateEvidenceSetup.type, "analysisCoordinateEvidenceArtifactSet");
assert.equal(coordinateEvidenceSetup.snapshot.appliedRows, 1);
assert.equal(coordinateEvidenceSetup.snapshot.typedRows, 1);
assert.equal(coordinateEvidenceSetup.snapshot.readinessStatus, "ready_descriptive");
const coordinateEvidenceFullCorpus = coordinateEvidenceWorker.send({
  type: "computeAnalysis",
  requestId: "coordinate-evidence-full-corpus",
  filterGeneration: 8,
  cancellationGeneration: 1,
  baselineMode: "full_catalog",
  fullTimeRange: true,
  timeRangeMode: "full",
  datasetHash: "coordinate-evidence-worker-fixture",
  selectedDomains: ["sources_quality"],
  filters: { ...filters, hideLowPrecision: false },
  lowPrecisionValues,
});
assert.equal(coordinateEvidenceFullCorpus.type, "analysisComputed");
assert.equal(coordinateEvidenceFullCorpus.result.sourcesQuality.coordinateEvidence.status, "ready_descriptive");
assert.equal(coordinateEvidenceFullCorpus.result.sourcesQuality.coordinateEvidence.coverage.active.sourceCoordinateRows, 1);
assert.equal(coordinateEvidenceFullCorpus.result.sourcesQuality.coordinateEvidence.coverage.active.typedRows, 1);
assert.equal(coordinateEvidenceFullCorpus.result.sourcesQuality.coordinateEvidence.distribution.find((item) => item.key === "country_consistent").activeCount, 1);
assert.equal(coordinateEvidenceFullCorpus.result.sourcesQuality.coordinateEvidence.patternFinderEligible, false);
assert.deepEqual(coordinateEvidenceFullCorpus.result.sourcesQuality.coordinateEvidence.artifactHashes, {
  coordinateEvidenceProjection: rawHash(coordinateEvidenceProjectionText),
  originalEvidenceShard000: "2".repeat(64),
});

const mismatchedCoordinateProjection = [[0, "2606225892387599", 1, 1, 1, 0, 0, 0, 0, 47, 2.3522]];
const mismatchedCoordinateText = JSON.stringify(mismatchedCoordinateProjection);
const mismatchedCoordinateManifest = structuredClone(coordinateEvidenceManifest);
mismatchedCoordinateManifest.artifacts.coordinateEvidenceProjection.sha256 = rawHash(mismatchedCoordinateText);
const mismatchedCoordinateWorker = loadWorker("webapp/static_public/catalog_filter_worker.js", {
  Response,
  TextDecoder,
  URL,
  fetch: async () => new Response(mismatchedCoordinateText, { status: 200 }),
  self: { crypto: webcrypto, location: { href: "https://example.test/catalog_filter_worker.js" } },
});
mismatchedCoordinateWorker.send({ type: "addCatalogFacetRows", requestId: "mismatched-coordinate-catalog", rows });
const mismatchedCoordinateSetup = await mismatchedCoordinateWorker.sendAsync({
  type: "setAnalysisCoordinateEvidenceArtifact",
  requestId: "mismatched-coordinate-setup",
  filterGeneration: 9,
  manifest: mismatchedCoordinateManifest,
  urls: { manifest: "https://example.test/data/analysis_coordinate_evidence_v1/manifest.json" },
});
assert.equal(mismatchedCoordinateSetup.type, "catalogFacetWorkerError");
assert.match(mismatchedCoordinateSetup.error, /values do not match the served catalog/i);

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
assert.equal(numericAdded.storage.typedBytes, 138);
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
const relationshipOnlyWorker = loadWorker("webapp/static_public/catalog_filter_worker.js", {
  Response,
  TextDecoder,
  URL,
  fetch: spatialFetch,
  self: { crypto: webcrypto, location: { href: "https://example.test/catalog_filter_worker.js" } },
});
const relationshipOnlySetup = await relationshipOnlyWorker.sendAsync({
  type: "setAnalysisRelationshipArtifact",
  requestId: "relationship-only-artifact",
  filterGeneration: 30,
  manifest: analysisV2Manifest,
  urls: { manifest: "https://example.test/data/analysis_v2/manifest.json" },
});
assert.equal(relationshipOnlySetup.type, "analysisRelationshipArtifactSet");
assert.equal(relationshipOnlySetup.snapshot.rowCount, 1_804);
const relationshipOnlyAnalysis = relationshipOnlyWorker.send({
  type: "computeAnalysis",
  requestId: "relationship-only-analysis",
  filterGeneration: 30,
  cancellationGeneration: 1,
  baselineMode: "whole_corpus_structure",
  fullTimeRange: true,
  timeRangeMode: "full",
  datasetHash: "relationship-only-fixture",
  selectedDomains: ["context"],
  filters: { ...filters, hideLowPrecision: false },
  lowPrecisionValues,
});
assert.equal(relationshipOnlyAnalysis.type, "analysisComputed");
assert.equal(
  relationshipOnlyAnalysis.result.spatialEvidence.status,
  "context_evidence_ready_spatial_not_loaded",
  "Context can render relationship evidence without cold-loading the point-neighborhood artifacts"
);
assert.equal(relationshipOnlyAnalysis.result.spatialEvidence.relationshipSummary.totalN, 1_804);
assert.equal(relationshipOnlyAnalysis.result.spatialEvidence.traceInputsRead, false);

const contextOnlyRequests = [];
const contextOnlyWorker = loadWorker("webapp/static_public/catalog_filter_worker.js", {
  Response,
  TextDecoder,
  URL,
  fetch: async (urlValue) => {
    contextOnlyRequests.push(String(urlValue));
    return spatialFetch(urlValue);
  },
  self: { crypto: webcrypto, location: { href: "https://example.test/catalog_filter_worker.js" } },
});
const contextOnlySetup = await contextOnlyWorker.sendAsync({
  type: "setAnalysisContextSpatialArtifact",
  requestId: "context-neighbors-only-artifact",
  filterGeneration: 30,
  manifest: analysisV2Manifest,
  urls: { manifest: "https://example.test/data/analysis_v2/manifest.json" },
});
assert.equal(contextOnlySetup.type, "analysisContextSpatialArtifactSet");
assert.equal(contextOnlySetup.snapshot.rowCount, 63_753);
assert.equal(contextOnlySetup.snapshot.fullSpatialLoaded, false);
assert.equal(contextOnlyRequests.length, 1, "Context loads only its point-neighbor projection");
assert.match(contextOnlyRequests[0], /context_ufo_neighbors_v1\.json(?:\?|$)/);
assert.equal(
  contextOnlyRequests.some((url) => /ufo_(?:configuration_(?:points|neighbors)|point_neighbors|spatial_points)|facility_analysis|relationship_reconciliation/.test(url)),
  false,
  "Context-only setup never fetches co-occurrence, Formation, facility, point-pool, or relationship artifacts"
);
const contextOnlyAnalysis = contextOnlyWorker.send({
  type: "computeAnalysis",
  requestId: "context-neighbors-only-analysis",
  filterGeneration: 30,
  cancellationGeneration: 1,
  baselineMode: "whole_corpus_structure",
  fullTimeRange: true,
  timeRangeMode: "full",
  datasetHash: "context-neighbors-only-fixture",
  selectedDomains: ["context"],
  filters: { ...filters, hideLowPrecision: false },
  lowPrecisionValues,
  spatialPermutationCount: 3,
  spatialBootstrapCount: 3,
});
assert.equal(contextOnlyAnalysis.type, "analysisComputed");
assert.equal(contextOnlyAnalysis.result.spatialEvidence.status, "context_evidence_ready_spatial_not_loaded");
assert.deepEqual(
  contextOnlyAnalysis.result.spatialEvidence.contextAssociations.lanes.map((lane) => lane.lane),
  ["crop_bounded", "crop_locality", "animal_public_marker"]
);
assert.equal(contextOnlyAnalysis.result.spatialEvidence.traceInputsRead, false);
assert.equal("cooccurrence" in contextOnlyAnalysis.result.spatialEvidence, false);
assert.equal("facility" in contextOnlyAnalysis.result.spatialEvidence, false);
assert.equal(contextOnlyAnalysis.result.spatialEvidence.inferenceEnabled, true);

contextOnlyWorker.send({
  type: "addCatalogFacetRows",
  requestId: "context-filter-catalog",
  rows,
});
const noMatchContextAnalysis = contextOnlyWorker.send({
  type: "computeAnalysis",
  requestId: "context-no-match-analysis",
  filterGeneration: 31,
  cancellationGeneration: 2,
  baselineMode: "whole_corpus_structure",
  fullTimeRange: true,
  timeRangeMode: "full",
  datasetHash: "context-no-match-fixture",
  selectedDomains: ["context"],
  filters: {
    ...filters,
    sourceMode: "subset",
    hideLowPrecision: false,
    selectedSources: ["source-with-no-reports"],
  },
  lowPrecisionValues,
  spatialPermutationCount: 3,
  spatialBootstrapCount: 3,
});
assert.equal(noMatchContextAnalysis.result.summary.activeCount, 0);
assert.ok(
  noMatchContextAnalysis.result.spatialEvidence.contextAssociations.lanes.every((lane) => (
    lane.observedPairN === 0 && lane.cells.every((cell) => cell.observedClusterCount === 0)
  )),
  "an All Time filter with zero matching reports stays empty instead of falling back to every context neighbor"
);
const retunedContextAnalysis = contextOnlyWorker.send({
  type: "computeAnalysis",
  requestId: "context-no-match-analysis-retuned",
  filterGeneration: 31,
  cancellationGeneration: 2,
  baselineMode: "whole_corpus_structure",
  fullTimeRange: true,
  timeRangeMode: "full",
  datasetHash: "context-no-match-fixture",
  selectedDomains: ["context"],
  filters: {
    ...filters,
    sourceMode: "subset",
    hideLowPrecision: false,
    selectedSources: ["source-with-no-reports"],
  },
  lowPrecisionValues,
  spatialPermutationCount: 5,
  spatialBootstrapCount: 4,
});
assert.equal(retunedContextAnalysis.cacheHit, false, "spatial tuning parameters participate in the Analysis cache key");
assert.ok(retunedContextAnalysis.result.spatialEvidence.contextAssociations.lanes.every((lane) => (
  lane.permutationCount === 5 && lane.bootstrapCount === 4
)));

const descriptiveContextAnalysis = contextOnlyWorker.send({
  type: "computeAnalysis",
  requestId: "context-descriptive-overlap-analysis",
  filterGeneration: 32,
  cancellationGeneration: 3,
  baselineMode: "full_catalog",
  fullTimeRange: false,
  timeRangeMode: "bounded",
  timeRangeStartOrdinal: APP_DAY_1955_08_20,
  timeRangeEndOrdinal: APP_DAY_1955_08_20,
  datasetHash: "context-descriptive-overlap-fixture",
  selectedDomains: ["context"],
  filters: { ...filters, hideLowPrecision: false },
  lowPrecisionValues,
  spatialPermutationCount: 3,
  spatialBootstrapCount: 3,
});
assert.equal(descriptiveContextAnalysis.result.spatialEvidence.inferenceEnabled, false);
assert.ok(descriptiveContextAnalysis.result.spatialEvidence.suppressionReasons.includes("full_catalog_overlap_descriptive_no_inference"));
assert.ok(descriptiveContextAnalysis.result.spatialEvidence.contextAssociations.lanes.every((lane) => (
  lane.cells.every((cell) => cell.pValue === null && cell.qValue === null && cell.patternFinderEligible === false)
)));

let releaseDelayedContextFetch;
let delayedContextFetchStarted = false;
const delayedContextFetchGate = new Promise((resolve) => {
  releaseDelayedContextFetch = resolve;
});
const raceWorker = loadWorker("webapp/static_public/catalog_filter_worker.js", {
  Response,
  TextDecoder,
  URL,
  fetch: async (urlValue) => {
    if (String(urlValue).includes("delayed-context-only.json")) {
      delayedContextFetchStarted = true;
      await delayedContextFetchGate;
      return spatialFetch(new URL(analysisV2Manifest.artifacts.contextUfoNeighbors.file, "https://example.test/"));
    }
    return spatialFetch(urlValue);
  },
  self: { crypto: webcrypto, location: { href: "https://example.test/catalog_filter_worker.js" } },
});
raceWorker.clearMessages();
raceWorker.dispatch({
  type: "setAnalysisContextSpatialArtifact",
  requestId: "context-race-partial",
  filterGeneration: 40,
  manifest: analysisV2Manifest,
  urls: { contextNeighbors: "https://example.test/delayed-context-only.json" },
});
assert.equal(delayedContextFetchStarted, true);
raceWorker.dispatch({
  type: "setAnalysisSpatialArtifacts",
  requestId: "context-race-full",
  filterGeneration: 40,
  cancellationGeneration: 10,
  manifest: analysisV2Manifest,
  urls: { manifest: "https://example.test/data/analysis_v2/manifest.json" },
});
const raceFullSetup = await raceWorker.waitFor("context-race-full");
assert.equal(raceFullSetup.type, "analysisSpatialArtifactsSet");
assert.equal(raceFullSetup.snapshot.rowCounts.contextNeighbors, 63_753);
releaseDelayedContextFetch();
const racePartialSetup = await raceWorker.waitFor("context-race-partial");
assert.equal(racePartialSetup.type, "catalogFacetWorkerError");
assert.match(racePartialSetup.error, /superseded by a newer spatial release request/i);

const fullLoadedContextOnly = raceWorker.send({
  type: "computeAnalysis",
  requestId: "full-loaded-context-only",
  filterGeneration: 41,
  cancellationGeneration: 11,
  baselineMode: "whole_corpus_structure",
  fullTimeRange: true,
  timeRangeMode: "full",
  datasetHash: "full-loaded-context-only-fixture",
  selectedDomains: ["context"],
  filters: { ...filters, hideLowPrecision: false },
  lowPrecisionValues,
  spatialPermutationCount: 3,
  spatialBootstrapCount: 3,
});
assert.equal(fullLoadedContextOnly.result.spatialEvidence.status, "context_evidence_ready");
assert.equal("cooccurrence" in fullLoadedContextOnly.result.spatialEvidence, false);
assert.equal("facility" in fullLoadedContextOnly.result.spatialEvidence, false);
assert.equal(fullLoadedContextOnly.result.spatialEvidence.contextAssociations.lanes.length, 3);
const incompatibleContextManifest = structuredClone(analysisV2Manifest);
incompatibleContextManifest.releaseId = analysisV2Manifest.releaseId + "-different-release";
const incompatibleContextSetup = await raceWorker.sendAsync({
  type: "setAnalysisContextSpatialArtifact",
  requestId: "context-incompatible-release",
  filterGeneration: 42,
  manifest: incompatibleContextManifest,
  urls: { manifest: "https://example.test/data/analysis_v2/manifest.json" },
});
assert.equal(incompatibleContextSetup.type, "catalogFacetWorkerError");
assert.match(incompatibleContextSetup.error, /does not match the spatial release already loaded/i);

let releaseDelayedFullFetch;
let delayedFullFetchStarted = false;
const delayedFullFetchGate = new Promise((resolve) => {
  releaseDelayedFullFetch = resolve;
});
const fullFirstRaceRequests = [];
const fullFirstRaceWorker = loadWorker("webapp/static_public/catalog_filter_worker.js", {
  Response,
  TextDecoder,
  URL,
  fetch: async (urlValue) => {
    const urlText = String(urlValue);
    fullFirstRaceRequests.push(urlText);
    if (urlText.includes("delayed-full-neighbors.json")) {
      delayedFullFetchStarted = true;
      await delayedFullFetchGate;
      return spatialFetch(new URL(analysisV2Manifest.artifacts.ufoPointNeighbors.file, "https://example.test/"));
    }
    return spatialFetch(urlValue);
  },
  self: { crypto: webcrypto, location: { href: "https://example.test/catalog_filter_worker.js" } },
});
fullFirstRaceWorker.clearMessages();
fullFirstRaceWorker.dispatch({
  type: "setAnalysisSpatialArtifacts",
  requestId: "full-first-race-spatial",
  filterGeneration: 43,
  cancellationGeneration: 12,
  manifest: analysisV2Manifest,
  urls: { neighbors: "https://example.test/delayed-full-neighbors.json" },
});
assert.equal(delayedFullFetchStarted, true);
fullFirstRaceWorker.dispatch({
  type: "setAnalysisContextSpatialArtifact",
  requestId: "full-first-race-context",
  filterGeneration: 43,
  manifest: analysisV2Manifest,
  urls: { contextNeighbors: "https://example.test/should-not-fetch-context.json" },
});
const fullFirstPartialSetup = await fullFirstRaceWorker.waitFor("full-first-race-context");
assert.equal(fullFirstPartialSetup.type, "catalogFacetWorkerError");
assert.match(fullFirstPartialSetup.error, /deferred while the full spatial release is loading/i);
assert.equal(
  fullFirstRaceRequests.some((url) => url.includes("should-not-fetch-context.json")),
  false,
  "a Context request arriving during the full load does not start a competing artifact fetch"
);
releaseDelayedFullFetch();
const fullFirstSpatialSetup = await fullFirstRaceWorker.waitFor("full-first-race-spatial");
assert.equal(fullFirstSpatialSetup.type, "analysisSpatialArtifactsSet");
assert.equal(fullFirstSpatialSetup.snapshot.rowCounts.contextNeighbors, 63_753);

const spatialWorkerRequests = [];
const spatialWorker = loadWorker("webapp/static_public/catalog_filter_worker.js", {
  Response,
  TextDecoder,
  URL,
  fetch: async (urlValue) => {
    spatialWorkerRequests.push(String(urlValue));
    return spatialFetch(urlValue);
  },
  self: { crypto: webcrypto, location: { href: "https://example.test/catalog_filter_worker.js" } },
});
await spatialWorker.sendAsync({
  type: "setAnalysisRelationshipArtifact",
  requestId: "spatial-preload-relationship",
  filterGeneration: 31,
  manifest: analysisV2Manifest,
  urls: { manifest: "https://example.test/data/analysis_v2/manifest.json" },
});
await spatialWorker.sendAsync({
  type: "setAnalysisContextSpatialArtifact",
  requestId: "spatial-preload-context",
  filterGeneration: 31,
  manifest: analysisV2Manifest,
  urls: { manifest: "https://example.test/data/analysis_v2/manifest.json" },
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
assert.equal(spatialArtifactSetup.snapshot.rowCounts.spatialPoints, 33_801);
assert.equal(spatialArtifactSetup.snapshot.rowCounts.contextNeighbors, 63_753);
assert.equal(spatialArtifactSetup.snapshot.releaseId, analysisV2Manifest.releaseId);
assert.equal(spatialArtifactSetup.snapshot.artifactHashes.ufoPointNeighbors, analysisV2Manifest.artifacts.ufoPointNeighbors.sha256);
assert.equal(
  spatialWorkerRequests.filter((url) => /relationship_reconciliation\.json(?:\?|$)/.test(url)).length,
  1,
  "Full Spatial reuses the relationship projection already loaded by Context"
);
assert.equal(
  spatialWorkerRequests.filter((url) => /context_ufo_neighbors_v1\.json(?:\?|$)/.test(url)).length,
  1,
  "Full Spatial reuses the context-neighbor projection already loaded by Context"
);
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
const cropReadiness = spatialComputed.result.spatialEvidence.readiness.find((row) => row.key === "cropCircles");
const animalReadiness = spatialComputed.result.spatialEvidence.readiness.find((row) => row.key === "animalReports");
assert.equal(cropReadiness.status, "ready_sensitivity");
assert.equal(cropReadiness.eligibleN, 3_655, "bounded and locality crop lanes remain distinct but both contribute usable markers");
assert.equal(animalReadiness.status, "ready_sensitivity");
assert.equal(animalReadiness.eligibleN, 339, "rough animal markers remain usable for public-marker association analysis");
const relationshipRuntimeReadiness = spatialComputed.result.spatialEvidence.readiness.find((row) => row.key === "relationshipReconciliation");
assert.equal(relationshipRuntimeReadiness.status, "ready_descriptive");
assert.equal(relationshipRuntimeReadiness.inferenceEnabled, false);
assert.equal(relationshipRuntimeReadiness.explicitSourceN, spatialArtifactSetup.snapshot.relationshipReadiness.explicitSourceN);
assert.equal(relationshipRuntimeReadiness.computedCandidateN, spatialArtifactSetup.snapshot.relationshipReadiness.computedCandidateN);
assert.equal(relationshipRuntimeReadiness.quarantinedSubjectN, spatialArtifactSetup.snapshot.relationshipReadiness.quarantinedSubjectN);
assert.equal(relationshipRuntimeReadiness.quarantinedObjectN, spatialArtifactSetup.snapshot.relationshipReadiness.quarantinedObjectN);
assert.ok(relationshipRuntimeReadiness.gates.some((gate) => gate.gateId === "relationship_inference" && gate.status === "blocked"));

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
  analysisDurationArtifactHashes: () => ({}),
  analysisReportingDelayArtifactHashes: () => ({}),
  analysisTimeOfDayArtifactHashes: () => ({}),
  analysisCoordinateEvidenceArtifactHashes: () => ({}),
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

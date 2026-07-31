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
  vm.runInNewContext(
    fs.readFileSync(workerPath, "utf8"),
    { Array, Boolean, Map, Number, Object, Set, String, console, self },
    { filename: workerPath }
  );
  assert.equal(typeof self.onmessage, "function");
  return {
    send(message) {
      messages.length = 0;
      self.onmessage({ data: message });
      assert.equal(messages.length, 1);
      return JSON.parse(JSON.stringify(messages[0]));
    },
  };
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

const rows = [
  {
    eventId: "2606225892387599",
    source: "ufocat",
    type: "Fireball",
    visualTypeGroup: "Light / glow",
    craftType: "light",
    precision: "exact_coords",
    datePrecision: "exact_day",
    sortOrdinal: 713915,
  },
  {
    eventId: "city-event",
    source: "nuforc",
    type: "Disk",
    visualTypeGroup: "Disc / saucer",
    craftType: "disc_saucer",
    precision: "city",
    datePrecision: "exact_day",
    sortOrdinal: 713915,
  },
  ...lowPrecisionValues.map((precision, index) => ({
    eventId: `low-${index}`,
    source: "fixture",
    type: "Unknown",
    visualTypeGroup: "Other / unknown",
    craftType: "unknown",
    precision,
    datePrecision: "exact_day",
    sortOrdinal: 713915,
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
assert.equal(added.storage.typedBytes, rows.length * 28);
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
  timeRangeStartOrdinal: 713915,
  timeRangeEndOrdinal: 713915,
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
  timeRangeStartOrdinal: 713915,
  timeRangeEndOrdinal: 713915,
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
    sortOrdinal: 713915,
  }],
});
assert.equal(numericAdded.storage.stringEventIds, 0);
assert.equal(numericAdded.storage.typedBytes, 28);
const numericFiltered = numericWorker.send({
  type: "computeFilteredCatalogIds",
  requestId: "numeric-filter",
  filters: { ...filters, hideLowPrecision: false },
  lowPrecisionValues,
  catalogExactDayAscending: true,
});
assert.deepEqual(numericFiltered.result.eventIds, [2606225892387599]);

console.log("catalog filter worker assertions passed");

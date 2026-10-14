(function (root, factory) {
  "use strict";
  const api = factory(function () {
    if (typeof module === "object" && module.exports) return require("./analysis_stats.js");
    return root.UfoAnalysisStats;
  });
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.UfoEncounterAtlasQuery = api;
})(typeof self !== "undefined" ? self : globalThis, function (getStats) {
  "use strict";
  const VERSION = "encounter-atlas-query-v1";
  function statistics() {
    const api = getStats();
    if (!api || typeof api.encounterAtlasRowMembership !== "function") throw new Error("The Analysis field classifier must load before an encounter atlas query.");
    return api;
  }
  function canonicalRow(rowValue, ordinalEpoch) {
    const row = rowValue || {};
    if (!ordinalEpoch || ["statistics_day", "gregorian_day"].includes(ordinalEpoch)) return row;
    if (ordinalEpoch !== "unix_day") throw new Error("Encounter atlas queries require an explicit supported ordinal epoch.");
    const offset = statistics().ordinalFromCivil(1970, 1, 1);
    const result = Object.assign({}, row);
    ["sortOrdinal", "dateStartOrdinal", "dateEndOrdinal"].forEach(function (key) {
      result[key] = typeof row[key] === "number" && Number.isInteger(row[key]) ? row[key] + offset : null;
    });
    return result;
  }
  function membership(rowValue, optionsValue) {
    const options = optionsValue || {};
    return statistics().encounterAtlasRowMembership(canonicalRow(rowValue, options.ordinalEpoch), options);
  }
  function matches(row, queryValue, optionsValue) {
    const query = queryValue || {}, options = Object.assign({}, optionsValue || {}, {
      population: query.population || (optionsValue || {}).population,
      evidenceMode: query.evidenceMode || (optionsValue || {}).evidenceMode,
    });
    const value = membership(row, options);
    if (!value.eligible || value.status !== "ready") return false;
    const rowKey = query.row || query.rowKey;
    if (rowKey && !value.rowKeys.includes(rowKey)) return false;
    const axisKey = query.axis || query.axisKey;
    if (!axisKey) return true;
    const field = value.fields[axisKey];
    if (!field || query.fieldState && field.state !== query.fieldState) return false;
    const columnKey = query.column || query.columnKey;
    if (!columnKey) return field.state !== "excluded" || query.fieldState === "excluded";
    return field.categories.some(function (category) { return category.key === columnKey; });
  }
  function predicate(query, options) { return function (row) { return matches(row, query, options); }; }
  function collectPage(forEachRow, queryValue, optionsValue) {
    if (typeof forEachRow !== "function") throw new Error("Encounter query paging requires the existing bounded row iterator.");
    const query = queryValue || {}, options = optionsValue || {};
    const offset = Number.isInteger(options.offset) && options.offset >= 0 ? options.offset : 0;
    const limit = Number.isInteger(options.limit) && options.limit > 0 ? Math.min(100, options.limit) : 25;
    const page = [], coverage = { populationReports: 0, eligibleReports: 0, supportedReports: 0, unknownReports: 0,
      notLoadedReports: 0, excludedReports: 0, provenanceUnavailableReports: 0 };
    let totalMatched = 0;
    forEachRow(function (row) {
      const value = membership(row, Object.assign({}, options, { population: query.population || options.population,
        evidenceMode: query.evidenceMode || options.evidenceMode }));
      if (value.status === "evidence_provenance_unavailable") { coverage.provenanceUnavailableReports += 1; return; }
      if (!value.eligible) return;
      const rowKey = query.row || query.rowKey, axisKey = query.axis || query.axisKey, columnKey = query.column || query.columnKey;
      if (rowKey && !value.rowKeys.includes(rowKey)) return;
      coverage.populationReports += 1;
      const field = axisKey ? value.fields[axisKey] : null;
      if (axisKey && !field) return;
      if (field) {
        const counter = { supported: "supportedReports", unknown: "unknownReports", not_loaded: "notLoadedReports", excluded: "excludedReports" }[field.state];
        coverage[counter] += 1;
        if (field.state !== "excluded") coverage.eligibleReports += 1;
        if (query.fieldState && field.state !== query.fieldState) return;
        if (columnKey ? !field.categories.some(function (entry) { return entry.key === columnKey; }) : field.state === "excluded" && query.fieldState !== "excluded") return;
      } else coverage.eligibleReports += 1;
      if (totalMatched >= offset && page.length < limit) page.push(typeof options.project === "function" ? options.project(row, value) : {
        eventId: String(row.eventId ?? row.id ?? ""), source: row.source ?? null, type: row.type ?? null,
        craftType: row.craftType ?? null, rowKeys: value.rowKeys.slice(), field: field || null,
      });
      totalMatched += 1;
    });
    return { status: coverage.provenanceUnavailableReports ? "evidence_provenance_unavailable" : "ready", totalMatched, offset, limit, rows: page, coverage };
  }
  return Object.freeze({ VERSION, canonicalRow, membership, matches, predicate, collectPage });
});

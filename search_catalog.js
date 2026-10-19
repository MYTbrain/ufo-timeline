(function (root, factory) {
  "use strict";
  const query = typeof module === "object" && module.exports ? require("./search_query.js") : root.UfoSearchQuery;
  const api = factory(query);
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.UfoSearchCatalog = api;
})(typeof self !== "undefined" ? self : globalThis, function (Query) {
  "use strict";
  function canonicalId(value) {
    if (typeof value === "string") return value.trim() ? value : null;
    if (typeof value === "number" && Number.isFinite(value)) return String(value);
    return null;
  }
  function eventId(record) {
    if (!record || typeof record !== "object") return null;
    return canonicalId(record.event_id != null ? record.event_id : record.eventId);
  }
  function abortError(message) {
    const error = new Error(message); error.name = "AbortError"; return error;
  }
  function current(options) {
    if (options.signal && options.signal.aborted) throw abortError("Search cancelled.");
    if (typeof options.isCurrent === "function" && !options.isCurrent()) throw abortError("Search superseded by a newer request.");
  }
  const yieldToPage = () => new Promise(resolve => setTimeout(resolve, 0));

  // Re-read the current catalog on every request. Corrected metadata supplements
  // each exact raw-text leaf before the query engine evaluates AND/OR; evaluating
  // the entire Boolean query against metadata alone would miss split matches.
  async function supplementalMatches(plan, catalog, configuration) {
    const options = configuration || {}, records = Array.isArray(catalog) ? catalog : [];
    if (!Query || typeof Query.serializeEvent !== "function") throw new Error("Load the search query module before catalog search.");
    const terms = Array.from(new Set((plan && Array.isArray(plan.terms) ? plan.terms : []).filter(term => typeof term === "string" && term.length)));
    if (terms.length > 32) throw new Error("Catalog search supports no more than 32 query terms.");
    const result = Object.create(null), seen = new Map(), total = records.length;
    const requestedEvery = Number(options.yieldEvery), every = Number.isFinite(requestedEvery)
      ? Math.max(1, Math.min(10000, Math.floor(requestedEvery))) : 1000;
    terms.forEach(term => { result[term] = []; });
    function progress(completedReports) {
      current(options);
      if (typeof options.onProgress === "function") options.onProgress({ completedReports, totalReports: total });
      current(options);
    }
    current(options); progress(0);
    if (!terms.length) return result;
    for (let start = 0; start < total; start += every) {
      current(options);
      const end = Math.min(start + every, total);
      for (let index = start; index < end; index += 1) {
        const record = records[index], id = eventId(record);
        if (id == null) continue;
        const text = Query.serializeEvent(record), previous = seen.get(id) || 0;
        let bits = previous;
        for (let termIndex = 0; termIndex < terms.length; termIndex += 1) {
          const bit = 1 << termIndex;
          if (!(bits & bit) && text.includes(terms[termIndex])) {
            result[terms[termIndex]].push(id); bits |= bit;
          }
        }
        if (bits !== previous) seen.set(id, bits);
      }
      progress(end);
      if (end < total) { await yieldToPage(); current(options); }
    }
    current(options);
    return result;
  }

  function filteredIds(allSearchIds, currentFilteredCatalog) {
    const allowed = new Set();
    if (allSearchIds && typeof allSearchIds[Symbol.iterator] === "function") {
      for (const value of allSearchIds) { const id = canonicalId(value); if (id != null) allowed.add(id); }
    }
    const found = new Set(), result = [];
    (Array.isArray(currentFilteredCatalog) ? currentFilteredCatalog : []).forEach(record => {
      const id = eventId(record);
      if (id != null && allowed.has(id) && !found.has(id)) { found.add(id); result.push(id); }
    });
    return result;
  }
  return Object.freeze({ supplementalMatches, filteredIds });
});

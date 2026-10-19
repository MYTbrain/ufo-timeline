(function (root, factory) {
  "use strict";
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.UfoAnalysisSession = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";
  const DOMAINS = Object.freeze(["source", "craft", "being", "abduction", "year", "calendarMonth", "weekday", "timeOfDay",
    "country", "macroregion", "adminRegion", "reportType", "datePrecision", "locationPrecision", "craftConfidence", "color", "duration", "witnessCount"]);
  const DOMAIN_ORDERS = Object.freeze({
    timeOfDay: Object.freeze(["night_00_05", "morning_06_11", "afternoon_12_17", "evening_18_23"]),
    duration: Object.freeze(["under_10_seconds", "10_59_seconds", "1_4_minutes", "5_14_minutes", "15_59_minutes", "1_5_hours", "over_5_hours"]),
    witnessCount: Object.freeze(["one", "two", "three_to_four", "five_to_nine", "ten_to_nineteen", "twenty_to_forty_nine", "fifty_to_ninety_nine", "hundred_to_999", "thousand_plus"]),
  });
  const COUNT_UNIT = "canonical reports; not independent incidents";
  const normalized = new WeakSet();
  function requireValue(value, message) { if (!value) throw new Error("Analysis session: " + message); }
  function plain(value) { return value && typeof value === "object" && (Object.getPrototypeOf(value) === Object.prototype || Object.getPrototypeOf(value) === null); }
  function clone(value, ancestors, key) {
    // Membership belongs to eventIds once. An active-snapshot object can contain
    // that array again; retain its declared size, not a second corpus-sized copy.
    if ((Array.isArray(value) || value instanceof Set) && /(?:event|report)ids$/i.test(String(key || "").replace(/[_-]/g, ""))) {
      return { reportIdsOmitted: true, providedIdCount: value instanceof Set ? value.size : value.length, membershipStoredAt: "cohort.eventIds" };
    }
    if (value == null || typeof value === "string" || typeof value === "boolean") return value;
    if (typeof value === "number") { requireValue(Number.isFinite(value), "non-finite metadata"); return value; }
    requireValue(Array.isArray(value) || plain(value), "metadata must contain plain data");
    ancestors = ancestors || new Set(); requireValue(!ancestors.has(value), "cyclic metadata"); ancestors.add(value);
    const copy = Array.isArray(value) ? value.map(item => clone(item, ancestors)) : {};
    if (!Array.isArray(value)) Object.keys(value).forEach(key => Object.defineProperty(copy, key, { value: clone(value[key], ancestors, key), enumerable: true, writable: true, configurable: true }));
    ancestors.delete(value); return copy;
  }
  function freeze(value) { if (value && typeof value === "object" && !Object.isFrozen(value)) { Object.values(value).forEach(freeze); Object.freeze(value); } return value; }
  function count(value, maximum, label) {
    if (value == null) return null;
    requireValue(Number.isSafeInteger(value) && value >= 0 && value <= maximum, "invalid " + label); return value;
  }
  function categoryMetadata(row, n, maximum) {
    const hasLower = row.lowerCount != null, hasUpper = row.upperCount != null;
    requireValue(hasLower === hasUpper, "sampled bounds require both lowerCount and upperCount");
    const metadata = {};
    if (hasLower) {
      const lower = count(row.lowerCount, maximum, "sampled lower count"), upper = count(row.upperCount, maximum, "sampled upper count");
      requireValue(lower <= n && n <= upper, "sampled bounds must contain the category count");
      metadata.lowerCount = lower; metadata.upperCount = upper;
    }
    const hasRow = row.matrixRow != null, hasColumn = row.matrixColumn != null;
    requireValue(hasRow === hasColumn, "matrix coordinates require both row and column");
    if (hasRow) {
      for (const key of ["matrixRow", "matrixColumn"]) {
        requireValue(typeof row[key] === "string" && row[key].trim() && row[key].length <= 256, "invalid " + key);
        metadata[key] = row[key];
      }
    }
    return metadata;
  }
  function coverageMetadata(value, totalN, eligibleN) {
    if (value == null) return null;
    requireValue(plain(value), "invalid comparison input coverage");
    const result = {};
    for (const key of ["eligibleExactDateN", "verifiedTimeN", "dateOnlyN", "stableN", "ambiguousN", "skyEligibleN", "verifiedInputN", "missingInputN"]) {
      if (Object.prototype.hasOwnProperty.call(value, key)) result[key] = count(value[key], totalN, "coverage " + key);
    }
    for (const [first, second, denominator] of [["verifiedTimeN", "dateOnlyN", eligibleN], ["stableN", "ambiguousN", eligibleN], ["verifiedInputN", "missingInputN", totalN]]) {
      if (result[first] != null && result[second] != null) requireValue(result[first] + result[second] === denominator, "coverage " + first + "/" + second + " does not match its population");
    }
    return result;
  }
  function uncertaintyMetadata(value) {
    if (value == null) return null;
    requireValue(plain(value) && value.kind === "sampled_time_interval", "unsupported comparison uncertainty kind");
    requireValue(["utc_noon_with_verified_utc_overrides", "verified_utc"].includes(value.estimate), "unsupported comparison estimate method");
    return { kind: value.kind, estimate: value.estimate, label: String(value.label || "Stable–possible counts"),
      note: String(value.note || "Sampled source-time bounds, not confidence intervals.") };
  }
  function heatmapMetadata(value, left, right) {
    if (value == null) return null;
    requireValue(plain(value) && typeof value.kind === "string" && value.kind.trim(), "invalid comparison matrix");
    const axes = {};
    for (const name of ["rows", "columns"]) {
      requireValue(Array.isArray(value[name]), "missing comparison matrix " + name);
      const keys = new Set();
      axes[name] = value[name].map(entry => {
        requireValue(plain(entry) && typeof entry.key === "string" && entry.key.trim() && entry.key.length <= 256 && !keys.has(entry.key), "invalid or repeated comparison matrix " + name);
        keys.add(entry.key); return { key: entry.key, label: String(entry.label == null ? entry.key : entry.label) };
      });
    }
    const rowKeys = new Set(axes.rows.map(entry => entry.key)), columnKeys = new Set(axes.columns.map(entry => entry.key));
    for (const side of [left, right]) if (side) {
      const cells = new Set();
      for (const row of side.rows) {
        requireValue(rowKeys.has(row.matrixRow) && columnKeys.has(row.matrixColumn), "category does not belong to comparison matrix axes");
        const cell = JSON.stringify([row.matrixRow, row.matrixColumn]);
        requireValue(!cells.has(cell), "repeated comparison matrix cell"); cells.add(cell);
      }
    }
    return { kind: value.kind, rows: axes.rows, columns: axes.columns };
  }
  function ids(values) {
    requireValue(Array.isArray(values) || values instanceof Set, "eventIds must be an array or Set");
    const seen = new Set(), result = [];
    for (const value of values) {
      requireValue(typeof value === "string" || typeof value === "number" && Number.isSafeInteger(value) && value >= 0, "invalid report identity");
      const key = String(value).trim(); requireValue(key.length > 0, "empty report identity");
      if (!seen.has(key)) { seen.add(key); result.push(key); }
    }
    return result;
  }
  function distribution(value, reportN, domain) {
    if (value == null || value.available === false) return null;
    // A bare array remains count-only: its field-coverage denominator is unknown.
    const input = Array.isArray(value) ? { rows: value } : value;
    requireValue(plain(input) && Array.isArray(input.rows), "invalid " + domain + " distribution");
    const eligibleN = count(input.eligibleN, reportN, domain + " eligible count"), unknownN = count(input.unknownN, reportN, domain + " unknown count");
    if (eligibleN !== null && unknownN !== null) requireValue(eligibleN + unknownN === reportN, domain + " coverage does not match captured reports");
    const keys = new Set(), rows = input.rows.map(row => {
      requireValue(plain(row) && row.key != null, "invalid category"); const key = String(row.key);
      requireValue(key && !keys.has(key), "repeated category"); keys.add(key);
      const n = count(row.count, eligibleN === null ? reportN : eligibleN, "category count"); requireValue(n !== null, "missing category count");
      return Object.assign({ key, label: String(row.label == null ? key : row.label), count: n }, categoryMetadata(row, n, eligibleN === null ? reportN : eligibleN));
    });
    const multiLabel = input.multiLabel === true, sum = rows.reduce((total, row) => total + row.count, 0);
    if (eligibleN !== null) requireValue(multiLabel ? sum >= eligibleN : sum === eligibleN, domain + " categories do not describe the eligible pool");
    return { available: true, eligibleN, unknownN, multiLabel, rows };
  }
  function cohort(payload) {
    requireValue(plain(payload), "capture payload must be an object");
    if (normalized.has(payload)) return payload;
    const eventIds = ids(payload.eventIds), reportN = eventIds.length;
    const input = payload.summary == null ? {} : payload.summary; requireValue(plain(input), "invalid summary");
    if (input.reportN != null) requireValue(input.reportN === reportN, "summary reportN differs from unique captured IDs");
    const summary = { reportN, mappedN: count(input.mappedN, reportN, "mapped count"), unmappedN: count(input.unmappedN, reportN, "unmapped count"),
      datedN: count(input.datedN, reportN, "dated count"), undatedN: count(input.undatedN, reportN, "undated count"), distributions: {} };
    [["mappedN", "unmappedN"], ["datedN", "undatedN"]].forEach(pair => {
      if (summary[pair[0]] !== null && summary[pair[1]] !== null) requireValue(summary[pair[0]] + summary[pair[1]] === reportN, pair.join("/") + " does not match captured reports");
    });
    if (input.dateLabel != null) summary.dateLabel = String(input.dateLabel);
    const supplied = input.distributions || {}; requireValue(plain(supplied), "invalid distribution summary");
    DOMAINS.forEach(domain => { summary.distributions[domain] = distribution(supplied[domain], reportN, domain); });
    const result = freeze({ eventIds, reportCount: reportN, label: String(payload.label == null ? "Captured reports" : payload.label),
      scope: clone(payload.scope == null ? "captured report cohort" : payload.scope), provenance: clone(payload.provenance == null ? {} : payload.provenance), summary, countUnit: COUNT_UNIT });
    normalized.add(result); return result;
  }
  function ratio(numerator, denominator) { return numerator === null || denominator === null || denominator <= 0 ? null : numerator / denominator; }
  function groupMeta(group) { return Object.assign({ label: group.label, scope: group.scope, provenance: group.provenance }, group.summary, { reportN: group.reportCount }); }
  function compareDomain(a, b, domain) {
    const left = a.summary.distributions[domain], right = b.summary.distributions[domain];
    const aMeta = { available: !!left, eligibleN: left ? left.eligibleN : null, unknownN: left ? left.unknownN : null };
    const bMeta = { available: !!right, eligibleN: right ? right.eligibleN : null, unknownN: right ? right.unknownN : null };
    const categories = new Map(), leftRows = new Map(), rightRows = new Map();
    if (left) left.rows.forEach(row => { categories.set(row.key, row.label); leftRows.set(row.key, row); });
    if (right) right.rows.forEach(row => { if (!categories.has(row.key)) categories.set(row.key, row.label); rightRows.set(row.key, row); });
    const rows = Array.from(categories, ([key, label]) => {
      const aRow = leftRows.get(key), bRow = rightRows.get(key);
      const aCount = left ? (aRow ? aRow.count : 0) : null, bCount = right ? (bRow ? bRow.count : 0) : null;
      const aShare = ratio(aCount, aMeta.eligibleN), bShare = ratio(bCount, bMeta.eligibleN);
      const aShareOfReports = ratio(aCount, a.reportCount), bShareOfReports = ratio(bCount, b.reportCount);
      if (aRow && bRow && aRow.matrixRow != null && bRow.matrixRow != null) requireValue(aRow.matrixRow === bRow.matrixRow && aRow.matrixColumn === bRow.matrixColumn, "conflicting comparison matrix coordinates");
      const aLowerCount = aRow && aRow.lowerCount != null ? aRow.lowerCount : null, aUpperCount = aRow && aRow.upperCount != null ? aRow.upperCount : null;
      const bLowerCount = bRow && bRow.lowerCount != null ? bRow.lowerCount : null, bUpperCount = bRow && bRow.upperCount != null ? bRow.upperCount : null;
      return { key, label, aCount, bCount, aShare, bShare, aShareOfReports, bShareOfReports,
        aLowerCount, aUpperCount, bLowerCount, bUpperCount,
        aLowerShareOfReports: ratio(aLowerCount, a.reportCount), aUpperShareOfReports: ratio(aUpperCount, a.reportCount),
        bLowerShareOfReports: ratio(bLowerCount, b.reportCount), bUpperShareOfReports: ratio(bUpperCount, b.reportCount),
        matrixRow: aRow && aRow.matrixRow != null ? aRow.matrixRow : bRow && bRow.matrixRow != null ? bRow.matrixRow : null,
        matrixColumn: aRow && aRow.matrixColumn != null ? aRow.matrixColumn : bRow && bRow.matrixColumn != null ? bRow.matrixColumn : null,
        shareDifference: aShare === null || bShare === null ? null : aShare - bShare,
        reportShareDifference: aShareOfReports === null || bShareOfReports === null ? null : aShareOfReports - bShareOfReports };
    }).sort((x, y) => {
      if (["year", "calendarMonth", "weekday"].includes(domain) && /^\d+$/.test(x.key) && /^\d+$/.test(y.key)) return Number(x.key) - Number(y.key);
      const order = DOMAIN_ORDERS[domain];
      if (order) {
        const xi = order.indexOf(x.key), yi = order.indexOf(y.key);
        if (xi !== -1 || yi !== -1) return (xi === -1 ? order.length : xi) - (yi === -1 ? order.length : yi);
      }
      return x.label.localeCompare(y.label) || x.key.localeCompare(y.key);
    });
    return { available: !!left && !!right, a: aMeta, b: bMeta, multiLabel: !!(left && left.multiLabel || right && right.multiLabel), rows,
      unknown: { aCount: aMeta.unknownN, bCount: bMeta.unknownN, aShareOfReports: ratio(aMeta.unknownN, a.reportCount), bShareOfReports: ratio(bMeta.unknownN, b.reportCount) },
      shareDenominator: "eligible reports within each group", reportShareDenominator: "all captured reports within each group" };
  }
  function compareGroups(left, right) {
    if (left == null || right == null) return null;
    const a = cohort(left), b = cohort(right), aIds = new Set(a.eventIds); let overlapN = 0;
    b.eventIds.forEach(id => { if (aIds.has(id)) overlapN += 1; });
    const distributions = {}; DOMAINS.forEach(domain => { distributions[domain] = compareDomain(a, b, domain); });
    return freeze({ a: groupMeta(a), b: groupMeta(b), overlapCount: overlapN,
      overlap: { reportN: overlapN, shareA: ratio(overlapN, a.reportCount), shareB: ratio(overlapN, b.reportCount),
        onlyAN: a.reportCount - overlapN, onlyBN: b.reportCount - overlapN, unionN: a.reportCount + b.reportCount - overlapN },
      distributions, countUnit: COUNT_UNIT, inferenceEligible: false,
      interpretation: "Descriptive overlapping report cohorts. Categories may overlap; differences do not establish independent incidents or causal effects." });
  }
  function compareExternalDimension(input) {
    requireValue(plain(input) && String(input.key || "").trim(), "invalid external comparison dimension");
    const key = String(input.key), unit = String(input.unit || "records"), multiLabel = input.multiLabel === true;
    function side(value, name) {
      if (value == null || value.available === false) return null;
      requireValue(plain(value), "invalid external " + name + " population");
      const totalN = count(value.totalN, Number.MAX_SAFE_INTEGER, name + " total");
      requireValue(totalN !== null, "missing external " + name + " total");
      const normalizedDistribution = distribution({ rows: value.rows, eligibleN: value.eligibleN, unknownN: value.unknownN, multiLabel }, totalN, key);
      requireValue(normalizedDistribution.eligibleN !== null && normalizedDistribution.unknownN !== null, "missing external field coverage");
      return Object.assign({ totalN }, normalizedDistribution);
    }
    const left = side(input.a, "A"), right = side(input.b, "B");
    // External catalogs have their own denominator. Never reuse the held UFO
    // report counts for crop records, animal records, pairs or test contexts.
    const result = compareDomain({ reportCount: left ? left.totalN : 0, summary: { distributions: { [key]: left } } },
      { reportCount: right ? right.totalN : 0, summary: { distributions: { [key]: right } } }, key);
    if (input.order === "source") {
      const order = new Map(); [left, right].forEach(value => { if (value) value.rows.forEach(row => { if (!order.has(row.key)) order.set(row.key, order.size); }); });
      result.rows.sort((a, b) => order.get(a.key) - order.get(b.key));
    }
    result.a.totalN = left ? left.totalN : count(input.a && input.a.totalN, Number.MAX_SAFE_INTEGER, "A total");
    result.b.totalN = right ? right.totalN : count(input.b && input.b.totalN, Number.MAX_SAFE_INTEGER, "B total");
    [["a", input.a], ["b", input.b]].forEach(([slot, source]) => {
      if (source && source.reason != null) result[slot].reason = String(source.reason);
      result[slot].notes = source && Array.isArray(source.notes) ? source.notes.map(String) : [];
      const normalized = slot === "a" ? left : right;
      result[slot].coverage = normalized ? coverageMetadata(source && source.coverage, normalized.totalN, normalized.eligibleN) : null;
      if (source && source.calculated != null) {
        requireValue(typeof source.calculated === "boolean", "invalid calculation availability"); result[slot].calculated = source.calculated;
      }
    });
    return freeze(Object.assign(result, { key, label: String(input.label || key), unit, external: true,
      notes: Array.isArray(input.notes) ? input.notes.map(String) : [],
      uncertainty: uncertaintyMetadata(input.uncertainty), heatmap: heatmapMetadata(input.heatmap, left, right),
      reportShareDenominator: "all " + unit + " within each derived group", order: input.order === "source" ? "source" : "difference" }));
  }
  function slot(value) { const key = String(value).toUpperCase(); requireValue(key === "A" || key === "B", "slot must be A or B"); return key; }
  function createStore(options) {
    options = options || {}; const listeners = new Set(); let state = freeze({ version: 0, groups: { A: null, B: null }, selection: null, activeGroup: null, comparison: null });
    function publish(groups, selection, activeGroup) {
      const comparison = groups.A === state.groups.A && groups.B === state.groups.B ? state.comparison : compareGroups(groups.A, groups.B);
      state = freeze({ version: state.version + 1, groups, selection, activeGroup, comparison });
      listeners.forEach(listener => { try { listener(state); } catch (error) { if (typeof options.onListenerError === "function") options.onListenerError(error); } });
      return state;
    }
    return Object.freeze({
      getState: () => state,
      subscribe: listener => { requireValue(typeof listener === "function", "listener must be a function"); listeners.add(listener); return () => listeners.delete(listener); },
      setGroup: (name, payload) => { const key = slot(name), value = cohort(payload); return publish(Object.assign({}, state.groups, { [key]: value }), state.selection, state.activeGroup === key ? null : state.activeGroup); },
      clearGroup: name => { const key = slot(name); if (!state.groups[key]) return state; return publish(Object.assign({}, state.groups, { [key]: null }), state.selection, state.activeGroup === key ? null : state.activeGroup); },
      useGroup: name => { const key = slot(name), value = state.groups[key]; if (!value || !value.reportCount) return false; publish(state.groups, value, key); return true; },
      useSelection: payload => publish(state.groups, cohort(payload), null),
      clearSelection: () => state.selection === null && state.activeGroup === null ? state : publish(state.groups, null, null),
      clearAll: () => !state.groups.A && !state.groups.B && !state.selection ? state : publish({ A: null, B: null }, null, null)
    });
  }
  return Object.freeze({ createStore, compareGroups, compareExternalDimension, DOMAINS, COUNT_UNIT });
});

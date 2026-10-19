(function (root, factory) {
  "use strict";
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.UfoAnalysisOverviewVisuals = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";
  // Deliberately identical to the map's default craft legend, rather than a
  // rank-dependent palette that changes when a time window or lens changes.
  const CRAFT_PALETTE = Object.freeze([
    ["disc_saucer", "Disc / saucer", "#38bdf8"], ["sphere_orb", "Sphere / orb", "#22c55e"],
    ["triangle", "Triangle", "#f97316"], ["cigar_cylinder", "Cigar / cylinder", "#a78bfa"],
    ["oval_egg", "Oval / egg", "#facc15"], ["chevron_boomerang", "Chevron / boomerang", "#fb7185"],
    ["rectangle_box", "Rectangle / box", "#60a5fa"], ["fireball_meteor_like", "Fireball / meteor-like", "#ef4444"],
    ["formation", "Formation", "#14b8a6"], ["cone", "Cone", "#e879f9"], ["diamond", "Diamond", "#2dd4bf"],
    ["teardrop", "Teardrop", "#0ea5e9"], ["dumbbell_barbell", "Dumbbell / barbell", "#c084fc"],
    ["light", "Light", "#b517ff"], ["conventional_or_explained", "Conventional / explained", "#94a3b8"],
    ["non_ufo_context", "Non-UFO context", "#64748b"], ["unknown", "Unknown", "#7e8f88"],
  ].map(value => Object.freeze({ key: value[0], label: value[1], color: value[2] })));
  const CRAFT_COLORS = Object.freeze(Object.fromEntries(CRAFT_PALETTE.map(item => [item.key, item.color])));
  const CRAFT_LABELS = Object.freeze(Object.fromEntries(CRAFT_PALETTE.map(item => [item.key, item.label])));
  const aliases = new Map();
  function normalized(value) { return String(value == null ? "" : value).trim().toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, ""); }
  CRAFT_PALETTE.forEach(item => { aliases.set(normalized(item.key), item.key); aliases.set(normalized(item.label), item.key); });
  function craftKey(value) { return aliases.get(normalized(value)) || "unknown"; }
  function craftColor(value) { return CRAFT_COLORS[craftKey(value)]; }
  function craftLabel(value) { return CRAFT_LABELS[craftKey(value)]; }
  function count(value) { return typeof value === "number" && Number.isSafeInteger(value) && value >= 0 ? value : null; }
  function cellMetrics(input) {
    input = input || {};
    const n = count(input.count), rowN = count(input.rowTotalN), columnN = count(input.columnTotalN), totalN = count(input.totalN);
    const impossible = n != null && rowN != null && n > rowN || n != null && columnN != null && n > columnN
      || rowN != null && totalN != null && rowN > totalN || columnN != null && totalN != null && columnN > totalN
      || n != null && rowN != null && columnN != null && totalN != null && n < Math.max(0, rowN + columnN - totalN);
    if (impossible) return { share: null, baselineShare: null, deltaPp: null };
    const share = n != null && rowN > 0 ? n / rowN : null;
    const baselineShare = columnN != null && totalN > 0 ? columnN / totalN : null;
    return { share, baselineShare, deltaPp: share != null && baselineShare != null ? (share - baselineShare) * 100 : null };
  }
  function knownKey(value) {
    const key = String(value == null ? "" : value).trim();
    return key && !/^(?:__|unknown(?:$|[_\s/])|not[_\s]indexed(?:$|[_\s])|unavailable(?:$|[_\s]))/i.test(key);
  }
  function axis(value, name) {
    const totals = value && value[name === "rows" ? "rowTotals" : "columnTotals"];
    const direct = value && value[name];
    return (Array.isArray(totals) ? totals : Array.isArray(direct) ? direct : []).map(item => ({ key: String(item.key),
      label: String(item.label == null ? item.key : item.label), totalN: count(item.count == null ? item.totalN : item.count) }));
  }
  function threshold(value, fallback, maximum) {
    const n = count(value);
    return n == null ? fallback : Math.min(maximum, n);
  }
  function deriveHighlights(card, value, options) {
    card = card || {}; value = value || {}; options = options || {};
    const totalN = count(value.totalN), limit = threshold(options.limit, 2, 10), minRowN = threshold(options.minRowN, 20, Number.MAX_SAFE_INTEGER),
      minCount = threshold(options.minCount, 5, Number.MAX_SAFE_INTEGER), rows = axis(value, "rows"), columns = axis(value, "columns");
    const unavailable = (reasonCode, reason) => ({ status: "insufficient_support", reasonCode, reason, highlights: [] });
    if (limit === 0) return { status: "ready", reasonCode: "disabled", reason: "Descriptive highlights are hidden for this view.", highlights: [] };
    if (value.available === false || totalN == null || totalN <= 0) return unavailable("population_unavailable", "No supported report population is available for descriptive contrasts.");
    const knownRows = rows.filter(item => knownKey(item.key) && item.totalN != null && item.totalN > 0 && item.totalN <= totalN);
    if (knownRows.length < 2) return unavailable("insufficient_groups", "At least two named groups with report counts are needed for descriptive contrasts.");
    const knownColumns = columns.filter(item => knownKey(item.key) && item.totalN != null && item.totalN > 0 && item.totalN <= totalN);
    const cells = new Map(), sparse = Array.isArray(value.cells);
    if (Array.isArray(value.cells)) value.cells.forEach(item => cells.set(JSON.stringify([String(item.rowKey), String(item.columnKey)]), count(item.count)));
    else if (Array.isArray(value.rows)) {
      const directColumns = Array.isArray(value.columns) ? value.columns : columns;
      value.rows.forEach(row => directColumns.forEach((column, index) => {
        const n = Array.isArray(row.counts) ? count(row.counts[index]) : null;
        cells.set(JSON.stringify([String(row.key), String(column.key)]), n);
      }));
    }
    const highlights = [];
    let supportedCells = 0;
    const rank = (a, b) => Math.abs(b.deltaPp) - Math.abs(a.deltaPp) || b.count - a.count || a.rowKey.localeCompare(b.rowKey, "en") || a.columnKey.localeCompare(b.columnKey, "en");
    knownRows.forEach(row => {
      if (row.totalN < minRowN) return;
      knownColumns.forEach(column => {
        const key = JSON.stringify([row.key, column.key]), n = cells.has(key) ? cells.get(key) : sparse ? 0 : null;
        // Sparse absent cells mean zero, but unknown/malformed counts are never
        // silently converted into an observed zero or a highlighted contrast.
        if (n == null || n < minCount) return;
        const metrics = cellMetrics({ count: n, rowTotalN: row.totalN, columnTotalN: column.totalN, totalN });
        if (metrics.deltaPp == null) return;
        supportedCells += 1;
        if (Math.abs(metrics.deltaPp) <= 1e-12 || limit === 0) return;
        highlights.push({ rowKey: row.key, rowLabel: row.label, columnKey: column.key, columnLabel: column.label,
          count: n, rowTotalN: row.totalN, columnTotalN: column.totalN, totalN, ...metrics, multiLabel: card.multiLabel === true,
          unit: "report representations", descriptive: true });
        highlights.sort(rank); if (highlights.length > limit) highlights.pop();
      });
    });
    if (!highlights.length) return unavailable(supportedCells ? "no_contrasts" : "insufficient_counts", supportedCells
      ? "Supported groups have no nonzero composition differences from the pooled report share."
      : "Descriptive contrasts require at least " + minRowN + " row reports and " + minCount + " reports in a named category cell.");
    return { status: "ready", reasonCode: "", reason: "", highlights };
  }
  function compute(card, value, options) {
    value = value || {};
    const totalN = count(value.totalN), baselineByColumn = Object.create(null);
    axis(value, "columns").forEach(item => { baselineByColumn[item.key] = cellMetrics({ columnTotalN: item.totalN, totalN }).baselineShare; });
    const result = deriveHighlights(card, value, options);
    return { baselineByColumn, highlights: result.highlights, highlightStatus: result.status, highlightReason: result.reason,
      highlightReasonCode: result.reasonCode, note: "Differences are row shares minus pooled category shares in the same report lens, in percentage points. They are descriptive, not statistical significance or causal effects." };
  }
  return Object.freeze({ CRAFT_PALETTE, CRAFT_COLORS, CRAFT_LABELS, craftKey, craftColor, craftLabel, cellMetrics, deriveHighlights, compute });
});

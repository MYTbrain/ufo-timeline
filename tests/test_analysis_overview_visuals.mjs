import assert from "node:assert/strict";
import { createRequire } from "node:module";
import fs from "node:fs";
import vm from "node:vm";
const require = createRequire(import.meta.url);
const Visuals = require("../analysis_overview_visuals.js"), Legend = require("../trace_neighborhood.js");
for (const key of Legend.CRAFT_TYPE_ORDER) {
  assert.equal(Visuals.craftColor(key), Legend.CRAFT_TYPE_COLORS[key], "Default legend color: " + key);
  assert.equal(Visuals.craftLabel(key), Legend.CRAFT_TYPE_LABELS[key]);
  assert.equal(Visuals.craftColor(Legend.CRAFT_TYPE_LABELS[key]), Legend.CRAFT_TYPE_COLORS[key], "Display labels resolve to the same stable palette");
}
assert.equal(Visuals.craftColor("A shape not in the reviewed taxonomy"), Legend.CRAFT_TYPE_COLORS.unknown);
assert.equal(Visuals.craftColor("__unknown__"), Legend.CRAFT_TYPE_COLORS.unknown);
assert.ok(Object.isFrozen(Visuals.CRAFT_PALETTE) && Visuals.CRAFT_PALETTE.every(Object.isFrozen));
assert.deepEqual(Visuals.cellMetrics({ count: 5, rowTotalN: 20, columnTotalN: 10, totalN: 100 }), { share: .25, baselineShare: .1, deltaPp: 15 });
assert.deepEqual(Visuals.cellMetrics({ count: 0, rowTotalN: 20, columnTotalN: 0, totalN: 100 }), { share: 0, baselineShare: 0, deltaPp: 0 });
assert.deepEqual(Visuals.cellMetrics({ count: 0, rowTotalN: 0, columnTotalN: 0, totalN: 0 }), { share: null, baselineShare: null, deltaPp: null });
assert.deepEqual(Visuals.cellMetrics({ count: null, rowTotalN: 20, columnTotalN: 10, totalN: 100 }), { share: null, baselineShare: .1, deltaPp: null });
assert.deepEqual(Visuals.cellMetrics({ count: 5, rowTotalN: 20, columnTotalN: null, totalN: 100 }), { share: .25, baselineShare: null, deltaPp: null });
assert.deepEqual(Visuals.cellMetrics({ count: "5", rowTotalN: 20, columnTotalN: 10, totalN: 100 }), { share: null, baselineShare: .1, deltaPp: null }, "Malformed numbers never become observations");
for (const input of [
  { count: 21, rowTotalN: 20, columnTotalN: 30, totalN: 100 },
  { count: 5, rowTotalN: 20, columnTotalN: 4, totalN: 100 },
  { count: 5, rowTotalN: 101, columnTotalN: 10, totalN: 100 },
  { count: 5, rowTotalN: 20, columnTotalN: 101, totalN: 100 },
  { count: 1, rowTotalN: 90, columnTotalN: 90, totalN: 100 },
]) assert.deepEqual(Visuals.cellMetrics(input), { share: null, baselineShare: null, deltaPp: null }, "Inconsistent denominators are not rendered as valid contrasts");
const boundary = Visuals.cellMetrics({ count: 80, rowTotalN: 90, columnTotalN: 90, totalN: 100 });
assert.equal(boundary.share, 80 / 90);
assert.equal(boundary.baselineShare, .9, "A feasible intersection at the exact marginal lower bound remains valid");
assert.ok(Math.abs(boundary.deltaPp - (80 / 90 - .9) * 100) < 1e-10);

const value = {
  totalN: 200,
  rowTotals: [{ key: "A", label: "First era", count: 150 }, { key: "B", label: "Second era", count: 50 }],
  columnTotals: [{ key: "x", label: "Category X", count: 80 }, { key: "y", label: "Category Y", count: 120 }],
  cells: [{ rowKey: "A", columnKey: "x", count: 40 }, { rowKey: "A", columnKey: "y", count: 110 },
    { rowKey: "B", columnKey: "x", count: 40 }, { rowKey: "B", columnKey: "y", count: 10 }],
};
let result = Visuals.deriveHighlights({}, value);
assert.equal(result.status, "ready");
assert.equal(result.highlights.length, 2);
assert.deepEqual(result.highlights.map(item => [item.rowKey, item.columnKey, item.count]), [["B", "x", 40], ["B", "y", 10]]);
assert.ok(Math.abs(result.highlights[0].deltaPp - 40) < 1e-10);
assert.ok(Math.abs(result.highlights[1].deltaPp + 40) < 1e-10, "Descriptive highlights can be above or below pooled composition");
assert.equal(result.highlights[0].rowTotalN, 50);
assert.equal(result.highlights[0].columnTotalN, 80);
assert.equal(result.highlights[0].totalN, 200);
assert.equal(result.highlights[0].descriptive, true);
assert.equal(result.highlights[0].unit, "report representations");
assert.deepEqual(Visuals.deriveHighlights({}, { ...value, rowTotals: value.rowTotals.slice().reverse(), columnTotals: value.columnTotals.slice().reverse(), cells: value.cells.slice().reverse() }), result,
  "Top contrasts and ties are independent of source iteration order");
const compact = Visuals.compute({}, value);
assert.equal(compact.baselineByColumn.x, .4);
assert.equal(compact.baselineByColumn.y, .6);
assert.deepEqual(compact.highlights, result.highlights);
assert.match(compact.note, /not statistical significance or causal effects/);

const overlaps = { totalN: 100,
  rowTotals: [{ key: "grey", label: "Grey", count: 70 }, { key: "humanoid", label: "Humanoid", count: 60 }, { key: "__not_indexed__", label: "Not indexed", count: 10 }],
  columnTotals: [{ key: "disc_saucer", label: "Disc / saucer", count: 60 }, { key: "triangle", label: "Triangle", count: 40 }],
  cells: [{ rowKey: "grey", columnKey: "disc_saucer", count: 50 }, { rowKey: "grey", columnKey: "triangle", count: 20 },
    { rowKey: "humanoid", columnKey: "disc_saucer", count: 30 }, { rowKey: "humanoid", columnKey: "triangle", count: 30 },
    { rowKey: "__not_indexed__", columnKey: "disc_saucer", count: 10 }],
};
const overlapping = Visuals.compute({ multiLabel: true }, overlaps);
assert.equal(overlapping.baselineByColumn.disc_saucer, .6, "Multi-label row memberships do not inflate the pooled report denominator");
assert.equal(overlapping.highlights[0].multiLabel, true);
assert.ok(overlapping.highlights.every(item => !item.rowKey.startsWith("__")));

const missing = { totalN: 100,
  rowTotals: [{ key: "A", count: 40 }, { key: "B", count: 40 }, { key: "__unknown__", count: 20 }],
  columnTotals: [{ key: "x", count: 60 }, { key: "__unavailable__", count: 40 }],
  cells: [{ rowKey: "A", columnKey: "x", count: 20 }, { rowKey: "A", columnKey: "__unavailable__", count: 20 },
    { rowKey: "B", columnKey: "x", count: 20 }, { rowKey: "B", columnKey: "__unavailable__", count: 20 },
    { rowKey: "__unknown__", columnKey: "x", count: 20 }],
};
result = Visuals.deriveHighlights({}, missing);
assert.equal(result.highlights[0].baselineShare, .6, "Unknown rows remain in the pooled population and category total");
assert.equal(result.highlights[0].share, .5);
assert.ok(result.highlights.every(item => !item.rowKey.startsWith("__") && !item.columnKey.startsWith("__")));

assert.equal(Visuals.deriveHighlights({}, { totalN: 0 }).reasonCode, "population_unavailable");
assert.equal(Visuals.deriveHighlights({}, { ...value, available: false }).reasonCode, "population_unavailable");
assert.equal(Visuals.deriveHighlights({}, { ...value, rowTotals: value.rowTotals.slice(0, 1) }).reasonCode, "insufficient_groups");
assert.equal(Visuals.deriveHighlights({}, value, { minRowN: 201 }).reasonCode, "insufficient_counts");
assert.equal(Visuals.deriveHighlights({}, value, { minCount: 121 }).reasonCode, "insufficient_counts");
assert.equal(Visuals.deriveHighlights({}, value, { limit: 0 }).reasonCode, "disabled");
const uniform = { totalN: 100, rowTotals: [{ key: "A", count: 50 }, { key: "B", count: 50 }], columnTotals: [{ key: "x", count: 100 }],
  cells: [{ rowKey: "A", columnKey: "x", count: 50 }, { rowKey: "B", columnKey: "x", count: 50 }] };
assert.equal(Visuals.deriveHighlights({}, uniform).reasonCode, "no_contrasts");
assert.match(Visuals.deriveHighlights({}, value, { minRowN: 201 }).reason, /201 row reports/);

// Dense fallback and the sparse model have the same exact full-lane baseline.
const dense = { totalN: 200, columns: value.columnTotals.map(item => ({ key: item.key, label: item.label, totalN: item.count })),
  rows: [{ key: "A", label: "First era", totalN: 150, counts: [40, 110] }, { key: "B", label: "Second era", totalN: 50, counts: [40, 10] }] };
assert.deepEqual(Visuals.deriveHighlights({}, dense), Visuals.deriveHighlights({}, value));
assert.equal(Visuals.compute({}, { totalN: 100, columns: [{ key: "x", totalN: null }] }).baselineByColumn.x, null);

const scope = {};
vm.runInNewContext(fs.readFileSync(new URL("../analysis_overview_visuals.js", import.meta.url), "utf8"), scope);
assert.equal(typeof scope.UfoAnalysisOverviewVisuals.cellMetrics, "function");
console.log("Analysis overview visual helpers passed.");

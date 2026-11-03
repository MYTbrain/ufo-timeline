import assert from "node:assert/strict";
import test from "node:test";
import starterCases from "../landing_site_cases.js";
import expandedCases from "../landing_site_expanded_cases.js";
import earlyCases from "../landing_site_phillips_early_cases.js";
import lateCases from "../landing_site_phillips_late_cases.js";
import directCases from "../landing_site_direct_reviewed_cases.js";
import australianReviewed from "../landing_site_australian_reviewed_cases.js";
import historicalReviewed from "../landing_site_historical_reviewed_cases.js";
import ufocatReviewed from "../landing_site_ufocat_reviewed_cases.js";
import analysis from "../landing_site_analysis.js";
import phillips from "../landing_site_phillips_catalog.js";
import comparison from "../landing_site_comparison.js";
import other from "../landing_site_other_catalog.js";
import australian from "../landing_site_australian_catalog.js";
import audit from "../landing_site_review_audit.js";

const cases = [...starterCases, ...expandedCases, ...earlyCases, ...lateCases,
  ...directCases, ...australianReviewed, ...historicalReviewed, ...ufocatReviewed];

test("trace filters preserve the distinct traces in a mixed case", () => {
  const scorchCases = analysis.casesWithTrace(cases, "scorching");
  const socorro = scorchCases.find((site) => site.id === "socorro");
  assert.ok(socorro.traces.some((trace) => trace.kind === "impression"));
  assert.ok(socorro.traces.some((trace) => trace.kind === "scorching"));
  assert.ok(!scorchCases.some((site) => site.id === "tully"));
  assert.ok(analysis.casesWithTrace(cases, "deformation").some((site) => site.id === "tully"));
});

test("measurements distinguish edge variation, patch elongation, and ring diameters", () => {
  const socorro = cases.find((site) => site.id === "socorro");
  const edges = socorro.traces.find((trace) => trace.pattern?.edgesM).pattern.edgesM;
  assert.equal(edges.length, 4);
  assert.ok(Math.abs(analysis.edgeSpread(edges) - 41.75) < 0.1);
  assert.equal(analysis.edgeSpread([2, 2, 2, 2]), 0);
  assert.equal(analysis.edgeSpread([2, 2, -1]), null);

  const tully = cases.find((site) => site.id === "tully");
  const tullySpan = analysis.spanMetrics(tully.traces[0].pattern.dimensions);
  assert.ok(Math.abs(tullySpan.aspectRatio - 1.28) < 0.01);
  assert.equal(analysis.spanMetrics({ longM: 2, shortM: 0 }), null);
  const trans = cases.find((site) => site.id === "trans_provence");
  assert.equal(analysis.spanMetrics(trans.traces[0].pattern.dimensions), null);
});

test("each trace resolves to a source and locator in its own case", () => {
  const traceKinds = new Set(["impression", "scorching", "deformation", "surface"]);
  const patternBases = new Set(["description", "dimensions"]);
  const layoutFamilies = new Set(["three_point", "four_point", "ring", "oval", "radial", "opposed", "rows",
    "swirl", "twist", "irregular", "isolated"]);
  assert.equal(new Set(cases.map((site) => site.id)).size, cases.length);
  for (const site of cases) {
    assert.ok(Number.isFinite(Date.parse(site.date)), site.id);
    assert.equal(new Set(site.sources.map((source) => source.id)).size, site.sources.length);
    for (const source of site.sources) {
      assert.equal(new URL(source.url).protocol, "https:");
      assert.ok(source.locator);
    }
    for (const trace of site.traces) {
      assert.ok(traceKinds.has(trace.kind));
      assert.ok(trace.sourceIds.length);
      assert.ok(trace.sourceIds.every((id) => site.sources.some((source) => source.id === id)));
      if (trace.pattern) {
        assert.ok(patternBases.has(trace.pattern.basis));
        assert.ok((trace.pattern.families || []).every((family) => layoutFamilies.has(family)), site.id);
      }
    }
  }
});

test("each plotted layer has matching trace evidence and diagram-specific sources", () => {
  for (const site of cases.filter(({ diagram }) => diagram)) {
    const { diagram } = site;
    const [left, top, width, height] = diagram.viewBox;
    assert.ok(diagram.title && diagram.basis && diagram.note, site.id);
    assert.ok(diagram.viewBox.every(Number.isFinite) && width > 0 && height > 0, site.id);
    assert.equal(new Set(diagram.layers.map((layer) => layer.label)).size, diagram.layers.length, site.id);
    for (const layer of diagram.layers) {
      assert.ok(site.traces.some((trace) => trace.kind === layer.kind), site.id);
      if (layer.channel) assert.ok(site.traces.some((trace) =>
        trace.kind === layer.kind && comparison.traceLane(trace) === layer.channel), site.id);
      assert.ok(layer.sourceIds.length && layer.sourceIds.every((id) =>
        site.sources.some((source) => source.id === id)), site.id);
      assert.ok(layer.marks.length, site.id);
      for (const mark of layer.marks) {
        assert.ok(mark.label, site.id);
        if (mark.type === "path") {
          assert.match(mark.d, /^[Mm]\s*[-.\d]/, site.id);
        } else {
          assert.ok(["point", "ellipse"].includes(mark.type), site.id);
          assert.ok(mark.x > left && mark.x < left + width && mark.y > top && mark.y < top + height, site.id);
        }
      }
    }
  }
});

test("co-located traces stay distinct and uncertain overlap is represented once", () => {
  const socorro = cases.find((site) => site.id === "socorro");
  assert.deepEqual(socorro.diagram.layers.map(({ kind, marks }) => [kind, marks.length]),
    [["impression", 4], ["scorching", 4]]);
  const dechmont = cases.find((site) => site.id === "dechmont");
  assert.deepEqual(dechmont.diagram.layers.map(({ kind, marks }) => [kind, marks.length]),
    [["deformation", 2], ["impression", 40]]);
  const anten = cases.find((site) => site.id === "lake_anten");
  assert.deepEqual(anten.diagram.layers.map(({ kind, marks }) => [kind, marks.length]), [["scorching", 3]]);
  const rendlesham = cases.find((site) => site.id === "rendlesham");
  assert.equal(rendlesham.diagram, undefined);
});

test("Phillips filters combine place, source category, trace type and layout leads", () => {
  const rows = [
    { id: 7, page: 25, date: "1960-05", location: "São Paulo, Brazil", kind: "trace_discovery", traces: ["deformation"], patterns: ["swirl"] },
    { id: 17, page: 26, date: "1960-05-07", location: "São Paulo, Brazil", kind: "sighting_trace", traces: ["scorching"], patterns: ["circular"] },
    { id: 70, page: null, date: null, location: null, kind: "unclear", traces: [], patterns: [] },
  ];
  assert.deepEqual(analysis.filterCatalog(rows, "#7", "", "", ""), [rows[0]]);
  assert.deepEqual(analysis.filterCatalog(rows, "sao brazil 1960", "sighting_trace", "scorching", "circular"), [rows[1]]);
  assert.deepEqual(analysis.filterCatalog(rows, "SÃO", "trace_discovery", "deformation", "circular"), []);
  assert.deepEqual(analysis.filterCatalog(rows, "", "unclear", "", ""), [rows[2]]);
  assert.deepEqual(analysis.filterCatalog(rows, "", "", "", "", "citation"), [rows[2]]);
});

test("Phillips scan locators are unique and individually checked dossiers resolve to the same pages", () => {
  const { source, rows } = phillips;
  const byId = new Map(rows.map((row) => [row.id, row]));
  assert.equal(byId.size, rows.length);
  assert.ok(rows.filter((row) => row.page).length > 500);
  assert.ok(rows.every(({ id, page }) => Number.isInteger(id) && id >= 1 &&
    id <= source.declaredCount && (page === null || (Number.isInteger(page) && page >= 19 && page <= 129))));
  for (const site of cases.filter((entry) => entry.phillipsCaseNumber)) {
    const row = byId.get(site.phillipsCaseNumber);
    assert.ok(row?.page, site.id);
    assert.ok(site.sources.some(({ url }) => url === source.url + "#page=" + row.page), site.id);
  }
});

test("combined analysis separates twist and co-location, and counts each case once per cell", () => {
  const ring = { kind: "scorching", pattern: { basis: "dimensions", families: ["ring", "ring"] } };
  const swirl = { kind: "deformation", pattern: { basis: "description", families: ["swirl"], handedness: "counterclockwise" } };
  const grass = { kind: "deformation", pattern: { basis: "dimensions", families: ["rows"] } };
  const sites = [
    { id: "a", phillipsCaseNumber: 1, traces: [ring, ring, swirl], diagram: { layers: [{ kind: "scorching" }, { kind: "deformation" }] } },
    { id: "b", traces: [ring, grass] },
  ];
  const all = comparison.analyze(sites);
  assert.equal(all.byLayout.get("ring").get("scorching").size, 2);
  assert.equal(all.byLane.get("twist").size, 1);
  assert.equal(all.byLane.get("deformation").size, 1);
  assert.ok(all.byDirection.get("counterclockwise").has("a"));
  const pair = all.pairs.find(({ left, right }) => left.id === "scorching" && right.id === "twist");
  assert.deepEqual(pair.shared.map(({ site }) => site.id), ["a"]);
  assert.deepEqual(pair.sharedPlans.map(({ site }) => site.id), ["a"]);
  assert.equal(comparison.analyze(sites, { dimensionsOnly: true }).byLane.get("twist").size, 0);
  assert.deepEqual(comparison.analyze(sites, { source: "other" }).selected.map(({ id }) => id), ["b"]);
});

test("additional inventories retain separate source locators and screening bases", () => {
  const rows = [...other.rows, ...australian.rows];
  assert.equal(new Set(rows.map(({ id }) => id)).size, rows.length);
  assert.ok(rows.length > 1500);
  assert.equal(australian.rows.length, 153);
  assert.ok(rows.every(({ source, evidenceBasis }) => source?.key && source.locator &&
    new URL(source.url).protocol === "https:" && ["described_trace", "classification_only", "catalog_only"].includes(evidenceBasis)));
  const screened = analysis.filterCatalog(rows, "", "", "", "", "", "basterfield", "described_trace");
  assert.ok(screened.length > 0 && screened.every(({ source }) => source.key === "basterfield"));
});

test("all 1541 review dispositions retain exact case and candidate links separately", () => {
  const rows = [...other.rows, ...australian.rows];
  const caseById = new Map(cases.map((site) => [site.id, site]));
  assert.equal(caseById.size, cases.length);
  assert.deepEqual(Object.keys(audit.records).sort(), rows.map(({ id }) => id).sort());
  for (const [id, entry] of Object.entries(audit.records)) {
    if (entry.caseId) assert.ok(caseById.has(entry.caseId), id + " → " + entry.caseId);
    if (entry.geometry === "diagram") assert.ok(caseById.get(entry.caseId)?.diagram, id);
    if (entry.possibleMatches) assert.ok(entry.possibleMatches.every((peer) => peer !== id &&
      (audit.records[peer] || /^Phillips #\d+$/.test(peer))), id);
  }
  for (const site of cases.filter(({ inventoryIds }) => inventoryIds?.length)) {
    assert.ok(site.inventoryIds.every((id) => audit.records[id]?.caseId === site.id), site.id);
  }
});

test("distinct mapped grass lay and twist layers support independent comparison", () => {
  const model = comparison.analyze(directCases, { origin: "original" });
  const pair = model.pairs.find(({ left, right }) => left.id === "twist" && right.id === "deformation");
  assert.ok(pair.sharedPlans.some(({ site }) => site.id === "porcieu_amblagnieu"));
  assert.ok(!model.byLane.get("scorching").has("titusville_yard_ring"));
});

test("Phillips original checks link existing dossiers and preserve the additional inventory denominator", () => {
  const byId = new Map(cases.map((site) => [site.id, site]));
  const indexed = new Set(phillips.rows.map(({ id }) => String(id)));
  for (const [id, entry] of Object.entries(audit.phillipsRecords)) {
    assert.ok(indexed.has(id), id);
    if (entry.caseId) assert.ok(byId.has(entry.caseId), id);
    if (entry.geometry === "diagram") assert.ok(byId.get(entry.caseId)?.diagram, id);
  }
  assert.equal(audit.phillipsRecords[167].caseId, "socorro");
  assert.equal(audit.phillipsRecords[820].caseId, "donnybrook_north_dakota");
  const filtered = comparison.analyze(cases, {
    source: "phillips", phillipsCaseIds: new Set(Object.values(audit.phillipsRecords).map(({ caseId }) => caseId)),
  }).selected;
  assert.equal(filtered.filter(({ id }) => id === "socorro").length, 1);
  assert.equal(Object.keys(audit.records).length, 1541);
});

test("new field plans register only the traces plotted in their source", () => {
  const dale = cases.find(({ id }) => id === "dale_englebrecht");
  assert.deepEqual(dale.diagram.layers.map(({ kind }) => kind), ["impression", "scorching"]);
  assert.equal(comparison.traceLane(dale.traces[2]), "twist");
  const churchill = cases.find(({ id }) => id === "churchill_park");
  assert.equal(churchill.diagram.layers.filter(({ kind }) => kind === "impression").length, 2);
  const pair = comparison.analyze([churchill]).pairs.find(({ left, right }) =>
    left.id === "impression" && right.id === "surface");
  assert.equal(pair.sharedPlans.length, 1);
});

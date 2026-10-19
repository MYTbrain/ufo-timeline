import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const { readinessMatrix, AnalysisViewController } = require("../analysis_view.js");
const Model = require("../analysis_readiness_model.js");

// The real release is a 90KB manifest. No catalog or relationship rows are
// required to reconcile readiness counts and typed policy metadata.
const manifest = JSON.parse(fs.readFileSync("data/analysis_v2/manifest.json", "utf8"));
const fixture = JSON.parse(fs.readFileSync("docs/qa/evidence-gates-20261019/readiness-audit.json", "utf8"));
const source = fs.readFileSync("catalog_filter_worker.js", "utf8");
const start = source.indexOf("  function spatialReadinessFromManifest(manifest) {");
const end = source.indexOf("  function spatialEligibilityFunnelFromManifest", start);
assert.ok(start > 0 && end > start);
const relationshipBaseline = fixture.lanes.find(row => row.key === "relationshipReconciliation");
const relationshipGate = fixture.gateDefinitions.relationship_reconciliation;
const context = vm.createContext({
  analysisSpatialArtifacts: { artifactHashes: {} },
  relationshipReconciliationReadiness() {
    return { ...relationshipBaseline, totalN: relationshipBaseline.totalN,
      reconciledN: relationshipGate.passedN, gates: relationshipBaseline.gateIds.map(key => fixture.gateDefinitions[key]) };
  },
});
vm.runInContext(source.slice(start, end), context);
const frozenManifest = JSON.stringify(manifest);
const rows = JSON.parse(JSON.stringify(context.spatialReadinessFromManifest(manifest)));
assert.equal(JSON.stringify(manifest), frozenManifest, "Annotating display contracts does not mutate the pinned release");
assert.equal(Object.keys(rows).length, 11);
for (const baseline of fixture.lanes) {
  const row = rows[baseline.key];
  for (const key of ["status", "eligibleN", "totalN", "inputN", "passedN", "failedN", "unknownN"])
    assert.equal(row[key], baseline[key], `${baseline.key}/${key}: eligibility and evidence status remain unchanged`);
  for (const gate of row.gates) {
    const expected = fixture.gateDefinitions[gate.gateId];
    for (const key of ["status", "inputN", "passedN", "failedN", "unknownN", "policyId"])
      assert.equal(gate[key], expected[key], `${baseline.key}/${gate.gateId}/${key}: no evidence gate is promoted`);
  }
}
assert.equal(rows.crop_strict.evidenceAudit.minimumStrictClusters, 25);
assert.equal(rows.crop_strict.evidenceAudit.cohortBalance.policy.minimumStrictUniqueClusters, 100);
assert.equal(rows.crop_strict.evidenceAudit.cohortBalance.strictUniqueClusters, 1);
assert.equal(rows.animal_strict.evidenceAudit.cohortBalance.strictUniqueClusters, 0);
assert.equal(rows.cropBounded.evidenceAudit.exclusionReasonsOverlap, true);
assert.equal(rows.cropBounded.evidenceAudit.leadingExclusionReasons[0].count, 7738);
assert.deepEqual(rows.crop_strict.gates.find(g => g.gateId === "crop_exact_site_formation_date").inputUnit, "catalog_records");
assert.deepEqual(rows.crop_strict.gates.find(g => g.gateId === "crop_exact_site_formation_date").passedUnit, "location_date_clusters");
const spatial = require("../analysis_spatial.js");
const fullSpatialRows = spatial.contextReadiness(rows);
for (const key of ["cropBounded", "cropLocality", "cropCircles", "animalReports"]) {
  const row = fullSpatialRows.find(value => value.key === key);
  assert.deepEqual(row.evidenceAudit, rows[key].evidenceAudit,
    `${key}: full Spatial refresh retains release audit metadata from context-only loading`);
  assert.deepEqual(row.gates.map(g => [g.gateId, g.inputUnit, g.passedUnit]), rows[key].gates.map(g => [g.gateId, g.inputUnit, g.passedUnit]));
}

const matrix = readinessMatrix(rows);
const cropBounded = matrix.rows.find(row => row.item.key === "cropBounded");
assert.equal(cropBounded.cells.find(cell => cell.key === "sample").status, "not_applicable");
assert.equal(cropBounded.cells.find(cell => cell.key === "review").value, "Other lane");
assert.equal(cropBounded.detailedGates.find(gate => gate.key === "crop_strict_balanced_cohort").applicableToLane, false);
assert.equal(cropBounded.detailedGates.find(gate => gate.key === "crop_bounded_marker_lane").applicableToLane, true);
const animal = matrix.rows.find(row => row.item.key === "animal_strict");
assert.equal(animal.cells.find(cell => cell.key === "date").representativeGateId, "animal_exact_site_reviewed",
  "The documented joint animal site/date/review gate is represented under Date");
const unknownGate = readinessMatrix([{ ...rows.cropBounded, gates: rows.cropBounded.gates.concat({ gateId: "future_typed_rule", status: "blocked", inputN: 10, passedN: 0 }) }]);
assert.equal(unknownGate.rows[0].detailedGates.find(gate => gate.key === "future_typed_rule").applicableToLane, true,
  "Unrecognized new requirements are retained for review rather than silently suppressed");

const model = Model.compute(matrix, { scope: { kind: "release_inventory", activeQueryReports: 519, activeQualifiedEndpoints: 0 } });
const lane = key => model.groups.flatMap(group => group.lanes).find(item => item.key === key);
assert.equal(lane("cropBounded").actualBlockedGates.length, 0, "Strict research limits do not block the available bounded-marker lane");
assert.equal(lane("crop_strict").retention.share, null, "Clusters and raw catalog records never create a retention percentage");
assert.equal(lane("crop_strict").applicableGates.find(gate => gate.key === "crop_exact_site_formation_date").retention.share, null);
assert.equal(lane("crop_strict").applicableGates.find(gate => gate.key === "crop_strict_context_clusters").status, "blocked");
assert.equal(lane("crop_strict").minimumStrictClusters, 25);
assert.equal(lane("crop_strict").cohortBalance.policy.minimumStrictUniqueClusters, 100);
assert.equal(lane("cropCircles").aggregateSummary, true);
assert.equal(lane("militaryFacilities").sharedInventoryKey, lane("researchFacilities").sharedInventoryKey);
assert.equal(lane("claimedUfoSites").policyExcludedFromInference, true);
assert.equal(lane("claimedUfoSites").eligible, 0); assert.equal(lane("claimedUfoSites").total, 11);
assert.equal(model.scope.activeQualifiedEndpoints, 0);

// Exercise the actual native renderer hook with a small view boundary. The
// fixed release inventory never acquires active counts from the toolbar.
const controller = Object.create(AnalysisViewController.prototype), host = {}, renders = [], revealed = [];
let created = 0, configuration;
Object.assign(controller, { documentView: { UfoAnalysisReadinessView: { create(target, config) {
  assert.equal(target, host); created += 1; configuration = config;
  return { render(input) { renders.push(input); } };
} } }, _prepareChart() { return host; }, _openSupportingChart(id) { revealed.push(id); }, _openOverviewChart(section) { revealed.push(section); } });
controller._renderReadiness("analysis-cross-domain-readiness-chart", rows, { activeCount: 123 });
assert.equal(renders[0].scope.activeQueryReports, null);
controller._renderReadiness("analysis-cross-domain-readiness-chart", rows, { activeCount: 123 },
  { scope: { kind: "release_inventory", activeQueryReports: 519, activeQualifiedEndpoints: 0 } });
assert.equal(created, 1, "A new result reuses the inspector and its selected lane");
assert.equal(renders[1].scope.activeQueryReports, 519); assert.equal(renders[1].scope.activeQualifiedEndpoints, 0);
configuration.onOpenSection("relationships"); assert.equal(revealed.at(-1), "analysis-relationship-readiness-chart");
configuration.onOpenSection("crops"); assert.equal(revealed.at(-1), "crops");
const markup = fs.readFileSync("index.html", "utf8");
assert.ok(markup.indexOf('./analysis_readiness_model.js?') < markup.indexOf('./analysis_readiness_view.js?'));
assert.match(markup, /<script defer src="\.\/analysis_readiness_model\.js\?/);
assert.match(markup, /<script defer src="\.\/analysis_readiness_view\.js\?/);
console.log("Evidence readiness integration: pinned counts, lane applicability, joint dates, units, targets, active scope and native navigation passed.");

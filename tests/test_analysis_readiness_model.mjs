import assert from "node:assert/strict";
import { createRequire } from "node:module";
import fs from "node:fs";
import vm from "node:vm";
const require = createRequire(import.meta.url), Model = require("../analysis_readiness_model.js"), { readinessMatrix } = require("../analysis_view.js");
const gate = (gateId, inputN, passedN, status, extra = {}) => ({ gateId, label: gateId, status, inputN, passedN,
  inputUnit: "catalog_records", passedUnit: "catalog_records",
  policyId: "preserved_policy_v1", evidenceHash: "abc123", reasonCodes: status === "blocked" ? ["minimum_cluster_count_not_met"] : [], ...extra });
const facilityGates = [gate("facility_descriptive_inventory", 1800, 1800, "ready_descriptive"), gate("facility_inferential_markers", 1800, 70, "limited")];
const source = [
  { key: "ufoCraftPoints", label: "High-precision report pool", status: "ready_inferential", eligibleN: 33800, totalN: 702893,
    gates: [gate("source_coordinates", 702893, 582877, "ready_inferential"), gate("coordinate_piles", 39047, 33800, "ready_inferential")] },
  { key: "crop_strict", label: "Crop circles — strict", status: "blocked", eligibleN: 1, totalN: 7745,
    evidenceAudit: { scope: "release_inventory", eligibleUnit: "location_date_clusters", inventoryUnit: "catalog_records", minimumStrictClusters: 25,
      cohortBalance: { policy: { minimumStrictUniqueClusters: 100, minimumSourceFamilies: 2 } }, leadingExclusionReasons: [{ reasonCode: "formation_date_missing", count: 7000 }] },
    gates: [gate("crop_exact_site_formation_date", 7745, 1, "blocked", { passedUnit: "location_date_clusters" }),
      gate("crop_strict_context_clusters", 1, 1, "blocked", { inputUnit: "location_date_clusters", passedUnit: "location_date_clusters" }),
      gate("crop_strict_balanced_cohort", 1, 0, "blocked", { inputUnit: "location_date_clusters", passedUnit: "location_date_clusters" })] },
  { key: "cropBounded", label: "Crop circles — bounded", status: "ready_sensitivity", eligibleN: 427, totalN: 7745,
    gates: [gate("crop_bounded_marker_lane", 7745, 427, "ready_sensitivity"), gate("crop_exact_site_formation_date", 7745, 1, "blocked", { applicableToLane: false })] },
  { key: "cropLocality", label: "Crop circles — locality", status: "ready_sensitivity", eligibleN: 3225, totalN: 7745,
    gates: [gate("crop_locality_marker_lane", 7745, 3225, "ready_sensitivity")] },
  { key: "cropCircles", label: "Crop marker aggregate", status: "ready_sensitivity", eligibleN: 3652, totalN: 7745, gates: [] },
  { key: "animal_strict", label: "Animal reports — strict", status: "blocked", eligibleN: 0, totalN: 1184,
    gates: [gate("animal_exact_site_reviewed", 1184, 0, "blocked"), gate("animal_strict_context_clusters", 0, 0, "blocked")] },
  { key: "militaryFacilities", label: "Military facilities", status: "limited", eligibleN: 70, totalN: 1800, gates: facilityGates },
  { key: "researchFacilities", label: "Research facilities", status: "limited", eligibleN: 70, totalN: 1800, gates: facilityGates },
  { key: "claimedUfoSites", label: "Claimed UFO sites", status: "ready_descriptive", eligibleN: 0, totalN: 11,
    reasonCodes: ["descriptive_only_prohibited_from_inference"], gates: [] },
  { key: "relationshipReconciliation", label: "Relationship review", status: "ready_descriptive", eligibleN: null, totalN: 1804,
    gates: [gate("relationship_descriptive_records", 1804, 1804, "ready_descriptive"), gate("relationship_reconciliation", 1804, 0, "not_evaluated")] },
  { key: "invented_key", label: "Crop circles and nuclear facilities", status: "data_unavailable", eligibleN: null, totalN: null, gates: [] },
];
const matrix = readinessMatrix(source), before = JSON.stringify(matrix);
const result = Model.compute(matrix, { scope: { kind: "release_inventory", label: "Release-wide evidence inventory", activeQueryReports: 15, activeQualifiedEndpoints: 2 } });
const lane = key => result.groups.flatMap(group => group.lanes).find(item => item.key === key);
assert.equal(result.laneN, 11);
assert.equal(result.unit, "analysis lanes");
assert.equal(Object.values(result.statusCounts).reduce((n, value) => n + value, 0), 11);
assert.equal(result.statusCounts.blocked, 2, "Status chips count lanes rather than duplicated matrix cells or gates");
assert.equal(result.statusCounts.ready_sensitivity, 3);
assert.equal(result.statusCounts.ready_inferential, 1);
assert.equal(result.scope.activeQueryReports, 15);
assert.equal(result.scope.activeQualifiedEndpoints, 2);
assert.equal(result.groups.find(group => group.key === "other").lanes[0].key, "invented_key", "Display prose cannot determine the domain group");
assert.equal(result.groups.find(group => group.key === "crops").lanes.length, 4);
assert.equal(result.groups.find(group => group.key === "facilities").lanes.length, 3);
assert.equal(lane("ufoCraftPoints").status, matrix.rows[0].cells.find(cell => cell.key === "overall").status);
assert.match(lane("ufoCraftPoints").notes.join(" "), /does not approve.*p-value/);
assert.equal(lane("crop_strict").eligible, 1);
assert.equal(lane("crop_strict").total, 7745);
assert.equal(lane("crop_strict").retention.share, null, "Unique clusters / raw records is not a record-retention percentage");
assert.equal(lane("crop_strict").retention.status, "unavailable");
assert.equal(lane("crop_strict").eligibleLabel, "Eligible unique context clusters");
assert.equal(lane("crop_strict").actualBlockedGateN, 3, "One joint gate shown in three columns remains one actual blocked gate");
assert.equal(lane("crop_strict").actualBlockedGates.filter(item => item.key === "crop_exact_site_formation_date").length, 1);
const cluster = lane("crop_strict").detailedGates.find(item => item.key === "crop_strict_context_clusters");
assert.equal(cluster.status, "blocked");
assert.equal(cluster.retention.share, 1, "Recorded gate retention is not a readiness score");
assert.equal(cluster.policyId, "preserved_policy_v1");
assert.equal(cluster.evidenceHash, "abc123");
assert.equal(cluster.gate, source[1].gates[1]);
assert.equal(lane("crop_strict").detailedGates.find(item => item.key === "crop_exact_site_formation_date").retention.share, null,
  "A named joint gate with output clusters and input records cannot become a percentage bar");
assert.equal(lane("crop_strict").minimumStrictClusters, 25);
assert.equal(lane("crop_strict").cohortBalance.policy.minimumStrictUniqueClusters, 100);
assert.equal(lane("crop_strict").leadingExclusionReasons[0].count, 7000);
assert.equal(lane("animal_strict").detailedGates.find(item => item.key === "animal_strict_context_clusters").retention.share, null, "0 / 0 is not 0% or 100%");
assert.equal(lane("cropCircles").aggregateSummary, true);
assert.equal(lane("cropBounded").detailedGates.length, 2);
assert.equal(lane("cropBounded").applicableGates.length, 1);
assert.equal(lane("cropBounded").actualBlockedGateN, 0, "A context-only strict test does not block the bounded-marker lane");
assert.equal(lane("cropBounded").detailedGates[1].status, "blocked", "Context-only gate status is preserved rather than relabeled");
assert.equal(lane("cropCircles").missingDefinitionN, 0, "An aggregate marker summary is not mislabeled as missing test definitions");
assert.ok(lane("cropCircles").cells.filter(cell => cell.status === "not_evaluated").length > 0, "The original summary matrix statuses remain intact");
assert.equal(lane("militaryFacilities").sharedInventoryKey, "facility_catalog");
assert.equal(lane("researchFacilities").sharedInventoryKey, "facility_catalog");
assert.equal(lane("militaryFacilities").total, 1800);
assert.equal(lane("researchFacilities").total, 1800);
assert.match(lane("militaryFacilities").notes.join(" "), /must not be added/);
assert.equal(lane("claimedUfoSites").total, 11);
assert.equal(lane("claimedUfoSites").eligible, 0);
assert.equal(lane("claimedUfoSites").retention.share, 0, "Actual zero inferential eligibility does not erase the descriptive inventory");
assert.equal(lane("claimedUfoSites").totalLabel, "Descriptive inventory records");
assert.equal(lane("claimedUfoSites").policyExcludedFromInference, true);
assert.equal(lane("relationshipReconciliation").unassessedGateN, 1);
assert.equal(lane("relationshipReconciliation").section, "relationships", "Relationship navigation opens the retained lineage analysis");
assert.equal(lane("relationshipReconciliation").eligibleLabel, "Association-eligible relationship records");
assert.equal(lane("relationshipReconciliation").reconciledRecords, 0, "Actual zero reconciliation passes are preserved from the typed gate");
assert.equal(lane("relationshipReconciliation").actualBlockedGateN, 0);
assert.equal(lane("invented_key").actualBlockedGateN, 0);
assert.ok(lane("invented_key").missingDefinitionN > 0, "An absent typed test stays distinct from a failed or unassessed defined test");
assert.equal(lane("relationshipReconciliation").retention.share, null);
assert.equal(lane("relationshipReconciliation").retention.status, "unavailable");
assert.equal(JSON.stringify(matrix), before, "No original gate, status, policy, hash, or source field is mutated");
assert.equal(result.totalRecords, undefined);
assert.equal(result.score, undefined);
assert.equal(result.funnel, undefined);
assert.match(result.notes.join(" "), /not datasets.*overall quality score/);
assert.match(result.notes.join(" "), /must not be pooled/);

const counts = Model.compute({ columns: [], typed: true, rows: [
  { label: "Real zero", eligible: 0, total: 100, item: { key: "zero" }, cells: [{ key: "overall", status: "blocked" }], detailedGates: [] },
  { label: "Empty", eligible: 0, total: 0, item: { key: "empty" }, cells: [{ key: "overall", status: "data_unavailable" }], detailedGates: [] },
  { label: "Bad count", eligible: "0", total: 100, item: { key: "bad" }, cells: [{ key: "overall", status: "blocked" }], detailedGates: [] },
  { label: "Impossible", eligible: 101, total: 100, item: { key: "impossible" }, cells: [{ key: "overall", status: "blocked" }], detailedGates: [] },
  { label: "New status", eligible: null, total: null, item: { key: "new" }, cells: [{ key: "overall", status: "new_raw_status" }], detailedGates: [] },
] });
const c = counts.groups[0].lanes;
assert.equal(c[0].retention.share, 0);
assert.equal(c[1].retention.share, null);
assert.equal(c[1].retention.status, "empty");
assert.equal(c[2].eligible, null);
assert.equal(c[2].rawCounts.eligible, "0");
assert.equal(c[2].retention.status, "invalid");
assert.equal(c[3].retention.status, "invalid");
assert.equal(c[4].status, "new_raw_status", "Unrecognized statuses are retained, never promoted to a known readiness class");
assert.equal(counts.statusCounts.new_raw_status, 1);
assert.equal(counts.scope.kind, "release_inventory");
assert.equal(counts.scope.activeQueryReports, null, "An active population is never inferred from lane inventories");
assert.equal(Model.compute(matrix, { scope: { activeQueryReports: 2, activeQualifiedEndpoints: 3 } }).scope.activeSupportStatus, "invalid");
assert.equal(Model.compute({ rows: [] }).laneN, 0);
const reconciliation = Model.compute(readinessMatrix([{ key: "relationshipReconciliation", label: "Relationship records", status: "ready_descriptive", eligibleN: 0, totalN: 1804,
  gates: [gate("relationship_reconciliation", 1804, 1320, "limited")] }]));
assert.equal(reconciliation.groups[0].lanes[0].reconciledRecords, 1320);
assert.equal(reconciliation.groups[0].lanes[0].eligible, 0, "Reconciliation does not alter association eligibility");
assert.equal(reconciliation.groups[0].lanes[0].total, 1804);

const differentUnits = Model.compute({ rows: [{ item: { key: "unit_fixture" }, cells: [{ key: "overall", status: "blocked" }], detailedGates: [{
  key: "unit_gate", label: "Different units", gate: { numeratorUnit: "clusters", denominatorUnit: "records" }, cell: { status: "blocked", counts: { passed: 1, input: 100 } },
}] }] });
assert.equal(differentUnits.groups[0].lanes[0].detailedGates[0].retention.share, null);
assert.equal(differentUnits.groups[0].lanes[0].detailedGates[0].retention.status, "unavailable");
const missingUnits = Model.compute({ rows: [{ item: { key: "unitless_fixture" }, cells: [{ key: "overall", status: "blocked" }], detailedGates: [{
  key: "unitless_gate", label: "Unit metadata absent", gate: {}, cell: { status: "blocked", counts: { passed: 1, input: 100 } },
}] }] });
assert.equal(missingUnits.groups[0].lanes[0].detailedGates[0].retention.share, null);
assert.match(missingUnits.groups[0].lanes[0].detailedGates[0].retention.reason, /units were not supplied/);
const scope = {};
vm.runInNewContext(fs.readFileSync(new URL("../analysis_readiness_model.js", import.meta.url), "utf8"), scope);
assert.equal(typeof scope.UfoAnalysisReadinessModel.compute, "function");
console.log("Analysis readiness model checks passed.");

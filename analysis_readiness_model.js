(function (root, factory) {
  "use strict";
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.UfoAnalysisReadinessModel = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";
  const STATUS_LABELS = Object.freeze({ ready_inferential: "Qualified for the stated inferential lane", ready_sensitivity: "Sensitivity analysis",
    ready_descriptive: "Descriptive only", limited: "Limited support", blocked: "Requirements not met", not_applicable: "Not applicable",
    not_evaluated: "Not assessed", data_unavailable: "Data unavailable" });
  const GROUPS = Object.freeze([
    { key: "ufo_points", label: "UFO report points", section: "spatial" }, { key: "crops", label: "Crop circles", section: "crops" },
    { key: "animals", label: "Animal reports", section: "animals" }, { key: "facilities", label: "Facilities and site markers", section: "facilities" },
    { key: "relationships", label: "Relationship records", section: "relationships" }, { key: "other", label: "Other analysis lanes", section: "context" },
  ]);
  // Only explicit release identifiers determine the family. Labels and reason
  // prose are deliberately never used to classify a lane or place a gate.
  const FAMILY = Object.freeze({
    ufoCraftPoints: "ufo_points", ufo_craft_points: "ufo_points", ufoPointNeighbors: "ufo_points", ufo_point_neighbors: "ufo_points",
    cropBounded: "crops", crop_bounded: "crops", cropLocality: "crops", crop_locality: "crops", cropCircles: "crops", crop_circles: "crops", cropStrict: "crops", crop_strict: "crops",
    animalReports: "animals", animal_reports: "animals", animalStrict: "animals", animal_strict: "animals", animal_public_marker: "animals",
    militaryFacilities: "facilities", military_facilities: "facilities", researchFacilities: "facilities", research_facilities: "facilities", claimedUfoSites: "facilities", claimed_ufo_sites: "facilities",
    relationshipReconciliation: "relationships", relationship_reconciliation: "relationships",
  });
  const STRICT = new Set(["cropStrict", "crop_strict", "animalStrict", "animal_strict"]);
  const SUMMARY = new Set(["cropCircles", "crop_circles"]);
  const SHARED_FACILITIES = new Set(["militaryFacilities", "military_facilities", "researchFacilities", "research_facilities"]);
  const CLAIMED = new Set(["claimedUfoSites", "claimed_ufo_sites"]);
  const POINTS = new Set(["ufoCraftPoints", "ufo_craft_points"]);
  function object(value) { return value && typeof value === "object" && !Array.isArray(value); }
  function count(value) { return typeof value === "number" && Number.isSafeInteger(value) && value >= 0 ? value : null; }
  function text(value) { return typeof value === "string" ? value : ""; }
  function statusLabel(status) { return STATUS_LABELS[status] || (status ? "Unrecognized status: " + status : "Status not supplied"); }
  function countStatuses(items, getStatus) {
    const result = Object.fromEntries(Object.keys(STATUS_LABELS).map(key => [key, 0]));
    items.forEach(item => { const key = getStatus(item) || "status_not_supplied"; result[key] = (result[key] || 0) + 1; });
    return result;
  }
  function retention(numerator, denominator, compatible, unitReason) {
    const n = count(numerator), d = count(denominator);
    if (numerator != null && n == null || denominator != null && d == null) {
      return { numerator: null, denominator: null, share: null, status: "invalid", reason: "The supplied counts are not valid nonnegative integer passed/input counts." };
    }
    if (compatible === false) return { numerator: n, denominator: d, share: null, status: "unavailable", reason: unitReason || "These counts use different units; a retention percentage is not defined." };
    if (n != null && d != null && n > d) return { numerator: null, denominator: null, share: null, status: "invalid", reason: "Passed counts exceed the supplied input count." };
    if (n == null || d == null) return { numerator: n, denominator: d, share: null, status: "unavailable", reason: "A numerator or denominator was not supplied." };
    if (d === 0) return { numerator: n, denominator: d, share: null, status: "empty", reason: "No input records were supplied; 0 / 0 is not a percentage." };
    return { numerator: n, denominator: d, share: n / d, status: "ready", reason: "Recorded passed/input counts for this individual lane or gate; this percentage does not determine its evidence status." };
  }
  function detailStatus(detail) { return detail && detail.cell ? text(detail.cell.status) || null : null; }
  function actionForGate(detail) {
    const status = detailStatus(detail), label = text(detail.label) || text(detail.key) || "Gate";
    return { type: "inspect_gate", gateId: text(detail.key), label: status === "blocked" ? "Review requirements: " + label
      : status === "not_evaluated" ? "Inspect assessment: " + label : status === "data_unavailable" ? "Inspect unavailable evidence: " + label : "Inspect gate: " + label,
    reason: text(detail.cell && detail.cell.reason), policyId: detail.policyId, evidenceHash: detail.evidenceHash };
  }
  function gateDetail(detail) {
    const cell = object(detail.cell) ? detail.cell : {}, counts = object(cell.counts) ? cell.counts : {}, gate = object(detail.gate) ? detail.gate : {};
    const numeratorUnit = text(gate.numeratorUnit) || text(gate.passedUnit) || text(gate.unit);
    const denominatorUnit = text(gate.denominatorUnit) || text(gate.inputUnit) || text(gate.unit);
    // Counts belong to this one typed gate. If explicit unit metadata disagree,
    // retain the gate and counts but do not manufacture a percentage.
    const compatible = Boolean(numeratorUnit && denominatorUnit && numeratorUnit === denominatorUnit);
    const status = detailStatus(detail);
    const applicableToLane = detail.applicableToLane !== false && gate.applicableToLane !== false && detail.applicability !== "not_applicable" && gate.applicability !== "not_applicable";
    return { ...detail, status, statusLabel: statusLabel(status), applicableToLane, retention: retention(counts.passed, counts.input, compatible,
      numeratorUnit && denominatorUnit ? "Passed and input counts use different units; their ratio is not a retention percentage." : "Gate count units were not supplied; a retention percentage is unavailable."),
      numeratorLabel: "Recorded passed", denominatorLabel: text(gate.denominatorLabel) || "Recorded input", numeratorUnit: numeratorUnit || null,
      denominatorUnit: denominatorUnit || null, action: actionForGate(detail) };
  }
  function compute(matrix, options) {
    matrix = object(matrix) ? matrix : {}; options = options || {};
    const sourceScope = object(options.scope) ? options.scope : {}, scope = { ...sourceScope,
      kind: text(sourceScope.kind) || "release_inventory", label: text(sourceScope.label) || "Release-wide evidence inventory",
      activeQueryReports: count(sourceScope.activeQueryReports), activeQualifiedEndpoints: count(sourceScope.activeQualifiedEndpoints) };
    if (scope.activeQueryReports != null && scope.activeQualifiedEndpoints != null && scope.activeQualifiedEndpoints > scope.activeQueryReports) {
      scope.activeQueryReports = null; scope.activeQualifiedEndpoints = null; scope.activeSupportStatus = "invalid";
    }
    const groups = GROUPS.map(group => ({ ...group, lanes: [] }));
    const rows = Array.isArray(matrix.rows) ? matrix.rows : [];
    const lanes = rows.map((row, index) => {
      const item = object(row.item) ? row.item : {}, key = text(item.key) || "unidentified_lane_" + (index + 1), group = groups.find(value => value.key === (FAMILY[key] || "other"));
      const cells = Array.isArray(row.cells) ? row.cells : [], overall = cells.find(cell => cell.key === "overall"), status = overall ? text(overall.status) || null : null;
      const detailedGates = (Array.isArray(row.detailedGates) ? row.detailedGates : []).filter(object).map(gateDetail);
      const aggregateSummary = SUMMARY.has(key), strict = STRICT.has(key), sharedInventoryKey = SHARED_FACILITIES.has(key) ? "facility_catalog" : null;
      const evidenceAudit = object(item.evidenceAudit) ? item.evidenceAudit : null;
      const eligibleUnit = evidenceAudit ? text(evidenceAudit.eligibleUnit) || null : null, inventoryUnit = evidenceAudit ? text(evidenceAudit.inventoryUnit) || null : null;
      const reasonCodes = Array.isArray(item.reasonCodes) ? item.reasonCodes : Array.isArray(item.reason_codes) ? item.reason_codes : [];
      const policyExcludedFromInference = CLAIMED.has(key) && reasonCodes.includes("descriptive_only_prohibited_from_inference");
      const applicableGates = detailedGates.filter(detail => detail.applicableToLane);
      const reconciliationGate = key === "relationshipReconciliation" || key === "relationship_reconciliation"
        ? detailedGates.find(detail => detail.key === "relationship_reconciliation") : null;
      const reconciledRecords = reconciliationGate ? count(reconciliationGate.cell && reconciliationGate.cell.counts && reconciliationGate.cell.counts.passed) : null;
      const actualBlockedGates = applicableGates.filter(detail => detail.status === "blocked");
      const unassessedGates = applicableGates.filter(detail => detail.status === "not_evaluated");
      const unavailableGates = applicableGates.filter(detail => detail.status === "data_unavailable");
      const missingDefinitionGates = aggregateSummary ? [] : cells.filter(cell => cell.key !== "overall" && cell.status === "not_evaluated"
        && !cell.gate && !cell.representativeGateId && !(Array.isArray(cell.gateIds) && cell.gateIds.length));
      const laneRetention = retention(row.eligible, row.total, !strict && !(eligibleUnit && inventoryUnit && eligibleUnit !== inventoryUnit),
        strict ? "Eligible strict context clusters and catalog records are different units; their ratio is not a record-retention percentage."
          : "Eligible and inventory counts use different declared units; their ratio is not a retention percentage.");
      const notes = [];
      if (strict) notes.push("Eligible counts are unique strict context clusters; total counts are catalog records. Their ratio is not a percentage of records passing.");
      if (aggregateSummary) notes.push("This is an aggregate crop marker summary. Typed tests belong to its underlying lanes; absent summary-column tests are not failed or missing assessments.");
      if (sharedInventoryKey) notes.push("The military and research/test lanes share the same facility inventory and gates. Their record counts must not be added as different datasets.");
      if (CLAIMED.has(key)) notes.push("Total counts describe retained claimed-site inventory records; eligible counts describe inferential eligibility, not whether descriptive records exist.");
      if (policyExcludedFromInference) notes.push("The retained policy explicitly excludes this descriptive inventory from inference.");
      if (POINTS.has(key)) notes.push("This lane qualifies release input points. Its status does not approve a particular active comparison, p-value, or q-value.");
      const lane = { key, label: text(row.label) || key, section: group.section, status, statusLabel: statusLabel(status),
        eligible: laneRetention.status === "invalid" ? null : count(row.eligible), total: laneRetention.status === "invalid" ? null : count(row.total),
        rawCounts: { eligible: row.eligible, total: row.total }, retention: laneRetention,
        eligibleLabel: strict ? "Eligible unique context clusters" : CLAIMED.has(key) ? "Inferentially eligible records"
          : group.key === "relationships" ? "Association-eligible relationship records" : "Eligible records",
        totalLabel: strict ? "Catalog records (different unit)" : CLAIMED.has(key) ? "Descriptive inventory records" : "Input records",
        sharedInventoryKey, aggregateSummary, policyExcludedFromInference, reconciledRecords, evidenceAudit, eligibleUnit, inventoryUnit,
        minimumStrictClusters: evidenceAudit ? count(evidenceAudit.minimumStrictClusters) : null,
        cohortBalance: evidenceAudit && object(evidenceAudit.cohortBalance) ? evidenceAudit.cohortBalance : null,
        leadingExclusionReasons: evidenceAudit && Array.isArray(evidenceAudit.leadingExclusionReasons) ? evidenceAudit.leadingExclusionReasons : [],
        notes, reasons: Array.isArray(row.reasons) ? row.reasons : [], cells, item, detailedGates, applicableGates,
        actualBlockedGates, unassessedGates, missingDefinitionGates, unavailableGates,
        actualBlockedGateN: actualBlockedGates.length, unassessedGateN: unassessedGates.length, missingDefinitionN: missingDefinitionGates.length, unavailableGateN: unavailableGates.length,
        statusCounts: countStatuses(detailedGates, detail => detail.status),
        actions: actualBlockedGates.map(detail => detail.action).concat(unassessedGates.map(detail => detail.action), unavailableGates.map(detail => detail.action),
          missingDefinitionGates.map(cell => ({ type: "inspect_definition", dimensionKey: cell.key, label: "Inspect test definition: " + cell.key, reason: text(cell.reason) }))) };
      group.lanes.push(lane); return lane;
    });
    return { schemaId: "ufo-analysis-readiness-view-v1", scope, unit: "analysis lanes", laneN: lanes.length,
      statusCounts: countStatuses(lanes, lane => lane.status), groups: groups.filter(group => group.lanes.length), columns: matrix.columns || [], typed: matrix.typed === true,
      notes: ["These status counts describe analysis lanes, not datasets, records, independent events, or an overall quality score.",
        "Readiness counts belong to their declared release inventory unless a different scope is explicitly supplied. Active query support is shown separately only when supplied by the spatial eligibility metadata.",
        "Lanes and gate inputs can overlap. Their counts and retention bars must not be pooled into a funnel or combined score.",
        "A defined blocked gate, a defined but unassessed gate, and an absent typed test are different states. Original gate statuses, policies, and evidence hashes remain unchanged."] };
  }
  return Object.freeze({ STATUS_LABELS, compute });
});

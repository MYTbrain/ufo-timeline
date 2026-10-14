(function (root, factory) {
  "use strict";
  const node = typeof module === "object" && module.exports;
  const api = factory(node ? require("./encounter_evidence.js") : root.UFOEncounterEvidence,
    node ? require("./analysis_lunar.js") : root.UfoAnalysisLunar,
    node ? require("./analysis_planetary.js") : root.UfoAnalysisPlanetary,
    node ? require("./analysis_nuclear.js") : root.UfoAnalysisNuclear,
    node ? require("./analysis_cross_context.js") : root.UfoAnalysisCrossContext);
  if (node) module.exports = api;
  if (root) root.UfoAnalysisEncounterContext = api;
})(typeof self !== "undefined" ? self : globalThis, function (Encounter, Lunar, Planetary, Nuclear, Cross) {
  "use strict";
  const VERSION = "encounter-context-atlas-v1";
  const WINDOWS = Object.freeze([0, 7, 30]);
  function finite(value) { return typeof value === "number" && Number.isFinite(value) ? value : null; }
  function text(value) { return value == null ? "" : String(value).trim(); }
  function ordinal(row) { return finite(row.startOrdinal) ?? finite(row.sortOrdinal); }
  function exact(row) { const day = ordinal(row); return day != null && (row.endOrdinal == null || row.endOrdinal === day) && ["exact_day", "day"].includes(row.datePrecision); }
  function point(row) { return row.mapped !== false && finite(row.lat) != null && finite(row.lon) != null && Math.abs(row.lat) <= 90 && Math.abs(row.lon) <= 180; }
  function inRange(row, range) { const start = ordinal(row); const end = finite(row.endOrdinal) ?? start; return !range || (start != null && end >= range.start && start <= range.end); }
  function collect(options) {
    const rows = [], seen = new Set(); let inputN = 0, duplicateIdentityN = 0;
    const visit = function (row) {
      inputN += 1;
      if (!row || row.encounterEvidenceReady !== true || !(Number(row.encounterBeingMask) || Number(row.encounterAbductionCode))) return;
      const id = text(row.eventId ?? row.id); if (!id) return;
      if (seen.has(id)) { duplicateIdentityN += 1; return; } seen.add(id);
      rows.push(Object.assign({}, row, { id, eventId: id }));
    };
    if (typeof options.forEachRow === "function") options.forEachRow(visit);
    else (options.rows || []).forEach(visit);
    const groups = Encounter.TAXONOMY.map(function (type) { return { id: type.key, label: type.label, kind: "being", bit: type.bit, rows: [] }; });
    groups.push({ id: "reported_abduction", label: "Reported abduction", kind: "abduction", rows: [] },
      { id: "source_abduction", label: "Source-classified abduction", kind: "abduction", rows: [] },
      { id: "narrative_abduction", label: "Narrative-reported abduction", kind: "abduction", rows: [] },
      { id: "ambiguous_abduction", label: "Abduction category or mention · unclear", kind: "abduction", rows: [] });
    rows.forEach(function (row) {
      const mode = options.evidenceMode || "all";
      const mask = Number(mode === "source_fields" ? row.encounterSourceBeingMask : mode === "narrative" ? row.encounterNarrativeBeingMask : row.encounterBeingMask) >>> 0;
      for (let bit = 0; bit < Encounter.TAXONOMY.length; bit += 1) if (mask & (1 << bit)) groups[bit].rows.push(row);
      const code = Number(row.encounterAbductionCode);
      if ((code === 1 || code === 2) && (mode === "all" || mode === "source_fields" && code === 1 || mode === "narrative" && code === 2)) groups[19].rows.push(row);
      if (code === 1 && mode !== "narrative") groups[20].rows.push(row);
      if (code === 2 && mode !== "source_fields") groups[21].rows.push(row);
      if (code === 3 && mode === "all") groups[22].rows.push(row);
    });
    return { rows, groups, inputN, duplicateIdentityN };
  }
  function metadata(cohort, range) { return cohort.groups.map(function (group) {
    return { id: group.id, label: group.label, kind: group.kind, allMatchedN: group.rows.length,
      activeN: group.rows.filter(function (row) { return inRange(row, range); }).length };
  }); }
  function evidenceModes(cohort, mode) {
    const provenanceReady = cohort.rows.every(function (row) { return !row.encounterBeingMask || row.encounterEvidenceProvenanceReady === true; });
    function modes(ready) { return [{ key: "all", label: "All indexed evidence", available: true },
      { key: "source_fields", label: "Direct source fields", available: ready, reason: ready ? "" : "Per-label origins are not loaded." },
      { key: "narrative", label: "Narrative reports", available: ready, reason: ready ? "" : "Per-label origins are not loaded." }]; }
    return { being: { evidenceMode: mode || "all", evidenceModes: modes(provenanceReady) }, abduction: { evidenceMode: mode || "all", evidenceModes: modes(true) } };
  }
  function matrix(columns) { return { columns, rows: [], inferenceEligible: false, countUnit: "unique catalog reports within each encounter category" }; }
  function addMatrixRow(target, group, eligible, cells, extra) {
    target.rows.push(Object.assign({ id: group.id, label: group.label, kind: group.kind, eligible, cells }, extra || {}));
  }
  function list(value) { return Array.isArray(value) ? value.map(String) : value == null ? [] : [String(value)]; }
  function sharedLineage(report, context) {
    const id = text(report.eventId ?? report.id);
    if (list(context.originUfoEventIds).includes(id) || list(context.originInputIds).includes(id)) return true;
    if (report.duplicateLineage && context.lineageHash && report.duplicateLineage === context.lineageHash) return true;
    const family = text(report.source).toLowerCase();
    return family && list(context.sourceFamilyIds).concat(list(context.originPublisherCodes)).some(function (value) { return value.toLowerCase() === family; });
  }
  function lowerBound(rows, day) { let low = 0, high = rows.length; while (low < high) { const mid = (low + high) >>> 1; if (ordinal(rows[mid]) < day) low = mid + 1; else high = mid; } return low; }
  function contextComparison(cohort, values, range, domain, enabled, retainLinks) {
    const calendar = matrix(WINDOWS.map(function (days) { return { id: String(days), label: days ? "Within ±" + days + " days" : "Same recorded date" }; }));
    const marker = matrix(WINDOWS.map(function (days) { return { id: String(days), label: "≤100 km · " + (days ? "±" + days + " days" : "same date") }; }));
    const excluded = {}, dateRoles = {}, clustered = new Map();
    function exclude(reason) { excluded[reason] = (excluded[reason] || 0) + 1; }
    (enabled ? values || [] : []).forEach(function (value) {
      const row = Object.assign({}, value);
      if (row.legalPublicationRestriction === true || row.dedupStatus === "duplicate" || list(row.exclusionReasons).some(function (reason) { return ["legal_publication_restriction", "duplicate_record_excluded_from_analysis", "unresolved_identity_date_or_coordinate_conflict"].includes(reason); })) { exclude("restricted_duplicate_or_unresolved"); return; }
      if (!exact(row)) { exclude("context_date_not_exact"); return; }
      if (!inRange(row, range)) { exclude("outside_selected_dates"); return; }
      const key = text(row.clusterId) || (point(row) ? [domain, row.lat.toFixed(6), row.lon.toFixed(6), ordinal(row)].join("|") : domain + "|" + text(row.id));
      if (!clustered.has(key)) clustered.set(key, Object.assign({}, row, { members: [] }));
      clustered.get(key).members.push(row);
      dateRoles[row.dateRole || "unspecified"] = (dateRoles[row.dateRole || "unspecified"] || 0) + 1;
    });
    const contexts = Array.from(clustered.values()).sort(function (a, b) { return ordinal(a) - ordinal(b); });
    const markerContextN = contexts.filter(point).length;
    const links = new Map(); let sourceCollisionPairs = 0;
    cohort.rows.filter(function (row) { return inRange(row, range) && exact(row); }).forEach(function (row) {
      const day = ordinal(row), counts = [0, 0, 0], spatial = [0, 0, 0];
      for (let i = lowerBound(contexts, day - 30); i < contexts.length && ordinal(contexts[i]) <= day + 30; i += 1) {
        const other = contexts[i];
        if (other.members.some(function (member) { return sharedLineage(row, member); })) { sourceCollisionPairs += 1; continue; }
        const delta = Math.abs(day - ordinal(other));
        const nearby = point(row) && point(other) && Cross.distanceKm(row, other) <= 100;
        WINDOWS.forEach(function (window, index) { if (delta <= window) { counts[index] += 1; if (nearby) spatial[index] += 1; } });
      }
      links.set(row.id, { counts, spatial });
    });
    cohort.groups.forEach(function (group) {
      const dated = group.rows.filter(function (row) { return inRange(row, range) && exact(row); });
      const located = dated.filter(point);
      function cells(rows, key) { return WINDOWS.map(function (days, i) {
        const contextReady = enabled && (key === "spatial" ? markerContextN > 0 : contexts.length > 0);
        const count = rows.reduce(function (sum, row) { const link = links.get(row.id); return sum + (link && link[key][i] > 0 ? 1 : 0); }, 0);
        const pairCount = rows.reduce(function (sum, row) { const link = links.get(row.id); return sum + (link ? link[key][i] : 0); }, 0);
        return { id: String(days), count: contextReady ? count : null, pairCount, share: rows.length && contextReady ? count / rows.length : null,
          status: !enabled ? "layer_disabled" : !contexts.length ? "context_catalog_no_eligible_rows" : key === "spatial" && !markerContextN ? "context_coordinates_unavailable" : !rows.length ? "no_eligible_encounter_rows" : "descriptive" };
      }); }
      addMatrixRow(calendar, group, dated.length, cells(dated, "counts"));
      addMatrixRow(marker, group, located.length, cells(located, "spatial"));
    });
    return { calendar, marker, inspectionLinks: retainLinks ? links : undefined, coverage: { inputN: (values || []).length, layerEnabled: enabled, eligibleContextClusters: contexts.length,
      markerContextClusters: markerContextN, excluded, dateRoles, sourceCollisionPairs },
      strictSiteStatus: "unavailable_source_verified_event_sites_and_times_required",
      warnings: ["Counts compare recorded dates; crop catalog/discovery dates and animal report/discovery dates are not assumed formation or death times.",
        "Calendar alignment is worldwide and is not local co-occurrence. The ≤100 km lane compares public markers, not verified event sites.",
        "Co-located same-day context markers are clustered. Known shared source families or originating reports are excluded; unknown source relationships may remain.",
        "Only context dates inside the selected range are used. Windows at the range boundary are truncated; no inference, incidence, p-value or causal claim is supplied."] };
  }
  function computeEncounterContext(optionsValue) {
    const options = optionsValue || {};
    if (options.encounterEvidenceReady !== true) return { status: "unavailable_encounter_evidence", schemaId: VERSION };
    if (options.ordinalEpoch && options.ordinalEpoch !== "unix_day") throw new Error("Encounter context requires explicit Unix-day ordinals");
    const range = options.range || null, cohort = collect(options);
    const lunar = matrix(Lunar.PHASES), nuclearPhase = matrix([]), facilities = matrix([]), nuclearDistance = matrix([]), coverage = [], matchedControls = [];
    let lunarMethod, lunarWarnings, nuclearWarnings, nuclearSettings, nuclearCoverage, nuclearStatus, facilityStatus;
    cohort.groups.forEach(function (group) {
      const moon = Lunar.computeLunarContext({ rows: group.rows, range, ordinalEpoch: "unix_day" });
      const domain = moon.domains[0];
      addMatrixRow(lunar, group, domain.phaseEligible, domain.phaseBins, { stableN: domain.stablePhaseCount, ambiguousN: domain.ambiguousPhaseCount, excluded: domain.excluded, sky: domain.sky });
      lunarMethod = moon.method; lunarWarnings = moon.warnings;
      const nuclear = Nuclear.computeNuclearContext(Object.assign({}, options.nuclear || {}, options.nuclearSettings || {}, {
        rows: group.rows, range, startOrdinal: range && range.start, endOrdinal: range && range.end, ordinalEpoch: "unix_day", crops: [], animals: [],
        broaderFacilities: options.broaderFacilities || [], facilityCodebook: options.facilityCodebook || {} }));
      const domainN = nuclear.domains.ufo, facilityN = nuclear.facilities.byDomain.ufo;
      matchedControls.push(Object.assign({ id: group.id, label: group.label }, domainN.matchedControls));
      nuclearPhase.columns = domainN.phases.map(function (cell) { return { id: cell.id || cell.phase, label: cell.label || cell.phase }; });
      facilities.columns = facilityN.groups.map(function (cell) { return { id: cell.id, label: cell.label }; });
      nuclearDistance.columns = domainN.distanceBands.map(function (cell) { return { id: cell.id, label: cell.label }; });
      const catalogReady = nuclear.status !== "source_catalog_unavailable";
      addMatrixRow(nuclearPhase, group, domainN.eligibleN, domainN.phases.map(function (cell) { return Object.assign({}, cell, { count: catalogReady ? cell.uniqueReports : null, share: catalogReady && domainN.eligibleN ? cell.uniqueReports / domainN.eligibleN : null, status: nuclear.status }); }), { linkedReportsN: domainN.linkedReportsN, excluded: domainN.exclusions });
      addMatrixRow(facilities, group, facilityN.eligibleN, facilityN.groups.map(function (cell) {
        const available = (nuclear.facilities.nuclearSitesN + nuclear.facilities.broaderSitesN > 0) && (!["nuclear_only", "both"].includes(cell.id) || nuclear.facilities.nuclearSitesN > 0);
        return Object.assign({}, cell, { count: available ? cell.reportsN : null, share: available ? cell.share : null, status: nuclear.facilities.status });
      }), { unknownActivityN: facilityN.unknownActivityN });
      addMatrixRow(nuclearDistance, group, domainN.eligibleN, domainN.distanceBands.map(function (cell) { return Object.assign({}, cell, { count: catalogReady ? cell.uniqueReports : null, share: catalogReady && domainN.eligibleN ? cell.uniqueReports / domainN.eligibleN : null, status: nuclear.status }); }));
      coverage.push({ id: group.id, label: group.label, lunarEligible: domain.phaseEligible, nuclearEligible: domainN.eligibleN, facilityEligible: facilityN.eligibleN,
        verifiedMoonSkyEligible: domain.sky.eligible, lunarExclusions: domain.excluded, nuclearExclusions: domainN.exclusions });
      nuclearWarnings = nuclear.policyWarnings.concat(nuclear.facilities.warnings); nuclearSettings = nuclear.settings; nuclearCoverage = nuclear.coverage;
      nuclearStatus = nuclear.status; facilityStatus = nuclear.facilities.status;
    });
    return { schemaId: VERSION, status: "ready", evidenceMode: options.evidenceMode || "all", ordinalEpoch: "unix_day", range, groups: metadata(cohort, range), inputN: cohort.inputN,
      populations: evidenceModes(cohort, options.evidenceMode),
      indexedMatchedN: cohort.rows.length, duplicateIdentityN: cohort.duplicateIdentityN, coverage,
      lunar: { matrix: lunar, method: lunarMethod, warnings: lunarWarnings }, nuclear: { phases: nuclearPhase, distances: nuclearDistance, facilities,
        settings: nuclearSettings, coverage: nuclearCoverage, matchedControls, warnings: nuclearWarnings, status: nuclearStatus, facilityStatus },
      crops: contextComparison(cohort, options.crops, range, "crop", options.cropCirclesEnabled !== false),
      animals: contextComparison(cohort, options.animals, range, "animal", options.animalMutilationsEnabled !== false), artifactHashes: options.artifactHashes || {},
      warnings: ["Each original report counts once within each category. Multiple being labels and nested abduction categories overlap and must not be added as independent encounters.",
        "All comparisons are descriptive catalog associations. Missing source labels are not a negative observation. Source effort, population exposure and incident independence are unmeasured."], inferenceEligible: false };
  }
  function computeEncounterPlanetary(optionsValue) {
    const options = optionsValue || {};
    if (options.encounterEvidenceReady !== true) return { status: "unavailable_encounter_evidence", schemaId: VERSION };
    const cohort = collect(options), matrices = { zodiac: {}, motion: {}, aspects: {} }; let method, warnings, precomputation, pairs;
    cohort.groups.forEach(function (group) {
      const model = Planetary.computePlanetaryHeatmaps(Object.assign({}, options.planetarySettings || {}, { rows: group.rows,
        range: options.range || null, ordinalEpoch: "unix_day", includeCategoryMatrices: false }));
      const domain = model.domains[0];
      ["zodiac", "motion", "aspects"].forEach(function (kind) {
        const native = domain.matrices[kind];
        native.rows.forEach(function (axis) {
          if (!matrices[kind][axis.id]) matrices[kind][axis.id] = Object.assign(matrix(native.columns), { axisId: axis.id, label: axis.label, planet: axis.planet, partner: axis.partner });
          addMatrixRow(matrices[kind][axis.id], group, domain.positionEligible, axis.cells, { excluded: domain.excluded });
        });
      });
      method = model.method; warnings = model.warnings; precomputation = model.precomputation; pairs = model.pairs;
    });
    return { schemaId: VERSION, status: "ready", evidenceMode: options.evidenceMode || "all", groups: metadata(cohort, options.range || null), matrices, bodies: Planetary.PLANETS, pairs,
      populations: evidenceModes(cohort, options.evidenceMode),
      settings: { zodiacSystem: options.planetarySettings && options.planetarySettings.zodiacSystem || "sidereal", ayanamsaId: options.planetarySettings && options.planetarySettings.ayanamsaId || "lahiri", aspectOrbDegrees: (options.planetarySettings && options.planetarySettings.aspectOrbDegrees) ?? 3 },
      method, warnings, precomputation, artifactHashes: options.artifactHashes || {}, housesStatus: "unavailable_verified_UTC_timezone_coordinates_and_house_convention_required", inferenceEligible: false };
  }
  function inspectReports(optionsValue, requestValue) {
    const request = requestValue || {}, options = Object.assign({}, optionsValue || {}, { evidenceMode: request.evidenceMode || "all" }), cohort = collect(options);
    const group = cohort.groups.find(function (value) { return value.id === request.rowKey; });
    if (!group) throw new Error("Unknown encounter category.");
    const rows = group.rows.filter(function (row) { return inRange(row, options.range); }), eligible = new Set(), matching = new Set();
    const topic = request.contextTopic, axis = request.contextAxis, column = String(request.columnKey);
    function capture(row, membership) {
      eligible.add(row.id);
      const hit = topic === "lunar" ? membership.phase === column : topic === "planetary" ? membership.column === column
        : axis === "facilities" ? membership.facility === column : axis === "distances" ? membership.distances.includes(column) : membership.phases.includes(column);
      if (hit) matching.add(row.id);
    }
    if (topic === "lunar") Lunar.computeLunarContext({ rows, range: options.range, ordinalEpoch: "unix_day", onReportMembership: capture });
    else if (topic === "planetary") Planetary.inspectHeatmapReports(Object.assign({}, options.planetarySettings, { rows, range: options.range,
      ordinalEpoch: "unix_day", kind: request.planetKind, axisId: axis, onReportMembership: capture }));
    else if (topic === "nuclear") Nuclear.computeNuclearContext(Object.assign({}, options.nuclear, options.nuclearSettings, { rows,
      startOrdinal: options.range && options.range.start, endOrdinal: options.range && options.range.end, ordinalEpoch: "unix_day",
      broaderFacilities: options.broaderFacilities, facilityCodebook: options.facilityCodebook, onReportMembership: capture }));
    else if (topic === "crops" || topic === "animals") {
      const enabled = topic === "crops" ? options.cropCirclesEnabled !== false : options.animalMutilationsEnabled !== false;
      const model = contextComparison(cohort, options[topic], options.range, topic === "crops" ? "crop" : "animal", enabled, true);
      if (!enabled || !model.coverage.eligibleContextClusters || (axis === "marker" && !model.coverage.markerContextClusters)) return { status: "unavailable_context", total: 0, eventIds: [] };
      const index = WINDOWS.indexOf(Number(column)); if (index < 0) throw new Error("Unknown context window.");
      rows.forEach(function (row) { if (!exact(row) || (axis === "marker" && !point(row))) return;
        eligible.add(row.id); const link = model.inspectionLinks.get(row.id);
        if (link && link[axis === "marker" ? "spatial" : "counts"][index] > 0) matching.add(row.id);
      });
    } else throw new Error("Unknown encounter context topic.");
    const bucket = request.bucket || "cell", offset = Math.max(0, Math.trunc(Number(request.offset) || 0)), limit = Math.max(1, Math.min(100, Math.trunc(Number(request.limit) || 25)));
    const eventIds = []; let total = 0;
    rows.forEach(function (row) {
      const hit = bucket === "eligible" || bucket === "supported" ? eligible.has(row.id) : bucket === "excluded" || bucket === "unknown" ? !eligible.has(row.id) : bucket === "not_loaded" ? false : matching.has(row.id);
      if (!hit) return; if (request.allIds || total >= offset && eventIds.length < limit) eventIds.push(row.id); total += 1;
    });
    return { status: "ready", total, offset, limit, eventIds, coverage: { population: rows.length, eligible: eligible.size, excluded: rows.length - eligible.size } };
  }
  return { VERSION, WINDOWS, computeEncounterContext, computeEncounterPlanetary, collect, inspectReports };
});

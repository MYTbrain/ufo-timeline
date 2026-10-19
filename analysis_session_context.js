(function (root, factory) {
  "use strict";
  const api = factory(typeof module === "object" && module.exports ? require("./analysis_spatial.js") : root.UfoAnalysisSpatial,
    typeof module === "object" && module.exports ? require("./analysis_collection_evidence.js") : root.UfoAnalysisCollectionEvidence);
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.UfoAnalysisSessionContext = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function (Spatial, Collections) {
  "use strict";
  const DAY = 86400000, PYTHON_EPOCH = 719163;
  const UNKNOWN = new Set(["", "unknown", "unavailable", "unresolved", "unparsed", "none", "null", "not_indexed", "not_provided", "n/a", "unspecified", "unknown / unresolved"]);
  const NOTES = ["Descriptive comparisons only; catalog records, source families and independent incidents are different units.",
    "No chronology connectors, inferred flight paths, significance tests or causal claims are used."];
  const array = value => Array.isArray(value) ? value : [];
  const text = value => String(value == null ? "" : value).trim();
  const known = value => !UNKNOWN.has(text(value).toLowerCase());
  const finite = value => typeof value === "number" && Number.isFinite(value);
  const idOf = row => text(row && (row.eventId ?? row.event_id));
  const pretty = value => text(value).replace(/_/g, " ");
  function unix(value, epoch) { return finite(value) ? value - (["statistics_day", "python_day"].includes(epoch) ? PYTHON_EPOCH : 0) : null; }
  function yearStart(year) { if (!Number.isInteger(year) || year < 1 || year > 9999) return null; const date = new Date(0); date.setUTCFullYear(year, 0, 1); date.setUTCHours(0, 0, 0, 0); return date.getTime() / DAY; }
  function dateInterval(row, epoch) {
    const start = unix(row.startOrdinal ?? row.dateStartOrdinal ?? row.sortOrdinal ?? row.ordinal, epoch);
    const end = unix(row.endOrdinal ?? row.dateEndOrdinal ?? row.sortOrdinal ?? row.ordinal, epoch);
    if (start != null && end != null && end >= start) return [start, end];
    const first = row.startYear ?? row.year, last = row.endYear ?? row.year ?? first;
    if (!known(row.datePrecision) || !Number.isInteger(first) || !Number.isInteger(last) || last < first) return null;
    const lower = yearStart(first), after = yearStart(last + 1);
    return lower != null && after != null ? [lower, after - 1] : null;
  }
  function cohortOf(value) { return value && value.cohort || value || {}; }
  function membership(value) { return new Set(array(cohortOf(value).eventIds).map(text)); }
  function reportCount(value) { const cohort = cohortOf(value); return Array.isArray(cohort.eventIds) ? membership(value).size : Number.isSafeInteger(cohort.reportCount) ? cohort.reportCount : 0; }
  function scopeOf(cohort, options) {
    const snapshot = cohort.provenance && cohort.provenance.capturedSnapshot || {};
    const scope = cohort.scope && typeof cohort.scope === "object" ? cohort.scope : {};
    if (scope.allRecords === true || cohort.provenance && cohort.provenance.selectionScope === "all_search_matches") {
      return { status: "unavailable", reason: "This all-records selection has no context date/area population; inherited map filters cannot define one." };
    }
    const time = scope.timeRange || snapshot.timeRange || {};
    const start = unix(time.startOrdinal, options.scopeOrdinalEpoch || "unix_day"), end = unix(time.endOrdinal, options.scopeOrdinalEpoch || "unix_day");
    const range = start != null && end != null && start <= end && !["full", "all", "all_time"].includes(time.mode) ? [start, end] : null;
    const area = scope.areaFilter || snapshot.areaFilter || {}, shapes = area.active === false ? [] : array(area.shapes).slice();
    if (!shapes.length && area.active && known(area.country)) shapes.push({ type: "country", country: area.country });
    const selected = snapshot.selection || cohort.provenance && cohort.provenance.selectionScope === "all_search_matches";
    const explicitFull = ["full", "all", "all_time"].includes(time.mode);
    const wholeCatalog = explicitFull && !selected && (cohort.provenance && cohort.provenance.sessionCaptureScope === "current_filters" ||
      snapshot.timeRange && ["full", "all", "all_time"].includes(snapshot.timeRange.mode));
    if (!range && !shapes.length && !wholeCatalog) return { status: "unavailable", reason: selected
      ? "This exact report selection has no captured date/geographic window defining an independent context population."
      : "A captured finite date window or geographic area is required for independent context records." };
    return { status: "ready", range, shapes, wholeCatalog: Boolean(wholeCatalog && !shapes.length) };
  }
  function coordinates(row) { const lat = row.lat, lon = row.lon ?? row.lng; return finite(lat) && finite(lon) && lat >= -90 && lat <= 90 && lon >= -180 && lon <= 180 ? [lat, lon] : null; }
  function inside(row, shape, spatial) {
    const kind = text(shape.type).toLowerCase();
    if (kind === "country") return known(row.country) && known(shape.country || shape.countryName)
      ? text(row.country).toLowerCase() === text(shape.country || shape.countryName).toLowerCase() : null;
    const point = coordinates(row); if (!point) return null;
    if (kind === "rectangle") {
      const bounds = shape.bounds || {}, { north, south, east, west } = bounds;
      if (![north, south, east, west].every(finite)) return null;
      return point[0] >= south && point[0] <= north && (west <= east ? point[1] >= west && point[1] <= east : point[1] >= west || point[1] <= east);
    }
    if (kind === "circle") {
      const center = shape.center || {}, radius = shape.radiusMeters ?? (finite(shape.radiusKm) ? shape.radiusKm * 1000 : null);
      const target = coordinates({ lat: center.lat, lon: center.lng ?? center.lon });
      return target && finite(radius) && radius >= 0 && spatial ? spatial.greatCircleDistanceMeters(point[0], point[1], target[0], target[1]) <= radius : null;
    }
    return null;
  }
  function scopedContext(rows, cohortValue, optionsValue) {
    const options = Object.assign({}, optionsValue && optionsValue.settings || {}, optionsValue || {});
    if (!Array.isArray(rows)) return { status: "unavailable", rows: [], notes: [], excludedUnknownScopeN: null, reason: "The context catalog is not loaded." };
    const scope = scopeOf(cohortOf(cohortValue), options);
    if (scope.status !== "ready") return Object.assign(scope, { rows: [], notes: [], excludedUnknownScopeN: null });
    const selected = [], seen = new Set(); let unresolved = 0;
    rows.forEach(function (row, index) {
      const key = text(row.id) || "row:" + index; if (seen.has(key)) return; seen.add(key);
      let uncertain = false;
      if (scope.range) {
        const interval = dateInterval(row, options.contextOrdinalEpoch || "unix_day");
        if (!interval) uncertain = true;
        else if (interval[1] < scope.range[0] || interval[0] > scope.range[1]) return;
      }
      if (scope.shapes.length) {
        const matches = scope.shapes.map(shape => inside(row, shape, options.spatialApi || Spatial));
        if (!matches.includes(true)) { if (matches.includes(null)) uncertain = true; else return; }
      }
      if (uncertain) unresolved += 1; else selected.push(row);
    });
    return { status: "ready", rows: selected, excludedUnknownScopeN: unresolved, scope,
      notes: ["Independent context records use the captured date window and area only; report craft, source and encounter filters do not identify context-record membership.",
        "Stored inclusive date intervals may overlap both groups. Publication/catalog dates retain their recorded role; markers do not establish exact sites."]
        .concat(scope.wholeCatalog ? ["This is an explicit All Time context population. Whole context catalogs can be identical in A and B even when their UFO source/type filters differ."] : [])
        .concat(unresolved ? [unresolved + " context records could not be assigned to the captured scope because date or geographic evidence is missing."] : []) };
  }
  function unavailable(reason, totalN) { return { status: "unavailable", available: false, reason, totalN: totalN ?? null, eligibleN: null, unknownN: null, rows: [] }; }
  function summarize(totalN, items, accessor) {
    const counts = new Map(); let eligibleN = 0;
    items.forEach(function (item) {
      const values = accessor(item), entries = new Map();
      array(Array.isArray(values) ? values : [values]).forEach(function (value) {
        const entry = value && typeof value === "object" ? value : { key: value, label: pretty(value) };
        if (known(entry.key)) entries.set(text(entry.key), { key: text(entry.key), label: text(entry.label) || pretty(entry.key) });
      });
      if (entries.size) eligibleN += 1;
      entries.forEach(function (entry, key) { const count = counts.get(key) || Object.assign({}, entry, { count: 0 }); count.count += 1; counts.set(key, count); });
    });
    return { status: "ready", available: true, totalN, eligibleN, unknownN: Math.max(0, totalN - eligibleN),
      rows: Array.from(counts.values()).sort((a, b) => a.label.localeCompare(b.label) || a.key.localeCompare(b.key)) };
  }
  function dimension(key, label, unit, a, b, notes, multiLabel) {
    return { key, label, unit, status: a.available || b.available ? "ready" : "unavailable", a, b, notes: notes || [], multiLabel: Boolean(multiLabel) };
  }
  function contextDimensions(options, domain) {
    const context = options.context || {}, values = context[domain], states = {};
    ["A", "B"].forEach(slot => { states[slot] = scopedContext(values, cohortOf(options.groups && options.groups[slot]), Object.assign({}, options.settings || {}, { spatialApi: options.spatialApi || Spatial })); });
    const unit = domain === "crops" ? "crop-circle catalog records" : "animal-report catalog records";
    const definitions = domain === "crops" ? [["morphology", "Reported morphology", row => row.morphology || (known(row.category) ? [row.category] : []), true],
      ["country", "Recorded country", row => row.country], ["classification", "Source classification", row => row.classification],
      ["originStatus", "Origin status", row => row.originStatus]] : [["species", "Reported species", row => row.species || (known(row.category) ? [row.category] : []), true]];
    definitions.push(["dateRole", "Date role", row => row.dateRole], ["datePrecision", "Date precision", row => row.datePrecision],
      ["coordinateEvidenceClass", "Coordinate evidence", row => row.coordinateEvidenceClass || row.coordinateClass],
      ["reviewState", "Review state", row => row.reviewState || row.status], ["independenceStatus", "Source independence status", row => row.independenceStatus],
      ["eligibility", "Strict context eligibility", row => typeof row.strictEligible === "boolean" ? { key: row.strictEligible ? "qualified" : "not_qualified", label: row.strictEligible ? "Passes stored strict eligibility" : "Does not pass stored strict eligibility" } : null],
      ["sourceFamily", "Source-family membership", row => row.sourceFamilyIds, true]);
    const notes = Array.from(new Set(states.A.notes.concat(states.B.notes)));
    return definitions.map(function ([key, label, accessor, multi]) {
      const sides = ["A", "B"].map(slot => states[slot].status === "ready" ? Object.assign(summarize(states[slot].rows.length, states[slot].rows, accessor),
        { excludedUnknownScopeN: states[slot].excludedUnknownScopeN }) : unavailable(states[slot].reason));
      return dimension(domain + "_" + key, label, unit, sides[0], sides[1], notes, multi);
    });
  }
  function groupData(value) {
    const ids = membership(value), seen = new Set(), rows = array(value.rows).filter(function (row) {
      const id = idOf(row); if (!ids.has(id) || seen.has(id)) return false; seen.add(id); return true;
    });
    return { cohort: value.cohort, ids, rows, totalN: reportCount(value) };
  }
  function codebook(context, key) { return context.codebooks && context.codebooks[key] || context.manifest && context.manifest.codes && context.manifest.codes[key] || {}; }
  function pins(context, group, spatial) {
    if (!Array.isArray(context.spatialPoints) || !spatial) return null;
    const points = new Map(); context.spatialPoints.forEach(function (row) {
      const point = spatial.normalizeSpatialPoint(row, codebook(context, "ufoSpatialPoints"));
      if (group.ids.has(point.eventId) && coordinates(point)) points.set(point.eventId, point);
    }); return points;
  }
  function distanceBand(km) { return km <= 25 ? "0–25 km" : km <= 50 ? ">25–50 km" : km <= 100 ? ">50–100 km" : km <= 250 ? ">100–250 km" : km <= 500 ? ">250–500 km" : ">500 km"; }
  function facilitiesDimensions(options, groups) {
    const context = options.context || {}, settings = options.settings || {}, radius = finite(settings.spatialRadiusKm) && settings.spatialRadiusKm > 0 ? settings.spatialRadiusKm : 100;
    const spatial = options.spatialApi || Spatial, loaded = Array.isArray(context.facilities) && Array.isArray(context.spatialPoints) && spatial;
    const facilities = loaded ? context.facilities.filter(row => spatial.facilityIsInferential(row, codebook(context, "facilityAnalysis")))
      .map(row => spatial.normalizeFacility(row, codebook(context, "facilityAnalysis"))) : [];
    const prepared = {};
    ["A", "B"].forEach(function (slot) {
      const group = groups[slot], points = loaded ? pins(context, group, spatial) : null, rows = [];
      if (points) points.forEach(function (point) {
        let nearest = null;
        facilities.forEach(function (facility) {
          const ordinal = unix(point.ordinal, settings.spatialOrdinalEpoch || "statistics_day");
          if (spatial.facilityActiveAt(facility, ordinal == null ? null : ordinal + PYTHON_EPOCH, point.year) !== "active") return;
          const km = spatial.greatCircleDistanceMeters(point.lat, point.lon, facility.lat, facility.lon) / 1000;
          if (!nearest || km < nearest.km) nearest = { km, facility };
        });
        if (nearest) rows.push({ id: point.eventId, km: nearest.km, uncertaintyKm: nearest.facility.uncertaintyKm, facilityClass: nearest.facility.facilityClass });
      }); prepared[slot] = { points, rows, totalN: group.totalN };
    });
    const defs = [["facility_distance", "Nearest qualifying active facility: distance", row => distanceBand(row.km)],
      ["facility_class", "Nearest qualifying active facility: class", row => row.facilityClass],
      ["facility_radius", "Within " + radius + " km of a qualifying active facility", row => row.uncertaintyKm > 0 && Math.abs(row.km - radius) <= row.uncertaintyKm ? { key: "boundary_uncertain", label: "Facility uncertainty crosses the radius boundary" }
        : { key: row.km <= radius ? "within_radius" : "beyond_radius", label: row.km <= radius ? "Within " + radius + " km" : "Beyond " + radius + " km" }]];
    const notes = ["Distances use the existing pinned high-precision report pool and only facility records passing the stored coordinate/activity policy.",
      "Nearest means nearest known qualifying active facility in this inventory; unqualified sites and unknown activity are not assumed absent.", "Generalized/unmapped report locations and reports without a qualifying active comparison remain unknown.",
      "Distances describe recorded markers; stored facility uncertainty is retained at the radius boundary."];
    return defs.map(function ([key, label, accessor]) { const sides = ["A", "B"].map(slot => loaded ? summarize(prepared[slot].totalN, prepared[slot].rows, accessor)
      : unavailable("Facility and qualified-point artifacts must be loaded.", groups[slot].totalN)); return dimension(key, label, "captured catalog reports", sides[0], sides[1], notes); });
  }
  function spatialDimensions(options, groups) {
    const context = options.context || {}, settings = options.settings || {}, spatial = options.spatialApi || Spatial;
    const loaded = spatial && Array.isArray(context.neighbors) && Array.isArray(context.spatialPoints);
    const radius = Math.min(100, finite(settings.spatialRadiusKm) && settings.spatialRadiusKm > 0 ? settings.spatialRadiusKm : 100);
    const data = {};
    ["A", "B"].forEach(function (slot) {
      const group = groups[slot], points = loaded ? pins(context, group, spatial) : null, pairs = [], touched = new Set(), seen = new Set();
      if (loaded) context.neighbors.forEach(function (value) {
        const edge = spatial.normalizeEdge(value);
        if (!edge.contractValid || edge.duplicateCandidate || !points.has(edge.eventIdA) || !points.has(edge.eventIdB) || edge.eventIdA === edge.eventIdB || edge.distanceMeters > radius * 1000 || edge.dayGap > 30) return;
        const key = [edge.eventIdA, edge.eventIdB].sort().join("|"); if (seen.has(key)) return; seen.add(key);
        pairs.push(edge); touched.add(edge.eventIdA); touched.add(edge.eventIdB);
      }); data[slot] = { points, pairs, touched };
    });
    const notes = ["Only unique unordered pairs whose two endpoints belong to the captured group are counted. Groups may share pairs.",
      "Pinned neighbor coverage is bounded to " + radius + " km and 30 days; no indexed neighbor does not mean no other sightings existed.", "These are point-neighborhood records, never chronology traces or measured travel paths."];
    if (finite(settings.spatialRadiusKm) && settings.spatialRadiusKm > 100) notes.push("The requested radius exceeds the artifact's 100 km coverage; this view explicitly uses 100 km.");
    const eligible = ["A", "B"].map(slot => loaded ? summarize(groups[slot].totalN, Array.from(groups[slot].ids), id => ({
      key: data[slot].points.has(id) ? "pinned_qualified" : "outside_pinned_pool", label: data[slot].points.has(id) ? "In pinned qualified point pool" : "Outside pinned qualified point pool" })) : unavailable("Qualified point/neighbor artifacts must be loaded.", groups[slot].totalN));
    const result = [dimension("spatial_eligibility", "Pinned point eligibility", "captured catalog reports", eligible[0], eligible[1], notes)];
    const present = ["A", "B"].map(slot => loaded ? summarize(groups[slot].totalN, Array.from(data[slot].points.keys()), id => ({
      key: data[slot].touched.has(id) ? "has_captured_neighbor" : "no_indexed_captured_neighbor", label: data[slot].touched.has(id) ? "At least one qualified captured neighbor" : "No qualified captured neighbor in indexed window" })) : unavailable("Qualified point/neighbor artifacts must be loaded.", groups[slot].totalN));
    result.push(dimension("spatial_neighbor_coverage", "Report-neighbor coverage", "captured catalog reports", present[0], present[1], notes));
    [["distance", "Pair distance", edge => distanceBand(edge.distanceMeters / 1000)], ["lag", "Absolute date separation", edge => edge.dayGap === 0 ? "Same calendar day" : edge.dayGap <= 7 ? "1–7 days" : "8–30 days"],
      ["source", "Pair source mix", edge => edge.crossSource == null ? null : edge.crossSource ? "Different catalog sources" : "Same catalog source"]].forEach(function ([key, label, accessor]) {
      const sides = ["A", "B"].map(slot => loaded ? summarize(data[slot].pairs.length, data[slot].pairs, accessor) : unavailable("Qualified point/neighbor artifacts must be loaded."));
      result.push(dimension("spatial_pair_" + key, label, "unique unordered qualified report pairs", sides[0], sides[1], notes));
    }); return result;
  }
  function evidenceDimensions(options, groups) {
    const context = options.context || {}, definitions = [["report_date_precision", "Report date precision", row => row.datePrecision],
      ["report_coordinate_source", "Coordinate source", row => row.coordinateSource], ["report_craft_confidence", "Craft confidence", row => row.craftConfidence]];
    const output = definitions.map(([key, label, accessor]) => dimension(key, label, "captured catalog reports",
      summarize(groups.A.totalN, groups.A.rows, accessor), summarize(groups.B.totalN, groups.B.rows, accessor), ["Unindexed fields remain unknown; exact captured IDs define the population."]));
    const relationshipsLoaded = Array.isArray(context.relationships), normalized = relationshipsLoaded ? context.relationships.map(function (row) {
      const decode = (name, value) => { const book = codebook(context, "relationshipReconciliation")[name]; return Number.isInteger(value) ? Array.isArray(book) && book[value] || "unknown" : value; };
      return Array.isArray(row) ? { id: text(row[0]), eventId: text(row[7]), type: decode("relationshipType", row[5]), review: decode("reviewState", row[6]), reconciliation: decode("reconciliationStatus", row[8]), eligibility: typeof row[9] === "boolean" ? row[9] : null }
        : { id: text(row.relationshipId), eventId: text(row.currentUfoEventId), type: decode("relationshipType", row.relationshipType ?? row.relationshipTypeCode),
          review: decode("reviewState", row.reviewState ?? row.reviewStateCode), reconciliation: decode("reconciliationStatus", row.reconciliation ?? row.reconciliationStatus ?? row.reconciliationStatusCode),
          eligibility: typeof row.associationEligible === "boolean" ? row.associationEligible : null };
    }) : [];
    const joined = {}, joinedIds = {};
    ["A", "B"].forEach(function (slot) { const seen = new Set(); joined[slot] = normalized.filter(function (row) {
      if (!row.eventId || !groups[slot].ids.has(row.eventId) || !row.id || seen.has(row.id)) return false; seen.add(row.id); return true;
    }); joinedIds[slot] = new Set(joined[slot].map(row => row.eventId)); });
    const notes = ["Only provenance relationships with an explicit current UFO report ID can join a captured group. Unjoined relationships are never copied into both groups.",
      "No indexed relationship is not evidence that a historical relationship was absent."];
    const sides = ["A", "B"].map(slot => relationshipsLoaded ? summarize(groups[slot].totalN, Array.from(joinedIds[slot]), () => ({ key: "indexed_exact_join", label: "Has an indexed exact-ID relationship" }))
      : unavailable("Relationship reconciliation evidence is not loaded.", groups[slot].totalN));
    output.push(dimension("relationship_coverage", "Exact-ID relationship coverage", "captured catalog reports", sides[0], sides[1], notes));
    [["type", "Indexed relationship type"], ["review", "Relationship review state"], ["reconciliation", "Relationship reconciliation"],
      ["eligibility", "Stored relationship eligibility", row => row.eligibility == null ? null : { key: row.eligibility ? "qualified" : "not_qualified", label: row.eligibility ? "Passes stored association gates" : "Does not pass stored association gates" }]].forEach(function ([key, label, accessor]) {
      const values = ["A", "B"].map(slot => relationshipsLoaded ? summarize(joined[slot].length, joined[slot], accessor || (row => row[key])) : unavailable("Relationship reconciliation evidence is not loaded."));
      output.push(dimension("relationship_" + key, label, "provenance relationship records", values[0], values[1], notes));
    });
    const spatial = options.spatialApi || Spatial;
    if (Array.isArray(context.contextNeighbors) && spatial) {
      const neighbors = context.contextNeighbors.map(row => spatial.normalizeContextNeighbor(row, codebook(context, "contextUfoNeighbors")))
        .filter(row => row.ufoEventId && row.dateRole.startsWith("observed_") && !row.originUfoExcluded && !row.originPublisherExcluded);
      const sides = ["A", "B"].map(function (slot) { const seen = new Set(); const rows = neighbors.filter(function (row) {
        const key = [row.ufoEventId, row.contextId, row.lane, row.dateRole].join("|");
        if (!groups[slot].ids.has(row.ufoEventId) || seen.has(key)) return false; seen.add(key); return true;
      }); return summarize(rows.length, rows, row => row.lane); });
      output.push(dimension("context_neighbor_lane", "Observed context-marker neighborhood lanes", "report-to-context marker pairs", sides[0], sides[1],
        ["Matched control-date rows and originating report/publisher exclusions are omitted. Rough-marker lanes remain separate from strict sites; descriptive neighborhood records do not establish physical association."]));
    }
    return output;
  }
  function collectionDimensions(options, groups) {
    const originalEvidence = options.collectionEvidence, all = options.settings && options.settings.collectionEvidence === "all", data = {};
    const collectionApi = options.collectionApi || Collections || (typeof globalThis !== "undefined" && globalThis.UfoAnalysisCollectionEvidence);
    const evidence = originalEvidence && Array.isArray(originalEvidence.reports) ? Object.assign({}, originalEvidence, {
      reports: originalEvidence.reports.filter(row => row.canonicalJoinStatus === "validated_id_source_chunk_index") }) : originalEvidence;
    ["A", "B"].forEach(function (slot) {
      if (!collectionApi || !evidence || !Array.isArray(evidence.reports)) { data[slot] = null; return; }
      data[slot] = collectionApi.compute({ evidence, allowedEventIds: groups[slot].ids, disposition: all ? "allcontexts" : "direct", scope: all ? "allmaterials" : "soilplants", includeMemberVariants: options.settings && options.settings.includeMemberVariants === true });
    });
    const notes = [all ? "Sensitivity includes uncertain/adjacent material contexts; these are not all direct soil/plant collection claims." : "Default: directly described soil/plant acts only; uncertain and adjacent contexts are excluded.",
      "Only validated exact catalog IDs join the groups; unjoined dossier cases do not become invented reports. No indexed collection account is not an absence claim.",
      "Merged member narratives differing from the canonical primary are held by default. Source-family/provisional labels are not independent incidents."];
    const taxonomy = evidence && evidence.taxonomy || {}, labels = key => new Map(array(taxonomy[key]).map(row => [row.key, row.label]));
    const defs = [["material", "Reported collection materials", row => array(row.materials).map(key => ({ key, label: labels("materials").get(key) || pretty(key) })), true],
      ["action", "Reported collection acts", row => array(row.actions).map(key => ({ key, label: labels("actions").get(key) || pretty(key) })), true],
      ["source_family", "Indexed source-family membership", row => row.sourceFamily], ["provisional_family", "Provisional account-family membership", row => row.provisionalGroup]];
    const output = defs.map(function ([key, label, accessor, multi]) { const sides = ["A", "B"].map(slot => data[slot]
      ? summarize(groups[slot].totalN, data[slot].reports, accessor) : unavailable("Verified collection evidence is not loaded.", groups[slot].totalN));
      return dimension("collection_" + key, label, "captured catalog reports", sides[0], sides[1], notes, multi); });
    const coverage = ["A", "B"].map(slot => data[slot] ? Object.assign(summarize(groups[slot].totalN, data[slot].reports, () => ({ key: "indexed_selected_collection", label: "Qualifying indexed collection account" })),
      { heldMemberVariantN: data[slot].stats.heldMemberVariantN, sourceFamilyN: new Set(data[slot].reports.map(row => row.sourceFamily).filter(known)).size }) : unavailable("Verified collection evidence is not loaded.", groups[slot].totalN));
    output.unshift(dimension("collection_coverage", "Qualifying collection-account coverage", "captured catalog reports", coverage[0], coverage[1], notes));
    const versions = ["A", "B"].map(function (slot) {
      if (!evidence || !Array.isArray(evidence.reports)) return unavailable("Verified collection evidence is not loaded.", groups[slot].totalN);
      const reports = evidence.reports.filter(row => groups[slot].ids.has(text(row.eventId)) && row.canonicalJoinStatus === "validated_id_source_chunk_index");
      return summarize(groups[slot].totalN, reports, row => ({ key: row.canonicalPrimaryDiffers ? "member_variant" : "primary_version", label: row.canonicalPrimaryDiffers ? "Merged member narrative differs from primary" : "Primary narrative / no indexed version mismatch" }));
    }); output.push(dimension("collection_versions", "Indexed narrative-version coverage", "captured catalog reports", versions[0], versions[1], notes));
    return output;
  }
  function compute(optionsValue) {
    const options = optionsValue || {}, source = options.groups || {}, groups = { A: groupData(source.A || {}), B: groupData(source.B || {}) };
    const section = text(options.section).replace(/^analysis-section-/, ""); let dimensions;
    if (["crops", "crop_circles"].includes(section)) dimensions = contextDimensions(options, "crops");
    else if (["animals", "animal_reports"].includes(section)) dimensions = contextDimensions(options, "animals");
    else if (section === "facilities") dimensions = facilitiesDimensions(options, groups);
    else if (section === "spatial") dimensions = spatialDimensions(options, groups);
    else if (["encounters", "collections"].includes(section)) dimensions = collectionDimensions(options, groups);
    else if (["context", "evidence", "sources-quality", "sources_quality"].includes(section)) dimensions = evidenceDimensions(options, groups);
    else return { status: "unavailable", dimensions: [], notes: NOTES.slice(), reason: "This section has no context comparison contract." };
    return { status: dimensions.some(row => row.status === "ready") ? "ready" : "unavailable", dimensions, notes: NOTES.slice(),
      artifactHashes: Object.assign({}, options.context && options.context.artifactHashes || {}) };
  }
  return Object.freeze({ compute, scopedContext, contextRows: scopedContext });
});

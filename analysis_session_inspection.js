(function (root, factory) {
  "use strict";
  const node = typeof module === "object" && module.exports;
  const api = factory(root, node ? require("./analysis_session_context.js") : null,
    node ? require("./analysis_session_comparisons.js") : null,
    node ? require("./analysis_spatial.js") : null,
    node ? require("./analysis_collection_evidence.js") : null,
    node ? require("./analysis_lunar.js") : null,
    node ? require("./analysis_planetary.js") : null,
    node ? require("./analysis_nuclear.js") : null);
  if (node) module.exports = api;
  if (root) root.UfoAnalysisSessionInspection = api;
})(typeof self !== "undefined" ? self : globalThis, function (root, Context, Comparisons, Spatial, Collections, Lunar, Planetary, Nuclear) {
  "use strict";
  const DAY = 86400000, OFFSET = 719163, UNKNOWN_KEY = "__unknown__";
  const UNKNOWN = new Set(["", "unknown", "unavailable", "unresolved", "unparsed", "none", "null", "not_indexed", "not_provided", "n/a", "unspecified", "unknown / unresolved"]);
  const array = value => Array.isArray(value) ? value : [];
  const text = value => String(value == null ? "" : value).trim();
  const first = (...values) => values.find(value => value != null && value !== "");
  const num = value => value == null || value === "" || typeof value === "boolean" || !Number.isFinite(Number(value)) ? null : Number(value);
  const idOf = row => text(row && first(row.eventId, row.event_id, row.id, row.analysisId));
  const known = value => !UNKNOWN.has(text(value).toLowerCase());
  const pretty = value => text(value).replace(/_/g, " ");
  function api(options, key, fallback, globalName) { return options[key] || fallback || root && root[globalName]; }
  function coords(row) { const lat = num(row.lat), lon = num(first(row.lon, row.lng)); return lat != null && lon != null && Math.abs(lat) <= 90 && Math.abs(lon) <= 180 ? { lat, lon } : null; }
  function iso(day) { if (!Number.isInteger(day)) return ""; const date = new Date(day * DAY); return Number.isFinite(date.getTime()) ? date.toISOString().slice(0, 10) : ""; }
  function dateOf(row) {
    if (row.encounterOccurrenceDateExcluded === true) return "Occurrence date withheld / unresolved";
    const start = first(row.startOrdinal, row.dateStartOrdinal, row.ordinal, row.sortOrdinal), end = first(row.endOrdinal, row.dateEndOrdinal, row.ordinal, row.sortOrdinal, start);
    return text(first(row.dateLabel, row.date, row.dateText, row.dateString)) || (iso(start) ? iso(start) + (end !== start && iso(end) ? " to " + iso(end) : "") : "Date unknown");
  }
  function urlOf(row) {
    const candidates = [row.sourceUrl, row.source_url, row.recordUrl, row.url].concat(array(row.sourceUrls), array(row.sources).map(item => typeof item === "string" ? item : item && item.url));
    return text(candidates.find(value => typeof value === "string" && /^https?:\/\/[^\s]+$/i.test(value)));
  }
  function displayRow(rowValue, ids, detail, identity) {
    const row = rowValue || {}, point = coords(row), id = text(identity || idOf(row));
    const location = text(first(row.location, row.locationName, row.place, row.locality)) || [row.admin1, row.country].filter(known).map(text).join(", ") || (point ? point.lat + ", " + point.lon : "Location unknown");
    return { id, label: text(first(row.title, row.name, row.caseName, row.label)) || (ids.length === 1 ? "Report " + ids[0] : id || "Catalog record"),
      date: dateOf(row), location, source: text(first(row.source, row.sourceFamily, row.sourceFamilyId)) || array(row.sourceFamilyIds).join(", ") || "Source unknown",
      detail: detail || text(first(row.summary, row.description, row.detail)), sourceUrl: urlOf(row), eventIds: ids.slice() };
  }
  function groupOf(value) {
    const group = value || {}, cohort = group.cohort || {}, ids = new Set(array(cohort.eventIds).map(text)), byId = new Map();
    array(group.rows).forEach(row => { const id = idOf(row); if (ids.has(id) && !byId.has(id)) byId.set(id, row); });
    return { group, cohort, ids, byId, rows: Array.from(byId.values()), totalN: ids.size };
  }
  function unavailable(totalN, reason, offset) { return { totalN: totalN == null ? null : totalN, matchedN: null, rows: [], offset, hasMore: false, available: false, reason }; }
  function collector(totalN, options) {
    let matchedN = 0; const rows = [], offset = Math.max(0, Math.floor(num(options.offset) || 0)), limit = Math.min(100, Math.max(1, Math.floor(num(options.limit) || 25)));
    return { add: function (raw, values, ids, detail, identity) {
      const keys = new Set(array(Array.isArray(values) ? values : [values]).map(value => value && typeof value === "object" ? value.key : value).filter(known).map(text));
      if (!(options.rowKey === UNKNOWN_KEY ? !keys.size : keys.has(text(options.rowKey)))) return;
      if (matchedN >= offset && rows.length < limit) rows.push(displayRow(raw, ids || [], detail, identity));
      matchedN++;
    }, finish: () => ({ totalN, matchedN, rows, offset, hasMore: matchedN > offset + rows.length, available: true }) };
  }
  function reportCandidates(group, values, details, options) {
    const output = collector(group.totalN, options);
    group.ids.forEach(id => output.add(group.byId.get(id) || { eventId: id }, values.get(id) || [], [id], details && details.get(id)));
    return output.finish();
  }
  function book(context, key) { return context.codebooks && context.codebooks[key] || context.manifest && context.manifest.codes && context.manifest.codes[key] || {}; }
  function distanceBand(km) { return km <= 25 ? "0–25 km" : km <= 50 ? ">25–50 km" : km <= 100 ? ">50–100 km" : km <= 250 ? ">100–250 km" : km <= 500 ? ">250–500 km" : ">500 km"; }
  function pinMap(context, group, spatial) {
    const points = new Map(); array(context.spatialPoints).forEach(raw => { const point = spatial.normalizeSpatialPoint(raw, book(context, "ufoSpatialPoints")); if (group.ids.has(point.eventId) && coords(point)) points.set(point.eventId, point); }); return points;
  }
  function independentContext(options, slot, domain) {
    const contextApi = api(options, "contextApi", Context, "UfoAnalysisSessionContext"), context = options.context || {}, group = groupOf(options.groups[slot]);
    if (!contextApi) return unavailable(null, "The independent context scope engine is not loaded.", options.offset);
    const scoped = contextApi.scopedContext(context[domain], group.cohort, Object.assign({}, options.settings, { spatialApi: api(options, "spatialApi", Spatial, "UfoAnalysisSpatial"), contextOrdinalEpoch: options.contextOrdinalEpoch || "unix_day" }));
    if (scoped.status !== "ready") return unavailable(null, scoped.reason, options.offset);
    const field = options.domainKey.slice(domain.length + 1), output = collector(scoped.rows.length, options);
    scoped.rows.forEach(function (row) {
      let values = row[field];
      if (field === "morphology" || field === "species") values = row[field] || (known(row.category) ? [row.category] : []);
      else if (field === "coordinateEvidenceClass") values = row.coordinateEvidenceClass || row.coordinateClass;
      else if (field === "reviewState") values = row.reviewState || row.status;
      else if (field === "eligibility") values = typeof row.strictEligible === "boolean" ? row.strictEligible ? "qualified" : "not_qualified" : null;
      else if (field === "sourceFamily") values = row.sourceFamilyIds;
      output.add(row, values, [], [row.dateRole ? "Date role: " + pretty(row.dateRole) : "Date role unknown", row.datePrecision ? "Date precision: " + pretty(row.datePrecision) : ""].filter(Boolean).join(". "));
    });
    return Object.assign(output.finish(), { notes: scoped.notes });
  }
  function collections(options, group) {
    const engine = api(options, "collectionApi", Collections, "UfoAnalysisCollectionEvidence"), original = options.collectionEvidence;
    if (!engine || !original || !Array.isArray(original.reports)) return unavailable(group.totalN, "Verified collection evidence is not loaded.", options.offset);
    const evidence = Object.assign({}, original, { reports: original.reports.filter(row => row.canonicalJoinStatus === "validated_id_source_chunk_index") }), values = new Map(), details = new Map(), settings = options.settings || {};
    const selected = options.domainKey === "collection_versions" ? evidence.reports.filter(row => group.ids.has(text(row.eventId))) : engine.compute({ evidence, allowedEventIds: group.ids,
      disposition: settings.collectionEvidence === "all" ? "allcontexts" : "direct", scope: settings.collectionEvidence === "all" ? "allmaterials" : "soilplants", includeMemberVariants: settings.includeMemberVariants === true }).reports;
    selected.forEach(function (row) {
      const id = text(row.eventId); if (!group.ids.has(id)) return;
      const key = options.domainKey;
      const labels = key === "collection_coverage" ? ["indexed_selected_collection"] : key === "collection_material" ? row.materials : key === "collection_action" ? row.actions :
        key === "collection_source_family" ? [row.sourceFamily] : key === "collection_provisional_family" ? [row.provisionalGroup] : key === "collection_versions" ? [row.canonicalPrimaryDiffers ? "member_variant" : "primary_version"] : [];
      values.set(id, labels); details.set(id, ["Reviewed source account", row.disposition && "disposition: " + pretty(row.disposition), row.sourceFamily && "source family: " + row.sourceFamily,
        row.canonicalPrimaryDiffers ? "Merged member narrative differs from the primary report" : ""].filter(Boolean).join(". "));
    }); return reportCandidates(group, values, details, options);
  }
  function facilities(options, group) {
    const context = options.context || {}, spatial = api(options, "spatialApi", Spatial, "UfoAnalysisSpatial"), settings = options.settings || {}, values = new Map(), details = new Map();
    if (!spatial || !Array.isArray(context.facilities) || !Array.isArray(context.spatialPoints)) return unavailable(group.totalN, "Facility and qualified-point artifacts must be loaded.", options.offset);
    const radius = num(settings.spatialRadiusKm) > 0 ? Number(settings.spatialRadiusKm) : 100, points = pinMap(context, group, spatial), inventory = context.facilities
      .filter(row => spatial.facilityIsInferential(row, book(context, "facilityAnalysis"))).map(row => spatial.normalizeFacility(row, book(context, "facilityAnalysis")));
    points.forEach(function (point, id) {
      let nearest = null;
      inventory.forEach(function (facility) {
        const day = num(point.ordinal), ordinal = day == null ? null : day + (["unix_day"].includes(settings.spatialOrdinalEpoch) ? OFFSET : 0);
        if (spatial.facilityActiveAt(facility, ordinal, point.year) !== "active") return;
        const km = spatial.greatCircleDistanceMeters(point.lat, point.lon, facility.lat, facility.lon) / 1000;
        if (!nearest || km < nearest.km) nearest = { km, facility };
      });
      if (!nearest) return;
      const value = options.domainKey === "facility_distance" ? distanceBand(nearest.km) : options.domainKey === "facility_class" ? nearest.facility.facilityClass :
        nearest.facility.uncertaintyKm > 0 && Math.abs(nearest.km - radius) <= nearest.facility.uncertaintyKm ? "boundary_uncertain" : nearest.km <= radius ? "within_radius" : "beyond_radius";
      values.set(id, [value]); details.set(id, "Nearest known qualifying active facility: " + text(first(nearest.facility.name, nearest.facility.label, nearest.facility.id)) + "; marker distance " + nearest.km.toFixed(2) + " km. This does not establish association.");
    }); return reportCandidates(group, values, details, options);
  }
  function spatial(options, group) {
    const context = options.context || {}, engine = api(options, "spatialApi", Spatial, "UfoAnalysisSpatial"), settings = options.settings || {};
    if (!engine || !Array.isArray(context.neighbors) || !Array.isArray(context.spatialPoints)) return unavailable(options.domainKey.startsWith("spatial_pair_") ? null : group.totalN, "Qualified point/neighbor artifacts must be loaded.", options.offset);
    const points = pinMap(context, group, engine), radius = Math.min(100, num(settings.spatialRadiusKm) > 0 ? Number(settings.spatialRadiusKm) : 100), pairs = [], touched = new Set(), seen = new Set();
    context.neighbors.forEach(function (raw) {
      const edge = engine.normalizeEdge(raw);
      if (!edge.contractValid || edge.duplicateCandidate || !points.has(edge.eventIdA) || !points.has(edge.eventIdB) || edge.eventIdA === edge.eventIdB || edge.distanceMeters > radius * 1000 || edge.dayGap > 30) return;
      const key = [edge.eventIdA, edge.eventIdB].sort().join("|"); if (seen.has(key)) return; seen.add(key); pairs.push(edge); touched.add(edge.eventIdA); touched.add(edge.eventIdB);
    });
    if (!options.domainKey.startsWith("spatial_pair_")) {
      const values = new Map(); group.ids.forEach(id => { if (options.domainKey === "spatial_eligibility") values.set(id, [points.has(id) ? "pinned_qualified" : "outside_pinned_pool"]);
        else if (points.has(id)) values.set(id, [touched.has(id) ? "has_captured_neighbor" : "no_indexed_captured_neighbor"]); });
      return reportCandidates(group, values, null, options);
    }
    const output = collector(pairs.length, options);
    pairs.forEach(function (edge) {
      const field = options.domainKey.slice("spatial_pair_".length), value = field === "distance" ? distanceBand(edge.distanceMeters / 1000) : field === "lag" ? edge.dayGap === 0 ? "Same calendar day" : edge.dayGap <= 7 ? "1–7 days" : "8–30 days" :
        edge.crossSource == null ? null : edge.crossSource ? "Different catalog sources" : "Same catalog source";
      output.add({ label: "Reports " + edge.eventIdA + " / " + edge.eventIdB }, [value], [edge.eventIdA, edge.eventIdB],
        "Unique unordered qualified report pair. Marker distance " + (edge.distanceMeters / 1000).toFixed(2) + " km; absolute calendar gap " + edge.dayGap + " days. No measured travel path.", [edge.eventIdA, edge.eventIdB].sort().join("|"));
    }); return output.finish();
  }
  function relationships(options, group) {
    const context = options.context || {}, key = options.domainKey;
    if (key.startsWith("report_")) { const field = { report_date_precision: "datePrecision", report_coordinate_source: "coordinateSource", report_craft_confidence: "craftConfidence" }[key], values = new Map(); group.rows.forEach(row => values.set(idOf(row), [row[field]])); return reportCandidates(group, values, null, options); }
    if (key === "context_neighbor_lane") {
      const engine = api(options, "spatialApi", Spatial, "UfoAnalysisSpatial");
      if (!engine || !Array.isArray(context.contextNeighbors)) return unavailable(null, "Context-neighbor evidence is not loaded.", options.offset);
      const seen = new Set(), rows = context.contextNeighbors.map(row => engine.normalizeContextNeighbor(row, book(context, "contextUfoNeighbors"))).filter(function (row) {
        const identity = [row.ufoEventId, row.contextId, row.lane, row.dateRole].join("|");
        if (!group.ids.has(row.ufoEventId) || !row.dateRole.startsWith("observed_") || row.originUfoExcluded || row.originPublisherExcluded || seen.has(identity)) return false; seen.add(identity); return true;
      }), output = collector(rows.length, options);
      rows.forEach(row => output.add({ id: [row.ufoEventId, row.contextId, row.lane, row.dateRole].join("|"), label: "Report " + row.ufoEventId + " / context " + row.contextId }, [row.lane], [row.ufoEventId], "Observed context-marker pair; " + row.dateRole + ". A marker neighborhood does not establish a physical relationship.")); return output.finish();
    }
    if (!Array.isArray(context.relationships)) return unavailable(key === "relationship_coverage" ? group.totalN : null, "Relationship reconciliation evidence is not loaded.", options.offset);
    const codes = book(context, "relationshipReconciliation"), decode = (name, value) => Number.isInteger(value) ? array(codes[name])[value] || "unknown" : value, seen = new Set(), rows = context.relationships.map(raw => Array.isArray(raw) ?
      { id: text(raw[0]), eventId: text(raw[7]), type: decode("relationshipType", raw[5]), review: decode("reviewState", raw[6]), reconciliation: decode("reconciliationStatus", raw[8]), eligibility: typeof raw[9] === "boolean" ? raw[9] : null } :
      { id: text(raw.relationshipId), eventId: text(raw.currentUfoEventId), type: decode("relationshipType", first(raw.relationshipType, raw.relationshipTypeCode)), review: decode("reviewState", first(raw.reviewState, raw.reviewStateCode)), reconciliation: decode("reconciliationStatus", first(raw.reconciliation, raw.reconciliationStatus, raw.reconciliationStatusCode)), eligibility: typeof raw.associationEligible === "boolean" ? raw.associationEligible : null }).filter(row => {
        if (!row.id || !group.ids.has(row.eventId) || seen.has(row.id)) return false; seen.add(row.id); return true;
      });
    if (key === "relationship_coverage") return reportCandidates(group, new Map(rows.map(row => [row.eventId, ["indexed_exact_join"]])), null, options);
    const output = collector(rows.length, options), field = key.slice("relationship_".length);
    rows.forEach(row => output.add({ id: row.id, label: "Relationship " + row.id }, [field === "eligibility" ? row.eligibility == null ? null : row.eligibility ? "qualified" : "not_qualified" : row[field]], [row.eventId],
      "Explicit current-report ID join. Type: " + pretty(row.type) + "; review: " + pretty(row.review) + "; reconciliation: " + pretty(row.reconciliation) + ".")); return output.finish();
  }
  function noncraft(row) {
    const key = value => text(value).toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "");
    return row.isUfoReport === false || row.isContext === true || ["non_ufo_context", "conventional_or_explained"].includes(key(row.craftType)) ||
      ["astronomical_scientific_event", "military_government_event", "nuclear_atomic_event", "nuclear_atomic_weapons_test", "historical_publication", "crop_circle", "crop_circles", "animal_mutilation_report", "animal_mutilation_reports", "animal_mutilation", "animal_mutilations", "non_ufo_context", "conventional_or_explained"].includes(key(row.type)) ||
      ["astronomical_scientific_space_activity", "historical_publication_media_organization", "military_government_intelligence_aerospace", "nuclear_atomic_weapons_test", "non_ufo_context"].includes(key(first(row.visualTypeGroup, row.visual_type_group)));
  }
  function comparisonSource(options, slot) {
    const engine = api(options, "comparisonsApi", Comparisons, "UfoAnalysisSessionComparisons"), settings = engine ? engine.normalizeSettings(options.settings) : Object.assign({ sourceDomain: "craft" }, options.settings), group = groupOf(options.groups[slot]), domain = settings.sourceDomain;
    const source = domain === "craft" ? group.rows : first(options.groups[slot].context, options.context && options.context[slot], options.context, {})[domain];
    if (!Array.isArray(source)) return { unavailable: "The captured comparison source catalog is not loaded.", settings, group };
    if (domain === "craft" && group.rows.length !== group.ids.size) return { unavailable: "Exact report metadata is missing for part of the frozen group.", settings, group };
    const seen = new Set(), rows = [];
    source.forEach(function (raw, index) {
      const id = idOf(raw) || "row:" + index; if (seen.has(id)) return; seen.add(id);
      const row = Object.assign({}, raw, { id, eventId: id });
      const epoch = options.groups[slot].ordinalEpoch || options.ordinalEpoch || "unix_day";
      ["sortOrdinal", "ordinal", "startOrdinal", "endOrdinal", "dateStartOrdinal", "dateEndOrdinal"].forEach(key => { const day = num(row[key]); row[key] = day == null ? null : day - (epoch === "python_day" ? OFFSET : 0); });
      row.startOrdinal = first(row.startOrdinal, row.dateStartOrdinal, row.ordinal, row.sortOrdinal); row.endOrdinal = first(row.endOrdinal, row.dateEndOrdinal, row.ordinal, row.sortOrdinal, row.startOrdinal); row.sortOrdinal = first(row.sortOrdinal, row.startOrdinal);
      row.datePrecision = first(row.datePrecision, row.date_precision, "unknown"); row.coordinateEvidenceClass = first(row.coordinateEvidenceClass, row.analysisCoordinateClass, row.coordinateSource, "unknown");
      if (noncraft(row)) row.isContext = true;
      if (row.mapped === false) { row.lat = null; row.lon = null; row.lng = null; }
      if (row.encounterOccurrenceDateExcluded === true) { ["sortOrdinal", "ordinal", "startOrdinal", "endOrdinal", "dateStartOrdinal", "dateEndOrdinal"].forEach(key => { row[key] = null; }); row.datePrecision = "unknown"; row.utcTimestampVerified = false; row.utc_timestamp_verified = false; }
      rows.push(row);
    }); return { rows, settings, group, domain };
  }
  function domainInput(rows, domain) { return { rows: domain === "craft" ? rows : [], crops: domain === "crops" ? rows : [], animals: domain === "animals" ? rows : [], ordinalEpoch: "unix_day", contextOrdinalEpoch: "unix_day" }; }
  function verifiedUtc(row) {
    const stamp = first(row.utcTimestamp, row.utc_timestamp, row.observationUtc);
    if (row.utcTimestampVerified !== true && row.utc_timestamp_verified !== true || !text(first(row.timeZoneProvenance, row.timezoneProvenance, row.utcTimestampProvenance)).replace(/^unknown$/, "")) return null;
    if (typeof stamp !== "string" || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})$/.test(stamp)) return null;
    const ms = Date.parse(stamp), match = /([+-])(\d{2}):(\d{2})$/.exec(stamp), offset = match ? (match[1] === "+" ? 1 : -1) * (Number(match[2]) * 60 + Number(match[3])) : 0;
    return Number.isFinite(ms) && Math.abs(offset) <= 840 && new Date(ms + offset * 60000).toISOString().slice(0, 10) === stamp.slice(0, 10) ? ms : null;
  }
  function celestial(options, source) {
    const key = options.domainKey, values = new Map(), details = new Map(), settings = source.settings, rows = source.rows;
    if (key.startsWith("lunar_")) {
      const lunar = api(options, "lunarApi", Lunar, "UfoAnalysisLunar"); if (!lunar) return unavailable(rows.length, "The Moon calculation engine is not loaded.", options.offset);
      rows.forEach(function (row) {
        const id = idOf(row); if (source.domain === "craft" && noncraft(row)) { if (key === "lunar_sky_coverage") values.set(id, ["non_ufo_context"]); return; }
        if (["lunar_horizon", "lunar_azimuth", "lunar_sky_coverage"].includes(key)) {
          const sky = lunar.moonSkyPosition(row);
          if (key === "lunar_sky_coverage") values.set(id, [sky.eligible ? "verified" : sky.reason]);
          else if (sky.eligible) values.set(id, [key === "lunar_horizon" ? sky.aboveHorizon ? "above" : "below" : ["N", "NE", "E", "SE", "S", "SW", "W", "NW"][Math.floor(((sky.azimuth + 22.5) % 360) / 45)]]);
          if (sky.eligible) details.set(id, "Verified UTC Moon location: " + sky.timestamp + "; geometric elevation " + sky.elevation + "°, azimuth " + sky.azimuth + "°. Horizon does not establish visibility."); return;
        }
        if (row.datePrecision !== "exact_day" || row.startOrdinal !== row.endOrdinal || !Number.isInteger(row.startOrdinal)) return;
        const phase = lunar.phaseForDay(row.startOrdinal, "unix_day"); if (!phase) return;
        const utc = verifiedUtc(row), exact = utc != null && Math.abs(utc / DAY - row.startOrdinal) <= 2 ? lunar.phaseAtUtc(utc) : null;
        const phaseId = exact ? lunar.PHASES[exact.index].id : phase.phaseId, illumination = exact ? exact.illumination : phase.illumination, stable = exact ? true : phase.stablePhase;
        values.set(id, [key === "lunar_phase" ? phaseId : key === "lunar_illumination" ? illumination < .25 ? "dark" : illumination < .75 ? "middle" : "bright" : stable ? "stable" : "ambiguous"]);
        details.set(id, exact ? "Moon state uses explicitly verified UTC. This is a descriptive comparison." : "Moon state uses the UTC-noon estimate for this source calendar date. Its possible civil-day interval may cross a phase/category boundary.");
      });
    } else {
      const planetary = api(options, "planetaryApi", Planetary, "UfoAnalysisPlanetary"); if (!planetary) return unavailable(rows.length, "The planetary calculation engine is not loaded.", options.offset);
      if (key === "planetary_houses") {
        rows.forEach(row => values.set(idOf(row), ["missing_inputs"]));
        planetary.preparePlanetaryCohort(Object.assign(domainInput(rows, source.domain), { onPreparedReport: (row, prepared) => values.set(idOf(row), [prepared._houseInputEligible ? "verified_inputs" : "missing_inputs"]) }));
      } else {
        let kind = key === "planetary_motion" ? "motion" : key.startsWith("planetary_aspect_") ? "aspects" : "zodiac", axisId = settings.planet.toLowerCase(), prefix = "";
        if (key.startsWith("planetary_all_")) { kind = key.slice("planetary_all_".length); const split = text(options.rowKey).lastIndexOf(":"); axisId = split > 0 ? text(options.rowKey).slice(0, split) : "venus"; prefix = axisId + ":"; }
        else if (kind === "aspects") { const partner = key.slice("planetary_aspect_".length), order = planetary.PLANETS.map(value => value.toLowerCase()); axisId = [axisId, partner].sort((a, b) => order.indexOf(a) - order.indexOf(b)).join("__"); }
        if (options.rowKey === UNKNOWN_KEY && key.startsWith("planetary_all_")) { kind = "zodiac"; axisId = "venus"; prefix = ""; }
        planetary.inspectHeatmapReports(Object.assign(domainInput(rows, source.domain), { kind, axisId, zodiacSystem: settings.zodiacSystem, ayanamsaId: settings.ayanamsaId, aspectOrbDegrees: settings.orb,
          onReportMembership: function (row, member) { values.set(idOf(row), [key === "planetary_stability" ? member.stable ? "stable" : "ambiguous" : prefix + member.column]);
            details.set(idOf(row), "Displayed planetary cell uses its noon estimate with verified-UTC override where available. Stable–possible count bounds may also include records assigned to other cells at noon."); } }));
      }
    }
    const output = collector(rows.length, options); rows.forEach(row => output.add(row, values.get(idOf(row)) || [], source.domain === "craft" ? [idOf(row)] : [], details.get(idOf(row)))); return output.finish();
  }
  function nuclear(options, source) {
    const engine = api(options, "nuclearApi", Nuclear, "UfoAnalysisNuclear"), input = options.nuclear || {}, key = options.domainKey, settings = source.settings, seen = new Set();
    const allTests = (Array.isArray(input) ? input : array(input.tests || input.events)).filter(test => { const id = text(first(test.id, test.name + ":" + test.ordinal)); if (!Number.isInteger(test.ordinal) || seen.has(id)) return false; seen.add(id); return true; }).slice().sort((a, b) => a.ordinal - b.ordinal);
    const inventory = array(input.nuclearFacilities).filter(row => row.nuclearRoleSourceVerified === true && coords(row)), isFacility = key.startsWith("nuclear_facility_"), isPair = key.startsWith("nuclear_pair_");
    if (!engine || !(isFacility ? inventory.length : allTests.length)) return unavailable(isPair ? null : source.rows.length, isFacility ? "Source-verified nuclear institution inventory is unavailable." : "Nuclear event chronology is unavailable.", options.offset);
    const tests = allTests.filter(test => settings.testRoles.includes(test.role)), firstDay = allTests[0]?.ordinal, lastDay = allTests[allTests.length - 1]?.ordinal, values = new Map(), details = new Map(), pairs = [], pairSeen = new Set();
    const bounds = [25, 100, 250, 500].filter(value => value < settings.nuclearRadiusKm).concat(settings.nuclearRadiusKm), phase = lag => lag < 0 ? "before" : lag > 0 ? "after" : "same_day";
    function lowerBound(day) { let low = 0, high = tests.length; while (low < high) { const mid = low + high >>> 1; if (tests[mid].ordinal < day) low = mid + 1; else high = mid; } return low; }
    source.rows.forEach(function (row) {
      const id = idOf(row), point = coords(row); if (!Number.isInteger(row.startOrdinal) || row.startOrdinal !== row.endOrdinal || row.datePrecision !== "exact_day" || source.domain === "craft" && noncraft(row)) return;
      const within = row.startOrdinal >= firstDay && row.startOrdinal <= lastDay;
      if (key === "nuclear_chronology_coverage") { values.set(id, [within ? "within_catalog_date_extent" : "outside_catalog_date_extent"]); return; }
      if (isFacility) {
        if (!point || !inventory.length) return;
        const roles = new Set(); let uncertain = false;
        inventory.forEach(function (facility) { if (engine.haversineKm(point, coords(facility)) > settings.nuclearRadiusKm) return; const status = engine.facilityActivity(facility, row.startOrdinal); if (status === "active") roles.add(first(facility.nuclearRole, "reviewed_nuclear_institution")); else if (status === "unknown") uncertain = true; });
        values.set(id, key === "nuclear_facility_role" ? roles.size ? Array.from(roles) : [uncertain ? "activity_unknown" : "no_confirmed_active_marker_match"] :
          [uncertain ? roles.size ? "confirmed_match_plus_uncertain_markers" : "activity_unknown" : roles.size ? "confirmed_active_marker_match" : "no_confirmed_active_marker_match"]); return;
      }
      if (!within) return;
      if ((isPair || key === "nuclear_spatial_reports") && !point) return;
      const phases = new Set(), roles = new Set();
      for (let index = lowerBound(row.startOrdinal - settings.nuclearWindowDays); index < tests.length && tests[index].ordinal <= row.startOrdinal + settings.nuclearWindowDays; index++) {
        const test = tests[index], lag = row.startOrdinal - test.ordinal, category = phase(lag);
        if (isPair || key === "nuclear_spatial_reports") {
          const target = coords(test); if (!target) continue; const km = engine.haversineKm(point, target); if (km > settings.nuclearRadiusKm) continue;
          phases.add(category);
          if (isPair) { const testId = text(first(test.id, test.name + ":" + test.ordinal)), identity = id + "|" + testId; if (pairSeen.has(identity)) continue; pairSeen.add(identity); pairs.push({ row, test, id: identity, phase: category, km, band: "km_" + bounds.find(value => km <= value) }); }
        } else { phases.add(category); roles.add(test.role || "unknown"); }
      }
      if (!isPair) values.set(id, key === "nuclear_temporal_roles" ? roles.size ? Array.from(roles) : ["no_catalog_test_in_window"] : phases.size ? Array.from(phases) : [key === "nuclear_spatial_reports" ? "no_link" : "no_catalog_test_in_window"]);
      details.set(id, "Source calendar dates compared with nuclear GMT catalog dates within ±" + settings.nuclearWindowDays + " days" + (key === "nuclear_spatial_reports" ? " and " + settings.nuclearRadiusKm + " km" : "") + ". Same day does not establish temporal order.");
    });
    const output = collector(isPair ? pairs.length : source.rows.length, options);
    if (isPair) pairs.forEach(pair => output.add({ id: pair.id, label: "Report/catalog " + idOf(pair.row) + " / " + text(first(pair.test.name, pair.test.id)), date: dateOf(pair.row), location: displayRow(pair.row, [], "").location, source: pair.row.source, sourceUrl: urlOf(pair.row) }, [key === "nuclear_pair_phase" ? pair.phase : pair.band], source.domain === "craft" ? [idOf(pair.row)] : [],
      "Report/test pair; nuclear date " + iso(pair.test.ordinal) + "; test role " + text(pair.test.role) + "; marker distance " + pair.km.toFixed(2) + " km. Calendar order is not verified UTC order."));
    else source.rows.forEach(row => output.add(row, values.get(idOf(row)) || [], source.domain === "craft" ? [idOf(row)] : [], details.get(idOf(row))));
    return output.finish();
  }
  function verify(result, options, slot) {
    const dimension = options.dimension; if (!dimension || !result.available) return result;
    const side = dimension[slot.toLowerCase()] || dimension[slot], row = dimension.row || dimension.selectedRow || dimension.selectedrow || {}, expected = options.rowKey === UNKNOWN_KEY ? side && side.unknownN : first(row[slot.toLowerCase() + "Count"], row[slot.toLowerCase()], dimension.rows && dimension.rows.find(item => text(item.key) === text(options.rowKey))?.[slot.toLowerCase() + "Count"]);
    if (side && side.available === false) return unavailable(side.totalN, side.reason || "This captured side is unavailable for the selected dimension.", result.offset);
    if (side && Number.isSafeInteger(side.totalN) && side.totalN !== result.totalN || Number.isSafeInteger(expected) && expected !== result.matchedN) throw new Error("Exact row inspection disagrees with the displayed " + options.domainKey + " denominator/count for group " + slot + ". Refresh the comparison before inspecting it.");
    return result;
  }
  function inspect(input) {
    const options = Object.assign({}, input || {}); options.domainKey = text(options.domainKey).replace(/^external:/, ""); options.rowKey = text(options.rowKey); options.offset = Math.max(0, Math.floor(num(options.offset) || 0));
    if (!options.domainKey || !options.rowKey || !options.groups || !options.groups.A || !options.groups.B) throw new Error("Inspection requires a dimension, a category and both frozen groups.");
    const results = {}, notes = ["Exact membership for the displayed category; A and B retain their own units and denominators. Shared records may appear in both groups.", "Report buttons use only verified held report IDs. Independent context records and test IDs are not invented UFO report joins."];
    ["A", "B"].forEach(function (slot) {
      const group = groupOf(options.groups[slot]), key = options.domainKey, declared = options.dimension && (options.dimension[slot.toLowerCase()] || options.dimension[slot]); let result;
      if (declared && declared.available === false) result = unavailable(declared.totalN, declared.reason || "This captured side is unavailable for this dimension.", options.offset);
      else if (/^(crops|animals)_/.test(key)) result = independentContext(options, slot, key.startsWith("crops_") ? "crops" : "animals");
      else if (key.startsWith("collection_")) result = collections(options, group);
      else if (key.startsWith("facility_")) result = facilities(options, group);
      else if (key.startsWith("spatial_")) result = spatial(options, group);
      else if (/^(relationship_|report_|context_neighbor_lane)/.test(key)) result = relationships(options, group);
      else if (/^(lunar_|planetary_|nuclear_)/.test(key)) { const source = comparisonSource(options, slot); result = source.unavailable ? unavailable(null, source.unavailable, options.offset) : key.startsWith("nuclear_") ? nuclear(options, source) : celestial(options, source); }
      else result = unavailable(group.totalN, "This external dimension has no exact membership inspection contract.", options.offset);
      results[slot] = verify(result, options, slot); if (result.notes) notes.push(...result.notes);
    });
    const descriptor = options.dimension || {}, selected = descriptor.row || descriptor.selectedRow || descriptor.selectedrow || {};
    if (/^(lunar_|planetary_)/.test(options.domainKey)) notes.push("Date-only astronomical cell membership follows the displayed UTC-noon estimate with verified-UTC overrides. Stable–possible bounds are not confidence intervals and may include records in other midpoint cells.");
    return { title: text(descriptor.label) || pretty(options.domainKey), category: text(selected.label) || (options.rowKey === UNKNOWN_KEY ? "Unknown / ineligible" : pretty(options.rowKey)), unit: text(descriptor.unit) || (/^(crops_)/.test(options.domainKey) ? "crop-circle catalog records" : /^(animals_)/.test(options.domainKey) ? "animal-report catalog records" : options.domainKey.startsWith("spatial_pair_") ? "unique unordered qualified report pairs" : options.domainKey.startsWith("nuclear_pair_") ? "report/catalog record-test pairs" : options.domainKey === "context_neighbor_lane" ? "report-to-context marker pairs" : options.domainKey.startsWith("relationship_") && options.domainKey !== "relationship_coverage" ? "provenance relationship records" : "captured catalog reports"), groups: results, notes: Array.from(new Set(notes)) };
  }
  return Object.freeze({ inspect });
});

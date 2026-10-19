(function (root, factory) {
  "use strict";
  const node = typeof module === "object" && module.exports;
  const api = factory(node ? require("./analysis_lunar.js") : root.UfoAnalysisLunar,
    node ? require("./analysis_planetary.js") : root.UfoAnalysisPlanetary,
    node ? require("./analysis_nuclear.js") : root.UfoAnalysisNuclear);
  if (node) module.exports = api;
  if (root) root.UfoAnalysisSessionComparisons = api;
})(typeof self !== "undefined" ? self : globalThis, function (Lunar, Planetary, Nuclear) {
  "use strict";
  const VERSION = "temporary-group-context-comparisons-v1";
  const OFFSET = 719163;
  const SOURCE_NAMES = { craft: "captured UFO reports", crops: "crop-circle catalog records", animals: "animal-report catalog records" };
  const UNITS = { craft: "canonical_reports", crops: "crop_catalog_records", animals: "animal_catalog_records" };
  const DAY_NOTE = "Date-only celestial states are UTC-noon estimates. Stable/possible counts span the full possible civil-day UTC interval; they are sampled bounds, not confidence intervals.";
  function first(...values) { return values.find(value => value != null && value !== ""); }
  function finite(value) { return value == null || value === "" || typeof value === "boolean" || !Number.isFinite(Number(value)) ? null : Number(value); }
  function number(value, fallback, min, max) { const n = finite(value); return n == null ? fallback : Math.max(min, Math.min(max, n)); }
  function settingsOf(input) {
    const settings = input || {}, zodiac = settings.zodiac || (settings.zodiacSystem === "tropical" ? "tropical" : "sidereal_lahiri");
    if (!["sidereal_lahiri", "sidereal_fagan_bradley", "tropical"].includes(zodiac)) throw new Error("Unsupported comparison zodiac convention.");
    const planet = settings.planet || "Venus", partner = first(settings.partner, settings.aspectPartner, planet === "Mars" ? "Moon" : "Mars");
    return { sourceDomain: ["craft", "crops", "animals"].includes(settings.sourceDomain) ? settings.sourceDomain : "craft", planet, partner,
      zodiac, zodiacSystem: zodiac === "tropical" ? "tropical" : "sidereal", ayanamsaId: zodiac === "sidereal_fagan_bradley" ? "fagan_bradley" : "lahiri",
      orb: number(first(settings.orb, settings.aspectOrbDegrees), 3, 0.01, 10),
      nuclearWindowDays: Math.round(number(first(settings.nuclearWindowDays, settings.windowDays), 30, 1, 90)),
      nuclearRadiusKm: number(first(settings.nuclearRadiusKm, settings.maxDistanceKm), 500, 1, 2000),
      planetaryHeatmaps: settings.planetaryHeatmaps !== false,
      testRoles: Array.isArray(settings.testRoles) ? settings.testRoles.map(String) : ["weapons", "peaceful", "combat"] };
  }
  function side(totalN, eligibleN, rows, available = true, extra) {
    if (!Number.isSafeInteger(totalN) || totalN < 0 || !Number.isSafeInteger(eligibleN) || eligibleN < 0 || eligibleN > totalN) throw new Error("Invalid temporary comparison denominator.");
    const output = (rows || []).map(row => ({ ...row, key: String(first(row.key, row.id, row.label)), label: String(first(row.label, row.key, row.id)), count: Number(row.count) }));
    if (output.some(row => !Number.isSafeInteger(row.count) || row.count < 0 || row.count > eligibleN)) throw new Error("Invalid temporary comparison count.");
    return Object.assign({ available, totalN, eligibleN, unknownN: totalN - eligibleN, rows: output }, extra || {});
  }
  function dimension(key, label, unit, a, b, notes, extra) { return Object.assign({ key, label, unit, notes: notes || [], a, b }, extra || {}); }
  function unavailable(totalN) { return side(totalN, 0, [], false); }
  function normalizeRows(values, epoch, wanted) {
    const seen = new Set(), output = [];
    for (let index = 0; index < values.length; index++) {
      const original = values[index] || {}, id = String(first(original.eventId, original.event_id, original.id, original.analysisId, "row:" + index));
      if (wanted && !wanted.has(id)) throw new Error("A context comparison received a report outside its captured group.");
      if (seen.has(id)) continue; seen.add(id);
      const row = { ...original, eventId: id, id };
      for (const key of ["sortOrdinal", "ordinal", "startOrdinal", "endOrdinal", "dateStartOrdinal", "dateEndOrdinal"]) {
        const value = finite(row[key]); row[key] = value == null ? null : value - (epoch === "python_day" ? OFFSET : 0);
      }
      row.startOrdinal = first(row.startOrdinal, row.dateStartOrdinal, row.ordinal, row.sortOrdinal);
      row.endOrdinal = first(row.endOrdinal, row.dateEndOrdinal, row.ordinal, row.sortOrdinal, row.startOrdinal);
      row.sortOrdinal = first(row.sortOrdinal, row.startOrdinal);
      row.datePrecision = first(row.datePrecision, row.date_precision, "unknown");
      row.coordinateEvidenceClass = first(row.coordinateEvidenceClass, row.analysisCoordinateClass, row.coordinateSource, "unknown");
      if (noncraft(row)) row.isContext = true;
      if (row.mapped === false) { row.lat = null; row.lon = null; row.lng = null; }
      if (row.encounterOccurrenceDateExcluded === true) {
        for (const key of ["sortOrdinal", "ordinal", "startOrdinal", "endOrdinal", "dateStartOrdinal", "dateEndOrdinal"]) row[key] = null;
        row.datePrecision = "unknown"; row.utcTimestampVerified = false; row.utc_timestamp_verified = false;
      }
      output.push(row);
    }
    if (wanted && seen.size !== wanted.size) throw new Error("A context comparison is missing captured report identities.");
    return output;
  }
  function rangeFor(cohort, rows, epoch) {
    const time = cohort?.scope?.timeRange || cohort?.provenance?.capturedSnapshot?.timeRange || {};
    const fromIso = value => typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value) ? Date.parse(value + "T00:00:00Z") / 86400000 : null;
    const start = first(fromIso(time.startIso), finite(time.startOrdinal) == null ? null : finite(time.startOrdinal) - (epoch === "python_day" ? OFFSET : 0));
    const end = first(fromIso(time.endIso), finite(time.endOrdinal) == null ? null : finite(time.endOrdinal) - (epoch === "python_day" ? OFFSET : 0));
    let low = Infinity, high = -Infinity;
    for (const row of rows) if (finite(row.startOrdinal) != null) { low = Math.min(low, row.startOrdinal); high = Math.max(high, first(row.endOrdinal, row.startOrdinal)); }
    // Captured explicit report IDs are authoritative. A stale inherited map
    // window must not silently remove members from the frozen population.
    if (start != null && end != null) return { start: Math.min(start, end, low), end: Math.max(start, end, high) };
    return low <= high ? { start: low, end: high } : null;
  }
  function domainOptions(rows, selected, range) {
    return { rows: selected === "craft" ? rows : [], crops: selected === "crops" ? rows : [], animals: selected === "animals" ? rows : [],
      ordinalEpoch: "unix_day", contextOrdinalEpoch: "unix_day", range, startOrdinal: range?.start, endOrdinal: range?.end };
  }
  function domain(model, selected) { const key = selected === "craft" ? "ufo" : selected; return Array.isArray(model.domains) ? model.domains.find(item => item.id === key) : model.domains[key]; }
  function binsSide(rows, total, eligible) { return side(total, eligible, rows.map(row => ({ key: row.id, label: row.label, count: row.count,
    lowerCount: first(row.lowerCount, row.stableCount), upperCount: first(row.upperCount, row.possibleCount) }))); }
  function phaseDimensions(groups, selected, unit) {
    const output = groups.map(group => domain(Lunar.computeLunarContext(domainOptions(group.rows, selected, group.range)), selected));
    const result = [];
    result.push(dimension("lunar_phase", "Moon phase", unit, ...output.map(item => binsSide(item.phaseBins, item.total, item.phaseEligible)), [DAY_NOTE]));
    result.push(dimension("lunar_illumination", "Moon illumination", unit, ...output.map(item => binsSide(item.illumination.bins, item.total, item.phaseEligible)), [DAY_NOTE]));
    result.push(dimension("lunar_phase_stability", "Moon phase date uncertainty", unit, ...output.map(item => side(item.total, item.phaseEligible,
      [{ key: "stable", label: "Phase stable across possible time interval", count: item.stablePhaseCount }, { key: "ambiguous", label: "Phase can cross a sector boundary", count: item.ambiguousPhaseCount }])), ["Unknown source clocks and timezones remain uncertain, including when a noon estimate falls in a named phase."]));
    const skyNotes = ["Moon location requires explicitly verified UTC, timezone provenance and source-verified coordinates. Recorded coordinate uncertainty above 5 km is excluded; missing uncertainty is not assumed to be zero. No local clock is promoted to UTC.", "Above the geometric horizon does not establish visibility through terrain, clouds or atmosphere."];
    result.push(dimension("lunar_horizon", "Moon above / below horizon", unit, ...output.map(item => side(item.total, item.sky.eligible,
      [{ key: "above", label: "Above geometric horizon", count: item.sky.aboveHorizon }, { key: "below", label: "Below geometric horizon", count: item.sky.belowHorizon }])), skyNotes));
    result.push(dimension("lunar_azimuth", "Moon compass position", unit, ...output.map(item => side(item.total, item.sky.eligible, item.sky.azimuthBins.map(row => ({ key: row.label, label: row.label, count: row.count })))), skyNotes));
    result.push(dimension("lunar_sky_coverage", "Moon location input coverage", unit, ...output.map(item => side(item.total, item.total,
      [{ key: "verified", label: "Verified time and location", count: item.sky.eligible }, ...Object.entries(item.sky.excluded).map(([key, count]) => ({ key, label: key.replace(/_/g, " "), count })),
        ...(item.nonReportContextCount ? [{ key: "non_ufo_context", label: "Non-UFO context record", count: item.nonReportContextCount }] : [])])), skyNotes));
    return result;
  }
  function planetaryDimensions(groups, selected, unit, settings) {
    const config = { planet: settings.planet, aspectPartner: settings.partner, zodiacSystem: settings.zodiacSystem, ayanamsaId: settings.ayanamsaId,
      aspectOrbDegrees: settings.orb, samplingMode: "common_grid" };
    const prepared = groups.map(group => Planetary.preparePlanetaryCohort(domainOptions(group.rows, selected, group.range)));
    const output = prepared.map(preparedCohort => domain(Planetary.computePlanetaryContext({ ...config, preparedCohort }), selected));
    const notes = [DAY_NOTE, settings.zodiacSystem === "tropical" ? "Tropical zodiac: twelve equal ecliptic-longitude sectors." : "Sidereal zodiac: " + (settings.ayanamsaId === "lahiri" ? "Lahiri" : "Fagan-Bradley") + " ayanamsa, twelve equal sectors; signs are not unequal astronomical constellations.", "Slow-planet positions track calendar era. These descriptive differences establish no astrological cause."];
    const result = [dimension("planetary_sign", settings.planet + " zodiac sign", unit, ...output.map(item => binsSide(item.signBins, item.total, item.positionEligible)), notes),
      dimension("planetary_motion", settings.planet + " apparent motion", unit, ...output.map(item => binsSide(item.motion.bins, item.total, item.positionEligible)), notes.concat("Near stationary means an absolute apparent longitude rate of at most 0.01 degree/day."))];
    const partners = output[0].aspectPartners;
    partners.forEach((partner, index) => result.push(dimension("planetary_aspect_" + partner.partner.toLowerCase(), settings.planet + " / " + partner.partner + " aspects (±" + settings.orb + "°)", unit,
      ...output.map(item => binsSide(item.aspectPartners[index].bins.concat(item.aspectPartners[index].outsideBand), item.total, item.positionEligible)), notes.concat("Five major angular bands plus outside-band estimates partition each eligible record. Ecliptic latitude is not included."))));
    result.push(dimension("planetary_stability", settings.planet + " zodiac date uncertainty", unit, ...output.map(item => side(item.total, item.positionEligible,
      [{ key: "stable", label: "Sign stable across sampled interval", count: item.stableSignCount }, { key: "ambiguous", label: "Sign may change within possible interval", count: item.ambiguousSignCount }])), notes));
    result.push(dimension("planetary_houses", "Astrological house input coverage", unit, ...output.map(item => side(item.total, item.total,
      [{ key: "verified_inputs", label: "Verified time and source location available", count: item.houses.eligibleInputs }, { key: "missing_inputs", label: "Verified time or source location missing", count: item.total - item.houses.eligibleInputs }], true, { calculated: false })),
      ["Houses and ascendant are not calculated. Verified UTC/timezone, trustworthy coordinates and an explicit house-system convention are required; input coverage is not a house assignment."]));
    if (settings.planetaryHeatmaps) {
      const grids = prepared.map(preparedCohort => domain(Planetary.computePlanetaryHeatmaps({ ...config, preparedCohort }), selected));
      for (const [kind, label] of [["zodiac", "All planetary signs"], ["motion", "All planetary motions"], ["aspects", "All planetary aspect pairs"]]) {
        result.push(dimension("planetary_all_" + kind, label, unit, ...grids.map(item => side(item.total, item.positionEligible,
          item.matrices[kind].rows.flatMap(row => row.cells.map(cell => ({ key: row.id + ":" + cell.id, label: row.label + " · " + cell.label,
            count: cell.count, lowerCount: cell.lowerCount, upperCount: cell.upperCount, matrixRow: row.id, matrixColumn: cell.id }))))),
          notes.concat("Each body or unordered body pair has its own partition of the same eligible records. Do not sum cells across different bodies/pairs; one record contributes to several rows."), { multiLabel: true, heatmap: { kind, rows: grids[0].matrices[kind].rows.map(row => ({ key: row.id, label: row.label })), columns: grids[0].matrices[kind].columns.map(column => ({ key: column.id, label: column.label })) } }));
      }
    }
    return result;
  }
  function validExact(row) { return Number.isInteger(row.startOrdinal) && row.startOrdinal === row.endOrdinal && row.datePrecision === "exact_day"; }
  function point(row) { const lat = finite(row.lat), lon = finite(first(row.lon, row.lng)); return lat != null && lon != null && Math.abs(lat) <= 90 && Math.abs(lon) <= 180 ? { lat, lon } : null; }
  function noncraft(row) {
    const key = value => String(value || "").trim().toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "");
    return row.isUfoReport === false || row.isContext === true || ["non_ufo_context", "conventional_or_explained"].includes(key(row.craftType)) ||
      ["astronomical_scientific_event", "military_government_event", "nuclear_atomic_event", "nuclear_atomic_weapons_test", "historical_publication", "crop_circle", "crop_circles", "animal_mutilation_report", "animal_mutilation_reports", "animal_mutilation", "animal_mutilations", "non_ufo_context", "conventional_or_explained"].includes(key(row.type)) ||
      ["astronomical_scientific_space_activity", "historical_publication_media_organization", "military_government_intelligence_aerospace", "nuclear_atomic_weapons_test", "non_ufo_context"].includes(key(first(row.visualTypeGroup, row.visual_type_group)));
  }
  function countRows(map) { return Array.from(map, ([key, count]) => ({ key, label: key.replace(/_/g, " "), count })); }
  function increment(map, key, amount = 1) { map.set(key, (map.get(key) || 0) + amount); }
  function lowerBound(tests, day) { let low = 0, high = tests.length; while (low < high) { const middle = (low + high) >>> 1; if (tests[middle].ordinal < day) low = middle + 1; else high = middle; } return low; }
  function nuclearDimensions(groups, selected, unit, options, settings) {
    const input = options.nuclear || {}, seen = new Set();
    const allTests = (Array.isArray(input) ? input : input.tests || input.events || []).filter(test => {
      const id = String(first(test.id, test.name + ":" + test.ordinal));
      if (!Number.isInteger(test.ordinal) || seen.has(id)) return false; seen.add(id); return true;
    }).slice().sort((a, b) => a.ordinal - b.ordinal);
    const tests = allTests.filter(test => settings.testRoles.includes(test.role)), firstDay = allTests[0]?.ordinal, lastDay = allTests.at(-1)?.ordinal;
    const facilities = (input.nuclearFacilities || []).filter(row => row.nuclearRoleSourceVerified === true && point(row));
    const available = allTests.length > 0;
    const coverageNotes = ["The nuclear chronology is a partial source catalog. Its first/last dates define catalog extent, not complete observation coverage or proof of an explosion-free period.", "Nuclear dates are GMT; report dates retain source-calendar roles. Same-day or adjacent-day links do not establish temporal order."];
    const output = groups.map(group => {
      const coverage = new Map(), temporal = new Map(), temporalRoles = new Map(), facilityRoles = new Map(), activity = new Map();
      let temporalEligible = 0, coverageEligible = 0, facilityEligible = 0;
      const covered = [];
      for (const row of group.rows) {
        if (!validExact(row) || selected === "craft" && noncraft(row)) continue;
        coverageEligible++;
        const within = available && row.startOrdinal >= firstDay && row.startOrdinal <= lastDay;
        increment(coverage, !available ? "source_catalog_unavailable" : within ? "within_catalog_date_extent" : "outside_catalog_date_extent");
        if (within) {
          temporalEligible++;
          const phases = new Set(), roles = new Set();
          for (let index = lowerBound(tests, row.startOrdinal - settings.nuclearWindowDays); index < tests.length && tests[index].ordinal <= row.startOrdinal + settings.nuclearWindowDays; index++) {
            phases.add(row.startOrdinal < tests[index].ordinal ? "before" : row.startOrdinal > tests[index].ordinal ? "after" : "same_day"); roles.add(tests[index].role || "unknown");
          }
          if (!phases.size) { phases.add("no_catalog_test_in_window"); roles.add("no_catalog_test_in_window"); }
          phases.forEach(key => increment(temporal, key)); roles.forEach(key => increment(temporalRoles, key)); covered.push(row);
        }
        const location = point(row);
        if (location && facilities.length) {
          facilityEligible++;
          const roles = new Set(); let uncertain = false;
          for (const facility of facilities) if (Nuclear.haversineKm(location, point(facility)) <= settings.nuclearRadiusKm) {
            const status = Nuclear.facilityActivity(facility, row.startOrdinal);
            if (status === "active") roles.add(first(facility.nuclearRole, "reviewed_nuclear_institution"));
            else if (status === "unknown") uncertain = true;
          }
          roles.forEach(key => increment(facilityRoles, key));
          if (!roles.size) increment(facilityRoles, uncertain ? "activity_unknown" : "no_confirmed_active_marker_match");
          increment(activity, uncertain ? roles.size ? "confirmed_match_plus_uncertain_markers" : "activity_unknown" : roles.size ? "confirmed_active_marker_match" : "no_confirmed_active_marker_match");
        }
      }
      const shared = domainOptions(covered, selected, group.range);
      const computed = Nuclear.computeNuclearContext({ ...input, ...shared, tests: allTests, nuclearFacilities: facilities,
        broaderFacilities: Array.isArray(options.facilities) ? options.facilities : options.facilities?.rows || options.facilities?.facilities || [],
        facilityCodebook: options.facilityCodebook || {}, windowDays: settings.nuclearWindowDays, testRoles: settings.testRoles, maxDistanceKm: settings.nuclearRadiusKm });
      const data = domain(computed, selected), pairN = data.phases.reduce((sum, item) => sum + item.pairCount, 0);
      return { total: group.rows.length, coverage, coverageEligible, temporal, temporalRoles, temporalEligible, facilityRoles, activity, facilityEligible, data, pairN,
        coverageInfo: computed.coverage, facilityStatus: computed.facilities.status };
    });
    const result = [dimension("nuclear_chronology_coverage", "Nuclear chronology date coverage", unit, ...output.map(item => side(item.total, item.coverageEligible, countRows(item.coverage), available)), coverageNotes),
      dimension("nuclear_temporal", "Nuclear test calendar relationship (±" + settings.nuclearWindowDays + " days)", unit, ...output.map(item => side(item.total, item.temporalEligible, countRows(item.temporal), available)), coverageNotes.concat("Temporal matching is global and does not imply geographic proximity. Each report counts once in each applicable before/same-day/after category."), { multiLabel: true }),
      dimension("nuclear_temporal_roles", "Matched nuclear dates by test role", unit, ...output.map(item => side(item.total, item.temporalEligible, countRows(item.temporalRoles), available)), coverageNotes.concat("Role labels describe catalog nuclear events within the declared date window; a report may match more than one role."), { multiLabel: true }),
      dimension("nuclear_spatial_reports", "Nuclear test links within " + settings.nuclearRadiusKm + " km", unit, ...output.map(item => side(item.total, item.data.eligibleN,
        item.data.phases.map(row => ({ key: row.id, label: row.label, count: row.uniqueReports })).concat({ key: "no_link", label: "No catalog test link within declared date/distance", count: item.data.eligibleN - item.data.linkedReportsN }), available)), coverageNotes.concat("Requires an exact date and retained coordinates. Distances are between catalog markers, with incomplete uncertainty; each record may link to several tests or date phases."), { multiLabel: true }),
      dimension("nuclear_pair_phase", "Linked nuclear report/test pairs by calendar order", selected === "craft" ? "report_test_pairs" : "catalog_record_test_pairs", ...output.map(item => side(item.pairN, item.pairN, item.data.phases.map(row => ({ key: row.id, label: row.label, count: row.pairCount })), available)), coverageNotes.concat("Denominator is matching report/test pairs, not reports. A report may contribute several pairs.")),
      dimension("nuclear_pair_distance", "Linked nuclear report/test pair distances", selected === "craft" ? "report_test_pairs" : "catalog_record_test_pairs", ...output.map(item => side(item.pairN, item.pairN, item.data.distanceBands.map(row => ({ key: row.id, label: row.label, count: row.pairCount,
        unknownUncertaintyPairs: row.unknownUncertaintyPairs, uncertaintyBoundaryPairs: row.uncertaintyBoundaryPairs })), available)), coverageNotes.concat("Marker-distance bands are descriptive; missing coordinate uncertainty is not assumed to be zero.")),
      dimension("nuclear_facility_role", "Reviewed nuclear institution roles", unit, ...output.map(item => side(item.total, item.facilityEligible, countRows(item.facilityRoles), facilities.length > 0)),
        ["Only source-verified nuclear roles enter this inventory. It is partial; broader military/research markers have unreviewed nuclear status.", "One record can match several reviewed roles. Opening/closing uncertainty is retained; missing historical activity is labeled unknown."], { multiLabel: true }),
      dimension("nuclear_facility_activity", "Reviewed nuclear institution historical activity", unit, ...output.map(item => side(item.total, item.facilityEligible, countRows(item.activity), facilities.length > 0)),
        ["Historical organization activity does not prove daily facility operation, radioactive release, or a relationship to a report. Year-only opening and closing boundaries remain uncertain."])
    ];
    return result;
  }
  function compute(optionsValue) {
    const options = optionsValue || {}, settings = settingsOf(options.settings), selected = settings.sourceDomain;
    if (!Lunar || !Planetary || !Nuclear) throw new Error("The Moon, planetary and nuclear comparison modules must be loaded before temporary group comparisons.");
    const epoch = options.ordinalEpoch || "unix_day";
    if (!["unix_day", "python_day"].includes(epoch)) throw new Error("Temporary context comparison ordinalEpoch must be explicit Unix or Python days.");
    const groups = ["A", "B"].map(slot => {
      const group = options.groups?.[slot]; if (!group) throw new Error("Both captured groups are required.");
      const groupEpoch = group.ordinalEpoch || epoch;
      if (!["unix_day", "python_day"].includes(groupEpoch)) throw new Error("A captured group's ordinalEpoch is unsupported.");
      const context = group.context || options.context?.[slot] || options.context || {};
      const source = selected === "craft" ? group.rows : context[selected];
      if (!Array.isArray(source)) throw new Error("The captured " + SOURCE_NAMES[selected] + " are not ready for comparison.");
      const ids = selected === "craft" && Array.isArray(group.cohort?.eventIds) ? new Set(group.cohort.eventIds.map(String)) : null;
      const rows = normalizeRows(source, groupEpoch, ids);
      return { rows, cohort: group.cohort || {}, range: rangeFor(group.cohort || {}, rows, groupEpoch) };
    });
    const unit = UNITS[selected];
    const dimensions = phaseDimensions(groups, selected, unit).concat(planetaryDimensions(groups, selected, unit, settings), nuclearDimensions(groups, selected, unit, options, settings));
    return { status: "ready", estimatorVersion: VERSION, dimensions, settings,
      notes: ["A and B use the same declared settings and their own frozen membership. Counts describe " + SOURCE_NAMES[selected] + "; different records may describe the same incident.",
        "Crop catalog/discovery and animal reported/discovery dates retain their recorded roles; they are not promoted to formation or occurrence dates.",
        "Descriptive comparisons only: no p-values, independent-incident claims, or causal conclusions are supplied."],
      artifactHashes: { ...(options.artifactHashes || {}) }, inferenceEligible: false };
  }
  return Object.freeze({ VERSION, compute, normalizeSettings: settingsOf });
});

(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.UfoAnalysisNuclear = api;
})(typeof self !== "undefined" ? self : globalThis, function () {
  "use strict";

  const VERSION = "ufo-analysis-nuclear-v1.0.0";
  const DAY_MS = 86400000;
  const DEFAULT_ROLES = Object.freeze(["weapons", "peaceful", "combat"]);
  const DEFAULT_BANDS = Object.freeze([25, 100, 250, 500]);
  const PHASES = Object.freeze([
    { id: "before", label: "Earlier source dates" },
    { id: "same_day", label: "Same date (order unknown)" },
    { id: "after", label: "Later source dates" },
  ]);
  const FACILITY_GROUPS = Object.freeze([
    { id: "nuclear_only", label: "Near reviewed nuclear institutions only" },
    { id: "broader_only", label: "Near broader military/research markers only" },
    { id: "both", label: "Near both marker groups" },
    { id: "neither", label: "No confirmed active marker match" },
  ]);
  const CONTEXT_TYPES = new Set([
    "astronomical_scientific_event", "military_government_event", "nuclear_atomic_event",
    "nuclear_atomic_weapons_test", "historical_publication", "crop_circle", "crop_circles",
    "animal_mutilation_report", "animal_mutilation_reports", "animal_mutilation", "animal_mutilations",
    "non_ufo_context", "conventional_or_explained",
  ]);
  const CONTEXT_CRAFTS = new Set(["non_ufo_context", "conventional_or_explained"]);
  const CONTEXT_GROUPS = new Set([
    "astronomical_scientific_space_activity", "historical_publication_media_organization",
    "military_government_intelligence_aerospace", "nuclear_atomic_weapons_test", "non_ufo_context",
  ]);

  function finite(value) {
    if (value == null || typeof value === "boolean" || (typeof value === "string" && !value.trim())) return null;
    const n = Number(value);
    return Number.isFinite(n) ? n : null;
  }
  function text(value, fallback) { return value == null || String(value).trim() === "" ? (fallback || "") : String(value).trim(); }
  function first() { for (const value of arguments) if (value !== undefined && value !== null) return value; return null; }
  function categoryKey(value) { return text(value).toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, ""); }
  function coordinates(value) {
    const lat = finite(value.lat), lon = finite(first(value.lon, value.lng));
    return lat != null && lon != null && Math.abs(lat) <= 90 && Math.abs(lon) <= 180 ? { lat, lon } : null;
  }
  function haversineKm(a, b) {
    const rad = Math.PI / 180, dLat = (b.lat - a.lat) * rad, dLon = (b.lon - a.lon) * rad;
    const h = Math.sin(dLat / 2) ** 2 + Math.cos(a.lat * rad) * Math.cos(b.lat * rad) * Math.sin(dLon / 2) ** 2;
    return 6371.0088 * 2 * Math.asin(Math.sqrt(Math.min(1, Math.max(0, h))));
  }
  function phase(lag) { return lag < 0 ? "before" : lag > 0 ? "after" : "same_day"; }
  function yearAt(ordinal) { return new Date(ordinal * DAY_MS).getUTCFullYear(); }
  function normalizeRow(value, domain) {
    const row = value || {};
    const ordinal = finite(first(row.startOrdinal, row.ordinal, row.sortOrdinal));
    const end = finite(first(row.endOrdinal, row.ordinal, row.sortOrdinal, row.startOrdinal));
    const datePrecision = text(first(row.datePrecision, row.date_precision), "unknown").toLowerCase();
    const craft = text(first(row.craftType, row.craft, row.category, row.featureGroup), "unknown").toLowerCase();
    const kind = text(first(row.type, row.typeLabel, row.eventType, row.eventKind, row.categoryLabel));
    const point = coordinates(row);
    return {
      id: text(first(row.eventId, row.event_id, row.id, row.analysisId), domain + ":" + ordinal + ":" +
        (point ? point.lat + ":" + point.lon : "unmapped") + ":" + text(row.source)),
      domain, ordinal, end, datePrecision, craft, point,
      dateRole: text(first(row.dateRole, row.date_role), domain === "ufo" ? "catalog_event_date_unverified_timezone" : "unknown"),
      source: text(first(row.source, row.sourceFamilyId), "unknown"),
      uncertaintyKm: finite(first(row.uncertaintyKm, row.coordinateUncertaintyKm)),
      // Appearance categories, including fireball/meteor-like, are not identified
      // explanations. Only explicit context classifications or flags exclude a
      // record; no narrative or appearance word is used to infer a cause.
      noncraft: domain === "ufo" && (row.isUfoReport === false || row.isContext === true ||
        CONTEXT_TYPES.has(categoryKey(kind)) || CONTEXT_CRAFTS.has(categoryKey(craft)) ||
        CONTEXT_GROUPS.has(categoryKey(first(row.visualTypeGroup, row.visual_type_group)))),
      coordinateEvidenceClass: text(first(row.coordinateEvidenceClass, row.coordinateEvidence, row.locationPrecision), "unknown"),
    };
  }
  function validExactDate(row) {
    return row.ordinal != null && Number.isInteger(row.ordinal) && Math.abs(row.ordinal) < 2000000 &&
      row.end === row.ordinal && row.datePrecision === "exact_day";
  }
  function testIdentity(test) { return text(test.id, text(test.country) + ":" + test.ordinal + ":" + text(test.name)); }
  function normalizeTests(input) {
    const byId = new Map();
    for (const value of Array.isArray(input) ? input : []) {
      if (!value) continue;
      const ordinal = finite(first(value.ordinal, value.startOrdinal));
      if (ordinal == null || !Number.isInteger(ordinal)) continue;
      const test = { ...value, id: testIdentity(value), ordinal, point: coordinates(value), role: text(value.role, "unknown") };
      if (!byId.has(test.id)) byId.set(test.id, test);
    }
    return [...byId.values()].sort((a, b) => a.ordinal - b.ordinal || a.id.localeCompare(b.id));
  }
  function addIndex(index, anchor, startLag, endLag, item) {
    for (let lag = startLag; lag <= endLag; lag += 1) {
      const date = anchor + lag;
      let list = index.get(date);
      if (!list) { list = []; index.set(date, list); }
      list.push(item);
    }
  }
  function bandsOf(options) {
    let bounds = [...new Set((options.distanceBandsKm || DEFAULT_BANDS).map(finite).filter(x => x != null && x > 0 && x <= 2000))].sort((a, b) => a - b);
    if (!bounds.length) bounds = DEFAULT_BANDS.slice();
    const radius = finite(options.radiusKm);
    if (radius != null && radius > 0 && radius <= 2000) {
      bounds = bounds.filter(x => x < radius); bounds.push(radius);
    }
    return bounds.map((maxKm, i) => ({ id: "km_" + maxKm, minKm: i ? bounds[i - 1] : 0, maxKm,
      label: (i ? bounds[i - 1] + "–" : "0–") + maxKm + " km" }));
  }
  function bandAt(distance, bands) {
    for (let i = 0; i < bands.length; i += 1) if (distance <= bands[i].maxKm) return i;
    return -1;
  }
  function createDomain(domain, bands, windowDays) {
    return {
      domain, inputN: 0, eligibleN: 0, exclusions: {}, seen: new Set(), linked: new Set(), tests: new Set(),
      phases: PHASES.map(x => ({ ...x, pairCount: 0, reports: new Set() })),
      distanceBands: bands.map(x => ({ ...x, before: 0, sameDay: 0, after: 0, pairCount: 0, reports: new Set(),
        unknownUncertaintyPairs: 0, uncertaintyBoundaryPairs: 0 })),
      daily: Array.from({ length: windowDays * 2 + 1 }, (_, i) => ({ lag: i - windowDays, pairCount: 0, reports: new Set() })),
      dateRoles: new Map(), crafts: new Map(), sources: new Map(), eras: new Map(),
      calendarBoundaryPairs: 0, dayBoundaryExcluded: { before: 0, after: 0 },
      controls: { testPairCount: 0, controlPairCount: 0, testReports: new Set(), controlReports: new Set(),
        testSources: new Map(), controlSources: new Map() },
      facilityInputN: 0, facilityGroups: FACILITY_GROUPS.map(x => ({ ...x, reportsN: 0, crafts: new Map() })),
      nuclearBands: bands.map(x => ({ ...x, reportsN: 0 })), broaderBands: bands.map(x => ({ ...x, reportsN: 0 })),
      unknownFacilityActivityN: 0,
    };
  }
  function increment(map, key, delta) { map.set(key, (map.get(key) || 0) + (delta || 1)); }
  function exclude(state, reason) { state.exclusions[reason] = (state.exclusions[reason] || 0) + 1; }
  function mapCounts(map, keyName) {
    return [...map].map(([key, count]) => ({ [keyName]: key, count })).sort((a, b) => b.count - a.count || String(a[keyName]).localeCompare(String(b[keyName])));
  }
  function addMainPair(state, row, test, lag, distance, bandIndex) {
    const p = phase(lag), pEntry = state.phases[p === "before" ? 0 : p === "after" ? 2 : 1];
    pEntry.pairCount += 1; pEntry.reports.add(row.id);
    state.linked.add(row.id); state.tests.add(test.id);
    const band = state.distanceBands[bandIndex];
    band.pairCount += 1; band.reports.add(row.id); band[p === "same_day" ? "sameDay" : p] += 1;
    if (row.uncertaintyKm == null || finite(test.uncertaintyKm) == null) band.unknownUncertaintyPairs += 1;
    else {
      const uncertainty = Math.max(0, row.uncertaintyKm) + Math.max(0, finite(test.uncertaintyKm));
      if (distance + uncertainty > band.maxKm || (band.minKm > 0 && distance - uncertainty <= band.minKm)) band.uncertaintyBoundaryPairs += 1;
    }
    const daily = state.daily[lag + state.daily.length / 2 - 0.5];
    daily.pairCount += 1; daily.reports.add(row.id);
    const role = state.dateRoles.get(row.dateRole); role.pairCount += 1; role.reports.add(row.id);
    if (Math.abs(lag) <= 1) state.calendarBoundaryPairs += 1;
    else state.dayBoundaryExcluded[p] += 1;
    let craft = state.crafts.get(row.craft);
    if (!craft) { craft = { before: new Set(), same_day: new Set(), after: new Set(), all: new Set() }; state.crafts.set(row.craft, craft); }
    craft[p].add(row.id); craft.all.add(row.id);
    increment(state.sources, row.source); increment(state.eras, Math.floor(yearAt(row.ordinal) / 10) * 10);
  }
  function codeLabel(codebook, key, code) {
    const list = codebook && codebook[key];
    return Array.isArray(list) && list[code] != null ? String(list[code]) : String(code == null ? "unknown" : code);
  }
  function normalizeFacilities(options, nuclear) {
    const source = options.broaderFacilities || options.facilities || [];
    const nuclearIds = new Set(nuclear.flatMap(x => x.linkedFacilityIds || [x.id]));
    const codebook = options.facilityCodebook || {};
    const seen = new Set(), facilities = [];
    for (const value of source) {
      const row = Array.isArray(value) ? { id: value[0], facilityClass: codeLabel(codebook, "class", value[1]),
        name: value[2], lat: value[3], lon: value[4], uncertaintyKm: value[7], activeIntervals: value[9] } : value;
      if (!row || nuclearIds.has(row.id) || seen.has(row.id)) continue;
      // Claimed UFO bases do not become military/nuclear comparator facilities.
      if (!["military", "research_test", "research", "research/test", "1", "2"].includes(text(first(row.facilityClass, row.category, row.class)).toLowerCase())) continue;
      const point = coordinates(row);
      if (!point) continue;
      seen.add(row.id); facilities.push({ ...row, point });
    }
    return facilities;
  }
  function facilityActivity(facility, ordinal) {
    const intervals = facility.activeIntervals || [];
    const year = yearAt(ordinal);
    let uncertain = false;
    for (const raw of intervals) {
      const x = Array.isArray(raw) ? { startYear: raw[0], endYear: raw[1], boundaryUncertaintyYears: 1 } : (raw || {});
      if (x.startYear != null || x.endYear != null) {
        const start = finite(x.startYear), end = finite(x.endYear), boundary = Math.max(1, finite(x.boundaryUncertaintyYears) || 1);
        if ((start == null || year > start + boundary - 1) && (end == null || year < end - boundary + 1)) return "active";
        if ((start == null || year >= start - boundary) && (end == null || year <= end + boundary)) uncertain = true;
      } else {
        const start = finite(x.startOrdinal), end = finite(x.endOrdinal), boundary = Math.max(0, finite(x.boundaryUncertaintyDays) || 0);
        if ((start != null || end != null) && (start == null || ordinal >= start + boundary) && (end == null || ordinal <= end - boundary)) return "active";
        if ((start == null || ordinal >= start - boundary) && (end == null || ordinal <= end + boundary)) uncertain = true;
      }
    }
    return uncertain || !intervals.length ? "unknown" : "inactive";
  }
  function facilityGrid(facilities) {
    const grid = new Map();
    for (const f of facilities) {
      const key = Math.floor((f.point.lat + 90) / 10) + ":" + (Math.floor((f.point.lon + 180) / 10) % 36);
      let cell = grid.get(key); if (!cell) { cell = []; grid.set(key, cell); } cell.push(f);
    }
    return grid;
  }
  function nearestFacility(row, facilities, grid, radius) {
    if (!facilities.length) return { distance: null, unknown: false };
    const angular = radius / 6371.0088, latDelta = angular * 180 / Math.PI;
    const phi = row.point.lat * Math.PI / 180;
    const poleCrossed = Math.abs(phi) + angular >= Math.PI / 2;
    const lonDelta = poleCrossed ? 180 : Math.asin(Math.min(1, Math.sin(angular) / Math.cos(phi))) * 180 / Math.PI;
    const minY = Math.max(0, Math.floor((row.point.lat - latDelta + 90) / 10));
    const maxY = Math.min(18, Math.floor((row.point.lat + latDelta + 90) / 10));
    const xSet = new Set();
    for (let x = Math.floor((row.point.lon - lonDelta + 180) / 10); x <= Math.floor((row.point.lon + lonDelta + 180) / 10); x += 1) xSet.add(((x % 36) + 36) % 36);
    let nearest = null, unknown = false;
    for (let y = minY; y <= maxY; y += 1) for (const x of xSet) {
      for (const f of grid.get(y + ":" + x) || []) {
        if (Math.abs(row.point.lat - f.point.lat) > latDelta) continue;
        const distance = haversineKm(row.point, f.point);
        if (distance > radius) continue;
        const activity = facilityActivity(f, row.ordinal);
        if (activity === "unknown") { unknown = true; continue; }
        if (activity !== "active") continue;
        if (nearest == null || distance < nearest) nearest = distance;
      }
    }
    return { distance: nearest, unknown };
  }
  function facilityReport(state, row, nuclear, broad, nuclearGrid, broadGrid, bands) {
    if (!nuclear.length && !broad.length) return;
    state.facilityInputN += 1;
    const radius = bands[bands.length - 1].maxKm;
    const n = nearestFacility(row, nuclear, nuclearGrid, radius), b = nearestFacility(row, broad, broadGrid, radius);
    if (n.unknown || b.unknown) state.unknownFacilityActivityN += 1;
    const group = state.facilityGroups[n.distance != null ? (b.distance != null ? 2 : 0) : (b.distance != null ? 1 : 3)];
    group.reportsN += 1; increment(group.crafts, row.craft);
    if (n.distance != null) state.nuclearBands[bandAt(n.distance, bands)].reportsN += 1;
    if (b.distance != null) state.broaderBands[bandAt(b.distance, bands)].reportsN += 1;
  }

  function computeNuclearContext(optionsValue) {
    const options = optionsValue || {};
    const windowDays = Math.max(1, Math.min(90, Math.floor(finite(options.windowDays) || 30)));
    const bands = bandsOf(options), radius = bands[bands.length - 1].maxKm;
    const start = finite(options.startOrdinal), end = finite(options.endOrdinal);
    const rangeStart = start == null ? -Infinity : start, rangeEnd = end == null ? Infinity : end;
    const roles = new Set(options.testRoles || DEFAULT_ROLES);
    const allTests = normalizeTests(options.tests), roleTests = allTests.filter(t => roles.has(t.role));
    const selected = roleTests.filter(t => t.ordinal >= rangeStart - windowDays && t.ordinal <= rangeEnd + windowDays);
    const located = selected.filter(t => t.point);
    const mainIndex = new Map(), matchedIndex = new Map(), controlIndex = new Map();
    for (const test of located) addIndex(mainIndex, test.ordinal, -windowDays, windowDays, test);
    const catalogFirst = allTests.length ? allTests[0].ordinal : null;
    const catalogLast = allTests.length ? allTests[allTests.length - 1].ordinal : null;
    let testWindows = 0, controlWindows = 0, testWindowDays = 0, controlWindowDays = 0, unavailableControls = 0;
    for (const test of located) {
      const minLag = Math.max(-windowDays, Math.ceil(rangeStart - test.ordinal));
      const maxLag = Math.min(windowDays, Math.floor(rangeEnd - test.ordinal));
      if (minLag > maxLag) continue;
      const anchors = [];
      for (const shift of [-364, 364]) {
        const anchor = test.ordinal + shift;
        if (anchor + minLag < catalogFirst || anchor + maxLag > catalogLast) continue;
        // The comparison date must not overlap a known explosion at the same
        // region or within the displayed radius, including excluded safety tests.
        const contaminated = allTests.some(other => {
          if (other.ordinal < anchor + minLag || other.ordinal > anchor + maxLag) return false;
          if (other.country === test.country && text(other.region) === text(test.region)) return true;
          return other.point && haversineKm(other.point, test.point) <= radius;
        });
        if (!contaminated) anchors.push(anchor);
      }
      if (!anchors.length) { unavailableControls += 1; continue; }
      testWindows += 1; testWindowDays += maxLag - minLag + 1;
      addIndex(matchedIndex, test.ordinal, minLag, maxLag, test);
      for (const anchor of anchors) {
        controlWindows += 1; controlWindowDays += maxLag - minLag + 1;
        addIndex(controlIndex, anchor, minLag, maxLag, { test, anchor, id: test.id + ":control:" + anchor });
      }
    }
    const nuclear = (options.nuclearFacilities || []).filter(f => f && f.nuclearRoleSourceVerified === true && coordinates(f))
      .map(f => ({ ...f, point: coordinates(f) }));
    const broad = normalizeFacilities(options, nuclear), nuclearGrid = facilityGrid(nuclear), broadGrid = facilityGrid(broad);
    const states = { ufo: createDomain("ufo", bands, windowDays), crops: createDomain("crops", bands, windowDays), animals: createDomain("animals", bands, windowDays) };
    const visit = (value, domain) => {
      const row = normalizeRow(value, domain), state = states[domain];
      const inRange = row.ordinal != null && row.ordinal <= rangeEnd && (row.end == null ? row.ordinal : row.end) >= rangeStart;
      if (inRange || row.ordinal == null) state.inputN += 1;
      if (row.noncraft) { if (inRange) exclude(state, "noncraft_or_nuclear_context_record"); return; }
      if (!validExactDate(row)) { if (inRange || row.ordinal == null) exclude(state, "date_not_exact_day_or_interval"); return; }
      if (!row.point) { if (inRange) exclude(state, "coordinates_missing_or_invalid"); return; }
      // One report can link multiple tests; each report/test pair is counted
      // once, and unique report denominators are reported alongside pair counts.
      if (state.seen.has(row.id)) { if (inRange) exclude(state, "duplicate_report_identity"); return; }
      state.seen.add(row.id);
      if (inRange) {
        state.eligibleN += 1;
        let role = state.dateRoles.get(row.dateRole);
        if (!role) { role = { dateRole: row.dateRole, eligibleN: 0, pairCount: 0, reports: new Set() }; state.dateRoles.set(row.dateRole, role); }
        role.eligibleN += 1;
        for (const test of mainIndex.get(row.ordinal) || []) {
          const distance = haversineKm(row.point, test.point), index = bandAt(distance, bands);
          if (index >= 0) addMainPair(state, row, test, row.ordinal - test.ordinal, distance, index);
        }
        facilityReport(state, row, nuclear, broad, nuclearGrid, broadGrid, bands);
      }
      for (const test of matchedIndex.get(row.ordinal) || []) if (haversineKm(row.point, test.point) <= radius) {
        state.controls.testPairCount += 1; state.controls.testReports.add(row.id); increment(state.controls.testSources, row.source);
      }
      for (const control of controlIndex.get(row.ordinal) || []) if (haversineKm(row.point, control.test.point) <= radius) {
        state.controls.controlPairCount += 1; state.controls.controlReports.add(row.id); increment(state.controls.controlSources, row.source);
      }
    };
    if (typeof options.forEachRow === "function") options.forEachRow(row => visit(row, "ufo"));
    else for (const row of options.rows || []) visit(row, "ufo");
    for (const row of options.crops || []) visit(row, "crops");
    for (const row of options.animals || []) visit(row, "animals");

    const domains = {}, facilityDomains = {};
    for (const [domain, state] of Object.entries(states)) {
      const c = state.controls;
      const testDensity = testWindowDays ? c.testPairCount / testWindowDays : null;
      const controlDensity = controlWindowDays ? c.controlPairCount / controlWindowDays : null;
      const composition = [...state.crafts].map(([category, entries]) => ({ category, before: entries.before.size,
        sameDay: entries.same_day.size, after: entries.after.size, total: entries.all.size,
        share: state.linked.size ? entries.all.size / state.linked.size : 0 })).sort((a, b) => b.total - a.total || a.category.localeCompare(b.category));
      domains[domain] = {
        inputN: state.inputN, eligibleN: state.eligibleN, excludedN: Object.values(state.exclusions).reduce((sum, n) => sum + n, 0),
        exclusions: state.exclusions, linkedReportsN: state.linked.size, testsWithReportsN: state.tests.size,
        phases: state.phases.map(({ reports, ...x }) => ({ ...x, uniqueReports: reports.size })),
        distanceBands: state.distanceBands.map(({ reports, ...x }) => ({ ...x, uniqueReports: reports.size })),
        daily: state.daily.map(({ reports, ...x }) => ({ ...x, uniqueReports: reports.size })),
        byDateRole: [...state.dateRoles.values()].map(({ reports, ...x }) => ({ ...x, uniqueReports: reports.size })),
        craftComposition: composition, sourceComposition: mapCounts(state.sources, "source"), eraComposition: mapCounts(state.eras, "decade"),
        calendarBoundaryPairs: state.calendarBoundaryPairs, dayBoundaryExcluded: state.dayBoundaryExcluded,
        matchedControls: {
          status: testWindows ? "ready_descriptive" : "no_uncontaminated_calendar_controls", label: "Same site, same weekday, approximately same season in adjacent years",
          testWindows, controlWindows, testWindowDays, controlWindowDays, unavailableControls,
          testPairCount: c.testPairCount, controlPairCount: c.controlPairCount,
          uniqueTestReports: c.testReports.size, uniqueControlReports: c.controlReports.size,
          testReportsPerWindowDay: testDensity, controlReportsPerWindowDay: controlDensity,
          relativeReportDensity: controlDensity != null && controlDensity > 0 ? testDensity / controlDensity : null,
          testSources: mapCounts(c.testSources, "source"), controlSources: mapCounts(c.controlSources, "source"),
          warnings: ["Reference dates can lie outside selected dates; all other UFO cohort filters are shared.",
            "Counts are report/test-window pairs; overlapping windows share reports and are not independent samples.",
            "Known explosions, including safety tests, are excluded from calendar controls; absent or missing chronology is not proof of a test-free date.",
            "Adjacent-year reporting effort and population are not measured; the ratio is descriptive, not an incidence or causal effect."],
        },
      };
      facilityDomains[domain] = {
        eligibleN: state.facilityInputN, unknownActivityN: state.unknownFacilityActivityN,
        groups: state.facilityGroups.map(({ crafts, ...x }) => ({ ...x, share: state.facilityInputN ? x.reportsN / state.facilityInputN : 0,
          craftComposition: mapCounts(crafts, "category") })),
        nearestNuclearBands: state.nuclearBands, nearestBroaderBands: state.broaderBands,
      };
    }
    const coverage = { ...(options.coverage || {}), catalogRows: allTests.length, selectedRoles: [...roles],
      selectedTests: selected.length, locatedTests: located.length, missingCoordsN: selected.length - located.length,
      excludedSafetyN: allTests.filter(t => t.role === "safety_or_mixed_safety" && !roles.has(t.role)).length,
      sourcePeriod: { firstOrdinal: catalogFirst, lastOrdinal: catalogLast },
      selectedPeriod: { startOrdinal: start, endOrdinal: end },
      boundaryOverlappingTests: selected.filter(t => t.ordinal < rangeStart || t.ordinal > rangeEnd).length };
    return {
      estimatorVersion: VERSION, status: allTests.length ? "ready_descriptive" : "source_catalog_unavailable", coverage,
      settings: { windowDays, distanceBandsKm: bands.map(x => x.maxKm), testRoles: [...roles], maxDistanceKm: radius }, domains,
      facilities: { status: nuclear.length ? "ready_descriptive_partial_inventory" : "no_source_verified_nuclear_facilities",
        nuclearSitesN: nuclear.length, broaderSitesN: broad.length, sourceVerifiedN: nuclear.length, byDomain: facilityDomains,
        institutions: nuclear.map(f => ({ id: f.id, name: f.name, nuclearRole: f.nuclearRole, sources: f.sources || [] })),
        warnings: ["Nuclear institutions are a reviewed partial inventory, not all nuclear facilities or power reactors.",
          "Broader military/research markers have unreviewed nuclear status; they are not a verified nonnuclear control.",
          "Distances are to retained facility markers, not operating-unit or site boundaries.",
          "Year-only opening/closing boundaries are excluded, and historical organization activity does not establish daily facility operation."] },
      readiness: { status: "ready_descriptive", strictInference: "blocked", reasons: ["nuclear_marker_uncertainty_not_quantified",
        "report_dates_not_harmonized_to_GMT", "reporting_effort_unmeasured", "catalog_and_facility_coverage_incomplete"] },
      policyWarnings: ["Independent nuclear chronology is separate from nuclear/atomic records in the UFO catalog; context records are excluded from craft comparisons.",
        "Test dates are GMT; report dates are source calendar dates with unverified timezone. Same-date or adjacent-day links do not establish event order.",
        "Published nuclear locations are often approximate. Bands are descriptive marker comparisons, not verified proximity or radiation exposure.",
        "Crop formation, discovery, publication and animal incident/discovery dates retain their separate date roles.",
        "Unique reports and report/test pairs are both shown; one report may overlap several tests or phase groups.",
        "The FOA/SIPRI source ends in 1998. Its transcription has a stated-total discrepancy and some unverified primary-table lines."],
      sources: options.sources || [],
    };
  }

  return { ESTIMATOR_VERSION: VERSION, DEFAULT_TEST_ROLES: DEFAULT_ROLES, computeNuclearContext, haversineKm, facilityActivity };
});

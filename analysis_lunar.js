(function (root, factory) {
  "use strict";
  const astronomy = typeof module === "object" && module.exports
    ? require("./analysis_astronomy_engine.js") : root && root.Astronomy;
  const api = factory(astronomy);
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.UfoAnalysisLunar = api;
})(typeof self !== "undefined" ? self : globalThis, function (Astronomy) {
  "use strict";

  const VERSION = "lunar-context-v1.0.0";
  const DAY_MS = 86400000;
  const PYTHON_OFFSET = 719163;
  const PHASES = Object.freeze([
    { id: "new", label: "New Moon" }, { id: "waxing_crescent", label: "Waxing crescent" },
    { id: "first_quarter", label: "First quarter" }, { id: "waxing_gibbous", label: "Waxing gibbous" },
    { id: "full", label: "Full Moon" }, { id: "waning_gibbous", label: "Waning gibbous" },
    { id: "last_quarter", label: "Last quarter" }, { id: "waning_crescent", label: "Waning crescent" },
  ].map(Object.freeze));
  const SOURCE_COORDINATES = new Set(["source_coordinates", "source_provided", "source-provided", "source_exact", "exact"]);
  const NON_REPORT_TYPES = new Set(["nuclear / atomic event", "military / government event", "astronomical / scientific event", "historical / publication"]);
  const NON_REPORT_GROUPS = new Set(["nuclear / atomic / weapons test", "military / government / intelligence / aerospace", "astronomical / scientific / space activity", "historical / publication / media / organization"]);
  const dayCache = new Map();
  const monthCache = new Map();
  const MAX_CACHE_DAYS = 100000;
  const MINIMUM_DATE = Date.UTC(1582, 9, 15) / DAY_MS;
  const MAXIMUM_DATE = Date.UTC(2100, 11, 31) / DAY_MS;
  function finite(value) {
    if (value == null || value === "" || typeof value === "boolean") return null;
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
  }
  function text(value, fallback) { return String(value == null ? "" : value).trim() || fallback || "unknown"; }
  function first() { for (const value of arguments) if (value != null && value !== "") return value; return null; }
  function round(number, digits) { return number == null ? null : Math.round(number * (10 ** (digits || 6))) / (10 ** (digits || 6)); }
  function increment(object, key, amount) { object[key] = (object[key] || 0) + (amount == null ? 1 : amount); }
  function normalizeOrdinal(value, epoch) {
    const number = finite(value);
    return number == null || !Number.isInteger(number) ? null : number - (epoch === "python_day" ? PYTHON_OFFSET : 0);
  }
  function validateEpoch(value) {
    const epoch = value || "unix_day";
    if (epoch !== "unix_day" && epoch !== "python_day") throw new Error("Lunar ordinalEpoch must be unix_day or python_day.");
    return epoch;
  }
  function phaseIndex(angle) { return Math.floor(((angle + 22.5) % 360) / 45); }
  function phaseAtUtc(timestamp) {
    if (!Astronomy) throw new Error("The offline Astronomy Engine module is not loaded.");
    const date = new Date(timestamp);
    const angle = Astronomy.MoonPhase(date);
    const illumination = Astronomy.Illumination(Astronomy.Body.Moon, date).phase_fraction;
    return { angle, illumination, index: phaseIndex(angle) };
  }
  function possibleIndexes(lowAngle, highAngle) {
    const span = ((highAngle - lowAngle) + 360) % 360;
    const result = new Set([phaseIndex(lowAngle), phaseIndex(highAngle)]);
    // Lunar elongation increases monotonically during this bounded 52-hour window.
    const start = Math.floor((lowAngle + 22.5) / 45);
    const finish = Math.floor((lowAngle + span + 22.5) / 45);
    for (let bin = start; bin <= finish; bin += 1) result.add(((bin % 8) + 8) % 8);
    return Array.from(result).sort();
  }
  function phaseForDay(ordinalValue, ordinalEpoch) {
    const day = normalizeOrdinal(ordinalValue, validateEpoch(ordinalEpoch));
    if (day == null || day < MINIMUM_DATE || day > MAXIMUM_DATE) return null;
    if (dayCache.has(day)) return dayCache.get(day);
    const noon = phaseAtUtc((day + 0.5) * DAY_MS);
    // The complete civil day may lie anywhere from UTC-12 to UTC+14. Unknown
    // source clocks never become a fabricated observation timestamp.
    const low = phaseAtUtc((day - (14 / 24)) * DAY_MS);
    const high = phaseAtUtc((day + 1 + (12 / 24)) * DAY_MS);
    const indexes = possibleIndexes(low.angle, high.angle);
    const illuminationValues = [low.illumination, noon.illumination, high.illumination];
    if (indexes.indexOf(0) !== -1) illuminationValues.push(0);
    if (indexes.indexOf(4) !== -1) illuminationValues.push(1);
    const result = Object.freeze({ ordinal: day, phaseIndex: noon.index, phaseId: PHASES[noon.index].id,
      phaseAngle: round(noon.angle), illumination: round(noon.illumination), possiblePhaseIndexes: indexes,
      stablePhase: indexes.length === 1, illuminationRange: [round(Math.min.apply(null, illuminationValues)), round(Math.max.apply(null, illuminationValues))],
      utcIntervalMs: [(day - (14 / 24)) * DAY_MS, (day + 1 + (12 / 24)) * DAY_MS] });
    if (dayCache.size >= MAX_CACHE_DAYS) dayCache.delete(dayCache.keys().next().value);
    dayCache.set(day, result);
    return result;
  }
  function verifiedUtc(row) {
    const timestamp = first(row.utcTimestamp, row.utc_timestamp, row.observationUtc);
    if (row.utcTimestampVerified !== true && row.utc_timestamp_verified !== true) return { reason: "unverified_utc_timestamp" };
    if (!text(first(row.timeZoneProvenance, row.timezoneProvenance, row.utcTimestampProvenance), "").replace(/^unknown$/, "")) {
      return { reason: "missing_timezone_provenance" };
    }
    if (typeof timestamp !== "string" || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})$/.test(timestamp)) {
      return { reason: "timestamp_requires_explicit_offset" };
    }
    const milliseconds = Date.parse(timestamp);
    if (!Number.isFinite(milliseconds)) return { reason: "invalid_utc_timestamp" };
    const civil = timestamp.slice(0, 10);
    const offsetMatch = /([+-])(\d{2}):(\d{2})$/.exec(timestamp);
    const offsetMinutes = offsetMatch ? (offsetMatch[1] === "+" ? 1 : -1) * ((Number(offsetMatch[2]) * 60) + Number(offsetMatch[3])) : 0;
    if (Math.abs(offsetMinutes) > 14 * 60 || new Date(milliseconds + offsetMinutes * 60000).toISOString().slice(0, 10) !== civil) {
      return { reason: "invalid_utc_timestamp" };
    }
    return { timestamp: milliseconds };
  }
  function moonSkyPosition(rowValue) {
    const row = rowValue || {};
    const utc = verifiedUtc(row);
    if (utc.reason) return { eligible: false, reason: utc.reason };
    const lat = finite(row.lat), lon = finite(row.lon);
    if (lat == null || lon == null || Math.abs(lat) > 90 || Math.abs(lon) > 180) return { eligible: false, reason: "missing_valid_coordinates" };
    const coordinateClass = text(first(row.coordinateEvidenceClass, row.analysisCoordinateClass, row.coordinateSource, row.coordinate_source));
    if (!SOURCE_COORDINATES.has(coordinateClass)) return { eligible: false, reason: "coordinates_not_source_verified" };
    if (finite(first(row.uncertaintyKm, row.coordinateUncertaintyKm)) > 5) return { eligible: false, reason: "coordinate_uncertainty_above_5km" };
    const date = new Date(utc.timestamp);
    if (utc.timestamp / DAY_MS < MINIMUM_DATE || utc.timestamp / DAY_MS > MAXIMUM_DATE + 1) return { eligible: false, reason: "outside_supported_calendar" };
    const observer = new Astronomy.Observer(lat, lon, 0);
    const equator = Astronomy.Equator(Astronomy.Body.Moon, date, observer, true, true);
    const horizon = Astronomy.Horizon(date, observer, equator.ra, equator.dec, null);
    return { eligible: true, azimuth: round(horizon.azimuth, 4), elevation: round(horizon.altitude, 4),
      aboveHorizon: horizon.altitude >= 0, nearHorizon: Math.abs(horizon.altitude) < 1,
      refraction: "none", observerHeightMeters: 0, timestamp: date.toISOString() };
  }
  function dateInterval(row, epoch) {
    const start = normalizeOrdinal(first(row.startOrdinal, row.dateStartOrdinal, row.start_ordinal, row.sortOrdinal), epoch);
    const end = normalizeOrdinal(first(row.endOrdinal, row.dateEndOrdinal, row.end_ordinal, row.startOrdinal, row.dateStartOrdinal, row.sortOrdinal), epoch);
    return start == null || end == null || end < start ? null : { start, end };
  }
  function rangeValue(value, epoch) {
    if (!value) return null;
    const start = normalizeOrdinal(Array.isArray(value) ? value[0] : first(value.start, value.startOrdinal), epoch);
    const end = normalizeOrdinal(Array.isArray(value) ? value[1] : first(value.end, value.endOrdinal), epoch);
    return start == null || end == null ? null : { start: Math.min(start, end), end: Math.max(start, end) };
  }
  function blankDomain(id, label, role, categoryLabel) {
    return { id, label, dateRoleDefault: role, categoryLabel, total: 0, reportCount: 0, nonReportContextCount: 0, phaseEligible: 0, stablePhaseCount: 0,
      ambiguousPhaseCount: 0, outsideRange: 0, excluded: {}, dateRoles: {}, sourceCounts: {}, phaseByCategory: [],
      phaseBins: PHASES.map(function (phase) { return { id: phase.id, label: phase.label, count: 0, stableCount: 0, possibleCount: 0 }; }),
      illumination: { bins: [ { id: "dark", label: "0–25% illuminated", count: 0 }, { id: "middle", label: "25–75% illuminated", count: 0 }, { id: "bright", label: "75–100% illuminated", count: 0 } ], mean: null },
      sky: { eligible: 0, aboveHorizon: 0, belowHorizon: 0, nearHorizon: 0, excluded: {}, azimuthBins: PHASES.map(function (_phase, index) { return { label: ["N", "NE", "E", "SE", "S", "SW", "W", "NW"][index], count: 0 }; }), sample: [] },
      _months: new Map(), _categories: new Map(), _illuminationSum: 0 };
  }
  function addRecord(domain, rowValue, range, epoch) {
    const row = rowValue || {};
    const interval = dateInterval(row, epoch);
    if (range && interval && (interval.end < range.start || interval.start > range.end)) { domain.outsideRange += 1; return; }
    domain.total += 1;
    if (domain.id === "ufo" && (row.isUfoReport === false || row.isContext === true ||
        text(first(row.craftType, row.category)).toLowerCase() === "non_ufo_context" ||
        NON_REPORT_TYPES.has(text(row.type).toLowerCase()) ||
        NON_REPORT_GROUPS.has(text(first(row.visualTypeGroup, row.visual_type_group)).toLowerCase()))) {
      domain.nonReportContextCount += 1;
      increment(domain.excluded, "non_ufo_context");
      return;
    }
    domain.reportCount += 1;
    const role = text(first(row.dateRole, row.date_role), domain.dateRoleDefault);
    increment(domain.dateRoles, role);
    increment(domain.sourceCounts, text(first(row.source, row.sourceFamily, Array.isArray(row.sourceFamilyIds) ? row.sourceFamilyIds.join("; ") : null)));
    const sky = moonSkyPosition(row);
    if (!sky.eligible) increment(domain.sky.excluded, sky.reason);
    else {
      domain.sky.eligible += 1;
      domain.sky[sky.aboveHorizon ? "aboveHorizon" : "belowHorizon"] += 1;
      if (sky.nearHorizon) domain.sky.nearHorizon += 1;
      domain.sky.azimuthBins[phaseIndex(sky.azimuth)].count += 1;
      if (domain.sky.sample.length < 8) domain.sky.sample.push(Object.assign({ id: first(row.id, row.eventId), dateRole: role }, sky));
    }
    let reason = null;
    if (!interval) reason = "missing_date";
    else if (text(first(row.datePrecision, row.date_precision)) !== "exact_day" || interval.start !== interval.end) reason = "date_not_exact_day";
    else if (interval.start < MINIMUM_DATE) reason = "historical_calendar_not_verified_before_1582";
    else if (interval.start > MAXIMUM_DATE) reason = "outside_supported_calendar";
    if (reason) { increment(domain.excluded, reason); return; }
    const phase = phaseForDay(interval.start);
    const utc = verifiedUtc(row);
    let midpoint = phase.phaseIndex, illumination = phase.illumination, possible = phase.possiblePhaseIndexes, stable = phase.stablePhase;
    if (utc.timestamp != null && Math.abs((utc.timestamp / DAY_MS) - interval.start) <= 2) {
      const exact = phaseAtUtc(utc.timestamp);
      midpoint = exact.index; illumination = exact.illumination; possible = [exact.index]; stable = true;
    }
    domain.phaseEligible += 1;
    domain[stable ? "stablePhaseCount" : "ambiguousPhaseCount"] += 1;
    domain.phaseBins[midpoint].count += 1;
    if (stable) domain.phaseBins[midpoint].stableCount += 1;
    possible.forEach(function (index) { domain.phaseBins[index].possibleCount += 1; });
    domain.illumination.bins[illumination < 0.25 ? 0 : illumination < 0.75 ? 1 : 2].count += 1;
    domain._illuminationSum += illumination;
    const civil = new Date(interval.start * DAY_MS);
    const monthKey = civil.getUTCFullYear() + "-" + String(civil.getUTCMonth() + 1).padStart(2, "0");
    domain._months.set(monthKey, (domain._months.get(monthKey) || 0) + 1);
    const category = text(first(row.craftType, row.category, row.crop, Array.isArray(row.species) ? row.species.join(", ") : row.species));
    if (!domain._categories.has(category)) domain._categories.set(category, { category, total: 0, stableCount: 0, counts: new Array(8).fill(0) });
    const matrix = domain._categories.get(category);
    matrix.total += 1; matrix.counts[midpoint] += 1; if (stable) matrix.stableCount += 1;
  }
  function exposureMonth(key, range) {
    const cacheKey = key + "|" + (range ? range.start + ":" + range.end : "full");
    if (monthCache.has(cacheKey)) return monthCache.get(cacheKey);
    const parts = key.split("-").map(Number);
    let start = Math.floor(Date.UTC(parts[0], parts[1] - 1, 1) / DAY_MS);
    let end = Math.floor(Date.UTC(parts[0], parts[1], 1) / DAY_MS) - 1;
    if (range) { start = Math.max(start, range.start); end = Math.min(end, range.end); }
    const counts = new Array(8).fill(0);
    let days = 0;
    for (let day = start; day <= end; day += 1) {
      const phase = phaseForDay(day);
      if (!phase) continue;
      counts[phase.phaseIndex] += 1; days += 1;
    }
    const result = { counts, days };
    if (monthCache.size >= 5000) monthCache.delete(monthCache.keys().next().value);
    monthCache.set(cacheKey, result);
    return result;
  }
  function finalizeDomain(domain, range, categoryLimit) {
    const expected = new Array(8).fill(0);
    let calendarDays = 0;
    domain._months.forEach(function (weight, key) {
      const month = exposureMonth(key, range);
      calendarDays += month.days;
      if (month.days) month.counts.forEach(function (count, index) { expected[index] += weight * count / month.days; });
    });
    domain.phaseBins.forEach(function (bin, index) {
      bin.share = domain.phaseEligible ? round(bin.count / domain.phaseEligible) : null;
      bin.stableShare = domain.stablePhaseCount ? round(bin.stableCount / domain.stablePhaseCount) : null;
      bin.expectedCount = round(expected[index], 4);
      bin.expectedCalendarShare = domain.phaseEligible ? round(expected[index] / domain.phaseEligible) : null;
      bin.calendarAdjustedRatio = expected[index] > 0 ? round(bin.count / expected[index], 4) : null;
      bin.lowerCount = bin.stableCount; bin.upperCount = bin.possibleCount;
    });
    domain.phaseByCategory = Array.from(domain._categories.values()).sort(function (left, right) { return right.total - left.total || left.category.localeCompare(right.category); }).slice(0, categoryLimit).map(function (entry) {
      return { category: entry.category, total: entry.total, stableCount: entry.stableCount,
        bins: PHASES.map(function (phase, index) { return { id: phase.id, label: phase.label, count: entry.counts[index], share: round(entry.counts[index] / entry.total) }; }) };
    });
    domain.illumination.mean = domain.phaseEligible ? round(domain._illuminationSum / domain.phaseEligible) : null;
    domain.exposure = { method: "year_month_matched_calendar_days", representedMonths: domain._months.size, calendarDays,
      weighting: "Each represented year-month is weighted by its eligible report count; only selected calendar days are used.",
      opportunity: "Calendar opportunity only; observer effort, weather, source selection and reporting biases are not measured." };
    domain.sky.status = domain.sky.eligible ? "descriptive_verified_timestamps" : "unavailable_verified_utc_required";
    domain.status = domain.phaseEligible ? "descriptive" : "unavailable_exact_dates_required";
    delete domain._months; delete domain._categories; delete domain._illuminationSum;
    return domain;
  }
  function computeLunarContext(optionsValue) {
    const options = optionsValue || {};
    const epoch = validateEpoch(options.ordinalEpoch);
    const contextEpoch = validateEpoch(options.contextOrdinalEpoch || epoch);
    const range = rangeValue(first(options.range, options.activeRange), epoch);
    const domains = [blankDomain("ufo", "UFO / craft reports", "occurrence", "Craft category"),
      blankDomain("crops", "Crop-circle reports", "catalog_or_discovery_date_not_verified_formation", "Crop / morphology category"),
      blankDomain("animals", "Animal reports", "reported_or_discovery_date_not_verified_occurrence", "Species category")];
    const acceptUfo = function (row) { addRecord(domains[0], row, range, epoch); };
    if (typeof options.forEachRow === "function") options.forEachRow(acceptUfo);
    else (Array.isArray(options.rows) ? options.rows : []).forEach(acceptUfo);
    const contextRange = range; // Internally all intervals have been normalized to Unix days.
    const crops = first(options.crops, options.cropCircles) || [];
    const animals = first(options.animals, options.animalReports) || [];
    (Array.isArray(crops) ? crops : []).forEach(function (row) { addRecord(domains[1], row, contextRange, contextEpoch); });
    (Array.isArray(animals) ? animals : []).forEach(function (row) { addRecord(domains[2], row, contextRange, contextEpoch); });
    const limit = Math.max(1, Math.min(50, Math.trunc(finite(options.categoryLimit) || 16)));
    domains.forEach(function (domain) { finalizeDomain(domain, range, limit); });
    return { estimatorVersion: VERSION, ordinalEpoch: "unix_day", status: "descriptive", domains,
      phaseBins: PHASES, range, unitOfAnalysis: "dated catalog report, separated by domain and recorded date role",
      method: { ephemeris: "Astronomy Engine", version: "2.1.19", commit: "865d3da7d8112bbc7911238052c6af4aaf877181",
        source: "https://github.com/cosinekitty/astronomy", sha256: "d1b3ab4b86aa409f78c0f0d95162a847496cba7e938eb6f4712cf9c1c45f4a2e",
        phase: "Geocentric Sun–Moon elongation, eight 45-degree sectors centered on named phases.",
        dateOnly: "UTC-noon descriptive estimate, with the complete possible civil-day UTC interval (UTC+14 to UTC-12); ambiguous phases retain bounds.",
        sky: "Topocentric airless Moon-center azimuth/elevation; only source-verified coordinates and explicitly verified UTC timestamps with timezone provenance.",
        calendar: "Normalized Gregorian civil dates from 1582-10-15 through 2100-12-31; earlier dates excluded until original calendar is verified.",
        independentReference: "https://ssd.jpl.nasa.gov/horizons/manual.html" },
      warnings: ["Descriptive catalog associations, not evidence that the Moon caused a report or that an object was the Moon.",
        "Explicit non-UFO/context classifications, including nuclear, military, astronomical and publication entries, are excluded from UFO phase counts; unclassified UFO reports remain visible.",
        "Crop catalog/discovery and animal report/discovery dates are not promoted to formation or occurrence dates.",
        "Calendar-adjusted ratios correct phase opportunity within represented year-months, not observer effort or reporting bias.",
        "Date-only phase boundaries are uncertain; use the stable and possible counts to assess that uncertainty.",
        "Moon above the geometric horizon does not establish visibility: clouds, terrain, atmosphere and actual observer conditions are not recorded."],
      inferenceEligible: false, patternFinderEligible: false };
  }
  return { VERSION, PHASES, computeLunarContext, phaseForDay, phaseAtUtc, moonSkyPosition, normalizeOrdinal };
});

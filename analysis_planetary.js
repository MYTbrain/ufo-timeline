(function (root, factory) {
  "use strict";
  const astronomy = typeof module === "object" && module.exports
    ? require("./analysis_astronomy_engine.js") : root && root.Astronomy;
  const api = factory(astronomy);
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.UfoAnalysisPlanetary = api;
})(typeof self !== "undefined" ? self : globalThis, function (Astronomy) {
  "use strict";

  const VERSION = "planetary-context-v1.0.0";
  const DAY_MS = 86400000;
  const PYTHON_OFFSET = 719163;
  const MINIMUM_DATE = Date.UTC(1582, 9, 15) / DAY_MS;
  const MAXIMUM_DATE = Date.UTC(2100, 11, 31) / DAY_MS;
  const PLANETS = Object.freeze(["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune"]);
  const SIGNS = Object.freeze(["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"].map(function (label, index) {
    return Object.freeze({ id: label.toLowerCase(), label, symbol: ["♈", "♉", "♊", "♋", "♌", "♍", "♎", "♏", "♐", "♑", "♒", "♓"][index], startDegrees: index * 30 });
  }));
  const ASPECTS = Object.freeze([
    { id: "conjunction", label: "Conjunction", angleDegrees: 0 },
    { id: "sextile", label: "Sextile", angleDegrees: 60 },
    { id: "square", label: "Square", angleDegrees: 90 },
    { id: "trine", label: "Trine", angleDegrees: 120 },
    { id: "opposition", label: "Opposition", angleDegrees: 180 },
  ].map(Object.freeze));
  const MOTIONS = Object.freeze([{ id: "direct", label: "Direct" }, { id: "retrograde", label: "Retrograde" }, { id: "stationary", label: "Near stationary" }].map(Object.freeze));
  const NON_REPORT_TYPES = new Set(["nuclear / atomic event", "military / government event", "astronomical / scientific event", "historical / publication"]);
  const NON_REPORT_GROUPS = new Set(["nuclear / atomic / weapons test", "military / government / intelligence / aerospace", "astronomical / scientific / space activity", "historical / publication / media / organization"]);
  const dayCache = new Map();
  const noonCache = new Map();
  const monthCache = new Map();
  const heatmapDayCache = new Map();
  const heatmapMonthCache = new Map();
  const MAX_CACHE_DAYS = 100000;
  const SAMPLE_MARGIN_DEGREES = 0.02;
  const RATE_MARGIN_DEGREES_PER_DAY = 0.002;
  const STATIONARY_THRESHOLD = 0.01;
  const ATLAS_SCHEMA = "ufo-planetary-ephemeris-atlas-v1";
  const ATLAS_HOURS = Object.freeze([0, 4, 10, 12, 16, 22]);
  const ATLAS_MAGIC = "UFOPLANETARY1";
  const CONFIG_BRAND = Symbol("validated_planetary_configuration");
  let ephemerisAtlas = null;
  const physicalCounters = { atlasHits: 0, directEphemerisCalls: 0, rateFallbackCalls: 0, precessionHits: 0, precessionFallbackCalls: 0 };

  function finite(value) {
    if (value == null || value === "" || typeof value === "boolean") return null;
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
  }
  function first() { for (const value of arguments) if (value != null && value !== "") return value; return null; }
  function text(value, fallback) { return String(value == null ? "" : value).trim() || fallback || "unknown"; }
  function round(number, digits) { return number == null ? null : Math.round(number * (10 ** (digits == null ? 6 : digits))) / (10 ** (digits == null ? 6 : digits)); }
  function increment(object, key, amount) { object[key] = (object[key] || 0) + (amount == null ? 1 : amount); }
  function wrap(angle) { return ((angle % 360) + 360) % 360; }
  function signedDifference(left, right) { return ((left - right + 540) % 360) - 180; }
  function angularDistance(left, right) { return Math.abs(signedDifference(left, right)); }
  function ordinal(value, epoch) {
    const number = typeof value === "number" ? value : finite(value);
    return number == null || !Number.isInteger(number) ? null : number - (epoch === "python_day" ? PYTHON_OFFSET : 0);
  }
  function validateEpoch(value) {
    const epoch = value || "unix_day";
    if (epoch !== "unix_day" && epoch !== "python_day") throw new Error("Planetary ordinalEpoch must be unix_day or python_day.");
    return epoch;
  }
  function rangeValue(options, epoch) {
    const value = first(options.range, options.activeRange);
    const start = ordinal(value ? (Array.isArray(value) ? value[0] : first(value.start, value.startOrdinal)) : options.startOrdinal, epoch);
    const end = ordinal(value ? (Array.isArray(value) ? value[1] : first(value.end, value.endOrdinal)) : options.endOrdinal, epoch);
    return start == null || end == null ? null : { start: Math.min(start, end), end: Math.max(start, end) };
  }
  function bodyName(value, fallback) {
    if (PLANETS.includes(value)) return value;
    const body = PLANETS.find(function (planet) { return planet.toLowerCase() === text(value, fallback).toLowerCase(); });
    if (!body) throw new Error("Unsupported planetary body: " + value);
    return body;
  }
  function configuration(options) {
    if (options[CONFIG_BRAND]) return options;
    const planet = bodyName(options.planet, "Venus");
    const system = options.zodiacSystem || "sidereal";
    if (system !== "tropical" && system !== "sidereal") throw new Error("zodiacSystem must be tropical or sidereal.");
    const partner = options.aspectPartner === "all" ? "all" : bodyName(options.aspectPartner, planet === "Mars" ? "Moon" : "Mars");
    if (partner === planet) throw new Error("Aspect partner must differ from the selected body.");
    const orb = finite(options.aspectOrbDegrees) == null ? 3 : Number(options.aspectOrbDegrees);
    if (orb <= 0 || orb > 10) throw new Error("Aspect orb must be greater than zero and at most 10 degrees.");
    const convention = options.ayanamsaId || "lahiri";
    const samplingMode = options.samplingMode || "adaptive";
    if (samplingMode !== "adaptive" && samplingMode !== "common_grid") throw new Error("samplingMode must be adaptive or common_grid.");
    if (system === "sidereal" && convention !== "lahiri" && convention !== "fagan_bradley" && typeof options.ayanamsaDegreesAtUtc !== "function") {
      throw new Error("Unsupported sidereal ayanamsa convention.");
    }
    return { [CONFIG_BRAND]: true, planet, zodiacSystem: system, ayanamsaId: convention, aspectOrbDegrees: orb, aspectPartner: partner, samplingMode,
      partners: partner === "all" ? PLANETS.filter(function (body) { return body !== planet; }) : [partner],
      ayanamsaDegreesAtUtc: options.ayanamsaDegreesAtUtc || ayanamsaDegreesAtUtc,
      cacheKey: planet + "|" + system + "|" + convention + "|" + partner + "|" + orb + "|" + samplingMode,
      cacheable: options.cacheable !== false && (typeof options.ayanamsaDegreesAtUtc !== "function" || options.ayanamsaDegreesAtUtc === ayanamsaDegreesAtUtc) };
  }
  // The sidereal origin helper is pinned and described below. It deliberately
  // remains separate from the apparent tropical ephemeris and aspect geometry.
  function ayanamsaDegreesAtUtc(timestamp, convention) {
    if (!Astronomy) throw new Error("The offline Astronomy Engine module is not loaded.");
    if (convention !== "lahiri" && convention !== "fagan_bradley") throw new Error("Unsupported sidereal ayanamsa convention.");
    const milliseconds = timestamp instanceof Date ? timestamp.getTime() : Number(timestamp);
    const atlasPoint = ephemerisAtlas && ephemerisAtlas.locate(milliseconds);
    const origin = convention === "fagan_bradley" ? 24.740299972222225 : 23.857092333333334;
    if (atlasPoint != null) { physicalCounters.precessionHits += 1; return origin + ephemerisAtlas.precession[atlasPoint]; }
    physicalCounters.precessionFallbackCalls += 1;
    const time = Astronomy.MakeTime(timestamp instanceof Date ? timestamp : new Date(timestamp));
    const fixedJ2000Axis = Astronomy.RotateVector(Astronomy.Rotation_ECL_EQJ(), new Astronomy.Vector(1, 0, 0, time));
    const longitude = Astronomy.Ecliptic(fixedJ2000Axis).elon;
    const precession = longitude > 180 ? longitude - 360 : longitude;
    // These mean J2000 origins are frozen from the official Astrodienst Swiss
    // Ephemeris test service. Astronomy Engine supplies precession and nutation;
    // no Swiss Ephemeris implementation or library is bundled.
    return origin + precession;
  }
  function rawLongitude(planet, timestamp) {
    if (!Astronomy) throw new Error("The offline Astronomy Engine module is not loaded.");
    const index = ephemerisAtlas && ephemerisAtlas.valueIndex(planet, timestamp);
    if (index != null) { physicalCounters.atlasHits += 1; return ephemerisAtlas.longitudes[index]; }
    physicalCounters.directEphemerisCalls += 1;
    return Astronomy.Ecliptic(Astronomy.GeoVector(Astronomy.Body[planet], new Date(timestamp), true)).elon;
  }
  function longitudeRateAtUtc(planetValue, timestamp) {
    const planet = bodyName(planetValue);
    const index = ephemerisAtlas && ephemerisAtlas.valueIndex(planet, timestamp);
    if (index != null) {
      const rate = ephemerisAtlas.rates[index];
      const magnitude = Math.abs(rate);
      // Preserve rare exact classifications at Float32 rate boundaries. Normal
      // dates stay entirely offline; only a threshold-adjacent rate is resolved.
      if (![0.008, 0.01, 0.012, 0.05].some(function (boundary) { return Math.abs(magnitude - boundary) < 1e-7; })) {
        physicalCounters.atlasHits += 1; return rate;
      }
      physicalCounters.rateFallbackCalls += 1;
    }
    const halfDay = 0.125;
    return signedDifference(rawLongitude(planet, timestamp + halfDay * DAY_MS), rawLongitude(planet, timestamp - halfDay * DAY_MS)) / (2 * halfDay);
  }
  function positionAtUtc(planetValue, timestampValue, optionsValue) {
    const options = optionsValue || {};
    const planet = bodyName(planetValue);
    const timestamp = timestampValue instanceof Date ? timestampValue.getTime() : typeof timestampValue === "string" ? Date.parse(timestampValue) : finite(timestampValue);
    if (timestamp == null || !Number.isFinite(timestamp)) throw new Error("A valid explicit UTC timestamp is required.");
    const tropicalLongitude = rawLongitude(planet, timestamp);
    const system = options.zodiacSystem || "tropical";
    const offset = system === "sidereal" ? (options.ayanamsaDegreesAtUtc || ayanamsaDegreesAtUtc)(timestamp, options.ayanamsaId || "lahiri") : 0;
    if (!Number.isFinite(offset)) throw new Error("Sidereal ayanamsa must be finite.");
    const longitude = wrap(tropicalLongitude - offset);
    const speed = longitudeRateAtUtc(planet, timestamp);
    return { planet, timestamp: new Date(timestamp).toISOString(), tropicalLongitudeDegrees: round(tropicalLongitude), longitudeDegrees: round(longitude),
      ayanamsaDegrees: round(offset), zodiacSystem: system, signIndex: Math.floor(longitude / 30), signId: SIGNS[Math.floor(longitude / 30)].id,
      longitudeRateDegreesPerDay: round(speed), motionIndex: motionIndex(speed), motionId: MOTIONS[motionIndex(speed)].id };
  }
  function motionIndex(speed) { return Math.abs(speed) <= STATIONARY_THRESHOLD ? 2 : speed > 0 ? 0 : 1; }
  function aspectIndex(separation, orb) {
    for (let index = 0; index < ASPECTS.length; index += 1) if (Math.abs(separation - ASPECTS[index].angleDegrees) <= orb) return index;
    return -1;
  }
  function circularBins(low, high, width, count) {
    const result = new Set();
    for (let index = Math.floor(low / width); index <= Math.floor(high / width); index += 1) result.add(((index % count) + count) % count);
    return Array.from(result).sort(function (left, right) { return left - right; });
  }
  function sampledAspectIndexes(relativeAngles, orb) {
    const values = [];
    relativeAngles.forEach(function (angle, index) { values.push(index ? values[index - 1] + signedDifference(angle, relativeAngles[index - 1]) : angle); });
    const low = Math.min.apply(null, values) - SAMPLE_MARGIN_DEGREES;
    const high = Math.max.apply(null, values) + SAMPLE_MARGIN_DEGREES;
    const indexes = new Set();
    ASPECTS.forEach(function (aspect, index) {
      for (const sign of aspect.angleDegrees === 0 || aspect.angleDegrees === 180 ? [1] : [-1, 1]) {
        for (let turn = Math.floor(low / 360) - 1; turn <= Math.floor(high / 360) + 1; turn += 1) {
          const center = sign * aspect.angleDegrees + turn * 360;
          if (low <= center + orb && high >= center - orb) indexes.add(index);
        }
      }
    });
    return { indexes: Array.from(indexes).sort(), low, high };
  }
  function positionForDay(ordinalValue, optionsValue) {
    const options = optionsValue || {};
    const config = configuration(options);
    const day = ordinal(ordinalValue, validateEpoch(options.ordinalEpoch));
    if (day == null || day < MINIMUM_DATE || day > MAXIMUM_DATE) return null;
    const key = config.cacheKey + "|" + day;
    if (config.cacheable && dayCache.has(key)) return dayCache.get(key);
    const lowTime = day * DAY_MS - 14 * 3600000;
    const noonTime = day * DAY_MS + 12 * 3600000;
    const highTime = day * DAY_MS + 36 * 3600000;
    const sampleTimes = [lowTime, noonTime, highTime];
    const samples = new Map();
    function get(timestamp) {
      if (!samples.has(timestamp)) {
        const longitude = rawLongitude(config.planet, timestamp);
        const offset = config.zodiacSystem === "sidereal" ? config.ayanamsaDegreesAtUtc(timestamp, config.ayanamsaId) : 0;
        if (!Number.isFinite(offset)) throw new Error("Sidereal ayanamsa must be finite.");
        const partners = config.partners.map(function (partner) { return rawLongitude(partner, timestamp); });
        samples.set(timestamp, { timestamp, tropicalLongitude: longitude, longitude: wrap(longitude - offset),
          speed: longitudeRateAtUtc(config.planet, timestamp), partners });
      }
      return samples.get(timestamp);
    }
    sampleTimes.forEach(get);
    const noon = get(noonTime);
    const initial = sampleTimes.map(get);
    const nearSignBoundary = initial.some(function (point) { const withinSign = point.longitude % 30; return withinSign < 1 || withinSign > 29; });
    const nearStation = initial.some(function (point) { return Math.abs(point.speed) < 0.05; }) || initial.some(function (point) { return motionIndex(point.speed) !== motionIndex(noon.speed); });
    const uncertainAspect = config.partners.some(function (_partner, partnerIndex) {
      const angles = initial.map(function (point) { return wrap(point.tropicalLongitude - point.partners[partnerIndex]); });
      const possible = sampledAspectIndexes(angles, config.aspectOrbDegrees).indexes;
      const middle = aspectIndex(angularDistance(noon.tropicalLongitude, noon.partners[partnerIndex]), config.aspectOrbDegrees);
      return possible.length > 1 || possible.length === 1 && (middle < 0 || initial.some(function (point) {
        return aspectIndex(angularDistance(point.tropicalLongitude, point.partners[partnerIndex]), config.aspectOrbDegrees) !== middle;
      }));
    });
    // Refine civil-day crossings/stations rather than treating matching endpoints
    // as proof. These remain sampled bounds, not a formal ephemeris enclosure.
    if (config.samplingMode === "common_grid" || nearSignBoundary || nearStation || uncertainAspect) {
      for (let timestamp = lowTime + 6 * 3600000; timestamp < highTime; timestamp += 6 * 3600000) { sampleTimes.push(timestamp); get(timestamp); }
    }
    sampleTimes.sort(function (left, right) { return left - right; });
    const points = sampleTimes.map(get);
    const unwrapped = points.map(function (point) { return noon.longitude + signedDifference(point.longitude, noon.longitude); });
    const signIndexes = circularBins(Math.min.apply(null, unwrapped) - SAMPLE_MARGIN_DEGREES, Math.max.apply(null, unwrapped) + SAMPLE_MARGIN_DEGREES, 30, 12);
    const minRate = Math.min.apply(null, points.map(function (point) { return point.speed; })) - RATE_MARGIN_DEGREES_PER_DAY;
    const maxRate = Math.max.apply(null, points.map(function (point) { return point.speed; })) + RATE_MARGIN_DEGREES_PER_DAY;
    const motionIndexes = [];
    if (maxRate > STATIONARY_THRESHOLD) motionIndexes.push(0);
    if (minRate < -STATIONARY_THRESHOLD) motionIndexes.push(1);
    if (minRate <= STATIONARY_THRESHOLD && maxRate >= -STATIONARY_THRESHOLD) motionIndexes.push(2);
    const aspectPartners = config.partners.map(function (partner, partnerIndex) {
      const angles = points.map(function (point) { return wrap(point.tropicalLongitude - point.partners[partnerIndex]); });
      const interval = sampledAspectIndexes(angles, config.aspectOrbDegrees);
      const separation = angularDistance(noon.tropicalLongitude, noon.partners[partnerIndex]);
      const middle = aspectIndex(separation, config.aspectOrbDegrees);
      const stableAspectIndexes = interval.indexes.filter(function (index) {
        return points.every(function (point) { return Math.abs(angularDistance(point.tropicalLongitude, point.partners[partnerIndex]) - ASPECTS[index].angleDegrees) <= config.aspectOrbDegrees - SAMPLE_MARGIN_DEGREES; });
      });
      return { partner, separationDegrees: round(separation), aspectIndex: middle, possibleAspectIndexes: interval.indexes, stableAspectIndexes };
    });
    const result = Object.freeze({ ordinal: day, planet: config.planet, longitudeDegrees: round(noon.longitude), tropicalLongitudeDegrees: round(noon.tropicalLongitude),
      ayanamsaDegrees: round(config.zodiacSystem === "sidereal" ? config.ayanamsaDegreesAtUtc(noonTime, config.ayanamsaId) : 0),
      signIndex: Math.floor(noon.longitude / 30), signId: SIGNS[Math.floor(noon.longitude / 30)].id, possibleSignIndexes: signIndexes,
      stableSign: signIndexes.length === 1, motionIndex: motionIndex(noon.speed), motionId: MOTIONS[motionIndex(noon.speed)].id,
      longitudeRateDegreesPerDay: round(noon.speed), rateRangeDegreesPerDay: [round(minRate), round(maxRate)],
      possibleMotionIndexes: motionIndexes, stableMotion: motionIndexes.length === 1, aspectPartners,
      utcIntervalMs: [lowTime, highTime], sampleCount: points.length, samplingMode: config.samplingMode, boundsStatus: "sampled_utc_interval_not_formal_enclosure" });
    if (config.cacheable) {
      if (dayCache.size >= MAX_CACHE_DAYS) dayCache.delete(dayCache.keys().next().value);
      dayCache.set(key, result);
      if (noonCache.size >= MAX_CACHE_DAYS) noonCache.delete(noonCache.keys().next().value);
      noonCache.set(key, { signIndex: result.signIndex, motionIndex: result.motionIndex, aspects: aspectPartners.map(function (partner) { return partner.aspectIndex; }) });
    }
    return result;
  }
  function noonForDay(day, config) {
    const key = config.cacheKey + "|" + day;
    if (config.cacheable && noonCache.has(key)) return noonCache.get(key);
    const timestamp = (day + 0.5) * DAY_MS;
    const position = positionAtUtc(config.planet, timestamp, config);
    const aspectLongitude = config.samplingMode === "common_grid" ? rawLongitude(config.planet, timestamp) : position.tropicalLongitudeDegrees;
    const aspects = config.partners.map(function (partner) { return aspectIndex(angularDistance(aspectLongitude, rawLongitude(partner, timestamp)), config.aspectOrbDegrees); });
    const result = { signIndex: position.signIndex, motionIndex: position.motionIndex, aspects };
    if (config.cacheable) {
      if (noonCache.size >= MAX_CACHE_DAYS) noonCache.delete(noonCache.keys().next().value);
      noonCache.set(key, result);
    }
    return result;
  }
  function verifiedUtc(row) {
    const value = first(row.utcTimestamp, row.utc_timestamp, row.observationUtc);
    if (row.utcTimestampVerified !== true && row.utc_timestamp_verified !== true) return null;
    if (!text(first(row.timeZoneProvenance, row.timezoneProvenance, row.utcTimestampProvenance), "").replace(/^unknown$/, "")) return null;
    if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})$/.test(value)) return null;
    const timestamp = Date.parse(value);
    if (!Number.isFinite(timestamp)) return null;
    const offsetMatch = /([+-])(\d{2}):(\d{2})$/.exec(value);
    const minutes = offsetMatch ? (offsetMatch[1] === "+" ? 1 : -1) * ((Number(offsetMatch[2]) * 60) + Number(offsetMatch[3])) : 0;
    if (Math.abs(minutes) > 14 * 60 || new Date(timestamp + minutes * 60000).toISOString().slice(0, 10) !== value.slice(0, 10)) return null;
    return timestamp;
  }
  function bins(descriptors) { return descriptors.map(function (entry) { return Object.assign({}, entry, { count: 0, stableCount: 0, possibleCount: 0 }); }); }
  function blankDomain(id, label, role, categoryLabel, config) {
    return { id, label, dateRoleDefault: role, categoryLabel, total: 0, reportCount: 0, nonReportContextCount: 0, positionEligible: 0,
      stableSignCount: 0, ambiguousSignCount: 0, verifiedTimeCount: 0, outsideRange: 0, excluded: {}, dateRoles: {}, sourceCounts: {},
      signBins: bins(SIGNS), signByCategory: [], aspectByCategory: [], motion: { stableCount: 0, ambiguousCount: 0, bins: bins(MOTIONS) },
      aspectPartners: config.partners.map(function (partner) { return { partner, label: config.planet + " ↔ " + partner, eligible: 0, anyAspectCount: 0, bins: bins(ASPECTS), _outsideLower: 0, _outsideUpper: 0 }; }),
      houses: { eligible: 0, eligibleInputs: 0, status: "unavailable_verified_time_and_location_required", calculated: false },
      sky: { eligible: 0, status: "not_calculated_verified_time_and_location_required" },
      _months: new Map(), _categories: new Map(), _dates: new Set(), _config: config };
  }
  function addRecord(domain, rowValue, range, epoch) {
    const row = rowValue || {};
    const weight = row._aggregateN || 1;
    const preparedGroup = row._preparedGroup === true;
    const start = preparedGroup ? row.startOrdinal : ordinal(first(row.startOrdinal, row.dateStartOrdinal, row.start_ordinal, row.sortOrdinal), epoch);
    if (!preparedGroup) {
      const end = ordinal(first(row.endOrdinal, row.dateEndOrdinal, row.end_ordinal, row.startOrdinal, row.dateStartOrdinal, row.sortOrdinal), epoch);
      if (range && start != null && end != null && (end < range.start || start > range.end)) { domain.outsideRange += weight; return; }
      domain.total += weight;
      if (domain.id === "ufo" && (row.isUfoReport === false || row.isContext === true || text(first(row.craftType, row.category)).toLowerCase() === "non_ufo_context" ||
          NON_REPORT_TYPES.has(text(row.type).toLowerCase()) || NON_REPORT_GROUPS.has(text(first(row.visualTypeGroup, row.visual_type_group)).toLowerCase()))) {
        domain.nonReportContextCount += weight; increment(domain.excluded, "non_ufo_context", weight); return;
      }
      domain.reportCount += weight;
      increment(domain.dateRoles, text(first(row.dateRole, row.date_role), domain.dateRoleDefault), weight);
      increment(domain.sourceCounts, text(first(row.source, row.sourceFamily, Array.isArray(row.sourceFamilyIds) ? row.sourceFamilyIds.join("; ") : null)), weight);
      let reason = null;
      if (start == null || end == null || end < start) reason = "missing_or_invalid_date";
      else if (text(first(row.datePrecision, row.date_precision)) !== "exact_day" || start !== end) reason = "date_not_exact_day";
      else if (start < MINIMUM_DATE) reason = "historical_calendar_not_verified_before_1582";
      else if (start > MAXIMUM_DATE) reason = "outside_supported_calendar";
      if (reason) { increment(domain.excluded, reason, weight); return; }
    }
    const config = domain._config;
    const daily = positionForDay(start, config);
    let signIndex = daily.signIndex, signIndexes = daily.possibleSignIndexes, stableSign = daily.stableSign;
    let motion = daily.motionIndex, motionIndexes = daily.possibleMotionIndexes, stableMotion = daily.stableMotion;
    let aspectPartners = daily.aspectPartners;
    const utc = preparedGroup ? row._preparedUtc : verifiedUtc(row);
    if (utc != null && utc >= daily.utcIntervalMs[0] && utc <= daily.utcIntervalMs[1]) {
      const exact = positionAtUtc(config.planet, utc, config);
      signIndex = exact.signIndex; signIndexes = [exact.signIndex]; stableSign = true;
      motion = exact.motionIndex; motionIndexes = [motion]; stableMotion = true;
      aspectPartners = config.partners.map(function (partner) {
        const longitude = config.samplingMode === "common_grid" ? rawLongitude(config.planet, utc) : exact.tropicalLongitudeDegrees;
        const index = aspectIndex(angularDistance(longitude, rawLongitude(partner, utc)), config.aspectOrbDegrees);
        return { partner, aspectIndex: index, possibleAspectIndexes: index < 0 ? [] : [index], stableAspectIndexes: index < 0 ? [] : [index] };
      });
      domain.verifiedTimeCount += weight;
      if (row._houseInputEligible === true || finite(row.lat) != null && finite(row.lon) != null && Math.abs(Number(row.lat)) <= 90 && Math.abs(Number(row.lon)) <= 180 &&
          new Set(["source_coordinates", "source_provided", "source-provided", "source_exact", "exact"]).has(text(first(row.coordinateEvidenceClass, row.coordinateSource)))) domain.houses.eligibleInputs += weight;
    }
    domain.positionEligible += weight;
    domain._dates.add(start);
    domain[stableSign ? "stableSignCount" : "ambiguousSignCount"] += weight;
    domain.signBins[signIndex].count += weight;
    if (stableSign) domain.signBins[signIndex].stableCount += weight;
    signIndexes.forEach(function (index) { domain.signBins[index].possibleCount += weight; });
    domain.motion[stableMotion ? "stableCount" : "ambiguousCount"] += weight;
    domain.motion.bins[motion].count += weight;
    if (stableMotion) domain.motion.bins[motion].stableCount += weight;
    motionIndexes.forEach(function (index) { domain.motion.bins[index].possibleCount += weight; });
    aspectPartners.forEach(function (entry, partnerIndex) {
      const group = domain.aspectPartners[partnerIndex]; group.eligible += weight;
      if (entry.aspectIndex >= 0) { group.bins[entry.aspectIndex].count += weight; group.anyAspectCount += weight; }
      entry.stableAspectIndexes.forEach(function (index) { group.bins[index].stableCount += weight; });
      entry.possibleAspectIndexes.forEach(function (index) { group.bins[index].possibleCount += weight; });
      if (!entry.possibleAspectIndexes.length) group._outsideLower += weight;
      if (!entry.stableAspectIndexes.length) group._outsideUpper += weight;
    });
    const date = new Date(start * DAY_MS);
    const monthKey = date.getUTCFullYear() + "-" + String(date.getUTCMonth() + 1).padStart(2, "0");
    domain._months.set(monthKey, (domain._months.get(monthKey) || 0) + weight);
    const category = preparedGroup ? row.category : text(first(row.craftType, row.category, row.crop, Array.isArray(row.species) ? row.species.join(", ") : row.species));
    if (!domain._categories.has(category)) domain._categories.set(category, { category, total: 0, stableCount: 0, counts: new Array(12).fill(0),
      aspectCounts: domain.aspectPartners.map(function () { return new Array(5).fill(0); }), months: new Map() });
    const matrix = domain._categories.get(category);
    matrix.total += weight; matrix.counts[signIndex] += weight; if (stableSign) matrix.stableCount += weight;
    aspectPartners.forEach(function (entry, index) { if (entry.aspectIndex >= 0) matrix.aspectCounts[index][entry.aspectIndex] += weight; });
    matrix.months.set(monthKey, (matrix.months.get(monthKey) || 0) + weight);
  }
  function exposureMonth(monthKey, range, config) {
    const key = config.cacheKey + "|" + monthKey + "|" + (range ? range.start + ":" + range.end : "full");
    if (config.cacheable && monthCache.has(key)) return monthCache.get(key);
    const parts = monthKey.split("-").map(Number);
    let start = Math.floor(Date.UTC(parts[0], parts[1] - 1, 1) / DAY_MS);
    let end = Math.floor(Date.UTC(parts[0], parts[1], 1) / DAY_MS) - 1;
    if (range) { start = Math.max(start, range.start); end = Math.min(end, range.end); }
    const result = { days: 0, signs: new Array(12).fill(0), motions: new Array(3).fill(0), aspects: config.partners.map(function () { return new Array(5).fill(0); }) };
    for (let day = start; day <= end; day += 1) {
      if (day < MINIMUM_DATE || day > MAXIMUM_DATE) continue;
      const snapshot = noonForDay(day, config);
      result.days += 1; result.signs[snapshot.signIndex] += 1; result.motions[snapshot.motionIndex] += 1;
      snapshot.aspects.forEach(function (index, partnerIndex) { if (index >= 0) result.aspects[partnerIndex][index] += 1; });
    }
    if (config.cacheable) {
      if (monthCache.size >= 10000) monthCache.delete(monthCache.keys().next().value);
      monthCache.set(key, result);
    }
    return result;
  }
  function finalizedBins(output, expected, denominator) {
    output.forEach(function (bin, index) {
      bin.share = denominator ? round(bin.count / denominator) : null;
      bin.expectedCount = round(expected[index], 4);
      bin.expectedCalendarShare = denominator ? round(expected[index] / denominator) : null;
      bin.calendarAdjustedRatio = expected[index] > 0 ? round(bin.count / expected[index], 4) : null;
      bin.lowerCount = bin.stableCount; bin.upperCount = bin.possibleCount;
      bin.boundStatus = "sampled_stability_not_formal_confidence_interval";
    });
  }
  function finalizeDomain(domain, range, categoryLimit) {
    const signExpected = new Array(12).fill(0), motionExpected = new Array(3).fill(0);
    const aspectExpected = domain.aspectPartners.map(function () { return new Array(5).fill(0); });
    let calendarDays = 0, variableSignMonths = 0, variableSignReports = 0, variableMotionMonths = 0, variableMotionReports = 0;
    const aspectVariation = domain.aspectPartners.map(function () { return { variableMonths: 0, variableReports: 0 }; });
    domain._months.forEach(function (weight, monthKey) {
      const exposure = exposureMonth(monthKey, range, domain._config); calendarDays += exposure.days;
      if (!exposure.days) return;
      exposure.signs.forEach(function (count, index) { signExpected[index] += weight * count / exposure.days; });
      exposure.motions.forEach(function (count, index) { motionExpected[index] += weight * count / exposure.days; });
      exposure.aspects.forEach(function (counts, partnerIndex) { counts.forEach(function (count, index) { aspectExpected[partnerIndex][index] += weight * count / exposure.days; }); });
      if (exposure.signs.filter(function (count) { return count > 0; }).length > 1) { variableSignMonths += 1; variableSignReports += weight; }
      if (exposure.motions.filter(function (count) { return count > 0; }).length > 1) { variableMotionMonths += 1; variableMotionReports += weight; }
      exposure.aspects.forEach(function (counts, index) {
        const outside = exposure.days - counts.reduce(function (sum, count) { return sum + count; }, 0);
        if (counts.concat([outside]).filter(function (count) { return count > 0; }).length > 1) {
          aspectVariation[index].variableMonths += 1; aspectVariation[index].variableReports += weight;
        }
      });
    });
    finalizedBins(domain.signBins, signExpected, domain.positionEligible);
    finalizedBins(domain.motion.bins, motionExpected, domain.positionEligible);
    domain.aspectPartners.forEach(function (partner, index) {
      finalizedBins(partner.bins, aspectExpected[index], domain.positionEligible);
      const outside = partner.eligible - partner.anyAspectCount;
      const expected = Math.max(0, partner.eligible - aspectExpected[index].reduce(function (sum, count) { return sum + count; }, 0));
      partner.outsideBand = { id: "outside", label: "Outside these bands", count: outside, share: partner.eligible ? round(outside / partner.eligible) : null,
        expectedCount: round(expected, 4), expectedCalendarShare: partner.eligible ? round(expected / partner.eligible) : null,
        calendarAdjustedRatio: expected > 0 ? round(outside / expected, 4) : null,
        lowerCount: domain._config.samplingMode === "common_grid" ? partner._outsideLower : Math.max(0, partner.eligible - partner.bins.reduce(function (sum, bin) { return sum + bin.possibleCount; }, 0)),
        upperCount: domain._config.samplingMode === "common_grid" ? partner._outsideUpper : partner.eligible - partner.bins.reduce(function (sum, bin) { return sum + bin.stableCount; }, 0),
        boundStatus: "sampled_stability_not_formal_confidence_interval" };
      partner.variableAspectMonths = aspectVariation[index].variableMonths;
      partner.variableAspectReports = aspectVariation[index].variableReports;
      delete partner._outsideLower; delete partner._outsideUpper;
    });
    const categories = Array.from(domain._categories.values()).sort(function (left, right) { return right.total - left.total || left.category.localeCompare(right.category); }).slice(0, categoryLimit);
    domain.signByCategory = categories.map(function (entry) {
      const expected = new Array(12).fill(0);
      entry.months.forEach(function (weight, monthKey) {
        const exposure = exposureMonth(monthKey, range, domain._config);
        if (exposure.days) exposure.signs.forEach(function (count, index) { expected[index] += weight * count / exposure.days; });
      });
      return { category: entry.category, total: entry.total, stableCount: entry.stableCount, bins: SIGNS.map(function (sign, index) {
        return { id: sign.id, label: sign.label, count: entry.counts[index], share: round(entry.counts[index] / entry.total), expectedCount: round(expected[index], 4),
          expectedCalendarShare: round(expected[index] / entry.total), calendarAdjustedRatio: expected[index] > 0 ? round(entry.counts[index] / expected[index], 4) : null };
      }) };
    });
    domain.aspectByCategory = domain.aspectPartners.map(function (partner, partnerIndex) {
      return { partner: partner.partner, label: partner.label, rows: categories.map(function (entry) {
        const expected = new Array(5).fill(0);
        entry.months.forEach(function (weight, monthKey) {
          const exposure = exposureMonth(monthKey, range, domain._config);
          if (exposure.days) exposure.aspects[partnerIndex].forEach(function (count, index) { expected[index] += weight * count / exposure.days; });
        });
        const categoryBins = ASPECTS.map(function (aspect, index) { return { id: aspect.id, label: aspect.label, count: entry.aspectCounts[partnerIndex][index],
          share: round(entry.aspectCounts[partnerIndex][index] / entry.total), expectedCount: round(expected[index], 4), expectedCalendarShare: round(expected[index] / entry.total),
          calendarAdjustedRatio: expected[index] > 0 ? round(entry.aspectCounts[partnerIndex][index] / expected[index], 4) : null }; });
        const outside = entry.total - entry.aspectCounts[partnerIndex].reduce(function (sum, count) { return sum + count; }, 0);
        const outsideExpected = Math.max(0, entry.total - expected.reduce(function (sum, count) { return sum + count; }, 0));
        return { category: entry.category, total: entry.total, bins: categoryBins, outsideBand: { id: "outside", label: "Outside these bands", count: outside,
          share: round(outside / entry.total), expectedCount: round(outsideExpected, 4), expectedCalendarShare: round(outsideExpected / entry.total),
          calendarAdjustedRatio: outsideExpected > 0 ? round(outside / outsideExpected, 4) : null } };
      }) };
    });
    domain.distinctEligibleDates = domain._dates.size;
    domain.exposure = { method: "year_month_matched_calendar_days", representedMonths: domain._months.size, calendarDays,
      variableSignMonths, variableSignReports, variableMotionMonths, variableMotionReports,
      weighting: "Actual noon ephemeris states on selected calendar days, weighted by each domain's eligible report count in each year-month. Category matrices use each category's own year-month weights. This also retains source-by-month count weights because every source has the same calendar candidate days; it does not estimate source-specific observing effort.",
      opportunity: "Calendar opportunity only; observing effort, source completeness and reporting selection are not measured.",
      slowPlanetCaution: "Months without any sign or motion change cannot distinguish a within-month association from the report's era or season." };
    domain.status = domain.positionEligible ? "descriptive" : "unavailable_exact_dates_required";
    if (domain.houses.eligibleInputs) domain.houses.status = "not_implemented_verified_inputs_present";
    delete domain._months; delete domain._categories; delete domain._dates; delete domain._config;
    return domain;
  }
  function preparePlanetaryCohort(optionsValue) {
    const options = optionsValue || {};
    const epoch = validateEpoch(options.ordinalEpoch), contextEpoch = validateEpoch(options.contextOrdinalEpoch || epoch);
    const range = rangeValue(options, epoch);
    const roles = ["occurrence", "catalog_or_discovery_date_not_verified_formation", "reported_or_discovery_date_not_verified_occurrence"];
    const domains = ["ufo", "crops", "animals"].map(function (id, index) {
      return { id, summary: { total: 0, reportCount: 0, nonReportContextCount: 0, outsideRange: 0, excluded: {}, dateRoles: {}, sourceCounts: {} }, groups: new Map(), defaultRole: roles[index] };
    });
    function accept(domain, rowValue, inputEpoch) {
      const row = rowValue || {}, summary = domain.summary;
      const start = ordinal(first(row.startOrdinal, row.dateStartOrdinal, row.start_ordinal, row.sortOrdinal), inputEpoch);
      const end = ordinal(first(row.endOrdinal, row.dateEndOrdinal, row.end_ordinal, row.startOrdinal, row.dateStartOrdinal, row.sortOrdinal), inputEpoch);
      if (range && start != null && end != null && (end < range.start || start > range.end)) { summary.outsideRange += 1; return; }
      summary.total += 1;
      if (domain.id === "ufo" && (row.isUfoReport === false || row.isContext === true || text(first(row.craftType, row.category)).toLowerCase() === "non_ufo_context" ||
          NON_REPORT_TYPES.has(text(row.type).toLowerCase()) || NON_REPORT_GROUPS.has(text(first(row.visualTypeGroup, row.visual_type_group)).toLowerCase()))) {
        summary.nonReportContextCount += 1; increment(summary.excluded, "non_ufo_context"); return;
      }
      summary.reportCount += 1;
      increment(summary.dateRoles, text(first(row.dateRole, row.date_role), domain.defaultRole));
      increment(summary.sourceCounts, text(first(row.source, row.sourceFamily, Array.isArray(row.sourceFamilyIds) ? row.sourceFamilyIds.join("; ") : null)));
      let reason = null;
      if (start == null || end == null || end < start) reason = "missing_or_invalid_date";
      else if (text(first(row.datePrecision, row.date_precision)) !== "exact_day" || start !== end) reason = "date_not_exact_day";
      else if (start < MINIMUM_DATE) reason = "historical_calendar_not_verified_before_1582";
      else if (start > MAXIMUM_DATE) reason = "outside_supported_calendar";
      if (reason) { increment(summary.excluded, reason); return; }
      const candidateUtc = verifiedUtc(row);
      const utc = candidateUtc != null && candidateUtc >= start * DAY_MS - 14 * 3600000 && candidateUtc <= start * DAY_MS + 36 * 3600000 ? candidateUtc : null;
      const house = utc != null && finite(row.lat) != null && finite(row.lon) != null && Math.abs(Number(row.lat)) <= 90 && Math.abs(Number(row.lon)) <= 180 &&
        new Set(["source_coordinates", "source_provided", "source-provided", "source_exact", "exact"]).has(text(first(row.coordinateEvidenceClass, row.coordinateSource)));
      const category = text(first(row.craftType, row.category, row.crop, Array.isArray(row.species) ? row.species.join(", ") : row.species));
      const key = JSON.stringify([start, category, utc, house]);
      if (!domain.groups.has(key)) domain.groups.set(key, { _preparedGroup: true, startOrdinal: start, endOrdinal: start, datePrecision: "exact_day", category,
        _preparedUtc: utc, _houseInputEligible: house, _aggregateN: 0 });
      domain.groups.get(key)._aggregateN += 1;
    }
    if (typeof options.forEachRow === "function") options.forEachRow(function (row) { accept(domains[0], row, epoch); });
    else (Array.isArray(options.rows) ? options.rows : []).forEach(function (row) { accept(domains[0], row, epoch); });
    (Array.isArray(options.crops) ? options.crops : []).forEach(function (row) { accept(domains[1], row, contextEpoch); });
    (Array.isArray(options.animals) ? options.animals : []).forEach(function (row) { accept(domains[2], row, contextEpoch); });
    const output = domains.map(function (domain) { return { id: domain.id, summary: domain.summary, groups: Array.from(domain.groups.values()) }; });
    return { schemaId: "ufo-planetary-prepared-cohort-v1", ordinalEpoch: "unix_day", range, domains: output,
      inputRows: output.reduce(function (sum, domain) { return sum + domain.summary.total + domain.summary.outsideRange; }, 0),
      foldedGroupN: output.reduce(function (sum, domain) { return sum + domain.groups.length; }, 0) };
  }
  function decodeEphemerisAtlas(input, manifestValue) {
    const manifest = manifestValue || {};
    if (manifest.schemaId !== ATLAS_SCHEMA || manifest.ordinalEpoch !== "unix_day") throw new Error("Planetary atlas schema/epoch mismatch.");
    if (manifest.byteOrder !== "little_endian" || manifest.longitudeFormat !== "float64" || manifest.rateFormat !== "float32" || manifest.precessionFormat !== "float64" ||
        manifest.algorithmVersion !== VERSION || manifest.ephemerisSha256 !== "d1b3ab4b86aa409f78c0f0d95162a847496cba7e938eb6f4712cf9c1c45f4a2e" ||
        JSON.stringify(manifest.quantityOrder) !== JSON.stringify(["longitudeDegrees", "longitudeRateDegreesPerDay", "sharedPrecessionDegrees"])) throw new Error("Planetary atlas numeric format/ephemeris identity mismatch.");
    if (new Uint8Array(new Uint32Array([0x01020304]).buffer)[0] !== 4) throw new Error("Planetary atlas requires a little-endian runtime.");
    if (JSON.stringify(manifest.bodies) !== JSON.stringify(PLANETS) || JSON.stringify(manifest.utcHours) !== JSON.stringify(ATLAS_HOURS)) throw new Error("Planetary atlas body/hour order mismatch.");
    let bytes;
    if (ArrayBuffer.isView(input)) bytes = new Uint8Array(input.buffer, input.byteOffset, input.byteLength);
    else bytes = new Uint8Array(input);
    if (bytes.byteLength < 64 || bytes.byteLength !== manifest.byteLength) throw new Error("Planetary atlas byte length mismatch.");
    if (bytes.byteOffset % 8) bytes = bytes.slice();
    const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    const magic = String.fromCharCode.apply(null, Array.from(bytes.subarray(0, ATLAS_MAGIC.length)));
    if (magic !== ATLAS_MAGIC || view.getUint32(16, true) !== 1 || view.getUint32(60, true) !== 1) throw new Error("Planetary atlas binary header mismatch.");
    const dayN = view.getUint32(20, true), bodyN = view.getUint32(24, true), hourN = view.getUint32(28, true);
    const indexOffset = view.getUint32(32, true), longitudeOffset = view.getUint32(36, true), rateOffset = view.getUint32(40, true), precessionOffset = view.getUint32(44, true);
    const total = view.getUint32(48, true), valueN = dayN * bodyN * hourN;
    const align8 = function (value) { return Math.ceil(value / 8) * 8; };
    if (!dayN || dayN !== manifest.dateCount || bodyN !== PLANETS.length || hourN !== ATLAS_HOURS.length || indexOffset !== 64 ||
        longitudeOffset !== align8(64 + dayN * 4) || rateOffset !== longitudeOffset + valueN * 8 || precessionOffset !== align8(rateOffset + valueN * 4) ||
        total !== precessionOffset + dayN * hourN * 8 || total !== bytes.byteLength) throw new Error("Planetary atlas dimensions/offsets mismatch.");
    const dates = new Int32Array(bytes.buffer, bytes.byteOffset + indexOffset, dayN);
    const longitudes = new Float64Array(bytes.buffer, bytes.byteOffset + longitudeOffset, valueN);
    const rates = new Float32Array(bytes.buffer, bytes.byteOffset + rateOffset, valueN);
    const precession = new Float64Array(bytes.buffer, bytes.byteOffset + precessionOffset, dayN * hourN);
    const dayIndex = new Map();
    for (let index = 0; index < dates.length; index += 1) {
      if (dates[index] < MINIMUM_DATE - 1 || dates[index] > MAXIMUM_DATE + 1 || index && dates[index] <= dates[index - 1]) throw new Error("Planetary atlas day index is invalid.");
      dayIndex.set(dates[index], index);
    }
    if (dates[0] !== view.getInt32(52, true) || dates[dates.length - 1] !== view.getInt32(56, true)) throw new Error("Planetary atlas date extent mismatch.");
    for (let index = 0; index < valueN; index += 1) if (!Number.isFinite(longitudes[index]) || longitudes[index] < 0 || longitudes[index] >= 360 || !Number.isFinite(rates[index]) || Math.abs(rates[index]) > 30) throw new Error("Planetary atlas physical value is invalid.");
    for (const value of precession) if (!Number.isFinite(value) || Math.abs(value) > 20) throw new Error("Planetary atlas precession value is invalid.");
    const bodyIndex = new Map(PLANETS.map(function (body, index) { return [body, index]; }));
    function locate(timestamp) {
      const day = Math.floor(timestamp / DAY_MS), hour = (timestamp - day * DAY_MS) / 3600000;
      const slot = ATLAS_HOURS.indexOf(hour), index = dayIndex.get(day);
      return slot < 0 || index == null ? null : index * hourN + slot;
    }
    return Object.freeze({ schemaId: ATLAS_SCHEMA, manifest: Object.assign({}, manifest), dates, longitudes, rates, precession, locate,
      valueIndex: function (body, timestamp) { const position = locate(timestamp), bodyNumber = bodyIndex.get(body); return position == null || bodyNumber == null ? null : Math.floor(position / hourN) * bodyN * hourN + bodyNumber * hourN + position % hourN; } });
  }
  function setEphemerisAtlas(atlas) {
    if (!atlas || atlas.schemaId !== ATLAS_SCHEMA || typeof atlas.valueIndex !== "function" || !atlas.longitudes) throw new Error("A decoded planetary atlas is required.");
    ephemerisAtlas = atlas; clearCaches();
  }
  function clearEphemerisAtlas() { ephemerisAtlas = null; clearCaches(); }
  function buildEphemerisAtlasBuffer(daysValue, optionsValue) {
    const options = optionsValue || {}, dates = Array.from(new Set(daysValue)).sort(function (left, right) { return left - right; });
    if (!dates.length || dates.some(function (day) { return !Number.isInteger(day) || day < MINIMUM_DATE - 1 || day > MAXIMUM_DATE + 1; })) throw new Error("Atlas builder dates are invalid.");
    const dayN = dates.length, bodyN = PLANETS.length, hourN = ATLAS_HOURS.length, valueN = dayN * bodyN * hourN;
    const longitudeOffset = Math.ceil((64 + dayN * 4) / 8) * 8, rateOffset = longitudeOffset + valueN * 8;
    const precessionOffset = Math.ceil((rateOffset + valueN * 4) / 8) * 8, byteLength = precessionOffset + dayN * hourN * 8;
    const buffer = new ArrayBuffer(byteLength), bytes = new Uint8Array(buffer), view = new DataView(buffer);
    Array.from(ATLAS_MAGIC).forEach(function (character, index) { bytes[index] = character.charCodeAt(0); });
    [1, dayN, bodyN, hourN, 64, longitudeOffset, rateOffset, precessionOffset, byteLength].forEach(function (value, index) { view.setUint32(16 + index * 4, value, true); });
    view.setInt32(52, dates[0], true); view.setInt32(56, dates[dates.length - 1], true); view.setUint32(60, 1, true);
    const indexArray = new Int32Array(buffer, 64, dayN), longitudes = new Float64Array(buffer, longitudeOffset, valueN), rates = new Float32Array(buffer, rateOffset, valueN), precession = new Float64Array(buffer, precessionOffset, dayN * hourN);
    const rawCache = PLANETS.map(function () { return new Map(); });
    function direct(bodyIndex, timestamp) {
      const cache = rawCache[bodyIndex];
      if (!cache.has(timestamp)) {
        cache.set(timestamp, Astronomy.Ecliptic(Astronomy.GeoVector(Astronomy.Body[PLANETS[bodyIndex]], new Date(timestamp), true)).elon);
        if (cache.size > 100) cache.delete(cache.keys().next().value);
      }
      return cache.get(timestamp);
    }
    dates.forEach(function (day, dayIndex) {
      indexArray[dayIndex] = day;
      ATLAS_HOURS.forEach(function (hour, slot) {
        const timestamp = day * DAY_MS + hour * 3600000;
        const time = Astronomy.MakeTime(new Date(timestamp));
        const axis = Astronomy.RotateVector(Astronomy.Rotation_ECL_EQJ(), new Astronomy.Vector(1, 0, 0, time));
        const angle = Astronomy.Ecliptic(axis).elon;
        precession[dayIndex * hourN + slot] = angle > 180 ? angle - 360 : angle;
        PLANETS.forEach(function (_body, bodyIndex) {
          const index = (dayIndex * bodyN + bodyIndex) * hourN + slot;
          longitudes[index] = direct(bodyIndex, timestamp);
          rates[index] = signedDifference(direct(bodyIndex, timestamp + 0.125 * DAY_MS), direct(bodyIndex, timestamp - 0.125 * DAY_MS)) / 0.25;
        });
      });
      if (options.onProgress && (dayIndex + 1) % 5000 === 0) options.onProgress({ completedDays: dayIndex + 1, totalDays: dayN });
    });
    return { buffer, metadata: { schemaId: ATLAS_SCHEMA, ordinalEpoch: "unix_day", dateCount: dayN, byteLength, bodies: PLANETS.slice(), utcHours: ATLAS_HOURS.slice(),
      byteOrder: "little_endian", longitudeFormat: "float64", rateFormat: "float32", precessionFormat: "float64", quantityOrder: ["longitudeDegrees", "longitudeRateDegreesPerDay", "sharedPrecessionDegrees"],
      timeScale: "UTC, Astronomy Engine internally converts to terrestrial time", frame: "apparent geocentric true ecliptic and equinox of date, light-time and annual aberration included",
      rateConvention: "Centered six-hour difference of apparent tropical longitude, degrees per day", algorithmVersion: VERSION,
      ephemerisSha256: "d1b3ab4b86aa409f78c0f0d95162a847496cba7e938eb6f4712cf9c1c45f4a2e", minimumOrdinal: dates[0], maximumOrdinal: dates[dates.length - 1] } };
  }
  const HEATMAP_PAIRS = Object.freeze(PLANETS.flatMap(function (planet, left) {
    return PLANETS.slice(left + 1).map(function (partner, offset) { return Object.freeze({ id: planet.toLowerCase() + "__" + partner.toLowerCase(), planet, partner, left, right: left + offset + 1, label: planet + " ↔ " + partner }); });
  }));
  const HEATMAP_ASPECT_COLUMNS = Object.freeze(ASPECTS.concat([Object.freeze({ id: "outside", label: "Outside these bands" })]));
  const HEATMAP_ROWS = PLANETS.map(function (planet, body) { return { id: planet.toLowerCase(), planet, label: planet, kind: "zodiac", body, columns: SIGNS }; })
    .concat(PLANETS.map(function (planet, body) { return { id: planet.toLowerCase(), planet, label: planet, kind: "motion", body, columns: MOTIONS }; }))
    .concat(HEATMAP_PAIRS.map(function (pair) { return Object.assign({ kind: "aspects", columns: HEATMAP_ASPECT_COLUMNS }, pair); }));
  let heatmapCellN = 0;
  HEATMAP_ROWS.forEach(function (row) { row.offset = heatmapCellN; heatmapCellN += row.columns.length; });
  const COMMON_GRID_HOURS = Object.freeze([-14, -8, -2, 4, 10, 12, 16, 22, 28, 34, 36]);
  function heatmapKey(config) { return config.zodiacSystem + "|" + config.ayanamsaId + "|" + config.aspectOrbDegrees; }
  function heatmapState(day, config, timestampValue, noonOnly) {
    const key = heatmapKey(config) + "|" + (noonOnly ? "noon|" : "full|") + day;
    if (timestampValue == null && config.cacheable && heatmapDayCache.has(key)) return heatmapDayCache.get(key);
    const times = timestampValue != null ? [timestampValue] : noonOnly ? [day * DAY_MS + 12 * 3600000] : COMMON_GRID_HOURS.map(function (hour) { return day * DAY_MS + hour * 3600000; });
    const noonIndex = times.length === 1 ? 0 : 5;
    const pointN = times.length, longitudes = new Float64Array(PLANETS.length * pointN), speeds = new Float64Array(PLANETS.length * pointN);
    const offsets = times.map(function (timestamp) {
      const offset = config.zodiacSystem === "sidereal" ? config.ayanamsaDegreesAtUtc(timestamp, config.ayanamsaId) : 0;
      if (!Number.isFinite(offset)) throw new Error("Ayanamsa helper returned an invalid offset.");
      return offset;
    });
    const state = { mid: new Uint8Array(HEATMAP_ROWS.length), lower: new Uint16Array(HEATMAP_ROWS.length), upper: new Uint16Array(HEATMAP_ROWS.length),
      monthKey: (function () { const date = new Date(day * DAY_MS); return date.getUTCFullYear() + "-" + String(date.getUTCMonth() + 1).padStart(2, "0"); })() };
    PLANETS.forEach(function (planet, body) {
      let minSign = Infinity, maxSign = -Infinity, minRate = Infinity, maxRate = -Infinity;
      times.forEach(function (timestamp, point) {
        const index = body * pointN + point;
        longitudes[index] = rawLongitude(planet, timestamp); speeds[index] = longitudeRateAtUtc(planet, timestamp);
      });
      const longitude = wrap(longitudes[body * pointN + noonIndex] - offsets[noonIndex]);
      for (let point = 0; point < pointN; point += 1) {
        const index = body * pointN + point, angle = longitude + signedDifference(wrap(longitudes[index] - offsets[point]), longitude);
        minSign = Math.min(minSign, angle); maxSign = Math.max(maxSign, angle); minRate = Math.min(minRate, speeds[index]); maxRate = Math.max(maxRate, speeds[index]);
      }
      const sign = Math.floor(longitude / 30), motion = motionIndex(speeds[body * pointN + noonIndex]);
      state.mid[body] = sign; state.mid[PLANETS.length + body] = motion;
      let signMask = 0, motionMask = 0;
      if (pointN === 1) { signMask = 1 << sign; motionMask = 1 << motion; }
      else {
        for (const index of circularBins(minSign - SAMPLE_MARGIN_DEGREES, maxSign + SAMPLE_MARGIN_DEGREES, 30, 12)) signMask |= 1 << index;
        minRate -= RATE_MARGIN_DEGREES_PER_DAY; maxRate += RATE_MARGIN_DEGREES_PER_DAY;
        if (maxRate > STATIONARY_THRESHOLD) motionMask |= 1;
        if (minRate < -STATIONARY_THRESHOLD) motionMask |= 2;
        if (minRate <= STATIONARY_THRESHOLD && maxRate >= -STATIONARY_THRESHOLD) motionMask |= 4;
      }
      state.upper[body] = signMask; state.lower[body] = signMask && !(signMask & (signMask - 1)) ? signMask : 0;
      state.upper[PLANETS.length + body] = motionMask; state.lower[PLANETS.length + body] = motionMask && !(motionMask & (motionMask - 1)) ? motionMask : 0;
    });
    HEATMAP_PAIRS.forEach(function (pair, pairIndex) {
      const row = 2 * PLANETS.length + pairIndex, angles = [];
      for (let point = 0; point < pointN; point += 1) angles.push(wrap(longitudes[pair.left * pointN + point] - longitudes[pair.right * pointN + point]));
      const middle = aspectIndex(angularDistance(longitudes[pair.left * pointN + noonIndex], longitudes[pair.right * pointN + noonIndex]), config.aspectOrbDegrees);
      state.mid[row] = middle < 0 ? 5 : middle;
      if (pointN === 1) { state.lower[row] = 1 << state.mid[row]; state.upper[row] = state.lower[row]; return; }
      const interval = sampledAspectIndexes(angles, config.aspectOrbDegrees);
      let stable = 0, possible = 0;
      interval.indexes.forEach(function (index) {
        possible |= 1 << index;
        if (angles.every(function (angle) { return Math.abs(angularDistance(angle, 0) - ASPECTS[index].angleDegrees) <= config.aspectOrbDegrees - SAMPLE_MARGIN_DEGREES; })) stable |= 1 << index;
      });
      const stableMajor = stable, possibleMajor = possible;
      if (!possibleMajor) stable |= 1 << 5;
      if (!stableMajor) possible |= 1 << 5;
      state.lower[row] = stable; state.upper[row] = possible;
    });
    if (timestampValue == null && config.cacheable) {
      if (heatmapDayCache.size >= MAX_CACHE_DAYS) heatmapDayCache.delete(heatmapDayCache.keys().next().value);
      heatmapDayCache.set(key, state);
    }
    return state;
  }
  function blankHeatmapAccumulator() {
    return { total: 0, count: new Float64Array(heatmapCellN), lower: new Float64Array(heatmapCellN), upper: new Float64Array(heatmapCellN),
      expected: new Float64Array(heatmapCellN), variableMonths: new Uint32Array(heatmapCellN), variableReports: new Float64Array(heatmapCellN),
      rowVariableMonths: new Uint32Array(HEATMAP_ROWS.length), rowVariableReports: new Float64Array(HEATMAP_ROWS.length), months: new Map() };
  }
  function addHeatmapState(accumulator, state, weight) {
    accumulator.total += weight;
    accumulator.months.set(state.monthKey, (accumulator.months.get(state.monthKey) || 0) + weight);
    for (let rowIndex = 0; rowIndex < HEATMAP_ROWS.length; rowIndex += 1) {
      const offset = HEATMAP_ROWS[rowIndex].offset;
      accumulator.count[offset + state.mid[rowIndex]] += weight;
      let lower = state.lower[rowIndex], upper = state.upper[rowIndex];
      while (lower) { accumulator.lower[offset + 31 - Math.clz32(lower & -lower)] += weight; lower &= lower - 1; }
      while (upper) { accumulator.upper[offset + 31 - Math.clz32(upper & -upper)] += weight; upper &= upper - 1; }
    }
  }
  function heatmapExposureMonth(monthKey, range, config) {
    const key = heatmapKey(config) + "|" + monthKey + "|" + (range ? range.start + ":" + range.end : "full");
    if (config.cacheable && heatmapMonthCache.has(key)) return heatmapMonthCache.get(key);
    const parts = monthKey.split("-").map(Number);
    let start = Math.max(MINIMUM_DATE, Math.floor(Date.UTC(parts[0], parts[1] - 1, 1) / DAY_MS));
    let end = Math.min(MAXIMUM_DATE, Math.floor(Date.UTC(parts[0], parts[1], 1) / DAY_MS) - 1);
    if (range) { start = Math.max(start, range.start); end = Math.min(end, range.end); }
    const counts = new Uint32Array(heatmapCellN);
    let days = 0;
    for (let day = start; day <= end; day += 1) {
      const state = heatmapState(day, config, null, true); days += 1;
      for (let row = 0; row < HEATMAP_ROWS.length; row += 1) counts[HEATMAP_ROWS[row].offset + state.mid[row]] += 1;
    }
    const result = { counts, days };
    if (config.cacheable) {
      if (heatmapMonthCache.size >= 5000) heatmapMonthCache.delete(heatmapMonthCache.keys().next().value);
      heatmapMonthCache.set(key, result);
    }
    return result;
  }
  function finishHeatmapAccumulator(accumulator, range, config) {
    let calendarDays = 0;
    accumulator.months.forEach(function (weight, monthKey) {
      const month = heatmapExposureMonth(monthKey, range, config); calendarDays += month.days;
      if (!month.days) return;
      for (let cell = 0; cell < heatmapCellN; cell += 1) {
        accumulator.expected[cell] += weight * month.counts[cell] / month.days;
        if (month.counts[cell] > 0 && month.counts[cell] < month.days) { accumulator.variableMonths[cell] += 1; accumulator.variableReports[cell] += weight; }
      }
      HEATMAP_ROWS.forEach(function (row, rowIndex) {
        if (row.columns.some(function (_column, index) { const count = month.counts[row.offset + index]; return count > 0 && count < month.days; })) {
          accumulator.rowVariableMonths[rowIndex] += 1; accumulator.rowVariableReports[rowIndex] += weight;
        }
      });
    });
    const matrices = { zodiac: { columns: SIGNS, rows: [] }, motion: { columns: MOTIONS, rows: [] }, aspects: { columns: HEATMAP_ASPECT_COLUMNS, rows: [] } };
    HEATMAP_ROWS.forEach(function (row, rowIndex) {
      const cells = row.columns.map(function (column, columnIndex) {
        const cell = row.offset + columnIndex, expected = accumulator.expected[cell], total = accumulator.total;
        return Object.assign({}, column, { count: accumulator.count[cell], lowerCount: accumulator.lower[cell], upperCount: accumulator.upper[cell],
          stableCount: accumulator.lower[cell], possibleCount: accumulator.upper[cell], share: total ? round(accumulator.count[cell] / total) : null,
          expectedCount: round(expected, 4), expectedCalendarShare: total ? round(expected / total) : null,
          calendarAdjustedRatio: expected > 0 ? round(accumulator.count[cell] / expected, 4) : null,
          variableOpportunityMonths: accumulator.variableMonths[cell], variableOpportunityReports: accumulator.variableReports[cell],
          status: !total ? "unavailable_exact_dates_required" : expected === 0 ? "no_calendar_opportunity" : !accumulator.variableReports[cell] ? "no_within_month_contrast" : "descriptive",
          boundStatus: "sampled_common_grid_not_formal_confidence_interval" });
      });
      matrices[row.kind].rows.push({ id: row.id, planet: row.planet, partner: row.partner || null, label: row.label, eligible: accumulator.total,
        cells, variableStateReports: accumulator.rowVariableReports[rowIndex], variableStateMonths: accumulator.rowVariableMonths[rowIndex] });
    });
    return { matrices, exposure: { method: "year_month_matched_calendar_days", representedMonths: accumulator.months.size, calendarDays,
      weighting: "Each report domain or category retains its own eligible report count weights by year-month; actual noon calendar states, clipped to the active date range, supply opportunity. Source-by-month weights are retained because candidate calendar days are shared; source-specific observing effort is unknown.",
      withinMonthContrast: "Each cell reports the eligible report weight in months where its calendar state is present on some but not all candidate days." } };
  }
  function computePlanetaryHeatmaps(optionsValue) {
    const options = optionsValue || {};
    const prepared = options.preparedCohort || preparePlanetaryCohort(options);
    if (prepared.schemaId !== "ufo-planetary-prepared-cohort-v1" || prepared.ordinalEpoch !== "unix_day") throw new Error("Invalid prepared planetary heatmap cohort.");
    const config = configuration(Object.assign({}, options, { planet: "Venus", aspectPartner: "Mars", samplingMode: "common_grid" }));
    const initialCounters = Object.assign({}, physicalCounters), range = prepared.range;
    const categoryLimit = Math.max(1, Math.min(50, Math.trunc(finite(options.categoryLimit) || 16)));
    const labels = ["UFO / craft reports", "Crop-circle reports", "Animal reports"], categoryLabels = ["Craft category", "Crop / morphology category", "Species category"];
    const domains = prepared.domains.map(function (input, domainIndex) {
      const accumulator = blankHeatmapAccumulator(), categories = new Map();
      if (options.includeCategoryMatrices === true) {
        const categoryWeights = new Map();
        input.groups.forEach(function (group) { categoryWeights.set(group.category, (categoryWeights.get(group.category) || 0) + group._aggregateN); });
        Array.from(categoryWeights).sort(function (left, right) { return right[1] - left[1] || left[0].localeCompare(right[0]); }).slice(0, categoryLimit).forEach(function (entry) { categories.set(entry[0], blankHeatmapAccumulator()); });
      }
      let verifiedTimeCount = 0;
      const dates = new Set();
      input.groups.forEach(function (group) {
        const state = heatmapState(group.startOrdinal, config, group._preparedUtc, false);
        addHeatmapState(accumulator, state, group._aggregateN);
        if (group._preparedUtc != null) verifiedTimeCount += group._aggregateN;
        dates.add(group.startOrdinal);
        if (categories.has(group.category)) addHeatmapState(categories.get(group.category), state, group._aggregateN);
      });
      const complete = finishHeatmapAccumulator(accumulator, range, config);
      return Object.assign({}, input.summary, complete, { id: input.id, label: labels[domainIndex], categoryLabel: categoryLabels[domainIndex],
        status: accumulator.total ? "descriptive" : "unavailable_exact_dates_required", positionEligible: accumulator.total, distinctEligibleDates: dates.size, verifiedTimeCount,
        categoryMatrices: Array.from(categories, function (entry) { const result = finishHeatmapAccumulator(entry[1], range, config); return Object.assign({ category: entry[0], total: entry[1].total }, result); }),
        categoryMatrixStatus: options.includeCategoryMatrices === true ? "top_categories_available" : "not_requested_detailed_views_retain_categories" });
    });
    return { estimatorVersion: "planetary-heatmaps-v1-common-grid", ordinalEpoch: "unix_day", status: "ready", zodiacSystem: config.zodiacSystem,
      ayanamsaId: config.zodiacSystem === "sidereal" ? config.ayanamsaId : null, aspectOrbDegrees: config.aspectOrbDegrees, samplingMode: "common_grid",
      planets: PLANETS, pairs: HEATMAP_PAIRS, domains, range,
      cohort: { prepared: true, inputRows: prepared.inputRows, foldedGroupN: prepared.foldedGroupN },
      method: { ephemeris: "Astronomy Engine", version: "2.1.19", commit: "865d3da7d8112bbc7911238052c6af4aaf877181",
        source: "https://github.com/cosinekitty/astronomy", sha256: "d1b3ab4b86aa409f78c0f0d95162a847496cba7e938eb6f4712cf9c1c45f4a2e",
        position: "Apparent geocentric ecliptic longitude, true ecliptic and equinox of date; light-time and annual aberration included via Ecliptic(GeoVector(body,time,true)).",
        zodiac: config.zodiacSystem === "tropical" ? "Twelve equal 30-degree sectors from the equinox of date, distinct from unequal astronomical constellations." : "Twelve equal 30-degree sidereal sectors using the selected Lahiri or Fagan-Bradley convention and Astronomy Engine precession model; distinct from unequal astronomical constellations.",
        samplingMode: "common_grid", utcGridHours: COMMON_GRID_HOURS,
        dateOnly: "Counts estimate UTC-noon states. Bounds use the same full 11-point grid over the complete 50-hour possible civil-day UTC interval for every body and pair, independently of any dropdown partner.",
        bounds: "Sampled stable/possible limits plus the existing 0.02-degree longitude and 0.002-degree/day rate margins; not formal enclosures or statistical confidence intervals. Common-grid drill-down retains these bounds; legacy adaptive views may have coarser sampled coverage.",
        motion: "Apparent geocentric tropical-longitude rate from a centered six-hour difference; near stationary is the operational |rate|≤0.01 degree/day bin, not an exact instant of station.",
        aspects: "All 36 unordered pairs. Raw/raw smallest ecliptic-longitude separation is symmetric; pair IDs use canonical body order only. Five major bands plus outside-band cells partition every eligible estimate. No diagonal or duplicate direction is counted.",
        calendar: "Actual UTC-noon states on selected Gregorian candidate days, weighted separately by each domain/category's represented year-month report mix. No uniform sign/aspect expectation or measured observing-effort denominator is assumed.",
        zeroOpportunity: "Zero expected calendar opportunity yields a null ratio. Empty eligible report cohorts remain unavailable rather than zero-share evidence.",
        houses: "Houses, ascendant and local visibility remain uncalculated without verified UTC/timezone and trustworthy observation coordinates." },
      warnings: ["Descriptive catalog associations, not evidence of astrological or planetary causation.", "Common-grid uncertainty is a distinct, consistently sampled estimator; UTC-noon counts remain estimates for date-only records.",
        "Slow-planet states track era and season. Inspect cell-specific within-month opportunity before interpreting ratios.", "Many bodies, pairs and bands are being scanned; no significance claim or Pattern Finder admission is provided.",
        "Crop/animal catalog, discovery, publication and reported dates retain their recorded roles."],
      precomputation: Object.assign({ status: ephemerisAtlas ? "precomputed_raw_ephemeris" : "direct_ephemeris", dateCount: ephemerisAtlas ? ephemerisAtlas.dates.length : 0,
        artifactSha256: ephemerisAtlas ? ephemerisAtlas.manifest.sha256 || null : null }, Object.fromEntries(Object.keys(physicalCounters).map(function (key) { return [key, physicalCounters[key] - initialCounters[key]]; }))),
      inferenceEligible: false, patternFinderEligible: false };
  }
  function computePlanetaryContext(optionsValue) {
    const options = optionsValue || {};
    const epoch = validateEpoch(options.ordinalEpoch);
    const contextEpoch = validateEpoch(options.contextOrdinalEpoch || epoch);
    const config = configuration(options);
    const prepared = options.preparedCohort;
    if (prepared && (prepared.schemaId !== "ufo-planetary-prepared-cohort-v1" || prepared.ordinalEpoch !== "unix_day" || !Array.isArray(prepared.domains))) throw new Error("Invalid prepared planetary cohort.");
    const range = prepared ? prepared.range : rangeValue(options, epoch);
    const initialCounters = Object.assign({}, physicalCounters);
    const domains = [blankDomain("ufo", "UFO / craft reports", "occurrence", "Craft category", config),
      blankDomain("crops", "Crop-circle reports", "catalog_or_discovery_date_not_verified_formation", "Crop / morphology category", config),
      blankDomain("animals", "Animal reports", "reported_or_discovery_date_not_verified_occurrence", "Species category", config)];
    if (prepared) {
      prepared.domains.forEach(function (input, index) {
        input.groups.forEach(function (group) { addRecord(domains[index], group, range, "unix_day"); });
        for (const key of ["total", "reportCount", "nonReportContextCount", "outsideRange"]) domains[index][key] = input.summary[key];
        for (const key of ["excluded", "dateRoles", "sourceCounts"]) domains[index][key] = Object.assign({}, input.summary[key]);
      });
    } else {
      const accept = function (row) { addRecord(domains[0], row, range, epoch); };
      if (typeof options.forEachRow === "function") options.forEachRow(accept);
      else (Array.isArray(options.rows) ? options.rows : []).forEach(accept);
      (Array.isArray(options.crops) ? options.crops : []).forEach(function (row) { addRecord(domains[1], row, range, contextEpoch); });
      (Array.isArray(options.animals) ? options.animals : []).forEach(function (row) { addRecord(domains[2], row, range, contextEpoch); });
    }
    const limit = Math.max(1, Math.min(50, Math.trunc(finite(options.categoryLimit) || 16)));
    domains.forEach(function (domain) { finalizeDomain(domain, range, limit); });
    return { estimatorVersion: VERSION, ordinalEpoch: "unix_day", status: "descriptive", planet: config.planet, planets: PLANETS,
      zodiacSystem: config.zodiacSystem, ayanamsaId: config.zodiacSystem === "sidereal" ? config.ayanamsaId : null,
      aspectPartner: config.aspectPartner, aspectOrbDegrees: config.aspectOrbDegrees, samplingMode: config.samplingMode, availableAspectPartners: PLANETS.filter(function (body) { return body !== config.planet; }),
      signs: SIGNS, aspects: ASPECTS, domains, range,
      cohort: { prepared: !!prepared, inputRows: prepared ? prepared.inputRows : null, foldedGroupN: prepared ? prepared.foldedGroupN : null },
      houses: { eligible: domains.reduce(function (sum, domain) { return sum + domain.houses.eligible; }, 0), eligibleInputs: domains.reduce(function (sum, domain) { return sum + domain.houses.eligibleInputs; }, 0), calculated: false,
        status: "unavailable_verified_time_and_location_required" },
      method: { ephemeris: "Astronomy Engine", version: "2.1.19", commit: "865d3da7d8112bbc7911238052c6af4aaf877181",
        source: "https://github.com/cosinekitty/astronomy", sha256: "d1b3ab4b86aa409f78c0f0d95162a847496cba7e938eb6f4712cf9c1c45f4a2e",
        position: "Apparent geocentric ecliptic longitude, true ecliptic and equinox of date; light-time and annual aberration included via Ecliptic(GeoVector(body,time,true)).",
        zodiac: config.zodiacSystem === "tropical" ? "Twelve equal 30-degree sectors from the equinox of date; zodiac signs are not unequal astronomical constellations." : "Twelve equal 30-degree sidereal sectors after the explicitly chosen ayanamsa; these signs are not unequal astronomical constellations.",
        ayanamsa: config.zodiacSystem === "sidereal" ? (config.ayanamsaId === "fagan_bradley" ? "Fagan-Bradley" : "Lahiri") + " convention, Astronomy Engine precession model: fixed mean J2000 origin plus the true-equinox-of-date precession/nutation of a J2000 ecliptic zero axis. Verified against official Swiss Ephemeris service fixtures from1582 to2100, maximum sampled true-ayanamsa difference0.184 arcsecond; not a bit-identical Swiss Ephemeris implementation." : null,
        ayanamsaReference: "https://www.astro.com/swisseph/swetest.htm",
        samplingMode: config.samplingMode,
        dateOnly: config.samplingMode === "common_grid" ? "UTC-noon descriptive estimate. A common full 11-point grid covers the complete 50-hour civil-day UTC interval [day−14h,day+36h], independently of selected planet or aspect partner." : "UTC-noon descriptive estimate. Sampling covers the complete 50-hour possible civil-day UTC interval [day−14h,day+36h], with six-hour refinement near zodiac/aspect crossings or stations.",
        uncertainty: "Displayed stable/possible bounds describe the sampled interval plus 0.02-degree longitude and 0.002-degree/day speed margins. Finite sampling is not a formal enclosure or a statistical confidence interval.",
        motion: "Apparent geocentric tropical-longitude rate from a centered six-hour difference; near stationary is the operational |rate|≤0.01 degree/day bin, not an exact instant of station.",
        aspects: "Smallest geocentric ecliptic longitude separation, within the declared orb of 0,60,90,120 or180 degrees. Convention shifts cancel; ecliptic latitude is not included.",
        houses: "No houses, ascendant or local-horizon positions are calculated. These require verified UTC/timezone, trustworthy event coordinates and an explicit house-system convention.",
        calendar: "Normalized Gregorian civil dates from1582-10-15 through2100-12-31; earlier dates remain excluded until the original calendar is verified.",
        independentReference: "https://ssd.jpl.nasa.gov/horizons/manual.html" },
      precomputation: Object.assign({ status: ephemerisAtlas ? "precomputed_raw_ephemeris" : "direct_ephemeris", schemaId: ephemerisAtlas ? ATLAS_SCHEMA : null,
        dateCount: ephemerisAtlas ? ephemerisAtlas.dates.length : 0, artifactSha256: ephemerisAtlas ? ephemerisAtlas.manifest.sha256 || null : null },
        Object.fromEntries(Object.keys(physicalCounters).map(function (key) { return [key, physicalCounters[key] - initialCounters[key]]; }))),
      warnings: ["Descriptive report-catalog associations; no astrological or planetary causal effect is established.",
        "Slow-planet positions are strongly tied to calendar era. Use actual year-month opportunity and inspect months with within-month state variation.",
        "Noon sign, aspect and motion counts are estimates when the event's UTC timestamp is not verified; sampled interval bounds remain visible.",
        "Crop discovery/catalog and animal publication/report dates retain their recorded roles; they do not become formation or occurrence times.",
        "Planetary longitudes alone neither establish local visibility nor identify a reported object.",
        "The selected aspect orb is a declared comparison rule. Trying bodies, signs, aspects and orbs generates multiple comparisons; no significance claim is supplied."],
      inferenceEligible: false, patternFinderEligible: false };
  }
  function clearCaches() { dayCache.clear(); noonCache.clear(); monthCache.clear(); heatmapDayCache.clear(); heatmapMonthCache.clear(); }
  return { VERSION, PLANETS, SIGNS, ASPECTS, MOTIONS, computePlanetaryContext, positionForDay, positionAtUtc, longitudeRateAtUtc,
    ayanamsaDegreesAtUtc, angularDistance, clearCaches, preparePlanetaryCohort, computePlanetaryHeatmaps, decodeEphemerisAtlas, setEphemerisAtlas, clearEphemerisAtlas, buildEphemerisAtlasBuffer,
    ATLAS_SCHEMA, ATLAS_HOURS };
});

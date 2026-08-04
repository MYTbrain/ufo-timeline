(function (root, factory) {
  "use strict";

  const api = factory();
  if (typeof module === "object" && module && module.exports) {
    module.exports = api;
  }
  if (root) {
    root.UfoAnalysisStats = api;
  }
})(typeof self !== "undefined" ? self : (typeof globalThis !== "undefined" ? globalThis : this), function () {
  "use strict";

  const SCHEMA_VERSION = 2;
  const ESTIMATOR_VERSION = "analysis_v2_3_duration_assessment_1";
  const MINIMUM_COMMON_SUPPORT = 0.80;
  const DEFAULT_BOOTSTRAP_REPLICATES = 999;
  const DEFAULT_ASSOCIATION_PERMUTATIONS = 499;
  const BASELINE_MODES = Object.freeze({
    OTHER_DATES_BALANCED: "other_dates_balanced",
    // Public compatibility key; the legacy input is normalized immediately
    // and is never emitted in a v2 result envelope.
    OTHER_DATES_MATCHED: "other_dates_balanced",
    PREVIOUS_EQUAL_DURATION: "previous_equal_duration",
    FULL_CATALOG: "full_catalog",
    INTERNAL_STRUCTURE: "internal_structure",
  });
  const ANALYSIS_MODES = Object.freeze({
    COHORT_COMPARISON: "cohort_comparison",
    WHOLE_CORPUS_STRUCTURE: "whole_corpus_structure",
  });
  const COMPARISON_STATES = Object.freeze({
    INFERENTIAL: "inferential",
    DESCRIPTIVE_OVERLAP: "descriptive_overlap",
    WHOLE_CORPUS_STRUCTURE: "whole_corpus_structure",
    UNAVAILABLE_NO_REFERENCE: "unavailable_no_reference",
    UNAVAILABLE_SELF_COMPARISON: "unavailable_self_comparison",
  });
  const MONTH_AXIS_ORDER = Object.freeze(Array.from({ length: 12 }, function (_unused, index) {
    return String(index + 1).padStart(2, "0");
  }));
  const DURATION_BIN_ORDER = Object.freeze([
    "under_10_seconds",
    "10_59_seconds",
    "1_4_minutes",
    "5_14_minutes",
    "15_59_minutes",
    "1_5_hours",
    "over_5_hours",
  ]);
  const DURATION_BIN_LABELS = Object.freeze({
    under_10_seconds: "Under 10 seconds",
    "10_59_seconds": "10–59 seconds",
    "1_4_minutes": "1–4 minutes",
    "5_14_minutes": "5–14 minutes",
    "15_59_minutes": "15–59 minutes",
    "1_5_hours": "1–5 hours",
    over_5_hours: "Over 5 hours",
  });
  const FAMILY_ORDER = Object.freeze([
    "craft",
    "time_month",
    "geography",
    "source",
    "date_precision",
    "location_precision",
    "coordinate_source",
    "craft_confidence",
  ]);
  const FAMILY_COVARIATES = Object.freeze({
    craft: Object.freeze(["source", "coarse_geography", "coordinate_class"]),
    time_month: Object.freeze(["source", "coarse_geography", "coordinate_class", "craft"]),
    geography: Object.freeze(["source", "coordinate_class", "craft"]),
    source: Object.freeze(["coarse_geography", "coordinate_class", "craft"]),
    date_precision: Object.freeze(["source", "coarse_geography", "craft"]),
    location_precision: Object.freeze(["source", "coarse_geography", "craft"]),
    coordinate_source: Object.freeze(["source", "coarse_geography", "craft"]),
    craft_confidence: Object.freeze(["source", "coarse_geography", "craft"]),
  });
  const SOURCE_COORDINATE_VALUES = new Set([
    "raw_latlong",
    "location_coordinates",
    "source_coordinates",
    "source-provided",
    "source_provided",
  ]);
  const POINT_NEIGHBOR_EXCLUDED_CRAFTS = new Set([
    "", "unknown", "other", "non_ufo", "non-ufo", "conventional", "aircraft", "fireball", "meteor",
  ]);
  const POINT_NEIGHBOR_CRAFT_CONFIDENCE = new Set(["medium", "high"]);
  const POINT_NEIGHBOR_SAME_DAY_SUITABILITY = new Set(["medium", "strong"]);
  const UNKNOWN_VALUES = new Set(["", "none", "null", "unknown", "unresolved", "not_provided", "n/a"]);
  const EXPLORATORY_POLICY = "Exploratory association; not evidence of cause, authenticity, incidence, risk, or travel.";
  const EQUAL_AREA_LATITUDE_BOUNDS = Array.from({ length: 13 }, function (_unused, index) {
    return Math.asin(clamp(-1 + ((2 * index) / 12), -1, 1)) * 180 / Math.PI;
  });
  const LAMBERT_MAP_LATITUDE_BOUNDS = Array.from({ length: 7 }, function (_unused, index) {
    return Math.asin(clamp(-1 + ((2 * index) / 6), -1, 1)) * 180 / Math.PI;
  });

  function finiteNumber(value) {
    if (value == null || (typeof value === "string" && value.trim() === "")) return null;
    const numeric = Number(value);
    return Number.isFinite(numeric) ? numeric : null;
  }

  function finiteInteger(value) {
    const numeric = finiteNumber(value);
    return numeric == null ? null : Math.trunc(numeric);
  }

  function clamp(value, minimum, maximum) {
    return Math.max(minimum, Math.min(maximum, value));
  }

  function category(value, fallback) {
    const text = String(value == null ? "" : value).trim();
    return text || (fallback || "unknown");
  }

  function isKnown(value) {
    return !UNKNOWN_VALUES.has(category(value, "unknown").toLowerCase());
  }

  function increment(map, key, amount) {
    const normalizedKey = category(key, "unknown");
    map.set(normalizedKey, (map.get(normalizedKey) || 0) + (amount == null ? 1 : amount));
  }

  function incrementRaw(map, key, amount) {
    map.set(key, (map.get(key) || 0) + (amount == null ? 1 : amount));
  }

  function sortedKeys(map) {
    return Array.from(map.keys()).sort(function (left, right) {
      return String(left).localeCompare(String(right));
    });
  }

  function semanticAxisRank(value, axisType) {
    const text = String(value == null ? "" : value);
    if (axisType === "month") {
      const monthIndex = MONTH_AXIS_ORDER.indexOf(text.padStart(2, "0"));
      return monthIndex === -1 ? Number.POSITIVE_INFINITY : monthIndex;
    }
    if (axisType === "year" || axisType === "decade" || axisType === "numeric") {
      const numeric = finiteNumber(text.replace(/s$/i, ""));
      return numeric == null ? Number.POSITIVE_INFINITY : numeric;
    }
    if (axisType === "geography") {
      const match = /(?:ea(?:6x12|12x24):)?(\d+):(\d+)$/.exec(text);
      if (match) return (Number(match[1]) * 1000) + Number(match[2]);
    }
    return null;
  }

  function semanticAxisCompare(leftValue, rightValue, axisType) {
    const leftRank = semanticAxisRank(leftValue, axisType);
    const rightRank = semanticAxisRank(rightValue, axisType);
    if (leftRank != null && rightRank != null && leftRank !== rightRank) return leftRank - rightRank;
    if (leftRank != null && rightRank == null) return -1;
    if (leftRank == null && rightRank != null) return 1;
    return String(leftValue).localeCompare(String(rightValue), undefined, { numeric: true });
  }

  function semanticAxisMetadata(valuesValue, axisTypeValue) {
    const axisType = category(axisTypeValue, "category");
    const values = Array.from(new Set(Array.from(valuesValue || []).map(function (value) { return String(value); })))
      .sort(function (left, right) { return semanticAxisCompare(left, right, axisType); });
    return {
      type: axisType,
      order: values,
      direction: axisType === "year" || axisType === "decade" || axisType === "month" || axisType === "numeric"
        ? "ascending"
        : (axisType === "geography" ? "spatial" : "categorical"),
      orderedBeforeSampling: true,
    };
  }

  function mapCount(map, key) {
    return Number(map && map.get(key)) || 0;
  }

  function mapEntriesByCount(map) {
    return Array.from(map.entries()).sort(function (left, right) {
      const countDifference = Number(right[1]) - Number(left[1]);
      return countDifference || String(left[0]).localeCompare(String(right[0]));
    });
  }

  function rate(count, total) {
    return total > 0 ? count / total : 0;
  }

  function round(value, digits) {
    if (!Number.isFinite(value)) return value;
    const factor = Math.pow(10, digits == null ? 6 : digits);
    return Math.round(value * factor) / factor;
  }

  function normalizeBaselineMode(value) {
    const normalized = String(value || "").trim().toLowerCase().replace(/[ -]+/g, "_");
    if (normalized === BASELINE_MODES.PREVIOUS_EQUAL_DURATION || normalized === "previous_period") {
      return BASELINE_MODES.PREVIOUS_EQUAL_DURATION;
    }
    if (normalized === BASELINE_MODES.FULL_CATALOG || normalized === "catalog") {
      return BASELINE_MODES.FULL_CATALOG;
    }
    if (normalized === "other_dates_matched" || normalized === BASELINE_MODES.OTHER_DATES_BALANCED) {
      return BASELINE_MODES.OTHER_DATES_BALANCED;
    }
    return BASELINE_MODES.OTHER_DATES_BALANCED;
  }

  // Howard Hinnant's civil calendar conversion, with Python ordinal 719163 as 1970-01-01.
  function civilFromOrdinal(value) {
    const ordinal = finiteInteger(value);
    if (ordinal == null || ordinal < 1) return null;
    let z = ordinal - 719163;
    z += 719468;
    const era = Math.floor(z / 146097);
    const dayOfEra = z - (era * 146097);
    const yearOfEra = Math.floor(
      (dayOfEra - Math.floor(dayOfEra / 1460) + Math.floor(dayOfEra / 36524) - Math.floor(dayOfEra / 146096)) / 365
    );
    let year = yearOfEra + (era * 400);
    const dayOfYear = dayOfEra - ((365 * yearOfEra) + Math.floor(yearOfEra / 4) - Math.floor(yearOfEra / 100));
    const monthPart = Math.floor(((5 * dayOfYear) + 2) / 153);
    const day = dayOfYear - Math.floor(((153 * monthPart) + 2) / 5) + 1;
    const month = monthPart + (monthPart < 10 ? 3 : -9);
    year += month <= 2 ? 1 : 0;
    return { year, month, day };
  }

  function ordinalFromCivil(yearValue, monthValue, dayValue) {
    let year = finiteInteger(yearValue);
    const month = finiteInteger(monthValue);
    const day = finiteInteger(dayValue);
    if (year == null || year < 1 || month == null || month < 1 || month > 12 || day == null || day < 1 || day > 31) {
      return null;
    }
    year -= month <= 2 ? 1 : 0;
    const era = Math.floor(year / 400);
    const yearOfEra = year - (era * 400);
    const monthPart = month + (month > 2 ? -3 : 9);
    const dayOfYear = Math.floor(((153 * monthPart) + 2) / 5) + day - 1;
    const dayOfEra = (yearOfEra * 365) + Math.floor(yearOfEra / 4) - Math.floor(yearOfEra / 100) + dayOfYear;
    const unixDays = (era * 146097) + dayOfEra - 719468;
    return unixDays + 719163;
  }

  function wilsonInterval(successesValue, totalValue, zValue) {
    const total = Math.max(0, finiteNumber(totalValue) || 0);
    const successes = clamp(finiteNumber(successesValue) || 0, 0, total);
    const z = finiteNumber(zValue) || 1.959963984540054;
    if (total <= 0) return { estimate: 0, lower: 0, upper: 1, level: 0.95 };
    const proportion = successes / total;
    const zSquared = z * z;
    const denominator = 1 + (zSquared / total);
    const center = (proportion + (zSquared / (2 * total))) / denominator;
    const margin = (z / denominator) * Math.sqrt(
      (proportion * (1 - proportion) / total) + (zSquared / (4 * total * total))
    );
    return {
      estimate: proportion,
      lower: clamp(center - margin, 0, 1),
      upper: clamp(center + margin, 0, 1),
      level: 0.95,
    };
  }

  function newcombeDifferenceInterval(successesA, totalA, successesB, totalB, zValue) {
    const first = wilsonInterval(successesA, totalA, zValue);
    const second = wilsonInterval(successesB, totalB, zValue);
    const difference = first.estimate - second.estimate;
    const lower = difference - Math.sqrt(
      Math.pow(first.estimate - first.lower, 2) + Math.pow(second.upper - second.estimate, 2)
    );
    const upper = difference + Math.sqrt(
      Math.pow(first.upper - first.estimate, 2) + Math.pow(second.estimate - second.lower, 2)
    );
    return {
      estimate: difference,
      lower: clamp(lower, -1, 1),
      upper: clamp(upper, -1, 1),
      level: 0.95,
      method: "newcombe_wilson",
    };
  }

  function erf(value) {
    const sign = value < 0 ? -1 : 1;
    const x = Math.abs(value);
    const t = 1 / (1 + (0.3275911 * x));
    const polynomial = t * (
      0.254829592 + (t * (-0.284496736 + (t * (1.421413741 + (t * (-1.453152027 + (t * 1.061405429)))))))
    );
    return sign * (1 - (polynomial * Math.exp(-x * x)));
  }

  function normalCdf(value) {
    return 0.5 * (1 + erf(value / Math.SQRT2));
  }

  function proportionComparison(successesAValue, totalAValue, successesBValue, totalBValue) {
    const totalA = Math.max(0, finiteNumber(totalAValue) || 0);
    const totalB = Math.max(0, finiteNumber(totalBValue) || 0);
    const successesA = clamp(finiteNumber(successesAValue) || 0, 0, totalA);
    const successesB = clamp(finiteNumber(successesBValue) || 0, 0, totalB);
    const failuresA = totalA - successesA;
    const failuresB = totalB - successesB;
    const combined = totalA + totalB;
    const pooled = combined > 0 ? (successesA + successesB) / combined : 0;
    const standardError = totalA > 0 && totalB > 0
      ? Math.sqrt(pooled * (1 - pooled) * ((1 / totalA) + (1 / totalB)))
      : 0;
    const z = standardError > 0 ? ((successesA / totalA) - (successesB / totalB)) / standardError : 0;
    const pValue = standardError > 0 ? clamp(2 * (1 - normalCdf(Math.abs(z))), 0, 1) : 1;
    const expected = combined > 0
      ? [
        totalA * pooled,
        totalA * (1 - pooled),
        totalB * pooled,
        totalB * (1 - pooled),
      ]
      : [0, 0, 0, 0];
    const cells = [successesA, failuresA, successesB, failuresB];
    let chiSquared = 0;
    for (let index = 0; index < expected.length; index += 1) {
      if (expected[index] > 0) {
        chiSquared += Math.pow(cells[index] - expected[index], 2) / expected[index];
      }
    }
    return {
      pValue,
      z,
      chiSquared,
      cramersV: combined > 0 ? Math.sqrt(chiSquared / combined) : 0,
      expectedCells: expected,
      minimumExpectedCell: expected.length ? Math.min.apply(null, expected) : 0,
    };
  }

  function benjaminiHochberg(items, getPValue) {
    const input = Array.isArray(items) ? items : [];
    const accessor = typeof getPValue === "function" ? getPValue : function (item) { return item && item.pValue; };
    const ranked = input.map(function (item, index) {
      return {
        item,
        index,
        pValue: clamp(finiteNumber(accessor(item)) == null ? 1 : finiteNumber(accessor(item)), 0, 1),
      };
    }).sort(function (left, right) {
      return (left.pValue - right.pValue) || (left.index - right.index);
    });
    let nextQ = 1;
    for (let index = ranked.length - 1; index >= 0; index -= 1) {
      const rawQ = ranked[index].pValue * ranked.length / (index + 1);
      nextQ = Math.min(nextQ, rawQ);
      ranked[index].qValue = clamp(nextQ, 0, 1);
    }
    const qValues = new Array(input.length).fill(1);
    ranked.forEach(function (entry) {
      qValues[entry.index] = entry.qValue;
    });
    return qValues;
  }

  function assignEligibleBenjaminiHochberg(itemsValue) {
    const items = Array.isArray(itemsValue) ? itemsValue : [];
    const eligible = [];
    items.forEach(function (item, index) {
      const pValue = finiteNumber(item && item.pValue);
      if (!item || item.inferenceEligible !== true || pValue == null) return;
      eligible.push({ index, pValue });
    });
    const qValues = benjaminiHochberg(eligible, function (entry) { return entry.pValue; });
    items.forEach(function (item) {
      if (item) item.qValue = null;
    });
    eligible.forEach(function (entry, eligibleIndex) {
      items[entry.index].qValue = round(qValues[eligibleIndex], 12);
    });
    return items;
  }

  function normalQuantileProbability(sortedValues, probabilityValue) {
    const values = Array.isArray(sortedValues) ? sortedValues : [];
    if (!values.length) return null;
    const probability = clamp(finiteNumber(probabilityValue) == null ? 0.5 : finiteNumber(probabilityValue), 0, 1);
    const position = (values.length - 1) * probability;
    const lowerIndex = Math.floor(position);
    const upperIndex = Math.ceil(position);
    if (lowerIndex === upperIndex) return values[lowerIndex];
    const fraction = position - lowerIndex;
    return values[lowerIndex] + ((values[upperIndex] - values[lowerIndex]) * fraction);
  }

  function deterministicSeed(value) {
    const text = String(value == null ? "analysis-v2" : value);
    let hash = 2166136261;
    for (let index = 0; index < text.length; index += 1) {
      hash ^= text.charCodeAt(index);
      hash = Math.imul(hash, 16777619);
    }
    return hash >>> 0;
  }

  function deterministicRandom(seedValue) {
    let state = deterministicSeed(seedValue) || 0x6d2b79f5;
    return function () {
      state += 0x6d2b79f5;
      let value = state;
      value = Math.imul(value ^ (value >>> 15), value | 1);
      value ^= value + Math.imul(value ^ (value >>> 7), value | 61);
      return ((value ^ (value >>> 14)) >>> 0) / 4294967296;
    };
  }

  function hypergeometricSampler(populationValue, successPopulationValue, drawsValue) {
    const population = Math.max(0, Math.round(finiteNumber(populationValue) || 0));
    const successPopulation = clamp(
      Math.round(finiteNumber(successPopulationValue) || 0),
      0,
      population
    );
    const draws = clamp(Math.round(finiteNumber(drawsValue) || 0), 0, population);
    const lower = Math.max(0, draws - (population - successPopulation));
    const upper = Math.min(draws, successPopulation);
    if (lower >= upper) {
      return function () { return lower; };
    }

    // Construct the finite hypergeometric CDF relative to its mode.  This is
    // the exact conditional distribution produced by permuting column labels
    // inside one stratum while holding both margins fixed.  Starting at the
    // mode keeps the recurrence numerically stable even for the full catalog.
    const mode = clamp(
      Math.floor(((draws + 1) * (successPopulation + 1)) / (population + 2)),
      lower,
      upper
    );
    const leftValues = [mode];
    const leftWeights = [1];
    let value = mode;
    let weight = 1;
    while (value > lower) {
      const numerator = value * (population - successPopulation - draws + value);
      const denominator = (successPopulation - value + 1) * (draws - value + 1);
      weight *= denominator > 0 ? numerator / denominator : 0;
      value -= 1;
      if (!(weight > 0) || !Number.isFinite(weight)) break;
      leftValues.push(value);
      leftWeights.push(weight);
    }
    const rightValues = [];
    const rightWeights = [];
    value = mode;
    weight = 1;
    while (value < upper) {
      const numerator = (successPopulation - value) * (draws - value);
      const denominator = (value + 1) * (population - successPopulation - draws + value + 1);
      weight *= denominator > 0 ? numerator / denominator : 0;
      value += 1;
      if (!(weight > 0) || !Number.isFinite(weight)) break;
      rightValues.push(value);
      rightWeights.push(weight);
    }

    const values = leftValues.slice().reverse().concat(rightValues);
    const weights = leftWeights.slice().reverse().concat(rightWeights);
    const totalWeight = weights.reduce(function (sum, item) { return sum + item; }, 0);
    const cumulative = new Array(weights.length);
    let running = 0;
    weights.forEach(function (item, index) {
      running += item / totalWeight;
      cumulative[index] = running;
    });
    cumulative[cumulative.length - 1] = 1;
    return function (random) {
      const target = random();
      let low = 0;
      let high = cumulative.length - 1;
      while (low < high) {
        const middle = (low + high) >>> 1;
        if (target <= cumulative[middle]) high = middle;
        else low = middle + 1;
      }
      return values[low];
    };
  }

  function deterministicStratifiedCellPermutation(strataValue, optionsValue) {
    const options = optionsValue || {};
    const strata = (Array.isArray(strataValue) ? strataValue : []).filter(function (entry) {
      return entry && entry.population > 0 && entry.expected > 0;
    });
    const replicateCount = Math.max(
      1,
      finiteInteger(options.replicates) || DEFAULT_ASSOCIATION_PERMUTATIONS
    );
    const seed = String(options.seed == null ? "analysis-v2.2-association" : options.seed);
    const observed = strata.reduce(function (sum, entry) { return sum + entry.observed; }, 0);
    const expected = strata.reduce(function (sum, entry) { return sum + entry.expected; }, 0);
    if (!(expected > 0) || !strata.length) {
      return {
        pValue: null,
        method: "deterministic_stratified_permutation",
        permutations: 0,
        seed,
        status: "not_estimable",
      };
    }
    const samplerCache = options.samplerCache instanceof Map ? options.samplerCache : new Map();
    const samplers = strata.map(function (entry) {
      const population = Math.round(entry.population);
      const successPopulation = Math.round(entry.columnTotal);
      const draws = Math.round(entry.rowTotal);
      const cacheKey = population + "|" + successPopulation + "|" + draws;
      if (!samplerCache.has(cacheKey)) {
        samplerCache.set(cacheKey, hypergeometricSampler(population, successPopulation, draws));
      }
      return samplerCache.get(cacheKey);
    });
    const random = deterministicRandom(seed);
    const observedDistance = Math.abs(observed - expected);
    let asOrMoreExtreme = 0;
    for (let replicate = 0; replicate < replicateCount; replicate += 1) {
      let permutedObserved = 0;
      for (let index = 0; index < samplers.length; index += 1) {
        permutedObserved += samplers[index](random);
      }
      if (Math.abs(permutedObserved - expected) + 1e-12 >= observedDistance) {
        asOrMoreExtreme += 1;
      }
    }
    return {
      pValue: (asOrMoreExtreme + 1) / (replicateCount + 1),
      method: "deterministic_stratified_permutation",
      permutations: replicateCount,
      seed,
      extremeReplicates: asOrMoreExtreme,
      status: "estimated",
    };
  }

  function sampledStandardNormal(random) {
    const first = Math.max(Number.EPSILON, random());
    const second = random();
    return Math.sqrt(-2 * Math.log(first)) * Math.cos(2 * Math.PI * second);
  }

  function sampledBinomial(totalValue, probabilityValue, random) {
    const total = Math.max(0, Math.round(finiteNumber(totalValue) || 0));
    const probability = clamp(finiteNumber(probabilityValue) || 0, 0, 1);
    if (!total || probability <= 0) return 0;
    if (probability >= 1) return total;
    const reflected = probability > 0.5;
    const workingProbability = reflected ? 1 - probability : probability;
    const mean = total * workingProbability;
    const variance = total * workingProbability * (1 - workingProbability);
    let successes;
    if (variance >= 9) {
      successes = clamp(Math.round(mean + (sampledStandardNormal(random) * Math.sqrt(variance))), 0, total);
    } else {
      const failureProbability = 1 - workingProbability;
      let probabilityAtCount = Math.pow(failureProbability, total);
      let cumulative = probabilityAtCount;
      const draw = random();
      successes = 0;
      while (draw > cumulative && successes < total) {
        probabilityAtCount *= ((total - successes) / (successes + 1)) * (workingProbability / failureProbability);
        successes += 1;
        cumulative += probabilityAtCount;
      }
    }
    return reflected ? total - successes : successes;
  }

  function normalizeComparisonStrata(strataValue) {
    const input = Array.isArray(strataValue) ? strataValue : [];
    return input.map(function (entryValue, index) {
      const entry = entryValue || {};
      const activeTotal = Math.max(0, finiteNumber(entry.activeTotal) || 0);
      const referenceTotal = Math.max(0, finiteNumber(entry.referenceTotal) || 0);
      return {
        key: category(entry.key, "stratum-" + index),
        activeCount: clamp(finiteNumber(entry.activeCount != null ? entry.activeCount : entry.observedCount) || 0, 0, activeTotal),
        activeTotal,
        referenceCount: clamp(finiteNumber(entry.referenceCount) || 0, 0, referenceTotal),
        referenceTotal,
      };
    }).filter(function (entry) {
      return entry.activeTotal > 0 || entry.referenceTotal > 0;
    }).sort(function (left, right) {
      return String(left.key).localeCompare(String(right.key));
    });
  }

  function cochranMantelHaenszel(strataValue) {
    const strata = normalizeComparisonStrata(strataValue).filter(function (entry) {
      return entry.activeTotal > 0 && entry.referenceTotal > 0;
    });
    let numerator = 0;
    let denominator = 0;
    let expectedSum = 0;
    let varianceSum = 0;
    let observedSum = 0;
    let total = 0;
    let minimumExpectedCell = Infinity;
    let varianceFirst = 0;
    let varianceMiddle = 0;
    let varianceLast = 0;
    strata.forEach(function (entry) {
      const a = entry.activeCount;
      const b = entry.activeTotal - a;
      const c = entry.referenceCount;
      const d = entry.referenceTotal - c;
      const n = entry.activeTotal + entry.referenceTotal;
      if (n <= 0) return;
      const rowActive = entry.activeTotal;
      const rowReference = entry.referenceTotal;
      const columnObserved = a + c;
      const columnOther = b + d;
      const expectedCells = [
        rowActive * columnObserved / n,
        rowActive * columnOther / n,
        rowReference * columnObserved / n,
        rowReference * columnOther / n,
      ];
      expectedCells.forEach(function (expected) {
        minimumExpectedCell = Math.min(minimumExpectedCell, expected);
      });
      const expectedA = expectedCells[0];
      const varianceA = n > 1
        ? (rowActive * rowReference * columnObserved * columnOther) / (n * n * (n - 1))
        : 0;
      observedSum += a;
      expectedSum += expectedA;
      varianceSum += varianceA;
      total += n;
      const rTerm = (a * d) / n;
      const sTerm = (b * c) / n;
      numerator += rTerm;
      denominator += sTerm;
      const pTerm = (a + d) / n;
      const qTerm = (b + c) / n;
      varianceFirst += pTerm * rTerm;
      varianceMiddle += (pTerm * sTerm) + (qTerm * rTerm);
      varianceLast += qTerm * sTerm;
    });
    if (!Number.isFinite(minimumExpectedCell)) minimumExpectedCell = 0;
    const z = varianceSum > 0 ? (observedSum - expectedSum) / Math.sqrt(varianceSum) : 0;
    const chiSquared = z * z;
    const pValue = varianceSum > 0 ? clamp(2 * (1 - normalCdf(Math.abs(z))), 0, 1) : 1;
    const oddsRatio = denominator > 0 ? numerator / denominator : (numerator > 0 ? Infinity : 1);
    let standardError = null;
    if (numerator > 0 && denominator > 0) {
      const variance = (varianceFirst / (2 * numerator * numerator)) +
        (varianceMiddle / (2 * numerator * denominator)) +
        (varianceLast / (2 * denominator * denominator));
      if (Number.isFinite(variance) && variance >= 0) standardError = Math.sqrt(variance);
    }
    const logOdds = Number.isFinite(oddsRatio) && oddsRatio > 0 ? Math.log(oddsRatio) : null;
    return {
      method: "cochran_mantel_haenszel",
      strataCount: strata.length,
      supportedN: total,
      oddsRatio: Number.isFinite(oddsRatio) ? round(oddsRatio, 8) : null,
      oddsRatioUnbounded: !Number.isFinite(oddsRatio),
      interval: logOdds != null && standardError != null ? {
        lower: round(Math.exp(logOdds - (1.959963984540054 * standardError)), 8),
        upper: round(Math.exp(logOdds + (1.959963984540054 * standardError)), 8),
        level: 0.95,
        method: "robins_breslow_greenland",
      } : null,
      z: round(z, 8),
      chiSquared: round(chiSquared, 8),
      pValue: round(pValue, 12),
      cramersV: total > 0 ? round(Math.sqrt(chiSquared / total), 8) : 0,
      minimumExpectedCell: round(minimumExpectedCell, 6),
    };
  }

  function deterministicAggregatedStratumBootstrap(strataValue, optionsValue) {
    const options = optionsValue || {};
    const strata = normalizeComparisonStrata(strataValue).filter(function (entry) {
      return entry.activeTotal > 0 && entry.referenceTotal > 0;
    });
    const replicateCount = Math.max(1, finiteInteger(options.replicates) || DEFAULT_BOOTSTRAP_REPLICATES);
    const activeTotal = strata.reduce(function (sum, entry) { return sum + entry.activeTotal; }, 0);
    if (!activeTotal || !strata.length) {
      return {
        estimate: null,
        lower: null,
        upper: null,
        level: 0.95,
        method: "deterministic_aggregated_stratum_bootstrap",
        replicates: replicateCount,
        seed: String(options.seed == null ? "analysis-v2" : options.seed),
        status: "not_estimable",
      };
    }
    let activeShare = 0;
    let referenceShare = 0;
    let referenceInformation = 0;
    const weightedStrata = strata.map(function (entry) {
      const weight = entry.activeTotal / activeTotal;
      const activeProbability = rate(entry.activeCount, entry.activeTotal);
      const referenceProbability = rate(entry.referenceCount, entry.referenceTotal);
      activeShare += weight * activeProbability;
      referenceShare += weight * referenceProbability;
      referenceInformation += (weight * weight) / entry.referenceTotal;
      return {
        entry,
        weight,
        activeProbability,
        referenceProbability,
      };
    });
    const effectiveReferenceN = referenceInformation > 0 ? Math.max(1, Math.round(1 / referenceInformation)) : 1;
    const random = deterministicRandom(options.seed == null ? "analysis-v2" : options.seed);
    const replicates = new Array(replicateCount);
    for (let index = 0; index < replicateCount; index += 1) {
      let standardizedActiveShare = 0;
      let standardizedReferenceShare = 0;
      weightedStrata.forEach(function (stratum) {
        standardizedActiveShare += stratum.weight * rate(
          sampledBinomial(stratum.entry.activeTotal, stratum.activeProbability, random),
          stratum.entry.activeTotal
        );
        standardizedReferenceShare += stratum.weight * rate(
          sampledBinomial(stratum.entry.referenceTotal, stratum.referenceProbability, random),
          stratum.entry.referenceTotal
        );
      });
      replicates[index] = standardizedActiveShare - standardizedReferenceShare;
    }
    replicates.sort(function (left, right) { return left - right; });
    return {
      estimate: round(activeShare - referenceShare, 8),
      lower: round(normalQuantileProbability(replicates, 0.025), 8),
      upper: round(normalQuantileProbability(replicates, 0.975), 8),
      level: 0.95,
      method: "deterministic_aggregated_stratum_bootstrap",
      replicates: replicateCount,
      seed: String(options.seed == null ? "analysis-v2" : options.seed),
      effectiveActiveN: activeTotal,
      effectiveReferenceN,
      strataCount: strata.length,
      status: "estimated",
    };
  }

  function standardizedEffectiveReferenceN(strataValue) {
    const strata = normalizeComparisonStrata(strataValue).filter(function (entry) {
      return entry.activeTotal > 0 && entry.referenceTotal > 0;
    });
    const activeTotal = strata.reduce(function (sum, entry) { return sum + entry.activeTotal; }, 0);
    if (!activeTotal) return 0;
    let referenceInformation = 0;
    strata.forEach(function (entry) {
      const weight = entry.activeTotal / activeTotal;
      referenceInformation += (weight * weight) / entry.referenceTotal;
    });
    return referenceInformation > 0 ? Math.max(1, Math.round(1 / referenceInformation)) : 0;
  }

  function balancedCommonSupportComparison(strataValue, optionsValue) {
    const options = optionsValue || {};
    const allStrata = normalizeComparisonStrata(strataValue);
    const commonStrata = allStrata.filter(function (entry) {
      return entry.activeTotal > 0 && entry.referenceTotal > 0;
    });
    const activeN = Math.max(0, finiteNumber(options.activeN) || allStrata.reduce(function (sum, entry) { return sum + entry.activeTotal; }, 0));
    const referenceN = Math.max(0, finiteNumber(options.referenceN) || allStrata.reduce(function (sum, entry) { return sum + entry.referenceTotal; }, 0));
    const supportedActiveN = commonStrata.reduce(function (sum, entry) { return sum + entry.activeTotal; }, 0);
    const supportedReferenceN = commonStrata.reduce(function (sum, entry) { return sum + entry.referenceTotal; }, 0);
    const observedCount = allStrata.reduce(function (sum, entry) { return sum + entry.activeCount; }, 0);
    const referenceCount = allStrata.reduce(function (sum, entry) { return sum + entry.referenceCount; }, 0);
    const supportedObservedCount = commonStrata.reduce(function (sum, entry) { return sum + entry.activeCount; }, 0);
    const commonSupportRate = rate(supportedActiveN, activeN);
    const minimumCommonSupport = clamp(
      finiteNumber(options.minimumCommonSupport) == null ? MINIMUM_COMMON_SUPPORT : finiteNumber(options.minimumCommonSupport),
      0,
      1
    );
    let adjustedReferenceShare = 0;
    if (supportedActiveN > 0) {
      commonStrata.forEach(function (entry) {
        adjustedReferenceShare += (entry.activeTotal / supportedActiveN) * rate(entry.referenceCount, entry.referenceTotal);
      });
    }
    const adjustedActiveShare = rate(supportedObservedCount, supportedActiveN);
    const adjustedDifference = supportedActiveN > 0 ? adjustedActiveShare - adjustedReferenceShare : null;
    const descriptive = Boolean(options.descriptive);
    const failedGates = [];
    if (!activeN) failedGates.push("active_n");
    if (!referenceN) failedGates.push("reference_n");
    if (!commonStrata.length) failedGates.push("no_common_support");
    if (commonSupportRate < minimumCommonSupport) failedGates.push("common_support");
    if (descriptive) failedGates.push("descriptive_baseline");
    const inferenceEligible = failedGates.length === 0;
    const cmh = commonStrata.length ? cochranMantelHaenszel(commonStrata) : cochranMantelHaenszel([]);
    const interval = !descriptive && commonStrata.length && options.skipBootstrap !== true
      ? deterministicAggregatedStratumBootstrap(commonStrata, {
        replicates: options.bootstrapReplicates,
        seed: options.seed,
      })
      : null;
    const effectiveReferenceN = standardizedEffectiveReferenceN(commonStrata) || supportedReferenceN;
    const adjustedReferenceCount = adjustedReferenceShare * effectiveReferenceN;
    const supportComparison = proportionComparison(
      supportedObservedCount,
      supportedActiveN,
      adjustedReferenceCount,
      effectiveReferenceN
    );
    const suppressionStatus = inferenceEligible ? "eligible" : "suppressed";
    const effectSize = {
      measure: "adjusted_share_difference",
      estimate: adjustedDifference == null ? null : round(adjustedDifference, 8),
      unit: "proportion",
    };
    return {
      estimatorVersion: ESTIMATOR_VERSION,
      covariates: Array.isArray(options.covariates) ? options.covariates.slice() : [],
      activeN,
      referenceN,
      cohortNs: { active: activeN, reference: referenceN },
      observedCount,
      referenceCount,
      supportedActiveN,
      supportedReferenceN,
      supportedNs: { active: supportedActiveN, reference: supportedReferenceN },
      supportedObservedCount,
      commonStrataCount: commonStrata.length,
      commonSupportRate: round(commonSupportRate, 8),
      minimumCommonSupport,
      observedShare: round(rate(observedCount, activeN), 8),
      referenceShare: round(rate(referenceCount, referenceN), 8),
      adjustedActiveShare: supportedActiveN > 0 ? round(adjustedActiveShare, 8) : null,
      adjustedReferenceShare: supportedActiveN > 0 ? round(adjustedReferenceShare, 8) : null,
      adjustedDifference: adjustedDifference == null ? null : round(adjustedDifference, 8),
      adjustedEffect: adjustedDifference == null ? null : round(adjustedDifference, 8),
      effectSize,
      interval,
      uncertainty: interval,
      cmh,
      oddsRatio: cmh.oddsRatio,
      oddsRatioInterval: cmh.interval,
      pValue: inferenceEligible ? cmh.pValue : null,
      qValue: null,
      cramersV: supportComparison.cramersV,
      minimumExpectedCell: supportComparison.minimumExpectedCell,
      inferenceEligible,
      suppressionStatus,
      suppressionReasons: failedGates,
      suppression: { status: suppressionStatus, reasons: failedGates.slice() },
      descriptive,
    };
  }

  function qualifySparseHeatmapCells(cellsValue, optionsValue) {
    const options = optionsValue || {};
    const maximumRows = Math.max(1, finiteInteger(options.maximumRows) || 12);
    const maximumColumns = Math.max(1, finiteInteger(options.maximumColumns) || 12);
    const minimumExpectedCell = Math.max(0, finiteNumber(options.minimumExpectedCell) == null ? 10 : finiteNumber(options.minimumExpectedCell));
    const minimumCommonSupport = clamp(
      finiteNumber(options.minimumCommonSupport) == null ? MINIMUM_COMMON_SUPPORT : finiteNumber(options.minimumCommonSupport),
      0,
      1
    );
    const input = Array.isArray(cellsValue) ? cellsValue : [];
    const fullCells = input.map(function (cellValue, index) {
      const cell = Object.assign({}, cellValue || {});
      const observed = Math.max(0, finiteNumber(cell.observed != null ? cell.observed : cell.activeCount) || 0);
      const referenceCount = Math.max(0, finiteNumber(cell.referenceCount != null ? cell.referenceCount : cell.reference) || 0);
      const expected = finiteNumber(cell.expectedCount != null ? cell.expectedCount
        : (cell.expected != null ? cell.expected : cell.minimumExpectedCell));
      const commonSupportRate = finiteNumber(cell.commonSupportRate);
      const reasons = [];
      const explicitEstimateAvailable = typeof cell.estimateAvailable === "boolean" ? cell.estimateAvailable : null;
      const estimateAvailable = explicitEstimateAvailable == null
        ? (observed > 0 || referenceCount > 0 || (expected != null && expected > 0))
        : explicitEstimateAvailable;
      const structurallyEmpty = cell.structurallyEmpty === true || !estimateAvailable;
      let inferenceEligible = cell.inferenceEligible === true;
      if (structurallyEmpty) {
        reasons.push("both_zero");
      } else {
        if (expected != null && expected < minimumExpectedCell) reasons.push("expected_cell");
        if (commonSupportRate != null && commonSupportRate < minimumCommonSupport) reasons.push("common_support");
        if (cell.inferenceEligible === false && Array.isArray(cell.suppressionReasons)) {
          cell.suppressionReasons.forEach(function (reason) {
            if (reasons.indexOf(reason) === -1) reasons.push(reason);
          });
        }
        if (cell.inferenceEligible == null) {
          inferenceEligible = (expected == null || expected >= minimumExpectedCell) &&
            (commonSupportRate == null || commonSupportRate >= minimumCommonSupport);
        }
      }
      const effect = finiteNumber(
        cell.conservativeEffect != null ? cell.conservativeEffect
          : (cell.adjustedEffect != null ? cell.adjustedEffect
            : (cell.adjustedDifference != null ? cell.adjustedDifference : cell.standardizedResidual))
      );
      cell.key = category(cell.key, "cell-" + index);
      cell.row = category(cell.row, "row");
      cell.column = category(cell.column, "column");
      cell.observed = observed;
      cell.activeCount = finiteNumber(cell.activeCount) == null ? observed : cell.activeCount;
      cell.expectedCount = expected;
      cell.estimateAvailable = !structurallyEmpty;
      cell.tested = cell.tested === true;
      cell.inferenceEligible = !structurallyEmpty && inferenceEligible && reasons.length === 0;
      cell.lowSupport = !structurallyEmpty && !cell.inferenceEligible;
      cell.displayStatus = structurallyEmpty ? "structurally_empty"
        : (cell.inferenceEligible ? "eligible" : (cell.comparisonState === COMPARISON_STATES.WHOLE_CORPUS_STRUCTURE ? "descriptive" : "low_support"));
      cell.displayEligible = !structurallyEmpty;
      cell.suppressionReasons = reasons;
      cell.conservativeEffect = finiteNumber(cell.conservativeEffect) == null ? Math.abs(effect || 0) : Math.abs(finiteNumber(cell.conservativeEffect));
      cell.zeroObservedQualifiedDepletion = cell.inferenceEligible && observed === 0 && (referenceCount > 0 || (expected != null && expected > 0));
      return cell;
    });
    const estimable = fullCells.filter(function (cell) { return cell.estimateAvailable; });
    const rowScores = new Map();
    const columnScores = new Map();
    estimable.forEach(function (cell) {
      rowScores.set(cell.row, Math.max(mapCount(rowScores, cell.row), cell.conservativeEffect));
      columnScores.set(cell.column, Math.max(mapCount(columnScores, cell.column), cell.conservativeEffect));
    });
    function selectedKeys(scores, maximum) {
      return new Set(Array.from(scores.entries()).sort(function (left, right) {
        return (right[1] - left[1]) || String(left[0]).localeCompare(String(right[0]));
      }).slice(0, maximum).map(function (entry) { return entry[0]; }));
    }
    const selectedRows = selectedKeys(rowScores, maximumRows);
    const selectedColumns = selectedKeys(columnScores, maximumColumns);
    const visibleCells = estimable.filter(function (cell) {
      return selectedRows.has(cell.row) && selectedColumns.has(cell.column);
    }).sort(function (left, right) {
      return semanticAxisCompare(left.row, right.row, options.rowAxisType) ||
        semanticAxisCompare(left.column, right.column, options.columnAxisType);
    });
    return {
      visibleCells,
      fullCells,
      metadata: {
        maximumRows,
        maximumColumns,
        minimumExpectedCell,
        minimumCommonSupport,
        inputCellCount: input.length,
        visibleCellCount: visibleCells.length,
        estimateAvailableCellCount: estimable.length,
        eligibleCellCount: fullCells.filter(function (cell) { return cell.inferenceEligible; }).length,
        lowSupportCellCount: fullCells.filter(function (cell) { return cell.lowSupport; }).length,
        suppressedCellCount: fullCells.filter(function (cell) { return cell.suppressionReasons.length > 0; }).length,
        structuralEmptyCellCount: fullCells.filter(function (cell) { return cell.displayStatus === "structurally_empty"; }).length,
        selectedRows: Array.from(selectedRows).sort(function (left, right) { return semanticAxisCompare(left, right, options.rowAxisType); }),
        selectedColumns: Array.from(selectedColumns).sort(function (left, right) { return semanticAxisCompare(left, right, options.columnAxisType); }),
        rowAxis: semanticAxisMetadata(selectedRows, options.rowAxisType),
        columnAxis: semanticAxisMetadata(selectedColumns, options.columnAxisType),
        policy: "Structurally empty cells are omitted. Every estimable cell remains visible; low support limits inference but never replaces a numeric estimate with a suppression label.",
      },
    };
  }

  function selectedAssociationCategories(totals, maximumValue) {
    const maximum = Math.max(2, finiteInteger(maximumValue) || 12);
    const entries = mapEntriesByCount(totals);
    const unknownEntries = entries.filter(function (entry) { return !isKnown(entry[0]); });
    const knownEntries = entries.filter(function (entry) { return isKnown(entry[0]); });
    const hasOther = knownEntries.length + unknownEntries.length > maximum;
    const reserved = (unknownEntries.length ? 1 : 0) + (hasOther ? 1 : 0);
    const selectedKnown = knownEntries.slice(0, Math.max(0, maximum - reserved)).map(function (entry) { return entry[0]; });
    const selected = new Set(selectedKnown);
    if (unknownEntries.length) selected.add("Unknown");
    if (hasOther) selected.add("Other");
    return {
      selected,
      normalize: function (key) {
        if (!isKnown(key)) return "Unknown";
        return selected.has(key) ? key : "Other";
      },
    };
  }

  function normalizedStratifiedMatrix(inputValue) {
    if (inputValue instanceof Map) return inputValue;
    const result = new Map();
    const input = Array.isArray(inputValue) ? inputValue : [];
    input.forEach(function (entryValue) {
      const entry = entryValue || {};
      const stratum = category(entry.stratum, "all");
      const row = category(entry.row, "unknown");
      const column = category(entry.column, "unknown");
      const count = Math.max(0, finiteNumber(entry.count != null ? entry.count : entry.observed) || 0);
      if (!result.has(stratum)) result.set(stratum, new Map());
      incrementRaw(result.get(stratum), row + "\u0000" + column, count);
    });
    return result;
  }

  function adjustedStandardizedResiduals(inputValue, optionsValue) {
    const options = optionsValue || {};
    const comparisonState = options.comparisonState || COMPARISON_STATES.WHOLE_CORPUS_STRUCTURE;
    const stratified = normalizedStratifiedMatrix(inputValue);
    const orderedStrata = Array.from(stratified.entries()).sort(function (left, right) {
      return String(left[0]).localeCompare(String(right[0]));
    });
    let inputSignature = 2166136261;
    orderedStrata.forEach(function (entry) {
      const matrixEntries = Array.from(entry[1].entries()).sort(function (left, right) {
        return String(left[0]).localeCompare(String(right[0]));
      });
      const signaturePart = String(entry[0]) + "\u001e" + matrixEntries.map(function (cell) {
        return String(cell[0]) + "=" + String(cell[1]);
      }).join("\u001d");
      for (let index = 0; index < signaturePart.length; index += 1) {
        inputSignature ^= signaturePart.charCodeAt(index);
        inputSignature = Math.imul(inputSignature, 16777619);
      }
    });
    inputSignature >>>= 0;
    const rowTotalsAll = new Map();
    const columnTotalsAll = new Map();
    let totalReportCount = 0;
    orderedStrata.forEach(function (stratumEntry) {
      const matrix = stratumEntry[1];
      matrix.forEach(function (count, composite) {
        const parts = composite.split("\u0000");
        incrementRaw(rowTotalsAll, parts[0], count);
        incrementRaw(columnTotalsAll, parts[1], count);
        totalReportCount += count;
      });
    });
    const rowSelection = selectedAssociationCategories(rowTotalsAll, options.maximumRows);
    const columnSelection = selectedAssociationCategories(columnTotalsAll, options.maximumColumns);
    const aggregates = new Map();
    let includedReportCount = 0;
    orderedStrata.forEach(function (stratumEntry) {
      const stratumKey = stratumEntry[0];
      const matrix = stratumEntry[1];
      const pooled = new Map();
      matrix.forEach(function (count, composite) {
        const parts = composite.split("\u0000");
        const row = rowSelection.normalize(parts[0]);
        const column = columnSelection.normalize(parts[1]);
        incrementRaw(pooled, row + "\u0000" + column, count);
      });
      const rowTotals = new Map();
      const columnTotals = new Map();
      let stratumTotal = 0;
      pooled.forEach(function (count, composite) {
        const parts = composite.split("\u0000");
        incrementRaw(rowTotals, parts[0], count);
        incrementRaw(columnTotals, parts[1], count);
        stratumTotal += count;
      });
      if (!stratumTotal) return;
      includedReportCount += stratumTotal;
      rowSelection.selected.forEach(function (row) {
        columnSelection.selected.forEach(function (column) {
          const composite = row + "\u0000" + column;
          const observed = mapCount(pooled, composite);
          const rowTotal = mapCount(rowTotals, row);
          const columnTotal = mapCount(columnTotals, column);
          const expected = rowTotal * columnTotal / stratumTotal;
          const rowShare = rate(rowTotal, stratumTotal);
          const columnShare = rate(columnTotal, stratumTotal);
          const variance = expected * Math.max(0, (1 - rowShare) * (1 - columnShare));
          if (!aggregates.has(composite)) {
            aggregates.set(composite, {
              row,
              column,
              observed: 0,
              expected: 0,
              variance: 0,
              supportingStrataCount: 0,
              permutationStrata: [],
            });
          }
          const aggregate = aggregates.get(composite);
          aggregate.observed += observed;
          aggregate.expected += expected;
          aggregate.variance += variance;
          if (expected > 0) {
            aggregate.supportingStrataCount += 1;
            aggregate.permutationStrata.push({
              key: stratumKey,
              population: stratumTotal,
              rowTotal,
              columnTotal,
              observed,
              expected,
            });
          }
        });
      });
    });
    const permutationCount = Math.max(
      1,
      finiteInteger(options.permutationCount) || DEFAULT_ASSOCIATION_PERMUTATIONS
    );
    const permutationSeed = String(options.permutationSeed == null
      ? [
        "analysis-v2.2-adjusted-association",
        category(options.associationLabel, "association"),
        comparisonState,
        inputSignature.toString(16).padStart(8, "0"),
      ].join("|")
      : options.permutationSeed);
    const samplerCache = new Map();
    const cells = Array.from(aggregates.values()).map(function (entry) {
      const residual = entry.variance > 0 ? (entry.observed - entry.expected) / Math.sqrt(entry.variance) : 0;
      const estimateAvailable = entry.expected > 0 || entry.observed > 0;
      const tested = estimateAvailable && entry.expected > 0;
      const permutation = tested ? deterministicStratifiedCellPermutation(entry.permutationStrata, {
        replicates: permutationCount,
        seed: permutationSeed + "|" + entry.row + "\u0000" + entry.column,
        samplerCache,
      }) : null;
      const enrichment = entry.expected > 0 ? entry.observed / entry.expected : null;
      return {
        key: entry.row + "\u0000" + entry.column,
        label: entry.row + " / " + entry.column,
        row: entry.row,
        column: entry.column,
        value: round(residual, 6),
        count: entry.observed,
        observed: entry.observed,
        observedCount: entry.observed,
        expected: round(entry.expected, 6),
        expectedCount: round(entry.expected, 6),
        conditionalExpectedCount: round(entry.expected, 6),
        observedExpectedRatio: enrichment == null ? null : round(enrichment, 8),
        log2ObservedExpected: enrichment != null && enrichment > 0 ? round(Math.log2(enrichment), 8) : null,
        standardizedResidual: round(residual, 6),
        variance: round(entry.variance, 8),
        supportingStrataCount: entry.supportingStrataCount,
        comparisonState,
        comparisonBasis: "conditional_expectation",
        estimateAvailable,
        structurallyEmpty: !estimateAvailable,
        tested,
        pValue: tested && permutation ? round(permutation.pValue, 12) : null,
        pValueMethod: tested && permutation ? permutation.method : null,
        permutationCount: tested && permutation ? permutation.permutations : 0,
        permutationSeed: tested && permutation ? permutation.seed : null,
        permutationExtremeReplicates: tested && permutation ? permutation.extremeReplicates : null,
        qValue: null,
      };
    });
    const estimableCells = cells.filter(function (cell) { return cell.estimateAvailable; });
    const minimumExpectedCell = estimableCells.length
      ? Math.min.apply(null, estimableCells.map(function (cell) { return cell.expectedCount; }))
      : 0;
    const chiSquared = cells.reduce(function (sum, cell) {
      return sum + (cell.expectedCount > 0 ? Math.pow(cell.observedCount - cell.expectedCount, 2) / cell.expectedCount : 0);
    }, 0);
    const rowCount = rowSelection.selected.size;
    const columnCount = columnSelection.selected.size;
    const dimension = Math.min(Math.max(0, rowCount - 1), Math.max(0, columnCount - 1));
    const cramersV = includedReportCount > 0 && dimension > 0
      ? clamp(Math.sqrt(chiSquared / (includedReportCount * dimension)), 0, 1)
      : 0;
    const tableTestable = rowCount >= 2 && columnCount >= 2 && includedReportCount > 0;
    cells.forEach(function (cell) {
      const reasons = [];
      if (!cell.estimateAvailable) reasons.push("structurally_empty");
      if (!tableTestable) reasons.push("table_structure");
      if (!(cell.variance > 0)) reasons.push("zero_variance");
      if (cell.expectedCount < 10) reasons.push("expected_cell");
      cell.inferenceEligible = cell.estimateAvailable && tableTestable && cell.tested && cell.variance > 0 && cell.expectedCount >= 10;
      cell.lowSupport = cell.estimateAvailable && !cell.inferenceEligible;
      cell.displayStatus = !cell.estimateAvailable ? "structurally_empty" : (cell.inferenceEligible ? "estimated" : "low_support");
      cell.displayEligible = cell.estimateAvailable;
      cell.suppressionReasons = reasons;
      cell.suppressionStatus = reasons.length ? "limited" : "eligible";
      cell.suppression = { status: cell.suppressionStatus, reasons: reasons.slice() };
      cell.estimatorVersion = ESTIMATOR_VERSION;
    });
    assignEligibleBenjaminiHochberg(cells);
    cells.forEach(function (cell) {
      const findingReasons = cell.suppressionReasons.slice();
      if (cramersV < 0.10) findingReasons.push("cramers_v");
      if (cell.inferenceEligible && (cell.qValue == null || cell.qValue > 0.05)) findingReasons.push("q_value");
      cell.statisticallyQualified = cell.inferenceEligible && cramersV >= 0.10 && cell.qValue != null && cell.qValue <= 0.05;
      cell.findingEligible = cell.statisticallyQualified;
      cell.qualificationReasons = findingReasons;
      cell.tableCramersV = round(cramersV, 8);
    });
    const orderedCells = cells.sort(function (left, right) {
      return semanticAxisCompare(left.row, right.row, options.rowAxisType) ||
        semanticAxisCompare(left.column, right.column, options.columnAxisType);
    });
    const associationLabel = category(options.associationLabel, "craft-by-source");
    const policyWarning = "Adjusted " + associationLabel + " association. Every estimable cell is displayed with its conditional expected count and receives a deterministic stratified permutation test when expected support is positive. Expected count, FDR, and effect gates qualify inference and findings but never erase descriptive estimates; neither axis is evidence of craft identity or cause.";
    return {
      cells: orderedCells.filter(function (cell) { return cell.estimateAvailable; }),
      fullCells: orderedCells,
      metadata: {
        eligible: tableTestable,
        status: tableTestable ? "estimated" : "not_estimable",
        estimatorVersion: ESTIMATOR_VERSION,
        comparisonState,
        comparisonBasis: "conditional_expectation",
        pValueMethod: "deterministic_stratified_permutation",
        permutationCount,
        permutationSeed,
        permutationInputHash: inputSignature.toString(16).padStart(8, "0"),
        adjustmentCovariates: Array.isArray(options.covariates) ? options.covariates.slice() : ["coarse_geography", "coordinate_class", "era"],
        cramersV: round(cramersV, 8),
        materialAssociationDetected: cramersV >= 0.10,
        associationConclusion: cramersV >= 0.10 ? "material_association_detected" : "no_material_association_detected",
        minimumExpectedCell: round(minimumExpectedCell, 6),
        chiSquared: round(chiSquared, 8),
        degreesOfFreedom: Math.max(0, rowCount - 1) * Math.max(0, columnCount - 1),
        rowCount,
        columnCount,
        rows: semanticAxisMetadata(rowSelection.selected, options.rowAxisType).order,
        columns: semanticAxisMetadata(columnSelection.selected, options.columnAxisType).order,
        rowAxis: semanticAxisMetadata(rowSelection.selected, options.rowAxisType),
        columnAxis: semanticAxisMetadata(columnSelection.selected, options.columnAxisType),
        includedReportCount,
        excludedReportCount: Math.max(0, totalReportCount - includedReportCount),
        totalReportCount,
        estimateAvailableCellCount: cells.filter(function (cell) { return cell.estimateAvailable; }).length,
        testedCellCount: cells.filter(function (cell) { return cell.tested; }).length,
        inferenceEligibleCellCount: cells.filter(function (cell) { return cell.inferenceEligible; }).length,
        qualifiedCellCount: cells.filter(function (cell) { return cell.statisticallyQualified; }).length,
        fdrFamilySize: cells.filter(function (cell) { return cell.inferenceEligible; }).length,
        thresholds: { minimumExpectedCell: 10, minimumCramersV: 0.10, maximumQValue: 0.05 },
        policyWarning,
      },
    };
  }

  function validCoordinates(row) {
    const latitude = finiteNumber(row && row.lat);
    const longitude = finiteNumber(row && row.lon);
    return latitude != null && longitude != null && latitude >= -90 && latitude <= 90 && longitude >= -180 && longitude <= 180;
  }

  function rowMapped(row) {
    if (row && typeof row.mapped === "boolean") return row.mapped;
    return validCoordinates(row);
  }

  function coordinateClass(row) {
    if (!rowMapped(row)) return "unmapped";
    const derived = category(row && row.analysisCoordinateClass, "").toLowerCase();
    if (derived === "source_coordinates" || derived === "generalized_coordinates") return derived;
    const coordinateSource = category(row && row.coordinateSource, "unknown").toLowerCase();
    const precision = category(row && row.precision, "unknown").toLowerCase();
    if (precision === "exact_coords" && SOURCE_COORDINATE_VALUES.has(coordinateSource) && coordinateSource !== "geocoded") {
      return "source_coordinates";
    }
    return "generalized_coordinates";
  }

  function equalAreaGridCell(latitudeValue, longitudeValue) {
    const latitude = finiteNumber(latitudeValue);
    const longitude = finiteNumber(longitudeValue);
    if (latitude == null || longitude == null || latitude < -90 || latitude > 90 || longitude < -180 || longitude > 180) {
      return null;
    }
    const latitudeBands = 12;
    const longitudeBands = 24;
    const normalizedLongitude = longitude === 180 ? -180 : longitude;
    const sinLatitude = Math.sin(latitude * Math.PI / 180);
    const latIndex = clamp(Math.floor(((sinLatitude + 1) / 2) * latitudeBands), 0, latitudeBands - 1);
    const lonIndex = clamp(Math.floor(((normalizedLongitude + 180) / 360) * longitudeBands), 0, longitudeBands - 1);
    const latMinimum = EQUAL_AREA_LATITUDE_BOUNDS[latIndex];
    const latMaximum = EQUAL_AREA_LATITUDE_BOUNDS[latIndex + 1];
    const lonMinimum = -180 + ((360 * lonIndex) / longitudeBands);
    const lonMaximum = -180 + ((360 * (lonIndex + 1)) / longitudeBands);
    return {
      key: "ea12x24:" + latIndex + ":" + lonIndex,
      latIndex,
      lonIndex,
      latMinimum,
      latMaximum,
      lonMinimum,
      lonMaximum,
    };
  }

  function equalAreaGridCellFromIndexes(latitudeIndexValue, longitudeIndexValue) {
    const latIndex = finiteInteger(latitudeIndexValue);
    const lonIndex = finiteInteger(longitudeIndexValue);
    if (latIndex == null || latIndex < 0 || latIndex >= 12 || lonIndex == null || lonIndex < 0 || lonIndex >= 24) {
      return null;
    }
    return {
      key: "ea12x24:" + latIndex + ":" + lonIndex,
      latIndex,
      lonIndex,
      latMinimum: EQUAL_AREA_LATITUDE_BOUNDS[latIndex],
      latMaximum: EQUAL_AREA_LATITUDE_BOUNDS[latIndex + 1],
      lonMinimum: -180 + ((360 * lonIndex) / 24),
      lonMaximum: -180 + ((360 * (lonIndex + 1)) / 24),
    };
  }

  function equalAreaMapCell6x12FromIndexes(latitudeIndexValue, longitudeIndexValue) {
    const latIndex = finiteInteger(latitudeIndexValue);
    const lonIndex = finiteInteger(longitudeIndexValue);
    if (latIndex == null || latIndex < 0 || latIndex >= 6 || lonIndex == null || lonIndex < 0 || lonIndex >= 12) {
      return null;
    }
    return {
      key: "lcea6x12:" + latIndex + ":" + lonIndex,
      latIndex,
      lonIndex,
      latMinimum: LAMBERT_MAP_LATITUDE_BOUNDS[latIndex],
      latMaximum: LAMBERT_MAP_LATITUDE_BOUNDS[latIndex + 1],
      lonMinimum: -180 + ((360 * lonIndex) / 12),
      lonMaximum: -180 + ((360 * (lonIndex + 1)) / 12),
    };
  }

  function equalAreaMapCell6x12(latitudeValue, longitudeValue) {
    const latitude = finiteNumber(latitudeValue);
    const longitude = finiteNumber(longitudeValue);
    if (latitude == null || longitude == null || latitude < -90 || latitude > 90 || longitude < -180 || longitude > 180) {
      return null;
    }
    const normalizedLongitude = longitude === 180 ? -180 : longitude;
    const sinLatitude = Math.sin(latitude * Math.PI / 180);
    const latIndex = clamp(Math.floor(((sinLatitude + 1) / 2) * 6), 0, 5);
    const lonIndex = clamp(Math.floor(((normalizedLongitude + 180) / 360) * 12), 0, 11);
    return equalAreaMapCell6x12FromIndexes(latIndex, lonIndex);
  }

  function familySourceMaps() {
    const result = {};
    FAMILY_ORDER.forEach(function (family) {
      result[family] = new Map();
    });
    return result;
  }

  function familyNestedMaps() {
    const result = {};
    FAMILY_ORDER.forEach(function (family) {
      result[family] = new Map();
    });
    return result;
  }

  function addFamilySourceCount(accumulator, family, key, source) {
    const normalizedKey = key || "unknown";
    const normalizedSource = source || "unknown";
    if (!accumulator.familyBySource[family].has(normalizedKey)) {
      accumulator.familyBySource[family].set(normalizedKey, new Map());
    }
    incrementRaw(accumulator.familyBySource[family].get(normalizedKey), normalizedSource, 1);
  }

  function addFamilyDimensionCount(container, family, key, dimensionValue) {
    const normalizedKey = category(key, "unknown");
    const normalizedDimension = category(dimensionValue, "unknown");
    if (!container[family].has(normalizedKey)) container[family].set(normalizedKey, new Map());
    incrementRaw(container[family].get(normalizedKey), normalizedDimension, 1);
  }

  function addFamilyStratumCount(accumulator, family, key, stratum) {
    incrementRaw(accumulator.familyStrataTotals[family], stratum, 1);
    addFamilyDimensionCount(accumulator.familyCategoryStrata, family, key, stratum);
  }

  function addGeographyRegionStratumCount(accumulator, key, region, stratum) {
    if (!accumulator.geographyStrataTotalsByRegion.has(region)) {
      accumulator.geographyStrataTotalsByRegion.set(region, new Map());
    }
    incrementRaw(accumulator.geographyStrataTotalsByRegion.get(region), stratum, 1);
    if (!accumulator.geographyCategoryStrataByRegion.has(key)) {
      accumulator.geographyCategoryStrataByRegion.set(key, new Map());
    }
    const byRegion = accumulator.geographyCategoryStrataByRegion.get(key);
    if (!byRegion.has(region)) byRegion.set(region, new Map());
    incrementRaw(byRegion.get(region), stratum, 1);
  }

  function explicitCoarseRegion(row) {
    const candidates = [
      row && row.analysisMacroregion,
      row && row.analysisCoarseSpatialStratum,
      row && row.coarseSpatialStratum,
      row && row.analysisRegionId,
      row && row.normalizedRegionId,
      row && row.adminRegionId,
      row && row.regionId,
    ];
    for (let index = 0; index < candidates.length; index += 1) {
      const value = String(candidates[index] == null ? "" : candidates[index]).trim();
      if (value) return value;
    }
    return "";
  }

  function countryForRow(row, mapped) {
    if (!mapped) return "Unmapped";
    const rawCountry = row && row.analysisCountry != null
      ? row.analysisCountry
      : (row && row.country != null ? row.country : row && row.countryName);
    const value = category(
      rawCountry,
      "Unknown country"
    );
    return isKnown(value) ? value : "Unknown country";
  }

  function countryGeographyKey(row, mapped, coordClass) {
    return category(coordClass, "unmapped") + "|country:" + countryForRow(row, mapped);
  }

  function countryGeographyMetadata(keyValue) {
    const key = String(keyValue || "");
    const match = /^([^|]+)\|country:(.*)$/.exec(key);
    const coordinate = match ? match[1] : "unmapped";
    const country = match ? (match[2] || "Unknown country") : "Unknown country";
    return {
      key,
      country,
      displayLabel: country,
      coordinateClass: coordinate,
      label: country + " · " + (coordinate === "source_coordinates" ? "source coordinates" :
        (coordinate === "generalized_coordinates" ? "generalized coordinates" : "unmapped")),
    };
  }

  function createCountryProvenanceAccumulator() {
    return {
      assignmentSources: new Map(),
      assignmentConfidences: new Map(),
      boundaryStatuses: new Map(),
      unknownStatuses: new Map(),
      macroregions: new Map(),
    };
  }

  function addCountryProvenanceToMap(provenanceMap, key, row, country) {
    if (!provenanceMap.has(key)) {
      provenanceMap.set(key, createCountryProvenanceAccumulator());
    }
    const provenance = provenanceMap.get(key);
    const assignmentSource = category(row && row.analysisGeographyAssignmentSource, "unavailable");
    const assignmentConfidence = category(row && row.analysisGeographyAssignmentConfidence, "unavailable");
    const boundaryStatus = category(row && row.analysisGeographyBoundaryStatus, "unavailable");
    const macroregion = category(row && row.analysisMacroregion, "unknown");
    const unknownStatus = country === "Unknown country"
      ? "unknown_country"
      : ((!isKnown(assignmentSource) || assignmentSource === "unavailable" ||
          !isKnown(assignmentConfidence) || assignmentConfidence === "unavailable" ||
          !isKnown(boundaryStatus) || boundaryStatus === "unavailable")
        ? "provenance_incomplete"
        : "assigned_country");
    incrementRaw(provenance.assignmentSources, assignmentSource, 1);
    incrementRaw(provenance.assignmentConfidences, assignmentConfidence, 1);
    incrementRaw(provenance.boundaryStatuses, boundaryStatus, 1);
    incrementRaw(provenance.unknownStatuses, unknownStatus, 1);
    incrementRaw(provenance.macroregions, macroregion, 1);
  }

  function addCountryProvenance(accumulator, key, row, country) {
    addCountryProvenanceToMap(accumulator.countryProvenance, key, row, country);
  }

  function nestedCategoryMap(container, key) {
    if (!container.has(key)) container.set(key, new Map());
    return container.get(key);
  }

  function evidenceCountRows(map, total, labelKey) {
    return mapEntriesByCount(map || new Map()).map(function (entry) {
      const value = { count: Number(entry[1]) || 0, share: round(rate(Number(entry[1]) || 0, total), 10) };
      value[labelKey || "label"] = entry[0];
      return value;
    });
  }

  function primaryEvidenceValue(rows, labelKey) {
    if (!rows.length) return "unavailable";
    return rows.length === 1 ? rows[0][labelKey || "label"] : "mixed";
  }

  function countryEvidenceMetadataFromMaps(activeSourceMap, referenceSourceMap, activeProvenance, referenceProvenance) {
    const activeSourceN = Array.from(activeSourceMap.values()).reduce(function (sum, value) { return sum + Number(value || 0); }, 0);
    const referenceSourceN = Array.from(referenceSourceMap.values()).reduce(function (sum, value) { return sum + Number(value || 0); }, 0);
    const sourceMix = evidenceCountRows(activeSourceMap, activeSourceN, "source");
    const referenceSourceMix = evidenceCountRows(referenceSourceMap, referenceSourceN, "source");
    const provenance = activeProvenance || referenceProvenance || createCountryProvenanceAccumulator();
    const provenanceTotal = activeProvenance ? activeSourceN : referenceSourceN;
    const assignmentSources = evidenceCountRows(provenance.assignmentSources, provenanceTotal, "value");
    const assignmentConfidences = evidenceCountRows(provenance.assignmentConfidences, provenanceTotal, "value");
    const boundaryStatuses = evidenceCountRows(provenance.boundaryStatuses, provenanceTotal, "value");
    const unknownStatuses = evidenceCountRows(provenance.unknownStatuses, provenanceTotal, "value");
    const macroregions = evidenceCountRows(provenance.macroregions, provenanceTotal, "value");
    return {
      sourceMix,
      referenceSourceMix,
      sourceMixLabel: sourceMix.length ? sourceMix.slice(0, 3).map(function (entry) {
        return entry.source + " " + Math.round(entry.share * 100) + "%";
      }).join(", ") : "No active reports",
      geographyAssignmentSource: primaryEvidenceValue(assignmentSources, "value"),
      geographyAssignmentConfidence: primaryEvidenceValue(assignmentConfidences, "value"),
      geographyBoundaryStatus: primaryEvidenceValue(boundaryStatuses, "value"),
      geographyUnknownStatus: primaryEvidenceValue(unknownStatuses, "value"),
      macroregion: primaryEvidenceValue(macroregions, "value"),
      geographyAssignmentProvenance: {
        assignmentSources,
        assignmentConfidences,
        boundaryStatuses,
        unknownStatuses,
        macroregions,
      },
    };
  }

  function countryEvidenceMetadata(active, reference, key) {
    return countryEvidenceMetadataFromMaps(
      active.familyBySource.geography.get(key) || new Map(),
      reference.familyBySource.geography.get(key) || new Map(),
      active.countryProvenance.get(key),
      reference.countryProvenance.get(key)
    );
  }

  function countryDecadeKey(countryKey, decade) {
    return String(countryKey) + "\u001e" + String(decade);
  }

  function countryDecadeFacetKey(countryKey, decade) {
    const metadata = countryGeographyMetadata(countryKey);
    return String(metadata.coordinateClass) + "\u001e" + String(decade);
  }

  function countryDecadeEvidenceMetadata(active, reference, countryKey, decade) {
    const key = countryDecadeKey(countryKey, decade);
    return countryEvidenceMetadataFromMaps(
      active.countryDecadeSources.get(key) || new Map(),
      reference.countryDecadeSources.get(key) || new Map(),
      active.countryDecadeProvenance.get(key),
      reference.countryDecadeProvenance.get(key)
    );
  }

  function sourceBalancedCountryDecadeShare(accumulator, countryKey, decade) {
    const sourceCounts = accumulator.countryDecadeSources.get(countryDecadeKey(countryKey, decade)) || new Map();
    const sourceTotals = accumulator.countryDecadeFacetSourceTotals.get(countryDecadeFacetKey(countryKey, decade)) || new Map();
    const sources = sortedKeys(sourceTotals).filter(function (source) {
      return mapCount(sourceTotals, source) > 0;
    });
    const share = sources.reduce(function (sum, source) {
      return sum + rate(mapCount(sourceCounts, source), mapCount(sourceTotals, source));
    }, 0);
    const facetTotal = Array.from(sourceTotals.values()).reduce(function (sum, value) {
      return sum + Number(value || 0);
    }, 0);
    return {
      share: sources.length ? share / sources.length : 0,
      sourceCount: sources.length,
      facetTotal,
    };
  }

  function coarseRegionForRow(row, mapped, gridCell) {
    const explicit = explicitCoarseRegion(row);
    if (explicit) return explicit;
    if (!mapped) return "unmapped";
    let latitudeIndex = finiteInteger(row && row.analysisGridLatIndex);
    let longitudeIndex = finiteInteger(row && row.analysisGridLonIndex);
    if ((latitudeIndex == null || longitudeIndex == null) && gridCell) {
      latitudeIndex = gridCell.latIndex;
      longitudeIndex = gridCell.lonIndex;
    }
    if (latitudeIndex == null || longitudeIndex == null) {
      const derived = equalAreaGridCell(row && row.lat, row && row.lon);
      if (derived) {
        latitudeIndex = derived.latIndex;
        longitudeIndex = derived.lonIndex;
      }
    }
    if (latitudeIndex == null || longitudeIndex == null) return "mapped_unknown_region";
    return "ea6x12:" + Math.floor(latitudeIndex / 2) + ":" + Math.floor(longitudeIndex / 2);
  }

  function adjustmentStratum(family, values) {
    const covariates = FAMILY_COVARIATES[family] || [];
    return covariates.map(function (covariate) {
      return category(values[covariate], "unknown");
    }).join("\u001f");
  }

  function adjustmentStrata(values) {
    const source = category(values.source, "unknown");
    const geography = category(values.coarse_geography, "unknown");
    const coordinate = category(values.coordinate_class, "unknown");
    const craft = category(values.craft, "unknown");
    return {
      craft: source + "\u001f" + geography + "\u001f" + coordinate,
      time_month: source + "\u001f" + geography + "\u001f" + coordinate + "\u001f" + craft,
      geography: source + "\u001f" + coordinate + "\u001f" + craft,
      source: geography + "\u001f" + coordinate + "\u001f" + craft,
      date_precision: source + "\u001f" + geography + "\u001f" + craft,
      location_precision: source + "\u001f" + geography + "\u001f" + craft,
      coordinate_source: source + "\u001f" + geography + "\u001f" + craft,
      craft_confidence: source + "\u001f" + geography + "\u001f" + craft,
    };
  }

  function durationEra(yearValue) {
    const year = finiteInteger(yearValue);
    if (year == null) return "unknown";
    if (year < 1945) return "pre_1945";
    if (year < 1960) return "1945_1959";
    if (year < 1980) return "1960_1979";
    if (year < 2000) return "1980_1999";
    if (year < 2020) return "2000_2019";
    return "2020_plus";
  }

  function durationStratum(source, yearValue, macroregionValue) {
    return [
      category(source, "unknown"),
      durationEra(yearValue),
      category(macroregionValue, "unknown"),
    ].join("\u001f");
  }

  function addDurationRow(accumulator, row, source, civil) {
    if (!row || row.analysisDurationAvailable !== true) return;
    const status = category(row.analysisDurationStatus, "unparsed");
    const descriptiveBin = category(row.analysisDurationDescriptiveBin, "unknown");
    const inferentialBin = category(row.analysisDurationInferentialBin, "unknown");
    const macroregion = category(row.analysisDurationMacroregion, "unknown");
    const stratum = durationStratum(source, civil && civil.year, macroregion);
    accumulator.durationRawRows += 1;
    incrementRaw(accumulator.durationStatusCounts, status, 1);
    if (["unparsed", "ambiguous", "unavailable"].indexOf(status) === -1) {
      accumulator.durationNormalizedRows += 1;
      incrementRaw(accumulator.durationNormalizedSources, source, 1);
    }
    if (descriptiveBin !== "unknown") {
      accumulator.durationDescriptiveRows += 1;
      incrementRaw(accumulator.durationDescriptiveBins, descriptiveBin, 1);
      incrementRaw(accumulator.durationDescriptiveStrataTotals, stratum, 1);
      if (!accumulator.durationDescriptiveBinStrata.has(descriptiveBin)) {
        accumulator.durationDescriptiveBinStrata.set(descriptiveBin, new Map());
      }
      incrementRaw(accumulator.durationDescriptiveBinStrata.get(descriptiveBin), stratum, 1);
    }
    if (inferentialBin !== "unknown") {
      accumulator.durationInferentialRows += 1;
      incrementRaw(accumulator.durationInferentialBins, inferentialBin, 1);
      incrementRaw(accumulator.durationInferentialSources, source, 1);
      incrementRaw(accumulator.durationInferentialStrataTotals, stratum, 1);
      if (!accumulator.durationInferentialBinStrata.has(inferentialBin)) {
        accumulator.durationInferentialBinStrata.set(inferentialBin, new Map());
      }
      incrementRaw(accumulator.durationInferentialBinStrata.get(inferentialBin), stratum, 1);
    }
  }

  function addStratifiedMatrixCount(container, stratum, rowKey, columnKey) {
    if (!container.has(stratum)) container.set(stratum, new Map());
    addMatrixCount(container.get(stratum), rowKey, columnKey);
  }

  function createAccumulator(name) {
    const accumulator = {
      name,
      total: 0,
      mapped: 0,
      sourceCoordinates: 0,
      generalizedCoordinates: 0,
      exactDate: 0,
      dated: 0,
      datedAndMapped: 0,
      sourceCoordinateExactDay: 0,
      pointNeighborhoodEligible: 0,
      knownCraft: 0,
      knownCraftConfidence: 0,
      knownShape: 0,
      missingOrdinal: 0,
      rowsMissingAny: 0,
      years: new Map(),
      decades: new Map(),
      months: new Map(),
      monthYears: new Map(),
      sources: new Map(),
      types: new Map(),
      crafts: new Map(),
      shapes: new Map(),
      datePrecisions: new Map(),
      locationPrecisions: new Map(),
      coordinateSources: new Map(),
      craftConfidences: new Map(),
      craftSources: new Map(),
      mappedStates: new Map(),
      grid: new Map(),
      gridMetadata: new Map(),
      mapGrid6: new Map(),
      mapGrid6Metadata: new Map(),
      mapGrid6CategoryStrata: new Map(),
      gridDecades: new Map(),
      countryDecades: new Map(),
      countryDecadeSources: new Map(),
      countryDecadeFacetSourceTotals: new Map(),
      countryDecadeProvenance: new Map(),
      countryMetadata: new Map(),
      countryProvenance: new Map(),
      craftDecades: new Map(),
      craftMonths: new Map(),
      craftRegions: new Map(),
      sourceDecades: new Map(),
      sourceYears: new Map(),
      craftSourcesMatrix: new Map(),
      craftSourceStrataMatrix: new Map(),
      craftMonthStrataMatrix: new Map(),
      craftEraStrataMatrix: new Map(),
      craftRegionStrataMatrix: new Map(),
      craftCountryStrataMatrix: new Map(),
      regionEraStrataMatrix: new Map(),
      craftShapesMatrix: new Map(),
      craftShapeStrataMatrix: new Map(),
      patternGeography: new Map(),
      missingAnyBy: {
        years: new Map(),
        decades: new Map(),
        monthYears: new Map(),
        sources: new Map(),
        types: new Map(),
        crafts: new Map(),
        locationPrecisions: new Map(),
        grid: new Map(),
        gridDecades: new Map(),
        countryDecades: new Map(),
        craftDecades: new Map(),
        craftMonths: new Map(),
        craftRegions: new Map(),
        sourceDecades: new Map(),
      },
      familyCounts: null,
      familyBySource: familySourceMaps(),
      familyByRegion: familySourceMaps(),
      familyStrataTotals: familySourceMaps(),
      familyCategoryStrata: familyNestedMaps(),
      geographyStrataTotalsByRegion: new Map(),
      geographyCategoryStrataByRegion: new Map(),
      regions: new Map(),
      durationRawRows: 0,
      durationNormalizedRows: 0,
      durationDescriptiveRows: 0,
      durationInferentialRows: 0,
      durationStatusCounts: new Map(),
      durationNormalizedSources: new Map(),
      durationDescriptiveBins: new Map(),
      durationInferentialBins: new Map(),
      durationInferentialSources: new Map(),
      durationDescriptiveStrataTotals: new Map(),
      durationDescriptiveBinStrata: new Map(),
      durationInferentialStrataTotals: new Map(),
      durationInferentialBinStrata: new Map(),
    };
    accumulator.familyCounts = {
      craft: accumulator.crafts,
      time_month: accumulator.months,
      geography: accumulator.patternGeography,
      source: accumulator.sources,
      date_precision: accumulator.datePrecisions,
      location_precision: accumulator.locationPrecisions,
      coordinate_source: accumulator.coordinateSources,
      craft_confidence: accumulator.craftConfidences,
    };
    return accumulator;
  }

  function addMatrixCount(map, rowKey, columnKey) {
    const key = rowKey + "\u0000" + columnKey;
    incrementRaw(map, key, 1);
  }

  function addRow(accumulator, row) {
    accumulator.total += 1;
    const source = category(row.source, "unknown");
    const reportType = category(row.type, "unknown");
    const craft = category(row.craftType, "unknown");
    const shape = category(row.shape, "unknown");
    const datePrecision = category(row.datePrecision, "unknown");
    const locationPrecision = category(row.precision, "unknown");
    const coordinateSource = category(row.coordinateSource, "unknown");
    const craftConfidence = category(row.craftConfidence, "unknown");
    const craftSource = category(row.craftSource, "unknown");
    const mapped = rowMapped(row);
    const coordClass = coordinateClass(row);
    const countryKey = mapped ? countryGeographyKey(row, true, coordClass) : null;
    const ordinal = finiteInteger(row.sortOrdinal);
    const derivedYear = finiteInteger(row.analysisYear);
    const derivedMonth = finiteInteger(row.analysisMonth);
    const civil = derivedYear != null && derivedYear >= 1 && derivedMonth != null && derivedMonth >= 1 && derivedMonth <= 12
      ? { year: derivedYear, month: derivedMonth }
      : civilFromOrdinal(ordinal);
    const derivedGridKey = mapped ? String(row.analysisGridKey || "").trim() : "";
    let analysisGridKey = derivedGridKey || null;
    let gridCell = null;
    let analysisDecade = "unknown";
    if (mapped && analysisGridKey) {
      if (!accumulator.gridMetadata.has(analysisGridKey)) {
        gridCell = equalAreaGridCellFromIndexes(row.analysisGridLatIndex, row.analysisGridLonIndex);
      }
    } else if (mapped) {
      gridCell = equalAreaGridCell(row.lat, row.lon);
      analysisGridKey = gridCell ? coordClass + "|" + gridCell.key : null;
    }
    let mapCell6 = mapped ? equalAreaMapCell6x12(row.lat, row.lon) : null;
    if (!mapCell6 && mapped) {
      const fineLatIndex = finiteInteger(row.analysisGridLatIndex != null ? row.analysisGridLatIndex : (gridCell && gridCell.latIndex));
      const fineLonIndex = finiteInteger(row.analysisGridLonIndex != null ? row.analysisGridLonIndex : (gridCell && gridCell.lonIndex));
      if (fineLatIndex != null && fineLonIndex != null) {
        mapCell6 = equalAreaMapCell6x12FromIndexes(Math.floor(fineLatIndex / 2), Math.floor(fineLonIndex / 2));
      }
    }
    const mapGrid6Key = mapCell6 ? coordClass + "|" + mapCell6.key : null;

    if (mapped) accumulator.mapped += 1;
    if (coordClass === "source_coordinates") accumulator.sourceCoordinates += 1;
    if (coordClass === "generalized_coordinates") accumulator.generalizedCoordinates += 1;
    if (datePrecision === "exact_day") accumulator.exactDate += 1;
    if (civil) accumulator.dated += 1;
    if (civil && mapped) accumulator.datedAndMapped += 1;
    const sourceCoordinateExactDay = Boolean(civil) && datePrecision === "exact_day" && coordClass === "source_coordinates";
    if (sourceCoordinateExactDay) accumulator.sourceCoordinateExactDay += 1;
    const sameDaySuitability = category(
      row.sameDayMatchStrength != null ? row.sameDayMatchStrength : row.same_day_match_strength,
      "none"
    ).toLowerCase();
    const coordinatePileCount = Math.max(0, finiteNumber(
      row.analysisCoordinatePileCount != null ? row.analysisCoordinatePileCount : row.coordinatePileCount
    ) || 0);
    const duplicateLineage = String(
      row.duplicateLineage != null ? row.duplicateLineage : (row.duplicate_lineage || "")
    ).trim();
    if (
      sourceCoordinateExactDay &&
      !POINT_NEIGHBOR_EXCLUDED_CRAFTS.has(craft.toLowerCase()) &&
      POINT_NEIGHBOR_CRAFT_CONFIDENCE.has(craftConfidence.toLowerCase()) &&
      POINT_NEIGHBOR_SAME_DAY_SUITABILITY.has(sameDaySuitability) &&
      !duplicateLineage &&
      coordinatePileCount < 10
    ) {
      accumulator.pointNeighborhoodEligible += 1;
    }
    if (isKnown(craft)) accumulator.knownCraft += 1;
    if (isKnown(craftConfidence)) accumulator.knownCraftConfidence += 1;
    if (isKnown(shape)) accumulator.knownShape += 1;
    if (!civil) accumulator.missingOrdinal += 1;
    const missingAny = !civil || !mapped || !isKnown(craft) || !isKnown(source);
    if (missingAny) accumulator.rowsMissingAny += 1;

    incrementRaw(accumulator.sources, source, 1);
    incrementRaw(accumulator.types, reportType, 1);
    incrementRaw(accumulator.crafts, craft, 1);
    incrementRaw(accumulator.shapes, shape, 1);
    incrementRaw(accumulator.datePrecisions, datePrecision, 1);
    incrementRaw(accumulator.locationPrecisions, locationPrecision, 1);
    incrementRaw(accumulator.coordinateSources, coordinateSource, 1);
    incrementRaw(accumulator.craftConfidences, craftConfidence, 1);
    incrementRaw(accumulator.craftSources, craftSource, 1);
    incrementRaw(accumulator.mappedStates, mapped ? "mapped" : "unmapped", 1);
    if (missingAny) {
      incrementRaw(accumulator.missingAnyBy.sources, source, 1);
      incrementRaw(accumulator.missingAnyBy.types, reportType, 1);
      incrementRaw(accumulator.missingAnyBy.crafts, craft, 1);
      incrementRaw(accumulator.missingAnyBy.locationPrecisions, locationPrecision, 1);
    }

    const familyValues = {
      craft,
      source,
      date_precision: datePrecision,
      location_precision: locationPrecision,
      coordinate_source: coordinateSource,
      craft_confidence: craftConfidence,
    };
    if (civil) {
      const year = String(civil.year);
      const decade = String(Math.floor(civil.year / 10) * 10);
      analysisDecade = decade;
      const month = String(civil.month).padStart(2, "0");
      const monthYear = year.padStart(4, "0") + "-" + month;
      incrementRaw(accumulator.years, year, 1);
      incrementRaw(accumulator.decades, decade, 1);
      incrementRaw(accumulator.months, month, 1);
      incrementRaw(accumulator.monthYears, monthYear, 1);
      addMatrixCount(accumulator.craftDecades, craft, decade);
      addMatrixCount(accumulator.craftMonths, craft, month);
      addMatrixCount(accumulator.sourceDecades, source, decade);
      addMatrixCount(accumulator.sourceYears, source, year);
      if (missingAny) {
        incrementRaw(accumulator.missingAnyBy.years, year, 1);
        incrementRaw(accumulator.missingAnyBy.decades, decade, 1);
        incrementRaw(accumulator.missingAnyBy.monthYears, monthYear, 1);
        addMatrixCount(accumulator.missingAnyBy.craftDecades, craft, decade);
        addMatrixCount(accumulator.missingAnyBy.craftMonths, craft, month);
        addMatrixCount(accumulator.missingAnyBy.sourceDecades, source, decade);
      }
      familyValues.time_month = month;
      if (analysisGridKey) {
        addMatrixCount(accumulator.gridDecades, analysisGridKey, decade);
        if (missingAny) addMatrixCount(accumulator.missingAnyBy.gridDecades, analysisGridKey, decade);
      }
      if (countryKey) {
        addMatrixCount(accumulator.countryDecades, countryKey, decade);
        const decadeEvidenceKey = countryDecadeKey(countryKey, decade);
        const decadeFacetKey = countryDecadeFacetKey(countryKey, decade);
        incrementRaw(nestedCategoryMap(accumulator.countryDecadeSources, decadeEvidenceKey), source, 1);
        incrementRaw(nestedCategoryMap(accumulator.countryDecadeFacetSourceTotals, decadeFacetKey), source, 1);
        addCountryProvenanceToMap(
          accumulator.countryDecadeProvenance,
          decadeEvidenceKey,
          row,
          countryForRow(row, mapped)
        );
        if (missingAny) addMatrixCount(accumulator.missingAnyBy.countryDecades, countryKey, decade);
      }
    } else {
      familyValues.time_month = "unknown";
      incrementRaw(accumulator.months, "unknown", 1);
    }
    if (analysisGridKey) {
      incrementRaw(accumulator.grid, analysisGridKey, 1);
      if (missingAny) incrementRaw(accumulator.missingAnyBy.grid, analysisGridKey, 1);
      if (!accumulator.gridMetadata.has(analysisGridKey) && gridCell) {
        accumulator.gridMetadata.set(analysisGridKey, Object.assign({}, gridCell, {
          key: analysisGridKey,
          gridKey: gridCell.key,
          coordinateClass: coordClass,
          label: coordClass + " / " + gridCell.key,
        }));
      }
    }
    familyValues.geography = countryKey || "unmapped";
    if (countryKey) {
      if (!accumulator.countryMetadata.has(countryKey)) {
        accumulator.countryMetadata.set(countryKey, countryGeographyMetadata(countryKey));
      }
      addCountryProvenance(accumulator, countryKey, row, countryForRow(row, mapped));
    }
    if (mapGrid6Key) {
      incrementRaw(accumulator.mapGrid6, mapGrid6Key, 1);
      if (!accumulator.mapGrid6Metadata.has(mapGrid6Key)) {
        accumulator.mapGrid6Metadata.set(mapGrid6Key, Object.assign({}, mapCell6, {
          key: mapGrid6Key,
          gridKey: mapCell6.key,
          coordinateClass: coordClass,
          label: coordClass + " / " + mapCell6.key,
        }));
      }
    }
    if (countryKey) incrementRaw(accumulator.patternGeography, countryKey, 1);
    const coarseRegion = coarseRegionForRow(row, mapped, gridCell);
    const stratumValues = {
      source,
      coarse_geography: coarseRegion,
      coordinate_class: coordClass,
      craft,
    };
    const familyStrata = adjustmentStrata(stratumValues);
    if (mapGrid6Key) {
      if (!accumulator.mapGrid6CategoryStrata.has(mapGrid6Key)) {
        accumulator.mapGrid6CategoryStrata.set(mapGrid6Key, new Map());
      }
      incrementRaw(accumulator.mapGrid6CategoryStrata.get(mapGrid6Key), familyStrata.geography, 1);
    }
    incrementRaw(accumulator.regions, coarseRegion, 1);
    addMatrixCount(accumulator.craftRegions, craft, coarseRegion);
    if (missingAny) addMatrixCount(accumulator.missingAnyBy.craftRegions, craft, coarseRegion);
    addMatrixCount(accumulator.craftSourcesMatrix, craft, source);
    addStratifiedMatrixCount(
      accumulator.craftSourceStrataMatrix,
      coarseRegion + "\u001f" + coordClass + "\u001f" + analysisDecade,
      craft,
      source
    );
    if (civil) {
      const month = String(civil.month).padStart(2, "0");
      addStratifiedMatrixCount(
        accumulator.craftMonthStrataMatrix,
        source + "\u001f" + coarseRegion + "\u001f" + coordClass + "\u001f" + analysisDecade,
        craft,
        month
      );
      addStratifiedMatrixCount(
        accumulator.craftEraStrataMatrix,
        source + "\u001f" + coarseRegion + "\u001f" + coordClass,
        craft,
        analysisDecade
      );
      addStratifiedMatrixCount(
        accumulator.craftRegionStrataMatrix,
        source + "\u001f" + analysisDecade + "\u001f" + coordClass,
        craft,
        coarseRegion
      );
      if (countryKey) {
        addStratifiedMatrixCount(
          accumulator.craftCountryStrataMatrix,
          source + "\u001f" + analysisDecade,
          craft,
          countryKey
        );
      }
      addStratifiedMatrixCount(
        accumulator.regionEraStrataMatrix,
        source + "\u001f" + coordClass + "\u001f" + craft,
        coarseRegion,
        analysisDecade
      );
    }
    addMatrixCount(accumulator.craftShapesMatrix, craft, shape);
    addStratifiedMatrixCount(
      accumulator.craftShapeStrataMatrix,
      source + "\u001f" + coarseRegion + "\u001f" + coordClass + "\u001f" + analysisDecade,
      craft,
      shape
    );
    addFamilySourceCount(accumulator, "craft", familyValues.craft, source);
    addFamilySourceCount(accumulator, "time_month", familyValues.time_month, source);
    addFamilySourceCount(accumulator, "geography", familyValues.geography, source);
    addFamilySourceCount(accumulator, "date_precision", familyValues.date_precision, source);
    addFamilySourceCount(accumulator, "location_precision", familyValues.location_precision, source);
    addFamilySourceCount(accumulator, "coordinate_source", familyValues.coordinate_source, source);
    addFamilySourceCount(accumulator, "craft_confidence", familyValues.craft_confidence, source);
    FAMILY_ORDER.forEach(function (family) {
      addFamilyDimensionCount(accumulator.familyByRegion, family, familyValues[family], coarseRegion);
      addFamilyStratumCount(accumulator, family, familyValues[family], familyStrata[family]);
    });
    addGeographyRegionStratumCount(
      accumulator,
      familyValues.geography,
      coarseRegion,
      familyStrata.geography
    );
    addDurationRow(accumulator, row, source, civil);
  }

  // The staged first render needs coverage, time, source, and quality summaries only.
  // Keep this path separate from addRow so the full estimator's strata and gates remain exact.
  function addQuickCoreRow(accumulator, row) {
    accumulator.total += 1;
    const source = category(row.source, "unknown");
    const reportType = category(row.type, "unknown");
    const craft = category(row.craftType, "unknown");
    const shape = category(row.shape, "unknown");
    const datePrecision = category(row.datePrecision, "unknown");
    const locationPrecision = category(row.precision, "unknown");
    const coordinateSource = category(row.coordinateSource, "unknown");
    const craftConfidence = category(row.craftConfidence, "unknown");
    const craftSource = category(row.craftSource, "unknown");
    const mapped = rowMapped(row);
    const coordClass = coordinateClass(row);
    const ordinal = finiteInteger(row.sortOrdinal);
    const derivedYear = finiteInteger(row.analysisYear);
    const derivedMonth = finiteInteger(row.analysisMonth);
    const civil = derivedYear != null && derivedYear >= 1 && derivedMonth != null && derivedMonth >= 1 && derivedMonth <= 12
      ? { year: derivedYear, month: derivedMonth }
      : civilFromOrdinal(ordinal);

    if (mapped) accumulator.mapped += 1;
    if (coordClass === "source_coordinates") accumulator.sourceCoordinates += 1;
    if (coordClass === "generalized_coordinates") accumulator.generalizedCoordinates += 1;
    if (datePrecision === "exact_day") accumulator.exactDate += 1;
    if (civil) accumulator.dated += 1;
    if (civil && mapped) accumulator.datedAndMapped += 1;
    const sourceCoordinateExactDay = Boolean(civil) && datePrecision === "exact_day" && coordClass === "source_coordinates";
    if (sourceCoordinateExactDay) accumulator.sourceCoordinateExactDay += 1;
    const sameDaySuitability = category(
      row.sameDayMatchStrength != null ? row.sameDayMatchStrength : row.same_day_match_strength,
      "none"
    ).toLowerCase();
    const coordinatePileCount = Math.max(0, finiteNumber(
      row.analysisCoordinatePileCount != null ? row.analysisCoordinatePileCount : row.coordinatePileCount
    ) || 0);
    const duplicateLineage = String(
      row.duplicateLineage != null ? row.duplicateLineage : (row.duplicate_lineage || "")
    ).trim();
    if (
      sourceCoordinateExactDay &&
      !POINT_NEIGHBOR_EXCLUDED_CRAFTS.has(craft.toLowerCase()) &&
      POINT_NEIGHBOR_CRAFT_CONFIDENCE.has(craftConfidence.toLowerCase()) &&
      POINT_NEIGHBOR_SAME_DAY_SUITABILITY.has(sameDaySuitability) &&
      !duplicateLineage &&
      coordinatePileCount < 10
    ) {
      accumulator.pointNeighborhoodEligible += 1;
    }
    if (isKnown(craft)) accumulator.knownCraft += 1;
    if (isKnown(craftConfidence)) accumulator.knownCraftConfidence += 1;
    if (isKnown(shape)) accumulator.knownShape += 1;
    if (!civil) accumulator.missingOrdinal += 1;
    const missingAny = !civil || !mapped || !isKnown(craft) || !isKnown(source);
    if (missingAny) accumulator.rowsMissingAny += 1;

    incrementRaw(accumulator.sources, source, 1);
    incrementRaw(accumulator.types, reportType, 1);
    incrementRaw(accumulator.crafts, craft, 1);
    incrementRaw(accumulator.shapes, shape, 1);
    incrementRaw(accumulator.datePrecisions, datePrecision, 1);
    incrementRaw(accumulator.locationPrecisions, locationPrecision, 1);
    incrementRaw(accumulator.coordinateSources, coordinateSource, 1);
    incrementRaw(accumulator.craftConfidences, craftConfidence, 1);
    incrementRaw(accumulator.craftSources, craftSource, 1);
    incrementRaw(accumulator.mappedStates, mapped ? "mapped" : "unmapped", 1);
    addMatrixCount(accumulator.craftShapesMatrix, craft, shape);
    if (missingAny) {
      incrementRaw(accumulator.missingAnyBy.sources, source, 1);
      incrementRaw(accumulator.missingAnyBy.types, reportType, 1);
      incrementRaw(accumulator.missingAnyBy.crafts, craft, 1);
      incrementRaw(accumulator.missingAnyBy.locationPrecisions, locationPrecision, 1);
    }
    addDurationRow(accumulator, row, source, civil);
    if (!civil) {
      incrementRaw(accumulator.months, "unknown", 1);
      return;
    }
    const year = String(civil.year);
    const decade = String(Math.floor(civil.year / 10) * 10);
    const month = String(civil.month).padStart(2, "0");
    const monthYear = year.padStart(4, "0") + "-" + month;
    incrementRaw(accumulator.years, year, 1);
    incrementRaw(accumulator.decades, decade, 1);
    incrementRaw(accumulator.months, month, 1);
    incrementRaw(accumulator.monthYears, monthYear, 1);
    addMatrixCount(accumulator.sourceDecades, source, decade);
    addMatrixCount(accumulator.sourceYears, source, year);
    if (missingAny) {
      incrementRaw(accumulator.missingAnyBy.years, year, 1);
      incrementRaw(accumulator.missingAnyBy.decades, decade, 1);
      incrementRaw(accumulator.missingAnyBy.monthYears, monthYear, 1);
      addMatrixCount(accumulator.missingAnyBy.sourceDecades, source, decade);
    }
  }

  function iterateRows(options, callback) {
    if (typeof options.forEachRow === "function") {
      options.forEachRow(callback);
      return;
    }
    const rows = Array.isArray(options.rows) ? options.rows : [];
    rows.forEach(callback);
  }

  function normalizeRange(startValue, endValue) {
    const start = finiteInteger(startValue);
    const end = finiteInteger(endValue);
    if (start == null || end == null) return null;
    return { start: Math.min(start, end), end: Math.max(start, end) };
  }

  function rowInRange(row, range) {
    if (!range) return true;
    const ordinal = finiteInteger(row && row.sortOrdinal);
    return ordinal != null && ordinal >= range.start && ordinal <= range.end;
  }

  function previousRange(activeRange) {
    if (!activeRange) return null;
    const duration = activeRange.end - activeRange.start + 1;
    return { start: activeRange.start - duration, end: activeRange.start - 1 };
  }

  function baselineDescriptor(mode, activeRange, wholeCorpusStructure) {
    if (wholeCorpusStructure) {
      return {
        mode: BASELINE_MODES.INTERNAL_STRUCTURE,
        requestedMode: mode,
        label: "All records \u2014 internal structure",
        descriptive: false,
        disjoint: true,
        internalStructure: true,
        activeRange: null,
        referenceRange: null,
        comparisonState: COMPARISON_STATES.WHOLE_CORPUS_STRUCTURE,
        warning: "All Time uses within-corpus conditional expectations; no duplicate or fabricated reference cohort is constructed.",
      };
    }
    if (mode === BASELINE_MODES.PREVIOUS_EQUAL_DURATION) {
      return {
        mode,
        label: "Previous equal-duration period",
        descriptive: false,
        disjoint: true,
        activeRange,
        referenceRange: previousRange(activeRange),
        comparisonState: COMPARISON_STATES.INFERENTIAL,
        warning: activeRange ? "" : "A finite active date range is required for this baseline.",
      };
    }
    if (mode === BASELINE_MODES.FULL_CATALOG) {
      return {
        mode,
        label: "Full catalog (descriptive)",
        descriptive: true,
        disjoint: false,
        activeRange,
        referenceRange: null,
        comparisonState: COMPARISON_STATES.DESCRIPTIVE_OVERLAP,
        warning: "The full-catalog reference can overlap the active cohort and can have a different source composition.",
      };
    }
    return {
      mode: BASELINE_MODES.OTHER_DATES_BALANCED,
      label: "Other dates, balanced",
      descriptive: false,
      disjoint: true,
      activeRange,
      referenceRange: null,
      comparisonState: COMPARISON_STATES.INFERENTIAL,
      warning: activeRange ? "" : "A finite active date range is required to construct a disjoint other-dates reference.",
    };
  }

  function membershipForRow(row, options, descriptor) {
    const matchesNonDate = typeof options.matchesNonDateFilters === "function"
      ? Boolean(options.matchesNonDateFilters(row))
      : true;
    const active = matchesNonDate && rowInRange(row, descriptor.activeRange);
    let reference = false;
    if (descriptor.internalStructure) {
      reference = false;
    } else if (descriptor.mode === BASELINE_MODES.FULL_CATALOG) {
      reference = true;
    } else if (descriptor.mode === BASELINE_MODES.PREVIOUS_EQUAL_DURATION) {
      reference = matchesNonDate && Boolean(descriptor.referenceRange) && rowInRange(row, descriptor.referenceRange);
    } else if (descriptor.activeRange) {
      const ordinal = finiteInteger(row && row.sortOrdinal);
      reference = matchesNonDate && ordinal != null && !rowInRange(row, descriptor.activeRange);
    }
    return { active, reference };
  }

  function resolveComparisonState(descriptor, active, reference) {
    if (descriptor && descriptor.internalStructure) return COMPARISON_STATES.WHOLE_CORPUS_STRUCTURE;
    if (!reference || reference.total <= 0) return COMPARISON_STATES.UNAVAILABLE_NO_REFERENCE;
    if (descriptor && descriptor.descriptive && active && active.total === reference.total) {
      return COMPARISON_STATES.UNAVAILABLE_SELF_COMPARISON;
    }
    if (descriptor && descriptor.descriptive) return COMPARISON_STATES.DESCRIPTIVE_OVERLAP;
    return COMPARISON_STATES.INFERENTIAL;
  }

  function countDatum(label, activeCount, referenceCount, activeTotal, referenceTotal, extra) {
    return Object.assign({
      label,
      value: activeCount,
      count: activeCount,
      observed: activeCount,
      reference: referenceCount,
      referenceCount,
      observedShare: round(rate(activeCount, activeTotal), 8),
      referenceShare: round(rate(referenceCount, referenceTotal), 8),
      difference: round(rate(activeCount, activeTotal) - rate(referenceCount, referenceTotal), 8),
    }, extra || {});
  }

  function previewMissingness(missingMap, key, cohortCount) {
    const count = Math.max(0, finiteNumber(cohortCount) || 0);
    const missingCount = Math.max(0, mapCount(missingMap, key));
    return {
      missingCount,
      missingness: round(rate(missingCount, count), 8),
      missingnessUnit: "reports missing any required analysis field within this preview cohort",
    };
  }

  function coverageObject(accumulator) {
    return {
      total: accumulator.total,
      mapped: accumulator.mapped,
      unmapped: accumulator.total - accumulator.mapped,
      sourceCoordinates: accumulator.sourceCoordinates,
      generalizedCoordinates: accumulator.generalizedCoordinates,
      exactDate: accumulator.exactDate,
      nonExactDate: accumulator.total - accumulator.exactDate,
      knownCraft: accumulator.knownCraft,
      unknownCraft: accumulator.total - accumulator.knownCraft,
      knownCraftConfidence: accumulator.knownCraftConfidence,
      unknownCraftConfidence: accumulator.total - accumulator.knownCraftConfidence,
      knownShape: accumulator.knownShape,
      unknownShape: accumulator.total - accumulator.knownShape,
      missingDateOrdinal: accumulator.missingOrdinal,
      missingRequiredAnalysisFields: accumulator.rowsMissingAny,
      dated: accumulator.dated,
      datedAndMapped: accumulator.datedAndMapped,
      sourceCoordinateExactDay: accumulator.sourceCoordinateExactDay,
      pointNeighborhoodEligible: accumulator.pointNeighborhoodEligible,
    };
  }

  function buildEligibilityFunnel(active) {
    const denominator = active.total;
    const stages = [
      {
        id: "matched_active_cohort",
        label: "All matched active reports",
        count: active.total,
        criteria: "Passed the shared date and canonical filters.",
      },
      {
        id: "dated",
        label: "Known report date",
        count: active.dated,
        criteria: "A usable report-date ordinal is present.",
      },
      {
        id: "dated_mapped",
        label: "Dated and mapped",
        count: active.datedAndMapped,
        criteria: "Known report date plus a mapped report marker.",
      },
      {
        id: "source_coordinate_exact_day",
        label: "Source-coordinate, exact-day points",
        count: active.sourceCoordinateExactDay,
        criteria: "Source-provided report marker plus exact-day date precision.",
      },
      {
        id: "point_neighborhood_eligible",
        label: "Point-neighborhood eligible",
        count: active.pointNeighborhoodEligible,
        criteria: "Recognized craft, medium/high craft confidence, medium/strong same-day suitability, no duplicate lineage, and coordinate-pile count below 10.",
      },
    ];
    let previousCount = denominator;
    return stages.map(function (stage, index) {
      const count = Math.min(previousCount, Math.max(0, finiteInteger(stage.count) || 0));
      const result = Object.assign({}, stage, {
        stage: index + 1,
        value: count,
        observed: count,
        count,
        denominator,
        excludedCount: Math.max(0, denominator - count),
        excludedFromPrevious: Math.max(0, previousCount - count),
        shareOfMatched: round(rate(count, denominator), 8),
        unitOfAnalysis: "reports",
        descriptive: true,
      });
      previousCount = count;
      return result;
    });
  }

  function buildCoverage(active, reference) {
    const activeCoverage = coverageObject(active);
    const referenceCoverage = coverageObject(reference);
    const fields = [
      ["Mapped reports", "mapped"],
      ["Unmapped reports", "unmapped"],
      ["Source-provided coordinates", "sourceCoordinates"],
      ["Generalized coordinates", "generalizedCoordinates"],
      ["Exact-day dates", "exactDate"],
      ["Non-exact dates", "nonExactDate"],
      ["Known craft classification", "knownCraft"],
      ["Unknown craft classification", "unknownCraft"],
      ["Known craft confidence", "knownCraftConfidence"],
      ["Known shape", "knownShape"],
    ];
    return {
      active: activeCoverage,
      reference: referenceCoverage,
      eligibilityFunnel: buildEligibilityFunnel(active),
      rows: fields.map(function (field) {
        return countDatum(field[0], activeCoverage[field[1]], referenceCoverage[field[1]], active.total, reference.total, {
          key: field[1],
        });
      }),
    };
  }

  function canonicalDatumPreview(kind, key) {
    if (kind === "craft") return { kind: "filter", patch: { craftTypes: [key] } };
    if (kind === "reportType") return { kind: "filter", patch: { types: [key] } };
    if (kind === "source") return { kind: "filter", patch: { sources: [key] } };
    if (kind === "precision") return { kind: "filter", patch: { precisions: [key] } };
    return null;
  }

  function unionMapDatums(activeMap, referenceMap, activeTotal, referenceTotal, previewKind, activeMissingMap) {
    const keys = new Set([].concat(sortedKeys(activeMap), sortedKeys(referenceMap)));
    return Array.from(keys).map(function (key) {
      const extra = {
        key,
      };
      const preview = canonicalDatumPreview(previewKind, key);
      const activeCount = mapCount(activeMap, key);
      if (preview) {
        extra.preview = preview;
        Object.assign(extra, previewMissingness(activeMissingMap, key, activeCount));
      }
      return countDatum(key, activeCount, mapCount(referenceMap, key), activeTotal, referenceTotal, extra);
    }).sort(function (left, right) {
      return (right.observed - left.observed) || String(left.key).localeCompare(String(right.key));
    });
  }

  function sourceBalancedYearShares(accumulator) {
    const sourceCount = accumulator.sources.size;
    const sums = new Map();
    const represented = new Map();
    if (!sourceCount) return { shares: sums, represented, sourceCount: 0 };
    accumulator.sourceYears.forEach(function (count, composite) {
      const parts = composite.split("\u0000");
      const source = parts[0];
      const year = parts[1];
      const sourceTotal = mapCount(accumulator.sources, source);
      if (sourceTotal <= 0) return;
      sums.set(year, (sums.get(year) || 0) + (count / sourceTotal));
      represented.set(year, (represented.get(year) || 0) + 1);
    });
    sums.forEach(function (sum, year) {
      sums.set(year, sum / sourceCount);
    });
    return { shares: sums, represented, sourceCount };
  }

  function buildSourceBalancedSeries(active, reference) {
    const activeBalanced = sourceBalancedYearShares(active);
    const referenceBalanced = sourceBalancedYearShares(reference);
    const keys = new Set([].concat(sortedKeys(activeBalanced.shares), sortedKeys(referenceBalanced.shares)));
    return Array.from(keys).map(Number).filter(Number.isFinite).sort(function (a, b) { return a - b; }).map(function (year) {
      const key = String(year);
      const observed = mapCount(activeBalanced.shares, key);
      const referenceValue = mapCount(referenceBalanced.shares, key);
      return {
        label: key,
        year,
        value: round(observed, 10),
        observed: round(observed, 10),
        reference: round(referenceValue, 10),
        observedSourcesRepresented: mapCount(activeBalanced.represented, key),
        referenceSourcesRepresented: mapCount(referenceBalanced.represented, key),
        activeSourceDenominator: activeBalanced.sourceCount,
        referenceSourceDenominator: referenceBalanced.sourceCount,
        unit: "mean within-source share",
      };
    });
  }

  function buildExploratoryBursts(accumulator) {
    if (accumulator.total < 200 || !accumulator.years.size) return [];
    const numericYears = sortedKeys(accumulator.years).map(Number).filter(Number.isFinite).sort(function (a, b) { return a - b; });
    if (!numericYears.length) return [];
    const minimumYear = numericYears[0];
    return numericYears.map(function (year) {
      const observed = mapCount(accumulator.years, String(year));
      if (observed < 25 || year - minimumYear < 5) return null;
      let baselineTotal = 0;
      for (let prior = year - 5; prior < year; prior += 1) {
        baselineTotal += mapCount(accumulator.years, String(prior));
      }
      const baselineMean = baselineTotal / 5;
      if (baselineMean < 10) return null;
      const ratioValue = observed / baselineMean;
      const standardizedExcess = (observed - baselineMean) / Math.sqrt(baselineMean);
      if (ratioValue < 1.5 || standardizedExcess < 3) return null;
      return {
        label: String(year),
        year,
        value: observed,
        observed,
        baselineMean: round(baselineMean, 6),
        ratio: round(ratioValue, 6),
        standardizedExcess: round(standardizedExcess, 6),
        baselineWindowYears: 5,
        exploratory: true,
        policyLabel: "Exploratory report-count concentration relative to the preceding five calendar years; not a causal or incidence claim.",
        ...previewMissingness(accumulator.missingAnyBy.years, String(year), observed),
        preview: {
          kind: "filter",
          patch: {
            dateRange: {
              startOrdinal: ordinalFromCivil(year, 1, 1),
              endOrdinal: ordinalFromCivil(year, 12, 31),
            },
          },
        },
      };
    }).filter(Boolean).sort(function (left, right) {
      return (right.standardizedExcess - left.standardizedExcess) || (left.year - right.year);
    });
  }

  function adaptiveTimeDefinition(yearsValue, active, reference) {
    const years = Array.isArray(yearsValue) ? yearsValue.filter(Number.isFinite).slice().sort(function (a, b) { return a - b; }) : [];
    if (!years.length) {
      return {
        unit: "year",
        widthYears: 1,
        spanYears: 0,
        startYear: null,
        endYear: null,
        densityReportsPerYear: 0,
        binCount: 0,
        policy: "No dated reports are available for adaptive binning.",
      };
    }
    const startYear = years[0];
    const endYear = years[years.length - 1];
    const spanYears = Math.max(1, endYear - startYear + 1);
    const densityReportsPerYear = (active.dated + reference.dated) / spanYears;
    let widthYears = 10;
    if (spanYears <= 40 || (spanYears <= 80 && densityReportsPerYear >= 0.25)) {
      widthYears = 1;
    } else if (spanYears <= 300 && densityReportsPerYear >= 0.10) {
      widthYears = 5;
    }
    const firstBinStart = Math.floor(startYear / widthYears) * widthYears;
    const lastBinStart = Math.floor(endYear / widthYears) * widthYears;
    return {
      unit: widthYears === 1 ? "year" : (widthYears === 10 ? "decade" : "multi_year"),
      widthYears,
      spanYears,
      startYear,
      endYear,
      firstBinStart,
      lastBinStart,
      densityReportsPerYear: round(densityReportsPerYear, 8),
      binCount: Math.floor((lastBinStart - firstBinStart) / widthYears) + 1,
      policy: "Deterministic bins use one year for compact or sufficiently dense spans, five years for supported medium spans, and decades for long or sparse spans; every dated report remains in exactly one bin.",
    };
  }

  function adaptiveBinLabel(startYear, widthYears) {
    if (widthYears === 1) return String(startYear);
    if (widthYears === 10 && startYear % 10 === 0) return String(startYear) + "s";
    return String(startYear) + "\u2013" + String(startYear + widthYears - 1);
  }

  function buildAdaptiveCountSeries(active, reference, definition) {
    if (!definition || definition.startYear == null) return [];
    const activeBins = new Map();
    const referenceBins = new Map();
    const activeMissingBins = new Map();
    function aggregate(yearMap, target) {
      yearMap.forEach(function (count, yearKey) {
        const year = Number(yearKey);
        if (!Number.isFinite(year)) return;
        const binStart = Math.floor(year / definition.widthYears) * definition.widthYears;
        incrementRaw(target, binStart, count);
      });
    }
    aggregate(active.years, activeBins);
    aggregate(reference.years, referenceBins);
    aggregate(active.missingAnyBy.years, activeMissingBins);
    const result = [];
    for (let binStart = definition.firstBinStart; binStart <= definition.lastBinStart; binStart += definition.widthYears) {
      const activeCount = mapCount(activeBins, binStart);
      const referenceCount = mapCount(referenceBins, binStart);
      if (activeCount <= 0 && referenceCount <= 0) continue;
      const endYear = binStart + definition.widthYears - 1;
      const label = adaptiveBinLabel(binStart, definition.widthYears);
      const previewStart = ordinalFromCivil(binStart, 1, 1);
      const previewEnd = ordinalFromCivil(endYear, 12, 31);
      const extra = {
        key: String(binStart),
        period: label,
        year: definition.widthYears === 1 ? binStart : undefined,
        startYear: binStart,
        endYear,
        binWidthYears: definition.widthYears,
        binUnit: definition.unit,
      };
      if (previewStart != null && previewEnd != null) {
        extra.preview = {
          kind: "filter",
          patch: { dateRange: { startOrdinal: previewStart, endOrdinal: previewEnd } },
        };
      }
      Object.assign(extra, {
        missingCount: mapCount(activeMissingBins, binStart),
        missingness: round(rate(mapCount(activeMissingBins, binStart), activeCount), 8),
        missingnessUnit: "reports missing any required analysis field within this adaptive time bin",
      });
      result.push(countDatum(
        label,
        activeCount,
        referenceCount,
        active.total,
        reference.total,
        extra
      ));
    }
    return result;
  }

  function buildAdaptiveSourceBalancedSeries(active, reference, definition) {
    if (!definition || definition.startYear == null) return [];
    function aggregate(accumulator) {
      const sums = new Map();
      const represented = new Map();
      const sourceCount = accumulator.sources.size;
      accumulator.sourceYears.forEach(function (count, composite) {
        const parts = composite.split("\u0000");
        const source = parts[0];
        const year = Number(parts[1]);
        if (!Number.isFinite(year)) return;
        const sourceTotal = mapCount(accumulator.sources, source);
        if (sourceTotal <= 0) return;
        const binStart = Math.floor(year / definition.widthYears) * definition.widthYears;
        sums.set(binStart, (sums.get(binStart) || 0) + (count / sourceTotal));
        if (!represented.has(binStart)) represented.set(binStart, new Set());
        represented.get(binStart).add(source);
      });
      sums.forEach(function (sum, binStart) {
        sums.set(binStart, sourceCount > 0 ? sum / sourceCount : 0);
      });
      return { sums, represented, sourceCount };
    }
    const activeBins = aggregate(active);
    const referenceBins = aggregate(reference);
    const result = [];
    for (let binStart = definition.firstBinStart; binStart <= definition.lastBinStart; binStart += definition.widthYears) {
      const activeValue = mapCount(activeBins.sums, binStart);
      const referenceValue = mapCount(referenceBins.sums, binStart);
      if (activeValue <= 0 && referenceValue <= 0) continue;
      const label = adaptiveBinLabel(binStart, definition.widthYears);
      result.push({
        label,
        period: label,
        year: definition.widthYears === 1 ? binStart : undefined,
        startYear: binStart,
        endYear: binStart + definition.widthYears - 1,
        binWidthYears: definition.widthYears,
        binUnit: definition.unit,
        value: round(activeValue, 10),
        observed: round(activeValue, 10),
        reference: round(referenceValue, 10),
        observedSourcesRepresented: activeBins.represented.has(binStart) ? activeBins.represented.get(binStart).size : 0,
        referenceSourcesRepresented: referenceBins.represented.has(binStart) ? referenceBins.represented.get(binStart).size : 0,
        activeSourceDenominator: activeBins.sourceCount,
        referenceSourceDenominator: referenceBins.sourceCount,
        unit: "mean within-source share",
      });
    }
    return result;
  }

  function deferredAssociation(associationLabel, covariates) {
    return {
      cells: [],
      fullCells: [],
      metadata: {
        eligible: false,
        status: "deferred",
        inferenceDeferred: true,
        associationLabel: associationLabel || "association",
        adjustmentCovariates: Array.isArray(covariates) ? covariates.slice() : [],
        suppressionReasons: ["quick_core_inference_deferred"],
        policyWarning: "Inferential association estimates are deferred until the full evidence computation completes.",
      },
    };
  }

  function buildTime(active, reference, optionsValue) {
    const options = optionsValue || {};
    const yearKeys = new Set([].concat(sortedKeys(active.years), sortedKeys(reference.years)));
    const years = Array.from(yearKeys).map(Number).filter(Number.isFinite).sort(function (a, b) { return a - b; });
    const annualSeries = years.map(function (year) {
      const key = String(year);
      const activeCount = mapCount(active.years, key);
      return countDatum(key, activeCount, mapCount(reference.years, key), active.total, reference.total, Object.assign({
        year,
        preview: {
          kind: "filter",
          patch: {
            dateRange: {
              startOrdinal: ordinalFromCivil(year, 1, 1),
              endOrdinal: ordinalFromCivil(year, 12, 31),
            },
          },
        },
      }, previewMissingness(active.missingAnyBy.years, key, activeCount)));
    });
    const adaptiveBinning = adaptiveTimeDefinition(years, active, reference);
    const series = buildAdaptiveCountSeries(active, reference, adaptiveBinning);
    adaptiveBinning.possibleBinCount = adaptiveBinning.binCount;
    adaptiveBinning.occupiedBinCount = series.length;
    adaptiveBinning.structurallyEmptyBinsOmitted = Math.max(0, adaptiveBinning.binCount - series.length);
    const seriesByStartYear = new Map(series.map(function (datum) { return [datum.startYear, datum]; }));
    const rolling = series.map(function (datum) {
      const startYear = Math.max(adaptiveBinning.firstBinStart, datum.startYear - (4 * adaptiveBinning.widthYears));
      let observed = 0;
      let referenceCount = 0;
      for (let cursor = startYear; cursor <= datum.startYear; cursor += adaptiveBinning.widthYears) {
        const bin = seriesByStartYear.get(cursor);
        if (!bin) continue;
        observed += bin.observed;
        referenceCount += bin.referenceCount;
      }
      return {
        label: datum.label,
        year: datum.year,
        startYear: datum.startYear,
        endYear: datum.endYear,
        observed,
        value: observed,
        reference: referenceCount,
        referenceCount,
        windowYears: datum.startYear - startYear + adaptiveBinning.widthYears,
      };
    });
    const monthYearKeys = new Set([].concat(sortedKeys(active.monthYears), sortedKeys(reference.monthYears)));
    const monthYear = Array.from(monthYearKeys).sort().map(function (key) {
      const parts = key.split("-");
      const year = Number(parts[0]);
      const month = Number(parts[1]);
      const nextYear = month === 12 ? year + 1 : year;
      const nextMonth = month === 12 ? 1 : month + 1;
      const startOrdinal = ordinalFromCivil(year, month, 1);
      const nextOrdinal = ordinalFromCivil(nextYear, nextMonth, 1);
      const activeCount = mapCount(active.monthYears, key);
      return countDatum(key, activeCount, mapCount(reference.monthYears, key), active.total, reference.total, Object.assign({
        row: year,
        column: month,
        year,
        month,
        preview: {
          kind: "filter",
          patch: { dateRange: { startOrdinal, endOrdinal: nextOrdinal == null ? null : nextOrdinal - 1 } },
        },
      }, previewMissingness(active.missingAnyBy.monthYears, key, activeCount)));
    });
    const decadeKeys = new Set([].concat(sortedKeys(active.decades), sortedKeys(reference.decades)));
    const decades = Array.from(decadeKeys).map(Number).filter(Number.isFinite).sort(function (a, b) { return a - b; }).map(function (decade) {
      const key = String(decade);
      const activeCount = mapCount(active.decades, key);
      return countDatum(decade + "s", activeCount, mapCount(reference.decades, key), active.total, reference.total, Object.assign({
        decade,
        preview: {
          kind: "filter",
          patch: {
            dateRange: {
              startOrdinal: ordinalFromCivil(decade, 1, 1),
              endOrdinal: ordinalFromCivil(decade + 9, 12, 31),
            },
          },
        },
      }, previewMissingness(active.missingAnyBy.decades, key, activeCount)));
    });
    const monthByCraft = options.inferenceDeferred
      ? deferredAssociation("recurring month-by-craft", ["source", "coarse_geography", "coordinate_class", "era"])
      : adjustedStandardizedResiduals(active.craftMonthStrataMatrix, {
        maximumRows: 12,
        maximumColumns: 12,
        covariates: ["source", "coarse_geography", "coordinate_class", "era"],
        associationLabel: "recurring month-by-craft",
        comparisonState: options.comparisonState,
        rowAxisType: "category",
        columnAxisType: "month",
      });
    if (!options.inferenceDeferred) {
      decorateAssociationResult(monthByCraft, active.total, function (cell) {
        const craft = cell.row;
        return {
          kind: "filter",
          patch: { craftTypes: [craft] },
          comparison: "Recurring calendar-month association for " + craft + "; applying the preview changes only the available craft filter.",
        };
      });
    }
    return {
      series,
      annualSeries,
      adaptiveBinning,
      axisMetadata: {
        annual: semanticAxisMetadata(annualSeries.map(function (datum) { return datum.year; }), "year"),
        adaptive: semanticAxisMetadata(series.map(function (datum) { return datum.startYear; }), "year"),
        monthYear: {
          type: "year_month",
          order: monthYear.map(function (datum) { return datum.label; }),
          direction: "ascending",
          orderedBeforeSampling: true,
        },
        decades: semanticAxisMetadata(decades.map(function (datum) { return datum.decade; }), "decade"),
        months: semanticAxisMetadata(MONTH_AXIS_ORDER, "month"),
      },
      decades,
      monthYear,
      monthByCraft,
      rolling,
      sourceBalanced: buildAdaptiveSourceBalancedSeries(active, reference, adaptiveBinning),
      annualSourceBalanced: buildSourceBalancedSeries(active, reference),
      bursts: buildExploratoryBursts(active),
      sourceBalancedPolicy: "Each source contributes equal total weight through its within-source adaptive-period shares.",
      burstPolicy: "A burst requires active N >= 200, year N >= 25, preceding-five-year mean >= 10, ratio >= 1.5, and standardized excess >= 3.",
    };
  }

  function coarseAreaPreview(regionValue) {
    const match = /^ea6x12:(\d+):(\d+)$/.exec(String(regionValue || ""));
    if (!match) return null;
    const cell = equalAreaMapCell6x12FromIndexes(Number(match[1]), Number(match[2]));
    if (!cell) return null;
    return {
      kind: "area",
      area: {
        bounds: {
          south: cell.latMinimum,
          west: cell.lonMinimum,
          north: cell.latMaximum,
          east: cell.lonMaximum,
        },
      },
    };
  }

  function decorateAssociationResult(result, activeTotal, previewBuilder) {
    const association = result || {};
    const allCells = Array.isArray(association.fullCells) ? association.fullCells : [];
    allCells.forEach(function (cell) {
      cell.activeCount = cell.observed;
      cell.expectedCount = round(cell.expectedCount != null ? cell.expectedCount : cell.expected, 6);
      cell.adjustedResidual = cell.standardizedResidual;
      cell.unitOfAnalysis = "reports";
      cell.activeN = Number(activeTotal) || 0;
      if (typeof previewBuilder === "function") {
        const preview = previewBuilder(cell);
        if (preview) cell.preview = preview;
      }
    });
    const rowAxisType = association.metadata && association.metadata.rowAxis && association.metadata.rowAxis.type;
    const columnAxisType = association.metadata && association.metadata.columnAxis && association.metadata.columnAxis.type;
    association.cells = allCells.filter(function (cell) { return cell.estimateAvailable; }).sort(function (left, right) {
      return semanticAxisCompare(left.row, right.row, rowAxisType) || semanticAxisCompare(left.column, right.column, columnAxisType);
    });
    association.metadata = Object.assign({}, association.metadata || {}, {
      activeN: Number(activeTotal) || 0,
      expectedCountLabel: "conditional expected count",
      comparisonCountKind: "conditional_expectation",
      status: association.metadata && association.metadata.status || "not_estimable",
    });
    return association;
  }

  function matrixCells(matrix, rowLimit, columnLimit) {
    const rowTotals = new Map();
    const columnTotals = new Map();
    matrix.forEach(function (count, composite) {
      const parts = composite.split("\u0000");
      increment(rowTotals, parts[0], count);
      increment(columnTotals, parts[1], count);
    });
    const rows = new Set(mapEntriesByCount(rowTotals).slice(0, rowLimit || 12).map(function (entry) { return entry[0]; }));
    const columns = new Set(mapEntriesByCount(columnTotals).slice(0, columnLimit || 12).map(function (entry) { return entry[0]; }));
    const total = Array.from(matrix.values()).reduce(function (sum, count) { return sum + count; }, 0);
    const result = [];
    rows.forEach(function (row) {
      columns.forEach(function (column) {
        const count = mapCount(matrix, row + "\u0000" + column);
        const expected = total > 0 ? (mapCount(rowTotals, row) * mapCount(columnTotals, column)) / total : 0;
        result.push({
          key: row + "\u0000" + column,
          label: row + " / " + column,
          row,
          column,
          value: expected > 0 ? round((count - expected) / Math.sqrt(expected), 6) : 0,
          count,
          observed: count,
          observedCount: count,
          expected: round(expected, 6),
          expectedCount: round(expected, 6),
          conditionalExpectedCount: round(expected, 6),
          standardizedResidual: expected > 0 ? round((count - expected) / Math.sqrt(expected), 6) : 0,
          estimateAvailable: expected > 0 || count > 0,
          tested: false,
          inferenceEligible: false,
          displayStatus: expected > 0 || count > 0 ? "descriptive" : "structurally_empty",
          displayEligible: expected > 0 || count > 0,
          suppressionReasons: ["inference_deferred"],
          pValue: null,
          qValue: null,
        });
      });
    });
    return result.sort(function (left, right) {
      return String(left.row).localeCompare(String(right.row)) || String(left.column).localeCompare(String(right.column));
    });
  }

  function craftSourceAssociation(matrix, rowLimit, columnLimit) {
    const rowTotalsAll = new Map();
    const columnTotalsAll = new Map();
    let totalReportCount = 0;
    matrix.forEach(function (count, composite) {
      const parts = composite.split("\u0000");
      increment(rowTotalsAll, parts[0], count);
      increment(columnTotalsAll, parts[1], count);
      totalReportCount += count;
    });
    const rows = mapEntriesByCount(rowTotalsAll).slice(0, rowLimit || 12).map(function (entry) {
      return entry[0];
    }).sort();
    const columns = mapEntriesByCount(columnTotalsAll).slice(0, columnLimit || 12).map(function (entry) {
      return entry[0];
    }).sort();
    const rowSet = new Set(rows);
    const columnSet = new Set(columns);
    const selectedCounts = new Map();
    const selectedRowTotals = new Map();
    const selectedColumnTotals = new Map();
    let includedReportCount = 0;
    matrix.forEach(function (count, composite) {
      const parts = composite.split("\u0000");
      if (!rowSet.has(parts[0]) || !columnSet.has(parts[1])) return;
      selectedCounts.set(composite, count);
      increment(selectedRowTotals, parts[0], count);
      increment(selectedColumnTotals, parts[1], count);
      includedReportCount += count;
    });

    const cells = [];
    let chiSquared = 0;
    let minimumExpectedCell = Infinity;
    rows.forEach(function (row) {
      columns.forEach(function (column) {
        const observed = mapCount(selectedCounts, row + "\u0000" + column);
        const expected = includedReportCount > 0
          ? (mapCount(selectedRowTotals, row) * mapCount(selectedColumnTotals, column)) / includedReportCount
          : 0;
        minimumExpectedCell = Math.min(minimumExpectedCell, expected);
        if (expected > 0) chiSquared += Math.pow(observed - expected, 2) / expected;
        cells.push({
          label: row + " / " + column,
          row,
          column,
          value: observed,
          count: observed,
          observed,
          expected: round(expected, 6),
          standardizedResidual: expected > 0 ? round((observed - expected) / Math.sqrt(expected), 6) : 0,
        });
      });
    });
    if (!cells.length || !Number.isFinite(minimumExpectedCell)) minimumExpectedCell = 0;
    const dimension = Math.min(Math.max(0, rows.length - 1), Math.max(0, columns.length - 1));
    const cramersV = includedReportCount > 0 && dimension > 0
      ? Math.sqrt(chiSquared / (includedReportCount * dimension))
      : 0;
    const eligible = rows.length >= 2 && columns.length >= 2 &&
      minimumExpectedCell >= 10 && cramersV >= 0.10;
    const policyWarning = "Descriptive craft-by-source association for the displayed top-frequency table. Residual cells are emitted only when every expected cell is at least 10 and table-level Cramer's V is at least 0.10; this is not evidence of craft identity or cause.";
    return {
      cells: eligible ? cells : [],
      metadata: {
        eligible,
        status: eligible ? "eligible" : "suppressed",
        cramersV: round(cramersV, 8),
        minimumExpectedCell: round(minimumExpectedCell, 6),
        chiSquared: round(chiSquared, 8),
        degreesOfFreedom: Math.max(0, rows.length - 1) * Math.max(0, columns.length - 1),
        rowCount: rows.length,
        columnCount: columns.length,
        rows,
        columns,
        includedReportCount,
        excludedReportCount: Math.max(0, totalReportCount - includedReportCount),
        totalReportCount,
        thresholds: {
          minimumExpectedCell: 10,
          minimumCramersV: 0.10,
        },
        policyWarning,
      },
    };
  }

  function pairedMatrixCells(activeMatrix, referenceMatrix, rowLimit, columnLimit) {
    const rowTotals = new Map();
    const columnTotals = new Map();
    const keys = new Set();
    [activeMatrix, referenceMatrix].forEach(function (matrix) {
      matrix.forEach(function (count, composite) {
        keys.add(composite);
        const parts = composite.split("\u0000");
        incrementRaw(rowTotals, parts[0], count);
        incrementRaw(columnTotals, parts[1], count);
      });
    });
    const rows = new Set(mapEntriesByCount(rowTotals).slice(0, rowLimit || 12).map(function (entry) { return entry[0]; }));
    const columns = new Set(mapEntriesByCount(columnTotals).slice(0, columnLimit || 12).map(function (entry) { return entry[0]; }));
    return Array.from(keys).map(function (composite) {
      const parts = composite.split("\u0000");
      const row = parts[0];
      const column = parts[1];
      if (!rows.has(row) || !columns.has(column)) return null;
      const activeCount = mapCount(activeMatrix, composite);
      const referenceCount = mapCount(referenceMatrix, composite);
      return {
        key: composite,
        label: row + " / " + column,
        row,
        column,
        value: activeCount,
        count: activeCount,
        absoluteCount: activeCount,
        activeCount,
        observed: activeCount,
        reference: referenceCount,
        referenceCount,
        referenceAbsoluteCount: referenceCount,
      };
    }).filter(Boolean).sort(function (left, right) {
      return String(left.row).localeCompare(String(right.row)) || String(left.column).localeCompare(String(right.column));
    });
  }

  function craftTrendSeries(active, reference) {
    const cells = pairedMatrixCells(active.craftDecades, reference.craftDecades, 12, 30);
    const byCraft = new Map();
    cells.forEach(function (cell) {
      if (!byCraft.has(cell.row)) byCraft.set(cell.row, []);
      byCraft.get(cell.row).push(cell);
    });
    const series = [];
    sortedKeys(byCraft).forEach(function (craft) {
      const craftCells = byCraft.get(craft).slice().sort(function (left, right) {
        return semanticAxisCompare(left.column, right.column, "decade");
      });
      ["active", "reference"].forEach(function (cohort) {
        const seriesKey = cohort + "\u0000" + craft;
        series.push({
          key: seriesKey,
          seriesKey,
          craft,
          cohort,
          label: (cohort === "reference" ? "Reference - " : "Active - ") + craft,
          points: craftCells.map(function (cell) {
            const count = cohort === "reference" ? cell.referenceCount : cell.activeCount;
            const decade = finiteInteger(cell.column);
            const point = {
              key: seriesKey + "\u0000" + cell.column,
              label: cell.column,
              row: craft,
              column: cell.column,
              craft,
              cohort,
              series: seriesKey,
              seriesKey,
              decade,
              value: count,
              count,
              observed: count,
              activeCount: cell.activeCount,
              referenceCount: cell.referenceCount,
              absoluteCount: count,
              preview: cohort !== "active" || decade == null ? null : {
                kind: "filter",
                patch: {
                  craftTypes: [craft],
                  dateRange: {
                    startOrdinal: ordinalFromCivil(decade, 1, 1),
                    endOrdinal: ordinalFromCivil(decade + 9, 12, 31),
                  },
                },
              },
            };
            if (cohort === "active" && point.preview) {
              Object.assign(
                point,
                previewMissingness(active.missingAnyBy.craftDecades, cell.row + "\u0000" + cell.column, cell.activeCount)
              );
            }
            return point;
          }),
        });
      });
    });
    return series;
  }

  function buildCraft(active, reference, optionsValue) {
    const options = optionsValue || {};
    const sourceAssociation = options.inferenceDeferred ? deferredAssociation(
      "craft-by-source",
      ["coarse_geography", "coordinate_class", "era"]
    ) : adjustedStandardizedResiduals(active.craftSourceStrataMatrix, {
      maximumRows: 12,
      maximumColumns: 12,
      covariates: ["coarse_geography", "coordinate_class", "era"],
      associationLabel: "craft-by-source",
      comparisonState: options.comparisonState,
      rowAxisType: "category",
      columnAxisType: "category",
    });
    if (!options.inferenceDeferred) {
      decorateAssociationResult(sourceAssociation, active.total, function (cell) {
        return { kind: "filter", patch: { craftTypes: [cell.row], sources: [cell.column] } };
      });
    }
    const byEra = options.inferenceDeferred ? deferredAssociation(
      "craft-by-era",
      ["source", "coarse_geography", "coordinate_class"]
    ) : adjustedStandardizedResiduals(active.craftEraStrataMatrix, {
      maximumRows: 12,
      maximumColumns: 12,
      covariates: ["source", "coarse_geography", "coordinate_class"],
      associationLabel: "craft-by-era",
      comparisonState: options.comparisonState,
      rowAxisType: "category",
      columnAxisType: "decade",
    });
    if (!options.inferenceDeferred) {
      decorateAssociationResult(byEra, active.total, function (cell) {
        const decade = finiteInteger(cell.column);
        if (decade == null) return { kind: "filter", patch: { craftTypes: [cell.row] } };
        return {
          kind: "filter",
          patch: {
            craftTypes: [cell.row],
            dateRange: {
              startOrdinal: ordinalFromCivil(decade, 1, 1),
              endOrdinal: ordinalFromCivil(decade + 9, 12, 31),
            },
          },
        };
      });
    }
    const byGeography = options.inferenceDeferred ? deferredAssociation(
      "craft-by-geography",
      ["source", "era", "coordinate_class"]
    ) : adjustedStandardizedResiduals(active.craftRegionStrataMatrix, {
      maximumRows: 12,
      maximumColumns: 12,
      covariates: ["source", "era", "coordinate_class"],
      associationLabel: "craft-by-geography",
      comparisonState: options.comparisonState,
      rowAxisType: "category",
      columnAxisType: "geography",
    });
    if (!options.inferenceDeferred) {
      decorateAssociationResult(byGeography, active.total, function (cell) {
        return coarseAreaPreview(cell.column) || { kind: "filter", patch: { craftTypes: [cell.row] } };
      });
    }
    return {
      distribution: unionMapDatums(active.crafts, reference.crafts, active.total, reference.total, "craft", active.missingAnyBy.crafts),
      reportTypes: unionMapDatums(active.types, reference.types, active.total, reference.total, "reportType", active.missingAnyBy.types),
      confidence: unionMapDatums(active.craftConfidences, reference.craftConfidences, active.total, reference.total, "craftConfidence"),
      source: unionMapDatums(active.craftSources, reference.craftSources, active.total, reference.total, "craftSource"),
      trends: craftTrendSeries(active, reference),
      byEra,
      byGeography,
      residuals: sourceAssociation.cells,
      residualAudit: sourceAssociation.fullCells,
      sourceAssociation: sourceAssociation.metadata,
      axisMetadata: {
        trends: semanticAxisMetadata(new Set([].concat(
          sortedKeys(active.decades),
          sortedKeys(reference.decades)
        )), "decade"),
        byEra: byEra.metadata && byEra.metadata.columnAxis,
        byGeography: byGeography.metadata && byGeography.metadata.columnAxis,
      },
    };
  }

  function geographyDatumMetadata(active, reference, key) {
    const metadata = active.gridMetadata.get(key) || reference.gridMetadata.get(key) || {};
    const coordinateClass = metadata.coordinateClass || String(key).split("|")[0] || "mapped_mixed_precision";
    const bounds = {
      south: metadata.latMinimum,
      west: metadata.lonMinimum,
      north: metadata.latMaximum,
      east: metadata.lonMaximum,
    };
    const gridMetadata = {
      definitionId: "sin_latitude_12_by_longitude_24_v1",
      key: metadata.gridKey || metadata.key || key,
      analysisKey: key,
      latIndex: metadata.latIndex,
      lonIndex: metadata.lonIndex,
      coordinateClass,
      bounds,
    };
    return Object.assign({}, metadata, {
      coordinateClass,
      bounds,
      gridMetadata,
      preview: { kind: "area", area: { bounds } },
    });
  }

  function sourceBalancedCountryShares(accumulator) {
    const sourceTotals = new Map();
    const byCountry = new Map();
    (accumulator.familyStrataTotals.geography || new Map()).forEach(function (count, stratum) {
      const source = String(stratum).split("\u001f")[0] || "unknown";
      incrementRaw(sourceTotals, source, count);
    });
    (accumulator.familyCategoryStrata.geography || new Map()).forEach(function (strataCounts, key) {
      const sourceCounts = new Map();
      strataCounts.forEach(function (count, stratum) {
        const source = String(stratum).split("\u001f")[0] || "unknown";
        incrementRaw(sourceCounts, source, count);
      });
      byCountry.set(key, sourceCounts);
    });
    const sources = sortedKeys(sourceTotals).filter(function (source) {
      return mapCount(sourceTotals, source) > 0;
    });
    const result = new Map();
    byCountry.forEach(function (sourceCounts, key) {
      const share = sources.reduce(function (sum, source) {
        return sum + rate(mapCount(sourceCounts, source), mapCount(sourceTotals, source));
      }, 0);
      result.set(key, sources.length ? share / sources.length : 0);
    });
    return { shares: result, sourceCount: sources.length };
  }

  function buildGeography(active, reference, optionsValue) {
    const options = optionsValue || {};
    const wholeCorpus = options.comparisonState === COMPARISON_STATES.WHOLE_CORPUS_STRUCTURE;
    const sourceBalanced = sourceBalancedCountryShares(active);
    const keys = new Set([].concat(sortedKeys(active.patternGeography), sortedKeys(reference.patternGeography)));
    const cells = Array.from(keys).map(function (key) {
      const metadata = active.countryMetadata.get(key) || reference.countryMetadata.get(key) || countryGeographyMetadata(key);
      const activeCount = mapCount(active.patternGeography, key);
      const datum = countDatum(metadata.label || metadata.country, activeCount, mapCount(reference.patternGeography, key), active.total, reference.total, Object.assign({}, metadata, {
        key,
        geographyKind: "country",
        preview: metadata.country === "Unknown country" || metadata.country === "Unmapped"
          ? null
          : { kind: "area", area: { type: "country", country: metadata.country } },
      }));
      datum.sourceBalancedReportShare = round(mapCount(sourceBalanced.shares, key), 10);
      datum.sourceBalancedShare = datum.sourceBalancedReportShare;
      datum.sourceBalancedSourceN = sourceBalanced.sourceCount;
      datum.reportShare = round(rate(activeCount, active.mapped), 10);
      datum.logCount = activeCount > 0 ? round(Math.log2(activeCount + 1), 8) : 0;
      Object.assign(datum, countryEvidenceMetadata(active, reference, key));
      return datum;
    }).sort(function (left, right) {
      return (right.observed - left.observed) || String(left.key).localeCompare(String(right.key));
    });
    const byTime = pairedMatrixCells(active.countryDecades, reference.countryDecades, Number.MAX_SAFE_INTEGER, 30).map(function (cell) {
      const metadata = active.countryMetadata.get(cell.row) || reference.countryMetadata.get(cell.row) || countryGeographyMetadata(cell.row);
      const activeBalanced = sourceBalancedCountryDecadeShare(active, cell.row, cell.column);
      const referenceBalanced = wholeCorpus ? null : sourceBalancedCountryDecadeShare(reference, cell.row, cell.column);
      const activeShare = rate(cell.activeCount, activeBalanced.facetTotal);
      const referenceShare = referenceBalanced ? rate(cell.referenceCount, referenceBalanced.facetTotal) : null;
      const adjustedDifference = referenceBalanced ? activeBalanced.share - referenceBalanced.share : null;
      const log2Enrichment = referenceBalanced && activeBalanced.facetTotal > 0 && referenceBalanced.facetTotal > 0
        ? Math.log2(
          ((cell.activeCount + 0.5) / (activeBalanced.facetTotal + 1)) /
          ((cell.referenceCount + 0.5) / (referenceBalanced.facetTotal + 1))
        )
        : null;
      return Object.assign({}, cell, wholeCorpus ? {
        reference: null,
        referenceCount: null,
        referenceAbsoluteCount: null,
      } : {}, metadata, countryDecadeEvidenceMetadata(active, reference, cell.row, cell.column), {
        key: cell.row + "\u0000" + cell.column,
        row: cell.row,
        column: cell.column,
        period: cell.column,
        label: metadata.country + " / " + cell.column,
        displayRow: metadata.country,
        reportShare: round(activeShare, 10),
        referenceReportShare: referenceShare == null ? null : round(referenceShare, 10),
        sourceBalancedReportShare: round(activeBalanced.share, 10),
        sourceBalancedShare: round(activeBalanced.share, 10),
        referenceSourceBalancedReportShare: referenceBalanced ? round(referenceBalanced.share, 10) : null,
        adjustedDifference: adjustedDifference == null ? null : round(adjustedDifference, 10),
        difference: adjustedDifference == null ? null : round(adjustedDifference, 10),
        log2Enrichment: log2Enrichment == null ? null : round(log2Enrichment, 8),
        sourceBalancedSourceN: activeBalanced.sourceCount,
        referenceSourceBalancedSourceN: referenceBalanced ? referenceBalanced.sourceCount : null,
        decadeFacetActiveN: activeBalanced.facetTotal,
        decadeFacetReferenceN: referenceBalanced ? referenceBalanced.facetTotal : null,
        comparisonState: options.comparisonState,
        estimateAvailable: cell.activeCount > 0 || (!wholeCorpus && cell.referenceCount > 0),
        inferenceEligible: false,
        preview: metadata.country === "Unknown country" || metadata.country === "Unmapped" ? null : {
          kind: "area",
          area: { type: "country", country: metadata.country },
          cohortSize: cell.activeCount,
          comparison: wholeCorpus
            ? cell.activeCount + " reports assigned to " + metadata.country + " during the " + cell.column + "s"
            : cell.activeCount + " active vs. " + cell.referenceCount + " reference reports assigned to " + metadata.country + " during the " + cell.column + "s",
        },
      });
    }).sort(function (left, right) {
      return String(left.country).localeCompare(String(right.country)) || semanticAxisCompare(left.period, right.period, "decade");
    });
    const byEra = options.inferenceDeferred ? deferredAssociation(
      "geography-by-era",
      ["source", "coordinate_class", "craft"]
    ) : adjustedStandardizedResiduals(active.regionEraStrataMatrix, {
      maximumRows: 12,
      maximumColumns: 12,
      covariates: ["source", "coordinate_class", "craft"],
      associationLabel: "geography-by-era",
      comparisonState: options.comparisonState,
      rowAxisType: "geography",
      columnAxisType: "decade",
    });
    if (!options.inferenceDeferred) {
      decorateAssociationResult(byEra, active.total, function (cell) {
        const decade = finiteInteger(cell.column);
        return {
          kind: "filter",
          patch: decade == null ? {} : {
            dateRange: {
              startOrdinal: ordinalFromCivil(decade, 1, 1),
              endOrdinal: ordinalFromCivil(decade + 9, 12, 31),
            },
          },
          comparison: category(cell.row, "Unknown macroregion") + (decade == null ? "" : " during the " + decade + "s"),
        };
      });
    }
    const craftByCountry = options.inferenceDeferred ? deferredAssociation(
      "craft-by-country",
      ["source", "era"]
    ) : adjustedStandardizedResiduals(active.craftCountryStrataMatrix, {
      maximumRows: 12,
      maximumColumns: 400,
      covariates: ["source", "era"],
      associationLabel: "craft-by-country",
      comparisonState: options.comparisonState,
      rowAxisType: "category",
      columnAxisType: "geography",
    });
    if (!options.inferenceDeferred) {
      [craftByCountry.cells, craftByCountry.fullCells].forEach(function (collection) {
        (Array.isArray(collection) ? collection : []).forEach(function (cell) {
          const metadata = active.countryMetadata.get(cell.column) || reference.countryMetadata.get(cell.column) || countryGeographyMetadata(cell.column);
          Object.assign(cell, metadata, countryEvidenceMetadata(active, reference, cell.column), {
            craft: cell.row,
            countryKey: cell.column,
            country: metadata.country,
            coordinateClass: metadata.coordinateClass,
            displayRow: category(cell.row, "Unknown craft"),
            displayColumn: metadata.country,
            preview: metadata.country === "Unknown country" || metadata.country === "Unmapped" ? {
              kind: "filter",
              patch: { craftTypes: [cell.row] },
            } : {
              kind: "filter",
              patch: {
                craftTypes: [cell.row],
                area: { type: "country", country: metadata.country },
              },
            },
          });
        });
      });
    }
    const sensitivityCells = new Set([].concat(sortedKeys(active.grid), sortedKeys(reference.grid)));
    const equalAreaSensitivity = Array.from(sensitivityCells).map(function (key) {
      const metadata = geographyDatumMetadata(active, reference, key);
      const activeCount = mapCount(active.grid, key);
      const latitudeLabel = round(metadata.latMinimum, 1) + "° to " + round(metadata.latMaximum, 1) + "°";
      const longitudeLabel = round(metadata.lonMinimum, 1) + "° to " + round(metadata.lonMaximum, 1) + "°";
      return countDatum(latitudeLabel + " / " + longitudeLabel, activeCount, mapCount(reference.grid, key), active.total, reference.total, Object.assign({}, metadata, {
        key,
        canonicalGridId: metadata.gridMetadata && metadata.gridMetadata.key,
        displayLabel: latitudeLabel + " · " + longitudeLabel,
      }, previewMissingness(active.missingAnyBy.grid, key, activeCount)));
    }).filter(function (cell) { return cell.observed > 0 || cell.referenceCount > 0; });
    return {
      gridDefinition: {
        id: "country_assignment_v1",
        geographyKind: "country",
        unit: "report points",
        warning: "Country assignment describes report-marker geography, not incidence or risk. Generalized coordinates remain a separate facet.",
      },
      cells,
      countryMap: {
        cells,
        byDecade: byTime,
        craftAssociations: craftByCountry,
        coordinateClasses: ["source_coordinates", "generalized_coordinates"],
        metrics: ["source_balanced_share", "adjusted_difference", "selected_craft_association", "report_counts"],
        defaultMetric: options.analysisMode === ANALYSIS_MODES.WHOLE_CORPUS_STRUCTURE
          ? "source_balanced_share"
          : "adjusted_difference",
      },
      equalAreaSensitivity,
      byTime,
      byEra,
      craftByCountry,
      axisMetadata: {
        byTimeRows: semanticAxisMetadata(byTime.map(function (datum) { return datum.row; }), "geography"),
        byTimeColumns: semanticAxisMetadata(byTime.map(function (datum) { return datum.column; }), "decade"),
        byEraRows: byEra.metadata && byEra.metadata.rowAxis,
        byEraColumns: byEra.metadata && byEra.metadata.columnAxis,
      },
    };
  }

  function sourceBalancedMapGridShares(accumulator) {
    const sourceTotals = new Map();
    const cellBySource = new Map();
    accumulator.mapGrid6CategoryStrata.forEach(function (strataCounts, key) {
      const bySource = new Map();
      strataCounts.forEach(function (count, stratum) {
        const source = String(stratum).split("\u001f")[0] || "unknown";
        incrementRaw(bySource, source, count);
        incrementRaw(sourceTotals, source, count);
      });
      cellBySource.set(key, bySource);
    });
    const sourceKeys = sortedKeys(sourceTotals).filter(function (source) { return mapCount(sourceTotals, source) > 0; });
    const shares = new Map();
    cellBySource.forEach(function (bySource, key) {
      let sum = 0;
      sourceKeys.forEach(function (source) {
        sum += rate(mapCount(bySource, source), mapCount(sourceTotals, source));
      });
      shares.set(key, sourceKeys.length ? sum / sourceKeys.length : 0);
    });
    return { shares, sourceCount: sourceKeys.length, unit: "mean within-source mapped report share" };
  }

  function buildLambertEqualAreaMap6x12(active, reference, comparisonFamily) {
    const coordinateClasses = ["source_coordinates", "generalized_coordinates"];
    const comparisonState = comparisonFamily && comparisonFamily.metadata && comparisonFamily.metadata.comparisonState
      ? comparisonFamily.metadata.comparisonState
      : (reference.total > 0 ? COMPARISON_STATES.INFERENTIAL : COMPARISON_STATES.UNAVAILABLE_NO_REFERENCE);
    const internalStructure = comparisonState === COMPARISON_STATES.WHOLE_CORPUS_STRUCTURE;
    const sourceBalancedShares = sourceBalancedMapGridShares(active);
    const allCells = [];
    const facets = coordinateClasses.map(function (coordinateClass) {
      const cells = [];
      for (let latIndex = 0; latIndex < 6; latIndex += 1) {
        for (let lonIndex = 0; lonIndex < 12; lonIndex += 1) {
          const gridCell = equalAreaMapCell6x12FromIndexes(latIndex, lonIndex);
          const key = coordinateClass + "|" + gridCell.key;
          const observedCount = mapCount(active.mapGrid6, key);
          const referenceCount = mapCount(reference.mapGrid6, key);
          const comparison = comparisonFamily.byKey.get(key) || null;
          const bounds = {
            south: gridCell.latMinimum,
            west: gridCell.lonMinimum,
            north: gridCell.latMaximum,
            east: gridCell.lonMaximum,
          };
          const datum = Object.assign(countDatum(
            coordinateClass + " / " + gridCell.key,
            observedCount,
            referenceCount,
            active.total,
            reference.total,
            {
              key,
              row: String(latIndex),
              column: String(lonIndex),
              latIndex,
              lonIndex,
              coordinateClass,
              latMinimum: gridCell.latMinimum,
              latMaximum: gridCell.latMaximum,
              lonMinimum: gridCell.lonMinimum,
              lonMaximum: gridCell.lonMaximum,
              bounds,
              gridMetadata: {
                definitionId: "lambert_cylindrical_equal_area_6_by_12_v2",
                key: gridCell.key,
                analysisKey: key,
                latIndex,
                lonIndex,
                coordinateClass,
                bounds,
              },
              preview: { kind: "area", area: { bounds } },
              defaultMetric: "adjusted_share_difference",
            }
          ), comparisonSchemaFields(comparison, comparisonState));
          datum.sourceBalancedReportShare = round(mapCount(sourceBalancedShares.shares, key), 10);
          datum.reportShare = round(rate(observedCount, active.mapped), 10);
          datum.logCount = observedCount > 0 ? round(Math.log2(observedCount + 1), 8) : 0;
          datum.comparisonState = comparisonState;
          datum.estimateAvailable = observedCount > 0 || referenceCount > 0 || Boolean(comparison);
          datum.tested = Boolean(comparison && comparison.pValue != null);
          datum.inferenceEligible = Boolean(comparison && comparison.inferenceEligible);
          if (internalStructure) {
            datum.value = datum.sourceBalancedReportShare;
            datum.reference = null;
            datum.referenceShare = null;
            datum.difference = null;
            datum.activeN = active.total;
            datum.referenceN = 0;
            datum.cohortNs = { active: active.total, reference: 0 };
          }
          if (!comparison && datum.estimateAvailable) {
            datum.suppressionReasons = [comparisonState];
            datum.suppressionStatus = "descriptive";
            datum.suppression = { status: "descriptive", reasons: [comparisonState] };
          }
          const adjustedActiveShare = finiteNumber(datum.adjustedActiveShare);
          const adjustedReferenceShare = finiteNumber(datum.adjustedReferenceShare);
          datum.signedAdjustedShareDifference = finiteNumber(datum.adjustedDifference);
          datum.log2Enrichment = adjustedActiveShare != null && adjustedReferenceShare != null && adjustedReferenceShare > 0 && adjustedActiveShare > 0
            ? round(Math.log2(adjustedActiveShare / adjustedReferenceShare), 8)
            : null;
          datum.log2EnrichmentUnbounded = adjustedActiveShare != null && adjustedActiveShare > 0 && adjustedReferenceShare === 0;
          datum.expected = comparison ? comparison.minimumExpectedCell : null;
          datum.expectedCount = null;
          datum.defaultMetric = internalStructure ? "source_balanced_report_share" : datum.defaultMetric;
          cells.push(datum);
          allCells.push(datum);
        }
      }
      const qualified = qualifySparseHeatmapCells(cells, {
        maximumRows: 6,
        maximumColumns: 12,
        minimumExpectedCell: 10,
        minimumCommonSupport: MINIMUM_COMMON_SUPPORT,
      });
      const qualifiedByKey = new Map(qualified.fullCells.map(function (cell) { return [cell.key, cell]; }));
      cells.forEach(function (cell) {
        const display = qualifiedByKey.get(cell.key);
        cell.displayStatus = display.displayStatus;
        cell.displayEligible = display.displayEligible;
        cell.zeroObservedQualifiedDepletion = display.zeroObservedQualifiedDepletion;
        cell.suppressionReasons = display.suppressionReasons.slice();
        cell.suppression = {
          status: display.displayStatus,
          reasons: display.suppressionReasons.slice(),
        };
      });
      return {
        id: coordinateClass,
        coordinateClass,
        label: coordinateClass === "source_coordinates" ? "Source-provided coordinates" : "Generalized coordinates",
        cells,
        qualifiedCells: cells.filter(function (cell) { return cell.displayStatus === "eligible"; }),
        descriptiveCells: cells.filter(function (cell) { return cell.displayStatus === "descriptive"; }),
        lowSupportCells: cells.filter(function (cell) { return cell.displayStatus === "low_support"; }),
        suppressedCells: cells.filter(function (cell) { return cell.suppressionReasons.length > 0 && cell.displayStatus !== "structurally_empty"; }),
        structurallyEmptyCells: cells.filter(function (cell) { return cell.displayStatus === "structurally_empty"; }),
        displayMetadata: qualified.metadata,
      };
    });
    return {
      definition: {
        id: "lambert_cylindrical_equal_area_6_by_12_v2",
        projection: "Lambert cylindrical equal-area",
        latitudeBands: 6,
        longitudeBands: 12,
        equalArea: true,
        cellCountPerFacet: 72,
        coordinateFacets: coordinateClasses.slice(),
        defaultMetric: internalStructure ? "source_balanced_report_share" : "adjusted_share_difference",
        alternateMetrics: internalStructure ? ["log_count", "counts"] : ["log2_enrichment", "counts"],
        sourceBalancedDenominator: sourceBalancedShares.sourceCount,
        sourceBalancedUnit: sourceBalancedShares.unit,
        unit: "report points",
      },
      facets,
      byCoordinateClass: {
        sourceCoordinates: facets[0],
        generalizedCoordinates: facets[1],
      },
      cells: allCells,
      comparisonMetadata: comparisonFamily.metadata,
      comparisonState,
      policyWarning: internalStructure
        ? "Whole-corpus geography shows source-balanced shares of mapped report points; it is report density, not incidence or risk. Generalized coordinates remain a separate facet."
        : "Signed adjusted share differences compare reports, not incidence or risk. Generalized coordinates are a separate facet and never imply exact sites.",
    };
  }

  function missingnessRows(active, reference) {
    const fields = [
      ["Any required analysis field", active.rowsMissingAny, reference.rowsMissingAny],
      ["Unmapped location", active.total - active.mapped, reference.total - reference.mapped],
      ["Missing date ordinal", active.missingOrdinal, reference.missingOrdinal],
      ["Unknown craft", active.total - active.knownCraft, reference.total - reference.knownCraft],
      ["Unknown craft confidence", active.total - active.knownCraftConfidence, reference.total - reference.knownCraftConfidence],
      ["Unknown shape", active.total - active.knownShape, reference.total - reference.knownShape],
    ];
    return fields.map(function (field) {
      return countDatum(field[0], field[1], field[2], active.total, reference.total);
    });
  }

  function sourceCompositionByTime(active, reference) {
    const activeMatrix = active.sourceDecades;
    const referenceMatrix = reference.sourceDecades;
    const activeColumnTotals = new Map();
    const referenceColumnTotals = new Map();
    const sources = new Set();
    const periods = new Set();
    activeMatrix.forEach(function (count, composite) {
      const parts = composite.split("\u0000");
      sources.add(parts[0]);
      periods.add(parts[1]);
      const column = parts[1];
      incrementRaw(activeColumnTotals, column, count);
    });
    referenceMatrix.forEach(function (count, composite) {
      const parts = composite.split("\u0000");
      sources.add(parts[0]);
      periods.add(parts[1]);
      const column = parts[1];
      incrementRaw(referenceColumnTotals, column, count);
    });
    const rows = [];
    Array.from(periods).sort(function (left, right) {
      return semanticAxisCompare(left, right, "decade");
    }).forEach(function (period) {
      Array.from(sources).sort().forEach(function (source) {
        const composite = source + "\u0000" + period;
        const activeCount = mapCount(activeMatrix, composite);
        const referenceCount = mapCount(referenceMatrix, composite);
        const activePeriodTotal = mapCount(activeColumnTotals, period);
        const referencePeriodTotal = mapCount(referenceColumnTotals, period);
        const activeShare = rate(activeCount, activePeriodTotal);
        const referenceShare = rate(referenceCount, referencePeriodTotal);
        const decade = finiteInteger(period);
        const preview = {
          kind: "filter",
          patch: {
            sources: [source],
          },
        };
        if (decade != null) {
          preview.patch.dateRange = {
            startOrdinal: ordinalFromCivil(decade, 1, 1),
            endOrdinal: ordinalFromCivil(decade + 9, 12, 31),
          };
        }
        rows.push(Object.assign({
          label: source + " / " + period,
          row: source,
          column: period,
          source,
          period,
          count: activeCount,
          absoluteCount: activeCount,
          activeCount,
          referenceCount,
          referenceAbsoluteCount: referenceCount,
          activePeriodTotal,
          referencePeriodTotal,
          activeShare: round(activeShare, 10),
          observedShare: round(activeShare, 10),
          referenceShare: round(referenceShare, 10),
          value: round(activeShare, 10),
          observed: round(activeShare, 10),
          reference: round(referenceShare, 10),
          compositionBasis: "within_period_100_percent",
          shareDenominator: "reports in the same cohort and period",
          unitOfAnalysis: "reports",
          preview,
        }, previewMissingness(active.missingAnyBy.sourceDecades, composite, activeCount)));
      });
    });
    return rows;
  }

  function buildSourcesQuality(active, reference, optionsValue) {
    const options = optionsValue || {};
    const fieldAudit = [];
    [
      ["Date precision", active.datePrecisions, reference.datePrecisions, "", null],
      ["Location precision", active.locationPrecisions, reference.locationPrecisions, "precision", active.missingAnyBy.locationPrecisions],
      ["Coordinate source", active.coordinateSources, reference.coordinateSources, ""],
      ["Craft confidence", active.craftConfidences, reference.craftConfidences, ""],
      ["Craft classification source", active.craftSources, reference.craftSources, ""],
      ["Mapped state", active.mappedStates, reference.mappedStates, ""],
    ].forEach(function (dimension) {
      unionMapDatums(dimension[1], dimension[2], active.total, reference.total, dimension[3], dimension[4]).forEach(function (datum) {
        fieldAudit.push(Object.assign({}, datum, { row: dimension[0], column: datum.key }));
      });
    });
    const classifierAssociation = options.inferenceDeferred
      ? {
        cells: matrixCells(active.craftShapesMatrix, 12, 12),
        fullCells: matrixCells(active.craftShapesMatrix, 12, 12),
        metadata: {
          eligible: false,
          status: "deferred",
          inferenceDeferred: true,
          adjustmentCovariates: ["source", "coarse_geography", "coordinate_class", "era"],
          policyWarning: "Classifier consistency estimates are descriptive until the full evidence computation completes.",
        },
      }
      : adjustedStandardizedResiduals(active.craftShapeStrataMatrix, {
        maximumRows: 12,
        maximumColumns: 12,
        covariates: ["source", "coarse_geography", "coordinate_class", "era"],
        associationLabel: "classifier consistency",
        comparisonState: options.comparisonState,
        rowAxisType: "category",
        columnAxisType: "category",
      });
    if (!options.inferenceDeferred) decorateAssociationResult(classifierAssociation, active.total);
    const classifierAudit = classifierAssociation.fullCells;
    return {
      sourceComposition: unionMapDatums(active.sources, reference.sources, active.total, reference.total, "source", active.missingAnyBy.sources),
      sourceByTime: sourceCompositionByTime(active, reference),
      missingness: missingnessRows(active, reference),
      audit: classifierAudit,
      classifierAudit,
      classifierAuditAssociation: classifierAssociation,
      classifierAuditMetadata: classifierAssociation.metadata,
      axisMetadata: {
        sourceByTime: semanticAxisMetadata(new Set([].concat(
          sortedKeys(active.decades),
          sortedKeys(reference.decades)
        )), "decade"),
        classifierRows: classifierAssociation.metadata && classifierAssociation.metadata.rowAxis,
        classifierColumns: classifierAssociation.metadata && classifierAssociation.metadata.columnAxis,
      },
      fieldAudit,
      classifierAuditPolicy: "Inferred craft category is compared with normalized reported shape using conditional expected counts and cell-wise tests; neither axis is ground truth.",
    };
  }

  function dominantSourceForCategory(active, reference, family, key) {
    const combined = new Map();
    const activeBySource = active.familyBySource[family].get(key) || new Map();
    const referenceBySource = reference.familyBySource[family].get(key) || new Map();
    activeBySource.forEach(function (count, source) { increment(combined, source, count); });
    referenceBySource.forEach(function (count, source) { increment(combined, source, count); });
    const first = mapEntriesByCount(combined)[0];
    return first ? first[0] : "unknown";
  }

  function buildFamilyHypotheses(keys, activeTotal, referenceTotal, activeCountForKey, referenceCountForKey) {
    const hypotheses = Array.from(keys).sort().map(function (key) {
      const observedCount = Math.max(0, activeCountForKey(key));
      const referenceCount = Math.max(0, referenceCountForKey(key));
      if (observedCount + referenceCount <= 0) return null;
      const observedShare = rate(observedCount, activeTotal);
      const referenceShare = rate(referenceCount, referenceTotal);
      const difference = observedShare - referenceShare;
      const relativeEnrichment = referenceShare > 0 ? observedShare / referenceShare : (observedShare > 0 ? Infinity : 1);
      const comparison = proportionComparison(observedCount, activeTotal, referenceCount, referenceTotal);
      return {
        key,
        observedCount,
        referenceCount,
        observedShare,
        referenceShare,
        difference,
        relativeEnrichment,
        comparison,
        pValue: comparison.pValue,
        qValue: 1,
      };
    }).filter(Boolean);
    const qValues = benjaminiHochberg(hypotheses);
    hypotheses.forEach(function (hypothesis, index) {
      hypothesis.qValue = qValues[index];
    });
    return hypotheses;
  }

  function familyComparisonStrata(active, reference, family, key) {
    const activeTotals = active.familyStrataTotals[family] || new Map();
    const referenceTotals = reference.familyStrataTotals[family] || new Map();
    const activeCounts = active.familyCategoryStrata[family].get(key) || new Map();
    const referenceCounts = reference.familyCategoryStrata[family].get(key) || new Map();
    const strata = new Set([].concat(sortedKeys(activeTotals), sortedKeys(referenceTotals)));
    return Array.from(strata).map(function (stratum) {
      return {
        key: stratum,
        activeCount: mapCount(activeCounts, stratum),
        activeTotal: mapCount(activeTotals, stratum),
        referenceCount: mapCount(referenceCounts, stratum),
        referenceTotal: mapCount(referenceTotals, stratum),
      };
    });
  }

  function buildBalancedFamilyComparisons(active, reference, descriptor, optionsValue) {
    const options = optionsValue || {};
    const result = {};
    FAMILY_ORDER.forEach(function (family) {
      const activeCounts = active.familyCounts[family] || new Map();
      const referenceCounts = reference.familyCounts[family] || new Map();
      const keys = new Set([].concat(sortedKeys(activeCounts), sortedKeys(referenceCounts)));
      const comparisons = Array.from(keys).sort().map(function (key) {
        const comparison = balancedCommonSupportComparison(familyComparisonStrata(active, reference, family, key), {
          activeN: active.total,
          referenceN: reference.total,
          descriptive: descriptor.descriptive,
          covariates: FAMILY_COVARIATES[family],
          minimumCommonSupport: options.minimumCommonSupport,
          bootstrapReplicates: options.bootstrapReplicates,
          seed: [options.datasetHash || "not_provided", descriptor.mode, family, key].join("|"),
        });
        comparison.family = family;
        comparison.key = key;
        comparison.datasetHash = options.datasetHash || "not_provided";
        comparison.artifactHashes = Object.assign({}, options.artifactHashes || {});
        return comparison;
      });
      assignEligibleBenjaminiHochberg(comparisons);
      result[family] = {
        comparisons,
        byKey: new Map(comparisons.map(function (comparison) { return [comparison.key, comparison]; })),
        metadata: {
          estimatorVersion: ESTIMATOR_VERSION,
          covariates: (FAMILY_COVARIATES[family] || []).slice(),
          minimumCommonSupport: finiteNumber(options.minimumCommonSupport) == null ? MINIMUM_COMMON_SUPPORT : finiteNumber(options.minimumCommonSupport),
          bootstrapReplicates: Math.max(1, finiteInteger(options.bootstrapReplicates) || DEFAULT_BOOTSTRAP_REPLICATES),
          descriptive: descriptor.descriptive,
          comparisonState: descriptor.comparisonState || (descriptor.descriptive ? COMPARISON_STATES.DESCRIPTIVE_OVERLAP : COMPARISON_STATES.INFERENTIAL),
        },
      };
    });
    return result;
  }

  function deferredBalancedFamilyComparisons(descriptor, optionsValue) {
    const options = optionsValue || {};
    const result = {};
    FAMILY_ORDER.forEach(function (family) {
      result[family] = {
        comparisons: [],
        byKey: new Map(),
        metadata: {
          estimatorVersion: ESTIMATOR_VERSION,
          covariates: (FAMILY_COVARIATES[family] || []).slice(),
          minimumCommonSupport: finiteNumber(options.minimumCommonSupport) == null ? MINIMUM_COMMON_SUPPORT : finiteNumber(options.minimumCommonSupport),
          bootstrapReplicates: 0,
          descriptive: descriptor.descriptive,
          inferenceDeferred: true,
          status: "deferred",
          suppressionReasons: ["quick_core_inference_deferred"],
        },
      };
    });
    return result;
  }

  function unavailableBalancedFamilyComparisons(descriptor, comparisonState, optionsValue) {
    const options = optionsValue || {};
    const result = {};
    FAMILY_ORDER.forEach(function (family) {
      result[family] = {
        comparisons: [],
        byKey: new Map(),
        metadata: {
          estimatorVersion: ESTIMATOR_VERSION,
          covariates: (FAMILY_COVARIATES[family] || []).slice(),
          minimumCommonSupport: finiteNumber(options.minimumCommonSupport) == null ? MINIMUM_COMMON_SUPPORT : finiteNumber(options.minimumCommonSupport),
          bootstrapReplicates: 0,
          descriptive: Boolean(descriptor && descriptor.descriptive),
          inferenceDeferred: false,
          comparisonState,
          status: comparisonState,
          suppressionReasons: [comparisonState],
        },
      };
    });
    return result;
  }

  function deferredMapGrid6Comparisons(descriptor, optionsValue) {
    const options = optionsValue || {};
    return {
      comparisons: [],
      byKey: new Map(),
      metadata: {
        estimatorVersion: ESTIMATOR_VERSION,
        covariates: FAMILY_COVARIATES.geography.slice(),
        minimumCommonSupport: finiteNumber(options.minimumCommonSupport) == null ? MINIMUM_COMMON_SUPPORT : finiteNumber(options.minimumCommonSupport),
        bootstrapReplicates: 0,
        fdrFamily: "all_nonempty_6x12_cells_across_coordinate_facets",
        descriptive: descriptor.descriptive,
        inferenceDeferred: true,
        status: "deferred",
        suppressionReasons: ["quick_core_inference_deferred"],
      },
    };
  }

  function unavailableMapGrid6Comparisons(descriptor, comparisonState, optionsValue) {
    const options = optionsValue || {};
    return {
      comparisons: [],
      byKey: new Map(),
      metadata: {
        estimatorVersion: ESTIMATOR_VERSION,
        covariates: FAMILY_COVARIATES.geography.slice(),
        minimumCommonSupport: finiteNumber(options.minimumCommonSupport) == null ? MINIMUM_COMMON_SUPPORT : finiteNumber(options.minimumCommonSupport),
        bootstrapReplicates: 0,
        fdrFamily: "none_without_independent_reference",
        descriptive: Boolean(descriptor && descriptor.descriptive),
        inferenceDeferred: false,
        comparisonState,
        status: comparisonState,
        suppressionReasons: [comparisonState],
      },
    };
  }

  function mapGrid6ComparisonStrata(active, reference, key) {
    const activeTotals = active.familyStrataTotals.geography || new Map();
    const referenceTotals = reference.familyStrataTotals.geography || new Map();
    const activeCounts = active.mapGrid6CategoryStrata.get(key) || new Map();
    const referenceCounts = reference.mapGrid6CategoryStrata.get(key) || new Map();
    const strata = new Set([].concat(sortedKeys(activeTotals), sortedKeys(referenceTotals)));
    return Array.from(strata).map(function (stratum) {
      return {
        key: stratum,
        activeCount: mapCount(activeCounts, stratum),
        activeTotal: mapCount(activeTotals, stratum),
        referenceCount: mapCount(referenceCounts, stratum),
        referenceTotal: mapCount(referenceTotals, stratum),
      };
    });
  }

  function buildMapGrid6Comparisons(active, reference, descriptor, optionsValue) {
    const options = optionsValue || {};
    const keys = new Set([].concat(sortedKeys(active.mapGrid6), sortedKeys(reference.mapGrid6)));
    const comparisons = Array.from(keys).sort().map(function (key) {
      const comparison = balancedCommonSupportComparison(mapGrid6ComparisonStrata(active, reference, key), {
        activeN: active.total,
        referenceN: reference.total,
        descriptive: descriptor.descriptive,
        covariates: FAMILY_COVARIATES.geography,
        minimumCommonSupport: options.minimumCommonSupport,
        bootstrapReplicates: options.bootstrapReplicates,
        seed: [options.datasetHash || "not_provided", descriptor.mode, "geography_map_6x12", key].join("|"),
      });
      comparison.family = "geography_map_6x12";
      comparison.key = key;
      comparison.datasetHash = options.datasetHash || "not_provided";
      comparison.artifactHashes = Object.assign({}, options.artifactHashes || {});
      return comparison;
    });
    assignEligibleBenjaminiHochberg(comparisons);
    return {
      comparisons,
      byKey: new Map(comparisons.map(function (comparison) { return [comparison.key, comparison]; })),
      metadata: {
        estimatorVersion: ESTIMATOR_VERSION,
        covariates: FAMILY_COVARIATES.geography.slice(),
        minimumCommonSupport: finiteNumber(options.minimumCommonSupport) == null ? MINIMUM_COMMON_SUPPORT : finiteNumber(options.minimumCommonSupport),
        bootstrapReplicates: Math.max(1, finiteInteger(options.bootstrapReplicates) || DEFAULT_BOOTSTRAP_REPLICATES),
        fdrFamily: "all_nonempty_6x12_cells_across_coordinate_facets",
        descriptive: descriptor.descriptive,
        comparisonState: descriptor.comparisonState || (descriptor.descriptive ? COMPARISON_STATES.DESCRIPTIVE_OVERLAP : COMPARISON_STATES.INFERENTIAL),
      },
    };
  }

  function comparisonSchemaFields(comparison, comparisonStateValue) {
    const comparisonState = comparisonStateValue || (comparison && comparison.comparisonState) || COMPARISON_STATES.INFERENTIAL;
    if (!comparison) {
      return {
        estimatorVersion: ESTIMATOR_VERSION,
        comparisonState,
        comparisonAvailable: false,
        estimateAvailable: false,
        tested: false,
        inferenceEligible: false,
        suppressionStatus: "unavailable",
        suppressionReasons: [comparisonState === COMPARISON_STATES.INFERENTIAL ? "comparison_not_available" : comparisonState],
        supportedActiveN: 0,
        supportedReferenceN: 0,
        supportedNs: { active: 0, reference: 0 },
        cohortNs: { active: 0, reference: 0 },
        commonSupportRate: null,
        adjustedEffect: null,
        effectSize: { measure: "adjusted_share_difference", estimate: null, unit: "proportion" },
        interval: null,
        pValue: null,
        qValue: null,
        covariates: [],
        suppression: { status: "unavailable", reasons: [comparisonState === COMPARISON_STATES.INFERENTIAL ? "comparison_not_available" : comparisonState] },
      };
    }
    return {
      estimatorVersion: comparison.estimatorVersion,
      comparisonState,
      comparisonAvailable: true,
      estimateAvailable: comparison.adjustedEffect != null,
      tested: comparison.pValue != null,
      activeN: comparison.activeN,
      referenceN: comparison.referenceN,
      cohortNs: Object.assign({}, comparison.cohortNs),
      supportedActiveN: comparison.supportedActiveN,
      supportedReferenceN: comparison.supportedReferenceN,
      supportedNs: Object.assign({}, comparison.supportedNs),
      commonStrataCount: comparison.commonStrataCount,
      commonSupportRate: comparison.commonSupportRate,
      adjustedActiveShare: comparison.adjustedActiveShare,
      adjustedReferenceShare: comparison.adjustedReferenceShare,
      adjustedDifference: comparison.adjustedDifference,
      adjustedEffect: comparison.adjustedEffect,
      effectSize: Object.assign({}, comparison.effectSize),
      interval: comparison.interval,
      uncertainty: comparison.uncertainty,
      oddsRatio: comparison.oddsRatio,
      oddsRatioInterval: comparison.oddsRatioInterval,
      pValue: comparison.pValue,
      qValue: comparison.qValue,
      cramersV: comparison.cramersV,
      minimumExpectedCell: comparison.minimumExpectedCell,
      inferenceEligible: comparison.inferenceEligible,
      suppressionStatus: comparison.suppressionStatus,
      suppressionReasons: comparison.suppressionReasons.slice(),
      suppression: {
        status: comparison.suppression.status,
        reasons: comparison.suppression.reasons.slice(),
      },
      covariates: comparison.covariates.slice(),
      datasetHash: comparison.datasetHash,
      artifactHashes: Object.assign({}, comparison.artifactHashes || {}),
    };
  }

  function applyComparisonSchema(datums, comparisonFamily, keyAccessor) {
    const input = Array.isArray(datums) ? datums : [];
    const byKey = comparisonFamily && comparisonFamily.byKey instanceof Map ? comparisonFamily.byKey : new Map();
    const accessor = typeof keyAccessor === "function" ? keyAccessor : function (datum) { return datum && datum.key; };
    input.forEach(function (datum) {
      const comparison = byKey.get(accessor(datum));
      Object.assign(datum, comparisonSchemaFields(comparison, comparisonFamily && comparisonFamily.metadata && comparisonFamily.metadata.comparisonState));
    });
    return input;
  }

  function createSourceExclusionCache(active, reference) {
    const sourceKeys = new Set([].concat(sortedKeys(active.sources), sortedKeys(reference.sources)));
    const eligibleSources = Array.from(sourceKeys).filter(function (source) {
      return isKnown(source) && mapCount(active.sources, source) >= 25;
    }).sort();
    const cache = new Map();

    function get(family, source) {
      const cacheKey = family + "\u0000" + source;
      if (cache.has(cacheKey)) return cache.get(cacheKey);
      const activeTotal = active.total - mapCount(active.sources, source);
      const referenceTotal = reference.total - mapCount(reference.sources, source);
      const activeCounts = active.familyCounts[family] || new Map();
      const referenceCounts = reference.familyCounts[family] || new Map();
      const keys = new Set([].concat(sortedKeys(activeCounts), sortedKeys(referenceCounts)));
      const comparisons = Array.from(keys).sort().map(function (key) {
        const strata = familyComparisonStrata(active, reference, family, key).filter(function (entry) {
          return String(entry.key).split("\u001f")[0] !== source;
        });
        const comparison = balancedCommonSupportComparison(strata, {
          activeN: activeTotal,
          referenceN: referenceTotal,
          covariates: FAMILY_COVARIATES[family],
          seed: ["source_exclusion", source, family, key].join("|"),
          skipBootstrap: true,
        });
        comparison.family = family;
        comparison.key = key;
        comparison._sensitivityStrata = strata;
        comparison._sensitivitySeed = ["source_exclusion", source, family, key].join("|");
        return comparison;
      });
      assignEligibleBenjaminiHochberg(comparisons);
      const result = {
        activeTotal,
        referenceTotal,
        comparisons,
        byKey: new Map(comparisons.map(function (comparison) { return [comparison.key, comparison]; })),
      };
      cache.set(cacheKey, result);
      return result;
    }

    return { eligibleSources, get };
  }

  function sourceExclusionAssessment(source, exclusion, key, direction) {
    const comparison = exclusion.byKey.get(key) || null;
    const difference = comparison && comparison.adjustedDifference != null ? comparison.adjustedDifference : 0;
    const adjustedActiveShare = comparison && comparison.adjustedActiveShare != null ? comparison.adjustedActiveShare : 0;
    const adjustedReferenceShare = comparison && comparison.adjustedReferenceShare != null ? comparison.adjustedReferenceShare : 0;
    const relativeEnrichment = adjustedReferenceShare > 0
      ? adjustedActiveShare / adjustedReferenceShare
      : (adjustedActiveShare > 0 ? Infinity : 1);
    const nontrivialEffect = Boolean(comparison) && (
      Math.abs(difference) >= 0.02 || relativeEnrichment >= 1.25 || relativeEnrichment <= 0.8
    );
    const sameDirection = Boolean(comparison) && (direction === "higher" ? difference > 0 : difference < 0);
    const interval = comparison && Array.isArray(comparison._sensitivityStrata)
      ? deterministicAggregatedStratumBootstrap(comparison._sensitivityStrata, {
        seed: comparison._sensitivitySeed,
      })
      : null;
    const intervalSupportsDirection = sameDirection && (
      direction === "higher" ? interval && interval.lower > 0 : interval && interval.upper < 0
    );
    const failedGates = [];
    if (exclusion.activeTotal < 200) failedGates.push("active_n");
    if (exclusion.referenceTotal <= 0) failedGates.push("reference_n");
    if (!comparison || comparison.observedCount < 25) failedGates.push("observed_category_n");
    if (!comparison || comparison.minimumExpectedCell < 10) failedGates.push("expected_cell");
    if (!comparison || comparison.cramersV < 0.10) failedGates.push("cramers_v");
    if (!comparison || comparison.qValue == null || comparison.qValue > 0.05) failedGates.push("q_value");
    if (comparison && !comparison.inferenceEligible) {
      comparison.suppressionReasons.forEach(function (reason) {
        if (failedGates.indexOf(reason) === -1) failedGates.push(reason);
      });
    }
    if (!nontrivialEffect) failedGates.push("nontrivial_effect");
    if (!sameDirection) failedGates.push("direction");
    if (!intervalSupportsDirection) failedGates.push("confidence_interval");
    return {
      source,
      passes: failedGates.length === 0,
      failedGates,
      activeN: exclusion.activeTotal,
      referenceN: exclusion.referenceTotal,
      observedCount: comparison ? comparison.observedCount : 0,
      referenceCount: comparison ? comparison.referenceCount : 0,
      supportedActiveN: comparison ? comparison.supportedActiveN : 0,
      supportedReferenceN: comparison ? comparison.supportedReferenceN : 0,
      commonSupportRate: comparison ? comparison.commonSupportRate : 0,
      adjustedActiveShare: comparison ? comparison.adjustedActiveShare : null,
      adjustedReferenceShare: comparison ? comparison.adjustedReferenceShare : null,
      adjustedDifference: comparison ? comparison.adjustedDifference : null,
      difference: round(difference, 8),
      relativeEnrichment: Number.isFinite(relativeEnrichment) ? round(relativeEnrichment, 8) : null,
      relativeEnrichmentUnbounded: !Number.isFinite(relativeEnrichment),
      pValue: comparison && comparison.pValue != null ? round(comparison.pValue, 12) : null,
      qValue: comparison && comparison.qValue != null ? round(comparison.qValue, 12) : null,
      cramersV: round(comparison ? comparison.cramersV : 0, 8),
      minimumExpectedCell: round(comparison ? comparison.minimumExpectedCell : 0, 6),
      oddsRatio: comparison ? comparison.oddsRatio : null,
      oddsRatioInterval: comparison ? comparison.oddsRatioInterval : null,
      covariates: comparison ? comparison.covariates.slice() : [],
      estimatorVersion: comparison ? comparison.estimatorVersion : ESTIMATOR_VERSION,
      inferenceEligible: Boolean(comparison && comparison.inferenceEligible),
      interval: interval ? {
        lower: round(interval.lower, 8),
        upper: round(interval.upper, 8),
        level: interval.level,
        method: interval.method,
        replicates: interval.replicates,
      } : null,
      sameDirection,
      nontrivialEffect,
      intervalSupportsDirection,
    };
  }

  function leaveOneSourceOut(active, reference, family, key, direction, exclusionCache) {
    if (family === "source") {
      return {
        status: "source_specific_dimension",
        stable: false,
        sourcesTested: 0,
        passes: 0,
        directionStable: false,
        effectStable: false,
        gateStable: false,
        dominantSource: key,
        exclusions: [],
      };
    }
    const eligibleSources = exclusionCache.eligibleSources;
    if (eligibleSources.length < 2) {
      return {
        status: "single_source_only",
        stable: false,
        sourcesTested: eligibleSources.length,
        passes: 0,
        directionStable: false,
        effectStable: false,
        gateStable: false,
        dominantSource: dominantSourceForCategory(active, reference, family, key),
        exclusions: [],
      };
    }
    const exclusions = eligibleSources.map(function (source) {
      return sourceExclusionAssessment(source, exclusionCache.get(family, source), key, direction);
    });
    const passes = exclusions.filter(function (exclusion) { return exclusion.passes; }).length;
    const directionStable = exclusions.every(function (exclusion) { return exclusion.sameDirection; });
    const effectStable = exclusions.every(function (exclusion) {
      return exclusion.sameDirection && exclusion.nontrivialEffect;
    });
    const stable = passes === eligibleSources.length;
    return {
      status: stable ? "stable_multi_source" : "source_sensitive",
      stable,
      sourcesTested: eligibleSources.length,
      passes,
      directionStable,
      effectStable,
      gateStable: stable,
      dominantSource: dominantSourceForCategory(active, reference, family, key),
      exclusions,
    };
  }

  function createRegionExclusionCache(active, reference) {
    const regionKeys = new Set([].concat(sortedKeys(active.regions), sortedKeys(reference.regions)));
    const eligibleRegions = Array.from(regionKeys).filter(function (region) {
      return mapCount(active.regions, region) + mapCount(reference.regions, region) >= 25;
    }).sort();
    const cache = new Map();
    function get(family, region) {
      const cacheKey = family + "\u0000" + region;
      if (cache.has(cacheKey)) return cache.get(cacheKey);
      const activeTotal = active.total - mapCount(active.regions, region);
      const referenceTotal = reference.total - mapCount(reference.regions, region);
      const activeCounts = active.familyCounts[family] || new Map();
      const referenceCounts = reference.familyCounts[family] || new Map();
      const keys = new Set([].concat(sortedKeys(activeCounts), sortedKeys(referenceCounts)));
      const comparisons = Array.from(keys).sort().map(function (key) {
        let strata;
        if (family === "geography") {
          const activeTotalsByRegion = active.geographyStrataTotalsByRegion.get(region) || new Map();
          const referenceTotalsByRegion = reference.geographyStrataTotalsByRegion.get(region) || new Map();
          const activeCategoryByRegion = (active.geographyCategoryStrataByRegion.get(key) || new Map()).get(region) || new Map();
          const referenceCategoryByRegion = (reference.geographyCategoryStrataByRegion.get(key) || new Map()).get(region) || new Map();
          strata = familyComparisonStrata(active, reference, family, key).map(function (entry) {
            return {
              key: entry.key,
              activeCount: Math.max(0, entry.activeCount - mapCount(activeCategoryByRegion, entry.key)),
              activeTotal: Math.max(0, entry.activeTotal - mapCount(activeTotalsByRegion, entry.key)),
              referenceCount: Math.max(0, entry.referenceCount - mapCount(referenceCategoryByRegion, entry.key)),
              referenceTotal: Math.max(0, entry.referenceTotal - mapCount(referenceTotalsByRegion, entry.key)),
            };
          }).filter(function (entry) {
            return entry.activeTotal > 0 || entry.referenceTotal > 0;
          });
        } else {
          const regionIndex = family === "source" ? 0 : 1;
          strata = familyComparisonStrata(active, reference, family, key).filter(function (entry) {
            return String(entry.key).split("\u001f")[regionIndex] !== region;
          });
        }
        const comparison = balancedCommonSupportComparison(strata, {
          activeN: activeTotal,
          referenceN: referenceTotal,
          covariates: FAMILY_COVARIATES[family],
          seed: ["region_exclusion", region, family, key].join("|"),
          skipBootstrap: true,
        });
        comparison.family = family;
        comparison.key = key;
        comparison._sensitivityStrata = strata;
        comparison._sensitivitySeed = ["region_exclusion", region, family, key].join("|");
        return comparison;
      });
      assignEligibleBenjaminiHochberg(comparisons);
      const result = {
        activeTotal,
        referenceTotal,
        comparisons,
        byKey: new Map(comparisons.map(function (comparison) { return [comparison.key, comparison]; })),
      };
      cache.set(cacheKey, result);
      return result;
    }
    return { eligibleRegions, get };
  }

  function leaveOneRegionOut(active, reference, family, key, direction, exclusionCache) {
    const eligibleRegions = exclusionCache.eligibleRegions;
    if (eligibleRegions.length < 2) {
      return {
        status: "insufficient_regions",
        stable: false,
        regionsTested: eligibleRegions.length,
        passes: 0,
        directionStable: false,
        effectStable: false,
        gateStable: false,
        exclusions: [],
      };
    }
    const exclusions = eligibleRegions.map(function (region) {
      const assessment = sourceExclusionAssessment(region, exclusionCache.get(family, region), key, direction);
      assessment.region = region;
      delete assessment.source;
      return assessment;
    });
    const passes = exclusions.filter(function (exclusion) { return exclusion.passes; }).length;
    const directionStable = exclusions.every(function (exclusion) { return exclusion.sameDirection; });
    const effectStable = exclusions.every(function (exclusion) {
      return exclusion.sameDirection && exclusion.nontrivialEffect;
    });
    const stable = passes === eligibleRegions.length;
    return {
      status: stable ? "stable_multi_region" : "region_sensitive",
      stable,
      regionsTested: eligibleRegions.length,
      passes,
      directionStable,
      effectStable,
      gateStable: stable,
      exclusions,
    };
  }

  function patternLabel(family, key) {
    const familyLabels = {
      craft: "Craft",
      time_month: "Month",
      geography: "Geographic grid cell",
      source: "Source",
      date_precision: "Date precision",
      location_precision: "Location precision",
      coordinate_source: "Coordinate source",
      craft_confidence: "Craft confidence",
    };
    return (familyLabels[family] || family) + ": " + key;
  }

  function unknownMapCount(map) {
    let count = 0;
    map.forEach(function (value, key) {
      if (!isKnown(key)) count += value;
    });
    return count;
  }

  function patternMissingCount(active, family) {
    if (family === "craft") return active.total - active.knownCraft;
    if (family === "craft_confidence") return active.total - active.knownCraftConfidence;
    if (family === "geography") return active.total - active.mapped;
    if (family === "time_month") return active.missingOrdinal;
    if (family === "source") return unknownMapCount(active.sources);
    if (family === "date_precision") return unknownMapCount(active.datePrecisions);
    if (family === "location_precision") return unknownMapCount(active.locationPrecisions);
    if (family === "coordinate_source") return unknownMapCount(active.coordinateSources);
    return active.rowsMissingAny;
  }

  function patternChartId(family) {
    const ids = {
      craft: "analysis-craft-distribution",
      time_month: "analysis-month-year",
      geography: "analysis-geography-grid",
      source: "analysis-source-composition",
      date_precision: "analysis-quality-date-precision",
      location_precision: "analysis-quality-location-precision",
      coordinate_source: "analysis-quality-coordinate-source",
      craft_confidence: "analysis-craft-confidence",
    };
    return ids[family] || "analysis-overview";
  }

  function patternPreview(active, family, key) {
    if (family === "geography") {
      const metadata = active.gridMetadata.get(key) || {};
      return {
        kind: "area",
        area: {
          bounds: {
            north: metadata.latMaximum,
            south: metadata.latMinimum,
            east: metadata.lonMaximum,
            west: metadata.lonMinimum,
          },
        },
      };
    }
    const patches = {
      craft: { craftTypes: [key] },
      source: { sources: [key] },
      location_precision: { precisions: [key] },
    };
    return patches[family] ? { kind: "filter", patch: patches[family] } : null;
  }

  function buildPatternFamilies(active, reference, datasetHash, descriptor, balancedFamilies, artifactHashes) {
    const result = {};
    if (descriptor.descriptive || active.total < 200 || reference.total <= 0) {
      FAMILY_ORDER.forEach(function (family) { result[family] = []; });
      return result;
    }
    FAMILY_ORDER.forEach(function (family) {
      const comparisons = balancedFamilies && balancedFamilies[family]
        ? balancedFamilies[family].comparisons
        : [];
      const candidates = [];
      comparisons.forEach(function (comparison) {
        const key = comparison.key;
        const observedCount = comparison.observedCount;
        const referenceCount = comparison.referenceCount;
        const observedShare = comparison.adjustedActiveShare;
        const referenceShare = comparison.adjustedReferenceShare;
        const difference = comparison.adjustedDifference;
        if (!comparison.inferenceEligible || difference == null || observedShare == null || referenceShare == null) return;
        const relativeEnrichment = referenceShare > 0 ? observedShare / referenceShare : (observedShare > 0 ? Infinity : 1);
        if (observedCount < 25) return;
        if (!(Math.abs(difference) >= 0.02 || relativeEnrichment >= 1.25 || relativeEnrichment <= 0.8)) return;
        if (comparison.minimumExpectedCell < 10) return;
        if (comparison.cramersV < 0.10) return;
        if (comparison.qValue == null || comparison.qValue > 0.05) return;
        const interval = comparison.interval;
        const direction = difference >= 0 ? "higher" : "lower";
        const conservativeEffect = direction === "higher" ? Math.max(0, interval.lower) : Math.max(0, -interval.upper);
        const missingCount = patternMissingCount(active, family);
        const observedPercent = round(observedShare * 100, 1);
        const referencePercent = round(referenceShare * 100, 1);
        const differencePoints = round(difference * 100, 1);
        const label = patternLabel(family, key);
        const preview = patternPreview(active, family, key);
        const candidate = {
          family,
          key,
          label,
          title: label,
          summary: label + " is " + direction + " after common-support balancing (" + observedPercent + "% vs " + referencePercent + "%).",
          effectLabel: observedPercent + "% vs " + referencePercent + "% (" + (differencePoints >= 0 ? "+" : "") + differencePoints + " percentage points)",
          intervalLabel: "95% interval " + round(interval.lower * 100, 1) + " to " + round(interval.upper * 100, 1) + " percentage points",
          chartId: patternChartId(family),
          direction,
          observedCount,
          referenceCount,
          activeN: active.total,
          referenceN: reference.total,
          cohortNs: { active: active.total, reference: reference.total },
          supportedActiveN: comparison.supportedActiveN,
          supportedReferenceN: comparison.supportedReferenceN,
          supportedNs: { active: comparison.supportedActiveN, reference: comparison.supportedReferenceN },
          commonSupportRate: comparison.commonSupportRate,
          commonStrataCount: comparison.commonStrataCount,
          observedShare: round(observedShare, 8),
          referenceShare: round(referenceShare, 8),
          difference: round(difference, 8),
          adjustedActiveShare: round(observedShare, 8),
          adjustedReferenceShare: round(referenceShare, 8),
          adjustedDifference: round(difference, 8),
          adjustedEffect: round(difference, 8),
          effectSize: {
            measure: "adjusted_share_difference",
            estimate: round(difference, 8),
            unit: "proportion",
          },
          relativeEnrichment: Number.isFinite(relativeEnrichment) ? round(relativeEnrichment, 8) : null,
          relativeEnrichmentUnbounded: !Number.isFinite(relativeEnrichment),
          interval: {
            lower: round(interval.lower, 8),
            upper: round(interval.upper, 8),
            level: interval.level,
            method: interval.method,
            replicates: interval.replicates,
          },
          pValue: round(comparison.pValue, 12),
          qValue: round(comparison.qValue, 12),
          cramersV: round(comparison.cramersV, 8),
          minimumExpectedCell: round(comparison.minimumExpectedCell, 6),
          oddsRatio: comparison.oddsRatio,
          oddsRatioInterval: comparison.oddsRatioInterval,
          conservativeEffect: round(conservativeEffect, 8),
          missingCount,
          missingness: round(rate(missingCount, active.total), 8),
          sourceStability: null,
          regionStability: null,
          covariates: comparison.covariates.slice(),
          estimatorVersion: comparison.estimatorVersion,
          inferenceEligible: true,
          suppressionStatus: "eligible",
          suppressionReasons: [],
          suppression: { status: "eligible", reasons: [] },
          datasetHash: datasetHash || "not_provided",
          artifactHashes: Object.assign({}, artifactHashes || {}),
          exploratory: true,
          policyLabel: EXPLORATORY_POLICY,
        };
        if (preview) candidate.preview = preview;
        candidates.push(candidate);
      });
      result[family] = candidates;
    });
    return result;
  }

  function populatePatternSourceSensitivity(active, reference, patternFamilies) {
    const sourceExclusionCache = createSourceExclusionCache(active, reference);
    const regionExclusionCache = createRegionExclusionCache(active, reference);
    const qualityFamilies = new Set(["source", "date_precision", "location_precision", "coordinate_source", "craft_confidence"]);
    FAMILY_ORDER.forEach(function (family) {
      const candidates = patternFamilies[family] || [];
      candidates.forEach(function (candidate) {
        candidate.sourceStability = leaveOneSourceOut(
          active,
          reference,
          family,
          candidate.key,
          candidate.direction,
          sourceExclusionCache
        );
        candidate.regionStability = leaveOneRegionOut(
          active,
          reference,
          family,
          candidate.key,
          candidate.direction,
          regionExclusionCache
        );
        if (qualityFamilies.has(family)) {
          candidate.findingLane = "collection_and_quality";
        } else if (candidate.sourceStability.stable && candidate.regionStability.stable) {
          candidate.findingLane = "stable_multi_source_content";
        } else {
          candidate.findingLane = "source_or_region_sensitive";
        }
      });
      candidates.sort(function (left, right) {
        return (right.conservativeEffect - left.conservativeEffect) || String(left.key).localeCompare(String(right.key));
      });
      candidates.forEach(function (candidate, index) {
        candidate.rankWithinFamily = index + 1;
      });
    });
  }

  function codebookContainers(container, domain) {
    if (!container || typeof container !== "object") return [];
    const results = [container];
    ["codebooks", "codes", "dictionaries", "lookupTables", "lookup_tables"].forEach(function (key) {
      if (container[key] && typeof container[key] === "object") results.push(container[key]);
    });
    ["domains", "projections", "datasets", "files"].forEach(function (key) {
      const group = container[key];
      if (!group || typeof group !== "object") return;
      const domainObject = group[domain] || group[domain === "cropCircles" ? "crop_circles" : "animal_reports"];
      if (domainObject && typeof domainObject === "object") {
        results.push.apply(results, codebookContainers(domainObject, domain));
      }
    });
    return results;
  }

  function lookupProjectionCode(containers, domain, fieldNames, code) {
    if (code == null || code === "") return "unknown";
    const names = Array.isArray(fieldNames) ? fieldNames : [fieldNames];
    const candidates = [];
    (Array.isArray(containers) ? containers : [containers]).forEach(function (container) {
      candidates.push.apply(candidates, codebookContainers(container, domain));
    });
    for (const candidate of candidates) {
      for (const field of names) {
        const variants = [field, field + "Codes", field + "_codes", field + "Code", field + "_code"];
        for (const variant of variants) {
          const book = candidate && candidate[variant];
          if (Array.isArray(book) && Object.prototype.hasOwnProperty.call(book, Number(code))) {
            return category(book[Number(code)], "unknown");
          }
          if (book && typeof book === "object" && Object.prototype.hasOwnProperty.call(book, String(code))) {
            return category(book[String(code)], "unknown");
          }
        }
      }
    }
    return category(code, "unknown");
  }

  function projectionRows(projection) {
    if (Array.isArray(projection)) return projection;
    if (!projection || typeof projection !== "object") return [];
    if (Array.isArray(projection.rows)) return projection.rows;
    if (Array.isArray(projection.records)) return projection.records;
    if (Array.isArray(projection.data)) return projection.data;
    return [];
  }

  function normalizeCropRow(row, projection, manifest) {
    if (Array.isArray(row)) {
      return {
        id: row[0],
        year: finiteInteger(row[1]),
        startYear: finiteInteger(row[1]),
        endYear: finiteInteger(row[2]) == null ? finiteInteger(row[1]) : finiteInteger(row[2]),
        datePrecision: lookupProjectionCode([projection, manifest], "cropCircles", ["datePrecision", "date_precision"], row[3]),
        country: lookupProjectionCode([projection, manifest], "cropCircles", ["country"], row[4]),
        crop: lookupProjectionCode([projection, manifest], "cropCircles", ["cropType", "crop_type", "crop"], row[5]),
        classification: "unknown",
        originStatus: "unknown",
        morphology: (Array.isArray(row[6]) ? row[6] : [row[6]]).filter(function (value) { return value != null; }).map(function (value) {
          return lookupProjectionCode([projection, manifest], "cropCircles", ["morphology", "morphologyFamily"], value);
        }),
        complexity: (Array.isArray(row[7]) ? row[7] : [row[7]]).filter(function (value) { return value != null; }).map(function (value) {
          return lookupProjectionCode([projection, manifest], "cropCircles", ["complexityTier", "complexity_tier"], value);
        }).join(", ") || "unknown",
        coordinateClass: lookupProjectionCode([projection, manifest], "cropCircles", ["coordinateClass", "coordinate_class"], row[8]),
        mapped: Boolean(row[9]),
        hasNarrative: Boolean(row[10]),
        hasSize: Boolean(row[11]),
        startOrdinal: finiteInteger(row[12]),
        endOrdinal: finiteInteger(row[13]) == null ? finiteInteger(row[12]) : finiteInteger(row[13]),
        lat: null,
        lon: null,
      };
    }
    const source = row || {};
    return {
      id: source.id,
      year: finiteInteger(source.year),
      startYear: finiteInteger(source.startYear || source.start_year || source.year),
      endYear: finiteInteger(source.endYear || source.end_year || source.year),
      datePrecision: category(source.datePrecision || source.date_precision, "unknown"),
      country: category(source.country, "unknown"),
      crop: category(source.crop || source.cropType, "unknown"),
      classification: category(source.classification, "unknown"),
      originStatus: category(source.originStatus || source.origin_status, "unknown"),
      morphology: (Array.isArray(source.morphology) ? source.morphology : (source.morphologyFamilies || [])).map(function (value) { return category(value, "unknown"); }),
      complexity: category(source.complexity || source.complexityTier, "unknown"),
      coordinateClass: category(source.coordinateClass || source.coordinate_class, "unknown"),
      mapped: typeof source.mapped === "boolean" ? source.mapped : validCoordinates(source),
      hasNarrative: Boolean(source.hasNarrative || source.has_narrative),
      hasSize: Boolean(source.hasSize || source.has_size),
      startOrdinal: finiteInteger(source.startOrdinal == null ? source.start_ordinal : source.startOrdinal),
      endOrdinal: finiteInteger(source.endOrdinal == null ? source.end_ordinal : source.endOrdinal),
      lat: finiteNumber(source.lat),
      lon: finiteNumber(source.lon),
    };
  }

  function normalizeAnimalRow(row, projection, manifest) {
    if (Array.isArray(row)) {
      return {
        id: row[0],
        year: finiteInteger(row[1]),
        startYear: finiteInteger(row[1]),
        endYear: finiteInteger(row[2]) == null ? finiteInteger(row[1]) : finiteInteger(row[2]),
        datePrecision: lookupProjectionCode([projection, manifest], "animalReports", ["datePrecision", "date_precision"], row[3]),
        species: (Array.isArray(row[4]) ? row[4] : [row[4]]).filter(function (value) { return value != null; }).map(function (value) {
          return lookupProjectionCode([projection, manifest], "animalReports", ["speciesGroup", "species_group"], value);
        }),
        mapped: Boolean(row[5]),
        lat: null,
        lon: null,
        status: lookupProjectionCode([projection, manifest], "animalReports", ["status", "reviewStatus"], row[6]),
        startOrdinal: finiteInteger(row[7]),
        endOrdinal: finiteInteger(row[8]) == null ? finiteInteger(row[7]) : finiteInteger(row[8]),
      };
    }
    const source = row || {};
    return {
      id: source.id,
      year: finiteInteger(source.year),
      startYear: finiteInteger(source.startYear || source.start_year || source.year),
      endYear: finiteInteger(source.endYear || source.end_year || source.year),
      datePrecision: category(source.datePrecision || source.date_precision, "unknown"),
      species: (Array.isArray(source.species) ? source.species : (source.speciesGroups || [])).map(function (value) { return category(value, "unknown"); }),
      mapped: typeof source.mapped === "boolean" ? source.mapped : validCoordinates(source),
      lat: finiteNumber(source.lat),
      lon: finiteNumber(source.lon),
      status: category(source.status || source.reviewStatus, "unknown"),
      startOrdinal: finiteInteger(source.startOrdinal == null ? source.start_ordinal : source.startOrdinal),
      endOrdinal: finiteInteger(source.endOrdinal == null ? source.end_ordinal : source.endOrdinal),
    };
  }

  function normalizeContextProjections(input) {
    const source = input || {};
    const manifest = source.manifest || {};
    const cropProjection = source.cropCircles || source.crops || source.crop_circles || [];
    const animalProjection = source.animalReports || source.animals || source.animal_reports || [];
    return {
      manifest,
      cropCircles: projectionRows(cropProjection).map(function (row) {
        return normalizeCropRow(row, cropProjection, manifest);
      }),
      animalReports: projectionRows(animalProjection).map(function (row) {
        return normalizeAnimalRow(row, animalProjection, manifest);
      }),
    };
  }

  function contextRowInterval(row) {
    const startOrdinal = finiteInteger(row.startOrdinal);
    const endOrdinal = finiteInteger(row.endOrdinal);
    if (startOrdinal != null || endOrdinal != null) {
      const lower = startOrdinal == null ? endOrdinal : startOrdinal;
      const upper = endOrdinal == null ? startOrdinal : endOrdinal;
      return { start: Math.min(lower, upper), end: Math.max(lower, upper), source: "projection_interval" };
    }
    const startYear = finiteInteger(row.startYear == null ? row.year : row.startYear);
    const endYear = finiteInteger(row.endYear == null ? row.year : row.endYear);
    if (startYear == null && endYear == null) return null;
    const minimum = Math.min(startYear == null ? endYear : startYear, endYear == null ? startYear : endYear);
    const maximum = Math.max(startYear == null ? endYear : startYear, endYear == null ? startYear : endYear);
    return {
      start: ordinalFromCivil(minimum, 1, 1),
      end: ordinalFromCivil(maximum, 12, 31),
      source: "year_fallback_interval",
    };
  }

  function contextRowActive(row, range) {
    if (!range) return true;
    const interval = contextRowInterval(row);
    return Boolean(interval) && interval.end >= range.start && interval.start <= range.end;
  }

  function contextMembership(row, descriptor) {
    const active = contextRowActive(row, descriptor.activeRange);
    if (descriptor.mode === BASELINE_MODES.FULL_CATALOG) return { active, reference: true };
    if (descriptor.mode === BASELINE_MODES.PREVIOUS_EQUAL_DURATION && descriptor.referenceRange) {
      return {
        active,
        reference: !active && contextRowActive(row, descriptor.referenceRange),
      };
    }
    return {
      active,
      reference: Boolean(descriptor.activeRange) && Boolean(contextRowInterval(row)) && !active,
    };
  }

  function contextCohorts(rows, descriptor) {
    const active = [];
    const reference = [];
    rows.forEach(function (row) {
      const membership = contextMembership(row, descriptor);
      if (membership.active) active.push(row);
      if (membership.reference) reference.push(row);
    });
    return { active, reference };
  }

  function contextCountAggregation(rows, descriptor, dimensionAccessor) {
    const active = new Map();
    const reference = new Map();
    let activeReportCount = 0;
    let referenceReportCount = 0;
    rows.forEach(function (row) {
      const values = dimensionAccessor(row);
      const rawCategories = Array.isArray(values) ? values : [values];
      const categories = Array.from(new Set(rawCategories.map(function (value) {
        return category(value, "unknown");
      })));
      if (!categories.length) categories.push("unknown");
      const membership = contextMembership(row, descriptor);
      if (membership.active) activeReportCount += 1;
      if (membership.reference) referenceReportCount += 1;
      categories.forEach(function (value) {
        if (membership.active) increment(active, value, 1);
        if (membership.reference) increment(reference, value, 1);
      });
    });
    const activeTotal = Array.from(active.values()).reduce(function (sum, value) { return sum + value; }, 0);
    const referenceTotal = Array.from(reference.values()).reduce(function (sum, value) { return sum + value; }, 0);
    return {
      active,
      reference,
      activeMembershipCount: activeTotal,
      referenceMembershipCount: referenceTotal,
      activeReportCount,
      referenceReportCount,
    };
  }

  function contextCounts(rows, descriptor, dimensionAccessor, axisType) {
    const aggregation = contextCountAggregation(rows, descriptor, dimensionAccessor);
    const values = unionMapDatums(
      aggregation.active,
      aggregation.reference,
      aggregation.activeMembershipCount,
      aggregation.referenceMembershipCount,
      "context"
    );
    if (axisType) {
      values.sort(function (left, right) { return semanticAxisCompare(left.key, right.key, axisType); });
      values.forEach(function (datum, index) {
        datum.axisType = axisType;
        datum.axisIndex = index;
      });
    }
    return values;
  }

  function multiLabelContextCounts(rows, descriptor, dimensionAccessor, membershipUnit, membershipPolicy) {
    const aggregation = contextCountAggregation(rows, descriptor, dimensionAccessor);
    const metadata = {
      multiLabel: true,
      membershipUnit,
      unitOfAnalysis: membershipUnit,
      membershipPolicy,
      totalsMayExceedReportN: true,
      activeMembershipCount: aggregation.activeMembershipCount,
      referenceMembershipCount: aggregation.referenceMembershipCount,
      activeReportCount: aggregation.activeReportCount,
      referenceReportCount: aggregation.referenceReportCount,
      shareDenominator: "label memberships within each cohort",
    };
    const values = unionMapDatums(
      aggregation.active,
      aggregation.reference,
      aggregation.activeMembershipCount,
      aggregation.referenceMembershipCount,
      "context"
    ).map(function (datum) {
      return Object.assign({}, datum, metadata);
    });
    return { values, metadata };
  }

  function contextCoverage(rows, descriptor, definitions) {
    const activeRows = rows.filter(function (row) { return contextMembership(row, descriptor).active; });
    return definitions.map(function (definition) {
      const count = activeRows.reduce(function (sum, row) { return sum + (definition[1](row) ? 1 : 0); }, 0);
      return {
        label: definition[0],
        value: count,
        count,
        observed: count,
        total: activeRows.length,
        observedShare: round(rate(count, activeRows.length), 8),
      };
    });
  }

  function emptyContextDomain(enabled, status) {
    return { enabled: Boolean(enabled), status: status || (enabled ? "not_loaded" : "disabled"), time: [], coverage: [] };
  }

  function contextArtifactHash(manifest, domain, fallback) {
    const aliases = domain === "cropCircles" ? ["cropCircles", "crop_circles", "crops"] : ["animalReports", "animal_reports", "animals"];
    const artifacts = manifest && manifest.artifacts && typeof manifest.artifacts === "object" ? manifest.artifacts : {};
    for (const alias of aliases) {
      const entry = artifacts[alias];
      if (entry && typeof entry === "object" && (entry.sha256 || entry.sha_256)) return category(entry.sha256 || entry.sha_256, "not_provided");
    }
    return category(fallback, "not_provided");
  }

  function contextPrecisionLabel(rows) {
    const counts = new Map();
    rows.forEach(function (row) { increment(counts, row.datePrecision, 1); });
    const first = mapEntriesByCount(counts)[0];
    return first ? first[0] + " " + Math.round(rate(first[1], rows.length) * 100) + "%" : "No records";
  }

  function contextDomainSummary(cohorts, config) {
    const activeRows = cohorts.active;
    const mappedCount = activeRows.reduce(function (sum, row) { return sum + (row.mapped ? 1 : 0); }, 0);
    const missingCount = activeRows.reduce(function (sum, row) { return sum + (config.required(row) ? 0 : 1); }, 0);
    return {
      activeCount: activeRows.length,
      referenceCount: cohorts.reference.length,
      mappedCount,
      unmappedCount: activeRows.length - mappedCount,
      missingCount,
      unitLabel: config.unitLabel,
      sourceMixLabel: config.sourceMixLabel,
      datePrecisionLabel: contextPrecisionLabel(activeRows),
      locationPrecisionLabel: activeRows.length ? Math.round(rate(mappedCount, activeRows.length) * 100) + "% mapped" : "No records",
      policyWarning: config.policyWarning,
      policyWarnings: [config.policyWarning],
      datasetHash: config.datasetHash,
      missingnessPolicy: {
        unit: "records missing any required descriptive field",
        aggregation: "set union; each record contributes at most once",
        requiredFields: config.requiredFields,
      },
    };
  }

  function buildContext(contextProjections, contextLayers, descriptor, releaseHashes) {
    const projections = contextProjections || { cropCircles: [], animalReports: [] };
    const layers = contextLayers || {};
    const cropsEnabled = layers.cropCirclesEnabled !== false;
    const animalsEnabled = layers.animalMutilationsEnabled !== false;
    let crops = emptyContextDomain(cropsEnabled);
    let animals = emptyContextDomain(animalsEnabled);
    if (cropsEnabled && Array.isArray(projections.cropCircles) && projections.cropCircles.length) {
      const morphologyMembershipPolicy = "Multi-label field: each crop-circle record contributes once to every distinct morphology label. Membership totals may exceed crop-circle report N and are not mutually exclusive report counts.";
      const policyWarning = "Descriptive crop-circle records only; no authenticity or cross-domain association claim is made. Date-window cohorts use stored inclusive date intervals; records overlapping the active window are excluded from disjoint references. " + morphologyMembershipPolicy;
      const cropHash = contextArtifactHash(
        projections.manifest,
        "cropCircles",
        releaseHashes && (releaseHashes.cropCircles || releaseHashes.crop_circles)
      );
      const cropCohorts = contextCohorts(projections.cropCircles, descriptor);
      const morphologyMembership = multiLabelContextCounts(
        projections.cropCircles,
        descriptor,
        function (row) { return row.morphology.length ? row.morphology : ["unknown"]; },
        "crop-circle record-to-morphology-label memberships",
        morphologyMembershipPolicy
      );
      const cropSummary = contextDomainSummary(cropCohorts, {
        unitLabel: "crop-circle records",
        sourceMixLabel: "Crop-circle descriptive projection",
        policyWarning,
        datasetHash: cropHash,
        requiredFields: ["known date interval", "mapped state", "known morphology", "known crop type"],
        required: function (row) {
          return contextRowInterval(row) != null && typeof row.mapped === "boolean" && row.morphology.some(isKnown) && isKnown(row.crop);
        },
      });
      crops = {
        enabled: true,
        status: "ready",
        datasetHash: cropHash,
        activeCount: cropCohorts.active.length,
        referenceCount: cropCohorts.reference.length,
        totalProjectionRows: projections.cropCircles.length,
        summary: cropSummary,
        time: contextCounts(projections.cropCircles, descriptor, function (row) { return row.year == null ? "unknown" : String(row.year); }, "year"),
        morphology: morphologyMembership.values,
        morphologyMembership: morphologyMembership.metadata,
        morphologyMembershipUnit: morphologyMembership.metadata.membershipUnit,
        morphologyMembershipPolicy: morphologyMembership.metadata.membershipPolicy,
        crop: contextCounts(projections.cropCircles, descriptor, function (row) { return row.crop; }),
        complexity: contextCounts(projections.cropCircles, descriptor, function (row) { return row.complexity; }),
        coordinateClass: contextCounts(projections.cropCircles, descriptor, function (row) { return row.coordinateClass; }),
        classification: contextCounts(projections.cropCircles, descriptor, function (row) { return row.classification; }),
        coverage: contextCoverage(projections.cropCircles, descriptor, [
          ["Mapped", function (row) { return row.mapped; }],
          ["Known date", function (row) { return contextRowInterval(row) != null; }],
          ["Known morphology", function (row) { return row.morphology.some(isKnown); }],
          ["Known crop", function (row) { return isKnown(row.crop); }],
          ["Known classification", function (row) { return isKnown(row.classification); }],
          ["Known origin status", function (row) { return isKnown(row.originStatus); }],
          ["Known complexity", function (row) { return isKnown(row.complexity); }],
          ["Known coordinate class", function (row) { return isKnown(row.coordinateClass); }],
          ["Narrative available", function (row) { return row.hasNarrative; }],
          ["Size available", function (row) { return row.hasSize; }],
        ]),
        policyWarning,
      };
    }
    if (animalsEnabled && Array.isArray(projections.animalReports) && projections.animalReports.length) {
      const speciesMembershipPolicy = "Multi-label field: each animal report contributes once to every distinct species-group label. Membership totals may exceed animal report N and are not mutually exclusive report counts.";
      const policyWarning = "Descriptive animal-report records only; no cause or cross-domain association claim is made. Date-window cohorts use stored inclusive date intervals; records overlapping the active window are excluded from disjoint references. " + speciesMembershipPolicy;
      const animalHash = contextArtifactHash(
        projections.manifest,
        "animalReports",
        releaseHashes && (releaseHashes.animalReports || releaseHashes.animal_reports)
      );
      const animalCohorts = contextCohorts(projections.animalReports, descriptor);
      const speciesMembership = multiLabelContextCounts(
        projections.animalReports,
        descriptor,
        function (row) { return row.species.length ? row.species : ["unknown"]; },
        "animal-report-to-species-group memberships",
        speciesMembershipPolicy
      );
      const animalSummary = contextDomainSummary(animalCohorts, {
        unitLabel: "animal reports",
        sourceMixLabel: "Animal-report descriptive projection",
        policyWarning,
        datasetHash: animalHash,
        requiredFields: ["known date interval", "mapped state", "known species group", "known review status"],
        required: function (row) {
          return contextRowInterval(row) != null && typeof row.mapped === "boolean" && row.species.some(isKnown) && isKnown(row.status);
        },
      });
      animals = {
        enabled: true,
        status: "ready",
        datasetHash: animalHash,
        activeCount: animalCohorts.active.length,
        referenceCount: animalCohorts.reference.length,
        totalProjectionRows: projections.animalReports.length,
        summary: animalSummary,
        time: contextCounts(projections.animalReports, descriptor, function (row) { return row.year == null ? "unknown" : String(row.year); }, "year"),
        species: speciesMembership.values,
        speciesMembership: speciesMembership.metadata,
        speciesMembershipUnit: speciesMembership.metadata.membershipUnit,
        speciesMembershipPolicy: speciesMembership.metadata.membershipPolicy,
        datePrecision: contextCounts(projections.animalReports, descriptor, function (row) { return row.datePrecision; }),
        statusBreakdown: contextCounts(projections.animalReports, descriptor, function (row) { return row.status; }),
        coverage: contextCoverage(projections.animalReports, descriptor, [
          ["Mapped", function (row) { return row.mapped; }],
          ["Known date", function (row) { return contextRowInterval(row) != null; }],
          ["Known species group", function (row) { return row.species.some(isKnown); }],
          ["Known review status", function (row) { return isKnown(row.status); }],
        ]),
        policyWarning,
      };
    }
    return { crops, animals };
  }

  function sourceMixLabel(accumulator) {
    const entries = mapEntriesByCount(accumulator.sources);
    if (!entries.length) return "No reports";
    return entries.slice(0, 3).map(function (entry) {
      return entry[0] + " " + Math.round(rate(entry[1], accumulator.total) * 100) + "%";
    }).join(", ");
  }

  function comparisonPreviewForFamily(family, key) {
    if (family === "craft") return { kind: "filter", patch: { craftTypes: [key] } };
    if (family === "source") return { kind: "filter", patch: { sources: [key] } };
    if (family === "location_precision") return { kind: "filter", patch: { precisions: [key] } };
    if (family === "date_precision" && key === "exact_day") {
      return { kind: "filter", patch: { hideNonExactDates: true } };
    }
    return null;
  }

  function adjustedEvidenceSummary(balancedFamilies) {
    const labels = {
      craft: "Craft",
      time_month: "Calendar month",
      source: "Source",
      date_precision: "Date precision",
      location_precision: "Location precision",
      coordinate_source: "Coordinate source",
      craft_confidence: "Craft confidence",
    };
    const candidates = [];
    Object.keys(labels).forEach(function (family) {
      const result = balancedFamilies[family];
      (result && Array.isArray(result.comparisons) ? result.comparisons : []).forEach(function (comparison) {
        if (comparison.adjustedEffect == null || !Number.isFinite(Number(comparison.adjustedEffect))) return;
        const interval = comparison.interval;
        const effect = Number(comparison.adjustedEffect);
        const conservative = interval && Number.isFinite(Number(interval.lower)) && Number.isFinite(Number(interval.upper))
          ? (effect < 0 ? Math.abs(Math.min(0, Number(interval.upper))) : Math.max(0, Number(interval.lower)))
          : 0;
        const item = Object.assign({
          family,
          key: comparison.key,
          label: labels[family] + ": " + String(comparison.key).replace(/_/g, " "),
          value: effect,
          difference: effect,
          observed: comparison.observedCount,
          observedCount: comparison.observedCount,
          reference: comparison.referenceCount,
          referenceCount: comparison.referenceCount,
          conservativeEffect: round(conservative, 8),
          preview: comparisonPreviewForFamily(family, comparison.key),
        }, comparisonSchemaFields(comparison));
        candidates.push(item);
      });
    });
    return candidates.sort(function (left, right) {
      return Number(Boolean(right.inferenceEligible)) - Number(Boolean(left.inferenceEligible)) ||
        right.conservativeEffect - left.conservativeEffect ||
        Math.abs(right.adjustedEffect) - Math.abs(left.adjustedEffect) ||
        String(left.family).localeCompare(String(right.family)) ||
        String(left.key).localeCompare(String(right.key));
    }).slice(0, 16);
  }

  function internalAssociationOutputs(active, associationsValue, datasetHash, artifactHashes) {
    const associations = Array.isArray(associationsValue) ? associationsValue : [];
    const evidence = [];
    const patterns = [];
    associations.forEach(function (definition) {
      const association = definition && definition.result;
      const metadata = association && association.metadata || {};
      const covariates = Array.isArray(metadata.adjustmentCovariates) ? metadata.adjustmentCovariates.slice() : [];
      (association && Array.isArray(association.fullCells) ? association.fullCells : []).forEach(function (cell) {
        if (!cell.estimateAvailable || cell.expectedCount == null || cell.expectedCount <= 0) return;
        const ratioValue = cell.observedCount / cell.expectedCount;
        const log2Effect = ratioValue > 0 ? Math.log2(ratioValue) : null;
        const interval = cell.observedCount > 0 && ratioValue > 0 ? {
          lower: round((Math.log(ratioValue) - (1.959963984540054 / Math.sqrt(cell.observedCount))) / Math.LN2, 8),
          upper: round((Math.log(ratioValue) + (1.959963984540054 / Math.sqrt(cell.observedCount))) / Math.LN2, 8),
          level: 0.95,
          method: "conditional_count_log_ratio_normal",
        } : null;
        const base = {
          family: definition.family,
          key: cell.key,
          label: definition.label + ": " + cell.row + " / " + cell.column,
          title: definition.label + ": " + cell.row + " / " + cell.column,
          chartId: definition.chartId,
          row: cell.row,
          column: cell.column,
          observed: cell.observedCount,
          observedCount: cell.observedCount,
          expected: cell.expectedCount,
          expectedCount: cell.expectedCount,
          conditionalExpectedCount: cell.expectedCount,
          value: log2Effect == null ? 0 : round(log2Effect, 8),
          adjustedEffect: log2Effect == null ? null : round(log2Effect, 8),
          effectSize: {
            measure: "log2_observed_expected_enrichment",
            estimate: log2Effect == null ? null : round(log2Effect, 8),
            unit: "log2 ratio",
          },
          observedExpectedRatio: round(ratioValue, 8),
          standardizedResidual: cell.standardizedResidual,
          interval,
          uncertainty: interval,
          pValue: cell.pValue,
          pValueMethod: cell.pValueMethod,
          permutationCount: cell.permutationCount,
          permutationSeed: cell.permutationSeed,
          qValue: cell.qValue,
          cramersV: metadata.cramersV,
          tableCramersV: metadata.cramersV,
          activeN: active.total,
          referenceN: 0,
          supportedActiveN: active.total,
          supportedReferenceN: 0,
          commonSupportRate: null,
          supportingStrataCount: cell.supportingStrataCount,
          estimateAvailable: true,
          tested: cell.tested,
          inferenceEligible: cell.inferenceEligible,
          statisticallyQualified: cell.statisticallyQualified,
          patternFinderEligible: false,
          sensitivityStatus: "not_assessed_for_internal_cell",
          suppressionStatus: cell.suppressionStatus,
          suppressionReasons: cell.suppressionReasons.slice(),
          covariates,
          comparisonState: COMPARISON_STATES.WHOLE_CORPUS_STRUCTURE,
          comparisonBasis: "conditional_expectation",
          estimatorVersion: ESTIMATOR_VERSION,
          datasetHash: datasetHash || "not_provided",
          artifactHashes: Object.assign({}, artifactHashes || {}),
          exploratory: true,
          policyLabel: EXPLORATORY_POLICY,
        };
        evidence.push(base);
        const nontrivialEffect = ratioValue >= 1.25 || ratioValue <= 0.80;
        if (
          definition.sensitivityAssessed === true &&
          active.total >= 200 &&
          cell.observedCount >= 25 &&
          cell.expectedCount >= 10 &&
          cell.statisticallyQualified &&
          nontrivialEffect
        ) {
          const direction = ratioValue >= 1 ? "higher" : "lower";
          const finding = Object.assign({}, base, {
            summary: base.label + " has " + cell.observedCount + " observed reports versus " + round(cell.expectedCount, 1) + " conditionally expected.",
            effectLabel: round(ratioValue, 2) + "\u00d7 conditional expectation",
            intervalLabel: interval
              ? "95% log2-ratio interval " + interval.lower + " to " + interval.upper
              : "No stable ratio interval is available.",
            direction,
            relativeEnrichment: round(ratioValue, 8),
            conservativeEffect: interval
              ? round(direction === "higher" ? Math.max(0, interval.lower) : Math.max(0, -interval.upper), 8)
              : 0,
            nontrivialEffect: true,
            findingLane: "within_corpus_association",
            sourceStability: { status: "not_assessed_for_internal_cell", stable: false, sourcesTested: 0 },
            regionStability: { status: "not_assessed_for_internal_cell", stable: false, regionsTested: 0 },
          });
          patterns.push(finding);
        }
      });
    });
    evidence.sort(function (left, right) {
      return Number(Boolean(right.statisticallyQualified)) - Number(Boolean(left.statisticallyQualified)) ||
        Math.abs(right.standardizedResidual || 0) - Math.abs(left.standardizedResidual || 0) ||
        String(left.family).localeCompare(String(right.family)) || String(left.key).localeCompare(String(right.key));
    });
    patterns.sort(function (left, right) {
      return right.conservativeEffect - left.conservativeEffect ||
        String(left.family).localeCompare(String(right.family)) || String(left.key).localeCompare(String(right.key));
    });
    return { evidence: evidence.slice(0, 16), patterns };
  }

  function precisionLabel(map, total) {
    const first = mapEntriesByCount(map)[0];
    if (!first) return "No reports";
    return first[0] + " " + Math.round(rate(first[1], total) * 100) + "%";
  }

  function requestedDomainSet(options) {
    const requested = Array.isArray(options && options.selectedDomains) ? options.selectedDomains : [];
    return new Set(requested.map(function (domain) {
      return String(domain || "").trim().toLowerCase().replace(/[^a-z0-9]+/g, "_");
    }).filter(Boolean));
  }

  function domainRequested(requested, domain) {
    if (!(requested instanceof Set) || requested.size === 0) return true;
    return requested.has(String(domain || "").trim().toLowerCase().replace(/[^a-z0-9]+/g, "_"));
  }

  function deferredTimeSection() {
    return {
      series: [], annualSeries: [], adaptiveBinning: null, decades: [], monthYear: [], rolling: [],
      sourceBalanced: [], annualSourceBalanced: [], bursts: [], monthComparison: [],
      monthByCraft: deferredAssociation("recurring month-by-craft", ["source", "coarse_geography", "coordinate_class", "era"]),
      comparisonMetadata: { inferenceDeferred: true, status: "not_requested" },
      inferenceDeferred: true,
      status: "not_requested",
    };
  }

  function deferredCraftSection() {
    return {
      distribution: [], reportTypes: [], confidence: [], source: [], trends: [], residuals: [], residualAudit: [], comparisons: [],
      byEra: deferredAssociation("craft-by-era", ["source", "coarse_geography", "coordinate_class"]),
      byGeography: deferredAssociation("craft-by-geography", ["source", "era", "coordinate_class"]),
      sourceAssociation: deferredAssociation("craft-by-source", ["coarse_geography", "coordinate_class", "era"]).metadata,
      comparisonMetadata: { inferenceDeferred: true, status: "not_requested" },
      inferenceDeferred: true,
      status: "not_requested",
    };
  }

  function deferredGeographySection() {
    return {
      gridDefinition: null, cells: [], byTime: [],
      byEra: deferredAssociation("geography-by-era", ["source", "coordinate_class", "craft"]),
      heatmap: { cells: [], fullCells: [], metadata: { status: "not_requested", inferenceDeferred: true } },
      comparisons: [],
      comparisonMetadata: { inferenceDeferred: true, status: "not_requested" },
      equalAreaMap: null,
      inferenceDeferred: true,
      status: "not_requested",
    };
  }

  function deferredSourcesQualitySection() {
    return {
      sourceComposition: [], sourceByTime: [], missingness: [], audit: [], classifierAudit: [], fieldAudit: [],
      comparisonFamilies: { source: [], datePrecision: [], locationPrecision: [], coordinateSource: [], craftConfidence: [] },
      inferenceDeferred: true,
      status: "not_requested",
    };
  }

  function durationComparisonStrata(active, reference, key) {
    const activeTotals = active.durationInferentialStrataTotals || new Map();
    const referenceTotals = reference.durationInferentialStrataTotals || new Map();
    const activeCounts = active.durationInferentialBinStrata.get(key) || new Map();
    const referenceCounts = reference.durationInferentialBinStrata.get(key) || new Map();
    const strata = new Set([].concat(sortedKeys(activeTotals), sortedKeys(referenceTotals)));
    return Array.from(strata).map(function (stratum) {
      return {
        key: stratum,
        activeCount: mapCount(activeCounts, stratum),
        activeTotal: mapCount(activeTotals, stratum),
        referenceCount: mapCount(referenceCounts, stratum),
        referenceTotal: mapCount(referenceTotals, stratum),
      };
    });
  }

  function durationCoverage(accumulator) {
    return {
      catalogRows: accumulator.total,
      rawDurationRows: accumulator.durationRawRows,
      rawDurationCoverage: round(rate(accumulator.durationRawRows, accumulator.total), 8),
      normalizedRows: accumulator.durationNormalizedRows,
      normalizedCoverage: round(rate(accumulator.durationNormalizedRows, accumulator.total), 8),
      descriptiveBinnedRows: accumulator.durationDescriptiveRows,
      inferentialBinnedRows: accumulator.durationInferentialRows,
      normalizedSources: mapEntriesByCount(accumulator.durationNormalizedSources).map(function (entry) {
        return { source: entry[0], rows: entry[1] };
      }),
      inferentialSources: mapEntriesByCount(accumulator.durationInferentialSources).map(function (entry) {
        return { source: entry[0], rows: entry[1] };
      }),
      statusCounts: mapEntriesByCount(accumulator.durationStatusCounts).map(function (entry) {
        return { status: entry[0], rows: entry[1] };
      }),
    };
  }

  function suppressDurationComparison(comparison, reasonsValue) {
    const reasons = Array.from(new Set((comparison.suppressionReasons || []).concat(reasonsValue || [])));
    comparison.inferenceEligible = false;
    comparison.suppressionStatus = "suppressed";
    comparison.suppressionReasons = reasons;
    comparison.suppression = { status: "suppressed", reasons: reasons.slice() };
    comparison.pValue = null;
    comparison.qValue = null;
    comparison.interval = null;
    comparison.uncertainty = null;
    return comparison;
  }

  function buildDurationAssessment(active, reference, descriptor, optionsValue) {
    const options = optionsValue || {};
    const artifact = options.durationArtifact && typeof options.durationArtifact === "object"
      ? options.durationArtifact
      : null;
    const loaded = options.durationProjectionLoaded === true && artifact;
    const activeCoverage = durationCoverage(active);
    const referenceCoverage = durationCoverage(reference);
    const empty = {
      schemaId: "ufo-timeline-analysis-duration-assessment-v1.0.0",
      estimatorVersion: ESTIMATOR_VERSION,
      releaseId: artifact ? String(artifact.releaseId || "") : "",
      artifactHashes: artifact ? Object.assign({}, artifact.artifactHashes || {}) : {},
      status: "data_unavailable",
      readinessStatus: "data_unavailable",
      coverage: { active: activeCoverage, reference: referenceCoverage },
      distribution: [],
      comparisons: [],
      comparisonMetadata: {
        status: "data_unavailable",
        covariates: ["source", "era", "macroregion"],
        fdrFamily: "duration_bins_v1",
      },
      negativeControls: artifact ? Object.assign({}, artifact.negativeControls || {}) : {},
      patternFinderEligible: false,
      suppressionReasons: ["duration_artifact_not_loaded"],
      warnings: [],
    };
    if (!loaded) return empty;

    const readiness = artifact.readiness || {};
    const policy = artifact.policy || {};
    const distribution = DURATION_BIN_ORDER.map(function (key) {
      const activeCount = mapCount(active.durationDescriptiveBins, key);
      const referenceCount = mapCount(reference.durationDescriptiveBins, key);
      return {
        key,
        label: DURATION_BIN_LABELS[key] || key,
        activeCount,
        referenceCount,
        activeShare: round(rate(activeCount, active.durationDescriptiveRows), 8),
        referenceShare: round(rate(referenceCount, reference.durationDescriptiveRows), 8),
        measurementClass: "descriptive_includes_source_declared_approximate_values",
        inferenceEligible: false,
      };
    });
    const comparisonUnavailable = [
      COMPARISON_STATES.WHOLE_CORPUS_STRUCTURE,
      COMPARISON_STATES.UNAVAILABLE_NO_REFERENCE,
      COMPARISON_STATES.UNAVAILABLE_SELF_COMPARISON,
    ].indexOf(descriptor.comparisonState) !== -1;
    let comparisons = [];
    let comparisonStatus = descriptor.comparisonState;
    if (options.inferenceDeferred) {
      comparisonStatus = "deferred";
    } else if (!comparisonUnavailable) {
      const activeSources = active.durationInferentialSources.size;
      const referenceSources = reference.durationInferentialSources.size;
      const minimumBinN = Math.max(20, finiteInteger(policy.minimumActiveAndReferenceBinN) || 20);
      const minimumSources = 2;
      comparisons = DURATION_BIN_ORDER.map(function (key) {
        const comparison = balancedCommonSupportComparison(durationComparisonStrata(active, reference, key), {
          activeN: active.durationInferentialRows,
          referenceN: reference.durationInferentialRows,
          descriptive: descriptor.descriptive,
          covariates: ["source", "era", "macroregion"],
          minimumCommonSupport: finiteNumber(policy.minimumCommonSupport) == null ? 0.8 : finiteNumber(policy.minimumCommonSupport),
          bootstrapReplicates: options.bootstrapReplicates,
          seed: [options.datasetHash || "not_provided", descriptor.mode, "duration", key].join("|"),
        });
        comparison.family = "duration";
        comparison.key = key;
        comparison.label = DURATION_BIN_LABELS[key] || key;
        comparison.fdrFamily = "duration_bins_v1";
        comparison.patternFinderEligible = false;
        comparison.measurementClass = "exact_or_closed_range_same_bin_only";
        const reasons = [];
        if (comparison.observedCount < minimumBinN) reasons.push("active_bin_n_below_" + minimumBinN);
        if (comparison.referenceCount < minimumBinN) reasons.push("reference_bin_n_below_" + minimumBinN);
        if (activeSources < minimumSources || referenceSources < minimumSources) {
          reasons.push("minimum_independent_sources");
        }
        if (reasons.length) suppressDurationComparison(comparison, reasons);
        comparison.minimumActiveAndReferenceBinN = minimumBinN;
        comparison.minimumIndependentSources = minimumSources;
        comparison.activeIndependentSources = activeSources;
        comparison.referenceIndependentSources = referenceSources;
        return comparison;
      });
      assignEligibleBenjaminiHochberg(comparisons);
      comparisonStatus = comparisons.some(function (comparison) { return comparison.inferenceEligible; })
        ? "ready_inferential"
        : "suppressed";
    }

    const globalReady = String(readiness.status || "") === "ready_descriptive";
    const activeReady = active.durationDescriptiveRows > 0 && active.durationNormalizedRows > 0;
    const anyInference = comparisons.some(function (comparison) { return comparison.inferenceEligible; });
    const status = !globalReady || !activeReady
      ? "not_estimable"
      : (anyInference ? "ready_descriptive_with_inferential_comparison" : "ready_descriptive");
    const suppressionReasons = [];
    if (!globalReady) suppressionReasons.push("global_duration_readiness_failed");
    if (!active.durationNormalizedRows) suppressionReasons.push("no_normalized_duration_in_active_cohort");
    if (!active.durationDescriptiveRows) suppressionReasons.push("no_single_bin_duration_in_active_cohort");
    return {
      schemaId: "ufo-timeline-analysis-duration-assessment-v1.0.0",
      estimatorVersion: ESTIMATOR_VERSION,
      releaseId: String(artifact.releaseId || ""),
      artifactHashes: Object.assign({}, artifact.artifactHashes || {}),
      status,
      readinessStatus: String(readiness.status || "not_estimable"),
      assessmentLane: String(readiness.assessmentLane || "descriptive_with_runtime_gated_comparisons"),
      coverage: { active: activeCoverage, reference: referenceCoverage },
      distribution,
      comparisons,
      comparisonMetadata: {
        status: comparisonStatus,
        comparisonState: descriptor.comparisonState,
        covariates: ["source", "era", "macroregion"],
        minimumCommonSupport: finiteNumber(policy.minimumCommonSupport) == null ? 0.8 : finiteNumber(policy.minimumCommonSupport),
        minimumActiveAndReferenceBinN: Math.max(20, finiteInteger(policy.minimumActiveAndReferenceBinN) || 20),
        fdrFamily: "duration_bins_v1",
        approximateValuesExcludedFromInference: true,
        binSpanningIntervalsExcludedFromInference: true,
      },
      negativeControls: Object.assign({}, artifact.negativeControls || {}),
      patternFinderEligible: false,
      suppressionReasons,
      warnings: Array.isArray(readiness.warnings) ? readiness.warnings.slice() : [],
      policy: Object.assign({}, policy),
    };
  }

  function computeAnalysis(optionsValue) {
    const options = optionsValue || {};
    const inferenceDeferred = options.quickMode === true || String(options.analysisPhase || "").trim().toLowerCase() === "quick";
    const requestedDomains = requestedDomainSet(options);
    const geographyProjectionLoaded = options.geographyProjectionLoaded !== false;
    const mode = normalizeBaselineMode(options.baselineMode);
    const fullTimeRange = Boolean(options.fullTimeRange) || ["full", "all", "all_time"].indexOf(
      String(options.timeRangeMode || "").trim().toLowerCase()
    ) !== -1;
    const activeRange = fullTimeRange ? null : normalizeRange(options.timeRangeStartOrdinal, options.timeRangeEndOrdinal);
    const wholeCorpusStructure = fullTimeRange || !activeRange;
    const descriptor = baselineDescriptor(mode, activeRange, wholeCorpusStructure);
    const active = createAccumulator("active");
    const reference = createAccumulator("reference");
    const quickCoreAccumulator = inferenceDeferred &&
      !domainRequested(requestedDomains, "craft") &&
      !domainRequested(requestedDomains, "geography");
    iterateRows(options, function (rowValue) {
      const row = rowValue || {};
      const membership = membershipForRow(row, options, descriptor);
      if (membership.active) (quickCoreAccumulator ? addQuickCoreRow : addRow)(active, row);
      if (membership.reference) (quickCoreAccumulator ? addQuickCoreRow : addRow)(reference, row);
    });

    const analysisMode = wholeCorpusStructure
      ? ANALYSIS_MODES.WHOLE_CORPUS_STRUCTURE
      : ANALYSIS_MODES.COHORT_COMPARISON;
    const comparisonState = resolveComparisonState(descriptor, active, reference);
    descriptor.comparisonState = comparisonState;

    const datasetHash = category(options.datasetHash, "not_provided");
    const artifactHashes = Object.assign({}, options.contextReleaseHashes || {}, options.artifactHashes || {});
    const coverage = buildCoverage(active, reference);
    const comparisonOptions = {
      datasetHash,
      artifactHashes,
      minimumCommonSupport: options.minimumCommonSupport,
      bootstrapReplicates: options.bootstrapReplicates,
    };
    const comparisonUnavailable = comparisonState === COMPARISON_STATES.WHOLE_CORPUS_STRUCTURE ||
      comparisonState === COMPARISON_STATES.UNAVAILABLE_NO_REFERENCE ||
      comparisonState === COMPARISON_STATES.UNAVAILABLE_SELF_COMPARISON;
    const balancedFamilies = inferenceDeferred
      ? deferredBalancedFamilyComparisons(descriptor, comparisonOptions)
      : (comparisonUnavailable
        ? unavailableBalancedFamilyComparisons(descriptor, comparisonState, comparisonOptions)
        : buildBalancedFamilyComparisons(active, reference, descriptor, comparisonOptions));
    const mapGrid6Comparisons = inferenceDeferred
      ? deferredMapGrid6Comparisons(descriptor, comparisonOptions)
      : (comparisonUnavailable
        ? unavailableMapGrid6Comparisons(descriptor, comparisonState, comparisonOptions)
        : buildMapGrid6Comparisons(active, reference, descriptor, comparisonOptions));
    const patternFamilies = inferenceDeferred
      ? FAMILY_ORDER.reduce(function (families, family) { families[family] = []; return families; }, {})
      : buildPatternFamilies(active, reference, datasetHash, descriptor, balancedFamilies, artifactHashes);
    const evidenceSummary = inferenceDeferred ? [] : adjustedEvidenceSummary(balancedFamilies);
    if (!inferenceDeferred) populatePatternSourceSensitivity(active, reference, patternFamilies);
    if (!geographyProjectionLoaded) {
      patternFamilies.geography = [];
      for (let index = evidenceSummary.length - 1; index >= 0; index -= 1) {
        if (String(evidenceSummary[index] && evidenceSummary[index].family || "") === "geography") {
          evidenceSummary.splice(index, 1);
        }
      }
    }
    const patterns = [];
    FAMILY_ORDER.forEach(function (family) {
      (patternFamilies[family] || []).forEach(function (pattern) { patterns.push(pattern); });
    });
    const patternGroups = {
      stableMultiSource: patterns.filter(function (pattern) {
        return pattern.sourceStability && pattern.sourceStability.status === "stable_multi_source";
      }),
      sourceSensitive: patterns.filter(function (pattern) {
        return pattern.sourceStability && pattern.sourceStability.status === "source_sensitive";
      }),
      sourceSpecific: patterns.filter(function (pattern) {
        return pattern.sourceStability && ["source_specific_dimension", "single_source_only"].indexOf(pattern.sourceStability.status) !== -1;
      }),
      stableMultiSourceContent: patterns.filter(function (pattern) {
        return pattern.findingLane === "stable_multi_source_content";
      }),
      sourceOrRegionSensitive: patterns.filter(function (pattern) {
        return pattern.findingLane === "source_or_region_sensitive";
      }),
      collectionAndQuality: patterns.filter(function (pattern) {
        return pattern.findingLane === "collection_and_quality";
      }),
    };
    const policyWarnings = [
      EXPLORATORY_POLICY,
      "Report density is not incidence, risk, or phenomenon likelihood.",
      "Generalized coordinates are not exact sites and cannot support kilometer-scale claims.",
      "No chronology trace segment, viewer bearing, or inferred travel direction is used in this analysis.",
    ];
    if (descriptor.warning) policyWarnings.push(descriptor.warning);
    if (datasetHash === "not_provided") policyWarnings.push("Catalog dataset hash was not provided for this computation.");

    const sectionOptions = { inferenceDeferred, comparisonState, analysisMode };
    const time = inferenceDeferred && !domainRequested(requestedDomains, "time")
      ? deferredTimeSection()
      : buildTime(active, reference, sectionOptions);
    time.duration = buildDurationAssessment(active, reference, descriptor, {
      durationProjectionLoaded: options.durationProjectionLoaded,
      durationArtifact: options.durationArtifact,
      inferenceDeferred,
      bootstrapReplicates: options.bootstrapReplicates,
      datasetHash,
    });
    time.monthComparison = balancedFamilies.time_month.comparisons;
    time.comparisonMetadata = balancedFamilies.time_month.metadata;
    time.bursts.forEach(function (burst) {
      burst.patternFinderEligible = false;
      burst.methodStatus = "legacy_descriptive_only";
    });
    const craft = inferenceDeferred && !domainRequested(requestedDomains, "craft")
      ? deferredCraftSection()
      : buildCraft(active, reference, sectionOptions);
    applyComparisonSchema(craft.distribution, balancedFamilies.craft);
    craft.comparisons = balancedFamilies.craft.comparisons;
    craft.comparisonMetadata = balancedFamilies.craft.metadata;
    const geography = inferenceDeferred && !domainRequested(requestedDomains, "geography")
      ? deferredGeographySection()
      : (!geographyProjectionLoaded
        ? Object.assign(deferredGeographySection(), {
            status: "data_unavailable",
            inferenceDeferred: false,
            loadingReason: "country_projection_not_loaded",
            message: "Country geography loads when the Geography dashboard is first opened.",
          })
        : buildGeography(active, reference, sectionOptions));
    applyComparisonSchema(geography.cells, balancedFamilies.geography);
    if (geography.countryMap) {
      geography.countryChoropleth = Object.assign({}, geography.countryMap, {
        countries: geography.cells,
      });
    }
    geography.heatmap = qualifySparseHeatmapCells(geography.cells.map(function (cell) {
      return Object.assign({}, cell, {
        row: cell.coordinateClass,
        column: cell.country || cell.displayLabel || "Unknown country",
        expected: cell.minimumExpectedCell,
        expectedCount: cell.minimumExpectedCell,
        estimateAvailable: cell.observed > 0 || cell.referenceCount > 0 || cell.adjustedEffect != null,
        comparisonState,
      });
    }), {
      maximumRows: 12,
      maximumColumns: 12,
      minimumExpectedCell: 10,
      rowAxisType: "category",
      columnAxisType: "geography",
    });
    geography.comparisons = balancedFamilies.geography.comparisons;
    geography.comparisonMetadata = balancedFamilies.geography.metadata;
    geography.equalAreaMap = geography.status === "not_requested" || geography.status === "data_unavailable"
      ? null
      : buildLambertEqualAreaMap6x12(active, reference, mapGrid6Comparisons);
    const sourcesQuality = inferenceDeferred && !domainRequested(requestedDomains, "sources_quality")
      ? deferredSourcesQualitySection()
      : buildSourcesQuality(active, reference, sectionOptions);
    applyComparisonSchema(sourcesQuality.sourceComposition, balancedFamilies.source);
    const qualityFamilyByRow = {
      "Date precision": "date_precision",
      "Location precision": "location_precision",
      "Coordinate source": "coordinate_source",
      "Craft confidence": "craft_confidence",
    };
    sourcesQuality.fieldAudit.forEach(function (datum) {
      const family = qualityFamilyByRow[datum.row];
      const comparisonFamily = family ? balancedFamilies[family] : null;
      Object.assign(datum, comparisonSchemaFields(
        comparisonFamily ? comparisonFamily.byKey.get(datum.column) : null,
        comparisonFamily && comparisonFamily.metadata && comparisonFamily.metadata.comparisonState
      ));
    });
    sourcesQuality.comparisonFamilies = {
      source: balancedFamilies.source.comparisons,
      datePrecision: balancedFamilies.date_precision.comparisons,
      locationPrecision: balancedFamilies.location_precision.comparisons,
      coordinateSource: balancedFamilies.coordinate_source.comparisons,
      craftConfidence: balancedFamilies.craft_confidence.comparisons,
    };
    if (!inferenceDeferred && analysisMode === ANALYSIS_MODES.WHOLE_CORPUS_STRUCTURE) {
      const internalDescriptors = [
        { family: "month_by_craft", label: "Recurring month by craft", chartId: "analysis-month-year", result: time.monthByCraft },
        { family: "craft_by_era", label: "Craft by era", chartId: "analysis-craft-era", result: craft.byEra },
        { family: "craft_by_geography", label: "Craft by geography", chartId: "analysis-craft-geography", result: craft.byGeography },
        { family: "geography_by_era", label: "Geography by era", chartId: "analysis-geography-time", result: geography.byEra },
        { family: "classifier_consistency", label: "Classifier consistency", chartId: "analysis-classifier-audit", result: sourcesQuality.classifierAuditAssociation },
      ].filter(function (entry) {
        return geographyProjectionLoaded || ["craft_by_geography", "geography_by_era"].indexOf(entry.family) === -1;
      });
      const internalOutputs = internalAssociationOutputs(active, internalDescriptors, datasetHash, artifactHashes);
      evidenceSummary.splice(0, evidenceSummary.length, ...internalOutputs.evidence);
      patternFamilies.internal_structure = internalOutputs.patterns;
      internalOutputs.patterns.forEach(function (pattern) { patterns.push(pattern); });
      patternGroups.withinCorpusAssociation = internalOutputs.patterns.slice();
    } else {
      patternGroups.withinCorpusAssociation = [];
    }
    const comparisonCatalog = {};
    FAMILY_ORDER.forEach(function (family) {
      comparisonCatalog[family] = {
        results: balancedFamilies[family].comparisons,
        metadata: balancedFamilies[family].metadata,
      };
    });
    comparisonCatalog.geography_map_6x12 = {
      results: mapGrid6Comparisons.comparisons,
      metadata: mapGrid6Comparisons.metadata,
    };
    const result = {
      schemaVersion: SCHEMA_VERSION,
      estimatorVersion: ESTIMATOR_VERSION,
      analysisMode,
      comparisonState,
      geographyProjection: {
        loaded: geographyProjectionLoaded,
        status: geographyProjectionLoaded ? "ready" : "data_unavailable",
        artifactHash: String(artifactHashes.ufoGeography || ""),
      },
      unitOfAnalysis: "reports",
      selectedDomains: Array.isArray(options.selectedDomains) ? options.selectedDomains.slice() : [],
      analysisPhase: inferenceDeferred ? "quick" : "full",
      inferenceDeferred,
      inference: {
        status: inferenceDeferred ? "deferred" : "complete",
        deferred: inferenceDeferred,
        reason: inferenceDeferred ? "quick_core_inference_deferred" : "",
        estimatorVersion: ESTIMATOR_VERSION,
        comparisonState,
      },
      baseline: descriptor,
      artifactHashes,
      cohorts: {
        active: { n: active.total },
        reference: { n: reference.total },
      },
      summary: {
        activeCount: active.total,
        referenceCount: reference.total,
        mappedCount: active.mapped,
        unmappedCount: active.total - active.mapped,
        missingCount: active.rowsMissingAny,
        unitLabel: "reports",
        sourceMixLabel: sourceMixLabel(active),
        datePrecisionLabel: precisionLabel(active.datePrecisions, active.total),
        locationPrecisionLabel: precisionLabel(active.locationPrecisions, active.total),
        policyWarnings,
        datasetHash,
        estimatorVersion: ESTIMATOR_VERSION,
        artifactHashes,
        analysisMode,
        comparisonState,
        missingnessPolicy: {
          unit: "rows missing any required analysis field",
          aggregation: "set union; each report contributes at most once",
          requiredFields: ["known date ordinal", "mapped point", "known craft classification", "known source"],
        },
      },
      overview: {
        coverage: coverage.rows,
        eligibilityFunnel: coverage.eligibilityFunnel,
        evidenceSummary,
        comparison: coverage.rows.map(function (row) {
          const comparisonAvailable = !comparisonUnavailable;
          const interval = comparisonAvailable
            ? newcombeDifferenceInterval(row.observed, active.total, row.referenceCount, reference.total)
            : null;
          const difference = comparisonAvailable ? row.observedShare - row.referenceShare : null;
          return {
            label: row.label,
            value: comparisonAvailable ? round(difference, 8) : row.observedShare,
            observed: comparisonAvailable ? round(difference, 8) : row.observedShare,
            reference: comparisonAvailable ? 0 : null,
            observedCount: row.observed,
            referenceCount: row.referenceCount,
            observedShare: row.observedShare,
            referenceShare: comparisonAvailable ? row.referenceShare : null,
            difference: comparisonAvailable ? round(difference, 8) : null,
            interval: inferenceDeferred || !interval ? null : {
              lower: round(interval.lower, 8),
              upper: round(interval.upper, 8),
              level: 0.95,
              method: interval.method,
            },
            effectLabel: comparisonAvailable
              ? (difference >= 0 ? "+" : "") + round(difference * 100, 1) + " percentage points"
              : round(row.observedShare * 100, 1) + "% of all matched reports",
            intervalLabel: inferenceDeferred
              ? "Inferential uncertainty deferred until the full evidence computation completes."
              : (interval
                ? "95% interval " + round(interval.lower * 100, 1) + " to " + round(interval.upper * 100, 1) + " percentage points"
                : "No independent reference cohort is used in whole-corpus structure mode."),
            estimatorVersion: "unadjusted_coverage_descriptor_1",
            comparisonState,
            comparisonAvailable,
            estimateAvailable: true,
            tested: false,
            inferenceEligible: false,
            suppressionStatus: "descriptive",
            suppressionReasons: ["coverage_descriptor"],
            supportedActiveN: active.total,
            supportedReferenceN: reference.total,
            commonSupportRate: null,
            adjustedEffect: null,
            pValue: null,
            qValue: null,
            covariates: [],
            datasetHash,
            artifactHashes,
          };
        }),
        active: coverage.active,
        reference: coverage.reference,
      },
      time,
      craft,
      geography,
      sourcesQuality,
      context: inferenceDeferred && !domainRequested(requestedDomains, "context")
        ? { crops: emptyContextDomain(false), animals: emptyContextDomain(false), inferenceDeferred: true, status: "not_requested" }
        : buildContext(options.contextProjections, options.contextLayers, descriptor, options.contextReleaseHashes),
      comparisons: comparisonCatalog,
      patterns,
      patternFamilies,
      patternGroups,
    };
    return result;
  }

  return Object.freeze({
    SCHEMA_VERSION,
    ESTIMATOR_VERSION,
    MINIMUM_COMMON_SUPPORT,
    DEFAULT_BOOTSTRAP_REPLICATES,
    DEFAULT_ASSOCIATION_PERMUTATIONS,
    BASELINE_MODES,
    ANALYSIS_MODES,
    COMPARISON_STATES,
    MONTH_AXIS_ORDER,
    DURATION_BIN_ORDER,
    DURATION_BIN_LABELS,
    FAMILY_ORDER,
    FAMILY_COVARIATES,
    EXPLORATORY_POLICY,
    normalizeBaselineMode,
    semanticAxisMetadata,
    civilFromOrdinal,
    ordinalFromCivil,
    wilsonInterval,
    newcombeDifferenceInterval,
    proportionComparison,
    benjaminiHochberg,
    cochranMantelHaenszel,
    cmhOddsRatio: cochranMantelHaenszel,
    deterministicAggregatedStratumBootstrap,
    bootstrapAdjustedDifference: deterministicAggregatedStratumBootstrap,
    balancedCommonSupportComparison,
    balancedComparison: balancedCommonSupportComparison,
    adjustedStandardizedResiduals,
    qualifySparseHeatmapCells,
    qualifyHeatmapCells: qualifySparseHeatmapCells,
    equalAreaGridCell,
    equalAreaGridCellFromIndexes,
    equalAreaMapCell6x12,
    equalAreaMapCell6x12FromIndexes,
    normalizeContextProjections,
    buildDurationAssessment,
    computeAnalysis,
  });
});

(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.UfoAnalysisSpatial = api;
})(typeof self !== "undefined" ? self : globalThis, function () {
  "use strict";

  const ESTIMATOR_VERSION = "ufo-analysis-spatial-v2.2.0";
  const DEFAULT_WINDOWS = Object.freeze([
    Object.freeze({ id: "near_25km_7d", label: "25 km / +/-7 days", radiusKm: 25, dayWindow: 7, primary: true }),
    Object.freeze({ id: "near_50km_7d", label: "50 km / +/-7 days", radiusKm: 50, dayWindow: 7 }),
    Object.freeze({ id: "near_100km_30d", label: "100 km / +/-30 days", radiusKm: 100, dayWindow: 30 }),
  ]);
  const EXCLUDED_CRAFTS = new Set([
    "", "unknown", "other", "non_ufo", "non-ufo", "conventional", "aircraft", "fireball", "meteor",
  ]);
  const QUALIFIED_CONFIDENCE = new Set(["medium", "high"]);
  const QUALIFIED_SAME_DAY = new Set(["medium", "strong"]);
  const SOURCE_COORDINATE_CLASSES = new Set(["source_coordinates", "source-provided", "source_provided"]);
  const PACKED_EDGE_SCHEMA = Object.freeze([
    "leftEventId", "rightEventId", "distanceDecameters", "dayLag", "crossSource",
  ]);
  const PACKED_FACILITY_SCHEMA = Object.freeze([
    "id", "classCode", "name", "lat", "lon", "coordinatePrecisionCode",
    "coordinateConfidenceCode", "uncertaintyKm", "temporalConfidenceCode",
    "activeIntervals", "statusCode", "countryCode", "provenanceCode",
    "inferentialEligible", "exclusionReasonCodes",
  ]);
  const PACKED_UFO_SPATIAL_POINT_SCHEMA = Object.freeze([
    "eventId", "lat", "lon", "ordinal", "year", "sourceCode", "craftCode",
    "craftConfidenceCode", "sameDayMatchStrengthCode", "coordinateEvidenceCode",
    "coordinatePileGroup", "coordinatePileCount", "fineSpatialStratumCode",
    "coarseSpatialStratumCode", "fiveYearBand", "decade", "duplicateLineageCode",
  ]);
  const PACKED_UFO_CONFIGURATION_POINT_SCHEMA = Object.freeze([
    "eventId", "lat", "lon", "ordinal", "year", "sourceCode", "configurationCode",
    "configurationConfidenceCode", "configurationSourceCode", "sameDayMatchStrengthCode",
    "coordinateEvidenceCode", "coordinatePileGroup", "coordinatePileCount",
    "fineSpatialStratumCode", "coarseSpatialStratumCode", "fiveYearBand", "decade",
    "duplicateLineageCode",
  ]);
  const PACKED_CONTEXT_NEIGHBOR_SCHEMA = Object.freeze([
    "contextDomainCode", "contextLaneCode", "contextId", "contextClusterId",
    "contextOrdinal", "ufoEventId", "distanceDecameters", "dayLag",
    "distanceRingCode", "dayLagBandCode", "uncertaintyClassCode",
    "contextUncertaintyKm", "ufoCraftCode", "ufoSourceCode",
    "ufoFineSpatialStratumCode", "ufoCoarseSpatialStratumCode", "featureGroupCode",
    "originUfoExcluded", "originPublisherExcluded", "independentAssociationEligible",
    "dateRoleCode",
  ]);
  const PACKED_RELATIONSHIP_SCHEMA = Object.freeze([
    "relationshipId", "subjectAnalysisId", "objectDomainCode", "objectAnalysisId",
    "assertionModeCode", "relationshipTypeCode", "reviewStateCode", "currentUfoEventId",
    "reconciliationStatusCode", "associationEligible", "sourceInputCount", "exclusionReasonCodes",
  ]);
  const CONTEXT_DISTANCE_RING_ORDER = Object.freeze(["0_25_km", "25_50_km", "50_100_km", "100_250_km"]);
  const CONTEXT_DAY_LAG_ORDER = Object.freeze(["same_day", "1_3_days", "4_7_days", "8_30_days"]);

  function finite(value, fallback) {
    if (value === null || value === undefined || value === "") return fallback;
    const number = Number(value);
    return Number.isFinite(number) ? number : fallback;
  }

  function text(value, fallback) {
    const cleaned = String(value == null ? "" : value).trim();
    return cleaned || (fallback || "");
  }

  function firstDefined() {
    for (let index = 0; index < arguments.length; index += 1) {
      if (arguments[index] !== undefined && arguments[index] !== null) return arguments[index];
    }
    return undefined;
  }

  function round(value, digits) {
    const multiplier = Math.pow(10, digits == null ? 6 : digits);
    return Math.round(finite(value, 0) * multiplier) / multiplier;
  }

  function hashSeed(value) {
    const input = text(value, "analysis-spatial-v2");
    let hash = 2166136261;
    for (let index = 0; index < input.length; index += 1) {
      hash ^= input.charCodeAt(index);
      hash = Math.imul(hash, 16777619);
    }
    return hash >>> 0 || 0x9e3779b9;
  }

  function seededRandom(seedValue) {
    let state = hashSeed(seedValue);
    return function () {
      state ^= state << 13;
      state ^= state >>> 17;
      state ^= state << 5;
      return (state >>> 0) / 4294967296;
    };
  }

  function quantile(valuesValue, probabilityValue) {
    const values = Array.isArray(valuesValue)
      ? valuesValue.filter(Number.isFinite).slice().sort(function (a, b) { return a - b; })
      : [];
    if (!values.length) return null;
    const probability = Math.max(0, Math.min(1, finite(probabilityValue, 0.5)));
    const position = (values.length - 1) * probability;
    const lower = Math.floor(position);
    const upper = Math.ceil(position);
    if (lower === upper) return values[lower];
    const fraction = position - lower;
    return values[lower] + ((values[upper] - values[lower]) * fraction);
  }

  function benjaminiHochberg(itemsValue, pKey) {
    const items = Array.isArray(itemsValue) ? itemsValue : [];
    const key = pKey || "pValue";
    const eligible = items.map(function (item, index) {
      return { item, index, p: finite(item && item[key], null) };
    }).filter(function (entry) {
      return entry.p != null && entry.p >= 0 && entry.p <= 1;
    }).sort(function (left, right) {
      if (left.p !== right.p) return left.p - right.p;
      return left.index - right.index;
    });
    let running = 1;
    for (let cursor = eligible.length - 1; cursor >= 0; cursor -= 1) {
      const entry = eligible[cursor];
      running = Math.min(running, (entry.p * eligible.length) / (cursor + 1));
      entry.item.qValue = round(Math.max(0, Math.min(1, running)), 8);
    }
    return items;
  }

  function greatCircleDistanceMeters(latitudeA, longitudeA, latitudeB, longitudeB) {
    const latA = finite(latitudeA, null);
    const lonA = finite(longitudeA, null);
    const latB = finite(latitudeB, null);
    const lonB = finite(longitudeB, null);
    if ([latA, lonA, latB, lonB].some(function (value) { return value == null; })) return null;
    const radians = Math.PI / 180;
    const deltaLatitude = (latB - latA) * radians;
    let deltaLongitudeDegrees = lonB - lonA;
    while (deltaLongitudeDegrees > 180) deltaLongitudeDegrees -= 360;
    while (deltaLongitudeDegrees < -180) deltaLongitudeDegrees += 360;
    const deltaLongitude = deltaLongitudeDegrees * radians;
    const firstLatitude = latA * radians;
    const secondLatitude = latB * radians;
    const haversine = Math.sin(deltaLatitude / 2) ** 2 +
      Math.cos(firstLatitude) * Math.cos(secondLatitude) * Math.sin(deltaLongitude / 2) ** 2;
    return 6371008.8 * 2 * Math.atan2(Math.sqrt(Math.max(0, haversine)), Math.sqrt(Math.max(0, 1 - haversine)));
  }

  function classifyUncertainDistance(distanceMetersValue, leftUncertaintyValue, rightUncertaintyValue, radiusMetersValue) {
    const distanceMeters = Math.max(0, finite(distanceMetersValue, Infinity));
    const uncertainty = Math.max(0, finite(leftUncertaintyValue, 0)) + Math.max(0, finite(rightUncertaintyValue, 0));
    const radiusMeters = Math.max(0, finite(radiusMetersValue, 0));
    const minimumDistance = Math.max(0, distanceMeters - uncertainty);
    const maximumDistance = distanceMeters + uncertainty;
    return {
      status: maximumDistance <= radiusMeters ? "near" : (minimumDistance > radiusMeters ? "far" : "ambiguous"),
      distanceMeters: round(distanceMeters, 3),
      uncertaintyMeters: round(uncertainty, 3),
      minimumDistanceMeters: round(minimumDistance, 3),
      maximumDistanceMeters: round(maximumDistance, 3),
      radiusMeters: round(radiusMeters, 3),
    };
  }

  function coordinateClass(row) {
    return text(row && (row.analysisCoordinateClass || row.coordinateEvidenceClass || row.coordinateClass), "unmapped").toLowerCase();
  }

  function recognizedCraft(row) {
    const craft = text(row && (row.craftType || row.craft || row.craft_type), "unknown").toLowerCase();
    return EXCLUDED_CRAFTS.has(craft) ? "" : craft;
  }

  function spatialEligibilityReason(rowValue) {
    const row = rowValue || {};
    if (!row.mapped || !Number.isFinite(Number(row.lat)) || !Number.isFinite(Number(row.lon))) return "unmapped";
    if (!SOURCE_COORDINATE_CLASSES.has(coordinateClass(row))) return "generalized_coordinates";
    if (text(row.datePrecision || row.date_precision, "unknown").toLowerCase() !== "exact_day") return "non_exact_date";
    if (!recognizedCraft(row)) return "unqualified_craft";
    if (!QUALIFIED_CONFIDENCE.has(text(row.craftConfidence || row.craft_confidence, "none").toLowerCase())) return "low_craft_confidence";
    if (!QUALIFIED_SAME_DAY.has(text(row.sameDayMatchStrength || row.same_day_match_strength, "none").toLowerCase())) return "weak_same_day_evidence";
    if (text(row.duplicateLineage || row.duplicate_lineage, "")) return "duplicate_lineage";
    if (Math.max(0, finite(firstDefined(row.analysisCoordinatePileCount, row.coordinatePileCount), 0)) >= 10) return "coordinate_pile";
    return "eligible";
  }

  function buildEligibilityFunnel(rowsValue) {
    const rows = Array.isArray(rowsValue) ? rowsValue : [];
    const funnel = {
      activeReports: rows.length,
      mappedReports: 0,
      sourceCoordinateReports: 0,
      exactDayReports: 0,
      qualifiedCraftReports: 0,
      inferentiallyEligibleReports: 0,
      exclusions: {},
      eligibleSources: {},
      eligibleRegions: {},
    };
    rows.forEach(function (row) {
      const mapped = Boolean(row && row.mapped && Number.isFinite(Number(row.lat)) && Number.isFinite(Number(row.lon)));
      if (mapped) funnel.mappedReports += 1;
      if (mapped && SOURCE_COORDINATE_CLASSES.has(coordinateClass(row))) funnel.sourceCoordinateReports += 1;
      if (text(row && (row.datePrecision || row.date_precision)).toLowerCase() === "exact_day") funnel.exactDayReports += 1;
      if (recognizedCraft(row) && QUALIFIED_CONFIDENCE.has(text(row && (row.craftConfidence || row.craft_confidence)).toLowerCase())) {
        funnel.qualifiedCraftReports += 1;
      }
      const reason = spatialEligibilityReason(row);
      if (reason !== "eligible") {
        funnel.exclusions[reason] = (funnel.exclusions[reason] || 0) + 1;
        return;
      }
      funnel.inferentiallyEligibleReports += 1;
      const source = text(row.source, "unknown");
      const region = text(row.analysisCoarseSpatialStratum, "unmapped");
      funnel.eligibleSources[source] = (funnel.eligibleSources[source] || 0) + 1;
      funnel.eligibleRegions[region] = (funnel.eligibleRegions[region] || 0) + 1;
    });
    funnel.eligibilityRate = rows.length ? funnel.inferentiallyEligibleReports / rows.length : 0;
    return funnel;
  }

  function normalizeEdge(edgeValue) {
    if (Array.isArray(edgeValue)) {
      const packedDistance = finite(edgeValue[2], Infinity);
      const packedDayLag = Math.abs(finite(edgeValue[3], Infinity));
      const validEventId = function (value) {
        return typeof value === "number"
          ? Number.isSafeInteger(value) && value >= 0
          : /^[0-9]+$/.test(text(value));
      };
      return {
        eventIdA: text(edgeValue[0]),
        eventIdB: text(edgeValue[1]),
        // ufo_point_neighbors_v1 stores distance in decameters so the complete
        // deterministic graph stays compact. Convert at this single boundary.
        distanceMeters: packedDistance * 10,
        distanceDecameters: packedDistance,
        dayGap: packedDayLag,
        crossSource: Boolean(edgeValue[4]),
        duplicateCandidate: false,
        packed: true,
        contractValid: validEventId(edgeValue[0]) && validEventId(edgeValue[1]) &&
          Number.isInteger(packedDistance) && packedDistance >= 0 && packedDistance <= 10000 &&
          Number.isInteger(packedDayLag) && packedDayLag >= 0 && packedDayLag <= 30 &&
          typeof edgeValue[4] === "boolean",
      };
    }
    const edge = edgeValue || {};
    const distanceDecameters = edge.distanceDecameters == null
      ? (edge.distance_decameters == null ? null : finite(edge.distance_decameters, null))
      : finite(edge.distanceDecameters, null);
    const distanceMeters = finite(
      edge.distanceMeters == null
        ? (edge.distance_meters == null
          ? (distanceDecameters == null ? Infinity : distanceDecameters * 10)
          : edge.distance_meters)
        : edge.distanceMeters,
      Infinity
    );
    const dayGap = Math.abs(finite(firstDefined(edge.dayGap, edge.day_gap, edge.dayLag, edge.day_lag), Infinity));
    return {
      eventIdA: text(edge.eventIdA || edge.event_id_a || edge.a || edge.catalogRowA),
      eventIdB: text(edge.eventIdB || edge.event_id_b || edge.b || edge.catalogRowB),
      distanceMeters,
      distanceDecameters,
      dayGap,
      crossSource: edge.crossSource == null ? edge.cross_source == null ? null : Boolean(edge.cross_source) : Boolean(edge.crossSource),
      duplicateCandidate: Boolean(edge.duplicateCandidate || edge.duplicate_candidate),
      packed: false,
      contractValid: Number.isFinite(distanceMeters) && distanceMeters >= 0 && Number.isFinite(dayGap) && dayGap >= 0,
    };
  }

  function spatialRow(rowValue) {
    const row = rowValue || {};
    return {
      eventId: text(row.eventId || row.event_id),
      source: text(row.source, "unknown").toLowerCase(),
      craft: recognizedCraft(row),
      year: finite(firstDefined(row.analysisYear, row.year), null),
      ordinal: finite(firstDefined(row.sortOrdinal, row.ordinal), null),
      lat: finite(row.lat, null),
      lon: finite(row.lon, null),
      fine: text(row.analysisFineSpatialStratum, "unmapped"),
      coarse: text(row.analysisCoarseSpatialStratum, "unmapped"),
      fiveYearBand: finite(row.analysisFiveYearBand, null),
      decade: finite(row.analysisDecade, null),
      pileCount: Math.max(0, finite(row.analysisCoordinatePileCount, 0)),
      region: text(firstDefined(row.adminRegion, row.region, row.analysisCoarseSpatialStratum), "unmapped"),
      raw: row,
    };
  }

  function supportedSpatialRows(rowsValue, minimumStratumSize) {
    const rows = rowsValue.map(spatialRow);
    const fineCounts = new Map();
    const coarseCounts = new Map();
    rows.forEach(function (row) {
      const five = row.fiveYearBand == null && row.year != null ? Math.floor(row.year / 5) * 5 : row.fiveYearBand;
      const decade = row.decade == null && row.year != null ? Math.floor(row.year / 10) * 10 : row.decade;
      row.fineKey = row.source + "|" + five + "|" + row.fine;
      row.coarseKey = row.source + "|" + decade + "|" + row.coarse;
      fineCounts.set(row.fineKey, (fineCounts.get(row.fineKey) || 0) + 1);
      coarseCounts.set(row.coarseKey, (coarseCounts.get(row.coarseKey) || 0) + 1);
    });
    const minimum = Math.max(2, finite(minimumStratumSize, 20));
    const supported = [];
    const excluded = [];
    rows.forEach(function (row) {
      if ((fineCounts.get(row.fineKey) || 0) >= minimum) {
        row.stratum = "fine|" + row.fineKey;
        supported.push(row);
      } else if ((coarseCounts.get(row.coarseKey) || 0) >= minimum) {
        row.stratum = "coarse|" + row.coarseKey;
        supported.push(row);
      } else {
        excluded.push(row);
      }
    });
    return { supported, excluded };
  }

  function buildAdjacency(rows, edgesValue, config) {
    const indexById = new Map();
    rows.forEach(function (row, index) { indexById.set(row.eventId, index); });
    const adjacency = Array.from({ length: rows.length }, function () { return []; });
    let qualifyingPairs = 0;
    let invalidEdgeCount = 0;
    let duplicateEdgeCount = 0;
    let crossSourceFlagMismatchCount = 0;
    let absentEndpointCount = 0;
    const seenPairs = new Set();
    const radiusMeters = Math.max(0, finite(config.radiusKm, 25) * 1000);
    const dayWindow = Math.max(0, finite(config.dayWindow, 7));
    (Array.isArray(edgesValue) ? edgesValue : []).forEach(function (edgeValue) {
      const edge = normalizeEdge(edgeValue);
      if (!edge.contractValid || !edge.eventIdA || !edge.eventIdB || edge.eventIdA === edge.eventIdB || edge.duplicateCandidate) {
        invalidEdgeCount += 1;
        return;
      }
      if (edge.distanceMeters > radiusMeters || edge.dayGap > dayWindow) return;
      const left = indexById.get(edge.eventIdA);
      const right = indexById.get(edge.eventIdB);
      if (left == null || right == null || left === right) {
        absentEndpointCount += 1;
        return;
      }
      const pairKey = left < right ? left + "|" + right : right + "|" + left;
      if (seenPairs.has(pairKey)) {
        duplicateEdgeCount += 1;
        return;
      }
      seenPairs.add(pairKey);
      const isCrossSource = rows[left].source !== rows[right].source;
      if (edge.crossSource != null && edge.crossSource !== isCrossSource) crossSourceFlagMismatchCount += 1;
      if (config.sourceLane === "cross" && !isCrossSource) return;
      if (config.sourceLane === "same" && isCrossSource) return;
      adjacency[left].push(right);
      adjacency[right].push(left);
      qualifyingPairs += 1;
    });
    return {
      adjacency,
      qualifyingPairs,
      invalidEdgeCount,
      duplicateEdgeCount,
      absentEndpointCount,
      crossSourceFlagMismatchCount,
    };
  }

  function matrixCounts(labels, adjacency, categoryCount, focalMask, neighborMask, focalWeights) {
    if (arguments.length < 5) neighborMask = focalMask;
    const counts = focalWeights
      ? new Float64Array(categoryCount * categoryCount)
      : new Int32Array(categoryCount * categoryCount);
    const seen = new Uint32Array(categoryCount);
    let stamp = 0;
    for (let focal = 0; focal < adjacency.length; focal += 1) {
      if (focalMask && !focalMask[focal]) continue;
      const weight = focalWeights ? finite(focalWeights[focal], 0) : 1;
      if (weight <= 0) continue;
      stamp += 1;
      if (stamp === 0xffffffff) {
        seen.fill(0);
        stamp = 1;
      }
      const focalLabel = labels[focal];
      const neighbors = adjacency[focal];
      for (let cursor = 0; cursor < neighbors.length; cursor += 1) {
        const neighborIndex = neighbors[cursor];
        if (neighborMask && !neighborMask[neighborIndex]) continue;
        const neighborLabel = labels[neighborIndex];
        if (seen[neighborLabel] === stamp) continue;
        seen[neighborLabel] = stamp;
        counts[(focalLabel * categoryCount) + neighborLabel] += weight;
      }
    }
    return counts;
  }

  function shuffledLabels(baseLabels, strata, random) {
    const labels = Int16Array.from(baseLabels);
    strata.forEach(function (indexes) {
      for (let cursor = indexes.length - 1; cursor > 0; cursor -= 1) {
        const swap = Math.floor(random() * (cursor + 1));
        const left = indexes[cursor];
        const right = indexes[swap];
        const value = labels[left];
        labels[left] = labels[right];
        labels[right] = value;
      }
    });
    return labels;
  }

  function effectValue(observed, expected) {
    return Math.log2((observed + 0.5) / (expected + 0.5));
  }

  function bootstrapEffectIntervals(rows, labels, adjacency, categoryCount, expected, replicateCount, random) {
    const blockByKey = new Map();
    rows.forEach(function (row, index) {
      // Resampling geography-by-time blocks keeps locally correlated reports
      // together. Source is deliberately not a block component; source
      // robustness is evaluated separately with leave-one-source-out checks.
      const key = (row.fiveYearBand == null ? row.decade : row.fiveYearBand) + "|" + row.coarse;
      if (!blockByKey.has(key)) blockByKey.set(key, []);
      blockByKey.get(key).push(index);
    });
    const blocks = Array.from(blockByKey.values());
    const distributions = Array.from({ length: categoryCount * categoryCount }, function () { return []; });
    if (!blocks.length) return distributions.map(function () { return [null, null]; });
    const baseFocalCounts = new Int32Array(categoryCount);
    labels.forEach(function (label) { baseFocalCounts[label] += 1; });
    const preparedBlocks = blocks.map(function (indexes) {
      const mask = new Uint8Array(rows.length);
      const focalCounts = new Int32Array(categoryCount);
      indexes.forEach(function (index) {
        mask[index] = 1;
        focalCounts[labels[index]] += 1;
      });
      return {
        counts: matrixCounts(labels, adjacency, categoryCount, mask, null),
        focalCounts,
      };
    });
    for (let replicate = 0; replicate < replicateCount; replicate += 1) {
      const counts = new Float64Array(categoryCount * categoryCount);
      const focalCounts = new Int32Array(categoryCount);
      for (let draw = 0; draw < preparedBlocks.length; draw += 1) {
        const block = preparedBlocks[Math.floor(random() * preparedBlocks.length)];
        for (let cell = 0; cell < counts.length; cell += 1) counts[cell] += block.counts[cell];
        for (let category = 0; category < categoryCount; category += 1) {
          focalCounts[category] += block.focalCounts[category];
        }
      }
      for (let cell = 0; cell < counts.length; cell += 1) {
        const rowCategory = Math.floor(cell / categoryCount);
        const scale = baseFocalCounts[rowCategory]
          ? focalCounts[rowCategory] / baseFocalCounts[rowCategory]
          : 0;
        distributions[cell].push(effectValue(counts[cell], expected[cell] * scale));
      }
    }
    return distributions.map(function (values) {
      return [quantile(values, 0.025), quantile(values, 0.975)];
    });
  }

  function leaveOneGroupOutSensitivity(rows, labels, adjacency, categoryCount, expected, groupSelector, minimumGroupN) {
    const groups = new Map();
    rows.forEach(function (row, index) {
      const key = text(groupSelector(row), "unknown");
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(index);
    });
    const minimum = Math.max(1, Math.trunc(finite(minimumGroupN, 25)));
    const eligibleGroups = Array.from(groups.entries()).filter(function (entry) {
      return entry[1].length >= minimum && rows.length - entry[1].length >= minimum;
    }).sort(function (left, right) { return left[0].localeCompare(right[0]); });
    const baseCategoryCounts = new Int32Array(categoryCount);
    labels.forEach(function (label) { baseCategoryCounts[label] += 1; });
    const effects = Array.from({ length: categoryCount * categoryCount }, function () { return []; });
    eligibleGroups.forEach(function (entry) {
      const mask = new Uint8Array(rows.length);
      mask.fill(1);
      entry[1].forEach(function (index) { mask[index] = 0; });
      const counts = matrixCounts(labels, adjacency, categoryCount, mask, mask);
      const remainingCategoryCounts = new Int32Array(categoryCount);
      rows.forEach(function (_row, index) {
        if (mask[index]) remainingCategoryCounts[labels[index]] += 1;
      });
      for (let cell = 0; cell < counts.length; cell += 1) {
        const rowCategory = Math.floor(cell / categoryCount);
        const columnCategory = cell % categoryCount;
        const focalScale = baseCategoryCounts[rowCategory]
          ? remainingCategoryCounts[rowCategory] / baseCategoryCounts[rowCategory]
          : 0;
        const neighborScale = baseCategoryCounts[columnCategory]
          ? remainingCategoryCounts[columnCategory] / baseCategoryCounts[columnCategory]
          : 0;
        effects[cell].push({
          omitted: entry[0],
          omittedN: entry[1].length,
          log2Enrichment: effectValue(counts[cell], expected[cell] * focalScale * neighborScale),
        });
      }
    });
    return {
      evaluatedGroups: eligibleGroups.map(function (entry) { return { key: entry[0], n: entry[1].length }; }),
      effects,
      method: "leave-one-group-out fixed-null opportunity scaling",
    };
  }

  function summarizeHoldoutEffects(baseEffect, effectsValue) {
    const effects = Array.isArray(effectsValue) ? effectsValue : [];
    if (!effects.length) {
      return {
        evaluatedHoldoutN: 0,
        signStable: null,
        thresholdStable: null,
        minimumLog2Enrichment: null,
        maximumLog2Enrichment: null,
        sensitiveGroups: [],
      };
    }
    const sign = Math.sign(baseEffect);
    const threshold = Math.log2(1.25);
    const values = effects.map(function (entry) { return entry.log2Enrichment; });
    return {
      evaluatedHoldoutN: effects.length,
      signStable: sign !== 0 && effects.every(function (entry) { return Math.sign(entry.log2Enrichment) === sign; }),
      thresholdStable: effects.every(function (entry) {
        return Math.sign(entry.log2Enrichment) === sign && Math.abs(entry.log2Enrichment) >= threshold;
      }),
      minimumLog2Enrichment: round(Math.min.apply(null, values), 6),
      maximumLog2Enrichment: round(Math.max.apply(null, values), 6),
      sensitiveGroups: effects.filter(function (entry) {
        return Math.sign(entry.log2Enrichment) !== sign || Math.abs(entry.log2Enrichment) < threshold;
      }).map(function (entry) { return entry.omitted; }),
    };
  }

  function computeCraftCooccurrence(optionsValue) {
    const options = optionsValue || {};
    const allRows = Array.isArray(options.rows) ? options.rows : [];
    const eligibleRaw = allRows.filter(function (row) { return spatialEligibilityReason(row) === "eligible"; });
    const supportedResult = supportedSpatialRows(eligibleRaw, options.minimumStratumSize || 20);
    const rows = supportedResult.supported;
    const commonSupportRate = eligibleRaw.length ? rows.length / eligibleRaw.length : 0;
    const categories = Array.from(new Set(rows.map(function (row) { return row.craft; }))).sort();
    const categoryIndex = new Map(categories.map(function (value, index) { return [value, index]; }));
    const labels = Int16Array.from(rows.map(function (row) { return categoryIndex.get(row.craft); }));
    const windowConfig = Object.assign({}, DEFAULT_WINDOWS[0], options.window || {});
    const adjacencyResult = buildAdjacency(rows, options.edges, {
      radiusKm: windowConfig.radiusKm,
      dayWindow: windowConfig.dayWindow,
      sourceLane: text(options.sourceLane, options.crossSourceOnly === false ? "all" : "cross"),
    });
    const observed = matrixCounts(labels, adjacencyResult.adjacency, categories.length);
    const strata = new Map();
    rows.forEach(function (row, index) {
      if (!strata.has(row.stratum)) strata.set(row.stratum, []);
      strata.get(row.stratum).push(index);
    });
    const permutationCount = Math.max(0, Math.trunc(finite(options.permutationCount, 499)));
    const random = seededRandom(text(options.seed, ESTIMATOR_VERSION + "|" + windowConfig.id));
    const distributions = Array.from({ length: observed.length }, function () { return []; });
    const stratumIndexes = Array.from(strata.values());
    for (let replicate = 0; replicate < permutationCount; replicate += 1) {
      const permuted = shuffledLabels(labels, stratumIndexes, random);
      const counts = matrixCounts(permuted, adjacencyResult.adjacency, categories.length);
      for (let cell = 0; cell < counts.length; cell += 1) distributions[cell].push(counts[cell]);
    }
    const expected = new Float64Array(observed.length);
    distributions.forEach(function (values, cell) {
      expected[cell] = values.length ? values.reduce(function (sum, value) { return sum + value; }, 0) / values.length : 0;
    });
    const bootstrapCount = Math.max(0, Math.trunc(finite(options.bootstrapCount, 199)));
    const effectIntervals = bootstrapEffectIntervals(
      rows,
      labels,
      adjacencyResult.adjacency,
      categories.length,
      expected,
      bootstrapCount,
      random
    );
    const noPileMask = Uint8Array.from(rows.map(function (row) { return row.pileCount < 10 ? 1 : 0; }));
    const noPileObserved = matrixCounts(labels, adjacencyResult.adjacency, categories.length, noPileMask);
    const baseCategoryCounts = new Int32Array(categories.length);
    const noPileCategoryCounts = new Int32Array(categories.length);
    labels.forEach(function (label, index) {
      baseCategoryCounts[label] += 1;
      if (noPileMask[index]) noPileCategoryCounts[label] += 1;
    });
    const sourceHoldouts = leaveOneGroupOutSensitivity(
      rows,
      labels,
      adjacencyResult.adjacency,
      categories.length,
      expected,
      function (row) { return row.source; },
      options.minimumHoldoutN || 25
    );
    const regionHoldouts = leaveOneGroupOutSensitivity(
      rows,
      labels,
      adjacencyResult.adjacency,
      categories.length,
      expected,
      function (row) { return row.coarse; },
      options.minimumHoldoutN || 25
    );
    const cells = [];
    for (let rowIndex = 0; rowIndex < categories.length; rowIndex += 1) {
      for (let columnIndex = 0; columnIndex < categories.length; columnIndex += 1) {
        const cell = (rowIndex * categories.length) + columnIndex;
        const observedCount = observed[cell];
        const expectedCount = expected[cell];
        const difference = observedCount - expectedCount;
        const values = distributions[cell];
        const extreme = values.filter(function (value) {
          return Math.abs(value - expectedCount) >= Math.abs(difference) - 1e-12;
        }).length;
        const pValue = values.length ? (extreme + 1) / (values.length + 1) : null;
        const enrichment = expectedCount > 0 ? observedCount / expectedCount : (observedCount > 0 ? Infinity : null);
        const log2Enrichment = effectValue(observedCount, expectedCount);
        const focalScale = baseCategoryCounts[rowIndex] ? noPileCategoryCounts[rowIndex] / baseCategoryCounts[rowIndex] : 0;
        const neighborScale = baseCategoryCounts[columnIndex] ? noPileCategoryCounts[columnIndex] / baseCategoryCounts[columnIndex] : 0;
        const pileEffect = effectValue(noPileObserved[cell], expectedCount * focalScale * neighborScale);
        const sourceSensitivity = summarizeHoldoutEffects(log2Enrichment, sourceHoldouts.effects[cell]);
        const regionSensitivity = summarizeHoldoutEffects(log2Enrichment, regionHoldouts.effects[cell]);
        const suppressionReasons = [];
        if (allRows.length < 200) suppressionReasons.push("active_cohort_below_200");
        if (observedCount < 25) suppressionReasons.push("observed_below_25");
        if (expectedCount < 10) suppressionReasons.push("expected_below_10");
        if (commonSupportRate < 0.8) suppressionReasons.push("common_support_below_80_percent");
        if (Math.abs(log2Enrichment) < Math.log2(1.25)) suppressionReasons.push("effect_below_1_25x");
        cells.push({
          estimatorVersion: ESTIMATOR_VERSION,
          artifactHashes: Object.assign({}, options.artifactHashes || {}),
          row: categories[rowIndex],
          column: categories[columnIndex],
          observedCount,
          expectedCount: round(expectedCount, 4),
          qualifyingReports: observedCount,
          log2Enrichment: round(log2Enrichment, 6),
          enrichmentRatio: enrichment == null || !Number.isFinite(enrichment) ? enrichment : round(enrichment, 6),
          effectInterval: effectIntervals[cell].map(function (value) { return value == null ? null : round(value, 6); }),
          nullInterval: [quantile(values, 0.025), quantile(values, 0.975)].map(function (value) { return value == null ? null : round(value, 4); }),
          pValue: pValue == null ? null : round(pValue, 8),
          qValue: null,
          pileSensitivity: {
            excludedReports: rows.length - noPileMask.reduce(function (sum, value) { return sum + value; }, 0),
            log2Enrichment: round(pileEffect, 6),
            signStable: Math.sign(pileEffect) === Math.sign(log2Enrichment),
          },
          sourceSensitivity,
          regionSensitivity,
          stabilityClass: sourceSensitivity.signStable === true && regionSensitivity.signStable === true
            ? "source_and_region_stable"
            : "source_or_region_sensitive",
          status: suppressionReasons.length ? "suppressed" : "eligible",
          suppressionReasons,
        });
      }
    }
    benjaminiHochberg(cells);
    cells.forEach(function (cell) {
      if (cell.status === "eligible" && finite(cell.qValue, 1) > 0.05) {
        cell.status = "suppressed";
        cell.suppressionReasons.push("q_above_0_05");
      }
    });
    const sourceCounts = {};
    rows.forEach(function (row) { sourceCounts[row.source] = (sourceCounts[row.source] || 0) + 1; });
    const substantiveSources = Object.keys(sourceCounts).filter(function (source) { return sourceCounts[source] >= 25; });
    cells.forEach(function (cell) {
      cell.patternFinderEligible = cell.status === "eligible" && substantiveSources.length >= 2 &&
        cell.sourceSensitivity.signStable === true &&
        cell.regionSensitivity.signStable === true;
    });
    return {
      estimatorVersion: ESTIMATOR_VERSION,
      unitOfAnalysis: "eligible UFO report exposed to at least one neighboring craft category",
      status: allRows.length < 200 || rows.length < 25 || commonSupportRate < 0.8 ? "suppressed" : "exploratory",
      window: windowConfig,
      sourceLane: text(options.sourceLane, options.crossSourceOnly === false ? "all" : "cross"),
      crossSourcePrimary: text(options.sourceLane, options.crossSourceOnly === false ? "all" : "cross") === "cross",
      activeN: allRows.length,
      eligibleN: eligibleRaw.length,
      supportedActiveN: rows.length,
      excludedSparseStratumN: supportedResult.excluded.length,
      commonSupportRate: round(commonSupportRate, 6),
      qualifyingPairCount: adjacencyResult.qualifyingPairs,
      edgeAudit: {
        schema: PACKED_EDGE_SCHEMA.slice(),
        packedDistanceUnit: "decameters",
        packedMaximumDistanceDecameters: 10000,
        packedMaximumDayLag: 30,
        invalidEdgeCount: adjacencyResult.invalidEdgeCount,
        duplicateEdgeCount: adjacencyResult.duplicateEdgeCount,
        absentEndpointCount: adjacencyResult.absentEndpointCount,
        crossSourceFlagMismatchCount: adjacencyResult.crossSourceFlagMismatchCount,
      },
      permutationCount,
      bootstrapCount,
      sourceCounts,
      sourceStability: {
        substantiveSources,
        multiSourceEligible: substantiveSources.length >= 2,
        evaluatedHoldouts: sourceHoldouts.evaluatedGroups,
        label: substantiveSources.length >= 2 ? "leave-one-source-out evaluated" : "source-specific only",
      },
      regionStability: {
        evaluatedHoldouts: regionHoldouts.evaluatedGroups,
        label: regionHoldouts.evaluatedGroups.length ? "leave-one-region-out evaluated" : "region holdout not estimable",
      },
      categories,
      cells,
      policyWarnings: [
        "Exploratory report-point co-occurrence; not an observed route, craft identity, or causal relationship.",
        "Source-provided report markers are not verified physical sites.",
        "Chronology connectors are not read by this estimator.",
      ],
      artifactHashes: Object.assign({}, options.artifactHashes || {}),
    };
  }

  function codeLabel(codebookValue, key, value, fallback) {
    const codebook = codebookValue || {};
    const labels = Array.isArray(codebook[key]) ? codebook[key] : [];
    const index = Number(value);
    return Number.isInteger(index) && index >= 0 && index < labels.length
      ? text(labels[index], fallback)
      : text(value, fallback);
  }

  function normalizeSpatialPoint(value, codebookValue) {
    if (Array.isArray(value)) {
      return {
        eventId: text(value[0]),
        lat: finite(value[1], null),
        lon: finite(value[2], null),
        ordinal: finite(value[3], null),
        year: finite(value[4], null),
        source: codeLabel(codebookValue, "source", value[5], "unknown").toLowerCase(),
        craft: codeLabel(codebookValue, "craft", value[6], "unknown").toLowerCase(),
        craftConfidence: codeLabel(codebookValue, "craftConfidence", value[7], "unknown").toLowerCase(),
        sameDayMatchStrength: codeLabel(codebookValue, "sameDayMatchStrength", value[8], "unknown").toLowerCase(),
        coordinateEvidence: codeLabel(codebookValue, "coordinateEvidence", value[9], "unknown").toLowerCase(),
        pileGroup: text(value[10]),
        pileCount: Math.max(0, finite(value[11], 0)),
        fine: codeLabel(codebookValue, "fineSpatialStratum", value[12], "unmapped"),
        coarse: codeLabel(codebookValue, "coarseSpatialStratum", value[13], "unmapped"),
        fiveYearBand: finite(value[14], null),
        decade: finite(value[15], null),
        duplicateLineage: codeLabel(codebookValue, "duplicateLineage", value[16], "canonical_deduped_event"),
        packed: true,
      };
    }
    const row = value || {};
    return {
      eventId: text(firstDefined(row.eventId, row.event_id)),
      lat: finite(row.lat, null),
      lon: finite(row.lon, null),
      ordinal: finite(firstDefined(row.ordinal, row.sortOrdinal), null),
      year: finite(firstDefined(row.year, row.analysisYear), null),
      source: text(firstDefined(row.source, row.sourceCode), "unknown").toLowerCase(),
      craft: text(firstDefined(row.craft, row.craftCode, row.craftType), "unknown").toLowerCase(),
      craftConfidence: text(firstDefined(row.craftConfidence, row.craftConfidenceCode), "unknown").toLowerCase(),
      sameDayMatchStrength: text(firstDefined(row.sameDayMatchStrength, row.sameDayMatchStrengthCode), "unknown").toLowerCase(),
      coordinateEvidence: text(firstDefined(row.coordinateEvidence, row.coordinateEvidenceCode), "unknown").toLowerCase(),
      pileGroup: text(firstDefined(row.coordinatePileGroup, row.pileGroup)),
      pileCount: Math.max(0, finite(firstDefined(row.coordinatePileCount, row.pileCount), 0)),
      fine: text(firstDefined(row.fineSpatialStratum, row.fineSpatialStratumCode), "unmapped"),
      coarse: text(firstDefined(row.coarseSpatialStratum, row.coarseSpatialStratumCode), "unmapped"),
      fiveYearBand: finite(row.fiveYearBand, null),
      decade: finite(row.decade, null),
      duplicateLineage: text(firstDefined(row.duplicateLineage, row.duplicateLineageCode), "canonical_deduped_event"),
      packed: false,
    };
  }

  function normalizeConfigurationPoint(value, codebookValue) {
    if (Array.isArray(value)) {
      return {
        eventId: text(value[0]),
        lat: finite(value[1], null),
        lon: finite(value[2], null),
        ordinal: finite(value[3], null),
        year: finite(value[4], null),
        source: codeLabel(codebookValue, "source", value[5], "unknown").toLowerCase(),
        craft: codeLabel(codebookValue, "configuration", value[6], "formation").toLowerCase(),
        configuration: codeLabel(codebookValue, "configuration", value[6], "formation").toLowerCase(),
        craftConfidence: codeLabel(codebookValue, "configurationConfidence", value[7], "unknown").toLowerCase(),
        configurationSource: codeLabel(codebookValue, "configurationSource", value[8], "unknown").toLowerCase(),
        sameDayMatchStrength: codeLabel(codebookValue, "sameDayMatchStrength", value[9], "unknown").toLowerCase(),
        coordinateEvidence: codeLabel(codebookValue, "coordinateEvidence", value[10], "unknown").toLowerCase(),
        pileGroup: text(value[11]),
        pileCount: Math.max(0, finite(value[12], 0)),
        fine: codeLabel(codebookValue, "fineSpatialStratum", value[13], "unmapped"),
        coarse: codeLabel(codebookValue, "coarseSpatialStratum", value[14], "unmapped"),
        fiveYearBand: finite(value[15], null),
        decade: finite(value[16], null),
        duplicateLineage: codeLabel(codebookValue, "duplicateLineage", value[17], "canonical_deduped_event"),
        packed: true,
        configurationPoint: true,
      };
    }
    const row = value || {};
    return {
      eventId: text(firstDefined(row.eventId, row.event_id)),
      lat: finite(row.lat, null),
      lon: finite(row.lon, null),
      ordinal: finite(firstDefined(row.ordinal, row.sortOrdinal), null),
      year: finite(firstDefined(row.year, row.analysisYear), null),
      source: text(firstDefined(row.source, row.sourceCode), "unknown").toLowerCase(),
      craft: text(firstDefined(row.configuration, row.configurationCode), "formation").toLowerCase(),
      configuration: text(firstDefined(row.configuration, row.configurationCode), "formation").toLowerCase(),
      craftConfidence: text(firstDefined(row.configurationConfidence, row.configurationConfidenceCode), "unknown").toLowerCase(),
      configurationSource: text(firstDefined(row.configurationSource, row.configurationSourceCode), "unknown").toLowerCase(),
      sameDayMatchStrength: text(firstDefined(row.sameDayMatchStrength, row.sameDayMatchStrengthCode), "unknown").toLowerCase(),
      coordinateEvidence: text(firstDefined(row.coordinateEvidence, row.coordinateEvidenceCode), "unknown").toLowerCase(),
      pileGroup: text(firstDefined(row.coordinatePileGroup, row.pileGroup)),
      pileCount: Math.max(0, finite(firstDefined(row.coordinatePileCount, row.pileCount), 0)),
      fine: text(firstDefined(row.fineSpatialStratum, row.fineSpatialStratumCode), "unmapped"),
      coarse: text(firstDefined(row.coarseSpatialStratum, row.coarseSpatialStratumCode), "unmapped"),
      fiveYearBand: finite(row.fiveYearBand, null),
      decade: finite(row.decade, null),
      duplicateLineage: text(firstDefined(row.duplicateLineage, row.duplicateLineageCode), "canonical_deduped_event"),
      packed: false,
      configurationPoint: true,
    };
  }

  function pinnedConfigurationRowsForActiveCohort(activeRowsValue, spatialPointsValue, configurationPointsValue, codebooksValue) {
    const activeRows = Array.isArray(activeRowsValue) ? activeRowsValue : [];
    const activeIds = new Set(activeRows.map(function (row) {
      return text(firstDefined(row && row.eventId, row && row.event_id));
    }));
    const codebooks = codebooksValue || {};
    const byEventId = new Map();
    (Array.isArray(spatialPointsValue) ? spatialPointsValue : []).forEach(function (value) {
      const point = normalizeSpatialPoint(value, codebooks.ufoSpatialPoints);
      if (activeIds.has(point.eventId)) byEventId.set(point.eventId, point);
    });
    (Array.isArray(configurationPointsValue) ? configurationPointsValue : []).forEach(function (value) {
      const point = normalizeConfigurationPoint(value, codebooks.ufoConfigurationPoints);
      if (activeIds.has(point.eventId)) byEventId.set(point.eventId, point);
    });
    return Array.from(byEventId.values()).map(function (point) {
      return {
        eventId: point.eventId,
        mapped: true,
        lat: point.lat,
        lon: point.lon,
        analysisCoordinateClass: point.coordinateEvidence,
        coordinateSource: "raw_latlong",
        datePrecision: "exact_day",
        craftType: point.craft,
        craftConfidence: point.craftConfidence,
        sameDayMatchStrength: point.sameDayMatchStrength,
        duplicateLineage: "",
        source: point.source,
        analysisYear: point.year,
        sortOrdinal: point.ordinal,
        analysisFiveYearBand: point.fiveYearBand,
        analysisDecade: point.decade,
        analysisFineSpatialStratum: point.fine,
        analysisCoarseSpatialStratum: point.coarse,
        analysisCoordinatePileGroup: point.pileGroup,
        analysisCoordinatePileCount: point.pileCount,
        configurationPoint: Boolean(point.configurationPoint),
      };
    });
  }

  function pinnedRowsForActiveCohort(activeRowsValue, spatialPointsValue, codebookValue) {
    const activeRows = Array.isArray(activeRowsValue) ? activeRowsValue : [];
    const spatialPoints = Array.isArray(spatialPointsValue) ? spatialPointsValue : [];
    if (!spatialPoints.length) return activeRows;
    const activeIds = new Set(activeRows.map(function (row) {
      return text(firstDefined(row && row.eventId, row && row.event_id));
    }));
    return spatialPoints.map(function (value) {
      return normalizeSpatialPoint(value, codebookValue);
    }).filter(function (point) {
      return activeIds.has(point.eventId);
    }).map(function (point) {
      return {
        eventId: point.eventId,
        mapped: true,
        lat: point.lat,
        lon: point.lon,
        analysisCoordinateClass: point.coordinateEvidence,
        coordinateSource: "raw_latlong",
        datePrecision: "exact_day",
        craftType: point.craft,
        craftConfidence: point.craftConfidence,
        sameDayMatchStrength: point.sameDayMatchStrength,
        duplicateLineage: "",
        source: point.source,
        analysisYear: point.year,
        sortOrdinal: point.ordinal,
        analysisFiveYearBand: point.fiveYearBand,
        analysisDecade: point.decade,
        analysisFineSpatialStratum: point.fine,
        analysisCoarseSpatialStratum: point.coarse,
        analysisCoordinatePileGroup: point.pileGroup,
        analysisCoordinatePileCount: point.pileCount,
      };
    });
  }

  function normalizeContextNeighbor(value, codebookValue) {
    if (Array.isArray(value)) {
      return {
        domain: codeLabel(codebookValue, "contextDomain", value[0], "unknown"),
        lane: codeLabel(codebookValue, "contextLane", value[1], "unknown"),
        contextId: text(value[2]),
        clusterId: text(value[3]),
        contextOrdinal: finite(value[4], null),
        ufoEventId: text(value[5]),
        distanceDecameters: finite(value[6], null),
        dayLag: finite(value[7], null),
        distanceRing: codeLabel(codebookValue, "distanceRing", value[8], "unknown"),
        dayLagBand: codeLabel(codebookValue, "dayLagBand", value[9], "unknown"),
        uncertaintyClass: codeLabel(codebookValue, "uncertaintyClass", value[10], "unknown"),
        contextUncertaintyKm: finite(value[11], null),
        craft: codeLabel(codebookValue, "ufoCraft", value[12], "unknown"),
        source: codeLabel(codebookValue, "ufoSource", value[13], "unknown"),
        fine: codeLabel(codebookValue, "ufoFineSpatialStratum", value[14], "unmapped"),
        coarse: codeLabel(codebookValue, "ufoCoarseSpatialStratum", value[15], "unmapped"),
        featureGroup: codeLabel(codebookValue, "featureGroup", value[16], "unknown"),
        originUfoExcluded: Boolean(value[17]),
        originPublisherExcluded: Boolean(value[18]),
        independentEligible: Boolean(value[19]),
        dateRole: codeLabel(codebookValue, "dateRole", value[20], "unknown"),
        packed: true,
      };
    }
    const row = value || {};
    return {
      domain: text(firstDefined(row.domain, row.contextDomain, row.contextDomainCode), "unknown"),
      lane: text(firstDefined(row.lane, row.contextLane, row.contextLaneCode), "unknown"),
      contextId: text(row.contextId),
      clusterId: text(firstDefined(row.clusterId, row.contextClusterId)),
      contextOrdinal: finite(row.contextOrdinal, null),
      ufoEventId: text(row.ufoEventId),
      distanceDecameters: finite(row.distanceDecameters, null),
      dayLag: finite(row.dayLag, null),
      distanceRing: text(firstDefined(row.distanceRing, row.distanceRingCode), "unknown"),
      dayLagBand: text(firstDefined(row.dayLagBand, row.dayLagBandCode), "unknown"),
      uncertaintyClass: text(firstDefined(row.uncertaintyClass, row.uncertaintyClassCode), "unknown"),
      contextUncertaintyKm: finite(row.contextUncertaintyKm, null),
      craft: text(firstDefined(row.craft, row.ufoCraft, row.ufoCraftCode), "unknown"),
      source: text(firstDefined(row.source, row.ufoSource, row.ufoSourceCode), "unknown"),
      fine: text(firstDefined(row.fine, row.ufoFineSpatialStratum, row.ufoFineSpatialStratumCode), "unmapped"),
      coarse: text(firstDefined(row.coarse, row.ufoCoarseSpatialStratum, row.ufoCoarseSpatialStratumCode), "unmapped"),
      featureGroup: text(firstDefined(row.featureGroup, row.featureGroupCode), "unknown"),
      originUfoExcluded: Boolean(row.originUfoExcluded),
      originPublisherExcluded: Boolean(row.originPublisherExcluded),
      independentEligible: row.independentAssociationEligible == null
        ? Boolean(row.independentEligible)
        : Boolean(row.independentAssociationEligible),
      dateRole: text(firstDefined(row.dateRole, row.dateRoleCode), "unknown"),
      packed: false,
    };
  }

  function contextCellIndex(row) {
    const distance = CONTEXT_DISTANCE_RING_ORDER.indexOf(row.distanceRing);
    const lag = CONTEXT_DAY_LAG_ORDER.indexOf(row.dayLagBand);
    return distance < 0 || lag < 0 ? -1 : (distance * CONTEXT_DAY_LAG_ORDER.length) + lag;
  }

  function contextClusterRoles(rowsValue, observedRole) {
    const roles = [
      observedRole,
      "matched_control_minus_2y",
      "matched_control_minus_1y",
      "matched_control_plus_1y",
      "matched_control_plus_2y",
    ];
    const clusters = new Map();
    (Array.isArray(rowsValue) ? rowsValue : []).forEach(function (row) {
      const cell = contextCellIndex(row);
      if (roles.indexOf(row.dateRole) === -1 || !row.clusterId) return;
      if (!clusters.has(row.clusterId)) clusters.set(row.clusterId, new Map());
      if (cell < 0) return;
      const roleMap = clusters.get(row.clusterId);
      if (!roleMap.has(row.dateRole)) roleMap.set(row.dateRole, new Set());
      roleMap.get(row.dateRole).add(cell);
    });
    return { roles, clusters: Array.from(clusters.entries()).sort(function (left, right) { return left[0].localeCompare(right[0]); }) };
  }

  function contextTotals(clusterEntries, roles) {
    const observed = new Int32Array(16);
    const controls = Array.from({ length: roles.length - 1 }, function () { return new Int32Array(16); });
    clusterEntries.forEach(function (entry) {
      const roleMap = entry[1];
      const observedSet = roleMap.get(roles[0]);
      if (observedSet) observedSet.forEach(function (cell) { observed[cell] += 1; });
      for (let roleIndex = 1; roleIndex < roles.length; roleIndex += 1) {
        const values = roleMap.get(roles[roleIndex]);
        if (values) values.forEach(function (cell) { controls[roleIndex - 1][cell] += 1; });
      }
    });
    const expected = new Float64Array(16);
    for (let cell = 0; cell < 16; cell += 1) {
      expected[cell] = controls.reduce(function (sum, values) { return sum + values[cell]; }, 0) / Math.max(1, controls.length);
    }
    return { observed, controls, expected };
  }

  function contextHoldoutSensitivity(rows, observedRole, baseEffects, selector, minimumN) {
    const groupCounts = new Map();
    rows.filter(function (row) { return row.dateRole === observedRole && row.ufoEventId; }).forEach(function (row) {
      const key = text(selector(row), "unknown");
      groupCounts.set(key, (groupCounts.get(key) || 0) + 1);
    });
    const total = Array.from(groupCounts.values()).reduce(function (sum, value) { return sum + value; }, 0);
    const groups = Array.from(groupCounts.entries()).filter(function (entry) {
      return entry[1] >= minimumN && total - entry[1] >= minimumN;
    }).sort(function (left, right) { return left[0].localeCompare(right[0]); });
    const effects = Array.from({ length: 16 }, function () { return []; });
    groups.forEach(function (entry) {
      const remaining = rows.filter(function (row) { return text(selector(row), "unknown") !== entry[0]; });
      const prepared = contextClusterRoles(remaining, observedRole);
      const totals = contextTotals(prepared.clusters, prepared.roles);
      for (let cell = 0; cell < 16; cell += 1) {
        effects[cell].push({
          omitted: entry[0],
          omittedN: entry[1],
          log2Enrichment: effectValue(totals.observed[cell], totals.expected[cell]),
        });
      }
    });
    return effects.map(function (values, cell) {
      return summarizeHoldoutEffects(baseEffects[cell], values);
    });
  }

  function contextFeatureAssociation(rowsValue, lane, observedRole, optionsValue) {
    const options = optionsValue || {};
    const rows = (Array.isArray(rowsValue) ? rowsValue : []).filter(function (row) {
      return row.ufoEventId && row.craft && row.craft !== "none";
    });
    const observedFeatureClusters = new Map();
    rows.filter(function (row) { return row.dateRole === observedRole; }).forEach(function (row) {
      const feature = text(row.featureGroup, "unknown");
      if (!observedFeatureClusters.has(feature)) observedFeatureClusters.set(feature, new Set());
      observedFeatureClusters.get(feature).add(row.clusterId);
    });
    const sparseLabel = lane === "animal_public_marker" ? "other_sparse_species" : "other_sparse_morphology";
    const featureMap = new Map();
    observedFeatureClusters.forEach(function (clusters, feature) {
      featureMap.set(feature, feature === "unknown" || clusters.size >= 25 ? feature : sparseLabel);
    });
    function prepare(mapper) {
      const crafts = Array.from(new Set(rows.map(function (row) { return row.craft; }))).sort();
      const features = Array.from(new Set(rows.map(function (row) {
        return mapper(text(row.featureGroup, "unknown"));
      }))).sort(function (left, right) {
        if (left === "unknown") return 1;
        if (right === "unknown") return -1;
        if (left === sparseLabel) return 1;
        if (right === sparseLabel) return -1;
        return left.localeCompare(right);
      });
      const craftIndex = new Map(crafts.map(function (value, index) { return [value, index]; }));
      const featureIndex = new Map(features.map(function (value, index) { return [value, index]; }));
      const roles = [
        observedRole, "matched_control_minus_2y", "matched_control_minus_1y",
        "matched_control_plus_1y", "matched_control_plus_2y",
      ];
      const clusters = new Map();
      rows.forEach(function (row) {
        if (roles.indexOf(row.dateRole) === -1) return;
        const cell = (craftIndex.get(row.craft) * features.length) + featureIndex.get(mapper(text(row.featureGroup, "unknown")));
        if (!clusters.has(row.clusterId)) clusters.set(row.clusterId, new Map());
        const roleMap = clusters.get(row.clusterId);
        if (!roleMap.has(row.dateRole)) roleMap.set(row.dateRole, new Set());
        roleMap.get(row.dateRole).add(cell);
      });
      return {
        crafts, features, roles,
        clusters: Array.from(clusters.entries()).sort(function (left, right) { return left[0].localeCompare(right[0]); }),
        cellCount: crafts.length * features.length,
      };
    }
    function totals(prepared) {
      const observed = new Int32Array(prepared.cellCount);
      const controls = Array.from({ length: 4 }, function () { return new Int32Array(prepared.cellCount); });
      prepared.clusters.forEach(function (entry) {
        const roleMap = entry[1];
        const actual = roleMap.get(observedRole);
        if (actual) actual.forEach(function (cell) { observed[cell] += 1; });
        for (let roleIndex = 1; roleIndex < prepared.roles.length; roleIndex += 1) {
          const values = roleMap.get(prepared.roles[roleIndex]);
          if (values) values.forEach(function (cell) { controls[roleIndex - 1][cell] += 1; });
        }
      });
      const expected = new Float64Array(prepared.cellCount);
      for (let cell = 0; cell < prepared.cellCount; cell += 1) {
        expected[cell] = controls.reduce(function (sum, values) { return sum + values[cell]; }, 0) / 4;
      }
      return { observed, expected };
    }
    function descriptiveCells(prepared, summary) {
      const cells = [];
      prepared.crafts.forEach(function (craft, craftIndex) {
        prepared.features.forEach(function (feature, featureIndex) {
          const index = (craftIndex * prepared.features.length) + featureIndex;
          cells.push({
            row: craft,
            column: feature,
            observedClusterCount: summary.observed[index],
            expectedClusterCount: round(summary.expected[index], 4),
            log2Enrichment: round(effectValue(summary.observed[index], summary.expected[index]), 6),
          });
        });
      });
      return cells;
    }
    const pooled = prepare(function (feature) { return featureMap.get(feature) || feature; });
    const pooledTotals = totals(pooled);
    const permutationCount = Math.max(0, Math.trunc(finite(options.permutationCount, 499)));
    const random = seededRandom(text(options.seed, ESTIMATOR_VERSION + "|feature|" + lane));
    const nullCounts = Array.from({ length: pooled.cellCount }, function () { return []; });
    for (let replicate = 0; replicate < permutationCount; replicate += 1) {
      const counts = new Int32Array(pooled.cellCount);
      pooled.clusters.forEach(function (entry) {
        const selectedRole = pooled.roles[Math.floor(random() * pooled.roles.length)];
        const values = entry[1].get(selectedRole);
        if (values) values.forEach(function (cell) { counts[cell] += 1; });
      });
      for (let cell = 0; cell < pooled.cellCount; cell += 1) nullCounts[cell].push(counts[cell]);
    }
    const inferenceEnabled = options.inferenceEnabled !== false;
    const cells = descriptiveCells(pooled, pooledTotals);
    cells.forEach(function (cell, index) {
      const observed = cell.observedClusterCount;
      const expected = cell.expectedClusterCount;
      const nullValues = nullCounts[index];
      const difference = observed - expected;
      const extreme = nullValues.filter(function (value) {
        return Math.abs(value - expected) >= Math.abs(difference) - 1e-12;
      }).length;
      const reasons = [];
      if (observed < 25) reasons.push("observed_clusters_below_25");
      if (expected < 10) reasons.push("expected_clusters_below_10");
      if (Math.abs(cell.log2Enrichment) < Math.log2(1.25)) reasons.push("effect_below_1_25x");
      cell.pValue = inferenceEnabled && nullValues.length ? round((extreme + 1) / (nullValues.length + 1), 8) : null;
      cell.qValue = null;
      cell.estimateAvailable = observed > 0 || expected > 0;
      cell.inferenceEligible = false;
      cell.evidenceStatus = reasons.length ? "low_support" : "candidate";
      cell.supportReasons = reasons;
      cell.patternFinderEligible = false;
    });
    if (inferenceEnabled) benjaminiHochberg(cells);
    cells.forEach(function (cell) {
      if (cell.evidenceStatus === "candidate" && finite(cell.qValue, 1) <= 0.05) {
        cell.evidenceStatus = "qualified_exploratory";
        cell.inferenceEligible = true;
        cell.patternFinderEligible = lane === "crop_bounded";
      } else if (cell.evidenceStatus === "candidate") {
        cell.evidenceStatus = "not_statistically_qualified";
        cell.supportReasons.push("q_above_0_05");
      }
    });
    const complete = prepare(function (feature) { return feature; });
    return {
      unitOfAnalysis: "unique context location-date cluster by neighboring craft and context feature",
      axes: { rows: pooled.crafts, columns: pooled.features },
      cells,
      permutationCount,
      poolingThreshold: 25,
      pooledFeatureGroups: Array.from(featureMap.entries()).filter(function (entry) {
        return entry[0] !== entry[1];
      }).map(function (entry) { return entry[0]; }).sort(),
      completeAccessibleTable: {
        axes: { rows: complete.crafts, columns: complete.features },
        cells: descriptiveCells(complete, totals(complete)),
      },
    };
  }

  function computeContextLane(laneValue, optionsValue) {
    const options = optionsValue || {};
    const rows = Array.isArray(options.rows) ? options.rows : [];
    const lane = text(laneValue);
    const laneRows = rows.filter(function (row) { return row.lane === lane && row.independentEligible; });
    const observedRole = lane === "animal_public_marker" ? "observed_reported_date" : "observed_catalog_date";
    const prepared = contextClusterRoles(laneRows, observedRole);
    const totals = contextTotals(prepared.clusters, prepared.roles);
    const random = seededRandom(text(options.seed, ESTIMATOR_VERSION + "|context|" + lane));
    const permutationCount = Math.max(0, Math.trunc(finite(options.permutationCount, 499)));
    const bootstrapCount = Math.max(0, Math.trunc(finite(options.bootstrapCount, 199)));
    const nullCounts = Array.from({ length: 16 }, function () { return []; });
    for (let replicate = 0; replicate < permutationCount; replicate += 1) {
      const counts = new Int32Array(16);
      prepared.clusters.forEach(function (entry) {
        const role = prepared.roles[Math.floor(random() * prepared.roles.length)];
        const values = entry[1].get(role);
        if (values) values.forEach(function (cell) { counts[cell] += 1; });
      });
      for (let cell = 0; cell < 16; cell += 1) nullCounts[cell].push(counts[cell]);
    }
    const bootstrapEffects = Array.from({ length: 16 }, function () { return []; });
    if (prepared.clusters.length) {
      for (let replicate = 0; replicate < bootstrapCount; replicate += 1) {
        const sampled = [];
        for (let draw = 0; draw < prepared.clusters.length; draw += 1) {
          sampled.push(prepared.clusters[Math.floor(random() * prepared.clusters.length)]);
        }
        const sampledTotals = contextTotals(sampled, prepared.roles);
        for (let cell = 0; cell < 16; cell += 1) {
          bootstrapEffects[cell].push(effectValue(sampledTotals.observed[cell], sampledTotals.expected[cell]));
        }
      }
    }
    const baseEffects = Array.from({ length: 16 }, function (_unused, cell) {
      return effectValue(totals.observed[cell], totals.expected[cell]);
    });
    const sourceSensitivity = contextHoldoutSensitivity(laneRows, observedRole, baseEffects, function (row) { return row.source; }, 25);
    const regionSensitivity = contextHoldoutSensitivity(laneRows, observedRole, baseEffects, function (row) { return row.coarse; }, 25);
    const inferential = options.inferenceEnabled !== false;
    const cells = [];
    for (let distanceIndex = 0; distanceIndex < CONTEXT_DISTANCE_RING_ORDER.length; distanceIndex += 1) {
      for (let lagIndex = 0; lagIndex < CONTEXT_DAY_LAG_ORDER.length; lagIndex += 1) {
        const cellIndex = (distanceIndex * CONTEXT_DAY_LAG_ORDER.length) + lagIndex;
        const observed = totals.observed[cellIndex];
        const expected = totals.expected[cellIndex];
        const nullValues = nullCounts[cellIndex];
        const difference = observed - expected;
        const extreme = nullValues.filter(function (value) {
          return Math.abs(value - expected) >= Math.abs(difference) - 1e-12;
        }).length;
        const effect = baseEffects[cellIndex];
        const reasons = [];
        if (prepared.clusters.length < 25) reasons.push("context_clusters_below_25");
        if (observed < 25) reasons.push("observed_clusters_below_25");
        if (expected < 10) reasons.push("expected_clusters_below_10");
        if (Math.abs(effect) < Math.log2(1.25)) reasons.push("effect_below_1_25x");
        cells.push({
          estimatorVersion: ESTIMATOR_VERSION,
          row: CONTEXT_DISTANCE_RING_ORDER[distanceIndex],
          column: CONTEXT_DAY_LAG_ORDER[lagIndex],
          observedClusterCount: observed,
          expectedClusterCount: round(expected, 4),
          log2Enrichment: round(effect, 6),
          effectInterval: bootstrapEffects[cellIndex].length
            ? [round(quantile(bootstrapEffects[cellIndex], 0.025), 6), round(quantile(bootstrapEffects[cellIndex], 0.975), 6)]
            : [null, null],
          pValue: inferential && nullValues.length ? round((extreme + 1) / (nullValues.length + 1), 8) : null,
          qValue: null,
          estimateAvailable: observed > 0 || expected > 0,
          inferenceEligible: false,
          evidenceStatus: reasons.length ? "low_support" : "candidate",
          supportReasons: reasons,
          sourceSensitivity: sourceSensitivity[cellIndex],
          regionSensitivity: regionSensitivity[cellIndex],
          patternFinderEligible: false,
        });
      }
    }
    if (inferential) benjaminiHochberg(cells);
    cells.forEach(function (cell) {
      if (cell.evidenceStatus === "candidate" && finite(cell.qValue, 1) <= 0.05) {
        cell.evidenceStatus = "qualified_exploratory";
        cell.inferenceEligible = true;
        cell.patternFinderEligible = lane === "crop_bounded" &&
          cell.sourceSensitivity.signStable === true && cell.regionSensitivity.signStable === true;
      } else if (cell.evidenceStatus === "candidate") {
        cell.evidenceStatus = "not_statistically_qualified";
        cell.supportReasons.push("q_above_0_05");
      }
    });
    const observedRows = laneRows.filter(function (row) { return row.dateRole === observedRole && row.ufoEventId; });
    const allLaneRows = rows.filter(function (row) { return row.lane === lane; });
    const uncertaintyCounts = {};
    observedRows.forEach(function (row) {
      uncertaintyCounts[row.uncertaintyClass] = (uncertaintyCounts[row.uncertaintyClass] || 0) + 1;
    });
    return {
      estimatorVersion: ESTIMATOR_VERSION,
      lane,
      evidenceClass: lane === "crop_bounded" ? "bounded_location" : "rough_public_marker",
      observedDateRole: observedRole,
      unitOfAnalysis: "unique context location-date cluster with at least one eligible UFO report marker",
      contextClusterN: prepared.clusters.length,
      observedContextClusterN: prepared.clusters.filter(function (entry) {
        const values = entry[1].get(observedRole);
        return values && values.size;
      }).length,
      observedPairN: observedRows.length,
      excludedObservedPairN: allLaneRows.filter(function (row) {
        return row.dateRole === observedRole && row.ufoEventId && !row.independentEligible;
      }).length,
      permutationCount,
      bootstrapCount,
      axes: { rows: CONTEXT_DISTANCE_RING_ORDER.slice(), columns: CONTEXT_DAY_LAG_ORDER.slice() },
      cells,
      featureAssociation: contextFeatureAssociation(laneRows, lane, observedRole, {
        permutationCount,
        inferenceEnabled: inferential,
        seed: text(options.seed) + "|feature",
      }),
      uncertaintyCounts,
      definiteNearEligible: lane === "crop_bounded",
      patternFinderLaneEligible: lane === "crop_bounded",
      policyWarnings: lane === "animal_public_marker"
        ? ["Public-marker association only; generalized animal markers never establish definite proximity."]
        : lane === "crop_locality"
          ? ["Crop-locality centroid association only; distances do not locate a formation site.", "Time is catalog date, not established formation time."]
          : ["Bounded crop-marker association uses catalog dates, not established formation times."],
    };
  }

  function computeContextAssociations(optionsValue) {
    const options = optionsValue || {};
    const activeIds = new Set((Array.isArray(options.activeRows) ? options.activeRows : []).map(function (row) {
      return text(firstDefined(row && row.eventId, row && row.event_id));
    }));
    const codebook = options.codebook || {};
    const includeAllWhenNoActiveRows = options.includeAllWhenNoActiveRows === true;
    const normalized = (Array.isArray(options.neighbors) ? options.neighbors : []).map(function (row) {
      return normalizeContextNeighbor(row, codebook);
    }).filter(function (row) {
      return !row.ufoEventId || activeIds.has(row.ufoEventId) || (includeAllWhenNoActiveRows && !activeIds.size);
    });
    return {
      estimatorVersion: ESTIMATOR_VERSION,
      traceInputsRead: false,
      matchedNull: "same-location same-season controls at -2, -1, +1, and +2 years",
      lanes: ["crop_bounded", "crop_locality", "animal_public_marker"].map(function (lane) {
        return computeContextLane(lane, {
          rows: normalized,
          seed: text(options.seed) + "|" + lane,
          permutationCount: options.permutationCount,
          bootstrapCount: options.bootstrapCount,
          inferenceEnabled: options.inferenceEnabled,
        });
      }),
      policyWarnings: [
        "Point-marker associations are exploratory and non-causal.",
        "Chronology connectors are prohibited estimator inputs.",
        "Originating UFO events and animal-record publishers are excluded from independent animal lanes.",
      ],
    };
  }

  function normalizeRelationship(value, codebookValue) {
    if (Array.isArray(value)) {
      return {
        relationshipId: text(value[0]),
        subjectId: text(value[1]),
        objectDomain: codeLabel(codebookValue, "objectDomain", value[2], "unknown"),
        objectId: text(value[3]),
        lane: codeLabel(codebookValue, "assertionMode", value[4], "unknown"),
        relationshipType: codeLabel(codebookValue, "relationshipType", value[5], "unknown"),
        reviewState: codeLabel(codebookValue, "reviewState", value[6], "unknown"),
        currentUfoEventId: value[7] == null ? "" : text(value[7]),
        reconciliation: codeLabel(codebookValue, "reconciliationStatus", value[8], "unknown"),
        associationEligible: Boolean(value[9]),
        sourceInputCount: finite(value[10], 0),
      };
    }
    const row = value || {};
    return {
      relationshipId: text(row.relationshipId),
      subjectId: text(row.subjectAnalysisId),
      objectDomain: text(firstDefined(row.objectDomain, row.objectDomainCode), "unknown"),
      objectId: text(row.objectAnalysisId),
      lane: text(firstDefined(row.lane, row.assertionMode, row.assertionModeCode), "unknown"),
      relationshipType: text(firstDefined(row.relationshipType, row.relationshipTypeCode), "unknown"),
      reviewState: text(firstDefined(row.reviewState, row.reviewStateCode), "unknown"),
      currentUfoEventId: row.currentUfoEventId == null ? "" : text(row.currentUfoEventId),
      reconciliation: text(firstDefined(row.reconciliation, row.reconciliationStatus, row.reconciliationStatusCode), "unknown"),
      associationEligible: Boolean(row.associationEligible),
      sourceInputCount: finite(row.sourceInputCount, 0),
    };
  }

  function computeRelationshipSummary(rowsValue, codebookValue, activeRowsValue, optionsValue) {
    const options = optionsValue || {};
    const includeAllWhenNoActiveRows = options.includeAllWhenNoActiveRows === true;
    const activeIds = new Set((Array.isArray(activeRowsValue) ? activeRowsValue : []).map(function (row) {
      return text(firstDefined(row && row.eventId, row && row.event_id));
    }));
    const rows = (Array.isArray(rowsValue) ? rowsValue : []).map(function (row) {
      return normalizeRelationship(row, codebookValue);
    }).filter(function (row) {
      return !row.currentUfoEventId || activeIds.has(row.currentUfoEventId) || (includeAllWhenNoActiveRows && !activeIds.size);
    });
    const lanes = Array.from(new Set(rows.map(function (row) { return row.lane; }))).sort();
    const relationshipTypes = Array.from(new Set(rows.map(function (row) { return row.relationshipType; }))).sort();
    const reconciliations = Array.from(new Set(rows.map(function (row) { return row.reconciliation; }))).sort();
    const counts = new Map();
    rows.forEach(function (row) {
      const key = row.lane + "|" + row.relationshipType + "|" + row.reconciliation;
      counts.set(key, (counts.get(key) || 0) + 1);
    });
    const cells = [];
    lanes.forEach(function (lane) {
      relationshipTypes.forEach(function (relationshipType) {
        reconciliations.forEach(function (reconciliation) {
          const count = counts.get(lane + "|" + relationshipType + "|" + reconciliation) || 0;
          if (!count) return;
          cells.push({ lane, row: relationshipType, column: reconciliation, count, descriptiveOnly: true });
        });
      });
    });
    return {
      estimatorVersion: ESTIMATOR_VERSION,
      unitOfAnalysis: "provenance-bearing relationship record",
      totalN: rows.length,
      lanes,
      relationshipTypes,
      reconciliations,
      cells,
      descriptiveOnly: true,
      policyWarnings: [
        "Explicit-source and deterministic-candidate lanes remain separate.",
        "Relationship records are descriptive and are not recomputed proximity evidence.",
      ],
    };
  }

  function normalizeFacility(facilityValue, codebookValue) {
    if (Array.isArray(facilityValue)) {
      return {
        id: text(facilityValue[0]),
        facilityClass: codeLabel(codebookValue, "class", facilityValue[1], "unknown").toLowerCase(),
        name: text(facilityValue[2]),
        lat: finite(facilityValue[3], null),
        lon: finite(facilityValue[4], null),
        coordinatePrecision: codeLabel(codebookValue, "coordinatePrecision", facilityValue[5], "unknown").toLowerCase(),
        coordinateConfidence: codeLabel(codebookValue, "coordinateConfidence", facilityValue[6], "unknown").toLowerCase(),
        uncertaintyKm: Math.max(0, finite(facilityValue[7], 0)),
        temporalConfidence: codeLabel(codebookValue, "temporalConfidence", facilityValue[8], "unknown").toLowerCase(),
        activeIntervals: Array.isArray(facilityValue[9]) ? facilityValue[9] : [],
        status: codeLabel(codebookValue, "status", facilityValue[10], "unknown").toLowerCase(),
        country: codeLabel(codebookValue, "country", facilityValue[11], "unknown"),
        provenance: codeLabel(codebookValue, "provenance", facilityValue[12], "unknown"),
        inferentialEligible: Boolean(facilityValue[13]),
        exclusionReasonCodes: Array.isArray(facilityValue[14]) ? facilityValue[14].slice() : [],
        packed: true,
      };
    }
    const value = facilityValue || {};
    return {
      id: text(firstDefined(value.id, value.facilityId, value.facility_id)),
      facilityClass: text(firstDefined(value.facilityClass, value.facility_class, value.category), "unknown").toLowerCase(),
      name: text(value.name),
      lat: finite(value.lat, null),
      lon: finite(value.lon, null),
      coordinatePrecision: text(firstDefined(value.coordinatePrecision, value.coordinate_precision), "unknown").toLowerCase(),
      coordinateConfidence: text(firstDefined(value.coordinateConfidence, value.coordinate_confidence), "unknown").toLowerCase(),
      uncertaintyKm: Math.max(0, finite(firstDefined(value.uncertaintyKm, value.uncertainty_km), 0)),
      temporalConfidence: text(firstDefined(value.temporalConfidence, value.temporal_confidence), "unknown").toLowerCase(),
      activeIntervals: Array.isArray(firstDefined(value.activeIntervals, value.active_intervals))
        ? firstDefined(value.activeIntervals, value.active_intervals)
        : [],
      status: text(value.status, "unknown").toLowerCase(),
      country: text(value.country, "unknown"),
      provenance: text(value.provenance, "unknown"),
      inferentialEligible: Object.prototype.hasOwnProperty.call(value, "inferentialEligible")
        ? Boolean(value.inferentialEligible)
        : null,
      exclusionReasonCodes: Array.isArray(value.exclusionReasonCodes) ? value.exclusionReasonCodes.slice() : [],
      packed: Boolean(value.packed),
    };
  }

  function facilityIsInferential(facilityValue, codebookValue) {
    const value = normalizeFacility(facilityValue, codebookValue);
    const acceptedClasses = new Set(["military", "research_test", "research", "research/test"]);
    if (value.packed && (value.facilityClass === "1" || value.facilityClass === "2")) {
      return Boolean(value.inferentialEligible) && Number.isFinite(value.lat) && Number.isFinite(value.lon) && value.lat >= -90 && value.lat <= 90;
    }
    if (!acceptedClasses.has(value.facilityClass)) return false;
    if (!Number.isFinite(value.lat) || !Number.isFinite(value.lon) || value.lat < -90 || value.lat > 90) return false;
    if (value.inferentialEligible != null) return value.inferentialEligible;
    const accepted = new Set(["medium", "high", "verified", "exact", "strong"]);
    return accepted.has(value.coordinateConfidence) && accepted.has(value.temporalConfidence) && value.activeIntervals.length > 0;
  }

  function facilityActiveAt(facilityValue, ordinalValue, yearValue, codebookValue) {
    const facility = normalizeFacility(facilityValue, codebookValue);
    const ordinal = finite(ordinalValue, null);
    if (ordinal == null) return "unknown";
    const intervals = Array.isArray(facility.activeIntervals)
      ? facility.activeIntervals
      : [{
          startOrdinal: facility.startOrdinal,
          endOrdinal: facility.endOrdinal,
          startYear: facility.startYear,
          endYear: facility.endYear,
        }];
    let boundaryUnknown = false;
    for (const intervalValue of intervals) {
      const interval = Array.isArray(intervalValue)
        ? { startYear: intervalValue[0], endYear: intervalValue[1] }
        : (intervalValue || {});
      const explicitStartYear = interval.startYear == null ? interval.start_year : interval.startYear;
      const explicitEndYear = interval.endYear == null ? interval.end_year : interval.endYear;
      const intervalStartOrdinal = interval.startOrdinal == null ? interval.start_ordinal : interval.startOrdinal;
      const looksLikeYears = explicitStartYear != null || explicitEndYear != null ||
        (Number.isFinite(Number(intervalStartOrdinal)) && Math.abs(Number(intervalStartOrdinal)) < 10000);
      if (looksLikeYears) {
        const year = finite(yearValue, null);
        if (year == null) {
          boundaryUnknown = true;
          continue;
        }
        const startYear = finite(explicitStartYear == null ? intervalStartOrdinal : explicitStartYear, -Infinity);
        const intervalEndOrdinal = interval.endOrdinal == null ? interval.end_ordinal : interval.endOrdinal;
        const endYear = finite(explicitEndYear == null ? intervalEndOrdinal : explicitEndYear, Infinity);
        const boundaryYears = Math.max(0, finite(
          interval.boundaryUncertaintyYears == null ? interval.boundary_uncertainty_years : interval.boundaryUncertaintyYears,
          0
        ));
        if (year >= startYear + boundaryYears && year <= endYear - boundaryYears) return "active";
        if (year >= startYear - boundaryYears && year <= endYear + boundaryYears) boundaryUnknown = true;
        continue;
      }
      const intervalEndOrdinal = interval.endOrdinal == null ? interval.end_ordinal : interval.endOrdinal;
      const start = finite(intervalStartOrdinal, -Infinity);
      const end = finite(intervalEndOrdinal, Infinity);
      const boundary = Math.max(0, finite(
        interval.boundaryUncertaintyDays == null ? interval.boundary_uncertainty_days : interval.boundaryUncertaintyDays,
        0
      ));
      if (ordinal >= start + boundary && ordinal <= end - boundary) return "active";
      if (ordinal >= start - boundary && ordinal <= end + boundary) boundaryUnknown = true;
    }
    return boundaryUnknown ? "unknown" : "inactive";
  }

  function facilityBinKey(latitudeBin, longitudeBin) {
    return latitudeBin + "|" + longitudeBin;
  }

  function buildFacilityIndex(facilitiesValue, codebookValue, maximumRadiusMetersValue) {
    const facilities = (Array.isArray(facilitiesValue) ? facilitiesValue : []).map(function (facility) {
      return normalizeFacility(facility, codebookValue);
    }).filter(function (facility) { return facilityIsInferential(facility); });
    const binDegrees = 5;
    const latitudeBinCount = 36;
    const longitudeBinCount = 72;
    const bins = new Map();
    facilities.forEach(function (facility, index) {
      const latitudeBin = Math.max(0, Math.min(latitudeBinCount - 1, Math.floor((facility.lat + 90) / binDegrees)));
      const normalizedLongitude = ((facility.lon + 180) % 360 + 360) % 360;
      const longitudeBin = Math.max(0, Math.min(longitudeBinCount - 1, Math.floor(normalizedLongitude / binDegrees)));
      const key = facilityBinKey(latitudeBin, longitudeBin);
      if (!bins.has(key)) bins.set(key, []);
      bins.get(key).push(index);
    });
    return {
      facilities,
      bins,
      binDegrees,
      latitudeBinCount,
      longitudeBinCount,
      maximumRadiusMeters: Math.max(0, finite(maximumRadiusMetersValue, 250000)),
    };
  }

  function facilityCandidates(indexValue, latitudeValue, longitudeValue) {
    const index = indexValue;
    const latitude = finite(latitudeValue, null);
    const longitude = finite(longitudeValue, null);
    if (!index || latitude == null || longitude == null) return [];
    const angularRadius = index.maximumRadiusMeters / 6371008.8;
    const latitudeRadians = latitude * Math.PI / 180;
    const latitudeDelta = (angularRadius * 180 / Math.PI) + 1e-9;
    const crossesPole = Math.abs(latitudeRadians) + angularRadius >= Math.PI / 2;
    const longitudeDelta = crossesPole
      ? 180
      : Math.min(180, (Math.asin(Math.min(1, Math.sin(angularRadius) / Math.max(1e-12, Math.cos(latitudeRadians)))) * 180 / Math.PI) + 1e-9);
    const minimumLatitudeBin = Math.max(0, Math.floor((Math.max(-90, latitude - latitudeDelta) + 90) / index.binDegrees));
    const maximumLatitudeBin = Math.min(index.latitudeBinCount - 1, Math.floor((Math.min(89.999999, latitude + latitudeDelta) + 90) / index.binDegrees));
    const seen = new Set();
    const result = [];
    for (let latitudeBin = minimumLatitudeBin; latitudeBin <= maximumLatitudeBin; latitudeBin += 1) {
      if (longitudeDelta >= 180) {
        for (let longitudeBin = 0; longitudeBin < index.longitudeBinCount; longitudeBin += 1) {
          const values = index.bins.get(facilityBinKey(latitudeBin, longitudeBin)) || [];
          values.forEach(function (facilityIndex) {
            if (!seen.has(facilityIndex)) { seen.add(facilityIndex); result.push(index.facilities[facilityIndex]); }
          });
        }
        continue;
      }
      const minimumLongitudeBin = Math.floor((((longitude - longitudeDelta) + 180) % 360 + 360) % 360 / index.binDegrees);
      const maximumLongitudeBin = Math.floor((((longitude + longitudeDelta) + 180) % 360 + 360) % 360 / index.binDegrees);
      const longitudeBins = [];
      if (minimumLongitudeBin <= maximumLongitudeBin) {
        for (let bin = minimumLongitudeBin; bin <= maximumLongitudeBin; bin += 1) longitudeBins.push(bin);
      } else {
        for (let bin = minimumLongitudeBin; bin < index.longitudeBinCount; bin += 1) longitudeBins.push(bin);
        for (let bin = 0; bin <= maximumLongitudeBin; bin += 1) longitudeBins.push(bin);
      }
      longitudeBins.forEach(function (longitudeBin) {
        const values = index.bins.get(facilityBinKey(latitudeBin, longitudeBin)) || [];
        values.forEach(function (facilityIndex) {
          if (!seen.has(facilityIndex)) { seen.add(facilityIndex); result.push(index.facilities[facilityIndex]); }
        });
      });
    }
    return result;
  }

  function nearestFacilityExposure(row, facilityIndex) {
    let nearestActive = Infinity;
    let nearestInactive = Infinity;
    let nearestClass = "unknown";
    const candidates = facilityCandidates(facilityIndex, row.lat, row.lon);
    let distanceEvaluationCount = 0;
    candidates.forEach(function (facility) {
      const distance = greatCircleDistanceMeters(row.lat, row.lon, facility.lat, facility.lon);
      if (distance == null) return;
      distanceEvaluationCount += 1;
      if (distance > facilityIndex.maximumRadiusMeters) return;
      const activity = facilityActiveAt(facility, row.ordinal, row.year);
      if (activity === "active" && distance < nearestActive) {
        nearestActive = distance;
        nearestClass = text(facility.facilityClass, "unknown");
      } else if (activity === "inactive" && distance < nearestInactive) {
        nearestInactive = distance;
      }
    });
    return { nearestActive, nearestInactive, nearestClass, candidateCount: candidates.length, distanceEvaluationCount };
  }

  function prepareFacilityLane(exposuresValue, distanceKey, nearRadius, comparisonMinimum, comparisonMaximum) {
    const candidate = [];
    (Array.isArray(exposuresValue) ? exposuresValue : []).forEach(function (entry) {
      const distance = finite(entry && entry[distanceKey], Infinity);
      let near = null;
      if (distance <= nearRadius) near = true;
      else if (distance >= comparisonMinimum && distance <= comparisonMaximum) near = false;
      if (near == null) return;
      const row = entry.row;
      const adjustmentKey = row.source + "|" + row.decade + "|" + row.coarse;
      candidate.push({ row, near, adjustmentKey, distance });
    });
    const support = new Map();
    candidate.forEach(function (entry) {
      if (!support.has(entry.adjustmentKey)) support.set(entry.adjustmentKey, { near: 0, comparison: 0 });
      support.get(entry.adjustmentKey)[entry.near ? "near" : "comparison"] += 1;
    });
    const supportedKeys = new Set(Array.from(support.entries()).filter(function (entry) {
      return entry[1].near > 0 && entry[1].comparison > 0;
    }).map(function (entry) { return entry[0]; }));
    const entries = candidate.filter(function (entry) { return supportedKeys.has(entry.adjustmentKey); });
    return {
      entries,
      candidateN: candidate.length,
      unsupportedN: candidate.length - entries.length,
      commonSupportRate: candidate.length ? entries.length / candidate.length : 0,
      supportedStratumN: supportedKeys.size,
    };
  }

  function aggregateFacilityStrata(entries, categories, labelsValue) {
    const categoryIndex = new Map(categories.map(function (category, index) { return [category, index]; }));
    const labels = labelsValue || Int16Array.from(entries.map(function (entry) { return categoryIndex.get(entry.row.craft); }));
    const byKey = new Map();
    entries.forEach(function (entry, index) {
      if (!byKey.has(entry.adjustmentKey)) {
        byKey.set(entry.adjustmentKey, {
          key: entry.adjustmentKey,
          source: entry.row.source,
          region: entry.row.coarse,
          nearTotal: 0,
          comparisonTotal: 0,
          nearCounts: new Int32Array(categories.length),
          comparisonCounts: new Int32Array(categories.length),
        });
      }
      const aggregate = byKey.get(entry.adjustmentKey);
      const category = labels[index];
      if (entry.near) {
        aggregate.nearTotal += 1;
        aggregate.nearCounts[category] += 1;
      } else {
        aggregate.comparisonTotal += 1;
        aggregate.comparisonCounts[category] += 1;
      }
    });
    return Array.from(byKey.values()).sort(function (left, right) { return left.key.localeCompare(right.key); });
  }

  function cmhFacilityEffect(aggregatesValue, categoryIndex) {
    const aggregates = Array.isArray(aggregatesValue) ? aggregatesValue : [];
    let numerator = 0;
    let denominator = 0;
    let nearCount = 0;
    let comparisonCount = 0;
    let nearTotal = 0;
    let comparisonTotal = 0;
    let expectedNearCount = 0;
    aggregates.forEach(function (aggregate) {
      const a = aggregate.nearCounts[categoryIndex] || 0;
      const b = aggregate.nearTotal - a;
      const c = aggregate.comparisonCounts[categoryIndex] || 0;
      const d = aggregate.comparisonTotal - c;
      const n = a + b + c + d;
      if (!n) return;
      numerator += (a * d) / n;
      denominator += (b * c) / n;
      nearCount += a;
      comparisonCount += c;
      nearTotal += aggregate.nearTotal;
      comparisonTotal += aggregate.comparisonTotal;
      expectedNearCount += aggregate.nearTotal * (a + c) / n;
    });
    if (!(numerator > 0) || !(denominator > 0)) {
      numerator = 0;
      denominator = 0;
      aggregates.forEach(function (aggregate) {
        const a = (aggregate.nearCounts[categoryIndex] || 0) + 0.5;
        const b = aggregate.nearTotal - (aggregate.nearCounts[categoryIndex] || 0) + 0.5;
        const c = (aggregate.comparisonCounts[categoryIndex] || 0) + 0.5;
        const d = aggregate.comparisonTotal - (aggregate.comparisonCounts[categoryIndex] || 0) + 0.5;
        const n = a + b + c + d;
        numerator += (a * d) / n;
        denominator += (b * c) / n;
      });
    }
    return {
      commonOddsRatio: denominator > 0 ? numerator / denominator : null,
      nearCount,
      comparisonCount,
      nearTotal,
      comparisonTotal,
      expectedNearCount,
    };
  }

  function facilityHoldoutSensitivity(aggregates, categoryIndex, groupKey, minimumN, baseOddsRatio) {
    const counts = new Map();
    aggregates.forEach(function (aggregate) {
      const key = text(aggregate[groupKey], "unknown");
      counts.set(key, (counts.get(key) || 0) + aggregate.nearTotal + aggregate.comparisonTotal);
    });
    const total = Array.from(counts.values()).reduce(function (sum, value) { return sum + value; }, 0);
    const effects = Array.from(counts.entries()).filter(function (entry) {
      return entry[1] >= minimumN && total - entry[1] >= minimumN;
    }).sort(function (left, right) { return left[0].localeCompare(right[0]); }).map(function (entry) {
      const remaining = aggregates.filter(function (aggregate) { return text(aggregate[groupKey], "unknown") !== entry[0]; });
      const effect = cmhFacilityEffect(remaining, categoryIndex).commonOddsRatio;
      return {
        omitted: entry[0],
        omittedN: entry[1],
        log2Enrichment: effect > 0 ? Math.log2(effect) : 0,
      };
    });
    return summarizeHoldoutEffects(baseOddsRatio > 0 ? Math.log2(baseOddsRatio) : 0, effects);
  }

  function computeFacilityLane(exposures, optionsValue) {
    const options = optionsValue || {};
    const lane = prepareFacilityLane(
      exposures,
      options.distanceKey,
      options.nearRadius,
      options.comparisonMinimum,
      options.comparisonMaximum
    );
    const categories = Array.from(new Set(lane.entries.map(function (entry) { return entry.row.craft; }))).sort();
    const categoryIndex = new Map(categories.map(function (category, index) { return [category, index]; }));
    const baseLabels = Int16Array.from(lane.entries.map(function (entry) { return categoryIndex.get(entry.row.craft); }));
    const stratumIndexes = new Map();
    lane.entries.forEach(function (entry, index) {
      if (!stratumIndexes.has(entry.adjustmentKey)) stratumIndexes.set(entry.adjustmentKey, []);
      stratumIndexes.get(entry.adjustmentKey).push(index);
    });
    const aggregates = aggregateFacilityStrata(lane.entries, categories, baseLabels);
    const inferential = options.inferential !== false;
    const permutationCount = inferential ? Math.max(0, Math.trunc(finite(options.permutationCount, 499))) : 0;
    const bootstrapCount = inferential ? Math.max(0, Math.trunc(finite(options.bootstrapCount, 199))) : 0;
    const random = seededRandom(text(options.seed, ESTIMATOR_VERSION + "|facility"));
    const nullOdds = Array.from({ length: categories.length }, function () { return []; });
    for (let replicate = 0; replicate < permutationCount; replicate += 1) {
      const permuted = shuffledLabels(baseLabels, Array.from(stratumIndexes.values()), random);
      const permutedAggregates = aggregateFacilityStrata(lane.entries, categories, permuted);
      for (let category = 0; category < categories.length; category += 1) {
        nullOdds[category].push(cmhFacilityEffect(permutedAggregates, category).commonOddsRatio);
      }
    }
    const bootstrapOdds = Array.from({ length: categories.length }, function () { return []; });
    if (aggregates.length) {
      for (let replicate = 0; replicate < bootstrapCount; replicate += 1) {
        const sampled = [];
        for (let draw = 0; draw < aggregates.length; draw += 1) {
          sampled.push(aggregates[Math.floor(random() * aggregates.length)]);
        }
        for (let category = 0; category < categories.length; category += 1) {
          bootstrapOdds[category].push(cmhFacilityEffect(sampled, category).commonOddsRatio);
        }
      }
    }
    const sourceCounts = {};
    const regionCounts = {};
    lane.entries.forEach(function (entry) {
      sourceCounts[entry.row.source] = (sourceCounts[entry.row.source] || 0) + 1;
      regionCounts[entry.row.coarse] = (regionCounts[entry.row.coarse] || 0) + 1;
    });
    const substantiveSources = Object.keys(sourceCounts).filter(function (key) { return sourceCounts[key] >= 25; }).sort();
    const cells = categories.map(function (category, index) {
      const effect = cmhFacilityEffect(aggregates, index);
      const oddsRatio = effect.commonOddsRatio;
      const logEffect = oddsRatio > 0 ? Math.log(oddsRatio) : 0;
      const nullValues = nullOdds[index].filter(function (value) { return value > 0 && Number.isFinite(value); });
      const extreme = nullValues.filter(function (value) { return Math.abs(Math.log(value)) >= Math.abs(logEffect) - 1e-12; }).length;
      const pValue = nullValues.length ? (extreme + 1) / (nullValues.length + 1) : null;
      const intervalValues = bootstrapOdds[index].filter(function (value) { return value > 0 && Number.isFinite(value); });
      const sourceSensitivity = facilityHoldoutSensitivity(aggregates, index, "source", 25, oddsRatio);
      const regionSensitivity = facilityHoldoutSensitivity(aggregates, index, "region", 25, oddsRatio);
      const suppressionReasons = [];
      if (options.activeN < 200) suppressionReasons.push("active_cohort_below_200");
      if (effect.nearCount < 25) suppressionReasons.push("near_observed_below_25");
      if (effect.expectedNearCount < 10) suppressionReasons.push("expected_below_10");
      if (lane.commonSupportRate < 0.8) suppressionReasons.push("common_support_below_80_percent");
      if (!(oddsRatio > 0) || (oddsRatio > 0.8 && oddsRatio < 1.25)) suppressionReasons.push("effect_below_1_25x_or_above_0_80x");
      return {
        estimatorVersion: ESTIMATOR_VERSION,
        artifactHashes: Object.assign({}, options.artifactHashes || {}),
        key: category,
        label: category,
        nearCount: effect.nearCount,
        nearTotal: effect.nearTotal,
        comparisonCount: effect.comparisonCount,
        comparisonTotal: effect.comparisonTotal,
        expectedNearCount: round(effect.expectedNearCount, 4),
        commonOddsRatio: oddsRatio == null ? null : round(oddsRatio, 6),
        oddsRatioInterval: intervalValues.length
          ? [round(quantile(intervalValues, 0.025), 6), round(quantile(intervalValues, 0.975), 6)]
          : [null, null],
        pValue: pValue == null ? null : round(pValue, 8),
        qValue: null,
        covariates: ["source", "decade", "coarse_equal_area_geography"],
        sourceSensitivity,
        regionSensitivity,
        stabilityClass: sourceSensitivity.signStable === true && regionSensitivity.signStable === true
          ? "source_and_region_stable"
          : "source_or_region_sensitive",
        status: inferential ? (suppressionReasons.length ? "suppressed" : "eligible") : "sensitivity",
        suppressionReasons: inferential ? suppressionReasons : [],
      };
    });
    if (inferential) {
      benjaminiHochberg(cells);
      cells.forEach(function (cell) {
        if (cell.status === "eligible" && finite(cell.qValue, 1) > 0.05) {
          cell.status = "suppressed";
          cell.suppressionReasons.push("q_above_0_05");
        }
        cell.patternFinderEligible = cell.status === "eligible" && substantiveSources.length >= 2 &&
          cell.sourceSensitivity.signStable === true && cell.regionSensitivity.signStable === true;
      });
    }
    const nearTotal = lane.entries.filter(function (entry) { return entry.near; }).length;
    const comparisonTotal = lane.entries.length - nearTotal;
    const globalSuppressionReasons = [];
    if (options.activeN < 200) globalSuppressionReasons.push("active_cohort_below_200");
    if (nearTotal < 25) globalSuppressionReasons.push("near_band_below_25");
    if (comparisonTotal < 25) globalSuppressionReasons.push("comparison_band_below_25");
    if (lane.commonSupportRate < 0.8) globalSuppressionReasons.push("common_support_below_80_percent");
    return {
      estimatorVersion: ESTIMATOR_VERSION,
      artifactHashes: Object.assign({}, options.artifactHashes || {}),
      role: text(options.role, inferential ? "inferential" : "sensitivity"),
      status: inferential ? (globalSuppressionReasons.length ? "suppressed" : "exploratory") : "sensitivity",
      suppressionReasons: inferential ? globalSuppressionReasons : [],
      nearRadiusKm: options.nearRadius / 1000,
      comparisonBandKm: [options.comparisonMinimum / 1000, options.comparisonMaximum / 1000],
      candidateN: lane.candidateN,
      supportedN: lane.entries.length,
      unsupportedN: lane.unsupportedN,
      commonSupportRate: round(lane.commonSupportRate, 6),
      supportedStratumN: lane.supportedStratumN,
      nearTotal,
      comparisonTotal,
      permutationCount,
      bootstrapCount,
      covariates: ["source", "decade", "coarse_equal_area_geography"],
      sourceCounts,
      regionCounts,
      substantiveSources,
      multiSourceEligible: substantiveSources.length >= 2,
      categories,
      cells,
    };
  }

  function computeFacilityContext(optionsValue) {
    const options = optionsValue || {};
    const allRows = Array.isArray(options.rows) ? options.rows : [];
    const rows = allRows.filter(function (row) { return spatialEligibilityReason(row) === "eligible"; }).map(spatialRow);
    const facilities = Array.isArray(options.facilities) ? options.facilities : [];
    const facilityCodes = options.facilityCodes || options.facilityCodebook || {};
    const normalizedFacilityCatalog = facilities.map(function (facility) {
      return normalizeFacility(facility, facilityCodes);
    });
    const catalogByClass = {};
    const catalogByPrecision = {};
    normalizedFacilityCatalog.forEach(function (facility) {
      catalogByClass[facility.facilityClass] = (catalogByClass[facility.facilityClass] || 0) + 1;
      catalogByPrecision[facility.coordinatePrecision] = (catalogByPrecision[facility.coordinatePrecision] || 0) + 1;
    });
    const nearRadius = Math.max(0, finite(options.nearRadiusKm, 25) * 1000);
    const comparisonMinimum = Math.max(nearRadius, finite(options.comparisonMinimumKm, 100) * 1000);
    const comparisonMaximum = Math.max(comparisonMinimum, finite(options.comparisonMaximumKm, 250) * 1000);
    const facilityIndex = buildFacilityIndex(facilities, facilityCodes, comparisonMaximum);
    const exposures = rows.map(function (row) {
      return Object.assign({ row }, nearestFacilityExposure(row, facilityIndex));
    });
    const primary = computeFacilityLane(exposures, {
      distanceKey: "nearestActive",
      nearRadius,
      comparisonMinimum,
      comparisonMaximum,
      activeN: allRows.length,
      permutationCount: options.permutationCount,
      bootstrapCount: options.bootstrapCount,
      seed: text(options.seed, ESTIMATOR_VERSION) + "|active-primary",
      inferential: true,
      role: "temporally_active_primary",
      artifactHashes: options.artifactHashes,
    });
    const negativeControl = computeFacilityLane(exposures, {
      distanceKey: "nearestInactive",
      nearRadius,
      comparisonMinimum,
      comparisonMaximum,
      activeN: allRows.length,
      permutationCount: options.permutationCount,
      bootstrapCount: options.bootstrapCount,
      seed: text(options.seed, ESTIMATOR_VERSION) + "|inactive-negative-control",
      inferential: true,
      role: "inactive_at_event_negative_control",
      artifactHashes: options.artifactHashes,
    });
    negativeControl.cells.forEach(function (cell) { cell.patternFinderEligible = false; });
    if (facilityIndex.facilities.length < 25) {
      [primary, negativeControl].forEach(function (lane) {
        lane.status = "suppressed";
        if (!lane.suppressionReasons.includes("inferential_facility_pool_below_25")) {
          lane.suppressionReasons.push("inferential_facility_pool_below_25");
        }
        lane.cells.forEach(function (cell) {
          cell.status = "suppressed";
          cell.patternFinderEligible = false;
          if (!cell.suppressionReasons.includes("inferential_facility_pool_below_25")) {
            cell.suppressionReasons.push("inferential_facility_pool_below_25");
          }
        });
      });
    }
    const sensitivity = [10, 50, 100].map(function (radiusKm) {
      return computeFacilityLane(exposures, {
        distanceKey: "nearestActive",
        nearRadius: radiusKm * 1000,
        comparisonMinimum,
        comparisonMaximum,
        activeN: allRows.length,
        inferential: false,
        role: "radius_sensitivity",
        artifactHashes: options.artifactHashes,
      });
    });
    const descriptiveClaimed = facilities.filter(function (facility) {
      return normalizeFacility(facility, facilityCodes).facilityClass.indexOf("claimed") !== -1;
    }).length;
    const distanceEvaluationCount = exposures.reduce(function (sum, entry) { return sum + entry.distanceEvaluationCount; }, 0);
    const candidateCount = exposures.reduce(function (sum, entry) { return sum + entry.candidateCount; }, 0);
    return {
      estimatorVersion: ESTIMATOR_VERSION,
      artifactHashes: Object.assign({}, options.artifactHashes || {}),
      unitOfAnalysis: "eligible UFO report marker by nearest temporally active facility-marker band",
      status: primary.status,
      suppressionReasons: primary.suppressionReasons,
      activeN: allRows.length,
      eligibleN: rows.length,
      inferentialFacilityN: facilityIndex.facilities.length,
      claimedFacilityN: descriptiveClaimed,
      catalogSummary: {
        totalN: normalizedFacilityCatalog.length,
        inferentialEligibleN: normalizedFacilityCatalog.filter(function (facility) {
          return facilityIsInferential(facility);
        }).length,
        descriptiveOnlyN: normalizedFacilityCatalog.filter(function (facility) {
          return !facilityIsInferential(facility);
        }).length,
        byFacilityClass: catalogByClass,
        byCoordinatePrecision: catalogByPrecision,
        coverageLimitations: ["research_test_supplements_concentrated_in_northern_europe_and_new_zealand"],
      },
      nearBandKm: [0, nearRadius / 1000],
      comparisonBandKm: [comparisonMinimum / 1000, comparisonMaximum / 1000],
      nearTotal: primary.nearTotal,
      comparisonTotal: primary.comparisonTotal,
      commonSupportRate: primary.commonSupportRate,
      supportedN: primary.supportedN,
      covariates: primary.covariates,
      cells: primary.cells,
      primary,
      inactiveNegativeControlN: negativeControl.nearTotal,
      inactiveFacilityNegativeControlN: negativeControl.nearTotal,
      inactiveNegativeControl: negativeControl,
      sensitivity,
      prefilter: {
        method: "5-degree latitude-longitude candidate index with exact great-circle verification",
        packedFacilitySchema: PACKED_FACILITY_SCHEMA.slice(),
        inputFacilityN: facilities.length,
        inferentialFacilityN: facilityIndex.facilities.length,
        reportN: rows.length,
        naiveDistanceEvaluationN: rows.length * facilityIndex.facilities.length,
        candidateN: candidateCount,
        distanceEvaluationN: distanceEvaluationCount,
      },
      policyWarnings: [
        "Craft composition among observed reports only; this is not an incidence or facility-influence estimate.",
        "Distances are report-marker to facility-marker distances, not site-boundary distances.",
        "Claimed UFO sites are descriptive and excluded from inference.",
        "Research/test-site coverage is strongly limited to the Northern Europe and New Zealand supplements.",
      ],
      coverageLimitations: ["research_test_supplements_concentrated_in_northern_europe_and_new_zealand"],
    };
  }

  function contextReadiness(contextValue) {
    const context = contextValue || {};
    const rows = [];
    const defaults = [
      ["ufoCraftPoints", "High-precision co-occurrence pool", "data_unavailable"],
      ["militaryFacilities", "Verified military facilities", "data_unavailable"],
      ["researchFacilities", "Research/test facilities", "data_unavailable"],
      ["claimedUfoSites", "Claimed UFO sites", "ready_descriptive"],
      ["cropBounded", "Crop circles — bounded markers", "data_unavailable"],
      ["cropLocality", "Crop circles — locality markers", "data_unavailable"],
      ["cropCircles", "Crop circles", "data_unavailable"],
      ["animalReports", "Animal reports — public markers", "data_unavailable"],
      ["relationshipReconciliation", "Relationship reconciliation", "data_unavailable"],
    ];
    defaults.forEach(function (definition) {
      const value = context[definition[0]] || {};
      const row = {
        key: definition[0],
        label: definition[1],
        status: text(value.status, definition[2]),
        eligibleN: finite(value.eligibleN, 0),
        totalN: finite(value.totalN, 0),
        reasons: Array.isArray(value.reasons) ? value.reasons.map(String) : [],
        reasonCodes: Array.isArray(value.reasonCodes) ? value.reasonCodes.map(String) : [],
        releaseHash: text(value.releaseHash),
        evidenceHash: text(firstDefined(value.evidenceHash, value.releaseHash)),
        applicability: text(value.applicability, "applicable"),
        inputN: finite(firstDefined(value.inputN, value.totalN), 0),
        passedN: finite(firstDefined(value.passedN, value.eligibleN), 0),
        failedN: finite(value.failedN, Math.max(0, finite(value.totalN, 0) - finite(value.eligibleN, 0))),
        unknownN: finite(value.unknownN, 0),
        denominatorLabel: text(value.denominatorLabel, "domain records"),
        policyId: text(value.policyId, "analysis_v2_2_domain_readiness"),
        gates: (Array.isArray(value.gates) ? value.gates : []).map(function (gate) {
          return Object.assign({}, gate, {
            gateId: text(gate && gate.gateId),
            label: text(gate && gate.label, gate && gate.gateId),
            status: text(gate && gate.status, "not_evaluated"),
            applicability: text(gate && gate.applicability, "applicable"),
            reasonCodes: Array.isArray(gate && gate.reasonCodes) ? gate.reasonCodes.map(String) : [],
          });
        }),
      };
      const laneCounts = value.laneCounts || value.lane_counts || value.details || null;
      if (laneCounts && typeof laneCounts === "object") row.laneCounts = Object.assign({}, laneCounts);
      rows.push(row);
    });
    return rows;
  }

  function appendUniqueReason(target, reason) {
    if (!target || typeof target !== "object") return;
    const reasons = Array.isArray(target.suppressionReasons) ? target.suppressionReasons.slice() : [];
    if (reasons.indexOf(reason) === -1) reasons.push(reason);
    target.suppressionReasons = reasons;
  }

  function removeInferentialFields(value) {
    if (Array.isArray(value)) {
      value.forEach(removeInferentialFields);
      return value;
    }
    if (!value || typeof value !== "object") return value;
    if (Object.prototype.hasOwnProperty.call(value, "pValue")) value.pValue = null;
    if (Object.prototype.hasOwnProperty.call(value, "qValue")) value.qValue = null;
    if (Object.prototype.hasOwnProperty.call(value, "p_value")) value.p_value = null;
    if (Object.prototype.hasOwnProperty.call(value, "q_value")) value.q_value = null;
    if (Object.prototype.hasOwnProperty.call(value, "patternFinderEligible")) value.patternFinderEligible = false;
    if (Object.prototype.hasOwnProperty.call(value, "pattern_finder_eligible")) value.pattern_finder_eligible = false;
    Object.keys(value).forEach(function (key) { removeInferentialFields(value[key]); });
    return value;
  }

  function markEvidenceLaneDescriptive(lane) {
    if (!lane || typeof lane !== "object") return;
    lane.status = "descriptive_only";
    lane.inferenceEnabled = false;
    appendUniqueReason(lane, "full_catalog_overlap_descriptive_no_inference");
    (Array.isArray(lane.cells) ? lane.cells : []).forEach(function (cell) {
      if (!cell || typeof cell !== "object") return;
      cell.status = "descriptive_only";
      cell.inferenceEligible = false;
      cell.patternFinderEligible = false;
      if (Object.prototype.hasOwnProperty.call(cell, "evidenceStatus")) cell.evidenceStatus = "descriptive_only";
      appendUniqueReason(cell, "full_catalog_overlap_descriptive_no_inference");
    });
    if (lane.featureAssociation && lane.featureAssociation !== lane) {
      markEvidenceLaneDescriptive(lane.featureAssociation);
    }
  }

  function enforceDescriptiveOnlyBaseline(resultValue) {
    const result = resultValue || {};
    removeInferentialFields(result);
    const cooccurrence = result.cooccurrence || {};
    ["crossSource", "sameSource"].forEach(function (key) {
      (Array.isArray(cooccurrence[key]) ? cooccurrence[key] : []).forEach(markEvidenceLaneDescriptive);
    });
    const configuration = cooccurrence.configuration || {};
    ["crossSource", "sameSource"].forEach(function (key) {
      (Array.isArray(configuration[key]) ? configuration[key] : []).forEach(markEvidenceLaneDescriptive);
    });
    const facility = result.facility || {};
    markEvidenceLaneDescriptive(facility);
    markEvidenceLaneDescriptive(facility.primary);
    markEvidenceLaneDescriptive(facility.inactiveNegativeControl);
    (Array.isArray(facility.sensitivity) ? facility.sensitivity : []).forEach(markEvidenceLaneDescriptive);
    const contextAssociations = result.contextAssociations || {};
    (Array.isArray(contextAssociations.lanes) ? contextAssociations.lanes : []).forEach(markEvidenceLaneDescriptive);
    result.baselineMode = "full_catalog";
    result.inferenceEnabled = false;
    appendUniqueReason(result, "full_catalog_overlap_descriptive_no_inference");
    const warnings = Array.isArray(result.policyWarnings) ? result.policyWarnings.slice() : [];
    const warning = "Full Catalog overlaps the active cohort and is descriptive only; spatial p-values, q-values, and Pattern Finder eligibility are disabled.";
    if (warnings.indexOf(warning) === -1) warnings.push(warning);
    result.policyWarnings = warnings;
    return result;
  }

  function computeSpatialAnalysis(optionsValue) {
    const options = optionsValue || {};
    const analysisMode = text(options.analysisMode, "comparative");
    const comparisonState = text(options.comparisonState, "inferential");
    const wholeCorpusStructure = analysisMode === "whole_corpus_structure" || comparisonState === "whole_corpus_structure";
    const rows = Array.isArray(options.rows) ? options.rows : [];
    const codebooks = options.codebooks || {};
    const analysisRows = pinnedRowsForActiveCohort(
      rows,
      options.spatialPoints,
      options.spatialPointCodes || codebooks.ufoSpatialPoints
    );
    const configurationRows = pinnedConfigurationRowsForActiveCohort(
      rows,
      options.spatialPoints,
      options.configurationPoints,
      codebooks
    );
    const windows = Array.isArray(options.windows) && options.windows.length ? options.windows : DEFAULT_WINDOWS;
    function computeLane(sourceLane, laneRowsValue, laneEdgesValue, seedSuffix) {
      return windows.map(function (windowConfig) {
        return computeCraftCooccurrence({
          rows: laneRowsValue,
          edges: laneEdgesValue,
          window: windowConfig,
          sourceLane,
          permutationCount: options.permutationCount,
          bootstrapCount: options.bootstrapCount,
          minimumStratumSize: options.minimumStratumSize,
          seed: text(options.seed) + "|" + text(seedSuffix, "craft") + "|" + sourceLane + "|" + windowConfig.id,
          artifactHashes: options.artifactHashes,
        });
      });
    }
    const result = {
      estimatorVersion: ESTIMATOR_VERSION,
      analysisMode,
      comparisonState,
      baselineMode: text(options.baselineMode, "other_dates_balanced"),
      inferenceEnabled: options.inferenceEnabled !== false,
      eligibility: options.eligibilityFunnel && typeof options.eligibilityFunnel === "object"
        ? Object.assign({}, options.eligibilityFunnel)
        : buildEligibilityFunnel(analysisRows),
      cooccurrence: {
        crossSource: computeLane("cross", analysisRows, options.edges, "craft_shape"),
        sameSource: computeLane("same", analysisRows, options.edges, "craft_shape"),
        configuration: {
          status: configurationRows.length ? "available" : "data_unavailable",
          unitOfAnalysis: "eligible Formation/configuration report exposed to a neighboring recognized craft shape or Formation report",
          crossSource: configurationRows.length
            ? computeLane("cross", configurationRows, options.configurationEdges, "formation_configuration")
            : [],
          sameSource: configurationRows.length
            ? computeLane("same", configurationRows, options.configurationEdges, "formation_configuration")
            : [],
          policyWarnings: [
            "Formation is a multi-object configuration lane and is never relabeled from dumbbell/barbell craft shape.",
            "This point-neighborhood estimator does not read chronology connectors or infer observed travel.",
          ],
        },
      },
      facility: computeFacilityContext({
        rows: analysisRows,
        facilities: options.facilities,
        facilityCodes: options.facilityCodes || (options.codebooks && options.codebooks.facilityAnalysis),
        nearRadiusKm: 25,
        comparisonMinimumKm: 100,
        comparisonMaximumKm: 250,
        permutationCount: firstDefined(options.facilityPermutationCount, options.permutationCount),
        bootstrapCount: firstDefined(options.facilityBootstrapCount, options.bootstrapCount),
        seed: text(options.seed) + "|facility",
        artifactHashes: options.artifactHashes,
      }),
      contextAssociations: computeContextAssociations({
        activeRows: rows,
        neighbors: options.contextNeighbors,
        codebook: options.contextNeighborCodes || codebooks.contextUfoNeighbors,
        permutationCount: firstDefined(options.contextPermutationCount, options.permutationCount),
        bootstrapCount: firstDefined(options.contextBootstrapCount, options.bootstrapCount),
        inferenceEnabled: options.inferenceEnabled,
        seed: text(options.seed) + "|context",
      }),
      relationshipSummary: computeRelationshipSummary(
        options.relationships,
        options.relationshipCodes || codebooks.relationshipReconciliation,
        rows
      ),
      readiness: contextReadiness(options.readiness),
      traceInvariant: true,
      traceInputsRead: false,
      contracts: {
        packedNeighborSchema: PACKED_EDGE_SCHEMA.slice(),
        packedNeighborDistanceUnit: "decameters",
        packedFacilitySchema: PACKED_FACILITY_SCHEMA.slice(),
        packedUfoSpatialPointSchema: PACKED_UFO_SPATIAL_POINT_SCHEMA.slice(),
        packedUfoConfigurationPointSchema: PACKED_UFO_CONFIGURATION_POINT_SCHEMA.slice(),
        packedUfoConfigurationNeighborSchema: PACKED_EDGE_SCHEMA.slice(),
        packedContextNeighborSchema: PACKED_CONTEXT_NEIGHBOR_SCHEMA.slice(),
        packedRelationshipSchema: PACKED_RELATIONSHIP_SCHEMA.slice(),
        chronologyInputs: "prohibited",
      },
      pinnedSpatialPointN: Array.isArray(options.spatialPoints) ? options.spatialPoints.length : 0,
      activePinnedSpatialPointN: analysisRows.length,
      artifactHashes: Object.assign({}, options.artifactHashes || {}),
    };
    return options.inferenceEnabled === false || (result.baselineMode === "full_catalog" && !wholeCorpusStructure)
      ? enforceDescriptiveOnlyBaseline(result)
      : result;
  }

  return Object.freeze({
    ESTIMATOR_VERSION,
    DEFAULT_WINDOWS,
    benjaminiHochberg,
    greatCircleDistanceMeters,
    classifyUncertainDistance,
    spatialEligibilityReason,
    buildEligibilityFunnel,
    normalizeEdge,
    normalizeSpatialPoint,
    pinnedRowsForActiveCohort,
    normalizeContextNeighbor,
    computeContextAssociations,
    computeRelationshipSummary,
    normalizeFacility,
    facilityActiveAt,
    facilityIsInferential,
    buildFacilityIndex,
    computeCraftCooccurrence,
    computeFacilityContext,
    contextReadiness,
    enforceDescriptiveOnlyBaseline,
    computeSpatialAnalysis,
  });
});

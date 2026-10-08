(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.UfoAnalysisCrossContext = api;
})(typeof self !== "undefined" ? self : globalThis, function () {
  "use strict";

  const VERSION = "cross-context-descriptive-v1";
  const DAY_MS = 86400000;
  const WINDOWS = Object.freeze([
    Object.freeze({ id: "near_50km_7d", radiusKm: 50, dayWindow: 7 }),
    Object.freeze({ id: "near_100km_30d", radiusKm: 100, dayWindow: 30 }),
    Object.freeze({ id: "near_250km_30d", radiusKm: 250, dayWindow: 30 }),
  ]);
  const STRICT_ROLES = {
    crop: new Set(["formation", "formation_date", "occurrence", "occurrence_date"]),
    animal: new Set(["occurrence", "occurrence_date", "death", "death_date", "death_interval", "incident_date"]),
  };

  function number(value) {
    return value === null || value === undefined || value === "" || typeof value === "boolean"
      ? null : (Number.isFinite(Number(value)) ? Number(value) : null);
  }
  function text(value) { return String(value == null ? "" : value).trim(); }
  function list(value) { return (Array.isArray(value) ? value : (value == null ? [] : [value])).map(text).filter(Boolean); }
  function rounded(value) { return Number.isFinite(value) ? Math.round(value * 10000) / 10000 : null; }
  function rows(value) { return Array.isArray(value) ? value : (value && (value.rows || value.records) || []); }

  function normalize(row, domain, epoch) {
    const source = row || {};
    const shift = epoch === "python_day" ? 719163 : 0;
    const start = number(source.startOrdinal);
    const end = number(source.endOrdinal);
    const uncertainty = number(source.uncertaintyKm == null ? source.coordinateUncertaintyKm : source.uncertaintyKm);
    return {
      id: text(source.id), title: text(source.title) || text(source.id), domain,
      ordinal: start === null ? null : start - shift,
      endOrdinal: end === null ? (start === null ? null : start - shift) : end - shift,
      datePrecision: text(source.datePrecision || source.datePrecisionCode),
      dateRole: text(source.dateRole || source.dateRoleCode) || (domain === "crop" ? "catalog_unspecified" : "reported_unspecified"),
      lat: number(source.lat), lon: number(source.lon), uncertaintyKm: uncertainty === null || uncertainty < 0 ? null : uncertainty,
      coordinateEvidenceClass: text(source.coordinateEvidenceClass || source.coordinateEvidenceClassCode),
      category: text(source.category || source.featureGroup || source.featureGroupCode) || "unknown",
      country: text(source.country),
      clusterId: text(source.clusterId || source.locationDateClusterId),
      sourceFamilyIds: list(source.sourceFamilyIds),
      originUfoEventIds: list(source.originUfoEventIds), originInputIds: list(source.originInputIds),
      originPublisherCodes: list(source.originPublisherCodes).map(function (v) { return v.toLowerCase(); }),
      publisherCodes: list(source.publisherCodes).map(function (v) { return v.toLowerCase(); }),
      lineageHash: text(source.lineageHash), sourceIncidentId: text(source.sourceIncidentId),
      sourceIncidentSha256: text(source.sourceIncidentSha256),
      strictFlag: source.strictEligible === true || source.kilometerEligible === true,
      dedupStatus: text(source.dedupStatus || source.dedupStatusCode),
      exclusionReasons: list(source.exclusionReasons || source.exclusionReasonCodes),
      restricted: source.legalPublicationRestriction === true,
    };
  }
  function exact(row) {
    return row.ordinal !== null && row.ordinal === row.endOrdinal && (row.datePrecision === "exact_day" || row.datePrecision === "day");
  }
  function mapped(row) {
    return row.lat !== null && row.lon !== null && Math.abs(row.lat) <= 90 && Math.abs(row.lon) <= 180;
  }
  function usable(row) {
    return !row.restricted && row.dedupStatus !== "duplicate" && !row.exclusionReasons.some(function (reason) {
      return reason === "duplicate_record_excluded_from_analysis" || reason === "legal_publication_restriction" || reason === "unresolved_identity_date_or_coordinate_conflict";
    });
  }
  function strict(row) {
    return row.strictFlag && exact(row) && mapped(row) && usable(row) && STRICT_ROLES[row.domain].has(row.dateRole)
      && (row.coordinateEvidenceClass === "source_exact" || row.coordinateEvidenceClass === "source_bounded")
      && row.uncertaintyKm !== null && row.uncertaintyKm <= 1 && row.exclusionReasons.length === 0;
  }
  function inScope(row, filters) {
    if (number(filters.startOrdinal) !== null && (row.endOrdinal === null || row.endOrdinal < Number(filters.startOrdinal))) return false;
    if (number(filters.endOrdinal) !== null && (row.ordinal === null || row.ordinal > Number(filters.endOrdinal))) return false;
    if (Array.isArray(filters.countries) && filters.countries.length && filters.countries.indexOf(row.country) < 0) return false;
    return true;
  }
  function cluster(values, spatial) {
    const grouped = new Map();
    values.forEach(function (row) {
      // A source cluster is preferred. Fallback co-located markers on the same day count once.
      const key = row.clusterId || (mapped(row)
        ? [row.domain, row.lat.toFixed(6), row.lon.toFixed(6), row.ordinal].join("|")
        : [row.domain, "unmapped", row.id].join("|"));
      if (!grouped.has(key)) grouped.set(key, Object.assign({}, row, { clusterId: key, members: [] }));
      grouped.get(key).members.push(row);
    });
    return Array.from(grouped.values()).sort(function (a, b) { return a.ordinal - b.ordinal || a.clusterId.localeCompare(b.clusterId); });
  }
  function intersect(left, right) { return left.some(function (value) { return right.indexOf(value) >= 0; }); }
  function memberCollision(a, b) {
    if (a.lineageHash && a.lineageHash === b.lineageHash) return "shared_lineage";
    if (a.sourceIncidentId && a.sourceIncidentId === b.sourceIncidentId) return "shared_incident_id";
    if (a.sourceIncidentSha256 && a.sourceIncidentSha256 === b.sourceIncidentSha256) return "shared_incident_hash";
    if (intersect(a.sourceFamilyIds, b.sourceFamilyIds)) return "shared_source_family";
    if (intersect(a.originUfoEventIds, b.originUfoEventIds) || intersect(a.originInputIds, b.originInputIds)) return "shared_originating_ufo";
    if (intersect(a.originPublisherCodes, b.publisherCodes) || intersect(b.originPublisherCodes, a.publisherCodes)
      || intersect(a.originPublisherCodes, b.originPublisherCodes)) return "shared_originating_publisher";
    return null;
  }
  function collision(a, b) {
    for (const left of a.members) for (const right of b.members) {
      const reason = memberCollision(left, right);
      if (reason) return reason;
    }
    return null;
  }
  function distanceKm(a, b) {
    const radians = Math.PI / 180;
    const lat = (b.lat - a.lat) * radians;
    const lon = (b.lon - a.lon) * radians;
    const h = Math.sin(lat / 2) ** 2 + Math.cos(a.lat * radians) * Math.cos(b.lat * radians) * Math.sin(lon / 2) ** 2;
    return 12742.0176 * Math.asin(Math.min(1, Math.sqrt(Math.max(0, h))));
  }
  function shiftYear(ordinal, offset) {
    const value = new Date(ordinal * DAY_MS);
    const year = value.getUTCFullYear() + offset;
    const month = value.getUTCMonth();
    const lastDay = new Date(Date.UTC(year, month + 1, 0)).getUTCDate();
    const date = new Date(0);
    date.setUTCFullYear(year, month, Math.min(value.getUTCDate(), lastDay));
    date.setUTCHours(0, 0, 0, 0);
    return Math.floor(date.getTime() / DAY_MS);
  }
  function dayIndex(values) {
    const index = new Map();
    values.forEach(function (row) {
      if (!index.has(row.ordinal)) index.set(row.ordinal, []);
      index.get(row.ordinal).push(row);
    });
    return index;
  }
  function computeLane(id, cropValues, animalValues, allAnimalValues, windows, isStrict, filters) {
    const index = dayIndex(allAnimalValues);
    const activeAnimals = new Set(animalValues.map(function (row) { return row.clusterId; }));
    const firstDay = allAnimalValues.length ? Math.min.apply(null, allAnimalValues.map(function (row) { return row.ordinal; })) : null;
    const lastDay = allAnimalValues.length ? Math.max.apply(null, allAnimalValues.map(function (row) { return row.ordinal; })) : null;
    const maxDays = Math.max.apply(null, windows.map(function (window) { return window.dayWindow; }));
    const isSpatial = id !== "calendar_alignment";
    const results = windows.map(function (window) {
      return Object.assign({}, window, {
        observedPairN: 0, observedCropClusterN: 0, observedAnimalClusterN: 0,
        matchedCropAnchorN: 0, matchedObservedPairN: 0, controlWindowN: 0, controlPairN: 0,
        definitelyNearPairN: 0, uncertaintyBoundaryPairN: 0, unknownUncertaintyPairN: 0,
        excludedLineagePairN: 0, lineageUnverifiedPairN: 0,
        samplePairs: [],
        observedCropIds: new Set(), observedAnimalIds: new Set(), exclusions: {},
      });
    });
    cropValues.forEach(function (crop) {
      const controls = [-2, -1, 1, 2].map(function (offset) { return shiftYear(crop.ordinal, offset); });
      const matched = windows.map(function (window) {
        const completeObservedWindow = (number(filters.startOrdinal) === null || crop.ordinal - window.dayWindow >= Number(filters.startOrdinal))
          && (number(filters.endOrdinal) === null || crop.ordinal + window.dayWindow <= Number(filters.endOrdinal));
        return completeObservedWindow && controls.every(function (day) { return firstDay !== null && day - window.dayWindow >= firstDay && day + window.dayWindow <= lastDay; });
      });
      results.forEach(function (result, i) {
        if (matched[i]) { result.matchedCropAnchorN += 1; result.controlWindowN += 4; }
      });
      [crop.ordinal].concat(controls).forEach(function (anchor, role) {
        for (let day = anchor - maxDays; day <= anchor + maxDays; day += 1) {
          const candidates = index.get(day);
          if (!candidates) continue;
          candidates.forEach(function (animal) {
            if (role === 0 && !activeAnimals.has(animal.clusterId)) return;
            const lag = Math.abs(day - anchor);
            const distance = isSpatial ? distanceKm(crop, animal) : 0;
            const reason = collision(crop, animal);
            results.forEach(function (result, i) {
              if (lag > result.dayWindow || (isSpatial && distance > result.radiusKm) || (role > 0 && !matched[i])) return;
              if (reason) {
                if (role === 0) { result.excludedLineagePairN += 1; result.exclusions[reason] = (result.exclusions[reason] || 0) + 1; }
                return;
              }
              if (role > 0) { result.controlPairN += 1; return; }
              result.observedPairN += 1;
              result.observedCropIds.add(crop.clusterId); result.observedAnimalIds.add(animal.clusterId);
              if (matched[i]) result.matchedObservedPairN += 1;
              // Distinct collection/family IDs alone do not verify cross-domain independence.
              result.lineageUnverifiedPairN += 1;
              if (result.samplePairs.length < 25) result.samplePairs.push({
                cropId: crop.id, animalId: animal.id, animalTitle: animal.title,
                cropOrdinal: crop.ordinal, animalOrdinal: animal.ordinal,
                cropDateRole: crop.dateRole, animalDateRole: animal.dateRole,
                distanceKm: isSpatial ? rounded(distance) : null,
                animalMinusCropDays: animal.ordinal - crop.ordinal,
                cropCategory: crop.category, animalCategory: animal.category,
                uncertaintyKnown: crop.uncertaintyKm !== null && animal.uncertaintyKm !== null,
              });
              if (!isSpatial) return;
              const uncertainty = crop.uncertaintyKm === null || animal.uncertaintyKm === null ? null : crop.uncertaintyKm + animal.uncertaintyKm;
              if (uncertainty === null) result.unknownUncertaintyPairN += 1;
              else if (distance + uncertainty > result.radiusKm) result.uncertaintyBoundaryPairN += 1;
              else if (isStrict) result.definitelyNearPairN += 1;
            });
          });
        }
      });
    });
    return {
      id, evidenceClass: isStrict ? "strict_source_supported_site" : (isSpatial ? "public_marker_descriptive" : "calendar_date_descriptive"),
      status: cropValues.length && animalValues.length ? "descriptive_available" : "insufficient_eligible_records",
      unitOfAnalysis: "unique crop location-date cluster / animal location-date cluster pair",
      cropClusterN: cropValues.length, animalClusterN: animalValues.length,
      cropDateRoles: countRoles(cropValues), animalDateRoles: countRoles(animalValues),
      inferenceEligible: false, patternFinderEligible: false,
      rows: results.map(function (result) {
        result.observedCropClusterN = result.observedCropIds.size;
        result.observedAnimalClusterN = result.observedAnimalIds.size;
        result.observedCropShare = cropValues.length ? rounded(result.observedCropClusterN / cropValues.length) : null;
        result.observedAnimalShare = animalValues.length ? rounded(result.observedAnimalClusterN / animalValues.length) : null;
        result.expectedMatchedPairN = result.matchedCropAnchorN ? rounded(result.controlPairN / 4) : null;
        result.descriptiveObservedControlRatio = result.expectedMatchedPairN > 0 ? rounded(result.matchedObservedPairN / result.expectedMatchedPairN) : null;
        result.controlStatus = !result.matchedCropAnchorN ? "no_complete_same_season_controls" : (result.expectedMatchedPairN === 0 ? "zero_control_pairs_ratio_unavailable" : "descriptive_comparison");
        result.supportReasons = ["descriptive_only"].concat(
          result.observedPairN < 25 ? ["observed_pairs_below_25"] : [],
          result.expectedMatchedPairN === null || result.expectedMatchedPairN < 10 ? ["matched_control_average_below_10_or_unavailable"] : [],
          result.unknownUncertaintyPairN ? ["unknown_event_site_uncertainty"] : []);
        result.pValue = null; result.qValue = null; result.inferenceEligible = false;
        result.lineageExclusions = result.exclusions;
        delete result.exclusions; delete result.observedCropIds; delete result.observedAnimalIds;
        return result;
      }),
    };
  }
  function countRoles(values) {
    const counts = {};
    values.forEach(function (row) { counts[row.dateRole] = (counts[row.dateRole] || 0) + 1; });
    return counts;
  }
  function coverage(values, scoped, dated, spatial, strictValues) {
    return {
      totalN: values.length, scopedN: scoped.length, exactDayN: dated.length,
      publicMarkerN: spatial.length, strictEligibleN: strictValues.length,
      nonExactOrUndatedN: scoped.filter(function (row) { return !exact(row); }).length,
      missingCoordinatesExactDayN: scoped.filter(function (row) { return exact(row) && !mapped(row); }).length,
      identityOrPublicationExcludedN: scoped.filter(function (row) { return !usable(row); }).length,
      dateRoles: countRoles(scoped),
    };
  }
  function computeCrossContext(inputValue) {
    const input = inputValue || {};
    const epoch = input.ordinalEpoch || "unix_day";
    if (epoch !== "unix_day" && epoch !== "python_day") throw new Error("Unsupported cross-context ordinal epoch");
    const crops = rows(input.crops || input.cropCircles).map(function (row) { return normalize(row, "crop", epoch); });
    const animals = rows(input.animals || input.animalReports).map(function (row) { return normalize(row, "animal", epoch); });
    const filters = input.filters || {};
    const scopedCrops = crops.filter(function (row) { return inScope(row, filters); });
    const scopedAnimals = animals.filter(function (row) { return inScope(row, filters); });
    const valid = function (row) { return exact(row) && usable(row); };
    const datedCrops = scopedCrops.filter(valid), datedAnimals = scopedAnimals.filter(valid);
    const publicCrops = datedCrops.filter(mapped), publicAnimals = datedAnimals.filter(mapped);
    const strictCrops = publicCrops.filter(strict), strictAnimals = publicAnimals.filter(strict);
    const animalControlPool = animals.filter(function (row) { return valid(row) && (!filters.countries || !filters.countries.length || filters.countries.indexOf(row.country) >= 0); });
    const windows = (Array.isArray(input.windows) && input.windows.length ? input.windows : WINDOWS).map(function (window, index) {
      return { id: text(window.id) || "window_" + index, radiusKm: Math.max(1, Math.min(1000, number(window.radiusKm) || 100)), dayWindow: Math.max(0, Math.min(90, Math.trunc(number(window.dayWindow) || 0))) };
    });
    const publicLane = computeLane("public_marker", cluster(publicCrops, true), cluster(publicAnimals, true), cluster(animalControlPool.filter(mapped), true), windows, false, filters);
    const strictLane = computeLane("strict_site", cluster(strictCrops, true), cluster(strictAnimals, true), cluster(animalControlPool.filter(strict), true), windows, true, filters);
    const calendarWindows = [0, 7, 30].map(function (days) { return { id: "calendar_" + days + "d", radiusKm: null, dayWindow: days }; });
    const calendarLane = computeLane("calendar_alignment", cluster(datedCrops, false), cluster(datedAnimals, false), cluster(animalControlPool, false), calendarWindows, false, filters);
    return {
      version: VERSION, ordinalEpoch: "unix_day", status: publicLane.status,
      scope: { startOrdinal: number(filters.startOrdinal), endOrdinal: number(filters.endOrdinal), countries: filters.countries || [], reportFiltersApply: false },
      coverage: { crops: coverage(crops, scopedCrops, datedCrops, publicCrops, strictCrops), animals: coverage(animals, scopedAnimals, datedAnimals, publicAnimals, strictAnimals) },
      qualityGates: {
        strictCropClusterN: strictLane.cropClusterN, strictAnimalClusterN: strictLane.animalClusterN,
        minimumStrictClustersPerDomain: 25, inferenceEligible: false,
        reasons: ["direct_cross_domain_source_independence_not_verified", "descriptive_controls_are_not_surveillance_exposure"].concat(
          strictLane.cropClusterN < 25 ? ["strict_crop_clusters_below_25"] : [], strictLane.animalClusterN < 25 ? ["strict_animal_clusters_below_25"] : []),
      },
      matchedControl: "Same crop marker and month/day at -2, -1, +1 and +2 years; only anchors with complete observed windows and all four controls inside the dated animal catalog extent are compared.",
      lanes: [publicLane, strictLane, calendarLane],
      policyWarnings: [
        "Crop catalog/discovery/photography dates and animal report/publication dates are retained as date roles; they are not substituted for formation or death time.",
        "Public-marker distance is a comparison between display markers, not definite event-site proximity; unknown and boundary-crossing uncertainty are reported separately.",
        "Calendar alignment pools recorded dates worldwide and does not establish local co-occurrence.",
        "Pairs sharing known source, incident, originating UFO or publisher lineage are excluded; absence of a known collision does not prove independence.",
        "Co-located same-day markers count once. Historical collection extent does not establish continuous reporting coverage or incidence; controls and ratios are descriptive only.",
        "Chronology trace connectors are not estimator inputs. No causal claim, p-value, or Pattern Finder admission is made.",
      ],
    };
  }
  return { VERSION, WINDOWS, computeCrossContext, distanceKm, shiftYear };
});

(function () {
  "use strict";

  const MISSING_SORT_ORDINAL = -2147483648;
  const MISSING_ANALYSIS_INDEX = 255;
  const PYTHON_ORDINAL_UNIX_EPOCH = 719163;
  const ANALYSIS_CACHE_LIMIT = 12;
  const SOURCE_COORDINATE_VALUES = new Set([
    "raw_latlong", "location_coordinates", "source_coordinates", "source-provided", "source_provided",
  ]);

  let chunks = [];
  let rowCount = 0;
  let typedStorageBytes = 0;
  let dictionaries = createDictionaries();
  let eventIdStrings = createDictionary();
  let analysisGridKeys = createDictionary();
  let analysisCoordinatePileKeys = createDictionary();
  let analysisCoordinatePileCounts = new Map();
  let analysisStatsApi = self.UfoAnalysisStats || null;
  let analysisSpatialApi = self.UfoAnalysisSpatial || null;
  let analysisCache = new Map();
  let analysisMatchCache = new Map();
  let analysisContext = {
    manifest: {},
    cropCircles: null,
    animalReports: null,
  };
  let analysisSpatialArtifacts = {
    manifest: null,
    neighbors: null,
    facilities: null,
    relationships: null,
    loaded: false,
    artifactHashes: {},
  };
  let analysisSpatialExecutor = null;
  let analysisSpatialExecutorEpoch = 0;
  let analysisSpatialPending = null;
  let analysisSpatialCancellationGeneration = 0;

  const SPATIAL_SOURCE_COORDINATE_CLASSES = new Set([
    "source_coordinates", "source-provided", "source_provided",
  ]);
  const SPATIAL_QUALIFIED_CONFIDENCE = new Set(["medium", "high"]);
  const SPATIAL_QUALIFIED_SAME_DAY = new Set(["medium", "strong"]);
  const SPATIAL_EXCLUDED_CRAFTS = new Set([
    "", "unknown", "other", "non_ufo", "non-ufo", "conventional", "aircraft", "fireball", "meteor",
  ]);

  function createDictionary() {
    return {
      values: [""],
      codes: new Map([["", 0]]),
    };
  }

  function createDictionaries() {
    return {
      source: createDictionary(),
      type: createDictionary(),
      visualTypeGroup: createDictionary(),
      craftType: createDictionary(),
      shape: createDictionary(),
      craftConfidence: createDictionary(),
      craftSource: createDictionary(),
      sameDayMatchStrength: createDictionary(),
      precision: createDictionary(),
      datePrecision: createDictionary(),
      coordinateSource: createDictionary(),
      country: createDictionary(),
      adminRegion: createDictionary(),
      duplicateLineage: createDictionary(),
    };
  }

  function ensureAnalysisStats() {
    if (analysisStatsApi && typeof analysisStatsApi.computeAnalysis === "function") return analysisStatsApi;
    if (typeof importScripts === "function") {
      importScripts("./analysis_stats.js");
      analysisStatsApi = self.UfoAnalysisStats || null;
    }
    if (!analysisStatsApi || typeof analysisStatsApi.computeAnalysis !== "function") {
      throw new Error("Analysis statistics module is unavailable.");
    }
    return analysisStatsApi;
  }

  function ensureAnalysisSpatial() {
    if (analysisSpatialApi && typeof analysisSpatialApi.computeSpatialAnalysis === "function") return analysisSpatialApi;
    if (typeof importScripts === "function") {
      importScripts("./analysis_spatial.js");
      analysisSpatialApi = self.UfoAnalysisSpatial || null;
    }
    if (!analysisSpatialApi || typeof analysisSpatialApi.computeSpatialAnalysis !== "function") {
      throw new Error("Analysis spatial statistics module is unavailable.");
    }
    return analysisSpatialApi;
  }

  function dictionaryCode(dictionary, value) {
    const key = String(value || "");
    if (dictionary.codes.has(key)) {
      return dictionary.codes.get(key);
    }
    const code = dictionary.values.length;
    dictionary.values.push(key);
    dictionary.codes.set(key, code);
    return code;
  }

  function categoryCode(dictionary, value) {
    const code = dictionaryCode(dictionary, value);
    if (code > 65535) {
      throw new Error("Catalog facet dictionary exceeded the Uint16 category limit.");
    }
    return code;
  }

  function dictionaryValue(dictionary, code) {
    return dictionary.values[Number(code)] || "";
  }

  // Hinnant civil-calendar conversion using the catalog's Unix-day epoch. These
  // columns are derived once as the existing worker ingests rows, avoiding date
  // object allocation and repeated calendar math on every Analysis recompute.
  function analysisCivilFromTimelineOrdinal(value) {
    if (!Number.isFinite(value) || value === MISSING_SORT_ORDINAL) return null;
    let z = Math.trunc(value) + 719468;
    const era = Math.floor(z / 146097);
    const dayOfEra = z - (era * 146097);
    const yearOfEra = Math.floor(
      (dayOfEra - Math.floor(dayOfEra / 1460) + Math.floor(dayOfEra / 36524) - Math.floor(dayOfEra / 146096)) / 365
    );
    let year = yearOfEra + (era * 400);
    const dayOfYear = dayOfEra - ((365 * yearOfEra) + Math.floor(yearOfEra / 4) - Math.floor(yearOfEra / 100));
    const monthPart = Math.floor(((5 * dayOfYear) + 2) / 153);
    const month = monthPart + (monthPart < 10 ? 3 : -9);
    year += month <= 2 ? 1 : 0;
    return year >= 1 ? { year, month } : null;
  }

  function analysisGridIndexes(latitude, longitude) {
    if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) return null;
    const normalizedLongitude = longitude === 180 ? -180 : longitude;
    const sinLatitude = Math.sin(latitude * Math.PI / 180);
    return {
      latIndex: Math.max(0, Math.min(11, Math.floor(((sinLatitude + 1) / 2) * 12))),
      lonIndex: Math.max(0, Math.min(23, Math.floor(((normalizedLongitude + 180) / 360) * 24))),
    };
  }

  function analysisCoordinateClassForRow(row, mapped) {
    if (!mapped) return "unmapped";
    const coordinateSource = String(row && row.coordinateSource || "unknown").trim().toLowerCase();
    const precision = String(row && row.precision || "unknown").trim().toLowerCase();
    if (precision === "exact_coords" && SOURCE_COORDINATE_VALUES.has(coordinateSource) && coordinateSource !== "geocoded") {
      return "source_coordinates";
    }
    return "generalized_coordinates";
  }

  function analysisCoordinatePileKey(latitude, longitude, coordinateClass) {
    if (coordinateClass !== "source_coordinates" || !Number.isFinite(latitude) || !Number.isFinite(longitude)) return "";
    return latitude.toFixed(6) + "," + longitude.toFixed(6);
  }

  function compactRows(nextRows) {
    const length = nextRows.length;
    const chunk = {
      length,
      eventIds: new Float64Array(length),
      eventIdStringCodes: new Uint32Array(length),
      sourceCodes: new Uint16Array(length),
      typeCodes: new Uint16Array(length),
      visualTypeGroupCodes: new Uint16Array(length),
      craftTypeCodes: new Uint16Array(length),
      shapeCodes: new Uint16Array(length),
      craftConfidenceCodes: new Uint16Array(length),
      craftSourceCodes: new Uint16Array(length),
      sameDayMatchStrengthCodes: new Uint16Array(length),
      precisionCodes: new Uint16Array(length),
      datePrecisionCodes: new Uint16Array(length),
      coordinateSourceCodes: new Uint16Array(length),
      countryCodes: new Uint16Array(length),
      adminRegionCodes: new Uint16Array(length),
      duplicateLineageCodes: new Uint16Array(length),
      sortOrdinals: new Int32Array(length),
      latitudes: new Float64Array(length),
      longitudes: new Float64Array(length),
      mappedStates: new Uint8Array(length),
      analysisYears: new Int32Array(length),
      analysisMonths: new Uint8Array(length),
      analysisGridLatIndexes: new Uint8Array(length),
      analysisGridLonIndexes: new Uint8Array(length),
      analysisCoordinateClasses: new Uint8Array(length),
      analysisGridKeyCodes: new Uint16Array(length),
      analysisCoordinatePileKeyCodes: new Uint32Array(length),
    };

    for (let index = 0; index < length; index += 1) {
      const row = nextRows[index] || {};
      const rawEventId = row.eventId;
      if (typeof rawEventId === "number" && Number.isSafeInteger(rawEventId)) {
        chunk.eventIds[index] = rawEventId;
      } else {
        const stringCode = dictionaryCode(eventIdStrings, rawEventId == null ? "" : String(rawEventId));
        chunk.eventIdStringCodes[index] = stringCode + 1;
      }
      chunk.sourceCodes[index] = categoryCode(dictionaries.source, row.source);
      chunk.typeCodes[index] = categoryCode(dictionaries.type, row.type);
      chunk.visualTypeGroupCodes[index] = categoryCode(dictionaries.visualTypeGroup, row.visualTypeGroup);
      chunk.craftTypeCodes[index] = categoryCode(dictionaries.craftType, row.craftType);
      chunk.shapeCodes[index] = categoryCode(dictionaries.shape, row.shape);
      chunk.craftConfidenceCodes[index] = categoryCode(dictionaries.craftConfidence, row.craftConfidence);
      chunk.craftSourceCodes[index] = categoryCode(dictionaries.craftSource, row.craftSource);
      chunk.sameDayMatchStrengthCodes[index] = categoryCode(dictionaries.sameDayMatchStrength, row.sameDayMatchStrength);
      chunk.precisionCodes[index] = categoryCode(dictionaries.precision, row.precision);
      chunk.datePrecisionCodes[index] = categoryCode(dictionaries.datePrecision, row.datePrecision);
      chunk.coordinateSourceCodes[index] = categoryCode(dictionaries.coordinateSource, row.coordinateSource);
      chunk.countryCodes[index] = categoryCode(dictionaries.country, row.country || "unknown");
      chunk.adminRegionCodes[index] = categoryCode(dictionaries.adminRegion, row.adminRegion || "unknown");
      chunk.duplicateLineageCodes[index] = categoryCode(dictionaries.duplicateLineage, row.duplicateLineage || "");
      const sortOrdinal = Number(row.sortOrdinal);
      chunk.sortOrdinals[index] = Number.isFinite(sortOrdinal)
        ? Math.max(-2147483647, Math.min(2147483647, Math.round(sortOrdinal)))
        : MISSING_SORT_ORDINAL;
      const analysisCivil = analysisCivilFromTimelineOrdinal(chunk.sortOrdinals[index]);
      chunk.analysisYears[index] = analysisCivil ? analysisCivil.year : MISSING_SORT_ORDINAL;
      chunk.analysisMonths[index] = analysisCivil ? analysisCivil.month : 0;
      const latitude = row.lat == null || (typeof row.lat === "string" && !row.lat.trim()) ? NaN : Number(row.lat);
      const longitude = row.lon == null || (typeof row.lon === "string" && !row.lon.trim()) ? NaN : Number(row.lon);
      const coordinatesValid = Number.isFinite(latitude) && latitude >= -90 && latitude <= 90 &&
        Number.isFinite(longitude) && longitude >= -180 && longitude <= 180;
      chunk.latitudes[index] = coordinatesValid ? latitude : NaN;
      chunk.longitudes[index] = coordinatesValid ? longitude : NaN;
      const mappedValue = typeof row.mapped === "boolean"
        ? row.mapped
        : (typeof row.mappedState === "boolean" ? row.mappedState : coordinatesValid);
      chunk.mappedStates[index] = mappedValue ? 2 : 1;
      const analysisGrid = mappedValue && coordinatesValid ? analysisGridIndexes(latitude, longitude) : null;
      chunk.analysisGridLatIndexes[index] = analysisGrid ? analysisGrid.latIndex : MISSING_ANALYSIS_INDEX;
      chunk.analysisGridLonIndexes[index] = analysisGrid ? analysisGrid.lonIndex : MISSING_ANALYSIS_INDEX;
      const analysisCoordinateClass = analysisCoordinateClassForRow(row, mappedValue && coordinatesValid);
      chunk.analysisCoordinateClasses[index] = analysisCoordinateClass === "source_coordinates"
        ? 1
        : (analysisCoordinateClass === "generalized_coordinates" ? 2 : 0);
      if (analysisGrid) {
        chunk.analysisGridKeyCodes[index] = categoryCode(
          analysisGridKeys,
          analysisCoordinateClass + "|ea12x24:" + analysisGrid.latIndex + ":" + analysisGrid.lonIndex
        );
      }
      const pileKey = analysisCoordinatePileKey(latitude, longitude, analysisCoordinateClass);
      if (pileKey) {
        const pileCode = dictionaryCode(analysisCoordinatePileKeys, pileKey);
        chunk.analysisCoordinatePileKeyCodes[index] = pileCode;
        analysisCoordinatePileCounts.set(pileCode, (analysisCoordinatePileCounts.get(pileCode) || 0) + 1);
      }
    }

    typedStorageBytes +=
      chunk.eventIds.byteLength +
      chunk.eventIdStringCodes.byteLength +
      chunk.sourceCodes.byteLength +
      chunk.typeCodes.byteLength +
      chunk.visualTypeGroupCodes.byteLength +
      chunk.craftTypeCodes.byteLength +
      chunk.shapeCodes.byteLength +
      chunk.craftConfidenceCodes.byteLength +
      chunk.craftSourceCodes.byteLength +
      chunk.sameDayMatchStrengthCodes.byteLength +
      chunk.precisionCodes.byteLength +
      chunk.datePrecisionCodes.byteLength +
      chunk.coordinateSourceCodes.byteLength +
      chunk.countryCodes.byteLength +
      chunk.adminRegionCodes.byteLength +
      chunk.duplicateLineageCodes.byteLength +
      chunk.sortOrdinals.byteLength +
      chunk.latitudes.byteLength +
      chunk.longitudes.byteLength +
      chunk.mappedStates.byteLength +
      chunk.analysisYears.byteLength +
      chunk.analysisMonths.byteLength +
      chunk.analysisGridLatIndexes.byteLength +
      chunk.analysisGridLonIndexes.byteLength +
      chunk.analysisCoordinateClasses.byteLength +
      chunk.analysisGridKeyCodes.byteLength +
      chunk.analysisCoordinatePileKeyCodes.byteLength;
    return chunk;
  }

  function eventIdAt(chunk, index) {
    const stringCode = chunk.eventIdStringCodes[index];
    if (stringCode) {
      return eventIdStrings.values[stringCode - 1] || "";
    }
    return chunk.eventIds[index];
  }

  function sortOrdinalAt(chunk, index) {
    const value = chunk.sortOrdinals[index];
    return value === MISSING_SORT_ORDINAL ? null : value;
  }

  function analysisOrdinalFromTimelineOrdinal(value) {
    if (value == null || (typeof value === "string" && !value.trim())) return null;
    const ordinal = Number(value);
    return Number.isFinite(ordinal) ? Math.round(ordinal) + PYTHON_ORDINAL_UNIX_EPOCH : null;
  }

  function timelineOrdinalFromAnalysisOrdinal(value) {
    if (value == null || (typeof value === "string" && !value.trim())) return null;
    const ordinal = Number(value);
    return Number.isFinite(ordinal) ? Math.round(ordinal) - PYTHON_ORDINAL_UNIX_EPOCH : null;
  }

  function hasSelection(list) {
    return Array.isArray(list) && list.length > 0;
  }

  function listHas(list, value) {
    return Array.isArray(list) && list.indexOf(value || "") !== -1;
  }

  function mapToObject(map) {
    const object = {};
    map.forEach(function (value, key) {
      object[key] = value;
    });
    return object;
  }

  function normalizedFilters(payload) {
    const source = payload && payload.filters && typeof payload.filters === "object"
      ? payload.filters
      : (payload || {});
    return {
      keyword: source.keyword || "",
      sourceMode: source.sourceMode || "all",
      typeMode: source.typeMode || "all",
      precisionMode: source.precisionMode || "all",
      selectedSources: Array.isArray(source.selectedSources) ? source.selectedSources : [],
      selectedTypes: Array.isArray(source.selectedTypes) ? source.selectedTypes : [],
      selectedPrecisions: Array.isArray(source.selectedPrecisions) ? source.selectedPrecisions : [],
      legendEventMode: ["all", "subset", "none"].indexOf(source.legendEventMode) !== -1
        ? source.legendEventMode
        : "all",
      legendColorMode: source.legendColorMode || "craft_type",
      selectedLegendEventKeys: Array.isArray(source.selectedLegendEventKeys) ? source.selectedLegendEventKeys : [],
      hideLowPrecision: Boolean(source.hideLowPrecision),
      hideNonExactDates: Boolean(source.hideNonExactDates),
    };
  }

  function legendEventKey(visualTypeGroup, craftType, precision, colorMode) {
    if (colorMode === "single") return "all_events";
    if (colorMode === "type") return visualTypeGroup || "Other / unknown";
    if (colorMode === "precision") return precision || "unknown";
    return craftType || "unknown";
  }

  function keywordIdSet(payload) {
    return Array.isArray(payload.keywordEventIds) ? new Set(payload.keywordEventIds.map(String)) : null;
  }

  function eventMatchesNonDateFilters(values, filters, keywordIds, lowPrecisionValues) {
    const keywordActive = Boolean(filters.keyword) || Boolean(keywordIds);
    if (keywordActive && keywordIds && !keywordIds.has(String(values.eventId))) {
      return false;
    }
    if (filters.sourceMode === "none") {
      return false;
    }
    if (hasSelection(filters.selectedSources) && !listHas(filters.selectedSources, values.source)) {
      return false;
    }
    if (filters.typeMode === "none") {
      return false;
    }
    if (hasSelection(filters.selectedTypes) && !listHas(filters.selectedTypes, values.type)) {
      return false;
    }
    if (filters.precisionMode === "none") {
      return false;
    }
    if (hasSelection(filters.selectedPrecisions) && !listHas(filters.selectedPrecisions, values.precision)) {
      return false;
    }
    if (filters.hideLowPrecision && lowPrecisionValues.has(values.precision)) {
      return false;
    }
    if (filters.hideNonExactDates && values.datePrecision !== "exact_day") {
      return false;
    }
    if (filters.legendEventMode === "none") {
      return false;
    }
    if (
      filters.legendEventMode === "subset" &&
      !listHas(
        filters.selectedLegendEventKeys,
        legendEventKey(values.visualTypeGroup, values.craftType, values.precision, filters.legendColorMode)
      )
    ) {
      return false;
    }
    return true;
  }

  function readRowValuesInto(values, chunk, index) {
    values.eventId = eventIdAt(chunk, index);
    values.source = dictionaryValue(dictionaries.source, chunk.sourceCodes[index]);
    values.type = dictionaryValue(dictionaries.type, chunk.typeCodes[index]);
    values.visualTypeGroup = dictionaryValue(dictionaries.visualTypeGroup, chunk.visualTypeGroupCodes[index]);
    values.craftType = dictionaryValue(dictionaries.craftType, chunk.craftTypeCodes[index]);
    values.shape = dictionaryValue(dictionaries.shape, chunk.shapeCodes[index]);
    values.craftConfidence = dictionaryValue(dictionaries.craftConfidence, chunk.craftConfidenceCodes[index]);
    values.craftSource = dictionaryValue(dictionaries.craftSource, chunk.craftSourceCodes[index]);
    values.sameDayMatchStrength = dictionaryValue(dictionaries.sameDayMatchStrength, chunk.sameDayMatchStrengthCodes[index]);
    values.precision = dictionaryValue(dictionaries.precision, chunk.precisionCodes[index]);
    values.datePrecision = dictionaryValue(dictionaries.datePrecision, chunk.datePrecisionCodes[index]);
    values.coordinateSource = dictionaryValue(dictionaries.coordinateSource, chunk.coordinateSourceCodes[index]);
    values.country = dictionaryValue(dictionaries.country, chunk.countryCodes[index]) || "unknown";
    values.adminRegion = dictionaryValue(dictionaries.adminRegion, chunk.adminRegionCodes[index]) || "unknown";
    values.duplicateLineage = dictionaryValue(dictionaries.duplicateLineage, chunk.duplicateLineageCodes[index]);
    values.sortOrdinal = sortOrdinalAt(chunk, index);
    values.lat = Number.isFinite(chunk.latitudes[index]) ? chunk.latitudes[index] : null;
    values.lon = Number.isFinite(chunk.longitudes[index]) ? chunk.longitudes[index] : null;
    values.mapped = chunk.mappedStates[index] === 2;
    values.analysisYear = chunk.analysisYears[index] === MISSING_SORT_ORDINAL ? null : chunk.analysisYears[index];
    values.analysisMonth = chunk.analysisMonths[index] || null;
    values.analysisGridLatIndex = chunk.analysisGridLatIndexes[index] === MISSING_ANALYSIS_INDEX
      ? null
      : chunk.analysisGridLatIndexes[index];
    values.analysisGridLonIndex = chunk.analysisGridLonIndexes[index] === MISSING_ANALYSIS_INDEX
      ? null
      : chunk.analysisGridLonIndexes[index];
    values.analysisCoordinateClass = chunk.analysisCoordinateClasses[index] === 1
      ? "source_coordinates"
      : (chunk.analysisCoordinateClasses[index] === 2 ? "generalized_coordinates" : "unmapped");
    values.analysisGridKey = dictionaryValue(analysisGridKeys, chunk.analysisGridKeyCodes[index]);
    const pileCode = chunk.analysisCoordinatePileKeyCodes[index];
    values.analysisCoordinatePileGroup = pileCode ? dictionaryValue(analysisCoordinatePileKeys, pileCode) : "";
    values.analysisCoordinatePileCount = pileCode ? (analysisCoordinatePileCounts.get(pileCode) || 0) : 0;
    values.analysisFineSpatialStratum = values.analysisGridLatIndex == null || values.analysisGridLonIndex == null
      ? "unmapped"
      : "ea12x24:" + values.analysisGridLatIndex + ":" + values.analysisGridLonIndex;
    values.analysisCoarseSpatialStratum = values.analysisGridLatIndex == null || values.analysisGridLonIndex == null
      ? "unmapped"
      : "ea6x12:" + Math.floor(values.analysisGridLatIndex / 2) + ":" + Math.floor(values.analysisGridLonIndex / 2);
    values.analysisFiveYearBand = Number.isFinite(values.analysisYear)
      ? Math.floor(values.analysisYear / 5) * 5
      : null;
    values.analysisDecade = Number.isFinite(values.analysisYear)
      ? Math.floor(values.analysisYear / 10) * 10
      : null;
    return values;
  }

  function computeFilteredCatalogIds(payload) {
    const filters = normalizedFilters(payload);
    const keywordIds = keywordIdSet(payload || {});
    const lowPrecisionValues = Array.isArray(payload.lowPrecisionValues) ? new Set(payload.lowPrecisionValues) : new Set();
    const legendBaseFilters = Object.assign({}, filters, {
      legendEventMode: "all",
      selectedLegendEventKeys: [],
    });
    const startOrdinal = Number(payload.timeRangeStartOrdinal);
    const endOrdinal = Number(payload.timeRangeEndOrdinal);
    const hasTimeRange = Number.isFinite(startOrdinal) && Number.isFinite(endOrdinal);
    const minOrdinal = hasTimeRange ? Math.min(startOrdinal, endOrdinal) : null;
    const maxOrdinal = hasTimeRange ? Math.max(startOrdinal, endOrdinal) : null;
    const legendEventCounts = new Map();
    let preserveDateAscending = Boolean(payload.catalogExactDayAscending);
    const eventIds = [];
    const values = {};

    for (const chunk of chunks) {
      for (let index = 0; index < chunk.length; index += 1) {
        readRowValuesInto(values, chunk, index);
        const rowOrdinal = values.sortOrdinal;
        if (
          eventMatchesNonDateFilters(values, legendBaseFilters, keywordIds, lowPrecisionValues) &&
          (
            !hasTimeRange ||
            (Number.isFinite(rowOrdinal) && rowOrdinal >= minOrdinal && rowOrdinal <= maxOrdinal)
          )
        ) {
          const legendKey = legendEventKey(
            values.visualTypeGroup,
            values.craftType,
            values.precision,
            filters.legendColorMode
          );
          legendEventCounts.set(legendKey, (legendEventCounts.get(legendKey) || 0) + 1);
        }
        if (!eventMatchesNonDateFilters(values, filters, keywordIds, lowPrecisionValues)) {
          continue;
        }
        eventIds.push(values.eventId);
        if (preserveDateAscending && (values.datePrecision !== "exact_day" || !Number.isFinite(rowOrdinal))) {
          preserveDateAscending = false;
        }
      }
    }

    return {
      eventIds,
      keywordActive: Boolean(filters.keyword),
      preserveDateAscending,
      rowCount,
      legendEventCounts: mapToObject(legendEventCounts),
      legendColorMode: filters.legendColorMode,
    };
  }

  function computeFacetCounts(payload) {
    const filters = normalizedFilters(payload);
    const keywordIds = Array.isArray(payload.keywordEventIds) ? new Set(payload.keywordEventIds.map(String)) : null;
    const sourceSelected = filters.selectedSources;
    const typeSelected = filters.selectedTypes;
    const precisionSelected = filters.selectedPrecisions;
    const lowPrecisionValues = Array.isArray(payload.lowPrecisionValues) ? new Set(payload.lowPrecisionValues) : new Set();
    const startOrdinal = Number(payload.timeRangeStartOrdinal);
    const endOrdinal = Number(payload.timeRangeEndOrdinal);
    const hasTimeRange = Number.isFinite(startOrdinal) && Number.isFinite(endOrdinal);
    const minOrdinal = hasTimeRange ? Math.min(startOrdinal, endOrdinal) : null;
    const maxOrdinal = hasTimeRange ? Math.max(startOrdinal, endOrdinal) : null;
    const sourceCounts = new Map();
    const typeCounts = new Map();
    const precisionCounts = new Map();
    const legendEventCounts = new Map();
    const values = {};
    const facetBaseFilters = Object.assign({}, filters, {
      selectedSources: [],
      selectedTypes: [],
      selectedPrecisions: [],
      sourceMode: filters.sourceMode === "none" ? "none" : "all",
      typeMode: filters.typeMode === "none" ? "none" : "all",
      precisionMode: filters.precisionMode === "none" ? "none" : "all",
    });
    const legendBaseFilters = Object.assign({}, filters, {
      legendEventMode: "all",
      selectedLegendEventKeys: [],
    });

    for (const chunk of chunks) {
      for (let index = 0; index < chunk.length; index += 1) {
        readRowValuesInto(values, chunk, index);
        const sortOrdinal = values.sortOrdinal;
        if (hasTimeRange && (!Number.isFinite(sortOrdinal) || sortOrdinal < minOrdinal || sortOrdinal > maxOrdinal)) {
          continue;
        }
        if (keywordIds && !keywordIds.has(String(values.eventId))) {
          continue;
        }
        if (eventMatchesNonDateFilters(values, legendBaseFilters, keywordIds, lowPrecisionValues)) {
          const legendKey = legendEventKey(
            values.visualTypeGroup,
            values.craftType,
            values.precision,
            filters.legendColorMode
          );
          legendEventCounts.set(legendKey, (legendEventCounts.get(legendKey) || 0) + 1);
        }
        if (!eventMatchesNonDateFilters(values, facetBaseFilters, keywordIds, lowPrecisionValues)) {
          continue;
        }

        const sourceSubsetActive = hasSelection(sourceSelected);
        const typeSubsetActive = hasSelection(typeSelected);
        const precisionSubsetActive = hasSelection(precisionSelected);

        const sourceFacetEligible =
          filters.typeMode !== "none" &&
          filters.precisionMode !== "none" &&
          (!typeSubsetActive || listHas(typeSelected, values.type)) &&
          (!precisionSubsetActive || listHas(precisionSelected, values.precision));
        if (sourceFacetEligible && values.source) {
          sourceCounts.set(values.source, (sourceCounts.get(values.source) || 0) + 1);
        }

        const typeFacetEligible =
          filters.sourceMode !== "none" &&
          filters.precisionMode !== "none" &&
          (!sourceSubsetActive || listHas(sourceSelected, values.source)) &&
          (!precisionSubsetActive || listHas(precisionSelected, values.precision));
        if (typeFacetEligible && values.type) {
          typeCounts.set(values.type, (typeCounts.get(values.type) || 0) + 1);
        }

        const precisionFacetEligible =
          filters.sourceMode !== "none" &&
          filters.typeMode !== "none" &&
          (!sourceSubsetActive || listHas(sourceSelected, values.source)) &&
          (!typeSubsetActive || listHas(typeSelected, values.type));
        if (precisionFacetEligible && values.precision) {
          precisionCounts.set(values.precision, (precisionCounts.get(values.precision) || 0) + 1);
        }
      }
    }

    return {
      source: mapToObject(sourceCounts),
      type: mapToObject(typeCounts),
      precision: mapToObject(precisionCounts),
      legendEventCounts: mapToObject(legendEventCounts),
      legendColorMode: filters.legendColorMode,
      rowCount,
    };
  }

  function analysisFilterGeneration(message) {
    const value = message && message.filterGeneration != null ? message.filterGeneration : message && message.generation;
    return Number.isFinite(Number(value)) ? Number(value) : 0;
  }

  function normalizedHashObject(value) {
    const result = {};
    Object.keys(value && typeof value === "object" ? value : {}).sort().forEach(function (key) {
      result[key] = String(value[key] == null ? "" : value[key]);
    });
    return result;
  }

  function normalizedAnalysisDomains(value) {
    return Array.isArray(value) ? value.map(String).sort() : [];
  }

  function normalizeLongitude(value) {
    let longitude = Number(value);
    if (!Number.isFinite(longitude)) return null;
    while (longitude < -180) longitude += 360;
    while (longitude > 180) longitude -= 360;
    return longitude;
  }

  function pointInsideAnalysisRectangle(latitude, longitude, shape) {
    const bounds = shape && shape.bounds && typeof shape.bounds === "object" ? shape.bounds : {};
    const north = Number(bounds.north);
    const south = Number(bounds.south);
    const east = normalizeLongitude(bounds.east);
    const west = normalizeLongitude(bounds.west);
    if (![north, south, east, west].every(Number.isFinite)) return false;
    const minimumLatitude = Math.max(-90, Math.min(north, south));
    const maximumLatitude = Math.min(90, Math.max(north, south));
    if (latitude < minimumLatitude || latitude > maximumLatitude) return false;
    if (west <= east) return longitude >= west && longitude <= east;
    return longitude >= west || longitude <= east;
  }

  function analysisGreatCircleDistanceMeters(latitudeA, longitudeA, latitudeB, longitudeB) {
    const radians = Math.PI / 180;
    const deltaLatitude = (latitudeB - latitudeA) * radians;
    const deltaLongitude = (longitudeB - longitudeA) * radians;
    const firstLatitude = latitudeA * radians;
    const secondLatitude = latitudeB * radians;
    const haversine = Math.sin(deltaLatitude / 2) * Math.sin(deltaLatitude / 2) +
      Math.cos(firstLatitude) * Math.cos(secondLatitude) *
      Math.sin(deltaLongitude / 2) * Math.sin(deltaLongitude / 2);
    return 6371008.8 * 2 * Math.atan2(Math.sqrt(Math.max(0, haversine)), Math.sqrt(Math.max(0, 1 - haversine)));
  }

  function pointInsideAnalysisCircle(latitude, longitude, shape) {
    const center = shape && shape.center && typeof shape.center === "object" ? shape.center : {};
    const centerLatitude = Number(center.lat);
    const centerLongitude = normalizeLongitude(center.lng == null ? center.lon : center.lng);
    const radiusMeters = Number(shape && shape.radiusMeters);
    if (!Number.isFinite(centerLatitude) || centerLatitude < -90 || centerLatitude > 90 ||
        !Number.isFinite(centerLongitude) || !Number.isFinite(radiusMeters) || radiusMeters < 0) {
      return false;
    }
    return analysisGreatCircleDistanceMeters(latitude, longitude, centerLatitude, centerLongitude) <= radiusMeters;
  }

  function pointInsideAnyAnalysisShape(latitudeValue, longitudeValue, shapes) {
    if (!Array.isArray(shapes)) return true;
    if (!shapes.length) return false;
    const latitude = Number(latitudeValue);
    const longitude = normalizeLongitude(longitudeValue);
    if (!Number.isFinite(latitude) || latitude < -90 || latitude > 90 || !Number.isFinite(longitude)) return false;
    return shapes.some(function (shape) {
      const type = String(shape && shape.type || "").toLowerCase();
      if (type === "rectangle") return pointInsideAnalysisRectangle(latitude, longitude, shape);
      if (type === "circle") return pointInsideAnalysisCircle(latitude, longitude, shape);
      return false;
    });
  }

  function analysisCacheKey(message) {
    const filters = normalizedFilters(message || {});
    const shapeSignature = Array.isArray(message.areaFilterShapes) ? message.areaFilterShapes : null;
    return JSON.stringify({
      rowCount,
      filterGeneration: analysisFilterGeneration(message),
      baselineMode: ensureAnalysisStats().normalizeBaselineMode(message.baselineMode),
      start: Number.isFinite(Number(message.timeRangeStartOrdinal)) ? Number(message.timeRangeStartOrdinal) : null,
      end: Number.isFinite(Number(message.timeRangeEndOrdinal)) ? Number(message.timeRangeEndOrdinal) : null,
      timeRangeMode: String(message.timeRangeMode || ""),
      fullTimeRange: Boolean(message.fullTimeRange),
      filters,
      keywordCount: Array.isArray(message.keywordEventIds) ? message.keywordEventIds.length : null,
      areaEventCount: Array.isArray(message.areaFilterEventIds) ? message.areaFilterEventIds.length : null,
      areaFilterShapes: shapeSignature,
      selectedDomains: normalizedAnalysisDomains(message.selectedDomains),
      contextLayers: message.contextLayers || {},
      contextReleaseHashes: normalizedHashObject(message.contextReleaseHashes),
      artifactHashes: normalizedHashObject(message.artifactHashes),
      datasetHash: String(message.datasetHash || ""),
      estimatorVersion: String(message.estimatorVersion || "analysis-v2"),
      analysisPhase: String(message.analysisPhase || (message.quickMode ? "quick" : "full")),
      quickMode: Boolean(message.quickMode),
      callerKey: String(message.analysisCacheKey || ""),
    });
  }

  function sortedAnalysisValues(value) {
    return (Array.isArray(value) ? value : []).map(String).sort();
  }

  function analysisMatchCacheKey(message) {
    const filters = normalizedFilters(message || {});
    return JSON.stringify({
      rowCount,
      filters,
      keywordEventIds: sortedAnalysisValues(message.keywordEventIds),
      areaFilterEventIds: Array.isArray(message.areaFilterEventIds)
        ? sortedAnalysisValues(message.areaFilterEventIds)
        : null,
      areaFilterShapes: Array.isArray(message.areaFilterShapes) ? message.areaFilterShapes : null,
      lowPrecisionValues: sortedAnalysisValues(message.lowPrecisionValues),
    });
  }

  function cacheAnalysisMatches(key, value) {
    if (analysisMatchCache.has(key)) analysisMatchCache.delete(key);
    analysisMatchCache.set(key, value);
    while (analysisMatchCache.size > 4) {
      analysisMatchCache.delete(analysisMatchCache.keys().next().value);
    }
  }

  function analysisRowMatches(values, filters, keywordIds, areaEventIds, areaShapes, lowPrecisionValues) {
    if (!eventMatchesNonDateFilters(values, filters, keywordIds, lowPrecisionValues)) return false;
    if (areaEventIds && !areaEventIds.has(String(values.eventId))) return false;
    if (areaShapes && !pointInsideAnyAnalysisShape(values.lat, values.lon, areaShapes)) return false;
    return true;
  }

  function matchedAnalysisRows(message, filters, keywordIds, areaEventIds, areaShapes, lowPrecisionValues) {
    const key = analysisMatchCacheKey(message);
    if (analysisMatchCache.has(key)) {
      const cached = analysisMatchCache.get(key);
      analysisMatchCache.delete(key);
      analysisMatchCache.set(key, cached);
      return cached;
    }
    const values = {};
    const chunkIndexes = [];
    let matchedRowCount = 0;
    for (const chunk of chunks) {
      const indexes = [];
      for (let index = 0; index < chunk.length; index += 1) {
        readRowValuesInto(values, chunk, index);
        if (!analysisRowMatches(values, filters, keywordIds, areaEventIds, areaShapes, lowPrecisionValues)) continue;
        indexes.push(index);
      }
      const typedIndexes = Uint32Array.from(indexes);
      matchedRowCount += typedIndexes.length;
      chunkIndexes.push(typedIndexes);
    }
    const result = { key, chunkIndexes, matchedRowCount };
    cacheAnalysisMatches(key, result);
    return result;
  }

  function cacheAnalysisResult(key, result) {
    if (analysisCache.has(key)) analysisCache.delete(key);
    analysisCache.set(key, result);
    while (analysisCache.size > ANALYSIS_CACHE_LIMIT) {
      analysisCache.delete(analysisCache.keys().next().value);
    }
  }

  function forEachAnalysisRow(callback) {
    const values = {};
    for (const chunk of chunks) {
      for (let index = 0; index < chunk.length; index += 1) {
        readRowValuesInto(values, chunk, index);
        values.sortOrdinal = analysisOrdinalFromTimelineOrdinal(values.sortOrdinal);
        callback(values);
      }
    }
  }

  function forEachMatchedAnalysisRow(matched, callback) {
    const values = {};
    for (let chunkIndex = 0; chunkIndex < chunks.length; chunkIndex += 1) {
      const chunk = chunks[chunkIndex];
      const indexes = matched.chunkIndexes[chunkIndex] || [];
      for (let cursor = 0; cursor < indexes.length; cursor += 1) {
        readRowValuesInto(values, chunk, indexes[cursor]);
        values.sortOrdinal = analysisOrdinalFromTimelineOrdinal(values.sortOrdinal);
        callback(values);
      }
    }
  }

  function analysisActiveRange(message) {
    const fullTimeRange = Boolean(message.fullTimeRange) || ["full", "all", "all_time"].indexOf(
      String(message.timeRangeMode || "").trim().toLowerCase()
    ) !== -1;
    if (fullTimeRange) return null;
    const start = analysisOrdinalFromTimelineOrdinal(message.timeRangeStartOrdinal);
    const end = analysisOrdinalFromTimelineOrdinal(message.timeRangeEndOrdinal);
    if (!Number.isFinite(start) || !Number.isFinite(end)) return null;
    return start <= end ? [start, end] : [end, start];
  }

  function copySpatialAnalysisRow(values) {
    return {
      eventId: String(values.eventId == null ? "" : values.eventId),
      mapped: Boolean(values.mapped),
      lat: Number(values.lat),
      lon: Number(values.lon),
      source: values.source,
      craftType: values.craftType,
      craftConfidence: values.craftConfidence,
      sameDayMatchStrength: values.sameDayMatchStrength,
      datePrecision: values.datePrecision,
      duplicateLineage: values.duplicateLineage,
      sortOrdinal: values.sortOrdinal,
      analysisYear: values.analysisYear,
      analysisFiveYearBand: values.analysisFiveYearBand,
      analysisDecade: values.analysisDecade,
      analysisCoordinateClass: values.analysisCoordinateClass,
      analysisFineSpatialStratum: values.analysisFineSpatialStratum,
      analysisCoarseSpatialStratum: values.analysisCoarseSpatialStratum,
      analysisCoordinatePileCount: values.analysisCoordinatePileCount,
      country: values.country,
      adminRegion: values.adminRegion,
    };
  }

  // Keep the catalog worker's dispatch filter aligned with the spatial
  // estimator without importing the expensive estimator into this worker.
  // The dedicated spatial worker applies the authoritative gate again.
  function spatialDispatchEligible(rowValue) {
    const row = rowValue || {};
    const latitude = Number(row.lat);
    const longitude = Number(row.lon);
    if (!row.mapped || !Number.isFinite(latitude) || !Number.isFinite(longitude)) return false;
    const coordinateClass = String(row.analysisCoordinateClass || "unmapped").trim().toLowerCase();
    if (!SPATIAL_SOURCE_COORDINATE_CLASSES.has(coordinateClass)) return false;
    if (String(row.datePrecision || "unknown").trim().toLowerCase() !== "exact_day") return false;
    const craft = String(row.craftType || "unknown").trim().toLowerCase();
    if (SPATIAL_EXCLUDED_CRAFTS.has(craft)) return false;
    if (!SPATIAL_QUALIFIED_CONFIDENCE.has(String(row.craftConfidence || "none").trim().toLowerCase())) return false;
    if (!SPATIAL_QUALIFIED_SAME_DAY.has(String(row.sameDayMatchStrength || "none").trim().toLowerCase())) return false;
    if (String(row.duplicateLineage || "").trim()) return false;
    if (Math.max(0, Number(row.analysisCoordinatePileCount) || 0) >= 10) return false;
    return true;
  }

  function activeSpatialRows(message, matched, filters, keywordIds, areaEventIds, areaShapes, lowPrecisionValues) {
    const range = analysisActiveRange(message);
    const rows = [];
    const collect = function (row) {
      if (range && (!Number.isFinite(row.sortOrdinal) || row.sortOrdinal < range[0] || row.sortOrdinal > range[1])) return;
      if (!spatialDispatchEligible(row)) return;
      rows.push(copySpatialAnalysisRow(row));
    };
    if (matched) {
      forEachMatchedAnalysisRow(matched, collect);
      return rows;
    }
    forEachAnalysisRow(function (row) {
      if (!analysisRowMatches(row, filters, keywordIds, areaEventIds, areaShapes, lowPrecisionValues)) return;
      collect(row);
    });
    return rows;
  }

  function spatialReadinessFromManifest(manifest) {
    const counts = manifest && manifest.counts || {};
    const hashes = analysisSpatialArtifacts.artifactHashes || {};
    return {
      ufoCraftPoints: {
        status: Number(counts.ufoNeighborEligiblePoints || 0) >= 25 ? "exploratory_ready" : "not_estimable",
        eligibleN: Number(counts.ufoNeighborEligiblePoints || 0),
        totalN: Number(manifest && manifest.sources && manifest.sources.ufoPointNeighbors &&
          manifest.sources.ufoPointNeighbors.counts && manifest.sources.ufoPointNeighbors.counts.packedRows || 0),
        releaseHash: hashes.ufoPointNeighbors || "",
        reasons: [
          "Eligible points are limited to UFOCAT and Majestic after raw-coordinate, date, craft-confidence, same-day, and coordinate-pile gates.",
          "Source-balanced estimates and leave-one-source-out sensitivity are mandatory; this is not population coverage.",
        ],
      },
      militaryFacilities: {
        status: Number(counts.facilityInferentialEligible || 0) >= 25 ? "exploratory_ready" : "not_estimable",
        eligibleN: Number(counts.facilityInferentialEligible || 0),
        totalN: Number(counts.facilityMarkers || 0),
        releaseHash: hashes.facilityAnalysis || "",
        reasons: ["Only verified facility markers with adequate coordinate and temporal confidence are inferential."],
      },
      researchFacilities: {
        status: "coverage_limited",
        eligibleN: Number(counts.facilityInferentialEligible || 0),
        totalN: Number(counts.facilityMarkers || 0),
        releaseHash: hashes.facilityAnalysis || "",
        reasons: ["Facility-class-specific support is reported in the facility evidence result."],
      },
      claimedUfoSites: {
        status: "descriptive_only",
        eligibleN: 0,
        totalN: Number(manifest && manifest.sources && manifest.sources.facilities &&
          manifest.sources.facilities.counts && manifest.sources.facilities.counts.claimedDescriptive || 0),
        releaseHash: hashes.facilityAnalysis || "",
        reasons: ["Claimed sites are excluded from inference and Pattern Finder."],
      },
      cropCircles: {
        status: Number(counts.cropKilometerEligible || 0) >= 25 ? "exploratory_ready" : "not_estimable",
        eligibleN: Number(counts.cropKilometerEligible || 0),
        totalN: Number(counts.cropContextRecords || 0),
        releaseHash: hashes.cropContextReadiness || "",
        reasons: [
          "No crop record currently passes exact-site, formation-date, and review gates together.",
          "Catalog dates cannot substitute for formation dates.",
        ],
      },
      animalReports: {
        status: Number(counts.animalKilometerEligible || 0) >= 25 ? "exploratory_ready" : "not_estimable",
        eligibleN: Number(counts.animalKilometerEligible || 0),
        totalN: Number(counts.animalContextRecords || 0),
        releaseHash: hashes.animalContextReadiness || "",
        reasons: ["Generalized animal markers cannot enter kilometer analysis."],
      },
      relationshipReconciliation: relationshipReconciliationReadiness(manifest || {}),
      chronologyConnectors: {
        status: "prohibited",
        eligibleN: 0,
        totalN: 0,
        releaseHash: "",
        reasons: ["Chronology connectors are display-only and are never read by spatial estimators."],
      },
    };
  }

  function addSpatialSuppressionReason(target, reason) {
    if (!target || typeof target !== "object") return;
    if (!Array.isArray(target.suppressionReasons)) target.suppressionReasons = [];
    if (target.suppressionReasons.indexOf(reason) === -1) target.suppressionReasons.push(reason);
  }

  function removeSpatialInferentialFields(value) {
    if (Array.isArray(value)) {
      value.forEach(removeSpatialInferentialFields);
      return;
    }
    if (!value || typeof value !== "object") return;
    if (Object.prototype.hasOwnProperty.call(value, "pValue")) value.pValue = null;
    if (Object.prototype.hasOwnProperty.call(value, "qValue")) value.qValue = null;
    if (Object.prototype.hasOwnProperty.call(value, "patternFinderEligible")) value.patternFinderEligible = false;
    Object.keys(value).forEach(function (key) { removeSpatialInferentialFields(value[key]); });
  }

  function markSpatialLaneDescriptive(lane) {
    if (!lane || typeof lane !== "object") return;
    lane.inferenceEnabled = false;
    lane.status = "descriptive_only";
    addSpatialSuppressionReason(lane, "full_catalog_overlap_descriptive_no_inference");
    (Array.isArray(lane.cells) ? lane.cells : []).forEach(function (cell) {
      cell.inferenceEligible = false;
      cell.status = "descriptive_only";
      cell.pValue = null;
      cell.qValue = null;
      cell.patternFinderEligible = false;
      addSpatialSuppressionReason(cell, "full_catalog_overlap_descriptive_no_inference");
    });
  }

  function finalizeSpatialEvidenceResult(resultValue, readinessValue, baselineModeValue, inferenceEnabledValue) {
    const result = resultValue && typeof resultValue === "object" ? resultValue : {};
    const readiness = readinessValue && typeof readinessValue === "object" ? readinessValue : {};
    const baselineMode = ensureAnalysisStats().normalizeBaselineMode(baselineModeValue);
    const inferenceEnabled = inferenceEnabledValue !== false &&
      baselineMode !== ensureAnalysisStats().BASELINE_MODES.FULL_CATALOG;
    result.baselineMode = baselineMode;
    result.inferenceEnabled = inferenceEnabled;
    const relationship = readiness.relationshipReconciliation;
    if (relationship && typeof relationship === "object") {
      result.relationshipReadiness = Object.assign({}, relationship);
      if (!Array.isArray(result.readiness)) result.readiness = [];
      const existing = result.readiness.findIndex(function (row) {
        return row && row.key === "relationshipReconciliation";
      });
      if (existing === -1) result.readiness.push(Object.assign({}, relationship));
      else result.readiness[existing] = Object.assign({}, relationship);
    }
    if (inferenceEnabled) return result;
    removeSpatialInferentialFields(result);
    addSpatialSuppressionReason(result, "full_catalog_overlap_descriptive_no_inference");
    const cooccurrence = result.cooccurrence || {};
    ["crossSource", "sameSource"].forEach(function (key) {
      (Array.isArray(cooccurrence[key]) ? cooccurrence[key] : []).forEach(function (lane) {
        markSpatialLaneDescriptive(lane);
      });
    });
    const facility = result.facility;
    if (facility && typeof facility === "object") {
      facility.inferenceEnabled = false;
      facility.status = "descriptive_only";
      addSpatialSuppressionReason(facility, "full_catalog_overlap_descriptive_no_inference");
      markSpatialLaneDescriptive(facility.primary);
      markSpatialLaneDescriptive(facility.inactiveNegativeControl);
      (Array.isArray(facility.sensitivity) ? facility.sensitivity : []).forEach(function (lane) {
        markSpatialLaneDescriptive(lane);
      });
    }
    return result;
  }

  function computeSpatialEvidence(message, matched, filters, keywordIds, areaEventIds, areaShapes, lowPrecisionValues) {
    const baselineMode = ensureAnalysisStats().normalizeBaselineMode(message.baselineMode);
    const inferenceEnabled = baselineMode !== ensureAnalysisStats().BASELINE_MODES.FULL_CATALOG;
    const readiness = spatialReadinessFromManifest(analysisSpatialArtifacts.manifest || {});
    if (!analysisSpatialArtifacts.loaded) {
      return finalizeSpatialEvidenceResult({
        estimatorVersion: ensureAnalysisSpatial().ESTIMATOR_VERSION,
        status: "artifacts_not_loaded",
        suppressionReasons: ["spatial_artifacts_not_loaded"],
        traceInputsRead: false,
      }, readiness, baselineMode, inferenceEnabled);
    }
    const rows = activeSpatialRows(message, matched, filters, keywordIds, areaEventIds, areaShapes, lowPrecisionValues);
    const result = ensureAnalysisSpatial().computeSpatialAnalysis({
      rows,
      edges: analysisSpatialArtifacts.neighbors || [],
      facilities: analysisSpatialArtifacts.facilities || [],
      readiness,
      artifactHashes: Object.assign({}, analysisSpatialArtifacts.artifactHashes || {}),
      seed: String(message.datasetHash || "catalog") + "|" + analysisFilterGeneration(message),
      baselineMode,
      inferenceEnabled,
      permutationCount: message.spatialPermutationCount,
      bootstrapCount: message.spatialBootstrapCount,
      minimumStratumSize: message.spatialMinimumStratumSize,
    });
    return finalizeSpatialEvidenceResult(result, readiness, baselineMode, inferenceEnabled);
  }

  function convertAnalysisPreviewOrdinalsToTimeline(value) {
    if (Array.isArray(value)) {
      value.forEach(convertAnalysisPreviewOrdinalsToTimeline);
      return value;
    }
    if (!value || typeof value !== "object") return value;
    if (Object.prototype.hasOwnProperty.call(value, "startOrdinal")) {
      value.startOrdinal = timelineOrdinalFromAnalysisOrdinal(value.startOrdinal);
    }
    if (Object.prototype.hasOwnProperty.call(value, "endOrdinal")) {
      value.endOrdinal = timelineOrdinalFromAnalysisOrdinal(value.endOrdinal);
    }
    Object.keys(value).forEach(function (key) {
      convertAnalysisPreviewOrdinalsToTimeline(value[key]);
    });
    return value;
  }

  function analysisResultForTimeline(result) {
    if (!result || typeof result !== "object") return result;
    const baseline = result.baseline;
    if (baseline && typeof baseline === "object") {
      ["activeRange", "referenceRange"].forEach(function (key) {
        const range = baseline[key];
        if (!range || typeof range !== "object") return;
        range.start = timelineOrdinalFromAnalysisOrdinal(range.start);
        range.end = timelineOrdinalFromAnalysisOrdinal(range.end);
      });
      baseline.ordinalEpoch = "unix_day";
    }
    convertAnalysisPreviewOrdinalsToTimeline(result);
    result.ordinalEpoch = "unix_day";
    return result;
  }

  function computeAnalysisResult(message, optionsValue) {
    const options = optionsValue || {};
    const stats = ensureAnalysisStats();
    const filters = normalizedFilters(message || {});
    const keywordIds = keywordIdSet(message || {});
    const areaEventIds = Array.isArray(message.areaFilterEventIds)
      ? new Set(message.areaFilterEventIds.map(String))
      : null;
    const areaShapes = Array.isArray(message.areaFilterShapes) && message.areaFilterShapes.length
      ? message.areaFilterShapes
      : null;
    const lowPrecisionValues = Array.isArray(message.lowPrecisionValues)
      ? new Set(message.lowPrecisionValues)
      : new Set();
    const baselineMode = stats.normalizeBaselineMode(message.baselineMode);
    const canReuseMatchedRows = baselineMode !== stats.BASELINE_MODES.FULL_CATALOG;
    const matched = canReuseMatchedRows
      ? matchedAnalysisRows(message, filters, keywordIds, areaEventIds, areaShapes, lowPrecisionValues)
      : null;
    const selectedDomains = normalizedAnalysisDomains(message.selectedDomains);
    const result = stats.computeAnalysis({
      forEachRow: matched
        ? function (callback) { forEachMatchedAnalysisRow(matched, callback); }
        : forEachAnalysisRow,
      matchesNonDateFilters: matched
        ? undefined
        : function (row) {
            return analysisRowMatches(row, filters, keywordIds, areaEventIds, areaShapes, lowPrecisionValues);
          },
      baselineMode,
      timeRangeStartOrdinal: analysisOrdinalFromTimelineOrdinal(message.timeRangeStartOrdinal),
      timeRangeEndOrdinal: analysisOrdinalFromTimelineOrdinal(message.timeRangeEndOrdinal),
      timeRangeMode: message.timeRangeMode,
      fullTimeRange: Boolean(message.fullTimeRange),
      datasetHash: message.datasetHash,
      selectedDomains,
      contextLayers: message.contextLayers || {},
      contextReleaseHashes: normalizedHashObject(message.contextReleaseHashes),
      artifactHashes: Object.assign(
        {},
        normalizedHashObject(message.artifactHashes),
        analysisSpatialArtifacts.artifactHashes || {}
      ),
      estimatorVersion: String(message.estimatorVersion || "ufo-analysis-v2"),
      analysisPhase: String(message.analysisPhase || (message.quickMode ? "quick" : "full")),
      quickMode: Boolean(message.quickMode),
      contextProjections: analysisContext,
    });
    if (!options.deferSpatial &&
        (selectedDomains.indexOf("spatial") !== -1 || selectedDomains.indexOf("spatial_evidence") !== -1)) {
      result.spatialEvidence = computeSpatialEvidence(
        message,
        matched,
        filters,
        keywordIds,
        areaEventIds,
        areaShapes,
        lowPrecisionValues
      );
    }
    return analysisResultForTimeline(result);
  }

  function analysisContextSnapshot() {
    return {
      rowCounts: {
        cropCircles: Array.isArray(analysisContext.cropCircles) ? analysisContext.cropCircles.length : 0,
        animalReports: Array.isArray(analysisContext.animalReports) ? analysisContext.animalReports.length : 0,
      },
      storage: {
        mode: "normalized_context_rows",
        loadedDomains: [
          Array.isArray(analysisContext.cropCircles) ? "cropCircles" : "",
          Array.isArray(analysisContext.animalReports) ? "animalReports" : "",
        ].filter(Boolean),
      },
    };
  }

  function firstProjectionValue(object, names) {
    if (!object || typeof object !== "object") return { present: false, value: null };
    for (const name of names) {
      if (Object.prototype.hasOwnProperty.call(object, name)) return { present: true, value: object[name] };
    }
    return { present: false, value: null };
  }

  function mergeAnalysisContextProjections(projectionsValue, manifestValue) {
    const stats = ensureAnalysisStats();
    const projections = projectionsValue && typeof projectionsValue === "object" ? projectionsValue : {};
    const crop = firstProjectionValue(projections, ["cropCircles", "crops", "crop_circles"]);
    const animals = firstProjectionValue(projections, ["animalReports", "animals", "animal_reports"]);
    const nextManifest = manifestValue && typeof manifestValue === "object" ? manifestValue : analysisContext.manifest;
    if (crop.present) {
      analysisContext.cropCircles = stats.normalizeContextProjections({
        manifest: nextManifest,
        cropCircles: crop.value,
      }).cropCircles;
    }
    if (animals.present) {
      analysisContext.animalReports = stats.normalizeContextProjections({
        manifest: nextManifest,
        animalReports: animals.value,
      }).animalReports;
    }
    if (manifestValue && typeof manifestValue === "object") {
      analysisContext.manifest = Object.assign({}, analysisContext.manifest || {}, manifestValue);
    }
    analysisCache.clear();
    return analysisContextSnapshot();
  }

  function rawJsonFallbackUrl(url) {
    return String(url || "").replace(/\.json\.gz(?:\?.*)?$/i, function (match) {
      const queryIndex = match.indexOf("?");
      return ".json" + (queryIndex === -1 ? "" : match.slice(queryIndex));
    });
  }

  function normalizedSha256(value) {
    const text = String(value || "").trim().toLowerCase().replace(/^sha256:/, "");
    return /^[0-9a-f]{64}$/.test(text) ? text : "";
  }

  async function sha256Hex(bytes) {
    if (!self.crypto || !self.crypto.subtle || typeof self.crypto.subtle.digest !== "function") {
      throw new Error("SHA-256 verification is unavailable in this worker.");
    }
    const digest = new Uint8Array(await self.crypto.subtle.digest("SHA-256", bytes));
    return Array.from(digest).map(function (value) { return value.toString(16).padStart(2, "0"); }).join("");
  }

  async function verifyAnalysisBytes(bytes, expectedValue, label) {
    const expected = normalizedSha256(expectedValue);
    if (!expected) return;
    const actual = await sha256Hex(bytes);
    if (actual !== expected) {
      throw new Error(label + " SHA-256 mismatch: expected " + expected + ", received " + actual + ".");
    }
  }

  async function decodeJsonResponse(response, sourceUrl, integrity) {
    const bytes = new Uint8Array(await response.arrayBuffer());
    let decodedBytes = bytes;
    const gzipEncoded = bytes.length >= 2 && bytes[0] === 0x1f && bytes[1] === 0x8b;
    if (gzipEncoded) {
      await verifyAnalysisBytes(bytes, integrity && integrity.gzipSha256, sourceUrl + " compressed payload");
      if (typeof DecompressionStream !== "function") {
        throw new Error("gzip context projection requires DecompressionStream support: " + sourceUrl);
      }
      const stream = new Response(bytes).body.pipeThrough(new DecompressionStream("gzip"));
      decodedBytes = new Uint8Array(await new Response(stream).arrayBuffer());
    }
    await verifyAnalysisBytes(decodedBytes, integrity && integrity.sha256, sourceUrl + " JSON payload");
    if (!gzipEncoded && normalizedSha256(integrity && integrity.gzipSha256) && !normalizedSha256(integrity && integrity.sha256)) {
      throw new Error(sourceUrl + " was decoded before the only available gzip SHA-256 could be verified.");
    }
    return JSON.parse(new TextDecoder("utf-8").decode(decodedBytes));
  }

  async function fetchAnalysisJson(urlValue, integrity) {
    const url = String(urlValue || "");
    if (!url) return null;
    try {
      const response = await fetch(url, { cache: "force-cache" });
      if (!response.ok) throw new Error("HTTP " + response.status + " for " + url);
      return await decodeJsonResponse(response, url, integrity || {});
    } catch (error) {
      if (error && /SHA-256 mismatch|only available gzip SHA-256/.test(String(error.message || error))) throw error;
      const fallback = rawJsonFallbackUrl(url);
      if (!fallback || fallback === url) throw error;
      const response = await fetch(fallback, { cache: "force-cache" });
      if (!response.ok) throw new Error("HTTP " + response.status + " for " + fallback);
      return await decodeJsonResponse(response, fallback, integrity || {});
    }
  }

  function manifestArtifactEntry(manifest, key) {
    const artifacts = manifest && manifest.artifacts && typeof manifest.artifacts === "object" ? manifest.artifacts : {};
    return artifacts[key] && typeof artifacts[key] === "object" ? artifacts[key] : null;
  }

  function manifestArtifactIntegrity(manifest, key) {
    const entry = manifestArtifactEntry(manifest, key) || {};
    return {
      sha256: entry.sha256 || "",
      gzipSha256: entry.gzipSha256 || entry.gzip_sha256 || "",
    };
  }

  function manifestArtifactFile(manifest, key) {
    const entry = manifestArtifactEntry(manifest, key) || {};
    // Raw JSON is deliberately preferred here. The v2 artifacts are lazy and
    // compact, and this avoids making browser decompression support a release
    // requirement while retaining deterministic gzip delivery twins.
    return entry.file || entry.path || entry.gzipFile || entry.gzip_file || "";
  }

  function decodeCode(codes, key, value) {
    const table = codes && Array.isArray(codes[key]) ? codes[key] : [];
    return Number.isInteger(Number(value)) ? String(table[Number(value)] || "unknown") : String(value || "unknown");
  }

  function decodeFacilityRows(rowsValue, manifest) {
    const rows = Array.isArray(rowsValue) ? rowsValue : [];
    const codes = manifest && manifest.codes && manifest.codes.facilityAnalysis || {};
    return rows.map(function (row) {
      if (!Array.isArray(row)) return row;
      return {
        id: String(row[0] || ""),
        facilityClass: decodeCode(codes, "class", row[1]),
        name: String(row[2] || ""),
        lat: Number(row[3]),
        lon: Number(row[4]),
        coordinatePrecision: decodeCode(codes, "coordinatePrecision", row[5]),
        coordinateConfidence: decodeCode(codes, "coordinateConfidence", row[6]),
        uncertaintyKm: row[7] == null ? null : Number(row[7]),
        temporalConfidence: decodeCode(codes, "temporalConfidence", row[8]),
        activeIntervals: Array.isArray(row[9]) ? row[9] : [],
        status: decodeCode(codes, "status", row[10]),
        country: decodeCode(codes, "country", row[11]),
        provenance: decodeCode(codes, "provenance", row[12]),
        inferentialEligible: Boolean(row[13]),
        exclusionReasons: (Array.isArray(row[14]) ? row[14] : []).map(function (code) {
          return decodeCode(codes, "exclusionReason", code);
        }),
      };
    });
  }

  function decodeRelationshipRows(rowsValue, manifest) {
    const rows = Array.isArray(rowsValue) ? rowsValue : [];
    const codes = manifest && manifest.codes && manifest.codes.relationshipReconciliation || {};
    return rows.map(function (row) {
      if (!Array.isArray(row)) return row;
      return {
        relationshipId: String(row[0] || ""),
        subjectAnalysisId: String(row[1] || ""),
        objectDomain: decodeCode(codes, "objectDomain", row[2]),
        objectAnalysisId: String(row[3] || ""),
        assertionMode: decodeCode(codes, "assertionMode", row[4]),
        relationshipType: decodeCode(codes, "relationshipType", row[5]),
        reviewState: decodeCode(codes, "reviewState", row[6]),
        currentUfoEventId: row[7] == null ? null : String(row[7]),
        reconciliationStatus: decodeCode(codes, "reconciliationStatus", row[8]),
        associationEligible: Boolean(row[9]),
        sourceInputCount: Math.max(0, Number(row[10]) || 0),
        exclusionReasons: (Array.isArray(row[11]) ? row[11] : []).map(function (code) {
          return decodeCode(codes, "exclusionReason", code);
        }),
      };
    });
  }

  function relationshipReconciliationReadiness(manifest) {
    const rows = Array.isArray(analysisSpatialArtifacts.relationships)
      ? analysisSpatialArtifacts.relationships
      : [];
    const source = manifest && manifest.sources && manifest.sources.relationshipReconciliation || {};
    const sourceReadiness = source.readiness && typeof source.readiness === "object" ? source.readiness : {};
    const minimumEligibleN = Math.max(
      0,
      Number(sourceReadiness.minimumEligibleRecords) ||
        Number(manifest && manifest.policy && manifest.policy.minimumContextEligibleRecordsForInference) ||
        25
    );
    const counts = {
      explicitSourceN: 0,
      computedCandidateN: 0,
      analystReviewedN: 0,
      quarantinedSubjectN: 0,
      quarantinedObjectN: 0,
      reconciledN: 0,
      reconciledCurrentN: 0,
      reconciledUnmappedUfoN: 0,
      associationEligibleN: 0,
    };
    rows.forEach(function (rowValue) {
      const row = rowValue || {};
      const assertionMode = String(row.assertionMode || "").toLowerCase();
      const reviewState = String(row.reviewState || "").toLowerCase();
      const reconciliationStatus = String(row.reconciliationStatus || "").toLowerCase();
      if (assertionMode === "explicit_source") counts.explicitSourceN += 1;
      if (assertionMode === "deterministic_match" || assertionMode === "computed_candidate") {
        counts.computedCandidateN += 1;
      }
      if (reviewState === "analyst_reviewed" || reviewState === "analyst_adjudicated" || reviewState === "reviewed") {
        counts.analystReviewedN += 1;
      }
      if (reconciliationStatus === "quarantined_subject") counts.quarantinedSubjectN += 1;
      if (reconciliationStatus === "quarantined_object") counts.quarantinedObjectN += 1;
      if (reconciliationStatus === "reconciled_current") counts.reconciledCurrentN += 1;
      if (reconciliationStatus === "reconciled_unmapped_ufo") counts.reconciledUnmappedUfoN += 1;
      if (reconciliationStatus.indexOf("reconciled_") === 0) counts.reconciledN += 1;
      if (row.associationEligible) counts.associationEligibleN += 1;
    });
    const reasons = Array.isArray(sourceReadiness.reasons)
      ? sourceReadiness.reasons.map(String)
      : (counts.associationEligibleN < minimumEligibleN
        ? ["relationship_reconciliation_readiness_reasons_unavailable"]
        : []);
    return Object.assign({
      key: "relationshipReconciliation",
      label: "Cross-domain relationship reconciliation",
      status: String(sourceReadiness.status || (counts.associationEligibleN >= minimumEligibleN
        ? "exploratory_ready"
        : "not_estimable")),
      eligibleN: counts.associationEligibleN,
      totalN: rows.length,
      minimumEligibleN,
      inferenceEnabled: Boolean(
        source.policy && source.policy.associationInferenceEnabled &&
        counts.associationEligibleN >= minimumEligibleN
      ),
      reasons,
      releaseHash: String(
        manifest && manifest.artifacts && manifest.artifacts.relationshipReconciliation &&
        manifest.artifacts.relationshipReconciliation.sha256 || ""
      ),
    }, counts);
  }

  function spatialArtifactHashes(manifest) {
    const result = {};
    Object.keys(manifest && manifest.artifacts || {}).sort().forEach(function (key) {
      const entry = manifest.artifacts[key];
      result[key] = String(entry && entry.sha256 || "");
    });
    result.manifest = String(manifest && manifest.releaseId || "") + ":" + String(manifest && manifest.schemaVersion || "");
    return result;
  }

  function analysisSpatialSnapshot() {
    return {
      loaded: Boolean(analysisSpatialArtifacts.loaded),
      rowCounts: {
        neighbors: Array.isArray(analysisSpatialArtifacts.neighbors) ? analysisSpatialArtifacts.neighbors.length : 0,
        facilities: Array.isArray(analysisSpatialArtifacts.facilities) ? analysisSpatialArtifacts.facilities.length : 0,
        relationships: Array.isArray(analysisSpatialArtifacts.relationships) ? analysisSpatialArtifacts.relationships.length : 0,
      },
      releaseId: String(analysisSpatialArtifacts.manifest && analysisSpatialArtifacts.manifest.releaseId || ""),
      artifactHashes: Object.assign({}, analysisSpatialArtifacts.artifactHashes || {}),
      relationshipReadiness: relationshipReconciliationReadiness(analysisSpatialArtifacts.manifest || {}),
      estimatorVersion: analysisSpatialExecutor && analysisSpatialExecutor.estimatorVersion
        ? analysisSpatialExecutor.estimatorVersion
        : (analysisSpatialApi && analysisSpatialApi.ESTIMATOR_VERSION
          ? analysisSpatialApi.ESTIMATOR_VERSION
          : "ufo-analysis-spatial-v2"),
    };
  }

  function dedicatedSpatialWorkerSupported() {
    return typeof Worker === "function";
  }

  function dedicatedSpatialWorkerUrl() {
    try {
      return new URL("./analysis_spatial_worker.js", self.location && self.location.href || undefined).toString();
    } catch (_error) {
      return "./analysis_spatial_worker.js";
    }
  }

  function analysisComputedEnvelope(message, result, cacheHit) {
    return {
      type: "analysisComputed",
      requestId: message.requestId || "",
      analysisSignature: String(message.analysisSignature || ""),
      filterGeneration: analysisFilterGeneration(message),
      generation: analysisFilterGeneration(message),
      baselineMode: ensureAnalysisStats().normalizeBaselineMode(message.baselineMode),
      datasetHash: String(message.datasetHash || ""),
      contextReleaseHashes: normalizedHashObject(message.contextReleaseHashes),
      artifactHashes: Object.assign(
        {},
        normalizedHashObject(message.contextReleaseHashes),
        normalizedHashObject(message.artifactHashes),
        analysisSpatialArtifacts.artifactHashes || {}
      ),
      estimatorVersion: String(message.estimatorVersion || "ufo-analysis-v2"),
      analysisPhase: String(message.analysisPhase || (message.quickMode ? "quick" : "full")),
      quickMode: Boolean(message.quickMode),
      inferenceDeferred: Boolean(result && result.inferenceDeferred),
      cancellationGeneration: Number(message.cancellationGeneration) || 0,
      ordinalEpoch: "unix_day",
      cacheHit: Boolean(cacheHit),
      result,
    };
  }

  function postAnalysisWorkerError(message, errorValue, codeValue, cancelled) {
    const error = errorValue && errorValue.message ? errorValue.message : String(errorValue || "Spatial analysis failed.");
    self.postMessage({
      type: "analysisWorkerError",
      requestId: message && message.requestId || "",
      analysisSignature: String(message && message.analysisSignature || ""),
      filterGeneration: analysisFilterGeneration(message || {}),
      generation: analysisFilterGeneration(message || {}),
      baselineMode: ensureAnalysisStats().normalizeBaselineMode(message && message.baselineMode),
      datasetHash: String(message && message.datasetHash || ""),
      contextReleaseHashes: normalizedHashObject(message && message.contextReleaseHashes),
      artifactHashes: Object.assign({}, analysisSpatialArtifacts.artifactHashes || {}),
      estimatorVersion: String(message && message.estimatorVersion || "ufo-analysis-v2"),
      cancellationGeneration: Number(message && message.cancellationGeneration) || 0,
      errorCode: String(codeValue || "spatial_analysis_failed"),
      cancelled: Boolean(cancelled),
      error,
    });
  }

  function terminateDedicatedSpatialExecutor(reasonValue, notifyPending) {
    const reason = String(reasonValue || "Spatial analysis was cancelled.");
    const pending = analysisSpatialPending;
    analysisSpatialPending = null;
    if (pending && notifyPending) {
      postAnalysisWorkerError(pending.message, reason, "spatial_analysis_cancelled", true);
    }
    const executor = analysisSpatialExecutor;
    analysisSpatialExecutor = null;
    if (!executor) return;
    if (!executor.ready && typeof executor.rejectReady === "function") {
      executor.rejectReady(new Error(reason));
    }
    try {
      executor.worker.onmessage = null;
      executor.worker.onerror = null;
      executor.worker.terminate();
    } catch (_error) {
      // Termination is best-effort; epoch checks still reject a late response.
    }
  }

  function handleDedicatedSpatialMessage(executor, event) {
    if (!analysisSpatialExecutor || analysisSpatialExecutor.epoch !== executor.epoch) return;
    const message = event && event.data || {};
    if (message.type === "spatialAnalysisReady") {
      executor.ready = true;
      executor.estimatorVersion = String(message.estimatorVersion || "ufo-analysis-spatial-v2");
      const resolveReady = executor.resolveReady;
      executor.resolveReady = null;
      executor.rejectReady = null;
      if (typeof resolveReady === "function") resolveReady(executor);
      return;
    }
    const pending = analysisSpatialPending;
    if (!pending || pending.executorEpoch !== executor.epoch || message.jobId !== pending.jobId) return;
    if (Number(message.cancellationGeneration) !== Number(pending.cancellationGeneration) ||
        Number(pending.cancellationGeneration) !== Number(analysisSpatialCancellationGeneration)) {
      return;
    }
    analysisSpatialPending = null;
    if (message.type === "spatialAnalysisComputed") {
      const baselineMode = ensureAnalysisStats().normalizeBaselineMode(pending.message.baselineMode);
      pending.result.spatialEvidence = finalizeSpatialEvidenceResult(
        message.result,
        spatialReadinessFromManifest(analysisSpatialArtifacts.manifest || {}),
        baselineMode,
        baselineMode !== ensureAnalysisStats().BASELINE_MODES.FULL_CATALOG
      );
      cacheAnalysisResult(pending.cacheKey, pending.result);
      self.postMessage(analysisComputedEnvelope(pending.message, pending.result, false));
      return;
    }
    postAnalysisWorkerError(
      pending.message,
      message.error || "Spatial analysis failed.",
      message.errorCode || "spatial_analysis_failed",
      false
    );
  }

  function handleDedicatedSpatialError(executor, errorValue) {
    if (!analysisSpatialExecutor || analysisSpatialExecutor.epoch !== executor.epoch) return;
    const error = errorValue && (errorValue.error || errorValue.message)
      ? (errorValue.error || new Error(errorValue.message))
      : new Error("The spatial analysis worker failed.");
    if (!executor.ready && typeof executor.rejectReady === "function") {
      const rejectReady = executor.rejectReady;
      executor.resolveReady = null;
      executor.rejectReady = null;
      rejectReady(error);
    }
    const pending = analysisSpatialPending;
    analysisSpatialPending = null;
    if (pending) postAnalysisWorkerError(pending.message, error, "spatial_worker_failed", false);
    try { executor.worker.terminate(); } catch (_error) { /* no-op */ }
    analysisSpatialExecutor = null;
  }

  function initializeDedicatedSpatialExecutor() {
    if (!dedicatedSpatialWorkerSupported()) return Promise.resolve(null);
    if (analysisSpatialExecutor) return analysisSpatialExecutor.readyPromise;
    const epoch = ++analysisSpatialExecutorEpoch;
    let worker;
    try {
      worker = new Worker(dedicatedSpatialWorkerUrl());
    } catch (error) {
      return Promise.reject(error);
    }
    const executor = {
      epoch,
      worker,
      ready: false,
      estimatorVersion: "",
      resolveReady: null,
      rejectReady: null,
      readyPromise: null,
    };
    executor.readyPromise = new Promise(function (resolve, reject) {
      executor.resolveReady = resolve;
      executor.rejectReady = reject;
    });
    analysisSpatialExecutor = executor;
    worker.onmessage = function (event) { handleDedicatedSpatialMessage(executor, event); };
    worker.onerror = function (event) { handleDedicatedSpatialError(executor, event); };
    worker.postMessage({
      type: "initializeSpatialAnalysis",
      executionEpoch: epoch,
      edges: analysisSpatialArtifacts.neighbors || [],
      facilities: analysisSpatialArtifacts.facilities || [],
      readiness: spatialReadinessFromManifest(analysisSpatialArtifacts.manifest || {}),
      artifactHashes: Object.assign({}, analysisSpatialArtifacts.artifactHashes || {}),
    });
    return executor.readyPromise;
  }

  function spatialExecutionPayload(message) {
    const stats = ensureAnalysisStats();
    const baselineMode = stats.normalizeBaselineMode(message.baselineMode);
    const inferenceEnabled = baselineMode !== stats.BASELINE_MODES.FULL_CATALOG;
    const filters = normalizedFilters(message || {});
    const keywordIds = keywordIdSet(message || {});
    const areaEventIds = Array.isArray(message.areaFilterEventIds)
      ? new Set(message.areaFilterEventIds.map(String))
      : null;
    const areaShapes = Array.isArray(message.areaFilterShapes) && message.areaFilterShapes.length
      ? message.areaFilterShapes
      : null;
    const lowPrecisionValues = Array.isArray(message.lowPrecisionValues)
      ? new Set(message.lowPrecisionValues)
      : new Set();
    const matched = baselineMode !== stats.BASELINE_MODES.FULL_CATALOG
      ? matchedAnalysisRows(message, filters, keywordIds, areaEventIds, areaShapes, lowPrecisionValues)
      : null;
    return {
      rows: activeSpatialRows(message, matched, filters, keywordIds, areaEventIds, areaShapes, lowPrecisionValues),
      seed: String(message.datasetHash || "catalog") + "|" + analysisFilterGeneration(message),
      baselineMode,
      inferenceEnabled,
      permutationCount: message.spatialPermutationCount,
      bootstrapCount: message.spatialBootstrapCount,
      minimumStratumSize: message.spatialMinimumStratumSize,
    };
  }

  function dispatchDedicatedSpatialAnalysis(message, result, cacheKey) {
    if (analysisSpatialPending) {
      terminateDedicatedSpatialExecutor("Spatial analysis was superseded by a newer request.", true);
    }
    const jobId = "spatial-" + analysisFilterGeneration(message) + "-" +
      (Number(message.cancellationGeneration) || 0) + "-" + String(message.requestId || "");
    const pending = {
      jobId,
      message,
      result,
      cacheKey,
      cancellationGeneration: Number(message.cancellationGeneration) || 0,
      executorEpoch: 0,
    };
    analysisSpatialPending = pending;
    initializeDedicatedSpatialExecutor().then(function (executor) {
      if (!executor || analysisSpatialPending !== pending ||
          pending.cancellationGeneration !== analysisSpatialCancellationGeneration) return;
      pending.executorEpoch = executor.epoch;
      executor.worker.postMessage(Object.assign({
        type: "computeSpatialAnalysis",
        jobId,
        cancellationGeneration: pending.cancellationGeneration,
      }, spatialExecutionPayload(message)));
    }).catch(function (error) {
      if (analysisSpatialPending !== pending) return;
      analysisSpatialPending = null;
      postAnalysisWorkerError(message, error, "spatial_worker_initialization_failed", false);
    });
  }

  function advanceSpatialCancellationGeneration(message) {
    const generation = Number(message.cancellationGeneration) || 0;
    if (generation < analysisSpatialCancellationGeneration) {
      postAnalysisWorkerError(
        message,
        "Spatial analysis request is stale and was not executed.",
        "stale_spatial_request",
        true
      );
      return false;
    }
    if (generation > analysisSpatialCancellationGeneration) {
      analysisSpatialCancellationGeneration = generation;
      if (analysisSpatialPending && analysisSpatialPending.cancellationGeneration < generation) {
        terminateDedicatedSpatialExecutor("Spatial analysis was superseded by a newer filter generation.", true);
      }
    }
    return true;
  }

  async function loadAnalysisSpatialArtifacts(message) {
    const urls = message.urls && typeof message.urls === "object" ? message.urls : {};
    const manifestUrl = String(urls.manifest || "./data/analysis_v2/manifest.json");
    const manifest = message.manifest && typeof message.manifest === "object"
      ? message.manifest
      : await fetchAnalysisJson(manifestUrl, { sha256: message.manifestSha256 || "" });
    if (!manifest || Number(manifest.schemaVersion) !== 2 || !manifest.artifacts) {
      throw new Error("Analysis v2 spatial manifest is invalid or unsupported.");
    }
    const neighborUrl = urls.neighbors || resolveAnalysisUrl(
      manifestArtifactFile(manifest, "ufoPointNeighbors"),
      manifestUrl
    );
    const facilityUrl = urls.facilities || resolveAnalysisUrl(
      manifestArtifactFile(manifest, "facilityAnalysis"),
      manifestUrl
    );
    const relationshipUrl = urls.relationshipReconciliation || urls.relationships || resolveAnalysisUrl(
      manifestArtifactFile(manifest, "relationshipReconciliation"),
      manifestUrl
    );
    const loaded = await Promise.all([
      fetchAnalysisJson(neighborUrl, manifestArtifactIntegrity(manifest, "ufoPointNeighbors")),
      fetchAnalysisJson(facilityUrl, manifestArtifactIntegrity(manifest, "facilityAnalysis")),
      relationshipUrl
        ? fetchAnalysisJson(relationshipUrl, manifestArtifactIntegrity(manifest, "relationshipReconciliation"))
        : Promise.resolve([]),
    ]);
    analysisSpatialArtifacts = {
      manifest,
      neighbors: Array.isArray(loaded[0]) ? loaded[0] : [],
      facilities: decodeFacilityRows(loaded[1], manifest),
      relationships: decodeRelationshipRows(loaded[2], manifest),
      loaded: true,
      artifactHashes: spatialArtifactHashes(manifest),
    };
    analysisCache.clear();
    terminateDedicatedSpatialExecutor("Spatial evidence artifacts were replaced.", true);
    if (dedicatedSpatialWorkerSupported()) await initializeDedicatedSpatialExecutor();
    return analysisSpatialSnapshot();
  }

  function manifestDomainEntry(manifest, domain) {
    const aliases = domain === "cropCircles" ? ["cropCircles", "crop_circles", "crops"] : ["animalReports", "animal_reports", "animals"];
    const containers = [manifest && manifest.artifacts, manifest && manifest.files, manifest && manifest.projections, manifest && manifest.domains, manifest];
    for (const container of containers) {
      const found = firstProjectionValue(container, aliases);
      if (found.present) return found.value;
    }
    return null;
  }

  function manifestDomainFile(manifest, domain) {
    const entry = manifestDomainEntry(manifest, domain);
    if (typeof entry === "string") return entry;
    if (entry && typeof entry === "object") {
      return entry.gzipFile || entry.gzip_file || entry.gzip || entry.gzipPath || entry.gzip_path || entry.path || entry.url || entry.file || "";
    }
    return "";
  }

  function manifestDomainIntegrity(manifest, domain) {
    const entry = manifestDomainEntry(manifest, domain);
    if (!entry || typeof entry !== "object") return {};
    return {
      sha256: entry.sha256 || entry.rawSha256 || entry.raw_sha256 || (entry.raw && entry.raw.sha256) || "",
      gzipSha256: entry.gzipSha256 || entry.gzip_sha256 || (entry.gzip && entry.gzip.sha256) || "",
    };
  }

  function resolveAnalysisUrl(candidate, manifestUrl) {
    if (!candidate) return "";
    try {
      const workerLocation = self.location && self.location.href ? self.location.href : undefined;
      const candidateText = String(candidate);
      const base = candidateText.indexOf("data/") === 0
        ? new URL("./", workerLocation)
        : new URL(String(manifestUrl || ""), workerLocation);
      return new URL(candidateText, base).toString();
    } catch (_error) {
      return String(candidate);
    }
  }

  async function loadAnalysisContextUrls(message) {
    const urls = message.urls && typeof message.urls === "object" ? message.urls : {};
    const manifest = message.manifest && typeof message.manifest === "object"
      ? message.manifest
      : (urls.manifest ? await fetchAnalysisJson(urls.manifest, {
        sha256: message.contextReleaseHashes && message.contextReleaseHashes.manifest,
      }) : analysisContext.manifest);
    const cropUrl = urls.cropCircles || urls.crops || urls.crop_circles ||
      resolveAnalysisUrl(manifestDomainFile(manifest, "cropCircles"), urls.manifest);
    const animalUrl = urls.animalReports || urls.animals || urls.animal_reports ||
      resolveAnalysisUrl(manifestDomainFile(manifest, "animalReports"), urls.manifest);
    const projections = {};
    const loads = [];
    if (cropUrl) {
      loads.push(fetchAnalysisJson(cropUrl, manifestDomainIntegrity(manifest, "cropCircles")).then(function (value) {
        projections.cropCircles = value;
      }));
    }
    if (animalUrl) {
      loads.push(fetchAnalysisJson(animalUrl, manifestDomainIntegrity(manifest, "animalReports")).then(function (value) {
        projections.animalReports = value;
      }));
    }
    await Promise.all(loads);
    return mergeAnalysisContextProjections(projections, manifest);
  }

  function postAnalysisContextSet(message, snapshot) {
    self.postMessage({
      type: "analysisContextProjectionsSet",
      requestId: message.requestId || "",
      filterGeneration: analysisFilterGeneration(message),
      generation: analysisFilterGeneration(message),
      contextReleaseHashes: normalizedHashObject(message.contextReleaseHashes),
      rowCounts: snapshot.rowCounts,
      storage: snapshot.storage,
    });
  }

  function storageSnapshot() {
    return {
      mode: "typed_column_chunks",
      chunks: chunks.length,
      rows: rowCount,
      typedBytes: typedStorageBytes,
      analysisDerivedColumns: true,
      analysisMatchCacheEntries: analysisMatchCache.size,
      stringEventIds: Math.max(0, eventIdStrings.values.length - 1),
      analysisGridKeys: Math.max(0, analysisGridKeys.values.length - 1),
      analysisCoordinatePiles: Math.max(0, analysisCoordinatePileKeys.values.length - 1),
      dictionaries: {
        source: dictionaries.source.values.length,
        type: dictionaries.type.values.length,
        visualTypeGroup: dictionaries.visualTypeGroup.values.length,
        craftType: dictionaries.craftType.values.length,
        shape: dictionaries.shape.values.length,
        craftConfidence: dictionaries.craftConfidence.values.length,
        craftSource: dictionaries.craftSource.values.length,
        sameDayMatchStrength: dictionaries.sameDayMatchStrength.values.length,
        precision: dictionaries.precision.values.length,
        datePrecision: dictionaries.datePrecision.values.length,
        coordinateSource: dictionaries.coordinateSource.values.length,
        country: dictionaries.country.values.length,
        adminRegion: dictionaries.adminRegion.values.length,
        duplicateLineage: dictionaries.duplicateLineage.values.length,
      },
    };
  }

  function resetRows() {
    chunks = [];
    rowCount = 0;
    typedStorageBytes = 0;
    dictionaries = createDictionaries();
    eventIdStrings = createDictionary();
    analysisGridKeys = createDictionary();
    analysisCoordinatePileKeys = createDictionary();
    analysisCoordinatePileCounts = new Map();
    analysisCache.clear();
    analysisMatchCache.clear();
  }

  self.onmessage = function (event) {
    const message = event.data || {};
    try {
      if (message.type === "resetCatalogFacetRows") {
        terminateDedicatedSpatialExecutor("Catalog rows were reset during spatial analysis.", true);
        resetRows();
        self.postMessage({
          type: "catalogFacetRowsReset",
          requestId: message.requestId || "",
          generation: Number(message.generation) || 0,
          rowCount,
          storage: storageSnapshot(),
        });
        return;
      }
      if (message.type === "addCatalogFacetRows") {
        const nextRows = Array.isArray(message.rows) ? message.rows : [];
        if (nextRows.length) {
          terminateDedicatedSpatialExecutor("Catalog rows changed during spatial analysis.", true);
          chunks.push(compactRows(nextRows));
          rowCount += nextRows.length;
          analysisCache.clear();
          analysisMatchCache.clear();
        }
        self.postMessage({
          type: "catalogFacetRowsAdded",
          requestId: message.requestId || "",
          generation: Number(message.generation) || 0,
          rowCount,
          storage: storageSnapshot(),
        });
        return;
      }
      if (message.type === "setAnalysisContextProjections") {
        const directSnapshot = message.projections && typeof message.projections === "object"
          ? mergeAnalysisContextProjections(message.projections, message.manifest)
          : null;
        if (message.urls && typeof message.urls === "object" && Object.keys(message.urls).length) {
          loadAnalysisContextUrls(message).then(function (snapshot) {
            postAnalysisContextSet(message, snapshot);
          }).catch(function (error) {
            self.postMessage({
              type: "catalogFacetWorkerError",
              requestId: message.requestId || "",
              filterGeneration: analysisFilterGeneration(message),
              generation: analysisFilterGeneration(message),
              baselineMode: ensureAnalysisStats().normalizeBaselineMode(message.baselineMode),
              contextReleaseHashes: normalizedHashObject(message.contextReleaseHashes),
              error: error && error.message ? error.message : String(error),
            });
          });
        } else {
          postAnalysisContextSet(message, directSnapshot || mergeAnalysisContextProjections({}, message.manifest));
        }
        return;
      }
      if (message.type === "setAnalysisSpatialArtifacts") {
        loadAnalysisSpatialArtifacts(message).then(function (snapshot) {
          self.postMessage({
            type: "analysisSpatialArtifactsSet",
            requestId: message.requestId || "",
            filterGeneration: analysisFilterGeneration(message),
            generation: analysisFilterGeneration(message),
            cancellationGeneration: Number(message.cancellationGeneration) || 0,
            snapshot,
          });
        }).catch(function (error) {
          self.postMessage({
            type: "catalogFacetWorkerError",
            requestId: message.requestId || "",
            filterGeneration: analysisFilterGeneration(message),
            generation: analysisFilterGeneration(message),
            cancellationGeneration: Number(message.cancellationGeneration) || 0,
            error: error && error.message ? error.message : String(error),
          });
        });
        return;
      }
      if (message.type === "computeAnalysis") {
        if (!advanceSpatialCancellationGeneration(message)) return;
        const cacheKey = analysisCacheKey(message);
        const cacheHit = analysisCache.has(cacheKey);
        if (cacheHit) {
          self.postMessage(analysisComputedEnvelope(message, analysisCache.get(cacheKey), true));
          return;
        }
        const selectedDomains = normalizedAnalysisDomains(message.selectedDomains);
        const requestsSpatial = selectedDomains.indexOf("spatial") !== -1 ||
          selectedDomains.indexOf("spatial_evidence") !== -1;
        if (requestsSpatial && analysisSpatialArtifacts.loaded && dedicatedSpatialWorkerSupported()) {
          const coreResult = computeAnalysisResult(message, { deferSpatial: true });
          dispatchDedicatedSpatialAnalysis(message, coreResult, cacheKey);
          return;
        }
        const result = computeAnalysisResult(message);
        cacheAnalysisResult(cacheKey, result);
        self.postMessage(analysisComputedEnvelope(message, result, false));
        return;
      }
      if (message.type === "computeCatalogFacetCounts") {
        self.postMessage({
          type: "catalogFacetCountsComputed",
          requestId: message.requestId || "",
          generation: Number(message.generation) || 0,
          result: computeFacetCounts(message),
        });
        return;
      }
      if (message.type === "computeFilteredCatalogIds") {
        self.postMessage({
          type: "filteredCatalogIdsComputed",
          requestId: message.requestId || "",
          generation: Number(message.generation) || 0,
          result: computeFilteredCatalogIds(message),
        });
      }
    } catch (error) {
      self.postMessage({
        type: "catalogFacetWorkerError",
        requestId: message.requestId || "",
        generation: Number(message.generation) || 0,
        filterGeneration: analysisFilterGeneration(message),
        baselineMode: message.type === "computeAnalysis" || message.type === "setAnalysisContextProjections"
          ? (analysisStatsApi && analysisStatsApi.normalizeBaselineMode
            ? analysisStatsApi.normalizeBaselineMode(message.baselineMode)
            : String(message.baselineMode || "other_dates_balanced"))
          : undefined,
        contextReleaseHashes: normalizedHashObject(message.contextReleaseHashes),
        error: error && error.message ? error.message : String(error),
      });
    }
  };
})();

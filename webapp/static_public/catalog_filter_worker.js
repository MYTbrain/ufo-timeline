(function () {
  "use strict";

  const MISSING_SORT_ORDINAL = -2147483648;
  const MISSING_ANALYSIS_INDEX = 255;
  const PYTHON_ORDINAL_UNIX_EPOCH = 719163;
  const ANALYSIS_CACHE_LIMIT = 12;
  const ANALYSIS_RUNTIME_CACHE_KEY = "2026-08-05-analysis-color-v1-ui1";
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
    spatialPoints: null,
    configurationPoints: null,
    configurationNeighbors: null,
    contextNeighbors: null,
    facilities: null,
    relationshipRows: null,
    relationships: null,
    codebooks: {},
    loaded: false,
    artifactHashes: {},
  };
  let analysisGeographyArtifact = {
    manifest: null,
    rows: null,
    codes: {},
    loaded: false,
    appliedRows: 0,
    artifactHash: "",
  };
  let analysisDurationArtifact = {
    manifest: null,
    loaded: false,
    appliedRows: 0,
    normalizedRows: 0,
    artifactHashes: {},
    releaseId: "",
  };
  let analysisReportingDelayArtifact = {
    manifest: null,
    loaded: false,
    appliedRows: 0,
    typedRows: 0,
    artifactHashes: {},
    releaseId: "",
  };
  let analysisTimeOfDayArtifact = {
    manifest: null,
    loaded: false,
    appliedRows: 0,
    typedRows: 0,
    artifactHashes: {},
    releaseId: "",
  };
  let analysisWitnessCountArtifact = {
    manifest: null,
    loaded: false,
    appliedRows: 0,
    typedRows: 0,
    artifactHashes: {},
    releaseId: "",
  };
  let analysisColorArtifact = {
    manifest: null,
    loaded: false,
    appliedRows: 0,
    normalizedRows: 0,
    artifactHashes: {},
    releaseId: "",
  };
  let analysisCoordinateEvidenceArtifact = {
    manifest: null,
    loaded: false,
    appliedRows: 0,
    typedRows: 0,
    artifactHashes: {},
    releaseId: "",
  };
  let analysisSpatialExecutor = null;
  let analysisSpatialExecutorEpoch = 0;
  let analysisSpatialPending = null;
  let analysisSpatialCancellationGeneration = 0;
  let analysisSpatialArtifactLoadEpoch = 0;
  let analysisPartialArtifactLoadEpoch = { relationship: 0, context: 0 };
  let analysisFullSpatialLoadsInFlight = 0;

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
      analysisCountry: createDictionary(),
      analysisMacroregion: createDictionary(),
      durationMacroregion: createDictionary(),
      reportingDelayMacroregion: createDictionary(),
      timeOfDayMacroregion: createDictionary(),
      witnessCountMacroregion: createDictionary(),
      colorMacroregion: createDictionary(),
      coordinateEvidenceMacroregion: createDictionary(),
      geographyAssignmentSource: createDictionary(),
      geographyAssignmentConfidence: createDictionary(),
      geographyBoundaryStatus: createDictionary(),
      duplicateLineage: createDictionary(),
    };
  }

  function ensureAnalysisStats() {
    if (analysisStatsApi && typeof analysisStatsApi.computeAnalysis === "function") return analysisStatsApi;
    if (typeof importScripts === "function") {
      importScripts("./analysis_stats.js?v=" + ANALYSIS_RUNTIME_CACHE_KEY);
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
      importScripts("./analysis_spatial.js?v=" + ANALYSIS_RUNTIME_CACHE_KEY);
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
      analysisCountryCodes: new Uint16Array(length),
      analysisMacroregionCodes: new Uint16Array(length),
      analysisGeographyAssignmentSourceCodes: new Uint16Array(length),
      analysisGeographyAssignmentConfidenceCodes: new Uint16Array(length),
      analysisGeographyBoundaryStatusCodes: new Uint16Array(length),
      analysisDurationValueCodes: new Uint32Array(length),
      analysisDurationStatusCodes: new Uint8Array(length),
      analysisDurationDescriptiveBinCodes: new Uint8Array(length),
      analysisDurationInferentialBinCodes: new Uint8Array(length),
      analysisDurationMacroregionCodes: new Uint16Array(length),
      analysisDurationLowerSeconds: new Float64Array(length),
      analysisDurationUpperSeconds: new Float64Array(length),
      analysisReportingDelayProjectionStates: new Uint8Array(length),
      analysisReportingDelayStatusCodes: new Uint8Array(length),
      analysisReportingDelayRoleCodes: new Uint8Array(length),
      analysisReportingDelayBinCodes: new Uint8Array(length),
      analysisReportingDelayMacroregionCodes: new Uint16Array(length),
      analysisReportingDelayDays: new Uint32Array(length),
      analysisTimeOfDayValueCodes: new Uint16Array(length),
      analysisTimeOfDayStatusCodes: new Uint8Array(length),
      analysisTimeOfDayDescriptiveBinCodes: new Uint8Array(length),
      analysisTimeOfDayInferentialBinCodes: new Uint8Array(length),
      analysisTimeOfDayMacroregionCodes: new Uint16Array(length),
      analysisTimeOfDayLowerMinutes: new Uint16Array(length),
      analysisTimeOfDayUpperMinutes: new Uint16Array(length),
      analysisWitnessCountValueCodes: new Uint16Array(length),
      analysisWitnessCountStatusCodes: new Uint8Array(length),
      analysisWitnessCountBinCodes: new Uint8Array(length),
      analysisWitnessCountMacroregionCodes: new Uint16Array(length),
      analysisWitnessCountExactCounts: new Uint32Array(length),
      analysisColorValueCodes: new Uint16Array(length),
      analysisColorStatusCodes: new Uint8Array(length),
      analysisColorRoleCodes: new Uint8Array(length),
      analysisColorCategoryMasks: new Uint16Array(length),
      analysisColorFlags: new Uint8Array(length),
      analysisColorMacroregionCodes: new Uint16Array(length),
      analysisCoordinateEvidenceProjectionStates: new Uint8Array(length),
      analysisCoordinateEvidenceStatusCodes: new Uint8Array(length),
      analysisCoordinateEvidenceConsistencyCodes: new Uint8Array(length),
      analysisCoordinateEvidenceQualityBinCodes: new Uint8Array(length),
      analysisCoordinateEvidenceRiskFlags: new Uint8Array(length),
      analysisCoordinateEvidenceMacroregionCodes: new Uint16Array(length),
    };
    chunk.analysisDurationLowerSeconds.fill(Number.NaN);
    chunk.analysisDurationUpperSeconds.fill(Number.NaN);
    chunk.analysisTimeOfDayLowerMinutes.fill(65535);
    chunk.analysisTimeOfDayUpperMinutes.fill(65535);

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
    typedStorageBytes +=
      chunk.analysisCountryCodes.byteLength +
      chunk.analysisMacroregionCodes.byteLength +
      chunk.analysisGeographyAssignmentSourceCodes.byteLength +
      chunk.analysisGeographyAssignmentConfidenceCodes.byteLength +
      chunk.analysisGeographyBoundaryStatusCodes.byteLength +
      chunk.analysisDurationValueCodes.byteLength +
      chunk.analysisDurationStatusCodes.byteLength +
      chunk.analysisDurationDescriptiveBinCodes.byteLength +
      chunk.analysisDurationInferentialBinCodes.byteLength +
      chunk.analysisDurationMacroregionCodes.byteLength +
      chunk.analysisDurationLowerSeconds.byteLength +
      chunk.analysisDurationUpperSeconds.byteLength;
    typedStorageBytes += chunk.analysisReportingDelayProjectionStates.byteLength +
      chunk.analysisReportingDelayStatusCodes.byteLength +
      chunk.analysisReportingDelayRoleCodes.byteLength +
      chunk.analysisReportingDelayBinCodes.byteLength +
      chunk.analysisReportingDelayMacroregionCodes.byteLength +
      chunk.analysisReportingDelayDays.byteLength;
    typedStorageBytes += chunk.analysisTimeOfDayValueCodes.byteLength +
      chunk.analysisTimeOfDayStatusCodes.byteLength +
      chunk.analysisTimeOfDayDescriptiveBinCodes.byteLength +
      chunk.analysisTimeOfDayInferentialBinCodes.byteLength +
      chunk.analysisTimeOfDayMacroregionCodes.byteLength +
      chunk.analysisTimeOfDayLowerMinutes.byteLength +
      chunk.analysisTimeOfDayUpperMinutes.byteLength;
    typedStorageBytes += chunk.analysisWitnessCountValueCodes.byteLength +
      chunk.analysisWitnessCountStatusCodes.byteLength +
      chunk.analysisWitnessCountBinCodes.byteLength +
      chunk.analysisWitnessCountMacroregionCodes.byteLength +
      chunk.analysisWitnessCountExactCounts.byteLength;
    typedStorageBytes += chunk.analysisColorValueCodes.byteLength +
      chunk.analysisColorStatusCodes.byteLength +
      chunk.analysisColorRoleCodes.byteLength +
      chunk.analysisColorCategoryMasks.byteLength +
      chunk.analysisColorFlags.byteLength +
      chunk.analysisColorMacroregionCodes.byteLength;
    typedStorageBytes += chunk.analysisCoordinateEvidenceProjectionStates.byteLength +
      chunk.analysisCoordinateEvidenceStatusCodes.byteLength +
      chunk.analysisCoordinateEvidenceConsistencyCodes.byteLength +
      chunk.analysisCoordinateEvidenceQualityBinCodes.byteLength +
      chunk.analysisCoordinateEvidenceRiskFlags.byteLength +
      chunk.analysisCoordinateEvidenceMacroregionCodes.byteLength;
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
    values.country = dictionaryValue(
      dictionaries.analysisCountry,
      chunk.analysisCountryCodes && chunk.analysisCountryCodes[index]
        ? chunk.analysisCountryCodes[index]
        : chunk.countryCodes[index]
    ) || dictionaryValue(dictionaries.country, chunk.countryCodes[index]) || "unknown";
    values.adminRegion = dictionaryValue(dictionaries.adminRegion, chunk.adminRegionCodes[index]) || "unknown";
    values.analysisCountry = values.country;
    values.analysisMacroregion = dictionaryValue(
      dictionaries.analysisMacroregion,
      chunk.analysisMacroregionCodes && chunk.analysisMacroregionCodes[index]
    ) || "unknown";
    values.analysisGeographyAssignmentSource = dictionaryValue(
      dictionaries.geographyAssignmentSource,
      chunk.analysisGeographyAssignmentSourceCodes && chunk.analysisGeographyAssignmentSourceCodes[index]
    ) || "unavailable";
    values.analysisGeographyAssignmentConfidence = dictionaryValue(
      dictionaries.geographyAssignmentConfidence,
      chunk.analysisGeographyAssignmentConfidenceCodes && chunk.analysisGeographyAssignmentConfidenceCodes[index]
    ) || "unavailable";
    values.analysisGeographyBoundaryStatus = dictionaryValue(
      dictionaries.geographyBoundaryStatus,
      chunk.analysisGeographyBoundaryStatusCodes && chunk.analysisGeographyBoundaryStatusCodes[index]
    ) || "unavailable";
    const durationValueCode = chunk.analysisDurationValueCodes && chunk.analysisDurationValueCodes[index];
    values.analysisDurationAvailable = Boolean(durationValueCode);
    values.analysisDurationValueCode = durationValueCode ? durationValueCode - 1 : null;
    values.analysisDurationStatus = durationValueCode
      ? String((analysisDurationArtifact.manifest.codes.status || [])[chunk.analysisDurationStatusCodes[index] - 1] || "unparsed")
      : "unavailable";
    values.analysisDurationDescriptiveBin = durationValueCode
      ? String((analysisDurationArtifact.manifest.codes.durationBin || [])[chunk.analysisDurationDescriptiveBinCodes[index] - 1] || "unknown")
      : "unknown";
    values.analysisDurationInferentialBin = durationValueCode
      ? String((analysisDurationArtifact.manifest.codes.durationBin || [])[chunk.analysisDurationInferentialBinCodes[index] - 1] || "unknown")
      : "unknown";
    values.analysisDurationMacroregion = durationValueCode
      ? dictionaryValue(dictionaries.durationMacroregion, chunk.analysisDurationMacroregionCodes[index]) || "unknown"
      : "unknown";
    values.analysisDurationLowerSeconds = durationValueCode && Number.isFinite(chunk.analysisDurationLowerSeconds[index])
      ? chunk.analysisDurationLowerSeconds[index]
      : null;
    values.analysisDurationUpperSeconds = durationValueCode && Number.isFinite(chunk.analysisDurationUpperSeconds[index])
      ? chunk.analysisDurationUpperSeconds[index]
      : null;
    const reportingDelayProjected = Boolean(
      chunk.analysisReportingDelayProjectionStates && chunk.analysisReportingDelayProjectionStates[index]
    );
    values.analysisReportingDelayAvailable = reportingDelayProjected;
    values.analysisReportingDelayStatus = reportingDelayProjected
      ? String((analysisReportingDelayArtifact.manifest.codes.status || [])[chunk.analysisReportingDelayStatusCodes[index] - 1] || "unavailable")
      : "unavailable";
    values.analysisReportingDelaySelectedRole = reportingDelayProjected
      ? String((analysisReportingDelayArtifact.manifest.codes.selectedRole || [])[chunk.analysisReportingDelayRoleCodes[index] - 1] || "none")
      : "none";
    values.analysisReportingDelayBin = reportingDelayProjected
      ? String((analysisReportingDelayArtifact.manifest.codes.delayBin || [])[chunk.analysisReportingDelayBinCodes[index] - 1] || "unknown")
      : "unknown";
    values.analysisReportingDelayMacroregion = reportingDelayProjected
      ? dictionaryValue(dictionaries.reportingDelayMacroregion, chunk.analysisReportingDelayMacroregionCodes[index]) || "unknown"
      : "unknown";
    values.analysisReportingDelayDays = reportingDelayProjected && ["reported_valid", "posted_fallback_valid"].indexOf(values.analysisReportingDelayStatus) !== -1
      ? chunk.analysisReportingDelayDays[index]
      : null;
    const timeOfDayValueCode = chunk.analysisTimeOfDayValueCodes && chunk.analysisTimeOfDayValueCodes[index];
    values.analysisTimeOfDayAvailable = Boolean(timeOfDayValueCode);
    values.analysisTimeOfDayStatus = timeOfDayValueCode
      ? String((analysisTimeOfDayArtifact.manifest.codes.status || [])[chunk.analysisTimeOfDayStatusCodes[index] - 1] || "unparsed")
      : "unavailable";
    values.analysisTimeOfDayDescriptiveBin = timeOfDayValueCode
      ? String((analysisTimeOfDayArtifact.manifest.codes.timeBin || [])[chunk.analysisTimeOfDayDescriptiveBinCodes[index] - 1] || "unknown")
      : "unknown";
    values.analysisTimeOfDayInferentialBin = timeOfDayValueCode
      ? String((analysisTimeOfDayArtifact.manifest.codes.timeBin || [])[chunk.analysisTimeOfDayInferentialBinCodes[index] - 1] || "unknown")
      : "unknown";
    values.analysisTimeOfDayMacroregion = timeOfDayValueCode
      ? dictionaryValue(dictionaries.timeOfDayMacroregion, chunk.analysisTimeOfDayMacroregionCodes[index]) || "unknown"
      : "unknown";
    values.analysisTimeOfDayLowerMinute = timeOfDayValueCode && chunk.analysisTimeOfDayLowerMinutes[index] !== 65535
      ? chunk.analysisTimeOfDayLowerMinutes[index]
      : null;
    values.analysisTimeOfDayUpperMinute = timeOfDayValueCode && chunk.analysisTimeOfDayUpperMinutes[index] !== 65535
      ? chunk.analysisTimeOfDayUpperMinutes[index]
      : null;
    const witnessCountValueCode = chunk.analysisWitnessCountValueCodes && chunk.analysisWitnessCountValueCodes[index];
    values.analysisWitnessCountAvailable = Boolean(witnessCountValueCode);
    values.analysisWitnessCountStatus = witnessCountValueCode
      ? String((analysisWitnessCountArtifact.manifest.codes.status || [])[chunk.analysisWitnessCountStatusCodes[index] - 1] || "unresolved_text")
      : "unavailable";
    values.analysisWitnessCountBin = witnessCountValueCode
      ? String((analysisWitnessCountArtifact.manifest.codes.witnessCountBin || [])[chunk.analysisWitnessCountBinCodes[index] - 1] || "unknown")
      : "unknown";
    values.analysisWitnessCountMacroregion = witnessCountValueCode
      ? dictionaryValue(dictionaries.witnessCountMacroregion, chunk.analysisWitnessCountMacroregionCodes[index]) || "unknown"
      : "unknown";
    values.analysisWitnessCountExactCount = witnessCountValueCode && values.analysisWitnessCountStatus === "exact_count"
      ? chunk.analysisWitnessCountExactCounts[index]
      : null;
    const colorValueCode = chunk.analysisColorValueCodes && chunk.analysisColorValueCodes[index];
    values.analysisColorAvailable = Boolean(colorValueCode);
    values.analysisColorStatus = colorValueCode
      ? String((analysisColorArtifact.manifest.codes.status || [])[chunk.analysisColorStatusCodes[index] - 1] || "unparsed")
      : "unavailable";
    values.analysisColorRole = colorValueCode
      ? String((analysisColorArtifact.manifest.codes.role || [])[chunk.analysisColorRoleCodes[index] - 1] || "role_unspecified")
      : "role_unspecified";
    values.analysisColorCategoryMask = colorValueCode ? chunk.analysisColorCategoryMasks[index] : 0;
    values.analysisColorChanging = Boolean(colorValueCode && (chunk.analysisColorFlags[index] & 1));
    values.analysisColorMulticolor = Boolean(colorValueCode && (chunk.analysisColorFlags[index] & 2));
    values.analysisColorCompound = Boolean(colorValueCode && (chunk.analysisColorFlags[index] & 4));
    values.analysisColorMacroregion = colorValueCode
      ? dictionaryValue(dictionaries.colorMacroregion, chunk.analysisColorMacroregionCodes[index]) || "unknown"
      : "unknown";
    const coordinateEvidenceProjected = Boolean(
      chunk.analysisCoordinateEvidenceProjectionStates && chunk.analysisCoordinateEvidenceProjectionStates[index]
    );
    values.analysisCoordinateEvidenceAvailable = coordinateEvidenceProjected;
    values.analysisCoordinateEvidenceStatus = coordinateEvidenceProjected
      ? String((analysisCoordinateEvidenceArtifact.manifest.codes.status || [])[chunk.analysisCoordinateEvidenceStatusCodes[index] - 1] || "unavailable")
      : "unavailable";
    values.analysisCoordinateCountryConsistency = coordinateEvidenceProjected
      ? String((analysisCoordinateEvidenceArtifact.manifest.codes.countryConsistency || [])[chunk.analysisCoordinateEvidenceConsistencyCodes[index] - 1] || "not_applicable_invalid")
      : "not_applicable_invalid";
    values.analysisCoordinateQualityBin = coordinateEvidenceProjected
      ? String((analysisCoordinateEvidenceArtifact.manifest.codes.qualityBin || [])[chunk.analysisCoordinateEvidenceQualityBinCodes[index] - 1] || "invalid_or_incompatible")
      : "invalid_or_incompatible";
    values.analysisCoordinateRiskFlags = coordinateEvidenceProjected
      ? chunk.analysisCoordinateEvidenceRiskFlags[index]
      : 0;
    values.analysisCoordinateMacroregion = coordinateEvidenceProjected
      ? dictionaryValue(dictionaries.coordinateEvidenceMacroregion, chunk.analysisCoordinateEvidenceMacroregionCodes[index]) || "unknown"
      : "unknown";
    values.analysisCoordinateEvidenceTyped = coordinateEvidenceProjected &&
      ["typed_country_consistent", "typed_country_unchecked"].indexOf(values.analysisCoordinateEvidenceStatus) !== -1;
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
    const selectedAreaCountry = String(payload && payload.selectedAreaCountry || "").trim().toLowerCase();

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
        if (selectedAreaCountry) {
          const analysisCountry = String(values.analysisCountry || "").trim().toLowerCase();
          const assignedCountry = analysisCountry && analysisCountry !== "unavailable" && analysisCountry !== "unknown"
            ? analysisCountry
            : String(values.country || "").trim().toLowerCase();
          if (assignedCountry !== selectedAreaCountry) continue;
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

  function analysisRowInsideAnyShape(values, shapes) {
    if (!Array.isArray(shapes)) return true;
    if (!shapes.length) return false;
    return shapes.some(function (shape) {
      const type = String(shape && shape.type || "").toLowerCase();
      if (type === "country") {
        const requested = String(shape && (shape.country || shape.countryName) || "").trim().toLowerCase();
        const projected = String(values && values.analysisCountry || "").trim().toLowerCase();
        const assigned = projected && projected !== "unavailable" && projected !== "unknown"
          ? projected
          : String(values && values.country || "").trim().toLowerCase();
        return Boolean(requested && assigned && requested === assigned);
      }
      return pointInsideAnyAnalysisShape(values && values.lat, values && values.lon, [shape]);
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
      spatialPermutationCount: Number.isFinite(Number(message.spatialPermutationCount))
        ? Number(message.spatialPermutationCount)
        : null,
      spatialBootstrapCount: Number.isFinite(Number(message.spatialBootstrapCount))
        ? Number(message.spatialBootstrapCount)
        : null,
      spatialMinimumStratumSize: Number.isFinite(Number(message.spatialMinimumStratumSize))
        ? Number(message.spatialMinimumStratumSize)
        : null,
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
    if (areaShapes && !analysisRowInsideAnyShape(values, areaShapes)) return false;
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

  function activeAnalysisIdRows(message, matched, filters, keywordIds, areaEventIds, areaShapes, lowPrecisionValues) {
    const range = analysisActiveRange(message);
    const rows = [];
    const collect = function (row) {
      if (range && (!Number.isFinite(row.sortOrdinal) || row.sortOrdinal < range[0] || row.sortOrdinal > range[1])) return;
      rows.push({ eventId: String(row.eventId == null ? "" : row.eventId) });
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
    const neighborSource = manifest && manifest.sources && manifest.sources.ufoPointNeighbors || {};
    const neighborCounts = neighborSource.counts || {};
    const neighborExclusions = neighborSource.exclusions || {};
    const spatialPointCount = Number(counts.ufoSpatialPoints || counts.ufoNeighborEligiblePoints || 0);
    const cropBoundedCount = Number(counts.cropBoundedAnalysisRecords || 0);
    const cropLocalityCount = Number(counts.cropLocalityAnalysisRecords || 0);
    const animalMarkerCount = Number(counts.animalPublicMarkerAnalysisRecords || 0);
    const mappedCount = Number(neighborCounts.packedRows || 0);
    const sourceCoordinateCount = Math.max(0, mappedCount - Number(neighborExclusions.not_source_provided_coordinate || 0));
    const exactDayCount = Math.max(0, sourceCoordinateCount - Number(neighborExclusions.date_not_exact_day || 0));
    const confidenceCount = Math.max(0, exactDayCount - Number(neighborExclusions.craft_confidence_below_medium || 0));
    const sameDayCount = Math.max(0, confidenceCount - Number(neighborExclusions.same_day_suitability_below_medium || 0));
    const recognizedCount = Math.max(0, sameDayCount - Number(neighborExclusions.craft_class_not_recognized || 0));
    const makeGate = function (gateId, label, status, inputN, passedN, reasonCodes, policyId, denominatorLabel) {
      const input = Math.max(0, Number(inputN) || 0);
      const passed = Math.max(0, Math.min(input, Number(passedN) || 0));
      return {
        gateId,
        label,
        applicability: "applicable",
        status,
        inputN: input,
        passedN: passed,
        failedN: Math.max(0, input - passed),
        unknownN: 0,
        denominatorLabel: denominatorLabel || "records entering this gate",
        reasonCodes: Array.isArray(reasonCodes) ? reasonCodes.slice() : [],
        policyId: policyId || "analysis_v2_2_evidence_gate",
        evidenceHash: String(hashes.ufoPointNeighbors || ""),
      };
    };
    const domain = function (key, label, status, eligibleN, totalN, gates, extra) {
      const total = Math.max(0, Number(totalN) || 0);
      const eligible = Math.max(0, Number(eligibleN) || 0);
      return Object.assign({
        key,
        label,
        status,
        applicability: "applicable",
        inputN: total,
        passedN: eligible,
        failedN: Math.max(0, total - eligible),
        unknownN: 0,
        eligibleN: eligible,
        totalN: total,
        denominatorLabel: "domain catalog records",
        reasonCodes: [],
        policyId: "analysis_v2_2_domain_readiness",
        evidenceHash: "",
        releaseHash: "",
        gates: Array.isArray(gates) ? gates : [],
        reasons: [],
      }, extra || {});
    };
    const relationship = relationshipReconciliationReadiness(manifest || {});
    const sourceGates = function (sourceKey) {
      const readiness = manifest && manifest.sources && manifest.sources[sourceKey] &&
        manifest.sources[sourceKey].readiness;
      return Array.isArray(readiness && readiness.gates)
        ? readiness.gates.map(function (gate) { return Object.assign({}, gate); })
        : [];
    };
    const relationshipGates = Array.isArray(
      manifest && manifest.sources && manifest.sources.relationshipReconciliation &&
      manifest.sources.relationshipReconciliation.readiness &&
      manifest.sources.relationshipReconciliation.readiness.gates
    ) ? manifest.sources.relationshipReconciliation.readiness.gates : [];
    return {
      ufoCraftPoints: domain("ufoCraftPoints", "High-precision co-occurrence pool",
        spatialPointCount >= 25 ? "ready_inferential" : "blocked", spatialPointCount, mappedCount, [
          makeGate("source_coordinates", "Source-provided coordinates", "ready_inferential", mappedCount, sourceCoordinateCount, ["generalized_coordinates_excluded"], "ufo_point_neighbors_v2", "mapped report markers"),
          makeGate("exact_day", "Exact-day date", "ready_inferential", sourceCoordinateCount, exactDayCount, ["non_exact_dates_excluded"], "ufo_point_neighbors_v2"),
          makeGate("classification_confidence", "Medium/high classification confidence", "ready_inferential", exactDayCount, confidenceCount, ["low_confidence_excluded"], "ufo_point_neighbors_v2"),
          makeGate("same_day_suitability", "Medium/strong same-day suitability", "ready_inferential", confidenceCount, sameDayCount, ["weak_same_day_evidence_excluded"], "ufo_point_neighbors_v2"),
          makeGate("recognized_shape", "Recognized craft shape", "ready_inferential", sameDayCount, recognizedCount, ["unrecognized_shape_excluded"], "ufo_point_neighbors_v2"),
          makeGate("coordinate_piles", "Coordinate-pile exclusion", "ready_inferential", recognizedCount, spatialPointCount, ["repeated_coordinate_piles_excluded"], "ufo_point_neighbors_v2"),
        ], {
          evidenceHash: hashes.ufoPointNeighbors || "",
          releaseHash: hashes.ufoPointNeighbors || "",
          reasonCodes: ["strict_high_trust_point_neighborhood_pool", "not_total_analysis_eligibility"],
        }),
      militaryFacilities: domain("militaryFacilities", "Verified military facilities", "limited",
        Number(counts.facilityInferentialEligible || 0), Number(counts.facilityMarkers || 0), sourceGates("facilities"), {
          evidenceHash: hashes.facilityAnalysis || "", releaseHash: hashes.facilityAnalysis || "",
          reasonCodes: ["verified_coordinate_and_temporal_contract", "coverage_limited"],
        }),
      researchFacilities: domain("researchFacilities", "Research/test facilities", "limited",
        Number(counts.facilityInferentialEligible || 0), Number(counts.facilityMarkers || 0), sourceGates("facilities"), {
          evidenceHash: hashes.facilityAnalysis || "", releaseHash: hashes.facilityAnalysis || "",
          reasonCodes: ["northern_europe_new_zealand_coverage_concentration"],
        }),
      claimedUfoSites: domain("claimedUfoSites", "Claimed UFO sites", "ready_descriptive", 0,
        Number(manifest && manifest.sources && manifest.sources.facilities &&
          manifest.sources.facilities.counts && manifest.sources.facilities.counts.claimedDescriptive || 0), [], {
          evidenceHash: hashes.facilityAnalysis || "", releaseHash: hashes.facilityAnalysis || "",
          reasonCodes: ["descriptive_only_prohibited_from_inference"],
        }),
      cropBounded: domain("cropBounded", "Crop circles — bounded markers", "ready_sensitivity",
        cropBoundedCount, Number(counts.cropContextRecords || 0), sourceGates("cropContext"), {
          evidenceHash: hashes.contextUfoNeighbors || hashes.cropContextReadiness || "",
          releaseHash: hashes.contextUfoNeighbors || hashes.cropContextReadiness || "",
          reasonCodes: ["catalog_date_not_formation_date", "bounded_marker_uncertainty_applied"],
        }),
      cropLocality: domain("cropLocality", "Crop circles — locality markers", "ready_descriptive",
        cropLocalityCount, Number(counts.cropContextRecords || 0), sourceGates("cropContext"), {
          evidenceHash: hashes.contextUfoNeighbors || hashes.cropContextReadiness || "",
          releaseHash: hashes.contextUfoNeighbors || hashes.cropContextReadiness || "",
          reasonCodes: ["rough_marker_lane", "not_exact_site"],
        }),
      cropCircles: domain("cropCircles", "Crop circles", "ready_sensitivity",
        cropBoundedCount + cropLocalityCount, Number(counts.cropContextRecords || 0), [], {
          evidenceHash: hashes.contextUfoNeighbors || hashes.cropContextReadiness || "",
          releaseHash: hashes.contextUfoNeighbors || hashes.cropContextReadiness || "",
          reasonCodes: ["bounded_and_locality_lanes_separate"],
        }),
      animalReports: domain("animalReports", "Animal reports — public markers", "ready_sensitivity",
        animalMarkerCount, Number(counts.animalContextRecords || 0), sourceGates("animalContext"), {
          evidenceHash: hashes.contextUfoNeighbors || hashes.animalContextReadiness || "",
          releaseHash: hashes.contextUfoNeighbors || hashes.animalContextReadiness || "",
          reasonCodes: ["public_marker_association", "origin_publisher_excluded", "not_exact_site"],
        }),
      relationshipReconciliation: Object.assign({}, relationship, {
        status: "ready_descriptive",
        applicability: "descriptive_only",
        inputN: Number(relationship.totalN || 0),
        passedN: Number(relationship.reconciledN || 0),
        failedN: Math.max(0, Number(relationship.totalN || 0) - Number(relationship.reconciledN || 0)),
        unknownN: 0,
        denominatorLabel: "relationship records",
        reasonCodes: ["inference_blocked_but_descriptive_relationships_available"],
        policyId: "relationship_reconciliation_v2_2",
        evidenceHash: String(relationship.releaseHash || ""),
        gates: relationshipGates,
      }),
    };
  }

  function spatialEligibilityFunnelFromManifest(manifest) {
    const source = manifest && manifest.sources && manifest.sources.ufoPointNeighbors || {};
    const counts = source.counts || {};
    const exclusions = source.exclusions || {};
    const mapped = Math.max(0, Number(counts.packedRows) || 0);
    const sourceCoordinates = Math.max(0, mapped - Number(exclusions.not_source_provided_coordinate || 0));
    const exactDay = Math.max(0, sourceCoordinates - Number(exclusions.date_not_exact_day || 0));
    const confidence = Math.max(0, exactDay - Number(exclusions.craft_confidence_below_medium || 0));
    const sameDay = Math.max(0, confidence - Number(exclusions.same_day_suitability_below_medium || 0));
    const recognized = Math.max(0, sameDay - Number(exclusions.craft_class_not_recognized || 0));
    const eligible = Math.max(0, Number(counts.eligiblePoints) || 0);
    const catalogTotal = Math.max(
      mapped,
      Number(counts.catalogRows || counts.catalogRecords ||
        manifest && manifest.counts && (manifest.counts.catalogRows || manifest.counts.catalogRecords) || 702893)
    );
    const stages = [
      ["catalog", "All catalog reports", catalogTotal],
      ["mapped", "Mapped reports", mapped],
      ["source_coordinates", "Source-provided coordinates", sourceCoordinates],
      ["exact_day", "Exact-day dates", exactDay],
      ["classification_confidence", "Medium/high classification confidence", confidence],
      ["same_day_suitability", "Medium/strong same-day suitability", sameDay],
      ["recognized_shape", "Recognized craft shapes", recognized],
      ["coordinate_pile_exclusion", "After coordinate-pile exclusions", eligible],
    ].map(function (entry, index, all) {
      const prior = index ? all[index - 1][2] : entry[2];
      return {
        key: entry[0],
        label: entry[1],
        count: entry[2],
        excludedN: Math.max(0, prior - entry[2]),
        retentionRate: prior > 0 ? entry[2] / prior : 0,
      };
    });
    return {
      label: "High-precision co-occurrence pool",
      scope: "sealed_full_catalog",
      unitOfAnalysis: "UFO report markers",
      catalogReports: catalogTotal,
      mappedReports: mapped,
      sourceCoordinateReports: sourceCoordinates,
      exactDayReports: exactDay,
      confidenceQualifiedReports: confidence,
      sameDayQualifiedReports: sameDay,
      recognizedCraftReports: recognized,
      inferentiallyEligibleReports: eligible,
      stages,
      exclusions: Object.assign({}, exclusions),
      eligibleSources: Object.assign({}, source.readiness && source.readiness.eligiblePointsBySource || {}),
      eligibilityRate: catalogTotal ? eligible / catalogTotal : 0,
      explanation: "This is a deliberately strict point-neighborhood pool, not the number of reports usable by Analysis generally.",
      evidenceHash: String(analysisSpatialArtifacts.artifactHashes.ufoPointNeighbors || ""),
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
    const wholeCorpusStructure = String(result.analysisMode || "") === "whole_corpus_structure" ||
      String(result.comparisonState || "") === "whole_corpus_structure";
    const inferenceEnabled = inferenceEnabledValue !== false &&
      (wholeCorpusStructure || baselineMode !== ensureAnalysisStats().BASELINE_MODES.FULL_CATALOG);
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
    const configuration = cooccurrence.configuration || {};
    ["crossSource", "sameSource"].forEach(function (key) {
      (Array.isArray(configuration[key]) ? configuration[key] : []).forEach(function (lane) {
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

  function computeSpatialEvidence(message, matched, filters, keywordIds, areaEventIds, areaShapes, lowPrecisionValues, optionsValue) {
    const options = optionsValue || {};
    const baselineMode = ensureAnalysisStats().normalizeBaselineMode(message.baselineMode);
    const wholeCorpusStructure = Boolean(message.fullTimeRange) || ["full", "all", "all_time"].indexOf(
      String(message.timeRangeMode || "").trim().toLowerCase()
    ) !== -1;
    const inferenceEnabled = wholeCorpusStructure || baselineMode !== ensureAnalysisStats().BASELINE_MODES.FULL_CATALOG;
    const readiness = spatialReadinessFromManifest(analysisSpatialArtifacts.manifest || {});
    if (!analysisSpatialArtifacts.loaded || options.contextOnly === true) {
      const relationshipRows = analysisSpatialArtifacts.relationshipRows || analysisSpatialArtifacts.relationships || [];
      const contextNeighbors = analysisSpatialArtifacts.contextNeighbors || [];
      const hasContextEvidence = relationshipRows.length || contextNeighbors.length;
      const fullSpatialLoaded = Boolean(analysisSpatialArtifacts.loaded);
      const activeRows = hasContextEvidence
        ? activeAnalysisIdRows(message, matched, filters, keywordIds, areaEventIds, areaShapes, lowPrecisionValues)
        : [];
      const includeAllWithoutCatalogRows = Boolean(message.fullTimeRange) && rowCount === 0;
      return finalizeSpatialEvidenceResult({
        estimatorVersion: ensureAnalysisSpatial().ESTIMATOR_VERSION,
        status: hasContextEvidence
          ? (fullSpatialLoaded ? "context_evidence_ready" : "context_evidence_ready_spatial_not_loaded")
          : "artifacts_not_loaded",
        suppressionReasons: hasContextEvidence
          ? (fullSpatialLoaded ? [] : ["point_neighborhood_artifacts_not_loaded"])
          : ["spatial_artifacts_not_loaded"],
        readiness: Object.keys(readiness).map(function (key) { return Object.assign({}, readiness[key]); }),
        contextAssociations: contextNeighbors.length
          ? ensureAnalysisSpatial().computeContextAssociations({
              activeRows,
              neighbors: contextNeighbors,
              codebook: analysisSpatialArtifacts.codebooks && analysisSpatialArtifacts.codebooks.contextUfoNeighbors,
              includeAllWhenNoActiveRows: includeAllWithoutCatalogRows,
              permutationCount: message.spatialPermutationCount,
              bootstrapCount: message.spatialBootstrapCount,
              inferenceEnabled,
              seed: String(message.datasetHash || "catalog") + "|" + analysisFilterGeneration(message) + "|context-only",
            })
          : null,
        relationshipSummary: relationshipRows.length
          ? ensureAnalysisSpatial().computeRelationshipSummary(
              relationshipRows,
              analysisSpatialArtifacts.codebooks && analysisSpatialArtifacts.codebooks.relationshipReconciliation,
              activeRows,
              { includeAllWhenNoActiveRows: includeAllWithoutCatalogRows }
            )
          : null,
        eligibility: spatialEligibilityFunnelFromManifest(analysisSpatialArtifacts.manifest || {}),
        traceInputsRead: false,
      }, readiness, baselineMode, inferenceEnabled);
    }
    const rows = activeSpatialRows(message, matched, filters, keywordIds, areaEventIds, areaShapes, lowPrecisionValues);
    const result = ensureAnalysisSpatial().computeSpatialAnalysis({
      rows,
      edges: analysisSpatialArtifacts.neighbors || [],
      spatialPoints: analysisSpatialArtifacts.spatialPoints || [],
      configurationPoints: analysisSpatialArtifacts.configurationPoints || [],
      configurationEdges: analysisSpatialArtifacts.configurationNeighbors || [],
      contextNeighbors: analysisSpatialArtifacts.contextNeighbors || [],
      facilities: analysisSpatialArtifacts.facilities || [],
      relationships: analysisSpatialArtifacts.relationshipRows || analysisSpatialArtifacts.relationships || [],
      codebooks: analysisSpatialArtifacts.codebooks || {},
      readiness,
      eligibilityFunnel: spatialEligibilityFunnelFromManifest(analysisSpatialArtifacts.manifest || {}),
      artifactHashes: Object.assign({}, analysisSpatialArtifacts.artifactHashes || {}),
      seed: String(message.datasetHash || "catalog") + "|" + analysisFilterGeneration(message),
      baselineMode,
      analysisMode: wholeCorpusStructure ? "whole_corpus_structure" : "cohort_comparison",
      comparisonState: wholeCorpusStructure
        ? "whole_corpus_structure"
        : (baselineMode === ensureAnalysisStats().BASELINE_MODES.FULL_CATALOG ? "descriptive_overlap" : "inferential"),
      inferenceEnabled,
      permutationCount: message.spatialPermutationCount,
      bootstrapCount: message.spatialBootstrapCount,
      minimumStratumSize: message.spatialMinimumStratumSize,
    });
    result.analysisMode = wholeCorpusStructure ? "whole_corpus_structure" : "cohort_comparison";
    result.comparisonState = wholeCorpusStructure
      ? "whole_corpus_structure"
      : (baselineMode === ensureAnalysisStats().BASELINE_MODES.FULL_CATALOG ? "descriptive_overlap" : "inferential");
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
        analysisSpatialArtifacts.artifactHashes || {},
        analysisGeographyArtifact.loaded
          ? { ufoGeography: String(analysisGeographyArtifact.artifactHash || "") }
          : {},
        analysisDurationArtifact.loaded
          ? Object.assign({}, analysisDurationArtifact.artifactHashes || {})
          : {},
        analysisReportingDelayArtifact.loaded
          ? Object.assign({}, analysisReportingDelayArtifact.artifactHashes || {})
          : {},
        analysisTimeOfDayArtifact.loaded
          ? Object.assign({}, analysisTimeOfDayArtifact.artifactHashes || {})
          : {},
        analysisWitnessCountArtifact.loaded
          ? Object.assign({}, analysisWitnessCountArtifact.artifactHashes || {})
          : {},
        analysisColorArtifact.loaded
          ? Object.assign({}, analysisColorArtifact.artifactHashes || {})
          : {},
        analysisCoordinateEvidenceArtifact.loaded
          ? Object.assign({}, analysisCoordinateEvidenceArtifact.artifactHashes || {})
          : {}
      ),
      geographyProjectionLoaded: Boolean(analysisGeographyArtifact.loaded),
      durationProjectionLoaded: Boolean(analysisDurationArtifact.loaded),
      durationArtifact: analysisDurationArtifact.loaded ? {
        releaseId: analysisDurationArtifact.releaseId,
        counts: Object.assign({}, analysisDurationArtifact.manifest.counts || {}),
        readiness: Object.assign({}, analysisDurationArtifact.manifest.readiness || {}),
        policy: Object.assign({}, analysisDurationArtifact.manifest.policy || {}),
        negativeControls: Object.assign({}, analysisDurationArtifact.manifest.negativeControls || {}),
        artifactHashes: Object.assign({}, analysisDurationArtifact.artifactHashes || {}),
      } : null,
      reportingDelayProjectionLoaded: Boolean(analysisReportingDelayArtifact.loaded),
      reportingDelayArtifact: analysisReportingDelayArtifact.loaded ? {
        releaseId: analysisReportingDelayArtifact.releaseId,
        counts: Object.assign({}, analysisReportingDelayArtifact.manifest.counts || {}),
        readiness: Object.assign({}, analysisReportingDelayArtifact.manifest.readiness || {}),
        policy: Object.assign({}, analysisReportingDelayArtifact.manifest.policy || {}),
        negativeControls: Object.assign({}, analysisReportingDelayArtifact.manifest.negativeControls || {}),
        artifactHashes: Object.assign({}, analysisReportingDelayArtifact.artifactHashes || {}),
      } : null,
      timeOfDayProjectionLoaded: Boolean(analysisTimeOfDayArtifact.loaded),
      timeOfDayArtifact: analysisTimeOfDayArtifact.loaded ? {
        releaseId: analysisTimeOfDayArtifact.releaseId,
        counts: Object.assign({}, analysisTimeOfDayArtifact.manifest.counts || {}),
        readiness: Object.assign({}, analysisTimeOfDayArtifact.manifest.readiness || {}),
        policy: Object.assign({}, analysisTimeOfDayArtifact.manifest.policy || {}),
        negativeControls: Object.assign({}, analysisTimeOfDayArtifact.manifest.negativeControls || {}),
        artifactHashes: Object.assign({}, analysisTimeOfDayArtifact.artifactHashes || {}),
      } : null,
      witnessCountProjectionLoaded: Boolean(analysisWitnessCountArtifact.loaded),
      witnessCountArtifact: analysisWitnessCountArtifact.loaded ? {
        releaseId: analysisWitnessCountArtifact.releaseId,
        counts: Object.assign({}, analysisWitnessCountArtifact.manifest.counts || {}),
        readiness: Object.assign({}, analysisWitnessCountArtifact.manifest.readiness || {}),
        policy: Object.assign({}, analysisWitnessCountArtifact.manifest.policy || {}),
        negativeControls: Object.assign({}, analysisWitnessCountArtifact.manifest.negativeControls || {}),
        artifactHashes: Object.assign({}, analysisWitnessCountArtifact.artifactHashes || {}),
      } : null,
      colorProjectionLoaded: Boolean(analysisColorArtifact.loaded),
      colorArtifact: analysisColorArtifact.loaded ? {
        releaseId: analysisColorArtifact.releaseId,
        counts: Object.assign({}, analysisColorArtifact.manifest.counts || {}),
        readiness: Object.assign({}, analysisColorArtifact.manifest.readiness || {}),
        policy: Object.assign({}, analysisColorArtifact.manifest.policy || {}),
        negativeControls: Object.assign({}, analysisColorArtifact.manifest.negativeControls || {}),
        commonSupport: Object.assign({}, analysisColorArtifact.manifest.commonSupport || {}),
        artifactHashes: Object.assign({}, analysisColorArtifact.artifactHashes || {}),
      } : null,
      coordinateEvidenceProjectionLoaded: Boolean(analysisCoordinateEvidenceArtifact.loaded),
      coordinateEvidenceArtifact: analysisCoordinateEvidenceArtifact.loaded ? {
        releaseId: analysisCoordinateEvidenceArtifact.releaseId,
        counts: Object.assign({}, analysisCoordinateEvidenceArtifact.manifest.counts || {}),
        readiness: Object.assign({}, analysisCoordinateEvidenceArtifact.manifest.readiness || {}),
        policy: Object.assign({}, analysisCoordinateEvidenceArtifact.manifest.policy || {}),
        negativeControls: Object.assign({}, analysisCoordinateEvidenceArtifact.manifest.negativeControls || {}),
        artifactHashes: Object.assign({}, analysisCoordinateEvidenceArtifact.artifactHashes || {}),
      } : null,
      estimatorVersion: String(message.estimatorVersion || "ufo-analysis-evidence-lab-v2.8.0"),
      analysisPhase: String(message.analysisPhase || (message.quickMode ? "quick" : "full")),
      quickMode: Boolean(message.quickMode),
      contextProjections: analysisContext,
    });
    const contextEvidenceRequested = selectedDomains.indexOf("context") !== -1 &&
      ((Array.isArray(analysisSpatialArtifacts.relationshipRows) && analysisSpatialArtifacts.relationshipRows.length > 0) ||
        (Array.isArray(analysisSpatialArtifacts.contextNeighbors) && analysisSpatialArtifacts.contextNeighbors.length > 0));
    const spatialEvidenceRequested = selectedDomains.indexOf("spatial") !== -1 ||
      selectedDomains.indexOf("spatial_evidence") !== -1;
    if (!options.deferSpatial &&
        (spatialEvidenceRequested || contextEvidenceRequested)) {
      result.spatialEvidence = computeSpatialEvidence(
        message,
        matched,
        filters,
        keywordIds,
        areaEventIds,
        areaShapes,
        lowPrecisionValues,
        { contextOnly: contextEvidenceRequested && !spatialEvidenceRequested }
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

  function rawBinaryFallbackUrl(url) {
    return String(url || "").replace(/\.bin\.gz(?:\?.*)?$/i, function (match) {
      const queryIndex = match.indexOf("?");
      return ".bin" + (queryIndex === -1 ? "" : match.slice(queryIndex));
    });
  }

  async function decodeBinaryResponse(response, sourceUrl, integrity) {
    const bytes = new Uint8Array(await response.arrayBuffer());
    let decodedBytes = bytes;
    const gzipEncoded = bytes.length >= 2 && bytes[0] === 0x1f && bytes[1] === 0x8b;
    if (gzipEncoded) {
      await verifyAnalysisBytes(bytes, integrity && integrity.gzipSha256, sourceUrl + " compressed payload");
      if (typeof DecompressionStream !== "function") {
        throw new Error("gzip analysis binary requires DecompressionStream support: " + sourceUrl);
      }
      const stream = new Response(bytes).body.pipeThrough(new DecompressionStream("gzip"));
      decodedBytes = new Uint8Array(await new Response(stream).arrayBuffer());
    }
    await verifyAnalysisBytes(decodedBytes, integrity && integrity.sha256, sourceUrl + " binary payload");
    return decodedBytes;
  }

  async function fetchAnalysisBinary(urlValue, integrity) {
    const url = String(urlValue || "");
    if (!url) return null;
    try {
      const response = await fetch(url, { cache: "force-cache" });
      if (!response.ok) throw new Error("HTTP " + response.status + " for " + url);
      return await decodeBinaryResponse(response, url, integrity || {});
    } catch (error) {
      if (error && /SHA-256 mismatch/.test(String(error.message || error))) throw error;
      const fallback = rawBinaryFallbackUrl(url);
      if (!fallback || fallback === url) throw error;
      const response = await fetch(fallback, { cache: "force-cache" });
      if (!response.ok) throw new Error("HTTP " + response.status + " for " + fallback);
      return await decodeBinaryResponse(response, fallback, integrity || {});
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
    const gzipFile = entry.gzipFile || entry.gzip_file || "";
    if (gzipFile && typeof DecompressionStream === "function") return gzipFile;
    return entry.file || entry.path || gzipFile || "";
  }

  function manifestArtifactUrl(manifest, key, manifestUrl) {
    const resolved = resolveAnalysisUrl(manifestArtifactFile(manifest, key), manifestUrl);
    const sha256 = normalizedSha256((manifestArtifactEntry(manifest, key) || {}).sha256);
    if (!resolved || !sha256) return resolved;
    try {
      const url = new URL(resolved, manifestUrl);
      url.searchParams.set("sha256", sha256);
      return url.toString();
    } catch (_error) {
      return resolved + (resolved.indexOf("?") === -1 ? "?" : "&") + "sha256=" + sha256;
    }
  }

  function geographyBinaryEntry(manifest) {
    const entry = manifestArtifactEntry(manifest, "ufoGeography") || {};
    return entry.binary && typeof entry.binary === "object" ? entry.binary : null;
  }

  function geographyBinaryFile(manifest) {
    const entry = geographyBinaryEntry(manifest) || {};
    const gzipFile = entry.gzipFile || entry.gzip_file || "";
    if (gzipFile && typeof DecompressionStream === "function") return gzipFile;
    return entry.file || entry.path || gzipFile || "";
  }

  function geographyBinaryUrl(manifest, manifestUrl) {
    const entry = geographyBinaryEntry(manifest) || {};
    const resolved = resolveAnalysisUrl(geographyBinaryFile(manifest), manifestUrl);
    const sha256 = normalizedSha256(entry.sha256);
    if (!resolved || !sha256) return resolved;
    try {
      const url = new URL(resolved, manifestUrl);
      url.searchParams.set("sha256", sha256);
      return url.toString();
    } catch (_error) {
      return resolved + (resolved.indexOf("?") === -1 ? "?" : "&") + "sha256=" + sha256;
    }
  }

  function geographyBinaryIntegrity(manifest) {
    const entry = geographyBinaryEntry(manifest) || {};
    return {
      sha256: entry.sha256 || "",
      gzipSha256: entry.gzipSha256 || entry.gzip_sha256 || "",
    };
  }

  function validateSpatialManifestArtifact(manifest, key) {
    const entry = manifestArtifactEntry(manifest, key);
    if (!entry) throw new Error("Analysis v2 manifest is missing required artifact " + key + ".");
    if (!normalizedSha256(entry.sha256)) {
      throw new Error("Analysis v2 artifact " + key + " is missing a valid raw SHA-256.");
    }
    if (!Number.isInteger(Number(entry.rowCount)) || Number(entry.rowCount) < 0) {
      throw new Error("Analysis v2 artifact " + key + " has an invalid declared row count.");
    }
    if (!Array.isArray(entry.rowSchema) || !entry.rowSchema.length ||
        new Set(entry.rowSchema.map(String)).size !== entry.rowSchema.length) {
      throw new Error("Analysis v2 artifact " + key + " has an invalid row schema.");
    }
    if (!manifestArtifactFile(manifest, key)) {
      throw new Error("Analysis v2 artifact " + key + " has no loadable file.");
    }
    const gzipFile = entry.gzipFile || entry.gzip_file || "";
    if (gzipFile && !normalizedSha256(entry.gzipSha256 || entry.gzip_sha256)) {
      throw new Error("Analysis v2 artifact " + key + " is missing a valid gzip SHA-256.");
    }
    return entry;
  }

  function validateLoadedSpatialArtifact(rowsValue, manifest, key) {
    const rows = rowsValue;
    const entry = manifestArtifactEntry(manifest, key) || {};
    if (!Array.isArray(rows)) throw new Error("Analysis v2 artifact " + key + " is not a row array.");
    if (rows.length !== Number(entry.rowCount)) {
      throw new Error("Analysis v2 artifact " + key + " row-count mismatch: expected " +
        Number(entry.rowCount) + ", received " + rows.length + ".");
    }
    const width = Array.isArray(entry.rowSchema) ? entry.rowSchema.length : 0;
    const invalidIndex = rows.findIndex(function (row) { return !Array.isArray(row) || row.length !== width; });
    if (invalidIndex !== -1) {
      throw new Error("Analysis v2 artifact " + key + " row " + invalidIndex +
        " does not match the declared " + width + "-field schema.");
    }
    return rows;
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

  function spatialManifestReleaseIdentity(manifest) {
    const value = manifest && typeof manifest === "object" ? manifest : {};
    return [
      String(value.schemaId || ""),
      String(value.schemaVersion || ""),
      String(value.manifestVersion || ""),
      String(value.releaseId || ""),
    ].join("|");
  }

  function assertPartialSpatialManifestCompatible(manifest) {
    const current = analysisSpatialArtifacts.manifest;
    if (!current) return;
    const currentIdentity = spatialManifestReleaseIdentity(current);
    const requestedIdentity = spatialManifestReleaseIdentity(manifest);
    if (currentIdentity !== requestedIdentity) {
      throw new Error("Analysis context artifact release does not match the spatial release already loaded in this worker.");
    }
    const currentHashes = analysisSpatialArtifacts.artifactHashes || {};
    Object.keys(currentHashes).forEach(function (key) {
      if (key === "manifest") return;
      const currentHash = String(currentHashes[key] || "");
      const requestedHash = String(
        manifest && manifest.artifacts && manifest.artifacts[key] && manifest.artifacts[key].sha256 || ""
      );
      if (currentHash && requestedHash && currentHash !== requestedHash) {
        throw new Error("Analysis context artifact hash does not match the spatial release already loaded in this worker.");
      }
    });
  }

  function analysisSpatialSnapshot() {
    return {
      loaded: Boolean(analysisSpatialArtifacts.loaded),
      rowCounts: {
        neighbors: Array.isArray(analysisSpatialArtifacts.neighbors) ? analysisSpatialArtifacts.neighbors.length : 0,
        spatialPoints: Array.isArray(analysisSpatialArtifacts.spatialPoints) ? analysisSpatialArtifacts.spatialPoints.length : 0,
        configurationPoints: Array.isArray(analysisSpatialArtifacts.configurationPoints) ? analysisSpatialArtifacts.configurationPoints.length : 0,
        configurationNeighbors: Array.isArray(analysisSpatialArtifacts.configurationNeighbors) ? analysisSpatialArtifacts.configurationNeighbors.length : 0,
        contextNeighbors: Array.isArray(analysisSpatialArtifacts.contextNeighbors) ? analysisSpatialArtifacts.contextNeighbors.length : 0,
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
          : "ufo-analysis-spatial-v2.2.0"),
    };
  }

  function dedicatedSpatialWorkerSupported() {
    return typeof Worker === "function";
  }

  function dedicatedSpatialWorkerUrl() {
    try {
      return new URL("./analysis_spatial_worker.js?v=" + ANALYSIS_RUNTIME_CACHE_KEY, self.location && self.location.href || undefined).toString();
    } catch (_error) {
      return "./analysis_spatial_worker.js?v=" + ANALYSIS_RUNTIME_CACHE_KEY;
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
      estimatorVersion: String(message.estimatorVersion || "ufo-analysis-evidence-lab-v2.4.0"),
      analysisPhase: String(message.analysisPhase || (message.quickMode ? "quick" : "full")),
      quickMode: Boolean(message.quickMode),
      inferenceDeferred: Boolean(result && result.inferenceDeferred),
      analysisMode: String(result && result.analysisMode || "cohort_comparison"),
      comparisonState: String(result && result.comparisonState || result && result.baseline && result.baseline.comparisonState || "inferential"),
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
      estimatorVersion: String(message && message.estimatorVersion || "ufo-analysis-evidence-lab-v2.4.0"),
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
      executor.estimatorVersion = String(message.estimatorVersion || "ufo-analysis-spatial-v2.2.0");
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
      const wholeCorpusStructure = String(message.result && message.result.analysisMode || "") === "whole_corpus_structure" ||
        String(message.result && message.result.comparisonState || "") === "whole_corpus_structure" ||
        Boolean(pending.message.fullTimeRange) || ["full", "all", "all_time"].indexOf(
          String(pending.message.timeRangeMode || "").trim().toLowerCase()
        ) !== -1;
      pending.result.spatialEvidence = finalizeSpatialEvidenceResult(
        message.result,
        spatialReadinessFromManifest(analysisSpatialArtifacts.manifest || {}),
        baselineMode,
        wholeCorpusStructure || baselineMode !== ensureAnalysisStats().BASELINE_MODES.FULL_CATALOG
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
      spatialPoints: analysisSpatialArtifacts.spatialPoints || [],
      configurationPoints: analysisSpatialArtifacts.configurationPoints || [],
      configurationEdges: analysisSpatialArtifacts.configurationNeighbors || [],
      contextNeighbors: analysisSpatialArtifacts.contextNeighbors || [],
      facilities: analysisSpatialArtifacts.facilities || [],
      relationships: analysisSpatialArtifacts.relationshipRows || analysisSpatialArtifacts.relationships || [],
      codebooks: analysisSpatialArtifacts.codebooks || {},
      readiness: spatialReadinessFromManifest(analysisSpatialArtifacts.manifest || {}),
      artifactHashes: Object.assign({}, analysisSpatialArtifacts.artifactHashes || {}),
    });
    return executor.readyPromise;
  }

  function spatialExecutionPayload(message) {
    const stats = ensureAnalysisStats();
    const baselineMode = stats.normalizeBaselineMode(message.baselineMode);
    const wholeCorpusStructure = Boolean(message.fullTimeRange) || ["full", "all", "all_time"].indexOf(
      String(message.timeRangeMode || "").trim().toLowerCase()
    ) !== -1;
    const inferenceEnabled = wholeCorpusStructure || baselineMode !== stats.BASELINE_MODES.FULL_CATALOG;
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
      analysisMode: wholeCorpusStructure ? "whole_corpus_structure" : "cohort_comparison",
      comparisonState: wholeCorpusStructure
        ? "whole_corpus_structure"
        : (baselineMode === stats.BASELINE_MODES.FULL_CATALOG ? "descriptive_overlap" : "inferential"),
      inferenceEnabled,
      eligibilityFunnel: spatialEligibilityFunnelFromManifest(analysisSpatialArtifacts.manifest || {}),
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

  function analysisV2ManifestSupported(manifest) {
    const version = String(manifest && manifest.manifestVersion || "");
    const schemaId = String(manifest && manifest.schemaId || "");
    return Boolean(
      manifest &&
      Number(manifest.schemaVersion) === 2 &&
      (version === "2.1.0" || version === "2.2.0") &&
      (schemaId === "ufo-timeline-analysis-evidence-artifacts-v2.1.0" ||
        schemaId === "ufo-timeline-analysis-evidence-artifacts-v2.2.0") &&
      manifest.artifacts
    );
  }

  function analysisDurationManifestSupported(manifest) {
    return Boolean(
      manifest &&
      Number(manifest.schemaVersion) === 1 &&
      String(manifest.schemaId || "") === "ufo-timeline-analysis-duration-artifacts-v1.0.0" &&
      String(manifest.manifestVersion || "") === "1.0.0" &&
      manifest.artifacts &&
      manifest.codes &&
      manifest.readiness
    );
  }

  function validateDurationArtifact(manifest, key) {
    const entry = manifestArtifactEntry(manifest, key);
    if (!entry) throw new Error("Duration manifest is missing required artifact " + key + ".");
    if (!normalizedSha256(entry.sha256) || !normalizedSha256(entry.gzipSha256)) {
      throw new Error("Duration artifact " + key + " is missing pinned raw or gzip integrity.");
    }
    if (!Number.isInteger(Number(entry.rowCount)) || Number(entry.rowCount) < 0) {
      throw new Error("Duration artifact " + key + " has an invalid row count.");
    }
    if (!Array.isArray(entry.rowSchema) || !entry.rowSchema.length) {
      throw new Error("Duration artifact " + key + " has an invalid row schema.");
    }
    return entry;
  }

  function validateDurationRows(rowsValue, manifest, key) {
    const rows = rowsValue;
    const entry = validateDurationArtifact(manifest, key);
    if (!Array.isArray(rows) || rows.length !== Number(entry.rowCount)) {
      throw new Error("Duration artifact " + key + " row-count mismatch.");
    }
    const width = entry.rowSchema.length;
    const invalidIndex = rows.findIndex(function (row) { return !Array.isArray(row) || row.length !== width; });
    if (invalidIndex !== -1) {
      throw new Error("Duration artifact " + key + " row " + invalidIndex + " has an invalid width.");
    }
    return rows;
  }

  function applyDurationProjection(dictionaryRows, projectionRows, manifest) {
    const statusCodes = manifest.codes.status || [];
    const binCodes = manifest.codes.durationBin || [];
    const macroregionCodes = manifest.codes.macroregion || [];
    const occurrences = new Uint32Array(dictionaryRows.length);
    let previousRowIndex = -1;
    let normalizedRows = 0;
    let chunkIndex = 0;
    let chunkStart = 0;
    projectionRows.forEach(function (projection, projectionIndex) {
      const catalogRowIndex = Number(projection[0]);
      const valueCode = Number(projection[2]);
      const macroregionCode = Number(projection[3]);
      if (!Number.isInteger(catalogRowIndex) || catalogRowIndex <= previousRowIndex) {
        throw new Error("Duration projection row order is not strictly increasing at row " + projectionIndex + ".");
      }
      previousRowIndex = catalogRowIndex;
      while (chunkIndex < chunks.length && catalogRowIndex >= chunkStart + chunks[chunkIndex].length) {
        chunkStart += chunks[chunkIndex].length;
        chunkIndex += 1;
      }
      if (catalogRowIndex < 0 || catalogRowIndex >= rowCount || chunkIndex >= chunks.length) {
        throw new Error("Duration projection references an out-of-range catalog row.");
      }
      const location = { chunk: chunks[chunkIndex], index: catalogRowIndex - chunkStart };
      if (String(eventIdAt(location.chunk, location.index)) !== String(projection[1])) {
        throw new Error("Duration projection event ID does not match the served catalog at row " + catalogRowIndex + ".");
      }
      if (!Number.isInteger(valueCode) || valueCode < 0 || valueCode >= dictionaryRows.length) {
        throw new Error("Duration projection has an invalid value code at row " + projectionIndex + ".");
      }
      if (!Number.isInteger(macroregionCode) || macroregionCode < 0 || macroregionCode >= macroregionCodes.length) {
        throw new Error("Duration projection has an invalid macroregion code at row " + projectionIndex + ".");
      }
      const value = dictionaryRows[valueCode];
      const statusCode = Number(value[3]);
      const descriptiveBinCode = Number(value[7]);
      const inferentialBinCode = Number(value[8]);
      if (!Number.isInteger(statusCode) || statusCode < 0 || statusCode >= statusCodes.length ||
          !Number.isInteger(descriptiveBinCode) || descriptiveBinCode < 0 || descriptiveBinCode >= binCodes.length ||
          !Number.isInteger(inferentialBinCode) || inferentialBinCode < 0 || inferentialBinCode >= binCodes.length) {
        throw new Error("Duration dictionary code is out of range for value " + valueCode + ".");
      }
      location.chunk.analysisDurationValueCodes[location.index] = valueCode + 1;
      location.chunk.analysisDurationStatusCodes[location.index] = statusCode + 1;
      location.chunk.analysisDurationDescriptiveBinCodes[location.index] = descriptiveBinCode + 1;
      location.chunk.analysisDurationInferentialBinCodes[location.index] = inferentialBinCode + 1;
      location.chunk.analysisDurationMacroregionCodes[location.index] = categoryCode(
        dictionaries.durationMacroregion,
        String(macroregionCodes[macroregionCode] || "unknown")
      );
      location.chunk.analysisDurationLowerSeconds[location.index] = value[5] == null ? Number.NaN : Number(value[5]);
      location.chunk.analysisDurationUpperSeconds[location.index] = value[6] == null ? Number.NaN : Number(value[6]);
      occurrences[valueCode] += 1;
      if (["unparsed", "ambiguous"].indexOf(String(statusCodes[statusCode] || "unparsed")) === -1) normalizedRows += 1;
    });
    dictionaryRows.forEach(function (value, valueCode) {
      if (occurrences[valueCode] !== Number(value[10])) {
        throw new Error("Duration dictionary occurrence parity failed for value " + valueCode + ".");
      }
    });
    return { appliedRows: projectionRows.length, normalizedRows };
  }

  async function loadAnalysisDurationArtifact(message) {
    const urls = message.urls && typeof message.urls === "object" ? message.urls : {};
    const manifestUrl = String(urls.manifest || "./data/analysis_duration_v1/manifest.json");
    const manifest = message.manifest && typeof message.manifest === "object"
      ? message.manifest
      : await fetchAnalysisJson(manifestUrl, { sha256: message.manifestSha256 || "" });
    if (!analysisDurationManifestSupported(manifest)) {
      throw new Error("Analysis duration manifest is invalid or unsupported.");
    }
    validateDurationArtifact(manifest, "durationValueDictionary");
    validateDurationArtifact(manifest, "durationProjection");
    const dictionaryRows = validateDurationRows(
      await fetchAnalysisJson(
        urls.dictionary || manifestArtifactUrl(manifest, "durationValueDictionary", manifestUrl),
        manifestArtifactIntegrity(manifest, "durationValueDictionary")
      ),
      manifest,
      "durationValueDictionary"
    );
    const projectionRows = validateDurationRows(
      await fetchAnalysisJson(
        urls.projection || manifestArtifactUrl(manifest, "durationProjection", manifestUrl),
        manifestArtifactIntegrity(manifest, "durationProjection")
      ),
      manifest,
      "durationProjection"
    );
    const applied = applyDurationProjection(dictionaryRows, projectionRows, manifest);
    analysisDurationArtifact = {
      manifest,
      loaded: true,
      appliedRows: applied.appliedRows,
      normalizedRows: applied.normalizedRows,
      releaseId: String(manifest.releaseId || ""),
      artifactHashes: {
        durationValueDictionary: String(manifest.artifacts.durationValueDictionary.sha256 || ""),
        durationProjection: String(manifest.artifacts.durationProjection.sha256 || ""),
      },
    };
    analysisCache.clear();
    analysisMatchCache.clear();
    return {
      loaded: true,
      appliedRows: applied.appliedRows,
      normalizedRows: applied.normalizedRows,
      releaseId: analysisDurationArtifact.releaseId,
      artifactHashes: Object.assign({}, analysisDurationArtifact.artifactHashes),
      readinessStatus: String(manifest.readiness.status || "not_estimable"),
    };
  }

  function analysisTimeOfDayManifestSupported(manifest) {
    return Boolean(
      manifest &&
      Number(manifest.schemaVersion) === 1 &&
      String(manifest.schemaId || "") === "ufo-timeline-analysis-time-of-day-artifacts-v1.0.0" &&
      String(manifest.manifestVersion || "") === "1.0.0" &&
      manifest.artifacts && manifest.artifacts.timeOfDayValueDictionary &&
      manifest.artifactGroups && Array.isArray(manifest.artifactGroups.timeProjectionShards) &&
      manifest.artifactGroups.timeProjectionShards.length > 0 &&
      manifest.codes && manifest.readiness
    );
  }

  function validateTimeOfDayRows(rows, manifest, key, width) {
    const entry = manifestArtifactEntry(manifest, key);
    if (!entry || !normalizedSha256(entry.sha256) || !normalizedSha256(entry.gzipSha256)) {
      throw new Error("Time-of-day artifact " + key + " is missing pinned integrity.");
    }
    if (!Array.isArray(entry.rowSchema) || entry.rowSchema.length !== width) {
      throw new Error("Time-of-day artifact " + key + " has an invalid row schema.");
    }
    if (!Array.isArray(rows) || rows.length !== Number(entry.rowCount)) {
      throw new Error("Time-of-day artifact " + key + " row-count mismatch.");
    }
    const invalidIndex = rows.findIndex(function (row) { return !Array.isArray(row) || row.length !== width; });
    if (invalidIndex !== -1) {
      throw new Error("Time-of-day artifact " + key + " row " + invalidIndex + " has an invalid width.");
    }
    return rows;
  }

  function applyTimeOfDayProjection(dictionaryRows, projectionRows, manifest) {
    const sourceCodes = manifest.codes.source || [];
    const statusCodes = manifest.codes.status || [];
    const binCodes = manifest.codes.timeBin || [];
    const macroregionCodes = manifest.codes.macroregion || [];
    const occurrences = new Uint32Array(dictionaryRows.length);
    let previousRowIndex = -1;
    let chunkIndex = 0;
    let chunkStart = 0;
    let typedRows = 0;
    projectionRows.forEach(function (projection, projectionIndex) {
      const catalogRowIndex = Number(projection[0]);
      const valueCode = Number(projection[2]);
      const macroregionCode = Number(projection[3]);
      if (!Number.isInteger(catalogRowIndex) || catalogRowIndex <= previousRowIndex) {
        throw new Error("Time-of-day projection row order is not strictly increasing at row " + projectionIndex + ".");
      }
      previousRowIndex = catalogRowIndex;
      while (chunkIndex < chunks.length && catalogRowIndex >= chunkStart + chunks[chunkIndex].length) {
        chunkStart += chunks[chunkIndex].length;
        chunkIndex += 1;
      }
      if (catalogRowIndex < 0 || catalogRowIndex >= rowCount || chunkIndex >= chunks.length) {
        throw new Error("Time-of-day projection references an out-of-range catalog row.");
      }
      const location = { chunk: chunks[chunkIndex], index: catalogRowIndex - chunkStart };
      if (String(eventIdAt(location.chunk, location.index)) !== String(projection[1])) {
        throw new Error("Time-of-day projection event ID does not match the served catalog at row " + catalogRowIndex + ".");
      }
      if (!Number.isInteger(valueCode) || valueCode < 0 || valueCode >= dictionaryRows.length ||
          !Number.isInteger(macroregionCode) || macroregionCode < 0 || macroregionCode >= macroregionCodes.length) {
        throw new Error("Time-of-day projection contains an out-of-range code at row " + projectionIndex + ".");
      }
      const value = dictionaryRows[valueCode];
      const sourceCode = Number(value[0]);
      const statusCode = Number(value[3]);
      const descriptiveBinCode = Number(value[7]);
      const inferentialBinCode = Number(value[8]);
      if (!Number.isInteger(sourceCode) || sourceCode < 0 || sourceCode >= sourceCodes.length ||
          !Number.isInteger(statusCode) || statusCode < 0 || statusCode >= statusCodes.length ||
          !Number.isInteger(descriptiveBinCode) || descriptiveBinCode < 0 || descriptiveBinCode >= binCodes.length ||
          !Number.isInteger(inferentialBinCode) || inferentialBinCode < 0 || inferentialBinCode >= binCodes.length) {
        throw new Error("Time-of-day dictionary code is out of range for value " + valueCode + ".");
      }
      const canonicalSource = dictionaryValue(dictionaries.source, location.chunk.sourceCodes[location.index]) || "unknown";
      if (String(sourceCodes[sourceCode] || "unknown") !== canonicalSource) {
        throw new Error("Time-of-day dictionary source does not match the served catalog at row " + catalogRowIndex + ".");
      }
      const status = String(statusCodes[statusCode] || "unparsed");
      const lowerMinute = value[5] == null ? null : Number(value[5]);
      const upperMinute = value[6] == null ? null : Number(value[6]);
      const typed = ["exact_clock", "approximate_clock", "clock_range", "qualitative_period"].indexOf(status) !== -1;
      if (status === "exact_clock") {
        if (!Number.isInteger(lowerMinute) || lowerMinute < 0 || lowerMinute >= 1440 || lowerMinute !== upperMinute || String(binCodes[inferentialBinCode]) === "unknown") {
          throw new Error("Exact time-of-day row has invalid minutes at row " + projectionIndex + ".");
        }
      } else if (["sentinel_ambiguous", "qualitative_period", "invalid_clock", "unparsed"].indexOf(status) !== -1 &&
          (lowerMinute != null || upperMinute != null || String(binCodes[inferentialBinCode]) !== "unknown")) {
        throw new Error("Excluded time-of-day value silently retains inferential minutes for value " + valueCode + ".");
      }
      location.chunk.analysisTimeOfDayValueCodes[location.index] = valueCode + 1;
      location.chunk.analysisTimeOfDayStatusCodes[location.index] = statusCode + 1;
      location.chunk.analysisTimeOfDayDescriptiveBinCodes[location.index] = descriptiveBinCode + 1;
      location.chunk.analysisTimeOfDayInferentialBinCodes[location.index] = inferentialBinCode + 1;
      location.chunk.analysisTimeOfDayMacroregionCodes[location.index] = categoryCode(
        dictionaries.timeOfDayMacroregion,
        String(macroregionCodes[macroregionCode] || "unknown")
      );
      location.chunk.analysisTimeOfDayLowerMinutes[location.index] = lowerMinute == null ? 65535 : lowerMinute;
      location.chunk.analysisTimeOfDayUpperMinutes[location.index] = upperMinute == null ? 65535 : upperMinute;
      occurrences[valueCode] += 1;
      if (typed) typedRows += 1;
    });
    dictionaryRows.forEach(function (value, valueCode) {
      if (occurrences[valueCode] !== Number(value[13])) {
        throw new Error("Time-of-day dictionary occurrence parity failed for value " + valueCode + ".");
      }
    });
    if (typedRows !== Number(manifest.counts && manifest.counts.typedRows)) {
      throw new Error("Time-of-day typed-row parity failed.");
    }
    return { appliedRows: projectionRows.length, typedRows };
  }

  async function loadAnalysisTimeOfDayArtifact(message) {
    const urls = message.urls && typeof message.urls === "object" ? message.urls : {};
    const manifestUrl = String(urls.manifest || "./data/analysis_time_of_day_v1/manifest.json");
    const manifest = message.manifest && typeof message.manifest === "object"
      ? message.manifest
      : await fetchAnalysisJson(manifestUrl, { sha256: message.manifestSha256 || "" });
    if (!analysisTimeOfDayManifestSupported(manifest)) {
      throw new Error("Analysis time-of-day manifest is invalid or unsupported.");
    }
    const dictionaryRows = validateTimeOfDayRows(
      await fetchAnalysisJson(
        urls.dictionary || manifestArtifactUrl(manifest, "timeOfDayValueDictionary", manifestUrl),
        manifestArtifactIntegrity(manifest, "timeOfDayValueDictionary")
      ),
      manifest,
      "timeOfDayValueDictionary",
      14
    );
    const projectionRows = [];
    for (const key of manifest.artifactGroups.timeProjectionShards) {
      const shardRows = validateTimeOfDayRows(
        await fetchAnalysisJson(manifestArtifactUrl(manifest, key, manifestUrl), manifestArtifactIntegrity(manifest, key)),
        manifest,
        key,
        4
      );
      shardRows.forEach(function (row) { projectionRows.push(row); });
    }
    const applied = applyTimeOfDayProjection(dictionaryRows, projectionRows, manifest);
    const artifactHashes = {};
    Object.keys(manifest.artifacts).sort().forEach(function (key) {
      artifactHashes[key] = String(manifest.artifacts[key].sha256 || "");
    });
    analysisTimeOfDayArtifact = {
      manifest,
      loaded: true,
      appliedRows: applied.appliedRows,
      typedRows: applied.typedRows,
      releaseId: String(manifest.releaseId || ""),
      artifactHashes,
    };
    analysisCache.clear();
    analysisMatchCache.clear();
    return {
      loaded: true,
      appliedRows: applied.appliedRows,
      typedRows: applied.typedRows,
      releaseId: analysisTimeOfDayArtifact.releaseId,
      artifactHashes: Object.assign({}, artifactHashes),
      readinessStatus: String(manifest.readiness.status || "not_estimable"),
    };
  }

  function analysisWitnessCountManifestSupported(manifest) {
    return Boolean(
      manifest &&
      Number(manifest.schemaVersion) === 1 &&
      String(manifest.schemaId || "") === "ufo-timeline-analysis-witness-count-artifacts-v1.0.0" &&
      String(manifest.manifestVersion || "") === "1.0.0" &&
      manifest.artifacts && manifest.artifacts.witnessCountValueDictionary &&
      manifest.artifactGroups && Array.isArray(manifest.artifactGroups.witnessCountProjectionShards) &&
      manifest.artifactGroups.witnessCountProjectionShards.length > 0 &&
      manifest.codes && manifest.readiness
    );
  }

  function validateWitnessCountRows(rows, manifest, key, width) {
    const entry = manifestArtifactEntry(manifest, key);
    if (!entry || !normalizedSha256(entry.sha256) || !normalizedSha256(entry.gzipSha256)) {
      throw new Error("Witness-count artifact " + key + " is missing pinned integrity.");
    }
    if (!Array.isArray(entry.rowSchema) || entry.rowSchema.length !== width) {
      throw new Error("Witness-count artifact " + key + " has an invalid row schema.");
    }
    if (!Array.isArray(rows) || rows.length !== Number(entry.rowCount)) {
      throw new Error("Witness-count artifact " + key + " row-count mismatch.");
    }
    const invalidIndex = rows.findIndex(function (row) { return !Array.isArray(row) || row.length !== width; });
    if (invalidIndex !== -1) {
      throw new Error("Witness-count artifact " + key + " row " + invalidIndex + " has an invalid width.");
    }
    return rows;
  }

  function applyWitnessCountProjection(dictionaryRows, projectionRows, manifest) {
    const sourceCodes = manifest.codes.source || [];
    const statusCodes = manifest.codes.status || [];
    const binCodes = manifest.codes.witnessCountBin || [];
    const macroregionCodes = manifest.codes.macroregion || [];
    const occurrences = new Uint32Array(dictionaryRows.length);
    let previousRowIndex = -1;
    let chunkIndex = 0;
    let chunkStart = 0;
    let typedRows = 0;
    projectionRows.forEach(function (projection, projectionIndex) {
      const catalogRowIndex = Number(projection[0]);
      const valueCode = Number(projection[2]);
      const macroregionCode = Number(projection[3]);
      if (!Number.isInteger(catalogRowIndex) || catalogRowIndex <= previousRowIndex) {
        throw new Error("Witness-count projection row order is not strictly increasing at row " + projectionIndex + ".");
      }
      previousRowIndex = catalogRowIndex;
      while (chunkIndex < chunks.length && catalogRowIndex >= chunkStart + chunks[chunkIndex].length) {
        chunkStart += chunks[chunkIndex].length;
        chunkIndex += 1;
      }
      if (catalogRowIndex < 0 || catalogRowIndex >= rowCount || chunkIndex >= chunks.length) {
        throw new Error("Witness-count projection references an out-of-range catalog row.");
      }
      const location = { chunk: chunks[chunkIndex], index: catalogRowIndex - chunkStart };
      if (String(eventIdAt(location.chunk, location.index)) !== String(projection[1])) {
        throw new Error("Witness-count projection event ID does not match the served catalog at row " + catalogRowIndex + ".");
      }
      if (!Number.isInteger(valueCode) || valueCode < 0 || valueCode >= dictionaryRows.length ||
          !Number.isInteger(macroregionCode) || macroregionCode < 0 || macroregionCode >= macroregionCodes.length) {
        throw new Error("Witness-count projection contains an out-of-range code at row " + projectionIndex + ".");
      }
      const value = dictionaryRows[valueCode];
      const sourceCode = Number(value[0]);
      const statusCode = Number(value[3]);
      const descriptiveBinCode = Number(value[8]);
      if (!Number.isInteger(sourceCode) || sourceCode < 0 || sourceCode >= sourceCodes.length ||
          !Number.isInteger(statusCode) || statusCode < 0 || statusCode >= statusCodes.length ||
          !Number.isInteger(descriptiveBinCode) || descriptiveBinCode < 0 || descriptiveBinCode >= binCodes.length) {
        throw new Error("Witness-count dictionary code is out of range for value " + valueCode + ".");
      }
      const canonicalSource = dictionaryValue(dictionaries.source, location.chunk.sourceCodes[location.index]) || "unknown";
      if (String(sourceCodes[sourceCode] || "unknown") !== canonicalSource || canonicalSource !== "nuforc") {
        throw new Error("Witness-count dictionary source is not the explicit NUFORC lane at row " + catalogRowIndex + ".");
      }
      const status = String(statusCodes[statusCode] || "unresolved_text");
      const exactCount = value[5] == null ? null : Number(value[5]);
      const typed = ["exact_count", "approximate_count", "bounded_range", "lower_bound", "qualitative_plural"].indexOf(status) !== -1;
      if (status === "exact_count") {
        if (!Number.isInteger(exactCount) || exactCount <= 0 || exactCount > 4294967295 || String(binCodes[descriptiveBinCode]) === "unknown") {
          throw new Error("Exact witness-count row has an invalid positive integer at row " + projectionIndex + ".");
        }
      } else if (exactCount != null || String(binCodes[descriptiveBinCode]) !== "unknown") {
        throw new Error("Excluded witness-count value silently retains an exact count for value " + valueCode + ".");
      }
      location.chunk.analysisWitnessCountValueCodes[location.index] = valueCode + 1;
      location.chunk.analysisWitnessCountStatusCodes[location.index] = statusCode + 1;
      location.chunk.analysisWitnessCountBinCodes[location.index] = descriptiveBinCode + 1;
      location.chunk.analysisWitnessCountMacroregionCodes[location.index] = categoryCode(
        dictionaries.witnessCountMacroregion,
        String(macroregionCodes[macroregionCode] || "unknown")
      );
      location.chunk.analysisWitnessCountExactCounts[location.index] = exactCount == null ? 0 : exactCount;
      occurrences[valueCode] += 1;
      if (typed) typedRows += 1;
    });
    dictionaryRows.forEach(function (value, valueCode) {
      if (occurrences[valueCode] !== Number(value[12])) {
        throw new Error("Witness-count dictionary occurrence parity failed for value " + valueCode + ".");
      }
    });
    if (typedRows !== Number(manifest.counts && manifest.counts.typedRows)) {
      throw new Error("Witness-count typed-row parity failed.");
    }
    return { appliedRows: projectionRows.length, typedRows };
  }

  async function loadAnalysisWitnessCountArtifact(message) {
    const urls = message.urls && typeof message.urls === "object" ? message.urls : {};
    const manifestUrl = String(urls.manifest || "./data/analysis_witness_count_v1/manifest.json");
    const manifest = message.manifest && typeof message.manifest === "object"
      ? message.manifest
      : await fetchAnalysisJson(manifestUrl, { sha256: message.manifestSha256 || "" });
    if (!analysisWitnessCountManifestSupported(manifest)) {
      throw new Error("Analysis witness-count manifest is invalid or unsupported.");
    }
    const dictionaryRows = validateWitnessCountRows(
      await fetchAnalysisJson(
        urls.dictionary || manifestArtifactUrl(manifest, "witnessCountValueDictionary", manifestUrl),
        manifestArtifactIntegrity(manifest, "witnessCountValueDictionary")
      ),
      manifest,
      "witnessCountValueDictionary",
      13
    );
    const projectionRows = [];
    for (const key of manifest.artifactGroups.witnessCountProjectionShards) {
      const shardRows = validateWitnessCountRows(
        await fetchAnalysisJson(manifestArtifactUrl(manifest, key, manifestUrl), manifestArtifactIntegrity(manifest, key)),
        manifest,
        key,
        4
      );
      shardRows.forEach(function (row) { projectionRows.push(row); });
    }
    const applied = applyWitnessCountProjection(dictionaryRows, projectionRows, manifest);
    const artifactHashes = {};
    Object.keys(manifest.artifacts).sort().forEach(function (key) {
      artifactHashes[key] = String(manifest.artifacts[key].sha256 || "");
    });
    analysisWitnessCountArtifact = {
      manifest,
      loaded: true,
      appliedRows: applied.appliedRows,
      typedRows: applied.typedRows,
      releaseId: String(manifest.releaseId || ""),
      artifactHashes,
    };
    analysisCache.clear();
    analysisMatchCache.clear();
    return {
      loaded: true,
      appliedRows: applied.appliedRows,
      typedRows: applied.typedRows,
      releaseId: analysisWitnessCountArtifact.releaseId,
      artifactHashes: Object.assign({}, artifactHashes),
      readinessStatus: String(manifest.readiness.status || "not_estimable"),
    };
  }

  function analysisColorManifestSupported(manifest) {
    return Boolean(
      manifest &&
      Number(manifest.schemaVersion) === 1 &&
      String(manifest.schemaId || "") === "ufo-timeline-analysis-color-artifacts-v1.0.0" &&
      String(manifest.manifestVersion || "") === "1.0.0" &&
      manifest.artifacts && manifest.artifacts.colorValueDictionary && manifest.artifacts.colorProjection &&
      manifest.codes && Array.isArray(manifest.codes.category) && manifest.codes.category.length <= 16 &&
      manifest.readiness
    );
  }

  function validateColorRows(rows, manifest, key, width) {
    const entry = manifestArtifactEntry(manifest, key);
    if (!entry || !normalizedSha256(entry.sha256) || !normalizedSha256(entry.gzipSha256)) {
      throw new Error("Color artifact " + key + " is missing pinned integrity.");
    }
    if (!Array.isArray(entry.rowSchema) || entry.rowSchema.length !== width) {
      throw new Error("Color artifact " + key + " has an invalid row schema.");
    }
    if (!Array.isArray(rows) || rows.length !== Number(entry.rowCount)) {
      throw new Error("Color artifact " + key + " row-count mismatch.");
    }
    const invalidIndex = rows.findIndex(function (row) { return !Array.isArray(row) || row.length !== width; });
    if (invalidIndex !== -1) {
      throw new Error("Color artifact " + key + " row " + invalidIndex + " has an invalid width.");
    }
    return rows;
  }

  function bitCount16(value) {
    let bits = Number(value) & 65535;
    let count = 0;
    while (bits) {
      count += bits & 1;
      bits >>>= 1;
    }
    return count;
  }

  function applyColorProjection(dictionaryRows, projectionRows, manifest) {
    const sourceCodes = manifest.codes.source || [];
    const statusCodes = manifest.codes.status || [];
    const roleCodes = manifest.codes.role || [];
    const categoryCodes = manifest.codes.category || [];
    const eraCodes = manifest.codes.era || [];
    const macroregionCodes = manifest.codes.macroregion || [];
    const normalizedStatuses = new Set([
      "exact_single", "explicit_compound", "multicolor_unspecified", "changing_known", "changing_unspecified",
    ]);
    const maximumMask = (1 << categoryCodes.length) - 1;
    const occurrences = new Uint32Array(dictionaryRows.length);
    let previousRowIndex = -1;
    let chunkIndex = 0;
    let chunkStart = 0;
    let normalizedRows = 0;
    projectionRows.forEach(function (projection, projectionIndex) {
      const catalogRowIndex = Number(projection[0]);
      const valueCode = Number(projection[2]);
      const eraCode = Number(projection[3]);
      const macroregionCode = Number(projection[4]);
      if (!Number.isInteger(catalogRowIndex) || catalogRowIndex <= previousRowIndex) {
        throw new Error("Color projection row order is not strictly increasing at row " + projectionIndex + ".");
      }
      previousRowIndex = catalogRowIndex;
      while (chunkIndex < chunks.length && catalogRowIndex >= chunkStart + chunks[chunkIndex].length) {
        chunkStart += chunks[chunkIndex].length;
        chunkIndex += 1;
      }
      if (catalogRowIndex < 0 || catalogRowIndex >= rowCount || chunkIndex >= chunks.length) {
        throw new Error("Color projection references an out-of-range catalog row.");
      }
      const location = { chunk: chunks[chunkIndex], index: catalogRowIndex - chunkStart };
      if (String(eventIdAt(location.chunk, location.index)) !== String(projection[1])) {
        throw new Error("Color projection event ID does not match the served catalog at row " + catalogRowIndex + ".");
      }
      if (!Number.isInteger(valueCode) || valueCode < 0 || valueCode >= dictionaryRows.length ||
          !Number.isInteger(eraCode) || eraCode < 0 || eraCode >= eraCodes.length ||
          !Number.isInteger(macroregionCode) || macroregionCode < 0 || macroregionCode >= macroregionCodes.length) {
        throw new Error("Color projection contains an out-of-range code at row " + projectionIndex + ".");
      }
      const value = dictionaryRows[valueCode];
      const sourceCode = Number(value[0]);
      const statusCode = Number(value[3]);
      const roleCode = Number(value[5]);
      const categoryMask = Number(value[6]);
      const changing = Number(value[7]);
      const multicolor = Number(value[8]);
      const compound = Number(value[9]);
      if (!Number.isInteger(sourceCode) || sourceCode < 0 || sourceCode >= sourceCodes.length ||
          !normalizedSha256(value[1]) || typeof value[2] !== "string" ||
          !Number.isInteger(statusCode) || statusCode < 0 || statusCode >= statusCodes.length ||
          !Number.isInteger(roleCode) || roleCode < 0 || roleCode >= roleCodes.length ||
          !Number.isInteger(categoryMask) || categoryMask < 0 || categoryMask > maximumMask ||
          [changing, multicolor, compound].some(function (flag) { return flag !== 0 && flag !== 1; })) {
        throw new Error("Color dictionary code or flag is invalid for value " + valueCode + ".");
      }
      const canonicalSource = dictionaryValue(dictionaries.source, location.chunk.sourceCodes[location.index]) || "unknown";
      if (String(sourceCodes[sourceCode] || "unknown") !== canonicalSource) {
        throw new Error("Color dictionary source does not match the served catalog at row " + catalogRowIndex + ".");
      }
      const status = String(statusCodes[statusCode] || "unparsed");
      const categoryCount = bitCount16(categoryMask);
      if ((status === "exact_single" && categoryCount !== 1) ||
          (status === "explicit_compound" && categoryCount < 2) ||
          (status === "changing_known" && categoryCount < 1) ||
          (["changing_unspecified", "non_color_descriptor", "unparsed"].indexOf(status) !== -1 && categoryCount !== 0) ||
          (status === "multicolor_unspecified" && categoryCount >= 2)) {
        throw new Error("Color status/category semantics failed closed for value " + valueCode + ".");
      }
      location.chunk.analysisColorValueCodes[location.index] = valueCode + 1;
      location.chunk.analysisColorStatusCodes[location.index] = statusCode + 1;
      location.chunk.analysisColorRoleCodes[location.index] = roleCode + 1;
      location.chunk.analysisColorCategoryMasks[location.index] = categoryMask;
      location.chunk.analysisColorFlags[location.index] = changing | (multicolor << 1) | (compound << 2);
      location.chunk.analysisColorMacroregionCodes[location.index] = categoryCode(
        dictionaries.colorMacroregion,
        String(macroregionCodes[macroregionCode] || "unknown")
      );
      occurrences[valueCode] += 1;
      if (normalizedStatuses.has(status)) normalizedRows += 1;
    });
    dictionaryRows.forEach(function (value, valueCode) {
      if (occurrences[valueCode] !== Number(value[10])) {
        throw new Error("Color dictionary occurrence parity failed for value " + valueCode + ".");
      }
    });
    if (normalizedRows !== Number(manifest.counts && manifest.counts.normalizedRows)) {
      throw new Error("Color normalized-row parity failed.");
    }
    return { appliedRows: projectionRows.length, normalizedRows };
  }

  async function loadAnalysisColorArtifact(message) {
    const urls = message.urls && typeof message.urls === "object" ? message.urls : {};
    const manifestUrl = String(urls.manifest || "./data/analysis_color_v1/manifest.json");
    const manifest = message.manifest && typeof message.manifest === "object"
      ? message.manifest
      : await fetchAnalysisJson(manifestUrl, { sha256: message.manifestSha256 || "" });
    if (!analysisColorManifestSupported(manifest)) {
      throw new Error("Analysis color manifest is invalid or unsupported.");
    }
    const dictionaryRows = validateColorRows(
      await fetchAnalysisJson(
        urls.dictionary || manifestArtifactUrl(manifest, "colorValueDictionary", manifestUrl),
        manifestArtifactIntegrity(manifest, "colorValueDictionary")
      ),
      manifest,
      "colorValueDictionary",
      11
    );
    const projectionRows = validateColorRows(
      await fetchAnalysisJson(
        urls.projection || manifestArtifactUrl(manifest, "colorProjection", manifestUrl),
        manifestArtifactIntegrity(manifest, "colorProjection")
      ),
      manifest,
      "colorProjection",
      5
    );
    const applied = applyColorProjection(dictionaryRows, projectionRows, manifest);
    const artifactHashes = {};
    Object.keys(manifest.artifacts).sort().forEach(function (key) {
      artifactHashes[key] = String(manifest.artifacts[key].sha256 || "");
    });
    analysisColorArtifact = {
      manifest,
      loaded: true,
      appliedRows: applied.appliedRows,
      normalizedRows: applied.normalizedRows,
      releaseId: String(manifest.releaseId || ""),
      artifactHashes,
    };
    analysisCache.clear();
    analysisMatchCache.clear();
    return {
      loaded: true,
      appliedRows: applied.appliedRows,
      normalizedRows: applied.normalizedRows,
      releaseId: analysisColorArtifact.releaseId,
      artifactHashes: Object.assign({}, artifactHashes),
      readinessStatus: String(manifest.readiness.status || "not_estimable"),
    };
  }

  function analysisReportingDelayManifestSupported(manifest) {
    return Boolean(
      manifest &&
      Number(manifest.schemaVersion) === 1 &&
      String(manifest.schemaId || "") === "ufo-timeline-analysis-reporting-delay-artifacts-v1.0.0" &&
      String(manifest.manifestVersion || "") === "1.0.0" &&
      manifest.artifacts &&
      manifest.artifacts.reportingDelayProjection &&
      manifest.artifactGroups &&
      Array.isArray(manifest.artifactGroups.roleEvidenceShards) &&
      manifest.codes &&
      manifest.readiness
    );
  }

  function validateReportingDelayManifest(manifest) {
    const projectionEntry = manifestArtifactEntry(manifest, "reportingDelayProjection");
    if (!projectionEntry || !normalizedSha256(projectionEntry.sha256) || !normalizedSha256(projectionEntry.gzipSha256)) {
      throw new Error("Reporting-delay projection is missing pinned raw or gzip integrity.");
    }
    if (!Array.isArray(projectionEntry.rowSchema) || projectionEntry.rowSchema.length !== 9) {
      throw new Error("Reporting-delay projection schema is invalid.");
    }
    let evidenceRows = 0;
    manifest.artifactGroups.roleEvidenceShards.forEach(function (key) {
      const entry = manifestArtifactEntry(manifest, key);
      if (!entry || !normalizedSha256(entry.sha256) || !normalizedSha256(entry.gzipSha256)) {
        throw new Error("Reporting-delay role-evidence shard " + key + " is invalid.");
      }
      if (!Array.isArray(entry.rowSchema) || entry.rowSchema.length !== 13) {
        throw new Error("Reporting-delay role-evidence shard " + key + " has an invalid schema.");
      }
      evidenceRows += Number(entry.rowCount) || 0;
    });
    if (evidenceRows !== Number(projectionEntry.rowCount) ||
        evidenceRows !== Number(manifest.counts && manifest.counts.dateRoleEvidenceRows)) {
      throw new Error("Reporting-delay projection and role-evidence row counts disagree.");
    }
    return projectionEntry;
  }

  function applyReportingDelayProjection(projectionRows, manifest) {
    const statusCodes = manifest.codes.status || [];
    const roleCodes = manifest.codes.selectedRole || [];
    const binCodes = manifest.codes.delayBin || [];
    const sourceCodes = manifest.codes.source || [];
    const eraCodes = manifest.codes.era || [];
    const macroregionCodes = manifest.codes.macroregion || [];
    let previousRowIndex = -1;
    let chunkIndex = 0;
    let chunkStart = 0;
    let typedRows = 0;
    projectionRows.forEach(function (projection, projectionIndex) {
      const catalogRowIndex = Number(projection[0]);
      const sourceCode = Number(projection[2]);
      const eraCode = Number(projection[3]);
      const macroregionCode = Number(projection[4]);
      const roleCode = Number(projection[5]);
      const statusCode = Number(projection[6]);
      const delayDays = projection[7] == null ? null : Number(projection[7]);
      const binCode = Number(projection[8]);
      if (!Number.isInteger(catalogRowIndex) || catalogRowIndex <= previousRowIndex) {
        throw new Error("Reporting-delay projection row order is not strictly increasing at row " + projectionIndex + ".");
      }
      previousRowIndex = catalogRowIndex;
      while (chunkIndex < chunks.length && catalogRowIndex >= chunkStart + chunks[chunkIndex].length) {
        chunkStart += chunks[chunkIndex].length;
        chunkIndex += 1;
      }
      if (catalogRowIndex < 0 || catalogRowIndex >= rowCount || chunkIndex >= chunks.length) {
        throw new Error("Reporting-delay projection references an out-of-range catalog row.");
      }
      const location = { chunk: chunks[chunkIndex], index: catalogRowIndex - chunkStart };
      if (String(eventIdAt(location.chunk, location.index)) !== String(projection[1])) {
        throw new Error("Reporting-delay projection event ID does not match the served catalog at row " + catalogRowIndex + ".");
      }
      if (!Number.isInteger(sourceCode) || sourceCode < 0 || sourceCode >= sourceCodes.length ||
          !Number.isInteger(eraCode) || eraCode < 0 || eraCode >= eraCodes.length ||
          !Number.isInteger(macroregionCode) || macroregionCode < 0 || macroregionCode >= macroregionCodes.length ||
          !Number.isInteger(roleCode) || roleCode < 0 || roleCode >= roleCodes.length ||
          !Number.isInteger(statusCode) || statusCode < 0 || statusCode >= statusCodes.length ||
          !Number.isInteger(binCode) || binCode < 0 || binCode >= binCodes.length) {
        throw new Error("Reporting-delay projection contains an out-of-range code at row " + projectionIndex + ".");
      }
      const canonicalSource = dictionaryValue(dictionaries.source, location.chunk.sourceCodes[location.index]) || "unknown";
      if (String(sourceCodes[sourceCode] || "unknown") !== canonicalSource) {
        throw new Error("Reporting-delay projection source does not match the served catalog at row " + catalogRowIndex + ".");
      }
      const status = String(statusCodes[statusCode] || "unavailable");
      const typed = ["reported_valid", "posted_fallback_valid"].indexOf(status) !== -1;
      if (typed) {
        if (!Number.isInteger(delayDays) || delayDays < 0 || String(binCodes[binCode] || "unknown") === "unknown") {
          throw new Error("Typed reporting-delay row has an invalid delay at row " + projectionIndex + ".");
        }
        typedRows += 1;
      } else if (delayDays != null || String(binCodes[binCode] || "unknown") !== "unknown") {
        throw new Error("Excluded reporting-delay row silently retains a typed delay at row " + projectionIndex + ".");
      }
      location.chunk.analysisReportingDelayProjectionStates[location.index] = 1;
      location.chunk.analysisReportingDelayStatusCodes[location.index] = statusCode + 1;
      location.chunk.analysisReportingDelayRoleCodes[location.index] = roleCode + 1;
      location.chunk.analysisReportingDelayBinCodes[location.index] = binCode + 1;
      location.chunk.analysisReportingDelayMacroregionCodes[location.index] = categoryCode(
        dictionaries.reportingDelayMacroregion,
        String(macroregionCodes[macroregionCode] || "unknown")
      );
      location.chunk.analysisReportingDelayDays[location.index] = typed ? delayDays : 0;
    });
    if (typedRows !== Number(manifest.counts && manifest.counts.typedRows)) {
      throw new Error("Reporting-delay typed-row parity failed.");
    }
    return { appliedRows: projectionRows.length, typedRows };
  }

  async function loadAnalysisReportingDelayArtifact(message) {
    const urls = message.urls && typeof message.urls === "object" ? message.urls : {};
    const manifestUrl = String(urls.manifest || "./data/analysis_reporting_delay_v1/manifest.json");
    const manifest = message.manifest && typeof message.manifest === "object"
      ? message.manifest
      : await fetchAnalysisJson(manifestUrl, { sha256: message.manifestSha256 || "" });
    if (!analysisReportingDelayManifestSupported(manifest)) {
      throw new Error("Analysis reporting-delay manifest is invalid or unsupported.");
    }
    const projectionEntry = validateReportingDelayManifest(manifest);
    const projectionRows = await fetchAnalysisJson(
      urls.projection || manifestArtifactUrl(manifest, "reportingDelayProjection", manifestUrl),
      manifestArtifactIntegrity(manifest, "reportingDelayProjection")
    );
    if (!Array.isArray(projectionRows) || projectionRows.length !== Number(projectionEntry.rowCount) ||
        projectionRows.some(function (row) { return !Array.isArray(row) || row.length !== 9; })) {
      throw new Error("Reporting-delay projection row-count or schema mismatch.");
    }
    const applied = applyReportingDelayProjection(projectionRows, manifest);
    const artifactHashes = {};
    Object.keys(manifest.artifacts).sort().forEach(function (key) {
      artifactHashes[key] = String(manifest.artifacts[key].sha256 || "");
    });
    analysisReportingDelayArtifact = {
      manifest,
      loaded: true,
      appliedRows: applied.appliedRows,
      typedRows: applied.typedRows,
      releaseId: String(manifest.releaseId || ""),
      artifactHashes,
    };
    analysisCache.clear();
    analysisMatchCache.clear();
    return {
      loaded: true,
      appliedRows: applied.appliedRows,
      typedRows: applied.typedRows,
      releaseId: analysisReportingDelayArtifact.releaseId,
      artifactHashes: Object.assign({}, artifactHashes),
      readinessStatus: String(manifest.readiness.status || "not_estimable"),
    };
  }

  function analysisCoordinateEvidenceManifestSupported(manifest) {
    return Boolean(
      manifest &&
      Number(manifest.schemaVersion) === 1 &&
      String(manifest.schemaId || "") === "ufo-timeline-analysis-coordinate-evidence-artifacts-v1.0.0" &&
      String(manifest.manifestVersion || "") === "1.0.0" &&
      manifest.artifacts &&
      manifest.artifacts.coordinateEvidenceProjection &&
      manifest.artifactGroups &&
      Array.isArray(manifest.artifactGroups.originalEvidenceShards) &&
      manifest.codes &&
      manifest.readiness &&
      manifest.policy &&
      manifest.policy.canonicalEventsMutated === false &&
      manifest.policy.externalGeocodingUsed === false &&
      manifest.policy.precisionPromotionAllowed === false &&
      manifest.policy.generalizedMarkersCountAsSourceCoordinates === false
    );
  }

  function validateCoordinateEvidenceManifest(manifest) {
    const projectionEntry = manifestArtifactEntry(manifest, "coordinateEvidenceProjection");
    if (!projectionEntry || !normalizedSha256(projectionEntry.sha256) || !normalizedSha256(projectionEntry.gzipSha256)) {
      throw new Error("Coordinate-evidence projection is missing pinned raw or gzip integrity.");
    }
    if (!Array.isArray(projectionEntry.rowSchema) || projectionEntry.rowSchema.length !== 11) {
      throw new Error("Coordinate-evidence projection schema is invalid.");
    }
    let evidenceRows = 0;
    manifest.artifactGroups.originalEvidenceShards.forEach(function (key) {
      const entry = manifestArtifactEntry(manifest, key);
      if (!entry || !normalizedSha256(entry.sha256) || !normalizedSha256(entry.gzipSha256)) {
        throw new Error("Coordinate original-evidence shard " + key + " is invalid.");
      }
      if (!Array.isArray(entry.rowSchema) || entry.rowSchema.length !== 18) {
        throw new Error("Coordinate original-evidence shard " + key + " has an invalid schema.");
      }
      evidenceRows += Number(entry.rowCount) || 0;
    });
    if (evidenceRows !== Number(projectionEntry.rowCount) ||
        evidenceRows !== Number(manifest.counts && manifest.counts.sourceCoordinateRows)) {
      throw new Error("Coordinate projection and original-evidence row counts disagree.");
    }
    return projectionEntry;
  }

  function applyCoordinateEvidenceProjection(projectionRows, manifest) {
    const sourceCodes = manifest.codes.source || [];
    const eraCodes = manifest.codes.era || [];
    const macroregionCodes = manifest.codes.macroregion || [];
    const statusCodes = manifest.codes.status || [];
    const consistencyCodes = manifest.codes.countryConsistency || [];
    const qualityCodes = manifest.codes.qualityBin || [];
    let previousRowIndex = -1;
    let chunkIndex = 0;
    let chunkStart = 0;
    let typedRows = 0;
    projectionRows.forEach(function (projection, projectionIndex) {
      const catalogRowIndex = Number(projection[0]);
      const sourceCode = Number(projection[2]);
      const eraCode = Number(projection[3]);
      const macroregionCode = Number(projection[4]);
      const statusCode = Number(projection[5]);
      const consistencyCode = Number(projection[6]);
      const qualityCode = Number(projection[7]);
      const riskFlags = Number(projection[8]);
      const latitude = Number(projection[9]);
      const longitude = Number(projection[10]);
      if (!Number.isInteger(catalogRowIndex) || catalogRowIndex <= previousRowIndex) {
        throw new Error("Coordinate-evidence projection row order is not strictly increasing at row " + projectionIndex + ".");
      }
      previousRowIndex = catalogRowIndex;
      while (chunkIndex < chunks.length && catalogRowIndex >= chunkStart + chunks[chunkIndex].length) {
        chunkStart += chunks[chunkIndex].length;
        chunkIndex += 1;
      }
      if (catalogRowIndex < 0 || catalogRowIndex >= rowCount || chunkIndex >= chunks.length) {
        throw new Error("Coordinate-evidence projection references an out-of-range catalog row.");
      }
      const location = { chunk: chunks[chunkIndex], index: catalogRowIndex - chunkStart };
      if (String(eventIdAt(location.chunk, location.index)) !== String(projection[1])) {
        throw new Error("Coordinate-evidence event ID does not match the served catalog at row " + catalogRowIndex + ".");
      }
      if (!Number.isInteger(sourceCode) || sourceCode < 0 || sourceCode >= sourceCodes.length ||
          !Number.isInteger(eraCode) || eraCode < 0 || eraCode >= eraCodes.length ||
          !Number.isInteger(macroregionCode) || macroregionCode < 0 || macroregionCode >= macroregionCodes.length ||
          !Number.isInteger(statusCode) || statusCode < 0 || statusCode >= statusCodes.length ||
          !Number.isInteger(consistencyCode) || consistencyCode < 0 || consistencyCode >= consistencyCodes.length ||
          !Number.isInteger(qualityCode) || qualityCode < 0 || qualityCode >= qualityCodes.length ||
          !Number.isInteger(riskFlags) || riskFlags < 0 || riskFlags > 255 ||
          !Number.isFinite(latitude) || latitude < -90 || latitude > 90 ||
          !Number.isFinite(longitude) || longitude < -180 || longitude > 180) {
        throw new Error("Coordinate-evidence projection contains an invalid code or value at row " + projectionIndex + ".");
      }
      const canonicalSource = dictionaryValue(dictionaries.source, location.chunk.sourceCodes[location.index]) || "unknown";
      const canonicalCoordinateSource = dictionaryValue(
        dictionaries.coordinateSource,
        location.chunk.coordinateSourceCodes[location.index]
      ) || "unresolved";
      if (String(sourceCodes[sourceCode] || "unknown") !== canonicalSource || canonicalCoordinateSource !== "raw_latlong") {
        throw new Error("Coordinate-evidence origin does not match the served catalog at row " + catalogRowIndex + ".");
      }
      if (Math.abs(location.chunk.latitudes[location.index] - latitude) > 1e-9 ||
          Math.abs(location.chunk.longitudes[location.index] - longitude) > 1e-9) {
        throw new Error("Coordinate-evidence values do not match the served catalog at row " + catalogRowIndex + ".");
      }
      const status = String(statusCodes[statusCode] || "unavailable");
      if (["typed_country_consistent", "typed_country_unchecked"].indexOf(status) !== -1) typedRows += 1;
      location.chunk.analysisCoordinateEvidenceProjectionStates[location.index] = 1;
      location.chunk.analysisCoordinateEvidenceStatusCodes[location.index] = statusCode + 1;
      location.chunk.analysisCoordinateEvidenceConsistencyCodes[location.index] = consistencyCode + 1;
      location.chunk.analysisCoordinateEvidenceQualityBinCodes[location.index] = qualityCode + 1;
      location.chunk.analysisCoordinateEvidenceRiskFlags[location.index] = riskFlags;
      location.chunk.analysisCoordinateEvidenceMacroregionCodes[location.index] = categoryCode(
        dictionaries.coordinateEvidenceMacroregion,
        String(macroregionCodes[macroregionCode] || "unknown")
      );
    });
    if (typedRows !== Number(manifest.counts && manifest.counts.typedRows)) {
      throw new Error("Coordinate-evidence typed-row parity failed.");
    }
    return { appliedRows: projectionRows.length, typedRows };
  }

  async function loadAnalysisCoordinateEvidenceArtifact(message) {
    const urls = message.urls && typeof message.urls === "object" ? message.urls : {};
    const manifestUrl = String(urls.manifest || "./data/analysis_coordinate_evidence_v1/manifest.json");
    const manifest = message.manifest && typeof message.manifest === "object"
      ? message.manifest
      : await fetchAnalysisJson(manifestUrl, { sha256: message.manifestSha256 || "" });
    if (!analysisCoordinateEvidenceManifestSupported(manifest)) {
      throw new Error("Analysis coordinate-evidence manifest is invalid or unsupported.");
    }
    const projectionEntry = validateCoordinateEvidenceManifest(manifest);
    const projectionRows = await fetchAnalysisJson(
      urls.projection || manifestArtifactUrl(manifest, "coordinateEvidenceProjection", manifestUrl),
      manifestArtifactIntegrity(manifest, "coordinateEvidenceProjection")
    );
    if (!Array.isArray(projectionRows) || projectionRows.length !== Number(projectionEntry.rowCount) ||
        projectionRows.some(function (row) { return !Array.isArray(row) || row.length !== 11; })) {
      throw new Error("Coordinate-evidence projection row-count or schema mismatch.");
    }
    const applied = applyCoordinateEvidenceProjection(projectionRows, manifest);
    const artifactHashes = {};
    Object.keys(manifest.artifacts).sort().forEach(function (key) {
      artifactHashes[key] = String(manifest.artifacts[key].sha256 || "");
    });
    analysisCoordinateEvidenceArtifact = {
      manifest,
      loaded: true,
      appliedRows: applied.appliedRows,
      typedRows: applied.typedRows,
      releaseId: String(manifest.releaseId || ""),
      artifactHashes,
    };
    analysisCache.clear();
    analysisMatchCache.clear();
    return {
      loaded: true,
      appliedRows: applied.appliedRows,
      typedRows: applied.typedRows,
      releaseId: analysisCoordinateEvidenceArtifact.releaseId,
      artifactHashes: Object.assign({}, artifactHashes),
      readinessStatus: String(manifest.readiness.status || "not_estimable"),
    };
  }

  function applyGeographyRowsToCatalog(rowsValue, manifest) {
    const rows = Array.isArray(rowsValue) ? rowsValue : [];
    const codes = manifest && manifest.codes && manifest.codes.ufoGeography || {};
    let cursor = 0;
    chunks.forEach(function (chunk) {
      for (let index = 0; index < chunk.length; index += 1) {
        if (chunk.mappedStates[index] !== 2) continue;
        const packed = rows[cursor];
        if (!Array.isArray(packed)) {
          throw new Error("The geography projection ended before the mapped catalog subsequence.");
        }
        if (Number(packed[0]) !== cursor) {
          throw new Error("The geography projection row index is not contiguous at mapped row " + cursor + ".");
        }
        const catalogEventId = String(eventIdAt(chunk, index));
        const geographyEventId = String(packed[1] == null ? "" : packed[1]);
        if (!catalogEventId || catalogEventId !== geographyEventId) {
          throw new Error(
            "The geography projection does not match the served mapped-event order at row " + cursor + "."
          );
        }
        chunk.analysisCountryCodes[index] = categoryCode(
          dictionaries.analysisCountry,
          decodeCode(codes, "country", packed[2]) || "unknown"
        );
        chunk.analysisMacroregionCodes[index] = categoryCode(
          dictionaries.analysisMacroregion,
          decodeCode(codes, "macroregion", packed[3]) || "unknown"
        );
        chunk.analysisGeographyAssignmentSourceCodes[index] = categoryCode(
          dictionaries.geographyAssignmentSource,
          decodeCode(codes, "assignmentSource", packed[4]) || "unknown"
        );
        chunk.analysisGeographyAssignmentConfidenceCodes[index] = categoryCode(
          dictionaries.geographyAssignmentConfidence,
          decodeCode(codes, "assignmentConfidence", packed[5]) || "unknown"
        );
        chunk.analysisGeographyBoundaryStatusCodes[index] = categoryCode(
          dictionaries.geographyBoundaryStatus,
          decodeCode(codes, "boundaryStatus", packed[6]) || "unknown"
        );
        cursor += 1;
      }
    });
    if (cursor !== rows.length) {
      throw new Error(
        "The geography projection contains " + rows.length +
        " mapped rows but the served catalog contains " + cursor + "."
      );
    }
    return cursor;
  }

  function decodeGeographyBinary(bytesValue, manifest) {
    const bytes = bytesValue instanceof Uint8Array ? bytesValue : new Uint8Array(bytesValue || 0);
    const entry = geographyBinaryEntry(manifest);
    if (!entry || String(entry.format || "") !== "ufo_geography_columnar_v1") {
      throw new Error("The geography binary encoding is missing or unsupported.");
    }
    const expectedMagic = [0x55, 0x46, 0x4f, 0x47, 0x45, 0x4f, 0x31, 0x00];
    if (bytes.length < 32 || expectedMagic.some(function (value, index) { return bytes[index] !== value; })) {
      throw new Error("The geography binary header magic is invalid.");
    }
    const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    const version = view.getUint32(8, true);
    const rowCount = view.getUint32(12, true);
    const pointRowBase = view.getUint32(16, true);
    const logicalColumnCount = view.getUint32(20, true);
    const codeColumnCount = view.getUint32(24, true);
    const headerBytes = view.getUint32(28, true);
    if (version !== 1 || pointRowBase !== 0 || logicalColumnCount !== 8 ||
        codeColumnCount !== 6 || headerBytes !== 32) {
      throw new Error("The geography binary header contract is invalid or unsupported.");
    }
    if (rowCount !== Number(manifest.artifacts.ufoGeography.rowCount)) {
      throw new Error("The geography binary row count does not match the signed manifest.");
    }
    const expectedBytes = headerBytes + rowCount * 8 + rowCount * codeColumnCount;
    if (bytes.length !== expectedBytes || Number(entry.bytes) !== expectedBytes) {
      throw new Error("The geography binary byte length does not match its format contract.");
    }
    const lowOffset = headerBytes;
    const highOffset = lowOffset + rowCount * 4;
    const codeOffset = highOffset + rowCount * 4;
    const codeColumns = [];
    for (let codeIndex = 0; codeIndex < codeColumnCount; codeIndex += 1) {
      codeColumns.push(new Uint8Array(
        bytes.buffer,
        bytes.byteOffset + codeOffset + codeIndex * rowCount,
        rowCount
      ));
    }
    return {
      bytes,
      view,
      rowCount,
      lowOffset,
      highOffset,
      codeColumns,
      format: "ufo_geography_columnar_v1",
    };
  }

  function geographyBinaryEventId(projection, index) {
    const low = projection.view.getUint32(projection.lowOffset + index * 4, true);
    const high = projection.view.getUint32(projection.highOffset + index * 4, true);
    const eventId = high * 4294967296 + low;
    if (!Number.isSafeInteger(eventId) || eventId < 0) {
      throw new Error("The geography binary contains an unsafe event ID at row " + index + ".");
    }
    return eventId;
  }

  function applyGeographyBinaryToCatalog(projection, manifest) {
    const codes = manifest && manifest.codes && manifest.codes.ufoGeography || {};
    const columns = projection.codeColumns;
    let cursor = 0;
    chunks.forEach(function (chunk) {
      for (let index = 0; index < chunk.length; index += 1) {
        if (chunk.mappedStates[index] !== 2) continue;
        if (cursor >= projection.rowCount) {
          throw new Error("The geography binary ended before the mapped catalog subsequence.");
        }
        const catalogEventId = String(eventIdAt(chunk, index));
        const geographyEventId = String(geographyBinaryEventId(projection, cursor));
        if (!catalogEventId || catalogEventId !== geographyEventId) {
          throw new Error(
            "The geography binary does not match the served mapped-event order at row " + cursor + "."
          );
        }
        chunk.analysisCountryCodes[index] = categoryCode(
          dictionaries.analysisCountry,
          decodeCode(codes, "country", columns[0][cursor]) || "unknown"
        );
        chunk.analysisMacroregionCodes[index] = categoryCode(
          dictionaries.analysisMacroregion,
          decodeCode(codes, "macroregion", columns[1][cursor]) || "unknown"
        );
        chunk.analysisGeographyAssignmentSourceCodes[index] = categoryCode(
          dictionaries.geographyAssignmentSource,
          decodeCode(codes, "assignmentSource", columns[2][cursor]) || "unknown"
        );
        chunk.analysisGeographyAssignmentConfidenceCodes[index] = categoryCode(
          dictionaries.geographyAssignmentConfidence,
          decodeCode(codes, "assignmentConfidence", columns[3][cursor]) || "unknown"
        );
        chunk.analysisGeographyBoundaryStatusCodes[index] = categoryCode(
          dictionaries.geographyBoundaryStatus,
          decodeCode(codes, "boundaryStatus", columns[4][cursor]) || "unknown"
        );
        // coordinateEvidence is a retained logical parity column. Its runtime
        // value already lives on the catalog row, but the code must remain
        // decodable so sentinel and source-coordinate semantics cannot drift.
        if (!decodeCode(codes, "coordinateEvidence", columns[5][cursor])) {
          throw new Error("The geography binary contains an invalid coordinate-evidence code at row " + cursor + ".");
        }
        cursor += 1;
      }
    });
    if (cursor !== projection.rowCount) {
      throw new Error(
        "The geography binary contains " + projection.rowCount +
        " mapped rows but the served catalog contains " + cursor + "."
      );
    }
    return cursor;
  }

  async function loadAnalysisGeographyArtifact(message) {
    const urls = message.urls && typeof message.urls === "object" ? message.urls : {};
    const manifestUrl = String(urls.manifest || "./data/analysis_v2/manifest.json");
    const manifest = message.manifest && typeof message.manifest === "object"
      ? message.manifest
      : await fetchAnalysisJson(manifestUrl, { sha256: message.manifestSha256 || "" });
    if (!analysisV2ManifestSupported(manifest)) {
      throw new Error("Analysis v2 geography manifest is invalid or unsupported.");
    }
    validateSpatialManifestArtifact(manifest, "ufoGeography");
    const binaryEntry = geographyBinaryEntry(manifest);
    let appliedRows = 0;
    let encodingHash = "";
    if (binaryEntry) {
      const binaryUrl = urls.geographyBinary || geographyBinaryUrl(manifest, manifestUrl);
      if (!binaryUrl) throw new Error("Analysis v2.2 manifest is missing the geography binary URL.");
      const binaryBytes = await fetchAnalysisBinary(binaryUrl, geographyBinaryIntegrity(manifest));
      const projection = decodeGeographyBinary(binaryBytes, manifest);
      appliedRows = applyGeographyBinaryToCatalog(projection, manifest);
      encodingHash = String(binaryEntry.sha256 || "");
    } else {
      const artifactUrl = urls.geography || urls.ufoGeography ||
        manifestArtifactUrl(manifest, "ufoGeography", manifestUrl);
      if (!artifactUrl) throw new Error("Analysis v2.2 manifest is missing the geography projection URL.");
      const payload = await fetchAnalysisJson(
        artifactUrl,
        manifestArtifactIntegrity(manifest, "ufoGeography")
      );
      const rows = validateLoadedSpatialArtifact(payload, manifest, "ufoGeography");
      appliedRows = applyGeographyRowsToCatalog(rows, manifest);
    }
    analysisGeographyArtifact = {
      manifest,
      rows: null,
      codes: manifest.codes && manifest.codes.ufoGeography || {},
      loaded: true,
      appliedRows,
      artifactHash: String(manifest.artifacts.ufoGeography.sha256 || ""),
      encodingHash,
    };
    analysisCache.clear();
    analysisMatchCache.clear();
    return {
      loaded: true,
      appliedRows,
      releaseId: String(manifest.releaseId || ""),
      artifactHash: analysisGeographyArtifact.artifactHash,
      encodingHash: analysisGeographyArtifact.encodingHash,
      rowOrder: "packed_points_input_order_mapped_catalog_subsequence",
    };
  }

  async function loadAnalysisSpatialArtifactsInternal(message) {
    const loadEpoch = ++analysisSpatialArtifactLoadEpoch;
    analysisPartialArtifactLoadEpoch.relationship += 1;
    analysisPartialArtifactLoadEpoch.context += 1;
    const urls = message.urls && typeof message.urls === "object" ? message.urls : {};
    const manifestUrl = String(urls.manifest || "./data/analysis_v2/manifest.json");
    const manifest = message.manifest && typeof message.manifest === "object"
      ? message.manifest
      : await fetchAnalysisJson(manifestUrl, { sha256: message.manifestSha256 || "" });
    if (!analysisV2ManifestSupported(manifest)) {
      throw new Error("Analysis v2 spatial manifest is invalid or unsupported.");
    }
    const requiredArtifactKeys = [
      "ufoPointNeighbors", "facilityAnalysis", "relationshipReconciliation",
      "ufoSpatialPoints", "contextUfoNeighbors",
    ];
    const configurationAvailable = Boolean(
      manifest.artifacts.ufoConfigurationPoints && manifest.artifacts.ufoConfigurationNeighbors
    );
    if (String(manifest.manifestVersion || "") === "2.2.0" && !configurationAvailable) {
      throw new Error("Analysis v2.2 manifest is missing Formation/configuration artifacts.");
    }
    if (configurationAvailable) {
      requiredArtifactKeys.push("ufoConfigurationPoints", "ufoConfigurationNeighbors");
    }
    requiredArtifactKeys.forEach(function (key) { validateSpatialManifestArtifact(manifest, key); });
    const neighborUrl = urls.neighbors || manifestArtifactUrl(manifest, "ufoPointNeighbors", manifestUrl);
    const facilityUrl = urls.facilities || manifestArtifactUrl(manifest, "facilityAnalysis", manifestUrl);
    const relationshipUrl = urls.relationshipReconciliation || urls.relationships ||
      manifestArtifactUrl(manifest, "relationshipReconciliation", manifestUrl);
    const spatialPointsUrl = urls.spatialPoints || urls.ufoSpatialPoints ||
      manifestArtifactUrl(manifest, "ufoSpatialPoints", manifestUrl);
    const contextNeighborsUrl = urls.contextNeighbors || urls.contextUfoNeighbors ||
      manifestArtifactUrl(manifest, "contextUfoNeighbors", manifestUrl);
    const configurationPointsUrl = configurationAvailable
      ? (urls.configurationPoints || urls.ufoConfigurationPoints ||
        manifestArtifactUrl(manifest, "ufoConfigurationPoints", manifestUrl))
      : "";
    const configurationNeighborsUrl = configurationAvailable
      ? (urls.configurationNeighbors || urls.ufoConfigurationNeighbors ||
        manifestArtifactUrl(manifest, "ufoConfigurationNeighbors", manifestUrl))
      : "";
    if (!neighborUrl || !facilityUrl || !relationshipUrl || !spatialPointsUrl || !contextNeighborsUrl) {
      throw new Error("Analysis v2 manifest is missing one or more required artifact URLs.");
    }
    const cachedRelationshipRows = !analysisSpatialArtifacts.loaded &&
      Array.isArray(analysisSpatialArtifacts.relationshipRows) &&
      analysisSpatialArtifacts.relationshipRows.length > 0 &&
      String(analysisSpatialArtifacts.artifactHashes && analysisSpatialArtifacts.artifactHashes.relationshipReconciliation || "") ===
        String(manifest.artifacts.relationshipReconciliation.sha256 || "")
      ? analysisSpatialArtifacts.relationshipRows
      : null;
    const cachedContextNeighborRows = !analysisSpatialArtifacts.loaded &&
      Array.isArray(analysisSpatialArtifacts.contextNeighbors) &&
      analysisSpatialArtifacts.contextNeighbors.length > 0 &&
      String(analysisSpatialArtifacts.artifactHashes && analysisSpatialArtifacts.artifactHashes.contextUfoNeighbors || "") ===
        String(manifest.artifacts.contextUfoNeighbors.sha256 || "")
      ? analysisSpatialArtifacts.contextNeighbors
      : null;
    const loadRequests = [
      fetchAnalysisJson(neighborUrl, manifestArtifactIntegrity(manifest, "ufoPointNeighbors")),
      fetchAnalysisJson(facilityUrl, manifestArtifactIntegrity(manifest, "facilityAnalysis")),
      cachedRelationshipRows || fetchAnalysisJson(relationshipUrl, manifestArtifactIntegrity(manifest, "relationshipReconciliation")),
      fetchAnalysisJson(spatialPointsUrl, manifestArtifactIntegrity(manifest, "ufoSpatialPoints")),
      cachedContextNeighborRows || fetchAnalysisJson(contextNeighborsUrl, manifestArtifactIntegrity(manifest, "contextUfoNeighbors")),
    ];
    if (configurationAvailable) {
      loadRequests.push(
        fetchAnalysisJson(configurationPointsUrl, manifestArtifactIntegrity(manifest, "ufoConfigurationPoints")),
        fetchAnalysisJson(configurationNeighborsUrl, manifestArtifactIntegrity(manifest, "ufoConfigurationNeighbors"))
      );
    }
    const loaded = await Promise.all(loadRequests);
    if (loadEpoch !== analysisSpatialArtifactLoadEpoch) {
      throw new Error("Analysis spatial artifact setup was superseded by a newer release request.");
    }
    const neighborRows = validateLoadedSpatialArtifact(loaded[0], manifest, "ufoPointNeighbors");
    const facilityRows = validateLoadedSpatialArtifact(loaded[1], manifest, "facilityAnalysis");
    const relationshipRows = cachedRelationshipRows || validateLoadedSpatialArtifact(loaded[2], manifest, "relationshipReconciliation");
    const spatialPointRows = validateLoadedSpatialArtifact(loaded[3], manifest, "ufoSpatialPoints");
    const contextNeighborRows = cachedContextNeighborRows || validateLoadedSpatialArtifact(loaded[4], manifest, "contextUfoNeighbors");
    const configurationPointRows = configurationAvailable
      ? validateLoadedSpatialArtifact(loaded[5], manifest, "ufoConfigurationPoints")
      : [];
    const configurationNeighborRows = configurationAvailable
      ? validateLoadedSpatialArtifact(loaded[6], manifest, "ufoConfigurationNeighbors")
      : [];
    analysisSpatialArtifacts = {
      manifest,
      neighbors: neighborRows,
      spatialPoints: spatialPointRows,
      configurationPoints: configurationPointRows,
      configurationNeighbors: configurationNeighborRows,
      contextNeighbors: contextNeighborRows,
      facilities: decodeFacilityRows(facilityRows, manifest),
      relationshipRows,
      relationships: decodeRelationshipRows(relationshipRows, manifest),
      codebooks: manifest.codes && typeof manifest.codes === "object" ? manifest.codes : {},
      loaded: true,
      artifactHashes: spatialArtifactHashes(manifest),
    };
    analysisCache.clear();
    terminateDedicatedSpatialExecutor("Spatial evidence artifacts were replaced.", true);
    if (dedicatedSpatialWorkerSupported()) await initializeDedicatedSpatialExecutor();
    if (loadEpoch !== analysisSpatialArtifactLoadEpoch) {
      throw new Error("Analysis spatial artifact setup was superseded by a newer release request.");
    }
    return analysisSpatialSnapshot();
  }

  async function loadAnalysisSpatialArtifacts(message) {
    analysisFullSpatialLoadsInFlight += 1;
    try {
      return await loadAnalysisSpatialArtifactsInternal(message);
    } finally {
      analysisFullSpatialLoadsInFlight = Math.max(0, analysisFullSpatialLoadsInFlight - 1);
    }
  }

  async function loadAnalysisRelationshipArtifact(message) {
    const loadEpoch = ++analysisPartialArtifactLoadEpoch.relationship;
    const urls = message.urls && typeof message.urls === "object" ? message.urls : {};
    const manifestUrl = String(urls.manifest || "./data/analysis_v2/manifest.json");
    const manifest = message.manifest && typeof message.manifest === "object"
      ? message.manifest
      : await fetchAnalysisJson(manifestUrl, { sha256: message.manifestSha256 || "" });
    if (!analysisV2ManifestSupported(manifest)) {
      throw new Error("Analysis v2 relationship manifest is invalid or unsupported.");
    }
    validateSpatialManifestArtifact(manifest, "relationshipReconciliation");
    assertPartialSpatialManifestCompatible(manifest);
    if (analysisSpatialArtifacts.loaded && Array.isArray(analysisSpatialArtifacts.relationshipRows)) {
      return {
        loaded: true,
        rowCount: analysisSpatialArtifacts.relationshipRows.length,
        releaseId: String(analysisSpatialArtifacts.manifest && analysisSpatialArtifacts.manifest.releaseId || ""),
        artifactHash: String(analysisSpatialArtifacts.artifactHashes && analysisSpatialArtifacts.artifactHashes.relationshipReconciliation || ""),
        descriptiveOnly: true,
      };
    }
    if (analysisFullSpatialLoadsInFlight > 0) {
      throw new Error("Analysis relationship artifact setup is deferred while the full spatial release is loading.");
    }
    const artifactUrl = urls.relationshipReconciliation || urls.relationships ||
      manifestArtifactUrl(manifest, "relationshipReconciliation", manifestUrl);
    if (!artifactUrl) throw new Error("Analysis v2 manifest is missing the relationship projection URL.");
    const payload = await fetchAnalysisJson(
      artifactUrl,
      manifestArtifactIntegrity(manifest, "relationshipReconciliation")
    );
    const rows = validateLoadedSpatialArtifact(payload, manifest, "relationshipReconciliation");
    if (loadEpoch !== analysisPartialArtifactLoadEpoch.relationship) {
      throw new Error("Analysis relationship artifact setup was superseded by a newer spatial release request.");
    }
    assertPartialSpatialManifestCompatible(manifest);
    if (analysisSpatialArtifacts.loaded && Array.isArray(analysisSpatialArtifacts.relationshipRows)) {
      return {
        loaded: true,
        rowCount: analysisSpatialArtifacts.relationshipRows.length,
        releaseId: String(analysisSpatialArtifacts.manifest && analysisSpatialArtifacts.manifest.releaseId || ""),
        artifactHash: String(analysisSpatialArtifacts.artifactHashes && analysisSpatialArtifacts.artifactHashes.relationshipReconciliation || ""),
        descriptiveOnly: true,
      };
    }
    if (!analysisSpatialArtifacts.loaded) {
      analysisSpatialArtifacts.manifest = manifest;
      analysisSpatialArtifacts.relationshipRows = rows;
      analysisSpatialArtifacts.relationships = decodeRelationshipRows(rows, manifest);
      analysisSpatialArtifacts.codebooks = manifest.codes && typeof manifest.codes === "object" ? manifest.codes : {};
      analysisSpatialArtifacts.artifactHashes = Object.assign(
        {},
        analysisSpatialArtifacts.artifactHashes || {},
        { relationshipReconciliation: String(manifest.artifacts.relationshipReconciliation.sha256 || "") }
      );
      analysisCache.clear();
    }
    return {
      loaded: true,
      rowCount: rows.length,
      releaseId: String(manifest.releaseId || ""),
      artifactHash: String(manifest.artifacts.relationshipReconciliation.sha256 || ""),
      descriptiveOnly: true,
    };
  }

  async function loadAnalysisContextSpatialArtifact(message) {
    const loadEpoch = ++analysisPartialArtifactLoadEpoch.context;
    const urls = message.urls && typeof message.urls === "object" ? message.urls : {};
    const manifestUrl = String(urls.manifest || "./data/analysis_v2/manifest.json");
    const manifest = message.manifest && typeof message.manifest === "object"
      ? message.manifest
      : await fetchAnalysisJson(manifestUrl, { sha256: message.manifestSha256 || "" });
    if (!analysisV2ManifestSupported(manifest)) {
      throw new Error("Analysis v2 context-neighbor manifest is invalid or unsupported.");
    }
    validateSpatialManifestArtifact(manifest, "contextUfoNeighbors");
    assertPartialSpatialManifestCompatible(manifest);
    if (Array.isArray(analysisSpatialArtifacts.contextNeighbors) && analysisSpatialArtifacts.contextNeighbors.length) {
      return {
        loaded: true,
        rowCount: analysisSpatialArtifacts.contextNeighbors.length,
        releaseId: String(analysisSpatialArtifacts.manifest && analysisSpatialArtifacts.manifest.releaseId || ""),
        artifactHash: String(analysisSpatialArtifacts.artifactHashes && analysisSpatialArtifacts.artifactHashes.contextUfoNeighbors || ""),
        fullSpatialLoaded: Boolean(analysisSpatialArtifacts.loaded),
      };
    }
    if (analysisFullSpatialLoadsInFlight > 0) {
      throw new Error("Analysis context-neighbor artifact setup is deferred while the full spatial release is loading.");
    }
    const artifactUrl = urls.contextNeighbors || urls.contextUfoNeighbors ||
      manifestArtifactUrl(manifest, "contextUfoNeighbors", manifestUrl);
    if (!artifactUrl) throw new Error("Analysis v2 manifest is missing the context-neighbor projection URL.");
    const payload = await fetchAnalysisJson(
      artifactUrl,
      manifestArtifactIntegrity(manifest, "contextUfoNeighbors")
    );
    const rows = validateLoadedSpatialArtifact(payload, manifest, "contextUfoNeighbors");
    if (loadEpoch !== analysisPartialArtifactLoadEpoch.context) {
      throw new Error("Analysis context-neighbor artifact setup was superseded by a newer spatial release request.");
    }
    assertPartialSpatialManifestCompatible(manifest);
    if (Array.isArray(analysisSpatialArtifacts.contextNeighbors) && analysisSpatialArtifacts.contextNeighbors.length) {
      return {
        loaded: true,
        rowCount: analysisSpatialArtifacts.contextNeighbors.length,
        releaseId: String(analysisSpatialArtifacts.manifest && analysisSpatialArtifacts.manifest.releaseId || ""),
        artifactHash: String(analysisSpatialArtifacts.artifactHashes && analysisSpatialArtifacts.artifactHashes.contextUfoNeighbors || ""),
        fullSpatialLoaded: Boolean(analysisSpatialArtifacts.loaded),
      };
    }
    if (!analysisSpatialArtifacts.loaded) {
      analysisSpatialArtifacts.manifest = manifest;
      analysisSpatialArtifacts.contextNeighbors = rows;
      analysisSpatialArtifacts.codebooks = manifest.codes && typeof manifest.codes === "object" ? manifest.codes : {};
      analysisSpatialArtifacts.artifactHashes = Object.assign(
        {},
        analysisSpatialArtifacts.artifactHashes || {},
        { contextUfoNeighbors: String(manifest.artifacts.contextUfoNeighbors.sha256 || "") }
      );
      analysisCache.clear();
    }
    return {
      loaded: true,
      rowCount: rows.length,
      releaseId: String(manifest.releaseId || ""),
      artifactHash: String(manifest.artifacts.contextUfoNeighbors.sha256 || ""),
      fullSpatialLoaded: Boolean(analysisSpatialArtifacts.loaded),
    };
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
        analysisCountry: dictionaries.analysisCountry.values.length,
        analysisMacroregion: dictionaries.analysisMacroregion.values.length,
        geographyAssignmentSource: dictionaries.geographyAssignmentSource.values.length,
        geographyAssignmentConfidence: dictionaries.geographyAssignmentConfidence.values.length,
        geographyBoundaryStatus: dictionaries.geographyBoundaryStatus.values.length,
        duplicateLineage: dictionaries.duplicateLineage.values.length,
        durationMacroregion: dictionaries.durationMacroregion.values.length,
        reportingDelayMacroregion: dictionaries.reportingDelayMacroregion.values.length,
        timeOfDayMacroregion: dictionaries.timeOfDayMacroregion.values.length,
        witnessCountMacroregion: dictionaries.witnessCountMacroregion.values.length,
        colorMacroregion: dictionaries.colorMacroregion.values.length,
        coordinateEvidenceMacroregion: dictionaries.coordinateEvidenceMacroregion.values.length,
      },
      geographyProjection: {
        loaded: Boolean(analysisGeographyArtifact.loaded),
        appliedRows: Number(analysisGeographyArtifact.appliedRows) || 0,
        artifactHash: String(analysisGeographyArtifact.artifactHash || ""),
      },
      durationProjection: {
        loaded: Boolean(analysisDurationArtifact.loaded),
        appliedRows: Number(analysisDurationArtifact.appliedRows) || 0,
        normalizedRows: Number(analysisDurationArtifact.normalizedRows) || 0,
        releaseId: String(analysisDurationArtifact.releaseId || ""),
        artifactHashes: Object.assign({}, analysisDurationArtifact.artifactHashes || {}),
      },
      reportingDelayProjection: {
        loaded: Boolean(analysisReportingDelayArtifact.loaded),
        appliedRows: Number(analysisReportingDelayArtifact.appliedRows) || 0,
        typedRows: Number(analysisReportingDelayArtifact.typedRows) || 0,
        releaseId: String(analysisReportingDelayArtifact.releaseId || ""),
        artifactHashes: Object.assign({}, analysisReportingDelayArtifact.artifactHashes || {}),
      },
      timeOfDayProjection: {
        loaded: Boolean(analysisTimeOfDayArtifact.loaded),
        appliedRows: Number(analysisTimeOfDayArtifact.appliedRows) || 0,
        typedRows: Number(analysisTimeOfDayArtifact.typedRows) || 0,
        releaseId: String(analysisTimeOfDayArtifact.releaseId || ""),
        artifactHashes: Object.assign({}, analysisTimeOfDayArtifact.artifactHashes || {}),
      },
      witnessCountProjection: {
        loaded: Boolean(analysisWitnessCountArtifact.loaded),
        appliedRows: Number(analysisWitnessCountArtifact.appliedRows) || 0,
        typedRows: Number(analysisWitnessCountArtifact.typedRows) || 0,
        releaseId: String(analysisWitnessCountArtifact.releaseId || ""),
        artifactHashes: Object.assign({}, analysisWitnessCountArtifact.artifactHashes || {}),
      },
      colorProjection: {
        loaded: Boolean(analysisColorArtifact.loaded),
        appliedRows: Number(analysisColorArtifact.appliedRows) || 0,
        normalizedRows: Number(analysisColorArtifact.normalizedRows) || 0,
        releaseId: String(analysisColorArtifact.releaseId || ""),
        artifactHashes: Object.assign({}, analysisColorArtifact.artifactHashes || {}),
      },
      coordinateEvidenceProjection: {
        loaded: Boolean(analysisCoordinateEvidenceArtifact.loaded),
        appliedRows: Number(analysisCoordinateEvidenceArtifact.appliedRows) || 0,
        typedRows: Number(analysisCoordinateEvidenceArtifact.typedRows) || 0,
        releaseId: String(analysisCoordinateEvidenceArtifact.releaseId || ""),
        artifactHashes: Object.assign({}, analysisCoordinateEvidenceArtifact.artifactHashes || {}),
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
    analysisGeographyArtifact = {
      manifest: null, rows: null, codes: {}, loaded: false, appliedRows: 0, artifactHash: "",
    };
    analysisDurationArtifact = {
      manifest: null, loaded: false, appliedRows: 0, normalizedRows: 0, artifactHashes: {}, releaseId: "",
    };
    analysisReportingDelayArtifact = {
      manifest: null, loaded: false, appliedRows: 0, typedRows: 0, artifactHashes: {}, releaseId: "",
    };
    analysisTimeOfDayArtifact = {
      manifest: null, loaded: false, appliedRows: 0, typedRows: 0, artifactHashes: {}, releaseId: "",
    };
    analysisWitnessCountArtifact = {
      manifest: null, loaded: false, appliedRows: 0, typedRows: 0, artifactHashes: {}, releaseId: "",
    };
    analysisColorArtifact = {
      manifest: null, loaded: false, appliedRows: 0, normalizedRows: 0, artifactHashes: {}, releaseId: "",
    };
    analysisCoordinateEvidenceArtifact = {
      manifest: null, loaded: false, appliedRows: 0, typedRows: 0, artifactHashes: {}, releaseId: "",
    };
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
      if (message.type === "setAnalysisGeographyArtifact") {
        loadAnalysisGeographyArtifact(message).then(function (snapshot) {
          self.postMessage({
            type: "analysisGeographyArtifactSet",
            requestId: message.requestId || "",
            filterGeneration: analysisFilterGeneration(message),
            generation: analysisFilterGeneration(message),
            snapshot,
          });
        }).catch(function (error) {
          self.postMessage({
            type: "catalogFacetWorkerError",
            requestId: message.requestId || "",
            filterGeneration: analysisFilterGeneration(message),
            generation: analysisFilterGeneration(message),
            error: error && error.message ? error.message : String(error),
          });
        });
        return;
      }
      if (message.type === "setAnalysisDurationArtifact") {
        loadAnalysisDurationArtifact(message).then(function (snapshot) {
          self.postMessage({
            type: "analysisDurationArtifactSet",
            requestId: message.requestId || "",
            filterGeneration: analysisFilterGeneration(message),
            generation: analysisFilterGeneration(message),
            snapshot,
          });
        }).catch(function (error) {
          self.postMessage({
            type: "catalogFacetWorkerError",
            requestId: message.requestId || "",
            filterGeneration: analysisFilterGeneration(message),
            generation: analysisFilterGeneration(message),
            error: error && error.message ? error.message : String(error),
          });
        });
        return;
      }
      if (message.type === "setAnalysisReportingDelayArtifact") {
        loadAnalysisReportingDelayArtifact(message).then(function (snapshot) {
          self.postMessage({
            type: "analysisReportingDelayArtifactSet",
            requestId: message.requestId || "",
            filterGeneration: analysisFilterGeneration(message),
            generation: analysisFilterGeneration(message),
            snapshot,
          });
        }).catch(function (error) {
          self.postMessage({
            type: "catalogFacetWorkerError",
            requestId: message.requestId || "",
            filterGeneration: analysisFilterGeneration(message),
            generation: analysisFilterGeneration(message),
            error: error && error.message ? error.message : String(error),
          });
        });
        return;
      }
      if (message.type === "setAnalysisTimeOfDayArtifact") {
        loadAnalysisTimeOfDayArtifact(message).then(function (snapshot) {
          self.postMessage({
            type: "analysisTimeOfDayArtifactSet",
            requestId: message.requestId || "",
            filterGeneration: analysisFilterGeneration(message),
            generation: analysisFilterGeneration(message),
            snapshot,
          });
        }).catch(function (error) {
          self.postMessage({
            type: "catalogFacetWorkerError",
            requestId: message.requestId || "",
            filterGeneration: analysisFilterGeneration(message),
            generation: analysisFilterGeneration(message),
            error: error && error.message ? error.message : String(error),
          });
        });
        return;
      }
      if (message.type === "setAnalysisWitnessCountArtifact") {
        loadAnalysisWitnessCountArtifact(message).then(function (snapshot) {
          self.postMessage({
            type: "analysisWitnessCountArtifactSet",
            requestId: message.requestId || "",
            filterGeneration: analysisFilterGeneration(message),
            generation: analysisFilterGeneration(message),
            snapshot,
          });
        }).catch(function (error) {
          self.postMessage({
            type: "catalogFacetWorkerError",
            requestId: message.requestId || "",
            filterGeneration: analysisFilterGeneration(message),
            generation: analysisFilterGeneration(message),
            error: error && error.message ? error.message : String(error),
          });
        });
        return;
      }
      if (message.type === "setAnalysisColorArtifact") {
        loadAnalysisColorArtifact(message).then(function (snapshot) {
          self.postMessage({
            type: "analysisColorArtifactSet",
            requestId: message.requestId || "",
            filterGeneration: analysisFilterGeneration(message),
            generation: analysisFilterGeneration(message),
            snapshot,
          });
        }).catch(function (error) {
          self.postMessage({
            type: "catalogFacetWorkerError",
            requestId: message.requestId || "",
            filterGeneration: analysisFilterGeneration(message),
            generation: analysisFilterGeneration(message),
            error: error && error.message ? error.message : String(error),
          });
        });
        return;
      }
      if (message.type === "setAnalysisCoordinateEvidenceArtifact") {
        loadAnalysisCoordinateEvidenceArtifact(message).then(function (snapshot) {
          self.postMessage({
            type: "analysisCoordinateEvidenceArtifactSet",
            requestId: message.requestId || "",
            filterGeneration: analysisFilterGeneration(message),
            generation: analysisFilterGeneration(message),
            snapshot,
          });
        }).catch(function (error) {
          self.postMessage({
            type: "catalogFacetWorkerError",
            requestId: message.requestId || "",
            filterGeneration: analysisFilterGeneration(message),
            generation: analysisFilterGeneration(message),
            error: error && error.message ? error.message : String(error),
          });
        });
        return;
      }
      if (message.type === "setAnalysisRelationshipArtifact") {
        loadAnalysisRelationshipArtifact(message).then(function (snapshot) {
          self.postMessage({
            type: "analysisRelationshipArtifactSet",
            requestId: message.requestId || "",
            filterGeneration: analysisFilterGeneration(message),
            generation: analysisFilterGeneration(message),
            snapshot,
          });
        }).catch(function (error) {
          self.postMessage({
            type: "catalogFacetWorkerError",
            requestId: message.requestId || "",
            filterGeneration: analysisFilterGeneration(message),
            generation: analysisFilterGeneration(message),
            error: error && error.message ? error.message : String(error),
          });
        });
        return;
      }
      if (message.type === "setAnalysisContextSpatialArtifact") {
        loadAnalysisContextSpatialArtifact(message).then(function (snapshot) {
          self.postMessage({
            type: "analysisContextSpatialArtifactSet",
            requestId: message.requestId || "",
            filterGeneration: analysisFilterGeneration(message),
            generation: analysisFilterGeneration(message),
            snapshot,
          });
        }).catch(function (error) {
          self.postMessage({
            type: "catalogFacetWorkerError",
            requestId: message.requestId || "",
            filterGeneration: analysisFilterGeneration(message),
            generation: analysisFilterGeneration(message),
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

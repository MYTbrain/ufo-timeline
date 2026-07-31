(function () {
  "use strict";

  const MISSING_SORT_ORDINAL = -2147483648;

  let chunks = [];
  let rowCount = 0;
  let typedStorageBytes = 0;
  let dictionaries = createDictionaries();
  let eventIdStrings = createDictionary();

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
      precision: createDictionary(),
      datePrecision: createDictionary(),
    };
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
      precisionCodes: new Uint16Array(length),
      datePrecisionCodes: new Uint16Array(length),
      sortOrdinals: new Int32Array(length),
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
      chunk.precisionCodes[index] = categoryCode(dictionaries.precision, row.precision);
      chunk.datePrecisionCodes[index] = categoryCode(dictionaries.datePrecision, row.datePrecision);
      const sortOrdinal = Number(row.sortOrdinal);
      chunk.sortOrdinals[index] = Number.isFinite(sortOrdinal)
        ? Math.max(-2147483647, Math.min(2147483647, Math.round(sortOrdinal)))
        : MISSING_SORT_ORDINAL;
    }

    typedStorageBytes +=
      chunk.eventIds.byteLength +
      chunk.eventIdStringCodes.byteLength +
      chunk.sourceCodes.byteLength +
      chunk.typeCodes.byteLength +
      chunk.visualTypeGroupCodes.byteLength +
      chunk.craftTypeCodes.byteLength +
      chunk.precisionCodes.byteLength +
      chunk.datePrecisionCodes.byteLength +
      chunk.sortOrdinals.byteLength;
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
    values.precision = dictionaryValue(dictionaries.precision, chunk.precisionCodes[index]);
    values.datePrecision = dictionaryValue(dictionaries.datePrecision, chunk.datePrecisionCodes[index]);
    values.sortOrdinal = sortOrdinalAt(chunk, index);
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

  function storageSnapshot() {
    return {
      mode: "typed_column_chunks",
      chunks: chunks.length,
      rows: rowCount,
      typedBytes: typedStorageBytes,
      stringEventIds: Math.max(0, eventIdStrings.values.length - 1),
      dictionaries: {
        source: dictionaries.source.values.length,
        type: dictionaries.type.values.length,
        visualTypeGroup: dictionaries.visualTypeGroup.values.length,
        craftType: dictionaries.craftType.values.length,
        precision: dictionaries.precision.values.length,
        datePrecision: dictionaries.datePrecision.values.length,
      },
    };
  }

  function resetRows() {
    chunks = [];
    rowCount = 0;
    typedStorageBytes = 0;
    dictionaries = createDictionaries();
    eventIdStrings = createDictionary();
  }

  self.onmessage = function (event) {
    const message = event.data || {};
    try {
      if (message.type === "resetCatalogFacetRows") {
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
          chunks.push(compactRows(nextRows));
          rowCount += nextRows.length;
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
        error: error && error.message ? error.message : String(error),
      });
    }
  };
})();

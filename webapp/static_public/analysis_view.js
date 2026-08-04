(function (root, factory) {
  "use strict";

  const api = factory();
  if (typeof module === "object" && module && module.exports) {
    module.exports = api;
  }
  if (root) {
    root.UfoAnalysisView = api;
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const SVG_NS = "http://www.w3.org/2000/svg";
  const SERIES_POINT_LIMIT = 48;
  const HEATMAP_CELL_LIMIT = 144;
  const HEATMAP_AXIS_LIMIT = 12;
  const COORDINATE_RANGE_LABEL_CACHE = new Map();
  const ACTIVE_VIEWS = Object.freeze(["map", "analysis"]);
  const ANALYSIS_STATES = Object.freeze(["loading", "ready", "empty", "error"]);
  const BASELINE_MODES = Object.freeze([
    "other_dates_balanced",
    "previous_equal_duration",
    "full_catalog",
  ]);
  const BASELINE_NOTES = Object.freeze({
    other_dates_balanced:
      "Balanced reference reports exclude the selected date window and standardize to the active cohort's common source, era, and geography support.",
    previous_equal_duration:
      "The immediately preceding equal-duration period is balanced to the active cohort's common support before inferential comparison.",
    full_catalog:
      "The full-catalog reference is descriptive: it can overlap the active cohort and can change source composition.",
  });
  const CHART_COLORS = Object.freeze([
    "#168aad",
    "#d18a34",
    "#7b61a8",
    "#2f9e76",
    "#c14e72",
    "#6574cd",
  ]);
  const SOURCE_COMPOSITION_SOURCE_LIMIT = 8;
  const SOURCE_COMPOSITION_PERIOD_LIMIT = 24;
  const MONTH_ORDER = Object.freeze({
    jan: 1, january: 1, "01": 1, "1": 1,
    feb: 2, february: 2, "02": 2, "2": 2,
    mar: 3, march: 3, "03": 3, "3": 3,
    apr: 4, april: 4, "04": 4, "4": 4,
    may: 5, "05": 5, "5": 5,
    jun: 6, june: 6, "06": 6, "6": 6,
    jul: 7, july: 7, "07": 7, "7": 7,
    aug: 8, august: 8, "08": 8, "8": 8,
    sep: 9, sept: 9, september: 9, "09": 9, "9": 9,
    oct: 10, october: 10, "10": 10,
    nov: 11, november: 11, "11": 11,
    dec: 12, december: 12, "12": 12,
  });
  const MONTH_ABBREVIATIONS = Object.freeze([
    "JAN", "FEB", "MAR", "APR", "MAY", "JUN",
    "JUL", "AUG", "SEP", "OCT", "NOV", "DEC",
  ]);
  const CRAFT_DISPLAY_LABELS = Object.freeze({
    formation: "Formation",
  });
  const READINESS_STATUS_LABELS = Object.freeze({
    ready_inferential: "Inferential",
    ready_sensitivity: "Sensitivity",
    ready_descriptive: "Descriptive",
    limited: "Limited",
    blocked: "Blocked",
    not_applicable: "N/A",
    not_evaluated: "Not evaluated",
    data_unavailable: "Unavailable",
  });
  const READINESS_MATRIX_COLUMNS = Object.freeze([
    Object.freeze({ key: "location", label: "Location" }),
    Object.freeze({ key: "date", label: "Date" }),
    Object.freeze({ key: "provenance", label: "Provenance" }),
    Object.freeze({ key: "lineage", label: "Lineage" }),
    Object.freeze({ key: "review", label: "Review" }),
    Object.freeze({ key: "sample", label: "Sample" }),
    Object.freeze({ key: "overall", label: "Output" }),
  ]);
  // Gate placement is deliberately keyed only by stable typed IDs. Labels,
  // reason text, and policy prose must never determine readiness state.
  const READINESS_GATE_COLUMN_MAP = Object.freeze({
    source_coordinates: Object.freeze(["location"]),
    exact_day: Object.freeze(["date"]),
    classification_confidence: Object.freeze(["sample"]),
    same_day_suitability: Object.freeze(["sample"]),
    recognized_shape: Object.freeze(["sample"]),
    coordinate_piles: Object.freeze(["sample"]),
    ufo_neighbor_source_coordinates: Object.freeze(["location"]),
    ufo_neighbor_exact_day: Object.freeze(["date"]),
    ufo_neighbor_craft_confidence: Object.freeze(["sample"]),
    ufo_neighbor_same_day_suitability: Object.freeze(["sample"]),
    ufo_neighbor_recognized_craft: Object.freeze(["sample"]),
    ufo_neighbor_coordinate_piles: Object.freeze(["sample"]),
    configuration_classification: Object.freeze(["sample"]),
    configuration_source_coordinates: Object.freeze(["location"]),
    configuration_exact_day: Object.freeze(["date"]),
    configuration_confidence: Object.freeze(["sample"]),
    configuration_same_day_suitability: Object.freeze(["sample"]),
    configuration_coordinate_piles: Object.freeze(["sample"]),
    configuration_neighbor_support: Object.freeze(["sample"]),
    animal_exact_site_reviewed: Object.freeze(["location", "review"]),
    animal_public_marker_lane: Object.freeze(["location", "date"]),
    crop_exact_site_formation_date: Object.freeze(["location", "date", "review"]),
    crop_bounded_marker_lane: Object.freeze(["location", "date"]),
    crop_locality_marker_lane: Object.freeze(["location", "date"]),
    facility_descriptive_inventory: Object.freeze(["provenance"]),
    facility_inferential_markers: Object.freeze(["location", "date", "sample"]),
    context_observed_neighbors: Object.freeze(["location", "date", "sample"]),
    context_independent_neighbors: Object.freeze(["provenance", "lineage", "sample"]),
    relationship_descriptive_records: Object.freeze(["provenance"]),
    relationship_reconciliation: Object.freeze(["lineage"]),
    relationship_inference: Object.freeze(["review", "sample"]),
  });
  const READINESS_DOMAIN_GATE_PREFERENCES = Object.freeze({
    ufocraftpoints: Object.freeze({
      location: "source_coordinates",
      date: "exact_day",
      sample: "coordinate_piles",
    }),
    cropbounded: Object.freeze({
      location: "crop_bounded_marker_lane",
      date: "crop_bounded_marker_lane",
      review: "crop_exact_site_formation_date",
    }),
    croplocality: Object.freeze({
      location: "crop_locality_marker_lane",
      date: "crop_locality_marker_lane",
      review: "crop_exact_site_formation_date",
    }),
    cropcircles: Object.freeze({
      location: "crop_bounded_marker_lane",
      date: "crop_bounded_marker_lane",
      review: "crop_exact_site_formation_date",
    }),
    animalreports: Object.freeze({
      location: "animal_public_marker_lane",
      date: "animal_public_marker_lane",
      review: "animal_exact_site_reviewed",
    }),
    militaryfacilities: Object.freeze({
      location: "facility_inferential_markers",
      date: "facility_inferential_markers",
      provenance: "facility_descriptive_inventory",
      sample: "facility_inferential_markers",
    }),
    researchfacilities: Object.freeze({
      location: "facility_inferential_markers",
      date: "facility_inferential_markers",
      provenance: "facility_descriptive_inventory",
      sample: "facility_inferential_markers",
    }),
    relationshipreconciliation: Object.freeze({
      provenance: "relationship_descriptive_records",
      lineage: "relationship_reconciliation",
      review: "relationship_inference",
      sample: "relationship_inference",
    }),
  });
  const PATTERN_FAMILY_ORDER = Object.freeze([
    "craft",
    "time_month",
    "geography",
    "source",
    "date_precision",
    "location_precision",
    "coordinate_source",
    "craft_confidence",
  ]);
  const PATTERN_LANES = Object.freeze([
    Object.freeze({
      key: "stableMultiSourceContent",
      label: "Stable multi-source content shifts",
      description: "A substantive content shift qualifies and remains directionally stable across eligible source and region holdouts.",
    }),
    Object.freeze({
      key: "sourceOrRegionSensitive",
      label: "Source- or region-sensitive findings",
      description: "The full cohort qualifies, but the effect is source- or region-dependent, or a holdout is underpowered.",
    }),
    Object.freeze({
      key: "collectionAndQuality",
      label: "Collection and data-quality shifts",
      description: "Changes in source composition, coverage, precision, or classification quality that can alter the apparent signal.",
    }),
  ]);
  const DEFAULT_IDS = Object.freeze({
    tablist: "analysis-view-tablist",
    mapTab: "view-tab-map",
    analysisTab: "view-tab-analysis",
    tabStatus: "analysis-tab-status",
    mapPanel: "map-explorer-panel",
    analysisPanel: "analysis-panel",
    baseline: "analysis-baseline",
    baselineNote: "analysis-baseline-note",
    computationStatus: "analysis-computation-status",
    stateRegion: "analysis-state-region",
    loading: "analysis-loading",
    loadingMessage: "analysis-loading-message",
    empty: "analysis-empty",
    emptyMessage: "analysis-empty-message",
    error: "analysis-error",
    errorMessage: "analysis-error-message",
    errorRetry: "analysis-error-retry",
    content: "analysis-content",
    previewDrawer: "analysis-preview-drawer",
    previewKind: "analysis-preview-kind",
    previewTitle: "analysis-preview-title",
    previewSummary: "analysis-preview-summary",
    previewCohort: "analysis-preview-cohort",
    previewMissingness: "analysis-preview-missingness",
    previewComparison: "analysis-preview-comparison",
    previewCriteria: "analysis-preview-criteria",
    previewFeedback: "analysis-preview-feedback",
    previewApplyFilters: "analysis-preview-apply-filters",
    previewApplyArea: "analysis-preview-apply-area",
    previewCancel: "analysis-preview-cancel",
    previewCancelTop: "analysis-preview-cancel-top",
    sectionNav: "analysis-section-nav",
    geographyStatus: "analysis-geography-status",
    contextStatus: "analysis-context-status",
    spatialSection: "analysis-section-spatial",
    spatialStatus: "analysis-spatial-status",
    cropInclude: "analysis-include-crop-circles",
    animalInclude: "analysis-include-animal-reports",
    cropView: "analysis-view-crop-analysis",
    animalView: "analysis-view-animal-analysis",
    cropControlStatus: "analysis-crop-control-status",
    animalControlStatus: "analysis-animal-control-status",
    exportJson: "analysis-export-json",
    exportCsv: "analysis-export-csv",
  });
  const SUMMARY_IDS = Object.freeze({
    activeCount: "analysis-active-count",
    referenceCount: "analysis-reference-count",
    mappedCount: "analysis-mapped-count",
    unmappedCount: "analysis-unmapped-count",
    missingCount: "analysis-missing-count",
    unitLabel: "analysis-unit-label",
    sourceMixLabel: "analysis-source-mix",
    datePrecisionLabel: "analysis-date-precision",
    locationPrecisionLabel: "analysis-location-precision",
    datasetHash: "analysis-dataset-hash",
    policyWarning: "analysis-policy-warning",
  });

  function isObject(value) {
    return Boolean(value) && typeof value === "object" && !Array.isArray(value);
  }

  function asArray(value) {
    return Array.isArray(value) ? value : [];
  }

  function sampleEvenly(items, limitValue) {
    const values = asArray(items);
    const limit = Math.max(1, Math.trunc(Number(limitValue) || SERIES_POINT_LIMIT));
    if (values.length <= limit) return values.slice();
    if (limit === 1) return [values[0]];
    const lastIndex = values.length - 1;
    const sampled = [];
    for (let index = 0; index < limit; index += 1) {
      sampled.push(values[Math.round((index * lastIndex) / (limit - 1))]);
    }
    return sampled;
  }

  function semanticNumericValue(value, kindValue) {
    const label = cleanText(value);
    const kind = cleanText(kindValue, "auto").toLowerCase();
    const lower = label.toLowerCase();
    if (kind === "month" || kind === "auto") {
      if (Object.prototype.hasOwnProperty.call(MONTH_ORDER, lower)) {
        return { kind: "month", value: MONTH_ORDER[lower] };
      }
    }
    if (kind === "year" || kind === "era" || kind === "period" || kind === "auto") {
      const yearMatch = /^(-?\d{1,6})(?:\s*s)?$/i.exec(label);
      if (yearMatch) return { kind: kind === "auto" ? "year" : kind, value: Number(yearMatch[1]) };
      const rangeMatch = /^(-?\d{1,6})\s*(?:-|\u2013|\u2014|to)\s*(-?\d{1,6})/i.exec(label);
      if (rangeMatch) return { kind: kind === "auto" ? "period" : kind, value: Number(rangeMatch[1]) };
    }
    return null;
  }

  function semanticAxisKind(labelsValue, requestedKindValue) {
    const requested = cleanText(requestedKindValue, "auto").toLowerCase();
    if (requested && requested !== "auto") return requested;
    const labels = asArray(labelsValue).map(cleanText).filter(Boolean);
    if (!labels.length) return "category";
    const monthMatches = labels.filter(function (label) {
      return Object.prototype.hasOwnProperty.call(MONTH_ORDER, label.toLowerCase());
    }).length;
    if (monthMatches === labels.length && labels.length <= 12) return "month";
    const numericMatches = labels.filter(function (label) {
      return Boolean(semanticNumericValue(label, "year"));
    }).length;
    if (numericMatches === labels.length) return "year";
    return "category";
  }

  function sortSemanticAxis(labelsValue, kindValue, explicitOrderValue) {
    const labels = Array.from(new Set(asArray(labelsValue).map(cleanText).filter(Boolean)));
    const explicitOrder = asArray(explicitOrderValue).map(cleanText);
    const explicitIndex = new Map(explicitOrder.map(function (label, index) { return [label, index]; }));
    const kind = semanticAxisKind(labels, kindValue);
    const originalIndex = new Map(labels.map(function (label, index) { return [label, index]; }));
    return labels.slice().sort(function (left, right) {
      if (explicitIndex.has(left) || explicitIndex.has(right)) {
        if (!explicitIndex.has(left)) return 1;
        if (!explicitIndex.has(right)) return -1;
        return explicitIndex.get(left) - explicitIndex.get(right);
      }
      const leftTail = /^(unknown|other|unmapped|not reported|unspecified)$/i.test(left);
      const rightTail = /^(unknown|other|unmapped|not reported|unspecified)$/i.test(right);
      if (leftTail !== rightTail) return leftTail ? 1 : -1;
      const leftNumeric = semanticNumericValue(left, kind);
      const rightNumeric = semanticNumericValue(right, kind);
      if (leftNumeric && rightNumeric && leftNumeric.value !== rightNumeric.value) {
        return leftNumeric.value - rightNumeric.value;
      }
      if (leftNumeric !== rightNumeric) return leftNumeric ? -1 : 1;
      return kind === "category"
        ? originalIndex.get(left) - originalIndex.get(right)
        : left.localeCompare(right, undefined, { numeric: true, sensitivity: "base" });
    });
  }

  function orderedSeriesDisplay(seriesValue, limitValue, options) {
    const config = options || {};
    const source = asArray(seriesValue).map(function (series) {
      return Object.assign({}, series, { points: asArray(series && series.points).slice() });
    });
    const allLabels = [];
    source.forEach(function (series) {
      series.points.forEach(function (point, index) {
        const label = datumLabel(point, index);
        if (allLabels.indexOf(label) === -1) allLabels.push(label);
      });
    });
    const orderedLabels = sortSemanticAxis(allLabels, config.axisKind, config.axisOrder);
    const displayedLabels = sampleEvenly(orderedLabels, limitValue);
    const displayedSet = new Set(displayedLabels);
    const orderIndex = new Map(orderedLabels.map(function (label, index) { return [label, index]; }));
    const fullSeries = source.map(function (series) {
      return Object.assign({}, series, {
        points: series.points.slice().sort(function (left, right) {
          return (orderIndex.get(datumLabel(left, 0)) || 0) - (orderIndex.get(datumLabel(right, 0)) || 0);
        }),
      });
    });
    return {
      labels: displayedLabels,
      allLabels: orderedLabels,
      series: fullSeries.map(function (series) {
        return Object.assign({}, series, {
          points: series.points.filter(function (point) { return displayedSet.has(datumLabel(point, 0)); }),
        });
      }),
      fullSeries,
      sampled: displayedLabels.length < orderedLabels.length,
    };
  }

  function collapseDuplicateReferenceSeries(seriesValue) {
    const series = asArray(seriesValue);
    const active = series.find(function (item) {
      return !item.reference && !/(^|·)\s*reference\b/i.test(cleanText(item.label));
    });
    if (!active) return series.slice();
    const activeByLabel = new Map(asArray(active.points).map(function (point, index) {
      return [datumLabel(point, index), datumValue(point)];
    }));
    return series.filter(function (item) {
      const reference = Boolean(item.reference) || /(^|·)\s*reference\b/i.test(cleanText(item.label));
      if (!reference) return true;
      const points = asArray(item.points);
      return !points.length || points.some(function (point, index) {
        const label = datumLabel(point, index);
        return !activeByLabel.has(label) || Math.abs(activeByLabel.get(label) - datumValue(point)) > 1e-12;
      });
    });
  }

  function sampledHeatmapAxes(rowsValue, columnsValue, limitValue) {
    const rows = asArray(rowsValue);
    const columns = asArray(columnsValue);
    const limit = Math.max(1, Math.trunc(Number(limitValue) || HEATMAP_CELL_LIMIT));
    if (!rows.length || !columns.length || (rows.length * columns.length) <= limit) {
      return { rows: rows.slice(), columns: columns.slice(), sampled: false };
    }

    const preserveShortAxisLimit = 24;
    let rowLimit;
    let columnLimit;
    if (columns.length <= preserveShortAxisLimit) {
      columnLimit = columns.length;
      rowLimit = Math.max(1, Math.floor(limit / columnLimit));
    } else if (rows.length <= preserveShortAxisLimit) {
      rowLimit = rows.length;
      columnLimit = Math.max(1, Math.floor(limit / rowLimit));
    } else {
      const aspect = rows.length / columns.length;
      rowLimit = Math.max(1, Math.floor(Math.sqrt(limit * aspect)));
      columnLimit = Math.max(1, Math.floor(limit / rowLimit));
    }
    rowLimit = Math.min(rows.length, rowLimit, HEATMAP_AXIS_LIMIT);
    columnLimit = Math.min(columns.length, columnLimit, HEATMAP_AXIS_LIMIT);
    while ((rowLimit * columnLimit) > limit) {
      if (rowLimit >= columnLimit && rowLimit > 1) rowLimit -= 1;
      else if (columnLimit > 1) columnLimit -= 1;
      else break;
    }
    return {
      rows: sampleEvenly(rows, rowLimit),
      columns: sampleEvenly(columns, columnLimit),
      sampled: rowLimit < rows.length || columnLimit < columns.length,
    };
  }

  function analysisRequestEnvelopeMatches(pendingValue, messageValue, currentSignatureValue) {
    const pending = pendingValue || {};
    const message = messageValue || {};
    const pendingGeneration = Number(pending.generation);
    const messageGeneration = Number(
      message.filterGeneration != null ? message.filterGeneration : message.generation
    );
    const pendingSignature = cleanText(pending.signature);
    const messageSignature = cleanText(message.analysisSignature);
    return Boolean(
      cleanText(pending.requestId) &&
      cleanText(message.requestId) === cleanText(pending.requestId) &&
      Number.isFinite(pendingGeneration) &&
      messageGeneration === pendingGeneration &&
      cleanText(message.baselineMode) === cleanText(pending.baselineMode) &&
      pendingSignature &&
      messageSignature === pendingSignature &&
      cleanText(currentSignatureValue) === pendingSignature
    );
  }

  function firstDefined(source, keys, fallback) {
    const input = source || {};
    for (let index = 0; index < keys.length; index += 1) {
      const value = input[keys[index]];
      if (value !== undefined && value !== null) return value;
    }
    return fallback;
  }

  function firstArray(source, keys) {
    const input = source || {};
    for (let index = 0; index < keys.length; index += 1) {
      if (Array.isArray(input[keys[index]])) return input[keys[index]];
    }
    return [];
  }

  function finiteNumber(value, fallback) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : (fallback == null ? 0 : fallback);
  }

  function nonnegativeNumber(value, fallback) {
    return Math.max(0, finiteNumber(value, fallback));
  }

  function cleanText(value, fallback) {
    const normalized = String(value == null ? "" : value).trim();
    return normalized || String(fallback == null ? "" : fallback);
  }

  function formatCount(value) {
    if (value == null || value === "") return "—";
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) return "—";
    return Math.round(numeric).toLocaleString("en-US");
  }

  function formatDecimal(value, digits) {
    if (value == null || value === "") return "—";
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) return "—";
    return numeric.toLocaleString("en-US", {
      maximumFractionDigits: digits == null ? 2 : digits,
    });
  }

  function formatPercent(value) {
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) return "—";
    const ratio = Math.abs(numeric) <= 1 ? numeric * 100 : numeric;
    return ratio.toLocaleString("en-US", { maximumFractionDigits: 1 }) + "%";
  }

  function formatSignedPercent(value) {
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) return "—";
    return (numeric > 0 ? "+" : "") + formatPercent(numeric);
  }

  function formatPercentInterval(value) {
    if (Array.isArray(value) && value.length >= 2) {
      return "[" + formatSignedPercent(value[0]) + ", " + formatSignedPercent(value[1]) + "]";
    }
    if (isObject(value)) {
      const lower = firstDefined(value, ["lower", "low", "minimum", "min"], null);
      const upper = firstDefined(value, ["upper", "high", "maximum", "max"], null);
      if (lower != null && upper != null) return "[" + formatSignedPercent(lower) + ", " + formatSignedPercent(upper) + "]";
    }
    return cleanText(value, "—");
  }

  function formatInterval(value) {
    if (Array.isArray(value) && value.length >= 2) {
      return "[" + formatDecimal(value[0], 3) + ", " + formatDecimal(value[1], 3) + "]";
    }
    if (isObject(value)) {
      const lower = firstDefined(value, ["lower", "low", "minimum", "min"], null);
      const upper = firstDefined(value, ["upper", "high", "maximum", "max"], null);
      if (lower != null && upper != null) {
        return "[" + formatDecimal(lower, 3) + ", " + formatDecimal(upper, 3) + "]";
      }
    }
    return cleanText(value, "—");
  }

  function formatSourceStability(value) {
    if (!isObject(value)) return cleanText(value, "Not reported");
    const status = cleanText(firstDefined(value, ["status", "label"], value.stable === true ? "stable" : (value.stable === false ? "source-specific" : "not reported")));
    const tested = firstDefined(value, ["sourcesTested", "sources_tested"], null);
    const dominant = cleanText(firstDefined(value, ["dominantSource", "dominant_source"], ""));
    const details = [status];
    if (tested != null) details.push(formatCount(tested) + " sources tested");
    if (dominant) details.push("dominant: " + dominant);
    return details.join(" · ");
  }

  function normalizeView(value) {
    const normalized = cleanText(value, "map").toLowerCase();
    if (ACTIVE_VIEWS.indexOf(normalized) === -1) {
      throw new TypeError("Unknown analysis view: " + normalized);
    }
    return normalized;
  }

  function normalizeAnalysisState(value) {
    const normalized = cleanText(value, "loading").toLowerCase();
    if (ANALYSIS_STATES.indexOf(normalized) === -1) {
      throw new TypeError("Unknown analysis state: " + normalized);
    }
    return normalized;
  }

  function normalizeBaselineMode(value) {
    const requested = cleanText(value, "other_dates_balanced").toLowerCase();
    const normalized = requested === "other_dates_matched" ? "other_dates_balanced" : requested;
    return BASELINE_MODES.indexOf(normalized) === -1
      ? "other_dates_balanced"
      : normalized;
  }

  function nextEnabledTabIndex(currentIndex, key, disabledIndexes, tabCount) {
    const count = Math.max(1, Math.trunc(Number(tabCount) || 1));
    const disabled = new Set(asArray(disabledIndexes).map(function (value) {
      return Math.trunc(Number(value));
    }));
    const enabled = [];
    for (let index = 0; index < count; index += 1) {
      if (!disabled.has(index)) enabled.push(index);
    }
    if (!enabled.length) return -1;
    if (key === "Home") return enabled[0];
    if (key === "End") return enabled[enabled.length - 1];

    const current = enabled.indexOf(Math.trunc(Number(currentIndex)));
    const origin = current === -1 ? 0 : current;
    if (key === "ArrowLeft" || key === "ArrowUp") {
      return enabled[(origin - 1 + enabled.length) % enabled.length];
    }
    if (key === "ArrowRight" || key === "ArrowDown") {
      return enabled[(origin + 1) % enabled.length];
    }
    return enabled[origin];
  }

  function normalizeSummary(summary) {
    const input = summary || {};
    const policyWarnings = firstDefined(input, ["policyWarnings", "policyWarning", "warnings"], []);
    const hashValue = firstDefined(
      input,
      ["datasetHash", "dataset_hash", "artifactHash", "artifact_hash"],
      "Waiting"
    );
    return {
      activeCount: nonnegativeNumber(firstDefined(input, ["activeCount", "active_count", "observedCount", "count"], 0)),
      referenceCount: nonnegativeNumber(firstDefined(input, ["referenceCount", "reference_count", "baselineCount"], 0)),
      mappedCount: nonnegativeNumber(firstDefined(input, ["mappedCount", "mapped_count"], 0)),
      unmappedCount: nonnegativeNumber(firstDefined(input, ["unmappedCount", "unmapped_count"], 0)),
      missingCount: nonnegativeNumber(firstDefined(input, ["missingCount", "missing_count"], 0)),
      unitLabel: cleanText(firstDefined(input, ["unitLabel", "unit", "unit_of_analysis"], "Reports"), "Reports"),
      sourceMixLabel: cleanText(firstDefined(input, ["sourceMixLabel", "sourceMix", "source_mix"], "Not reported"), "Not reported"),
      datePrecisionLabel: cleanText(firstDefined(input, ["datePrecisionLabel", "datePrecision", "date_precision"], "Not reported"), "Not reported"),
      locationPrecisionLabel: cleanText(firstDefined(input, ["locationPrecisionLabel", "locationPrecision", "location_precision"], "Not reported"), "Not reported"),
      datasetHash: isObject(hashValue)
        ? Object.keys(hashValue).sort().map(function (key) { return key + ": " + hashValue[key]; }).join(" · ")
        : cleanText(hashValue, "Not reported"),
      policyWarning: Array.isArray(policyWarnings)
        ? policyWarnings.map(function (warning) { return cleanText(warning); }).filter(Boolean).join(" ")
        : cleanText(policyWarnings),
    };
  }

  function datumLabel(item, index) {
    return cleanText(firstDefined(
      item,
      ["label", "name", "category", "period", "year", "key", "id"],
      "Item " + (index + 1)
    ));
  }

  function datumValue(item, preferredKeys) {
    const keys = asArray(preferredKeys).concat([
      "value", "count", "observed", "activeCount", "share", "rate", "residual",
    ]);
    return finiteNumber(firstDefined(item, keys, 0));
  }

  function datumReference(item, preferredKeys) {
    const explicitKeys = asArray(preferredKeys);
    const value = firstDefined(
      item,
      explicitKeys.length ? explicitKeys : ["reference", "referenceCount", "baseline", "expected", "referenceShare"],
      null
    );
    return value == null ? null : finiteNumber(value, 0);
  }

  function matrixItems(value) {
    if (Array.isArray(value)) return value;
    if (!isObject(value)) return [];
    if (Array.isArray(value.fullCells)) return value.fullCells;
    if (Array.isArray(value.full_cells)) return value.full_cells;
    if (Array.isArray(value.cells)) return value.cells;
    if (!Array.isArray(value.rows)) return [];
    const columns = asArray(value.columns);
    const output = [];
    value.rows.forEach(function (row, rowIndex) {
      const values = Array.isArray(row) ? row : asArray(row && row.values);
      const rowLabel = Array.isArray(row)
        ? cleanText(rowIndex + 1)
        : cleanText(firstDefined(row, ["label", "name", "row"], rowIndex + 1));
      values.forEach(function (cell, columnIndex) {
        const source = isObject(cell) ? cell : { value: cell };
        output.push(Object.assign({}, source, {
          row: firstDefined(source, ["row", "rowLabel"], rowLabel),
          column: firstDefined(source, ["column", "columnLabel"], columns[columnIndex] || (columnIndex + 1)),
        }));
      });
    });
    return output;
  }

  function intervalBounds(item, optionsValue) {
    const options = optionsValue || {};
    const effectIntervalKeys = ["interval", "effectInterval", "effect_interval", "confidenceInterval", "confidence_interval", "differenceInterval", "difference_interval"];
    const interval = firstDefined(
      item,
      options.ratioScale === true
        ? ["oddsRatioInterval", "odds_ratio_interval"].concat(effectIntervalKeys)
        : effectIntervalKeys,
      null
    );
    const validated = function (lowerValue, upperValue) {
      const lower = Number(lowerValue);
      const upper = Number(upperValue);
      return Number.isFinite(lower) && Number.isFinite(upper) && lower <= upper
        ? { lower, upper }
        : null;
    };
    if (Array.isArray(interval) && interval.length >= 2 && interval[0] != null && interval[1] != null) {
      return validated(interval[0], interval[1]);
    }
    if (isObject(interval)) {
      const lower = firstDefined(interval, ["lower", "low", "minimum", "min"], null);
      const upper = firstDefined(interval, ["upper", "high", "maximum", "max"], null);
      if (lower != null && upper != null) return validated(lower, upper);
    }
    const lower = firstDefined(item, ["lower", "ciLower", "ci_lower"], null);
    const upper = firstDefined(item, ["upper", "ciUpper", "ci_upper"], null);
    return lower != null && upper != null
      ? validated(lower, upper)
      : null;
  }

  function comparativeEffect(item, preferredKeys) {
    const explicit = firstDefined(item, asArray(preferredKeys).concat([
      "adjustedDifference", "adjusted_difference", "difference", "shareDifference", "share_difference",
      "log2Enrichment", "log2_enrichment", "commonOddsRatio", "common_odds_ratio", "oddsRatio", "odds_ratio",
      "standardizedResidual", "standardized_residual", "adjustedResidual", "adjusted_residual",
      "conditionalResidual", "conditional_residual", "sourceBalancedShare", "source_balanced_share",
      "residual", "effect", "value",
    ]), null);
    if (explicit != null && Number.isFinite(Number(explicit))) return Number(explicit);
    const activeShare = firstDefined(item, ["adjustedActiveShare", "adjusted_active_share", "activeShare", "active_share", "share"], null);
    const referenceShare = firstDefined(item, ["adjustedReferenceShare", "adjusted_reference_share", "referenceShare", "reference_share"], null);
    return activeShare != null && referenceShare != null
      ? finiteNumber(activeShare) - finiteNumber(referenceShare)
      : datumValue(item, preferredKeys);
  }

  function conservativeEffectMagnitude(item, preferredKeys, nullValue) {
    const nullPoint = Number.isFinite(Number(nullValue)) ? Number(nullValue) : 0;
    const effect = comparativeEffect(item, preferredKeys);
    const interval = intervalBounds(item, { ratioScale: nullPoint === 1 });
    let boundary = effect;
    if (interval) {
      const lower = Math.min(interval.lower, interval.upper);
      const upper = Math.max(interval.lower, interval.upper);
      if (lower <= nullPoint && upper >= nullPoint) return 0;
      boundary = effect >= nullPoint ? lower : upper;
    }
    if (nullPoint === 1 && boundary > 0) return Math.abs(Math.log(boundary));
    return Math.abs(boundary - nullPoint);
  }

  function humanizeEvidenceReason(value) {
    const reason = cleanText(value);
    return reason.indexOf("_") === -1 ? reason : reason.replace(/_/g, " ");
  }

  function monthDisplayLabel(value) {
    const raw = cleanText(value);
    const month = MONTH_ORDER[raw.toLowerCase()];
    if (!month) return raw;
    return String(month).padStart(2, "0") + "/" + MONTH_ABBREVIATIONS[month - 1];
  }

  function craftDisplayLabel(value) {
    const raw = cleanText(value);
    const key = raw.toLowerCase().replace(/[\s/-]+/g, "_");
    if (Object.prototype.hasOwnProperty.call(CRAFT_DISPLAY_LABELS, key)) return CRAFT_DISPLAY_LABELS[key];
    return raw.replace(/_/g, " ").replace(/\b\w/g, function (letter) { return letter.toUpperCase(); });
  }

  function isDumbbellBarbellCraft(value) {
    return cleanText(value).toLowerCase().replace(/[\s/-]+/g, "_") === "dumbbell_barbell";
  }

  function isFormationConfiguration(value) {
    return cleanText(value).toLowerCase().replace(/[\s/-]+/g, "_") === "formation";
  }

  function equalAreaBandBounds(rowValue, columnValue, rowsValue, columnsValue) {
    const rows = Math.max(1, Math.trunc(Number(rowsValue) || 6));
    const columns = Math.max(1, Math.trunc(Number(columnsValue) || 12));
    const row = Math.max(0, Math.min(rows - 1, Math.trunc(Number(rowValue) || 0)));
    const column = Math.max(0, Math.min(columns - 1, Math.trunc(Number(columnValue) || 0)));
    const latitudeFor = function (index) {
      return Math.asin(Math.max(-1, Math.min(1, -1 + ((2 * index) / rows)))) * (180 / Math.PI);
    };
    return {
      south: latitudeFor(row),
      north: latitudeFor(row + 1),
      west: -180 + ((360 * column) / columns),
      east: -180 + ((360 * (column + 1)) / columns),
    };
  }

  function equalAreaGridIdentity(value) {
    const raw = cleanText(value);
    const match = /^(?:lcea)?ea(\d+)x(\d+):(\d+):(\d+)$/i.exec(raw);
    if (!match) return null;
    return {
      rows: Number(match[1]),
      columns: Number(match[2]),
      row: Number(match[3]),
      column: Number(match[4]),
    };
  }

  function humanGeographyLabel(value) {
    const raw = cleanText(value, "Unknown region");
    const identity = equalAreaGridIdentity(raw);
    if (!identity) return raw.replace(/_/g, " ");
    const bounds = equalAreaBandBounds(identity.row, identity.column, identity.rows, identity.columns);
    return "Latitude " + coordinateRangeLabel(bounds.south, bounds.north)
      + " / longitude " + coordinateRangeLabel(bounds.west, bounds.east);
  }

  function canonicalCountryName(value) {
    return cleanText(value).normalize("NFKD").replace(/[\u0300-\u036f]/g, "")
      .toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
  }

  function countryEvidenceItems(value) {
    const source = Array.isArray(value) ? value : firstArray(value, ["countries", "cells", "items", "effects", "rows"]);
    return source.filter(isObject).map(function (item, index) {
      const country = cleanText(firstDefined(item, ["countryName", "country_name", "country", "name", "label"], "Country " + (index + 1)));
      return Object.assign({}, item, { country, countryKey: canonicalCountryName(country) });
    }).filter(function (item) { return item.countryKey; });
  }

  function projectedGeometryPath(geometry, widthValue, heightValue) {
    const width = Number(widthValue) || 960;
    const height = Number(heightValue) || 480;
    if (!geometry || !Array.isArray(geometry.coordinates)) return "";
    const project = function (coordinate) {
      const longitude = Math.max(-180, Math.min(180, Number(coordinate[0]) || 0));
      const latitude = Math.max(-90, Math.min(90, Number(coordinate[1]) || 0));
      return [((longitude + 180) / 360) * width, ((90 - latitude) / 180) * height];
    };
    const ringPath = function (ring) {
      if (!Array.isArray(ring) || ring.length < 3) return "";
      return ring.map(function (coordinate, index) {
        const point = project(coordinate);
        return (index ? "L" : "M") + point[0].toFixed(2) + " " + point[1].toFixed(2);
      }).join(" ") + " Z";
    };
    const polygonPath = function (polygon) {
      return asArray(polygon).map(ringPath).filter(Boolean).join(" ");
    };
    if (geometry.type === "Polygon") return polygonPath(geometry.coordinates);
    if (geometry.type === "MultiPolygon") return geometry.coordinates.map(polygonPath).filter(Boolean).join(" ");
    return "";
  }

  function projectedEqualAreaGeometryPath(geometry, widthValue, heightValue) {
    const width = Number(widthValue) || 600;
    const height = Number(heightValue) || 300;
    if (!geometry || !Array.isArray(geometry.coordinates)) return "";
    const project = function (coordinate) {
      const longitude = Math.max(-180, Math.min(180, Number(coordinate[0]) || 0));
      const latitude = Math.max(-90, Math.min(90, Number(coordinate[1]) || 0));
      const equalAreaY = (Math.sin(latitude * Math.PI / 180) + 1) / 2;
      return [((longitude + 180) / 360) * width, (1 - equalAreaY) * height];
    };
    const ringPath = function (ring) {
      if (!Array.isArray(ring) || ring.length < 3) return "";
      return ring.map(function (coordinate, index) {
        const point = project(coordinate);
        return (index ? "L" : "M") + point[0].toFixed(2) + " " + point[1].toFixed(2);
      }).join(" ") + " Z";
    };
    const polygonPath = function (polygon) {
      return asArray(polygon).map(ringPath).filter(Boolean).join(" ");
    };
    if (geometry.type === "Polygon") return polygonPath(geometry.coordinates);
    if (geometry.type === "MultiPolygon") return geometry.coordinates.map(polygonPath).filter(Boolean).join(" ");
    return "";
  }

  function suppressionReason(item) {
    const explicitValue = firstDefined(item, ["suppressionReasons", "suppression_reasons", "supportReasons", "support_reasons", "suppressionReason", "suppression_reason", "reason"], "");
    const explicit = Array.isArray(explicitValue)
      ? explicitValue.map(humanizeEvidenceReason).filter(Boolean).join("; ")
      : humanizeEvidenceReason(explicitValue);
    const status = cleanText(firstDefined(item, ["displayStatus", "display_status", "suppressionStatus", "suppression_status", "status", "eligibility", "evidenceStatus", "evidence_status"], "")).toLowerCase();
    const suppressed = item && (
      item.suppressed === true ||
      item.inferenceEligible === false ||
      item.inference_eligible === false ||
      item.qualified === false ||
      item.displayEligible === false ||
      status === "suppressed" ||
      status === "not_estimable" ||
      status === "not estimable"
    );
    return suppressed ? (explicit || status.replace(/_/g, " ") || "Insufficient support") : "";
  }

  function estimateAvailable(item, preferredKeys) {
    if (!isObject(item)) return false;
    const explicit = firstDefined(item, ["estimateAvailable", "estimate_available", "displayEstimate", "display_estimate"], null);
    if (explicit != null) return Boolean(explicit);
    const status = cleanText(firstDefined(item, ["displayStatus", "display_status"], "")).toLowerCase();
    if (status === "structurally_empty" || status === "prohibited") return false;
    const observed = firstDefined(item, ["activeCount", "active_count", "observedCount", "observed_count", "observed", "count"], null);
    const expected = firstDefined(item, ["referenceCount", "reference_count", "expectedCount", "expected_count", "reference", "expected"], null);
    const explicitEffect = firstDefined(item, asArray(preferredKeys).concat([
      "adjustedDifference", "adjusted_difference", "difference", "shareDifference", "share_difference",
      "log2Enrichment", "log2_enrichment", "commonOddsRatio", "common_odds_ratio", "oddsRatio", "odds_ratio",
      "standardizedResidual", "standardized_residual", "adjustedResidual", "adjusted_residual",
      "conditionalResidual", "conditional_residual", "sourceBalancedShare", "source_balanced_share", "residual", "effect", "value",
    ]), null);
    return (explicitEffect != null && Number.isFinite(Number(explicitEffect)))
      || (observed != null && Number.isFinite(Number(observed)))
      || (expected != null && Number.isFinite(Number(expected)));
  }

  function inferenceEligible(item) {
    if (!isObject(item)) return false;
    const explicit = firstDefined(item, ["inferenceEligible", "inference_eligible", "qualified"], null);
    if (explicit != null) return Boolean(explicit);
    return !suppressionReason(item);
  }

  function evidenceStatusLabel(item) {
    const reason = suppressionReason(item);
    if (reason) return "Not estimable · " + reason;
    const status = cleanText(firstDefined(item, ["status", "evidenceStatus", "evidence_status"], "")).toLowerCase();
    if (status === "descriptive_only" || status === "descriptive only") return "Descriptive only";
    if (status === "sensitivity") return "Sensitivity view";
    if (status === "exploratory") return "Exploratory";
    return "Qualified";
  }

  function heatmapDisplayItems(value, preferredKeys) {
    const data = matrixItems(value).filter(function (item) {
      const displayStatus = cleanText(firstDefined(item, ["displayStatus", "display_status"], "")).toLowerCase();
      if (displayStatus === "structurally_empty") return false;
      const effect = comparativeEffect(item, preferredKeys);
      const active = finiteNumber(firstDefined(item, ["activeCount", "active_count", "observed", "count"], 0));
      const reference = finiteNumber(firstDefined(item, ["referenceCount", "reference_count", "reference", "expected"], 0));
      return estimateAvailable(item, preferredKeys) && (Boolean(suppressionReason(item)) || effect !== 0 || active !== 0 || reference !== 0);
    });
    const scoreByRow = new Map();
    const scoreByColumn = new Map();
    data.forEach(function (item) {
      const row = cleanText(firstDefined(item, ["row", "rowLabel", "group", "category"], "All"), "All");
      const column = cleanText(firstDefined(item, ["column", "columnLabel", "period", "month", "year", "label"], "Value"), "Value");
      const interval = intervalBounds(item);
      const effect = comparativeEffect(item, preferredKeys);
      const conservative = interval
        ? (effect < 0 ? Math.abs(Math.min(0, interval.upper)) : Math.max(0, interval.lower))
        : Math.abs(effect);
      scoreByRow.set(row, Math.max(scoreByRow.get(row) || 0, conservative));
      scoreByColumn.set(column, Math.max(scoreByColumn.get(column) || 0, conservative));
    });
    return {
      data,
      rows: Array.from(scoreByRow.keys()).sort(function (left, right) {
        return (scoreByRow.get(right) || 0) - (scoreByRow.get(left) || 0) || left.localeCompare(right);
      }),
      columns: Array.from(scoreByColumn.keys()).sort(function (left, right) {
        return (scoreByColumn.get(right) || 0) - (scoreByColumn.get(left) || 0) || left.localeCompare(right);
      }),
    };
  }

  function evidencePackageRows(result) {
    const payload = isObject(result) ? result : {};
    const rows = [];
    const exportContext = function (section, item, inherited) {
      const context = Object.assign({}, inherited || {});
      const explicitLane = cleanText(firstDefined(item, ["lane", "laneId", "lane_id", "evidenceLane", "evidence_lane"], ""));
      const sourceLane = cleanText(firstDefined(item, ["sourceLane", "source_lane"], ""));
      if (/\.configuration(?:\.|\[|$)/.test(section)) context.lane = "formation_configuration";
      else if (explicitLane) context.lane = explicitLane;
      else if (sourceLane) context.lane = sourceLane === "cross" ? "cross_source" : (sourceLane === "same" ? "same_source" : sourceLane);
      if (!context.lane && /\.crossSource(?:\.|\[|$)/.test(section)) context.lane = "cross_source";
      if (!context.lane && /\.sameSource(?:\.|\[|$)/.test(section)) context.lane = "same_source";
      context.policyId = firstDefined(item, ["policyId", "policy_id"], context.policyId || "");
      context.evidenceHash = firstDefined(item, ["evidenceHash", "evidence_hash"], context.evidenceHash || "");
      context.durationReleaseId = firstDefined(item, ["releaseId", "release_id"], context.durationReleaseId || "");
      context.durationAssessmentLane = firstDefined(item, ["assessmentLane", "assessment_lane"], context.durationAssessmentLane || "");
      return context;
    };
    const appendRow = function (section, item, index, inherited) {
      const interval = intervalBounds(item);
      const context = exportContext(section, item, inherited);
      const rawRow = firstDefined(item, ["rawRowLabel", "raw_row_label", "row", "rowLabel", "row_label", "focalCraft", "focal_craft"], "");
      const rawColumn = firstDefined(item, ["rawColumnLabel", "raw_column_label", "column", "columnLabel", "column_label", "neighborCraft", "neighbor_craft"], "");
      const rawLabel = firstDefined(item, ["rawLabel", "raw_label", "canonicalLabel", "canonical_label", "key", "id"],
        rawRow && rawColumn ? rawRow + " / " + rawColumn : datumLabel(item, index));
      const displayRow = firstDefined(item, ["displayRow", "display_row", "displayRowLabel", "display_row_label"], rawRow ? craftDisplayLabel(rawRow) : "");
      const displayColumn = firstDefined(item, ["displayColumn", "display_column", "displayColumnLabel", "display_column_label"], rawColumn ? craftDisplayLabel(rawColumn) : "");
      const displayLabel = firstDefined(item, ["displayLabel", "display_label", "countryName", "country_name", "country"],
        displayRow && displayColumn ? displayRow + " / " + displayColumn : datumLabel(item, index));
      rows.push({
        section,
        label: datumLabel(item, index),
        raw_label: rawLabel,
        display_label: displayLabel,
        row_label: rawRow,
        raw_row_label: rawRow,
        display_row_label: displayRow,
        column_label: rawColumn,
        raw_column_label: rawColumn,
        display_column_label: displayColumn,
        lane: context.lane || "",
        unit: firstDefined(item, ["unitOfAnalysis", "unit_of_analysis", "unit"], "reports"),
        active_n: firstDefined(item, ["activeCount", "active_count", "observedCount", "observed_count", "nearCount", "near_count", "observed", "count"], ""),
        reference_n: firstDefined(item, ["referenceCount", "reference_count", "comparisonCount", "comparison_count", "reference"], ""),
        expected_count: firstDefined(item, ["expectedCount", "expected_count", "expectedClusterCount", "expected_cluster_count", "expected"], ""),
        supported_active_n: firstDefined(item, ["supportedActiveN", "supported_active_n", "supportedCount", "supported_count", "supportedN", "supported_n"], ""),
        supported_reference_n: firstDefined(item, ["supportedReferenceN", "supported_reference_n"], ""),
        common_support_rate: firstDefined(item, ["commonSupportRate", "common_support_rate"], ""),
        active_share: firstDefined(item, ["activeShare", "active_share", "observedShare", "observed_share"], ""),
        reference_share: firstDefined(item, ["referenceShare", "reference_share"], ""),
        adjusted_effect: comparativeEffect(item),
        interval_lower: interval ? interval.lower : "",
        interval_upper: interval ? interval.upper : "",
        p_value: firstDefined(item, ["pValue", "p_value", "p"], ""),
        q_value: firstDefined(item, ["qValue", "q_value", "q"], ""),
        estimate_available: estimateAvailable(item),
        inference_eligible: inferenceEligible(item),
        low_support: estimateAvailable(item) && !inferenceEligible(item),
        covariates: firstDefined(item, ["covariates", "adjustmentCovariates", "adjustment_covariates"], []),
        source_stability: firstDefined(item, ["sourceStability", "source_stability"], ""),
        region_stability: firstDefined(item, ["regionStability", "region_stability"], ""),
        estimator_version: firstDefined(item, ["estimatorVersion", "estimator_version"], ""),
        artifact_hashes: firstDefined(item, ["artifactHashes", "artifact_hashes", "datasetHash", "dataset_hash"], ""),
        release_hashes: firstDefined(item, ["releaseHashes", "release_hashes", "releaseHash", "release_hash"], ""),
        exclusions: firstDefined(item, ["exclusions", "exclusionCounts", "exclusion_counts", "excludedN", "excluded_n", "excludedObservedPairN", "excluded_observed_pair_n"], ""),
        sensitivity: firstDefined(item, ["sensitivity", "sensitivityView", "sensitivity_view", "sourceSensitivity", "source_sensitivity", "regionSensitivity", "region_sensitivity"], ""),
        permutation_count: firstDefined(item, ["permutationCount", "permutation_count"], ""),
        bootstrap_count: firstDefined(item, ["bootstrapCount", "bootstrap_count"], ""),
        suppression_reason: suppressionReason(item),
        gate_id: firstDefined(item, ["gateId", "gate_id"], ""),
        gate_label: firstDefined(item, ["gateLabel", "gate_label", "label", "name"], ""),
        readiness_status: firstDefined(item, ["readinessStatus", "readiness_status", "status", "evidenceStatus", "evidence_status"], ""),
        applicability: firstDefined(item, ["applicability"], ""),
        input_n: firstDefined(item, ["inputN", "input_n"], ""),
        passed_n: firstDefined(item, ["passedN", "passed_n"], ""),
        failed_n: firstDefined(item, ["failedN", "failed_n"], ""),
        unknown_n: firstDefined(item, ["unknownN", "unknown_n"], ""),
        policy_id: context.policyId,
        evidence_hash: context.evidenceHash,
        reason_codes: firstDefined(item, ["reasonCodes", "reason_codes"], []),
        duration_bin: /(?:^|\.)duration(?:\.|\[|$)/.test(section) ? firstDefined(item, ["key", "durationBin", "duration_bin"], "") : "",
        duration_measurement_class: firstDefined(item, ["measurementClass", "measurement_class"], ""),
        duration_release_id: context.durationReleaseId || "",
        duration_assessment_lane: context.durationAssessmentLane || "",
        geography_country: firstDefined(item, ["country", "countryName", "country_name"], ""),
        geography_macroregion: firstDefined(item, ["macroregion", "analysisMacroregion", "analysis_macroregion"], ""),
        geography_assignment_source: firstDefined(item, ["geographyAssignmentSource", "geography_assignment_source", "assignmentSource", "assignment_source"], ""),
        geography_assignment_confidence: firstDefined(item, ["geographyAssignmentConfidence", "geography_assignment_confidence", "assignmentConfidence", "assignment_confidence"], ""),
        geography_boundary_status: firstDefined(item, ["geographyBoundaryStatus", "geography_boundary_status", "boundaryStatus", "boundary_status"], ""),
        geography_unknown_status: firstDefined(item, ["geographyUnknownStatus", "geography_unknown_status", "unknownStatus", "unknown_status"], ""),
        geography_source_mix: firstDefined(item, ["sourceMix", "source_mix"], []),
        geography_assignment_provenance: firstDefined(item, ["geographyAssignmentProvenance", "geography_assignment_provenance", "assignmentProvenance", "assignment_provenance"], {}),
      });
    };
    const visit = function (section, value, inherited) {
      if (Array.isArray(value)) {
        value.forEach(function (item, index) {
          if (!isObject(item)) return;
          const context = exportContext(section, item, inherited);
          appendRow(section, item, index, context);
          Object.keys(item).sort().forEach(function (key) {
            if (key === "summary" || key === "meta") return;
            if (["sourceMix", "source_mix", "referenceSourceMix", "reference_source_mix", "geographyAssignmentProvenance", "geography_assignment_provenance"].indexOf(key) !== -1) return;
            const child = item[key];
            if (Array.isArray(child) || isObject(child)) {
              visit(section + "[" + index + "]." + key, child, context);
            }
          });
        });
        return;
      }
      if (!isObject(value)) return;
      const context = exportContext(section, value, inherited);
      Object.keys(value).sort().forEach(function (key) {
        if (key === "summary" || key === "meta") return;
        visit(section ? section + "." + key : key, value[key], context);
      });
    };
    visit("", payload, {});
    return rows;
  }

  function buildEvidencePackage(result, meta) {
    const payload = isObject(result) ? result : {};
    const metadata = Object.assign({}, isObject(payload.meta) ? payload.meta : {}, isObject(meta) ? meta : {});
    return {
      schemaVersion: "ufo-timeline-analysis-evidence-v2.3",
      generatedAt: new Date().toISOString(),
      estimatorVersion: cleanText(firstDefined(metadata, ["estimatorVersion", "estimator_version"], firstDefined(payload, ["estimatorVersion", "estimator_version"], "not reported"))),
      baselineMode: cleanText(firstDefined(metadata, ["baselineMode", "baseline_mode"], firstDefined(payload.summary || {}, ["baselineMode", "baseline_mode"], "not reported"))),
      analysisMode: cleanText(firstDefined(metadata, ["analysisMode", "analysis_mode"], firstDefined(payload, ["analysisMode", "analysis_mode"], firstDefined(payload.summary || {}, ["analysisMode", "analysis_mode"], "comparative")))),
      comparisonState: cleanText(firstDefined(metadata, ["comparisonState", "comparison_state"], firstDefined(payload, ["comparisonState", "comparison_state"], firstDefined(payload.summary || {}, ["comparisonState", "comparison_state"], "not reported")))),
      filterSnapshot: firstDefined(metadata, ["filterSnapshot", "filter_snapshot"], null),
      artifactHashes: firstDefined(metadata, ["artifactHashes", "artifact_hashes", "datasetHash", "dataset_hash"], firstDefined(payload.summary || {}, ["artifactHashes", "artifact_hashes", "datasetHash", "dataset_hash"], {})),
      summary: isObject(payload.summary) ? payload.summary : {},
      evidenceRows: evidencePackageRows(payload),
      result: payload,
    };
  }

  function csvCell(value) {
    const text = value == null ? "" : (isObject(value) || Array.isArray(value) ? JSON.stringify(value) : String(value));
    return /[",\r\n]/.test(text) ? '"' + text.replace(/"/g, '""') + '"' : text;
  }

  function evidencePackageToCsv(packageValue) {
    const rows = asArray(packageValue && packageValue.evidenceRows);
    const metadata = packageValue || {};
    const columns = [
      "schema_version", "generated_at", "analysis_mode", "comparison_state", "baseline_mode", "package_estimator_version", "filter_snapshot", "package_artifact_hashes",
      "section", "label", "raw_label", "display_label", "row_label", "raw_row_label", "display_row_label", "column_label", "raw_column_label", "display_column_label", "lane", "unit", "active_n", "reference_n", "expected_count", "supported_active_n", "supported_reference_n",
      "common_support_rate", "active_share", "reference_share", "adjusted_effect", "interval_lower", "interval_upper", "p_value", "q_value", "estimate_available", "inference_eligible", "low_support", "covariates",
      "source_stability", "region_stability", "estimator_version", "artifact_hashes", "release_hashes", "exclusions", "sensitivity", "permutation_count", "bootstrap_count", "suppression_reason",
      "gate_id", "gate_label", "readiness_status", "applicability", "input_n", "passed_n", "failed_n", "unknown_n", "policy_id", "evidence_hash", "reason_codes", "duration_bin", "duration_measurement_class", "duration_release_id", "duration_assessment_lane",
      "geography_country", "geography_macroregion", "geography_assignment_source", "geography_assignment_confidence", "geography_boundary_status", "geography_unknown_status", "geography_source_mix", "geography_assignment_provenance",
    ];
    const exportRows = rows.length ? rows : [{ section: "metadata", label: "No evidence rows" }];
    return [columns.join(",")].concat(exportRows.map(function (row) {
      const value = Object.assign({
        schema_version: metadata.schemaVersion,
        generated_at: metadata.generatedAt,
        analysis_mode: metadata.analysisMode,
        comparison_state: metadata.comparisonState,
        baseline_mode: metadata.baselineMode,
        package_estimator_version: metadata.estimatorVersion,
        filter_snapshot: metadata.filterSnapshot,
        package_artifact_hashes: metadata.artifactHashes,
      }, row);
      return columns.map(function (column) { return csvCell(value[column]); }).join(",");
    })).join("\r\n");
  }

  function coordinateRangeLabel(minimumValue, maximumValue) {
    const minimum = Number(minimumValue);
    const maximum = Number(maximumValue);
    if (!Number.isFinite(minimum) || !Number.isFinite(maximum)) return "Unknown band";
    const cacheKey = minimum + "\u0000" + maximum;
    if (COORDINATE_RANGE_LABEL_CACHE.has(cacheKey)) return COORDINATE_RANGE_LABEL_CACHE.get(cacheKey);
    const format = function (value) {
      return (Math.round(value * 10) / 10).toLocaleString("en-US", { maximumFractionDigits: 1 }) + "°";
    };
    const label = format(minimum) + " to " + format(maximum);
    COORDINATE_RANGE_LABEL_CACHE.set(cacheKey, label);
    return label;
  }

  function normalizeGeographyCells(items) {
    return matrixItems(items).filter(function (item) {
      return cleanText(firstDefined(item, ["displayStatus", "display_status"], "")).toLowerCase() !== "structurally_empty";
    }).map(function (item) {
      const coordinateClass = cleanText(firstDefined(item, ["coordinateClass", "coordinate_class"], "")).toLowerCase();
      const classLabel = coordinateClass.indexOf("general") !== -1
        ? "Generalized"
        : ((coordinateClass.indexOf("source") !== -1 || coordinateClass.indexOf("exact") !== -1)
          ? "Source-provided exact"
          : "Unspecified coordinate class");
      if (Number.isFinite(Number(item.latIndex)) && Number.isFinite(Number(item.lonIndex))) {
        return Object.assign({}, item, {
          row: classLabel + " · " + coordinateRangeLabel(item.latMinimum, item.latMaximum),
          column: coordinateRangeLabel(item.lonMinimum, item.lonMaximum),
        });
      }
      const identity = equalAreaGridIdentity(firstDefined(item, ["row", "rowLabel", "key", "region", "geography"], ""));
      if (identity) {
        const bounds = equalAreaBandBounds(identity.row, identity.column, identity.rows, identity.columns);
        return Object.assign({}, item, {
          row: classLabel + " · " + coordinateRangeLabel(bounds.south, bounds.north),
          column: coordinateRangeLabel(bounds.west, bounds.east),
        });
      }
      return Object.assign({}, item, {
        row: classLabel + " · " + humanGeographyLabel(firstDefined(item, ["row", "rowLabel"], "Unknown band")),
        column: humanGeographyLabel(firstDefined(item, ["column", "columnLabel"], "Value")),
      });
    }).sort(function (left, right) {
      const leftLat = Number(left.latIndex);
      const rightLat = Number(right.latIndex);
      if (Number.isFinite(leftLat) && Number.isFinite(rightLat) && leftLat !== rightLat) return rightLat - leftLat;
      const leftLon = Number(left.lonIndex);
      const rightLon = Number(right.lonIndex);
      if (Number.isFinite(leftLon) && Number.isFinite(rightLon) && leftLon !== rightLon) return leftLon - rightLon;
      return String(left.row || "").localeCompare(String(right.row || "")) || String(left.column || "").localeCompare(String(right.column || ""));
    });
  }

  function geographyMapCells(value) {
    if (Array.isArray(value)) return normalizeGeographyCells(value);
    if (!isObject(value)) return [];
    let cells = [];
    const facets = firstArray(value, ["facets"]);
    if (facets.length) {
      cells = facets.flatMap(function (facet, index) {
        const coordinateClass = cleanText(firstDefined(facet, ["coordinateClass", "coordinate_class", "key", "label", "name"], "facet_" + (index + 1)));
        return firstArray(facet, ["cells", "grid", "values"]).map(function (cell) {
          return Object.assign({ coordinateClass }, cell);
        });
      });
    } else if (isObject(value.byCoordinateClass || value.by_coordinate_class)) {
      const grouped = value.byCoordinateClass || value.by_coordinate_class;
      cells = Object.keys(grouped).sort().flatMap(function (coordinateClass) {
        const group = grouped[coordinateClass];
        const groupCells = Array.isArray(group) ? group : firstArray(group, ["cells", "grid", "values"]);
        return groupCells.map(function (cell) { return Object.assign({ coordinateClass }, cell); });
      });
    } else {
      cells = firstArray(value, ["cells", "grid", "values"]);
    }
    return normalizeGeographyCells(cells);
  }

  function resolvedPatternChartId(value) {
    const requested = cleanText(value);
    const aliases = {
      "analysis-overview": "analysis-coverage-chart",
      "analysis-craft-distribution": "analysis-craft-distribution-chart",
      "analysis-craft-confidence": "analysis-craft-confidence-chart",
      "analysis-time-decades": "analysis-time-series-chart",
      "analysis-month-year": "analysis-month-year-chart",
      "analysis-geography-grid": "analysis-geography-grid-chart",
      "analysis-source-composition": "analysis-source-composition-chart",
      "analysis-source-time": "analysis-source-time-chart",
      "analysis-quality-date-precision": "analysis-quality-audit-chart",
      "analysis-quality-location-precision": "analysis-quality-audit-chart",
      "analysis-quality-coordinate-source": "analysis-quality-audit-chart",
    };
    return aliases[requested] || requested;
  }

  function sourceBalancedDisplay(sourceBalanced, rawSeries) {
    const balanced = asArray(sourceBalanced);
    if (!balanced.length) return [];
    const rawByLabel = new Map(asArray(rawSeries).map(function (item, index) {
      return [datumLabel(item, index), item];
    }));
    return [
      {
        label: "Active · source-balanced share",
        points: balanced.map(function (item, index) {
          const label = datumLabel(item, index);
          const raw = rawByLabel.get(label) || {};
          const activeShare = finiteNumber(firstDefined(item, ["observed", "value"], 0));
          const referenceShare = finiteNumber(firstDefined(item, ["reference", "referenceValue"], 0));
          const rawPreview = isObject(raw.preview) ? raw.preview : (isObject(raw.selection) ? raw.selection : {});
          const itemPreview = isObject(item.preview) ? item.preview : {};
          const cohortSize = firstDefined(raw, ["absoluteCount", "observedCount", "count"], null);
          const patch = firstDefined(item, ["patch", "filterPatch"], firstDefined(raw, ["patch", "filterPatch"], null));
          const selectable = Object.keys(rawPreview).length || Object.keys(itemPreview).length || patch != null;
          return Object.assign({}, raw, item, {
            value: activeShare,
            patch,
            preview: selectable ? Object.assign({}, rawPreview, itemPreview, {
              cohortSize,
              comparison: formatPercent(activeShare) + " source-balanced active vs. " + formatPercent(referenceShare) + " reference",
            }) : null,
          });
        }),
      },
      {
        label: "Reference · source-balanced share",
        points: balanced.map(function (item) {
          return Object.assign({}, item, {
            value: finiteNumber(firstDefined(item, ["reference", "referenceValue"], 0)),
            preview: null,
            selection: null,
            patch: null,
            area: null,
          });
        }),
      },
    ];
  }

  function craftTrendSeries(value) {
    const data = matrixItems(value);
    if (!data.length) return [];
    if (data.some(function (item) { return isObject(item) && Array.isArray(item.points); })) {
      return data.slice();
    }
    const hasCraftDimension = data.some(function (item) {
      return firstDefined(item, ["row", "rowLabel", "craft", "craftLabel", "series", "seriesLabel"], null) != null;
    });
    if (!hasCraftDimension) return data.slice();

    const grouped = new Map();
    data.forEach(function (item, index) {
      const craft = cleanText(firstDefined(
        item,
        ["row", "rowLabel", "craft", "craftLabel", "series", "seriesLabel", "category"],
        "Other craft"
      ), "Other craft");
      const period = cleanText(firstDefined(
        item,
        ["column", "columnLabel", "period", "year", "label"],
        "Period " + (index + 1)
      ));
      if (!grouped.has(craft)) {
        grouped.set(craft, { active: [], reference: [], hasReference: false, colorIndex: grouped.size });
      }
      const group = grouped.get(craft);
      group.active.push(Object.assign({}, item, {
        label: period,
        value: datumValue(item, ["observed", "count", "value"]),
      }));
      const reference = datumReference(item);
      if (reference != null) {
        group.hasReference = true;
        group.reference.push(Object.assign({}, item, {
          label: period,
          value: reference,
          preview: null,
          selection: null,
          patch: null,
          filterPatch: null,
          area: null,
        }));
      }
    });

    const output = [];
    grouped.forEach(function (group, craft) {
      output.push({
        label: craft + " · active",
        points: group.active,
        colorIndex: group.colorIndex,
        reference: false,
      });
      if (group.hasReference) {
        output.push({
          label: craft + " · reference",
          points: group.reference,
          colorIndex: group.colorIndex,
          reference: true,
        });
      }
    });
    return output;
  }

  function sourceCompositionDisplay(value, sourceLimitValue, periodLimitValue) {
    const cells = matrixItems(value);
    const sourceLimit = Math.max(2, Math.trunc(Number(sourceLimitValue) || SOURCE_COMPOSITION_SOURCE_LIMIT));
    const periodLimit = Math.max(1, Math.trunc(Number(periodLimitValue) || SOURCE_COMPOSITION_PERIOD_LIMIT));
    const sources = [];
    const periods = [];
    const sourceScores = new Map();
    const cellLookup = new Map();

    cells.forEach(function (item) {
      const source = cleanText(firstDefined(item, ["row", "rowLabel", "source", "category"], "Unknown source"), "Unknown source");
      const period = cleanText(firstDefined(item, ["column", "columnLabel", "period", "year", "label"], "Unknown period"), "Unknown period");
      if (sources.indexOf(source) === -1) sources.push(source);
      if (periods.indexOf(period) === -1) periods.push(period);
      const activeShare = Math.max(0, finiteNumber(firstDefined(item, ["activeShare", "observedShare", "share", "value", "observed"], 0)));
      const referenceShare = Math.max(0, finiteNumber(firstDefined(item, ["referenceShare", "reference", "referenceValue"], 0)));
      const activeCount = Math.max(0, finiteNumber(firstDefined(item, ["absoluteCount", "activeCount", "count", "observedCount"], 0)));
      const referenceCount = Math.max(0, finiteNumber(firstDefined(item, ["referenceAbsoluteCount", "referenceCount", "baselineCount"], 0)));
      const key = source + "\u0000" + period;
      const previous = cellLookup.get(key);
      cellLookup.set(key, {
        source,
        period,
        activeShare: activeShare + (previous ? previous.activeShare : 0),
        referenceShare: referenceShare + (previous ? previous.referenceShare : 0),
        activeCount: activeCount + (previous ? previous.activeCount : 0),
        referenceCount: referenceCount + (previous ? previous.referenceCount : 0),
        item: previous ? previous.item : item,
      });
      const score = activeCount + referenceCount + activeShare + referenceShare;
      sourceScores.set(source, (sourceScores.get(source) || 0) + score);
    });

    const rankedSources = sources.slice().sort(function (left, right) {
      return (sourceScores.get(right) || 0) - (sourceScores.get(left) || 0)
        || sources.indexOf(left) - sources.indexOf(right);
    });
    const groupedSources = rankedSources.length > sourceLimit;
    const displayedSources = groupedSources
      ? rankedSources.slice(0, sourceLimit - 1).concat(["Other sources"])
      : rankedSources;
    const individualSourceSet = new Set(groupedSources ? displayedSources.slice(0, -1) : displayedSources);
    const orderedPeriods = sortSemanticAxis(periods, "auto");
    const displayedPeriods = sampleEvenly(orderedPeriods, periodLimit);
    const rows = [];

    displayedPeriods.forEach(function (period) {
      displayedSources.forEach(function (source) {
        if (source !== "Other sources") {
          const cell = cellLookup.get(source + "\u0000" + period);
          rows.push(cell || {
            source,
            period,
            activeShare: 0,
            referenceShare: 0,
            activeCount: 0,
            referenceCount: 0,
            item: null,
          });
          return;
        }
        const aggregate = {
          source,
          period,
          activeShare: 0,
          referenceShare: 0,
          activeCount: 0,
          referenceCount: 0,
          item: null,
        };
        rankedSources.forEach(function (candidate) {
          if (individualSourceSet.has(candidate)) return;
          const cell = cellLookup.get(candidate + "\u0000" + period);
          if (!cell) return;
          aggregate.activeShare += cell.activeShare;
          aggregate.referenceShare += cell.referenceShare;
          aggregate.activeCount += cell.activeCount;
          aggregate.referenceCount += cell.referenceCount;
        });
        rows.push(aggregate);
      });
    });

    return {
      cells,
      sources: displayedSources,
      periods: displayedPeriods,
      rows,
      sourceCount: sources.length,
      periodCount: orderedPeriods.length,
      groupedSources,
      sampledPeriods: displayedPeriods.length < periods.length,
    };
  }

  function poissonCountInterval(countValue) {
    const count = Math.max(0, finiteNumber(countValue, 0));
    const center = Math.sqrt(count + 0.375);
    const halfWidth = 1.96 / 2;
    return {
      lower: Math.max(0, Math.pow(Math.max(0, center - halfWidth), 2) - 0.375),
      upper: Math.max(0, Math.pow(center + halfWidth, 2) - 0.375),
    };
  }

  function proportionalTreemap(itemsValue) {
    const items = asArray(itemsValue).map(function (item, index) {
      return {
        item,
        index,
        weight: Math.max(0, finiteNumber(firstDefined(item, ["weight", "count", "value"], 0))),
      };
    }).filter(function (entry) { return entry.weight > 0; });
    const total = items.reduce(function (sum, entry) { return sum + entry.weight; }, 0);
    if (!total) return [];
    const rectangles = [];
    const partition = function (entries, x, y, width, height) {
      if (!entries.length) return;
      if (entries.length === 1) {
        rectangles.push({
          item: entries[0].item,
          sourceIndex: entries[0].index,
          x,
          y,
          width,
          height,
          areaShare: (width * height) / 10000,
        });
        return;
      }
      const weight = entries.reduce(function (sum, entry) { return sum + entry.weight; }, 0);
      let leftWeight = 0;
      let splitIndex = 1;
      let bestDistance = Infinity;
      for (let index = 1; index < entries.length; index += 1) {
        leftWeight += entries[index - 1].weight;
        const distance = Math.abs((weight / 2) - leftWeight);
        if (distance <= bestDistance) {
          bestDistance = distance;
          splitIndex = index;
        } else {
          break;
        }
      }
      const first = entries.slice(0, splitIndex);
      const second = entries.slice(splitIndex);
      const firstWeight = first.reduce(function (sum, entry) { return sum + entry.weight; }, 0);
      const ratio = weight > 0 ? firstWeight / weight : 0.5;
      if (width >= height) {
        const firstWidth = width * ratio;
        partition(first, x, y, firstWidth, height);
        partition(second, x + firstWidth, y, width - firstWidth, height);
      } else {
        const firstHeight = height * ratio;
        partition(first, x, y, width, firstHeight);
        partition(second, x, y + firstHeight, width, height - firstHeight);
      }
    };
    partition(items, 0, 0, 100, 100);
    return rectangles;
  }

  function patternFamilyRank(finding) {
    const family = cleanText(firstDefined(finding, ["family", "statisticalFamily", "statistical_family"], "")).toLowerCase();
    const aliases = {
      temporal: "time_month",
      time: "time_month",
      quality: "date_precision",
    };
    const index = PATTERN_FAMILY_ORDER.indexOf(aliases[family] || family);
    return index === -1 ? PATTERN_FAMILY_ORDER.length : index;
  }

  function patternSignature(finding) {
    return [
      cleanText(firstDefined(finding, ["family", "statisticalFamily", "statistical_family"], "")),
      cleanText(firstDefined(finding, ["key", "category", "id"], "")),
      cleanText(firstDefined(finding, ["title", "label"], "")),
      cleanText(firstDefined(finding, ["observedCount", "observed", "count"], "")),
      cleanText(firstDefined(finding, ["referenceCount", "reference"], "")),
    ].join("\u0000");
  }

  function patternLaneKey(finding) {
    const explicitLane = cleanText(firstDefined(finding, ["findingLane", "finding_lane"], "")).toLowerCase();
    if (explicitLane === "stable_multi_source_content") return "stableMultiSourceContent";
    if (explicitLane === "collection_and_quality") return "collectionAndQuality";
    if (explicitLane === "source_or_region_sensitive") return "sourceOrRegionSensitive";
    const family = cleanText(firstDefined(finding, ["family", "statisticalFamily", "statistical_family"], "")).toLowerCase();
    if (["source", "date_precision", "location_precision", "coordinate_source", "craft_confidence"].indexOf(family) !== -1) {
      return "collectionAndQuality";
    }
    const stability = firstDefined(finding, ["sourceStability", "stability"], {});
    const status = cleanText(isObject(stability) ? firstDefined(stability, ["status", "label"], "") : stability).toLowerCase();
    if (status === "stable_multi_source" || status === "stable" || (isObject(stability) && stability.stable === true)) {
      return "stableMultiSourceContent";
    }
    return "sourceOrRegionSensitive";
  }

  function patternGroupsForDisplay(findings, patternGroups) {
    const flat = asArray(findings);
    const groups = isObject(patternGroups) ? patternGroups : {};
    const explicit = PATTERN_LANES.some(function (lane) { return Array.isArray(groups[lane.key]); });
    const grouped = new Map(PATTERN_LANES.map(function (lane) {
      return [lane.key, explicit ? asArray(groups[lane.key]).slice() : []];
    }));
    if (!explicit) {
      flat.forEach(function (finding) { grouped.get(patternLaneKey(finding)).push(finding); });
    } else {
      const assigned = new Set();
      grouped.forEach(function (items) {
        items.forEach(function (finding) { assigned.add(patternSignature(finding)); });
      });
      flat.forEach(function (finding) {
        if (!assigned.has(patternSignature(finding))) grouped.get(patternLaneKey(finding)).push(finding);
      });
    }

    const flatOrder = new Map();
    flat.forEach(function (finding, index) {
      const signature = patternSignature(finding);
      if (!flatOrder.has(signature)) flatOrder.set(signature, index);
    });
    return PATTERN_LANES.map(function (lane) {
      const patterns = grouped.get(lane.key).map(function (finding, index) {
        return { finding, index };
      }).sort(function (left, right) {
        return patternFamilyRank(left.finding) - patternFamilyRank(right.finding)
          || (flatOrder.has(patternSignature(left.finding)) ? flatOrder.get(patternSignature(left.finding)) : Number.MAX_SAFE_INTEGER)
            - (flatOrder.has(patternSignature(right.finding)) ? flatOrder.get(patternSignature(right.finding)) : Number.MAX_SAFE_INTEGER)
          || left.index - right.index;
      }).map(function (entry) { return entry.finding; });
      return {
        key: lane.key,
        label: lane.label,
        description: lane.description,
        patterns,
      };
    });
  }

  function contextMembershipDisclosure(contextDataValue, summaryValue, fallbackLabel) {
    const contextData = isObject(contextDataValue) ? contextDataValue : {};
    const summary = isObject(summaryValue) ? summaryValue : {};
    const unit = cleanText(
      firstDefined(summary, ["unitLabel", "unit", "unit_of_analysis"], firstDefined(contextData, ["unitLabel", "unit"], fallbackLabel)),
      fallbackLabel
    );
    const policy = cleanText(firstDefined(
      contextData,
      ["policyWarning", "policyWarnings"],
      firstDefined(summary, ["policyWarning", "policyWarnings"], "Descriptive context records only.")
    ));
    const missingness = firstDefined(summary, ["missingnessPolicy", "missingness_policy"], firstDefined(contextData, ["missingnessPolicy", "missingness_policy"], null));
    const statements = ["Membership unit: " + unit + "."];
    if (policy) statements.push("Membership policy: " + policy);
    if (isObject(missingness)) {
      const missingnessUnit = cleanText(firstDefined(missingness, ["unit", "membershipUnit", "membership_unit"], ""));
      const aggregation = cleanText(firstDefined(missingness, ["aggregation", "policy"], ""));
      const requiredFields = asArray(firstDefined(missingness, ["requiredFields", "required_fields"], [])).map(function (field) {
        return cleanText(field);
      }).filter(Boolean);
      const details = [];
      if (missingnessUnit) details.push("unit: " + missingnessUnit);
      if (aggregation) details.push("aggregation: " + aggregation);
      if (requiredFields.length) details.push("required fields: " + requiredFields.join(", "));
      if (details.length) statements.push("Missingness membership " + details.join("; ") + ".");
    }
    return statements.join(" ");
  }

  function contextEnabledForRender(contextDataValue, filterSnapshotValue, domainValue) {
    const contextData = isObject(contextDataValue) ? contextDataValue : {};
    const snapshot = isObject(filterSnapshotValue) ? filterSnapshotValue : {};
    const layers = isObject(snapshot.contextLayers) ? snapshot.contextLayers : {};
    const domain = domainValue === "animals" ? "animals" : "crops";
    const layer = isObject(layers[domain]) ? layers[domain] : null;
    if (layer && Object.prototype.hasOwnProperty.call(layer, "enabled")) {
      return Boolean(layer.enabled);
    }
    return contextData.enabled !== false;
  }

  function readinessForDomain(value, domain) {
    const rows = Array.isArray(value)
      ? value
      : (isObject(value) ? Object.keys(value).filter(function (key) { return isObject(value[key]); }).map(function (key) { return Object.assign({ key, label: key }, value[key]); }) : []);
    const needle = domain === "animals" ? "animal" : (domain === "relationships" ? "relationship" : "crop");
    return rows.filter(function (item) {
      return [firstDefined(item, ["key", "id", "domain"], ""), firstDefined(item, ["label", "name"], "")]
        .some(function (candidate) { return cleanText(candidate).toLowerCase().indexOf(needle) !== -1; });
    });
  }

  function normalizedGateStatus(value, fallback) {
    const status = cleanText(value, fallback || "unknown").toLowerCase().replace(/[\s-]+/g, "_");
    if (["ready_inferential", "ready_sensitivity", "ready_descriptive", "limited", "blocked", "not_applicable", "not_evaluated", "data_unavailable"].indexOf(status) !== -1) return status;
    if (["ready", "eligible", "qualified", "pass", "passed", "available", "exploratory_ready"].indexOf(status) !== -1) return "ready_inferential";
    if (["failed", "fail", "not_estimable", "prohibited", "excluded", "unavailable"].indexOf(status) !== -1) return "blocked";
    if (["partial", "descriptive", "descriptive_only"].indexOf(status) !== -1) return "ready_descriptive";
    if (["sensitivity", "warning"].indexOf(status) !== -1) return "ready_sensitivity";
    if (["not_applicable", "na"].indexOf(status) !== -1) return "not_applicable";
    if (["unknown", "not_reported"].indexOf(status) !== -1) return "data_unavailable";
    return "not_evaluated";
  }

  function readinessStatusLabel(value) {
    const status = normalizedGateStatus(value);
    return READINESS_STATUS_LABELS[status] || humanizeEvidenceReason(status);
  }

  function readinessGateKey(gate, fallback) {
    return cleanText(firstDefined(gate, ["gateId", "gate_id", "key", "id", "gate", "name"], fallback || "gate"))
      .toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "");
  }

  function readinessCounts(item) {
    const input = firstDefined(item, ["inputN", "input_n", "totalN", "total_n", "totalCount", "total_count"], null);
    const passed = firstDefined(item, ["passedN", "passed_n", "eligibleN", "eligible_n", "eligibleCount", "eligible_count", "qualifiedCount", "qualified_count"], null);
    const failed = firstDefined(item, ["failedN", "failed_n"], null);
    const unknown = firstDefined(item, ["unknownN", "unknown_n"], null);
    return { input, passed, failed, unknown };
  }

  function readinessCell(gate, key, fallbackReasonCodes) {
    if (!gate) {
      return {
        key,
        status: "not_evaluated",
        value: readinessStatusLabel("not_evaluated"),
        reason: "No typed gate evaluates this dimension for the domain.",
        reasonCodes: [],
      };
    }
    const applicability = cleanText(firstDefined(gate, ["applicability"], "applicable")).toLowerCase().replace(/[\s-]+/g, "_");
    const status = applicability === "not_applicable"
      ? "not_applicable"
      : normalizedGateStatus(firstDefined(gate, ["status", "result", "state"], "not_evaluated"));
    const counts = readinessCounts(gate);
    const denominatorLabel = cleanText(firstDefined(gate, ["denominatorLabel", "denominator_label"], ""));
    const reasonCodes = asArray(firstDefined(gate, ["reasonCodes", "reason_codes"], fallbackReasonCodes || [])).map(humanizeEvidenceReason).filter(Boolean);
    let value = readinessStatusLabel(status);
    if (status === "not_applicable") value = "N/A";
    else if (counts.passed != null && counts.input != null) value = formatCount(counts.passed) + " / " + formatCount(counts.input);
    else if (counts.passed != null) value = formatCount(counts.passed);
    const countDetails = [
      counts.failed == null ? "" : "failed " + formatCount(counts.failed),
      counts.unknown == null ? "" : "unknown " + formatCount(counts.unknown),
    ].filter(Boolean);
    const reason = [denominatorLabel, countDetails.join("; "), reasonCodes.join("; ")].filter(Boolean).join(". ");
    return { key, status, value, reason, reasonCodes, counts, gate };
  }

  function readinessDomainKey(item) {
    return cleanText(firstDefined(item, ["key", "id", "domain", "label", "name"], "domain"))
      .toLowerCase().replace(/[^a-z0-9]+/g, "");
  }

  function readinessGateEntries(item) {
    const gates = firstDefined(item, ["gates", "readinessGates", "readiness_gates", "gateResults", "gate_results"], null);
    if (Array.isArray(gates)) {
      return gates.map(function (gate, index) {
        return { key: readinessGateKey(gate, "gate_" + (index + 1)), gate };
      }).filter(function (entry) { return entry.key && isObject(entry.gate); });
    }
    if (isObject(gates)) {
      return Object.keys(gates).sort().map(function (rawKey) {
        const gate = isObject(gates[rawKey]) ? gates[rawKey] : { status: gates[rawKey] };
        return { key: readinessGateKey(Object.assign({ gateId: rawKey }, gate), rawKey), gate };
      }).filter(function (entry) { return entry.key; });
    }
    return [];
  }

  function readinessGateStatusRank(gate) {
    const status = normalizedGateStatus(firstDefined(gate, ["status", "result", "state"], "not_evaluated"));
    return {
      ready_inferential: 8,
      ready_sensitivity: 7,
      ready_descriptive: 6,
      limited: 5,
      blocked: 4,
      not_applicable: 3,
      not_evaluated: 2,
      data_unavailable: 1,
    }[status] || 0;
  }

  function readinessRepresentativeGate(entries, domainKey, columnKey) {
    const candidates = entries.filter(function (entry) {
      return asArray(READINESS_GATE_COLUMN_MAP[entry.key]).indexOf(columnKey) !== -1;
    });
    if (!candidates.length) return null;
    const preference = READINESS_DOMAIN_GATE_PREFERENCES[domainKey] &&
      READINESS_DOMAIN_GATE_PREFERENCES[domainKey][columnKey];
    if (preference) {
      const preferred = candidates.find(function (entry) { return entry.key === preference; });
      if (preferred) return preferred;
    }
    return candidates.slice().sort(function (left, right) {
      const statusDifference = readinessGateStatusRank(right.gate) - readinessGateStatusRank(left.gate);
      if (statusDifference) return statusDifference;
      const leftCounts = readinessCounts(left.gate);
      const rightCounts = readinessCounts(right.gate);
      const leftRate = Number(leftCounts.input) > 0 ? Number(leftCounts.passed) / Number(leftCounts.input) : -1;
      const rightRate = Number(rightCounts.input) > 0 ? Number(rightCounts.passed) / Number(rightCounts.input) : -1;
      if (rightRate !== leftRate) return rightRate - leftRate;
      return left.key.localeCompare(right.key);
    })[0];
  }

  function readinessMatrix(value) {
    const source = Array.isArray(value) ? value : firstArray(value, ["domains", "readiness", "rows", "items"]);
    const rows = (source.length ? source : (isObject(value) ? Object.keys(value).filter(function (key) {
      return isObject(value[key]);
    }).map(function (key) { return Object.assign({ key, label: key }, value[key]); }) : [])).filter(function (item) {
      const identity = cleanText(firstDefined(item, ["key", "id", "label", "name"], "")).toLowerCase();
      return !(identity.indexOf("chronology") !== -1 && identity.indexOf("connector") !== -1);
    });
    const typed = rows.some(function (item) { return readinessGateEntries(item).length > 0; });
    const definitions = READINESS_MATRIX_COLUMNS.slice();
    return {
      columns: definitions,
      typed,
      rows: rows.map(function (item, index) {
        const label = datumLabel(item, index);
        const eligible = firstDefined(item, ["eligibleN", "eligible_n", "eligibleCount", "eligible_count", "qualifiedCount", "qualified_count"], null);
        const total = firstDefined(item, ["totalN", "total_n", "totalCount", "total_count", "count"], null);
        const reasonValue = firstDefined(item, ["reasons", "suppressionReasons", "suppression_reasons", "message", "reason", "policyWarning", "policy_warning"], "");
        const reasons = (Array.isArray(reasonValue) ? reasonValue : [reasonValue]).map(humanizeEvidenceReason).filter(Boolean);
        const reasonCodes = asArray(firstDefined(item, ["reasonCodes", "reason_codes"], [])).map(humanizeEvidenceReason).filter(Boolean);
        const gateEntries = readinessGateEntries(item);
        const domainKey = readinessDomainKey(item);
        const cells = definitions.map(function (definition) {
          if (definition.key === "overall") {
            const outputCell = readinessCell(item, definition.key, reasonCodes);
            outputCell.value = readinessStatusLabel(outputCell.status);
            return outputCell;
          }
          const representative = readinessRepresentativeGate(gateEntries, domainKey, definition.key);
          const cell = readinessCell(representative && representative.gate, definition.key, reasonCodes);
          cell.gateIds = gateEntries.filter(function (entry) {
            return asArray(READINESS_GATE_COLUMN_MAP[entry.key]).indexOf(definition.key) !== -1;
          }).map(function (entry) { return entry.key; });
          if (representative) cell.representativeGateId = representative.key;
          return cell;
        });
        const detailedGates = gateEntries.map(function (entry) {
          return {
            key: entry.key,
            label: cleanText(firstDefined(entry.gate, ["label", "name"], humanizeEvidenceReason(entry.key))),
            applicability: cleanText(firstDefined(entry.gate, ["applicability"], "applicable")),
            policyId: cleanText(firstDefined(entry.gate, ["policyId", "policy_id"], "No policy identifier")),
            evidenceHash: cleanText(firstDefined(entry.gate, ["evidenceHash", "evidence_hash", "releaseHash", "release_hash"], "Unavailable")),
            cell: readinessCell(entry.gate, entry.key, reasonCodes),
            gate: entry.gate,
          };
        });
        return { label, eligible, total, reasons: reasons.concat(reasonCodes), item, cells, detailedGates };
      }),
    };
  }

  function relationshipMatrix(value) {
    const direct = matrixItems(value);
    if (direct.length && direct.some(function (item) {
      return firstDefined(item, ["row", "rowLabel", "lane", "relationshipType", "relationship_type"], null) != null;
    })) return direct.map(function (item) {
      const lane = cleanText(firstDefined(item, ["lane", "evidenceLane", "evidence_lane"], ""));
      const relationshipType = cleanText(firstDefined(item, ["relationshipType", "relationship_type", "row", "rowLabel"], "Relationship"));
      return Object.assign({}, item, {
        row: lane ? lane.replace(/_/g, " ") + " · " + relationshipType.replace(/_/g, " ") : relationshipType.replace(/_/g, " "),
        column: cleanText(firstDefined(item, ["reconciliation", "reconciliationStatus", "reconciliation_status", "column", "columnLabel"], "State")).replace(/_/g, " "),
        value: finiteNumber(firstDefined(item, ["count", "value"], 0)),
        estimateAvailable: true,
        inferenceEligible: false,
        status: "descriptive_only",
      });
    });
    const source = Array.isArray(value) ? value[0] : value;
    if (!isObject(source)) return [];
    const details = firstDefined(source, ["laneCounts", "lane_counts", "details", "counts"], source);
    if (!isObject(details)) return [];
    const definitions = [
      ["explicitSource", "Explicit-source", "Relationship lane"],
      ["computedCandidate", "Computed candidate", "Relationship lane"],
      ["analystReviewed", "Analyst-reviewed", "Relationship lane"],
      ["reconciledCurrent", "Reconciled current", "Reconciliation"],
      ["reconciledUnmapped", "Reconciled unmapped", "Reconciliation"],
      ["quarantinedSubject", "Quarantined subject", "Quarantine"],
      ["quarantinedObject", "Quarantined object", "Quarantine"],
      ["associationEligible", "Association eligible", "Output"],
    ];
    return definitions.map(function (definition) {
      const snake = definition[0].replace(/[A-Z]/g, function (letter) { return "_" + letter.toLowerCase(); });
      const count = firstDefined(details, [definition[0], definition[0] + "N", snake, snake + "_n"], null);
      if (count == null) return null;
      return { row: definition[2], column: definition[1], value: Number(count), count: Number(count), estimateAvailable: true, inferenceEligible: false, status: "descriptive_only" };
    }).filter(Boolean);
  }

  function positiveSeriesMaximum(values) {
    const maximum = Math.max.apply(null, (Array.isArray(values) ? values : []).map(function (value) {
      return Math.max(0, Number(value) || 0);
    }).concat([0]));
    return Math.max(Number.EPSILON, maximum);
  }

  function previewValueList(value) {
    return asArray(value).map(function (item) { return cleanText(item); }).filter(Boolean).join(", ");
  }

  function previewOrdinalLabel(value) {
    if (value == null || value === "") return "";
    const ordinal = Number(value);
    if (!Number.isFinite(ordinal)) return cleanText(value);
    try {
      return new Date(Math.round(ordinal) * 86400000).toISOString().slice(0, 10);
    } catch (_error) {
      return "Ordinal " + Math.round(ordinal);
    }
  }

  function inferPreviewCriteria(patchValue, areaValue) {
    const patch = isObject(patchValue) ? patchValue : {};
    const filters = isObject(patch.filters) ? patch.filters : patch;
    const criteria = [];
    const dateRange = firstDefined(patch, ["dateRange", "timeRange"],
      patch.startOrdinal != null || patch.endOrdinal != null ? patch : null);
    if (isObject(dateRange)) {
      const start = firstDefined(dateRange, ["startIso", "start", "startOrdinal"], null);
      const end = firstDefined(dateRange, ["endIso", "end", "endOrdinal"], null);
      const label = [previewOrdinalLabel(start), previewOrdinalLabel(end)].filter(Boolean).join(" to ");
      if (label) criteria.push({ label: "Date range", value: label });
    }
    [
      ["Source", ["sources", "selectedSources"]],
      ["Report type", ["types", "selectedTypes", "reportTypes"]],
      ["Precision", ["precisions", "selectedPrecisions"]],
      ["Craft type", ["craftTypes", "selectedCraftTypes", "craft"]],
    ].forEach(function (definition) {
      const value = firstDefined(filters, definition[1], null);
      const display = previewValueList(value);
      if (display) criteria.push({ label: definition[0], value: display });
    });
    if (Object.prototype.hasOwnProperty.call(filters, "hideLowPrecision")) {
      criteria.push({ label: "Precision", value: filters.hideLowPrecision ? "Hide low precision" : "Include low precision" });
    }
    if (Object.prototype.hasOwnProperty.call(filters, "hideNonExactDates")) {
      criteria.push({ label: "Date precision", value: filters.hideNonExactDates ? "Exact dates only" : "Include non-exact dates" });
    }
    const area = isObject(areaValue) ? areaValue : firstDefined(patch, ["area", "areaFilter"], null);
    const bounds = isObject(area) && isObject(area.bounds) ? area.bounds : area;
    if (isObject(bounds)) {
      const south = firstDefined(bounds, ["south", "minLat"], null);
      const west = firstDefined(bounds, ["west", "minLng", "minLon"], null);
      const north = firstDefined(bounds, ["north", "maxLat"], null);
      const east = firstDefined(bounds, ["east", "maxLng", "maxLon"], null);
      if ([south, west, north, east].every(function (value) { return Number.isFinite(Number(value)); })) {
        criteria.push({
          label: "Geography bounds",
          value: "S " + formatDecimal(south, 2) + ", W " + formatDecimal(west, 2)
            + ", N " + formatDecimal(north, 2) + ", E " + formatDecimal(east, 2),
        });
      }
    }
    return criteria;
  }

  function evidenceBreakdownText(value, labelKeys) {
    return asArray(value).slice(0, 5).map(function (entry) {
      if (!isObject(entry)) return cleanText(entry);
      const label = cleanText(firstDefined(entry, asArray(labelKeys).concat(["label", "value", "key"]), "Unknown"), "Unknown");
      const count = firstDefined(entry, ["count", "n"], null);
      const share = firstDefined(entry, ["share", "rate"], null);
      return label.replace(/_/g, " ")
        + (share == null ? "" : " " + formatPercent(share))
        + (count == null ? "" : " (n=" + formatCount(count) + ")");
    }).filter(Boolean).join(", ");
  }

  function previewForDatum(item, label, summary, defaultKind) {
    const source = item || {};
    const explicit = isObject(source.preview) ? source.preview : null;
    const selection = isObject(source.selection) ? source.selection : null;
    const patch = firstDefined(source, ["patch", "filterPatch"], selection && firstDefined(selection, ["patch", "filterPatch"], null));
    const area = firstDefined(source, ["area", "areaFilter", "geometry"], selection && firstDefined(selection, ["area", "areaFilter", "geometry"], null));
    if (!explicit && !selection && patch == null && area == null) return null;
    const input = Object.assign({}, selection || {}, explicit || {});
    const kind = cleanText(firstDefined(input, ["kind", "type"], area != null ? "area" : (defaultKind || "filter"))).toLowerCase() === "area"
      ? "area"
      : "filter";
    const observed = datumValue(source);
    const reference = datumReference(source);
    const absoluteObserved = firstDefined(source, ["absoluteCount", "observedCount", "count"], observed);
    const absoluteReference = firstDefined(source, ["referenceAbsoluteCount", "referenceCount"], reference);
    const resolvedPatch = firstDefined(input, ["patch", "filterPatch"], patch);
    const resolvedArea = firstDefined(input, ["area", "areaFilter", "geometry"], area);
    const explicitCriteria = asArray(firstDefined(input, ["criteria", "changedCriteria"], []));
    const criteria = explicitCriteria.length ? explicitCriteria.slice() : inferPreviewCriteria(resolvedPatch, resolvedArea);
    if (kind === "area") {
      const adjustedActiveShare = firstDefined(source, ["adjustedActiveShare", "adjusted_active_share"], null);
      const adjustedReferenceShare = firstDefined(source, ["adjustedReferenceShare", "adjusted_reference_share"], null);
      const adjustedDifference = firstDefined(source, ["adjustedDifference", "adjusted_difference", "effect"], null);
      const interval = intervalBounds(source);
      const qValue = firstDefined(source, ["qValue", "q_value", "q"], null);
      const supportRate = firstDefined(source, ["commonSupportRate", "common_support_rate"], null);
      const coordinateClass = cleanText(firstDefined(source, ["coordinateClass", "coordinate_class"], "")).replace(/_/g, " ");
      if (coordinateClass) criteria.push({ label: "Coordinate class", value: coordinateClass });
      const sourceMixText = evidenceBreakdownText(firstDefined(source, ["sourceMix", "source_mix"], []), ["source"]);
      if (sourceMixText) criteria.push({ label: "Source mix", value: sourceMixText });
      const provenance = firstDefined(source, ["geographyAssignmentProvenance", "geography_assignment_provenance"], {});
      [
        ["Assignment source", ["assignmentSources", "assignment_sources"], ["value"], ["geographyAssignmentSource", "geography_assignment_source"]],
        ["Assignment confidence", ["assignmentConfidences", "assignment_confidences"], ["value"], ["geographyAssignmentConfidence", "geography_assignment_confidence"]],
        ["Boundary status", ["boundaryStatuses", "boundary_statuses"], ["value"], ["geographyBoundaryStatus", "geography_boundary_status"]],
        ["Unknown status", ["unknownStatuses", "unknown_statuses"], ["value"], ["geographyUnknownStatus", "geography_unknown_status"]],
        ["Macroregion", ["macroregions"], ["value"], ["macroregion", "analysisMacroregion", "analysis_macroregion"]],
      ].forEach(function (definition) {
        const breakdown = isObject(provenance)
          ? evidenceBreakdownText(firstDefined(provenance, definition[1], []), definition[2])
          : "";
        const fallback = cleanText(firstDefined(source, definition[3], "")).replace(/_/g, " ");
        if (breakdown || fallback) criteria.push({ label: definition[0], value: breakdown || fallback });
      });
      if (adjustedActiveShare != null) criteria.push({ label: "Adjusted active share", value: formatPercent(adjustedActiveShare) });
      if (adjustedReferenceShare != null) criteria.push({ label: "Adjusted reference share", value: formatPercent(adjustedReferenceShare) });
      if (adjustedDifference != null) criteria.push({ label: "Adjusted difference", value: formatSignedPercent(adjustedDifference) });
      if (interval) criteria.push({ label: "95% interval", value: formatPercentInterval(interval) });
      if (qValue != null) criteria.push({ label: "q-value", value: formatDecimal(qValue, 4) });
      if (supportRate != null) criteria.push({ label: "Common support", value: formatPercent(supportRate) });
    }
    return Object.assign({}, input, {
      kind,
      title: cleanText(input.title, label),
      summary: cleanText(input.summary, "Preview reports represented by " + label + "."),
      cohortSize: firstDefined(input, ["cohortSize", "count"], absoluteObserved),
      missingness: firstDefined(
        input,
        ["missingness", "missingRate"],
        firstDefined(source, ["missingness", "missingRate"], "Not computed for this preview")
      ),
      comparison: cleanText(
        input.comparison,
        absoluteReference == null ? "No reference value" : formatCount(absoluteObserved) + " active vs. " + formatCount(absoluteReference) + " reference"
      ),
      criteria,
      patch: resolvedPatch,
      area: resolvedArea,
    });
  }

  function datumHasPreview(item) {
    const source = item || {};
    if (isObject(source.preview) || isObject(source.selection)) return true;
    return firstDefined(source, ["patch", "filterPatch", "area", "areaFilter", "geometry"], null) != null;
  }

  function setElementInert(element, inert) {
    if (!element) return;
    element.inert = Boolean(inert);
    if (inert) {
      element.setAttribute("inert", "");
      element.setAttribute("aria-hidden", "true");
    } else {
      element.removeAttribute("inert");
      element.setAttribute("aria-hidden", "false");
    }
  }

  class AnalysisViewController {
    constructor(options) {
      const config = options || {};
      this.document = config.document || (typeof document !== "undefined" ? document : null);
      if (!this.document || typeof this.document.getElementById !== "function") {
        throw new TypeError("AnalysisViewController requires a document.");
      }
      this.ids = Object.assign({}, DEFAULT_IDS, config.ids || {});
      this.callbacks = {
        onViewChange: typeof config.onViewChange === "function" ? config.onViewChange : null,
        onBaselineChange: typeof config.onBaselineChange === "function" ? config.onBaselineChange : null,
        onApplyFilterPreview: typeof config.onApplyFilterPreview === "function" ? config.onApplyFilterPreview : null,
        onApplyAreaPreview: typeof config.onApplyAreaPreview === "function" ? config.onApplyAreaPreview : null,
        onCancelPreview: typeof config.onCancelPreview === "function" ? config.onCancelPreview : null,
        onRetryAnalysis: typeof config.onRetryAnalysis === "function" ? config.onRetryAnalysis : null,
        onContextLayerChange: typeof config.onContextLayerChange === "function" ? config.onContextLayerChange : null,
        onContextView: typeof config.onContextView === "function" ? config.onContextView : null,
        onExportEvidence: typeof config.onExportEvidence === "function"
          ? config.onExportEvidence
          : (typeof config.onEvidenceExport === "function" ? config.onEvidenceExport : null),
        onSectionActivate: typeof config.onSectionActivate === "function" ? config.onSectionActivate : null,
        onGeographyRequested: typeof config.onGeographyRequested === "function" ? config.onGeographyRequested : null,
        onSpatialEvidenceRequested: typeof config.onSpatialEvidenceRequested === "function" ? config.onSpatialEvidenceRequested : null,
        onRenderComplete: typeof config.onRenderComplete === "function" ? config.onRenderComplete : null,
        getFilterSnapshot: typeof config.getFilterSnapshot === "function" ? config.getFilterSnapshot : null,
        getWorldReferenceData: typeof config.getWorldReferenceData === "function" ? config.getWorldReferenceData : null,
      };
      this.listeners = [];
      this.currentPreview = null;
      this.previousPreviewFocus = null;
      this.previewPending = false;
      this.analysisInitialized = false;
      this.analysisState = "loading";
      this.currentAnalysisMode = "comparative";
      this.currentComparisonState = "inferential";
      this.activeView = "map";
      this.latestResult = null;
      this.latestMeta = {};
      this.sectionLinks = [];
      this.sectionEntries = [];
      this.activeSectionId = "analysis-section-overview";
      this.sectionObserver = null;
      this.sectionScrollFrame = null;
      this.anchorCorrectionTimerId = null;
      this.spatialRequested = false;
      this.contextSubviewEntries = [];
      this.activeContextSubviewId = "analysis-crop-context";
      this.geographyRequested = false;
      this.worldPathCache = typeof WeakMap === "function" ? new WeakMap() : new Map();
      this.worldEqualAreaPathCache = typeof WeakMap === "function" ? new WeakMap() : new Map();
      this.cachedWorldReferenceData = null;
      this.resultRenderVersion = 0;
      this.renderPlans = new Map();
      this.renderedPlanVersions = new Map();
      this.deferredDisclosureJobs = new Map();
      this.renderFinalState = "ready";
      this.activeRenderPlanKeys = [];
      this.activeRenderTargetIds = [];
      this.contextState = {
        crops: { enabled: true, status: "ready", message: "Included" },
        animals: { enabled: true, status: "ready", message: "Included" },
      };
      const documentView = this.document.defaultView || null;
      this.documentView = documentView;
      this.IntersectionObserver = config.IntersectionObserver
        || (documentView && documentView.IntersectionObserver)
        || (typeof IntersectionObserver === "function" ? IntersectionObserver : null);
      this.requestRenderFrame = typeof config.requestAnimationFrame === "function"
        ? config.requestAnimationFrame
        : (documentView && typeof documentView.requestAnimationFrame === "function"
          ? documentView.requestAnimationFrame.bind(documentView)
          : null);
      this.cancelRenderFrame = typeof config.cancelAnimationFrame === "function"
        ? config.cancelAnimationFrame
        : (documentView && typeof documentView.cancelAnimationFrame === "function"
          ? documentView.cancelAnimationFrame.bind(documentView)
          : null);
      this.renderGeneration = 0;
      this.renderFrameId = null;
      this.renderPending = false;
      this.renderCompletionState = null;
      this.renderCompletionMessage = "";
      this.els = {};
      Object.keys(this.ids).forEach((key) => {
        this.els[key] = this.document.getElementById(this.ids[key]);
      });
      [
        "tablist", "mapTab", "analysisTab", "tabStatus", "mapPanel", "analysisPanel",
        "baseline", "baselineNote", "stateRegion", "loading", "empty", "error", "content",
        "previewDrawer", "previewTitle", "previewCriteria", "previewApplyFilters",
        "previewApplyArea", "previewCancel", "previewCancelTop",
      ].forEach((key) => {
        if (!this.els[key]) throw new Error("Analysis view element is missing: #" + this.ids[key]);
      });
      this.analysisEnabled = !this.els.analysisTab.disabled && this.els.analysisTab.getAttribute("aria-disabled") !== "true";
      this.baselineMode = normalizeBaselineMode(this.els.baseline.value);
      this._bindEvents();
      this._initializeSectionNavigation();
      this._initializeContextSubviewNavigation();
      this.setBaselineMode(this.els.baseline.value, { notify: false });
      this.setActiveView("map", { force: true, silent: true, source: "initial" });
    }

    _listen(element, eventName, handler) {
      if (!element || typeof element.addEventListener !== "function") return;
      element.addEventListener(eventName, handler);
      this.listeners.push([element, eventName, handler]);
    }

    _setDeferredDisclosureJobs(disclosureId, jobs) {
      const entry = {
        version: this.resultRenderVersion,
        jobs: asArray(jobs).filter(function (job) { return typeof job === "function"; }),
        rendered: false,
      };
      this.deferredDisclosureJobs.set(disclosureId, entry);
      const disclosure = this.document.getElementById(disclosureId);
      if (disclosure && disclosure.open) this._renderDeferredDisclosure(disclosureId);
      return entry;
    }

    _renderDeferredDisclosure(disclosureId) {
      const disclosure = this.document.getElementById(disclosureId);
      const entry = this.deferredDisclosureJobs.get(disclosureId);
      if (!disclosure || !disclosure.open || !entry || entry.rendered || entry.version !== this.resultRenderVersion) return false;
      entry.rendered = true;
      disclosure.setAttribute("aria-busy", "true");
      let index = 0;
      const runNext = () => {
        if (this.deferredDisclosureJobs.get(disclosureId) !== entry || entry.version !== this.resultRenderVersion || !disclosure.open) {
          entry.rendered = false;
          disclosure.setAttribute("aria-busy", "false");
          return;
        }
        entry.jobs[index]();
        index += 1;
        if (index >= entry.jobs.length) {
          disclosure.setAttribute("aria-busy", "false");
          return;
        }
        if (this.requestRenderFrame) this.requestRenderFrame(runNext);
        else runNext();
      };
      if (!entry.jobs.length) {
        disclosure.setAttribute("aria-busy", "false");
        return false;
      }
      if (this.requestRenderFrame) this.requestRenderFrame(runNext);
      else runNext();
      return true;
    }

    _bindEvents() {
      this._listen(this.els.mapTab, "click", () => {
        this.setActiveView("map", { source: "click" });
      });
      this._listen(this.els.analysisTab, "click", () => {
        this.setActiveView("analysis", { source: "click" });
      });
      this._listen(this.els.tablist, "keydown", (event) => this._handleTabKeydown(event));
      this._listen(this.els.baseline, "change", () => {
        this.setBaselineMode(this.els.baseline.value, { notify: true });
      });
      this._listen(this.els.previewApplyFilters, "click", () => this._applyPreview("filter"));
      this._listen(this.els.previewApplyArea, "click", () => this._applyPreview("area"));
      this._listen(this.els.previewCancel, "click", () => this._cancelPreview());
      this._listen(this.els.previewCancelTop, "click", () => this._cancelPreview());
      this._listen(this.els.previewDrawer, "keydown", (event) => {
        if (event.key !== "Escape") return;
        event.preventDefault();
        this._cancelPreview();
      });
      this._listen(this.els.errorRetry, "click", () => {
        if (this.callbacks.onRetryAnalysis) this.callbacks.onRetryAnalysis();
      });
      this._listen(this.els.cropInclude, "click", () => this._requestContextLayerChange("crops"));
      this._listen(this.els.animalInclude, "click", () => this._requestContextLayerChange("animals"));
      this._listen(this.els.cropView, "click", (event) => this._handleContextView(event, "crops", "analysis-crop-context"));
      this._listen(this.els.animalView, "click", (event) => this._handleContextView(event, "animals", "analysis-animal-context"));
      this._listen(this.els.exportJson, "click", () => this._exportEvidence("json"));
      this._listen(this.els.exportCsv, "click", () => this._exportEvidence("csv"));
      [
        "analysis-spatial-matrix-disclosure",
        "analysis-spatial-context-disclosure",
        "analysis-spatial-facility-disclosure",
      ].forEach((disclosureId) => {
        this._listen(this.document.getElementById(disclosureId), "toggle", () => this._renderDeferredDisclosure(disclosureId));
      });
    }

    _sectionLinkElements() {
      if (!this.els.sectionNav) return [];
      if (typeof this.els.sectionNav.querySelectorAll === "function") {
        return Array.from(this.els.sectionNav.querySelectorAll('[role="tab"][aria-controls^="analysis-section-"], a[href^="#analysis-section-"]'));
      }
      return Array.prototype.slice.call(this.els.sectionNav.children || []).filter(function (child) {
        if (!child || !child.tagName || !child.getAttribute) return false;
        return /^analysis-section-/.test(cleanText(child.getAttribute("aria-controls")))
          || /^#analysis-section-/.test(cleanText(child.getAttribute("href")));
      });
    }

    _sectionIdForLink(link) {
      if (!link || !link.getAttribute) return "";
      return cleanText(link.getAttribute("aria-controls") || link.getAttribute("href")).replace(/^#/, "");
    }

    _prefersReducedMotion() {
      return Boolean(this.documentView && typeof this.documentView.matchMedia === "function"
        && this.documentView.matchMedia("(prefers-reduced-motion: reduce)").matches);
    }

    _initializeSectionNavigation() {
      this.sectionLinks = this._sectionLinkElements();
      this.sectionEntries = this.sectionLinks.map((link) => ({
        link,
        id: this._sectionIdForLink(link),
        section: this.document.getElementById(this._sectionIdForLink(link)),
      })).filter(function (entry) { return Boolean(entry.id && entry.section); });
      if (!this.sectionEntries.length) return;
      this.els.sectionNav.setAttribute("role", "tablist");
      this.els.sectionNav.setAttribute("aria-label", cleanText(this.els.sectionNav.getAttribute("aria-label"), "Analysis sections"));
      this.sectionEntries.forEach((entry) => {
        const linkId = cleanText(entry.link.getAttribute("id"), entry.id + "-tab");
        entry.link.setAttribute("id", linkId);
        entry.link.setAttribute("role", "tab");
        entry.link.setAttribute("aria-controls", entry.id);
        entry.section.setAttribute("role", "tabpanel");
        entry.section.setAttribute("aria-labelledby", linkId);
        entry.section.setAttribute("tabindex", "0");
        this._listen(entry.link, "click", (event) => {
          if (event && typeof event.preventDefault === "function") event.preventDefault();
          this.navigateToSection(entry.id, { updateHash: true, focus: true, source: "section-link" });
        });
      });
      this._listen(this.els.sectionNav, "keydown", (event) => this._handleSectionNavKeydown(event));
      if (this.documentView) {
        this._listen(this.documentView, "resize", () => this._scheduleSectionScrollspy());
        this._listen(this.documentView, "hashchange", () => this._honorAnalysisHash({ focus: false }));
      }
      this.setActiveSection(this.sectionEntries[0].id, { scrollLink: false, source: "initial" });
    }

    _initializeContextSubviewNavigation() {
      const tablist = this.document.getElementById("analysis-context-subview-tabs");
      if (!tablist || typeof tablist.querySelectorAll !== "function") return;
      this.contextSubviewEntries = Array.from(tablist.querySelectorAll('[role="tab"][aria-controls]')).map((tab) => {
        const panelId = cleanText(tab.getAttribute("aria-controls"));
        return { tab, panelId, panel: this.document.getElementById(panelId) };
      }).filter(function (entry) { return Boolean(entry.panelId && entry.panel); });
      if (!this.contextSubviewEntries.length) return;
      this.contextSubviewEntries.forEach((entry) => {
        this._listen(entry.tab, "click", (event) => {
          if (event && typeof event.preventDefault === "function") event.preventDefault();
          this.setActiveContextSubview(entry.panelId, { focus: true, updateHash: true, source: "click" });
        });
      });
      this._listen(tablist, "keydown", (event) => this._handleContextSubviewKeydown(event));
      const selected = this.contextSubviewEntries.find(function (entry) {
        return entry.tab.getAttribute("aria-selected") === "true";
      }) || this.contextSubviewEntries[0];
      this.setActiveContextSubview(selected.panelId, { focus: false, source: "initial" });
    }

    _handleContextSubviewKeydown(event) {
      const supported = ["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Home", "End"];
      if (!event || supported.indexOf(event.key) === -1 || !this.contextSubviewEntries.length) return;
      let index = this.contextSubviewEntries.findIndex(function (entry) { return entry.tab === event.target; });
      if (index < 0) index = Math.max(0, this.contextSubviewEntries.findIndex((entry) => entry.panelId === this.activeContextSubviewId));
      if (event.key === "Home") index = 0;
      else if (event.key === "End") index = this.contextSubviewEntries.length - 1;
      else if (event.key === "ArrowLeft" || event.key === "ArrowUp") index = (index - 1 + this.contextSubviewEntries.length) % this.contextSubviewEntries.length;
      else index = (index + 1) % this.contextSubviewEntries.length;
      event.preventDefault();
      this.setActiveContextSubview(this.contextSubviewEntries[index].panelId, { focus: true, updateHash: true, source: "keyboard" });
    }

    setActiveContextSubview(panelId, options) {
      const selected = this.contextSubviewEntries.find(function (entry) { return entry.panelId === panelId; });
      if (!selected) return false;
      const previousPanelId = this.activeContextSubviewId;
      this.activeContextSubviewId = panelId;
      this.contextSubviewEntries.forEach(function (entry) {
        const active = entry.panelId === panelId;
        entry.tab.classList.toggle("is-active", active);
        entry.tab.setAttribute("aria-selected", active ? "true" : "false");
        entry.tab.setAttribute("tabindex", active ? "0" : "-1");
        entry.panel.hidden = !active;
        entry.panel.setAttribute("aria-hidden", active ? "false" : "true");
        setElementInert(entry.panel, !active);
      });
      if (options && options.focus && typeof selected.tab.focus === "function") {
        selected.tab.focus({ preventScroll: true });
      }
      if (options && options.updateHash) this._replaceHash(panelId);
      if (this.activeSectionId === "analysis-section-context" && previousPanelId !== panelId) {
        if (this.renderPending) this._cancelActiveRenderScope();
        this._renderActiveSectionIfNeeded();
      }
      return true;
    }

    _handleSectionNavKeydown(event) {
      const supported = ["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Home", "End"];
      if (!event || supported.indexOf(event.key) === -1 || !this.sectionEntries.length) return;
      let index = this.sectionEntries.findIndex(function (entry) { return entry.link === event.target; });
      if (index < 0) index = Math.max(0, this.sectionEntries.findIndex((entry) => entry.id === this.activeSectionId));
      if (event.key === "Home") index = 0;
      else if (event.key === "End") index = this.sectionEntries.length - 1;
      else if (event.key === "ArrowLeft" || event.key === "ArrowUp") index = (index - 1 + this.sectionEntries.length) % this.sectionEntries.length;
      else index = (index + 1) % this.sectionEntries.length;
      event.preventDefault();
      const entry = this.sectionEntries[index];
      this.navigateToSection(entry.id, { updateHash: true, focus: true, source: "section-keyboard" });
    }

    _handleSectionIntersections(entries) {
      const visible = asArray(entries).filter(function (entry) { return entry && entry.isIntersecting; });
      if (!visible.length) return;
      visible.sort(function (left, right) {
        const leftTop = left.boundingClientRect ? Math.abs(left.boundingClientRect.top - 96) : 0;
        const rightTop = right.boundingClientRect ? Math.abs(right.boundingClientRect.top - 96) : 0;
        return leftTop - rightTop;
      });
      const id = cleanText(visible[0].target && visible[0].target.getAttribute && visible[0].target.getAttribute("id"));
      if (id) this._setActiveSection(id, { source: "scrollspy" });
    }

    _scheduleSectionScrollspy() {
      if (this.sectionScrollFrame != null) return;
      const run = () => {
        this.sectionScrollFrame = null;
        this._revealActiveSectionLink();
      };
      if (this.requestRenderFrame) this.sectionScrollFrame = this.requestRenderFrame(run);
      else run();
    }

    _updateSectionFromGeometry() {
      this._revealActiveSectionLink();
    }

    _revealActiveSectionLink() {
      const activeEntry = this.sectionEntries.find((entry) => entry.id === this.activeSectionId);
      const nav = this.els.sectionNav;
      if (!activeEntry || !activeEntry.link || !nav ||
          typeof activeEntry.link.getBoundingClientRect !== "function" || typeof nav.getBoundingClientRect !== "function") return false;
      const linkRect = activeEntry.link.getBoundingClientRect();
      const navRect = nav.getBoundingClientRect();
      let nextScrollLeft = null;
      if (linkRect.left < navRect.left + 8) {
        nextScrollLeft = Math.max(0, Number(nav.scrollLeft || 0) - ((navRect.left + 8) - linkRect.left));
      } else if (linkRect.right > navRect.right - 8) {
        nextScrollLeft = Number(nav.scrollLeft || 0) + (linkRect.right - (navRect.right - 8));
      }
      if (nextScrollLeft == null) return false;
      if (typeof nav.scrollTo === "function") {
        nav.scrollTo({ left: nextScrollLeft, behavior: this._prefersReducedMotion() ? "auto" : "smooth" });
      } else {
        nav.scrollLeft = nextScrollLeft;
      }
      return true;
    }

    setActiveSection(sectionId, options) {
      if (!this.sectionEntries.some(function (entry) { return entry.id === sectionId; })) return false;
      const previousSectionId = this.activeSectionId;
      this.activeSectionId = sectionId;
      this.sectionEntries.forEach(function (entry) {
        const active = entry.id === sectionId;
        if (entry.link.classList) entry.link.classList.toggle("is-active", active);
        entry.link.setAttribute("aria-selected", active ? "true" : "false");
        entry.link.setAttribute("tabindex", active ? "0" : "-1");
        if (active) entry.link.setAttribute("aria-current", "location");
        else entry.link.removeAttribute("aria-current");
        entry.section.hidden = !active;
        entry.section.setAttribute("aria-hidden", active ? "false" : "true");
        setElementInert(entry.section, !active);
      });
      if (!options || options.scrollLink !== false) this._revealActiveSectionLink();
      if ((previousSectionId !== sectionId || sectionId === "analysis-section-context") && this.callbacks.onSectionActivate) {
        this.callbacks.onSectionActivate({
          sectionId,
          sectionKey: sectionId.replace(/^analysis-section-/, ""),
          source: cleanText(options && options.source, "navigation"),
        });
      }
      if (sectionId === "analysis-section-geography") this._requestGeography("section-visible");
      if (sectionId === "analysis-section-spatial") this._requestSpatialEvidence("section-visible");
      if (previousSectionId !== sectionId) {
        if (this.renderPending) this._cancelActiveRenderScope();
        this._renderActiveSectionIfNeeded();
      }
      return true;
    }

    _setActiveSection(sectionId, options) {
      return this.setActiveSection(sectionId, options);
    }

    _replaceHash(sectionId) {
      if (!this.documentView || !this.documentView.location) return;
      const hash = "#" + sectionId;
      if (this.documentView.location.hash === hash) return;
      if (this.documentView.history && typeof this.documentView.history.replaceState === "function") {
        this.documentView.history.replaceState(null, "", hash);
      } else {
        this.documentView.location.hash = hash;
      }
    }

    navigateToSection(sectionId, options) {
      const entry = this.sectionEntries.find(function (candidate) { return candidate.id === sectionId; });
      if (!entry) return false;
      const config = options || {};
      this.setActiveSection(sectionId, { source: cleanText(config.source, "navigation") });
      if (config.updateHash !== false) this._replaceHash(sectionId);
      if (config.focus !== false && entry.link && typeof entry.link.focus === "function") entry.link.focus({ preventScroll: true });
      return true;
    }

    _honorAnalysisHash(options) {
      const hash = cleanText(this.documentView && this.documentView.location && this.documentView.location.hash).replace(/^#/, "");
      if (!hash) return false;
      if (/^analysis-section-/.test(hash)) {
        return this.navigateToSection(hash, Object.assign({ updateHash: false, focus: false }, options || {}));
      }
      if (hash === "analysis-crop-context" || hash === "analysis-animal-context" || hash === "analysis-relationship-context") {
        const activated = this.navigateToSection("analysis-section-context", Object.assign({ updateHash: false, focus: false }, options || {}));
        this.setActiveContextSubview(hash, { focus: false, source: "hash" });
        const target = this.document.getElementById(hash);
        if (target && typeof target.scrollIntoView === "function") {
          target.scrollIntoView({ block: "start", behavior: this._prefersReducedMotion() ? "auto" : "smooth" });
        }
        if (target && options && options.focus && typeof target.focus === "function") target.focus({ preventScroll: true });
        return activated;
      }
      return false;
    }

    refreshSectionNavigation(options) {
      if (options && options.honorHash && this._honorAnalysisHash({ focus: Boolean(options.focus) })) return;
      this._revealActiveSectionLink();
    }

    _requestGeography(origin) {
      if (this.geographyRequested) return false;
      this.geographyRequested = true;
      this.setSectionState("geography", "loading", "Loading country-level geography evidence…");
      if (this.callbacks.onGeographyRequested) {
        this.callbacks.onGeographyRequested({ origin: cleanText(origin, "analysis"), requestedDomains: ["geography"] });
      }
      return true;
    }

    _requestSpatialEvidence(origin) {
      if (this.spatialRequested) return false;
      this.spatialRequested = true;
      this.setSectionState("spatial", "loading", "Loading qualified point-based spatial evidence…");
      if (this.callbacks.onSpatialEvidenceRequested) {
        this.callbacks.onSpatialEvidenceRequested({ origin: cleanText(origin, "analysis"), requestedDomains: ["cooccurrence", "facilities", "cross_domain_readiness"] });
      }
      return true;
    }

    setSectionState(sectionValue, stateValue, messageValue) {
      const section = cleanText(sectionValue).toLowerCase().replace(/^analysis-section-/, "");
      const state = cleanText(stateValue, "ready").toLowerCase();
      if (section !== "spatial" && section !== "geography" && section !== "context") return false;
      const sectionElement = this.document.getElementById("analysis-section-" + section);
      let status = section === "spatial"
        ? this.els.spatialStatus
        : (section === "context" ? this.els.contextStatus : this.els.geographyStatus);
      if (!status && (section === "geography" || section === "context") && sectionElement) {
        status = this._element("p", "analysis-section-status analysis-readiness-summary analysis-" + section + "-status");
        status.setAttribute("id", this.ids[section + "Status"]);
        status.setAttribute("role", "status");
        if (typeof sectionElement.insertBefore === "function") sectionElement.insertBefore(status, sectionElement.firstChild || null);
        else sectionElement.appendChild(status);
        this.els[section + "Status"] = status;
      }
      if (section === "spatial") {
        if (state === "error") this.spatialRequested = false;
        else if (state === "loading" || state === "ready") this.spatialRequested = true;
      } else if (section === "geography") {
        if (state === "error") this.geographyRequested = false;
        else if (state === "loading" || state === "ready") this.geographyRequested = true;
      }
      if (sectionElement) sectionElement.setAttribute("aria-busy", state === "loading" ? "true" : "false");
      if (status) {
        status.setAttribute("data-analysis-state", state);
        status.setAttribute("aria-busy", state === "loading" ? "true" : "false");
        status.classList.toggle("is-error", state === "error");
        status.classList.toggle("is-loading", state === "loading");
        const fallback = section === "spatial"
          ? (state === "error" ? "Spatial evidence could not be loaded. Select Spatial Evidence to retry."
            : (state === "loading" ? "Loading qualified point-based spatial evidence…" : "Spatial evidence artifacts ready."))
          : section === "context"
            ? (state === "error" ? "Context point-neighborhood evidence could not be loaded. Select Context to retry."
              : (state === "loading" ? "Loading crop, animal, and relationship evidence…" : "Context point-neighborhood evidence ready."))
            : (state === "error" ? "Geography evidence could not be loaded. Select Geography to retry."
              : (state === "loading" ? "Loading country-level geography evidence…" : "Country-level geography evidence ready."));
        status.textContent = cleanText(messageValue, fallback);
      }
      return { section, state, message: status ? status.textContent : cleanText(messageValue) };
    }

    setContextLayerState(domain, stateValue) {
      const normalizedDomain = domain === "animals" ? "animals" : "crops";
      const prior = this.contextState[normalizedDomain];
      const state = isObject(stateValue) ? stateValue : { enabled: Boolean(stateValue) };
      const enabled = state.enabled == null ? prior.enabled : Boolean(state.enabled);
      const status = cleanText(state.status, state.busy ? "loading" : "ready").toLowerCase();
      const busy = state.busy === true || status === "loading" || status === "busy";
      const message = cleanText(state.message, busy ? "Updating…" : (enabled ? "Included" : "Excluded"));
      this.contextState[normalizedDomain] = { enabled, status, message, busy };
      const prefix = normalizedDomain === "crops" ? "crop" : "animal";
      const control = this.els[prefix + "Include"];
      const controlStatus = this.els[prefix + "ControlStatus"];
      const content = this.document.getElementById("analysis-" + prefix + "-content");
      const excluded = this.document.getElementById("analysis-" + prefix + "-excluded");
      if (control) {
        control.setAttribute("aria-checked", enabled ? "true" : "false");
        control.setAttribute("aria-busy", busy ? "true" : "false");
        control.disabled = busy;
      }
      if (controlStatus) controlStatus.textContent = message;
      if (content) {
        content.hidden = !enabled;
        setElementInert(content, !enabled);
      }
      if (excluded) {
        excluded.hidden = enabled;
        setElementInert(excluded, enabled);
      }
      return this.contextState[normalizedDomain];
    }

    setContextControlState(domain, stateValue) {
      return this.setContextLayerState(domain, stateValue);
    }

    _requestContextLayerChange(domain) {
      const prior = this.contextState[domain] || { enabled: true };
      const enabled = !prior.enabled;
      this.setContextLayerState(domain, { enabled, busy: true, message: enabled ? "Including and recomputing…" : "Excluding and recomputing…" });
      const request = { domain, enabled, origin: "analysis" };
      if (!this.callbacks.onContextLayerChange) {
        this.setContextLayerState(domain, { enabled, status: "ready" });
        return Promise.resolve(request);
      }
      let response;
      try {
        response = this.callbacks.onContextLayerChange(request);
      } catch (error) {
        response = Promise.reject(error);
      }
      return Promise.resolve(response).then((result) => {
        const next = isObject(result) ? result : { enabled };
        return this.setContextLayerState(domain, Object.assign({ enabled, status: "ready" }, next));
      }).catch((error) => {
        this.setContextLayerState(domain, { enabled: prior.enabled, status: "error", message: "Could not update: " + cleanText(error && error.message, "unknown error") });
        return null;
      });
    }

    _handleContextView(event, domain, targetId) {
      if (event && typeof event.preventDefault === "function") event.preventDefault();
      if (this.callbacks.onContextView) this.callbacks.onContextView({ domain, targetId, origin: "analysis" });
      this.navigateToSection("analysis-section-context", { updateHash: false, focus: false, source: "context-view" });
      this.setActiveContextSubview(targetId, { focus: false, source: "context-view" });
      const target = this.document.getElementById(targetId);
      this._replaceHash(targetId);
      if (target && typeof target.scrollIntoView === "function") {
        target.scrollIntoView({ block: "start", behavior: this._prefersReducedMotion() ? "auto" : "smooth" });
      }
      if (target && typeof target.focus === "function") {
        if (!target.getAttribute("tabindex")) target.setAttribute("tabindex", "-1");
        target.focus({ preventScroll: true });
      }
    }

    _exportEvidence(format) {
      if (!this.latestResult) return null;
      let filterSnapshot = null;
      if (this.callbacks.getFilterSnapshot) {
        try { filterSnapshot = this.callbacks.getFilterSnapshot(); } catch (_error) { filterSnapshot = null; }
      }
      const evidencePackage = buildEvidencePackage(this.latestResult, Object.assign({}, this.latestMeta, { filterSnapshot }));
      const normalizedFormat = format === "csv" ? "csv" : "json";
      const text = normalizedFormat === "csv"
        ? evidencePackageToCsv(evidencePackage)
        : JSON.stringify(evidencePackage, null, 2);
      const exportValue = {
        format: normalizedFormat,
        filename: "ufo-timeline-analysis-evidence." + normalizedFormat,
        mimeType: normalizedFormat === "csv" ? "text/csv;charset=utf-8" : "application/json;charset=utf-8",
        package: evidencePackage,
        text,
      };
      if (this.callbacks.onExportEvidence) {
        this.callbacks.onExportEvidence(Object.assign({ result: this.latestResult }, exportValue));
        return exportValue;
      }
      const view = this.documentView;
      if (!view || typeof view.Blob !== "function" || !view.URL || typeof view.URL.createObjectURL !== "function" || !this.document.body) return exportValue;
      const url = view.URL.createObjectURL(new view.Blob([text], { type: exportValue.mimeType }));
      const anchor = this.document.createElement("a");
      anchor.href = url;
      anchor.download = exportValue.filename;
      this.document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      view.setTimeout(function () { view.URL.revokeObjectURL(url); }, 0);
      return exportValue;
    }

    _handleTabKeydown(event) {
      const supported = ["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Home", "End"];
      if (!event || supported.indexOf(event.key) === -1) return;
      const tabs = [this.els.mapTab, this.els.analysisTab];
      let currentIndex = tabs.indexOf(event.target);
      if (currentIndex === -1) currentIndex = this.activeView === "analysis" ? 1 : 0;
      const disabledIndexes = tabs.reduce(function (indexes, tab, index) {
        if (tab.disabled || tab.getAttribute("aria-disabled") === "true") indexes.push(index);
        return indexes;
      }, []);
      const nextIndex = nextEnabledTabIndex(currentIndex, event.key, disabledIndexes, tabs.length);
      if (nextIndex < 0) return;
      event.preventDefault();
      const nextTab = tabs[nextIndex];
      if (typeof nextTab.focus === "function") nextTab.focus();
      this.setActiveView(nextIndex === 1 ? "analysis" : "map", { source: "keyboard" });
    }

    setAnalysisEnabled(enabled, reason) {
      const nextEnabled = Boolean(enabled);
      this.analysisEnabled = nextEnabled;
      this.els.analysisTab.disabled = !nextEnabled;
      this.els.analysisTab.setAttribute("aria-disabled", nextEnabled ? "false" : "true");
      this.els.analysisTab.title = nextEnabled
        ? "Open statistical analysis for the active filters."
        : cleanText(reason, "Analysis becomes available when the core catalog is ready.");
      this.els.tabStatus.textContent = nextEnabled
        ? "Analysis is ready."
        : cleanText(reason, "Analysis is waiting for the core catalog.");
      if (!nextEnabled && this.activeView === "analysis") {
        this.setActiveView("map", { source: "availability" });
      }
      return this.analysisEnabled;
    }

    setActiveView(view, options) {
      const nextView = normalizeView(view);
      const config = options || {};
      if (nextView === "analysis" && !this.analysisEnabled) return false;
      const previousView = this.activeView;
      const changed = previousView !== nextView;
      if (!changed && !config.force) return true;

      this.activeView = nextView;
      const mapActive = nextView === "map";
      this.els.mapTab.setAttribute("aria-selected", mapActive ? "true" : "false");
      this.els.mapTab.setAttribute("tabindex", mapActive ? "0" : "-1");
      this.els.analysisTab.setAttribute("aria-selected", mapActive ? "false" : "true");
      this.els.analysisTab.setAttribute("tabindex", mapActive ? "-1" : "0");
      if (this.els.mapTab.classList) this.els.mapTab.classList.toggle("is-active", mapActive);
      if (this.els.analysisTab.classList) this.els.analysisTab.classList.toggle("is-active", !mapActive);

      this.els.mapPanel.hidden = !mapActive;
      this.els.analysisPanel.hidden = mapActive;
      setElementInert(this.els.mapPanel, !mapActive);
      setElementInert(this.els.analysisPanel, mapActive);
      if (this.document.documentElement) {
        this.document.documentElement.setAttribute("data-active-primary-view", nextView);
      }
      if (mapActive && this.currentPreview) this.hidePreview({ restoreFocus: false });

      const firstAnalysisActivation = nextView === "analysis" && !this.analysisInitialized;
      if (firstAnalysisActivation) this.analysisInitialized = true;
      if (nextView === "analysis") {
        this.refreshSectionNavigation({ honorHash: true, focus: false });
      }
      if (!config.silent && this.callbacks.onViewChange) {
        this.callbacks.onViewChange({
          activeView: nextView,
          previousView,
          changed,
          firstAnalysisActivation,
          source: cleanText(config.source, "programmatic"),
        });
      }
      return true;
    }

    getActiveView() {
      return this.activeView;
    }

    setBaselineMode(mode, options) {
      const nextMode = normalizeBaselineMode(mode);
      const previousMode = this.baselineMode;
      this.baselineMode = nextMode;
      if (this.currentAnalysisMode !== "whole_corpus_structure") this.els.baseline.value = nextMode;
      if (this.currentAnalysisMode !== "whole_corpus_structure") this.els.baselineNote.textContent = BASELINE_NOTES[nextMode];
      this.els.baselineNote.classList.toggle("is-descriptive-warning", nextMode === "full_catalog");
      if ((!options || options.notify !== false) && nextMode !== previousMode && this.callbacks.onBaselineChange) {
        this.callbacks.onBaselineChange({ baselineMode: nextMode, previousMode });
      }
      return nextMode;
    }

    _setAnalysisModePresentation(modeValue, comparisonStateValue) {
      const mode = cleanText(modeValue, "comparative").toLowerCase();
      const comparisonState = cleanText(comparisonStateValue, mode === "whole_corpus_structure" ? "whole_corpus_structure" : "inferential").toLowerCase();
      const wholeCorpus = mode === "whole_corpus_structure" || comparisonState === "whole_corpus_structure";
      this.currentAnalysisMode = wholeCorpus ? "whole_corpus_structure" : mode;
      this.currentComparisonState = comparisonState;
      const baselineLabel = this.document.getElementById("analysis-baseline-label");
      const activeLabel = this.document.getElementById("analysis-active-count-label");
      const referenceCard = this.document.getElementById("analysis-reference-count-card");
      const timelineTitle = this.document.getElementById("analysis-time-series-title");
      const timelineQuestion = this.document.getElementById("analysis-time-series-question");
      const desktopModeLabel = this.document.getElementById("analysis-mode-label");
      const mobileModeLabel = this.document.getElementById("analysis-date-range-chip-mode");
      const modeLabels = {
        inferential: "Balanced comparison",
        descriptive_overlap: "Descriptive overlap",
        whole_corpus_structure: "Internal structure",
        unavailable_no_reference: "No valid reference",
        unavailable_self_comparison: "Self-comparison unavailable",
      };
      const resolvedModeLabel = wholeCorpus ? modeLabels.whole_corpus_structure : (modeLabels[comparisonState] || "Analysis comparison");
      [desktopModeLabel, mobileModeLabel].forEach(function (element) {
        if (!element) return;
        element.textContent = resolvedModeLabel;
        element.setAttribute("data-comparison-state", comparisonState);
      });
      this.els.baseline.disabled = wholeCorpus;
      this.els.baseline.setAttribute("aria-disabled", wholeCorpus ? "true" : "false");
      this.els.baseline.value = wholeCorpus ? "whole_corpus_structure" : this.baselineMode;
      if (baselineLabel) baselineLabel.textContent = wholeCorpus ? "Analysis mode" : "Reference baseline";
      if (activeLabel) activeLabel.textContent = wholeCorpus ? "Reports" : "Active reports";
      if (referenceCard) referenceCard.hidden = wholeCorpus;
      if (timelineTitle) timelineTitle.textContent = wholeCorpus ? "Reporting activity across all records" : "Adaptive balanced timeline";
      if (timelineQuestion) timelineQuestion.textContent = wholeCorpus
        ? "How does reporting activity change chronologically across the matched corpus?"
        : "Does the cohort depart from its balanced reference through time?";
      this.els.baselineNote.classList.toggle("is-descriptive-warning", !wholeCorpus && this.baselineMode === "full_catalog");
      this.els.baselineNote.classList.toggle("is-internal-structure", wholeCorpus);
      this.els.baselineNote.textContent = wholeCorpus
        ? "All records — internal structure. Charts compare observed patterns with conditional expectations; no duplicate or fabricated reference cohort is drawn."
        : BASELINE_NOTES[this.baselineMode];
      return { analysisMode: this.currentAnalysisMode, comparisonState: this.currentComparisonState };
    }

    _applyAnalysisState(nextState, message) {
      this.analysisState = nextState;
      const cards = [this.els.loading, this.els.empty, this.els.error];
      const stateCard = nextState === "loading"
        ? this.els.loading
        : (nextState === "empty" ? this.els.empty : (nextState === "error" ? this.els.error : null));
      cards.forEach(function (card) { card.hidden = card !== stateCard; });
      this.els.stateRegion.hidden = nextState === "ready";
      this.els.content.hidden = nextState !== "ready";
      setElementInert(this.els.content, nextState !== "ready");
      if (message) {
        const target = nextState === "loading"
          ? this.els.loadingMessage
          : (nextState === "empty" ? this.els.emptyMessage : this.els.errorMessage);
        if (target) target.textContent = cleanText(message);
      }
      return nextState;
    }

    setAnalysisState(state, message) {
      const nextState = normalizeAnalysisState(state);
      if (this.renderPending && (nextState === "ready" || nextState === "empty")) {
        this.renderCompletionState = nextState;
        this.renderCompletionMessage = cleanText(message);
        return nextState;
      }
      if (this.renderPending && nextState === "error") {
        this._cancelRenderSequence();
      }
      return this._applyAnalysisState(nextState, message);
    }

    setComputationPhase(phaseValue, messageValue) {
      const phase = cleanText(phaseValue, "idle").toLowerCase();
      const status = this.els.computationStatus;
      if (!status) return phase;
      const hidden = phase === "idle" || phase === "ready";
      status.hidden = hidden;
      status.setAttribute("data-phase", phase);
      status.textContent = hidden ? "" : cleanText(messageValue, "Analysis computation is continuing off the main thread.");
      if (this.els.content) this.els.content.setAttribute("aria-busy", hidden ? "false" : "true");
      return phase;
    }

    _cancelRenderSequence() {
      if (this.renderFrameId != null && this.cancelRenderFrame) {
        this.cancelRenderFrame(this.renderFrameId);
      }
      this.renderFrameId = null;
      this.renderPending = false;
      this.renderCompletionState = null;
      this.renderCompletionMessage = "";
      this.renderGeneration += 1;
      if (this.els.content) this.els.content.setAttribute("aria-busy", "false");
    }

    _completeRenderSequence(generation, fallbackState) {
      if (generation !== this.renderGeneration) return false;
      this.renderFrameId = null;
      this.renderPending = false;
      const finalState = this.renderCompletionState || fallbackState;
      const finalMessage = this.renderCompletionMessage;
      this.renderCompletionState = null;
      this.renderCompletionMessage = "";
      this._enforceDeferredRenderIsolation(this.resultRenderVersion);
      this.activeRenderPlanKeys = [];
      this.activeRenderTargetIds = [];
      if (this.els.content) this.els.content.setAttribute("aria-busy", "false");
      this._applyAnalysisState(finalState, finalMessage);
      if (this.callbacks.onRenderComplete) {
        this.callbacks.onRenderComplete({
          generation,
          state: finalState,
          activeSectionId: this.activeSectionId,
          activeContextSubviewId: this.activeContextSubviewId,
        });
      }
      if (finalState === "ready" || finalState === "empty") {
        // The content is hidden while batched chart jobs run. Reapply the
        // requested hash only after it is visible and has final dimensions.
        const realign = () => {
          if (generation !== this.renderGeneration) return;
          this.refreshSectionNavigation({ honorHash: true, focus: false });
        };
        if (this.requestRenderFrame) {
          this.requestRenderFrame(() => this.requestRenderFrame(realign));
        } else {
          realign();
        }
      }
      return true;
    }

    _clearRenderTargets(targetIds) {
      asArray(targetIds).forEach((targetId) => {
        const target = this.document.getElementById(targetId);
        if (target) this._clear(target);
      });
    }

    _enforceDeferredRenderIsolation(versionValue) {
      if (!this.renderPlans.size) return [];
      const version = Number(versionValue == null ? this.resultRenderVersion : versionValue);
      const currentlyActiveKeys = new Set(this._activeRenderKeys());
      const activeKeys = new Set(this.activeRenderPlanKeys.filter(function (key) {
        return currentlyActiveKeys.has(key);
      }));
      const clearedTargetIds = [];
      this.renderPlans.forEach((plan, key) => {
        const renderedForVersion = this.renderedPlanVersions.get(key) === version;
        if (renderedForVersion || activeKeys.has(key)) return;
        asArray(plan && plan.targets).forEach((targetId) => {
          const target = this.document.getElementById(targetId);
          if (!target || !target.children || !target.children.length) return;
          this._clear(target);
          clearedTargetIds.push(targetId);
        });
      });
      return clearedTargetIds;
    }

    _cancelActiveRenderScope() {
      if (!this.renderPending) return false;
      const targetIds = this.activeRenderTargetIds.slice();
      const planKeys = this.activeRenderPlanKeys.slice();
      this._cancelRenderSequence();
      this._clearRenderTargets(targetIds);
      planKeys.forEach((key) => this.renderedPlanVersions.delete(key));
      this.activeRenderPlanKeys = [];
      this.activeRenderTargetIds = [];
      return true;
    }

    _activeRenderKeys() {
      if (this.activeSectionId !== "analysis-section-context") return [this.activeSectionId];
      return [this.activeContextSubviewId, "analysis-section-context"];
    }

    _renderActiveSectionIfNeeded() {
      if (!this.latestResult || !this.renderPlans.size) return false;
      const version = this.resultRenderVersion;
      // A dashboard owns chart DOM only after its plan has completed for the
      // current result. This fail-closed sweep prevents a stale frame or
      // extension callback from materializing a dashboard the user has never
      // opened, while preserving completed dashboards as warm in-session DOM.
      this._enforceDeferredRenderIsolation(version);
      const planKeys = this._activeRenderKeys().filter((key) => {
        return this.renderPlans.has(key) && this.renderedPlanVersions.get(key) !== version;
      });
      if (!planKeys.length) return false;
      if (this.renderPending) this._cancelActiveRenderScope();
      const jobs = [];
      const targetIds = [];
      const rawJobs = [];
      planKeys.forEach((key) => {
        const plan = this.renderPlans.get(key);
        rawJobs.push.apply(rawJobs, asArray(plan && plan.jobs));
        targetIds.push.apply(targetIds, asArray(plan && plan.targets));
      });
      const ownsActiveScope = () => {
        if (version !== this.resultRenderVersion) return false;
        const currentKeys = new Set(this._activeRenderKeys());
        return planKeys.every(function (key) { return currentKeys.has(key); });
      };
      rawJobs.forEach(function (job) {
        jobs.push(function () {
          if (ownsActiveScope()) job();
        });
      });
      jobs.push(() => {
        if (!ownsActiveScope()) return;
        planKeys.forEach((key) => this.renderedPlanVersions.set(key, version));
      });
      this.activeRenderPlanKeys = planKeys.slice();
      this.activeRenderTargetIds = Array.from(new Set(targetIds));
      return this._runRenderJobs(jobs, this.renderFinalState);
    }

    _runRenderJobs(jobs, finalState) {
      if (this.renderFrameId != null && this.cancelRenderFrame) {
        this.cancelRenderFrame(this.renderFrameId);
      }
      const generation = this.renderGeneration + 1;
      this.renderGeneration = generation;
      this.renderFrameId = null;
      this.renderCompletionState = finalState;
      this.renderCompletionMessage = "";
      const pendingJobs = asArray(jobs).slice();
      const preserveVisibleContent = this.analysisState === "ready" && !this.els.content.hidden;
      if (preserveVisibleContent) {
        this.els.content.setAttribute("aria-busy", "true");
      } else {
        this._applyAnalysisState(
          "loading",
          this.analysisInitialized ? "Rendering analysis charts in small batches..." : "Preparing analysis charts..."
        );
      }

      if (!this.requestRenderFrame || !pendingJobs.length) {
        this.renderPending = false;
        try {
          pendingJobs.forEach(function (job) { job(); });
        } catch (error) {
          this.renderCompletionState = null;
          this._applyAnalysisState("error", cleanText(error && error.message, "Analysis charts could not be rendered."));
          throw error;
        }
        this._completeRenderSequence(generation, finalState);
        return false;
      }

      this.renderPending = true;
      let jobIndex = 0;
      const runNext = () => {
        if (generation !== this.renderGeneration || !this.renderPending) return;
        this.renderFrameId = null;
        try {
          pendingJobs[jobIndex]();
        } catch (error) {
          this.renderPending = false;
          this.renderCompletionState = null;
          this.renderCompletionMessage = "";
          this._applyAnalysisState("error", cleanText(error && error.message, "Analysis charts could not be rendered."));
          return;
        }
        jobIndex += 1;
        if (jobIndex >= pendingJobs.length) {
          this._completeRenderSequence(generation, finalState);
          return;
        }
        this.renderFrameId = this.requestRenderFrame(runNext);
      };
      this.renderFrameId = this.requestRenderFrame(runNext);
      return true;
    }

    updateCohortSummary(summary) {
      const normalized = normalizeSummary(summary);
      const values = {
        activeCount: formatCount(normalized.activeCount),
        referenceCount: formatCount(normalized.referenceCount),
        mappedCount: formatCount(normalized.mappedCount),
        unmappedCount: formatCount(normalized.unmappedCount),
        missingCount: formatCount(normalized.missingCount),
        unitLabel: normalized.unitLabel,
        sourceMixLabel: normalized.sourceMixLabel,
        datePrecisionLabel: normalized.datePrecisionLabel,
        locationPrecisionLabel: normalized.locationPrecisionLabel,
        datasetHash: normalized.datasetHash,
        policyWarning: normalized.policyWarning || "Generalized coordinates remain separated from exact source coordinates. Chronology connectors never enter travel or proximity statistics.",
      };
      Object.keys(SUMMARY_IDS).forEach((key) => {
        const element = this.document.getElementById(SUMMARY_IDS[key]);
        if (element) element.textContent = values[key];
      });
      return normalized;
    }

    _commonChartMeta(summary) {
      const metadata = [
        "Unit: " + summary.unitLabel,
        "Active n=" + formatCount(summary.activeCount),
        "Reference n=" + formatCount(summary.referenceCount),
        "Missing=" + formatCount(summary.missingCount),
        "Source mix: " + summary.sourceMixLabel,
        "Date precision: " + summary.datePrecisionLabel,
        "Location precision: " + summary.locationPrecisionLabel,
      ];
      if (summary.policyWarning) metadata.push("Policy: " + summary.policyWarning);
      return metadata.join(" · ");
    }

    _element(tagName, className, text) {
      const element = this.document.createElement(tagName);
      if (className) element.className = className;
      if (text != null) element.textContent = String(text);
      return element;
    }

    _svgElement(tagName, attributes) {
      const element = this.document.createElementNS(SVG_NS, tagName);
      Object.keys(attributes || {}).forEach(function (key) {
        element.setAttribute(key, String(attributes[key]));
      });
      return element;
    }

    _clear(element) {
      if (!element) return;
      if (typeof element.replaceChildren === "function") {
        element.replaceChildren();
        return;
      }
      while (element.firstChild) element.removeChild(element.firstChild);
    }

    _prepareChart(chartId, items, summary, emptyMessage) {
      const container = this.document.getElementById(chartId);
      if (!container) return null;
      this._clear(container);
      if (!items.length) {
        container.appendChild(this._element("p", "analysis-chart-empty", emptyMessage || "No values are available for this cohort."));
        return null;
      }
      return container;
    }

    _appendDataTable(container, caption, columns, rows) {
      const details = this._element("details", "analysis-data-details");
      details.appendChild(this._element("summary", "", "View data table"));
      const scroll = this._element("div", "analysis-data-table-scroll");
      const table = this._element("table", "analysis-data-table");
      const tableCaption = this._element("caption", "sr-only", caption);
      table.appendChild(tableCaption);
      const head = this._element("thead");
      const headRow = this._element("tr");
      columns.forEach((column) => headRow.appendChild(this._element("th", "", column)));
      head.appendChild(headRow);
      table.appendChild(head);
      const body = this._element("tbody");
      rows.forEach((row) => {
        const tableRow = this._element("tr");
        columns.forEach((column, index) => {
          tableRow.appendChild(this._element(index === 0 ? "th" : "td", "", row[index] == null ? "—" : row[index]));
        });
        body.appendChild(tableRow);
      });
      table.appendChild(body);
      scroll.appendChild(table);
      details.appendChild(scroll);
      container.appendChild(details);
    }

    _appendLazyDataTable(container, caption, columns, rows) {
      const details = this._element("details", "analysis-data-details analysis-data-details-lazy");
      details.appendChild(this._element("summary", "", "View complete data table (" + formatCount(rows.length) + " rows)"));
      const placeholder = this._element("p", "analysis-chart-meta", "The complete accessible table is built only when opened to protect interaction performance.");
      details.appendChild(placeholder);
      let rendered = false;
      const render = () => {
        if (rendered || !details.open) return;
        rendered = true;
        if (placeholder.parentNode) details.removeChild(placeholder);
        const scroll = this._element("div", "analysis-data-table-scroll");
        const table = this._element("table", "analysis-data-table");
        table.appendChild(this._element("caption", "sr-only", caption));
        const head = this._element("thead");
        const headRow = this._element("tr");
        columns.forEach((column) => headRow.appendChild(this._element("th", "", column)));
        head.appendChild(headRow);
        table.appendChild(head);
        const body = this._element("tbody");
        rows.forEach((row) => {
          const tableRow = this._element("tr");
          columns.forEach((column, index) => {
            tableRow.appendChild(this._element(index === 0 ? "th" : "td", "", row[index] == null ? "—" : row[index]));
          });
          body.appendChild(tableRow);
        });
        table.appendChild(body);
        scroll.appendChild(table);
        details.appendChild(scroll);
      };
      details.addEventListener("toggle", render);
      container.appendChild(details);
    }

    _appendChartPolicy(chartId, policyText) {
      const container = this.document.getElementById(chartId);
      const policy = cleanText(policyText);
      if (!container || !policy) return;
      container.appendChild(this._element("p", "analysis-chart-policy", policy));
    }

    _activatePreview(element, item, label, summary, defaultKind) {
      if (!datumHasPreview(item)) return false;
      element.classList.add("is-selectable");
      if (element.tagName && element.tagName.toLowerCase() !== "button") {
        element.setAttribute("role", "button");
        element.setAttribute("tabindex", "0");
      }
      const openPreview = () => {
        const preview = previewForDatum(item, label, summary, defaultKind);
        if (preview) this.showPreview(preview);
      };
      element.addEventListener("click", openPreview);
      element.addEventListener("keydown", (event) => {
        if (event.key !== "Enter" && event.key !== " ") return;
        event.preventDefault();
        openPreview();
      });
      return true;
    }

    _activateEvidenceInspection(element, item, label, summary, options) {
      const config = options || {};
      if (datumHasPreview(item)) return this._activatePreview(element, item, label, summary, config.defaultKind);
      if (!estimateAvailable(item, config.valueKeys)) return false;
      element.classList.add("is-selectable", "is-evidence-inspection");
      if (element.tagName && element.tagName.toLowerCase() !== "button") {
        element.setAttribute("role", "button");
        element.setAttribute("tabindex", "0");
      }
      const open = () => {
        const observed = firstDefined(item, ["activeCount", "active_count", "observedCount", "observed_count", "observedClusterCount", "observed_cluster_count", "observed", "count"], null);
        const expected = firstDefined(item, ["referenceCount", "reference_count", "expectedCount", "expected_count", "expectedClusterCount", "expected_cluster_count", "reference", "expected"], null);
        const effect = comparativeEffect(item, config.valueKeys);
        const interval = intervalBounds(item);
        const pValue = firstDefined(item, ["pValue", "p_value", "p"], null);
        const qValue = firstDefined(item, ["qValue", "q_value", "q"], null);
        const support = firstDefined(item, ["commonSupportRate", "common_support_rate", "supportRate", "support_rate", "supportedN", "supported_n"], null);
        const criteria = [
          { label: cleanText(config.effectLabel, "Effect"), value: (config.valueFormat === "percent" ? formatSignedPercent(effect) : formatDecimal(effect, 3)) },
          interval ? { label: "95% interval", value: formatInterval(interval) } : null,
          pValue == null ? null : { label: "p-value", value: formatDecimal(pValue, 4) },
          qValue == null ? null : { label: "q-value", value: formatDecimal(qValue, 4) },
          support == null ? null : { label: "Support", value: Number(support) <= 1 ? formatPercent(support) : formatCount(support) },
          suppressionReason(item) ? { label: "Reliability", value: suppressionReason(item) } : null,
        ].filter(Boolean);
        this.showPreview({
          readOnly: true,
          kind: "filter",
          title: label,
          summary: "Evidence details for this chart cell. This inspection does not change shared filters.",
          cohortSize: observed,
          missingness: firstDefined(item, ["missingness", "missingRate", "missing_rate"], "See evidence package"),
          comparison: "Observed n=" + formatCount(observed) + (expected == null ? "" : " · conditional expected n=" + formatCount(expected)),
          criteria,
        });
      };
      element.addEventListener("click", open);
      element.addEventListener("keydown", function (event) {
        if (event.key !== "Enter" && event.key !== " ") return;
        event.preventDefault();
        open();
      });
      return true;
    }

    _renderForestPlot(chartId, items, summary, options) {
      const config = options || {};
      const ratioScale = config.scale === "ratio" || finiteNumber(config.nullValue, 0) === 1;
      const ranked = asArray(items).filter(isObject).slice();
      if (config.rankByEvidence) {
        ranked.sort(function (left, right) {
          return conservativeEffectMagnitude(right, config.valueKeys, config.nullValue)
            - conservativeEffectMagnitude(left, config.valueKeys, config.nullValue)
            || datumLabel(left, 0).localeCompare(datumLabel(right, 0));
        });
      }
      const data = ranked.slice(0, config.limit || 24);
      const container = this._prepareChart(chartId, data, summary, config.emptyMessage || "No qualified adjusted effects are available for this cohort.");
      if (!container) return;
      const transform = function (value) {
        const numeric = finiteNumber(value, ratioScale ? 1 : 0);
        return ratioScale ? Math.log2(Math.max(Number.EPSILON, numeric)) : numeric;
      };
      const values = [];
      data.forEach(function (item) {
        const effect = comparativeEffect(item, config.valueKeys);
        const interval = intervalBounds(item, { ratioScale });
        values.push(Math.abs(transform(effect)));
        if (interval) values.push(Math.abs(transform(interval.lower)), Math.abs(transform(interval.upper)));
      });
      const extent = Math.max(0.01, ...values);
      const position = function (value) {
        return Math.max(0, Math.min(100, 50 + ((transform(value) / (extent * 2)) * 100)));
      };
      const legend = this._element("p", "analysis-forest-legend", config.compact
        ? "Point = effect · line = 95% interval · center = none · hatch = limited support"
        : "Point = adjusted effect · line = 95% interval · center = no difference · diagonal overlay = descriptive estimate with limited support");
      container.appendChild(legend);
      const qualifiedCount = data.filter(inferenceEligible).length;
      container.appendChild(this._element("p", "analysis-qualification-summary" + (qualifiedCount ? "" : " is-descriptive-only"), qualifiedCount
        ? formatCount(qualifiedCount) + " inferentially qualified effects · " + formatCount(data.length - qualifiedCount) + " descriptive effects"
        : "No effects qualify for inference in this view. Descriptive estimates remain visible."));
      const list = this._element("div", "analysis-forest-list" + (config.compact ? " analysis-signal-spectrum" : ""));
      const tableRows = [];
      data.forEach((item, index) => {
        const label = datumLabel(item, index);
        const effect = comparativeEffect(item, config.valueKeys);
        const interval = intervalBounds(item, { ratioScale });
        const plotInterval = interval || { lower: effect, upper: effect };
        const itemSuppression = suppressionReason(item);
        const selectable = estimateAvailable(item, config.valueKeys) && datumHasPreview(item);
        const row = this._element(selectable ? "button" : "div", "analysis-forest-row" + (config.compact ? " analysis-signal-spectrum-row" : ""));
        if (selectable) row.type = "button";
        if (itemSuppression) row.classList.add("is-low-support");
        if (transform(effect) < 0) row.classList.add("is-negative");
        row.appendChild(this._element("span", "analysis-forest-label", label));
        const track = this._element("span", "analysis-forest-track");
        const intervalMark = this._element("span", "analysis-forest-interval");
        const lower = plotInterval.lower;
        const upper = plotInterval.upper;
        intervalMark.style.setProperty("--analysis-ci-left", position(lower).toFixed(2) + "%");
        intervalMark.style.setProperty("--analysis-ci-width", Math.max(0.8, position(upper) - position(lower)).toFixed(2) + "%");
        const point = this._element("span", "analysis-forest-point");
        point.style.setProperty("--analysis-point-left", position(effect).toFixed(2) + "%");
        if (interval) track.appendChild(intervalMark);
        track.appendChild(point);
        row.appendChild(track);
        const qValue = firstDefined(item, ["qValue", "q_value", "q"], null);
        const primaryCount = firstDefined(item, asArray(config.primaryCountKeys), null);
        const comparisonCount = firstDefined(item, asArray(config.comparisonCountKeys), null);
        const countText = primaryCount == null && comparisonCount == null ? "" : cleanText(config.primaryCountLabel, "Observed") + " n=" + formatCount(primaryCount)
          + " · " + cleanText(config.comparisonCountLabel, "Expected") + " n=" + formatCount(comparisonCount);
        const intervalLabel = interval
          ? (ratioScale ? formatInterval(interval) : formatPercentInterval(interval))
          : "unavailable";
        const valueLabel = (ratioScale ? cleanText(config.effectLabel, "Odds ratio") + " " + formatDecimal(effect, 3) : formatSignedPercent(effect))
          + " · 95% CI " + intervalLabel
          + (qValue == null ? "" : " · q=" + formatDecimal(qValue, 3));
        const faceValueLabel = config.compact
          ? (ratioScale
            ? formatDecimal(effect, 2) + " · " + intervalLabel
            : formatSignedPercent(effect) + " · " + intervalLabel)
          : valueLabel;
        row.appendChild(this._element("span", "analysis-forest-value", faceValueLabel));
        if (countText) row.appendChild(this._element("span", "analysis-forest-counts", countText));
        if (itemSuppression) {
          row.appendChild(this._element("span", "analysis-forest-status", "Descriptive estimate · " + itemSuppression));
        }
        row.setAttribute("aria-label", label + ": " + (countText ? countText + ". " : "") + valueLabel + (itemSuppression ? ". Descriptive estimate: " + itemSuppression + "." : (selectable ? ". Preview this selection." : "")));
        if (config.compact) row.setAttribute("title", valueLabel);
        if (selectable) this._activatePreview(row, item, label, summary, config.defaultKind);
        list.appendChild(row);
        const tableRow = [
          label,
          ratioScale ? formatDecimal(effect, 3) : formatSignedPercent(effect),
          interval ? (ratioScale ? formatInterval(interval) : formatPercentInterval(interval)) : "—",
          qValue == null ? "—" : formatDecimal(qValue, 3),
          inferenceEligible(item) ? "Inferentially qualified" : (suppressionReason(item) ? "Descriptive · " + suppressionReason(item) : "Descriptive"),
        ];
        if (countText) tableRow.push(formatCount(primaryCount), formatCount(comparisonCount));
        tableRows.push(tableRow);
      });
      container.appendChild(list);
      const tableHeadings = ["Category", "Adjusted effect", "95% interval", "q-value", "Status"];
      if (tableRows.some(function (row) { return row.length > tableHeadings.length; })) {
        tableHeadings.push(cleanText(config.primaryCountLabel, "Observed") + " n", cleanText(config.comparisonCountLabel, "Expected") + " n");
      }
      this._appendDataTable(container, config.caption || "Adjusted effects and uncertainty", tableHeadings, tableRows);
    }

    _renderEligibilityFunnel(chartId, items, summary, options) {
      const config = options || {};
      const stages = asArray(items).filter(isObject).slice(0, config.limit || 8);
      const container = this._prepareChart(chartId, stages, summary, config.emptyMessage || "Eligibility stages are unavailable for this cohort.");
      if (!container) return;
      const firstInput = firstDefined(stages[0], ["inputN", "input_n", "totalN", "total_n", "count", "passedN", "passed_n"], summary.activeCount);
      const denominator = Math.max(1, finiteNumber(firstInput, summary.activeCount || 1));
      const list = this._element("ol", "analysis-eligibility-funnel");
      list.setAttribute("aria-label", config.caption || "Analysis eligibility funnel");
      const rows = [];
      let previous = denominator;
      stages.forEach((stage, index) => {
        const label = datumLabel(stage, index);
        const inputN = firstDefined(stage, ["inputN", "input_n"], previous);
        const passedN = firstDefined(stage, ["passedN", "passed_n", "eligibleN", "eligible_n", "count", "value"], inputN);
        const failedN = firstDefined(stage, ["failedN", "failed_n", "excludedN", "excluded_n"], inputN == null || passedN == null ? null : Math.max(0, Number(inputN) - Number(passedN)));
        const retention = Number(inputN) > 0 ? Number(passedN) / Number(inputN) : 0;
        const overall = Math.max(0, Number(passedN) || 0) / denominator;
        const item = this._element("li", "analysis-eligibility-stage");
        item.style.setProperty("--analysis-funnel-width", Math.max(4, overall * 100).toFixed(2) + "%");
        item.appendChild(this._element("span", "analysis-eligibility-stage-label", label));
        item.appendChild(this._element("strong", "analysis-eligibility-stage-count", formatCount(passedN)));
        item.appendChild(this._element("span", "analysis-eligibility-stage-retention", index === 0 ? "Starting pool" : formatPercent(retention) + " retained"));
        const criteria = cleanText(firstDefined(stage, ["criteria", "policy", "description", "reason"], ""));
        item.setAttribute("aria-label", label + ": " + formatCount(passedN) + " eligible from " + formatCount(inputN)
          + (failedN == null ? "" : "; " + formatCount(failedN) + " excluded") + (criteria ? ". " + criteria : ""));
        item.setAttribute("title", criteria || (formatCount(failedN) + " excluded at this stage"));
        list.appendChild(item);
        rows.push([label, formatCount(inputN), formatCount(passedN), failedN == null ? "—" : formatCount(failedN), formatPercent(retention), criteria || "—"]);
        previous = Number(passedN) || 0;
      });
      container.appendChild(list);
      this._appendDataTable(container, config.caption || "Eligibility funnel", ["Stage", "Input n", "Eligible n", "Excluded n", "Retention", "Policy"], rows);
    }

    _renderCraftMosaic(chartId, items, summary, options) {
      const config = options || {};
      const craftCount = function (item) {
        const explicit = firstDefined(item, ["count", "observedCount", "observed_count", "activeCount", "active_count", "observed", "reportCount", "report_count"], null);
        return Math.max(0, explicit == null ? datumValue(item, config.valueKeys) : finiteNumber(explicit, 0));
      };
      const ranked = asArray(items).filter(isObject).slice().sort(function (left, right) {
        return craftCount(right) - craftCount(left)
          || datumLabel(left, 0).localeCompare(datumLabel(right, 0));
      });
      const limit = Math.max(2, config.limit || 12);
      let display = ranked.slice(0, limit);
      if (ranked.length > limit) {
        const remaining = ranked.slice(limit - 1);
        display = ranked.slice(0, limit - 1).concat([{
          label: "Remaining categories",
          count: remaining.reduce(function (sum, item) { return sum + craftCount(item); }, 0),
          aggregatedCategoryCount: remaining.length,
          aggregateOnly: true,
        }]);
      }
      const container = this._prepareChart(chartId, display, summary, config.emptyMessage || "No craft categories are available for this cohort.");
      if (!container) return;
      const total = Math.max(1, ranked.reduce(function (sum, item) { return sum + craftCount(item); }, 0));
      const mosaic = this._element("div", "analysis-craft-mosaic");
      mosaic.setAttribute("role", "group");
      mosaic.setAttribute("aria-label", "Craft mosaic; tile area encodes report share and color encodes "
        + (this.currentAnalysisMode === "whole_corpus_structure" ? "whole-corpus share intensity" : "adjusted difference"));
      const layout = proportionalTreemap(display.map(function (item) {
        return { item, weight: craftCount(item) };
      }));
      const effects = display.map(function (item) {
        return finiteNumber(firstDefined(item, ["adjustedDifference", "adjusted_difference", "difference", "shareDifference", "share_difference", "effect"], 0), 0);
      });
      const maximumEffect = Math.max(Number.EPSILON, ...effects.map(Math.abs));
      const maximumShare = Math.max(Number.EPSILON, ...display.map(function (item) { return craftCount(item) / total; }));
      layout.forEach((rectangle, index) => {
        const item = rectangle.item.item;
        const rawLabel = datumLabel(item, index);
        const label = craftDisplayLabel(rawLabel);
        const count = craftCount(item);
        const share = count / total;
        const effect = firstDefined(item, ["adjustedDifference", "adjusted_difference", "difference", "shareDifference", "share_difference", "effect"], null);
        const interval = intervalBounds(item);
        const selectable = !item.aggregateOnly && datumHasPreview(item);
        const tile = this._element(selectable ? "button" : "div", "analysis-craft-mosaic-tile");
        if (selectable) tile.type = "button";
        tile.style.left = rectangle.x.toFixed(4) + "%";
        tile.style.top = rectangle.y.toFixed(4) + "%";
        tile.style.width = rectangle.width.toFixed(4) + "%";
        tile.style.height = rectangle.height.toFixed(4) + "%";
        tile.style.setProperty("--analysis-mosaic-area-share", share.toFixed(8));
        if (rectangle.width < 18 || rectangle.height < 22 || share < 0.025) tile.classList.add("is-compact");
        if (this.currentAnalysisMode === "whole_corpus_structure") {
          const intensity = Math.round(14 + (74 * Math.sqrt(share / maximumShare)));
          tile.style.setProperty("--analysis-mosaic-fill", "color-mix(in srgb, var(--accent) " + intensity + "%, var(--surface-muted))");
          tile.classList.add("is-whole-corpus");
        } else {
          const numericEffect = finiteNumber(effect, 0);
          const intensity = Math.round(13 + (72 * Math.abs(numericEffect) / maximumEffect));
          tile.style.setProperty("--analysis-mosaic-fill", numericEffect < 0
            ? "color-mix(in srgb, var(--warn-text) " + intensity + "%, var(--surface-muted))"
            : "color-mix(in srgb, var(--accent) " + intensity + "%, var(--surface-muted))");
          tile.classList.add(numericEffect < 0 ? "is-negative" : (numericEffect > 0 ? "is-positive" : "is-neutral"));
        }
        tile.appendChild(this._element("strong", "analysis-craft-mosaic-label", label));
        tile.appendChild(this._element("span", "analysis-craft-mosaic-count", formatPercent(share)));
        if (effect != null && this.currentAnalysisMode !== "whole_corpus_structure") tile.appendChild(this._element("span", "analysis-craft-mosaic-effect", formatSignedPercent(effect)));
        const accessible = label + ": " + formatCount(count) + " reports, " + formatPercent(share) + " of matched craft reports; tile area " + formatPercent(rectangle.areaShare)
          + (this.currentAnalysisMode === "whole_corpus_structure" ? "; color shows report-share intensity" : (effect == null ? "" : "; adjusted effect " + formatSignedPercent(effect)))
          + (interval ? "; 95% interval " + formatPercentInterval(interval) : "");
        tile.setAttribute("aria-label", accessible + (selectable ? ". Preview this craft selection." : ""));
        tile.setAttribute("title", accessible);
        if (selectable) this._activatePreview(tile, item, label, summary, config.defaultKind || "filter");
        mosaic.appendChild(tile);
      });
      container.appendChild(mosaic);
      container.appendChild(this._element("p", "analysis-chart-summary analysis-mosaic-encoding", "Area = report share. "
        + (this.currentAnalysisMode === "whole_corpus_structure"
          ? "Darker teal = larger whole-corpus share."
          : "Teal = above the balanced expectation; amber = below it.")));
      this._appendDataTable(container, config.caption || "Craft category mosaic", ["Craft", "Reports", "Share", "Adjusted effect", "95% interval"], ranked.map(function (item, index) {
        const count = craftCount(item);
        const effect = firstDefined(item, ["adjustedDifference", "adjusted_difference", "difference", "shareDifference", "share_difference", "effect"], null);
        return [craftDisplayLabel(datumLabel(item, index)), formatCount(count), formatPercent(count / total), effect == null ? "—" : formatSignedPercent(effect), intervalBounds(item) ? formatPercentInterval(intervalBounds(item)) : "—"];
      }));
    }

    _renderBars(chartId, items, summary, options) {
      const config = options || {};
      const hideReference = config.hideReference === true || this.currentAnalysisMode === "whole_corpus_structure";
      const data = asArray(items).slice(0, config.limit || 40);
      const container = this._prepareChart(chartId, data, summary, config.emptyMessage);
      if (!container) return;
      const magnitudes = data.map(function (item) {
        return Math.max(Math.abs(datumValue(item, config.valueKeys)), hideReference ? 0 : Math.abs(datumReference(item, config.referenceKeys) || 0));
      });
      const maximum = config.scaleActual ? positiveSeriesMaximum(magnitudes) : Math.max(1, ...magnitudes);
      const includeReference = !hideReference && data.some(function (item) { return datumReference(item, config.referenceKeys) != null; });
      const hasIntervals = data.some(function (item) {
        return firstDefined(item, ["interval", "confidenceInterval", "intervalLabel"], null) != null;
      });
      const list = this._element("ol", "analysis-bar-list");
      const rows = [];
      data.forEach((item, index) => {
        const label = datumLabel(item, index);
        const value = datumValue(item, config.valueKeys);
        const reference = hideReference ? null : datumReference(item, config.referenceKeys);
        const listItem = this._element("li", "analysis-bar-item");
        const selectable = datumHasPreview(item);
        const row = this._element(selectable ? "button" : "div", "analysis-bar-row");
        if (selectable) row.type = "button";
        const labelElement = this._element("span", "analysis-bar-label", label);
        const tracks = this._element("span", "analysis-bar-tracks");
        const activeTrack = this._element("span", "analysis-bar-track");
        const activeFill = this._element("span", "analysis-bar-fill");
        if (value < 0) {
          row.classList.add("is-negative");
          activeFill.classList.add("is-negative");
        }
        activeFill.style.width = Math.max(value ? 1 : 0, (Math.abs(value) / maximum) * 100) + "%";
        activeTrack.appendChild(activeFill);
        tracks.appendChild(activeTrack);
        if (reference != null) {
          const referenceTrack = this._element("span", "analysis-bar-track analysis-bar-track-reference");
          const referenceFill = this._element("span", "analysis-bar-fill analysis-bar-fill-reference");
          referenceFill.style.width = Math.max(reference ? 1 : 0, (Math.abs(reference) / maximum) * 100) + "%";
          referenceTrack.appendChild(referenceFill);
          tracks.appendChild(referenceTrack);
        }
        const formatValue = config.signedPercent
          ? formatSignedPercent
          : (config.valueFormat === "percent" ? formatPercent : function (number) { return formatDecimal(number, 2); });
        const valueText = reference == null
          ? formatValue(value)
          : formatValue(value) + " / " + formatValue(reference);
        const intervalValue = firstDefined(item, ["interval", "confidenceInterval", "intervalLabel"], null);
        const intervalText = intervalValue == null
          ? "—"
          : (config.intervalFormat === "percent" ? formatPercentInterval(intervalValue) : formatInterval(intervalValue));
        const displayText = intervalValue == null ? valueText : valueText + " · 95% CI " + intervalText;
        row.appendChild(labelElement);
        row.appendChild(tracks);
        row.appendChild(this._element("span", "analysis-bar-value", displayText));
        if (selectable) {
          row.setAttribute("aria-label", label + ": " + displayText + ". Preview this selection.");
          this._activatePreview(row, item, label, summary, config.defaultKind);
        }
        listItem.appendChild(row);
        list.appendChild(listItem);
        const tableRow = [label, formatValue(value)];
        if (includeReference) tableRow.push(reference == null ? "—" : formatValue(reference));
        if (hasIntervals) tableRow.push(intervalText);
        rows.push(tableRow);
      });
      container.appendChild(list);
      if (includeReference) {
        const legend = this._element("p", "analysis-chart-legend", "Solid bar: active cohort · Thin bar: reference");
        container.appendChild(legend);
      }
      const headings = ["Category", config.valueLabel || "Active"];
      if (includeReference) headings.push(config.referenceLabel || "Reference");
      if (hasIntervals) headings.push("95% interval");
      this._appendDataTable(container, config.caption || "Chart values", headings, rows);
    }

    _renderStackedComposition(chartId, value, summary, options) {
      const config = options || {};
      const display = sourceCompositionDisplay(
        value,
        config.sourceLimit || SOURCE_COMPOSITION_SOURCE_LIMIT,
        config.periodLimit || SOURCE_COMPOSITION_PERIOD_LIMIT
      );
      const container = this._prepareChart(chartId, display.cells, summary, config.emptyMessage);
      if (!container) return;
      const chart = this._element("div", "analysis-composition-chart");
      const hasReference = this.currentAnalysisMode !== "whole_corpus_structure" && display.rows.some(function (row) {
        return row.referenceShare > 0 || row.referenceCount > 0;
      });

      display.periods.forEach((period) => {
        const periodRows = display.rows.filter(function (row) { return row.period === period; });
        const periodGroup = this._element("section", "analysis-composition-period");
        periodGroup.appendChild(this._element("h5", "analysis-composition-period-label", period));

        const appendCohortRow = (cohortLabel, shareKey, countKey, selectable) => {
          const cohortRow = this._element("div", "analysis-composition-row" + (selectable ? "" : " is-reference"));
          cohortRow.appendChild(this._element("span", "analysis-composition-cohort", cohortLabel));
          const track = this._element("div", "analysis-composition-track");
          track.setAttribute("role", "group");
          const total = periodRows.reduce(function (sum, row) { return sum + Math.max(0, row[shareKey]); }, 0);
          const summaryText = periodRows.filter(function (row) { return row[shareKey] > 0; }).map(function (row) {
            return row.source + " " + formatPercent(row[shareKey]);
          }).join(", ");
          track.setAttribute("aria-label", period + " " + cohortLabel.toLowerCase() + " source composition" + (summaryText ? ": " + summaryText : ": no reports"));
          if (total <= 0) {
            track.appendChild(this._element("span", "analysis-composition-empty", "No reports"));
          } else {
            periodRows.forEach((row, sourceIndex) => {
              const share = Math.max(0, row[shareKey]);
              if (share <= 0) return;
              const canSelect = selectable && row.item && datumHasPreview(row.item);
              const segment = this._element(canSelect ? "button" : "span", "analysis-composition-segment");
              if (canSelect) segment.type = "button";
              segment.style.setProperty("--analysis-composition-share", ((share / total) * 100).toFixed(5) + "%");
              segment.style.setProperty("--analysis-composition-color", CHART_COLORS[sourceIndex % CHART_COLORS.length]);
              const accessibleLabel = row.source + ": " + formatPercent(share) + " (" + formatCount(row[countKey]) + " reports)";
              segment.setAttribute("aria-label", accessibleLabel + (canSelect ? ". Preview this source selection." : ""));
              segment.setAttribute("title", accessibleLabel);
              segment.appendChild(this._element("span", "sr-only", accessibleLabel));
              if (canSelect) this._activatePreview(segment, row.item, period + " / " + row.source, summary, config.defaultKind || "filter");
              track.appendChild(segment);
            });
          }
          cohortRow.appendChild(track);
          periodGroup.appendChild(cohortRow);
        };

        appendCohortRow(this.currentAnalysisMode === "whole_corpus_structure" ? "All records" : "Active", "activeShare", "activeCount", true);
        if (hasReference) appendCohortRow("Reference", "referenceShare", "referenceCount", false);
        chart.appendChild(periodGroup);
      });
      container.appendChild(chart);

      const legend = this._element("ul", "analysis-composition-legend");
      display.sources.forEach((source, sourceIndex) => {
        const entry = this._element("li", "", source);
        entry.style.setProperty("--analysis-composition-color", CHART_COLORS[sourceIndex % CHART_COLORS.length]);
        legend.appendChild(entry);
      });
      container.appendChild(legend);
      container.appendChild(this._element(
        "p",
        "analysis-chart-summary",
        hasReference
          ? "Each cohort row is a 100% stacked source composition; labels retain the worker-provided cohort shares and absolute report counts."
          : "The row is the 100% source composition of all matched records; no duplicate reference is drawn."
      ));
      const tableColumns = ["Period", "Source", hasReference ? "Active share" : "Share", hasReference ? "Active reports" : "Reports"];
      if (hasReference) tableColumns.push("Reference share", "Reference reports");
      this._appendDataTable(container, config.caption || "Source composition by period", tableColumns, display.rows.map(function (row) {
        const values = [row.period, row.source, formatPercent(row.activeShare), formatCount(row.activeCount)];
        if (hasReference) values.push(formatPercent(row.referenceShare), formatCount(row.referenceCount));
        return values;
      }));
      if (display.groupedSources || display.sampledPeriods) {
        const notes = [];
        if (display.groupedSources) {
          notes.push("the " + (display.sources.length - 1) + " highest-volume sources are shown separately and "
            + (display.sourceCount - display.sources.length + 1) + " lower-volume sources are combined as Other sources");
        }
        if (display.sampledPeriods) {
          notes.push(display.periods.length + " of " + display.periodCount + " periods are evenly sampled, retaining the first and last periods");
        }
        this._appendChartPolicy(chartId, "Display scope: " + notes.join("; ") + ". Worker calculations and cohort totals remain unchanged.");
      }
    }

    _normalizeSeries(items) {
      const data = asArray(items);
      if (data.some(function (item) { return isObject(item) && Array.isArray(item.points); })) {
        return data.map(function (series, index) {
          return {
            label: cleanText(firstDefined(series, ["label", "name", "series"], "Series " + (index + 1))),
            points: asArray(series.points),
            colorIndex: Number.isFinite(Number(series.colorIndex)) ? Number(series.colorIndex) : index,
            reference: Boolean(series.reference),
          };
        });
      }
      const grouped = new Map();
      data.forEach(function (item) {
        const group = cleanText(firstDefined(item, ["series", "seriesLabel"], "Active"), "Active");
        if (!grouped.has(group)) grouped.set(group, []);
        grouped.get(group).push(item);
      });
      if (data.some(function (item) { return datumReference(item) != null; })) {
        grouped.set("Reference", data.map(function (item) {
          return Object.assign({}, item, { value: datumReference(item), preview: null, selection: null, patch: null, area: null });
        }));
      }
      return Array.from(grouped.entries()).map(function (entry) {
        return { label: entry[0], points: entry[1], reference: /^Reference\b/i.test(entry[0]) };
      });
    }

    _renderSeries(chartId, items, summary, options) {
      const config = options || {};
      const singleSeries = config.singleSeries === true || this.currentAnalysisMode === "whole_corpus_structure";
      let normalizedSeries = collapseDuplicateReferenceSeries(this._normalizeSeries(items));
      if (singleSeries) {
        normalizedSeries = normalizedSeries.filter(function (item) {
          return !item.reference && !/(^|·)\s*reference\b/i.test(cleanText(item.label));
        }).slice(0, 1).map(function (item) {
          return Object.assign({}, item, { label: cleanText(config.singleSeriesLabel, "All records"), reference: false });
        });
      }
      const ordered = orderedSeriesDisplay(normalizedSeries, SERIES_POINT_LIMIT, {
        axisKind: config.axisKind || "auto",
        axisOrder: config.axisOrder || [],
      });
      const series = ordered.series;
      const displaySampled = ordered.sampled;
      const pointCount = series.reduce(function (count, item) { return count + item.points.length; }, 0);
      const container = this._prepareChart(chartId, pointCount ? [true] : [], summary, config.emptyMessage);
      if (!container) return;
      const formatValue = config.valueFormat === "percent" ? formatPercent : function (number) { return formatDecimal(number, 3); };
      const width = 720;
      const height = 270;
      const padding = { top: 18, right: 18, bottom: 48, left: 58 };
      const labels = ordered.labels;
      const values = [];
      series.forEach(function (item) {
        item.points.forEach(function (point) {
          const value = Math.max(0, datumValue(point));
          values.push(value);
          if (config.countUncertainty) values.push(poissonCountInterval(value).upper);
        });
      });
      const maxValue = positiveSeriesMaximum(values);
      const plotWidth = width - padding.left - padding.right;
      const plotHeight = height - padding.top - padding.bottom;
      const xFor = function (label) {
        const index = Math.max(0, labels.indexOf(label));
        return padding.left + (labels.length <= 1 ? plotWidth / 2 : (index / (labels.length - 1)) * plotWidth);
      };
      const yFor = function (value) {
        return padding.top + plotHeight - ((Math.max(0, value) / maxValue) * plotHeight);
      };
      const svg = this._svgElement("svg", {
        class: "analysis-series-svg",
        viewBox: "0 0 " + width + " " + height,
        role: "img",
        "aria-label": config.ariaLabel || (config.singleSeries ? "Trend chart for all matched records" : "Trend chart for the active and reference cohorts"),
      });
      svg.appendChild(this._svgElement("line", { x1: padding.left, y1: padding.top, x2: padding.left, y2: padding.top + plotHeight, class: "analysis-axis-line" }));
      svg.appendChild(this._svgElement("line", { x1: padding.left, y1: padding.top + plotHeight, x2: width - padding.right, y2: padding.top + plotHeight, class: "analysis-axis-line" }));
      [0, 0.5, 1].forEach((ratio) => {
        const value = maxValue * ratio;
        const y = yFor(value);
        const grid = this._svgElement("line", { x1: padding.left, y1: y, x2: width - padding.right, y2: y, class: "analysis-grid-line" });
        svg.appendChild(grid);
        const text = this._svgElement("text", { x: padding.left - 8, y: y + 4, class: "analysis-axis-label", "text-anchor": "end" });
        text.textContent = formatValue(value);
        svg.appendChild(text);
      });
      const tickStep = Math.max(1, Math.ceil(labels.length / 8));
      labels.forEach((label, index) => {
        if (index % tickStep !== 0 && index !== labels.length - 1) return;
        const text = this._svgElement("text", { x: xFor(label), y: height - 18, class: "analysis-axis-label", "text-anchor": "middle" });
        text.textContent = label.length > 12 ? label.slice(0, 11) + "…" : label;
        svg.appendChild(text);
      });
      series.forEach((seriesItem, seriesIndex) => {
        const colorIndex = seriesItem.colorIndex != null && Number.isFinite(Number(seriesItem.colorIndex)) ? Number(seriesItem.colorIndex) : seriesIndex;
        const color = CHART_COLORS[colorIndex % CHART_COLORS.length];
        const referenceSeries = Boolean(seriesItem.reference) || /(^|\u00b7)\s*reference\b/i.test(seriesItem.label);
        const sorted = seriesItem.points.slice().sort(function (left, right) {
          return labels.indexOf(datumLabel(left, 0)) - labels.indexOf(datumLabel(right, 0));
        });
        if (config.countUncertainty && sorted.length) {
          const upperPath = sorted.map(function (point, pointIndex) {
            const x = xFor(datumLabel(point, pointIndex));
            const y = yFor(poissonCountInterval(datumValue(point)).upper);
            return (pointIndex ? "L" : "M") + x.toFixed(2) + " " + y.toFixed(2);
          }).join(" ");
          const lowerPath = sorted.slice().reverse().map(function (point) {
            return "L" + xFor(datumLabel(point, 0)).toFixed(2) + " " + yFor(poissonCountInterval(datumValue(point)).lower).toFixed(2);
          }).join(" ");
          svg.appendChild(this._svgElement("path", {
            d: upperPath + " " + lowerPath + " Z",
            fill: color,
            stroke: "none",
            class: "analysis-series-uncertainty" + (referenceSeries ? " is-reference" : ""),
          }));
        }
        const pathData = sorted.map(function (point, pointIndex) {
          const x = xFor(datumLabel(point, pointIndex));
          const y = yFor(datumValue(point));
          return (pointIndex ? "L" : "M") + x.toFixed(2) + " " + y.toFixed(2);
        }).join(" ");
        svg.appendChild(this._svgElement("path", {
          d: pathData,
          fill: "none",
          stroke: color,
          "stroke-width": referenceSeries ? 2 : 3,
          "stroke-dasharray": referenceSeries ? "7 5" : "none",
          class: "analysis-series-line",
        }));
        sorted.forEach((point, pointIndex) => {
          const label = datumLabel(point, pointIndex);
          const value = datumValue(point);
          const circle = this._svgElement("circle", {
            cx: xFor(label),
            cy: yFor(value),
            r: 4,
            fill: color,
            class: "analysis-series-point",
            "aria-label": seriesItem.label + ", " + label + ": " + formatValue(value)
              + (config.countUncertainty ? "; approximate 95% Poisson count interval " + formatInterval(poissonCountInterval(value)) : ""),
          });
          const title = this._svgElement("title");
          title.textContent = seriesItem.label + " · " + label + ": " + formatValue(value)
            + (config.countUncertainty ? " · approximate 95% Poisson count interval " + formatInterval(poissonCountInterval(value)) : "");
          circle.appendChild(title);
          this._activatePreview(circle, point, label, summary, config.defaultKind);
          svg.appendChild(circle);
        });
      });
      container.appendChild(svg);
      const legend = this._element("ul", "analysis-series-legend");
      series.forEach(function (item, index) {
        const entry = documentSafeElement(container.ownerDocument, "li", "", item.label);
        const colorIndex = item.colorIndex != null && Number.isFinite(Number(item.colorIndex)) ? Number(item.colorIndex) : index;
        entry.style.setProperty("--analysis-series-color", CHART_COLORS[colorIndex % CHART_COLORS.length]);
        legend.appendChild(entry);
      });
      container.appendChild(legend);
      const tableRows = [];
      ordered.fullSeries.forEach(function (seriesItem) {
        seriesItem.points.forEach(function (point, pointIndex) {
          const value = datumValue(point);
          const row = [datumLabel(point, pointIndex), seriesItem.label, formatValue(value)];
          if (config.countUncertainty) {
            const interval = poissonCountInterval(value);
            row.push(formatDecimal(interval.lower, 2), formatDecimal(interval.upper, 2));
          }
          tableRows.push(row);
        });
      });
      const tableHeadings = ["Period", "Series", "Value"];
      if (config.countUncertainty) tableHeadings.push("Approx. 95% lower count", "Approx. 95% upper count");
      this._appendLazyDataTable(container, config.caption || "Trend values", tableHeadings, tableRows);
      if (config.countUncertainty) {
        this._appendChartPolicy(chartId, "The translucent ribbon is an approximate descriptive 95% Poisson interval for report counts. It is not an incidence estimate or a causal confidence interval.");
      }
      if (displaySampled) {
        this._appendChartPolicy(
          chartId,
          "The shared chronological axis is ordered before it is evenly sampled to at most " + SERIES_POINT_LIMIT + " periods. The complete accessible table retains every period."
        );
      }
    }

    _renderAdaptiveTimeline(chartId, value, summary, options) {
      const config = options || {};
      const source = isObject(value) ? value : {};
      const volume = asArray(source.volume);
      const annual = asArray(source.annual);
      const balanced = asArray(source.balanced);
      const collection = firstDefined(source, ["collection", "sourceByTime", "source_by_time"], []);
      const collectionDisplay = sourceCompositionDisplay(collection, SOURCE_COMPOSITION_SOURCE_LIMIT, SOURCE_COMPOSITION_PERIOD_LIMIT);
      const modes = [{ key: "volume", label: "Report volume" }];
      if (balanced.length) modes.push({ key: "balanced", label: "Source-balanced activity" });
      if (collectionDisplay.cells.length) modes.push({ key: "collection", label: "Collection change" });

      const collectionChangeSummary = function () {
        if (collectionDisplay.periods.length < 2) return "One source-composition period is available; change requires at least two periods.";
        let largest = { difference: -1, from: "", to: "" };
        for (let index = 1; index < collectionDisplay.periods.length; index += 1) {
          const previous = collectionDisplay.periods[index - 1];
          const current = collectionDisplay.periods[index];
          let distance = 0;
          collectionDisplay.sources.forEach(function (sourceLabel) {
            const previousRow = collectionDisplay.rows.find(function (row) { return row.period === previous && row.source === sourceLabel; });
            const currentRow = collectionDisplay.rows.find(function (row) { return row.period === current && row.source === sourceLabel; });
            distance += Math.abs((currentRow ? currentRow.activeShare : 0) - (previousRow ? previousRow.activeShare : 0));
          });
          distance /= 2;
          if (distance > largest.difference) largest = { difference: distance, from: previous, to: current };
        }
        return "Largest displayed source-composition shift: " + largest.from + " to " + largest.to + " (" + formatPercent(largest.difference) + " total-variation distance).";
      };

      const appendAdaptivePolicy = () => {
        const adaptiveWidth = Number(firstDefined(source.adaptiveBinning, ["widthYears", "width_years"], 0));
        const adaptiveUnit = cleanText(firstDefined(source.adaptiveBinning, ["unit"], adaptiveWidth === 1 ? "year" : "period"));
        if (adaptiveWidth > 0) {
          this._appendChartPolicy(chartId, "Adaptive display uses " + (adaptiveWidth === 1 ? "annual" : formatCount(adaptiveWidth) + "-year")
            + " " + adaptiveUnit + " bins; structurally empty periods are omitted.");
        }
      };

      const appendRawAnnualTable = () => {
        const container = this.document.getElementById(chartId);
        if (!container || !annual.length) return;
        const annualOrder = sortSemanticAxis(annual.map(function (item, index) { return datumLabel(item, index); }), "year");
        const annualOrderIndex = new Map(annualOrder.map(function (label, index) { return [label, index]; }));
        const orderedAnnual = annual.slice().sort(function (left, right) {
          return annualOrderIndex.get(datumLabel(left, 0)) - annualOrderIndex.get(datumLabel(right, 0));
        });
        const displayedAnnual = sampleEvenly(orderedAnnual, SERIES_POINT_LIMIT);
        const hasReference = this.currentAnalysisMode !== "whole_corpus_structure" && displayedAnnual.some(function (item) {
          return datumReference(item) != null;
        });
        const headings = ["Period", this.currentAnalysisMode === "whole_corpus_structure" ? "Reports" : "Active reports"];
        if (hasReference) headings.push("Reference reports");
        this._appendDataTable(container, "Raw annual report counts", headings, displayedAnnual.map(function (item, index) {
          const row = [datumLabel(item, index), formatCount(datumValue(item))];
          if (hasReference) row.push(formatCount(datumReference(item)));
          return row;
        }));
        if (displayedAnnual.length < orderedAnnual.length) {
          this._appendChartPolicy(chartId, "The raw annual accessible table is evenly sampled to " + SERIES_POINT_LIMIT + " periods after chronological ordering; calculations and cohort totals still use every period.");
        }
      };

      const renderMode = (requestedMode) => {
        const mode = modes.some(function (candidate) { return candidate.key === requestedMode; }) ? requestedMode : modes[0].key;
        if (mode === "balanced") {
          this._renderSeries(chartId, balanced, summary, {
            caption: "Source-balanced reporting activity by adaptive period",
            defaultKind: config.defaultKind || "filter",
            valueFormat: "percent",
            axisKind: "year",
            singleSeries: this.currentAnalysisMode === "whole_corpus_structure",
            singleSeriesLabel: "All records · source-balanced share",
          });
          this._appendChartPolicy(chartId, source.sourceBalancedPolicy || "Each source contributes equal total weight through its within-source adaptive-period shares.");
          appendAdaptivePolicy();
          appendRawAnnualTable();
        } else if (mode === "collection") {
          this._renderStackedComposition(chartId, collection, summary, {
            caption: "Source composition and collection change by period",
            defaultKind: config.defaultKind || "filter",
          });
          this._appendChartPolicy(chartId, collectionChangeSummary());
        } else {
          this._renderSeries(chartId, volume, summary, {
            caption: "Adaptive report volume with descriptive count uncertainty",
            defaultKind: config.defaultKind || "filter",
            axisKind: "year",
            countUncertainty: true,
            singleSeries: this.currentAnalysisMode === "whole_corpus_structure",
            singleSeriesLabel: "All records",
          });
          appendAdaptivePolicy();
        }
        const container = this.document.getElementById(chartId);
        if (!container) return;
        const controls = this._element("div", "analysis-timeline-view-controls");
        controls.setAttribute("role", "group");
        controls.setAttribute("aria-label", "Adaptive timeline view");
        modes.forEach(function (candidate) {
          const button = documentSafeElement(container.ownerDocument, "button", "analysis-timeline-view-button", candidate.label);
          button.type = "button";
          button.setAttribute("aria-pressed", candidate.key === mode ? "true" : "false");
          button.addEventListener("click", function () { renderMode(candidate.key); });
          controls.appendChild(button);
        });
        if (typeof container.insertBefore === "function") container.insertBefore(controls, container.firstChild || null);
        else container.appendChild(controls);
      };
      renderMode(config.defaultMode || (this.currentAnalysisMode === "whole_corpus_structure" ? "volume" : (balanced.length ? "balanced" : "volume")));
    }

    _renderHeatmap(chartId, value, summary, options) {
      const config = options || {};
      const axisLimit = Math.max(1, Math.min(HEATMAP_AXIS_LIMIT, Number(config.axisLimit) || HEATMAP_AXIS_LIMIT));
      const display = heatmapDisplayItems(value, config.valueKeys);
      const fullData = display.data;
      const completeData = config.completeData == null
        ? fullData
        : matrixItems(config.completeData).filter(function (item) {
          return cleanText(firstDefined(item, ["displayStatus", "display_status"], "")).toLowerCase() !== "structurally_empty";
        });
      const container = this._prepareChart(chartId, fullData, summary, config.emptyMessage || "No supported cells are available for this comparison.");
      if (!container) return;
      const formatValue = config.valueFormat === "percent" ? formatPercent : function (number) { return formatDecimal(number, 2); };
      const rows = display.rows;
      const columns = display.columns;
      const axisMetadata = isObject(value) ? firstDefined(value, ["axisMetadata", "axis_metadata", "axes"], {}) : {};
      const rowMetadata = isObject(axisMetadata) ? firstDefined(axisMetadata, ["rows", "row"], {}) : {};
      const columnMetadata = isObject(axisMetadata) ? firstDefined(axisMetadata, ["columns", "column"], {}) : {};
      const rowKind = config.rowAxisKind || firstDefined(rowMetadata, ["kind", "semanticKind", "semantic_kind"], "category");
      const columnKind = config.columnAxisKind || firstDefined(columnMetadata, ["kind", "semanticKind", "semantic_kind"], "auto");
      const fixedAxisColumns = asArray(config.axisColumns).map(function (value) { return cleanText(value); }).filter(Boolean);
      let displayedRows;
      let displayedColumns;
      if (config.squareAxes) {
        const categoryScores = new Map();
        fullData.forEach(function (item) {
          const score = conservativeEffectMagnitude(item, config.valueKeys, config.nullValue);
          const row = cleanText(firstDefined(item, ["row", "rowLabel", "group", "category"], "All"), "All");
          const column = cleanText(firstDefined(item, ["column", "columnLabel", "period", "month", "year", "label"], "Value"), "Value");
          categoryScores.set(row, Math.max(categoryScores.get(row) || 0, score));
          categoryScores.set(column, Math.max(categoryScores.get(column) || 0, score));
        });
        const requestedOrder = asArray(config.axisOrder || config.rowAxisOrder || config.columnAxisOrder).map(cleanText);
        const union = Array.from(new Set(rows.concat(columns))).sort(function (left, right) {
          const leftRequested = requestedOrder.indexOf(left);
          const rightRequested = requestedOrder.indexOf(right);
          if (leftRequested !== -1 || rightRequested !== -1) {
            if (leftRequested === -1) return 1;
            if (rightRequested === -1) return -1;
            return leftRequested - rightRequested;
          }
          return (categoryScores.get(right) || 0) - (categoryScores.get(left) || 0) || left.localeCompare(right);
        }).slice(0, axisLimit);
        const shared = sortSemanticAxis(union, rowKind, requestedOrder);
        displayedRows = shared;
        displayedColumns = shared.slice();
      } else {
        displayedRows = sortSemanticAxis(rows.slice(0, axisLimit), rowKind, config.rowAxisOrder || firstDefined(rowMetadata, ["order", "labels"], []));
        const columnCandidates = fixedAxisColumns.length
          ? fixedAxisColumns.concat(columns.filter(function (column) { return fixedAxisColumns.indexOf(column) === -1; }))
          : columns;
        displayedColumns = sortSemanticAxis(
          columnCandidates,
          columnKind,
          config.columnAxisOrder || (fixedAxisColumns.length ? fixedAxisColumns : firstDefined(columnMetadata, ["order", "labels"], []))
        ).slice(0, axisLimit);
      }
      const formatRowLabel = typeof config.rowLabelFormatter === "function"
        ? config.rowLabelFormatter
        : (config.humanGeographyRows ? humanGeographyLabel : (config.craftRows ? craftDisplayLabel : cleanText));
      const formatColumnLabel = typeof config.columnLabelFormatter === "function"
        ? config.columnLabelFormatter
        : (columnKind === "month" ? monthDisplayLabel : (config.humanGeographyColumns ? humanGeographyLabel : (config.craftColumns ? craftDisplayLabel : cleanText)));
      const displayedRowSet = new Set(displayedRows);
      const displayedColumnSet = new Set(displayedColumns);
      const data = fullData.filter(function (item) {
        const row = cleanText(firstDefined(item, ["row", "rowLabel", "group", "category"], "All"), "All");
        const column = cleanText(firstDefined(item, ["column", "columnLabel", "period", "month", "year", "label"], "Value"), "Value");
        return displayedRowSet.has(row) && displayedColumnSet.has(column);
      });
      const lookup = new Map();
      data.forEach(function (item) {
        const row = cleanText(firstDefined(item, ["row", "rowLabel", "group", "category"], "All"), "All");
        const column = cleanText(firstDefined(item, ["column", "columnLabel", "period", "month", "year", "label"], "Value"), "Value");
        lookup.set(row + "\u0000" + column, item);
      });
      const maximum = Math.max(Number.EPSILON, ...fullData.map(function (item) { return Math.abs(comparativeEffect(item, config.valueKeys)); }));
      const qualifiedCount = fullData.filter(inferenceEligible).length;
      const descriptiveCount = fullData.filter(function (item) {
        return estimateAvailable(item, config.valueKeys) && !inferenceEligible(item);
      }).length;
      container.appendChild(this._element("p", "analysis-heatmap-legend", "Blue = above expectation · amber = below expectation · diagonal overlay = descriptive estimate with limited inferential support"));
      container.appendChild(this._element(
        "p",
        "analysis-qualification-summary" + (qualifiedCount ? "" : " is-descriptive-only"),
        qualifiedCount
          ? formatCount(qualifiedCount) + " inferentially qualified " + (qualifiedCount === 1 ? "cell" : "cells") + " · " + formatCount(descriptiveCount) + " additional descriptive " + (descriptiveCount === 1 ? "estimate" : "estimates")
          : "No cells qualify for inference in this view. " + formatCount(descriptiveCount) + " descriptive " + (descriptiveCount === 1 ? "estimate remains" : "estimates remain") + " visible."
      ));
      const tableWrap = this._element("div", "analysis-heatmap-scroll");
      const table = this._element("table", "analysis-heatmap-table");
      const caption = this._element("caption", "sr-only", config.caption || "Heatmap values");
      table.appendChild(caption);
      const head = this._element("thead");
      const headRow = this._element("tr");
      headRow.appendChild(this._element("th", "", config.rowHeading || "Group"));
      displayedColumns.forEach((column) => {
        const heading = this._element("th", craftDisplayLabel(column) === "Formation" ? "is-formation-lane" : "", formatColumnLabel(column));
        heading.setAttribute("data-axis-key", column);
        heading.setAttribute("aria-label", formatColumnLabel(column));
        headRow.appendChild(heading);
      });
      head.appendChild(headRow);
      table.appendChild(head);
      const body = this._element("tbody");
      displayedRows.forEach((row) => {
        const tableRow = this._element("tr");
        const rowHeadingElement = this._element("th", craftDisplayLabel(row) === "Formation" ? "is-formation-lane" : "", formatRowLabel(row));
        rowHeadingElement.setAttribute("data-axis-key", row);
        tableRow.appendChild(rowHeadingElement);
        displayedColumns.forEach((column) => {
          const cell = this._element("td");
          const rowLabel = formatRowLabel(row);
          const columnLabel = formatColumnLabel(column);
          const diagonal = config.squareAxes && row === column;
          if (diagonal) cell.classList.add("is-diagonal");
          if (craftDisplayLabel(row) === "Formation" || craftDisplayLabel(column) === "Formation") cell.classList.add("has-formation-lane");
          const item = lookup.get(row + "\u0000" + column);
          if (!item) {
            const empty = this._element("span", "analysis-heat-cell is-structural-empty" + (diagonal ? " is-diagonal" : ""), diagonal ? "—" : "");
            empty.setAttribute("aria-label", rowLabel + ", " + columnLabel + ": " + (diagonal ? "same-category diagonal; no estimate available." : "structurally empty or outside the selected display cells."));
            empty.setAttribute("title", diagonal ? "Same-category diagonal · no estimate available" : "Structurally empty");
            cell.appendChild(empty);
          } else {
            const valueNumber = comparativeEffect(item, config.valueKeys);
            const reason = suppressionReason(item);
            const qualified = inferenceEligible(item);
            const available = estimateAvailable(item, config.valueKeys);
            const selectable = available && (datumHasPreview(item) || config.inspectable !== false);
            const formattedValue = available ? formatValue(valueNumber) : "Not estimable";
            const mark = this._element(selectable ? "button" : "span", "analysis-heat-cell" + (diagonal ? " is-diagonal" : ""));
            if (selectable) mark.type = "button";
            mark.style.setProperty("--analysis-heat-percent", (12 + (Math.min(1, Math.abs(valueNumber) / maximum) * 74)).toFixed(2) + "%");
            if (valueNumber < 0) mark.classList.add("is-negative");
            if (!qualified) mark.classList.add("is-low-support");
            if (!available) mark.classList.add("is-not-estimable");
            mark.appendChild(this._element("span", "analysis-heat-cell-value", formattedValue));
            const observed = firstDefined(item, ["activeCount", "active_count", "observedCount", "observed_count", "observed", "count"], null);
            const expected = firstDefined(item, ["referenceCount", "reference_count", "expectedCount", "expected_count", "reference", "expected"], null);
            const countText = observed == null && expected == null
              ? ""
              : "O " + formatCount(observed) + (expected == null ? "" : " · E " + formatCount(expected));
            if (countText && !config.effectOnly) mark.appendChild(this._element("span", "analysis-heat-cell-counts", countText));
            const interval = intervalBounds(item);
            const pValue = firstDefined(item, ["pValue", "p_value", "p"], null);
            const qValue = firstDefined(item, ["qValue", "q_value", "q"], null);
            const support = firstDefined(item, ["commonSupportRate", "common_support_rate", "supportRate", "support_rate", "supportedN", "supported_n", "contextClusterN", "context_cluster_n"], null);
            const evidenceText = [
              interval ? "95% CI " + formatInterval(interval) : "",
              pValue == null ? "" : "p " + formatDecimal(pValue, 3),
              qValue == null ? "" : "q " + formatDecimal(qValue, 3),
            ].filter(Boolean).join(" · ");
            if (evidenceText && !config.effectOnly) mark.appendChild(this._element("span", "analysis-heat-cell-evidence", evidenceText));
            const statusText = qualified ? "inferentially qualified" : (reason ? "descriptive estimate; " + reason : "descriptive estimate");
            const supportText = support == null ? "" : (String(firstDefined(item, ["commonSupportRate", "common_support_rate", "supportRate", "support_rate"], "")) !== "" ? "support " + formatPercent(support) : "supported n=" + formatCount(support));
            mark.setAttribute("aria-label", rowLabel + ", " + columnLabel + ": " + formattedValue + (countText ? "; " + countText : "") + (evidenceText ? "; " + evidenceText : "") + (supportText ? "; " + supportText : "") + ". " + statusText + "." + (selectable ? " Inspect evidence details." : ""));
            mark.setAttribute("title", [rowLabel + " / " + columnLabel + ": " + formattedValue, countText, statusText, evidenceText, supportText].filter(Boolean).join(" · "));
            if (selectable) this._activateEvidenceInspection(mark, item, rowLabel + " / " + columnLabel, summary, config);
            cell.appendChild(mark);
          }
          tableRow.appendChild(cell);
        });
        body.appendChild(tableRow);
      });
      table.appendChild(body);
      tableWrap.appendChild(table);
      container.appendChild(tableWrap);
      if (displayedRows.length < rows.length || displayedColumns.length < columns.length) {
        this._appendChartPolicy(
          chartId,
          "Display shows " + displayedRows.length + " of " + rows.length + " highest-information rows and "
            + displayedColumns.length + " of " + columns.length + " highest-information columns (at most "
            + (axisLimit * axisLimit) + " cells); calculations and evidence gates use every cell."
        );
      }
      this._appendLazyDataTable(
        container,
        (config.caption || "Heatmap") + " complete qualified data",
        [config.rowHeading || "Group", "Column", "Effect", "Observed n", "Expected/reference n", "95% interval", "p-value", "q-value", "Support", "Status"],
        completeData.map(function (item) {
          const rawRow = cleanText(firstDefined(item, ["row", "rowLabel", "group", "category"], "All"), "All");
          const rawColumn = cleanText(firstDefined(item, ["column", "columnLabel", "period", "month", "year", "label"], "Value"), "Value");
          return [
            config.preserveRawCompleteLabels ? rawRow : formatRowLabel(rawRow),
            config.preserveRawCompleteLabels ? rawColumn : formatColumnLabel(rawColumn),
            formatValue(comparativeEffect(item, config.valueKeys)),
            formatCount(firstDefined(item, ["activeCount", "active_count", "observedCount", "observed_count", "observedClusterCount", "observed_cluster_count", "observed", "count"], null)),
            formatCount(firstDefined(item, ["referenceCount", "reference_count", "expectedCount", "expected_count", "expectedClusterCount", "expected_cluster_count", "reference", "expected"], null)),
            intervalBounds(item) ? formatInterval(intervalBounds(item)) : "—",
            formatDecimal(firstDefined(item, ["pValue", "p_value", "p"], null), 3),
            formatDecimal(firstDefined(item, ["qValue", "q_value", "q"], null), 3),
            firstDefined(item, ["commonSupportRate", "common_support_rate", "supportRate", "support_rate"], null) == null
              ? formatCount(firstDefined(item, ["supportedN", "supported_n", "contextClusterN", "context_cluster_n"], null))
              : formatPercent(firstDefined(item, ["commonSupportRate", "common_support_rate", "supportRate", "support_rate"], null)),
            inferenceEligible(item) ? "Inferentially qualified" : (suppressionReason(item) ? "Descriptive · " + suppressionReason(item) : "Descriptive estimate"),
          ];
        })
      );
      const peak = data.slice().filter(function (item) { return estimateAvailable(item, config.valueKeys); }).sort(function (left, right) {
        return Math.abs(comparativeEffect(right, config.valueKeys)) - Math.abs(comparativeEffect(left, config.valueKeys));
      })[0];
      if (peak) {
        const peakRow = formatRowLabel(cleanText(firstDefined(peak, ["row", "rowLabel", "group", "category"], "All")));
        const peakColumn = formatColumnLabel(cleanText(firstDefined(peak, ["column", "columnLabel", "period", "month", "year", "label"], "Value")));
        container.appendChild(this._element("p", "analysis-chart-summary", "Largest displayed magnitude: " + peakRow + " / " + peakColumn + " (" + formatValue(comparativeEffect(peak, config.valueKeys)) + ") · " + (inferenceEligible(peak) ? "inferentially qualified" : "descriptive") + "."));
      }
    }

    _renderCountryChoropleth(chartId, value, summary, options) {
      const config = options || {};
      const wholeCorpus = this.currentAnalysisMode === "whole_corpus_structure";
      const mapData = isObject(value) ? value : {};
      const items = countryEvidenceItems(value);
      const decadeItems = countryEvidenceItems(firstDefined(mapData, ["byDecade", "by_decade", "decades"], []));
      const craftAssociation = firstDefined(mapData, ["craftAssociations", "craft_associations", "selectedCraftAssociation", "selected_craft_association"], {});
      const craftItems = countryEvidenceItems(firstDefined(craftAssociation, ["fullCells", "full_cells", "cells", "items"], []));
      const world = this._getWorldReferenceData();
      const features = asArray(world && world.features).filter(function (feature) {
        return feature && feature.geometry && (feature.geometry.type === "Polygon" || feature.geometry.type === "MultiPolygon")
          && Array.isArray(feature.geometry.coordinates) && feature.geometry.coordinates.length;
      });
      if (!items.length || !features.length) return false;
      const container = this._prepareChart(chartId, items, summary, config.emptyMessage || "No country-level evidence is available.");
      if (!container) return false;
      const coordinateClassFor = function (item) {
        return cleanText(firstDefined(item, ["coordinateClass", "coordinate_class", "coordinateEvidenceClass", "coordinate_evidence_class"], "all"), "all").toLowerCase();
      };
      const coordinateClassLabel = function (value) {
        const key = cleanText(value, "all").toLowerCase();
        if (key === "source_coordinates" || key === "source_provided" || key === "exact") return "Source-provided coordinates";
        if (key === "generalized_coordinates" || key === "generalized") return "Generalized coordinates";
        if (key === "unmapped") return "Unmapped";
        return key === "all" ? "All coordinate classes" : key.replace(/_/g, " ");
      };
      const coordinateClasses = Array.from(new Set(items.concat(decadeItems, craftItems).map(coordinateClassFor))).sort(function (left, right) {
        const priority = { source_coordinates: 0, source_provided: 0, exact: 0, generalized_coordinates: 1, generalized: 1, all: 2, unmapped: 3 };
        return firstDefined(priority, [left], 9) - firstDefined(priority, [right], 9) || left.localeCompare(right);
      });
      let activeCoordinateClass = coordinateClasses[0] || "all";
      const decadeValues = sortSemanticAxis(Array.from(new Set(decadeItems.map(function (item) {
        return cleanText(firstDefined(item, ["period", "column", "decade"], ""));
      }).filter(Boolean))), "decade");
      let activeDecade = "all";
      const craftValues = Array.from(new Set(craftItems.map(function (item) {
        return cleanText(firstDefined(item, ["craft", "row", "category"], ""));
      }).filter(Boolean))).sort(function (left, right) {
        return craftDisplayLabel(left).localeCompare(craftDisplayLabel(right));
      });
      let activeCraft = craftValues[0] || "";
      let cachedPaths = this.worldPathCache.get(world);
      if (!cachedPaths) {
        cachedPaths = new Map();
        features.forEach(function (feature, index) {
          const name = cleanText(firstDefined(feature.properties || {}, ["name", "NAME", "admin", "ADMIN"], "Country " + (index + 1)));
          cachedPaths.set(canonicalCountryName(name), { name, path: projectedGeometryPath(feature.geometry, 960, 480) });
        });
        this.worldPathCache.set(world, cachedPaths);
      }
      const modes = [
        { key: "effect", label: wholeCorpus ? "Source-balanced share" : "Adjusted effect" },
        { key: "craft", label: "Selected craft", available: craftItems.length > 0 },
        { key: "enrichment", label: "Log₂ enrichment", available: !wholeCorpus },
        { key: "count", label: "Report count" },
      ].filter(function (mode) { return mode.available !== false; });
      const controls = this._element("div", "analysis-map-mode-controls analysis-country-mode-controls");
      controls.setAttribute("role", "group");
      controls.setAttribute("aria-label", "Country choropleth measure");
      let coordinateSelect = null;
      if (coordinateClasses.length > 1) {
        const coordinateLabel = this._element("label", "field compact-field analysis-country-coordinate-field");
        coordinateLabel.appendChild(this._element("span", "", "Coordinate class"));
        coordinateSelect = this._element("select", "analysis-country-coordinate-select");
        coordinateSelect.setAttribute("aria-label", "Country choropleth coordinate class");
        coordinateClasses.forEach(function (coordinateClass) {
          const option = this._element("option", "", coordinateClassLabel(coordinateClass));
          option.value = coordinateClass;
          coordinateSelect.appendChild(option);
        }, this);
        coordinateSelect.value = activeCoordinateClass;
        coordinateLabel.appendChild(coordinateSelect);
        controls.appendChild(coordinateLabel);
      }
      let decadeSelect = null;
      if (decadeValues.length) {
        const decadeLabel = this._element("label", "field compact-field analysis-country-decade-field");
        decadeLabel.appendChild(this._element("span", "", "Decade"));
        decadeSelect = this._element("select", "analysis-country-decade-select");
        decadeSelect.setAttribute("aria-label", "Country choropleth decade");
        const allDecades = this._element("option", "", "All decades");
        allDecades.value = "all";
        decadeSelect.appendChild(allDecades);
        decadeValues.forEach(function (decade) {
          const option = this._element("option", "", decade + "s");
          option.value = decade;
          decadeSelect.appendChild(option);
        }, this);
        decadeLabel.appendChild(decadeSelect);
        controls.appendChild(decadeLabel);
      }
      let craftSelect = null;
      let craftLabel = null;
      if (craftValues.length) {
        craftLabel = this._element("label", "field compact-field analysis-country-craft-field");
        craftLabel.appendChild(this._element("span", "", "Craft"));
        craftSelect = this._element("select", "analysis-country-craft-select");
        craftSelect.setAttribute("aria-label", "Country choropleth selected craft");
        craftValues.forEach(function (craft) {
          const option = this._element("option", "", craftDisplayLabel(craft));
          option.value = craft;
          craftSelect.appendChild(option);
        }, this);
        craftSelect.value = activeCraft;
        craftLabel.hidden = true;
        craftLabel.appendChild(craftSelect);
        controls.appendChild(craftLabel);
      }
      const buttons = modes.map((mode, index) => {
        const button = this._element("button", "secondary-button analysis-map-mode-button", mode.label);
        button.type = "button";
        button.setAttribute("aria-pressed", index === 0 ? "true" : "false");
        controls.appendChild(button);
        return { mode, button };
      });
      container.appendChild(controls);
      const legend = this._element("p", "analysis-map-legend");
      container.appendChild(legend);
      const svg = this._svgElement("svg", {
        class: "analysis-country-choropleth",
        viewBox: "0 0 960 480",
        role: "img",
        "aria-label": "Country-level geography evidence map",
      });
      container.appendChild(svg);
      let marks = [];
      let activeMode = this.currentComparisonState === "unavailable_no_reference"
        || this.currentComparisonState === "unavailable_self_comparison" ? "count" : "effect";
      const evidenceForCurrentView = () => {
        if (activeMode === "craft") {
          return craftItems.filter(function (item) {
            return coordinateClassFor(item) === activeCoordinateClass
              && cleanText(firstDefined(item, ["craft", "row", "category"], "")) === activeCraft;
          });
        }
        if (activeDecade !== "all") {
          const selected = decadeItems.filter(function (item) {
            return coordinateClassFor(item) === activeCoordinateClass
              && cleanText(firstDefined(item, ["period", "column", "decade"], "")) === activeDecade;
          });
          const observedTotal = selected.reduce(function (sum, item) {
            return sum + finiteNumber(firstDefined(item, ["activeCount", "active_count", "observedCount", "observed_count", "observed", "count"], 0), 0);
          }, 0);
          const referenceTotal = wholeCorpus ? 0 : selected.reduce(function (sum, item) {
            return sum + finiteNumber(firstDefined(item, ["referenceCount", "reference_count", "reference"], 0), 0);
          }, 0);
          return selected.map(function (item) {
            const observed = finiteNumber(firstDefined(item, ["activeCount", "active_count", "observedCount", "observed_count", "observed", "count"], 0), 0);
            const referenceCountValue = wholeCorpus ? null : finiteNumber(firstDefined(item, ["referenceCount", "reference_count", "reference"], 0), 0);
            const observedShare = observedTotal > 0 ? observed / observedTotal : 0;
            const referenceShare = referenceTotal > 0 ? referenceCountValue / referenceTotal : null;
            const sourceBalancedShare = finiteNumber(firstDefined(item, ["sourceBalancedReportShare", "source_balanced_report_share", "sourceBalancedShare", "source_balanced_share"], observedShare), observedShare);
            const adjustedDifference = wholeCorpus ? null : firstDefined(item, ["adjustedDifference", "adjusted_difference", "difference"], null);
            const log2Enrichment = !wholeCorpus && referenceTotal > 0
              ? Math.log2(((observed + 0.5) / (observedTotal + 1)) / ((referenceCountValue + 0.5) / (referenceTotal + 1)))
              : null;
            const preview = isObject(item.preview) ? Object.assign({}, item.preview) : null;
            if (preview) {
              preview.criteria = asArray(firstDefined(preview, ["criteria", "changedCriteria"], [])).slice();
              preview.criteria.push(
                { label: "Measure", value: wholeCorpus ? "Source-balanced within-decade report share" : "Adjusted within-decade share difference" },
                { label: "Selected decade", value: activeDecade + "s" },
                { label: "Active reports in decade", value: formatCount(observed) },
                { label: "Source-balanced within-decade share", value: formatPercent(sourceBalancedShare) }
              );
              if (!wholeCorpus) {
                preview.criteria.push(
                  { label: "Reference reports in decade", value: formatCount(referenceCountValue) },
                  { label: "Adjusted within-decade share difference", value: adjustedDifference == null ? "Unavailable" : formatSignedPercent(adjustedDifference) },
                  { label: "Raw active within-decade share", value: formatPercent(observedShare) },
                  { label: "Raw reference within-decade share", value: referenceShare == null ? "Unavailable" : formatPercent(referenceShare) }
                );
              }
              const balancedShare = firstDefined(item, ["sourceBalancedReportShare", "source_balanced_report_share", "sourceBalancedShare", "source_balanced_share"], null);
              const referenceBalancedShare = firstDefined(item, ["referenceSourceBalancedReportShare", "reference_source_balanced_report_share"], null);
              const activeFacetN = firstDefined(item, ["decadeFacetActiveN", "decade_facet_active_n"], null);
              const referenceFacetN = firstDefined(item, ["decadeFacetReferenceN", "decade_facet_reference_n"], null);
              if (balancedShare != null && Math.abs(finiteNumber(balancedShare, 0) - sourceBalancedShare) > Number.EPSILON) preview.criteria.push({ label: "Source-balanced within-decade share", value: formatPercent(balancedShare) });
              if (!wholeCorpus && referenceBalancedShare != null) preview.criteria.push({ label: "Reference source-balanced within-decade share", value: formatPercent(referenceBalancedShare) });
              if (activeFacetN != null) preview.criteria.push({ label: "Selected-decade coordinate-facet reports", value: formatCount(activeFacetN) });
              if (!wholeCorpus && referenceFacetN != null) preview.criteria.push({ label: "Reference-decade coordinate-facet reports", value: formatCount(referenceFacetN) });
              preview.criteria.push({ label: "Source and provenance scope", value: "Selected decade only" });
              preview.summary = activeDecade + "s " + (wholeCorpus ? "source-balanced report share" : "adjusted share difference") + " for " + cleanText(firstDefined(item, ["country", "countryName", "country_name"], "this country")) + ". Source mix and assignment provenance shown here are computed from this selected decade only.";
              preview.comparison = wholeCorpus
                ? "Selected-decade reports n=" + formatCount(observed) + ". No reference cohort is used in All-Time internal-structure mode."
                : "Selected-decade active n=" + formatCount(observed) + " · reference n=" + formatCount(referenceCountValue) + ".";
            }
            const scopedItem = Object.assign({}, item, {
              activeCount: observed,
              observedCount: observed,
              referenceCount: referenceCountValue,
              expectedCount: null,
              reportShare: sourceBalancedShare,
              sourceBalancedReportShare: sourceBalancedShare,
              withinDecadeReportShare: sourceBalancedShare,
              adjustedDifference,
              difference: adjustedDifference,
              log2Enrichment: firstDefined(item, ["log2Enrichment", "log2_enrichment"], log2Enrichment),
              estimateAvailable: observed > 0 || (!wholeCorpus && referenceCountValue > 0),
              geographyEvidenceScope: wholeCorpus ? "selected_decade_source_balanced_share" : "selected_decade_adjusted_difference",
              preview,
            });
            return scopedItem;
          });
        }
        return items.filter(function (item) {
          return coordinateClassFor(item) === activeCoordinateClass;
        });
      };
      const renderCoordinateClass = () => {
        this._clear(svg);
        marks = [];
        const facetItems = evidenceForCurrentView();
        const byCountry = new Map(facetItems.map(function (item) { return [item.countryKey, item]; }));
        cachedPaths.forEach((geometry, countryKey) => {
          const item = byCountry.get(countryKey) || null;
          const path = this._svgElement("path", {
            d: geometry.path,
            class: "analysis-country-shape" + (item ? " has-evidence" : " is-no-data"),
            "data-country-key": countryKey,
          });
          if (!item) {
            path.setAttribute("aria-hidden", "true");
            path.setAttribute("fill", "transparent");
            path.setAttribute("stroke", "currentColor");
            path.setAttribute("stroke-opacity", "0.18");
          } else {
            const title = this._svgElement("title");
            path.appendChild(title);
            this._activateEvidenceInspection(path, item, geometry.name, summary, config);
            marks.push({ path, item, name: geometry.name, title });
          }
          svg.appendChild(path);
        });
      };
      const modeValue = function (item, key) {
        if (key === "count") return finiteNumber(firstDefined(item, ["activeCount", "active_count", "observedCount", "observed_count", "count"], 0));
        if (key === "enrichment") return finiteNumber(firstDefined(item, ["log2Enrichment", "log2_enrichment"], 0));
        if (key === "craft") return finiteNumber(firstDefined(item, ["adjustedResidual", "adjusted_residual", "standardizedResidual", "standardized_residual", "residual", "value"], 0));
        if (activeDecade !== "all") {
          return wholeCorpus
            ? finiteNumber(firstDefined(item, ["sourceBalancedReportShare", "source_balanced_report_share", "sourceBalancedShare", "source_balanced_share", "reportShare", "report_share"], 0))
            : finiteNumber(firstDefined(item, ["adjustedDifference", "adjusted_difference", "difference"], 0));
        }
        if (wholeCorpus) {
          return finiteNumber(firstDefined(item, ["sourceBalancedShare", "source_balanced_share", "reportShare", "report_share", "share"], 0));
        }
        return comparativeEffect(item, config.valueKeys);
      }.bind(this);
      const update = (modeKey) => {
        const maximum = Math.max(Number.EPSILON, ...marks.map(function (mark) { return Math.abs(modeValue(mark.item, modeKey)); }));
        buttons.forEach(function (entry) {
          entry.button.setAttribute("aria-pressed", entry.mode.key === modeKey ? "true" : "false");
          entry.button.textContent = entry.mode.key === "effect" && activeDecade !== "all"
            ? (wholeCorpus ? "Source-balanced share" : "Adjusted difference")
            : entry.mode.label;
        });
        if (craftLabel) craftLabel.hidden = modeKey !== "craft";
        if (decadeSelect) decadeSelect.disabled = modeKey === "craft";
        const selectedDecade = activeDecade !== "all" && modeKey !== "craft";
        legend.textContent = modeKey === "craft"
          ? craftDisplayLabel(activeCraft) + " association by country; blue is above conditional expectation and amber below."
          : (selectedDecade && modeKey === "effect"
          ? (wholeCorpus
            ? activeDecade + "s source-balanced within-decade report share; darker fill means a larger balanced share. No reference cohort is used."
            : activeDecade + "s adjusted within-decade share difference; blue is above the balanced reference and amber below. Active and reference counts are decade-local.")
          : (selectedDecade && modeKey === "count"
          ? activeDecade + "s raw within-decade report counts; darker fill means more reports in the selected decade."
          : (selectedDecade && modeKey === "enrichment"
          ? activeDecade + "s active/reference enrichment using decade-local counts."
          : (modeKey === "count"
          ? "Country report counts; darker fill means more matched reports."
          : (modeKey === "enrichment" ? "Country log₂ enrichment; blue is above expectation and amber below."
            : (activeDecade !== "all" ? activeDecade + "s country report-share structure."
              : (wholeCorpus ? "Source-balanced share of matched reports by country." : "Country adjusted effect; blue is above expectation and amber below.")))))));
        svg.setAttribute("aria-label", selectedDecade
          ? "Country-level " + (wholeCorpus ? "source-balanced report-share" : "adjusted comparison") + " map for the " + activeDecade + "s"
          : "Country-level geography evidence map");
        marks.forEach((mark) => {
          const valueNumber = modeValue(mark.item, modeKey);
          const count = firstDefined(mark.item, ["activeCount", "active_count", "observedCount", "observed_count", "count"], null);
          const selectedDecadeReference = selectedDecade
            ? firstDefined(mark.item, ["referenceCount", "reference_count", "reference"], null)
            : null;
          const conditionalExpected = selectedDecade ? null : firstDefined(mark.item, ["expectedCount", "expected_count", "expected", "referenceCount", "reference_count", "reference"], null);
          const formatted = modeKey === "count" ? formatCount(valueNumber) + " reports"
            : (modeKey === "craft" ? formatDecimal(valueNumber, 2) + " adjusted residual"
            : (modeKey === "effect" ? (wholeCorpus ? formatPercent(valueNumber) : formatSignedPercent(valueNumber)) : formatDecimal(valueNumber, 3)));
          const accessible = mark.name + ": " + formatted + "; observed n=" + formatCount(count)
            + (selectedDecadeReference == null ? "" : "; reference n=" + formatCount(selectedDecadeReference))
            + (conditionalExpected == null ? "" : "; conditional expected n=" + formatCount(conditionalExpected));
          mark.path.setAttribute("fill", modeKey !== "count" && valueNumber < 0 ? "#d18a34" : "#168aad");
          mark.path.setAttribute("fill-opacity", String(0.18 + (0.76 * Math.min(1, Math.abs(valueNumber) / maximum))));
          mark.path.setAttribute("stroke", "currentColor");
          mark.path.setAttribute("stroke-opacity", "0.35");
          mark.path.setAttribute("aria-label", accessible + ". Inspect evidence details.");
          mark.title.textContent = accessible;
        });
      };
      renderCoordinateClass();
      update(activeMode);
      buttons.forEach(function (entry) {
        entry.button.addEventListener("click", function () {
          activeMode = entry.mode.key;
          renderCoordinateClass();
          update(activeMode);
        });
      });
      if (coordinateSelect) {
        coordinateSelect.addEventListener("change", function () {
          activeCoordinateClass = cleanText(coordinateSelect.value, coordinateClasses[0]);
          renderCoordinateClass();
          update(activeMode);
        });
      }
      if (decadeSelect) {
        decadeSelect.addEventListener("change", function () {
          activeDecade = cleanText(decadeSelect.value, "all");
          renderCoordinateClass();
          update(activeMode);
        });
      }
      if (craftSelect) {
        craftSelect.addEventListener("change", function () {
          activeCraft = cleanText(craftSelect.value, craftValues[0]);
          renderCoordinateClass();
          update(activeMode);
        });
      }
      const countryTableRows = items.map(function (item) {
        const provenance = firstDefined(item, ["geographyAssignmentProvenance", "geography_assignment_provenance"], {});
        const provenanceText = [
          ["source", ["assignmentSources", "assignment_sources"], ["geographyAssignmentSource", "geography_assignment_source"]],
          ["confidence", ["assignmentConfidences", "assignment_confidences"], ["geographyAssignmentConfidence", "geography_assignment_confidence"]],
          ["boundary", ["boundaryStatuses", "boundary_statuses"], ["geographyBoundaryStatus", "geography_boundary_status"]],
          ["unknown", ["unknownStatuses", "unknown_statuses"], ["geographyUnknownStatus", "geography_unknown_status"]],
          ["macroregion", ["macroregions"], ["macroregion", "analysisMacroregion", "analysis_macroregion"]],
        ].map(function (definition) {
          const breakdown = isObject(provenance) ? evidenceBreakdownText(firstDefined(provenance, definition[1], []), ["value"]) : "";
          const fallback = cleanText(firstDefined(item, definition[2], "")).replace(/_/g, " ");
          return breakdown || fallback ? definition[0] + ": " + (breakdown || fallback) : "";
        }).filter(Boolean).join(" · ");
        return {
          country: item.country,
          coordinateClass: coordinateClassLabel(coordinateClassFor(item)),
          observed: formatCount(firstDefined(item, ["activeCount", "active_count", "observedCount", "observed_count", "count"], null)),
          expected: formatCount(firstDefined(item, ["referenceCount", "reference_count", "expectedCount", "expected_count", "expected"], null)),
          adjustedEffect: formatDecimal(comparativeEffect(item, config.valueKeys), 3),
          log2Enrichment: formatDecimal(firstDefined(item, ["log2Enrichment", "log2_enrichment"], null), 3),
          sourceBalancedShare: formatPercent(firstDefined(item, ["sourceBalancedReportShare", "source_balanced_report_share", "sourceBalancedShare", "source_balanced_share"], 0)),
          reportShare: formatPercent(firstDefined(item, ["reportShare", "report_share"], 0)),
          sourceMix: evidenceBreakdownText(firstDefined(item, ["sourceMix", "source_mix"], []), ["source"]) || "—",
          provenance: provenanceText || "—",
          status: inferenceEligible(item) ? "Inferentially qualified" : "Descriptive",
        };
      });
      if (wholeCorpus) {
        this._appendLazyDataTable(
          container,
          "Country whole-corpus geography evidence",
          ["Country", "Coordinate class", "Observed n", "Source-balanced report share", "Raw report share", "Source mix", "Assignment provenance", "Status"],
          countryTableRows.map(function (row) {
            return [row.country, row.coordinateClass, row.observed, row.sourceBalancedShare, row.reportShare, row.sourceMix, row.provenance, row.status];
          })
        );
      } else {
        this._appendLazyDataTable(
          container,
          "Country geography evidence",
          ["Country", "Coordinate class", "Observed n", "Expected n", "Adjusted effect", "Log2 enrichment", "Source mix", "Assignment provenance", "Status"],
          countryTableRows.map(function (row) {
            return [row.country, row.coordinateClass, row.observed, row.expected, row.adjustedEffect, row.log2Enrichment, row.sourceMix, row.provenance, row.status];
          })
        );
      }
      return true;
    }

    _getWorldReferenceData() {
      if (this.cachedWorldReferenceData) return this.cachedWorldReferenceData;
      const world = this.callbacks.getWorldReferenceData ? this.callbacks.getWorldReferenceData() : null;
      if (world && Array.isArray(world.features)) this.cachedWorldReferenceData = world;
      return world;
    }

    _renderEqualAreaMap(chartId, value, summary, options) {
      const config = options || {};
      const wholeCorpus = this.currentAnalysisMode === "whole_corpus_structure";
      const sourceItems = geographyMapCells(value).filter(function (item) {
        return isObject(item) && cleanText(firstDefined(item, ["displayStatus", "display_status"], "")).toLowerCase() !== "structurally_empty";
      });
      if (sourceItems.length && !sourceItems.some(function (item) {
        return Number.isFinite(Number(item.latIndex)) && Number.isFinite(Number(item.lonIndex));
      })) {
        this._renderHeatmap(chartId, sourceItems, summary, Object.assign({}, config, {
          caption: config.caption || "Geography evidence",
          rowHeading: "Region",
          emptyMessage: "No gridded geography evidence is available.",
        }));
        return;
      }
      const container = this._prepareChart(chartId, sourceItems, summary, config.emptyMessage || "No mapped reports meet the geography support gates.");
      if (!container) return;
      const maxLatIndex = Math.max(0, ...sourceItems.map(function (item) { return finiteNumber(item.latIndex, 0); }));
      const maxLonIndex = Math.max(0, ...sourceItems.map(function (item) { return finiteNumber(item.lonIndex, 0); }));
      const collapseRows = maxLatIndex >= 6;
      const collapseColumns = maxLonIndex >= 12;
      const groups = new Map();
      sourceItems.forEach(function (item) {
        if (!Number.isFinite(Number(item.latIndex)) || !Number.isFinite(Number(item.lonIndex))) return;
        const latIndex = Math.max(0, Math.min(5, Math.floor(Number(item.latIndex) / (collapseRows ? 2 : 1))));
        const lonIndex = Math.max(0, Math.min(11, Math.floor(Number(item.lonIndex) / (collapseColumns ? 2 : 1))));
        const coordinateClass = cleanText(firstDefined(item, ["coordinateClass", "coordinate_class"], "unspecified"), "unspecified");
        const key = coordinateClass + "\u0000" + latIndex + "\u0000" + lonIndex;
        let group = groups.get(key);
        if (!group) {
          const preview = isObject(item.preview) ? item.preview : null;
          group = { coordinateClass, latIndex, lonIndex, activeCount: 0, referenceCount: 0, support: 0, weightedEffect: 0, weightedShare: 0, shareSupport: 0, weightedLog2: 0, log2Support: 0, items: [], preview, patch: firstDefined(item, ["patch"], preview && preview.patch), area: firstDefined(item, ["area"], preview && preview.area) };
          groups.set(key, group);
        }
        const active = nonnegativeNumber(firstDefined(item, ["activeCount", "active_count", "observed", "count"], 0));
        const reference = nonnegativeNumber(firstDefined(item, ["referenceCount", "reference_count", "reference", "expected"], 0));
        const support = Math.max(1, active + reference);
        group.activeCount += active;
        group.referenceCount += reference;
        group.support += support;
        group.weightedEffect += comparativeEffect(item, config.valueKeys) * support;
        const reportShare = firstDefined(item, ["sourceBalancedShare", "source_balanced_share", "reportShare", "report_share", "activeShare", "active_share"], null);
        if (reportShare != null && Number.isFinite(Number(reportShare))) {
          group.weightedShare += Number(reportShare) * support;
          group.shareSupport += support;
        }
        const log2 = firstDefined(item, ["log2Enrichment", "log2_enrichment"], null);
        if (log2 != null && Number.isFinite(Number(log2))) {
          group.weightedLog2 += Number(log2) * support;
          group.log2Support += support;
        }
        group.items.push(item);
      });
      const cells = Array.from(groups.values()).map(function (group) {
        const effect = group.support ? group.weightedEffect / group.support : 0;
        const activeShare = group.activeCount / Math.max(1, summary.activeCount);
        const referenceShare = group.referenceCount / Math.max(1, summary.referenceCount);
        const evidenceItem = group.items.find(function (item) { return !suppressionReason(item); }) || group.items[0] || {};
        return Object.assign(group, {
          effect: Number.isFinite(effect) && effect !== 0 ? effect : activeShare - referenceShare,
          reportShare: group.shareSupport ? group.weightedShare / group.shareSupport : activeShare,
          log2Enrichment: group.log2Support ? group.weightedLog2 / group.log2Support : null,
          adjustedActiveShare: wholeCorpus ? null : firstDefined(evidenceItem, ["adjustedActiveShare", "adjusted_active_share"], null),
          adjustedReferenceShare: wholeCorpus ? null : firstDefined(evidenceItem, ["adjustedReferenceShare", "adjusted_reference_share"], null),
          adjustedDifference: wholeCorpus ? null : firstDefined(evidenceItem, ["adjustedDifference", "adjusted_difference"], null),
          differenceInterval: firstDefined(evidenceItem, ["differenceInterval", "difference_interval", "effectInterval", "effect_interval", "interval"], null),
          qValue: firstDefined(evidenceItem, ["qValue", "q_value", "q"], null),
          commonSupportRate: firstDefined(evidenceItem, ["commonSupportRate", "common_support_rate"], null),
          supportedActiveN: firstDefined(evidenceItem, ["supportedActiveN", "supported_active_n"], null),
          supportedReferenceN: firstDefined(evidenceItem, ["supportedReferenceN", "supported_reference_n"], null),
          suppressed: group.items.every(function (item) { return !inferenceEligible(item); }),
          suppressionReason: group.items.map(suppressionReason).filter(Boolean)[0] || "",
          preview: wholeCorpus && (group.preview || group.patch || group.area) ? Object.assign({}, group.preview || {}, {
            comparison: formatCount(group.activeCount) + " reports in this grid cell; internal structure has no reference cohort",
          }) : group.preview,
        });
      }).filter(function (cell) {
        return cell.activeCount > 0 || cell.referenceCount > 0 || cell.suppressed;
      });
      if (!cells.length) {
        this._clear(container);
        container.appendChild(this._element("p", "analysis-chart-empty", "No non-empty equal-area cells meet the display policy."));
        return;
      }
      const modeControls = this._element("div", "analysis-map-mode-controls");
      modeControls.setAttribute("role", "group");
      modeControls.setAttribute("aria-label", "Geography map measure");
      const modeDefinitions = [
        { key: "difference", label: this.currentAnalysisMode === "whole_corpus_structure" ? "Report share" : "Adjusted difference" },
        { key: "log2", label: "Log₂ enrichment", available: !wholeCorpus },
        { key: "count", label: this.currentAnalysisMode === "whole_corpus_structure" ? "Report counts" : "Active counts" },
      ].filter(function (mode) { return mode.available !== false; });
      const modeButtons = [];
      modeDefinitions.forEach((mode, index) => {
        const button = this._element("button", "secondary-button analysis-map-mode-button", mode.label);
        button.type = "button";
        button.setAttribute("aria-pressed", index === 0 ? "true" : "false");
        modeButtons.push({ button, mode });
        modeControls.appendChild(button);
      });
      container.appendChild(modeControls);
      const mapLegend = this._element("p", "analysis-map-legend");
      container.appendChild(mapLegend);
      const facets = this._element("div", "analysis-equal-area-facets");
      const mapMarks = [];
      const world = this._getWorldReferenceData();
      const worldFeatures = asArray(world && world.features).filter(function (feature) {
        return feature && feature.geometry && (feature.geometry.type === "Polygon" || feature.geometry.type === "MultiPolygon")
          && Array.isArray(feature.geometry.coordinates) && feature.geometry.coordinates.length;
      });
      let equalAreaLandPaths = world ? this.worldEqualAreaPathCache.get(world) : null;
      if (!equalAreaLandPaths && worldFeatures.length) {
        equalAreaLandPaths = worldFeatures.map(function (feature, index) {
          return {
            name: cleanText(firstDefined(feature.properties || {}, ["name", "NAME", "admin", "ADMIN"], "Land " + (index + 1))),
            path: projectedEqualAreaGeometryPath(feature.geometry, 600, 300),
          };
        }).filter(function (entry) { return entry.path; });
        this.worldEqualAreaPathCache.set(world, equalAreaLandPaths);
      }
      const coordinateClassRank = function (value) {
        const label = cleanText(value).toLowerCase();
        if (label.indexOf("source") !== -1 || label.indexOf("exact") !== -1) return 0;
        if (label.indexOf("general") !== -1 || label.indexOf("rough") !== -1) return 1;
        return 2;
      };
      const classes = Array.from(new Set(cells.map(function (cell) { return cell.coordinateClass; }))).sort(function (left, right) {
        return coordinateClassRank(left) - coordinateClassRank(right) || left.localeCompare(right);
      });
      classes.forEach((coordinateClass, facetIndex) => {
        const facet = this._element("section", "analysis-equal-area-facet");
        facet.appendChild(this._element("h5", "", coordinateClass.replace(/_/g, " ")));
        const svg = this._svgElement("svg", { class: "analysis-equal-area-svg", viewBox: "-42 -20 684 375", role: "img", "aria-label": coordinateClass + " equal-area world grid with land silhouette, latitude bands, and longitude meridians" });
        const defs = this._svgElement("defs", {});
        const patternId = "analysis-map-hatch-" + facetIndex;
        const pattern = this._svgElement("pattern", { id: patternId, width: 8, height: 8, patternUnits: "userSpaceOnUse", patternTransform: "rotate(45)" });
        pattern.appendChild(this._svgElement("line", { x1: 0, y1: 0, x2: 0, y2: 8, stroke: "currentColor", "stroke-width": 2, opacity: 0.35 }));
        defs.appendChild(pattern);
        svg.appendChild(defs);
        const contextLayer = this._svgElement("g", { class: "analysis-equal-area-context", "aria-hidden": "true" });
        (equalAreaLandPaths || []).forEach((entry) => {
          contextLayer.appendChild(this._svgElement("path", { class: "analysis-equal-area-land", d: entry.path, "data-land-name": entry.name }));
        });
        for (let longitudeIndex = 0; longitudeIndex <= 12; longitudeIndex += 1) {
          const x = longitudeIndex * 50;
          contextLayer.appendChild(this._svgElement("line", { class: "analysis-equal-area-graticule", x1: x, y1: 0, x2: x, y2: 300 }));
          if (longitudeIndex % 2 === 0) {
            const longitude = -180 + (longitudeIndex * 30);
            const label = this._svgElement("text", { class: "analysis-equal-area-axis-label analysis-equal-area-longitude-label", x, y: 320, "text-anchor": "middle" });
            label.textContent = longitude === 0 ? "0°" : Math.abs(longitude) + "°" + (longitude < 0 ? "W" : "E");
            contextLayer.appendChild(label);
          }
        }
        for (let latitudeIndex = 0; latitudeIndex <= 6; latitudeIndex += 1) {
          const y = (6 - latitudeIndex) * 50;
          contextLayer.appendChild(this._svgElement("line", { class: "analysis-equal-area-graticule", x1: 0, y1: y, x2: 600, y2: y }));
          const latitudeBoundary = latitudeIndex === 0 ? -90 : (latitudeIndex === 6 ? 90 : Math.asin(-1 + (latitudeIndex / 3)) * 180 / Math.PI);
          const label = this._svgElement("text", { class: "analysis-equal-area-axis-label analysis-equal-area-latitude-label", x: -8, y: y + 3, "text-anchor": "end" });
          label.textContent = Math.abs(latitudeBoundary).toFixed(latitudeIndex === 0 || latitudeIndex === 6 ? 0 : 1) + "°" + (latitudeBoundary < 0 ? "S" : (latitudeBoundary > 0 ? "N" : ""));
          contextLayer.appendChild(label);
        }
        const longitudeTitle = this._svgElement("text", { class: "analysis-equal-area-axis-title", x: 300, y: 340, "text-anchor": "middle" });
        longitudeTitle.textContent = "Longitude";
        contextLayer.appendChild(longitudeTitle);
        const latitudeTitle = this._svgElement("text", { class: "analysis-equal-area-axis-title", x: -35, y: 150, transform: "rotate(-90 -35 150)", "text-anchor": "middle" });
        latitudeTitle.textContent = "Equal-area latitude";
        contextLayer.appendChild(latitudeTitle);
        svg.appendChild(contextLayer);
        cells.filter(function (cell) { return cell.coordinateClass === coordinateClass; }).forEach((cell) => {
          const rect = this._svgElement("rect", {
            x: cell.lonIndex * 50,
            y: (5 - cell.latIndex) * 50,
            width: 50,
            height: 50,
            class: "analysis-map-cell " + (cell.suppressed ? "is-low-support" : "is-qualified"),
          });
          const bounds = equalAreaBandBounds(cell.latIndex, cell.lonIndex, 6, 12);
          const label = "Latitude " + coordinateRangeLabel(bounds.south, bounds.north)
            + ", longitude " + coordinateRangeLabel(bounds.west, bounds.east);
          rect.setAttribute("aria-label", label);
          rect.appendChild(this._svgElement("title", {}));
          rect.children[0].textContent = label;
          if (cell.patch || cell.area) {
            this._activatePreview(rect, cell, label, summary, "area");
          }
          mapMarks.push({ rect, cell, patternId, label });
          svg.appendChild(rect);
        });
        const outlineLayer = this._svgElement("g", { class: "analysis-equal-area-land-outline-layer", "aria-hidden": "true" });
        (equalAreaLandPaths || []).forEach((entry) => {
          outlineLayer.appendChild(this._svgElement("path", { class: "analysis-equal-area-land-outline", d: entry.path }));
        });
        svg.appendChild(outlineLayer);
        facet.appendChild(svg);
        facets.appendChild(facet);
      });
      container.appendChild(facets);
      const updateMapMode = (modeKey) => {
        const modeValue = (cell) => {
          if (modeKey === "count") return cell.activeCount;
          if (modeKey === "log2") return Number.isFinite(Number(cell.log2Enrichment)) ? Number(cell.log2Enrichment) : 0;
          return this.currentAnalysisMode === "whole_corpus_structure" ? cell.reportShare : cell.effect;
        };
        const maximum = Math.max(Number.EPSILON, ...cells.filter((cell) => {
          return modeKey === "count" || this.currentAnalysisMode === "whole_corpus_structure" || !cell.suppressed;
        }).map(function (cell) { return Math.abs(modeValue(cell)); }));
        modeButtons.forEach(function (entry) { entry.button.setAttribute("aria-pressed", entry.mode.key === modeKey ? "true" : "false"); });
        mapLegend.textContent = modeKey === "count"
          ? "Report counts · darker cells contain more matched reports · inferential support does not hide descriptive density"
          : (modeKey === "log2"
            ? "Log₂ active/reference enrichment · blue above reference · amber below reference · hatched insufficient support"
            : (this.currentAnalysisMode === "whole_corpus_structure"
              ? "Source-balanced report share · darker cells contain a larger share of matched reports"
              : "Signed adjusted share difference · blue above reference · amber below reference · diagonal overlay marks limited inferential support"));
        mapMarks.forEach((mark) => {
          const valueNumber = modeValue(mark.cell);
          if (mark.cell.suppressed && modeKey !== "count" && this.currentAnalysisMode !== "whole_corpus_structure") {
            mark.rect.setAttribute("fill", "url(#" + mark.patternId + ")");
            mark.rect.setAttribute("fill-opacity", "1");
          } else {
            mark.rect.setAttribute("fill", modeKey !== "count" && valueNumber < 0 ? "#d18a34" : "#168aad");
            mark.rect.setAttribute("fill-opacity", String(0.16 + (0.78 * Math.min(1, Math.abs(valueNumber) / maximum))));
          }
          const valueLabel = modeKey === "count"
            ? formatCount(valueNumber) + " reports"
            : (modeKey === "log2" ? formatDecimal(valueNumber, 2) + " log2 enrichment" : formatSignedPercent(valueNumber));
          const accessible = this.currentAnalysisMode === "whole_corpus_structure"
            ? mark.label + ": " + valueLabel + "; report n=" + formatCount(mark.cell.activeCount) + "; internal structure has no reference cohort"
            : mark.label + ": " + valueLabel + "; active n=" + formatCount(mark.cell.activeCount) + ", reference n=" + formatCount(mark.cell.referenceCount);
          mark.rect.setAttribute("aria-label", accessible);
          if (mark.rect.children && mark.rect.children[0]) mark.rect.children[0].textContent = accessible;
        });
      };
      modeButtons.forEach((entry) => entry.button.addEventListener("click", function () { updateMapMode(entry.mode.key); }));
      const comparatorUnavailable = this.currentComparisonState === "unavailable_no_reference"
        || this.currentComparisonState === "unavailable_self_comparison";
      const defaultMode = this.currentAnalysisMode === "whole_corpus_structure"
        ? "difference"
        : (comparatorUnavailable || cells.every(function (cell) { return cell.suppressed; }) ? "count" : "difference");
      updateMapMode(defaultMode);
      if (wholeCorpus) {
        this._appendDataTable(container, "Equal-area whole-corpus geography evidence", ["Coordinate class", "Latitude", "Longitude", "Source-balanced report share", "Report n", "Status"], cells.map(function (cell) {
          const bounds = equalAreaBandBounds(cell.latIndex, cell.lonIndex, 6, 12);
          return [cell.coordinateClass, coordinateRangeLabel(bounds.south, bounds.north), coordinateRangeLabel(bounds.west, bounds.east), formatPercent(cell.reportShare), formatCount(cell.activeCount), cell.suppressed ? "Descriptive estimate" : "Qualified"];
        }));
      } else {
        this._appendDataTable(container, "Equal-area geography evidence", ["Coordinate class", "Latitude", "Longitude", "Adjusted difference", "Log2 enrichment", "Active n", "Reference n", "Status"], cells.map(function (cell) {
          const bounds = equalAreaBandBounds(cell.latIndex, cell.lonIndex, 6, 12);
          return [cell.coordinateClass, coordinateRangeLabel(bounds.south, bounds.north), coordinateRangeLabel(bounds.west, bounds.east), formatSignedPercent(cell.effect), cell.log2Enrichment == null ? "—" : formatDecimal(cell.log2Enrichment, 2), formatCount(cell.activeCount), formatCount(cell.referenceCount), cell.suppressed ? cell.suppressionReason : "Qualified"];
        }));
      }
    }

    _renderEvidenceGroupSelector(chartId, groupsValue, summary, options) {
      const config = options || {};
      const groups = asArray(groupsValue).filter(function (group) { return isObject(group); });
      if (!groups.length) {
        this._renderEvidenceList(chartId, [], summary, config);
        return;
      }
      const renderGroup = (indexValue) => {
        const index = Math.max(0, Math.min(groups.length - 1, Number(indexValue) || 0));
        const group = groups[index];
        const groupValue = isObject(group.value) ? group.value : {};
        const reasons = firstDefined(groupValue, ["suppressionReasons", "suppression_reasons"], []);
        const emptyReason = (Array.isArray(reasons) ? reasons : [reasons]).map(humanizeEvidenceReason).filter(Boolean).join("; ");
        const laneStatus = cleanText(firstDefined(groupValue, ["status"], "")).toLowerCase();
        const laneReasons = (Array.isArray(reasons) ? reasons : [reasons]).map(humanizeEvidenceReason).filter(Boolean);
        const laneSuppressed = laneStatus === "suppressed" || laneStatus === "not_estimable" || laneStatus === "not estimable";
        const displayItems = asArray(group.items).map(function (item) {
          if (!isObject(item) || (!laneSuppressed && laneStatus !== "descriptive_only")) return item;
          const ownReasonsValue = firstDefined(item, ["suppressionReasons", "suppression_reasons"], []);
          const ownReasons = (Array.isArray(ownReasonsValue) ? ownReasonsValue : [ownReasonsValue]).map(humanizeEvidenceReason).filter(Boolean);
          return Object.assign({}, item, {
            status: laneSuppressed ? laneStatus : cleanText(firstDefined(item, ["status"], laneStatus)),
            suppressionReasons: Array.from(new Set(ownReasons.concat(laneReasons))),
          });
        });
        this._renderEvidenceList(chartId, displayItems, summary, Object.assign({}, config, {
          emptyMessage: emptyReason || config.emptyMessage,
        }));
        const container = this.document.getElementById(chartId);
        if (!container) return;
        const controls = this._element("div", "analysis-evidence-view-controls");
        if (groups.length > 1) {
          const label = this._element("label", "field compact-field");
          label.appendChild(this._element("span", "", "Evidence view"));
          const select = this._element("select", "analysis-evidence-view-select");
          select.setAttribute("aria-label", "Evidence view");
          groups.forEach((candidate, candidateIndex) => {
            const option = this._element("option", "", candidate.label);
            option.value = String(candidateIndex);
            select.appendChild(option);
          });
          select.value = String(index);
          select.addEventListener("change", function () { renderGroup(select.value); });
          label.appendChild(select);
          controls.appendChild(label);
        }
        const status = cleanText(firstDefined(groupValue, ["status"], "not estimable")).replace(/_/g, " ");
        const supportedN = firstDefined(groupValue, ["supportedActiveN", "supported_active_n", "supportedN", "supported_n"], null);
        const commonSupport = firstDefined(groupValue, ["commonSupportRate", "common_support_rate"], null);
        controls.appendChild(this._element(
          "p",
          "analysis-chart-policy",
          group.label + " · " + status
            + (supportedN == null ? "" : " · supported n=" + formatCount(supportedN))
            + (commonSupport == null ? "" : " · common support " + formatPercent(commonSupport))
            + (emptyReason ? " · " + emptyReason : "")
        ));
        if (typeof container.insertBefore === "function") container.insertBefore(controls, container.firstChild || null);
        else if (Array.isArray(container.children)) container.children.unshift(controls);
        else container.appendChild(controls);
      };
      renderGroup(0);
    }

    _renderCooccurrenceEvidence(chartId, value, summary, options) {
      const config = options || {};
      const source = isObject(value) ? value : {};
      const groups = [];
      const laneDefinitions = [
        { key: "crossSource", alias: "cross_source", label: "Cross-source" },
        { key: "sameSource", alias: "same_source", label: "Same-source" },
      ];
      const appendLaneGroups = function (laneSource, configurationLane) {
        laneDefinitions.forEach(function (lane) {
          firstArray(laneSource, [lane.key, lane.alias]).forEach(function (windowResult, windowIndex) {
          const windowMetadata = isObject(windowResult.window) ? windowResult.window : {};
          const windowLabel = cleanText(firstDefined(windowResult, ["label", "windowLabel", "window_label"], firstDefined(windowMetadata, ["label", "windowLabel", "window_label"], "Window " + (windowIndex + 1))));
          const groupLabel = (configurationLane ? "Formation configurations · " : "") + lane.label + " · " + windowLabel
            + (lane.key === "crossSource" && windowMetadata.primary === true ? " · primary" : " · sensitivity");
          const status = cleanText(firstDefined(windowResult, ["status"], ""));
          const reasons = firstDefined(windowResult, ["suppressionReasons", "suppression_reasons"], []);
          const completeItems = firstArray(windowResult, ["cells", "categories", "effects", "findings"]).map(function (item, index) {
            const left = cleanText(firstDefined(item, ["row", "craftA", "craft_a", "sourceCategory", "source_category"], ""));
            const right = cleanText(firstDefined(item, ["column", "craftB", "craft_b", "neighborCategory", "neighbor_category"], ""));
            return Object.assign({}, item, {
              label: cleanText(firstDefined(item, ["label", "name"], left && right ? left + " × " + right : "Pair " + (index + 1))),
              status: cleanText(firstDefined(item, ["status"], status)),
              suppressionReasons: firstDefined(item, ["suppressionReasons", "suppression_reasons"], reasons),
            });
          });
          const items = configurationLane ? completeItems : completeItems.filter(function (item) {
            const left = firstDefined(item, ["row", "craftA", "craft_a", "sourceCategory", "source_category"], "");
            const right = firstDefined(item, ["column", "craftB", "craft_b", "neighborCategory", "neighbor_category"], "");
            return !isDumbbellBarbellCraft(left) && !isDumbbellBarbellCraft(right)
              && !isFormationConfiguration(left) && !isFormationConfiguration(right);
          });
          const axisOrder = firstArray(windowResult, ["craftCategories", "craft_categories", "axisOrder", "axis_order"])
            .map(cleanText).filter(function (label) {
              return configurationLane || (!isDumbbellBarbellCraft(label) && !isFormationConfiguration(label));
            });
          groups.push({ label: groupLabel, value: windowResult, items, completeItems, axisOrder, configurationLane });
          });
        });
      };
      appendLaneGroups(source, false);
      const configurationSource = isObject(source.configuration) ? source.configuration : {};
      appendLaneGroups(configurationSource, true);
      if (!groups.length) {
        this._renderHeatmap(chartId, [], summary, { emptyMessage: config.emptyMessage });
        return;
      }
      const renderGroup = (indexValue) => {
        const index = Math.max(0, Math.min(groups.length - 1, Number(indexValue) || 0));
        const group = groups[index];
        this._renderHeatmap(chartId, group.items, summary, {
          caption: group.configurationLane ? "Directed Formation-configuration point co-occurrence" : (config.caption || "Directed point-based craft co-occurrence"),
          rowHeading: group.configurationLane ? "Focal configuration or craft" : "Focal craft",
          rowAxisKind: "category",
          columnAxisKind: "category",
          defaultKind: config.defaultKind || "filter",
          valueKeys: config.valueKeys || ["log2Enrichment", "log2_enrichment"],
          nullValue: 0,
          squareAxes: true,
          axisLimit: config.axisLimit,
          axisOrder: group.axisOrder,
          craftRows: true,
          craftColumns: true,
          effectOnly: true,
          inspectable: true,
          effectLabel: "Log2 observed/expected enrichment",
          completeData: group.completeItems,
          preserveRawCompleteLabels: !group.configurationLane,
          emptyMessage: config.emptyMessage,
        });
        const container = this.document.getElementById(chartId);
        if (!container) return;
        container.classList.toggle("shows-formation-configuration", Boolean(group.configurationLane));
        const controls = this._element("div", "analysis-evidence-view-controls");
        const label = this._element("label", "field compact-field");
        label.appendChild(this._element("span", "", "Evidence lane and window"));
        const select = this._element("select", "analysis-evidence-view-select");
        select.setAttribute("aria-label", "Craft co-occurrence lane and distance-time window");
        groups.forEach((candidate, candidateIndex) => {
          const option = this._element("option", "", candidate.label);
          option.value = String(candidateIndex);
          select.appendChild(option);
        });
        select.value = String(index);
        select.addEventListener("change", function () { renderGroup(select.value); });
        label.appendChild(select);
        controls.appendChild(label);
        const laneStatus = cleanText(firstDefined(group.value, ["status"], "descriptive")).replace(/_/g, " ");
        const configurationWarnings = group.configurationLane
          ? asArray(firstDefined(configurationSource, ["policyWarnings", "policy_warnings"], [])).map(cleanText).filter(Boolean).join(" ")
          : "Dumbbell/barbell craft is omitted from this default matrix and is never used as a configuration label; its raw category remains in the expanded table and evidence export.";
        controls.appendChild(this._element("p", "analysis-chart-policy", group.label + " · " + laneStatus
          + ". Rows are focal observations; columns are neighboring observations, so direction is preserved. " + configurationWarnings));
        if (typeof container.insertBefore === "function") container.insertBefore(controls, container.firstChild || null);
        else if (Array.isArray(container.children)) {
          controls.parentNode = container;
          container.children.unshift(controls);
        } else container.appendChild(controls);
      };
      renderGroup(0);
    }

    _renderContextAssociations(chartId, value, summary, options) {
      const config = options || {};
      const source = isObject(value) ? value : {};
      const laneLabels = {
        crop_bounded: "Bounded crop markers · field candidates",
        crop_locality: "Crop locality markers",
        animal_public_marker: "Animal public markers · uncertainty lane",
      };
      const allowedLanes = new Set(asArray(config.allowedLanes).map(cleanText).filter(Boolean));
      const axisLabels = {
        "0_25_km": "0–25 km", "25_50_km": "25–50 km", "50_100_km": "50–100 km", "100_250_km": "100–250 km",
        same_day: "Same day", "1_3_days": "1–3 days", "4_7_days": "4–7 days", "8_30_days": "8–30 days",
      };
      const lanes = firstArray(source, ["lanes", "evidenceLanes", "evidence_lanes"]).map(function (lane, index) {
        const laneKey = cleanText(firstDefined(lane, ["lane", "key", "id"], "lane_" + (index + 1)));
        const cells = firstArray(lane, ["cells", "matrix", "effects"]).map(function (cell) {
          const rowKey = cleanText(firstDefined(cell, ["row", "distanceRing", "distance_ring"], ""));
          const columnKey = cleanText(firstDefined(cell, ["column", "dayLagBand", "day_lag_band"], ""));
          return Object.assign({}, cell, {
            row: axisLabels[rowKey] || rowKey.replace(/_/g, " "),
            column: axisLabels[columnKey] || columnKey.replace(/_/g, " "),
            observedCount: firstDefined(cell, ["observedCount", "observed_count", "observedClusterCount", "observed_cluster_count"], null),
            expectedCount: firstDefined(cell, ["expectedCount", "expected_count", "expectedClusterCount", "expected_cluster_count"], null),
            suppressionReasons: firstDefined(cell, ["suppressionReasons", "suppression_reasons", "supportReasons", "support_reasons"], []),
          });
        });
        return { key: laneKey, label: laneLabels[laneKey] || laneKey.replace(/_/g, " "), lane, cells };
      }).filter(function (lane) {
        return lane.cells.length && (!allowedLanes.size || allowedLanes.has(lane.key));
      });
      if (!lanes.length) {
        this._renderHeatmap(chartId, [], summary, { emptyMessage: config.emptyMessage || "Context-marker neighborhood evidence has not loaded." });
        return;
      }
      const renderLane = (indexValue) => {
        const index = Math.max(0, Math.min(lanes.length - 1, Number(indexValue) || 0));
        const selected = lanes[index];
        const loadedNoMatchMessage = "Evidence artifact loaded. No eligible report-point neighborhoods match the active date window and filters for this lane.";
        this._renderHeatmap(chartId, selected.cells, summary, {
          caption: selected.label + " distance-ring by day-lag evidence",
          rowHeading: "Distance ring",
          rowAxisKind: "category",
          rowAxisOrder: ["0–25 km", "25–50 km", "50–100 km", "100–250 km"],
          columnAxisKind: "category",
          columnAxisOrder: ["Same day", "1–3 days", "4–7 days", "8–30 days"],
          valueKeys: ["log2Enrichment", "log2_enrichment"],
          effectOnly: true,
          inspectable: true,
          effectLabel: "Log2 observed/expected enrichment",
          emptyMessage: loadedNoMatchMessage,
        });
        const container = this.document.getElementById(chartId);
        if (!container) return;
        const controls = this._element("div", "analysis-evidence-view-controls");
        const label = this._element("label", "field compact-field");
        label.appendChild(this._element("span", "", "Context evidence lane"));
        const select = this._element("select", "analysis-evidence-view-select");
        select.setAttribute("aria-label", "Context evidence lane");
        lanes.forEach((lane, laneIndex) => {
          const option = this._element("option", "", lane.label);
          option.value = String(laneIndex);
          select.appendChild(option);
        });
        select.value = String(index);
        select.addEventListener("change", function () { renderLane(select.value); });
        label.appendChild(select);
        controls.appendChild(label);
        const policy = asArray(firstDefined(selected.lane, ["policyWarnings", "policy_warnings"], [])).join(" ");
        const clusterN = firstDefined(selected.lane, ["contextClusterN", "context_cluster_n"], null);
        const observedPairN = firstDefined(selected.lane, ["observedPairN", "observed_pair_n"], null);
        const excludedPairN = firstDefined(selected.lane, ["excludedObservedPairN", "excluded_observed_pair_n"], null);
        const uncertaintyCounts = firstDefined(selected.lane, ["uncertaintyCounts", "uncertainty_counts"], {});
        const metrics = this._element("dl", "analysis-context-lane-metrics");
        [
          ["Context clusters", clusterN],
          ["Observed pairs", observedPairN],
          [selected.key === "animal_public_marker" ? "Contamination exclusions" : "Origin exclusions", excludedPairN],
        ].forEach((metric) => {
          if (metric[1] == null) return;
          const item = this._element("div");
          item.appendChild(this._element("dt", "", metric[0]));
          item.appendChild(this._element("dd", "", formatCount(metric[1])));
          metrics.appendChild(item);
        });
        if (isObject(uncertaintyCounts)) {
          Object.keys(uncertaintyCounts).sort().forEach((key) => {
            const item = this._element("div");
            item.appendChild(this._element("dt", "", cleanText(key).replace(/_/g, " ")));
            item.appendChild(this._element("dd", "", formatCount(uncertaintyCounts[key])));
            metrics.appendChild(item);
          });
        }
        if (metrics.children && metrics.children.length) controls.appendChild(metrics);
        const audit = selected.key === "animal_public_marker" && excludedPairN != null
          ? " Contamination audit: " + formatCount(excludedPairN) + " originating-UFO or originating-publisher pairs were excluded from the independent lane."
          : "";
        controls.appendChild(this._element("p", "analysis-chart-policy", selected.label + (clusterN == null ? "" : " · " + formatCount(clusterN) + " unique location-date clusters") + (policy ? ". " + policy : "") + audit));
        if (typeof container.insertBefore === "function") container.insertBefore(controls, container.firstChild || null);
        else if (Array.isArray(container.children)) {
          controls.parentNode = container;
          container.children.unshift(controls);
        } else container.appendChild(controls);
      };
      renderLane(0);
    }

    _renderContextCategoryAssociations(chartId, cardId, value, summary) {
      const source = isObject(value) ? value : {};
      let groups = firstArray(source, ["categoryHeatmaps", "category_heatmaps", "categoryAssociations", "category_associations", "secondary"]);
      if (!groups.length) {
        const laneLabels = {
          crop_bounded: "Craft by bounded-marker crop morphology",
          crop_locality: "Craft by crop-locality morphology",
          animal_public_marker: "Craft by pooled animal species",
        };
        groups = firstArray(source, ["lanes", "evidenceLanes", "evidence_lanes"]).map(function (lane, index) {
          const association = firstDefined(lane, ["featureAssociation", "feature_association"], null);
          if (!isObject(association) || !matrixItems(association).length) return null;
          const laneKey = cleanText(firstDefined(lane, ["lane", "key", "id"], "lane_" + (index + 1)));
          return Object.assign({}, association, {
            label: laneLabels[laneKey] || ("Craft by " + laneKey.replace(/_/g, " ")),
            lane: laneKey,
          });
        }).filter(Boolean);
      }
      const card = this.document.getElementById(cardId);
      if (!groups.length) {
        if (card) card.hidden = true;
        this._clear(this.document.getElementById(chartId));
        return;
      }
      if (card) card.hidden = false;
      const renderGroup = (indexValue) => {
        const index = Math.max(0, Math.min(groups.length - 1, Number(indexValue) || 0));
        const group = groups[index];
        const labelText = cleanText(firstDefined(group, ["label", "name"], "Craft by context feature"));
        this._renderHeatmap(chartId, firstDefined(group, ["cells", "matrix", "effects"], group), summary, {
          caption: labelText,
          rowHeading: "Craft",
          rowAxisKind: "category",
          columnAxisKind: "category",
          valueKeys: ["log2Enrichment", "log2_enrichment", "adjustedResidual", "adjusted_residual", "standardizedResidual", "standardized_residual"],
          craftRows: true,
          effectOnly: true,
          inspectable: true,
        });
        const container = this.document.getElementById(chartId);
        if (!container) return;
        const controls = this._element("div", "analysis-evidence-view-controls");
        const label = this._element("label", "field compact-field");
        label.appendChild(this._element("span", "", "Context feature lane"));
        const select = this._element("select", "analysis-evidence-view-select");
        select.setAttribute("aria-label", "Context feature lane");
        groups.forEach(function (candidate, groupIndex) {
          const option = documentSafeElement(container.ownerDocument, "option", "", cleanText(firstDefined(candidate, ["label", "name"], "Context feature " + (groupIndex + 1))));
          option.value = String(groupIndex);
          select.appendChild(option);
        });
        select.value = String(index);
        select.addEventListener("change", function () { renderGroup(select.value); });
        label.appendChild(select);
        controls.appendChild(label);
        const poolingThreshold = firstDefined(group, ["poolingThreshold", "pooling_threshold"], null);
        if (poolingThreshold != null) {
          controls.appendChild(this._element("p", "analysis-chart-policy", "Sparse context features are pooled below N=" + formatCount(poolingThreshold) + "; the complete unpooled table remains available below."));
        }
        if (typeof container.insertBefore === "function") container.insertBefore(controls, container.firstChild || null);
        else container.appendChild(controls);

        const complete = firstDefined(group, ["completeAccessibleTable", "complete_accessible_table"], null);
        const completeCells = matrixItems(complete);
        if (completeCells.length) {
          this._appendLazyDataTable(container, labelText + " complete unpooled values", ["Craft", "Context feature", "Observed", "Expected", "Log2 enrichment"], completeCells.map(function (cell) {
            return [
              cleanText(firstDefined(cell, ["row", "rowLabel"], "Unknown")),
              cleanText(firstDefined(cell, ["column", "columnLabel"], "Unknown")),
              formatCount(firstDefined(cell, ["observedClusterCount", "observedCount", "observed"], 0)),
              formatDecimal(firstDefined(cell, ["expectedClusterCount", "expectedCount", "expected"], 0), 2),
              formatDecimal(firstDefined(cell, ["log2Enrichment", "log2_enrichment"], 0), 2),
            ];
          }));
        }
      };
      renderGroup(0);
    }

    _renderFacilityEvidence(chartId, value, summary, options) {
      const config = options || {};
      const source = isObject(value) ? value : {};
      const catalogSummary = isObject(firstDefined(source, ["catalogSummary", "catalog_summary"], null))
        ? firstDefined(source, ["catalogSummary", "catalog_summary"], {})
        : {};
      const inferentialFacilityN = Number(firstDefined(
        source,
        ["inferentialFacilityN", "inferential_facility_n"],
        firstDefined(catalogSummary, ["inferentialEligibleN", "inferential_eligible_n"], 0)
      )) || 0;
      const facilityCatalogN = Number(firstDefined(
        catalogSummary,
        ["totalN", "total_n"],
        firstDefined(source, ["facilityCatalogN", "facility_catalog_n", "totalFacilityN", "total_facility_n"], 0)
      )) || 0;
      const descriptiveOnlyFacilityN = Number(firstDefined(
        catalogSummary,
        ["descriptiveOnlyN", "descriptive_only_n"],
        Math.max(0, facilityCatalogN - inferentialFacilityN)
      )) || 0;
      const claimedFacilityN = Number(firstDefined(source, ["claimedFacilityN", "claimed_facility_n"], 0)) || 0;
      const policyWarnings = firstArray(source, ["policyWarnings", "policy_warnings"]);
      const coverageLimitations = firstArray(source, ["coverageLimitations", "coverage_limitations"])
        .concat(firstArray(catalogSummary, ["coverageLimitations", "coverage_limitations"]));
      const coverageWarning = policyWarnings.find(function (warning) {
        return /Northern Europe|New Zealand/i.test(cleanText(warning));
      }) || (coverageLimitations.some(function (warning) {
        return /northern[_\s-]*europe|new[_\s-]*zealand/i.test(cleanText(warning));
      })
        ? "Research/test-site coverage is strongly limited to the Northern Europe and New Zealand supplements."
        : "Facility coverage varies substantially by region; interpret comparisons only within documented coverage.");
      const appendFacilityScope = (container) => {
        if (!container) return;
        const scope = this._element("section", "analysis-readiness-item analysis-facility-scope");
        scope.setAttribute("aria-label", "Facility evidence scope");
        scope.appendChild(this._element("strong", "", "Facility evidence scope"));
        scope.appendChild(this._element(
          "p",
          "",
          "The inferential lane uses a qualified subset of the facility catalog. Every catalog marker remains available descriptively, while claimed UFO sites never enter inference."
        ));
        const metrics = this._element("dl", "analysis-readiness-metrics");
        [
          ["Qualified for inference", inferentialFacilityN],
          ["Full catalog shown descriptively", facilityCatalogN],
          ["Descriptive-only markers", descriptiveOnlyFacilityN],
          ["Claimed UFO sites — descriptive only", claimedFacilityN],
        ].forEach((entry) => {
          const metric = this._element("div", "");
          metric.appendChild(this._element("dt", "", entry[0]));
          metric.appendChild(this._element("dd", "", formatCount(entry[1])));
          metrics.appendChild(metric);
        });
        scope.appendChild(metrics);
        scope.appendChild(this._element("p", "analysis-chart-policy", cleanText(coverageWarning)));
        if (typeof container.insertBefore === "function") container.insertBefore(scope, container.firstChild || null);
        else if (Array.isArray(container.children)) {
          scope.parentNode = container;
          container.children.unshift(scope);
        } else container.appendChild(scope);
      };
      const groups = [];
      const primary = isObject(source.primary) ? source.primary : source;
      groups.push({ label: "Temporally active · 25 km vs 100–250 km · primary", value: primary, items: firstArray(primary, ["cells", "categories", "effects", "findings"]) });
      const negative = firstDefined(source, ["inactiveNegativeControl", "inactive_negative_control"], null);
      if (isObject(negative)) groups.push({ label: "Inactive at event · negative control", value: negative, items: firstArray(negative, ["cells", "categories", "effects", "findings"]) });
      firstArray(source, ["sensitivity", "sensitivityViews", "sensitivity_views"]).forEach(function (lane, index) {
        const radius = firstDefined(lane, ["nearRadiusKm", "near_radius_km"], [10, 50, 100][index]);
        groups.push({ label: formatDecimal(radius, 0) + " km active-facility radius · sensitivity", value: lane, items: firstArray(lane, ["cells", "categories", "effects", "findings"]) });
      });
      const nonemptyGroups = groups.filter(function (group) { return group.items.length; });
      if (!nonemptyGroups.length) {
        this._renderForestPlot(chartId, [], summary, { emptyMessage: config.emptyMessage });
        appendFacilityScope(this.document.getElementById(chartId));
        return;
      }
      const renderGroup = (indexValue) => {
        const index = Math.max(0, Math.min(nonemptyGroups.length - 1, Number(indexValue) || 0));
        const group = nonemptyGroups[index];
        const laneStatus = cleanText(firstDefined(group.value, ["status"], "")).toLowerCase();
        const laneReasonValue = firstDefined(group.value, ["suppressionReasons", "suppression_reasons"], []);
        const laneReasons = Array.isArray(laneReasonValue) ? laneReasonValue : [laneReasonValue];
        const laneLimited = ["suppressed", "not_estimable", "not estimable", "descriptive_only"].indexOf(laneStatus) !== -1;
        const displayItems = group.items.map(function (item) {
          if (!laneLimited) return item;
          const ownReasonValue = firstDefined(item, ["suppressionReasons", "suppression_reasons"], []);
          const ownReasons = Array.isArray(ownReasonValue) ? ownReasonValue : [ownReasonValue];
          return Object.assign({}, item, {
            inferenceEligible: false,
            suppressionReasons: Array.from(new Set(ownReasons.concat(laneReasons).filter(Boolean))),
          });
        });
        this._renderForestPlot(chartId, displayItems, summary, {
          caption: config.caption || "Facility-marker craft-composition effects",
          defaultKind: config.defaultKind || "filter",
          valueKeys: config.valueKeys || ["commonOddsRatio", "common_odds_ratio", "oddsRatio", "odds_ratio"],
          nullValue: 1,
          scale: "ratio",
          effectLabel: config.effectLabel || "Common odds ratio",
          primaryCountLabel: config.primaryCountLabel,
          comparisonCountLabel: config.comparisonCountLabel,
          primaryCountKeys: config.primaryCountKeys,
          comparisonCountKeys: config.comparisonCountKeys,
          limit: config.limit,
          emptyMessage: config.emptyMessage,
        });
        const container = this.document.getElementById(chartId);
        if (!container) return;
        const controls = this._element("div", "analysis-evidence-view-controls");
        const label = this._element("label", "field compact-field");
        label.appendChild(this._element("span", "", "Facility comparison"));
        const select = this._element("select", "analysis-evidence-view-select");
        select.setAttribute("aria-label", "Facility comparison and sensitivity view");
        nonemptyGroups.forEach((candidate, candidateIndex) => {
          const option = this._element("option", "", candidate.label);
          option.value = String(candidateIndex);
          select.appendChild(option);
        });
        select.value = String(index);
        select.addEventListener("change", function () { renderGroup(select.value); });
        label.appendChild(select);
        controls.appendChild(label);
        controls.appendChild(this._element("p", "analysis-chart-policy", "Distances are report-marker-to-facility-marker distances. Claimed UFO sites are excluded from inference."));
        if (typeof container.insertBefore === "function") container.insertBefore(controls, container.firstChild || null);
        else if (Array.isArray(container.children)) {
          controls.parentNode = container;
          container.children.unshift(controls);
        } else container.appendChild(controls);
        appendFacilityScope(container);
      };
      renderGroup(0);
    }

    _renderEvidenceList(chartId, value, summary, options) {
      const config = options || {};
      let source = Array.isArray(value) ? value : firstArray(value, ["findings", "effects", "comparisons", "rows", "cells"]);
      if (!source.length && isObject(value)) {
        const lanes = [
          { key: "crossSource", label: "Cross-source" },
          { key: "sameSource", label: "Same-source" },
        ];
        source = lanes.flatMap(function (lane, laneIndex) {
          return firstArray(value, [lane.key, lane.key === "crossSource" ? "cross_source" : "same_source"]).flatMap(function (windowResult, windowIndex) {
            const windowMetadata = isObject(windowResult.window) ? windowResult.window : {};
            const windowLabel = cleanText(firstDefined(
              windowResult,
              ["label", "windowLabel", "window_label"],
              firstDefined(windowMetadata, ["label", "windowLabel", "window_label"], "Window " + (windowIndex + 1))
            ));
            const windowStatus = cleanText(firstDefined(windowResult, ["status"], ""));
            const windowReasons = firstDefined(windowResult, ["suppressionReasons", "suppression_reasons"], []);
            return firstArray(windowResult, ["cells", "categories", "effects", "findings"]).map(function (item, cellIndex) {
              const left = cleanText(firstDefined(item, ["row", "craftA", "craft_a", "sourceCategory", "source_category"], ""));
              const right = cleanText(firstDefined(item, ["column", "craftB", "craft_b", "neighborCategory", "neighbor_category"], ""));
              return Object.assign({}, item, {
                label: cleanText(firstDefined(item, ["label", "name"], left && right ? left + " × " + right : "Pair " + (cellIndex + 1))) + " · " + lane.label + " · " + windowLabel,
                status: cleanText(firstDefined(item, ["status"], windowStatus)),
                suppressionReasons: firstDefined(item, ["suppressionReasons", "suppression_reasons"], windowReasons),
                _analysisLaneOrder: laneIndex,
                _analysisWindowOrder: windowMetadata.primary === true ? -1 : windowIndex,
              });
            });
          });
        });
      }
      source = source.slice().sort(function (left, right) {
        const leftLane = finiteNumber(left._analysisLaneOrder, 0);
        const rightLane = finiteNumber(right._analysisLaneOrder, 0);
        const leftWindow = finiteNumber(left._analysisWindowOrder, 0);
        const rightWindow = finiteNumber(right._analysisWindowOrder, 0);
        return leftLane - rightLane || leftWindow - rightWindow
          || Number(Boolean(suppressionReason(left))) - Number(Boolean(suppressionReason(right)))
          || conservativeEffectMagnitude(right, config.valueKeys, config.nullValue) - conservativeEffectMagnitude(left, config.valueKeys, config.nullValue)
          || Math.abs(comparativeEffect(right, config.valueKeys) - finiteNumber(config.nullValue, 0)) - Math.abs(comparativeEffect(left, config.valueKeys) - finiteNumber(config.nullValue, 0))
          || datumLabel(left, 0).localeCompare(datumLabel(right, 0));
      });
      const status = isObject(value) ? cleanText(firstDefined(value, ["status", "evidenceStatus", "evidence_status"], "")) : "";
      const reason = isObject(value) ? cleanText(firstDefined(value, ["reason", "suppressionReason", "suppression_reason", "message"], "")) : "";
      const container = this._prepareChart(chartId, source, summary, reason || config.emptyMessage || (status ? "Spatial evidence is " + status.replace(/_/g, " ") + "." : "Spatial evidence has not been computed for this cohort."));
      if (!container) return;
      const list = this._element("div", "analysis-evidence-list");
      source.slice(0, 24).forEach((item, index) => {
        const card = this._element("article", "analysis-evidence-item");
        card.appendChild(this._element("strong", "", datumLabel(item, index)));
        const effect = comparativeEffect(item, config.valueKeys);
        const interval = intervalBounds(item);
        const q = firstDefined(item, ["qValue", "q_value", "q"], null);
        const primaryCount = firstDefined(item, asArray(config.primaryCountKeys).concat(["activeCount", "active_count", "observedCount", "observed_count", "nearCount", "near_count", "observed", "count"]), null);
        const comparisonCount = firstDefined(item, asArray(config.comparisonCountKeys).concat(["referenceCount", "reference_count", "expectedCount", "expected_count", "comparisonCount", "comparison_count", "reference", "expected"]), null);
        const counts = cleanText(config.primaryCountLabel, "Active") + " n=" + formatCount(primaryCount)
          + " · " + cleanText(config.comparisonCountLabel, "Reference") + " n=" + formatCount(comparisonCount);
        const statistical = cleanText(config.effectLabel, "Effect") + " " + formatDecimal(effect, 3) + (interval ? " · 95% CI " + formatInterval(interval) : "")
          + (q == null ? "" : " · q=" + formatDecimal(q, 3));
        card.appendChild(this._element("p", "", counts + " · " + statistical));
        const itemReason = suppressionReason(item);
        const statusLabel = evidenceStatusLabel(item);
        if (itemReason || statusLabel !== "Qualified") card.appendChild(this._element("span", "analysis-readiness-state", statusLabel));
        if (!itemReason && datumHasPreview(item)) this._activatePreview(card, item, datumLabel(item, index), summary, config.defaultKind || "filter");
        list.appendChild(card);
      });
      container.appendChild(list);
      this._appendDataTable(container, config.caption || "Spatial evidence", ["Finding", cleanText(config.effectLabel, "Effect"), "95% interval", "q-value", "Status"], source.map(function (item, index) {
        const interval = intervalBounds(item);
        return [datumLabel(item, index), formatDecimal(comparativeEffect(item, config.valueKeys), 3), interval ? formatInterval(interval) : "—", formatDecimal(firstDefined(item, ["qValue", "q_value", "q"], null), 3), evidenceStatusLabel(item)];
      }));
    }

    _renderReadiness(chartId, value, summary, options) {
      const config = options || {};
      const matrix = readinessMatrix(value);
      const container = this._prepareChart(chartId, matrix.rows, summary, config.emptyMessage || "No cross-domain result is estimable. Readiness details will appear after provenance checks complete.");
      if (!container) return;
      container.appendChild(this._element("p", "analysis-heatmap-legend", "Green = inferentially ready · blue = descriptive or sensitivity-ready · amber = limited · red = blocked · gray = unavailable, not evaluated, or not applicable"));
      const scroll = this._element("div", "analysis-heatmap-scroll");
      const table = this._element("table", "analysis-readiness-matrix");
      table.appendChild(this._element("caption", "sr-only", "Cross-domain evidence readiness by domain and gate"));
      const head = this._element("thead");
      const headRow = this._element("tr");
      headRow.appendChild(this._element("th", "", "Domain"));
      matrix.columns.forEach((column) => headRow.appendChild(this._element("th", "", column.label)));
      head.appendChild(headRow);
      table.appendChild(head);
      const body = this._element("tbody");
      matrix.rows.forEach((row) => {
        const tableRow = this._element("tr");
        const domainHeading = this._element("th", "analysis-readiness-domain", row.label);
        if (row.eligible != null || row.total != null) {
          domainHeading.appendChild(this._element("span", "analysis-readiness-domain-count", " " + formatCount(row.eligible) + " / " + formatCount(row.total)));
        }
        tableRow.appendChild(domainHeading);
        row.cells.forEach((cell) => {
          const tableCell = this._element("td");
          const mark = this._element("span", "analysis-readiness-cell is-" + cell.status.replace(/_/g, "-"), cell.value);
          mark.setAttribute("data-readiness-status", cell.status);
          mark.setAttribute("data-gate-id", cell.key);
          mark.setAttribute("aria-label", row.label + ", " + cell.key + ": " + readinessStatusLabel(cell.status) + (cell.value === readinessStatusLabel(cell.status) ? "" : "; " + cell.value) + (cell.reason ? ". " + cell.reason : ""));
          mark.setAttribute("title", cell.reason || cell.value);
          tableCell.appendChild(mark);
          tableRow.appendChild(tableCell);
        });
        body.appendChild(tableRow);
      });
      table.appendChild(body);
      scroll.appendChild(table);
      container.appendChild(scroll);
      const details = this._element("details", "analysis-readiness-details");
      details.appendChild(this._element("summary", "", "View gate explanations and release hashes"));
      const detailList = this._element("dl", "analysis-readiness-detail-list");
      matrix.rows.forEach((row) => {
        const wrapper = this._element("div");
        wrapper.appendChild(this._element("dt", "", row.label));
        const releaseHash = cleanText(firstDefined(row.item, ["evidenceHash", "evidence_hash", "releaseHash", "release_hash", "artifactHash", "artifact_hash"], "Unavailable"));
        const policyId = cleanText(firstDefined(row.item, ["policyId", "policy_id"], "No policy identifier"));
        const description = this._element("dd");
        description.appendChild(this._element("p", "", (row.reasons.length ? row.reasons.join(" ") : "No domain-level reason codes.") + " Policy: " + policyId + ". Evidence hash: " + releaseHash));
        if (row.detailedGates.length) {
          const gateList = this._element("ul", "analysis-readiness-gate-list");
          row.detailedGates.forEach((detail) => {
            const gateItem = this._element("li");
            gateItem.appendChild(this._element("strong", "", detail.label));
            const countSummary = detail.cell.value === readinessStatusLabel(detail.cell.status)
              ? ""
              : " · passed/input " + detail.cell.value;
            const detailText = "Gate " + detail.key + " · " + readinessStatusLabel(detail.cell.status) + countSummary
              + " · applicability " + detail.applicability
              + (detail.cell.reason ? ". " + detail.cell.reason : "")
              + ". Policy: " + detail.policyId + ". Evidence hash: " + detail.evidenceHash;
            gateItem.appendChild(this._element("span", "", detailText));
            gateList.appendChild(gateItem);
          });
          description.appendChild(gateList);
        } else {
          description.appendChild(this._element("p", "", "No typed detailed gates are included for this domain."));
        }
        wrapper.appendChild(description);
        detailList.appendChild(wrapper);
      });
      details.appendChild(detailList);
      container.appendChild(details);
    }

    _renderRelationshipEvidence(chartId, value, summary, options) {
      const config = options || {};
      const cells = relationshipMatrix(value);
      this._renderHeatmap(chartId, cells, summary, {
        caption: config.caption || "Relationship lane and reconciliation counts",
        rowHeading: "Evidence lane",
        rowAxisKind: "category",
        columnAxisKind: "category",
        valueKeys: ["count", "value"],
        effectOnly: true,
        inspectable: true,
        effectLabel: "Relationship record count",
        emptyMessage: config.emptyMessage,
      });
      if (cells.length) this._appendChartPolicy(chartId, "Counts describe inherited relationship records and reconciliation state. Recomputed proximity evidence is kept separate.");
    }

    _renderDurationEvidence(value, summary) {
      const duration = isObject(value) ? value : {};
      const status = cleanText(firstDefined(duration, ["status", "readinessStatus", "readiness_status"], "data_unavailable"));
      const statusElement = this.document.getElementById("analysis-duration-status");
      const coverage = isObject(duration.coverage) ? duration.coverage : {};
      const active = isObject(coverage.active) ? coverage.active : {};
      const normalizedRows = finiteNumber(active.normalizedRows, 0);
      const catalogRows = finiteNumber(active.catalogRows, 0);
      const descriptiveRows = finiteNumber(active.descriptiveBinnedRows, 0);
      const inferentialRows = finiteNumber(active.inferentialBinnedRows, 0);
      const sourceCount = asArray(active.normalizedSources).filter(function (item) {
        return finiteNumber(item && item.rows, 0) > 0;
      }).length;
      if (statusElement) {
        if (status === "data_unavailable") {
          statusElement.textContent = "Typed duration evidence loads only when Time is requested. No duration chart is shown until its immutable artifact passes integrity checks.";
        } else if (status === "not_estimable") {
          statusElement.textContent = "Duration is not estimable for this cohort. Normalized values remain missing—not zero—and the readiness result is retained instead of an empty chart.";
        } else {
          statusElement.textContent = formatCount(normalizedRows) + " normalized duration records across " + formatCount(sourceCount)
            + " sources (" + formatPercent(catalogRows > 0 ? normalizedRows / catalogRows : 0) + " of matched reports). "
            + formatCount(descriptiveRows) + " occupy one conservative display bin; " + formatCount(inferentialRows)
            + " exact or closed-range records are eligible for comparison gates.";
        }
      }
      if (status === "data_unavailable" || status === "not_estimable") {
        const message = status === "data_unavailable"
          ? "Readiness pending: select Time to integrity-check and load the typed duration projection."
          : "Readiness failed for this cohort; missing, ambiguous, and bin-spanning values remain suppressed.";
        this._renderBars("analysis-duration-chart", [], summary, { emptyMessage: message });
        this._renderForestPlot("analysis-duration-comparison-chart", [], summary, {
          emptyMessage: "No adjusted duration comparison is available until the duration readiness gates pass.",
        });
        return;
      }
      const distribution = firstArray(duration, ["distribution", "bins"]);
      this._renderBars("analysis-duration-chart", distribution, summary, {
        caption: "Conservative reported-duration distribution",
        valueKeys: ["activeShare"],
        referenceKeys: ["referenceShare"],
        valueFormat: "percent",
        valueLabel: "Active share",
        referenceLabel: "Reference share",
        scaleActual: true,
        emptyMessage: "No duration interval falls wholly within one conservative display bin for this cohort.",
      });
      this._appendChartPolicy(
        "analysis-duration-chart",
        "Approximate source codes are descriptive. Censored, ambiguous, unresolved, and bin-spanning values never become zero or silently gain precision."
      );
      const comparisons = firstArray(duration, ["comparisons", "adjustedComparisons", "adjusted_comparisons"]);
      this._renderForestPlot("analysis-duration-comparison-chart", comparisons, summary, {
        caption: "Source–era–macroregion adjusted duration-bin differences",
        defaultKind: "filter",
        valueKeys: ["adjustedDifference", "adjustedEffect"],
        primaryCountLabel: "Active bin",
        comparisonCountLabel: "Reference bin",
        primaryCountKeys: ["observedCount"],
        comparisonCountKeys: ["referenceCount"],
        emptyMessage: "The descriptive duration distribution is ready. Adjusted comparisons require an independent reference cohort and all support gates.",
      });
    }

    _sectionData(result) {
      const overview = isObject(result.overview) ? result.overview : {};
      const time = isObject(result.time) ? result.time : {};
      const craft = isObject(result.craft) ? result.craft : {};
      const geography = isObject(result.geography) ? result.geography : {};
      const sourcesQuality = isObject(result.sourcesQuality) ? result.sourcesQuality : {};
      const sources = isObject(result.sources) ? result.sources : {};
      const quality = isObject(result.quality) ? result.quality : {};
      const context = isObject(result.context) ? result.context : {};
      const spatial = isObject(result.spatial) ? result.spatial : (isObject(result.spatialEvidence) ? result.spatialEvidence : {});
      const spatialEligibility = firstDefined(spatial, ["eligibility", "eligibilityFunnel", "eligibility_funnel"], {});
      const crossDomainReadiness = firstDefined(spatial, ["crossDomainReadiness", "cross_domain_readiness", "readiness"], firstDefined(context, ["readiness", "crossDomainReadiness"], {}));
      const adaptiveTimeSeries = firstArray(time, ["series", "yearly", "trends"]);
      const annualTimeSeries = firstArray(time, ["annualSeries", "annual_series"]);
      const sourceBalanced = firstArray(time, ["sourceBalanced", "source_balanced"]);
      const sourceBalancedSeries = sourceBalancedDisplay(sourceBalanced, adaptiveTimeSeries);
      return {
        overviewCoverage: firstArray(overview, ["eligibilityFunnel", "eligibility_funnel", "coverage", "coverageBars"]),
        overviewComparison: firstArray(overview, ["evidenceSummary", "evidence_summary", "adjustedEffects", "adjusted_effects", "comparison", "differences", "comparisonBars"]),
        timeSeries: this.currentAnalysisMode === "whole_corpus_structure"
          ? adaptiveTimeSeries
          : (sourceBalancedSeries.length ? sourceBalancedSeries : adaptiveTimeSeries),
        adaptiveTimeSeries,
        annualTimeSeries: annualTimeSeries.length ? annualTimeSeries : adaptiveTimeSeries,
        adaptiveBinning: isObject(time.adaptiveBinning) ? time.adaptiveBinning : (isObject(time.adaptive_binning) ? time.adaptive_binning : {}),
        sourceBalanced: sourceBalancedSeries,
        sourceBalancedPolicy: cleanText(firstDefined(time, ["sourceBalancedPolicy", "source_balanced_policy"], "")),
        duration: firstDefined(time, ["duration", "durationAssessment", "duration_assessment"], {}),
        monthYear: firstDefined(time, ["monthByCraft", "month_by_craft", "monthYear", "monthly", "monthByYear"], []),
        craftDistribution: firstArray(craft, ["mosaic", "distribution", "ranked", "categories", "adjustedEffects", "adjusted_effects"]),
        reportTypes: firstArray(craft, ["reportTypes", "reportedTypes", "types"]),
        craftConfidence: firstArray(craft, ["confidence", "classificationConfidence", "craftConfidence"]),
        craftEra: firstDefined(craft, ["byEra", "by_era", "eraHeatmap", "era_heatmap"], firstDefined(craft, ["trends", "byTime"], [])),
        craftResiduals: firstDefined(craft, ["residuals", "sourceDependence", "association"], []),
        craftSourceAssociation: firstDefined(craft, ["sourceAssociation", "source_association"], {}),
        geographyCountries: firstDefined(geography, ["countryChoropleth", "country_choropleth", "countryEffects", "country_effects", "countries"], []),
        geographyCells: geographyMapCells(firstDefined(geography, ["equalAreaMap", "equal_area_map", "equalArea", "equal_area", "cells", "grid", "density"], [])),
        geographySensitivity: firstDefined(geography, ["equalAreaSensitivity", "equal_area_sensitivity", "equalAreaMap", "equal_area_map"], []),
        geographyTime: normalizeGeographyCells(firstDefined(geography, ["byEra", "by_era", "byTime", "geographyTime", "timeGrid"], [])),
        cooccurrence: firstDefined(spatial, ["cooccurrence", "craftCooccurrence", "craft_cooccurrence"], {}),
        spatialEligibility: Array.isArray(spatialEligibility)
          ? spatialEligibility
          : firstArray(spatialEligibility, ["stages", "funnel", "items"]),
        contextAssociations: firstDefined(spatial, ["contextAssociations", "context_associations"], {}),
        facilities: firstDefined(spatial, ["facility", "facilities", "facilityContext", "facility_context"], {}),
        crossDomainReadiness,
        cropReadiness: readinessForDomain(crossDomainReadiness, "crops"),
        animalReadiness: readinessForDomain(crossDomainReadiness, "animals"),
        relationshipReadiness: firstDefined(spatial, ["relationshipSummary", "relationship_summary", "relationshipEvidence", "relationship_evidence", "relationships"], readinessForDomain(crossDomainReadiness, "relationships")),
        spatialStatus: cleanText(firstDefined(spatial, ["status", "message", "evidenceStatus", "evidence_status"], "")),
        sourceComposition: firstArray(sourcesQuality, ["sourceComposition", "sources", "composition"]).concat(
          firstArray(sources, ["composition", "distribution"])
        ),
        sourceByTime: firstDefined(sourcesQuality, ["sourceByTime", "source_by_time", "compositionByTime"], firstDefined(sources, ["byTime", "sourceByTime"], [])),
        missingness: firstDefined(sourcesQuality, ["missingness", "coverage"], firstDefined(quality, ["missingness", "coverage"], [])),
        audit: firstDefined(sourcesQuality, ["classifierAudit", "audit"], firstDefined(quality, ["classifierAudit", "audit", "confusion"], [])),
        auditPolicy: cleanText(firstDefined(sourcesQuality, ["classifierAuditPolicy", "classifier_audit_policy", "auditPolicy"], "Classifier consistency is an internal agreement audit, not ground truth.")),
        crops: isObject(context.crops) ? context.crops : (isObject(result.crops) ? result.crops : {}),
        animals: isObject(context.animals) ? context.animals : (isObject(result.animals) ? result.animals : {}),
      };
    }

    _setContextGroup(groupId, statusId, contextData, label) {
      const group = this.document.getElementById(groupId);
      const status = this.document.getElementById(statusId);
      const domain = groupId.indexOf("animal") !== -1 ? "animals" : "crops";
      const enabled = contextEnabledForRender(
        contextData,
        this.latestMeta && this.latestMeta.filterSnapshot,
        domain
      );
      if (group && group.classList && !group.classList.contains("analysis-context-subview")) {
        group.hidden = false;
        setElementInert(group, false);
      }
      if (!enabled) {
        this.setContextControlState(domain, {
          enabled: false,
          status: "ready",
          message: "Excluded",
        });
        if (status) status.textContent = label + " are excluded from the current Analysis computation.";
        return null;
      }
      this.setContextControlState(domain, {
        enabled: true,
        status: cleanText(firstDefined(contextData, ["status"], "ready")),
        message: "Included",
      });
      const domainSummary = Object.assign(
        {},
        isObject(contextData.summary) ? contextData.summary : {},
        isObject(contextData.meta) ? contextData.meta : {}
      );
      const timeRows = firstArray(contextData, ["time", "series", "yearly"]);
      const inferredActive = timeRows.reduce(function (total, item) { return total + Math.max(0, datumValue(item)); }, 0);
      const inferredReference = timeRows.reduce(function (total, item) { return total + Math.max(0, datumReference(item) || 0); }, 0);
      const activeCount = firstDefined(contextData, ["activeCount", "count", "rowCount", "recordCount"],
        firstDefined(domainSummary, ["activeCount", "active_count", "count"], timeRows.length ? inferredActive : null));
      const referenceCount = firstDefined(contextData, ["referenceCount", "baselineCount"],
        firstDefined(domainSummary, ["referenceCount", "reference_count", "baselineCount"], timeRows.length ? inferredReference : null));
      const projectionRows = firstDefined(contextData, ["totalProjectionRows", "projectionRowCount", "projectionRows"],
        firstDefined(domainSummary, ["totalProjectionRows", "projectionRowCount"], null));
      if (status) {
        const statusCode = cleanText(contextData.status).toLowerCase();
        status.textContent = statusCode && statusCode !== "ready" && activeCount == null && projectionRows == null
          ? label + " projection is " + statusCode.replace(/_/g, " ") + "."
          : (this.currentAnalysisMode === "whole_corpus_structure"
            ? label + ": " + formatCount(activeCount) + " matched records · " + formatCount(projectionRows) + " total projection rows."
            : label + ": " + formatCount(activeCount) + " active · " + formatCount(referenceCount)
              + " reference · " + formatCount(projectionRows) + " total projection rows.");
      }
      const contextSummary = normalizeSummary(Object.assign(
        {},
        domainSummary,
        {
          activeCount: activeCount == null ? 0 : activeCount,
          referenceCount: referenceCount == null ? 0 : referenceCount,
          unitLabel: cleanText(firstDefined(contextData, ["unitLabel", "unit"], firstDefined(domainSummary, ["unitLabel", "unit", "unit_of_analysis"], label)), label),
          datasetHash: firstDefined(contextData, ["datasetHash", "dataset_hash", "artifactHash", "artifact_hash"], firstDefined(domainSummary, ["datasetHash", "dataset_hash", "artifactHash", "artifact_hash"], "Not reported")),
          policyWarning: cleanText(firstDefined(contextData, ["policyWarning", "policyWarnings"], firstDefined(domainSummary, ["policyWarning", "policyWarnings"], "Descriptive context records only."))),
        }
      ));
      if (group) {
        let disclosure = Array.prototype.slice.call(group.children || []).find(function (child) {
          return (" " + cleanText(child.className) + " ").indexOf(" analysis-context-membership-policy ") !== -1;
        });
        if (!disclosure) {
          disclosure = this._element("p", "analysis-context-membership-policy analysis-chart-policy");
          group.appendChild(disclosure);
        }
        disclosure.textContent = contextMembershipDisclosure(contextData, domainSummary, contextSummary.unitLabel);
      }
      return contextSummary;
    }

    renderAnalysisResult(result, metaOverrides) {
      const payload = isObject(result) ? result : {};
      this.latestResult = payload;
      this.latestMeta = isObject(metaOverrides) ? Object.assign({}, metaOverrides) : {};
      if (this.els.exportJson) this.els.exportJson.disabled = false;
      if (this.els.exportCsv) this.els.exportCsv.disabled = false;
      const summaryInput = Object.assign(
        {},
        isObject(payload.summary) ? payload.summary : {},
        isObject(payload.meta) ? payload.meta : {},
        isObject(metaOverrides) ? metaOverrides : {}
      );
      const analysisMode = cleanText(firstDefined(
        payload,
        ["analysisMode", "analysis_mode"],
        firstDefined(summaryInput, ["analysisMode", "analysis_mode"], "comparative")
      ));
      const comparisonState = cleanText(firstDefined(
        payload,
        ["comparisonState", "comparison_state"],
        firstDefined(summaryInput, ["comparisonState", "comparison_state"], analysisMode === "whole_corpus_structure" ? "whole_corpus_structure" : "inferential")
      ));
      this._setAnalysisModePresentation(analysisMode, comparisonState);
      const summary = this.updateCohortSummary(summaryInput);
      const data = this._sectionData(payload);
      const overviewJobs = [];
      const timeJobs = [];
      const craftJobs = [];
      const geographyJobs = [];
      const spatialJobs = [];
      const sourcesQualityJobs = [];
      const contextOverviewJobs = [];
      const cropContextJobs = [];
      const animalContextJobs = [];
      const relationshipContextJobs = [];
      overviewJobs.push(() => this._renderEligibilityFunnel("analysis-coverage-chart", data.overviewCoverage, summary, { caption: "Analysis eligibility funnel", limit: 8 }));
      overviewJobs.push(() => this._renderForestPlot("analysis-comparison-chart", data.overviewComparison, summary, {
        caption: "Signal spectrum: adjusted effects with 95% intervals",
        defaultKind: "filter",
        valueKeys: ["difference", "value"],
        limit: 6,
        compact: true,
        rankByEvidence: true,
      }));
      timeJobs.push(() => {
        this._renderAdaptiveTimeline("analysis-time-series-chart", {
          volume: data.adaptiveTimeSeries,
          annual: data.annualTimeSeries,
          balanced: data.sourceBalanced,
          collection: data.sourceByTime,
          adaptiveBinning: data.adaptiveBinning,
          sourceBalancedPolicy: data.sourceBalancedPolicy,
        }, summary, {
          defaultKind: "filter",
        });
      });
      timeJobs.push(() => this._renderDurationEvidence(data.duration, summary));
      timeJobs.push(() => this._renderHeatmap("analysis-month-year-chart", data.monthYear, summary, { caption: "Recurring month by craft adjusted effects", rowHeading: "Craft", defaultKind: "filter", columnAxisKind: "month", axisColumns: ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12"], craftRows: true, effectOnly: true, valueKeys: ["adjustedResidual", "adjusted_residual", "standardizedResidual", "residual", "difference", "value"] }));
      craftJobs.push(() => {
        this._renderCraftMosaic("analysis-craft-distribution-chart", data.craftDistribution, summary, { caption: "Craft category mosaic", defaultKind: "filter", limit: 12 });
      });
      sourcesQualityJobs.push(() => this._renderBars("analysis-report-type-chart", data.reportTypes, summary, { caption: "Reported event types", defaultKind: "filter" }));
      craftJobs.push(() => this._renderBars("analysis-craft-confidence-chart", data.craftConfidence, summary, { caption: "Craft classification confidence" }));
      craftJobs.push(() => this._renderHeatmap("analysis-craft-era-chart", data.craftEra, summary, { caption: "Craft by era adjusted residuals", rowHeading: "Craft", defaultKind: "filter", columnAxisKind: "era", craftRows: true, effectOnly: true, valueKeys: ["adjustedResidual", "adjusted_residual", "standardizedResidual", "residual", "difference", "value"] }));
      sourcesQualityJobs.push(() => {
        this._renderHeatmap("analysis-craft-residual-chart", data.craftResiduals, summary, { caption: "Craft by source standardized residuals", rowHeading: "Craft", defaultKind: "filter", craftRows: true, effectOnly: true, valueKeys: ["standardizedResidual", "residual"] });
        this._appendChartPolicy(
          "analysis-craft-residual-chart",
          cleanText(
            firstDefined(data.craftSourceAssociation, ["policyWarning", "policy_warning"], "Association residuals require expected cell counts of at least 10 and Cramer's V of at least 0.10.")
          )
        );
      });
      geographyJobs.push(() => {
        const renderedCountries = this._renderCountryChoropleth("analysis-geography-grid-chart", data.geographyCountries, summary, { caption: "Country-level geography evidence", defaultKind: "area", valueKeys: ["adjustedDifference", "adjusted_difference", "difference", "value"] });
        if (!renderedCountries) this._renderEqualAreaMap("analysis-geography-grid-chart", data.geographyCells, summary, { caption: "Equal-area adjusted report enrichment", defaultKind: "area", valueKeys: ["adjustedDifference", "adjusted_difference", "difference", "value"] });
      });
      geographyJobs.push(() => {
        const sensitivity = this.document.getElementById("analysis-geography-sensitivity-chart");
        if (!sensitivity) return;
        this._renderEqualAreaMap("analysis-geography-sensitivity-chart", data.geographySensitivity, summary, { caption: "Equal-area spatial-bias sensitivity", defaultKind: "area", valueKeys: ["adjustedDifference", "adjusted_difference", "difference", "value"] });
      });
      geographyJobs.push(() => this._renderHeatmap("analysis-geography-time-chart", data.geographyTime, summary, { caption: "Geography by era adjusted comparison", rowHeading: "Region", defaultKind: "area", columnAxisKind: "era", humanGeographyRows: true, effectOnly: true, valueKeys: ["adjustedDifference", "adjusted_difference", "standardizedResidual", "residual", "difference", "value"] }));
      const spatialCooccurrenceJob = () => this._renderCooccurrenceEvidence("analysis-cooccurrence-chart", data.cooccurrence, summary, { caption: "Point-based craft co-occurrence evidence", defaultKind: "filter", primaryCountLabel: "Observed", comparisonCountLabel: "Expected", primaryCountKeys: ["observedCount", "observed_count"], comparisonCountKeys: ["expectedCount", "expected_count"], effectLabel: "Log2 observed/expected enrichment", valueKeys: ["log2Enrichment", "log2_enrichment"], nullValue: 0, axisLimit: 6, emptyMessage: "Not estimable until the qualified point-neighbor artifact and stratified null results are available." });
      spatialJobs.push(() => {
        if (!this.document.getElementById("analysis-spatial-eligibility-chart")) return;
        this._renderEligibilityFunnel("analysis-spatial-eligibility-chart", data.spatialEligibility, summary, { caption: "High-precision co-occurrence pool", limit: 8 });
      });
      const spatialContextJobs = [
        () => this._renderContextAssociations("analysis-context-neighborhood-chart", data.contextAssociations, summary, { emptyMessage: "Context-marker neighborhood evidence loads with the pinned point-neighbor artifact." }),
        () => this._renderContextCategoryAssociations("analysis-context-category-chart", "analysis-context-category-card", data.contextAssociations, summary),
      ];
      const spatialFacilityJob = () => this._renderFacilityEvidence("analysis-facility-context-chart", data.facilities, summary, { caption: "Qualified facility-marker context evidence", defaultKind: "filter", primaryCountLabel: "Near band", comparisonCountLabel: "Comparison band", primaryCountKeys: ["nearCount", "near_count"], comparisonCountKeys: ["comparisonCount", "comparison_count"], effectLabel: "CMH odds ratio", valueKeys: ["commonOddsRatio", "common_odds_ratio", "oddsRatio", "odds_ratio"], nullValue: 1, limit: 8, emptyMessage: "Not estimable until facility precision, activity interval, and common-support gates pass." });
      contextOverviewJobs.push(() => this._renderReadiness("analysis-cross-domain-readiness-chart", data.crossDomainReadiness, summary, { emptyMessage: "Crop and animal proximity remains not estimable until provenance, uncertainty, lineage, and sample gates pass." }));
      spatialJobs.push(() => {
        if (this.els.spatialStatus) this.els.spatialStatus.textContent = data.spatialStatus || "Spatial evidence is associative, point-based, uncertainty-aware, and never uses chronology connectors.";
      });
      sourcesQualityJobs.push(() => this._renderBars("analysis-source-composition-chart", data.sourceComposition, summary, { caption: "Source composition", defaultKind: "filter" }));
      sourcesQualityJobs.push(() => this._renderStackedComposition("analysis-source-time-chart", data.sourceByTime, summary, {
        caption: "100% stacked source composition by period",
        defaultKind: "filter",
      }));
      sourcesQualityJobs.push(() => this._renderHeatmap("analysis-quality-missingness-chart", data.missingness, summary, { caption: "Field missingness and coverage", rowHeading: "Field", defaultKind: "filter", effectOnly: true }));
      sourcesQualityJobs.push(() => {
        this._renderHeatmap("analysis-quality-audit-chart", data.audit, summary, { caption: "Classifier consistency audit", rowHeading: "Recorded class", defaultKind: "filter", effectOnly: true, craftRows: true, craftColumns: true });
        this._appendChartPolicy("analysis-quality-audit-chart", data.auditPolicy);
      });
      relationshipContextJobs.push(() => this._renderRelationshipEvidence("analysis-relationship-readiness-chart", data.relationshipReadiness, summary, { emptyMessage: "Relationship reconciliation details load with Spatial Evidence; unresolved identifiers remain quarantined." }));

      const crops = data.crops;
      const cropSummary = this._setContextGroup(
        "analysis-crop-context",
        "analysis-crop-context-status",
        crops,
        "Crop-circle records"
      );
      if (cropSummary) {
        cropContextJobs.push(() => this._renderReadiness("analysis-crop-readiness-chart", data.cropReadiness, cropSummary, { emptyMessage: "Detailed crop-association readiness loads with Spatial Evidence; descriptive catalog health remains available here." }));
        cropContextJobs.push(() => this._renderSeries("analysis-crop-time-chart", firstArray(crops, ["time", "series", "yearly"]), cropSummary, { caption: "Crop-circle records by period", axisKind: "year", singleSeries: this.currentAnalysisMode === "whole_corpus_structure", singleSeriesLabel: "All crop-circle records" }));
        cropContextJobs.push(() => this._renderBars("analysis-crop-morphology-chart", firstArray(crops, ["morphology", "types", "distribution"]), cropSummary, { caption: "Provisional crop morphology" }));
        cropContextJobs.push(() => this._renderBars("analysis-crop-type-chart", firstArray(crops, ["crop", "cropType", "cropTypes"]), cropSummary, { caption: "Crop-circle crop types" }));
        cropContextJobs.push(() => this._renderBars("analysis-crop-coordinate-chart", firstArray(crops, ["coordinateClass", "coordinateClasses", "coordinate_class"]), cropSummary, { caption: "Crop-circle coordinate classes" }));
        cropContextJobs.push(() => this._renderHeatmap("analysis-crop-coverage-chart", firstDefined(crops, ["coverage", "missingness"], []), cropSummary, { caption: "Crop-circle field coverage", rowHeading: "Field" }));
        cropContextJobs.push(() => this._renderContextAssociations("analysis-crop-spatial-chart", data.contextAssociations, cropSummary, {
          allowedLanes: ["crop_bounded", "crop_locality"],
          emptyMessage: "Crop point-neighborhood evidence has not loaded. The descriptive crop catalog above remains available.",
        }));
      }
      const animals = data.animals;
      const animalSummary = this._setContextGroup(
        "analysis-animal-context",
        "analysis-animal-context-status",
        animals,
        "Animal reports"
      );
      if (animalSummary) {
        animalContextJobs.push(() => this._renderReadiness("analysis-animal-readiness-chart", data.animalReadiness, animalSummary, { emptyMessage: "Detailed animal-association readiness loads with Spatial Evidence; descriptive catalog health remains available here." }));
        animalContextJobs.push(() => this._renderSeries("analysis-animal-time-chart", firstArray(animals, ["time", "series", "yearly"]), animalSummary, { caption: "Animal reports by period", axisKind: "year", singleSeries: this.currentAnalysisMode === "whole_corpus_structure", singleSeriesLabel: "All animal reports" }));
        animalContextJobs.push(() => this._renderBars("analysis-animal-species-chart", firstArray(animals, ["species", "speciesGroups", "distribution"]), animalSummary, { caption: "Animal report species groups" }));
        animalContextJobs.push(() => this._renderBars("analysis-animal-status-chart", firstArray(animals, ["statusBreakdown", "reviewStatus", "status"]), animalSummary, { caption: "Animal report review status" }));
        animalContextJobs.push(() => this._renderBars("analysis-animal-date-precision-chart", firstArray(animals, ["datePrecision", "datePrecisions", "date_precision"]), animalSummary, { caption: "Animal report date precision" }));
        animalContextJobs.push(() => this._renderHeatmap("analysis-animal-coverage-chart", firstDefined(animals, ["coverage", "missingness"], []), animalSummary, { caption: "Animal report field coverage", rowHeading: "Field" }));
        animalContextJobs.push(() => this._renderContextAssociations("analysis-animal-spatial-chart", data.contextAssociations, animalSummary, {
          allowedLanes: ["animal_public_marker"],
          emptyMessage: "Animal public-marker neighborhood evidence has not loaded. The descriptive animal catalog above remains available.",
        }));
      }
      overviewJobs.push(() => {
        const findings = (this.currentAnalysisMode !== "whole_corpus_structure" && (this.baselineMode === "full_catalog" || this.currentComparisonState === "descriptive_overlap")) ? [] : firstArray(payload, ["patterns", "findings", "patternFindings"]).filter(function (finding) {
          const family = cleanText(firstDefined(finding, ["family", "statisticalFamily", "statistical_family"], "")).toLowerCase();
          return family !== "burst" && family !== "time_burst" && family !== "date_window" && family !== "structural_date_window";
        });
        this.renderPatternFindings(findings, firstDefined(payload, ["patternGroups", "pattern_groups"], null));
      });
      if (this.renderPending) this._cancelActiveRenderScope();
      this._clearRenderTargets(Array.from(this.renderPlans.values()).reduce(function (ids, plan) {
        return ids.concat(asArray(plan && plan.targets));
      }, []));
      this.resultRenderVersion += 1;
      this.renderedPlanVersions.clear();
      this._setDeferredDisclosureJobs("analysis-spatial-matrix-disclosure", [spatialCooccurrenceJob]);
      this._setDeferredDisclosureJobs("analysis-spatial-context-disclosure", spatialContextJobs);
      this._setDeferredDisclosureJobs("analysis-spatial-facility-disclosure", [spatialFacilityJob]);
      this.renderFinalState = summary.activeCount > 0 ? "ready" : "empty";
      this.renderPlans = new Map([
        ["analysis-section-overview", { jobs: overviewJobs, targets: ["analysis-coverage-chart", "analysis-comparison-chart", "analysis-pattern-list"] }],
        ["analysis-section-time", { jobs: timeJobs, targets: ["analysis-time-series-chart", "analysis-duration-chart", "analysis-duration-comparison-chart", "analysis-month-year-chart"] }],
        ["analysis-section-craft", { jobs: craftJobs, targets: ["analysis-craft-distribution-chart", "analysis-craft-confidence-chart", "analysis-craft-era-chart"] }],
        ["analysis-section-geography", { jobs: geographyJobs, targets: ["analysis-geography-grid-chart", "analysis-geography-sensitivity-chart", "analysis-geography-time-chart"] }],
        ["analysis-section-spatial", { jobs: spatialJobs, targets: ["analysis-cooccurrence-chart", "analysis-spatial-eligibility-chart", "analysis-context-neighborhood-chart", "analysis-context-category-chart", "analysis-facility-context-chart"] }],
        ["analysis-section-context", { jobs: contextOverviewJobs, targets: ["analysis-cross-domain-readiness-chart"] }],
        ["analysis-crop-context", { jobs: cropContextJobs, targets: ["analysis-crop-readiness-chart", "analysis-crop-time-chart", "analysis-crop-morphology-chart", "analysis-crop-type-chart", "analysis-crop-coordinate-chart", "analysis-crop-coverage-chart", "analysis-crop-spatial-chart"] }],
        ["analysis-animal-context", { jobs: animalContextJobs, targets: ["analysis-animal-readiness-chart", "analysis-animal-time-chart", "analysis-animal-species-chart", "analysis-animal-status-chart", "analysis-animal-date-precision-chart", "analysis-animal-coverage-chart", "analysis-animal-spatial-chart"] }],
        ["analysis-relationship-context", { jobs: relationshipContextJobs, targets: ["analysis-relationship-readiness-chart"] }],
        ["analysis-section-sources-quality", { jobs: sourcesQualityJobs, targets: ["analysis-report-type-chart", "analysis-craft-residual-chart", "analysis-source-composition-chart", "analysis-source-time-chart", "analysis-quality-missingness-chart", "analysis-quality-audit-chart"] }],
      ]);
      this._clearRenderTargets(Array.from(this.renderPlans.values()).reduce(function (ids, plan) {
        return ids.concat(asArray(plan && plan.targets));
      }, []));
      this._renderActiveSectionIfNeeded();
      return summary;
    }

    _renderPatternFindingItem(finding, index) {
      const item = this._element("li", "analysis-pattern-item");
      const head = this._element("div", "analysis-pattern-heading");
      const title = this._element("strong", "", cleanText(firstDefined(finding, ["title", "label"], "Exploratory pattern " + (index + 1))));
      const sourceStability = firstDefined(finding, ["sourceStability", "stability"], "Not reported");
      const stabilityLabel = isObject(sourceStability)
        ? cleanText(firstDefined(sourceStability, ["status", "label"], sourceStability.stable === true ? "Stable" : (sourceStability.stable === false ? "Source-specific" : "Qualified")))
        : cleanText(sourceStability, cleanText(finding.badge, "Qualified"));
      const badge = this._element("span", "analysis-pattern-badge", stabilityLabel);
      head.appendChild(title);
      head.appendChild(badge);
      item.appendChild(head);
      item.appendChild(this._element("p", "analysis-pattern-summary", cleanText(firstDefined(finding, ["summary", "policyLabel", "policy_label"], "A qualified difference was detected."))));
      const metrics = this._element("dl", "analysis-pattern-metrics");
      const difference = firstDefined(finding, ["difference", "shareDifference", "share_difference"], null);
      const relativeEnrichment = firstDefined(finding, ["relativeEnrichment", "relative_enrichment", "shareRatio"], null);
      const derivedEffect = [
        difference == null ? "" : "Δ " + formatPercent(difference),
        relativeEnrichment == null ? "" : "Relative enrichment " + formatDecimal(relativeEnrichment, 3) + "x",
      ].filter(Boolean).join(" · ");
      const metricValues = [
        ["Observed", formatCount(firstDefined(finding, ["observedCount", "observed", "count"], null))],
        ["Reference", formatCount(firstDefined(finding, ["referenceCount", "reference"], null))],
        ["Effect", cleanText(firstDefined(finding, ["effectLabel", "effect", "effectSize"], derivedEffect || "—"))],
        ["95% interval", formatInterval(firstDefined(finding, ["intervalLabel", "interval", "confidenceInterval"], null))],
        ["q-value", formatDecimal(firstDefined(finding, ["qValue", "q_value", "q"], null), 4)],
        ["Missingness", firstDefined(finding, ["missingness", "missingRate"], null) == null ? "—" : formatPercent(firstDefined(finding, ["missingness", "missingRate"], null))],
        ["Common support", firstDefined(finding, ["commonSupportRate", "common_support_rate"], null) == null ? "Not reported" : formatPercent(firstDefined(finding, ["commonSupportRate", "common_support_rate"], null))],
        ["Source stability", formatSourceStability(sourceStability)],
        ["Region stability", formatSourceStability(firstDefined(finding, ["regionStability", "region_stability"], "Not reported"))],
        ["Dataset", cleanText(firstDefined(finding, ["datasetHash", "dataset_hash"], "Not reported"))],
      ];
      metricValues.forEach((entry) => {
        const wrapper = this._element("div");
        wrapper.appendChild(this._element("dt", "", entry[0]));
        wrapper.appendChild(this._element("dd", "", entry[1]));
        metrics.appendChild(wrapper);
      });
      item.appendChild(metrics);
      const chartId = resolvedPatternChartId(firstDefined(finding, ["chartId", "chart_id", "supportingChartId"], ""));
      if (chartId && this.document.getElementById(chartId)) {
        const button = this._element("button", "secondary-button analysis-pattern-link", "Open supporting chart");
        button.type = "button";
        button.addEventListener("click", () => {
          const chart = this.document.getElementById(chartId);
          if (chart && typeof chart.scrollIntoView === "function") chart.scrollIntoView({ behavior: "smooth", block: "center" });
          if (chart) {
            chart.setAttribute("tabindex", "-1");
            if (typeof chart.focus === "function") chart.focus({ preventScroll: true });
          }
        });
        item.appendChild(button);
      }
      return item;
    }

    renderPatternFindings(findings, patternGroups) {
      const list = this.document.getElementById("analysis-pattern-list");
      const count = this.document.getElementById("analysis-pattern-count");
      if (!list) return 0;
      this._clear(list);
      const lanes = patternGroupsForDisplay(findings, patternGroups);
      const total = lanes.reduce(function (sum, lane) { return sum + lane.patterns.length; }, 0);
      if (count) count.textContent = formatCount(total);
      let findingIndex = 0;
      lanes.forEach((lane) => {
        const laneItem = this._element("li", "analysis-pattern-lane analysis-pattern-lane-" + lane.key);
        const heading = this._element("div", "analysis-pattern-lane-heading");
        heading.appendChild(this._element("h5", "", lane.label));
        heading.appendChild(this._element("span", "analysis-pattern-lane-count", formatCount(lane.patterns.length)));
        laneItem.appendChild(heading);
        laneItem.appendChild(this._element("p", "analysis-pattern-lane-description", lane.description));
        const laneList = this._element("ol", "analysis-pattern-lane-list");
        if (!lane.patterns.length) {
          laneList.appendChild(this._element("li", "analysis-pattern-empty", "No qualified findings in this lane for the active cohort."));
        } else {
          lane.patterns.forEach((finding) => {
            laneList.appendChild(this._renderPatternFindingItem(finding, findingIndex));
            findingIndex += 1;
          });
        }
        laneItem.appendChild(laneList);
        list.appendChild(laneItem);
      });
      return total;
    }

    showPreview(preview) {
      if (!isObject(preview)) throw new TypeError("Preview metadata must be an object.");
      const kind = cleanText(preview.kind, preview.area != null ? "area" : "filter").toLowerCase() === "area" ? "area" : "filter";
      this.currentPreview = Object.assign({}, preview, { kind });
      this.previousPreviewFocus = this.document.activeElement;
      this.els.previewKind.textContent = preview.readOnly === true ? "Evidence details" : (kind === "area" ? "Local geography preview" : "Local chart preview");
      this.els.previewTitle.textContent = cleanText(preview.title, "Preview selection");
      this.els.previewSummary.textContent = cleanText(preview.summary, "Review the proposed cohort before changing the shared filters.");
      this.els.previewCohort.textContent = preview.cohortSize == null ? "—" : formatCount(preview.cohortSize);
      this.els.previewMissingness.textContent = preview.missingness == null
        ? "—"
        : (typeof preview.missingness === "string" ? preview.missingness : formatPercent(preview.missingness));
      this.els.previewComparison.textContent = cleanText(preview.comparison, "No comparison supplied");
      this._clear(this.els.previewCriteria);
      const criteria = asArray(firstDefined(preview, ["criteria", "changedCriteria"], []));
      if (!criteria.length) {
        this.els.previewCriteria.appendChild(this._element("li", "", "No additional criteria supplied."));
      } else {
        criteria.forEach((criterion) => {
          const text = isObject(criterion)
            ? cleanText(criterion.label, "Criterion") + ": " + cleanText(criterion.value, "—")
            : cleanText(criterion);
          this.els.previewCriteria.appendChild(this._element("li", "", text));
        });
      }
      this.els.previewFeedback.textContent = "";
      this.els.previewApplyFilters.hidden = preview.readOnly === true || kind !== "filter";
      this.els.previewApplyArea.hidden = preview.readOnly === true || kind !== "area";
      this.els.previewDrawer.hidden = false;
      setElementInert(this.els.previewDrawer, false);
      if (typeof this.els.previewTitle.focus === "function") this.els.previewTitle.focus({ preventScroll: true });
      return this.currentPreview;
    }

    hidePreview(options) {
      const config = options || {};
      this.els.previewDrawer.hidden = true;
      setElementInert(this.els.previewDrawer, true);
      this.els.previewFeedback.textContent = "";
      this.previewPending = false;
      this.els.previewApplyFilters.disabled = false;
      this.els.previewApplyArea.disabled = false;
      const restoreTarget = this.previousPreviewFocus;
      this.currentPreview = null;
      this.previousPreviewFocus = null;
      if (config.restoreFocus !== false && restoreTarget && typeof restoreTarget.focus === "function") {
        restoreTarget.focus({ preventScroll: true });
      }
    }

    _setPreviewPending(pending) {
      this.previewPending = Boolean(pending);
      this.els.previewApplyFilters.disabled = this.previewPending;
      this.els.previewApplyArea.disabled = this.previewPending;
      this.els.previewDrawer.setAttribute("aria-busy", this.previewPending ? "true" : "false");
      if (this.previewPending) this.els.previewFeedback.textContent = "Applying selection…";
    }

    _applyPreview(kind) {
      if (!this.currentPreview || this.previewPending || this.currentPreview.kind !== kind) return false;
      const callback = kind === "area" ? this.callbacks.onApplyAreaPreview : this.callbacks.onApplyFilterPreview;
      if (!callback) {
        this.els.previewFeedback.textContent = "This selection is not connected to the shared filters yet.";
        return false;
      }
      let result;
      try {
        result = callback(this.currentPreview);
      } catch (error) {
        this.els.previewFeedback.textContent = cleanText(error && error.message, "The selection could not be applied.");
        return false;
      }
      if (result && typeof result.then === "function") {
        this._setPreviewPending(true);
        result.then((outcome) => {
          this._setPreviewPending(false);
          if (outcome !== false) this.hidePreview();
        }).catch((error) => {
          this._setPreviewPending(false);
          this.els.previewFeedback.textContent = cleanText(error && error.message, "The selection could not be applied.");
        });
      } else if (result !== false) {
        this.hidePreview();
      }
      return true;
    }

    _cancelPreview() {
      if (!this.currentPreview) return;
      const preview = this.currentPreview;
      this.hidePreview();
      if (this.callbacks.onCancelPreview) this.callbacks.onCancelPreview(preview);
    }

    destroy() {
      this._cancelRenderSequence();
      if (this.sectionObserver && typeof this.sectionObserver.disconnect === "function") this.sectionObserver.disconnect();
      this.sectionObserver = null;
      if (this.sectionScrollFrame != null && this.cancelRenderFrame) this.cancelRenderFrame(this.sectionScrollFrame);
      this.sectionScrollFrame = null;
      if (this.anchorCorrectionTimerId != null && this.documentView && typeof this.documentView.clearTimeout === "function") {
        this.documentView.clearTimeout(this.anchorCorrectionTimerId);
      }
      this.anchorCorrectionTimerId = null;
      this.listeners.forEach(function (entry) {
        if (entry[0] && typeof entry[0].removeEventListener === "function") {
          entry[0].removeEventListener(entry[1], entry[2]);
        }
      });
      this.listeners = [];
      this.deferredDisclosureJobs.clear();
      this.currentPreview = null;
    }
  }

  function documentSafeElement(ownerDocument, tagName, className, text) {
    const element = ownerDocument.createElement(tagName);
    if (className) element.className = className;
    if (text != null) element.textContent = String(text);
    return element;
  }

  function createAnalysisViewController(options) {
    return new AnalysisViewController(options);
  }

  return Object.freeze({
    ACTIVE_VIEWS,
    ANALYSIS_STATES,
    BASELINE_MODES,
    BASELINE_NOTES,
    SERIES_POINT_LIMIT,
    HEATMAP_CELL_LIMIT,
    HEATMAP_AXIS_LIMIT,
    SOURCE_COMPOSITION_SOURCE_LIMIT,
    SOURCE_COMPOSITION_PERIOD_LIMIT,
    PATTERN_FAMILY_ORDER,
    PATTERN_LANES,
    AnalysisViewController,
    analysisRequestEnvelopeMatches,
    buildEvidencePackage,
    collapseDuplicateReferenceSeries,
    comparativeEffect,
    countryEvidenceItems,
    craftDisplayLabel,
    contextEnabledForRender,
    contextMembershipDisclosure,
    createAnalysisViewController,
    craftTrendSeries,
    formatCount,
    formatInterval,
    formatPercent,
    formatPercentInterval,
    formatSignedPercent,
    formatSourceStability,
    geographyMapCells,
    evidencePackageRows,
    evidencePackageToCsv,
    estimateAvailable,
    heatmapDisplayItems,
    humanGeographyLabel,
    inferPreviewCriteria,
    inferenceEligible,
    matrixItems,
    monthDisplayLabel,
    nextEnabledTabIndex,
    normalizeGeographyCells,
    normalizeAnalysisState,
    normalizeBaselineMode,
    normalizeSummary,
    normalizeView,
    orderedSeriesDisplay,
    previewForDatum,
    patternGroupsForDisplay,
    poissonCountInterval,
    projectedEqualAreaGeometryPath,
    proportionalTreemap,
    resolvedPatternChartId,
    readinessMatrix,
    relationshipMatrix,
    sampleEvenly,
    sampledHeatmapAxes,
    semanticAxisKind,
    semanticNumericValue,
    sortSemanticAxis,
    sourceBalancedDisplay,
    sourceCompositionDisplay,
    positiveSeriesMaximum,
  });
});

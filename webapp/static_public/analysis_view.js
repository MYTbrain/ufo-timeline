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

  function datumReference(item) {
    const value = firstDefined(item, ["reference", "referenceCount", "baseline", "expected", "referenceShare"], null);
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

  function intervalBounds(item) {
    const interval = firstDefined(item, ["interval", "effectInterval", "effect_interval", "confidenceInterval", "confidence_interval", "differenceInterval", "difference_interval", "oddsRatioInterval", "odds_ratio_interval"], null);
    if (Array.isArray(interval) && interval.length >= 2 && interval[0] != null && interval[1] != null) {
      return { lower: finiteNumber(interval[0]), upper: finiteNumber(interval[1]) };
    }
    if (isObject(interval)) {
      const lower = firstDefined(interval, ["lower", "low", "minimum", "min"], null);
      const upper = firstDefined(interval, ["upper", "high", "maximum", "max"], null);
      if (lower != null && upper != null) return { lower: finiteNumber(lower), upper: finiteNumber(upper) };
    }
    const lower = firstDefined(item, ["lower", "ciLower", "ci_lower"], null);
    const upper = firstDefined(item, ["upper", "ciUpper", "ci_upper"], null);
    return lower != null && upper != null
      ? { lower: finiteNumber(lower), upper: finiteNumber(upper) }
      : null;
  }

  function comparativeEffect(item, preferredKeys) {
    const explicit = firstDefined(item, asArray(preferredKeys).concat([
      "adjustedDifference", "adjusted_difference", "difference", "shareDifference", "share_difference",
      "log2Enrichment", "log2_enrichment", "commonOddsRatio", "common_odds_ratio", "oddsRatio", "odds_ratio",
      "standardizedResidual", "residual", "effect", "value",
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
    const interval = intervalBounds(item);
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

  function suppressionReason(item) {
    const explicitValue = firstDefined(item, ["suppressionReasons", "suppression_reasons", "suppressionReason", "suppression_reason", "reason"], "");
    const explicit = Array.isArray(explicitValue)
      ? explicitValue.map(humanizeEvidenceReason).filter(Boolean).join("; ")
      : humanizeEvidenceReason(explicitValue);
    const status = cleanText(firstDefined(item, ["displayStatus", "display_status", "suppressionStatus", "suppression_status", "status", "eligibility", "evidenceStatus", "evidence_status"], "")).toLowerCase();
    const suppressed = item && (
      item.suppressed === true ||
      item.qualified === false ||
      item.displayEligible === false ||
      status === "suppressed" ||
      status === "not_estimable" ||
      status === "not estimable"
    );
    return suppressed ? (explicit || status.replace(/_/g, " ") || "Insufficient support") : "";
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
      return Boolean(suppressionReason(item)) || effect !== 0 || active !== 0 || reference !== 0;
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
    const appendRow = function (section, item, index) {
      const interval = intervalBounds(item);
      rows.push({
        section,
        label: datumLabel(item, index),
        unit: firstDefined(item, ["unitOfAnalysis", "unit_of_analysis", "unit"], "reports"),
        active_n: firstDefined(item, ["activeCount", "active_count", "observedCount", "observed_count", "nearCount", "near_count", "observed", "count"], ""),
        reference_n: firstDefined(item, ["referenceCount", "reference_count", "expectedCount", "expected_count", "comparisonCount", "comparison_count", "reference", "expected"], ""),
        supported_active_n: firstDefined(item, ["supportedActiveN", "supported_active_n", "supportedCount", "supported_count", "supportedN", "supported_n"], ""),
        supported_reference_n: firstDefined(item, ["supportedReferenceN", "supported_reference_n"], ""),
        common_support_rate: firstDefined(item, ["commonSupportRate", "common_support_rate"], ""),
        adjusted_effect: comparativeEffect(item),
        interval_lower: interval ? interval.lower : "",
        interval_upper: interval ? interval.upper : "",
        p_value: firstDefined(item, ["pValue", "p_value", "p"], ""),
        q_value: firstDefined(item, ["qValue", "q_value", "q"], ""),
        covariates: firstDefined(item, ["covariates", "adjustmentCovariates", "adjustment_covariates"], []),
        source_stability: firstDefined(item, ["sourceStability", "source_stability"], ""),
        region_stability: firstDefined(item, ["regionStability", "region_stability"], ""),
        estimator_version: firstDefined(item, ["estimatorVersion", "estimator_version"], ""),
        artifact_hashes: firstDefined(item, ["artifactHashes", "artifact_hashes", "datasetHash", "dataset_hash"], ""),
        suppression_reason: suppressionReason(item),
      });
    };
    const visit = function (section, value) {
      if (Array.isArray(value)) {
        value.forEach(function (item, index) {
          if (!isObject(item)) return;
          appendRow(section, item, index);
          Object.keys(item).sort().forEach(function (key) {
            if (key === "summary" || key === "meta") return;
            const child = item[key];
            if (Array.isArray(child) || isObject(child)) {
              visit(section + "[" + index + "]." + key, child);
            }
          });
        });
        return;
      }
      if (!isObject(value)) return;
      Object.keys(value).sort().forEach(function (key) {
        if (key === "summary" || key === "meta") return;
        visit(section ? section + "." + key : key, value[key]);
      });
    };
    visit("", payload);
    return rows;
  }

  function buildEvidencePackage(result, meta) {
    const payload = isObject(result) ? result : {};
    const metadata = Object.assign({}, isObject(payload.meta) ? payload.meta : {}, isObject(meta) ? meta : {});
    return {
      schemaVersion: "ufo-timeline-analysis-evidence-v2",
      generatedAt: new Date().toISOString(),
      estimatorVersion: cleanText(firstDefined(metadata, ["estimatorVersion", "estimator_version"], firstDefined(payload, ["estimatorVersion", "estimator_version"], "not reported"))),
      baselineMode: cleanText(firstDefined(metadata, ["baselineMode", "baseline_mode"], firstDefined(payload.summary || {}, ["baselineMode", "baseline_mode"], "not reported"))),
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
      "schema_version", "generated_at", "baseline_mode", "package_estimator_version", "filter_snapshot", "package_artifact_hashes",
      "section", "label", "unit", "active_n", "reference_n", "supported_active_n", "supported_reference_n",
      "common_support_rate", "adjusted_effect", "interval_lower", "interval_upper", "p_value", "q_value", "covariates",
      "source_stability", "region_stability", "estimator_version", "artifact_hashes", "suppression_reason",
    ];
    const exportRows = rows.length ? rows : [{ section: "metadata", label: "No evidence rows" }];
    return [columns.join(",")].concat(exportRows.map(function (row) {
      const value = Object.assign({
        schema_version: metadata.schemaVersion,
        generated_at: metadata.generatedAt,
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
    return asArray(items).filter(function (item) {
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
      const match = /^ea12x24:(\d+):(\d+)$/.exec(String(item.row || item.key || ""));
      if (match) {
        return Object.assign({}, item, {
          row: classLabel + " · latitude band " + (Number(match[1]) + 1) + " · longitude band " + (Number(match[2]) + 1),
        });
      }
      return Object.assign({}, item, {
        row: classLabel + " · " + cleanText(firstDefined(item, ["row", "rowLabel"], "Unknown band"), "Unknown band"),
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
      "analysis-time-decades": "analysis-decade-chart",
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
    const displayedPeriods = sampleEvenly(periods, periodLimit);
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
      periodCount: periods.length,
      groupedSources,
      sampledPeriods: displayedPeriods.length < periods.length,
    };
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
        onSpatialEvidenceRequested: typeof config.onSpatialEvidenceRequested === "function" ? config.onSpatialEvidenceRequested : null,
        getFilterSnapshot: typeof config.getFilterSnapshot === "function" ? config.getFilterSnapshot : null,
      };
      this.listeners = [];
      this.currentPreview = null;
      this.previousPreviewFocus = null;
      this.previewPending = false;
      this.analysisInitialized = false;
      this.analysisState = "loading";
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
      this.setBaselineMode(this.els.baseline.value, { notify: false });
      this.setActiveView("map", { force: true, silent: true, source: "initial" });
    }

    _listen(element, eventName, handler) {
      if (!element || typeof element.addEventListener !== "function") return;
      element.addEventListener(eventName, handler);
      this.listeners.push([element, eventName, handler]);
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
    }

    _sectionLinkElements() {
      if (!this.els.sectionNav) return [];
      if (typeof this.els.sectionNav.querySelectorAll === "function") {
        return Array.from(this.els.sectionNav.querySelectorAll('a[href^="#analysis-section-"]'));
      }
      return Array.prototype.slice.call(this.els.sectionNav.children || []).filter(function (child) {
        return child && child.tagName && child.tagName.toLowerCase() === "a"
          && /^#analysis-section-/.test(cleanText(child.getAttribute && child.getAttribute("href")));
      });
    }

    _sectionIdForLink(link) {
      return cleanText(link && link.getAttribute && link.getAttribute("href")).replace(/^#/, "");
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
      this.sectionEntries.forEach((entry) => {
        this._listen(entry.link, "click", (event) => {
          if (event && typeof event.preventDefault === "function") event.preventDefault();
          this.navigateToSection(entry.id, { updateHash: true, focus: true, source: "section-link" });
        });
      });
      this._listen(this.els.sectionNav, "keydown", (event) => this._handleSectionNavKeydown(event));
      if (this.IntersectionObserver) {
        this.sectionObserver = new this.IntersectionObserver((entries) => this._handleSectionIntersections(entries), {
          root: null,
          rootMargin: "-96px 0px -62% 0px",
          threshold: [0, 0.01, 0.2, 0.6],
        });
        this.sectionEntries.forEach((entry) => this.sectionObserver.observe(entry.section));
      } else if (this.documentView) {
        this._listen(this.documentView, "scroll", () => this._scheduleSectionScrollspy());
      }
      if (this.documentView) {
        // IntersectionObserver does not fire merely because a horizontal
        // navigation rail became narrower. Re-run the geometry pass on every
        // viewport resize so the single active link is kept in view on mobile
        // rotation and responsive-pane changes.
        this._listen(this.documentView, "resize", () => this._scheduleSectionScrollspy());
        this._listen(this.documentView, "hashchange", () => this._honorAnalysisHash({ focus: false }));
      }
      this._setActiveSection(this.sectionEntries[0].id, { scrollLink: false });
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
      if (entry.link && typeof entry.link.focus === "function") entry.link.focus();
      this.navigateToSection(entry.id, { updateHash: true, focus: false, source: "section-keyboard" });
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
        this._updateSectionFromGeometry();
      };
      if (this.requestRenderFrame) this.sectionScrollFrame = this.requestRenderFrame(run);
      else run();
    }

    _updateSectionFromGeometry() {
      let selected = this.sectionEntries[0] || null;
      this.sectionEntries.forEach(function (entry) {
        if (!entry.section || typeof entry.section.getBoundingClientRect !== "function") return;
        if (entry.section.getBoundingClientRect().top <= 112) selected = entry;
      });
      if (selected) this._setActiveSection(selected.id, { source: "scrollspy-fallback" });
    }

    _setActiveSection(sectionId, options) {
      if (!this.sectionEntries.some(function (entry) { return entry.id === sectionId; })) return false;
      const previousSectionId = this.activeSectionId;
      this.activeSectionId = sectionId;
      this.sectionEntries.forEach(function (entry) {
        const active = entry.id === sectionId;
        if (entry.link.classList) entry.link.classList.toggle("is-active", active);
        if (active) entry.link.setAttribute("aria-current", "location");
        else entry.link.removeAttribute("aria-current");
      });
      const activeEntry = this.sectionEntries.find(function (entry) { return entry.id === sectionId; });
      const nav = this.els.sectionNav;
      if ((!options || options.scrollLink !== false) && activeEntry && activeEntry.link && nav &&
          typeof activeEntry.link.getBoundingClientRect === "function" && typeof nav.getBoundingClientRect === "function") {
        const linkRect = activeEntry.link.getBoundingClientRect();
        const navRect = nav.getBoundingClientRect();
        let nextScrollLeft = null;
        if (linkRect.left < navRect.left + 8) {
          nextScrollLeft = Math.max(0, Number(nav.scrollLeft || 0) - ((navRect.left + 8) - linkRect.left));
        } else if (linkRect.right > navRect.right - 8) {
          nextScrollLeft = Number(nav.scrollLeft || 0) + (linkRect.right - (navRect.right - 8));
        }
        if (nextScrollLeft != null) {
          if (typeof nav.scrollTo === "function") {
            nav.scrollTo({ left: nextScrollLeft, behavior: this._prefersReducedMotion() ? "auto" : "smooth" });
          } else {
            nav.scrollLeft = nextScrollLeft;
          }
        }
      }
      if (previousSectionId !== sectionId && this.callbacks.onSectionActivate) {
        this.callbacks.onSectionActivate({
          sectionId,
          sectionKey: sectionId.replace(/^analysis-section-/, ""),
          source: cleanText(options && options.source, "scrollspy"),
        });
      }
      if (sectionId === "analysis-section-spatial") this._requestSpatialEvidence("section-visible");
      return true;
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
      this._setActiveSection(sectionId, { source: cleanText(config.source, "navigation") });
      if (config.updateHash !== false) this._replaceHash(sectionId);
      if (entry.section && typeof entry.section.scrollIntoView === "function") {
        // Section height changes while progressive charts render. Immediate
        // alignment is deterministic and refreshSectionNavigation reapplies it
        // after the final layout; a long smooth scroll is otherwise cancelled
        // by those layout changes before reaching distant sections.
        entry.section.scrollIntoView({ block: "start", behavior: "auto" });
      }
      if (config.focus !== false && entry.section && typeof entry.section.focus === "function") {
        entry.section.focus({ preventScroll: true });
      }
      if (this.documentView && typeof this.documentView.setTimeout === "function") {
        if (this.anchorCorrectionTimerId != null && typeof this.documentView.clearTimeout === "function") {
          this.documentView.clearTimeout(this.anchorCorrectionTimerId);
        }
        this.anchorCorrectionTimerId = this.documentView.setTimeout(() => {
          this.anchorCorrectionTimerId = null;
          if (this.activeView !== "analysis") return;
          const correctionEntry = this.sectionEntries.find(function (candidate) { return candidate.id === sectionId; });
          if (!correctionEntry || !correctionEntry.section || typeof correctionEntry.section.scrollIntoView !== "function") return;
          correctionEntry.section.scrollIntoView({ block: "start", behavior: "auto" });
          this._setActiveSection(sectionId, { source: "layout-correction" });
        }, 700);
      }
      return true;
    }

    _honorAnalysisHash(options) {
      const hash = cleanText(this.documentView && this.documentView.location && this.documentView.location.hash).replace(/^#/, "");
      if (!hash || !/^analysis-section-/.test(hash)) return false;
      return this.navigateToSection(hash, Object.assign({ updateHash: false, focus: false }, options || {}));
    }

    refreshSectionNavigation(options) {
      if (this.sectionObserver) {
        this.sectionEntries.forEach((entry) => {
          this.sectionObserver.unobserve(entry.section);
          this.sectionObserver.observe(entry.section);
        });
      }
      this._updateSectionFromGeometry();
      if (options && options.honorHash) this._honorAnalysisHash({ focus: Boolean(options.focus) });
    }

    _requestSpatialEvidence(origin) {
      if (this.spatialRequested) return false;
      this.setSectionState("spatial", "loading", "Loading qualified point-based spatial evidence…");
      if (this.callbacks.onSpatialEvidenceRequested) {
        this.callbacks.onSpatialEvidenceRequested({ origin: cleanText(origin, "analysis"), requestedDomains: ["cooccurrence", "facilities", "cross_domain_readiness"] });
      }
      return true;
    }

    setSectionState(sectionValue, stateValue, messageValue) {
      const section = cleanText(sectionValue).toLowerCase().replace(/^analysis-section-/, "");
      const state = cleanText(stateValue, "ready").toLowerCase();
      if (section !== "spatial") return false;
      const status = this.els.spatialStatus;
      if (state === "error") this.spatialRequested = false;
      else if (state === "loading" || state === "ready") this.spatialRequested = true;
      if (status) {
        status.setAttribute("data-analysis-state", state);
        status.setAttribute("aria-busy", state === "loading" ? "true" : "false");
        status.classList.toggle("is-error", state === "error");
        status.classList.toggle("is-loading", state === "loading");
        status.textContent = cleanText(messageValue, state === "error"
          ? "Spatial evidence could not be loaded. Select Spatial Evidence to retry."
          : (state === "loading" ? "Loading qualified point-based spatial evidence…" : "Spatial evidence artifacts ready."));
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
      const target = this.document.getElementById(targetId);
      if (target && typeof target.scrollIntoView === "function") {
        target.scrollIntoView({ block: "start", behavior: this._prefersReducedMotion() ? "auto" : "smooth" });
      }
      this._replaceHash(targetId);
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
      this.els.baseline.value = nextMode;
      this.els.baselineNote.textContent = BASELINE_NOTES[nextMode];
      this.els.baselineNote.classList.toggle("is-descriptive-warning", nextMode === "full_catalog");
      if ((!options || options.notify !== false) && nextMode !== previousMode && this.callbacks.onBaselineChange) {
        this.callbacks.onBaselineChange({ baselineMode: nextMode, previousMode });
      }
      return nextMode;
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
    }

    _completeRenderSequence(generation, fallbackState) {
      if (generation !== this.renderGeneration) return false;
      this.renderFrameId = null;
      this.renderPending = false;
      const finalState = this.renderCompletionState || fallbackState;
      const finalMessage = this.renderCompletionMessage;
      this.renderCompletionState = null;
      this.renderCompletionMessage = "";
      this._applyAnalysisState(finalState, finalMessage);
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

    _renderForestPlot(chartId, items, summary, options) {
      const config = options || {};
      const data = asArray(items).filter(isObject).slice(0, config.limit || 24);
      const container = this._prepareChart(chartId, data, summary, config.emptyMessage || "No qualified adjusted effects are available for this cohort.");
      if (!container) return;
      const values = [];
      data.forEach(function (item) {
        const effect = comparativeEffect(item, config.valueKeys);
        const interval = intervalBounds(item);
        values.push(Math.abs(effect));
        if (interval) values.push(Math.abs(interval.lower), Math.abs(interval.upper));
      });
      const extent = Math.max(0.01, ...values);
      const position = function (value) {
        return Math.max(0, Math.min(100, 50 + ((finiteNumber(value) / (extent * 2)) * 100)));
      };
      const legend = this._element("p", "analysis-forest-legend", "Point = adjusted effect · line = 95% interval · center = no difference · hatched rows are suppressed");
      container.appendChild(legend);
      const list = this._element("div", "analysis-forest-list");
      const tableRows = [];
      data.forEach((item, index) => {
        const label = datumLabel(item, index);
        const effect = comparativeEffect(item, config.valueKeys);
        const interval = intervalBounds(item) || { lower: effect, upper: effect };
        const itemSuppression = suppressionReason(item);
        const selectable = !itemSuppression && datumHasPreview(item);
        const row = this._element(selectable ? "button" : "div", "analysis-forest-row");
        if (selectable) row.type = "button";
        if (itemSuppression) row.classList.add("is-suppressed");
        if (effect < 0) row.classList.add("is-negative");
        row.appendChild(this._element("span", "analysis-forest-label", label));
        const track = this._element("span", "analysis-forest-track");
        const intervalMark = this._element("span", "analysis-forest-interval");
        const lower = Math.min(interval.lower, interval.upper);
        const upper = Math.max(interval.lower, interval.upper);
        intervalMark.style.setProperty("--analysis-ci-left", position(lower).toFixed(2) + "%");
        intervalMark.style.setProperty("--analysis-ci-width", Math.max(0.8, position(upper) - position(lower)).toFixed(2) + "%");
        const point = this._element("span", "analysis-forest-point");
        point.style.setProperty("--analysis-point-left", position(effect).toFixed(2) + "%");
        track.appendChild(intervalMark);
        track.appendChild(point);
        row.appendChild(track);
        const qValue = firstDefined(item, ["qValue", "q_value", "q"], null);
        const valueLabel = formatSignedPercent(effect) + " · 95% CI " + formatPercentInterval(interval)
          + (qValue == null ? "" : " · q=" + formatDecimal(qValue, 3));
        row.appendChild(this._element("span", "analysis-forest-value", valueLabel));
        if (itemSuppression) {
          row.appendChild(this._element("span", "analysis-forest-status", "Suppressed · " + itemSuppression));
        }
        row.setAttribute("aria-label", label + ": " + valueLabel + (itemSuppression ? ". Suppressed: " + itemSuppression + "." : (selectable ? ". Preview this selection." : "")));
        if (selectable) this._activatePreview(row, item, label, summary, config.defaultKind);
        list.appendChild(row);
        tableRows.push([
          label,
          formatSignedPercent(effect),
          formatPercentInterval(interval),
          qValue == null ? "—" : formatDecimal(qValue, 3),
          suppressionReason(item) || "Qualified",
        ]);
      });
      container.appendChild(list);
      this._appendDataTable(container, config.caption || "Adjusted effects and uncertainty", ["Category", "Adjusted effect", "95% interval", "q-value", "Status"], tableRows);
    }

    _renderBars(chartId, items, summary, options) {
      const config = options || {};
      const data = asArray(items).slice(0, config.limit || 40);
      const container = this._prepareChart(chartId, data, summary, config.emptyMessage);
      if (!container) return;
      const magnitudes = data.map(function (item) {
        return Math.max(Math.abs(datumValue(item, config.valueKeys)), config.hideReference ? 0 : Math.abs(datumReference(item) || 0));
      });
      const maximum = config.scaleActual ? positiveSeriesMaximum(magnitudes) : Math.max(1, ...magnitudes);
      const includeReference = !config.hideReference && data.some(function (item) { return datumReference(item) != null; });
      const hasIntervals = data.some(function (item) {
        return firstDefined(item, ["interval", "confidenceInterval", "intervalLabel"], null) != null;
      });
      const list = this._element("ol", "analysis-bar-list");
      const rows = [];
      data.forEach((item, index) => {
        const label = datumLabel(item, index);
        const value = datumValue(item, config.valueKeys);
        const reference = config.hideReference ? null : datumReference(item);
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
      const hasReference = display.rows.some(function (row) { return row.referenceShare > 0 || row.referenceCount > 0; });

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

        appendCohortRow("Active", "activeShare", "activeCount", true);
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
        "Each cohort row is a 100% stacked source composition; labels retain the worker-provided cohort shares and absolute report counts."
      ));
      this._appendDataTable(
        container,
        config.caption || "Source composition by period",
        ["Period", "Source", "Active share", "Active reports", "Reference share", "Reference reports"],
        display.rows.map(function (row) {
          return [
            row.period,
            row.source,
            formatPercent(row.activeShare),
            formatCount(row.activeCount),
            formatPercent(row.referenceShare),
            formatCount(row.referenceCount),
          ];
        })
      );
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
      let displaySampled = false;
      const series = this._normalizeSeries(items).map(function (seriesItem) {
        const points = sampleEvenly(seriesItem.points, SERIES_POINT_LIMIT);
        if (points.length < seriesItem.points.length) displaySampled = true;
        return Object.assign({}, seriesItem, { points });
      });
      const pointCount = series.reduce(function (count, item) { return count + item.points.length; }, 0);
      const container = this._prepareChart(chartId, pointCount ? [true] : [], summary, config.emptyMessage);
      if (!container) return;
      const formatValue = config.valueFormat === "percent" ? formatPercent : function (number) { return formatDecimal(number, 3); };
      const width = 720;
      const height = 270;
      const padding = { top: 18, right: 18, bottom: 48, left: 58 };
      const labels = [];
      series.forEach(function (item) {
        item.points.forEach(function (point, index) {
          const label = datumLabel(point, index);
          if (labels.indexOf(label) === -1) labels.push(label);
        });
      });
      const values = [];
      series.forEach(function (item) {
        item.points.forEach(function (point) { values.push(Math.max(0, datumValue(point))); });
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
        "aria-label": config.ariaLabel || "Trend chart for the active and reference cohorts",
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
      const tableRows = [];
      series.forEach((seriesItem, seriesIndex) => {
        const colorIndex = seriesItem.colorIndex != null && Number.isFinite(Number(seriesItem.colorIndex)) ? Number(seriesItem.colorIndex) : seriesIndex;
        const color = CHART_COLORS[colorIndex % CHART_COLORS.length];
        const referenceSeries = Boolean(seriesItem.reference) || /(^|\u00b7)\s*reference\b/i.test(seriesItem.label);
        const sorted = seriesItem.points.slice().sort(function (left, right) {
          return labels.indexOf(datumLabel(left, 0)) - labels.indexOf(datumLabel(right, 0));
        });
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
            "aria-label": seriesItem.label + ", " + label + ": " + formatValue(value),
          });
          const title = this._svgElement("title");
          title.textContent = seriesItem.label + " · " + label + ": " + formatValue(value);
          circle.appendChild(title);
          this._activatePreview(circle, point, label, summary, config.defaultKind);
          svg.appendChild(circle);
          tableRows.push([label, seriesItem.label, formatValue(value)]);
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
      this._appendDataTable(container, config.caption || "Trend values", ["Period", "Series", "Value"], tableRows);
      if (displaySampled) {
        this._appendChartPolicy(
          chartId,
          "Display is evenly sampled to at most " + SERIES_POINT_LIMIT + " points per series, retaining the first and last points; calculations, cohort sizes, and statistical tests are unchanged."
        );
      }
    }

    _renderHeatmap(chartId, value, summary, options) {
      const config = options || {};
      const display = heatmapDisplayItems(value, config.valueKeys);
      const fullData = display.data;
      const container = this._prepareChart(chartId, fullData, summary, config.emptyMessage || "No supported cells are available for this comparison.");
      if (!container) return;
      const formatValue = config.valueFormat === "percent" ? formatPercent : function (number) { return formatDecimal(number, 2); };
      const rows = display.rows;
      const columns = display.columns;
      const displayedRows = rows.slice(0, HEATMAP_AXIS_LIMIT);
      const displayedColumns = columns.slice(0, HEATMAP_AXIS_LIMIT);
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
      container.appendChild(this._element("p", "analysis-heatmap-legend", "Blue = above reference · amber = below reference · hatched = suppressed by evidence gates"));
      const tableWrap = this._element("div", "analysis-heatmap-scroll");
      const table = this._element("table", "analysis-heatmap-table");
      const caption = this._element("caption", "sr-only", config.caption || "Heatmap values");
      table.appendChild(caption);
      const head = this._element("thead");
      const headRow = this._element("tr");
      headRow.appendChild(this._element("th", "", config.rowHeading || "Group"));
      displayedColumns.forEach((column) => headRow.appendChild(this._element("th", "", column)));
      head.appendChild(headRow);
      table.appendChild(head);
      const body = this._element("tbody");
      displayedRows.forEach((row) => {
        const tableRow = this._element("tr");
        tableRow.appendChild(this._element("th", "", row));
        displayedColumns.forEach((column) => {
          const cell = this._element("td");
          const item = lookup.get(row + "\u0000" + column);
          if (!item) {
            cell.appendChild(this._element("span", "analysis-heat-cell is-missing", "Not tested"));
          } else {
            const valueNumber = comparativeEffect(item, config.valueKeys);
            const reason = suppressionReason(item);
            const selectable = !reason && datumHasPreview(item);
            const formattedValue = reason ? "Suppressed" : formatValue(valueNumber);
            const mark = this._element(selectable ? "button" : "span", "analysis-heat-cell", formattedValue);
            if (selectable) mark.type = "button";
            mark.style.setProperty("--analysis-heat-percent", (12 + (Math.min(1, Math.abs(valueNumber) / maximum) * 74)).toFixed(2) + "%");
            if (valueNumber < 0) mark.classList.add("is-negative");
            if (reason) mark.classList.add("is-suppressed");
            mark.setAttribute("aria-label", row + ", " + column + ": " + formattedValue + (reason ? ". " + reason + "." : "") + (selectable ? ". Preview this selection." : ""));
            if (selectable) this._activatePreview(mark, item, row + " / " + column, summary, config.defaultKind);
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
            + HEATMAP_CELL_LIMIT + " cells); calculations and evidence gates use every cell."
        );
      }
      this._appendLazyDataTable(
        container,
        (config.caption || "Heatmap") + " complete qualified data",
        [config.rowHeading || "Group", "Column", "Effect", "Active n", "Reference n", "Status"],
        fullData.map(function (item) {
          return [
            cleanText(firstDefined(item, ["row", "rowLabel", "group", "category"], "All"), "All"),
            cleanText(firstDefined(item, ["column", "columnLabel", "period", "month", "year", "label"], "Value"), "Value"),
            formatValue(comparativeEffect(item, config.valueKeys)),
            formatCount(firstDefined(item, ["activeCount", "active_count", "observed", "count"], null)),
            formatCount(firstDefined(item, ["referenceCount", "reference_count", "reference", "expected"], null)),
            suppressionReason(item) || "Qualified",
          ];
        })
      );
      const peak = data.slice().filter(function (item) { return !suppressionReason(item); }).sort(function (left, right) {
        return Math.abs(comparativeEffect(right, config.valueKeys)) - Math.abs(comparativeEffect(left, config.valueKeys));
      })[0];
      if (peak) {
        const peakRow = cleanText(firstDefined(peak, ["row", "rowLabel", "group", "category"], "All"));
        const peakColumn = cleanText(firstDefined(peak, ["column", "columnLabel", "period", "month", "year", "label"], "Value"));
        container.appendChild(this._element("p", "analysis-chart-summary", "Largest displayed qualified magnitude: " + peakRow + " / " + peakColumn + " (" + formatValue(comparativeEffect(peak, config.valueKeys)) + ")."));
      }
    }

    _renderEqualAreaMap(chartId, value, summary, options) {
      const config = options || {};
      const sourceItems = asArray(value).filter(function (item) {
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
          group = { coordinateClass, latIndex, lonIndex, activeCount: 0, referenceCount: 0, support: 0, weightedEffect: 0, weightedLog2: 0, log2Support: 0, items: [], preview, patch: firstDefined(item, ["patch"], preview && preview.patch), area: firstDefined(item, ["area"], preview && preview.area) };
          groups.set(key, group);
        }
        const active = nonnegativeNumber(firstDefined(item, ["activeCount", "active_count", "observed", "count"], 0));
        const reference = nonnegativeNumber(firstDefined(item, ["referenceCount", "reference_count", "reference", "expected"], 0));
        const support = Math.max(1, active + reference);
        group.activeCount += active;
        group.referenceCount += reference;
        group.support += support;
        group.weightedEffect += comparativeEffect(item, config.valueKeys) * support;
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
          log2Enrichment: group.log2Support ? group.weightedLog2 / group.log2Support : null,
          adjustedActiveShare: firstDefined(evidenceItem, ["adjustedActiveShare", "adjusted_active_share"], null),
          adjustedReferenceShare: firstDefined(evidenceItem, ["adjustedReferenceShare", "adjusted_reference_share"], null),
          adjustedDifference: firstDefined(evidenceItem, ["adjustedDifference", "adjusted_difference"], null),
          differenceInterval: firstDefined(evidenceItem, ["differenceInterval", "difference_interval", "effectInterval", "effect_interval", "interval"], null),
          qValue: firstDefined(evidenceItem, ["qValue", "q_value", "q"], null),
          commonSupportRate: firstDefined(evidenceItem, ["commonSupportRate", "common_support_rate"], null),
          supportedActiveN: firstDefined(evidenceItem, ["supportedActiveN", "supported_active_n"], null),
          supportedReferenceN: firstDefined(evidenceItem, ["supportedReferenceN", "supported_reference_n"], null),
          suppressed: group.items.every(function (item) { return Boolean(suppressionReason(item)); }),
          suppressionReason: group.items.map(suppressionReason).filter(Boolean)[0] || "",
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
        { key: "difference", label: "Adjusted difference" },
        { key: "log2", label: "Log₂ enrichment" },
        { key: "count", label: "Active counts" },
      ];
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
      const classes = Array.from(new Set(cells.map(function (cell) { return cell.coordinateClass; }))).sort();
      classes.forEach((coordinateClass, facetIndex) => {
        const facet = this._element("section", "analysis-equal-area-facet");
        facet.appendChild(this._element("h5", "", coordinateClass.replace(/_/g, " ")));
        const svg = this._svgElement("svg", { class: "analysis-equal-area-svg", viewBox: "0 0 600 300", role: "img", "aria-label": coordinateClass + " equal-area world grid" });
        const defs = this._svgElement("defs", {});
        const patternId = "analysis-map-hatch-" + facetIndex;
        const pattern = this._svgElement("pattern", { id: patternId, width: 8, height: 8, patternUnits: "userSpaceOnUse", patternTransform: "rotate(45)" });
        pattern.appendChild(this._svgElement("line", { x1: 0, y1: 0, x2: 0, y2: 8, stroke: "currentColor", "stroke-width": 2, opacity: 0.35 }));
        defs.appendChild(pattern);
        svg.appendChild(defs);
        cells.filter(function (cell) { return cell.coordinateClass === coordinateClass; }).forEach((cell) => {
          const rect = this._svgElement("rect", {
            x: cell.lonIndex * 50,
            y: (5 - cell.latIndex) * 50,
            width: 50,
            height: 50,
            class: "analysis-map-cell " + (cell.suppressed ? "is-suppressed" : "is-qualified"),
          });
          if (cell.suppressed) rect.setAttribute("fill", "url(#" + patternId + ")");
          const label = "Latitude band " + (cell.latIndex + 1) + ", longitude band " + (cell.lonIndex + 1);
          rect.setAttribute("aria-label", label);
          rect.appendChild(this._svgElement("title", {}));
          rect.children[0].textContent = label;
          if (!cell.suppressed && (cell.patch || cell.area)) {
            this._activatePreview(rect, cell, label, summary, "area");
          }
          mapMarks.push({ rect, cell, patternId, label });
          svg.appendChild(rect);
        });
        facet.appendChild(svg);
        facets.appendChild(facet);
      });
      container.appendChild(facets);
      const updateMapMode = (modeKey) => {
        const modeValue = function (cell) {
          if (modeKey === "count") return cell.activeCount;
          if (modeKey === "log2") return Number.isFinite(Number(cell.log2Enrichment)) ? Number(cell.log2Enrichment) : 0;
          return cell.effect;
        };
        const maximum = Math.max(Number.EPSILON, ...cells.filter(function (cell) { return !cell.suppressed; }).map(function (cell) { return Math.abs(modeValue(cell)); }));
        modeButtons.forEach(function (entry) { entry.button.setAttribute("aria-pressed", entry.mode.key === modeKey ? "true" : "false"); });
        mapLegend.textContent = modeKey === "count"
          ? "Active report counts · darker cells contain more qualified reports · hatched insufficient support"
          : (modeKey === "log2"
            ? "Log₂ active/reference enrichment · blue above reference · amber below reference · hatched insufficient support"
            : "Signed adjusted share difference · blue above reference · amber below reference · hatched insufficient support");
        mapMarks.forEach(function (mark) {
          const valueNumber = modeValue(mark.cell);
          if (mark.cell.suppressed) {
            mark.rect.setAttribute("fill", "url(#" + mark.patternId + ")");
            mark.rect.setAttribute("fill-opacity", "1");
          } else {
            mark.rect.setAttribute("fill", modeKey !== "count" && valueNumber < 0 ? "#d18a34" : "#168aad");
            mark.rect.setAttribute("fill-opacity", String(0.16 + (0.78 * Math.min(1, Math.abs(valueNumber) / maximum))));
          }
          const valueLabel = mark.cell.suppressed
            ? "suppressed, " + mark.cell.suppressionReason
            : (modeKey === "count" ? formatCount(valueNumber) + " active reports" : (modeKey === "log2" ? formatDecimal(valueNumber, 2) + " log2 enrichment" : formatSignedPercent(valueNumber)));
          const accessible = mark.label + ": " + valueLabel + "; active n=" + formatCount(mark.cell.activeCount) + ", reference n=" + formatCount(mark.cell.referenceCount);
          mark.rect.setAttribute("aria-label", accessible);
          if (mark.rect.children && mark.rect.children[0]) mark.rect.children[0].textContent = accessible;
        });
      };
      modeButtons.forEach((entry) => entry.button.addEventListener("click", function () { updateMapMode(entry.mode.key); }));
      updateMapMode("difference");
      this._appendDataTable(container, "Equal-area geography evidence", ["Coordinate class", "Latitude band", "Longitude band", "Adjusted difference", "Log2 enrichment", "Active n", "Reference n", "Status"], cells.map(function (cell) {
        return [cell.coordinateClass, cell.latIndex + 1, cell.lonIndex + 1, formatSignedPercent(cell.effect), cell.log2Enrichment == null ? "—" : formatDecimal(cell.log2Enrichment, 2), formatCount(cell.activeCount), formatCount(cell.referenceCount), cell.suppressed ? cell.suppressionReason : "Qualified"];
      }));
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
      const source = isObject(value) ? value : {};
      const groups = [];
      [
        { key: "crossSource", alias: "cross_source", label: "Cross-source" },
        { key: "sameSource", alias: "same_source", label: "Same-source" },
      ].forEach(function (lane) {
        firstArray(source, [lane.key, lane.alias]).forEach(function (windowResult, windowIndex) {
          const windowMetadata = isObject(windowResult.window) ? windowResult.window : {};
          const windowLabel = cleanText(firstDefined(windowResult, ["label", "windowLabel", "window_label"], firstDefined(windowMetadata, ["label", "windowLabel", "window_label"], "Window " + (windowIndex + 1))));
          const groupLabel = lane.label + " · " + windowLabel + (lane.key === "crossSource" && windowMetadata.primary === true ? " · primary" : " · sensitivity");
          const status = cleanText(firstDefined(windowResult, ["status"], ""));
          const reasons = firstDefined(windowResult, ["suppressionReasons", "suppression_reasons"], []);
          const items = firstArray(windowResult, ["cells", "categories", "effects", "findings"]).map(function (item, index) {
            const left = cleanText(firstDefined(item, ["row", "craftA", "craft_a", "sourceCategory", "source_category"], ""));
            const right = cleanText(firstDefined(item, ["column", "craftB", "craft_b", "neighborCategory", "neighbor_category"], ""));
            return Object.assign({}, item, {
              label: cleanText(firstDefined(item, ["label", "name"], left && right ? left + " × " + right : "Pair " + (index + 1))),
              status: cleanText(firstDefined(item, ["status"], status)),
              suppressionReasons: firstDefined(item, ["suppressionReasons", "suppression_reasons"], reasons),
            });
          });
          groups.push({ label: groupLabel, value: windowResult, items });
        });
      });
      this._renderEvidenceGroupSelector(chartId, groups, summary, options);
    }

    _renderFacilityEvidence(chartId, value, summary, options) {
      const source = isObject(value) ? value : {};
      const groups = [];
      const primary = isObject(source.primary) ? source.primary : source;
      groups.push({ label: "Temporally active · 25 km vs 100–250 km · primary", value: primary, items: firstArray(primary, ["cells", "categories", "effects", "findings"]) });
      const negative = firstDefined(source, ["inactiveNegativeControl", "inactive_negative_control"], null);
      if (isObject(negative)) groups.push({ label: "Inactive at event · negative control", value: negative, items: firstArray(negative, ["cells", "categories", "effects", "findings"]) });
      firstArray(source, ["sensitivity", "sensitivityViews", "sensitivity_views"]).forEach(function (lane, index) {
        const radius = firstDefined(lane, ["nearRadiusKm", "near_radius_km"], [10, 50, 100][index]);
        groups.push({ label: formatDecimal(radius, 0) + " km active-facility radius · sensitivity", value: lane, items: firstArray(lane, ["cells", "categories", "effects", "findings"]) });
      });
      this._renderEvidenceGroupSelector(chartId, groups, summary, options);
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
      const source = Array.isArray(value) ? value : firstArray(value, ["domains", "readiness", "rows", "items"]);
      const fallback = isObject(value) && !source.length ? Object.keys(value).filter(function (key) { return isObject(value[key]); }).map(function (key) {
        return Object.assign({ label: key }, value[key]);
      }) : source;
      const container = this._prepareChart(chartId, fallback, summary, config.emptyMessage || "No cross-domain result is estimable. Readiness details will appear after provenance checks complete.");
      if (!container) return;
      const grid = this._element("div", "analysis-readiness-grid");
      fallback.forEach((item, index) => {
        const card = this._element("article", "analysis-readiness-item");
        card.appendChild(this._element("strong", "", datumLabel(item, index)));
        const eligible = firstDefined(item, ["eligibleN", "eligible_n", "eligibleCount", "eligible_count", "qualifiedCount", "qualified_count"], null);
        const total = firstDefined(item, ["totalN", "total_n", "totalCount", "total_count", "count"], null);
        const reasonValue = firstDefined(item, ["reasons", "suppressionReasons", "suppression_reasons", "message", "reason", "policyWarning", "policy_warning"], "Evidence gates have not reported a publishable association.");
        const reasonText = Array.isArray(reasonValue)
          ? reasonValue.map(humanizeEvidenceReason).filter(Boolean).join(" ")
          : humanizeEvidenceReason(reasonValue);
        card.appendChild(this._element("p", "", "Eligible " + formatCount(eligible) + " of " + formatCount(total) + ". " + reasonText));
        card.appendChild(this._element("span", "analysis-readiness-state", cleanText(firstDefined(item, ["status", "evidenceStatus", "evidence_status"], "Not estimable")).replace(/_/g, " ")));
        const releaseHash = cleanText(firstDefined(item, ["releaseHash", "release_hash", "artifactHash", "artifact_hash"], ""));
        if (releaseHash) card.appendChild(this._element("code", "analysis-readiness-hash", releaseHash));
        const detailValue = firstDefined(item, ["laneCounts", "lane_counts", "details", "counts"], null);
        const detailSource = isObject(detailValue) ? detailValue : item;
        if (isObject(detailSource)) {
          const detailDefinitions = [
            ["explicitSource", "Explicit-source"],
            ["computedCandidate", "Computed candidate"],
            ["analystReviewed", "Analyst-reviewed"],
            ["reconciledCurrent", "Reconciled current"],
            ["reconciledUnmapped", "Reconciled unmapped"],
            ["quarantinedSubject", "Quarantined subject"],
            ["quarantinedObject", "Quarantined object"],
            ["associationEligible", "Association eligible"],
          ];
          const metrics = this._element("dl", "analysis-readiness-metrics");
          detailDefinitions.forEach((definition) => {
            const snake = definition[0].replace(/[A-Z]/g, function (letter) { return "_" + letter.toLowerCase(); });
            const aliases = [definition[0], definition[0] + "N", snake, snake + "_n"];
            if (definition[0] === "reconciledUnmapped") aliases.push("reconciledUnmappedUfoN", "reconciled_unmapped_ufo_n");
            const detail = firstDefined(detailSource, aliases, null);
            if (detail == null) return;
            const wrapper = this._element("div");
            wrapper.appendChild(this._element("dt", "", definition[1]));
            wrapper.appendChild(this._element("dd", "", formatCount(detail)));
            metrics.appendChild(wrapper);
          });
          if ((metrics.children || []).length) card.appendChild(metrics);
        }
        grid.appendChild(card);
      });
      container.appendChild(grid);
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
      const crossDomainReadiness = firstDefined(spatial, ["crossDomainReadiness", "cross_domain_readiness", "readiness"], firstDefined(context, ["readiness", "crossDomainReadiness"], {}));
      const adaptiveTimeSeries = firstArray(time, ["series", "yearly", "trends"]);
      const annualTimeSeries = firstArray(time, ["annualSeries", "annual_series"]);
      const sourceBalanced = firstArray(time, ["sourceBalanced", "source_balanced"]);
      const sourceBalancedSeries = sourceBalancedDisplay(sourceBalanced, adaptiveTimeSeries);
      const bursts = firstArray(time, ["bursts", "qualifiedBursts", "qualified_bursts"]);
      return {
        overviewCoverage: firstArray(overview, ["eligibilityFunnel", "eligibility_funnel", "coverage", "coverageBars"]),
        overviewComparison: firstArray(overview, ["evidenceSummary", "evidence_summary", "adjustedEffects", "adjusted_effects", "comparison", "differences", "comparisonBars"]),
        timeSeries: sourceBalancedSeries.length ? sourceBalancedSeries : adaptiveTimeSeries,
        adaptiveTimeSeries,
        annualTimeSeries: annualTimeSeries.length ? annualTimeSeries : adaptiveTimeSeries,
        adaptiveBinning: isObject(time.adaptiveBinning) ? time.adaptiveBinning : (isObject(time.adaptive_binning) ? time.adaptive_binning : {}),
        decades: firstArray(time, ["decades", "decadeCounts", "byDecade"]),
        sourceBalanced: sourceBalancedSeries,
        sourceBalancedPolicy: cleanText(firstDefined(time, ["sourceBalancedPolicy", "source_balanced_policy"], "")),
        monthYear: firstDefined(time, ["monthByCraft", "month_by_craft", "monthYear", "monthly", "monthByYear"], []),
        rolling: firstArray(time, ["rolling", "observedReference", "bursts"]),
        bursts,
        burstPolicy: cleanText(firstDefined(time, ["burstPolicy", "burst_policy"], "")),
        craftDistribution: firstArray(craft, ["adjustedEffects", "adjusted_effects", "distribution", "ranked", "categories"]),
        reportTypes: firstArray(craft, ["reportTypes", "reportedTypes", "types"]),
        craftConfidence: firstArray(craft, ["confidence", "classificationConfidence", "craftConfidence"]),
        craftTrends: craftTrendSeries(firstDefined(craft, ["trends", "series", "byTime"], [])),
        craftEra: firstDefined(craft, ["byEra", "by_era", "eraHeatmap", "era_heatmap"], firstDefined(craft, ["trends", "byTime"], [])),
        craftGeography: firstDefined(craft, ["byGeography", "by_geography", "geographyHeatmap", "geography_heatmap"], []),
        craftResiduals: firstDefined(craft, ["residuals", "sourceDependence", "association"], []),
        craftSourceAssociation: firstDefined(craft, ["sourceAssociation", "source_association"], {}),
        geographyCells: geographyMapCells(firstDefined(geography, ["equalAreaMap", "equal_area_map", "equalArea", "equal_area", "cells", "grid", "density"], [])),
        geographyTime: normalizeGeographyCells(firstDefined(geography, ["byEra", "by_era", "byTime", "geographyTime", "timeGrid"], [])),
        cooccurrence: firstDefined(spatial, ["cooccurrence", "craftCooccurrence", "craft_cooccurrence"], {}),
        facilities: firstDefined(spatial, ["facility", "facilities", "facilityContext", "facility_context"], {}),
        crossDomainReadiness,
        cropReadiness: readinessForDomain(crossDomainReadiness, "crops"),
        animalReadiness: readinessForDomain(crossDomainReadiness, "animals"),
        relationshipReadiness: readinessForDomain(crossDomainReadiness, "relationships"),
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
      const enabled = contextData.enabled !== false;
      if (group) {
        group.hidden = false;
        setElementInert(group, false);
      }
      const domain = groupId.indexOf("animal") !== -1 ? "animals" : "crops";
      if (!enabled) {
        this.setContextControlState(domain, {
          enabled: false,
          status: "ready",
          message: cleanText(firstDefined(contextData, ["message", "statusMessage", "status_message"], "Excluded")),
        });
        if (status) status.textContent = label + " are excluded from the current Analysis computation.";
        return null;
      }
      this.setContextControlState(domain, {
        enabled: true,
        status: cleanText(firstDefined(contextData, ["status"], "ready")),
        message: cleanText(firstDefined(contextData, ["statusMessage", "status_message"], "Included")),
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
          : label + ": " + formatCount(activeCount) + " active · " + formatCount(referenceCount)
            + " reference · " + formatCount(projectionRows) + " total projection rows.";
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
      const summary = this.updateCohortSummary(summaryInput);
      const data = this._sectionData(payload);
      const jobs = [];
      jobs.push(() => this._renderBars("analysis-coverage-chart", data.overviewCoverage, summary, { caption: "Cohort coverage values" }));
      jobs.push(() => this._renderForestPlot("analysis-comparison-chart", data.overviewComparison, summary, {
        caption: "Active minus reference share differences with 95% intervals",
        defaultKind: "filter",
        valueKeys: ["difference", "value"],
      }));
      jobs.push(() => {
        this._renderSeries("analysis-time-series-chart", data.timeSeries, summary, {
          caption: "Reports by period",
          defaultKind: "filter",
          valueFormat: data.sourceBalanced.length ? "percent" : "decimal",
        });
        if (!data.sourceBalanced.length) return;
        this._appendChartPolicy(
          "analysis-time-series-chart",
          "Source-balanced exploratory trend. " + (data.sourceBalancedPolicy || "Each source contributes equal total weight through its within-source period shares.")
        );
        const adaptiveWidth = Number(firstDefined(data.adaptiveBinning, ["widthYears", "width_years"], 0));
        const adaptiveUnit = cleanText(firstDefined(data.adaptiveBinning, ["unit"], adaptiveWidth === 1 ? "year" : "period"));
        if (adaptiveWidth > 0) {
          this._appendChartPolicy(
            "analysis-time-series-chart",
            "Adaptive display uses " + (adaptiveWidth === 1 ? "annual" : formatCount(adaptiveWidth) + "-year")
              + " " + adaptiveUnit + " bins; structurally empty periods are omitted."
          );
        }
        const timeContainer = this.document.getElementById("analysis-time-series-chart");
        if (!timeContainer || !data.annualTimeSeries.length) return;
        const rawAnnualRows = sampleEvenly(data.annualTimeSeries, SERIES_POINT_LIMIT);
        this._appendDataTable(
          timeContainer,
          "Raw annual report counts",
          ["Period", "Active reports", "Reference reports"],
          rawAnnualRows.map(function (item, index) {
            return [datumLabel(item, index), formatCount(datumValue(item)), formatCount(datumReference(item))];
          })
        );
        if (rawAnnualRows.length < data.annualTimeSeries.length) {
          this._appendChartPolicy(
            "analysis-time-series-chart",
            "The raw annual accessible table is evenly sampled to " + SERIES_POINT_LIMIT + " periods; calculations and cohort totals still use every period."
          );
        }
      });
      jobs.push(() => this._renderBars("analysis-decade-chart", data.decades, summary, { caption: "Reports by decade", defaultKind: "filter" }));
      jobs.push(() => this._renderHeatmap("analysis-month-year-chart", data.monthYear, summary, { caption: "Recurring month by craft adjusted effects", rowHeading: "Craft", defaultKind: "filter", valueKeys: ["adjustedResidual", "adjusted_residual", "standardizedResidual", "residual", "difference", "value"] }));
      jobs.push(() => {
        this._renderSeries("analysis-rolling-chart", data.rolling, summary, { caption: "Rolling active and reference values", defaultKind: "filter" });
        this._appendChartPolicy("analysis-rolling-chart", "Descriptive rolling report counts; not a causal or incidence claim.");
      });
      jobs.push(() => this._clear(this.document.getElementById("analysis-bursts-chart")));
      jobs.push(() => {
        const comparative = data.craftDistribution.some(function (item) {
          return firstDefined(item, ["adjustedDifference", "adjusted_difference", "difference", "shareDifference", "share_difference", "interval"], null) != null;
        });
        if (comparative) this._renderForestPlot("analysis-craft-distribution-chart", data.craftDistribution, summary, { caption: "Adjusted craft share effects", defaultKind: "filter" });
        else this._renderBars("analysis-craft-distribution-chart", data.craftDistribution, summary, { caption: "Craft category distribution", defaultKind: "filter" });
      });
      jobs.push(() => this._renderBars("analysis-report-type-chart", data.reportTypes, summary, { caption: "Reported event types", defaultKind: "filter" }));
      jobs.push(() => this._renderBars("analysis-craft-confidence-chart", data.craftConfidence, summary, { caption: "Craft classification confidence" }));
      jobs.push(() => this._renderSeries("analysis-craft-trends-chart", data.craftTrends, summary, { caption: "Craft categories over time", defaultKind: "filter" }));
      jobs.push(() => this._renderHeatmap("analysis-craft-era-chart", data.craftEra, summary, { caption: "Craft by era adjusted residuals", rowHeading: "Craft", defaultKind: "filter", valueKeys: ["adjustedResidual", "adjusted_residual", "standardizedResidual", "residual", "difference", "value"] }));
      jobs.push(() => this._renderHeatmap("analysis-craft-geography-chart", data.craftGeography, summary, { caption: "Craft by geography adjusted residuals", rowHeading: "Craft", defaultKind: "filter", valueKeys: ["adjustedResidual", "adjusted_residual", "standardizedResidual", "residual", "difference", "value"] }));
      jobs.push(() => {
        this._renderHeatmap("analysis-craft-residual-chart", data.craftResiduals, summary, { caption: "Craft by source standardized residuals", rowHeading: "Craft", defaultKind: "filter", valueKeys: ["standardizedResidual", "residual"] });
        this._appendChartPolicy(
          "analysis-craft-residual-chart",
          cleanText(
            firstDefined(data.craftSourceAssociation, ["policyWarning", "policy_warning"], "Association residuals require expected cell counts of at least 10 and Cramer's V of at least 0.10.")
          )
        );
      });
      jobs.push(() => this._renderEqualAreaMap("analysis-geography-grid-chart", data.geographyCells, summary, { caption: "Equal-area adjusted report enrichment", defaultKind: "area", valueKeys: ["adjustedDifference", "adjusted_difference", "difference", "value"] }));
      jobs.push(() => this._renderHeatmap("analysis-geography-time-chart", data.geographyTime, summary, { caption: "Geography by era adjusted comparison", rowHeading: "Region", defaultKind: "area", valueKeys: ["adjustedDifference", "adjusted_difference", "standardizedResidual", "residual", "difference", "value"] }));
      jobs.push(() => this._renderCooccurrenceEvidence("analysis-cooccurrence-chart", data.cooccurrence, summary, { caption: "Point-based craft co-occurrence evidence", defaultKind: "filter", primaryCountLabel: "Observed", comparisonCountLabel: "Expected", primaryCountKeys: ["observedCount", "observed_count"], comparisonCountKeys: ["expectedCount", "expected_count"], effectLabel: "Log2 observed/expected enrichment", valueKeys: ["log2Enrichment", "log2_enrichment"], nullValue: 0, emptyMessage: "Not estimable until the qualified point-neighbor artifact and stratified null results are available." }));
      jobs.push(() => this._renderFacilityEvidence("analysis-facility-context-chart", data.facilities, summary, { caption: "Qualified facility-marker context evidence", defaultKind: "filter", primaryCountLabel: "Near band", comparisonCountLabel: "Comparison band", primaryCountKeys: ["nearCount", "near_count"], comparisonCountKeys: ["comparisonCount", "comparison_count"], effectLabel: "CMH odds ratio", valueKeys: ["commonOddsRatio", "common_odds_ratio", "oddsRatio", "odds_ratio"], nullValue: 1, emptyMessage: "Not estimable until facility precision, activity interval, and common-support gates pass." }));
      jobs.push(() => this._renderReadiness("analysis-cross-domain-readiness-chart", data.crossDomainReadiness, summary, { emptyMessage: "Crop and animal proximity remains not estimable until provenance, uncertainty, lineage, and sample gates pass." }));
      jobs.push(() => {
        if (this.els.spatialStatus) this.els.spatialStatus.textContent = data.spatialStatus || "Spatial evidence is associative, point-based, uncertainty-aware, and never uses chronology connectors.";
      });
      jobs.push(() => this._renderBars("analysis-source-composition-chart", data.sourceComposition, summary, { caption: "Source composition", defaultKind: "filter" }));
      jobs.push(() => this._renderStackedComposition("analysis-source-time-chart", data.sourceByTime, summary, {
        caption: "100% stacked source composition by period",
        defaultKind: "filter",
      }));
      jobs.push(() => this._renderHeatmap("analysis-quality-missingness-chart", data.missingness, summary, { caption: "Field missingness and coverage", rowHeading: "Field", defaultKind: "filter" }));
      jobs.push(() => {
        this._renderHeatmap("analysis-quality-audit-chart", data.audit, summary, { caption: "Classifier consistency audit", rowHeading: "Recorded class", defaultKind: "filter" });
        this._appendChartPolicy("analysis-quality-audit-chart", data.auditPolicy);
      });
      jobs.push(() => this._renderReadiness("analysis-relationship-readiness-chart", data.relationshipReadiness, summary, { emptyMessage: "Relationship reconciliation details load with Spatial Evidence; unresolved identifiers remain quarantined." }));

      const crops = data.crops;
      const cropSummary = this._setContextGroup(
        "analysis-crop-context",
        "analysis-crop-context-status",
        crops,
        "Crop-circle records"
      );
      if (cropSummary) {
        jobs.push(() => this._renderReadiness("analysis-crop-readiness-chart", data.cropReadiness, cropSummary, { emptyMessage: "Detailed crop-association readiness loads with Spatial Evidence; descriptive catalog health remains available here." }));
        jobs.push(() => this._renderSeries("analysis-crop-time-chart", firstArray(crops, ["time", "series", "yearly"]), cropSummary, { caption: "Crop-circle records by period" }));
        jobs.push(() => this._renderBars("analysis-crop-morphology-chart", firstArray(crops, ["morphology", "types", "distribution"]), cropSummary, { caption: "Provisional crop morphology" }));
        jobs.push(() => this._renderBars("analysis-crop-type-chart", firstArray(crops, ["crop", "cropType", "cropTypes"]), cropSummary, { caption: "Crop-circle crop types" }));
        jobs.push(() => this._renderBars("analysis-crop-coordinate-chart", firstArray(crops, ["coordinateClass", "coordinateClasses", "coordinate_class"]), cropSummary, { caption: "Crop-circle coordinate classes" }));
        jobs.push(() => this._renderHeatmap("analysis-crop-coverage-chart", firstDefined(crops, ["coverage", "missingness"], []), cropSummary, { caption: "Crop-circle field coverage", rowHeading: "Field" }));
      }
      const animals = data.animals;
      const animalSummary = this._setContextGroup(
        "analysis-animal-context",
        "analysis-animal-context-status",
        animals,
        "Animal reports"
      );
      if (animalSummary) {
        jobs.push(() => this._renderReadiness("analysis-animal-readiness-chart", data.animalReadiness, animalSummary, { emptyMessage: "Detailed animal-association readiness loads with Spatial Evidence; descriptive catalog health remains available here." }));
        jobs.push(() => this._renderSeries("analysis-animal-time-chart", firstArray(animals, ["time", "series", "yearly"]), animalSummary, { caption: "Animal reports by period" }));
        jobs.push(() => this._renderBars("analysis-animal-species-chart", firstArray(animals, ["species", "speciesGroups", "distribution"]), animalSummary, { caption: "Animal report species groups" }));
        jobs.push(() => this._renderBars("analysis-animal-status-chart", firstArray(animals, ["statusBreakdown", "reviewStatus", "status"]), animalSummary, { caption: "Animal report review status" }));
        jobs.push(() => this._renderBars("analysis-animal-date-precision-chart", firstArray(animals, ["datePrecision", "datePrecisions", "date_precision"]), animalSummary, { caption: "Animal report date precision" }));
        jobs.push(() => this._renderHeatmap("analysis-animal-coverage-chart", firstDefined(animals, ["coverage", "missingness"], []), animalSummary, { caption: "Animal report field coverage", rowHeading: "Field" }));
      }
      jobs.push(() => {
        const findings = this.baselineMode === "full_catalog" ? [] : firstArray(payload, ["patterns", "findings", "patternFindings"]).filter(function (finding) {
          const family = cleanText(firstDefined(finding, ["family", "statisticalFamily", "statistical_family"], "")).toLowerCase();
          return family !== "burst" && family !== "time_burst" && family !== "date_window" && family !== "structural_date_window";
        });
        this.renderPatternFindings(findings, firstDefined(payload, ["patternGroups", "pattern_groups"], null));
      });
      this._runRenderJobs(jobs, summary.activeCount > 0 ? "ready" : "empty");
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
      this.els.previewKind.textContent = kind === "area" ? "Local geography preview" : "Local chart preview";
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
      this.els.previewApplyFilters.hidden = kind !== "filter";
      this.els.previewApplyArea.hidden = kind !== "area";
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
    comparativeEffect,
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
    heatmapDisplayItems,
    inferPreviewCriteria,
    matrixItems,
    nextEnabledTabIndex,
    normalizeGeographyCells,
    normalizeAnalysisState,
    normalizeBaselineMode,
    normalizeSummary,
    normalizeView,
    previewForDatum,
    patternGroupsForDisplay,
    resolvedPatternChartId,
    sampleEvenly,
    sampledHeatmapAxes,
    sourceBalancedDisplay,
    sourceCompositionDisplay,
    positiveSeriesMaximum,
  });
});

(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  }
  if (root) {
    root.UfoPlaybackPerformance = api;
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const DEFAULT_RESULTS_WINDOW_SIZE = 60;
  const DEFAULT_RESULTS_WINDOW_MARGIN = 10;

  function clampInteger(value, minimum, maximum) {
    const normalized = Number.isFinite(Number(value)) ? Math.trunc(Number(value)) : minimum;
    return Math.max(minimum, Math.min(maximum, normalized));
  }

  function normalizeResultsWindow(total, start, windowSize) {
    const safeTotal = Math.max(0, Math.trunc(Number(total) || 0));
    const safeWindowSize = Math.max(1, Math.trunc(Number(windowSize) || DEFAULT_RESULTS_WINDOW_SIZE));
    const maximumStart = Math.max(0, safeTotal - safeWindowSize);
    const safeStart = clampInteger(start, 0, maximumStart);
    return {
      start: safeStart,
      end: Math.min(safeTotal, safeStart + safeWindowSize),
      size: safeWindowSize,
      total: safeTotal,
    };
  }

  function resultsWindowForTarget(config) {
    const options = config || {};
    const normalized = normalizeResultsWindow(
      options.total,
      options.currentStart,
      options.windowSize
    );
    if (!normalized.total) return normalized;

    const targetIndex = clampInteger(options.targetIndex, 0, normalized.total - 1);
    const maximumMargin = Math.max(0, Math.floor((normalized.size - 1) / 2));
    const margin = clampInteger(
      options.margin == null ? DEFAULT_RESULTS_WINDOW_MARGIN : options.margin,
      0,
      maximumMargin
    );
    const visibleStart = normalized.start;
    const visibleEnd = normalized.end;
    const targetComfortablyVisible =
      targetIndex >= (visibleStart + margin) &&
      targetIndex < (visibleEnd - margin);

    if (targetComfortablyVisible || normalized.total <= normalized.size) {
      return Object.assign({}, normalized, {
        targetIndex,
        changed: false,
      });
    }

    const desiredStart = targetIndex - Math.floor(normalized.size / 3);
    const shifted = normalizeResultsWindow(normalized.total, desiredStart, normalized.size);
    return Object.assign({}, shifted, {
      targetIndex,
      changed: shifted.start !== normalized.start,
    });
  }

  function shiftResultsWindow(config) {
    const options = config || {};
    const normalized = normalizeResultsWindow(
      options.total,
      options.currentStart,
      options.windowSize
    );
    const shift = Math.max(1, Math.trunc(Number(options.shift) || Math.floor(normalized.size * 0.66)));
    const direction = Number(options.direction) < 0 ? -1 : 1;
    const shifted = normalizeResultsWindow(
      normalized.total,
      normalized.start + (direction * shift),
      normalized.size
    );
    return Object.assign({}, shifted, {
      changed: shifted.start !== normalized.start,
    });
  }

  function adaptivePlaybackTiming(config) {
    const options = config || {};
    const baseIntervalMs = Math.max(1, Number(options.baseIntervalMs) || 1200);
    const targetIntervalMs = Math.max(1, Number(options.targetIntervalMs) || baseIntervalMs);
    const stepCostMs = Math.max(0, Number(options.stepCostMs) || 0);
    const reserveMs = Math.max(2, Number(options.reserveMs) || 8);
    const costMultiplier = Math.max(1, Number(options.costMultiplier) || 1.35);
    const requiredIntervalMs = Math.max(
      targetIntervalMs,
      (stepCostMs * costMultiplier) + reserveMs
    );
    const limited = requiredIntervalMs > (targetIntervalMs * 1.1);
    return {
      delayMs: requiredIntervalMs,
      effectiveSpeed: baseIntervalMs / requiredIntervalMs,
      limited,
    };
  }

  function weightedSamplePartitions(total, limit) {
    const safeTotal = Math.max(0, Math.trunc(Number(total) || 0));
    const safeLimit = Math.max(1, Math.trunc(Number(limit) || 1));
    const sampleCount = Math.min(safeTotal, safeLimit);
    const partitions = [];
    for (let sampleIndex = 0; sampleIndex < sampleCount; sampleIndex += 1) {
      const start = Math.floor((sampleIndex * safeTotal) / sampleCount);
      const end = Math.floor(((sampleIndex + 1) * safeTotal) / sampleCount);
      partitions.push({
        index: Math.floor((start + Math.max(start, end - 1)) / 2),
        start,
        end,
        weight: Math.max(1, end - start),
      });
    }
    return partitions;
  }

  return Object.freeze({
    DEFAULT_RESULTS_WINDOW_SIZE,
    DEFAULT_RESULTS_WINDOW_MARGIN,
    normalizeResultsWindow,
    resultsWindowForTarget,
    shiftResultsWindow,
    adaptivePlaybackTiming,
    weightedSamplePartitions,
  });
});

(function (root, factory) {
  "use strict";
  const api = factory(root);
  if (typeof module === "object" && module && module.exports) module.exports = api;
  if (root) root.UfoProgressiveCatalogRuntime = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function (root) {
  "use strict";

  const DEFAULT_MAX_BATCH_ROWS = 512;
  const DEFAULT_BUDGET_MS = 8;
  const FRAME_FALLBACK_MS = 160;

  function monotonicNow() {
    return root && root.performance && typeof root.performance.now === "function"
      ? root.performance.now()
      : Date.now();
  }

  function yieldToMain() {
    if (root && root.scheduler && typeof root.scheduler.yield === "function") {
      return root.scheduler.yield();
    }
    return new Promise(function (resolve) {
      const document = root && root.document;
      const visible = document && document.visibilityState === "visible";
      const requestFrame = root && root.requestAnimationFrame;
      if (!visible || typeof requestFrame !== "function") {
        root.setTimeout(resolve, 0);
        return;
      }
      let settled = false;
      let frameId = null;
      const fallbackId = root.setTimeout(finish, FRAME_FALLBACK_MS);
      function finish() {
        if (settled) return;
        settled = true;
        root.clearTimeout(fallbackId);
        if (frameId != null && typeof root.cancelAnimationFrame === "function") {
          root.cancelAnimationFrame(frameId);
        }
        resolve();
      }
      frameId = requestFrame.call(root, function () {
        frameId = null;
        // Continue in a later task, after the browser has had a paint opportunity.
        root.setTimeout(finish, 0);
      });
    });
  }

  function throwIfAborted(signal) {
    if (!signal) return;
    if (typeof signal.throwIfAborted === "function") {
      signal.throwIfAborted();
      return;
    }
    if (!signal.aborted) return;
    if (signal.reason !== undefined) throw signal.reason;
    const error = new Error("Catalog ingestion was cancelled.");
    error.name = "AbortError";
    throw error;
  }

  function positiveNumber(value, fallback) {
    const number = Number(value);
    return Number.isFinite(number) && number > 0 ? number : fallback;
  }

  async function ingestRows(rows, ingestBatch, options) {
    if (!Array.isArray(rows)) throw new TypeError("Catalog rows must be an array.");
    if (typeof ingestBatch !== "function") throw new TypeError("Catalog ingestion needs a batch callback.");
    const config = options || {};
    const now = typeof config.now === "function" ? config.now : monotonicNow;
    const yieldWork = typeof config.yieldToMain === "function" ? config.yieldToMain : yieldToMain;
    const maxBatchRows = Math.max(1, Math.floor(positiveNumber(config.maxBatchRows, DEFAULT_MAX_BATCH_ROWS)));
    const budgetMs = positiveNumber(config.budgetMs, DEFAULT_BUDGET_MS);
    const signal = config.signal;
    const onBatch = typeof config.onBatch === "function" ? config.onBatch : null;
    const startedAt = now();
    let sliceStartedAt = startedAt;
    const stats = {
      totalRows: rows.length,
      processedRows: 0,
      batchCount: 0,
      yieldCount: 0,
      maxBatchRows: 0,
      maxBatchDurationMs: 0,
      activeDurationMs: 0,
      wallDurationMs: 0,
    };
    throwIfAborted(signal);
    for (let start = 0; start < rows.length; start += maxBatchRows) {
      throwIfAborted(signal);
      const end = Math.min(rows.length, start + maxBatchRows);
      // The only copied input is this bounded batch; the corpus stays shared.
      const batch = rows.slice(start, end);
      const batchStartedAt = now();
      const result = ingestBatch(batch, start, end);
      if (result && typeof result.then === "function") await result;
      const batchDurationMs = Math.max(0, now() - batchStartedAt);
      stats.processedRows = end;
      stats.batchCount += 1;
      stats.maxBatchRows = Math.max(stats.maxBatchRows, batch.length);
      stats.maxBatchDurationMs = Math.max(stats.maxBatchDurationMs, batchDurationMs);
      stats.activeDurationMs += batchDurationMs;
      stats.wallDurationMs = Math.max(0, now() - startedAt);
      if (onBatch) onBatch(Object.assign({}, stats, { batchRows: batch.length, batchDurationMs }));
      throwIfAborted(signal);
      if (end < rows.length && now() - sliceStartedAt >= budgetMs) {
        await yieldWork();
        stats.yieldCount += 1;
        throwIfAborted(signal);
        sliceStartedAt = now();
      }
    }
    stats.wallDurationMs = Math.max(0, now() - startedAt);
    return stats;
  }

  return Object.freeze({ ingestRows, yieldToMain });
});

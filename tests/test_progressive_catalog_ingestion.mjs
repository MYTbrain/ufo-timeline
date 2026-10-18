import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import vm from "node:vm";

const require = createRequire(import.meta.url);
const runtime = require("../progressive_catalog_runtime.js");
const source = readFileSync(new URL("../progressive_catalog_runtime.js", import.meta.url), "utf8");
const rows = Array.from({ length: 2501 }, (_, index) => ({ id: index % 1703, ordinal: index }));
const original = rows.slice();
const seen = new Set(), accepted = [], calls = [], turns = [], snapshots = [];
let time = 0;
const stats = await runtime.ingestRows(rows, (batch, start, end) => {
  calls.push({ start, end, length: batch.length });
  assert.equal(batch[0], rows[start], "Batch rows retain their original object identity");
  for (const row of batch) if (!seen.has(row.id)) { seen.add(row.id); accepted.push(row.id); }
  time += 5;
}, {
  now: () => time,
  yieldToMain: async () => { turns.push(calls.length); time += 2; },
  onBatch: value => { snapshots.push(value); value.processedRows = -1; },
});
assert.deepEqual(calls, [
  { start: 0, end: 512, length: 512 }, { start: 512, end: 1024, length: 512 },
  { start: 1024, end: 1536, length: 512 }, { start: 1536, end: 2048, length: 512 },
  { start: 2048, end: 2501, length: 453 },
]);
assert.deepEqual(turns, [2, 4], "Input/paint opportunities occur after the time budget, between ordered batches");
assert.deepEqual(accepted, Array.from({ length: 1703 }, (_, index) => index), "Caller-owned deduplication and input order survive every yield");
assert.deepEqual(rows, original, "Ingestion never mutates or replaces the input corpus");
assert.deepEqual(stats, { totalRows: 2501, processedRows: 2501, batchCount: 5, yieldCount: 2,
  maxBatchRows: 512, maxBatchDurationMs: 5, activeDurationMs: 25, wallDurationMs: 29 });
assert.equal(snapshots.length, 5);

let paintCount = 0;
const inputOrder = [];
await runtime.ingestRows([0, 1, 2], async batch => { inputOrder.push(...batch); }, {
  now: () => ++time, maxBatchRows: 1, budgetMs: 1,
  yieldToMain: () => new Promise(resolve => setTimeout(() => { paintCount += 1; inputOrder.push("input"); resolve(); }, 0)),
});
assert.deepEqual(inputOrder, [0, "input", 1, "input", 2]);
assert.equal(paintCount, 2);

const failure = new Error("Native ingestion rejected a row");
let failedCalls = 0;
await assert.rejects(runtime.ingestRows(rows, () => { if (++failedCalls === 2) throw failure; },
  { maxBatchRows: 2, now: () => 0, yieldToMain: async () => assert.fail("No budget exhausted") }), error => error === failure);
assert.equal(failedCalls, 2, "A failed batch stops later rows immediately");
await assert.rejects(runtime.ingestRows([1], async () => { throw failure; }), error => error === failure);
await assert.rejects(runtime.ingestRows([1, 2], () => {}, {
  maxBatchRows: 1, budgetMs: 1, now: () => ++time, yieldToMain: async () => { throw failure; },
}), error => error === failure);

const before = new AbortController(); before.abort();
await assert.rejects(runtime.ingestRows(rows, () => assert.fail("Already-aborted work must not start"), { signal: before.signal }), { name: "AbortError" });
const between = new AbortController(); let abortedBatches = 0;
await assert.rejects(runtime.ingestRows(rows, () => { abortedBatches += 1; }, {
  maxBatchRows: 1, budgetMs: 1, now: () => ++time, signal: between.signal,
  yieldToMain: async () => { between.abort(failure); },
}), error => error === failure);
assert.equal(abortedBatches, 1, "Cancellation during a yield prevents the next batch");
let fallbackAbortedBatches = 0;
await assert.rejects(runtime.ingestRows(rows, () => { fallbackAbortedBatches += 1; }, {
  signal: { aborted: true },
}), { name: "AbortError" });
assert.equal(fallbackAbortedBatches, 0);
assert.equal((await runtime.ingestRows([], () => assert.fail("Empty corpus has no batch"))).batchCount, 0);
await assert.rejects(runtime.ingestRows(null, () => {}), /must be an array/);
await assert.rejects(runtime.ingestRows([], null), /batch callback/);

function browserFixture(visible = true) {
  let nextTimer = 0, nextFrame = 0;
  const timers = new Map(), frames = new Map();
  const sandbox = vm.createContext({ Promise, Date, Object, Array, Math, Number, Error, TypeError,
    document: { visibilityState: visible ? "visible" : "hidden" },
    setTimeout(callback, delay) { const id = ++nextTimer; timers.set(id, { callback, delay }); return id; },
    clearTimeout(id) { timers.delete(id); },
    requestAnimationFrame(callback) { const id = ++nextFrame; frames.set(id, callback); return id; },
    cancelAnimationFrame(id) { frames.delete(id); },
  });
  vm.runInContext(source, sandbox);
  return { sandbox, timers, frames, api: sandbox.UfoProgressiveCatalogRuntime };
}
const browser = browserFixture();
assert.equal(typeof browser.api.ingestRows, "function", "Browser global is exported without CommonJS");
let yielded = false;
const paintYield = browser.api.yieldToMain().then(() => { yielded = true; });
assert.equal(browser.frames.size, 1);
assert.equal([...browser.timers.values()][0].delay, 160, "Visible-page fallback is bounded when animation frames stall");
[...browser.frames.values()][0]();
await Promise.resolve();
assert.equal(yielded, false, "A frame alone does not resume ingestion before painting");
const resume = [...browser.timers.values()].find(timer => timer.delay === 0);
assert.ok(resume); resume.callback(); await paintYield;
assert.equal(yielded, true);
assert.equal(browser.timers.size, 1, "Mock-retained fired resume timer is the only remaining timer");

const stalled = browserFixture();
const fallback = stalled.api.yieldToMain();
[...stalled.timers.values()][0].callback(); await fallback;
assert.equal(stalled.frames.size, 0, "Stalled animation frame is cancelled on fallback");
const hidden = browserFixture(false);
const hiddenYield = hidden.api.yieldToMain();
assert.equal(hidden.frames.size, 0, "Hidden tabs do not wait for a throttled animation frame");
assert.equal([...hidden.timers.values()][0].delay, 0);
[...hidden.timers.values()][0].callback(); await hiddenYield;
const preferred = browserFixture(); let schedulerCalls = 0;
preferred.sandbox.scheduler = { yield() { schedulerCalls += 1; return Promise.resolve(); } };
await preferred.api.yieldToMain();
assert.equal(schedulerCalls, 1);
assert.equal(preferred.timers.size, 0, "Native scheduler yield needs no timer or frame fallback");

console.log("Progressive catalog batches retain ordering, caller-owned deduplication, bounded copies, budgeted input yields, cancellation, failures, and browser scheduling fallbacks.");

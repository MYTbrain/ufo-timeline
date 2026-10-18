import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";

const flush = async () => { for (let index = 0; index < 8; index++) await Promise.resolve(); };
function deferred() {
  let resolve;
  const promise = new Promise(yes => { resolve = yes; });
  return { promise, resolve };
}
function fixture(domain, { core = true, response = null } = {}) {
  const calls = [], listeners = new Map(), errors = [], gate = deferred();
  const button = { dataset: {}, disabled: false, setAttribute() {}, removeAttribute() {},
    classList: { toggle() {} }, addEventListener() {} };
  const status = { textContent: "", classList: { toggle() {} } };
  const crop = domain === "crops";
  const window = { addEventListener(name, callback) { listeners.set(name, callback); }, setTimeout, clearTimeout };
  const layer = { setDateScope() {}, setEnabled(enabled) { calls.push({ layerEnabled: enabled }); return enabled ? gate.promise : Promise.resolve(false); } };
  window[crop ? "UfoCropCircleLayer" : "UfoAnimalMutilationLayer"] = layer;
  if (core) window.setContextLayerEnabled = (requestedDomain, enabled, origin) => {
    calls.push({ domain: requestedDomain, enabled, origin });
    return response ? Promise.resolve(response) : gate.promise;
  };
  const document = { querySelector(selector) {
    if (selector === (crop ? "#overlay-crop-circles" : "#overlay-animal-mutilations")) return button;
    if (selector === (crop ? "#crop-circle-status" : "#animal-mutilation-status")) return status;
    return null;
  } };
  const context = vm.createContext({ window, document, Promise, Error, Object, Date, String, Number,
    console: { error(error) { errors.push(error.message); } } });
  vm.runInContext(fs.readFileSync(new URL(crop ? "../crop_circle_bootstrap.js" : "../animal_mutilation_bootstrap.js", import.meta.url), "utf8"), context);
  return { api: window[crop ? "UfoCropCircleBootstrap" : "UfoAnimalMutilationBootstrap"], calls, errors, gate, status,
    fullReady() { listeners.get("ufo:timeline-ready")(); } };
}

for (const domain of ["crops", "animals"]) {
  const initial = fixture(domain);
  assert.equal(initial.calls.length, 0, "Default overlays remain lazy until an actual readiness owner requests them");
  const first = initial.api.prepareInitialView();
  assert.equal(initial.api.prepareInitialView(), first, "Concurrent initial map owners share one completion promise");
  await flush();
  assert.deepEqual(initial.calls, [{ domain, enabled: true, origin: "startup-default" }]);
  let completed = false;
  first.then(() => { completed = true; });
  await flush();
  assert.equal(completed, false, "Preparing the initial view waits for actual overlay completion");
  initial.gate.resolve({ domain, enabled: true });
  await first;
  assert.equal(completed, true);
  await initial.api.setEnabled(false, "user-toggle");
  initial.fullReady();
  await flush();
  assert.equal(initial.api.getDesiredEnabled(), false);
  assert.equal(initial.calls.filter(row => row.domain).length, 1, "Later global catalog readiness cannot re-enable a user-disabled overlay");

  const failed = fixture(domain, { response: { overlayAvailable: false, error: "Pinned overlay unavailable" } });
  await assert.rejects(failed.api.prepareInitialView(), /Pinned overlay unavailable/,
    "The shared context's soft failure cannot be mistaken for a ready rendered overlay");
  failed.fullReady();
  await flush();
  assert.equal(failed.calls.length, 1, "Global readiness does not duplicate or silently restart a failed initial activation");
  assert.equal(failed.errors.length, 1);

  const fallback = fixture(domain, { core: false });
  const fallbackReady = fallback.api.prepareInitialView();
  await flush();
  assert.deepEqual(fallback.calls, [{ layerEnabled: true }], "The extension can still prepare with its existing map-context fallback");
  fallback.gate.resolve(true);
  assert.equal(await fallbackReady, true);
  fallback.fullReady();
  await flush();
  assert.equal(fallback.calls.length, 1);

  const legacy = fixture(domain);
  legacy.fullReady();
  await flush();
  assert.deepEqual(legacy.calls, [{ domain, enabled: true, origin: "startup-default" }], "Existing complete-catalog startup retains default overlay activation");
  legacy.gate.resolve(true);
  await legacy.api.prepareInitialView();

  const disabled = fixture(domain);
  await disabled.api.setEnabled(false, "user-toggle");
  const disabledReady = disabled.api.prepareInitialView();
  await flush();
  assert.equal(disabled.calls.at(-1).enabled, false, "Initial preparation respects an already disabled optional overlay");
  disabled.gate.resolve(false);
  await disabledReady;
}
console.log("Crop and animal initial-view hooks await rendering once, expose load failures, preserve opt-out choices, and coexist with final catalog readiness.");

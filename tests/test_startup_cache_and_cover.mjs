import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import { gzipSync } from "node:zlib";

const source = fs.readFileSync(new URL("../app.js", import.meta.url), "utf8").replace(/\r\n/g, "\n");
function actualFunction(name) {
  const start = source.search(new RegExp("^  (?:async )?function " + name + "\\(", "m"));
  assert.ok(start >= 0, "Actual app function exists: " + name);
  const remaining = source.slice(start + 1);
  const next = remaining.search(/\n  (?:async )?function \w+\(/);
  assert.ok(next >= 0, "Actual app function has a following boundary: " + name);
  return source.slice(start, start + 1 + next).trim();
}

const payload = Buffer.from([0, 1, 2, 3, 255]);
const requests = [];
let responseMode = "gzip";
const cacheSandbox = vm.createContext({ URL, Response, DecompressionStream,
  document: { baseURI: "https://fixture.invalid/index.html" }, startup: {},
  resolveAssetPath: (value) => new URL(value, "https://fixture.invalid/index.html").href,
  renderStartupDiagnostics() {},
  createStartupError: (message) => new Error(message),
  fetch: async (url, options) => {
    requests.push({ url, options });
    if (responseMode === "network") throw new Error("offline");
    if (responseMode === "http") return new Response("missing", { status: 404 });
    if (responseMode === "empty") return new Response(null);
    if (responseMode === "invalid") return new Response("not gzip");
    return new Response(gzipSync(payload));
  } });
vm.runInContext(actualFunction("binaryAssetCacheMode") + "\n" + actualFunction("fetchGzipArrayBuffer"), cacheSandbox);
for (const [url, expected] of [
  ["https://data.invalid/releases/quality-20261007/points.bin.gz", "default"],
  ["./data/points.bin.gz?v=release-v1", "default"],
  ["./data/points.bin.gz?v=%20release-v1%20", "default"],
  ["./data/points.bin.gz", "no-store"],
  ["./data/points.bin.gz?v=%20", "no-store"],
  ["https://data.invalid/releases//points.bin.gz", "no-store"],
  ["http://[invalid", "no-store"],
]) {
  assert.equal(cacheSandbox.binaryAssetCacheMode(url), expected, url);
  if (url === "http://[invalid") continue;
  const decoded = await cacheSandbox.fetchGzipArrayBuffer(url, "Fixture binary");
  assert.deepEqual(Buffer.from(decoded), payload, "Normal cache selection must retain gzip decoding");
  assert.equal(requests.at(-1).options.cache, expected, "Actual fetch uses the guarded cache policy");
}
assert.ok(requests.every(({ options }) => options.cache !== "force-cache"));
for (const [mode, message] of [["network", /could not be fetched/], ["http", /HTTP 404/],
  ["empty", /no response body/], ["invalid", /could not be decoded/]]) {
  responseMode = mode;
  await assert.rejects(cacheSandbox.fetchGzipArrayBuffer("./data/points.bin.gz?v=release-v1", "Fixture binary"), message);
}

const minimumMatch = source.match(/const MAP_STARTUP_OVERLAY_MIN_VISIBLE_MS = (\d+);/);
assert.ok(minimumMatch);
assert.equal(Number(minimumMatch[1]), 900, "The app retains the existing loading-cover minimum");
function loadingCover() {
  let now = 100, timerId = 0;
  const timers = new Map(), attributes = {};
  const startup = { phase: "Loading report evidence", initialViewReady: false, errorText: "", overview: "Preparing reports" };
  const runtime = { mapStartupOverlayVisibleSince: 0, mapStartupOverlayHideTimerId: null };
  const els = { mapStartupOverlay: { hidden: true }, mapStartupProgressFill: { style: {} },
    mapStartupProgressLabel: {}, mapStartupTitle: {}, mapStartupDetail: {} };
  const sandbox = vm.createContext({ startup, runtime, els, MAP_STARTUP_OVERLAY_MIN_VISIBLE_MS: Number(minimumMatch[1]),
    performance: { now: () => now }, document: { documentElement: { setAttribute: (key, value) => { attributes[key] = value; } } },
    window: { setTimeout(callback, delay) { const id = ++timerId; timers.set(id, { callback, delay }); return id; },
      clearTimeout(id) { timers.delete(id); } } });
  vm.runInContext(actualFunction("renderMapStartupOverlay"), sandbox);
  return { startup, runtime, els, timers, attributes, setNow(value) { now = value; }, render: sandbox.renderMapStartupOverlay };
}

const cover = loadingCover();
cover.render(35);
assert.equal(cover.els.mapStartupOverlay.hidden, false);
assert.equal(cover.attributes["data-map-startup-overlay"], "visible");
assert.equal(cover.els.mapStartupProgressLabel.textContent, "35%");
cover.startup.initialViewReady = true;
cover.render(97);
assert.equal(cover.els.mapStartupOverlay.hidden, false, "Initial visuals alone must not dismiss the cover");
cover.startup.initialViewReady = false;
cover.startup.phase = "Ready";
cover.setNow(300);
cover.render(100);
assert.equal(cover.els.mapStartupOverlay.hidden, false, "Ready alone must not dismiss the cover");
assert.equal(cover.timers.size, 0);
cover.startup.initialViewReady = true;
cover.setNow(400);
cover.render(100);
assert.equal(cover.els.mapStartupOverlay.hidden, false, "Fast completion retains the 900 ms minimum");
assert.equal(cover.timers.size, 1);
const scheduled = cover.timers.get(cover.runtime.mapStartupOverlayHideTimerId);
assert.equal(scheduled.delay, 600);
cover.setNow(999);
cover.render(100);
assert.equal(cover.els.mapStartupOverlay.hidden, false);
assert.equal(cover.timers.size, 1, "Repeated progress renders do not create duplicate hide timers");
cover.setNow(1000);
scheduled.callback();
assert.equal(cover.els.mapStartupOverlay.hidden, true, "Cover dismisses after complete readiness and the minimum duration");
assert.equal(cover.attributes["data-map-startup-overlay"], "hidden");

const failure = loadingCover();
failure.render(20);
failure.startup.phase = "Ready";
failure.startup.initialViewReady = true;
failure.setNow(200);
failure.render(100);
assert.equal(failure.timers.size, 1);
failure.startup.errorText = "Fixture failure";
failure.setNow(250);
failure.render(99);
assert.equal(failure.timers.size, 0, "Failure cancels a pending dismissal");
assert.equal(failure.runtime.mapStartupOverlayHideTimerId, null);
assert.equal(failure.els.mapStartupOverlay.hidden, false, "Errors keep the loading screen visible, even with readiness flags");
assert.equal(failure.els.mapStartupTitle.textContent, "Startup needs attention");
assert.match(failure.els.mapStartupDetail.textContent, /could not finish loading/);
failure.startup.phase = "Failed";
failure.setNow(2000);
failure.render(99);
assert.equal(failure.els.mapStartupOverlay.hidden, false);
console.log("Actual app binary cache policy, gzip/error handling, and loading-screen readiness/minimum/failure behavior pass.");

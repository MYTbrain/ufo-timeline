import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import { gzipSync } from "node:zlib";

const workerSource = fs.readFileSync(new URL("../startup_profile_worker.js", import.meta.url), "utf8");
const base = "https://fixture.invalid/data/startup_profiles/france_1954_flap/";
const manifest = { files: { events: "events.json", events_gzip: "events.json.gz",
  trace_preview_segments: "trace_preview_segments.json", trace_preview_segments_gzip: "trace_preview_segments.json.gz" } };
const events = [{ event_id: 123, source: "ufocat", date_precision: "exact_day" }];
const traces = [{ from_event_id: 123, to_event_id: 456, gap_days: 0 }];
const bodies = new Map([["manifest.json", manifest], ["events.json", events], ["trace_preview_segments.json", traces]]);

async function load({ manifestUrl = base + "manifest.json", versionToken = "release-v1", missingGzip = false,
  gzipSupport = true } = {}) {
  const requests = [];
  let onMessage, settle;
  const result = new Promise((resolve) => { settle = resolve; });
  const self = { location: { href: "https://fixture.invalid/startup_profile_worker.js" },
    DecompressionStream: gzipSupport ? DecompressionStream : undefined,
    addEventListener(type, listener) { assert.equal(type, "message"); onMessage = listener; },
    postMessage(message) { settle(message); } };
  const sandbox = vm.createContext({ self, URL, Response, DecompressionStream,
    fetch: async (rawUrl, options) => {
      const url = new URL(rawUrl);
      requests.push({ url, options });
      const file = url.pathname.split("/").at(-1);
      const gzip = file.endsWith(".gz");
      if (gzip && missingGzip && file === "manifest.json.gz") return new Response("missing", { status: 404 });
      const body = bodies.get(gzip ? file.slice(0, -3) : file);
      if (!body) return new Response("unexpected asset", { status: 404 });
      const bytes = Buffer.from(JSON.stringify(body));
      return new Response(gzip ? gzipSync(bytes) : bytes);
    } });
  vm.runInContext(workerSource, sandbox, { filename: "startup_profile_worker.js" });
  onMessage({ data: { type: "loadStartupProfile", requestId: "profile", versionToken,
    config: { baseUrl: base, manifestUrl, tracePreview: true } } });
  const message = await result;
  assert.equal(message.type, "startupProfileLoaded", message.error);
  assert.equal(message.requestId, "profile");
  assert.deepEqual(JSON.parse(JSON.stringify(message.result.events)), events);
  assert.deepEqual(JSON.parse(JSON.stringify(message.result.tracePreviewSegments)), traces);
  assert.ok(requests.every(({ options }) => options.cache === "default"));
  return { requests, result: message.result };
}

const compressed = await load();
assert.equal(compressed.requests.length, 3, "Healthy gzip assets must not cause redundant raw fallbacks");
assert.deepEqual(compressed.requests.map(({ url }) => url.pathname.split("/").at(-1)),
  ["manifest.json.gz", "events.json.gz", "trace_preview_segments.json.gz"]);
assert.ok(compressed.requests.every(({ url }) => url.searchParams.get("v") === "release-v1"));
assert.equal(compressed.result.usedGzip.manifest, true);
assert.equal(compressed.result.usedGzip.events, true);
assert.equal(compressed.result.usedGzip.tracePreview, true);

const pinned = await load({ manifestUrl: base + "manifest.json?v=pinned-release&region=france#details", versionToken: "new-shell" });
assert.equal(pinned.requests[0].url.pathname, new URL(base).pathname + "manifest.json.gz");
assert.equal(pinned.requests[0].url.searchParams.get("v"), "pinned-release", "Existing version pins must remain unchanged");
assert.equal(pinned.requests[0].url.searchParams.get("region"), "france");
assert.equal(pinned.requests[0].url.hash, "#details");

const fallback = await load({ missingGzip: true });
assert.equal(fallback.requests.length, 4);
assert.equal(fallback.requests[1].url.pathname, new URL(base).pathname + "manifest.json");
assert.equal(fallback.requests[1].url.searchParams.get("v"), "release-v1");
assert.equal(fallback.result.usedGzip.manifest, false, "Missing compressed assets retain the raw JSON fallback");

const legacy = await load({ gzipSupport: false });
assert.equal(legacy.requests.length, 3);
assert.ok(legacy.requests.every(({ url }) => !url.pathname.endsWith(".gz")));
assert.equal(legacy.result.usedGzip.manifest, false);
assert.equal(legacy.result.usedGzip.events, false);
assert.equal(legacy.result.usedGzip.tracePreview, false);
console.log("Startup profile worker uses version-preserving gzip siblings without redundant requests; raw and legacy fallbacks pass.");

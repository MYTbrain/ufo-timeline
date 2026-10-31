import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { gzipSync, gunzipSync } from "node:zlib";
import vm from "node:vm";

const require = createRequire(import.meta.url);
const share = require("../share_view.js");
const evidence = JSON.parse(readFileSync(new URL("../docs/qa/share-view-20261031/browser.json", import.meta.url), "utf8"));
const archived = [evidence.caseRoundTrip.expected, evidence.customAreaRoundTrip.expected];
const clone = value => JSON.parse(JSON.stringify(value));
const compressedToken = value => "2." + gzipSync(Buffer.from(value, "utf8")).toString("base64url");
const base = "https://ufo-timeline.pages.dev/index.html?debug=1&start=1900&autoselect=first#analysis-section-encounters";
const measurements = [];

// Frozen 2026-10-31 v2 delta fixture. This must remain readable if current app
// defaults change; regenerating it would hide a transport compatibility break.
const frozenV2 = "2.H4sIAAAAAAAACm1S0ZKCMAz8lzyD06a0QH-FYRyE6nEgdQre6Tn8-03DgcLpE9vdJLsmGVQQZBg8oClBZzyAsujN3tmDccN-KO6tdZAH0PAK9KTjLQkHdzVEnAkei7Y3-RhkOT3eZ_VlKeve6L5mNkoXnXjRBdCIz23dMkTNNee1o-gJVwXIiXhAo0BDabtjfbo6U4EvuoGWcpdyxBhTwZgSivsaBjoUO8mlQsnmXxRAE5Wg1Uh9f2YjFQ1g5OJ7ZUqka1hsUn4Qzh7QGNCPp58XC3L0bXvQ4Myptl2I3jjeQcfembeU-Fy1K1sDI0UW9WZOs7bRbuhu89f5t9OcDg_LktZlcg2xfrNqtEub4h3tpvO7GNfX_WC6gc4Oe3oW9D38Xei1H-yZaLGZLNQkaW1ZDLXt9kVfTkK7yh1NAdhOElJ_iMln6tuSNZ4sKEZ7xeN_F9dJIdOE2hXzmWEMGpChClkUck7rSkAjk9JfEFaggScpCxkP2UQb0CGmyNPx5XbzX-dOfp2nAwAA";
assert.deepEqual(await share.decodeAny(frozenV2), archived[0], "previous v2 links retain their exact baseline and key meanings");

assert.equal(share.COMPACT_VERSION, 3);
for (const snapshot of archived) {
  const original = JSON.stringify(snapshot);
  const legacy = share.encode(snapshot);
  const compact = await share.encodeCompact(snapshot);
  assert.match(compact, /^(?:2\.|3\.[rg]\.)[A-Za-z0-9_-]+$/);
  assert.ok(compact.length <= legacy.length * 0.4, "the real view should shrink by at least 60 percent");
  assert.deepEqual(await share.decodeAny(compact), snapshot, "every original setting survives compaction");
  assert.deepEqual(await share.decodeAny(legacy), snapshot, "original v1 links remain readable");
  assert.equal(JSON.stringify(snapshot), original, "compaction does not mutate source settings");
  const url = new URL(await share.buildCompactUrl(snapshot, base));
  const fragment = new URLSearchParams(url.hash.slice(1));
  assert.equal(url.search, "", "compact settings never enter the HTTP request query");
  assert.deepEqual([...fragment.keys()], ["view", "s"]);
  assert.equal(fragment.get("view"), compact);
  assert.equal(fragment.get("s"), "encounters");
  assert.equal(share.readSectionHash(url.href), "#analysis-section-encounters");
  assert.deepEqual(await share.readAnyUrl(url.href), snapshot);
  assert.deepEqual(await share.readAnyUrl(share.buildUrl(snapshot, base)), snapshot);
  assert.deepEqual(await share.readAnyUrl(`https://example.test/?view=${compact}`), snapshot,
    "previous compact query links remain readable");
  assert.deepEqual(await share.readAnyUrl(`https://example.test/?view=${legacy}`), snapshot,
    "previous uncompressed query links remain readable");
  assert.equal(new URL(await share.buildCompactUrl(snapshot, url.href)).hash, url.hash,
    "regenerated links retain their section without duplicating the view");
  measurements.push({ oldToken: legacy.length, compactToken: compact.length,
    reductionPercent: Number((100 * (1 - compact.length / legacy.length)).toFixed(1)) });
}

const tricky = clone(archived[0]);
tricky.filters.keyword = "Высота 611 · lumière 🛸";
tricky.filters.extra = { k0: false, k1: true, "~time": "", "~~": [], "": null, time: "literal", false: 0 };
tricky.map.lat = 55.91227293006361;
tricky.map.lng = -3.5156250000000004;
tricky.selection = 4316005650816402;
tricky.region.shapes.push({ id: "date-line", type: "rectangle", bounds: { west: 170, east: 190, south: -10, north: 20 } });
assert.deepEqual(await share.decodeAny(await share.encodeCompact(tricky)), tricky,
  "Unicode, aliases, unknown keys, floating-point coordinates, large IDs and dateline geometry round trip exactly");

// A frozen transport baseline must never add omitted keys or turn false/empty
// values into defaults. Test both full application snapshots and partial ones.
const partials = [{}, { settings: {} }, { settings: null }, { filters: { facets: {} } },
  { settings: { showTraceDirectionArrows: false } }, { settings: { showTraceDirectionArrows: true } },
  { region: { shapes: [], depth: 0, knownDirectionOnly: false } },
  { filters: { keyword: "", facets: { precision: { mode: "none", selectedValues: [] } } } },
  { selection: null }, { selection: "" }, { controls: { k0: false, "~k0": null } }];
for (const path of [["time"], ["settings", "showTraceDirectionArrows"], ["layers", "crops", "ufoFocus", "showRadius"],
  ["filters", "facets", "precision", "selectedValues"], ["region", "shapes"]]) {
  const variant = clone(archived[0]);
  let target = variant;
  for (const key of path.slice(0, -1)) target = target[key];
  delete target[path.at(-1)];
  partials.push(variant);
}
for (const snapshot of partials) {
  assert.deepEqual(await share.decodeAny(await share.encodeCompact(snapshot)), snapshot,
    "missing keys stay missing and present empty/false/null values stay present");
}
const inverseFlags = clone(archived[0]);
function invertBooleans(value) {
  if (!value || typeof value !== "object") return;
  for (const key of Object.keys(value)) {
    if (typeof value[key] === "boolean") value[key] = !value[key];
    else invertBooleans(value[key]);
  }
}
invertBooleans(inverseFlags);
assert.deepEqual(await share.decodeAny(await share.encodeCompact(inverseFlags)), inverseFlags,
  "every checkbox can invert independently of the frozen transport baseline");
assert.equal(await share.encodeCompact({}), share.encode({}), "a tiny snapshot retains the shorter uncompressed representation");
let randomState = 0x1a18e65;
function noise(length) {
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";
  let output = "";
  for (let index = 0; index < length; index += 1) {
    randomState ^= randomState << 13;
    randomState ^= randomState >>> 17;
    randomState ^= randomState << 5;
    output += alphabet[randomState >>> 26];
  }
  return output;
}
const nearLimit = { filters: { a: noise(8130), b: noise(8130), c: noise(8130) } };
assert.ok(Buffer.byteLength(JSON.stringify({ v: 1, ...nearLimit })) > 24000);
assert.deepEqual(await share.decodeAny(await share.encodeCompact(nearLimit)), nearLimit,
  "a valid near-limit high-entropy snapshot stays shareable even if compact candidates cannot improve it");
assert.equal(await share.readAnyUrl("https://example.test/?start=1986-01-28"), null);
assert.equal(await share.readAnyUrl("https://example.test/#analysis-section-time"), null);
for (const suffix of ["?view=", "#view=", "?view=a&view=b", "#view=a&view=b",
  `?view=${frozenV2}#view=${frozenV2}`, `?view=#view=${frozenV2}`]) {
  await assert.rejects(share.readAnyUrl("https://example.test/" + suffix), /invalid/i,
    "fragment tokens receive the same empty/duplicate/mixed-location rejection as query tokens");
}
assert.deepEqual(await share.readAnyUrl("https://example.test/#view=" + frozenV2), archived[0],
  "existing compact bytes can move to the fragment without changing the restored state");

// Keep the v2 transport's corruption/CRC tests independent of which encoder wins.
const compact = frozenV2;
const bytes = Buffer.from(compact.slice(2), "base64url");
assert.ok(gunzipSync(bytes).length < 24576);
const corrupt = Buffer.from(bytes);
corrupt[corrupt.length - 8] ^= 255; // gzip CRC, not a JSON/schema error
for (const token of ["2.", "2.a", "2._w", compact + "=", "2." + corrupt.toString("base64url"),
  "2." + bytes.subarray(0, bytes.length - 5).toString("base64url"), compressedToken("{"), compressedToken("[]")]) {
  await assert.rejects(share.decodeAny(token), Error, "malformed or corrupt data is rejected");
}
await assert.rejects(share.decodeAny("4." + compact.slice(2)), /newer/i);
await assert.rejects(share.decodeAny("1." + compact.slice(2)), /not supported|unsupported/i);
await assert.rejects(share.decodeAny("2." + "a".repeat(32772)), /too large/i);
await assert.rejects(share.decodeAny(compressedToken('"' + "x".repeat(24577) + '"')), /too large/i,
  "decompressed data is bounded before JSON/schema validation");
await assert.rejects(share.encodeCompact({ filters: { keyword: "x".repeat(8193) } }), /too large/i);
await assert.rejects(share.encodeCompact(JSON.parse('{"filters":{"__proto__":{"polluted":true}}}')), /invalid/i);
assert.equal({}.polluted, undefined);

const code = readFileSync(new URL("../share_view.js", import.meta.url), "utf8");
const browserGlobals = {
  URL, URLSearchParams, TextEncoder, TextDecoder, Blob, CompressionStream, DecompressionStream,
  btoa: text => Buffer.from(text, "binary").toString("base64"),
  atob: text => Buffer.from(text, "base64").toString("binary"),
};
for (const preference of ["checked", "unchecked"]) {
  const browser = vm.createContext({ ...browserGlobals,
    get localStorage() { assert.fail("compaction must not consult recipient preferences: " + preference); },
  });
  vm.runInContext(code, browser);
  browser.snapshotJson = JSON.stringify(tricky);
  browser.token = await vm.runInContext("UfoShareView.encodeCompact(JSON.parse(snapshotJson))", browser);
  assert.match(browser.token, /^(?:2\.|3\.[rg]\.)/);
  const restored = await vm.runInContext("UfoShareView.decodeAny(token).then(JSON.stringify)", browser);
  assert.deepEqual(JSON.parse(restored), tricky, "the actual browser API path works without Node Buffer");
  browser.token = share.encode(tricky);
  assert.deepEqual(JSON.parse(await vm.runInContext("UfoShareView.decodeAny(token).then(JSON.stringify)", browser)), tricky);
  const browserUrl = await vm.runInContext("UfoShareView.buildCompactUrl(JSON.parse(snapshotJson), 'https://example.test/?debug=1#analysis-section-time')", browser);
  assert.equal(new URL(browserUrl).search, "");
  browser.sharedUrl = browserUrl;
  assert.deepEqual(JSON.parse(await vm.runInContext("UfoShareView.readAnyUrl(sharedUrl).then(JSON.stringify)", browser)), tricky,
    "fragment URL generation/restoration works in the browser API path without Buffer");
}

const fallback = vm.createContext({ ...browserGlobals, CompressionStream: undefined, DecompressionStream: undefined });
vm.runInContext(code, fallback);
fallback.snapshotJson = JSON.stringify(tricky);
const fallbackToken = await vm.runInContext("UfoShareView.encodeCompact(JSON.parse(snapshotJson))", fallback);
assert.ok(fallbackToken.length <= share.encode(tricky).length, "unavailable compression selects a portable raw format no longer than legacy");
fallback.token = fallbackToken;
assert.deepEqual(JSON.parse(await vm.runInContext("UfoShareView.decodeAny(token).then(JSON.stringify)", fallback)), tricky);
fallback.token = compact;
await assert.rejects(vm.runInContext("UfoShareView.decodeAny(token)", fallback), /browser|decompress|support/i);

console.log("Compact shared-view tests passed:", JSON.stringify(measurements));

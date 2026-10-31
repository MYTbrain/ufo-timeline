import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import vm from "node:vm";
const require = createRequire(import.meta.url);
const share = require("../share_view.js");
const rawToken = text => Buffer.from(text, "utf8").toString("base64url");
const snapshot = {
  time: { start: "1986-01-28", end: "1986-01-30", mode: "custom" },
  map: { center: [44.55, 135.61], zoom: 6.25, basemap: "" },
  case: "case_dalnegorsk",
  filters: { sources: [], keyword: "Высота 611 · lumière 🛸", hideLowPrecision: false, hideNonExactDates: true },
  settings: { arrows: false, knownDirectionOnly: true, color: "#abc123" },
  region: { shapes: [{ type: "circle", center: { lat: 44.55, lng: 135.61 }, radiusMeters: 75000 },
    { type: "rectangle", bounds: { west: 170, east: 190, north: 55, south: 35 } }], depth: 0, pointOnly: false },
  layers: { encounters: false, airports: true, disabled: [], optional: null },
  controls: { expanded: [], compact: false }, section: "map", selection: "",
};
const original = JSON.stringify(snapshot);
const token = share.encode(snapshot);
assert.match(token, /^[A-Za-z0-9_-]+$/);
assert.ok(token.length < 32768);
assert.equal(JSON.parse(Buffer.from(token, "base64url").toString("utf8")).v, 1);
const decoded = share.decode(token);
assert.deepEqual(decoded, snapshot, "Unicode, zero, false, empty strings, empty arrays and region geometry round trip exactly");
assert.equal(JSON.stringify(snapshot), original, "encoding never mutates its source");
assert.notEqual(decoded.region, snapshot.region);
assert.notEqual(decoded.region.shapes, snapshot.region.shapes);
assert.ok(!Object.hasOwn(decoded, "v"), "the transport version is not an application setting");
assert.deepEqual(share.decode(share.encode({})), {});

const base = "https://ufo-timeline.pages.dev/index.html?start=1900-01-01&end=2000-12-31&windowStart=a&windowEnd=b&autosearch=x&autoselect=y&liveProbe=1&debug=1&startupProbeTitle=1&unknown=secret#analysis-section-sources-quality";
const built = share.buildUrl(snapshot, base);
const url = new URL(built);
const fragment = new URLSearchParams(url.hash.slice(1));
assert.equal(url.search, "", "shared settings and existing diagnostics never enter the HTTP request query");
assert.deepEqual([...fragment.keys()], ["view", "section"]);
assert.equal(fragment.get("view"), token);
assert.equal(url.pathname, "/index.html");
assert.equal(fragment.get("section"), "analysis-section-sources-quality");
assert.deepEqual(share.readUrl(built), snapshot);
assert.deepEqual(share.readUrl(`https://example.test/?view=${token}#analysis-section-time`), snapshot,
  "existing query-based links remain readable");
assert.equal(new URL(share.buildUrl(snapshot, built)).hash, url.hash,
  "sharing an already shared view retains its analysis section");
assert.equal(share.readUrl("https://example.test/?start=2000-01-01#analysis-section-time"), null);
for (const hash of ["#analysis-crop-context", "#analysis-animal-context", "#analysis-relationship-context", "#analysis-section-encounters"]) {
  const next = new URL(share.buildUrl(snapshot, "https://example.test/" + hash));
  assert.equal(new URLSearchParams(next.hash.slice(1)).get("section"), hash.slice(1));
}
for (const hash of ["#debug", "#analysis-section-<script>", "#analysis-section-time?debug=1", "#analysis-section-" + "x".repeat(90)]) {
  const next = new URL(share.buildUrl(snapshot, "https://example.test/" + hash));
  assert.deepEqual([...new URLSearchParams(next.hash.slice(1)).keys()], ["view"], "unrecognized fragments are not carried into shared links");
}
for (const suffix of ["?view=", "#view=", `?view=${token}&view=${token}`, `#view=${token}&view=${token}`,
  `?view=${token}#view=${token}`, `?view=#view=${token}`]) {
  const value = "https://example.test/" + suffix;
  assert.throws(() => share.readUrl(value), /invalid/, "empty or ambiguous shared state is rejected");
  assert.equal(share.hasViewUrl(value), true, "invalid shared state must still suppress URL automation");
}
for (const suffix of [`?view=${token}`, `#view=${token}`, "#view=not-a-valid-token", "#%76iew=", "?%76iew="]) {
  assert.equal(share.hasViewUrl("https://example.test/" + suffix), true);
}
for (const suffix of ["", "?start=1986-01-28", "#analysis-section-time", "#preview=abc", "?preview=abc"]) {
  assert.equal(share.hasViewUrl("https://example.test/" + suffix), false);
}
assert.throws(() => share.buildUrl(snapshot, "javascript:alert(1)"), /HTTP/);
assert.throws(() => share.buildUrl(snapshot, "https://private:password@example.test/"), /HTTP/);

for (const value of [undefined, null, [], "view", new Date(), { unknown: true }, { v: 1 }, { filters: { bad: undefined } },
  { settings: { bad: Infinity } }, { map: { bad: NaN } }, { controls: { bad: 1n } }, { selection: () => {} }]) {
  assert.throws(() => share.encode(value), Error);
}
for (const text of ['{"v":1,"unknown":true}', '{"v":1,"filters":{"__proto__":{"polluted":true}}}',
  '{"v":1,"settings":{"constructor":{"prototype":{"polluted":true}}}}', '{"v":1,"map":{"prototype":{}}}',
  '{"v":1,"map":{"zoom":1e400}}', '{"filters":{}}', '[]', '{']) {
  assert.throws(() => share.decode(rawToken(text)), Error);
}
assert.equal({}.polluted, undefined);
assert.throws(() => share.decode(rawToken('{"v":2,"time":{}}')), /newer/);
assert.throws(() => share.decode(rawToken('{"v":0}')), /not supported/);
assert.throws(() => share.decode(rawToken('{"v":"1"}')), /not supported/);
for (const bad of ["", "a", "abc=", "a/b", "a+b", "_ ", "é", "_w"]) assert.throws(() => share.decode(bad), Error);
const canonical = rawToken('{"v":1}');
const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";
const alternate = canonical.slice(0, -1) + alphabet[alphabet.indexOf(canonical.at(-1)) + 1];
assert.throws(() => share.decode(alternate), /invalid/, "noncanonical trailing base64 bits are rejected");
assert.throws(() => share.decode("a".repeat(32772)), /too large/);
assert.throws(() => share.encode({ filters: { keyword: "a".repeat(8193) } }), /too large/);
assert.throws(() => share.encode({ filters: Array(5000).fill(false) }), /too large/);
assert.throws(() => share.encode({ filters: ["🛸".repeat(4000), "🛸".repeat(4000)] }), /too large/);
let nested = false;
for (let index = 0; index < 16; index += 1) nested = { child: nested };
assert.throws(() => share.encode({ controls: nested }), /too large/);
const cyclic = { controls: {} }; cyclic.controls.self = cyclic;
assert.throws(() => share.encode(cyclic), /invalid/);
const getter = { filters: {} };
Object.defineProperty(getter.filters, "keyword", { enumerable: true, get() { assert.fail("getters must never execute"); } });
assert.throws(() => share.encode(getter), /invalid/);
assert.throws(() => share.encode({ filters: new Array(3) }), /invalid/);
const symbol = { filters: { [Symbol("hidden")]: true } };
assert.throws(() => share.encode(symbol), /invalid/);
const inherited = Object.create({ keyword: "not owned" }); inherited.enabled = false;
assert.throws(() => share.encode({ filters: inherited }), /invalid/);
const nullPrototype = Object.create(null); nullPrototype.settings = Object.create(null); nullPrototype.settings.enabled = false;
assert.deepEqual(share.decode(share.encode(nullPrototype)), { settings: { enabled: false } });

// Exercise the actual browser path without Buffer. Storage access throws, so a
// successful round trip proves that visitor preferences cannot alter the token.
const code = readFileSync(new URL("../share_view.js", import.meta.url), "utf8");
for (const preference of ["arrows-on", "arrows-off"]) {
  const browser = vm.createContext({ URL, URLSearchParams, TextEncoder, TextDecoder,
    btoa: text => Buffer.from(text, "binary").toString("base64"),
    atob: text => Buffer.from(text, "base64").toString("binary"),
    get localStorage() { assert.fail("shared views must not read storage: " + preference); },
  });
  vm.runInContext(code, browser);
  browser.snapshotJson = original;
  const browserToken = vm.runInContext("UfoShareView.encode(JSON.parse(snapshotJson))", browser);
  assert.equal(browserToken, token);
  browser.token = token;
  assert.equal(vm.runInContext("JSON.stringify(UfoShareView.decode(token))", browser), original);
}
const nodeFallback = vm.createContext({ Buffer, URL, URLSearchParams });
vm.runInContext(code, nodeFallback);
nodeFallback.token = token;
assert.equal(vm.runInContext("JSON.stringify(UfoShareView.decode(token))", nodeFallback), original, "Node fallback decodes UTF-8 without TextDecoder");
console.log("Shared-view tests passed: exact snapshots, portable URLs, storage independence, versioning, safe cloning and bounded invalid-input rejection.");

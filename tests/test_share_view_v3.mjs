import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { gzipSync } from "node:zlib";
import vm from "node:vm";

const require = createRequire(import.meta.url);
const share = require("../share_view.js");
const clone = value => JSON.parse(JSON.stringify(value));
const raw = value => "3.r." + Buffer.from(JSON.stringify(value), "utf8").toString("base64url");
const zipped = value => "3.g." + gzipSync(Buffer.from(JSON.stringify(value), "utf8")).toString("base64url");
const oldBaselineToken = "2." + gzipSync(Buffer.from('["d",[0]]', "utf8")).toString("base64url");
const baseline = await share.decodeAny(oldBaselineToken);
const defaultToken = "3.r.W10"; // Frozen empty-delta wire fixture: []

assert.equal(share.COMPACT_VERSION, 3);
assert.deepEqual(await share.decodeAny(defaultToken), baseline,
  "v3 starts from the same immutable protocol defaults as existing v2 links");
assert.equal(await share.encodeCompact(baseline), defaultToken);

// Frozen preorder path IDs, not derived from the implementation under test.
const arrowsPath = 31;
const militaryPath = 36;
const one = clone(baseline);
one.settings.showTraceDirectionArrows = true;
const oneToken = "3.r.WzMxXQ"; // [31]
assert.equal(await share.encodeCompact(one), oneToken);
assert.deepEqual(await share.decodeAny(oneToken), one);
const two = clone(one);
two.settings.overlayVisibility.military = false;
const several = clone(two);
several.settings.traceWidthScale = 0.05;
several.settings.playbackTracePersistence = "persistent";
several.layers.animals.enabled = true;
several.layers.crops.enabled = true;
const tokens = await Promise.all([one, two, several].map(value => share.encodeCompact(value)));
assert.ok(tokens[0].length < tokens[1].length && tokens[1].length < tokens[2].length,
  "one, two and several changed settings produce progressively larger tokens");
assert.ok(tokens[0].length <= 12 && tokens[1].length <= 20,
  "one or two checkbox changes avoid gzip headers and recursive delta overhead");

const userV2 = "2.H4sIAAAAAAAACnVQyWrDQAz9F53HRtJsnvkV40PwEoKbuHgJLsH_XkaunULpZXiL0HuaEhpQJasX9HqF-IMWiCUpCkxYKejJn5wS50441Ms0D3dIkrmI9IKeW4gUiCkNFgkzCW4gAiNzhjbDAEnyp1Rk6GGrNlVWkkDHOlohZmRzdoULVqMPxmufRhBiZjAni2SMC8TonElVaoice6ugdxChHh7d7bqMbQNbWq2v55l3CZnHpZXM4TB4P6a7fEziaP2LHxWNExFztEL3xpQXsmsSxoLnP7_F4y59tuN0m-b2Me-fqM8GqwzYPe2IpK_Dfx6AzPuGs9m_5vupvgEioqCg-QEAAA";
const userSnapshot = await share.decodeAny(userV2);
const userCompact = await share.encodeCompact(userSnapshot);
assert.ok(userCompact.length < userV2.length,
  "the exact supplied view shrinks without changing a single saved field");
assert.deepEqual(await share.decodeAny(userCompact), userSnapshot);

const evidence = JSON.parse(readFileSync(new URL("../docs/qa/share-view-20261031/browser.json", import.meta.url), "utf8"));
const unusual = clone(baseline);
unusual.filters.keyword = "Высота 611 · lumière 🛸";
unusual.settings.unknown = { "": null, "~k0": false, "k0": [], value: [false, null, 0, ""] };
unusual.settings[""] = false;
unusual.controls = { nested: { checked: false }, custom: null };
unusual.map = { lat: 55.91227293006361, lng: -3.5156250000000004, zoom: 6.25, basemap: "configured" };
unusual.region.shapes = [{ type: "rectangle", bounds: { west: 170, east: 190, north: 20, south: -10 } }];
unusual.selection = 4316005650816402;
const missing = clone(baseline);
delete missing.settings.showTraceDirectionArrows;
delete missing.filters.facets.type.selectedValues;
delete missing.layers;
const explicit = clone(baseline);
explicit.settings.showTraceDirectionArrows = null;
explicit.filters.facets.source.selectedValues = [];
explicit.settings.craftTypeColorOverrides = null;
explicit.selection = "";
explicit.settings.playbackWindowDays = 0;
const variants = [one, two, several, unusual, missing, explicit, {}, { settings: null },
  { controls: { "": false } }, evidence.caseRoundTrip.expected, evidence.customAreaRoundTrip.expected];
for (const snapshot of variants) {
  const before = JSON.stringify(snapshot);
  assert.deepEqual(await share.decodeAny(await share.encodeCompact(snapshot)), snapshot);
  assert.deepEqual(await share.decodeAny(share.encode(snapshot)), snapshot, "legacy v1 remains readable");
  assert.equal(JSON.stringify(snapshot), before, "encoding never mutates input");
}

const mutable = await share.decodeAny(defaultToken);
mutable.settings.overlayVisibility.military = false;
mutable.region.shapes.push({ type: "circle" });
assert.deepEqual(await share.decodeAny(defaultToken), baseline,
  "decoded objects never share mutable references with frozen protocol defaults");
assert.deepEqual(await share.decodeAny(raw([arrowsPath, militaryPath])), two);
assert.deepEqual(await share.decodeAny(zipped([arrowsPath, militaryPath])), two);

const compactUrl = await share.buildCompactUrl(two,
  "https://ufo-timeline.pages.dev/?debug=1#analysis-section-overview");
const compactAddress = new URL(compactUrl);
assert.equal(compactAddress.search, "");
assert.equal(new URLSearchParams(compactAddress.hash.slice(1)).get("s"), "overview");
assert.equal(share.readSectionHash(compactUrl), "#analysis-section-overview");
assert.deepEqual(await share.readAnyUrl(compactUrl), two);
assert.equal(await share.buildCompactUrl(two, compactUrl), compactUrl,
  "resharing retains the abbreviated analysis location without adding parameters");
for (const suffix of ["&s=", "&s=overview&s=time", "&s=time&section=analysis-section-overview",
  "&s=%3Cscript%3E", "&s=" + "x".repeat(80)]) {
  assert.equal(share.readSectionHash("https://example.test/#view=" + oneToken + suffix), "",
    "empty, ambiguous or unsafe navigation abbreviations do not become section anchors");
}
assert.equal(share.readSectionHash("https://example.test/#s=overview"), "");
const contextUrl = await share.buildCompactUrl(two, "https://example.test/#analysis-crop-context");
assert.equal(share.readSectionHash(contextUrl), "#analysis-crop-context",
  "nonsection context anchors retain their established form");

// A delta may not depend on operation order or walk through inherited/array data.
const malformed = [null, {}, true, [null], [[]], [true], [31.5], [-1], [99999], [5], [22],
  [[31, true, false]], [["settings.showTraceDirectionArrows", true]],
  [[["unknownRoot"], false]], [[["settings", "__proto__"], { "~polluted": true }]],
  [[["settings", "constructor", "prototype"], {}]], [[["settings", "prototype"], false]],
  [[["controls", "missingParent"], false]],
  [[["filters", "facets", "type", "selectedValues", "0"], "anything"]],
  [31, 31], [[31, true], 31], [[31], [31, true]],
  [[22, null], 31], [31, [22]],
  [31, [["settings", "showTraceDirectionArrows"], false]],
  [[["settings", "new"], {}], [["settings", "new", "child"], true]],
  [[["settings", ...Array(14).fill("nested")], null]],
  [[["settings", "x".repeat(129)], null]],
  [[31, { "~__proto__": { "~polluted": true } }]],
];
for (const operations of malformed) {
  await assert.rejects(share.decodeAny(raw(operations)), Error,
    "malformed, overlapping, forbidden or non-Boolean inversion paths are rejected");
}
assert.equal({}.polluted, undefined);
for (const token of ["3.", "3.r.", "3.g.", "3.x.W10", "3.r.a", "3.r._w", defaultToken + "=", "03.r.W10"]) {
  await assert.rejects(share.decodeAny(token), Error);
}
await assert.rejects(share.decodeAny("4.r.W10"), /newer/i);
await assert.rejects(share.decodeAny(raw(Array(5000).fill(31))), /large|invalid/i);
await assert.rejects(share.decodeAny(zipped([[18, "x".repeat(24577)]])), /large/i,
  "compressed output is limited before parsing or applying operations");
await assert.rejects(share.decodeAny(raw([[18, "x".repeat(8193)]])), /large/i);
const compressedBytes = Buffer.from(zipped([31]).slice(4), "base64url");
compressedBytes[compressedBytes.length - 8] ^= 255;
await assert.rejects(share.decodeAny("3.g." + compressedBytes.toString("base64url")), Error);

// Raw deltas stay portable without compression support or Node Buffer.
const code = readFileSync(new URL("../share_view.js", import.meta.url), "utf8");
const browser = vm.createContext({ URL, URLSearchParams, TextEncoder, TextDecoder,
  btoa: value => Buffer.from(value, "binary").toString("base64"),
  atob: value => Buffer.from(value, "base64").toString("binary"),
  get localStorage() { assert.fail("recipient preferences must not affect restoration"); },
});
vm.runInContext(code, browser);
browser.snapshotJson = JSON.stringify(two);
const noCompressionToken = await vm.runInContext("UfoShareView.encodeCompact(JSON.parse(snapshotJson))", browser);
assert.equal(noCompressionToken, tokens[1]);
browser.token = noCompressionToken;
assert.deepEqual(JSON.parse(await vm.runInContext("UfoShareView.decodeAny(token).then(JSON.stringify)", browser)), two);
browser.token = zipped([31]);
await assert.rejects(vm.runInContext("UfoShareView.decodeAny(token)", browser), /browser|support|decompress/i);

console.log("Share v3 passed: exact defaults/deltas, progressively shorter small changes, legacy compatibility, mutation isolation, malformed-operation rejection and browser raw fallback.",
  JSON.stringify({ oneChange: tokens[0].length, twoChanges: tokens[1].length, severalChanges: tokens[2].length,
    suppliedV2: userV2.length, suppliedV3: userCompact.length }));

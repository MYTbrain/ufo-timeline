import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import crypto from "node:crypto";
import zlib from "node:zlib";
import { createRequire } from "node:module";
import { buildSearchIndex, decodeVarints } from "../scripts/build_search_index.mjs";

const require = createRequire(import.meta.url);
const Query = require("../search_query.js");
const temp = fs.mkdtempSync(path.join(os.tmpdir(), "ufo-search-fixture-"));
const source = path.join(temp, "inputs");
fs.mkdirSync(source);
const rows = [
  { event_id: 0, description: "Beings collected topsoil and plants.", source: "fixture", has_coordinates: false },
  { event_id: 4503599627370495, raw_event_block: "ARIEL account: sand, soil; red craft.", source: "fixture" },
  { event_id: "9007199254740993", description: "Planets, plantations; échantillon 🌱.", location_raw: "Île de Ré" },
  { event_id: 8, description: "Only the current catalog may be indexed." },
  { event_id: 9, description: "Plants appeared in a separate account." },
];
function writeJson(file, object) {
  const bytes = zlib.gzipSync(Buffer.from(JSON.stringify(object)));
  const filename = path.join(source, file);
  fs.writeFileSync(filename, bytes);
  return { path: filename, sha256: crypto.createHash("sha256").update(bytes).digest("hex") };
}
const summary = writeJson("summary.json.gz", rows.filter(row => row.event_id !== 8).map(row => ({ event_id: row.event_id })));
const chunk = writeJson("detail.json.gz", rows);
const pins = path.join(source, "pins.json");
fs.writeFileSync(pins, JSON.stringify({ summary_shards: [summary], detail_chunks: [{ ...chunk, id: "fixture" }] }));
const output = path.join(temp, "index");
const result = await buildSearchIndex({ pinsPath: pins, outputDir: output, pageSize: 1, maxPackBytes: 180,
  expectedRecordCount: 4 });
const manifest = result.manifest;
assert.equal(manifest.recordCount, 4);
assert.equal(manifest.coverage.complete, true);
assert.equal(manifest.coverage.currentCatalogIdSetSha256, manifest.coverage.indexedIdSetSha256);
assert.equal(manifest.coverage.includesUnmapped, true);
assert.ok(manifest.textPacks.length > 1, "Fixture forces text pack boundaries.");
assert.ok([...manifest.textPacks, ...manifest.postingPacks].every(pack => pack.bytes <= 180));
const unzip = file => JSON.parse(zlib.gunzipSync(fs.readFileSync(path.join(output, file))).toString());
const ids = unzip(manifest.ids.file), lexicon = unzip(manifest.lexicon.file), pages = unzip(manifest.pages.file);
assert.deepEqual(ids, ["0", "4503599627370495", "9007199254740993", "9"], "IDs remain exact strings; held detail is excluded.");
function range(packs, start, length) {
  const pack = packs.find(pack => start >= pack.start && start + length <= pack.start + pack.bytes);
  assert.ok(pack, "Every member stays within one immutable pack.");
  return fs.readFileSync(path.join(output, pack.file)).subarray(start - pack.start, start - pack.start + length);
}
const restored = pages.flatMap(page => JSON.parse(zlib.gunzipSync(range(manifest.textPacks, page[0], page[1])).toString()));
assert.deepEqual(restored, rows.filter(row => row.event_id !== 8).map(Query.serializeEvent));
for (const term of ["soil", "plants", "ariel", "échant", "îl", "red", "0", "plant", "900"] ) {
  const indexed = new Set();
  for (const [token, offset, length, df] of lexicon) {
    if (!token.includes(term)) continue;
    const ordinals = decodeVarints(range(manifest.postingPacks, offset, length));
    assert.equal(ordinals.length, df);
    for (const ordinal of ordinals) indexed.add(ordinal);
  }
  const expected = restored.flatMap((text, ordinal) => text.includes(term) ? [ordinal] : []);
  assert.deepEqual([...indexed].sort((a, b) => a - b), expected, "Word-fragment postings must be exact: " + term);
}
const phrase = "soil and plants";
let conservative = null;
for (const part of phrase.split(" ")) {
  const candidates = new Set();
  for (const [token, offset, length] of lexicon) if (token.includes(part)) {
    for (const ordinal of decodeVarints(range(manifest.postingPacks, offset, length))) candidates.add(ordinal);
  }
  conservative = conservative === null ? candidates : new Set([...conservative].filter(value => candidates.has(value)));
}
assert.deepEqual([...conservative].filter(ordinal => restored[ordinal].includes(phrase)), [0]);
await assert.rejects(() => buildSearchIndex({ pinsPath: pins, outputDir: output }), /never overwritten/);
await assert.rejects(() => buildSearchIndex({ pinsPath: pins, outputDir: path.join(temp, "budget"), maxBytes: 10 }), /hard disk budget/);
const broken = path.join(source, "broken.json");
fs.writeFileSync(broken, JSON.stringify({ summary_shards: [summary], detail_chunks: [] }));
await assert.rejects(() => buildSearchIndex({ pinsPath: broken, outputDir: path.join(temp, "missing") }), /coverage failed/);
const stale = path.join(source, "stale.json");
fs.writeFileSync(stale, JSON.stringify({ summary_shards: [{ ...summary, sha256: "0".repeat(64) }], detail_chunks: [chunk] }));
await assert.rejects(() => buildSearchIndex({ pinsPath: stale, outputDir: path.join(temp, "stale") }), /Input hash changed/);
await assert.rejects(() => buildSearchIndex({ pinsPath: pins, outputDir: path.join(temp, "count"), expectedRecordCount: 5 }), /required report count/);
assert.throws(() => decodeVarints(Uint8Array.from([128])), /Truncated/);
console.log("search index: exact IDs, substring postings, Unicode, unmapped coverage, page ranges, hard budget and source guards passed");
// All paths below are unique, small, generated test fixtures owned by this run.
fs.rmSync(temp, { recursive: true });

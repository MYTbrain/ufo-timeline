import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import zlib from "node:zlib";
import crypto from "node:crypto";
import { createRequire } from "node:module";
import { buildSearchIndex, decodeVarints } from "../scripts/build_search_index.mjs";
import { buildSearchAccelerator, DEFAULT_TERMS, unionPosting } from "../scripts/build_search_accelerator.mjs";
const require = createRequire(import.meta.url), Query = require("../search_query.js");
const sha = bytes => crypto.createHash("sha256").update(bytes).digest("hex");
const temp = fs.mkdtempSync(path.join(os.tmpdir(), "ufo-fragment-fixture-"));
const rows = [
  { event_id: 0, description: "Bright RED craft collected topsoil." },
  { event_id: 1, description: "A tired grey being carried plants." },
  { event_id: 2, description: "SANDY beach. DNA sample. Ufo." },
  { event_id: 3, description: "Réd échantillon 21:40. 0123456789" },
  { event_id: 4, description: "Unreported observer." },
  { event_id: 5, description: "Redwood tree; blue light." },
  { event_id: "9007199254740993", description: "red soil" },
];
function input(file, value) {
  const bytes = zlib.gzipSync(Buffer.from(JSON.stringify(value))), filename = path.join(temp, file);
  fs.writeFileSync(filename, bytes);
  return { path: filename, sha256: sha(bytes) };
}
const summary = input("summary.json.gz", rows.map(row => ({ event_id: row.event_id })));
const detail = input("detail.json.gz", rows);
const pins = path.join(temp, "pins.json");
fs.writeFileSync(pins, JSON.stringify({ summary_shards: [summary], detail_chunks: [detail] }));
async function base(name) {
  const directory = path.join(temp, name);
  await buildSearchIndex({ pinsPath: pins, outputDir: directory, pageSize: 2 });
  return directory;
}
const directory = await base("index"), proofPath = path.join(temp, "accelerator-proof.json");
const oldManifestBytes = fs.readFileSync(path.join(directory, "manifest.json"));
const oldManifest = JSON.parse(oldManifestBytes.toString());
const oldHashes = new Map([...oldManifest.textPacks, ...oldManifest.postingPacks].map(pack =>
  [pack.file, sha(fs.readFileSync(path.join(directory, pack.file)))]));
const terms = ["red", "soil", "plant", "dna", "échant", "ré", "unknownzz", "a", "0", "ufo", "21", "grey"];
const result = await buildSearchAccelerator({ directory, proofPath, terms, maxPackBytes: 12,
  expectedManifestSha256: sha(oldManifestBytes) });
assert.equal(result.proof.status, "complete");
assert.equal(result.proof.sourceManifestSha256, sha(oldManifestBytes));
assert.equal(result.proof.nextManifestSha256, sha(fs.readFileSync(path.join(directory, "manifest.json"))));
assert.ok(result.manifest.fragmentPacks.every(pack => pack.bytes <= 12));
assert.ok(result.manifest.fragmentPacks.length > 1, "Fixture exercises accelerator pack rollover.");
for (const [file, expected] of oldHashes) assert.equal(sha(fs.readFileSync(path.join(directory, file))), expected);
const ids = JSON.parse(zlib.gunzipSync(fs.readFileSync(path.join(directory, oldManifest.ids.file))).toString());
for (const [term, offset, length, frequency] of result.manifest.fragments) {
  let ordinals = [];
  if (length) {
    const pack = result.manifest.fragmentPacks.find(pack => offset >= pack.start && offset + length <= pack.start + pack.bytes);
    assert.ok(pack);
    const bytes = fs.readFileSync(path.join(directory, pack.file)).subarray(offset - pack.start, offset - pack.start + length);
    ordinals = decodeVarints(bytes);
  }
  const expected = rows.flatMap((row, ordinal) => Query.serializeEvent(row).includes(term) ? [ordinal] : []);
  assert.deepEqual(ordinals, expected, "Exact vocabulary substring union: " + term);
  assert.equal(frequency, expected.length);
  assert.deepEqual(ordinals.map(ordinal => ids[ordinal]), expected.map(ordinal => String(rows[ordinal].event_id)));
}
assert.deepEqual(result.manifest.fragments.find(row => row[0] === "unknownzz"), ["unknownzz", 0, 0, 0]);
assert.ok(DEFAULT_TERMS.length >= 150 && DEFAULT_TERMS.length <= 250);
assert.equal(new Set(DEFAULT_TERMS).size, DEFAULT_TERMS.length);
for (const character of "abcdefghijklmnopqrstuvwxyz0123456789") assert.ok(DEFAULT_TERMS.includes(character));
for (const term of DEFAULT_TERMS) assert.ok(Query.isWordFragment(term));
await assert.rejects(() => buildSearchAccelerator({ directory, proofPath }), /already exists/);
const invalid = await base("invalid");
await assert.rejects(() => buildSearchAccelerator({ directory: invalid, proofPath,
  expectedManifestSha256: "0".repeat(64), terms }), /manifest pin drift/);
await assert.rejects(() => buildSearchAccelerator({ directory: invalid, proofPath, terms: ["red lights"] }), /pure Unicode word fragments/);
const beforeBudget = fs.readFileSync(path.join(invalid, "manifest.json"));
await assert.rejects(() => buildSearchAccelerator({ directory: invalid, proofPath, terms: ["a"], maxAddedBytes: 1 }), /disk budget/);
assert.deepEqual(fs.readFileSync(path.join(invalid, "manifest.json")), beforeBudget, "Budget refusal retains the old valid descriptor.");
assert.throws(() => unionPosting(new Uint8Array(1), Uint8Array.from([128]), 1), /truncated/);
assert.throws(() => unionPosting(new Uint8Array(1), Uint8Array.from([2]), 1), /exceeds/);
assert.throws(() => unionPosting(new Uint8Array(2), Uint8Array.from([0]), 2), /frequency/);
console.log("search accelerator: exact fragments, Unicode, zero matches, stable IDs, immutable source packs, budgets, QA hash and 247-term policy passed");
fs.rmSync(temp, { recursive: true });

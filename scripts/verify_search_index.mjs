/** Bounded source-to-index parity check. No source or generated asset is changed. */
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import zlib from "node:zlib";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { performance } from "node:perf_hooks";
import { decodeVarints } from "./build_search_index.mjs";
const require = createRequire(import.meta.url);
const Query = require("../search_query.js");
const args = process.argv.slice(2);
const option = name => { const index = args.indexOf(name); return index < 0 ? null : args[index + 1]; };
const directory = option("--index"), pinsPath = option("--pins");
if (!directory || !pinsPath) throw new Error("--index and --pins are required.");
const sha = bytes => crypto.createHash("sha256").update(bytes).digest("hex");
const manifest = JSON.parse(fs.readFileSync(path.join(directory, "manifest.json"), "utf8"));
const files = [manifest.ids, manifest.pages, manifest.lexicon, ...manifest.textPacks, ...manifest.postingPacks];
for (const entry of files) {
  const bytes = fs.readFileSync(path.join(directory, entry.file));
  assert.equal(bytes.length, entry.bytes);
  assert.equal(sha(bytes), entry.sha256, "Derivative hash mismatch: " + entry.file);
}
const load = entry => JSON.parse(zlib.gunzipSync(fs.readFileSync(path.join(directory, entry.file))).toString());
const started = performance.now();
const ids = load(manifest.ids), pages = load(manifest.pages), lexicon = load(manifest.lexicon);
const metadataMs = performance.now() - started;
const ordinalById = new Map(ids.map((id, ordinal) => [id, ordinal]));
const handles = new Map();
let postingBytes = 0, textBytes = 0;
function range(packs, offset, length, kind) {
  const pack = packs.find(pack => offset >= pack.start && offset + length <= pack.start + pack.bytes);
  assert.ok(pack, "Member crosses pack boundary.");
  let fd = handles.get(pack.file);
  if (fd === undefined) { fd = fs.openSync(path.join(directory, pack.file), "r"); handles.set(pack.file, fd); }
  const bytes = Buffer.alloc(length);
  assert.equal(fs.readSync(fd, bytes, 0, length, offset - pack.start), length);
  if (kind === "postings") postingBytes += length;
  else textBytes += length;
  return bytes;
}
const pins = JSON.parse(fs.readFileSync(pinsPath, "utf8"));
const selected = [0, 40, 80, 120, 160, 200, 240, 281].filter(value => value < pins.detail_chunks.length);
const sourceTexts = new Map();
for (const chunk of selected) {
  const pin = pins.detail_chunks[chunk];
  const bytes = fs.readFileSync(pin.path);
  assert.equal(sha(bytes), pin.sha256, "Source changed: " + pin.path);
  const events = JSON.parse((pin.path.endsWith(".gz") ? zlib.gunzipSync(bytes) : bytes).toString());
  for (const event of events) {
    const ordinal = ordinalById.get(String(event.event_id));
    if (ordinal !== undefined) sourceTexts.set(ordinal, Query.serializeEvent(event));
  }
}
const restored = new Map();
for (const pageIndex of new Set([...sourceTexts.keys()].map(ordinal => Math.floor(ordinal / manifest.pageSize)))) {
  const page = pages[pageIndex];
  const strings = JSON.parse(zlib.gunzipSync(range(manifest.textPacks, page[0], page[1], "text")).toString());
  assert.equal(strings.length, page[3]);
  for (let index = 0; index < strings.length; index++) if (sourceTexts.has(page[2] + index)) {
    restored.set(page[2] + index, strings[index]);
  }
}
for (const [ordinal, expected] of sourceTexts) assert.equal(restored.get(ordinal), expected, "Text serialization mismatch.");
const termCache = new Map();
function fragmentBitmap(fragment) {
  if (termCache.has(fragment)) return termCache.get(fragment);
  const bitmap = new Uint8Array(ids.length);
  for (const [token, offset, length, df] of lexicon) if (token.includes(fragment)) {
    const ordinals = decodeVarints(range(manifest.postingPacks, offset, length, "postings"));
    assert.equal(ordinals.length, df);
    for (const ordinal of ordinals) { assert.ok(ordinal < ids.length); bitmap[ordinal] = 1; }
  }
  termCache.set(fragment, bitmap);
  return bitmap;
}
function combine(type, children) {
  const value = new Uint8Array(ids.length);
  if (type === "and") value.fill(1);
  for (const child of children) for (let index = 0; index < value.length; index++) {
    value[index] = type === "and" ? value[index] & child[index] : value[index] | child[index];
  }
  return value;
}
function candidates(node) {
  if (node.type !== "term") return combine(node.type, node.children.map(candidates));
  const parts = Query.wordParts(node.value);
  if (!parts.length) return new Uint8Array(ids.length).fill(1);
  return combine("and", [...new Set(parts)].map(fragmentBitmap));
}
const queries = ["soil", "plants", "ariel", "red", "sand", "collection", "dna", "topsoil", "collected", "abduction",
  "échantillon", "1952", '"red lights"', '"soil and plants"', '"plant sample"', "soil AND plants", "sand OR soil",
  '"red lights" AND disc', "21:40", "source:"];
const checks = [];
for (const query of queries) {
  const plan = Query.compile(query), before = postingBytes, start = performance.now();
  const candidate = candidates(plan.ast);
  let expected = 0, actual = 0, exactFragmentChecks = 0;
  for (const [ordinal, text] of sourceTexts) {
    const direct = Query.matches(plan, text);
    if (direct) expected++;
    const indexed = candidate[ordinal] && Query.matches(plan, restored.get(ordinal));
    if (indexed) actual++;
    assert.equal(Boolean(indexed), direct, "Query parity: " + query + " report " + ids[ordinal]);
    if (plan.ast.type === "term" && Query.isWordFragment(plan.ast.value)) {
      assert.equal(Boolean(candidate[ordinal]), direct, "Word-fragment fast lane must be exact.");
      exactFragmentChecks++;
    }
  }
  checks.push({ query, matchesInSourceSample: actual, parity: actual === expected, exactFragmentChecks,
    postingBytes: postingBytes - before, milliseconds: Math.round(performance.now() - start) });
}
for (const fd of handles.values()) fs.closeSync(fd);
const report = { complete: true, indexedReports: ids.length, sourceChunks: selected.length,
  sourceReports: sourceTexts.size, textRoundTripReports: restored.size, queries: checks,
  metadataCompressedBytes: manifest.ids.bytes + manifest.lexicon.bytes + manifest.pages.bytes,
  metadataLocalLoadMs: Math.round(metadataMs), sampledTextBytes: textBytes, postingBytes,
  inputFilesChanged: false };
if (option("--out")) fs.writeFileSync(option("--out"), JSON.stringify(report, null, 2) + "\n");
console.log(JSON.stringify(report, null, 2));

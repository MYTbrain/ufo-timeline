/**
 * Build a bounded, disposable search derivative from pinned canonical inputs.
 * Raw inputs are read in place. Only compressed text pages and compact postings
 * are written; neither a corpus copy nor a static deployment tree is created.
 */
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import zlib from "node:zlib";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const Query = require("../search_query.js");
const MIB = 1024 * 1024;
const DEFAULT_CAP = 900 * MIB;
const DEFAULT_PACK_CAP = 32 * MIB;
const WORDS = /[\p{L}\p{M}\p{N}_]+/gu;

export function wordTokens(text) {
  return new Set(String(text).match(WORDS) || []);
}

export function appendVarint(target, number) {
  if (!Number.isSafeInteger(number) || number < 0 || number > 0xffffffff) {
    throw new Error("Posting delta is outside the uint32 ordinal range.");
  }
  do {
    const byte = number & 127;
    number = Math.floor(number / 128);
    if (target.length === target.bytes.length) {
      const grown = new Uint8Array(Math.max(8, target.bytes.length * 2));
      grown.set(target.bytes);
      target.bytes = grown;
    }
    target.bytes[target.length++] = byte | (number ? 128 : 0);
  } while (number);
}

export function decodeVarints(buffer) {
  const output = [];
  let previous = 0, value = 0, multiplier = 1;
  for (const byte of buffer) {
    value += (byte & 127) * multiplier;
    if (byte & 128) multiplier *= 128;
    else {
      previous += value;
      output.push(previous);
      value = 0;
      multiplier = 1;
    }
  }
  if (multiplier !== 1) throw new Error("Truncated posting varint.");
  return output;
}

function sha(bytes) { return crypto.createHash("sha256").update(bytes).digest("hex"); }
function idSetHash(ids) {
  const hash = crypto.createHash("sha256");
  for (const id of [...ids].sort()) hash.update(id + "\n");
  return hash.digest("hex");
}
function reportId(value) {
  if (value == null || (typeof value === "number" && !Number.isSafeInteger(value))) {
    throw new Error("Missing or unsafe report ID.");
  }
  return String(value);
}
function json(bytes, filename) {
  return JSON.parse((filename.endsWith(".gz") ? zlib.gunzipSync(bytes) : bytes).toString("utf8").replace(/^\uFEFF/, ""));
}
function pinnedJson(pin) {
  const bytes = fs.readFileSync(pin.path);
  if (pin.sha256 && sha(bytes) !== pin.sha256) throw new Error("Input hash changed: " + pin.path);
  return json(bytes, pin.path);
}

/** A logical byte stream split without cutting a list or compressed text page. */
class PackWriter {
  constructor(output, stem, budget, maxPackBytes) {
    this.output = output;
    this.stem = stem;
    this.budget = budget;
    this.maxPackBytes = maxPackBytes;
    this.offset = 0;
    this.packs = [];
    this.fd = null;
    this.current = null;
    this.hash = null;
  }
  finishPack() {
    if (this.fd === null) return;
    fs.closeSync(this.fd);
    this.current.sha256 = this.hash.digest("hex");
    this.fd = null;
  }
  write(bytes) {
    if (bytes.byteLength > this.maxPackBytes) throw new Error(this.stem + " member exceeds the pack limit.");
    if (!this.current || this.current.bytes + bytes.byteLength > this.maxPackBytes) {
      this.finishPack();
      const file = this.stem + "_" + String(this.packs.length).padStart(3, "0") + ".pack";
      this.current = { file, start: this.offset, bytes: 0, sha256: null };
      this.packs.push(this.current);
      this.fd = fs.openSync(path.join(this.output, file), "wx");
      this.hash = crypto.createHash("sha256");
    }
    this.budget.reserve(bytes.byteLength);
    const start = this.offset;
    fs.writeSync(this.fd, bytes);
    this.hash.update(bytes);
    this.current.bytes += bytes.byteLength;
    this.offset += bytes.byteLength;
    return [start, bytes.byteLength];
  }
  finish() { this.finishPack(); return this.packs; }
}

export async function buildSearchIndex(options) {
  const output = path.resolve(options.outputDir);
  const pageSize = options.pageSize || 16;
  const maxBytes = Math.min(DEFAULT_CAP, options.maxBytes || DEFAULT_CAP);
  const maxPackBytes = Math.min(DEFAULT_PACK_CAP, options.maxPackBytes || DEFAULT_PACK_CAP);
  if (!Number.isSafeInteger(pageSize) || pageSize < 1 || pageSize > 128) throw new Error("Page size must be between 1 and 128.");
  if (fs.existsSync(output) && fs.readdirSync(output).length) throw new Error("Output must be new or empty; existing derivatives are never overwritten.");
  fs.mkdirSync(output, { recursive: true });
  const budget = { used: 0, reserve(bytes) {
    if (this.used + bytes > maxBytes) throw new Error("Search derivative reached its hard disk budget; retained partial build for explicit review.");
    this.used += bytes;
  }};
  const writeFile = (file, bytes) => {
    budget.reserve(bytes.byteLength);
    fs.writeFileSync(path.join(output, file), bytes, { flag: "wx" });
    return { file, bytes: bytes.byteLength, sha256: sha(bytes) };
  };
  const notes = Buffer.from("Purpose: current candidate search derivative, not a corpus backup.\nProvenance: pinned canonical detail chunks filtered to pinned current summary IDs.\nRebuild: scripts/build_search_index.mjs --pins <input_pins.json> --output <new directory>.\nRetention: retain if validated and referenced by release; partial builds require explicit review before deletion.\nNo raw dataset or static bundle has been copied here.\n");
  writeFile("PURPOSE.txt", notes);
  const pinsBytes = fs.readFileSync(options.pinsPath);
  const pins = JSON.parse(pinsBytes.toString("utf8").replace(/^\uFEFF/, ""));
  const progress = options.onProgress || (() => {});
  const currentIds = new Set();
  for (let index = 0; index < pins.summary_shards.length; index++) {
    const rows = pinnedJson(pins.summary_shards[index]);
    if (!Array.isArray(rows)) throw new Error("Summary input must be an array.");
    for (const row of rows) {
      if (row.event_id == null) throw new Error("Current catalog row has no report ID.");
      const id = reportId(row.event_id);
      if (currentIds.has(id)) throw new Error("Duplicate current catalog ID: " + id);
      currentIds.add(id);
    }
  }
  const expectedRecordCount = currentIds.size;
  if (options.expectedRecordCount != null && expectedRecordCount !== options.expectedRecordCount) {
    throw new Error("Current catalog differs from required report count: " + expectedRecordCount);
  }
  const currentCatalogIdSetSha256 = idSetHash(currentIds);
  progress({ phase: "catalog", recordCount: expectedRecordCount });
  const text = new PackWriter(output, "text", budget, maxPackBytes);
  const pages = [];
  const ids = [];
  const seen = new Set();
  const postings = new Map();
  const inputProof = [];
  let texts = [], pageStart = 0, physicalRows = 0;
  function flushPage() {
    if (!texts.length) return;
    const compressed = zlib.gzipSync(Buffer.from(JSON.stringify(texts)), { level: 6 });
    const range = text.write(compressed);
    pages.push([range[0], range[1], pageStart, texts.length]);
    texts = [];
    pageStart = ids.length;
  }
  for (let chunkIndex = 0; chunkIndex < pins.detail_chunks.length; chunkIndex++) {
    const pin = pins.detail_chunks[chunkIndex];
    const events = pinnedJson(pin);
    if (!Array.isArray(events)) throw new Error("Detail input must be an array.");
    physicalRows += events.length;
    for (const event of events) {
      const id = reportId(event.event_id);
      if (!currentIds.has(id)) continue;
      if (seen.has(id)) throw new Error("Duplicate current report in details: " + id);
      seen.add(id);
      const ordinal = ids.length;
      ids.push(id);
      const normalized = Query.serializeEvent(event);
      texts.push(normalized);
      for (const token of wordTokens(normalized)) {
        let posting = postings.get(token);
        if (!posting) {
          posting = { bytes: new Uint8Array(8), length: 0, previous: 0, count: 0 };
          postings.set(token, posting);
        }
        appendVarint(posting, ordinal - posting.previous);
        posting.previous = ordinal;
        posting.count++;
      }
      if (texts.length === pageSize) flushPage();
    }
    inputProof.push({ id: pin.id, url: pin.url || null, sha256: pin.sha256 || null, physicalRows: events.length });
    progress({ phase: "details", chunk: chunkIndex + 1, chunks: pins.detail_chunks.length,
      recordCount: ids.length, tokenCount: postings.size, outputBytes: budget.used });
  }
  flushPage();
  text.finish();
  if (seen.size !== expectedRecordCount) {
    const missing = [];
    for (const id of currentIds) if (!seen.has(id) && missing.length < 20) missing.push(id);
    throw new Error("Full catalog coverage failed: " + seen.size + " / " + expectedRecordCount + "; missing IDs " + missing.join(", "));
  }
  const index = new PackWriter(output, "postings", budget, maxPackBytes);
  const lexicon = [];
  let postingCount = 0;
  for (const token of [...postings.keys()].sort()) {
    const posting = postings.get(token);
    const range = index.write(posting.bytes.subarray(0, posting.length));
    lexicon.push([token, range[0], range[1], posting.count]);
    postingCount += posting.count;
    postings.delete(token);
  }
  index.finish();
  const idsFile = writeFile("ids.json.gz", zlib.gzipSync(Buffer.from(JSON.stringify(ids)), { level: 6 }));
  const pagesFile = writeFile("pages.json.gz", zlib.gzipSync(Buffer.from(JSON.stringify(pages)), { level: 6 }));
  const lexiconFile = writeFile("lexicon.json.gz", zlib.gzipSync(Buffer.from(JSON.stringify(lexicon)), { level: 6 }));
  const sourceProof = writeFile("source_pins.json", Buffer.from(JSON.stringify({
    inputPinsSha256: sha(pinsBytes), summaries: pins.summary_shards.map(pin => ({ url: pin.url || null, sha256: pin.sha256, rows: pin.rows })),
    details: inputProof,
    overlaysExcludedFromRawText: (pins.overlays || []).map(pin => ({ path: pin.path, sha256: pin.sha256 }))
  }, null, 2) + "\n"));
  const manifest = {
    schemaVersion: 1,
    serializerVersion: Query.VERSION,
    normalization: "JavaScript String.toLowerCase; exact preserved-text field serialization",
    tokenizer: "Unicode letters, marks, numbers, underscore; substring scan of vocabulary",
    countingUnit: "current canonical catalog report representation",
    recordCount: ids.length, expectedRecordCount, physicalRows, pageSize,
    tokenCount: lexicon.length, postingCount,
    coverage: { complete: true, currentCatalogIds: currentIds.size, indexedIds: seen.size,
      currentCatalogIdSetSha256, indexedIdSetSha256: idSetHash(seen),
      rawPreservedText: true, includesUnmapped: true, currentMetadataOverlayMustBeUnioned: true },
    ids: { ...idsFile, encoding: "gzip-json-strings" },
    pages: { ...pagesFile, encoding: "gzip-json-page-ranges", row: ["offset", "byteLength", "firstOrdinal", "recordCount"] },
    lexicon: { ...lexiconFile, encoding: "gzip-json-token-ranges", row: ["token", "offset", "byteLength", "documentFrequency"] },
    textPacks: text.packs, postingPacks: index.packs,
    textEncoding: "independent-gzip-json-string-arrays",
    postingEncoding: "unsigned-base128-delta-varints; first delta is absolute ordinal",
    sourceProof, outputCapBytes: maxBytes, maxPackBytes,
    rebuild: "node scripts/build_search_index.mjs --pins <input_pins.json> --output <new empty directory>",
    retention: "Current candidate search derivative. Promote only after validation; no corpus backup or deployment copies."
  };
  const manifestBytes = Buffer.from(JSON.stringify(manifest, null, 2) + "\n");
  writeFile("manifest.json", manifestBytes);
  progress({ phase: "complete", recordCount: ids.length, tokenCount: lexicon.length,
    postingCount, outputBytes: budget.used, manifestSha256: sha(manifestBytes) });
  return { manifest, bytes: budget.used, manifestSha256: sha(manifestBytes) };
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const args = process.argv.slice(2);
  function value(flag, fallback) { const index = args.indexOf(flag); return index >= 0 ? args[index + 1] : fallback; }
  const pinsPath = value("--pins");
  const outputDir = value("--output");
  if (!pinsPath || !outputDir) throw new Error("Usage: node scripts/build_search_index.mjs --pins <input_pins.json> --output <new empty directory>");
  if (!/^d:/i.test(path.resolve(outputDir))) throw new Error("Full search derivatives must be built on primary data drive D:.");
  buildSearchIndex({ pinsPath, outputDir, pageSize: Number(value("--page-size", "16")),
    expectedRecordCount: Number(value("--expected-records", "702893")),
    onProgress: event => process.stdout.write(JSON.stringify(event) + "\n") }).catch(error => {
      process.stderr.write(error.stack + "\n"); process.exitCode = 1;
    });
}

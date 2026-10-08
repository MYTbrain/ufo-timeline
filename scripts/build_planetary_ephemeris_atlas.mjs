// Compact physical ephemeris only: shared corpus stays in its canonical root.
import fs from "node:fs";
import path from "node:path";
import zlib from "node:zlib";
import crypto from "node:crypto";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const Planetary = require("../analysis_planetary.js");
const args = process.argv.slice(2);
const option = name => args.includes(name) ? args[args.indexOf(name) + 1] : null;
const sharedRoot = option("--shared-root");
if (!sharedRoot) throw new Error("Supply --shared-root with the protected canonical workspace.");
const outputRoot = path.resolve(option("--output-root") || "data/analysis_comparisons");
const preflight = args.includes("--preflight");
const catalogRoot = path.join(sharedRoot, "data/research/analysis-repairs-20261007/catalog");
const summaryPath = path.join(catalogRoot, "summary_manifest.json");
const contextPath = path.resolve("data/analysis_comparisons/context_rows.json.gz");
const hash = buffer => crypto.createHash("sha256").update(buffer).digest("hex");
const inputs = [];
function read(filename, role) {
  const bytes = fs.readFileSync(filename);
  inputs.push({ path: filename, byteLength: bytes.length, sha256: hash(bytes), role });
  return JSON.parse(filename.endsWith(".gz") ? zlib.gunzipSync(bytes) : bytes);
}
const summary = read(summaryPath, "effective shared summary manifest");
const context = read(contextPath, "date-role-preserving crop/animal context");
if (context.ordinalEpoch !== "unix_day") throw new Error("Context epoch mismatch.");
let streamedRows = 0;
const started = performance.now();
const prepared = Planetary.preparePlanetaryCohort({ ordinalEpoch: "unix_day", crops: context.crops, animals: context.animals,
  forEachRow(accept) {
    for (const shard of summary) {
      const rows = read(path.join(catalogRoot, "summary_shards", shard.id + ".json.gz"), "shared effective summary shard");
      for (const value of rows) {
        accept({ datePrecision: value.date_precision, sortOrdinal: value.sort_date_iso ? Math.floor(Date.parse(value.sort_date_iso) / 86400000) : null,
          craftType: value.craft_type_inferred, source: value.source, type: value.type, visualTypeGroup: value.visual_type_group });
        streamedRows += 1;
      }
    }
  },
});
const minimumDay = Math.floor(Date.UTC(1582, 9, 15) / 86400000), maximumDay = Math.floor(Date.UTC(2100, 11, 31) / 86400000);
const months = new Set(), reportDates = new Set(), calendarDates = new Set();
for (const domain of prepared.domains) for (const group of domain.groups) {
  reportDates.add(group.startOrdinal);
  const date = new Date(group.startOrdinal * 86400000);
  months.add(date.getUTCFullYear() + "-" + String(date.getUTCMonth() + 1).padStart(2, "0"));
}
for (const month of months) {
  const [year, number] = month.split("-").map(Number);
  const start = Math.max(minimumDay, Math.floor(Date.UTC(year, number - 1, 1) / 86400000));
  const end = Math.min(maximumDay, Math.floor(Date.UTC(year, number, 1) / 86400000) - 1);
  for (let day = start; day <= end; day += 1) calendarDates.add(day);
}
const atlasDates = new Set(calendarDates);
for (const day of reportDates) { atlasDates.add(day - 1); atlasDates.add(day); atlasDates.add(day + 1); }
const dates = Array.from(atlasDates).sort((left, right) => left - right);
const expectedByteLength = Math.ceil((64 + dates.length * 4) / 8) * 8 + dates.length * 9 * 6 * 12 + dates.length * 6 * 8;
const intendedGzip = path.join(outputRoot, "ephemeris_atlas_v1.bin.gz");
const summaryInfo = { schemaId: "ufo-planetary-atlas-build-preflight-v1", streamedCatalogRows: streamedRows, exactReportDates: reportDates.size,
  representedMonths: months.size, calendarDateCount: calendarDates.size, atlasDateCount: dates.length, expectedLogicalBytes: expectedByteLength,
  destination: intendedGzip, estimatedStoredMiB: Math.round(expectedByteLength * 0.85 / 1048576),
  equivalentArtifactAlreadyExists: fs.existsSync(intendedGzip), fullCorpusCopied: false, retention: "One current lossless gzip atlas. Rebuild from protected shared summaries, context and pinned MIT ephemeris; no raw duplicate or version tree retained." };
console.log(JSON.stringify(summaryInfo));
if (preflight) process.exit(0);
if (expectedByteLength > 100 * 1048576) throw new Error("Atlas exceeds the declared bounded artifact plan; stop before creating it.");
fs.mkdirSync(outputRoot, { recursive: true });
Planetary.clearEphemerisAtlas();
const built = Planetary.buildEphemerisAtlasBuffer(dates, { onProgress(value) {
  console.log(JSON.stringify({ status: "building_raw_ephemeris", ...value, elapsedSeconds: Math.round((performance.now() - started) / 1000) }));
} });
const rawBytes = Buffer.from(built.buffer), gzip = zlib.gzipSync(rawBytes, { level: 9 });
const manifest = { ...built.metadata, file: path.basename(intendedGzip), sha256: hash(rawBytes), gzipSha256: hash(gzip), gzipByteLength: gzip.length,
  dayIndexSha256: hash(Buffer.from(Int32Array.from(dates).buffer)), reportDateCount: reportDates.size, calendarDateCount: calendarDates.size,
  representedMonths: months.size, generatedAt: new Date().toISOString(), buildRuntimeMilliseconds: Math.round(performance.now() - started),
  generator: { path: "scripts/build_planetary_ephemeris_atlas.mjs", sha256: hash(fs.readFileSync(new URL(import.meta.url))),
    enginePath: "analysis_planetary.js", engineSha256: hash(fs.readFileSync(path.resolve("analysis_planetary.js"))) },
  inputs, coveragePolicy: "Eligible exact Gregorian report dates and all candidate days in their represented year-months; report dates have a ±1-day ephemeris halo for full civil-UTC uncertainty. Atlas stores physical quantities, not source clocks, filtered counts, zodiac bins, observed visibility or houses.",
  float32RatePolicy: "Rates within1e-7 degree/day of classification thresholds are resolved against the original double-precision ephemeris at query time.",
  storage: { canonical: intendedGzip, uncompressedFileRetained: false, fullCorpusCopied: false, newFilesAbove100MiB: [],
    purpose: "Precomputed shared raw positions/rates/precession for responsive planet, partner and zodiac controls.",
    rebuild: "node scripts/build_planetary_ephemeris_atlas.mjs --shared-root <protected canonical workspace>",
    retention: "Current canonical gzip plus manifest. Generated RAM buffer is discarded after build; no versioned raw atlas or corpus staging tree." } };
const validation = Planetary.decodeEphemerisAtlas(built.buffer, manifest);
if (validation.dates.length !== dates.length) throw new Error("Built atlas failed final dimension validation.");
fs.writeFileSync(intendedGzip, gzip);
fs.writeFileSync(path.join(outputRoot, "ephemeris_atlas_manifest.json"), JSON.stringify(manifest, null, 2) + "\n");
console.log(JSON.stringify({ status: "built_validated", logicalBytes: rawBytes.length, storedBytes: gzip.length, storedMiB: Math.round(gzip.length / 1048576 * 100) / 100,
  elapsedMilliseconds: manifest.buildRuntimeMilliseconds, sha256: manifest.sha256, gzipSha256: manifest.gzipSha256, destination: intendedGzip }));

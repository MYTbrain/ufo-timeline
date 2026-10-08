import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { readFileSync } from "node:fs";
import vm from "node:vm";
import { gzipSync } from "node:zlib";
import { createHash } from "node:crypto";

const require = createRequire(import.meta.url);
const chronology = require("../trace_chronology.js");
const neighborhood = require("../trace_neighborhood.js");
const directions = require("../trace_direction_summary.js");
const source = readFileSync(new URL("../app.js", import.meta.url), "utf8");
const clone = value => JSON.parse(JSON.stringify(value));
const hour = 3600000;
const day = Date.parse("1994-09-16T00:00:00Z");
function payload(rows) {
  return { schemaId: chronology.SCHEMA_ID, sourceContract: chronology.SOURCE_CONTRACT, releaseId: "test-clock-evidence",
    rowSchema: [...chronology.ROW_SCHEMA], rows, codes: {
      evidence: [{ status: "accepted", kind: "source_clock", confidence: "high", basis: "Preserved occurrence clock and historical timezone" }],
      zone: ["Africa/Harare", "America/Los_Angeles"],
    } };
}
const input = payload([[1, day + 28 * hour, day + 28 * hour + 59999, 0, 1], [2, day + 8 * hour, day + 8 * hour + 59999, 0, 0],
  [3, day + 7 * hour, day + 9 * hour, 0, 0], [4, day + 8 * hour, day + 10 * hour, 0, 0]]);
const before = clone(input);
const index = chronology.createEvidenceIndex(input);
assert.deepEqual(input, before, "index construction leaves source artifact untouched");
assert.equal(index.snapshot().indexBytes, input.rows.length * 32, "runtime keeps compact typed arrays");
assert.equal(index.interval("2").zone, "Africa/Harare");
assert.equal(index.interval(null), null);
assert.equal(index.interval(true), null);
assert.equal(index.interval("missing"), null);
assert.equal(index.interval(5), null);
const jsonBytes = Buffer.from(JSON.stringify(input));
const gzipBytes = gzipSync(jsonBytes);
const pins = { gzipSha256: createHash("sha256").update(gzipBytes).digest("hex"),
  sha256: createHash("sha256").update(jsonBytes).digest("hex"), rowCount: input.rows.length };
assert.deepEqual(await chronology.decodeEvidenceResponse(new Response(gzipBytes), pins), input, "raw gzip is decoded and both release hashes checked");
assert.deepEqual(await chronology.decodeEvidenceResponse(new Response(jsonBytes, { headers: { "Content-Encoding": "gzip" } }), pins), input,
  "already-decoded Content-Encoding data is never decompressed twice");
await assert.rejects(chronology.decodeEvidenceResponse(new Response(gzipBytes), { ...pins, sha256: "0".repeat(64) }), /hash/);
await assert.rejects(chronology.decodeEvidenceResponse(new Response(gzipBytes), { ...pins, gzipSha256: "0".repeat(64) }), /hash/);
await assert.rejects(chronology.decodeEvidenceResponse(new Response(jsonBytes), { ...pins, rowCount: 9 }), /row count/);
await assert.rejects(chronology.decodeEvidenceResponse(new Response(gzipBytes.subarray(0, 15)), {}));
await assert.rejects(chronology.decodeEvidenceResponse(new Response("not JSON"), {}));
await assert.rejects(chronology.decodeEvidenceResponse(new Response("missing", { status: 404 }), {}), /response failed/);

const westToEast = { traceId: "1->2", fromEventId: 1, toEventId: 2, eventIds: [1, 2], from: [47, -122], to: [-18, 31], gapDays: 0 };
const ordered = chronology.orientSegment(index, westToEast);
assert.equal(ordered.traceId, "2->1");
assert.deepEqual(ordered.from, westToEast.to);
assert.deepEqual(ordered.to, westToEast.from);
assert.deepEqual(ordered.eventIds, [2, 1]);
assert.equal(ordered.sameDayOrderKnown, true, "later UTC date can follow an earlier report sharing its civil date");
assert.equal(westToEast.traceId, "1->2", "orientation never mutates shared cached source segment");
assert.equal(directions.segmentOrderUncertain(ordered), false);
const speed = chronology.hypotheticalSpeedRange(ordered.chronology, 1000);
assert.ok(speed.lowerKph < speed.upperKph && speed.lowerKph > 49 && speed.upperKph < 51,
  "hypothetical range uses UTC elapsed bounds rather than zero same-calendar-day gap");
assert.equal(chronology.hypotheticalSpeedRange({ status: "unknown" }, 1000), null);
assert.equal(chronology.hypotheticalSpeedRange({ status: "ordered", from: { startMs: 0, endMs: 100 }, to: { startMs: 100, endMs: 200 } }, 1000), null,
  "zero minimum elapsed time cannot yield a finite implied speed");
assert.equal(chronology.hypotheticalSpeedRange({ status: "ordered", from: { startMs: 0, endMs: 200 }, to: { startMs: 100, endMs: 300 } }, 1000), null);
assert.equal(chronology.resolvePair(index, 3, 4).reason, "overlapping_utc_intervals", "DST-like overlapping possible intervals remain unresolved");
assert.equal(chronology.resolvePair(index, 2, 99).reason, "missing_source_backed_time", "sentinel or missing clock absent from overlay cannot gain order");
assert.equal(chronology.resolvePair(index, 2, 2).status, "unknown", "simultaneous intervals have no order");
const touching = chronology.createEvidenceIndex(payload([[10, 100, 200, 0, 0], [11, 200, 300, 0, 0]]));
assert.equal(chronology.resolvePair(touching, 10, 11).status, "unknown", "interval boundaries must be strictly separated");
assert.match(chronology.intervalLabel(index.interval(2)), /1994-09-16T08:00:00.000Z.*Africa\/Harare.*occurrence clock/);

for (const mutation of [
  p => { p.sourceContract = "unverified"; }, p => { p.codes.evidence[0].status = "candidate"; },
  p => { p.codes.zone[0] = "not-a-timezone"; }, p => { p.rows[0][1] = null; },
  p => { p.rows[0][1] = false; }, p => { p.rows[0][2] = Infinity; }, p => { p.rows[0][2] = p.rows[0][1] - 1; },
  p => { p.rows[0][0] = Number.MAX_SAFE_INTEGER + 1; }, p => { p.rows[0][3] = 3; },
  p => { p.rows.push([...p.rows[0]]); }, p => { p.rowSchema[1] = "localMinutes"; },
]) {
  const invalid = clone(input); mutation(invalid);
  assert.throws(() => chronology.createEvidenceIndex(invalid), /Trace chronology/);
}

const noClock = { ...westToEast, fromEventId: 91, toEventId: 92, gapDays: 3, fromSortOrdinal: 100, toSortOrdinal: 103 };
const dateOrdered = chronology.orientSegment(null, noClock);
assert.equal(dateOrdered.sameDayOrderKnown, true);
assert.equal(dateOrdered.chronology.from.evidence.kind, "date_only");
assert.equal(dateOrdered.chronology.from.endMs < dateOrdered.chronology.to.startMs, true);
for (const gapDays of [0, 1, 2]) assert.equal(chronology.orientSegment(null, { ...noClock, gapDays }).sameDayOrderKnown, false);
assert.equal(chronology.orientSegment(null, { ...noClock, fromSortOrdinal: null }).sameDayOrderKnown, false);

const reports = [
  { event_id: 1, date_precision: "exact_day", sort_date_iso: "1994-09-16", sort_ordinal: Math.floor(day / 86400000), lat: 47, lon: -122,
    craft_type_inferred: "disc_saucer", has_coordinates: true, playback_sort_key: [2, 1] },
  { event_id: 2, date_precision: "exact_day", sort_date_iso: "1994-09-16", sort_ordinal: Math.floor(day / 86400000), lat: -18, lon: 31,
    craft_type_inferred: "disc_saucer", has_coordinates: true, playback_sort_key: [2, 999] },
];
const caseLinks = neighborhood.buildSameDayCraftTraceSegments(reports, { chronology: index, timingSupport: chronology });
assert.equal(caseLinks[0].traceId, "2->1", "famous-case chain uses evidence UTC rather than misleading local presentation keys");
assert.equal(caseLinks[0].sameDayOrderKnown, true);
const withoutEvidence = neighborhood.buildSameDayCraftTraceSegments(reports, { chronology: chronology.createEvidenceIndex(payload([])), timingSupport: chronology });
assert.equal(withoutEvidence[0].sameDayOrderKnown, false, "old keys cannot establish source-backed order");
const summary = directions.summarizeDirections([ordered, chronology.orientSegment(index, { ...westToEast, fromEventId: 3, toEventId: 4 })]);
assert.equal(summary.denominator, 1);
assert.equal(summary.unorderedSegments, 1);

function extract(name) {
  const start = source.indexOf(`function ${name}(`);
  assert.notEqual(start, -1, name);
  let depth = 0;
  for (let position = source.indexOf("{", start); position < source.length; position++) {
    if (source[position] === "{") depth++;
    if (source[position] === "}" && --depth === 0) return source.slice(start, position + 1);
  }
  assert.fail(name);
}
const runtime = { traceChronologyEvidence: index, traceChronologyStatus: "ready", filteredMappedCatalogDateAsc: true };
const bucket = { key: "gap_le_1", maxDays: 1 };
const artifact = { rowCount: 2 };
const state = { filteredMappedPlaybackEvents: reports, filteredMappedCatalog: reports, timelineDataVersion: 1, filterGeneration: 1 };
const context = vm.createContext({ TRACE_CHRONOLOGY: chronology, runtime, state,
  getCatalogEventById: id => reports.find(event => String(event.event_id) === String(id)),
  activeTraceBuckets: () => [bucket], filteredMappedEventIdSet: () => new Set(["1", "2"]),
  canonicalTraceSegmentsCacheKey: () => "legacy:" + runtime.traceChronologyEvidence.releaseId,
  canonicalTraceSegmentsPackedCacheKey: () => "packed:" + runtime.traceChronologyEvidence.releaseId,
  decodePackedTraceEventIndexRowForRender: (artifact, row) => reports[row],
  packedTraceOrdinalScanRange: () => ({ startRow: 0, endRow: 2, bounded: true }),
  playbackTrailBucketForGapDays: () => bucket,
  shortestWrappedSegment: (from, to) => ({ from: [from.lat, from.lon], to: [to.lat, to.lon] }),
  createTraceFacilityClassificationContext: () => ({}), applyTraceFacilityFilterToSegmentWithContext: segment => segment,
  applyTraceFacilityFilterToSegment: segment => segment, traceFacilityFilterEnabled: () => false,
  traceFacilityFilterSignature: () => "", catalogEventIdIdentityKey: () => "two-events",
  traceAggregateZoomBucket: () => ({ label: "detail" }), canonicalFilteredTraceAggregationRequested: () => false,
  traceViewportBoundsKey: () => "", TRACE_RENDER_MODE_INDIVIDUAL: "individual", TRACE_RENDER_MODE_AGGREGATE: "aggregate",
  TRACE_RENDER_MODE_SUMMARY: "summary", TRACE_RENDER_MODE_BUDGETED: "budgeted", resolveTraceRenderMode: () => "individual",
  styleRawTraceSegmentsForDensity: segments => segments, traceFacilityFilterStatsSnapshot: () => ({}),
  packedTraceRenderResultIsUsable: () => true, clamp: (v, lo, hi) => Math.min(hi, Math.max(lo, v)),
  PLAYBACK_TRAIL_BUCKET_BY_KEY: new Map([["gap_le_1", bucket]]),
});
vm.runInContext(["applyTraceChronology", "traceChronologyIdentity", "canonicalTraceId", "finiteChronologyNumber",
  "buildCanonicalTraceSegmentsFromPackedEventIndex", "buildLegacyCanonicalTraceSegments", "buildCanonicalPackedTraceRenderSegments",
  "buildPackedTraceFacilityWorkerCandidateSegments", "normalizeStartupProfileTraceSegment"].map(extract).join("\n"), context);
for (const [name, wrapped] of [["buildCanonicalTraceSegmentsFromPackedEventIndex", false], ["buildLegacyCanonicalTraceSegments", false],
  ["buildCanonicalPackedTraceRenderSegments", true], ["buildPackedTraceFacilityWorkerCandidateSegments", true]]) {
  runtime.traceSequenceCacheKey = ""; runtime.packedTraceRenderCacheKey = "";
  const result = context[name](artifact, {});
  const segment = wrapped ? result.segments[0] : result[0];
  assert.equal(segment.traceId, "2->1", `${name} orients actual endpoint IDs`);
  assert.equal(segment.sameDayOrderKnown, true, `${name} preserves accepted time decision`);
}
const previewSegment = context.normalizeStartupProfileTraceSegment({ from_event_id: 1, to_event_id: 2, gap_days: 0,
  from: [47, -122], to: [-18, 31], bucket_key: "gap_le_1" });
assert.equal(previewSegment.traceId, "2->1", "optional startup-profile previews use the same source-time resolver");
assert.equal(previewSegment.sameDayOrderKnown, true);
assert.deepEqual([...previewSegment.from], [-18, 31]);
for (const value of [null, "", "  ", true, false, undefined]) assert.equal(context.finiteChronologyNumber(value), null);
assert.equal(context.finiteChronologyNumber(0), 0, "real epoch zero remains valid");
const playbackReports = [
  { ...reports[0], craft_type_inferred: "disc_saucer" },
  { ...reports[1], craft_type_inferred: "sphere_orb" },
];
const playbackRuntime = { traceChronologyEvidence: index, playbackLayer: {}, playbackTrailLines: [] };
let classifiedPlaybackSegment;
const playbackContext = vm.createContext({ TRACE_CHRONOLOGY: chronology, TRACE_NEIGHBORHOOD: neighborhood, runtime: playbackRuntime,
  CRAFT_TYPE_COLORS: { disc_saucer: "cyan", sphere_orb: "green", unknown: "gray" },
  getCatalogEventById: id => playbackReports.find(event => String(event.event_id) === String(id)),
  traceModeIncludesPlayback: () => true, shortestWrappedSegment: (from, to) => ({ from: [from.lat, from.lon], to: [to.lat, to.lon] }),
  applyTraceFacilityFilterToSegment: segment => {
    classifiedPlaybackSegment = segment;
    assert.equal(segment.fromEventId, 2, "playback facility classifier receives the earlier UTC endpoint");
    assert.deepEqual([...segment.from], [-18, 31], "facility geometry follows the reordered endpoint");
    return { ...segment, facilityTraceClass: "departure", facilityTraceEvidenceClass: "confirmed",
      facilityAccentPlacement: "start", facilityKeys: ["earlier-report-facility"] };
  },
  craftTraceColoringActive: () => true, TRACE_FACILITY_POSSIBLE_TRACE_DASH_ARRAY: "5 3", PLAYBACK_TRAIL_PERSISTENT_LIMIT: 10,
  playbackTrailFadeDuration: () => Infinity, performance: { now: () => 123 },
  renderTraceStatusSummary() {}, syncPlaybackTrailCanvas() {}, syncTraceFacilityDisplayRestriction() {},
});
vm.runInContext(["applyTraceChronology", "canonicalTraceId", "finiteChronologyNumber", "addPlaybackTrail"].map(extract).join("\n"), playbackContext);
playbackContext.addPlaybackTrail(playbackReports[0], playbackReports[1], { ...bucket, color: "white", weight: 2, opacity: 0.8 }, 1);
const playbackEntry = playbackRuntime.playbackTrailLines[0];
assert.equal(playbackEntry.traceId, "2->1");
assert.equal(playbackEntry.fromEventId, 2);
assert.equal(playbackEntry.toEventId, 1);
assert.deepEqual([...playbackEntry.geometry.from], [-18, 31]);
assert.deepEqual([...playbackEntry.geometry.to], [47, -122]);
assert.equal(playbackEntry.facilityTraceClass, "departure");
assert.equal(playbackEntry.segment.facilityAccentPlacement, "start");
assert.equal(playbackEntry.segment.fromCraftColor, "green");
assert.equal(playbackEntry.segment.toCraftColor, "cyan");
assert.deepEqual([...playbackEntry.segment.eventIds], [2, 1]);
assert.equal(playbackEntry.segment.sameDayOrderKnown, true);
assert.equal(playbackEntry.chronology.status, "ordered");
assert.equal(playbackEntry.segment.chronology, classifiedPlaybackSegment.chronology, "canvas and stored entry retain the same timing evidence");
assert.equal(playbackReports[0].event_id, 1, "trail orientation leaves the playback cursor sequence untouched");
console.log("Trace chronology passed: source guards, typed index, UTC ranges and reversal, missing/sentinel/overlap, bounded dates, famous chains, six actual app routes and direction denominator.");

function loaderContext(responseFactory) {
  let requests = 0;
  const runtime = { appConfig: { traceChronologyEvidenceUrl: "./data/timing.json.gz",
    traceChronologyEvidenceGzipSha256: pins.gzipSha256, traceChronologyEvidenceSha256: pins.sha256,
    traceChronologyEvidenceRowCount: pins.rowCount } };
  const context = vm.createContext({ TRACE_CHRONOLOGY: chronology, runtime, URL, document: { baseURI: "https://example.invalid/index.html" },
    APP_SHELL_RELEASE_TOKEN: "reviewed-timing", resolveAssetPath: value => value,
    fetch: async url => { requests++; assert.match(url, /v=reviewed-timing/); return responseFactory(); },
    console: { warn() {} },
  });
  vm.runInContext(["loadTraceChronologyEvidence", "getTraceChronologySnapshot"].map(extract).join("\n"), context);
  return { context, runtime, requests: () => requests };
}
const loader = loaderContext(() => new Response(gzipBytes));
assert.equal((await loader.context.loadTraceChronologyEvidence()).rowCount, input.rows.length);
assert.equal((await loader.context.loadTraceChronologyEvidence()).releaseId, input.releaseId);
assert.equal(loader.requests(), 1, "selections reuse precomputed evidence without repeated fetching or parsing");
assert.equal(loader.context.getTraceChronologySnapshot().status, "ready");
assert.equal(loader.runtime.traceSequenceCacheKey, "", "new evidence clears earlier eligibility cache");
const rejectedLoader = loaderContext(() => new Response("bad gzip"));
assert.equal(await rejectedLoader.context.loadTraceChronologyEvidence(), null);
assert.equal(rejectedLoader.runtime.traceChronologyEvidence, null, "artifact rejection never commits partial time evidence");
assert.equal(rejectedLoader.context.getTraceChronologySnapshot().status, "unavailable");
console.log("Actual app evidence loader passed: gzip integrity, one-time loading and fail-closed unavailable state.");

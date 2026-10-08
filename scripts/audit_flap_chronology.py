"""Read-only full-corpus chronology coverage and all preset-flap drilldowns.

Uses effective shared summaries and the frozen event-clock projection. The
runtime evidence is authoritative for acceptance. Holds reproduce the existing
builder gates and must reconcile with its pinned receipt. Link counts come from
the actual packed runtime constructor, actual same-day craft constructor, and
actual UTC resolver, with no facility or viewport filtering. No corpus or staging
copy is written; only this small JSON report is retained.

Run with the bundled Python containing tzdata 2026.3, and Node.js on PATH.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time
import types

FRONTEND = Path(__file__).resolve().parents[1]
SHARED = Path(r"C:/Users/jarod/Desktop/UFO Timeline map tool")
FROZEN_BUILDER_REF = "617d06130d557f6d6eaf760cd7127155a4db3205"

# The driver evaluates the production constructor and decoder functions, rather
# than replacing the production adjacency model with custom pair enumeration.
RUNTIME_DRIVER = r"""
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const zlib = require('node:zlib'), crypto = require('node:crypto');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const source = input.runtimeSources['app.js'];
function runtimeModule(name) {
  const module = { exports: {} };
  vm.runInNewContext(input.runtimeSources[name], { module, Intl }, { filename: name });
  return module.exports;
}
const chronology = runtimeModule('trace_chronology.js');
const neighborhood = runtimeModule('trace_neighborhood.js');
const directions = runtimeModule('trace_direction_summary.js');
const runtimeManifest = input.evidencePins;
const gzip = fs.readFileSync(input.evidencePath);
const decoded = zlib.gunzipSync(gzip);
const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
if (sha(gzip) !== runtimeManifest.gzipSha256 || sha(decoded) !== runtimeManifest.decodedSha256)
  throw new Error('Runtime evidence release pin mismatch');
// Preserve the complete payload, including source occurrence-date exclusions.
const payload = JSON.parse(decoded);
const evidence = chronology.createEvidenceIndex(payload);
if (evidence.rowCount !== runtimeManifest.rowCount) throw new Error('Runtime evidence row-count mismatch');
const indexRoot = path.join(input.shared, 'data/releases/quality-20261007/map_delta');
const metadata = JSON.parse(fs.readFileSync(path.join(indexRoot, 'trace_event_index_meta.json')));
const binary = fs.readFileSync(path.join(indexRoot, 'trace_event_index.bin'));
if (metadata.struct_format !== '<QddiiIIiI' || metadata.bytes_per_row !== 48 || binary.length !== 48 * metadata.row_count)
  throw new Error('Trace index schema/count drift');
const artifact = { metadata, bytesPerRow: 48, rowCount: metadata.row_count,
  view: new DataView(binary.buffer, binary.byteOffset, binary.length) };
const fields = new Map(metadata.fields.map(f => [f.name, f]));
function extract(name) {
  const start = source.indexOf('  function ' + name + '(');
  if (start < 0) throw new Error('Production function missing: ' + name);
  const next = source.indexOf('\n  function ', start + 4);
  return source.slice(start, next < 0 ? source.length : next).trim();
}
function constant(name, prefix, suffix) {
  const start = source.indexOf('  const ' + name + ' = ' + prefix);
  if (start < 0) throw new Error('Production constant missing: ' + name);
  const valueStart = start + ('  const ' + name + ' = ' + prefix).length;
  const end = source.indexOf(suffix, valueStart);
  return vm.runInNewContext('(' + source.slice(valueStart, end) + ')');
}
const presets = constant('TIMELINE_FLAP_PRESET_BUTTONS', 'Object.freeze(', ');');
const buckets = constant('PLAYBACK_TRAIL_BUCKETS', '', ';');
const craftOnlyLabels = new Set(constant('CRAFT_ONLY_TYPE_LABELS', 'new Set(', ');'));
const records = input.records.map(r => ({ event_id: r[0], sort_date_iso: r[1], date_precision: 'exact_day',
  lat: r[2], lon: r[3], craft_type_inferred: r[4], type: r[5], held_reason: r[6],
  has_coordinates: true, sort_ordinal: Math.floor(Date.parse(r[1] + 'T00:00:00Z') / 86400000) }));
input.records = null;
const byId = new Map(records.map(r => [String(r.event_id), r]));
let selectedIds = new Set();
const runtime = { traceChronologyEvidence: evidence, traceChronologyStatus: 'ready' };
const state = {};
const context = vm.createContext({ TRACE_CHRONOLOGY: chronology, runtime, state,
  PLAYBACK_TRAIL_BUCKETS: buckets,
  activeTraceBuckets: () => buckets,
  filteredMappedEventIdSet: () => selectedIds,
  canonicalTraceSegmentsPackedCacheKey: () => 'audit',
  getCatalogEventById: id => byId.get(String(id)),
  createTraceFacilityClassificationContext: () => ({}),
  applyTraceFacilityFilterToSegmentWithContext: segment => segment,
  normalizeLongitude: value => ((((value + 180) % 360) + 360) % 360) - 180,
  clamp: (value, low, high) => Math.min(high, Math.max(low, value)),
  isoToOrdinal: iso => Math.floor(Date.parse(iso + 'T00:00:00Z') / 86400000),
  decodePackedTraceField: (a, view, name, row) => {
    const field = fields.get(name), offset = row * 48 + field.offset;
    if (field.type === 'uint64') return String(view.getBigUint64(offset, true));
    if (field.type === 'float64') return view.getFloat64(offset, true);
    if (field.type === 'int32') return view.getInt32(offset, true);
    return view.getUint32(offset, true);
  },
});
['sortDateIsoFromPackedKey', 'normalizedPackedTraceSortOrdinalForRender',
 'decodePackedTraceEventIndexRowForRender', 'decodePackedTraceSortOrdinalForRender',
 'packedTraceSortOrdinalLowerBound', 'packedTraceSortOrdinalUpperBound',
 'packedTraceOrdinalScanRange', 'playbackTrailBucketForGapDays', 'shortestLongitudeDelta',
 'shortestWrappedSegment', 'canonicalTraceId', 'applyTraceChronology',
 'buildCanonicalTraceSegmentsFromPackedEventIndex'].forEach(name => vm.runInContext(extract(name), context));
const traceIds = new Set();
for (let row = 0; row < artifact.rowCount; row++)
  traceIds.add(String(artifact.view.getBigUint64(row * 48, true)));
const absent = records.filter(r => !traceIds.has(String(r.event_id)));
function increment(object, key) { object[key] = (object[key] || 0) + 1; }
function summarize(segments) {
  const radar = directions.createDirectionAccumulator();
  const radarLe2 = directions.createDirectionAccumulator();
  const result = { links: segments.length, ordered: 0, ordered_using_two_accepted_clocks: 0,
    ordered_noncoincident: 0, ordered_coincident: 0, ordered_invalid_geometry: 0,
    ordered_using_calendar_fallback: 0, ordered_using_source_calendar_day_bounds: 0,
    reversed_from_stored_endpoint_order: 0,
    unknown_missing_time: 0, unknown_overlapping_intervals: 0, unknown_source_date_excluded: 0,
    unknown_other_reasons: {}, source_date_exclusion_reasons: {}, same_day_links: 0,
    same_day_ordered: 0, zero_length_links: 0, buckets: {}, missing_endpoint_reasons: {},
    missing_endpoint_baseline_gate_reasons: {},
    examples: { ordered: [], unknown_missing: [], unknown_overlap: [], unknown_date_excluded: [], unknown_other: [] } };
  for (const segment of segments) {
    radar.add(segment);
    if (Number.isFinite(segment.gapDays) && segment.gapDays <= 2) radarLe2.add(segment);
    const d = segment.chronology;
    const bucket = segment.bucket ? segment.bucket.key : 'same_day_craft';
    if (!result.buckets[bucket]) result.buckets[bucket] = { links: 0, ordered: 0 };
    result.buckets[bucket].links++;
    if (segment.gapDays === 0) result.same_day_links++;
    const fromGeometry = directions.coordinatePair(segment.from);
    const toGeometry = directions.coordinatePair(segment.to);
    const validGeometry = !!fromGeometry && !!toGeometry;
    const deltaLon = validGeometry ? ((((toGeometry[1] - fromGeometry[1] + 180) % 360) + 360) % 360) - 180 : null;
    const coincident = validGeometry && Math.abs(fromGeometry[0] - toGeometry[0]) < 1e-12 &&
      (Math.abs(deltaLon) < 1e-12 || Math.abs(Math.abs(fromGeometry[0]) - 90) < 1e-12);
    if (coincident) result.zero_length_links++;
    let exampleKind;
    if (d.status === 'ordered') {
      result.ordered++; result.buckets[bucket].ordered++;
      if (!validGeometry) result.ordered_invalid_geometry++;
      else if (coincident) result.ordered_coincident++;
      else result.ordered_noncoincident++;
      if (segment.gapDays === 0) result.same_day_ordered++;
      if (d.reversed) result.reversed_from_stored_endpoint_order++;
      if (d.from.evidence.kind === 'date_only' || d.to.evidence.kind === 'date_only') result.ordered_using_calendar_fallback++;
      else if (d.from.evidence.kind.includes('calendar_day') || d.to.evidence.kind.includes('calendar_day')) result.ordered_using_source_calendar_day_bounds++;
      else result.ordered_using_two_accepted_clocks++;
      exampleKind = 'ordered';
    } else if (d.reason === 'missing_source_backed_time') {
      result.unknown_missing_time++;
      for (const id of [segment.fromEventId, segment.toEventId]) {
        if (!evidence.interval(id)) {
          const baselineReason = byId.get(String(id)).held_reason;
          increment(result.missing_endpoint_baseline_gate_reasons, baselineReason);
          increment(result.missing_endpoint_reasons, input.baselineGateReasonsApply ? baselineReason : 'no_accepted_interval_in_comparison_index');
        }
      }
      exampleKind = 'unknown_missing';
    } else if (d.reason === 'overlapping_utc_intervals') {
      result.unknown_overlapping_intervals++; exampleKind = 'unknown_overlap';
    } else if (d.reason === 'source_occurrence_date_excluded') {
      result.unknown_source_date_excluded++; exampleKind = 'unknown_date_excluded';
      for (const id of [segment.fromEventId, segment.toEventId]) {
        const exclusion = typeof evidence.exclusion === 'function' ? evidence.exclusion(id) : null;
        if (exclusion) increment(result.source_date_exclusion_reasons, exclusion.reason);
      }
    } else {
      increment(result.unknown_other_reasons, d.reason || 'unknown_reason'); exampleKind = 'unknown_other';
    }
    if (result.examples[exampleKind].length < 2) result.examples[exampleKind].push({
      fromEventId: segment.fromEventId, toEventId: segment.toEventId,
      gapDays: segment.gapDays, reason: d.reason,
    });
  }
  const radarSummary = radar.finish();
  const radarLe2Summary = radarLe2.finish();
  result.radar_relevant_denominator = radarSummary.denominator;
  result.radar_ordered_links = radarSummary.orderedSegments;
  result.radar_unknown_order_links = radarSummary.unorderedSegments;
  result.radar_geometry_exclusions = radarSummary.excludedCounts;
  result.radar_duplicates_ignored = radarSummary.duplicatesIgnored;
  result.radar_sector_counts = Object.fromEntries(radarSummary.sectors.map(sector => [sector.key, sector.count]));
  result.radar_gap_le_2_denominator = radarLe2Summary.denominator;
  result.radar_gap_le_2_ordered_links = radarLe2Summary.orderedSegments;
  result.radar_gap_le_2_unknown_order_links = radarLe2Summary.unorderedSegments;
  result.radar_gap_le_2_geometry_exclusions = radarLe2Summary.excludedCounts;
  result.radar_gap_le_2_sector_counts = Object.fromEntries(radarLe2Summary.sectors.map(sector => [sector.key, sector.count]));
  if (result.ordered !== result.ordered_noncoincident + result.ordered_coincident + result.ordered_invalid_geometry)
    throw new Error('Ordered geometry counts do not reconcile');
  if (result.links !== result.ordered + result.unknown_missing_time + result.unknown_overlapping_intervals +
      result.unknown_source_date_excluded + Object.values(result.unknown_other_reasons).reduce((total, count) => total + count, 0))
    throw new Error('Chronology decision-reason counts do not reconcile');
  result.ordered_percent = result.links ? Math.round(10000 * result.ordered / result.links) / 100 : null;
  return result;
}
function packed(selected, preset) {
  selectedIds = new Set(selected.map(r => String(r.event_id)));
  state.timeRangeStartOrdinal = preset ? Math.floor(Date.parse(preset.startIso + 'T00:00:00Z') / 86400000) : null;
  state.timeRangeEndOrdinal = preset ? Math.floor(Date.parse(preset.endIso + 'T00:00:00Z') / 86400000) : null;
  // Null bounds are Number(null)=0 in production, so full-corpus audit uses
  // explicit effective date extrema rather than pretending null is unbounded.
  if (!preset) {
    state.timeRangeStartOrdinal = selected.reduce((v, r) => Math.min(v, r.sort_ordinal), Infinity);
    state.timeRangeEndOrdinal = selected.reduce((v, r) => Math.max(v, r.sort_ordinal), -Infinity);
  }
  runtime.traceSequenceCacheKey = ''; runtime.traceSequenceCacheValue = null;
  const result = summarize(context.buildCanonicalTraceSegmentsFromPackedEventIndex(artifact));
  runtime.traceSequenceCacheValue = null;
  if (global.gc) global.gc();
  return result;
}
function auditScope(selected, preset) {
  const crafts = selected.filter(r => craftOnlyLabels.has(String(r.type || '').trim().toLowerCase()));
  const kinds = {}, acceptedCounts = { accepted_interval_rows: 0, accepted_source_clock_rows: 0,
    accepted_source_calendar_day_bound_rows: 0 };
  for (const record of selected) {
    const interval = evidence.interval(record.event_id);
    if (!interval) continue;
    acceptedCounts.accepted_interval_rows++;
    increment(kinds, interval.evidence.kind);
    if (interval.evidence.kind.includes('calendar_day')) acceptedCounts.accepted_source_calendar_day_bound_rows++;
    else acceptedCounts.accepted_source_clock_rows++;
  }
  const scope = { mapped_exact_day_rows: selected.length, craft_only_mapped_exact_day_rows: crafts.length,
    ...acceptedCounts, accepted_interval_kind_counts: kinds,
    ordinary_packed_all_types: packed(selected, preset), ordinary_packed_craft_only: packed(crafts, preset),
    famous_same_day_craft_all_types: summarize(neighborhood.buildSameDayCraftTraceSegments(selected,
      { chronology: evidence, timingSupport: chronology })),
    famous_same_day_craft_craft_only: summarize(neighborhood.buildSameDayCraftTraceSegments(crafts,
      { chronology: evidence, timingSupport: chronology })) };
  if (global.gc) global.gc();
  return scope;
}
const result = { evidence_snapshot: evidence.snapshot(),
  source_date_exclusions: { records: (payload.excludedDates || []).length,
    reasons: (payload.excludedDates || []).reduce((counts, exclusion) => { increment(counts, exclusion.reason); return counts; }, {}),
    payload_preserved_without_row_only_cloning: true },
  same_day_chain_ranking: input.runtimeSources['trace_neighborhood.js'].includes('interval.evidence.kind !== "source_calendar_day_zone_bound"')
    ? 'Actual source-clock intervals use UTC midpoint ranking; date-only accepted calendar bounds remain in the unknown-clock ID lane, without an invented clock midpoint.'
    : 'Accepted UTC intervals use midpoint ranking followed by unknown-clock ID ranking (original deployed constructor).',
  packed_inventory: { rows: artifact.rowCount, mapped_exact_day_absent_rows: absent.length,
    absent_records_reason: absent.every(r => r.sort_date_iso.startsWith('0000-'))
      ? 'Year-zero placeholder dates excluded by the canonical packed trace inventory'
      : 'See named absent records; no valid record disappearance is inferred',
    absent_records: absent.map(r => ({ eventId: r.event_id, date: r.sort_date_iso,
      lat: r.lat, lon: r.lon, craftType: r.craft_type_inferred, type: r.type, baselineHeldReason: r.held_reason })) },
  whole_corpus: auditScope(records, null), flaps: [] };
for (const preset of presets) {
  const selected = records.filter(r => preset.startIso <= r.sort_date_iso && r.sort_date_iso <= preset.endIso);
  result.flaps.push({ id: preset.id, ...auditScope(selected, preset) });
}
console.log(JSON.stringify(result));
"""


def load_builder(frontend, shared, ref):
    # Read the immutable Git blob in memory, so concurrent gate improvements
    # cannot silently change this pre-change baseline or its blocker histogram.
    blob = subprocess.run(["git", "show", ref + ":scripts/build_trace_chronology_evidence.py"],
                          cwd=frontend, capture_output=True, check=True).stdout
    module = types.ModuleType("audit_frozen_chronology_builder")
    module.__file__ = str(frontend / "scripts/build_trace_chronology_evidence.py")
    exec(compile(blob, module.__file__, "exec"), module.__dict__)
    module.SHARED = shared
    module.REPAIRS = shared / "data/research/analysis-repairs-20261007"
    return module, {"gitRef": ref, "gitPath": "scripts/build_trace_chronology_evidence.py",
                    "bytes": len(blob), "sha256": hashlib.sha256(blob).hexdigest(),
                    "role": "immutable_baseline_gate_classifier"}


def presets_from_app(text):
    match = re.search(r"const TIMELINE_FLAP_PRESET_BUTTONS = Object\.freeze\(\[([\s\S]*?)\]\);", text)
    if not match:
        raise ValueError("Flap presets not found")
    entries = []
    for raw in re.findall(r"\{[^{}]+\}", match[1]):
        values = dict(re.findall(r'(\w+):\s*"([^"]*)"', raw))
        if not all(key in values for key in ("id", "name", "startIso", "endIso")):
            raise ValueError("Unexpected flap preset shape")
        entries.append(values)
    return entries


def counter_json(value):
    return dict(sorted(value.items(), key=lambda entry: (-entry[1], entry[0])))


def scope_metrics():
    return {"counts": Counter(), "clock_status": Counter(), "held_reasons": Counter(),
            "mapped_exact_day_held_reasons": Counter(), "mapped_exact_day_exact_clock_held_reasons": Counter(),
            "sources": defaultdict(Counter), "blocker_details": defaultdict(Counter), "examples": defaultdict(list)}


def serialize_scope(scope):
    return {key: (dict(value) if key == "examples" else
                  {name: counter_json(counter) for name, counter in sorted(value.items())}
                  if key in {"sources", "blocker_details"} else counter_json(value))
            for key, value in scope.items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shared-root", type=Path, default=SHARED)
    parser.add_argument("--frontend-root", type=Path, default=FRONTEND)
    parser.add_argument("--output", type=Path, default=FRONTEND / "docs/qa/flap-chronology-20261008/baseline.json")
    parser.add_argument("--node", default="node")
    parser.add_argument("--gate-builder-ref", default=FROZEN_BUILDER_REF)
    parser.add_argument("--runtime-ref", default=FROZEN_BUILDER_REF,
                        help="Baseline runtime Git ref. Use working-tree only for a deliberate current-runtime audit.")
    parser.add_argument("--comparison-evidence", type=Path,
                        help="Optional new sparse evidence.json.gz to compare without modifying runtime assets.")
    parser.add_argument("--comparison-audit", type=Path,
                        help="Required with comparison evidence: its matching evidence_build_audit.json.")
    parser.add_argument("--comparison-runtime-ref", default="working-tree")
    args = parser.parse_args()
    started = time.monotonic()
    frontend, shared = args.frontend_root.resolve(), args.shared_root.resolve()
    builder, builder_pin = load_builder(frontend, shared, args.gate_builder_ref)
    aliases, single, tz_meta = builder.country_zone_rules()
    research = shared / "data/research/trace-chronology-20261008"
    previous = builder.load(research / "evidence_build_audit.json")
    expected_builder_pin = next(pin for pin in previous["inputs"] if pin["role"] == "reproducible_sparse_evidence_builder")
    if builder_pin["sha256"] != expected_builder_pin["sha256"]:
        raise ValueError("Immutable baseline builder differs from frozen build receipt")
    if tz_meta != previous["timezoneDatabase"]:
        raise ValueError("Current timezone/reference inputs differ from frozen build")
    def runtime_sources(ref):
        sources, source_pins = {}, []
        for name in ("app.js", "trace_chronology.js", "trace_neighborhood.js", "trace_direction_summary.js"):
            raw = (frontend / name).read_bytes() if ref == "working-tree" else subprocess.run(
                ["git", "show", ref + ":" + name], cwd=frontend, capture_output=True, check=True).stdout
            sources[name] = raw.decode("utf-8")
            source_pins.append({"gitRef": ref, "gitPath": name, "bytes": len(raw),
                                "sha256": hashlib.sha256(raw).hexdigest(), "role": "actual_production_runtime_code"})
        return sources, source_pins

    baseline_sources, runtime_source_pins = runtime_sources(args.runtime_ref)
    comparison_prepared = None
    if args.comparison_evidence or args.comparison_audit:
        if not args.comparison_evidence or not args.comparison_audit:
            raise ValueError("Comparison evidence and audit must both be supplied")
        comparison_audit = builder.load(args.comparison_audit)
        # Snapshot current code before any source scan or baseline evaluation.
        new_sources, new_source_pins = runtime_sources(args.comparison_runtime_ref)
        new_pins = {"gzipSha256": comparison_audit["evidence"]["sha256"],
                    "decodedSha256": comparison_audit["evidence"]["decodedSha256"],
                    "rowCount": comparison_audit["evidence"]["rowCount"]}
        comparison_prepared = (comparison_audit, new_sources, new_source_pins, new_pins)
    runtime_manifest = {"gzipSha256": previous["evidence"]["sha256"],
                        "decodedSha256": previous["evidence"]["decodedSha256"],
                        "rowCount": previous["evidence"]["rowCount"]}
    runtime_evidence_path = research / "evidence.json.gz"
    if builder.sha(runtime_evidence_path) != runtime_manifest["gzipSha256"]:
        raise ValueError("Frozen runtime evidence hash mismatch")
    evidence = builder.load(runtime_evidence_path)
    accepted = {row[0]: evidence["codes"]["evidence"][row[3]]["kind"] for row in evidence["rows"]}
    pins = [builder_pin, *runtime_source_pins]

    def pin(path, role):
        pins.append({"path": str(path.resolve()), "bytes": path.stat().st_size,
                     "sha256": builder.sha(path), "role": role})

    for path, role in [(Path(__file__), "read_only_audit_script"),
                       (research / "evidence_build_audit.json", "frozen_baseline_receipt"),
                       (runtime_evidence_path, "accepted_runtime_intervals")]:
        pin(path, role)
    repairs = shared / "data/research/analysis-repairs-20261007"
    attribute = repairs / "attributes/analysis_time_of_day_v1"
    clock_manifest_path = attribute / "manifest.json"
    dictionary_path = attribute / "time_of_day_value_dictionary_v1.json.gz"
    clock_manifest, dictionary = builder.load(clock_manifest_path), builder.load(dictionary_path)
    pin(clock_manifest_path, "typed_clock_manifest")
    pin(dictionary_path, "typed_source_clock_dictionary")
    projected = {}
    for name in clock_manifest["artifactGroups"]["timeProjectionShards"]:
        artifact = clock_manifest["artifacts"][name]
        path = shared / "data/releases/quality-20261007/analysis_delta/analysis_time_of_day_v1" / Path(artifact["gzipFile"]).name
        pin(path, "shared_event_clock_projection")
        if pins[-1]["sha256"] != artifact["gzipSha256"]:
            raise ValueError("Projection pin mismatch")
        for _, event_id, code, _ in builder.load(path):
            if event_id in projected:
                raise ValueError("Duplicate clock projection event")
            projected[event_id] = code
    presets = presets_from_app(baseline_sources["app.js"])
    whole = scope_metrics()
    scopes = {preset["id"]: scope_metrics() for preset in presets}
    mapped_records = []
    manifest_path = repairs / "source-quality/catalog/summary_manifest.json"
    pin(manifest_path, "effective_summary_manifest")

    def classify(event, status, value):
        event_id = event["event_id"]
        if event.get("date_precision") != "exact_day" or event.get("exact_day_eligible") is False:
            return "held_partial_or_uncertain_date", ""
        if event_id in accepted:
            return "accepted_utc_interval", accepted[event_id]
        if value is None:
            return "held_no_source_clock", ""
        if status != "exact_clock":
            return "held_" + status, ""
        if value[2] != event.get("time_raw"):
            raise ValueError("Source clock raw/projection mismatch")
        clock = builder.source_clock(value[2], value[5])
        if clock is None:
            return "held_unsupported_exact_clock_syntax", ""
        zone, zone_reason = builder.strict_zone(event, aliases, single)
        start, end, token = clock
        if token:
            (interval, reason), _ = builder.explicit_utc_interval(event.get("sort_date_iso"), start, end, token, zone)
        elif zone:
            if not builder.historical_jurisdiction_supported(event, zone):
                return "held_historical_locality_timezone_uncertainty", zone
            interval, reason = builder.utc_interval(event.get("sort_date_iso"), start, end, zone)
        else:
            return "held_" + zone_reason, ""
        if interval is not None:
            raise ValueError("Gate classifier would accept an event absent from frozen runtime: " + str(event_id))
        return "held_" + reason, ""

    def accumulate(scope, event, status, held, detail):
        c = scope["counts"]
        c["catalog_rows"] += 1
        mapped = bool(event.get("has_coordinates"))
        exact_day = event.get("date_precision") == "exact_day" and event.get("exact_day_eligible") is not False
        exact_clock = status == "exact_clock"
        source = scope["sources"][event.get("source", "unknown")]
        source["catalog_rows"] += 1
        scope["clock_status"][status] += 1
        if mapped: c["mapped_rows"] += 1
        if exact_day: c["exact_day_rows"] += 1
        if exact_clock: c["structured_exact_clock_rows"] += 1
        if mapped and exact_day:
            c["mapped_exact_day_rows"] += 1
            source["mapped_exact_day_rows"] += 1
            if exact_clock:
                c["mapped_exact_day_structured_exact_clock_rows"] += 1
                source["mapped_exact_day_structured_exact_clock_rows"] += 1
        if held == "accepted_utc_interval":
            c["accepted_utc_rows"] += 1
            c["accepted_" + detail + "_rows"] += 1
            source["accepted_utc_rows"] += 1
            if mapped and exact_day:
                c["mapped_exact_day_accepted_utc_rows"] += 1
                source["mapped_exact_day_accepted_utc_rows"] += 1
            return
        scope["held_reasons"][held] += 1
        if mapped and exact_day:
            scope["mapped_exact_day_held_reasons"][held] += 1
            source["mapped_exact_day_" + held] += 1
            if exact_clock:
                scope["mapped_exact_day_exact_clock_held_reasons"][held] += 1
                source["mapped_exact_day_exact_clock_" + held] += 1
        parts = [builder.normalized(part) for part in str(event.get("location_raw") or "").split(",") if builder.normalized(part)]
        if len(parts) >= 3 and parts[-1] in builder.CONTINENTS and parts[-2] in aliases:
            parts.pop()
        suffix = parts[-1] if parts else "EMPTY"
        if held == "held_historical_locality_timezone_uncertainty":
            scope["blocker_details"][held]["pre1900" if event.get("sort_date_iso", "") < "1900-01-01" else "pre1970_nonrepresentative_locality"] += 1
            scope["blocker_details"][held + "_zones"][detail] += 1
        elif held in {"held_multi_zone_or_unknown_country", "held_split_or_missing_us_state", "held_jurisdiction_coordinate_mismatch", "held_low_location_precision"}:
            scope["blocker_details"][held + "_suffix"][suffix] += 1
            if held == "held_multi_zone_or_unknown_country":
                category = "known_multizone_country" if suffix in aliases else "unrecognized_country_alias_or_no_country_suffix"
                scope["blocker_details"][held][category] += 1
        if mapped and exact_day and len(scope["examples"][held]) < 3:
            scope["examples"][held].append({key: event.get(key) for key in
                ("event_id", "source", "sort_date_iso", "time_raw", "location_raw", "location_precision", "chunk_id", "detail_index")})

    for entry in builder.load(manifest_path):
        path = repairs / "source-quality/catalog/summary_shards" / (entry["file"] + ".gz")
        if not path.exists(): path = repairs / "catalog/summary_shards" / (entry["file"] + ".gz")
        pin(path, "effective_shared_summary_shard")
        for event in builder.load(path):
            code = projected.get(event["event_id"])
            value = dictionary[code] if code is not None else None
            status = clock_manifest["codes"]["status"][value[3]] if value else "no_structured_clock"
            held, detail = classify(event, status, value)
            accumulate(whole, event, status, held, detail)
            day = event.get("sort_date_iso") or ""
            for preset in presets:
                if preset["startIso"] <= day <= preset["endIso"]:
                    accumulate(scopes[preset["id"]], event, status, held, detail)
            if event.get("has_coordinates") and event.get("date_precision") == "exact_day":
                mapped_records.append([event["event_id"], day, event.get("lat"), event.get("lon"),
                                       event.get("craft_type_inferred"), event.get("type"), held])
    if whole["counts"]["catalog_rows"] != previous["sourceRowsPreserved"]:
        raise ValueError("Corpus count differs from frozen baseline")
    expected_holds = {key: value for key, value in previous["counts"].items() if key.startswith("held_")}
    if dict(whole["held_reasons"]) != expected_holds:
        raise ValueError("Hold classifications differ from frozen evidence-build receipt")
    if whole["counts"]["accepted_utc_rows"] != runtime_manifest["rowCount"]:
        raise ValueError("Accepted count differs from runtime")
    for name in ("trace_event_index.bin", "trace_event_index_meta.json"):
        pin(shared / "data/releases/quality-20261007/map_delta" / name, "unchanged_packed_trace_inventory")
    def evaluate_runtime(evidence_path, evidence_pins, sources, baseline_gate_reasons_apply):
        runtime_input = json.dumps({"frontend": str(frontend), "shared": str(shared), "records": mapped_records,
                                    "evidencePath": str(evidence_path.resolve()), "evidencePins": evidence_pins,
                                    "runtimeSources": sources,
                                    "baselineGateReasonsApply": baseline_gate_reasons_apply}, separators=(",", ":"))
        process = subprocess.run([args.node, "--expose-gc", "--max-old-space-size=3072", "-e", RUNTIME_DRIVER],
                                 input=runtime_input, capture_output=True, text=True, encoding="utf-8")
        if process.returncode:
            raise RuntimeError("Actual runtime constructor audit failed:\n" + process.stderr)
        return json.loads(process.stdout)

    print("Source scan reconciled; evaluating frozen actual runtime constructors.", flush=True)
    runtime_result = evaluate_runtime(runtime_evidence_path, runtime_manifest, baseline_sources, True)
    comparison = None
    if comparison_prepared is not None:
        comparison_audit, new_sources, new_source_pins, new_pins = comparison_prepared
        pin(args.comparison_evidence, "new_sparse_evidence_for_comparison")
        pin(args.comparison_audit, "matching_new_evidence_build_receipt")
        comparison = {"runtimeCode": new_source_pins, "evidenceBuildCounts": comparison_audit["counts"],
                      "sourceGateHoldCounters": {key: value for key, value in comparison_audit["counts"].items() if key.startswith("held_")},
                      "sourceGateHoldCounterScope": "Read directly from the matching hash-pinned comparison build receipt. Precision holds may coexist with wider accepted bounds; these are gate counters, not counts of records absent from the final index.",
                      "sourceAcceptanceBySource": comparison_audit.get("sources", {}),
                      "baselineSourceHoldReasonsRemainBaselineOnly": True,
                      **evaluate_runtime(args.comparison_evidence, new_pins, new_sources, False)}
    result = {"schemaId": "full-corpus-and-flap-chronology-audit-v1",
              "generatedUtc": datetime.now(timezone.utc).isoformat(),
              "scope": {"all_preserved_catalog_rows": True, "flap_windows_are_global_calendar_windows": True,
                        "flap_labels_do_not_imply_country_filtering": True,
                        "ordinary_links": "Production packed constructor: filter effective mapped exact-day rows, then adjacent visible rows in unchanged stored playback order; all gap buckets; facility and viewport restrictions absent.",
                        "same_day_craft_links": "Production same-day craft constructor: recognized same-day same-craft records and distinct-location links; baseline and comparison ranking contracts are recorded separately. This is the famous-case constructor, not a claim that flap selection activates that mode.",
                        "scope_limit": "Counts are reproducible baseline selections, not every possible user filter or evidence of a craft flight path."},
              "inputs": pins, "timezoneDatabase": tz_meta,
              "reconciliation": {"hold_histogram_matches_frozen_builder": True, "catalog_count_matches": True,
                                 "accepted_count_matches_hash_pinned_runtime": True},
              "whole_corpus": {**serialize_scope(whole), "runtime_adjacency": runtime_result["whole_corpus"]},
              "flaps": [{**preset, **serialize_scope(scopes[preset["id"]]),
                         "runtime_adjacency": next(row for row in runtime_result["flaps"] if row["id"] == preset["id"])}
                        for preset in presets],
              "runtime_evidence_snapshot": runtime_result["evidence_snapshot"],
              "baseline_source_date_exclusions": runtime_result["source_date_exclusions"],
              "baseline_same_day_chain_ranking": runtime_result["same_day_chain_ranking"],
              "packed_inventory": runtime_result["packed_inventory"],
              "elapsedSeconds": round(time.monotonic() - started, 3),
              "storageLifecycle": {"canonicalArtifact": str(args.output.resolve()),
                                   "rollback": "Existing frozen trace-chronology-20261008 evidence/release remains unchanged.",
                                   "newCorpusOrRuntimeCopies": False, "newFilesOver100MiB": [],
                                   "retention": "Retain this small reproducible audit with frontend code. No staging or backup directory is created.",
                                   "approximateNetDiskGrowthBytes": Path(__file__).stat().st_size,
                                   "supersededArtifacts": [], "cleanupProposal": "No new generated artifact needs cleanup; no dataset deletion authorized."}}
    if comparison is not None:
        result["comparison"] = comparison
    retained_v2_path = args.output.parent / "v2-comparison.json"
    if retained_v2_path.exists():
        result["storageLifecycle"]["retainedPriorAudit"] = {
            "path": str(retained_v2_path.resolve()), "bytes": retained_v2_path.stat().st_size,
            "sha256": builder.sha(retained_v2_path),
            "purpose": "Unique v2 before/after audit preserved after later raw source timezone/date flags required scientific corrections. Superseded counts are not the final release result.",
            "provenance": "Original v2 report retains its input hashes and working-code snapshot hashes; renamed without changing bytes.",
            "rebuildMethod": "Replay the v2 input/code snapshots if retained. When a snapshot is superseded, this preserved JSON remains the unique audit receipt and does not claim an exact rebuild from newer inputs.",
            "retentionDecision": "Retain this small correction-provenance receipt with final audit; no corpus or staging copy."}
        result["storageLifecycle"]["approximateNetDiskGrowthBytes"] += retained_v2_path.stat().st_size
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Include the report itself in the approximate lifecycle estimate.
    result["storageLifecycle"]["approximateNetDiskGrowthBytes"] += len(json.dumps(result, ensure_ascii=True, indent=2).encode("utf-8")) + 1
    args.output.write_text(json.dumps(result, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output.resolve()), "bytes": args.output.stat().st_size,
                      "elapsedSeconds": result["elapsedSeconds"], "counts": result["whole_corpus"]["counts"],
                      "runtime_adjacency": {key: {metric: value for metric, value in audit.items() if metric in {"links", "ordered", "ordered_percent"}}
                                            for key, audit in runtime_result["whole_corpus"].items() if isinstance(audit, dict)}}, indent=2))


if __name__ == "__main__":
    main()

"""Derive the small initial map view from the pinned effective catalog in place.

No canonical dataset, full static bundle, or historical release is copied. The
only outputs are one compressed scoped view and its provenance/pin manifest.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import struct

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "data/startup_profiles/france_1954_flap"
SCHEMA = "ufo-progressive-startup-view-v1"
START, END = "1954-09-01", "1954-11-30"
EXPECTED_CORPUS = 702893
MAX_GZIP_BYTES = 1024 * 1024
SHARED_TRACE = Path("C:/Users/jarod/Desktop/UFO Timeline map tool/data/releases/quality-20261007/map_delta/trace_event_index.bin.gz")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    raw = Path(path).read_bytes()
    return json.loads(gzip.decompress(raw) if str(path).endswith(".gz") else raw)


def pin(path, role):
    raw = Path(path).read_bytes()
    return {"path": Path(path).resolve().relative_to(ROOT).as_posix(), "bytes": len(raw), "sha256": sha(raw), "role": role}


def in_window(row):
    if not row.get("has_coordinates"):
        return False
    lat, lon = row.get("lat"), row.get("lon")
    if not isinstance(lat, (float, int)) or not isinstance(lon, (float, int)):
        return False
    if not -90 <= lat <= 90 or not -180 <= lon <= 180:
        return False
    if row.get("date_recovery_contract"):
        first, last = row.get("date_iso"), row.get("end_date_iso")
    else:
        first = last = row.get("sort_date_iso")
    return isinstance(first, str) and isinstance(last, str) and first <= END and last >= START


def subset_timing(payload, ids):
    result = dict(payload)
    selected = [row for row in payload["rows"] if str(row[0]) in ids]
    evidence_ids = sorted({row[3] for row in selected})
    zone_ids = sorted({row[4] for row in selected})
    evidence_codes = {value: index for index, value in enumerate(evidence_ids)}
    zone_codes = {value: index for index, value in enumerate(zone_ids)}
    result["rows"] = [[*row[:3], evidence_codes[row[3]], zone_codes[row[4]]] for row in selected]
    result["codes"] = {"evidence": [payload["codes"]["evidence"][index] for index in evidence_ids],
                       "zone": [payload["codes"]["zone"][index] for index in zone_ids]}
    result["excludedDates"] = [row for row in payload.get("excludedDates", []) if str(row["eventId"]) in ids]
    result["scope"] = "mapped_reports_in_initial_time_window"
    result["globalRowCount"] = len(payload["rows"])
    return result


DECORATE = r'''
const fs = require("node:fs"), zlib = require("node:zlib"), path = require("node:path"), vm = require("node:vm");
const root = process.argv[1], input = JSON.parse(fs.readFileSync(0, "utf8"));
const app = fs.readFileSync(path.join(root, "app.js"), "utf8");
function appConstant(name) {
  const begin = app.indexOf("  const " + name + " = ");
  const end = app.indexOf("\n  ", begin + 3);
  // These reviewed declarations are deliberately evaluated from current source,
  // so a later rule change cannot silently drift from this derived view.
  const declarationEnd = app.indexOf(";", begin) + 1;
  if (begin < 0 || declarationEnd < begin) throw new Error("Actual app constant absent: " + name);
  return vm.runInNewContext(app.slice(begin, declarationEnd) + "\nArray.from(" + name + ")");
}
const read = name => JSON.parse(zlib.gunzipSync(fs.readFileSync(path.join(root, name))));
const encounters = require(path.join(root, "encounter_evidence.js"));
const manifest = JSON.parse(fs.readFileSync(path.join(root, "data/encounters/manifest.json"), "utf8"));
const index = encounters.createIndex(read("data/encounters/" + manifest.artifact.file), manifest.attributeReviews, manifest.artifact.decodedSha256);
const origins = encounters.createLabelOriginsIndex(read("data/encounters/" + manifest.labelOrigins.file), index, manifest.artifact.decodedSha256);
const chronology = require(path.join(root, "trace_chronology.js")).createEvidenceIndex(input.traceChronology);
const labels = read("data/location_label_overlay.json.gz");
const patches = new Map(labels.labels.map(row => [String(row[0]), { location_display: row[1] }]));
const allowed = new Set(appConstant("LOCATION_LABEL_OVERLAY_SUMMARY_FIELDS"));
for (const [id, patch] of labels.reviewed) {
  const selected = Object.fromEntries(Object.entries(patch).filter(([key]) => allowed.has(key)));
  patches.set(String(id), Object.assign({}, patches.get(String(id)), selected));
}
const quality = read("data/quality_detail_patches.json.gz");
const qualityIds = new Set(quality.patches.map(row => String(row.eventId)));
const events = input.events.map(row => {
  const event = row.quality_view_changes || qualityIds.has(String(row.event_id)) ? { ...row } : Object.assign({}, row, patches.get(String(row.event_id)));
  encounters.decorateInPlace(event, index, origins);
  if (event.encounterIdentityMismatch) throw new Error("Scoped encounter source identity mismatch");
  event.encounterOccurrenceDateExcluded = Boolean(chronology.exclusion(event.event_id));
  return event;
});
const craftTypes = appConstant("CRAFT_ONLY_TYPE_LABELS");
const defaultRows = events.filter(row => row.date_precision === "exact_day" && craftTypes.includes(String(row.type || "").trim().toLowerCase()));
const defaultIds = new Set(defaultRows.map(row => String(row.event_id)));
const traceRows = input.traceEventRows.filter(row => defaultIds.has(String(row[0])));
const traceApi = require(path.join(root, "trace_chronology.js"));
const directionApi = require(path.join(root, "trace_direction_summary.js"));
const traces = [];
for (let i = 1; i < traceRows.length; i++) {
  const a = traceRows[i - 1], b = traceRows[i], gap = Math.abs(b[3] - a[3]);
  if (gap > 2) continue;
  traces.push(traceApi.orientSegment(chronology, { traceId: a[0] + "->" + b[0], fromEventId: a[0], toEventId: b[0],
    from: [a[1], a[2]], to: [b[1], b[2]], fromSortOrdinal: a[3], toSortOrdinal: b[3], gapDays: gap,
    bucket: { key: gap <= 1 ? "gap_le_1" : "gap_le_2" } }));
}
const traceParity = { defaultTraceEvents: traceRows.length, segments: traces.length,
  endpointsSha256: require("node:crypto").createHash("sha256").update(JSON.stringify(traces.map(t => [t.fromEventId, t.toEventId, t.gapDays, t.chronology.status]))).digest("hex"),
  directions: directionApi.summarizeDirections(traces) };
process.stdout.write(JSON.stringify({ events, defaultFilteredCount: defaultRows.length,
  timingSnapshot: chronology.snapshot(), craftOnlyTypes: craftTypes, traceParity }));
'''


def build(plan_path, output, node):
    plan = read_json(plan_path)
    shards = sorted((row for row in plan["uploads"] if "/summary_shards/summary_" in row["key"] and row["key"].endswith(".json.gz")), key=lambda row: row["key"])
    require(len(shards) == 71 and plan["counts"]["events"] == EXPECTED_CORPUS, "The complete current effective catalog is required")
    events, summary_pins = [], []
    values = {"sources": set(), "types": set(), "precisions": set()}
    rows_read = 0
    for row in shards:
        raw = Path(row["source"]).read_bytes()
        require(len(raw) == row["bytes"] and sha(raw) == row["sha256"], "Effective summary pin mismatch: " + row["key"])
        rows = json.loads(gzip.decompress(raw))
        rows_read += len(rows)
        for event in rows:
            values["sources"].add(event.get("source") or "")
            values["types"].add(event.get("type") or "")
            values["precisions"].add(event.get("location_precision") or "unknown")
            if in_window(event):
                events.append(event)
        summary_pins.append({key: row[key] for key in ("key", "bytes", "sha256")})
    require(rows_read == EXPECTED_CORPUS, "Effective catalog row count drift")
    ids = {str(event["event_id"]) for event in events}
    require(len(ids) == len(events), "Scoped catalog contains duplicate source IDs")
    timing_path = ROOT / "data/trace_chronology/evidence.json.gz"
    timing_manifest = read_json(ROOT / "data/trace_chronology/manifest.json")
    timing_gzip = timing_path.read_bytes()
    timing_raw = gzip.decompress(timing_gzip)
    require(sha(timing_gzip) == timing_manifest["gzipSha256"] and sha(timing_raw) == timing_manifest["decodedSha256"], "Global timing source pin drift")
    timing = subset_timing(json.loads(timing_raw), ids)
    old_release = read_json(ROOT / "reproduction/quality_release.json")
    trace_pin = next(row for row in old_release["runtime_objects"] if row["url"].endswith("map_delta/trace_event_index.bin.gz"))
    trace_gzip = SHARED_TRACE.read_bytes()
    require(len(trace_gzip) == trace_pin["bytes"] and sha(trace_gzip) == trace_pin["sha256"], "Canonical packed trace inventory pin drift")
    trace_raw = gzip.decompress(trace_gzip)
    record = struct.Struct("<QddiiIIiI")
    require(len(trace_raw) == 577004 * record.size, "Canonical packed trace row inventory drift")
    trace_rows = [list(row[:5]) for row in record.iter_unpack(trace_raw) if str(row[0]) in ids]
    decorated = subprocess.run([node, "-e", DECORATE, str(ROOT)], input=json.dumps({"events": events, "traceChronology": timing, "traceEventRows": trace_rows}), text=True, encoding="utf-8", capture_output=True, check=True)
    derived = json.loads(decorated.stdout)
    events = derived["events"]
    require(derived["defaultFilteredCount"] == 770, "Default filtered profile changed; review the full-view parity before publishing")
    source_files = [
        (ROOT / "data/trace_chronology/manifest.json", "global source-backed chronology manifest"),
        (timing_path, "global source-backed chronology payload"),
        (ROOT / "data/location_label_overlay.json.gz", "current reviewed and generic display labels"),
        (ROOT / "data/quality_detail_patches.json.gz", "quality correction IDs retain their higher-priority location labels"),
        (ROOT / "data/encounters/manifest.json", "encounter classification and attribute review pins"),
        (ROOT / "data/encounters/evidence.json.gz", "encounter source evidence"),
        (ROOT / "data/encounters/label_origins.json.gz", "encounter classification provenance"),
        (ROOT / "encounter_evidence.js", "actual current encounter decoration rules"),
        (ROOT / "trace_chronology.js", "actual current source chronology schema and index rules"),
    ]
    source_pins = {"effectiveSummaryShards": summary_pins, "files": [pin(path, role) for path, role in source_files],
                   "catalogCount": rows_read, "globalTimingDecodedSha256": timing_manifest["decodedSha256"],
                   "globalTimingReleaseId": timing_manifest["releaseId"], "packedTraceIndex": dict(trace_pin, decodedSha256=sha(trace_raw), decodedBytes=len(trace_raw))}
    payload = {"schemaId": SCHEMA, "profileId": "france_1954_flap", "scope": "mapped_reports_in_initial_time_window",
               "dateRange": {"start": START, "end": END}, "events": events, "traceChronology": timing,
               "traceEventOrder": [row[0] for row in trace_rows],
               "filterValues": {key: sorted(value) for key, value in values.items()}, "sourcePins": source_pins}
    raw = (json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n").encode("utf-8")
    compressed = gzip.compress(raw, compresslevel=9, mtime=0)
    require(len(compressed) < MAX_GZIP_BYTES, "Scoped view exceeded its reviewed one MiB output ceiling")
    output.mkdir(parents=True, exist_ok=True)
    artifact = output / "progressive_view.json.gz"
    artifact.write_bytes(compressed)
    manifest = {"schemaId": "ufo-progressive-startup-manifest-v1", "profileId": payload["profileId"],
                "scope": payload["scope"], "dateRange": payload["dateRange"],
                "artifact": {"file": artifact.name, "gzipBytes": len(compressed), "gzipSha256": sha(compressed),
                             "decodedBytes": len(raw), "decodedSha256": sha(raw)},
                "counts": {"events": len(events), "mappedEvents": len(events), "defaultFilteredEvents": derived["defaultFilteredCount"],
                           "acceptedTimingRows": len(timing["rows"]), "excludedDates": len(timing["excludedDates"]), "globalCatalog": rows_read},
                "sourcePins": source_pins, "timingSnapshot": derived["timingSnapshot"],
                "traceParity": derived["traceParity"],
                "policies": {"unmappedReportsIncluded": False, "fullCatalogReady": False, "canonicalSourcesMutated": False,
                             "rawNarrativesRedistributed": False, "observedFlightPathsAsserted": False},
                "lifecycle": {"purpose": "Product initial mapped view while complete catalog prepares in the background",
                              "rebuild": "python scripts/build_progressive_startup_profile.py",
                              "retention": "One current derived profile; previous legacy profile remains unchanged for fallback. No full corpus copy.",
                              "newFilesLargerThan100MiB": [], "netGeneratedBytes": len(compressed)}}
    manifest_path = output / "progressive_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--delivery-plan", type=Path, default=ROOT / "releases/workspace-analysis-20261008/delivery_plan.json")
    parser.add_argument("--output", type=Path, default=PROFILE)
    parser.add_argument("--node", default="C:/Program Files/nodejs/node.exe")
    args = parser.parse_args()
    result = build(args.delivery_plan, args.output, args.node)
    print(json.dumps({"artifact": result["artifact"], "counts": result["counts"], "timingSnapshot": result["timingSnapshot"]}, indent=2))


if __name__ == "__main__":
    main()

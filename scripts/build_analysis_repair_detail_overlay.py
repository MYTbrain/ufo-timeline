"""Package reviewed sparse detail date corrections; never copy a detail corpus.

Read shared original chunks, apply the retained quality overlay in memory, then
run the existing frozen MUFON and reviewed-year guards. Persist one bounded gzip
packet, its delivery pins and a receipt. --dry-run computes/validates without writes.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from copy import deepcopy
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SHARED = Path.home() / "Desktop/UFO Timeline map tool"
RELATIVE = Path("data/research/analysis-repairs-20261007")
SCHEMA = "ufo-analysis-repair-detail-overlay-v1"
MAX_BYTES = 1024 * 1024
CORE_GUARDS = ("event_id", "canonical_event_id", "source_id", "source", "date_raw", "date_iso", "end_date_iso",
               "sort_date_iso", "date_precision", "chunk_id", "detail_index")
RAW_GUARDS = ("id", "source", "source_id", "name", "date", "location", "city", "country", "description")
OUTPUT_FIELDS = frozenset(("date_iso", "end_date_iso", "sort_date_iso", "date_precision", "date_interval_semantics",
                           "exact_day_eligible", "date_recovery_contract", "date_recovery_provenance"))


def raw_json(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def pin(path):
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(block)
    return {"path": str(path.resolve()), "bytes": path.stat().st_size, "sha256": hasher.hexdigest()}


def read_json(path):
    data = path.read_bytes()
    return json.loads(gzip.decompress(data) if path.suffix == ".gz" else data)


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def event_rows(packet):
    if isinstance(packet, list):
        return packet
    if isinstance(packet, dict):
        for key in ("events", "rows", "records"):
            if isinstance(packet.get(key), list):
                return packet[key]
    raise ValueError("Detail chunk does not contain a supported event array")


def apply_quality(row, patch):
    if patch is None:
        return row
    for key, value in patch["guards"].items():
        if row.get(key) != value:
            raise ValueError(f"Existing quality guard failed: {row.get('event_id')}:{key}")
    result = dict(row)
    result.update(deepcopy(patch["setFields"]))
    return result


def guard_value(row, path):
    value = row
    for part in path:
        if isinstance(value, dict) and part in value:
            value = value[part]
        elif isinstance(value, list) and isinstance(part, int) and 0 <= part < len(value):
            value = value[part]
        else:
            return {"path": path, "exists": False, "value": None}
    if value is not None and not isinstance(value, (str, int, float, bool)):
        raise ValueError(f"Guard must remain a scalar source value: {path}")
    return {"path": path, "exists": True, "value": value}


def source_chunk(shared, name):
    for parent in (shared / "data/canonical_web/event_chunks", shared / "static_bundle/data/canonical_web/event_chunks"):
        for suffix in (".json.gz", ".json"):
            path = parent / (Path(name).stem + suffix)
            if path.exists():
                return path
    raise FileNotFoundError(f"Shared original detail chunk unavailable: {name}")


def build(shared, output, dry_run=False, maximum_bytes=MAX_BYTES):
    shared, output = shared.resolve(), output.resolve()
    if shared == output or shared in output.parents and not output.is_relative_to(ROOT / "data/analysis_repair_detail"):
        raise ValueError("Output must be the dedicated small frontend detail-overlay directory")
    sys.path.insert(0, str(shared / "scripts"))
    mufon = load_module("repair_detail_mufon", shared / "scripts/build_analysis_repair_catalog_overlay.py")
    year = load_module("repair_detail_year", ROOT / "scripts/build_analysis_reviewed_year_overlay.py")
    mufon_path = shared / RELATIVE / "attributes/mufon_partial_date_patches.json.gz"
    year_path = shared / RELATIVE / "source-quality/catalog/reviewed_year_patches.json.gz"
    mufon_patches, year_patches = mufon.load_patch_map(str(mufon_path)), year.load_patch_map(str(year_path))
    if len(mufon_patches) != 3898 or len(year_patches) != 2 or set(mufon_patches) & set(year_patches):
        raise ValueError("Frozen detail patch allowlists changed")
    quality_path = ROOT / "data/quality_detail_patches.json.gz"
    quality_config = read_json(ROOT / "data/app_config.json")["detailQualityOverlay"]
    quality_pin = pin(quality_path)
    if quality_pin["sha256"] != quality_config["gzipSha256"] or (quality_config.get("gzipBytes") is not None and quality_pin["bytes"] != quality_config["gzipBytes"]):
        raise ValueError("Existing protected quality overlay delivery pin changed")
    quality = read_json(quality_path)
    if len(quality["patches"]) != 4451 or quality_config["patchCount"] != 4451:
        raise ValueError("Existing protected quality patch inventory changed")
    for key in ("baseManifestSha256", "qualityManifestSha256"):
        if quality[key] != quality_config[key]:
            raise ValueError("Existing quality source pins changed")
    quality_by_id = {str(patch["eventId"]): patch for patch in quality["patches"]}
    source_paths = {
        "baseQualityManifestSha256": shared / "data/releases/quality-20261007/map_delta/canonical_web_manifest.json",
        "mufonPatchSha256": mufon_path,
        "mufonRepairManifestSha256": shared / RELATIVE / "catalog/canonical_web_manifest.json",
        "reviewedYearPatchSha256": year_path,
        "reviewedYearManifestSha256": year_path.parent / "canonical_web_manifest.json",
        "sourceReviewSha256": shared / RELATIVE / "source-quality/source_quality_review.json",
        "existingQualityOverlayGzipSha256": quality_path,
    }
    inputs = {key: pin(path) for key, path in source_paths.items()}
    source_pins = {key: value["sha256"] for key, value in inputs.items()}
    if source_pins["baseQualityManifestSha256"] != mufon.EXPECTED_BASE_MANIFEST_SHA256 or source_pins["sourceReviewSha256"] != year.EXPECTED_REVIEW_SHA256:
        raise ValueError("Audited base/source-review manifest changed")
    jobs = defaultdict(list)
    for event_id, patch in mufon_patches.items():
        path = source_chunk(shared, patch["detailChunk"])
        jobs[path].append((event_id, "mufon_partial_date", patch))
    for event_id, patch in year_patches.items():
        path = Path(patch["sourceRecordLocator"]["path"])
        if pin(path)["sha256"] != patch["sourceRecordLocator"]["sha256"]:
            raise ValueError("Reviewed-year frozen detail source changed")
        jobs[path].append((event_id, "source_reviewed_year", patch))
    packet_patches, chunks, seen = [], [], set()
    prior_quality_overlap = 0
    for path, entries in sorted(jobs.items(), key=lambda item: str(item[0])):
        rows = event_rows(read_json(path))
        wanted = {item[0]: item for item in entries}
        found = set()
        for index, original in enumerate(rows):
            event_id = str(original.get("event_id"))
            if event_id not in wanted:
                continue
            if event_id in found or event_id in seen:
                raise ValueError("Repeated original detail identity")
            _, kind, frozen = wanted[event_id]
            chunk_id = Path(path.name.removesuffix(".gz")).stem
            if original.get("chunk_id") != chunk_id or original.get("detail_index") != index:
                raise ValueError("Original detail array/object locator disagrees with record")
            if kind == "source_reviewed_year" and index != frozen["sourceRecordLocator"]["detailIndex"]:
                raise ValueError("Reviewed-year exact source index changed")
            before = apply_quality(original, quality_by_id.get(event_id))
            if event_id in quality_by_id:
                prior_quality_overlap += 1
            effective = (mufon if kind == "mufon_partial_date" else year).apply_detail_patch(before, {event_id: frozen})
            changed = {key for key in set(before) | set(effective) if before.get(key) != effective.get(key) or (key in before) != (key in effective)}
            if not changed <= OUTPUT_FIELDS or set(effective[key] for key in ("exact_day_eligible",)) != {False}:
                raise ValueError("Reviewed correction changed a protected field or promoted an exact day")
            fields = {key: deepcopy(effective[key]) for key in OUTPUT_FIELDS}
            guards = [guard_value(before, [key]) for key in CORE_GUARDS]
            if kind == "source_reviewed_year":
                guards += [guard_value(before, ["raw_source_row", key]) for key in RAW_GUARDS]
            packet_patches.append({"eventId": original["event_id"], "chunkId": chunk_id, "detailIndex": index,
                                   "kind": kind, "guards": guards, "setFields": fields})
            found.add(event_id)
            seen.add(event_id)
        if found != set(wanted):
            raise ValueError(f"Frozen detail source lost requested records: {path}")
        chunks.append(dict(pin(path), matchedPatches=len(found)))
    if seen != set(mufon_patches) | set(year_patches):
        raise ValueError("Detail packet completeness failed")
    packet_patches.sort(key=lambda patch: patch["eventId"])
    payload = {"schemaId": SCHEMA, "schemaVersion": 1, "sourcePins": source_pins, "patches": packet_patches}
    decoded = raw_json(payload)
    compressed = gzip.compress(decoded, compresslevel=9, mtime=0)
    manifest = {"schemaId": SCHEMA, "schemaVersion": 1, "file": "patches.json.gz", "bytes": len(decoded), "sha256": sha(decoded),
                "gzipBytes": len(compressed), "gzipSha256": sha(compressed), "patchCount": len(packet_patches), "sourcePins": source_pins}
    receipt = {"schemaId": "ufo-analysis-repair-detail-build-receipt-v1", "status": "validated_dry_run" if dry_run else "validated_local_candidate",
               "patchCount": len(packet_patches), "mufonPartialDates": len(mufon_patches), "reviewedOccurrenceYears": len(year_patches),
               "existingQualityPatchCountRetained": 4451, "existingQualityOverlap": prior_quality_overlap, "sourcePins": inputs,
               "sourceChunks": chunks, "delivery": manifest,
               "checks": ["Frozen source patch functions applied after unchanged quality overlay", "Exact event/source/date and detail locator guards",
                          "Reviewed raw-source identity/narrative preserved", "Only reviewed interval/provenance fields differ", "No exact-day eligibility promoted"],
               "storage": {"fullCorpusCopied": False, "originalChunksWritten": False, "newFilesAbove100MiB": [],
                           "purpose": "Current sparse production detail-date correction packet and immutable source trail",
                           "rebuild": "py -3 scripts/build_analysis_repair_detail_overlay.py --shared-root <protected canonical root>",
                           "retention": "Retain this packet/manifest/receipt as the local release candidate; source datasets and prior quality overlay unchanged"},
               "deploymentPerformed": False}
    manifest_bytes, receipt_bytes = raw_json(manifest), raw_json(receipt)
    total = len(compressed) + len(manifest_bytes) + len(receipt_bytes)
    if total > maximum_bytes:
        raise ValueError(f"Sparse detail overlay exceeds bounded byte budget: {total}/{maximum_bytes}")
    receipt["storage"]["generatedBytes"] = total
    receipt_bytes = raw_json(receipt)
    total = len(compressed) + len(manifest_bytes) + len(receipt_bytes)
    receipt["storage"]["generatedBytes"] = total
    receipt_bytes = raw_json(receipt)
    if len(compressed) + len(manifest_bytes) + len(receipt_bytes) > maximum_bytes:
        raise ValueError("Sparse detail packet plus final receipt exceeds the byte budget")
    if not dry_run:
        output.mkdir(parents=True, exist_ok=True)
        for name, content in (("patches.json.gz", compressed), ("manifest.json", manifest_bytes), ("receipt.json", receipt_bytes)):
            (output / name).write_bytes(content)
    return {"status": receipt["status"], "patchCount": len(packet_patches), "sourceChunks": len(chunks), "gzipBytes": len(compressed),
            "decodedBytes": len(decoded), "generatedBytes": total, "maximumBytes": maximum_bytes, "existingQualityOverlap": prior_quality_overlap,
            "manifest": manifest, "outputRoot": str(output), "deployed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shared-root", type=Path, default=DEFAULT_SHARED)
    parser.add_argument("--output-root", type=Path, default=ROOT / "data/analysis_repair_detail")
    parser.add_argument("--max-output-bytes", type=int, default=MAX_BYTES)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(json.dumps(build(args.shared_root, args.output_root, args.dry_run, args.max_output_bytes), indent=2))

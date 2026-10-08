"""Build a tiny, guarded local overlay for two source-reviewed occurrence years.

Only changed summary shards are written. Original details are patched in memory;
raw source data, map/trace assets, canonical order and scientific gates survive.
Year boundaries and calendar midpoints are not observed occurrence days.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import csv
from datetime import date, timedelta
from functools import lru_cache
import gzip
import hashlib
import json
from pathlib import Path
from typing import Any

OVERLAY_ID = "analysis-source-reviewed-year-overlay-20261007"
CONTRACT = "source_reviewed_occurrence_year_v1"
RELATIVE_REVIEW = Path("data/research/analysis-repairs-20261007/source-quality")
EXPECTED_REVIEW_SHA256 = "e870a2ae49e91c490fa45cb2362ce0e93dda0a477650a5d573627a6ae96924b3"
EXPECTED_CANDIDATE_SHA256 = "59a68bfbf27ebfd2ec029413086bcb37223e0cbb5be7e4c78452805628c90b4a"
EXPECTED_QUALITY_SHA256 = "316bfbfb3c20fa57324b28d840d84e8f79581f54d228876b4ad947408e028c2e"
MAXIMUM_BYTES = 3 * 1024 * 1024
# Explicit adjudication allowlist. Other sentinel candidates remain unresolved.
TARGETS = {
    "192457427678091": {"year": 1967, "updbNativeId": "5198825", "nativeId": "10085", "summaryShard": "summary_000061.json.gz"},
    "2629924530431414": {"year": 1975, "updbNativeId": "5202682", "nativeId": "13010", "summaryShard": "summary_000042.json.gz"},
}
DATE_FIELDS = ("event_id", "source", "date_raw", "date_iso", "end_date_iso", "sort_date_iso", "date_precision")
RAW_FIELDS = ("id", "source", "source_id", "name", "date", "location", "city", "country")
SUMMARY_FIELDS = ("event_id", "source", "date_raw", "date_iso", "end_date_iso", "sort_date_iso", "date_precision", "chunk_id", "detail_index")


def raw_json(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def identity(row: dict, fields: tuple[str, ...]) -> str:
    return digest(raw_json({key: row.get(key) for key in fields}))


def read_json(path: Path) -> Any:
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == ".gz" else raw)


def pin(path: Path) -> dict:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(block)
    return {"path": str(path.resolve()), "bytes": path.stat().st_size, "sha256": hasher.hexdigest()}


def year_patch(year: int) -> dict:
    start, end = date(year, 1, 1), date(year, 12, 31)
    midpoint = start + timedelta(days=(end - start).days // 2)
    return {
        "date_iso": start.isoformat(), "end_date_iso": end.isoformat(),
        "sort_date_iso": midpoint.isoformat(), "date_precision": "year",
        "date_interval_semantics": "source_calendar_precision_bounds_not_observed_days",
        "exact_day_eligible": False, "date_recovery_contract": CONTRACT,
    }


def _default_patch_path() -> Path:
    # Code lives in a small worktree; corpus/output remain in the shared project.
    candidates = [Path(__file__).resolve().parents[1], Path.home() / "Desktop/UFO Timeline map tool"]
    for root in candidates:
        path = root / RELATIVE_REVIEW / "catalog/reviewed_year_patches.json.gz"
        if path.exists():
            return path
    raise FileNotFoundError("Reviewed-year patch map unavailable; provide an explicit frozen patch map")


@lru_cache(maxsize=4)
def load_patch_map(path: str | None = None) -> dict[str, dict]:
    patch_path = Path(path) if path else _default_patch_path()
    manifest_path = patch_path.parent / "canonical_web_manifest.json"
    if manifest_path.exists():
        metadata = read_json(manifest_path).get("reviewedYearOverlay", {})
        if metadata.get("sourceManifest", {}).get("sha256") != EXPECTED_CANDIDATE_SHA256 or metadata.get("frozenPatches", {}).get("sha256") != pin(patch_path)["sha256"]:
            raise ValueError("Reviewed-year frozen patch/manifest receipt failed")
    packet = read_json(patch_path)
    if packet.get("overlayId") != OVERLAY_ID or packet.get("sourceReviewSha256") != EXPECTED_REVIEW_SHA256:
        raise ValueError("Reviewed-year patch packet identity failed")
    patches = packet.get("patches", [])
    if {str(row.get("eventId")) for row in patches} != set(TARGETS) or len(patches) != 2:
        raise ValueError("Reviewed-year patch allowlist failed")
    result = {}
    for patch in patches:
        event_id = str(patch["eventId"])
        target = TARGETS[event_id]
        if patch["source"] != "phenomenainon_updb" or patch["patch"] != year_patch(target["year"]):
            raise ValueError("Reviewed-year date/source contract failed")
        if patch["updbNativeId"] != target["updbNativeId"] or patch["underlyingNativeId"] != "S" + target["nativeId"]:
            raise ValueError("Reviewed-year native identity failed")
        if patch["rawDate"] != "1900-01-01" or digest(patch["rawDate"].encode("utf-8")) != patch["rawDateSha256"]:
            raise ValueError("Reviewed-year original date identity failed")
        result[event_id] = patch
    return result


def _guard(row: dict, patch: dict, *, detail: bool) -> None:
    if str(row.get("event_id")) != patch["eventId"] or row.get("source") != patch["source"]:
        raise ValueError("Reviewed-year event/source guard failed")
    if row.get("date_raw") != patch["rawDate"] or row.get("date_precision") != "exact_day" or row.get("sort_date_iso") != "1900-01-01":
        raise ValueError("Reviewed-year original normalized date guard failed")
    if row.get("date_iso") not in (None, "1900-01-01") or row.get("end_date_iso") not in (None, "1900-01-01"):
        raise ValueError("Reviewed-year original date bounds guard failed")
    if detail:
        raw = row.get("raw_source_row") or {}
        if str(row.get("source_id")) != patch["updbNativeId"] or row.get("canonical_event_id") != patch["canonicalEventId"]:
            raise ValueError("Reviewed-year detail native/canonical identity guard failed")
        if identity(row, DATE_FIELDS) != patch["detailDateIdentitySha256"] or identity(raw, RAW_FIELDS) != patch["rawSourceIdentitySha256"]:
            raise ValueError("Reviewed-year detail date/raw identity hash guard failed")
        if digest(str(raw.get("description", "")).encode("utf-8")) != patch["sourceNarrativeSha256"]:
            raise ValueError("Reviewed-year source narrative hash guard failed")
        if patch["occurrenceClause"] not in str(raw.get("description", "")):
            raise ValueError("Reviewed-year source occurrence clause guard failed")
    elif identity(row, SUMMARY_FIELDS) != patch["summaryDateIdentitySha256"]:
        raise ValueError("Reviewed-year summary date/locator identity guard failed")


def apply_detail_patch(row: dict, patches: dict[str, dict] | None = None) -> dict:
    """Apply after existing quality and MUFON detail overlays; unrelated rows survive."""
    patch = (patches if patches is not None else load_patch_map()).get(str(row.get("event_id")))
    if patch is None:
        return row
    _guard(row, patch, detail=True)
    result = dict(row)
    result.update(patch["patch"])
    result["date_recovery_provenance"] = {
        "overlay_id": OVERLAY_ID, "source": patch["source"],
        "underlying_source": "NUFORC", "underlying_native_id": patch["underlyingNativeId"],
        "source_review_sha256": EXPECTED_REVIEW_SHA256,
        "source_narrative_sha256": patch["sourceNarrativeSha256"],
        "original_detail_date_identity_sha256": patch["detailDateIdentitySha256"],
        "original_date_precision": "exact_day", "original_date_was_reviewed_sentinel": True,
        "interval_bounds_are_observed_days": False, "sort_midpoint_is_observed_day": False,
    }
    return result


def apply_summary_patch(row: dict, patch: dict) -> dict:
    _guard(row, patch, detail=False)
    result = dict(row)
    result.update(patch["patch"])
    result["date_recovery_raw_sha256"] = patch["rawDateSha256"]
    return result


def _verify_source_observations(review: dict, proposals: list[dict]) -> list[dict]:
    """Verify frozen source CSV bytes, native ID, occurrence role and narrative join."""
    csv_pins = {row["path"]: row for row in review["inputs"] if row["path"].endswith(".csv")}
    observations = {}
    for proposal in proposals:
        for observation in proposal["sourceObservations"]:
            observations.setdefault(observation["file"], []).append((proposal, observation))
    receipts = []
    for filename, entries in sorted(observations.items()):
        path = Path(filename)
        actual = pin(path)
        expected = csv_pins.get(filename)
        if expected is None or actual["sha256"] != expected["sha256"] or actual["bytes"] != expected["bytes"]:
            raise ValueError("Frozen occurrence-source CSV receipt changed")
        by_row = {item[1]["sourceRowNumber"]: item for item in entries}
        found = set()
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            for row_number, source_row in enumerate(csv.DictReader(stream), start=2):
                item = by_row.get(row_number)
                if item is None:
                    continue
                proposal, observed = item
                target = TARGETS[proposal["eventId"]]
                if str(source_row.get("No")) != target["nativeId"] or observed["nativeId"] != target["nativeId"]:
                    raise ValueError("Underlying occurrence-source native ID changed")
                if {key: str(source_row.get(key, "")).strip() for key in observed["fields"]} != observed["fields"]:
                    raise ValueError("Underlying structured occurrence/submission roles changed")
                occurred = source_row.get("Occurred", "").strip()
                clause = proposal["calendarPrecisionDecision"]["occurrenceClause"]
                if not occurred.startswith(str(target["year"]) + "-") or "Approximate" not in occurred or clause not in source_row.get("Description", ""):
                    raise ValueError("Reviewed occurrence year/clause no longer supported")
                found.add(row_number)
                if found == set(by_row):
                    break
        if found != set(by_row):
            raise ValueError("Underlying occurrence-source row locator missing")
        receipts.append(actual)
    return receipts


def build(data_root: Path, output: Path, *, dry_run: bool = False, maximum_bytes: int = MAXIMUM_BYTES) -> dict:
    data_root, output = data_root.resolve(), output.resolve()
    candidate = data_root / "data/research/analysis-repairs-20261007/catalog"
    quality = data_root / "data/releases/quality-20261007/map_delta"
    review_path = data_root / RELATIVE_REVIEW / "source_quality_review.json"
    if output == candidate or output == quality or candidate in output.parents or quality in output.parents:
        raise ValueError("Supplemental candidate must be separate from existing candidate/validated release")
    review_raw = review_path.read_bytes()
    if digest(review_raw) != EXPECTED_REVIEW_SHA256:
        raise ValueError("Source adjudication report changed")
    review = json.loads(review_raw)
    proposals = [row for row in review["sentinelDateReview"] if row.get("proposal")]
    if len(proposals) != 2 or {row["eventId"] for row in proposals} != set(TARGETS):
        raise ValueError("Source review proposals differ from the explicit two-record allowlist")
    source_receipts = _verify_source_observations(review, proposals)
    manifest_path = candidate / "canonical_web_manifest.json"
    if pin(manifest_path)["sha256"] != EXPECTED_CANDIDATE_SHA256 or pin(quality / "canonical_web_manifest.json")["sha256"] != EXPECTED_QUALITY_SHA256:
        raise ValueError("Current candidate/quality manifest identity changed")
    manifest = read_json(manifest_path)
    summary_index_path = candidate / "summary_manifest.json"
    summary_index_raw = summary_index_path.read_bytes()
    summary_index = json.loads(summary_index_raw)
    index_by_file, row_start = {}, 0
    for entry in summary_index:
        index_by_file[Path(entry["file"]).stem + ".json.gz"] = (entry, row_start)
        row_start += entry["event_count"]
    if row_start != manifest["counts"]["events"]:
        raise ValueError("Candidate summary index/event count parity failed")
    patches, shard_packets, shard_receipts = [], [], []
    for proposal in proposals:
        event_id, target = proposal["eventId"], TARGETS[proposal["eventId"]]
        expected_proposal = {"datePrecision": "year", "dateIso": None, "startDate": f"{target['year']}-01-01", "endDate": f"{target['year']}-12-31"}
        if proposal["proposal"] != expected_proposal or proposal["dateRole"] != "source_structured_occurrence" or proposal["calendarPrecisionDecision"]["status"] != "source_reviewed_year_only":
            raise ValueError("Adjudication cannot promote an exact occurrence day")
        locator = proposal["sourceRecordLocator"]
        detail_path = Path(locator["path"])
        if pin(detail_path)["sha256"] != locator["sha256"]:
            raise ValueError("Source detail chunk receipt changed")
        detail = read_json(detail_path)[locator["detailIndex"]]
        raw = detail.get("raw_source_row", {})
        if str(detail.get("event_id")) != event_id or str(detail.get("source_id")) != target["updbNativeId"] or detail.get("canonical_event_id") != proposal["canonicalEventId"]:
            raise ValueError("Reviewed detail event/canonical/native identity changed")
        if raw.get("source") != "2" or raw.get("name") != "NUFORC" or raw.get("source_id") != "S" + target["nativeId"] or raw.get("id") != target["updbNativeId"] or raw.get("date") != proposal["rawUpdbDate"]:
            raise ValueError("Reviewed UPDB source identity changed")
        if digest(raw.get("description", "").encode("utf-8")) != proposal["sourceNarrativeSha256"]:
            raise ValueError("Reviewed source narrative changed")
        filename = target["summaryShard"]
        source_path = next((root / "summary_shards" / filename for root in (candidate, quality) if (root / "summary_shards" / filename).exists()), None)
        if source_path is None:
            raise FileNotFoundError(filename)
        original_compressed = source_path.read_bytes()
        original_decoded = gzip.decompress(original_compressed)
        rows = json.loads(original_decoded)
        entry, global_start = index_by_file[filename]
        if len(rows) != entry["event_count"] or rows[0]["event_id"] != entry["start_event_id"] or rows[-1]["event_id"] != entry["end_event_id"]:
            raise ValueError("Summary shard referential metadata mismatch")
        matches = [index for index, row in enumerate(rows) if str(row["event_id"]) == event_id]
        if len(matches) != 1:
            raise ValueError("Reviewed summary event must occur exactly once in its frozen shard")
        local_index = matches[0]
        summary = rows[local_index]
        if summary.get("chunk_id") != detail_path.stem or summary.get("detail_index") != locator["detailIndex"]:
            raise ValueError("Summary/detail locator join changed")
        patch = {
            "eventId": event_id, "canonicalEventId": proposal["canonicalEventId"], "source": "phenomenainon_updb",
            "updbNativeId": target["updbNativeId"], "underlyingNativeId": "S" + target["nativeId"],
            "rawDate": "1900-01-01", "rawDateSha256": digest(b"1900-01-01"),
            "detailDateIdentitySha256": identity(detail, DATE_FIELDS), "rawSourceIdentitySha256": identity(raw, RAW_FIELDS),
            "summaryDateIdentitySha256": identity(summary, SUMMARY_FIELDS),
            "sourceNarrativeSha256": proposal["sourceNarrativeSha256"], "occurrenceClause": proposal["calendarPrecisionDecision"]["occurrenceClause"],
            "catalogRowIndex": global_start + local_index, "summaryShard": filename, "summaryRowIndex": local_index,
            "sourceRecordLocator": locator, "sourceObservations": proposal["sourceObservations"], "patch": year_patch(target["year"]),
        }
        apply_detail_patch(detail, {event_id: patch})
        patched = apply_summary_patch(summary, patch)
        if patched["event_id"] != summary["event_id"] or patched.get("same_day_match_strength") != summary.get("same_day_match_strength"):
            raise ValueError("Date patch changed event identity or craft linkage evidence")
        rows[local_index] = patched
        decoded = raw_json(rows)
        compressed = gzip.compress(decoded, compresslevel=9, mtime=0)
        shard_packets.append((filename, compressed))
        shard_receipts.append({"file": filename, "eventCount": len(rows), "patchedRows": 1, "catalogRowIndex": patch["catalogRowIndex"], "source": pin(source_path), "sourceDecodedSha256": digest(original_decoded), "bytes": len(compressed), "sha256": digest(compressed), "decodedSha256": digest(decoded)})
        patches.append(patch)
    before_counts = manifest["counts"]["date_precision_counts"]
    after_counts = Counter(before_counts)
    after_counts["exact_day"] -= len(patches)
    after_counts["year"] += len(patches)
    if min(after_counts.values()) < 0 or sum(after_counts.values()) != row_start:
        raise ValueError("Supplemental precision count parity failed")
    patched_manifest = deepcopy(manifest)
    patched_manifest["counts"]["date_precision_counts"] = dict(sorted(after_counts.items()))
    patch_packet = {"overlayId": OVERLAY_ID, "status": "local_review_candidate", "sourceReviewSha256": EXPECTED_REVIEW_SHA256, "sourceReceipts": source_receipts, "patches": patches}
    patch_packed = gzip.compress(raw_json(patch_packet), compresslevel=9, mtime=0)
    patched_manifest["reviewedYearOverlay"] = {
        "overlayId": OVERLAY_ID, "status": "local_review_candidate", "patchRows": 2, "changedSummaryShards": 2,
        "sourceManifest": pin(manifest_path), "sourceReview": pin(review_path),
        "frozenPatches": {"path": str(output / "reviewed_year_patches.json.gz"), "bytes": len(patch_packed), "sha256": digest(patch_packed)},
        "dateRecoveryContract": CONTRACT, "exactDayEligibleAdded": 0, "exactDaySentinelsDemoted": 2,
        "intervalBoundsAreObservedDays": False, "sortMidpointIsObservedDay": False,
        "eventIdsAndRowOrderingRetained": True, "rawSourceFieldsRetained": True,
        "mapTraceAssetsCopied": False, "detailCorpusCopied": False,
    }
    manifest_raw = raw_json(patched_manifest)
    files = shard_packets + [
        ("canonical_web_manifest.json", manifest_raw), ("canonical_web_manifest.json.gz", gzip.compress(manifest_raw, compresslevel=9, mtime=0)),
        ("summary_manifest.json", summary_index_raw), ("summary_manifest.json.gz", gzip.compress(summary_index_raw, compresslevel=9, mtime=0)),
        ("reviewed_year_patches.json.gz", patch_packed),
    ]
    predicted = sum(len(raw) for _, raw in files) + 32 * 1024
    receipt = {"schemaId": "analysis-reviewed-year-overlay-v1", "overlayId": OVERLAY_ID, "status": "dry_run" if dry_run else "local_review_candidate", "sourceReview": pin(review_path), "sourceCandidateManifest": pin(manifest_path), "sourceOccurrenceCsvReceipts": source_receipts, "catalogRows": row_start, "patchRows": 2, "beforeDatePrecision": before_counts, "afterDatePrecision": dict(sorted(after_counts.items())), "changedSummaryShards": shard_receipts, "canonicalManifestSha256": digest(manifest_raw), "predictedBytesWith32KiBEvidenceReserve": predicted, "maximumBytes": maximum_bytes, "canonicalEventsMutated": False, "tracePointQualificationPromoted": False, "eventOrderAndRowIndexRetained": True, "deployed": False}
    if predicted > maximum_bytes:
        raise ValueError(f"Supplemental overlay exceeds small-output budget: {predicted}/{maximum_bytes}")
    if dry_run:
        return receipt
    (output / "summary_shards").mkdir(parents=True, exist_ok=True)
    shard_names = {filename for filename, _raw in shard_packets}
    for filename, raw in files:
        (output / "summary_shards" / filename if filename in shard_names else output / filename).write_bytes(raw)
    (output / "catalog_overlay_receipt.json").write_bytes(raw_json(receipt))
    total = sum(path.stat().st_size for path in output.rglob("*") if path.is_file())
    purpose_path = output.parent / "PURPOSE.txt"
    marker = "Supplemental reviewed YEAR overlay:"
    note = (
        f"\n{marker} catalog/ is the current local candidate for two guarded UPDB/NUFORC occurrence-year corrections (1967 and 1975), layered ahead of the existing MUFON catalog candidate. It writes two gzip summary shards and small metadata, preserves original data and order, and uses in-memory detail patches.\n"
        "Rebuild: scripts/build_analysis_reviewed_year_overlay.py --data-root <shared root> --output <source-quality/catalog>. Receipts pin source review, source CSVs, detail chunks, original/candidate summaries and manifest. January 1/December 31 boundaries and midpoint are representative bounds/order, never exact occurrence days.\n"
        f"Retention: retain this local review overlay and source_quality_review.json. Production dc834bac-2108-4de3-baad-47044e2ec51c and sole rollback 78cc3660-5750-4685-a095-fee6dce37fbf remain unchanged. Overlay measured {total:,} bytes ({total / 1048576:.2f} MiB) net growth; no file >100 MiB. No superseded release/backup/staging or full corpus copy created; no deletion proposed.\n"
    )
    previous = purpose_path.read_text(encoding="utf-8") if purpose_path.exists() else "Purpose: retain bounded source-quality review evidence.\n"
    if marker in previous:
        previous = previous.split("\n" + marker)[0]
    purpose_path.write_text(previous.rstrip() + "\n" + note, encoding="utf-8")
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-output-bytes", type=int, default=MAXIMUM_BYTES)
    args = parser.parse_args()
    result = build(args.data_root, args.output, dry_run=args.dry_run, maximum_bytes=args.max_output_bytes)
    print(json.dumps({key: value for key, value in result.items() if key != "sourceOccurrenceCsvReceipts"}, indent=2))

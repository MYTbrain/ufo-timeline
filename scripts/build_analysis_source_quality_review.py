"""Build bounded, read-only source-quality review and sensitivity evidence.

The shared corpus is streamed, never copied. This script proposes no dates from
narrative prose, never repairs coordinates, and does not modify runtime gates.
The output is a reproducible review packet, not an accepted canonical overlay.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import date
import gzip
import hashlib
import json
from pathlib import Path
import re
from typing import Any

EXPECTED_MANIFEST_SHA256 = "316bfbfb3c20fa57324b28d840d84e8f79581f54d228876b4ad947408e028c2e"
PRIORITY_EVENT_IDS = {"3482820524303901", "400494667543215", "2858831246130457"}
REVIEW_SENTINELS = {"1900-01-01", "1970-01-01"}
# Targeted source adjudications, not a general rule that discards the month/day
# of every approximate datetime. Both underlying IDs and same-report occurrence
# clauses must agree with the structured occurrence year before use.
PARTIAL_YEAR_ADJUDICATIONS = {
    "10085": {"year": 1967, "occurrenceClause": "back in 1967 in Florida"},
    "13010": {"year": 1975, "occurrenceClause": "near Oscoda in the late summer of 1975"},
}


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def load_json(path: Path) -> tuple[Any, dict[str, Any]]:
    raw = path.read_bytes()
    content = gzip.decompress(raw) if path.suffix == ".gz" else raw
    return json.loads(content), {"path": str(path), "bytes": len(raw), "sha256": sha256(raw), "contentSha256": sha256(content)}


def pinned_artifact(data_root: Path, analysis_root: Path, key: str, manifest: dict) -> tuple[list, dict]:
    entry = manifest["artifacts"][key]
    filename = Path(entry["file"]).name
    candidates = [analysis_root / "analysis_v2" / (filename + ".gz"), data_root / "webapp/static_public/data/analysis_v2" / filename]
    path = next((path for path in candidates if path.exists()), None)
    if path is None:
        raise FileNotFoundError(f"Pinned artifact unavailable locally: {key}")
    rows, receipt = load_json(path)
    if receipt["contentSha256"] != entry["sha256"] or len(rows) != entry["rowCount"]:
        raise ValueError(f"Pinned artifact identity/row count mismatch: {key}")
    receipt.update({"artifactKey": key, "releaseId": entry.get("releaseId"), "rows": len(rows), "schema": entry["rowSchema"]})
    return rows, receipt


def normalize_native_id(value: Any) -> str:
    raw = str(value or "").strip()
    return re.sub(r"^[SM](?=\d+$)", "", raw, flags=re.I)


def source_date(value: str) -> dict | None:
    """Only a structured ISO-prefix occurrence field can propose a date.

    The two sentinel values need adjudication in this targeted review lane;
    this does not downgrade all January 1 dates in the catalog.
    """
    match = re.match(r"^\s*(\d{4})-(\d{2})-(\d{2})(?=\s|T|$)", value or "")
    if not match:
        return None
    year, month, day = map(int, match.groups())
    iso = f"{year:04d}-{month:02d}-{day:02d}"
    if iso in REVIEW_SENTINELS or not 1 <= year <= 9999:
        return None
    try:
        if month == 0 and day == 0:
            return {"datePrecision": "year", "dateIso": None, "startDate": f"{year:04d}-01-01", "endDate": f"{year:04d}-12-31"}
        if day == 0 and 1 <= month <= 12:
            import calendar
            return {"datePrecision": "month", "dateIso": None, "startDate": f"{year:04d}-{month:02d}-01", "endDate": f"{year:04d}-{month:02d}-{calendar.monthrange(year, month)[1]:02d}"}
        date(year, month, day)
    except ValueError:
        return None
    return {"datePrecision": "exact_day", "dateIso": iso, "startDate": iso, "endDate": iso}


def text_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def source_identity_agrees(raw: dict, source_row: dict, family: str) -> bool:
    if normalize_native_id(raw.get("source_id")) != normalize_native_id(source_row.get("No")):
        return False
    original = source_row.get("Description") if family == "NUFORC" else source_row.get("Long Description")
    original = re.sub(r"^NUFORC UFO Sighting\s*\d+", "", str(original or ""), flags=re.I)
    left, right = text_key(raw.get("description", "")), text_key(original)
    # IDs alone do not establish identity. Require a substantial matching
    # narrative fragment, never use the fragment as a date assertion.
    return min(len(left), len(right)) >= 60 and (right[:160] in left or left[:160] in right)


def adjudicate_sentinel(raw: dict, source_rows: list[dict], family: str) -> dict:
    matches = [row for row in source_rows if source_identity_agrees(raw, row, family)]
    occurrence_key = "Occurred" if family == "NUFORC" else "Date/Time of Event"
    role_fields = [occurrence_key, "Reported", "Posted"] if family == "NUFORC" else [occurrence_key, "Date Submitted"]
    observations = [{"file": row["_file"], "sourceRowNumber": row["_row"], "nativeId": row.get("No"), "fields": {key: row.get(key, "").strip() for key in role_fields}} for row in matches]
    proposals = [source_date(row.get(occurrence_key, "")) for row in matches]
    valid = [proposal for proposal in proposals if proposal is not None]
    identities = {json.dumps(proposal, sort_keys=True) for proposal in valid}
    if valid and len(identities) == 1 and len(valid) == len(matches):
        approximate = any(re.search(r"\bapproximate\b", row.get(occurrence_key, ""), re.I) for row in matches)
        if approximate:
            adjudication = PARTIAL_YEAR_ADJUDICATIONS.get(normalize_native_id(raw.get("source_id"))) if family == "NUFORC" else None
            clause = text_key((adjudication or {}).get("occurrenceClause", ""))
            if not adjudication or not clause or clause not in text_key(raw.get("description", "")) or not all(clause in text_key(row.get("Description", "")) and str(row.get(occurrence_key, "")).strip().startswith(str(adjudication["year"])) for row in matches):
                return {"status": "unresolved_occurrence_date", "canonicalApplyAuthorized": False, "proposal": None,
                        "reason": "The structured source occurrence datetime is declared approximate; calendar precision has not been independently adjudicated.", "sourceObservations": observations}
            year = adjudication["year"]
            proposal = {"datePrecision": "year", "dateIso": None, "startDate": f"{year}-01-01", "endDate": f"{year}-12-31"}
            return {"status": "source_supported_date_proposal", "canonicalApplyAuthorized": False, "proposal": proposal,
                    "dateRole": "source_structured_occurrence", "sourceObservations": observations,
                    "calendarPrecisionDecision": {"status": "source_reviewed_year_only", "occurrenceClause": adjudication["occurrenceClause"], "reason": "The matched structured occurrence field and same-report occurrence-year clause agree. The approximate datetime and first-of-month day are not promoted to exact-day evidence."}}
        return {"status": "source_supported_date_proposal", "canonicalApplyAuthorized": False, "proposal": valid[0], "dateRole": "source_structured_occurrence", "sourceObservations": observations}
    return {"status": "unresolved_occurrence_date", "canonicalApplyAuthorized": False, "proposal": None,
            "reason": "Matched occurrence fields are sentinels, absent or contradictory; submission/publication dates and incidental narrative years cannot substitute." if matches else "No independently matched retained underlying source row; direct source review is required.",
            "sourceObservations": observations}


def coordinate_holdout(flags: list[dict], points: list[list], pairs: list[list], context: list[list]) -> dict:
    flag_ids = {str(row["eventId"]) for row in flags}
    point_ids = {str(row[0]) for row in points}
    flagged_points = sorted(flag_ids & point_ids, key=int)
    flagged_pairs = [{"rowIndex": index, "leftEventId": str(row[0]), "rightEventId": str(row[1]), "distanceDecameters": row[2], "dayLag": row[3], "crossSource": row[4]} for index, row in enumerate(pairs) if str(row[0]) in flag_ids or str(row[1]) in flag_ids]
    flagged_context = [{"rowIndex": index, "contextDomainCode": row[0], "contextLaneCode": row[1], "contextId": row[2], "contextClusterId": row[3], "ufoEventId": str(row[5]), "dateRoleCode": row[20]} for index, row in enumerate(context) if str(row[5]) in flag_ids]
    return {
        "policyId": "broad_country_review_bounds_flag_holdout_v1",
        "status": "sensitivity_only_not_coordinate_adjudication",
        "automaticExclusionApplied": False,
        "coordinateCorrections": [],
        "counts": {"reviewFlags": len(flags), "qualifiedEndpoints": len(points), "flaggedQualifiedEndpoints": len(flagged_points), "remainingQualifiedEndpoints": len(points) - len(flagged_points),
                   "pairs": len(pairs), "pairsTouchingFlags": len(flagged_pairs), "remainingPairs": len(pairs) - len(flagged_pairs), "distinctFlaggedPairedEvents": len({event for row in flagged_pairs for event in [row["leftEventId"], row["rightEventId"]] if event in flag_ids}),
                   "contextRows": len(context), "contextRowsTouchingFlags": len(flagged_context), "remainingContextRows": len(context) - len(flagged_context), "distinctFlaggedContextEvents": len({row["ufoEventId"] for row in flagged_context})},
        "qualifiedEndpointExclusionAllowlist": flagged_points,
        "pairExclusionAllowlist": flagged_pairs,
        "contextRowExclusionAllowlist": flagged_context,
        "caveat": "Broad review bounds are not exact country boundaries. These flags do not prove wrong coordinates; this packet permits an explicit sensitivity comparison without changing the primary pool or original records.",
    }


def build_review(data_root: Path, output: Path) -> dict:
    data_root = data_root.resolve()
    quality_root = data_root / "data/releases/quality-20261007"
    map_root, analysis_root = quality_root / "map_delta", quality_root / "analysis_delta"
    manifest_path = map_root / "canonical_web_manifest.json"
    manifest, manifest_receipt = load_json(manifest_path)
    if manifest_receipt["sha256"] != EXPECTED_MANIFEST_SHA256:
        raise ValueError("Source-quality review requires the audited immutable catalog manifest")
    summary_manifest, summary_receipt = load_json(map_root / "summary_manifest.json")
    summaries = {}
    summary_pins = []
    base = data_root / "static_bundle/data/canonical_web"
    for entry in summary_manifest:
        filename = entry["file"]
        candidates = [map_root / "summary_shards" / (filename + ".gz"), map_root / "summary_shards" / filename, base / "summary_shards" / filename]
        path = next((path for path in candidates if path.exists()), None)
        if path is None:
            raise FileNotFoundError(filename)
        rows, receipt = load_json(path)
        if len(rows) != entry["event_count"]:
            raise ValueError(f"Summary count mismatch: {filename}")
        summary_pins.append(receipt)
        summaries.update({str(row["event_id"]): row for row in rows})
    if len(summaries) != manifest["counts"]["events"]:
        raise ValueError("Effective summary corpus count mismatch")
    sentinel_ids = {event_id for event_id, row in summaries.items() if row.get("source") == "phenomenainon_updb" and row.get("sort_date_iso") == "1900-01-01"}
    if len(sentinel_ids) != 178:
        raise ValueError("The audited sentinel candidate set changed")
    spatial_manifest, spatial_receipt = load_json(analysis_root / "analysis_v2/manifest.json")
    coord_manifest, coord_receipt = load_json(analysis_root / "analysis_coordinate_evidence_v1/manifest.json")
    coordinate_rows, coordinate_receipt = load_json(analysis_root / "analysis_coordinate_evidence_v1/coordinate_evidence_projection_v1.json.gz")
    coordinate_entry = coord_manifest["artifacts"]["coordinateEvidenceProjection"]
    if coordinate_receipt["contentSha256"] != coordinate_entry["sha256"]:
        raise ValueError("Coordinate projection SHA mismatch")
    flag_status = coord_manifest["codes"]["status"].index("country_inconsistent")
    flags = [{"eventId": str(row[1]), "catalogRowIndex": row[0], "source": coord_manifest["codes"]["source"][row[2]], "servedLatitude": row[9], "servedLongitude": row[10],
              "qualityStatus": "country_inconsistent", "flagRole": "broad_country_review_bounds_not_mislocation_proof", "locationRaw": summaries[str(row[1])].get("location_raw"), "chunkId": summaries[str(row[1])]["chunk_id"], "detailIndex": summaries[str(row[1])]["detail_index"]} for row in coordinate_rows if row[5] == flag_status]
    if len(flags) != 297:
        raise ValueError("The audited coordinate flag set changed")
    points, point_receipt = pinned_artifact(data_root, analysis_root, "ufoSpatialPoints", spatial_manifest)
    pairs, pair_receipt = pinned_artifact(data_root, analysis_root, "ufoPointNeighbors", spatial_manifest)
    context, context_receipt = pinned_artifact(data_root, analysis_root, "contextUfoNeighbors", spatial_manifest)
    holdout = coordinate_holdout(flags, points, pairs, context)

    # One corpus pass establishes collection lineage for retained canonical
    # events and preserves source-role evidence for every sentinel candidate.
    lineage_counts = Counter()
    lineage_names = defaultdict(Counter)
    sentinel_details = {}
    detail_pins = []
    structured_forms = Counter()
    for chunk_path in sorted((base / "event_chunks").glob("chunk_*.json")):
        rows, receipt = load_json(chunk_path)
        detail_pins.append(receipt)
        for index, event in enumerate(rows):
            event_id = str(event["event_id"])
            if event_id not in summaries or event.get("source") != "phenomenainon_updb":
                continue
            raw = event.get("raw_source_row") or {}
            source_code = str(raw.get("source", ""))
            source_name = str(raw.get("name", "Unknown")).strip()
            lineage_counts[source_code] += 1
            lineage_names[source_code][source_name] += 1
            description = str(raw.get("description", ""))
            structured_forms["durationFormRecords"] += bool(re.search(r"(?:^|\n)Duration:", description))
            structured_forms["shapeFormRecords"] += bool(re.search(r"(?:^|\n)Shape:", description))
            if event_id in sentinel_ids:
                summary = summaries[event_id]
                if summary["chunk_id"] != chunk_path.stem or summary["detail_index"] != index:
                    raise ValueError("Current summary/detail identity mismatch")
                sentinel_details[event_id] = {"event": event, "raw": raw, "locator": {"path": str(chunk_path), "sha256": receipt["sha256"], "detailIndex": index}}
    if len(sentinel_details) != len(sentinel_ids) or sum(lineage_counts.values()) != 161029:
        raise ValueError("Retained UPDB identity/count mismatch")
    needed_native_ids = defaultdict(set)
    for candidate in sentinel_details.values():
        family = str(candidate["raw"].get("name", "")).strip().upper()
        if family in {"NUFORC", "MUFON"}:
            needed_native_ids[family].add(normalize_native_id(candidate["raw"].get("source_id")))
    underlying_rows = defaultdict(list)
    underlying_receipts = []
    for family, filenames in {"NUFORC": ["nuforc.csv", "nuforcpy.csv"], "MUFON": ["mufon.csv", "mufonpy.csv"]}.items():
        if not needed_native_ids[family]:
            continue
        for filename in filenames:
            path = data_root / "UFO Databases" / filename
            with path.open("rb") as handle:
                digest = hashlib.file_digest(handle, "sha256").hexdigest()
            underlying_receipts.append({"path": str(path), "bytes": path.stat().st_size, "sha256": digest, "family": family})
            with path.open(encoding="utf-8-sig", newline="") as handle:
                for row_number, row in enumerate(csv.DictReader(handle), 2):
                    native_id = normalize_native_id(row.get("No"))
                    if native_id in needed_native_ids[family]:
                        underlying_rows[(family, native_id)].append(dict(row, _file=str(path), _row=row_number))
    queue = []
    for event_id in sorted(sentinel_details, key=lambda value: (value not in PRIORITY_EVENT_IDS, int(value))):
        candidate = sentinel_details[event_id]
        event, raw = candidate["event"], candidate["raw"]
        family = str(raw.get("name", "")).strip().upper()
        native_id = normalize_native_id(raw.get("source_id"))
        decision = adjudicate_sentinel(raw, underlying_rows.get((family, native_id), []), family) if family in {"NUFORC", "MUFON"} else {"status": "unresolved_occurrence_date", "canonicalApplyAuthorized": False, "proposal": None, "reason": "No structured independently matched occurrence field was available in this bounded source family review.", "sourceObservations": []}
        queue.append({"eventId": event_id, "canonicalEventId": event.get("canonical_event_id"), "updbNativeId": event.get("source_id"), "underlyingSourceCode": raw.get("source"), "underlyingSourceName": family, "underlyingNativeId": raw.get("source_id"), "currentDateIso": summaries[event_id].get("sort_date_iso"), "currentDatePrecision": summaries[event_id].get("date_precision"), "rawUpdbDate": raw.get("date"), "locationRaw": event.get("location_raw"), "priorityNamedAuditExample": event_id in PRIORITY_EVENT_IDS, "sourceRecordLocator": candidate["locator"], "sourceNarrativeSha256": sha256(str(raw.get("description", "")).encode()), **decision})

    boundary_path = data_root / "webapp/static_public/data/world_countries.geojson"
    boundary, boundary_receipt = load_json(boundary_path)
    historical_path = data_root / "campaign/analysis_improvement/waves/wave-008-country-admin-provenance/provenance_audit.json"
    historical, historical_receipt = load_json(historical_path)
    boundary_metadata = spatial_manifest["sources"]["ufoGeography"]["worldCountries"]
    if boundary_receipt["sha256"] != boundary_metadata["sha256"]:
        raise ValueError("Current boundary SHA differs from audited metadata")
    feature_ids = Counter(str(feature.get("id")) for feature in boundary["features"])
    boundary_review = {"status": "authoritative_derivative_provenance_unresolved", "currentArtifact": boundary_receipt, "releaseMetadata": boundary_metadata,
        "featureCount": len(boundary["features"]), "uniqueFeatureIds": len(feature_ids), "duplicateFeatureIds": sorted(key for key, count in feature_ids.items() if count > 1),
        "historicalExactUpstreamMatch": historical["boundedExternalIdentityCheck"]["exactUpstreamMatch"],
        "currentPrimarySourceChecks": [{"url": "https://github.com/johan/world.geo.json", "checkedOn": "2026-10-07", "finding": "Upstream README continues to warn that dataset legal status is dubious and recommends attributable alternative sources."}, {"url": "https://www.naturalearthdata.com/about/terms-of-use/", "checkedOn": "2026-10-07", "finding": "Official Natural Earth data are public domain; this does not establish derivation or a specific authoritative version for this exact derivative."}],
        "migrationPerformed": False, "requiredUnblock": historical["decision"]["requiredFutureUnblock"], "historicalEvidence": historical_receipt}
    counts = Counter(row["status"] for row in queue)
    lineage = {"status": "collection_lineage_sensitivity_metadata", "retainedUpdbRecords": sum(lineage_counts.values()), "families": [{"sourceCode": code, "sourceNames": dict(lineage_names[code]), "records": count} for code, count in sorted(lineage_counts.items(), key=lambda entry: int(entry[0] or 0))],
        "mufonDerivedRecords": lineage_counts["1"], "nuforcDerivedRecords": lineage_counts["2"], "mufonOrNuforcDerivedRecords": lineage_counts["1"] + lineage_counts["2"],
        "sensitivityPolicy": "Treat collection identity and underlying source family as separate dimensions. A collection holdout is not an independent-source holdout when it retains the same underlying source family.", "duplicateIncidentsEstablished": False, "sourceFamilyInferencePromotion": False, "structuredSourceFormLeads": dict(structured_forms)}
    result = {"schemaId": "analysis-source-quality-review-v1", "status": "bounded_review_complete", "catalogRows": len(summaries), "canonicalDataMutated": False, "runtimeGatesChanged": False,
        "scope": {"sentinelCandidates": len(queue), "dateProposals": counts["source_supported_date_proposal"], "unresolvedOccurrenceDates": counts["unresolved_occurrence_date"], "coordinateFlags": len(flags), "approvedCoordinateRepairs": 0, "authoritativeBoundaryMigration": False},
        "inputs": [manifest_receipt, summary_receipt, spatial_receipt, coord_receipt, coordinate_receipt, point_receipt, pair_receipt, context_receipt, *underlying_receipts],
        "summaryShardPins": summary_pins, "detailChunkPins": detail_pins, "lineage": lineage, "sentinelDateReview": queue, "coordinateReviewFlags": flags, "coordinateSensitivity": holdout, "boundaryProvenance": boundary_review,
        "externalAccessLimits": {"nuforcPrimaryPages": "Current and legacy URLs for audit priority reports64886,16647,160488 were inaccessible to the web tool. Frozen local source rows were reviewed; no present-day primary-page occurrence assertion was established."},
        "retention": "Retain this small unique review packet with its builder. Rebuild against the declared shared inputs; no corpus, staging tree or rollback copy is created."}
    output.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode()
    if len(raw) > 3 * 1024 * 1024:
        raise ValueError("Review packet exceeds the documented small-artifact budget")
    report_path = output / "source_quality_review.json"
    report_path.write_bytes(raw)
    (output / "PURPOSE.txt").write_text("Purpose: read-only A12/A13/A15 source-quality adjudication and explicit sensitivity allowlists.\nProvenance: immutable catalog, coordinate/spatial pins and streamed retained source records recorded in source_quality_review.json.\nRebuild: run scripts/build_analysis_source_quality_review.py --data-root <shared project root> --output <this directory>.\nRetention: retain this unique small research packet; no accepted canonical corrections, boundary migration or automatic exclusions.\nCurrent validated deployment and known-good rollback remain unchanged. Superseded large artifacts: none. Newly created files >100 MiB: none.\n", encoding="utf-8")
    return {"report": str(report_path), "bytes": len(raw), "scope": result["scope"], "coordinateSensitivityCounts": holdout["counts"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True, help="Existing shared canonical-data project root")
    parser.add_argument("--output", type=Path, required=True, help="Small unique research packet destination")
    args = parser.parse_args()
    print(json.dumps(build_review(args.data_root, args.output), indent=2))


if __name__ == "__main__":
    main()

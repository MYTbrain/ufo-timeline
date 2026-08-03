from __future__ import annotations

import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

from parser.packed_points import export_packed_points


REPO_ROOT = Path(__file__).resolve().parents[1]
STATIC_ROOT = REPO_ROOT / "webapp" / "static_public"
ANALYSIS_ROOT = STATIC_ROOT / "data" / "analysis_v2"
BUILDER_PATH = REPO_ROOT / "scripts" / "build_analysis_v2_artifacts.py"


def load_builder():
    spec = importlib.util.spec_from_file_location("analysis_v2_artifact_builder", BUILDER_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


BUILDER = load_builder()


def manifest() -> dict:
    return json.loads((ANALYSIS_ROOT / "manifest.json").read_text(encoding="utf-8"))


def artifact_rows(name: str) -> tuple[list, list[str]]:
    declaration = manifest()["artifacts"][name]
    path = STATIC_ROOT / declaration["file"]
    return json.loads(path.read_text(encoding="utf-8")), declaration["rowSchema"]


def decoded_label(artifact: str, field: str, code: int) -> str:
    return manifest()["codes"][artifact][field.removesuffix("Code")][code]


def test_frozen_manifest_is_evidence_gated_and_pins_current_releases() -> None:
    value = manifest()

    assert value["schemaVersion"] == 2
    assert value["schemaId"] == "ufo-timeline-analysis-evidence-artifacts-v2.0.0"
    assert value["releaseId"] == "analysis-evidence-lab-v2-20260803"
    assert value["counts"] == {
        "animalContextRecords": 1177,
        "animalKilometerEligible": 0,
        "cropContextRecords": 7745,
        "cropKilometerEligible": 0,
        "facilityMarkers": 1800,
        "facilityInferentialEligible": 70,
        "relationshipRows": 1804,
        "relationshipAssociationEligible": 0,
        "ufoNeighborEligiblePoints": 33801,
        "ufoNeighborPairs": 42575,
    }
    assert value["sources"]["cropContext"]["releaseId"] == "crop-circles-v156-20260731"
    assert value["sources"]["animalContext"]["releaseId"] == "animal-mutilations-v1-20260802"
    assert value["sources"]["relationshipPackage"]["sha256"] == (
        "18e3a451872793d02018fda961e5eda17d62bba18cea088b63a4033c9d715d2c"
    )
    assert value["policy"] == {
        "authenticityAssessments": False,
        "causalInferences": False,
        "chronologySegmentsRead": False,
        "contextProximityFailClosed": True,
        "generalizedCoordinatesKilometerEligible": False,
        "minimumContextEligibleRecordsForInference": 25,
        "pointNeighborhoodsOnly": True,
        "traceMetrics": False,
        "travelMetrics": False,
    }
    neighbor_source = value["sources"]["ufoPointNeighbors"]
    assert neighbor_source["policy"]["chronologySegmentsRead"] is False
    assert set(neighbor_source) == {
        "counts",
        "exclusions",
        "pointsBinary",
        "pointsMetadata",
        "policy",
        "readiness",
    }
    assert neighbor_source["readiness"] == {
        "eligiblePointCount": 33801,
        "eligiblePointsBySource": {"majestic": 8844, "ufocat": 24957},
        "status": "qualified_candidate_pool",
        "warnings": [
            "eligible_source_coordinates_are_currently_limited_to_majestic_and_ufocat",
            "source_balancing_and_leave_one_source_out_sensitivity_required",
            "point_neighborhood_association_is_not_observed_travel",
        ],
    }
    assert all("trace" not in declaration["label"].casefold() for declaration in (
        neighbor_source["pointsBinary"],
        neighbor_source["pointsMetadata"],
    ))


def test_artifacts_are_hashed_compact_decodable_and_deterministically_gzipped() -> None:
    value = manifest()
    for declaration in value["artifacts"].values():
        raw = (STATIC_ROOT / declaration["file"]).read_bytes()
        compressed = (STATIC_ROOT / declaration["gzipFile"]).read_bytes()
        assert len(raw) == declaration["bytes"]
        assert len(compressed) == declaration["gzipBytes"]
        assert hashlib.sha256(raw).hexdigest() == declaration["sha256"]
        assert hashlib.sha256(compressed).hexdigest() == declaration["gzipSha256"]
        assert compressed[4:8] == b"\x00\x00\x00\x00"
        assert gzip.decompress(compressed) == raw
        rows = json.loads(raw)
        assert len(rows) == declaration["rowCount"]
        assert all(len(row) == len(declaration["rowSchema"]) for row in rows)

    snapshot = value["sources"]["relationshipSourceSnapshot"]
    raw_snapshot = (STATIC_ROOT / snapshot["file"]).read_bytes()
    assert hashlib.sha256(raw_snapshot).hexdigest() == snapshot["sha256"]
    lowered = raw_snapshot.lower()
    assert b"http" not in lowered
    assert b"source_records" not in lowered
    assert b"distance_km" not in lowered
    assert b"review_notes" not in lowered


def test_context_readiness_never_promotes_generalized_or_catalog_markers() -> None:
    crop_rows, crop_schema = artifact_rows("cropContextReadiness")
    crop_evidence = crop_schema.index("coordinateEvidenceCode")
    crop_eligible = crop_schema.index("kilometerEligible")
    crop_counts: dict[str, int] = {}
    for row in crop_rows:
        label = decoded_label("cropContextReadiness", "coordinateEvidenceCode", row[crop_evidence])
        crop_counts[label] = crop_counts.get(label, 0) + 1
    assert crop_counts == {
        "candidate_field_marker": 409,
        "exact_source_coordinate": 10,
        "locality_centroid": 3886,
        "unmapped": 3440,
    }
    assert not any(row[crop_eligible] for row in crop_rows)

    animal_rows, animal_schema = artifact_rows("animalContextReadiness")
    animal_evidence = animal_schema.index("coordinateEvidenceCode")
    animal_eligible = animal_schema.index("kilometerEligible")
    animal_counts: dict[str, int] = {}
    for row in animal_rows:
        label = decoded_label("animalContextReadiness", "coordinateEvidenceCode", row[animal_evidence])
        animal_counts[label] = animal_counts.get(label, 0) + 1
    assert animal_counts == {"generalized_public_marker": 518, "unmapped": 659}
    assert not any(row[animal_eligible] for row in animal_rows)


def test_facility_projection_separates_qualified_markers_from_claims() -> None:
    rows, schema = artifact_rows("facilityAnalysis")
    class_index = schema.index("classCode")
    coordinate_confidence_index = schema.index("coordinateConfidenceCode")
    temporal_confidence_index = schema.index("temporalConfidenceCode")
    intervals_index = schema.index("activeIntervals")
    eligible_index = schema.index("inferentialEligible")
    reasons_index = schema.index("exclusionReasonCodes")
    classes: dict[str, int] = {}
    eligible = 0
    for row in rows:
        facility_class = decoded_label("facilityAnalysis", "classCode", row[class_index])
        classes[facility_class] = classes.get(facility_class, 0) + 1
        if row[eligible_index]:
            eligible += 1
            assert facility_class in {"military", "research_test"}
            assert decoded_label(
                "facilityAnalysis", "coordinateConfidenceCode", row[coordinate_confidence_index]
            ) in {"medium", "high"}
            assert decoded_label(
                "facilityAnalysis", "temporalConfidenceCode", row[temporal_confidence_index]
            ) in {"medium", "high"}
            assert row[intervals_index]
            assert row[reasons_index] == []
        if facility_class == "claimed_ufo_base":
            assert row[eligible_index] is False
    assert classes == {"claimed_ufo_base": 11, "military": 1577, "research_test": 212}
    assert eligible == 70


def test_neighbor_projection_contains_only_unique_bounded_unordered_point_pairs() -> None:
    rows, schema = artifact_rows("ufoPointNeighbors")
    left = schema.index("leftEventId")
    right = schema.index("rightEventId")
    distance = schema.index("distanceDecameters")
    lag = schema.index("dayLag")
    cross_source = schema.index("crossSource")

    assert len(rows) == 42575
    assert len({(row[left], row[right]) for row in rows}) == len(rows)
    assert all(0 <= row[left] < row[right] <= 2**53 - 1 for row in rows)
    assert all(0 <= row[distance] <= 10_000 for row in rows)
    assert all(0 <= row[lag] <= 30 for row in rows)
    assert sum(row[cross_source] for row in rows) == 16913
    assert rows == sorted(rows, key=lambda row: (row[left], row[right], row[distance], row[lag]))

    counts = manifest()["sources"]["ufoPointNeighbors"]["counts"]
    assert counts == {
        "coordinatePileRowsExcluded": 5247,
        "coordinatePilesExcluded": 210,
        "crossSourcePairs": 16913,
        "eligibleBeforePileExclusion": 39048,
        "eligiblePoints": 33801,
        "packedRows": 580783,
        "pairs": 42575,
        "pairsWithin25Km7Days": 6703,
        "pairsWithin50Km7Days": 10702,
    }


def test_neighbor_builder_handles_dateline_and_excludes_coordinate_piles(tmp_path: Path) -> None:
    events = []
    for event_id in range(1, 11):
        events.append({
            "event_id": event_id,
            "lat": 40.0,
            "lon": -105.0,
            "date_iso": "2000-01-01",
            "sort_date_iso": "2000-01-01",
            "source": "ufocat",
            "craft_type_inferred": "disc_saucer",
            "craft_type_confidence": "high",
            "same_day_match_strength": "strong",
            "date_precision": "exact_day",
            "location_precision": "exact_coords",
            "coordinate_source": "raw_latlong",
        })
    for event_id, lon, source in ((11, 179.9, "ufocat"), (12, -179.9, "majestic")):
        events.append({
            "event_id": event_id,
            "lat": 0.0,
            "lon": lon,
            "date_iso": "2000-01-01",
            "sort_date_iso": "2000-01-01",
            "source": source,
            "craft_type_inferred": "triangle",
            "craft_type_confidence": "medium",
            "same_day_match_strength": "medium",
            "date_precision": "exact_day",
            "location_precision": "exact_coords",
            "coordinate_source": "raw_latlong",
        })
    export_packed_points(events, tmp_path)

    rows, source = BUILDER.build_neighbor_projection(tmp_path)

    assert source["counts"]["eligibleBeforePileExclusion"] == 12
    assert source["counts"]["coordinatePileRowsExcluded"] == 10
    assert source["counts"]["eligiblePoints"] == 2
    assert rows == [[11, 12, 2224, 0, True]]


def test_relationship_reconciliation_uses_lineage_and_quarantines_unresolved_rows() -> None:
    value = manifest()
    counts = value["sources"]["relationshipReconciliation"]["counts"]
    assert counts == {
        "associationEligible": 0,
        "quarantinedObject": 24,
        "quarantinedSubject": 460,
        "reconciledCurrent": 1069,
        "reconciledUnmappedUfo": 251,
        "rows": 1804,
        "sourceInputIds": 1670,
        "sourceInputIdsReconciled": 1670,
    }
    policy = value["sources"]["relationshipReconciliation"]["policy"]
    assert policy["canonicalEventIdStringSimilarityUsed"] is False
    assert policy["reconciliationKey"] == "canonical_input_lineage"
    assert policy["unresolvedRelationshipsQuarantined"] is True

    rows, schema = artifact_rows("relationshipReconciliation")
    eligible = schema.index("associationEligible")
    current_id = schema.index("currentUfoEventId")
    assert not any(row[eligible] for row in rows)
    assert all(
        row[current_id] is None or 0 <= row[current_id] <= 2**53 - 1
        for row in rows
    )


def test_uncertainty_classification_and_distance_are_boundary_safe() -> None:
    assert BUILDER.classify_uncertain_distance(5, 1, 1, 10) == "near"
    assert BUILDER.classify_uncertain_distance(20, 2, 2, 10) == "far"
    assert BUILDER.classify_uncertain_distance(10, 2, 2, 10) == "ambiguous"
    assert 22.0 < BUILDER.haversine_km(0, 179.9, 0, -179.9) < 22.3
    assert BUILDER.haversine_km(89.9, 170, 89.9, -170) < 4.0


def test_builder_regenerates_frozen_analysis_v2_byte_for_byte(tmp_path: Path) -> None:
    output = tmp_path / "analysis_v2"
    rebuilt = BUILDER.build(output_root=output)

    assert rebuilt == manifest()
    frozen_files = sorted(path.name for path in ANALYSIS_ROOT.iterdir() if path.is_file())
    assert frozen_files
    assert frozen_files == sorted(path.name for path in output.iterdir() if path.is_file())
    for filename in frozen_files:
        assert (output / filename).read_bytes() == (ANALYSIS_ROOT / filename).read_bytes()

from __future__ import annotations

import gzip
import hashlib
import importlib.util
import json
from functools import lru_cache
from pathlib import Path
import struct
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


@lru_cache(maxsize=1)
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
    assert value["schemaId"] == "ufo-timeline-analysis-evidence-artifacts-v2.2.0"
    assert value["releaseId"] == "analysis-evidence-lab-v2.2-20260803"
    assert value["manifestVersion"] == "2.2.0"
    assert value["counts"] == {
        "animalContextRecords": 1177,
        "animalKilometerEligible": 0,
        "animalPublicMarkerAnalysisRecords": 339,
        "contextIndependentObservedRows": 12180,
        "contextLocationDateClusters": 3892,
        "contextObservedNeighborRows": 12596,
        "contextUfoNeighborRows": 63753,
        "cropBoundedAnalysisRecords": 406,
        "cropContextRecords": 7745,
        "cropKilometerEligible": 0,
        "cropLocalityAnalysisRecords": 3249,
        "facilityMarkers": 1800,
        "facilityInferentialEligible": 70,
        "relationshipRows": 1804,
        "relationshipAssociationEligible": 0,
        "ufoNeighborEligiblePoints": 33801,
        "ufoNeighborPairs": 42575,
        "ufoConfigurationNeighborPairs": 2012,
        "ufoConfigurationPoints": 1270,
        "ufoGeographyCountryAssigned": 561658,
        "ufoGeographyRows": 580783,
        "ufoSpatialPoints": 33801,
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
        "roughMarkerAnalysisEnabled": True,
        "roughMarkerAssociationInferenceEligible": True,
        "roughMarkerDefiniteNearEligible": False,
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
    readiness = neighbor_source["readiness"]
    assert readiness["eligiblePointCount"] == 33801
    assert readiness["eligiblePointsBySource"] == {"majestic": 8844, "ufocat": 24957}
    assert readiness["status"] == "qualified_candidate_pool"
    assert [gate["gateId"] for gate in readiness["gates"]] == [
        "ufo_neighbor_source_coordinates",
        "ufo_neighbor_exact_day",
        "ufo_neighbor_craft_confidence",
        "ufo_neighbor_same_day_suitability",
        "ufo_neighbor_recognized_craft",
        "ufo_neighbor_coordinate_piles",
    ]
    assert readiness["warnings"] == [
        "eligible_source_coordinates_are_currently_limited_to_majestic_and_ufocat",
        "source_balancing_and_leave_one_source_out_sensitivity_required",
        "point_neighborhood_association_is_not_observed_travel",
    ]
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


def test_manifest_pins_estimator_artifact_releases_ordering_and_contract_hashes() -> None:
    value = manifest()

    assert value["estimatorVersion"] == BUILDER.ESTIMATOR_VERSION == (
        "ufo-analysis-evidence-lab-v2.2.0"
    )
    assert set(BUILDER.ARTIFACT_CONTRACTS) == set(value["artifacts"])
    assert value["artifactReleases"] == {
        artifact_key: declaration["releaseId"]
        for artifact_key, declaration in sorted(value["artifacts"].items())
    }
    assert value["rowOrderingHashes"] == {
        artifact_key: declaration["rowOrdering"]["sha256"]
        for artifact_key, declaration in sorted(value["artifacts"].items())
    }

    for artifact_key, declaration in value["artifacts"].items():
        contract = BUILDER.ARTIFACT_CONTRACTS[artifact_key]
        assert declaration["artifactId"] == contract["artifactId"]
        assert declaration["releaseId"] == (
            f'{value["releaseId"]}.{contract["artifactId"]}'
        )
        rows = json.loads((STATIC_ROOT / declaration["file"]).read_text(encoding="utf-8"))
        assert declaration["rowOrdering"] == BUILDER.row_ordering_declaration(
            rows,
            declaration["rowSchema"],
            contract["orderingFields"],
            policy_id=contract["orderingPolicyId"],
        )
        assert len(declaration["rowOrdering"]["sha256"]) == 64

    dictionaries = value["dictionaries"]
    assert dictionaries["codebooksPath"] == "#/codes"
    assert dictionaries["encoding"] == "zero_based_integer_index_into_manifest_codebook"
    assert dictionaries["sha256"] == BUILDER.sha256_bytes(
        BUILDER.canonical_json_bytes(value["codes"])
    )
    assert dictionaries["artifactSha256"] == {
        artifact_key: BUILDER.sha256_bytes(BUILDER.canonical_json_bytes(codebook))
        for artifact_key, codebook in sorted(value["codes"].items())
    }
    assert value["contractHashes"] == {
        "artifactDeclarationsSha256": BUILDER.sha256_bytes(
            BUILDER.canonical_json_bytes(value["artifacts"])
        ),
        "dictionaryCodebooksSha256": dictionaries["sha256"],
        "rootPolicySha256": BUILDER.sha256_bytes(
            BUILDER.canonical_json_bytes(value["policy"])
        ),
    }

    snapshot = value["sources"]["relationshipSourceSnapshot"]
    snapshot_rows = json.loads((STATIC_ROOT / snapshot["file"]).read_text(encoding="utf-8"))
    snapshot_contract = BUILDER.RELATIONSHIP_SNAPSHOT_CONTRACT
    assert snapshot["artifactId"] == snapshot_contract["artifactId"]
    assert snapshot["releaseId"] == (
        f'{value["releaseId"]}.{snapshot_contract["artifactId"]}'
    )
    assert snapshot["rowOrdering"] == BUILDER.row_ordering_declaration(
        snapshot_rows,
        snapshot["rowSchema"],
        snapshot_contract["orderingFields"],
        policy_id=snapshot_contract["orderingPolicyId"],
    )
    snapshot_metadata = value["sources"]["relationshipSourceSnapshotMetadata"]
    assert snapshot_metadata["artifactId"] == (
        BUILDER.RELATIONSHIP_SNAPSHOT_METADATA_ARTIFACT_ID
    )
    assert snapshot_metadata["releaseId"] == (
        f'{value["releaseId"]}.{BUILDER.RELATIONSHIP_SNAPSHOT_METADATA_ARTIFACT_ID}'
    )

    def assert_declaration_hashes(item: object) -> None:
        if isinstance(item, dict):
            if "bytes" in item and ("file" in item or "label" in item):
                assert len(str(item.get("sha256", ""))) == 64
            for child in item.values():
                assert_declaration_hashes(child)
        elif isinstance(item, list):
            for child in item:
                assert_declaration_hashes(child)

    assert_declaration_hashes(value["artifacts"])
    assert_declaration_hashes(value["sources"])


def test_row_ordering_hash_is_deterministic_and_order_sensitive() -> None:
    schema = ["eventId", "label", "value"]
    rows = [[10, "a", 2], [20, "b", 1]]
    first = BUILDER.row_ordering_declaration(
        rows,
        schema,
        ("eventId", "label"),
        policy_id="fixture_order_v1",
    )
    repeated = BUILDER.row_ordering_declaration(
        rows,
        schema,
        ("eventId", "label"),
        policy_id="fixture_order_v1",
    )
    reversed_rows = BUILDER.row_ordering_declaration(
        list(reversed(rows)),
        schema,
        ("eventId", "label"),
        policy_id="fixture_order_v1",
    )
    assert first == repeated
    assert first["sha256"] != reversed_rows["sha256"]
    assert first["sha256"] == BUILDER.sha256_bytes(b"[[10,\"a\"],[20,\"b\"]]")


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


def test_context_analysis_lanes_publish_the_locked_candidate_counts() -> None:
    crops, crop_source = BUILDER.build_crop_context_projection(BUILDER.STATIC_DATA_ROOT)
    animals, animal_source, _incident_map = BUILDER.build_animal_context_projection(
        BUILDER.STATIC_DATA_ROOT
    )

    assert sum(row["analysisLaneCode"] == "crop_bounded" for row in crops) == 406
    assert sum(row["analysisLaneCode"] == "crop_locality" for row in crops) == 3249
    assert sum(row["analysisLaneCode"] == "animal_public_marker" for row in animals) == 339
    assert crop_source["policy"]["candidateMarkersBoundedAnalysisEligible"] is True
    assert crop_source["policy"]["catalogDatesSubstituteForFormationDates"] is False
    assert animal_source["policy"]["generalizedPublicMarkersRoughAnalysisEligible"] is True
    assert animal_source["policy"]["generalizedPublicMarkersDefiniteNearEligible"] is False


def test_context_neighbors_keep_origin_and_publisher_exclusions_auditable() -> None:
    ordinal = BUILDER.date(2000, 1, 1).toordinal()
    points = [
        {
            "eventId": 1, "lat": 0.0, "lon": 0.0, "ordinal": ordinal, "sourceCode": "source-a",
            "craftCode": "triangle", "fineSpatialStratumCode": "fine-a",
            "coarseSpatialStratumCode": "coarse-a",
        },
        {
            "eventId": 2, "lat": 0.0, "lon": 0.1, "ordinal": ordinal, "sourceCode": "source-b",
            "craftCode": "disc_saucer", "fineSpatialStratumCode": "fine-a",
            "coarseSpatialStratumCode": "coarse-a",
        },
    ]
    animals = [{
        "id": "animal-1", "lat": 0.0, "lon": 0.0, "startOrdinal": ordinal,
        "analysisLaneCode": "animal_public_marker", "featureGroupCode": "bovine",
        "locationDateClusterId": "cluster-1", "coordinateUncertaintyKm": None,
        "originUfoEventIds": [1], "originPublisherCodes": ["source-a"],
    }]

    rows, source = BUILDER.build_context_ufo_neighbor_projection(points, [], animals)
    observed = [row for row in rows if row["dateRoleCode"] == "observed_reported_date"]
    assert len(observed) == 2
    origin = next(row for row in observed if row["ufoEventId"] == 1)
    independent = next(row for row in observed if row["ufoEventId"] == 2)
    assert origin["originUfoExcluded"] is True
    assert origin["originPublisherExcluded"] is True
    assert origin["independentAssociationEligible"] is False
    assert independent["independentAssociationEligible"] is True
    assert independent["uncertaintyClassCode"] == "public_marker_ambiguous"
    assert source["counts"]["originExclusions"] == {
        "origin_publisher": 1,
        "origin_ufo_event": 1,
    }
    assert source["policy"]["chronologySegmentsRead"] is False
    repeated_rows, repeated_source = BUILDER.build_context_ufo_neighbor_projection(points, [], animals)
    assert (rows, source) == (repeated_rows, repeated_source)


def test_v22_packed_spatial_schemas_are_versioned_and_decision_complete() -> None:
    assert BUILDER.DEFAULT_RELEASE_ID == "analysis-evidence-lab-v2.2-20260803"
    assert BUILDER.SCHEMA_ID == "ufo-timeline-analysis-evidence-artifacts-v2.2.0"
    assert BUILDER.UFO_SPATIAL_POINT_ROW_SCHEMA == [
        "eventId", "lat", "lon", "ordinal", "year", "sourceCode", "craftCode",
        "craftConfidenceCode", "sameDayMatchStrengthCode", "coordinateEvidenceCode",
        "coordinatePileGroup", "coordinatePileCount", "fineSpatialStratumCode",
        "coarseSpatialStratumCode", "fiveYearBand", "decade", "duplicateLineageCode",
    ]
    assert BUILDER.CONTEXT_UFO_NEIGHBOR_ROW_SCHEMA[-4:] == [
        "originUfoExcluded", "originPublisherExcluded", "independentAssociationEligible",
        "dateRoleCode",
    ]
    assert "contextClusterId" in BUILDER.CONTEXT_UFO_NEIGHBOR_ROW_SCHEMA
    assert "uncertaintyClassCode" in BUILDER.CONTEXT_UFO_NEIGHBOR_ROW_SCHEMA
    assert BUILDER.UFO_GEOGRAPHY_ROW_SCHEMA == [
        "pointRowIndex", "eventId", "countryCode", "macroregionCode",
        "assignmentSourceCode", "assignmentConfidenceCode", "boundaryStatusCode",
        "coordinateEvidenceCode",
    ]
    assert BUILDER.UFO_CONFIGURATION_POINT_ROW_SCHEMA == [
        "eventId", "lat", "lon", "ordinal", "year", "sourceCode", "configurationCode",
        "configurationConfidenceCode", "configurationSourceCode", "sameDayMatchStrengthCode",
        "coordinateEvidenceCode", "coordinatePileGroup", "coordinatePileCount",
        "fineSpatialStratumCode", "coarseSpatialStratumCode", "fiveYearBand", "decade",
        "duplicateLineageCode",
    ]


def test_v22_geography_projection_is_row_aligned_decodable_and_fail_closed() -> None:
    value = manifest()
    rows, schema = artifact_rows("ufoGeography")
    assert schema == BUILDER.UFO_GEOGRAPHY_ROW_SCHEMA
    assert len(rows) == 580783
    row_index = schema.index("pointRowIndex")
    event_id = schema.index("eventId")
    country = schema.index("countryCode")
    macroregion = schema.index("macroregionCode")
    boundary = schema.index("boundaryStatusCode")
    coordinate_evidence = schema.index("coordinateEvidenceCode")
    codes = value["codes"]["ufoGeography"]
    metadata = json.loads(
        (REPO_ROOT / "data" / "canonical_web" / "points_meta.json").read_text(encoding="utf-8")
    )
    row_struct = struct.Struct(metadata["struct_format"])
    event_id_field = next(
        index for index, field in enumerate(metadata["fields"]) if field["name"] == "event_id"
    )
    packed_rows = row_struct.iter_unpack(
        (REPO_ROOT / "data" / "canonical_web" / "points.bin").read_bytes()
    )
    for index, (projection_row, packed_row) in enumerate(zip(rows, packed_rows, strict=True)):
        assert projection_row[row_index] == index
        assert projection_row[event_id] == packed_row[event_id_field]
    assert value["sources"]["ufoGeography"]["policy"]["rowOrder"] == (
        "packed_points_input_order_mapped_catalog_subsequence"
    )
    assert value["sources"]["ufoGeography"]["policy"]["runtimeVerification"] == (
        "contiguous_point_row_index_and_event_id_fail_closed"
    )
    assert value["sources"]["ufoGeography"]["counts"] == {
        "rows": 580783,
        "uniqueCoordinateMarkers": 85136,
        "countryAssigned": 561658,
        "countryUnknown": 19125,
        "byBoundaryStatus": {
            "inside_country": 561657,
            "on_boundary": 1,
            "outside_country_boundaries": 19088,
            "overlapping_boundaries": 37,
        },
        "byMacroregion": {
            "africa": 1894,
            "antarctica": 8,
            "asia": 4868,
            "europe": 42230,
            "latin_america_caribbean": 10479,
            "northern_america": 491890,
            "oceania": 10289,
            "unknown": 19125,
        },
    }
    assert {
        codes["coordinateEvidence"][row[coordinate_evidence]]
        for row in rows
    } == {"generalized_coordinates", "source_coordinates"}
    for row in rows:
        country_label = codes["country"][row[country]]
        macroregion_label = codes["macroregion"][row[macroregion]]
        boundary_label = codes["boundaryStatus"][row[boundary]]
        if boundary_label in {"outside_country_boundaries", "overlapping_boundaries"}:
            assert country_label == "unknown"
            assert macroregion_label == "unknown"
    world = value["sources"]["ufoGeography"]["worldCountries"]
    assert world["featureCount"] == 180
    assert world["geometryCounts"] == {"MultiPolygon": 30, "Polygon": 150}
    assert world["releaseId"] == "world-countries-geojson-sha256-bc2356a26a2976f9"
    assert world["sha256"] == "bc2356a26a2976f98e4aaf1b24c5693d5a4dc9b6178aeb952dbafbcd42c73bcd"


def test_world_country_assignment_handles_interiors_boundaries_and_unknown_space() -> None:
    west = [[[-10, -10], [0, -10], [0, 10], [-10, 10], [-10, -10]]]
    east = [[[0, -10], [10, -10], [10, 10], [0, 10], [0, -10]]]
    parts = [
        {"country": "West", "polygon": west},
        {"country": "East", "polygon": east},
    ]
    buckets = {
        (18, 35): (0,),
        (18, 36): (0, 1),
        (18, 37): (1,),
        (18, 38): (),
    }
    macroregions = {"West": "west_region", "East": "east_region"}
    assert BUILDER.assign_world_country(0, -5, parts, buckets, macroregions) == (
        "West", "west_region", "world_country_polygon", "high", "inside_country"
    )
    assert BUILDER.assign_world_country(0, 0, parts, buckets, macroregions) == (
        "unknown", "unknown", "world_country_boundary_ambiguous", "none",
        "overlapping_boundaries",
    )
    assert BUILDER.assign_world_country(0, 12, parts, buckets, macroregions) == (
        "unknown", "unknown", "unassigned_ocean_or_boundary_gap", "none",
        "outside_country_boundaries",
    )


def test_v22_configuration_points_and_neighbors_are_separate_from_dumbbell_craft() -> None:
    value = manifest()
    points, point_schema = artifact_rows("ufoConfigurationPoints")
    neighbors, neighbor_schema = artifact_rows("ufoConfigurationNeighbors")
    assert point_schema == BUILDER.UFO_CONFIGURATION_POINT_ROW_SCHEMA
    assert neighbor_schema == BUILDER.NEIGHBOR_ROW_SCHEMA
    assert len(points) == 1270
    assert len(neighbors) == 2012
    point_event = point_schema.index("eventId")
    configuration = point_schema.index("configurationCode")
    pile_count = point_schema.index("coordinatePileCount")
    configuration_ids = {row[point_event] for row in points}
    assert len(configuration_ids) == len(points)
    assert {
        decoded_label("ufoConfigurationPoints", "configurationCode", row[configuration])
        for row in points
    } == {"formation"}
    assert "dumbbell_barbell" not in value["codes"]["ufoConfigurationPoints"]["configuration"]
    assert all(1 <= row[pile_count] < 10 for row in points)
    left = neighbor_schema.index("leftEventId")
    right = neighbor_schema.index("rightEventId")
    distance = neighbor_schema.index("distanceDecameters")
    lag = neighbor_schema.index("dayLag")
    assert len({(row[left], row[right]) for row in neighbors}) == len(neighbors)
    assert all(row[left] < row[right] for row in neighbors)
    assert all(row[left] in configuration_ids or row[right] in configuration_ids for row in neighbors)
    assert all(0 <= row[distance] <= 10_000 and 0 <= row[lag] <= 30 for row in neighbors)
    assert value["sources"]["ufoConfigurationPoints"]["counts"] == {
        "packedRows": 580783,
        "formationRows": 15605,
        "sourceCoordinateRows": 1424,
        "exactDayRows": 1349,
        "confidenceRows": 1349,
        "suitabilityRows": 1349,
        "validDateRows": 1349,
        "eligibleBeforePileExclusion": 1349,
        "eligiblePoints": 1270,
        "coordinatePilesExcluded": 22,
        "coordinatePileRowsExcluded": 79,
        "eligiblePointsBySource": {"majestic": 126, "ufocat": 1144},
    }
    assert value["sources"]["ufoConfigurationNeighbors"]["counts"] == {
        "eligibleUnionEndpoints": 34919,
        "eligibleCraftEndpoints": 33649,
        "eligibleConfigurationEndpoints": 1270,
        "pairedConfigurationEndpoints": 632,
        "pairs": 2012,
        "configurationConfigurationPairs": 114,
        "configurationCraftPairs": 1898,
        "crossSourcePairs": 392,
        "pairsWithin25Km7Days": 263,
        "pairsWithin50Km7Days": 455,
        "pairsWithin100Km30Days": 2012,
    }
    assert value["sources"]["ufoConfigurationPoints"]["policy"]["dumbbellBarbellAlias"] is False
    assert value["sources"]["ufoConfigurationNeighbors"]["policy"]["chronologySegmentsRead"] is False


def test_typed_readiness_gates_are_count_complete_and_self_hashing() -> None:
    value = manifest()
    sources_with_gates = {
        "animalContext", "cropContext", "facilities", "relationshipReconciliation",
        "ufoPointNeighbors", "ufoSpatialPoints", "contextUfoNeighbors", "ufoGeography",
        "ufoConfigurationPoints", "ufoConfigurationNeighbors",
    }
    required_fields = {
        "gateId", "label", "denominatorLabel", "applicability", "status", "inputN",
        "passedN", "failedN", "unknownN", "reasonCodes", "policyId", "evidenceHash",
    }
    for source_name in sources_with_gates:
        gates = value["sources"][source_name]["readiness"]["gates"]
        assert gates
        for gate in gates:
            assert set(gate) == required_fields
            assert gate["label"]
            assert gate["denominatorLabel"]
            assert gate["status"] in BUILDER.READINESS_STATUSES
            if gate["inputN"] is not None and gate["passedN"] is not None:
                assert gate["failedN"] == gate["inputN"] - gate["passedN"] - gate["unknownN"]
            evidence = dict(gate)
            actual_hash = evidence.pop("evidenceHash")
            assert actual_hash == BUILDER.sha256_bytes(BUILDER.canonical_json_bytes(evidence))


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


def test_v22_pinned_points_and_context_neighbors_are_bounded_and_decodable() -> None:
    points, point_schema = artifact_rows("ufoSpatialPoints")
    assert len(points) == 33801
    event_id = point_schema.index("eventId")
    coordinate_class = point_schema.index("coordinateEvidenceCode")
    pile_count = point_schema.index("coordinatePileCount")
    assert len({row[event_id] for row in points}) == len(points)
    assert all(
        decoded_label("ufoSpatialPoints", "coordinateEvidenceCode", row[coordinate_class])
        == "source_coordinates"
        for row in points
    )
    assert all(1 <= row[pile_count] < 10 for row in points)

    neighbors, schema = artifact_rows("contextUfoNeighbors")
    role = schema.index("dateRoleCode")
    lane = schema.index("contextLaneCode")
    distance = schema.index("distanceDecameters")
    lag = schema.index("dayLag")
    independent = schema.index("independentAssociationEligible")
    origin_event = schema.index("originUfoExcluded")
    origin_publisher = schema.index("originPublisherExcluded")
    assert len(neighbors) == 63753
    assert all(row[distance] is None or 0 <= row[distance] <= 25_000 for row in neighbors)
    assert all(row[lag] is None or abs(row[lag]) <= 30 for row in neighbors)
    assert {
        decoded_label("contextUfoNeighbors", "contextLaneCode", row[lane])
        for row in neighbors
    } == {"animal_public_marker", "crop_bounded", "crop_locality"}
    assert {
        decoded_label("contextUfoNeighbors", "dateRoleCode", row[role])
        for row in neighbors
    } == {
        "matched_control_minus_1y", "matched_control_minus_2y",
        "matched_control_plus_1y", "matched_control_plus_2y",
        "observed_catalog_date", "observed_reported_date",
    }
    assert any(row[origin_event] for row in neighbors)
    assert any(row[origin_publisher] for row in neighbors)
    assert all(
        row[independent] is False
        for row in neighbors
        if row[origin_event] or row[origin_publisher]
    )
    source = manifest()["sources"]["contextUfoNeighbors"]
    assert source["policy"]["chronologySegmentsRead"] is False
    assert source["counts"]["observedOriginExclusions"] == {
        "origin_publisher": 410,
        "origin_ufo_event": 30,
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

    points, rows, source = BUILDER.build_ufo_spatial_projections(tmp_path)

    assert source["counts"]["eligibleBeforePileExclusion"] == 12
    assert source["counts"]["coordinatePileRowsExcluded"] == 10
    assert source["counts"]["eligiblePoints"] == 2
    assert rows == [[11, 12, 2224, 0, True]]
    assert [point["eventId"] for point in points] == [11, 12]
    assert all(point["coordinateEvidenceCode"] == "source_coordinates" for point in points)
    assert all(point["duplicateLineageCode"] == "canonical_deduped_event" for point in points)
    assert all(point["fineSpatialStratumCode"].startswith("ea12x24:") for point in points)


def test_configuration_builder_keeps_formation_distinct_and_enforces_union_piles(tmp_path: Path) -> None:
    events = []
    for event_id in range(1, 11):
        events.append({
            "event_id": event_id,
            "lat": 40.0,
            "lon": -105.0,
            "date_iso": "2000-01-01",
            "sort_date_iso": "2000-01-01",
            "source": "ufocat",
            "craft_type_inferred": "formation",
            "craft_type_confidence": "high",
            "craft_type_source": "shape_normalized",
            "same_day_match_strength": "strong",
            "date_precision": "exact_day",
            "location_precision": "exact_coords",
            "coordinate_source": "raw_latlong",
        })
    for event_id, lon, source, configuration in (
        (11, 179.9, "ufocat", "formation"),
        (12, -179.9, "majestic", "triangle"),
    ):
        events.append({
            "event_id": event_id,
            "lat": 0.0,
            "lon": lon,
            "date_iso": "2000-01-01",
            "sort_date_iso": "2000-01-01",
            "source": source,
            "craft_type_inferred": configuration,
            "craft_type_confidence": "medium",
            "craft_type_source": "shape_normalized",
            "same_day_match_strength": "medium",
            "date_precision": "exact_day",
            "location_precision": "exact_coords",
            "coordinate_source": "raw_latlong",
        })
    export_packed_points(events, tmp_path)

    craft_points, _craft_pairs, _craft_source = BUILDER.build_ufo_spatial_projections(tmp_path)
    configuration_points, pairs, point_source, neighbor_source = (
        BUILDER.build_ufo_configuration_projections(tmp_path, craft_points)
    )

    assert [point["eventId"] for point in craft_points] == [12]
    assert [point["eventId"] for point in configuration_points] == [11]
    assert configuration_points[0]["configurationCode"] == "formation"
    assert configuration_points[0]["configurationCode"] != "dumbbell_barbell"
    assert point_source["counts"]["eligibleBeforePileExclusion"] == 11
    assert point_source["counts"]["coordinatePileRowsExcluded"] == 10
    assert point_source["counts"]["eligiblePoints"] == 1
    assert pairs == [[11, 12, 2224, 0, True]]
    assert neighbor_source["counts"]["configurationCraftPairs"] == 1
    assert neighbor_source["counts"]["configurationConfigurationPairs"] == 0
    repeated = BUILDER.build_ufo_configuration_projections(tmp_path, craft_points)
    assert (configuration_points, pairs, point_source, neighbor_source) == repeated


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

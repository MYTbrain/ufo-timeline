from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path

import pytest

from scripts.analysis_coordinate_evidence import (
    RISK_FLAG_DATELINE,
    RISK_FLAG_DUPLICATE_LINEAGE,
    RISK_FLAG_HIGH_LATITUDE,
    normalize_coordinate_evidence,
)
from scripts.build_analysis_coordinate_evidence_v1 import explicit_country_for_event
from scripts import build_cloudflare_bundle, reproduction
from scripts import publish_analysis_coordinate_evidence_r2_release as coordinate_release
from scripts import publish_optional_layer_r2_release as optional_r2


ROOT = Path(__file__).resolve().parents[1]
COORDINATE_ROOT = ROOT / "webapp" / "static_public" / "data" / "analysis_coordinate_evidence_v1"
MANIFEST_PATH = COORDINATE_ROOT / "manifest.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def classify(**overrides):
    values = {
        "coordinate_source": "raw_latlong",
        "location_precision": "exact_coords",
        "latitude": 40.0,
        "longitude": -75.0,
        "explicit_country": "United States of America",
        "country_bounds_available": True,
        "inside_country_bounds": True,
        "unresolved_lineage_conflict": False,
        "duplicate_record_count": 1,
    }
    values.update(overrides)
    return normalize_coordinate_evidence(**values)


def test_consistent_source_coordinate_is_typed_without_mutation() -> None:
    result = classify(latitude=40.1234567, longitude=-75.7654321)
    assert result.typed is True
    assert result.status == "typed_country_consistent"
    assert result.latitude == 40.1234567
    assert result.longitude == -75.7654321


def test_missing_country_bounds_stays_typed_but_explicitly_unchecked() -> None:
    result = classify(country_bounds_available=False, inside_country_bounds=None)
    assert result.typed is True
    assert result.status == "typed_country_unchecked"
    assert result.country_consistency == "unchecked_no_pinned_bounds"


def test_country_inconsistency_and_lineage_conflict_fail_closed() -> None:
    inconsistent = classify(inside_country_bounds=False)
    conflict = classify(unresolved_lineage_conflict=True, duplicate_record_count=4)
    assert inconsistent.typed is False
    assert inconsistent.status == "country_inconsistent"
    assert conflict.typed is False
    assert conflict.status == "unresolved_lineage_conflict"
    assert conflict.risk_flags & RISK_FLAG_DUPLICATE_LINEAGE


def test_zero_invalid_and_generalized_coordinates_never_gain_precision() -> None:
    zero = classify(latitude=0, longitude=0)
    generalized = classify(coordinate_source="geocoded", location_precision="city")
    assert zero.typed is False
    assert zero.status == "invalid_zero_sentinel"
    assert generalized.typed is False
    assert generalized.status == "origin_incompatible"


def test_dateline_and_high_latitude_are_explicit_sensitivity_flags() -> None:
    result = classify(
        latitude=70,
        longitude=175,
        explicit_country=None,
        country_bounds_available=False,
        inside_country_bounds=None,
    )
    assert result.typed is True
    assert result.risk_flags & RISK_FLAG_HIGH_LATITUDE
    assert result.risk_flags & RISK_FLAG_DATELINE


def test_specific_served_country_prevents_embedded_group_token_promotion() -> None:
    assert explicit_country_for_event({
        "country": "Malaysia",
        "location_raw": "Coastlands, PINANG, MALAYSIA, PNG, Malaysia",
    }) == "Malaysia"
    assert explicit_country_for_event({
        "country": "EU",
        "location_raw": "OSTRICOURT, Nord, FRA, EU",
    }) == "France"


def test_built_coordinate_artifacts_are_integral_separated_and_material() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert manifest["readiness"]["status"] == "ready_descriptive"
    assert manifest["counts"]["catalogRows"] == 702_893
    assert manifest["counts"]["sourceCoordinateRows"] == 110_352
    assert manifest["counts"]["typedRows"] == 110_055
    assert manifest["counts"]["typedCatalogPct"] == 15.657433
    assert manifest["counts"]["bySourceTyped"] == {
        "majestic": 14_510,
        "phenomenainon_updb": 1,
        "ufocat": 95_544,
    }
    assert manifest["counts"]["supportedSources"] == ["majestic", "ufocat"]
    assert manifest["counts"]["byCoordinateOrigin"] == {
        "geocoded": 470_431,
        "raw_latlong": 110_352,
        "unresolved": 122_110,
    }
    assert manifest["counts"]["byStatus"]["country_inconsistent"] == 297
    assert all(manifest["readiness"]["materialGates"].values())
    assert manifest["policy"]["canonicalEventsMutated"] is False
    assert manifest["policy"]["externalGeocodingUsed"] is False
    assert manifest["policy"]["coordinateRepairApplied"] is False
    assert manifest["policy"]["precisionPromotionAllowed"] is False
    assert manifest["policy"]["generalizedMarkersCountAsSourceCoordinates"] is False
    assert manifest["policy"]["missingCoordinatesCountAsZero"] is False

    decoded = {}
    for key, artifact in manifest["artifacts"].items():
        raw_path = COORDINATE_ROOT / Path(artifact["file"]).name
        gzip_path = COORDINATE_ROOT / Path(artifact["gzipFile"]).name
        assert raw_path.stat().st_size == artifact["bytes"]
        assert gzip_path.stat().st_size == artifact["gzipBytes"]
        assert gzip_path.stat().st_size <= 5_000_000
        assert sha256(raw_path) == artifact["sha256"]
        assert sha256(gzip_path) == artifact["gzipSha256"]
        assert gzip.decompress(gzip_path.read_bytes()) == raw_path.read_bytes()
        decoded[key] = json.loads(raw_path.read_text(encoding="utf-8"))
        assert len(decoded[key]) == artifact["rowCount"]

    projection = decoded["coordinateEvidenceProjection"]
    evidence = []
    for key in manifest["artifactGroups"]["originalEvidenceShards"]:
        evidence.extend(decoded[key])
    assert len(projection) == len(evidence) == 110_352
    assert [(row[0], str(row[1])) for row in projection] == [(row[0], str(row[1])) for row in evidence]
    assert all(projection[index][0] < projection[index + 1][0] for index in range(len(projection) - 1))
    statuses = manifest["codes"]["status"]
    for row in projection:
        assert -90 <= row[9] <= 90
        assert -180 <= row[10] <= 180
        if statuses[row[5]].startswith("typed_"):
            assert statuses[row[5]] in {"typed_country_consistent", "typed_country_unchecked"}


def test_coordinate_payload_is_classified_as_immutable_r2_only() -> None:
    discovered = build_cloudflare_bundle.discover_optional_r2_paths(ROOT / "webapp" / "static_public")
    payload = "data/analysis_coordinate_evidence_v1/coordinate_evidence_projection_v1.json.gz"
    assert payload in discovered
    assert build_cloudflare_bundle.classify_file(
        Path(payload),
        1,
        include_gzip_data=False,
        optional_r2_paths=discovered,
    ) == {"copy": False, "reason": "optional_layer_immutable_r2_payload"}
    contracts = reproduction.optional_layer_contracts(
        ROOT / "webapp" / "static_public",
        validate_local_payloads=True,
    )
    coordinate = next(contract for contract in contracts if contract["name"] == "analysis_coordinate_evidence_v1")
    assert len(coordinate["r2_records"]) == 12


def test_locked_coordinate_release_validates_locally() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    payloads = optional_r2.declared_payloads(manifest, MANIFEST_PATH.resolve())
    coordinate_release.validate_coordinate_evidence_manifest(manifest, payloads)
    report = optional_r2.publish_release(
        manifest_path=MANIFEST_PATH,
        bucket="ufo-timeline-data",
        wrangler=Path("node_modules/.bin/wrangler"),
        timeout=1,
        validate_only=True,
        validate_manifest=coordinate_release.validate_coordinate_evidence_manifest,
        upload_label="analysis-coordinate-evidence-test",
    )
    assert report == {
        "releaseId": "analysis-coordinate-evidence-v1-20260804",
        "bucket": "ufo-timeline-data",
        "payloadCount": 12,
        "payloadBytes": 29_127_049,
        "r2Prefix": "releases/analysis-coordinate-evidence-v1-20260804",
        "assetBaseUrl": "https://pub-e9029ab2f6b448daad03d7cde7e15e64.r2.dev/releases/analysis-coordinate-evidence-v1-20260804",
        "validated": True,
    }


def test_coordinate_release_rejects_precision_promotion() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    payloads = optional_r2.declared_payloads(manifest, MANIFEST_PATH.resolve())
    changed = deepcopy(manifest)
    changed["policy"]["precisionPromotionAllowed"] = True
    with pytest.raises(optional_r2.ReleaseError, match="identity changed"):
        coordinate_release.validate_coordinate_evidence_manifest(changed, payloads)

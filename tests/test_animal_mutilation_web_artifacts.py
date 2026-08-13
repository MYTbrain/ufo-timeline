from __future__ import annotations

import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
STATIC_ROOT = REPO_ROOT / "webapp" / "static_public"
ANIMAL_ROOT = STATIC_ROOT / "data" / "animal_mutilations"
BUILDER_PATH = REPO_ROOT / "scripts" / "build_animal_mutilation_web_artifacts.py"


def load_builder():
    spec = importlib.util.spec_from_file_location("animal_mutilation_web_builder", BUILDER_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


BUILDER = load_builder()


def read_gzip_json(path: Path):
    return json.loads(gzip.decompress(path.read_bytes()))


def test_frozen_animal_web_artifacts_are_complete_reachable_and_r2_only() -> None:
    manifest_bytes = (ANIMAL_ROOT / "manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    assert manifest["releaseId"] == "animal-mutilations-v1-20260812"
    assert manifest["assetBaseUrl"].endswith("/releases/animal-mutilations-v1-20260812/")
    assert manifest["delivery"]["immutablePrefix"] == "releases/animal-mutilations-v1-20260812/"
    assert manifest["delivery"]["pagesFiles"] == ["manifest.json"]
    assert manifest["counts"] == {
        "acceptedNewCases": 7,
        "boundedCoordinates": 0,
        "records": 1184,
        "mapped": 518,
        "unmapped": 666,
        "mappedPositions": 400,
        "exactCoordinates": 0,
        "dated": 1156,
        "undated": 28,
        "exactDay": 928,
        "mappedExactDay": 340,
        "reportedUnreviewed": 1173,
        "legallyRestrictedSuppressed": 0,
        "sourceRecords": 1177,
        "detailChunks": 5,
    }
    assert manifest["policy"] == {
        "causality": "not_asserted",
        "contentWarningRequired": True,
        "craftColorEligible": False,
        "exactCoordinateEligible": False,
        "legalRestrictionSuppressesPublicRecord": True,
        "playbackEligible": False,
        "privateOwnerAndAccessDetailsPublished": False,
        "relationshipsEligible": False,
        "sourceSupportedPrivatePropertyCoordinatesPublished": True,
        "status": "mixed",
        "traceEligible": False,
        "traceRole": "context_only",
    }
    assert re.fullmatch(r"[0-9a-f]{64}", manifest["source"]["handoffZipSha256"])
    assert re.fullmatch(r"[0-9a-f]{64}", manifest["source"]["handoffManifestSha256"])
    assert re.fullmatch(r"[0-9a-f]{40}", manifest["source"]["releaseCommit"])
    coordinate_audit = manifest["source"]["coordinateAudit"]
    assert coordinate_audit["requiredForRelease"] is True
    if coordinate_audit["available"]:
        assert coordinate_audit["recordCount"] == 1177
        assert coordinate_audit["correctionCount"] == 479
        assert coordinate_audit["semanticValidationPassed"] is True
    else:
        assert coordinate_audit == {"available": False, "requiredForRelease": True}

    declarations = [manifest["points"], manifest["catalog"], *manifest["details"]["files"]]
    declared_paths = sorted(item["path"] for item in declarations)
    assert manifest["delivery"]["r2OnlyPaths"] == declared_paths
    assert all(item["r2Only"] is True for item in declarations)
    assert manifest["details"]["chunkSize"] == 250
    assert len(manifest["details"]["files"]) == 5
    assert all(item["recordCount"] <= 250 for item in manifest["details"]["files"])
    for declaration in declarations:
        payload = (ANIMAL_ROOT / declaration["path"]).read_bytes()
        assert len(payload) == declaration["bytes"]
        assert hashlib.sha256(payload).hexdigest() == declaration["sha256"]
        assert len(gzip.decompress(payload)) == declaration["decodedBytes"]

    points = read_gzip_json(ANIMAL_ROOT / manifest["points"]["path"])
    catalog = read_gzip_json(ANIMAL_ROOT / manifest["catalog"]["path"])
    assert len(points) == 518
    assert len(catalog) == 1184
    assert points == sorted(points, key=lambda row: row[0])
    assert catalog == sorted(catalog, key=lambda row: row[0])
    assert len({(row[1], row[2]) for row in points}) == 400
    assert sum(row[5] == 0 for row in points) == 340
    assert sum(row[4] is None for row in catalog) == 28
    assert sum(row[8] for row in catalog) == 518
    assert {row[10] for row in catalog} == {"reported_unreviewed", "source_reviewed"}
    assert sum(row[10] == "source_reviewed" for row in catalog) == 11
    assert "evidenceExcerpt" not in manifest["catalog"]["rowSchema"]
    assert "sourceNarrative" not in manifest["catalog"]["rowSchema"]

    catalog_ids = {row[0] for row in catalog}
    point_ids = {row[0] for row in points}
    assert len(catalog_ids) == 1184
    assert point_ids < catalog_ids
    detail_ids: set[str] = set()
    for chunk_number, declaration in enumerate(manifest["details"]["files"]):
        details = read_gzip_json(ANIMAL_ROOT / declaration["path"])
        assert len(details) == declaration["recordCount"]
        detail_ids.update(details)
        assert all(detail["status"] in {"reported_unreviewed", "source_reviewed"} for detail in details.values())
        assert all(detail["causality"] == "not_asserted" for detail in details.values())
        assert all(detail["traceEligible"] is False for detail in details.values())
        assert all(detail["traceRole"] == "context_only" for detail in details.values())
        assert {row[0] for row in catalog if row[9] == chunk_number} == set(details)
    assert detail_ids == catalog_ids


def minimal_collection() -> dict:
    props = {
        "animal_mutilation_event_id": "ami_test",
        "causality": "not_asserted",
        "claim_label": "Reported animal mutilation",
        "content_warning": "Animal-death descriptions may be disturbing.",
        "date_end": "1975-01-31",
        "date_precision": "month",
        "date_start": "1975-01-01",
        "event_domain": "animal_mutilation",
        "evidence_excerpts": ["A public bounded excerpt."],
        "evidence_status": "reported_unreviewed",
        "location_label": "Example County, US",
        "location_precision": "unknown",
        "normalized_common_names": ["cattle"],
        "privacy_level": "public_generalized",
        "record_type": "mutilation_case",
        "reported_taxon_keys": ["cattle"],
        "source_incident_id": "cmi_test",
        "source_incident_sha256": "0" * 64,
        "source_refs": [{"source_id": "source:test", "source_hash": "1" * 64, "locator": "line 1"}],
        "source_status": "lead",
        "species_groups": ["bovine"],
        "status": "reported_unreviewed",
        "summary": "The cited source reports an animal mutilation incident involving cattle.",
        "title": "Reported animal mutilation",
        "trace_eligible": False,
        "trace_role": "context_only",
        "uncertainty": {
            "coordinates_available": True,
            "date_precision": "month",
            "location_precision": "unknown",
            "privacy_generalized": True,
        },
    }
    return {
        "type": "FeatureCollection",
        "name": "Animal Mutilation Reports",
        "schema_version": "animal-mutilation-timeline-overlay-v1.1.0",
        "causality": "not_asserted",
        "trace_eligible": False,
        "trace_role": "context_only",
        "features": [{
            "type": "Feature",
            "id": "animal_mutilation:ami_test",
            "geometry": {"type": "Point", "coordinates": [-104.5, 39.7]},
            "properties": props,
        }],
    }


def test_builder_is_byte_deterministic_and_keeps_excerpts_out_of_catalog(tmp_path: Path) -> None:
    source = tmp_path / "source.geojson"
    source.write_bytes(BUILDER.canonical_json_bytes(minimal_collection()))
    outputs = [tmp_path / "build-a", tmp_path / "build-b"]
    for output in outputs:
        BUILDER.build(
            input_path=source,
            handoff_zip=None,
            output_root=output,
            release_id="animal-mutilations-v1-20260802",
            asset_base_url="https://assets.example.test/releases/animal-mutilations-v1-20260802/",
            chunk_size=250,
            context_evidence_root=None,
        )
    paths_a = sorted(path.relative_to(outputs[0]) for path in outputs[0].rglob("*") if path.is_file())
    paths_b = sorted(path.relative_to(outputs[1]) for path in outputs[1].rglob("*") if path.is_file())
    assert paths_a == paths_b
    assert all((outputs[0] / path).read_bytes() == (outputs[1] / path).read_bytes() for path in paths_a)
    catalog = read_gzip_json(outputs[0] / "catalog.json.gz")
    assert "public bounded excerpt" not in catalog[0][12]
    details = read_gzip_json(outputs[0] / "details" / "chunk_000.json.gz")
    assert details["animal_mutilation:ami_test"]["evidenceExcerpts"] == ["A public bounded excerpt."]


def test_builder_rejects_oversized_chunks_and_nonimmutable_urls(tmp_path: Path) -> None:
    source = tmp_path / "source.geojson"
    source.write_bytes(BUILDER.canonical_json_bytes(minimal_collection()))
    with pytest.raises(ValueError, match="between 1 and 250"):
        BUILDER.build(
            input_path=source,
            handoff_zip=None,
            output_root=tmp_path / "bad-chunk",
            release_id="animal-mutilations-v1-20260802",
            asset_base_url="",
            chunk_size=251,
        )
    with pytest.raises(ValueError, match="immutable release prefix"):
        BUILDER.build(
            input_path=source,
            handoff_zip=None,
            output_root=tmp_path / "bad-url",
            release_id="animal-mutilations-v1-20260802",
            asset_base_url="https://assets.example.test/releases/wrong/",
            chunk_size=250,
        )

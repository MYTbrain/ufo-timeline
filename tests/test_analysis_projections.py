from __future__ import annotations

import gzip
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import re
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
STATIC_ROOT = REPO_ROOT / "webapp" / "static_public"
ANALYSIS_ROOT = STATIC_ROOT / "data" / "analysis_v1"
BUILDER_PATH = REPO_ROOT / "scripts" / "build_analysis_projections.py"


def load_builder():
    spec = importlib.util.spec_from_file_location("analysis_projection_builder", BUILDER_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


BUILDER = load_builder()


def read_manifest() -> dict:
    return json.loads((ANALYSIS_ROOT / "manifest.json").read_text(encoding="utf-8"))


def artifact_bytes(declaration: dict, key: str) -> bytes:
    return (STATIC_ROOT / declaration[key]).read_bytes()


def test_frozen_manifest_pins_releases_hashes_and_descriptive_policy() -> None:
    manifest = read_manifest()

    assert manifest["schemaVersion"] == 1
    assert manifest["schemaId"] == "ufo-timeline-analysis-projections-v1.1.0"
    assert manifest["releaseId"] == "analysis-projections-v1-context-evidence-20260811"
    assert manifest["counts"] == {
        "animalReports": 1177,
        "cropCircles": 7745,
        "mappedAnimalReports": 518,
        "ufoCatalog": 702893,
        "unmappedAnimalReports": 659,
    }
    assert manifest["sources"]["cropCircles"]["releaseId"] == "crop-circles-context-evidence-v1-20260811"
    assert manifest["sources"]["cropCircles"]["rowCount"] == 7745
    assert manifest["sources"]["animalReports"]["releaseId"] == "animal-mutilations-v1-20260811"
    assert manifest["sources"]["animalReports"]["rowCount"] == 1177

    catalog = manifest["sources"]["ufoCatalog"]
    assert catalog["releaseId"] == "coordinated-reliability-v152-20260731"
    assert catalog["rowCount"] == 702893
    assert catalog["mappedRowCount"] == 580783
    assert catalog["hashRole"] == "served_catalog_manifest"
    assert catalog["sha256"] == "242ff4abc42c70c2b241a3cd16c8b9059bca137d940bd6147c5a65de63b7750b"
    assert catalog["sourceCorpusBytes"] == 4949745439
    assert catalog["sourceCorpusHashRole"] == "pre_serving_canonical_source_corpus"
    assert catalog["sourceCorpusRowCount"] == 703018
    assert catalog["sourceCorpusSha256"] == (
        "3d91c97621d23dfe28020c2ee7b311b7bf850c1c519371afc62ebafb8a32f29b"
    )
    assert catalog["reviewedMergedShellReduction"] == 125
    assert catalog["canonicalWebManifestSha256"] == (
        "242ff4abc42c70c2b241a3cd16c8b9059bca137d940bd6147c5a65de63b7750b"
    )
    assert catalog["canonicalWebManifestSha256"] == catalog["sha256"]
    assert "releaseSeal" not in catalog
    assert "releaseSealSha256" not in catalog

    for source in manifest["sources"].values():
        for key in (
            "path",
            "manifest",
            "canonicalWebManifest",
            "sourceCorpusPath",
        ):
            value = source.get(key)
            if value is None:
                continue
            assert not PurePosixPath(value).is_absolute()
            assert ":\\" not in value and ":/" not in value
            assert "\\" not in value
        for key, value in source.items():
            if key.lower().endswith("sha256"):
                assert re.fullmatch(r"[0-9a-f]{64}", value)

    assert manifest["policy"] == {
        "authenticityAssessments": False,
        "causalInferences": False,
        "crossDomainJoins": False,
        "proximityMetrics": False,
        "scope": "descriptive_catalog_aggregates_only",
        "speciesGroupsIncluded": True,
        "traceMetrics": False,
        "travelMetrics": False,
        "ufoRelationships": False,
        "unmappedAnimalReportsIncluded": True,
    }


def test_projection_artifacts_are_complete_hashed_compact_and_decodable() -> None:
    manifest = read_manifest()
    crop_declaration = manifest["artifacts"]["cropCircles"]
    animal_declaration = manifest["artifacts"]["animalReports"]

    assert crop_declaration["rowSchema"] == BUILDER.CROP_ROW_SCHEMA
    assert animal_declaration["rowSchema"] == BUILDER.ANIMAL_ROW_SCHEMA
    assert all(field not in BUILDER.CROP_ROW_SCHEMA for field in (
        "classification",
        "originStatus",
        "lat",
        "lon",
        "trace",
        "proximity",
        "travel",
        "causality",
        "authenticity",
    ))
    assert all(field not in BUILDER.ANIMAL_ROW_SCHEMA for field in (
        "lat",
        "lon",
        "sourceRefs",
        "searchText",
        "trace",
        "proximity",
        "travel",
        "causality",
    ))

    payloads: dict[str, list] = {}
    for domain, declaration in manifest["artifacts"].items():
        raw = artifact_bytes(declaration, "file")
        compressed = artifact_bytes(declaration, "gzipFile")
        assert len(raw) == declaration["bytes"]
        assert len(compressed) == declaration["gzipBytes"]
        assert hashlib.sha256(raw).hexdigest() == declaration["sha256"]
        assert hashlib.sha256(compressed).hexdigest() == declaration["gzipSha256"]
        assert gzip.decompress(compressed) == raw
        assert compressed[4:8] == b"\x00\x00\x00\x00"
        payloads[domain] = json.loads(raw)
        assert len(payloads[domain]) == declaration["rowCount"]
        assert all(len(row) == len(declaration["rowSchema"]) for row in payloads[domain])
        ids = [row[0] for row in payloads[domain]]
        assert ids == sorted(ids)
        assert len(ids) == len(set(ids))
        assert b"ufo:" not in raw.lower()

    crop_rows = payloads["cropCircles"]
    assert len(crop_rows) == 7745
    assert sum(row[9] for row in crop_rows) == 4324
    assert sum(not row[9] for row in crop_rows) == 3421
    assert sum(row[10] for row in crop_rows) == 564
    assert sum(row[11] for row in crop_rows) == 136
    assert all(
        (row[12] is None and row[13] is None)
        or (row[12] <= row[13])
        for row in crop_rows
    )
    assert {
        code: sum(row[8] == code for row in crop_rows)
        for code in range(len(manifest["codes"]["coordinateClass"]))
    } == {0: 10, 1: 409, 2: 3905, 3: 3421}

    animal_rows = payloads["animalReports"]
    assert len(animal_rows) == 1177
    assert sum(row[5] for row in animal_rows) == 518
    assert sum(not row[5] for row in animal_rows) == 659
    assert sum(row[1] is None for row in animal_rows) == 28
    assert {code for row in animal_rows for code in row[4]} == set(
        range(len(manifest["codes"]["speciesGroup"]))
    )
    assert all(row[4] for row in animal_rows)
    assert all(row[6] == 0 for row in animal_rows)
    assert all(
        (row[7] is None and row[8] is None)
        or (row[7] <= row[8])
        for row in animal_rows
    )


def test_builder_regenerates_the_frozen_release_byte_for_byte(tmp_path: Path) -> None:
    if not BUILDER.DEFAULT_CATALOG_SOURCE.is_file():
        pytest.skip("Full-corpus Analysis v1 regeneration requires the protected catalog source")
    output = tmp_path / "analysis_v1"
    manifest = BUILDER.build(output_root=output)

    assert manifest == read_manifest()
    for filename in (
        "animal_reports.json",
        "animal_reports.json.gz",
        "crop_circles.json",
        "crop_circles.json.gz",
        "manifest.json",
    ):
        assert (output / filename).read_bytes() == (ANALYSIS_ROOT / filename).read_bytes()


def test_gzip_encoding_is_reproducible_without_timestamps() -> None:
    raw = BUILDER.canonical_json_document([["record", 1, True]])
    first = BUILDER.deterministic_gzip(raw)
    second = BUILDER.deterministic_gzip(raw)

    assert first == second
    assert first[4:8] == b"\x00\x00\x00\x00"
    assert gzip.decompress(first) == raw


def test_date_intervals_preserve_partial_date_uncertainty() -> None:
    assert BUILDER.date_interval_ordinals("2000-02-29") == (730179, 730179)
    assert BUILDER.date_interval_ordinals("2000-02") == (730151, 730179)
    assert BUILDER.date_interval_ordinals("2000") == (730120, 730485)
    assert BUILDER.date_interval_ordinals("2000-12-31", "2001-01-02") == (730485, 730487)
    assert BUILDER.date_interval_ordinals(None, None) == (None, None)

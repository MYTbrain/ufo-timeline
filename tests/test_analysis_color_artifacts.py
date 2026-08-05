from __future__ import annotations

from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path

import pytest

from scripts import build_cloudflare_bundle, reproduction
from scripts import publish_analysis_color_r2_release as color_release
from scripts import publish_optional_layer_r2_release as optional_r2


ROOT = Path(__file__).resolve().parents[1]
COLOR_ROOT = ROOT / "webapp" / "static_public" / "data" / "analysis_color_v1"
MANIFEST_PATH = COLOR_ROOT / "manifest.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_built_color_artifacts_are_integral_material_and_role_preserving() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    counts = manifest["counts"]
    assert counts["catalogRows"] == 702_893
    assert counts["rawColorRows"] == 79_215
    assert counts["normalizedRows"] == 70_097
    assert counts["normalizedCatalogPct"] == 9.972642
    assert counts["uniqueSourceRawValues"] == 4_859
    assert counts["bySourceRaw"] == {"nuforc": 11_686, "ufocat": 67_529}
    assert counts["bySourceNormalized"] == {"nuforc": 10_165, "ufocat": 59_932}
    assert counts["roleSpecificRows"] == 1_207
    assert counts["roleUnspecifiedRows"] == 77_994
    assert counts["supportedSources"] == ["nuforc", "ufocat"]
    assert all(manifest["readiness"]["materialGates"].values())
    assert manifest["readiness"]["status"] == "ready_descriptive_cross_source"
    assert manifest["readiness"]["assessmentLane"] == "cross_source_descriptive_role_preserving"
    assert manifest["commonSupport"]["commonSupportRate"] == 1.0
    assert len(manifest["commonSupport"]["commonSupportCategories"]) == 15
    assert manifest["policy"]["narrativeDescriptionsRead"] is False
    assert manifest["policy"]["neighboringFieldsRead"] is False
    assert manifest["policy"]["unknownRolePromoted"] is False
    assert manifest["policy"]["patternFinderPromotion"] is False

    decoded = {}
    for key, artifact in manifest["artifacts"].items():
        raw_path = COLOR_ROOT / Path(artifact["file"]).name
        gzip_path = COLOR_ROOT / Path(artifact["gzipFile"]).name
        assert raw_path.stat().st_size == artifact["bytes"]
        assert gzip_path.stat().st_size == artifact["gzipBytes"]
        assert gzip_path.stat().st_size <= 5_000_000
        assert sha256(raw_path) == artifact["sha256"]
        assert sha256(gzip_path) == artifact["gzipSha256"]
        assert gzip.decompress(gzip_path.read_bytes()) == raw_path.read_bytes()
        decoded[key] = json.loads(raw_path.read_text(encoding="utf-8"))
        assert len(decoded[key]) == artifact["rowCount"]

    dictionary = decoded["colorValueDictionary"]
    projection = decoded["colorProjection"]
    assert all(projection[index][0] < projection[index + 1][0] for index in range(len(projection) - 1))
    assert sum(row[10] for row in dictionary) == len(projection)
    statuses = manifest["codes"]["status"]
    roles = manifest["codes"]["role"]
    maximum_mask = (1 << len(manifest["codes"]["category"])) - 1
    occurrences = [0] * len(dictionary)
    for projection_row in projection:
        occurrences[projection_row[2]] += 1
    for index, row in enumerate(dictionary):
        assert hashlib.sha256(row[2].encode("utf-8")).hexdigest() == row[1]
        assert roles[row[5]] in {
            "role_unspecified", "emitted_light_explicit", "object_surface_explicit", "both_role_cues_ambiguous",
        }
        assert 0 <= row[6] <= maximum_mask
        assert occurrences[index] == row[10]
        category_count = row[6].bit_count()
        status = statuses[row[3]]
        if status == "exact_single":
            assert category_count == 1
        elif status == "explicit_compound":
            assert category_count >= 2
        elif status == "changing_known":
            assert category_count >= 1
        elif status in {"missing", "source_sentinel", "changing_unspecified", "non_color_descriptor", "unparsed"}:
            assert category_count == 0
        elif status == "multicolor_unspecified":
            assert category_count < 2


def test_color_payload_is_classified_as_immutable_r2_only() -> None:
    discovered = build_cloudflare_bundle.discover_optional_r2_paths(ROOT / "webapp" / "static_public")
    payload = "data/analysis_color_v1/color_projection_v1.json.gz"
    assert payload in discovered
    assert build_cloudflare_bundle.classify_file(
        Path(payload), 1, include_gzip_data=False, optional_r2_paths=discovered,
    ) == {"copy": False, "reason": "optional_layer_immutable_r2_payload"}
    contracts = reproduction.optional_layer_contracts(
        ROOT / "webapp" / "static_public", validate_local_payloads=True,
    )
    contract = next(item for item in contracts if item["name"] == "analysis_color_v1")
    assert len(contract["r2_records"]) == 4


def test_locked_color_release_validates_locally() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    payloads = optional_r2.declared_payloads(manifest, MANIFEST_PATH.resolve())
    color_release.validate_color_manifest(manifest, payloads)
    report = optional_r2.publish_release(
        manifest_path=MANIFEST_PATH,
        bucket="ufo-timeline-data",
        wrangler=Path("node_modules/.bin/wrangler"),
        timeout=1,
        validate_only=True,
        validate_manifest=color_release.validate_color_manifest,
        upload_label="analysis-color-test",
    )
    assert report == {
        "releaseId": "analysis-color-v1-20260805",
        "bucket": "ufo-timeline-data",
        "payloadCount": 4,
        "payloadBytes": 4_586_485,
        "r2Prefix": "releases/analysis-color-v1-20260805",
        "assetBaseUrl": "https://pub-e9029ab2f6b448daad03d7cde7e15e64.r2.dev/releases/analysis-color-v1-20260805",
        "validated": True,
    }


def test_color_release_rejects_role_or_pattern_promotion() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    payloads = optional_r2.declared_payloads(manifest, MANIFEST_PATH.resolve())
    for key in ("unknownRolePromoted", "sourceFieldImpliesObjectColor", "patternFinderPromotion"):
        changed = deepcopy(manifest)
        changed["policy"][key] = True
        with pytest.raises(optional_r2.ReleaseError, match="weakens"):
            color_release.validate_color_manifest(changed, payloads)

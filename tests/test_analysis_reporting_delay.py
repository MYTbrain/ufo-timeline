from __future__ import annotations

from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path

import pytest

from scripts.analysis_reporting_delay import normalize_reporting_delay, parse_explicit_day
from scripts import build_cloudflare_bundle, reproduction
from scripts import publish_analysis_reporting_delay_r2_release as reporting_release
from scripts import publish_optional_layer_r2_release as optional_r2


ROOT = Path(__file__).resolve().parents[1]
REPORTING_DELAY_ROOT = ROOT / "webapp" / "static_public" / "data" / "analysis_reporting_delay_v1"
MANIFEST_PATH = REPORTING_DELAY_ROOT / "manifest.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_explicit_day_parser_accepts_only_leading_iso_calendar_days() -> None:
    assert parse_explicit_day("2008-04-02 20:18 Pacific").isoformat() == "2008-04-02"
    assert parse_explicit_day("2008-02-31") is None
    assert parse_explicit_day("04/02/2008") is None
    assert parse_explicit_day("2008-04") is None


def test_reported_and_posted_roles_never_conflate() -> None:
    reported = normalize_reporting_delay("2008-04-02", "exact_day", "2008-04-04 20:18 Pacific", "2008-04-17")
    assert reported.typed is True
    assert reported.selected_role == "reported"
    assert reported.status == "reported_valid"
    assert reported.delay_days == 2
    assert reported.delay_bin == "two_to_three_days"
    assert reported.posted_date.isoformat() == "2008-04-17"

    fallback = normalize_reporting_delay("2008-04-02", "exact_day", "", "2008-04-17")
    assert fallback.typed is True
    assert fallback.selected_role == "posted"
    assert fallback.status == "posted_fallback_valid"
    assert fallback.delay_days == 15


def test_present_invalid_or_negative_reported_role_fails_closed_without_posted_rescue() -> None:
    negative = normalize_reporting_delay("2018-07-07", "exact_day", "2018-07-06 21:49 Pacific", "2018-07-13")
    assert negative.typed is False
    assert negative.selected_role == "reported"
    assert negative.status == "reported_negative"
    assert negative.delay_days is None
    assert negative.delay_bin == "unknown"

    invalid = normalize_reporting_delay("2018-07-07", "exact_day", "July 8, 2018", "2018-07-13")
    assert invalid.typed is False
    assert invalid.selected_role == "reported"
    assert invalid.status == "reported_unparseable"
    assert invalid.delay_days is None


def test_occurrence_precision_must_be_exact_day() -> None:
    value = normalize_reporting_delay("2018-07-07", "month", "2018-07-08", "")
    assert value.typed is False
    assert value.status == "occurrence_precision_incompatible"
    assert value.delay_days is None


def test_built_reporting_delay_artifacts_are_integral_role_preserving_and_material() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert manifest["readiness"]["status"] == "ready_descriptive"
    assert manifest["counts"]["catalogRows"] == 702_893
    assert manifest["counts"]["dateRoleEvidenceRows"] == 270_461
    assert manifest["counts"]["typedRows"] == 261_331
    assert manifest["counts"]["typedCatalogPct"] == 37.179343
    assert manifest["counts"]["bySourceTyped"] == {"mufon": 113_016, "nuforc": 148_315}
    assert manifest["counts"]["supportedSources"] == ["mufon", "nuforc"]
    assert manifest["counts"]["byStatus"]["reported_negative"] == 3_584
    assert all(manifest["readiness"]["materialGates"].values())
    assert manifest["policy"]["canonicalEventsMutated"] is False
    assert manifest["policy"]["missingDelayIsZero"] is False
    assert manifest["policy"]["negativeDelayCoercedToZero"] is False
    assert manifest["policy"]["reportedRolePrecedence"] == "present_reported_role_never_replaced_by_posted_role"

    decoded = {}
    for key, artifact in manifest["artifacts"].items():
        raw_path = REPORTING_DELAY_ROOT / Path(artifact["file"]).name
        gzip_path = REPORTING_DELAY_ROOT / Path(artifact["gzipFile"]).name
        assert raw_path.stat().st_size == artifact["bytes"]
        assert gzip_path.stat().st_size == artifact["gzipBytes"]
        assert gzip_path.stat().st_size <= 5_000_000
        assert sha256(raw_path) == artifact["sha256"]
        assert sha256(gzip_path) == artifact["gzipSha256"]
        assert gzip.decompress(gzip_path.read_bytes()) == raw_path.read_bytes()
        decoded[key] = json.loads(raw_path.read_text(encoding="utf-8"))
        assert len(decoded[key]) == artifact["rowCount"]

    projection = decoded["reportingDelayProjection"]
    evidence = []
    for key in manifest["artifactGroups"]["roleEvidenceShards"]:
        evidence.extend(decoded[key])
    assert len(projection) == len(evidence) == 270_461
    assert [(row[0], str(row[1])) for row in projection] == [(row[0], str(row[1])) for row in evidence]
    assert all(projection[index][0] < projection[index + 1][0] for index in range(len(projection) - 1))
    status_codes = manifest["codes"]["status"]
    bin_codes = manifest["codes"]["delayBin"]
    for row in projection:
        status = status_codes[row[6]]
        delay = row[7]
        bin_id = bin_codes[row[8]]
        if status in {"reported_valid", "posted_fallback_valid"}:
            assert isinstance(delay, int) and delay >= 0 and bin_id != "unknown"
        else:
            assert delay is None and bin_id == "unknown"


def test_reporting_delay_payload_is_classified_as_immutable_r2_only() -> None:
    discovered = build_cloudflare_bundle.discover_optional_r2_paths(ROOT / "webapp" / "static_public")
    assert "data/analysis_reporting_delay_v1/reporting_delay_projection_v1.json.gz" in discovered
    decision = build_cloudflare_bundle.classify_file(
        Path("data/analysis_reporting_delay_v1/reporting_delay_projection_v1.json.gz"),
        1,
        include_gzip_data=False,
        optional_r2_paths=discovered,
    )
    assert decision == {"copy": False, "reason": "optional_layer_immutable_r2_payload"}
    contracts = reproduction.optional_layer_contracts(
        ROOT / "webapp" / "static_public",
        validate_local_payloads=True,
    )
    reporting = next(contract for contract in contracts if contract["name"] == "analysis_reporting_delay_v1")
    assert len(reporting["r2_records"]) == 14


def test_locked_reporting_delay_release_validates_locally() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    payloads = optional_r2.declared_payloads(manifest, MANIFEST_PATH.resolve())
    reporting_release.validate_reporting_delay_manifest(manifest, payloads)
    report = optional_r2.publish_release(
        manifest_path=MANIFEST_PATH,
        bucket="ufo-timeline-data",
        wrangler=Path("node_modules/.bin/wrangler"),
        timeout=1,
        validate_only=True,
        validate_manifest=reporting_release.validate_reporting_delay_manifest,
        upload_label="analysis-reporting-delay-test",
    )
    assert report == {
        "releaseId": "analysis-reporting-delay-v1-20260804",
        "bucket": "ufo-timeline-data",
        "payloadCount": 14,
        "payloadBytes": 49_629_719,
        "r2Prefix": "releases/analysis-reporting-delay-v1-20260804",
        "assetBaseUrl": "https://pub-e9029ab2f6b448daad03d7cde7e15e64.r2.dev/releases/analysis-reporting-delay-v1-20260804",
        "validated": True,
    }


def test_reporting_delay_release_rejects_changed_scientific_contract() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    payloads = optional_r2.declared_payloads(manifest, MANIFEST_PATH.resolve())
    changed = deepcopy(manifest)
    changed["policy"]["negativeDelayCoercedToZero"] = True
    with pytest.raises(optional_r2.ReleaseError, match="identity changed"):
        reporting_release.validate_reporting_delay_manifest(changed, payloads)

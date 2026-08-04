from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

from scripts.analysis_duration import normalize_duration
from scripts import build_cloudflare_bundle, reproduction


ROOT = Path(__file__).resolve().parents[1]
DURATION_ROOT = ROOT / "webapp" / "static_public" / "data" / "analysis_duration_v1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_nuforc_exact_and_range_values_are_typed_conservatively() -> None:
    exact = normalize_duration("nuforc", "2 Minutes")
    assert exact.status == "exact"
    assert exact.lower_seconds == exact.upper_seconds == 120
    assert exact.descriptive_bin == exact.inferential_bin == "1_4_minutes"

    interval = normalize_duration("nuforc", "2-3 minutes")
    assert interval.status == "closed_range"
    assert (interval.lower_seconds, interval.upper_seconds) == (120, 180)
    assert interval.inferential_bin == "1_4_minutes"

    spanning = normalize_duration("nuforc", "3-5 minutes")
    assert spanning.status == "closed_range"
    assert spanning.descriptive_bin == "unknown"
    assert spanning.inferential_bin == "unknown"


def test_explicit_compound_approximate_and_censored_values_do_not_gain_precision() -> None:
    compound = normalize_duration("nuforc", "1 hour 30 minutes")
    assert compound.status == "exact"
    assert compound.lower_seconds == compound.upper_seconds == 5400

    approximate = normalize_duration("nuforc", "about 5 minutes")
    assert approximate.status == "approximate"
    assert approximate.descriptive_bin == "5_14_minutes"
    assert approximate.inferential_bin == "unknown"

    censored = normalize_duration("nuforc", "at least 10 minutes")
    assert censored.status == "lower_censored"
    assert censored.lower_seconds == 600
    assert censored.upper_seconds is None
    assert censored.inferential_bin == "unknown"

    irregular_fraction_spacing = normalize_duration("nuforc", "1 /4 hour")
    assert irregular_fraction_spacing.status == "exact"
    assert irregular_fraction_spacing.lower_seconds == irregular_fraction_spacing.upper_seconds == 900


def test_ufocat_codebook_semantics_remain_approximate() -> None:
    minutes = normalize_duration("ufocat", "5")
    assert minutes.status == "approximate"
    assert minutes.lower_seconds == minutes.upper_seconds == 300
    assert minutes.descriptive_bin == "5_14_minutes"
    assert minutes.inferential_bin == "unknown"

    seconds_code = normalize_duration("ufocat", ".1")
    assert seconds_code.status == "approximate"
    assert (seconds_code.lower_seconds, seconds_code.upper_seconds) == (3, 8)

    at_least = normalize_duration("ufocat", "+2")
    assert at_least.status == "lower_censored"
    assert at_least.lower_seconds == 120
    assert at_least.upper_seconds is None


def test_ambiguous_or_undocumented_values_fail_closed() -> None:
    assert normalize_duration("nuforc", "seconds").status == "unparsed"
    assert normalize_duration("nuforc", "ongoing").status == "unparsed"
    assert normalize_duration("nuforc", "15").status == "unparsed"
    assert normalize_duration("majestic", "15").reason == "majestic_numeric_unit_undocumented"
    assert normalize_duration("ufocat", "SH").status == "ambiguous"


def test_built_duration_artifacts_are_integral_sparse_and_material() -> None:
    manifest = json.loads((DURATION_ROOT / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["readiness"]["status"] == "ready_descriptive"
    assert manifest["counts"]["catalogRows"] == 702_893
    assert manifest["counts"]["normalizedRows"] >= 232_065
    assert manifest["counts"]["normalizedCatalogPct"] >= 33.0
    assert manifest["counts"]["supportedSources"] == ["nuforc", "ufocat"]
    assert all(manifest["readiness"]["materialGates"].values())
    assert manifest["policy"]["canonicalEventsMutated"] is False
    assert manifest["policy"]["narrativeDescriptionsRead"] is False
    assert manifest["policy"]["ufocatApproximateCodesInferentiallyEligible"] is False

    decoded = {}
    for key, artifact in manifest["artifacts"].items():
        raw_path = DURATION_ROOT / Path(artifact["file"]).name
        gzip_path = DURATION_ROOT / Path(artifact["gzipFile"]).name
        assert raw_path.stat().st_size == artifact["bytes"]
        assert gzip_path.stat().st_size == artifact["gzipBytes"]
        assert sha256(raw_path) == artifact["sha256"]
        assert sha256(gzip_path) == artifact["gzipSha256"]
        assert gzip.decompress(gzip_path.read_bytes()) == raw_path.read_bytes()
        decoded[key] = json.loads(raw_path.read_text(encoding="utf-8"))
        assert len(decoded[key]) == artifact["rowCount"]

    dictionary = decoded["durationValueDictionary"]
    projection = decoded["durationProjection"]
    previous_index = -1
    for catalog_index, event_id, value_code, macroregion_code in projection:
        assert catalog_index > previous_index
        assert event_id != ""
        assert 0 <= value_code < len(dictionary)
        assert 0 <= macroregion_code < len(manifest["codes"]["macroregion"])
        previous_index = catalog_index
    assert sum(row[-1] for row in dictionary) == len(projection)
    for row in dictionary:
        assert hashlib.sha256(row[2].encode("utf-8")).hexdigest() == row[1]


def test_duration_payload_is_classified_as_immutable_r2_only() -> None:
    discovered = build_cloudflare_bundle.discover_optional_r2_paths(ROOT / "webapp" / "static_public")
    assert "data/analysis_duration_v1/duration_projection_v1.json.gz" in discovered
    decision = build_cloudflare_bundle.classify_file(
        Path("data/analysis_duration_v1/duration_projection_v1.json.gz"),
        1,
        include_gzip_data=False,
        optional_r2_paths=discovered,
    )
    assert decision == {"copy": False, "reason": "optional_layer_immutable_r2_payload"}
    contracts = reproduction.optional_layer_contracts(
        ROOT / "webapp" / "static_public",
        validate_local_payloads=True,
    )
    duration = next(contract for contract in contracts if contract["name"] == "analysis_duration_v1")
    assert len(duration["r2_records"]) == 4

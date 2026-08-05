from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from scripts import build_analysis_improvement_campaign as campaign


ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN_ROOT = ROOT / "campaign" / "analysis_improvement"


def load(relative: str):
    return json.loads((CAMPAIGN_ROOT / relative).read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_field_semantics_fail_closed() -> None:
    event = {
        "date_precision": "exact_day",
        "sort_date_iso": "2000-01-02",
        "reported_date_raw": "1999-12-31",
        "raw_fields": {"Characteristics": "Lights on object"},
    }
    flags = campaign.field_flags(event, "unknown", False)
    assert flags["reporting_delay_estimable"] is False
    assert flags["light_positive_mention"] is True
    assert flags["sound_raw"] is False
    assert flags["administrative_region"] is False
    assert flags["coordinate_pile_review_state"] is False


def test_initializer_refuses_to_overwrite_completed_wave_history(tmp_path: Path) -> None:
    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True)
    (state_dir / "completed_waves.json").write_text(
        json.dumps({"waves": [{"waveId": "wave-001"}]}),
        encoding="utf-8",
    )
    args = SimpleNamespace(
        detail_root=ROOT,
        analysis_root=ROOT,
        output_root=tmp_path,
        app_config=ROOT / "static_bundle" / "data" / "app_config.json",
        force_reinitialize=False,
    )
    with pytest.raises(RuntimeError, match="Refusing to reinitialize"):
        campaign.build(args)


def test_era_policy_is_deterministic() -> None:
    assert campaign.era_for("1944-12-31") == "pre_1945"
    assert campaign.era_for("1945-01-01") == "1945_1959"
    assert campaign.era_for("2020-01-01") == "2020_plus"
    assert campaign.era_for(None) == "unknown"


def test_authoritative_state_is_pinned_and_self_consistent() -> None:
    current = load("state/current.json")
    completed = load("state/completed_waves.json")
    wave_one_receipt = load("waves/wave-001-duration-assessment/wave_receipt.json")
    wave_two_receipt = load("waves/wave-002-reporting-delay-assessment/wave_receipt.json")
    wave_three_receipt = load("waves/wave-003-coordinate-evidence-repair/wave_receipt.json")
    wave_four_receipt = load("waves/wave-004-time-of-day-assessment/wave_receipt.json")
    wave_five_receipt = load("waves/wave-005-witness-count-assessment/wave_receipt.json")
    wave_six_receipt = load("waves/wave-006-analysis-projection-encoding/wave_receipt.json")
    wave_seven_receipt = load("waves/wave-007-color-assessment/wave_receipt.json")
    wave_eight_receipt = load("waves/wave-008-country-admin-provenance/wave_receipt.json")
    assert current["schemaId"] == campaign.CAMPAIGN_SCHEMA
    assert current["currentProduction"]["baselineCommit"] == campaign.BASELINE_COMMIT
    assert current["currentProduction"]["deploymentId"] == wave_seven_receipt["production"]["deploymentId"]
    assert current["currentProduction"]["frozenTreeSha256"] == wave_seven_receipt["artifacts"]["frozenPagesTreeSha256"]
    assert current["rollbackTarget"]["deploymentId"] == wave_seven_receipt["rollback"]["deploymentId"]
    assert current["rollbackTarget"]["tested"] is True
    assert current["consecutiveNoGainFrontierPasses"] == 1
    assert current["status"] == "active"
    assert len(completed["waves"]) == 8
    assert completed["waves"][0]["waveId"] == "wave-001-duration-assessment"
    assert completed["waves"][0]["status"] == "accepted_and_promoted"
    assert completed["waves"][1]["waveId"] == "wave-002-reporting-delay-assessment"
    assert completed["waves"][1]["status"] == "accepted_and_promoted"
    assert completed["waves"][1]["productionDeploymentId"] == wave_two_receipt["production"]["deploymentId"]
    assert completed["waves"][2]["waveId"] == "wave-003-coordinate-evidence-repair"
    assert completed["waves"][2]["status"] == "accepted_and_promoted"
    assert completed["waves"][2]["productionDeploymentId"] == wave_three_receipt["production"]["deploymentId"]
    assert completed["waves"][3]["waveId"] == "wave-004-time-of-day-assessment"
    assert completed["waves"][3]["status"] == "accepted_and_promoted"
    assert completed["waves"][3]["productionDeploymentId"] == wave_four_receipt["production"]["deploymentId"]
    assert completed["waves"][4]["waveId"] == "wave-005-witness-count-assessment"
    assert completed["waves"][4]["status"] == "accepted_and_promoted"
    assert completed["waves"][4]["productionDeploymentId"] == wave_five_receipt["production"]["deploymentId"]
    assert completed["waves"][5]["waveId"] == "wave-006-analysis-projection-encoding"
    assert completed["waves"][5]["status"] == "accepted_and_promoted"
    assert completed["waves"][5]["productionDeploymentId"] == wave_six_receipt["production"]["deploymentId"]
    assert completed["waves"][6]["waveId"] == "wave-007-color-assessment"
    assert completed["waves"][6]["status"] == "accepted_and_promoted"
    assert completed["waves"][6]["productionDeploymentId"] == wave_seven_receipt["production"]["deploymentId"]
    assert completed["waves"][7]["waveId"] == "wave-008-country-admin-provenance"
    assert completed["waves"][7]["status"] == "completed_no_gain"
    assert completed["waves"][7]["productionDeploymentId"] == wave_eight_receipt["production"]["deploymentId"]
    assert completed["waves"][7]["deploymentPerformed"] is False
    assert wave_one_receipt["production"]["deploymentId"] == wave_two_receipt["rollback"]["deploymentId"]
    assert wave_two_receipt["production"]["deploymentId"] == wave_three_receipt["rollback"]["deploymentId"]
    assert wave_three_receipt["production"]["deploymentId"] == wave_four_receipt["rollback"]["deploymentId"]
    assert wave_four_receipt["production"]["deploymentId"] == wave_five_receipt["rollback"]["deploymentId"]
    assert wave_five_receipt["production"]["deploymentId"] == wave_six_receipt["rollback"]["deploymentId"]
    assert wave_six_receipt["production"]["deploymentId"] == wave_seven_receipt["rollback"]["deploymentId"]
    assert current["activeWave"]["waveId"] == "wave-009-dashboard-density-frontier"
    assert current["nextCandidate"] == current["activeWave"]["candidateId"]
    assert "campaign/analysis_improvement/waves/wave-001-duration-assessment/build_audit.json" in current["packageArtifacts"]
    assert "campaign/analysis_improvement/waves/wave-001-duration-assessment/wave_receipt.json" in current["packageArtifacts"]
    assert "campaign/analysis_improvement/waves/wave-002-reporting-delay-assessment/preregistration.json" in current["packageArtifacts"]
    assert "campaign/analysis_improvement/waves/wave-002-reporting-delay-assessment/build_audit.json" in current["packageArtifacts"]
    assert "campaign/analysis_improvement/waves/wave-002-reporting-delay-assessment/before_after_metrics.json" in current["packageArtifacts"]
    assert "campaign/analysis_improvement/waves/wave-002-reporting-delay-assessment/preview_receipt.json" in current["packageArtifacts"]
    assert "campaign/analysis_improvement/waves/wave-002-reporting-delay-assessment/wave_receipt.json" in current["packageArtifacts"]
    assert "campaign/analysis_improvement/waves/wave-003-coordinate-evidence-repair/preregistration.json" in current["packageArtifacts"]
    assert "campaign/analysis_improvement/waves/wave-003-coordinate-evidence-repair/build_audit.json" in current["packageArtifacts"]
    assert "campaign/analysis_improvement/waves/wave-003-coordinate-evidence-repair/before_after_metrics.json" in current["packageArtifacts"]
    assert "campaign/analysis_improvement/waves/wave-003-coordinate-evidence-repair/preview_receipt.json" in current["packageArtifacts"]
    assert "campaign/analysis_improvement/waves/wave-003-coordinate-evidence-repair/wave_receipt.json" in current["packageArtifacts"]
    assert "campaign/analysis_improvement/waves/wave-004-time-of-day-assessment/preregistration.json" in current["packageArtifacts"]
    assert "campaign/analysis_improvement/waves/wave-004-time-of-day-assessment/build_audit.json" in current["packageArtifacts"]
    assert "campaign/analysis_improvement/waves/wave-004-time-of-day-assessment/before_after_metrics.json" in current["packageArtifacts"]
    assert "campaign/analysis_improvement/waves/wave-004-time-of-day-assessment/preview_receipt.json" in current["packageArtifacts"]
    assert "campaign/analysis_improvement/waves/wave-004-time-of-day-assessment/wave_receipt.json" in current["packageArtifacts"]
    assert "campaign/analysis_improvement/waves/wave-005-witness-count-assessment/preregistration.json" in current["packageArtifacts"]
    assert "campaign/analysis_improvement/waves/wave-005-witness-count-assessment/before_after_metrics.json" in current["packageArtifacts"]
    assert "campaign/analysis_improvement/waves/wave-005-witness-count-assessment/preview_receipt.json" in current["packageArtifacts"]
    assert "campaign/analysis_improvement/waves/wave-005-witness-count-assessment/wave_receipt.json" in current["packageArtifacts"]
    assert "campaign/analysis_improvement/waves/wave-006-analysis-projection-encoding/preregistration.json" in current["packageArtifacts"]
    assert "campaign/analysis_improvement/waves/wave-006-analysis-projection-encoding/baseline_audit.json" in current["packageArtifacts"]
    assert "campaign/analysis_improvement/waves/wave-006-analysis-projection-encoding/encoding_build_receipt.json" in current["packageArtifacts"]
    assert "campaign/analysis_improvement/waves/wave-006-analysis-projection-encoding/before_after_metrics.json" in current["packageArtifacts"]
    assert "campaign/analysis_improvement/waves/wave-006-analysis-projection-encoding/preview_receipt.json" in current["packageArtifacts"]
    assert "campaign/analysis_improvement/waves/wave-006-analysis-projection-encoding/wave_receipt.json" in current["packageArtifacts"]
    assert "campaign/analysis_improvement/waves/wave-007-color-assessment/preregistration.json" in current["packageArtifacts"]
    assert "campaign/analysis_improvement/waves/wave-007-color-assessment/build_audit.json" in current["packageArtifacts"]
    assert "campaign/analysis_improvement/waves/wave-007-color-assessment/parser_contract.json" in current["packageArtifacts"]
    assert "campaign/analysis_improvement/waves/wave-007-color-assessment/raw_value_audit.json" in current["packageArtifacts"]
    assert "campaign/analysis_improvement/waves/wave-007-color-assessment/before_after_metrics.json" in current["packageArtifacts"]
    assert "campaign/analysis_improvement/waves/wave-007-color-assessment/preview_receipt.json" in current["packageArtifacts"]
    assert "campaign/analysis_improvement/waves/wave-007-color-assessment/wave_receipt.json" in current["packageArtifacts"]
    assert "campaign/analysis_improvement/waves/wave-008-country-admin-provenance/preregistration.json" in current["packageArtifacts"]
    assert "campaign/analysis_improvement/waves/wave-008-country-admin-provenance/provenance_audit.json" in current["packageArtifacts"]
    assert "campaign/analysis_improvement/waves/wave-008-country-admin-provenance/wave_receipt.json" in current["packageArtifacts"]
    assert "campaign/analysis_improvement/waves/wave-009-dashboard-density-frontier/preregistration.json" in current["packageArtifacts"]
    for relative, record in current["packageArtifacts"].items():
        path = ROOT / relative
        assert path.stat().st_size == record["bytes"]
        assert sha256(path) == record["sha256"]


def test_coverage_matrix_counts_the_served_catalog_and_keeps_coverage_kinds_distinct() -> None:
    matrix = load("metrics/field_coverage_matrix.json")
    assert matrix["rowCount"] == 702_893
    assert sum(group["rows"] for group in matrix["groups"]) == matrix["rowCount"]
    definitions = {item["field_id"]: item for item in matrix["fieldDefinitions"]}
    assert definitions["light_positive_mention"]["coverage_kind"] == "raw_positive_mention"
    assert definitions["sound_raw"]["coverage_kind"] == "raw_explicit_value"
    assert matrix["overall"]["administrative_region"]["coveredRows"] == 0
    assert matrix["overall"]["coordinate_pile_review_state"]["coveredRows"] == 0


def test_backlog_is_ranked_by_the_declared_formula() -> None:
    backlog = load("state/ranked_backlog.json")
    candidates = backlog["candidates"]
    assert [item["rank"] for item in candidates] == list(range(1, len(candidates) + 1))
    assert [item["score"] for item in candidates] == sorted((item["score"] for item in candidates), reverse=True)
    assert candidates[0]["candidateId"] == "duration_assessment"
    assert candidates[0]["status"] == "completed_accepted_promoted"
    active_candidates = [item for item in candidates if item["status"].startswith("in_progress")]
    assert len(active_candidates) == 1
    assert active_candidates[0]["candidateId"] == load("state/current.json")["nextCandidate"]


def test_duration_wave_is_preregistered_before_implementation() -> None:
    preregistration = load("waves/wave-001-duration-assessment/preregistration.json")
    assert preregistration["candidateId"] == "duration_assessment"
    assert preregistration["beforeMetrics"]["typedDurationRows"] == 0
    assert preregistration["expectedMaterialGain"]["minimumNormalizedRows"] == 232_065
    assert preregistration["expectedMaterialGain"]["minimumIndependentSources"] == 2
    assert "canonical event mutation" in preregistration["interventionBoundary"]["outOfScope"]
    assert "free-text duration inference" in preregistration["interventionBoundary"]["outOfScope"]


def test_reporting_delay_wave_is_preregistered_before_implementation() -> None:
    preregistration = load("waves/wave-002-reporting-delay-assessment/preregistration.json")
    assert preregistration["candidateId"] == "reporting_delay_assessment"
    assert preregistration["beforeMetrics"]["browserTypedReportingDelayRows"] == 0
    assert preregistration["expectedMaterialGain"]["minimumTypedRows"] == 209_065
    assert preregistration["expectedMaterialGain"]["minimumIndependentSources"] == 2
    assert preregistration["expectedMaterialGain"]["dateRolesPreserved"] is True
    assert "treating occurrence date as report or posting date" in preregistration["interventionBoundary"]["outOfScope"]
    assert "coercing negative or ambiguous delays to zero" in preregistration["interventionBoundary"]["outOfScope"]


def test_reporting_delay_receipt_and_coordinate_wave_transition_are_pinned() -> None:
    receipt = load("waves/wave-002-reporting-delay-assessment/wave_receipt.json")
    coordinate = load("waves/wave-003-coordinate-evidence-repair/preregistration.json")
    assert receipt["releaseGate"] == "accepted_and_promoted"
    assert receipt["materialGain"]["passed"] is True
    assert receipt["materialGain"]["evidence"]["typedRows"] == 261_331
    assert receipt["materialGain"]["evidence"]["reportedAndPostedRolesRemainSeparate"] is True
    assert receipt["rollback"]["tested"] is True
    assert coordinate["candidateId"] == "coordinate_evidence_repair"
    assert coordinate["baselineCommit"] == receipt["artifacts"]["candidateCommit"]
    assert coordinate["beforeMetrics"]["sourceCoordinateRows"] == 110_352
    assert coordinate["expectedMaterialGain"]["minimumNormalizedRows"] == 88_281
    assert coordinate["expectedMaterialGain"]["minimumIndependentSources"] == 2
    assert coordinate["expectedMaterialGain"]["generalizedMarkersRemainSeparate"] is True
    assert "external geocoding or reverse-geocoding" in coordinate["interventionBoundary"]["outOfScope"]


def test_coordinate_receipt_and_time_of_day_wave_transition_are_pinned() -> None:
    receipt = load("waves/wave-003-coordinate-evidence-repair/wave_receipt.json")
    time_of_day = load("waves/wave-004-time-of-day-assessment/preregistration.json")
    assert receipt["releaseGate"] == "accepted_and_promoted"
    assert receipt["materialGain"]["passed"] is True
    assert receipt["materialGain"]["evidence"]["typedRows"] == 110_055
    assert receipt["materialGain"]["evidence"]["generalizedMarkerRows"] == 470_431
    assert receipt["materialGain"]["evidence"]["unresolvedRows"] == 122_110
    assert receipt["rollback"]["tested"] is True
    assert time_of_day["candidateId"] == "time_of_day_assessment"
    assert time_of_day["baselineCommit"] == receipt["artifacts"]["candidateCommit"]
    assert time_of_day["beforeMetrics"]["normalizedTimeOfDayCoverageRows"] == 128_013
    assert time_of_day["expectedMaterialGain"]["minimumTypedRows"] == 102_410
    assert time_of_day["expectedMaterialGain"]["minimumIndependentSources"] == 3
    assert time_of_day["expectedMaterialGain"]["timezoneSemanticsRemainUnknownUnlessExplicit"] is True
    assert "timezone inference or UTC conversion" in time_of_day["interventionBoundary"]["outOfScope"]


def test_time_of_day_receipt_and_witness_count_wave_transition_are_pinned() -> None:
    receipt = load("waves/wave-004-time-of-day-assessment/wave_receipt.json")
    witness = load("waves/wave-005-witness-count-assessment/preregistration.json")
    assert receipt["releaseGate"] == "accepted_and_promoted"
    assert receipt["materialGain"]["passed"] is True
    assert receipt["materialGain"]["evidence"]["typedRows"] == 523_077
    assert receipt["materialGain"]["evidence"]["sentinelAmbiguousRows"] == 70_199
    assert receipt["materialGain"]["evidence"]["timezoneSemanticsSeparated"] is True
    assert receipt["rollback"]["tested"] is True
    assert witness["candidateId"] == "witness_count_assessment"
    assert witness["baselineCommit"] == receipt["artifacts"]["candidateCommit"]
    assert witness["beforeMetrics"]["rawWitnessCountRows"] == 145_289
    assert witness["expectedMaterialGain"]["minimumNormalizedRows"] == 116_231
    assert witness["expectedMaterialGain"]["minimumIndependentSources"] == 1
    assert witness["expectedMaterialGain"]["singleSourceComparisonsSuppressed"] is True
    assert "treating missing witness count as zero or one" in witness["interventionBoundary"]["outOfScope"]


def test_witness_count_receipt_and_projection_encoding_wave_transition_are_pinned() -> None:
    receipt = load("waves/wave-005-witness-count-assessment/wave_receipt.json")
    projection = load("waves/wave-006-analysis-projection-encoding/preregistration.json")
    assert receipt["releaseGate"] == "accepted_and_promoted"
    assert receipt["materialGain"]["passed"] is True
    assert receipt["materialGain"]["evidence"]["typedRows"] == 135_868
    assert receipt["materialGain"]["evidence"]["singleSourceComparisonsSuppressed"] is True
    assert receipt["materialGain"]["evidence"]["patternFinderEligible"] is False
    assert receipt["rollback"]["tested"] is True
    assert projection["candidateId"] == "analysis_projection_encoding"
    assert projection["baselineCommit"] == receipt["artifacts"]["candidateCommit"]
    assert projection["beforeMetrics"]["pagesTotalBytes"] == 107_456_540
    assert projection["expectedMaterialGain"]["minimumCompressedTransferReductionPct"] == 10
    assert projection["expectedMaterialGain"]["decodedValueParityRequired"] is True
    assert "lossy numeric quantization, dropped provenance, or changed null and sentinel semantics" in projection["interventionBoundary"]["outOfScope"]


def test_projection_encoding_receipt_and_color_wave_transition_are_pinned() -> None:
    receipt = load("waves/wave-006-analysis-projection-encoding/wave_receipt.json")
    color = load("waves/wave-007-color-assessment/preregistration.json")
    assert receipt["releaseGate"] == "accepted_and_promoted"
    assert receipt["materialGain"]["passed"] is True
    assert receipt["materialGain"]["evidence"]["projectionRows"] == 580_783
    assert receipt["materialGain"]["evidence"]["gzipByteReductionPct"] >= 10
    assert receipt["materialGain"]["evidence"]["decodedValueParityPct"] == 100
    assert receipt["materialGain"]["evidence"]["scientificOutputParityPct"] == 100
    assert receipt["rollback"]["tested"] is True
    assert color["candidateId"] == "typed_observation_assessments"
    assert color["baselineCommit"] == receipt["artifacts"]["candidateCommit"]
    assert color["beforeMetrics"]["rawColorRows"] == 79_215
    assert color["expectedMaterialGain"]["minimumNormalizedRows"] == 63_372
    assert color["expectedMaterialGain"]["minimumIndependentSources"] == 2
    assert color["expectedMaterialGain"]["originalValuesPreserved"] is True
    assert "inferring color from craft type, brightness, illumination, photographs, or chronology prose" in color["interventionBoundary"]["outOfScope"]


def test_color_receipt_and_country_admin_wave_transition_are_pinned() -> None:
    receipt = load("waves/wave-007-color-assessment/wave_receipt.json")
    country = load("waves/wave-008-country-admin-provenance/preregistration.json")
    assert receipt["releaseGate"] == "accepted_and_promoted"
    assert receipt["materialGain"]["passed"] is True
    assert receipt["materialGain"]["evidence"]["normalizedRows"] == 70_097
    assert receipt["materialGain"]["evidence"]["supportedSources"] == ["nuforc", "ufocat"]
    assert receipt["materialGain"]["evidence"]["roleUnspecifiedRows"] == 77_994
    assert receipt["rollback"]["tested"] is True
    assert country["candidateId"] == "country_admin_provenance"
    assert country["baselineCommit"] == receipt["artifacts"]["candidateCommit"]
    assert country["beforeMetrics"]["countryAssignedRows"] == 561_658
    assert country["expectedMaterialGain"]["minimumProvenanceQualifiedRows"] == 548_257
    assert country["expectedMaterialGain"]["exactCountryAssignmentParityRequired"] is True
    assert "online geocoding, silent boundary substitution, nearest-country filling, coastline snapping, or disputed-territory guessing" in country["interventionBoundary"]["outOfScope"]


def test_country_admin_no_gain_and_dashboard_frontier_transition_are_pinned() -> None:
    receipt = load("waves/wave-008-country-admin-provenance/wave_receipt.json")
    dashboard = load("waves/wave-009-dashboard-density-frontier/preregistration.json")
    assert receipt["releaseGate"] == "completed_no_gain_not_deployed"
    assert receipt["materialGain"]["passed"] is False
    assert receipt["materialGain"]["evidence"]["exactUpstreamByteMatch"] is True
    assert receipt["materialGain"]["evidence"]["pinnedExternalReleaseIdentity"] is False
    assert receipt["materialGain"]["evidence"]["rightsEvidenceForExactArtifact"] is False
    assert receipt["materialGain"]["evidence"]["stableUniqueBoundaryIdentifiers"] is False
    assert receipt["production"]["unchanged"] is True
    assert receipt["deployment"]["previewCreated"] is False
    assert dashboard["candidateId"] == "dashboard_density_refinement"
    assert dashboard["baselineCommit"] == "a14889b428f18c399db0b8b884a6f88dea1e2c8a"
    assert dashboard["beforeMetrics"]["maximumDashboardHeightPx"] == 874.859375
    assert dashboard["expectedMaterialGain"]["minimumImprovementPct"] == 10.0
    assert dashboard["expectedMaterialGain"]["informationAndControlParityRequired"] is True


def test_module_registry_preserves_forbidden_claims_and_suppression() -> None:
    registry = load("state/module_readiness.json")
    assert "inferred_travel" in registry["forbiddenClaims"]
    assert "causal_facility_interpretation" in registry["forbiddenClaims"]
    for module in registry["candidateModules"]:
        assert module["suppressionPolicy"]
        assert module["uncertaintyTreatment"]
        assert module["negativeControls"]

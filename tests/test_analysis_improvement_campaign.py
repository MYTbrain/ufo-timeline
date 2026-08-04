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
    assert current["schemaId"] == campaign.CAMPAIGN_SCHEMA
    assert current["currentProduction"]["baselineCommit"] == campaign.BASELINE_COMMIT
    assert current["currentProduction"]["deploymentId"] == wave_two_receipt["production"]["deploymentId"]
    assert current["currentProduction"]["frozenTreeSha256"] == wave_two_receipt["artifacts"]["frozenPagesTreeSha256"]
    assert current["rollbackTarget"]["deploymentId"] == wave_two_receipt["rollback"]["deploymentId"]
    assert current["rollbackTarget"]["tested"] is True
    assert current["consecutiveNoGainFrontierPasses"] == 0
    assert current["status"] == "active"
    assert len(completed["waves"]) == 2
    assert completed["waves"][0]["waveId"] == "wave-001-duration-assessment"
    assert completed["waves"][0]["status"] == "accepted_and_promoted"
    assert completed["waves"][1]["waveId"] == "wave-002-reporting-delay-assessment"
    assert completed["waves"][1]["status"] == "accepted_and_promoted"
    assert completed["waves"][1]["productionDeploymentId"] == wave_two_receipt["production"]["deploymentId"]
    assert wave_one_receipt["production"]["deploymentId"] == wave_two_receipt["rollback"]["deploymentId"]
    assert current["activeWave"]["waveId"] == "wave-003-coordinate-evidence-repair"
    assert current["nextCandidate"] == current["activeWave"]["candidateId"]
    assert "campaign/analysis_improvement/waves/wave-001-duration-assessment/build_audit.json" in current["packageArtifacts"]
    assert "campaign/analysis_improvement/waves/wave-001-duration-assessment/wave_receipt.json" in current["packageArtifacts"]
    assert "campaign/analysis_improvement/waves/wave-002-reporting-delay-assessment/preregistration.json" in current["packageArtifacts"]
    assert "campaign/analysis_improvement/waves/wave-002-reporting-delay-assessment/build_audit.json" in current["packageArtifacts"]
    assert "campaign/analysis_improvement/waves/wave-002-reporting-delay-assessment/before_after_metrics.json" in current["packageArtifacts"]
    assert "campaign/analysis_improvement/waves/wave-002-reporting-delay-assessment/preview_receipt.json" in current["packageArtifacts"]
    assert "campaign/analysis_improvement/waves/wave-002-reporting-delay-assessment/wave_receipt.json" in current["packageArtifacts"]
    assert "campaign/analysis_improvement/waves/wave-003-coordinate-evidence-repair/preregistration.json" in current["packageArtifacts"]
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
    active_candidates = [item for item in candidates if item["status"] == "in_progress"]
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


def test_module_registry_preserves_forbidden_claims_and_suppression() -> None:
    registry = load("state/module_readiness.json")
    assert "inferred_travel" in registry["forbiddenClaims"]
    assert "causal_facility_interpretation" in registry["forbiddenClaims"]
    for module in registry["candidateModules"]:
        assert module["suppressionPolicy"]
        assert module["uncertaintyTreatment"]
        assert module["negativeControls"]

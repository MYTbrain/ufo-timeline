from __future__ import annotations

import hashlib
import json
from pathlib import Path

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


def test_era_policy_is_deterministic() -> None:
    assert campaign.era_for("1944-12-31") == "pre_1945"
    assert campaign.era_for("1945-01-01") == "1945_1959"
    assert campaign.era_for("2020-01-01") == "2020_plus"
    assert campaign.era_for(None) == "unknown"


def test_authoritative_state_is_pinned_and_self_consistent() -> None:
    current = load("state/current.json")
    assert current["schemaId"] == campaign.CAMPAIGN_SCHEMA
    assert current["currentProduction"]["baselineCommit"] == campaign.BASELINE_COMMIT
    assert current["currentProduction"]["deploymentId"] == campaign.PRODUCTION_DEPLOYMENT_ID
    assert current["currentProduction"]["frozenTreeSha256"] == campaign.FROZEN_TREE_SHA256
    assert current["rollbackTarget"]["deploymentId"] == campaign.ROLLBACK_DEPLOYMENT_ID
    assert current["consecutiveNoGainFrontierPasses"] == 0
    assert current["status"] == "active"
    assert current["activeWave"]["waveId"] == "wave-001-duration-assessment"
    assert current["nextCandidate"] == current["activeWave"]["candidateId"]
    assert "campaign/analysis_improvement/waves/wave-001-duration-assessment/build_audit.json" in current["packageArtifacts"]
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
    assert candidates[0]["candidateId"] == load("state/current.json")["nextCandidate"]
    assert candidates[0]["status"] == "in_progress"


def test_duration_wave_is_preregistered_before_implementation() -> None:
    preregistration = load("waves/wave-001-duration-assessment/preregistration.json")
    assert preregistration["candidateId"] == "duration_assessment"
    assert preregistration["beforeMetrics"]["typedDurationRows"] == 0
    assert preregistration["expectedMaterialGain"]["minimumNormalizedRows"] == 232_065
    assert preregistration["expectedMaterialGain"]["minimumIndependentSources"] == 2
    assert "canonical event mutation" in preregistration["interventionBoundary"]["outOfScope"]
    assert "free-text duration inference" in preregistration["interventionBoundary"]["outOfScope"]


def test_module_registry_preserves_forbidden_claims_and_suppression() -> None:
    registry = load("state/module_readiness.json")
    assert "inferred_travel" in registry["forbiddenClaims"]
    assert "causal_facility_interpretation" in registry["forbiddenClaims"]
    for module in registry["candidateModules"]:
        assert module["suppressionPolicy"]
        assert module["uncertaintyTreatment"]
        assert module["negativeControls"]

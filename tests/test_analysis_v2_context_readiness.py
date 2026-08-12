from __future__ import annotations

import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
BUILDER_PATH = REPO_ROOT / "scripts" / "build_analysis_v2_artifacts.py"


def load_builder():
    spec = importlib.util.spec_from_file_location("analysis_v2_context_readiness_builder", BUILDER_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


BUILDER = load_builder()
EVIDENCE_HASH = "a" * 64


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


def write_detail_layer(root: Path, domain: str, records: dict[str, dict]) -> None:
    layer = root / domain
    layer.mkdir(parents=True)
    raw = json.dumps(records, sort_keys=True, separators=(",", ":")).encode("utf-8")
    compressed = gzip.compress(raw, mtime=0)
    (layer / "details-000.json.gz").write_bytes(compressed)
    (layer / "manifest.json").write_text(
        json.dumps({
            "details": {"files": [{
                "path": "details-000.json.gz",
                "sha256": hashlib.sha256(compressed).hexdigest(),
            }]},
            "releaseId": f"{domain}-fixture",
        }),
        encoding="utf-8",
    )


def accepted_case_rows(domain: str, case_id: str, fields: dict[str, object]) -> tuple[list[dict], list[dict]]:
    assertions: list[dict] = []
    decisions: list[dict] = []
    for index, (field_name, value) in enumerate(fields.items(), start=1):
        assertion_id = f"assertion-{domain}-{index}"
        assertions.append({
            "assertionId": assertion_id,
            "caseId": case_id,
            "domain": domain,
            "evidenceSha256": [EVIDENCE_HASH],
            "fieldName": field_name,
            "sourceIds": ["src_official"],
            "value": value,
        })
        for reviewer in ("agent-alpha", "agent-beta"):
            decisions.append({
                "assertionId": assertion_id,
                "caseId": case_id,
                "decisionId": f"decision-{domain}-{index}-{reviewer}",
                "domain": domain,
                "frozenEvidenceSha256": [EVIDENCE_HASH],
                "outcome": "accepted",
                "reviewer": {"reviewerId": reviewer, "reviewerType": "agent"},
                "supersedesDecisionIds": [],
            })
    return assertions, decisions


def append_rejected_assertion(
    ledger_root: Path,
    *,
    domain: str,
    case_id: str,
    field_name: str,
    value: object,
) -> None:
    assertion_id = f"assertion-{domain}-rejected-{field_name}"
    assertion = {
        "assertionId": assertion_id,
        "caseId": case_id,
        "domain": domain,
        "evidenceSha256": [EVIDENCE_HASH],
        "fieldName": field_name,
        "sourceIds": ["src_official"],
        "value": value,
    }
    decision = {
        "assertionId": assertion_id,
        "caseId": case_id,
        "decisionId": f"decision-{domain}-rejected-{field_name}",
        "domain": domain,
        "frozenEvidenceSha256": [EVIDENCE_HASH],
        "outcome": "rejected",
        "reviewer": {"reviewerId": "human-adjudicator", "reviewerType": "human"},
        "supersedesDecisionIds": [],
    }
    for filename, row in (
        ("case_enrichment.jsonl", assertion),
        ("case_review_decisions.jsonl", decision),
    ):
        path = ledger_root / filename
        path.write_text(
            path.read_text(encoding="utf-8")
            + json.dumps(row, sort_keys=True, separators=(",", ":"))
            + "\n",
            encoding="utf-8",
        )


def write_accepted_fixture(ledger_root: Path) -> None:
    source = {
        "independenceStatus": "independent",
        "sourceFamilyId": "family_official",
        "sourceId": "src_official",
        "sourceTier": "official",
    }
    crop_assertions, crop_decisions = accepted_case_rows("crop", "cc_fixture", {
        "formation_date": "2001-05-06",
        "latitude": 40.25,
        "longitude": -100.75,
        "coordinate_uncertainty_m": 75,
        "coordinate_method": "surveyed_source_site",
        "dedup_cluster_id": "crop-cluster-1",
    })
    animal_assertions, animal_decisions = accepted_case_rows("animal", "ami_fixture", {
        "occurrence_date": "2002-06-07",
        "latitude": 41.5,
        "longitude": -101.5,
        "coordinate_uncertainty_m": 800,
        "coordinate_method": "official_incident_coordinates",
        "dedup_cluster_id": "animal-cluster-1",
    })
    write_jsonl(ledger_root / "source_ledger.jsonl", [source])
    write_jsonl(ledger_root / "case_enrichment.jsonl", crop_assertions + animal_assertions)
    write_jsonl(ledger_root / "case_review_decisions.jsonl", crop_decisions + animal_decisions)


def test_accepted_frozen_assertions_generate_strict_crop_and_animal_tiers(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    ledger_root = tmp_path / "ledgers"
    write_detail_layer(source_root, "crop_circles", {
        "cc_fixture": {
            "classification": "unreviewed",
            "datePrecision": "year",
            "dateRole": "catalog_unspecified",
            "sources": [],
        },
    })
    write_detail_layer(source_root, "animal_mutilations", {
        "animal_mutilation:ami_fixture": {
            "datePrecision": "unknown",
            "sourceRefs": [],
            "status": "reported_unreviewed",
            "traceEligible": False,
            "causality": "not_asserted",
        },
    })
    write_accepted_fixture(ledger_root)

    crops, crop_source = BUILDER.build_crop_context_projection(source_root, ledger_root)
    animals, animal_source, _incident_map = BUILDER.build_animal_context_projection(
        source_root, ledger_root
    )

    crop = crops[0]
    assert crop["analysisTierCode"] == crop["analysisLaneCode"] == "crop_strict"
    assert crop["coordinateEvidenceClassCode"] == "source_exact"
    assert crop["coordinateMethodCode"] == "surveyed_source_site"
    assert crop["coordinateUncertaintyM"] == 75.0
    assert crop["dateRoleCode"] == "formation_date"
    assert crop["reviewStateCode"] == "source_reviewed"
    assert crop["sourceFamilyIds"] == ["family_official"]
    assert crop["independenceStatusCode"] == "single_independent_source_family"
    assert crop["dedupStatusCode"] == "resolved_cluster"
    assert crop["kilometerEligible"] is True
    assert crop["exclusionReasonCodes"] == []

    animal = animals[0]
    assert animal["analysisTierCode"] == animal["analysisLaneCode"] == "animal_strict"
    assert animal["coordinateEvidenceClassCode"] == "source_bounded"
    assert animal["coordinateUncertaintyM"] == 800.0
    assert animal["dateRoleCode"] == "occurrence_date"
    assert animal["reviewStateCode"] == "source_reviewed"
    assert animal["kilometerEligible"] is True
    assert animal["exclusionReasonCodes"] == []
    assert crop_source["counts"]["strictReady"] == 1
    assert animal_source["counts"]["strictReady"] == 1
    assert crop_source["policy"]["traceEligible"] is False
    assert animal_source["policy"]["traceEligible"] is False
    assert animal_source["policy"]["relationshipsEligible"] is False


def test_rejected_critical_claim_does_not_block_valid_strict_claim(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    ledger_root = tmp_path / "ledgers"
    write_detail_layer(source_root, "crop_circles", {
        "cc_fixture": {
            "classification": "unreviewed",
            "datePrecision": "year",
            "dateRole": "catalog_unspecified",
            "sources": [],
        },
    })
    write_detail_layer(source_root, "animal_mutilations", {
        "animal_mutilation:ami_fixture": {
            "datePrecision": "unknown",
            "sourceRefs": [],
            "status": "reported_unreviewed",
            "traceEligible": False,
            "causality": "not_asserted",
        },
    })
    write_accepted_fixture(ledger_root)
    append_rejected_assertion(
        ledger_root,
        domain="crop",
        case_id="cc_fixture",
        field_name="formation_date",
        value="2001-05-07",
    )
    append_rejected_assertion(
        ledger_root,
        domain="animal",
        case_id="ami_fixture",
        field_name="occurrence_date",
        value="2002-06-08",
    )

    crops, crop_source = BUILDER.build_crop_context_projection(source_root, ledger_root)
    animals, animal_source, _incident_map = BUILDER.build_animal_context_projection(
        source_root, ledger_root
    )

    assert crops[0]["analysisTierCode"] == "crop_strict"
    assert animals[0]["analysisTierCode"] == "animal_strict"
    assert "unresolved_identity_date_or_coordinate_conflict" not in crops[0]["exclusionReasonCodes"]
    assert "unresolved_identity_date_or_coordinate_conflict" not in animals[0]["exclusionReasonCodes"]
    assert crop_source["counts"]["strictReady"] == 1
    assert animal_source["counts"]["strictReady"] == 1


@pytest.mark.parametrize(
    ("domain", "date_role"),
    (("crop", "formation_date"), ("animal", "occurrence_date")),
)
def test_reviewed_duplicate_is_excluded_from_every_analysis_tier(
    domain: str,
    date_role: str,
) -> None:
    quality = BUILDER.context_quality_state(
        domain,
        {},
        {
            "fields": {
                "duplicate_of_case_id": {
                    "value": f"{'cc' if domain == 'crop' else 'ami'}_canonical",
                    "sourceIds": ["src_official"],
                    "reviewState": "source_reviewed",
                },
            },
            "reviewState": "source_reviewed",
            "sourceFamilyIds": ["family_official"],
            "independenceStatus": "single_independent_source_family",
            "sourceGateSatisfied": True,
        },
        {
            "coordinateEvidenceClassCode": "source_exact",
            "coordinateEvidenceCode": "exact_source_coordinate",
            "coordinateMethodCode": "surveyed_source_site",
            "coordinateProvenanceComplete": True,
            "coordinateUncertaintyM": 75.0,
            "lat": 40.25,
            "lon": -100.75,
        },
        start=730_000,
        end=730_000,
        date_precision="exact_day",
        date_role=date_role,
        date_provenance_complete=True,
    )

    assert quality["dedupStatusCode"] == "duplicate"
    assert quality["analysisTierCode"] == quality["analysisLaneCode"] == "excluded"
    assert quality["kilometerEligible"] is False
    assert quality["exclusionReasonCodes"] == [
        "deduplication_not_resolved",
        "duplicate_record_excluded_from_analysis",
    ]


def test_active_agent_disagreement_blocks_source_reviewed_promotion(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    ledger_root = tmp_path / "ledgers"
    write_detail_layer(source_root, "crop_circles", {
        "cc_fixture": {
            "classification": "unreviewed",
            "datePrecision": "year",
            "dateRole": "catalog_unspecified",
            "sources": [],
        },
    })
    fields = {
        "formation_date": "2001-05-06",
        "latitude": 40.25,
        "longitude": -100.75,
        "coordinate_uncertainty_m": 75,
        "coordinate_method": "surveyed_source_site",
        "dedup_cluster_id": "crop-cluster-1",
    }
    assertions, decisions = accepted_case_rows("crop", "cc_fixture", fields)
    disputed = dict(decisions[0])
    disputed["decisionId"] = "decision-crop-1-agent-gamma"
    disputed["outcome"] = "rejected"
    disputed["reviewer"] = {"reviewerId": "agent-gamma", "reviewerType": "agent"}
    decisions.append(disputed)
    write_jsonl(ledger_root / "source_ledger.jsonl", [{
        "independenceStatus": "independent",
        "sourceFamilyId": "family_official",
        "sourceId": "src_official",
        "sourceTier": "official",
    }])
    write_jsonl(ledger_root / "case_enrichment.jsonl", assertions)
    write_jsonl(ledger_root / "case_review_decisions.jsonl", decisions)

    crops, source = BUILDER.build_crop_context_projection(source_root, ledger_root)

    assert crops[0]["analysisTierCode"] != "crop_strict"
    assert "date_not_exact_occurrence_day" in crops[0]["exclusionReasonCodes"]
    assert source["counts"]["strictReady"] == 0


def test_current_public_baseline_remains_zero_strict_with_explicit_quality_fields() -> None:
    crops, _crop_source = BUILDER.build_crop_context_projection(BUILDER.STATIC_DATA_ROOT, None)
    animals, _animal_source, _incident_map = BUILDER.build_animal_context_projection(
        BUILDER.STATIC_DATA_ROOT, None
    )

    assert sum(row["analysisTierCode"] == "crop_strict" for row in crops) == 0
    assert sum(row["analysisTierCode"] == "animal_strict" for row in animals) == 0
    assert sum(row["analysisTierCode"] == "crop_bounded" for row in crops) == 433
    assert sum(row["analysisTierCode"] == "crop_locality" for row in crops) == 3225
    assert sum(row["analysisTierCode"] == "animal_public_marker" for row in animals) == 339
    for row in (crops[0], animals[0]):
        assert row["analysisTierCode"] in BUILDER.CONTEXT_ANALYSIS_TIERS
        assert "coordinateEvidenceClassCode" in row
        assert "coordinateMethodCode" in row
        assert "coordinateUncertaintyM" in row
        assert "sourceFamilyIds" in row
        assert "independenceStatusCode" in row
        assert "dedupStatusCode" in row
        assert row["exclusionReasonCodes"]


def test_conflicting_accepted_values_fail_closed(tmp_path: Path) -> None:
    ledger_root = tmp_path / "ledgers"
    write_jsonl(ledger_root / "source_ledger.jsonl", [{
        "independenceStatus": "independent",
        "sourceFamilyId": "family_official",
        "sourceId": "src_official",
        "sourceTier": "official",
    }])
    assertions: list[dict] = []
    decisions: list[dict] = []
    for index, latitude in enumerate((40.0, 41.0), start=1):
        assertion_id = f"conflict-{index}"
        assertions.append({
            "assertionId": assertion_id,
            "caseId": "cc_conflict",
            "domain": "crop",
            "evidenceSha256": [EVIDENCE_HASH],
            "fieldName": "latitude",
            "sourceIds": ["src_official"],
            "value": latitude,
        })
        for reviewer in ("agent-alpha", "agent-beta"):
            decisions.append({
                "assertionId": assertion_id,
                "caseId": "cc_conflict",
                "decisionId": f"decision-{index}-{reviewer}",
                "domain": "crop",
                "frozenEvidenceSha256": [EVIDENCE_HASH],
                "outcome": "accepted",
                "reviewer": {"reviewerId": reviewer, "reviewerType": "agent"},
                "supersedesDecisionIds": [],
            })
    write_jsonl(ledger_root / "case_enrichment.jsonl", assertions)
    write_jsonl(ledger_root / "case_review_decisions.jsonl", decisions)

    with pytest.raises(ValueError, match="Conflicting accepted context assertions"):
        BUILDER.load_context_evidence(ledger_root)


def test_wave4_associated_claims_remain_additive_in_analysis_loader(tmp_path: Path) -> None:
    ledger_root = tmp_path / "ledgers"
    write_jsonl(ledger_root / "source_ledger.jsonl", [{
        "independenceStatus": "independent",
        "sourceFamilyId": "family_official",
        "sourceId": "src_official",
        "sourceTier": "official",
    }])
    claims = [
        {"claimType": "campaign_identity", "value": "Bacardi Seven Tiki"},
        {
            "claimType": "source_lineage_or_scope_decision",
            "status": "count_as_one_family_pending_separate_evidence",
        },
    ]
    assertions: list[dict] = []
    decisions: list[dict] = []
    for index, claim in enumerate(claims, start=1):
        assertion_id = f"wave4-claim-{index}"
        assertions.append({
            "assertionId": assertion_id,
            "caseId": "cc_wave4",
            "domain": "crop",
            "evidenceSha256": [EVIDENCE_HASH],
            "fieldName": "associated_claim",
            "sourceIds": ["src_official"],
            "value": claim,
        })
        for reviewer in ("agent-alpha", "agent-beta"):
            decisions.append({
                "assertionId": assertion_id,
                "caseId": "cc_wave4",
                "decisionId": f"decision-{index}-{reviewer}",
                "domain": "crop",
                "frozenEvidenceSha256": [EVIDENCE_HASH],
                "outcome": "accepted",
                "reviewer": {"reviewerId": reviewer, "reviewerType": "agent"},
                "supersedesDecisionIds": [],
            })
    write_jsonl(ledger_root / "case_enrichment.jsonl", assertions)
    write_jsonl(ledger_root / "case_review_decisions.jsonl", decisions)

    evidence, metadata = BUILDER.load_context_evidence(ledger_root)

    expected = sorted(claims, key=BUILDER.canonical_json_bytes)
    assert evidence[("crop", "cc_wave4")]["fields"]["associated_claim"]["value"] == expected
    assert metadata["activeAcceptedAssertions"] == 1


def test_new_case_bootstrap_projects_and_legal_restriction_stays_non_public(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    ledger_root = tmp_path / "ledgers"
    write_detail_layer(source_root, "crop_circles", {})
    write_detail_layer(source_root, "animal_mutilations", {})
    write_jsonl(ledger_root / "source_ledger.jsonl", [{
        "independenceStatus": "same_family",
        "sourceFamilyId": "family_official",
        "sourceId": "src_official",
        "sourceTier": "official",
    }])
    public_fields = {
        "source_case_identifier": "official-case-1",
        "public_title": "Reviewed incident",
        "primary_classification": "animal_mutilation_report",
        "animal_species": "cattle",
        "occurrence_date": "2002-06-07",
        "location_label": "County-level incident site",
        "latitude": 41.5,
        "longitude": -101.5,
        "coordinate_uncertainty_m": 800,
        "coordinate_method": "official_incident_coordinates",
        "dedup_cluster_id": "animal-cluster-new-1",
    }
    restricted_fields = dict(public_fields)
    restricted_fields["source_case_identifier"] = "official-case-2"
    restricted_fields["legal_publication_restriction"] = True
    assertions: list[dict] = []
    decisions: list[dict] = []
    for case_id, fields in (("ami_newpublic", public_fields), ("ami_restricted", restricted_fields)):
        case_assertions, case_decisions = accepted_case_rows("animal", case_id, fields)
        # accepted_case_rows uses IDs based only on the field index; make them
        # stable and unique across the two fixture cases.
        for assertion in case_assertions:
            old_id = assertion["assertionId"]
            new_id = old_id + "-" + case_id
            assertion["assertionId"] = new_id
            for decision in case_decisions:
                if decision["assertionId"] == old_id:
                    decision["assertionId"] = new_id
                    decision["decisionId"] += "-" + case_id
        assertions.extend(case_assertions)
        decisions.extend(case_decisions)
    write_jsonl(ledger_root / "case_enrichment.jsonl", assertions)
    write_jsonl(ledger_root / "case_review_decisions.jsonl", decisions)

    animals, source, incident_map = BUILDER.build_animal_context_projection(source_root, ledger_root)

    assert [row["id"] for row in animals] == ["animal_mutilation:ami_newpublic"]
    assert animals[0]["analysisTierCode"] == "animal_strict"
    assert incident_map == {"official-case-1": "animal_mutilation:ami_newpublic"}
    assert source["contextEvidence"]["newCasesProjected"] == 1
    assert source["contextEvidence"]["legalPublicationRestrictedCasesWithheld"] == 1


def test_context_pulse_summary_uses_domain_counts_and_preserves_frozen_release_delta() -> None:
    legacy = {
        "counts": {
            "animalPublicMarkerAnalysisRecords": 339,
            "animalStrictAnalysisRecords": 0,
            "cropBoundedAnalysisRecords": 406,
            "cropLocalityAnalysisRecords": 3249,
            "cropStrictAnalysisRecords": 0,
            "facilityInferentialEligible": 70,
            "facilityMarkers": 1800,
        },
        "releaseId": "analysis-old",
        "sources": {
            "animalContext": {"rowCount": 1177},
            "cropContext": {"rowCount": 7745},
            "facilities": {"counts": {"inferentialEligible": 70, "rows": 1800}},
        },
    }
    crop = {
        "counts": {
            "activeInventory": 7750,
            "mapped": 4310,
            "sensitivityReady": 3660,
            "strictReady": 25,
        },
        "readiness": {"leadingExclusionReasons": [{"count": 7000, "reasonCode": "formation_date_missing"}]},
    }
    animal = {
        "counts": {
            "activeInventory": 1202,
            "mapped": 543,
            "sensitivityReady": 342,
            "strictReady": 25,
        },
        "readiness": {"leadingExclusionReasons": [{"count": 900, "reasonCode": "site_uncertainty_too_large"}]},
    }
    facilities = {
        "counts": {"inferentialEligible": 70, "rows": 1800},
        "readiness": {"gates": [{"reasonCodes": ["claimed_sites_descriptive_only"]}]},
    }

    summary = BUILDER.build_context_pulse_summary(
        release_id="analysis-new",
        crop_source=crop,
        animal_source=animal,
        facility_source=facilities,
        previous_manifest=legacy,
    )

    assert summary["domains"]["crops"]["inventoryN"] == 7750
    assert summary["domains"]["crops"]["mappedN"] == 4310
    assert summary["domains"]["crops"]["releaseDelta"] == {
        "inventoryN": 5,
        "sensitivityReadyN": 5,
        "strictReadyN": 25,
    }
    assert summary["domains"]["animals"]["releaseDelta"]["inventoryN"] == 25
    assert summary["domains"]["facilities"]["strictReadyN"] == 70
    assert summary["domains"]["facilities"]["releaseDelta"]["strictReadyN"] == 0
    assert summary["domains"]["crops"]["exclusionReasonCodes"] == ["formation_date_missing"]

    rebuilt = BUILDER.build_context_pulse_summary(
        release_id="analysis-new",
        crop_source=crop,
        animal_source=animal,
        facility_source=facilities,
        previous_manifest={"contextPulseSummary": summary, "releaseId": "analysis-new"},
    )
    assert rebuilt == summary


def test_strict_neighbor_projection_keeps_uncertainty_margin_and_context_holdout_groups() -> None:
    ordinal = BUILDER.date(2000, 1, 1).toordinal()
    crop = {
        "analysisLaneCode": "crop_strict",
        "coordinateUncertaintyKm": 1.0,
        "featureGroupCode": "radial_rosette_or_star",
        "id": "cc_strict_fixture",
        "lat": 0.0,
        "locationDateClusterId": "strict-crop-cluster",
        "lon": 0.0,
        "sourceFamilyIds": ["sf_fixture"],
        "startOrdinal": ordinal,
    }
    points = [
        {
            "coarseSpatialStratumCode": "ufo-coarse",
            "craftCode": "triangle",
            "eventId": 1,
            "fineSpatialStratumCode": "ufo-fine",
            "lat": 0.0,
            "lon": 0.1,
            "ordinal": ordinal,
            "sourceCode": "source-a",
        },
        {
            "coarseSpatialStratumCode": "ufo-coarse",
            "craftCode": "disc_saucer",
            "eventId": 2,
            "fineSpatialStratumCode": "ufo-fine",
            "lat": 0.0,
            "lon": 2.252,
            "ordinal": ordinal,
            "sourceCode": "source-b",
        },
    ]

    rows, source = BUILDER.build_context_ufo_neighbor_projection(points, [crop], [])
    observed = [row for row in rows if row["dateRoleCode"] == "observed_formation_date"]

    assert len(observed) == 2
    definite = next(row for row in observed if row["ufoEventId"] == 1)
    margin = next(row for row in observed if row["ufoEventId"] == 2)
    assert definite["uncertaintyClassCode"] == "definitely_near_at_250km"
    assert margin["distanceDecameters"] > 25_000
    assert margin["distanceRingCode"] == "outside_250km_uncertainty_margin"
    assert margin["uncertaintyClassCode"] == "ambiguous_at_250km"
    assert definite["contextSourceFamilyGroupCode"] == "sf_fixture"
    assert definite["contextCoarseSpatialStratumCode"].startswith("ea6x12:")
    assert source["counts"]["strictContextClustersByDomain"] == {"animal": 0, "crop": 1}
    assert source["readiness"]["status"] == "exploratory_sensitivity_pool"

from __future__ import annotations

import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_script(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


CROP = load_script(
    "context_crop_public_builder",
    REPO_ROOT / "scripts" / "build_crop_circle_web_artifacts.py",
)
ANIMAL = load_script(
    "context_animal_public_builder",
    REPO_ROOT / "scripts" / "build_animal_mutilation_web_artifacts.py",
)


def read_gzip_json(path: Path):
    return json.loads(gzip.decompress(path.read_bytes()))


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")), encoding="utf-8")


def empty_ledgers(root: Path) -> Path:
    root.mkdir(parents=True)
    for name in (
        "source_ledger.jsonl", "case_enrichment.jsonl", "case_review_decisions.jsonl",
        "research_queue.jsonl",
    ):
        (root / name).write_text("", encoding="utf-8")
    return root


def write_reviewed_ledgers(
    root: Path,
    *,
    domain: str,
    case_id: str,
    fields: dict[str, object],
    accepted_new: bool,
) -> Path:
    root.mkdir(parents=True)
    source_id = "src_" + "1" * 16
    family_id = "sf_" + "2" * 16
    evidence_hash = "3" * 64
    source = {
        "schemaId": "ufo-timeline-context-evidence-source-v1.0.0",
        "sourceId": source_id,
        "sourceFamilyId": family_id,
        "title": "Official incident report",
        "publisher": "Public agency",
        "publicationDate": "1980-06-01",
        "authors": ["Report author"],
        "locator": {
            "kind": "url", "value": "https://example.test/report",
            "accessedAt": "2026-08-10", "pageOrSection": "incident table",
        },
        "accessStatus": "retrieved",
        "contentSha256": evidence_hash,
        "sourceTier": "official",
        "rights": {
            "status": "public_domain", "redistributionAllowed": True,
            "license": None, "notes": None,
        },
        "retention": {
            "class": "canonical_source", "storageLocation": "D:\\UFO-Timeline-Context-Evidence\\source",
            "decision": "retain canonical evidence",
        },
        "derivation": {"derivedFromSourceIds": [], "relation": "original"},
        "independenceStatus": "independent",
        "registeredAt": "2026-08-10T12:00:00Z",
    }
    assertions: list[dict[str, object]] = []
    decisions: list[dict[str, object]] = []
    for index, (field_name, value) in enumerate(sorted(fields.items()), start=1):
        identity = hashlib.sha256(f"{domain}:{case_id}:{field_name}".encode()).hexdigest()[:16]
        assertion_id = f"cea_{identity}"
        assertions.append({
            "schemaId": "ufo-timeline-context-evidence-assertion-v1.0.0",
            "assertionId": assertion_id,
            "caseId": case_id,
            "domain": domain,
            "fieldName": field_name,
            "value": value,
            "sourceIds": [source_id],
            "sourceLocators": [{"sourceId": source_id, "locator": f"field {field_name}"}],
            "confidence": "high",
            "polarity": "supports",
            "evidenceSha256": [evidence_hash],
            "waveId": "wave-001-public-builders",
            "assertedAt": "2026-08-10T12:01:00Z",
        })
        decisions.append({
            "schemaId": "ufo-timeline-context-evidence-review-decision-v1.0.0",
            "decisionId": "crd_" + hashlib.sha256(f"decision:{identity}".encode()).hexdigest()[:16],
            "assertionId": assertion_id,
            "caseId": case_id,
            "domain": domain,
            "outcome": "accepted",
            "reviewer": {"reviewerId": "fixture-human", "reviewerType": "human", "runId": None},
            "frozenEvidenceSha256": [evidence_hash],
            "reasonCodes": ["source_matches_assertion"],
            "supersedesDecisionIds": [],
            "duplicateOfCaseId": None,
            "decidedAt": f"2026-08-10T12:{index + 1:02d}:00Z",
        })
    queue: list[dict[str, object]] = []
    if accepted_new:
        queue.append({
            "schemaId": "ufo-timeline-context-evidence-research-queue-v1.0.0",
            "queueId": "rq_" + "4" * 16,
            "caseId": case_id,
            "candidateId": None,
            "domain": domain,
            "lane": "case_enrichment",
            "caseClass": "accepted_new_source",
            "missingStrictGates": ["review_quorum"],
            "priorityInputs": {
                "missingStrictGateCount": 1, "independentSourceFamilyCount": 1,
                "exactOccurrenceDay": True, "sourceSupportedCoordinate": True,
            },
            "priorityScore": 1,
            "rank": 1,
            "queryBudget": {
                "firstPassQueries": 2, "firstPassSourceOpenings": 4,
                "escalationQueries": 3, "escalationSourceOpenings": 4,
                "archiveFallbacks": 1, "escalationApproved": False,
            },
            "attempts": [],
            "waveId": "wave-001-public-builders",
            "status": "strict_ready",
            "terminalDisposition": "strict_ready",
            "createdAt": "2026-08-10T12:00:00Z",
            "updatedAt": "2026-08-10T12:30:00Z",
        })
    for name, rows in (
        ("source_ledger.jsonl", [source]),
        ("case_enrichment.jsonl", assertions),
        ("case_review_decisions.jsonl", decisions),
        ("research_queue.jsonl", queue),
    ):
        (root / name).write_text(
            "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows),
            encoding="utf-8",
        )
    return root


def write_two_reviewed_values(
    root: Path,
    *,
    domain: str,
    case_id: str,
    field_name: str,
    values: list[object],
) -> Path:
    root = write_reviewed_ledgers(
        root,
        domain=domain,
        case_id=case_id,
        fields={field_name: values[0]},
        accepted_new=False,
    )
    source = json.loads((root / "source_ledger.jsonl").read_text(encoding="utf-8"))
    source_id = source["sourceId"]
    evidence_hash = source["contentSha256"]
    assertions: list[dict[str, object]] = []
    decisions: list[dict[str, object]] = []
    for index, value in enumerate(values, start=1):
        assertion_id = "cea_" + hashlib.sha256(
            f"{domain}:{case_id}:{field_name}:{index}".encode()
        ).hexdigest()[:16]
        assertions.append({
            "schemaId": "ufo-timeline-context-evidence-assertion-v1.0.0",
            "assertionId": assertion_id,
            "caseId": case_id,
            "domain": domain,
            "fieldName": field_name,
            "value": value,
            "sourceIds": [source_id],
            "sourceLocators": [{"sourceId": source_id, "locator": f"field {field_name} {index}"}],
            "confidence": "high",
            "polarity": "supports",
            "evidenceSha256": [evidence_hash],
            "waveId": "wave-004-public-builder-claims",
            "assertedAt": "2026-08-11T12:00:00Z",
        })
        for reviewer in ("wave4-agent-a", "wave4-agent-b"):
            decision_token = f"{assertion_id}:{reviewer}"
            decisions.append({
                "schemaId": "ufo-timeline-context-evidence-review-decision-v1.0.0",
                "decisionId": "crd_" + hashlib.sha256(decision_token.encode()).hexdigest()[:16],
                "assertionId": assertion_id,
                "caseId": case_id,
                "domain": domain,
                "outcome": "accepted",
                "reviewer": {
                    "reviewerId": reviewer,
                    "reviewerType": "agent",
                    "runId": f"run-{reviewer}",
                },
                "frozenEvidenceSha256": [evidence_hash],
                "reasonCodes": ["source_matches_assertion"],
                "supersedesDecisionIds": [],
                "duplicateOfCaseId": None,
                "decidedAt": "2026-08-11T12:01:00Z",
            })
    for name, rows in (
        ("case_enrichment.jsonl", assertions),
        ("case_review_decisions.jsonl", decisions),
    ):
        (root / name).write_text(
            "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows),
            encoding="utf-8",
        )
    return root


def crop_export() -> dict:
    return {
        "schema_version": "crop-circle-timeline-export-v1.0.0",
        "source": {"source_commit": "fixture"},
        "events": [{
            "event_id": 1,
            "event_hash": "cc_aaaaaaaaaaaaaaaa",
            "external_id": "cc_aaaaaaaaaaaaaaaa",
            "date_raw": "1996-09-23",
            "date_iso": "1996-09-23",
            "end_date_iso": None,
            "date_precision": "exact_day",
            "location_raw": "Example locality",
            "lat": 37.1,
            "lon": -106.0,
            "has_coordinates": True,
            "marker_confidence": "locality_only",
            "exact_coordinate_eligible": False,
            "coordinate_uncertainty_km": 20.0,
            "mapping_notes": "Locality centroid only.",
            "description": "Catalog report.",
            "links": [],
            "crop_circle": {
                "formation_id": "cc_aaaaaaaaaaaaaaaa", "place": "Example", "region": "Test",
                "country": "US", "crop": "wheat", "crop_normalized": "wheat",
                "classification": "unreviewed", "origin_status": "unknown",
                "source_family_names": ["Legacy catalog"], "assertion_count": 1,
                "multi_archive_coverage": False, "possible_multiple_formations_same_entity": False,
                "modal_morphology_family": None,
            },
        }],
        "morphology_occurrences": [], "source_assertions": [], "image_links": [],
    }


def animal_collection(*, include_record: bool = True) -> dict:
    features: list[dict[str, object]] = []
    if include_record:
        features.append({
            "type": "Feature",
            "id": "animal_mutilation:ami_aaaaaaaaaaaaaaaa",
            "geometry": {"type": "Point", "coordinates": [-104.5, 39.7]},
            "properties": {
                "causality": "not_asserted", "claim_label": "Reported animal mutilation",
                "content_warning": "Animal-death descriptions may be disturbing.",
                "date_end": "1975-01-31", "date_precision": "month", "date_start": "1975-01-01",
                "evidence_excerpts": ["A bounded public excerpt."],
                "evidence_status": "reported_unreviewed", "location_label": "Example County, US",
                "location_precision": "unknown", "normalized_common_names": ["cattle"],
                "privacy_level": "public_generalized", "reported_taxon_keys": ["cattle"],
                "source_incident_id": "cmi_fixture", "source_incident_sha256": "5" * 64,
                "source_refs": [{"source_id": "legacy", "source_hash": "6" * 64, "locator": "line 1"}],
                "source_status": "lead", "species_groups": ["bovine"],
                "status": "reported_unreviewed", "summary": "Reported incident.",
                "title": "Reported animal mutilation", "trace_eligible": False,
                "trace_role": "context_only",
                "uncertainty": {
                    "coordinates_available": True, "date_precision": "month",
                    "location_precision": "unknown", "privacy_generalized": True,
                },
            },
        })
    return {
        "type": "FeatureCollection", "name": "Animal Mutilation Reports",
        "schema_version": "animal-mutilation-timeline-overlay-v1.1.0",
        "causality": "not_asserted", "trace_eligible": False, "trace_role": "context_only",
        "features": features,
    }


def required_fields(detail: dict[str, object]) -> None:
    for field in (
        "coordinateEvidenceClass", "coordinateMethod", "coordinateUncertaintyM", "dateRole",
        "reviewState", "sourceFamilyIds", "independenceStatus", "dedupStatus", "analysisTier",
        "exclusionReasonCodes",
    ):
        assert field in detail


def test_legacy_public_records_gain_generated_fields_without_strict_promotion(tmp_path: Path) -> None:
    ledgers = empty_ledgers(tmp_path / "empty-ledgers")
    crop_source = tmp_path / "crop.json"
    animal_source = tmp_path / "animal.json"
    write_json(crop_source, crop_export())
    write_json(animal_source, animal_collection())
    crop_out = tmp_path / "crop-out"
    animal_out = tmp_path / "animal-out"
    crop_manifest = CROP.build(
        crop_source, crop_out, "crop-fixture-v1", 50, context_evidence_root=ledgers,
    )
    animal_manifest = ANIMAL.build(
        input_path=animal_source, handoff_zip=None, output_root=animal_out,
        release_id="animal-mutilations-v1-20260810", asset_base_url="", chunk_size=250,
        context_evidence_root=ledgers,
    )
    crop_detail = next(iter(read_gzip_json(crop_out / "details" / "chunk_000.json.gz").values()))
    animal_detail = next(iter(read_gzip_json(animal_out / "details" / "chunk_000.json.gz").values()))
    required_fields(crop_detail)
    required_fields(animal_detail)
    assert crop_detail["coordinateEvidenceClass"] == "locality_centroid"
    assert animal_detail["coordinateEvidenceClass"] == "generalized_public_marker"
    assert crop_manifest["readiness"]["strictReady"] == 0
    assert animal_manifest["readiness"]["strictReady"] == 0
    assert crop_detail["causality"] == animal_detail["causality"] == "not_asserted"
    assert crop_detail["traceEligible"] is animal_detail["traceEligible"] is False

    crop_out_repeat = tmp_path / "crop-out-repeat"
    CROP.build(crop_source, crop_out_repeat, "crop-fixture-v1", 50, context_evidence_root=ledgers)
    relative_files = sorted(path.relative_to(crop_out) for path in crop_out.rglob("*") if path.is_file())
    assert all(
        (crop_out / path).read_bytes() == (crop_out_repeat / path).read_bytes()
        for path in relative_files
    )


@pytest.mark.parametrize(
    ("loader", "domain", "case_id"),
    [
        (CROP, "crop_circle", "cc_aaaaaaaaaaaaaaaa"),
        (ANIMAL, "animal_mutilation", "ami_aaaaaaaaaaaaaaaa"),
    ],
    ids=("crop", "animal"),
)
def test_public_loaders_keep_wave4_associated_claims_additive_and_scalars_fail_closed(
    tmp_path: Path,
    loader,
    domain: str,
    case_id: str,
) -> None:
    claims = [
        {"claimType": "campaign_identity", "value": "Bacardi Seven Tiki"},
        {
            "claimType": "source_lineage_or_scope_decision",
            "status": "count_as_one_family_pending_separate_evidence",
        },
    ]
    claim_root = write_two_reviewed_values(
        tmp_path / f"{domain}-claims",
        domain=domain,
        case_id=case_id,
        field_name="associated_claim",
        values=claims,
    )
    evidence, _metadata, _accepted_new = loader.load_context_evidence(claim_root, domain)
    expected = sorted(claims, key=loader.canonical_json_bytes)
    assert evidence[case_id]["fields"]["associated_claim"]["value"] == expected

    scalar_root = write_two_reviewed_values(
        tmp_path / f"{domain}-scalar",
        domain=domain,
        case_id=case_id,
        field_name="latitude",
        values=[40.0, 41.0],
    )
    with pytest.raises(ValueError, match="Conflicting accepted"):
        loader.load_context_evidence(scalar_root, domain)


def test_accepted_new_crop_and_animal_cases_bootstrap_into_strict_tiers(tmp_path: Path) -> None:
    crop_id = "cc_bbbbbbbbbbbbbbbb"
    animal_id = "ami_bbbbbbbbbbbbbbbb"
    crop_ledgers = write_reviewed_ledgers(
        tmp_path / "crop-ledgers", domain="crop_circle", case_id=crop_id, accepted_new=True,
        fields={
            "source_case_identifier": "official-crop-1", "public_title": "Reviewed crop formation",
            "public_summary": "A formation was documented at the cited site.",
            "primary_classification": "documented formation", "crop_type": "wheat",
            "formation_date": "2001-07-14", "location_label": "Example Parish, UK",
            "latitude": 51.1234, "longitude": -1.2345, "coordinate_uncertainty_m": 80,
            "coordinate_method": "source_reported_event_site", "dedup_cluster_id": "crop-cluster-1",
        },
    )
    animal_ledgers = write_reviewed_ledgers(
        tmp_path / "animal-ledgers", domain="animal_mutilation", case_id=animal_id, accepted_new=True,
        fields={
            "source_case_identifier": "official-animal-1", "public_title": "Reviewed animal incident",
            "public_summary": "An official report documented the incident.",
            "primary_classification": "explained scavenger damage", "animal_species": "cattle",
            "occurrence_date": "1979-08-15", "location_label": "Questa area, New Mexico",
            "latitude": 36.701, "longitude": -105.595, "coordinate_uncertainty_m": 900,
            "coordinate_method": "source_reported_event_site", "dedup_cluster_id": "animal-cluster-1",
            "witnesses": ["Private name retained only in the evidence ledger"],
        },
    )
    crop_source = tmp_path / "empty-crop.json"
    animal_source = tmp_path / "empty-animal.json"
    empty_crop = crop_export()
    empty_crop["events"] = []
    write_json(crop_source, empty_crop)
    write_json(animal_source, animal_collection(include_record=False))
    crop_out = tmp_path / "new-crop-out"
    animal_out = tmp_path / "new-animal-out"
    crop_manifest = CROP.build(
        crop_source, crop_out, "crop-fixture-v2", 50, context_evidence_root=crop_ledgers,
    )
    animal_manifest = ANIMAL.build(
        input_path=animal_source, handoff_zip=None, output_root=animal_out,
        release_id="animal-mutilations-v1-20260810", asset_base_url="", chunk_size=250,
        context_evidence_root=animal_ledgers,
    )
    crop_detail = read_gzip_json(crop_out / "details" / "chunk_000.json.gz")[crop_id]
    animal_detail = read_gzip_json(animal_out / "details" / "chunk_000.json.gz")[f"animal_mutilation:{animal_id}"]
    assert crop_detail["coordinateEvidenceClass"] == "source_exact"
    assert crop_detail["analysisTier"] == "crop_strict"
    assert animal_detail["coordinateEvidenceClass"] == "source_bounded"
    assert animal_detail["analysisTier"] == "animal_strict"
    assert animal_detail["status"] == animal_detail["reviewState"] == "human_reviewed"
    assert animal_detail["privacyLevel"] == "public_source_supported_site"
    assert crop_manifest["readiness"]["strictReady"] == 1
    assert animal_manifest["readiness"]["strictReady"] == 1
    assert animal_manifest["policy"]["sourceSupportedPrivatePropertyCoordinatesPublished"] is True
    assert crop_manifest["counts"]["acceptedNewCases"] == 1
    assert animal_manifest["counts"]["acceptedNewCases"] == 1
    assert "Private name" not in json.dumps(animal_detail)
    animal_points = read_gzip_json(animal_out / "points.json.gz")
    assert animal_points[0][-1] == 900.0


def test_centroid_method_never_becomes_exact_and_legal_restriction_suppresses(tmp_path: Path) -> None:
    crop_id = "cc_aaaaaaaaaaaaaaaa"
    crop_ledgers = write_reviewed_ledgers(
        tmp_path / "centroid-ledgers", domain="crop_circle", case_id=crop_id, accepted_new=False,
        fields={
            "formation_date": "1996-09-23", "latitude": 37.1, "longitude": -106.0,
            "coordinate_uncertainty_m": 20, "coordinate_method": "locality_centroid",
            "dedup_cluster_id": "crop-cluster-existing",
        },
    )
    crop_source = tmp_path / "crop.json"
    write_json(crop_source, crop_export())
    crop_out = tmp_path / "centroid-out"
    CROP.build(crop_source, crop_out, "crop-fixture-v3", 50, context_evidence_root=crop_ledgers)
    crop_detail = read_gzip_json(crop_out / "details" / "chunk_000.json.gz")[crop_id]
    assert crop_detail["coordinateEvidenceClass"] == "locality_centroid"
    assert crop_detail["analysisTier"] != "crop_strict"

    animal_id = "ami_aaaaaaaaaaaaaaaa"
    animal_ledgers = write_reviewed_ledgers(
        tmp_path / "restricted-ledgers", domain="animal_mutilation", case_id=animal_id,
        accepted_new=False, fields={"legal_publication_restriction": True},
    )
    animal_source = tmp_path / "animal.json"
    write_json(animal_source, animal_collection())
    animal_out = tmp_path / "restricted-out"
    manifest = ANIMAL.build(
        input_path=animal_source, handoff_zip=None, output_root=animal_out,
        release_id="animal-mutilations-v1-20260810", asset_base_url="", chunk_size=250,
        context_evidence_root=animal_ledgers,
    )
    assert manifest["counts"]["records"] == 0
    assert manifest["counts"]["legallyRestrictedSuppressed"] == 1
    assert read_gzip_json(animal_out / "catalog.json.gz") == []


def test_reviewed_duplicates_remain_mappable_but_are_excluded_from_analysis(tmp_path: Path) -> None:
    crop_id = "cc_aaaaaaaaaaaaaaaa"
    crop_ledgers = write_reviewed_ledgers(
        tmp_path / "duplicate-crop-ledgers",
        domain="crop_circle",
        case_id=crop_id,
        accepted_new=False,
        fields={
            "formation_date": "1996-09-23",
            "latitude": 37.1,
            "longitude": -106.0,
            "coordinate_uncertainty_m": 50,
            "coordinate_method": "source_reported_event_site",
            "duplicate_of_case_id": "cc_bbbbbbbbbbbbbbbb",
        },
    )
    crop_source = tmp_path / "duplicate-crop.json"
    write_json(crop_source, crop_export())
    crop_out = tmp_path / "duplicate-crop-out"
    crop_manifest = CROP.build(
        crop_source,
        crop_out,
        "crop-fixture-duplicate-v1",
        50,
        context_evidence_root=crop_ledgers,
    )
    crop_detail = read_gzip_json(crop_out / "details" / "chunk_000.json.gz")[crop_id]
    assert crop_detail["dedupStatus"] == "duplicate"
    assert crop_detail["analysisTier"] == "excluded"
    assert crop_detail["cropChronologyEligible"] is False
    assert "duplicate_record_excluded_from_analysis" in crop_detail["exclusionReasonCodes"]
    assert read_gzip_json(crop_out / "points.json.gz")[0][0] == crop_id
    assert crop_manifest["counts"]["mapped"] == 1
    assert crop_manifest["readiness"]["sensitivityReady"] == 0
    assert crop_manifest["readiness"]["strictReady"] == 0

    animal_id = "ami_aaaaaaaaaaaaaaaa"
    animal_ledgers = write_reviewed_ledgers(
        tmp_path / "duplicate-animal-ledgers",
        domain="animal_mutilation",
        case_id=animal_id,
        accepted_new=False,
        fields={
            "occurrence_date": "1975-01-15",
            "latitude": 39.7,
            "longitude": -104.5,
            "coordinate_uncertainty_m": 500,
            "coordinate_method": "source_reported_event_site",
            "duplicate_of_case_id": "ami_bbbbbbbbbbbbbbbb",
        },
    )
    animal_source = tmp_path / "duplicate-animal.json"
    write_json(animal_source, animal_collection())
    animal_out = tmp_path / "duplicate-animal-out"
    animal_manifest = ANIMAL.build(
        input_path=animal_source,
        handoff_zip=None,
        output_root=animal_out,
        release_id="animal-mutilations-v1-20990101",
        asset_base_url="",
        chunk_size=250,
        context_evidence_root=animal_ledgers,
    )
    animal_key = f"animal_mutilation:{animal_id}"
    animal_detail = read_gzip_json(animal_out / "details" / "chunk_000.json.gz")[animal_key]
    assert animal_detail["dedupStatus"] == "duplicate"
    assert animal_detail["analysisTier"] == "excluded"
    assert "duplicate_record_excluded_from_analysis" in animal_detail["exclusionReasonCodes"]
    assert read_gzip_json(animal_out / "points.json.gz")[0][0] == animal_key
    assert animal_manifest["counts"]["mapped"] == 1
    assert animal_manifest["readiness"]["sensitivityReady"] == 0
    assert animal_manifest["readiness"]["strictReady"] == 0


def test_terminal_new_case_without_reviewed_bootstrap_fails_closed(tmp_path: Path) -> None:
    case_id = "ami_cccccccccccccccc"
    ledgers = write_reviewed_ledgers(
        tmp_path / "incomplete-ledgers", domain="animal_mutilation", case_id=case_id,
        accepted_new=True, fields={"public_title": "Incomplete new case"},
    )
    animal_source = tmp_path / "empty-animal.json"
    write_json(animal_source, animal_collection(include_record=False))
    with pytest.raises(ValueError, match="lacks reviewed bootstrap fields"):
        ANIMAL.build(
            input_path=animal_source, handoff_zip=None, output_root=tmp_path / "incomplete-out",
            release_id="animal-mutilations-v1-20260810", asset_base_url="", chunk_size=250,
            context_evidence_root=ledgers,
        )

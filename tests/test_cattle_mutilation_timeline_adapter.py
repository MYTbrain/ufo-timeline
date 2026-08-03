from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from scripts import build_animal_mutilation_timeline_layer as adapter
from scripts import package_animal_mutilation_timeline_handoff as packager


def _write_jsonl(path: Path, rows: list[dict]) -> bytes:
    data = b"".join(adapter.canonical_json_line(row) for row in rows)
    path.write_bytes(data)
    return data


def _incident(
    suffix: str,
    *,
    common_name: str = "cattle",
    taxon_key: str | None = None,
    species_group: str = "bovine",
    status: str = "lead",
    role: str = "reported_victim",
    privacy_level: str = "public_generalized",
    location_precision: str = "locality",
    location_label: str | None = "Test County, CO, US",
    longitude_public: float | None = -105.2,
    latitude_public: float | None = 40.1,
    longitude_internal: float | None = -105.234567,
    latitude_internal: float | None = 40.123456,
    evidence: str | None = "A source reports the animal was found mutilated.",
    source_url: str | None = "https://records.example.test/case/1",
) -> dict:
    source_id = f"src:{suffix}"
    source_hash = hashlib.sha256(source_id.encode()).hexdigest()
    cmi = f"cmi_{suffix}"
    animal = {
        "species": None if common_name == "unknown_animal" else common_name,
        "reported_text": "animal" if common_name == "unknown_animal" else common_name,
        "reported_taxon_key": taxon_key or common_name,
        "normalized_common_name": common_name,
        "species_group": species_group,
        "domestic_context": "unknown",
        "incident_role": role,
        "identification_basis": "sentence_local_explicit_mutilation",
        "identification_confidence": 0.1,
        "source_ids": [source_id],
        "evidence_excerpt": evidence,
        "breed": None,
        "sex": None,
        "age_class": None,
        "count": None,
        "condition_before_death": None,
        "ownership_public": None,
    }
    return {
        "event_domain": "animal_mutilation",
        "record_id": cmi,
        "canonical_incident_id": cmi,
        "record_type": "mutilation_case",
        "status": status,
        "title": "A source title that the public overlay must not copy",
        "summary": "A source summary that the public overlay must not copy",
        "explicit_negative": False,
        "negative_only": False,
        "dates": {
            "event_start": "1975-04-02",
            "event_end": "1975-04-30",
            "discovery_start": None,
            "discovery_end": None,
            "report_date": None,
            "estimated_death_start": None,
            "estimated_death_end": None,
            "precision": "month",
            "raw_text": "April 1975",
        },
        "location": {
            "raw_text": location_label,
            "country_code": "US",
            "admin1": "CO",
            "admin2": "Test County",
            "locality": "Test",
            "latitude_internal": latitude_internal,
            "longitude_internal": longitude_internal,
            "latitude_public": latitude_public,
            "longitude_public": longitude_public,
            "precision": location_precision,
            "coordinate_source": "fixture",
            "geocode_query": None,
            "geocode_confidence": None,
            "privacy_level": privacy_level,
            "mapping_notes": None,
        },
        "animals": [animal],
        "animal_context": [],
        "sources": [
            {
                "source_id": source_id,
                "tier": "D",
                "source_type": "dataset",
                "title": "Fixture source",
                "agency_or_publisher": None,
                "publication_date": None,
                "url": source_url,
                "page_or_container": "fixture.jsonl line 1",
                "archival_citation": None,
                "rights_status": "copyrighted_metadata_only",
                "raw_text_retention": "internal_only",
                "source_hash": source_hash,
            }
        ],
        "provenance": {
            "ingestion_adapter": "fixture",
            "source_native_id": None,
            "raw_record_hash": "a" * 64,
            "duplicate_cluster_id": cmi,
            "canonicalization_version": "test",
            "ingested_at": None,
            "review_state": "unreviewed",
            "review_notes": None,
        },
        "extraction": {
            "candidate_score": 0.0,
            "candidate_reasons": [],
            "incident_likelihood": 0.0,
            "needs_human_review": True,
        },
        "public_content_warning": "Animal-death descriptions may be disturbing.",
        "external_event_refs": [
            {
                "domain": "ufo",
                "dataset": "fixture-ufo",
                "external_id": "evt_fixture",
                "native_event_id": "evt_fixture",
                "relationship_id": "rel_" + "b" * 24,
            }
        ],
    }


def _write_seed(
    root: Path,
    incidents: list[dict],
    *,
    run_mode: str = adapter.EXPECTED_RUN_MODE,
    count_override: int | None = None,
    coverage_ids: list[str] | None = None,
) -> Path:
    seed = root / "seed"
    seed.mkdir()
    canonical_bytes = _write_jsonl(seed / adapter.CANONICAL_NAME, incidents)
    covered = coverage_ids
    if covered is None:
        covered = [row["canonical_incident_id"] for row in incidents]
    incidents_by_id = {row["canonical_incident_id"]: row for row in incidents}
    case_decisions = []
    for source_id in covered:
        incident = incidents_by_id[source_id]
        expected = adapter._expected_case_projection(incident)
        case_decisions.append(
            {
                "record_id": source_id,
                "basis": "ufo_source_record",
                "expected": expected,
                "expected_projection_sha256": hashlib.sha256(
                    adapter.canonical_json_bytes(expected)
                ).hexdigest(),
            }
        )
    validation_provenance = {
        "schema_version": "animal-mutilation-validation-provenance-v1.2.0",
        "case_decisions": case_decisions,
    }
    validation_provenance["registry_sha256"] = hashlib.sha256(
        adapter.canonical_json_bytes(validation_provenance)
    ).hexdigest()
    manifest = {
        "schema_version": "animal-mutilation-seed-run-manifest-v1.2.0",
        "pipeline_version": "animal-mutilation-cross-domain-seed-v1.1.12",
        "base_commit": "d0c8341c9b4785db40f7da74369c750770b0d21f",
        "run_mode": run_mode,
        "counts": {
            "canonical_incidents": len(incidents) if count_override is None else count_override,
            "explicit_source_relationships": 2,
            "computed_relationships": 3,
            "cross_domain_relationships": 5,
        },
        "outputs": {
            adapter.CANONICAL_NAME: {
                "sha256": hashlib.sha256(canonical_bytes).hexdigest(),
                "size_bytes": len(canonical_bytes),
            }
        },
        "validation_provenance": validation_provenance,
    }
    (seed / adapter.SEED_MANIFEST_NAME).write_bytes(adapter.canonical_json_line(manifest))
    return seed


def _rewrite_seed_manifest(
    seed: Path,
    mutate,
    *,
    recompute_registry: bool,
) -> None:
    manifest_path = seed / adapter.SEED_MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    mutate(manifest["validation_provenance"])
    if recompute_registry:
        provenance = manifest["validation_provenance"]
        provenance.pop("registry_sha256", None)
        provenance["registry_sha256"] = hashlib.sha256(
            adapter.canonical_json_bytes(provenance)
        ).hexdigest()
    manifest_path.write_bytes(adapter.canonical_json_line(manifest))


def _decision(
    incident: dict,
    suffix: str,
    *,
    disposition: str = "accepted",
    ami_suffix: str | None = None,
    source_hash: str | None = None,
    approved_public_fields: dict | None = None,
) -> dict:
    decision = {
        "schema_version": adapter.DECISION_SCHEMA_VERSION,
        "review_decision_id": f"amrd_{suffix}",
        "source_incident_id": incident["canonical_incident_id"],
        "source_incident_sha256": source_hash
        or hashlib.sha256(adapter.canonical_json_bytes(incident)).hexdigest(),
        "disposition": disposition,
        "reviewer_id": "internal-reviewer-17",
        "reviewed_at": "2026-08-02T10:30:00Z",
        "notes": "Internal review note; never public.",
    }
    if disposition == "accepted":
        decision["animal_mutilation_event_id"] = f"ami_{ami_suffix or suffix}"
    if approved_public_fields is not None:
        decision["approved_public_fields"] = approved_public_fields
    return decision


def _build(
    tmp_path: Path,
    incidents: list[dict],
    decisions: list[dict] | None,
    *,
    output_name: str = "out",
    **seed_options,
) -> tuple[Path, Path, dict]:
    seed = _write_seed(tmp_path, incidents, **seed_options)
    ledger = None
    if decisions is not None:
        ledger = tmp_path / "review_decisions.jsonl"
        _write_jsonl(ledger, decisions)
    output = tmp_path / output_name
    manifest = adapter.build_timeline_layer(
        seed_output_dir=seed,
        review_decisions=ledger,
        output_dir=output,
    )
    return seed, output, manifest


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_missing_decision_is_queued_and_output_is_confined(tmp_path: Path) -> None:
    incident = _incident("0" * 24)
    seed = _write_seed(tmp_path, [incident])
    input_hashes = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in seed.iterdir()
    }
    output = tmp_path / "timeline"

    manifest = adapter.build_timeline_layer(
        seed_output_dir=seed,
        review_decisions=None,
        output_dir=output,
    )

    assert {path.name for path in output.iterdir()} == set(adapter.OUTPUT_NAMES)
    assert input_hashes == {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in seed.iterdir()
    }
    overlay = _load_json(output / adapter.OVERLAY_NAME)
    assert overlay["name"] == "Animal Mutilation Reports"
    assert overlay["release_mode"] == "reported_unreviewed"
    assert len(overlay["features"]) == 1
    feature = overlay["features"][0]
    properties = feature["properties"]
    assert properties["status"] == "reported_unreviewed"
    assert properties["evidence_status"] == "reported_unreviewed"
    assert properties["source_status"] == "lead"
    assert "review_decision_id" not in properties
    assert "reviewed_on" not in properties
    assert properties["animal_mutilation_event_id"] == adapter._stable_reported_event_id(
        incident["canonical_incident_id"]
    )
    queue = _load_jsonl(output / adapter.QUEUE_NAME)
    assert [row["queue_state"] for row in queue] == ["reported_unreviewed"]
    assert manifest["counts"] == {
        "total_source_incidents": 1,
        "decision_ledger_rows": 0,
        "accepted": 0,
        "reported_unreviewed": 1,
        "rejected": 0,
        "unresolved": 0,
        "missing_decision": 1,
        "mapped_incidents": 1,
        "unmapped_incidents": 0,
        "queued_for_review": 1,
        "features_with_geometry": 1,
        "features_without_geometry": 0,
        "generated_artifacts": 3,
    }
    assert manifest["layer_name"] == "Animal Mutilation Reports"
    assert manifest["source_commit"] == "d0c8341c9b4785db40f7da74369c750770b0d21f"
    assert manifest["seed_pipeline_version"] == "animal-mutilation-cross-domain-seed-v1.1.12"
    assert manifest["inputs"]["review_decision_ledger"]["sha256"] == hashlib.sha256(b"").hexdigest()


def test_accepted_projection_preserves_stable_lineage_and_trace_safety(tmp_path: Path) -> None:
    incident = _incident("1" * 24, common_name="dog", species_group="canid")
    decision = _decision(incident, "a" * 24)
    _, output, manifest = _build(tmp_path, [incident], [decision])

    overlay = _load_json(output / adapter.OVERLAY_NAME)
    feature = overlay["features"][0]
    properties = feature["properties"]
    assert overlay["name"] == "Animal Mutilation Reports"
    assert overlay["release_mode"] == "review_ledger"
    assert feature["id"] == "animal_mutilation:ami_" + "a" * 24
    assert properties["animal_mutilation_event_id"] == "ami_" + "a" * 24
    assert properties["source_incident_id"] == incident["canonical_incident_id"]
    assert properties["source_incident_sha256"] == decision["source_incident_sha256"]
    assert properties["title"] == properties["claim_label"] == "Reported animal mutilation"
    assert properties["evidence_status"] == "reviewed"
    assert properties["source_status"] == "lead"
    assert properties["normalized_common_names"] == ["dog"]
    assert properties["trace_eligible"] is overlay["trace_eligible"] is False
    assert properties["trace_role"] == overlay["trace_role"] == "context_only"
    assert properties["causality"] == overlay["causality"] == "not_asserted"
    assert feature["geometry"] == {"type": "Point", "coordinates": [-105.2, 40.1]}
    public_bytes = (output / adapter.OVERLAY_NAME).read_text(encoding="utf-8")
    assert "internal-reviewer-17" not in public_bytes
    assert "-105.234567" not in public_bytes
    assert "40.123456" not in public_bytes
    assert "external_event_refs" not in public_bytes
    assert "relationship_id" not in public_bytes
    assert "trace_segments" not in public_bytes
    assert manifest["pending_relationships"]["total_pending"] == 5
    assert manifest["pending_relationships"]["emitted"] == 0


def test_unreviewed_projection_omits_private_url_and_corrupt_evidence(
    tmp_path: Path,
) -> None:
    incident = _incident(
        "1f" * 12,
        source_url="https://records.example.test/catalog/Kings%20Ranch/case",
        evidence="The source contains ΓÇÖ mojibake and a replacement character �.",
    )
    _, output, _ = _build(tmp_path, [incident], None)

    feature = _load_json(output / adapter.OVERLAY_NAME)["features"][0]
    properties = feature["properties"]
    assert properties["evidence_excerpts"] == []
    assert "url" not in properties["source_refs"][0]
    assert properties["source_refs"][0]["source_id"] == "src:" + "1f" * 12
    serialized = json.dumps(feature, ensure_ascii=False)
    assert "Kings%20Ranch" not in serialized
    assert "ΓÇ" not in serialized
    assert "�" not in serialized

    assert (
        packager._decoded_url_privacy_reason(
            "https://records.example.test/catalog/Kings%2520Ranch/case"
        )
        == "private_locator"
    )
    assert packager._corrupt_text_path({"evidence": "bad � text"}) == "evidence"


def test_all_species_and_explained_statuses_are_eligible_after_acceptance(tmp_path: Path) -> None:
    incidents = [
        _incident("2" * 24, common_name="cattle", species_group="bovine", status="lead"),
        _incident("3" * 24, common_name="wild_bird", taxon_key="penguin", species_group="avian", status="explained_natural"),
        _incident("4" * 24, common_name="fish", taxon_key="eel", species_group="fish", status="explained_human"),
        _incident("5" * 24, common_name="unknown_animal", species_group="unknown", status="contested"),
    ]
    decisions = [_decision(row, f"{index:x}" * 24) for index, row in enumerate(incidents, 6)]
    _, output, manifest = _build(tmp_path, incidents, decisions)

    features = _load_json(output / adapter.OVERLAY_NAME)["features"]
    assert manifest["counts"]["accepted"] == 4
    assert {feature["properties"]["status"] for feature in features} == {
        "lead",
        "explained_natural",
        "explained_human",
        "contested",
    }
    assert {name for feature in features for name in feature["properties"]["normalized_common_names"]} == {
        "cattle",
        "wild_bird",
        "fish",
        "unknown_animal",
    }


def test_rejected_unresolved_and_missing_have_distinct_dispositions(tmp_path: Path) -> None:
    rejected = _incident("a" * 24)
    unresolved = _incident("b" * 24)
    missing = _incident("c" * 24)
    decisions = [
        _decision(rejected, "1" * 24, disposition="rejected"),
        _decision(unresolved, "2" * 24, disposition="unresolved"),
    ]
    _, output, manifest = _build(tmp_path, [rejected, unresolved, missing], decisions)

    assert _load_json(output / adapter.OVERLAY_NAME)["features"] == []
    queue = _load_jsonl(output / adapter.QUEUE_NAME)
    assert [row["source_incident_id"] for row in queue] == sorted(
        [unresolved["canonical_incident_id"], missing["canonical_incident_id"]]
    )
    assert {row["queue_state"] for row in queue} == {
        "review_unresolved",
        "missing_review_decision",
    }
    assert manifest["counts"]["rejected"] == 1
    assert manifest["counts"]["unresolved"] == 1
    assert manifest["counts"]["missing_decision"] == 1


@pytest.mark.parametrize("failure_kind", ["stale", "unknown", "duplicate_source", "duplicate_id", "ami_reuse"])
def test_invalid_decision_ledger_fails_closed(tmp_path: Path, failure_kind: str) -> None:
    first = _incident("d" * 24)
    second = _incident("e" * 24)
    decisions = [_decision(first, "3" * 24), _decision(second, "4" * 24)]
    if failure_kind == "stale":
        decisions[0]["source_incident_sha256"] = "0" * 64
    elif failure_kind == "unknown":
        decisions[0]["source_incident_id"] = "cmi_" + "f" * 24
    elif failure_kind == "duplicate_source":
        decisions[1]["source_incident_id"] = decisions[0]["source_incident_id"]
        decisions[1]["source_incident_sha256"] = decisions[0]["source_incident_sha256"]
    elif failure_kind == "duplicate_id":
        decisions[1]["review_decision_id"] = decisions[0]["review_decision_id"]
    else:
        decisions[1]["animal_mutilation_event_id"] = decisions[0]["animal_mutilation_event_id"]
    seed = _write_seed(tmp_path, [first, second])
    ledger = tmp_path / "decisions.jsonl"
    _write_jsonl(ledger, decisions)
    output = tmp_path / "out"

    with pytest.raises(adapter.TimelineAdapterError):
        adapter.build_timeline_layer(
            seed_output_dir=seed,
            review_decisions=ledger,
            output_dir=output,
        )
    assert not output.exists()


@pytest.mark.parametrize("mutation", ["not_case", "negative", "noise", "no_victim"])
def test_accepted_decision_requires_actual_nonnegative_victim_case(tmp_path: Path, mutation: str) -> None:
    incident = _incident("f" * 24)
    if mutation == "not_case":
        incident["record_type"] = "aggregate_report"
    elif mutation == "negative":
        incident["explicit_negative"] = True
        incident["negative_only"] = True
    elif mutation == "noise":
        incident["provenance"]["review_state"] = "rejected_as_noise"
    else:
        incident["animals"][0]["incident_role"] = "context_only"
    decision = _decision(incident, "5" * 24)
    seed = _write_seed(tmp_path, [incident])
    ledger = tmp_path / "decisions.jsonl"
    _write_jsonl(ledger, [decision])

    with pytest.raises(adapter.TimelineAdapterError):
        adapter.build_timeline_layer(
            seed_output_dir=seed,
            review_decisions=ledger,
            output_dir=tmp_path / "out",
        )


def test_private_location_never_projects_internal_location_or_geometry(tmp_path: Path) -> None:
    incident = _incident(
        "6" * 24,
        privacy_level="internal_only",
        location_precision="exact_site",
        location_label="Secret Ranch",
        longitude_public=None,
        latitude_public=None,
        longitude_internal=-101.123456,
        latitude_internal=39.654321,
    )
    decision = _decision(incident, "7" * 24)
    _, output, _ = _build(tmp_path, [incident], [decision])

    feature = _load_json(output / adapter.OVERLAY_NAME)["features"][0]
    assert feature["geometry"] is None
    assert feature["properties"]["location_label"] is None
    serialized = json.dumps(feature)
    assert "Secret Ranch" not in serialized
    assert "-101.123456" not in serialized
    assert "39.654321" not in serialized


def test_one_sided_coordinate_pair_fails_closed(tmp_path: Path) -> None:
    incident = _incident("7" * 24, longitude_public=None, latitude_public=40.1)
    decision = _decision(incident, "8" * 24)
    seed = _write_seed(tmp_path, [incident])
    ledger = tmp_path / "decisions.jsonl"
    _write_jsonl(ledger, [decision])
    with pytest.raises(adapter.TimelineAdapterError, match="one-sided"):
        adapter.build_timeline_layer(
            seed_output_dir=seed,
            review_decisions=ledger,
            output_dir=tmp_path / "out",
        )


def test_generalized_location_cannot_retain_exact_precision(tmp_path: Path) -> None:
    incident = _incident("8" * 24, location_precision="exact_site")
    decision = _decision(incident, "9" * 24)
    seed = _write_seed(tmp_path, [incident])
    ledger = tmp_path / "decisions.jsonl"
    _write_jsonl(ledger, [decision])
    with pytest.raises(adapter.TimelineAdapterError, match="generated Timeline overlay"):
        adapter.build_timeline_layer(
            seed_output_dir=seed,
            review_decisions=ledger,
            output_dir=tmp_path / "out",
        )


def test_private_property_and_embedded_url_need_clean_reviewer_overrides(tmp_path: Path) -> None:
    incident = _incident(
        "9" * 24,
        location_label="Smith Ranch, CO",
        evidence="See https://private.example.test for the calf at Smith Ranch.",
    )
    unsafe_decision = _decision(incident, "a" * 24)
    seed = _write_seed(tmp_path, [incident])
    ledger = tmp_path / "unsafe.jsonl"
    _write_jsonl(ledger, [unsafe_decision])
    with pytest.raises(adapter.TimelineAdapterError, match="disallowed"):
        adapter.build_timeline_layer(
            seed_output_dir=seed,
            review_decisions=ledger,
            output_dir=tmp_path / "unsafe_out",
        )

    safe_decision = _decision(
        incident,
        "b" * 24,
        approved_public_fields={
            "location_label": "Test County, CO, US",
            "evidence_excerpts": ["A calf was reported found mutilated."],
        },
    )
    safe_ledger = tmp_path / "safe.jsonl"
    _write_jsonl(safe_ledger, [safe_decision])
    output = tmp_path / "safe_out"
    adapter.build_timeline_layer(
        seed_output_dir=seed,
        review_decisions=safe_ledger,
        output_dir=output,
    )
    feature = _load_json(output / adapter.OVERLAY_NAME)["features"][0]
    assert feature["properties"]["source_refs"][0]["url"].startswith("https://")
    assert "Smith Ranch" not in json.dumps(feature)


@pytest.mark.parametrize(
    "leak",
    [
        "Call (303) 555-0199 for details.",
        "The carcass was at 12-14 Smith Road.",
        "The report names jesse and frank ranch.",
        "The exact location was 40.12345, -105.12345.",
    ],
)
def test_reviewer_override_display_leaks_fail_closed(tmp_path: Path, leak: str) -> None:
    incident = _incident("1a" * 12)
    decision = _decision(
        incident,
        "1" * 24,
        approved_public_fields={"summary": leak},
    )
    seed = _write_seed(tmp_path, [incident])
    ledger = tmp_path / "decisions.jsonl"
    _write_jsonl(ledger, [decision])
    with pytest.raises(adapter.TimelineAdapterError, match="disallowed"):
        adapter.build_timeline_layer(
            seed_output_dir=seed,
            review_decisions=ledger,
            output_dir=tmp_path / "out",
        )


def test_mapped_unmapped_counts_apply_only_to_accepted_features(tmp_path: Path) -> None:
    mapped = _incident("2a" * 12)
    unmapped = _incident("2b" * 12, longitude_public=None, latitude_public=None)
    rejected = _incident("2c" * 12)
    unresolved = _incident("2d" * 12)
    missing = _incident("2e" * 12)
    decisions = [
        _decision(mapped, "2" * 24),
        _decision(unmapped, "3" * 24),
        _decision(rejected, "4" * 24, disposition="rejected"),
        _decision(unresolved, "5" * 24, disposition="unresolved"),
    ]
    _, _, manifest = _build(
        tmp_path,
        [mapped, unmapped, rejected, unresolved, missing],
        decisions,
    )
    assert manifest["counts"]["accepted"] == 2
    assert manifest["counts"]["mapped_incidents"] == 1
    assert manifest["counts"]["unmapped_incidents"] == 1
    assert manifest["counts"]["rejected"] == 1
    assert manifest["counts"]["unresolved"] == 1
    assert manifest["counts"]["missing_decision"] == 1


def test_superseded_lineage_must_be_historical_and_globally_unique(tmp_path: Path) -> None:
    first = _incident("3a" * 12)
    second = _incident("3b" * 12)
    historical = "cmi_" + "9a" * 12
    decisions = [_decision(first, "6" * 24), _decision(second, "7" * 24)]
    decisions[0]["supersedes_source_incident_ids"] = [historical]
    decisions[1]["supersedes_source_incident_ids"] = [historical]
    seed = _write_seed(tmp_path, [first, second])
    ledger = tmp_path / "duplicate_history.jsonl"
    _write_jsonl(ledger, decisions)
    with pytest.raises(adapter.TimelineAdapterError, match="multiple decisions"):
        adapter.build_timeline_layer(
            seed_output_dir=seed,
            review_decisions=ledger,
            output_dir=tmp_path / "out1",
        )

    decisions[1].pop("supersedes_source_incident_ids")
    decisions[0]["supersedes_source_incident_ids"] = [second["canonical_incident_id"]]
    _write_jsonl(ledger, decisions)
    with pytest.raises(adapter.TimelineAdapterError, match="supersedes current incident"):
        adapter.build_timeline_layer(
            seed_output_dir=seed,
            review_decisions=ledger,
            output_dir=tmp_path / "out2",
        )


@pytest.mark.parametrize("source_failure", ["missing_source", "bad_hash", "credential_url"])
def test_supporting_source_resolution_fails_closed(tmp_path: Path, source_failure: str) -> None:
    incident = _incident("0a" * 12)
    if source_failure == "missing_source":
        incident["animals"][0]["source_ids"] = ["src:missing"]
    elif source_failure == "bad_hash":
        incident["sources"][0]["source_hash"] = None
    else:
        incident["sources"][0]["url"] = "https://user:secret@example.test/case"
    decision = _decision(incident, "c" * 24)
    seed = _write_seed(tmp_path, [incident])
    ledger = tmp_path / "decisions.jsonl"
    _write_jsonl(ledger, [decision])
    with pytest.raises(adapter.TimelineAdapterError):
        adapter.build_timeline_layer(
            seed_output_dir=seed,
            review_decisions=ledger,
            output_dir=tmp_path / "out",
        )


@pytest.mark.parametrize("seed_failure", ["wrong_mode", "bad_count", "missing_coverage", "hash_mismatch", "duplicate_cmi"])
def test_untrusted_seed_fails_closed(tmp_path: Path, seed_failure: str) -> None:
    incident = _incident("0b" * 12)
    incidents = [incident]
    options = {}
    if seed_failure == "wrong_mode":
        options["run_mode"] = "partial_fixture"
    elif seed_failure == "bad_count":
        options["count_override"] = 2
    elif seed_failure == "missing_coverage":
        options["coverage_ids"] = []
    elif seed_failure == "duplicate_cmi":
        incidents = [incident, copy.deepcopy(incident)]
    seed = _write_seed(tmp_path, incidents, **options)
    if seed_failure == "hash_mismatch":
        with (seed / adapter.CANONICAL_NAME).open("ab") as handle:
            handle.write(b" ")
    with pytest.raises(adapter.TimelineAdapterError):
        adapter.build_timeline_layer(
            seed_output_dir=seed,
            review_decisions=None,
            output_dir=tmp_path / "out",
        )


@pytest.mark.parametrize(
    ("tamper_kind", "expected_message"),
    [
        ("registry_hash", "registry SHA-256 mismatch"),
        ("expected_hash", "decision hash mismatch"),
        ("projection", "decision projection mismatch"),
        ("duplicate_decision", "duplicate case decision"),
        ("malformed_decision", "is malformed"),
    ],
)
def test_validation_provenance_integrity_tampering_fails_closed(
    tmp_path: Path,
    tamper_kind: str,
    expected_message: str,
) -> None:
    incident = _incident("4a" * 12)
    seed = _write_seed(tmp_path, [incident])

    if tamper_kind == "registry_hash":
        _rewrite_seed_manifest(
            seed,
            lambda provenance: provenance.__setitem__("registry_sha256", "0" * 64),
            recompute_registry=False,
        )
    elif tamper_kind == "expected_hash":
        _rewrite_seed_manifest(
            seed,
            lambda provenance: provenance["case_decisions"][0].__setitem__(
                "expected_projection_sha256", "0" * 64
            ),
            recompute_registry=True,
        )
    elif tamper_kind == "projection":
        def change_projection(provenance: dict) -> None:
            decision = provenance["case_decisions"][0]
            decision["expected"]["dates"]["event_start"] = "1976-01-01"
            decision["expected_projection_sha256"] = hashlib.sha256(
                adapter.canonical_json_bytes(decision["expected"])
            ).hexdigest()

        _rewrite_seed_manifest(seed, change_projection, recompute_registry=True)
    elif tamper_kind == "duplicate_decision":
        _rewrite_seed_manifest(
            seed,
            lambda provenance: provenance["case_decisions"].append(
                copy.deepcopy(provenance["case_decisions"][0])
            ),
            recompute_registry=True,
        )
    else:
        _rewrite_seed_manifest(
            seed,
            lambda provenance: provenance["case_decisions"].append("not-an-object"),
            recompute_registry=True,
        )

    with pytest.raises(adapter.TimelineAdapterError, match=expected_message):
        adapter.build_timeline_layer(
            seed_output_dir=seed,
            review_decisions=None,
            output_dir=tmp_path / "out",
        )
    assert not (tmp_path / "out").exists()


def test_output_cannot_equal_or_nest_inside_seed(tmp_path: Path) -> None:
    incident = _incident("0c" * 12)
    seed = _write_seed(tmp_path, [incident])
    with pytest.raises(adapter.TimelineAdapterError):
        adapter.build_timeline_layer(
            seed_output_dir=seed,
            review_decisions=None,
            output_dir=seed,
        )
    with pytest.raises(adapter.TimelineAdapterError):
        adapter.build_timeline_layer(
            seed_output_dir=seed,
            review_decisions=None,
            output_dir=seed / "nested",
        )


def test_two_runs_are_byte_identical_and_manifest_hashes_subordinate_outputs(tmp_path: Path) -> None:
    incident = _incident("0d" * 12, longitude_public=None, latitude_public=None)
    decision = _decision(incident, "d" * 24)
    seed = _write_seed(tmp_path, [incident])
    ledger = tmp_path / "decisions.jsonl"
    _write_jsonl(ledger, [decision])
    seed_before = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in seed.iterdir()
    }
    outputs = []
    for name in ("first", "second"):
        output = tmp_path / name
        adapter.build_timeline_layer(
            seed_output_dir=seed,
            review_decisions=ledger,
            output_dir=output,
        )
        outputs.append(output)

    for name in adapter.OUTPUT_NAMES:
        assert (outputs[0] / name).read_bytes() == (outputs[1] / name).read_bytes()
    manifest = _load_json(outputs[0] / adapter.IMPORT_MANIFEST_NAME)
    for subordinate in (adapter.QUEUE_NAME, adapter.OVERLAY_NAME):
        data = (outputs[0] / subordinate).read_bytes()
        assert manifest["outputs"][subordinate]["sha256"] == hashlib.sha256(data).hexdigest()
        assert manifest["outputs"][subordinate]["size_bytes"] == len(data)
    assert adapter.IMPORT_MANIFEST_NAME not in manifest["outputs"]
    assert manifest["manifest_self_hash_policy"] == "not_embedded_to_avoid_recursion"
    assert seed_before == {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in seed.iterdir()
    }


def test_decision_schema_is_closed_and_all_dispositions_are_attributed(tmp_path: Path) -> None:
    incident = _incident("0e" * 12)
    rejected = _decision(incident, "e" * 24, disposition="rejected")
    rejected.pop("reviewer_id")
    rejected["unexpected"] = True
    seed = _write_seed(tmp_path, [incident])
    ledger = tmp_path / "decisions.jsonl"
    _write_jsonl(ledger, [rejected])
    with pytest.raises(adapter.TimelineAdapterError, match="schema validation"):
        adapter.build_timeline_layer(
            seed_output_dir=seed,
            review_decisions=ledger,
            output_dir=tmp_path / "out",
        )


def test_cli_main_builds_only_bridge_artifacts(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    incident = _incident("0f" * 12)
    seed = _write_seed(tmp_path, [incident])
    output = tmp_path / "out"
    result = adapter.main(
        ["--seed-output-dir", str(seed), "--output-dir", str(output)]
    )
    assert result == 0
    output_text = capsys.readouterr().out
    assert "mapped=1" in output_text
    assert "reported_unreviewed=1" in output_text
    assert {path.name for path in output.iterdir()} == set(adapter.OUTPUT_NAMES)

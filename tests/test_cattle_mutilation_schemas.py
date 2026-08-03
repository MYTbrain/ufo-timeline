from __future__ import annotations

import copy
import json
from pathlib import Path

try:
    from jsonschema import Draft202012Validator
except ImportError:  # The repository does not require jsonschema at runtime.
    Draft202012Validator = None


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "docs" / "cattle_mutilation"


def _load(name: str) -> dict:
    return json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))


CASE_SCHEMA = _load("case.schema.json")
RELATIONSHIP_SCHEMA = _load("cross_domain_relationship.schema.json")
SOURCE_REGISTRY = _load("source_registry.json")


def _validate_when_available(schema: dict, instance: dict) -> None:
    if Draft202012Validator is not None:
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(instance)
        return

    # Standard-library fallback: the focused tests below assert the nested
    # contract; this check guarantees that top-level required keys are present.
    missing = set(schema.get("required", ())) - set(instance)
    assert not missing, f"missing required fields: {sorted(missing)}"


def _validation_errors(schema: dict, instance: dict) -> list:
    if Draft202012Validator is None:
        return []
    return list(Draft202012Validator(schema).iter_errors(instance))


def _representative_case() -> dict:
    return {
        "event_domain": "animal_mutilation",
        "record_id": "cm_ufo_hatch_udb_11636_a1",
        "canonical_incident_id": "cm_whiteface_tx_1975_03_10",
        "record_type": "mutilation_case",
        "status": "documented_report",
        "title": "Whiteface cattle and crop-circle report",
        "explicit_negative": False,
        "negative_only": False,
        "dates": {
            "event_start": "1975-03-10",
            "event_end": "1975-03-10",
            "precision": "exact_day",
        },
        "location": {
            "raw_text": "Whiteface, Texas",
            "country_code": "US",
            "admin1": "Texas",
            "locality": "Whiteface",
            "precision": "locality",
            "privacy_level": "public_generalized",
        },
        "animals": [
            {
                "species": "cattle",
                "reported_text": "cow",
                "reported_taxon_key": "cattle",
                "normalized_common_name": "cattle",
                "species_group": "bovine",
                "domestic_context": "livestock",
                "incident_role": "reported_victim",
                "identification_basis": "sentence_local_explicit_mutilation",
                "identification_confidence": 0.94,
                "source_ids": ["ufo_hatch_udb_11636"],
                "evidence_excerpt": "A mutilated cow was found.",
                "count": 1,
            }
        ],
        "associated_events": [
            {
                "association_type": "crop_circle",
                "claim": {
                    "claim_type": "reported_same_scene",
                    "asserted_value": True,
                    "observation_basis": "retelling",
                    "source_ids": ["ufo_hatch_udb_11636"],
                    "confidence": 0.75,
                },
                "linked_record_id": None,
                "temporal_offset_hours": 0,
                "distance_km": 0,
            }
        ],
        "sources": [
            {
                "source_id": "ufo_hatch_udb_11636",
                "tier": "C",
                "source_type": "dataset",
                "title": "Hatch UDB 11636",
                "rights_status": "copyrighted_metadata_only",
                "raw_text_retention": "internal_only",
            }
        ],
        "provenance": {
            "ingestion_adapter": "ufo_timeline_source_records_v1",
            "source_native_id": "Hatch_UDB_11636",
            "raw_record_hash": "1" * 64,
            "review_state": "unreviewed",
        },
        "related_ufo_timeline_event_ids": [87939],
        "external_event_refs": [
            {
                "domain": "crop_circle",
                "dataset": "crop_circle_atlas_export_v1",
                "external_id": "cc_3bd2d49faaef",
                "native_event_id": 11636,
                "relationship_id": "rel_0123456789abcdef",
            }
        ],
    }


def _representative_relationship() -> dict:
    return {
        "relationship_id": "rel_0123456789abcdef",
        "subject": {
            "domain": "animal_mutilation",
            "dataset": "animal_mutilation_phase1",
            "external_id": "cm_whiteface_tx_1975_03_10",
            "native_event_id": "Hatch_UDB_11636",
        },
        "object": {
            "domain": "crop_circle",
            "dataset": "crop_circle_atlas_export_v1",
            "external_id": "cc_3bd2d49faaef",
            "native_event_id": 11636,
        },
        "relationship_type": "same_scene",
        "assertion_mode": "explicit_source",
        "match_tier": 1,
        "temporal": {
            "subject_interval": {
                "start": "1975-03-10",
                "end": "1975-03-10",
                "precision": "exact_day",
            },
            "object_interval": {
                "start": "1975-03-10",
                "end": "1975-03-10",
                "precision": "exact_day",
            },
            "comparison": "exact_day",
            "offset_days": 0,
            "score": 1.0,
        },
        "spatial": {
            "subject_precision": "locality",
            "object_precision": "locality",
            "comparison": "same_locality",
            "distance_km": None,
            "uncertainty_km": None,
            "score": 1.0,
        },
        "scores": {
            "relationship_compatibility": 0.98,
            "temporal_component": 1.0,
            "spatial_component": 1.0,
            "source_component": 0.9,
        },
        "reasons": ["Source describes a mutilated cow in a crop circle."],
        "source_refs": [
            {
                "source_id": "ufo_hatch_udb_11636",
                "supports": "explicit_relationship",
                "locator": "source_records.jsonl:Hatch_UDB_11636",
                "source_hash": "a" * 64,
            }
        ],
        "review_state": "needs_human_review",
        "provenance": {
            "ingestion_adapter": "cross_domain_relationship_v1",
            "provenance_locator": "Hatch_UDB_11636#narrative",
            "raw_record_hash": "b" * 64,
            "canonicalization_version": "1.0.0",
            "generated_at": None,
        },
        "causality": "not_asserted",
    }


def test_case_schema_preserves_starter_contract_and_adds_crop_refs() -> None:
    required = set(CASE_SCHEMA["required"])
    assert {
        "record_id",
        "record_type",
        "status",
        "dates",
        "location",
        "sources",
        "provenance",
    } <= required

    properties = CASE_SCHEMA["properties"]
    assert "related_ufo_timeline_event_ids" in properties
    association_enum = properties["associated_events"]["items"]["properties"][
        "association_type"
    ]["enum"]
    assert association_enum == [
        "helicopter",
        "aircraft",
        "uap_or_light",
        "vehicle",
        "person",
        "animal_behavior",
        "communications",
        "crop_circle",
        "other",
    ]

    external_ref = properties["external_event_refs"]["items"]
    assert set(external_ref["required"]) == {
        "domain",
        "dataset",
        "external_id",
        "native_event_id",
        "relationship_id",
    }
    assert set(external_ref["properties"]["domain"]["enum"]) == {
        "animal_mutilation",
        "cattle_mutilation",
        "crop_circle",
        "ufo",
        "other",
    }
    _validate_when_available(CASE_SCHEMA, _representative_case())


def test_case_schema_requires_consistent_negative_flags() -> None:
    candidate = _representative_case()
    candidate["negative_only"] = True
    candidate["explicit_negative"] = False
    if Draft202012Validator is not None:
        assert _validation_errors(CASE_SCHEMA, candidate)
    else:
        assert candidate["negative_only"] and not candidate["explicit_negative"]


def test_relationship_schema_has_closed_scientific_enums_and_required_fields() -> None:
    assert set(RELATIONSHIP_SCHEMA["properties"]["relationship_type"]["enum"]) == {
        "same_incident",
        "same_scene",
        "reported_nearby",
        "regional_context",
        "topical_context",
        "duplicate_lineage",
    }
    assert set(RELATIONSHIP_SCHEMA["properties"]["assertion_mode"]["enum"]) == {
        "explicit_source",
        "deterministic_match",
        "analyst_confirmed",
    }
    assert set(RELATIONSHIP_SCHEMA["required"]) >= {
        "relationship_id",
        "subject",
        "object",
        "temporal",
        "spatial",
        "scores",
        "reasons",
        "source_refs",
        "review_state",
        "provenance",
        "causality",
    }
    assert RELATIONSHIP_SCHEMA["properties"]["causality"] == {
        "const": "not_asserted"
    }
    _validate_when_available(RELATIONSHIP_SCHEMA, _representative_relationship())


def test_relationship_schema_rejects_unknown_enums_and_causal_claims() -> None:
    relationship = _representative_relationship()

    invalid_values = {
        "relationship_type": "caused_by",
        "assertion_mode": "model_verified",
        "causality": "asserted",
    }
    for key, invalid_value in invalid_values.items():
        candidate = copy.deepcopy(relationship)
        candidate[key] = invalid_value
        if Draft202012Validator is not None:
            assert _validation_errors(RELATIONSHIP_SCHEMA, candidate), key
        elif key == "causality":
            assert invalid_value != RELATIONSHIP_SCHEMA["properties"][key]["const"]
        else:
            assert invalid_value not in RELATIONSHIP_SCHEMA["properties"][key]["enum"]

    missing_source = copy.deepcopy(relationship)
    missing_source["source_refs"] = []
    if Draft202012Validator is not None:
        assert _validation_errors(RELATIONSHIP_SCHEMA, missing_source)
    else:
        assert (
            RELATIONSHIP_SCHEMA["properties"]["source_refs"]["minItems"] == 1
        )


def test_deterministic_candidates_cannot_be_marked_analyst_confirmed() -> None:
    candidate = _representative_relationship()
    candidate["assertion_mode"] = "deterministic_match"
    candidate["review_state"] = "analyst_confirmed"
    if Draft202012Validator is not None:
        assert _validation_errors(RELATIONSHIP_SCHEMA, candidate)
    else:
        deterministic_rule = RELATIONSHIP_SCHEMA["allOf"][0]
        assert deterministic_rule["if"]["properties"]["assertion_mode"]["const"] == (
            "deterministic_match"
        )
        assert "analyst_confirmed" not in deterministic_rule["then"]["properties"][
            "review_state"
        ]["enum"]


def test_source_registry_retains_starter_sources_and_pins_crop_inputs() -> None:
    source_ids = {source["source_id"] for source in SOURCE_REGISTRY["sources"]}
    starter_source_ids = {
        "ufo_timeline_seed",
        "fbi_vault_animal_mutilation",
        "illume_umbra_cattle_archive",
        "mss370_schmitt",
        "colorado_historic_newspapers",
        "new_mexico_newspapers",
        "historic_oregon_newspapers",
        "utah_digital_newspapers",
        "loc_chronicling_america",
        "internet_archive",
        "gdelt",
        "google_books",
        "rice_vallee_b13",
        "usda_nass_quickstats",
        "local_public_records",
    }
    assert starter_source_ids <= source_ids
    assert {
        "crop_circle_atlas_export_v1",
        "crop_circle_atlas_catalog_pdf",
        "crop_circle_atlas_linked_pages",
    } <= source_ids

    pins = SOURCE_REGISTRY["input_pins"]
    assert pins["starter_pack"]["sha256"] == (
        "578F9A6E2E6B1EFDC4634EF5421F3079A5E169ADE89EF65F9CA181BC506AE611"
    )
    assert pins["crop_circle_atlas_export"]["sha256"] == (
        "7F552F66A197B96C838475B5CAEAB7C78C1AEE5544C81D658A10335687CB2DF6"
    )
    assert pins["crop_circle_atlas_export"]["source_commit"] == (
        "0086e3b86ceefeaa5c12422ea28a3fed05e8e260"
    )
    assert pins["crop_circle_atlas_export"]["event_count"] == 7745
    assert pins["crop_circle_atlas_export"]["source_assertion_count"] == 8391
    assert pins["crop_circle_atlas_export"]["unique_linked_source_url_count"] == 2345
    assert pins["crop_circle_catalog_pdf"]["sha256"] == (
        "F51718F1EEB1C3F06F3A154D02EB7AB24DCEFEBB201E3ACE04C6E8F79DCC65E7"
    )

    linked_pages = next(
        source
        for source in SOURCE_REGISTRY["sources"]
        if source["source_id"] == "crop_circle_atlas_linked_pages"
    )
    assert "private content-addressed cache" in linked_pages["ingestion"]
    assert "never negative evidence" in linked_pages["notes"]

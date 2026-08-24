from parser.location_display import (
    LOCATION_DISPLAY_NORMALIZATION_POLICY,
    apply_location_display_normalization,
)
from parser.utils import write_jsonl
from scripts.build_canonical_web_artifacts import build_canonical_web_artifacts


def test_majestic_environment_and_redundant_state_are_display_only() -> None:
    event = {
        "source_name": "majestic",
        "location_raw": "Coastlands, CRESCENT CITY, CA, California, USA",
        "raw_fields": {
            "key_vals/Locale": "Coastlands",
            "location/0": "CRESCENT CITY, CA",
            "key_vals/State/Prov": "California",
            "key_vals/Country": "USA",
        },
    }

    normalized = apply_location_display_normalization(event)

    assert normalized["location_raw"] == event["location_raw"]
    assert normalized["raw_fields"] == event["raw_fields"]
    assert normalized["location_display"] == "CRESCENT CITY, CA, USA"
    assert normalized["location_display_normalizations"] == [
        {
            "policy_id": LOCATION_DISPLAY_NORMALIZATION_POLICY,
            "transformations": [
                "remove_majestic_environment_category",
                "remove_redundant_us_state_components",
            ],
            "raw_location_preserved": True,
        }
    ]


def test_generic_normalization_removes_empty_duplicate_and_placeholder_components() -> None:
    event = {
        "source_name": "mufon",
        "location_raw": "Unknown City,, Paris, Paris, France",
    }

    normalized = apply_location_display_normalization(event)

    assert normalized["location_raw"] == event["location_raw"]
    assert normalized["location_display"] == "Paris, France"
    assert normalized["location_display_normalizations"][0]["transformations"] == [
        "remove_empty_components",
        "remove_placeholder_components",
        "remove_adjacent_duplicate_components",
    ]


def test_distinct_us_states_are_not_guessed() -> None:
    event = {
        "source_name": "mufon",
        "location_raw": "Augusta, Georgia, SC, US",
    }

    normalized = apply_location_display_normalization(event)

    assert normalized["location_raw"] == event["location_raw"]
    assert normalized["location_display"] == "Augusta, US"
    assert normalized["location_display_normalizations"][0]["transformations"] == [
        "omit_conflicting_us_state_components"
    ]


def test_parenthesized_conflict_is_left_for_review_when_tokenizing_would_damage_label() -> None:
    event = {
        "source_name": "nuforc",
        "location_raw": "Washington DC (Suitland, MD), DC, USA",
    }

    normalized = apply_location_display_normalization(event)

    assert normalized == event


def test_existing_reviewed_display_label_wins_and_is_idempotent() -> None:
    event = {
        "source_name": "majestic",
        "location_raw": "Farmlands, NAPA VALLEY, CA, Colorado, USA",
        "location_display": "Napa Valley near Napa, Napa County, California, USA",
    }

    assert apply_location_display_normalization(event) == event


def test_markdown_location_link_is_unwrapped_without_losing_raw_value() -> None:
    event = {
        "source_name": "majestic",
        "location_raw": "[Pearl Harbor, Hawaii](https://example.test/map)",
    }

    normalized = apply_location_display_normalization(event)

    assert normalized["location_raw"] == event["location_raw"]
    assert normalized["location_display"] == "Pearl Harbor, Hawaii"
    assert normalized["location_display_normalizations"][0]["transformations"] == [
        "unwrap_markdown_location_link"
    ]


def test_existing_display_can_be_cleaned_when_raw_label_is_absent() -> None:
    event = {
        "source_name": "mufon",
        "location_display": "Paris,, France",
    }

    normalized = apply_location_display_normalization(event)

    assert normalized["location_display"] == "Paris, France"
    assert normalized["location_display_normalizations"][0][
        "raw_location_preserved"
    ] is False


def test_canonical_web_exports_display_normalization_and_policy_count(tmp_path) -> None:
    input_path = tmp_path / "events.jsonl"
    output_dir = tmp_path / "canonical_web"
    event = {
        "canonical_input_id": "cin_display",
        "canonical_input_ids": ["cin_display"],
        "canonical_event_id": "evt_display",
        "source_name": "majestic",
        "source_file": "majestic.csv",
        "source_native_id": "display",
        "source_row_number": 1,
        "source_row_hash": "hash",
        "source_provenance": [],
        "duplicate_record_count": 1,
        "dedupe_strategy": "single_record",
        "location_raw": "Farmlands, TESTVILLE, CA, California, USA",
        "lat": 38.0,
        "lon": -122.0,
        "coordinate_source": "raw_latlong",
        "location_precision": "exact_coords",
        "raw_fields": {"key_vals/Locale": "Farmlands"},
    }
    write_jsonl(input_path, [event])

    build_canonical_web_artifacts(
        input_path=input_path,
        output_dir=output_dir,
        chunk_size=1,
        summary_shard_size=1,
    )

    import json

    detail = json.loads(
        (output_dir / "event_chunks/chunk_000000.json").read_text(encoding="utf-8")
    )[0]
    summary = json.loads(
        (output_dir / "summary_shards/summary_000000.json").read_text(
            encoding="utf-8"
        )
    )[0]
    manifest = json.loads(
        (output_dir / "canonical_web_manifest.json").read_text(encoding="utf-8")
    )

    assert detail["location_raw"] == event["location_raw"]
    assert detail["location_display"] == "TESTVILLE, CA, USA"
    assert detail["raw_fields"] == event["raw_fields"]
    assert detail["location_display_normalizations"][0]["policy_id"] == (
        LOCATION_DISPLAY_NORMALIZATION_POLICY
    )
    assert summary["location_display"] == detail["location_display"]
    assert manifest["policy"]["location_display_normalizations"] == {
        "applied": True,
        "event_count": 1,
        "policy_counts": {LOCATION_DISPLAY_NORMALIZATION_POLICY: 1},
        "raw_source_fields_preserved": True,
    }

import json

from scripts.audit_static_location_labels import audit_static_location_labels


def write_summary(root, events):
    summary_dir = root / "data" / "canonical_web" / "summary_shards"
    summary_dir.mkdir(parents=True)
    (summary_dir / "summary_000000.json").write_text(
        json.dumps(events), encoding="utf-8"
    )


def test_location_label_audit_classifies_source_categories_and_state_risks(tmp_path):
    root = tmp_path / "bundle"
    write_summary(
        root,
        [
            {
                "event_id": "napa",
                "source": "majestic",
                "location_raw": "Farmlands, NAPA VALLEY, CA, Colorado, USA",
            },
            {
                "event_id": "crescent-city",
                "source": "majestic",
                "location_raw": "Coastlands, CRESCENT CITY, CA, California, USA",
            },
            {
                "event_id": "ordinary",
                "source": "nuforc",
                "location_raw": "Evansville, IN, USA",
            },
        ],
    )

    report = audit_static_location_labels(payload_root=root)

    assert report["counts"] == {
        "scanned_events": 3,
        "events_with_findings": 2,
        "finding_rows": 4,
    }
    assert report["reason_counts"] == {
        "contradictory_us_state_components": 1,
        "majestic_environment_category_prefix": 2,
        "redundant_us_state_components": 1,
    }


def test_location_label_audit_prefers_reviewed_display_label(tmp_path):
    root = tmp_path / "bundle"
    write_summary(
        root,
        [
            {
                "event_id": "napa",
                "source": "majestic",
                "location_raw": "Farmlands, NAPA VALLEY, CA, Colorado, USA",
                "location_display": (
                    "Napa Valley near Napa, Napa County, California, USA"
                ),
            }
        ],
    )

    report = audit_static_location_labels(payload_root=root)

    assert report["status"] == "ready"
    assert report["counts"]["events_with_findings"] == 0


def test_location_label_audit_flags_structural_display_problems(tmp_path):
    root = tmp_path / "bundle"
    write_summary(
        root,
        [
            {
                "event_id": "structural",
                "source": "other",
                "location_raw": "Unknown City,, Paris, Paris, France",
            },
            {
                "event_id": "coordinate",
                "source": "majestic",
                "location_raw": "37.0000 -116.0000, USA",
            },
        ],
    )

    report = audit_static_location_labels(payload_root=root)

    assert report["reason_counts"] == {
        "adjacent_duplicate_component": 1,
        "coordinate_literal_as_place": 1,
        "empty_comma_component": 1,
        "placeholder_component_with_context": 1,
    }


def test_location_label_audit_treats_source_only_nonplaces_as_missing(tmp_path):
    root = tmp_path / "bundle"
    write_summary(
        root,
        [
            {"event_id": "commas", "source": "mufon", "location_raw": ","},
            {
                "event_id": "placeholders",
                "source": "majestic",
                "location_raw": "unknown location, Unknown",
            },
            {"event_id": "environment", "source": "majestic", "location_raw": "Desert"},
        ],
    )

    report = audit_static_location_labels(payload_root=root)

    assert report["reason_counts"] == {"missing_location_label": 3}


def test_location_label_audit_recognizes_state_codes_next_to_punctuation(tmp_path):
    root = tmp_path / "bundle"
    write_summary(
        root,
        [
            {
                "event_id": "parenthetical-state",
                "source": "nuforc",
                "location_raw": "Washington DC (Suitland, MD), DC, USA",
            }
        ],
    )

    report = audit_static_location_labels(payload_root=root)

    assert report["reason_counts"] == {"contradictory_us_state_components": 1}

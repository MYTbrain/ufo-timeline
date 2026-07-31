import json
import zipfile

from scripts.apply_jurisdiction_coordinate_repair_preview import (
    apply_jurisdiction_coordinate_repair_preview,
)


def write_geonames_zip(path):
    lines = [
        "\t".join(
            [
                "5059163",
                "Fargo",
                "Fargo",
                "Fargo",
                "46.87719",
                "-96.7898",
                "P",
                "PPL",
                "US",
                "",
                "ND",
                "017",
                "",
                "",
                "125990",
                "",
                "274",
                "America/Chicago",
                "2025-01-01",
            ]
        ),
        "\t".join(
            [
                "4180439",
                "Atlanta",
                "Atlanta",
                "Atlanta",
                "33.749",
                "-84.388",
                "P",
                "PPLA",
                "US",
                "",
                "GA",
                "121",
                "",
                "",
                "498715",
                "",
                "320",
                "America/New_York",
                "2025-01-01",
            ]
        ),
    ]
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("allCountries.txt", "\n".join(lines) + "\n")


def test_jurisdiction_coordinate_repair_replaces_outside_state_with_same_state_geonames(tmp_path):
    events = tmp_path / "events.jsonl"
    events.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "canonical_event_id": "fargo",
                        "source_name": "ufocat",
                        "source_row_number": 1,
                        "location_raw": "FARGO, Cass, ND, US",
                        "lat": 46.88,
                        "lon": 96.78,
                        "coordinate_source": "raw_latlong",
                        "location_precision": "exact_coords",
                    }
                ),
                json.dumps(
                    {
                        "canonical_event_id": "atlanta",
                        "source_name": "ufocat",
                        "source_row_number": 2,
                        "location_raw": "ATLANTA, Fulton, GA, US",
                        "lat": 33.11,
                        "lon": -94.16,
                        "coordinate_source": "raw_latlong",
                        "location_precision": "exact_coords",
                    }
                ),
                json.dumps(
                    {
                        "canonical_event_id": "inside",
                        "source_name": "ufocat",
                        "source_row_number": 3,
                        "location_raw": "FARGO, Cass, ND, US",
                        "lat": 46.88,
                        "lon": -96.78,
                        "coordinate_source": "raw_latlong",
                        "location_precision": "exact_coords",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    geonames = tmp_path / "allCountries.zip"
    write_geonames_zip(geonames)

    report = apply_jurisdiction_coordinate_repair_preview(
        input_path=events,
        geonames_zip=geonames,
        output_dir=tmp_path / "out",
        report_output=tmp_path / "report.json",
    )
    rows = [json.loads(line) for line in (tmp_path / "out" / "deduped_events.jsonl").read_text(encoding="utf-8").splitlines()]

    assert report["outside_state_count"] == 2
    assert report["repaired_event_count"] == 2
    assert report["quarantined_event_count"] == 0
    assert rows[0]["lat"] == 46.87719
    assert rows[0]["lon"] == -96.7898
    assert rows[0]["jurisdiction_coordinate_repair_action"] == "replace_with_same_state_geonames_city"
    assert rows[1]["lat"] == 33.749
    assert rows[1]["lon"] == -84.388
    assert "jurisdiction_coordinate_repair_action" not in rows[2]


def test_jurisdiction_coordinate_repair_unmaps_when_no_same_state_city_match(tmp_path):
    events = tmp_path / "events.jsonl"
    events.write_text(
        json.dumps(
            {
                "canonical_event_id": "bad",
                "source_name": "ufocat",
                "source_row_number": 1,
                "location_raw": "NOTAREALPLACE, Cass, ND, US",
                "lat": 46.88,
                "lon": 96.78,
                "coordinate_source": "raw_latlong",
                "location_precision": "exact_coords",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    geonames = tmp_path / "allCountries.zip"
    write_geonames_zip(geonames)

    report = apply_jurisdiction_coordinate_repair_preview(
        input_path=events,
        geonames_zip=geonames,
        output_dir=tmp_path / "out",
        report_output=tmp_path / "report.json",
    )
    row = json.loads((tmp_path / "out" / "deduped_events.jsonl").read_text(encoding="utf-8"))

    assert report["outside_state_count"] == 1
    assert report["repaired_event_count"] == 0
    assert report["quarantined_event_count"] == 1
    assert row["lat"] is None
    assert row["lon"] is None
    assert row["coordinate_source"] == "unresolved"
    assert row["jurisdiction_coordinate_repair_action"] == "quarantine_unmapped"

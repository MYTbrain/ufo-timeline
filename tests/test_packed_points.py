import json
import struct

from parser.packed_points import MISSING_DETAIL_INDEX, MISSING_INT64, SCHEMA_VERSION, export_packed_points


def test_export_packed_points_roundtrips_binary_rows(tmp_path):
    metadata = export_packed_points(
        [
            {
                "event_id": 10,
                "lat": "31.766668",
                "lon": "35.233335",
                "sort_date_iso": "1970-05-21",
                "estimated_utc_timestamp_ms": 123456789,
                "source": "Hatch",
                "type": "sighting",
                "shape_normalized": "cylinder",
                "visual_type_group": "Craft",
                "date_precision": "exact_day",
                "location_precision": "exact_coords",
                "coordinate_source": "raw_latlong",
                "chunk_id": "chunk_000",
                "detail_index": 7,
            },
            {
                "event_id": 11,
                "lat": 40.7128,
                "lon": -74.006,
                "date_iso": "1997-03-13",
                "source_name": "NUFORC",
                "type_raw": "triangle",
                "shape_normalized": "Triangle",
                "visual_type_group": "Craft",
                "date_precision": "exact_day",
                "location_precision": "city",
                "coordinate_source": "geocoded",
            },
        ],
        tmp_path,
    )

    rows = _read_packed_rows(tmp_path / "points.bin", metadata)

    assert (tmp_path / "points_meta.json").exists()
    assert SCHEMA_VERSION == 3
    assert metadata["schema_version"] == SCHEMA_VERSION
    assert metadata["row_count"] == 2
    assert metadata["bytes_per_row"] == struct.calcsize(metadata["struct_format"])
    assert metadata["lookup_tables"]["sources"] == [None, "Hatch", "NUFORC"]
    assert metadata["lookup_tables"]["types"] == [None, "sighting", "triangle"]
    assert metadata["lookup_tables"]["shapes"] == [None, "cylinder", "Triangle"]
    assert metadata["lookup_tables"]["visual_type_groups"] == [None, "Craft"]
    assert metadata["lookup_tables"]["craft_types"] == [None]
    assert metadata["lookup_tables"]["craft_type_confidences"] == [None]
    assert metadata["lookup_tables"]["craft_type_sources"] == [None]
    assert metadata["lookup_tables"]["same_day_match_strengths"] == [None]
    assert metadata["lookup_tables"]["date_precisions"] == [None, "exact_day"]
    assert metadata["lookup_tables"]["location_precisions"] == [None, "city", "exact_coords"]
    assert metadata["lookup_tables"]["coordinate_sources"] == [None, "geocoded", "raw_latlong"]
    assert metadata["lookup_tables"]["chunk_ids"] == [None, "chunk_000"]

    assert rows[0] == {
        "event_id": 10,
        "lat": 31.766668,
        "lon": 35.233335,
        "sort_date_key": 19700521,
        "sort_time_ms": 123456789,
        "source_id": "Hatch",
        "type_id": "sighting",
        "shape_id": "cylinder",
        "visual_type_group_id": "Craft",
        "craft_type_id": None,
        "craft_type_confidence_id": None,
        "craft_type_source_id": None,
        "same_day_match_strength_id": None,
        "date_precision_id": "exact_day",
        "location_precision_id": "exact_coords",
        "coordinate_source_id": "raw_latlong",
        "chunk_id": "chunk_000",
        "detail_index": 7,
    }
    assert rows[1]["event_id"] == 11
    assert rows[1]["source_id"] == "NUFORC"
    assert rows[1]["type_id"] == "triangle"
    assert rows[1]["shape_id"] == "Triangle"
    assert rows[1]["visual_type_group_id"] == "Craft"
    assert rows[1]["date_precision_id"] == "exact_day"
    assert rows[1]["location_precision_id"] == "city"
    assert rows[1]["coordinate_source_id"] == "geocoded"
    assert rows[1]["sort_date_key"] == 19970313
    assert rows[1]["sort_time_ms"] == MISSING_INT64
    assert rows[1]["chunk_id"] is None
    assert rows[1]["detail_index"] == -1


def test_export_packed_points_filters_unmapped_and_leaves_missing_detail_without_manifest_details(tmp_path):
    metadata = export_packed_points(
        [
            {
                "event_id": 2500,
                "lat": None,
                "lon": None,
                "coordinate_source": "unresolved",
                "source": "Skipped",
            },
            {
                "event_id": 2501,
                "lat": 35,
                "lon": -105,
                "coordinate_source": "geocoded",
                "source": "Mapped",
                "type": "light",
            },
        ],
        tmp_path,
        chunk_manifest=[
            {
                "id": "chunk_001",
                "start_event_id": 2500,
                "end_event_id": 4999,
            }
        ],
    )

    rows = _read_packed_rows(tmp_path / "points.bin", metadata)

    assert metadata["row_count"] == 1
    assert metadata["input"]["event_count"] == 2
    assert metadata["input"]["skipped_event_count"] == 1
    assert metadata["lookup_tables"]["sources"] == [None, "Mapped"]
    assert metadata["lookup_tables"]["chunk_ids"] == [None, "chunk_001"]
    assert rows[0]["event_id"] == 2501
    assert rows[0]["chunk_id"] == "chunk_001"
    assert rows[0]["detail_index"] == MISSING_DETAIL_INDEX


def test_export_packed_points_uses_manifest_details_for_sparse_event_ids(tmp_path):
    metadata = export_packed_points(
        [
            {
                "event_id": 6100,
                "lat": 34.05,
                "lon": -118.25,
                "source": "Sparse",
            },
            {
                "event_id": 6150,
                "lat": 36.17,
                "lon": -115.14,
                "source": "Sparse",
            },
        ],
        tmp_path,
        chunk_manifest=[
            {
                "id": "chunk_sparse",
                "start_event_id": 6100,
                "end_event_id": 6200,
                "details": [
                    {"event_id": 6100},
                    {"event_id": 6150},
                ],
            }
        ],
    )

    rows = _read_packed_rows(tmp_path / "points.bin", metadata)

    assert metadata["lookup_tables"]["chunk_ids"] == [None, "chunk_sparse"]
    assert rows[0]["chunk_id"] == "chunk_sparse"
    assert rows[0]["detail_index"] == 0
    assert rows[1]["chunk_id"] == "chunk_sparse"
    assert rows[1]["detail_index"] == 1


def test_export_packed_points_is_deterministic(tmp_path):
    events = [
        {
            "event_id": 2,
            "lat": 1.25,
            "lon": 2.5,
            "sort_date_iso": "2000-01-02",
            "source": "Beta",
            "type": "orb",
        },
        {
            "event_id": 1,
            "lat": -3,
            "lon": 4,
            "sort_date_iso": "1999-12-31",
            "source": "Alpha",
            "type": "disk",
        },
    ]
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"

    export_packed_points(events, first_dir)
    export_packed_points(events, second_dir)

    assert (first_dir / "points.bin").read_bytes() == (second_dir / "points.bin").read_bytes()
    first_meta = json.loads((first_dir / "points_meta.json").read_text(encoding="utf-8"))
    second_meta = json.loads((second_dir / "points_meta.json").read_text(encoding="utf-8"))
    assert first_meta == second_meta


def _read_packed_rows(path, metadata):
    row_struct = struct.Struct(metadata["struct_format"])
    fields = metadata["fields"]
    data = path.read_bytes()
    assert len(data) == metadata["row_count"] * metadata["bytes_per_row"]

    rows = []
    for unpacked in row_struct.iter_unpack(data):
        row = {}
        for field, value in zip(fields, unpacked):
            table_name = field.get("lookup_table")
            if table_name:
                value = metadata["lookup_tables"][table_name][value]
            row[field["name"]] = value
        rows.append(row)
    return rows

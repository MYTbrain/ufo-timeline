import gzip
import json

from scripts.summarize_updb_location_id_mapping_candidates import (
    summarize_updb_location_id_mapping_candidates,
)


def write_jsonl(path, rows):
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def write_updb_sql_gz(path, rows):
    body = [
        "CREATE TABLE api.location (",
        "    id integer NOT NULL",
        ");",
        "COPY api.location (id, city, district, country, water, other, latitude, longitude, geoname_id, population, fclass) FROM stdin;",
        *rows,
        "\\.",
    ]
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        handle.write("\n".join(body) + "\n")


def test_updb_location_id_candidates_accept_matching_city_country(tmp_path):
    input_path = tmp_path / "events.jsonl"
    write_jsonl(
        input_path,
        [
            {
                "canonical_event_id": "evt1",
                "source_name": "phenomenainon_updb",
                "location_raw": "COLUMBUS, US",
                "city": "COLUMBUS",
                "country": "US",
                "lat": None,
                "lon": None,
                "raw_fields": {"location": "5188517"},
            },
            {
                "canonical_event_id": "evt2",
                "source_name": "phenomenainon_updb",
                "location_raw": "SPRINGFIELD, US",
                "city": "SPRINGFIELD",
                "country": "US",
                "lat": 1.0,
                "lon": 2.0,
                "raw_fields": {"location": "5218795"},
            },
        ],
    )
    sql_path = tmp_path / "phenomenon.sql.gz"
    write_updb_sql_gz(
        sql_path,
        [
            "5188517\tCOLUMBUS\tOHIO\tUS\t\t\t39.96118\t-82.99879\t4509177\t905748\tP",
            "5218795\tSPRINGFIELD\tOREGON\tUS\t\t\t44.04624\t-123.02203\t5754005\t60870\tP",
        ],
    )

    report = summarize_updb_location_id_mapping_candidates(input_path=input_path, updb_sql_gz=sql_path)

    assert report["canonical_outputs_mutated"] is False
    assert report["candidate_event_count"] == 1
    candidate = report["candidates"][0]
    assert candidate["canonical_event_id"] == "evt1"
    assert candidate["query"] == "columbus, us"
    assert candidate["confidence"] == "high"
    assert candidate["admin1"] == "OHIO"
    assert candidate["updb_location_id"] == "5188517"


def test_updb_location_id_candidates_reject_mismatches_and_bad_coordinates(tmp_path):
    input_path = tmp_path / "events.jsonl"
    write_jsonl(
        input_path,
        [
            {
                "canonical_event_id": "evt1",
                "source_name": "phenomenainon_updb",
                "location_raw": "COLUMBUS, US",
                "city": "COLUMBUS",
                "country": "US",
                "lat": None,
                "lon": None,
                "raw_fields": {"location": "1"},
            },
            {
                "canonical_event_id": "evt2",
                "source_name": "phenomenainon_updb",
                "location_raw": "ROME, US",
                "city": "ROME",
                "country": "US",
                "lat": None,
                "lon": None,
                "raw_fields": {"location": "2"},
            },
            {
                "canonical_event_id": "evt3",
                "source_name": "phenomenainon_updb",
                "location_raw": "PARIS, US",
                "city": "PARIS",
                "country": "US",
                "lat": None,
                "lon": None,
                "raw_fields": {"location": "3"},
            },
        ],
    )
    sql_path = tmp_path / "phenomenon.sql.gz"
    write_updb_sql_gz(
        sql_path,
        [
            "1\tCOLUMBUS\tOHIO\tUS\t\t\t\\N\t\\N\t4509177\t905748\tP",
            "2\tROME\tLAZIO\tIT\t\t\t41.8933\t12.4829\t3169070\t2318895\tP",
            "3\tPARIS\tTEXAS\tUS\t\t\t999\t-95.5555\t4717560\t24782\tP",
        ],
    )

    report = summarize_updb_location_id_mapping_candidates(input_path=input_path, updb_sql_gz=sql_path)

    assert report["candidate_event_count"] == 0
    assert report["rejected_event_counts"]["missing_coordinates"] == 1
    assert report["rejected_event_counts"]["country_mismatch"] == 1
    assert report["rejected_event_counts"]["invalid_coordinates"] == 1

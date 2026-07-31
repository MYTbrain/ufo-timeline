import json

from scripts.summarize_duplicate_candidate_clusters import summarize_duplicate_candidate_clusters


def _write_jsonl(path, records):
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )


def test_summarize_duplicate_candidate_clusters_reports_connected_components(tmp_path):
    candidates_path = tmp_path / "duplicate_candidates.jsonl"
    _write_jsonl(
        candidates_path,
        [
            {
                "score": 1.0,
                "reasons": ["same_strong_date"],
                "blocking": {"date_iso": "1950-01-01", "location_key": "a"},
                "canonical_input_ids": ["cin_a", "cin_b"],
            },
            {
                "score": 1.0,
                "reasons": ["same_strong_date"],
                "blocking": {"date_iso": "1950-01-01", "location_key": "a"},
                "canonical_input_ids": ["cin_b", "cin_c"],
            },
            {
                "score": 0.9,
                "reasons": ["same_normalized_location"],
                "blocking": {"date_iso": "1950-01-02", "location_key": "b"},
                "canonical_input_ids": ["cin_d", "cin_e"],
            },
        ],
    )

    report = summarize_duplicate_candidate_clusters(candidates_path)

    assert report["canonical_outputs_mutated"] is False
    assert report["candidate_edge_count"] == 3
    assert report["candidate_input_node_count"] == 5
    assert report["candidate_cluster_count"] == 2
    assert report["projected_cluster_reduction_if_all_edges_same_event"] == 3
    assert report["dense_pair_capacity_waste"] == 0
    assert report["component_size_summary"]["top_25"] == [3, 2]
    assert report["reason_counts"] == {
        "same_normalized_location": 1,
        "same_strong_date": 2,
    }


def test_summarize_duplicate_candidate_clusters_detects_dense_pair_waste(tmp_path):
    candidates_path = tmp_path / "duplicate_candidates.jsonl"
    _write_jsonl(
        candidates_path,
        [
            {"score": 1.0, "canonical_input_ids": ["cin_a", "cin_b"]},
            {"score": 1.0, "canonical_input_ids": ["cin_a", "cin_c"]},
            {"score": 1.0, "canonical_input_ids": ["cin_b", "cin_c"]},
        ],
    )

    report = summarize_duplicate_candidate_clusters(candidates_path)

    assert report["candidate_edge_count"] == 3
    assert report["candidate_cluster_count"] == 1
    assert report["projected_cluster_reduction_if_all_edges_same_event"] == 2
    assert report["dense_pair_capacity_waste"] == 1

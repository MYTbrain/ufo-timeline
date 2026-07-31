"""Summarize duplicate-candidate pair edges as connected components.

The current fuzzy candidate queue is pairwise and capped. This report shows how
many independent clusters those pair edges actually represent, so we can tell
whether the cap is being consumed by dense all-pairs groups.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_CANDIDATES_PATH = Path("data/canonical_full/duplicate_candidates.jsonl")
DEFAULT_OUTPUT = Path("data/reports/duplicate_candidate_cluster_summary.json")


class DisjointSet:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}
        self.rank: dict[str, int] = {}

    def add(self, value: str) -> None:
        if value not in self.parent:
            self.parent[value] = value
            self.rank[value] = 0

    def find(self, value: str) -> str:
        self.add(value)
        parent = self.parent[value]
        if parent != value:
            self.parent[value] = self.find(parent)
        return self.parent[value]

    def union(self, left: str, right: str) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root == right_root:
            return
        if self.rank[left_root] < self.rank[right_root]:
            left_root, right_root = right_root, left_root
        self.parent[right_root] = left_root
        if self.rank[left_root] == self.rank[right_root]:
            self.rank[left_root] += 1


def summarize_duplicate_candidate_clusters(candidates_path: Path = DEFAULT_CANDIDATES_PATH) -> dict[str, Any]:
    candidates = read_jsonl(candidates_path)
    dsu = DisjointSet()
    edge_count = 0
    candidate_score_counts: dict[str, int] = {}
    reason_counts: dict[str, int] = {}
    block_edge_counts: dict[str, int] = {}

    for candidate in candidates:
        input_ids = normalized_id_list(candidate.get("canonical_input_ids"))
        if len(input_ids) < 2:
            continue
        edge_count += 1
        dsu.union(input_ids[0], input_ids[1])
        candidate_score_counts[str(candidate.get("score"))] = candidate_score_counts.get(str(candidate.get("score")), 0) + 1
        for reason in candidate.get("reasons") or []:
            reason_text = str(reason)
            reason_counts[reason_text] = reason_counts.get(reason_text, 0) + 1
        block = candidate.get("blocking") if isinstance(candidate.get("blocking"), dict) else {}
        block_key = f"{block.get('date_iso') or ''}|{block.get('location_key') or ''}"
        block_edge_counts[block_key] = block_edge_counts.get(block_key, 0) + 1

    components: dict[str, set[str]] = {}
    for input_id in dsu.parent:
        components.setdefault(dsu.find(input_id), set()).add(input_id)

    component_sizes = sorted((len(ids) for ids in components.values()), reverse=True)
    projected_cluster_reduction = sum(size - 1 for size in component_sizes if size > 1)
    dense_pair_capacity_waste = edge_count - projected_cluster_reduction
    return {
        "schema_version": 1,
        "report_policy": "analysis_only",
        "canonical_outputs_mutated": False,
        "input": str(candidates_path),
        "candidate_edge_count": edge_count,
        "candidate_input_node_count": len(dsu.parent),
        "candidate_cluster_count": len(component_sizes),
        "projected_cluster_reduction_if_all_edges_same_event": projected_cluster_reduction,
        "dense_pair_capacity_waste": dense_pair_capacity_waste,
        "component_size_summary": {
            "max": max(component_sizes) if component_sizes else 0,
            "top_25": component_sizes[:25],
            "singletons": sum(1 for size in component_sizes if size == 1),
            "size_2": sum(1 for size in component_sizes if size == 2),
            "size_3_to_5": sum(1 for size in component_sizes if 3 <= size <= 5),
            "size_6_to_20": sum(1 for size in component_sizes if 6 <= size <= 20),
            "size_over_20": sum(1 for size in component_sizes if size > 20),
        },
        "candidate_score_counts": dict(sorted(candidate_score_counts.items())),
        "reason_counts": dict(sorted(reason_counts.items())),
        "top_blocks_by_edge_count": [
            {"block": block, "edge_count": count}
            for block, count in sorted(block_edge_counts.items(), key=lambda item: (-item[1], item[0]))[:25]
        ],
    }


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(f"{path} line {line_number} must be a JSON object.")
            records.append(payload)
    return records


def normalized_id_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [text for item in value if (text := str(item or "").strip())]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = summarize_duplicate_candidate_clusters(args.candidates)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(args.output),
        "candidate_edge_count": report["candidate_edge_count"],
        "candidate_cluster_count": report["candidate_cluster_count"],
        "projected_cluster_reduction_if_all_edges_same_event": report[
            "projected_cluster_reduction_if_all_edges_same_event"
        ],
        "dense_pair_capacity_waste": report["dense_pair_capacity_waste"],
        "canonical_outputs_mutated": False,
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

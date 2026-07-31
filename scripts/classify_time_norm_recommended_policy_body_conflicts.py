"""Classify merge-body conflicts for the recommended time-normalization lane.

This report narrows the final apply-policy blocker by proving which compact
policy-body previews have only expected time conflicts and which have additional
text conflicts that are punctuation-only. It is report-only and does not create
decisions, apply merges, or mutate canonical outputs.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any


DEFAULT_POLICY_BODY_PREVIEW = Path("data/reports/entity_resolution_cluster_time_norm_recommended_policy_body_preview.json")
DEFAULT_OUTPUT_JSON = Path("data/reports/entity_resolution_cluster_time_norm_recommended_policy_conflict_classification.json")
DEFAULT_OUTPUT_CSV = Path("data/reports/entity_resolution_cluster_time_norm_recommended_policy_conflict_classification.csv")
DEFAULT_OUTPUT_MARKDOWN = Path("data/reports/entity_resolution_cluster_time_norm_recommended_policy_conflict_classification.md")

CLASSIFICATION_POLICY = "entity_resolution_time_norm_recommended_policy_conflict_classification_only"
EXPECTED_PREVIEW_POLICY = "entity_resolution_cluster_canonical_merge_body_policy_preview_only"
EXPECTED_POLICY = "entity_resolution_cluster_canonical_merge_policy_proposal_v1"

CSV_FIELDS = (
    "review_item_id",
    "effect_id",
    "classification",
    "risk_tier",
    "policy_action",
    "conflict_fields",
    "source_event_count",
    "canonical_input_id_count",
    "blockers",
)


def classify_time_norm_recommended_policy_body_conflicts(policy_body_preview: dict[str, Any]) -> dict[str, Any]:
    validate_policy_body_preview(policy_body_preview)
    previews = [item for item in policy_body_preview.get("previews") or [] if isinstance(item, dict)]
    items = [classify_preview(item) for item in previews]
    return {
        "schema_version": 1,
        "classification_policy": CLASSIFICATION_POLICY,
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "auto_merge_performed": False,
        "ready_for_canonical_apply": False,
        "summary": {
            "policy_body_preview_count": len(previews),
            "classification_counts": count_by(items, "classification"),
            "risk_tier_counts": count_by(items, "risk_tier"),
            "policy_action_counts": count_by(items, "policy_action"),
            "blocker_counts": count_blockers(items),
            "time_only_preview_count": sum(1 for item in items if item.get("classification") == "time_raw_only"),
            "punctuation_only_text_variant_count": sum(
                1 for item in items if item.get("classification") == "time_raw_with_punctuation_only_text_variants"
            ),
            "blocking_preview_count": sum(1 for item in items if item.get("blockers")),
            "apply_policy_candidate_count": sum(
                1 for item in items if item.get("policy_action") == "candidate_for_final_policy_after_decision_acceptance"
            ),
        },
        "items": items,
        "notes": [
            "This is conflict classification only, not canonical apply.",
            "time_raw conflicts are expected for the recommended time-normalization lane.",
            "Punctuation-only summary/description variants can be represented by retaining the chosen representative text and preserving source variants in provenance/conflict metadata.",
        ],
    }


def validate_policy_body_preview(payload: dict[str, Any]) -> None:
    errors: list[str] = []
    if payload.get("preview_policy") != EXPECTED_PREVIEW_POLICY:
        errors.append(f"preview_policy must be {EXPECTED_PREVIEW_POLICY}")
    if payload.get("policy") != EXPECTED_POLICY:
        errors.append(f"policy must be {EXPECTED_POLICY}")
    for flag in ("canonical_outputs_mutated", "preview_outputs_written", "decisions_created", "auto_merge_performed"):
        if payload.get(flag) is not False:
            errors.append(f"{flag} must be false")
    if payload.get("ready_for_canonical_apply") is not False:
        errors.append("ready_for_canonical_apply must be false")
    if errors:
        raise ValueError("policy body preview is not safe for conflict classification: " + "; ".join(errors))


def classify_preview(preview: dict[str, Any]) -> dict[str, Any]:
    conflicts = preview.get("entity_resolution_canonical_merge_conflicts")
    conflicts = conflicts if isinstance(conflicts, dict) else {}
    conflict_fields = sorted(str(field) for field in conflicts)
    blockers = conflict_blockers(conflicts)
    if blockers:
        classification = "blocking_policy_conflict"
        risk_tier = "high"
        policy_action = "requires_manual_policy_review"
    elif conflict_fields == ["time_raw"]:
        classification = "time_raw_only"
        risk_tier = "low"
        policy_action = "candidate_for_final_policy_after_decision_acceptance"
    elif set(conflict_fields).issubset({"description", "summary", "time_raw"}) and text_conflicts_are_punctuation_only(conflicts):
        classification = "time_raw_with_punctuation_only_text_variants"
        risk_tier = "low"
        policy_action = "candidate_for_final_policy_after_decision_acceptance"
    elif set(conflict_fields).issubset({"description", "summary", "time_raw"}) and text_conflicts_are_minor_typos(conflicts):
        classification = "time_raw_with_minor_text_typo_variants"
        risk_tier = "low"
        policy_action = "candidate_for_final_policy_after_decision_acceptance"
    else:
        classification = "unclassified_policy_conflict"
        risk_tier = "high"
        policy_action = "requires_manual_policy_review"
        blockers = blockers + ["unclassified_conflict_fields"]
    return {
        "review_item_id": clean_text(preview.get("review_item_id")),
        "effect_id": clean_text(preview.get("effect_id")),
        "classification": classification,
        "risk_tier": risk_tier,
        "policy_action": policy_action,
        "conflict_fields": conflict_fields,
        "source_event_count": as_int(preview.get("source_event_count")),
        "canonical_input_id_count": as_int(preview.get("canonical_input_id_count")),
        "blockers": blockers,
        "representative_event_id": clean_text(preview.get("representative_event_id")),
        "canonical_event_id": clean_text(preview.get("canonical_event_id")),
    }


def conflict_blockers(conflicts: dict[str, Any]) -> list[str]:
    allowed_fields = {"description", "summary", "time_raw"}
    blockers: list[str] = []
    extra_fields = sorted(field for field in conflicts if str(field) not in allowed_fields)
    if extra_fields:
        blockers.append("unexpected_conflict_fields:" + ",".join(str(field) for field in extra_fields))
    if "time_raw" not in conflicts:
        blockers.append("missing_expected_time_raw_conflict")
    if (
        any(field in conflicts for field in ("description", "summary"))
        and not text_conflicts_are_punctuation_only(conflicts)
        and not text_conflicts_are_minor_typos(conflicts)
    ):
        blockers.append("non_punctuation_text_conflict")
    return blockers


def text_conflicts_are_punctuation_only(conflicts: dict[str, Any]) -> bool:
    text_fields = [field for field in ("description", "summary") if field in conflicts]
    if not text_fields:
        return True
    for field in text_fields:
        values = conflict_values(conflicts.get(field))
        normalized = {normalize_text_variant(value) for value in values if clean_text(value)}
        if len(normalized) > 1:
            return False
    return True


def text_conflicts_are_minor_typos(conflicts: dict[str, Any]) -> bool:
    text_fields = [field for field in ("description", "summary") if field in conflicts]
    if not text_fields:
        return True
    for field in text_fields:
        values = [normalize_text_variant(value) for value in conflict_values(conflicts.get(field)) if clean_text(value)]
        unique_values = sorted(set(values))
        if len(unique_values) <= 1:
            continue
        shortest = min(len(value) for value in unique_values)
        if shortest < 20:
            return False
        anchor = unique_values[0]
        if any(levenshtein_distance(anchor, value, max_distance=2) > 2 for value in unique_values[1:]):
            return False
    return True


def levenshtein_distance(left: str, right: str, *, max_distance: int) -> int:
    if abs(len(left) - len(right)) > max_distance:
        return max_distance + 1
    previous = list(range(len(right) + 1))
    for index_left, char_left in enumerate(left, start=1):
        current = [index_left]
        row_min = current[0]
        for index_right, char_right in enumerate(right, start=1):
            insert_cost = current[index_right - 1] + 1
            delete_cost = previous[index_right] + 1
            replace_cost = previous[index_right - 1] + (char_left != char_right)
            value = min(insert_cost, delete_cost, replace_cost)
            current.append(value)
            row_min = min(row_min, value)
        if row_min > max_distance:
            return max_distance + 1
        previous = current
    return previous[-1]


def conflict_values(conflict: Any) -> list[str]:
    if not isinstance(conflict, dict):
        return []
    values = conflict.get("values")
    if not isinstance(values, list):
        return []
    return [text for value in values if (text := clean_text(value))]


def normalize_text_variant(value: Any) -> str:
    text = clean_text(value).lower()
    text = re.sub(r"[\W_]+", "", text, flags=re.UNICODE)
    return text


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_csv(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for item in report.get("items") or []:
            if isinstance(item, dict):
                writer.writerow(
                    {
                        "review_item_id": item.get("review_item_id"),
                        "effect_id": item.get("effect_id"),
                        "classification": item.get("classification"),
                        "risk_tier": item.get("risk_tier"),
                        "policy_action": item.get("policy_action"),
                        "conflict_fields": "; ".join(string_list(item.get("conflict_fields"))),
                        "source_event_count": item.get("source_event_count"),
                        "canonical_input_id_count": item.get("canonical_input_id_count"),
                        "blockers": "; ".join(string_list(item.get("blockers"))),
                    }
                )


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    lines = [
        "# Recommended Time-Normalization Policy Conflict Classification",
        "",
        "This report is classification-only and does not mutate canonical outputs.",
        "",
        "## Summary",
        "",
        f"- Policy-body previews: `{summary.get('policy_body_preview_count', 0)}`",
        f"- Classification counts: `{json.dumps(summary.get('classification_counts') or {}, sort_keys=True)}`",
        f"- Risk tiers: `{json.dumps(summary.get('risk_tier_counts') or {}, sort_keys=True)}`",
        f"- Blocking previews: `{summary.get('blocking_preview_count', 0)}`",
        f"- Apply-policy candidates after decision acceptance: `{summary.get('apply_policy_candidate_count', 0)}`",
        f"- Canonical outputs mutated: `{str(report.get('canonical_outputs_mutated')).lower()}`",
        "",
        "## Items",
        "",
    ]
    for item in report.get("items") or []:
        if not isinstance(item, dict):
            continue
        lines.extend(
            [
                f"- `{item.get('review_item_id')}` `{item.get('classification')}`",
                f"  - Conflicts: {', '.join(string_list(item.get('conflict_fields'))) or 'none'}",
                f"  - Policy action: `{item.get('policy_action')}` blockers: {', '.join(string_list(item.get('blockers'))) or 'none'}",
            ]
        )
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = clean_text(row.get(key)) or "unknown"
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def count_blockers(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        for blocker in string_list(row.get("blockers")):
            counts[blocker] = counts.get(blocker, 0) + 1
    return dict(sorted(counts.items()))


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [text for item in value if (text := clean_text(item))]
    text = clean_text(value)
    return [text] if text else []


def as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy-body-preview", type=Path, default=DEFAULT_POLICY_BODY_PREVIEW)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_OUTPUT_CSV)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_OUTPUT_MARKDOWN)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = classify_time_norm_recommended_policy_body_conflicts(read_json(args.policy_body_preview))
    report["inputs"] = {"policy_body_preview": str(args.policy_body_preview)}
    report["outputs"] = {
        "json": str(args.json_output),
        "csv": str(args.csv_output),
        "markdown": str(args.markdown_output),
    }
    write_json(args.json_output, report)
    write_csv(args.csv_output, report)
    write_markdown(args.markdown_output, report)
    print(
        json.dumps(
            {
                "json_output": str(args.json_output),
                "csv_output": str(args.csv_output),
                "markdown_output": str(args.markdown_output),
                "classification_policy": report["classification_policy"],
                "summary": report["summary"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

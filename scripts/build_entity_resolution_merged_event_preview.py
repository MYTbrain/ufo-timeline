"""Build compact merged-event body previews for ER merge patches.

This streams deduped_events.jsonl only to hydrate event rows referenced by a
compact ER merge patch. It does not write a shadow corpus and does not mutate
canonical outputs.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

from parser.canonical_schema import clean_text
from scripts.preview_entity_resolution_apply import merge_event_rows


DEFAULT_PATCH = Path("data/reports/entity_resolution_ai_merge_preview_patch.json")
DEFAULT_DEDUPED_EVENTS = Path("data/canonical_full/deduped_events.jsonl")
DEFAULT_OUTPUT = Path("data/reports/entity_resolution_ai_merged_event_preview.json")

CONFLICT_FIELDS = (
    "date_iso",
    "time_raw",
    "location_raw",
    "lat",
    "lon",
    "coordinate_source",
    "shape_normalized",
    "type_normalized",
    "summary",
    "description",
)

SUMMARY_FIELDS = (
    "canonical_event_id",
    "canonical_input_ids",
    "source_name",
    "source_file",
    "source_native_id",
    "date_iso",
    "time_raw",
    "location_raw",
    "lat",
    "lon",
    "shape_normalized",
    "type_normalized",
    "summary",
)


def build_entity_resolution_merged_event_preview(
    *,
    merge_patch: dict[str, Any],
    deduped_events_path: Path,
    merge_patch_path: Path | None = None,
) -> dict[str, Any]:
    validate_merge_patch(merge_patch)
    patches = merge_patch.get("patches") if isinstance(merge_patch.get("patches"), list) else []
    required_event_ids = {
        event_id
        for patch in patches
        if isinstance(patch, dict)
        for event_id in normalized_id_list(patch.get("merge_canonical_event_ids"))
    }
    event_rows, scanned_event_count = collect_event_rows(deduped_events_path, required_event_ids)

    previews = []
    missing_patch_count = 0
    for patch in patches:
        if not isinstance(patch, dict):
            continue
        event_ids = normalized_id_list(patch.get("merge_canonical_event_ids"))
        rows = [event_rows[event_id] for event_id in event_ids if event_id in event_rows]
        missing_event_ids = [event_id for event_id in event_ids if event_id not in event_rows]
        if missing_event_ids:
            missing_patch_count += 1
        effects = [{"effect_id": patch.get("effect_id")}]
        preview_event = merge_event_rows(rows, effects=effects) if rows and not missing_event_ids else None
        representative_row = select_representative_row(rows) if rows else None
        previews.append(
            {
                "patch_id": patch.get("patch_id"),
                "effect_id": patch.get("effect_id"),
                "review_item_id": patch.get("review_item_id"),
                "source_event_count": len(rows),
                "missing_event_ids": missing_event_ids,
                "projected_event_reduction": patch.get("projected_event_reduction"),
                "preview_event": compact_event_body(preview_event, representative_row=representative_row) if preview_event else None,
                "source_event_summaries": [compact_source_event(row) for row in rows],
                "field_conflicts": summarize_field_conflicts(rows),
            }
        )

    return {
        "schema_version": 1,
        "preview_policy": "entity_resolution_compact_merged_event_preview_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "auto_merge_performed": False,
        "inputs": {
            "merge_patch": str(merge_patch_path) if merge_patch_path else None,
            "deduped_events": str(deduped_events_path),
        },
        "merge_patch_count": len(patches),
        "required_event_id_count": len(required_event_ids),
        "hydrated_event_count": len(event_rows),
        "missing_event_id_count": len(required_event_ids - set(event_rows)),
        "patches_with_missing_events": missing_patch_count,
        "scanned_event_count": scanned_event_count,
        "merged_event_preview_count": len(previews),
        "previews": previews,
        "notes": [
            "This is a compact body preview, not a shadow deduped_events corpus.",
            "preview_event is a compact summary, not a full canonical event body.",
            "field_conflicts highlights source event values that still need policy review before canonical apply.",
        ],
    }


def validate_merge_patch(merge_patch: dict[str, Any]) -> None:
    errors: list[str] = []
    if merge_patch.get("patch_policy") != "entity_resolution_merge_patch_preview_only":
        errors.append("patch_policy must be 'entity_resolution_merge_patch_preview_only'")
    for flag in ("canonical_outputs_mutated", "preview_outputs_written", "auto_merge_performed"):
        if merge_patch.get(flag) is not False:
            errors.append(f"{flag} must be false")
    if errors:
        raise ValueError(f"merge patch is not safe to preview: {'; '.join(errors)}")


def collect_event_rows(deduped_events_path: Path, required_event_ids: set[str]) -> tuple[dict[str, dict[str, Any]], int]:
    event_rows: dict[str, dict[str, Any]] = {}
    scanned_event_count = 0
    if not required_event_ids:
        return event_rows, scanned_event_count
    for row in iter_jsonl(deduped_events_path):
        scanned_event_count += 1
        event_id = clean_text(row.get("canonical_event_id")) or clean_text(row.get("event_id"))
        if event_id in required_event_ids:
            event_rows[event_id] = row
            if len(event_rows) == len(required_event_ids):
                break
    return event_rows, scanned_event_count


def compact_event_body(event: dict[str, Any] | None, *, representative_row: dict[str, Any] | None) -> dict[str, Any] | None:
    if event is None:
        return None
    representative_row = representative_row or event
    return {
        "body_policy": "compact_preview_summary_not_canonical_event_body",
        "canonical_event_id": event.get("canonical_event_id"),
        "representative_event_id": representative_row.get("canonical_event_id"),
        "representative_selection": "highest_quality_preview_source_row",
        "canonical_input_id": event.get("canonical_input_id"),
        "canonical_input_ids": normalized_id_list(event.get("canonical_input_ids")),
        "duplicate_record_count": event.get("duplicate_record_count"),
        "dedupe_strategy": event.get("dedupe_strategy"),
        "representative_fields": {
            "date_iso": representative_row.get("date_iso"),
            "time_raw": representative_row.get("time_raw"),
            "location_raw": representative_row.get("location_raw"),
            "lat": representative_row.get("lat"),
            "lon": representative_row.get("lon"),
            "shape_normalized": representative_row.get("shape_normalized"),
            "type_normalized": representative_row.get("type_normalized"),
            "summary": representative_row.get("summary"),
            "description_snippet": snippet(representative_row.get("description")),
        },
        "source_provenance_summary": summarize_source_provenance(
            event.get("source_provenance") if isinstance(event.get("source_provenance"), list) else []
        ),
        "entity_resolution_preview_merged_event_ids": event.get("entity_resolution_preview_merged_event_ids") or [],
        "entity_resolution_preview_effect_ids": event.get("entity_resolution_preview_effect_ids") or [],
    }


def compact_source_event(event: dict[str, Any]) -> dict[str, Any]:
    summary = {field: event.get(field) for field in SUMMARY_FIELDS if field in event and field != "summary"}
    summary["summary"] = snippet(event.get("summary"), limit=220)
    summary["description_snippet"] = snippet(event.get("description"), limit=220)
    return summary


def select_representative_row(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return max(rows, key=lambda row: (row_quality_score(row), str(row.get("canonical_event_id") or "")))


def row_quality_score(row: dict[str, Any]) -> tuple[int, int, int, int, int]:
    has_coordinates = int(row.get("lat") is not None and row.get("lon") is not None)
    has_exact_day = int(bool(row.get("date_iso")) and row.get("date_precision") in {None, "day"})
    has_time = int(bool(clean_text(row.get("time_raw"))))
    description_len = len(str(row.get("description") or ""))
    provenance_count = len(row.get("source_provenance")) if isinstance(row.get("source_provenance"), list) else 0
    return (has_coordinates, has_exact_day, has_time, description_len, provenance_count)


def summarize_source_provenance(provenance: list[dict[str, Any]]) -> dict[str, Any]:
    by_source_file: dict[str, int] = {}
    samples = []
    for item in provenance:
        if not isinstance(item, dict):
            continue
        source_key = " / ".join(
            part for part in [clean_text(item.get("source_name")), clean_text(item.get("source_file"))] if part
        ) or "unknown"
        by_source_file[source_key] = by_source_file.get(source_key, 0) + 1
        if len(samples) < 12:
            samples.append(
                {
                    "source_name": item.get("source_name"),
                    "source_file": item.get("source_file"),
                    "source_row_number": item.get("source_row_number"),
                    "source_native_id": item.get("source_native_id"),
                    "canonical_input_id": item.get("canonical_input_id"),
                }
            )
    return {
        "source_record_count": len(provenance),
        "by_source_file": dict(sorted(by_source_file.items())),
        "samples": samples,
        "sample_truncated": len(provenance) > len(samples),
    }


def snippet(value: Any, *, limit: int = 320) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def summarize_field_conflicts(rows: list[dict[str, Any]]) -> dict[str, list[Any]]:
    conflicts: dict[str, list[Any]] = {}
    for field in CONFLICT_FIELDS:
        values = []
        seen = set()
        for row in rows:
            value = row.get(field)
            key = json.dumps(value, ensure_ascii=False, sort_keys=True)
            if value not in (None, "") and key not in seen:
                values.append(value)
                seen.add(key)
        if len(values) > 1:
            conflicts[field] = values
    return conflicts


def normalized_id_list(value: Any) -> list[str]:
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if not isinstance(value, list):
        return []
    ids = []
    for item in value:
        text = str(item or "").strip()
        if text:
            ids.append(text)
    return ids


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(f"{path} line {line_number} must be a JSON object.")
            yield payload


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--merge-patch", type=Path, default=DEFAULT_PATCH)
    parser.add_argument("--deduped-events", type=Path, default=DEFAULT_DEDUPED_EVENTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    merge_patch = read_json(args.merge_patch)
    report = build_entity_resolution_merged_event_preview(
        merge_patch=merge_patch,
        merge_patch_path=args.merge_patch,
        deduped_events_path=args.deduped_events,
    )
    write_json(args.output, report)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "preview_policy": report["preview_policy"],
                "merged_event_preview_count": report["merged_event_preview_count"],
                "missing_event_id_count": report["missing_event_id_count"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0 if report["missing_event_id_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

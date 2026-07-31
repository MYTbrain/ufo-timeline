"""Build a compact preview patch for planned ER merge effects.

The patch is an inspectable plan artifact. It does not rewrite the deduped
event corpus and it does not choose final merged event contents.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_EFFECTS_PLAN = Path("data/reports/entity_resolution_ai_effects_plan.json")
DEFAULT_OUTPUT = Path("data/reports/entity_resolution_ai_merge_preview_patch.json")


def build_entity_resolution_merge_preview_patch(
    *,
    effects_plan: dict[str, Any],
    effects_plan_path: Path | None = None,
) -> dict[str, Any]:
    validate_effects_plan(effects_plan)
    effects = effects_plan.get("effects") if isinstance(effects_plan.get("effects"), list) else []
    patches = []
    skipped = []
    projected_event_reduction = 0

    for index, effect in enumerate(effects, start=1):
        if not isinstance(effect, dict) or effect.get("planned_effect") != "merge_entity_resolution_candidate":
            continue
        event_ids = sorted(set(normalized_id_list(effect.get("merge_canonical_event_ids"))))
        if len(event_ids) <= 1:
            skipped.append(
                {
                    "effect_index": index,
                    "effect_id": effect.get("effect_id"),
                    "review_item_id": effect.get("review_item_id"),
                    "reason": "insufficient_merge_event_ids",
                    "merge_canonical_event_ids": event_ids,
                }
            )
            continue
        replacement_event_id = event_ids[0]
        suppressed_event_ids = event_ids[1:]
        projected_event_reduction += len(suppressed_event_ids)
        patches.append(
            {
                "patch_id": f"er_merge_patch_{len(patches) + 1:06d}",
                "effect_id": effect.get("effect_id"),
                "review_item_id": effect.get("review_item_id"),
                "review_band": effect.get("review_band"),
                "score": effect.get("score"),
                "replacement_canonical_event_id": replacement_event_id,
                "suppressed_canonical_event_ids": suppressed_event_ids,
                "merge_canonical_event_ids": event_ids,
                "canonical_input_ids": normalized_id_list(effect.get("canonical_input_ids")),
                "projected_event_reduction": len(suppressed_event_ids),
                "requires_explicit_apply_step": bool(effect.get("requires_explicit_apply_step")),
                "replacement_selection": "first_sorted_current_event_id_preview_only",
            }
        )

    return {
        "schema_version": 1,
        "patch_policy": "entity_resolution_merge_patch_preview_only",
        "canonical_outputs_mutated": False,
        "preview_outputs_written": False,
        "decisions_created": False,
        "auto_merge_performed": False,
        "inputs": {
            "effects_plan": str(effects_plan_path) if effects_plan_path else None,
        },
        "merge_patch_count": len(patches),
        "skipped_merge_effect_count": len(skipped),
        "projected_event_reduction": projected_event_reduction,
        "patches": patches,
        "skipped_merge_effects": skipped,
        "notes": [
            "This patch is compact metadata only; it does not contain merged event bodies.",
            "A future apply step must decide final merged event content and provenance reconciliation.",
            "No canonical event outputs are mutated by this patch builder.",
        ],
    }


def validate_effects_plan(effects_plan: dict[str, Any]) -> None:
    errors: list[str] = []
    if effects_plan.get("effect_policy") != "entity_resolution_plan_only":
        errors.append("effect_policy must be 'entity_resolution_plan_only'")
    for flag in ("canonical_outputs_mutated", "preview_outputs_written", "auto_merge_performed"):
        if effects_plan.get(flag) is not False:
            errors.append(f"{flag} must be false")
    if errors:
        raise ValueError(f"effects plan is not safe for preview patching: {'; '.join(errors)}")


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
    parser.add_argument("--effects-plan", type=Path, default=DEFAULT_EFFECTS_PLAN)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    effects_plan = read_json(args.effects_plan)
    patch = build_entity_resolution_merge_preview_patch(effects_plan=effects_plan, effects_plan_path=args.effects_plan)
    write_json(args.output, patch)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "patch_policy": patch["patch_policy"],
                "merge_patch_count": patch["merge_patch_count"],
                "projected_event_reduction": patch["projected_event_reduction"],
                "canonical_outputs_mutated": False,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

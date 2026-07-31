# Manual Review Apply Step Design

This document defines the safe path from reviewed manual decisions to future canonical-output changes.

Current state:

- `scripts/build_canonical_ufo_dataset.py --manual-review-decisions` records accepted decisions only.
- `scripts/plan_manual_review_effects.py` converts accepted decisions into `manual_review_effects_plan.json`.
- No canonical event, normalized event, map event, or web runtime artifact is mutated by either step.

## Guardrails

- Do not auto-merge fuzzy duplicate candidates.
- Do not overwrite `deduped_events.jsonl`, `normalized_events.json`, `map_events.json`, or canonical web artifacts in the first apply implementation.
- Do not repair source data implicitly from a review decision.
- Treat `repair_source_row`, `fix_adapter`, `fix_source_file`, and `map_columns` as backlog/workflow actions, not automatic data rewrites.
- Preserve all source provenance for any preview merge.
- Keep source-row exclusion explicit and reversible through reviewed decision artifacts.

## Proposed Apply Phases

### Phase A: Preview-Only Shadow Outputs

The first preview command is implemented as:

```powershell
python scripts\apply_manual_review_effects.py --effects-plan data\reports\manual_review_effects_plan.json --mode preview
```

Preview mode should write only new shadow outputs, for example:

```text
data/canonical_preview_manual_review/deduped_events.jsonl
data/canonical_preview_manual_review/duplicate_groups.jsonl
data/canonical_preview_manual_review/normalized_events.json
data/canonical_preview_manual_review/map_events.json
data/reports/manual_review_apply_preview_report.json
```

It must not overwrite the canonical build outputs.

### Phase B: Reviewed Promotion

Only after preview QA, add an explicit promotion mode. Promotion must require an explicit flag such as:

```powershell
python scripts\apply_manual_review_effects.py --effects-plan data\reports\manual_review_effects_plan.json --mode promote --i-understand-this-mutates-canonical-outputs
```

Promotion should remain optional and should be blocked if validation errors exist.

## Effect Semantics

`merge_duplicate_candidate`:

- Merge only the `canonical_input_ids` listed in the reviewed effect.
- Preserve all source provenance from merged records.
- Use `replacement_canonical_event_id` only if it resolves to a member of the merge set or a valid existing canonical event target.
- If records conflict strongly on exact date or mapped location, block the effect and report a validation error.

`preserve_distinct_events`:

- Do not merge the candidate records.
- Optionally suppress or mark the candidate as reviewed in future QA reports.

`exclude_source_row`:

- Remove the specified `canonical_input_ids` from preview outputs only.
- Keep an exclusion report with source file, row number, and reviewer metadata.
- If the row is the only provenance for an event, remove that event from preview outputs.

`repair_source_row_upstream`, `fix_source_adapter`, `fix_source_file_upstream`, `update_source_column_mapping`:

- Do not mutate canonical outputs directly.
- Emit backlog/report entries requiring source or adapter changes followed by a normal rebuild.

`defer_duplicate_candidate` and unmapped effects:

- Do not change preview outputs.
- Preserve as unresolved review state.

## Validation Gates

The apply command should fail closed when:

- An effect references a missing `review_item_id`.
- A merge effect references missing `canonical_input_ids`.
- A source-row exclusion references missing `canonical_input_ids`.
- The same `canonical_input_id` is both excluded and merged.
- Two merge effects request conflicting merge groups.
- `replacement_canonical_event_id` does not resolve safely.
- Any effect lacks `effect_policy: plan_only` or `effect_status: planned_not_applied`.

The preview report should include:

- Effects requested, applied, skipped, and blocked.
- Counts by effect type and review type.
- Canonical event count before/after preview.
- Source-row count before/after preview.
- A list of blocked effects with reasons.
- `canonical_outputs_mutated: false` in preview mode.

## Test Requirements

Minimum tests before preview mode is implemented:

- Same-event duplicate preview merges records while preserving source provenance.
- Distinct-event decision does not merge records.
- Source-row exclusion removes only the reviewed row.
- Excluding the only row for an event removes that event from preview outputs.
- Conflicting merge/exclude effects are blocked.
- Missing IDs are blocked.
- Promotion cannot run without an explicit mutation acknowledgement flag.
- Preview mode never rewrites canonical outputs.

## Open Decisions

- Whether future promoted canonical outputs should live in `data/canonical` directly or in a versioned release directory first.
- Whether reviewed distinct decisions should suppress duplicate-candidate re-emission on future builds.
- Whether source-row exclusions should become a durable input file consumed by the canonical build, rather than a post-build apply step.

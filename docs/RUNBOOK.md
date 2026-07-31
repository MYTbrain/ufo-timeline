# UFO Timeline Scale Migration Runbook

## Current Workspace

```text
C:\Users\jarod\Desktop\UFO Timeline map tool
```

For the current blocked-readiness stop point, see:

```text
docs/PHASE_3_BLOCKED_READINESS_HANDOFF.md
```

## Baseline Verification

Use bundled runtimes when available:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' --check webapp\static_public\app.js
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' tests\test_frontend_utils.mjs
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' tests\test_packed_points_frontend.mjs
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' tests\test_packed_traces_frontend.mjs
```

## Rebuild Static Bundle

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\rebuild_static_bundle_from_existing_data.py --config config.example.yaml
if (Test-Path -LiteralPath 'static_bundle.zip') { Remove-Item -LiteralPath 'static_bundle.zip' -Force }
Compress-Archive -Path 'static_bundle\*' -DestinationPath 'static_bundle.zip' -Force
```

## Run Source Audit

```powershell
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\audit_ufo_csv_sources.py
```

Outputs:

```text
data/reports/ufo_csv_audit.json
data/canonical/source_field_inventories/*.json
data/canonical/source_column_mapping.json
data/canonical/unmapped_fields_report.json
data/canonical/unmapped_fields_report.csv
```

## Build Canonical CSV Dataset

Use this for smoke builds while validating adapter/provenance behavior:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\build_canonical_ufo_dataset.py --limit-per-source 25 --output-dir data\canonical_smoke --reports-dir data\reports\canonical_smoke
```

Default canonical build inputs:

```text
data/reports/ufo_csv_audit.json
data/canonical/source_column_mapping.json
```

Important outputs:

```text
data/canonical/source_records.jsonl
data/canonical/source_claims.jsonl
data/canonical/deduped_events.jsonl
data/canonical/duplicate_candidates.jsonl
data/canonical/manual_review_queue.jsonl
data/canonical/manual_review_applied_decisions.jsonl
data/canonical/manual_review_decision_schema.json
data/reports/canonical_import_report.json
data/reports/canonical_column_accounting.json
data/reports/canonical_import_failures.json
data/reports/manual_review_decisions_report.json
data/reports/dedupe_report.json
```

`canonical_input_events.jsonl` is a legacy duplicate of `source_records.jsonl`. It is skipped by default to avoid multi-GB duplication. Use `--write-legacy-canonical-input-events` only if an older downstream tool explicitly requires that filename.

Export the current manual review queue into human-triage artifacts without creating decisions or mutating canonical outputs:

```powershell
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\build_manual_review_packet.py --queue data\canonical_full\manual_review_queue.jsonl --json-output data\reports\manual_review_packet.json --csv-output data\reports\manual_review_packet.csv --markdown-output data\reports\manual_review_packet.md
```

The packet is review-only. It preserves review IDs, candidate/input IDs, suggested decision options, source rows, date/location keys, and evidence summaries. It does not create decisions, perform auto-merges, write effects plans, or change any canonical/runtime output.

Validate the packet before using it for human triage:

```powershell
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\check_manual_review_packet.py --queue data\canonical_full\manual_review_queue.jsonl --packet data\reports\manual_review_packet.json --csv data\reports\manual_review_packet.csv --markdown data\reports\manual_review_packet.md --output data\reports\manual_review_packet_readiness.json
```

Expected current status is `ready`. This is still report-only; it does not ingest decisions or mutate canonical data.

Generate conservative AI-assisted review decisions from the full queue:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\ai_review_manual_review_queue.py --queue data\canonical_full\manual_review_queue.jsonl --decisions-output data\canonical_full\manual_review_decisions_ai_assisted.jsonl --applied-output data\canonical_full\manual_review_applied_decisions_ai_assisted.jsonl --report-output data\reports\manual_review_ai_decisions_report.json
```

Plan effects from those AI-assisted decisions without mutating canonical outputs:

```powershell
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\plan_manual_review_effects.py --queue data\canonical_full\manual_review_queue.jsonl --applied-decisions data\canonical_full\manual_review_applied_decisions_ai_assisted.jsonl --output data\reports\manual_review_ai_effects_plan.json
```

Summarize full-corpus impact without loading or rewriting the 5.9GB deduped event corpus:

```powershell
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\summarize_manual_review_effect_impact.py --effects-plan data\reports\manual_review_ai_effects_plan.json --deduped-events data\canonical_full\deduped_events.jsonl --output data\reports\manual_review_ai_effect_impact_summary.json
```

Do not run the legacy full preview apply on `data/canonical_full/deduped_events.jsonl`. `scripts/apply_manual_review_effects.py` deep-copies the entire event corpus and is suitable for small/smoke outputs, not the full 5.9GB corpus.

For full-corpus sidecar application, use the stream-safe component writer:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\apply_manual_review_effects_stream.py --effects-plan data\reports\manual_review_ai_effects_plan.json --deduped-events data\canonical_full\deduped_events.jsonl --output-events data\canonical_manual_review_ai_preview\deduped_events.jsonl --report-output data\reports\manual_review_ai_stream_apply_report.json --overwrite-output
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\check_manual_review_stream_apply_output.py --apply-report data\reports\manual_review_ai_stream_apply_report.json --apply-events data\canonical_manual_review_ai_preview\deduped_events.jsonl --output data\reports\manual_review_ai_stream_apply_output_check.json
```

Current manual-review sidecar result: 944,578 input rows, 940,548 output rows, 2,546 connected merge components, 4,030 actual event reduction, valid output check, 0 suppressed IDs still present, and `data/canonical_full/deduped_events.jsonl` unchanged. The earlier 4,984 number is a pairwise projection; the stream writer collapses overlapping duplicate edges into components, so the lower actual reduction is the correct sidecar count.

To compose the accepted time-normalization lanes with the AI-assisted manual-review lane:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\apply_manual_review_effects_stream.py --effects-plan data\reports\manual_review_ai_effects_plan.json --deduped-events data\canonical_time_norm_recommended_plus_shorthand_plus_likely_plus_single_exact_context\deduped_events.jsonl --output-events data\canonical_time_norm_plus_manual_review_ai_preview\deduped_events.jsonl --report-output data\reports\manual_review_ai_after_time_norm_stream_apply_report.json --overwrite-output
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\check_manual_review_stream_apply_output.py --apply-report data\reports\manual_review_ai_after_time_norm_stream_apply_report.json --apply-events data\canonical_time_norm_plus_manual_review_ai_preview\deduped_events.jsonl --output data\reports\manual_review_ai_after_time_norm_stream_apply_output_check.json
```

Current composed sidecar result: 944,464 input rows, 940,477 output rows, 2,512 connected merge components, 3,987 manual-review reduction on top of the time-normalized corpus, 4,101 net reduction from the original 944,578-row canonical full corpus, valid output check, and 0 suppressed IDs still present. Treat this as preview/staging only until replacement-row audit risks are adjudicated and UI parity smoke is complete.

To audit the composed replacement rows for hidden date/time/location/classification/body conflicts:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\audit_manual_review_stream_replacements.py --apply-report data\reports\manual_review_ai_after_time_norm_stream_apply_report.json --source-events data\canonical_time_norm_recommended_plus_shorthand_plus_likely_plus_single_exact_context\deduped_events.jsonl --candidate-events data\canonical_time_norm_plus_manual_review_ai_preview\deduped_events.jsonl --output data\reports\manual_review_ai_after_time_norm_replacement_audit.json --csv-output data\reports\manual_review_ai_after_time_norm_replacement_audit.csv
```

Current replacement audit result: 2,512 components audited, 6,499 source component rows found, 37 high-risk components, 1,384 medium-risk components, 1,091 low-risk components, valid audit structure, and canonical outputs unchanged. The audit intentionally keeps `ready_for_runtime_promotion=false`; high and medium risks must be reviewed or filtered into stricter lanes before promotion.

To build a review-only packet for the high/medium components excluded from the low-risk lane:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\build_manual_review_replacement_audit_packet.py --audit-csv data\reports\manual_review_ai_after_time_norm_replacement_audit.csv --output-json data\reports\manual_review_ai_after_time_norm_replacement_audit_review_packet.json --output-csv data\reports\manual_review_ai_after_time_norm_replacement_audit_review_packet.csv --output-md data\reports\manual_review_ai_after_time_norm_replacement_audit_review_packet.md --markdown-limit 100
```

Current high/medium review packet result: 1,421 review rows, including 37 high-risk and 1,384 medium-risk components. This packet is review-only and does not apply any excluded component.

To summarize the audit backlog into bounded sublanes:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\summarize_manual_review_replacement_audit_sublanes.py --audit-csv data\reports\manual_review_ai_after_time_norm_replacement_audit.csv --output-json data\reports\manual_review_ai_after_time_norm_replacement_audit_sublanes.json --output-csv data\reports\manual_review_ai_after_time_norm_replacement_audit_sublanes.csv
```

Current sublane summary: 11 lanes. The accepted low-risk preview lane is 1,091 components / 1,696 projected reduction. The largest remaining bounded lane is `medium_time_raw_only` with 818 components / 1,369 projected reduction, followed by `medium_time_or_identity_only` with 196 components / 327 projected reduction. Treat these as targeting guidance only; each medium lane needs its own stricter parser-backed acceptance gate before apply.

To review the `medium_time_raw_only` lane with the existing time parser:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\review_manual_review_medium_time_raw_only.py --audit-csv data\reports\manual_review_ai_after_time_norm_replacement_audit.csv --output-json data\reports\manual_review_ai_after_time_norm_medium_time_raw_only_review.json --output-csv data\reports\manual_review_ai_after_time_norm_medium_time_raw_only_review.csv --output-md data\reports\manual_review_ai_after_time_norm_medium_time_raw_only_review.md --max-exact-span-minutes 15 --markdown-limit 100
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\promote_manual_review_medium_time_raw_only_review_to_decision_candidates.py --review data\reports\manual_review_ai_after_time_norm_medium_time_raw_only_review.json --candidate-events data\canonical_time_norm_plus_manual_review_ai_preview\deduped_events.jsonl --decisions-output data\reports\manual_review_ai_after_time_norm_medium_time_raw_only_decision_candidates.jsonl --report-output data\reports\manual_review_ai_after_time_norm_medium_time_raw_only_decision_candidates_report.json
```

Current medium-time-only review result: 818 items reviewed, 178 parser-backed same-event candidates, 640 still need more evidence, and 238 projected event reduction from the candidates. These candidates are not applied by the review/promotion commands.

To compose those candidates with the low-risk lane and build a sidecar:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\combine_manual_review_effect_lanes.py --original-effects-plan data\reports\manual_review_ai_effects_plan.json --base-effects-plan data\reports\manual_review_ai_after_time_norm_low_risk_effects_plan.json --decision-candidates data\reports\manual_review_ai_after_time_norm_medium_time_raw_only_decision_candidates.jsonl --output-plan data\reports\manual_review_ai_after_time_norm_low_risk_plus_medium_time_effects_plan.json --output-report data\reports\manual_review_ai_after_time_norm_low_risk_plus_medium_time_effects_plan_report.json
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\apply_manual_review_effects_stream.py --effects-plan data\reports\manual_review_ai_after_time_norm_low_risk_plus_medium_time_effects_plan.json --deduped-events data\canonical_time_norm_recommended_plus_shorthand_plus_likely_plus_single_exact_context\deduped_events.jsonl --output-events data\canonical_time_norm_plus_manual_review_ai_low_risk_plus_medium_time_preview\deduped_events.jsonl --report-output data\reports\manual_review_ai_after_time_norm_low_risk_plus_medium_time_stream_apply_report.json --overwrite-output
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\check_manual_review_stream_apply_output.py --apply-report data\reports\manual_review_ai_after_time_norm_low_risk_plus_medium_time_stream_apply_report.json --apply-events data\canonical_time_norm_plus_manual_review_ai_low_risk_plus_medium_time_preview\deduped_events.jsonl --output data\reports\manual_review_ai_after_time_norm_low_risk_plus_medium_time_stream_apply_output_check.json
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\audit_manual_review_stream_replacements.py --apply-report data\reports\manual_review_ai_after_time_norm_low_risk_plus_medium_time_stream_apply_report.json --source-events data\canonical_time_norm_recommended_plus_shorthand_plus_likely_plus_single_exact_context\deduped_events.jsonl --candidate-events data\canonical_time_norm_plus_manual_review_ai_low_risk_plus_medium_time_preview\deduped_events.jsonl --output data\reports\manual_review_ai_after_time_norm_low_risk_plus_medium_time_replacement_audit.json --csv-output data\reports\manual_review_ai_after_time_norm_low_risk_plus_medium_time_replacement_audit.csv
```

Current low-risk plus medium-time sidecar result: 2,087 selected merge effects, 942,530 output rows, 1,934 actual event reduction, valid output check, 0 suppressed IDs still present, and a replacement audit of 0 high-risk / 178 medium-risk / 1,091 low-risk components. The remaining medium components are intentionally excluded.

To build and validate compact web artifacts from that combined sidecar:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\build_canonical_web_artifacts.py --input data\canonical_time_norm_plus_manual_review_ai_low_risk_plus_medium_time_preview\deduped_events.jsonl --output-dir data\canonical_web_time_norm_plus_manual_review_ai_low_risk_plus_medium_time_preview_smoke --limit 10000 --write-gzip
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\check_canonical_web_runtime_readiness.py --artifact-dir data\canonical_web_time_norm_plus_manual_review_ai_low_risk_plus_medium_time_preview_smoke --output data\reports\canonical_web_time_norm_plus_manual_review_ai_low_risk_plus_medium_time_preview_smoke_runtime_readiness.json

& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\build_canonical_web_artifacts.py --input data\canonical_time_norm_plus_manual_review_ai_low_risk_plus_medium_time_preview\deduped_events.jsonl --output-dir data\canonical_web_time_norm_plus_manual_review_ai_low_risk_plus_medium_time_preview --write-gzip
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\check_canonical_web_runtime_readiness.py --artifact-dir data\canonical_web_time_norm_plus_manual_review_ai_low_risk_plus_medium_time_preview --output data\reports\canonical_web_time_norm_plus_manual_review_ai_low_risk_plus_medium_time_preview_runtime_readiness.json

& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\stage_canonical_web_static_payload.py --artifact-dir data\canonical_web_time_norm_plus_manual_review_ai_low_risk_plus_medium_time_preview --output-root data\canonical_web_time_norm_plus_manual_review_ai_low_risk_plus_medium_time_preview_static_primary_trace_payload --mode primary-catalog-trace-runtime
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\check_canonical_web_static_payload.py --payload-root data\canonical_web_time_norm_plus_manual_review_ai_low_risk_plus_medium_time_preview_static_primary_trace_payload --static-bundle-root static_bundle --output data\reports\canonical_web_time_norm_plus_manual_review_ai_low_risk_plus_medium_time_preview_static_payload_readiness.json
```

Current combined compact-web result: 942,530 events, 287,855 mapped events, 286,582 trace-event-index rows, 286,581 trace segments, 378 event chunks, 95 summary shards, 2,131.61 MB raw, 404.93 MB gzip, 7.03 MB startup gzip, and `ready_for_preview`. The lean static payload has 212 files, 95 summary shards, 0 event chunks, about 588.02 MB raw plus 74.56 MB gzip, status `ready`, and the default `static_bundle` config still keeps canonical web artifacts disabled.

To build the stricter low-risk manual-review effects lane from that audit:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\filter_manual_review_effects_by_replacement_audit.py --effects-plan data\reports\manual_review_ai_effects_plan.json --replacement-audit-csv data\reports\manual_review_ai_after_time_norm_replacement_audit.csv --candidate-events data\canonical_time_norm_plus_manual_review_ai_preview\deduped_events.jsonl --output-plan data\reports\manual_review_ai_after_time_norm_low_risk_effects_plan.json --output-report data\reports\manual_review_ai_after_time_norm_low_risk_effects_plan_report.json --allowed-risk-level low
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\apply_manual_review_effects_stream.py --effects-plan data\reports\manual_review_ai_after_time_norm_low_risk_effects_plan.json --deduped-events data\canonical_time_norm_recommended_plus_shorthand_plus_likely_plus_single_exact_context\deduped_events.jsonl --output-events data\canonical_time_norm_plus_manual_review_ai_low_risk_preview\deduped_events.jsonl --report-output data\reports\manual_review_ai_after_time_norm_low_risk_stream_apply_report.json --overwrite-output
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\check_manual_review_stream_apply_output.py --apply-report data\reports\manual_review_ai_after_time_norm_low_risk_stream_apply_report.json --apply-events data\canonical_time_norm_plus_manual_review_ai_low_risk_preview\deduped_events.jsonl --output data\reports\manual_review_ai_after_time_norm_low_risk_stream_apply_output_check.json
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\audit_manual_review_stream_replacements.py --apply-report data\reports\manual_review_ai_after_time_norm_low_risk_stream_apply_report.json --source-events data\canonical_time_norm_recommended_plus_shorthand_plus_likely_plus_single_exact_context\deduped_events.jsonl --candidate-events data\canonical_time_norm_plus_manual_review_ai_low_risk_preview\deduped_events.jsonl --output data\reports\manual_review_ai_after_time_norm_low_risk_replacement_audit.json --csv-output data\reports\manual_review_ai_after_time_norm_low_risk_replacement_audit.csv
```

Current low-risk sidecar result: 1,091 selected replacement components, 1,808 selected merge effects, 3,176 excluded merge effects, 0 selected/excluded effect overlaps, 0 selected/excluded component-event overlaps, 942,768 output rows, 1,696 actual event reduction, valid output check, 0 suppressed IDs still present, and a follow-up replacement audit of 0 high-risk / 0 medium-risk / 1,091 low-risk components.

To build and validate compact web artifacts from the low-risk sidecar:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\build_canonical_web_artifacts.py --input data\canonical_time_norm_plus_manual_review_ai_low_risk_preview\deduped_events.jsonl --output-dir data\canonical_web_time_norm_plus_manual_review_ai_low_risk_preview_smoke --limit 10000 --write-gzip
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\check_canonical_web_runtime_readiness.py --artifact-dir data\canonical_web_time_norm_plus_manual_review_ai_low_risk_preview_smoke --output data\reports\canonical_web_time_norm_plus_manual_review_ai_low_risk_preview_smoke_runtime_readiness.json

& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\build_canonical_web_artifacts.py --input data\canonical_time_norm_plus_manual_review_ai_low_risk_preview\deduped_events.jsonl --output-dir data\canonical_web_time_norm_plus_manual_review_ai_low_risk_preview --write-gzip
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\check_canonical_web_runtime_readiness.py --artifact-dir data\canonical_web_time_norm_plus_manual_review_ai_low_risk_preview --output data\reports\canonical_web_time_norm_plus_manual_review_ai_low_risk_preview_runtime_readiness.json

& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\stage_canonical_web_static_payload.py --artifact-dir data\canonical_web_time_norm_plus_manual_review_ai_low_risk_preview --output-root data\canonical_web_time_norm_plus_manual_review_ai_low_risk_preview_static_primary_trace_payload --mode primary-catalog-trace-runtime
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\check_canonical_web_static_payload.py --payload-root data\canonical_web_time_norm_plus_manual_review_ai_low_risk_preview_static_primary_trace_payload --static-bundle-root static_bundle --output data\reports\canonical_web_time_norm_plus_manual_review_ai_low_risk_preview_static_payload_readiness.json
```

Current low-risk compact-web result: 942,768 events, 288,092 mapped events, 286,819 trace-event-index rows, 286,818 trace segments, 378 event chunks, 95 summary shards, 2,132.05 MB raw, 404.99 MB gzip, 7.03 MB startup gzip, and `ready_for_preview`. The lean static payload has 212 files, 95 summary shards, 0 event chunks, about 588.01 MB raw plus 74.59 MB gzip, status `ready`, and the default `static_bundle` config still keeps canonical web artifacts disabled.

To build and validate compact web artifacts from the composed sidecar:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\build_canonical_web_artifacts.py --input data\canonical_time_norm_plus_manual_review_ai_preview\deduped_events.jsonl --output-dir data\canonical_web_time_norm_plus_manual_review_ai_preview_smoke --limit 10000 --write-gzip
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\check_canonical_web_runtime_readiness.py --artifact-dir data\canonical_web_time_norm_plus_manual_review_ai_preview_smoke --output data\reports\canonical_web_time_norm_plus_manual_review_ai_preview_smoke_runtime_readiness.json

& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\build_canonical_web_artifacts.py --input data\canonical_time_norm_plus_manual_review_ai_preview\deduped_events.jsonl --output-dir data\canonical_web_time_norm_plus_manual_review_ai_preview --write-gzip
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\check_canonical_web_runtime_readiness.py --artifact-dir data\canonical_web_time_norm_plus_manual_review_ai_preview --output data\reports\canonical_web_time_norm_plus_manual_review_ai_preview_runtime_readiness.json

& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\stage_canonical_web_static_payload.py --artifact-dir data\canonical_web_time_norm_plus_manual_review_ai_preview --output-root data\canonical_web_time_norm_plus_manual_review_ai_preview_static_primary_trace_payload --mode primary-catalog-trace-runtime
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\check_canonical_web_static_payload.py --payload-root data\canonical_web_time_norm_plus_manual_review_ai_preview_static_primary_trace_payload --static-bundle-root static_bundle --output data\reports\canonical_web_time_norm_plus_manual_review_ai_preview_static_payload_readiness.json
```

Current composed compact-web result: 940,477 events, 285,962 mapped events, 284,689 trace-event-index rows, 284,688 trace segments, 377 event chunks, 95 summary shards, 2,127.75 MB raw, 404.33 MB gzip, 6.98 MB startup gzip, and `ready_for_preview`. The lean static payload has 212 files, 95 summary shards, 0 event chunks, about 587.23 MB raw plus 74.32 MB gzip, status `ready`, and the default `static_bundle` config still keeps canonical web artifacts disabled.

Optional human-review decisions can be ingested as JSONL or a JSON array:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\build_canonical_ufo_dataset.py --manual-review-decisions data\canonical\manual_review_decisions.jsonl
```

Decision ingestion is currently non-destructive: accepted decisions are recorded on `manual_review_queue.jsonl`, mirrored to `manual_review_applied_decisions.jsonl`, and summarized in `manual_review_decisions_report.json`, but fuzzy duplicate decisions do not mutate `deduped_events.jsonl` or normalized web/runtime outputs.

To convert reviewed decisions into a reviewable next-step plan without mutating canonical outputs:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\plan_manual_review_effects.py --queue data\canonical\manual_review_queue.jsonl --applied-decisions data\canonical\manual_review_applied_decisions.jsonl --output data\reports\manual_review_effects_plan.json
```

The effects plan is also non-destructive. It classifies accepted decisions into planned merge, exclusion, preserve, repair, mapping, or defer actions and explicitly marks any future merge/exclusion as requiring a separate apply step.

The future mutation path is specified, but not enabled, in `docs/MANUAL_REVIEW_APPLY_DESIGN.md`.

To create preview-only shadow outputs from a reviewed effects plan:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\apply_manual_review_effects.py --effects-plan data\reports\manual_review_effects_plan.json --deduped-events data\canonical\deduped_events.jsonl --output-dir data\canonical_preview_manual_review --mode preview
```

This command writes shadow `deduped_events.jsonl`, `normalized_events.json`, `map_events.json`, and `manual_review_apply_preview_report.json` files under the preview directory. Promotion/mutation mode is intentionally not implemented.

For local canonical-web trace-runtime previews, the preview server can opt into filtered trace aggregation without changing checked-in defaults:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\serve_static_bundle_with_canonical_web.py --enable-primary-catalog --enable-trace-runtime --enable-filtered-trace-aggregation
```

`filteredTraceAggregation` remains `false` in the shipped `app_config.json`. When enabled with canonical primary catalog and trace runtime, wide static trace windows aggregate the already-filtered trace-event-index segments client-side. The full-universe `trace_aggregate_bins.bin` preview artifact is not used for filtered live rendering.

To run the guarded browser smoke without mutating checked-in defaults:

```powershell
& 'C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe' -ExecutionPolicy Bypass -File scripts\smoke_guarded_canonical_preview_cdp.ps1 -PreviewPort 8148 -DebugPort 9382 -TimeoutSeconds 900
```

This script starts the gzip-aware preview server with `primaryCatalog`, `traceRuntime`, and `filteredTraceAggregation` enabled only through the local server response, then launches headless Chrome through CDP. Chrome must be started at `about:blank` without `--user-data-dir` in this environment; otherwise it fails before exposing CDP with `Multiple targets are not supported in headless mode`.

Current browser-smoke state: the CDP launch blocker is fixed, guarded 10k and full staged primary-catalog trace-runtime browser smokes pass, and a temporary static-config smoke passes for the 10k payload with `-UseStaticAppConfig`. Default runtime promotion remains blocked only by the explicit promotion decision and preview-only manual-review mutation policy.

## Phase 2 Current State

The canonical import path now:

- Preserves complete raw row JSON including empty fields.
- Preserves row shape anomalies and overflow columns.
- Emits adapter-explicit source claims and mapping-derived source claims.
- Emits field-level mapping/accounting reports.
- Verifies exact subset decisions from `data/reports/ufo_csv_audit.json` when available.
- Emits import failure reports and manual review queue scaffolding.
- Optionally ingests manual review decisions as record-only adjudication annotations.

Relevant files:

```text
parser/canonical_schema.py
parser/csv_sources/base.py
parser/csv_sources/*.py
parser/dedupe.py
scripts/build_canonical_ufo_dataset.py
```

Do not consume fuzzy duplicate candidates as merges without explicit manual decisions. The generated review queue is intentionally non-destructive.

## Static App Safety Rule

Do not replace the existing `data/normalized_events.json`, `data/map_events.json`, or `static_bundle/` with canonical CSV output until compatibility output has passed the full existing test suite and a static-bundle smoke check.

## Full Build Storage Warning

The isolated full canonical build in `data/canonical_full` is intentionally not wired into the web app.

Current measured full-build artifacts total about 25.7 GB. Treat these as archival/build outputs, not browser startup assets.

Before static integration, create compact web-facing artifacts:

- Packed point rows for marker startup.
- Time/spatial shards for map-window queries.
- Lazy event-detail chunks.
- Lazy source-claim/provenance chunks.
- Compressed transport artifacts.
- A compatibility layer that preserves current static app behavior until parity checks pass.

Regenerate size reports with:

```powershell
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\profile_canonical_artifacts.py --build-duration-seconds 1058.7 --legacy-duplicate-path data\canonical_full\canonical_input_events.jsonl
```

## Build Compact Canonical Web Artifacts

Build a small smoke artifact set:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\build_canonical_web_artifacts.py --input data\canonical_full\deduped_events.jsonl --output-dir data\canonical_web_smoke --limit 10000 --write-gzip
```

Build the full compact static-first artifact set:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\build_canonical_web_artifacts.py --input data\canonical_full\deduped_events.jsonl --output-dir data\canonical_web --write-gzip
```

`--write-gzip` emits static-host friendly `.gz` siblings plus `compression_report.json`. Do not wire `data/canonical_web/event_chunks/*.json` into startup as eager loads. They are lazy detail chunks. Startup should use `points.bin`, `points_meta.json`, and compact manifests first.

The builder applies a browser-facing taxonomy projection from `parser/taxonomy.py`:

- Raw source type/shape text remains in lazy details.
- Browser filter fields use cleaned `type`, `shape_normalized`, and `visual_type_group` values.
- Source-family labels such as `NUFORC`, `MUFON`, `BLUEBOOK`, and `UFODNA` are not exposed as object/craft types.
- Description fragments are rejected unless they contain a recognized object shape or bounded event class.

The build also writes lean summary shards for guarded primary-catalog experiments:

```text
data/canonical_web/summary_manifest.json
data/canonical_web/summary_shards/*.json
```

Summary shards intentionally exclude narrative text (`summary`, `description_short`) to avoid duplicating lazy detail payload. Use summary rows for filters, timeline ordering, map/result shells, and `chunk_id`/`detail_index` pointers back to lazy full detail chunks.

The build also writes packed trace-support artifacts:

```text
data/canonical_web/trace_event_index.bin
data/canonical_web/trace_event_index_meta.json
data/canonical_web/trace_segments.bin
data/canonical_web/trace_segments_meta.json
data/canonical_web/trace_aggregate_bins.bin
data/canonical_web/trace_aggregate_bins_meta.json
```

Use `trace_event_index.bin` as the primary future static-trace input: filter rows by the active event universe first, then connect adjacent visible rows in canonical playback order. Treat `trace_segments.bin` as diagnostic/convenience data only; it contains full unfiltered adjacent pairs and does not preserve every possible filtered-adjacent pair after arbitrary filters.

Use `trace_aggregate_bins.bin` only as full-universe wide-window LOD data until a frontend/client aggregator is wired from `trace_event_index.bin`. Its metadata intentionally declares `supported_filter_semantics: ["none/full_universe"]`.

Frontend trace artifact decoding is covered by `webapp/static/packed-trace-utils.mjs` and `tests/test_packed_traces_frontend.mjs`. `webapp/static_public/app.js` exposes guarded debug loaders and an off-by-default `canonicalWebArtifacts.traceRuntime` branch that can build static trace segments from cached `trace_event_index` rows only when the canonical primary catalog is explicitly enabled. The shipped config leaves this disabled.

Deployment strategy for these opt-in payloads is tracked in `docs/CANONICAL_WEB_DEPLOYMENT_STRATEGY.md`.

Stage a small trace-runtime static payload without copying the full canonical web corpus:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\stage_canonical_web_static_payload.py --artifact-dir data\canonical_web --output-root data\canonical_web_static_trace_payload --mode trace-runtime
```

That writes files under `data/canonical_web_static_trace_payload/data/canonical_web`. Use this payload for guarded trace-artifact loader testing. Do not merge it into the normal `static_bundle.zip` unless the extra payload size is intentional.

For a standalone guarded primary-catalog + trace-runtime payload, include summary shards too:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\stage_canonical_web_static_payload.py --artifact-dir data\canonical_web --output-root data\canonical_web_static_primary_trace_payload --mode primary-catalog-trace-runtime
```

This mode copies summary shards and trace artifacts but still omits lazy full-detail event chunks. It is for startup/filter/timeline/map-shell preview, not complete event-detail browsing.

For a complete production-like payload that supports full-detail browsing, explicitly include lazy detail chunks:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\stage_canonical_web_static_payload.py --artifact-dir data\canonical_web --output-root data\canonical_web_static_primary_trace_payload_full --mode primary-catalog-trace-runtime-with-details
```

This full-detail mode is intentionally opt-in because it copies all `event_chunks/*.json` plus gzip siblings when available. Use it for deployment/package tests, not for the default `static_bundle.zip`.

Validate runtime readiness:

```powershell
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\check_canonical_web_runtime_readiness.py --artifact-dir data\canonical_web --output data\reports\canonical_web_runtime_readiness.json
```

The readiness report should be `ready_for_startup_preview` before frontend experiments. `ready_for_primary_catalog_prototype` can be true once summary shards are valid, but `ready_for_primary_catalog` should remain false until UI parity and lazy detail hydration are smoke-tested end to end.

Validate the staged static payload after staging:

```powershell
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\check_canonical_web_static_payload.py --payload-root data\canonical_web_static_primary_trace_payload --static-bundle-root static_bundle --output data\reports\canonical_web_static_payload_readiness.json
```

This checks the copied payload manifest, mode-required files, gzip sibling pairing, lean/full-detail chunk policy, provenance-only file exclusion, and confirms the checked-in `static_bundle/data/app_config.json` keeps `canonicalWebArtifacts` disabled.

Summarize all runtime integration gates into one report:

```powershell
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\summarize_runtime_integration_readiness.py --manual-review-packet-readiness data\reports\manual_review_packet_readiness.json --canonical-facet-readiness data\reports\canonical_facet_readiness.json --output data\reports\runtime_integration_readiness_gate.json
```

Expected current state is `preview_ready_default_blocked`: the payload can be previewed, but default promotion remains blocked until browser runtime smoke passes and canonical primary catalog promotion is explicitly approved.

Summarize browser-facing facet readiness before adding new UI facet controls:

```powershell
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\summarize_canonical_facet_readiness.py --scan-summary-shards --output data\reports\canonical_facet_readiness.json
```

Expected current status is `ready_with_caveats`: source/date/location/coordinate-source facets are manifest-counted, and visual type/time/playback chronology facets are counted by scanning summary shards. Type, shape, visual type group, and time sort kind have high unknown coverage and should be exposed with caveats.

Summarize the current capped fuzzy duplicate queue as connected components:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\summarize_duplicate_candidate_clusters.py --candidates data\canonical_full\duplicate_candidates.jsonl --output data\reports\duplicate_candidate_cluster_summary.json
```

Use this to diagnose how much of the 5,000-item queue is consumed by dense all-pairs candidate blocks.

Estimate expanded dedupe opportunity without applying merges:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\summarize_expanded_dedupe_opportunities.py --source-records data\canonical_full\source_records.jsonl --deduped-events data\canonical_full\deduped_events.jsonl --output data\reports\expanded_dedupe_opportunity_report.json
```

The report is analysis-only. It must keep `canonical_outputs_mutated`, `preview_outputs_written`, `decisions_created`, and `auto_merge_performed` false. Treat projected reductions as review opportunity, not approved merges.

Consolidate the dedupe math against the external UFOSINT screenshot benchmark:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\summarize_dedupe_benchmark_gap.py --output data\reports\dedupe_benchmark_gap_summary.json
```

This report deliberately treats the 618,316 count as an external methodology-unknown benchmark. Do not use it as an auto-merge target.

Build the compact input-event lookup used by ER/review tools:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\build_input_event_lookup.py --deduped-events data\canonical_full\deduped_events.jsonl --output data\canonical_full\input_event_lookup.jsonl --report data\reports\input_event_lookup_report.json
```

This writes one compact JSONL row per `canonical_input_id` with its current `canonical_event_id`. It is a derived acceleration artifact only; `deduped_events.jsonl` remains authoritative.

Score entity-resolution candidates without applying merges:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\score_entity_resolution_candidates.py --limit 100000 --max-scored-pairs 100000 --output data\reports\entity_resolution_score_report_sample100k.json
```

Run the full report-only scorer when a longer full-corpus pass is intended:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\score_entity_resolution_candidates.py --max-scored-pairs 500000 --output data\reports\entity_resolution_score_report.json
```

The scorer is analysis-only. Treat `likely_same_event_review`, `strong_candidate_review`, and `moderate_candidate_review` as review priority bands, not merge decisions. Limited runs use a touched-input lookup and intentionally leave full-corpus count fields null.

Build a review-only packet from the ER score report:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\build_entity_resolution_review_packet.py --score-report data\reports\entity_resolution_score_report.json --json-output data\reports\entity_resolution_review_packet.json --csv-output data\reports\entity_resolution_review_packet.csv --markdown-output data\reports\entity_resolution_review_packet.md --per-band-limit 50 --markdown-item-limit 120
```

The packet exports cross-current-event review candidates by default. Use `--include-already-merged` only for calibration/debugging samples, not merge review.

Summarize ER calibration hotspots and review readiness:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\summarize_entity_resolution_calibration.py --score-report data\reports\entity_resolution_score_report.json --review-packet data\reports\entity_resolution_review_packet.json --output data\reports\entity_resolution_calibration_summary.json
```

This report is calibration-only. It summarizes score bands, risk hotspots, source-pair hotspots, review-packet coverage, and workflow readiness. It fails closed if the score report or review packet is not marked report-only. `ready_for_human_review` may be true while `ready_for_apply` remains false until validated `same_event` decisions exist.

Generate conservative AI-assisted ER suggestions without creating validated decisions:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\ai_suggest_entity_resolution_decisions.py --packet data\reports\entity_resolution_review_packet.json --suggestions-output data\reports\entity_resolution_review_suggestions.jsonl --report-output data\reports\entity_resolution_review_suggestions_report.json
```

This writes suggestion-only rows with `suggested_decision`, confidence, rationale, and audit evidence. It deliberately keeps `decisions_created`, `decision_outputs_created`, `validated_decisions_created`, and `auto_merge_performed` false. Convert accepted suggestions to ER decision records before using the validator below.

Promote conservative ER suggestions into a separate AI-accepted decision file:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\promote_entity_resolution_suggestions.py --suggestions data\reports\entity_resolution_review_suggestions.jsonl --suggestions-report data\reports\entity_resolution_review_suggestions_report.json --decisions-output data\canonical_full\entity_resolution_decisions_ai_accepted.jsonl --report-output data\reports\entity_resolution_suggestion_promotion_report.json
```

This creates AI-accepted decision records but still does not validate or apply them. Keep this output separate from `data/canonical_full/entity_resolution_decisions.jsonl` unless deliberately promoting it to the main decision lane.

Validate reviewer-provided ER decisions without applying them:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\validate_entity_resolution_decisions.py --packet data\reports\entity_resolution_review_packet.json --decisions data\canonical_full\entity_resolution_decisions.jsonl --normalized-output data\canonical_full\entity_resolution_validated_decisions.jsonl --report-output data\reports\entity_resolution_decisions_report.json
```

Allowed decisions are `same_event`, `distinct_events`, and `needs_more_evidence`. Validated `same_event` rows are still `validated_not_applied`; they require a later stream-safe effect planning/apply step.

Validate the AI-accepted ER decision lane separately:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\validate_entity_resolution_decisions.py --packet data\reports\entity_resolution_review_packet.json --decisions data\canonical_full\entity_resolution_decisions_ai_accepted.jsonl --normalized-output data\canonical_full\entity_resolution_validated_decisions_ai_accepted.jsonl --report-output data\reports\entity_resolution_ai_decisions_validation_report.json
```

Plan effects for validated ER decisions without applying them:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\plan_entity_resolution_effects.py --validated-decisions data\canonical_full\entity_resolution_validated_decisions.jsonl --output data\reports\entity_resolution_effects_plan.json
```

The plan maps `same_event` to `merge_entity_resolution_candidate`, `distinct_events` to `preserve_distinct_events`, and `needs_more_evidence` to `defer_entity_resolution_candidate`. It remains plan-only; merge effects still require a later stream-safe preview/apply implementation.

Plan effects for the AI-accepted ER lane separately:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\plan_entity_resolution_effects.py --validated-decisions data\canonical_full\entity_resolution_validated_decisions_ai_accepted.jsonl --output data\reports\entity_resolution_ai_effects_plan.json
```

Summarize the AI-accepted ER effects plan without applying or copying the corpus:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\summarize_entity_resolution_effect_impact.py --effects-plan data\reports\entity_resolution_ai_effects_plan.json --output data\reports\entity_resolution_ai_effect_impact_summary.json
```

This estimates projected event reduction from event IDs already present in the ER effects plan. It does not stream or copy `deduped_events.jsonl`.

Build a compact ER merge preview patch without writing a shadow corpus:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\build_entity_resolution_merge_preview_patch.py --effects-plan data\reports\entity_resolution_ai_effects_plan.json --output data\reports\entity_resolution_ai_merge_preview_patch.json
```

The patch contains replacement/suppressed event IDs and input IDs for inspection. It is not a final merge output and does not choose final merged event bodies or provenance reconciliation.

Build compact merged-event body previews for the ER patch:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\build_entity_resolution_merged_event_preview.py --merge-patch data\reports\entity_resolution_ai_merge_preview_patch.json --deduped-events data\canonical_full\deduped_events.jsonl --output data\reports\entity_resolution_ai_merged_event_preview.json
```

This hydrates only event rows referenced by the patch, reports representative fields and field conflicts, and keeps descriptions/provenance bounded. `preview_event.body_policy` is `compact_preview_summary_not_canonical_event_body`; do not treat it as a canonical merged event row.

Check ER merge readiness before a full shadow-corpus preview:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\check_entity_resolution_merge_readiness.py --merged-event-preview data\reports\entity_resolution_ai_merged_event_preview.json --output data\reports\entity_resolution_ai_merge_readiness.json
```

This gate treats hard date/time/type conflicts and large coordinate distance as blockers. Tiny coordinate variance and raw-location/text differences are review-only conflicts.

Filter the ER effects plan to a readiness-approved shadow-preview subset:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\filter_entity_resolution_effects_plan_by_readiness.py --effects-plan data\reports\entity_resolution_ai_effects_plan.json --readiness-report data\reports\entity_resolution_ai_merge_readiness.json --output data\reports\entity_resolution_ai_effects_plan_ready_subset.json
```

This subset keeps only merge effects that passed the readiness gate. It is intended for shadow preview only; excluded merge effects remain deferred.

Preview ER merge effects without mutating canonical outputs:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\preview_entity_resolution_apply.py --effects-plan data\reports\entity_resolution_effects_plan.json --deduped-events data\canonical_full\deduped_events.jsonl --output-dir data\canonical_preview_entity_resolution --report-output data\reports\entity_resolution_preview_apply_report.json
```

When there are no merge effects, the preview applier writes only a no-op report and does not copy the full 5.9GB corpus. When merge effects exist, it streams `deduped_events.jsonl`, buffers only merge-group rows, and writes a shadow `deduped_events.jsonl` under the preview directory.

Preview the readiness-approved AI ER subset without mutating canonical outputs:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\preview_entity_resolution_apply.py --effects-plan data\reports\entity_resolution_ai_effects_plan_ready_subset.json --deduped-events data\canonical_full\deduped_events.jsonl --output-dir data\canonical_preview_entity_resolution_ai_ready_subset --report-output data\reports\entity_resolution_ai_ready_subset_preview_apply_report.json
```

This writes a full shadow `deduped_events.jsonl` for the approved subset only. It is expected to be multi-GB; check disk space first.

Validate the ER shadow preview output:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\check_entity_resolution_preview_output.py --preview-report data\reports\entity_resolution_ai_ready_subset_preview_apply_report.json --preview-events data\canonical_preview_entity_resolution_ai_ready_subset\deduped_events.jsonl --output data\reports\entity_resolution_ai_ready_subset_preview_output_check.json
```

Build a focused packet for ER merges blocked by readiness:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\build_entity_resolution_blocked_merge_packet.py --readiness-report data\reports\entity_resolution_ai_merge_readiness.json --merged-event-preview data\reports\entity_resolution_ai_merged_event_preview.json --json-output data\reports\entity_resolution_blocked_merge_review_packet.json --csv-output data\reports\entity_resolution_blocked_merge_review_packet.csv --markdown-output data\reports\entity_resolution_blocked_merge_review_packet.md
```

Analyze blocked ER merges without creating decisions:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\analyze_entity_resolution_blocked_merges.py --blocked-packet data\reports\entity_resolution_blocked_merge_review_packet.json --output data\reports\entity_resolution_blocked_merge_analysis.json
```

This report is suggestion-only. It can identify high-confidence source subtype variants for a shadow-preview override lane, while keeping coordinate-distance conflicts review-first.

Build a shadow-preview subset that adds only high-confidence blocked-merge analysis overrides:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\build_entity_resolution_shadow_override_effects_plan.py --effects-plan data\reports\entity_resolution_ai_effects_plan.json --ready-subset data\reports\entity_resolution_ai_effects_plan_ready_subset.json --blocked-analysis data\reports\entity_resolution_blocked_merge_analysis.json --output data\reports\entity_resolution_ai_effects_plan_shadow_override_subset.json
```

Preview and validate that shadow-override subset without mutating canonical outputs:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\preview_entity_resolution_apply.py --effects-plan data\reports\entity_resolution_ai_effects_plan_shadow_override_subset.json --deduped-events data\canonical_full\deduped_events.jsonl --output-dir data\canonical_preview_entity_resolution_ai_shadow_override_subset --report-output data\reports\entity_resolution_ai_shadow_override_subset_preview_apply_report.json

$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\check_entity_resolution_preview_output.py --preview-report data\reports\entity_resolution_ai_shadow_override_subset_preview_apply_report.json --preview-events data\canonical_preview_entity_resolution_ai_shadow_override_subset\deduped_events.jsonl --output data\reports\entity_resolution_ai_shadow_override_subset_preview_output_check.json
```

Summarize the delta between the readiness-only shadow preview and the shadow-override preview:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\summarize_entity_resolution_shadow_override_delta.py --ready-subset data\reports\entity_resolution_ai_effects_plan_ready_subset.json --ready-preview-report data\reports\entity_resolution_ai_ready_subset_preview_apply_report.json --ready-output-check data\reports\entity_resolution_ai_ready_subset_preview_output_check.json --override-subset data\reports\entity_resolution_ai_effects_plan_shadow_override_subset.json --override-preview-report data\reports\entity_resolution_ai_shadow_override_subset_preview_apply_report.json --override-output-check data\reports\entity_resolution_ai_shadow_override_subset_preview_output_check.json --blocked-analysis data\reports\entity_resolution_blocked_merge_analysis.json --output data\reports\entity_resolution_shadow_override_delta_summary.json
```

Check whether the validated shadow preview is ready for canonical apply:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\check_entity_resolution_canonical_apply_readiness.py --delta-summary data\reports\entity_resolution_shadow_override_delta_summary.json --override-subset data\reports\entity_resolution_ai_effects_plan_shadow_override_subset.json --override-preview-report data\reports\entity_resolution_ai_shadow_override_subset_preview_apply_report.json --override-output-check data\reports\entity_resolution_ai_shadow_override_subset_preview_output_check.json --output data\reports\entity_resolution_canonical_apply_readiness.json
```

This gate must remain blocking until final canonical merge-body/provenance policy and a separate canonical apply command exist.

Build the report-only canonical merge-body/provenance policy proposal:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\propose_entity_resolution_canonical_merge_policy.py --merged-event-preview data\reports\entity_resolution_ai_merged_event_preview.json --shadow-override-delta data\reports\entity_resolution_shadow_override_delta_summary.json --apply-readiness data\reports\entity_resolution_canonical_apply_readiness.json --output data\reports\entity_resolution_canonical_merge_policy_proposal.json
```

This proposal is a draft policy artifact only. It records deterministic field/provenance rules and observed conflict counts; it does not implement canonical apply.

Build compact policy-body previews for selected ER merge candidates:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\build_entity_resolution_policy_body_preview.py --merged-event-preview data\reports\entity_resolution_ai_merged_event_preview.json --policy-proposal data\reports\entity_resolution_canonical_merge_policy_proposal.json --override-subset data\reports\entity_resolution_ai_effects_plan_shadow_override_subset.json --output data\reports\entity_resolution_policy_body_preview.json
```

This compact preview shows proposed canonical merge audit fields and conflict metadata for the selected shadow-override effects. It is not a full canonical event corpus.

Validate the compact policy-body preview:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\check_entity_resolution_policy_body_preview.py --policy-body-preview data\reports\entity_resolution_policy_body_preview.json --output data\reports\entity_resolution_policy_body_preview_check.json
```

This validates required audit fields, selected-effect count, duplicate IDs, merge policy identity, and conflict metadata references. It remains report-only.

### Expanded ER review samples

To expand the deterministic ER review lane beyond the original 200 packet rows, regenerate a separate score report with larger retained samples:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\score_entity_resolution_candidates.py --source-records data\canonical_full\source_records.jsonl --deduped-events data\canonical_full\deduped_events.jsonl --input-event-lookup data\canonical_full\input_event_lookup.jsonl --output data\reports\entity_resolution_score_report_samples500.json --top-pair-limit 2000 --band-sample-limit 500
```

Build the expanded packet and suggestion lane:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\build_entity_resolution_review_packet.py --score-report data\reports\entity_resolution_score_report_samples500.json --json-output data\reports\entity_resolution_review_packet_samples500.json --csv-output data\reports\entity_resolution_review_packet_samples500.csv --markdown-output data\reports\entity_resolution_review_packet_samples500.md --per-band-limit 500 --markdown-item-limit 200

& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\ai_suggest_entity_resolution_decisions.py --packet data\reports\entity_resolution_review_packet_samples500.json --suggestions-output data\reports\entity_resolution_review_suggestions_samples500.jsonl --report-output data\reports\entity_resolution_review_suggestions_samples500_report.json
```

Promote, validate, plan, and preview this expanded lane under separate `samples500` artifact names. Keep it separate from the original 200-row baseline:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\promote_entity_resolution_suggestions.py --suggestions data\reports\entity_resolution_review_suggestions_samples500.jsonl --suggestions-report data\reports\entity_resolution_review_suggestions_samples500_report.json --decisions-output data\canonical_full\entity_resolution_decisions_ai_accepted_samples500.jsonl --report-output data\reports\entity_resolution_suggestion_promotion_samples500_report.json

& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\validate_entity_resolution_decisions.py --packet data\reports\entity_resolution_review_packet_samples500.json --decisions data\canonical_full\entity_resolution_decisions_ai_accepted_samples500.jsonl --normalized-output data\canonical_full\entity_resolution_validated_decisions_ai_accepted_samples500.jsonl --report-output data\reports\entity_resolution_ai_decisions_validation_samples500_report.json

& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\plan_entity_resolution_effects.py --validated-decisions data\canonical_full\entity_resolution_validated_decisions_ai_accepted_samples500.jsonl --output data\reports\entity_resolution_ai_effects_plan_samples500.json

& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\summarize_entity_resolution_effect_impact.py --effects-plan data\reports\entity_resolution_ai_effects_plan_samples500.json --output data\reports\entity_resolution_ai_effect_impact_samples500_summary.json
```

Build compact previews, readiness-filter, and shadow-preview the expanded lane:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\build_entity_resolution_merge_preview_patch.py --effects-plan data\reports\entity_resolution_ai_effects_plan_samples500.json --output data\reports\entity_resolution_ai_merge_preview_patch_samples500.json

& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\build_entity_resolution_merged_event_preview.py --merge-patch data\reports\entity_resolution_ai_merge_preview_patch_samples500.json --deduped-events data\canonical_full\deduped_events.jsonl --output data\reports\entity_resolution_ai_merged_event_preview_samples500.json

& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\check_entity_resolution_merge_readiness.py --merged-event-preview data\reports\entity_resolution_ai_merged_event_preview_samples500.json --output data\reports\entity_resolution_ai_merge_readiness_samples500.json

& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\filter_entity_resolution_effects_plan_by_readiness.py --effects-plan data\reports\entity_resolution_ai_effects_plan_samples500.json --readiness-report data\reports\entity_resolution_ai_merge_readiness_samples500.json --output data\reports\entity_resolution_ai_effects_plan_ready_subset_samples500.json

& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\build_entity_resolution_blocked_merge_packet.py --readiness-report data\reports\entity_resolution_ai_merge_readiness_samples500.json --merged-event-preview data\reports\entity_resolution_ai_merged_event_preview_samples500.json --json-output data\reports\entity_resolution_blocked_merge_review_packet_samples500.json --csv-output data\reports\entity_resolution_blocked_merge_review_packet_samples500.csv --markdown-output data\reports\entity_resolution_blocked_merge_review_packet_samples500.md

& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\analyze_entity_resolution_blocked_merges.py --blocked-packet data\reports\entity_resolution_blocked_merge_review_packet_samples500.json --output data\reports\entity_resolution_blocked_merge_analysis_samples500.json

& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\build_entity_resolution_shadow_override_effects_plan.py --effects-plan data\reports\entity_resolution_ai_effects_plan_samples500.json --ready-subset data\reports\entity_resolution_ai_effects_plan_ready_subset_samples500.json --blocked-analysis data\reports\entity_resolution_blocked_merge_analysis_samples500.json --output data\reports\entity_resolution_ai_effects_plan_shadow_override_subset_samples500.json

& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\preview_entity_resolution_apply.py --effects-plan data\reports\entity_resolution_ai_effects_plan_shadow_override_subset_samples500.json --deduped-events data\canonical_full\deduped_events.jsonl --output-dir data\canonical_preview_entity_resolution_ai_shadow_override_subset_samples500 --report-output data\reports\entity_resolution_ai_shadow_override_subset_samples500_preview_apply_report.json

& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\check_entity_resolution_preview_output.py --preview-report data\reports\entity_resolution_ai_shadow_override_subset_samples500_preview_apply_report.json --preview-events data\canonical_preview_entity_resolution_ai_shadow_override_subset_samples500\deduped_events.jsonl --output data\reports\entity_resolution_ai_shadow_override_subset_samples500_preview_output_check.json
```

The shadow-output checker handles connected merge groups by expecting one preview merge row per unique `preview_canonical_event_id`, not one row per applied effect.

To run a larger separated lane, keep the same commands and suffix every artifact consistently. Current expanded lanes use:

```text
samples500: --top-pair-limit 2000 --band-sample-limit 500
samples1000: --top-pair-limit 4000 --band-sample-limit 1000
```

For `samples1000`, replace each `samples500` artifact suffix above with `samples1000`, set the review-packet `--per-band-limit` to `1000`, and use `--markdown-item-limit 200` or another explicit bounded value. The scorer must be rerun for each larger retained sample size; the packet builder cannot recover omitted candidate rows from a smaller score report.

Readiness reports should include full `blocking_items` and `review_items` arrays. Downstream ready-subset filtering and blocked-packet generation consume full `blocking_items` when present and fall back to `blocking_items_sample` only for older reports. Do not use a sampled-only readiness report for expanded shadow previews with more than 50 blockers.

For future larger ER review expansion, prefer generating a sidecar candidate worklist during the scorer pass instead of repeatedly rerunning the scorer for every packet size:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\score_entity_resolution_candidates.py --source-records data\canonical_full\source_records.jsonl --deduped-events data\canonical_full\deduped_events.jsonl --input-event-lookup data\canonical_full\input_event_lookup.jsonl --output data\reports\entity_resolution_score_report_with_worklist.json --candidate-worklist-output data\reports\entity_resolution_candidate_worklist.jsonl --candidate-worklist-per-band-limit 5000 --candidate-worklist-min-band moderate_candidate_review
```

The worklist is still candidate-only. It records scored cross-current-event pairs for review acceleration and keeps `canonical_outputs_mutated`, `preview_outputs_written`, `decisions_created`, and `auto_merge_performed` false. The score report records the worklist summary while the potentially larger rows stay in the separate JSONL sidecar.

Build a review packet from that sidecar without rerunning the scorer:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\build_entity_resolution_review_packet.py --score-report data\reports\entity_resolution_score_report_with_worklist.json --candidate-worklist data\reports\entity_resolution_candidate_worklist.jsonl --json-output data\reports\entity_resolution_review_packet_from_worklist.json --csv-output data\reports\entity_resolution_review_packet_from_worklist.csv --markdown-output data\reports\entity_resolution_review_packet_from_worklist.md --per-band-limit 500 --markdown-item-limit 200 --exclude-weak
```

This preserves the score report as provenance but uses `candidate_worklist_jsonl` as the sample source. It does not create decisions, validate decisions, plan effects, or mutate canonical outputs.

Compare the ER lanes after generating baseline/sample/worklist artifacts:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\summarize_entity_resolution_lanes.py --output data\reports\entity_resolution_lane_comparison.json
```

Use this report to distinguish candidate/effect counts from actual shadow-preview reduction. It is report-only and keeps canonical mutation, preview writing, decision creation, and auto-merge flags false.

Generate a wider cluster-opportunity report and cluster review packet when pairwise ER lanes are no longer enough:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\summarize_expanded_dedupe_opportunities.py --source-records data\canonical_full\source_records.jsonl --deduped-events data\canonical_full\deduped_events.jsonl --top-group-limit 500 --top-group-event-id-limit 300 --output data\reports\expanded_dedupe_opportunity_report_top500.json

& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\build_entity_resolution_cluster_review_packet.py --opportunity-report data\reports\expanded_dedupe_opportunity_report_top500.json --json-output data\reports\entity_resolution_cluster_review_packet.json --csv-output data\reports\entity_resolution_cluster_review_packet.csv --markdown-output data\reports\entity_resolution_cluster_review_packet.md --per-family-limit 500 --markdown-item-limit 250

& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\check_entity_resolution_cluster_review_packet.py --packet data\reports\entity_resolution_cluster_review_packet.json --csv data\reports\entity_resolution_cluster_review_packet.csv --markdown data\reports\entity_resolution_cluster_review_packet.md --output data\reports\entity_resolution_cluster_review_packet_check.json
```

The cluster packet is a review/planning surface only. It does not create cluster decisions, does not validate decisions, and does not mutate canonical outputs. The `--top-group-event-id-limit` option exports bounded `current_event_ids` into each top opportunity group so cluster reviewers can trace a cluster back to exact current canonical events without inventing merge decisions.

After human or AI-assisted review creates explicit cluster decisions, validate and plan them under separate cluster-suffixed artifacts:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\ai_suggest_entity_resolution_cluster_decisions.py --packet data\reports\entity_resolution_cluster_review_packet.json --suggestions-output data\reports\entity_resolution_cluster_review_suggestions.jsonl --report-output data\reports\entity_resolution_cluster_review_suggestions_report.json

& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\promote_entity_resolution_cluster_suggestions.py --suggestions data\reports\entity_resolution_cluster_review_suggestions.jsonl --suggestions-report data\reports\entity_resolution_cluster_review_suggestions_report.json --decisions-output data\canonical_full\entity_resolution_cluster_decisions_ai_accepted.jsonl --report-output data\reports\entity_resolution_cluster_suggestion_promotion_report.json

& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\validate_entity_resolution_cluster_decisions.py --packet data\reports\entity_resolution_cluster_review_packet.json --decisions data\canonical_full\entity_resolution_cluster_decisions.jsonl --normalized-output data\canonical_full\entity_resolution_validated_cluster_decisions.jsonl --report-output data\reports\entity_resolution_cluster_decisions_validation_report.json

& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\plan_entity_resolution_effects.py --validated-decisions data\canonical_full\entity_resolution_validated_cluster_decisions.jsonl --output data\reports\entity_resolution_cluster_effects_plan.json

& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\summarize_entity_resolution_effect_impact.py --effects-plan data\reports\entity_resolution_cluster_effects_plan.json --output data\reports\entity_resolution_cluster_effect_impact_summary.json
```

Do not mix cluster and pairwise ER plans when reporting reduction totals. Cluster decisions are valid only when they explicitly reference a packet `cluster_review_id`; full-cluster `same_event` decisions are rejected if the packet's `current_event_ids` are missing, truncated, or count-mismatched.

The cluster suggestion script is intentionally stricter than the cluster packet itself. It only suggests `same_event` for complete, non-truncated conservative clusters from strict families with one date and one location. The current generated suggestion lane has 554 `same_event` suggestions and 4,491 `needs_more_evidence` suggestions. Readiness still blocks most accepted cluster suggestions because compact merged bodies expose `time_raw`, type, and coordinate conflicts; treat the ready subset and blocked analysis as review inputs, not merge approval.

To review blocked cluster candidates with classifications joined back to source details:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\build_entity_resolution_blocked_merge_action_packet.py --blocked-packet data\reports\entity_resolution_cluster_blocked_merge_review_packet.json --blocked-analysis data\reports\entity_resolution_cluster_blocked_merge_analysis.json --json-output data\reports\entity_resolution_cluster_blocked_merge_action_packet.json --csv-output data\reports\entity_resolution_cluster_blocked_merge_action_packet.csv --markdown-output data\reports\entity_resolution_cluster_blocked_merge_action_packet.md --markdown-item-limit 250

& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\build_entity_resolution_blocked_merge_action_packet.py --blocked-packet data\reports\entity_resolution_cluster_blocked_merge_review_packet.json --blocked-analysis data\reports\entity_resolution_cluster_blocked_merge_analysis.json --include-classification time_format_or_multiple_time_variant --include-classification time_conflict_requires_review --json-output data\reports\entity_resolution_cluster_time_blocker_action_packet.json --csv-output data\reports\entity_resolution_cluster_time_blocker_action_packet.csv --markdown-output data\reports\entity_resolution_cluster_time_blocker_action_packet.md --markdown-item-limit 250
```

The focused time-blocker packet currently exports 420 review items. It is for review planning only and does not create overrides or decisions.

To build the prioritized queue for the remaining cluster blockers after excluding the current 18 already-selected shadow overrides:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\build_entity_resolution_cluster_blocker_priority_queue.py --action-packet data\reports\entity_resolution_cluster_blocked_merge_action_packet.json --override-subset data\reports\entity_resolution_cluster_ai_effects_plan_shadow_override_subset.json --json-output data\reports\entity_resolution_cluster_blocker_priority_queue.json --csv-output data\reports\entity_resolution_cluster_blocker_priority_queue.csv --markdown-output data\reports\entity_resolution_cluster_blocker_priority_queue.md --markdown-item-limit 120
```

This queue is review-only. It keeps canonical mutation, preview writing, decision creation, and auto-merge flags false. Current queue counts are 520 remaining blockers: 230 time-format reviews, 174 time-conflict reviews, 84 type-conflict reviews, and 32 coordinate-conflict reviews. The action packets and queue include canonical event/input IDs in source summaries, so reviewers can audit exact current events without promoting any row to a decision. Use it as the next triage surface before creating any additional explicit cluster decisions or override subsets.

To classify the 230 time-format review blockers into time-normalization review buckets:

```powershell
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\analyze_entity_resolution_cluster_time_normalization.py --priority-queue data\reports\entity_resolution_cluster_blocker_priority_queue.json --json-output data\reports\entity_resolution_cluster_time_normalization_analysis.json --csv-output data\reports\entity_resolution_cluster_time_normalization_analysis.csv --markdown-output data\reports\entity_resolution_cluster_time_normalization_analysis.md --markdown-item-limit 120
```

This is review-only. It currently classifies 230 items into 57 lower-risk review cases, 142 medium-risk cases, and 31 high-risk distinct-time cases. It should be used to decide what evidence to review next, not to bypass readiness or create merge decisions.

To build and validate the strict v2 time-normalization shadow-preview subset:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\build_entity_resolution_cluster_time_norm_shadow_override_subset.py --effects-plan data\reports\entity_resolution_cluster_ai_effects_plan.json --base-subset data\reports\entity_resolution_cluster_ai_effects_plan_shadow_override_subset.json --time-analysis data\reports\entity_resolution_cluster_time_normalization_analysis.json --output data\reports\entity_resolution_cluster_time_norm_shadow_override_subset.json

& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\summarize_entity_resolution_effect_impact.py --effects-plan data\reports\entity_resolution_cluster_time_norm_shadow_override_subset.json --output data\reports\entity_resolution_cluster_time_norm_shadow_override_effect_impact_summary.json

& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\preview_entity_resolution_apply.py --effects-plan data\reports\entity_resolution_cluster_time_norm_shadow_override_subset.json --deduped-events data\canonical_full\deduped_events.jsonl --output-dir data\canonical_preview_entity_resolution_cluster_time_norm_shadow_override_subset --report-output data\reports\entity_resolution_cluster_time_norm_shadow_override_subset_preview_apply_report.json

& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\check_entity_resolution_preview_output.py --preview-report data\reports\entity_resolution_cluster_time_norm_shadow_override_subset_preview_apply_report.json --preview-events data\canonical_preview_entity_resolution_cluster_time_norm_shadow_override_subset\deduped_events.jsonl --output data\reports\entity_resolution_cluster_time_norm_shadow_override_subset_preview_output_check.json
```

This subset uses `entity_resolution_cluster_time_normalization_shadow_preview_subset_v2`. It extends the 34-effect cluster shadow subset with 44 additional lower-risk time-normalization candidates only when the blocker is exactly `time_raw`, the parsed exact-minute span is 15 minutes or less, there are no fuzzy/ambiguous/unknown tokens, and the source summary has one source name, one source-native ID, one date, one location, and at least two canonical events. The current shadow preview applies 78 effects, blocks 0, projects a 120-event reduction, and validates 944,458 preview rows with 78 preview merge rows. It is preview-only and still does not create accepted decisions or mutate canonical outputs.

To classify the remaining 174 time-conflict review blockers:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\analyze_entity_resolution_cluster_time_conflicts.py --priority-queue data\reports\entity_resolution_cluster_blocker_priority_queue.json --json-output data\reports\entity_resolution_cluster_time_conflict_analysis.json --csv-output data\reports\entity_resolution_cluster_time_conflict_analysis.csv --markdown-output data\reports\entity_resolution_cluster_time_conflict_analysis.md --markdown-item-limit 120
```

This is review-only. After applying the stricter approximate-token and coordinate-risk gates, all 174 time-conflict items remain high risk. The report still identifies useful review structure: 15 exact conflicts within 5 minutes, 9 exact conflicts within 15 minutes, 3 within-15-minute conflicts with approximation markers, 8 within-15-minute conflicts with other context, and 28 within-60-minute conflicts. It also records identity consistency: 146 items have a single source/source-native-ID/date/location block, while 28 are mixed or incomplete identity; 154 items carry coordinate-risk flags. Do not treat this report as approval to merge time conflicts; it is a triage surface for source-row review.

To classify the remaining 84 type-conflict review blockers:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\analyze_entity_resolution_cluster_type_conflicts.py --priority-queue data\reports\entity_resolution_cluster_blocker_priority_queue.json --json-output data\reports\entity_resolution_cluster_type_conflict_analysis.json --csv-output data\reports\entity_resolution_cluster_type_conflict_analysis.csv --markdown-output data\reports\entity_resolution_cluster_type_conflict_analysis.md --markdown-item-limit 120
```

This is review-only. It currently classifies 84 type-conflict items and keeps all 84 high risk. The report separates 65 type+time conflicts, 15 type+time+coordinate conflicts, 3 type-only cross-family conflicts, and 1 type-only single-family subcode conflict. Identity consistency is still recorded: 80 items have a single source/source-native-ID/date/location block, while 4 are mixed or incomplete identity. Do not promote any type-conflict item without source-row review.

To classify the remaining 32 coordinate-conflict review blockers:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\analyze_entity_resolution_cluster_coordinate_conflicts.py --priority-queue data\reports\entity_resolution_cluster_blocker_priority_queue.json --json-output data\reports\entity_resolution_cluster_coordinate_conflict_analysis.json --csv-output data\reports\entity_resolution_cluster_coordinate_conflict_analysis.csv --markdown-output data\reports\entity_resolution_cluster_coordinate_conflict_analysis.md --markdown-item-limit 120
```

This is review-only. It currently keeps all 32 coordinate-conflict items high risk. Distance buckets are 8 items at 10-15km, 11 at 15-50km, 7 at 50-150km, and 6 over 150km, with a maximum observed spread of 357.423km. Identity consistency is recorded: 31 items have a single source/source-native-ID/date/location block and 1 is mixed or incomplete. These stay map/source review items, not merge candidates.

To regenerate the consolidated cluster blocker analysis checkpoint:

```powershell
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\summarize_entity_resolution_cluster_blocker_analysis_suite.py --priority-queue data\reports\entity_resolution_cluster_blocker_priority_queue.json --time-norm-subset data\reports\entity_resolution_cluster_time_norm_shadow_override_subset.json --time-conflict-analysis data\reports\entity_resolution_cluster_time_conflict_analysis.json --type-conflict-analysis data\reports\entity_resolution_cluster_type_conflict_analysis.json --coordinate-conflict-analysis data\reports\entity_resolution_cluster_coordinate_conflict_analysis.json --json-output data\reports\entity_resolution_cluster_blocker_analysis_suite_summary.json --markdown-output data\reports\entity_resolution_cluster_blocker_analysis_suite_summary.md
```

This checkpoint consolidates the blocker analyses. Current conclusion: the only preview-safe new candidate class under current gates is the 44 strict time-normalization candidates; the remaining 186 time-format items plus all 174 time-conflict, 84 type-conflict, and 32 coordinate-conflict items remain source-row review work.

To build the source-row evidence packet for the 44 strict time-normalization candidates:

```powershell
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\build_entity_resolution_cluster_time_norm_source_evidence_packet.py --subset data\reports\entity_resolution_cluster_time_norm_shadow_override_subset.json --deduped-events data\canonical_full\deduped_events.jsonl --json-output data\reports\entity_resolution_cluster_time_norm_source_evidence_packet.json --csv-output data\reports\entity_resolution_cluster_time_norm_source_evidence_packet.csv --markdown-output data\reports\entity_resolution_cluster_time_norm_source_evidence_packet.md --markdown-item-limit 44 --markdown-row-limit-per-item 8
```

This packet is review-only. It currently extracts evidence for 44 candidate effects, 103 requested/matched canonical events, 0 missing event IDs, 173 candidate input IDs, 281 evidence input IDs from the current canonical rows/provenance, and 0 candidate input IDs missing from evidence. Use this packet to inspect raw/source time evidence, conflict flags, and reviewer prompts before any canonical promotion of the strict time-normalization candidates.

To build conservative source-review recommendations from that evidence packet:

```powershell
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\recommend_entity_resolution_cluster_time_norm_source_decisions.py --packet data\reports\entity_resolution_cluster_time_norm_source_evidence_packet.json --json-output data\reports\entity_resolution_cluster_time_norm_source_review_recommendations.json --csv-output data\reports\entity_resolution_cluster_time_norm_source_review_recommendations.csv --markdown-output data\reports\entity_resolution_cluster_time_norm_source_review_recommendations.md
```

This report is recommendation-only. It currently recommends 33 clean numeric time-only candidates for same-event review, defers 11 candidates, and keeps decisions/apply/canonical mutation disabled. The deferred set includes 10 symbolic or shorthand time-token cases plus 1 clean-token case with a non-time shape conflict.

To build an isolated preview lane for only the 33 clean recommended candidates:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\promote_time_norm_source_recommendations_to_decision_candidates.py --recommendations data\reports\entity_resolution_cluster_time_norm_source_review_recommendations.json --decisions-output data\reports\entity_resolution_cluster_time_norm_recommended_decision_candidates.jsonl --report-output data\reports\entity_resolution_cluster_time_norm_recommended_decision_candidates_report.json --reviewed-at 2026-05-22T00:00:00Z

& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\plan_entity_resolution_effects.py --validated-decisions data\reports\entity_resolution_cluster_time_norm_recommended_decision_candidates.jsonl --output data\reports\entity_resolution_cluster_time_norm_recommended_effects_plan.json

& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\preview_entity_resolution_apply.py --effects-plan data\reports\entity_resolution_cluster_time_norm_recommended_effects_plan.json --deduped-events data\canonical_full\deduped_events.jsonl --output-dir data\canonical_preview_entity_resolution_cluster_time_norm_recommended --report-output data\reports\entity_resolution_cluster_time_norm_recommended_preview_apply_report.json

& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\check_entity_resolution_preview_output.py --preview-report data\reports\entity_resolution_cluster_time_norm_recommended_preview_apply_report.json --preview-events data\canonical_preview_entity_resolution_cluster_time_norm_recommended\deduped_events.jsonl --output data\reports\entity_resolution_cluster_time_norm_recommended_preview_output_check.json
```

Current preview-only result: 33 decision candidates, 33 planned effects, 33 applied preview effects, 0 blocked effects, 40 projected event reduction, 944,538 preview rows, and a valid preview output check. This still does not mutate canonical outputs or mark the lane as canonical-apply ready.

To build the compact merge-body/policy preview for the same lane:

```powershell
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\build_entity_resolution_merge_preview_patch.py --effects-plan data\reports\entity_resolution_cluster_time_norm_recommended_effects_plan.json --output data\reports\entity_resolution_cluster_time_norm_recommended_merge_preview_patch.json

& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\build_entity_resolution_merged_event_preview.py --merge-patch data\reports\entity_resolution_cluster_time_norm_recommended_merge_preview_patch.json --deduped-events data\canonical_full\deduped_events.jsonl --output data\reports\entity_resolution_cluster_time_norm_recommended_merged_event_preview.json

& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\build_time_norm_recommended_policy_body_subset.py --effects-plan data\reports\entity_resolution_cluster_time_norm_recommended_effects_plan.json --output data\reports\entity_resolution_cluster_time_norm_recommended_policy_body_subset.json

& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\build_entity_resolution_policy_body_preview.py --merged-event-preview data\reports\entity_resolution_cluster_time_norm_recommended_merged_event_preview.json --policy-proposal data\reports\entity_resolution_cluster_canonical_merge_policy_proposal.json --override-subset data\reports\entity_resolution_cluster_time_norm_recommended_policy_body_subset.json --output data\reports\entity_resolution_cluster_time_norm_recommended_policy_body_preview.json

& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\check_entity_resolution_policy_body_preview.py --policy-body-preview data\reports\entity_resolution_cluster_time_norm_recommended_policy_body_preview.json --output data\reports\entity_resolution_cluster_time_norm_recommended_policy_body_preview_check.json
```

Current merge-body preview result: 33 merge patches, 33 hydrated compact merged-event previews, 0 missing event IDs, 33 policy-body previews, 0 skipped previews, valid policy-body check, and 0 invalid conflict metadata. The compact conflict fields are `time_raw` on all 33 previews plus `summary` and `description` on 4 previews.

To classify policy conflicts, validate the full-row apply contract, and build/check full canonical-body dry-run rows:

```powershell
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\classify_time_norm_recommended_policy_body_conflicts.py --policy-body-preview data\reports\entity_resolution_cluster_time_norm_recommended_policy_body_preview.json --json-output data\reports\entity_resolution_cluster_time_norm_recommended_policy_conflict_classification.json --csv-output data\reports\entity_resolution_cluster_time_norm_recommended_policy_conflict_classification.csv --markdown-output data\reports\entity_resolution_cluster_time_norm_recommended_policy_conflict_classification.md

& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\check_time_norm_recommended_canonical_apply_contract.py --effects-plan data\reports\entity_resolution_cluster_time_norm_recommended_effects_plan.json --merge-patch data\reports\entity_resolution_cluster_time_norm_recommended_merge_preview_patch.json --recommendations data\reports\entity_resolution_cluster_time_norm_source_review_recommendations.json --policy-conflict-classification data\reports\entity_resolution_cluster_time_norm_recommended_policy_conflict_classification.json --original-events data\canonical_full\deduped_events.jsonl --preview-events data\canonical_preview_entity_resolution_cluster_time_norm_recommended\deduped_events.jsonl --preview-output-check data\reports\entity_resolution_cluster_time_norm_recommended_preview_output_check.json --output data\reports\entity_resolution_cluster_time_norm_recommended_canonical_apply_contract_check.json

& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\build_time_norm_recommended_canonical_body_dry_run.py --effects-plan data\reports\entity_resolution_cluster_time_norm_recommended_effects_plan.json --merge-patch data\reports\entity_resolution_cluster_time_norm_recommended_merge_preview_patch.json --original-events data\canonical_full\deduped_events.jsonl --output-jsonl data\reports\entity_resolution_cluster_time_norm_recommended_canonical_body_dry_run.jsonl --report-output data\reports\entity_resolution_cluster_time_norm_recommended_canonical_body_dry_run_report.json

& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\check_time_norm_recommended_canonical_body_dry_run.py --dry-run-jsonl data\reports\entity_resolution_cluster_time_norm_recommended_canonical_body_dry_run.jsonl --dry-run-report data\reports\entity_resolution_cluster_time_norm_recommended_canonical_body_dry_run_report.json --output data\reports\entity_resolution_cluster_time_norm_recommended_canonical_body_dry_run_check.json
```

Current full-row policy evidence result: 33 low-risk policy candidates, 0 blocking policy conflicts, a valid canonical apply contract check, 33 dry-run merged rows, a valid dry-run check, and 0 incomplete conflict source-value sets. These are still report-only artifacts; they do not rewrite the canonical corpus.

To create the non-mutating accepted-decision artifact and accepted plan-only effects artifact:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\accept_time_norm_recommended_decisions.py --decision-candidates data\reports\entity_resolution_cluster_time_norm_recommended_decision_candidates.jsonl --decision-candidate-report data\reports\entity_resolution_cluster_time_norm_recommended_decision_candidates_report.json --policy-conflict-classification data\reports\entity_resolution_cluster_time_norm_recommended_policy_conflict_classification.json --canonical-apply-contract-check data\reports\entity_resolution_cluster_time_norm_recommended_canonical_apply_contract_check.json --canonical-body-dry-run-check data\reports\entity_resolution_cluster_time_norm_recommended_canonical_body_dry_run_check.json --accepted-decisions-output data\canonical_full\entity_resolution_cluster_time_norm_recommended_accepted_decisions.jsonl --report-output data\reports\entity_resolution_cluster_time_norm_recommended_acceptance_report.json --accepted-at 2026-05-22T00:00:00Z

& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\plan_entity_resolution_effects.py --validated-decisions data\canonical_full\entity_resolution_cluster_time_norm_recommended_accepted_decisions.jsonl --output data\reports\entity_resolution_cluster_time_norm_recommended_accepted_effects_plan.json
```

Current acceptance result: 33 policy-accepted decisions, 33 plan-only accepted effects, 40 projected event reduction, no canonical output mutation, and no auto-merge. This clears only the decision-state blocker; it still does not apply merges.

To stream-apply those accepted decisions into a separate canonical candidate corpus:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\apply_time_norm_recommended_canonical_decisions.py --accepted-effects-plan data\reports\entity_resolution_cluster_time_norm_recommended_accepted_effects_plan.json --dry-run-rows data\reports\entity_resolution_cluster_time_norm_recommended_canonical_body_dry_run.jsonl --dry-run-check data\reports\entity_resolution_cluster_time_norm_recommended_canonical_body_dry_run_check.json --deduped-events data\canonical_full\deduped_events.jsonl --output-events data\canonical_time_norm_recommended\deduped_events.jsonl --report-output data\reports\entity_resolution_cluster_time_norm_recommended_canonical_apply_report.json

& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\check_time_norm_recommended_canonical_apply_output.py --apply-report data\reports\entity_resolution_cluster_time_norm_recommended_canonical_apply_report.json --apply-events data\canonical_time_norm_recommended\deduped_events.jsonl --dry-run-rows data\reports\entity_resolution_cluster_time_norm_recommended_canonical_body_dry_run.jsonl --output data\reports\entity_resolution_cluster_time_norm_recommended_canonical_apply_output_check.json
```

Current stream-apply result: 944,578 input rows, 944,538 output rows, 33 replacement rows, 40 suppressed rows, valid output check, 0 suppressed IDs still present, and the original `data/canonical_full/deduped_events.jsonl` remains untouched. Treat `data/canonical_time_norm_recommended/deduped_events.jsonl` as a canonical candidate corpus until downstream compact-web/runtime rebuild checks pass.

To build and validate compact web artifacts from that candidate corpus:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\build_canonical_web_artifacts.py --input data\canonical_time_norm_recommended\deduped_events.jsonl --output-dir data\canonical_web_time_norm_recommended_smoke --limit 10000 --write-gzip
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\check_canonical_web_runtime_readiness.py --artifact-dir data\canonical_web_time_norm_recommended_smoke --output data\reports\canonical_web_time_norm_recommended_smoke_runtime_readiness.json

& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\build_canonical_web_artifacts.py --input data\canonical_time_norm_recommended\deduped_events.jsonl --output-dir data\canonical_web_time_norm_recommended --write-gzip
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\check_canonical_web_runtime_readiness.py --artifact-dir data\canonical_web_time_norm_recommended --output data\reports\canonical_web_time_norm_recommended_runtime_readiness.json
```

Current full candidate compact-web result: 944,538 events, 289,791 mapped events, 378 event chunks, 95 summary shards, 2,135.05 MB raw, 405.4 MB gzip, 7.07 MB startup gzip, and `ready_for_preview`. `ready_for_primary_catalog` remains false until guarded UI parity smoke passes.

To stage and validate a guarded primary-catalog + trace-runtime payload from the candidate artifacts:

```powershell
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\stage_canonical_web_static_payload.py --artifact-dir data\canonical_web_time_norm_recommended --output-root data\canonical_web_time_norm_recommended_static_primary_trace_payload --mode primary-catalog-trace-runtime

& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\check_canonical_web_static_payload.py --payload-root data\canonical_web_time_norm_recommended_static_primary_trace_payload --static-bundle-root static_bundle --output data\reports\canonical_web_time_norm_recommended_static_payload_readiness.json
```

Current candidate payload result: 212 files, 95 summary shards, 0 event chunks, about 590.31 MB raw plus 74.8 MB gzip, status `ready`, and default `static_bundle` config still keeps canonical web artifacts disabled.

To build and validate compact web artifacts from the combined 90-decision time-normalization corpus:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\build_canonical_web_artifacts.py --input data\canonical_time_norm_recommended_plus_shorthand_plus_likely_plus_single_exact_context\deduped_events.jsonl --output-dir data\canonical_web_time_norm_combined_plus_likely_plus_single_exact_context_smoke --limit 10000 --write-gzip
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\check_canonical_web_runtime_readiness.py --artifact-dir data\canonical_web_time_norm_combined_plus_likely_plus_single_exact_context_smoke --output data\reports\canonical_web_time_norm_combined_plus_likely_plus_single_exact_context_smoke_runtime_readiness.json

& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\build_canonical_web_artifacts.py --input data\canonical_time_norm_recommended_plus_shorthand_plus_likely_plus_single_exact_context\deduped_events.jsonl --output-dir data\canonical_web_time_norm_combined_plus_likely_plus_single_exact_context --write-gzip
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\check_canonical_web_runtime_readiness.py --artifact-dir data\canonical_web_time_norm_combined_plus_likely_plus_single_exact_context --output data\reports\canonical_web_time_norm_combined_plus_likely_plus_single_exact_context_runtime_readiness.json
```

Current combined candidate compact-web result: 944,464 events, 289,717 mapped events, 288,444 trace-event-index rows, 288,443 trace segments, 378 event chunks, 95 summary shards, 2,134.9 MB raw, 405.37 MB gzip, 7.07 MB startup gzip, and `ready_for_preview`. `ready_for_primary_catalog` remains false until guarded UI parity smoke passes. The default runtime catalog and `data/canonical_full/deduped_events.jsonl` remain unchanged.

To stage and validate a guarded primary-catalog + trace-runtime payload from the combined candidate artifacts:

```powershell
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\stage_canonical_web_static_payload.py --artifact-dir data\canonical_web_time_norm_combined_plus_likely_plus_single_exact_context --output-root data\canonical_web_time_norm_combined_plus_likely_plus_single_exact_context_static_primary_trace_payload --mode primary-catalog-trace-runtime

& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\check_canonical_web_static_payload.py --payload-root data\canonical_web_time_norm_combined_plus_likely_plus_single_exact_context_static_primary_trace_payload --static-bundle-root static_bundle --output data\reports\canonical_web_time_norm_combined_plus_likely_plus_single_exact_context_static_payload_readiness.json
```

Current combined candidate payload result: 212 files, 95 summary shards, 0 event chunks, about 590.25 MB raw plus 74.8 MB gzip, status `ready`, and default `static_bundle` config still keeps canonical web artifacts disabled.

To check apply readiness for the recommended preview lane:

```powershell
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\check_time_norm_recommended_apply_readiness.py --decision-report data\reports\entity_resolution_cluster_time_norm_recommended_decision_candidates_report.json --effects-plan data\reports\entity_resolution_cluster_time_norm_recommended_accepted_effects_plan.json --preview-report data\reports\entity_resolution_cluster_time_norm_recommended_preview_apply_report.json --output-check data\reports\entity_resolution_cluster_time_norm_recommended_preview_output_check.json --policy-body-check data\reports\entity_resolution_cluster_time_norm_recommended_policy_body_preview_check.json --canonical-body-dry-run-check data\reports\entity_resolution_cluster_time_norm_recommended_canonical_body_dry_run_check.json --accepted-decision-report data\reports\entity_resolution_cluster_time_norm_recommended_acceptance_report.json --canonical-apply-output-check data\reports\entity_resolution_cluster_time_norm_recommended_canonical_apply_output_check.json --output data\reports\entity_resolution_cluster_time_norm_recommended_apply_readiness.json
```

Current readiness result: preview output, policy-body preview, the canonical-body dry-run check, the accepted-decision report, and the stream-applied output check are valid. The narrow lane now has 0 canonical-apply blockers, but runtime/static promotion is still a separate explicit step.

To review and stage the previously deferred shorthand time-normalization cases without mutating canonical outputs:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\review_time_norm_deferred_shorthand_candidates.py --packet data\reports\entity_resolution_cluster_time_norm_source_evidence_packet.json --recommendations data\reports\entity_resolution_cluster_time_norm_source_review_recommendations.json --json-output data\reports\entity_resolution_cluster_time_norm_deferred_shorthand_review.json --csv-output data\reports\entity_resolution_cluster_time_norm_deferred_shorthand_review.csv --markdown-output data\reports\entity_resolution_cluster_time_norm_deferred_shorthand_review.md

& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\promote_time_norm_deferred_shorthand_review_to_decision_candidates.py --review data\reports\entity_resolution_cluster_time_norm_deferred_shorthand_review.json --decisions-output data\reports\entity_resolution_cluster_time_norm_deferred_shorthand_decision_candidates.jsonl --report-output data\reports\entity_resolution_cluster_time_norm_deferred_shorthand_decision_candidates_report.json --reviewed-at 2026-05-22T00:00:00Z

& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\plan_entity_resolution_effects.py --validated-decisions data\reports\entity_resolution_cluster_time_norm_deferred_shorthand_decision_candidates.jsonl --output data\reports\entity_resolution_cluster_time_norm_deferred_shorthand_effects_plan.json

& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\build_entity_resolution_merge_preview_patch.py --effects-plan data\reports\entity_resolution_cluster_time_norm_deferred_shorthand_effects_plan.json --output data\reports\entity_resolution_cluster_time_norm_deferred_shorthand_merge_preview_patch.json

& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\build_time_norm_recommended_canonical_body_dry_run.py --effects-plan data\reports\entity_resolution_cluster_time_norm_deferred_shorthand_effects_plan.json --merge-patch data\reports\entity_resolution_cluster_time_norm_deferred_shorthand_merge_preview_patch.json --jsonl-output data\reports\entity_resolution_cluster_time_norm_deferred_shorthand_canonical_body_dry_run.jsonl --report-output data\reports\entity_resolution_cluster_time_norm_deferred_shorthand_canonical_body_dry_run_report.json

& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\check_time_norm_recommended_canonical_body_dry_run.py --dry-run-jsonl data\reports\entity_resolution_cluster_time_norm_deferred_shorthand_canonical_body_dry_run.jsonl --dry-run-report data\reports\entity_resolution_cluster_time_norm_deferred_shorthand_canonical_body_dry_run_report.json --output data\reports\entity_resolution_cluster_time_norm_deferred_shorthand_canonical_body_dry_run_check.json
```

Current deferred-shorthand result: 11 deferred inputs reviewed, 9 source-reviewed same-event candidates, 2 remaining deferred, 17 projected reduction, 9 decision candidates, 9 planned effects, 9 merge patches, and a valid 9-row canonical-body dry run with 0 validation errors. This lane stays non-mutating and intentionally does not stream-apply; the `19+`/`1900` insufficient-distinct-minute case and the Manhattan Beach shape-conflict case remain deferred.

To finish the independent shorthand acceptance/apply gate and build the combined 33+9 candidate corpus:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\preview_entity_resolution_apply.py --effects-plan data\reports\entity_resolution_cluster_time_norm_deferred_shorthand_effects_plan.json --deduped-events data\canonical_full\deduped_events.jsonl --output-dir data\canonical_preview_entity_resolution_cluster_time_norm_deferred_shorthand --report-output data\reports\entity_resolution_cluster_time_norm_deferred_shorthand_preview_apply_report.json

& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\check_entity_resolution_preview_output.py --preview-report data\reports\entity_resolution_cluster_time_norm_deferred_shorthand_preview_apply_report.json --preview-events data\canonical_preview_entity_resolution_cluster_time_norm_deferred_shorthand\deduped_events.jsonl --output data\reports\entity_resolution_cluster_time_norm_deferred_shorthand_preview_output_check.json

& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\accept_time_norm_deferred_shorthand_decisions.py --accepted-at 2026-05-22T00:00:00Z

& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\plan_entity_resolution_effects.py --validated-decisions data\canonical_full\entity_resolution_cluster_time_norm_deferred_shorthand_accepted_decisions.jsonl --output data\reports\entity_resolution_cluster_time_norm_deferred_shorthand_accepted_effects_plan.json

& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\apply_time_norm_recommended_canonical_decisions.py --accepted-effects-plan data\reports\entity_resolution_cluster_time_norm_deferred_shorthand_accepted_effects_plan.json --dry-run-rows data\reports\entity_resolution_cluster_time_norm_deferred_shorthand_canonical_body_dry_run.jsonl --dry-run-check data\reports\entity_resolution_cluster_time_norm_deferred_shorthand_canonical_body_dry_run_check.json --deduped-events data\canonical_full\deduped_events.jsonl --output-events data\canonical_time_norm_deferred_shorthand\deduped_events.jsonl --report-output data\reports\entity_resolution_cluster_time_norm_deferred_shorthand_canonical_apply_report.json

& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\check_time_norm_recommended_canonical_apply_output.py --apply-report data\reports\entity_resolution_cluster_time_norm_deferred_shorthand_canonical_apply_report.json --apply-events data\canonical_time_norm_deferred_shorthand\deduped_events.jsonl --dry-run-rows data\reports\entity_resolution_cluster_time_norm_deferred_shorthand_canonical_body_dry_run.jsonl --output data\reports\entity_resolution_cluster_time_norm_deferred_shorthand_canonical_apply_output_check.json

& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\combine_time_norm_accepted_decisions.py

& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\plan_entity_resolution_effects.py --validated-decisions data\canonical_full\entity_resolution_cluster_time_norm_combined_accepted_decisions.jsonl --output data\reports\entity_resolution_cluster_time_norm_combined_effects_plan.json

& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\build_entity_resolution_merge_preview_patch.py --effects-plan data\reports\entity_resolution_cluster_time_norm_combined_effects_plan.json --output data\reports\entity_resolution_cluster_time_norm_combined_merge_preview_patch.json

& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\build_time_norm_recommended_canonical_body_dry_run.py --effects-plan data\reports\entity_resolution_cluster_time_norm_combined_effects_plan.json --merge-patch data\reports\entity_resolution_cluster_time_norm_combined_merge_preview_patch.json --jsonl-output data\reports\entity_resolution_cluster_time_norm_combined_canonical_body_dry_run.jsonl --report-output data\reports\entity_resolution_cluster_time_norm_combined_canonical_body_dry_run_report.json

& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\check_time_norm_recommended_canonical_body_dry_run.py --dry-run-jsonl data\reports\entity_resolution_cluster_time_norm_combined_canonical_body_dry_run.jsonl --dry-run-report data\reports\entity_resolution_cluster_time_norm_combined_canonical_body_dry_run_report.json --output data\reports\entity_resolution_cluster_time_norm_combined_canonical_body_dry_run_check.json

& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\apply_time_norm_recommended_canonical_decisions.py --accepted-effects-plan data\reports\entity_resolution_cluster_time_norm_combined_effects_plan.json --dry-run-rows data\reports\entity_resolution_cluster_time_norm_combined_canonical_body_dry_run.jsonl --dry-run-check data\reports\entity_resolution_cluster_time_norm_combined_canonical_body_dry_run_check.json --deduped-events data\canonical_full\deduped_events.jsonl --output-events data\canonical_time_norm_recommended_plus_shorthand\deduped_events.jsonl --report-output data\reports\entity_resolution_cluster_time_norm_combined_canonical_apply_report.json

& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\check_time_norm_recommended_canonical_apply_output.py --apply-report data\reports\entity_resolution_cluster_time_norm_combined_canonical_apply_report.json --apply-events data\canonical_time_norm_recommended_plus_shorthand\deduped_events.jsonl --dry-run-rows data\reports\entity_resolution_cluster_time_norm_combined_canonical_body_dry_run.jsonl --output data\reports\entity_resolution_cluster_time_norm_combined_canonical_apply_output_check.json
```

Current combined result: 42 accepted decisions, 57 projected reduction, 42 dry-run rows, valid dry-run check, a separate stream-applied candidate corpus at `data/canonical_time_norm_recommended_plus_shorthand/deduped_events.jsonl`, 944,521 output rows, 42 replacement rows, and 0 suppressed IDs still present. `data/canonical_full/deduped_events.jsonl` remains unchanged.

To build source-row evidence for the next high-confidence time-format blocker lane:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\build_entity_resolution_likely_time_format_source_evidence_packet.py --action-packet data\reports\entity_resolution_cluster_time_blocker_action_packet.json --deduped-events data\canonical_full\deduped_events.jsonl --json-output data\reports\entity_resolution_cluster_likely_time_format_source_evidence_packet.json --csv-output data\reports\entity_resolution_cluster_likely_time_format_source_evidence_packet.csv --markdown-output data\reports\entity_resolution_cluster_likely_time_format_source_evidence_packet.md
```

Current likely-time-format evidence packet result: 16 candidate effects, 33 requested/matched canonical events, 107 candidate input IDs, 0 missing input IDs, and 17 projected reduction. This is source-evidence only and should be reviewed before any decision candidate promotion.

To validate cluster shadow-override merge-body metadata without writing a full shadow preview:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\propose_entity_resolution_canonical_merge_policy.py --merged-event-preview data\reports\entity_resolution_cluster_ai_merged_event_preview.json --shadow-override-delta data\reports\entity_resolution_cluster_ai_shadow_override_effect_impact_summary.json --apply-readiness data\reports\entity_resolution_cluster_ai_merge_readiness.json --override-subset data\reports\entity_resolution_cluster_ai_effects_plan_shadow_override_subset.json --output data\reports\entity_resolution_cluster_canonical_merge_policy_proposal.json

& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\build_entity_resolution_policy_body_preview.py --merged-event-preview data\reports\entity_resolution_cluster_ai_merged_event_preview.json --policy-proposal data\reports\entity_resolution_cluster_canonical_merge_policy_proposal.json --override-subset data\reports\entity_resolution_cluster_ai_effects_plan_shadow_override_subset.json --output data\reports\entity_resolution_cluster_policy_body_preview.json

& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\check_entity_resolution_policy_body_preview.py --policy-body-preview data\reports\entity_resolution_cluster_policy_body_preview.json --output data\reports\entity_resolution_cluster_policy_body_preview_check.json
```

This cluster policy checkpoint uses `entity_resolution_cluster_canonical_merge_policy_proposal_v1` and `entity_resolution_cluster_canonical_merge_body_policy_preview_only`. It currently selects 34 merge-body previews, skips 520 blocked/excluded previews, validates with zero invalid conflict metadata, and keeps canonical mutation, preview writing, decision creation, and auto-merge flags false. It is still not canonical apply.

To make cluster canonical-apply blocking explicit:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\check_entity_resolution_cluster_canonical_apply_readiness.py --override-subset data\reports\entity_resolution_cluster_ai_effects_plan_shadow_override_subset.json --merge-readiness data\reports\entity_resolution_cluster_ai_merge_readiness.json --policy-body-check data\reports\entity_resolution_cluster_policy_body_preview_check.json --output data\reports\entity_resolution_cluster_canonical_apply_readiness.json
```

After the cluster full shadow preview exists, pass it into the same readiness gate:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\preview_entity_resolution_apply.py --effects-plan data\reports\entity_resolution_cluster_ai_effects_plan_shadow_override_subset.json --deduped-events data\canonical_full\deduped_events.jsonl --output-dir data\canonical_preview_entity_resolution_cluster_ai_shadow_override_subset --report-output data\reports\entity_resolution_cluster_ai_shadow_override_subset_preview_apply_report.json

& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\check_entity_resolution_preview_output.py --preview-report data\reports\entity_resolution_cluster_ai_shadow_override_subset_preview_apply_report.json --preview-events data\canonical_preview_entity_resolution_cluster_ai_shadow_override_subset\deduped_events.jsonl --output data\reports\entity_resolution_cluster_ai_shadow_override_subset_preview_output_check.json

& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\check_entity_resolution_cluster_canonical_apply_readiness.py --override-subset data\reports\entity_resolution_cluster_ai_effects_plan_shadow_override_subset.json --merge-readiness data\reports\entity_resolution_cluster_ai_merge_readiness.json --policy-body-check data\reports\entity_resolution_cluster_policy_body_preview_check.json --shadow-preview-report data\reports\entity_resolution_cluster_ai_shadow_override_subset_preview_apply_report.json --shadow-output-check data\reports\entity_resolution_cluster_ai_shadow_override_subset_preview_output_check.json --output data\reports\entity_resolution_cluster_canonical_apply_readiness.json
```

Current validated cluster shadow preview applies 34 effects, blocks 0, projects a 61-event reduction, and validates 944,517 preview rows with 34 preview merge rows. The readiness report still keeps `ready_for_canonical_apply: false` with three hard blockers: no canonical apply command, 520 excluded cluster merge effects, and 538 blocking conflicts in the full compact cluster merge preview.

### Guarded canonical runtime experiment

The static bundle now contains an opt-in `canonicalWebArtifacts` config block. Keep it disabled for normal builds:

```json
"canonicalWebArtifacts": {
  "enabled": false,
  "manifestUrl": "./data/canonical_web/canonical_web_manifest.json",
  "chunkManifestUrl": "./data/canonical_web/event_chunk_manifest.json",
  "eventChunksBaseUrl": "./data/canonical_web/event_chunks/",
  "summaryManifestUrl": "./data/canonical_web/summary_manifest.json",
  "summaryShardsBaseUrl": "./data/canonical_web/summary_shards/",
  "primaryCatalog": false,
  "traceRuntime": false
}
```

For a local experiment, enable it only after copying or serving `data/canonical_web` at the configured static path. This loads the canonical manifest, lazy chunk manifest, and summary manifest, but it does not replace browser catalog shards unless `primaryCatalog` is true. The debug helpers `window.__UFO_TIMELINE_DEBUG__.loadCanonicalSummaryShard(0)`, `window.__UFO_TIMELINE_DEBUG__.loadCanonicalSummaryEvents({ maxShards: 1 })`, `window.__UFO_TIMELINE_DEBUG__.loadCanonicalPackedFullEvent(eventId)`, `window.__UFO_TIMELINE_DEBUG__.loadCanonicalTraceArtifact("trace_event_index")`, `window.__UFO_TIMELINE_DEBUG__.getCanonicalTraceArtifactRow("trace_event_index", 0)`, `window.__UFO_TIMELINE_DEBUG__.getCanonicalTraceRuntimeStatus()`, `window.__UFO_TIMELINE_DEBUG__.renderCanonicalTraceAggregatePreview({ level: "10deg" })`, and `window.__UFO_TIMELINE_DEBUG__.clearCanonicalTraceAggregatePreview()` can then test summary-shard, lazy-detail, trace-artifact loading, and full-universe trace aggregate preview rendering.

For a guarded primary-catalog prototype, set both flags to true only in a local/test config:

```json
"enabled": true,
"primaryCatalog": true,
"traceRuntime": true
```

That branch ingests canonical summary shards instead of legacy catalog shards, preserves `chunk_id`/`detail_index` for lazy full-detail hydration, and lets static traces use `trace_event_index.bin` after the artifact is loaded. If either manifest is missing or invalid, startup fails clearly instead of silently mixing legacy and canonical catalogs. The shipped default remains disabled.

To preview without modifying `static_bundle/data/app_config.json`, use the local gzip-aware preview server:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\serve_static_bundle_with_canonical_web.py --static-root static_bundle --canonical-web-dir data\canonical_web --enable-canonical-web --enable-primary-catalog --enable-trace-runtime
```

The server overlays `/data/canonical_web/` from the canonical artifact directory and serves `.gz` siblings with `Content-Encoding: gzip` when the browser advertises gzip support. It also returns an in-memory app config override for the enabled flags, so the checked-in static bundle remains safe. When `--enable-primary-catalog` is set, the preview config also points `packedPoints.metadataUrl` and `packedPoints.binaryUrl` at `/data/canonical_web/points_meta.json` and `/data/canonical_web/points.bin`. Use `--use-canonical-packed-points` to test canonical packed points without enabling the primary catalog.

`renderCanonicalTraceAggregatePreview` is deliberately labeled as full-universe LOD only. It reads `trace_aggregate_bins.bin`, honors active trace bucket visibility, and renders a separate debug canvas layer. It does not preserve arbitrary filter semantics; use `trace_event_index.bin` for exact filtered traces.

### Likely time-format candidate lane

To finish the likely-time-format review/apply lane and build the combined 33+9+16 candidate corpus:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\review_likely_time_format_candidates.py
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\promote_likely_time_format_review_to_decision_candidates.py --reviewed-at 2026-05-22T00:00:00Z
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\plan_entity_resolution_effects.py --validated-decisions data\reports\entity_resolution_cluster_likely_time_format_decision_candidates.jsonl --output data\reports\entity_resolution_cluster_likely_time_format_effects_plan.json
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\preview_entity_resolution_apply.py --effects-plan data\reports\entity_resolution_cluster_likely_time_format_effects_plan.json --deduped-events data\canonical_full\deduped_events.jsonl --output-dir data\canonical_preview_entity_resolution_cluster_likely_time_format --report-output data\reports\entity_resolution_cluster_likely_time_format_preview_apply_report.json
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\check_entity_resolution_preview_output.py --preview-report data\reports\entity_resolution_cluster_likely_time_format_preview_apply_report.json --preview-events data\canonical_preview_entity_resolution_cluster_likely_time_format\deduped_events.jsonl --output data\reports\entity_resolution_cluster_likely_time_format_preview_output_check.json
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\build_entity_resolution_merge_preview_patch.py --effects-plan data\reports\entity_resolution_cluster_likely_time_format_effects_plan.json --output data\reports\entity_resolution_cluster_likely_time_format_merge_preview_patch.json
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\build_time_norm_recommended_canonical_body_dry_run.py --effects-plan data\reports\entity_resolution_cluster_likely_time_format_effects_plan.json --merge-patch data\reports\entity_resolution_cluster_likely_time_format_merge_preview_patch.json --jsonl-output data\reports\entity_resolution_cluster_likely_time_format_canonical_body_dry_run.jsonl --report-output data\reports\entity_resolution_cluster_likely_time_format_canonical_body_dry_run_report.json
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\check_time_norm_recommended_canonical_body_dry_run.py --dry-run-jsonl data\reports\entity_resolution_cluster_likely_time_format_canonical_body_dry_run.jsonl --dry-run-report data\reports\entity_resolution_cluster_likely_time_format_canonical_body_dry_run_report.json --output data\reports\entity_resolution_cluster_likely_time_format_canonical_body_dry_run_check.json
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\accept_likely_time_format_decisions.py --accepted-at 2026-05-22T00:00:00Z
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\plan_entity_resolution_effects.py --validated-decisions data\canonical_full\entity_resolution_cluster_likely_time_format_accepted_decisions.jsonl --output data\reports\entity_resolution_cluster_likely_time_format_accepted_effects_plan.json
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\apply_time_norm_recommended_canonical_decisions.py --accepted-effects-plan data\reports\entity_resolution_cluster_likely_time_format_accepted_effects_plan.json --dry-run-rows data\reports\entity_resolution_cluster_likely_time_format_canonical_body_dry_run.jsonl --dry-run-check data\reports\entity_resolution_cluster_likely_time_format_canonical_body_dry_run_check.json --deduped-events data\canonical_full\deduped_events.jsonl --output-events data\canonical_time_norm_likely_time_format\deduped_events.jsonl --report-output data\reports\entity_resolution_cluster_likely_time_format_canonical_apply_report.json
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\check_time_norm_recommended_canonical_apply_output.py --apply-report data\reports\entity_resolution_cluster_likely_time_format_canonical_apply_report.json --apply-events data\canonical_time_norm_likely_time_format\deduped_events.jsonl --dry-run-rows data\reports\entity_resolution_cluster_likely_time_format_canonical_body_dry_run.jsonl --output data\reports\entity_resolution_cluster_likely_time_format_canonical_apply_output_check.json
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\combine_time_norm_accepted_decisions.py --output data\canonical_full\entity_resolution_cluster_time_norm_combined_plus_likely_accepted_decisions.jsonl --report-output data\reports\entity_resolution_cluster_time_norm_combined_plus_likely_accepted_decisions_report.json
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\plan_entity_resolution_effects.py --validated-decisions data\canonical_full\entity_resolution_cluster_time_norm_combined_plus_likely_accepted_decisions.jsonl --output data\reports\entity_resolution_cluster_time_norm_combined_plus_likely_effects_plan.json
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\build_entity_resolution_merge_preview_patch.py --effects-plan data\reports\entity_resolution_cluster_time_norm_combined_plus_likely_effects_plan.json --output data\reports\entity_resolution_cluster_time_norm_combined_plus_likely_merge_preview_patch.json
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\build_time_norm_recommended_canonical_body_dry_run.py --effects-plan data\reports\entity_resolution_cluster_time_norm_combined_plus_likely_effects_plan.json --merge-patch data\reports\entity_resolution_cluster_time_norm_combined_plus_likely_merge_preview_patch.json --jsonl-output data\reports\entity_resolution_cluster_time_norm_combined_plus_likely_canonical_body_dry_run.jsonl --report-output data\reports\entity_resolution_cluster_time_norm_combined_plus_likely_canonical_body_dry_run_report.json
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\check_time_norm_recommended_canonical_body_dry_run.py --dry-run-jsonl data\reports\entity_resolution_cluster_time_norm_combined_plus_likely_canonical_body_dry_run.jsonl --dry-run-report data\reports\entity_resolution_cluster_time_norm_combined_plus_likely_canonical_body_dry_run_report.json --output data\reports\entity_resolution_cluster_time_norm_combined_plus_likely_canonical_body_dry_run_check.json
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\apply_time_norm_recommended_canonical_decisions.py --accepted-effects-plan data\reports\entity_resolution_cluster_time_norm_combined_plus_likely_effects_plan.json --dry-run-rows data\reports\entity_resolution_cluster_time_norm_combined_plus_likely_canonical_body_dry_run.jsonl --dry-run-check data\reports\entity_resolution_cluster_time_norm_combined_plus_likely_canonical_body_dry_run_check.json --deduped-events data\canonical_full\deduped_events.jsonl --output-events data\canonical_time_norm_recommended_plus_shorthand_plus_likely_time_format\deduped_events.jsonl --report-output data\reports\entity_resolution_cluster_time_norm_combined_plus_likely_canonical_apply_report.json
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\check_time_norm_recommended_canonical_apply_output.py --apply-report data\reports\entity_resolution_cluster_time_norm_combined_plus_likely_canonical_apply_report.json --apply-events data\canonical_time_norm_recommended_plus_shorthand_plus_likely_time_format\deduped_events.jsonl --dry-run-rows data\reports\entity_resolution_cluster_time_norm_combined_plus_likely_canonical_body_dry_run.jsonl --output data\reports\entity_resolution_cluster_time_norm_combined_plus_likely_canonical_apply_output_check.json
```

Current likely-time-format result: 16 source-reviewed same-event candidates, 0 deferred, 17 projected reduction, 16 accepted decisions, valid 16-row dry run, a separate stream-applied corpus at `data/canonical_time_norm_likely_time_format/deduped_events.jsonl`, 944,561 output rows, 16 replacement rows, and 0 suppressed IDs still present.

Current combined+likely result: 58 accepted decisions, 74 projected reduction, valid 58-row dry run, a separate stream-applied corpus at `data/canonical_time_norm_recommended_plus_shorthand_plus_likely_time_format/deduped_events.jsonl`, 944,504 output rows, 58 replacement rows, and 0 suppressed IDs still present. `data/canonical_full/deduped_events.jsonl` remains unchanged.

### Time-conflict context evidence packet

To rebuild the review-only packet for high-risk nearby-time conflicts that include context tokens:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\build_entity_resolution_time_conflict_context_source_evidence_packet.py --analysis data\reports\entity_resolution_cluster_time_conflict_analysis.json --deduped-events data\canonical_full\deduped_events.jsonl --json-output data\reports\entity_resolution_time_conflict_context_source_evidence_packet.json --csv-output data\reports\entity_resolution_time_conflict_context_source_evidence_packet.csv --markdown-output data\reports\entity_resolution_time_conflict_context_source_evidence_packet.md
```

Current result: 8 `nearby_exact_conflict_15m_or_less_with_context` items, 24 requested/matched canonical events, 50 candidate input IDs, 0 missing input IDs, and 16 projected reduction. This packet is source evidence only. It does not approve these merges because the time-conflict lane remains high risk due coordinate-risk and identity-risk flags.

To build conservative source-review triage for that packet:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\review_time_conflict_context_candidates.py --packet data\reports\entity_resolution_time_conflict_context_source_evidence_packet.json --json-output data\reports\entity_resolution_time_conflict_context_review.json --csv-output data\reports\entity_resolution_time_conflict_context_review.csv --markdown-output data\reports\entity_resolution_time_conflict_context_review.md
```

Current result: 0 `source_review_same_event_candidate` rows and 8 `needs_more_evidence` rows with projected reduction 16. This is recommendation-only. The gate requires a time-only conflict, single source/native/date/location/coordinate/type identity, no coordinate risk, no identity-risk flags, no ambiguous/unknown/approximate tokens, compatible broad fuzzy labels, identical source summaries, and complete evidence coverage. The current 8 rows all fail at least one of those conditions, so do not promote this lane without new manual evidence.

### Single-exact context evidence packet

To rebuild the review-only packet for exact-time rows with fuzzy/context tokens:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\build_entity_resolution_single_exact_context_source_evidence_packet.py --analysis data\reports\entity_resolution_cluster_time_normalization_analysis.json --deduped-events data\canonical_full\deduped_events.jsonl --json-output data\reports\entity_resolution_single_exact_context_source_evidence_packet.json --csv-output data\reports\entity_resolution_single_exact_context_source_evidence_packet.csv --markdown-output data\reports\entity_resolution_single_exact_context_source_evidence_packet.md
```

Current result: 85 `single_exact_minute_with_context_tokens` items, 203 requested/matched canonical events, 506 candidate input IDs, 0 missing input IDs, and 118 projected reduction. Hydrated evidence shows 84 time-only conflict items and 1 non-time conflict item. This packet is source evidence only; a later compatibility review must reject incompatible fuzzy/context tokens before any decision candidate promotion.

To build the conservative source-review recommendations from that packet:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\review_single_exact_context_candidates.py --packet data\reports\entity_resolution_single_exact_context_source_evidence_packet.json --json-output data\reports\entity_resolution_single_exact_context_review.json --csv-output data\reports\entity_resolution_single_exact_context_review.csv --markdown-output data\reports\entity_resolution_single_exact_context_review.md
```

Current result: 32 `source_review_same_event_candidate` rows with projected reduction 40, and 53 `needs_more_evidence` rows with projected reduction 78. This is recommendation-only; it creates no decisions, accepted records, preview output, or candidate corpus. Do not promote these rows until a separate explicit decision-candidate gate exists and is reviewed.

To promote and gate only the 32 source-reviewed rows into a separate accepted-decision/candidate-corpus lane:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\promote_single_exact_context_review_to_decision_candidates.py --reviewed-at 2026-05-22T00:00:00Z
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\plan_entity_resolution_effects.py --validated-decisions data\reports\entity_resolution_single_exact_context_decision_candidates.jsonl --output data\reports\entity_resolution_single_exact_context_effects_plan.json
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\preview_entity_resolution_apply.py --effects-plan data\reports\entity_resolution_single_exact_context_effects_plan.json --deduped-events data\canonical_full\deduped_events.jsonl --output-dir data\canonical_preview_entity_resolution_single_exact_context --report-output data\reports\entity_resolution_single_exact_context_preview_apply_report.json
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\check_entity_resolution_preview_output.py --preview-report data\reports\entity_resolution_single_exact_context_preview_apply_report.json --preview-events data\canonical_preview_entity_resolution_single_exact_context\deduped_events.jsonl --output data\reports\entity_resolution_single_exact_context_preview_output_check.json
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\build_entity_resolution_merge_preview_patch.py --effects-plan data\reports\entity_resolution_single_exact_context_effects_plan.json --output data\reports\entity_resolution_single_exact_context_merge_preview_patch.json
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\build_time_norm_recommended_canonical_body_dry_run.py --effects-plan data\reports\entity_resolution_single_exact_context_effects_plan.json --merge-patch data\reports\entity_resolution_single_exact_context_merge_preview_patch.json --jsonl-output data\reports\entity_resolution_single_exact_context_canonical_body_dry_run.jsonl --report-output data\reports\entity_resolution_single_exact_context_canonical_body_dry_run_report.json
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\check_time_norm_recommended_canonical_body_dry_run.py --dry-run-jsonl data\reports\entity_resolution_single_exact_context_canonical_body_dry_run.jsonl --dry-run-report data\reports\entity_resolution_single_exact_context_canonical_body_dry_run_report.json --output data\reports\entity_resolution_single_exact_context_canonical_body_dry_run_check.json
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\accept_single_exact_context_decisions.py --accepted-at 2026-05-22T00:00:00Z
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\plan_entity_resolution_effects.py --validated-decisions data\canonical_full\entity_resolution_single_exact_context_accepted_decisions.jsonl --output data\reports\entity_resolution_single_exact_context_accepted_effects_plan.json
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\apply_time_norm_recommended_canonical_decisions.py --accepted-effects-plan data\reports\entity_resolution_single_exact_context_accepted_effects_plan.json --dry-run-rows data\reports\entity_resolution_single_exact_context_canonical_body_dry_run.jsonl --dry-run-check data\reports\entity_resolution_single_exact_context_canonical_body_dry_run_check.json --deduped-events data\canonical_full\deduped_events.jsonl --output-events data\canonical_time_norm_single_exact_context\deduped_events.jsonl --report-output data\reports\entity_resolution_single_exact_context_canonical_apply_report.json
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\check_time_norm_recommended_canonical_apply_output.py --apply-report data\reports\entity_resolution_single_exact_context_canonical_apply_report.json --apply-events data\canonical_time_norm_single_exact_context\deduped_events.jsonl --dry-run-rows data\reports\entity_resolution_single_exact_context_canonical_body_dry_run.jsonl --output data\reports\entity_resolution_single_exact_context_canonical_apply_output_check.json
```

Current single-exact/context result: 32 decision candidates, 53 skipped review rows, 40 projected reduction, valid preview output, valid 32-row canonical-body dry run, 32 accepted decisions, a separate stream-applied corpus at `data/canonical_time_norm_single_exact_context/deduped_events.jsonl`, 944,538 output rows, 32 replacement rows, and 0 suppressed IDs still present. The acceptance gate records modifier tokens but requires clean exact-clock evidence from unmodified tokens.

To combine this lane with the earlier 33+9+16 accepted decisions:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\combine_time_norm_accepted_decisions.py --output data\canonical_full\entity_resolution_cluster_time_norm_combined_plus_likely_plus_single_exact_context_accepted_decisions.jsonl --report-output data\reports\entity_resolution_cluster_time_norm_combined_plus_likely_plus_single_exact_context_accepted_decisions_report.json
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\plan_entity_resolution_effects.py --validated-decisions data\canonical_full\entity_resolution_cluster_time_norm_combined_plus_likely_plus_single_exact_context_accepted_decisions.jsonl --output data\reports\entity_resolution_cluster_time_norm_combined_plus_likely_plus_single_exact_context_effects_plan.json
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\build_entity_resolution_merge_preview_patch.py --effects-plan data\reports\entity_resolution_cluster_time_norm_combined_plus_likely_plus_single_exact_context_effects_plan.json --output data\reports\entity_resolution_cluster_time_norm_combined_plus_likely_plus_single_exact_context_merge_preview_patch.json
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\build_time_norm_recommended_canonical_body_dry_run.py --effects-plan data\reports\entity_resolution_cluster_time_norm_combined_plus_likely_plus_single_exact_context_effects_plan.json --merge-patch data\reports\entity_resolution_cluster_time_norm_combined_plus_likely_plus_single_exact_context_merge_preview_patch.json --jsonl-output data\reports\entity_resolution_cluster_time_norm_combined_plus_likely_plus_single_exact_context_canonical_body_dry_run.jsonl --report-output data\reports\entity_resolution_cluster_time_norm_combined_plus_likely_plus_single_exact_context_canonical_body_dry_run_report.json
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\check_time_norm_recommended_canonical_body_dry_run.py --dry-run-jsonl data\reports\entity_resolution_cluster_time_norm_combined_plus_likely_plus_single_exact_context_canonical_body_dry_run.jsonl --dry-run-report data\reports\entity_resolution_cluster_time_norm_combined_plus_likely_plus_single_exact_context_canonical_body_dry_run_report.json --output data\reports\entity_resolution_cluster_time_norm_combined_plus_likely_plus_single_exact_context_canonical_body_dry_run_check.json
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\apply_time_norm_recommended_canonical_decisions.py --accepted-effects-plan data\reports\entity_resolution_cluster_time_norm_combined_plus_likely_plus_single_exact_context_effects_plan.json --dry-run-rows data\reports\entity_resolution_cluster_time_norm_combined_plus_likely_plus_single_exact_context_canonical_body_dry_run.jsonl --dry-run-check data\reports\entity_resolution_cluster_time_norm_combined_plus_likely_plus_single_exact_context_canonical_body_dry_run_check.json --deduped-events data\canonical_full\deduped_events.jsonl --output-events data\canonical_time_norm_recommended_plus_shorthand_plus_likely_plus_single_exact_context\deduped_events.jsonl --report-output data\reports\entity_resolution_cluster_time_norm_combined_plus_likely_plus_single_exact_context_canonical_apply_report.json
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\check_time_norm_recommended_canonical_apply_output.py --apply-report data\reports\entity_resolution_cluster_time_norm_combined_plus_likely_plus_single_exact_context_canonical_apply_report.json --apply-events data\canonical_time_norm_recommended_plus_shorthand_plus_likely_plus_single_exact_context\deduped_events.jsonl --dry-run-rows data\reports\entity_resolution_cluster_time_norm_combined_plus_likely_plus_single_exact_context_canonical_body_dry_run.jsonl --output data\reports\entity_resolution_cluster_time_norm_combined_plus_likely_plus_single_exact_context_canonical_apply_output_check.json
```

Current combined result: 90 accepted decisions, 114 projected reduction, valid 90-row dry run, a separate stream-applied corpus at `data/canonical_time_norm_recommended_plus_shorthand_plus_likely_plus_single_exact_context/deduped_events.jsonl`, 944,464 output rows, 90 replacement rows, and 0 suppressed IDs still present. `data/canonical_full/deduped_events.jsonl` remains unchanged.

To refresh the report-only ER lane comparison with the combined time-normalization corpus metrics:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\summarize_entity_resolution_lanes.py --output data\reports\entity_resolution_lane_comparison.json
```

Current comparison adds `time_norm_combined_*` fields to the cluster lane: 90 combined decisions, projected reduction 114, valid 90-row body dry run, valid 944,464-row candidate corpus, 90 replacement rows, and 0 suppressed IDs still present. This is report-only; it does not promote the candidate corpus to runtime/default data.

### Medium time-or-identity manual-review lane

To rebuild the review-only report for medium-risk manual-review replacements whose only flags are `same_source_multiple_native_ids` and optionally `time_raw_conflict`:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\review_manual_review_medium_time_or_identity_only.py
```

Current result: 196 target components, 523 / 523 source component rows found, 71 `manual_identity_review_candidate` rows, 125 `needs_deeper_identity_review` rows, and 115 projected reduction in the candidate bucket. This lane remains review-only because every row contains same-source multiple native IDs; do not generate accepted decisions or a candidate corpus from it without a separate manual identity evidence gate.

### Medium body-text-only manual-review lane

To rebuild the review-only report for medium-risk manual-review replacements whose only flags are `description_text_conflict` and `summary_text_conflict`:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\review_manual_review_medium_body_text_only.py
```

Current result: 35 target components, 70 / 70 source component rows found, 29 `body_variant_review_candidate` rows, 6 `needs_deeper_body_review` rows, and 29 projected reduction in the candidate bucket. This lane remains review-only because body text differences can preserve distinct narrative details; do not apply it without a separate explicit body-variant evidence gate.

### Medium classification-only manual-review lane

To rebuild the review-only report for medium-risk manual-review replacements whose only flag is `type_conflict`:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\review_manual_review_medium_classification_only.py
```

Current result: 8 target components, 23 / 23 source component rows found, 3 `classification_variant_review_candidate` rows, 5 `needs_deeper_classification_review` rows, and 4 projected reduction in the candidate bucket. This lane remains review-only because broad UFOCAT type-code differences such as `2|5`, `3|5`, and `4|5` need an explicit classification-code equivalence table before acceptance.

### Medium location-text-mixed manual-review lane

To rebuild the review-only report for medium-risk manual-review replacements whose flags are limited to `location_text_conflict` and optional `time_raw_conflict`:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\review_manual_review_medium_location_text_mixed.py
```

Current result: 4 target components, 3 `location_variant_review_candidate` rows, 1 `needs_deeper_location_review` row, and 3 projected reduction in the candidate bucket. This lane remains review-only because time conflicts such as `0230|02+` still need manual interpretation even when location punctuation/spacing normalizes cleanly.

### Remaining manual-review lane action matrix

To rebuild the action matrix for all manual-review replacement audit sublanes:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\summarize_manual_review_remaining_lane_actions.py
```

Current result: 11 sublanes summarized, 1,091 accepted-sidecar preview components, 818 parser-backed partial sidecar components, 243 review-only packet components, 323 unreviewed mixed-risk components, and 37 high-risk review-packet-only components. This report is a guardrail; it does not approve or apply any remaining lane.

### Medium coordinate-span manual-review lane

To rebuild the review-only evidence packet for medium-risk replacements with `coordinate_span_gt_5km`:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\review_manual_review_medium_coordinate_span.py
```

Current result: 148 target components, 391 / 391 source component rows found, 54 `coordinate_review_candidate` rows, 94 `needs_deeper_coordinate_review` rows, and 81 projected reduction in the candidate bucket. This remains review-only because coordinate variance can be geocoding noise or genuinely distinct nearby sightings.

### Medium identity-mixed manual-review lane

To rebuild the review-only packet for medium-risk replacements with `same_source_multiple_native_ids` mixed with body/type/location conflicts:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\review_manual_review_medium_identity_mixed.py
```

Current result: 22 target components, all 22 `needs_deeper_identity_mixed_review`. This lane intentionally has no candidate bucket because multiple native IDs mixed with body/type/location conflicts require manual source identity review.

### Medium classification-mixed manual-review lane

To rebuild the review-only packet for medium-risk replacements whose flags are limited to time/type/shape conflicts:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\review_manual_review_medium_classification_mixed.py
```

Current result: 68 target components, all 68 `needs_deeper_classification_mixed_review`. This lane intentionally has no candidate bucket because time conflicts combined with type/shape conflicts need classification-code and time evidence review.

### Medium body-text-mixed manual-review lane

To rebuild the review-only packet for medium-risk replacements with body text conflicts mixed with location/time/type conflicts:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\review_manual_review_medium_body_text_mixed.py
```

Current result: 85 target components, all 85 `needs_deeper_body_mixed_review`. After this packet, all medium manual-review audit sublanes have either a sidecar preview lane or a review-only packet; the only remaining non-medium bucket is the high-risk coordinate-span review-packet lane.

### High coordinate-span manual-review lane

To rebuild the dedicated high-risk coordinate-span packet:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\review_manual_review_high_coordinate_span.py
```

Current result: 37 target components, all 37 `needs_deeper_high_coordinate_review`. The action matrix now has no unreviewed mixed-risk components; remaining automated promotion is still blocked by manual review and runtime-promotion review.

To rebuild the report-only high coordinate-span triage digest:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\build_high_coordinate_span_triage_digest.py
```

Current result: `data/reports/high_coordinate_span_triage_digest.json` and `.md` summarize 37 blocked high-coordinate review items, 75 projected event reduction behind the blocked queue, span km min/median/max of 50.038 / 116.815 / 668.336, and keep `ready_for_canonical_apply=false` with canonical outputs unchanged.

To rebuild the report-only mixed medium manual-review triage digest:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\build_mixed_medium_review_triage_digest.py
```

Current result: `data/reports/mixed_medium_review_triage_digest.json` and `.md` summarize the three mixed medium manual-review lanes: identity mixed, classification mixed, and body-text mixed. It records 175 reviewed items, 223 projected event reduction behind blocked queues, and keeps `ready_for_canonical_apply=false` with canonical outputs unchanged.

### Guarded canonical primary-catalog trace-runtime smoke

To run the guarded 10k canonical-web smoke without changing checked-in defaults:

```powershell
& 'C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe' -ExecutionPolicy Bypass -File 'scripts\smoke_guarded_canonical_preview_cdp.ps1' -CanonicalWebDir 'data\canonical_web_time_norm_plus_manual_review_ai_low_risk_plus_medium_time_preview_smoke' -PreviewPort 8150 -DebugPort 9384 -TimeoutSeconds 120 -StartupAttempts 3
```

Current result: passed with `catalogSource=canonical_web`, `traceMode=static`, `trace_event_index` cached, 2,533 trace rows, and checked-in defaults unchanged.

To run the full staged sidecar payload smoke:

```powershell
& 'C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe' -ExecutionPolicy Bypass -File 'scripts\smoke_guarded_canonical_preview_cdp.ps1' -CanonicalWebDir 'data\canonical_web_time_norm_plus_manual_review_ai_low_risk_plus_medium_time_preview_static_primary_trace_payload\data\canonical_web' -PreviewPort 8162 -DebugPort 9392 -TimeoutSeconds 900 -StartupAttempts 3
```

Current result: passed on fresh ports with `catalogSource=canonical_web`, `traceMode=static`, `trace_event_index` cached, 286,582 trace rows, budgeted static trace rendering, 11,135 rendered/source segments, and checked-in defaults unchanged.

To smoke a temporary static root whose `data/app_config.json` already has the promoted canonical flags, add `-UseStaticAppConfig`. This disables preview-server config injection and fails if the static config itself is not promoted:

```powershell
& 'C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe' -ExecutionPolicy Bypass -File 'scripts\smoke_guarded_canonical_preview_cdp.ps1' -StaticRoot '.tmp\promoted_static_bundle' -CanonicalWebDir '.tmp\promoted_static_bundle\data\canonical_web' -PreviewPort 8170 -DebugPort 9400 -TimeoutSeconds 900 -StartupAttempts 3 -UseStaticAppConfig
```

Current full-sidecar static-config smoke result: passed from `.tmp\promoted_static_bundle_full_smoke` on `8175/9405` with `catalogSource=canonical_web`, startup `Ready`, `trace_event_index` cached, 286,582 trace rows, budgeted static trace rendering, 11,135 rendered/source segments, and checked-in defaults unchanged.

Important implementation notes:

- `scripts/serve_static_bundle_with_canonical_web.py` streams static files in chunks and can inject guarded canonical-web/primary-catalog/trace-runtime config for local preview only.
- `scripts/smoke_guarded_canonical_preview_cdp.ps1` normalizes duplicate Windows `PATH`/`Path` environment keys before launching child processes and captures preview-server stdout/stderr on app-config fetch failures.
- `scripts/serve_static_bundle_with_canonical_web.py` accepts UTF-8 BOM `app_config.json` files so temporary promoted configs written by Windows tooling can be smoked.
- `webapp/static_public/app.js` retries canonical summary shard JSON and canonical packed trace metadata/binary fetches up to 3 attempts for transient request, decode, or 5xx failures.
- One full-smoke attempt on `8156/9386` failed before catalog loading with `net::ERR_CONNECTION_RESET` on baseline vendor/CSS assets; rerunning on fresh ports passed. Prefer fresh preview/debug ports when repeating browser smoke.
- This smoke does not promote canonical primary catalog defaults; runtime promotion remains an explicit separate decision.

After a passed guarded smoke, refresh the preview/default-promotion gate:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\summarize_runtime_integration_readiness.py
```

Current result: `preview_ready_default_blocked`, `ready_for_preview_package=true`, `ready_for_default_promotion=false`, with blockers limited to the intentionally unpromoted primary catalog and preview-only manual-review mutation policy.

Promotion checklist: `docs/CANONICAL_PRIMARY_PROMOTION_PLAN.md`.

### Remaining Lower Time-Format Review Lane

To rebuild the report-only source evidence packet for remaining lower-risk time-format blockers not already accepted by the combined time-normalization sidecar:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\build_entity_resolution_remaining_lower_time_format_source_evidence_packet.py
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\review_remaining_lower_time_format_candidates.py
```

Current result: 15 source-evidence items, 44 / 44 canonical events found, 115 / 115 candidate input IDs covered, 6 `source_review_same_event_candidate` rows with projected reduction 12, and 9 deferred rows with projected reduction 17. This lane is report-only; it does not create accepted decisions, apply merges, mutate canonical outputs, or change runtime defaults.

To write a separate decision-candidate file for only the 6 source-reviewed rows, without accepting or applying them:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\promote_remaining_lower_time_format_review_to_decision_candidates.py
```

Current decision-candidate result: 6 candidate records, 9 skipped deferred rows, projected reduction 12, `ready_for_canonical_apply=false`, canonical outputs unchanged, and no preview sidecar written.

To audit that candidate gate against the source review, its report, and already accepted combined time-normalization decisions:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\check_remaining_lower_time_format_decision_candidates.py
```

Current check result: valid, 6 candidate rows, 9 deferred rows preserved, 90 accepted combined decisions checked, no accepted-decision overlap, no deferred-row overlap, `ready_for_canonical_apply=false`, and canonical outputs unchanged.

### Canonical Promotion Decision Packet

To rebuild the report-only packet that summarizes the runtime evidence and the explicit remaining approval choices:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\build_canonical_promotion_decision_packet.py
```

Current result: `data/reports/canonical_promotion_decision_packet.json` and `.md` report `preview_ready_default_blocked`, `ready_for_preview_package=true`, `ready_for_default_promotion=false`, default runtime config unchanged, and canonical outputs unchanged. The packet records three explicit choices: approve default canonical runtime, approve canonical mutation as a separate future contract, or defer and continue report-only work.

To rebuild the report-only promotion/rollback gap audit:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\build_canonical_promotion_rollback_gap_audit.py
```

Current result: `data/reports/canonical_promotion_rollback_gap_audit.json` and `.md` compare checked-in disabled canonical flags against candidate promoted flags, summarize sidecar payload sizes, list rollback steps, preserve `ready_for_default_promotion=false`, and confirm default runtime config plus canonical outputs are unchanged.

To rebuild the final deferred-work queue / approval-boundary report:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\build_deferred_work_queue.py
```

Current result: `data/reports/deferred_work_queue.json` and `.md` split remaining work into `requires_default_runtime_approval`, `requires_canonical_mutation_or_apply_approval`, and `safe_report_only_backlog`. The safe report-only backlog now records the high-coordinate, mixed-medium, and static-host payload reports as `completed_report_only`. It preserves `preview_ready_default_blocked`, keeps default runtime config unchanged, and confirms canonical outputs are unchanged.

To rebuild the report-only static host payload risk summary:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\build_static_host_payload_risk_report.py
```

Current result: `data/reports/static_host_payload_risk_report.json` and `.md` compare the lean and full-detail canonical web payloads, flag the full-detail payload as high static-host risk at about 405.41 gzip MB, and keep `ready_for_default_promotion=false`, default runtime config unchanged, and canonical outputs unchanged.

### Current Promoted Canonical Runtime

The shipped `static_bundle` is now promoted to the canonical web runtime:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\check_canonical_web_static_payload.py --payload-root static_bundle --static-bundle-root static_bundle --expected-canonical-config promoted --output data\reports\canonical_web_static_payload_promoted_readiness.json
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\summarize_runtime_integration_readiness.py
```

Current expected results:

```text
static payload status: ready
runtime gate status: default_promoted_ready
canonical web files: 968
event chunks: 378
trace rows: 286,570
canonical outputs mutated: false
```

Actual promoted-bundle browser smoke command:

```powershell
& 'C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe' -ExecutionPolicy Bypass -File 'scripts\smoke_guarded_canonical_preview_cdp.ps1' -StaticRoot 'static_bundle' -CanonicalWebDir 'static_bundle\data\canonical_web' -PreviewPort 8181 -DebugPort 9411 -TimeoutSeconds 900 -StartupAttempts 3 -UseStaticAppConfig
```

Current smoke result: passed with `catalogSource=canonical_web`, `startupPhase=Ready`, `trace_event_index` cached, `rowCount=286570`, and `11135 / 11135` rendered/source segments.

### Canonical Mutation Contract

The approved runtime payload is still a sidecar-derived runtime payload. It does not rewrite `data/canonical_full/deduped_events.jsonl`.

To rebuild the report-only mutation contract:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\build_canonical_mutation_contract.py
```

Current result: `data/reports/canonical_mutation_contract.json` reports current canonical events `944578`, promoted preview events `942518`, whole-chain reduction `2060`, latest remaining-lower reduction `12`, `contract_valid=true`, `ready_for_direct_canonical_overwrite=false`, and `canonical_outputs_mutated=false`.

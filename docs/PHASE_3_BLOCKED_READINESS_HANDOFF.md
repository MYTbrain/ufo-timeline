# Phase 3 Blocked Readiness Handoff

## Current State

The large-catalog static runtime path is preview-ready but intentionally not default-promotable.

Current aggregate gate:

```text
data/reports/runtime_integration_readiness_gate.json
status: preview_ready_default_blocked
ready_for_preview_package: true
ready_for_default_promotion: false
failed_checks: none
```

This means the offline/static artifacts and report gates are internally consistent, but the app must not be switched to canonical defaults yet.

## Preview-Ready Inputs

The following reports/artifacts are current:

```text
data/reports/canonical_web_runtime_readiness.json
data/reports/canonical_web_static_payload_readiness.json
data/reports/canonical_web_static_payload_full_readiness.json
data/reports/manual_review_packet.json
data/reports/manual_review_packet.csv
data/reports/manual_review_packet.md
data/reports/manual_review_packet_readiness.json
data/reports/canonical_facet_readiness.json
data/reports/runtime_integration_readiness_gate.json
data/reports/duplicate_candidate_cluster_summary.json
data/reports/expanded_dedupe_opportunity_report.json
data/reports/dedupe_benchmark_gap_summary.json
```

The manual-review packet exports all 5,001 queue items and remains review-only:

```text
canonical_outputs_mutated: false
decisions_created: false
decision_outputs_created: false
auto_merge_performed: false
```

The facet readiness report is also report-only. It confirms required counted facets are present and flags high-unknown facets before UI exposure.

The dedupe opportunity reports are also report-only:

```text
current deduped events: 944578
current exact duplicate reduction: 26537
candidate queue pair edges: 5000
candidate queue connected clusters: 2561
expanded conservative projected additional reduction: 49627
expanded aggressive projected additional reduction: 76360
projected event count after conservative review: 894951
projected event count after aggressive review: 868218
UFOSINT screenshot benchmark: 618316
remaining gap after conservative estimate: 276635
remaining gap after exploratory estimate: 273978
remaining gap after aggressive estimate: 249902
canonical outputs mutated: false
preview outputs written: false
decisions created: false
auto merge performed: false
```

The RONGERES screenshot pattern is represented in tests as same source family, exact day, specific time, same normalized location, and nearby trusted coordinates with different source-native IDs.

The first over-broad source-URL estimate was corrected before saving the current report. Generic labels such as `UFOReportCtr` are not treated as specific URLs.

## Blockers

Browser visual/runtime smoke is still blocked in this environment:

```text
Headless Chrome/Edge CDP exits before exposing a target.
The Codex in-app browser blocks localhost navigation with ERR_BLOCKED_BY_CLIENT.
```

Manual-review mutation is also intentionally blocked:

```text
AI-assisted decisions and a plan-only effects report exist.
Manual-review apply remains preview-only.
Promotion/mutation mode is not implemented.
```

Dedupe expansion is intentionally blocked from mutation:

```text
Expanded opportunity reports estimate review work only.
They do not create decisions or apply merges.
The 618k UFOSINT screenshot count is an external benchmark, not an approved target.
```

## Do Not Promote Yet

Do not change checked-in defaults until browser smoke passes:

```json
"canonicalWebArtifacts": {
  "enabled": false,
  "primaryCatalog": false,
  "traceRuntime": false,
  "filteredTraceAggregation": false
}
```

Do not treat packet suggestions as applied outcomes. The AI-assisted decisions file is separate and explicitly marked conservative/reviewed by `codex_ai_conservative_review_v1`.

Do not run full preview apply against `data/canonical_full/deduped_events.jsonl` until the apply path is redesigned to stream or patch outputs. The current apply script deep-copies the full 5.9GB corpus.

Do not add a backend, GPU renderer, or runtime data mutation as a workaround for the remaining gate.

## Commands To Reproduce Current Gates

```powershell
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\build_manual_review_packet.py --queue data\canonical_full\manual_review_queue.jsonl --json-output data\reports\manual_review_packet.json --csv-output data\reports\manual_review_packet.csv --markdown-output data\reports\manual_review_packet.md

& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\check_manual_review_packet.py --queue data\canonical_full\manual_review_queue.jsonl --packet data\reports\manual_review_packet.json --csv data\reports\manual_review_packet.csv --markdown data\reports\manual_review_packet.md --output data\reports\manual_review_packet_readiness.json

& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\summarize_canonical_facet_readiness.py --scan-summary-shards --output data\reports\canonical_facet_readiness.json

& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\summarize_runtime_integration_readiness.py --manual-review-packet-readiness data\reports\manual_review_packet_readiness.json --canonical-facet-readiness data\reports\canonical_facet_readiness.json --output data\reports\runtime_integration_readiness_gate.json

& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\summarize_duplicate_candidate_clusters.py --candidates data\canonical_full\duplicate_candidates.jsonl --output data\reports\duplicate_candidate_cluster_summary.json

& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\summarize_expanded_dedupe_opportunities.py --source-records data\canonical_full\source_records.jsonl --deduped-events data\canonical_full\deduped_events.jsonl --output data\reports\expanded_dedupe_opportunity_report.json

& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\summarize_dedupe_benchmark_gap.py --output data\reports\dedupe_benchmark_gap_summary.json
```

AI-assisted manual-review commands:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\ai_review_manual_review_queue.py --queue data\canonical_full\manual_review_queue.jsonl --decisions-output data\canonical_full\manual_review_decisions_ai_assisted.jsonl --applied-output data\canonical_full\manual_review_applied_decisions_ai_assisted.jsonl --report-output data\reports\manual_review_ai_decisions_report.json

& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\plan_manual_review_effects.py --queue data\canonical_full\manual_review_queue.jsonl --applied-decisions data\canonical_full\manual_review_applied_decisions_ai_assisted.jsonl --output data\reports\manual_review_ai_effects_plan.json

& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\summarize_manual_review_effect_impact.py --effects-plan data\reports\manual_review_ai_effects_plan.json --deduped-events data\canonical_full\deduped_events.jsonl --output data\reports\manual_review_ai_effect_impact_summary.json
```

Full verification command:

```powershell
$env:PYTHONPATH='C:\Users\jarod\Desktop\UFO Timeline map tool\.python_packages;C:\Users\jarod\Desktop\UFO Timeline map tool'
& 'C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest
```

Latest result:

```text
127 passed
```

## Next Unblocked Work

Once browser smoke is available:

1. Serve `static_bundle` with `scripts/serve_static_bundle_with_canonical_web.py`.
2. Enable preview-only canonical flags through the preview server, not checked-in config.
3. Smoke primary catalog startup, filters, map points, Results, details hydration, static traces, and filtered trace aggregation.
4. Keep default promotion blocked until the visual/runtime smoke passes.

Once the full apply path is redesigned for the 5.9GB corpus:

1. Use the AI-assisted decisions/effects plan as the first candidate input.
2. Run preview-only manual-review apply with streaming or patch-based output.
3. Review shadow outputs before any future mutation design.

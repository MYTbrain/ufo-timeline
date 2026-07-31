# UFO Timeline Worklog

## 2026-05-21 Phase 0 Baseline

Baseline static app state captured before large CSV ingestion work:

- `normalized_events`: 54,751
- `mapped_events`: 34,227
- `unresolved_locations`: 25,270
- `points.bin` schema: 2
- `points.bin` rows: 34,227
- `points.bin` bytes per row: 72
- Catalog shards: about 24.77 MB
- Event chunks: about 155.56 MB
- `static_bundle.zip`: 30,718,770 bytes at baseline check

Relevant scale work already present:

- Packed point schema v2.
- Packed startup heatmap preview.
- Packed-backed point/cluster/heatmap path after parity checks.
- Ordered work-conserving catalog shard fetch+ingest.
- Slimmed startup catalog summaries.
- Lazy full event chunks preserved.

Baseline checks run:

- `python -m py_compile scripts/audit_ufo_csv_sources.py`
- `node --check webapp/static_public/app.js`
- `node tests/test_frontend_utils.mjs`

## 2026-05-21 Phase 1 Source Field Inventory

Revised the long-run handoff into:

- `docs/UFO_TIMELINE_CODEX_LONG_RUN_HANDOFF_REVISED.md`

Upgraded the source audit utility:

- `scripts/audit_ufo_csv_sources.py`

The audit now emits:

- `data/reports/ufo_csv_audit.json`
- `data/canonical/source_field_inventories/*.json`
- `data/canonical/source_column_mapping.json`
- `data/canonical/unmapped_fields_report.json`
- `data/canonical/unmapped_fields_report.csv`

Audit results:

- Source files scanned: 7
- Raw rows scanned: 1,268,745
- Exact subset drops recommended: `mufon.csv`, `nuforc.csv`
- Estimated rows after exact subset pruning: 971,115
- Non-empty source-specific columns requiring preservation or mapping review: 129
- Mapping action counts: 73 canonical, 21 source claim, 129 source specific, 18 empty

Verified exact subset pairs:

- `mufon.csv` is a left subset of `mufonpy.csv`; `mufonpy.csv` has 546 additional rows.
- `nuforc.csv` is a left subset of `nuforcpy.csv`; `nuforcpy.csv` has 820 additional rows.

Important adapter gaps identified by review:

- Existing `raw_fields` preservation is partial and does not preserve original row text, header order, dialect, overflow columns, or parse anomalies.
- Source claims are not yet modeled separately.
- Exact subset handling in canonical build is hardcoded and should be verified from audit results.
- Dedupe is conservative but lacks adjudication/review decision state.
- Canonical compatibility output exists in parallel and is not yet integrated into the main static bundle path.

## 2026-05-21 Phase 2 Adapter Hardening Started

Implemented first provenance-preservation improvements:

- `CanonicalInputRecord` now carries complete raw source row preservation fields.
- Base CSV adapter now preserves raw header, row values, empty fields, overflow columns, missing columns, row/header column counts, and anomaly labels.
- Source row hashes now include overflow columns when present.
- `compact_raw_fields()` no longer leaks adapter-internal overflow keys.
- Canonical builder now emits `source_claims.jsonl`.
- Source claims currently cover adapter-explicit date, time, location, shape, type, duration, source URL, reported date, and posted date fields.

Tests and smoke checks:

- `python -m py_compile parser/canonical_schema.py parser/csv_sources/base.py scripts/audit_ufo_csv_sources.py`
- `pytest tests/test_canonical_import.py tests/test_canonical_export.py`: 11 passed
- Limited canonical build smoke with `--limit-per-source 25`
- Smoke output: 125 source records, 682 source claims, 121 normalized events, 23 mapped events
- Full `pytest`: 56 passed

Remaining Phase 2 work:

- Generate source claims from all high-value source-specific fields using `source_column_mapping.json`.
- Add field-level column accounting tests.
- Make exact subset skipping depend on verified audit results, not only hardcoded filenames.
- Add import failure logging.
- Add dedupe adjudication/review state.

## 2026-05-21 Phase 2 Adapter Hardening Continued

Extended the canonical builder:

- `scripts/build_canonical_ufo_dataset.py` now accepts `--source-column-mapping` and emits mapping-derived source claims for columns marked `source_claim`.
- `scripts/build_canonical_ufo_dataset.py` now accepts `--audit-report` and uses verified `left_subset_of_right` audit evidence for exact-subset pruning when available.
- `canonical_import_report.json` now records the source file plan, audit evidence, source claim origin counts, column-accounting summary, import-failure report path, and manual-review queue summary.
- `canonical_column_accounting.json` reports mapping action counts, unmapped headers, source-specific preserved values, source-claim values, and row-shape anomalies by source file.
- `canonical_import_failures.json` is emitted even when empty.
- `manual_review_queue.jsonl` now includes fuzzy duplicate candidates and row/import/accounting anomalies as explicit non-auto-merge review items.
- `manual_review_decision_schema.json` provides the adjudication schema for later human decisions.

Limited canonical build smoke with audit and source-column mapping enabled:

- Source file plan: `ufo_csv_audit`
- Source records: 125
- Source claims: 755
- Adapter-explicit source claims: 682
- Mapping-derived source claims: 73
- Deduped events: 121
- Normalized events: 121
- Mapped events: 23
- Duplicate candidates: 3
- Manual review queue items: 3
- Column accounting: 0 unmapped headers, 582 source-specific non-empty values preserved, 0 row-shape anomalies in the 25-row/source smoke sample

Verification:

- `python -m py_compile scripts/build_canonical_ufo_dataset.py parser/canonical_schema.py parser/csv_sources/base.py tests/test_canonical_import.py`
- `pytest tests/test_canonical_import.py`: 10 passed
- Full `pytest`: 58 passed

Remaining work:

- Run and inspect a full canonical build when ready to spend the time/disk on all retained rows.
- Wire canonical compatibility output into the static app only after bundle parity and smoke checks.
- Add optional/manual adjudication input consumption; current queue generation is read-only scaffolding.

## 2026-05-21 Full Canonical Build Probe

Ran a full retained-source canonical build into isolated directories:

```text
data/canonical_full
data/reports/canonical_full
```

First full run exposed a real importer defect:

- `ufocat2023.csv` failed after 630 rows.
- Cause: UFOCAT row 632 had `DAY=0`, and the adapter treated that as an exact day.
- Fix: UFOCAT now falls back to month precision when day is zero or out of range.
- Regression test added: `test_ufocat_zero_day_falls_back_to_month_precision`.
- Full `pytest` after the fix: 59 passed.

Second full run succeeded:

- Build duration: 1058.7 seconds
- Imported retained source records: 971,115
- Import failures: 0
- Source claims: 7,609,978
- Adapter-explicit source claims: 6,444,436
- Mapping-derived source claims: 1,165,542
- Deduped events: 944,578
- Mapped events: 289,831
- Exact duplicate groups: 17,969
- Duplicate review candidates: 5,000
- Manual review queue items: 5,001
- Row-shape anomalies: 1 preserved NUFORC overflow row

Artifact size report:

```text
data/reports/canonical_full/artifact_size_report.json
```

Added repeatable profiler:

```text
scripts/profile_canonical_artifacts.py
```

Important size finding:

- Full canonical/provenance JSON outputs total about 25.7 GB.
- Largest files are `deduped_events.jsonl` at about 5.63 GB, `source_records.jsonl` at about 5.28 GB, `canonical_input_events.jsonl` at about 5.28 GB, `normalized_events.json` at about 4.98 GB, and `source_claims.jsonl` at about 3.54 GB.
- These outputs are archival/build artifacts only. They are not suitable for browser startup loading.

Next architectural implication:

- Browser startup must use compact packed indexes, spatial/time shards, and lazy detail/provenance fetches.
- The app should not load canonical raw records, source claims, or full normalized JSON directly at startup.
- `canonical_input_events.jsonl` duplicated `source_records.jsonl`; future builds now skip this legacy duplicate unless `--write-legacy-canonical-input-events` is passed.

## 2026-05-21 Compact Canonical Web Artifact Probe

Added a static-first compact web artifact builder:

```text
scripts/build_canonical_web_artifacts.py
```

Purpose:

- Stream from `data/canonical_full/deduped_events.jsonl`.
- Avoid reading multi-GB `normalized_events.json`.
- Emit compact lazy event detail chunks without raw source rows, source claims, or full provenance.
- Emit the existing packed point index format for mapped rows.
- Emit a manifest with source/type/shape/precision counts and mapped bounds.

Outputs:

```text
data/canonical_web/points.bin
data/canonical_web/points_meta.json
data/canonical_web/event_chunk_manifest.json
data/canonical_web/event_chunks/*.json
data/canonical_web/canonical_web_manifest.json
data/canonical_web/artifact_size_report.json
data/canonical_web/compression_report.json
data/reports/canonical_web_runtime_readiness.json
```

10k smoke build:

- Events: 10,000
- Mapped events: 2,535
- Total artifacts: about 14.49 MB
- Gzip artifacts: about 3.71 MB
- Packed points: 182,520 bytes

Full compact build:

- Events: 944,578
- Mapped events: 289,831
- Event chunks: 378
- Packed points: 20,867,832 bytes, about 19.9 MB
- Points metadata: about 1.55 MB
- Lazy detail chunks: about 1.25 GB total
- Total compact artifacts: about 1.27 GB raw

Compression output:

```text
--write-gzip
data/canonical_web/compression_report.json
```

- Full compact artifact set gzip output: about 319.67 MB
- Startup-critical packed files gzip output: about 7.51 MB
- Lazy detail chunks gzip output: about 312.16 MB

Runtime readiness:

- `scripts/check_canonical_web_runtime_readiness.py` validates the compact point index, manifest counts, byte lengths, gzip siblings, and lazy-detail policy.
- Full canonical web output is `ready_for_startup_preview`.
- It is not yet `ready_for_primary_catalog` because the existing app startup still loads browser catalog shards eagerly; the next runtime step is a guarded lazy canonical detail path.

Important interpretation:

- Startup should load `points.bin`, `points_meta.json`, and compact manifests only.
- Detail chunks must remain lazy; eagerly loading all `event_chunks/*.json` would still be too heavy.
- Type/facet counts should be treated as browser-facing projection fields, not raw source truth. Raw source labels remain in lazy detail/provenance paths.

## 2026-05-21 Guarded Canonical Lazy-Detail Runtime Seam

Added an opt-in frontend runtime seam for compact canonical artifacts without changing the default catalog startup path:

- `app_config.json` now includes `canonicalWebArtifacts` with `enabled: false` and `primaryCatalog: false`.
- `webapp/static_public/app.js` can preload the canonical web manifest and chunk manifest only when explicitly enabled.
- Canonical lazy detail chunks are cached under a `canonical_web:` prefix so they do not collide with current static-bundle event chunks that use the same chunk IDs.
- Debug helpers expose `getCanonicalWebArtifactsStatus()` and `loadCanonicalPackedFullEvent(eventId)` for guarded smoke testing.
- Existing static bundle startup still loads the current catalog shards eagerly. The canonical artifact path is a readiness seam, not a primary catalog switch.
- The runtime now also preloads the canonical summary manifest when `canonicalWebArtifacts.enabled` is explicitly true, and exposes debug helpers for loading summary shards without switching the app's primary catalog.
- Added a guarded `canonicalWebArtifacts.primaryCatalog` prototype branch. When both `enabled` and `primaryCatalog` are explicitly true and the canonical manifests validate, startup ingests canonical summary shards into the normal in-memory catalog and hydrates full records lazily from canonical detail chunks. The shipped config still keeps both flags false.

Verification:

- Rebuilt `static_bundle` from existing generated data.
- Refreshed `static_bundle.zip`.
- Confirmed `static_bundle/data/app_config.json` contains `canonicalWebArtifacts.enabled: false`.

## 2026-05-21 Lean Summary Shards For Guarded Primary-Catalog Prototype

Extended the compact canonical web artifact builder with browser-summary shards:

```text
data/canonical_web/summary_manifest.json
data/canonical_web/summary_shards/*.json
```

Purpose:

- Keep startup on packed points and manifests.
- Add lazy, compact event summary shards for a future guarded primary-catalog prototype.
- Preserve `chunk_id` and `detail_index` links from every summary row back to lazy full detail chunks.
- Avoid duplicating narrative text in summaries; `summary` and `description_short` remain in lazy detail chunks.

Full lean compact build:

- Events: 944,578
- Mapped events: 289,831
- Event chunks: 378
- Summary shards: 95
- Packed points: 20,867,832 bytes, about 19.9 MB
- Lazy detail chunks: about 1.28 GB raw, about 311.91 MB gzipped
- Summary shards: about 356.42 MB raw, about 43.89 MB gzipped
- Startup-critical manifests/points: about 21.03 MB raw, about 6.93 MB gzipped
- Total compact artifacts: about 1.66 GB raw
- Full gzip output: about 362.73 MB
- Non-startup lazy gzip output: about 355.80 MB

Runtime readiness:

- `ready_for_startup_preview: true`
- `ready_for_primary_catalog_prototype: true`
- `ready_for_primary_catalog: false`

Important interpretation:

- The app is still not switched to the canonical primary catalog.
- Summary shards are enough to prototype primary-catalog filtering/timeline/result shells without loading all lazy detail chunks at startup.
- Full event text/details should still be fetched by `chunk_id` and `detail_index` only for visible/selected rows.

## 2026-05-21 Browser-Facing Taxonomy Projection

Added a conservative taxonomy projection before exposing canonical web artifacts to browser filters:

- New `parser/taxonomy.py` separates source-family labels from event/object labels.
- Source labels such as `NUFORC`, `MUFON`, `BLUEBOOK`, `UFODNA`, `NICAP`, `NIDS`, and `UKTNA` no longer become browser-facing type values.
- MUFON short-description tail fragments are no longer stored as future canonical object types.
- Shape synonyms collapse to controlled display labels such as `Disk`, `Sphere / orb`, `Triangle`, `Rectangle`, and `Formation`.
- Raw `type_raw` and `shape_raw` remain in lazy detail chunks; the cleaned `type`, `shape_normalized`, and `visual_type_group` fields are projection fields for UI filtering/coloring.

Rebuilt `data/canonical_web` after projection cleanup:

- Events: 944,578
- Mapped events: 289,831
- Event chunks: 378
- Summary shards: 95
- Total compact artifacts: about 1.66 GB raw
- Total gzip output: about 362.73 MB
- Startup gzip output: about 6.93 MB
- Top type labels are now controlled labels: `Unknown`, `Light`, `Sphere / orb`, `Disk`, `Triangle`, `Circle`, `Oval / egg`, `Fireball`, `Sighting`.

Verification:

- `pytest`: 65 passed
- `node --check webapp/static_public/app.js`
- `node --check static_bundle/app.js`
- `node tests/test_frontend_utils.mjs`
- `node tests/test_packed_points_frontend.mjs`
- Local HTTP asset smoke for `static_bundle/index.html`, `app.js`, `styles.css`, `data/app_config.json`, and `data/points_meta.json`

## 2026-05-21 Static Trace Render Budget And Chronology Color

Added the first frontend trace-scale improvement without changing playback sequencing:

- Static trace rendering now uses explicit segment-count modes: `individual`, `budgeted`, `aggregate`, and `summary`.
- Narrow windows still render all static trace segments.
- Large windows render a deterministic chronological sample instead of trying to draw every segment.
- Aggregate mode samples up to 18,000 segments.
- Summary mode samples up to 12,000 segments.
- Static trace colors now use an older-to-newer gradient from blue to green to orange.
- Gap bucket toggles still decide which trace segments are included.
- Playback trail behavior is unchanged.
- The map legend now shows the static trace chronology gradient and notes when a wide-window sample is being rendered.

Verification:

- Rebuilt `static_bundle`.
- Refreshed `static_bundle.zip` (30,724,596 bytes).
- `pytest`: 65 passed
- `node --check webapp/static_public/app.js`
- `node --check static_bundle/app.js`
- `node tests/test_frontend_utils.mjs`
- `node tests/test_packed_points_frontend.mjs`

## 2026-05-21 Packed Trace Event Index And Diagnostic Segments

Added offline trace-support artifacts to the canonical web builder:

```text
data/canonical_web/trace_event_index.bin
data/canonical_web/trace_event_index_meta.json
data/canonical_web/trace_segments.bin
data/canonical_web/trace_segments_meta.json
data/canonical_web/trace_aggregate_bins.bin
data/canonical_web/trace_aggregate_bins_meta.json
```

Important contract:

- `trace_event_index.bin` is the primary future-runtime artifact. It stores mapped traceable events in canonical playback order.
- Runtime filtering should filter trace event rows first, then connect adjacent visible rows client-side. This preserves the current filtered static-trace meaning.
- `trace_segments.bin` stores full-sequence adjacent segments only as diagnostic/convenience data. It is not a complete substitute for filtered static trace reconstruction because filters can create adjacent visible pairs that do not exist in the full unfiltered sequence.
- `trace_aggregate_bins.bin` stores full-universe wide-window LOD bins. It is explicitly not authoritative for arbitrary filtered traces; filtered aggregate behavior should be computed from `trace_event_index.bin`.
- Compact web detail and summary rows are now enriched with canonical chronology fields before writing, so summary shards carry `playback_sort_key` and related ordering metadata.

Full canonical web rebuild:

- Events: 944,578
- Mapped points: 289,831
- Trace event index rows: 288,558
- Full-sequence diagnostic trace segments: 288,557
- Full-universe aggregate trace bins: 153,626
- Trace event index bytes: 13,850,784 raw, about 6.11 MB gzipped
- Trace segments bytes: 20,776,104 raw, about 6.45 MB gzipped
- Trace aggregate bins bytes: 7,988,552 raw, about 4.00 MB gzipped
- Total compact artifacts: about 2,135.13 MB raw
- Full gzip output: about 405.41 MB
- Startup gzip output: about 7.07 MB

Verification:

- Limited 50,000-row real-data build passed runtime readiness.
- Full `data/canonical_web` rebuild passed runtime readiness.
- `pytest`: 68 passed

## 2026-05-21 Frontend Packed Trace Utility Guardrails

Added a tested frontend utility module for future guarded trace-artifact consumption:

```text
webapp/static/packed-trace-utils.mjs
tests/test_packed_traces_frontend.mjs
webapp/static_public/app.js guarded debug trace artifact loader
```

The utility validates and decodes:

- `trace_event_index.bin`
- `trace_segments.bin`
- `trace_aggregate_bins.bin`

It also provides `traceEventRowsToVisibleSegments(rows)`, which encodes the required filtered-trace rule: filter event-index rows first, then connect adjacent visible rows. The test covers the A-B-C case where filtering out B must reconstruct A-C from the event index rather than expecting a precomputed full-sequence segment.

Extended the utility with exact client-side filtered aggregation helpers:

- `aggregateTraceEventRows(rows, levels)`
- `aggregateTraceSegments(segments, levels)`
- `traceGapBucketForDays(gapDays)`
- shortest-path longitude wrapping for antimeridian-safe visible segments

This is still utility-only. It prepares the logic for later live trace rendering without changing current playback/static trace behavior.

`webapp/static_public/app.js` now exposes debug helpers after `canonicalWebArtifacts.enabled` is explicitly true:

```text
window.__UFO_TIMELINE_DEBUG__.loadCanonicalTraceArtifact(kind)
window.__UFO_TIMELINE_DEBUG__.getCanonicalTraceArtifactRow(kind, rowIndex, options)
```

This does not change default startup, playback, trace rendering, or static traces. The shipped config still leaves `canonicalWebArtifacts.enabled` and `primaryCatalog` disabled.

Verification:

- Rebuilt `static_bundle`.
- Refreshed `static_bundle.zip` (30,726,436 bytes).
- `pytest`: 68 passed
- `node tests/test_packed_traces_frontend.mjs`
- `node tests/test_frontend_utils.mjs`
- `node tests/test_packed_points_frontend.mjs`
- `node --check webapp/static/packed-trace-utils.mjs`
- `node --check webapp/static_public/app.js`
- `node --check static_bundle/app.js`

## 2026-05-21 Canonical Trace Static Payload Staging

Added an opt-in staging helper:

```text
scripts/stage_canonical_web_static_payload.py
tests/test_stage_canonical_web_static_payload.py
```

Purpose:

- Create a static-root-compatible `data/canonical_web` payload for guarded browser experiments.
- Avoid copying the full multi-GB canonical web corpus into the default `static_bundle.zip`.
- Support the current trace-artifact debug loaders with only manifests plus packed trace files.

Real trace-runtime payload staged at `data/canonical_web_static_trace_payload`:

- Files copied: 18
- Raw payload bytes: 42,721,166
- Gzip sibling bytes: 17,381,589
- Total staged bytes: 60,102,755

The staging helper also supports `--mode primary-catalog-trace-runtime`, which includes summary shards and trace artifacts for guarded primaryCatalog + traceRuntime startup previews while still omitting lazy full-detail event chunks.

Verification:

- `pytest tests/test_stage_canonical_web_static_payload.py`: 2 passed

## 2026-05-21 Guarded Canonical Trace Runtime Preview

Added an off-by-default frontend trace-runtime seam:

```text
webapp/static_public/app.js
parser/static_bundle.py
```

The shipped `app_config.json` now includes:

```json
"canonicalWebArtifacts": {
  "enabled": false,
  "primaryCatalog": false,
  "traceRuntime": false
}
```

When all three flags are explicitly enabled, the static trace builder can use cached `trace_event_index.bin` rows from canonical web artifacts. It filters event-index rows by the active mapped event universe first, then connects adjacent visible rows in canonical playback order. If the artifact is not cached yet, the renderer keeps the existing legacy trace path for that pass, starts a one-time preload, invalidates trace caches on success, and rerenders static traces. Default startup, playback trails, and legacy static traces remain unchanged.

Also added a local gzip-aware preview server:

```text
scripts/serve_static_bundle_with_canonical_web.py
tests/test_canonical_preview_server.py
```

Purpose:

- Serve the normal `static_bundle` without editing checked-in config.
- Overlay `/data/canonical_web/` from `data/canonical_web`.
- Serve `.gz` siblings with `Content-Encoding: gzip` for local static-host parity.
- Optionally return an in-memory app config override for `enabled`, `primaryCatalog`, and `traceRuntime`.
- Point `packedPoints` at canonical `points_meta.json` / `points.bin` when primary-catalog preview is enabled, or when `--use-canonical-packed-points` is passed.

Verification:

- `pytest tests/test_canonical_preview_server.py`: 6 passed
- `pytest`: 69 passed before the preview server test was added
- `node --check webapp/static_public/app.js`
- `node --check static_bundle/app.js`
- `node tests/test_frontend_utils.mjs`
- `node tests/test_packed_points_frontend.mjs`
- `node tests/test_packed_traces_frontend.mjs`

Added a guarded aggregate trace preview helper in `webapp/static_public/app.js`:

```text
window.__UFO_TIMELINE_DEBUG__.renderCanonicalTraceAggregatePreview({ level: "10deg" })
window.__UFO_TIMELINE_DEBUG__.clearCanonicalTraceAggregatePreview()
window.__UFO_TIMELINE_DEBUG__.getCanonicalTraceAggregatePreviewStats()
```

This reads `trace_aggregate_bins.bin` through the existing canonical trace-artifact loader and renders a separate debug trace canvas layer. It is explicitly full-universe LOD only and does not replace exact filtered traces from `trace_event_index.bin`.

## 2026-05-21 Manual Review Decision Ingestion

Added optional record-only manual adjudication ingestion to the canonical CSV build:

```text
scripts/build_canonical_ufo_dataset.py
tests/test_canonical_import.py
```

The new `--manual-review-decisions` option accepts JSONL or a JSON array keyed by `manual_review_queue.review_item_id`. Valid decisions are recorded back onto matching queue items, mirrored to `manual_review_applied_decisions.jsonl`, and summarized in `manual_review_decisions_report.json`.

This is intentionally non-destructive. Decisions such as `same_event` are now captured for provenance and workflow continuity, but they do not mutate `deduped_events.jsonl`, `normalized_events.json`, or web runtime artifacts until a separate, explicitly tested merge/exclusion application pass exists.

Verification:

- `py_compile scripts/build_canonical_ufo_dataset.py tests/test_canonical_import.py`
- `pytest tests/test_canonical_import.py`: 13 passed

## 2026-05-21 Manual Review Effects Plan

Added a plan-only follow-up pass for reviewed manual decisions:

```text
scripts/plan_manual_review_effects.py
tests/test_manual_review_effects_plan.py
```

The planner reads `manual_review_queue.jsonl` plus `manual_review_applied_decisions.jsonl` and emits `manual_review_effects_plan.json`. It converts reviewed decisions into explicit planned effects such as `merge_duplicate_candidate`, `preserve_distinct_events`, `exclude_source_row`, `repair_source_row_upstream`, mapping actions, or deferred review. This remains deliberately non-destructive: planned merge/exclusion effects are reviewable intent only and require a later explicit apply step before any canonical outputs are rewritten.

Added `docs/MANUAL_REVIEW_APPLY_DESIGN.md` to define the later explicit apply path. The design requires preview-only shadow outputs first and blocks promotion unless a separate mutation implementation passes validation and uses an explicit acknowledgement flag.

Implemented the preview-only shadow apply step:

```text
scripts/apply_manual_review_effects.py
tests/test_manual_review_apply_preview.py
```

The script supports `--mode preview` only. It can merge reviewed duplicate candidates or exclude reviewed source rows into a separate preview output directory while preserving `canonical_outputs_mutated: false`; promotion/mutation mode remains unavailable.

## 2026-05-21 Guarded Filtered Trace Aggregation

Added an off-by-default live static-trace aggregation branch:

```text
webapp/static_public/app.js
parser/static_bundle.py
scripts/serve_static_bundle_with_canonical_web.py
static_bundle/
static_bundle.zip
```

The new `canonicalWebArtifacts.filteredTraceAggregation` flag only becomes eligible when canonical web artifacts, primary catalog, and trace runtime are all enabled and `trace_event_index.bin` is cached. For aggregate/summary trace render modes, the app now groups the exact filtered trace-event-index segments into client-side density segments before drawing. This avoids using `trace_aggregate_bins.bin` for filtered rendering; that artifact remains debug/full-universe only.

Preview-server support:

```text
scripts/serve_static_bundle_with_canonical_web.py --enable-primary-catalog --enable-trace-runtime --enable-filtered-trace-aggregation
```

Verification:

- `node --check webapp/static_public/app.js`
- `node --check static_bundle/app.js`
- `py_compile parser/static_bundle.py scripts/serve_static_bundle_with_canonical_web.py`
- `pytest tests/test_canonical_preview_server.py tests/test_pipeline.py`: 7 passed
- `pytest`: 78 passed
- `node tests/test_frontend_utils.mjs`
- `node tests/test_packed_points_frontend.mjs`
- `node tests/test_packed_traces_frontend.mjs`

Preview smoke:

- Staged `primary-catalog-trace-runtime` payload at `data/canonical_web_static_primary_trace_payload`.
- Short-lived preview server verified `primaryCatalog=true`, `traceRuntime=true`, `filteredTraceAggregation=true`, canonical packed-points URLs, manifest HTTP 200, and `trace_event_index_meta.json` with 288,558 rows at 48 bytes/row.
- Headless Chrome and Edge CDP smoke was blocked by browser exit code 13 before a debugging target was exposed, so visual/browser runtime confirmation remains pending.
- Codex in-app browser smoke was also blocked by local navigation `ERR_BLOCKED_BY_CLIENT`; repeat visual smoke in a normal local browser or an unblocked browser automation environment.

## 2026-05-21 Full-Detail Canonical Payload Staging Mode

Added an explicit full-detail staging mode:

```text
scripts/stage_canonical_web_static_payload.py --mode primary-catalog-trace-runtime-with-details
tests/test_stage_canonical_web_static_payload.py
```

The existing `primary-catalog-trace-runtime` mode remains lean and omits `event_chunks`. The new `primary-catalog-trace-runtime-with-details` mode copies summary shards, trace artifacts, and every lazy `event_chunks/*.json` file listed by `event_chunk_manifest.json`, plus gzip siblings when available. This gives us a production-like payload path for full-detail browsing without bloating the default `static_bundle.zip`.

Verification:

- `py_compile scripts/stage_canonical_web_static_payload.py tests/test_stage_canonical_web_static_payload.py`
- `pytest tests/test_stage_canonical_web_static_payload.py`: 3 passed

## 2026-05-21 Canonical Packed-Point Map-Layer Eligibility

Removed the guarded canonical-primary skip that forced packed-point catalog parity to `ok: false`. When `canonicalWebArtifacts.primaryCatalog` is enabled, the app now validates sampled packed-point rows against the loaded canonical summary catalog. Packed points can serve map-layer events only if that parity check passes, so the default legacy path and disabled canonical config remain unchanged.

## 2026-05-21 Packed-Point Filter/Facet Helpers

Added pure packed-point filter and facet helpers in:

```text
webapp/static/packed-points-utils.mjs
tests/test_packed_points_frontend.mjs
```

The helpers can filter typed packed rows by date range, source, type, location precision, low-precision suppression, and exact-date suppression while returning row indexes/event IDs instead of projected event objects. Facet counts mirror the existing cross-filter eligibility model. Keyword/search filters intentionally return `requiresFallback` because packed point rows do not contain full searchable text.

This is deliberately helper-only. It is not wired into startup, map rendering, Results, or default app config.

## 2026-05-21 Canonical Static Payload Validator

Added a staged static-payload readiness checker:

```text
scripts/check_canonical_web_static_payload.py
tests/test_check_canonical_web_static_payload.py
data/reports/canonical_web_static_payload_readiness.json
```

The checker validates the opt-in payload manifest, copied file existence/byte sizes, mode-required artifacts, summary-shard/detail-chunk policy, gzip sibling pairing, provenance-only file exclusion, and the checked-in `static_bundle/data/app_config.json` canonical flags staying disabled.

Current `data/canonical_web_static_primary_trace_payload` validation:

```text
status: ready
mode: primary-catalog-trace-runtime
files: 212
raw files: 106
gzip files: 106
summary shards: 95
event chunks: 0
default canonical config disabled: true
```

HTTP gzip smoke with the local preview handler returned `Content-Encoding: gzip` and `Vary: Accept-Encoding` for `/data/canonical_web/points_meta.json`. This validates the server/header path separately from file presence.

Also staged and validated the opt-in full-detail payload:

```text
data/canonical_web_static_primary_trace_payload_full
data/reports/canonical_web_static_payload_full_readiness.json
```

Full-detail validation:

```text
status: ready
mode: primary-catalog-trace-runtime-with-details
files: 968
raw files: 484
gzip files: 484
summary shards: 95
event chunks: 378
raw bytes: 2,238,847,529
gzip bytes: 425,104,204
default canonical config disabled: true
```

This payload is explicitly deployment/test-only and remains outside `static_bundle.zip`.

## 2026-05-21 Static Trace Render Metrics

Added a debug/status-only static trace render metrics snapshot in:

```text
webapp/static_public/app.js
static_bundle/app.js
tests/test_webapp.py
```

`window.__UFO_TIMELINE_DEBUG__.getStaticTraceRenderMetrics()` now reports the last static trace render mode, total segment count, rendered segment count, sample ratio, threshold/sample-limit constants, area-filter/cache context, source path, and filtered aggregation status. This does not rebuild traces, change playback, alter trace rendering decisions, or enable canonical flags.

The hidden/static-off path now clears stale aggregation status and records an inactive metrics reason, so debug output does not report an old aggregate render after static traces are hidden.

## 2026-05-21 Runtime Integration Readiness Gate

Added a conservative aggregate gate:

```text
scripts/summarize_runtime_integration_readiness.py
tests/test_runtime_integration_readiness.py
data/reports/runtime_integration_readiness_gate.json
```

Current status:

```text
status: preview_ready_default_blocked
ready_for_preview_package: true
ready_for_default_promotion: false
failed_checks: none
```

The gate confirms the checked-in canonical flags remain disabled, runtime artifacts are preview-ready, lean and full-detail static payloads validate, gzip header smoke is recorded, packed-point helpers and trace metrics are helper/debug-only, manual-review mutation remains unavailable, and browser smoke is still explicitly blocked rather than treated as passed.

## 2026-05-21 Descriptor-Driven Trace Legend

Integrated the frontend trace legend with local descriptor objects that mirror the backend descriptor shape:

```text
webapp/static_public/app.js
static_bundle/app.js
tests/test_webapp.py
```

The Sequence Trail legend now renders chronology, sampling, and aggregate-cell rows from `TRACE_LEGEND_DESCRIPTORS` instead of a hardcoded chronology row. Existing playback bucket rows remain unchanged. Aggregation legend text is shown only when `runtime.staticTraceAggregationStatus.active` is true.

This is UI/explanation-only: trace rendering, playback behavior, sample thresholds, cache keys, and canonical default flags were not changed.

## 2026-05-21 Manual Review Packet Export

Added a non-destructive manual review packet exporter:

```text
scripts/build_manual_review_packet.py
tests/test_manual_review_packet.py
data/reports/manual_review_packet.json
data/reports/manual_review_packet.csv
data/reports/manual_review_packet.md
data/reports/manual_review_packet_readiness.json
```

The exporter summarizes the current `data/canonical_full/manual_review_queue.jsonl` into JSON, CSV, and compact Markdown triage views. It preserves `review_item_id`, `review_type`, suggested decision options, candidate IDs, input IDs, score/reason evidence, date/location blocking keys, and source row summaries.

Current packet:

```text
input queue items: 5001
exported items: 5001
duplicate candidates: 5000
row shape anomalies: 1
canonical outputs mutated: false
decisions created: false
auto-merge performed: false
readiness status: ready
```

This is export-only. It does not create reviewer decisions, apply merges, write effects plans, mutate canonical outputs, or change browser/runtime behavior.

Added a packet readiness checker that verifies packet-vs-queue counts, exact review ID coverage, duplicate IDs, CSV JSON-field parseability, Markdown truncation disclosure, safety flags, and absence of forbidden mutation artifacts under `data/canonical_full`.

The aggregate runtime integration gate now includes `manual_review_packet_ready` and reports the packet item/CSV row counts while keeping the overall status `preview_ready_default_blocked`.

## 2026-05-21 Canonical Facet Readiness

Added a report-only facet readiness summarizer:

```text
scripts/summarize_canonical_facet_readiness.py
tests/test_canonical_facet_readiness.py
data/reports/canonical_facet_readiness.json
```

The report reads `data/canonical_web/canonical_web_manifest.json` and can optionally scan all summary shards for fields not counted in the manifest. The checked-in report was generated with `--scan-summary-shards`, so visual type group and time/playback chronology fields now have measured summary-shard counts. Source, date precision, location precision, and coordinate-source facets are ready from manifest-level counts. Type, shape, visual type group, and time sort kind are available but high-unknown and should be exposed with caveats/provenance.

This is report-only. It does not add UI controls, change filters, alter runtime behavior, or mutate canonical outputs.

The aggregate runtime readiness gate now includes `canonical_facet_readiness_available` plus facet/caveat counts. The current gate remains `preview_ready_default_blocked`.

## 2026-05-21 Phase 3 Blocked Readiness Handoff

Added `docs/PHASE_3_BLOCKED_READINESS_HANDOFF.md` to consolidate the current stop point. It records what is preview-ready, what remains blocked, the exact commands to regenerate the manual-review packet, packet readiness, facet readiness, and aggregate readiness reports, and the guardrails against default canonical promotion or manual-review mutation.

The current implementation state should pause on new runtime/UI promotion until either browser visual smoke is unblocked or a real human-reviewed decisions file exists.

## 2026-05-21 AI-Assisted Manual Review

Added a conservative AI-assisted reviewer and streaming impact summarizer:

```text
scripts/ai_review_manual_review_queue.py
scripts/summarize_manual_review_effect_impact.py
tests/test_ai_review_manual_review_queue.py
tests/test_manual_review_effect_impact.py
data/canonical_full/manual_review_decisions_ai_assisted.jsonl
data/canonical_full/manual_review_applied_decisions_ai_assisted.jsonl
data/reports/manual_review_ai_decisions_report.json
data/reports/manual_review_ai_effects_plan.json
data/reports/manual_review_ai_effect_impact_summary.json
```

The AI reviewer uses conservative, explicit rules. Duplicate candidates become `same_event` only when they have score 1.0, same strong date, same normalized location, similar source text, and a strong identifier/native-id/text-similarity tie. Weaker candidates are kept as `needs_more_evidence`. The row-shape anomaly is accepted as preserved rather than excluded.

Current AI-assisted decision counts:

```text
same_event: 4984
needs_more_evidence: 16
accept_preserved_row: 1
invalid decisions: 0
unknown review ids: 0
canonical outputs mutated: false
```

## Mapping Enrichment Preview From Offline GeoNames

Fixed the dataset status mapped-count display so canonical runtime mode reads the canonical web manifest count instead of the legacy packed-points count:

```text
source: webapp/static_public/app.js
built bundle: static_bundle/app.js
old visible mapped count source: static_bundle/data/app_config.json mappedCount = 34,227
canonical manifest mapped count before enrichment: 287,843
canonical manifest mapped count after enrichment: 315,855
```

Built report-only mapping coverage diagnostics:

```text
script: scripts/summarize_mapping_coverage_opportunities.py
json: data/reports/mapping_coverage_opportunities.json
csv: data/reports/mapping_coverage_opportunities.csv
events: 942,518
mapped: 287,843
unresolved: 654,675
unresolved with usable location text: 638,442
unresolved without usable location text: 16,233
cached geocode rows observed: 9,087
```

Built an offline GeoNames candidate diagnostic from the local allCountries dump:

```text
script: scripts/summarize_offline_geonames_mapping_candidates.py
json: data/reports/offline_geonames_mapping_candidates.json
csv: data/reports/offline_geonames_mapping_candidates.csv
queries checked: 250
parseable queries: 205
resolved queries: 198
high/medium candidate event count: 28,012
canonical outputs mutated: false
```

Applied only high/medium offline GeoNames candidates to a preview sidecar:

```text
script: scripts/apply_mapping_enrichment_preview.py
test: tests/test_mapping_enrichment_preview.py
input: data/canonical_preview_remaining_lower_time_format_apply/deduped_events.jsonl
output: data/canonical_preview_mapping_enrichment_geonames_high_medium/deduped_events.jsonl
report: data/reports/mapping_enrichment_geonames_high_medium_preview_apply_report.json
input events: 942,518
mapped before: 287,843
enriched events: 28,012
projected mapped after: 315,855
canonical outputs mutated: false
geocoding performed: false
```

Built, staged, and smoked the enriched canonical web payload:

```text
artifact: data/canonical_web_mapping_enrichment_geonames_high_medium
staged bundle dir: static_bundle/data/canonical_web
events: 942,518
mapped events: 315,855
trace events: 314,304
trace segments: 314,303
event chunks: 378
summary shards: 95
startup gzip MB: 7.75
runtime readiness: ready_for_primary_catalog
static payload readiness: ready
runtime integration gate: default_promoted_ready
browser smoke: passed on 8183/9413
smoke catalog source: canonical_web
smoke trace row count: 314,304
smoke rendered/source segments: 11,216 / 11,216
```

Expanded the same offline flow to a broader top-5000 unresolved query worklist:

```text
coverage report: data/reports/mapping_coverage_opportunities_top5000.json
coverage csv: data/reports/mapping_coverage_opportunities_top5000.csv
candidate report: data/reports/offline_geonames_mapping_candidates_top5000.json
candidate csv: data/reports/offline_geonames_mapping_candidates_top5000.csv
queries checked: 5,000
resolved queries: 4,439
high/medium candidate event count: 141,388
canonical outputs mutated: false
```

Applied the top-5000 high/medium candidates to a second preview sidecar and promoted that validated preview payload into the shipped static bundle:

```text
script: scripts/apply_mapping_enrichment_preview.py
input: data/canonical_preview_remaining_lower_time_format_apply/deduped_events.jsonl
candidates: data/reports/offline_geonames_mapping_candidates_top5000.csv
output: data/canonical_preview_mapping_enrichment_geonames_top5000_high_medium/deduped_events.jsonl
report: data/reports/mapping_enrichment_geonames_top5000_high_medium_preview_apply_report.json
input events: 942,518
mapped before: 287,843
enriched events: 141,388
projected mapped after: 429,231
geocoding performed: false
canonical outputs mutated: false
```

Built, staged, and smoked the broader top-5000 enriched canonical web payload:

```text
artifact: data/canonical_web_mapping_enrichment_geonames_top5000_high_medium
staged bundle dir: static_bundle/data/canonical_web
events: 942,518
mapped events: 429,231
trace events: 426,453
trace segments: 426,452
event chunks: 378
summary shards: 95
startup gzip MB: 11.21
runtime readiness: ready_for_primary_catalog
static payload readiness: ready
runtime integration gate: default_promoted_ready
browser smoke: passed on 8184/9414
smoke catalog source: canonical_web
smoke trace row count: 426,453
smoke rendered/source segments: 11,515 / 11,515
```

Generated a residual mapping report after the top-5000 GeoNames pass and triaged the remaining local geocode cache:

```text
residual coverage json: data/reports/mapping_coverage_opportunities_after_top5000_geonames.json
residual coverage csv: data/reports/mapping_coverage_opportunities_after_top5000_geonames.csv
mapped after top-5000 GeoNames: 429,231
remaining unresolved: 513,287
remaining unresolved with location text: 497,054
remaining unresolved without location text: 16,233
cached geocode candidates json: data/reports/cached_geocode_mapping_candidates_after_top5000.json
cached geocode candidates csv: data/reports/cached_geocode_mapping_candidates_after_top5000.csv
safe cached candidate queries after rejecting broad centroids: 9
safe cached candidate event count: 185
```

Applied the safe cached candidate lane to an optional preview sidecar only:

```text
input: data/canonical_preview_mapping_enrichment_geonames_top5000_high_medium/deduped_events.jsonl
output: data/canonical_preview_mapping_enrichment_geonames_top5000_plus_cached/deduped_events.jsonl
report: data/reports/mapping_enrichment_geonames_top5000_plus_cached_preview_apply_report.json
mapped before: 429,231
enriched events: 185
projected mapped after: 429,416
staged into static_bundle: no
reason: small gain; kept as preview until cached-geocode precision policy is reviewed
canonical outputs mutated: false
```

### Canonical Runtime Default Promotion

Approved runtime promotion has now been applied to the shipped static bundle:

```text
config: static_bundle/data/app_config.json
canonicalWebArtifacts.enabled: true
canonicalWebArtifacts.primaryCatalog: true
canonicalWebArtifacts.traceRuntime: true
canonicalWebArtifacts.filteredTraceAggregation: true
canonical outputs mutated: false
```

The full-detail canonical web payload was restaged into the deployable bundle from:

```text
source artifact: data/canonical_web_remaining_lower_time_format_apply
target: static_bundle/data/canonical_web
mode: primary-catalog-trace-runtime-with-details
files: 968
event chunks: 378
gzip bytes: 424,596,978
events: 942,518
mapped events: 287,843
trace rows: 286,570
```

Validation after promotion:

```text
runtime readiness: data/reports/canonical_web_runtime_readiness.json
status: ready_for_primary_catalog
static payload readiness: data/reports/canonical_web_static_payload_promoted_readiness.json
status: ready
integration gate: data/reports/runtime_integration_readiness_gate.json
gate status: default_promoted_ready
promotion blockers: none
browser smoke: passed against actual static_bundle on 8181/9411
startupPhase: Ready
catalogSource: canonical_web
trace_event_index cached: true
rowCount: 286,570
rendered/source segments: 11,135 / 11,135
static_bundle.zip: refreshed after restaging
```

The previous approval-boundary reports were refreshed to match the current promoted state:

```text
data/reports/canonical_promotion_decision_packet.json
data/reports/canonical_promotion_rollback_gap_audit.json
data/reports/deferred_work_queue.json
data/reports/static_host_payload_risk_report.json
```

### Remaining-Lower Time-Format Candidate Apply

The source-reviewed remaining-lower time-format lane was accepted and applied to a preview sidecar only:

```text
accepted decisions: 6
accepted decisions file: data/canonical_full/entity_resolution_remaining_lower_time_format_accepted_decisions.jsonl
effects plan: data/reports/entity_resolution_remaining_lower_time_format_effects_plan.json
preview apply report: data/reports/entity_resolution_remaining_lower_time_format_preview_apply_report.json
input sidecar events: 942,530
preview output events: 942,518
projected reduction: 12
canonical outputs mutated: false
```

The promoted runtime payload uses that sidecar output. This does not rewrite `data/canonical_full/deduped_events.jsonl`.

### Canonical Mutation Contract

A report-only mutation contract was added because direct canonical overwrite would promote the whole sidecar chain, not only the latest 6 decisions:

```text
script: scripts/build_canonical_mutation_contract.py
json: data/reports/canonical_mutation_contract.json
markdown: data/reports/canonical_mutation_contract.md
current canonical events: 944,578
promoted preview events: 942,518
whole-chain reduction if promoted: 2,060
latest remaining-lower reduction: 12
contract valid: true
ready_for_direct_canonical_overwrite: false
canonical outputs mutated: false
```

The contract records required backup, immutable report, rebuild, restage, smoke, and rollback steps for a future canonical corpus mutation.

### Mapping Coverage Counter Fix And Opportunity Report

Fixed the Dataset Status mapped count to use canonical web manifest counts when canonical runtime is active:

```text
source: webapp/static_public/app.js
deployed bundle: static_bundle/app.js
old behavior: preferred legacy app_config.mappedCount, showing 34,227 mapped events
new behavior: prefers canonical_web_manifest counts.mapped_events when canonical artifacts are ready
current canonical mapped events: 287,843
```

Built the first report-only mapping-coverage diagnostic:

```text
script: scripts/summarize_mapping_coverage_opportunities.py
json: data/reports/mapping_coverage_opportunities.json
csv: data/reports/mapping_coverage_opportunities.csv
events: 942,518
mapped: 287,843
unresolved: 654,675
unresolved with location text: 638,442
unresolved without location text: 16,233
mapped ratio: 0.305398
geocoding performed: false
canonical outputs mutated: false
```

Largest unresolved location-text buckets:

```text
city_state_country_like: 311,208
city_region_like: 290,227
city_state_like: 15,598
facility_or_site: 9,185
country_or_region_only: 6,550
single_place_token: 4,783
vague_or_unspecified: 891
```

Verification:

```text
node --check webapp/static_public/app.js: passed
node --check static_bundle/app.js: passed
pytest: 416 passed
promoted static_bundle smoke: passed on 8182/9412
static_bundle.zip: refreshed after app.js update
```

Extended the diagnostic to check the existing local geocode cache and the cached GeoNames download:

```text
cache file: cache/geocode_cache.jsonl
unresolved rows with cached geocode: 9,087
script: scripts/summarize_offline_geonames_mapping_candidates.py
json: data/reports/offline_geonames_mapping_candidates.json
csv: data/reports/offline_geonames_mapping_candidates.csv
GeoNames source: cache/map_overlays/allCountries.zip
top unresolved query limit requested: 500
top unresolved queries available: 250
parseable queries: 205
resolved query strings: 198
high-or-medium confidence event rows represented: 28,012
canonical outputs mutated: false
```

After adding the GeoNames candidate report:

```text
pytest: 417 passed
```

The effects plan remains plan-only:

```text
merge_duplicate_candidate: 4984
defer_duplicate_candidate: 16
preserve_source_row: 1
warnings: 0
canonical outputs mutated: false
```

The full preview apply path was not run against `data/canonical_full/deduped_events.jsonl` because the current apply script deep-copies and rewrites the full 5.9GB event corpus. Instead, `scripts/summarize_manual_review_effect_impact.py` streamed the full deduped corpus and reported:

```text
scanned events: 944517
required input ids: 7083
matched input ids: 7083
missing input ids: 0
cross-event merge effects: 4984
projected event reduction: 4984
canonical outputs mutated: false
preview outputs written: false
```

## 2026-05-21 Expanded Dedupe Opportunity Sizing

Added report-only duplicate sizing tools:

```text
scripts/summarize_duplicate_candidate_clusters.py
scripts/summarize_expanded_dedupe_opportunities.py
scripts/summarize_dedupe_benchmark_gap.py
tests/test_duplicate_candidate_clusters.py
tests/test_expanded_dedupe_opportunities.py
tests/test_dedupe_benchmark_gap.py
data/reports/duplicate_candidate_cluster_summary.json
data/reports/expanded_dedupe_opportunity_report.json
data/reports/dedupe_benchmark_gap_summary.json
```

The duplicate-candidate cluster summary shows the current 5,000-item fuzzy queue is pair-edge capped, not cluster-aware:

```text
candidate pair edges: 5000
candidate input nodes: 7113
candidate clusters: 2561
projected reduction if every edge in those clusters were same-event: 4552
dense pair capacity waste: 448
canonical outputs mutated: false
```

The expanded opportunity estimator streams current canonical source records and current deduped-event membership, groups only compact keys, and writes an estimate without creating decisions, preview outputs, or canonical mutations.

Current full report:

```text
source records scanned: 971115
current deduped events: 944578
current exact duplicate reduction: 26537
conservative projected additional reduction: 49627
moderate projected additional reduction: 49654
exploratory projected additional reduction: 52284
aggressive projected additional reduction: 76360
projected count after conservative review: 894951
projected count after aggressive review: 868218
UFOSINT screenshot benchmark: 618316
remaining gap after conservative estimate: 276635
remaining gap after aggressive estimate: 249902
canonical outputs mutated: false
preview outputs written: false
decisions created: false
auto merge performed: false
```

The first full run exposed an over-broad source-URL grouping risk: values such as `UFOReportCtr` are generic source labels, not unique URLs. The estimator now requires a specific URL signal and includes normalized location in the source-URL key. The saved report reflects the tightened rule.

After a spot-check indicated the UFOSINT screenshot is also under-deduped, the estimator was extended with an explicitly labeled aggressive review-only tier. The saved report now shows:

```text
conservative projected additional reduction: 49627
moderate projected additional reduction: 49654
exploratory projected additional reduction: 52284
aggressive projected additional reduction: 76360
projected count after aggressive review: 868218
remaining gap after aggressive estimate: 249902
```

The RONGERES example from the UFOSINT screenshot was added as a concrete test pattern: same source family, same exact day, same specific time, same normalized location, nearby trusted coordinates, but different source-native IDs. The estimator now has two narrower aggressive review-only families for that pattern:

```text
same_source_strong_date_location_specific_time projected reduction: 33489
same_source_strong_date_coordinate_cell_specific_time projected reduction: 23338
```

After tightening clock parsing and coordinate-source eligibility, the saved aggressive estimate is:

```text
aggressive projected additional reduction: 76360
projected count after aggressive review: 868218
remaining gap after aggressive estimate: 249902
```

This analysis means the current strongest report-only keys can recover a meaningful amount of duplicate inflation, and aggressive same-ID/time/location families recover more, but they still do not explain the full gap to the 618k external screenshot. Reaching or beating that count would require a broader validated entity-resolution pass, not simply applying the current report-only keys.

`data/reports/dedupe_benchmark_gap_summary.json` consolidates the current math:

```text
current gap to 618316 benchmark: 326262
after AI-assisted plan, naive/non-additive gap: 321278
after expanded conservative estimate gap: 276635
after expanded exploratory estimate gap: 273978
after expanded aggressive estimate gap: 249902
AI impact scanned event count matches import report: false
```

The AI scanned-event mismatch is carried forward as an explicit consistency check instead of being hidden.

## 2026-05-22 Entity-Resolution Scoring

Added a compact input-event lookup artifact:

```text
scripts/build_input_event_lookup.py
tests/test_input_event_lookup.py
data/canonical_full/input_event_lookup.jsonl
data/reports/input_event_lookup_report.json
```

The lookup is a derived acceleration artifact with one compact row per canonical source input:

```text
event count: 944578
source record count from events: 971115
lookup rows: 971115
lookup bytes: 102938190
exact duplicate record reduction: 26537
event ids with multiple inputs: 17969
duplicate input ids: 0
conflicting input ids: 0
canonical outputs mutated: false
```

It maps each `canonical_input_id` to the current `canonical_event_id` from `deduped_events.jsonl`. It does not replace `deduped_events.jsonl` as the authoritative source and does not apply merges.

Added a report-only ER scoring pass:

```text
scripts/score_entity_resolution_candidates.py
scripts/build_entity_resolution_review_packet.py
scripts/validate_entity_resolution_decisions.py
scripts/plan_entity_resolution_effects.py
scripts/preview_entity_resolution_apply.py
tests/test_entity_resolution_scoring.py
tests/test_entity_resolution_review_packet.py
tests/test_entity_resolution_decisions.py
tests/test_entity_resolution_effects_plan.py
tests/test_entity_resolution_preview_apply.py
data/reports/entity_resolution_score_report.json
data/reports/entity_resolution_score_report_smoke.json
data/reports/entity_resolution_score_report_sample100k.json
data/reports/entity_resolution_review_packet.json
data/reports/entity_resolution_review_packet.csv
data/reports/entity_resolution_review_packet.md
data/reports/entity_resolution_decisions_report.json
data/canonical_full/entity_resolution_validated_decisions.jsonl
data/reports/entity_resolution_effects_plan.json
data/reports/entity_resolution_preview_apply_report.json
```

The scorer is intentionally non-destructive. It scores bounded candidate pairs for review prioritization and keeps all apply/merge flags false:

```text
canonical outputs mutated: false
preview outputs written: false
decisions created: false
auto merge performed: false
```

The score model combines exact-day/date precision, specific time, normalized location or trusted coordinate distance, text evidence, source/native ID evidence, type/shape agreement or conflicts, and a structured same-source/date/time/location pattern. It also downgrades coarse dates, penalizes same-source records with different native IDs, and limits text credit for very short generic exact text.

The `--limit` path now performs true bounded source-record passes and uses the compact lookup when available instead of materializing the full input-to-event index from `deduped_events.jsonl`. Limited reports mark `event_index_scope: touched_input_ids`, keep full-corpus count fields null, and report how many lookup rows were scanned to resolve the touched IDs.

After adding `data/canonical_full/input_event_lookup.jsonl`, scorer reports use `event_index_source: input_event_lookup` and `deduped_events_scanned_for_index: 0`.

Current full report:

```text
source records scanned: 971115
current event count: 944578
required input ids for index: 971108
matched required input ids: 971108
event index source: input_event_lookup
deduped events scanned for index: 0
lookup rows scanned for index: 971115
selected multi-record blocks: 126298
candidate pair upper bound: 586002
scored pairs: 325249
cross-event scored pairs: 282652
likely same-event review pairs: 90275
strong candidate review pairs: 64118
moderate candidate review pairs: 93835
projected cross-event reduction, likely same-event review: 22056
projected cross-event reduction, strong or better: 37601
projected cross-event reduction, moderate or better: 63668
canonical outputs mutated: false
```

The ER review packet exports cross-current-event samples only by default, so it is useful for merge review rather than calibration of already-merged examples:

```text
sample scope: per_band_cross_event_scored_pair_samples
exported review items: 200
likely same-event review items: 50
strong candidate review items: 50
moderate candidate review items: 50
weak candidate items: 50
cross current event items: 200
canonical outputs mutated: false
decisions created: false
```

The ER decision validator is also wired but has no human decisions yet:

```text
packet items: 200
input decisions: 0
valid decisions: 0
invalid decisions: 0
validated decisions output bytes: 0
canonical outputs mutated: false
decisions created: false
auto merge performed: false
```

The ER effects planner is wired after validation and is also currently empty because no decisions have been supplied:

```text
effect policy: entity_resolution_plan_only
validated decisions: 0
planned effects: 0
requires explicit apply step: 0
canonical outputs mutated: false
auto merge performed: false
```

The ER preview apply seam is stream-oriented and preview-only. It buffers only event rows that participate in planned ER merge groups. With the current empty effects plan it wrote a no-op report and intentionally did not copy the 5.9GB corpus:

```text
apply policy: entity_resolution_stream_preview_only
preview outputs written: false
effects requested: 0
effects applied: 0
effects blocked: 0
projected event reduction: 0
canonical outputs mutated: false
```

The bounded 100k run still scanned most of the lookup rows because the source-record order and lookup order are not aligned. That is acceptable for calibration and is still much cheaper than scanning the 5.9GB event file, but a future indexed/sharded lookup would make arbitrary small touched-ID queries faster.

The ER calibration summary is now generated from the full score report plus the cross-event review packet:

```text
report: data/reports/entity_resolution_calibration_summary.json
report policy: entity_resolution_calibration_summary
scored pairs: 325249
cross-event scored pairs: 282652
exported review items: 200
review packet cross-event only: true
ready for human review: true
ready for apply: false
apply blocker: validated_same_event_decisions_required
canonical outputs mutated: false
preview outputs written: false
decisions created: false
auto merge performed: false
```

The top likely-band risk hotspot remains weak text overlap, followed by short text match limits and type disagreement. Treat these as calibration prompts for review, not as automatic merge blockers or automatic approvals.

The ER AI-assisted suggestion pass is now separate from validated decisions and stays under `data/reports`:

```text
suggestions: data/reports/entity_resolution_review_suggestions.jsonl
report: data/reports/entity_resolution_review_suggestions_report.json
suggestion policy: entity_resolution_ai_assisted_conservative_suggestions
packet items reviewed: 200
suggestions written: 200
same_event suggestions: 37
needs_more_evidence suggestions: 163
decisions created: false
decision outputs created: false
validated decisions created: false
canonical outputs mutated: false
auto merge performed: false
```

This is intentionally not written to `data/canonical_full/entity_resolution_decisions.jsonl`. Accepted suggestions must be converted to decision records and validated before any effect plan can use them.

The AI-accepted ER lane is now generated separately from the main human-decision lane:

```text
promoted decisions: data/canonical_full/entity_resolution_decisions_ai_accepted.jsonl
promotion report: data/reports/entity_resolution_suggestion_promotion_report.json
promoted decision count: 200
same_event decisions: 37
needs_more_evidence decisions: 163
skipped suggestions: 0
validated decisions: data/canonical_full/entity_resolution_validated_decisions_ai_accepted.jsonl
validation report: data/reports/entity_resolution_ai_decisions_validation_report.json
valid decisions: 200
invalid decisions: 0
AI effects plan: data/reports/entity_resolution_ai_effects_plan.json
planned merge effects: 37
planned deferrals: 163
requires explicit apply step: 37
canonical outputs mutated: false
auto merge performed: false
```

The stream preview apply was not run for this lane because applying 37 merge effects would write a full shadow corpus. The current stop point is a plan-only artifact.

The AI ER effect impact summary quantifies that stop point without streaming or copying the full corpus:

```text
report: data/reports/entity_resolution_ai_effect_impact_summary.json
impact policy: entity_resolution_plan_impact_summary_only
merge effects: 37
defer effects: 163
touched event count: 74
projected event reduction: 37
merge effects with insufficient event ids: 0
requires explicit apply step: 37
canonical outputs mutated: false
preview outputs written: false
auto merge performed: false
```

A compact ER merge preview patch now represents the same 37 AI-planned merges without writing a full shadow corpus:

```text
patch: data/reports/entity_resolution_ai_merge_preview_patch.json
patch policy: entity_resolution_merge_patch_preview_only
merge patch count: 37
skipped merge effects: 0
projected event reduction: 37
replacement selection: first_sorted_current_event_id_preview_only
canonical outputs mutated: false
preview outputs written: false
auto merge performed: false
```

This patch is metadata-only. A future apply step still has to decide final merged event bodies and provenance reconciliation.

The compact merged-event body preview hydrates the 74 event rows touched by the 37 ER merge patches and summarizes representative fields, source provenance, and conflicts:

```text
preview: data/reports/entity_resolution_ai_merged_event_preview.json
preview policy: entity_resolution_compact_merged_event_preview_only
merge patches: 37
required event ids: 74
hydrated event ids: 74
missing event ids: 0
patches with missing events: 0
scanned events before all rows found: 801113
merged-event previews: 37
body policy: compact_preview_summary_not_canonical_event_body
canonical outputs mutated: false
preview outputs written: false
auto merge performed: false
```

This remains a bounded inspection artifact. It does not write a full shadow `deduped_events.jsonl`.

The ER merge readiness gate now separates material blockers from review-only differences:

```text
report: data/reports/entity_resolution_ai_merge_readiness.json
readiness policy: entity_resolution_merge_preview_readiness_gate
merge previews checked: 37
missing event ids: 0
blocking conflict items: 4
review-only conflict items: 33
conflict counts: description=21, summary=21, location_raw=18, lon=5, lat=3, type_normalized=3
ready for full shadow preview: false
ready for canonical apply: false
canonical outputs mutated: false
preview outputs written: false
auto merge performed: false
```

The 4 blockers are 3 type conflicts and 1 coordinate-distance-over-10km case. A ready-subset shadow preview can proceed with the 33 non-blocking patch rows while these 4 remain deferred.

The readiness-filtered ER effects plan keeps only the non-blocking merge effects:

```text
subset plan: data/reports/entity_resolution_ai_effects_plan_ready_subset.json
subset policy: entity_resolution_ready_subset_for_shadow_preview
source effects: 200
selected merge effects: 33
excluded merge effects: 4
passthrough non-merge effects: 163
canonical outputs mutated: false
preview outputs written: false
auto merge performed: false
```

This subset is the correct input for any later full shadow-corpus ER preview.

The readiness-approved ER subset shadow preview was generated:

```text
report: data/reports/entity_resolution_ai_ready_subset_preview_apply_report.json
shadow deduped events: data/canonical_preview_entity_resolution_ai_ready_subset/deduped_events.jsonl
shadow output size: 5,669,833,884 bytes / 5,407.17 MB
input event count: 944578
preview event count: 944545
effects requested: 33
effects applied: 33
effects blocked: 0
projected event reduction: 33
canonical outputs mutated: false
```

This is still preview-only. The canonical full corpus remains unchanged.

The ER shadow preview output validator scanned the 5.41GB preview JSONL and passed:

```text
check: data/reports/entity_resolution_ai_ready_subset_preview_output_check.json
check policy: entity_resolution_shadow_preview_output_check
valid: true
row count: 944545
expected row count: 944545
preview merge rows: 33
expected preview merge rows: 33
duplicate event ids: 0
malformed rows: 0
canonical outputs mutated: false
```

The blocked ER merge review packet was generated for the 4 readiness-blocked cases:

```text
json: data/reports/entity_resolution_blocked_merge_review_packet.json
csv: data/reports/entity_resolution_blocked_merge_review_packet.csv
markdown: data/reports/entity_resolution_blocked_merge_review_packet.md
blocked items: 4
blocking field counts: type_normalized=3, coordinate_distance_over_10km=1
canonical outputs mutated: false
decisions created: false
```

The blocked ER merge analyzer classified the 4 deferred cases without creating decisions:

```text
analysis: data/reports/entity_resolution_blocked_merge_analysis.json
analysis policy: entity_resolution_blocked_merge_analysis_only
blocked items: 4
likely source subtype variants: 3
nearby location coordinate variants: 1
high-confidence shadow override candidates: 3
canonical outputs mutated: false
decisions created: false
override decisions created: false
```

The 3 type-code variants are now isolated as shadow-preview override candidates. The Salta/San Bernardo coordinate-distance case remains review-first.

The shadow-override ER subset plan adds only those high-confidence type-code variants to the readiness-approved subset:

```text
subset plan: data/reports/entity_resolution_ai_effects_plan_shadow_override_subset.json
subset policy: entity_resolution_shadow_preview_subset_with_analysis_overrides
baseline selected merge effects: 33
override selected merge effects: 3
selected merge effects: 36
excluded merge effects: 1
canonical outputs mutated: false
override decisions created: false
```

The shadow-override subset preview was generated and validated:

```text
report: data/reports/entity_resolution_ai_shadow_override_subset_preview_apply_report.json
shadow deduped events: data/canonical_preview_entity_resolution_ai_shadow_override_subset/deduped_events.jsonl
check: data/reports/entity_resolution_ai_shadow_override_subset_preview_output_check.json
input event count: 944578
preview event count: 944542
effects requested: 36
effects applied: 36
effects blocked: 0
projected event reduction: 36
row count: 944542
duplicate event ids: 0
malformed rows: 0
valid: true
canonical outputs mutated: false
```

The shadow-override delta summary now records the net effect of adding those 3 overrides:

```text
summary: data/reports/entity_resolution_shadow_override_delta_summary.json
summary policy: entity_resolution_shadow_override_delta_summary
ready subset reduction: 33
override subset reduction: 36
incremental projected reduction: 3
remaining excluded merge effects: 1
ready output valid: true
override output valid: true
canonical outputs mutated: false
```

The ER canonical-apply readiness gate now explicitly blocks canonical mutation until the remaining safety work is done:

```text
readiness: data/reports/entity_resolution_canonical_apply_readiness.json
apply readiness policy: entity_resolution_canonical_apply_readiness_gate
shadow preview valid: true
shadow preview effects applied: 36
shadow preview effects blocked: 0
projected reduction: 36
remaining excluded merge effects: 1
ready for canonical apply: false
canonical apply blockers: final_merge_body_policy_missing, canonical_apply_command_not_implemented, review_first_merge_candidates_remaining
canonical outputs mutated: false
```

The draft canonical merge-body/provenance policy proposal is now machine-readable:

```text
proposal: data/reports/entity_resolution_canonical_merge_policy_proposal.json
policy: entity_resolution_canonical_merge_policy_proposal_v1
policy status: draft_not_implemented
observed merge previews: 37
observed conflicts: description=21, summary=21, location_raw=18, lon=5, lat=3, type_normalized=3
shadow override projected reduction: 36
remaining excluded merge effects: 1
ready for apply implementation: false
canonical outputs mutated: false
```

The proposal defines deterministic field rules for IDs, input IDs, provenance unioning, scalar conflicts, text conflicts, coordinates, and ER merge audit metadata. It intentionally does not enable canonical apply.

The policy body preview applies the draft policy shape to the shadow-override merge subset:

```text
preview: data/reports/entity_resolution_policy_body_preview.json
preview policy: entity_resolution_canonical_merge_body_policy_preview_only
selected effects: 36
policy body previews: 36
skipped previews: 1
canonical outputs mutated: false
ready for canonical apply: false
```

This compact preview shows the proposed ER merge audit fields and structured conflict metadata per selected merge candidate. It is still not a full canonical event corpus.

The policy-body preview check validates the proposed audit/conflict metadata:

```text
check: data/reports/entity_resolution_policy_body_preview_check.json
check policy: entity_resolution_policy_body_preview_check
valid: true
policy body previews: 36
selected effects: 36
duplicate effect ids: 0
duplicate review item ids: 0
missing required fields: 0
invalid conflict metadata: 0
canonical outputs mutated: false
```

The ER review lane was expanded from 50 retained samples per band to 500 retained samples per band under separate artifact names:

```text
score report: data/reports/entity_resolution_score_report_samples500.json
review packet: data/reports/entity_resolution_review_packet_samples500.json
suggestions: data/reports/entity_resolution_review_suggestions_samples500.jsonl
suggestions report: data/reports/entity_resolution_review_suggestions_samples500_report.json
scored pairs: 325249
review packet items: 2000
suggestions: 2000
suggested same_event: 408
suggested needs_more_evidence: 1592
canonical outputs mutated: false
```

The expanded sample decisions/effects lane remains separate from the original 200-row baseline:

```text
decisions: data/canonical_full/entity_resolution_decisions_ai_accepted_samples500.jsonl
validated decisions: data/canonical_full/entity_resolution_validated_decisions_ai_accepted_samples500.jsonl
validation report: data/reports/entity_resolution_ai_decisions_validation_samples500_report.json
effects plan: data/reports/entity_resolution_ai_effects_plan_samples500.json
impact summary: data/reports/entity_resolution_ai_effect_impact_samples500_summary.json
valid decisions: 2000
invalid decisions: 0
planned merge effects: 408
planned defer effects: 1592
projected event reduction before readiness filtering: 408
canonical outputs mutated: false
```

The expanded compact merge preview/readiness lane found most planned merges suitable for shadow preview:

```text
merge patch: data/reports/entity_resolution_ai_merge_preview_patch_samples500.json
merged preview: data/reports/entity_resolution_ai_merged_event_preview_samples500.json
readiness: data/reports/entity_resolution_ai_merge_readiness_samples500.json
ready subset: data/reports/entity_resolution_ai_effects_plan_ready_subset_samples500.json
blocked packet: data/reports/entity_resolution_blocked_merge_review_packet_samples500.json
blocked analysis: data/reports/entity_resolution_blocked_merge_analysis_samples500.json
merge previews: 408
missing event ids: 0
readiness-selected merge effects: 377
readiness-blocked merge effects: 31
high-confidence subtype override candidates: 5
remaining review-first blockers after override analysis: 26
canonical outputs mutated: false
```

The expanded shadow-override preview was generated and validated:

```text
subset plan: data/reports/entity_resolution_ai_effects_plan_shadow_override_subset_samples500.json
preview report: data/reports/entity_resolution_ai_shadow_override_subset_samples500_preview_apply_report.json
shadow deduped events: data/canonical_preview_entity_resolution_ai_shadow_override_subset_samples500/deduped_events.jsonl
output check: data/reports/entity_resolution_ai_shadow_override_subset_samples500_preview_output_check.json
selected merge effects: 382
effects applied: 382
effects blocked: 0
projected event reduction: 338
preview event count: 944240
preview merge rows: 313
duplicate event ids: 0
malformed rows: 0
valid: true
canonical outputs mutated: false
```

The shadow-output validator now correctly handles connected merge groups where multiple merge effects collapse into one merged preview row. It validates preview rows against unique `preview_canonical_event_id` values from `applied_effects`, not raw effect count.

The ER readiness/filter lane was hardened for expanded packets:

```text
readiness reports now include full blocking_items and review_items arrays
ready-subset filtering now consumes full blocking_items when present
blocked-merge packet generation now consumes full blocking_items when present
fallback compatibility: blocking_items_sample remains supported for older reports
```

This fixes the expanded-lane failure mode where reports with more than 50 blockers could expose only the first sampled blockers to downstream filtering.

The ER review lane was expanded again to 1000 retained samples per band under separate artifact names:

```text
score report: data/reports/entity_resolution_score_report_samples1000.json
review packet: data/reports/entity_resolution_review_packet_samples1000.json
suggestions: data/reports/entity_resolution_review_suggestions_samples1000.jsonl
suggestions report: data/reports/entity_resolution_review_suggestions_samples1000_report.json
scored pairs: 325249
review packet items: 4000
suggestions: 4000
suggested same_event: 811
suggested needs_more_evidence: 3189
canonical outputs mutated: false
```

The samples1000 decisions/effects lane remains separate from the original 200-row baseline and the samples500 lane:

```text
decisions: data/canonical_full/entity_resolution_decisions_ai_accepted_samples1000.jsonl
validated decisions: data/canonical_full/entity_resolution_validated_decisions_ai_accepted_samples1000.jsonl
validation report: data/reports/entity_resolution_ai_decisions_validation_samples1000_report.json
effects plan: data/reports/entity_resolution_ai_effects_plan_samples1000.json
impact summary: data/reports/entity_resolution_ai_effect_impact_samples1000_summary.json
valid decisions: 4000
invalid decisions: 0
planned merge effects: 811
planned defer effects: 3189
projected event reduction before readiness filtering: 811
canonical outputs mutated: false
```

The samples1000 compact merge preview/readiness lane found 754 merge effects ready for shadow preview and 57 requiring review-first or override analysis:

```text
merge patch: data/reports/entity_resolution_ai_merge_preview_patch_samples1000.json
merged preview: data/reports/entity_resolution_ai_merged_event_preview_samples1000.json
readiness: data/reports/entity_resolution_ai_merge_readiness_samples1000.json
ready subset: data/reports/entity_resolution_ai_effects_plan_ready_subset_samples1000.json
blocked packet: data/reports/entity_resolution_blocked_merge_review_packet_samples1000.json
blocked analysis: data/reports/entity_resolution_blocked_merge_analysis_samples1000.json
merge previews: 811
missing event ids: 0
readiness-selected merge effects: 754
readiness-blocked merge effects: 57
high-confidence subtype override candidates: 12
remaining review-first blockers after override analysis: 45
canonical outputs mutated: false
```

The samples1000 shadow-override preview was generated and validated:

```text
subset plan: data/reports/entity_resolution_ai_effects_plan_shadow_override_subset_samples1000.json
preview report: data/reports/entity_resolution_ai_shadow_override_subset_samples1000_preview_apply_report.json
shadow deduped events: data/canonical_preview_entity_resolution_ai_shadow_override_subset_samples1000/deduped_events.jsonl
output check: data/reports/entity_resolution_ai_shadow_override_subset_samples1000_preview_output_check.json
selected merge effects: 766
effects applied: 766
effects blocked: 0
projected event reduction: 619
preview event count: 943959
preview merge rows: 566
duplicate event ids: 0
malformed rows: 0
valid: true
canonical outputs mutated: false
```

The ER scorer now supports an optional report-only candidate worklist sidecar so one longer scorer pass can retain a larger cross-event review queue without changing canonical data or embedding the whole queue in the score report:

```text
scorer option: --candidate-worklist-output
retention option: --candidate-worklist-per-band-limit
band floor option: --candidate-worklist-min-band
worklist policy: entity_resolution_candidate_worklist_report_only
canonical outputs mutated: false
preview outputs written: false
decisions created: false
auto merge performed: false
```

A bounded smoke run verified the sidecar path:

```text
score report: data/reports/entity_resolution_score_report_worklist_smoke.json
worklist jsonl: data/reports/entity_resolution_candidate_worklist_smoke.jsonl
input limit: 50000
max scored pairs: 10000
worklist per-band limit: 50
scored pairs: 59
worklist items: 44
strong candidate rows: 3
moderate candidate rows: 41
candidate items embedded in score report: false
canonical outputs mutated: false
```

The ER review-packet builder can now consume that sidecar directly:

```text
packet input option: --candidate-worklist
packet source scope: candidate_worklist_jsonl
smoke packet json: data/reports/entity_resolution_review_packet_worklist_smoke.json
smoke packet csv: data/reports/entity_resolution_review_packet_worklist_smoke.csv
smoke packet markdown: data/reports/entity_resolution_review_packet_worklist_smoke.md
exported review items: 44
strong candidate rows: 3
moderate candidate rows: 41
candidate worklist used: true
canonical outputs mutated: false
decisions created: false
```

The full worklist-backed ER lane was generated from one full scorer pass:

```text
score report: data/reports/entity_resolution_score_report_with_worklist.json
candidate worklist: data/reports/entity_resolution_candidate_worklist.jsonl
review packet: data/reports/entity_resolution_review_packet_worklist.json
suggestions: data/reports/entity_resolution_review_suggestions_worklist.jsonl
decisions: data/canonical_full/entity_resolution_decisions_ai_accepted_worklist.jsonl
validated decisions: data/canonical_full/entity_resolution_validated_decisions_ai_accepted_worklist.jsonl
scored pairs: 325249
worklist rows: 15000
review packet rows: 15000
same_event suggestions: 4051
needs_more_evidence suggestions: 10949
valid decisions: 15000
invalid decisions: 0
planned merge effects: 4051
planned defer effects: 10949
projected event reduction before readiness filtering: 4051
canonical outputs mutated: false
```

The full worklist compact preview/readiness lane:

```text
merge patch: data/reports/entity_resolution_ai_merge_preview_patch_worklist.json
merged preview: data/reports/entity_resolution_ai_merged_event_preview_worklist.json
readiness: data/reports/entity_resolution_ai_merge_readiness_worklist.json
ready subset: data/reports/entity_resolution_ai_effects_plan_ready_subset_worklist.json
blocked packet: data/reports/entity_resolution_blocked_merge_review_packet_worklist.json
blocked analysis: data/reports/entity_resolution_blocked_merge_analysis_worklist.json
merge previews: 4051
missing event ids: 0
readiness-selected merge effects: 3782
readiness-blocked merge effects: 269
high-confidence subtype override candidates: 43
remaining review-first blockers after override analysis: 226
canonical outputs mutated: false
```

The worklist readiness-only and shadow-override previews were generated and validated:

```text
ready preview report: data/reports/entity_resolution_ai_ready_subset_worklist_preview_apply_report.json
ready preview check: data/reports/entity_resolution_ai_ready_subset_worklist_preview_output_check.json
ready shadow deduped events: data/canonical_preview_entity_resolution_ai_ready_subset_worklist/deduped_events.jsonl
ready effects applied: 3782
ready projected event reduction: 2123
ready preview event count: 942455
ready preview merge rows: 1868
ready output valid: true

override subset plan: data/reports/entity_resolution_ai_effects_plan_shadow_override_subset_worklist.json
override preview report: data/reports/entity_resolution_ai_shadow_override_subset_worklist_preview_apply_report.json
override preview check: data/reports/entity_resolution_ai_shadow_override_subset_worklist_preview_output_check.json
override shadow deduped events: data/canonical_preview_entity_resolution_ai_shadow_override_subset_worklist/deduped_events.jsonl
override effects applied: 3825
override projected event reduction: 2147
override preview event count: 942431
override preview merge rows: 1889
override output valid: true
canonical outputs mutated: false
```

The worklist override delta and apply-readiness gates remain blocked for canonical mutation:

```text
delta summary: data/reports/entity_resolution_shadow_override_delta_worklist_summary.json
apply readiness: data/reports/entity_resolution_canonical_apply_readiness_worklist.json
override effects added: 43
incremental projected event reduction: 24
remaining excluded merge effects: 226
ready for canonical apply: false
canonical apply blockers: 3
canonical outputs mutated: false
```

The worklist merge-body policy preview also validates at the larger lane size:

```text
policy proposal: data/reports/entity_resolution_canonical_merge_policy_proposal_worklist.json
policy body preview: data/reports/entity_resolution_policy_body_preview_worklist.json
policy body check: data/reports/entity_resolution_policy_body_preview_worklist_check.json
policy body previews: 3825
skipped previews: 226
invalid conflict metadata: 0
valid: true
canonical outputs mutated: false
```

Added a report-only ER lane comparison summary:

```text
summary: data/reports/entity_resolution_lane_comparison.json
summary policy: entity_resolution_lane_comparison_report_only
lanes compared: baseline_200, samples500, samples1000, worklist15000
current event count: 944578
best override projected event reduction: 2147
best override preview event count: 942431
UFOSINT screenshot benchmark: 618316
remaining gap after best override preview: 324115
canonical outputs mutated: false
```

The comparison makes the current limitation explicit: expanding the conservative pairwise ER lane improves quality and catches real duplicate clusters, but by itself it is far short of the roughly 618k-sighting benchmark. Closing that larger gap likely needs broader cluster/entity-resolution strategy, not just larger top-N pair packets.

Regenerated the expanded dedupe opportunity report with a wider top-group sample:

```text
report: data/reports/expanded_dedupe_opportunity_report_top500.json
top groups retained per family: 500
scanned source records: 971115
current event count: 944578
conservative projected reduction: 49627
moderate projected reduction: 49654
exploratory projected reduction: 52284
aggressive projected reduction: 76360
canonical outputs mutated: false
```

Added a report-only cluster review packet for the top opportunity groups:

```text
json: data/reports/entity_resolution_cluster_review_packet.json
csv: data/reports/entity_resolution_cluster_review_packet.csv
markdown: data/reports/entity_resolution_cluster_review_packet.md
packet policy: entity_resolution_cluster_review_only
exported cluster items: 5045
conservative cluster items: 1001
moderate cluster items: 500
exploratory cluster items: 1000
aggressive cluster items: 2544
projected reduction sum, not deduped: 35974
canonical outputs mutated: false
decisions created: false
```

This packet is not an apply path. It is a review/planning surface for cluster-level ER work, especially same-source-native-id/date groups and same-source/date/location/time families that pairwise top-N review under-samples.

Added a cluster packet checker:

```text
check: data/reports/entity_resolution_cluster_review_packet_check.json
check policy: entity_resolution_cluster_review_packet_check
valid: true
cluster items: 5045
duplicate cluster review ids: 0
missing required fields: 0
canonical outputs mutated: false
```

Regenerated the top-500 expanded dedupe opportunity report with bounded current-event IDs exported per top group, then rebuilt the cluster review packet:

```text
report: data/reports/expanded_dedupe_opportunity_report_top500.json
top groups retained per family: 500
top group current-event ID export cap: 300
cluster packet: data/reports/entity_resolution_cluster_review_packet.json
cluster items: 5045
cluster items with current_event_ids: 5045
max exported current_event_ids in one cluster: 90
truncated current_event_id lists: 0
cluster packet check valid: true
current_event_id overflow count: 0
current_event_id truncation mismatch count: 0
canonical outputs mutated: false
full pytest: 211 passed
```

This makes the cluster packet actionable for review: each cluster target now carries the current canonical event IDs needed to inspect or later build explicit cluster-level decisions. It remains report-only and does not apply or approve any merge.

Added the first report-only cluster decision validation lane:

```text
validator: scripts/validate_entity_resolution_cluster_decisions.py
normalized decisions: data/canonical_full/entity_resolution_validated_cluster_decisions.jsonl
validation report: data/reports/entity_resolution_cluster_decisions_validation_report.json
cluster effects plan: data/reports/entity_resolution_cluster_effects_plan.json
cluster effect impact: data/reports/entity_resolution_cluster_effect_impact_summary.json
input cluster decisions present: 0
valid cluster decisions: 0
planned cluster effects: 0
projected cluster reduction from reviewed decisions: 0
canonical outputs mutated: false
full pytest: 216 passed
```

The validator requires an explicit `cluster_review_id` decision and rejects full-cluster `same_event` decisions when exported `current_event_ids` are missing, truncated, or count-mismatched. Cluster outputs use separate filenames so their reductions are not accidentally mixed with pairwise ER lanes.

Added a conservative cluster suggestion and AI-accepted promotion lane, then ran it through validation, plan-only impact, compact preview, readiness, and blocked-analysis gates:

```text
suggestion script: scripts/ai_suggest_entity_resolution_cluster_decisions.py
promotion script: scripts/promote_entity_resolution_cluster_suggestions.py
suggestions: data/reports/entity_resolution_cluster_review_suggestions.jsonl
suggestions report: data/reports/entity_resolution_cluster_review_suggestions_report.json
AI-accepted decisions: data/canonical_full/entity_resolution_cluster_decisions_ai_accepted.jsonl
validated AI decisions: data/canonical_full/entity_resolution_validated_cluster_decisions_ai_accepted.jsonl
AI decisions validation report: data/reports/entity_resolution_cluster_ai_decisions_validation_report.json
AI effects plan: data/reports/entity_resolution_cluster_ai_effects_plan.json
AI impact summary: data/reports/entity_resolution_cluster_ai_effect_impact_summary.json
compact merge patch: data/reports/entity_resolution_cluster_ai_merge_preview_patch.json
compact merged-event preview: data/reports/entity_resolution_cluster_ai_merged_event_preview.json
readiness: data/reports/entity_resolution_cluster_ai_merge_readiness.json
blocked packet: data/reports/entity_resolution_cluster_blocked_merge_review_packet.json
blocked analysis: data/reports/entity_resolution_cluster_blocked_merge_analysis.json
ready subset: data/reports/entity_resolution_cluster_ai_effects_plan_ready_subset.json
shadow override subset: data/reports/entity_resolution_cluster_ai_effects_plan_shadow_override_subset.json
cluster suggestions: 5045
same_event suggestions: 554
needs_more_evidence suggestions: 4491
validated cluster decisions: 5045
invalid cluster decisions: 0
merge effects: 554
projected reduction before readiness: 1504
compact preview missing event ids: 0
readiness blockers: 538
readiness review-only conflicts: 9
ready merge effects: 16
high-confidence override candidates: 2
shadow-override selected merge effects: 18
canonical outputs mutated: false
full pytest: 223 passed
```

The blocker analyzer now classifies time-only conflicts instead of leaving them unclassified. It also parses true time-format variants such as `1630` vs `16:30` into high-confidence override candidates while leaving genuinely different times review-first. Current blocked-cluster classifications are: coordinate conflict requires review 32, likely source subtype variant 2, likely time-format variant 16, time conflict requires review 174, time-format or multiple-time variant 230, and type conflict requires review 84. The cluster shadow-override subset now selects 34 merge effects: 16 readiness-clean effects plus 18 high-confidence override candidates.

Regenerated the ER lane comparison with the cluster lane included:

```text
summary: data/reports/entity_resolution_lane_comparison.json
lanes compared: 5
cluster lane: cluster_ai_conservative
cluster review packet items: 5045
cluster same_event suggestions: 554
cluster pre-readiness projected reduction: 1504
cluster ready merge effects: 16
cluster shadow-override selected merge effects: 34
cluster shadow-override projected reduction without full preview: 61
best pairwise/worklist override projected reduction remains: 2147
remaining gap after best existing override preview: 324115
canonical outputs mutated: false
full pytest: 223 passed
```

Added joined blocked-merge action packets for cluster blocker triage:

```text
builder: scripts/build_entity_resolution_blocked_merge_action_packet.py
all-blocker packet: data/reports/entity_resolution_cluster_blocked_merge_action_packet.json
all-blocker CSV: data/reports/entity_resolution_cluster_blocked_merge_action_packet.csv
all-blocker markdown: data/reports/entity_resolution_cluster_blocked_merge_action_packet.md
time-blocker packet: data/reports/entity_resolution_cluster_time_blocker_action_packet.json
time-blocker CSV: data/reports/entity_resolution_cluster_time_blocker_action_packet.csv
time-blocker markdown: data/reports/entity_resolution_cluster_time_blocker_action_packet.md
all blocked action items: 538
time blocked action items: 420
likely time-format variant items: 16
cluster shadow-override selected merge effects after time parsing: 34
cluster shadow-override projected reduction without full preview: 61
canonical outputs mutated: false
full pytest: 227 passed
```

These packets join readiness-blocked merge details back to the blocker classifications and source summary fields, so the next review pass can target time-format/multiple-time blockers without changing readiness or apply behavior.

Added a cluster-specific canonical merge policy/body-preview checkpoint for the 34-effect cluster shadow-override subset:

```text
policy helper: scripts/propose_entity_resolution_canonical_merge_policy.py
policy proposal: data/reports/entity_resolution_cluster_canonical_merge_policy_proposal.json
policy: entity_resolution_cluster_canonical_merge_policy_proposal_v1
policy body preview: data/reports/entity_resolution_cluster_policy_body_preview.json
preview policy: entity_resolution_cluster_canonical_merge_body_policy_preview_only
policy body check: data/reports/entity_resolution_cluster_policy_body_preview_check.json
observed cluster merge previews: 554
selected policy body previews: 34
skipped blocked/excluded previews: 520
cluster shadow-override projected reduction: 61
remaining excluded merge effects: 520
policy body preview valid: true
invalid conflict metadata count: 0
canonical outputs mutated: false
focused policy pytest: 10 passed
full pytest: 230 passed
```

The proposal helper now accepts the cluster lane's `entity_resolution_plan_impact_summary_only` and `entity_resolution_merge_preview_readiness_gate` report shapes while preserving the existing pairwise-lane defaults. The body-preview/check scripts now accept explicit cluster policy identifiers while preserving the existing pairwise/worklist policy identifiers, so this stays a compact report-only validation step and still does not implement canonical apply.

Regenerated `data/reports/entity_resolution_lane_comparison.json` after wiring in the cluster policy-body check. The `cluster_ai_conservative` lane now reports `policy_body_preview_count: 34` and `policy_body_preview_valid: true`; best existing pairwise/worklist override reduction remains 2,147 and the remaining screenshot-benchmark gap remains 324,115.

Added an explicit cluster canonical-apply readiness gate:

```text
checker: scripts/check_entity_resolution_cluster_canonical_apply_readiness.py
readiness: data/reports/entity_resolution_cluster_canonical_apply_readiness.json
apply readiness policy: entity_resolution_cluster_canonical_apply_readiness_gate
selected cluster merge effects: 34
excluded cluster merge effects: 520
policy body preview valid: true
ready for canonical apply: false
canonical apply blockers: 4
blockers: cluster_full_shadow_preview_missing, canonical_apply_command_not_implemented, cluster_review_first_merge_candidates_remaining, cluster_merge_preview_blocking_conflicts_remaining
canonical outputs mutated: false
focused readiness/lane pytest: 3 passed
```

Regenerated `data/reports/entity_resolution_lane_comparison.json` again after wiring in the cluster apply-readiness report. Before the full cluster shadow preview existed, the cluster lane recorded `ready_for_canonical_apply: false` and `canonical_apply_blocker_count: 4`.

Ran the full shadow preview for the 34-effect cluster shadow-override subset:

```text
preview report: data/reports/entity_resolution_cluster_ai_shadow_override_subset_preview_apply_report.json
preview output: data/canonical_preview_entity_resolution_cluster_ai_shadow_override_subset/deduped_events.jsonl
preview output check: data/reports/entity_resolution_cluster_ai_shadow_override_subset_preview_output_check.json
effects requested: 34
effects applied: 34
effects blocked: 0
projected event reduction: 61
validated preview row count: 944517
validated preview merge rows: 34
preview output valid: true
canonical outputs mutated: false
```

Regenerated `data/reports/entity_resolution_cluster_canonical_apply_readiness.json` with that shadow-preview evidence included. The missing-shadow-preview blocker is now cleared, but `ready_for_canonical_apply` remains false with 3 hard blockers: canonical apply command not implemented, 520 cluster merge effects still excluded, and 538 blocking conflicts still present in the full compact cluster merge preview. Regenerated `data/reports/entity_resolution_lane_comparison.json`; the cluster lane now reports `override_effects_applied: 34`, `override_projected_event_reduction: 61`, `override_preview_event_count: 944517`, `override_preview_valid: true`, and `canonical_apply_blocker_count: 3`.

Added a report-only priority queue for the remaining cluster blockers:

```text
builder: scripts/build_entity_resolution_cluster_blocker_priority_queue.py
queue JSON: data/reports/entity_resolution_cluster_blocker_priority_queue.json
queue CSV: data/reports/entity_resolution_cluster_blocker_priority_queue.csv
queue markdown: data/reports/entity_resolution_cluster_blocker_priority_queue.md
queue policy: entity_resolution_cluster_blocker_priority_queue_review_only
source blocked action items: 538
already-selected shadow overrides excluded: 18
remaining queue items: 520
projected reduction sum, not deduped: 1443
time-format review items: 230
time-conflict review items: 174
type-conflict review items: 84
coordinate-conflict review items: 32
canonical outputs mutated: false
focused pytest: 6 passed
```

The queue deliberately excludes the 18 already-selected shadow override candidates by default and ranks the remaining blockers by review bucket before projected reduction. `data/reports/entity_resolution_lane_comparison.json` now surfaces the cluster queue counts on the `cluster_ai_conservative` lane so the lane report shows both current preview status and the remaining review queue.

Regenerated the joined all-blocker and time-blocker action packets so their source summaries now carry bounded audit IDs: `canonical_event_ids`, `canonical_input_ids`, and associated counts. The priority queue preserves those IDs into JSON/CSV/Markdown review surfaces, so follow-up triage can jump back to exact current canonical events without creating decisions.

Added a report-only time-normalization analysis for the 230 `time_format_review` blockers:

```text
analyzer: scripts/analyze_entity_resolution_cluster_time_normalization.py
analysis JSON: data/reports/entity_resolution_cluster_time_normalization_analysis.json
analysis CSV: data/reports/entity_resolution_cluster_time_normalization_analysis.csv
analysis markdown: data/reports/entity_resolution_cluster_time_normalization_analysis.md
analysis policy: entity_resolution_cluster_time_normalization_review_only
analyzed items: 230
lower-risk review items: 57
medium-risk review items: 142
high-risk review items: 31
single exact minute: 1
single exact minute with context tokens: 85
nearby exact minutes <=15m: 56
nearby exact minutes <=60m: 47
multiple distinct exact minutes: 31
fuzzy bucket only: 6
fuzzy or ambiguous only: 4
canonical outputs mutated: false
```

This is still not a merge approval surface. It parses time tokens into exact/fuzzy/ambiguous/unknown groups and ranks lower-risk review cases first so a future pass can focus on time normalization evidence before creating any new explicit cluster decisions.

Regenerated `data/reports/entity_resolution_lane_comparison.json` again so the cluster lane now includes `time_normalization_analyzed_items: 230` plus the time-normalization classification and risk-tier counts.

Built and validated a strict v2 time-normalization shadow-preview subset:

```text
builder: scripts/build_entity_resolution_cluster_time_norm_shadow_override_subset.py
subset JSON: data/reports/entity_resolution_cluster_time_norm_shadow_override_subset.json
effect impact: data/reports/entity_resolution_cluster_time_norm_shadow_override_effect_impact_summary.json
preview report: data/reports/entity_resolution_cluster_time_norm_shadow_override_subset_preview_apply_report.json
preview output: data/canonical_preview_entity_resolution_cluster_time_norm_shadow_override_subset/deduped_events.jsonl
preview output check: data/reports/entity_resolution_cluster_time_norm_shadow_override_subset_preview_output_check.json
subset policy: entity_resolution_cluster_time_normalization_shadow_preview_subset_v2
base selected cluster shadow effects: 34
new strict time-normalization effects: 44
selected effects total: 78
excluded merge effects: 476
effects applied in shadow preview: 78
effects blocked in shadow preview: 0
projected event reduction: 120
preview rows: 944,458
preview merge rows: 78
preview output valid: true
canonical outputs mutated: false
```

The v2 subset is still preview-only. It adds hard gates beyond the time parser classification: candidates must be `time_raw`-only blockers, lower risk, exact-minute span <=15 minutes, free of fuzzy/ambiguous/unknown tokens, and have a single source name, single source-native ID, single date, single location, and at least two canonical events in the source summary. Regenerated `data/reports/entity_resolution_lane_comparison.json` so the cluster lane now surfaces these v2 preview counts.

Validation:

```text
JSON validation: 6 entity-resolution/status reports parsed successfully
focused pytest before extra hardening: 6 passed
identity-gate focused pytest: 8 passed
full pytest after extra hardening: 249 passed
```

Added a report-only analysis for the remaining cluster `time_conflict_review` blockers:

```text
analyzer: scripts/analyze_entity_resolution_cluster_time_conflicts.py
analysis JSON: data/reports/entity_resolution_cluster_time_conflict_analysis.json
analysis CSV: data/reports/entity_resolution_cluster_time_conflict_analysis.csv
analysis markdown: data/reports/entity_resolution_cluster_time_conflict_analysis.md
analysis policy: entity_resolution_cluster_time_conflict_review_only
analyzed items: 174
lower-risk review items after approximate/coordinate-risk gates: 0
medium-risk review items after approximate/coordinate-risk gates: 0
high-risk review items after approximate/coordinate-risk gates: 174
single source/source-native-ID/date/location identity: 146
mixed or incomplete identity: 28
items with coordinate-risk flags: 154
items without coordinate-risk flags: 20
nearby exact conflicts <=5m: 15
nearby exact conflicts <=15m: 9
nearby exact conflicts <=15m with approximation: 3
nearby exact conflicts <=15m with context: 8
nearby exact conflicts <=60m: 28
single exact with fuzzy context: 37
single exact with approximation context: 1
wide exact conflicts >60m: 33
ambiguous or unknown conflicts: 28
fuzzy bucket only conflicts: 2
canonical outputs mutated: false
focused pytest: 3 passed
JSON validation: 3 report/status files parsed successfully
full pytest: 251 passed
```

Regenerated `data/reports/entity_resolution_lane_comparison.json` so the cluster lane now includes the time-conflict classification, risk-tier, and identity-consistency counts. After subagent review, approximate time markers and coordinate-drift risk now keep otherwise-close conflicts out of lower-risk buckets. This remains a triage surface only; no decisions, override subset, preview apply, or canonical mutation were created from time conflicts.

Added a report-only analysis for the remaining cluster `type_conflict_review` blockers:

```text
analyzer: scripts/analyze_entity_resolution_cluster_type_conflicts.py
analysis JSON: data/reports/entity_resolution_cluster_type_conflict_analysis.json
analysis CSV: data/reports/entity_resolution_cluster_type_conflict_analysis.csv
analysis markdown: data/reports/entity_resolution_cluster_type_conflict_analysis.md
analysis policy: entity_resolution_cluster_type_conflict_review_only
analyzed items: 84
high-risk review items: 84
single source/source-native-ID/date/location identity: 80
mixed or incomplete identity: 4
type + time conflicts: 65
type + time + coordinate conflicts: 15
type-only cross-family conflicts: 3
type-only single-family subcode conflicts: 1
canonical outputs mutated: false
focused pytest: 3 passed
JSON validation: 5 report/status files parsed successfully
full pytest: 255 passed
```

Regenerated `data/reports/entity_resolution_lane_comparison.json` so the cluster lane now includes type-conflict classification, risk-tier, and identity-consistency counts. The lone type-only single-family subcode case still remains high risk under the current gates, so this did not create a preview subset or canonical change.

Added a report-only analysis for the remaining cluster `coordinate_conflict_review` blockers:

```text
analyzer: scripts/analyze_entity_resolution_cluster_coordinate_conflicts.py
analysis JSON: data/reports/entity_resolution_cluster_coordinate_conflict_analysis.json
analysis CSV: data/reports/entity_resolution_cluster_coordinate_conflict_analysis.csv
analysis markdown: data/reports/entity_resolution_cluster_coordinate_conflict_analysis.md
analysis policy: entity_resolution_cluster_coordinate_conflict_review_only
analyzed items: 32
high-risk review items: 32
single source/source-native-ID/date/location identity: 31
mixed or incomplete identity: 1
coordinate conflicts 10-15km: 8
coordinate conflicts 15-50km: 11
coordinate conflicts 50-150km: 7
coordinate conflicts over 150km: 6
maximum coordinate distance: 357.423km
canonical outputs mutated: false
focused pytest: 3 passed
```

Regenerated `data/reports/entity_resolution_lane_comparison.json` so the cluster lane now includes coordinate-conflict classification, risk-tier, identity-consistency, and max-distance metrics. Coordinate conflicts remain source/map review only; no decisions, override subset, preview apply, or canonical mutation were created.

Added a consolidated report-only blocker analysis checkpoint:

```text
builder: scripts/summarize_entity_resolution_cluster_blocker_analysis_suite.py
summary JSON: data/reports/entity_resolution_cluster_blocker_analysis_suite_summary.json
summary markdown: data/reports/entity_resolution_cluster_blocker_analysis_suite_summary.md
summary policy: entity_resolution_cluster_blocker_analysis_suite_report_only
queue items: 520
strict time-normalization new preview candidates: 44
remaining time-format review items: 186
time-conflict high-risk items: 174 / 174
type-conflict high-risk items: 84 / 84
coordinate-conflict high-risk items: 32 / 32
preview-safe new candidate class: strict_time_normalization_only
canonical outputs mutated: false
focused pytest: 2 passed
JSON validation: 3 report/status files parsed successfully
full pytest: 257 passed
```

This is now the fastest checkpoint for the current cluster blocker state: only the 44 strict time-normalization candidates are plausible preview candidates under current gates; all time/type/coordinate conflicts remain source-row review work.

Added a source-row evidence packet for the 44 strict time-normalization candidates:

```text
builder: scripts/build_entity_resolution_cluster_time_norm_source_evidence_packet.py
packet JSON: data/reports/entity_resolution_cluster_time_norm_source_evidence_packet.json
packet CSV: data/reports/entity_resolution_cluster_time_norm_source_evidence_packet.csv
packet markdown: data/reports/entity_resolution_cluster_time_norm_source_evidence_packet.md
packet policy: entity_resolution_cluster_time_normalization_source_row_evidence_review_only
candidate effects: 44
requested canonical events: 103
matched canonical events: 103
missing canonical events: 0
candidate input IDs: 173
evidence input IDs from current rows/provenance: 281
candidate input IDs missing from evidence: 0
projected event reduction represented by these 44 candidates: 59
canonical outputs mutated: false
focused pytest: 2 passed
full pytest: 319 passed
```

The evidence packet scans `data/canonical_full/deduped_events.jsonl` once and extracts only the current canonical rows behind strict time-normalization candidates, including raw source row data, compact raw date/time/location/source fields, source provenance, dates, times, locations, coordinates, type/shape, summaries, description excerpts, conflict flags, and reviewer prompts. It targets only `shadow_preview_override_reason == strict_time_normalization_candidate`, so it does not mix in the older 34-effect base shadow subset. This remains source-row review evidence only; it does not create accepted ER decisions or mark the 44 candidates as canonical-apply ready.

Validation:

```text
JSON validation: 4 report/status files parsed successfully
full pytest: 259 passed
```

Added conservative source-review recommendations for the 44 strict time-normalization candidates:

```text
builder: scripts/recommend_entity_resolution_cluster_time_norm_source_decisions.py
recommendations JSON: data/reports/entity_resolution_cluster_time_norm_source_review_recommendations.json
recommendations CSV: data/reports/entity_resolution_cluster_time_norm_source_review_recommendations.csv
recommendations markdown: data/reports/entity_resolution_cluster_time_norm_source_review_recommendations.md
recommendation policy: entity_resolution_time_norm_auto_recommendation_only
packet items reviewed: 44
recommend same-event review candidates: 33
needs more evidence: 11
clean clock-token items: 34
symbolic/shorthand time-token items: 10
non-time conflict deferred items: 1
recommended projected event reduction: 40
deferred projected event reduction: 19
duplicate review item IDs: 0
duplicate effect IDs: 0
canonical outputs mutated: false
decisions created: false
ready for canonical apply: false
focused pytest: 3 passed
```

The recommendation layer is stricter than the strict time-normalization preview subset. It recommends only clean 3-4 digit HHMM/HMM clock-token cases with time-only conflicts and complete evidence coverage. It defers symbolic or shorthand time tokens such as `00+`, `20`, and `21+`, and it also deferred one clean-token item because the source evidence still shows a non-time shape conflict. This report does not create validated decisions, effects, preview output, or canonical changes.

Built an isolated preview lane from only the 33 clean recommended time-normalization candidates:

```text
decision candidate builder: scripts/promote_time_norm_source_recommendations_to_decision_candidates.py
decision candidates: data/reports/entity_resolution_cluster_time_norm_recommended_decision_candidates.jsonl
decision candidate report: data/reports/entity_resolution_cluster_time_norm_recommended_decision_candidates_report.json
effects plan: data/reports/entity_resolution_cluster_time_norm_recommended_effects_plan.json
preview deduped events: data/canonical_preview_entity_resolution_cluster_time_norm_recommended/deduped_events.jsonl
preview apply report: data/reports/entity_resolution_cluster_time_norm_recommended_preview_apply_report.json
preview output check: data/reports/entity_resolution_cluster_time_norm_recommended_preview_output_check.json
merge preview patch: data/reports/entity_resolution_cluster_time_norm_recommended_merge_preview_patch.json
merged event preview: data/reports/entity_resolution_cluster_time_norm_recommended_merged_event_preview.json
policy body subset: data/reports/entity_resolution_cluster_time_norm_recommended_policy_body_subset.json
policy body preview: data/reports/entity_resolution_cluster_time_norm_recommended_policy_body_preview.json
policy body preview check: data/reports/entity_resolution_cluster_time_norm_recommended_policy_body_preview_check.json
policy conflict classification: data/reports/entity_resolution_cluster_time_norm_recommended_policy_conflict_classification.json
canonical apply contract check: data/reports/entity_resolution_cluster_time_norm_recommended_canonical_apply_contract_check.json
canonical body dry run: data/reports/entity_resolution_cluster_time_norm_recommended_canonical_body_dry_run.jsonl
canonical body dry run report: data/reports/entity_resolution_cluster_time_norm_recommended_canonical_body_dry_run_report.json
canonical body dry run check: data/reports/entity_resolution_cluster_time_norm_recommended_canonical_body_dry_run_check.json
accepted decisions: data/canonical_full/entity_resolution_cluster_time_norm_recommended_accepted_decisions.jsonl
acceptance report: data/reports/entity_resolution_cluster_time_norm_recommended_acceptance_report.json
accepted effects plan: data/reports/entity_resolution_cluster_time_norm_recommended_accepted_effects_plan.json
stream-applied candidate corpus: data/canonical_time_norm_recommended/deduped_events.jsonl
stream-apply report: data/reports/entity_resolution_cluster_time_norm_recommended_canonical_apply_report.json
stream-apply output check: data/reports/entity_resolution_cluster_time_norm_recommended_canonical_apply_output_check.json
candidate compact-web smoke: data/canonical_web_time_norm_recommended_smoke
candidate compact-web smoke readiness: data/reports/canonical_web_time_norm_recommended_smoke_runtime_readiness.json
candidate compact-web full: data/canonical_web_time_norm_recommended
candidate compact-web full readiness: data/reports/canonical_web_time_norm_recommended_runtime_readiness.json
candidate primary trace payload: data/canonical_web_time_norm_recommended_static_primary_trace_payload
candidate static payload readiness: data/reports/canonical_web_time_norm_recommended_static_payload_readiness.json
apply readiness: data/reports/entity_resolution_cluster_time_norm_recommended_apply_readiness.json
decision candidates: 33
skipped recommendations: 11
planned effects: 33
preview effects applied: 33
preview effects blocked: 0
projected event reduction: 40
preview row count: 944538
preview merge rows: 33
preview output valid: true
merge patches: 33
hydrated merged-event previews: 33
missing event IDs: 0
policy body previews: 33
invalid policy-body conflict metadata: 0
policy conflict low-risk candidates: 33
policy conflict blockers: 0
canonical apply contract valid: true
canonical apply contract validation errors: 0
canonical body dry-run rows: 33
canonical body dry-run valid: true
canonical body dry-run incomplete conflict source values: 0
accepted decisions: 33
accepted plan-only effects: 33
stream-apply input rows: 944578
stream-apply output rows: 944538
stream-apply replacement rows: 33
stream-apply suppressed rows: 40
stream-apply output check valid: true
stream-apply suppressed IDs still present: 0
candidate compact-web smoke events: 10000
candidate compact-web smoke mapped events: 2534
candidate compact-web smoke readiness: ready_for_preview
candidate compact-web full events: 944538
candidate compact-web full mapped events: 289791
candidate compact-web full raw MB: 2135.05
candidate compact-web full gzip MB: 405.4
candidate compact-web startup gzip MB: 7.07
candidate compact-web readiness: ready_for_preview
candidate static payload status: ready
candidate static payload files: 212
candidate static payload event chunks: 0
apply readiness: true
canonical apply blockers: 0
canonical outputs mutated: false
canonical candidate apply performed: true
ready for canonical apply: true
focused promotion pytest: 2 passed
focused lane/recommendation pytest: 4 passed
focused apply-readiness pytest: 2 passed
focused policy-body subset pytest: 2 passed
focused policy-conflict pytest: 4 passed
focused canonical contract/body dry-run pytest: 8 passed
focused acceptance/readiness pytest: 6 passed
focused stream-apply/check pytest: 6 passed
```

This lane is a narrower preview than the 78-effect shadow subset. It intentionally excludes 11 source-review cases and writes only shadow preview output under `data/canonical_preview_entity_resolution_cluster_time_norm_recommended/`. The newer full-row checks confirm the policy conflicts are low risk, the preview output contract is valid, and dry-run canonical merge rows can be constructed with complete conflict source values. The accepted-decision artifact clears the decision-state blocker without applying merges. The stream-safe apply command then writes a separate canonical candidate corpus under `data/canonical_time_norm_recommended/` without overwriting `data/canonical_full/`. The readiness gate now reports 0 blockers for this narrow lane. Candidate compact-web artifacts and a guarded primary-catalog + trace-runtime payload were rebuilt and validated, but runtime/static promotion remains separate because the default bundle still keeps canonical web artifacts disabled.

Validation:

```text
JSON validation: 14 recommendation/preview/status reports parsed successfully
full pytest: 289 passed
```

Added a conservative deferred-shorthand follow-up lane for the 11 previously skipped strict time-normalization cases:

```text
review builder: scripts/review_time_norm_deferred_shorthand_candidates.py
review JSON: data/reports/entity_resolution_cluster_time_norm_deferred_shorthand_review.json
review CSV: data/reports/entity_resolution_cluster_time_norm_deferred_shorthand_review.csv
review markdown: data/reports/entity_resolution_cluster_time_norm_deferred_shorthand_review.md
decision candidate builder: scripts/promote_time_norm_deferred_shorthand_review_to_decision_candidates.py
decision candidates: data/reports/entity_resolution_cluster_time_norm_deferred_shorthand_decision_candidates.jsonl
decision candidate report: data/reports/entity_resolution_cluster_time_norm_deferred_shorthand_decision_candidates_report.json
effects plan: data/reports/entity_resolution_cluster_time_norm_deferred_shorthand_effects_plan.json
merge preview patch: data/reports/entity_resolution_cluster_time_norm_deferred_shorthand_merge_preview_patch.json
canonical body dry run: data/reports/entity_resolution_cluster_time_norm_deferred_shorthand_canonical_body_dry_run.jsonl
canonical body dry run report: data/reports/entity_resolution_cluster_time_norm_deferred_shorthand_canonical_body_dry_run_report.json
canonical body dry run check: data/reports/entity_resolution_cluster_time_norm_deferred_shorthand_canonical_body_dry_run_check.json
review policy: entity_resolution_time_norm_deferred_shorthand_source_review_only
deferred input count: 11
source-reviewed same-event candidates: 9
remaining deferred candidates: 2
projected reduction from source-reviewed candidates: 17
decision candidates: 9
planned effects: 9
merge patches: 9
canonical body dry-run rows: 9
canonical body dry-run valid: true
canonical body dry-run validation errors: 0
canonical outputs mutated: false
preview outputs written: false
auto merge performed: false
ready for canonical apply: false
focused shorthand review/promote pytest: 8 passed
full pytest: 297 passed
```

This lane deliberately tightened the rule after review: `19+`/`1900` remains deferred because the original blocker includes insufficient distinct parsed minutes, and the Manhattan Beach row remains deferred because it has a non-time shape conflict. The 9 promoted candidates require time-only conflicts, same source/native/date/location evidence, identical normalized summary text, no missing IDs, at least two distinct parsed minute values, and shorthand/exact clock tokens within a 15-minute band.

Completed independent acceptance/apply gates for the 9 source-reviewed shorthand candidates and then built a combined 33+9 candidate corpus:

```text
shorthand preview apply report: data/reports/entity_resolution_cluster_time_norm_deferred_shorthand_preview_apply_report.json
shorthand preview output check: data/reports/entity_resolution_cluster_time_norm_deferred_shorthand_preview_output_check.json
shorthand accepted decisions: data/canonical_full/entity_resolution_cluster_time_norm_deferred_shorthand_accepted_decisions.jsonl
shorthand acceptance report: data/reports/entity_resolution_cluster_time_norm_deferred_shorthand_acceptance_report.json
shorthand accepted effects plan: data/reports/entity_resolution_cluster_time_norm_deferred_shorthand_accepted_effects_plan.json
shorthand stream-applied candidate corpus: data/canonical_time_norm_deferred_shorthand/deduped_events.jsonl
shorthand stream-apply report: data/reports/entity_resolution_cluster_time_norm_deferred_shorthand_canonical_apply_report.json
shorthand stream-apply output check: data/reports/entity_resolution_cluster_time_norm_deferred_shorthand_canonical_apply_output_check.json
combined accepted decisions: data/canonical_full/entity_resolution_cluster_time_norm_combined_accepted_decisions.jsonl
combined accepted decisions report: data/reports/entity_resolution_cluster_time_norm_combined_accepted_decisions_report.json
combined effects plan: data/reports/entity_resolution_cluster_time_norm_combined_effects_plan.json
combined merge preview patch: data/reports/entity_resolution_cluster_time_norm_combined_merge_preview_patch.json
combined canonical body dry run: data/reports/entity_resolution_cluster_time_norm_combined_canonical_body_dry_run.jsonl
combined canonical body dry run check: data/reports/entity_resolution_cluster_time_norm_combined_canonical_body_dry_run_check.json
combined stream-applied candidate corpus: data/canonical_time_norm_recommended_plus_shorthand/deduped_events.jsonl
combined stream-apply report: data/reports/entity_resolution_cluster_time_norm_combined_canonical_apply_report.json
combined stream-apply output check: data/reports/entity_resolution_cluster_time_norm_combined_canonical_apply_output_check.json
shorthand preview effects applied: 9
shorthand preview output valid: true
shorthand accepted decisions: 9
shorthand stream-apply output rows: 944561
shorthand stream-apply replacement rows: 9
shorthand suppressed IDs still present: 0
combined accepted decisions: 42
combined projected reduction: 57
combined canonical body dry-run valid: true
combined stream-apply output rows: 944521
combined replacement rows: 42
combined suppressed IDs still present: 0
canonical outputs mutated: false
```

Also generated the next source-row evidence packet for high-confidence `likely_time_format_variant` blockers:

```text
builder: scripts/build_entity_resolution_likely_time_format_source_evidence_packet.py
packet JSON: data/reports/entity_resolution_cluster_likely_time_format_source_evidence_packet.json
packet CSV: data/reports/entity_resolution_cluster_likely_time_format_source_evidence_packet.csv
packet markdown: data/reports/entity_resolution_cluster_likely_time_format_source_evidence_packet.md
packet policy: entity_resolution_likely_time_format_source_row_evidence_review_only
candidate effects: 16
requested canonical events: 33
matched canonical events: 33
missing canonical events: 0
candidate input IDs: 107
candidate input IDs missing from evidence: 0
projected event reduction: 17
canonical outputs mutated: false
full pytest: 305 passed
```

Completed strict review, acceptance, and stream-safe candidate apply gates for the 16 `likely_time_format_variant` cases, then built a combined 33+9+16 candidate corpus without mutating `data/canonical_full/deduped_events.jsonl`:

```text
likely review script: scripts/review_likely_time_format_candidates.py
likely decision candidate builder: scripts/promote_likely_time_format_review_to_decision_candidates.py
likely acceptance gate: scripts/accept_likely_time_format_decisions.py
likely review JSON: data/reports/entity_resolution_cluster_likely_time_format_review.json
likely decision candidates: data/reports/entity_resolution_cluster_likely_time_format_decision_candidates.jsonl
likely accepted decisions: data/canonical_full/entity_resolution_cluster_likely_time_format_accepted_decisions.jsonl
likely candidate corpus: data/canonical_time_norm_likely_time_format/deduped_events.jsonl
combined+likely accepted decisions: data/canonical_full/entity_resolution_cluster_time_norm_combined_plus_likely_accepted_decisions.jsonl
combined+likely candidate corpus: data/canonical_time_norm_recommended_plus_shorthand_plus_likely_time_format/deduped_events.jsonl
likely source-reviewed same-event candidates: 16
likely remaining deferred candidates: 0
likely projected reduction: 17
likely preview output valid: true
likely canonical body dry-run rows: 16
likely canonical body dry-run valid: true
likely stream-apply output rows: 944561
likely replacement rows: 16
likely suppressed IDs still present: 0
combined+likely accepted decisions: 58
combined+likely projected reduction: 74
combined+likely canonical body dry-run valid: true
combined+likely stream-apply output rows: 944504
combined+likely replacement rows: 58
combined+likely suppressed IDs still present: 0
canonical outputs mutated: false
full pytest: 317 passed
```

The likely lane is intentionally narrow: it accepts only source rows with a bare-hour token and an exact-clock token that parse to the same minute, with no non-time conflicts, same source/native/date/location/coordinate evidence, identical summary text, and no missing input/event evidence. The extended combined corpus preserves the earlier 42-decision combined output and writes a new `combined_plus_likely` path for comparison.

Added the next review-only evidence packet for the high-risk time-conflict context lane:

```text
builder: scripts/build_entity_resolution_time_conflict_context_source_evidence_packet.py
packet JSON: data/reports/entity_resolution_time_conflict_context_source_evidence_packet.json
packet CSV: data/reports/entity_resolution_time_conflict_context_source_evidence_packet.csv
packet markdown: data/reports/entity_resolution_time_conflict_context_source_evidence_packet.md
packet policy: entity_resolution_time_conflict_context_source_evidence_review_only
target classification: nearby_exact_conflict_15m_or_less_with_context
source time-conflict analysis items: 174
candidate effects: 8
requested canonical events: 24
matched canonical events: 24
missing canonical events: 0
candidate input IDs: 50
candidate input IDs missing from evidence: 0
projected event reduction: 16
canonical outputs mutated: false
focused pytest: 2 passed
full pytest: 321 passed
```

This is intentionally evidence-only. These rows remain high risk because the existing time-conflict analysis flags coordinate risk and, in some cases, mixed identity fields. No decisions, preview apply, accepted decisions, or candidate corpus were created from this lane.

Fixed lane-specific metadata in `scripts/check_time_norm_recommended_canonical_apply_output.py` so custom apply-output checks record the actual `--dry-run-rows` path instead of the default recommended-lane path. Regenerated the shorthand, combined 33+9, likely-time-format, and combined+likely apply-output checks; all remained valid with zero suppressed IDs present. Full pytest still reports 319 passed.

Added a review-only source evidence packet for the next exact-time/context-token lane:

```text
builder: scripts/build_entity_resolution_single_exact_context_source_evidence_packet.py
packet JSON: data/reports/entity_resolution_single_exact_context_source_evidence_packet.json
packet CSV: data/reports/entity_resolution_single_exact_context_source_evidence_packet.csv
packet markdown: data/reports/entity_resolution_single_exact_context_source_evidence_packet.md
packet policy: entity_resolution_single_exact_context_source_evidence_review_only
target classification: single_exact_minute_with_context_tokens
source time-normalization analysis items: 230
candidate effects: 85
requested canonical events: 203
matched canonical events: 203
missing canonical events: 0
candidate input IDs: 506
candidate input IDs missing from evidence: 0
time-only conflict items after hydration: 84
non-time conflict items after hydration: 1
projected event reduction: 118
canonical outputs mutated: false
focused pytest: 2 passed
```

This packet is evidence-only. It exposes the source rows behind exact-time plus context/fuzzy-word cases so a later compatibility review can reject incompatible context words before any decision candidate promotion.

Added the conservative source-review pass for the single-exact/context-token lane:

```text
review script: scripts/review_single_exact_context_candidates.py
review JSON: data/reports/entity_resolution_single_exact_context_review.json
review CSV: data/reports/entity_resolution_single_exact_context_review.csv
review markdown: data/reports/entity_resolution_single_exact_context_review.md
review policy: entity_resolution_single_exact_context_source_review_only
input packet policy: entity_resolution_single_exact_context_source_evidence_review_only
input items reviewed: 85
source-review same-event candidates: 32
needs-more-evidence rows: 53
candidate projected reduction: 40
deferred projected reduction: 78
canonical outputs mutated: false
preview outputs written: false
decisions created: false
ready for canonical apply: false
focused pytest: 7 passed
full pytest: 328 passed
```

This remains review-only. The same-event recommendation requires a single parsed exact minute, an exact clock token for that minute, only compatible fuzzy labels (`before_dawn`, `dawn`, `daytime`, `noon`, `dusk`, `evening`, `night`), no ambiguous/unknown tokens, time-only conflicts, strict source/native/date/location/coordinate/type/shape identity, identical nonempty source summary text, complete evidence coverage, and positive projected reduction. Approximation markers such as `?`, `+`, and `~` no longer count as exact-clock tokens.

Added the conservative source-review pass for the time-conflict/context lane:

```text
review script: scripts/review_time_conflict_context_candidates.py
review JSON: data/reports/entity_resolution_time_conflict_context_review.json
review CSV: data/reports/entity_resolution_time_conflict_context_review.csv
review markdown: data/reports/entity_resolution_time_conflict_context_review.md
review policy: entity_resolution_time_conflict_context_source_review_only
input packet policy: entity_resolution_time_conflict_context_source_evidence_review_only
input items reviewed: 8
source-review same-event candidates: 0
needs-more-evidence rows: 8
candidate projected reduction: 0
deferred projected reduction: 16
canonical outputs mutated: false
preview outputs written: false
decisions created: false
ready for canonical apply: false
focused pytest: 7 passed
full pytest: 335 passed
```

The result intentionally recommends no same-event candidates from this high-risk lane. All 8 rows still fail strict source-review conditions because each has non-time conflicts, coordinate risk, identity-risk flags, source-native mismatch, or ambiguous/unknown time tokens. No decisions, preview apply, accepted decisions, or candidate corpus were created.

Promoted and accepted only the 32 source-reviewed single-exact/context rows, then built a separate combined candidate corpus with all accepted time-normalization lanes:

```text
single-exact/context promotion: scripts/promote_single_exact_context_review_to_decision_candidates.py
single-exact/context acceptance: scripts/accept_single_exact_context_decisions.py
decision candidates: data/reports/entity_resolution_single_exact_context_decision_candidates.jsonl
accepted decisions: data/canonical_full/entity_resolution_single_exact_context_accepted_decisions.jsonl
single-exact/context candidate corpus: data/canonical_time_norm_single_exact_context/deduped_events.jsonl
combined accepted decisions: data/canonical_full/entity_resolution_cluster_time_norm_combined_plus_likely_plus_single_exact_context_accepted_decisions.jsonl
combined candidate corpus: data/canonical_time_norm_recommended_plus_shorthand_plus_likely_plus_single_exact_context/deduped_events.jsonl
single-exact/context decision candidates: 32
single-exact/context skipped review items: 53
single-exact/context projected reduction: 40
single-exact/context preview output valid: true
single-exact/context canonical body dry-run rows: 32
single-exact/context canonical body dry-run valid: true
single-exact/context accepted decisions: 32
single-exact/context stream-apply output rows: 944538
single-exact/context replacement rows: 32
single-exact/context suppressed IDs still present: 0
combined accepted decisions: 90
combined projected reduction: 114
combined canonical body dry-run valid: true
combined stream-apply output rows: 944464
combined replacement rows: 90
combined suppressed IDs still present: 0
canonical outputs mutated: false
focused pytest: 13 passed
full pytest: 344 passed
```

The single-exact/context acceptance gate explicitly records modifier-bearing tokens such as `13+` but requires clean exact-clock evidence from a separate unmodified token, so modifier tokens are not silently counted as exact-time proof. `data/canonical_full/deduped_events.jsonl` remains unchanged; the 944,464-row output is a separate candidate corpus for comparison/runtime staging only.

Regenerated the ER lane comparison so the cluster lane now reports the accepted combined time-normalization candidate corpus:

```text
summary: data/reports/entity_resolution_lane_comparison.json
summary policy: entity_resolution_lane_comparison_report_only
lanes compared: 5
combined time-normalization decisions: 90
combined projected reduction: 114
combined apply output rows: 944464
combined replacement rows: 90
combined suppressed IDs still present: 0
combined apply output valid: true
canonical outputs mutated: false
focused pytest: 1 passed
full pytest: 344 passed
```

This is report-only bookkeeping. It does not change the active canonical corpus or runtime/default bundle.

Built and validated compact web artifacts from the combined 90-decision time-normalization candidate corpus:

```text
candidate corpus: data/canonical_time_norm_recommended_plus_shorthand_plus_likely_plus_single_exact_context/deduped_events.jsonl
smoke compact-web output: data/canonical_web_time_norm_combined_plus_likely_plus_single_exact_context_smoke
smoke readiness: data/reports/canonical_web_time_norm_combined_plus_likely_plus_single_exact_context_smoke_runtime_readiness.json
full compact-web output: data/canonical_web_time_norm_combined_plus_likely_plus_single_exact_context
full readiness: data/reports/canonical_web_time_norm_combined_plus_likely_plus_single_exact_context_runtime_readiness.json
smoke events: 10,000
smoke mapped events: 2,533
smoke raw/gzip size: 23.79 MB / 4.73 MB
full events: 944,464
full mapped events: 289,717
full trace event rows: 288,444
full trace segment rows: 288,443
full event chunks: 378
full summary shards: 95
full raw/gzip size: 2,134.9 MB / 405.37 MB
full startup gzip: 7.07 MB
full lazy-detail gzip: 398.31 MB
readiness status: ready_for_preview
ready for startup preview: true
ready for primary catalog prototype: true
ready for primary catalog: false
static payload: data/canonical_web_time_norm_combined_plus_likely_plus_single_exact_context_static_primary_trace_payload
static payload readiness: data/reports/canonical_web_time_norm_combined_plus_likely_plus_single_exact_context_static_payload_readiness.json
static payload mode: primary-catalog-trace-runtime
static payload files: 212
static payload summary shards: 95
static payload event chunks: 0
static payload raw/gzip size: 590.25 MB / 74.8 MB
static payload status: ready
canonical outputs mutated: false
runtime/default config changed: false
post-update full pytest: 344 passed
```

The readiness blocker remains intentional: the app config keeps canonical web primary-catalog loading disabled until guarded UI parity smoke passes. These artifacts are sidecar preview/staging outputs only.

Added a stream-safe manual-review sidecar apply path and used it to measure the AI-assisted manual-review lane without deep-copying the full corpus:

```text
stream apply script: scripts/apply_manual_review_effects_stream.py
stream output checker: scripts/check_manual_review_stream_apply_output.py
focused pytest: 5 passed

manual-review plan: data/reports/manual_review_ai_effects_plan.json
manual-review stream report: data/reports/manual_review_ai_stream_apply_report.json
manual-review stream check: data/reports/manual_review_ai_stream_apply_output_check.json
manual-review candidate corpus: data/canonical_manual_review_ai_preview/deduped_events.jsonl
input rows: 944,578
output rows: 940,548
pairwise projected reduction: 4,984
component-collapsed actual reduction: 4,030
merge components: 2,546
replacement rows found: 2,546
suppressed IDs still present: 0
valid output check: true

composed input corpus: data/canonical_time_norm_recommended_plus_shorthand_plus_likely_plus_single_exact_context/deduped_events.jsonl
composed stream report: data/reports/manual_review_ai_after_time_norm_stream_apply_report.json
composed stream check: data/reports/manual_review_ai_after_time_norm_stream_apply_output_check.json
composed candidate corpus: data/canonical_time_norm_plus_manual_review_ai_preview/deduped_events.jsonl
composed input rows: 944,464
composed output rows: 940,477
manual-review actual reduction on time-normalized corpus: 3,987
net reduction from canonical_full: 4,101
composed merge components: 2,512
composed replacement rows found: 2,512
composed suppressed IDs still present: 0
composed valid output check: true
canonical outputs mutated: false
runtime/default config changed: false
```

Built and validated compact web artifacts for the composed time-normalization + manual-review sidecar:

```text
smoke compact-web output: data/canonical_web_time_norm_plus_manual_review_ai_preview_smoke
smoke readiness: data/reports/canonical_web_time_norm_plus_manual_review_ai_preview_smoke_runtime_readiness.json
full compact-web output: data/canonical_web_time_norm_plus_manual_review_ai_preview
full readiness: data/reports/canonical_web_time_norm_plus_manual_review_ai_preview_runtime_readiness.json
static payload: data/canonical_web_time_norm_plus_manual_review_ai_preview_static_primary_trace_payload
static payload readiness: data/reports/canonical_web_time_norm_plus_manual_review_ai_preview_static_payload_readiness.json
full events: 940,477
full mapped events: 285,962
full trace event rows: 284,689
full trace segment rows: 284,688
full event chunks: 377
full summary shards: 95
full raw/gzip size: 2,127.75 MB / 404.33 MB
startup gzip: 6.98 MB
static payload mode: primary-catalog-trace-runtime
static payload files: 212
static payload raw/gzip size: 587.23 MB / 74.32 MB
readiness status: ready_for_preview
static payload status: ready
ready for primary catalog: false
canonical outputs mutated: false
runtime/default config changed: false
full pytest: 353 passed
```

The component-based stream apply is intentionally more conservative than the earlier pairwise impact estimate. It resolves overlapping duplicate-pair decisions into connected components before writing replacement rows, so it avoids overcounting reductions and duplicate output IDs. The composed sidecar is still not canonical/default; promotion remains blocked on UI parity smoke and deeper merged-row conflict/body audit.

Added the merged-row conflict/body audit for the composed time-normalization + manual-review sidecar:

```text
audit script: scripts/audit_manual_review_stream_replacements.py
focused pytest: 2 passed
audit output: data/reports/manual_review_ai_after_time_norm_replacement_audit.json
audit csv: data/reports/manual_review_ai_after_time_norm_replacement_audit.csv
components audited: 2,512
source component rows found: 6,499
high-risk components: 37
medium-risk components: 1,384
low-risk components: 1,091
most common audit flags:
- time_raw_conflict: 1,245
- same_source_multiple_native_ids: 225
- coordinate_span_gt_5km: 148
- type_conflict: 147
- description_text_conflict: 143
- summary_text_conflict: 141
- location_text_conflict: 71
- coordinate_span_gt_50km: 37
canonical outputs mutated: false
runtime/default config changed: false
full pytest: 351 passed
```

This audit is intentionally promotion-blocking evidence, not a merge failure. The stream sidecar remains preview-only until the high/medium-risk replacement components are adjudicated or a stricter acceptance lane is created.

Created the stricter low-risk manual-review sidecar lane from that audit:

```text
filter script: scripts/filter_manual_review_effects_by_replacement_audit.py
filter report: data/reports/manual_review_ai_after_time_norm_low_risk_effects_plan_report.json
filtered effects plan: data/reports/manual_review_ai_after_time_norm_low_risk_effects_plan.json
allowed replacement-audit risk levels: low
selected replacement components: 1,091
selected merge effects: 1,808
excluded merge effects: 3,176
selected/excluded effect overlap: 0
selected/excluded component-event overlap: 0

candidate corpus: data/canonical_time_norm_plus_manual_review_ai_low_risk_preview/deduped_events.jsonl
stream apply report: data/reports/manual_review_ai_after_time_norm_low_risk_stream_apply_report.json
stream apply check: data/reports/manual_review_ai_after_time_norm_low_risk_stream_apply_output_check.json
input rows: 944,464
output rows: 942,768
actual event reduction: 1,696
replacement rows found: 1,091
suppressed IDs still present: 0
valid output check: true

low-risk replacement audit: data/reports/manual_review_ai_after_time_norm_low_risk_replacement_audit.json
low-risk replacement audit csv: data/reports/manual_review_ai_after_time_norm_low_risk_replacement_audit.csv
low-risk audit result: 0 high / 0 medium / 1,091 low

smoke compact-web output: data/canonical_web_time_norm_plus_manual_review_ai_low_risk_preview_smoke
smoke readiness: data/reports/canonical_web_time_norm_plus_manual_review_ai_low_risk_preview_smoke_runtime_readiness.json
full compact-web output: data/canonical_web_time_norm_plus_manual_review_ai_low_risk_preview
full readiness: data/reports/canonical_web_time_norm_plus_manual_review_ai_low_risk_preview_runtime_readiness.json
static payload: data/canonical_web_time_norm_plus_manual_review_ai_low_risk_preview_static_primary_trace_payload
static payload readiness: data/reports/canonical_web_time_norm_plus_manual_review_ai_low_risk_preview_static_payload_readiness.json
full events: 942,768
full mapped events: 288,092
full trace event rows: 286,819
full trace segment rows: 286,818
full raw/gzip size: 2,132.05 MB / 404.99 MB
startup gzip: 7.03 MB
static payload files: 212
static payload raw/gzip size: 588.01 MB / 74.59 MB
readiness status: ready_for_preview
static payload status: ready
ready for primary catalog: false
canonical outputs mutated: false
runtime/default config changed: false
full pytest: 362 passed
```

This low-risk lane trades fewer accepted reductions for much cleaner audit posture. It is still sidecar-only and still blocked from default runtime use until UI parity smoke and an explicit promotion decision happen.

Built a review-only packet for the high/medium replacement audit components excluded from the low-risk lane:

```text
packet script: scripts/build_manual_review_replacement_audit_packet.py
packet json: data/reports/manual_review_ai_after_time_norm_replacement_audit_review_packet.json
packet csv: data/reports/manual_review_ai_after_time_norm_replacement_audit_review_packet.csv
packet markdown: data/reports/manual_review_ai_after_time_norm_replacement_audit_review_packet.md
review rows: 1,421
high-risk rows: 37
medium-risk rows: 1,384
markdown top rows: 100
canonical outputs mutated: false
runtime/default config changed: false
full pytest: 354 passed
```

The packet gives the excluded components an actionable review queue with recommended action buckets. It does not apply or accept any high/medium component.

Summarized the replacement-audit backlog into bounded sublanes:

```text
sublane script: scripts/summarize_manual_review_replacement_audit_sublanes.py
sublane json: data/reports/manual_review_ai_after_time_norm_replacement_audit_sublanes.json
sublane csv: data/reports/manual_review_ai_after_time_norm_replacement_audit_sublanes.csv
sublanes: 11
accepted low-risk preview lane: 1,091 components / 1,696 projected reduction
medium time_raw only: 818 components / 1,369 projected reduction
medium time-or-identity only: 196 components / 327 projected reduction
medium coordinate span >5km: 148 components / 243 projected reduction
medium body text mixed: 85 components / 94 projected reduction
medium classification mixed: 68 components / 107 projected reduction
medium body text only: 35 components / 35 projected reduction
medium identity mixed: 22 components / 22 projected reduction
medium classification only: 8 components / 15 projected reduction
medium location text mixed: 4 components / 4 projected reduction
high coordinate span >50km: 37 components / 75 projected reduction
canonical outputs mutated: false
runtime/default config changed: false
```

The biggest next candidate is the `medium_time_raw_only` lane, but it should get its own parser-backed acceptance gate rather than being accepted from this summary alone.

Post-sublane full verification:

```text
full pytest: 355 passed
```

Reviewed and staged the next bounded medium-time-only lane:

```text
review script: scripts/review_manual_review_medium_time_raw_only.py
review output: data/reports/manual_review_ai_after_time_norm_medium_time_raw_only_review.json
review csv: data/reports/manual_review_ai_after_time_norm_medium_time_raw_only_review.csv
review markdown: data/reports/manual_review_ai_after_time_norm_medium_time_raw_only_review.md
medium time_raw-only items reviewed: 818
source-review same-event candidates: 178
needs more evidence: 640
candidate projected reduction: 238

decision candidate script: scripts/promote_manual_review_medium_time_raw_only_review_to_decision_candidates.py
decision candidates: data/reports/manual_review_ai_after_time_norm_medium_time_raw_only_decision_candidates.jsonl
decision candidate report: data/reports/manual_review_ai_after_time_norm_medium_time_raw_only_decision_candidates_report.json
decision candidate count: 178
projected event reduction: 238

combined effects script: scripts/combine_manual_review_effect_lanes.py
combined effects plan: data/reports/manual_review_ai_after_time_norm_low_risk_plus_medium_time_effects_plan.json
combined effects report: data/reports/manual_review_ai_after_time_norm_low_risk_plus_medium_time_effects_plan_report.json
selected merge effects: 2,087

candidate corpus: data/canonical_time_norm_plus_manual_review_ai_low_risk_plus_medium_time_preview/deduped_events.jsonl
stream apply report: data/reports/manual_review_ai_after_time_norm_low_risk_plus_medium_time_stream_apply_report.json
stream apply check: data/reports/manual_review_ai_after_time_norm_low_risk_plus_medium_time_stream_apply_output_check.json
input rows: 944,464
output rows: 942,530
actual event reduction: 1,934
replacement rows found: 1,269
suppressed IDs still present: 0
valid output check: true
replacement audit: 0 high / 178 medium / 1,091 low

smoke compact-web output: data/canonical_web_time_norm_plus_manual_review_ai_low_risk_plus_medium_time_preview_smoke
smoke readiness: data/reports/canonical_web_time_norm_plus_manual_review_ai_low_risk_plus_medium_time_preview_smoke_runtime_readiness.json
full compact-web output: data/canonical_web_time_norm_plus_manual_review_ai_low_risk_plus_medium_time_preview
full readiness: data/reports/canonical_web_time_norm_plus_manual_review_ai_low_risk_plus_medium_time_preview_runtime_readiness.json
static payload: data/canonical_web_time_norm_plus_manual_review_ai_low_risk_plus_medium_time_preview_static_primary_trace_payload
static payload readiness: data/reports/canonical_web_time_norm_plus_manual_review_ai_low_risk_plus_medium_time_preview_static_payload_readiness.json
full events: 942,530
full mapped events: 287,855
full trace event rows: 286,582
full trace segment rows: 286,581
full raw/gzip size: 2,131.61 MB / 404.93 MB
startup gzip: 7.03 MB
static payload files: 212
static payload raw/gzip size: 588.02 MB / 74.56 MB
readiness status: ready_for_preview
static payload status: ready
ready for primary catalog: false
canonical outputs mutated: false
runtime/default config changed: false
```

This combined lane remains sidecar-only. The 178 medium-risk components are included only because the parser-backed gate identified narrow exact-time variance and no non-time audit flags; the remaining 640 medium-time-only items stay deferred.

Reviewed the next medium `time_or_identity_only` lane without creating decisions:

```text
review script: scripts/review_manual_review_medium_time_or_identity_only.py
review output: data/reports/manual_review_ai_after_time_norm_medium_time_or_identity_only_review.json
review csv: data/reports/manual_review_ai_after_time_norm_medium_time_or_identity_only_review.csv
review markdown: data/reports/manual_review_ai_after_time_norm_medium_time_or_identity_only_review.md
target components: 196
source component rows found: 523 / 523
manual identity review candidates: 71
needs deeper identity review: 125
candidate projected reduction if later reviewed/accepted: 115
subcategories:
  identity_only_no_time_conflict: 53
  identity_plus_nearby_exact_time: 18
  identity_plus_wide_exact_time: 76
  identity_plus_fuzzy_or_unknown_time: 49
canonical outputs mutated: false
decisions created: false
auto merge performed: false
ready for runtime promotion: false
```

This lane is deliberately review-only because every component includes `same_source_multiple_native_ids`. Multiple native IDs from the same source are useful dedupe evidence but not enough for automatic acceptance without source-identity review.

Post-review verification:

```text
syntax check: scripts/review_manual_review_medium_time_or_identity_only.py compiled
json validation: phase_status and medium time-or-identity review passed
full pytest: 365 passed
```

Reviewed the small `medium_body_text_only` lane without creating decisions:

```text
review script: scripts/review_manual_review_medium_body_text_only.py
review output: data/reports/manual_review_ai_after_time_norm_medium_body_text_only_review.json
review csv: data/reports/manual_review_ai_after_time_norm_medium_body_text_only_review.csv
review markdown: data/reports/manual_review_ai_after_time_norm_medium_body_text_only_review.md
target components: 35
source component rows found: 70 / 70
body variant review candidates: 29
needs deeper body review: 6
candidate projected reduction if later reviewed/accepted: 29
subcategories:
  minor_body_wording_variant: 29
  substantive_body_text_variance: 6
canonical outputs mutated: false
decisions created: false
auto merge performed: false
ready for runtime promotion: false
```

This lane stays review-only because body-text conflicts can carry witness-detail differences. The review report hydrates source rows and records normalized text similarity so a later explicit evidence gate can separate harmless wording variants from substantive narrative differences.

Post-body-lane verification:

```text
syntax check: medium time-or-identity and medium body-text scripts compiled
json validation: phase_status plus both review reports passed
full pytest: 368 passed
```

Reviewed the small `medium_classification_only` lane without creating decisions:

```text
review script: scripts/review_manual_review_medium_classification_only.py
review output: data/reports/manual_review_ai_after_time_norm_medium_classification_only_review.json
review csv: data/reports/manual_review_ai_after_time_norm_medium_classification_only_review.csv
review markdown: data/reports/manual_review_ai_after_time_norm_medium_classification_only_review.md
target components: 8
source component rows found: 23 / 23
classification variant review candidates: 3
needs deeper classification review: 5
candidate projected reduction if later reviewed/accepted: 4
subcategories:
  minor_type_code_variant: 3
  substantive_type_category_variance: 5
canonical outputs mutated: false
decisions created: false
auto merge performed: false
ready for runtime promotion: false
```

This lane stays review-only because broad UFOCAT type changes like `2|5`, `3|5`, and `4|5` should not be treated as equivalent without an explicit source-code hierarchy/equivalence table.

Post-classification-lane verification:

```text
syntax check: medium classification/body/time-or-identity review scripts compiled
json validation: phase_status plus classification/body/time-or-identity review reports passed
full pytest: 371 passed
```

Reviewed the small `medium_location_text_mixed` lane without creating decisions:

```text
review script: scripts/review_manual_review_medium_location_text_mixed.py
review output: data/reports/manual_review_ai_after_time_norm_medium_location_text_mixed_review.json
review csv: data/reports/manual_review_ai_after_time_norm_medium_location_text_mixed_review.csv
review markdown: data/reports/manual_review_ai_after_time_norm_medium_location_text_mixed_review.md
target components: 4
location variant review candidates: 3
needs deeper location review: 1
candidate projected reduction if later reviewed/accepted: 3
subcategories:
  punctuation_spacing_location_variant: 4
canonical outputs mutated: false
decisions created: false
auto merge performed: false
ready for runtime promotion: false
```

This lane stays review-only. One row has a fuzzy/partial time conflict (`0230|02+`), so it remains deeper review even though the location text itself normalizes cleanly.

Post-location-lane verification:

```text
syntax check: medium location/classification/body/time-or-identity review scripts compiled
json validation: phase_status plus location/classification review reports passed
full pytest: 374 passed
```

Built the remaining manual-review lane action matrix:

```text
action matrix script: scripts/summarize_manual_review_remaining_lane_actions.py
action matrix output: data/reports/manual_review_ai_after_time_norm_remaining_lane_actions.json
action matrix csv: data/reports/manual_review_ai_after_time_norm_remaining_lane_actions.csv
sublanes summarized: 11
accepted sidecar preview components: 1,091
parser-backed partial sidecar preview components: 818
review-only packet components: 243
unreviewed mixed-risk components: 323
high-risk review-packet-only components: 37
canonical outputs mutated: false
decisions created: false
auto merge performed: false
ready for runtime promotion: false
```

The action matrix makes the next boundary explicit: the remaining 323 medium mixed-risk components and 37 high-risk coordinate components should get evidence packets/manual review, not automated apply gates.

Post-action-matrix verification:

```text
syntax check: remaining action matrix and medium review scripts compiled
json validation: phase_status plus remaining action matrix and location review reports passed
full pytest: 376 passed
```

Reviewed the `medium_coordinate_span_gt_5km` lane without creating decisions:

```text
review script: scripts/review_manual_review_medium_coordinate_span.py
review output: data/reports/manual_review_ai_after_time_norm_medium_coordinate_span_review.json
review csv: data/reports/manual_review_ai_after_time_norm_medium_coordinate_span_review.csv
review markdown: data/reports/manual_review_ai_after_time_norm_medium_coordinate_span_review.md
target components: 148
source component rows found: 391 / 391
coordinate review candidates: 54
needs deeper coordinate review: 94
candidate projected reduction if later reviewed/accepted: 81
subcategories:
  local_coordinate_variance_5_to_10km: 79
  regional_coordinate_variance_10_to_25km: 49
  broad_coordinate_variance_25_to_50km: 20
canonical outputs mutated: false
decisions created: false
auto merge performed: false
ready for runtime promotion: false
```

Refreshed the remaining-lane action matrix after the coordinate packet:

```text
review-only packet components: 391
unreviewed mixed-risk components: 175
high-risk review-packet-only components: 37
```

This coordinate lane remains review-only. Distance conflicts can reflect geocoding/precision variance, but they can also indicate distinct nearby sightings, especially when time/body/type/identity flags are also present.

Post-coordinate-lane verification:

```text
syntax check: medium coordinate-span review and remaining action matrix scripts compiled
json validation: phase_status plus coordinate review and action matrix reports passed
full pytest: 379 passed
```

Reviewed the `medium_identity_mixed` lane without creating decisions:

```text
review script: scripts/review_manual_review_medium_identity_mixed.py
review output: data/reports/manual_review_ai_after_time_norm_medium_identity_mixed_review.json
review csv: data/reports/manual_review_ai_after_time_norm_medium_identity_mixed_review.csv
review markdown: data/reports/manual_review_ai_after_time_norm_medium_identity_mixed_review.md
target components: 22
needs deeper identity mixed review: 22
subcategories:
  identity_plus_body_text_conflict: 19
  identity_plus_classification_conflict: 2
  identity_plus_location_conflict: 1
canonical outputs mutated: false
decisions created: false
auto merge performed: false
ready for runtime promotion: false
```

Refreshed the remaining-lane action matrix after the identity-mixed packet:

```text
review-only packet components: 413
unreviewed mixed-risk components: 153
high-risk review-packet-only components: 37
```

This lane intentionally has no candidate bucket. Multiple native IDs mixed with body/type/location conflicts require manual source identity review before any merge decision.

Post-identity-mixed verification:

```text
syntax check: medium identity-mixed review and remaining action matrix scripts compiled
json validation: phase_status plus identity-mixed review and action matrix reports passed
full pytest: 381 passed
```

Reviewed the `medium_classification_mixed` lane without creating decisions:

```text
review script: scripts/review_manual_review_medium_classification_mixed.py
review output: data/reports/manual_review_ai_after_time_norm_medium_classification_mixed_review.json
review csv: data/reports/manual_review_ai_after_time_norm_medium_classification_mixed_review.csv
review markdown: data/reports/manual_review_ai_after_time_norm_medium_classification_mixed_review.md
target components: 68
needs deeper classification mixed review: 68
subcategories:
  minor_type_code_with_time_conflict: 42
  substantive_type_category_with_time_conflict: 16
  shape_with_time_conflict: 7
  shape_and_type_with_time_conflict: 3
canonical outputs mutated: false
decisions created: false
auto merge performed: false
ready for runtime promotion: false
```

Refreshed the remaining-lane action matrix after the classification-mixed packet:

```text
review-only packet components: 481
unreviewed mixed-risk components: 85
high-risk review-packet-only components: 37
```

Post-classification-mixed verification:

```text
syntax check: medium classification-mixed review and remaining action matrix scripts compiled
json validation: phase_status plus classification-mixed review and action matrix reports passed
full pytest: 383 passed
```

Reviewed the final unresolved medium mixed lane, `medium_body_text_mixed`, without creating decisions:

```text
review script: scripts/review_manual_review_medium_body_text_mixed.py
review output: data/reports/manual_review_ai_after_time_norm_medium_body_text_mixed_review.json
review csv: data/reports/manual_review_ai_after_time_norm_medium_body_text_mixed_review.csv
review markdown: data/reports/manual_review_ai_after_time_norm_medium_body_text_mixed_review.md
target components: 85
needs deeper body mixed review: 85
subcategories:
  body_location_classification_time_mixed: 65
  body_time_mixed: 14
  body_classification_time_mixed: 6
canonical outputs mutated: false
decisions created: false
auto merge performed: false
ready for runtime promotion: false
```

Refreshed the remaining-lane action matrix after all medium mixed packets:

```text
review-only packet components: 566
unreviewed mixed-risk components: 0
high-risk review-packet-only components: 37
```

All medium manual-review audit sublanes now have either a sidecar preview lane or a review-only packet. The only remaining non-medium bucket is the existing high-risk coordinate-span review packet lane.

Post-body-mixed verification:

```text
syntax check: medium body-text-mixed/classification-mixed review and action matrix scripts compiled
json validation: phase_status plus body-text-mixed review and action matrix reports passed
full pytest: 385 passed
```

Built a dedicated high-risk coordinate-span packet:

```text
review script: scripts/review_manual_review_high_coordinate_span.py
review output: data/reports/manual_review_ai_after_time_norm_high_coordinate_span_review.json
review csv: data/reports/manual_review_ai_after_time_norm_high_coordinate_span_review.csv
review markdown: data/reports/manual_review_ai_after_time_norm_high_coordinate_span_review.md
target components: 37
needs deeper high coordinate review: 37
subcategories:
  severe_coordinate_variance_100_to_500km: 21
  high_coordinate_variance_50_to_100km: 14
  extreme_coordinate_variance_over_500km: 2
canonical outputs mutated: false
decisions created: false
auto merge performed: false
ready for runtime promotion: false
```

Refreshed the action matrix after all review-packet coverage:

```text
accepted sidecar preview components: 1,091
parser-backed partial sidecar preview components: 818
review-only packet components: 566
high-risk dedicated review packet components: 37
unreviewed mixed-risk components: 0
```

Post-high-coordinate verification:

```text
syntax check: high coordinate-span review, body-text-mixed review, and action matrix scripts compiled
json validation: phase_status plus high coordinate review and action matrix reports passed
full pytest: 387 passed
```

Started the next guarded runtime-readiness lane with a local primary-catalog/trace-runtime preview smoke:

```text
preview server: scripts/serve_static_bundle_with_canonical_web.py
preview url: http://127.0.0.1:8146/index.html
sidecar payload: data/canonical_web_time_norm_plus_manual_review_ai_low_risk_plus_medium_time_preview_static_primary_trace_payload/data/canonical_web
preview flags: canonicalWebArtifacts enabled, primaryCatalog true, traceRuntime true, filteredTraceAggregation true
http app_config smoke: passed
static/default config changed: false
```

Browser visual smoke remains environment-blocked:

```text
in-app browser: fetched index/css/js assets, but exposed an uninitialized shell with 0 dataset counts and no debug runtime object; screenshot capture timed out
CDP probe: .tmp/verify_canonical_trace_aggregation_cdp.ps1 failed before page inspection with "Unable to discover Chrome debugging targets on port 9379"
result: runtime promotion still blocked on a successful real browser smoke
```

Added a source-controlled guarded browser smoke script and narrowed the blocker:

```text
script: scripts/smoke_guarded_canonical_preview_cdp.ps1
fix: launch Chrome headless at about:blank and do not pass --user-data-dir
reason: this Chrome build fails CDP startup with "Multiple targets are not supported in headless mode" when a user-data-dir is provided or the app URL is passed as the initial headless target
http app_config override: passed
short CDP diagnostic: app executed and reached "Loading canonical summary shards"; 8 of 95 shards loaded after 45 seconds
long CDP diagnostic: did not reach startup Ready within 900 seconds; final diagnostic had no debug runtime object, 0 dataset counts, and 0 map children
default/runtime config changed: false
promotion status: still blocked
```

Resolved the guarded browser-smoke runtime blocker for the staged primary-catalog/trace-runtime payload:

```text
preview server fix: scripts/serve_static_bundle_with_canonical_web.py now streams file responses in 256KB chunks with Content-Length and Connection: close instead of loading large files into one bytes object
frontend fix: webapp/static_public/app.js now uses packedTraceDataView for canonical trace binary DataView construction
frontend resilience: canonical summary shard JSON plus canonical packed trace metadata/binary fetches use a bounded 3-attempt retry for transient request/decode/5xx failures
static bundle: rebuilt from source with checked-in canonical defaults still disabled
10k smoke: passed on http://127.0.0.1:8150/index.html
full sidecar smoke: passed on fresh ports at http://127.0.0.1:8162/index.html
trace runtime rows: 286,582
static trace render mode: budgeted
rendered/source segments: 11,135 / 11,135
default/runtime config changed: false
promotion status: guarded preview passed; default promotion still requires an explicit promotion decision
```

One full-smoke attempt on `8156/9386` failed before catalog loading because `vendor/leaflet.js` and `styles.css` hit `net::ERR_CONNECTION_RESET`; rerunning the same staged payload on fresh `8162/9392` ports passed. Treat that failed attempt as local preview transport flakiness, not a canonical data failure.

Refreshed the runtime integration readiness gate after the guarded browser smoke passed:

```text
script: scripts/summarize_runtime_integration_readiness.py
report: data/reports/runtime_integration_readiness_gate.json
status: preview_ready_default_blocked
ready_for_preview_package: true
ready_for_default_promotion: false
browser smoke check: passed or explicitly blocked = true
remaining blockers:
  canonical primary catalog remains intentionally not promoted
  manual review apply remains preview-only; canonical mutation is unavailable by design
```

Started the next non-promotional ER lane: remaining lower-risk time-format blockers not already accepted by the combined time-normalization sidecar.

```text
builder: scripts/build_entity_resolution_remaining_lower_time_format_source_evidence_packet.py
reviewer: scripts/review_remaining_lower_time_format_candidates.py
evidence packet: data/reports/entity_resolution_remaining_lower_time_format_source_evidence_packet.json
review output: data/reports/entity_resolution_remaining_lower_time_format_review.json
candidate_effect_count: 15
requested/matched canonical events: 44 / 44
candidate/evidence input IDs: 115 / 115
missing events: 0
missing candidate input IDs: 0
projected reduction in packet: 29
source_review_same_event_candidate: 6
remain_deferred: 9
candidate projected reduction: 12
deferred projected reduction: 17
canonical outputs mutated: false
decisions created: false
auto merge performed: false
ready for canonical apply: false
```

The review deliberately stayed conservative. Rows with ambiguous one/two-digit time tokens, incompatible fuzzy context, non-identical source text, shape conflict, or non-time conflict stayed deferred.

Refreshed the ER lane comparison so the new report-only lane is visible in the cluster-lane planning summary:

```text
script: scripts/summarize_entity_resolution_lanes.py
report: data/reports/entity_resolution_lane_comparison.json
remaining lower time-format reviewed items: 15
remaining lower time-format candidate count: 6
remaining lower time-format deferred count: 9
remaining lower time-format projected reduction by recommendation:
  source_review_same_event_candidate: 12
  remain_deferred: 17
canonical outputs mutated: false
```

Added and verified a static-config promotion smoke path without changing checked-in defaults:

```text
script: scripts/smoke_guarded_canonical_preview_cdp.ps1
new mode: -UseStaticAppConfig
purpose: verify a temporary promoted static root where data/app_config.json already contains canonical runtime flags
preview server hardening: normalizes duplicate PATH/Path environment keys before Start-Process
preview server diagnostics: captures preview stdout/stderr and reports process status if app_config cannot be fetched
preview server config loading: accepts UTF-8 BOM app_config.json files produced by Windows tooling
10k temp static-config smoke: passed on http://127.0.0.1:8174/index.html
catalog source: canonical_web
trace mode: static
trace_event_index cached: true
rendered/source segments: 133 / 133
checked-in default config changed: false
canonical outputs mutated: false
```

Verification:

```text
PowerShell parser check: scripts/smoke_guarded_canonical_preview_cdp.ps1 passed
targeted pytest: 13 passed
full pytest: 394 passed
```

Ran the production-like static-config smoke against the full staged sidecar payload, still using only a temporary static root:

```text
temp root: .tmp/promoted_static_bundle_full_smoke
canonical files copied: 212
script: scripts/smoke_guarded_canonical_preview_cdp.ps1 -UseStaticAppConfig
preview url: http://127.0.0.1:8175/index.html
catalog source: canonical_web
startup phase: Ready
trace mode: static
trace_event_index cached: true
trace runtime rows: 286,582
static trace render mode: budgeted
rendered/source segments: 11,135 / 11,135
checked-in default config changed: false
canonical outputs mutated: false
```

Added the next report-only candidate gate for the remaining lower time-format review lane:

```text
script: scripts/promote_remaining_lower_time_format_review_to_decision_candidates.py
input: data/reports/entity_resolution_remaining_lower_time_format_review.json
decision candidates: data/reports/entity_resolution_remaining_lower_time_format_decision_candidates.jsonl
report: data/reports/entity_resolution_remaining_lower_time_format_decision_candidates_report.json
decision_candidate_count: 6
skipped_review_item_count: 9
projected_event_reduction: 12
ready_for_canonical_apply: false
accepted decisions created: false
preview outputs written: false
canonical outputs mutated: false
```

Refreshed `data/reports/entity_resolution_lane_comparison.json` so the cluster lane shows the remaining lower time-format decision-candidate count and projected reduction separately from accepted/applied lanes.

Added an audit-only checker around that candidate gate:

```text
script: scripts/check_remaining_lower_time_format_decision_candidates.py
check: data/reports/entity_resolution_remaining_lower_time_format_decision_candidates_check.json
valid: true
decision_candidate_count: 6
projected_event_reduction: 12
deferred_review_item_count: 9
accepted_decision_count_checked: 90
overlap_with_accepted_review_ids: 0
overlap_with_deferred_review_ids: 0
ready_for_canonical_apply: false
canonical outputs mutated: false
```

Built a report-only promotion decision packet:

```text
script: scripts/build_canonical_promotion_decision_packet.py
json: data/reports/canonical_promotion_decision_packet.json
markdown: data/reports/canonical_promotion_decision_packet.md
gate status: preview_ready_default_blocked
ready_for_preview_package: true
ready_for_default_promotion: false
approval choices:
  approve_default_canonical_runtime
  approve_canonical_mutation
  defer_and_continue_report_only
canonical outputs mutated: false
default runtime config changed: false
```

Corrected the promotion decision packet evidence source:

```text
issue: the packet initially looked for a non-existent top-level metrics object, so smoke evidence fields rendered as null
fix: merge phase_2_progress and compact_web_artifact_probe as the phase-status evidence source
result: smoke statuses, full-sidecar trace rows, rendered segments, remaining-lower check validity, and latest pytest status are populated
canonical outputs mutated: false
default runtime config changed: false
```

Built a report-only promotion/rollback gap audit:

```text
script: scripts/build_canonical_promotion_rollback_gap_audit.py
json: data/reports/canonical_promotion_rollback_gap_audit.json
markdown: data/reports/canonical_promotion_rollback_gap_audit.md
current checked-in canonical flags: all false
candidate promoted canonical flags: enabled, primaryCatalog, traceRuntime, filteredTraceAggregation all true
lean sidecar files: 212
full-detail sidecar files: 968
full-detail gzip MB: 405.41
ready_for_default_promotion: false
default runtime config changed: false
canonical outputs mutated: false
```

Built the final deferred-work queue / approval-boundary report:

```text
script: scripts/build_deferred_work_queue.py
json: data/reports/deferred_work_queue.json
markdown: data/reports/deferred_work_queue.md
buckets:
  requires_default_runtime_approval
  requires_canonical_mutation_or_apply_approval
  safe_report_only_backlog
gate status: preview_ready_default_blocked
default runtime config changed: false
canonical outputs mutated: false
```

Built a report-only static host payload risk report:

```text
script: scripts/build_static_host_payload_risk_report.py
json: data/reports/static_host_payload_risk_report.json
markdown: data/reports/static_host_payload_risk_report.md
overall risk: high
lean payload: 212 files, 74.81 gzip MB, 0 event chunks
full-detail payload: 968 files, 405.41 gzip MB, 378 event chunks
ready_for_default_promotion: false
default runtime config changed: false
canonical outputs mutated: false
```

Built a report-only high coordinate-span triage digest:

```text
script: scripts/build_high_coordinate_span_triage_digest.py
json: data/reports/high_coordinate_span_triage_digest.json
markdown: data/reports/high_coordinate_span_triage_digest.md
reviewed items: 37
projected event reduction behind blocked queue: 75
span km min / median / max: 50.038 / 116.815 / 668.336
ready_for_canonical_apply: false
canonical outputs mutated: false
```

Built a report-only mixed medium manual-review triage digest:

```text
script: scripts/build_mixed_medium_review_triage_digest.py
json: data/reports/mixed_medium_review_triage_digest.json
markdown: data/reports/mixed_medium_review_triage_digest.md
lanes: medium_identity_mixed, medium_classification_mixed, medium_body_text_mixed
reviewed items: 175
projected event reduction behind blocked queues: 223
ready_for_canonical_apply: false
canonical outputs mutated: false
```

Refreshed the deferred-work queue after completing the safe report-only backlog:

```text
script: scripts/build_deferred_work_queue.py
json: data/reports/deferred_work_queue.json
markdown: data/reports/deferred_work_queue.md
safe report-only statuses:
  review_high_coordinate_span_manual_queue: completed_report_only
  review_mixed_medium_manual_queues: completed_report_only
  monitor_static_host_payload_risk: completed_report_only
requires_default_runtime_approval: unchanged
requires_canonical_mutation_or_apply_approval: unchanged
default runtime config changed: false
canonical outputs mutated: false
```

Investigated the visible bad-map-location reports and found a systemic source-coordinate sign issue, especially in UFOCAT raw latitude/longitude rows:

```text
examples verified from screenshots:
  WEST BERLIN, TEMPELHOF APT, Berlin, GER, EU
    before: lat 52.47, lon -13.40
    after:  lat 52.47, lon  13.40
  FLATBUSH, BROOKLYN, Kings, NY, US
    before: lat 40.645, lon  73.96
    after:  lat 40.645, lon -73.96
root cause: source/raw coordinate longitude signs, not GeoNames enrichment
```

Added future-import normalization for UFOCAT coordinate signs and a preview-side coordinate sanity pass for the already generated top-5000 GeoNames sidecar. The first pass found the systemic sign issue; the v2 pass tightened UFOCAT country-code interpretation so `STATE=NZL`, `MEX`, `CUB`, `PR`, etc. are not misread through broad `REGION` buckets like `AU` or `CA`.

```text
source import fix: parser/csv_sources/ufocat.py
preview script: scripts/apply_coordinate_sanity_preview.py
v2 report: data/reports/coordinate_sanity_top5000_preview_apply_report_v2.json
v2 preview output: data/canonical_preview_mapping_enrichment_geonames_top5000_coordinate_sane_v2/deduped_events.jsonl
policy: exact/source coordinate rows only; prefer explicit UFOCAT country-like STATE codes; flip longitude when country polygon or bounded country range validates the corrected point
v1 corrected events: 189,857
v1 suspicious-but-not-autocorrected events: 10,727
v2 corrected events: 190,648
v2 suspicious-but-not-autocorrected events: 2,997
v2 polygon-outside review rows after bounded corrections: 7,744
canonical outputs mutated: false
```

Built and staged the v2 coordinate-sane canonical web payload into the promoted static bundle:

```text
artifact: data/canonical_web_mapping_enrichment_geonames_top5000_coordinate_sane_v2
staged payload: static_bundle/data/canonical_web
events: 942,518
mapped events: 429,231
trace events: 426,453
trace aggregate bins: 150,261
startup gzip MB: 11.20
static payload readiness: ready
runtime readiness: ready_for_primary_catalog
static_bundle.zip: refreshed after staging
```

Verification for the coordinate-sane staged bundle:

```text
targeted tests: coordinate sanity preview + suspicious summary + UFOCAT sign normalization passed
JS syntax: webapp/static_public/app.js and static_bundle/app.js passed node --check
browser smoke: passed at http://127.0.0.1:8186/index.html using debug port 9416
smoke catalog source: canonical_web
trace runtime rows: 426,453
rendered/source segments: 11,515 / 11,515
full pytest: 424 passed
```

Remaining coordinate limitation:

```text
2,997 exact/source-coordinate rows remain uncorrected by the v2 safety policy.
7,744 rows remain useful for polygon-outside review because bounded coastal/island corrections may still fall outside the coarse country polygon.
The coordinate-sanity v2 output is staged as the current static sidecar, while canonical source mutation remains a separate approval-gated lane.
New reports for that next lane:
  data/reports/coordinate_sanity_suspicious_summary_v2.json
  data/reports/coordinate_sanity_suspicious_summary_v2.csv
  data/reports/coordinate_sanity_suspicious_examples_v2.csv
```

Continued the coordinate-quality lane by fixing another UFOCAT code-semantics issue:

```text
issue: UFOCAT REGION=AU with STATE=SAU means South Australia, not Saudi Arabia
related contextual codes handled: AU+NSW/QLD/SAU/TAS/TSM/VIC/WAU -> Australia, AU+NZL -> New Zealand, AU+PNG -> Papua New Guinea
future import fix: parser/csv_sources/ufocat.py now flips Australian state-code longitudes eastward when they are stored as negative western-hemisphere values
preview fix: scripts/apply_coordinate_sanity_preview.py now uses contextual REGION+STATE country inference before generic country-code aliases
```

Built and staged the v3 coordinate-sane canonical web payload:

```text
v3 report: data/reports/coordinate_sanity_top5000_preview_apply_report_v3.json
v3 preview output: data/canonical_preview_mapping_enrichment_geonames_top5000_coordinate_sane_v3/deduped_events.jsonl
v3 corrected events: 198,010
v3 suspicious-but-not-autocorrected events: 2,172
v3 polygon-outside review rows: 6,919
artifact: data/canonical_web_mapping_enrichment_geonames_top5000_coordinate_sane_v3
staged payload: static_bundle/data/canonical_web
events: 942,518
mapped events: 429,231
trace events: 426,453
trace aggregate bins: 148,804
startup gzip MB: 11.21
static payload readiness: ready
runtime readiness: ready_for_primary_catalog
static_bundle.zip: refreshed after staging
```

Verification for the v3 coordinate-sane staged bundle:

```text
targeted tests: coordinate sanity preview + suspicious summary + UFOCAT sign normalization passed
JS syntax: webapp/static_public/app.js and static_bundle/app.js passed node --check
browser smoke: passed at http://127.0.0.1:8187/index.html using debug port 9417
smoke catalog source: canonical_web
trace runtime rows: 426,453
rendered/source segments: 11,515 / 11,515
full pytest: 424 passed
```

Remaining coordinate limitation after v3:

```text
2,172 exact/source-coordinate rows remain uncorrected by the safety policy.
6,919 rows remain useful for polygon-outside review because coastal/island/ocean-adjacent points and coarse country polygons can still disagree.
The v3 coordinate-sanity output is staged as the current static sidecar; canonical source mutation remains a separate approval-gated lane.
New reports for the next review/quarantine lane:
  data/reports/coordinate_sanity_suspicious_summary_v3.json
  data/reports/coordinate_sanity_suspicious_summary_v3.csv
  data/reports/coordinate_sanity_suspicious_examples_v3.csv
```

Built the coordinate quarantine review gate for the v3 remaining polygon-outside rows:

```text
script: scripts/build_coordinate_quarantine_packet.py
check: scripts/check_coordinate_quarantine_packet.py
json: data/reports/coordinate_quarantine_packet_v3.json
csv: data/reports/coordinate_quarantine_packet_v3.csv
readiness: data/reports/coordinate_quarantine_packet_v3_readiness.json
mode: report_only
ready_for_apply: false
human_review_required_before_hiding: true
canonical outputs mutated: false
preview outputs mutated: false
```

The packet separates rows that should not be trusted for map display from rows that are probably coarse-country-polygon misses:

```text
total polygon-outside rows reviewed: 6,919
quarantine_until_review: 1,308
keep_visible_polygon_review: 5,611
manual_review: 0
readiness status: ready_for_review
```

Verification for the quarantine packet:

```text
targeted pytest: coordinate quarantine packet, quarantine packet check, coordinate sanity summary, and coordinate sanity preview passed
full pytest: 426 passed
```

Applied the coordinate quarantine packet to a preview-only v3 quarantine lane and staged it as the promoted static payload:

```text
script: scripts/apply_coordinate_quarantine_preview.py
report: data/reports/coordinate_quarantine_preview_apply_report_v3.json
preview output: data/canonical_preview_mapping_enrichment_geonames_top5000_coordinate_sane_v3_quarantined/deduped_events.jsonl
canonical web artifact: data/canonical_web_mapping_enrichment_geonames_top5000_coordinate_sane_v3_quarantined
quarantined events: 1,308
mapped reduction: 1,308
mapped before: 429,231
mapped after: 427,923
canonical outputs mutated: false
```

The quarantine apply is intentionally conservative:

```text
Only rows marked quarantine_until_review are unmapped.
Event records remain in the corpus and results.
Original coordinates are preserved on the event as coordinate_quarantine_original_lat/lon/source/precision.
The staged sidecar removes the high-risk Asia/ocean false points from the map without deleting the sightings.
The 5,611 keep_visible_polygon_review rows remain mapped because they are likely coastal/island/coarse-polygon review cases rather than clear coordinate failures.
```

Verification for the staged quarantined static bundle:

```text
static payload readiness: ready
runtime readiness: ready_for_primary_catalog
JS syntax: webapp/static_public/app.js and static_bundle/app.js passed node --check
browser smoke: passed at http://127.0.0.1:8188/index.html using debug port 9418
smoke catalog source: canonical_web
trace runtime rows: 425,147
rendered/source segments: 11,508 / 11,508
full pytest: 427 passed
static_bundle.zip: refreshed after staging
```

Expanded the post-quarantine mapping sidecar from the remaining unresolved location text using local GeoNames only:

```text
coverage report: data/reports/mapping_coverage_opportunities_after_coordinate_quarantine_v3.json
coverage csv: data/reports/mapping_coverage_opportunities_after_coordinate_quarantine_v3.csv
unresolved with location text after quarantine: 498,362
offline GeoNames candidates: data/reports/offline_geonames_mapping_candidates_after_coordinate_quarantine_v3_top10000.json
resolved top-10k query strings: 4,085
high/medium-confidence candidate events: 25,973
preview apply report: data/reports/mapping_enrichment_geonames_top10000_after_coordinate_quarantine_v3_preview_apply_report.json
preview output: data/canonical_preview_mapping_enrichment_geonames_top10000_coordinate_sane_v3_quarantined/deduped_events.jsonl
enriched events: 25,973
mapped after: 453,896
canonical outputs mutated: false
network geocoding performed: false
```

Built and staged the top-10k post-quarantine canonical web payload:

```text
artifact: data/canonical_web_mapping_enrichment_geonames_top10000_coordinate_sane_v3_quarantined
staged payload: static_bundle/data/canonical_web
events: 942,518
mapped events: 453,896
trace events: 450,798
trace aggregate bins: 146,194
startup gzip MB: 11.99
static payload readiness: ready
runtime readiness: ready_for_primary_catalog
coordinate suspicious rows after staging: 5,611
```

Verification for the staged top-10k post-quarantine static bundle:

```text
JS syntax: webapp/static_public/app.js and static_bundle/app.js passed node --check
browser smoke: passed at http://127.0.0.1:8189/index.html using debug port 9419
smoke catalog source: canonical_web
trace runtime rows: 450,798
rendered/source segments: 11,596 / 11,596
full pytest: 427 passed
static_bundle.zip: refreshed after staging
```

Expanded the same safe offline GeoNames lane to the top-50k unresolved worklist:

```text
coverage report: data/reports/mapping_coverage_opportunities_after_coordinate_quarantine_v3_top50000.json
coverage csv: data/reports/mapping_coverage_opportunities_after_coordinate_quarantine_v3_top50000.csv
offline GeoNames candidates: data/reports/offline_geonames_mapping_candidates_after_coordinate_quarantine_v3_top50000.json
resolved top-50k query strings: 33,944
high/medium-confidence candidate events: 127,594
preview apply report: data/reports/mapping_enrichment_geonames_top50000_after_coordinate_quarantine_v3_preview_apply_report.json
preview output: data/canonical_preview_mapping_enrichment_geonames_top50000_coordinate_sane_v3_quarantined/deduped_events.jsonl
enriched events: 127,594
mapped after: 555,517
canonical outputs mutated: false
network geocoding performed: false
```

Built and staged the top-50k post-quarantine canonical web payload:

```text
artifact: data/canonical_web_mapping_enrichment_geonames_top50000_coordinate_sane_v3_quarantined
staged payload: static_bundle/data/canonical_web
events: 942,518
mapped events: 555,517
trace events: 550,990
trace aggregate bins: 153,952
startup gzip MB: 15.20
static payload readiness: ready
runtime readiness: ready_for_primary_catalog
coordinate suspicious rows after staging: 5,611
```

Verification for the staged top-50k post-quarantine static bundle:

```text
JS syntax: webapp/static_public/app.js and static_bundle/app.js passed node --check
browser smoke: passed at http://127.0.0.1:8190/index.html using debug port 9420
smoke catalog source: canonical_web
trace runtime rows: 550,990
rendered/source segments: 12,012 / 12,012
full pytest: 427 passed
static_bundle.zip: refreshed after staging
```

Residual mapping coverage after the active top-50k sidecar:

```text
report: data/reports/mapping_coverage_opportunities_after_geonames_top50000_quarantine_v3.json
csv: data/reports/mapping_coverage_opportunities_after_geonames_top50000_quarantine_v3.csv
mapped: 555,517
remaining unresolved with location text: 370,768
cached geocode candidates remaining: 478 events
```

The next material coverage lane is not another blind bulk apply. The largest remaining buckets are ambiguous or under-specified, for example `phoenix, us`, `portland, us`, `us`, and `gb`. Those need a separate ambiguity-resolution policy, such as dominant-population review, source-specific state parsing, or evidence from raw body text, before coordinates should be applied.

Implemented the first ambiguity-resolution lane for dominant city/country-only GeoNames matches:

```text
script: scripts/summarize_dominant_geonames_mapping_candidates.py
tests: tests/test_dominant_geonames_mapping_candidates.py
input coverage: data/reports/mapping_coverage_opportunities_after_geonames_top50000_quarantine_v3.csv
candidate report: data/reports/dominant_geonames_mapping_candidates_after_geonames_top50000_quarantine_v3.json
candidate csv: data/reports/dominant_geonames_mapping_candidates_after_geonames_top50000_quarantine_v3.csv
accepted dominant-city queries: 604
accepted event count: 46,919
policy: city/country only, top GeoNames population >= 100,000, top-to-runner-up population ratio >= 5x
canonical outputs mutated: false
network geocoding performed: false
```

Applied the dominant-city candidates as a preview-only sidecar on top of the top-50k post-quarantine payload:

```text
preview apply report: data/reports/mapping_enrichment_geonames_top50000_plus_dominant_after_quarantine_v3_preview_apply_report.json
preview output: data/canonical_preview_mapping_enrichment_geonames_top50000_plus_dominant_coordinate_sane_v3_quarantined/deduped_events.jsonl
enriched events: 46,919
mapped after: 602,436
coordinate suspicious rows after dominant apply: 5,611
canonical outputs mutated: false
```

Built and staged the top-50k plus dominant-city canonical web payload:

```text
artifact: data/canonical_web_mapping_enrichment_geonames_top50000_plus_dominant_coordinate_sane_v3_quarantined
staged payload: static_bundle/data/canonical_web
events: 942,518
mapped events: 602,436
trace events: 597,864
trace aggregate bins: 155,146
startup gzip MB: 16.28
static payload readiness: ready
runtime readiness: ready_for_primary_catalog
```

Verification for the staged top-50k plus dominant-city static bundle:

```text
JS syntax: webapp/static_public/app.js and static_bundle/app.js passed node --check
browser smoke: passed at http://127.0.0.1:8191/index.html using debug port 9421
smoke catalog source: canonical_web
trace runtime rows: 597,864
rendered/source segments: 12,054 / 12,054
full pytest: 429 passed
static_bundle.zip: refreshed after staging
```

Expanded the dominant city/country-only lane with a stricter-ratio lower-population pass:

```text
candidate report: data/reports/dominant_geonames_mapping_candidates_after_top50000_plus_dominant_quarantine_v3_lowpop_ratio10.json
candidate csv: data/reports/dominant_geonames_mapping_candidates_after_top50000_plus_dominant_quarantine_v3_lowpop_ratio10.csv
policy: city/country only, top GeoNames population >= 25,000, top-to-runner-up population ratio >= 10x
accepted dominant-city queries: 720
accepted event count: 20,946
canonical outputs mutated: false
network geocoding performed: false
```

Applied the low-population high-ratio candidates as a preview-only sidecar:

```text
preview apply report: data/reports/mapping_enrichment_geonames_top50000_plus_dominant_lowpop_after_quarantine_v3_preview_apply_report.json
preview output: data/canonical_preview_mapping_enrichment_geonames_top50000_plus_dominant_lowpop_coordinate_sane_v3_quarantined/deduped_events.jsonl
enriched events: 20,946
mapped after: 623,382
coordinate suspicious rows after lowpop apply: 5,611
canonical outputs mutated: false
```

Built and staged the top-50k plus dominant low-population canonical web payload:

```text
artifact: data/canonical_web_mapping_enrichment_geonames_top50000_plus_dominant_lowpop_coordinate_sane_v3_quarantined
staged payload: static_bundle/data/canonical_web
events: 942,518
mapped events: 623,382
trace events: 618,803
trace aggregate bins: 155,624
startup gzip MB: 16.86
static payload readiness: ready
runtime readiness: ready_for_primary_catalog
```

Verification for the staged top-50k plus dominant low-population static bundle:

```text
JS syntax: webapp/static_public/app.js and static_bundle/app.js passed node --check
browser smoke: passed at http://127.0.0.1:8192/index.html using debug port 9422
smoke catalog source: canonical_web
trace runtime rows: 618,803
rendered/source segments: 12,061 / 12,061
full pytest: 429 passed
static_bundle.zip: refreshed after staging
```

Applied the safe cached-geocode lane on top of the dominant low-population sidecar:

```text
residual coverage report: data/reports/mapping_coverage_opportunities_after_top50000_plus_dominant_lowpop_quarantine_v3.json
residual mapped: 623,382
residual unresolved with location text: 302,903
residual cached geocode rows: 8,357
candidate report: data/reports/cached_geocode_mapping_candidates_after_top50000_plus_dominant_lowpop_quarantine_v3.json
candidate csv: data/reports/cached_geocode_mapping_candidates_after_top50000_plus_dominant_lowpop_quarantine_v3.csv
accepted cached query count: 68
accepted event count: 422
policy: cached geocode only, confidence >= 0.75, city/town/village/hamlet/municipality/suburb/locality only
rejected: country/state/province/region centroids, low-confidence hits, and risky address types
canonical outputs mutated: false
network geocoding performed: false
```

Built and staged the cached-geocode canonical web payload:

```text
preview apply report: data/reports/mapping_enrichment_top50000_plus_dominant_lowpop_plus_cached_after_quarantine_v3_preview_apply_report.json
preview output: data/canonical_preview_mapping_enrichment_top50000_plus_dominant_lowpop_plus_cached_coordinate_sane_v3_quarantined/deduped_events.jsonl
artifact: data/canonical_web_mapping_enrichment_top50000_plus_dominant_lowpop_plus_cached_coordinate_sane_v3_quarantined
staged payload: static_bundle/data/canonical_web
events: 942,518
mapped events: 623,804
trace events: 619,222
trace aggregate bins: 155,851
startup gzip MB: 16.87
coordinate suspicious rows after cached apply: 5,611
static payload readiness: ready
runtime readiness: ready_for_primary_catalog
```

Verification for the staged cached-geocode static bundle:

```text
JS syntax: webapp/static_public/app.js and static_bundle/app.js passed node --check
browser smoke: passed at http://127.0.0.1:8193/index.html using debug port 9423
smoke catalog source: canonical_web
trace runtime rows: 619,222
rendered/source segments: 12,137 / 12,137
full pytest: 429 passed
static_bundle.zip: refreshed after staging
```

Added a conservative admin-region mapping lane for explicit US state and Canadian province rows:

```text
script: scripts/summarize_admin_region_mapping_candidates.py
tests: tests/test_admin_region_mapping_candidates.py
precision preservation: scripts/build_canonical_web_artifacts.py now keeps state/province precision labels
residual offline GeoNames rerun: data/reports/offline_geonames_mapping_candidates_after_top50000_plus_dominant_lowpop_plus_cached_quarantine_v3.json
offline GeoNames resolved query strings: 6,436
offline GeoNames high/medium event count: 0
admin-region candidate report: data/reports/admin_region_mapping_candidates_after_top50000_plus_dominant_lowpop_plus_cached_quarantine_v3.json
admin-region candidate csv: data/reports/admin_region_mapping_candidates_after_top50000_plus_dominant_lowpop_plus_cached_quarantine_v3.csv
accepted explicit admin-region queries: 112
accepted event count: 10,494
policy: explicit STATE, US and PROVINCE, CA rows only; country-only and city/country rows rejected
location precision: state/province centroid, not city precision
canonical outputs mutated: false
network geocoding performed: false
```

Built and staged the admin-region canonical web payload:

```text
preview apply report: data/reports/mapping_enrichment_top50000_plus_dominant_lowpop_plus_cached_plus_admin_region_after_quarantine_v3_preview_apply_report.json
preview output: data/canonical_preview_mapping_enrichment_top50000_plus_dominant_lowpop_plus_cached_plus_admin_region_coordinate_sane_v3_quarantined/deduped_events.jsonl
artifact: data/canonical_web_mapping_enrichment_top50000_plus_dominant_lowpop_plus_cached_plus_admin_region_coordinate_sane_v3_quarantined
staged payload: static_bundle/data/canonical_web
events: 942,518
mapped events: 634,298
trace events: 629,183
trace aggregate bins: 156,887
startup gzip MB: 17.25
state-precision events: 9,892
province-precision events: 602
coordinate suspicious rows after admin-region apply: 5,611
static payload readiness: ready
runtime readiness: ready_for_primary_catalog
```

Verification for the staged admin-region static bundle:

```text
JS syntax: webapp/static_public/app.js and static_bundle/app.js passed node --check
browser smoke: passed at http://127.0.0.1:8194/index.html using debug port 9424
smoke catalog source: canonical_web
trace runtime rows: 629,183
rendered/source segments: 12,281 / 12,281
full pytest: 432 passed
static_bundle.zip: refreshed after staging
```

Expanded the offline GeoNames matcher for parenthetical city notes and Canadian postal province codes:

```text
script: scripts/summarize_offline_geonames_mapping_candidates.py
tests: tests/test_offline_geonames_mapping_candidates.py
normalization: strips trailing parenthetical notes from city names and translates Canadian province postal codes to GeoNames admin1 codes
candidate report: data/reports/offline_geonames_mapping_candidates_after_admin_region_parenthetical_cleanup_v3.json
candidate csv: data/reports/offline_geonames_mapping_candidates_after_admin_region_parenthetical_cleanup_v3.csv
resolved query strings: 8,614
high/medium-confidence candidate events: 15,179
canonical outputs mutated: false
network geocoding performed: false
```

Applied the parenthetical/admin-code GeoNames candidates as a preview-only sidecar:

```text
preview apply report: data/reports/mapping_enrichment_top50000_plus_dominant_lowpop_plus_cached_plus_admin_region_plus_parenthetical_geonames_after_quarantine_v3_preview_apply_report.json
preview output: data/canonical_preview_mapping_enrichment_top50000_plus_dominant_lowpop_plus_cached_plus_admin_region_plus_parenthetical_geonames_coordinate_sane_v3_quarantined/deduped_events.jsonl
enriched events: 15,179
mapped after: 649,477
coordinate suspicious rows after apply: 5,611
canonical outputs mutated: false
```

Built and staged the parenthetical/admin-code canonical web payload:

```text
artifact: data/canonical_web_mapping_enrichment_top50000_plus_dominant_lowpop_plus_cached_plus_admin_region_plus_parenthetical_geonames_coordinate_sane_v3_quarantined
staged payload: static_bundle/data/canonical_web
events: 942,518
mapped events: 649,477
trace events: 644,194
trace aggregate bins: 161,182
startup gzip MB: 17.69
static payload readiness: ready
runtime readiness: ready_for_primary_catalog
```

Verification for the staged parenthetical/admin-code static bundle:

```text
JS syntax: webapp/static_public/app.js and static_bundle/app.js passed node --check
browser smoke: passed at http://127.0.0.1:8195/index.html using debug port 9425
smoke catalog source: canonical_web
trace runtime rows: 644,194
rendered/source segments: 12,325 / 12,325
full pytest: 433 passed
static_bundle.zip: refreshed after staging
```

Tightened the offline GeoNames matcher for comma-bearing parenthetical locations and guarded population-dominance promotion:

```text
script: scripts/summarize_offline_geonames_mapping_candidates.py
tests: tests/test_offline_geonames_mapping_candidates.py
normalization: splits commas outside parentheses, extracts AU/CA/GB admin hints inside parentheses, expands common country aliases
safety: parenthetical population-dominance promotion only applies when the parenthetical text is country/admin context; descriptive notes such as "north of" remain low confidence
safety: zero-population multi-candidate admin matches remain low confidence
candidate report: data/reports/offline_geonames_mapping_candidates_after_parenthetical_parser_cleanup_v4.json
candidate csv: data/reports/offline_geonames_mapping_candidates_after_parenthetical_parser_cleanup_v4.csv
resolved query strings: 7,231
high/medium-confidence candidate events: 2,774
canonical outputs mutated: false
network geocoding performed: false
```

Applied the corrected parenthetical parser candidates as a preview-only sidecar:

```text
preview apply report: data/reports/mapping_enrichment_top50000_plus_dominant_lowpop_plus_cached_plus_admin_region_plus_parenthetical_geonames_plus_parser_cleanup_after_quarantine_v4_preview_apply_report.json
preview output: data/canonical_preview_mapping_enrichment_top50000_plus_dominant_lowpop_plus_cached_plus_admin_region_plus_parenthetical_geonames_plus_parser_cleanup_coordinate_sane_v4_quarantined/deduped_events.jsonl
enriched events: 2,774
mapped after: 652,251
coordinate suspicious rows after apply: 5,611
canonical outputs mutated: false
```

Built and staged the corrected parenthetical parser canonical web payload:

```text
artifact: data/canonical_web_mapping_enrichment_top50000_plus_dominant_lowpop_plus_cached_plus_admin_region_plus_parenthetical_geonames_plus_parser_cleanup_coordinate_sane_v4_quarantined
staged payload: static_bundle/data/canonical_web
events: 942,518
mapped events: 652,251
trace events: 646,968
trace aggregate bins: 163,638
startup gzip MB: 17.76
static payload readiness: ready
runtime readiness: ready_for_primary_catalog
```

Verification for the staged corrected parenthetical parser static bundle:

```text
JS syntax: webapp/static_public/app.js and static_bundle/app.js passed node --check
browser smoke: passed at http://127.0.0.1:8196/index.html using debug port 9426
smoke catalog source: canonical_web
trace runtime rows: 646,968
rendered/source segments: 12,347 / 12,347
full pytest: 436 passed
static_bundle.zip: refreshed after staging
```

Added a coarse placeholder-city admin-region lane for malformed rows that still carry explicit state/province evidence:

```text
script: scripts/summarize_admin_region_mapping_candidates.py
tests: tests/test_admin_region_mapping_candidates.py
policy: accepts placeholder city/admin/country rows such as 0, PA, US or unknown, ON, CA as state/province centroid evidence only
candidate report: data/reports/admin_region_mapping_candidates_placeholder_city_after_parenthetical_parser_cleanup_quarantine_v5.json
candidate csv: data/reports/admin_region_mapping_candidates_placeholder_city_after_parenthetical_parser_cleanup_quarantine_v5.csv
accepted candidate queries: 101
accepted event count: 1,450
location precision: state/province centroid, not city precision
canonical outputs mutated: false
network geocoding performed: false
```

Applied the placeholder-city admin-region candidates as a preview-only sidecar:

```text
preview apply report: data/reports/mapping_enrichment_v5_placeholder_admin_region_preview_apply_report.json
preview output: data/canonical_preview_map_enrich_v5_placeholder_admin_region/deduped_events.jsonl
enriched events: 1,450
mapped after: 653,701
coordinate suspicious rows after apply: 5,611
canonical outputs mutated: false
```

Built and staged the placeholder-city admin-region canonical web payload:

```text
artifact: data/canonical_web_map_enrich_v5_placeholder_admin_region
staged payload: static_bundle/data/canonical_web
events: 942,518
mapped events: 653,701
trace events: 648,377
trace aggregate bins: 163,695
startup gzip MB: 17.81
static payload readiness: ready
runtime readiness: ready_for_primary_catalog
```

Verification for the staged placeholder-city admin-region static bundle:

```text
JS syntax: webapp/static_public/app.js and static_bundle/app.js passed node --check
browser smoke: passed at http://127.0.0.1:8197/index.html using debug port 9427
smoke catalog source: canonical_web
trace runtime rows: 648,377
rendered/source segments: 12,389 / 12,389
full pytest: 437 passed
static_bundle.zip: refreshed after staging
```

Added a conservative event-level body-text city/state mapping lane for ambiguous `City, US` residual rows:

```text
script: scripts/summarize_body_text_city_state_mapping_candidates.py
tests: tests/test_body_text_city_state_mapping_candidates.py and tests/test_mapping_enrichment_preview.py
policy: event-level only; requires same-row text evidence such as City StateName, City ST, or City, ST
safety: does not map whole City, US buckets by population; skips ambiguous standalone state abbreviations IN/ME/OR; requires GeoNames primary/ascii name match rather than alternate-name-only
candidate report: data/reports/body_text_city_state_mapping_candidates_after_placeholder_admin_region_v6.json
candidate csv: data/reports/body_text_city_state_mapping_candidates_after_placeholder_admin_region_v6.csv
target ambiguous City, US queries: 7,793
candidate events with explicit body evidence: 13,783
resolved event-level candidates: 13,206
canonical outputs mutated: false
network geocoding performed: false
```

Applied the body-text city/state candidates as a preview-only event-specific sidecar:

```text
preview apply report: data/reports/mapping_enrichment_v6_body_city_state_preview_apply_report.json
preview output: data/canonical_preview_map_enrich_v6_body_city_state/deduped_events.jsonl
enriched events: 13,206
mapped after: 666,907
coordinate suspicious rows after apply: 5,611
canonical outputs mutated: false
```

Built and staged the body-text city/state canonical web payload:

```text
artifact: data/canonical_web_map_enrich_v6_body_city_state
staged payload: static_bundle/data/canonical_web
events: 942,518
mapped events: 666,907
trace events: 661,583
trace aggregate bins: 163,940
startup gzip MB: 18.19
static payload readiness: ready
runtime readiness: ready_for_primary_catalog
```

Verification for the staged body-text city/state static bundle:

```text
JS syntax: webapp/static_public/app.js and static_bundle/app.js passed node --check
browser smoke: passed at http://127.0.0.1:8199/index.html using debug port 9429
smoke catalog source: canonical_web
trace runtime rows: 661,583
rendered/source segments: 12,389 / 12,389
full pytest: 441 passed
static_bundle.zip: refreshed after staging
```

Added a structured city-alias GeoNames lane for already state/province-qualified residual rows:

```text
script: scripts/summarize_structured_city_alias_geonames_mapping_candidates.py
tests: tests/test_structured_city_alias_geonames_mapping_candidates.py
policy: accepts only rows with explicit city, admin-region, and country evidence
aliases: Ft/Fort, Mt/Mount, St/Saint, directional abbreviations, apostrophes, periods, and D.C./DC admin text
candidate report: data/reports/structured_city_alias_geonames_mapping_candidates_after_body_city_state_v7.json
candidate csv: data/reports/structured_city_alias_geonames_mapping_candidates_after_body_city_state_v7.csv
resolved structured alias queries: 375
high-confidence event count: 1,475
canonical outputs mutated: false
network geocoding performed: false
```

Applied the structured city-alias candidates as a preview-only sidecar:

```text
preview apply report: data/reports/mapping_enrichment_v7_structured_city_alias_preview_apply_report.json
preview output: data/canonical_preview_map_enrich_v7_structured_city_alias/deduped_events.jsonl
enriched events: 1,475
mapped after: 668,382
coordinate suspicious rows after apply: 5,611
canonical outputs mutated: false
```

Built and staged the structured city-alias canonical web payload:

```text
artifact: data/canonical_web_map_enrich_v7_structured_city_alias
staged payload: static_bundle/data/canonical_web
events: 942,518
mapped events: 668,382
trace events: 663,034
trace aggregate bins: 164,037
startup gzip MB: 18.23
static payload readiness: ready
runtime readiness: ready_for_primary_catalog
```

Verification for the staged structured city-alias static bundle:

```text
JS syntax: webapp/static_public/app.js and static_bundle/app.js passed node --check
browser smoke: passed at http://127.0.0.1:8200/index.html using debug port 9430
smoke catalog source: canonical_web
trace runtime rows: 663,034
rendered/source segments: 12,394 / 12,394
full pytest: 443 passed
static_bundle.zip: refreshed after staging
```

Added a facility/site authority mapping lane for unresolved facility rows:

```text
script: scripts/summarize_facility_site_mapping_candidates.py
tests: tests/test_facility_site_mapping_candidates.py
policy: accepts only exact normalized aliases against local military/research authority overlays
safety guard: countryless non-US authority matches are rejected unless the query explicitly provides the country
candidate report: data/reports/facility_site_mapping_candidates_after_structured_city_alias_v8.json
candidate csv: data/reports/facility_site_mapping_candidates_after_structured_city_alias_v8.csv
candidate queries: 101
candidate events: 705
canonical outputs mutated: false
network geocoding performed: false
```

Applied the facility/site candidates as a preview-only sidecar:

```text
preview apply report: data/reports/mapping_enrichment_v8_facility_site_preview_apply_report.json
preview output: data/canonical_preview_map_enrich_v8_facility_site/deduped_events.jsonl
enriched events: 705
mapped after: 669,087
coordinate suspicious rows after apply: 5,611
canonical outputs mutated: false
```

Built and staged the facility/site canonical web payload:

```text
artifact: data/canonical_web_map_enrich_v8_facility_site
staged payload: static_bundle/data/canonical_web
events: 942,518
mapped events: 669,087
trace events: 663,736
trace aggregate bins: 164,101
startup gzip MB: 18.26
static payload readiness: ready
runtime readiness: ready_for_primary_catalog
```

Verification for the staged facility/site static bundle:

```text
JS syntax: webapp/static_public/app.js and static_bundle/app.js passed node --check
browser smoke: passed at http://127.0.0.1:8201/index.html using debug port 9431
smoke catalog source: canonical_web
trace runtime rows: 663,736
rendered/source segments: 12,419 / 12,419
full pytest: 446 passed
static_bundle.zip: refreshed after staging
```

Added an explicit city/country GeoNames lane for rows with missing admin text:

```text
script: scripts/summarize_city_country_geonames_mapping_candidates.py
tests: tests/test_city_country_geonames_mapping_candidates.py
policy: accepts only city, empty-admin, country residual rows
safety: ignores country-only rows, City/US rows, placeholder cities, slash-region labels, and country-as-city rows
matching: primary GeoNames name/ascii name only; no alternate-name matching
acceptance: unique city/country match or strongly dominant populated-place match inside the explicit country
candidate report: data/reports/city_country_geonames_mapping_candidates_after_facility_site_v9.json
candidate csv: data/reports/city_country_geonames_mapping_candidates_after_facility_site_v9.csv
resolved queries: 899
high/medium-confidence event count: 3,809
canonical outputs mutated: false
network geocoding performed: false
```

Applied the city/country candidates as a preview-only sidecar:

```text
preview apply report: data/reports/mapping_enrichment_v9_city_country_preview_apply_report.json
preview output: data/canonical_preview_map_enrich_v9_city_country/deduped_events.jsonl
enriched events: 3,784
mapped after: 672,871
coordinate suspicious rows after apply: 5,611
canonical outputs mutated: false
```

Built and staged the city/country canonical web payload:

```text
artifact: data/canonical_web_map_enrich_v9_city_country
staged payload: static_bundle/data/canonical_web
events: 942,518
mapped events: 672,871
trace events: 667,440
trace aggregate bins: 171,728
startup gzip MB: 18.37
static payload readiness: ready
runtime readiness: ready_for_primary_catalog
```

Verification for the staged city/country static bundle:

```text
JS syntax: webapp/static_public/app.js and static_bundle/app.js passed node --check
browser smoke: first attempt hit transient local ERR_CONNECTION_RESET at 91/95 summary shards
browser smoke rerun: passed at http://127.0.0.1:8203/index.html using debug port 9433
smoke catalog source: canonical_web
trace runtime rows: 667,440
rendered/source segments: 12,436 / 12,436
full pytest: 449 passed
static_bundle.zip: refreshed after staging
```

Added a strict structured primary city/admin GeoNames lane:

```text
script: scripts/summarize_structured_primary_city_admin_geonames_mapping_candidates.py
tests: tests/test_structured_primary_city_admin_geonames_mapping_candidates.py
policy: accepts only explicit city/admin/country residual rows with recognized state/province evidence
safety: matches GeoNames primary/ascii populated-place names only; alternate names are deliberately ignored
candidate report: data/reports/structured_primary_city_admin_geonames_mapping_candidates_after_city_country_v10.json
candidate csv: data/reports/structured_primary_city_admin_geonames_mapping_candidates_after_city_country_v10.csv
resolved queries: 230
high/medium-confidence event count: 233
canonical outputs mutated: false
network geocoding performed: false
```

Applied the strict structured primary city/admin candidates as a preview-only sidecar:

```text
preview apply report: data/reports/mapping_enrichment_v10_structured_primary_city_admin_preview_apply_report.json
preview output: data/canonical_preview_map_enrich_v10_structured_primary_city_admin/deduped_events.jsonl
enriched events: 233
mapped after: 673,104
coordinate suspicious rows after apply: 5,611
canonical outputs mutated: false
```

Built and staged the strict structured primary city/admin canonical web payload:

```text
artifact: data/canonical_web_map_enrich_v10_structured_primary_city_admin
staged payload: static_bundle/data/canonical_web
events: 942,518
mapped events: 673,104
trace events: 667,666
trace aggregate bins: 171,748
startup gzip MB: 18.38
static payload readiness: ready
runtime readiness: ready_for_primary_catalog
```

Verification for the staged strict structured primary city/admin static bundle:

```text
JS syntax: webapp/static_public/app.js and static_bundle/app.js passed node --check
browser smoke: passed at http://127.0.0.1:8204/index.html using debug port 9434
smoke catalog source: canonical_web
trace runtime rows: 667,666
rendered/source segments: 12,436 / 12,436
full pytest: 452 passed
static_bundle.zip: refreshed after staging
```

Follow-up coordinate sanity and static config cleanup:

```text
coordinate quarantine packet: data/reports/coordinate_quarantine_packet_v10_structured_primary_city_admin.json
hard quarantine candidates: 0
display-safe polygon/coastal review rows: 5,611
finding: user-visible Berlin/Flatbush longitude-sign examples are already corrected in the current v10 preview/static payload
static app_config mappedCount synchronized to canonical manifest: 673,104
static app_config normalizedCount synchronized to canonical manifest: 942,518
startup packedPoints kept on lightweight legacy preview rows: 34,227
reason: pointing startup packedPoints at the full canonical 673k point binary regressed startup smoke time
```

Verification after static config synchronization:

```text
focused pytest: 8 passed for stage/check canonical static payload
static payload readiness: ready
JS syntax: webapp/static_public/app.js and static_bundle/app.js passed node --check
browser smoke: passed at http://127.0.0.1:8206/index.html using debug port 9436
smoke catalog source: canonical_web
trace runtime rows: 667,666
rendered/source segments: 12,436 / 12,436
full pytest: 452 passed
```

Added a conservative U.S. city-only dominant GeoNames lane for residual `City, US` rows:

```text
script: scripts/summarize_us_city_dominant_geonames_mapping_candidates.py
tests: tests/test_us_city_dominant_geonames_mapping_candidates.py
policy: accepts exact City, US residuals only when the U.S. populated-place match is unique with population >= 1,000 or strongly dominant
safety: rejects ambiguous city names, U.S. state-name tokens, direction-only tokens, and known unsafe landmark/region-only tokens
candidate report: data/reports/us_city_dominant_geonames_mapping_candidates_after_structured_primary_city_admin_v11.json
candidate csv: data/reports/us_city_dominant_geonames_mapping_candidates_after_structured_primary_city_admin_v11.csv
resolved queries: 393
high/medium-confidence event count: 3,563
rejected ambiguous event count: 74,210
rejected low-population unique event count: 748
canonical outputs mutated: false
network geocoding performed: false
```

Applied the U.S. city-only dominant candidates as a preview-only sidecar:

```text
preview apply report: data/reports/mapping_enrichment_us_city_dominant_v11_preview_apply_report.json
preview output: data/canonical_preview_map_enrich_v11_us_city_dominant/deduped_events.jsonl
enriched events: 3,563
mapped after: 676,667
hard coordinate quarantine candidates after apply: 0
display-safe polygon/coastal review rows: 5,611
canonical outputs mutated: false
```

Built and staged the U.S. city-only dominant canonical web payload:

```text
artifact: data/canonical_web_map_enrich_v11_us_city_dominant
staged payload: static_bundle/data/canonical_web
events: 942,518
mapped events: 676,667
trace events: 671,229
trace aggregate bins: 171,789
startup gzip MB: 18.43
static payload readiness: ready
static app_config mappedCount: 676,667
static app_config normalizedCount: 942,518
startup packedPoints kept on lightweight legacy preview rows: 34,227
```

Verification for the staged U.S. city-only dominant static bundle:

```text
JS syntax: webapp/static_public/app.js and static_bundle/app.js passed node --check
full pytest: 455 passed
browser smoke: passed at http://127.0.0.1:8207/index.html using debug port 9437
smoke catalog source: canonical_web
trace runtime rows: 671,229
rendered/source segments: 12,436 / 12,436
mapping coverage after v11: 676,667 mapped; 249,618 unresolved with location text; 7,775 unresolved with cached geocode
```

Added a source-backed UPDB location-id mapping lane:

```text
script: scripts/summarize_updb_location_id_mapping_candidates.py
tests: tests/test_updb_location_id_mapping_candidates.py
source lookup: UFO Databases/sources/phenomenon.sql.gz api.location
policy: emits event-specific candidates only when raw_fields.location maps to a coordinate-bearing UPDB location row and city/country agree
safety: does not treat raw UPDB location ids as GeoNames ids; direct GeoNames lookup was verified unsafe for these ids
candidate report: data/reports/updb_location_id_mapping_candidates_after_us_city_dominant_v12.json
candidate csv: data/reports/updb_location_id_mapping_candidates_after_us_city_dominant_v12.csv
candidate events: 95,279
high-confidence candidate events: 73,799
medium-confidence candidate events: 21,480
canonical outputs mutated: false
network geocoding performed: false
```

Applied the UPDB location-id candidates as a preview-only sidecar:

```text
preview apply report: data/reports/mapping_enrichment_updb_location_id_v12_preview_apply_report.json
preview output: data/canonical_preview_map_enrich_v12_updb_location_id/deduped_events.jsonl
enriched events: 95,279
mapped after: 771,946
hard coordinate quarantine candidates after apply: 0
display-safe polygon/coastal review rows: 5,611
canonical outputs mutated: false
```

Built and staged the UPDB location-id canonical web payload:

```text
artifact: data/canonical_web_map_enrich_v12_updb_location_id
staged payload: static_bundle/data/canonical_web
events: 942,518
mapped events: 771,946
trace events: 766,508
trace aggregate bins: 189,897
startup gzip MB: 21.18
static payload readiness: ready
static app_config mappedCount: 771,946
static app_config normalizedCount: 942,518
startup packedPoints kept on lightweight legacy preview rows: 34,227
```

Verification for the staged UPDB location-id static bundle:

```text
JS syntax: webapp/static_public/app.js and static_bundle/app.js passed node --check
full pytest: 457 passed
browser smoke with gzip serving: passed at http://127.0.0.1:8210/index.html using debug port 9440
smoke catalog source: canonical_web
trace runtime rows: 766,508
rendered/source segments: 12,436 / 12,436
mapping coverage after v12: 771,946 mapped; 154,339 unresolved with location text; 7,673 unresolved with cached geocode
note: non-gzip local smoke hit local static-server/browser connection resets on the larger v12 payload; gzip serving passed and matches production serving expectations
```

Added two strict two-part residual mapping lanes:

```text
non-US city/country script: scripts/summarize_two_part_city_country_geonames_mapping_candidates.py
non-US city/country tests: tests/test_two_part_city_country_geonames_mapping_candidates.py
US city/state script: scripts/summarize_two_part_us_city_state_geonames_mapping_candidates.py
US city/state tests: tests/test_two_part_us_city_state_geonames_mapping_candidates.py
policy: report-only GeoNames populated-place matching; no network geocoding; no canonical source mutation
non-US accepted events: 83
US city/state accepted events: 322
safety fix: parenthetical non-US country hints like "cornwall (canada), ca" are excluded from the US city/state lane
```

Applied the two-part candidates as preview-only sidecars:

```text
v13 preview apply report: data/reports/mapping_enrichment_two_part_city_country_v13_preview_apply_report.json
v13 preview output: data/canonical_preview_map_enrich_v13_two_part_city_country/deduped_events.jsonl
v13 enriched events: 83
v13 mapped after: 772,029
v14 preview apply report: data/reports/mapping_enrichment_two_part_us_city_state_v14_preview_apply_report.json
v14 preview output: data/canonical_preview_map_enrich_v14_two_part_city_state/deduped_events.jsonl
v14 enriched events: 322
v14 mapped after: 772,351
hard coordinate quarantine candidates after v14 apply: 0
display-safe polygon/coastal review rows: 5,611
canonical outputs mutated: false
```

Built and staged the two-part city/state canonical web payload:

```text
artifact: data/canonical_web_map_enrich_v14_two_part_city_state
staged payload: static_bundle/data/canonical_web
events: 942,518
mapped events: 772,351
trace events: 766,910
trace aggregate bins: 189,955
startup gzip MB: 21.18
static payload readiness: ready
static app_config mappedCount: 772,351
static app_config normalizedCount: 942,518
startup packedPoints kept on lightweight legacy preview rows: 34,227
```

Verification for the staged two-part city/state static bundle:

```text
JS syntax: webapp/static_public/app.js and static_bundle/app.js passed node --check
full pytest: 462 passed
browser smoke with gzip serving: passed at http://127.0.0.1:8211/index.html using debug port 9441
smoke catalog source: canonical_web
trace runtime rows: 766,910
rendered/source segments: 12,489 / 12,489
mapping coverage after v14: 772,351 mapped; 153,934 unresolved with location text; 7,480 unresolved with cached geocode
```

Extended the two-part U.S. city/state lane with a narrow Washington DC exception:

```text
script updated: scripts/summarize_two_part_us_city_state_geonames_mapping_candidates.py
test updated: tests/test_two_part_us_city_state_geonames_mapping_candidates.py
policy: allows Washington + DC even though Washington is also a state name; supports compact "washington dc" residual text
candidate report: data/reports/two_part_us_city_state_geonames_mapping_candidates_after_two_part_city_state_v15.json
candidate csv: data/reports/two_part_us_city_state_geonames_mapping_candidates_after_two_part_city_state_v15.csv
candidate events: 189
canonical outputs mutated: false
network geocoding performed: false
```

Applied the Washington DC / city-state candidates as a preview-only sidecar:

```text
preview apply report: data/reports/mapping_enrichment_washington_dc_city_state_v15_preview_apply_report.json
preview output: data/canonical_preview_map_enrich_v15_washington_dc_city_state/deduped_events.jsonl
enriched events: 189
mapped after: 772,540
hard coordinate quarantine candidates after apply: 0
display-safe polygon/coastal review rows: 5,611
canonical outputs mutated: false
```

Built and staged the Washington DC city-state canonical web payload:

```text
artifact: data/canonical_web_map_enrich_v15_washington_dc_city_state
staged payload: static_bundle/data/canonical_web
events: 942,518
mapped events: 772,540
trace events: 767,098
trace aggregate bins: 189,939
startup gzip MB: 21.18
static payload readiness: ready
static app_config mappedCount: 772,540
static app_config normalizedCount: 942,518
startup packedPoints kept on lightweight legacy preview rows: 34,227
```

Verification for the staged Washington DC city-state static bundle:

```text
JS syntax: webapp/static_public/app.js and static_bundle/app.js passed node --check
full pytest: 463 passed
browser smoke with gzip serving: passed at http://127.0.0.1:8212/index.html using debug port 9442
smoke catalog source: canonical_web
trace runtime rows: 767,098
rendered/source segments: 12,524 / 12,524
mapping coverage after v15: 772,540 mapped; 153,745 unresolved with location text; 7,480 unresolved with cached geocode
```

Added a strict legacy continent-suffix mapping lane:

```text
script: scripts/summarize_legacy_continent_city_country_geonames_mapping_candidates.py
tests: tests/test_legacy_continent_city_country_geonames_mapping_candidates.py
policy: handles city/admin/ISO3-country/continent rows by ignoring only the final continent marker; accepts only unique or dominant populated-place matches within the country
candidate report: data/reports/legacy_continent_city_country_geonames_mapping_candidates_after_washington_dc_v16.json
candidate csv: data/reports/legacy_continent_city_country_geonames_mapping_candidates_after_washington_dc_v16.csv
candidate events: 68
canonical outputs mutated: false
network geocoding performed: false
```

Applied the legacy continent-suffix candidates as a preview-only sidecar:

```text
preview apply report: data/reports/mapping_enrichment_legacy_continent_city_country_v16_preview_apply_report.json
preview output: data/canonical_preview_map_enrich_v16_legacy_continent_city_country/deduped_events.jsonl
enriched events: 68
mapped after: 772,608
hard coordinate quarantine candidates after apply: 0
display-safe polygon/coastal review rows: 5,611
canonical outputs mutated: false
```

Built and staged the legacy continent-suffix canonical web payload:

```text
artifact: data/canonical_web_map_enrich_v16_legacy_continent_city_country
staged payload: static_bundle/data/canonical_web
events: 942,518
mapped events: 772,608
trace events: 767,166
trace aggregate bins: 189,995
startup gzip MB: 21.18
static payload readiness: ready
static app_config mappedCount: 772,608
static app_config normalizedCount: 942,518
startup packedPoints kept on lightweight legacy preview rows: 34,227
```

Verification for the staged legacy continent-suffix static bundle:

```text
JS syntax: webapp/static_public/app.js and static_bundle/app.js passed node --check
full pytest: 465 passed
browser smoke with gzip serving: passed at http://127.0.0.1:8214/index.html using debug port 9444
smoke catalog source: canonical_web
trace runtime rows: 767,166
rendered/source segments: 12,524 / 12,524
mapping coverage after v16: 772,608 mapped; 153,677 unresolved with location text; 7,480 unresolved with cached geocode
note: first v16 smoke attempt on port 8213 hit a local static-server/browser ERR_CONNECTION_RESET for vendor/leaflet.js; retry on fresh port 8214 passed
disk note: older generated preview/artifact directories were removed after path verification to recover workspace space; reports, source files, static_bundle, and current v16 artifacts remain
```

Fixed UFOCAT North America coordinate sign leakage into Asia/Middle East:

```text
source fix: parser/csv_sources/ufocat.py now treats UFOCAT legacy CN as Canada, legacy A+Canadian province as Canada, and U.S. state codes as western-hemisphere rows even when REGION is a legacy/mistyped value such as P, UA, UE, EU, AS, or CN
preview fix: scripts/apply_coordinate_sanity_preview.py now infers the same legacy UFOCAT North America cases before country-polygon/bounded longitude correction
focused tests: tests/test_canonical_import.py and tests/test_coordinate_sanity_preview.py cover CN/ON Canada, P/HI Hawaii, EU/WI Wisconsin, and CN/CN Toronto examples
preview output: data/canonical_preview_map_enrich_v18_ufocat_na_coordinate_sign_quarantined/deduped_events.jsonl
coordinate sanity report: data/reports/coordinate_sanity_v17_ufocat_na_coordinate_sign_report.json
quarantine packet: data/reports/coordinate_quarantine_packet_v17_ufocat_na_coordinate_sign.json
quarantine apply report: data/reports/coordinate_quarantine_apply_v18_ufocat_na_coordinate_sign.json
corrected exact/source-coordinate rows: 20,338
quarantined bad remaining coordinates: 72
remaining tested North-America-looking UFOCAT source coordinates in Asia/Middle-East bbox: 0
canonical outputs mutated: false
```

Built and staged the UFOCAT North America coordinate-sign corrected web payload:

```text
artifact: data/canonical_web_map_enrich_v18_ufocat_na_coordinate_sign_quarantined
staged payload: static_bundle/data/canonical_web
events: 942,518
mapped events: 772,536
trace events: 767,096
trace aggregate bins: 176,341
startup gzip MB: 21.14
static app_config mappedCount: 772,536
static app_config normalizedCount: 942,518
static app_config unresolvedCount: 169,982
```

Verification for the staged UFOCAT coordinate-sign corrected bundle:

```text
JS syntax: webapp/static_public/app.js and static_bundle/app.js passed node --check
runtime readiness: ready_for_primary_catalog
full pytest: 465 passed
HTTP static smoke: passed at http://127.0.0.1:8215/index.html
data scan: remaining tested North-America-looking UFOCAT source coordinates in Asia/Middle-East bbox = 0
static_bundle.zip refreshed: 990,205,345 bytes
```

Extended coordinate-sign hardening to conservative western Europe cases:

```text
source fix: parser/csv_sources/ufocat.py now normalizes strong UFOCAT legacy EU/GBR, EU/IRL, and EU/POR longitude sign omissions on future imports
preview fix: scripts/apply_coordinate_sanity_preview.py now recognizes GBR, IRL, POR, ESP, and related aliases, and applies symmetric bounded longitude sign correction only after declared-country checks
focused tests: tests/test_canonical_import.py and tests/test_coordinate_sanity_preview.py now cover UK, Ireland, Portugal, and inverse France examples
preview output: data/canonical_preview_map_enrich_v19_europe_coordinate_sign/deduped_events.jsonl
coordinate sanity report: data/reports/coordinate_sanity_v19_europe_coordinate_sign_report.json
quarantine packet: data/reports/coordinate_quarantine_packet_v19_europe_coordinate_sign.json
corrected rows: 12,494
corrected by country: United Kingdom 9,201; Spain 1,710; Portugal 591; Ireland 523; France 350; New Zealand 119
new quarantine candidates after v19: 0
canonical outputs mutated: false
```

Built and staged the western-Europe coordinate-sign corrected web payload:

```text
artifact: data/canonical_web_map_enrich_v19_europe_coordinate_sign
staged payload: static_bundle/data/canonical_web
events: 942,518
mapped events: 772,536
trace events: 767,096
trace aggregate bins: 174,172
startup gzip MB: 21.14
static app_config mappedCount: 772,536
static app_config normalizedCount: 942,518
static app_config unresolvedCount: 169,982
```

Verification for the staged western-Europe coordinate-sign corrected bundle:

```text
JS syntax: webapp/static_public/app.js and static_bundle/app.js passed node --check
runtime readiness: ready_for_primary_catalog
full pytest: 465 passed
HTTP static smoke: passed at http://127.0.0.1:8216/index.html
static_bundle.zip refreshed: 990,068,418 bytes
```

Extended coordinate-sign hardening to eastern-hemisphere country-code cases:

```text
source fix: parser/csv_sources/ufocat.py now normalizes strong UFOCAT eastern-country longitude omissions for AUT, BEL, CHN, CZE, DEN, FIN, GRE, ITA, JPN, NOR, POL, ROM, RUS, SUI, and SWE on future imports
preview fix: scripts/apply_coordinate_sanity_preview.py now recognizes and bounded-flips Austria, Belgium, China, Czech Republic, Denmark, Finland, Italy, Japan, Norway, Poland, Romania, Russia, Sweden, Switzerland, and related aliases when the declared country verifies the flip
focused tests: tests/test_canonical_import.py and tests/test_coordinate_sanity_preview.py now cover Italy, Japan, China, and Sweden examples
preview output: data/canonical_preview_map_enrich_v20_eastern_coordinate_sign/deduped_events.jsonl
coordinate sanity report: data/reports/coordinate_sanity_v20_eastern_coordinate_sign_report.json
quarantine packet: data/reports/coordinate_quarantine_packet_v20_eastern_coordinate_sign.json
corrected rows: 10,755
corrected by country: Italy 2,093; Sweden 1,269; Belgium 1,042; Denmark 974; Russia 936; Japan 588; China 533
new quarantine candidates after v20: 0
canonical outputs mutated: false
```

Built and staged the eastern-hemisphere coordinate-sign corrected web payload:

```text
artifact: data/canonical_web_map_enrich_v20_eastern_coordinate_sign
staged payload: static_bundle/data/canonical_web
events: 942,518
mapped events: 772,536
trace events: 767,096
trace aggregate bins: 171,282
startup gzip MB: 21.14
static app_config mappedCount: 772,536
static app_config normalizedCount: 942,518
static app_config unresolvedCount: 169,982
```

Verification for the staged eastern-hemisphere coordinate-sign corrected bundle:

```text
JS syntax: webapp/static_public/app.js and static_bundle/app.js passed node --check
runtime readiness: ready_for_primary_catalog
full pytest: 465 passed
HTTP static smoke: passed at http://127.0.0.1:8217/index.html
static_bundle.zip refreshed: 989,953,684 bytes
```

Closed the residual Greece coordinate-sign alias gap and hardened bounded correction idempotence:

```text
preview fix: scripts/apply_coordinate_sanity_preview.py now maps GR/GRE/GREECE to Greece
bounded fallback fix: bounded flip_lon only runs when the current point is outside declared-country review bounds and the flipped point is inside, preventing repeat passes from flipping already-plausible coordinates back across zero longitude
source fix already present: parser/csv_sources/ufocat.py already included GRE in the future-import eastern-country normalization set
focused tests: tests/test_canonical_import.py covers UFOCAT EU/GRE Athens import; tests/test_coordinate_sanity_preview.py covers EU/GRE preview correction and a France in-bounds non-flip regression
preview output: data/canonical_preview_map_enrich_v21_greece_coordinate_sign/deduped_events.jsonl
coordinate sanity report: data/reports/coordinate_sanity_v21_greece_coordinate_sign_report.json
quarantine packet: data/reports/coordinate_quarantine_packet_v21_greece_coordinate_sign.json
corrected rows: 114
corrected by country: Greece 114
new quarantine candidates after v21: 0
canonical outputs mutated: false
```

Built and staged the Greece coordinate-sign corrected web payload:

```text
artifact: data/canonical_web_map_enrich_v21_greece_coordinate_sign
staged payload: static_bundle/data/canonical_web
events: 942,518
mapped events: 772,536
trace events: 767,096
trace aggregate bins: 171,156
startup gzip MB: 21.14
static app_config mappedCount: 772,536
static app_config normalizedCount: 942,518
static app_config unresolvedCount: 169,982
```

Verification for the staged Greece coordinate-sign corrected bundle:

```text
JS syntax: webapp/static_public/app.js and static_bundle/app.js passed node --check
runtime readiness: ready_for_primary_catalog
full pytest: 465 passed
HTTP static smoke: passed at http://127.0.0.1:8219/index.html
static_bundle.zip refreshed: 989,941,943 bytes
```

Aligned coordinate quarantine review bounds with the countries now handled by coordinate sanity, then quarantined the remaining implausible coordinates:

```text
report fix: scripts/build_coordinate_quarantine_packet.py now includes review bounds for Austria, Belgium, China, Czech Republic, Denmark, Finland, Greece, Ireland, Italy, Japan, Norway, Poland, Portugal, Romania, Russia, Spain, Sweden, Switzerland, and United Kingdom
focused test: tests/test_coordinate_quarantine_packet.py covers a non-US country row outside a toy polygon but inside broad review bounds
updated packet: data/reports/coordinate_quarantine_packet_v21_greece_coordinate_sign.json
manual review count after bounds alignment: 0
quarantine candidates after bounds alignment: 117
quarantine apply report: data/reports/coordinate_quarantine_apply_v22_coordinate_quarantine.json
preview output: data/canonical_preview_map_enrich_v22_coordinate_quarantine/deduped_events.jsonl
quarantined rows: 117
mapped reduction: 117
canonical outputs mutated: false
```

Built and staged the coordinate-quarantined web payload:

```text
artifact: data/canonical_web_map_enrich_v22_coordinate_quarantine
staged payload: static_bundle/data/canonical_web
events: 942,518
mapped events: 772,419
trace events: 766,979
trace aggregate bins: 170,869
startup gzip MB: 21.13
static app_config mappedCount: 772,419
static app_config normalizedCount: 942,518
static app_config unresolvedCount: 170,099
```

Verification for the staged coordinate-quarantined bundle:

```text
JS syntax: webapp/static_public/app.js and static_bundle/app.js passed node --check
runtime readiness: ready_for_primary_catalog
full pytest: 465 passed
HTTP static smoke: passed at http://127.0.0.1:8220/index.html
static_bundle.zip refreshed: 989,901,181 bytes
obsolete generated v20/v21 coordinate artifact dirs removed after v22 staging
post-quarantine packet: 0 remaining quarantine candidates, 0 manual-review rows, 8,872 display-safe polygon/coastal review rows
```

Applied a conservative two-part US city/state mapping coverage lane on top of the coordinate-quarantined corpus:

```text
candidate report: data/reports/two_part_us_city_state_geonames_mapping_candidates_after_coordinate_quarantine_v22.json
candidate csv: data/reports/two_part_us_city_state_geonames_mapping_candidates_after_coordinate_quarantine_v22.csv
candidate policy: explicit two-part US city/state residual rows only, matched to GeoNames populated-place primary/ascii names in the declared state
resolved candidate queries: 30
high/medium candidate event count: 342
city/country lane from the same v22 opportunity report: 0 candidates
apply report: data/reports/mapping_enrichment_v23_two_part_us_city_state_apply_report.json
preview output: data/canonical_preview_map_enrich_v23_two_part_us_city_state/deduped_events.jsonl
enriched rows: 342
enriched by source: majestic 342
coordinate quarantine check after apply: 0 quarantine candidates, 0 manual-review rows
canonical outputs mutated: false
```

Built and staged the two-part US city/state enriched web payload:

```text
artifact: data/canonical_web_map_enrich_v23_two_part_us_city_state
staged payload: static_bundle/data/canonical_web
events: 942,518
mapped events: 772,761
trace events: 767,321
trace aggregate bins: 170,868
startup gzip MB: 21.14
static app_config mappedCount: 772,761
static app_config normalizedCount: 942,518
static app_config unresolvedCount: 169,757
```

Verification for the staged two-part US city/state enriched bundle:

```text
JS syntax: webapp/static_public/app.js and static_bundle/app.js passed node --check
runtime readiness: ready_for_primary_catalog
full pytest: 465 passed
HTTP static smoke: passed at http://127.0.0.1:8221/index.html
static_bundle.zip refreshed: 989,961,727 bytes
```

Applied the next conservative two-part city/country mapping coverage lane on top of v23:

```text
candidate report: data/reports/two_part_city_country_geonames_mapping_candidates_after_two_part_us_city_state_v23.json
candidate csv: data/reports/two_part_city_country_geonames_mapping_candidates_after_two_part_us_city_state_v23.csv
candidate policy: explicit two-part city/country residual rows only, matched to GeoNames populated-place primary/ascii names in the declared country
resolved candidate queries: 3
high/medium candidate event count: 32
queries resolved: caracas, venezuela; moscow, russia; lima, peru
apply report: data/reports/mapping_enrichment_v24_two_part_city_country_apply_report.json
preview output: data/canonical_preview_map_enrich_v24_two_part_city_country/deduped_events.jsonl
enriched rows: 32
enriched by source: majestic 32
coordinate quarantine check after apply: 0 quarantine candidates, 0 manual-review rows
canonical outputs mutated: false
```

Built and staged the two-part city/country enriched web payload:

```text
artifact: data/canonical_web_map_enrich_v24_two_part_city_country
staged payload: static_bundle/data/canonical_web
events: 942,518
mapped events: 772,793
trace events: 767,353
trace aggregate bins: 170,903
startup gzip MB: 21.14
static app_config mappedCount: 772,793
static app_config normalizedCount: 942,518
static app_config unresolvedCount: 169,725
```

Verification for the staged two-part city/country enriched bundle:

```text
JS syntax: webapp/static_public/app.js and static_bundle/app.js passed node --check
runtime readiness: ready_for_primary_catalog
full pytest: 465 passed
HTTP static smoke: passed at http://127.0.0.1:8222/index.html
static_bundle.zip refreshed: 989,971,938 bytes
obsolete generated v22/v23 mapping artifact dirs removed after v24 staging
```

Applied the next residual two-part US city/state mapping coverage lane on top of v24:

```text
coverage report: data/reports/mapping_coverage_opportunities_after_two_part_city_country_v24.json
candidate report: data/reports/two_part_us_city_state_geonames_mapping_candidates_after_two_part_city_country_v24.json
candidate csv: data/reports/two_part_us_city_state_geonames_mapping_candidates_after_two_part_city_country_v24.csv
candidate policy: explicit two-part US city/state residual rows only, matched to GeoNames populated-place primary/ascii names in the declared state
resolved candidate queries: 3
high/medium candidate event count: 27
queries resolved: oklahoma city, ok; st. louis, mo; tampa, florida
apply report: data/reports/mapping_enrichment_v25_residual_us_city_state_apply_report.json
preview output: data/canonical_preview_map_enrich_v25_residual_us_city_state/deduped_events.jsonl
enriched rows: 27
enriched by source: majestic 27
coordinate quarantine check after apply: 0 quarantine candidates, 0 manual-review rows
canonical outputs mutated: false
```

Built and staged the residual US city/state enriched web payload:

```text
artifact: data/canonical_web_map_enrich_v25_residual_us_city_state
staged payload: static_bundle/data/canonical_web
events: 942,518
mapped events: 772,820
trace events: 767,380
trace aggregate bins: 170,905
startup gzip MB: 21.14
static app_config mappedCount: 772,820
static app_config normalizedCount: 942,518
static app_config unresolvedCount: 169,698
```

Verification for the staged residual US city/state enriched bundle:

```text
JS syntax: webapp/static_public/app.js and static_bundle/app.js passed node --check
runtime readiness: ready_for_primary_catalog
full pytest: 465 passed
HTTP static smoke: passed at http://127.0.0.1:8223/index.html
static_bundle.zip refreshed: 989,975,717 bytes
```

Generated post-v25 mapping coverage and exhausted the currently implemented conservative candidate lanes:

```text
coverage report: data/reports/mapping_coverage_opportunities_after_residual_us_city_state_v25.json
mapped events: 772,820
unresolved with location text: 153,465
unresolved with cached geocode: 7,250
two-part US city/state candidates: 0 events
two-part city/country candidates: 0 events
cached geocode candidates: 0 events
body-text city/state resolved candidates: 0 events
admin-region candidates: 0 events
facility/site candidates: 0 events
dominant GeoNames candidates: 0 events
remaining top unresolved rows are mostly country-code-only or narrative-location rows; they should not be mapped by centroid without an explicit low-precision product decision.
obsolete generated v24 mapping artifact dirs removed after v25 staging
```

Fixed a static bundle loadout regression in canonical web payload staging:

```text
issue: static_bundle/data/canonical_web/event_chunks remained from an older full-detail staging even when current mode was primary-catalog-trace-runtime
impact: stale full-detail event chunks added about 1.9 GB raw staged payload and kept static_bundle.zip near 990 MB
code fix: scripts/stage_canonical_web_static_payload.py now clears the existing data/canonical_web target before copying the selected mode's artifact subset
config fix: staged primary-catalog-trace-runtime app_config now records canonicalWebArtifacts.fullDetails=false
runtime fix: Full Details falls back to the loaded summary event when lightweight canonical detail chunks are intentionally not staged
test added: tests/test_stage_canonical_web_static_payload.py verifies stale event_chunks are removed when staging primary-catalog-trace-runtime and records fullDetails=false
restaged current v25 payload: event_chunks directory absent, summary_shards retained
static smoke: passed at http://127.0.0.1:8225/index.html
full pytest: 466 passed
static_bundle.zip after cleanup: 280,909,430 bytes
```

Pruned unused legacy static payload directories for the canonical-primary bundle:

```text
issue: static_bundle still shipped legacy data/catalog_shards and data/event_chunks even though canonicalWebArtifacts.primaryCatalog=true uses canonical summary shards instead
code fix: scripts/stage_canonical_web_static_payload.py now removes legacy catalog_shards/event_chunks when staging a primary-catalog mode, while preserving legacy manifests
removed from staged bundle: data/catalog_shards (14 files, 25,970,390 bytes) and data/event_chunks (22 files, 163,120,377 bytes)
static smoke: passed at http://127.0.0.1:8226/index.html
full pytest: 466 passed
static_bundle.zip after legacy payload prune: 256,728,560 bytes
```

Removed unused canonical point binaries from the promoted primary-catalog trace-runtime payload:

```text
issue: primary-catalog trace-runtime staging still copied canonical_web/points.bin and points_meta.json even though the promoted app_config keeps startup packedPoints on the lightweight legacy preview at data/points.bin
code fix: primary-catalog-trace-runtime mode now omits canonical point artifacts; startup-preview and full-detail modes still keep point artifacts
validator fix: scripts/check_canonical_web_static_payload.py no longer requires canonical points for primary-catalog-trace-runtime mode
static smoke: passed at http://127.0.0.1:8227/index.html
full pytest: 466 passed
static_bundle.zip after omitting canonical points: 212,407,866 bytes
```

Updated the trace visual palette without changing trace sequencing or render logic:

```text
scope: CSS/JS color constants only
playback gap buckets: high-contrast ordered palette from short-gap magenta/orange/yellow to long-gap cyan/violet dashed
static trace chronology: expanded from a 3-stop blue/green/orange ramp to a 6-stop blue/cyan/green/yellow/orange/magenta spectrum
legend sync: Sequence Trail legend and trace bucket buttons now use the same updated colors as rendered traces
static bundle source: webapp/static_public and static_bundle updated together
syntax check: node --check passed for webapp/static_public/app.js and static_bundle/app.js
```

Improved wide-window static trace render usefulness without changing canonical trace sequencing:

```text
issue: budgeted/aggregate/summary trace modes selected global segments before canvas viewport culling, so zoomed views could spend work on offscreen traces and lose useful local segments
runtime fix: scaled static-trace modes now window the source segments to the current padded map viewport before sampling or aggregating
refresh fix: static traces in budgeted/aggregate/summary modes are rebuilt on map move/zoom so the trace sample/aggregate follows the visible viewport
debug metrics: static trace metrics now report viewportSourceSegments, viewportWindowed, and viewportBoundsKey
guardrail: individual/narrow-window trace rendering remains unchanged
targeted tests: tests/test_trace_scale.py and tests/test_webapp.py passed
static smoke: passed at http://127.0.0.1:8230/index.html
full pytest: 466 passed
static_bundle.zip after trace updates: 212,408,505 bytes
```

Applied the conservative v26 structured long-tail city/admin mapping lane:

```text
candidate scan: scripts/summarize_structured_long_tail_geonames_mapping_candidates.py scanned the actual v25 deduped JSONL against offline GeoNames
guardrails: promoted only city/admin/country candidates; broad city/country rows were left as review material because spot checks showed ambiguity
candidate report: 29,745 resolved queries and 30,434 high/medium candidate events before safe-subset filtering
safe subset: 21,171 city/admin candidate queries covering 21,172 candidate events
preview apply: enriched 21,154 events
mapped coverage: 772,820 -> 793,974 mapped events
unresolved coverage: 169,698 -> 148,544 unresolved events
trace runtime: 788,121 trace events and 172,490 trace aggregate bins
coordinate quarantine: 0 quarantine candidates after the safe subset
static staging: primary-catalog trace-runtime payload staged with fullDetails=false
static smoke: passed at http://127.0.0.1:8231/index.html
targeted tests: 22 passed
full pytest: 470 passed
static_bundle.zip after v26 staging: 215,232,123 bytes
```

Promoted the next small conservative residual mapping lanes after v26:

```text
post-v26 coverage report: data/reports/mapping_coverage_opportunities_after_structured_long_tail_city_admin_safe_v26.json
remaining after v26: 148,544 unresolved; 132,311 unresolved with location text
intentionally deferred: cached geocode and admin-region leftovers because they include single-token/broad centroid risks
v27 structured city aliases: 273 high-confidence events mapped from explicit city/admin/country alias rows
v28 body-text city/state: 165 event-specific mappings from explicit city + state evidence in event text
v29 facility/site authority lane: 55 mappings from curated facility/site overlays
coordinate quarantine after v29: 0 quarantine candidates
mapped coverage: 793,974 -> 794,467 mapped events
unresolved coverage: 148,544 -> 148,051 unresolved events
trace runtime: 788,610 trace events and 172,567 trace aggregate bins
static smoke: passed at http://127.0.0.1:8232/index.html
targeted tests: 30 passed
full pytest: 470 passed
static_bundle.zip after v29 staging: 215,298,498 bytes
```

Fixed canonical-primary startup ingestion to use staged summary shards:

```text
issue: primaryCatalog mode replaced the catalog manifest with canonical summary_shards, but loadAndIngestCatalogShards still fetched hard-coded legacy ./data/catalog_shards paths
impact: real browser startup could fail once legacy catalog_shards were pruned, even though manifest/config HTTP smoke checks passed
runtime fix: canonical primary catalog fetches through ensureCanonicalSummaryShardLoaded(...) and keeps the legacy catalog_shards path only for legacy mode
regression test: tests/test_webapp.py asserts canonical_web mode uses summary shard loading and legacy mode still has its fallback path
syntax check: node --check passed for webapp/static_public/app.js and static_bundle/app.js
targeted tests: 14 passed
static smoke: passed at http://127.0.0.1:8236/index.html
full pytest: 471 passed
static_bundle.zip after ingest fix: 215,298,584 bytes
browser plugin note: in-app browser loaded the HTML but did not execute local page scripts in this environment, so the reliable verification was HTTP asset smoke plus JS syntax/tests
```

Reduced canonical primary summary-shard transfer size on static hosts that do not auto-serve gzip:

```text
issue: staged summary shards include both raw JSON and .json.gz siblings, but the browser loader always requested raw JSON
impact: canonical primary startup could transfer about 567 MB of raw summary JSON instead of about 61 MB of existing gzip summary shards when the static host does not apply gzip content-encoding automatically
runtime fix: canonical summary shard loading now prefers the existing .json.gz sibling when the browser supports DecompressionStream("gzip")
fallback: if gzip fetch/decode fails or the browser lacks DecompressionStream, the loader falls back to raw JSON without changing catalog semantics
static smoke: passed at http://127.0.0.1:8237/index.html and confirmed summary_000000.json.gz is served
targeted tests: 15 passed
full pytest: 472 passed
static_bundle.zip after gzip-preferred loader: 215,298,923 bytes
```

Finished the viewport-effective static trace mode correction:

```text
issue: wide-window static traces already windowed source segments to the current viewport, but metrics/tests did not make the global-vs-effective mode distinction explicit
runtime behavior: raw/global segment count chooses initialRenderMode; viewport-windowed segment count chooses the effective renderMode used for sampling/aggregation
refresh behavior: pan/zoom refresh stays enabled when a render was viewport-windowed, even if the effective viewport render mode downshifts to individual
debug metrics: static trace metrics now report initialRenderMode alongside effective renderMode
source/static sync: webapp/static_public/app.js and static_bundle/app.js updated together
syntax check: node --check passed for both app.js files
targeted tests: tests/test_webapp.py and tests/test_trace_scale.py passed, 20 passed
static smoke: passed at http://127.0.0.1:8242/static_bundle using shipped canonical_web paths
full pytest: 472 passed
static_bundle.zip after viewport-effective trace metrics: 215,298,998 bytes
```

Refreshed the current v29 post-mapping opportunity report and checked the ready time-normalization ER lane against the current corpus:

```text
current corpus: data/canonical_preview_map_enrich_v29_facility_site/deduped_events.jsonl
mapping coverage report: data/reports/mapping_coverage_opportunities_after_facility_site_v29.json
events: 942,518
mapped: 794,467
unresolved with location text: 131,818
unresolved with cached geocode: 7,220
cached-geocode candidate lane: 0 safe candidate queries/events after v29
time-normalization ER rebase attempt: blocked safely
blocked reason: accepted time-normalization plan references 40 suppressed event IDs that are absent from the current v29 corpus
result: no v29+time-normalization candidate corpus was written; canonical/static outputs were not mutated
report: data/reports/v29_plus_time_norm_recommended_canonical_apply_report.json
next action: regenerate or rebase the time-normalization ER decision lane from the current v29 corpus before attempting runtime/static promotion
```

Added an idempotence-aware current-corpus checker for the accepted time-normalization ER lane:

```text
script: scripts/check_time_norm_recommended_corpus_state.py
tests: tests/test_time_norm_recommended_corpus_state.py
report: data/reports/v29_time_norm_recommended_corpus_state_check.json
current corpus checked: data/canonical_preview_map_enrich_v29_facility_site/deduped_events.jsonl
accepted effects checked: 33
state: already_applied = 33
candidate output needed: false
ready_for_runtime_promotion: true
meaning: current v29 already contains the replacement rows, merged-id metadata, effect-id metadata, and absent suppressed rows for the accepted clean time-normalization merges
targeted tests: 2 passed
full pytest: 474 passed
```

Fixed canonical primary packed-point staging so the shipped app uses the full current mapped population instead of the legacy 34k startup points:

```text
issue: static_bundle/data/app_config.json advertised the v29 canonical counts, but packedPoints still targeted legacy data/points_meta.json and data/points.bin with 34,227 rows
impact: the deployed/static app could display only the old 34k mapped point population even though the canonical corpus had 794,467 mapped events
staging fix: primary-catalog-trace-runtime now stages canonical_web/points_meta.json and points.bin, and app_config points packedPoints at ./data/canonical_web/points_meta.json
runtime fix: packed point binary loading now prefers points.bin.gz through DecompressionStream("gzip"), with raw points.bin fallback
current packed points: 794,467 rows, schema 2, 72 bytes/row
packed point transfer: raw points.bin 57,201,624 bytes; gzip points.bin.gz 22,410,144 bytes
canonical static payload readiness: ready
static smoke: passed at http://127.0.0.1:8243/index.html and confirmed canonical points/meta/gzip assets are served
syntax check: node --check passed for source and bundle app.js
targeted tests: 16 passed
frontend node tests: passed
full pytest: 475 passed
static_bundle.zip after canonical packed points staging: 261,043,258 bytes
```

Tightened the coordinate-sanity audit bounds for legitimate western Aleutian U.S. records:

```text
issue: the display corpus no longer has the U.S./Canada-positive-longitude UFOCAT pattern, but the coordinate-sanity audit still treated far-west Alaska records such as Adak/Gambell as outside the U.S. bounded review range
fix: expanded the U.S. Alaska bounded longitude range from -170..-130 to -180..-130
impact: legitimate Aleutian records no longer appear as residual U.S. coordinate-sanity failures
targeted test: tests/test_coordinate_sanity_preview.py passed, 2 passed
current v29 UFOCAT U.S./Canada bounded residual check: 0 rows
```

Added and applied a narrow UFOCAT U.S. territory longitude-sign lane:

```text
report script: scripts/summarize_ufocat_us_territory_coordinate_sign_candidates.py
report: data/reports/ufocat_us_territory_coordinate_sign_candidates_after_v29.json
candidate scope: exact/source-coordinate UFOCAT rows with explicit U.S. Virgin Islands evidence and positive longitude that flips into a bounded USVI box
candidate count: 24
false-positive guard: excludes Jamaica ST THOMAS and Guam/other positive-longitude territories unless explicit bounded USVI/PR evidence matches
apply script: scripts/apply_coordinate_sanity_preview.py
preview output: data/canonical_preview_map_enrich_v30_us_territory_coordinate_sign/deduped_events.jsonl
apply report: data/reports/coordinate_sanity_v30_us_territory_coordinate_sign_report.json
corrected rows: 24
canonical web artifact dir: data/canonical_web_map_enrich_v30_us_territory_coordinate_sign
mapped events: 794,467
trace events: 788,610
trace aggregate bins: 172,561
startup gzip: 21.82 MB
static payload readiness: ready
static smoke: passed at http://127.0.0.1:8244/index.html
syntax checks: Python py_compile passed; node --check passed for source and bundle app.js
targeted tests: 3 passed
frontend node tests: passed
full pytest: 477 passed
static_bundle.zip after v30 territory coordinate sign staging: 261,042,067 bytes
post-v30 residual U.S. territory coordinate-sign candidates: 0
```

Cleaned up the dataset status totals for canonical primary startup:

```text
issue: Mapped Events used canonical/app_config counts, but All Events still displayed catalog.length, which can under-report during lazy canonical summary startup
fix: renderStats now prefers canonical manifest counts.events, then app_config.normalizedCount, then catalog.length
scope: display-only counter path; no render/filter/playback behavior changed
syntax check: node --check passed for source and bundle app.js
targeted test: tests/test_webapp.py passed, 8 passed
full pytest: 478 passed
static asset smoke: node static server fetched index.html, app.js, app_config.json, and points.bin.gz successfully
static_bundle.zip after dataset counter cleanup: 261,042,093 bytes
```

Added a report-only static loadout readiness audit for the staged canonical bundle:

```text
script: scripts/check_static_loadout_readiness.py
tests: tests/test_static_loadout_readiness.py
report: data/reports/static_loadout_readiness.json
status: ready
checks: critical files present, canonical config promoted, packed points use canonical paths, row parity OK, points binary size OK, gzip startup assets present, zip exists
manifest mapped events: 794,467
packed points metadata rows: 794,467
summary shards: 95
payload files: 212
payload raw bytes: 729,499,591
payload gzip bytes: 127,632,643
static_bundle.zip bytes: 261,042,093
targeted tests: 2 passed
full pytest: 480 passed
```

Fixed the remaining UFOCAT western-hemisphere longitude-sign lane that was plotting Latin America/Caribbean rows into Asia/Middle East:

```text
issue: after the U.S./Canada sign pass, many 1954 Asia/Middle East-looking dots were still UFOCAT source-coordinate rows with western-hemisphere country codes such as VEN, SA; COL, SA; HON, CA; and BER, A
root cause: coordinate sanity inference did not recognize the legacy Latin America/Caribbean UFOCAT state/region codes as country evidence, so positive longitudes were left unchanged
fix: added bounded country inference/sign correction for Venezuela, Colombia, Honduras, Bermuda, and broader South America codes used by UFOCAT
preview output: data/canonical_preview_map_enrich_v31_latin_america_coordinate_sign/deduped_events.jsonl
apply report: data/reports/coordinate_sanity_v31_latin_america_coordinate_sign_report.json
corrected rows: 8,338
top corrected countries: Argentina 3,329; Brazil 3,295; Venezuela 628; Peru 423; Uruguay 332; Colombia 211; Bolivia 71; Bermuda 27; Honduras 22
post-v31 target-code positive-longitude rows: 898 -> 10, with remaining rows outside safe country bounds and left for quarantine/manual review
post-v31 screenshot-window residual: 36 positive-longitude rows remain in 1954-09-04..1954-10-16; they are explicit Asia/Middle East/Korea/India records or unresolved UFOCAT POLE placeholders, not VEN/COL/HON/BER western-hemisphere sign errors
canonical web artifact dir: data/canonical_web_map_enrich_v31_latin_america_coordinate_sign
mapped events: 794,467
startup gzip: 21.82 MB
static payload readiness: ready
static loadout readiness: ready
static_bundle.zip after v31 staging: 260,803,731 bytes
syntax checks: node --check passed for source and bundle app.js
targeted tests: tests/test_coordinate_sanity_preview.py passed, 2 passed
full pytest: 480 passed
static asset smoke: node static server fetched index.html, app.js, app_config.json, points.bin.gz, and summary_000000.json.gz successfully
```

Fixed wrapped-world marker copies making corrected U.S. UFOCAT points appear over Asia:

```text
issue: examples such as FARGO, Cass, ND, US; BUTLER, Bates, MO, US; MARION, Smyth, VA, US; KINSTON, Lenoir, NC, US; and PASCO, Franklin, WA, US had correct negative longitudes in the v31 corpus, static summary shards, and points.bin, but could still render in the Asia-side wrapped world copy
root cause: wrappedViewportContainsLatLon(...) only checked latitude; offscreen wrapped longitudes passed the viewport filter and marker copies were created in the wrong visible world copy
fix: wrappedViewportContainsLatLon(...) now checks both latitude and longitude with TRACE_VIEWPORT_LON_PAD
scope: source and shipped static bundle app.js only; no data, playback, trace, filter, or chronology logic changed
targeted test: tests/test_webapp.py passed, 9 passed
full pytest: 481 passed
syntax checks: node --check passed for source and bundle app.js
static loadout readiness: ready
static asset smoke: node static server fetched index.html, app.js, app_config.json, and points.bin.gz successfully
static_bundle.zip after wrapped-marker fix: 260,803,765 bytes
```

Added a static regression guard for explicit U.S. coordinate placement:

```text
script: scripts/check_static_coordinate_regressions.py
scope: report-only static summary shard scan; no canonical outputs mutated
purpose: catch explicit U.S. state rows such as FARGO, Cass, ND, US if they ship with impossible non-U.S. coordinates
false-positive guard: only rows ending in explicit state + US/USA/United States are treated as U.S.; bare CA remains Canada/Central America-safe
report: data/reports/static_coordinate_regressions.json
status: ready
explicit U.S. rows scanned: 420,011
explicit U.S. rows outside wide U.S. bounds: 0
named examples checked: FARGO ND, BUTLER MO, MARION VA, KINSTON NC, PASCO WA
named regression failures: 0
targeted tests: tests/test_static_coordinate_regressions.py passed, 3 passed
full pytest: 484 passed
```

Fixed the remaining Atlantic-side coordinate sign lane for Eastern/Central Europe and nearby UFOCAT rows:

```text
issue: many UFOCAT rows labelled with European/near-Europe country codes were plotted in the Atlantic because codes such as UKR, CRO, SER, HUN, BUL, LIT, LAT, EST, CYP, and BS were not in the coordinate-sanity country/range table
fix: expanded coordinate sanity aliases and bounded longitude ranges for Eastern/Central Europe, Kazakhstan, Cyprus, Baltic Sea, and a few legacy regional codes
v33 preview output: data/canonical_preview_map_enrich_v33_eastern_europe_coordinate_sign/deduped_events.jsonl
v33 report: data/reports/coordinate_sanity_v33_eastern_europe_coordinate_sign_report.json
v33 corrected rows: 1,174
top corrected countries: Ukraine 246; Kazakhstan 191; Croatia 118; Serbia 114; Hungary 79; Slovenia 71; Bulgaria 64; Bosnia and Herzegovina 50; Latvia 44; Georgia 41
v34 residual preview output: data/canonical_preview_map_enrich_v34_europe_residual_coordinate_sign/deduped_events.jsonl
v34 report: data/reports/coordinate_sanity_v34_europe_residual_coordinate_sign_report.json
v34 corrected rows: 53
v34 corrected countries: Cyprus 37; Baltic Sea 9; Italy 5; Lithuania 1; Former Yugoslavia 1
residual EU-coded negative-longitude rows in static summary shards: 8; remaining rows are U.S. records with bad EU labels but correct U.S. coordinates, or Ukraine-coded rows that are not safe sign-only fixes
canonical web artifact dir: data/canonical_web_map_enrich_v34_europe_residual_coordinate_sign
staged static mapped events: 794,530
static loadout readiness: ready
static coordinate regression report: ready
static_bundle.zip bytes: 260,756,483
targeted tests: tests/test_coordinate_sanity_preview.py passed, 2 passed
full pytest: 484 passed
```

Applied the next conservative mapping lane on top of v31:

```text
input corpus: data/canonical_preview_map_enrich_v31_latin_america_coordinate_sign/deduped_events.jsonl
mapping coverage report: data/reports/mapping_coverage_opportunities_after_latin_america_coordinate_sign_v31_top50000.json
candidate report: data/reports/structured_primary_city_admin_geonames_mapping_candidates_after_latin_america_coordinate_sign_v31_top50000.json
candidate policy: strict GeoNames primary/ascii populated-place match with explicit admin/state/country evidence
resolved candidate queries: 63
preview output: data/canonical_preview_map_enrich_v32_structured_primary_city_admin/deduped_events.jsonl
apply report: data/reports/mapping_enrichment_v32_structured_primary_city_admin_preview_apply_report.json
enriched events: 63
projected mapped events: 794,530
enriched by source: nuforc 60; mufon 3
canonical web artifact dir: data/canonical_web_map_enrich_v32_structured_primary_city_admin
staged static mapped events: 794,530
static loadout readiness: ready
static coordinate regression report: ready; explicit U.S. rows outside wide U.S. bounds 0; named regression failures 0
static_bundle.zip bytes: 260,817,885
full pytest: 484 passed
```

# UFO Timeline Static Scale Migration Handoff

## Mission

Turn the UFO/UAP Timeline Map into a scalable, static-first research platform for large heterogeneous sighting catalogs.

Controlling rule:

> Preserve source evidence and provenance first. Optimize startup/rendering only after preservation is testable.

The public app remains static-first. Heavy work happens offline in preprocessing; the browser receives compact startup artifacts, packed indexes, and lazy full-detail chunks. Do not add a required backend unless measured static limits prove it necessary.

## Current Baseline Snapshot

Workspace:

```text
C:\Users\jarod\Desktop\UFO Timeline map tool
```

Current generated baseline:

```text
normalized_events: 54,751
mapped_events: 34,227
points.bin schema: 2
points.bin rows: 34,227
points.bin bytes_per_row: 72
catalog_shards total: about 24.77 MB
event_chunks total: about 155.56 MB
```

Current scale work already completed:

```text
packed point schema v2
packed startup heatmap preview
packed-backed point/cluster/heatmap map layer path after parity checks
ordered work-conserving catalog shard fetch+ingest
startup catalog summary trimming
lazy full event chunks preserved
```

Known CSV source sizes from prior audit:

```text
majestic.csv: 54,751 rows
mufon.csv: 138,310 rows
mufonpy.csv: 138,856 rows
nuforc.csv: 159,320 rows
nuforcpy.csv: 160,140 rows
phenomenAInon_UPDB.csv: 296,956 rows
ufocat2023.csv: 320,412 rows
raw total: 1,268,745 rows
exact-pruned keep set estimate: 971,115 rows
```

Known sibling-file relationship:

```text
mufon.csv appears to be an exact subset of mufonpy.csv
nuforc.csv appears to be an exact subset of nuforcpy.csv
```

Important: subset files may be excluded from canonical event import only after verifying they add no unique columns or provenance value. Do not delete or overwrite them.

## Existing Repo Assets

Use these before adding parallel systems:

```text
docs/UFO_DATASET_SCALE_PLAN.md
scripts/audit_ufo_csv_sources.py
scripts/build_canonical_ufo_dataset.py
parser/canonical_schema.py
parser/csv_sources/*
parser/dedupe.py
parser/canonical_export.py
parser/packed_points.py
parser/static_bundle.py
```

## Operating Mode

Operate autonomously.

- Do not ask clarifying questions unless truly blocked.
- Make reasonable default decisions and document them.
- Run tests, rebuilds, and smoke checks yourself.
- Keep the current static app usable after every coherent subphase.
- Prefer idempotent scripts that can resume after interruption.
- Maintain `docs/WORKLOG.md`, `docs/RUNBOOK.md`, and phase reports.
- Never overwrite original source CSVs.

Autonomy does not mean broad rewrites. Startup, playback, map rendering, traces, and timeline behavior require isolated changes plus verification.

## Non-Negotiable Data Rules

No source data loss:

- Every original row must be represented as a source record, import failure, or explicitly skipped exact-subset record.
- Every non-empty source column must map to a canonical field, source-specific raw field, source claim, or unmapped-field report.
- Full raw records, row hashes, source file names, row numbers, native IDs, links, notes, and source-specific fields must survive.
- Ambiguous data stays preserved as source-specific/provenance data rather than being coerced into fake precision.

No over-merge:

- Dedupe is offline only.
- False merges are worse than missed duplicates.
- Weak fuzzy matches go to review, not automatic merge.
- Conflicting values become source claims, not overwritten scalar fields.

Static-first architecture:

- Use offline preprocessing.
- Generate canonical JSONL and QA reports.
- Generate packed binary startup indexes and dictionaries.
- Keep full detail/source claims lazy-loaded.
- Do not require a backend just to render points.

## Phase Gates

### Phase 0: Baseline Freeze

Required before changing ingestion:

```text
run tests
rebuild static_bundle
measure bundle sizes
record normalized/mapped/unresolved counts
record points.bin schema/row count
record catalog/event chunk sizes
write docs/WORKLOG.md baseline
write data/canonical/reports/phase_status.json
```

### Phase 1: Source Field Inventory

No app runtime changes.

Outputs:

```text
data/canonical/source_field_inventories/*.json
data/canonical/source_column_mapping.json
data/canonical/unmapped_fields_report.json
data/canonical/unmapped_fields_report.csv
docs/SOURCE_FIELD_INVENTORY.md
docs/SOURCE_FIELD_MAPPING.md
```

Inventory must include row count, columns, inferred types, non-empty counts, sample values, semantic role guesses, and whether each column maps to canonical or remains source-specific.

### Phase 2: Canonical Source Records And Claims

Adapters must preserve every column. Emit:

```text
data/canonical/source_records.jsonl
data/canonical/canonical_events_raw.jsonl
data/canonical/source_claims.jsonl
data/canonical/import_report.json
data/canonical/import_failures.jsonl
```

Do not replace current app output yet.

### Phase 3: Compatibility Output

Convert canonical raw output back into current app-compatible:

```text
data/normalized_events.json
data/map_events.json
static_bundle/
static_bundle.zip
```

Acceptance: existing app behavior still works.

### Phase 4: Conservative Dedupe

Auto-merge only exact/high-confidence records. Emit:

```text
data/canonical/deduped_events.jsonl
data/canonical/duplicate_groups.jsonl
data/canonical/duplicate_candidates.jsonl
data/canonical/manual_review_queue.jsonl
data/canonical/manual_review_applied_decisions.jsonl
data/canonical/manual_review_decision_schema.json
data/reports/manual_review_decisions_report.json
data/reports/manual_review_effects_plan.json
data/canonical/dedupe_qa_report.json
```

Do not make fuzzy candidates canonical without review.

Manual review decisions can be ingested with `scripts/build_canonical_ufo_dataset.py --manual-review-decisions <jsonl-or-json-array>`. Matching queue items are marked reviewed and reported, but dedupe/normalized/web outputs are not mutated by decisions.

Reviewed decisions can then be converted into a non-destructive effects plan with `scripts/plan_manual_review_effects.py`. That plan identifies intended merge, preserve, exclusion, repair, mapping, and defer actions, but any canonical output mutation still requires a separate explicit apply step.

The apply step is designed in `docs/MANUAL_REVIEW_APPLY_DESIGN.md`. The first implementation should write preview-only shadow outputs and must not overwrite canonical outputs.

### Phase 5: Static Packed Runtime Artifacts

Move runtime toward compact artifacts:

```text
points.bin
points_meta.json
dictionaries.json
compact result summaries
lazy full-detail chunks
lazy source-claims chunks
```

Startup should not require full detail records.

Current guarded runtime seams:

- `canonicalWebArtifacts.primaryCatalog` can load canonical summary shards as the primary browser catalog.
- Packed points validate parity against the active catalog, including the guarded canonical summary primary catalog, before serving map-layer rows.
- `canonicalWebArtifacts.traceRuntime` can render static traces from cached `trace_event_index.bin`.
- `canonicalWebArtifacts.filteredTraceAggregation` can aggregate exact filtered trace-event-index segments client-side for aggregate/summary static trace render modes.
- All three remain disabled in the shipped `app_config.json`; use `scripts/serve_static_bundle_with_canonical_web.py` flags for local previews.

### Phase 6: UI Facets And Provenance

Add facets only after canonical fields exist:

```text
craft/shape/object type
movement/direction
credibility/reliability/strangeness
witness/evidence fields
source dataset
case status/classification
```

Full Event View should show source records, source claims, conflicts, raw rows, unmapped fields, and field-level provenance.

### Phase 7: Runtime Performance

Promote typed-array filtering and compact summaries. Consider deck.gl/WebGL only after packed artifacts and canonical IDs are stable.

### Phase 8: Trace Scale, Color, And Legend

Do not start trace overhaul before canonical/dedupe artifacts stabilize.

Trace roadmap:

```text
trace_event_index.bin
trace_segments.bin as diagnostic/convenience only
trace_aggregate_bins.bin as full-universe LOD only
narrow exact traces
medium budgeted traces
wide aggregate/LOD traces
all-time density/flow summaries
trace color modes
mode-aware legend
```

## Required Verification

Run the equivalent of:

```text
python -m pytest
node --check webapp/static_public/app.js
node --check static_bundle/app.js
node tests/test_frontend_utils.mjs
node tests/test_packed_points_frontend.mjs
node tests/test_packed_traces_frontend.mjs
```

Add tests for:

```text
source field inventory
column accounting
raw source preservation
source claims preservation
canonical ID determinism
dedupe conflict preservation
compatibility output
packed/runtime parity
facet count parity
Full Event View source claims display
```

## Artifact Budgets

Targets:

```text
startup catalog/summary: target under 15 MB, acceptable under 25 MB
points.bin: compact packed mapped index
event_chunks: lazy only
source claims/raw rows: lazy only
```

If a larger startup payload is required, document why and what will reduce it later.

## Stop Conditions

Stop and report only if:

```text
required source files are missing
the repo cannot run tests/build after reasonable repair
there is a destructive data-loss risk
static bundle cannot be rebuilt and cause is not locally fixable
```

Do not stop just because a field is hard to classify, dedupe is ambiguous, or geocoding is incomplete. Preserve raw data, emit reports, and continue.

## Immediate Next Command Sequence

```text
python -m pytest
node --check webapp/static_public/app.js
node tests/test_frontend_utils.mjs
node tests/test_packed_points_frontend.mjs
node tests/test_packed_traces_frontend.mjs
python scripts/audit_ufo_csv_sources.py
```

Then update:

```text
docs/WORKLOG.md
docs/RUNBOOK.md
data/canonical/reports/phase_status.json
```

## Current Runtime Artifact State As Of 2026-05-21

Implemented and verified:

```text
scripts/build_canonical_web_artifacts.py
scripts/check_canonical_web_runtime_readiness.py
webapp/static_public/app.js guarded canonicalWebArtifacts seam
parser/static_bundle.py canonicalWebArtifacts config block
tests/test_canonical_web_artifacts.py
tests/test_packed_points.py
tests/test_packed_points_frontend.mjs
parser/trace_segments.py
tests/test_trace_segments.py
webapp/static/packed-trace-utils.mjs
tests/test_packed_traces_frontend.mjs
scripts/stage_canonical_web_static_payload.py
tests/test_stage_canonical_web_static_payload.py
```

Current full compact canonical web artifact metrics:

```text
events: 944,578
mapped events: 289,831
trace event index rows: 288,558
diagnostic trace segment rows: 288,557
aggregate trace bins: 153,626
event detail chunks: 378
summary shards: 95
startup gzip: 7.07 MB
detail chunk gzip: 330.60 MB
summary shard gzip: 51.18 MB
trace event index gzip: 6.11 MB
trace segments gzip: 6.45 MB
trace aggregate bins gzip: 4.00 MB
total gzip: 405.41 MB
```

Readiness state:

```text
ready_for_startup_preview: true
ready_for_primary_catalog_prototype: true
ready_for_primary_catalog: false
```

Important: the canonical web artifacts are still opt-in. `canonicalWebArtifacts.enabled`, `canonicalWebArtifacts.primaryCatalog`, and `canonicalWebArtifacts.traceRuntime` remain false in the shipped static config. The guarded primary-catalog prototype loads summary shards for filter/timeline/result shells and hydrates full event details lazily by `chunk_id` and `detail_index`.

That guarded prototype branch now exists in `webapp/static_public/app.js`: when both `enabled` and `primaryCatalog` are true and canonical manifests validate, startup ingests canonical summary shards instead of legacy catalog shards. The default shipped config is still disabled, so normal startup remains unchanged.

Browser-facing taxonomy projection now exists in `parser/taxonomy.py` and is applied by `scripts/build_canonical_web_artifacts.py`. The rebuilt `data/canonical_web` no longer exposes source-family labels (`NUFORC`, `MUFON`, `BLUEBOOK`, `UFODNA`, etc.) or MUFON description-tail fragments as filterable object types. Raw source text remains available in lazy detail chunks.

Packed trace-support artifacts now exist in `data/canonical_web`. `trace_event_index.bin` is the primary future runtime input: filter rows by the active event universe first, then connect adjacent visible rows client-side. `trace_segments.bin` contains full unfiltered adjacent pairs only and should be treated as diagnostic/convenience data, not as a complete replacement for filtered static trace reconstruction. `trace_aggregate_bins.bin` is full-universe wide-window LOD data only; exact filtered aggregate behavior should be computed from `trace_event_index.bin`.

`webapp/static/packed-trace-utils.mjs` now provides tested frontend decode/validation utilities for those trace artifacts. `webapp/static_public/app.js` also exposes guarded debug helpers for loading trace artifacts when `canonicalWebArtifacts.enabled` is true. An off-by-default `canonicalWebArtifacts.traceRuntime` branch can build static trace segments from cached `trace_event_index` rows only when the canonical primary catalog is explicitly enabled; normal shipped rendering still uses the existing trace path.

The same utility module now includes exact filtered aggregate helpers. The intended runtime path is: decode/filter `trace_event_index` rows, connect adjacent visible rows, then aggregate those filtered segments client-side when wide-window LOD is needed.

`webapp/static_public/app.js` also exposes `renderCanonicalTraceAggregatePreview({ level: "10deg" })` as a debug-only full-universe LOD preview for `trace_aggregate_bins.bin`. This is intentionally separate from exact filtered traces and should not be treated as filter-correct output.

`scripts/stage_canonical_web_static_payload.py` stages a small opt-in trace-runtime static payload without copying full canonical detail chunks. The current staged payload at `data/canonical_web_static_trace_payload` is 42,721,166 raw bytes plus 17,381,589 gzip bytes.

`scripts/serve_static_bundle_with_canonical_web.py` provides a local gzip-aware preview server that serves the checked-in `static_bundle` plus `/data/canonical_web/` from the canonical artifact directory. It can override the app config in memory for `enabled`, `primaryCatalog`, `traceRuntime`, and canonical packed-points URLs, so local previews do not require editing shipped config files.

Available debug helpers after opting into `canonicalWebArtifacts.enabled`:

```text
window.__UFO_TIMELINE_DEBUG__.getCanonicalWebArtifactsStatus()
window.__UFO_TIMELINE_DEBUG__.loadCanonicalSummaryShard(0)
window.__UFO_TIMELINE_DEBUG__.loadCanonicalSummaryEvents({ maxShards: 1 })
window.__UFO_TIMELINE_DEBUG__.loadCanonicalPackedFullEvent(eventId)
window.__UFO_TIMELINE_DEBUG__.loadCanonicalTraceArtifact("trace_event_index")
window.__UFO_TIMELINE_DEBUG__.getCanonicalTraceArtifactRow("trace_event_index", 0)
window.__UFO_TIMELINE_DEBUG__.getCanonicalTraceRuntimeStatus()
window.__UFO_TIMELINE_DEBUG__.renderCanonicalTraceAggregatePreview({ level: "10deg" })
window.__UFO_TIMELINE_DEBUG__.clearCanonicalTraceAggregatePreview()
```

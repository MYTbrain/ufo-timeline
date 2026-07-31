# UFO Dataset Integration And Scale Migration Plan

This document is the working migration plan for bringing the local UFO CSV
databases into the static UFO/UAP Timeline Map app without making startup,
filtering, traces, or mobile rendering collapse under the larger corpus.

The plan is intentionally static-first. A backend may become useful later for
search, exports, review workflows, or private APIs, but the first scaling wins
should come from offline canonicalization, compact browser payloads, typed-array
filtering, and trace budgets.

## 1. Current Baseline

Current code paths:

- Parser entry: `scripts/parse_ufo_files.py`
- Pipeline: `parser/pipeline.py`
- Static bundle builder: `parser/static_bundle.py`
- Browser app: `webapp/static_public/app.js`
- Current generated event files: `data/normalized_events.json`, `data/map_events.json`
- Current shipped lazy-detail path: `static_bundle/data/event_chunks/*.json`
- Current shipped startup catalog path: `static_bundle/data/catalog_shards/*.json`

Current app behavior:

1. The browser fetches all catalog shards at startup.
2. The app hydrates those shards into JS object arrays.
3. Filtering, results, timeline, and rendering operate over object-heavy in-memory state.
4. Full event details are already chunked and lazy-loaded, which should be preserved.

This is acceptable for the present dataset, but it is the wrong model for
hundreds of thousands or roughly one million source rows.

## 2. Local CSV Source Audit

Audit script:

- `scripts/audit_ufo_csv_sources.py`

Audit report:

- `data/reports/ufo_csv_audit.json`

Raw sources inspected:

- `UFO Databases/majestic.csv`
- `UFO Databases/mufon.csv`
- `UFO Databases/mufonpy.csv`
- `UFO Databases/nuforc.csv`
- `UFO Databases/nuforcpy.csv`
- `UFO Databases/phenomenAInon_UPDB.csv`
- `UFO Databases/ufocat2023.csv`

Raw row totals:

- `majestic.csv`: 54,751 rows
- `mufon.csv`: 138,310 rows
- `mufonpy.csv`: 138,856 rows
- `nuforc.csv`: 159,320 rows
- `nuforcpy.csv`: 160,140 rows
- `phenomenAInon_UPDB.csv`: 296,956 rows
- `ufocat2023.csv`: 320,412 rows
- Total raw rows: 1,268,745

Exact subset findings:

- `mufon.csv` is an exact subset of `mufonpy.csv`.
- `nuforc.csv` is an exact subset of `nuforcpy.csv`.

Exact-pruned keep set:

- `majestic.csv`
- `mufonpy.csv`
- `nuforcpy.csv`
- `phenomenAInon_UPDB.csv`
- `ufocat2023.csv`

Estimated rows after exact subset pruning:

- 971,115 rows

This only removes exact sibling-file duplication. Cross-source duplicate
resolution still has to happen offline.

## 3. Reference Lessons From UFOSINT

The useful lesson from `UFOSINT/ufosint-explorer` is not just "use the GPU".
Their scale comes from several linked decisions:

- PostgreSQL/Flask backend for serving already-prepared data.
- A compact bulk point endpoint instead of object-heavy startup JSON.
- Typed arrays on the client.
- deck.gl for dense point, heatmap, and aggregation rendering.
- Offline or server-side data preparation before frontend rendering.

For this app, the transferable techniques are:

- Build compact startup data, not giant object catalogs.
- Filter typed arrays, not hydrated JS event objects.
- Keep full records lazy-loaded.
- Use GPU rendering for dense visual layers after the data format is fixed.

The backend is not the first required step. The static equivalent of their bulk
endpoint is:

- `static_bundle/data/points.bin`
- `static_bundle/data/points_meta.json`

## 4. Non-Negotiable Architecture Decisions

### 4.1 Dedupe Is Offline

Do not dedupe in `app.js`.

Cross-source record linkage requires source-specific parsing, canonicalization,
normalization, provenance retention, fuzzy matching, and review artifacts. That
belongs in build-time data prep.

### 4.2 Startup Must Stop Loading The Full Object Catalog

More JSON sharding alone is insufficient. Sharding helps network chunking, but
the browser still pays the cost of fetching, parsing, allocating, and filtering
large object arrays.

The large-dataset path must load a compact index first and load full detail
records later.

### 4.3 Canonical IDs And Provenance Come Before GPU Rendering

GPU rendering can make dense points faster, but it cannot fix duplicate records,
unstable IDs, or poor trace/event associations.

Before deck.gl work, the app needs:

- stable canonical event IDs
- source-row provenance
- deterministic duplicate groups
- a compact mapped-event index

### 4.4 Traces Need Budgets And Aggregates

The existing trace feature is valuable, but raw segment rendering cannot scale
linearly into wide windows over a much larger dataset.

Trace rendering must choose the representation by visible segment count:

- narrow windows: individual traces
- medium windows: budgeted/sampled individual traces
- wide windows: aggregate flow or density traces
- huge windows: summary/density only

## 5. Target Data Model

### 5.1 Canonical Source Record

Each imported source row should produce a canonical input record with at least:

- `canonical_input_id`
- `source_name`
- `source_file`
- `source_row_number`
- `source_native_id`
- `source_row_hash`
- `date_raw`
- `date_iso`
- `date_precision`
- `time_raw`
- `location_raw`
- `city`
- `state_province`
- `country`
- `lat`
- `lon`
- `coordinate_source`
- `location_precision`
- `shape_raw`
- `shape_normalized`
- `type_raw`
- `type_normalized`
- `duration_raw`
- `description`
- `summary`
- `reported_date_raw`
- `posted_date_raw`
- `source_url`
- `raw_fields`

### 5.2 Deduped Canonical Event

Each deduped event should retain:

- stable canonical event ID
- winning canonical display fields
- source provenance list
- duplicate group ID when applicable
- duplicate confidence metadata
- date/time precision metadata
- map-ready lat/lon when available
- compact category/type/shape fields for filters
- compatibility fields needed by the existing parser/static bundle path

### 5.3 Generated Artifacts

Recommended generated files:

- `data/canonical/source_records.jsonl`
- `data/canonical/canonical_input_events.jsonl`
- `data/canonical/deduped_events.jsonl`
- `data/canonical/duplicate_groups.jsonl`
- `data/canonical/duplicate_candidates.jsonl`
- `data/reports/canonical_import_report.json`
- `data/reports/dedupe_report.json`

Browser-delivery files for the scaled path:

- `static_bundle/data/points.bin`
- `static_bundle/data/points_meta.json`
- `static_bundle/data/event_chunks/*.json`
- `data/canonical_web/trace_event_index.bin`
- `data/canonical_web/trace_segments.bin`
- `data/canonical_web/trace_aggregate_bins.bin`

## 6. Packed Startup Index

The packed point index should include only startup/filter/render fields for
mapped rows.

Candidate row fields:

- event ID or event index
- lat
- lon
- local date day index
- canonical playback sort ordinal
- source index
- type index
- shape index
- location precision flags
- date/time precision flags
- chronology/playback confidence flags
- chunk index for lazy detail lookup

Metadata sidecar requirements:

- schema version
- row count
- bytes per row
- field offsets and numeric types
- lookup tables for source/type/shape labels
- chunk manifest references
- checksum or byte-length validation

Frontend requirements:

- Load `points.bin` as `ArrayBuffer`.
- Expose typed arrays for filtering and rendering.
- Build visible index arrays from typed filters.
- Lazy-load full details only on demand.
- Keep the old catalog shard path until parity and fallback are proven.

Pass/fail gate:

- In packed mode, startup must not fetch every `catalog_shards/*.json` file.

## 7. Trace Scaling And Visual Encoding

### 7.1 Trace Representation Resolver

Add a trace render-mode resolver before increasing the dataset:

- `individual`: small windows, raw segments are useful.
- `budgeted`: medium windows, cap rendered individual segments.
- `aggregate`: wide windows, show aggregate flow/density.
- `summary`: huge windows, avoid raw line noise.

Suggested initial thresholds:

- individual: up to 3,000 segments
- budgeted: 3,001 to 15,000 segments
- aggregate: 15,001 to 75,000 segments
- summary: above 75,000 segments

These thresholds should be constants and validated with real performance tests.

Implemented status:

- `parser/trace_scale.py` defines the resolver, thresholds, and trace gap bucket boundaries.
- The current frontend static trace renderer uses `individual`, `budgeted`, `aggregate`, and `summary` modes to avoid unbounded raw line rendering.
- `parser/trace_segments.py` exports a packed trace event index from canonical playback order so a future runtime can reconstruct filtered static traces from typed rows.
- The full-sequence `trace_segments.bin` artifact is diagnostic/convenience only; it should not be treated as the authoritative filtered trace representation.
- The full-universe `trace_aggregate_bins.bin` artifact provides initial wide-window LOD bins only. Its metadata marks supported filter semantics as `none/full_universe`.
- `webapp/static/packed-trace-utils.mjs` validates/decodes trace artifacts and codifies the filtered-event-index reconstruction rule for future guarded runtime integration.
- `webapp/static/packed-trace-utils.mjs` also includes client-side filtered aggregation helpers so future exact filtered aggregate traces can be built from visible event-index rows instead of the full-universe aggregate artifact.

### 7.2 Trace Color Modes

Replace the current one-size trace color story with explicit modes:

- `chronology`: older cool colors to newer warm colors
- `playback_recency`: faded past to bright current/recent
- `density`: low-density muted blue to high-density amber/white
- `source`: categorical comparison by source
- `gap`: current bucket/gap diagnostic mode

Do not use rainbow colors as an unlabelled default. If categorical colors are
used, the legend must explain the categories.

Implemented status:

- Static traces now use a chronology gradient from older cool colors to newer warm colors.
- The legend exposes the chronology gradient and sampled-count context when static trace windows are budgeted.
- Source, gap, recency, and density legend descriptor helpers exist for future richer modes, but the frontend does not yet expose every mode as a user-selectable trace coloring system.

### 7.3 Legend Requirements

The legend must be descriptor-driven:

- show chronology gradient only when chronology trace mode is active
- show playback recency only during playback-recency mode
- show density scale only during aggregate/density mode
- show source swatches only during source mode
- show current gap buckets only during gap mode or gap-filter editing

The legend should become smaller and more semantic, not a static list of every
possible trace meaning.

## 8. GPU Rendering Plan

Do not start with deck.gl.

The correct order is:

1. Canonical IDs and dedupe.
2. Packed point index.
3. Typed-array filtering.
4. Leaflet fallback parity.
5. deck.gl point path.
6. deck.gl heatmap/aggregation path.
7. Optional deck.gl line/arc trace path after trace budgets exist.

deck.gl should initially own only dense sighting point rendering and heatmap or
hex aggregation. Existing Leaflet layers can continue to own:

- bases/facilities
- research/test sites
- overlays
- existing trace renderer until replaced safely
- region filters and other map controls

Fallback requirements:

- no WebGL: use existing Leaflet path
- failed binary load: use existing JSON path or show clear error
- schema mismatch: fail visibly, do not render corrupted points
- detail chunk missing: degrade detail view, do not crash the map

## 9. Backend Decision

A backend is useful when the app needs:

- full-text search over narratives at scale
- server-side duplicate review workflows
- dynamic exports
- private raw-source browsing
- authenticated APIs
- true spatial queries over the full corpus

A backend is not required just to render a large static map if the app has:

- offline dedupe
- packed point indexes
- typed-array filtering
- lazy detail chunks
- GPU/fallback rendering

Decision for now:

- keep static-first
- defer backend until packed static mode is measured and found insufficient

## 10. Migration Phases

### Phase 0: Baseline And Guardrails

Deliverables:

- record current startup/network/memory numbers
- record current bundle sizes
- add a startup test that catches accidental full-catalog fetches in packed mode
- preserve current app behavior as fallback

Acceptance gates:

- current test suite passes before migration
- current static bundle still builds
- baseline metrics are documented

### Phase 1: Canonical CSV Import And Dedupe Prep

Deliverables:

- source-specific CSV adapters
- canonical input schema
- exact sibling pruning
- deterministic source row hashes
- deterministic canonical input IDs
- high-confidence duplicate grouping
- ambiguous duplicate review queue
- provenance-preserving deduped canonical output

Acceptance gates:

- `mufon.csv` and `nuforc.csv` are not imported as distinct full sources
- canonical IDs are stable across rebuilds
- duplicate merges preserve all source provenance
- ambiguous fuzzy matches are not silently merged
- weak-date records are not over-merged

### Phase 2: Compatibility Output

Deliverables:

- convert `deduped_events.jsonl` into the current normalized event shape
- rebuild existing `normalized_events.json`, `map_events.json`, catalog shards, and event chunks from canonical data
- verify current UI can still run from compatibility output

Acceptance gates:

- existing parser/static bundle tests pass
- current map/results/playback behavior remains intact
- displayed source date/time text is not rewritten by canonical metadata

### Phase 3: Packed Point Runtime

Deliverables:

- `points.bin`
- `points_meta.json`
- frontend packed loader
- typed-array filter path
- visible index arrays
- lazy detail lookup from packed rows to event chunks
- JSON fallback path retained

Acceptance gates:

- startup does not fetch all catalog shards in packed mode
- filters produce event IDs matching the old catalog path on test fixtures
- clicking a point still opens the correct event detail
- results list respects the same filtered IDs
- corrupt or mismatched binary payload fails clearly

### Phase 4: Trace Scale V1

Deliverables:

- trace render-mode resolver
- segment count budgets
- chronology color mode
- playback recency color mode
- density/aggregate placeholder mode where needed
- dynamic trace legend descriptors

Acceptance gates:

- narrow windows still show individual traces
- wide windows do not render unbounded raw segments
- trace colors are explained by the legend
- playback trace behavior is not broken
- mobile remains usable

### Phase 5: GPU Dense Map Rendering

Deliverables:

- vendored deck.gl assets or equivalent static-compatible build
- WebGL capability probe
- deck.gl point layer
- deck.gl heatmap or aggregation layer
- Leaflet fallback

Acceptance gates:

- points render through deck.gl when supported
- fallback renders through Leaflet when unsupported
- filter changes update GPU layers without rebuilding full object arrays
- map controls, overlays, traces, and results still work

### Phase 6: Trace Aggregates And Optional GPU Traces

Deliverables:

- packed trace event index. Done in `parser/trace_segments.py` and `data/canonical_web/trace_event_index.bin`.
- aggregate trace bins. Done as full-universe LOD bins in `data/canonical_web/trace_aggregate_bins.bin`.
- aggregate flow/density rendering
- optional deck.gl line/arc path

Acceptance gates:

- wide windows become visually useful instead of visually noisy
- trace aggregates preserve the meaning of the active filtered universe
- individual traces remain available where they are meaningful

## 11. QA And Performance Gates

Measure at these tiers:

- current 55k-ish event dataset
- 100k sample
- 400k mapped-style sample
- 700k to 1M stress sample

Initial targets:

- app shell visible under 1.5s desktop, 3s mobile
- first usable map under 5s desktop, 10s mobile for large packed mode
- filter response p95 under 250ms desktop, 600ms mobile
- point mode switch p95 under 500ms desktop, 1s mobile
- narrow trace render p95 under 750ms
- no unbounded raw trace rendering for wide windows
- no repeated 200ms+ long tasks during normal filtering/playback

Required test areas:

- source adapters
- canonical IDs
- exact dedupe and fuzzy candidate generation
- packed exporter schema/byte validation
- frontend typed-array filter parity
- lazy detail lookup
- WebGL fallback
- trace render-mode resolver
- dynamic legend descriptors
- mobile portrait and landscape smoke checks
- static deployment smoke check

## 12. Immediate Backlog

Recommended next implementation order:

1. Add `parser/canonical_schema.py`. Done.
2. Add `parser/csv_sources/` with one adapter per retained CSV source. Done.
3. Add `parser/dedupe.py` with exact/high-confidence matching first. Done for conservative exact canonical fingerprints.
4. Add `scripts/build_canonical_ufo_dataset.py`. Done.
5. Generate canonical JSONL artifacts and import/dedupe reports. Done.
6. Add tests for adapter parsing, stable IDs, exact subset pruning, and duplicate provenance. Done.
7. Convert canonical output into the current normalized event shape. Done via `parser/canonical_export.py`.
8. Start `points.bin` / `points_meta.json`. Done via `parser/packed_points.py` and static bundle generation.

Parallel low-risk UI/performance work:

1. Add trace render-mode resolver constants. Done in `parser/trace_scale.py`.
2. Add chronology/playback-recency trace color descriptor modes. Done as backend/planning descriptors.
3. Make the trace legend descriptor-driven. Done for frontend Sequence Trail chronology/sampling/aggregation rows.
4. Add performance counters for trace segment counts and render mode. Done via debug/status metrics.

## 12.1 Implemented Migration Slice

The current implementation now includes:

- Canonical source schema helpers.
- Source-specific adapters for the five exact-pruned CSV files.
- Conservative exact canonical dedupe grouping with provenance retention.
- Canonical-to-normalized compatibility export.
- Canonical build script outputs:
  - `source_records.jsonl`
  - `canonical_input_events.jsonl`
  - `deduped_events.jsonl`
  - `duplicate_groups.jsonl`
  - `duplicate_candidates.jsonl`
  - `normalized_events.json`
  - `map_events.json`
  - `canonical_import_report.json`
  - `dedupe_report.json`
- Packed point exporter:
  - `points.bin`
  - `points_meta.json`
- Static bundle generation now emits packed point files beside the existing catalog shards and event chunks.
- Trace scale resolver and JSON-friendly legend descriptors.
- Canonical web artifact generation now emits `trace_event_index.bin` for filtered static trace reconstruction and `trace_segments.bin` as full-sequence diagnostic segment data.
- Canonical web artifact generation now emits `trace_aggregate_bins.bin` for full-universe wide-window trace LOD experiments.
- Canonical web detail and summary rows now include derived chronology fields such as `playback_sort_key` so guarded primary-catalog playback ordering can use the same chronology evidence as the canonical build.
- Frontend utility tests now cover packed trace metadata validation, row decoding, aggregate-bin decoding, and filtered A-C reconstruction from event-index rows.
- Frontend utility tests now also cover filtered aggregate-bin creation, gap bucketing, sequence/date spans, and antimeridian shortest-path segment reconstruction.
- Frontend packed-point utilities now include tested helper-only row filtering and facet counting by typed fields, with keyword/search explicitly falling back to catalog/detail search.
- `scripts/stage_canonical_web_static_payload.py` stages a small opt-in trace-runtime payload under `data/canonical_web` for guarded browser testing without bloating the normal static bundle.
- `scripts/stage_canonical_web_static_payload.py` also has an explicit `primary-catalog-trace-runtime-with-details` mode for production-like payloads that include lazy `event_chunks`.
- `webapp/static_public/app.js` now has an off-by-default `canonicalWebArtifacts.traceRuntime` seam that can consume cached `trace_event_index.bin` rows only when the canonical primary catalog is explicitly enabled.
- `scripts/serve_static_bundle_with_canonical_web.py` provides local gzip-aware static preview serving without editing the checked-in bundle config, including optional canonical packed-points URL overrides.
- `webapp/static_public/app.js` exposes a debug-only full-universe aggregate trace preview helper for `trace_aggregate_bins.bin`.
- `scripts/build_canonical_ufo_dataset.py --manual-review-decisions` can ingest JSONL/JSON-array adjudication decisions as record-only queue annotations, with `manual_review_applied_decisions.jsonl` and `manual_review_decisions_report.json` outputs.
- `scripts/plan_manual_review_effects.py` turns reviewed decisions into a non-destructive `manual_review_effects_plan.json` so merge/exclusion intent can be reviewed before a later explicit apply step mutates canonical outputs.
- `webapp/static_public/app.js` has an off-by-default `canonicalWebArtifacts.filteredTraceAggregation` branch that aggregates exact filtered trace-event-index segments client-side for aggregate/summary static trace render modes.
- `webapp/static_public/app.js` exposes debug-only static trace render metrics for render mode, segment counts, sampling ratio, thresholds, source path, and filtered aggregation status.
- `webapp/static_public/app.js` renders the Sequence Trail chronology/sampling/aggregation legend rows from frontend trace legend descriptors instead of hardcoded row markup.

The frontend still uses the existing catalog shards at startup. This is
deliberate: packed points are now generated and tested, but runtime rendering
has not been switched over yet.

## 13. Open Limitations

- Cross-source fuzzy dedupe is not implemented yet.
- Manual review decisions are ingested as record-only annotations and can now be converted into a plan-only effects report; they still do not apply merge/exclusion effects to canonical outputs.
- The future explicit apply path is documented in `docs/MANUAL_REVIEW_APPLY_DESIGN.md`; first implementation should produce preview-only shadow outputs before any promoted mutation path exists.
- Packed point runtime exists as a guarded path and now validates sampled packed rows against the canonical summary primary catalog before serving map-layer data.
- deck.gl is not integrated yet.
- Filtered trace aggregation is wired only behind disabled local-preview flags; it is not a shipped default behavior.
- Frontend trace rendering can consume cached `data/canonical_web/trace_event_index.bin` only behind disabled local-preview flags; it is not a shipped default behavior.
- Canonical packed-points rendering is currently a preview-server config path, not a shipped default config path.
- `trace_aggregate_bins.bin` preview is full-universe LOD only and intentionally not valid for arbitrary filtered trace semantics.
- The staged canonical trace payload and local preview server are for local/static experiment packaging only; production hosting still needs an explicit decision on where canonical web artifacts live and whether precompressed `.gz` siblings are served with correct content encoding.
- Heatmap and cluster rendering still depend on the current frontend model.
- Full-text search over a million narratives will likely need either a compact
  client index, deferred detail search, or a backend later.
- Packed-point filter/facet helpers are not wired into startup yet; they are a validated readiness layer for future typed-array filtering work.

## 14. Bottom Line

The first implementation milestone should not be GPU rendering or a backend.

The first milestone should be:

1. canonical source import
2. provenance-preserving dedupe
3. compatibility output into the current app

The second milestone should be:

1. packed startup point index
2. typed-array filtering
3. lazy details retained

After those are stable, GPU rendering and trace aggregation become much safer
and more valuable.

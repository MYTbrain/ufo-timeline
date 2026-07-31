# Active Triage Plan

Last updated: 2026-06-06

This is the current working order for the UFO Timeline World Map project. It reconciles the older handoff, dataset scale, canonical deployment, deferred work, and recent UI/runtime fix plans into one active triage list.

## Ground Rules

- Deploy only when the user explicitly asks for deployment or approves a specific deploy gate.
- Do not mutate `data/canonical_full/deduped_events.jsonl` without a separate explicit canonical mutation contract.
- Keep the public app static-first: Cloudflare Pages for the shell and Cloudflare R2 for large canonical artifacts.
- Preserve provenance and uncertainty. Do not coerce ambiguous source records into fake precision.
- Treat map location trust, trace reliability, and startup responsiveness as product-critical.

## Priority 0: Ship Gate For Current Fixes

Goal: keep the currently deployed app stable while continuing local fixes, with search/details, filters, loading, and traces as the first regression gate.

Status:

- 2026-06-05 production deployment is live on Cloudflare Pages/R2. Public shell URL: `https://ufo-timeline.pages.dev/`; R2 public artifact base: `https://pub-e9029ab2f6b448daad03d7cde7e15e64.r2.dev`.
- 2026-06-05 detail/search fix deployed: keyword search and `Full Details` lazy chunk loading were repaired after `ensureCanonicalWebArtifactChunkLoaded()` treated parsed JSON arrays as wrapper objects. Canonical detail chunks were enriched from local canonical detail sources and uploaded to R2.
- 2026-06-05 deployed canonical web manifest reports 942,518 normalized events and 793,571 mapped events. Full detail chunks are lazy-loaded; raw source rows and raw event blocks are included.
- 2026-06-05 detail coverage audit across served canonical chunks found 942,518 / 942,518 rows with raw event blocks, 942,518 / 942,518 rows with raw source rows, and 838,082 / 942,518 rows with narrative descriptions. Remaining narrative gaps are mainly UFOCAT source gaps rather than chunk-loading failures.
- 2026-06-05 validation before the latest deploy included app/bundle JS syntax checks, `pytest tests/test_canonical_web_artifacts.py -q`, Cloudflare bundle validation, direct R2 chunk/detail checks, and production URL version verification.
- 2026-06-05 local release-gate refresh passed after restoring the local `static_bundle` canonical payload from `data/canonical_web`: app/worker JS syntax checks passed, focused Python regression slice passed with 42 tests, frontend/packed-data/trace-worker `.mjs` tests passed, `scripts/check_static_loadout_readiness.py` reported `ready`, `scripts/check_canonical_web_static_payload.py` reported `ready`, and `scripts/validate_cloudflare_bundle.py --bundle-root cloudflare_bundle_r2` reported `pages_safe=true` with 486 R2 upload-manifest entries.
- 2026-06-05 CDP smoke against `http://127.0.0.1:8130/index.html?codexPriority0Smoke=20260605165553` passed. Startup profile preview rendered in about 349 ms, first usable render in about 8.6 s, full `Ready` in about 8.9 s, default state was `mapMode=heatmap`, `traceMode=static`, profile `1954 France Sept-Nov`, Type filter actions worked (`None`, single `Beam`, `Invert`, `Craft Only`, `All`), slow Start/End Date typing held through idle and committed once, and static facility-proximity traces restored across `off`, `playback`, `static`, `points`, `clusters`, and `heatmap`.
- 2026-06-05 trace-facility controls smoke passed locally: default 5 km start/end/between classification rendered 72 matched static segments from 1,950 candidates; 1/2/3/4/5/25 km refreshes all completed without worker error; start-only, end-only, between-only, passes-only, all, and none states all refreshed without dropping the static trace layer unexpectedly.
- 2026-06-05 in-app browser local smoke confirmed keyword entry no longer triggers the old startup/load-failed state (`BERGERAC` held in the search field and retained visible results). Browser automation could not click a hidden `Full Details` button until the Results pane was expanded in the in-app mobile-landscape viewport, but the tested result's canonical summary-to-detail mapping was verified directly: event `1138789185256346` maps to `chunk_000266`, `detail_index=166`, with raw event block, raw source row, and description present.
- 2026-06-05 deployment-header cleanup deployed: `scripts/build_cloudflare_bundle.py` no longer emits a catch-all `/* Cache-Control` rule that caused Cloudflare Pages to concatenate duplicate cache headers onto mutable config files. Rebuilt `cloudflare_bundle_r2` validates with `pages_safe=true`; focused deployment/webapp tests passed with 29 tests. Production HEAD checks now show mutable Pages config files using `Cache-Control: public, max-age=0, must-revalidate`, while startup-profile artifacts use immutable cache headers.
- 2026-06-05 production CDP smoke passed against `https://ufo-timeline.pages.dev/index.html?codexDeploySmoke=20260605_173939`: startup reached `Ready`, startup preview rendered in about 664 ms, full `Ready` in about 13.2 s, default state was `mapMode=heatmap`, `traceMode=static`, profile `1954 France Sept-Nov`, Type filter probe returned non-zero results, static facility-proximity traces rendered 72 matched segments, and trace mode cycling restored static traces across `off`, `playback`, `static`, `points`, `clusters`, and `heatmap` with zero captured console/network errors.
- Local UI/runtime fixes are implemented in source and bundle for Type filter behavior, date entry stability, heatmap default, Phoenix Lights preset, wider horizontal panning, and reduced chronology auto-rescaling.
- 2026-06-03 local validation: JS syntax checks passed for source and bundle, `pytest tests -q` passed with 570 tests, and local browser smoke confirmed the default heatmap France Sept-Nov startup, Phoenix Lights preset, and repaired Type-filter worker result lookup.
- 2026-06-03 follow-up validation: app/worker JS syntax checks passed for source and bundle; all local frontend `.mjs` tests passed; targeted Python regression subset passed with 38 tests; `scripts/validate_cloudflare_bundle.py --bundle-root cloudflare_bundle_r2` passed with `pages_safe=true`, real R2 base URL, and 486 upload-manifest entries.
- 2026-06-03 filter/date CDP smoke passed against `http://127.0.0.1:8130/index.html?codexFilterSmoke=20260603092933`. Slow Start/End Date typing held the typed value through idle and first commit, `None` cleared Type selection, a single non-default `Beam` Type selection returned 4 results, and `All` restored the all-active mode.
- Latest approved deployment gate completed. Future deployments remain intentionally gated.

Next actions:

- Re-run JS syntax checks and focused tests before any additional deployment.
- Run a local browser smoke pass for loading overlay readiness, keyword search, `Full Details`, Type filter actions, slow date entry, default heatmap loadout, and static trace/facility-proximity mode.
- Run a production smoke pass against `https://ufo-timeline.pages.dev/` after each future deployment, especially for R2 lazy detail chunks, keyword search, Type filtering, and static trace/facility-proximity mode.
- Rebuild and validate the Cloudflare Pages/R2 bundle after any source or data artifact change.
- Keep `scripts/benchmark_public_startup_cdp.ps1 -ProbeFilterControls` in the release gate for slow date entry and repeated Type action clicks under heavy map load.
- Deploy only after the current fix set has passed the local gate and the user approves deployment.

Exit criteria:

- Current local app passes syntax/tests.
- Current Cloudflare bundle validates.
- Local browser smoke passes the current default loadout and critical filter/trace paths.
- User explicitly approves deployment.
- Production smoke passes after deployment.

## Priority 1: Location Correctness And Coordinate Trust

Goal: stop obviously wrong dots, especially records whose textual location contradicts mapped coordinates.

Status:

- Multiple coordinate repair/quarantine passes exist.
- Known recurring problem class remains: UFOCAT or other legacy records with `raw_latlong` coordinates that place US/Canada/Europe textual locations in Asia, the Middle East, the Atlantic, or other wrong regions.
- 2026-06-03 current static payload check: `static_bundle` is built from `canonical_preview_map_enrich_v109_geonames_sign_mirror_repair`; rerun checks found zero explicit-U.S. out-of-bounds rows, zero explicit-U.S. state-bound failures, zero named screenshot regression failures, zero named country regression failures, zero packed-point regression failures, and zero broad country-coordinate anomalies.
- 2026-06-03 fresh release-gate rerun passed: coordinate-focused pytest group passed with 39 tests; `static_bundle` audits found 419,813 explicit-U.S. rows with 0 outside-bounds/state-bound failures, 762,452 country-coded rows with 0 broad country anomalies, and 793,571 packed-point rows with 0 packed coordinate regression failures.
- 2026-06-05 coordinate gate rerun passed after the current deploy: `scripts/check_static_coordinate_regressions.py` found 419,813 explicit-U.S. rows with 0 U.S./state failures and 0 named failures; `scripts/check_static_country_coordinate_anomalies.py` checked 762,452 explicit country-coded rows with 0 anomalies; `scripts/check_static_packed_coordinate_regressions.py` scanned 793,571 packed rows with 0 packed coordinate failures.
- 2026-06-05 high-confidence coordinate disagreement packet added as a report-only next-review lane. New outputs: `data/reports/high_confidence_coordinate_disagreement_packet_v109.json` and `.csv`. It filters the noisy `geonames_coordinate_disagreements_v109.csv` queue from 47,742 rows to 3,572 UFOCAT review candidates, requires US/Canada/Australia admin-region agreement when those tokens are present, rejects generic primary names such as Hawaii/Windward, and does not mutate canonical outputs. Admin-token parsing now requires standalone 2-3 letter tokens so county names such as `Adams` cannot incorrectly contribute state-code substrings.
- 2026-06-05 coordinate disagreement review lanes added as report-only outputs: `data/reports/coordinate_disagreement_review_lanes_v109.json`, `data/reports/coordinate_disagreement_admin_matched_v109.csv`, `data/reports/coordinate_disagreement_admin_ambiguous_v109.csv`, and `data/reports/coordinate_disagreement_international_review_v109.csv`. The safest first lane now contains 710 unambiguous one-admin-token US/Australia rows, 28 multi-admin US rows are separated into the ambiguous lane, and 2,834 non-admin-required international rows remain in a separate review queue. Validation passed with 49 focused coordinate tests.
- 2026-06-05 admin-matched repair candidate classifier added as a report-only output: `data/reports/coordinate_admin_matched_repair_candidates_v109.json` and `.csv`. It reviewed the 710-row unambiguous admin-matched lane and found 13 `preview_repair_candidate` rows and 697 `manual_review_only` rows. All 13 immediate candidates are Australian admin-bound contradictions where current coordinates are outside the declared admin bounds and the GeoNames replacement is inside those bounds. U.S. rows stayed manual-review-only because their current coordinates are inside broad declared-state bounds, and distance alone is not safe enough for automatic repair. No canonical, static, or deployment artifacts were mutated. Validation passed with 56 focused coordinate tests.
- 2026-06-05 admin-matched repair sidecar added as a proposed-patch artifact: `data/reports/coordinate_admin_matched_repair_sidecar_v109.json` and `.csv`. It converts only the 13 `preview_repair_candidate` rows into reviewable coordinate patch records, preserves old lat/lon/source metadata, proposes GeoNames-backed `geocoded` coordinates, and skips the other 697 rows. It still does not mutate canonical, preview, static, or deployment artifacts. Validation passed with 60 focused coordinate tests.
- 2026-06-05 preview-apply script prepared but not run on the real corpus: `scripts/apply_coordinate_admin_matched_repair_sidecar_preview.py`. It matches sidecar patches by `canonical_event_id`, verifies old lat/lon/source before any coordinate rewrite, and writes only a new preview corpus when explicitly invoked. Validation passed with 64 focused coordinate tests.
- 2026-06-05 refreshed the admin-matched sidecar against the current `data/canonical_full/deduped_events.jsonl` because the original v109 sidecar guards correctly detected stale old-coordinate values. New report-only outputs: `data/reports/coordinate_admin_matched_repair_sidecar_current_v110.json` and `.csv`; refreshed 13 / 13 patches, skipped 0.
- 2026-06-05 applied the refreshed v110 sidecar to a preview-only corpus: `data/canonical_preview_map_enrich_v110_admin_matched_repair/deduped_events.jsonl`, with report `data/reports/coordinate_admin_matched_repair_preview_v110_from_canonical_full.json`. The preview apply processed 944,578 events, applied 13 / 13 patches, skipped 0, and left canonical/static/deployment artifacts untouched. Direct preview-row validation confirmed all 13 target rows match the proposed repaired coordinates. Focused coordinate regression suite passed with 67 tests.
- 2026-06-05 full canonical-web rebuild from the available v110 preview corpus was rejected because it would have reduced mapped events to 289,831. The currently shipped enriched source behind the 793,571 mapped-event payload is not present as a reusable deduped JSONL, so the safe route is direct artifact patching of the existing enriched `data/canonical_web` payload.
- 2026-06-05 direct canonical-web artifact patcher added: `scripts/apply_coordinate_admin_matched_repair_sidecar_to_canonical_web.py`, with regression coverage in `tests/test_apply_coordinate_admin_matched_repair_sidecar_to_canonical_web.py`. It applies reviewed sidecar coordinate repairs to canonical web event chunks and summary shards, regenerates packed points/traces, updates manifests/reports, and does not mutate `data/canonical_full/deduped_events.jsonl`.
- 2026-06-05 applied the refreshed v110 sidecar directly to `data/canonical_web`: 13 / 13 patches applied, 0 missing, mapped events preserved at 793,571, trace events preserved at 787,726, and trace segments preserved at 787,725. Report: `data/reports/coordinate_admin_matched_repair_canonical_web_apply_v110.json`.
- 2026-06-05 staged the patched canonical web payload into `static_bundle` and rebuilt `cloudflare_bundle_r2` without deploying. Validation passed: static coordinate regressions, country anomalies, packed coordinate regressions, static loadout readiness, staged canonical payload readiness, targeted coordinate tests, JS syntax checks, and Cloudflare bundle validation. The bundle remains deployable pending explicit user approval.
- 2026-06-05 international country-bound splitter added as a report-only lane: `scripts/build_coordinate_international_country_repair_candidates.py`, with outputs `data/reports/coordinate_international_country_repair_candidates_v109.json`, `.csv`, `coordinate_international_country_quarantine_candidates_v109.csv`, and `coordinate_international_country_manual_review_v109.csv`. It reviewed the 2,834-row international queue and produced 0 country-bound repair/quarantine candidates because all current coordinates still fall inside broad country bounds; those broad bounds are too coarse for Atlantic/near-country errors.
- 2026-06-05 coordinate transform evidence lane added as a report-only output: `scripts/build_coordinate_transform_repair_candidates.py`, `data/reports/coordinate_transform_repair_candidates_v109.json`, and `.csv`. It found 47 high-signal UFOCAT transform candidates from the international queue: 46 longitude-sign flips and 1 lat/lon swap, with country counts Spain 27, United Kingdom 18, France 1, and Russia 1. Criteria require original disagreement at least 100 km, transformed coordinate within 50 km of GeoNames, and at least 3x improvement. No canonical, static, or deployment artifacts were mutated. Focused coordinate tests passed with 22 tests for the current report lanes.
- 2026-06-05 coordinate transform sidecar and guarded apply path added: `data/reports/coordinate_transform_repair_sidecar_v109.json` and `.csv` with 47 / 47 proposed patches and 0 skips. New scripts/tests: `scripts/build_coordinate_transform_repair_sidecar.py`, `scripts/apply_coordinate_transform_repair_sidecar_to_canonical_web.py`, `tests/test_coordinate_transform_repair_sidecar.py`, and `tests/test_apply_coordinate_transform_repair_sidecar_to_canonical_web.py`. The apply path validates old lat/lon/source guards plus transform evidence before rewriting event chunks, summary shards, packed points, and trace artifacts.
- 2026-06-05 applied the 47-row transform sidecar directly to `data/canonical_web`: 47 / 47 patches applied, 0 missing, mapped events preserved at 793,571, and no `data/canonical_full` mutation. Report: `data/reports/coordinate_transform_repair_canonical_web_apply_v109.json`. The transform policy metadata was separated from the prior 13-row admin repair policy in `canonical_web_manifest.json`.
- 2026-06-05 restaged the transform-patched canonical web payload into `static_bundle` and rebuilt `cloudflare_bundle_r2` without deploying. Validation passed: manifest policy check, static coordinate regressions, country anomalies, packed coordinate regressions, static loadout readiness, staged canonical payload readiness, Cloudflare bundle validation, JS syntax checks, and 32 focused coordinate transform/admin tests. Local browser smoke against `http://127.0.0.1:8130/index.html?codexSmoke=1780722118083` loaded without startup/load failure, reported 942,518 total events and 793,571 mapped events, and confirmed the default map mode is `heatmap`.
- 2026-06-05 served-payload GeoNames disagreement scanner added: `scripts/summarize_served_geonames_coordinate_disagreements.py`, with outputs `data/reports/served_geonames_coordinate_disagreements_v111.json` and `.csv`. It scans the actual served `data/canonical_web/summary_shards` payload, not stale preview JSONL. The broad mining queue currently contains 45,571 disagreement rows from 762,452 explicit country-coded rows; most are not automatically actionable because GeoNames can match the wrong duplicate place name. This queue is diagnostic/review-only.
- 2026-06-05 served-payload transform candidate flow added and applied for the narrow safe subset. `scripts/build_coordinate_transform_repair_candidates.py` now preserves served `chunk_id` and `detail_index` fields and supports source fallback from `source`; `scripts/build_coordinate_transform_repair_sidecar.py` can recover a missing `canonical_event_id` only from an exact `chunk_id` + `detail_index` + `event_id` target with old-coordinate/source guards. Report outputs: `data/reports/served_coordinate_transform_repair_candidates_v111.json`, `.csv`, `data/reports/served_coordinate_transform_repair_sidecar_v111.json`, and `.csv`. The lane found 18 high-signal UFOCAT longitude-sign-flip repairs: United Kingdom 13, Spain 4, France 1.
- 2026-06-05 applied the 18-row served transform sidecar directly to `data/canonical_web`: 18 / 18 event chunks and 18 / 18 summary shard rows patched, 0 missing, mapped events preserved at 793,571, and no `data/canonical_full` mutation. Report: `data/reports/served_coordinate_transform_repair_canonical_web_apply_v111.json`. Direct post-apply verification confirmed all 18 patched rows match repaired coordinates in both event chunks and summary shards. Restaged the patched canonical web payload into `static_bundle` and rebuilt `cloudflare_bundle_r2` without deploying. Validation passed: static coordinate regressions, country anomalies, packed coordinate regressions, static loadout readiness, staged canonical payload readiness, Cloudflare bundle validation, JS syntax checks, and 19 focused served-transform tests.
- 2026-06-05 refreshed the served GeoNames disagreement queue after the 18-row transform apply. New post-apply outputs: `data/reports/served_geonames_coordinate_disagreements_v112.json` and `.csv`; disagreement rows dropped from 45,571 to 45,472. Re-running the served transform classifier on v112 produced 0 remaining mechanical transform candidates.
- 2026-06-05 served disagreement triage splitter added: `scripts/triage_served_geonames_coordinate_disagreements.py`, with `data/reports/served_geonames_coordinate_disagreement_triage_v112.json` and lane CSVs. Current lanes: 39,535 `geonames_admin_conflict` rows that are usually wrong duplicate-place GeoNames matches; 1,423 clean `admin_matched_review` rows; 37 `admin_ambiguous_review` rows with multiple text admin tokens; 121 `admin_country_missing_text_admin` rows; and 4,356 `international_or_no_admin_review` rows. This remains report-only and does not mutate artifacts. Focused served-coordinate tests now pass with 23 tests.
- 2026-06-05 transform repair manifest bookkeeping fixed. The transform apply script now preserves cumulative transform sidecar history in `policy.transform_coordinate_repair_sidecars` while retaining the existing latest-sidecar `policy.transform_coordinate_repair_sidecar` field for compatibility. Current `data/canonical_web`, `static_bundle`, and `cloudflare_bundle_r2` manifests all record two applied transform repair batches: 47 from `coordinate_transform_repair_sidecar_v109.json` plus 18 from `served_coordinate_transform_repair_sidecar_v111.json`, for 65 total transform repairs. Validation passed: app/bundle JS syntax checks, 25 focused coordinate/served tests, static payload validation, Cloudflare bundle validation, static coordinate regressions, country anomalies, packed coordinate regressions, and static loadout readiness.
- 2026-06-05 served admin-matched repair classifier added as a report-only guard: `scripts/build_served_admin_matched_repair_candidates.py`, with outputs `data/reports/served_admin_matched_repair_candidates_v112.json` and `.csv`. It reviewed the 1,423-row served `admin_matched_review` lane and promoted 0 repairs: all 1,423 rows stayed `manual_review_only` because their current served coordinates are inside broad declared-admin bounds. This protects against false same-admin GeoNames replacements such as `Desert, CANUTILLO, TX` and `Wetlands, TULLY, QLD`, where GeoNames points to a different same-name feature elsewhere in the same state/province. Validation passed with 18 focused served-coordinate tests. No canonical, static, or deployment artifacts were mutated.

Next actions:

- Keep the current coordinate contradiction audits in the release gate and rerun them after any data/artifact rebuild.
- Expand regression fixtures when the user spots new concrete bad-map examples beyond Fargo ND, Butler MO, Marion VA, Pasco WA, Patrick AFB FL, Santa Monica CA, and European Atlantic cases.
- Do not rebuild canonical web/static artifacts from `data/canonical_preview_map_enrich_v110_admin_matched_repair/deduped_events.jsonl` unless the enriched mapping source is restored or the rebuild path is fixed; that source currently drops mapped-event coverage.
- Use the direct canonical-web sidecar patchers for reviewed admin and transform repairs until a full enriched canonical-source rebuild path is available.
- If the current patched bundle is accepted, upload the updated R2 artifacts and deploy the Pages shell, then run production smoke against `https://ufo-timeline.pages.dev/`.
- Keep the 697 `manual_review_only` rows out of any apply path unless stronger contradiction criteria are added, such as county/city-specific boundaries or a source-coordinate format error detector.
- Keep the 28-row ambiguous admin lane out of any automatic apply path until each row is manually resolved as source-coordinate error, multi-location ambiguity, or legitimate route/multi-site record.
- Continue mining the remaining international manual-review rows for safe coordinate-source format errors, local administrative contradictions, and source-specific transform patterns. Keep any new lane report-only until it has old-coordinate/source guards and regression coverage.
- Keep the broad country-bound splitter as a diagnostic lane only; it is not sufficient to catch Atlantic/coastal sign errors because the current bad points can still sit inside broad country bounds.
- Use the 45,571-row served GeoNames disagreement queue as a mining source only. Do not auto-replace coordinates from that queue without stronger duplicate-place disambiguation, county/admin matching, or a mechanical transform signal.
- Use the current v112 served triage, not the stale v111 queue, for future coordinate mining. The next safest lane is not the 39,535 `geonames_admin_conflict` rows; those mostly show GeoNames false matches. Work should start with the 1,423 `admin_matched_review` rows and add stronger city/county/current-coordinate contradiction criteria before any repair sidecar.
- Prefer high-confidence repair when textual location is specific and coordinate sign/order errors are detectable.
- Quarantine suspicious coordinates when repair confidence is not strong enough.
- Rebuild canonical web/static artifacts after corrections.

Exit criteria:

- Known screenshot examples no longer map to the wrong continent/ocean.
- New regression checks prevent those cases from returning.
- Map points, heatmap, clusters, Results, and detail cards agree on corrected mapped status.

## Priority 2: Trace Reliability And Trace UX

Goal: make static/playback traces product-ready under all supported combinations.

Status:

- Static traces, facility/base proximity, trace aggregation, and start/end/between coloring have all received multiple fixes.
- This remains high-risk because trace behavior is complex and performance-sensitive.
- 2026-06-03 CDP static trace smoke passed against `http://127.0.0.1:8130/index.html?codexTraceSmoke=1780500001` with headless Chrome. Default state was `mapMode=heatmap`, `traceMode=static`, startup profile `1954 France Sept-Nov`, facility proximity enabled at 5 km with `start,end,between` active, worker trace-index load mode `worker_fetch`, no worker error, 1,950 candidate segments, 72 matched/rendered static segments, and the static trace layer visible.
- 2026-06-03 trace audit gap: facility proximity main-thread and worker geometry paths are duplicated and need parity coverage for start/end/between/passes, antimeridian, high-latitude, and long-segment skip cases.
- 2026-06-03 worker regression coverage added in `tests/test_trace_facility_worker.mjs`; it passes and directly validates worker start/end/between/passes classification, antimeridian wrapping, high-latitude endpoint matching, disabled class filtering, and oversized pass-scan skipping.
- 2026-06-03 CDP map-mode trace smokes passed for `heatmap`, `points`, and `clusters`; all three retained `traceMode=static`, a visible static trace layer, 72 rendered facility-proximity segments from 1,950 candidate segments, and no trace worker error.
- 2026-06-03 trace facility mixed-toggle coverage expanded in `tests/test_trace_facility_worker.mjs`: `start` only, `end` only, `between` only, `passes` only, `start+end`, `between+passes`, and no-class states are now checked with expected hidden/disabled/pass-skip counters. `tests/test_webapp.py` now guards the shared main-thread/worker segment-distance geometry and key proximity scan fragments. Targeted validation passed: `node tests/test_trace_facility_worker.mjs` and `pytest tests/test_webapp.py -q`.
- 2026-06-03 CDP trace-facility controls smoke passed against `http://127.0.0.1:8130/index.html?codexTraceFacilitySmoke=20260603094929`. Radius presets produced expected live worker refreshes at 1, 2, 3, 4, 5, and 25 km with matched segment counts `9, 26, 30, 34, 72, 514`. Class actions `start`, `end`, `between`, `passes`, `all`, `none`, and restored `all` all applied with no worker errors.
- 2026-06-03 CDP trace-mode cycling smoke passed against `http://127.0.0.1:8130/index.html?codexTraceModeCycleSmoke=20260603095847`. Static traces rendered 72 facility-proximity segments initially, disappeared only while trace mode was intentionally `off` or `playback`, restored to 72 segments after switching back to `static`, and stayed visible with 72 segments across `points`, `clusters`, and `heatmap`.
- 2026-06-03 in-app browser visual smoke passed against `http://127.0.0.1:8130/index.html?codexVisualTraceSmoke=1780506152367`. Default state reached `Ready` with `mapMode=heatmap`, active heatmap canvas and trace SVG layers, 30 loaded Carto basemap tiles, and no startup diagnostics error; the basemap remained visible under static traces.

Next actions:

- Keep wide-window traces on aggregate/LOD paths and narrow/scoped windows on individual traces.

Exit criteria:

- Static traces render consistently after repeated mode changes.
- Playback traces and static traces remain aligned with current filters.
- Facility proximity classification does not suppress all traces unexpectedly.
- Chrome, Edge, and Firefox remain responsive on normal scoped windows.

## Priority 3: Entity Resolution And Dedupe

Goal: reduce duplicate sightings with defensible scoring, provenance, and review controls.

Status:

- Exact subset pruning is known for MUFON and NUFORC sibling files.
- Current canonical deduped count is still substantially above the UFOSINT screenshot benchmark.
- Existing reports are mostly analysis/review-only and have not mutated canonical outputs.
- 2026-06-03 coordinate-conflict source evidence packet added for the narrow `coordinate_conflict_10_to_15km` review slice. Outputs: `data/reports/entity_resolution_cluster_coordinate_conflict_source_evidence_packet.json`, `.csv`, and `.md`; packet policy `entity_resolution_cluster_coordinate_conflict_source_evidence_review_only`; 8 candidate effects, 19 matched canonical events, 0 missing evidence rows, projected event reduction 11, and no canonical outputs mutated. The packet uses provenance-inclusive input-ID accounting and a coordinate-specific CSV with classification, max-distance, risk, identity, and row-level coordinate fields.
- 2026-06-03 coordinate-conflict source review added for that packet. Outputs: `data/reports/entity_resolution_cluster_coordinate_conflict_source_review.json`, `.csv`, and `.md`; review policy `entity_resolution_coordinate_conflict_source_review_only`; 8 reviewed items; 6 `source_review_coordinate_precision_candidate` recommendations with medium confidence, 2 `needs_more_evidence` recommendations with low confidence, projected reduction 8 in the candidate lane and 3 left blocked, and no canonical outputs mutated.
- 2026-06-03 ER scoring model now includes source-location country/region hint agreement and conflict signals. `scripts/score_entity_resolution_candidates.py` extracts lightweight source-location country and US/Canada region hints from preserved source fields, emits `same_source_location_country_hint`, `same_source_location_region_hint`, `source_location_country_hint_conflict`, and `source_location_region_hint_conflict`, and exposes those hints in review samples. Bounded smoke artifact `data/reports/entity_resolution_score_report_location_hints_smoke.json` is review-only with 1,047 scored pairs, 255 likely same-event review candidates, 698 same-country evidence hits, 670 same-region evidence hits, 1 country-conflict risk, 1 region-conflict risk, and `canonical_outputs_mutated=false`. Validation passed: `tests/test_entity_resolution_scoring.py` and targeted webapp/trace tests.
- 2026-06-03 coordinate-conflict scoring gap digest added. Outputs: `data/reports/entity_resolution_coordinate_conflict_scoring_gap_report.json`, `.csv`, and `.md`; report policy `entity_resolution_coordinate_conflict_scoring_gap_review_only`; 8 source-review items joined to evidence rows; 6 coordinate-precision candidates are ready for human review before any decision path, 2 remain blocked on compatible-time evidence, projected reduction is 8 in the review-candidate lane and 3 in the blocked lane, and no canonical outputs were mutated.
- 2026-06-03 medium entity-resolution worklist smoke generated using the source-location hint scorer. Outputs: `data/reports/entity_resolution_score_report_location_hints_medium_worklist_smoke.json` and `data/reports/entity_resolution_candidate_worklist_location_hints_medium_smoke.jsonl`; report-only run scanned 150,000 source records, collected 2,628 records for scoring, scored 1,807 pairs, produced 460 likely same-event, 510 strong, and 816 moderate review candidates, and retained 339 cross-event worklist items. A larger 300,000-record interactive run exceeded the 10-minute shell timeout, so broader queue generation needs batching or an overnight/background run rather than an interactive command.
- 2026-06-03 ER scorer now supports `--offset` for report-only batched worklist generation. First offset batch output: `data/reports/entity_resolution_score_report_location_hints_medium_worklist_batch_000150000.json` and `data/reports/entity_resolution_candidate_worklist_location_hints_medium_batch_000150000.jsonl`; scanned source records 150,000-299,999, scored 2,329 pairs, produced 234 likely same-event, 430 strong, and 1,659 moderate review candidates, and retained 420 cross-event worklist items. Validation passed for the new offset regression.
- 2026-06-05 ER worklist combiner added: `scripts/combine_entity_resolution_worklists.py`, with outputs `data/reports/entity_resolution_candidate_worklist_location_hints_medium_combined_manifest.json` and `.jsonl`. It combines existing bounded/offset worklists without rerunning prior expensive scorer batches, dedupes by `pair_id`, and preserves report-only safety flags. After adding the 900,000-offset tail batch, the combined queue now has 4,804 unique review candidates from 7 batches: 1,204 `likely_same_event_review`, 1,800 `strong_candidate_review`, and 1,800 `moderate_candidate_review`. No canonical decisions or merges were created. Validation passed with focused ER packet/combiner/scoring/suggestion/decision tests.
- 2026-06-05 next ER offset batch completed: `data/reports/entity_resolution_score_report_location_hints_medium_worklist_batch_000300000.json` and `data/reports/entity_resolution_candidate_worklist_location_hints_medium_batch_000300000.jsonl`; scanned source records 300,000-449,999, scored 5,536 pairs, produced 398 likely same-event, 716 strong, and 3,976 moderate review candidates, and retained 738 worklist items. This remains report-only and did not mutate canonical outputs.
- 2026-06-05 additional ER offset batch completed: `data/reports/entity_resolution_score_report_location_hints_medium_worklist_batch_000450000.json` and `data/reports/entity_resolution_candidate_worklist_location_hints_medium_batch_000450000.jsonl`; scanned source records 450,000-599,999, scored 4,042 pairs, produced 270 likely same-event, 1,026 strong, and 2,677 moderate review candidates, and retained 607 worklist items. This remains report-only and did not mutate canonical outputs.
- 2026-06-06 additional ER offset batch completed: `data/reports/entity_resolution_score_report_location_hints_medium_worklist_batch_000600000.json` and `data/reports/entity_resolution_candidate_worklist_location_hints_medium_batch_000600000.jsonl`; scanned source records 600,000-749,999, scored 90,507 pairs, produced 27,987 likely same-event, 15,109 strong, and 25,524 moderate review candidates, and retained 900 worklist items. This remains report-only and did not mutate canonical outputs.
- 2026-06-06 additional ER offset batch completed: `data/reports/entity_resolution_score_report_location_hints_medium_worklist_batch_000750000.json` and `data/reports/entity_resolution_candidate_worklist_location_hints_medium_batch_000750000.jsonl`; scanned source records 750,000-899,999, scored 37,768 pairs, produced 17,303 likely same-event, 6,243 strong, and 8,516 moderate review candidates, and retained 900 worklist items. This remains report-only and did not mutate canonical outputs.
- 2026-06-06 additional ER tail batch completed: `data/reports/entity_resolution_score_report_location_hints_medium_worklist_batch_000900000.json` and `data/reports/entity_resolution_candidate_worklist_location_hints_medium_batch_000900000.jsonl`; scanned source records 900,000-end, scored 50,028 pairs, produced 22,463 likely same-event, 8,549 strong, and 12,082 moderate review candidates, and retained 900 worklist items. This remains report-only and did not mutate canonical outputs.
- 2026-06-06 ER review packet generation added for the combined location-hints worklist. `scripts/build_entity_resolution_review_packet.py` now preserves the legacy `--score-report`/candidate-worklist packet API used by downstream ER decision tooling, and also supports the new combined-worklist packet path. Current outputs: `data/reports/entity_resolution_review_packet_location_hints_medium_combined.json`, `.csv`, and `.md`. The packet ranks the top 200 / 4,804 combined candidates; all 200 are currently `tier_1_likely_duplicate_review` rows. No canonical decisions, auto-merge, or canonical output mutation occurred. Validation passed with focused ER packet/combiner/scoring tests plus a legacy CLI compatibility smoke.
- 2026-06-06 decision-ready ER packet bridge refreshed for the same combined worklist. Current outputs: `data/reports/entity_resolution_review_packet_location_hints_medium_combined_decision_ready.json`, `.csv`, and `.md`. This uses the legacy `packet_policy=entity_resolution_review_only` plus stable `review_item_id`/`items` schema so existing suggestion and decision validators can consume it, but it still mutates no canonical output. The packet contains 600 items: 200 likely, 200 strong, and 200 moderate review rows. A downstream report-only `ai_suggest_entity_resolution_decisions.py` pass produced 167 conservative `same_event` suggestions and 433 `needs_more_evidence` suggestions, with no auto-merge.
- 2026-06-06 non-mutating ER decision staging and readiness gates completed for the current decision-ready packet. Outputs include `data/canonical_full/entity_resolution_decisions_location_hints_medium_ai_accepted.jsonl`, `data/canonical_full/entity_resolution_validated_decisions_location_hints_medium_ai_accepted.jsonl`, `data/reports/entity_resolution_effects_plan_location_hints_medium_ai_accepted.json`, `data/reports/entity_resolution_merge_preview_patch_location_hints_medium_ai_accepted.json`, `data/reports/entity_resolution_merged_event_preview_location_hints_medium_ai_accepted.json`, and `data/reports/entity_resolution_merge_readiness_location_hints_medium_ai_accepted.json`. Validation accepted 600 / 600 staged decisions; the plan-only effects file has 167 merge candidates and 433 deferred candidates; the initial readiness gate blocked 8 merge candidates and flagged 111 review-conflict candidates. After filtering hard blockers, `data/reports/entity_resolution_effects_plan_location_hints_medium_ready_subset.json` contains 159 selected merge effects, `data/reports/entity_resolution_merge_readiness_location_hints_medium_ready_subset.json` reports 0 blocking conflicts, 111 review conflicts, and `ready_for_full_shadow_preview=true`. No canonical event corpus, static bundle, or deployment artifact was mutated.
- 2026-06-06 non-mutating ER shadow preview completed for the current blocker-free ready subset. `scripts/preview_entity_resolution_apply.py` wrote `data/canonical_preview_entity_resolution_location_hints_medium_ready_subset/deduped_events.jsonl` and report `data/reports/entity_resolution_location_hints_medium_ready_subset_preview_apply_report.json`; 159 effects were requested/applied, 0 blocked, projected event reduction was 158, and canonical outputs were not mutated. `scripts/check_entity_resolution_preview_output.py` validated the preview via `data/reports/entity_resolution_location_hints_medium_ready_subset_preview_output_check.json` with `valid=true`, 944,420 rows, and `canonical_outputs_mutated=false`.
- 2026-06-06 blocked ER merge action packet completed for the 8 readiness-blocked candidates. Outputs: `data/reports/entity_resolution_blocked_merge_packet_location_hints_medium.json`, `.csv`, `.md`, `data/reports/entity_resolution_blocked_merge_analysis_location_hints_medium.json`, and `data/reports/entity_resolution_blocked_merge_action_packet_location_hints_medium.json`, `.csv`, `.md`. Classifications: 1 `likely_source_subtype_variant`, 2 `nearby_location_coordinate_variant`, and 5 `type_conflict_requires_review`; 1 candidate is a high-confidence shadow-override candidate. No canonical outputs were mutated.
- 2026-06-06 non-mutating ER shadow-override preview completed. `data/reports/entity_resolution_effects_plan_location_hints_medium_shadow_override_subset.json` starts from the 159 blocker-free ready merges and adds the single high-confidence blocked override candidate, for 160 preview-only merge effects total. `scripts/preview_entity_resolution_apply.py` wrote `data/canonical_preview_entity_resolution_location_hints_medium_shadow_override_subset/deduped_events.jsonl` and report `data/reports/entity_resolution_location_hints_medium_shadow_override_subset_preview_apply_report.json`; 160 effects were requested/applied, 0 blocked, projected event reduction was 159, and canonical outputs were not mutated. `data/reports/entity_resolution_shadow_override_delta_location_hints_medium_summary.json` reports 1 incremental projected reduction and 7 remaining excluded merge effects.
- 2026-06-06 canonical apply readiness and merge-body policy preview completed for the location-hints ER lane. `data/reports/entity_resolution_canonical_apply_readiness_location_hints_medium.json` reports `ready_for_canonical_apply=false` with 3 hard blockers: final merge-body policy still draft, canonical apply command intentionally not implemented, and 7 review-first merge candidates remaining. Draft policy output: `data/reports/entity_resolution_canonical_merge_policy_proposal_location_hints_medium.json`. Compact body preview output: `data/reports/entity_resolution_policy_body_preview_location_hints_medium.json`; validation `data/reports/entity_resolution_policy_body_preview_location_hints_medium_check.json` reports `valid=true`, 160 body previews, 7 skipped previews, 0 invalid conflict metadata, and no canonical output mutation.
- 2026-06-06 refreshed blocker triage for the older 15k worklist ER lane because it remains the highest-impact existing dedupe lane. New joined action packet outputs: `data/reports/entity_resolution_blocked_merge_action_packet_worklist.json`, `.csv`, and `.md`; it contains 269 blocked items classified as 43 `likely_source_subtype_variant`, 65 `nearby_location_coordinate_variant`, 155 `type_conflict_requires_review`, and 6 `coordinate_conflict_requires_review`. New priority queue outputs: `data/reports/entity_resolution_blocker_priority_queue_worklist.json`, `.csv`, and `.md`; after skipping 43 already-selected override candidates, it leaves 226 review items: 71 coordinate-conflict reviews and 155 type-conflict reviews. No canonical outputs were mutated.
- 2026-06-06 worklist blocker analysis continued with report-only type and coordinate conflict splits. Type outputs: `data/reports/entity_resolution_type_conflict_analysis_worklist.json`, `.csv`, and `.md`; it analyzed 155 type blockers and classified 89 `type_only_single_family_subcode_conflict`, 55 `type_only_cross_family_conflict`, 4 `type_only_single_family_with_shape_conflict`, and 7 `type_with_coordinate_conflict`. Coordinate outputs: `data/reports/entity_resolution_coordinate_conflict_analysis_worklist.json`, `.csv`, and `.md`; it analyzed 71 coordinate blockers and classified 30 `coordinate_conflict_10_to_15km`, 32 `coordinate_conflict_15_to_50km`, and 9 `coordinate_conflict_50_to_150km`. No canonical outputs were mutated.
- 2026-06-06 low-risk type-subcode review subset exported for the same older 15k worklist lane. Outputs: `data/reports/entity_resolution_type_subcode_low_risk_review_subset_worklist.json`, `.csv`, and `.md`; it selected 8 lower-risk same-source/same-date/same-location subtype-code candidates and deferred the other 147 type-conflict blockers. This is still review-only: no decisions, preview applies, or canonical output mutations were created.
- 2026-06-06 grouped the low-risk type-subcode subset to avoid overstating overlapping effects. Outputs: `data/reports/entity_resolution_type_subcode_low_risk_review_groups_worklist.json`, `.csv`, and `.md`; the 8 selected effects collapse into 6 source/date/location review groups, with 2 overlapping groups. This remains report-only and is the safer packet to review before any future preview subset.
- 2026-06-06 source-row evidence packet added for the low-risk type-subcode worklist subset. New script/test: `scripts/build_entity_resolution_type_subcode_source_evidence_packet.py` and `tests/test_type_subcode_source_evidence_packet.py`. Outputs: `data/reports/entity_resolution_type_subcode_source_evidence_packet_worklist.json`, `.csv`, and `.md`; it matched 12 / 12 requested canonical event rows for the 8 candidate effects with 0 missing canonical event IDs. This remains review-only and mutates no canonical outputs.
- 2026-06-06 source-review classifier added for the same low-risk type-subcode evidence packet. New script/test: `scripts/review_type_subcode_source_candidates.py` and `tests/test_type_subcode_source_review.py`. Outputs: `data/reports/entity_resolution_type_subcode_source_review_worklist.json`, `.csv`, and `.md`; it reviewed 8 / 8 items and classified all 8 as `source_review_type_subcode_same_event_candidate` under report-only gates. Syntax checks passed for the two new scripts, and the focused ER blocker/source-review test slice passed with 14 tests.
- 2026-06-06 grouped source-review summary added for the low-risk type-subcode worklist lane. Outputs: `data/reports/entity_resolution_type_subcode_source_review_groups_worklist.json`, `.csv`, and `.md`; it joins the 8 effect-level source-review recommendations back into 6 grouped candidates, all 6 currently `source_review_group_same_event_candidate`. This is the cleanest current review artifact for this lane and still creates no accepted decisions or canonical mutations.
- 2026-06-06 coordinate-conflict source evidence/review completed for the narrowest older 15k worklist blocker class. Outputs: `data/reports/entity_resolution_coordinate_conflict_10_15km_source_evidence_packet_worklist.json`, `.csv`, and `.md`, plus `data/reports/entity_resolution_coordinate_conflict_10_15km_source_review_worklist.json`, `.csv`, and `.md`. The evidence packet matched 28 / 28 requested canonical event rows for 30 candidate effects with 0 missing event/input IDs, but the source-review classifier kept all 30 as `needs_more_evidence`; failed conditions were mostly missing/variant summary text, non-single-location identity, and non-coordinate-only conflicts. No canonical outputs were mutated.
- 2026-06-06 preview-only decision/effects staging completed for the 6 grouped low-risk type-subcode worklist candidates. New script/test: `scripts/build_type_subcode_source_review_decision_candidates.py` and `tests/test_type_subcode_source_review_decision_candidates.py`. Outputs: `data/reports/entity_resolution_type_subcode_source_review_decision_candidates_worklist.jsonl`, `data/reports/entity_resolution_type_subcode_source_review_decision_candidates_check_worklist.json`, and `data/reports/entity_resolution_type_subcode_source_review_effects_plan_worklist.json`; the candidate check is valid, with 6 preview decision candidates, 6 plan-only merge effects, and projected reduction 6. `scripts/preview_entity_resolution_apply.py` wrote shadow output `data/canonical_preview_entity_resolution_type_subcode_source_review_worklist/deduped_events.jsonl` plus report `data/reports/entity_resolution_type_subcode_source_review_preview_apply_report_worklist.json`; all 6 effects applied, 0 blocked, and canonical outputs were not mutated. `scripts/check_entity_resolution_preview_output.py` validated `data/reports/entity_resolution_type_subcode_source_review_preview_output_check_worklist.json` with `valid=true`, 944,572 rows, and 6 preview merge rows.
- 2026-06-06 unresolved type-conflict next queue added after excluding the 8 review IDs covered by the 6 preview-staged subtype groups. New script/test: `scripts/build_entity_resolution_type_conflict_next_queue.py` and `tests/test_entity_resolution_type_conflict_next_queue.py`. Outputs: `data/reports/entity_resolution_type_conflict_next_queue_worklist.json`, `.csv`, and `.md`; 147 type-conflict items remain: 74 `source_row_identity_review`, 55 `cross_family_human_review_only`, 7 `subcode_policy_review`, 7 `coordinate_plus_type_blocked`, and 4 `shape_type_semantics_review`. This queue is review-only and mutates no canonical outputs.
- 2026-06-06 source-row evidence packet added for the unresolved `source_row_identity_review` type-conflict lane. New script/test: `scripts/build_entity_resolution_type_conflict_source_identity_evidence_packet.py` and `tests/test_type_conflict_source_identity_evidence_packet.py`. Outputs: `data/reports/entity_resolution_type_conflict_source_identity_evidence_packet_worklist.json`, `.csv`, and `.md`; it covers 74 candidate effects, matched 76 canonical event rows, found 0 missing canonical event IDs, and remains review-only with no canonical output mutation.
- 2026-06-06 conservative source-review classifier added for the unresolved type-conflict source-identity packet. New script/test: `scripts/review_type_conflict_source_identity_candidates.py` and `tests/test_type_conflict_source_identity_review.py`. Outputs: `data/reports/entity_resolution_type_conflict_source_identity_review_worklist.json`, `.csv`, and `.md`; it reviewed 74 items, recommended 67 `source_review_identity_variant_same_event_candidate` rows with medium confidence, and left 7 as `needs_more_evidence`. This remains recommendation-only and mutates no canonical outputs.
- 2026-06-06 grouped the conservative source-identity recommendations to avoid double-counting overlapping candidate effects. New script/test: `scripts/group_type_conflict_source_identity_review_candidates.py` and `tests/test_type_conflict_source_identity_review_groups.py`. Outputs: `data/reports/entity_resolution_type_conflict_source_identity_review_groups_worklist.json`, `.csv`, and `.md`; 67 safe recommendation rows collapse into 32 ready review groups, 7 items remain blocked/needs-more-evidence, and the grouped projected reduction is 38. This remains review-only and mutates no canonical outputs.
- 2026-06-06 preview-only decision/effects staging completed for the 32 grouped source-identity worklist candidates. New script/test: `scripts/build_type_conflict_source_identity_review_decision_candidates.py` and `tests/test_type_conflict_source_identity_review_decision_candidates.py`. Outputs: `data/reports/entity_resolution_type_conflict_source_identity_review_decision_candidates_worklist.jsonl`, `data/reports/entity_resolution_type_conflict_source_identity_review_decision_candidates_check_worklist.json`, and `data/reports/entity_resolution_type_conflict_source_identity_review_effects_plan_worklist.json`; the candidate check is valid with 32 preview decisions, 32 plan-only merge effects, and projected reduction 38. `scripts/preview_entity_resolution_apply.py` wrote shadow output `data/canonical_preview_entity_resolution_type_conflict_source_identity_review_worklist/deduped_events.jsonl` plus report `data/reports/entity_resolution_type_conflict_source_identity_review_preview_apply_report_worklist.json`; all 32 effects applied, 0 blocked, and canonical outputs were not mutated. `scripts/check_entity_resolution_preview_output.py` validated `data/reports/entity_resolution_type_conflict_source_identity_review_preview_output_check_worklist.json` with `valid=true`, 944,540 rows, and 32 preview merge rows.
- 2026-06-06 subcode-policy lane evidence/review added for the remaining 7 high-risk single-family subtype blockers that were not part of the lower-risk subtype preview lane. `scripts/build_entity_resolution_type_conflict_source_identity_evidence_packet.py` now supports a configurable `--packet-policy` for lane-specific evidence output. New script/test: `scripts/review_type_conflict_subcode_policy_candidates.py` and `tests/test_type_conflict_subcode_policy_review.py`. Outputs: `data/reports/entity_resolution_type_conflict_subcode_policy_evidence_packet_worklist.json`, `.csv`, `.md`, plus `data/reports/entity_resolution_type_conflict_subcode_policy_review_worklist.json`, `.csv`, `.md`; the evidence packet covers 7 candidate effects, 6 matched canonical rows, 0 missing event/input IDs, and the review classifier recommended all 7 as `source_review_subcode_policy_same_event_candidate`. This remains recommendation-only and mutates no canonical outputs; the 7 effects still need grouping before any preview-only decision staging.

Next actions:

- Continue refining proper entity-resolution scoring across date, time, coordinates, location text, source family, shape/type, description similarity, and provenance, using the scoring-gap digest to avoid premature canonical decisions.
- Continue duplicate candidate generation with additional `--offset` batches, then merge them into the combined worklist without rerunning prior batches.
- Use `data/reports/entity_resolution_review_packet_location_hints_medium_combined.csv` and `.md` as the current human-readable ER review packet for the top-ranked combined candidates.
- Use the ready-subset packet and readiness outputs for human review of the 111 review-conflict candidates before any canonical apply step is considered.
- Use `data/reports/entity_resolution_type_subcode_source_review_decision_candidates_worklist.jsonl`, `data/reports/entity_resolution_type_subcode_source_review_effects_plan_worklist.json`, and the validated shadow preview under `data/canonical_preview_entity_resolution_type_subcode_source_review_worklist/` as the current non-mutating preview package for the low-risk subtype lane.
- Treat the 6 type-subcode preview candidates as ready for human review against the shadow output, not as canonical merges. Canonical apply remains blocked until merge-body/provenance policy and explicit apply approval are in place.
- Use `data/reports/entity_resolution_type_subcode_source_evidence_packet_worklist.csv` and `.md`, `data/reports/entity_resolution_type_subcode_source_review_groups_worklist.csv` and `.md`, and `data/reports/entity_resolution_type_subcode_source_review_preview_output_check_worklist.json` as the evidence/check set for that review.
- Use `data/reports/entity_resolution_type_conflict_next_queue_worklist.csv` and `.md` as the current unresolved type-conflict queue. Source-identity and subcode-policy lanes now have downstream review artifacts; cross-family, coordinate-linked, shape/type, and the 7 source-identity needs-more-evidence rows remain review-first.
- Use `data/reports/entity_resolution_type_conflict_source_identity_review_decision_candidates_worklist.jsonl`, `data/reports/entity_resolution_type_conflict_source_identity_review_effects_plan_worklist.json`, and the validated shadow preview under `data/canonical_preview_entity_resolution_type_conflict_source_identity_review_worklist/` as the current non-mutating preview package for the source-identity lane.
- Treat the 32 source-identity preview candidates as ready for human review against the shadow output, not as canonical merges. Canonical apply remains blocked until merge-body/provenance policy and explicit apply approval are in place.
- Use `data/reports/entity_resolution_type_conflict_subcode_policy_review_worklist.csv` and `.md` as the current recommendation artifact for the remaining subcode-policy lane. The next bounded ER step is grouping these 7 recommendations so overlapping effects are not double-counted, then preview-only decision/effects staging if the groups remain blocker-free.
- Treat `data/reports/entity_resolution_coordinate_conflict_10_15km_source_review_worklist.csv` and `.md` as a blocker report, not a promotion lane: the current coordinate-source review did not find safe same-event candidates.
- Keep coordinate-conflict blockers review-first unless source-row evidence or a tighter coordinate policy justifies a separate preview-only repair lane.
- Review the new coordinate-conflict source review and scoring-gap candidates before creating any decision/apply path; keep the current review artifacts recommendation-only.
- Apply only approved high-confidence decisions through a streaming/patch-based apply path.
- Keep false merges more costly than missed duplicates.

Exit criteria:

- Entity-resolution scoring is documented and test-covered.
- High-confidence duplicate reductions can be applied reproducibly.
- Canonical IDs and source claims remain stable and inspectable.

## Priority 4: Public Startup And Browser Performance

Goal: keep the public app feeling snappy on average hardware, not only the development machine.

Status:

- Startup profile preview exists.
- Full global catalog hydration remains the main post-preview bottleneck.
- Cloudflare Pages/R2 deployment path exists and is now exercised in production.
- 2026-06-05 production deployment still needs cross-browser cold/warm timing measurements after the latest detail/search deploy. User-reported target remains: default useful view should feel ready before full global hydration finishes.

Next actions:

- Benchmark Chrome, Edge, Firefox, and one lower-spec machine, cold and warm.
- Confirm the startup loading overlay stays visible until the configured default demo state is genuinely usable, not merely until the first partial render.
- Move more full-catalog construction into worker/background phases.
- Keep default France flap usable before global hydration completes.
- Keep map pan/zoom responsive while hydration and trace workers run.
- Bound decoded artifact caches to avoid Chrome memory pressure.

Exit criteria:

- App shell appears quickly.
- Default France view becomes usable before full global hydration.
- Full hydration completes in the background without blocking map interaction.

## Priority 5: Feature QA And UI Polish

Goal: stabilize newer UI features without broad redesign.

Status:

- Area Select, compact chronology controls, Map Controls dock behavior, mobile landscape resizing, legend cleanup, scale bar, and default overlays have all had targeted work.

Next actions:

- QA Area Select one-shot drawing, Clear, Undo, multi-region OR, Results filtering, mobile touch, and map panning restoration.
- Verify Map Controls collapsed/expanded behavior across desktop, mobile portrait, and mobile landscape.
- Verify scale bar, legend controls, UFO sites default-off, and trace label encoding.
- Verify date entry and chronology scaling after latest fixes.

Exit criteria:

- No major UI control blocks map interaction.
- Default loadout matches intended product demo.
- Mobile and desktop core controls remain usable.

## Priority 6: Dataset Integration And Canonical Pipeline

Goal: keep growing the catalog without breaking deployability.

Status:

- Source row audit exists.
- Canonical source records, claims, packed artifacts, and lazy detail chunks are the intended model.

Next actions:

- Preserve every source row as imported, failed, or intentionally skipped exact-subset record.
- Keep source-specific raw fields and unmapped-field reports current.
- Rebuild current app-compatible outputs after canonical changes.
- Avoid shipping raw/intermediate pipeline baggage.

Exit criteria:

- Deployment uses distilled canonical artifacts, not the whole working tree.
- The canonical pipeline can be rerun and audited.

## Priority 7: Deployment Operations

Goal: make deploys repeatable and safe.

Status:

- Cloudflare deployment scripts and docs exist.
- R2 is the intended host for large canonical artifacts.
- 2026-06-05 `cloudflare_bundle_r2` validates locally and points at `https://pub-e9029ab2f6b448daad03d7cde7e15e64.r2.dev`.
- 2026-06-05 Wrangler OAuth and R2 activation were completed, R2 upload succeeded, and Cloudflare Pages production deploy succeeded.
- 2026-06-05 latest successful production deployment URL recorded during deployment: `https://d7328eee.ufo-timeline.pages.dev`; production alias `https://ufo-timeline.pages.dev/` also returns the deployed app.
- Current deployment caveat: R2 canonical objects are reachable, but HEAD checks still show no `Cache-Control` header on representative R2 objects. Pages `_headers` duplicate-cache cleanup is deployed and verified.
- 2026-06-03 preflight clarification: startup profile artifacts are intentionally Pages-hosted under `./data/startup_profiles/...`; global canonical artifacts are R2-hosted. Do not validate startup profiles against the R2 base URL.

Next actions:

- Verify `cloudflare_bundle_r2` after every significant app/data change.
- Confirm no Pages file exceeds limits.
- Confirm R2 manifest paths and public URLs resolve.
- Before deploy, run `scripts/cloudflare_whoami.ps1`, final syntax/tests, Cloudflare bundle validation, and one promoted-bundle startup smoke.
- Deploy only after explicit approval.
- Run production smoke after deploy.
- Apply/verify R2 cache metadata when performance/cache hardening resumes.

Exit criteria:

- A clean deploy can be reproduced from documented commands.
- Production app does not request missing canonical artifacts.
- Pages cache/version behavior is predictable; R2 cache metadata is explicitly verified or documented.

## Current Recommended Order

1. Resume Priority 1 location correctness and facility/base temporal coverage now that the current app-level deploy gate is stable.
2. Harden Priority 2 traces with cross-mode regression tests before adding more trace features.
3. Continue Priority 3 startup/deployment performance work, especially R2 cache metadata and cross-browser cold/warm timing.
4. Keep Priority 0 regression smoke in the release gate before every future deploy.
5. Patch any newly confirmed Priority 0 regression first, then rebuild/validate `cloudflare_bundle_r2`, deploy only after approval, and immediately run production smoke.
6. Continue Priority 3 entity-resolution scoring after map trust regressions are under control.
7. Continue Priority 4 performance once correctness and trace stability are not actively regressing.

# Rich Handoff Manifest

This manifest describes the larger handoff package intended for someone who needs more than the public URL or source-only ZIP.

## Included

- Full self-contained static app bundle: `static_bundle/`
- Current Cloudflare Pages/R2 deployment shell: `cloudflare_bundle_r2/`
- App source, scripts, docs, tests, and parser source.
- App-side reports from `data/reports/`, including entity-resolution, location-quality, benchmark, and facility/base review outputs.
- Facilities and bases data through the app source tree, especially `webapp/static_public/data/map_overlays/`.
- Russia/China and broader external-source ingest project from `C:\Users\jarod\Documents\Chi ufo sightings scrape\ufo-global-ingest`, including its `data/`, `docs/`, `pipeline/`, `sources/`, `config/`, and tests.

## Important Included Facility/Base Files

- `webapp/static_public/data/map_overlays/military_bases.geojson`
- `webapp/static_public/data/map_overlays/military_base_temporal_overrides.json`
- `webapp/static_public/data/map_overlays/military_base_overlay_membership_overrides.json`
- `webapp/static_public/data/map_overlays/research_test_sites.geojson`
- `webapp/static_public/data/map_overlays/research_test_sites_config.json`
- `webapp/static_public/data/map_overlays/new_zealand_military_facilities.geojson`
- `webapp/static_public/data/map_overlays/new_zealand_research_facilities.geojson`

## Included Trace Capability

The package includes `static_bundle/`, which contains the current app shell plus the canonical web runtime data used for points, event chunks, trace indexes, trace segments, trace aggregation, and startup profiles. This is the correct bundle for a self-contained local preview of the trace-enabled app.

## Included Russia/China Work

The package includes the `ufo-global-ingest` project with cached/raw and normalized data. The most useful review files are:

- `ufo-global-ingest/docs/NONLOCAL_SOURCE_RESULTS.md`
- `ufo-global-ingest/docs/LIVE_LIBRARY_RESULTS.md`
- `ufo-global-ingest/docs/ACQUISITION_TARGETS.md`
- `ufo-global-ingest/docs/LARGE_CORPUS_SEARCH.md`
- `ufo-global-ingest/docs/DEDUPE_POLICY.md`
- `ufo-global-ingest/docs/IMPORT_CONTRACT.md`

## Excluded

The rich handoff still excludes the very large canonical rebuild intermediates:

- `data/canonical_full/`
- `data/canonical_manual_review_ai_preview/`
- `data/canonical_web/`

Those folders are useful for deep rebuild/audit work but are not required to run the current app or inspect the current data/product work. They account for most of the 46 GB local workspace.

The original local source database folder is also excluded by default:

- `UFO Databases/`

Keep or archive that separately if the recipient needs to rerun the entire original-source ingestion from scratch.

# Sharing Guide

This workspace contains several different things that should not be shared as one giant folder.

## Fastest Way To Share The App

Send the deployed app URL:

```text
https://ufo-timeline.pages.dev
```

This is the right option for someone who only needs to use or review the tool.

## What Is Needed For A Code Collaborator

Share the source repository files, not the full 46 GB workspace. A collaborator usually needs:

- `webapp/`
- `scripts/`
- `tests/`
- `docs/`
- `parser/`
- `package.json`
- `package-lock.json`
- `requirements.txt`
- `README.md`
- `DEPLOY.md`
- `config.example.yaml`
- `canonical_web_static_payload_manifest.json`

They do not need local browser profiles, old bundles, generated canonical intermediates, or raw source databases unless they are rebuilding the data pipeline.

## Current Deployable Bundle

The current Cloudflare Pages/R2 deploy bundle is:

```text
cloudflare_bundle_r2/
```

This is the compact deployment artifact. It keeps the Pages-safe shell locally and points large runtime data to R2.

Do not use these older/heavier artifacts for sharing unless specifically needed:

- `static_bundle/`
- `static_bundle.zip`
- `cloudflare_bundle/`

## Data And Rebuild Artifacts

These folders are large and should be treated as local build/research artifacts, not normal app-sharing content:

- `data/canonical_full/`
- `data/canonical_manual_review_ai_preview/`
- `data/reports/`
- `UFO Databases/`

Keep or archive these if you want to preserve rebuild, dedupe, provenance, or audit ability. They are not needed by a normal viewer of the deployed app.

## Facilities And Bases Work

The app-side facilities/base data lives under:

```text
webapp/static_public/data/map_overlays/
```

Important files include:

- `military_bases.geojson`
- `military_base_temporal_overrides.json`
- `military_base_overlay_membership_overrides.json`
- `research_test_sites.geojson`
- `research_test_sites_config.json`
- `new_zealand_military_facilities.geojson`
- `new_zealand_research_facilities.geojson`

If someone is reviewing the base/facility layer, share these source files plus the relevant notes in `docs/`, especially `docs/NEW_ZEALAND_FACILITY_CANDIDATES.md`.

## Dedupe And Entity Resolution Work

The dedupe/entity-resolution intermediate outputs are mostly in:

```text
data/canonical_full/
data/reports/
```

These files are important for audit/rebuild work but are too large and noisy for a normal app handoff. Archive them separately if someone needs to inspect the dedupe process.

## China/Russia Corpus Work

The China/Russia source expansion work is not primarily in this app folder. The separate workspace is:

```text
C:\Users\jarod\Documents\Chi ufo sightings scrape\ufo-global-ingest
```

Useful handoff docs there include:

- `docs/NONLOCAL_SOURCE_RESULTS.md`
- `docs/LIVE_LIBRARY_RESULTS.md`
- `docs/ACQUISITION_TARGETS.md`
- `docs/LARGE_CORPUS_SEARCH.md`
- `docs/DEDUPE_POLICY.md`
- `docs/IMPORT_CONTRACT.md`

Share that project separately if the recipient needs the Russia/China acquisition and dedupe pipeline.

## Cleanup Candidates

These are generated/cache folders that can usually be deleted or regenerated, but do not delete them automatically during a handoff without confirming the current rebuild/deploy workflow:

- `.tmp/`
- `.wrangler/`
- `cache/`
- `node_modules/`
- `.pytest_cache/`
- `.python_packages/`

For a clean handoff, create a new folder or ZIP from the source list above instead of copying the entire workspace.

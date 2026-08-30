# UFO Timeline basemap provider repair — 2026-08-29

## Purpose

Remove CARTO's new `API KEY REQUIRED` watermark from the public map by replacing the active keyless CARTO raster configuration with OpenStreetMap's standard raster endpoint. This is an application-shell and configuration repair; canonical datasets and R2 objects are unchanged.

## Production baseline

- Deployment: `db1663ee-5dfc-409f-8f5c-e7e742af15b9`
- Immutable URL: `https://db1663ee.ufo-timeline.pages.dev`
- Source commit: `f350a49103e6badbf00b2f51e6956cea72438174`
- Canonical URL: `https://ufo-timeline.pages.dev`

## Rebuild and validation

The deployable site is the repository root on `main`. Rebuild is the Git checkout itself; no dataset generation or R2 upload is required. Validate the focused basemap tests, JavaScript syntax, JSON syntax, and a Cloudflare preview from the repair branch before fast-forwarding `main`.

## Storage and retention

No full dataset or static-bundle copy is required for this release. Retain the new production deployment as current and `db1663ee-5dfc-409f-8f5c-e7e742af15b9` as the one rollback deployment. Remove the superseded local candidate made from the older `5b54558e` baseline after recording its tree hash and confirming it is reproducible from `reproduction/release.json`.


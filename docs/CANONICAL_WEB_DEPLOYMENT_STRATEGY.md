# Canonical Web Deployment Strategy

This document defines the current static-host deployment strategy for the large canonical UFO/UAP catalog artifacts.

## Goals

- Keep the default `static_bundle.zip` small and safe for normal static hosting.
- Serve million-row canonical catalog experiments from an opt-in `data/canonical_web/` payload.
- Preserve static hosting compatibility: no backend, no database, no runtime geocoding.
- Use lazy loading for full event details so startup only loads compact summaries and binary indexes.
- Preserve existing legacy bundle behavior unless guarded canonical flags are explicitly enabled.

## Payload Modes

Use `scripts/stage_canonical_web_static_payload.py` to create deployment payloads outside the default bundle.

### Trace Runtime Only

```powershell
python scripts\stage_canonical_web_static_payload.py --artifact-dir data\canonical_web --output-root data\canonical_web_static_trace_payload --mode trace-runtime
```

Use this for trace artifact loader/debug work. It copies manifests and packed trace artifacts only.

### Primary Catalog + Trace Runtime

```powershell
python scripts\stage_canonical_web_static_payload.py --artifact-dir data\canonical_web --output-root data\canonical_web_static_primary_trace_payload --mode primary-catalog-trace-runtime
```

Use this for startup/filter/timeline/map-shell previews. It copies points, summary shards, and trace artifacts, but intentionally omits lazy full-detail `event_chunks`.

### Primary Catalog + Trace Runtime + Full Details

```powershell
python scripts\stage_canonical_web_static_payload.py --artifact-dir data\canonical_web --output-root data\canonical_web_static_primary_trace_payload_full --mode primary-catalog-trace-runtime-with-details
```

Use this for production-like deployments where "Full Details" must work. It copies summary shards, trace artifacts, and all lazy `event_chunks`.

## Hosting Layout

For public Cloudflare deployment, prefer the scripted Pages/R2 bundle:

```powershell
python scripts\build_public_cloudflare_bundle.py `
  --static-root static_bundle `
  --output-root cloudflare_bundle_r2 `
  --r2-base-url https://YOUR_R2_PUBLIC_BASE_URL/ufo
```

This wraps startup-profile generation, Cloudflare bundle generation, and
pre-upload validation. The generated `r2_upload_manifest.json` is the source of
truth for which omitted canonical artifacts must be copied to R2.

Curated startup profiles are generated under:

```text
data/startup_profiles/
  manifest.json
  france_1954_flap/
  belgium_1989_1990_wave/
```

These scoped artifacts are intentionally small enough to remain on Pages so the
default famous-flap view can render before the global catalog and trace payloads
finish hydrating.

Deploy the normal static app plus one staged canonical payload with this shape:

```text
index.html
app.js
styles.css
data/app_config.json
data/canonical_web/canonical_web_manifest.json
data/canonical_web/event_chunk_manifest.json
data/canonical_web/summary_manifest.json
data/canonical_web/points.bin
data/canonical_web/points_meta.json
data/canonical_web/trace_event_index.bin
data/canonical_web/trace_event_index_meta.json
data/canonical_web/summary_shards/*.json
data/canonical_web/event_chunks/*.json      # full-detail mode only
```

Precompressed `.gz` siblings should be deployed beside large JSON/bin files when the host can serve them with:

```text
Content-Encoding: gzip
Vary: Accept-Encoding
```

If the host cannot serve precompressed siblings correctly, do not rely on the `.gz` files for performance.

## App Config Flags

The checked-in default must remain disabled:

```json
{
  "canonicalWebArtifacts": {
    "enabled": false,
    "primaryCatalog": false,
    "traceRuntime": false,
    "filteredTraceAggregation": false
  }
}
```

For a guarded canonical runtime preview:

```json
{
  "canonicalWebArtifacts": {
    "enabled": true,
    "primaryCatalog": true,
    "traceRuntime": true,
    "filteredTraceAggregation": true
  },
  "packedPoints": {
    "enabled": true,
    "metadataUrl": "/data/canonical_web/points_meta.json",
    "binaryUrl": "/data/canonical_web/points.bin"
  }
}
```

Use `scripts/serve_static_bundle_with_canonical_web.py` for local previews instead of editing checked-in config:

```powershell
python scripts\serve_static_bundle_with_canonical_web.py --enable-primary-catalog --enable-trace-runtime --enable-filtered-trace-aggregation
```

## Size Expectations

Current full canonical web artifact scale:

```text
Startup gzip: about 7 MB
Lazy non-startup gzip: about 398 MB
Full raw canonical web artifacts: about 2.1 GB
Full gzip canonical web artifacts: about 405 MB
```

The full-detail deployment is large but acceptable for static hosting if the host supports range/caching/gzip behavior well. It is not acceptable to eagerly load all details at startup.

## Required Pre-Deployment Checks

1. Run `scripts/check_canonical_web_runtime_readiness.py`.
2. Stage the desired payload mode.
3. Run `scripts/check_canonical_web_static_payload.py` against the staged payload.
4. Serve locally with `scripts/serve_static_bundle_with_canonical_web.py`.
5. Verify `/data/app_config.json` has the intended guarded flags.
6. Verify `/data/canonical_web/canonical_web_manifest.json` returns HTTP 200.
7. Verify large `.bin` and `.json` files are served with gzip when requested.
8. Browser-smoke primary catalog startup.
9. Browser-smoke "Full Details" if using full-detail mode.
10. Browser-smoke static traces with `filteredTraceAggregation=true`.

## Current Blocker

Headless Chrome/Edge CDP smoke is blocked in the current local automation environment by browser exit code 13 before a debug target is exposed. The Codex in-app browser also blocks local preview navigation with `ERR_BLOCKED_BY_CLIENT`. HTTP/config smoke passed, but browser visual/runtime confirmation still needs a working browser environment.

## Deployment Decision

Recommended next production path:

1. Keep `static_bundle.zip` as the safe default legacy-compatible bundle.
2. Deploy canonical artifacts as a separate static payload under `/data/canonical_web/`.
3. Enable canonical flags only on a preview branch or preview config first.
4. Promote `primaryCatalog=true` only after browser startup, filtering, results, map, details, and trace aggregation pass visual smoke.
5. Keep backend/GPU work out of this path until the static-host ceiling is proven insufficient.

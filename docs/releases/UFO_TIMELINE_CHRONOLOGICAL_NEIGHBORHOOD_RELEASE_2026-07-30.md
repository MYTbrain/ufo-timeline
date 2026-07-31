# UFO Timeline Chronological Neighborhood Release

Release date: 2026-07-30

## Pre-change baseline

- Authoritative checkout: `C:\Users\jarod\Desktop\UFO Timeline map tool`
- Git metadata: absent
- Authoritative frontend: `webapp/static_public`
- Generated frontend: `static_bundle`
- Cloudflare Pages project: `ufo-timeline`
- Cloudflare Pages project ID: `38d2e04e-b622-4e8f-9ea1-b6a101b10448`
- Production branch: `main`
- Previous production deployment ID: `5de106f3-95b4-4d3b-99d4-071e24f489ad`
- Previous production deployment URL: `https://5de106f3.ufo-timeline.pages.dev`
- Previous production status: `success`
- Previous production asset version: `2026-07-21-location-precision-label-v137`
- Wrangler: `4.95.0`
- Cloudflare authentication: OAuth account `f19eee6af8d32295458eda8abec46eac`
- `webapp/static_public`: 31 files, 8,297,602 bytes
- `static_bundle`: 818 files, 7,983,676,380 bytes

| Baseline file | Bytes | SHA-256 |
| --- | ---: | --- |
| `webapp/static_public/index.html` | 64,349 | `f34f4ad963b41d4aeab7d3ad91ccef5799efc168e8a5c2738fbb4fc4a4d95ad5` |
| `webapp/static_public/styles.css` | 119,331 | `5ebee89f2777eb13a620b9853ca7c56423490ad27ddf1e68ee0b28e8bed34b3a` |
| `webapp/static_public/app.js` | 872,124 | `e11f6751a62e5d6144f6d95ecbcd8482e9c6c565dab6bf445d82f770a62d6892` |
| `static_bundle/index.html` | 64,349 | `f34f4ad963b41d4aeab7d3ad91ccef5799efc168e8a5c2738fbb4fc4a4d95ad5` |
| `static_bundle/styles.css` | 119,331 | `5ebee89f2777eb13a620b9853ca7c56423490ad27ddf1e68ee0b28e8bed34b3a` |
| `static_bundle/app.js` | 872,124 | `e11f6751a62e5d6144f6d95ecbcd8482e9c6c565dab6bf445d82f770a62d6892` |
| `static_bundle/data/app_config.json` | 2,521 | `146b7426115e81885fd9319274f090b1e3ff19c82c00de4af5884a4171d0fabc` |
| `static_bundle/data/event_catalog_manifest.json` | 1,533 | `4e5933ecd886ab2c11c0d3b061c636369a74458af96f399327587b2820b162c1` |
| `static_bundle/data/canonical_web/canonical_web_manifest.json` | 5,735 | `561404fbf020414bd2123e6bdb4dc47fc49f7e5539a6d4866f712fa5ee33a303` |
| `canonical_web_static_payload_manifest.json` | 107,282 | `bd8caf1e562b90cc355aa0a000d264c13761d966655497c1b05b09af56e35cb9` |

The canonical payload and R2 objects are out of scope for mutation in this release.

## Implementation

- Added `trace_neighborhood.js`, a reusable browser/CommonJS module containing:
  - canonical craft-type resolution and marker-palette reuse;
  - matching, mixed, and Unknown endpoint styles;
  - deterministic filtered trace adjacency construction;
  - event- and trace-seeded forward/backward/both traversal for depths 1-4;
  - overlapping-seed attribution, duplicate suppression, spatial lookup, dateline wrapping, and great-circle distance.
- Added the Area Filter **Chronological Neighborhood** controls, explanatory disclaimer, hop/direction styling, endpoint markers, outside-area endpoint inclusion, and exact-segment inspector.
- Extended static, playback, selected, neighborhood, dateline-wrapped, and dynamically aggregated traces to color by earlier/later endpoint craft types in Craft Type mode.
- Added a craft-aware viewport/filter aggregation path sourced from the canonical trace-event index. Chronology-only aggregate bins are bypassed in Craft Type mode.
- Added monotonically increasing filter generations to the main thread and both workers. Catalog, trace, selection, legend, and packed-layer work is generation-keyed; stale worker/render results are rejected.
- Consolidated filter application into one atomic refresh and preserved regions, depth, and direction across refreshes.
- Added four synchronized hybrid date controls: authoritative flexible text fields plus native-calendar buttons for exact dates. Partial dates and year `0000` remain supported by the text path.
- Added inline date validation, exact leap/month-length handling, range preservation on invalid input, 44-by-44-pixel touch targets, keyboard labels, and mobile stacking.
- Extended the debug snapshot with filter-generation, stale-result, adjacency-build, traversal, and timing diagnostics.
- Fixed two defects found during live QA:
  - corrected negative-era civil-date conversion so `0000-01-01` round-trips exactly;
  - restricted craft-colored neighborhood halves to Craft Type mode so no hue leaks into other Color By modes.
- Synchronized all changed frontend files byte-for-byte from `webapp/static_public` into `static_bundle`.

### Final source inventory

- `webapp/static_public`: 32 files, 8,370,164 bytes
- `static_bundle`: 819 files, 7,983,748,951 bytes

| Final authoritative file | Bytes | SHA-256 |
| --- | ---: | --- |
| `webapp/static_public/index.html` | 68,919 | `7cf3dacc088308c65816489ce186692094a7f1134097a110f21abf7e7bbc25ce` |
| `webapp/static_public/styles.css` | 124,096 | `bcb233245c0e729baee37a78d2e9ea752aacc41d0f7088d211fadd23cd737b71` |
| `webapp/static_public/app.js` | 913,417 | `ec20fe9d397220bbe542ff0f9f87de6a4868bf58b45f56818a7e5bbff3aecbb0` |
| `webapp/static_public/catalog_filter_worker.js` | 8,610 | `4294a1a000466ccb78311f44ac22da06ebc5a7097001c3cb685ffb8f710076a2` |
| `webapp/static_public/trace_facility_worker.js` | 49,332 | `62d6286544667a9bd9692eb4d5fc5253f98f7836e88a35a437dc26a995a719e2` |
| `webapp/static_public/trace_neighborhood.js` | 21,245 | `da56be9cbff7a92ec5ca966b7b4e2a305d9ca64cb55d2b8d10e97735d15024c6` |

## Validation

### Executable checks

- Python suite: **770 passed**, 1 Starlette/httpx deprecation warning, 0 failures.
- Node suites: **7 of 7 test files passed**, including traversal, craft style, dateline, packed point, packed trace, facility worker, filter worker, and frontend date helpers.
- JavaScript syntax checks passed for `app.js`, `trace_neighborhood.js`, `catalog_filter_worker.js`, and `trace_facility_worker.js`.
- Source/generated parity passed byte-for-byte for all six synchronized frontend files.
- Frozen Pages bundle validator: `ok: true`; all 11 release checks passed.
- R2 manifest comparison against the prior production folder:
  - 366 uploads in both;
  - 913,862,841 referenced bytes in both;
  - identical prefix and public base URL;
  - 0 row differences.
- The canonical data payload was not rebuilt, uploaded, or mutated.

The Windows Python 3.14 validation environment did not include an IANA timezone database. A test-only `tzdata-2026.3` zoneinfo path was supplied for the full run; no deployed file or application dependency was changed.

### Browser QA

Local, preview, and production checks covered desktop and a 390-by-844 mobile viewport.

- Startup reached **Ready / 100%** with:
  - 703,018 canonical events;
  - 580,802 mapped rows;
  - packed-catalog parity sample 256/256 with 0 mismatches.
- Points, Clusters, Heatmap, playback, static traces, Full Event View, Area Filter, filters, and timeline synchronization passed.
- Depth 1 rendered both endpoints, including endpoints outside the drawn area.
- The live probe reached 4 segments / 7 events at depth 1 and 22 segments / 25 events at depth 4 Both.
- Changing depth/direction reused the same adjacency build.
- The inspector identified the link only as chronological adjacency and displayed endpoint dates, elapsed time, derived distance, derived implied speed/missing state, craft types, hop/direction, and region.
- Craft Type mode displayed the “Craft-type traces” legend and endpoint-craft trace status, with no chronology fallback. Switching away removed craft wording immediately.
- Rapid checkbox toggles settled on the final state and reproduced exact sorted event and mapped-event ID sets; the drawn region and depth/direction were preserved.
- `0000`, `YYYY-MM`, leap day, invalid day, native-picker change, duplicate-field synchronization, and All Time passed. Invalid input preserved the last valid ordinal range.
- Mobile QA measured all four calendar controls and both neighborhood selects at 44 pixels high, with zero document or panel horizontal overflow.
- Preview and production console checks found 0 warnings/errors.
- Captured preview and production network checks found 0 failed requests; canonical R2 manifest and packed-point responses returned HTTP 200.

### Measured timings

| Check | Local | Preview | Production |
| --- | ---: | ---: | ---: |
| Time to Ready | 8,243.6 ms | 8,350.5 ms | 9,998.2 ms |
| Adjacency build | 2.5 ms | 3.9 ms | 11.7 ms |
| Depth-4 Both traversal | 5.4 ms | 5.8 ms | 0.3 ms |
| Atomic filter refresh | 1,670-1,810 ms | 2,096.7 ms | 1,931.9 ms |

Local Color By restyle samples were 40.5 ms then 22.6 ms entering Craft Type mode. The first uncached all-time Single Color aggregate rebuild measured 2,892.9 ms; the cached repeat measured 17.0 ms. Warm depth/direction changes traversed only the reached neighborhood and did not rebuild the full adjacency index.

## Release

- New asset version: `2026-07-30-chronological-neighborhood-v138`
- Frozen Pages folder: `cloudflare_bundle_r2_chronological-neighborhood-v138_20260730`
- Frozen folder: 102 files, 53,391,041 bytes
- Deterministic tree hash: `8cb2013031c94373635d34650a7fa697b7a966d52e41f91ddc75c078a728395e`
- Hash matched before preview, after preview QA, and after production deployment.
- Preview branch: `chronological-neighborhood-v138`
- Preview deployment ID: `0c14959d-40f0-43a9-ad66-092bab705c08`
- Preview URL: `https://0c14959d.ufo-timeline.pages.dev`
- Production branch: `main`
- New production deployment ID: `a5f7634e-287e-40ba-ac2d-91e0852e5549`
- Immutable production deployment URL: `https://a5f7634e.ufo-timeline.pages.dev`
- Canonical production URL: `https://ufo-timeline.pages.dev`
- Previous production deployment ID: `5de106f3-95b4-4d3b-99d4-071e24f489ad`
- Wrangler reported 0 production asset uploads because all 101 content-addressed files were already present from the validated preview.

Release status: **production deployed and verified**.

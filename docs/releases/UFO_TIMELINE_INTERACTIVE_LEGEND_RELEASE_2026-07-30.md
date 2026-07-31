# UFO Timeline Interactive Legend Release

Release date: 2026-07-30

## Outcome

The production map legend is now an interactive filtering surface.

- The first event-category dot click isolates that category.
- Additional category clicks add or remove categories without clearing the user's other selections.
- All event categories remain visible in the legend while a subset is active, so the user can add categories back directly.
- Overlay dots toggle the corresponding map overlays and stay synchronized with the existing overlay controls.
- A compact circular Reset control sits between the Legend title and minimize control and restores all legend-managed event and overlay defaults.
- Legend state is announced to assistive technology, has visible focus treatment, and uses 44-by-44-pixel touch targets on mobile.

The default `Color By` mode remains **Craft Type**. Full exact dates remain readable in both synchronized date-control pairs.

## Scope and implementation

- Authoritative checkout: `C:\Users\jarod\Desktop\UFO Timeline map tool`
- Git metadata: absent
- Authoritative frontend: `webapp/static_public`
- Generated frontend: `static_bundle`
- Asset version: `2026-07-30-interactive-legend-v142`
- Canonical payload and R2 objects: unchanged

The release adds a pure shared helper, `legend_controls.js`, for normalized category selection, first-click isolation, additive toggling, reset behavior, grouped overlays, and stable keys. The helper is used by production code and executable JavaScript tests.

Legend event selection is included in the catalog-filter worker request and cache identity. Pre-legend category counts are returned separately so inactive categories do not disappear from the legend. The resulting event set drives markers, exact and aggregate traces, Chronological Neighborhood traversal, results, timeline, and playback rather than applying a map-only visual mask.

Overlay legend controls cover Airports, Highways, individual military branches, discovered research-facility categories, claimed bases, and claimed traces. Existing overlay controls and legend controls share one state and render path.

Changing `Color By` clears a category subset intentionally so category names and colors cannot leak across incompatible legends. Reset restores the currently discovered research categories as well as the static defaults.

## UX defects found and repaired during QA

Two issues were caught before release:

1. Dynamically discovered research categories such as Observatory and Space Launch initially looked enabled but did not have normalized state. Their first click therefore failed to hide them. Discovered categories are now initialized, included in dirty/default detection, grouped toggling, and Reset.
2. The previous mobile legend width was too narrow for the new title, Reset, and minimize controls. The mobile legend is now 204 to 220 pixels wide, provides a measured 6-pixel title-to-Reset gap, scrolls internally, and does not create horizontal page overflow.

An apparent additive-filter count discrepancy was also investigated. The underlying Disc plus Triangle selection contained 273 filtered events; the smaller visible result count was the expected static-trace-linked subset, not lost selection state.

## Automated verification

- Focused Python webapp suite: **46 passed**
- Complete Python suite: **771 passed**, **0 failed**
- Existing non-failing warning: one Starlette/httpx deprecation warning
- Executable Node behavior suites: **8 of 8 passed**
  - catalog filter worker
  - frontend utilities
  - interactive legend controls
  - map move-end behavior
  - packed points
  - packed traces
  - trace-facility worker
  - chronological-neighborhood traversal
- Authoritative/generated parity: **7 of 7 frontend files matched byte-for-byte**
- Cloudflare bundle validation: **11 of 11 checks passed**

The certified Python invocation used the repository root on `PYTHONPATH` and the bundled `tzdata` zoneinfo directory on `PYTHONTZPATH`, which is required for deterministic chronology fallback tests on the installed Windows Python 3.14 runtime.

Coverage includes first-click isolation, additive selection, deselection to zero, reset, grouped and dynamic overlays, source-control synchronization, rapid final-state-wins toggling, stale-generation rejection, stable category availability and counts, color-mode transitions, mobile sizing, source/bundle parity, and existing map/timeline/trace behavior.

## Browser QA

Local, immutable preview, immutable production, and canonical production checks covered desktop and 390-by-844 mobile layouts.

Verified behavior:

- startup reaches **Ready / 100%**;
- Craft Type is the default color mode;
- Disc/Saucer isolates on the first click;
- Triangle adds without clearing Disc/Saucer;
- individual categories can then be removed;
- all 12 category choices remain present while filtering;
- Reset restores all 12 event categories and overlay defaults;
- Airports and military/research overlays synchronize in both directions;
- Observatory and Space Launch dynamic overlays toggle and reset correctly;
- rapid clicks resolve to the final requested state with no stale rendered result;
- date fields show the complete `1954-09-01` and `1954-11-30` values;
- Reset, legend dots, and minimize controls are 44 by 44 pixels on mobile;
- the mobile legend has a 6-pixel title-to-Reset gap and zero horizontal overflow;
- the legend scrolls without moving the map;
- captured failed requests: **0**;
- responses with status 400 or higher: **0**;
- console warnings/errors: **0**.

## Observed interaction timings

| Environment and action | Observed time |
| --- | ---: |
| Local first cold additive selection, including lazy data loading | 12,979 ms |
| Local warm category refresh | 83.7 to 339.8 ms |
| Local rapid-toggle final-state render | 210.8 ms |
| Preview warm additive selection | 353.8 ms |
| Preview Reset | 1,797 ms |
| Production Reset | approximately 1,799 ms |

Warm category changes use the filter-generation and cache path; the long local cold observation included first-use lazy chunk loading and was not reproduced by warm interactions.

## Final file evidence

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `webapp/static_public/app.js` | 936,754 | `cf131f5d6e8231aac51f9c777ea7a74476381f299909691793f51a7fdef4b293` |
| `webapp/static_public/index.html` | 69,418 | `443b09a7b1b18c8a0b81282c347fcd7ebad2f6d4345f767df27d2ba0529fb5f7` |
| `webapp/static_public/styles.css` | 127,639 | `80895b6822f62947b11591a2e214730d2902b2896377da50e689a72a12459eb9` |
| `webapp/static_public/catalog_filter_worker.js` | 10,598 | `909049fd13291dc50a6912e45a8b75cde0c90897bfdd1f9e1e0b45a192cceab9` |
| `webapp/static_public/legend_controls.js` | 4,067 | `825bb16db73d55e9f16cb4cf9ae96fbdd901e5542c6d1d29ec32125f36fe78dc` |
| `static_bundle/data/app_config.json` | 2,522 | `6bbfb2d24df2b404c5a36dd7fa85c4273c6f80e15c75ddcedd0b12be48a813fa` |
| `tests/test_webapp.py` | 100,388 | `321f00a0ce32fd4f731fb220042ff3dca3a921f948bb2ad090424644d6691133` |
| `tests/test_catalog_filter_worker.mjs` | 4,729 | `d61c1abbe2ef0faf16211e8ea3c3a3e54d6150f570cd92d75482d4744557b361` |
| `tests/test_legend_controls.mjs` | 2,722 | `3635d88328b041208189a1310ad07acd56304550c64c20f8c89de9193e8fa4a4` |

## Release

- Cloudflare Pages project: `ufo-timeline`
- Production branch: `main`
- Previous production deployment: `ae7c9cb8-a2de-4bfd-af80-3b46671e3901`
- Frozen folder: `cloudflare_bundle_r2_interactive-legend-v142_20260730`
- Frozen inventory: **103 files**, **53,424,533 bytes**
- Frozen tree hash: `3cb765f9cd9979557f319d2bba3fcea42ec8014632dcbe2bdfccbba75b1d9c43`
- The hash matched before preview, after preview QA, and after production QA.
- R2 manifest: **366 rows**, **913,862,841 bytes**, unchanged from v141
- R2 uploads performed: **0**
- Preview deployment: `faa07cbf-63ca-4408-b93d-e66d394f53cb`
- Preview URL: `https://faa07cbf.ufo-timeline.pages.dev`
- Named preview alias: `https://interactive-legend-v142.ufo-timeline.pages.dev`
- Production deployment: `8ee0381d-4cda-4c55-afd7-b797edf8fbe6`
- Immutable production URL: `https://8ee0381d.ufo-timeline.pages.dev`
- Canonical production URL: `https://ufo-timeline.pages.dev`

The production deployment uploaded zero new files after preview because Cloudflare reused the identical frozen artifact.

Release status: **production deployed and verified**.

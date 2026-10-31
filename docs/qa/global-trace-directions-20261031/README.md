# Global trace direction controls

Published on 2026-10-31 at [UFO Timeline](https://ufo-timeline.pages.dev/).
The runtime source is `caae56d89a35dfbd20302a9e31232147b7c0fc01`, including
the direction-control fix `cafd3235fce9754bbfbf58bce07037a1f7bd8851` and the
updated frontend staging allowlist.

The known-direction filter previously affected only area/case traversal. The
ordinary map bypassed it, and its arrow control was disabled without an area.
Filtering now runs before aggregation in packed, progressive, legacy and
facility-worker paths, and filters playback without destroying retained history.
Cache keys and asynchronous completion checks prevent an older population from
reappearing. A completed all-unknown result remains an empty, cacheable result.

The arrow switch now redraws the ordinary static and playback canvases. Ordered
links have a single arrow; unknown order has a neutral double-headed arrow.
Clipped and wrapped links retain correct orientation. Aggregate representatives
do not receive individual-chronology arrows; area/case interactive badges remain
separate. Arrow density limits affect glyphs only, never trace populations.

Validation:
- `test_known_direction_filter.mjs`: traversal, independent toggles, ordinary
  static/playback availability, case/area controls and cancellation.
- `test_static_trace_direction_arrows.mjs`: actual Canvas drawing, source-backed
  chronology reversal, unknown order, clipping, wrapping, split craft colors,
  layer isolation and progressive density.
- `test_trace_direction_population.mjs`: warm caches, filtering before
  aggregation, progressive cancellation, valid empty results and playback restore.
- `test_trace_facility_worker.mjs`, `test_trace_chronology.mjs`, and
  `test_direction_cases_integration.mjs`: passed.
- JavaScript syntax and diff whitespace checks: passed.
- Browser, ordinary map with no case or selected area: 98 traces became 62 when
  known-only was checked; all 98 returned on uncheck. Arrow visibility changed
  the actual Canvas while keeping the filtered count at 62. See `browser.json`
  and `map-controls.png`.

## Published release

Validated production is `034c76fd-15cf-4e30-a2d3-fea9fd4c1b2c`
([immutable deployment](https://034c76fd.ufo-timeline.pages.dev)). The sole
retained rollback is `742eb895-1387-43bd-b69f-85911b806ee9`, from source
`15f32aa0ded006c2b1a718dcf3a6141adb6ce678`; its pinned index is verified in
`rollback.json`. This supersedes the former rollback designation `11f72dab`.

The canonical site passed verification of 232 served objects; the immutable
production deployment passed hash checks for all three changed runtime files:
`app.js`, `index.html`, and `trace_facility_worker.js`. The worker and its
dependencies inherit the new app version token for returning visitors.
All 150 immutable data objects (586,867,702 bytes) were reused, with zero data
uploads. See `production-release.json`, `production-files.json`,
`immutable-production.json`, and `provider.json`.

Hosted preview `2bd77ead-93cc-4887-b261-db5b9c855ff2` reproduced the
98 → 62 → 98 trace counts and the arrow-only canvas change at a stable count
of 62. Its evidence is `preview-browser.json` and `preview-files.json`.
Production repeated these counts and canvas checks. A returning visitor's
ordinary reload, without clearing caches, updated the old app and enabled the
arrow control. Startup reached Ready with 702,893 total and 582,877 mapped
events and no error. Evidence is kept separately in `production-browser.json`
and `production-controls.png`; the original local `browser.json` and
`map-controls.png` remain unchanged.

The single canonical stage, `.tmp/workspace-analysis-20261008-pages`, was
refreshed in place: 234 files, 41,645,831 bytes, tree SHA-256
`188ac39e5301d9b69c623d8b811839ba0f5ec6f2baa65e04660deafad2011a7f`.
Rebuild with `scripts/prepare_workspace_analysis_release.py --refresh-frontend`
and verify the frozen stage with `--verify-existing`. Stage growth is 7,287
bytes; approximate total task growth is under 1 MiB, with no newly created file
above 100 MiB. No corpus, database, backup tree, or duplicate stage was copied.
Retain this stage, validated production, and the designated rollback. The
superseded hosted preview is a future cleanup candidate requiring a separate
explicit allowlist; no deletion was performed.

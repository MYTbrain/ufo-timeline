# Global trace direction controls

Local preview verified on 2026-10-31; not deployed. The candidate is the source
in the `case-navigation-release/UFO Timeline map tool` worktree on branch
`codex/global-trace-directions-20261031`.

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

Production remains `742eb895-1387-43bd-b69f-85911b806ee9`, with
`11f72dab-fdf5-4eaf-b84c-301637685fa2` as the retained rollback. The validated
deployment stage is unchanged. No dataset/build/backup tree was created or
copied. New artifacts are small, reproducible QA evidence retained with the
source; no new file exceeds 100 MiB. Approximate net growth is under 1 MiB.
There are no superseded generated directories requiring cleanup in this task.

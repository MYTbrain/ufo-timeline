# Playback resume repair

Published on 2026-10-31 at [UFO Timeline](https://ufo-timeline.pages.dev/).
The local verification below records the original reproduction and repair in
the `case-navigation-release/UFO Timeline map tool` worktree on branch
`codex/playback-resume-20261031`.

The user's shared view reproduced a pause/resume failure with playback traces,
persistent history, known-direction filtering, arrows, Follow Results and a
2022-08-05 through 2022-08-07 date window. The icon changed to Playing at event
18/137 but the event stopped advancing. The playback legend passed a plain
viewport snapshot into an intersection helper expecting Leaflet bounds methods.
Its `bounds.getSouth is not a function` exception interrupted the resume handler
before it scheduled another animation frame.

The playback legend now passes the actual map bounds. The application script
version is updated so returning visitors receive the repaired code.
No playback timing, report order, filter, or history behavior was changed.

Validation:
- `tests/test_playback_resume.mjs` passes actual controller, status, trail and
  legend functions through pause/resume; checks continued advancement, retained
  sequence/history, stale-session rejection, speed changes, unmapped events,
  finished restart and all three Play handlers.
- `tests/test_trace_direction_population.mjs` uses the real viewport/intersection
  contract and verifies visible trail counts without discarding offscreen or
  unknown-order history.
- JavaScript syntax and whitespace checks passed.
- In the exact shared view, the timeline control paused/resumed at 18/137 and
  advanced to 42. The map control paused/resumed at 42 and advanced to 116.
  No new console errors occurred. The test view was left paused at 116/137.
  See `browser.json` and `playback-resume.png`.

At local verification, production remained `034c76fd` with `742eb895` as its
rollback; the stage had not yet been modified. The original `browser.json` and
`playback-resume.png` remain unchanged as historical evidence.

## Published release

Validated production is `0ac7c2bc-3f39-4984-920a-5fcd45327d4c`
([immutable deployment](https://0ac7c2bc.ufo-timeline.pages.dev)), from runtime
source `e1d1ce6e287abc4d5e572f86dcd01cce47b2712b` and feature fix
`c7251461f945a8b42f22b9fa2bd8b064f8fd15d6`. The sole retained rollback is
`034c76fd-15cf-4e30-a2d3-fea9fd4c1b2c`, from source
`caae56d89a35dfbd20302a9e31232147b7c0fc01`; its pinned index is verified in
`rollback.json`. The former rollback designation `742eb895` is superseded.

The canonical site passed verification of 232 served objects, and the immutable
production deployment passed hash checks for both changed runtime files,
`app.js` and `index.html`. All 150 immutable data objects (586,867,702 bytes)
were reused, with zero data uploads. See `production-release.json`,
`production-files.json`, `immutable-production.json`, and `provider.json`.

Hosted preview `fcb85210-ec70-49e1-95cb-0e6943b98fe5` reproduced the exact
shared view: playback paused and resumed at 32/137, then advanced to 66/137
without errors while the trail legend contained 12 ordered links. Its evidence
is `preview-browser.json` and `preview-files.json`.

On production, a returning visitor's normal reload, without clearing caches,
updated `global-trace-directions-v1` to `playback-resume-v1`. Startup reached
Ready with 702,893 total and 582,877 mapped events and no error. The map control
paused/resumed at 51/137 and advanced to 80; the timeline control paused/resumed
at 80 and advanced to 114. The populated trail legend showed 17 ordered links,
and no new console errors occurred. The test was left paused at 115/137. See
`production-browser.json` and `production-playback.png`.

The single canonical stage, `.tmp/workspace-analysis-20261008-pages`, was
refreshed in place: 234 files, 41,645,812 bytes, tree SHA-256
`8750a8f760b2cefc95f162cecbf99433f2655f0a1221400eb820629558429e76`.
Rebuild with `scripts/prepare_workspace_analysis_release.py --refresh-frontend`
and verify the frozen stage with `--verify-existing`. The stage shrank by 19
bytes; approximate total task growth is under 1 MiB, with no newly created file
above 100 MiB. No corpus, database, backup tree, or duplicate stage was copied.
Retain this stage, validated production, and the designated rollback. The
superseded hosted preview is a future cleanup candidate requiring a separate
explicit allowlist; no deletion was performed.

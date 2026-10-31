# Playback resume repair

Local preview verified on 2026-10-31; not deployed. Candidate source is in the
`case-navigation-release/UFO Timeline map tool` worktree on branch
`codex/playback-resume-20261031`.

The user's shared view reproduced a pause/resume failure with playback traces,
persistent history, known-direction filtering, arrows, Follow Results and a
2022-08-05 through 2022-08-07 date window. The icon changed to Playing at event
18/137 but the event stopped advancing. The playback legend passed a plain
viewport snapshot into an intersection helper expecting Leaflet bounds methods.
Its `bounds.getSouth is not a function` exception interrupted the resume handler
before it scheduled another animation frame.

The playback legend now passes the actual map bounds. The application script
version is updated so a future release refreshes returning visitors' code.
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

Production remains `034c76fd-15cf-4e30-a2d3-fea9fd4c1b2c`, with
`742eb895-1387-43bd-b69f-85911b806ee9` retained as rollback. The canonical stage
was not modified. These small QA artifacts are reproducible from the recorded
shared view and retained with the fix. No dataset/build/backup directory was
created, no new file exceeds 100 MiB, and approximate net growth is under 1 MiB.
No generated directory was superseded and no cleanup is needed for this fix.

# Direction control defaults

Local candidate on `codex/direction-defaults-20261031`, based on `8d76a7b`.
Not deployed.

Fresh default views now enable Only traces with known direction. Show direction
arrows remains off by default. Both Reset Map and the legend reset restore this
pair. The legend reset indicator compares against the new default. An explicitly
saved arrow preference still applies on return visits; shared links continue to
restore their saved choices. Frozen v2/v3 protocol defaults are unchanged.

Verification on 2026-10-31:
- `test_known_direction_filter.mjs`, `test_share_view_capture.mjs` and
  `test_playback_resume.mjs` passed; JavaScript syntax and whitespace checks passed.
- Capture tests restore false from older v2/v3 baseline links despite the new
  application default and round-trip explicit true and false through compact links.
- Local browser startup reached Ready. Changing both controls and resetting the
  legend restored arrows=false, knownOnly=true; the dirty indicator cleared.
  Changing them again and using Reset Map restored the same pair. A normal reload
  retained arrows=false, knownOnly=true, with no console errors.
- `default-loadout.png` records the verified map and expanded direction controls.

The authoritative candidate is this worktree's source. The canonical deployment
remains `0ac7c2bc-3f39-4984-920a-5fcd45327d4c`; its sole designated rollback remains
`034c76fd-15cf-4e30-a2d3-fea9fd4c1b2c`. The canonical deployment stage
`.tmp/workspace-analysis-20261008-pages` was not changed. No datasets, stages or
backup trees were copied; no files above 100 MiB were created. Net task growth is
under 1 MiB. This small QA directory is retained verification evidence and can be
reproduced with the listed tests and local browser flow. No newly superseded local
generated artifacts require cleanup, and no deletion was performed.

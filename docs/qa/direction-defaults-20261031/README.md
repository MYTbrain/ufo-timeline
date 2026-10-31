# Direction control defaults

Published on 2026-10-31 at https://ufo-timeline.pages.dev/.
Feature commit `fab8d46`; runtime source `4b2ccd5`, based on `8d76a7b`.

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

Preview `b13f1846-01bd-42e3-9fda-8a26a4e209da` passed 232 served-file checks,
browser startup and legend reset. The identical stage was then deployed to
production `90fa1b95-d819-4808-8e8e-387930455391`. Canonical production passed
232 served-file checks and immutable production passed both changed-file hashes.
The browser updated from playback-resume-v1 to direction-defaults-v1 on normal
reload without clearing caches, reached Ready, and showed arrows off with known
direction on. Changing both controls and using Reset Map restored the pair.
No console errors occurred. See `production-release.json` and
`production-defaults.png` for the release receipt and live proof.

The canonical deployment is now `90fa1b95-d819-4808-8e8e-387930455391`; the sole
designated rollback is `0ac7c2bc-3f39-4984-920a-5fcd45327d4c`, whose pinned index
was verified. The previous rollback designation `034c76fd` is superseded.
The single canonical stage `.tmp/workspace-analysis-20261008-pages` was refreshed
in place: 234 files, 41,646,208 bytes, SHA-256
`d994c2cdc2bee19b6bea8f091a265592126876294850e71353a03f3f945d52e5`.
Reproduce with `scripts/prepare_workspace_analysis_release.py --refresh-frontend`.
All 150 immutable data objects were reused, with zero data uploads. Stage growth
was 396 bytes; total task growth is under 1 MiB. No datasets, full stages or backup
trees were copied, and no file above 100 MiB was created. Retain this QA evidence,
current stage, production, and rollback. The hosted preview is superseded and is
eligible for cleanup only under a separate explicit allowlist. No superseded large
local stage exists, and no deletion was performed.

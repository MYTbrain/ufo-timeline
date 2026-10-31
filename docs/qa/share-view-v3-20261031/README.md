# Smaller share links

Published and verified on 2026-10-31 at https://ufo-timeline.pages.dev/.
Production deployment: `742eb895-1387-43bd-b69f-85911b806ee9`.
Runtime source: `15f32aa0ded006c2b1a718dcf3a6141adb6ce678`.

The v3 encoder uses a frozen table of full setting paths and a flat list of
changes. Boolean flips are a single code. It chooses the shortest raw, compressed,
or legacy representation; a small change no longer needs a gzip header. The v2
baseline and dictionaries remain unchanged, and existing v1/v2 links still load.
Missing fields, null/false/empty values, exact coordinates, and inactive controls
are preserved. Decoding rejects overlapping paths, prototype keys, invalid
traversals, excessive input and malformed compressed data.

New captures omit only derived timeline ISO labels and local shape IDs that the
restorer already ignored/regenerated. The Analysis topic uses `s=overview`
instead of `section=analysis-section-overview`; both forms remain readable.

The supplied URL shrinks from 423 characters to 316 with a lossless codec-only
re-encode (including the shortened section). With the redundant capture fields
removed it is 294 characters, a 30.5% reduction. A default-relative settings-only
payload uses 10 characters for one Boolean change and 14 for two. These figures
exclude separately changed camera/date-window state. See `measurements.json`.

Validation passed:
- `tests/test_share_view.mjs`
- `tests/test_share_view_compact.mjs`
- `tests/test_share_view_v3.mjs`
- `tests/test_share_view_capture.mjs`
- `tests/test_analysis_view_repairs.mjs`
- Browser: the Share button emitted v3; decoding matched the captured state;
  all non-camera settings restored exactly, including unchecked boxes;
  Analysis topic navigation and sharing preserved the topic. Hosted camera
  restoration remained within approximately one screen pixel.
- Canonical production verified 232 served objects; the immutable deployment
  verified all five changed frontend files. The 150 immutable data objects
  (586,867,702 bytes) were unchanged, with zero data uploads.
- A returning visitor's existing v2 client updated to v3 after a normal reload.
  A fresh v3 example retained its 294-character URL and decoded exactly. Live
  inventory remained 702,893 total events and 582,877 mapped events.

Release preview caught a pre-existing camera restore issue at fractional zoom:
stale map dimensions shifted latitude by four screen pixels. Restoration now
invalidates the visible container size before a forced Leaflet camera reset,
and keeps the shared camera centered during delayed startup/Analysis resizes.
Leaflet's pixel-origin rounding can leave approximately half a pixel of camera
quantization; hosted restoration remains within approximately one screen pixel.
The decoded camera values and report/area geometry remain exact. Final deployment
evidence is in `production-release.json`, `production-browser.json`, and
`public-files.json`; the live mosaic is shown in `production-mosaic.png`.

The canonical validated artifact is `.tmp/workspace-analysis-20261008-pages`,
refreshed in place from the runtime source above and including the mosaic
readability change. It contains 234 files totaling 41,638,544 bytes, with tree
SHA-256 `a1f902449a1ca3e4212da10d5d66a3e944a08d300a81878b772ba4b4d34c2902`.
Retained rollback is `11f72dab-fdf5-4eaf-b84c-301637685fa2` from source
`151354cb62dc9546b76a62182f539f9302bd1241`; its pinned index was verified.
The previous rollback designation `2850fbfd-1010-417d-86c4-3d94decc5025` is superseded.

This folder contains small reproducible QA evidence only, retained with this
source change. Rebuild by running the listed tests, refreshing the existing stage
from the recorded source, and opening the Share dialog. No dataset or duplicate
staging/backup tree was copied; no new file exceeds 100 MiB. Stage growth is
11,891 bytes; approximate total task growth is under 5 MiB. Superseded hosted
previews `9e44325c-720e-42fc-a75f-7fec850f49a8`,
`34e8edb8-f1db-4198-a8c4-bc3e3ca50678`, and
`d70e9dcc-1d2a-46a1-9193-1bc024c908ee` are eligible for later cleanup only under
an explicit allowlist. No deletion was performed.

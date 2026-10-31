# Smaller share links

Validated local candidate, 2026-10-31. This change has not been deployed.

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
  opening it in another tab restored every captured root exactly, including
  unchecked boxes; Analysis topic navigation and sharing preserved the topic.

The canonical candidate is the source in the `case-navigation-release/UFO Timeline
map tool` worktree, alongside the previously validated mosaic readability change.
Production and its canonical staging tree are unchanged: deployment
`11f72dab-fdf5-4eaf-b84c-301637685fa2`, rollback
`2850fbfd-1010-417d-86c4-3d94decc5025`.

This folder contains small reproducible QA evidence only, retained with this
source change. Rebuild by running the listed tests and opening the local preview's
Share dialog. No dataset/build/staging/backup tree was copied or superseded;
no new file exceeds 100 MiB. Approximate net growth is under 1 MiB. No cleanup
is needed for this change.

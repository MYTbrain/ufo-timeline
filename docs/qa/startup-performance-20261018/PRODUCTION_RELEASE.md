# Progressive startup production release — 18 October 2026

Published and verified: <https://ufo-timeline.pages.dev/>. Production deployment
`16443086-c630-41d8-a793-92a0243a76f6` serves GitHub main commit
`15ab1607390d636f1571fa10bb4c8b137cf391f2`. Cloudflare's Git push publication
completed successfully. All 199 staged runtime files match their committed Git
objects; all 197 public runtime objects match the delivery plan, accounting only
for Cloudflare's exact known Analytics insertion in three HTML files.

The user approved the matched, hosted startup preview for production. Ordinary
visits now use the verified early default map, retain the loading screen until
the map's visual readiness checks pass, and finish loading the complete catalog
in the background. Search, dates, playback and Analysis unlock at full readiness.
The previous full-startup route remains available with `?progressiveStartup=0`.
Bookmarks specifying start/end or windowStart/windowEnd and automation links
retain their complete startup path so their requested view is preserved.

The accepted runtime and its measured comparison are documented in
`releases/workspace-analysis-20261008/STARTUP_COMPARISON_RESULTS.md` and
`startup_controlled_comparison.json`. Deployment adds only default routing,
bookmark guards, a cache revision and accurate release/rollback metadata.
Focused tests cover those routes, control locks and the loading cover.

## Storage and retention

Canonical candidate: the single existing
`.tmp/workspace-analysis-20261008-pages` stage, pinned by the updated delivery
plan. It contains 199 files, approximately 38.18 MiB. Rebuild it in place with
`scripts/prepare_workspace_analysis_release.py --refresh-stage`, then verify
with `--verify-existing`; shared canonical corpus inputs remain in the desktop
project. The 87 immutable R2 objects (101,875,689 bytes) are unchanged.

The sole rollback for this release is the previous validated production
`b4e04dc8-4605-486e-bdbc-174acd3ca37e`, source
`576e09b904341bc7184180fcfbe74a4efecf364d`. The earlier rollback designation
`626b22b4-af0a-4252-8525-0ba21289c0d0` is superseded. The approved
`cb8556e1-d941-4ff7-8e6d-b10cdea21aad` preview and earlier progressive preview
deployments become superseded provider history after production verification;
they are proposed for provider-side cleanup after review, with no deletion
performed here. Unique comparison reports and screenshots remain provenance.

No additional staging tree, corpus copy or large backup is created. New files
above 100 MiB: none. Expected source, Git and QA growth is below 5 MiB, with
effectively unchanged stage size. No dataset or analysis deletion is proposed.
The production provider identity, public byte checks and browser proof are
recorded in the accompanying production receipt after publication.

## Production acceptance

An ordinary URL without the preview flag showed the loading cover, followed by
an interactive default map while the catalog was still loading, then Ready with
Analysis enabled. Final checks passed: 702,893 catalog and worker rows, 582,877
mapped rows, zero packed-point parity mismatches, 770 default Results, unchanged
1954-09-01 through 1954-11-30 dates, and completed facility, trace, canvas and
tile gates. Browser errors: none. The legend, map tools, radar and chronology
chart are visible in `production-ready.png`; `production-loading-screen.png`
records the retained cover.

This production smoke check used the current 973×780 browser viewport. Its
769 rendered links and radar's 263 ordered / 504 unknown-order links reflect
that view, with two coincident endpoints excluded from bearings. It is not the
1265×720 controlled benchmark viewport, so its trace counts and warm-cache
timings are not substituted into the earlier comparison. Initial map and full
Ready milestones were both recorded. An initial public hash check ran while
publication was still pending and saw the previous bootstrap; the complete
post-success check passed without changing any runtime file.

Final canonical runtime tree: `a819766ead6f89c78d30f0ca705bedd95033327731d5e2753e7a9cd83b14bfc9`,
199 files / 40,033,059 bytes. Stage growth from the accepted preview: 104 bytes.
Source, Git and compact QA growth remains below 5 MiB. No newly created file
exceeds 100 MiB; C: remains approximately 87.5 GiB free. There is one local
stage, no new backup tree, no R2 upload and no deletion. Receipts are retained
locally as unique release provenance without a documentation-only production
rebuild; GitHub main already contains the exact deployed runtime and comparison.

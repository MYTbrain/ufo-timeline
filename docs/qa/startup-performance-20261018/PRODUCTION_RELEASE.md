# Progressive startup production release — 18 October 2026

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

# Accepted workspace UI promotion — 8 October 2026

The user authorized deployment of all improvements since the previous release.
The accepted whole-site layout had been served only by the local review server;
it is now self-contained in the release checkout. This promotion preserves the
reviewed layout and original controls rather than introducing a new design.

## Included scope

- Compact header and map-first workspace; full original interactive legend and
  collapsible map tools, side filters on desktop and filter disclosure on phones.
- Original chronology controls grouped and aligned, retaining native date, flap,
  playback, rolling-window, collapse and current-event actions.
- Full-width Analysis workspace with desktop topic rail, native phone selectors,
  focused chart groups and All charts, all original inclusion and cohort controls.
- Supporting-chart navigation opens the relevant group/disclosure before focus;
  guide links activate their Map context; Map return restores timeline geometry.
- Downloads use the filter/date snapshot that produced their displayed result.
  Source crop-field values and provisional morphology retain honest domain labels.
- Shared focus-panel restoration and report return use the original handlers.

`index.html`, `app.js` and `analysis_view.js` incorporate the exact previously
asserted `preview_transforms.py` changes. Fourteen accepted CSS/JavaScript sources
are versioned under `ui/accepted-workspace/` and loaded in the original review
order. They total 82,001 bytes and match the accepted preview sources byte for
byte. The withdrawn `laptop.js` and rejected top-filter layout are excluded.

The promotion receipt is `ui/accepted-workspace/promotion_receipt.json`.
`scripts/promote_accepted_workspace_ui.py --preview-root <retained review source>`
performs all source assertions before changing any file; repeating it verifies
the promoted sources and assets, and `--check` makes no writes. Existing file
line endings are preserved using each file's dominant convention. The local
review server detects `accepted-workspace-ui:v1` and bypasses old injections;
restart it once to pick up that server change. Its shared data overlays remain
local until the separate release contracts are promoted.

The retained review source is the `faithful-polish-preview` directory for task
`01a112de-10d8-7230-b5ab-c5950201bd54`. Its `PURPOSE.txt`, layout/chronology/
navigation receipts and source transforms preserve the acceptance history.
The transform source SHA-256 is
`ab49c57fcef549511fcc87d1673ce1db6eb24ec133f281e39049b286b9a8a9b9`.
Production assets do not depend on that directory or the local preview server.

## Storage and release status

This frontend candidate references shared canonical data and adds approximately
0.1 MiB of small UI assets, the promotion script, receipt and documentation. No
new file exceeds 100 MiB; no corpus, bundle, release tree, backup or database was
copied. No generated dataset is superseded and no data cleanup is proposed.

Publication and final browser verification are performed by the release owner.
At promotion, validated production remains `dc834bac-2108-4de3-baad-47044e2ec51c`
and the single retained known-good rollback remains
`78cc3660-5750-4685-a095-fee6dce37fbf`. The release receipt, once published,
supersedes these current/rollback designations as explicitly recorded there.

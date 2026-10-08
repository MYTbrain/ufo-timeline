# Guided tours and floating Help

Status: published and verified at https://ufo-timeline.pages.dev/.
Deployed GitHub main source: `af13d62`. Feature source: `047c6df`, including
`8b4bcc5`. Baseline production source:
`1578ba4671bc87a6a13af12d631afe7aecab0244`. Publication evidence is kept in
`releases/guided-tours-20261008/`. This UI release preserves the data inventory.

## Entry points and experience

- **Take a tour** is a compact header action. It starts nine Essentials steps:
  map, famous cases, report filters, Results, interactive legend, map display,
  traces, Chronology Explorer and Analysis.
- **Help** retains the reference shortcuts and adds both tour launchers.
- Help opens a bounded floating panel with its own scroll, keeping the header and
  map in place. Its Close button stays visible during scrolling; Escape and an
  outside pointer action also dismiss it. Short screens use the available viewport
  height. Choosing a shortcut or starting a tour dismisses Help, and keyboard
  shortcuts focus the destination control. Tour exit returns focus to header Help.
- **Analysis tour**, also available inside Analysis, covers topics, report dates
  and baseline, coverage, focused chart Views, and wider comparisons in five steps.
- Tours are opt-in. No welcome modal or new content above the map appears on load.
- A small nonmodal card highlights the live control. Back, Next, Finish, Exit and
  Escape work; Left/Right advance steps only while focus is inside the card.
  The rest of the tool remains operable. Narrow screens dock the card at the
  bottom; short screens retain visible navigation. Reduced motion is respected.

## State contract

Tour preparation changes presentation only: primary view, Analysis topic/section
URL, the Overview chart View, open panels/disclosures and scroll positions.
It never selects a demo case, edits dates, changes report/category filters, changes
map mode, starts playback, enables overlays or changes trace settings. Map pan and
zoom are untouched. The tour distinguishes viewport legend counts from Results,
source report chronology from observed travel, and associations from causation.

Presentation leases restore tour-owned layout. Native user interactions claim the
affected layout; if a later step temporarily changes it, its restoration baseline
becomes the user's latest deliberate choice. Thus choosing Time during an Analysis
tour and continuing to its Comparisons step restores Time at completion. A case,
date or filter chosen during a tour remains selected. No generic Reset action is
introduced.

The section URL lease is necessary because the existing Analysis renderer honors
the URL again after asynchronous chart rendering. It uses replaceState, adds no
history entries, and restores the prior URL on exit unless the user changed it.
Coverage explicitly reveals Cohort overview while retaining the prior Overview
View. Missing/loading panels show a short status rather than fabricated counts;
catalog readiness can reveal a waiting Analysis step.

Scroll handling moves actual scroll panes and the document explicitly. It avoids
scrolling overflow:hidden map surfaces, which would displace map controls. The
highlight follows clipping containers, scroll, resize and target-size changes.

## Implementation and checks

- Runtime: `guided_tour.js`, `guided_tour_state.js`, `guided_tour_content.js`,
  `guided_tour.css`, `help_panel.js`; references in `index.html`.
- Small existing-help wording fixes in `app.js` and matching HTML fallback.
- The bounded release builder includes these runtime files in its allowlist.
  It verified the prior stage and refreshed that same small shell in place,
  adding only the five reviewed tour/Help assets and retaining identical R2 pins.
- `node --test tests/guided_tour_state.test.js`: 17 meaningful behavior tests,
  including user ownership/rebasing, restoration order, clipping and card placement.
- Browser walkthrough: all Essentials and Analysis steps, unchanged inputs,
  chosen case/date retention, prior topic and Overview View restoration, deliberate
  topic choice retention, Back and Escape/focus return, narrow and short viewport
  layout. Detailed observations and a representative screenshot live in
  `docs/qa/guided-tour-20261008/`.
- JavaScript syntax and Git whitespace checks pass. No dataset rebuild or full
  bundle build was performed.
- Help follow-up: desktop header height, map position and document height were
  unchanged when opening Help. Dates stayed unchanged through shortcut/tour QA.
  Close/Escape, outside dismissal, destination focus and tour exit focus passed.
  A 404 x 700 CSS-pixel phone viewport and 612 x 350 short viewport kept Help
  within the screen; internal scrolling retained its visible Close button.
  Evidence: `help-panel-checks.json` and `help-panel.jpg` in the same QA folder.

## Storage and retention

Canonical tour source: this frontend worktree and the published GitHub main.
Shared canonical data is referenced in place. Verified guided-tour production is
`e8cf1fb8-2bdb-437e-97af-f856e022f3dc`. The previous production deployment
`0fb396aa-2876-4343-b8b8-87796880a177` is now the sole known-good rollback,
superseding the prior `a70bc14c` designation.
No protected source or prior unique provenance is deleted.

`docs/qa/guided-tour-20261008/` contains small UI evidence from the local preview;
purpose: demonstrate and verify this implementation, provenance: the checked
frontend sources and browser at `http://127.0.0.1:8168/whole-site.html`, rebuild:
run the existing shared-data preview and replay the tour, retention: retain with
this implementation until superseded by a reviewed tour update. It contains no
dataset or deployment-tree copy. No new file exceeds 100 MiB. New managed files
and QA evidence are below 1 MiB, plus a small Git delta if committed.
The Help follow-up adds approximately 0.16 MiB of source/documentation/UI evidence,
plus a small Git delta; it creates no staging tree or large artifact.

The reused `.tmp/workspace-analysis-20261008-pages` contains 184 files totaling
32,302,392 bytes; its tree SHA-256 is
`33a7da86dafaa5ff8b50f46ff04a8827ac9ce732ed91e23e77e75a10b3fe5feb`.
Its growth is only 41,351 bytes; immutable R2 uploads remain unchanged at 87
objects / 101,875,689 bytes. C: was below 100 GiB free, so preparation charged
only actual growth against the sub-100-MiB allowance in the storage policy.
Deployment evidence and Git metadata keep estimated new local growth below
1 MiB. No file exceeds 100 MiB. The release evidence directory contains
small source/verification receipts and a browser proof, rebuilt by rerunning the
bounded release verifier and live Help/tour checks; retain with this UI release.
No new staging/backup tree was created or superseded. No deletion was performed.
Previously superseded shell stages and the explicit cleanup proposal remain
documented in `WORKSPACE_ANALYSIS_RELEASE_20261008.md`; cleanup is independent of
this feature. No new cleanup action is needed.

## Production verification

All 182 publicly retrievable Pages assets passed exact byte/hash and required
cache-header checks; the other two entries are `_headers` and `.nojekyll`.
Only the previously declared exact Cloudflare Analytics HTML envelope was
accepted. All 184 staged source assets also matched their committed Git bytes.
The live browser loaded all 702,893 records, opened both tours, restored Map and
keyboard focus on exit, preserved dates, and kept the header/map position stable
when Help opened. No console errors were observed. The receipt, detailed browser
checks and `production-help.jpg` are retained in the release evidence directory.

Receipt-only pushes trigger an equivalent Cloudflare Git deployment with the same
runtime inventory. The final provider ID is observed locally after that push,
without creating another receipt-push loop. The inventory is authoritative.

# Guided tours — local review

Status: implemented in the frontend worktree, not published. Baseline: production
source `1578ba4671bc87a6a13af12d631afe7aecab0244`. The live site and data release
remain unchanged.

## Entry points and experience

- **Take a tour** is a compact header action. It starts nine Essentials steps:
  map, famous cases, report filters, Results, interactive legend, map display,
  traces, Chronology Explorer and Analysis.
- **Help** retains the reference shortcuts and adds both tour launchers.
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
  `guided_tour.css`; references in `index.html`.
- Small existing-help wording fixes in `app.js` and matching HTML fallback.
- The bounded release builder includes these runtime files in its allowlist.
  It has not been run and the validated deployment staging tree is untouched.
- `node --test tests/guided_tour_state.test.js`: 17 meaningful behavior tests,
  including user ownership/rebasing, restoration order, clipping and card placement.
- Browser walkthrough: all Essentials and Analysis steps, unchanged inputs,
  chosen case/date retention, prior topic and Overview View restoration, deliberate
  topic choice retention, Back and Escape/focus return, narrow and short viewport
  layout. Detailed observations and a representative screenshot live in
  `docs/qa/guided-tour-20261008/`.
- JavaScript syntax and Git whitespace checks pass. No dataset rebuild or full
  bundle build was performed.

## Storage and retention

Canonical tour source: this frontend worktree. Shared canonical data is referenced
in place. Current validated production remains deployment
`0fb396aa-2876-4343-b8b8-87796880a177`; the sole designated production rollback
remains `a70bc14c-550c-4057-b461-bca4fd7aba27`.

`docs/qa/guided-tour-20261008/` contains small UI evidence from the local preview;
purpose: demonstrate and verify this implementation, provenance: the checked
frontend sources and browser at `http://127.0.0.1:8168/whole-site.html`, rebuild:
run the existing shared-data preview and replay the tour, retention: retain with
this implementation until superseded by a reviewed tour update. It contains no
dataset or deployment-tree copy. No new file exceeds 100 MiB. New managed files
and QA evidence are below 1 MiB, plus a small Git delta if committed.

No new staging/backup tree was created or superseded. No deletion was performed.
Previously superseded shell stages and the explicit cleanup proposal remain
documented in `WORKSPACE_ANALYSIS_RELEASE_20261008.md`; cleanup is independent of
this feature. No new cleanup action is needed.

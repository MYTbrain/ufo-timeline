# Legend direction radar

Status: published and verified at https://ufo-timeline.pages.dev/ with the
corpus-wide timing recovery. Publication receipts are in
`releases/corpus-timing-20261008-v3/`. Feature baseline: `275a769`.

## Behavior

The original interactive legend retains its event symbols, colors, counts,
overlay controls and trace key. A collapsible **Report-link directions** section
adds a compact grayscale radar above these entries. It shows the actual date
window, counted population and ordered/unknown totals. **Direction counts &
shares** expands the eight compass-sector table, exclusions and interpretation.

Static statistics follow the exact source links under the current dates,
categories, trace-gap, facility and map-rendering scope. They are accumulated
before trace sampling/aggregation; aggregate representative bearings cannot
change the percentages. Scope text distinguishes viewport-intersecting links,
all filtered links, and an existing fallback that includes offscreen links.
Cached arrays retain their immutable source summary. Pending replacement work
and the limited startup preview show loading instead of old percentages.

A selected case/area uses the same visible raw-link population and neighborhood
direction rules as its existing direction breakdown and inspectors. That
population takes priority over the global layer mode. A point-only selection
does not produce direction counts. Playback uses the visible playback trail,
including its existing persistence and visibility filters.

**Show direction arrows** defaults off and remembers a deliberate choice.
It toggles the existing selected-link badges only; global static/playback canvas
lines already have no badges. The toggle is unavailable without a trace-capable
case/area selection. Hiding badges leaves the connection lines and their click
inspectors intact. Reset legend restores arrows off.

Directions describe map bearings of chronological report connections, not
measured craft travel. Accepted chronological ordering supplies direction;
unresolved links are separately disclosed and excluded from percentages.
Coincident endpoints and invalid/undefined bearings are excluded separately.
Existing backward/both neighborhood semantics are preserved and explained in
the expanded table. The radar labels its adaptive outer percentage scale;
an empty/loading/off chart has reference spokes but no invented distribution.

## Verification

- Direction-summary tests cover compass geometry, wrap, chronology uncertainty,
  backward/both semantics, duplicate suppression, immutable streamed snapshots,
  accessible compact markup and honest empty/loading/off states.
- The actual packed builder test deliberately reduces three original links to
  one north-pointing aggregate: source statistics remain one north, one east
  and one unresolved. It also checks viewport subsets, cached metadata,
  fallback disclosure, pending/off state and source immutability.
- Actual legend-view fixtures cover selected links with global mode off,
  point-only selections, playback visibility, missing populations and limited
  startup previews. Chronology route/integrity tests and existing relevant
  packed/facility/famous-case checks pass.
- Browser: Ariel School shows one ordered NW link and one unresolved link.
  Turning badges on preserves exact connection-canvas pixels, radar markup,
  dates and Results count. Badge count returns to zero when switched off.
- A broader 1994-09-01 through 1994-11-30 window shows 54 ordered links,
  360 unresolved links and 16 coincident-endpoint exclusions. Sector counts:
  N 3, NE 4, E 9, SE 2, S 0, SW 5, W 31, NW 0.
- Outer radar collapse survives full legend refresh. Trace Off without a
  selected population displays an off state, and no stale percentages.
- Map-container resizing now requests the existing debounced viewport trace
  refresh. Explicit metadata also refreshes narrow packed populations after a
  pan/zoom, even when their rendered LOD stays individual. The actual refresh
  predicate test verifies this case and avoids rescanning all-filtered fallbacks.
- Wide desktop and 400 x 840 CSS-pixel layouts retain the existing legend;
  the phone radar fits its scrollable body without horizontal overflow.
  Responsive button-handler layout was also checked by invoking its actual
  DOM click because the browser automation pointer used inconsistent zoom
  coordinates under the temporary viewport override. No application override
  or injected UI remains. Temporary viewport settings were reset.
- JavaScript syntax, Git whitespace and browser error checks pass.

## Storage and retention

Canonical feature source is this frontend worktree and published GitHub main.
Shared canonical data is used in place. Verified runtime publication is
`d7836d81-11e7-412b-98a0-4920ca0612a2`; the sole designated known-good rollback
is prior production `192e21f6-9c44-4b89-8d88-361e1c3d10d6`. The existing stage
`.tmp/workspace-analysis-20261008-pages` was refreshed in place. Combined
chronology/radar publication and storage receipts are in the corpus timing
handoff; no extra corpus or staging-tree copy was created.

`docs/qa/legend-directions-20261008/` has small browser-check metadata and a
representative screenshot. Purpose: verification of this UI; provenance: checked
source plus the existing shared-data local preview; rebuild: run that preview
and repeat the named date/case checks; retention: retain with this feature until
superseded by a reviewed update. No new file exceeds 100 MiB. Source, tests,
documentation, QA and the small local Git delta add approximately 0.25 MiB
(managed project artifacts). No superseded stage/backup is created and no cleanup is
needed for it. Previously identified generated stages remain a separate,
explicitly approved cleanup proposal; protected data is untouched.

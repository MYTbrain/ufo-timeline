# Direction and famous-case navigation

The current frontend source adds arrow-only grayscale direction badges to area
selection and a searchable 85-case dropdown directly beneath Famous Flaps.

## Direction statistics

Badges preserve the arrow glyph, use eight neutral tones, and keep direction
names in accessible labels and inspector statistics. Badge locations are
staggered along their connections to reduce overlap. Clicking or activating a
badge with the keyboard opens the existing chronology inspector.

Report connections with unknown chronological order use one neutral,
double-headed arrow with a dashed border. This includes explicit uncertain-order
records and zero-day gaps without an explicit known-order flag. The badge's
rotation describes only the undirected axis between locations. Both heads mean
the connection has no assigned travel direction, not that bidirectional travel
was reported. Ordinary ordered links retain their single-headed grayscale arrows.
Unordered report links that draw the same line share one badge per rendered map
copy. This includes reversed endpoints and shorter overlapping paths with a
shared endpoint whose axis differs by less than one screen pixel at the current
zoom. The popup lists every underlying report link and lets users select each
one. This groups only the display: report IDs, link counts, dates, sources, and
uncertainty totals are retained. Divergent paths and paths that only meet at an
endpoint keep separate badges; zooming in can separate nearby paths again.

The inspector and the expandable Direction breakdown in Area Selection show
an eight-sector radar chart, counts, and percentages. Bearings describe straight
Web Mercator map connections. They do not estimate a witnessed craft heading.
The denominator is unique selected ordered report-link directions before wrapped map
copies. Forward and direct links count once; backward reverses the displayed
connection; a link reached in both directions displays two arrows and contributes
one count in each direction. Invalid, coincident, and map-collapsed endpoints
are excluded explicitly. Unknown-order links are counted separately and excluded
from direction percentages. An all-unordered selection shows its link count and
uncertainty explanation without a direction table or radar. Radial scales and
the exact percentage table are shown when ordered links exist.

## Case navigation

The catalog is independent of the canonical corpus. Each preset has reported
dates, an approximate vicinity circle, aliases, and labeled source references.
Alphabetical and Chronological buttons organize the dropdown by name or by
reported start date, oldest first. Sorting preserves the search and active case;
the browser remembers the chosen order. Alphabetical is the initial default.
Chronological labels show the year or full year range first; Alphabetical labels
show the case name first.
Selection centers the map without changing zoom, briefly highlights its circle
twice, and applies dates plus an event-seeded vicinity filter. Reduced-motion
preferences replace the pulses with one static highlight. Default viewing dates
include one calendar day before the sourced start and after the sourced end;
the card keeps the historical date separate from the active viewing range.
Other filters remain active, so candidate results can be empty. The picker
searches its own small catalog without initiating a full-corpus keyword search.

Case selection enables Static traces and the bucket that includes same-day
connections. Case connections are built from recognized craft-category groups
on each exact calendar date, using the existing filtered global report pool.
Neighboring reports within each group can connect beyond the vicinity. Only
actual report points in the vicinity seed the default direct, zero-hop
selection; geographic crossings alone do not become case connections. The
Results list retains local candidate reports, including isolated reports.
It also includes both endpoint reports of every displayed case connection, even
when an endpoint lies outside the selected area. Each distinct event ID appears
once, and endpoint records are retained even if their display text duplicates
another source record. Cards use a subtle solid accent border and "In selected
area" label for local reports, and a dashed neutral border with "Connected outside
area" for external endpoints. The Results header counts both groups. These rows
support Description, Full Details, selection, sorting, and paging. The map's area
cohort, area counts, statistical summaries, and playback remain area-scoped.
Only endpoints present in the shared filtered catalog are included; hiding their
traces removes the related rows. Clear removes case-specific labels and restores
the preceding Results scope.
Unknown categories, explained/context records, inexact dates, conflicting
duplicate IDs, invalid coordinates, and zero-length edges do not form links.

The left case picker retains only the selected case name and Clear. A compact
case summary in Results shows the reported date and location, the active viewing
dates, connection count (or unavailable reason), and Fit connections. Background,
date uncertainty, approximate area scope, date-window behavior, connection
interpretation, and references sit in a closed "Case details & sources"
disclosure. Its expanded content is height-capped and scrollable. Same-case
refreshes preserve disclosure state; choosing another case or Clear resets it.
The summary remains available when the owned vicinity is removed, with its
inactive status. The generic area/hop banner is hidden during case focus to avoid
duplicating the case summary and inside/outside counts.
Fit connections includes their remote endpoints. The inspector labels Endpoint
A/B and uncertain same-day ordering; it shows an undirected map axis for these
links without assigning a cardinal direction percentage, and does not treat
estimated time metadata as an observed flight direction or compute a same-day speed.
Facility proximity and existing source/type/precision/keyword filters still
apply. Clear restores the original trace mode and same-day bucket unless the
user changed those controls after selecting the case.

Switching cases preserves the original date and area selection for Clear.
Manual date changes, All Time, and timeline/flap presets keep the case, its
vicinity, and connection focus selected until explicit Clear (or Reset filters).
A user-edited area is preserved. Out-of-catalog sourced dates leave the existing
selection intact; optional padded days at catalog boundaries are clamped. Date
notes distinguish uncertain or broader context windows.
See `FAMOUS_CASE_PRESETS.md` for catalog source and geographic limitations.

## Craft legend symbols

Both craft legends place small monochrome SVG silhouettes between the existing
color dots and labels. They illustrate all 17 craft categories, including a
neutral unknown symbol for unrecognized keys. The symbols describe category
names, not reconstructed objects. They inherit the theme's text color and do
not add another color encoding. The icon and label share the existing solo
button; visibility dots, counts, color pickers, and keyboard labels are retained.

## Local verification and preview

For the current Pages layout, run `python -m http.server 8138 --bind 127.0.0.1`
from the repository root and open `http://127.0.0.1:8138/index.html`. The compact
checked-in runtime assets retain the existing immutable R2 URLs; no corpus build
is needed. The original research checkout can also use
`scripts/serve_frontend_preview.py` with its existing shared runtime data.
The October release record documents the production baseline and storage decisions.

Validated with the direction, catalog, case/arrow integration, chronology,
area-selection, and flap-label Node tests; 14 targeted analysis-shell and existing
area/flap checks. A browser smoke check confirmed Kecksberg
alias search, case switching/restoration, actual drawn area selection,
arrow-only badges, and clickable direction statistics. For one selected cohort,
18 unique links remained the denominator despite 54 wrapped map badges.
Its direction shares were W 61.1%, E 33.3%, and SE 5.6%.

The local configuration's optional hosted overlay fetches and labeled tile
service were unavailable during preview; the built-in world view and canonical
core catalog were sufficient for these feature checks. No hosting change is
included in this task.

The legend/year-label follow-up passed the legend, 85-case catalog, and actual
app integration Node checks, JavaScript syntax validation, and all nine analysis
shell checks. The live preview confirmed 20-pixel symbols without clipped label
buttons, year-first Chronological options, and name-first Alphabetical options.

The case-trace correction passed dedicated grouping tests, actual app integration
tests, existing neighborhood/direction tests, syntax validation, and all nine
shell checks. Live checks in the current primary catalog showed Phoenix Lights
with 50 vicinity reports and 57 distinct-location connections under Craft Only.
Kecksburg showed five reports and five connections with Type set to All. With
Craft Only, one local Light report survived and had no same-day Light neighbor;
the case card now explains that Type All can include original Sighting/Unknown
labels with inferred craft categories. Nimitz showed no mapped vicinity reports
and disabled Fit connections. Falcon Lake had one local anchor connected to a
same-day same-category report outside its vicinity, confirming that remote
endpoints are retained. The arrow inspector opened in the browser and displayed
Endpoint A/B, matching calendar dates/categories, uncertain timing, an undefined
speed, and the 57-link direction denominator. Test changes also cover unchanged
trace control restoration and preserving later user edits on Clear.

The zoom/date follow-up passed case-window and actual app integration checks,
syntax validation, same-day grouping tests, and all nine shell checks. Integration
covers unchanged map zoom, centering, circle pulse completion/cancellation,
reduced motion, suppression of late startup fitting, calendar boundaries, and
case retention through manual dates, rolling/flap windows, and All Time. The
browser confirmed a padded Phoenix window of March 12â€“14 with 58 local reports
and 66 connections. Editing Start to March 11 retained Phoenix, its vicinity,
and its traces, and refreshed the case card's active viewing range. Switching
cases at a wide zoom preserved that scale. The saved image records the edited
view rather than treating the exploratory date range as the historical case date.

The uncertain-arrow follow-up passed the direction module and actual app
integration tests, syntax validation, and all nine shell checks. Tests cover
mixed ordered/unordered populations, zero-day records without explicit flags,
wrapped-copy deduplication, neutral double-headed badges, keyboard/click access,
and all-unordered selections without percentages or a radar. The browser checked
Mariana film's two links: both badges were neutral and double-headed, and clicking
one showed an Eastâ€“West map axis, A/B endpoints, unknown report order, and two
links excluded from the ordered-direction denominator. The same-day neighbor
data, case date window, and report count were preserved.

The shared-arrow correction passed the direction helper, actual app integration,
syntax validation, and nine shell checks. The live Mariana example has two
different report connections: Salem to Great Falls and Great Falls to Stanfield.
Their map paths overlap within one screen pixel at the fitted zoom. The browser
confirmed one visible double-headed badge, both links in its popup, and successful
selection of the second link with its distinct endpoint IDs. Tests retain both
raw paths and uncertainty counts, separate the paths at closer zoom, and keep
divergent or end-to-end connections separate. Zoom changes recalculate grouping.

The endpoint-Results follow-up passed the actual app integration, syntax, and
nine shell checks. The integration fixture preserves five area reports and adds
three unique connected reports; further chain members and crossing-only links
stay excluded. It covers current-filter membership, duplicate IDs, distinct
endpoint records, trace/bucket/facility visibility, area-only playback IDs, card
labels, and Clear restoration. The live Florence case showed one area report
plus two outside endpoints (Hesdin Forest and Linzeux). Description inspection
preserved the source's missing-description status for Hesdin; Full Details opened
the Linzeux record and its preserved source fields.

The context relocation passed the actual app integration, syntax validation,
and 11 shell/area checks. Tests exercise the moved Fit action and compact Clear,
the distinct reported/viewing dates, disclosure state across refreshes and case
switches, and unavailable-link status. The browser checked Frederick Valentich:
the left card contains only its name and Clear, while Results shows the date
summary, six connections, five reports inside and three connected outside.
Expanding details revealed the background, scope, and sources; Fit continued to
work and left the disclosure open until the user closed it.

## Storage lifecycle

The canonical change artifact is the current source under
`webapp/static_public`, plus the small tests and documentation in this checkout.
The user-facing QA images in `docs/ui/direction-case-preview.jpg`,
`docs/ui/famous-case-order.jpg`, and `docs/ui/legend-case-labels.png` record the
browser checks and are retained as
small documentation. Reproduce them by running the preview, selecting an area
and opening an arrow's inspector, or switching the case order. The sorting
follow-up also verified persistence after reload and search/selection retention.
The legend image uses the built-in world view to show the symbols clearly.
`docs/ui/famous-case-traces.png` is the retained case-trace QA image: run the
preview, select Phoenix Lights with Craft Only, choose the built-in world view,
and use Fit connections. It records the 57-connection case card and map. No
generated data or large staging artifact is required to reproduce this check.

The current deployment remains
`D:/UFO-Timeline-Context-Evidence/release/context-evidence-mapping-provenance-v2-20260812/acceptance-site`,
referenced by this checkout's `static_bundle` junction. The retained rollback is
`C:/Users/jarod/Desktop/UFO Timeline map tool/static_bundle_rollback_f21b47a5`.
Its `data/canonical_web` also supplies current runtime data through a junction
and must remain protected.

No deployment, corpus regeneration, bundle copy, staging tree, backup, or
superseded release was created. No new file exceeds 100 MiB. The initial feature
batch grew by less than 1 MiB including its retained QA images; the legend/year-label
follow-up adds about 0.2 MiB and the case-trace correction about 0.15 MiB.
There are no superseded generated artifacts from these changes to clean up.
Existing protected storage is unchanged.

The zoom/date follow-up edits only small source, tests, and documentation, plus
one retained UI proof image (`docs/ui/famous-case-focus.png`). Reproduce the image
by selecting Phoenix Lights at a wide map zoom and adjusting its viewing dates.
It creates no dataset, bundle, staging tree, release, or backup. No new artifact
exceeds 100 MiB; source and proof-image growth is approximately 0.16 MiB. No
superseded generated artifact requires cleanup. The current deployment and
rollback above remain the retained pair.

The uncertain-arrow follow-up edits small frontend source, tests, and this
documentation. `docs/ui/uncertain-case-connections.png` records the revised Mariana
film view and is retained as reproducible UI evidence: select that case, use Fit
connections, and click a dashed double-headed badge. No dataset or bundle is
regenerated, and no release or rollback is added. No new file exceeds 100 MiB;
approximate net growth is below 0.2 MiB. There are no superseded generated artifacts
from this change to clean up; the canonical source and retained release pair
remain those designated above.

The shared-arrow correction retains one small QA image at
`docs/ui/deduplicated-case-connections.png`. Reproduce it by selecting Mariana
film, using Fit connections, and opening its single dashed double-headed badge.
The popup records both links on the shared line. The earlier uncertain-arrow
image is retained as the before-state evidence for this display correction.
Canonical source remains `webapp/static_public` with its tests and documentation.
No dataset, staging tree, bundle, backup, deployment, or rollback was generated;
the existing deployment/rollback pair above remains retained. No new file exceeds
100 MiB, approximate net growth is below 0.2 MiB (the new QA image is 119,419 bytes),
and no superseded generated artifact
from this change needs cleanup.

The endpoint-Results follow-up retains the small proof image
`docs/ui/famous-case-results-endpoints.png` (123,124 bytes). Reproduce it by
selecting Florence stadium sighting, choosing the built-in world view, and
opening Results with its local and connected cards. Canonical source remains
`webapp/static_public` plus the focused tests and this documentation; the current
deployment and retained rollback above are unchanged. No dataset, bundle,
staging directory, backup, or release was generated, no new file exceeds
100 MiB, and approximate net growth is below 0.2 MiB. There are no superseded
generated artifacts from this follow-up to clean up.

The context relocation retains `docs/ui/famous-case-context-results.png`
(139,839 bytes) as UI evidence. Reproduce it by selecting Frederick Valentich,
using the built-in world view and Fit connections, and leaving Case details
closed. The canonical artifact remains the frontend source, focused tests, and
this document. The current deployment and last-known-good rollback above remain
the retained pair. No data, staging tree, bundle, backup, or release was created;
no new file exceeds 100 MiB, approximate net growth is below 0.2 MiB, and there
are no superseded generated artifacts from this change to clean up.

# Famous UFO case navigation catalog

The catalog contains 86 individually referenced historical reports, cases,
and controversies. It is an editorial navigation aid, independent of the canonical
sighting corpus. Inclusion does not identify an object's origin or validate a
historical claim. Known natural explanations, hoax controversies, and conflicting
accounts are represented alongside unresolved reports.

The current production implementation is the repository-root `famous_case_presets.js`.
It exports `UfoFamousCasePresets` in the browser and CommonJS in Node. Its immutable
records hold names, aliases, reported dates, short attributed descriptions,
approximate navigation centers and radii, and labeled source references. New
entries can be added through the existing `add` definition with an individually
relevant source, without changing the application integration.

The optional order argument to `filterCases`, `sortCases`, and `formatCaseLabel`
accepts `alphabetical` or `chronological`, with chronological as the default.
An explicitly saved alphabetical preference remains available and is respected.
Alphabetical labels use `Name · Year`; chronological labels use `Year · Name`.
Cases spanning multiple years retain the full year range in either display order.
Chronological sorting follows each preset's first date, including context windows.

Dates are historical reported calendar dates, used as inclusive date-filter
windows. A range can include intervening days without documented case activity.
Jimmy Carter and Colares intentionally use a full-year context window. Roswell
uses the July announcement/recovery context rather than a purported crash date.
Early-modern pamphlet dates have not been converted between historical calendars.
Date notes preserve these distinctions.

Centers and radii are manually chosen approximate exploration areas. They are
not recovered witness coordinates, claimed trajectories, validated geocoding,
case boundaries, or a determination that any corpus event belongs to the case.
Most local reports use a 75 km radius; aerial routes and regional reports use
larger radii. Selection applies an inclusive date window padded by one calendar
day before the sourced start and after the sourced end, clamped to available
catalog dates. Sourced dates and chronological labels remain unchanged. The map
centers on the vicinity without changing zoom, and its circle highlights twice
briefly. Reduced-motion settings receive one static highlight. The case remains
selected through manual date changes, timeline presets, and All Time; Clear
releases the selection. The card shows both sourced dates and the active viewing
range. Other existing filters
may produce fewer results or none. A zero-result window does not mean that the
historical report is absent from every source.

The Results summary now checks the complete loaded catalog for mapped records
inside the active circle/date window before applying filters. It distinguishes
an empty vicinity from nearby records hidden by filters and waits for catalog
ingestion before claiming zero coverage. These counts are contextual candidates,
not verified case membership.

The original 85 presets have a completed, bounded database identity review. Their
`catalogReview` separates matched cases from cases with no confirmed source
identity; an empty vicinity does not substitute for this decision. The generated
crosswalk is rebuilt from the three reviewed group JSONs by
`scripts/build_famous_case_identity_crosswalk.py`, which checks production data
pins, source/date identity and original-detail pointers without changing data.

Reviewed `catalogRefs` identify original records explicitly naming a case or
describing its distinct source account. The Results summary lists these records
separately, with direct Full Details access even when they are unmapped, misplaced,
or excluded by the map filters. It does not manufacture points, enlarge the
circle, or change map/statistical cohorts. Identity fields fail closed on catalog
drift; mapping notes are scoped to the reviewed coordinates. Multiple source
entries are not independent incidents. Stored dates outside the reported preset
are shown explicitly, along with non-exact precision and distinct image/radar
context roles where relevant. Unconfirmed presets are marked in the dropdown.
See `docs/releases/FAMOUS_CASE_FULL_IDENTITY_REVIEW_2026-10-06.md` and its
machine-readable receipt for the complete list; the earlier vicinity audit is
a separate geographic candidate-coverage check.

Case presets also enable direct same-day, same-category report connections.
The graph groups exact-date, mapped, recognized-craft records from the filtered
global report pool and connects consecutive records within each group. Local
report points seed the vicinity selection; remote linked endpoints may extend
beyond it, but unrelated lines crossing the vicinity are not selected. No
synthetic event is created at the preset center. Isolated local reports remain
visible, and the case card gives a connection count or an explicit zero message.
The Fit connections action includes remote endpoints.

Same-day record order can depend on estimated times or stable IDs. The inspector
uses Endpoint A/B and labels this uncertainty; connection orientation cannot
establish an origin, destination, flight heading, or shared object identity.
Unknown-order links use a neutral double-headed arrow with a dashed border and
are excluded from directional percentages; their map axis is undirected.
This graph is separate from ordinary mixed-category chronology traces. Selecting
a case enables Static and the gap bucket containing same-day links; Clear
restores these prior controls unless the user changed them. Existing facility
and report filters continue to apply.

Source selection was reviewed on 6 October 2026. The five requested cases are
Kenneth Arnold (Smithsonian), Falcon Lake (Library and Archives Canada), Kecksburg
(released NASA records plus an individual historical overview), Betty and Barney
Hill (University of New Hampshire collection plus an individual historical
overview), and Ariel School (an individually referenced secondary overview).
Other entries use individually relevant secondary overviews, NICAP research
archives, contemporary newspaper transcriptions, released-record mirrors, and
submitted witness reports. Source type labels distinguish these categories.
Secondary references are starting points for research, not an exhaustive source
review. Some archive URLs may require ordinary browser access when automated
fetching is restricted.

Dalnegorsk / Height 611 was added on 30 October 2026 with the reported local date
of 29 January 1986, using the [Dalnegorsk Museum's local history](https://dalmuseum.ru/height611/).
Its 75 km vicinity is centered approximately on Dalnegorsk, not a claimed impact
coordinate. The description distinguishes the reported sphere and fire from later
material-origin claims; this navigation entry does not validate those claims or
include later follow-up sightings as part of the original event. The new entry is
outside the original 85-case identity review: `catalogReview` is null and no
`catalogRefs` are asserted. Nearby catalog reports do not establish identity.
Its dropdown availability is computed from the loaded catalog and active report
filters, like the other presets. That indicator describes possible contextual
report connections and does not substitute for a database identity review.

Results shows a compact Case details / Fit connections row. Case name, reported
date/location, matched source records, connection status, background, and sources
are inside the disclosure; the active viewing range is not repeated. The outer
disclosure owns scrolling, avoiding nested scroll panes for matched records.
Existing disclosure persistence, record inspection, and Fit actions remain intact.
The Results header, case disclosure, and area count retain their content height;
only the report list uses remaining space. In the reported 206-result view, the
expanded detail body ends before the area count and pagination, with no overlap.
Browser proof is retained in `docs/ui/expanded-case-results-layout.png`.

The availability previews use each preset's default padded dates and actual
vicinity geometry against the complete, report-filtered all-date catalog.
Dropdown rows show only the case date/name, followed by a thin colored outline
around a positive visible link count. Cases without visible links have no suffix.
The native select remains in use: browsers with customizable-select support render
the outlined badges, and older browsers retain readable plain-text link counts.
Reports-only, no-local-report, outside-catalog, filtered-link, and record-identity
statuses remain in option tooltips rather than adding text to every row. Loading
and failed-load states appear once in the shared picker status as Checking links
or Link counts unavailable. These are presentation changes only; source data,
identity reviews, counts, and graph semantics are unchanged. The same case graph
builder and accepted chronology evidence used by the map also supply the counts.
Changing report filters, chronology evidence or the known-direction preference
invalidates the cached preview. Facility filters may further hide connections,
as disclosed beside the picker.

The October 30 change is based on the current root frontend at `4af19b0`, with
the October 20 production data configuration, not the older desktop checkout's
`webapp/static_public` shell. Its reviewed stage is reused by
`scripts/serve_current_frontend_preview.py`; only nine named frontend files are
overlaid. Published R2 assets are routed through the loopback preview in memory
to avoid the host's localhost CORS restriction. Compressed scientific data bytes
are unchanged and no data copy is written. Production and rollback designations
are recorded in `releases/workspace-analysis-20261008/current_production.json`.
The canonical development artifact is this worktree's root source plus tests;
the authorized deployment overlays only these nine frontend files into the
existing stage, as recorded in `docs/qa/case-navigation-20261030/RELEASE.md`.
Superseded edits from the older checkout were restored after preserving a
78,124-byte recovery delta and literal-path receipt at
`D:/UFO-Timeline-Safety-Backup/case-navigation-baseline-correction/`.
The delta is provenance, not an additional deployment. No newly created file
exceeds 100 MiB; estimated net growth is below 2 MiB. No superseded large staging
or backup artifact was created and no dataset cleanup is required.

Initial browser verification on the corrected preview completed with the full
catalog and Analysis ready. Chronological was selected, Dalnegorsk had reports
but no links, and Ariel School displayed two links. Enabling Only traces with known
direction reduced Ariel to one link and one connected outside report; its
compass retained the single northwest ordered link. The existing Encounters
panel opened with its two in-scope being reports. Small screenshots are retained
as validation evidence in `docs/ui/case-availability-current-version.png` and
`docs/ui/encounters-and-compass-current-version.png`; they can be reproduced from
the local preview and are not deployment artifacts. Ten focused Node suites and
the three case-navigation shell checks passed.

`tests/test_famous_case_presets.mjs` checks required cases and dates, citation
schema, unique IDs, valid geographic/date windows, immutability, browser export,
accent-insensitive aliases, token-AND searching, and contextual selection windows.
It does not assert that historical claims are scientifically validated or that
the corpus contains corresponding records.

This change creates only small source, test, and documentation files. It creates
no dataset, staging directory, static data copy, deployment bundle, or retained
release. The catalog remains part of the current application source; release and
rollback retention decisions remain those of the project's deployment lifecycle.

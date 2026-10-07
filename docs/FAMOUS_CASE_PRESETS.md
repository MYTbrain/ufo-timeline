# Famous UFO case navigation catalog

The initial catalog contains 85 individually referenced historical reports, cases,
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
accepts `alphabetical` or `chronological`, with alphabetical as the default.
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

Reviewed `catalogRefs` identify original records explicitly naming a case or
describing its distinct source account. The Results summary lists these records
separately, with direct Full Details access even when they are unmapped, misplaced,
or excluded by the map filters. It does not manufacture points, enlarge the
circle, or change map/statistical cohorts. Identity fields fail closed on catalog
drift; mapping notes are scoped to the reviewed coordinates. Multiple source
entries are not independent incidents. See the October 6 catalog identity and
vicinity coverage audits in `docs/releases/`.

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

`tests/test_famous_case_presets.mjs` checks required cases and dates, citation
schema, unique IDs, valid geographic/date windows, immutability, browser export,
accent-insensitive aliases, token-AND searching, and contextual selection windows.
It does not assert that historical claims are scientifically validated or that
the corpus contains corresponding records.

This change creates only small source, test, and documentation files. It creates
no dataset, staging directory, static data copy, deployment bundle, or retained
release. The catalog remains part of the current application source; release and
rollback retention decisions remain those of the project's deployment lifecycle.

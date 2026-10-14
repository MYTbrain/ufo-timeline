# Encounter map and selection candidate

The phone review preview is updated on the existing `encounter-preview-20261013`
branch. This batch is a review candidate; it does not publish to production or
push GitHub. The current native legend, craft colors, controls, chronology and
report-direction radar remain in place.

## Interaction and scope

Encounters now has a visible legend section and an independent map layer. Neutral
symbols distinguish abduction without an indexed being description, beings
without an abduction classification, both in one report, and optional unclear
abduction mentions. These are disjoint display categories, not verified species
or independently verified incidents. Legend category visibility does not erase
its eligible counts or its reports from the inspector.

The open Encounters controls provide All encounters, Abductions, Being encounters
and Both presets, searchable multi-select descriptions, counts, and a deliberate
selection target. **Encounter overlay** is the default: source/date/search/
precision/area constraints apply while craft Type and craft-legend visibility do
not restrict the overlay. **Filter reports and Analysis** applies the original
encounter facets to the shared report cohort. The explicit Include all report
types action remains available; selecting an encounter never silently widens
the raw Type filter. Preset counts are before encounter facets and follow their
target's other restrictions. Description choices are OR; abduction and being
facets combine with AND. Reset clears both facets and chart-applied encounter
IDs while retaining other source/date/geography choices.

The independent layer is necessary because 1,999 of the 3,217 indexed reported
abductions have raw Type Unknown. Craft Only can hide those records. The direct
71-shard source-index join found 13,290 mapped and 3,029 unmapped indexed encounter
reports. Unmapped records remain available in the inspector; no location is
invented. A drawn area requires an actual mapped point, so records that cannot be
placed inside it are outside that area's eligible overlay cohort.

## Map identity and relationships

The layer uses only existing canonical coordinates. It retains source location
precision; source-provided coordinates are not independently verified sites.
Display groups retain every original report ID and anchor at an actual report
coordinate, never an invented centroid or purported common incident. At most
320 spatial display groups render at once. Markers have 44-pixel interaction
targets. Group and whole-scope inspection use bounded pages, including eligible
unmapped reports. Locate pans while preserving zoom; source details remain an
explicit action.

Details distinguish source-reported craft association, same-record co-reporting,
no craft reported, and not established. An existing craft category/color sample
is shown only for the first two states. Repeated source accounts and shared
dates/locations do not establish incident identity or craft identity.

Highlight existing links matches exact original report endpoint IDs from current
static, playback or selected-area chronological report links. It adds a neutral
halo beneath the original line, preserving its craft color. It creates no new
encounter-to-craft edge, reorders no chronology, and enters neither radar counts
nor adjacency traversal. Scope signatures, active-layer checks, pending-state
guards and ready trace-population metadata prevent old links from being treated
as current. Off/hidden/reset changes clear highlights. An empty result says no
current detailed trace uses that report as an endpoint; it does not claim that
the report has no related sightings.

No proximity connectors are added. A future explicit proximity exploration
would need labelled day/distance/precision evidence, undirected display and
exclusion from report-direction statistics. The present pilot has no verified
exact sites/UTC with which to establish measured encounter travel.

Country Area membership uses the same geography-aware catalog worker as other
report filters, and fails closed while loading or unavailable. A discovered
dictionary bug is corrected: source country and projected country retain
separate IDs; a known projection overrides source country and an unknown
projection preserves the original fallback.

## Verification and retention

Focused actual-app tests exercise overlay/report targeting, source/date/search/
precision/drawn-area/country/exact-ID scope, hidden category counts, unmapped
inspection, viewport caching, search without report refresh, contradictory
selection guards, original report identity, bounded deterministic aggregation,
and reset behavior. Country membership tests run the actual worker. Retained
analysis and trace/radar/famous-case regressions are checked against the current
runtime. Browser inventory has no enabled browser surface, so interactive phone
visual acceptance is pending; runtime/DOM and public mobile HTTP checks are
reported separately.

The canonical candidate is the current source checkout and requested hosted
preview. Shared corpus, encounter evidence/origins/enrichment, original source
chunks and coordinates remain unchanged. The validated 184-file production
stage remains untouched. Production and sole rollback IDs are recorded in the
fresh phone-preview QA receipts. The curated temporary shell is under 50 MiB,
removed only by its literal path/size/hash inventory after public verification.
No full corpus/database/static-bundle copy or new file above 100 MiB is created.
Approximate persistent growth is under 500 KiB plus small Git/Wrangler cache
metadata. The superseded preview is recoverable from its retained Git source;
the current hosted preview is kept for user review. Larger cleanup proposals
remain separate and require their documented literal allowlists.

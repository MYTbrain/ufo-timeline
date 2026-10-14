# Being and abduction comparison atlas

Local implementation, baseline `f52e0cd`; no deployment, push, corpus import or
source-record rewrite. Preview:
http://127.0.0.1:8168/whole-site.html#analysis-section-encounters.

## Source selection

The first encounter feature extracted the five collections already preserved
in the project; it did not establish that they form the best available abduction
dataset. The new [16-source review](ABDUCTION_DATASET_REVIEW_20261013.md) compares
case catalogs, investigation archives and respondent surveys, with access,
provenance and reuse boundaries. HUMCAT original cards and Rosales' narratives
are strong candidates for source reconciliation and enrichment. URECAT helps
compare conflicting accounts. Respondent surveys and private interviews require
their own analysis units; they are not one located incident per respondent.
No external records have been added by this batch.

## Native Analysis behavior

The existing Encounters topic now includes one grouped comparison picker for
33 report-field axes. The heatmap displays all 19 being categories, and up to
32 columns, including all 24 source-clock hours and unknown/unloaded bins.
Longer country or administrative-region axes retain complete tables and exports.
Each selected comparison has exact values, CSV and JSON with filters and
artifact hashes. A report is counted at most once per being/field combination.
Categories and source versions can overlap; totals are reports, not independently
deduplicated incidents or verified biological types.

The axes cover abduction classifications and co-descriptions; craft co-reports;
source, country, macroregion and administrative region; decade, month, weekday,
source hour/period and clock status; duration and status; witnesses and status;
role-preserving color categories; reported source height and uniform; reporting
delay and date role; report type, shape and craft confidence; mapping, precision,
coordinate evidence/source; duplicate-lineage status; and occurrence-date status.

Supported, unknown, not-loaded and excluded counts are shown separately.
Selecting an unloaded geography, clock, duration, delay, witness, color or
coordinate-evidence axis requests its existing guarded projection automatically;
an explicit load/retry control remains available. Users do not need to visit a
different Analysis topic first. The loaded projection refreshes the shared cohort.
Source clock values do not become UTC clocks. Midnight/noon sentinels, intervals
crossing hours, partial dates and lower-bound counts retain their uncertainty.
Height is positive finite source-supplied feet. Uniform wording remains the
source field, without invented garment interpretations. Height, color and uniform
are co-fields within a report, and may describe different objects or beings;
their attribution to a particular label is not established by a heatmap cell.

## Calendar and external context

A separate lazy disclosure compares all being labels or the overlapping abduction
classifications against:

- Moon phase, including stable/possible date bounds and represented-year/month
  calendar opportunity. Moon sky position retains the verified time/coordinate
  gate; unavailable inputs stay unavailable.
- All nine supported planetary bodies' signs and motion, plus all 36 unordered
  aspect pairs. One explicit load prepares the complete atlas using the existing
  saved ephemeris; choosing a body, pair or count/share view uses its cached
  matrices. Zodiac convention and orb changes reuse raw ephemeris and change
  the declared classification rule. Sidereal Lahiri remains the default. Houses
  require verified UTC/timezone, trustworthy coordinates and a house convention.
- Nuclear-test calendar windows and distance bins, plus reviewed nuclear and
  broader military/research institution markers. Original source-timezone,
  activity-interval, partial-inventory and site-uncertainty limits remain visible.
- Crop-circle and animal reports, separately, in same-date, ±7-day and ±30-day
  windows. Worldwide recorded-date alignment and ≤100 km public-marker distance
  are separate lanes. Crop discovery/catalog and animal report/publication dates
  are not promoted to formation or death times.

The external matrices show count or eligible-report share, with calendar ratios
only where the native astronomy engine supplies a represented-year/month
reference. Exact tables, selected-cell detail, uncertainty bounds, coverage and
complete evidence download accompany them. Known source-family/originating
publisher and own-report overlaps are withheld from context links. Co-located
same-day context markers are clustered. Unknown cross-source dependencies can
remain. Empty or disabled inventories produce unavailable cells, not zero
observations. These are descriptive catalog comparisons; no causal claim,
significance scan or Pattern Finder admission is added.

## Existing occurrence-date corrections

The existing source-pinned chronology index contains 3,624 occurrence-date holds.
369 overlap encounter records: 210 approximate, 95 publication and 64 erroneous
source dates, all from UFOCAT. These records keep source classification, badges,
original dates and source precision. The new temporal atlas and comparison input
adapter withhold their occurrence-date placement. This includes 75 source-classified
abduction records and one ambiguous record. If the chronology index is unavailable,
the flag stays null/not loaded rather than asserting the exclusion check passed.

Abduction classification remains 3,217 reports. The guarded lunar denominator is
1,882 and the located nuclear denominator is 1,671; exclusions and eligible counts
remain visible. These are different eligibility gates, not changed case totals.

## Validation and reproduction

Focused tests exercise the 33-axis contracts, exact coverage partitions,
multi-label counts, source/date guards, optional metadata transport, lazy controls,
complete exports, actual renderer callbacks, all context topics and populations,
keyboard navigation, cache identity and existing Analysis behavior.

The actual-corpus worker audit is
`docs/qa/encounter-atlas-20261013/corpus-runtime.json`. The independent calendar
and marker audit is `context-real-artifacts.json` in the same directory:
702,893 summaries, 16,319 exact encounter joins and all 552 independent
calendar/marker count and pair cells matched. It used the existing protected
summary shards, crop/animal context, chronology, nuclear/facility inventories and
ephemeris in place. Full encounter context took about 2.49 seconds in the audit;
the saved-ephemeris 1954-window nine-body/36-pair calculation took 0.047 seconds.
These measured calculations do not establish a universal browser/network timing.

`tests/test_encounter_delivery.mjs` verifies the actual local HTTP delivery,
final evidence pins and new assets. The corpus receipt pins the computation
before the final lazy-loading callback and explanatory captions; their changes
do not alter the serializer or estimator, and have separate routing/renderer
tests plus the final HTTP asset hashes. Browser inventory was rechecked and exposes
no connected surface, so interactive browser/visual acceptance remains pending.
DOM-renderer and HTTP checks are recorded separately.

`docs/qa/encounter-atlas-20261013/audit-context-real-artifacts.mjs --occurrence-guard`
reproduces the independent context audit using existing files and protects its
current output against overwrite. The prior receipt
`context-real-artifacts-before-occurrence-date-guard.json` is retained as a unique
quality intermediate; its purpose and retention are documented in the adjacent
`CONTEXT_REAL_ARTIFACT_REVIEW.md`. No complete dataset, static tree or database copy
is required for reproduction.

## Storage and release lifecycle

Current encounter data remains shared
`data/research/encounters-20261013/validated/reviewed/`, with the unchanged small
`data/encounters/` runtime counterpart. The new source-review document/register
and final atlas QA receipts are canonical outputs of this batch. The held
pre-date-guard receipt remains unique correction evidence; it is not a deployment
backup. Small live preview-server logs have their explicit local-session purpose
and are excluded from Git.

Last validated production remains deployment
`626b22b4-af0a-4252-8525-0ba21289c0d0`, with sole deployment rollback
`192e21f6-9c44-4b89-8d88-361e1c3d10d6`. The existing validated 184-file stage is
retained unchanged. Future packaging has only been checked, not generated or
published. No source corpus, coordinates, canonical event IDs or cloud artifacts
were modified. No new file exceeds 100 MiB, and attributable disk growth is approximately
1.2 MiB including local Git objects, below the constrained-C: approval threshold.
New small research/QA outputs have documented provenance and retention; none is
proposed for deletion. Previously superseded deployment-stage cleanup remains a
separate literal-allowlist proposal in `WORKSPACE_ANALYSIS_RELEASE_20261008.md`.

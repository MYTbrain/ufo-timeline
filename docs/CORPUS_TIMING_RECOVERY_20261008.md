# Corpus-wide chronology recovery

This release improves report-time ordering throughout the preserved
702,893-record corpus. Famous flaps are acceptance checks, not the processing
scope. Canonical reports, coordinates, dates, event IDs and the packed trace
inventory remain unchanged. The preceding legend radar and independent arrow
visibility feature are retained. It is published at https://ufo-timeline.pages.dev/
and on GitHub main. Publication and browser receipts are retained in
`releases/corpus-timing-20261008-v3/`.

## Evidence model

Each accepted report receives a UTC interval, rather than a guessed timestamp.
A link is ordered only if one report's latest possible time is strictly earlier
than the other's earliest possible time. Overlap stays unresolved and is
excluded from radar direction shares. These are report connections; neither
chronology nor their compass bearings establishes a physical flight path.

- Existing accepted clocks remain unless original source flags supply a stronger
  timebase or warn that the coded date cannot establish occurrence ordering.
- Clear own-occurrence text can add source-pinned local clocks. Source minute,
  whole-hour, explicit same-day range and literal AM/PM half-day precision are
  preserved. Publication times, other incidents, ambiguous dates, maritime or
  airborne time bases, approximate times, and natural-language day periods do
  not acquire invented precision.
- Split-zone jurisdictions retain a range of supported offsets. Post-1970
  multi-zone countries retain all IANA country candidates, rather than choosing
  the nearest city. Existing coordinate contradictions and low-precision
  geography gates remain in force.
- Unsupported historical continental US localities from 1918-03-31 retain
  UTC−08:00 through UTC−04:00. This includes the four continental standard
  zones and daylight advancement, without assigning a municipality's DST.
  Alaska and Hawaii are outside this envelope. References: the [1918 Standard
  Time Act](https://www.govinfo.gov/content/pkg/STATUTE-40/pdf/STATUTE-40-Pg451.pdf)
  and [US time-zone statutes](https://www.govinfo.gov/content/pkg/USCODE-1997-title15/html/USCODE-1997-title15-chap6-subchapIX.htm).
- Metropolitan France uses a conservative UTC+00:00 through UTC+02:00 range
  from 1911-03-12 through 1945, and the national UTC+01:00 rule for 1946–1969.
  Overseas territories are excluded. The [Paris Observatory's legal-time
  history](https://observatoiredeparis.psl.eu/l-heure-d-ete-fete-ses-40-ans.html)
  documents the retained 1945 hour and the resumption of summer changes in 1976.
  The [1911 statute transcription](https://lists.iana.org/hyperkitty/list/tz%40iana.org/message/QAB4HOEJP55OFOJQHTUBVW5AB4OOEQA6/)
  is preserved as a reference; the original linked BnF scan was not retrievable.
- UK home-territory historical clocks from 1916-10-02 through 1969 retain GMT
  through UTC+02:00. This bounds seasonal and double-summer regimes without
  choosing a particular transition. References: the [Time (Ireland) Act
  1916](https://www.legislation.gov.uk/ukpga/Geo5/6-7/45/pdfs/ukpga_19160045_en.pdf)
  and [Parliament's summer-time history](https://researchbriefings.files.parliament.uk/documents/SN03796/SN03796.pdf).
- A missing, sentinel, approximate or unsupported clock may supply only its
  entire reported civil date within a supported jurisdiction. This improves
  date-separated links without pretending a clock was recovered. Uncertain or
  partial dates, skipped civil dates and conflicting declared time frames stay
  withheld. Explicit source timezone tokens are never discarded to fit a
  preferred geographic zone.

The second source pass reads all 702,893 original detail records and all 320,412
rows of the protected UFOCAT CSV. The [CUFOS codebook](https://cufos.org/PDFs/UFOCAT%20Codebook%202023.pdf),
printed pages 18–19, defines explicit standard, daylight and GMT flags and warns
about publication, approximate and erroneous dates. A sparse ledger reopens
9,861 nonblank-flag records in 282 hashed source chunks. Only documented
TZONE codes supply fixed offsets; blank flags cannot assert standard or
daylight time. Existing numeric noon/midnight sentinel safeguards remain.

Date warnings and undocumented/combined flags exclude occurrence ordering,
including the otherwise available generic fallback for links separated by more
than two days. The inspector explains that source warning. Reports remain
available for inspection; original records and their coded dates are preserved.
The v2 audit exposed 1,441 accepted intervals on date-warning records and 174
intervals that conflicted with source-defined offsets. V3 corrects this evidence
rather than preserving an incorrect prior interval for continuity.

Source-specific geography parsing also separates UFOCAT regional suffixes from
country codes. Canada `CN` requires a recognized province; Central America `CA`,
Oceania `AU`, and Middle East `ME` require a recognized, allowlisted country.
This repairs 20,173 jurisdiction parses throughout the corpus, exposing 14,105
new guarded interval candidates before clock/date gates. Other sources retain
their existing country interpretation. Ambiguous native aliases, contradictory
raw source fields, coordinate contradictions and unsupported historical frames
stay held.

The inspector distinguishes whole-day bounds from occurrence clocks and shows
UTC ranges when needed. A narrative clock cannot be mislabeled with a withheld
structured midnight/noon value. Runtime diagnostics count each evidence kind
separately. The radar denominator still contains only ordered, noncoincident
links, before rendering aggregation or level-of-detail sampling.

Whole-day bounds also remain in the missing-clock adjacency lane when selecting
same-day craft neighbors. They cannot inject an invented noon into the chain.
Clock-backed interval midpoints are only a deterministic neighbor-selection
key; every link still needs disjoint full intervals to acquire an arrow.

## Audit and reproducibility

The source scan joins hashed effective summary shards, the existing typed clock
projection, and original detail chunks. Recovered clocks retain event identity,
source field, exact excerpt, extraction rule, local interval, chunk locator and
hash. The builder reopens those chunks and replays every accepted extraction.
No original detail chunk is copied or edited.

The before/after audit uses the actual packed app constructor and the actual
same-day craft constructor across all records and all ten flap windows. The
baseline code is frozen at Git `617d061`; comparison code is pinned separately.
Flap windows are global date windows, with no implied geographic restriction.
All-gap and default-gap counts are reported separately; viewport and facility
restrictions are absent. These selections are reproducible inventories, not a
claim to cover every possible user filter.

The 56 effective summary rows absent from the packed index all carry year-zero
placeholder dates. They are disclosed in the audit and are not treated as
valid missed trace endpoints.

## Final v3 results

All 702,893 reports pass through the corpus-wide pipeline. Accepted UTC timing
intervals increased from 213,364 to **425,214**: 347,946 clock-backed intervals
and 77,268 whole-day bounds. The latter do not represent recovered clocks.
The narrow narrative/field recovery produced 1,568 source-pinned local
intervals; 85 passed the UTC geography and historical-timebase gates. The
remaining local evidence remains available for review without gaining arrows.

The final source-field pass accepts 5,596 documented timebase clocks and
withholds occurrence ordering for 3,624 records: 2,669 approximate dates,
605 publication dates, 321 erroneous dates, and 29 undocumented or combined
flags requiring review. These exclusions also block wider-gap date fallback.
If timing evidence cannot load, ordering fails closed.

The transition receipt accounts for every prior interval: 213,125 retain
identical numeric bounds, 116 are corrected using original source timebase
flags, and 123 are withdrawn using original source warnings. Another 211,973
reports receive newly supported intervals. No unexplained prior changes remain.

For the actual packed trace inventory, ordered noncoincident links admitted to
the radar under the default gap of at most two days increase **92,727 → 193,433**
across all types, and **87,722 → 176,029** under Craft Only. Without a gap
restriction, the all-type radar count increases 94,393 → 195,040. Actual
same-day craft directions increase 77,005 → 93,807 across all types.
Neighbor inventories are rebuilt under each filter; Craft Only is therefore
not a simple subset of the all-type link inventory.

| Flap window | Default-gap ordered radar links, before → v3 |
| --- | ---: |
| Airship | 0 → 0 |
| Roswell era | 0 → 95 |
| Washington | 0 → 120 |
| France | 0 → 571 |
| Late-60s | 0 → 1,043 |
| 1973 | 265 → 607 |
| Belgium | 71 → 277 |
| Phoenix Lights | 6 → 25 |
| Phoenix era | 113 → 382 |
| Nimitz era | 474 → 1,134 |

Nine windows now have ordered default-gap links. The early airship window
still has none: three accepted source clocks do not yield a comparable
default-gap pair. Unsupported order remains unresolved.

Validation passed 30 Python tests and four JavaScript suites covering evidence,
source flags, direction populations, radar summaries and neighborhoods. The
whole-corpus runtime audit reconciles all decision categories and reports no
geometry failures. In the live preview, the Washington selection contains
116 ordered and 367 unresolved links, with arrows hidden. This differs from
the global audit's 120 because the preview retains its user filters and map
viewport. Final proof is `docs/qa/corpus-timing-20261008/washington-radar-v3.jpg`;
the earlier unversioned screenshots are intermediate diagnostics.

Receipts:

- `docs/qa/flap-chronology-20261008/baseline.json`: frozen pre-change baseline
  and final v3 whole-corpus comparison.
- `docs/qa/flap-chronology-20261008/v2-comparison.json`: unchanged intermediate
  comparison before the source-flag correction; retained as unique audit evidence.
- `docs/qa/corpus-timing-20261008/interval-transition.json`: every changed or
  withdrawn prior interval joined to original source flags.
- `docs/qa/corpus-timing-20261008/source-region-audit.json`: source-specific
  region/country interpretation counts and guarded examples.
- `docs/qa/corpus-timing-20261008/browser-checks.json`: intermediate and final
  preview checks, with final release and screenshot identified explicitly.

## Retention

The new canonical sparse evidence and source-recovery ledger live under shared
`data/research/trace-chronology-20261008/corpus-recovery/`; the current evidence
is its `evidence-v3/evidence.json.gz`, gzip SHA-256
`b720163bf83c96bc0bcf0997dbc268063b07c25e0c6fc48d821544040b14e3f8`.
Runtime uses the
hash-pinned counterpart in `data/trace_chronology/`; it is delivery data, not a
second canonical corpus. The previous scientific evidence remains unchanged at
`data/research/trace-chronology-20261008/evidence.json.gz` for provenance and
comparison.

The intermediate `corpus-recovery/evidence/` v2 artifact is retained as the
unique before-source-flag-correction analysis, not as a deployment rollback.
It can be rebuilt from the v2 provenance receipt and source recovery ledger;
the frozen v2 runtime comparison cannot be regenerated with the final v3 code
without reconstructing that intermediate implementation, so its original
receipt is preserved unchanged. `releases/corpus-timing-20261008-v2/` retains
only sparse recovery/provenance receipts; `releases/corpus-timing-20261008-v3/`
retains the current build and source-flag ledger/verification receipts. Neither
contains a full site release or a second corpus.

Verified runtime publication is deployment
`d7836d81-11e7-412b-98a0-4920ca0612a2`, from GitHub main `c549990`.
The previous production `192e21f6-9c44-4b89-8d88-361e1c3d10d6` is now the sole
known-good rollback, superseding the prior `0fb396aa` designation. Its frozen
delivery inventory is retained in `rollback_delivery_plan.json`.
The existing stage `.tmp/workspace-analysis-20261008-pages` was refreshed in
place to 184 files / 36,431,848 bytes; tree SHA-256 is
`09503b6c5e47b389884a831e0b434417587c07e05a0013c86eb1a9846b959dbc`.
No full corpus, static bundle or database copy is created. No file above
100 MiB is created. Existing superseded stages remain documented in
`WORKSPACE_ANALYSIS_RELEASE_20261008.md`; cleanup requires its literal allowlist
and separate authorization.

Bounded storage accounting records approximately 27,563,128 bytes (26.29 MiB)
of logical task-file growth, including the runtime evidence replacement delta,
and 10,596,499 bytes of new Git objects: **about 36.4 MiB total**. Later small
documentation changes are negligible at this scale. The shared recovery area
has 13 files totaling 18,466,263 bytes; none is over 100 MiB. The small shared
`git-storage-before.json` is retained solely as the pre-commit accounting
receipt. Browser state, unrelated activity and existing caches are outside
this bounded development estimate. No extra staging tree was created.

No cleanup of the new unique evidence is proposed. Existing superseded
generated stages remain the cleanup candidates already listed with literal
paths and retained counterparts in the release note; none was deleted here.

## Production verification

All 182 public Pages objects passed exact byte/hash and required cache-header
checks. The other two source entries are `_headers` and `.nojekyll`. Only the
previously declared exact 214-byte Cloudflare Analytics envelope is accepted
before HTML source hash comparison. All 184 staged objects match their Git
source bytes. The live browser loaded all 702,893 catalog rows, accepted the
425,214-report timing index with 3,624 exclusions, and reproduced Washington's
116 ordered / 367 unknown links with arrows hidden. No browser console errors
were observed. Production proof and browser checks are in the v3 release folder.

This deployment adds about 6 MiB, primarily 4,129,456 bytes of net stage growth
plus small inventory, publication, screenshot and Git receipts. No R2 upload,
corpus regeneration, new file above 100 MiB, or deletion was required. The sparse
v3 evidence remains canonical and previous source/evidence provenance is
protected. Receipt-only pushes trigger equivalent runtime deployments; the
final provider observation is saved locally in shared
`corpus-recovery/publication-final-observation.json` without a receipt-push loop.

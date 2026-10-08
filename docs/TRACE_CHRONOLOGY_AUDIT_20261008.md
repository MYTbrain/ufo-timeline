# Report-link timing audit and repair — October 8, 2026

Status: implemented and verified in the local preview; not deployed. All 702,893
preserved catalog records remain unchanged. This is a sparse timing-evidence
overlay joined to existing event IDs, not a rewritten corpus.

## Finding and resulting behavior

Famous-case connections were always marked as unknown order. Other trace routes
also omitted timing evidence, and the legacy clock parser missed compact HHMM,
seconds, and source-specific Local labels. Several country/state aliases were
ambiguous, Zimbabwe had no recognized timezone alias, and summary compaction did
not retain the evidence required for UTC comparisons.

The runtime now loads a precomputed, hash-pinned UTC-interval index once. It
orients report connections only when one report's latest possible time precedes
the other report's earliest possible time. The same resolver is used before
facility classification in static legacy and packed links, facility candidates
and the facility worker, progressive rendering, famous-case links, playback
trails, and optional startup previews. Area/crop neighborhoods reuse those
corrected report segments. Endpoint IDs, coordinates, labels, craft colors,
facility start/end roles, and directional statistics follow the resulting order.

Single-headed arrows show earlier-to-later report order. They do not establish a
craft's identity, travel, origin, or witnessed heading. Unknown-order links remain
double-headed and are excluded from the directional denominator. The inspector
shows original clocks, named zones, UTC bounds, and release provenance. Optional
straight-line speed bounds remain inside the timing-evidence disclosure and
explicitly assume the same craft without establishing that assumption.

The separate orange UFO-to-crop relation links use their existing preceding
catalog-date model. Same-day crop relations have no directional arrowhead.
Crop formation times cannot be inferred from a report/discovery date; this repair
does not replace that distinct relation model.

## Corpus coverage

| Measure | Records or links |
| --- | ---: |
| Preserved catalog records scanned | 702,893 |
| Structured source clocks classified exact | 511,394 |
| Exact structured clocks missed by the legacy chronology parser | 407,207 |
| Missed clocks with both mapped coordinates and exact calendar dates | 352,193 |
| Accepted UTC intervals in the overlay | 213,364 |
| Intervals from each record's own structured clock | 213,326 |
| Additional reviewed own-record narrative clocks | 38 |
| Stored mapped, exact-date craft-adjacency pairs audited | 361,266 |
| Audited pairs with provable UTC order | 60,358 |
| Audited pairs with overlapping UTC intervals | 19,547 |
| Audited pairs missing accepted endpoint timing | 281,361 |

The 407,207 count measures parser coverage, not 407,207 newly proven directions.
The 60,358 count refers to the existing stored adjacency inventory, not every
possible filtered case chain, zero-length link, or simultaneously visible arrow.

The broad source scan identified 3,985 strong description-clock leads. A bounded
queue contains 199 originally mapped leads plus Ariel's own narrative record.
Of those 200 candidates, 99 full descriptions were individually read, 38 clocks
were accepted, and 162 candidates were deferred. Deferred candidates include
unreviewed leads, incomplete dates, separate incidents in the same narrative,
airborne/offshore timebases, jurisdiction contradictions, and historical
municipal daylight-saving uncertainty. No unreviewed description clock was
automatically promoted. All 38 accepted records were subsequently reverified
against 36 original source chunks, including chunk hashes, detail indices,
event/source IDs, calendar dates, description hashes, and exact quoted excerpts.

## Washington and the Ariel vicinity

The screenshot's yellow connection joins the separate Harare rural oval report
and Carbonado, Washington State. It is not a direct connection from the Ariel
School disc report. Each report retains its identity and category.

| Own report | Source clock on September 16, 1994 | Historical local zone | UTC interval |
| --- | --- | --- | --- |
| Ariel School disc, ID 1548188833291382 | 1015 | Africa/Harare | September 16, 08:15:00–08:15:59.999 |
| Harare rural oval, ID 1880247488343365 | 1018 | Africa/Harare | September 16, 08:18:00–08:18:59.999 |
| Carbonado oval, ID 3972295816637808 | 10:00PM | America/Los_Angeles | September 17, 05:00:00–05:00:59.999 |

Carbonado's structured 10 PM clock agrees with the description's broader “after
9 PM” statement. The Harare–Carbonado arrow now points from Zimbabwe toward
Washington, with 20.68–20.72 hours between report-time intervals. At the default
Craft Only filter, this is one ordered Northwest link and one unknown-order
Ariel–Mexico link; the direction table correctly counts only the ordered link.

Mexico endpoint ID 3448855352240391 has the ambiguous 1200 default. Similar
Mexico narratives with 8 PM or 23:00 belong to other records and are not borrowed
without an identity/provenance review. The disc link remains unresolved.

## Evidence rules and remaining limits

- Exact source clocks retain their reported resolution as intervals. Clock
  precision is not a claim of physical measurement accuracy.
- Missing clocks, approximate/qualitative periods, and the 72,236 source
  midnight/noon sentinel defaults never become invented midnight observations.
  The audit found 19,737 sentinels that legacy metadata treated as exact or
  approximate; the new index withholds them.
- Historical IANA rules handle daylight saving. Thirty-five fold cases preserve
  both possible instants; five nonexistent local times are withheld.
- Geographic timezone selection is explicitly an inference. Single-zone
  countries and eligible uniform US states use structured jurisdiction evidence.
  Multi-zone countries, split US states, low precision, missing jurisdiction,
  and coordinate contradictions are withheld. No longitude-based timezone guess
  is used. State abbreviations are checked before conflicting ISO country aliases.
- Inferred zones before 1900 are withheld. Before 1970, inferred zones require
  the named IANA representative locality, or an independently supported explicit
  source offset. IANA describes the geographic/historical limits of its data in
  [its scope documentation](https://data.iana.org/time-zones/tzdb/theory.html#scope).
  This holds 13,944 unsupported historical-locality cases rather than assuming
  modern uniform daylight-saving rules.
- Without accepted clocks, different calendar dates prove order only when
  conservative full-day UTC bounds do not overlap. The fallback permits offsets
  through ±24 hours and requires dates more than two days apart. Adjacent-day
  missing-clock links remain unresolved.
- Famous-case chains use accepted UTC ordering within each source calendar date.
  Ordinary packed/global neighbor inventories and the playback cursor retain
  their existing presentation sequence; the repair correctly orients each pair.
  Rebuilding global within-day nearest-time adjacency requires a separate frozen
  ranking sidecar across packed, progressive, worker, and playback consumers.
  That is an outstanding enhancement, not completed by this repair.
- Description-only timing recovery is bounded to the accepted ledger. Thousands
  of additional narrative leads remain available for source-by-source review.

## Verification and reproducibility

The focused JavaScript suite covers UTC reversal, same-day overlaps, absent and
sentinel timing, strict schema/ID/hash validation, raw and browser-decoded gzip,
one-time loading and failure behavior, bounded calendar-date fallback, actual
app trace constructors, facility-worker classification, playback endpoint
geometry/colors, famous-case chains, and directional denominators. Eight Python
tests cover source parsing, historical timezone safeguards, and tampered source
chunks, descriptions, locators, and quotes. Existing polar constraints and the
map/chronology height behavior also passed their targeted checks.

Browser verification loaded all 213,364 intervals (6,827,648 bytes of typed index),
confirmed the actual Harare-to-Carbonado endpoint reversal, retained the unresolved
Mexico link, included both remote reports in Results, and inspected UTC bounds and
the one-ordered/one-unknown directional denominator. The retained browser receipt
and image are in `releases/trace-chronology-20261008/`.

`scripts/build_trace_chronology_evidence.py` reads the shared reviewed source-clock
projection/dictionary, effective summary shards, geographic reference bounds,
installed timezone database, and optional reviewed narrative ledger. The frozen
`evidence_build_audit.json` records exact rebuild arguments, all input hashes,
original source-chunk pins, and acceptance/holdout counts. Its command includes
`--reviewed-clock-evidence` so reproducing the artifact retains the 38 reviewed
clocks. `timing_coverage_audit.json` records the broader source scan;
`accepted_narrative_clocks.json` records review decisions and quotations.

Runtime gzip: 3,488,744 bytes, SHA-256
`121f17e63dff84125e4da413979102b0ef754a220177f70576e7acbb15401375`.
Decoded bytes: 10,773,026, SHA-256
`145148d5aaf01c92ecba71680603defe34f4759925ed154faadbe0f2e15075db`.
`data/trace_chronology/manifest.json` freezes these pins. Release preparation
copies only this small runtime sidecar and its manifest, plus the changed runtime
code; immutable R2 object plans and the corpus are not regenerated.

## Storage and release lifecycle

Canonical scientific artifact:
`C:/Users/jarod/Desktop/UFO Timeline map tool/data/research/trace-chronology-20261008/evidence.json.gz`
and its source-pinned audit/review files. Retain while referenced by the runtime;
rebuild from the audit's pinned shared inputs rather than making corpus backups.

The frontend's `data/trace_chronology/` is the small frozen deployable counterpart.
`releases/trace-chronology-20261008/` preserves the unique review/audit receipts and
browser evidence in Git; it is not a copied static bundle or source corpus.
Its purpose is to reproduce and review this repair, and it is retained with this
release's code. The bounded review queue is retained only in shared research.

Current validated production deployment remains
`a70bc14c-550c-4057-b461-bca4fd7aba27`; the retained known-good rollback remains
`c3bee7a9-56cf-4124-b17d-68f8b8533fa0`. No deployment, push, full corpus copy,
new staging tree, or rollback copy was performed for this investigation. The
existing `.tmp/workspace-analysis-20261008-pages` validated stage is untouched.

Approximate net growth is 14 MiB, including the shared sparse evidence, its small
runtime replica, receipts, code/tests, browser images, and the local Git snapshot.
No new file exceeds
100 MiB. No generated artifact from this repair is superseded. Previously
documented superseded stages `.tmp/interface-pages-candidate` (26,115,918 bytes)
and `.tmp/quality-20261007-pages` (28,176,967 bytes) remain candidates for an
explicit, separately authorized literal-path cleanup. Necessary data and the
current/rollback releases remain protected.

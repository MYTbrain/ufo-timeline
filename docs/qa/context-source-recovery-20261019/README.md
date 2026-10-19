# Crop/animal evidence recovery and Ted Phillips source integration

Date: 19 October 2026. Research and prepared product changes only. Production and the accepted public preview were not republished in this batch.

## Complete inventory audit and bounded source research

The full current 7,745-record crop inventory and 1,184-record animal inventory were recomputed through the existing context-evidence projection builder. The baseline, complete exclusion totals, overlapping exclusion combinations and a deterministic near-eligibility roster are retained in `D:/UFO-Timeline-Context-Evidence/candidate/eligibility-research-20261019/baseline-audit.json`. No UFO proximity, association strength or direction statistic was used to select research targets.

Previous research had already covered many sources and case queries. The new user request authorized a fresh bounded pass rather than automatic continuation of the parked lanes. Eight existing crop representations and six animal records were examined. Failed access and unresolved identity/count conflicts remain recorded, and known Rockville facts were not counted again as discoveries.

Two independent agents inspected identical frozen evidence and checked catalog identity, including direct visual comparisons of the Vimy and Chualar photographs and the Duran memorandum. Only their accepted intersection entered the append-only canonical ledgers through the established atomic writer. The accepted wave is `wave-026-context-source-recovery-20261019`, package `cep_1cb125ed9a7111ca76e693b9`.

The wave adds **21 assertions, 42 independent agent decisions, nine source cards and five terminal case snapshots**. Six source cards have retrieved bytes; three are explicitly inaccessible bibliographic/upstream leads, with no evidentiary or independence credit. Commissioned NVIDIA material shares a source family; Rommel transcriptions retain their parent lineage and secondary access tier.

| Existing representation(s) | Accepted additions | Limits preserved |
| --- | --- | --- |
| Vimy `cc_bd4c5cdf1f3c`, `cc_e7f5cdae7ab8` | Discovery on 5 July 2020, wheat, article publication on 6 July, with original agricultural reporting | Two representations of one formation, not two independent events. Discovery is not formation. No coordinates or duplicate merge manufactured. |
| Chualar `cc_debcda17244d` | Commissioned artwork classification, locality, and attributed NVIDIA/photographer account | Catalog wheat, NVIDIA barley, photographer rye remain conflicting descriptions. Exact creation date and event position remain unknown. |
| Duran `ami_03e69cd26a2bd82af80a4960` | Discovery date, one cattle victim, near-Duran locality, attributed age, memorandum date and approximate officer-arrival observation | Approximately 11 a.m. is the officer's arrival/observation, not proven first discovery or death. Memo date is not publication or incident date. No coordinate-method overwrite. |
| Taos `ami_c491e7a7a75f754af4ff81d7` | Discovery chronology, cattle/species/count, locality and attributed age from the report transcription | Original newspaper/veterinary files remain unrecovered; neither exact death date nor a carcass point is established. |

The five catalog representations describe four underlying case groups. Malaga count/species/identity conflicts, the Dulce aircraft-date issue, and the Texas news/aggregate identity issue remain held outside accepted case assertions. A contested source account was not used to overwrite a diagnosis, count or incident date.

The canonical data commit is `731aaaa` in the shared repository's context-evidence branch. The four ledgers retain their prior byte prefixes; the package can be reproduced against those prefixes without storing full copies. The application receipt, frozen inputs, separate reviews and mapping decisions are on D:. Existing unrelated shared-root modifications were left untouched.

## Effect on eligibility

| Measure | Before | After |
| --- | ---: | ---: |
| Crop source-reviewed representations | 134 | 137 |
| Animal source-reviewed representations | 11 | 13 |
| Strict crop location/date clusters | 1 | 1 |
| Strict animal location/date clusters | 0 | 0 |

This pass improves documented sourcing and date roles but produces **zero strict promotions**. Exact formation/death occurrence days, source-supported event points with quantified uncertainty, and unresolved identity/dedup requirements still prevent promotion. No threshold, uncertainty, coordinate, source independence or human-review status was invented. The initial 25-cluster and balanced 100-cluster policies remain intact.

`eligibility-impact.json` records the complete after-projection counts and five affected evidence rows. No full Analysis database, corpus, map bundle, or immutable public artifact was rebuilt. The accepted facts are now in the canonical review layer and are available to the established crop/animal/Analysis builders for the next authorized release. Existing public detail/readiness snapshots were not silently overwritten.

## Ted Phillips coverage and product fix

The authoritative UFOCAT source-code workbook distinguishes four exact codes: investigation files (`TPhillips`), the CUFOS 1975 *Physical Traces Associated with UFO Sightings* catalog (`TPhillips1`), *Trace Cases* (`TPhillips2`), and Missouri/newspaper reports (`TPhillips3`). Author names and publisher-name coincidences are not exact source matches.

All 320,412 UFOCAT rows and all 702,893 current canonical event representations were scanned without copying the corpus. Exact source codes identify **2,882 source representations attached to 1,953 current event IDs**, including 1,798 mapped events. There are intersections with 195 current encounter-evidence IDs and 13 collection-evidence IDs. These are coverage counts, not independent incidents, validated physical traces or causal relationships.

| Source work | Source representations | Distinct current event IDs |
| --- | ---: | ---: |
| Investigation files | 791 | 714 |
| 1975 CUFOS catalog | 1,039 | 833 |
| Trace Cases | 495 | 477 |
| Missouri/newspaper reports | 615 | 577 |

Rows overlap and must not be summed as independent events or source families. The 1975 catalog itself declares 831 reports: 561 with a UFO seen and a trace, 154 trace discoveries without a UFO sighting, and 116 with insufficient detail. The later TRACAT/CPTR collection is larger and has not been fully recovered; the 1975 edition is not a complete substitute.

The canonical exporter formerly emitted an empty References list even when raw UFOCAT source fields survived. New Python/browser helpers preserve existing references, decode the four Phillips works and retain other codes literally. Direct and indirect citations remain separate. Direct `TPhillips1/PAGEVOL` is a catalog case number; indirect `IPAGEVOL` may be a printed page or case number and remains explicitly unverified. No case number is turned into a fabricated PDF-page link. Invalid/out-of-edition locators remain flagged.

Primary raw-field decoding alone recovers citations for only 1,048 of the 1,953 records. The new small member-citation sidecar restores the additional **905 merged records**, using exact event ID, canonical event ID, canonical input membership, native ID and source-row hash checks. It contains factual citation metadata only, with no source narratives or coordinates. The CUFOS scan and OCR stay on D:.

The prepared runtime loads the 244,310-byte gzip and its 2,123-byte manifest only on full-record opening, sharing one integrity-checked request across concurrent openings. Initial startup does not fetch this data. Original details/references survive optional index failures. Cache tokens follow the current shell. Detail request generations prevent late results from replacing a newly selected record or leaving a busy state after selection clears.

The sidecar is registered in the release inventory for a future release, but the existing validated stage and production remain unchanged. This change improves citation visibility and preserves a source-linked index; it does not claim complete acquisition of later Phillips files or reclassify every Phillips-cited report as a crop circle, mutilation or physical-trace finding.

## Verification and retention

Eight Python source/export tests, the browser/Python citation parity and full-sidecar suite, actual app lazy-loading/integrity/cache/request-generation integration tests, the existing startup/loading-cover suite and ten release/search tests passed. The full 1,953-event/2,882-member sidecar passes structural, source-pin and compressed/decoded hash checks. Actual merged primary-source shapes and wrong/missing identity guards are tested. One test expectation was corrected when a real source member correctly retained an additional non-Phillips indirect citation; no data or guard was weakened. The package passed its combined schema/semantic dry run, atomic append and post-application projection check. No production/browser publication is claimed for these prepared runtime changes.

The canonical research receipt is `D:/UFO-Timeline-Context-Evidence/candidate/eligibility-research-20261019`, with purpose, provenance, hashes, bounded source attempts, independent reviews, frozen package, application and impact receipts. It is about **77 MiB on D:**, including the 45.8 MB CUFOS scan and 14.6 MB government-file scan. Canonical product additions are the small append-only ledgers plus the checked-in citation helper, manifest and compressed metadata derivative. The derivative rebuilds with `scripts/build_phillips_source_citations.py`; its source index stays on D:.

Approximate C: project growth is below 1 MiB; no newly created file exceeds 100 MiB. C: remains below the 100 GiB reserve. No full datasets, database, source archive, repository or staging tree were copied, and no protected data was deleted. No new release/backup tree was created. The prior current validated deployment (`16b1c76f-8896-4c00-ab00-4676212a941e`, source `94384c0`), sole designated rollback (`16443086-c630-41d8-a793-92a0243a76f6`, source `15ab160`) and accepted preview `5e423cb2` remain designated and protected. No superseded large generated artifacts need cleanup; retain the bounded D: research package and small checked-in receipts.

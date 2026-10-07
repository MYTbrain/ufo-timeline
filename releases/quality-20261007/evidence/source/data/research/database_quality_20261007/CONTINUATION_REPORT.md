# Continued database quality recovery — 7 October 2026

This second pass adds **349 supported map references** and corrects **7 uncertain dates previously labelled exact day**. It changes 351 distinct records. The combined local quality view now retains **702,893 source representations: 582,877 mapped and 120,016 unmapped**. None is deleted or automatically merged.

These results extend the first pass's 1,742 map recoveries. Together the two October 7 passes restore 2,091 map references. References can represent the same underlying account or incident; they are not independent sighting discoveries. Most points identify submitted towns, municipalities or coarse archival grid locations, rather than measured witness or craft positions.

| Research lane | Changed records | Additional map references | Date precision downgrades |
|---|---:|---:|---:|
| Independent original-account locality recovery | 148 | 148 | 0 |
| Original-account date-only correction | 1 | 0 | 1 |
| International publisher-declared locality recovery | 166 | 165 | 3 |
| Primary historical-grid and installation evidence | 26 | 26 | 2 |
| Coordinate notation and locality conflicts | 10 | 10 | 1 |

## Research that changed the result

The original-account lane examined the full 3,440-pair reverse queue, where an original report lacked a point but its UPDB republication had one. Native observation fields, source context and independent geographic authorities determined the accepted point. The copy's coordinate never selected or justified the original's reference. Repeated administrative text and registered abbreviations were resolved transparently; six city-sector references retain their directional text and approximate municipality scope.

The international lane read all 1,529 candidates and required a fixed local observer context as well as an unambiguous publisher-declared locality. The official [MUFON Journal, printed page 13](https://www.mufon.com/wp-content/uploads/2024/11/JULY_2023_MUFON_Journal_WEB.pdf) distinguishes the nearest event-city field, while the [NUFORC reporting form](https://nuforc.org/reportform/) separates sighting location and personal address. These semantics support a locality reference; historical-form changes and incorrect submissions remain limits. Full narratives, named-place disagreements, travel, remote media and forced form answers still block admission.

The historical-grid work revisited all 59 earlier holds using primary geographic, administrative and National Heritage List evidence. Twenty source grids now resolve to supported localities. Six additional Fort Huachuca ground-observer reports receive a rounded installation reference supported by the [National Park Service's original historic-district nomination, page 4](https://npgallery.nps.gov/NRHP/GetAsset/NHLS/74000443_text). The reference does not locate a particular building or an object's origin.

The coordinate lane reviewed 141 other remaining UFOCAT raw-coordinate records. Eight receive a supported source or locality reference, with two corresponding original publisher recoveries. Explicit codebook notation is interpreted conservatively. Malformed numbers and wrong-jurisdiction points do not receive a guessed decimal separator or automatic arithmetic adjustment.

For Ash Grove, the [original report 18233](https://nuforc.org/sighting/?id=18233) places the observer at a farm outside Ash Grove, Missouri, despite a Maryland form field. Its approximate date flag and conflicting seasonal/calendar anchors are preserved. Mishicot and Columbia Cross Roads also had administrative labels inconsistent with their source coordinates and independently verified counties. These label corrections improve the inspected record as well as its map reference.

## Uncertainty and abstentions remain visible

The date changes downgrade precision without inventing replacement dates. They include publisher-marked approximate days, an explicitly approximate MUFON narrative and a narrative month contradiction. Every stored sorting day, original occurrence field and narrative remains unchanged. These precision changes must be carried into any later rebuild of map, trace or analysis assets; this pass does not modify existing packed assets.

Context review prevented misleading point assignments. A Calgary submission describes a camp at Kananaskis Lakes; a Joppatown submission describes ISS live-feed footage. Other held examples include Rytro's unidentified kayak dock, Wallops postal/island/facility ambiguity, travel through several observation locations, distant homonyms and composites needing member-level review. The retained worklists document exclusions and geographic roles instead of forcing every record onto a map.

Publisher access limits are recorded. Some original pages could be inspected online; others were inaccessible and only their pinned retained source records were available. A failed retrieval is not evidence that a record is absent. Online fact receipts authenticate extracted facts and locators; retained downloaded documents have separate byte hashes.

The full residual census remains large:

| Source family | Remaining unmapped representations |
|---|---:|
| UPDB | 43,609 |
| Majestic | 30,981 |
| UFOCAT | 17,112 |
| NUFORC | 15,754 |
| MUFON | 12,560 |

Further research can target withheld named observer sites, ambiguous native place fields, composite member coordinates and original narratives with empty or country-only locations. These queues overlap; their sizes do not predict recoverable points. This bounded pass does not claim that every remaining report has been searched online.

## Verification and use

The current canonical quality artifact remains `quality_view_manifest.json`, with the unchanged reader, shared canonical base and pinned sparse decisions. It has **3,730 accepted decisions** across both retained quality batches. The new lanes have no overlap with each other or the first pass's changed records. Every summary guard in all 71 pinned shards and the complete 113,539-link account ledger passes the reader.

The continuation integration verified all **351 new changed detail records across 207 pinned shared chunks**. Exact summary/detail edits agree. Whole-row comparisons preserve raw fields, narratives, native IDs, dates, merge members and representation counts. All 7 precision downgrades pass. 24 unsafe-edit controls are rejected, and consumer-copy isolation passes. The unchanged first-pass and prior rollback full-source receipts are inherited through pinned baseline contracts, rather than re-expanding the entire corpus.

Read a corrected record with the existing `sparse_quality_view.py --event-id EVENT_ID` interface. Rebuild the current contract with `continuation_02/assemble_continuation.py`, then run `continuation_02/integration_validation.py`; the latter also refreshes the residual census. Each lane documents its retained source evidence and rebuild method. The original `assemble_quality_view.py` and first-pass report/receipts remain historical provenance and do not include this continuation.

**These corrections are local and validated; they are not yet displayed by the live website.** A release must derive map, trace, details and analysis consistently from the corrected view. No new deployment or runtime bundle was created here.

## Storage and retention

The current October 7 guarded view and its sparse evidence are the canonical local quality artifact. `database_quality_20261006/quality_view_manifest.json` remains the single local quality rollback. Production remains deployment `78cc3660-5750-4685-a095-fee6dce37fbf`, with `f88416b1-1e96-45fa-8b2a-a1edbfc5fdae` as its retained production rollback. The small first-pass baseline manifest in `continuation_02` is a provenance contract, not an additional corpus or release copy.

This continuation retains approximately **12.3 MiB** of new research, with **131.9 GiB free on C:** at completion. No new file exceeds 100 MiB, the planned 65 MiB growth bound is maintained, and shared source archives/canonical data/runtime bundles are read in place. There are no superseded large staging or backup artifacts. Retain the unique source evidence, accepted decisions, unresolved worklists and receipts; no protected-data deletion or incidental cleanup is proposed. `continuation_02/artifact_inventory.json` records exact file sizes, hashes and delta accounting.

Detailed reports: [original-account recovery](account_reverse_recovery/REPORT.md), [international locality recovery](international_source_recovery/REPORT.md), [extended online evidence](extended_online_recovery/README.md), and [coordinate notation/locality recovery](coordinate_notation_recovery/REPORT.md).

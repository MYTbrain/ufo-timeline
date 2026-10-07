# Unmapped recovery and source research — 7 October 2026

This pass recovered supported map references for **1,742 previously unmapped report records**. It also corrected **four date-precision labels** and enriched **one locality description** without assigning an unsupported point. The changes are integrated into the local guarded quality view, with original source records retained. The live map has not been updated by this research batch.

The combined view contains **702,893 source representations**, of which **582,528 are mapped and 120,365 remain unmapped**. The previous validated quality view had 122,107 unmapped records; this pass reduces that number by 1,742, approximately 1.4%. These are record counts, not counts of independent physical incidents.

| Recovery method | New map references | Supporting work |
|---|---:|---|
| Original-account recovery | 910 | Explicit native-account links, original occurrence fields, narrative and craft agreement, and independently checked locality references |
| Reported locality recovery | 795 | Original MUFON/NUFORC observation-location fields, exact locality authorities, jurisdiction checks and narrative-role screening |
| Online original documents and facility authorities | 13 | Original Air Force and UK Airprox documents, plus named ground-observer facility references |
| Archival British grid coordinates | 24 | UFOCAT source grid fields and codebook, nearby named locality and tested coordinate conversion |
| **Total** | **1,742** | Every accepted change retains before-value guards, source locators and hashes |

The 910 first-row recoveries concern UPDB republications of existing mapped originals. They improve archive coverage and inspection, rather than add 910 independent sightings. Four of the online recoveries concern a single Pan Am incident: all four records, conflicting details and provenance remain separate, with an explicit shared-incident relationship. No record was deleted or automatically merged.

## What online sources added

The [original Air Force Blue Book file](https://thedailydialectics.com/bluebook/scans/1950s/1952-05-9612806-ATLANTICOCEAN.pdf), scan pages 2 and 5, supplies the rounded observer-aircraft position for Pan Am Flight 203 on 8 May 1952. The four account representations receive an approximate source-reported observer reference. Their aircraft, altitude, route and time-zone disagreements remain visible in their source narratives.

Original UK Airprox Board assessments supply three encounter references, including [2017195, page 5](https://www.airproxboard.org.uk/Documents/Download/1715/676d6913-3528-4d32-8e66-50e2f5ec8c7b/1813) and [2019091/2019098, pages 3 and 5](https://www.airproxboard.org.uk/Documents/Download/1713/767ba307-2c1e-4031-b39d-ff0193e0fb9a/2315). These references replace missing coordinates with the documented encounter locality, rather than a departure or destination airport. An altitude discrepancy between a secondary narrative and the Airprox assessment is retained.

Municipal and government sources support six named ground-observer facility references at Heathrow, the Vatican Museums and Walla Walla airport. These remain city-level facility markers; they do not locate a historical tower, particular window or object exactly. The [original investigation of the Barra da Tijuca photographs](https://files.ncas.org/condon/text/case48.htm) supports the locality description but does not establish an adequate observer point, so that record remains unmapped.

Four official NUFORC pages explicitly mark approximate dates: [11277](https://nuforc.org/sighting/?id=11277), [11757](https://nuforc.org/sighting/?id=11757), [31901](https://nuforc.org/sighting/?id=31901) and [40718](https://nuforc.org/sighting/?id=40718). Their primary-record precision changes from exact day to approximate. The stored calendar day is preserved; the change is not silently propagated to copied accounts. Another 154 approximation scopes remain unresolved.

## The remaining database still has substantial research potential

The complete remaining census was regenerated from the combined view, rather than inferred from a single famous case.

| Source family | Remaining unmapped representations |
|---|---:|
| UPDB | 43,609 |
| Majestic | 30,981 |
| UFOCAT | 17,140 |
| NUFORC | 15,871 |
| MUFON | 12,764 |
| **Total** | **120,365** |

**81,104** remaining records carry a city-level label, **22,384** carry a country-level label, and **16,877** have unknown locality precision. Those inherited labels are research diagnostics, not proof that an unambiguous point can be assigned. Majestic alone has 13,812 remaining records with an empty location field, making narrative and original-source research particularly relevant.

The next useful queues are:

1. **3,440 original-account pairs with the original unmapped and its UPDB copy mapped.** Native report identities make these searchable, but the copy's coordinate must be independently verified; some copies use administrative markers.
2. **1,529 international records with exact locality matches but insufficient narrative corroboration.** Original report pages, attachments or archived source context can resolve wrong form-city selections and genuine locality references.
3. **59 unresolved British grid records and 141 other unmapped UFOCAT raw-coordinate records.** Historical administrative evidence, retained merge members and the codebook's other coordinate conventions are the relevant leads.
4. **Country-only and empty-location reports.** Named places in original narratives may recover missing observation context. Departure airports, destinations, publishers, photograph subjects and witness addresses require distinct interpretation.

These queues come from different bounded screens and can overlap. They must not be summed into a projected recovery count. The accepted batches likewise do not imply that every unmapped source page was searched online. Some publisher requests were inaccessible; unavailable pages are recorded as access limits, not evidence that the reports are absent.

Geographic ambiguity remains visible. This pass withheld 95 otherwise eligible original-account transfers because of distant locality homonyms, 11 specifically identified narrative/form-location conflicts, 59 British grid candidates and 13 individually researched online leads. The lane reports preserve the exact reasons and source locators for further work.

## Verification and use

`quality_view_manifest.json` designates the current local quality view. It pins the unchanged canonical base, prior accepted sidecars, new sidecars, reader and incident relationship file. All **71 summary shards**, every accepted summary guard and the complete **113,539-link original-account ledger** passed the combined constructor. It reports **3,379 accepted changes** in total, including **1,747 new unique changed records**, with no overlap between new and prior changed records.

The final integration pass verified **all 1,747 new changed detail records across 282 pinned chunks**, exact summary/detail agreement and preservation of identities, original raw fields, retained members and stored sort dates. **24 unsafe-edit controls were rejected**, and source-cache and decision-copy isolation passed. All four date-precision downgrades and all four Pan Am relationship members passed. The prior unchanged batch retains its existing full-source validation receipt. A separate read-only review found no material defect in the new reader or assembler. `quality_view_test_receipt.json` pins the final reader, manifest and validator.

Run `py data/research/database_quality_20261007/sparse_quality_view.py` for the effective census, or add `--event-id EVENT_ID` to inspect a corrected detail record and its evidence trail. This reads the shared source gzip files in place. `assemble_quality_view.py` rebuilds the manifest from the final accepted sidecars; `remaining_recovery_census.py` rebuilds the residual source/precision census. Lane reports give the source-research rebuild commands and limitations.

The reader supplies corrected summaries and details. Existing packed map, trace and analysis assets are outside this effective view; a future release must derive its displayed data coherently from the corrected rows. This batch creates no deployment and makes no claim that the live site already displays these changes.

## Storage and retention

The new canonical **quality artifact** is this batch's manifest, sidecars, reader and retained evidence, referencing the shared canonical dataset. The prior `database_quality_20261006/quality_view_manifest.json` remains the local quality rollback. The validated production deployment remains `78cc3660-5750-4685-a095-fee6dce37fbf`, with `f88416b1-1e96-45fa-8b2a-a1edbfc5fdae` retained as its last-known-good rollback. No additional release copy was created.

`artifact_inventory.json` records the final sizes and hashes, free-space measurement and approximate batch-attributable growth: **about 37 MiB**, with **about 132 GiB free on C:** at completion. No newly created file exceeds 100 MiB. Shared source archives, canonical datasets and runtime bundles were neither copied nor expanded to disk. The retained PDFs, rendered coordinate pages, authority facts and abstention ledgers preserve unique research provenance. There is no superseded large staging or backup tree, and no protected-data deletion or cleanup is proposed.

Detailed lane reports: [original-account recovery](account_recovery/REPORT.md), [locality recovery](gazetteer_recovery/REPORT.md), [online originals](online_sources/README.md), and [British grid recovery](grid_reference_recovery/REPORT.md).

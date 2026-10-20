# Context evidence continuation — 19 October 2026

Status: accepted canonical evidence and prepared product changes, **not deployed**. The MUFON date sidequest remains committed separately and intact. Shared data commit: `65d05ef3106bcb30bf7a0ac05d7656df255a64a6`.

## Accepted work

Wave `wave-027-context-source-continuation-20261019`, package `cep_43cea7767e7590922e335580`, adds **21 assertions, 42 independent agent decisions, nine source cards and eleven terminal research rows**. Eight cards have retrieved evidence; one is explicitly an inaccessible upstream newspaper bibliographic lead. Field additions affect six catalog representations of five underlying case groups. No new event is claimed. The bounded crop lane screened five representations/four case groups; the animal lane researched four cases. The Vimy duplicate review reused prior frozen images without new source searches.

- **Wilbur 2012:** contemporary AP reporting places farmer notification/discovery on 24 July. The imported 31 July is the publication day. The seven-day difference is preserved without calling discovery a witnessed formation date. A regional Highway 174 locator is added without inventing a field coordinate.
- **Sutton Hall 2016:** 29 August is explicitly a report date, and 31 August a blog publication date. Grid reference TQ888893 remains an attributed source claim; its cell precision is not treated as surveyed ground accuracy.
- **Chillicothe 2012:** a retained ICCRA HTML capture previously labeled non-extractable contains the investigator account. Accepted metadata distinguishes 20 September report receipt, 28 September ground photography and 30 September investigation, plus an attributed 43-circle count. The investigation day is a narrowly reviewed associated claim because the existing contract reserves the typed investigation_date field for animals. The second Chillicothe representation remains only a possible duplicate; no unsupported merge was made.
- **Middle Creek Road/La Veta 1994:** recovered the contemporary Signature article of 3 November, reproduced on printed/PDF page 18 in the March 1995 clipping issue. Three cattle is explicitly an article-scoped claim; it is not a cumulative episode total. The source says discovery was last week and supplies only approximate locality. A veterinarian offered alternatives but explicitly had not examined these carcasses. No cause-of-death, exact death day or absolute event point was inferred.
- **Vimy 2020:** two catalog representations use the same aerial photograph; the farmer article shows matching distinctive geometry and tramlines from another angle. Two independent agents accepted one duplicate relationship and a common cluster. The bounded provisional Connector representation remains the representative; its inherited 25 m claim is not validated. The locality-centroid representation remains inspectable but is excluded from independent-event analysis. No row or source was deleted.

Ickleton, Ioka Lane, Hooper and Costilla County exact-source routes closed honestly without material gains. No unrelated report was joined by place/date coincidence. Three animal extraction/classification concerns are retained as future review leads, not automatic deletions.

## Product date-role fix and measured impact

Both shared crop/Analysis builders formerly ignored accepted crop report_date fields, allowing a lower-priority publication/photo date to displace a documented report day. Both now consistently prefer formation→occurrence→discovery→report→photography→catalog→publication. Unsupported crop investigation_date fields are not selected or used for bootstrap. Animal date selection and strict evidence definitions are unchanged.

The canonical writer proved byte-prefix preservation and applied only the accepted ledger delta. Initial dry-run rejection of the unsupported crop investigation field was retained; the sole correction mapped it to the exact attributed claim and received both original independent reviewers' explicit acknowledgments. The final combined dry run passed before atomic application. No contract/gate was relaxed.

| Measure | Before | After |
| --- | ---: | ---: |
| Crop inventory representations | 7,745 | 7,745 |
| Animal inventory representations | 1,184 | 1,184 |
| Source-reviewed crop representations | 137 | 140 |
| Source-reviewed animal representations | 13 | 14 |
| Crop bounded descriptive tier | 427 | 428 |
| Crop locality descriptive tier | 3,225 | 3,224 |
| Crop excluded representations | 4,092 | 4,092 |
| Strict crop clusters | 1 | 1 |
| Strict animal clusters | 0 | 0 |

Chillicothe moves from excluded to bounded descriptive with its literal report date. Vimy's duplicate moves from locality to excluded, so total descriptive rows do not simply increase by one. FormationDateKnown remains false for these crop cases. Exact formation/death occurrence and supported site/uncertainty requirements continue to block strict promotion. before-projection.json and after-projection.json on D: retain target rows, full counts and projection metadata. The full public map bundle/Analysis database was not rebuilt; the next authorized release must regenerate the affected context artifacts from these authoritative ledgers and builders.

## Ted Phillips continuation

Recovered the author-attributed 2004 nine-page interim report, *Physical Traces Associated with Unidentified Flying Objects: Results of Processing Data 1490–2004*, from the Informe OVNI mirror: https://www.informeovni.net/documentos/Phillips_2004_Physical_Traces_Associated_With_UFOS_An_Interim_Report.pdf . SHA256: `350bbf229278c3cfba136a6761555116da2ca7e1b1230cd6865b4bfeea3caa65`. It declares 3,059 reports/91 countries but is aggregate analysis, not the underlying row-level catalog. These are not ingested as new datapoints. The later complete TRACAT/CPTR archive remains unrecovered. The original CPTR selected-case page was readable once, but failed capture reopens remain explicit errors rather than invented source contents.

Three existing-case direct TPhillips1 locators received independent visual checks from the retained 1975 book and exact source-member/event joins: Roaring River #253→printed 44/PDF 62; Houston #537→86/104; Columbia #585→90/108. Python/browser helpers now offer those exact fixed-page links, with the original PDF hash pinned. Indirect page-or-case locators and other Phillips works remain unresolved. Exact legacy helper references upgrade without duplication, while arbitrary/source-unowned references remain intact. Houston/Columbia date/time conflicts remain unresolved; no chronology, coordinates or event counts changed. Citation payload bytes and initial dataset loading remain unchanged.

## Verification and retention

Thirty focused shared-builder tests passed, including actual candidate date roles, bootstrap and strict nonpromotion controls. Seven focused Python citation tests and three JavaScript citation/ownership/lazy-loading suites passed in the parent, with browser/Python parity, indirect guards, existing-reference upgrades and immutable payload checks. No public/browser deployment verification is claimed.

The canonical unique research/provenance package is `D:/UFO-Timeline-Context-Evidence/candidate/eligibility-recovery-continuation-20261019`, including frozen sources, independent reviews, package builder/manifest, canonical application and before/after receipts. The earlier 45.8 MB book and other source captures are referenced by hash, never copied. New capture/projection/review storage is about 24 MiB on D:; C: project growth remains below 1 MiB. No new file exceeds 100 MiB. No full corpus, database, repository, bundle, stage or backup tree was copied. Retain the unique bounded source package and these compact receipts; no superseded large artifact needs cleanup and no deletion is authorized.

Current validated deployment remains `16b1c76f-8896-4c00-ab00-4676212a941e` (94384c0); sole rollback remains `16443086-c630-41d8-a793-92a0243a76f6` (15ab160); accepted preview remains `5e423cb2`. No deployment, public artifact overwrite, or main-branch push occurred.

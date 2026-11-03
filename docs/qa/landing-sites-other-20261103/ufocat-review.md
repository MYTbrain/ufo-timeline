# UFOCAT landing-site source screening

## Initial screening

All 412 UFOCAT inventory IDs were reconciled by PRN to the pinned source CSV and its original row number. The source rows contained 261 narratives and 151 blanks. Direct and indirect source codes were checked against the Sources workbook distributed with UFOCAT 2023. The ledger carries the exact record and citation locators. The 92 catalog descriptions are screening dispositions based on the UFOCAT notes. Geometry tagged description records reported physical details and does not certify a layout or its origin.

| Source disposition | Records |
| --- | ---: |
| Original report, investigation or reassessment reviewed | 5 |
| UFOCAT catalog description reviewed | 92 |
| Citation lead | 302 |
| Source code or usable ground layout unresolved | 13 |

The 412 records resolve to 3 diagram-linked rows, 94 descriptions and 315 with insufficient geometry. Original-source checks cover Gatchellville, Trans-en-Provence, Rendlesham, Tucson and Douvrin. Two independent records were added as dossiers. Tucson plots approximate APRO dimensions and discloses the conflicting Blue Book diameter estimate alongside the Army tests. Douvrin's GEIPAN reassessment describes strips and a circular feature without enough measurements to place them on a plan.

Same-event overlap was checked against trace details and source context. The two Cook, Minnesota records repeat a distinctive narrative verbatim with different citation chains. They remain separate catalog records with reciprocal notes. The Hatch Tucson and Gatchellville rows and three Trans-en-Provence export rows match the corresponding sites through their source descriptions. The Eberhart Rendlesham record explicitly describes the first patrol and next-day impressions. A late-evening Hatch Rendlesham report does not establish that same episode. Numeric matches between UFOCAT Hatch references and exported Hatch ID suffixes did not hold on date and locality.

## Storage and reproducibility

- Canonical inputs remain shared and in place. UFOCAT CSV SHA-256 `04b71519710b48c86492f8a73686405621983269795ee65c5e7d3f4a6248f017`. UFOCAT 2023 Excel format ZIP SHA-256 `724f02b79736265bede0bbe77043b270a17bfa7a770a85e85c6042c2b0a392ae`.
- The canonical review artifacts are `ufocat.json` (156,348 bytes) and the root `landing_site_ufocat_reviewed_cases.js` (7,407 bytes). The ledger SHA-256 is `f8eb56deadc4c2288075eb6dbccb1d3ea049dfef76ce0dbe2ac6a9028a2d4c8c`.
- Retained review scratch is `D:/UFO-Timeline-Context-Evidence/candidate/landing-other-ufocat-20261103`, 939,137 bytes in four files. The extracted rows can be reproduced by filtering the pinned CSV to the PRNs in the non-Phillips inventory and retaining source row numbers. The source-code lookup can be reproduced by reading the Sources XLSX from the pinned ZIP in memory. The working review script rebuilds the ledger from these two extracts. The scratch narratives were used for screening and were excluded from the public review artifacts.
- Retain the D: working extracts and script as a reproducibility receipt for the current review. No complete corpus was copied. No new file exceeds 100 MiB and no separate backup or deployment was created for this audit. Total C: growth from the two review artifacts and this receipt is under 170 KiB.

## Follow-up source retrieval

This pass updated 44 ledger rows, including 41 exact source, citation or dossier updates and three narrowed Blue Book retrieval leads. The updated 412-row ledger is the canonical review artifact.

| Source disposition | Records |
| --- | ---: |
| Original report, investigation or reassessment reviewed | 33 |
| Catalog, index or derivative report reviewed | 98 |
| Citation lead | 269 |
| Unresolved | 12 |

Six UFOCAT rows now link to diagrams, 104 contain trace descriptions, and 302 have insufficient geometry for comparison. Original-source status describes the document reviewed. The NUFORC accounts include uncorroborated retrospective statements and the examined Blue Book cases include ordinary materials.

- **NUFORC.** Checked all 32 direct UFOReportCtr rows and two explicit indirect NUFORC references against the retained original narrative export. Matched 26 on distinctive wording, place or original reporting metadata. Six older short-number references and two indirect references did not match exactly. Matched three direct-inventory peers, of which Elk Grove and Plain now share dossiers across both source records. The Lynn submission has contradictory years and remains a description. [NUFORC databank](https://nuforc.org/databank/)
- **Project Blue Book.** Checked all nine direct Blue Book references. Tucson was already reviewed. Recovered and visually read the exact Napavine and Stevens Point cards, which report glass and radar chaff respectively. The exact Islamorada, Cypress Gardens and LTV Aerospace index entries concern specimens and lack site geometry. Los Angeles, Mandan and the entry with locality A remain unresolved to an original report. [Napavine card](https://catalog.archives.gov/id/28958326), [Stevens Point card](https://catalog.archives.gov/id/302569447), [contemporary Blue Book listings](https://documents.theblackvault.com/bluebookdesk/pbbcases-1966-1969.pdf)
- **APRO.** Checked nine direct or indirect APRO Bulletin references. Recovered exact articles for Bethel, Clyde and Tyneham, and inspected the pages supporting both diagrams. Clyde models the sole reported span of the flattened wheat patch. Tyneham shows the two reported radii without inventing hole bearings. Both APRO date versions are recorded. BUFORA assessed the case as a probable hoax. Six other APRO issue references remain retrieval leads after issue and mirror checks. [Bethel](https://www.openminds.tv/pdf/apro/apro_jul_1967.pdf#page=7), [Clyde](https://www.openminds.tv/pdf/apro/apro_jan_1968.pdf#page=3), [Tyneham](https://www.openminds.tv/pdf/apro/apro_nov_1969.pdf#page=7), [BUFORA assessment](https://www.bufora.org.uk/_files/ugd/4719c2_9072a71750cb4fd0a85600435a361def.pdf)
- **IUR, GEIPAN and NICAP.** Recovered IUR entries for Edmonton, Kola, Ste-Marie-de-Monnoir, Concord and Trout Lake. The cited Concord source expressly records that no ground marks were found. The reviewed GEIPAN material for Les Tuiles places the physical effects on a roof. The light reported in a field provides no measured ground trace. Reconciled Dale to the reproduced field sketch and linked it to the existing dossier. [IUR July–August 1990](https://cufos.org/PDFs/IUR%20issues/IUR%20Vol.%2015%20No.%204%20July-Aug.%201990.pdf#page=12), [Concord](https://cufos.org/PDFs/IUR%20issues/IUR%20Vol.%2027%20No.%202%20Summer%202002.pdf#page=23), [Trout Lake](https://cufos.org/PDFs/IUR%20issues/IUR%20Vol.%2022%20No.%202%20Summer%201997.pdf#page=32), [Les Tuiles](https://www.geipan.fr/fr/cas/1989-09-01666), [Dale sketch](https://www.iccra.org/reports/ICCRA%20pdf%20reports/Dale%2C%20IN%201964%20for%202010%20ICCRA%20Conference_v%20website.pdf#page=14)

### Follow-up storage receipt

- Updated ledger SHA-256 (LF repository bytes) `b03eb8271151362b741bb973fb61b3fa38688d480196e768bf359d14a48d6161`. The runtime dossier module SHA-256 is `399e623d8021c6c3f4bdedfd7823058c7942c0115629289f3c0523ca730ff43f`.
- The existing D: working folder now holds 25 files totaling 48,994,809 bytes, a net increase of 48,055,672 bytes for this pass. It holds five cited PDF scans, two NARA frame images, small rendered or text derivatives, and reproducibility scripts and matches. The original narrative export remains shared in place. No newly created file exceeds 100 MiB.
- Retain the cited scans and exact NARA frames with the review receipt. The three rendered pages and text extractions are reproducible from the scans with Poppler and FFmpeg. The match output can be regenerated with `find-nuforc.py`. They are eligible for a later literal-path cleanup if disk space is needed. This lane made no deployment or rollback artifact.

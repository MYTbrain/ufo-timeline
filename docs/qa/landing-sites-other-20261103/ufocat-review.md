# UFOCAT landing-site source screening

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

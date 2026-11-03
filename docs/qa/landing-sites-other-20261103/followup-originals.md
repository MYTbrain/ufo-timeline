# Landing Sites original-source follow-up

This pass starts from production `bcc2d1b8`. It searches upstream archives for selected catalog and citation entries, follows exact same-case links, and updates the source decisions and trace records in the local preview. The published release receipt remains the frozen record of production.

## Coverage and comparison

| Additional inventory | Original reporting | Catalog reviewed | Citation only | Unresolved |
| --- | ---: | ---: | ---: | ---: |
| Direct | 57 | 0 | 0 | 0 |
| Historical compilations | 39 | 880 | 0 | 0 |
| UFOCAT | 33 | 98 | 269 | 12 |
| Australia | 14 | 137 | 2 | 0 |
| Total | 143 | 1,115 | 271 | 12 |

The original-checked count increased by 63. Of the 1,541 additional records, 97 now link to 71 dossiers and 60 link to diagrams. Another 246 have descriptive geometry and 1,235 have insufficient geometry. Possible same-day overlap remains separate from checked case identity.

The combined view increased from 71 to 93 dossiers and from 54 to 71 diagrams, with 167 trace records. It includes 25 three-mark and 10 four-mark ground-impression layouts, 10 circular scorch layouts, and 19 swirl or twist cases. The reported swirl directions are 10 counterclockwise, 5 clockwise, and 4 uncertain or unreported. Three cases report scorch and swirl, and one has a diagram relating the two trace types. Counts describe the reviewed case set. They do not measure incidence or imply a shared mechanism.

## Source decisions

- **Phillips:** Field accounts and plans add La Madera, Hubbard, Dale, Presque Isle and Hampton Falls. The 1975 catalog pages for Socorro #167 and Donnybrook #820 were recovered by reading the original scan. Both rows now link to their existing dossiers. The first page screen misread Donnybrook's case number as #620. The 17 targeted Phillips reviews are recorded separately from the 1,541 additional records. Fifteen checks reach original reporting. The Ngātea and Tyneham Phillips entries link to the same dossiers as their other catalog records. The Harrisburg #281 and Springfield #685 entries retain compiler-level geometry. The Dell scan located for Harrisburg was issue 3. The source cited for that case is issue 4.
- **Historical compilations:** The Hatch and specialist receipts follow matched first-hand field reports and exact known aliases. They add the Ngātea mānuka patch, Øydeskyvatn snow impressions, Baldwin and São José do Campestre. South Hill gains a diagram from original APRO measurements with the assumed diagonal midpoint made explicit. The burn lacks measured registration to those marks.
- **UFOCAT:** Matching witness narrative, event date, place and submission information recovered underlying NUFORC reports. The receipt distinguishes original witness text, original agency material, catalog narratives and open citations. Several source checks exposed tags that described aircraft, lights, roof damage or ordinary material instead of landing marks. [UFOCAT source and storage receipt](ufocat-review.md)
- **Australia:** Contemporary field accounts and trace plans were checked in AFSR, Australian UFO Bulletin, press reproductions and other sources. Auchettl's Churchill Park plan supports separate layers for the four pad-like impressions, scoop marks and discoloration. A kite with two pairs of reported equal sides has nominal reflection symmetry. The source does not establish how the marks formed.

Several source records can resolve to one site. The comparison counts a dossier once per trace and layout cell. A nominal shape or radius guide appears with its basis and scope. A source can support a diagram for one trace while giving only descriptive detail for another. Ground impressions, scorching, vegetation twist and other vegetation changes remain separate in the combined comparison.

## Key geometry checks

- Dale's Powers sketch shows three shallow indentations and a small irregular burn in the same frame. A later grass-swirl account has no measured registration to that drawing. [Powers sketch](https://www.iccra.org/reports/ICCRA%20pdf%20reports/Dale%2C%20IN%201964%20for%202010%20ICCRA%20Conference_v%20website.pdf#page=14)
- Presque Isle's engineering reviewers found that the photograph contradicted the orientation in the field sketch. The diagram preserves the reported 16-foot spacing between the larger depressions. [Air Force engineering review](https://documents2.theblackvault.com/documents/projectbluebook/PresqueIslandStatePark-Pennsylvania-07-31-1966-main.pdf#page=77)
- At Hubbard, the deputy's approximate three-foot spacing concerns localized crushed wheat. The nominal triangle is a vegetation diagram. [NICAP report](https://cufos.org/PDFs/UFOI_and_Selected_Documents/UFOI/023%20JUL-AUG%201964.pdf#page=6)

The follow-up is targeted. Unrecovered original material remains distinguishable from a compilation or citation. Matching observations across catalogs does not establish a common physical cause.

## Reproduction

The canonical local derivatives are the reviewed case modules, the four additional-inventory ledgers, the partial Phillips original-source ledger and their generated audit. Run `python scripts/build_landing_site_review_audit.py` to reconcile the inventories and pin the receipts. The retained 1975 scan, full and number-column OCR caches and pinned source index reproduce the Phillips inventory. Pass those paths to `scripts/build_phillips_landing_inventory.py` with `--ocr-cache`, `--left-cache` and `--ufocat-index` respectively.

## Storage and retention

The [follow-up is live](https://ufo-timeline.pages.dev/#analysis-section-landing-sites) as `277fbeff`. The retained rollback is `bcc2d1b8`. The [release receipt](followup-production-release.json) pins the stage and verification. The stage materializes 11 changed files and hard-links 240 verified files from the rollback stage. Deployment adds about 1.1 MiB on D: and under 1 MiB on C:. The earlier `f975c83d` rollback designation is superseded.

Research growth was approximately 0.11 MiB in the worktree and 220 MiB on D: across the Phillips, UFOCAT and historical source-review folders. No newly created file exceeds 100 MiB.

- `D:/UFO-Timeline-Research/landing-sites-originals-followup-20261103` contains the recovered PDFs, a source hash manifest, and reproducible text and image working files. The Dell issue 3 scan and its derivatives are superseded search scratch. The relevant source PDFs remain retained.
- `D:/UFO-Timeline-Context-Evidence/candidate/landing-other-ufocat-20261103` retains the pinned UFOCAT source review and reproducibility aids.
- `D:/UFO-Timeline-Research/landing-sites-combined-20261103/historical-source-review` retains the Baldwin original scan. Its reading render is reproducible.
- Reproducible renders, OCR extracts and the superseded Dell acquisition can be considered for cleanup under a literal allowlist. Australian archive renders used as temporary working files are reproducible from the dossier source links.

The Landing Sites and neighboring Analysis checks passed 18 JavaScript tests. The release preparation suite passed six tests and 11 subtests. Desktop and mobile Chromium checked the source filters, exact dossier links and independent trace-layer controls.

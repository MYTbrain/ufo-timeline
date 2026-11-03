# Source review of the additional landing reports

The review covers the 1,541 records in the two additional Landing Sites inventories. Four ledgers preserve the native inventory IDs and the source and geometry decisions for each record. The Australian ledger records the Basterfield catalog review. The historical ledger covers Hatch and the other historical compilations. The UFOCAT ledger uses the native citation records and source-code index. The direct ledger covers NUFORC, GEIPAN and Project Blue Book.

## Review results

| Ledger | Records | Original reporting | Compiled account | Citation only | Unresolved |
| --- | ---: | ---: | ---: | ---: | ---: |
| Direct | 57 | 57 | 0 | 0 | 0 |
| Historical compilations | 919 | 12 | 907 | 0 | 0 |
| Australian catalog | 153 | 6 | 144 | 3 | 0 |
| UFOCAT | 412 | 5 | 92 | 302 | 13 |
| Total | 1,541 | 80 | 1,143 | 305 | 13 |

The audit links 70 records to 51 dossiers, including 12 dossiers with multiple linked records. It lists 267 records with possible same-day locality matches. There are 27 diagram-linked records, 241 records with descriptive details and 1,273 with insufficient geometry. The descriptive category can include narrative details without a coded layout.

The expanded comparison has 71 dossiers, 128 trace entries and 54 diagrams. This pass adds 28 dossiers and 18 diagrams. Original-source checking also strengthened the existing Stirum diagram. The NARA file is indexed under Gwinner. The North Dakota Air National Guard recorded the same isosceles spacing as Phillips and reported no heat effects in the stubble. The Air Force technical review considered the arrangement compatible with tripod landing gear, with no soil-strength data for a force estimate. [NARA case file, roll 65, frames 0923 and 0925](https://catalog.archives.gov/id/302555731)

### Recurrence in the combined case set

| Trace | Reviewed cases with this trace | Selected recurring layouts |
| --- | ---: | --- |
| Ground impressions | 48 | 20 three-mark layouts, 9 four-mark layouts, 6 rings or circular areas |
| Scorching | 19 | 6 rings or circular areas |
| Vegetation swirl or twist | 14 | 7 ring or circular layouts. Handedness was 7 counterclockwise, 4 clockwise and 3 uncertain or unreported. |

Fifteen dossiers record impressions and scorching, and six have a plan with both layers. Six dossiers record impressions and vegetation twist, and two have a plan with both layers. These are counts within the reviewed case set. A reported shape can recur without measured equality of its sides, angular spacing or agreement across trace types.

## Reading the results

- **Original reporting checked** indicates a witness submission, a contemporaneous investigation or an identified first-hand report, including an identifiable reproduction of that report.
- **Catalog account checked** indicates a compiler’s account that can be read and evaluated. Some accounts describe enough geometry for a labelled schematic.
- **Citation only** indicates a usable citation without a recovered account for that source entry.
- **Unresolved source** indicates that the review could not establish a usable upstream source.
- **Diagram** requires a source-supported arrangement, measured bounds or a visible plan. Reported dimensions and measured point positions are distinct. Diagram layers carry their own scope notes.
- **Descriptive geometry** retains trace wording and any reported counts or measurements. For example, the Donnybrook field report records two triangular groups of depressions and a pooled range of spacings. The missing individual positions prevent a plan reconstruction.
- **Insufficient detail** includes miscoded or negated trace tags, records with no usable trace geometry and accounts whose detail could not be recovered.

An exact dossier link records a reviewed source identity. The automated overlap screen lists candidate records that share an exact calendar date and normalized locality token, including Phillips records where available. This screen can produce false matches between places with the same name and miss reports with inconsistent dates or place names. The application counts each reviewed dossier once per trace and layout cell. Catalog records, citation variants and candidate matches are excluded from those counts. An original-reporting filter scopes the comparison to dossiers whose provenance was explicitly coded in this audit.

The combined table keeps possible support impressions, scorching, swirl or twist, other vegetation deformation and other surface traces in separate columns. A site can contribute to more than one layout row. Three or four reported marks by themselves do not establish equal angular spacing. A directional swirl describes vegetation lay and does not establish a shared cause across cases.

## Rebuild and review

Run `python scripts/build_landing_site_review_audit.py` from the release worktree. The script requires an exact one-to-one reconciliation between inventory records and review dispositions and records input SHA-256 hashes in the generated asset. The checked-in format keeps the four ledgers inspectable and the site dossiers maintainable separately.

The local preview serves the current worktree assets over the retained mapping stage without copying the catalog or static bundle. Production remains `f975c83d` with `90fa1b95` retained as rollback.

## Storage and retention

The four ledgers and reviewed case modules are the canonical local research derivatives. The generated audit JavaScript is reproducible from the ledgers and pinned catalog assets. Worktree growth for this pass is about 1.1 MiB. Original documents and working aids on D: add approximately 173 MiB across the direct, historical and UFOCAT source-review folders. This pass created no file larger than 100 MiB and no full bundle or catalog copy. The source folders have separate receipts documenting acquisition, derivation and retention.

- `D:/UFO-Timeline-Research/landing-sites-other-review-20261103` retains the GEIPAN reports, Air Force scans and reproducible renders and text extracts.
- `D:/UFO-Timeline-Research/landing-sites-combined-20261103/historical-source-review` retains historical acquisitions and a source manifest. Retain the underlying evidence and consider the derived renders for cleanup.
- `D:/UFO-Timeline-Context-Evidence/candidate/landing-other-ufocat-20261103` holds the small UFOCAT working files and source receipt. The Australian dossier sources carry the published plan and photo locators.

The retained production stage and rollback are reused. There are no superseded release or staging trees from this pass. The cleanup candidates are reproducible review renders and contact sheets, with the underlying sources retained.

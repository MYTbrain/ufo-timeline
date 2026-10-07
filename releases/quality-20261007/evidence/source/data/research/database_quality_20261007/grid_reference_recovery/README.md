# British source-grid recovery artifacts

Purpose: restore supported coarse archival British grid references into the guarded quality view while retaining source identities, original fields, dates, uncertainty and unresolved cases. This directory contains **24 accepted decisions**, an **83-record source-candidate census** and **59 unresolved records**. It is an analysis/evidence directory, not a release staging tree.

Canonical lane artifact: `accepted_grid_recovery_decisions.jsonl`, interpreted alongside `REPORT.md` and `validation_receipt.json`. Rollback: the unchanged production-pinned source catalog in shared `data/canonical_web`. The parent task retains the current validated deployment and one known-good production rollback; this directory adds no deployment copy.

Inputs and provenance:

- Existing shared `data/canonical_web` summary/detail gzip files, checked against `reproduction/release.json` pins; the base manifest hash is recorded in `source_grid_candidates.json` and accepted decisions.
- Existing UFOCAT codebook extract at `data/reports/ufocat_codebook_extract/UFOCAT Codebook 2023.txt`, hashed in the source census. Coordinate encoding and location-role sections are cited by each accepted decision.
- Shared populated-place authority references captured in `named_grid_place_references.json` by the parent task, including exact primary/ascii/alternate name comparisons. Preserve this pinned compact file when rebuilding the decision step; no full gazetteer copy is needed.
- Official `OSTN15-OSGM15-Lite-DevelopersPack.zip` validation input, retained at 1,260,148 bytes. Its official URL and SHA256 are recorded in `validation_receipt.json`. The runtime conversion uses approximate Helmert rather than the OSTN15 correction grid.

Rebuild from the project root:

1. Run `py -3 data/research/database_quality_20261007/grid_reference_recovery/research_grid_references.py` to extract current pinned raw grid candidates.
2. Retain or reproducibly refresh `named_grid_place_references.json` from the existing shared authority using the same exact-name and British-context policy; never substitute an unpinned global geocoder response.
3. Run `py -3 data/research/database_quality_20261007/grid_reference_recovery/build_grid_decisions.py` to rebuild accepted/withheld decisions and validation receipts. The builder imports `british_grid.py`, preserves nominal source values, and requires the retained official developer pack.

Retention decision: keep all compact unique evidence and reproducible scripts in this directory, including the official control pack and unresolved worklist. `__pycache__` is disposable interpreter output, not an input or safety backup; no cleanup is required to complete this task. There are no historical full-data backups, superseded releases or unexplained large directories here. Expected lane size is approximately 1.6 MiB, with no file above 100 MiB. No deletion is proposed.

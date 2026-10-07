# Purpose and reconstruction

This is a new research lane for the 1,529 international exact-locality candidates held by the earlier gazetteer pass. It is a sparse source review and guarded decision package, not a corpus backup or deployment directory. Retain its unique source/context decisions and receipts with the 7 October 2026 quality package.

Shared inputs are the canonical web catalog, its production hash receipts, the old gazetteer screen/admin facts, and the existing GeoNames archive. `prior_accepted_inputs.json` freezes the seven accepted predecessor sidecars by path/hash and the then-current root manifest hash. It does not copy their data. This prevents reconstruction from ingesting this lane's own decisions after future root integration.

From the project root:

```text
py -3 data/research/database_quality_20261007/international_source_recovery/prepare_source_review.py
py -3 data/research/database_quality_20261007/international_source_recovery/recover_declared_localities.py
py -3 data/research/database_quality_20261007/international_source_recovery/recover_declared_localities.py accept
py -3 data/research/database_quality_20261007/international_source_recovery/verify_recovery.py
```

The builder reads shared files in place, aborts on failed pins/guards and writes only lane-local sparse artifacts. Original online fact receipts and explicit human context reviews are inputs; do not replace a failed fetch with a claimed verification. The PDF evidence extractor uses the bundled Python environment with pypdf and `prepare_source_review.py pdf`; if publisher bytes change, retain the existing evidence and record a new research version rather than overwriting the original receipt.

`amend_wangenies_date_precision.py` documents the one-record final amendment from sidecar SHA256 `93011d8e22bf016e23bfac76c65329e820c95946ea9e20b4116c4cf688d5977b`. It reads only the Wangenies pinned chunk, preserves the other 165 sidecar lines byte-for-byte, and writes the focused receipt and date/census metadata. It deliberately rejects another starting hash, so it is a one-time amendment helper, not a command to rerun on the final sidecar. The main builder already includes this correction for complete reconstruction.

| Artifact group | Purpose | Retention |
| --- | --- | --- |
| Accepted sidecar, IDs, census, date annotations, verification and focused amendment receipts | Guarded integration delta and checks | Retain |
| Candidate/provisional/context disagreement reviews | Sparse full-source review trail and unresolved prioritization | Retain; approximately 4.6 MB total, no full corpus copy |
| Native online and PDF receipts, selected source PDF page/images | Publisher field semantics, individual fact checks and uncertainty limits | Retain |
| Owned/remaining IDs and predecessor pin list | Team ownership and reproducible non-overlap | Retain |
| Four Python scripts | Rebuild, focused amendment and fail-closed admission rules | Retain |
| REPORT.md, README.md, artifact_inventory.json | Scientific interpretation and storage accounting | Retain |
| __pycache__ | Automatically generated import cache | Reproducible; not required for reconstructing decisions |

No raw archives, canonical datasets, runtime assets, prior decisions or release/rollback artifacts are removed or duplicated. Parent integration must enforce cross-lane duplicate-ID/conflict checks. Remaining IDs are leads; their counts do not represent proven geographic repairs.

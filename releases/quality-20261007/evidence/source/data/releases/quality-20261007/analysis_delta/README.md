# Quality analysis release delta — 7 October 2026

This candidate contains eight current analysis manifests and compressed changed
projections for the validated guarded quality view. It uses the shared original
source records and the corrected map release; it contains no raw corpus, analysis
database, full index copy, or raw projection array.

The established six attribute classifiers and Analysis v2 spatial algorithms
remain unchanged. The release adapter substitutes only their pinned effective
source stream, geographic strata and compressed serializer. One original detail
pass supplies only the consumed compact fields in memory. Original narratives,
dates, IDs, dictionaries and source provenance remain protected in place.

The effective catalog still has 702,893 source records, now with 582,877 mapped
references. Geography assigns a country to 563,665 rows. Qualified source
coordinate endpoints decrease from 33,801 to 33,800, and qualifying neighbor pairs
from 42,575 to 42,574. Exact occurrence-date reporting-delay rows decrease by ten
to 261,321 after the source-confirmed precision downgrades. Configuration and
context-neighbor memberships remain unchanged. Additional locality, nominal grid
and installation references remain generalized; they are not measured craft
positions and do not enter the source-coordinate inference pool.

Nine targeted tests and the existing six material readiness gates pass. A single
bounded final artifact check verifies local file pins, gzip decoded pins, 19
changed JSON projections, mapped-row order, geography binary parity and current
source freshness. `analysis_validation_receipt.json` records that result.

The deployment assembler should consume `analysis_release_receipt.json`:

- R2 objects use `releases/quality-20261007/analysis_delta/<directory>/...`.
- Eight tiny Pages manifests use `data/<directory>/manifest.json`.
- Eleven unchanged immutable artifacts retain their prior URLs and pins.
- Six build audits, this README and the validation receipt are retained research
  evidence rather than application delivery objects.

The current effective map manifest SHA256 is
`316bfbfb3c20fa57324b28d840d84e8f79581f54d228876b4ad947408e028c2e`.
The sealed map receipt SHA256 is
`4c5cd6aa00de0eb9be1a54387a2d249ebce3b4c754922949cb85183e229bcf5d`.
The analysis delivery receipt SHA256 is
`7458c39b3301bb10da506579f68f1e9a0e648ac2e49bc16ad1c47dce1c4b676a`.
The old canonical base hash is retained separately and is not advertised as the
current effective map/summary hash.

Declared artifacts occupy 44,270,122 bytes (42.219 MiB), plus small local receipts
and these notes. No new file exceeds 100 MiB. This is below the approved 65 MiB
analysis cap. Net local growth is approximately 42.3 MiB; no superseded staging or
backup directory was created.

After parent integration, validation and publication, this delta and its inherited
immutable pins are the canonical current analysis release. Retain the previous
validated analysis release as the rollback chosen by the parent release package.
Retain all unique audits and receipts. No cleanup is needed in this directory.

Rebuild in a new, explicitly approved empty candidate directory using
`py -3 scripts/build_quality_analysis_release.py --build --output <directory>`.
The default command performs a read-only storage estimate. The builder rejects
nonempty destinations, stale source/map pins, classifier input-contract drift,
failed established readiness gates and artifacts exceeding the configured cap.

# Mapping recovery, 3 November 2026

Current reviewed local candidate. **Not deployed.** The current production and
rollback remain 90fa1b95 and 0ac7c2bc respectively.

The complete 702,893-record served catalog was checked. Every one of its 120,016
unmapped records was screened against retained location authorities and original
source evidence. Accepted corrections add **12,479** map references and correct
one existing marker on the wrong Hawaiian island. The candidate contains
**595,356 mapped / 107,537 unmapped** source representations, not independent
incident counts.

Of the newly mapped records, 11,437 are country/state/province references and
1,042 have locality, compound-locality, or original-source coordinate references.
Broad references are explicitly labelled; they do not become exact sighting
positions or qualify for precise spatial inference. The five reported examples
are included. Original dates, narratives, identities, and source fields remain
unchanged. Unresolved cases retain per-lane reasons and evidence; this pass does
not claim that every remaining location is impossible to recover.

## Candidate and evidence

- Root: `D:/UFO-Timeline-Research/mapping-recovery-20261103`
- Human review: `recovery-report.html` (standalone, with local evidence links)
- Canonical decisions: `accepted-decisions.jsonl.gz`
- Map delta: `map-delta/map_release_receipt.json`
- Analysis delta: `analysis-delta/analysis_delta_receipt.json`
- Sparse deployment inventory: `candidate/delivery_plan.json`
- Actual runtime overlay-chain check: `frontend-integration-review.json`
- HTTP/gzip delivery check: `preview-delivery-review.json`
- Local preview: `http://127.0.0.1:8137/index.html`

`candidate-receipt.json` in this directory pins these artifacts. The evidence root
also retains all candidate and hold ledgers, full unresolved source snapshots,
authority pins, original-member checks, and report rebuild instructions. Raw
source chunks stay shared under the Desktop project's canonical directory.

## Validation

The current 71 summary shards and all 282 source detail chunks were hash-checked.
All 12,480 accepted changes pass summary guards and full effective-detail guards
after the previous quality and date overlays. No chronology recomputation occurred.
The actual JavaScript loader accepts the complete new patch packet. All seven
manual example/copy records agree with the rebuilt summaries, with every
non-geographic effective field preserved.

Analysis geography contains 595,356 aligned rows with full binary/JSON parity.
Strict spatial and context projections and current codebooks remain unchanged;
readiness denominators and descriptive macroregions reflect the recovered data.
Three Burundi references remain country-unknown in Analysis because that country
is absent from its frozen codebook; their map references remain available.

Focused source-admission, overlay, map/Analysis-build, and cache tests pass. The
HTTP check verified 28 requests including the compressed production upload
paths. Returning-visitor manifest URLs now carry the new version. Visual UI
inspection could not run: both browser-control and native computer-use kernels
failed with `failed to write kernel assets: path not found`. No visual pass or
production deployment is claimed.

## Rebuild and preview

Use the tracked audit, recovery, admission, manual-review, merge, map-build, and
Analysis-build scripts, with the exact input paths/hashes recorded in their
receipts. They refuse accidental replacement of accepted/generated data. Do not
run historical full-corpus builders or copy a whole staging tree.

After the two deltas are built:

```powershell
python scripts/prepare_mapping_recovery_candidate.py --root D:/UFO-Timeline-Research/mapping-recovery-20261103 --serve --port 8137
python scripts/verify_mapping_preview.py --root D:/UFO-Timeline-Research/mapping-recovery-20261103
```

The preview serves the shared source and sparse deltas directly. Production URLs
stay in the candidate plan; only preview responses rebase unpublished URLs to
localhost. Large objects belong on R2, not in Pages. Stage only the plan's Pages
allowlist when deploying, then verify the canonical and returning-visitor paths.

## Storage and retention

Approximately **447 MiB net growth on D:** and under **1 MiB of source/QA files on
C:**. No complete corpus, database, repository, or staging copy was created.
The only new file larger than 100 MiB is
`D:/UFO-Timeline-Research/mapping-recovery-20261103/unmapped-details.jsonl.gz`
(137,475,232 bytes; SHA256
`4e48f09585dac64055e7acb85ff04548b1abb2fd88da6717a93ca9b62d4bec79`).

The D: evidence root and its sparse map/Analysis candidate are canonical for this
review. The production pointer and retained rollback are unchanged. The initial
`location-source-review` directory (about 2.55 MiB) is superseded by
`location-source-review-v2`; retain it as review history until a literal-path
cleanup allowlist is approved. No cleanup or deletion was performed.

# Extended original-source geographic recovery

This directory preserves a bounded, source-supported continuation of the October 7 database audit. It reviews the 59 British grid records withheld by the earlier grid lane and 11 native reports explicitly associated with Fort Huachuca. It accepts 26 new coarse map references, with two guarded date-precision downgrades on those same records, and documents 44 abstentions. It does not change the corpus, reader, parent manifest, runtime assets or deployment.

`accepted_extended_online_recovery_decisions.jsonl`, its `extended_decision_manifest.json`, manually reviewed authority specifications and the pinned fact/source receipts are the canonical sparse analysis result for this lane. Parent integration remains necessary before these decisions become part of the effective quality view. The current parent quality view and its retained October 6 local rollback remain the prior counterparts; the production release and its existing rollback are unaffected by this lane.

## Evidence and safeguards

Each decision carries the eight common source/date/location guards, immutable base-manifest pin, full native record digest, original native provenance and compressed detail locator. The two precision downgrades add a guard for the original `exact_day` value and change only its effective classification to `approximate`. Stored occurrence dates, sort days, raw fields, narratives, canonical membership and record counts are preserved.

The 20 British references restore the literal archival grid coordinate after locality disambiguation against a primary geographic authority. The authority's building point is not substituted for the archive point. Their source resolution is generally 1 km; rounding/truncation is unknown and the retained approximate projection is not OSTN 15. County strings remain source material, not rewritten modern administrative assertions.

The six Fort references use a rounded city-level named-installation anchor. The NPS historic-district reference is inside the installation; it is not an exact witness building, object location, installation-boundary centroid or measured flight origin. Source-explicit ground observation is required. Route departures, dreams and more-specific unestablished trails were withheld. Multiple records may describe a repeated observer series; they are not counted as independently established incidents or automatically merged.

## Rebuild

Run from the project root with Python 3.14:

```powershell
py -3 data/research/database_quality_20261007/extended_online_recovery/build_extended_decisions.py
py -3 data/research/database_quality_20261007/extended_online_recovery/verify_extended_decisions.py
```

The builder reads shared canonical gzip chunks in place, the prior grid codebook/projection receipts, retained native review records, manually reviewed specifications, source bytes/extracts and a small pinned parent manifest. It hashes the original source chunks before use and excludes every accepted ID in that retained contract. It does not download the corpus or create a release tree. A mismatch fails closed rather than silently updating old evidence.

`retrieve_primary_sources.py` documents and can repeat bounded primary-source retrieval, with a 4 MiB per-file limit and a 14 MiB lane retrieval limit. Retrieval is not the evidence-acceptance gate: changed online bytes require a fresh manual review and pin before rebuilding. The source specifications and publication facts were manually reviewed on 2026-10-07. NPS page 4 was rendered and visually inspected with the bundled Python PDF runtime; standard-library code performs the rounded reference conversion. The ordinary build and verifier require no newly installed package.

`reviewed_parent_quality_manifest.json` is a 65,691 byte contract snapshot with SHA256 `fba5d2116aa974c4a39ca0095302e819aeb9669e94050b53b40ed187468a44e1`. It preserves the original exclusion set after parent integration. It is deliberately retained for reproducibility and is not a dataset or release backup.

## Retention and storage

Retain the accepted decisions, specifications, manifests, primary factual/source receipts, selected native records, original HTML/PDF evidence, reviewed PDF images and the two explicitly labeled web-tool text extracts as correction provenance. The selected records are 70 reviewed records, not a full corpus copy. The original JNCC chapter was approximately 28 MiB and exceeded the download cap; a bounded primary-publisher extract is retained instead. Direct Handsworth HTML retrieval returned 403, so its primary statutory text is also retained as a labeled web-tool extract, not claimed as original downloaded bytes.

`__pycache__` is a small, reproducible Python import cache and is not a required evidence input. No superseded dataset, staging tree or release is created by this lane. No deletion is performed or proposed. `artifact_inventory.json` lists file purposes, sizes and hashes; its own bytes are excluded from that hash inventory. Approximate net growth is 3.7 MiB, with no new file larger than 100 MiB and no operation near the 20 MiB lane budget.

## Verification result

All 26 full-detail digests and guards pass; summaries and details receive the exact same declared edits. Both precision downgrades preserve all stored date fields. The verifier rejects 210 stale guards and 108 invalid operations, including missing date guards and precision upgrades, and checks eight important abstentions. There is no overlap with the prior 3,379 accepted IDs. See `extended_validation_receipt.json` for immutable input and verifier pins and `REPORT.md` for findings and remaining leads.

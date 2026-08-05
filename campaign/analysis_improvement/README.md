# UFO Timeline Analysis improvement campaign

This directory is the authoritative, versioned control package for the continuous Analysis improvement campaign. It records the sealed production baseline, rollback target, source x era x region x field coverage, module readiness, ranked backlog, provenance and rights constraints, before/after metrics, completed-wave receipts, and the two-pass diminishing-returns stop counter.

The package is internal release-control evidence. It is not copied into the Pages bundle or R2 payloads.

## Invariants

- `webapp/static_public` remains authoritative frontend source; `static_bundle` is generated output.
- The worker-owned typed catalog remains the only browser event model.
- Original values and conflicts are preserved. Missing and unresolved values remain unknown, never zero.
- Raw presence, positive mentions, normalized fields, and inferentially qualified values are reported as different coverage kinds.
- Chronology connectors, trace styling, inferred travel, authenticity, incidence, risk, and causal facility interpretations remain excluded.
- No external whole-dataset ingestion is allowed without public-domain status, an appropriate license, or permission.
- Audit-only and no-gain waves are never deployed.
- Every accepted wave uses an identical frozen package for preview and production and keeps a tested rollback target.

## Regeneration

For a new campaign baseline, run `python scripts/build_analysis_improvement_campaign.py`. The builder scans the served canonical detail chunks and the pinned Analysis geography projection, verifies the row count against `data/app_config.json`, and writes deterministic JSON/CSV state. Once a completed-wave receipt exists, the builder fails closed instead of overwriting campaign history; `--force-reinitialize` is reserved for an intentional baseline replacement.

Advance an active campaign by adding the next preregistration, the completed wave's before/after metrics and receipt, then updating `state/completed_waves.json`, `state/ranked_backlog.json`, `state/module_readiness.json`, and `state/current.json` with verified artifact hashes.

The generated state is validated by `tests/test_analysis_improvement_campaign.py`. Per-wave preregistrations and receipts live under `waves/<wave-id>/` and must validate against the schemas under `contracts/v1/`.

## Current status

Wave 7 made role-preserving color evidence estimable for 70,097 catalog rows (9.972642%) across NUFORC and UFOCAT. Object-surface, emitted-light, compound, changing, ambiguous-role, descriptor-only, sentinel, and unparsed evidence remain distinct; Pattern Finder and incidence, authenticity, risk, and causal claims remain suppressed. The exact frozen package passed preview, production, served-hash parity, and isolated Wave 6 rollback reconstruction, and is deployed as production deployment `bb261575-1812-46ab-a6fd-1165e04759d0`.

Wave 8 closed as the first consecutive no-gain frontier pass. The local country shell is content-addressed and the assignment algorithm is deterministic, but the exact upstream repository calls the dataset's legal status dubious, its original gist is not an authoritative boundary release, and the 180 features contain only 179 unique identifiers. No code, data, preview, production, or rollback target changed.

Wave 9 closed as the second consecutive no-gain frontier pass. A fresh 1440x720 inventory kept Time as the tallest dashboard at 874.859375 px. The single bounded information-preserving prototype expanded the primary Time evidence to full width and placed the two already-closed supporting cards side by side, but the dashboard grew to 894.90625 px, a -2.29144 percent improvement. The runtime-only prototype was removed and the accepted height restored exactly; no source, served artifact, preview, production deployment, or rollback target changed.

The campaign is closed under its preregistered diminishing-returns rule. Wave 8 and Wave 9 are two consecutive bounded frontier passes with no safely deployable material gain. Production remains Wave 7 deployment `bb261575-1812-46ab-a6fd-1165e04759d0`, with tested Wave 6 rollback target `e4c8685c-4228-4e98-93fe-09a935fa86a6`.

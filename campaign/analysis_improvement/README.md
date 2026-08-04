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

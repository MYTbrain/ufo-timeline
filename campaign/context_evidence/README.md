# UFO Timeline context evidence campaign

This package is the authoritative control surface for bounded crop-circle and
animal-mutilation evidence research. It is separate from the completed
`campaign/analysis_improvement` package and is never copied into the public
Pages bundle.

## Goal and boundaries

- Milestone 1 requires at least 25 strict-ready cases in each domain and 100
  materially upgraded cases overall.
- Milestone 2 requires at least 100 strict-ready cases in each domain, with the
  source-family and regional balance recorded in `state/current.json`.
- Research effort is planned at 70 percent existing-case enrichment and 30
  percent source discovery. Case selection must never use UFO proximity,
  neighbor counts, or apparent association strength.
- Crop-footprint orientation analysis is out of scope. Context relationships
  remain descriptive and noncausal.
- A lane is parked after two consecutive preregistered no-gain subwaves. No
  third retry is permitted merely to seek a different result.

## Append-only ledgers

The four files under `ledgers/` are append-only JSONL. Empty ledgers are a valid
foundation state; later waves append one compact JSON object per line.

- `source_ledger.jsonl` records documents, source families, rights, content
  hashes, retention, derivation, and independence.
- `case_enrichment.jsonl` records field-level assertions. Every assertion cites
  registered sources and frozen evidence hashes.
- `case_review_decisions.jsonl` records independent decisions. One explicit
  human adjudication confers `human_reviewed`; `source_reviewed` requires at
  least two distinct agents to agree unanimously against identical frozen
  evidence. An active agent disagreement prevents promotion.
- `research_queue.jsonl` records priority, fixed query/opening budgets, attempts,
  explicit blockers, terminal disposition, and the required repository/catalog
  classification (`accept_ingest`, `metadata_only`, `duplicate`, `irrelevant`,
  `rights_blocked`, or `inaccessible`). Canonical queue rows are immutable
  terminal wave snapshots; later work on the same case appends a new wave row
  instead of rewriting history. Rank is deterministic within each wave so a
  later append never invalidates an earlier roster. Reusing a query, URL,
  repository sample, or source version fingerprint is rejected.

The previously processed 2,371 Atlas-linked URLs are not duplicated as ledger
rows. `state/known_source_reconciliation.json` content-addresses their canonical
27,953-row audit and directs the validator to reconstruct the exact fingerprint
set. Repository candidates discovered during the preliminary audit are marked as
already-known frontier inputs; the package does not claim a pristine pre-query
state.
The existing 18-entry cattle-mutilation source registry is likewise
content-addressed and its 15 URLs enter the exact no-repeat set. Registry
presence proves only that a lead was known; it does not claim document retrieval
or source independence.

Mirrors, scans, syndications, translations, and derivative retellings remain in
one source family unless independent evidence is demonstrated. A source row is
a lead, not corroboration, when its underlying evidence cannot be recovered.
An inaccessible lead records `contentSha256: null`; null is prohibited for a
retrieved source. New cases receive a stable `cc_*` or `ami_*` identifier before
assertions are accepted and must at minimum assert a source case identifier,
public title or summary, domain classification, date role, and location role.

## Deterministic validation

Run:

```text
python scripts/build_context_evidence_campaign.py --check
```

The validator checks every schema and line, cross-ledger references, reviewer
quorum inputs, source-family rules, queue rank order, fixed research budgets,
PII-forbidden key names, and no-repeat fingerprints. It then reconstructs the
foundation receipt and requires byte-for-byte equality with
`state/foundation_build_receipt.json`.

After an intentional ledger or contract change, generate the candidate receipt
once with `--write-receipt`, inspect the diff, and return to `--check`. Research
wave outputs belong under `D:\UFO-Timeline-Context-Evidence`; C: retains only
these compact ledgers, schemas, accepted runtime deltas, the current release,
and one documented rollback.

`state/release_seal.json` is the fail-closed release state for the explicitly
authorized mapping/provenance release. Its `pre_release` form freezes the four
ledger identities and records the honest 98-case, zero-strict, non-milestone
status. It may become `released` only after it records three checked-in runtime
manifest identities, exactly one successful local suite and clean-clone CI run,
immutable crop/animal/Analysis R2 readbacks, byte-identical preview/production
Pages evidence, reproduction hashes, and the retained pre-release production as
rollback. The seal schema prohibits milestone, strict-readiness, trace, or
causal claims. The mutable seal is validated on every campaign check but is
excluded from the immutable foundation receipt so deployment IDs can be added
after promotion without rewriting the frozen evidence foundation.

Adjudicated waves enter these ledgers only through
`scripts/apply_context_evidence_wave.py`. Its content-derived package manifest
pins all four candidate JSONL files, it requires complete independent review,
rejects ID collisions and partial wave extensions, proves every canonical file
retains its prior byte prefix, and refreshes the campaign receipt only after the
combined ledgers pass the source, lineage, queue, privacy, and bootstrap rules.

## Wave discipline

- A case first pass permits two targeted queries and four substantive source
  openings. Escalation is allowed only when one promising strict gate remains,
  and adds at most three queries, four source openings, and one archive fallback.
- A domain subwave is productive only when it produces three strict-ready cases,
  eight decisive analysis-critical upgrades, or twelve resolved source-family
  or duplicate-lineage decisions.
- Per-wave validation is one focused pack, one correction pass, and one final
  targeted rerun. A second failure quarantines the wave.
- Full acceptance, deterministic double-build, browser QA, and deployment occur
  only at a qualifying milestone release.

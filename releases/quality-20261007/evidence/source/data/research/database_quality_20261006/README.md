# Database quality improvement batch — 6–7 October 2026

This package follows the current database-wide audit. It enriches the shared
catalog with original-account identity links, source-backed location decisions,
and guarded unmapped recovery decisions. Existing raw sources, current runtime
assets, and the original served catalog remain protected.

The canonical artifact for this batch is a sparse, source-pinned quality view:
the existing catalog plus compact reviewed decisions and account links. It must
retain before values, source evidence, original event IDs, witness/publication
distinctions, and every unresolved date/location conflict. No whole composite
event is merged solely because its primary account has a matching upstream ID.

## Inputs and provenance

- Shared base: `data/canonical_web` (702,893 current records).
- Immutable data contract: `reproduction/release.json`, v152 July 31 release.
- Canonical manifest SHA-256:
  `242ff4abc42c70c2b241a3cd16c8b9059bca137d940bd6147c5a65de63b7750b`.
- Audit evidence: `data/research/database_audit_20261006`.
- Existing source archives, SQL, GeoNames and review evidence are read in place;
  their hashes and individual authorities are recorded in lane receipts.

## Lanes and rebuild

Each lane contains its reproducible script and report:

1. `account_links/`: source-native original-account identity and conflict classes.
2. `location_corrections/`: supported coordinate/precision decisions; ambiguous
   observer, airborne, route and historical jurisdiction cases remain unresolved.
3. `unmapped_recovery/`: targeted native location-ID lookup and original-field
   evidence; administrative centroids are not automatic populated-place fixes.

The final batch report documents how the validated quality view is read without
materializing the complete corpus. The base manifest and exact current-field
guards must pass before a decision can be applied. Stale or conflicting decisions
fail closed. Original values and decision evidence remain inspectable.

Completed: 1,632 accepted guarded changes, 113,539 original-account relationships,
47,788 optional agreeing-account projection candidates and 726 review-only date
role annotations. All 702,893 base representations remain available. The effective
view contains 580,786 mapped and 122,107 unmapped records. See `REPORT.md`,
`quality_view_manifest.json`, `sparse_quality_view.py` and the validation receipts.
This batch is usable locally and has not been published to the live website.

## Storage and retention

Target output budget: below 100 MiB combined. There are no planned artifacts above
100 MiB, no full catalog/static-bundle/database copies, and no timestamped backup
tree. Retain this as unique research and quality enrichment evidence. The existing
base catalog is the retained rollback for the quality view. Current production
remains `78cc3660-5750-4685-a095-fee6dce37fbf`; production rollback remains
`f88416b1-1e96-45fa-8b2a-a1edbfc5fdae` unless a later publication receipt changes it.

No superseded data or historical analyses are deleted. Final output sizes, newly
created large-file inventory, net artifact growth and retention decisions are
reported in the batch report. No cleanup is proposed merely to remove protected
history.

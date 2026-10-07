# Reviewed database quality release — 7 October 2026

The release applies the complete validated sparse quality view to the public map,
trace indexes, startup profiles, report details and analysis projections together.
It preserves all 702,893 source representations and their original identities,
source fields, narratives and sorting dates. Reports are not automatically merged.

There are 582,877 mapped reports and 120,016 unmapped reports. The quality view
contains 3,730 accepted record changes. Eleven date values previously labeled
exact day are now marked approximate; derived time-order confidence and analysis
eligibility are recomputed. The two October 7 research passes recover 2,091 map
references. A reference often identifies a submitted municipality or archival grid
area, rather than a measured observer position or a craft's location.

## Runtime and provenance

The new immutable assets use R2 prefix `releases/quality-20261007`. Corrected
summary shards and regenerated packed indexes are published separately from the
unchanged original detail chunks. The details loader verifies the compressed hash
and applies 4,451 guarded patches, including 726 review-only date annotations and
preserved shared-incident metadata. It checks source, original values, identity and
chunk locator before accepting an edit. The earlier display-label overlay cannot
overwrite reviewed records.

Map and analysis share the same effective catalog and packed-point fingerprints.
Changed analysis projections are regenerated, while 11 unchanged immutable
artifacts are reused. Original attribute classifiers and raw-value dictionaries
are retained; the date-precision and geography codebooks reflect the corrected
effective pool. Approximate dates cannot retain unsupported exact-day chronology.

The Reports downloads remain historical exports of the original catalog and are
labeled accordingly. They are not exports of this corrected quality view.

The original detail corpus remains shared under the immutable
`coordinated-reliability-v152-20260731` prefix. Large source archives and research
databases are not added to Git. Small release contracts and sparse evidence provide
reviewable pins; source rebuilds require the separately retained canonical inputs.

## Validation

- The map builder checks all source chunks and preserves all 579,365 unchanged
  mapped rows' decoded packed values, including UTC and lookup semantics.
- The analysis builder checks all changed artifact hashes and 582,877 geography
  rows against the current map metadata. Six material readiness gates pass.
- Targeted browser-module tests check stale guards, protected fields, immutable
  inputs, malformed coordinates, duplicate patches and compressed integrity.
- Existing famous-case, trace navigation, direction summary and packed-index
  tests pass. Publication additionally verifies the frozen public asset inventory
  and exercises the actual preview in a browser.

Publication IDs, commit pins, exact byte inventories and final verification are
recorded in the release's publication receipt after deployment.

## Storage and retention

The local build is `data/releases/quality-20261007` in the research workspace.
Its map delta is about 225.4 MiB, and its analysis delta is about 42.3 MiB. Only a
small Pages candidate is assembled; original chunks and databases are never copied
into it. No newly generated file exceeds 100 MiB. The release cap is 850 MiB and
the Pages candidate cap is 40 MiB.

The new production deployment becomes current when verified. Deployment
`78cc3660-5750-4685-a095-fee6dce37fbf` is retained as the single known-good
production rollback. The prior rollback designation is superseded; shared source
assets required by current or rollback remain protected. The October 6 sparse
quality manifest remains the local quality rollback. Any future removal of
generated staging data requires a literal allowlist and retained counterparts.

# Famous-case catalog coverage repair

This records the initial 16-reference repair. The subsequent full-list identity
review in `FAMOUS_CASE_FULL_IDENTITY_REVIEW_2026-10-06.md` supersedes its limited
identity scope; this document remains part of the release provenance trail.

Cash–Landrum showed no nearby map results despite six explicitly identifying
catalog records. Five have no coordinates; the UFOCAT entry is geocoded roughly
418 km from Huffman. Maury Island has a similar misplaced point and six unmapped
source records. Calvine, Hangzhou and Norway spiral also have identifying unmapped
entries. Berkshire's original case entry remains unverified in the bounded review.

The interface now exposes these 16 reviewed source references in the Results
summary, with mapping status and direct Full Details access independent of map
filters. The references never become synthetic points or trace seeds. Source and
date checks fail closed when catalog identity changes. Multiple entries about the
same case remain multiple source records, not independent incidents.

The complete-catalog vicinity diagnostic distinguishes missing mapped candidates
from existing candidates hidden by filters. It waits for complete ingestion,
honors current dates and circle geometry, and caches the geographic scan without
changing the map, playback or statistical cohorts. Unreviewed presets are labeled
as historical navigation presets with database identity not yet checked.

## Evidence and validation

- `FAMOUS_CASE_CATALOG_AUDIT_2026-10-06.md`: exact record identities, source locators,
  full-detail indices/hashes, mapping discrepancies and excluded weaker mentions.
- `FAMOUS_CASE_VICINITY_COVERAGE_2026-10-06.json`: 85 presets, 702,893 summaries,
  71 production-pinned shard hash checks, six empty vicinities, twelve entirely
  excluded by the default raw craft Type selection.
- Node: preset, reference, trace and direction/case integration checks passed.
- Python: three case-navigation shell checks passed. App syntax and static release
  dependency/data pins passed.

## Storage and rollback

The root Git source and existing `.tmp/interface-pages-candidate` are the canonical
interface artifacts. Refresh the candidate only after checking its existing hash
inventory; replace changed allowed shell files and refresh the inventory. Do not
copy or rebuild the canonical corpus. The candidate's 151 files total about
24.56 MiB; this repair changes only four already-staged interface files. Audits
retain about 107 KiB of new evidence. No newly created file exceeds 100 MiB.

The validated production `e988d48e-896e-4f92-9205-f75365bd1cfa` is the rollback for
this update. The earlier `ca73305a-aff6-4466-8d9a-83c9416f4cfe` deployment and the
temporary `d60a8856-e538-4515-9c73-72cbe863953a` preview are superseded remote
cleanup candidates after validation. Existing local research and dataset rollback
directories retain their documented protected purposes. No dataset or analysis
deletion is part of this repair.

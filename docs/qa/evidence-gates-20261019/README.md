# Evidence readiness inspector

Preview: https://analysis-groups-20261018.ufo-timeline.pages.dev/#analysis-section-context

Immutable preview: https://5e423cb2.ufo-timeline.pages.dev/#analysis-section-context

Published source: `e95e07c`. Main implementation `cf15080`; presentation refinements `72a5786` and `70e0f80`. This is a preview-only update. No main-branch push or production deployment was performed. Protected production remains deployment `16b1c76f-8896-4c00-ab00-4676212a941e`, source `94384c0`; the single designated rollback remains `16443086-c630-41d8-a793-92a0243a76f6`, source `15ab160`.

## Changes

The Evidence Gates landing view now answers what each evidence family can support. It provides a family/lane picker, a single focused inspector, exact counts with explicit units, status symbols and plain-language output descriptions. Strict lanes show their pinned count targets and source/region balance requirements. Actual failing checks lead; secondary assessment information, repeated release notes, policies, evidence hashes and the full matrix remain available in disclosures. The full matrix has its own horizontal scroll area. A related-analysis action opens the existing native chart rather than a duplicate view. Phone layouts use two compact native selectors.

The release-wide evidence inventory is explicitly distinguished from active-query support. Changing analysis dates does not imply recomputing the sealed inventory. No aggregate quality score or invented sequential funnel is introduced. The existing Overview improvements, Analysis navigation, temporary A/B groups, map, guided tour, fast initial map and loading cover remain in this preview.

## Audit and interpretation corrections

- The military and research/test rows share the same facility inventory and checks: 70 qualified markers among 1,800. The inspector warns against adding these as separate datasets.
- The crop summary of 3,652 among 7,745 records is an aggregate of the bounded and locality marker lanes, not an additional failed test. Available marker lanes do not inherit strict-only blocking checks. All source gates remain inspectable, including context-only checks.
- The animal exact-site/reviewed predicate also evaluates dates. Its Date matrix column now carries the existing joint check rather than claiming no date check exists. The primary predicate was verified in `scripts/build_analysis_v2_artifacts.py` in the shared canonical workspace.
- Strict crop and animal eligible counts are unique location-date clusters. Catalog totals are record counts. A cluster-to-record readiness percentage is not displayed. The actual strict crop count is 1 and the strict animal count is 0. The first pinned cluster threshold is 25. The balanced-cohort milestone requires 100 clusters, at least two source families, at least two macroregions containing at least 25 clusters each, and no source-family or macroregion share above 60%. Source-family labels can overlap. Zero-cluster concentration is shown as not measurable.
- A recorded strict gate count of 1/1 can still be blocked by the minimum sample requirement. Retention bars preserve source statuses and do not promote this result to ready.
- Claimed UFO sites retain 11 descriptive records but have zero inferentially eligible records. Relationship data separately show 1,804 records, 1,320 reconciled records and zero association-eligible records. Retention and reconciliation are not evidence of association or causation.
- An absent separate dimension result is distinguished from a failed check; a requirement may be evaluated in a joint predicate. Overlapping exclusion reasons are not added into a funnel or treated as independent audits.

No corpus records, source coordinates, dates, statistical populations, evidence policies or eligibility counts were changed. Missingness is not filled by guesses. New metadata passes through existing manifest facts; it does not create a second analysis database.

## Verification

Twelve focused JavaScript suites passed: readiness model, readiness view, readiness integration, existing view repairs, spatial projection/cache race, scheduling repairs, Overview integration, Overview view, Analysis session context, Analysis session view, search integration, and startup/cache/loading cover. Ten Python release/search tests passed. The affected readiness view and integration suites passed again after the final disclosure change. Syntax and whitespace checks passed.

`readiness-audit.json` retains the exact 20 typed checks and a compact projection of the 11 lanes, with pinned manifest, builder and relationship-artifact provenance. The 92,122-byte relationship gzip was verified and decoded in memory; its 1,804 rows were not copied into this QA folder. Integration tests reconcile all lane/gate counts, statuses, policies and thresholds to the fixture, cover full/context-only metadata parity, null versus zero, unlike units, shared inventories, unknown gate preservation and native navigation.

`public-preview.json` records the independent public/source/stage reconciliation. All 225 staged runtime files match committed source. The two final changed public assets were streamed and verified; the remaining 221 public assets inherit exact verified hashes from `c7ad79b6`. That preceding receipt is retained inline and verifies nine changed assets against accepted source `6987b51`; its 214 unchanged assets inherit that accepted preview's exact hashes. All 105 immutable data objects and their input pins remain unchanged. Final stage tree: `ab9002e869cef49e449b698ec8633c85642599cf0b9b99f7da4f8ce2b9a7a728`.

Hosted browser observations and screenshots are recorded in `browser-checks.json` and the adjacent PNGs. All Time with existing default report filters displayed 334,511 active report representations and 21,110 qualified endpoints, separately from the release-wide inventory. The bounded crop lane remained available with 427/7,745 records and no false red failure section. Strict crop milestones displayed 1/25 and 1/100; duplicate release notes started collapsed. The animal strict view displayed 0 clusters and explicitly unmeasurable concentration. The full matrix retained all 11 rows and the corrected animal Date check. Facility/claimed-site counts and native relationship navigation were checked; detailed strict policies and hashes remained visible when expanded. Arrow-key navigation selected and focused the same lane. No browser console errors were observed. The loading cover remained present during startup.

Desktop document/client widths both measured 1,265 CSS px. At a 390 by 844 phone override, document/client widths both measured 375 CSS px; both selectors worked, and the 1,050 px matrix scrolled within its own 262 px container. The viewport override was reset. Some unchanged facility/relationship/date paths were inspected on the immediately preceding preview, as recorded in the browser receipt; the final source change only folded repeated release notes, and final-source integration tests also cover those paths.

## Storage lifecycle

The canonical preview stage is the existing `.tmp/workspace-analysis-20261008-pages`, refreshed in place and reproducible with `scripts/prepare_workspace_analysis_release.py --refresh-stage`. Its 225 files total 41,055,766 bytes, a 66,690-byte increase over the preceding accepted Overview preview. Shared canonical datasets, raw inputs, provenance, the current production release and the designated rollback remain protected. No complete corpus, database, static bundle or release tree was copied for this task.

New source, tests, compact audit fixture, QA receipts, screenshots and the stage delta total less than approximately 3 MiB of project growth. No newly created project file exceeds 100 MiB. C: remains below the 100 GiB reserve; no large generated-data operation was performed. Preceding preview `1b4fbabd` and interim previews `afbdd2a6` and `c7ad79b6` are superseded for the active preview alias by `5e423cb2`; these are provider preview deployments, not retained local release copies. No superseded large local directory was created and no protected-data deletion or cleanup is needed. The QA directory is retained as the small reproducible receipt for this change.

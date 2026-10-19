# Analysis pattern dashboard preview

Preview: https://analysis-groups-20261018.ufo-timeline.pages.dev/#analysis-section-overview

Immutable preview: https://25ccc615.ufo-timeline.pages.dev/

Published source: `dce0a8b16a738ceb2910441a3354971bc5129628` (implementation `1b53dd0`, responsive refinement `c29624b`). Production remains deployment `16b1c76f-8896-4c00-ab00-4676212a941e`, source `94384c055f9363c8ebdd13d1c8fcec1c5e83ba3d`. Designated rollback remains `16443086-c630-41d8-a793-92a0243a76f6`, source `15ab1607390d636f1571fa10bb4c8b137cf391f2`. No production deployment or main-branch push was performed.

## User-facing changes

Analysis > Overview now defaults to a pattern dashboard. Four primary views show craft through time, being descriptions with craft, country craft profiles, and seasonality through time. Time matrices span the available width. Additional craft/month, source/decade and being/decade views are grouped under More patterns.

One shared report lens switches every matrix between all active reports, reports with indexed being descriptions, and positive reported-abduction codes. Combined with the existing date and other report filters, this supports more than two variables without a separate set of dropdowns for every chart. Row percentages and report counts are selectable. Exact tables and field coverage remain available in disclosures. Country profiles use consistent category colors and shares within each country.

Existing Cohort overview, Signals & patterns, Methodology & provenance, native topic charts, and temporary A/B groups remain available. Chart cells and Explore actions reveal the corresponding detailed chart and its saved subview; they do not claim to apply a cell-specific filter. Separate crop/animal context links state that their counts cover the date window in their own catalogs. Soil/plant collections and celestial/nuclear comparisons remain explicit topic links rather than fabricated joined populations.

## Counting and scope

The worker builds sparse aggregate cubes from precisely the active report membership, including non-date filters, date intervals, area selection and exact-ID cohorts. A model-population mismatch fails the optional dashboard rather than replacing existing Analysis results. Counts describe report representations, not independent incidents. Being labels can overlap. Ambiguous abduction codes are not positive abductions. Missing provenance, unindexed evidence, unavailable fields and unknown dates remain distinct from positive evidence; civil date boundaries are not filled with invented months.

The dashboard is lazy: its model is not loaded at Map startup or for requests without Overview. Reviewed geography is requested once after a successful visible Overview render. Existing pinned catalog data are shared. The dashboard does not automatically load planetary ephemerides or create new research joins.

## Verification

Twenty-one focused JavaScript suites and ten Python release tests passed. Coverage includes the new model, view and worker integration; date epochs and interval ambiguity; active and exact-ID memberships; positive evidence provenance; native topic/subview navigation; null versus zero; rare report lenses; retained keyboard focus; existing A/B, search, loading cover and release behavior. The affected view and integration suites passed again after the responsive refinement.

Hosted browser checks used All Time with the existing default report filters: **334,511 active report representations**, **2,368 reports describing beings**, and **823 positive reported-abduction representations**. These are filtered UI denominators, not whole-corpus encounter totals. All three lenses updated the cards. Counts/row shares switched correctly; a positive craft cell opened the visible Craft by era view. More patterns exposed the three additional charts. Exact tables populated; prior Cohort overview and Methodology views remained reachable. No browser console errors were captured.

Desktop document width and scroll width both measured 1,265 CSS px. Phone override was 390 by 844; client and document scroll widths both measured 375 CSS px including its scrollbar convention. The first phone matrix had a 285 px scroll container and 635 px content, so scrolling stays within the card. The viewport override was reset after testing. Screenshots are `desktop-dashboard.png` and `phone-dashboard.png`; `browser-checks.json` records the bounded observations.

`public-preview.json` verifies all **221** staged runtime files against committed source and eight changed public assets against served bytes. The remaining 211 public assets inherit exact unchanged hashes from the previously verified preview. All **105 immutable data objects** remain byte-identical. The delivery-plan tree is `fa82251b973bacd4c9a77360ef23dc9ad4ca4ca3cb8702cb8d632b83a999ca37`.

## Storage lifecycle

Canonical datasets, raw sources, provenance and the existing D: derivative remain shared and unchanged. The one bounded candidate stage `.tmp/workspace-analysis-20261008-pages` was refreshed in place; it is the canonical preview stage, reproducible with `scripts/prepare_workspace_analysis_release.py --refresh-stage`. Its 221 files total **40,961,084 bytes**, **59,396 bytes** above the previous accepted preview stage. No corpus, analysis database or full release-tree copy was created.

New source, tests, screenshots and QA receipts plus the small stage delta add less than approximately 2 MiB of project data. No newly created file exceeds 100 MiB. C: remained below the 100 GiB reserve, so no large data build or copy was attempted. Production and its single designated rollback stay protected. Preview deployments `a9a81802` and interim `f3189ab9` are superseded by `25ccc615` for this active alias; they are historical provider previews, not additional local retained release trees. No superseded large local staging directory was created, and no dataset deletion or cleanup is needed for this batch.

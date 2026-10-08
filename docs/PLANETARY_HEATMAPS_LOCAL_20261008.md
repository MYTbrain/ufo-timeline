# Planetary heatmaps — local handoff, 2026-10-08

The local Comparisons → Planets preview now offers an overview of every supported body and pair, with cell inspection and a returnable detailed comparison. This is a validated local candidate; nothing has been deployed. Browser, narrow-screen and keyboard smoke checks passed. A missing constructor callback found during browser QA was corrected and is covered by an actual-controller regression.

## Three questions

| View | Rows × states | Cells per report domain |
| --- | --- | ---: |
| Zodiac positions | 9 bodies × 12 equal zodiac sectors | 108 |
| Planet pairs & aspects | 36 unordered pairs × 5 major aspect bands plus outside-band | 216 |
| Direct & retrograde | 9 bodies × direct, retrograde and near stationary | 27 |

Each of the UFO/craft, crop-circle and animal-report domains has 351 cells, for 1,053 total. The supported bodies are Sun, Moon, Mercury, Venus, Mars, Jupiter, Saturn, Uranus and Neptune. Pairs appear once; there are no self-pairs or duplicate directions.

## Behavior and method

Color defaults to report share minus matched calendar share, in percentage points, with a neutral zero and a consistent diverging scale. Report share is available as an alternative. Clicking a cell exposes counts, calendar-weighted counts, shares, ratios, sampled stable/possible limits and within-month contrast. Zero calendar opportunity has a null ratio; missing eligible dates appear unavailable rather than zero-share evidence. Keyboard navigation and exact-value tables accompany the matrices.

The declared estimator is `planetary-heatmaps-v1-common-grid`: every body and pair uses the same 11 samples over the complete 50-hour possible UTC interval of a recorded civil date. Cell drilldown selects `samplingMode: common_grid` to preserve overview bounds. Legacy detailed views retain their original adaptive sampling; their sampled bounds can differ, while the retained default UTC-noon counts remain unchanged. These limits are not confidence intervals or formal continuous-time enclosures. Verified timestamps, source date roles, historical calendar exclusions, and unavailable houses retain the existing gates.

Actual calendar days are weighted separately by each domain/category's represented year-month report mix and clipped to the active date window. Shared zodiac origins cancel in aspect angles. Within-month contrast and era/season limits remain visible; scanning many cells supplies no statistical-significance or causal claim.

The overview loads lazily and reuses the existing physical ephemeris atlas and prepared filtered cohort. Domain, matrix, color and cell changes are local display operations. Relevant convention/orb or report-filter changes use correctly scoped cached models; generation/cohort checks reject stale responses. No report aggregates were frozen into the atlas.

## Verification and publication status

`data/analysis_comparisons/planetary_heatmaps_qa.json` records a passed full retained-cohort check: all 1,053 cells partition their eligible counts and expected calendar counts, and sampled limits contain the estimates. Full common-grid Venus–Mars and Sun–Moon drilldowns agree. The overview took 1.920 seconds cold and 231 milliseconds warm, excluding initial cohort preparation and browser loading.

Targeted coverage is in `tests/test_analysis_planetary_heatmaps.mjs`, `tests/test_analysis_planetary_heatmaps_real_artifacts.mjs`, `tests/test_analysis_comparisons_view.mjs`, `tests/test_analysis_comparisons_worker.mjs`, and `tests/test_analysis_comparisons_schedule.mjs`. It covers all 36 pair drilldowns, reverse-pair symmetry, category-specific calendar weighting, source/date gates, unavailable states, neutral color, keyboard access, evidence export, lazy requests and settings/cache identities. The independent review in `PLANETARY_HEATMAP_METHOD_REVIEW_20261008.md` also checked 2,106 cells against detailed common-grid outputs across both zodiac systems.

The actual-model renderer, constructor-callback, signed-zero, worker and scheduling suites passed, along with retained core statistics, view, spatial-concurrency and planetary regressions. The 36 aspect-pair rows scroll within the matrix; arrow keys navigate cells with one entry in the page's Tab sequence. Difference cells use two decimal places and normalize rounded zero.

`data/analysis_comparisons/browser_planetary_heatmaps_qa.json` records browser checks for the actual filtered all-time cohort: 334,397 eligible UFO reports, 6,430 crop reports and 928 animal reports. The bulk request took 1.300 seconds including the worker response; matrix/domain/color/cell changes made no additional worker requests. Core and unrelated models retained their references. The Sun–Moon crop trine drilldown matched every displayed count, bound and calendar value. The narrow-screen grid scrolls locally without document overflow, keyboard selection works, and no console errors were captured. The screenshot is retained in the existing preview directory as `comparisons-heatmaps-preview.jpg`.

Deployment remains separate and requires the existing 39.39 MiB ephemeris atlas to use the project's R2 large-artifact delivery path, with its URL/hash pinned in the comparison manifest. The atlas exceeds the Pages bundle's per-file guard and must not be placed in the Pages upload.

## Storage and retained releases

Current local candidate: the existing frontend checkout and comparison runtime, with shared canonical catalogs referenced in place. The existing `ephemeris_atlas_v1.bin.gz` is reused unchanged: 41,307,851 bytes (39.39 MiB), gzip SHA-256 `d5c38232e0702783a46df4e38e24c8dce947ce54ab9843d93191ddce5b447b8f`. Its logical decompressed representation remains in memory; no additional raw binary, corpus, bundle, staging tree or backup was created for this work.

New artifacts are code/tests, small receipts, documentation and a browser screenshot only. No new file exceeds 100 MiB; approximate incremental project growth is under 1 MiB for this heatmap batch. C: had 124.64 GiB free at the final check. No generated release was superseded and no data cleanup/deletion is proposed. The existing preview directory retains its shared-data server and this proof of the candidate; it is not a release copy.

Validated production remains `dc834bac-2108-4de3-baad-47044e2ec51c`; the single retained known-good rollback remains `78cc3660-5750-4685-a095-fee6dce37fbf`. Both are unchanged. Small QA artifacts document this candidate and are reproducible from the named tests against the shared protected catalogs and existing atlas.

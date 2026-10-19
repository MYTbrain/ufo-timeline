# More visually informative Analysis overview

Preview: https://analysis-groups-20261018.ufo-timeline.pages.dev/#analysis-section-overview

Immutable preview: https://1b4fbabd.ufo-timeline.pages.dev/

Published source: `6987b51ee2c07544352d2fa6e23bf7e95e5903fc`. Main implementation `0a3c76d`; final small-value formatting `16bc332`. This batch only publishes a preview. The protected production designation remains deployment `16b1c76f-8896-4c00-ab00-4676212a941e`, source `94384c0`; the designated rollback remains `16443086-c630-41d8-a793-92a0243a76f6`, source `15ab160`. No main-branch push or production deployment was performed.

## Changes

- Added Difference mode alongside row shares and counts. Each known cell displays its row share minus the pooled category share in the selected report lens, in percentage points. A common symmetric blue/amber scale clips color at plus/minus 50 pp; the displayed values are not clipped. The scale marks zero. Missing, unavailable and unindexed axes remain striped and unsigned. A known zero-count cell can still show a negative difference.
- Added report-volume bars alongside row counts. Bars use the maximum over the complete card's row counts, including rows outside the displayed top categories; the maximum is labelled. Being rows can overlap.
- Reused the exact default map craft colors for category headings and country composition bars. Clicking a craft heading or legend chip emphasizes that category across craft-bearing charts, retains all report counts and denominators, and leaves non-craft charts unchanged. Rare highlighted categories are retained in truncated axes. A highlight clears with a status message when it is absent from a newly selected report lens.
- Added up to two compact row-versus-overall comparison tracks per card, with separate marker shapes, counts, shares and percentage-point differences. The descriptive selection rule ranks absolute differences among known cells with at least 20 row reports and 5 cell reports. It is a reading aid rather than a significance test or a claim about independent incidents.
- Added compact indexed-field coverage tracks. Difference-mode exact tables include the pooled reference share and the cell difference, including supported zero-count cells. Tiny differences keep their magnitude instead of displaying signed zero. Existing topic navigation, counts, report lenses, A/B comparisons, date/area filters and map behavior are preserved.

## Data and interpretation

The new visual helper uses the existing aggregate cubes. It does not rescan the corpus, create data copies, fetch new evidence or alter worker populations. Pooled shares use the complete untrimmed column report count divided by the report count in the selected lens. They never use summed being memberships or only the visible categories. Unknown reports remain in the denominator. The pooled baseline includes the row being compared.

Null/malformed counts and impossible intersections are rejected. In particular, an intersection must be between `max(0, rowN + columnN - totalN)` and `min(rowN, columnN)`. Being labels can overlap, but each marginal still counts report membership. Descriptive differences do not establish observing rates, statistical significance, independent events, physical association or causality. Custom user map-color overrides are not propagated into this standalone overview; its category colors match the default map palette.

## Verification

Eight focused JavaScript suites passed: Overview model, visual helpers, Overview view, Overview integration, A/B navigation, A/B view, search integration, and startup cache/loading-cover behavior. Ten Python release/search tests passed. The affected view and integration suites passed again after the final formatting fix. Pure helper checks include dense/sparse parity, overlapping-label denominators, unknowns, both intersection bounds, deterministic descriptive contrast selection and exact map-color parity. UI checks cover negative zero-count differences, unknown unsigned cells, fixed scales, reference columns, idempotent exact tables, rare-craft highlights, missing-lens clearing, keyboard focus and missing-helper fallback.

Hosted browser checks used All Time with the existing default report filters: 334,511 active report representations, 2,368 reports describing beings, and 823 positive reported-abduction representations. These are filtered UI counts, not whole-corpus encounter totals. Difference mode and all three report lenses rendered. Highlighting Disc/saucer kept 334,511 reports and did not dim the non-craft seasonality chart; clearing restored the other categories. A zero-count source cell displayed its valid negative difference. Exact tables exposed reference shares, counts and differences. The final table displayed a small contrast as `-0.02 pp`, with no signed-zero cells. No browser console errors were observed. The existing startup/loading cover remained present while the full catalog prepared.

Desktop client/document scroll widths both measured 1,265 CSS px. At a 390 by 844 phone override, client/document scroll widths both measured 375 CSS px; the lens was 303 px wide and the matrix scrolled within its 285 px container, with 635 px content. The override was reset. `desktop-cross-comparisons.png`, `desktop-difference.png`, `phone-difference.png` and `browser-checks.json` record the views and bounded observations.

Independent public verification in `public-preview.json` reconciles all 222 staged runtime files with committed source and verifies the four changed public assets against served bytes. The 216 unchanged public assets inherit exact verified hashes from the previous accepted preview. All 105 immutable data objects and their input pins remain unchanged. Stage tree: `9899b58c06d4c06e132f7bfad359ac35ef69dcdfe65309955880c016a0005f48`.

## Storage lifecycle

The canonical preview stage is the existing `.tmp/workspace-analysis-20261008-pages`, refreshed in place and reproducible with `scripts/prepare_workspace_analysis_release.py --refresh-stage`. Its 222 files total 40,989,076 bytes, 27,992 bytes above the preceding accepted preview. Canonical datasets, raw inputs, provenance and the existing D: derivative remain shared and unchanged. No corpus, database or release-tree copy was created.

Source, tests, screenshots, receipts and the stage delta add less than approximately 2 MiB of project data. No newly created file exceeds 100 MiB. C: remains below the 100 GiB reserve; no large net-positive data operation was attempted. Production and the single designated rollback stay protected. Preview `25ccc615` and interim `925f5ca2` are superseded by `1b4fbabd` for the active preview alias; they are historical provider previews, not additional local release copies. No superseded large local staging tree was created, and no protected-data deletion or cleanup is needed for this batch.

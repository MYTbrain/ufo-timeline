# UFO Timeline Analysis Tab v1 release receipt

Date: 2026-08-03

Status: frozen local release candidate; not deployed or promoted

## Source identity

- Production baseline: `920123ebebf996c69b12b031fa3796c8e3caf350`
- Working branch: `codex/analysis-tab-v1`
- Sealed catalog unit: 702,893 reports
- Sealed catalog SHA-256: `242ff4abc42c70c2b241a3cd16c8b9059bca137d940bd6147c5a65de63b7750b`
- Primary worktree remains uncommitted so release and deployment remain separately authorized actions.

## Delivered product surface

- Accessible `Map Explorer` and `Analysis` tabs with native tablist semantics, arrow/Home/End navigation, focus restoration, `aria-selected`, `aria-controls`, `hidden`, and `inert` states.
- Fresh loads default to Map Explorer. Analysis remains disabled until the core catalog reports Ready and loads its statistical code and context projections only on first use.
- The Leaflet map and all runtime layers remain mounted while Analysis replaces the central surface. Playback pauses without losing its cursor. Reopening Map Explorer restores the existing map instance, viewport, filters, layers, overlays, selections, and controls.
- Shared date, keyword, source, report type/craft, precision, crop-circle, animal-report, and point-only Area Filter state drives the Analysis worker.
- Local chart previews disclose cohort size, exact preview missingness, comparison counts, and changed criteria before applying or cancelling.
- Sections delivered: Overview, Time, Craft, Geography, Sources and Quality, and Context.
- Analytical outputs include coverage, active/reference comparisons, source-balanced time views, source composition, craft distributions and trends, equal-area geography, quality audits, descriptive crop/animal panels, and guarded Pattern Finder lanes.
- Three reference modes are available: disjoint other dates with matched non-date filters, the previous equal-duration period, and an explicitly descriptive full-catalog reference.

## Statistical and scientific guardrails

- Pattern Finder gates active N, observed and expected cell counts, effect size, 95% intervals, Benjamini-Hochberg q-values, and strict leave-one-source-out stability.
- Stable multi-source, source-sensitive, and source-specific findings are reported separately. Ranking is deterministic within comparable statistical families.
- Every result reports its unit, active/reference N, missingness, source mix, date/location precision, dataset identity, and applicable warnings.
- Generalized coordinates stay separate from source-provided coordinates and cannot enter exact-site analysis.
- Analysis Area Filters use mapped report points only. Chronology indexes, connectors, and segments do not enter geographic selection or any travel/proximity statistic.
- Crop-circle and animal-report context is descriptive only. No cross-domain proximity, authenticity, causation, incidence, risk, facility influence, travel, or trace-crossing claim is produced.

## Context projection seal

Projection release: `analysis-projections-v1-20260803`

| Artifact | Rows | Bytes | SHA-256 | Gzip bytes | Gzip SHA-256 |
|---|---:|---:|---|---:|---|
| Crop circles | 7,745 | 626,096 | `a0b1517ee4eec6c04ac87b405790d043dcc1a3cca762d2ef22fdd2ae99bb6d0b` | 141,809 | `baf4d59e0e5cb1811f5a952844362a3d477e5438b520d2606c4de71077ea0c12` |
| Animal reports | 1,177 | 104,423 | `6bf67a59d081de3c7e385d38e8a0ad0701c2cbbdb28a93528bcbd4650b447478` | 27,925 | `eb437b517887343194838b3e3a509b6a4b2a9bdcecb952da55dce949215529df` |

- Animal projection coverage: 518 mapped and 659 unmapped reports.
- Analysis manifest: 6,213 bytes; SHA-256 `794cc4a91c91d40c02709b063fb6e948ae7864b4d6ea3a7de3ed603297406832`.
- A fresh offline rebuild reproduced all five projection files byte-for-byte.

## Automated acceptance

- Python: 1,220 passed, 4 subtests passed, 1 dependency deprecation warning; 117.49 seconds.
- JavaScript: 14 of 14 suites passed.
- Source/generated parity: 13 of 13 changed web assets matched by SHA-256.
- `git diff --check`: passed.
- Tests cover tab state, snapshots and patches, disjoint baselines, stale generation/signature rejection, statistics, intervals, FDR, effect gates, source stability, deterministic ordering, generalized-coordinate exclusion, chronology exclusion, context toggles, preview/cancel/apply, point-only Area Filters, map preservation, and map-control restoration.

## Live browser acceptance

- First useful Analysis render: 1,626.6 ms on the reference desktop; worker computation 622.2 ms.
- Twenty uncached warm date-window recomputations: p95 696.8 ms; median 620.3 ms; minimum 553.0 ms; maximum 711.9 ms.
- Analysis activation and progressive chart rendering produced no main-thread task above 50 ms. The pre-existing shared full-filter refresh lifecycle is not represented as an Analysis-only task.
- No heavy analysis request occurred before first Analysis selection.
- Ten repeated Map Explorer/Analysis cycles preserved the same map element, viewport, playback cursor, and resource set with zero catalog, crop, animal, tile, or layer reloads.
- All 71 map-only controls stayed disabled and marked unavailable while Analysis was active, including after context-layer state synchronization; their prior state restored on return to Map Explorer.
- Filter preview apply/cancel, focus restoration, point-only Area Filter parity, and stale envelope rejection passed.
- Context sections followed their existing toggles without additional artifact or layer requests.
- Requested mobile portrait 390x844 and landscape 844x390 profiles had no document-level horizontal overflow; both tabs and Analysis content remained available.
- Light and dark themes passed. Reduced-motion mode resolved Analysis animation and transition durations to 0 seconds and restored normally.
- Browser console errors: 0. Page errors: 0. Unhandled rejections: 0.

## Frozen artifacts

### Complete static package

- Path: `static_bundle.zip`
- Bytes: 1,832,083,039
- Entries: 853
- SHA-256: `432002c1e5391b8564b2366c479faceb2f37659c9d428d96e35c7418b4d67712`
- Archive CRC validation: passed.

### Pages-only candidate

- Directory: `cloudflare_bundle_r2_analysis-v1-release_20260803`
- Files: 141
- Bytes: 56,165,537
- Tree SHA-256: `eae66787abf7174a71276388c0ad115860de453f1c374d5725fd1a23b9bb326b`
- Pages/R2 policy validation: passed with no optional-layer R2 payloads embedded in Pages.

Two independent deterministic archives of that directory are identical:

- `cloudflare_bundle_r2_analysis-v1-release_20260803-pages-a.zip`
- `cloudflare_bundle_r2_analysis-v1-release_20260803-pages-b.zip`
- Bytes each: 9,103,288
- SHA-256 each: `a5902f8cde5a808a58c66d9e6be108ac7889ae5f3b4bb67a4c9c299622439f94`

### Unchanged R2 release

- Uploads: 366
- Bytes: 913,767,840
- Tree SHA-256: `5cfd7f9e3158facdfc4d3de42fd388093fb8dfa2d617a9608a1d04127f4563a2`
- Existing immutable prefix: `releases/coordinated-reliability-v152-20260731`

## Clean-clone reproduction

- Verification clone: `.reproduction/analysis-v1-clean-clone-final`
- Verification-only commit: `fa84abd5285bad9ba90329afe13c6273b1a8d27f`
- The clone was clean before hydration and clean again after the generated candidate was validated and removed.
- Hydration from the sealed release contract reproduced the 141-file Pages candidate with 56,165,537 bytes and tree SHA-256 `eae66787abf7174a71276388c0ad115860de453f1c374d5725fd1a23b9bb326b`.
- The complete Pages/R2 separation validator passed in the clean clone.

## Release boundary

No deployment, R2 upload, production promotion, push, pull request, or primary-worktree commit was performed. Promotion requires separate authorization.

# UFO Timeline Analysis v2 Evidence Lab release receipt

Date: 2026-08-03  
Status: frozen local release candidate; not deployed or promoted  
Branch: `codex/analysis-tab-v1`  
Baseline: `920123ebebf996c69b12b031fa3796c8e3caf350`

## Product outcome

Analysis v2 replaces the count-heavy prototype with an evidence-first workspace while preserving the mounted Map Explorer, timeline, filters, results, context layers, selected map state, and playback cursor. The release contains seven document-flow sections with sticky scrollspy navigation: Overview, Time, Craft, Geography, Spatial Evidence, Sources & Quality, and Context.

The primary comparative outputs use balanced, disjoint references; common-support standardization; adjusted active/reference shares; percentage-point effects; Cochran-Mantel-Haenszel common odds ratios; deterministic bootstrap intervals; adjusted standardized residuals; false-discovery correction; and source/region sensitivity lanes. Full Catalog is descriptive-only and cannot emit p-values, q-values, or Pattern Finder findings.

The Evidence Lab includes:

- eligibility funnels, adjusted forest plots, and a guarded three-lane Pattern Finder;
- adaptive reporting-activity plots and supported recurring month-by-craft heatmaps;
- adjusted craft share, craft-by-era, and craft-by-geography comparisons;
- a sparse 6 x 12 Lambert cylindrical equal-area enrichment map and supported geography-by-era heatmap;
- point-based craft co-occurrence with cross-source and same-source sensitivity lanes;
- temporally qualified report-marker-to-facility-marker comparisons and an inactive-facility negative control;
- collection-bias, missingness, precision, and source-composition diagnostics;
- direct Include/View controls for crop circles and animal reports; and
- downloadable JSON and CSV evidence packages with estimator metadata, Ns, effects, uncertainty, suppression reasons, filter state, and release hashes.

Chronology connectors, trace styling, viewer bearing, inferred direction, generalized context markers, crop locality centroids, and unreviewed animal markers are excluded from kilometer-scale inference. All findings are labeled exploratory, associative, and non-causal.

## Context rehabilitation outcome

The crop and animal domains correctly fail closed for cross-domain proximity inference in this release:

- Crop circles: 7,745 records; 0 kilometer-eligible after joint coordinate, formation-date, and review gates.
- Animal reports: 1,177 records; 0 kilometer-eligible because the published locations are generalized or unmapped and the records remain unreviewed.
- Relationship reconciliation: 1,804 rows; 1,320 reconciled; 0 association-eligible after lineage, identifier, adjudication, mapping, and uncertainty gates.

The product therefore displays readiness matrices, eligible/excluded counts, and exact suppression reasons instead of publishing unsupported crop or animal proximity claims.

## Pinned Analysis v2 artifacts

Manifest release: `analysis-evidence-lab-v2-20260803`

| Artifact | Rows | SHA-256 |
|---|---:|---|
| UFO point neighbors | 42,575 pairs from 33,801 eligible points | `9de03bdcc8d285b0dedcbc659ba28b2126008b807a08c308a62e9551bee5d51d` |
| Facility analysis | 1,800 markers; 70 inferentially eligible | `8c7703b602b06e8ad5d86b3bb826b20a3685ecd1100cfd6ea8369652ff1e28e4` |
| Crop readiness | 7,745 | `6925c5c2dd9fbf3d3e31ab62a47076fd0ad1851140d397b4780b2dba7350cc39` |
| Animal readiness | 1,177 | `000616e91a24b2f0b92022631cbd46d9e878d2a41e6ad12c4a871bf256574bdf` |
| Relationship reconciliation | 1,804 | `49b1a2b5f3d859713192e0291b3bf19c852d91d38cb5c97828e3afc5985523db` |

The neighbor builder reads report points only. Its manifest explicitly records `chronologySegmentsRead: false`, `traceMetrics: false`, and `travelMetrics: false`.

## Performance evidence

Live-browser measurements against the 702,893-report catalog:

- first useful balanced core: 385-483 ms in the normal staged path;
- warm cached quick core: 21.9 ms;
- warm cached full inference: 142.3 ms;
- full adjusted inference in the background: 7.5-8.1 s while the quick core remained usable;
- cold on-demand Spatial Evidence: 3,066.5 ms; and
- repeated Map/Analysis switching: 118 total resources and 90 data/tile resources before and after, with identical map center, zoom, DOM identity, and playback cursor.

Analysis makes no heavy request before first selection. Core and spatial calculations run in workers, stale generations are rejected, and spatial artifacts load only when Spatial Evidence is requested.

## Browser acceptance

Verified in the live local reproduction at `http://127.0.0.1:8771/`:

- fresh load defaults to Map Explorer; Analysis becomes available only after the catalog is ready;
- sticky navigation remains within 2 px of the viewport safe position and owns exactly one `aria-current="location"` link;
- direct hashes, progressive chart realignment, keyboard navigation, reduced motion, and mobile horizontal link visibility work;
- desktop, narrow in-app pane, portrait, and landscape layouts have no document-level horizontal overflow;
- dark and light themes render correctly;
- crop and animal switches mutate shared state while Map Explorer is hidden and inert;
- Full Catalog emits no inferential fields or Pattern Finder candidates;
- returning to Map Explorer preserves viewport, layer state, filters, selection, and playback cursor with zero reload requests; and
- browser error log and visible alert count are zero.

## Test and integrity evidence

- Python: `1229 passed, 1 warning, 4 subtests passed`.
- JavaScript: all 16 suites passed; the spatial suite contains 16 additional point/facility/uncertainty subtests.
- Focused analysis view and shell tests include responsive active-link visibility and wide-heatmap containment.
- Reproduction contract: release `context-layer-quick-toggles-v1-20260803`; Pages tree `465002faa4145226bae6bffabbba03473e4722317ffa91606c36f7e5270638a2`; R2 tree `5cfd7f9e3158facdfc4d3de42fd388093fb8dfa2d617a9608a1d04127f4563a2`.
- Authoritative source overlay: 66 files; tree SHA-256 `f52d025da1f778c3a85ed0ef5f389548019774fa8758dec6a08eb4c93e650d35`.
- Source/generated parity is exact for the changed application files.
- Full offline local preview: 949 files; 8,016,588,302 bytes.

## Frozen Pages candidate

Directory: `cloudflare_bundle_r2_analysis-v2-frozen_20260803`

- 157 files; 62,438,802 bytes.
- Tree SHA-256: `567b882f2423642a507de6be225edeefc80a1575d9dbe61c4b4265b0908c39ab`.
- Exact release inventory: pass.
- Required release JSON: pass.
- Pages/R2 separation: pass; optional R2 payloads excluded.
- R2 upload manifest: 366 immutable uploads.

Deterministic archives:

- `cloudflare_bundle_r2_analysis-v2-frozen_20260803-pages-a.zip`
- `cloudflare_bundle_r2_analysis-v2-frozen_20260803-pages-b.zip`
- Each archive: 12,271,775 bytes.
- SHA-256: `7292b530045849d566a608e281db14b3143aad9d7e947a3b16a42bcc00cff407`.
- ZIP CRC/inventory: pass; both archives are byte-identical.

No deployment, Cloudflare upload, production promotion, or public release action was performed.

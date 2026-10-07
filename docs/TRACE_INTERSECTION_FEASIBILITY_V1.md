# Trace Intersection Feasibility v1

Date: 2026-08-19
Status: integrated local exploratory layer; not deployed or promoted

## Decision

This lane is worth continuing, but only as a **convergence-screening tool**. It is not ready to be described as a route, traffic, origin, destination, or travel-path analysis.

The prototype produces information that Area Select does not: it draws no report endpoints and no trace fan-out. It shows only cells containing proper interior connector crossings, permits raw-versus-opportunity-normalized comparison, exposes endpoint sensitivity, retains mixed and cross-craft evidence, and summarizes undirected connector axes by craft.

The strongest result is also the main warning: most apparent crossings are endpoint-sensitive. A cell must survive the conservative endpoint exclusion before it should receive serious attention.

## Scientific input contract

The pilot uses the pinned Analysis v2.3 qualified point-neighbor artifacts rather than the map's full chronological trace index:

- 33,801 qualified report points;
- source-provided coordinates, exact-day dates, medium/high recognized craft classifications, and coordinate-pile exclusions;
- 5,992 nondegenerate neighbor connectors within 25 km and 7 days; and
- Majestic and UFOCAT are the only qualified source collections in this pool.

These connectors are bounded report associations, not observed movement. The artifact explicitly records that observed travel, direction, origin/destination, causation, and chronology-trace parity are false.

## Intersection rules

A crossing is retained only when:

- two connectors do not share a report endpoint;
- their interiors properly cross;
- the crossing angle is at least 15 degrees; and
- the crossing lies outside the selected distance from both ends of both connectors.

The two published sensitivity profiles remove the first and last 1 km or 5 km of every connector. Cells use equal increments of longitude and sin(latitude), giving equal surface area at approximately 24,792 kmÂ², 2,497 kmÂ², 259 kmÂ² (100 miÂ²), and 25.9 kmÂ² (10 miÂ²). The fine grid is retained for local inspection: it has 121 crossing cells and 14 limited-or-better cells under the conservative profile, but no repeated-tier cells. That is useful resolution for exploration, not evidence that every fine cell is meaningful.

The qualified recognized-craft input contract excludes generic lights. The integrated control says this explicitly as **All recognized craft â€” lights excluded**, while preserving cross-craft, same-craft, and individual-craft views.

## Measured outcome

| Result | 1 km endpoint exclusion | 5 km endpoint exclusion |
|---|---:|---:|
| Proper interior crossings | 2,375 | 363 |
| Same-craft crossings | 562 | 78 |
| Different homotypic-craft crossings | 101 | 19 |
| Crossings involving at least one mixed-endpoint connector | 1,712 | 266 |
| Crossing cells at ~24,792 kmÂ² | 81 | 38 |
| Crossing cells at ~2,497 kmÂ² | 127 | 49 |
| Crossing cells at ~259 kmÂ² / 100 miÂ² | 205 | 77 |
| Crossing cells at ~25.9 kmÂ² / 10 miÂ² | 406 | 121 |
| Limited-or-better 10 miÂ² cells | 94 | 14 |

Only 15.3% of the 1 km crossings survive the 5 km exclusion. That makes the sensitivity comparison essential rather than optional.

Cross-craft information must remain visible. Under the conservative profile, 285 of 363 crossings (78.5%) are either between different homotypic craft connectors or involve a connector whose endpoint craft classifications differ. Restricting the analysis to same-craft connectors would discard most of the already-limited signal.

## Illustrative retained candidates

### Los Angeles regional cell

At the coarsest resolution, cell `43:63` is a repeated candidate centered near 34.608Â° N, 118.346Â° W:

- 265 crossings after the 1 km exclusion and 90 after 5 km (34.0% retained);
- 1.97Ã— opportunity-normalized lift in the conservative profile;
- 47 unique crossing connectors across nine five-year periods;
- 14.4% maximum contribution from any one connector; and
- 64 mixed-endpoint, 23 same-craft disc/disc, and 3 homotypic cross-craft crossings.

This is a useful review target because it combines support, temporal coverage, low single-connector dominance, and partial endpoint-buffer stability. It is still not evidence of traffic or a route.

### Paris-area perpendicular craft-axis example

At the 100 miÂ² resolution, cell `1260:694` is centered near 48.920Â° N, 2.387Â° E:

- 138 crossings after the 1 km exclusion and 37 after 5 km (26.8% retained);
- 2.12Ã— opportunity-normalized lift after the 5 km exclusion;
- 15 unique crossing connectors across two five-year periods;
- seven Eâ€“W disc/saucer connectors and four Nâ€“S triangle connectors in the conservative view; and
- four Eâ€“W sphere/orb connectors.

This demonstrates that the proposed triangle-versus-saucer axis question can be surfaced. It is not yet a strong finding: 35 of the 37 crossings involve mixed-endpoint craft connectors, none are between two differently typed homotypic connectors, and only five are same-five-year-period crossings. The pattern is a candidate for source-record inspection, not a route claim.

## Prototype product behavior

The standalone lab and integrated main-map layer provide:

- discovery (1 km) and conservative (5 km) endpoint profiles;
- four equal-area cell resolutions, including 100 miÂ² and 10 miÂ²;
- a default all-recognized-craft view that explicitly excludes lights, plus inclusive cross-craft, same-craft, and individual-craft scopes;
- all catalog years with no crossing-date separation limit by default, the current Timeline range, and optional 5-, 10-, 25-, and 50-year connector-date separation filters;
- opportunity-normalized lift, raw crossings, period coverage, same-craft, different-craft, mixed-endpoint, and selected-craft views;
- support tiers that suppress thin or connector-dominated cells by default;
- cell-level buffer-survival comparison;
- full connector craft signatures, so mixed endpoint classifications are not collapsed away;
- undirected Nâ€“S, NEâ€“SW, Eâ€“W, and NWâ€“SE connector-axis counts by craft;
- time coverage, crossing-angle, source-count, and connector-dominance diagnostics; and
- bounded crossing examples without drawing the underlying connector fan-out.

The main UFO Timeline controls now include a collapsed **Convergence cells** section beside Traces and Facility proximity. The layer is off and unloaded by default. When enabled, its default de-cluttering option temporarily hides ordinary traces and restores the prior trace mode when the layer is turned off. Military-base and research-site markers remain independent overlay evidence and render above the cells; a control opens the existing overlay section instead of duplicating or conflating facility controls. At broad zoom, 10 miÂ² hotspots use labeled centroid symbols. A ranked hotspot selector provides a dependable selection path, and **Zoom to selected cell** moves to the true equal-area footprint at zoom 7 or closer.

The in-browser review found no console warnings or errors, verified wide and compact layouts without document-level horizontal overflow, exercised both endpoint profiles and the 100 miÂ² craft view, and confirmed keyboard-focusable hotspot cells.

The integrated-map browser pass used the retained canonical payload in a production-like local preview. It verified lazy profile loading, 18 supported conservative 100 miÂ² cells, 14 supported conservative 10 miÂ² cells, the explicit lights-excluded all-craft scope, 5- versus 50-year separation filters, reversible ordinary-trace suppression, the facility-overlay shortcut, ranked cell selection, and the transition from broad-zoom centroid symbols to a true selected-cell footprint. The temporary preview-only runtime configuration was removed afterward.

## Why this is not ready for production inference

1. The connector itself is an association between nearby-in-space-and-time reports, not an observed path.
2. The 84.7% loss from the 1 km to 5 km profile shows that endpoint geometry manufactures much of the raw crossing volume.
3. The opportunity lift is a screening normalization, not a formal null model or significance test.
4. Qualified inputs currently cover only two source collections, so source composition and collection practices can dominate geography.
5. Mixed-endpoint connectors retain scarce information but can also encode classification inconsistency rather than two craft populations.
6. Undirected axes reveal alignment, not heading. They cannot establish where anything came from or went.

## Recommended next gate

Keep the integrated layer explicitly exploratory and do not promote or deploy it as an inferential feature until a research-validation pass:

1. ranks only cells stable across endpoint buffers and adjacent resolutions;
2. compares observed crossings with source-, era-, geography-, distance-, and craft-stratified bearing permutations;
3. adds leave-one-source-out and time-window sensitivity;
4. separates same-period crossings from long-term geometric recurrence;
5. reviews the small number of retained perpendicular craft-axis candidates against their underlying source records; and
6. promotes only robust cells to the main product, initially as aggregate cell summaries or axis rosesâ€”not endpoint fans or all-trace overlays.

## Reproduction and retention

Builder: `scripts/trace_intersection_feasibility.py`
Collection manifest: `webapp/static_public/data/trace_intersection_feasibility_v1/manifest.json`

```powershell
python scripts/trace_intersection_feasibility.py --endpoint-buffer-km 1 --output webapp/static_public/data/trace_intersection_feasibility_v1/strict_25km_7d_buffer1.json
python scripts/trace_intersection_feasibility.py --endpoint-buffer-km 5 --output webapp/static_public/data/trace_intersection_feasibility_v1/strict_25km_7d_buffer5.json
```

No canonical dataset was copied or modified. The two generated analysis payloads are about 4.2 MiB combined, are pinned by size and SHA-256 in the collection manifest, and can be rebuilt deterministically from the retained Analysis v2.3 artifacts. No deployment archive, backup tree, or additional release copy was created.

For the root-layout Pages checkout, rebuilding requires the original shared
analysis arrays. Supply explicit --manifest, --points, and --neighbors
paths from the preserved research workspace; the Pages release deliberately
does not copy those canonical arrays or rebuild this exploratory dataset.

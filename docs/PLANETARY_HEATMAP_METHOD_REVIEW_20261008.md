# Planetary heatmap method review — 2026-10-08

This is a bounded independent review of the local, unpublished planetary heatmap implementation. The canonical report catalogs, date roles, raw ephemeris atlas and their provenance are unchanged. The review covers `analysis_planetary.js`, comparison scheduling in `app.js` and `catalog_filter_worker.js`, and the heatmap renderer in `analysis_comparisons_view.js`.

## Settled model

- Nine supported bodies produce 9 × 12 zodiac cells and 9 × 3 motion cells. The 36 unordered body pairs produce five major aspect bands plus one outside-band cell per pair. Every row partitions the same domain's eligible report estimates; possible-count bounds need not sum to that denominator.
- Positions are apparent geocentric longitudes in the true ecliptic/equinox of date from the pinned MIT Astronomy Engine 2.1.19. Signs use equal 30-degree sectors with the declared Lahiri sidereal origin or tropical origin. Pairwise aspects use the smallest ecliptic-longitude separation; a common zodiac-origin shift cancels. Motion uses apparent tropical-longitude rate, independently of the zodiac display choice.
- The heatmap estimator is explicitly `planetary-heatmaps-v1-common-grid`. Date-only records use UTC noon as their descriptive estimate and the same 11 sample times over [civil date − 14 hours, civil date + 36 hours] for every body and pair. The grid is independent of a dropdown partner. Its sampled limits, with the existing longitude/rate margins, are neither formal continuous-time enclosures nor statistical confidence intervals.
- Verified UTC timestamps retain the existing provenance gate and use their verified instant. Unverified clock strings do not become UTC timestamps. Crop discovery/catalog and animal discovery/report/publication dates retain their recorded roles. Houses and local visibility remain unavailable without the required verified inputs.
- Calendar opportunity is calculated from actual UTC-noon states on Gregorian days in each represented year-month, clipped to the active date range. Each report domain and any requested category matrix retain their own report-count month weights. This controls calendar mix, not unknown observing effort or every source-selection bias.
- Cell-specific within-month contrast identifies the report weight in months where that cell's state is present on some, but not all, candidate days. Row-wide contrast is the union of varying months, not the maximum of cell-specific weights. Slow-body/era confounding remains visible; scanning many cells does not supply a significance claim.

## Display and filter contracts

The default color is report share minus matched calendar share in percentage points, centered on a neutral zero. Report share remains an alternative. No eligible denominator is unavailable, whereas a genuine zero share remains zero. A zero expected opportunity produces a null ratio rather than infinity. Clicked cells expose counts, shares, calendar-weighted counts, sampled stable/possible limits and cell-specific contrast. Drilldown selects `samplingMode: common_grid` so its bounds agree with the overview. Legacy adaptive views remain a separately identified estimator.

The heatmap is requested lazily and cached by the full filtered cohort plus its zodiac convention and aspect orb. Local domain/matrix/cell selection does not launch another worker query. Worker component identities preserve body/partner/sampling-mode distinctions for detailed comparisons; generation and cohort checks reject obsolete responses after rapid settings or filter changes. Statistical aggregates are computed for the current filter cohort rather than stored in the raw ephemeris atlas.

## Review findings and bounded verification

The review caught and the implementing agents corrected an outside-band upper-mask error, a rounded/raw verified-UTC aspect mismatch in common-grid drilldown, row-variation undercounting, non-finite custom-origin handling, and missing method/source fields in the visible policy. Renderer corrections include neutral zero and cell-specific contrast explanations.

After those corrections, an independent small three-domain cohort checked 162 matrix rows: every estimate partition and expected-count partition matched its denominator, and every cell satisfied lower ≤ estimate ≤ upper. A second comparison checked 2,106 cells against common-grid detailed comparisons in both zodiac systems, including Mercury and Venus station dates, tropical/sidereal ingress dates, verified UTC and excluded context/imprecise-date records. Counts, sampled bounds and expected counts agreed; non-finite custom offsets failed closed. These are implementation checks, not validation of an astrological effect. Full-cohort timing and browser interaction checks are owned by the implementation/integration work.

## Retention

This small review note is retained with the local implementation trail. It creates no dataset, atlas or release copy, no artifact over 100 MiB, and no deployment. The current validated deployment and existing rollback remain the retained releases.

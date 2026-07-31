# UFO Timeline Responsiveness Release

Release date: 2026-07-30

## Outcome

The production map now keeps playback, Results, timeline dragging, and large-window traces responsive without reducing the underlying event or trace data.

The release addresses the Airship Wave failure case directly:

- The 413-event Mystery Airship Wave plays at 16x without freezing.
- Playback advances through one animation-frame scheduler instead of timer catch-up loops.
- Results follow playback in a bounded 60-card window instead of rebuilding the complete result list.
- Playback trail drawing uses a bounded canvas layer.
- A measured step can automatically slow the effective playback rate before the browser becomes unresponsive.

Large windows now refine progressively:

- Moving a timeline handle produces a fast weighted-density preview while the pointer is down.
- The preview is visibly marked with an approximate count.
- Releasing the handle commits the exact range and exact trace-linked result set.
- Exact trace-linked visibility and large trace summaries are built in short batches that yield to the browser.
- Large trace sets render a bounded 2,600-cell viewport summary rather than inserting hundreds of thousands of individual map objects at once.
- Stale visibility, trace, filter-worker, and timeline generations are cancelled or discarded.

The existing product choices remain intact:

- Craft Type remains the default Color By mode.
- Only the `<=1 day` and `<=2 days` trace buckets are enabled by default.
- Exact results, source records, craft colors, trace metadata, Area Filter behavior, date controls, and legend filtering are preserved.

## Main implementation changes

### Playback and Results

- Added a reusable playback-performance helper with animation-frame scheduling, adaptive effective speed, bounded result windows, and progressive-work budgeting.
- Added Previous and Next controls for the bounded Results window.
- Kept Follow Results enabled by default; manual result scrolling disables following so playback does not fight the user.
- Cached result display ordering and reduced playback-driven Results refreshes.
- Replaced persistent playback polylines with a bounded canvas trail.

### Timeline and filtering

- Added a 140 ms live timeline-update cadence.
- Added 12,000-row weighted density previews, reduced to 5,000 rows on constrained devices.
- Kept the flexible ancient and partial date fields authoritative.
- Added worker-produced facet counts and typed-column worker storage for all 702,901 rows.
- Added generation-aware cancellation and stale-result rejection throughout filters and large-window work.
- Replaced duplicate/exclusion hot-path structures with typed indexes and bounded caches.

### Map, heatmap, and traces

- Added cached heatmap sprites and latitude indexing.
- Added automatic map-detail selection for large visible sets.
- Added progressive heatmap aggregation.
- Added progressive exact trace-linked visibility.
- Added progressive packed-trace aggregation with stale-context cancellation.
- Preserved exact endpoint metadata and Craft Type styling while using summary geometry for very large windows.

## Measured browser performance

### Airship Wave playback

| Environment | Window | Speed | Observed advancement | Playback step EWMA | Playback Results redraws | Result cards | Limited |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Local | 413 events | 16x | 84-180 events in about 6-8 seconds | 0.16-0.17 ms | 2-5 | 60 | No |
| Preview | 413 events | 16x | 81 events in 6 seconds | 0.19 ms | 2 | 60 | No |
| Production | 413 events | 16x | 55 events in 4 seconds | 0.12 ms | 1 | 60 | No |

Playback remained responsive in every run, and the final requested speed remained 16x.

### All Time

The production All Time interaction returned a stable refining state in **271 ms**. It then produced:

- **309,203** exact visible Results.
- **308,120** exact visible traces.
- Exact trace-linked visibility: **606.9 ms** active work over **1,488.1 ms** wall time in **178 batches**; maximum batch **17.4 ms**.
- Large trace refinement: **979.4 ms** active work over **1,636.2 ms** wall time in **193 batches**; maximum batch **16.0 ms**.
- **2,600** rendered trace-summary cells from **258,364** viewport source segments.
- **60** mounted Results cards.

The earlier implementation performed an approximately 970-1,152 ms exact UI block followed by an approximately 1,169 ms static-trace block. The new work is split across frames and exposes a stable progress state instead of freezing the page.

The preview deployment independently completed the same exact counts. Its slower cold run used 211 trace-linked visibility batches and 372 trace-refinement batches, confirming that the scheduler continues to yield under less favorable timing.

### Live timeline dragging

An actual pointer drag on the deployed preview produced a 12,000-row weighted density preview in **17.7 ms**. The live preview represented 333,589 filtered events and 309,009 mapped events; releasing the handle committed **308,694** exact trace-linked events for the selected range.

The approximate state is intentionally labeled and uses the `≈` prefix. It is never presented as the final exact count.

## Automated verification

- Complete Python suite: **787 passed**, **0 failed**
- Existing non-failing warning: one Starlette/httpx deprecation warning
- Focused webapp suite: **48 passed**
- Executable JavaScript behavior suites: **10 of 10 passed**
- JavaScript syntax checks: passed
- Authoritative/generated frontend parity: **11 of 11 files matched**
- Canonical static-payload readiness: passed
- Cloudflare bundle validation: **11 of 11 checks passed**
- Preview deployed frontend assets: **9 of 9 byte-for-byte matches**
- Production deployed frontend assets: **9 of 9 byte-for-byte matches**

The focused coverage includes adaptive playback timing, bounded Results windows, progressive work budgets, worker facet counts, final-generation filter behavior, default profiles, mobile layout requirements, date synchronization, Craft Type defaults, and short-gap trace defaults.

## Browser QA

The frozen release was exercised locally, on the immutable preview, and on the canonical production URL.

Verified:

- Ready / 100% startup.
- 702,901 total events and 580,785 mapped events.
- Default France Wave window: 770 visible mapped Results.
- Mystery Airship Wave: 413 visible mapped Results.
- Craft Type default coloring.
- Only the `<=1 day` and `<=2 days` trace buckets active by default.
- Follow Results enabled and 60 mounted Result cards.
- 16x playback remains interactive.
- All Time progressive exact visibility and trace refinement.
- Additive Disc/Saucer plus Light legend selection and legend reset.
- Rapid checkbox cycles reproduce the exact same 821 filtered event IDs and 770 visible mapped Results when returned to the original state.
- Full Start, End, Window Start, and Window End dates and their labels remain visible.
- Famous Flap labels include their month ranges and names.
- Desktop and 390 x 844 mobile layouts have no horizontal overflow.
- All four calendar controls are 44 x 44 px on mobile.
- Preview and production console warnings/errors: none.
- Preview and production network failures: none.
- No older frontend asset token was loaded.

Cloudflare injects its browser-insights beacon into served HTML. The nine directly addressable JavaScript and CSS files still match the frozen files byte-for-byte, and browser inspection confirms that the deployed HTML references the v149 asset token.

## Known remaining performance frontier

Cold startup is still dominated by construction of the 702,901-row browser catalog. The measured dominant catalog-build step was approximately 6.9-7.2 seconds; first usable render occurred in approximately 9.9-11.5 seconds, and the cold production run reached Ready in 18.7 seconds.

This release concentrates on the user-blocking interaction failures: playback, live timeline movement, Results rendering, filters, heatmap aggregation, and very large trace windows. A later startup-focused release can move more catalog construction off the main thread or load columns on demand without weakening the exact interaction improvements delivered here.

## Release evidence

- Authoritative checkout: `C:\Users\jarod\Desktop\UFO Timeline map tool`
- Git metadata: absent
- Authoritative frontend: `webapp/static_public`
- Generated frontend: `static_bundle`
- Asset version: `2026-07-30-responsiveness-v149`
- Previous production deployment: `e69c19e0-2e52-403e-b820-ed2d10b12f9b`
- Frozen Pages folder: `cloudflare_bundle_r2_responsiveness-v149_20260730`
- Frozen inventory: **127 files**, **54,642,744 bytes**
- Frozen tree-hash algorithm: SHA-256 of ordinal-sorted `path<TAB>bytes<TAB>file-sha256<LF>` rows
- Frozen tree hash before preview: `1a027062e02de21fc0b8b1bd21ce1b4b68211566e891fca212745a512454ee46`
- Frozen tree hash after preview: `1a027062e02de21fc0b8b1bd21ce1b4b68211566e891fca212745a512454ee46`
- Frozen tree hash after production: `1a027062e02de21fc0b8b1bd21ce1b4b68211566e891fca212745a512454ee46`
- Preview deployment: `741ddf26-4b8a-4504-b000-528cd7a0de40`
- Preview URL: `https://741ddf26.ufo-timeline.pages.dev`
- Preview alias: `https://responsiveness-v149.ufo-timeline.pages.dev`
- Production deployment: `d809ab16-62e9-4a84-8a23-cc7289d1790f`
- Immutable production URL: `https://d809ab16.ufo-timeline.pages.dev`
- Canonical production URL: `https://ufo-timeline.pages.dev`
- Production upload reused the preview artifact: **0 files uploaded**, **126 files already uploaded**
- Existing immutable R2 prefix reused without mutation: `releases/airship-wave-v148-20260730`
- Frozen app.js SHA-256: `cd966cea1cbab3b20469ea3f24ceddfcefda29051cd0c7d245bd44a85056eec4`
- Frozen app-config SHA-256: `b1a8b02fca8111de583d6881c5c2d86c285c77edf22e3194f70ccc6b07e77a1c`

The same frozen folder was deployed to preview and production. The previous v148 production deployment and frozen v148 folder remain available for rollback.

## Key source hashes

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `webapp/static_public/app.js` | 1,036,916 | `cd966cea1cbab3b20469ea3f24ceddfcefda29051cd0c7d245bd44a85056eec4` |
| `webapp/static_public/index.html` | 69,776 | `94cca09655681d819add81ff6f9c26cb20211d0ff93b05011ae96c5eb040dc4f` |
| `webapp/static_public/styles.css` | 129,071 | `3f3761a9ea26439cb64f2d47ef69593e9075c575cf96ba66b4e5d02c80188a83` |
| `webapp/static_public/catalog_filter_worker.js` | 17,006 | `dd3359364d0a21b6d8c841e194e6972a19d491afa17e66cb6b10aa06720c4cb1` |
| `webapp/static_public/playback_performance.js` | 4,689 | `d2a20b082d2c4608dc9b859fa3c2201b11277bf81922c9fbb66793689516bf52` |
| `scripts/build_startup_profile_artifacts.py` | 13,659 | `f02bf0e4c4501190cf3e5a170db805170f172c894d7eb95a83df6c9f79c1b78c` |
| `tests/test_playback_performance.mjs` | 2,892 | `945d1ee06d913456f9fe8ed2626f5c696616a31f49deede4c86c280669ec9274` |

Release status: **production deployed and verified**.

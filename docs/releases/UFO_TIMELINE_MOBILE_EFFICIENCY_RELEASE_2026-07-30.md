# UFO Timeline Mobile Efficiency Release

Release date: 2026-07-30

## Outcome

This release removes the largest avoidable browser-memory multipliers while preserving the complete 703,018-event catalog, the existing R2 payload, and all current map features.

In a controlled cold-start comparison at a true 390-by-844 CSS-pixel viewport with cache disabled and identical local data:

| Measurement | v143 before | v144 after | Change |
| --- | ---: | ---: | ---: |
| Renderer JavaScript heap used | 672,109,960 bytes | 173,988,508 bytes | **-498,121,452 bytes (-74.1%)** |
| Browser heap indicator (`performance.memory.usedJSHeapSize`) | 1,076,211,940 bytes | 308,670,515 bytes | **-767,541,425 bytes (-71.3%)** |
| Time to Ready | 6,517.5 ms | 7,063.0 ms | +545.5 ms |
| Time to first usable render | 6,243.4 ms | 6,811.0 ms | +567.6 ms |
| Timeline playback construction/sort | 583.1 ms | 397.3 ms | **-185.8 ms (-31.9%)** |

The modest cold-build cost is intentional: v144 interns repeated catalog strings while each shard is ingested, then releases the temporary pool. This trades about half a second in the controlled cold run for roughly 500 MB less live renderer heap, directly addressing mobile tab termination and severe garbage-collection pressure.

## Implementation

### Compact canonical event records

- Replaced in-place property deletion with fresh, consistently shaped runtime records. In-place deletion had pushed V8 objects into memory-expensive dictionary mode.
- Released 5,624,144 unused summary-property instances across 703,018 events.
- Reused one frozen fallback playback key for 570,320 events.
- Compacted 132,698 non-default playback keys by dropping their redundant event-ID element.
- Interned the 13 retained string fields while ingesting shards:
  - 8,248,843 candidate string references were represented by 295,615 unique pooled values in the measured catalog.
  - The temporary interning pool is cleared after ingestion.

### Typed indexes and worker storage

- Replaced the 580,802-entry string-keyed packed-point `Map` with a typed open-addressing index:
  - 1,048,576 slots
  - 12,582,912 bytes
  - zero fallback IDs for the canonical catalog
- Replaced 703,018 full JavaScript objects in the catalog facet worker with typed column chunks:
  - 282 chunks
  - 19,684,504 typed bytes
  - compact dictionaries for source, type, visual group, craft type, location precision, and date precision
  - zero string event IDs for the canonical catalog
- Retained string-ID fallbacks for noncanonical or unsafe integer IDs.

### Duplicate and transient-state removal

- The legacy event-to-chunk lookup is no longer built for canonical web artifacts; final entry count is zero.
- Parsed summary-shard arrays are released immediately after their records are ingested; final cached-shard count is zero.
- Summary fetching now uses a bounded four-shard ordered prefetch window instead of allowing completed parsed shards to accumulate.
- Added the worker/index/storage mode, byte counts, released-cache counts, filter generation, and stale-result counters to the existing debug snapshot.

## Preserved product behavior

The release retains:

- Craft Type as the default color mode.
- Additive interactive legend event selection and legend reset.
- Full, labeled Start Date and End Date fields with calendar buttons.
- Date-first, month-bearing Famous Flaps labels.
- Partial dates, year `0000`, leap days, invalid-range feedback, and four-field synchronization.
- Points, Clusters, Heatmap, playback, static traces, Full Event View, overlays, filters, and timeline controls.
- Chronological Neighborhood direction/depth controls, outside-area endpoint markers, two-tone craft traces, and the exploratory-adjacency disclaimer.

## Automated verification

- Complete Python suite: **772 passed**, **0 failed**
- Existing non-failing warning: one Starlette/httpx deprecation warning
- Executable JavaScript suites: **9 of 9 passed**
- JavaScript syntax checks passed for authoritative and generated app/worker files.
- Authoritative/generated parity passed for the synchronized frontend.
- Cloudflare bundle validation: **11 of 11 checks passed**

The Windows test environment required the `tzdata` runtime package so the existing historical-timezone chronology tests could execute; after restoring that test dependency, the complete suite passed.

## Browser QA

Local, immutable preview, immutable production, and canonical production were checked at desktop and mobile sizes.

Verified:

- Ready / 100% startup with canonical artifacts and packed points reporting `ready`.
- No captured console exceptions or errors.
- Craft Type default and v144 asset token.
- Full dates and their Start/End labels.
- 44-pixel calendar and Famous Flaps controls at 390 pixels wide.
- Full visible mobile date values and no horizontal overflow.
- All nine date-first descriptive Famous Flaps labels, including Belgium Wave and Phoenix Lights.
- Legend Disc/Saucer-only selection, additive Sphere/Orb selection, and reset.
- All four precision/date checkbox combinations plus rapid-toggle final-state parity; returning to the default combination reproduced the exact event-ID hash.
- Manual partial dates, year `0000`, native-picker dates, leap day, invalid-range feedback, and restored preset synchronization.
- Points, Clusters, Heatmap, playback stepping, Full Event View, playback traces, and static traces.
- Static trace coloring returned to the Craft-type explanation after mode switching without color leakage.
- A trace-intersection neighborhood whose two endpoints were both outside the selected rectangle:
  - depth 1 displayed both endpoint markers and the mixed Disc/Saucer to Cigar/Cylinder trace;
  - depth 4 reused the same region and expanded to 56 segments / 64 events;
  - measured warm depth-4 traversal was approximately 1 ms.

Observed canonical-production cold startup at 390 by 844 was approximately:

- startup-profile preview: 0.586 s
- first usable render: 10.882 s
- Ready: 12.105 s
- renderer JavaScript heap used: 237,692,904 bytes

The production app and worker returned HTTP 200 and matched the frozen files byte-for-byte on the preview deployment, immutable production deployment, and canonical production domain.

## Release evidence

- Authoritative checkout: `C:\Users\jarod\Desktop\UFO Timeline map tool`
- Git metadata: absent
- Authoritative frontend: `webapp/static_public`
- Generated frontend: `static_bundle`
- Asset version: `2026-07-30-mobile-efficiency-v144`
- Previous production deployment: `59dad72d-f83a-4212-8177-b07f8ddc30cc`
- Frozen folder: `cloudflare_bundle_r2_mobile-efficiency-v144_20260730`
- Frozen inventory: **104 files**, **53,444,486 bytes**
- Frozen tree-hash algorithm: SHA-256 of ordinal-sorted `path<TAB>bytes<TAB>file-sha256<LF>` rows
- Frozen tree hash: `c3ee5e59c1ee82dc8a08ea074afd90878f5ca74e61c7af48c726774c396cd8d4`
- Preview deployment: `7299adf2-1a6d-4c3d-b2b0-03704babf68a`
- Preview URL: `https://7299adf2.ufo-timeline.pages.dev`
- Preview alias: `https://mobile-efficiency-v144.ufo-timeline.pages.dev`
- Production deployment: `8e0345db-2e97-4a61-bd18-03677b33cc2c`
- Immutable production URL: `https://8e0345db.ufo-timeline.pages.dev`
- Canonical production URL: `https://ufo-timeline.pages.dev`
- Production Pages upload reused the preview artifact: **0 files uploaded**
- R2 uploads performed: **0**
- Existing R2 manifest retained: **366 rows**, **913,862,841 bytes**

### Final file hashes

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `webapp/static_public/app.js` | 947,790 | `2016df732d9be74a5c7a1cc78d23e555073f1314cab3056d8eb84490a8cc9be7` |
| `webapp/static_public/catalog_filter_worker.js` | 16,339 | `fb165532548f20cbddcdf6132d1a1c118d55eb8e42dfe82d028c84b8bcd756fa` |
| `webapp/static/packed-points-utils.mjs` | 23,338 | `4059339a5169fcbdf5e3e608eb101d2860d0ef870ba2eb830c3672ff5a4084ad` |
| `webapp/static_public/index.html` | 69,527 | `51942b2de66a7b21a8c55e977177fb65b425dad21aec9a79ed763e28d7aa574e` |
| `static_bundle/data/app_config.json` | 2,521 | `372d856db99fdd23f9a4b3863cfd31f54a36c9f0d829308f2cb18f44168b467c` |

## Genuine remaining limitation

This pass deliberately did not change the canonical payload or R2 schema. The initial browser session still downloads and parses the complete catalog: the compressed summary shards alone total about 50.4 MB, in addition to the packed point and trace indexes. Network-bound cold startup therefore remains substantial even though the live-memory crash risk is dramatically lower. A future reduction in cold network time would require a separate staged-catalog/payload release rather than another in-memory cleanup.

Release status: **production deployed and verified**.

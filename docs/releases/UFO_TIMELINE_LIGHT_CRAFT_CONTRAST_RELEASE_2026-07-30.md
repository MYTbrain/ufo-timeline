# UFO Timeline Light Craft Contrast Release

Release date: 2026-07-30

## Outcome

The canonical `Light` craft-type color is now electric violet `#b517ff`, replacing the pale yellow `#fef08a`.

The new hue is visibly distinct against both the dark legend and light map, and it separates cleanly from the common cyan, green, orange, and yellow craft colors. Because all craft-colored markers and traces use the shared craft-style resolver, this change applies consistently to:

- Event markers and legend controls
- Static and playback traces
- Area Filter and Chronological Neighborhood traces
- Matching, mixed-endpoint, wrapped, and aggregate craft traces

Mixed traces retain the established two-tone rule. A same-day Sphere/orb-to-Light trace, for example, now transitions from green into electric violet at the midpoint instead of fading into a hard-to-see pale yellow half.

## Implementation

- Changed the canonical `light` palette entry in `trace_neighborhood.js` to `#b517ff`.
- Preserved `Unknown` gray and every other craft-type color.
- Added executable coverage for the exact Light color and mixed Light/Disc endpoint styling.
- Advanced the frontend asset version to `2026-07-30-light-craft-contrast-v146`.
- Synchronized the authoritative frontend into `static_bundle`.
- Preserved the default Craft Type color mode and the default `<=1 day` plus `<=2 days` trace loadout.

## Automated verification

- Complete Python suite: **773 passed**, **0 failed**
- Existing non-failing warning: one Starlette/httpx deprecation warning
- Executable JavaScript suites: **9 of 9 passed**
- JavaScript syntax checks: **14 files passed**
- Authoritative/generated/frozen frontend parity: passed
- Cloudflare bundle validation: **11 of 11 checks passed**

## Browser QA

Local, immutable preview, immutable production, and canonical production were checked at desktop and mobile sizes.

Verified:

- Ready / 100% startup.
- The Light legend swatch is `#b517ff`.
- Craft Type remains the default color mode.
- Only the `<=1 day` and `<=2 days` trace buckets are active by default.
- The Light legend button still supports show-only selection, additive selection, and reset behavior.
- The Light legend button is a 44 by 44 CSS-pixel touch target at 390 CSS pixels.
- No page-level horizontal overflow at 390 CSS pixels.
- Start and End date values remain fully readable on mobile.
- No captured console warnings or errors.

Exact production data check:

- Date: `1954-10-10`
- Trace: `4097179308907573->4159503471518869`
- Earlier endpoint: Sphere / orb, `#22c55e`
- Later endpoint: Light, `#b517ff`
- Gap: 0 days
- Neighborhood: hop 1, both directions
- Result: two distinct trace halves with `continuous: false`

Representative startup timings:

| Environment | First usable | Ready |
| --- | ---: | ---: |
| Local | 6,623.5 ms | 6,856.8 ms |
| Preview | 9,548.2 ms | 10,665.7 ms |
| Immutable production | 9,246.8 ms | 10,498.7 ms |
| Canonical production | 9,038.0 ms | 9,814.3 ms |

The focused preview neighborhood build completed in 0.5 ms and its depth-1 traversal completed in 1.4 ms.

## Release evidence

- Authoritative checkout: `C:\Users\jarod\Desktop\UFO Timeline map tool`
- Git metadata: absent
- Authoritative frontend: `webapp/static_public`
- Generated frontend: `static_bundle`
- Asset version: `2026-07-30-light-craft-contrast-v146`
- Previous production deployment: `466365be-bb06-4667-a1e6-e783c72a1f7d`
- Frozen folder: `cloudflare_bundle_r2_light-craft-contrast-v146_20260730`
- Frozen inventory: **104 files**, **53,444,674 bytes**
- Frozen tree-hash algorithm: SHA-256 of ordinal-sorted `path<TAB>bytes<TAB>file-sha256<LF>` rows
- Frozen tree hash before preview: `fb6816ef795835a0791b0bb57c474ec007391c5c5337db76f01785ad4bc71c8a`
- Frozen tree hash after preview: `fb6816ef795835a0791b0bb57c474ec007391c5c5337db76f01785ad4bc71c8a`
- Frozen tree hash after production: `fb6816ef795835a0791b0bb57c474ec007391c5c5337db76f01785ad4bc71c8a`
- Preview deployment: `90108fb5-c4bd-4e50-898b-f88de84d2093`
- Preview URL: `https://90108fb5.ufo-timeline.pages.dev`
- Preview alias: `https://light-craft-contrast-v146.ufo-timeline.pages.dev`
- Production deployment: `10ddf5d1-aee0-4843-ab79-f841ab02bd5d`
- Immutable production URL: `https://10ddf5d1.ufo-timeline.pages.dev`
- Canonical production URL: `https://ufo-timeline.pages.dev`
- Production Pages upload reused the preview artifact: **0 files uploaded**
- R2 uploads performed: **0**
- Existing R2 manifest retained: **366 rows**, **913,862,841 bytes**

The immutable preview, immutable production, and canonical production copies of `trace_neighborhood.js` match the frozen file byte-for-byte. The deployed `app.js` and deployment-profile `app_config.json` were also verified by SHA-256.

### Final source hashes

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `webapp/static_public/app.js` | 947,904 | `29b224dcfebf7a3f407017a87a5d8268db3f8d5b6ab24c06da190928326700df` |
| `webapp/static_public/index.html` | 69,514 | `311010cf67e2862411a941ee57cac47f57a7751204f8af9de29466b5cbda5693` |
| `webapp/static_public/styles.css` | 127,906 | `a0f7b7785f81938a6f612ebb109ee695ae21450d0356a9cd25a2bfd881d94758` |
| `webapp/static_public/trace_neighborhood.js` | 21,245 | `7bb346bd72b28b0fb998ebe24ed59bc9fdaa84ae20bd2653532d8aee6400ec66` |
| `static_bundle/data/app_config.json` | 2,524 | `02ecc8032989993e4702bdc4ff0475cf0f3a121fe5a43002b6d174be94c65eeb` |
| Frozen/deployed `data/app_config.json` | 3,605 | `24a7cec7d6865c30fa7ea8a4ba926cf95f47018a90f5ea8af9269e234e307958` |

Release status: **production deployed and verified**.

# UFO Timeline Short-Gap Trace Default Release

Release date: 2026-07-30

## Outcome

The default trace loadout now enables only:

- `≤1 day`
- `≤2 days`

The `≤7 days`, `≤30 days`, and `>30 days` buckets remain available as additive opt-in controls. Initial load and Reset Map both restore the same two-bucket default.

## Implementation

- Consolidated startup and reset behavior behind `defaultTraceBucketVisibilityState()`.
- Synchronized the pre-script button classes and `aria-pressed` values with the runtime state.
- Added the active trace bucket keys and visibility map to the existing debug snapshot.
- Added a regression contract covering authoritative/generated source, initial markup, startup state, Reset Map, and mobile stacking.
- Corrected the mobile layer order so an expanded map-control panel remains above the floating legend. This prevents the legend from intercepting touches intended for Reset Map.
- Preserved Craft Type as the default color mode and preserved all longer-gap trace options.

## Automated verification

- Complete Python suite: **773 passed**, **0 failed**
- Existing non-failing warning: one Starlette/httpx deprecation warning
- Executable JavaScript suites: **9 of 9 passed**
- JavaScript syntax checks: **14 files passed**
- Authoritative/generated frontend parity: passed
- Cloudflare bundle validation: **11 of 11 checks passed**

## Browser QA

Local, immutable preview, immutable production, and canonical production were checked at desktop and mobile sizes.

Verified:

- Ready / 100% startup.
- Craft Type remains the default.
- Only `≤1 day` and `≤2 days` are active on first load.
- Selecting `≤7 days` adds it without disabling either short-gap bucket.
- Reset Map restores exactly `≤1 day` and `≤2 days`.
- Trace status reports the same active buckets as the buttons.
- The mobile Reset Map touch target is the topmost hit target rather than the legend.
- No page-level horizontal overflow at 390 CSS pixels.
- Start/End date values and labels remain present and readable.
- No captured console errors.

## Release evidence

- Authoritative checkout: `C:\Users\jarod\Desktop\UFO Timeline map tool`
- Git metadata: absent
- Authoritative frontend: `webapp/static_public`
- Generated frontend: `static_bundle`
- Asset version: `2026-07-30-short-gap-default-v145`
- Previous production deployment: `8e0345db-2e97-4a61-bd18-03677b33cc2c`
- Frozen folder: `cloudflare_bundle_r2_short-gap-default-v145_20260730`
- Frozen inventory: **104 files**, **53,444,653 bytes**
- Frozen tree-hash algorithm: SHA-256 of ordinal-sorted `path<TAB>bytes<TAB>file-sha256<LF>` rows
- Frozen tree hash: `9a6370439ba3b0762db23d44a976c783e825441f96b18ce5a0d523b833752d7f`
- Preview deployment: `c1d6b925-aea1-4a01-b605-b50fd0087edd`
- Preview URL: `https://c1d6b925.ufo-timeline.pages.dev`
- Preview alias: `https://short-gap-default-v145.ufo-timeline.pages.dev`
- Production deployment: `466365be-bb06-4667-a1e6-e783c72a1f7d`
- Immutable production URL: `https://466365be.ufo-timeline.pages.dev`
- Canonical production URL: `https://ufo-timeline.pages.dev`
- Production Pages upload reused the preview artifact: **0 files uploaded**
- R2 uploads performed: **0**
- Existing R2 manifest retained: **366 rows**, **913,862,841 bytes**

The immutable production and canonical production app, styles, and config match the frozen files byte-for-byte. After removing Cloudflare's configured Pages Analytics injection, production `index.html` also matches the frozen file exactly.

### Final source hashes

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `webapp/static_public/app.js` | 947,904 | `29b224dcfebf7a3f407017a87a5d8268db3f8d5b6ab24c06da190928326700df` |
| `webapp/static_public/index.html` | 69,499 | `6accf8f1ec2ef0d2081724a65134fc9c8768c9a1007fb3905e1023061be6f317` |
| `webapp/static_public/styles.css` | 127,906 | `a0f7b7785f81938a6f612ebb109ee695ae21450d0356a9cd25a2bfd881d94758` |
| `static_bundle/data/app_config.json` | 2,521 | `63d310c97b99be1cac9302e661a3e9fa4808c18315b472d4c9f56cd035a02277` |

Release status: **production deployed and verified**.

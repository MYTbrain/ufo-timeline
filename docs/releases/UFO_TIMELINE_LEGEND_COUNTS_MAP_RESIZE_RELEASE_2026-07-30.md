# UFO Timeline Legend Counts and Map Resize Release

Release date: 2026-07-30

## Outcome

The production map legend now shows the current filtered count beside every
Craft Type. The counts remain visible while legend buttons are used to isolate,
add, or reset craft selections, and each count has matching accessible text.
Singular values are announced correctly, for example `1 event`.

Desktop users can now drag the new horizontal handle below the map to create
more vertical map space. The map, legend, and default map-control layout grow
with the surface. The measured pre-feature map height is enforced as a hard
minimum, so the control can enlarge the map but cannot make it smaller than its
existing layout.

The resize handle supports:

- Pointer and touch-capable desktop dragging.
- Arrow Up and Arrow Down adjustments.
- Page Up and Page Down larger adjustments.
- Home to restore the measured default and End to use the maximum.
- Double-click to restore the measured default.
- A persisted expanded height across reloads.
- Accessible separator semantics, value text, focus treatment, and keyboard
  focus after pointer use.

The resize control is intentionally unavailable at mobile and narrow-tablet
breakpoints, where the existing responsive map height remains authoritative.

## Craft counts verified in the default France Wave window

| Craft Type | Count |
| --- | ---: |
| Disc / saucer | 268 |
| Sphere / orb | 120 |
| Triangle | 5 |
| Cigar / cylinder | 82 |
| Oval / egg | 81 |
| Chevron / boomerang | 4 |
| Rectangle / box | 4 |
| Fireball / meteor-like | 7 |
| Formation | 10 |
| Cone | 5 |
| Light | 234 |
| Unknown | 1 |

These total 821 filtered events. The default window has 770 visible mapped
Results.

## Browser QA

The release was exercised locally, on the immutable preview, and on the
canonical production URL.

Verified:

- Ready / 100% startup.
- 702,901 total events and 580,785 mapped events.
- 770 default visible mapped Results.
- Craft Type remains the default Color By mode.
- Only the `<=1 day` and `<=2 days` trace buckets are active by default.
- All 12 Craft Type rows show counts that exactly match the worker-produced
  filtered count map.
- Disc/Saucer isolation, additive Light selection, and legend Reset preserve
  the displayed counts.
- Pointer resizing increases the map and the available legend/control height.
- Dragging upward past the measured default clamps at the default.
- Keyboard adjustment, Home reset, double-click reset, and reload persistence
  work.
- Enlarging the map can expose the full legend without internal scrolling.
- At 390 x 844, the resize control is hidden, all four date values and labels
  remain readable, Craft Type counts remain available when the legend is
  expanded, and there is no horizontal overflow.
- Preview and production console warnings/errors: none.
- Preview and production failed resources: none.
- No v150 frontend token was loaded by final production.
- Preview and production frontend assets: 9 of 9 byte-for-byte matches.

## Automated verification

- Complete Python suite: **788 passed**, **0 failed**
- Existing non-failing warning: one Starlette/httpx deprecation warning
- Focused webapp suite: **49 passed**
- Executable JavaScript behavior suites: **10 of 10 passed**
- JavaScript syntax checks: passed
- Authoritative/generated frontend parity: **11 of 11 files matched**
- Canonical static-payload readiness: passed
- Static loadout readiness: passed
- Cloudflare bundle validation: **11 of 11 checks passed**

## Release evidence

- Authoritative checkout: `C:\Users\jarod\Desktop\UFO Timeline map tool`
- Git metadata: absent
- Authoritative frontend: `webapp/static_public`
- Generated frontend: `static_bundle`
- Asset version: `2026-07-30-legend-counts-map-resize-v151`
- Baseline production deployment: `d809ab16-62e9-4a84-8a23-cc7289d1790f`
- Final preview deployment: `e5b42eb1-5eea-42c2-b30c-12c87678a5bf`
- Final preview URL: `https://e5b42eb1.ufo-timeline.pages.dev`
- Final production deployment: `ba4f800d-b75b-4169-9857-51dd6b8988e2`
- Immutable production URL: `https://ba4f800d.ufo-timeline.pages.dev`
- Canonical production URL: `https://ufo-timeline.pages.dev`
- Frozen Pages folder:
  `cloudflare_bundle_r2_legend-counts-map-resize-v151_20260730`
- Frozen inventory: **127 files**, **54,661,153 bytes**
- Frozen tree-hash algorithm: SHA-256 of ordinal-sorted
  `path<TAB>bytes<TAB>file-sha256<LF>` rows
- Frozen tree hash before preview:
  `a03c5c7925bf8cd24be836e7ffa4a464d215f88a5fc6e5875664617855397a87`
- Frozen tree hash after preview:
  `a03c5c7925bf8cd24be836e7ffa4a464d215f88a5fc6e5875664617855397a87`
- Frozen tree hash after production:
  `a03c5c7925bf8cd24be836e7ffa4a464d215f88a5fc6e5875664617855397a87`
- Production upload reused the preview artifact: **0 files uploaded**, **126
  files already uploaded**
- Existing immutable R2 prefix reused without mutation:
  `releases/airship-wave-v148-20260730`
- Frozen `app.js` SHA-256:
  `e3a2c36ac3061b165c96baa4e976764d315aa72f4d7f1b34636791e370593de6`
- Frozen `index.html` SHA-256:
  `72c34818f919af902a187b8b373724409015b3ecf914d09bbf65559d08756f64`
- Frozen `styles.css` SHA-256:
  `6c7ed41df0e3f49246714dbe99b9af911fd2489cfff178d06327c36c1944fbe8`
- Frozen app-config SHA-256:
  `bcd1f4d9c144b675dd56dde36dfd87af04100e854c066540ddfc43e913acbf3a`

The same frozen v151 folder was deployed to preview and production. The v149
baseline and the fully tested v150 intermediate deployment remain available
for rollback.

Release status: **production deployed and verified**.

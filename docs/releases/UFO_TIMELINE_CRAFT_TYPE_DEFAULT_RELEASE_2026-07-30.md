# UFO Timeline Craft Type Default Release — 2026-07-30

## Outcome

The default color mode is now **Craft Type** on a clean load and after **Reset Map**.

The release changes all three default-entry paths together:

- the selected option in the authoritative HTML;
- the initial application state;
- the reset-view default state.

Switching to another color mode during a session still works normally.

## Implementation

- Authoritative source: `webapp/static_public`
- Generated frontend: `static_bundle`
- Default constant: `DEFAULT_COLOR_MODE = "craft_type"`
- Static asset version: `2026-07-30-craft-type-default-v141`
- Canonical payload and R2 objects: unchanged

Regression checks assert that:

- Craft Type is the one selected HTML option;
- Single Color is not selected;
- both JavaScript default-state paths use the shared constant;
- the source and generated frontend remain byte-identical.

## Automated verification

- Focused Python regression tests: **3 passed**
- Complete Python suite: **770 passed**, **0 failed**
- Existing non-failing warning: one Starlette/httpx deprecation warning
- Executable Node behavior suites: **7 of 7 passed**
- Source/generated parity: **6 of 6 frontend files matched**
- Cloudflare bundle validation: **11 of 11 checks passed**

## Browser QA

Local, preview, and production checks confirmed:

- startup reaches **Ready / 100%** with no startup error;
- `Color By` initially reads **Craft Type**;
- the legend shows **Craft-type traces** and no chronology fallback;
- trace status reports earlier/later endpoint craft coloring;
- selecting Single Color and pressing **Reset Map** restores Craft Type;
- desktop and 390-by-844 mobile layouts have zero horizontal overflow;
- mobile start/end dates remain fully readable;
- zero captured failed network requests;
- zero console warnings or errors.

The first canonical production navigation reused the browser's previously cached v140 document while the uncached configuration already reported v141. A cache-disabled clean navigation returned the complete v141 shell and passed every production check.

## Final file evidence

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `webapp/static_public/index.html` | 68,910 | `e219c4fbea26c771b6d8f632238554cf8c461a36c0978a757068bdf94e0e0cf8` |
| `webapp/static_public/app.js` | 913,523 | `f7a91aff1e936830320ee7b0542ed1bedfc720765006d717f95de8aa862544ce` |
| `static_bundle/data/app_config.json` | 2,522 | `87415eec90c44600c076eb1f119a508b4b3e7a7bfa21bbe1ce86402b1e252fc1` |
| `tests/test_webapp.py` | 97,626 | `96f61297906c1fe2695865b1e96b8c882bdeef24e5ea6a6e8f97e63bd205cf14` |

`static_bundle/index.html` and `static_bundle/app.js` match their authoritative source counterparts byte-for-byte.

## Release

- Previous production deployment: `264cc621-7c86-46bc-b60f-3c1813daa71c`
- Frozen folder: `cloudflare_bundle_r2_craft-type-default-v141_20260730`
- Frozen folder inventory: **102 files**, **53,391,370 bytes**
- Frozen tree hash: `c4fd180bff1ededfe51b9e765f084d13520e8bb671a0c636b12b122c0179a31f`
- Hash matched before preview, before production promotion, and after production QA.
- R2 manifest: **366 rows**, **913,862,841 bytes**, **0 differences** from v140
- Preview deployment: `166cc592-e8d2-4a0a-9e00-0aa5ff616225`
- Preview URL: `https://166cc592.ufo-timeline.pages.dev`
- Production deployment: `ae7c9cb8-a2de-4bfd-af80-3b46671e3901`
- Immutable production URL: `https://ae7c9cb8.ufo-timeline.pages.dev`
- Canonical production URL: `https://ufo-timeline.pages.dev`

Release status: **production deployed and verified**.

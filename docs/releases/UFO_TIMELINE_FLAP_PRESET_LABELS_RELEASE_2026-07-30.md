# UFO Timeline Famous-Flap Preset Label Release

Release date: 2026-07-30

## Outcome

Every Famous Flaps option now keeps its chronological window and descriptive label together.

- The date range comes first.
- Start and end months are shown.
- Days are omitted from the compact visible label.
- The historical wave, location, or event name follows the date.
- The exact day-level range remains authoritative and is applied to all four synchronized date fields.
- Each option title records the exact start/end dates and the longer preset description.

The Filters and Timeline Window selectors use the same generated labels and remain synchronized.

## Visible labels and exact windows

| Visible option | Exact applied window |
| --- | --- |
| `1947 Jun-Sep - Roswell era` | `1947-06-01` through `1947-09-30` |
| `1952 Jun-Aug - Washington D.C.` | `1952-06-15` through `1952-08-31` |
| `1954 Sep-Nov - France wave` | `1954-09-01` through `1954-11-30` |
| `1965 Jan-67 Dec - Late-60s wave` | `1965-01-01` through `1967-12-31` |
| `1973 Aug-74 Jan - 1973 wave` | `1973-08-01` through `1974-01-31` |
| `1989 Nov-90 Apr - Belgium Wave` | `1989-11-01` through `1990-04-30` |
| `1997 Mar - Phoenix Lights` | `1997-03-12` through `1997-03-14` |
| `1997 Feb-May - Phoenix era` | `1997-02-01` through `1997-05-31` |
| `2004 Oct-05 Jan - Nimitz era` | `2004-10-01` through `2005-01-31` |

The live interface uses typographic en dashes for ranges and a centered dot between the range and name.

## Implementation

- Authoritative checkout: `C:\Users\jarod\Desktop\UFO Timeline map tool`
- Git metadata: absent
- Authoritative frontend: `webapp/static_public`
- Generated frontend: `static_bundle`
- Asset version: `2026-07-30-flap-preset-labels-v143`
- Canonical data and R2 objects: unchanged

A pure `flap_preset_labels.js` helper now derives the visible month range directly from each preset's real `startIso` and `endIso`. This prevents the displayed range from drifting away from the dates the control actually applies.

The formatter:

- collapses same-month windows to one month, such as `1997 Mar`;
- shows both months for same-year windows;
- shows both years for cross-century windows;
- uses a compact two-digit ending year when both years share a century;
- falls back safely when a malformed preset is supplied.

The Timeline Famous Flaps control spans additional grid space on desktop and both selectors use a readable 14-pixel font. Both controls retain a 44-pixel minimum height and collapse to one clean column without horizontal overflow on mobile.

## Automated verification

- Complete Python suite: **771 passed**, **0 failed**
- Existing non-failing warning: one Starlette/httpx deprecation warning
- Executable JavaScript suites: **9 of 9 passed**
- New formatter coverage includes same-month, same-year, cross-year, cross-century, malformed-input, fallback-label, exact-title, Belgium Wave, and Phoenix Lights cases.
- JavaScript syntax checks passed for authoritative and generated copies.
- Authoritative/generated parity: **8 of 8 frontend files matched byte-for-byte**
- Cloudflare bundle validation: **11 of 11 checks passed**

## Browser QA

Local, immutable preview, immutable production, and canonical production were checked at desktop and 390-by-844 mobile sizes.

Verified:

- startup completed without failure;
- all nine date-first descriptive labels were present in both selectors;
- Craft Type remained the default color mode;
- selecting Belgium Wave showed `1989 Nov-90 Apr - Belgium Wave`;
- both synchronized selectors selected Belgium Wave;
- all four date fields became `1989-11-01` / `1990-04-30`;
- selecting Phoenix Lights showed the tidy month-only label `1997 Mar - Phoenix Lights`;
- all four exact fields became `1997-03-12` / `1997-03-14`;
- mobile selected text was fully visible;
- both selectors measured 44 pixels high on mobile;
- the Timeline selector received additional desktop width;
- complete exact dates remained readable;
- horizontal overflow: **0 pixels**;
- failed network requests: **0**;
- responses with status 400 or higher: **0**;
- console warnings/errors: **0**.

Observed startup-to-ready times were approximately 8.6 seconds on preview, 9.1 seconds on immutable production, and 8.4 seconds on the canonical production domain.

## Final file evidence

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `webapp/static_public/app.js` | 937,157 | `d072cf7f475f15c0f08a984646f3653ab8e9c98cd36d18d680d1b6e186920760` |
| `webapp/static_public/index.html` | 69,532 | `890f43ca92ef4ce5b5dc1e71166900e64038aaed1acb9145c5be44203e5fed04` |
| `webapp/static_public/styles.css` | 127,825 | `e29c41dd74c82e92f4a4758edf02d13cc0d5d024b13acdc573931efd0c981a7f` |
| `webapp/static_public/flap_preset_labels.js` | 2,806 | `7cfba4ee961be0c622b0d83ae85b352e974bbf6715aa4e1c81583f5055bc98c1` |
| `static_bundle/data/app_config.json` | 2,522 | `3b374c706a8b7a0674c74a4ba1d12155adfc0745f723a965fbfeb0305d18d10c` |
| `tests/test_webapp.py` | 101,651 | `90f9e2f1b4b10693ba5d0a758f9cd92521aef74c6fae48b21646e62bf1247f74` |
| `tests/test_flap_preset_labels.mjs` | 1,432 | `ecf9684f7718049811b2a02fde36e1cf2fe181bc15348b1ee78498785f0ec526` |

## Release

- Cloudflare Pages project: `ufo-timeline`
- Production branch: `main`
- Previous production deployment: `8ee0381d-4cda-4c55-afd7-b797edf8fbe6`
- Frozen folder: `cloudflare_bundle_r2_flap-preset-labels-v143_20260730`
- Frozen inventory: **104 files**, **53,428,119 bytes**
- Frozen tree hash: `a276187412df8d135061224fe467af86aa3b37a619f9db75c6bb8ec3c9786f9e`
- The tree hash matched before preview, after preview QA, and after production QA.
- R2 manifest: **366 rows**, **913,862,841 bytes**, byte-for-byte equivalent after generated metadata is excluded
- R2 uploads performed: **0**
- Preview deployment: `c041ad7e-adf0-4476-a66d-0e701c8039dd`
- Preview URL: `https://c041ad7e.ufo-timeline.pages.dev`
- Named preview alias: `https://flap-preset-labels-v143.ufo-timeline.pages.dev`
- Production deployment: `59dad72d-f83a-4212-8177-b07f8ddc30cc`
- Immutable production URL: `https://59dad72d.ufo-timeline.pages.dev`
- Canonical production URL: `https://ufo-timeline.pages.dev`

Production uploaded zero new files after preview because Cloudflare reused the identical frozen artifact.

Release status: **production deployed and verified**.

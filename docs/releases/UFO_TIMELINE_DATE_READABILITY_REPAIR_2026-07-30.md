# UFO Timeline Date Readability Repair

Release date: 2026-07-30

## Scope

- Authoritative checkout: `C:\Users\jarod\Desktop\UFO Timeline map tool`
- Git metadata: absent
- Authoritative frontend: `webapp/static_public`
- Generated frontend: `static_bundle`
- Cloudflare Pages project: `ufo-timeline`
- Production branch: `main`
- Previous production deployment: `a5f7634e-287e-40ba-ac2d-91e0852e5549`
- Previous asset version: `2026-07-30-chronological-neighborhood-v138`
- Canonical payload and R2 objects: unchanged

## Defect and repair

The Filters rail forced Start Date and End Date into two equal columns even when the rail was only 212 pixels wide. Each text input was reduced to 50 pixels, leaving 20 pixels of usable text space for a complete 10-character date that required approximately 82 pixels. The field therefore showed only the leading portion of a valid date.

The repair:

- marks the Filters date row as `filter-date-grid`;
- uses an adaptive grid with a 210-pixel minimum complete-control width;
- retains two columns only when both date/calendar controls have enough space;
- otherwise stacks Start Date and End Date with the calendar button beside each full-width text field;
- uses tabular numerals for stable date alignment;
- gives the Famous Flaps control a larger wrapping basis;
- displays concise preset labels while preserving the full description in the option title;
- keeps the Timeline Window date controls unchanged because they already fit complete dates.

## Measured layout

| Surface | Value | Usable text width | Full value visible | Horizontal overflow |
| --- | --- | ---: | --- | ---: |
| Previous production Filters rail | `1954-09-01` | 20 px | No | 0 px |
| v140 desktop Filters rail, 212 px container | `1954-09-01` | 132 px | Yes | 0 px |
| v140 desktop Filters rail, 212 px container | `1954-11-30` | 132 px | Yes | 0 px |
| v140 desktop Timeline Window | both exact dates | 120 px | Yes | 0 px |
| v140 mobile, 390 px viewport | Filters exact dates | 231 px | Yes | 0 px |
| v140 mobile, 390 px viewport | Timeline Window exact dates | 120 px | Yes | 0 px |

All four calendar controls remained 44 by 44 pixels on mobile. The active preset rendered as `1954 France Sept-Nov` without clipping.

## Validation

- Focused date/responsive/source-parity checks: 3 passed.
- Complete Python suite: 770 passed, 1 existing Starlette/httpx deprecation warning.
- Complete Node suite: 7 of 7 files passed.
- Authoritative/generated parity: all six frontend files matched byte-for-byte.
- Local Browser QA:
  - Ready / 100%;
  - full desktop and mobile dates visible;
  - preset label visible;
  - zero horizontal overflow;
  - zero console warnings/errors.
- Preview and production Browser QA:
  - Ready / 100%;
  - asset version `2026-07-30-date-readability-v140`;
  - full Filters and Timeline Window dates visible;
  - 44-by-44-pixel calendar controls;
  - zero horizontal overflow;
  - zero captured failed requests;
  - zero console warnings/errors.

| Final file | Bytes | SHA-256 |
| --- | ---: | --- |
| `webapp/static_public/index.html` | 68,905 | `4341ec3e431d6c727ecf4fb90e46530b58d2e2411c6b1a2e179c3a7743ed9519` |
| `webapp/static_public/styles.css` | 124,344 | `982028f2c6fe92aa76a06905fa9b8a59acb2201984e3e84fee05f33787382c24` |
| `webapp/static_public/app.js` | 913,460 | `cc07055133a9c4d333d64bcb2580bfa5293889287af6a6a71cca312643f230fe` |
| `static_bundle/data/app_config.json` | 2,520 | `bde674f56e3b660b6a3e9c5020b26a9780bef890670fb60a44ea53675d254515` |
| `tests/test_webapp.py` | 97,326 | `0e8b36cdafcc778d1806af75c59ce1967c01bc0218b95c4c3b0825777c018cbe` |

## Release

- Final asset version: `2026-07-30-date-readability-v140`
- Frozen folder: `cloudflare_bundle_r2_date-readability-v140_20260730`
- Frozen folder size: 102 files, 53,391,298 bytes
- Frozen tree hash: `09b144da44606ea98c26d821a817b9b5d76c0d62e2498101a0ed76cb3e69c2f7`
- Hash matched before preview, after preview QA, and after production promotion.
- R2 manifest: 366 rows, 913,862,841 bytes, 0 differences from v138.
- Initial date-readable preview, not promoted after its visual gate found an adjacent preset-label issue:
  - deployment `f99df8ad-4efd-417e-9387-df546425e348`
  - `https://f99df8ad.ufo-timeline.pages.dev`
- Accepted v140 preview:
  - deployment `f7dda539-dee6-4ea0-833d-c8e757c92b14`
  - `https://f7dda539.ufo-timeline.pages.dev`
- Production:
  - deployment `264cc621-7c86-46bc-b60f-3c1813daa71c`
  - immutable URL `https://264cc621.ufo-timeline.pages.dev`
  - canonical URL `https://ufo-timeline.pages.dev`

Release status: **production deployed and verified**.

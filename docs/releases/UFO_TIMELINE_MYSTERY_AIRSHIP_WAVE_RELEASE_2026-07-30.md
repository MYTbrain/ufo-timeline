# UFO Timeline Mystery Airship Wave Release

Release date: 2026-07-30

## Outcome

The Famous Flaps controls now include:

`1896 Nov–97 Jun · Mystery Airship Wave`

Selecting it applies `1896-11-01` through `1897-06-30` to both synchronized date-control pairs. The range follows the documented 1896–1897 American mystery-airship wave: reports began in California in November 1896, spread east during 1897, and were still being reported in the first half of that year. Historical context: [History Nebraska](https://history.nebraska.gov/look-up-in-the-air/) and [CUFOS](https://cufos.org/types-of-ufos/pre-1940-cases/).

The release also applies a bounded, manually reviewed duplicate repair within that window. Only records determined to be cross-source retellings of the same incident were consolidated. Similar-looking events were not merged merely because they shared a date, month, place, or description.

## Duplicate review

| Measure | Count |
| --- | ---: |
| Canonical events in the window before review | 1,384 |
| Reviewed same-incident clusters | 52 |
| Canonical event shells represented by those clusters | 169 |
| Duplicate event shells consolidated | 117 |
| Canonical events in the window after review | 1,267 |
| Mapped events in the window after review | 992 |
| Unmapped events in the window after review | 275 |

Post-review source counts in the window:

| Source | Events |
| --- | ---: |
| UFOCAT | 968 |
| Majestic | 266 |
| PhenomenaINON UPDB | 31 |
| NUFORC | 2 |

All 117 removed event IDs are absent from the published catalog, and all 52 keeper IDs remain. The keeper records preserve the removed events as normalized-event snapshots together with every underlying source record. Across the 52 keepers, 530 source records remain available in Full Event View.

The review intentionally retained ambiguous co-located month-only records and any candidate whose evidence did not establish that it was the same incident.

## Guarded application

- The reviewed merge sidecar explicitly names every keeper and member ID.
- Cluster membership is disjoint and bounded to `1896-11-01` through `1897-06-30`.
- Every expected event identity and source record is validated before mutation.
- All output is staged before replacing current canonical-web artifacts.
- Events, summary shards, detail chunks, packed points, trace indexes, segments, aggregate bins, manifests, and gzip siblings are regenerated as one operation.
- Removed event snapshots and source provenance are attached to the keeper before duplicate shells are removed.
- The upstream canonical-full payload was not changed.
- Earlier R2 release prefixes were not changed.

## Resulting global data counts

| Measure | Before | After |
| --- | ---: | ---: |
| Total events | 703,018 | 702,901 |
| Mapped events / packed points | 580,799 | 580,785 |
| Trace events | 574,959 | 574,945 |
| Trace segments | 574,958 | 574,944 |
| Trace aggregate bins | 146,869 | 146,869 |

The decrease in mapped and trace rows is limited to duplicate event shells. No distinct source record was discarded.

## Automated verification

- Complete Python suite: **787 passed**, **0 failed**
- Existing non-failing warning: one Starlette/httpx deprecation warning
- Focused merge, staging, and static-payload tests: **13 passed**
- Post-startup-profile regression subset: **52 passed**
- Executable JavaScript behavior suites: **9 of 9 passed**
- JavaScript syntax checks: source and generated bundle passed
- Authoritative/generated frontend parity: **10 of 10 files matched**
- Canonical static-payload readiness: **13 of 13 checks passed**
- Cloudflare bundle validation: **11 of 11 checks passed**
- All 52 keepers passed a full source-provenance comparison after application.
- Representative public R2 verification: **11 of 11 objects matched local SHA-256**, including manifests, packed points, the trace-event index, detail chunks, and summary shards.

Executable tests cover the exact preset label and boundaries, synchronized selectors, reviewed-cluster disjointness, stale-input rejection, duplicate removal, keeper retention, and provenance preservation.

## Browser QA

The frozen release was exercised locally through the repository's canonical-data preview harness, then on the immutable preview, immutable production deployment, and canonical production URL.

Verified:

- Ready / 100% startup.
- 702,901 total events and 580,785 mapped events.
- The new label appears in both Famous Flaps selectors.
- Selecting it synchronizes all four date fields to `1896-11-01` and `1897-06-30`.
- The resulting default-filter view contains 413 mapped events.
- Craft Type remains the default Color By mode.
- Only the `<=1 day` and `<=2 days` trace buckets are active by default.
- Desktop and 390 x 844 mobile layouts have no horizontal overflow.
- Mobile Start and End fields are 47 px high; both flap selectors are 44 px high.
- The complete date range and flap name remain visible and readable on mobile.
- Production browser console warnings/errors: none.
- Production asset inventory: 116 observed assets, all release URLs use the v148 asset token and immutable v148 R2 prefix, with no older R2 release URL present.
- Ten production frontend/config files match the frozen files byte-for-byte.

Full-record preview QA inspected the consolidated 1896-11-15 Suisun City keeper. It visibly retains the reviewed-consolidation note, cluster ID, two normalized event copies, five preserved source records, and both `ufocat:79528` and `majestic:Johnson_7681`.

Localhost cannot directly request the production R2 origin under its deployed CORS policy. The repository's local preview server therefore served the same frozen frontend while rewriting only the in-memory app-config response to the local canonical-web payload; no frozen file was edited.

## Release evidence

- Authoritative checkout: `C:\Users\jarod\Desktop\UFO Timeline map tool`
- Git metadata: absent
- Authoritative frontend: `webapp/static_public`
- Generated frontend: `static_bundle`
- Asset version: `2026-07-30-airship-wave-v148`
- Previous production deployment: `083a37e1-18dd-4bd0-88ed-ba8cdb371c8e`
- Frozen Pages folder: `cloudflare_bundle_r2_airship-wave-v148_20260730`
- Frozen inventory: **104 files**, **53,450,125 bytes**
- Frozen tree-hash algorithm: SHA-256 of ordinal-sorted `path<TAB>bytes<TAB>file-sha256<LF>` rows
- Frozen tree hash before production: `af4c27e51f56308716be62bc4d4ef91b5581ec851303260697c3d965eeb36a41`
- Frozen tree hash after production: `af4c27e51f56308716be62bc4d4ef91b5581ec851303260697c3d965eeb36a41`
- Preview deployment: `d8e45ee9-f4fe-4a77-984e-0f62b05cf0a6`
- Preview URL: `https://d8e45ee9.ufo-timeline.pages.dev`
- Preview alias: `https://airship-wave-v148.ufo-timeline.pages.dev`
- Production deployment: `e69c19e0-2e52-403e-b820-ed2d10b12f9b`
- Immutable production URL: `https://e69c19e0.ufo-timeline.pages.dev`
- Canonical production URL: `https://ufo-timeline.pages.dev`
- Production Pages upload reused the preview artifact: **0 files uploaded**, **103 files already uploaded**
- New immutable R2 prefix: `releases/airship-wave-v148-20260730`
- R2 public base: `https://pub-e9029ab2f6b448daad03d7cde7e15e64.r2.dev/releases/airship-wave-v148-20260730`
- R2 upload manifest: **366 objects**, **913,749,942 bytes**
- R2 upload-manifest SHA-256: `7e4ac43ae9ac7d73d8af17e16ea407b365b018a867ba1bb68828075f77af54eb`
- Frozen/deployed app-config SHA-256: `041704d10c04ba5a9aa033e5b4541b93b2f19687e647422302325ab6b234cf10`

An initial scratch tree digest from before preview was discarded because it did not reproduce under the documented algorithm. The authoritative digest above was recomputed before and after production. As an independent check, every normally addressable preview asset matched the frozen file byte-for-byte; `_headers` is routing configuration rather than a public asset, and Cloudflare clean-URL redirects account for the two HTML route exceptions.

## Rollback

The complete pre-application canonical-web tree was copied before mutation:

`backups/airship_wave_v148_preapply_20260730/data_canonical_web`

- Files: **730**
- Bytes: **7,931,057,831**
- Tree hash: `3e5d28703210b3a75656d112f1a94c473a1e301766b9df7ae195db8463e6060d`
- Pre-application canonical-web manifest SHA-256: `f16126732d0266446f1ec867c25dd2060caeefa4a4299d1f23f7a3aa531ce91e`

The previous production deployment and all earlier immutable R2 prefixes remain available.

## Key source hashes

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `scripts/apply_reviewed_event_merges_to_canonical_web.py` | 41,881 | `72169a5b3c6005be023251e6f0a6769609e459fd0ba3b3dcfc45f66cc4f4220f` |
| `data/reports/airship_wave_reviewed_event_merges_v148.json` | 24,543 | `a451f4e885a13195bfac1267c8d13cea159552b86c24ff69e11dfea627dcf245` |
| `data/reports/airship_wave_reviewed_event_merges_apply_v148.json` | 88,517 | `fb9475748c570ae974a6bd94edf0a4a0583186dd52ec01f2b54ea179a0ff35dc` |
| `data/reports/canonical_web_static_payload_readiness_airship_wave_v148.json` | 1,469 | `e71fd6ee6793bd53e41beeb5556d87de384b807c8741f28f68c1be060edaa094` |
| `tests/test_apply_reviewed_event_merges_to_canonical_web.py` | 12,800 | `fc61beda3940ba6e3c2ebcd1afd7ff31b3ab54bda6df91bd17d61aca68a2df28` |
| `tests/test_flap_preset_labels.mjs` | 1,716 | `615940758774789c6af1ae8bce401d61675777bf886ea6ca69f1fad4c84d939b` |
| `webapp/static_public/app.js` | 948,132 | `2fc72bd0edc83ec3fe9874e046267c5cb53478be28a340a051ef93b382082bec` |
| `webapp/static_public/index.html` | 69,474 | `50f37887a3fae63d9429759547a2a35da074834339bfc2c2de2c7d6d3ff64785` |
| `data/canonical_web/canonical_web_manifest.json` | 6,782 | `e22c4e0acaca2b95ef2674988e960c4f946daa1cb13732edc63fa12d31556dcf` |

Release status: **production deployed and verified**.

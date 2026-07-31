# UFO Timeline Non-Terrestrial Coordinate Quarantine Release

Release date: 2026-07-30

## Outcome

Three Majestic records whose source jurisdiction is explicitly `The Moon` and whose source coordinate is exactly `0,0` no longer appear as Earth-map sightings in the Gulf of Guinea.

The records were not deleted. Each remains in the canonical catalog and Full Event View as an `Unmapped` event. The original source row, raw `0.000000 -0.000000` value, description, references, and provenance remain visible. Full Event View now explains:

> Earth-map coordinates omitted: the source supplied an exact 0,0 placeholder for a non-terrestrial report.

This is a deliberately narrow rule:

- The source must explicitly identify a known non-terrestrial jurisdiction.
- The coordinate must be exactly zero latitude and zero longitude.
- Nonzero observer coordinates and spacecraft ground-track coordinates are preserved.
- Terrestrial events at or near zero coordinates are not changed.

The audit found exactly three mapped catalog records meeting the rule and no mapped terrestrial exact-zero record.

## Quarantined records

| Date | Source ID | Event ID | Location |
| --- | --- | ---: | --- |
| 1887-11-23 | `Hatch_UDB_139` | `31235763669570` | Residential, MOON, PLT, The Moon |
| 1954-09-05 | `Hatch_UDB_3756` | `4114331960007368` | Residential, MOON, MHM, The Moon |
| 1996-09-21 | `Hatch_UDB_17715` | `132294255236761` | Residential, MT. VERNON, IN, IND, The Moon |

As a preservation check, nonzero lunar-observer event `1769977787353407` remains in both packed points and the trace-event index.

## Implementation

- Added a reusable non-terrestrial zero-coordinate policy helper.
- Applied the policy during future Majestic imports.
- Added a guarded, staged current-artifact repair:
  - Every target path, row index, event identity, prior coordinate, and raw source field must match the sidecar before any write.
  - All output is staged before committing.
  - Event and summary rows are updated together.
  - Packed points, trace events, trace segments, aggregate bins, manifests, size reports, and affected gzip siblings are regenerated together.
  - Stale guards fail closed without partial writes.
- Added explicit quarantine metadata and a human-readable mapping note.
- Rebuilt both startup profiles so no quarantined event remains in startup events or trace previews.
- Synchronized the changed canonical web artifacts into `static_bundle`.
- Corrected the public app counters and advanced the asset version to `2026-07-30-non-terrestrial-coordinate-quarantine-v147`.
- The upstream canonical full payload, source CSV, R2 objects from earlier releases, and unrelated data were not changed.

## Resulting data counts

| Measure | Before | After |
| --- | ---: | ---: |
| Total events | 703,018 | 703,018 |
| Mapped events / packed points | 580,802 | 580,799 |
| Unresolved events | 122,216 | 122,219 |
| Exact-coordinate events | 110,360 | 110,357 |
| Unknown-location-precision events | 16,924 | 16,927 |
| Trace events | 574,962 | 574,959 |
| Trace segments | 574,961 | 574,958 |
| Trace aggregate bins | 146,885 | 146,869 |

All three quarantined IDs are absent from packed points, the trace-event index, trace segments, and startup profiles.

## Automated verification

- Complete Python suite: **783 passed**, **0 failed**
- Existing non-failing warning: one Starlette/httpx deprecation warning
- Executable JavaScript behavior suites: **9 of 9 passed**
- JavaScript syntax checks: **16 files passed**
- Authoritative/generated frontend parity: **10 of 10 files matched**
- Guarded repair tests cover successful application, narrow policy scope, and stale-input no-write behavior.
- Static regression tests cover the exact three IDs, packed point/trace exclusion, retained raw evidence, preserved nonzero observer coordinates, startup-profile exclusion, and public counter parity.
- Cloudflare bundle validation: **11 of 11 checks passed**
- Public R2 verification: seven representative objects matched local SHA-256 hashes, including all three affected event chunks, the affected summary shard, packed points, and the trace-event index.
- The R2 copy of `Hatch_UDB_139` was decompressed and checked directly: `has_coordinates=false`, `lat=null`, `lon=null`, `coordinate_source=unresolved`, with raw zero-coordinate evidence preserved.

## Browser QA

Local, immutable preview, immutable production, and canonical production were tested through the live application.

Verified:

- Ready / 100% startup.
- 703,018 total events and 580,799 mapped events.
- Craft Type remains the default color mode.
- Only the `<=1 day` and `<=2 days` trace buckets are active by default.
- Full-corpus search for `marching triangle` returns exactly one event when Trace Mode is set to None.
- The result card visibly says `Unmapped`.
- Full Event View identifies `Hatch_UDB_139`, shows `coordinate_source=unresolved`, displays the quarantine explanation, and preserves `key_vals/LatLong: 0.000000 -0.000000`.
- No browser console warnings or errors on local, preview, immutable production, or canonical production.
- The deployed app, stylesheet, deployment config, and startup profile match the frozen files byte-for-byte.
- Cloudflare modifies only served `index.html` by adding its expected Pages Analytics tag.
- Existing mobile-layout regression coverage remained green; this release changes data/import policy and cache-version text, not layout or CSS.

The default static trace view intentionally shows only endpoints participating in the active short-gap traces. Because an unmapped event cannot be a trace endpoint, set Trace Mode to `None` when searching for this or another isolated unmapped record.

Representative startup timings:

| Environment | First usable | Ready |
| --- | ---: | ---: |
| Local | 5,708.2 ms | 5,924.5 ms |
| Preview | 12,640.5 ms | 14,035.7 ms |
| Immutable production | 8,808.7 ms | 11,007.9 ms |
| Canonical production | 8,315.6 ms | 9,954.0 ms |

## Release evidence

- Authoritative checkout: `C:\Users\jarod\Desktop\UFO Timeline map tool`
- Git metadata: absent
- Authoritative frontend: `webapp/static_public`
- Generated frontend: `static_bundle`
- Asset version: `2026-07-30-non-terrestrial-coordinate-quarantine-v147`
- Previous production deployment: `10ddf5d1-aee0-4843-ab79-f841ab02bd5d`
- Frozen Pages folder: `cloudflare_bundle_r2_non-terrestrial-coordinate-quarantine-v147_20260730`
- Frozen inventory: **104 files**, **53,475,866 bytes**
- Frozen tree-hash algorithm: SHA-256 of ordinal-sorted `path<TAB>bytes<TAB>file-sha256<LF>` rows
- Frozen tree hash before preview: `35335c54947f77a882b80026828f1957a0477a03a042643c82452758bc795c07`
- Frozen tree hash after preview: `35335c54947f77a882b80026828f1957a0477a03a042643c82452758bc795c07`
- Frozen tree hash after production: `35335c54947f77a882b80026828f1957a0477a03a042643c82452758bc795c07`
- Preview deployment: `717651d2-8ae3-41f0-8e52-a5558df2ac25`
- Preview URL: `https://717651d2.ufo-timeline.pages.dev`
- Preview alias: `https://non-terrestrial-coordinate-q.ufo-timeline.pages.dev`
- Production deployment: `083a37e1-18dd-4bd0-88ed-ba8cdb371c8e`
- Immutable production URL: `https://083a37e1.ufo-timeline.pages.dev`
- Canonical production URL: `https://ufo-timeline.pages.dev`
- Production Pages upload reused the preview artifact: **0 files uploaded**, **103 files already uploaded**
- New immutable R2 prefix: `releases/non-terrestrial-coordinate-quarantine-v147-20260730`
- R2 public base: `https://pub-e9029ab2f6b448daad03d7cde7e15e64.r2.dev/releases/non-terrestrial-coordinate-quarantine-v147-20260730`
- R2 upload manifest: **366 objects**, **913,862,988 bytes**
- One transient Cloudflare R2 `500` occurred for `chunk_000004.json.gz`; the guarded uploader retried it successfully, and all 366 objects completed.
- R2 upload-manifest SHA-256: `8d9ec0d9e1d68ac09c98fb4f53ac9e1da82e96b862197ba518d2f83bf99f6980`
- Frozen/deployed app-config SHA-256: `f2c6855b9fe9d628f1661f8bd104f316fcb9a137bb66563ce8a112138e5b1514`

## Rollback

The 32 affected pre-application artifacts were copied before mutation:

`backups/non_terrestrial_coordinate_quarantine_v147_preapply_20260730/data_canonical_web`

- Files: **32**
- Bytes: **279,838,323**
- Tree hash using the same release algorithm: `e3311fe9d049ad22c02b04589142815763658ab4f079901e196c9fd353a540e8`

Earlier R2 release prefixes and the previous production deployment remain immutable.

## Key source hashes

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `parser/non_terrestrial_coordinates.py` | 1,741 | `5ef84e6624b5e95b8c945154da2b4190f36e3f124ba15f6f9669172e757f1cba` |
| `parser/csv_sources/majestic.py` | 3,632 | `a991072dbd370efae841f0e837afe4d304d43296c940d140c0bca3d1521b0e1e` |
| `scripts/apply_non_terrestrial_coordinate_quarantine_to_canonical_web.py` | 26,396 | `ed101b3dfff88c899c718c0f341561d43c650fc6cded5b4b576f7d25d47ab155` |
| `data/reports/non_terrestrial_coordinate_quarantine_sidecar_v147.json` | 7,346 | `0e642293432efd12a2c52be58d05c99f5ba5dae1840cb064cb429316b42029cb` |
| `data/reports/non_terrestrial_coordinate_quarantine_apply_v147.json` | 6,186 | `3112595d256a1f95e8ebaa1544faf925154a16c6fe72ef3b875006f7adebb611` |
| `data/canonical_web/canonical_web_manifest.json` | 4,551 | `f16126732d0266446f1ec867c25dd2060caeefa4a4299d1f23f7a3aa531ce91e` |
| `webapp/static_public/index.html` | 69,599 | `e464787ee2affdf5dce74df916a0ae8176b75dcee3913b158b11e6bb5aa97501` |
| `static_bundle/data/app_config.json` | 2,537 | `c6a9038377383c7284bfb5071f8b421af673ddc0b66be4a7f7f748a9c77f03b3` |

Release status: **production deployed and verified**.

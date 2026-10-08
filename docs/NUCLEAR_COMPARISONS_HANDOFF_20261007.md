# Nuclear comparison implementation, local candidate

The user authorized lunar, nuclear, and direct crop/animal comparisons. This component adds independent nuclear chronology and a separate source-confirmed nuclear-facility lane. No deployment or GitHub write was performed.

## Source and coverage

`data/analysis_comparisons/nuclear_context_v1.json` is the new canonical compact runtime input. Plain SHA-256: `5f3da478cb2d1891edacb398686f0627f27ad82fd7fe954833f72107f123ec65`. The gzip is 82,892 bytes. The primary report is *Nuclear Explosions 1945–1998*, Bergkvist/Ferm, FOA/SIPRI, July 2000, FOA-R--00-01572-180--SE. The primary PDF and separately MIT-licensed transcription are pinned from data-is-plural commit `056ac3db13b392cb69be9f787e235738167e7fb1` in `nuclear_sources`.

The input contains 2,051 published test/group-explosion records across seven testing states, from 1945-07-16 through 1998-05-30. It is not a count of individual devices. The report's summary says 2,052, including 715 Soviet records; the transcription has 714 Soviet rows. That discrepancy remains explicit. No post-1998 chronology, disputed Vela event, or inferred replacement record is invented.

Primary report section 3.2 explicitly defines dates/times as GMT, zero/blank as unavailable/nil/negligible, and locations as often approximate. Therefore 24 `(0,0)` markers become missing coordinates; zero yields stay unknown rather than zero-yield claims. GMT dates stay unchanged, including Hiroshima's 1945-08-05 GMT date. Trinity's rough published Alamogordo marker stays unchanged and remains ineligible for strict site-distance inference.

The source audit checks 1,978 primary layout-extracted lines against country/date/ID/time/coordinates/yields. Of these, 1,964 also have exact purpose-text agreement. Fourteen purpose differences are OCR/column-read review targets, and 73 lines are not parsed reliably. The total 87 incomplete line verifications remains visible. First table and GMT/data conventions were also visually inspected; PNGs are bounded source evidence, not runtime assets.

Default selected roles are weapons (1,723), peaceful (192), and combat (2): 1,917 records. Safety and mixed safety (133), and unknown purpose (1), are separate. Compound safety purposes are excluded by default, not silently promoted to weapons. IDs combine country, GMT date and source ID because the printed ID `74044` appears for different US/French records.

## Actual calculations

`analysis_nuclear.js` exposes `UfoAnalysisNuclear.computeNuclearContext`. All ordinals are UNIX days. It accepts a streaming `forEachRow(callback)` or fixture `rows`, shared compact crop/animal inputs, tests, nuclear facilities, existing broader facilities/codebook, active start/end dates, a 7/30/90-day window and test-role selection. It does not retain a recycled callback object. Date-indexed tests and a spatial facility grid bound runtime.

Main outputs use the active dates. Earlier/same/later source dates, marker-distance rings, daily lags, unique-report craft composition and source/era summaries expose both report/test-pair counts and unique reports. Overlapping test windows are not independent observations. Source date roles are preserved separately: crop formation versus discovery/publication and animal incident versus discovery/publication.

Calendar controls use the same marker, the same weekday and approximately the same season at -364/+364 days. Target and control windows use identical offsets, including clipping to the selected target dates. Other UFO cohort filters are shared, but reference dates can fall outside the selected dates. Windows overlapping any known same-region/nearby source event, including safety events, are excluded. The relative report density uses pair counts divided by test/control window-days; it is descriptive, not incidence or causal inference. Adjacent-year reporting effort and population are not observed. Calendar boundary sensitivity reports pairs within +/-1 day separately because UFO source dates are not harmonized to GMT.

Explicit nuclear/atomic, military/government, astronomical/scientific and historical/publication context types/groups, canonical `non_ufo_context` / `conventional_or_explained` categories, and explicit context flags are excluded from the UFO lane. Fireball/meteor-like, satellite-like, aircraft-like, balloon-like or other appearance words never establish an identified explanation and are not excluded by substring matching. Parent integration must pass human-readable type/craft/group labels or `isContext: true` / `isUfoReport: false`; raw numeric taxonomy codes cannot substantiate this exclusion.

## Nuclear facilities are a separate, partial inventory

Four existing institutions are reviewed against captured official histories/roles: Los Alamos main campus, Lawrence Livermore main site, Oak Ridge National Laboratory, and AWE Aldermaston. Linked alternate markers for the same institutions are excluded from the broader comparison. Nuclear identity is a reviewed ID allowlist, not a keyword match. Existing campus coordinates and uncertainty limits remain unchanged.

The broader pool comprises military/research markers with unreviewed nuclear status. It must never be labelled a verified nonnuclear control. Group counts are exclusive: nuclear-only, broader-only, both, or no confirmed active marker match. Unknown operational intervals remain separate. Source-year opening/closing boundaries are excluded. This is not a global nuclear-facility or power-reactor inventory.

## Verification

Focused tests cover GMT/UNIX day zero, missing coordinates, role exclusion, duplicate test/report identity, unique-report composition, crop/animal date roles, calendar-control contamination, mutable callbacks, nuclear identity aliases, year activity boundaries, and dateline distance/grid handling.

The real-source test reads the shared repaired catalog's 702,893 rows without copying them. It passed in 7.52 seconds including I/O after narrowing context exclusions to explicit categories. All-time +/-30 days / 500 km produced:

| Domain | Exact-day mapped eligible records | Unique reports linked | Earlier / same / later date pairs | Calendar-control pairs |
|---|---:|---:|---:|---:|
| Craft/UFO reports | 548,042 | 4,613 | 8,982 / 318 / 9,493 | 4,302 |
| Crop reports | 3,659 | 5 | 14 / 0 / 11 | 1 |
| Animal reports | 340 | 2 | 3 / 0 / 2 | 0 |

Facility group totals equal each domain's eligible denominator: four reviewed nuclear institutions, 1,783 broader markers. `nuclear_sources/runtime_qa.json` pins the input and contains the actual result receipt. These counts concern published markers and source dates; they do not show a nuclear effect or physical flight path. Strict inference remains blocked by unquantified marker error, date/timezone limits, reporting-effort gaps, incomplete chronology/facility coverage and unresolved source independence.

## Storage and reproduction

Rebuild the input with the bundled Python containing pypdf: `scripts/build_nuclear_comparison_context.py`. Existing captures are reused. `--fetch-missing-sources` downloads only small missing source files. `--shared-root` points to the protected primary workspace. Run `tests/test_analysis_nuclear.mjs` and `tests/test_analysis_nuclear_real_artifacts.mjs` with the bundled Node runtime.

Canonical candidate: the compact nuclear input and its source/provenance directory. Rollback: existing protected production release unchanged. No dataset, bundle, release, or database copy was made. New files are approximately 4.9 MiB total; none exceeds 100 MiB. The two source-check images are retained bounded evidence. No superseded large generated artifact or cleanup candidate was created.

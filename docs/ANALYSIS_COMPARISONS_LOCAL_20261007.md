# Analysis comparisons local candidate — 7 October 2026

## Status and authorized scope

The user authorized implementing Moon, nuclear and direct crop–animal comparisons after the Analysis inventory. This is a local candidate in `C:/Users/jarod/.codex/worktrees/case-navigation-release/UFO Timeline map tool`, extending the existing whole-site preview. The later planetary addition is documented in `docs/PLANETARY_COMPARISONS_LOCAL_20261007.md`, including its selected Lahiri convention, major-aspect views, date-only uncertainty and unavailable houses. The user's instruction not to deploy remains active. No deployment or production acceptance is established by the checks below.

**Runtime browser/UI verification completed.** The final integrated verification and actual browser receipt are recorded below. Unit, artifact, full-catalog and browser checks establish local QA; user acceptance and publication remain separate.

Protected production identity remains `dc834bac-2108-4de3-baad-47044e2ec51c`; the single known-good rollback remains `78cc3660-5750-4685-a095-fee6dce37fbf`. Neither release was replaced by this work.

## Shared inputs and date contracts

Canonical source data and effective repaired summary shards stay in the shared workspace `C:/Users/jarod/Desktop/UFO Timeline map tool`. The worktree does not contain a copied UFO corpus, analysis database or full deployment bundle.

- `scripts/build_analysis_comparison_context.py` produces the compact `data/analysis_comparisons/context_rows.json` and deterministic gzip, preserving 7,745 crops and 1,184 animal reports. `context_manifest.json` records source paths, SHA-256 pins, coverage and date-role counts; `CONTEXT_PURPOSE.txt` records rebuild and retention.
- New public comparison inputs use **Unix day ordinals**, with 1970-01-01 equal to zero. Existing internal Analysis accumulators use **Python day ordinals**, with 1970-01-01 equal to 719163. The worker converts explicitly; these epochs must never be guessed or mixed.
- Lunar accepts explicit `ordinalEpoch` and optional `contextOrdinalEpoch` as `unix_day` or `python_day`; its range and output are normalized to Unix days. Cross-context accepts the same named epochs. The nuclear payload declares `ordinalEpoch: unix_day`.
- Exact-day classification, start/end interval equality and date-role evidence are separate. Source catalog, discovery, publication or reported dates are not promoted to crop formation or animal occurrence dates. Missing, approximate, month/year and disputed intervals remain visible as exclusions.
- UFO input iterators receive transient mutable worker rows and do not retain a 702,893-object array. Explicit nuclear, military, astronomical and publication entries, normalized `non_ufo_context` craft/category classifications, and `isUfoReport: false` / `isContext: true` flags are excluded from lunar UFO phase counts. The nuclear estimator additionally applies its documented craft/domain exclusions. Unknown craft categories remain descriptive where the relevant engine admits them.

`scripts/build_analysis_comparisons_manifest.py` pins gzip and decompressed bytes for the context/nuclear payloads, reuses the existing source-pinned facility artifact, and records the parent quality Analysis manifest. Loader changes are responsible for hash validation, atomic commit and cache invalidation.

## Moon comparison

Implementation: `analysis_lunar.js`; offline dependency: `analysis_astronomy_engine.js`. Astronomy Engine is MIT licensed, retains its license notice, has no package/network runtime dependencies, and is pinned to commit `865d3da7d8112bbc7911238052c6af4aaf877181`, version 2.1.19, SHA-256 `d1b3ab4b86aa409f78c0f0d95162a847496cba7e938eb6f4712cf9c1c45f4a2e`.

The engine reports eight phase sectors, illumination, categories by phase, date-role/source coverage, and a calendar opportunity comparison for UFO reports, crops and animals. Date-only estimates use UTC noon descriptively. The uncertainty window covers the entire possible civil day across UTC+14 to UTC-12; phase bins retain stable counts and possible upper counts. Noon counts are estimates, not known observation-time phases. The calendar baseline uses actual days within each represented year-month, weighted by eligible reports in that month and clipped to the selected range. It corrects unequal phase opportunity and broad era/season composition; it does not measure observation effort, weather or reporting selection.

Normalized Gregorian dates before 1582-10-15 are excluded until the original calendar is verified; the current supported date range ends 2100-12-31. Source clocks without timezone evidence never become UTC.

Moon sky position requires an explicitly offset-bearing timestamp, a verified UTC flag, timezone provenance and source-verified coordinates with no declared uncertainty above 5 km. It reports airless topocentric Moon-center elevation and compass azimuth at zero observer height. Horizon position is not proof of visibility through terrain/clouds and does not identify a reported object.

Independent frozen JPL Horizons DE441 fixtures verify three geocentric illumination values within 0.01 percentage points and a topocentric airless azimuth/elevation fixture within 0.02 degrees. Source documentation: [Astronomy Engine](https://github.com/cosinekitty/astronomy), [Horizons API](https://ssd-api.jpl.nasa.gov/doc/horizons.html), [Horizons manual](https://ssd.jpl.nasa.gov/horizons/manual.html).

Real shared-corpus receipt `data/analysis_comparisons/lunar_qa.json`: cold computation including streamed gzip/JSON reads took 6.440 seconds after the live preview exposed normalized context classifications not captured by display-label exclusions alone. It considered 702,893 catalog entries, excluded 12,446 explicit/classified non-UFO context entries, and retained 690,447 report candidates. Eligible phase dates: 659,616 UFO reports (287,170 stable; 372,446 phase-boundary ambiguous), 6,430 crops (2,750 stable; 3,680 ambiguous), 928 animals (404 stable; 524 ambiguous). All three domains have **zero verified sky-position observations**. These are whole-catalog QA counts; a live filtered query has its own denominators. Focused tests cover normalized `non_ufo_context` and explicit context flags even when display type/group labels look unknown.

## Independent nuclear chronology and facilities

Implementation: `analysis_nuclear.js`; builder: `scripts/build_nuclear_comparison_context.py`; compact runtime input: `data/analysis_comparisons/nuclear_context_v1.json` and gzip. Retained source captures, primary table audit, visual source checks, runtime QA and lifecycle purpose are under `data/analysis_comparisons/nuclear_sources/`.

The independent source is Bergkvist and Ferm, *Nuclear Explosions 1945–1998*, FOA/SIPRI, July 2000, report `FOA-R--00-01572-180--SE`. The original report is retained from a pinned transcription repository and has an [official IAEA record](https://www.iaea.org/inis/collection/NCLCollectionStore/_Public/31/060/31060372.pdf). Transcription commit: `056ac3db13b392cb69be9f787e235738167e7fb1`. Primary PDF SHA-256: `df9c1a2fb676a4b80de85a053e26dd434721cf8c4fc9d26f3548b1788eb39c1a`; CSV SHA-256: `1bdfb18cc41741e6c45c5bdfa3d70d8d0739e08b406c647aa1913ce013ee5b95`.

Coverage is **2,051 transcribed explosions**, 1945-07-16 through 1998-05-30, in seven country categories; 2,027 have usable locations. The report summary states 2,052 explosions and 715 Soviet entries; the transcription has 714 Soviet entries. The missing Soviet row remains missing. Primary table audit verifies 1,964 transcribed rows against parsed primary lines; 87 remain unverified. Missing positions, yields, purposes and position errors are not filled. No North Korean/post-1998 chronology or comprehensive reactor inventory is supplied.

Default comparison selects 1,917 weapons, peaceful and combat entries, of which 1,893 are located; 133 safety/mixed-safety entries and one unknown-purpose entry remain outside the default. Nuclear dates are GMT; report dates retain their source civil-date convention with unknown timezone. Earlier/same/later source dates do not establish event order.

The comparison separates unique reports from report–explosion pairs and presents before/same-date/after counts, distance bands, category/date-role/source breakdowns and same-site calendar controls. Controls match weekday and approximately season in adjacent years, require adequate source-period/window support, and exclude known explosions including safety events. Missing chronology is not proof that a control date was test free. Ratios use calendar window opportunity, not measured surveillance/reporting effort. Positional uncertainty and overlapping distance boundaries remain reported.

Four existing institutions have nuclear roles confirmed through retained official sources: Los Alamos National Laboratory, Lawrence Livermore National Laboratory, Oak Ridge National Laboratory and AWE Aldermaston. This is a reviewed partial US/UK institution inventory, not all nuclear sites. Institution identities/aliases are allowlisted; name keywords do not classify arbitrary facilities. Existing marker coordinates are retained. Opening/closing years retain boundary uncertainty, and historical organization activity does not prove daily unit operation. Broader military/research markers have unreviewed nuclear status and must not be called a verified nonnuclear control. Distances are marker distances, not site-boundary or radiation-exposure measurements.

`nuclear_sources/runtime_qa.json` records the real 702,893-row run, 1,917 selected chronology entries, 4,480 linked UFO reports, nonzero supported calendar controls and four reviewed nuclear institutions. Its recorded run took 9.955 seconds. Those results remain descriptive; strict inference is blocked by unknown position error, timezone mismatch, incomplete inventory and unmeasured reporting effort.

## Direct crop–animal comparison

Implementation: `analysis_cross_context.js`. It compares unique crop location/date clusters with unique animal location/date clusters; chronology trace connectors are not estimator inputs. Public-marker windows are 50 km/±7 days, 100 km/±30 days and 250 km/±30 days. A separate calendar-only lane admits exact dated reports without coordinates. The strict site lane retains original source/date/coordinate/independence gates.

Shared lineage, source incident identity/hash, source family, originating UFO record and originating publisher collisions exclude pairs. Distinct collection names do not prove independence. Duplicate markers are clustered before counting. Exact recorded date roles remain in sample pairs and coverage.

Matched controls use the same crop marker and month/day at −2, −1, +1 and +2 years. All four windows must fit inside the animal catalog's dated extent, and the observed window must be complete under selected date filters; February 29 is handled without silent rollover. Opportunity controls are descriptive, not surveillance denominators. Unknown coordinate uncertainty is separately counted and never assumed zero. Source centroids/public markers do not become measured event-site distances.

The real-context fixture has 3,579 public crop clusters and 308 public animal clusters, with 5, 8 and 19 marker pairs across the three windows; every one has unknown event-site uncertainty. Strict coverage remains one crop cluster and zero animal clusters. No p-values, causal effect, incidence estimate or Pattern Finder admission is produced.

## Rebuild and checks

Run from the frontend checkout using the retained shared workspace; replace `<shared canonical root>` with its literal path:

```text
py -3 scripts/build_analysis_comparison_context.py --source-root "<shared canonical root>"
<bundled Python with pypdf> scripts/build_nuclear_comparison_context.py --shared-root "<shared canonical root>"
py -3 scripts/build_analysis_comparisons_manifest.py --shared-root "<shared canonical root>"
node tests/test_analysis_lunar.mjs
node tests/test_analysis_lunar_real_artifacts.mjs "<shared canonical root>"
node tests/test_analysis_cross_context.mjs
node tests/test_analysis_nuclear.mjs
node tests/test_analysis_nuclear_real_artifacts.mjs "<shared canonical root>"
node tests/test_analysis_comparisons_worker.mjs
```

Lunar checks passed independently with frozen JPL references, epoch preservation, valid epoch zero, missing-date rejection, phase uncertainty, actual calendar opportunity, source-date roles, UTC gating, mutable iterators and worker/browser UMD loading. The real lunar receipt hashes its actual implementation, shared summary manifest, compact context gzip and offline ephemeris. Nuclear and cross-domain receipts/tests preserve their actual source pins and exclusions. Worker tests cover input preservation, scope, explicit epoch conversion, atomic artifact loading, hashes, cache identity and control input availability. The final integrated checks below were run after the current implementation and classification-gate fixes.

## Storage lifecycle and retention

Retain `data/analysis_comparisons/` as the small current local candidate, including source captures, manifests, audits, deterministic runtime projections and QA receipts. Each component has a documented purpose/rebuild method. Protect all unpushed implementation work and the shared canonical inputs/corrections/current repaired artifacts. No new file exceeds 100 MiB and no full corpus or bundle copy is created. No dataset, source capture or deployment deletion is authorized by this handoff.

The current local candidate is `analysis-comparisons-local-v1-20261007`, defined by `data/analysis_comparisons/manifest.json`, the root runtime modules and the retained repaired shared datasets. It is under review, not an additional accepted deployment. Production remains `dc834bac-2108-4de3-baad-47044e2ec51c`; the known-good rollback remains `78cc3660-5750-4685-a095-fee6dce37fbf`. No deployment or GitHub write occurred.

Approximate task disk growth is 16 MiB including the compact evidence/source captures, implementation, tests, handoffs and preview screenshots. New candidate data and the six new runtime assets total 15.3 MiB before the small final browser receipt. No new file exceeds 100 MiB. C: retains about 126 GiB free. No superseded staging or backup tree was created; no cleanup or deletion is proposed. Plain canonical JSON and deterministic gzip delivery have separate documented purposes, and neither is a corpus-sized rollback copy.

Future publication must include the six new root runtime assets, the comparison manifest/context/nuclear gzip payloads, and the existing SHA-pinned `data/analysis_v2/facility_analysis_v1.json.gz` delivery. The latter is reused from the shared canonical asset; its inherited source URL remains recorded as `sourceFile`. Do not run an old release preparer with a frozen asset allowlist and assume it includes this candidate. The whole-site presentation remains the retained preview overlay pending approval; its source is in the preview directory below.

## Final integrated verification

Live browser verification completed against `http://127.0.0.1:8168/whole-site.html#analysis-section-comparisons`. `data/analysis_comparisons/browser_qa.json` preserves the actual active cohort, runtime model counts, source hashes, default settings, geometry and observed interaction checks. The active craft-filtered cohort has 334,511 matched records and 334,397 eligible lunar dates; normalized non-UFO context categories no longer appear in the phase matrix. The independent nuclear inventory loads four reviewed institutions and 1,783 broader markers. This is an active-filter browser receipt, distinct from the complete 702,893-row engine receipts.

Verified all three question tabs and report-domain selectors; nuclear timing/category/institution subviews; recomputation at 7 days, peaceful explosions and 100 km; restoration to 30 days/all selected roles/500 km; sample-pair table disclosure preserving discovery/publication date roles; and transition back to Map Explorer with the existing map, legend and controls present. The requested 375 x 812 narrow viewport has no comparison-section overflow (377 px client and scroll width at the user's existing browser zoom). The viewport was restored.

Focused lunar/nuclear/crop-animal engine tests, real-model renderer tests, atomic artifact/worker integration, repaired Analysis scheduling/view checks, retained statistics/view/spatial concurrency regressions and syntax checks passed. Lunar and nuclear full-catalog receipts were regenerated after the final classification-gate fixes. Appearance labels such as fireball/meteor-like do not by themselves identify an astronomical explanation. Comparison loading errors retain a retry action, and failed partial loads do not replace validated evidence.

Preview source/proof directory: `C:/Users/jarod/.codex/visualizations/2026/10/06/01a112de-10d8-7230-b5ab-c5950201bd54/faithful-polish-preview/`. `serve_preview.py` references the shared canonical data rather than copying it; `analysis-navigation.js` registers Comparisons within Context catalogs. Retain `comparisons-moon-preview.jpg` and `comparisons-phone-qa.jpg` as small verification screenshots. This overlay and these observations are local QA, not user acceptance or publication.

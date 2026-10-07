# Guarded unmapped-record recovery research — 7 October 2026

This lane produces **218 accepted source-supported quality-view decisions: six map-reference recoveries and 212 text-only repairs**. The shared July31 canonical corpus, original source fields, narratives and dates are unchanged. Accepted decisions are a sparse sidecar, not a rebuilt catalog.

## Direct current native-ID SQL check

The existing 126,550,647-byte compressed UPDB SQL archive was streamed in place through `COPY api.location`, using the existing lookup parser. Only the currently requested IDs were retained: **44,524 unmapped records / 31,400 unique IDs**. Of those, **9,592 IDs exist** in the preserved table and **21,808 are absent** from this archive. Absence is bounded to this archive, not proof that a historical observation/location never existed or that another source version lacks the row.

| Initial screen | Current records | Unique native IDs |
|---|---:|---:|
| No row in preserved SQL |23,894|21,808|
| Native row not a populated-place feature |16,751|7,539|
| Native row has no coordinates |3,870|2,047|
| Populated-place city text initially disagrees |9|6|

The matched table subset is approximately 1.7 MB compact JSON, not a full SQL index or corpus copy. The SQL source SHA-256 is `4d14cc91d6329fce861bacdcd99787655ffacbb666f353daba2b70a42cfc71d2`. Requested-ID and parser hashes, actual retained rows and complete class counts are in `requested_updb_location_matches.json` and `native_updb_sql_recovery_screen.json`.

All nine populated-place candidates received original-account review. Four Istanbul rows share native ID 5466312 and a P/PPLA city authority. Their garbled city name strictly reverses to the SQL city name. Five others describe aircraft routes, offshore positions, an airport offset, or multiple radar/observer sites; their Boston/Hampton/Jacksonville/New Orleans city points are not safe observation locations and remain unapplied. SQL COPY escaped carriage returns explain several text mismatches, but repairing that comparison would not make those city points correct.

## Accepted recovery batch

| Source-supported scope | Records | Evidence and coordinate role |
|---|---:|---|
| Istanbul native-city recovery |4|Exact native-ID join, reversible city-text repair, country agreement, dated original accounts and [GeoNames P/PPLA city 745044](https://www.geonames.org/745044/istanbul.html). Points are reported-city references.|
| St Austell locality normalization |1|Raw source explicitly names town, Cornwall and United Kingdom. [GeoNames P/PPL town 2638853](https://www.geonames.org/2638853/st-austell.html) distinguishes the populated town from administrative features; the account's viewing site and sea object position are unknown.|
| Mojave/KMHV observer facility |1|Original account explicitly identifies the airport boneyard and KMHV; [FAA MHV Airport Master Record](https://www.gcr1.com/5010ReportRouter/MHV.pdf) supplies airport reference coordinates and labels latitude estimated. [FAA diagram](https://aeronav.faa.gov/d-tpp/2507/09353AD.PDF) identifies the facility in Mojave, California. Photographer and photographed-object positions are unknown.|
| Reversible location text only |212|Exact strict CP437→UTF-8 roundtrip repairs readable/searchable place text. No coordinates, source dates, original raw fields or narratives change.|

**The six map points are locality/facility reference markers at city precision, not measured observer or object positions.** Five use populated-place authorities; the airport uses a published facility reference. No county/province/country centroid, fuzzy city match, assumed bearing or guessed witness point was approved. Municipal checks corroborate [Istanbul's city identity](https://istanbuluseyret.ibb.gov.tr/istanbul-hakkinda/) and [St Austell's town context](https://www.staustell-tc.gov.uk/About_St_Austell_15216.aspx). Retained fact summaries and source-role limitations are in `reviewed_authorities.json`.

The compact-summary encoding screen covers all 44,524 currently unmapped UPDB records. It finds 239 diagnostic box/block-symbol rows; **216 rows / 188 distinct transformations** pass strict decoding, exact reverse roundtrip, meaningful non-ASCII-letter and no remaining damage/control-character gates. Four of those 216 are the individually reviewed mapped Istanbul rows; the other 212 are text-only. The remaining 23 are unchanged. Examples include Belém, Santo Antônio do Tauá, İstanbul, Ciudad de México and Gdańsk. Source display text, its hash and reconstructed payload bytes are retained; reconstructed bytes are decoding proof, not a claim that original CSV bytes were reread. No fuzzy geocoding follows these repairs.

## Sidecar contract and review limits

`accepted_recovery_decisions.json` SHA-256: `bee0969e833d595ab56dcda9a55f016f80dfdef0cc96492d8233a6c1026d0591`. All 218 rows have status `accepted_source_supported` and unique event/decision IDs. Each includes:

- `event_id`, `decision_id`, scope and confidence restricted to that scope;
- guards for source, stored sort date, original location text, latitude, longitude, coordinate source/precision and mapped state;
- sparse `set_fields`, evidence, authority/source-role notes and unchanged source-date context;
- canonical/summary manifest hashes, source chunk/detail locator and pinned detail gzip hash.

Unmapped compact summaries can omit latitude/longitude; null guards mean absent-or-null for those two fields. The consumer must reject a mismatching base manifest or guard. Text-only decisions set only `location_raw`; the six point decisions set reference coordinates, `has_coordinates`, `coordinate_source=reviewed_location_authority`, and `location_precision=city`, with explicit unknown exact observer/object positions. Base raw fields remain available. The sidecar itself applies nothing to canonical files.

`remaining_source_review_candidates.json` preserves the five route/multiple-site abstentions and six narrow narrative/secondary-field leads. One offshore account explicitly states 31°20′N, 70°W, but original-report/coordinate-resolution and aircraft-account discrepancies still require review, so its point is not accepted. Other leads include Lickdale road context, Barra da Tijuca neighborhood text, Libau's three-mile offset, source-spelled Maldonada/Uraguay, a Zoom Earth view URL and a nondecimal Handsworth grid-like field. Admin areas, image centers and offsets are not silently promoted to observation points.

## Validation, reproduction and storage

Validation checked 218 unique IDs/statuses, all 212 text-only roundtrip, unchanged date fields, unresolved guards, per-chunk hash locators, and the declared scope of all six reference points. Candidate totals, accepted decisions and unmodified unresolved records stay distinct. No canonical apply, full build, SQL index, geocoder, frontend edit or source-data mutation was performed.

Reproduce in order:

1. `python data/research/database_quality_20261006/unmapped_recovery/research_unmapped_recovery.py`
2. `python data/research/database_quality_20261006/unmapped_recovery/build_guarded_recovery_decisions.py`
3. `python data/research/database_quality_20261006/unmapped_recovery/finalize_recovery_report.py`

Retain this directory as the canonical research/decision artifact for the lane, along with the prior small unmapped audit and immutable source pins. Current and rollback deployments are unchanged. Output is approximately 2.3 MiB, below the 25 MiB lane limit; no new file exceeds 100 MiB. No new release/staging tree or superseded large artifact was generated, and no data cleanup is proposed. Retained reviewed-authority facts make the decision generation reproducible without relying on later changes to live authority pages.

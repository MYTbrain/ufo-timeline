# Exact populated-place recovery, 7 October 2026

This lane adds **795 supported locality-reference markers** for previously unmapped reports: **368 MUFON and 427 NUFORC**. These are references to the locality reported in the publisher's observation-location field. They are **not measured observer or object coordinates**, and do not establish a craft flight path. Dates, craft descriptions, source fields, original values and event identities are preserved.

The accepted sparse artifact is `accepted_gazetteer_recovery_decisions.jsonl`. Every decision carries eight original-value guards, the pinned base-manifest hash, a full detail locator and gzip hash, original publisher location evidence and its selected populated-place authority. It is suitable for the guarded quality view; this lane does not change the canonical catalog, packed map data, runtime bundle or live site.

| Stage | Report rows |
|---|---:|
| All currently unmapped summaries scanned | 122,110 |
| MUFON/NUFORC summaries in this lane | 29,434 |
| Parseable declared city/country and supported admin context | 12,274 |
| Exact primary/ascii populated-place name match, with all matching alternate-name features within a 4 km locality cluster | 2,578 |
| Accepted after full publisher-field, membership and narrative-role gates | **795** |
| International city reference lacks narrative locality corroboration | 1,529 |
| Route, military-site or non-observation narrative requires research | 129 |
| Publisher location field does not exactly reproduce the retained canonical field after escaping/whitespace normalization | 56 |
| Composite record requires retained-member review | 22 |
| Insufficient observation context | 36 |
| Individually identified narrative/form locality conflict | 11 |

The 2,578 full-source candidates were read from all **282 pinned detail chunks**, one chunk at a time. All candidate summary/detail identities, original-value guards and gzip pins matched. Earlier prototypes were tightened when qualitative source checks exposed geographically distant alternate-name homonyms and wrong form selections; their provisional totals are superseded by the final 795-row sidecar.

The query screen also withheld **1,104** rows with geographically separate exact same-name primary or alternate populated-place features. It did not select the largest city merely because its population was dominant. Another 8,581 parseable rows had no exact primary/ascii name match; 11 had unsupported populated-place feature types. These are research outcomes, not proof that a case is unmappable.

## Evidence and scope

The reference matcher uses only transparent case, spacing, punctuation and diacritic normalization. Country must be explicit. The United States, Canada and Australia additionally require an explicit supported state/province/territory. Other countries require a unique country-context locality cluster and an exact locality-name corroboration in the retained narrative. When an admin name is supplied, it must agree with an official GeoNames admin1 name/code. Raw publisher location fields must agree with the canonical observation-location label; no publisher address, departure location, prose mention or broad administrative center becomes a point automatically.

Only ordinary populated places and subdivisions are accepted. The reference-marker precision is `city`; neighborhood/subdivision references retain their feature code in the evidence. The same-name cluster's 4 km diameter is an ambiguity screen, **not an observer-position uncertainty radius**. Source stories may contain unreported observer offsets, transcription errors or other uncertainties. A finite reference coordinate cannot establish where an object was physically located.

The shared cached GeoNames archive was streamed in place and hashed. Primary/ascii names establish the selected reference; exact alternate names are used to catch distant homonyms. For example, the primary-name-only Tramore screen initially missed a distant alternative-name locality. The final method withholds that query.

Online official GeoNames documentation describes the [WGS84 coordinate and feature schema](https://download.geonames.org/export/dump/readme.txt). Current [admin1 names/codes](https://download.geonames.org/export/dump/admin1CodesASCII.txt) were retrieved as a 151,583-byte fact file and hashed. The [admin2 table](https://download.geonames.org/export/dump/admin2Codes.txt) was hashed while streaming, with only its 185 GB rows retained; this supports another lane's modern county-name checks and does not establish historical county equivalence.

Representative live reference checks agreed for [Twentynine Palms](https://www.geonames.org/5404198/twentynine-palms.html) and [Coeur d'Alene](https://www.geonames.org/5589173/coeur-d-alene.html). Municipal sources independently support the spelling and jurisdiction of [Twentynine Palms](https://www.ci.twentynine-palms.ca.us/about), [Coeur d'Alene](https://www.cdaid.org/government) and [Land O' Lakes](https://pascoeasypay.pascocountyfl.net/contact-us). These representative checks are not a claim that all 795 source pages or all reference features were independently retrieved online. Compact fact receipts preserve URLs, retrieval time and fact hashes; fact hashes are not represented as full-page byte hashes.

## Useful abstentions and next research

The original [NUFORC record 533](https://nuforc.org/sighting/?id=533) uses Twenty Nine Palms but describes military guard duty. It remains withheld for site/observer-role research. Other reviewed examples show a Mexican form city accompanying a Chichén Itzá photograph, an Austrian form city accompanying a Tehran military account, a Slovenian form choice explicitly substituted for Belgrade, and an airborne Alps photograph submitted under Sursee. These are real mechanisms by which indiscriminate geocoding could increase false pins.

The highest-yield next queue is the **1,529 international records with exact unique locality authority matches but no narrative locality corroboration**. Original report pages, attachments and archived source context may resolve them. The **11 explicit conflicts** deserve individual site research or a retained quality warning rather than reuse of the submitted form city. The 4,075 damaged/qualified city-label rows and 3,004 unsupported parenthetical qualifiers in the summary census also deserve parser-specific source research; parenthetical text is deliberately not discarded indiscriminately. The 92,676 rows from other source families were counted but are handled by the other lanes, not treated as failed recoveries here.

`gazetteer_screen.json` preserves every query-level result and authority ambiguity. `full_source_review_census.json` preserves every withheld candidate with its event locator. `verification_receipt.json` records **13 meaningful controls** and accepted-row invariants for all 795 decisions, including real Tramore homonym rejection, missing/contradictory jurisdiction, route/area input, unsupported parenthetic removal and word-boundary locality matching. The rebuilt source/country sample is a qualitative review aid; its size or outcomes must not be interpreted as a weighted yield estimate or a claim of manual review of the entire accepted cohort.

## Rebuild and storage

Run `py -3 data/research/database_quality_20261007/gazetteer_recovery/research_gazetteer_recovery.py scan`, then the same command with `review`. The rebuild reads shared `data/canonical_web` summary/detail gzip files and shared `cache/map_overlays/allCountries.zip`. The pinned compact admin fact files are retained inputs. A changed base manifest or source gzip hash fails the build before recovery approval.

The accepted sidecar plus this lane's census and evidence are the new canonical **lane analysis**. The untouched pinned source catalog remains its rollback; current validated production and its existing last-known-good rollback are retained by the parent task. Retain the query screen, accepted sidecar, census, controls, fact receipts, builder and review aids because they are compact reproducible evidence. The partial account-cluster index documents precisely which tuples were covered and which were not; no unscanned tuple is approved. Prototype files were overwritten in place, so there is no additional release, staging tree or backup directory to clean up.

New files total approximately **20 MiB** before the parent package inventory. No file exceeds 100 MiB, no existing corpus or runtime copy was created, and net disk growth attributable to this lane is approximately 20 MiB. No dataset deletion or cleanup is proposed.

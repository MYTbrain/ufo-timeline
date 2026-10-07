# Source-backed original-account recovery — October 7, 2026

This lane accepts **910 additional mapped archival references** and **4 date-precision corrections**. The 910 references are currently unmapped UPDB republications of already mapped original MUFON or NUFORC accounts. They improve inspection and provenance coverage; they are **not 910 newly discovered independent physical sightings**.

All decisions are sparse and guarded against the original served catalog. The canonical files and production website remain unchanged by this lane. The parent quality reader can apply the accepted decisions as a reversible view.

## What was recovered

| Original account authority | Accepted UPDB city references |
|---|---:|
| MUFON | 604 |
| NUFORC | 306 |
| **Total** | **910** |

The geography comprises 769 US references and 141 Canadian references. Each coordinate identifies an approximate **reported observer-city reference**, not a measured observer address or object position. The original place/admin fields, selected geographic authority, source account identity, before values, both detail locators and hashes remain in the decision.

Acceptance requires an explicit upstream native account pointer; a single ledger-consistent retained member at both endpoints; matching source-stated occurrence day verified in original date fields; significant narrative Jaccard of at least 0.8 with at least 20 shared significant tokens; matching nonempty craft labels; agreeing raw city/country context; and a populated-place reference matching the original point at five decimal places in the declared country/admin region. Exact administrative marker coordinates are excluded. The geographic role follows the [GeoNames feature definitions](https://www.geonames.org/export/codes.html).

The final geography screen also checks exact alternate names for distant homonyms. Every accepted locality has an exact-name same-admin reference cluster spanning at most 10 km. **95 otherwise eligible transfers were withheld** because the old geocode did not resolve that ambiguity; their full evidence is retained for research.

## Full-population screening, with source checks

| Stage | Account pairs |
|---|---:|
| Complete original-account crosswalk screened | 113,539 |
| Exactly one endpoint unmapped | 15,412 |
| Single-member identity/date/narrative/craft gates passed | 8,211 |
| Simple original city with agreeing target place/admin/country | 1,442 |
| Independent same-name/admin populated-place point matched | 1,236 |
| Original observer route context excluded | 84 |
| Original occurrence uncertainty excluded from transfers | 147 |
| Distant same-admin locality ambiguity excluded | 95 |
| **Accepted reference recoveries** | **910** |

Both endpoints of the 1,236 geographically matched candidates were checked in pinned full detail records across 282 existing gzip chunks. No full catalog or source archive was copied or expanded to disk. The counts above are this lane's finite population, not an estimated recovery rate for the remaining database.

Direct official-report checks include native IDs spanning early and recent NUFORC accounts. [Ashgrove, report 11415](https://nuforc.org/sighting/?id=11415), [Brier, report 112405](https://nuforc.org/sighting/?id=112405) and [Leading Tickles, report 166818](https://nuforc.org/sighting/?id=166818) independently confirm original report identity, source place and occurrence day for accepted transfers. These examples do not substitute for the record-by-record retained-source and geographic gates across all 910 accepted decisions.

The [Somerset account, report 10199](https://nuforc.org/sighting/?id=10199) confirms why an uncertain place name and interstate observer route should be withheld. Several other official URLs were inaccessible through the web tool; this is recorded as an access limitation, not evidence that those reports do not exist.

## Date quality improved by online originals

The retained NUFORC occurrence fields contain a generic “Approximate” suffix. Among the 1,236 examined original endpoints, **158 have occurrence uncertainty**, and the stored fields alone do not establish whether the uncertainty applies to date or time. The online originals are more explicit for four reviewed accounts; this lane does not establish whether that difference arose during archival processing or later publisher changes.

Individually verified official pages explicitly mark approximate dates for [Cotton, report 11277](https://nuforc.org/sighting/?id=11277), [Brier, report 11757](https://nuforc.org/sighting/?id=11757), [Laurel Springs, report 31901](https://nuforc.org/sighting/?id=31901) and [Gackle, report 40718](https://nuforc.org/sighting/?id=40718). Four primary-only decisions change `date_precision` from `exact_day` to `approximate`. They preserve the stored calendar day, guard the original precision and eight location fields, retain the pinned source locator, and preserve both the shortened archive text and official-page receipt. No observation date is invented and no precision change is silently propagated to a republication.

The remaining **154 approximation scopes remain review-only**. For example, [Nabb, report 109952](https://nuforc.org/sighting/?id=109952) still has a generic approximation label on the official page, so a date-precision overwrite is not justified.

## Work retained for further research

The compact review queue includes 3,440 reverse-direction pairs: the original account is unmapped while its UPDB republication has a point. These are promising leads, but the UPDB points may be administrative markers incorrectly presented as cities. An original account's native ID, narrative and declared place can support targeted municipal, geographic or publisher research; its existing UPDB coordinate alone cannot justify a transfer.

Other excluded pairs have composite source membership, observed-day conflicts, insufficient narrative agreement, craft-label conflicts, complex places, unsupported geography or observer routes. These exclusions do not mean they are unresolvable. The complete first-failure census is in `account_recovery_census.json`.

## Verification and retention

The independent contract check validates all 910 accepted decisions, the source/geographic gates, unique target/account identities and the absence of unsupported occurrence dates. It rereads all four actual pinned date-correction originals. Eleven policy controls and nine failure controls passed, including changed base hash, event ID, place, coordinates, unapproved candidate, invalid day and uncertain dates.

The current canonical artifacts for this lane are `accepted_account_recovery_decisions.jsonl` and `accepted_date_precision_decisions.jsonl`, with their census and validation hashes. The unmodified served catalog and prior quality layer remain the reversible baseline. No deployment or rollback release is created or replaced here, and no raw input or unique analysis is deleted.

New storage is approximately **5.3 MiB** including compact research receipts. No newly created file exceeds 100 MiB. No superseded large staging or backup directory exists, and no cleanup of protected data is proposed. The inventory records exact sizes/hashes. Normal rebuilds produce the small date-evidence ledger directly; the initial bootstrap only reread previously examined original endpoints whose compact date evidence had not yet been retained.

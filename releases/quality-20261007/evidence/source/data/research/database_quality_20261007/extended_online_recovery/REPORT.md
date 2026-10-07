# Extended online recovery findings — October 7,2026

This pass produces 26 additional map reference recoveries:20 from the 59 unresolved British grid records and six source-explicit ground observer reports at Fort Huachuca. Two of the same Fort records also receive date-precision downgrades. The remaining 44 reviewed records are withheld. These are record improvements, not 26 independently verified incidents.

Every recovered point remains at city/reference precision. Source dates, narratives, native IDs, raw coordinates, provenance, canonical membership and record counts are preserved. No source-coordinate rewrite, automatic merge or replacement event date is performed.

## British grid recoveries

Primary statutory/geological sources disambiguate the 16 locality groups below. The 20 restored points are the archival nominal grid references, not the authority landmarks used to corroborate the locality. All accepted source grids resolve at 1 km or finer. The original approximate OS projection and its independently checked prior receipt are pinned in the decisions; rounding/truncation remains unknown.

| Source locality | Records | Primary geographic evidence | Review implication |
|---|---:|---|---|
| Handsworth |3|[Handsworth Park, NHLE 1001473](https://historicengland.org.uk/listing/the-list/list-entry/1001473/)|Birmingham locality and Staffordshire history; absorbed into Birmingham in 1911. Sheffield namesake excluded.|
| Hall Green |3|[Three Magpies, NHLE 1245354](https://historicengland.org.uk/listing/the-list/list-entry/1245354)|Hall Green, Birmingham, beside the sourceSP 11/81 reference. Archival Warwick county label preserved.|
| Willian |1|[Three Horseshoes, NHLE 1347290](https://historicengland.org.uk/listing/the-list/list-entry/1347290)|Hertfordshire locality matchesTL 22/30. Original month-only date retained.|
| Ewell |1|[St Mary, NHLE 1277324](https://historicengland.org.uk/listing/the-list/list-entry/1277324)|Surrey locality matchesTQ 22/62; Temple Ewell excluded.|
| Penn |1|[Watercroft, NHLE 1124968](https://historicengland.org.uk/listing/the-list/list-entry/1124968)|Buckinghamshire locality matchesSU 91/93.|
| Wells |1|[NatWest, NHLE 1382952](https://historicengland.org.uk/listing/the-list/list-entry/1382952)|Somerset locality matchesST 54/45.|
| Rushton |1|[Upper Farmhouse, NHLE 1224437](https://historicengland.org.uk/listing/the-list/list-entry/1224437)|Shropshire locality matchesSJ 60/08.|
| Hanwell |1|[St Peter, NHLE 1216364](https://historicengland.org.uk/listing/the-list/list-entry/1216364)|Oxfordshire locality matchesSP 43/43; London namesake excluded.|
| Barnby |1|[St John Baptist, NHLE 1032106](https://historicengland.org.uk/listing/the-list/list-entry/1032106)|Suffolk locality matchesTM 47/89.|
| Weeton |1|[St Barnabas, NHLE 1149990](https://historicengland.org.uk/listing/the-list/list-entry/1149990)|North Yorkshire locality matchesSE 28/46 and resolves the otherwise blank county.|
| Ruspidge |1|[Methodist Church, NHLE 1213344](https://historicengland.org.uk/listing/the-list/list-entry/1213344)|Gloucestershire locality matchesSO 65/12. Original year-only date retained.|
| Norden |1|[War memorial, NHLE 1441459](https://historicengland.org.uk/listing/the-list/list-entry/1441459)|Rochdale locality matchesSD 86/14; archival Lancashire label preserved.|
| Badbury Rings |1|[Scheduled monument, NHLE 1002679](https://historicengland.org.uk/listing/the-list/list-entry/1002679)|Dorset hillfort matchesST 96/02; absence from populated-place lookup is not a location contradiction.|
| Isle of Grain |1|[St James, NHLE 1085755](https://historicengland.org.uk/listing/the-list/list-entry/1085755)|Wider Kent island/locality supportsTQ 86/76; landmark point is not assigned to the account.|
| Hog's Back |1|[BGS OR/15/004 locality research](https://earthwise.bgs.ac.uk/index.php/OR/15/004_Locality_description_and_interpretation)|Surrey ridge locality supportsSU 93/48 despite not being a populated settlement.|
| Colwell Bay |1|[JNCC Geological Conservation Review, volume 15, chapter 5](https://data.jncc.gov.uk/data/94dbee01-ece8-4587-a874-bd697d797388/gcr-v15-british-tertiary-stratigraphy-c5.pdf)|Isle of Wight coastal rangeSZ 327878–SZ 331887 supports the sourceSZ 32/88 reference.|

These recoveries resolve namesakes, omitted localities and non-settlement features. They do not establish measured observer/object coordinates or convert approximate dates into exact days. The primary-source format exceptions and bounded retention are recorded in `primary_geographic_fact_receipts.json`.

## Fort Huachuca ground observer references

The [original NPS nomination 74000443](https://npgallery.nps.gov/NRHP/GetAsset/NHLS/74000443_text) identifies the military reservation west of Sierra Vista in Cochise County. Page 4 gives six zone 12 UTM references for its historic district. Their mean supplies a rounded 0.01 degree named-installation reference; the historical datum is unstated. The retained marker is 31.55,-110.36 at city/reference precision. The old district lies within the source installation and is not asserted to contain every observer building.

Six independently reviewed native records explicitly place the observer on the ground at the installation: NUFORC 11424 and MUFON 67532,96993,67497,67612,67531. Their accounts describe a street, barracks quad, building, field or class vicinity. Exact witness buildings and object positions remain unknown. Some reports may form a repeated observer series; none is automatically merged or counted as an independently established incident.

Five other Fort-associated records are held: NUFORC 55808 describes an outside-base bypass; NUFORC 32455 and 59773 describe routes; MUFON 67533 contains dream/imagined-location material; MUFON 12847 names Middle Garden Canyon trail, whose more-specific observer location is not established by the old-post authority. No departure-point or imagined-position substitution is made.

## Date-precision corrections

Both source-language checks use the preserved native raw record and its full pinned digest; this review does not claim fresh retrieval of a live MUFON report or replacement date.

| Native record | Preserved source issue | Effective change |
|---|---|---|
| NUFORC 11424, event 263239566450658 |Occurred field says Local - Approximate; narrative gives only summer 1985.|`exact_day` to `approximate`; stored 1985-06-06 remains unchanged.|
| MUFON 67532, event 3222852598701040 |Observer questions March and suggests December holiday leave.|`exact_day` to `approximate`; stored 2000-03-10 remains unchanged.|

The additional precision guard prevents stale or unguarded date classification edits. No alternative month, day or year is inferred. These changes remove an unsupported exact-day claim while preserving original source chronology for trace inspection.

## Abstentions and useful remaining leads

All 59 British worklist records were reviewed. The 39 remaining British records include composite canonical membership requiring full member review; county conflicts that the reviewed authorities do not resolve; wider route/offset descriptions; and coarser 10 km references. Blank names or a nearby gazetteer point alone are insufficient.

Four encoded-coordinate conflicts are explicitly protected: Clifton 2003/native 227047 names Stainburn bypass while its grid/admin combination points elsewhere; Wanborough/native 48383 combines a Surrey label with a Wiltshire grid; Telegraph Hill/native 51506 has a Scottish grid against a Devon label; Lee Green/native 19921 has a Cheshire grid against Kent. Their existing points remain unassigned. Bray/Oxford, Brightwalton/Oxford, Heptonstall/Lancashire and Aston Ingham/Gloucester remain historical-administration leads rather than accepted restorations. These should be reopened only with dated boundary or original observer-location evidence that closes the specific contradiction.

## Verification and artifact status

The 26 decisions pass full-source digest and guard checks, exact summary/detail edit agreement, all source/date/native-ID preservation checks,210 stale-guard rejection controls and 108 invalid-operation controls. Eight important withheld records are asserted to remain excluded. The bounded UTM numerical check passes. There is no overlap with the prior 3,379 accepted IDs.

Final decision SHA256: `af33f5229ed47e9f3ed66ac46c96e827f7886e626c29b7c41ec262cab680b9f5`.

This sparse result is ready for parent quality-view integration. Canonical source bytes, existing view/deployment assets and retained rollback are unchanged. The lane adds approximately 3.7 MiB and no file exceeds 100 MiB. Retain the evidence and rebuilding contract as provenance; no large superseded artifact or cleanup operation is introduced.

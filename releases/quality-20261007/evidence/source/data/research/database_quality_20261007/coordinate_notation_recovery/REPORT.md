# Source coordinate notation and locality recovery

This continuation restores **10 map references**: eight UFOCAT records and two original NUFORC records. It also changes one source-confirmed date precision from exact day to approximate. Stored calendar dates, original forms, narratives, source identifiers, merge members and record counts remain unchanged. These are named-place references, not measured witness or craft positions.

The bounded queue contained 141 remaining unmapped UFOCAT records with raw coordinate text outside the British-grid convention. Eight receive supported points; **133 remain withheld**. Two independently identifiable original publisher records receive additional references. All candidates excluded the first pass's 3,379 changed records.

| Locality | Accepted representations | Basis and limits |
|---|---:|---|
| Ash Grove, Missouri | 2 | The original account explicitly describes a farm outside Ash Grove, Missouri, despite its Maryland form field. A municipality-area reference preserves the unspecified farm position and date disagreements. |
| Fareham, Hampshire | 2 | The retained original publisher form and distinctive narrative corroborate the UFOCAT locality. Invalid numeric notation is replaced by a municipality reference; no decimal separator is guessed. |
| Udine, Italy | 2 | Codebook interpretation of explicit degree/minute latitude and western-positive negative longitude agrees with the named city. Source datum and rounding remain unspecified. |
| Mishicot, Wisconsin | 1 | Explicit raw coordinates agree with Mishicot in Manitowoc County, Wisconsin; the Indiana administrative label is corrected. |
| Columbia Cross Roads, Pennsylvania | 1 | Explicit raw coordinates agree with the named Bradford County locality in Pennsylvania; the Maryland label is corrected. |
| Gravelbourg, Saskatchewan | 1 | Provincial and municipal evidence resolves the locality independently of malformed longitude. |
| Fort Oglethorpe, Georgia | 1 | The source's Catoosa County context and municipal evidence resolve its misspelled locality. A reference replaces the conflicting raw latitude without an automatic arithmetic correction. |

The [original NUFORC account 18233](https://nuforc.org/sighting/?id=18233) supplies the Missouri narrative and explicitly marks its date approximate. Its stored June 1, 1968 sorting anchor remains unchanged, while `date_precision` becomes `approximate`. The UFOCAT account carries a different June anchor, and the narrative describes the fall. These disagreements remain visible; this pass establishes no automatic account merge or date transfer.

Primary locality checks include [Ash Grove municipal government](https://ashgrovemo.socs.net/), [Fareham Borough Council](https://www.fareham.gov.uk/about_the_council/), [Manitowoc County communities](https://manitowoccountywi.gov/residents/community/communities-in-the-county/), [Udine municipal government](https://www.comune.udine.it/it/), [Gravelbourg municipal government](https://www.gravelbourg.ca/home.html), [Fort Oglethorpe municipal government](https://fortogov.com/city-manager/), and [Bradford County's Columbia Township page](https://www.bradfordcountypa.gov/208/Columbia-Township). The compact online receipts retain URLs, access times, factual scope and limitations; their hashes authenticate those extracted receipts, not the publishers' complete HTML pages.

GeoNames candidate facts were streamed from the existing, freshly hash-checked `cache/map_overlays/allCountries.zip`; only selected locality facts were retained. Every accepted jurisdiction requires a uniquely identified primary name and a compact same-jurisdiction alias cluster. Raw coordinates use the pinned UFOCAT codebook's blank-X3 Greenwich convention: north/west positive, south/east negative. No French-meridian conversion is used, and no malformed number is silently repaired.

## Withheld cases and access limits

Forty composite records require member-level review. Remaining holds include wrong-jurisdiction coordinates, distant homonyms, unparseable notation, and source-role conflicts. Wallops Island reports do not establish whether the relevant observer was at the postal locality, physical island or wider facility. NASA's [visitor guidance](https://www.nasa.gov/wallops/visitor-center/plan-your-visit/) distinguishes these places but cannot locate those witnesses. Rytro's [original account 148376](https://nuforc.org/sighting/?id=148376) describes an unidentified dock reached by kayak from Piwniczna; assigning a dock or town-center observer point would add unsupported specificity. A Daly City submission describes travel and observations at multiple places, and remains withheld.

Current requests for NUFORC 167561 and 63563 were inaccessible. The accepted Fareham decision uses the pinned retained original account, not a claimed fresh web retrieval. The full abstention queue remains in `unresolved_coordinate_worklist.json`.

## Rebuild, verification and retention

Run `extract_candidates.py`, `extract_place_authorities.py`, then `build_decisions.py`. They read shared canonical chunks, the existing gazetteer archive, retained publisher context and small online fact receipts in place. Source snapshots pin original full-record digests and compressed chunk locators. The lane validation checks all ten decision guards, seven malformed-notation rejection controls and four known-value/sign controls. The continuation integration receipt additionally checks the actual shared source chunks and exact summary/detail agreement.

Retain this sparse sidecar, source snapshots, selected authority facts, receipts, unresolved worklist and rebuild scripts as unique research provenance. They extend the current October 7 quality view; the October 6 local quality view remains the rollback. No canonical dataset, complete static bundle or production release is copied or changed. No superseded staging tree or protected-data deletion is proposed. Final sizes and hashes are recorded by the continuation artifact inventory.

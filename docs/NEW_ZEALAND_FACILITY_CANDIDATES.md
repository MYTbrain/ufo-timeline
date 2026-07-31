# New Zealand Base And Facility Candidates

Prepared: 2026-06-04

Purpose: source-backed candidate list for adding New Zealand military, defense, space, and research facilities to the map with temporal visibility fields. The app should only show these facilities when the selected timeline window overlaps the facility's active period.

## Local Schema Note

The current `military_bases.geojson` overlay is not yet temporal. It stores basic display fields such as `name`, `country`, `branch`, and `type`, but not `start_year` or `end_year`.

The richer `research_test_sites.geojson` schema already supports temporal fields:

- `start_year`
- `end_year`
- `date_precision_start`
- `date_precision_end`
- `historical_status`
- confidence and source notes

Recommended implementation path: either add New Zealand entries to the richer facility schema, or extend the military overlay schema/render path to honor the same temporal fields before adding more military-base rows. Do not duplicate Whenuapai; it already exists in the military overlay and should be enriched with temporal metadata.

## Recommended V1 Additions

| Facility | Category | Lat | Lng | Start | End | Temporal confidence | Add action |
|---|---:|---:|---:|---:|---:|---|---|
| RNZAF Base Auckland / Whenuapai | air base | -36.787778 | 174.630278 | 1937 | null | high | Enrich existing row |
| RNZAF Base Ohakea | air base | -40.206111 | 175.387778 | 1938 | null | high | Add |
| RNZAF Base Woodbourne | air/support base | -41.517900 | 173.870000 | 1939 | null | high | Add |
| Devonport Naval Base / HMNZS Philomel | naval base | -36.830241 | 174.786236 | 1841 | null | medium-high | Add |
| Linton Military Camp | army camp | -40.404400 | 175.581400 | 1942 | null | high | Add |
| Burnham Military Camp | army camp | -43.615000 | 172.315000 | 1923 | null | high | Add |
| Waiouru Military Camp | army camp/training area | -39.469167 | 175.681667 | 1939 | null | medium | Add |
| Papakura Military Camp | army camp/special operations | -37.049700 | 174.944100 | 1939 | null | high | Add |
| Trentham Military Camp | army/defence camp | -41.143500 | 175.036000 | 1914 | null | high | Add |
| RNZAF Station Hobsonville | former air base/seaplane station | -36.788874 | 174.671602 | 1928 | 2002 | medium-high | Add historic |
| RNZAF Base Wigram | former air base/training station | -43.551100 | 172.553000 | 1917 | 1995 | medium-high | Add historic |
| Waihopai Station | SIGINT/listening station | -41.576389 | 173.738889 | 1989 | null | high | Add |
| Tangimoana Station | SIGINT/radio interception station | -40.314722 | 175.249722 | 1982 | null | high | Add |
| Rocket Lab Launch Complex 1 | commercial space launch/test facility | -39.260917 | 177.865833 | 2016 | null | high | Add |
| Rocket Lab Launch Complex 1B | commercial launch pad | -39.260556 | 177.865250 | 2022 | null | medium-high | Optional child site |
| University of Canterbury Mt John Observatory | astronomy/research observatory | -43.986667 | 170.465000 | 1965 | null | high | Add if research observatories fit overlay scope |

## Source Notes

### Current NZDF Facilities

NZDF pages confirm current facility identity and historical context:

- Base Ohakea: `https://www.nzdf.mil.nz/defence-and-whanau/where-we-are/ohakea/`
- Base Woodbourne: `https://www.nzdf.mil.nz/air-force/where-we-are/woodbourne/`
- Base Auckland / Whenuapai: `https://www.nzdf.mil.nz/defence-and-whanau/where-we-are/whenuapai/`
- Linton Military Camp: `https://www.nzdf.mil.nz/defence-and-whanau/where-we-are/linton/`
- Burnham Military Camp: `https://www.nzdf.mil.nz/defence-and-whanau/where-we-are/burnham/`
- Waiouru Military Camp: `https://www.nzdf.mil.nz/defence-and-whanau/where-we-are/waiouru/`
- Papakura Military Camp: `https://www.nzdf.mil.nz/defence-and-whanau/where-we-are/papakura/`
- Trentham Military Camp: `https://www.nzdf.mil.nz/defence-and-whanau/where-we-are/trentham/`
- Devonport Naval Base: `https://www.nzdf.mil.nz/defence-and-whanau/where-we-are/devonport/`

Dates extracted from NZDF pages:

- Whenuapai/Base Auckland: established 1937.
- Ohakea: built during 1937-1939; historical section identifies RNZAF Station Ohakea as built in 1938.
- Woodbourne: established for the Air Force just before WWII; No. 2 General Reconnaissance Squadron operated there from September 1939.
- Linton: land purchased in 1941; first accommodation/tented use in 1942.
- Burnham: established 1923.
- Waiouru: WWII-era army training area; official page cites 1941 schools. Use 1939 as approximate start with medium confidence unless a stronger source is added.
- Papakura: established 1939.
- Trentham: tented camp first established 1914; first wooden huts built in March 1915.
- Devonport: official page states the base estate has been there since 1841; HMNZS Philomel naming transferred to the base in 1946.

Coordinates above are from public geospatial records, primarily Wikidata entities, because NZDF facility pages generally do not publish coordinate pairs.

### Historic RNZAF Sites

- Hobsonville: National Library topic page describes Hobsonville as established as a seaplane station in 1928 and integrated with Base Auckland in 1965. `https://natlib.govt.nz/records/22574552`
- Hobsonville 1928-2002 date range appears in public former RNZAF station lists; treat end date as medium confidence until confirmed by a stronger government/source document.
- Wigram: Christchurch planning/heritage documents and public aviation histories describe RNZAF use beginning in 1917 and RNZAF base closure in 1995. Useful sources:
  - `https://www.ccc.govt.nz/assets/Documents/The-Council/Plans-Strategies-Policies-Bylaws/Plans/district-plan/city-plan/CityPlan-OperativePlanChange46.pdf`
  - `https://resources.ccc.govt.nz/files/thecouncil/meetingsminutes/agendas/2015/april/chapter9naturalandculturalheritagesection32appendix8heritagestatementsofsignificancechristchurch.pdf`
  - `https://nzhistory.govt.nz/comment/12456`

### SIGINT / Surveillance Facilities

- Waihopai: GCSB page confirms radome/dish decommissioning while noting first dish operations in 1989 and continued other collection capabilities. `https://www.gcsb.govt.nz/news/gcsb-to-remove-dishes-and-radomes-at-waihopai-station`
- Tangimoana: National Library topic page describes Tangimoana as a GCSB radio communications interception station opened in 1982. `https://natlib.govt.nz/records/22493967`

### Space / Research Facilities

- Rocket Lab Launch Complex 1: public launch-site sources and Rocket Lab references place LC-1 on the Mahia Peninsula and identify 2016 opening / 2017 first launch activity. Use 2016 as site start, with 2017 available as first-launch note.
- UC Mt John Observatory: University of Canterbury pages confirm current observatory facility and coordinates; public observatory references give 1965 establishment.
  - `https://www.canterbury.ac.nz/research/research-facilities-and-equipment/field-stations/mt-john-observatory-field-station`
  - `https://www.canterbury.ac.nz/research/research-facilities-and-equipment/field-stations/mt-john-observatory-field-station/visit-the-observatory`

## Candidate Record Shape

Use this shape when adding to a temporal-capable facility overlay:

```json
{
  "name": "RNZAF Base Ohakea",
  "country": "New Zealand",
  "country_code": "NZ",
  "facility_type": "military_air_base",
  "branch": "air",
  "start_year": 1938,
  "end_year": null,
  "date_precision_start": "year",
  "date_precision_end": "unknown",
  "historical_status": "active",
  "temporal_confidence": "high",
  "coordinate_confidence": "medium_high",
  "source_urls": [
    "https://www.nzdf.mil.nz/defence-and-whanau/where-we-are/ohakea/",
    "https://www.wikidata.org/wiki/Q7277291"
  ]
}
```

## Implementation TODO

Status: implemented locally on 2026-06-04 for source and static bundle paths.

- NZ military bases were added as a military-overlay supplemental file: `new_zealand_military_facilities.geojson`.
- NZ SIGINT/space/observatory facilities were added as a research-overlay supplemental file: `new_zealand_research_facilities.geojson`.
- The existing GeoNames Whenuapai record is replaced at overlay merge time using `replaces_source_id: "geonames:6299998"` so the enriched temporal row does not duplicate it.
- Runtime temporal filtering now applies to both military and research/facility overlays via `start_year` and `end_year`, and trace facility-proximity indexing reads the same filtered overlay feature set.

Remaining smoke-check targets:
   - 1954 NZ window: Whenuapai, Ohakea, Woodbourne, Devonport, Burnham, Waiouru, Papakura, Trentham, Wigram, Hobsonville should appear if overlays are enabled.
   - 1990 NZ window: Waihopai, Tangimoana, active NZDF sites should appear; Wigram should still appear until 1995.
   - 2017+ NZ window: Rocket Lab LC-1 and Mt John should appear if research/space sites are enabled.
   - Pre-1914 NZ window: none of these should appear except Devonport if using the 1841 estate date.

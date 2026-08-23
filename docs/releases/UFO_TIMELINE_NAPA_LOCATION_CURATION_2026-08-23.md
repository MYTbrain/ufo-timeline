# UFO Timeline Napa Location Curation

Review date: 2026-08-23

Source: `majestic.csv`

Source ID: `Hatch_UDB_2481`

Source row: `11264`

## Outcome

The existing coordinate, `38.300002, -122.300006`, is retained as an
approximate Napa-area marker. The normalized state is corrected from Colorado
to California, the Hatch environment category `Farmlands` is removed from the
place label, and coordinate precision is lowered from exact coordinates to
city/observer-vicinity precision.

Contemporary source review also changes the normalized time from `10:50` to
`10:45` local and clears Hatch's unsupported duration value. Every original
Hatch field remains unchanged in raw provenance.

## Stable identity

- Canonical event ID: `evt_49c65297c6a08bd6ff910e2d`
- Numeric event ID: `3483027136344169`
- Canonical input ID: `cin_2117d48199668f694e7c1a29`
- Source row hash: `fc1a2224bc69a9810773e1034a2e0d8ae5a4de36`

The correction is applied only after deduplication establishes event identity.
It is guarded by the stable source identifiers and exact expected raw fields,
and fails closed if the imported source row changes.

## Source evidence

Loren E. Gross transcribed a report from the *Napa Register*, published July
29, 1952. The transcription identifies John Foraythe of 1512 A Street, Napa,
and says he observed a metallic, disc-shaped object at 10:45 a.m. on Sunday,
July 27. The object was estimated at 20,000 feet, moved west at great speed over
Napa Valley, tilted so its thin edge faced him, and disappeared in haze. His
report to the local sheriff's office was forwarded to Hamilton Field airbase.

- [Gross supplemental volume, printed page 50 / PDF page 51](https://sohp.us/collections/ufos-a-history/pdf/GROSS-1952-July-21-31-SN.pdf#page=51)
- [Gross collection provenance](https://sohp.us/collections/ufos-a-history/)
- [Napa Register issue, July 29, 1952](https://cdnc.ucr.edu/?a=d&d=NVR19520729)

The newspaper transcription does not state a duration. It also does not give
the observer's exact position or the object's exact aerial position.

## Map decision

The Hatch coordinate is a round DMS-derived point (`38°18′N, 122°18′W`). An
official U.S. Census reverse-geography lookup places it in Napa city, Napa
County, California. It is also approximately 0.4 km from the Census-geocoded
current address range for 1512 A Street. This is enough to validate the Napa
placement, but not enough to represent the point as an exact sighting site.

- Display: `Napa Valley near Napa, Napa County, California, USA`
- Structured city: `Napa`
- State: `California`
- Country: `USA`
- Coordinate: unchanged at `38.300002, -122.300006`
- Precision: `city`
- Marker meaning: approximate Napa observer vicinity, not a reconstructed
  object track

[U.S. Census reverse geography for the retained point](https://geocoding.geo.census.gov/geocoder/geographies/coordinates?x=-122.300006&y=38.300002&benchmark=Public_AR_Current&vintage=Current_Current&format=json)

## Normalized event facts

- Date: 1952-07-27
- Time: 10:45 a.m. local
- Witness spelling: `John Foraythe`, preserved as printed/transcribed
- Report route: local sheriff's office, then Hamilton Field airbase
- Object: metallic disc
- Reported motion: west at great speed over Napa Valley
- Estimated altitude: 20,000 feet
- End of observation: tilted edge-on and disappeared in haze
- Duration: unknown

No corroborating witness, image, angular size, numeric speed, track endpoints,
or official investigation result was located. The report remains a traceable
historical sighting report, not a high-confidence anomalous case.

## Regression coverage

The tests verify that:

- reviewed values reach normalized export, detail chunks, summary shards,
  packed points, and chronology;
- the source coordinate and stable event IDs do not change;
- raw `Colorado`, `Farmlands`, `10:50`, and duration `1` remain auditable;
- stale source rows fail closed; and
- static QA now detects full-state-name coordinate contradictions such as the
  original `Colorado, USA` label on a Napa coordinate.

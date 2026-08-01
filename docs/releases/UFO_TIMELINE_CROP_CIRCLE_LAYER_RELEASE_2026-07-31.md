# UFO Timeline Crop Circle Layer Release — 2026-07-31

## Outcome

Crop circles are now an optional, lazy-loaded map layer in the UFO Timeline.
The user enables the layer from Map Overlays, sees uncertainty-coded crop-circle
locations alongside UFO sightings, and opens a dedicated detail card containing
an event-specific, measurement-informed schematic plus date, location, size,
crop, morphology, provenance, and source links.

## Runtime contract

- The layer is off by default.
- No crop-circle manifest, point index, detail record, schematic, or photograph
  request occurs during normal app startup.
- First enable fetches one manifest and a 92 KB gzip point index for 4,305 mapped
  records.
- Opening a point fetches one of 31 detail chunks; the largest is about 41 KB
  gzip and the five most recently used chunks are retained in memory.
- Source photographs are never preloaded. Only 13 links explicitly marked as
  embeddable by the export can be loaded, and only after a user presses the load
  button.
- Schematics are generated locally from the individual record's catalog
  morphology measurements. They are labeled as approximations because the
  interoperability export contains no distributable diagram pixels.

## Data coverage

| Record class | Count |
| --- | ---: |
| Conservative crop-circle entities | 7,745 |
| Mappable entities | 4,305 |
| Reviewed/corroborated exact fields | 10 |
| Provisional candidate fields | 409 |
| Locality centroids | 3,886 |
| Lazy detail chunks | 31 |
| Rights-permitted image links | 13 |

Marker styling deliberately exposes spatial uncertainty:

- solid: reviewed/corroborated exact field;
- dashed: provisional candidate field;
- hollow: locality centroid, not the formation site.

The existing coordinate-precision control keeps only the 10 exact crop-circle
locations when enabled. The existing exact-date control and Timeline date
window also filter this layer.

## Scientific and interaction safeguards

- Every crop-circle record remains `trace_eligible: false` and
  `trace_role: context_only`.
- Crop circles never enter same-day craft traces or chronological-hop expansion.
- Craft-type color mode uses a fixed crop-circle purple rather than pretending
  crop circles are a craft type.
- Chronology color mode may color fills by date while retaining a distinctive
  purple outline.
- No maker, mechanism, authenticity, or UFO origin is inferred.

## Validation

- JavaScript syntax checks pass for the app shell, bootstrap, and lazy runtime.
- Python syntax and a full artifact rebuild pass.
- All 4,305 point rows resolve to one of the 7,745 validated detail records.
- Exact/candidate/locality counts reproduce 10/409/3,886.
- Rights enforcement confirms that gated image links have no runtime image URL.
- A Node runtime harness verifies zero data requests before enable, date and
  coordinate filtering, 4,305-point rendering, 10-point exact filtering, lazy
  detail fetching, schematic rendering, and clean disable behavior.

## Deployment layout

The Pages app shell contains the crop-circle manifest and lazy runtime code.
The point index and detail chunks use the immutable R2 prefix
`releases/crop-circles-v155-20260731/`, independently of the UFO catalog release.

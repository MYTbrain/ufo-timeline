# UFO Timeline Crop-Circle Descriptions and Chronology Release — 2026-07-31

## Outcome

This release replaces the crop-circle layer's generated description treatment
with source-backed narratives where an event-specific narrative is available,
changes the map symbol to a high-contrast spiral that cannot be confused with a
UFO craft color, groups records that share a mapped position, and adds a
separate opt-in crop chronology. Crop circles remain excluded from every UFO
trace and chronological-hop pathway.

## Source descriptions

The detail card now distinguishes two different things:

- **Source description** is a short event-specific excerpt from a linked ICCRA
  record page.
- **Catalog summary** is generated context about location confidence,
  morphology, and interpretation limits. It is never labeled as a description.

The public runtime carries no page HTML or full article text. Each source
excerpt is sentence-aware and capped at 25 words, with an explicit short-excerpt
label when the source narrative continues. Every excerpt links to its source
page. Safe concise credits may be displayed; longer attribution stays on the
source page.

| Description audit | Count |
| --- | ---: |
| Candidate source assertions | 572 |
| Formation records with source narratives | 564 |
| Preserved source-description assertions | 566 |
| Duplicate formations retaining two assertions | 2 |
| Source/date mismatches quarantined | 5 |
| Source page unavailable | 1 |

All 31 source pages that the first parser missed but that contained a usable
narrative were recovered through a bounded legacy-page fallback. The final
audit found no empty, over-limit, URL-contaminated, metadata-contaminated, HTML,
control-character, invalid-crop, or unsafe display-credit excerpt.

The Colorado Antonito record now displays the actual source narrative:
“Twelve circles in pasture grass discovered near a cattle mutilation.
Eyewitness report only.” The source credit is Jeffrey Wilson and the crop is
grass.

Records without a captured source narrative say so explicitly. They do not
substitute generated boilerplate.

## Marker and selection design

- 4,305 mapped records are grouped into 2,541 selectable positions.
- The marker is a charcoal/ivory/acid-lime spiral, invariant across UFO color
  modes.
- A solid center means a reviewed/corroborated exact field, a dashed ring means
  a candidate field, and a dotted ring means a locality centroid.
- Shared positions open a date-ordered record chooser instead of stacking
  indistinguishable markers.
- The shared Canvas and its pane are noninteractive. A bounded hit test consumes
  a click only when the pointer is on a crop spiral, so blank-map clicks, UFO
  point/cluster clicks, and Area Select keep their existing behavior.

The Canvas layer remains mouse/touch operated. A keyboard-accessible crop record
search/list is a separate follow-up because Canvas paths have no focus targets;
the chooser and detail-card controls themselves use native buttons.

## Separate crop chronology

Crop chronology is off by default and uses its own controls, renderer, pane,
state, status text, and cleanup lifecycle. It never writes to the UFO trace or
hop state.

Available relations:

- same catalog day, drawn as an undirected minimum spanning forest;
- same day plus the next 7 catalog days; or
- same day plus the next 30 catalog days.

Later-date adjacency is drawn with dashed acid-lime lines and arrows. Same-day
links are solid and arrow-free. The default coordinate scope includes exact and
candidate fields only; locality centroids require an explicit opt-in. Distance
limits of 100, 250, 500, and 1,000 km and zoom-dependent viewport caps keep the
overlay inspectable.

Only exact-day catalog dates are eligible. The interface repeatedly states that
catalog dates may be discovery, report, or publication dates and may lag actual
formation by days or weeks. Links indicate catalog-date adjacency only; they do
not imply formation time, causation, travel, or authenticity.

## Runtime artifacts

| Runtime class | Count or size |
| --- | ---: |
| Conservative crop-circle records | 7,745 |
| Mapped records | 4,305 |
| Grouped mapped positions | 2,541 |
| Exact fields | 10 |
| Candidate fields | 409 |
| Locality centroids | 3,886 |
| Exact-day chronology-eligible records | 3,655 |
| Lazy detail chunks | 31 |
| Point index, gzip | 92,355 bytes |
| Largest detail chunk, gzip | 50,851 bytes |
| All 32 R2 payloads | 1,575,726 bytes |

Immutable crop release:
`releases/crop-circles-v156-20260731/`.

The Pages manifest is small and loads with the application shell. The point
index loads only when Crop circles is enabled, and one detail chunk loads only
when a record is opened. The 32 gzip payloads remain R2-only and are forbidden
from the Pages directory.

## Release safety and validation

- All 32 local R2 payload hashes and byte counts match the v156 manifest.
- Every point resolves to one of 7,745 validated detail records.
- The Antonito sentinel, both duplicate-description records, and all five
  quarantined mismatches pass explicit tests.
- The complete 11-suite JavaScript regression set passes.
- The focused Python release set passes: 88 tests and 4 subtests.
- The exact hydrated Pages candidate contains 131 files, parses every required
  JSON route, excludes every crop R2 payload, and has tree SHA-256
  `26c07fb94ed5d4e67235068332c0c68b62cfa27f3ba078ed03f27f73a0ebf969`.
- The immutable R2 publisher preflights every object, skips a matching object,
  refuses to overwrite a mismatched object, uploads only a missing object, and
  verifies every public hash after upload.
- The Pages deploy wrapper refuses the raw `webapp/static_public` directory and
  validates the exact hydrated inventory before invoking Wrangler.

Production remains unchanged until the v156 R2 objects are public and verified,
the exact Pages candidate is deployed and checked at an immutable preview URL,
and that unchanged candidate is promoted to the production branch.

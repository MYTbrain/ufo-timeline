# Production location-label audit — 2026-08-24

## Scope

This audit scanned every event in the immutable production release
`coordinated-reliability-v152-20260731`: 702,893 summary records across 71
shards. The attached 54,751-event historical bundle was retained as supporting
source evidence, not substituted for the full production catalog.

The audit is deliberately about rendered location labels. It does not infer
that a coordinate is wrong merely because source text is malformed, and it
does not rewrite `location_raw`, source rows, source identifiers, canonical
identifiers, or coordinates.

## Baseline findings

The report-only audit found 77,501 events with at least one label concern and
86,906 finding rows.
Several concerns can apply to the same event.

| Finding | Events | Disposition |
| --- | ---: | --- |
| Adjacent duplicate component | 24,072 | Safe display normalization |
| Empty comma component | 17,573 | Safe when another place component remains |
| Missing or unusable label | 16,221 | Source-review queue; no place invented |
| Majestic environment category prefix | 14,564 | Safe display normalization |
| Redundant U.S. state components | 6,935 | Safe display normalization |
| Contradictory U.S. state components | 2,402 | Uncertainty display; conflicting states omitted |
| Coordinate literal used as place | 1,962 | Source-review queue |
| Repeated non-adjacent component | 1,764 | Safe display normalization |
| Damaged/control character | 836 | Source-repair queue; no guessed spelling |
| Placeholder alongside real context | 551 | Safe display normalization |
| Excessive location components | 22 | Review queue |
| Overlong narrative in location | 3 | Individually reviewed below |
| Markup or URL in location | 1 | Safe display normalization |

Majestic's `Locale` values are environmental classifications rather than place
names. The affected prefixes include `Farmlands`, `Pasture`, `Residential`,
`Town & City`, `Metropolis`, `Coastlands`, and similar categories. This is the
systemic source of the original Napa label's `Farmlands` prefix.

## Implemented display policy

The post-deduplication policy `location-label-structural-v1` creates or improves
`location_display` only when the structural interpretation is unambiguous. In
the v152 preview it improves 68,651 events:

| Transformation | Events |
| --- | ---: |
| Remove adjacent duplicate components | 24,066 |
| Remove empty components | 17,573 |
| Remove Majestic environment category | 14,564 |
| Remove redundant U.S. state components | 5,909 |
| Omit mutually conflicting U.S. state components | 2,320 |
| Remove repeated non-adjacent components | 1,775 |
| Remove placeholder components | 551 |
| Unwrap a Markdown location link | 1 |

For contradictory state labels whose comma structure can be safely parsed, the
policy does not pick a winner. It displays the remaining place and country
while retaining the complete contradictory source claim in `location_raw`.
Ten parenthetical labels and one unusually structured redundant-state label
remain in the review queue because deleting their comma-delimited state tokens
would damage the displayed text. Coordinate QA also falls back to
`location_raw`, so this display treatment cannot hide a state/coordinate
conflict.

Labels consisting only of commas, placeholders, or a Majestic environment
category remain unmodified and are classified as missing/unusable. Damaged
character sequences and coordinate-only place labels also remain review items.

## Individually reviewed field-shift defects

Three production labels exceeded 180 characters because a narrative had been
shifted into the source location field. Each correction is fail-closed against
the production event/input IDs, singleton topology, source row identity, row
hash, and exact location/description hashes.

| Source ID | Reviewed display | Precision |
| --- | --- | --- |
| `Overmeire_1022` | Oslofjord, about 30 km from Oslo, Norway | Region; unmapped |
| `Magonia_811` | Interstate 64 near Dunbar, West Virginia, USA | City; unmapped |
| `Overmeire_2808` | At sea between St Kilda and Barra, Outer Hebrides, Scotland, UK | Region; unmapped |

The original narratives remain in `location_raw` and `raw_fields`. No point
coordinate was introduced for these regional or source-limited accounts.

## Reproducibility and release boundary

Run the report against an unpacked static payload:

```bash
python scripts/audit_static_location_labels.py \
  --payload-root /path/to/release/payload \
  --json-output /tmp/static_location_label_audit.json \
  --csv-output /tmp/static_location_label_audit.csv
```

The build manifest records the display-normalization policy counts, and detail
records carry per-event transformation metadata. This change does not overwrite
or deploy the immutable v152 release; production output changes only after an
authorized rebuild and publication.

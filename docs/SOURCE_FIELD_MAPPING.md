# Source Field Mapping Draft

This is a Phase 1 draft generated from column-name heuristics and sample values. It is not a final adapter contract.

Machine-readable mapping:

```text
data/canonical/source_column_mapping.json
```

Unmapped/source-specific review queue:

```text
data/canonical/unmapped_fields_report.json
data/canonical/unmapped_fields_report.csv
```

## Mapping Actions

`canonical` means the field likely maps to a current normalized event field such as date, time, location, source, description, latitude, longitude, or source URL.

`source_claim` means the field should become a provenance-linked claim rather than a single lossy scalar. Examples include shape, craft/object type, direction, speed, altitude, witness, evidence, credibility, reliability, strangeness, status, and classification.

`source_specific` means the field is non-empty and must be preserved even if not normalized yet.

`ignore_empty` means the column was empty in the observed source file.

## Adapter Requirements

Each source adapter must:

- Preserve complete raw row JSON, including empty fields.
- Preserve source row number and stable row hash.
- Preserve overflow columns and malformed row shape information.
- Emit mapped canonical fields.
- Emit source claims for claim-like fields.
- Keep every non-empty unmapped field under source-specific storage.
- Emit parse warnings instead of dropping records.

## Current Builder Behavior

`scripts/build_canonical_ufo_dataset.py` now consumes this mapping file by default.

Columns marked `source_claim` are emitted to `source_claims.jsonl` as provenance-linked claims with:

- `origin: source_column_mapping`
- original `source_field`
- original `raw_value`
- audit mapping role
- stable `source_claim_id`

Columns marked `source_specific` remain preserved in each source record's complete raw row. The canonical build also emits `canonical_column_accounting.json` so these preserved values can be audited by source file.

The mapping is still a draft. It should be refined from `canonical_column_accounting.json`, `unmapped_fields_report.json`, and human review rather than treated as a final semantic contract.

## Known Risk Areas

`majestic.csv` contains many `key_vals/*`, `attributes/*`, `location/*`, `ref/*`, and `see_also/*` fields. These should not be flattened away; they need either structured source-specific preservation or explicit source claims.

`ufocat2023.csv` has rich fields such as `HYNEK`, `VALLEE`, `SVP`, `TYPE`, `EXPL`, `OBJS`, `DUR`, `SIZE`, `COLOR`, `SHAPE`, `SOUND`, witness fields, and coordinates. These are high-value metadata and should become source claims or normalized facets.

`nuforc.csv` and `nuforcpy.csv` each have one row with extra CSV columns. The adapter must preserve those overflow values with the source row rather than dropping them.

`mufon.csv` and `nuforc.csv` are exact subset candidates, but the import pipeline should verify that from the audit report before skipping them.

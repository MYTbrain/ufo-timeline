# Craft Type Classification Cleanup Plan

## Goal

Reduce the practical impact of vague `Unknown` type labels without rewriting
source evidence. The app should preserve original `type_raw`, `type_normalized`,
`shape_raw`, `shape_normalized`, descriptions, and source text, while adding a
derived craft classification layer for filtering, visualization, trace styling,
and future same-day sequence matching.

## Current Audit

Latest report artifacts:

- `data/reports/unresolved_craft_type_by_source_current.json`
- `data/reports/unresolved_craft_type_by_source_after_plural_morphology.json`
- `data/reports/unresolved_craft_type_by_source_after_multilingual_morphology.json`

Measured against
`data/canonical_full_maximal_v3_rehydrated_jurisdiction_repair/deduped_events.jsonl`:

- Events scanned: `703,018`
- App-facing `Unknown` events: `328,690`
- Derived `unknown` events before this morphology pass: `140,573`
- Derived `unknown` events after this morphology pass: `137,343`
- App-facing `Unknown` still unresolved after this morphology pass: `114,409`

Rebuilt web artifact counts after the latest conservative classifier pass:

- Web events: `703,018`
- Mapped events: `580,703`
- Manifest `unknown` craft bucket: `124,762`
- Manifest `unknown` craft bucket before this pass: `127,853`
- Net manifest gain from this pass: `3,091` fewer `unknown` craft rows

Most remaining unresolved records either lack direct craft-shape evidence, use
event-category/source codes rather than craft shape, or explicitly describe
conventional/prosaic outcomes such as aircraft, meteor, balloon, satellite, or
Venus. These should not be forced into craft-shape buckets.

Latest source-specific pass:

- Added UFOCAT codebook-backed decoding for explicit morphology subcodes such
  as `2D`/`3D`/`4D`/`5D` disc, `2C`/`3C`/`4C` cloud-cigar, `2Z`/`3Z`
  crescent, and meteor/fireball subcodes.
- Added a `non_ufo_context` derived bucket for UFOCAT `TYPE` codes beginning
  with `0`, which the UFOCAT codebook defines as non-UFO/context records.
- Added source-gated conventional/astronomical UFOCAT subtype handling for
  codes such as Venus, star, comet, and satellite. These do not become craft
  shapes.
- Expanded exact legacy SHAPE handling for unambiguous morphology values such
  as `Wedge`, `Wing`, `U-Shape`, `Banana`, `Missile`, `Bell`, and
  `Dumbbell`.
- Net full-audit gain from this pass: `21,218` additional app-facing Unknown
  rows recovered, with UFOCAT remaining Unknown reduced from `97,386` to
  `78,241`.

Latest morphology pass:

- Added conservative plural and spelling variants for direct shape terms such
  as `discs`, `disks`, `saucers`, `globes`, `cylinders`, `pyramids`,
  `triangles`, `cross-shaped`, `rectangular`, and `roundish`.
- Added conservative direct non-English shape terms seen in the corpus, such
  as `lumiere`, `luces`, `licht`, `boule`, `kugel`, `esfera`, `disco`,
  `disque`, `scheibe`, `cilindro`, `cylindre`, `zylinder`, `triangulo`,
  `triangulaire`, `dreieck`, `rectangulaire`, `ovalado`, `diamante`, and
  `losange`.
- Did not classify vague terms such as `craft`, `entity`, `occupants`,
  `metallic`, or `silver`, because those do not safely identify a craft shape.

Important caveat: recoverable does not mean safe for every downstream use.
Generic `light` evidence is useful for display, but weak for same-day matching.

## Derived Fields

Add these fields during canonical/web artifact generation:

- `craft_type_inferred`
- `craft_type_label`
- `craft_type_confidence`
- `craft_type_source`
- `craft_type_reason`
- `same_day_match_strength`

Suggested values:

- `craft_type_confidence`: `high`, `medium`, `low`, `none`
- `same_day_match_strength`: `strong`, `medium`, `weak`, `none`

The source display text remains unchanged. These are derived analysis fields.

## Candidate Craft Buckets

V1 buckets from the audit script:

- `triangle`
- `disc_saucer`
- `sphere_orb`
- `cigar_cylinder`
- `rectangle_box`
- `chevron_boomerang`
- `oval_egg`
- `teardrop`
- `cone`
- `diamond`
- `formation`
- `fireball_meteor_like`
- `dumbbell_barbell`
- `non_ufo_context`
- `conventional_or_explained`
- `light`
- `unknown`

For same-day trace/sequence support, use only medium/high confidence evidence
with `same_day_match_strength` of `medium` or `strong`. Do not use generic
`light` as strong evidence.

## Triage

### Phase 1: Source-Preserving Data Layer

- Keep `scripts/audit_craft_type_inference.py` as the report/audit entrypoint.
- Move the inference rules into a reusable parser module or canonical artifact
  helper.
- Add derived craft fields to canonical web summary/event artifacts.
- Add regression tests for representative shape/description patterns.

### Phase 2: UI Filtering And Visualization

- Add a craft-shape color mode distinct from current broad `Type` grouping.
- Add optional craft-shape filter chips or a compact filter group.
- Keep the existing source type filters intact.
- Let points, clusters, heatmap, and results use the derived craft bucket when
  the user chooses craft visualization.

### Phase 3: Trace Styling

- Add trace color modes by derived craft bucket where a trace has reliable
  endpoint craft evidence.
- For mixed/unknown endpoints, use neutral or split encoding rather than
  inventing certainty.
- Keep existing temporal and facility-proximity trace colors available.

### Phase 4: Same-Day Chronology Support

- Use derived craft type as a tie-breaker only when confidence is sufficient.
- Do not reorder events solely by generic `light` labels.
- Preserve stable fallback for weak/unknown craft evidence.

## Constraints

- Do not mutate source rows.
- Do not replace source-displayed type/shape text.
- Do not collapse uncertain sightings into overly specific craft labels.
- Do not use weak generic evidence to make high-confidence chronology claims.

## Next Implementation Slice

Phase 1 artifact propagation is complete for the current conservative
classifier pass: `data/canonical_web`, `static_bundle`, startup profiles, and
`cloudflare_bundle_r2` have been rebuilt from the active deduped source.

Continue cleanup in this order:

1. Review the remaining `phenomenainon_updb` unresolved pool for source-native
   shape fields or safe description patterns.
2. Review the remaining `mufon` unresolved pool for source-native shape fields
   or safe description patterns.
3. Review the remaining `majestic` and `nuforc` pools only where direct shape
   evidence exists.
4. Add one optional display/debug surface for derived craft classification.
5. Keep rejecting vague material/color/occupant terms unless they directly
   describe shape.

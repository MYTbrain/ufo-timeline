# Data Archive Plan

This project has a very large `data/` directory because prior dedupe, mapping,
time-normalization, coordinate-repair, entity-resolution, and static-payload
passes wrote full candidate snapshots instead of mutating the canonical corpus
in place.

The active app and deployment path should keep:

- `data/canonical_full/`
- `data/canonical_web/`
- `data/reports/`
- `data/canonical/`
- `data/canonical_smoke/`
- `data/manual_location_overrides.json`
- `data/normalized_events.json`
- `data/map_events.json`
- `data/sample_inputs/`
- source folders such as `webapp/`, `scripts/`, `tests/`, `static_bundle/`,
  and `cloudflare_bundle_r2/`

Generated candidate snapshots can be archived out of the active workspace.
These are useful for audit/rollback history, but they are not required for
normal UI changes or Cloudflare Pages/R2 deployment when the current
`canonical_full` and `canonical_web` outputs are already present.

Archived candidate patterns:

- `data/canonical_preview*`
- `data/canonical_time_norm*`
- `data/canonical_web_time_norm*`
- `data/canonical_web_mapping*`
- `data/canonical_web_static*`
- `data/canonical_web_manual*`
- `data/canonical_web_remaining*`

Archive destination used for this cleanup:

`C:\Users\jarod\Desktop\UFO Timeline data archive\generated_snapshots_2026-05-27`

Follow-up disk-space cleanup:

The generated snapshot folders were later deleted from this archive location to
reclaim local disk space. The archive manifest was kept:

`C:\Users\jarod\Desktop\UFO Timeline data archive\generated_snapshots_2026-05-27\archive_manifest.csv`

The manifest records what was removed. The deleted snapshot folders were
intermediate/generated candidates and are not required for normal app UI
changes, static bundle updates, or Cloudflare Pages/R2 deployments as long as
the active canonical outputs remain present.

To restore a snapshot from an external backup, move the needed folder back under:

`C:\Users\jarod\Desktop\UFO Timeline map tool\data\`

If future pipeline work needs a deleted intermediate snapshot, rebuild it from
the current canonical inputs or restore it from an external backup if one was
created before deletion.

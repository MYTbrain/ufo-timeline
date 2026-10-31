# Craft mosaic readability

Local preview change on 2026-10-31. The canonical candidate is the source in the
`case-navigation-release/UFO Timeline map tool` worktree; no deployment or data
build was performed.

Tiles now use the chart's actual aspect ratio without changing proportional
areas. Text has readable line heights and a font-scaled chart height. Optional
effect badges yield to category names. Categories that cannot fit have a compact,
numbered label and percentage below the chart, with the same preview/rebalance
actions. Resize observers are replaced on rerender and disconnected on teardown.

Validation:
- `node tests/test_analysis_craft_mosaic.mjs`: proportional areas, identity,
  bounds, non-overlap, skewed/zero weights and portrait/wide geometry passed.
- `node tests/test_analysis_view_repairs.mjs`: existing controller checks passed.
- Browser: all displayed category names/shares readable in the real 1954 cohort,
  enlarged text (150%), and a reproduction of the screenshot's proportions,
  including Triangle at 8.1%. A narrow layout with approximately 390 CSS pixels
  also passed. See `verification.json` for actual viewport measurements.
- Category preview, excluding a small category through its key entry, and Show
  all were verified. Temporary fixture/text changes were discarded by reload.

Artifacts here are small UI verification evidence, generated from the local
preview and reproducible by opening Analysis > Cohort overview. `after.png`
shows the real cohort. Retain these with this source change;
they are not deployment bundles or dataset backups.

Storage: production remains deployment `11f72dab-fdf5-4eaf-b84c-301637685fa2`;
retained rollback remains `2850fbfd-1010-417d-86c4-3d94decc5025`. The canonical
deployment staging tree is unchanged. No staging/backup tree was created or
superseded, and no generated artifact exceeds 100 MiB. Expected total growth is
under 1 MiB. An unusable temporary screenshot was removed; no other cleanup is
needed for this change.

Production update, 2026-10-31: this readability change is now published with the
v3 share-link release in deployment `742eb895-1387-43bd-b69f-85911b806ee9`, source
`15f32aa0ded006c2b1a718dcf3a6141adb6ce678`. The current canonical stage remains
`.tmp/workspace-analysis-20261008-pages`, refreshed in place (234 files,
41,638,544 bytes). The sole designated rollback is now
`11f72dab-fdf5-4eaf-b84c-301637685fa2`; the earlier rollback designation above is
superseded. Live verification and the production screenshot are recorded in
`../share-view-v3-20261031/production-release.json` and
`../share-view-v3-20261031/production-mosaic.png`. The combined release added
11,891 bytes to the stage and under 5 MiB overall, created no file above 100 MiB,
and made no corpus copy or duplicate local stage. Hosted preview cleanup is only
proposed in the release receipt; no deletion was performed.

# Case navigation and compact layout release, 30 October 2026

Authorized scope: publish the reviewed current root frontend, including Dalnegorsk,
chronological case ordering, positive link-count badges, the known-direction trace
filter, compact legend and case details, playback alignment, the expanded-results
overlap fix, UFOSINT attribution, and year-first `YYYY/MM - YYYY/MM` flap labels.
The existing Encounters and direction compass remain in this frontend.

The canonical candidate reuses `.tmp/workspace-analysis-20261008-pages` in place.
Only nine explicitly named frontend files are overlaid; all Pages data and immutable
R2 objects are reused byte-for-byte. Reproduce the overlay using
`scripts/prepare_workspace_analysis_release.py --refresh-frontend`; inspect without
writing using `--refresh-frontend --check-only`. No catalog, analysis database,
context derivative, or complete release tree is rebuilt or copied.

Before publication, production is `1a60ac73-eaab-4efa-9dc3-a59da873929d` at
`https://ufo-timeline.pages.dev/`. That validated deployment becomes the sole
designated rollback when the new production is verified. The previous rollback
designation `a49d5164-2f86-48e7-9d4c-9d8686d015d9` is superseded, without deletion.
Provider/public/browser verification and the final artifact hashes are recorded
in `production-release.json` after publication.

Validation: 12 existing Node suites passed (case presets, catalog references,
availability helper/integration, known-direction filter, direction/case integration,
famous-case traces, direction summary/population, neighborhood, encounters, and flap
labels), plus all three case-navigation shell checks. The current preview has been
visually reviewed throughout the changes; link selection and compact layout were
checked against the complete catalog. Final live validation checks the published
bytes and key controls.

Storage: the retained stage starts at 232 files / 41,553,472 bytes and grows by
approximately 15 KiB for the frontend changes. Source, tests, release receipts, and
small UI screenshots add less than 5 MiB overall. No new file exceeds 100 MiB and
no duplicate large stage or backup is created. Existing historical provider
deployments are not designated additional retained releases. Any future provider
cleanup requires a separate literal allowlist; no data or deployment deletion is
part of this publication. Screenshots in `docs/ui` are small review evidence, not
extra deployment bundles.

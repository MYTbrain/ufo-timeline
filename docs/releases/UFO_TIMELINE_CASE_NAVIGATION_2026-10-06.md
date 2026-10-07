# Case navigation and trace inspection release — 2026-10-06

The release adds 85 searchable famous cases, alphabetical/chronological ordering,
arrow direction summaries, monochrome craft silhouettes, and Results cards for
reports at both ends of case connections. The compact case picker keeps Clear;
Results holds the date window, connection counts, Fit action, and optional sources.
Selecting a case preserves zoom, briefly highlights its area, and defaults to one
day before/after its source dates. Uncertain connections have a single shared,
double-headed badge and are excluded from directional percentages.

## Production preservation

The baseline is production `ca73305a-aff6-4466-8d9a-83c9416f4cfe`, source
`6fb09834ec028b48e4d201a1ee632206d5c38404`. It is the retained public rollback.
The current R2 release remains `coordinated-reliability-v152-20260731`, with
702,893 normalized and 580,783 mapped records. This interface release preserves
the reviewed location-label overlay, service-worker retirement, loading behavior,
OpenStreetMap basemap, and immutable report URLs. It also preserves the approved
three-state crop/animal context controls. Exploratory convergence cells start off;
their existing data and builder hashes are preserved, with no new scientific run.

## Validation and reproduction

Seven root-layout Node suites and 26 targeted Python checks passed, including
case/endpoints/direction integration, exact convergence pins, and reviewed-label
provenance. The original research workspace also passed its crop suite and
broader area/chronology contracts. Browser release verification is recorded below.

Prepare only the explicitly allowed runtime assets:

```powershell
python scripts/prepare_interface_release.py --output .tmp/interface-pages-candidate --inventory .tmp/interface-pages-inventory.json
python scripts/prepare_interface_release.py --output .tmp/interface-pages-candidate --inventory .tmp/interface-pages-inventory.json --verify-existing
```

The candidate contains 151 files, 25,739,855 bytes (24.55 MiB); tree SHA-256:
`692fe473ddcf4db0dcdd7bfd9455159435ff345ca66b89caa49ab02b4b969245`.
The inventory remains outside the public directory. Publication uses the established
Cloudflare Pages project `ufo-timeline`, production branch `main`, and
<https://ufo-timeline.pages.dev>. GitHub source uses the repository-root Pages layout.

## Storage and retention

The new canonical interface artifacts are the root-layout Git source and the
validated `.tmp/interface-pages-candidate`; its adjacent inventory records every
path, byte count, and hash. The release worktree is a small source checkout based
on the production baseline, with no full corpus or analysis database. It is retained
for further interface work; Git and the preparation command reproduce the candidate.

The prior production deployment above is the one designated public rollback.
Existing research data under the D: acceptance-site junction and the C: historical
rollback remain protected shared inputs; no corpus was copied, rebuilt, or uploaded.
No newly created file exceeds 100 MiB. Approximate growth for source checkout,
Git objects, small QA images, and the candidate is below 80 MiB. The temporary
preview becomes superseded after production passes; removing that preview is the
only new cleanup proposal. No historical dataset or release directory is deleted.

## Hosted preview acceptance

Preview deployment `d60a8856-e538-4515-9c73-72cbe863953a` served source
`c548a27538da7a1ed9efa9328f4791d269e8bd8b` at
<https://d60a8856.ufo-timeline.pages.dev>. Twelve critical hosted asset hashes
matched the prepared inventory, including the current configuration, label gzip,
retirement worker, and new interface modules. Browser checks showed six links,
five area reports and three outside endpoints for Frederick Valentich. Changing
the end date retained the case; Fit worked; the outside Gallipolis Ferry Full
Details loaded event `56304148725268` with preserved source fields. No browser
errors or warnings were captured. `docs/ui/famous-case-hosted-preview.png` records
the map, legend silhouettes, compact Results context, and outside report card.

Production is published from this release on GitHub main. The final local
publication receipt beside the inventory records the confirmed production
UUID/source and retains the baseline UUID as the one public rollback.

# Phone-accessible encounter preview

Review link: https://encounter-preview-20261013.ufo-timeline.pages.dev/whole-site

Cloudflare deployment `d0a94735-9bc7-4daf-9965-a62aa0809adc` is a **Preview** on branch
`encounter-preview-20261013`, using runtime `b5c8ac5`. Production
before and after remains `626b22b4-af0a-4252-8525-0ba21289c0d0` on main. The sole
production rollback is `192e21f6-9c44-4b89-8d88-361e1c3d10d6`. No GitHub push,
production deployment, R2 upload, source-corpus copy or permission change occurs.

The v6 review makes encounters opt-in at startup/reset, moves the legend entries
immediately after crop circles and animal mutilations, adds colored outlines,
and moves display controls into the native map pane. Markers, smoothed report
density, combined display and optional bounded same-day report comparisons use
independent layers. They preserve craft colors/traces/radar, source metadata,
original coordinates, nullable unknowns and report identity. See
`docs/ENCOUNTER_MAP_20261013.md` and the focused runtime QA receipt.

`shell.json` records the exact public asset/source/hash allowlist: 196
files, 39,714,739 bytes (37.87 MiB). It serves only
previously approved runtime assets, current encounter metadata and the small
nuclear patch. Source archives, workspace/repository files, scripts and scientific
QA remain outside the public shell. Published R2 data is reused.

`public-verification.json` records 194 remotely streamed/hash-checked
files, validated static references and a mobile-client HTTP200 response with v6
assets. `/whole-site` is the provider-normalized route. Interactive phone visual
acceptance remains pending; it is separate from passing actual-runtime/DOM,
worker, heatmap lifecycle, connection eligibility, control and HTTP tests.

The exact inventoried temporary shell was removed after successful verification.
All retained source files and the validated 184-file production stage stay in
place. No newly created file exceeds100MiB. Approximate persistent growth is
under500KiB plus small Git/Wrangler cache metadata. `storage.json` records the
allowlist, canonical candidate and retention. No superseded local staging remains.
The previous v5 preview is superseded; its source/QA remain recoverable in Git.
The current remote preview is retained for user review.

Replay uses `scripts/prepare_phone_preview.py`, shared Wrangler with the explicit
nonproduction `--branch encounter-preview-20261013`, then
`scripts/verify_phone_preview.py`. Never use the generic deploy wrapper without
its missing preview-branch protection or overwrite the validated production stage.
The local delivery check accepts a loopback-only
`UFO_ENCOUNTER_DELIVERY_BASE_URL`, permitting an ephemeral test port when8168 is
already owned by the local preview service.

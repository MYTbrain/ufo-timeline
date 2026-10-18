# Visual comparison layout revision

User feedback: the original large, nested comparison tables were difficult to
scan. This revision keeps the Analysis page compact and opens the comparison in
a separate native dialog with one central chart topic at a time.

Preview: https://analysis-groups-20261018.ufo-timeline.pages.dev/
Deployment: `73407a2e-93c4-4b39-8da9-2de4a62c9d89`.
Runtime source: `0f1696dc367cd1a0261cfc83352c5a6e37458763`.

## Behavior and evidence

- Compact Set/Replace A/B controls with visible scopes and report counts.
- Scope and filter identities distinguish same-date groups. Full collection
  selections ignore inherited map date labels; reheld selections are explicit.
- Craft, Beings, Abductions, Sources and Coverage share one chart area. Bars
  show A/B percentages on a common 0-100% scale with exact counts. Categories
  rank by absolute percentage-point difference when both sides are available.
- Unknown values are separate. Unavailable information stays unavailable.
  All shares use captured report counts, not a changing eligible denominator.
- The complete exact table is optional; the first eight categories have an
  explicit show-all action. No persistence or extra dataset is introduced.
- Native dialog Escape/Close and focus return work in the hosted browser.
  Applying A closes the dialog and uses the 821-report population; returning
  to filters restores the live 505-report window without losing either group.

Actual browser comparison: A = 1954-09-01 to 1954-11-30 (821 reports); B =
1952-06-15 to 1952-08-31 (505 reports). Craft and being views rendered with the
expected denominators. The main page remains compact, and three paired chart
rows fit beneath the cards at the tested 1265x712 viewport. This is a desktop
browser check; it is not a physical-phone audit. CSS includes narrow layouts.

`comparison-workspace.png` and `compact-toolbar.png` are direct browser captures.
`hosted-public.json` verifies 205 browser-served Pages files. `provider.json`
records the preview and unchanged production/rollback identities.

Focused checks passed: session view (actual model, counts, scopes, overlap,
unknown/unavailable fields, show-all/table agreement, keyboard/modal focus,
async errors and reset), session model, actual app/worker integration, syntax
and whitespace checks. The underlying app and worker were not edited.

## Storage and retention

The canonical preview candidate is the single refreshed
`.tmp/workspace-analysis-20261008-pages` directory in the attached
case-navigation-release checkout. It has 207 files and 40,603,136 bytes, tree
SHA-256 `e580a5e6ef590da12e966dcef03549461b0f4bd054abb733ecb5d0dd6ad8236b`.
Its growth from the previous preview is 18,761 bytes. Total local growth from
source, tests and these QA artifacts is approximately under 1 MiB. No newly
created file exceeds 100 MiB. No full corpus, staging or analysis copy was made.
The 87 immutable R2 objects (101,875,689 bytes) are reused without new uploads.

Production remains `16443086-c630-41d8-a793-92a0243a76f6`; its one designated
rollback remains `b4e04dc8-4605-486e-bdbc-174acd3ca37e`. Preview `18a18133` is
superseded by this candidate; its local stage was replaced in place. A later
explicit remote cleanup may retire the superseded preview, preserving current
production and rollback. No dataset or remote deployment was deleted.

This QA directory is retained as small evidence for the layout decision. It is
reproducible from the runtime source and the documented two-window browser flow.

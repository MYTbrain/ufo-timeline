# Temporary Analysis selections and comparisons

This preview adds a page-only research workflow. It does not require accounts,
saved projects, exports, or a file-management workflow. Refreshing the page clears
the selection and both held groups.

## Workflow

1. Open Analysis and choose the shared filters you want. **Hold current as A**
   captures the matching catalog report IDs and their descriptive summaries.
2. Change the shared filters and **Hold current as B**. Expand **Compare A and B**
   to inspect totals, coverage and categorical distributions.
3. Encounter report inspection and the collection study provide **Use in
   Analysis**, **Hold as A**, and **Hold as B**. These include every matching
   catalog report across pagination, including unmapped reports.
4. **Use in Analysis** or **Use A/B in Analysis** makes that frozen report set the
   Analysis population. The selection remains independent of later map filters.
   **Return to filters** restores the current live shared Analysis filters.

The collection study's explicit full-study mode continues to ignore shared
filters. Select its shared-filter mode when studying an active temporary
population there. Unjoined dossier-only accounts cannot be turned into invented
catalog report IDs.

## Interpretation

The counting unit is catalog report representations, not independent historical
incidents. The comparison shows shared membership explicitly. Category shares
use each group's captured report denominator; field coverage and unknown values
are separate. Multiple being categories may apply to a report. Unavailable
evidence remains unavailable. The comparison provides descriptive summaries,
not significance tests or causal conclusions.

Frozen populations use Analysis's internal-structure baseline. Their original
capture filters and date scope remain in provenance. Per-analysis date,
location, source and evidence eligibility still apply.

## Delivery and storage

Implementation checkout: `C:/Users/jarod/.codex/worktrees/case-navigation-release/UFO Timeline map tool`.
Branch: `codex/temporary-analysis-20261018`.
Shared canonical inputs remain under `C:/Users/jarod/Desktop/UFO Timeline map tool`.
The single bounded Pages stage is refreshed in place at
`.tmp/workspace-analysis-20261008-pages`; no corpus or complete analysis database
is copied. Immutable R2 objects are reused.

Production remains deployment `16443086-c630-41d8-a793-92a0243a76f6`, source
`15ab1607390d636f1571fa10bb4c8b137cf391f2`. The retained production rollback is
`b4e04dc8-4605-486e-bdbc-174acd3ca37e`. The new preview candidate supersedes the
local collection-only candidate, which remains reproducible from its source
revision. No dataset, analysis, old research queue, or remote deployment is
deleted by this task.

## Verified preview

URL: https://analysis-groups-20261018.ufo-timeline.pages.dev/
Deployment: `18a18133-ca83-4af3-99a7-6cf88ea0b800`.
Runtime source: `6aa65d32b28f27583e436e9b21ca3dc753f299f6`.
The frozen Pages candidate has 207 files, 40,584,375 bytes, tree SHA-256
`875a2cb72d13b721481833e6ae8d29ab0a26a811906021ce9ee111ba5926e70e`.
The existing 87 immutable R2 objects (101,875,689 bytes) are unchanged and were
not uploaded again. `provider.json` records the production and rollback check;
`hosted-public.json` records byte verification of 205 browser-served Pages files.

Focused checks passed: session model, session view, actual app/worker/session
integration, collection evidence/view/delivery/worker cohort, encounter inspection
view, catalog filtering, comparison worker, Analysis view and scheduling repairs,
startup cache/loading cover, and progressive startup flow. The integration test
uses the real worker response and view envelope for both quick and full frozen
population results, rather than a response-echoing mock.

Hosted browser checks used A = September-November 1954 (821 reports, 770 mapped)
and B = June 15-August 31 1952 (505 reports, 491 mapped). The two captured windows
had no shared report IDs. Applying A rendered the selected 821-report population
in Time, retaining the 1952 live date inputs and 491 mapped map results. Returning
to filters restored the 505-report Analysis cohort while preserving both groups.
Reload cleared both groups. `comparison-preview.png` shows the completed browser
workflow. This desktop check does not claim a physical-phone accessibility audit.

The live review caught and repaired two issues before delivery: the accepted
layout inserted the new controls below the charts, and a request used an Analysis
result-mode value where the worker required a baseline value. Placement is now
above the topic workspace, and real-envelope regression coverage prevents the
second issue from silently leaving charts on 'updating'.

Local net growth is approximately under 1 MiB including code, tests, QA and the
54,698-byte increase in the single existing stage. No newly created file exceeds
100 MiB. No additional large directory was created. This QA directory contains
small reproducible evidence for this preview and is retained with its source.

Cleanup proposal: the superseded collection-only local candidate has already
been replaced in place. Intermediate preview deployments `a8de6675`, `2af5a28e`
and `9639e2a8` are superseded by `18a18133`; retire them in a later explicit
remote cleanup, preserving production and its one designated rollback. No data
or remote deployment was deleted during this task.

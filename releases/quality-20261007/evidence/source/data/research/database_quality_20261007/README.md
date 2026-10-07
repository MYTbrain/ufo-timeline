# Online and systematic unmapped recovery — 7 October 2026

Purpose: recover supported geographic references for currently unmapped reports,
using original accounts, declared places, source grid coordinates and online
primary documents/authorities. This extends the retained October 6–7 quality view;
it is not a copy or mutation of the complete canonical catalog.

Shared inputs: the pinned `data/canonical_web` base, prior audit and quality batch,
existing source archives and cached geographic authorities, all read in place.
The prior `database_quality_20261006/quality_view_manifest.json` remains the local
quality rollback. Source evidence, unresolved conflicts and raw fields remain.

Lanes: `account_recovery`, `gazetteer_recovery`, `online_sources` and
`grid_reference_recovery`. Each records accepted decisions, evidence, exact
before-field guards, source locators/hashes, rebuild methods and abstentions.
No location is inferred solely from the date, aircraft route, publisher, a
country/state centroid, similar UFO story or another witness's account.

Expected retained output is below 100 MiB combined. All source ZIPs/PDFs fetched for
this batch are individually bounded evidence files, not full corpus/archive
copies. No planned file exceeds 100 MiB or 1 GiB; C: begins with approximately 132.27 GiB free.
The small Ordnance Survey developer ZIP documents projection test coordinates
and transformation limits; retain it as primary technical evidence and reuse it
without downloading again. Any extracted grid test/fact files are reproducible
from that pinned ZIP. No full geocoder index, bundle or backup tree is created.

The final report/inventory designates the combined canonical quality manifest,
the prior quality view rollback, unchanged current/rollback deployments, new file
sizes, net growth and retention. No dataset deletion or incidental cleanup is
planned. Live publication, if performed, requires a separate receipt and coherent
map/trace/analysis projections from the corrected rows.

Completed result: 1,742 new mapped report references, four guarded date-precision
downgrades, and one unmapped locality enrichment. The combined local quality view
retains 702,893 representations: 582,528 mapped and 120,365 unmapped.
See REPORT.md for scope, remaining research queues, verification and retention.

## Current continuation result

The second pass adds 349 map references and 7 date-precision downgrades. The current local view has 582,877 mapped and 120,016 unmapped representations. See CONTINUATION_REPORT.md and continuation_02/quality_view_test_receipt.json for current results. REPORT.md and the first-pass receipt document the earlier state.

Current rebuild: continuation_02/assemble_continuation.py, then continuation_02/integration_validation.py and continuation_02/inventory_continuation.py. The first-pass assembler is historical and would omit this extension; use the continuation assembler for the current view. Production remains unchanged.

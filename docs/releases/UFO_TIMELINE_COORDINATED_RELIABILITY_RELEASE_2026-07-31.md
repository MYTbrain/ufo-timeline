# UFO Timeline Coordinated Reliability Release

Release date: 2026-07-31  
Release identifier: `coordinated-reliability-v152`  
Production URL: <https://ufo-timeline.pages.dev>  
Authoritative source root: `C:\Users\jarod\Desktop\UFO Timeline map tool\webapp\static_public`  
Generated static root: `C:\Users\jarod\Desktop\UFO Timeline map tool\static_bundle`

## Outcome

This release fixes the coordinated marker/trace interaction defects, prevents Craft Type endpoint colors from leaking into other color modes, hardens generation-aware filter refresh behavior, merges the reviewed Falcon Lake duplicates, adds a fail-closed canonical-pipeline completeness audit, and repairs the hosted end-to-end verifier so it tests the current canvas/progressive-rendering architecture.

The final Pages folder was built once, hashed, certified on a named preview, and promoted unchanged to production. The production deployment uploaded zero new Pages files because every file was already present from the certified preview.

## Product fixes

- A visible point marker now wins when a point and Chronological Neighborhood connector overlap. The same event-opening path is used by ordinary map points and neighborhood endpoints. Connector-only clicks still open the chronological-adjacency inspector.
- Trace segments no longer retain Craft Type endpoint decorations after changing to chronology or another color mode. Cached aggregate source segments are not mutated during render-time styling.
- Overlay markers now carry an overlay-specific class, allowing deterministic interaction and QA without confusing airports, military facilities, and research sites.
- Filter work remains generation-aware and atomic. Stale worker/render results are rejected, and rapid precision/date-checkbox toggling deterministically resolves to the last state.
- The existing default loadout remains intact: Craft Type coloring, Heatmap map mode, and only the `<=1 day` and `<=2 days` trace buckets.
- The hosted verifier now understands progressive result windows, canvas trails, the current map legend, current default modes, stable timeline viewport behavior, and state-based overlay validation.

## Falcon Lake reviewed merge

- Keeper canonical ID: `evt_b4569b109528e632c01815c4`
- Keeper event ID: `3904275358258169`
- Date: `1967-05-20`
- Location: `FALCON LAKE, 01, MB, CN`
- Coordinates: `49.7, -95.32`
- Type: `Disk`
- Craft type: `disc_saucer` with high confidence
- Preserved provenance: 47 source records
- Removed duplicate shells: 8

The generalized merge applicator accepts only explicitly reviewed craft/type normalization fields from the sidecar and fails closed on unsupported overrides.

Pre-apply backup:

- Folder: `backups/coordinated_reliability_v152_preapply_20260731/data_canonical_web`
- Files: 730
- Bytes: 7,930,157,194
- Pre-apply canonical manifest SHA-256: `e22c4e0acaca2b95ef2674988e960c4f946daa1cb13732edc63fa12d31556dcf`

Post-apply canonical manifest:

- SHA-256: `242ff4abc42c70c2b241a3cd16c8b9059bca137d940bd6147c5a65de63b7750b`
- Source and `static_bundle` copies are byte-identical.

Reviewed artifacts:

- `data/reports/falcon_lake_reviewed_event_merge_v152.json` — SHA-256 `bcb5e1a49670f4dad8b366c04b52c22137eb15ac55b7519dc6e5b4fd4e7b6823`
- `data/reports/falcon_lake_reviewed_event_merge_apply_v152.json` — SHA-256 `333dc38c5e3161b51e8269367ba8eb86fd1fdbd8ead1adfce01d84b9505c97d1`

## Canonical completeness audit

All 14 fail-closed checks passed:

- 971,115 source records and 971,115 unique stable input IDs
- 703,018 successfully normalized expected canonical events
- 268,097 automatic duplicate reductions
- 53 reviewed merge clusters
- 125 reviewed removed shells
- 702,893 current canonical web events
- 580,783 mapped events
- 122,110 unresolved events: 82,847 city, 22,387 country, and 16,876 unknown
- 0 invalid serialized coordinates
- 0 source IDs missing from provenance
- 0 unexpected source inputs
- 0 undocumented missing expected shells
- 0 unexpected current canonical events
- 0 import failures

Audit artifacts:

- `data/reports/canonical_pipeline_completeness_audit_v152.json` — SHA-256 `47a66361ba388504b50f4f8476e41e1aae544383321351eeeecf9419ad7a97ac`
- `data/reports/canonical_pipeline_completeness_audit_v152.md` — SHA-256 `a2b445454ce9f9f25a07626458539c9e98a58ba7caa068601b1b0b4655b7d4c1`

## Validation

Final local gates:

- 10/10 executable JavaScript behavior suites passed.
- 16/16 JavaScript syntax checks passed across authoritative and generated roots.
- 794 Python tests passed.
- One existing Starlette/httpx deprecation warning remains; it is not a test failure.
- Canonical payload readiness: READY.
- Static loadout readiness: READY.
- Source/generated frontend parity checks passed.

Readiness artifacts:

- `data/reports/canonical_web_static_payload_readiness_coordinated_reliability_v152.json` — SHA-256 `96f23ff476c2a4de1506a6e4db60094a7cde25d3f796bb3715eb16e2ef6cd569`
- `data/reports/static_loadout_readiness_coordinated_reliability_v152.json` — SHA-256 `ebc6701b7d5ae95a1798cc28d376267af1bad53a9d96564cd299b29565078583`

Hosted verifier result: zero failures. It covered startup, catalog totals, timeline/source synchronization, themes, Full Event View, category actions/counts, timeline zoom and dragging, legend filtering, progressive results, overlays and marker semantics, sorting, panel resizing/collapse, playback, cursor/badge behavior, canvas trail styling, and detail persistence.

Manual/live browser checks also covered:

- Point-over-trace clicks open the endpoint event while connector-only clicks open the adjacency inspector.
- Area selection at depth 4 and direction Both rendered outside-area endpoints and 114 neighborhood traces without losing trace inspection.
- Craft Type -> chronology -> Craft Type switching restored the correct trace explanation without color leakage.
- All four precision-checkbox combinations reproduced exact result counts over repeated cycles, and rapid toggling returned to the identical final count.
- Falcon Lake resolves to the single reviewed event with its coordinates, type, source record, and Full Event View provenance.
- The Airship Wave preset produced 413 events; playback at 4x advanced responsively and paused without a page freeze.

## Performance evidence

Hosted certified preview:

- First usable render: 7,883.30 ms
- Ready: 8,613.20 ms
- Dominant browser catalog-build phase: 5,346.80 ms
- Initial filtered catalog build: 45.60 ms
- Filtered shell render: 69.80 ms
- Initial heatmap render: 7.60 ms

Production browser samples:

- Canonical URL: first usable 8,493.00 ms; Ready 9,221.80 ms
- Immutable production URL: first usable 8,937.20 ms; Ready 9,838.70 ms
- No browser errors or warnings were observed.

Pure helper stress benchmark using a 100,000-edge synthetic chain:

- Adjacency-index build: 162.39 ms
- Warm depth-4 Both traversal: 18.65 microseconds, reaching 8 segments
- 100,000 mixed-endpoint Craft Type style resolutions: 6.56 ms

These helper numbers demonstrate that warm depth/direction traversal is proportional to the reached neighborhood. They are not end-to-end browser render timings.

## Frozen artifact and deployment

R2:

- Immutable prefix: `releases/coordinated-reliability-v152-20260731`
- Public base: `https://pub-e9029ab2f6b448daad03d7cde7e15e64.r2.dev/releases/coordinated-reliability-v152-20260731`
- Objects: 366
- Bytes: 913,767,840
- Stable upload-entry SHA-256: `16a87b965ee80006e347e4abf5b957fc471cf16080a94a205b041fd5e20b5455`
- Public object verification: 11/11 sampled object hashes matched.

Final Pages folder:

- Folder: `cloudflare_bundle_r2_coordinated-reliability-v152_certified3_20260731`
- Files: 127
- Copied deploy files: 123
- Omitted R2-hosted files: 721
- Maximum Pages file size: 15,343,050 bytes
- Tree SHA-256: `9ecd803279489bcbfbb0d7bdccd03814c06865a22896b24d6251d3658f5fb179`
- `app.js` SHA-256: `08567e05bd3ac51333c8a58b6f18024feebb5d579a190ba3fb0a2709ae270fd5`
- Post-deployment tree SHA-256 remained identical.

Deployments:

- Previous production: `ba4f800d-b75b-4169-9857-51dd6b8988e2`
- Certified preview: `2ea31163-4665-486c-ab6b-163b0b5e6d68`
- Preview URL: <https://2ea31163.ufo-timeline.pages.dev>
- New production: `5727804b-4d91-47a3-9895-eeb6f60b9165`
- Immutable production URL: <https://5727804b.ufo-timeline.pages.dev>
- Canonical production URL: <https://ufo-timeline.pages.dev>

The production deploy reported `0 files uploaded (126 already uploaded)`, proving that the certified preview artifact—not a rebuilt variant—was promoted.

## Genuine limitations

- The browser still builds a 702,893-event summary catalog at startup. On the tested desktop connection, Ready took about 8.6–9.8 seconds; this is much safer and more responsive after startup, but it is not an instant first load.
- A first-time, full-corpus keyword search can still be substantially slower than direct date filtering because it must inspect the complete searchable summary catalog.
- Native mobile browser emulation was not available in the connected browser surface for this final promotion. Mobile layout invariants remain covered by the executable responsive-layout tests and by the prior preview QA; production desktop and immutable/canonical parity were rechecked after promotion.


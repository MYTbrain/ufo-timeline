# Search preview, 18 October 2026

Status: hosted preview verified at https://analysis-groups-20261018.ufo-timeline.pages.dev/ (deployment `9ddc6f4e-a385-4524-85dd-3df20435b65b`, runtime source `e85c23c`). Production remains deployment `16443086-c630-41d8-a793-92a0243a76f6`, source `15ab1607390d636f1571fa10bb4c8b137cf391f2`; sole designated rollback `b4e04dc8-4605-486e-bdbc-174acd3ca37e`.

## Behavior

Plain input retains contiguous case-insensitive substring matching. Uppercase AND/OR, quoted phrases and parentheses support research queries. The lazy worker searches all 702,893 current report representations including unmapped reports. Each Boolean leaf unions original preserved text with current corrected catalog metadata before the expression is evaluated. This preserves split-source AND matches without changing canonical records.

Only complete, release-pinned searches enter the bounded cache or enable Analysis/A/B capture. Failed searches show summary-only coverage and a retry action. Syntax errors preserve prior results. Stale query, generation, dataset and release responses are discarded. Snippets use safe text nodes and only request the visible result page. Search data and its worker do not load during initial startup; the existing loading screen remains intact.

Shared-filter capture includes matching mapped/unmapped reports under date/category filters and explicitly excludes drawn-area restrictions. All-search capture spans dates/categories. Both are RAM-only and use exact IDs; they do not change Map filters or create saved files.

## Verification

Query, catalog metadata, safe UI, lazy runtime, production app integration, index and accelerator fixture suites pass. Existing startup cover/cache, progressive flow, catalog worker, collection delivery and temporary Analysis model/view/integration checks pass. Ten release checks pass, including physical manifest bytes and versioned checksum URLs on Windows. Real-data parity checks cover 20 queries over 18,014 source reports from eight pinned chunks, with exact normalized-text roundtrip and no candidate false negatives.

`local-runtime-smoke.json` measures local range-adapter CPU/read performance, not internet latency. Common fragments such as red/light use one small range after the metadata is ready. Arbitrary quoted phrases may still require many verification pages; progress remains visible. `search-range-verification.json` verifies actual hosted range bytes and CORS. Upload receipts attest 18 new immutable objects without replacing existing objects.

## Storage lifecycle

The sole canonical search derivative is `D:/Codex/UFO-Timeline/search-index-20261018-v1` (479,750,248 bytes including local provenance/QA). Its PURPOSE.txt documents source pins, purpose, rebuild and retention. Rebuild with `scripts/build_search_index.mjs`, then `scripts/build_search_accelerator.mjs`; never overwrite or copy the corpus. Current corpus and source archives are read in place and unchanged.

The single Pages candidate `.tmp/workspace-analysis-20261008-pages` is refreshed in place. It contains only the small search manifest and scripts/styles; large packs are served by the immutable R2 prefix `releases/search-index-20261018-v1`. The 87 preexisting object pins remain unchanged. The production and rollback designations above remain valid; this work is preview-only.

No new file exceeds 100 MiB. Approximate net growth: D: 457.53 MiB; C: less than 2 MiB for sources, tests, receipts, manifest and shell changes. No superseded large stage or backup was created, and no data was deleted. Retain this one validated search derivative while the preview references it. Cleanup proposal: none for this batch; do not remove protected source data or the current rollback.

## Hosted browser result

The final hosted browser verifies full coverage for `ariel AND school` (4 matches) and `soil OR plants` (2,640 matches). The four Ariel/school reports transferred into Analysis as an exact temporary population. The phone drawer at 390 x 844 supports scope selection and capture; the final capture confirmation reads "Held 2,640 reports as A." The viewport override was reset afterward. Desktop and phone screenshots show the retained Map tools/legend and new search controls. `startup-search-network.json` records zero search-data/worker requests before the first query.

A hosted check caught Windows newline translation changing the manifest after its checksum was calculated. The builder now writes this manifest with explicit LF and requests it with its checksum in the URL. Runtime checksum validation remains strict. The new physical-file regression test covers this failure.

`provider-deployments.json` confirms the final preview source, unchanged production, and retained rollback. `hosted-public.json` verifies the four final changed public files against their frozen bytes and inherits 208 byte-identical public files from the preceding complete 212-object check. A final repeat sweep hit a network read timeout; the bounded delta check passed. Only the expected Cloudflare Analytics injection is permitted. Immutable R2 source objects are independently pinned and range-verified.

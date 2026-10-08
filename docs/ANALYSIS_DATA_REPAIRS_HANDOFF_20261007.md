# Analysis data repair handoff — 7 October 2026

User request: fix the findings in the full Analysis data audit. Keep the ongoing whole-site usability preview and all original functionality. The earlier instruction not to deploy remains active; nothing in this batch has been pushed or published.

## Runtime changes

- Missing/blank/boolean date ordinals no longer become 1970. Genuine epoch zero remains valid.
- Descriptive coverage charts retain zero rows and report present, missing, total and percentage using their actual cohort denominators.
- Deferred chart jobs belong to their owning dashboard and render generation, survive navigation correctly and rerender after invalidation. Inactive sections do not consume another section's chart work.
- Analysis requests/artifact arrival coalesce around a single worker computation; stale generations and quick/full results cannot replace newer filters. Map exit and return, caches and timers are covered by integration tests.
- Strict crop/animal gate mapping uses the actual strict lanes, separate from sensitivity lanes. Eligibility stays at one crop record and zero animal reports with other required gates blocked.
- The spatial exclusion funnel distinguishes the full release from active-query support. Exported exact-date counts cover all reports, with mapped-only counts identified separately.
- Partial source dates filter by interval overlap. Year-only dates do not enter an invented month, exact-day traces or inference. Active/reference interval cohorts remain disjoint.
- Witness wording and policy use documented source-field contracts and distinguish collections from independent underlying sources. Source independence is unverified, so comparative inference and Pattern Finder remain disabled.
- Seven reviewed animal cards show descriptive source titles, correct paraphrase/capture-hash labels and expandable accepted field provenance without duplicating the summary.
- Cache signatures and evidence-package artifact hashes include both catalog date-repair sidecars alongside the pinned original dataset identity.
- Typed witness projection loading validates the whole input before committing; explicitly documented NUFORC and UFOCAT lanes are supported without weakening source-independence policy. A rejected lane leaves a clean unavailable state.
- Worker result cache identities include actual projection readiness. Delayed dedicated Spatial jobs cannot reinsert an empty field result under the identity of subsequently loaded clock, duration or witness evidence.

## Changed-only candidate data

Shared root: `C:/Users/jarod/Desktop/UFO Timeline map tool/data/research/analysis-repairs-20261007`. See its `PURPOSE.md` and final receipt for component paths, pins, actual sizes and retention.

- 21,778 additional approximate clocks; exact-clock inference unchanged; 2,037 ambiguous sentinel clocks remain distinct.
- 1,110 explicit number-word/unit durations recovered under a bounded source parser.
- 74,593 raw UFOCAT witness fields recovered using the retained primary codebook. Combined exact count coverage is 198,228; qualitative, lower-bound, unresolved and nonpositive values stay separate. UFOCAT source lineage is retained.
- 3,898 MUFON dates recovered as 3,391 month and 507 year intervals. No inferred exact occurrence day.
- Gainesville and Oscoda records corrected to source-reviewed years 1967 and 1975. First-of-month approximate source dates were not promoted to exact days. Catalog exact-day total becomes 670,124, year total 9,262, while all 702,893 IDs/row positions and 582,877 mapped records remain.
- Crop projection restores 94 classifications and 88 origins, retaining original columns and typed coordinate evidence.
- Seven animal cases regain eight distinct public references and reviewed field provenance. Unknown incident hashes remain unknown; frozen source hashes have their own role.

## Remaining research

Of 178 suspicious UPDB dates, 176 remain unresolved. Never substitute Reported/Posted dates for occurrence. The source-quality packet includes 297 coordinate flags, 109 qualified endpoints, 45 affected pairs and 228 affected context rows, plus explicit sensitivity holdouts. These are review targets; they do not prove mislocation or authorize removal from the main result.

Underlying UPDB/MUFON/NUFORC lineage is documented, but neither record similarity nor collection names prove incident duplication or source independence. Missing context date roles, uncertainty and facility activity intervals still require evidence. Boundary derivative/version/rights provenance and structured duration/shape extraction remain research work.

## Delivery and validation

Preview: http://127.0.0.1:8168/whole-site.html. Repair report: http://127.0.0.1:8168/preview/analysis-repairs.html. Server: `C:/Users/jarod/.codex/visualizations/2026/10/06/01a112de-10d8-7230-b5ab-c5950201bd54/faithful-polish-preview/serve_preview.py`. It applies existing usability transformations in memory, serves changed-only overlays before shared current artifacts and patches guarded details in memory. Restart with `py -3 serve_preview.py` in that directory if needed.

Focused app/worker/statistics and renderer tests, real candidate artifact loader checks, source guards and retained regressions are recorded in the final repair receipt. The original baseline tests retain their statistical assertions; the adapter only updates intentional witness wording and the worker cache version. There is no full bundle build or redundant data copy.

Future authorized deployment must use a new immutable data prefix, include both repair identities and preserve the current validated production plus the single known-good rollback. Do not overwrite the old immutable release artifacts or rebuild/copy the entire corpus into this worktree.

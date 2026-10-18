# Startup comparison protocol

Goal: preserve the usable scoped map and loading cover while removing the total-readiness regression.
This is a preview-only change. Production and the designated rollback remain unchanged.

Compare A, the original full-startup path (`?progressiveStartup=0`), with B, the repaired progressive
path (`?progressiveStartup=1`), in the same deployed build, browser tab, viewport, connection and
unchanged catalog. Both use the same runtime code, integrity gates and immutable source assets.
The A path has no scoped startup population or progressive UI. Shared single-flight and date
conversion optimizations apply equally, making A a conservative current baseline rather than
using older, independently measured timings. Do not compare the old 12-second observation
directly with this experiment.

Run one unmeasured complete navigation of each path to warm their assets. Then perform six
complete navigations in the predeclared order A, B, B, A, A, B. Do not change filters, inspect
reports, switch tabs or scroll during the measured interval. Reuse normal browser caching
without clearing it between runs. Do not infer cold-cache or mobile results from these runs.
Record every run, including failures or slow samples. No run is discarded or retried to improve
the result. Report medians and full ranges, and retain data/canvas/readiness parity per run.

Use two milestones: actual usable default map (loading cover dismissed after the full visual
gate), and complete catalog readiness (dates, search and Analysis enabled). A's usable map
milestone is full readiness because its cover remains until then. B's earlier cheap render is
never counted before its verified visual gate. Record application timing and the application
start offset from navigation separately; end-to-end comparisons include that offset.

Also record phase times, source-wait versus hydration time, full 702,893-row worker readiness,
770 mapped reports, 721 visible trace links and the direction distribution, plus preserved dates.
Successful B completion must retain the initial viewport. Background failure must retain the
verified scoped map with retry; this is tested separately from speed measurement.

Storage: use the one existing bounded stage and shared canonical data. New reports, tests and
runtime deltas are expected below 5 MiB; no new file above 100 MiB, corpus copy or extra staging
tree is needed. Production `b4e04dc8-4605-486e-bdbc-174acd3ca37e` and rollback
`626b22b4-af0a-4252-8525-0ba21289c0d0` remain protected. The new validated preview replaces
`e75adec1` as the current candidate; old provider preview history is superseded and proposed
for cleanup after review. No dataset deletion is proposed.

## Additional tab-lifecycle condition

The completed ABBAAB existing-tab series is retained in full. Both paths slowed substantially
relative to their unmeasured warm-ups; catalog consumer processing approximately doubled.
This observation does not establish its cause. Add a separate, explicitly labelled fresh-tab
series to distinguish opening the tool from repeated navigation history in a data-heavy tab.
Do not replace or exclude the existing-tab measurements.

Keep the browser profile, warmed HTTP cache, runtime, viewport and connection unchanged.
Close only agent-owned map preview tabs between samples; preserve login and unrelated tabs.
Open each measured page visibly in a fresh tab, in the declared order A, B, A, B, A, B.
Retain all six runs, failures and slow samples. Report both conditions separately, without
pooling them or claiming that a fresh tab is equivalent to a cold HTTP cache.

Both series completed on runtime `2ebbc3a`, deployment `cb8556e1`. All twelve measurements
are retained in `startup_controlled_comparison.json`. Preliminary warm-ups from earlier
development builds are separately labelled and excluded from the measured summaries.

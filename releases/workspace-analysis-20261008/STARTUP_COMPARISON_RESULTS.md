# Preview startup repair and matched comparison

Current preview: <https://progressive-startup-20261018.ufo-timeline.pages.dev/?progressiveStartup=1>.
Deployment `cb8556e1-d941-4ff7-8e6d-b10cdea21aad`, runtime `2ebbc3a`.
Production remains `b4e04dc8-4605-486e-bdbc-174acd3ca37e` (source `576e09b`).

The full-startup regression is substantially reduced. The early map and loading screen remain.
Full readiness is in the standard path's range; repeated reloads retain a roughly one-second
median disadvantage. These samples do not demonstrate a universal total-speed improvement.

| Condition | Standard map/full median | Preview usable-map median | Preview full median |
|---|---:|---:|---:|
| Fresh tab, warm HTTP cache | 16.36 s | 4.11 s | 15.88 s |
| Repeated navigation, warm HTTP cache | 17.65 s | 4.61 s | 18.67 s |

Three measured samples per path in each condition. Fresh-tab full ranges: standard
15.15–17.31 s, preview 15.85–18.66 s. Repeated-navigation full ranges: standard
17.55–18.42 s, preview 17.42–18.74 s. All twelve runs, including slow observations,
are retained; the conditions are not pooled. Times include navigation-to-application startup.
The same browser profile, 1265×720 viewport, asset cache, connection, dataset and deployed
runtime were used. There was no filter, report, scrolling or tab interaction during timing.
Fresh openings closed the prior agent-owned map tab; login tabs were preserved.

This compares standard full startup with progressive startup in one build. Shared safe
optimizations apply to both paths, making the standard path a conservative baseline.
The prior approximately 12-second and 29-second observations were not controlled pairs
and are not used to calculate a speed ratio. Warm-ups were sometimes faster than measured
runs; those observations are preserved separately. Neither cold-cache nor mobile speed
is established. The cause of the lifecycle-related variation is not established.

What changed:

- Progress UI discovers controls once, checks only newly added controls, and skips unchanged
  text writes. Previously each update and its resulting mutations repeated a 91-part global scan.
- The two correction indexes are single-flight and reused by the initial and complete views.
- Global evidence, packed points and four initial summary shards load concurrently during
  the initial view's visual preparation. Hydration waits for complete annotations.
- Replacement shard requests begin before consuming the active shard: four pending plus one
  active, with bounded memory and ordered ingestion. The global trace index preloads concurrently.
- Canonical hydration reuses its computed date ordinal. No unknown dates or timing are invented.
- Both paths refresh Results after the final visibility transition, preventing stale counts.

All twelve runs passed data/visual parity: 702,893 worker rows, 770 mapped/default Results,
721 visible links, the same 254 ordered / 467 unknown-order radar distribution, unchanged
1954-09-01 through 1954-11-30 dates, completed facility/canvas/tile gates and a dismissed cover.
Targeted tests cover loader reuse, prefetch bounds/order, annotation barriers, timing handoff,
background failure/retry, viewport/date preservation, final visibility counts and native control locks.

Storage lifecycle: canonical candidate remains `.tmp/workspace-analysis-20261008-pages`
(199 files, 40,032,955 bytes; tree SHA-256
`8c8b14bc55b0423b412099c4bed7f1edd69d296d8e823c4245da0ce7db3eecf6`).
The 87 immutable R2 objects / 101,875,689 bytes are unchanged. Retained rollback is
`626b22b4-af0a-4252-8525-0ba21289c0d0`. No new file exceeds 100 MiB; task growth is below
5 MiB, with no corpus copies or extra staging/backup trees. Prior candidate `e75adec1` and
interim previews `8bd25ecd` / `e9061161` are superseded provider history proposed for cleanup
after review. Earlier unique QA reports remain provenance, not additional runtime copies.
No dataset or analysis deletion is proposed.

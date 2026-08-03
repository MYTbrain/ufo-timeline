# UFO Timeline context layers default-on release - 2026-08-03

Crop circles and Animal Mutilation Reports now turn on automatically after the
core UFO Timeline reaches `Ready`. Their bootstrap scripts remain lightweight:
neither optional runtime nor either point index is requested before that Ready
boundary. Animal catalog and detail payloads remain interaction-lazy.

Animal reports now use one recognizable, deterministic upside-down Holstein cow
across the overlay toggle, map markers, and selectable legend. The embedded SVG
uses near-black `#101417` with cool off-white `#e9f2ff`, intentionally distinct
from the map's warm light colors. It requires no image request, remains
pointer-transparent and decorative, and scales from 21 to 30 px for grouped
positions.

Users can turn either context layer off and back on. Reset Legend restores both
default-on layers. For crop circles it also clears chronology, UFO-relation,
trace-analysis, hop, radius, isolation, selection, and detail-panel state rather
than disabling the layer.

## Scientific contract

- No animal or crop record changed.
- Animal coverage remains 1,177 reports: 518 mapped, 659 unmapped, 921
  exact-day, 339 mapped exact-day, and 28 undated.
- Every animal record remains `reported_unreviewed`, noncausal,
  `traceEligible=false`, and `traceRole=context_only`.
- Animal reports remain excluded from UFO relationships, traces, hops,
  chronology, playback, proximity/radius tools, craft typing, and craft-color
  logic.
- Exact-coordinate filtering still yields zero animal markers because public
  animal locations retain `location_precision=unknown`.
- The crop-circle dataset and its scientific nonpromotion rules are unchanged;
  crop chronology and trace analysis remain explicit opt-ins.
- All existing crop and animal R2 payload objects are unchanged. This release
  publishes only a new immutable Pages reproduction archive.

## Frozen release evidence

- Application commit:
  `975e90016b604e1196e082c0364c59eabb5d9cb9`
- Pages candidate: 134 files, 54,925,063 bytes, tree SHA-256
  `a9da150aa9122a01723a63eb698e3875c1b2cf8b5436a5ecbe59ae8940add441`
- Git source-overlay tree: 43 files, 8,789,110 bytes, SHA-256
  `d225ecd99c45cfadf36009b3f884c6acc86495fda2ef2aceff9b1c9e387bd3ed`
- Preview deployment:
  `f7c697f6-9dba-4e01-b015-d3d111f5c6bd`, branch
  `context-layers-default-on-preview`
- Production deployment:
  `6b19dddf-6a6a-4609-925c-b5277ab7ce1f`, branch `main`
- Production promotion reused all 133 uploaded assets from the frozen preview
  candidate and uploaded zero changed file assets; `_headers` was promoted from
  the same directory.
- Reproduction release: `context-layers-default-on-v1-20260803`
- Reproduction archive: 8,693,168 bytes, SHA-256
  `c3db24341a7183c6fbcc6889ed8c3bfb8d85770debc89f6e442ec51c767e53cb`
- Reproduction manifest: 187,550 bytes, SHA-256
  `b439d1c65733ae3c32684cf80a95b61f76841e7fe821e558dc8c4ed8dd16d504`
- Unchanged full R2 payload tree SHA-256:
  `5cfd7f9e3158facdfc4d3de42fd388093fb8dfa2d617a9608a1d04127f4563a2`

## Acceptance

- Complete Python suite: 1,207 passed, four subtests passed, with one existing
  upstream deprecation warning.
- Browser-side suites: 12 / 12 passed.
- Candidate validation passed exact inventory, Pages safety, R2-only exclusion,
  manifest, hash, and source parity gates.
- The reproduction archive and manifest matched byte-for-byte across two
  independent builds.
- Online hydration downloaded the published immutable archive and reproduced
  the exact candidate and source trees.
- Production verification passed baseline-source identity, canonical production
  drift, all optional-layer R2 hashes, and all source/generated parity checks.
- Local, immutable-preview, and immutable-production Browser QA reached Ready
  without console warnings or errors. All Time rendered 3,632 crop records at
  2,170 mapped positions and 339 animal reports at 256 generalized positions.
- Browser QA confirmed both layers default on, successful off/on cleanup and
  restoration, identical toggle/map cow art, near-black and cool-white fills,
  computed 180-degree rotation, 21 px singleton size, and disabled pointer
  events.

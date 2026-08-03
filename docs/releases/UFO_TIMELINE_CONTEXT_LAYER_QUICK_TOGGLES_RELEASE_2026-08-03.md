# UFO Timeline context-layer quick toggles release - 2026-08-03

Crop circles and Animal Mutilation Reports remain on by default after the core
timeline reaches `Ready`. A separate two-button context-layer pill now appears
immediately to the right of the existing Map, Military, Research, and Traces
quick controls. Both buttons are native, labeled toggle buttons and delegate to
the canonical controls in Overlays + View rather than creating a second loading
path.

The crop-circle toggle, Overlays + View chip, and selectable legend now reuse one
self-contained SVG rendition of the map marker. Its 24 px coordinate system,
8.3 px singleton radius, 4.6 / 2.0 px rings, 35-point spiral, 4.2 / 1.9 px
spiral strokes, and 1.8 px exact-coordinate dot match the Canvas renderer. The
animal toggle reuses the existing upside-down Holstein cow in near-black
`#101417` and cool off-white `#e9f2ff`, distinct from the map's warm whites.

Quick controls, Overlays + View, and the legend synchronize pressed, loading,
disabled, and failure states. Responsive layouts keep the context buttons in a
separate pill, wrap them as a unit when needed, and stack them in collapsed mode.

## Scientific contract

- No crop or animal record, manifest, bootstrap, heavy layer runtime, or R2 data
  payload changed.
- Animal coverage remains 1,177 reports: 518 mapped, 659 unmapped, 921
  exact-day, 339 mapped exact-day, and 28 undated.
- Every animal record remains `reported_unreviewed`, noncausal,
  `traceEligible=false`, and `traceRole=context_only`.
- Animal reports remain excluded from UFO relationships, traces, hops,
  chronology, playback, proximity/radius tools, craft typing, and craft-color
  logic.
- Crop chronology and trace analysis remain separate, explicit opt-ins.
- This follow-up publishes only the immutable Pages reproduction archive; the
  existing 39 optional-layer payloads remain byte-identical.

## Frozen release evidence

- Application commit:
  `e16740c620244ce8026ee595f096d03bac6662b8`
- Pages candidate: 134 files, 54,933,569 bytes, tree SHA-256
  `465002faa4145226bae6bffabbba03473e4722317ffa91606c36f7e5270638a2`
- Git source-overlay tree: 43 files, 8,797,616 bytes, SHA-256
  `86e73af25b472b4547cae82f5063fff144a78204a902177f629cc4235a1b5c22`
- Preview deployment:
  `d8c33d71-cb3b-457f-9bec-01e399ee9154`, branch
  `context-layer-quick-toggles-preview`
- Production deployment:
  `688e156d-1a4e-44d5-8a60-de1d6554ee18`, branch `main`
- Production promotion reused all 133 uploaded assets from the frozen preview
  and uploaded zero changed file assets; `_headers` came from the same folder.
- Reproduction release: `context-layer-quick-toggles-v1-20260803`
- Reproduction archive: 8,694,455 bytes, SHA-256
  `6f3bbe200364aed283f3b1837b2ca14bea52ecde687544e161e82491b53fa9d2`
- Reproduction manifest: 187,554 bytes, SHA-256
  `d110d1b18fc722be12d3c75d09814bcc0ca4a4d99b2d8646dd5e51fb97bcb2b5`
- Optional-layer payload contract: 39 objects, 1,980,282 bytes, SHA-256
  `79b36c280aea52c234cc61c8ae0e0230b71e60aad92b2bc1a21bf7f29a84ea94`
- Unchanged full R2 tree SHA-256:
  `5cfd7f9e3158facdfc4d3de42fd388093fb8dfa2d617a9608a1d04127f4563a2`

## Acceptance

- Complete Python suite: 1,208 passed, four subtests passed, with one existing
  upstream deprecation warning.
- Browser-side suites: 12 / 12 passed.
- Animal validation-only publisher: 7 objects, 404,556 bytes.
- Crop validation-only publisher: 32 objects, 1,575,726 bytes.
- Candidate validation passed exact inventory, Pages safety, R2-only exclusion,
  manifest, hash, and source-parity gates.
- Two independent builds produced byte-identical archive and manifest hashes.
- The new R2 key was proven absent before upload; online hydration then
  downloaded the published archive and reproduced the exact Pages tree.
- A clean clone at `170d54ab4c725506c3bacfb5cbe9ebd4463929ad`
  rehydrated and revalidated the 134-file Pages candidate, then verified all
  366 canonical R2 objects and all 39 optional-layer objects. Its localized
  offline site contained 530 files, 970,466,284 bytes, with tree SHA-256
  `0db2c8cabcc66bf7cc848dce1ba2ad9264bb6635ac39d7f9cd41ffae86422e0c`;
  the clean clone remained unmodified.
- Production verification passed baseline-source identity, canonical production
  drift, all optional-layer R2 hashes, and source/generated parity.
- Local, immutable-preview, immutable-production, and canonical-production
  Browser QA reached Ready with no console warnings or errors. It verified
  shared crop/cow art, exact crop geometry, three-way toggle synchronization,
  visible light/dark pressed states, same-row placement, collapsed layout, and
  default-on restoration.
- Production All Time rendered 3,632 crop records at 2,170 mapped positions and
  339 animal reports at 256 generalized positions; 659 unmapped animal reports
  remained available through Browse all reports.

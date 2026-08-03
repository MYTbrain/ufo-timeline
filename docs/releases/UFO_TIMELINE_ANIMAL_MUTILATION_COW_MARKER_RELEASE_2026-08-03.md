# Animal Mutilation Reports cow-marker release — 2026-08-03

Animal Mutilation Reports now use a small upside-down cow silhouette instead
of the prior dashed amber circle. The marker is a deterministic inline SVG
mask, not a platform emoji or fetched image. It remains neutral amber,
decorative, pointer-transparent, keyboard-inert, and isolated to the animal
layer. The toggle swatch and map legend use the same cow silhouette.

Shared generalized positions remain grouped. Cow dimensions scale from 21 px
for a singleton to 30 px for the largest visible stack, preserving the prior
stack-size cue. The existing map-level hit test still opens the corresponding
report or shared-position detail stack.

No animal data, coordinates, classifications, evidence states, privacy rules,
or scientific nonpromotion fields changed. The frozen contract remains 1,177
reports, 518 mapped, 659 unmapped, and 400 generalized map positions. The
animal R2 release and all seven data objects are unchanged.

## Frozen release evidence

- Application commit: `122bde4525c6a9cd2f1f5a344f934cb1dc809411`
- Pages candidate: 134 files, 54,921,123 bytes, tree SHA-256
  `76ce86e6f64837c61eccb95260b8037fe068301ed2650f32ceef178f7394a272`
- Git source-overlay tree SHA-256:
  `650c0992ae63c82d0953a5671047a9e56acf0312d8deaa5a522dee87babd8160`
- Preview deployment: `a6a4b958-7926-4d3a-9d0b-9b6311ee93f9`, branch
  `animal-mutilation-cow-preview`
- Production deployment: `2f372d2d-6625-4f5d-8eca-425fb624b06d`, branch
  `main`; promotion uploaded 0 changed file assets and reused all 133 assets
  from the frozen preview candidate
- Reproduction release: `animal-mutilation-cow-v1-20260803`
- Reproduction archive: 8,692,340 bytes, SHA-256
  `e74be365087f6fa3e4ebbdb069e045a5d58c81ea75f24bb62fe113354d09d05c`
- Reproduction manifest SHA-256:
  `d61277ecb7277827d0c78288c72851e0fe3d07fde7b3ae9dea8c7e1d87976047`

## Acceptance

- Complete Python suite: 1,207 passed with one existing upstream deprecation
  warning
- Browser-side suites: 12 / 12 passed
- Preview Browser QA: zero cow markers before opt-in; 256 exact-day positions
  after opt-in and All Time; amber inline mask present; computed 180-degree
  rotation; 21–30 px stack scaling; pointer events disabled; marker detail
  loading passed; zero console warnings or errors
- Production smoke at `https://ufo-timeline.pages.dev`: cache-busted cow assets
  present; zero startup cow markers; the same 256-position rendering contract;
  matching color, mask, rotation, scale, and pointer isolation; zero console
  warnings or errors

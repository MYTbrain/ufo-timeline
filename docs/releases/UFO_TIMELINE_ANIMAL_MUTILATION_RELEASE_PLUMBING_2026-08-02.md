# Animal Mutilation Reports release plumbing — 2026-08-02

The optional layer uses immutable release ID
`animal-mutilations-v1-20260802` and R2 prefix
`releases/animal-mutilations-v1-20260802/`. Pages receives only the manifest,
bootstrap, runtime, and shell assets. Points, the all-record catalog, and five
detail chunks remain R2-only.

`scripts/publish_animal_mutilation_r2_release.py` validates local byte counts,
SHA-256 identities, decoded JSON/counts, the corrected handoff and coordinate
audit identities, and all scientific nonpromotion policy fields before making
any network request. Publication preflights every immutable key with HEAD plus
byte readback, skips byte-identical objects, refuses any mismatch before the
first upload, uploads only missing objects through the repo-pinned Wrangler,
and reads every object back afterward. The Windows launcher invokes the pinned
Wrangler JavaScript entrypoint through Node rather than executing the POSIX
`.bin/wrangler` shim.

Reproduction discovers crop and animal payloads from their manifests. Pages
validation rejects all declared R2 payloads and every undeclared file beneath
either layer root. Offline hydration verifies and copies the payloads, rewrites
the manifest asset bases to local paths, and retains exact inventory checks
before localization. Review queues, raw pages, caches, images, private inputs,
and provenance-only audit files are neither Pages nor browser-R2 artifacts.

Preview and production deploys require an explicit Cloudflare branch and the
same frozen bundle path:

```powershell
python scripts\publish_animal_mutilation_r2_release.py --validate-only
python scripts\publish_animal_mutilation_r2_release.py
powershell -ExecutionPolicy Bypass -File scripts\cloudflare_deploy_pages.ps1 `
  -ProjectName ufo-timeline `
  -BundleRoot <frozen-pages-candidate> `
  -Branch <explicit-preview-or-production-branch>
```

The publication gate is satisfied by corrected handoff release commit
`1c08784af354b2666ac3c1637a2c68974c3c1af8`, ZIP SHA-256
`C78B85EE4FE0818F1C1F1252269AE084E7B2F16ED13FCD7DB76D3FE8B3B0979B`,
and coordinate-audit SHA-256
`82BB3508906AA4B850D59CC6179C645EFBAEE21BBEED0D9E52809EB869BC44C7`.
The audit covers all 1,177 reports, records exactly 479 corrections, and passes
semantic geography validation.

## Frozen release evidence

- Stacked handoff merge: `024a2f5e761791088b7eecdc7cf541a71d5adc26`
- Deployed application commit: `af2f87bba5c66355235ab9ca57043eeceb99b693`
- Animal R2 publication: 7 / 7 objects, 404,556 bytes, independently read back;
  a second publication pass reported all 7 already present and uploaded 0.
- Pages candidate: 134 files, 54,919,484 bytes, tree SHA-256
  `2ff093d68531c3c78f3dd6784f7d6f3ff7e9be2d87868796589704af58f63e67`.
  Validation found zero crop or animal R2 payloads in Pages.
- Preview deployment: `ed6e09b2-fe77-4a75-8593-f4888580cdf6`, branch
  `animal-mutilations-v1-preview`.
- Production deployment: `56481f8e-83c9-4d35-9404-7ee7257479ce`, branch
  `main`. Promotion reused all 133 file assets and uploaded 0 changed files.
- Reproduction archive: 8,691,874 bytes, SHA-256
  `3de80f0dded0557e99d3bd60f9f5f0419b90548817d0e5a29925cb2db4f61b22`.
- Final acceptance: 1,207 Python tests passed with one upstream deprecation
  warning; all 12 JavaScript suites passed. The clean-clone hydration verified
  366 canonical R2 objects, all 39 optional-layer objects, exact Pages
  inventory, R2-only exclusions, and source/generated parity.
- Preview Browser QA covered desktop and 390 x 844 mobile layouts, keyboard
  focus restoration, zero startup animal-data requests, Browse-only catalog
  loading, detail-chunk laziness, map-only point loading, 518 / 400 All Time
  map counts, 339 exact-day mapped reports, the zero exact-coordinate result,
  pointer-transparent markers, disable cleanup, and zero console errors.
  Production smoke repeated the off-by-default and 1,177-record browser gates
  on `https://ufo-timeline.pages.dev` with zero console errors.
- Live drift verification matched 42 public source files, all 39 optional-layer
  R2 objects, canonical counts and R2 manifest, source tree SHA-256
  `18ebe90da91fcc6bae65a6bfc36be3aa0aa12a945225787d7cced2cb629ef436`,
  optional-layer tree SHA-256
  `79b36c280aea52c234cc61c8ae0e0230b71e60aad92b2bc1a21bf7f29a84ea94`,
  and canonical R2 tree SHA-256
  `5cfd7f9e3158facdfc4d3de42fd388093fb8dfa2d617a9608a1d04127f4563a2`.
  `_headers` remains pinned in the Pages archive but is correctly excluded from
  HTTP drift reads because Cloudflare consumes it as a non-public control file.

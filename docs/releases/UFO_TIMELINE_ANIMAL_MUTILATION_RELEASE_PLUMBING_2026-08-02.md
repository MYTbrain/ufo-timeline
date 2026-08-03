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
semantic geography validation. Network publication remains a separate release
step after the product tree is frozen and its preview candidate passes QA.

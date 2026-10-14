# Phone-accessible encounter preview

Public review link:
https://encounter-preview-20261013.ufo-timeline.pages.dev/whole-site

Cloudflare deployment `fbc9e7d7-edd2-47c9-ac3c-6bd8840f5d20` is explicitly a
**Preview** on branch `encounter-preview-20261013`, with runtime source `169c0b2`.
No GitHub push, production deployment, new R2 data upload or account permission
change was performed. Production before and after remains
`626b22b4-af0a-4252-8525-0ba21289c0d0` on `main` (`8721330`). The retained production
rollback remains `192e21f6-9c44-4b89-8d88-361e1c3d10d6`.

`shell.json` is the exact public-asset allowlist, source pins and temporary-copy
removal inventory. It contains196 runtime files, totaling39,680,968 bytes. Source
archives, repository files, research scripts, scientific QA and the complete UFO
corpus were not exposed by the deployment. Published R2 data is reused. The
latest encounter evidence/origins/enrichment and small nuclear extension are
served by the preview itself. `whole-site.html` aliases the unchanged current
index, and preview headers prohibit indexing.

`public-verification.json` records194 remotely streamed/hash-verified files,
checked static references, and an HTTP200 mobile-client response with the latest
runtime and Encounters section. The provider-normalized alias is `/whole-site`.
The preview is usable independently of the desktop's local port8168. A standalone
default-Python-user-agent header probe returned403; explicit release-verifier and
mobile-browser probes returned200. No security settings or access restrictions
were changed. Interactive visual testing from a native phone/browser is not
claimed by these HTTP checks.

After verification, the exact inventoried37.84MiB shell copies were removed;
the existing validated production stage and all canonical sources remain in
place. `storage.json` records the retention and removal decision. Net growth is
under500KiB of reproducibility/verification files plus small Git/Wrangler cache
metadata; no newly created file is larger than100MiB. No superseded local shell
remains. The requested remote review preview is retained while the user reviews
it; it is not promoted to production.

Replay uses `scripts/prepare_phone_preview.py`, shared Wrangler with an explicit
nonproduction `--branch`, and `scripts/verify_phone_preview.py`. Never use the
generic deployment wrapper without its missing preview-branch protection, and
never refresh or overwrite the retained production stage for this preview.

The current review adds visible encounter legend entries, an independent marker
layer, explicit overlay/report filter targeting, bounded report inspection and
existing-link highlights. The final v5 runtime also clears highlights when the
published trace population becomes pending. Details and test contracts are in
`docs/ENCOUNTER_MAP_20261013.md`. The intermediate v4 preview was superseded by
this verified candidate; its source and verification snapshot remain recoverable
in Git, with no retained local staging copy.

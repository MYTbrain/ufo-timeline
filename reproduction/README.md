# Exact UFO Timeline Reproduction

This directory defines the immutable production-data contract for the UFO
Timeline. A reproduction combines:

1. the source code and small scientific assets from the checked-out Git
   revision;
2. the deterministic Pages archive recorded in `release.json`; and
3. the immutable, versioned canonical R2 objects recorded with exact byte
   counts and SHA-256 hashes in `release.json`; and
4. manifest-declared optional-layer R2 payloads pinned in Git for crop circles
   and Animal Mutilation Reports.

The current Git checkout is always overlaid after the frozen Pages archive is
extracted. As a result, future committed interface or application changes are
automatically present in the reproduction. A data-release change requires a
new manifest generated from the frozen deployment; CI and the scheduled drift
check fail closed if live production points to a different data release.

## Reproduce locally

Use the exact Python and Node versions from `.python-version` and `.nvmrc`.

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install --require-hashes -r requirements.lock
npm.cmd install --global npm@11.16.0
npm.cmd ci --ignore-scripts
.\.venv\Scripts\python.exe scripts\reproduction.py verify
.\.venv\Scripts\python.exe scripts\reproduction.py hydrate --offline
.\.venv\Scripts\python.exe scripts\reproduction.py serve
```

Open <http://127.0.0.1:8000>. After hydration, the local site no longer needs
R2 for application data; production R2 URLs in `data/app_config.json` and each
optional-layer `manifest.json` are localized to verified files. Optional-layer
payloads are copied only for offline hydration and are rejected from every
Pages deployment candidate.

The compact offline reproduction needs roughly 1 GB. To reproduce the full
scientific acceptance environment, including uncompressed siblings expected
by the repository's artifact tests, add `--expand-gzip`; allow roughly 9 GB of
free disk space:

```powershell
.\.venv\Scripts\python.exe scripts\reproduction.py hydrate --offline --expand-gzip --output static_bundle
.\.venv\Scripts\python.exe -m pytest -q
$nodeTests = @(Get-ChildItem tests -Filter '*.mjs' -File | Select-Object -ExpandProperty FullName)
node --test $nodeTests
```

## Integrity guarantees

- The Pages archive is deterministic and tied to an immutable Pages deployment.
- Every R2 object is tied to a versioned `releases/` prefix.
- Every archive and object has an exact byte count and SHA-256 digest.
- Downloads retain certificate and hostname verification. The reproducer
  disables only Python 3.14's extra strict-X509 flag for compatibility with
  otherwise valid Cloudflare certificate chains.
- Archive extraction rejects absolute paths and parent-directory traversal.
- Source files from `webapp/static_public` overwrite the release baseline on
  every hydration, so the reproduced application follows the Git revision.
- Optional-layer manifests are the delivery allowlist. Any undeclared review
  queue, raw page, cache, image, audit, or private input under a browser layer
  root fails closed.
- The clean-clone GitHub workflow installs only locked dependencies, hydrates
  the full release, and runs all Python and browser-side tests.
- The weekly production-drift workflow compares the live R2 pointer, event
  counts, R2 manifest, and every authoritative frontend source asset to Git.

## Publish a future production release

First freeze and deploy the exact Pages directory through the existing
preview-to-production process. Then run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\publish_reproduction_release.ps1 `
  -PagesRoot cloudflare_bundle_r2_NAME `
  -PagesDeploymentId FULL-CLOUDFLARE-DEPLOYMENT-ID `
  -ReleaseId IMMUTABLE-RELEASE-ID
```

This command deterministically archives the frozen Pages directory, recomputes
all Pages/R2/source hashes, uploads the small Pages archive to a versioned R2
key, downloads it back for verification, and rewrites `release.json`. Commit
the refreshed manifest with the product change. Never point the contract at
the mutable `ufo-timeline.pages.dev` hostname or an unversioned R2 prefix.

Reproduction does not publish credentials, private Cloudflare state, or the
multi-snapshot working corpus. The immutable production artifacts are the
authoritative runtime data needed to recreate the served product exactly.

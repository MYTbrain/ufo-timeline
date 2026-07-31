# Deploying The Static UFO Map

## Recommended Public Cloudflare Path

For the current large canonical catalog, use Cloudflare Pages for the app shell
and Cloudflare R2 for large `data/canonical_web/` artifacts. Do not upload the
raw `static_bundle/` directly to Pages for public production unless you have
already confirmed every file is below Pages limits and the large data load is
acceptable.

Build a Pages/R2 bundle with:

```powershell
& "C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" scripts\build_public_cloudflare_bundle.py `
  --static-root static_bundle `
  --output-root cloudflare_bundle_r2 `
  --r2-base-url https://YOUR_R2_PUBLIC_BASE_URL/ufo
```

For an isolated, immutable release, make the public URL path and R2 key prefix
match. This prevents a later canonical rebuild from changing an already-published
Pages deployment:

```powershell
& "C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" scripts\build_public_cloudflare_bundle.py `
  --static-root static_bundle `
  --output-root cloudflare_bundle_r2 `
  --r2-base-url https://YOUR_R2_PUBLIC_BASE_URL/releases/RELEASE_NAME `
  --r2-key-prefix releases/RELEASE_NAME
```

This command:

- rebuilds curated startup profile artifacts, currently `1954 France Sept-Nov`
  and `1989-1990 Belgium wave`
- creates `cloudflare_bundle_r2/` for Cloudflare Pages
- writes `cloudflare_bundle_r2/r2_upload_manifest.json` listing files that must
  be uploaded to R2 with the same relative keys
- writes `cloudflare_bundle_r2/upload_r2_assets.ps1`, a repeatable Wrangler
  upload script that sets `Content-Type` while leaving `.gz` artifacts without
  `Content-Encoding`, because the app fetches compressed bytes and decodes them
  in JavaScript
- rewrites large canonical data URLs in `data/app_config.json` to the R2 base URL
- validates the result before upload

For local dry runs only, placeholder R2 URLs can be allowed explicitly:

```powershell
& "C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" scripts\build_public_cloudflare_bundle.py `
  --static-root static_bundle `
  --output-root cloudflare_bundle_r2 `
  --r2-base-url https://example-r2.invalid/ufo `
  --allow-placeholder-r2
```

The validator intentionally fails public bundles that still use placeholder R2
hosts. Before a real upload, run:

```powershell
& "C:\Users\jarod\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" scripts\validate_cloudflare_bundle.py --bundle-root cloudflare_bundle_r2
```

Expected deployed layout:

- `cloudflare_bundle_r2/` goes to Cloudflare Pages.
- Every path listed in `cloudflare_bundle_r2/r2_upload_manifest.json` goes to R2.
- R2 object keys must match the `r2_key` values exactly.
- R2 should use long-lived immutable cache headers for versioned data artifacts.

If you use Wrangler, upload the canonical artifacts with:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\cloudflare_upload_r2.ps1 `
  -BucketName YOUR_R2_BUCKET_NAME
```

R2 must allow browser fetches from the Pages origin. Configure CORS with:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\cloudflare_configure_r2_cors.ps1 `
  -BucketName YOUR_R2_BUCKET_NAME
```

This repo also includes local Cloudflare wrappers that do not require `npm`,
`node`, or `wrangler` to be visible on the global `PATH`:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\cloudflare_login.ps1
powershell -ExecutionPolicy Bypass -File scripts\cloudflare_whoami.ps1
powershell -ExecutionPolicy Bypass -File scripts\cloudflare_deploy_pages.ps1 `
  -ProjectName YOUR_PAGES_PROJECT_NAME
```

If OAuth login prints a URL, keep that PowerShell command running while you
authorize in the browser. Wrangler's OAuth redirect uses
`http://localhost:8976/oauth/callback`, so do not override the callback port
unless Cloudflare changes the redirect URL too. If browser OAuth is blocked by
local firewall/proxy behavior, use an API token instead:

```powershell
$env:CLOUDFLARE_API_TOKEN = "YOUR_TOKEN"
powershell -ExecutionPolicy Bypass -File scripts\cloudflare_whoami.ps1
```

Once R2 is enabled on the Cloudflare account, a first public deploy can be run
with the account's public `r2.dev` bucket URL:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\cloudflare_deploy_public.ps1 `
  -BucketName ufo-timeline-data `
  -ProjectName ufo-timeline `
  -UseR2DevUrl
```

For a custom R2 domain, pass the public base URL explicitly instead:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\cloudflare_deploy_public.ps1 `
  -BucketName ufo-timeline-data `
  -ProjectName ufo-timeline `
  -R2BaseUrl https://assets.example.com/ufo-timeline
```

The generated script uploads from `static_bundle\data\canonical_web\...` and
uses the minimized R2 upload set: small canonical manifests/metadata are
uploaded uncompressed, while large binary/chunk/shard artifacts are uploaded as
their `.gz` objects only. This keeps the current R2 upload payload around
`482 MB` instead of uploading duplicate raw and gzip copies.

Startup behavior is intentionally progressive: the shell and scoped famous-flap
preview load first, then the broader canonical catalog hydrates in the
background.

## Startup And Trace Performance Benchmarking

Use the CDP benchmark script when comparing Chrome, Edge, local preview, and
Cloudflare preview behavior. It opens the app in a real browser, waits for the
startup loader to report ready, and can optionally probe static trace rendering.

Chrome local preview:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\benchmark_public_startup_cdp.ps1 `
  -Url http://127.0.0.1:8130/index.html `
  -ProbeStaticTraces `
  -OutputPath data\reports\startup_benchmark_chrome_local.json
```

Edge local preview:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\benchmark_public_startup_cdp.ps1 `
  -BrowserPath "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" `
  -Url http://127.0.0.1:8130/index.html `
  -ProbeStaticTraces `
  -OutputPath data\reports\startup_benchmark_edge_local.json
```

Cloudflare preview:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\benchmark_public_startup_cdp.ps1 `
  -Url https://YOUR_PREVIEW_URL/index.html `
  -ProbeStaticTraces `
  -OutputPath data\reports\startup_benchmark_cloudflare_preview.json
```

The JSON report includes browser navigation timing, app startup timing,
canonical trace runtime status, static trace layer state, and facility-proximity
trace metrics. For the current optimized static trace path, prefer
`traceFacility.worker.traceIndexLoadMode = "worker_fetch"`. A
`"message_buffer"` value means the app fell back to main-thread transfer for the
packed trace index and should be treated as slower but still functional. Use
`startupTiming.milestones["time to startup profile preview render"]` as the
default-flap preview metric, and `startupTiming.milestones["time to Ready"]` as
the full global-catalog hydration metric. After the default-flap preview is
painted, the startup diagnostics panel hides unless diagnostics are explicitly
requested or startup fails, so the map can remain usable while the full catalog
hydrates in the background.

Current local baseline on `http://127.0.0.1:8130/index.html`:

- Chrome headless: startup profile preview render around `248 ms`; full `Ready`
  around `7.7 s`; static facility trace worker uses `worker_fetch`.
- Edge headless: startup profile preview render around `264 ms`; full `Ready`
  around `12.3 s`; static facility trace worker uses `worker_fetch`.

The remaining startup bottleneck is full global catalog hydration after the
preview is already interactive, especially summary-shard ingest/catalog
construction. The full initial display sort has been deferred out of the
startup path, normal `YYYY-MM-DD` catalog dates now avoid regex parsing during
hydration, compact summary rows no longer receive empty derived chronology
properties during startup, and playback/stable sort keys are cached lazily
instead of being built for every row up front. The playback/timeline sequence
sort is now about `0.57 s` in Chrome. Do not optimize this by blocking the
startup preview. The next practical slice is to move more of the full-catalog
catalog construction off the initial interactive path or into worker/background
phases.

Deploy the contents of `static_bundle/`. That folder is already a complete static site:

- `index.html`
- `styles.css`
- `app.js`
- `vendor/`
- `data/`
- `reports/`
- `.nojekyll`

Important:

- Hosted static HTTP/HTTPS delivery is the intended mode.
- The current shipped bundle includes the promoted full-detail canonical web payload under `data/canonical_web`.
- The promoted payload is large: 968 canonical web files, 378 lazy event chunks, and about 405 MB of gzip artifacts.
- Static hosting should preserve `.gz` siblings and serve them with correct `Content-Encoding: gzip` where supported.
- Direct `file://` opening may fail in browsers because runtime local chunk loads can be blocked by browser security policy even though the same bundle works correctly once hosted.

All asset paths are relative, so the bundle is path-safe for:

- a site hosted at the domain root
- a site hosted under a GitHub Pages project subpath

Direct `file://` opening is still useful for a quick smoke test of the shell, but it is not a reliable runtime mode for this app because browsers may block on-demand local chunk loads.

## Cloudflare Pages

Reference: [Cloudflare Pages get started](https://developers.cloudflare.com/pages/get-started/) and [Direct Upload](https://developers.cloudflare.com/pages/get-started/direct-upload/)

### Option A: Git-connected Pages project

1. Push this repository to GitHub or GitLab.
2. In Cloudflare, go to `Workers & Pages` and create a new `Pages` project.
3. Connect the repository.
4. Use these build settings:
   - Framework preset: `None`
   - Build command: leave blank
   - Build output directory: `static_bundle`
5. Start the deployment.
6. After the first deploy finishes, open the Pages URL and verify:
   - the map loads
   - the event list renders
   - keyword search works
   - `reports/` links open

### Option B: Direct Upload

1. Open Cloudflare Pages and choose `Upload assets`.
2. Upload the contents of `static_bundle/` as the site root.
3. Wait for the upload to finish.
4. Open the deployed URL and verify the same items as above.

Notes:

- The public bundle has no backend requirement.
- The current bundle defaults to `No basemap world view`, so it does not depend on third-party tile availability.
- The catalog is already split into multiple shard files so no single bundle data file is oversized for normal static hosting workflows.
- If you test by opening `index.html` directly from disk and see browser security errors, deploy the same `static_bundle/` folder to Pages instead of debugging the bundle itself.

## GitHub Pages

Reference: [Creating a GitHub Pages site](https://docs.github.com/en/pages/getting-started-with-github-pages/creating-a-github-pages-site)

### Option A: Publish from `/docs`

1. Create or use a GitHub repository.
2. Copy the contents of `static_bundle/` into a top-level `docs/` folder.
3. Commit and push.
4. In GitHub, open `Settings` -> `Pages`.
5. Under `Build and deployment`, choose:
   - Source: `Deploy from a branch`
   - Branch: your chosen branch
   - Folder: `/docs`
6. Save and wait for the Pages deployment to finish.

### Option B: Publish from repository root

1. Copy the contents of `static_bundle/` into the repository root.
2. Commit and push.
3. In `Settings` -> `Pages`, choose:
   - Source: `Deploy from a branch`
   - Branch: your chosen branch
   - Folder: `/ (root)`
4. Save and wait for the site to publish.

Notes:

- Keep `.nojekyll` in the deployed root. It is already generated in `static_bundle/`.
- Because all app asset paths are relative (`./data/...`, `./vendor/...`), project-site URLs work without rewriting paths.
- No API routes, server functions, or build step are required for end users.
- GitHub Pages is intended to serve the bundle over HTTPS. Direct `file://` testing is not a reliable validation path for this app because browsers may block runtime local file loads.

## Expected Final Structure

The deployed site root should look like this:

```text
index.html
styles.css
app.js
.nojekyll
vendor/
data/
reports/
```

Important subfolders:

```text
data/
  app_config.json
  event_catalog_manifest.json
  event_chunk_manifest.json
  catalog_shards/
  event_chunks/

reports/
  unresolved_locations.csv
  unresolved_locations.json
  ranked_unresolved_locations.csv
  ranked_unresolved_locations.json
```

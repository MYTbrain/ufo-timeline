# UFO Timeline Area Point Popup Repair Release — 2026-07-31

## Outcome

Area Filter and Chronological Neighborhood sighting dots are clickable again.
Clicking a visible sighting dot opens the same full map popup used by ordinary
map points, even when the dot is an outside-area neighborhood endpoint or is
covered by intersecting trace hit targets. Hover tooltips remain available.

Production: <https://ufo-timeline.pages.dev>

## Root cause and repair

- Neighborhood endpoint dots render in a dedicated pane above ordinary point
  markers. Their click handler selected the result but did not open a Leaflet
  popup, so the higher endpoint dot intercepted the click and appeared inert.
- Trace hit forwarding likewise activated the sighting without explicitly
  opening the exact marker under the pointer.
- `activateMapPointEvent` now accepts the clicked marker and opens its popup
  before preserving the existing result-selection and detail-panel behavior.
- Ordinary points, clustered points, trace-overlap forwarding, and
  neighborhood endpoint points now use that shared activation path.
- Neighborhood endpoints bind the standard `buildPopupContent` popup, keeping
  their content and actions consistent with all other sighting dots.

## Changed files

- `webapp/static_public/app.js`
- `webapp/static_public/index.html`
- `static_bundle/app.js`
- `static_bundle/index.html`
- `tests/test_webapp.py`

The authoritative and generated frontend copies are byte-identical. The asset
version is `2026-07-31-area-point-popup-v153`.

## Validation

- Focused regression tests: **2 passed**
- Full Python suite: **794 passed**, with one existing dependency deprecation
  warning
- JavaScript syntax checks: **16/16 passed**
- Executable JavaScript behavior suites: **10/10 passed**
- Static-loadout readiness: **READY**; **580,783** mapped events
- Canonical web-static-payload readiness: **READY**; **730** checked files
- Hosted feature verifier on preview: **40 passed, 0 failed**
- Hosted feature verifier on production: **40 passed, 0 failed**
- Startup on preview and production: **Ready / 100%**

### Browser regression scenario

On both preview and production, a rectangle Area Filter was drawn over the
Maritimes. A Chronological Neighborhood endpoint near Augusta, Maine was
visible outside the rectangle beneath several intersecting traces. Clicking
that endpoint changed the popup count from zero to one and opened the complete
sighting popup, including date, location, source, craft type, precision,
coordinate source, Description, and Full Details. The Description action was
also exercised successfully.

## Frozen artifact and deployments

- Frozen Pages folder:
  `cloudflare_bundle_r2_area-point-popup-v153_20260731`
- Frozen inventory: **127 files**, **54,682,674 bytes**
- Tree-hash algorithm: SHA-256 of ordinal-sorted
  `path<TAB>bytes<TAB>file-sha256<LF>` rows
- Frozen tree hash after production:
  `7c9f2050977f8d21f9282021a475e777e23d21e47dea28c89a6d03c77fc9b2c8`
- Frozen `app.js` SHA-256:
  `d411ceaa0f0a47b908292c8aec2fea7a350b88956a5110f6da13637df739abf2`
- Frozen `styles.css` SHA-256:
  `6c7ed41df0e3f49246714dbe99b9af911fd2489cfff178d06327c36c1944fbe8`
- Frozen `data/app_config.json` SHA-256:
  `2511d000909e6e9637cef25540382e32d24c2ba208298ec7fbfd2e9b27047a32`
- Previous production deployment:
  `5727804b-4d91-47a3-9895-eeb6f60b9165`
- Preview deployment:
  `08e6fb76-7606-459e-8326-dae2e6542a09`
- Preview URL: <https://08e6fb76.ufo-timeline.pages.dev>
- Preview alias: <https://area-point-popup-v153.ufo-timeline.pages.dev>
- Production deployment:
  `767d3188-79e4-4c09-8204-813e39c835a8`
- Immutable production URL: <https://767d3188.ufo-timeline.pages.dev>
- Canonical production URL: <https://ufo-timeline.pages.dev>

Production promotion used the identical frozen preview folder. Cloudflare
reported **0 files uploaded** and **126 already uploaded**. The immutable and
canonical production copies of `app.js`, `styles.css`, and
`data/app_config.json` match the frozen files byte-for-byte.

## Data and storage scope

No canonical event data, backend interface, R2 object, or R2 payload was
changed. The existing v152 R2 release prefix was reused read-only; all **366**
manifested R2 entries were confirmed unchanged.

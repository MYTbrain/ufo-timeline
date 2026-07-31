# UFO Timeline Area Interaction Lifecycle Repair — 2026-07-31

## Outcome

Two related Area Filter interaction regressions are repaired in production:

1. Clearing an Area Filter no longer leaves the Chronological Neighborhood
   interaction pane able to intercept later sighting-dot clicks.
2. Clicking the map outside a sighting popup now dismisses the associated
   Event Description panel as well as the popup.

Production: <https://ufo-timeline.pages.dev>

## Root causes and repairs

### Normal sighting clicks after Clear

Chronological Neighborhood lines and endpoints use a higher map pane so they
can remain usable over dense traces. Clearing the region removed the selection
state, but interaction cleanup depended on the later full map render. The
higher pane could therefore remain interactive after Clear and interfere with
the restored ordinary point layer.

The Clear path now immediately:

- empties the Chronological Neighborhood interaction layer;
- disables pointer events on its map pane;
- closes the neighborhood inspector; and
- then performs the normal results and map redraw.

The pane begins disabled, becomes interactive only while an Area Filter is
active, and is disabled again whenever the neighborhood overlay is inactive.

### Event Description dismissal

Neighborhood endpoint markers did not carry the `ufoEventId` marker metadata
used by the existing Leaflet `popupclose` cleanup. The popup could close, but
the handler could not associate it with the selected event and returned before
closing Event Description.

Every neighborhood endpoint now carries its canonical event ID. Popup-close
cleanup can therefore clear the matching selection and description state in
the same way as ordinary point and cluster markers.

## Changed files

- `webapp/static_public/app.js`
- `webapp/static_public/index.html`
- `webapp/static_public/verify_timeline_features.html`
- synchronized copies in `static_bundle`
- `tests/test_webapp.py`

Asset version: `2026-07-31-area-lifecycle-v154`.

## Validation

- Focused lifecycle regression tests: **3 passed**
- Complete Python suite: **795 passed**, with one existing dependency
  deprecation warning
- Executable JavaScript behavior suites: **10/10 passed**
- JavaScript syntax checks: **16/16 passed** across source and generated copies
- Source/generated frontend parity: **10/10 files**
- Static-loadout readiness: **READY**; **580,783** mapped events
- Canonical web static payload readiness: **READY**; **730** checked files
- Local hosted browser verifier: **43 passed, 0 failed**
- Final preview browser verifier: **43 passed, 0 failed**
- Immutable production browser verifier: **43 passed, 0 failed**
- Canonical production browser verifier: **43 passed, 0 failed**
- All hosted runs reached **Ready / 100%** with **702,893** total events and
  **580,783** mapped events.

### Exact browser lifecycle proved

The browser verifier switches to Points, creates a one-hop Area Filter around
a real mapped trace endpoint, and then verifies:

1. an Area Filter endpoint opens the full sighting popup and Event Description;
2. a genuine click on the map outside the popup closes both the popup and Event
   Description;
3. Clear produces zero neighborhood interaction layers and sets the high pane
   to `pointer-events: none`; and
4. another ordinary sighting point immediately opens its popup afterward.

The progressive-results verifier was also corrected to treat a result set of
60 or fewer as valid when every result is already rendered and no progressive
window label is needed.

## Frozen artifact and deployment evidence

- Previous production deployment:
  `767d3188-79e4-4c09-8204-813e39c835a8`
- Final frozen Pages folder:
  `cloudflare_bundle_r2_area-lifecycle-v154-final_20260731`
- Frozen inventory: **127 files**, **54,690,337 bytes**
- Tree-hash algorithm: SHA-256 of ordinal-sorted
  `path<TAB>bytes<TAB>file-sha256<LF>` rows
- Frozen tree hash before preview, before production, and after production:
  `abb0134e0ae6ec4bd74a4d159e645bd1096c37a9d3834076788e7c19fe1fdfa1`
- Frozen `app.js` SHA-256:
  `073bae0db0000f0924dcfef16cd762f5e0b39fa47e9c69da02617135e27c8dd3`
- Frozen `index.html` SHA-256:
  `97882ba6f88330681188d33955ac3546000edebdafa25d03eb47bd8519886c34`
- Frozen `styles.css` SHA-256:
  `6c7ed41df0e3f49246714dbe99b9af911fd2489cfff178d06327c36c1944fbe8`
- Frozen `verify_timeline_features.html` SHA-256:
  `d818efd83f5597c10d8f2800f4d51a5cf5e48bb38e6f8bf6d402e6db840e65cd`
- Frozen `data/app_config.json` SHA-256:
  `be039879fbedbdd8882fdb6285bb5361acb397e7b3fb4225915268d230e7c888`
- Preliminary preview, superseded after strengthening the genuine outside-click
  browser check: `885fe0ac-e9b4-4f47-b890-de41b9595979`
- Final preview deployment:
  `fa2b0a71-df5f-48ca-bd61-bd5429e7b4fa`
- Final preview URL: <https://fa2b0a71.ufo-timeline.pages.dev>
- Preview alias: <https://area-lifecycle-v154.ufo-timeline.pages.dev>
- Production deployment:
  `35673440-926d-4dfd-a030-96c947d3615c`
- Immutable production URL: <https://35673440.ufo-timeline.pages.dev>
- Canonical production URL: <https://ufo-timeline.pages.dev>

Production promotion used the identical final preview folder. Cloudflare
reported **0 files uploaded** and **126 already uploaded**. The immutable and
canonical production copies of `app.js`, `styles.css`, and
`data/app_config.json` match the frozen artifact byte-for-byte.

## Data and storage scope

No canonical event data, backend interface, R2 object, or R2 payload changed.
The existing versioned v152 R2 prefix was reused read-only. All **366** upload
manifest entries are identical to the previous release, with stable entry hash
`16a87b965ee80006e347e4abf5b957fc471cf16080a94a205b041fd5e20b5455`.

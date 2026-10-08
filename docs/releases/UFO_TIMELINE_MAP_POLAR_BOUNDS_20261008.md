# Map polar boundaries — 8 October 2026

The previous map-center clamp at ±82° did not constrain the visible map edges.
Dragging could therefore expose space beyond the Web Mercator world, especially
when a tall map was zoomed out. Correcting the center after movement also allowed
the view to overshoot before returning.

The repair uses Leaflet's native latitude bounds at ±85.0511287798066° with full
bounds viscosity, stopping north/south dragging at the world edge. Longitude
remains unbounded so east/west wrapping is preserved. The minimum zoom adapts to
the map height and pixel-world height, rounding upward to the next quarter-step
with a floor of 1. It refreshes after initialization, resizing and movement so
the visible map fits inside the world's vertical extent without a bounce.
Existing case navigation, fitting, legend and collapsible controls are retained.
Implementation reference: [Leaflet map options and projected-world API](https://leafletjs.com/reference.html#map-maxbounds).

Focused regressions passed against actual app functions and the vendored Leaflet
1.9.4 projection/bounds methods, including longitude wrap, tall maps, resize,
move-end recursion and trace refresh. Existing map resizing, famous-case and legend
checks also passed. In the browser, actual held-pointer drags stopped at both
polar edges with zero gap. A 2400 px map required zoom 3.25 (world height
2435.50 px); attempts to zoom out further remained bounded. Longitude �540.25�
was preserved. Leaflet permits up to one pixel of projection-rounding tolerance.
Shrinking the map lowered its zoom floor while retaining its current zoom.
Browser evidence: `releases/map-polar-bounds-20261008/browser_qa.json`.
Production deployment `1d4474fb-6a1b-4862-b826-ed938fdf77da` passed 174
public-object byte/hash checks. Actual held-pointer checks at both poles on the
loaded production page reported zero blank gap, with Analysis ready and no console
errors. Both screenshots and the storage/publication receipt are retained in
`releases/map-polar-bounds-20261008/`. The test views were restored.

Shared source data, scientific methods, evidence, coordinates and inherited R2
objects remain unchanged. The existing 27.4 MiB Pages stage is refreshed in place:
`C:\Users\jarod\.codex\worktrees\case-navigation-release\UFO Timeline map tool\.tmp\workspace-analysis-20261008-pages`.
There are no R2 uploads, full bundle/data copies or additional rollback copies.
Incremental code, tests and documentation are expected to add less than 1 MiB;
no new file is expected to exceed 100 MiB. After successful production validation,
designate the repaired deployment current and retain
`c3bee7a9-56cf-4124-b17d-68f8b8533fa0` as the single known-good rollback.

The two earlier cleanup proposals remain unchanged and require explicit approval:

- `C:\Users\jarod\.codex\worktrees\case-navigation-release\UFO Timeline map tool\.tmp\interface-pages-candidate` — 26,115,918 bytes.
- `C:\Users\jarod\.codex\worktrees\case-navigation-release\UFO Timeline map tool\.tmp\quality-20261007-pages` — 28,176,967 bytes.

Their purposes, exact hashes and retained counterparts are documented in
`docs/WORKSPACE_ANALYSIS_RELEASE_20261008.md`. Protected shared datasets and
provenance remain retained. No cleanup or data deletion is performed here.

# Map sizing and Chronology visibility â€” 8 October 2026

The accepted workspace layout gave the map nearly the entire viewport without
reserving space for Chronology. The older resize implementation could only
enlarge that measured minimum and retained its largest value across layout
changes. Together, these pushed the chart below the first screen and prevented
the drag bar from reducing the oversized map.

The repaired default reserves space for the Chronology chart and responds to the
available viewport. Desktop dragging now resizes the map in both directions.
Keyboard resizing remains available; Home and double-click restore the automatic
fitted default. Version 2 preferences preserve explicit custom heights, while
legacy version 1 heights are ignored so an old oversized setting cannot override
the repaired default.

The original interactive legend, collapsible map controls and their internal
scrolling remain available. Map invalidation and layout refresh follow the
effective height. Narrow-screen behavior retains its responsive layout and the
hidden desktop resize rail. Catalogs, coordinates, traces, scientific methods,
evidence and all inherited R2 objects remain unchanged.

Runtime, focused regression and browser checks passed. At 1366 × 768 the full
chart ends at 755.49 px; at 1280 × 720 it ends at 707.50 px in document coordinates.
Actual pointer drags changed the map in both directions; a 293 px custom height
survived reload, and Home restored automatic fitting. The original legend and
control body remained scrollable to their final rows. Portrait 390 × 844 uses a
112 px chart, ending at 840.85 px, with no horizontal overflow. The desktop rail
is hidden on compact screens. Production deployment `5483977b-fd45-432b-b370-d0fa091a3771` passed 174
public-object byte/hash checks. The loaded 1280 × 720 production page uses a
292 px map and the full plot ends at 707.59 px with document scroll zero.
A trusted 48 px drag grew the map to 340 px; double-click restored 292 px.
Analysis was ready and the console reported no errors. Publication and storage
receipt: `releases/map-chronology-fit-20261008/publication_receipt.json`.
Browser evidence: `releases/map-chronology-fit-20261008/browser_qa.json`.

The single existing Pages stage is refreshed in place. There are no R2 uploads,
full bundle/data copies or additional rollback directories. Small code, tests and
this note target less than 1 MiB net growth; no new file exceeds 100 MiB. After
successful production validation, designate the repaired deployment current and
retain `e70b33ca-a8c6-47b3-a4ae-55927de7e2da` as the single known-good rollback.
Protected shared datasets and source/provenance records remain retained. No
cleanup or data deletion is performed by this repair.

# International native-source locality recovery — 7 October 2026

This lane adds **165 publisher-declared town/nearest-city references** to previously unmapped modern reports: 59 MUFON and 106 NUFORC records across 52 countries or territories. It also corrects **three source-confirmed approximate-day labels** while preserving all three stored calendar dates. There are 166 distinct guarded decisions because two date corrections are combined with point recoveries, and one is date-only.

These points are populated-place references for the submitted report locality. They do **not** establish an exact witness, camera, object, flight-path, or landing location. Confidence is explicitly moderate for the publisher-declared locality reference. No numerical event-position uncertainty radius is inferred from a city name. The 4 km locality-cluster screen is an ambiguity exclusion threshold, not an event accuracy estimate.

## Why this resolves a real missing-data issue

The preceding gazetteer lane withheld 1,529 otherwise exact international locality matches because the narrative did not repeat the city name. That absence does not prove that the retained observation-location field is wrong. This pass checks the field's publisher-defined role and requires a specific fixed local observer setting, then applies full-account exclusions and targeted manual role review.

The [current NUFORC form](https://nuforc.org/reportform/) separates sighting location from personal contact address and distinguishes land, boat and aircraft settings. This proves current field semantics, not that all historical forms were identical or that every submitted location is correct. The official [MUFON July 2023 Journal](https://www.mufon.com/wp-content/uploads/2024/11/JULY_2023_MUFON_Journal_WEB.pdf), printed page 13, visually labels the CMS search field **“Event City (nearest)”** and its result field Location of Event. The relevant source page and embedded screenshots are retained with remote-byte and extracted-page hashes.

Field semantics alone are insufficient. MUFON's [official public table](https://mufon.com/) provides a concrete counterexample: native case 139117 lists Helotes, Texas, while its account summary names Altlengbach, Lower Austria. This case is outside this lane but validates the need for narrative/context conflict exclusions.

## Admission rules and results

All 1,529 candidates were read from the shared pinned full-detail chunks. The 166 decision records were independently rechecked against 125 relevant chunks before writing the initial sidecar. The final Wangenies date-precision amendment rechecked only its one existing pinned record and chunk; all other 165 sidecar lines remain byte-identical. Core source, stored date, raw location, coordinate fields and coordinate-status guards must match exactly. Native report identifiers and raw-field JSON hashes are also checked. Composite records and mismatched publisher location fields fail admission.

Geographic identity reuses the existing pinned GeoNames authority in place. The source city must exactly match a primary/ASCII populated-place name after transparent case, diacritic and punctuation normalization; submitted country and administrative context must agree. All exact primary and alternate populated-place matches in that context must belong to a locality cluster no wider than 4 km. Administrative centroids, fuzzy spelling substitution, population-based disambiguation, and route/departure/target substitutions are excluded.

Accepted accounts establish house, garden, balcony, bedroom/window, yard, terrace or a comparable fixed observer setting. Whole narratives are screened for aircraft, journeys, docks, offshore scenes, trips, remote media review, forced form choices, multiple locations and contradictory named places. Provisional excerpts and the initial 79 source/country strata were inspected; ambiguous marker roles and named-location conflicts received targeted full-context review. This is a bounded admission screen, not proof of exhaustive semantic correctness or the physical truth of a report.

| Disposition | Records |
| --- | ---: |
| Fixed-local-observer declared locality reference | 159 |
| Additional manually resolved observer-role phrasing | 3 |
| Individually checked native pages establishing local land/stargazing scene | 3 |
| No specific fixed observer context | 985 |
| No supported observation context under this pass | 108 |
| Conservative route/site/media/ambiguous-context exclusion | 236 |
| Explicit manual context disagreements | 35 |
| **Total screened** | **1,529** |

One of the 35 held point cases receives a date-only correction. The remaining 1,363 IDs are released for independent recovery lanes after excluding all 166 current decisions. The 35 explicit disagreements remain unresolved constraints until independently addressed.

The three manual positive controls distinguish source roles: an observer out the back of an Iver Heath warehouse, an observer opening a gate in Fermoy while *the lights* are travelling, and household stargazing in Riebeek Kasteel. These use full retained native records; their original public pages are not claimed successfully fetched when the web reader was unavailable.

## Original-page enrichment and date repairs

Seven original NUFORC pages were read online. Five corroborate accepted point contexts: [Kannattota 61642](https://nuforc.org/sighting/?id=61642), [Taumarunui 123853](https://nuforc.org/sighting/?id=123853), [Brodek u Přerova 188154](https://nuforc.org/sighting/?id=188154), [Kemayan 35392](https://nuforc.org/sighting/?id=35392) and [Quatre Bornes 42037](https://nuforc.org/sighting/?id=42037). Brodek explicitly reports a land observer. These checks corroborate declared locality and observer setting; they do not identify an exact witness point.

[Kirkkonummi 36964](https://nuforc.org/sighting/?id=36964) and Kannattota explicitly flag an approximate day. Kannattota also explains that NUFORC assigned an arbitrary date. Both base records were labelled exact_day. Decisions downgrade date_precision to approximate with an additional exact_day guard and preserve sort_date_iso and all original date fields. Kirkkonummi lacks this pass's specific fixed-observer context and remains unmapped.

The retained full native MUFON 141275 account for Wangenies explicitly rejects its entered exact date and recalls only a Tuesday in late autumn 1989 or early winter. That supports an approximate-date label, not a replacement day. Its existing locality decision adds the exact_day guard and approximate precision while preserving the stored **1989-11-14** anchor, point reference, raw fields and French narrative. `focused_date_amendment_receipt.json` retains the exact native statement, full-record and narrative hashes, source locator, and byte-preservation check; a fresh public-page fetch is not claimed.

[Rytro 148376](https://nuforc.org/sighting/?id=148376) names an unnamed kayak dock associated with Piwniczna travel; its dock-to-Rytro relationship is unresolved, so its point remains withheld. The Jessore page returned a verification challenge, and several other original pages were unavailable. Receipts distinguish those outcomes from successful checks. Most accepted records were checked through their pinned retained full native records rather than individually re-fetched online.

Primary municipal/statistical pages independently checked Kitwe's Copperbelt/Zambia identity, Calw's German administrative identity, Iver Heath's Buckinghamshire parish context and the French municipal correspondence between Le Touquet and Le Touquet-Paris-Plage. The Jashore government search result on a Jessore-domain URL supports spelling context at district level only; its direct fetch returned 403, and it is not used as a new coordinate authority.

## Unresolved disagreements and negative controls

`manual_context_disagreements.json` retains all 35 explicit holds with full native text, pinned detail locator, source field and reason. Examples include Polokwane versus Tzaneen; Stafford versus Penridge; Churand versus Mandi Bahauddin; Bergsdalen versus Bergen/Colorado; broader Brasília versus Recanto das Emas; aircraft-window observation; forced Midway form answers; later at-home photo review; remote security-camera viewing; and a potential Jersey-versus-GB St Helier country convention. These remain review leads, not silently corrected locations.

Repeated observations at the same household do not independently establish a flight path or causation. Claimed entities, extraordinary object behavior, dreams, interpretation and observer judgments remain source claims. Existing narrative encoding damage is preserved; this lane does not rewrite accounts, craft types or dates.

Twenty controls pass in `verification_receipt.json`: predecessor exclusions, exact guard coverage, sparse allowed mutations, populated-place ambiguity limits, precise-day downgrade constraints, stale native/publisher fields, composite and existing-coordinate exclusions, real aircraft/forced-form/media/dock/dependency-country negatives, and the manually resolved travelling-light versus stationary-observer positive.

## Provenance, integration and retention

Accepted sidecar: `accepted_international_source_decisions.jsonl` — **166 rows, 700,992 bytes**, SHA256 **c5b9ab001586bfa76320ea67b6bdcd8c1557e5c3249ce72c8c5881f53789a467**. Each decision retains eight core guards, native source ID, canonical input membership, full-detail gzip hash/index, raw-field JSON hash, selected GeoNames feature and line hash, authority archive hash, prior-screen hash and online-receipt hash. Only the three explicitly confirmed date downgrades add a ninth guard.

Canonical base remains `data/canonical_web`, manifest SHA256 `242ff4abc42c70c2b241a3cd16c8b9059bca137d940bd6147c5a65de63b7750b`. This lane writes no canonical dataset, full corpus copy, static bundle, root reader or root quality manifest. The new canonical *analysis* is this guarded sidecar and its retained receipts. The previous validated quality view remains the rollback counterpart until parent integration and publication.

The lane is approximately 5.5 MiB, with **no newly created file larger than 100 MiB**. Net C: growth is approximately that amount. The 418.7 MB GeoNames archive and canonical detail chunks are reused without copying. The remote 1.9 MB journal was read in memory; only its relevant page and images are retained. There is no superseded staging tree or additional deployment. All sparse reviews, decisions, scripts and evidence receipts are retained as protected unique analysis; Python bytecode is a small reproducible cache. See `README.md` and `artifact_inventory.json` for purposes and reconstruction.

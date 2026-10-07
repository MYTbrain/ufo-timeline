# Archival British grid-reference recovery, 7 October 2026

This lane recovers **24 previously unmapped UFOCAT archival grid references** from **83 source candidates**. **59 remain withheld.** The accepted locations represent the grid value recorded in the archive, corroborated against a named British populated place. They are **not measured craft coordinates or independently established observer positions**.

The source codebook, retained at `data/reports/ufocat_codebook_extract/UFOCAT Codebook 2023.txt`, explains the geographical-coordinate representation and location-role flags. The extraction preserves the current source record, raw coordinate fields, location/county labels, native identity, original-value guards and pinned detail locator. An explicit British two-letter square is followed by fractional grid values: the source `LONGITUDE` fraction supplies easting and the `LATITUDE` fraction supplies northing.

The accepted sidecar is `accepted_grid_recovery_decisions.jsonl`, SHA256 **`c07fc0a77aa9c1060199d9a4e8424fcfcbbba538aaa3e280a39cf28b47288d95`**. It is intended for the guarded sparse quality view. The original dates and source fields are preserved; the canonical catalog, packed runtime data and production site have not been altered by this lane.

## Acceptance and abstention

Acceptance requires a single retained source member, explicit `GBR`/`EU` jurisdiction, no special source-coordinate/location-role flag, an explicit valid British grid reference with source resolution no coarser than 1 km, and an exact primary/ascii/alternate populated-place name within 5 km of the nominal source coordinate. A same-name or exact-alias British populated feature more than 10 km away triggers further administrative disambiguation rather than an automatic choice.

The withheld reasons overlap; their counts must not be summed as independent records:

| Review condition | Records flagged |
|---|---:|
| Distant same-name or exact-alias locality requires administrative disambiguation | 25 |
| Composite source membership requires retained-member review | 19 |
| No exact named populated place within 5 km | 23 |
| Reported county needs historical/source interpretation | 5 |
| Grid coarser than 1 km | 2 |

The five deliberately unresolved county questions concern Bray/Oxford, Brightwalton/Oxford, two Heptonstall/Lancashire records and Aston Ingham/Gloucester. Modern administrative names alone cannot settle those historical source labels. Accepted rows also preserve their original county labels and explicitly record that county adjudication was not performed. The archival grid value and locality corroboration support the narrow recovery scope; they do not validate every ancillary administrative field.

## Coordinate interpretation and accuracy

The point preserves the **nominal numerical source easting and northing**. The implementation names these values `easting_sw`/`northing_sw`, reflecting the usual grid-cell lower-corner representation. It does **not** add half a cell to invent a center. Whether the source producer rounded, truncated or used another recording convention has not been independently established. Consequently the source resolution is a limit on interpretation, not a demonstrated bounded uncertainty interval around a witness or craft.

The transformation uses inverse British National Grid projection equations and an **approximate Helmert datum transformation**. It is **not OSTN15**. The source's coarse archival resolution dominates the few-metre transformation differences for this use.

The implementation was checked against **115 official Ordnance Survey Lite control points** from the [retained developer pack](https://www.ordnancesurvey.co.uk/documents/resources/OSTN15-OSGM15-Lite-DevelopersPack.zip). Maximum horizontal difference was **4.676750785 metres**; mean difference was **1.860511003 metres**. This measures agreement on that published control set, not universal accuracy or source-observer accuracy. Four invalid-format/out-of-grid controls passed. `projection_validation.json` and `validation_receipt.json` preserve the test results, input hashes, official pack URL and 1,260,148-byte pack hash.

The implementation's cited authorities are the [Ordnance Survey coordinate-system guide](https://www.ordnancesurvey.co.uk/documents/resources/guide-coordinate-systems-great-britain.pdf), [approximate geodetic transformation documentation](https://docs.os.uk/more-than-maps/a-guide-to-coordinate-systems-in-great-britain/from-one-coordinate-system-to-another-geodetic-transformations/approximate-wgs84-to-osgb36-odn-transformation) and [National Grid guide](https://www.ordnancesurvey.co.uk/documents/resources/guide-to-nationalgrid.pdf). Nearby named-place references use the already shared GeoNames authority; they corroborate an archival locality rather than substitute a town center for the source grid value.

The next research queue is the 59-record `unresolved_grid_worklist.json`. Historical county documentation, source-account context and retained merge members can resolve particular cases; no placeholder coordinate, global homonym or broad county center was promoted merely to increase mapped coverage.

## Retention and storage

This lane's accepted sidecar and evidence are the new canonical **grid-recovery analysis**, with the untouched pinned source catalog as rollback. Current validated production and its existing known-good rollback remain under the parent task's release policy. Retain the source-candidate census, named-place references, unresolved worklist, builder, projection module, test receipts and official developer pack: they jointly preserve the decisions and their reproducible validation.

The lane occupies approximately **1.6 MiB**, including the 1.2 MiB official validation pack; no new file exceeds 100 MiB and no corpus, runtime bundle or release tree was copied. Net disk growth attributable to this lane is approximately 1.6 MiB. No superseded release/staging directory or dataset deletion is proposed. See `README.md` and `artifact_inventory.json` for rebuild and inventory details.

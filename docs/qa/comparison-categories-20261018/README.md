# Category-linked A/B comparison preview

The previous interface held A/B populations correctly but showed their comparison only in a separate dialog. Category charts continued to show live shared filters, making a captured B window look like the comparison.

This candidate makes Current reports / Compare A/B explicit, enters comparison after the second group is captured, and follows the Analysis navigation with inline paired charts. The same captured report IDs are used for all report-based dimensions. Original category charts remain available in Current reports mode; no map filters are changed by switching modes.

Captures cover 18 descriptive fields: source, craft, being, abduction, year, calendar month, weekday, time of day, country, world region, local region, report type, date precision, location precision, craft confidence, color, duration, witness count. Optional projections are unavailable when absent at capture; unknowns are distinct from zero. Colors retain their reported role. Exact-date weekday uses the recorded date, with no timezone inference.

Independent crop/animal catalogs, facility/spatial relationships, Moon/planet/nuclear context, and evidence-gate relationships do not yet have captured A/B populations. Their comparison mode displays a specific explanation and an action to view current reports. It never substitutes live B charts or invented counts.

Set/Replace uses the current applied dates and filters. Opening a frozen group in Analysis does not silently override a later toolbar capture. Both live-filter and active-selection signatures are checked before committing a capture. Existing exact-ID drilldown capture APIs retain their previous behavior.

Focused model, worker, view, category navigation, app integration, search, collection delivery and loading-cover checks pass. Ten release checks pass. Hosted browser verification follows in this directory.

Storage: reuse the single .tmp/workspace-analysis-20261008-pages candidate; all 105 immutable R2 objects stay unchanged. No corpus, database or full release copy is created. Production 16443086-c630-41d8-a793-92a0243a76f6 and rollback b4e04dc8-4605-486e-bdbc-174acd3ca37e remain retained. Net C: growth is below2MiB (small code/tests/receipts/screenshots); D: growth0. No new file exceeds100MiB and no superseded large stage exists. Cleanup proposal: none for this batch. This remains preview-only.

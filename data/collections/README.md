# Collection motif evidence sidecar

This is the current validated **preview** derivative. It does not change the
canonical UFO corpus, production release, encounter index or original dossier.
The two runtime files are `manifest.json` and `evidence.json.gz` (about 0.5 MiB
combined). No new file exceeds 100 MiB. There is one generated sidecar, not a
sequence of backups; the production site and its retained rollback are unchanged.

The manifest pins the original reviewed report register, dossier, coverage/source
ledger, current encounter evidence, additional reviewed contexts, country-name
reference and every canonical detail chunk used for identity joins. The public
artifact contains no local user paths. All original research files are retained
unchanged. New report rows are validated by event ID, source, native source ID,
chunk and detail index. Dossier associations remain separate ID joins and are
not authenticated incident merges.

Rebuild from the implementation checkout with the preserved original evidence
folder in `--dossier-dir`:

```text
python scripts/build_collection_evidence.py --dossier-dir "<original Soil and plant encounters directory>" --source-review docs/qa/collection-analysis-20261018/source-review.json --additions docs/qa/collection-analysis-20261018/collection_recall_audit_additions.json --additions docs/qa/collection-analysis-20261018/collection_recall_data_review_additions.json
```

The builder also reuses the browser's pinned quality and date guard modules for
current metadata. Eight partial dates retain month/year calendar bounds, never
fabricated exact days; display labels do not assert coordinates. Eleven targeted
facet reviews guard against negated removal, background plants and other-object
inspection being misclassified. All these inputs are pinned.

This reads shared canonical chunks one at a time. It copies no corpus and replaces
only this bounded derivative. Its output is deterministic (including gzip mtime).
Material/action facets are conservative labels from reviewer-written target and
act summaries; keyword search candidates never become positives automatically.
Unknown being/geography/date facets stay explicit. Directly described acts,
ambiguous claims, adjacent contexts and excluded controls are separate cohorts.
Counts are reports and representations, never authenticated independent incidents.
Merged-member excerpts that differ from the canonical primary narrative are held
from matrices by default; an explicit sensitivity option can include their primary
row facets while retaining the narrative-identity warning.

The supplemental recall audit scanned all 702,893 pinned corpus rows. Its broad
candidate queue is not exhaustively adjudicated; retained additions and remaining
coverage limits are documented in `docs/qa/collection-analysis-20261018/`.

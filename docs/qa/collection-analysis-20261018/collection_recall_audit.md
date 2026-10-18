# Complementary collection-report recall audit

This pass supplements the supplied soil/plant dossier. It does not overwrite its
6,690 reviewed dispositions or reinterpret its 729 retained report rows.

| Coverage | Result |
| --- | ---: |
| Current pinned corpus records screened | 702,893 |
| Records containing narrative text | 647,216 |
| Records without narrative text | 55,677 |
| New lexical candidates outside prior reviewed IDs | 9,618 |
| Previously reviewed matches preserved | 764 |
| Bounded contexts manually reviewed in this lane | 89 |
| Retained additions read in full canonical primary text | 18 |
| Matched-context exclusions | 71 |
| Remaining candidates unreviewed in this lane | 9,529 |
| New direct soil/plant collection rows established | 0 |

The new search adds geological/vegetative synonyms (for example, boulders,
pebbles, clay, saplings, berries and foliage), extraction mechanics, additional
Romance-language verbs, and actor-free mechanical contexts. All 282 full-detail
chunk hashes and 71 summary hashes matched the dossier pins. No corpus files were
copied. Exact patterns, source counts and timing are in the summary JSON.

The 18 retained rows comprise three direct-report rows (one mineral source
variant and two derivative water accounts), seven adjacent rows, and eight
ambiguous rows across 12 explicit source families. These are not 18 independent
incidents. Two botanical additions describe berry consumption and grasping a
sapling; neither is recoded as witnessed collection. Other additions preserve
reported ground depressions, later missing material and extraction speculation
as adjacent or uncertain. The default direct soil/plant view is not inflated.

Five additional priority contexts were delegated to the data lane and are
recorded separately in `collection_recall_data_review_additions.json`; their
reviews are not included in the 89 above. In particular, original-source
retraction evidence must take priority over a catalogue's apparent water-sampling
claim.

`excluded_context` means that the displayed discovery window concerned an
ordinary human action, setting, data extraction, idiom or different target. It is
not a judgment about every sentence of the complete report. The remaining queue
is explicitly unreviewed. Missing narratives, untranslated terms, truncated
catalogue descriptions and unrecovered originals remain coverage limits.

## Artifacts and storage lifecycle

- `collection_recall_audit_candidates.json`: current canonical recall queue;
  1,868 bounded priority contexts plus 7,750 compact exact locators.
- `collection_recall_audit_reviewed_dispositions.json`: all 89 manual decisions.
- `collection_recall_audit_additions.json`: the 18 retained additions for analysis.
- `collection_recall_audit_summary.json`: coverage, limitations and input pins.
- `collection_recall_audit_metadata.json`: sparse original-row identity metadata.
- `collection_recall_audit_priority_review.json` and
  `collection_recall_audit_material_review.json`: small reproducible review queues
  retained to explain review selection; no full corpus or archive.

The original supplied dossier remains the retained prior research checkpoint.
These audit artifacts add approximately 8 MiB, with no new file over 100 MiB and
no new deployment or corpus bundle. One generated queue was compacted in place;
there is no superseded staging tree. All artifacts have a provenance/rebuild role
and can remain through review; no dataset deletion or cleanup is proposed.

Rebuild discovery with `scripts/audit_collection_recall.py --dossier <original
dossier directory> --output <this directory>`. Manual dispositions and additions
are research judgments and must not be regenerated from keyword scores.

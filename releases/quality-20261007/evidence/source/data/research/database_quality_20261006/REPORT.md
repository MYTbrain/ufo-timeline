# Database quality improvement batch — 6–7 October 2026

**Completed a validated local quality view with 1,632 source-supported changes,
113,539 original-account relationships and 726 date-role review annotations.**
The view reads the existing shared catalog and applies sparse guarded decisions.
It preserves all 702,893 source representations, original values, raw source
fields, narratives, dates and retained source members. The live website and its
base dataset have not been changed by this research batch.

## What changed in the effective dataset

| Supported change | Records | Scope |
|---|---:|---|
| City → state precision label |1,404|Keep existing administrative reference coordinates; stop presenting them as city precision.|
| Corrected existing reference coordinates |7|Five city references, one original-source coordinate restoration and one named observer-site reference.|
| Recovered previously unmapped reference markers |6|Four Istanbul accounts, St Austell and the explicitly named Mojave/KMHV facility.|
| Quarantined incorrect mapped markers |3|Keep the source record, remove the incorrect Earth marker until the observer location is supported.|
| Location text repaired without geocoding |212|Strict reversible encoding repair only; no guessed places or points.|
| **Total accepted modified records** |**1,632**|Exact source/date/place/coordinate/precision guards checked against the pinned base.|

The four recovered Istanbul entries also receive reversible city-text repairs.
There are **216 proven encoding repairs in total**: those four plus the 212
text-only records. St Austell and the facility reference also receive supported
display normalization; they are not counted as encoding repairs.

Mapped representations change from **580,783 to 580,786**: six reference recoveries
and three quarantines. **122,107 remain unmapped.** All reference coordinates have
explicit roles and limits. They do not establish object positions, flight paths,
report authenticity or physical-event identity.

The precision batch is conservative: exact administrative-reference coordinates,
matching full source country/admin fields, an exact same-admin locality cluster
more than 75 km away, and no route/compound primary place. Only 1,403 records pass
this systemic screen; Maury Island supplies the separately reviewed 1,404th.
The broader centroid/country screens remain research leads, not accepted fixes.

Examples include correcting the Red Bluff reference with the
[Census city internal point](https://tigerweb.geo.census.gov/tigerwebmain/Files/acs25/tigerweb_acs25_incplace_ca.html),
restoring the literal Majestic decimal/DMS coordinates for Eagle Lake with
[BLM locality corroboration](https://www.blm.gov/visit/eagle-lake-recreation-area),
and using the independently published Punta Gorda site reference for the account
whose source explicitly places the observer inside the lighthouse.
[NOAA-hosted BLM report](https://www.fisheries.noaa.gov/s3/2023-12/BLMPuntaGorda-2023IHA-Final-Report-OPR1.pdf).
The exact observer or object positions are not inferred from a town/facility
reference. Fort Macleod, Westall and Deadhorse are quarantined because their served
markers contradict source geography while a supported observer point is absent.

## Original accounts and duplicate quality

The crosswalk connects **113,539 explicit UPDB original-account references** to
their current MUFON or NUFORC primary records. It exposes the source-native key,
both pinned detail locators, retained member guards, narrative evidence,
date/location/craft conflicts and the original representations.

**47,788 pairs** qualify for an optional conservative account projection: explicit
native identity, substantial matching narrative, the same exact stored day,
identical valid mapped coordinates and craft classification, and one consistent
retained source member at each endpoint. If both representations are already in
a selection, the reader can keep the original primary representation and expose
the copied representation as suppressed in that view. A copied-only selection
keeps its report. All composite or conflicting records survive. No base events
are merged or deleted; these are account identities, not a count of verified
independent physical incidents.

| Exclusive review partition | Relationships |
|---|---:|
| Agreeing republication / optional projection candidate |47,788|
| Composite membership review |4,189|
| Date review |3,220|
| Content review |22,190|
| Mapping review |23,182|
| Craft-label review |12,970|
| **Total** |**113,539**|

Independent review flags overlap. The exclusive partitions above do not mean only
3,220 date disagreements or only 23,182 mapping issues exist. Coordinate or other
accepted quality edits invalidate affected base projection candidates until
current fields are rechecked; none of this batch's changes intersects the 47,788
eligible pairs. Projection still rechecks the actual pinned full detail records.
This helps prevent copied accounts from becoming independent analytical inputs,
while preserving witness/publication distinctions and every original record.

## Dates: submission is not occurrence

The new source-role census covers **74,257 matched MUFON primary endpoints**, not
the full 119,350-record MUFON population. It reads the original `Date/Time of
Event` and `Date Submitted` fields preserved in pinned detail records.

- 71,057 have a valid explicit occurrence-day prefix, all agreeing with their
  current primary stored day.
- 3,200 lack a valid explicit occurrence day: 2,475 invalid calendar prefixes
  and 725 time-only or non-date fields.
- In 726 linked UPDB copies, the stored day equals the original submission day
  while the original occurrence field lacks a valid explicit event day.

The **726 are review annotations**, not 726 proven wrong dates. Their copied day
is retained, the source roles are visible, and no occurrence date is invented.
For example, MUFON 100285 preserves `12:00AM` as its occurrence field and
`2019-05-15` as its submission day; its linked UPDB representation stores May 15.
The source evidence does not establish an observation day. Composite membership
and calendar uncertainty remain explicit. This batch makes **zero date edits**.

## Wider native-location research

The SQL lane checks **all 44,524 currently unmapped UPDB records / 31,400 requested
native location IDs** against the preserved SQL, streamed in place. It finds
9,592 requested IDs; 21,808 are absent from that archive. This is archive-specific
absence, not proof a historical place or observation is missing everywhere.

The initial record classes reconcile exactly: 23,894 have no location row in this
archive, 16,751 point to non-populated-place features, 3,870 lack source coordinates,
and nine have populated-place text disagreements. All nine receive source-role
review: four Istanbul rows are recovered through a strict reversible text repair
and exact native-ID city join; the five route/multiple-site cases remain unresolved.
Municipal/populated-place references and the
[FAA MHV record](https://www.gcr1.com/5010ReportRouter/MHV.pdf) support the six
accepted locality/facility markers. Exact photographer, airborne or object
positions remain unknown.

## Using and reproducing the view

The canonical quality artifact is `quality_view_manifest.json` plus its pinned
accepted sidecars, account crosswalk, annotations, reader and shared base.
`sparse_quality_view.py` exposes `QualityView.iter_summaries()`, `get_detail(id)`,
`get_decisions(id)` and optional `project_selected_event_ids(ids)`. All normal
reads retain every source representation. The reader attaches original values,
decision IDs, evidence-artifact references, account relationships and date notes.

From the project directory:

```powershell
py -3 data/research/database_quality_20261006/sparse_quality_view.py
py -3 data/research/database_quality_20261006/sparse_quality_view.py --event-id 2033413551753606
```

The first returns the validated effective census. The second returns the corrected
Eagle Lake full record alongside its original source fields and decision trail.
For Python consumers:

```python
from pathlib import Path
import sparse_quality_view as quality
view = quality.QualityView(Path(quality.__file__).with_name('quality_view_manifest.json'))
for report in view.iter_summaries():
    # Consume effective coordinates, precision and quality annotations.
    pass
```

Use the reader module's directory on the import path, or load it by its absolute
path. The manifest includes the actual shared-base path and can accept an explicit
`base_dir` override if moved, provided all pins still match. Constructor validation
checks all 71 compact summary shards and exhausts the bounded account stream.
It retains compact relationship metadata rather than expanding a complete corpus.
Detail reads verify actual compressed chunk hashes and exact event locators.

Rebuild the lane decisions with the existing lane scripts, then run
`assemble_quality_view.py`. Lane reports record archive/reference hashes and
authority facts. No full canonical/static-bundle copy or materialization is needed.
Unknown candidates, stale guards, inconsistent points, wrong base pins,
conflicting decisions and incomplete date annotations fail closed. All guards
refer to the original base values, even when compatible edits share an event.

**Base packed point, trace and analysis binaries are deliberately excluded from
this view.** A production consumer must derive its coordinate/trace/analysis
outputs from the effective rows, or apply the same decisions consistently to all
of those projections. Loading corrected summaries alongside unchanged packed
coordinates would be an incomplete publication. This batch is ready for local
research consumption; there is no production publication receipt for it.

## Verification and remaining research

The complete source integration checked every accepted edit and date annotation
against actual pinned full detail records, including unchanged dates, source
identity, raw fields and retained membership. Thirteen integration controls
passed. After tightening annotation pins/locators and batching selected projection
reads by chunk, fourteen final focused controls passed. Account and location lanes
also passed 13 and eight focused tests respectively. The recovery lane validates
all 218 statuses, unique IDs, source locators, date preservation and every text
roundtrip. Receipts are `quality_view_validation.json` and
`quality_view_test_receipt.json`; source evidence stays in each lane.

Highest-value remaining work is concrete and bounded:

1. Integrate the account-aware view into map/results/analysis consumers before
   adding more copied-account coordinates. Original-only/copy-only selections
   and conflicting dates must retain their source roles.
2. Review the **2,460 unaccepted location candidates** individually, prioritizing
   wrong country/admin geography and source coordinates. Routes, historical
   jurisdictions, observer/publisher/departure roles and legacy coordinate
   conventions need explicit evidence, not another generic city lookup.
3. Resolve the five SQL route/multiple-site abstentions and six retained narrative
   leads in `remaining_source_review_candidates.json`; pursue original reports
   for IDs absent from this preserved SQL.
4. Extend occurrence/submission-role checks to the remaining 45,093 MUFON primary
   records and review copied dates with uncertain original fields. Keep missing
   days and partial dates honest.
5. Review previously composite events and narrative-only duplicate leads using
   their retained source members. Similar city/day/craft labels or account text
   alone cannot justify merging distinct witnesses or physical events.

## Storage lifecycle and retained releases

Retain this directory as unique quality decisions and research evidence. Its
purpose, source pins, rebuild method and retention are documented above and in
`README.md` and lane reports. The shared pinned `data/canonical_web` is the base
and rollback for the quality view; disabling the sidecars restores the base read.
Raw inputs, archives, canonical datasets, coordinate history, unique analyses and
unpushed Git work are unchanged.

- New canonical quality artifact: this manifest, reader and pinned sparse inputs.
- Retained production current: `78cc3660-5750-4685-a095-fee6dce37fbf`, source
  `eb5269c6c2c237a66982253639dada29c1214714`.
- Retained production rollback: `f88416b1-1e96-45fa-8b2a-a1edbfc5fdae`, source
  `8a04e13`; no additional retained release or deployment tree was created.
- Newly created files larger than 100 MiB: **none**.
- Approximate net retained artifact growth: **32.5 MB / 31 MiB**. Compressed account
  evidence is ~21 MB; the complete inventory includes scripts, receipts, reports,
  small Python bytecode caches and the other sparse evidence.
- C: free at the final measurement: ~132.27 GiB, above the 100 GiB reserve. C:'s
  whole-volume free-space decrease since the recorded batch start was ~54.3 MB;
  only ~32.5 MB is attributable to these artifacts. Remaining concurrent/system
  growth is not attributed to this task. No large net-positive operation occurred.
- Superseded staging/backup artifacts: **none created**. No full corpus, SQL,
  static bundle or release copy was made. No files were placed on D: or E:.
- Cleanup proposal: none for this protected unique research batch. No redundant
  generated large artifacts require removal, and no deletion was performed.

`artifact_inventory.json` records each retained artifact's size/hash (excluding
itself), the final volume measurement and retention decision. The directory began
on October 6 local time and completed October 7 UTC; its original name is retained.

## Evidence packages

- [Guarded location decisions](location_corrections/REPORT.md)
- [Original-account identity and conflict review](account_links/ACCOUNT_LINK_QUALITY.md)
- [Native SQL lookup and unmapped recovery](unmapped_recovery/UNMAPPED_RECOVERY_REPORT.md)
- [Previous whole-catalog audit](../database_audit_20261006/REPORT.md)

The scientific limits belong with these results: an account reference is not a
physical-incident identity, a town/facility point is not an object position, and a
copied stored day is not proof of occurrence time. Every supported improvement
and every remaining disagreement stays traceable to its source.

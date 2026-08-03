# Animal-Mutilation Phase 1.1 Cross-Domain Seed

This directory defines the non-destructive export used to prepare the
**Animal Mutilation Reports** layer for UFO Timeline. Cattle are one supported animal
group, not an eligibility boundary. The pipeline also supports other
livestock, companion animals, wildlife, birds, fish, reptiles, amphibians,
invertebrates, mixed-species incidents, and source-described unknown animals. It does not
change the UFO Timeline frontend, canonical corpora, deployment bundles, or
production behavior.

## Locked inputs

The command fails closed unless these research packages match their pinned
SHA-256 identities:

- `cattle_mutilation_mapping_starter_pack.zip` -
  `578F9A6E2E6B1EFDC4634EF5421F3079A5E169ADE89EF65F9CA181BC506AE611`
- `Crop_Circle_UFO_Timeline_Export_v1.zip` -
  `7F552F66A197B96C838475B5CAEAB7C78C1AEE5544C81D658A10335687CB2DF6`
- `COMBINED.pdf` -
  `F51718F1EEB1C3F06F3A154D02EB7AB24DCEFEBB201E3ACE04C6E8F79DCC65E7`

The full run expects 971,115 UFO source records, 944,578 deduplicated UFO
events, 7,745 crop events, 8,391 crop assertions, 2,345 assertion-linked
source URLs, 26 additional record-level source URLs, 309 catalog pages, and
5,978 catalog formation slots. The packaged image-link narratives add 2,858
nonempty `alt_text` values and 78 nonempty `title_text` values; both fields are
audited independently.

## Reproducible stages

Commands are run from the repository root. Acquisition is offline by default;
network access and Wayback fallback are separately explicit. Raw source bytes
remain in the private content-addressed cache and are never copied into public
outputs or Git.

```powershell
python scripts/cattle_mutilation_seed.py acquire \
  --network \
  --archive-fallback \
  --workers 4 \
  --private-cache-dir "C:\Users\jarod\Documents\Cattle Mutilation Map\private_cache\crop_sources_v1"

python scripts/cattle_mutilation_seed.py extract \
  --output-dir "C:\Users\jarod\Documents\Cattle Mutilation Map\outputs\phase1_1\global_animal_seed_v1_1" \
  --private-cache-dir "C:\Users\jarod\Documents\Cattle Mutilation Map\private_cache\crop_sources_v1"

python scripts/cattle_mutilation_seed.py validate \
  --output-dir "C:\Users\jarod\Documents\Cattle Mutilation Map\outputs\phase1_1\global_animal_seed_v1_1"
```

`--workers` bounds concurrent source targets (default `1`). Request starts
remain globally rate-limited by `--rate-limit-seconds`, including when more
than one worker is selected; a small value such as `4` is the intended bounded
parallel setting.

Use `extract --resume` after interruption. The scanner resumes from a verified
source-file size and byte offset. Successful page-cache objects are always
hash-verified before reuse. `--allow-partial --limit N` is fixture/test mode
only and is visibly recorded in the run manifest.

Expected resources for the full run are approximately 12 GB of sequential
input reads plus output/audit space. Candidate records are retained in memory;
the two multi-gigabyte UFO corpora are streamed.

## Inclusive classification and evidence

Narrative values are analyzed separately from source taxonomy fields. A
`mutilation_case` requires at least one animal linked within the same evidence
unit to an explicit mutilation phrase or distinctive injury predicate. Broad
page-level co-occurrence is retained as context and cannot establish a case.
All non-human animal taxa are eligible; species is never an exclusion rule.
An ordinary animal death, killing, or carcass report without mutilation or a
distinctive injury predicate is not classified as a mutilation case.
Hatch and other attribute glosses can create a review lead, but never a direct
case.

The controlled taxonomy includes bovines, equines, sheep, goats, pigs,
camelids, cervids, dogs and wild canids, cats and wild felids, rabbits/hares,
rodents, poultry and wild birds, fish, marine mammals, reptiles, amphibians,
invertebrates, other named animals, and unknown animals. Mixed incidents contain multiple
animal assertions; they never use a synthetic `mixed` species.

Each animal assertion records the reported term, normalized common name,
animal group, domestic/wild context, incident role, identification basis,
confidence, source IDs, and a short evidence excerpt. Roles distinguish
reported or possible victims from witness companions, predators/scavengers,
nearby unaffected animals, and other context. Ambiguous terms such as human
`kids`, technical `RAM`, animal place names, and ordinary witness pets are
regression controls rather than species aliases.

Evidence excerpts are bounded source windows anchored on the reported animal
and the closest harm predicate, so long narratives do not publish an unrelated
prefix. A source that explicitly describes people staging or planting a
mutilated animal is marked `contested`; this records deliberate placement and
does not infer who injured the animal.

The deterministic score now records:

- sentence-local explicit animal mutilation: +0.78;
- sentence-local distinctive animal injury: +0.62;
- page-level animal/mutilation context without victim binding: +0.24;
- mutilation-related source type: +0.22;
- structured animal/injury codes: +0.12, review-only;
- source-local incident verb: +0.12;
- explicit negative/non-classic statement: -0.30;
- research/publication context without a supported incident: -0.18.

Candidate score, incident likelihood, record type, source tier, species
identification confidence, and relationship compatibility are distinct
fields. None is a probability of an anomalous cause. Low-confidence,
negative, aggregate, research, nonclassic-death, and structured-code records
remain in audit or context outputs rather than disappearing.

## Correlation contract

`cross_domain_relationships.jsonl` preserves two evidence lanes for the
`animal_mutilation` domain:

- `explicit_source` - the source itself reports the relationship;
- `deterministic_match` - date/place compatibility created a review candidate.

Matching order is source-explicit same scene, native/citation lineage,
exact-day plus compatible locality, overlapping interval plus county/region,
then regional/topical review context. Approximate dates remain intervals,
country/admin conflicts fail closed, and coordinate uncertainty is carried
through the match. Month/year start-only dates expand to their calendar end;
approximate, range, season, and unknown start-only dates retain an open end
instead of becoming exact-day claims. A locality centroid is never a site.

All crop events and crop-source candidates stay `context_only` with
`trace_eligible: false`. Every relationship fixes `causality` to
`not_asserted`; computed relationships cannot be marked analyst-confirmed.

Animal records are also not UFO craft traces. The standalone Timeline adapter
honors `trace_eligible: false` and keeps the layer separate from sequential UFO
trace construction.

## Outputs

The output directory contains:

- `candidate_records.jsonl`
- `canonical_incidents.jsonl`
- `related_events.jsonl`
- `extraction_audit.csv`
- `seed_report.md`
- `duplicate_pairs.csv`
- `rejected_or_noise_candidates.jsonl`
- `cross_domain_relationships.jsonl`
- `crop_circle_source_candidates.jsonl`
- `crop_circle_source_access_audit.csv`
- `run_manifest.json`

The manifest records input identities, corpus counts, coverage gaps, and
SHA-256 identities for every other output. Run extraction twice into different
directories and compare those listed hashes for byte-level determinism.

## Privacy and rights

All named ranch, farm, and homestead properties are redacted and have public
coordinates suppressed regardless of date or recorded precision. Unnamed
private locations are suppressed when modern or precise. Public summaries and
animal evidence excerpts redact common email, phone, exact-coordinate,
street-address, and embedded Web-locator patterns. Output prose is limited to
short factual evidence excerpts and durable structured source locators/hashes.
Missing, blocked, rights-limited, or narrative-free source pages are
`coverage_gap`, never evidence that no relationship exists. Images and
third-party raw pages are not redistributed.

The seed `candidate_records.jsonl` and `canonical_incidents.jsonl` are
restricted review artifacts: their location objects retain internal custody
coordinates alongside the generalized public projection. They must not be
published, served by the frontend, or copied into a public release. Only the
public-safe `animal_mutilations.geojson` bridge artifact is designed for the
public Timeline layer; the adapter omits every internal-coordinate field,
uses structured generalized location labels, and rescans all emitted strings
for private locators.

## Import readiness

This export remains a reports-and-review corpus. It must not be appended
directly to the UFO canonical stream or treated as evidence of a UFO cause.
The public-safe layer may include every eligible incident immediately when it
is clearly labelled `reported_unreviewed`; analyst verification is not a
publication prerequisite. Isolated or ambiguous classifications remain in the
review queue as `unresolved` work and are not release blockers. Cross-domain
relationships are not emitted by this adapter.

The standalone bridge creates a separate Timeline overlay asset
family without writing canonical UFO data, static bundles, frontend files, or
relationship artifacts:

```powershell
python scripts/build_animal_mutilation_timeline_layer.py `
  --seed-output-dir "C:\Users\jarod\Documents\Cattle Mutilation Map\outputs\phase1_1\global_animal_seed_v1_1" `
  --output-dir "C:\Users\jarod\Documents\Cattle Mutilation Map\outputs\timeline_layer_v1_1"
```

With no `--review-decisions` ledger, the adapter publishes every eligible case
as `reported_unreviewed` and also places it in the non-blocking review queue.
The bridge writes four deterministic artifacts:
`timeline_review_queue.jsonl`, `animal_mutilations.geojson`,
`animal_mutilation_coordinate_normalization_audit.jsonl`, and
`animal_mutilations_import_manifest.json`. The audit preserves each original
public geometry, output geometry, source scope, transformation rule, semantic
geography result, canonical incident hash, and stable `ami_*` identity. The
frozen seed incidents are never rewritten. The adapter applies the documented
UFOCAT west-positive/east-negative convention only to the public projection;
Majestic coordinates already use standard signed longitude and remain
unchanged. Unknown provenance or a post-transform geography mismatch fails
closed by retaining the report with null public geometry, never by guessing.
The emitted GeoJSON is already normalized, so downstream products must not
apply another sign transformation. An optional review ledger remains available
for later accepted, rejected, or unresolved adjudication. Queue rows and audit
rows are validated against `timeline_review_queue.schema.json` and
`timeline_coordinate_normalization_audit.schema.json`, respectively.

The original `Animal_Mutilation_Reports_UFO_Timeline_Handoff_v1.zip`
(`CAECFB0B2F94F7F361AB0782D4097FEE31711073EDE3B8A1B2AD071AE28F1048`)
is retained unchanged as a historical, rejected map release because 479 public
longitudes used the wrong signed convention. The v1.1 handoff supersedes it for
mapping by rebuilding only the deterministic Timeline projection from the same
frozen 1,177 canonical reports; extraction, crawling, classification, and
deduplication are not rerun.

Extraction `cmi_*` identifiers remain mutable lineage because clustering can
change. The unreviewed release derives one deterministic opaque
`ami_<24 lowercase hex>` identity from each current `cmi_*` lineage and also
pins that lineage's canonical JSON hash. A later accepted review decision may
assign a persistent reviewed identity without auto-carrying a scientific
decision across extraction drift. Every emitted feature is species-neutral,
`context_only`,
`trace_eligible: false`, and `causality: not_asserted`.

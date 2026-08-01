# Cattle-Mutilation Phase 1 Cross-Domain Seed

This directory defines the non-destructive export used to seed a future,
separate cattle-mutilation map. It does not change the UFO Timeline frontend,
canonical corpora, deployment bundles, or production behavior.

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
  --output-dir "C:\Users\jarod\Documents\Cattle Mutilation Map\outputs\phase1\global_seed_v1" \
  --private-cache-dir "C:\Users\jarod\Documents\Cattle Mutilation Map\private_cache\crop_sources_v1"

python scripts/cattle_mutilation_seed.py validate \
  --output-dir "C:\Users\jarod\Documents\Cattle Mutilation Map\outputs\phase1\global_seed_v1"
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

## Classification and evidence

Narrative values are analyzed separately from source taxonomy fields. Hatch
and other attribute glosses can create a review lead, but never a direct case.
The deterministic score records each contributing signal:

- explicit animal-mutilation phrase: +0.65;
- animal near a mutilation term: +0.55;
- animal and mutilation terms elsewhere in the same narrative: +0.38;
- animal near distinctive scene/anatomical findings: +0.34;
- mutilation-related source type: +0.32;
- structured animal/injury codes: +0.18, review-only;
- incident verb in a supported animal context: +0.12;
- explicit negative/non-classic statement: -0.30;
- research/publication context without an incident: -0.18.

Candidate score, incident likelihood, record type, source tier, and
relationship compatibility are distinct fields. None is a probability of an
anomalous cause. Low-confidence, negative, aggregate, research, and structured
code records remain in audit or context outputs rather than disappearing.

## Correlation contract

`cross_domain_relationships.jsonl` preserves two evidence lanes:

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

Potentially modern private ranch/address locations retain internal source
coordinates only; public coordinates are suppressed and the public precision
is generalized. Output prose is limited to short factual evidence excerpts and
durable source locators/hashes. Missing, blocked, rights-limited, or
narrative-free source pages are `coverage_gap`, never evidence that no
relationship exists. Images and third-party raw pages are not redistributed.

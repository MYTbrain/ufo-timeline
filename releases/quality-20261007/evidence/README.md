# Quality release 2026-10-07: review evidence

This compact Git handoff preserves the reviewed sparse decisions and their source
citations for the quality release: 3,730 distinct changed records, including eleven
source-supported date-precision downgrades. The effective catalog retains all
702,893 source representations; 582,877 are mapped and 120,016 remain unmapped.
The retained original research evidence and shared catalog remain the authoritative
local research inputs. This package changes none of those inputs.

`package_manifest.json` records every copied source-relative path, its original
byte count/hash and its stored byte count/hash. Large text sidecars are stored as
deterministic gzip streams; decompressing `gzip-original-bytes` reconstructs the
exact pinned bytes, rather than a reformatted JSON approximation. Files already
ending in `.gz` retain their original gzip bytes. Reports, both guarded readers,
source citation/fact receipts and current map/analysis build receipts are included.

`source_citation_ledger.json` indexes source links and the files citing them. The
original decisions and receipts define each link's evidence scope and retrieval
method. Some source pages were individually retrieved; others are native report
links attached to a reviewed, pinned local source record. A citation is not a claim
that every page was fetched live. Named-locality and archive-grid recoveries are
reference locations with stated uncertainty; they do not locate the craft or prove
a flight path. Conflicts, withheld cases and approximate-date anchors remain visible.

`shared_dependencies.json.gz` records omitted shared input pins and referenced
source artifacts. The package deliberately omits the full detail corpus, account
crosswalk bulk files, authority ZIPs, PDFs/images, runtime binaries and historical
workflow scripts. Original manifests retain exact bytes, including their absolute
local roots. Therefore this is a reviewable provenance handoff, **not a standalone
relocated QualityView or database**. Full reproduction requires the shared inputs
at the recorded paths (or an explicitly repinned relocated view), followed by the
current release builders in `scripts/build_quality_map_release.py` and
`scripts/build_quality_analysis_release.py`. The readers must not be run against
unpacked package paths by silently editing a preserved manifest.

The frozen research manifest's `production_published=false` and warning about
original packed assets describe the sparse research view at acceptance time. The
included current map/analysis receipts join that accepted view to the regenerated
runtime artifacts and their hashes. Deployment success and the retained production
rollback are recorded by the deployment owner; this package does not assert that
publication has completed. The previous quality manifest is retained solely as an
input/acceptance lineage record, not as another full deployment copy.

## Verify and rebuild

Run `py -3 verify_package.py` from this directory. This read-only check verifies
stored/decoded hashes, all twelve sidecar row counts, original guard coverage,
decision uniqueness, eleven date-precision guards, and the final quality/map/
analysis receipt join. It does not repeat the full-corpus acceptance validation.

Rebuild this small handoff from the original MAIN checkout with
`py -3 scripts/package_quality_release_evidence.py --write`. The explicit input
allowlist and manifest pins are checked before writing; changed existing package
files are rejected. A second rebuild must use a new deliberately named package if
any protected input changed. No source archive/corpus copy is permitted by that
builder. This README, verifier and packaging receipt supplement its generated
source inventory and should be retained with the handoff.

Purpose and retention: retain this bounded, compressed evidence handoff with the
current validated quality release and Git history. Shared original research,
canonical source data, the current validated deployment and one known-good
production rollback remain protected. No superseded staging or additional dataset
backup is created here; no cleanup is necessary to complete this handoff. Net disk
growth is approximately 3.8 MiB, with no newly created file over 100 MiB.

# Original-source encounter enrichment pilot

This additive pilot reviews **24 source entries**, representing **20 case families and 25 reported episodes**. It joins **25 existing UFOCAT reports**: **22 reviewed identity links**, **3 held candidates**, and **1 source entry with no confirmed native episode link**. It adds **36 scoped entity observations and 56 attributed attributes**. These are source annotation units, not a count of verified beings, independently verified incidents, or deduplicated encounters.

Canonical shared artifacts:

- `C:/Users/jarod/Desktop/UFO Timeline map tool/data/research/encounter-enrichment-pilot-20261013/validated/reviewed/evidence.json.gz`
- The adjacent `manifest.json` and `audit.json`.
- Protected original captures and `primary_manifest.json` in the same shared research parent.

The runtime payload is **14,338 bytes compressed / 80,172 bytes decoded**. Compressed SHA-256: `eb263f4f9f520438e524263698900f5220c907f464dc34474a3ddeffc40fccfc`. Decoded SHA-256: `e00b934e1a2152ad4bdeac00db38a2d56184c0631fa0aa05ecaa1dafc29db34f`. The artifact pins the existing encounter base decoded SHA `0a26ec2f83c9c2f368c9e457c94d7ec0d651f8da514cdfd27662ee2735bbe8b8`.

## Source coverage and rights

Sixteen entries come from the custodian-hosted original HUMCAT cards for [1954](https://cufos.org/PDFs/HUMCAT/HUMCAT_Index_1954.pdf), [1961](https://cufos.org/PDFs/HUMCAT/HUMCAT_Index_1961.pdf), [1965](https://cufos.org/PDFs/HUMCAT/HUMCAT_Index_1965.pdf), and [1975](https://cufos.org/PDFs/HUMCAT/HUMCAT_Index_1975.pdf). Four entries come from [Albert Rosales’s 1993 catalog](https://www.iraap.org/rosales/1993.htm). Four come from attributed source comparisons for [Megrit](https://ufologie.patrickgross.org/ce3/1954-10-04-france-megritf.htm), [Quarouble September](https://ufologie.patrickgross.org/1954/10sep1954quaroublef.htm), [Mourieras](https://ufologie.patrickgross.org/1954/10sep1954mourierasf.htm), and [Quarouble October](https://ufologie.patrickgross.org/1954/10oct1954quaroublef.htm).

These are original catalog/source-comparison materials, often citing earlier reports; they are not all contemporaneous witness documents. Upstream references are retained per entry. Eight local source files are hash-pinned. The Rosales page was reviewed live; direct local acquisition returned HTTP 403, so its capture hash remains **null**. Its evidence hash is explicitly a locator/excerpt annotation hash, not a captured-page hash. No private access, credentials, or access restriction bypass was used.

Source capture does not establish a redistribution license. Public output contains factual annotations, source links, and at most 25 quoted words per source. Full PDFs/HTML remain protected research inputs outside runtime assets. No source full narratives, new private addresses, or bulk NUFORC collection were imported. The 1973 HUMCAT material bearing a historical publication restriction was not selected or downloaded for this pilot.

## Scientific distinctions retained

| Distinction | Accepted behavior |
| --- | --- |
| Report versus episode versus case | Native report IDs stay intact. Two Panama records link to one compiled episode; paired Hellwig, Druce, Torphins and Dewilde accounts remain separate reported episodes. |
| Contact versus abduction | `contactKind` labels interaction. `onboardStatus` separately records reported, absent, or disputed transport. Invitations, greetings, and exchanges do not establish abduction. Panama consent remains unclear. |
| Conscious versus hypnotic recall | Hill and Stalnaker have separate recall stages. Penrose’s planned hypnosis and Mendes’s refused hypnosis are not classified as completed hypnotic recall. |
| Repeated history versus dated event | Lake Huron is recurring history with unknown episode count. Later Stalnaker events and a separate Torphins resident’s history are not added to the selected episode. |
| Individual versus group attribute | Height/clothing attributes attach only to the described individual or explicit group. Overlapping attribute groups carry flags and must not be summed as independent beings. |
| Clock versus measured UTC | Source civil clocks are reported metadata. Exact coordinates and verified UTC remain null throughout the pilot. Existing chronology exclusions remain effective. |
| Phenotype versus species | Source descriptions and stable appearance keys are preserved as reported classifications; they are not biological identifications. |

The original card images corrected consequential OCR errors: Pinhal reads **21:30**, not the extracted text’s 21:50; Walton reads **18:30**, not the extracted text’s 10:30. Walton’s existing 18:10 remains an explicit source conflict. Penrose’s card supplies 23:30 where the native record has the `00` sentinel. Brands Flats describes one occupant’s left-hand finger, not an OCR-implied forehead mark. Wauwatosa’s five-foot staff is not converted into being height.

Where a locality permits an IANA zone candidate, provenance labels the candidate as inferred. Two conditional civil-rule offsets were calculated with installed **tzdata 2026c**, which is recorded rather than represented as the latest rules release. The [IANA database](https://www.iana.org/time-zones) describes civil-time rules; a rules calculation does not verify that a witness used that zone or recover an observation time. No computed UTC enters this pilot.

## Holds and limits

- `3356684600748588`: first Poole candidate has native 1964 versus source “about 1965”; identity remains held.
- `1555818683808798`, `1958215277055445`: Happy Camp candidate dates are October versus the selected source’s approximately November account. Both remain excluded from runtime annotation joins.
- Torphins HC3943: no confirmed first-episode native report. Coverage gap retained; the morning/hairy native report links only to HC3944.
- `2881065199895387`: Stalnaker already has `source_date_flagged_erroneous` in the chronology sidecar. Reviewing another source does not clear that flag.
- Megrit and Quarouble keep incompatible times, occupant versions and later retellings explicit. Matching a source identity does not adjudicate its claims or alternatives.

The pilot improves evidence structure and reviewable metadata. It is neither a corpus-wide enrichment pass nor a complete abduction dataset, and supplies zero verified UTC episodes and zero source-verified exact sites.

## QA and replay

`scripts/encounter_enrichment_build_pilot.py` verifies original report ID, source, native source ID, chunk, detail index, original plain-chunk SHA, date and clock. It pins source captures, reviewed input, builder and existing encounter base, checks references/unique IDs, and fails if pinned inputs change during the build. All source-derived additions preserve the originals.

Actual artifact checks passed, including forced/voluntary semantics, mixed recall, refused/planned hypnosis, staff-versus-height, separate Walton crews, inferred relative-day boundaries, candidate holds, and taxonomy restrictions. **11 focused tests passed**; `docs/qa/encounter-enrichment-pilot-20261013/focused-test-receipt.json` pins the artifact and test source. Build: Python 3.14 / pypdf 6.14.2, approximately 3.6 seconds, reading only selected original chunks in place.

```powershell
python scripts/encounter_enrichment_review.py
python scripts/encounter_enrichment_build_pilot.py --output '<new-empty-replay-directory>'
python -m unittest discover -s tests -p test_encounter_enrichment.py
```

The builder refuses nonempty output. Replays use the protected source captures; the acquisition script refuses to replace an existing capture manifest. Review-input edits require another reviewed, uniquely named output and promotion decision, not an overwrite of the validated pilot. Existing preserved native originals allow identity checks to be replayed without a corpus copy.

## Exact per-label origin sidecar

`scripts/encounter_enrichment_label_origins.py` produced the separate shared `label_origins/` artifact. It reran the unchanged pinned classifier on all **16,319 indexed original encounter rows**, tracing actual accepted per-label decisions and checking traced/normal output parity. It did not infer origins from collection names or re-parse stored excerpts. **12,595** rows have being labels: **9,395** source-origin rows, **5,913** narrative-origin rows, and **1,846** rows where the same label is supported by both. Source/narrative origins overlap and these row counts must not be summed.

Origin gzip: **879,454 bytes**, SHA `81fee2c14f22417e560bd6c0dcc61def5d51d15d2981dddcc3cb2f142b1af687`; decoded SHA `b6302f29b698728c8ba38acb733aec832754b9a6589a50f3e5ffa175ae08105f`. Unknown-origin labels: zero. That sidecar and its manifest/audit are canonical additive provenance; no original descriptions or classifier decisions changed.

## Storage lifecycle

Canonical: shared `validated/reviewed/` pilot and `label_origins/` artifacts. Unique protected research inputs: eight bounded captures (9,799,400 bytes) and their manifest. Rebuild evidence: small discovery/identity inputs, reviewed annotations, rendered cards and QA receipts. Current deployed site and the known-good rollback remain unchanged. There is no superseded deployed release or full staging tree from this task. The parent `validated/` keeps one small quality intermediate; `validated/provenance/` preserves its exact reviewed input, builder and test receipt. It differs only in the room-versus-craft transport guard for Stalnaker. These files are unique quality provenance, excluded from runtime. The saved builder and source input allow reproduction to a new empty directory with their input paths bound explicitly; original source/chunk pins are unchanged.

Validated reviewed pilot folder: 28,532 bytes. Shared pilot research total: 10,928,633 bytes (approximately 10.42 MiB). Frontend QA: approximately 1.18 MiB, including ten small source-card images. Scripts/tests: approximately 64 KiB. **Approximate owned net growth: 11.7 MiB**, excluding root’s small runtime copies/Git metadata. No created file exceeds 100 MiB; largest is the 3.09 MiB original 1954 PDF. C: free space at the receipt was approximately 9.8 GiB. All outputs remain below the task’s 20 MiB ceiling.

No deletion is proposed: these are unique source/provenance/QA inputs, not redundant full releases. Any later removal requires a literal allowlist and a retained reproducible canonical counterpart under the project storage policy.

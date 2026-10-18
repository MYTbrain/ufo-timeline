# Encounter quality audit and source recovery

Reviewed 2026-10-17. Local working changes; no deployment or push.

The audit covers every one of the **16,319 indexed source reports** and **10,853 acquired Rosales source accounts**. These populations overlap and cannot be added together. The metadata audit is corpus-wide; detailed historical source review remains a much smaller, explicitly identified subset. Neither catalog membership nor a successful source association verifies the reported event.

## Coverage and remaining gaps

The audit joined all indexed reports to 71 effective summary shards covering all 702,893 catalog rows, checked label-origin identity, applied the current timing overlay, and verified all 73 retained original captures. It found no duplicate report IDs or repeated indexed native detail references. That does **not** establish the absence of duplicate incidents or source conflations.

| Layer | Important remaining gap |
| --- | --- |
| Indexed encounter reports | 3,029 unmapped; 5,220 with nonexact dates |
| Indexed being descriptions | 4,076 specify no being type beyond “unspecified” |
| Reported-abduction rows | 1,644 have no indexed being description |
| Indexed timing | 11,859 lack clock-supported runtime timing; 2,632 have whole-calendar-day envelopes, which are not known clocks |
| Acquired Rosales accounts | 5,519 nonexact dates; 883 unknown/missing raw times; 391 nonspecific locality signals |
| Source identity | 87 numeric HC collision groups involve 177 acquired accounts; HC alone is not a safe join |

The full per-record gap registry and a source-stratified research queue are retained privately in the shared research folder. A second full pass after integration uses the recovered citations, effective association revisions, and five measurement holds, so the current queue does not keep requesting the twelve already recovered citations. Missing metadata is not interpreted as a negative observation or assigned an invented credibility score.

## Corrections and recovered information

**Citation recovery:** twelve footers omitted by the parser were recovered from the already retained originals. Missing parsed citations fell from 18 to six. This includes unlabeled source lines, malformed “Source” labels, and citations embedded in damaged HC footers. The derived 10,853-account metadata view preserves every original account ID and changes only the recovered bibliography, review flags, and its provenance. The original capture and original metadata remain protected.

**Capture completeness:** a full check of the 73 sources identified one truncated 2003 HTML account and one recoverable 1994 PDF account held because of letterspaced labels. That additional account remains a separate held recovery candidate. Three explicitly removed entries were not reconstructed. The 10,853 accounts describe our acquired and parsed material, not a complete historical Rosales collection.

**Height units:** all 2,441 indexed height rows were checked against their native details, reading 281 chunks (6.32 GB) in place. The [official codebook](https://cufos.org/PDFs/UFOCAT%20Codebook%202023.pdf), printed page 10, declares feet. Five same-number metric/feet conflicts received manual subject review: four clear unit conflicts and one additional unit/subject ambiguity. The local tool now withholds those five values from height comparisons, preserves the original fields, and explains the hold in report evidence. The future extractor has a corresponding guard. No automatic conversion was made; other ranges and numerical disagreements remain research candidates.

**Original-source research:** eight comparison groups were reviewed across earlier investigator articles, original-author catalogs, and a later first-person book. These produced nine case/source-episode families of research findings. Immediate additions to existing runtime context comprise 18 attributed findings across eight source-account records, supported by seven additional documents and nine source entries:

- **Poole:** the [original Harris article](https://ignaciodarnaude.es/wp-content/uploads/2025/08/HarrisUFOs-1971Poole-HospitalEnglandFSR-CH-1972-N-9.pdf) and native author/journal/page/family metadata resolve one previously held identity. The native 1964, HUMCAT approximately 1965, and original source-relative age remain distinct. The source gives Roderick, rather than the later Broderick. The second figure was reported the following afternoon.
- **Ipswich:** the [upstream-author catalog](https://www.project1947.com/kbcat/kbmoreintoz.htm) gives 00:15 instead of 02:00, plus five perceived versus 75 elapsed minutes. Both clocks remain visible. Missing time is not recoded as abduction.
- **Casino:** the [investigator’s catalog](https://www.project1947.com/kbcat/kbabduct0505.htm) gives 16 March at about 21:00 instead of 6 March at 03:00. Conscious observations, later hypnosis, and the two adults’ descriptions remain separate. The identity hold remains.
- **Baca:** the author’s bedroom experience and neighboring woman’s account are distinct. Internal date/relative-time conflicts in the [later book](https://www.theparacast.com/resources/MysteriousValleyeBook.pdf), printed pages 211–212, remain unresolved.
- **Juárez:** the Nuevo León/Chihuahua disagreement remains unresolved. Government locality evidence establishes ambiguity, not the encounter’s location.
- **Calama:** the capture rumor and single winged-attacker narrative have different source chains. The [recovered journal report](https://www.geocities.ws/INEXPLICATA2000/issue7/3.html) helps trace the rumor; the contradicted association remains held. Military capture and NASA involvement are not established facts.
- **Hill:** the reproduced early letter, November 1961 dream narrative, and 1964 hypnosis material in [Webb’s investigation file](https://cufos.org/PDFs/Abductions/1961_09_19_US_NH_White-Mountains_NICAP_Hill.pdf) receive explicit documentary stage attribution. This is the investigation already cited downstream, not independent corroboration.

Additional research retained outside runtime promotion covers Largs Bay regression provenance and UFORA reference; Adelaide bibliography; Melbourne 1979 sleep-transition and group-specific height; NSW reporting age versus event age; and Melbourne 1992 wake/sleep context, UFORA reference, and unsupported phenotype detail. Mambau, Happy Camp, Benalmádena and Padova original-source leads remain documented and unresolved.

The runtime’s prior six source tables remain exact prefixes. Its 202 stored association rows are unchanged; one explicit reviewed revision changes effective accepted associations from **127 to 128**, leaving **74 held**. The 16,319 base classifications, event IDs, source dates, and coordinates remain unchanged. Additional-source findings and existing recall stages can be expanded in the Analysis report inspector.

## Geographic and duplicate correction still requiring release integration

The Santa Elena de Codao/Canales record points to Calama coordinates although the [investigator article](https://www.geocities.ws/adels_adels/index_archivos/0008.html) places it in Peumo/O’Higgins; a [government locality source](https://ohiggins.mop.gob.cl/seremi-saravia-para-mejorar-la-conectividad-en-sectores-rurales-son-claves-los-alcaldes/) independently supports that geographic distinction. A separate Calama record repeats a narrative already retained in the Santa Elena record’s merged evidence. Exact native pins and the coordinate-invalidation proposal are recorded. **The global map point has not yet been changed and the records have not been merged.** A reviewed map-data correction must invalidate the unsupported point without guessing an exact replacement and reconcile the duplicate/source conflict before rebuilding the relevant map/trace artifacts.

## Validation and next work

Focused checks cover source pins, unchanged prior records, explicit identity revision, held conflicts, measurement exclusions, unsafe source text, report-inspector rendering, and future extractor behavior. The completion receipt records the executed tests. This was not a production deployment or a complete new visual browser review.

Next priority is the documented geographic/source conflation, followed by native bibliography joins for held associations, original witness/investigator documents for recall and entity scope, and source-supported locality recovery. Exact dates, UTC, being types and coordinates must remain unknown where evidence does not establish them. Later web retellings that quote Rosales are source dependencies, not independent confirmations.

## Rebuild and retention

Canonical research: `C:/Users/jarod/Desktop/UFO Timeline map tool/data/research/encounter-quality-20261017/`.

- Current metadata audit: `corpus-audit-current/`; pre-improvement baseline and its exact producer: `corpus-audit-validated/`; source/capture checks: `source-capture-integrity/`; citation-recovered view: `citation-recovery/`.
- Height audit and adjudications: `height-unit-audit/`; source captures/findings: `gap-research/`, `original-research/`, and `investigation-sources/`.
- Current reviewed enrichment: `validated/evidence.json.gz`, promoted to local `data/encounters/enrichment.json.gz` with manifest pins. Retained immediate prior: shared `data/research/encounter-reviewed-20261017/validated/evidence.json.gz`.
- The O’Brien book is retained only on D:, with its exact path/hash in the capture manifest. Full source texts remain private and are not included in Git or runtime.
- One superseded diagnostic audit directory, `corpus-audit/`, is documented as noncanonical. Its exact cleanup candidate inventory is in `lifecycle.json`; no deletion was performed.

Rebuild commands use new empty output directories and shared inputs in place: `encounter_quality_corpus_audit.py`, `encounter_original_citation_recovery.py`, `encounter_height_unit_audit.py`, and `encounter_source_capture_integrity.py`. `encounter_quality_supplements.py` additionally requires the immutable immediate-prior enrichment and the pinned reviewed-supplements JSON. Runtime height holds are the reviewed attribute delta in the manifest. No full corpus, static bundle, staging tree, or deployment copy was created. Current validated production and its sole rollback remain unchanged. Exact size/hash inventory and net disk growth are recorded in the lifecycle receipt.

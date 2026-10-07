# Famous-case catalog identity audit — 2026-10-06

This is a bounded review of original catalog records behind famous-case navigation. A named historical case can have no mapped reports within its date/vicinity preset even when the catalog contains a clearly identified record. A contextual vicinity match is not a case identity match. References below identify catalog entries about a case; they do not establish the reported object's origin, confirm narrative claims, or represent independent observations.

## Catalog provenance and scope

- Production/release `data/app_config.json` points to `https://pub-e9029ab2f6b448daad03d7cde7e15e64.r2.dev/releases/coordinated-reliability-v152-20260731/data/canonical_web/`.
- The original workspace `data/canonical_web`, `static_bundle/data/canonical_web`, and release-root `data/canonical_web` have byte-identical canonical, summary and detail-chunk manifests.
- The shared detail files inspected here resolve through `static_bundle/data/canonical_web` to `C:/Users/jarod/Desktop/UFO Timeline map tool/static_bundle_rollback_f21b47a5/data/canonical_web`. The current `static_bundle` junction itself resolves to the retained acceptance site on D:; no corpus was copied.
- Canonical manifest counts: 702,893 events, 580,783 mapped events, 282 full-detail chunks and 71 summary shards. The recorded canonical input is `data/canonical_full_maximal_v3_rehydrated_jurisdiction_repair/deduped_events.jsonl` in the original research workspace.
- The parallel coverage audit verified the 71 existing local gzip summary shards against SHA-256 and byte lengths pinned for the immutable July 31 R2 objects in the release reproduction contract. This is verification against the pinned deployment contract; current live shard bytes were not downloaded for this identity audit. A direct CLI R2 request returned HTTP 403.

| Manifest | SHA-256 |
| --- | --- |
| `canonical_web_manifest.json` | `242ff4abc42c70c2b241a3cd16c8b9059bca137d940bd6147c5a65de63b7750b` |
| `summary_manifest.json` | `9c50d0e608fc89d1dc7523cde5f407a45e2d10a9e6adefaf83384d1a8a209bdc` |
| `event_chunk_manifest.json` | `833ca33e18ca17768b2e1852d36ad28bd45f9544e88d1821677a67ac176a9d19` |

## Cash–Landrum: six explicit identity references

All six records below have `sort_date_iso=1980-12-29` and `date_precision=exact_day`. The preset uses a separate approximate navigation center `[30.08, -95.1]`, a 75 km vicinity and default context dates 1980-12-28 through 1980-12-30. The center is not substituted into these records. Detail indices are zero-based positions in the specified JSON array.

| Event ID | Detail chunk / index | Source identifier and source row | Served mapping | Explicit identity evidence |
| --- | --- | --- | --- | --- |
| `4435047138615330` | `chunk_000005.json` / `1204` | `ufocat2023.csv`; IRN/PRN `111830`; row `123935`; source reference `DStacy1`, investigator field `JSchuessler` | `geocoded`, city; `[31.25044, -99.25061]`; raw location `HUFFMAN, Harris, TX, US`; mapping needs review | Raw `NAMES: CASH=LANDRUM`; Diamond shape; road encounter, physiological effects and helicopters in the source description. |
| `2777607620134637` | `chunk_000028.json` / `1363` | `majestic.csv`; `Eberhart_6220`; row `43538`; timeline locator `timeline_part5.html#35DF5D33`, entry `43536` | `unresolved`, country; no latitude/longitude; raw location `Piney Woods of East Texas near Huffman` | The narrative names Betty J. Cash, Vickie and Colby Landrum, describes the road encounter near Huffman and discusses their lawsuit. |
| `1525578423981311` | `chunk_000057.json` / `257` | `majestic.csv`; `rr0_2895`; row `43532`; locator `timeline_part5.html#4D170247`, entry `43530` | `unresolved`, unknown; no coordinates or location field | Description explicitly names `Cash/Landrum Incident` and December 29, with an archived RR0 witness reference. |
| `2789274609070155` | `chunk_000145.json` / `1059` | `majestic.csv`; `Maj2_725`; row `43529`; locator `timeline_part5.html#330B511E`, entry `43527` | `unresolved`, city; no coordinates; raw location `north of Houston, TX` | Description explicitly says `Cash-Landrum incident`. Its additional investigation assertion is a source claim, not an audit conclusion. |
| `1440440470049090` | `chunk_000207.json` / `309` | `majestic.csv`; `Overmeire_3094`; row `43530`; locator `timeline_part5.html#2D579C7A`, entry `43528` | `unresolved`, city; no coordinates; raw location `USA, Huffman, between Caney and Dayton (Texas)` | Description explicitly titles the case `Cash-Landrum` and names Bette Cash, Vicky Landrum and her grandson. |
| `1380717117749497` | `chunk_000227.json` / `2093` | `majestic.csv`; `Johnson_8644`; row `43539`; locator `timeline_part5.html#4177F809`, entry `43537` | `unresolved`, unknown; no coordinates or location field; narrative describes a rural road near Dayton | Narrative names Betty Cash, Vickie Landrum and grandson Colby and describes the road encounter and subsequent case. |

The UFOCAT entry has `canonical_event_id=evt_d2f1dc17d3aa224cb0416b24`, 22 retained source-provenance/input members and `duplicate_record_count=22`. Six displayed references are six catalog rows about the case, not six independent incidents, confirmations or witnesses. Whether every retained member belongs to one incident was not re-adjudicated here.

### Coordinate discrepancy and current parser contract

The served UFOCAT point is about 418 km from the preset center using a spherical haversine distance, well outside the 75 km vicinity. The parallel Leaflet-based coverage audit reports about 420 km. Both measurements identify the same material exclusion.

The preserved raw fields are `LATITUDE: 30.03`, `LONGITUDE: 95.08`, `REGION: US`, `STATE: TX`. In the current original-workspace parser:

- `parser/csv_sources/ufocat.py` passes these fields to `coordinates_from_fields` and then `_normalize_ufocat_coordinate_signs`.
- `parser/csv_sources/base.py:coordinates_from_fields` and `parser/canonical_schema.py:coerce_coordinate` interpret numeric text as a float. There is no special degrees-and-minutes conversion on this adapter path.
- The conservative US/TX hemisphere rule changes a positive longitude to negative. A read-only invocation on these four raw fields returned `(30.03, -95.08)`, with `source_coordinates` at the initial field-extraction step.
- This documents current implementation behavior. It does not independently establish the original codebook's coordinate encoding or positional accuracy. The served entry is explicitly `geocoded`, rather than retained source coordinates. The intervening reconciliation decision was not reviewed in this audit.

No coordinates, dates, canonical files or source records were changed. A user-facing repair can expose these original entries with **Mapping needs review** or **Unmapped** status and direct full-detail access while keeping the separate navigation center approximate. A coordinate correction requires a reviewed data correction workflow.

### Excluded mentions and weaker candidates

The text search found 30 records containing Cash/Landrum or witness-name tokens. Many are later commentary, comparisons or separate sightings; text occurrence alone was not accepted as case membership. In particular, Austin reports `2295054664126301` and `3041474250073677` mention a perceived connection in their narratives but describe a separate Austin sighting. They are excluded from the identity crosswalk.

Two dated 1980-12-12 entries (`2742256558099896`, UPDB/NICAP source `5181972`, and `729823850165965`, majestic/NICAP source `NICAP_DB_5345`) explicitly mention Cash/Landrum but have conflicting source dates. They are excluded from this exact-date crosswalk. The UPDB point repeats the same out-of-vicinity Huffman geocode.

Two same-day unmapped narratives are candidate associations, not accepted explicit identity references: `3921133534704119` (`chunk_000126.json` / `2008`, majestic `Maj2_724`) describes Dayton helicopters and includes speculative assertions; `2771933228538620` (`chunk_000236.json` / `2421`, majestic `HallUFOE2_366`) describes a Huffman road encounter without naming the case or witnesses. Date, place and resemblance alone were not used to promote these into the six-reference crosswalk.

## Other zero-vicinity presets: reviewed original references

The parallel 85-preset coverage audit identified six presets with zero mapped reports in their default date/vicinity window: Cash–Landrum, Maury Island, Calvine, Berkshire County / Labor Day, Hangzhou Xiaoshan Airport and Norway spiral. Zero vicinity is a spatial/date query result, not evidence that the historical case is absent from the catalog. Original identity inspection established the additional references below. All listed dates retain the original `exact_day` catalog values.

### Maury Island: seven explicit original references

All seven references have `sort_date_iso=1947-06-21`. Later case investigations, the bomber crash, comparisons to the incident and other June sightings were excluded from this original-event crosswalk. The source narratives include allegations and source hoax assessments; identifying a reference does not endorse either.

| Event ID | Detail chunk / zero-based index | Source identifier / source row | Served mapping | Identity evidence |
| --- | --- | --- | --- | --- |
| `1022815602953765` | `chunk_000001.json` / `2140` | UFOCAT source/PRN `114181`; raw IRN `11570`; row `161221`; source reference `JVallee01` | `geocoded`, city; `[47.50012, -120.50147]`; raw `MAURY ISLAND, King, WA, US`; mapping needs review | Raw `NAMES: DAHL`; description identifies six tire-shaped objects over Puget Sound. |
| `3788857718621447` | `chunk_000029.json` / `690` | majestic `Maj2_233`; row `5034` | `unresolved`; no coordinates or location field | Description explicitly says `Maury Island Incident`. |
| `834979913809692` | `chunk_000039.json` / `1895` | majestic `Magonia_56`; row `5044` | `unresolved`; raw `Maury Island, near Tacoma, Washington` | Names Harold A. Dahl and describes the six objects and alleged metal fragments. |
| `2940389522932652` | `chunk_000056.json` / `651` | majestic `Eberhart_931`; row `5047` | `unresolved`; raw `Maury Island, Washington` | Names Harold A. Dahl and his son Charles in the Maury Island encounter narrative. |
| `1761834897578309` | `chunk_000112.json` / `1316` | majestic `Johnson_3565`; row `5049` | `unresolved`; no location field; narrative names Maury Island/Puget Sound | Names Harold A. Dahl and the alleged metal-fragment encounter. |
| `1899321965915825` | `chunk_000166.json` / `817` | majestic `Overmeire_1184`; row `5036` | `unresolved`; raw `USA, Maury Island, Tacoma` | Narrative identifies Dahl, his superior Fred L. Crisman and the six objects. |
| `3365016448763449` | `chunk_000182.json` / `19` | majestic `rr0_607`; row `5037` | `unresolved`; no coordinates or location field | Description explicitly opens `Start of the Maury Island affair` and names Dahl/Crisman. |

The served UFOCAT geocode is about 147 km from the approximate `[47.37, -122.45]` navigation center, outside the preset's 75 km vicinity. Its raw fields retain `LATITUDE: 47.38`, `LONGITUDE: 122.42`, `REGION: US`, `STATE: WA`; these would pass through the same numeric/sign parser path discussed above. No source point was substituted for the served geocode in this audit.

### Calvine, Hangzhou and Norway spiral

| Preset | Original event ID | Detail chunk / zero-based index | Original date | Source identifier / source row | Served mapping and identity evidence |
| --- | --- | --- | --- | --- | --- |
| Calvine photograph | `2681305045272129` | `chunk_000232.json` / `2031` | `1990-08-04` | majestic `Eberhart_6917`; row `48023` | `unresolved`; no coordinates; raw `A9 near Calvine, Perthshire, Scotland`. Narrative identifies two hikers, a diamond-shaped object, an RAF Harrier and photographs. |
| Hangzhou Xiaoshan Airport | `2003214068068190` | `chunk_000118.json` / `325` | `2010-07-07` | majestic `Eberhart_7606`; row `54164` | `unresolved`; no coordinates; raw `Hangzhou Xiaoshan International Airport`. Narrative describes the airport closure and diverted flights after the reported object. |
| Norway spiral | `1218480407598414` | `chunk_000029.json` / `1111` | `2009-12-09` | majestic `Eberhart_7594`; row `54139` | `unresolved`; no coordinates; raw `Tr�ndelag` contains an encoding replacement character. Narrative identifies the blue beam/gray spiral across northern Norway. The historical preset separately retains the missile-launch explanation. |

For Hangzhou, an UPDB email-discussion record (`1986387425324626`, date `2010-07-01`) mentions the airport but has a different source date and describes correspondence, rather than the original July 7 event narrative. It was not added to this original-event crosswalk. US dream/comparison narratives mentioning the Norway spiral were likewise excluded.

### Berkshire: original September case identity not verified

A bounded search of case-name/location tokens and 1969-dated full-detail records did not identify a reviewed original September 1 Berkshire/Labor Day case reference. The search found two February 7 East Canaan records (`1181466031201992`, UPDB `5510376`, and `3812367247756440`, MUFON `48028`) whose narratives mention a separate September Ashley Falls/Berkshire case. They describe the February encounter and were not promoted into September case identities. Date-window candidates did not establish a match either. This is a bounded non-verification result, not a claim that the complete corpus contains no possible Berkshire reference.

## Verified full-detail chunk hashes

These SHA-256 values cover the exact shared JSON files read for the 16 accepted explicit references across five presets.

| Detail file | SHA-256 |
| --- | --- |
| `chunk_000005.json` | `96aa9d687fc751caf26af671c5fcfbb07ad7ecea28ffd5cf29422f3c606c2561` |
| `chunk_000028.json` | `f4af0ef24bcaabe7bada0f01bca45063206b24e47ca30d26407b3db492d85b28` |
| `chunk_000057.json` | `fde2a701fb46e19f86ad248cdbef775d416e4b9b0227d874bfad6bdaf636ea34` |
| `chunk_000145.json` | `57edf3aadd2a29c7edf158d95a7f934b5062b0c2fe8b1736a22cd756627973ae` |
| `chunk_000207.json` | `4dac437da2182019ba7360d8084992874b1d6ec98bb84d031f80f6f2b44a954e` |
| `chunk_000227.json` | `f28fb4c324a679de1d0e7f34382a59bd0399a7c79d4a045f842d61f0a9348143` |
| `chunk_000001.json` | `2ac97f98e23e346b7e82f49066dea3b17297e35c62e8c3a5354aa26a82553615` |
| `chunk_000029.json` | `5b8c3579e817637d82ef01b09305358fbdd047532a6615114e7b2e706e030bca` |
| `chunk_000039.json` | `376f8138d0c89eb77ec77bc47dffff04e11bf6cea213fdee50b3c36f04e3c3b5` |
| `chunk_000056.json` | `7d9ee01c70bfd7e4f5f6504d7267eeb93843bdded574683c489b57f754353a96` |
| `chunk_000112.json` | `973da5bc92f4f6a2092d25800207a0459978079a5879b5d11360810734fbb768` |
| `chunk_000166.json` | `3c218a26dd9bd5e3e3a6e945d611e053241732871626df755ad2b0281c7d531a` |
| `chunk_000182.json` | `378943541c8419a846ed4dab8b403093b487aee2a97e40adb472ebdd5c168a34` |
| `chunk_000232.json` | `edbe51c70bb118a0f6189744b7d45ea2ead8cb16a16bbd38a1884574f639846d` |
| `chunk_000118.json` | `00f18774a843021a7e11bbd17ca6c1e68529931d3b0618d74ca9e24c2390906e` |

## Reproduction and retention

Read the small canonical manifests, identify case-name matches with a filename-only text search, and inspect the specified full-detail rows in place. Confirm event ID, source ID, date, identity text and served mapping before adding any crosswalk reference. Hash the existing detail files and compare the shared manifests with release metadata. This Markdown file is a small retained provenance artifact; no dataset, deployment bundle, recovery copy or temporary large directory was created.

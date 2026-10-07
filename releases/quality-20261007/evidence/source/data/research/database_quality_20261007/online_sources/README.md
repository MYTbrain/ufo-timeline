# Online source recovery — 7 October 2026

This bounded review accepts 14 source-supported changes: 13 previously unmapped account records receive a supported reference point, and one receives a locality correction while remaining unmapped. Four of the mapped account records describe one Pan Am incident, so these counts are database improvements, not counts of independent sightings. Thirteen reviewed leads are explicitly withheld.

The canonical database, frontend, and production deployment were not changed by this lane. The ready-to-integrate sparse output is `accepted_online_recovery_decisions.jsonl`; its base, source, and evidence pins are in `decision_manifest.json`. `online_incident_relationships.json` retains the four Pan Am account representations without merging them.

## Accepted changes

| Account group | Records | Reported date | New information and mapping role |
| --- | ---: | --- | --- |
| Pan Am Flight 203 | 4 | 1952-05-08 | Rounded observer position in the original witness and USAF records: 31°20′ N, 70° W. Approximate source-reported aircraft observer position. |
| UK Airprox 2017195 | 1 | 2017-07-14 | Published encounter reference 50°56′ N, 000°03′ E. Approximate aircraft encounter reference near Uckfield. |
| UK Airprox 2019098 | 1 | 2019-04-28 | Published encounter reference 51°09′ N, 000°07′ E. Approximate aircraft encounter reference east of Gatwick. |
| UK Airprox 2019091 | 1 | 2019-05-05 | Published encounter reference 51°02′ N, 000°00′ W. Approximate aircraft encounter reference southeast of Crawley. Zero longitude is valid here. |
| Ground observers at Heathrow | 4 | 1950, 1959, 1966 | Current published airport reference point, with city-level precision. It locates the named facility; it does not locate the historical tower or observer exactly. |
| Vatican Museums photographic account | 1 | 2009-04-17 | Named museum observer facility verified against Rome's municipal facility page. City-level reference marker; the window and object position remain unknown. |
| Walla Walla airport controller | 1 | 1996-02-03 | Government airport station reference point, with city-level precision. It does not assert the historical tower position. |
| Barra da Tijuca photographs | 1 | 1952-05-07 | Recovers the explicit locality and country. Remains unmapped because the reviewed investigation does not establish a suitable observer coordinate. |

The original [USAF Blue Book file](https://thedailydialectics.com/bluebook/scans/1950s/1952-05-9612806-ATLANTICOCEAN.pdf), scan pages 2 and 5, gives the Pan Am observer position. Each of the four preserved account records was independently matched through its flight/date, distinctive narrative, and original source locator. The aircraft type, route description, altitude, and time-zone discrepancies remain in the source records. Rounded coordinates and unknown historical accuracy are represented as approximate; they are not object coordinates.

The original UK Airprox Board assessments provide the [2017195 encounter reference on page 5](https://www.airproxboard.org.uk/Documents/Download/1715/676d6913-3528-4d32-8e66-50e2f5ec8c7b/1813) and [2019091 and 2019098 references on pages 3 and 5](https://www.airproxboard.org.uk/Documents/Download/1713/767ba307-2c1e-4031-b39d-ff0193e0fb9a/2315). Aircraft, date, time, and distinctive object descriptions match the account records. The 2019098 original gives FL117 whereas its secondary database narrative gives 17,000 feet; the contradiction is recorded without rewriting the narrative.

The Heathrow point comes from the airport reference table on page 25 of a [technical assessment published by the London Borough of Hillingdon](https://planning.hillingdon.gov.uk/OcellaWeb/viewDocument?file=dv_pl_files%5C2382_APP_2023_2906%5CAviation+Glint+%26+Glare+Assessment.pdf&module=pl). The four source narratives independently place the ground observer at Heathrow. The present-day reference cannot establish the old tower location. The September 1966 account retains its month precision and existing sort-date approximation; 15 September is not asserted as its exact incident date.

The preserved MUFON account explicitly places the photographer at a window in the Vatican Museums. [Rome's municipal visitor service](https://www.turismoroma.it/en/places/vatican-museums-and-sistine-chapel) supplies the named facility's point. Its room, window, and object distance remain unresolved, and the existing country field remains unchanged. The preserved NUFORC account explicitly places the Walla Walla controller in the airport tower. The [US National Weather Service airport observation station](https://forecast.weather.gov/MapClick.php?FcstType=text&lat=46.0946&lg=en&lon=-118.2858&unit=1) supplies a government facility reference. Neither case is promoted to an exact observer position.

The [original Colorado investigation of the Barra da Tijuca photographs](https://files.ncas.org/condon/text/case48.htm) supports the reported locality and date. It also records unresolved photographic evidence and objections to the asserted distant-object interpretation. Those findings do not establish an object location or justify a precise map point.

## Safeguards and abstentions

Every accepted row is pinned to the canonical manifest, summary manifest, source detail gzip, detail index, event ID, source-native ID, full source-record digest, and retained online evidence. Eight current-value guards cover source, sort date, locality, latitude, longitude, coordinate source, precision, and mapped status. Only single-member canonical records were accepted. Raw narratives, dates, identifiers, and original source fields are unchanged.

Coordinate roles distinguish reported observer position, published aircraft encounter reference, and a named ground observer facility reference. A departure airport, destination, map-image center, publisher address, or object position is never substituted for an observer location. Unknown historical accuracy stays visible.

`online_source_abstentions.json` documents 13 withheld records, including one multi-member record needing complete member review; a Pan Am account whose route description conflicts with the original file; translated or abbreviated accounts without a sufficient source-native incident pin; airborne airport-route accounts lacking an actual observer position; remote television-image accounts; and a general policy statement that is not an incident report.

Bounded live access to the original NUFORC site failed with HTTP 403. No new original NUFORC case content is claimed from those requests. The Walla Walla case identity comes from its preserved native report; its new online evidence concerns only the government geographic reference. Prior Mojave and St Austell recoveries were excluded to avoid repeating the previous batch.

Validation passed once against the real pinned records: 14 accepted guard checks, 14 detail-pin checks, and 84 negative controls that reject stale guards, a stale base, or a nonaccepted status. The receipt is `validation_receipt.json`. The counts are suitable for integration review; they do not imply that all unmapped records were audited.

## Rebuild and retention

Run `build_online_decisions.py` from this directory against the shared `data/canonical_web` base. It reads compressed shards in place and reconstructs the sparse decisions from `reviewed_online_specs.json` and retained evidence. Run `test_online_decisions.py` to repeat the bounded guard validation. Both scripts are read-only with respect to canonical data. Changed source or base hashes must cause a new review rather than silently rebasing accepted decisions.

The new canonical analysis output for this lane is the accepted JSONL, its manifest, reviewed specifications, relationship file, abstentions, and validation receipt. Retained PDFs, HTML, rendered coordinate pages, and retrieval receipts form the provenance bundle. Small source extracts are retained working evidence supporting the acceptance and abstention review. No whole database, corpus, staging tree, release, or rollback copy was created.

The shared canonical dataset and the prior `database_quality_20261006` review remain the baseline and rollback for this sparse analysis. Production and its retained deployment rollback remain under the parent release workflow and are unchanged. No superseded large staging or backup directory was created; no deletion is proposed. `artifact_inventory.json` records the actual retained bytes and hashes. There are no new files larger than 100 MiB, and net local growth is approximately 10 MiB. All files in this lane should be retained with the integrated correction provenance; temporary re-renders can be regenerated from the pinned source PDFs if later explicitly allowlisted for cleanup.

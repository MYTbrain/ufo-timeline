# Five MUFON occurrence-date corrections

Prepared 19 October 2026. Not deployed; original CSVs and published catalog files remain unchanged.

## Finding

Both screenshots reproduce a value already present in the imported MUFON data: 1890-04-01 at 12:00 AM. This is not a parser century-conversion error. The adapter accepted a syntactically valid upstream field as an exact observed date, and the old chronology also treated its midnight as a precise local clock.

All 138,856 MUFONpy rows were screened. Exactly five share this date/time, and their seven source fields are identical in the retained sibling MUFON CSV. No alternate occurrence date was recovered from those copies or bounded online searches.

| MUFON native ID | Place | Submission | Review |
| --- | --- | --- | --- |
| 8882 | New Rochelle, NY | 2008-01-15 | Narrative dates its photographs to 2007–2008, without a supported exact incident day. |
| 9920 | Brentwood, NY | 2008-03-13 | No supported replacement occurrence date. |
| 12619 | La Junta, CO | 2008-09-18 | Screenshot 1. The witness explicitly says several years had passed and they do not remember dates. |
| 18815 | Maryland | 2009-08-22 | Screenshot 2. The account mentions reporting to 9-11; the narrative is omitted with a 2012 redaction note. No recoverable incident date. |
| 30468 | City, MD | 2011-07-31 | No description or supported replacement occurrence date. |

Submission is a separate date role. A modern submission of an old report is not inherently an error. Neither submission dates nor the 2012 redaction note replaces an occurrence date. Modern wording alone does not identify a corrected year.

The wider screen found 36 nonzero pre-1900 records, including 28 in 1890, plus 90 year-zero rows. The other 31 early records are an individual-review roster, not automatic invalidations. One source explicitly says 1890 was selected because the form had no earlier years; other records describe plausible nineteenth-century oral histories. April 1 is therefore a suspected shared placeholder in these five reviewed records, not a documented universal sentinel for every historical report.

Primary-source context: MUFON's July 2023 Journal, printed page 12, describes the CMS search range as starting in 1890: https://mufon.com/wp-content/uploads/2024/11/JULY_2023_MUFON_Journal_WEB.pdf . This does not document April 1 as a default. Direct access to https://mufoncms.com/cgi-bin/report_handler.pl?req=view_long_desc&id=18815 failed; access failure is retained as a limit, not negative evidence. Original event dates remain unresolved.

## Prepared correction

The five exact source identities, canonical input IDs, row hashes and current detail locators are pinned. Future builds apply the reviewed correction after deduplication, preserving stable identity. Current runtime summaries, packed points, full details and Analysis use a small local review module; the complete corpus is not copied or rewritten.

Normalized occurrence dates, ordinal keys, placeholder midnight and derived UTC/playback fields are withheld. Date precision becomes unknown and exact-day eligibility is false. Titles, results, markers and details say **Date unverified**. Original date/time, narratives, coordinates, source fields and submission dates remain inspectable; the detail view explicitly labels the imported date unverified and displays submission separately. Undated reports remain available in All Time when non-exact dates are included.

Packed traces cannot revive the rejected date from the old immutable trace index. Core Analysis and A/B date cohorts receive null ordinals and unknown date precision. Moon/planetary/cross-context inputs use those current core values. A separate sparse worker flag prevents cached reporting-delay or clock projections from treating these five rejected occurrence dates/times as measurements. This does not suppress independently supported clocks on every other undated report.

The shared local reporting-delay table assigned the five cases 43,022–44,315 days, but its hashes differ from the published runtime manifest. Those exact local values are not claimed as verified served values. The structural independent-projection issue was verified in current worker code and guarded. The local time-of-day table already classified their midnight as sentinel_ambiguous.

The parser guard refuses stale source hashes, date fields, primary identity or merge topology. Current sparse runtime guards leave unrelated dates and supported future corrections untouched. Later rebuilt records retain the explicit date-review label even if chunk locators change. Remaining early records require their own source review.

## Evidence, verification and retention

- evidence-receipt.json pins original CSVs, current manifests, the selected five summary/detail inputs, and compact evidence captures. Its read-only status describes acquisition; the implementation is recorded separately in implementation-receipt.json.
- fixtures.json contains five current summary/detail pairs, five-source-rows.json preserves seven original fields, and pre1900-roster.json is the full bounded early-date triage list.
- Product tests cover actual canonical exports, source-identity guards, raw-field preservation, current app compaction/packed projection/detail rendering, a real Analysis worker window with a valid historical control, and derived reporting-delay/time-of-day holds. Startup/loading-cover behavior and existing partial-date/encounter behavior are checked.

Canonical new artifacts are this compact review, the checked-in guarded corrections and tests. They rebuild by reading the pinned originals and selecting the five exact source identities; the wider roster uses the recorded year screen. No new canonical corpus, Analysis database, stage, backup directory or release bundle was generated. Retain these unique review receipts with Git; retain shared original sources in place. Approximate net project growth on C: is below 1 MiB, no new file exceeds 100 MiB, and no superseded large artifact needs cleanup. No deletion is authorized.

Current validated deployment remains 16b1c76f-8896-4c00-ab00-4676212a941e (94384c0), retained rollback 16443086-c630-41d8-a793-92a0243a76f6 (15ab160), and accepted preview 5e423cb2. No deployment, immutable artifact overwrite or main-branch push occurred in this sidequest.

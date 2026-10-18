# Encounter quality release — 18 October 2026 UTC

Production: https://ufo-timeline.pages.dev/

- Validated deployment: `b4e04dc8-4605-486e-bdbc-174acd3ca37e`.
- GitHub main/source: `576e09b904341bc7184180fcfbe74a4efecf364d`.
- Sole designated production rollback: previous production `626b22b4-af0a-4252-8525-0ba21289c0d0`, source `8721330997f1851c620fdb6a34512b16a3cda1b0`.
- Public verification: 192 runtime objects verified against frozen hashes and byte lengths. Cloudflare's known Analytics insertion was removed exactly before verifying three HTML objects. All 194 delivery files also match their Git objects. The 87 existing R2 objects were unchanged; no R2 upload was required.

## Encounter integration

The complete 702,893-row catalog was checked in place through the app serializer and catalog worker. All 16,319 encounter-index joins matched catalog ID, source, chunk, and detail index, with zero missing or mismatched joins. The indexed population includes 12,595 source reports describing beings and 3,217 reported abductions. These are source-report counts, not deduplicated incidents.

Both encounter populations and all 33 core comparison axes passed the actual-data checks. The five disputed height fields remain withheld from numeric analysis while their original values are preserved.

Reviewed context is now reachable in map inspection and full Results details, and in Analysis → Encounters → Classification & sources → Reviewed source context & additional research. The inventory provides 202 catalog reports, 128 accepted associations, 74 held associations, 210 source entries, 214 entity descriptions, 557 attributed fields, and eight additional source reviews containing 18 findings. The two reviewed reports without positive encounter classifications and one unlinked source account remain inspectable without acquiring invented classifications or incident identities.

Hosted browser testing confirmed the full 16,319/12,595/3,217 population after removing shared date/type restrictions. The browser caught and the release fixes an inspector embedded within a hidden topic: it now lives at the common Analysis root and cancels pending inspection on topic changes. Regression coverage checks the actual HTML ancestry and stale replies. An unlinked Torphins account also rendered with its source and uncertainty intact.

The 10,853 acquired Rosales source accounts remain research material requiring identity and episode review. They are not added to incident counts merely because they were acquired. Raw narratives and private capture paths were not published.

## Storage lifecycle

Canonical runtime release: the deployment above and the single in-place stage `.tmp/workspace-analysis-20261008-pages`, pinned by `releases/workspace-analysis-20261008/delivery_plan.json`. Stage inventory: 194 files / 39,700,042 bytes; tree SHA-256 `20359b4fe23ade419e47d82f6f3ae3252f992e4084d9135b1eb543a052f3b8e1`.

The existing stage grew by 3,268,194 bytes (about 3.12 MiB). QA receipts, source changes and subsequent bounded research add a few MiB; no newly created file exceeds 100 MiB. No corpus, repository, static bundle, or database was copied, and no dataset was deleted. Canonical corpus inputs remain shared in the desktop project. C: remained below the 100 GiB reserve; no operation expected to add more than 100 MiB was performed.

The temporary `encounter-quality-20261018` provider preview was solely a hosted integration candidate because the existing R2 CORS rules permit hosted site origins. Its bytes are reproducible from the source commit and the one stage; it is superseded by validated production and is not designated as an additional rollback. Earlier provider histories were not duplicated locally or deleted. The superseded failed diagnostic `data/research/encounter-quality-20261017/corpus-audit` has an existing literal cleanup proposal; deletion remains unperformed.

Post-release research is retained privately under shared `data/research/encounter-quality-20261017/post-release-research`, with each stream responsible for source pins, purpose, rebuild method and retention. Research changes do not silently alter this validated production release.

## Completed post-release batch

`post-release-research/INDEX.json` is the new research checkpoint. A sparse, guarded metadata addition covers 247 existing source accounts: 15 repaired headers, seven explicitly written calendar dates, and 240 other date structures retained as uncertainty constraints. Its audit replays 257 source blocks across 64 pinned captures. Original fields remain intact; no complete metadata copy is required. Ten accounts remain held, including six absent citations.

Original-source follow-up adds 22 attributed findings across five groups, including a 1955 facsimile distinguishing a hypnosis-session date and duration from physical encounter timing. New source descriptions remain separate from native identity and episode adjudication.

The Santa Elena/Calama decision package validates coordinate invalidation against the official guarded correction contracts and documents the map, trace and Analysis dependencies. It does not apply a partial detail-only correction, invent a replacement location, or merge the two accounts. A future coordinated data release must preserve the current MUFON and reviewed-year repairs.

Measured stage/research/QA growth is approximately 11 MiB, plus small source and Git bookkeeping changes; there are no new files over 100 MiB. No cleanup or deletion was performed. The temporary local validation server was stopped. Production browser verification confirms all 202 reviewed reports are reachable after clearing shared restrictions, and records no console errors. The production screenshot and provider/public/browser receipts remain beside this note.

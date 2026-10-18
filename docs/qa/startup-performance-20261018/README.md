# Startup performance pass

Baseline production source: 576e09b904341bc7184180fcfbe74a4efecf364d (Cloudflare deployment b4e04dc8). Baseline browser receipt is retained in baseline-browser.json. One normal desktop reload measured 12.206 seconds to Ready, including 6.104 seconds for canonical summary fetch/ingestion and 1.583 seconds across the previously serial support loaders. Browser cache/network/device conditions are not controlled laboratory conditions.

Candidate changes overlap independent pinned requests, cache release/version-addressed compressed binaries normally, correct the startup worker gzip URL, and avoid replacement copies of newly owned compact catalog rows. All source/data identity, hash and validation checks remain in place. No corpus, Analysis dataset, feature or initial visual readiness requirement is removed. The loading overlay remains until Ready, initialViewReady and no error, retaining its minimum display duration and failure feedback.

Storage: reuse the single .tmp/workspace-analysis-20261008-pages stage in place; candidate194files39,702,320bytes, only2,278bytes larger than validated production stage. Shared corpus and87immutableR2 objects are reused with no upload/rebuild. Keep production b4e04dc8 canonical and626b22b4 as its sole designated rollback until a new production publication is explicitly made. This pass creates only small source/test/QA changes; no project artifact above100MiB, new full data copy, superseded local stage or deletion. Browser-managed caching of existing immutable binaries remains bounded by their existing compressed sizes.

Purpose/retention: retain this unique before/after performance evidence and tests. Hosted candidate is for review, reproducible from its Git commit and the one bounded stage, and is not an extra rollback release. No cleanup proposed.

## Verified hosted result

Candidate: https://startup-performance-20261018.ufo-timeline.pages.dev/ (4ee785d3, runtime sourceabfc36f). Production remainsb4e04dc8; this is a review preview. All194runtimeGitbytesmatchthefrozenplan, andallfourchangedpublicobjectsverify. The87R2objectsareunchanged.

Two complete current-release reloads:12.206s,19.391s. Three candidate repeat loads:8.781s,9.126s,9.249s (median9.126s). The first candidate visit took16.767s while downloading uncached support and binary files; it is retained, not treated as a controlled cold-start comparison. Do not present these normal-browser observations as universal speed or a guaranteedpercentage.

All complete samples reached the same702893catalog/582877mapped counts and identical initial770sightings/721traces, with every initial visual gate true. The loading screen was visibly captured during the new report-evidence phase; actual-app tests verify readiness,900msminimumandfailure behavior. Additional tests verify concurrent barriers/failures, unchanged encounter attributes and measurement holds, worker gzipfallbacks, versioned-cache policy and gziperrors.

Project source/test/QA/stage growth is below1MiB; normalbrowser-managed caching can add about29.6MiB for the two existing packed binaries, plus small shell-versioned resources. No new project file exceeds100MiB. No corpus or analysis rebuild/copy, data removal, additional local stage or cleanup was performed.

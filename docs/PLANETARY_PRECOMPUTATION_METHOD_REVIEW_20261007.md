# Planetary precomputation: independent method and architecture review

The approved architecture precomputes astronomical quantities, not filtered report statistics. It accelerates the local candidate while preserving the report/date/provenance gates and the existing descriptive interpretation. It does not authorize deployment.

## Settled atlas plan

The engine owner proposes a sorted Int32 Unix-day index; per-body geocentric apparent tropical longitude as Float64 and centered-six-hour longitude rate as Float32; and a shared Float64 true-equinox precession/nutation offset. The nine-body list is explicit in the manifest: Sun, Moon, Mercury, Venus, Mars, Jupiter, Saturn, Uranus and Neptune. Pluto must remain explicitly outside this atlas unless added by a declared schema/build change; existing direct calculations can provide a separate supported path.

The timestamp grid is UTC hours `[0, 4, 10, 12, 16, 22]`. The day set includes all eligible dated-report days across the three catalogs, every candidate day in their represented calendar months, and a one-day halo on both sides. For a report date `d`, the old initial samples at `d−14h`, `d+12h`, and `d+36h` map to `(d−1)10h`, `d12h`, and `(d+1)12h`. All old six-hour interior refinement samples also map exactly onto this grid. Thus it can provide the unchanged conditional sampling path for each selected body, partner, orb and zodiac system.

Six slots are a superset of the five hours required by current day-only comparisons. Hour zero additionally supports midnight lookup; its inclusion is a small explicit design allowance rather than a different uncertainty model. Arbitrary verified timestamps and custom ayanamsa callbacks retain the direct calculation path, avoiding interpolation presented as an observed position.

Using approximately 66,000 dates and nine bodies, the longitude/rate channels require about 40.8 MiB, the shared offsets about 3.0 MiB, and the day index about 0.25 MiB in memory. These are planning estimates, not measured build sizes. Persist only the canonical compressed atlas and its manifest; retain the decompressed typed data in memory without an additional raw binary file. The engine owner estimates a compressed artifact below 45 MiB. The final build receipt must record actual compressed/in-memory sizes, hashes, duration and net disk growth.

## Precision and method preservation

Float64 longitude avoids rare sign, exact-aspect or refinement-trigger bin changes caused by Float32 angular quantization. Float32 longitude spacing near 360 degrees can reach 0.0000305 degree; that is smaller than the existing model margin but can still change an exact displayed count at a bin edge.

The selected Float32 rate channel has negligible numeric error for ordinary motions, but classifications must still match the original double-precision calculation. The planned direct-rate fallback within `1e−7 degree/day` of the positive and negative `0.01`, `0.05`, `0.008`, and `0.012` thresholds protects stationary classification, refinement decisions and rate-margin edge cases. Preserve the original centered-six-hour **tropical** rate convention and its explicit label; do not silently change it while accelerating the calculation.

The precomputed shared offset is the same true-equinox-of-date transform used by the reviewed Lahiri helper. Add the pinned mean J2000 origin at query time. The same raw atlas can therefore support tropical, Lahiri and Fagan/Bradley views without storing separate coordinate copies. Major-aspect separations remain based on the same raw longitude differences and declared orb.

The existing 50-hour possible civil-date interval, sampled-bound label, longitude/rate margins, exact-day requirements, historical-calendar exclusions, non-report classifications and original date roles must remain unchanged. A faster loader is not new scientific evidence or a tighter continuous uncertainty enclosure.

## Manifest and loader contract

The manifest should identify:

- Schema and layout versions, compression, byte order, numeric types, channel order, alignment, body order, UTC grid, dimensions and total uncompressed byte length.
- Unix-day epoch, normalized Gregorian calendar and supported/covered dates, including halo purpose.
- Earth-geocentric apparent true-ecliptic/equinox-of-date longitude; light-time and aberration convention; centered-six-hour tropical rate.
- Pinned Astronomy Engine version/commit/SHA256, planetary algorithm version, source fixtures and the shared-offset/J2000-origin definitions.
- The canonical compressed SHA256, decompressed-byte SHA256, sorted-day-set hash, and input manifests/hashes used to construct the coverage universe.
- Measured artifact sizes, build duration, reproducible build command and retention decision.

Validate hashes, dimensions, body/grid order and exact expected byte length before installing the candidate. The install must be atomic and must invalidate prior derived day/month caches. Retain the already validated state if the new atlas fails validation. Align Float64 blocks to eight-byte offsets or use an explicit DataView layout; an odd Int32 index count must not produce a misaligned Float64 view. Views must use the declared byte order, not an undocumented assumption about host layout.

Missing days or genuinely unsupported bodies require an explicit bounded direct fallback or an unavailable result. Do not substitute the nearest date, noon of another date, an interpolated catalog timestamp, or a zero-filled position.

## Filter and query behavior

The astronomical atlas is independent of keywords, craft type, sources, geography, selected areas and date-window filters. After each query, the selected report cohort still determines counts, date-role totals, categories and calendar weights. Include planet, partner, orb, zodiac, active window, the complete report filter identity and atlas/schema identity in derived-result cache keys.

Reuse a compact eligible per-date/category cohort when its complete filter identity is unchanged. Preserve report multiplicity and provenance totals; folding rows for speed must not turn report counts into unique-date counts. Distinct-date counts remain a separate displayed quantity.

Calendar opportunity includes days without reports and is clipped to the active window. Category-specific year-month weights remain necessary. Source × month weights collapse algebraically into month weights when every source uses the same candidate calendar days; this compact representation is valid and is not a claim to have measured source-specific observing effort. No precomputed whole-catalog category composition may be displayed as the composition of a filtered cohort.

## Bounded parity checks

Require classification and aggregate parity, in addition to coordinate tolerances, for the default full retained cohort and focused filtered/date-window examples. Retain the independent Mercury station, Venus station and Lahiri sign-ingress fixtures. Exercise different bodies, partners, supported orbs and zodiac systems; include the first/last supported dates, halo lookups, months containing no report on some candidate days, and an explicit trusted UTC timestamp outside the atlas grid.

Verify failed integrity/dimension checks cannot replace the validated atlas, and an atlas replacement cannot leave old derived caches active. Measure the first atlas load, a cold configuration switch and a repeated query separately. These checks establish numerical/method parity and responsiveness; they do not establish an astrological association.

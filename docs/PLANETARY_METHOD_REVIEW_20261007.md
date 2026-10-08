# Planetary comparison method review — local candidate

This review concerns the new local Analysis comparisons. It does not authorize deployment or modify report dates, coordinates, or provenance. The report unit remains a dated catalog entry rather than an independently witnessed event.

## Coordinate convention

Use Earth-centered apparent ecliptic longitude referred to the true equinox of date. In the existing pinned MIT Astronomy Engine, this is `Ecliptic(GeoVector(body, time, true)).elon`. `EclipticLongitude(body, time)` is heliocentric and is unsuitable for this purpose. Major aspects use differences in these longitudes, with circular wrapping; they are not full three-dimensional angular separations.

Lahiri sidereal is the default interpretation of the twelve equal 30-degree sectors. Tropical remains a clearly named option. Neither sector system is an IAU constellation classification. Aspects do not change when the same ayanamsa is subtracted from both bodies.

Use the existing ephemeris's precession model to propagate the primary-reference Lahiri anchor rather than a constant present-day or linear annual offset:

```js
const time = Astronomy.MakeTime(date);
const zero = Astronomy.RotateVector(
  Astronomy.Rotation_ECL_EQJ(), new Astronomy.Vector(1, 0, 0, time)
);
const raw = Astronomy.Ecliptic(zero).elon;
const truePrecession = raw > 180 ? raw - 360 : raw;
const trueLahiriAyanamsa = 23.857092333333334 + truePrecession;
const siderealLongitude = ((tropicalLongitude - trueLahiriAyanamsa) % 360 + 360) % 360;
```

The anchor is the **mean** Lahiri ayanamsa at TT Julian day 2451545.0, measured from the official Astrodienst Swiss Ephemeris 2.10.03 calculator in mode 1. The propagated quantity above includes the existing engine's nutation and is therefore a **true** ayanamsa, appropriate for subtraction from true-equinox planetary longitudes. Do not subtract the mean ayanamsa from true longitude without accounting for nutation.

Name this method “Lahiri convention; Astronomy Engine precession model.” It is not a claim that the tool runs Swiss Ephemeris. No Swiss Ephemeris executable, library, or source code is bundled. The comparable Fagan/Bradley J2000 mean anchor is 24.740299972222225 degrees, but the current default is Lahiri.

## Independent reference checks

`data/analysis_comparisons/planetary_reference_fixtures.json` retains complete primary query URLs and numerical results. It contains 22 JPL Horizons positions and 24 official Swiss ayanamsa reference values. The checks cover Mercury retrograde and a Mercury station, a Venus station, tropical longitude wrapping at the March 2024 equinox, a real Lahiri sidereal Pisces–Aries ingress in April 2024, and Pluto at two modern epochs.

Against the initial 22 Swiss checks at 1582, 1900, J2000, 2024, 2100, and the named reference epochs, the helper's maximum true-ayanamsa discrepancy was 0.184 arcsecond (0.000051 degree). The corresponding maximum mean-ayanamsa discrepancy was 0.0126 arcsecond. Across the first 15 JPL positions, the pinned engine's maximum planetary longitude discrepancy was 0.001154 degree. These are empirical checks at the listed dates, **not a mathematical guarantee of a uniform error bound** over all dates.

For a concrete sidereal ingress check, JPL gives the Sun's tropical longitude as 24.0489167 degrees at 2024-04-13 12:00 UT. Official true Lahiri ayanamsa is 24.1948504167 degrees, giving sidereal longitude 359.8540663 degrees, in Pisces. At 2024-04-14 12:00 UT, the corresponding values are 25.028802 and 24.1949172222 degrees, giving 0.8338848 degrees, in Aries. A date-only report on April 13 must retain both possible sectors over its unknown-time interval.

Pluto required no new ephemeris library. One JPL quantity-31 batch query for Pluto's center (999), using `plu060_merged` and the DE441 Earth geocenter, gives 251.4547644 degrees at 2000-01-01 12:00 UT and 302.0333926 degrees at 2024-04-15 12:00 UT. The pinned engine gives 251.4547351599 and 302.0330028017 degrees, respectively; maximum discrepancy is 0.000390 degree. Enabling it remains contingent on the implementation's bounded runtime check. Its inclusion is an astrology convention and does not alter its astronomical dwarf-planet classification.

## Time and boundary uncertainty

- Exact-day reports without verified clock/timezone provenance use UTC noon only as a descriptive reference. Their possible UTC interval is the complete civil date under UTC+14 through UTC−12: `[day−14 hours, day+36 hours]`, a 50-hour interval.
- Evaluate interior samples as well as interval endpoints. Longitude is not monotone during a station; endpoints alone can miss a reversal. Mercury on April 1, 2024 and Venus on July 23, 2023 are independent fixtures demonstrating this issue.
- Finite sampling supports “stable at sampled times” and “possible at sampled times.” It must not be described as a certified continuous enclosure. A small declared position guard around sign/aspect boundaries helps represent ephemeris approximation, but is not a formal global guarantee.
- “Near stationary” requires a declared rate threshold. It is an operational display category, not an exact zero-velocity instant. Rates should identify their longitude frame; using the selected frame consistently avoids silently mixing tropical and sidereal rates.
- Month-only/year-only dates and unverified historical calendar conversions must not acquire precise planetary positions. Crop discovery/publication dates and animal report/discovery dates retain those roles.
- Astrological houses, ascendants, and local visibility require verified timestamps and location. The present catalogs have no qualified population for such measurements; do not assign houses from UTC noon, a country centroid, or a default birthplace.

## Comparison baseline and interpretation

The recommended visible result is observed report counts/shares beside calendar opportunity, with exact tables, eligible distinct dates, and boundary ambiguity. It remains descriptive; p-values, significance labels, causal statements, and Pattern Finder admission are not warranted by this addition.

For calendar opportunity, preserve the selected catalog/domain, source mix, era, and season. Weight candidate days within each represented source × year-month stratum by that stratum's eligible report count, intersecting the active date window. Category comparisons need their own matched source/year-month weights; using the whole-domain expected distribution for every craft/species category can create a source/era confound. Date clustering, duplicates, observer effort, weather, publication behavior, and unmeasured reporting biases remain unresolved.

Slow outer planets may remain in one sign throughout a represented month or much of an era. If the matched strata contain no within-stratum state variation, the comparison is not informative about an association; a ratio near one is not evidence that the planet has no association. Conversely, a long-lived sign cannot be interpreted independently of era/source changes from unadjusted totals.

A fixed three-degree orb for conjunction, sextile, square, trine, and opposition is a declared binning choice. Keep the “outside these aspect bands” category visible. Report counts from browsing many planet/partner/category combinations do not constitute independent confirmatory tests.

## Primary sources

- [JPL Horizons manual, quantity 31 and observer coordinate conventions](https://ssd.jpl.nasa.gov/horizons/manual.html)
- [JPL Horizons API documentation](https://ssd-api.jpl.nasa.gov/doc/horizons.html)
- [Pinned Astronomy Engine JavaScript documentation](https://github.com/cosinekitty/astronomy/blob/865d3da7d8112bbc7911238052c6af4aaf877181/source/js/README.md)
- [Official Swiss Ephemeris documentation, including Lahiri definitions and mean/true ayanamsa](https://www.astro.com/swisseph/swisseph.htm)
- [Official Astrodienst calculator help](https://www.astro.com/cgi/swetest.cgi?arg=-h)

The fixture JSON records individual reproducible calculator and Horizons URLs. Only small numerical reference files and this review were created; no source dataset, corpus, ephemeris package, or large build was copied.

import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import fs from 'node:fs';
const require = createRequire(import.meta.url);
const { computeNuclearContext, facilityActivity, haversineKm } = require('../analysis_nuclear.js');

const test = (id, ordinal, extra = {}) => ({ id, ordinal, country: 'USA', region: 'fixture_site', lat: 40, lon: -100, role: 'weapons', ...extra });
const row = (id, ordinal, extra = {}) => ({ eventId: id, ordinal, datePrecision: 'exact_day', craftType: 'disc_saucer', lat: 40, lon: -100, source: 'fixture_source', ...extra });
const edges = [test('coverage_start', -1000, { lat: -40, lon: 90, region: 'far' }), test('coverage_end', 1000, { lat: -40, lon: 90, region: 'far' })];
const options = { tests: [...edges, test('target', 0)], startOrdinal: -2, endOrdinal: 2, windowDays: 7, distanceBandsKm: [25, 100] };

{
  const result = computeNuclearContext({ ...options, rows: [row('before', -1), row('same', 0), row('after', 1), row('before', -1),
    row('old_control', -365), row('new_control', 364), row('generic_nuclear', 0, { type: 'Nuclear / atomic / weapons test' }),
    row('bad_date', null), row('interval', -1, { endOrdinal: 1, datePrecision: 'month' }), row('unmapped', 0, { lat: null })] });
  assert.equal(result.domains.ufo.eligibleN, 3);
  assert.equal(result.domains.ufo.exclusions.duplicate_report_identity, 1);
  assert.equal(result.domains.ufo.exclusions.noncraft_or_nuclear_context_record, 1);
  assert.equal(result.domains.ufo.exclusions.date_not_exact_day_or_interval, 2);
  assert.equal(result.domains.ufo.exclusions.coordinates_missing_or_invalid, 1);
  assert.deepEqual(result.domains.ufo.phases.map(x => x.pairCount), [1, 1, 1]);
  assert.equal(result.domains.ufo.linkedReportsN, 3);
  assert.equal(result.domains.ufo.calendarBoundaryPairs, 3);
  assert.deepEqual(result.domains.ufo.dayBoundaryExcluded, { before: 0, after: 0 });
  assert.equal(result.domains.ufo.matchedControls.testWindows, 1);
  assert.equal(result.domains.ufo.matchedControls.controlWindows, 2);
  assert.equal(result.domains.ufo.matchedControls.testWindowDays, 5);
  assert.equal(result.domains.ufo.matchedControls.controlWindowDays, 10);
  assert.equal(result.domains.ufo.matchedControls.testPairCount, 3);
  assert.equal(result.domains.ufo.matchedControls.controlPairCount, 2);
  assert.ok(Math.abs(result.domains.ufo.matchedControls.relativeReportDensity - 3) < 1e-12);
}

{
  const result = computeNuclearContext({ ...options, tests: [...options.tests, test('overlapping_target', 1), test('target', 0)],
    rows: [row('one_report', 0)] });
  assert.equal(result.coverage.catalogRows, 4, 'duplicate test identity is removed');
  assert.equal(result.domains.ufo.linkedReportsN, 1, 'one report remains one unique report across overlapping tests');
  assert.equal(result.domains.ufo.phases.reduce((s, x) => s + x.pairCount, 0), 2);
  assert.equal(result.domains.ufo.craftComposition[0].total, 1, 'craft shares use unique reports rather than link count');
  assert.equal(result.domains.ufo.craftComposition[0].share, 1);
}

{
  const result = computeNuclearContext({ ...options, tests: [...options.tests, test('safety', 0, { role: 'safety_or_mixed_safety' })],
    rows: [row('near', 0, { lat: 40.1 }), row('outer_band', 0, { lat: 40.8 })],
    crops: [{ id: 'crop_discovered', startOrdinal: 0, endOrdinal: 0, datePrecision: 'exact_day', dateRole: 'discovery', lat: 40, lon: -100, category: 'pictogram' },
      { id: 'crop_formed', startOrdinal: 0, endOrdinal: 0, datePrecision: 'exact_day', dateRole: 'formation', lat: 40, lon: -100, category: 'ring' }],
    animals: [{ id: 'animal_found', startOrdinal: 0, endOrdinal: 0, datePrecision: 'exact_day', dateRole: 'discovery', lat: 40, lon: -100, category: 'cattle' }] });
  assert.equal(result.coverage.excludedSafetyN, 1);
  assert.equal(result.coverage.selectedTests, 1);
  assert.deepEqual(result.domains.ufo.distanceBands.map(x => x.pairCount), [1, 1]);
  assert.deepEqual(result.domains.crops.byDateRole.map(x => x.dateRole).sort(), ['discovery', 'formation']);
  assert.equal(result.domains.animals.byDateRole[0].dateRole, 'discovery');
  assert.equal(result.readiness.strictInference, 'blocked');
  assert.equal(result.domains.ufo.distanceBands[0].unknownUncertaintyPairs, 1, 'missing uncertainty is not invented as zero');
}

{
  const result = computeNuclearContext({ ...options, tests: [...options.tests,
    test('contaminates_older_control', -364, { role: 'safety_or_mixed_safety' })], rows: [row('one', 0)] });
  assert.equal(result.domains.ufo.matchedControls.controlWindows, 1, 'safety tests contaminate controls despite exclusion from target role');
}

{
  const inputs = [row('recycled1', 0), row('recycled2', 1, { craftType: 'triangle' })];
  const fixture = {};
  const result = computeNuclearContext({ ...options, forEachRow(callback) { for (const value of inputs) { Object.assign(fixture, value); callback(fixture); } } });
  assert.equal(result.domains.ufo.linkedReportsN, 2);
  assert.equal(result.domains.ufo.craftComposition.length, 2, 'callbacks may recycle their row object');
}

{
  const nuclear = [{ id: 'nuclear', name: 'Reviewed', lat: 40, lon: -100, nuclearRoleSourceVerified: true,
    linkedFacilityIds: ['nuclear', 'nuclear_alternate_marker'], activeIntervals: [{ startYear: 1960, endYear: 1980 }], nuclearRole: 'nuclear_research' }];
  const facilities = [
    { id: 'broad', name: 'Research', lat: 40, lon: -100.1, facilityClass: 'research_test', activeIntervals: [[1960, 1980]] },
    { id: 'nuclear_alternate_marker', name: 'Nuclear duplicate', lat: 40, lon: -100, facilityClass: 'research_test', activeIntervals: [[1960, 1980]] },
    { id: 'claimed', name: 'Claimed UFO base', lat: 40, lon: -100, facilityClass: 'claimed_ufo_base', activeIntervals: [[1960, 1980]] },
  ];
  const result = computeNuclearContext({ ...options, nuclearFacilities: nuclear, facilities, rows: [row('one', 0)] });
  assert.equal(result.facilities.nuclearSitesN, 1);
  assert.equal(result.facilities.broaderSitesN, 1);
  assert.equal(result.facilities.byDomain.ufo.groups.find(x => x.id === 'both').reportsN, 1);
  assert.equal(result.facilities.byDomain.ufo.nearestNuclearBands[0].reportsN, 1);
  const withExplicitBroad = computeNuclearContext({ ...options, nuclearFacilities: nuclear, facilities: nuclear,
    broaderFacilities: facilities, rows: [row('one', 0)] });
  assert.equal(withExplicitBroad.facilities.broaderSitesN, 1, 'explicit broader-facility input takes priority over the nuclear list');
  assert.equal(facilityActivity(nuclear[0], Math.floor(Date.UTC(1960, 6, 1) / 86400000)), 'unknown', 'year of opening is a boundary, not a proven daily operation');
  assert.equal(facilityActivity(nuclear[0], 0), 'active');
}

{
  const nuclear = [{ id: 'dateline', lat: 40, lon: 180, nuclearRoleSourceVerified: true, activeIntervals: [[1900, 2000]] }];
  const result = computeNuclearContext({ ...options, nuclearFacilities: nuclear, rows: [row('across_dateline', 0, { lon: -179.9 })] });
  assert.equal(result.facilities.byDomain.ufo.groups.find(x => x.id === 'nuclear_only').reportsN, 1);
  assert.ok(haversineKm({ lat: 0, lon: 179.9 }, { lat: 0, lon: -179.9 }) < 23);
}

{
  const result = computeNuclearContext({ ...options, rows: [
    row('appearance_fireball', 0, { craftType: 'fireball_meteor_like', type: 'Fireball' }),
    row('appearance_satellite', 0, { craftType: 'satellite_like', type: 'Sighting' }),
    row('explicit_astronomical', 0, { craftType: 'fireball_meteor_like', type: 'Astronomical / scientific event' }),
    row('explicit_conventional', 0, { craftType: 'conventional_or_explained', type: 'Sighting' }),
    row('explicit_context_group', 0, { visualTypeGroup: 'non_ufo_context', type: 'Sighting' }),
    row('explicit_nuclear_group', 0, { visualTypeGroup: 'Nuclear / atomic / weapons test', type: 'Unknown' }),
  ] });
  assert.equal(result.domains.ufo.eligibleN, 2, 'appearance words never establish an identified explanation');
  assert.equal(result.domains.ufo.exclusions.noncraft_or_nuclear_context_record, 4);
  assert.equal(result.domains.ufo.craftComposition.find(x => x.category === 'fireball_meteor_like').total, 1);
}

{
  const payload = JSON.parse(fs.readFileSync(new URL('../data/analysis_comparisons/nuclear_context_v1.json', import.meta.url), 'utf8'));
  assert.equal(payload.tests.length, 2051);
  assert.equal(new Set(payload.tests.map(x => x.id)).size, payload.tests.length);
  assert.equal(payload.tests.filter(x => x.lat === null).length, 24);
  assert.equal(payload.tests.filter(x => x.lat === 0 && x.lon === 0).length, 0, 'unknown source coordinates do not become a real location');
  assert.equal(payload.ordinalEpoch, 'unix_day');
  const first = payload.tests.find(x => x.name === 'TRINITY');
  assert.equal(first.ordinal, -8935);
  assert.equal(first.dateRole, 'explosion_GMT_day');
  assert.equal(first.lat, 32.54, 'approximate source marker is retained and not silently corrected');
  assert.equal(first.strictSpatialEligible, false);
  assert.equal(payload.tests.find(x => x.name === 'LITTLEBOY').date, '1945-08-05', 'GMT date is preserved, not converted to the familiar Japanese civil date');
  assert.equal(payload.nuclearFacilities.length, 4);
  assert.ok(payload.nuclearFacilities.every(x => x.nuclearRoleSourceVerified && x.sources.length));
}

console.log('Nuclear chronology, date roles, deduplication, calendar controls, facilities and real-source contracts passed.');

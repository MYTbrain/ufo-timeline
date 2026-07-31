import assert from "node:assert/strict";

import {
  LOW_PRECISION_VALUES,
  daysFromCivil,
  colorForEvent,
  computeDateExtent,
  filterEvents,
  isoToOrdinal,
  normalizeDateBoundary,
  ordinalToIso,
} from "../webapp/static/app-utils.mjs";

const sampleEvents = [
  {
    event_id: 1,
    sort_date_iso: "1947-07-08",
    source: "Maj2",
    type: "sighting",
    location_precision: "city",
    search_text: "roswell new mexico debris",
  },
  {
    event_id: 2,
    sort_date_iso: "1952-07-19",
    source: "BlueBook",
    type: "radar",
    location_precision: "approximate",
    search_text: "washington dc radar",
  },
];

assert.equal(normalizeDateBoundary("1947", "start"), "1947-01-01");
assert.equal(normalizeDateBoundary("1952", "end"), "1952-12-31");
assert.equal(normalizeDateBoundary("1952-07", "end"), "1952-07-31");
assert.equal(normalizeDateBoundary("2024-02-29", "start"), "2024-02-29");
assert.equal(normalizeDateBoundary("2023-02-29", "start"), null);
assert.equal(normalizeDateBoundary("2024-13", "start"), null);
assert.equal(ordinalToIso(isoToOrdinal("0000-01-01")), "0000-01-01");
assert.equal(ordinalToIso(isoToOrdinal("0000-12-31")), "0000-12-31");
assert.equal(ordinalToIso(isoToOrdinal("2024-02-29")), "2024-02-29");
assert.equal(daysFromCivil(0, 1, 2) - daysFromCivil(0, 1, 1), 1);

const filtered = filterEvents(sampleEvents, {
  keyword: "roswell",
  startDate: "1947",
  endDate: "1947-12-31",
  sources: ["Maj2"],
  types: ["sighting"],
  precisions: ["city"],
  hideLowPrecision: true,
});

assert.equal(filtered.length, 1);
assert.equal(filtered[0].event_id, 1);
assert.ok(LOW_PRECISION_VALUES.has("approximate"));

const sourceCoordinateWithoutResolvedPlace = {
  event_id: 3,
  sort_date_iso: "1954-09-18",
  source: "ufocat",
  type: "Fireball",
  coordinate_source: "raw_latlong",
  location_precision: "exact_coords",
  geocode_display_name: null,
};
const preciseOnly = filterEvents(
  [sampleEvents[1], sourceCoordinateWithoutResolvedPlace],
  { hideLowPrecision: true }
);
assert.deepEqual(preciseOnly.map((event) => event.event_id), [3]);

const extent = computeDateExtent(sampleEvents);
assert.deepEqual(extent.min, "1947-07-08");
assert.deepEqual(extent.max, "1952-07-19");
assert.match(colorForEvent(sampleEvents[0], extent), /^hsl\(/);

console.log("frontend utility assertions passed");

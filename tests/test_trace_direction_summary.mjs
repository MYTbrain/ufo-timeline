import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";
const require = createRequire(import.meta.url);
const directions = require("../trace_direction_summary.js");
const browser = {};
runInNewContext(readFileSync(new URL("../trace_direction_summary.js", import.meta.url), "utf8"), browser);
assert.equal(browser.UfoTraceDirectionSummary.segmentDirections({ from: [0, 0], to: [1, 0] })[0].sector, "N", "browser UMD export is available without Node module support");

function close(actual, expected, message) {
  assert.ok(Math.abs(actual - expected) < 1e-8, `${message}: ${actual} != ${expected}`);
}

const center = [0, 0];
for (const [point, bearing] of [[[1, 0], 0], [[0, 1], 90], [[-1, 0], 180], [[0, -1], 270]]) {
  close(directions.mapBearing(center, point), bearing, "map cardinal");
  close(directions.initialBearing(center, point), bearing, "great-circle cardinal");
}
assert.equal(directions.sectorForBearing(0).key, "N");
assert.equal(directions.sectorForBearing(22.4999).key, "N");
assert.equal(directions.sectorForBearing(22.5).key, "NE");
assert.equal(directions.sectorForBearing(337.5).key, "N");
assert.equal(directions.sectorForBearing(-45).key, "NW");
assert.equal(directions.sectorForBearing(405).key, "NE");
assert.equal(directions.sectorForBearing(null), null);
assert.equal(directions.sectorForBearing(""), null);

close(directions.mapBearing([0, 179], [0, -179]), 90, "short east antimeridian connection");
close(directions.mapBearing([0, -179], [0, 179]), 270, "short west antimeridian connection");
close(directions.mapBearing([0, 539], [0, 541]), 90, "wrapped world copy");
close(directions.mapBearing([60, 0], [60, 80]), 90, "straight Mercator link");
assert.ok(directions.initialBearing([60, 0], [60, 80]) < 60, "great-circle bearing is distinct on long east links");
assert.equal(directions.initialBearing([0, 0], [0, 180]), null, "antipodal great-circle bearing undefined");
assert.equal(directions.mapBearing([0, 0], [0, 0]), null);
assert.equal(directions.mapBearing([10, 10], [10, 370]), null, "longitude-wrapped coincidence");
assert.equal(directions.mapBearing([90, 0], [90, 120]), null, "same geographic pole");
assert.equal(directions.mapBearing([86, 0], [87, 0]), null, "same projected location after latitude clamp");
for (const invalid of [[null, 0], ["", 0], [false, 0], [undefined, 0], [0, Infinity], [91, 0], [-91, 0]]) {
  assert.equal(directions.mapBearing(invalid, center), null, `invalid ${JSON.stringify(invalid)}`);
}

const link = (id, from, to, direction) => ({ traceId: id, from, to, neighborhood: { direction } });
assert.equal(directions.segmentDirections(link("east", center, [0, 1], "direct"))[0].sector, "E", "zero-hop direct is chronological forward");
assert.equal(directions.segmentDirections(link("east", center, [0, 1], "backward"))[0].sector, "W");
assert.deepEqual(directions.segmentDirections(link("east", center, [0, 1], "both")).map(row => row.sector), ["E", "W"]);
assert.deepEqual(directions.segmentDirections(link("tie", center, [0, 180], "both")).map(row => row.sector), ["W", "E"], "backward reverses the renderer's chosen 180-degree segment");
assert.equal(directions.segmentDirections({ from: center, to: [1, 0] }, { direction: "backward" })[0].sector, "S");
assert.equal(directions.segmentDirections({ from: center, to: [1, 0], neighborhood: { directions: ["backward", "forward"] } }).length, 2);

const cohort = [
  link("a", center, [0, 1], "forward"),
  link("b", center, [0, 1], "backward"),
  link("c", center, [1, 0], "both"),
  link("d", center, center, "both"),
  link("e", [null, 0], [1, 0], "forward"),
  link("f", [86, 0], [87, 0], "forward"),
  link("a", [0, 360], [0, 361], "forward"),
];
const summary = directions.summarizeDirections(cohort);
assert.equal(summary.inputSegments, 7);
assert.equal(summary.uniqueSegments, 6);
assert.equal(summary.duplicatesIgnored, 1, "world copies must not inflate percentages");
assert.equal(summary.validSegments, 3);
assert.equal(summary.orderedSegments, 3);
assert.equal(summary.unorderedSegments, 0);
assert.equal(summary.bothDirectionSegments, 1);
assert.equal(summary.denominator, 4, "both direction link contributes exactly two directions");
assert.equal(summary.excludedSegments, 3);
assert.deepEqual(summary.excludedCounts, { invalidCoordinates: 1, zeroDistance: 1, undefinedBearing: 1 });
assert.deepEqual(summary.sectors.filter(row => row.count).map(row => [row.key, row.count, row.percentage]), [["N", 1, 25], ["E", 1, 25], ["S", 1, 25], ["W", 1, 25]]);
assert.equal(summary.sectors.reduce((sum, row) => sum + row.percentage, 0), 100);

const unbalanced = directions.summarizeDirections([link("one", center, [1, 0], "forward"), link("two", center, [1, 0], "forward"), link("three", center, [0, 1], "forward")]);
close(unbalanced.sectors[0].percentage, 200 / 3, "honest unrounded percentage");
assert.equal(directions.formatPercentage(unbalanced.sectors[0].percentage), "66.7%");
assert.equal(directions.summarizeDirections([]).denominator, 0);
assert.ok(directions.summaryMarkup(directions.summarizeDirections([])).includes("No report links with known chronological order"));
const markup = directions.summaryMarkup(summary, { selectedSectors: ["E"] });
assert.ok(markup.includes('role="img"'), "chart is accessible");
assert.ok(markup.includes('<th scope="row">'), "exact data available as accessible table");
assert.ok(markup.includes("Radial scale: 0–25%"), "normalized radial scale is explicit");
assert.ok(markup.includes("not reported flight paths"), "connection semantics are stated");
assert.ok(markup.includes("4 directions across 3 ordered report links"), "denominator visible");
assert.ok(markup.includes("count once in each direction"), "both-direction counting disclosed");
assert.ok(markup.includes("Excluded 3 links"), "exclusions visible");
assert.ok(markup.includes('class="is-selected-direction"'), "clicked direction can be identified");
const badge = directions.directionBadgeMarkup(directions.segmentDirections(link("north", center, [1, 0], "forward"))[0]);
assert.ok(badge.includes('class="trace-direction-badge-arrow" aria-hidden="true">➜</span>'), "map marker keeps its visible arrow");
assert.ok(!badge.includes("trace-direction-badge-label"), "map marker does not display compass letters");
assert.ok(badge.includes('aria-label="North report connection (0°)"'), "cardinal direction remains available to screen readers");
assert.ok(badge.includes("--direction-tone:#f5f5f5"));
assert.ok(badge.includes("--direction-arrow-angle:-90.0deg"));
assert.equal(directions.directionBadgeMarkup({ bearing: null }), "");

assert.equal(directions.segmentOrderUncertain({ sameDayOrderKnown: false, gapDays: 2 }), true, "explicit unknown order remains unknown");
assert.equal(directions.segmentOrderUncertain({ sameDayOrderKnown: true, gapDays: 0 }), false, "explicit confirmed same-day report order is retained");
assert.equal(directions.segmentOrderUncertain({ gapDays: 0 }), true, "ordinary shared-date links have no confirmed within-day order");
assert.equal(directions.segmentOrderUncertain({ gapDays: "0" }), true);
for (const gapDays of [null, undefined, "", " ", false, true, Infinity, NaN, 1]) {
  assert.equal(directions.segmentOrderUncertain({ gapDays }), false, "unknown or nonzero gaps do not become numeric zero");
}
const unorderedEast = { ...link("unknown-east", center, [0, 1], "forward"), sameDayOrderKnown: false };
const unorderedWest = { ...link("unknown-west", center, [0, -1], "backward"), gapDays: 0 };
const unknownDescription = directions.describeSegment(unorderedEast);
assert.equal(unknownDescription.valid, true);
assert.equal(unknownDescription.orderUncertain, true);
assert.equal(unknownDescription.direction, "unordered");
assert.deepEqual(unknownDescription.directions, [], "a valid unordered map axis never becomes a chronology direction");
assert.equal(unknownDescription.orientation.bearing, 90);
assert.equal(unknownDescription.orientation.axisLabel, "East–West");
assert.equal(directions.describeSegment(unorderedWest).orientation.bearing, 90, "opposite endpoint ordering yields the identical unoriented map axis");
assert.equal(directions.describeSegment({ ...unorderedEast, from: [null, 0] }).valid, false, "uncertainty does not rescue invalid geometry");
assert.equal(directions.describeSegment({ ...unorderedEast, to: center }).reason, "zeroDistance");
const uncertaintyBadge = directions.directionBadgeMarkup(unknownDescription.orientation);
assert.ok(uncertaintyBadge.includes('aria-hidden="true">↔</span>'), "unordered links retain one double-headed arrow");
assert.ok(!uncertaintyBadge.includes("➜"), "unordered link has no chosen forward arrow");
assert.ok(uncertaintyBadge.includes("is-order-uncertain"));
assert.ok(uncertaintyBadge.includes("sector-unordered"));
assert.ok(uncertaintyBadge.includes("border-style:dashed"), "uncertainty is visible without relying on color");
assert.ok(uncertaintyBadge.includes("--direction-tone:#969696"), "unordered axes use one neutral shade");
assert.ok(uncertaintyBadge.includes("chronological order unknown"));
assert.ok(!uncertaintyBadge.includes("trace-direction-badge-label"), "uncertainty does not add visible letters");
assert.equal(directions.directionBadgeMarkup(directions.describeSegment(unorderedWest).orientation), uncertaintyBadge, "opposite arbitrary order receives the same map badge");

const mixedSummary = directions.summarizeDirections([link("known-east", center, [0, 1], "forward"), unorderedEast, unorderedWest, { ...unorderedEast }]);
assert.equal(mixedSummary.validSegments, 3);
assert.equal(mixedSummary.orderedSegments, 1);
assert.equal(mixedSummary.unorderedSegments, 2);
assert.equal(mixedSummary.duplicatesIgnored, 1);
assert.equal(mixedSummary.excludedSegments, 0, "unordered map links are not invalid coordinate exclusions");
assert.equal(mixedSummary.denominator, 1, "only ordered links enter the directional denominator");
assert.equal(mixedSummary.sectors.find(sector => sector.key === "E").percentage, 100);
assert.ok(directions.summaryMarkup(mixedSummary).includes("2 valid map links have unknown chronological order"));
assert.ok(directions.summaryMarkup(mixedSummary).includes("1 direction across 1 ordered report link"));
const allUnordered = directions.summarizeDirections([unorderedEast, unorderedWest]);
assert.equal(allUnordered.denominator, 0);
assert.equal(allUnordered.unorderedSegments, 2);
const allUnorderedMarkup = directions.summaryMarkup(allUnordered);
assert.ok(allUnorderedMarkup.includes("No report links with known chronological order"));
assert.ok(!allUnorderedMarkup.includes("<svg"), "all-uncertain links cannot produce a directional radar graph");
assert.ok(!allUnorderedMarkup.includes("<table"), "all-uncertain links cannot produce directional shares");
assert.ok(!allUnorderedMarkup.includes("%"), "all-uncertain links display no invented percentage");
const confirmedSameDay = { ...link("confirmed", center, [0, 1], "forward"), gapDays: 0, sameDayOrderKnown: true };
assert.equal(directions.describeSegment(confirmedSameDay).orderUncertain, false);
assert.ok(directions.directionBadgeMarkup(directions.segmentDirections(confirmedSameDay)[0]).includes("➜"), "confirmed report order retains its existing single-headed arrow");

const geographicForward = { ...link("great-falls->salem", [47.5053, -111.3008], [44.9429, -123.0351], "direct"), gapDays: 0 };
const geographicReciprocal = { ...link("salem->great-falls", [44.9429, -123.0351], [47.5053, -111.3008], "direct"), sameDayOrderKnown: false };
const sameGeometryWithoutId = { from: geographicForward.from.slice(), to: geographicForward.to.slice(), gapDays: 0 };
const wrappedGeographicCopy = { ...geographicForward, from: [47.50530000001, 248.69919999999], to: [44.94289999999, 236.96490000001] };
const geometryInputs = [geographicForward, geographicReciprocal, sameGeometryWithoutId, wrappedGeographicCopy];
const geometrySnapshot = JSON.stringify(geometryInputs);
const grouped = directions.groupUnorderedConnections(geometryInputs);
assert.equal(grouped.length, 1, "reciprocal report links and wrapped copies share one undirected badge group");
assert.equal(grouped[0].representative, geographicForward, "representative is a real original report link");
assert.deepEqual(grouped[0].segments, geometryInputs, "badge grouping preserves every original link including missing or repeated trace ids");
assert.equal(JSON.stringify(geometryInputs), geometrySnapshot, "grouping leaves all source records and coordinates unchanged");
assert.equal(directions.groupUnorderedConnections(geometryInputs.slice().reverse())[0].key, grouped[0].key, "group key has no endpoint polarity or input-order dependence");
assert.equal(directions.summarizeDirections(geometryInputs).unorderedSegments, 3, "UI grouping does not replace semantic summary deduplication or its denominator");
const nearParallel = { ...geographicForward, traceId: "parallel", from: [47.5054, -111.3008], to: [44.9430, -123.0351] };
const collinearExtension = { ...link("extension", center, [0, 2], "direct"), gapDays: 0 };
const partiallyOverlapping = { ...link("partial", [0, 1], [0, 3], "direct"), gapDays: 0 };
assert.equal(directions.groupUnorderedConnections([geographicForward, nearParallel]).length, 2, "distinct nearby parallel endpoints do not collapse");
assert.equal(directions.groupUnorderedConnections([unorderedEast, collinearExtension, partiallyOverlapping]).length, 3, "collinear extensions and partial overlaps keep distinct endpoint groups");
const boundaryGeometry = [
  { ...link("boundary-a", [10, 180], [12, 170], "direct"), gapDays: 0 },
  { ...link("boundary-b", [12, 530], [10, -180], "direct"), gapDays: 0 },
];
assert.equal(directions.groupUnorderedConnections(boundaryGeometry).length, 1, "180/-180 and repeated world longitudes use identical canonical endpoints");
assert.deepEqual(directions.groupUnorderedConnections([confirmedSameDay, { ...unorderedEast, from: [null, 0] }, { ...unorderedEast, to: center }]), [], "ordered and invalid or zero-length links do not enter unordered badge groups");
assert.deepEqual(directions.groupUnorderedConnections(null), []);

const tinyOffset = { ...geographicReciprocal, traceId: "near-reciprocal", from: [44.9433, -123.0355], to: [47.5057, -111.3012] };
const coarseProject = point => [point[1] * 100, point[0] * 100];
assert.equal(directions.groupUnorderedConnections([geographicForward, tinyOffset]).length, 2, "default grouping still requires canonical geographic endpoints");
const coarseGroups = directions.groupUnorderedConnections([geographicForward, tinyOffset], { project: coarseProject, pixelTolerance: 1 });
assert.equal(coarseGroups.length, 1, "subpixel endpoint differences group into one display badge at a coarse zoom");
assert.deepEqual(coarseGroups[0].segments, [geographicForward, tinyOffset], "pixel grouping preserves both original report links");
assert.equal(directions.groupUnorderedConnections([tinyOffset, geographicForward], { project: coarseProject, pixelTolerance: 1 }).length, 1, "pixel matching accepts reversed endpoint orientation and input order");
assert.equal(directions.groupUnorderedConnections([geographicForward, tinyOffset], { project: point => [point[1] * 10000, point[0] * 10000], pixelTolerance: 1 }).length, 2, "paths that separate at a closer zoom regain separate badges");
assert.equal(directions.groupUnorderedConnections([geographicForward, tinyOffset], { project: coarseProject, pixelTolerance: 0 }).length, 2, "zero pixel tolerance retains distinct projected endpoints");
assert.equal(directions.groupUnorderedConnections([unorderedEast, collinearExtension, partiallyOverlapping], { project: point => [point[1] * 100, point[0] * 100], pixelTolerance: 1 }).length, 2, "shared-origin overlapping extensions aggregate while partial overlap without a shared endpoint stays separate");
const sharedOrigin = { ...link("shared-origin", center, [0, 3], "direct"), gapDays: 0 };
assert.equal(directions.groupUnorderedConnections([unorderedEast, sharedOrigin], { project: point => [point[1] * 100, point[0] * 100], pixelTolerance: 1 }).length, 1, "shared-origin straight overlapping routes use one badge");
for (const project of [() => [NaN, 0], () => [null, 0], () => [0, Infinity], () => { throw new Error("projection unavailable"); }, () => ({ x: 0, y: 0 })]) {
  assert.equal(directions.groupUnorderedConnections([geographicForward, tinyOffset], { project, pixelTolerance: 1 }).length, 2, "invalid projected points fall back to real geographic identity instead of a shared placeholder");
  assert.equal(directions.groupUnorderedConnections([geographicForward, geographicReciprocal], { project, pixelTolerance: 1 }).length, 1, "unavailable projection preserves safe geographic reciprocal grouping");
}
const binBoundary = [
  { ...link("bin-a", [1, 0.009], [2, 0.109], "direct"), gapDays: 0 },
  { ...link("bin-b", [1, 0.011], [2, 0.111], "direct"), gapDays: 0 },
];
assert.equal(directions.groupUnorderedConnections(binBoundary, { project: coarseProject, pixelTolerance: 1 }).length, 1, "neighbor bins catch visually coincident endpoints across pixel bin boundaries");
const mutableProjectInput = JSON.stringify(geometryInputs);
directions.groupUnorderedConnections(geometryInputs, { project: point => { point[0] *= 10; point[1] *= 10; return point; }, pixelTolerance: 1 });
assert.equal(JSON.stringify(geometryInputs), mutableProjectInput, "project callbacks receive copies and cannot mutate source coordinates");

const salemGreatFalls = { ...link("salem-great-falls", [44.9429, -123.0351], [47.5053, -111.3008], "direct"), gapDays: 0 };
const greatFallsHermiston = { ...link("great-falls-hermiston", [47.5053, -111.3008], [45.8404, -119.2895], "direct"), gapDays: 0 };
const livePixels = new Map([
  [JSON.stringify(salemGreatFalls.from), [3666.399, 8340.195]],
  [JSON.stringify(salemGreatFalls.to), [4421.647, 8102.231]],
  [JSON.stringify(greatFallsHermiston.to), [3912.126, 8263.475]],
]);
const liveProject = point => livePixels.get(JSON.stringify(point));
const liveGroups = directions.groupUnorderedConnections([salemGreatFalls, greatFallsHermiston], { project: liveProject, pixelTolerance: 1 });
assert.equal(liveGroups.length, 1, "actual Salem/Great Falls/Hermiston overlapping straight map paths share one display badge");
assert.deepEqual(liveGroups[0].segments, [salemGreatFalls, greatFallsHermiston]);
assert.equal(liveGroups[0].representative, salemGreatFalls, "longest original connection supplies the badge geometry");
const shortReversed = { ...greatFallsHermiston, from: greatFallsHermiston.to.slice(), to: greatFallsHermiston.from.slice() };
assert.equal(directions.groupUnorderedConnections([salemGreatFalls, shortReversed], { project: liveProject, pixelTolerance: 1 }).length, 1, "reversing the shorter path preserves overlap aggregation");
const shortFirst = directions.groupUnorderedConnections([greatFallsHermiston, salemGreatFalls], { project: liveProject, pixelTolerance: 1 });
assert.equal(shortFirst.length, 1);
assert.equal(shortFirst[0].representative, salemGreatFalls, "a later longer member replaces the representative and its endpoint bins");
assert.deepEqual(shortFirst[0].segments, [greatFallsHermiston, salemGreatFalls], "representative replacement preserves original record order");
const closeZoomProject = point => { const pixel = liveProject(point); return pixel ? [pixel[0] * 4, pixel[1] * 4] : null; };
assert.equal(directions.groupUnorderedConnections([salemGreatFalls, greatFallsHermiston], { project: closeZoomProject, pixelTolerance: 1 }).length, 2, "zoomed perpendicular separation beyond one pixel restores distinct paths");
const linearProject = point => [point[1] * 100, point[0] * 100];
const adjacent = { ...link("adjacent", [0, 1], [0, 2], "direct"), gapDays: 0 };
assert.equal(directions.groupUnorderedConnections([unorderedEast, adjacent], { project: linearProject, pixelTolerance: 1 }).length, 2, "collinear paths meeting only end-to-end have no positive overlapping interval");
assert.equal(directions.groupUnorderedConnections([unorderedEast, adjacent], { project: point => [point[1] * 0.5, point[0] * 0.5], pixelTolerance: 1 }).length, 2, "even subpixel end-to-end paths do not count a mere meeting as positive overlap");
const divergent = { ...link("divergent", center, [1, 1], "direct"), gapDays: 0 };
assert.equal(directions.groupUnorderedConnections([unorderedEast, divergent], { project: linearProject, pixelTolerance: 1 }).length, 2, "a shared endpoint cannot merge a diverging route");
const parallelOutside = { ...link("parallel-outside", [0.02, 0], [0.02, 1], "direct"), gapDays: 0 };
assert.equal(directions.groupUnorderedConnections([unorderedEast, parallelOutside], { project: linearProject, pixelTolerance: 1 }).length, 2, "parallel lines beyond tolerance do not merge");
const bridgeLong = { ...link("bridge", [0, 0], [0, 2], "direct"), gapDays: 0 };
const bridged = directions.groupUnorderedConnections([unorderedEast, adjacent, bridgeLong], { project: linearProject, pixelTolerance: 1 });
assert.equal(bridged.length, 1, "a longer shared-endpoint path can join previously separate overlapping badge groups");
assert.equal(bridged[0].representative, bridgeLong);
assert.deepEqual(bridged[0].segments, [unorderedEast, adjacent, bridgeLong], "bridging groups preserves every record and input order");
const longNorth = { ...link("north-route", center, [1, 0], "direct"), gapDays: 0 };
const tinyShared = { ...link("tiny-shared", center, [0.005, 0.005], "direct"), gapDays: 0 };
assert.equal(directions.groupUnorderedConnections([unorderedEast, longNorth, tinyShared], { project: linearProject, pixelTolerance: 1 }).length, 2, "a tiny shared-origin connector cannot collapse two long divergent routes");

const legendMarkup = directions.legendSummaryMarkup(mixedSummary, { scopeLabel: "Visible traces · September 1994" });
assert.ok(legendMarkup.includes("Visible traces · September 1994"), "legend explicitly identifies its time-window scope");
assert.ok(legendMarkup.includes("1 ordered link"));
assert.ok(legendMarkup.includes("2 unknown-order links excluded"), "unknown-order links remain visible alongside the directional denominator");
assert.ok(legendMarkup.includes("Radial scale: 0–100%"));
assert.equal((legendMarkup.match(/<th scope="row">/g) || []).length, 8, "all eight sectors remain available as exact data");
assert.ok(legendMarkup.includes('title="East">E</abbr></th><td>1</td><td>100%</td>'), "legend shares use only ordered links, not all valid links");
assert.ok(legendMarkup.includes('<details class="trace-direction-legend-details"><summary>Direction counts &amp; shares</summary>'), "narrow legend keeps exact sector data behind a native accessible expander");
assert.ok(legendMarkup.includes("chronological report links; these do not measure craft travel"), "directional associations are distinguished from measured travel");
assert.ok(!legendMarkup.includes("<h4>"), "legend does not duplicate the surrounding panel heading");
assert.ok(!legendMarkup.includes('class="trace-direction-data"'), "legend does not reuse the wide two-column popup layout");

const emptyLegendMarkup = directions.legendSummaryMarkup(directions.summarizeDirections([]));
const unknownLegendMarkup = directions.legendSummaryMarkup(allUnordered);
for (const emptyMarkup of [emptyLegendMarkup, unknownLegendMarkup]) {
  assert.ok(emptyMarkup.includes('<figure class="trace-direction-chart is-empty"><svg'), "empty legend retains its compass radar reference");
  assert.equal((emptyMarkup.match(/<line x1="110"/g) || []).length, 8, "empty radar retains eight labeled spokes");
  assert.ok(!emptyMarkup.includes('fill-opacity="0.16"'), "empty radar draws no invented data polygon");
  assert.ok(!emptyMarkup.includes("<circle"), "empty radar draws no invented data points");
  assert.ok(!emptyMarkup.includes("NaN") && !emptyMarkup.includes("Infinity"), "zero-denominator radar has no invalid geometry");
  assert.equal((emptyMarkup.match(/<td>—<\/td>/g) || []).length, 8, "zero-denominator shares are undefined rather than fabricated zero percentages");
}
assert.ok(unknownLegendMarkup.includes("2 unknown-order links excluded"));
assert.ok(unknownLegendMarkup.includes("no directions can be counted"), "unknown-only traces explain why the reference radar contains no values");
assert.equal(directions.radialChartMarkup(allUnordered), "", "legacy popup chart still suppresses unknown-only distributions");

for (const status of ["off", "disabled", "loading"]) {
  const statusMarkup = directions.legendSummaryMarkup(summary, { status });
  assert.ok(statusMarkup.includes("0 ordered links"), `${status} must suppress stale known counts`);
  assert.ok(statusMarkup.includes('class="trace-direction-chart is-empty"'), `${status} must suppress stale distribution geometry`);
  assert.ok(statusMarkup.includes(status === "loading" ? "Updating trace directions" : "Enable traces"), `${status} has a useful status explanation`);
}
const escapedLegendMarkup = directions.legendSummaryMarkup(null, { scopeLabel: '<img src=x onerror="bad()">', emptyMessage: "<script>bad()</script>" });
assert.ok(!escapedLegendMarkup.includes("<img") && !escapedLegendMarkup.includes("<script>"), "caller-provided scope and status text cannot become HTML");
assert.ok(escapedLegendMarkup.includes("&lt;img") && escapedLegendMarkup.includes("&lt;script&gt;"));
const bothLegendMarkup = directions.legendSummaryMarkup(summary);
assert.ok(bothLegendMarkup.includes("3 ordered links · 4 directions"), "legend distinguishes bidirectional traversal contributions from unique ordered links");
assert.ok(bothLegendMarkup.includes("contributes once in each direction"));
assert.ok(bothLegendMarkup.includes("3 other links excluded: 1 invalid coordinates, 1 coincident endpoints, 1 undefined bearings."), "coordinate exclusions are distinct from unknown chronology");

const streamedRows = [...cohort, unorderedEast, unorderedWest, confirmedSameDay, { ...unorderedEast }];
const accumulator = directions.createDirectionAccumulator();
const emptySnapshot = accumulator.finish();
for (const segment of streamedRows.slice(0, 3)) assert.equal(accumulator.add(segment), accumulator, "streaming additions are chainable");
const firstSnapshot = accumulator.finish();
for (const segment of streamedRows.slice(3)) accumulator.add(segment);
const streamedSummary = accumulator.finish();
assert.deepEqual(streamedSummary, directions.summarizeDirections(streamedRows), "streamed and array summaries agree across forward, backward, both, unknown, exclusions and duplicate links");
assert.equal(streamedSummary.inputSegments, streamedRows.length);
assert.equal(streamedSummary.duplicatesIgnored, 2);
assert.equal(streamedSummary.unorderedSegments, 2);
assert.equal(streamedSummary.orderedSegments, 4);
assert.equal(streamedSummary.denominator, 5);
assert.deepEqual(streamedSummary.excludedCounts, { invalidCoordinates: 1, zeroDistance: 1, undefinedBearing: 1 });
assert.equal(emptySnapshot.denominator, 0, "continuing a scan cannot change an earlier empty snapshot");
assert.equal(firstSnapshot.inputSegments, 3);
assert.equal(firstSnapshot.denominator, 4);
assert.equal(firstSnapshot.unorderedSegments, 0, "later unknown links cannot alter prior snapshot counts");
assert.equal(firstSnapshot.excludedCounts.invalidCoordinates, 0, "later exclusions cannot alter prior nested snapshot counts");
assert.ok(Object.isFrozen(streamedSummary) && Object.isFrozen(streamedSummary.sectors) && Object.isFrozen(streamedSummary.sectors[0]) && Object.isFrozen(streamedSummary.excludedCounts), "all summary snapshot state is immutable");
assert.throws(() => { streamedSummary.sectors[0].count = 999; }, TypeError);
assert.throws(() => { streamedSummary.excludedCounts.invalidCoordinates = 999; }, TypeError);
assert.deepEqual(accumulator.finish(), streamedSummary, "taking a snapshot neither resets nor consumes the accumulator");

const streamOptions = { direction: "backward", bearingMode: "greatCircle" };
const configuredAccumulator = directions.createDirectionAccumulator(streamOptions);
streamOptions.direction = "forward";
streamOptions.bearingMode = "map";
const configuredRows = [{ from: [60, 0], to: [60, 80] }, link("both-geodesic", [60, 0], [60, 80], "both")];
configuredRows.forEach(row => configuredAccumulator.add(row));
assert.deepEqual(configuredAccumulator.finish(), directions.summarizeDirections(configuredRows, { direction: "backward", bearingMode: "greatCircle" }), "streaming freezes configuration and retains great-circle and fallback-direction semantics");
assert.deepEqual(directions.createDirectionAccumulator().finish(), directions.summarizeDirections(null), "empty streaming and non-array summaries use the same contract");

const repeatedLink = link("unique-canonical-source", center, [0, 1], "forward");
const deduplicatedStream = directions.createDirectionAccumulator().add(repeatedLink).add(repeatedLink).finish();
assert.equal(deduplicatedStream.uniqueSegments, 1, "ordinary streaming suppresses duplicate identities by default");
assert.equal(deduplicatedStream.duplicatesIgnored, 1);
const trustedUniqueStream = directions.createDirectionAccumulator({ deduplicate: false }).add(repeatedLink).add(repeatedLink).finish();
assert.equal(trustedUniqueStream.inputSegments, 2);
assert.equal(trustedUniqueStream.uniqueSegments, 2, "explicit no-dedup mode counts every supplied canonical-source row");
assert.equal(trustedUniqueStream.orderedSegments, 2);
assert.equal(trustedUniqueStream.denominator, 2);
assert.equal(trustedUniqueStream.duplicatesIgnored, 0);
assert.equal(trustedUniqueStream.sectors.find(row => row.key === "E").count, 2);
assert.deepEqual(trustedUniqueStream, directions.summarizeDirections([repeatedLink, repeatedLink], { deduplicate: false }), "array and streamed no-dedup modes retain the same contract");
const identityUnreadable = { from: center, to: [1, 0], get traceId() { throw new Error("identity key must not be read"); } };
assert.equal(directions.createDirectionAccumulator({ deduplicate: false }).add(identityUnreadable).finish().denominator, 1, "no-dedup mode skips identity extraction entirely");

console.log("Trace direction summaries passed: wrapped bearings, chronology uncertainty, honest counts, accessible charts and arrow-only badges.");

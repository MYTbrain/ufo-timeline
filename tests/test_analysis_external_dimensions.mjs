import assert from "node:assert/strict";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const Model = require("../analysis_session.js");
const side = (totalN, eligibleN, key, n = eligibleN) => ({ totalN, eligibleN, unknownN: totalN - eligibleN, rows: [{ key, count: n }] });
const input = { key: "morphology", label: "Formation profile", unit: "crop-circle records", notes: ["The temporal intersection uses each held report group."],
  a: side(2, 1, "ring"), b: side(3, 1, "ring") };
const value = Model.compareExternalDimension(input), row = value.rows[0];
assert.equal(value.a.totalN, 2); assert.equal(value.b.totalN, 3);
assert.equal(row.aCount, 1); assert.equal(row.bCount, 1);
assert.equal(row.aShareOfReports, .5); assert.equal(row.bShareOfReports, 1 / 3, "external units must retain their own catalog denominators");
assert.equal(value.unknown.aCount, 1); assert.equal(value.unknown.bCount, 2);
assert.equal(value.unknown.aShareOfReports, .5); assert.equal(value.unit, "crop-circle records");
input.a.rows[0].count = 0; input.notes.push("later mutation");
assert.equal(row.aCount, 1); assert.equal(value.notes.length, 1); assert.equal(Object.isFrozen(value), true);
assert.equal(Object.isFrozen(value.rows), true); assert.equal(Object.isFrozen(value.a), true);

const unavailable = Model.compareExternalDimension({ key: "distance", unit: "eligible report locations", a: null, b: side(2, 1, "near") });
assert.equal(unavailable.a.available, false); assert.equal(unavailable.a.totalN, null);
assert.equal(unavailable.rows[0].aCount, null); assert.equal(unavailable.rows[0].aShareOfReports, null);
assert.equal(unavailable.unknown.aCount, null); assert.equal(unavailable.rows[0].bCount, 1);
const reason = Model.compareExternalDimension({ key: "location", unit: "context records", a: { available: false, totalN: 4, reason: "No bounded context scope.", notes: ["Membership remains held."] }, b: null });
assert.equal(reason.a.totalN, 4, "an unavailable field can retain a known population denominator");
assert.equal(reason.a.eligibleN, null); assert.equal(reason.unknown.aCount, null);
assert.equal(reason.a.reason, "No bounded context scope."); assert.deepEqual(reason.a.notes, ["Membership remains held."]);
const empty = Model.compareExternalDimension({ key: "empty", a: { totalN: 0, eligibleN: 0, unknownN: 0, rows: [] }, b: side(1, 1, "present") });
assert.equal(empty.rows[0].aCount, 0); assert.equal(empty.rows[0].aShareOfReports, null, "a zero denominator has no percentage");

const overlapping = Model.compareExternalDimension({ key: "materials", unit: "collection accounts", multiLabel: true,
  a: { totalN: 3, eligibleN: 2, unknownN: 1, rows: [{ key: "soil", count: 2 }, { key: "plants", count: 1 }] }, b: null });
assert.equal(overlapping.multiLabel, true); assert.equal(overlapping.rows.find(row => row.key === "soil").aShareOfReports, 2 / 3);
assert.equal(overlapping.unknown.aCount, 1, "multilabel counts never erase the explicit unknown population");
const ordered = Model.compareExternalDimension({ key: "lunar", order: "source", a: { totalN: 2, eligibleN: 2, unknownN: 0,
  rows: [{ key: "new", label: "New moon", count: 1 }, { key: "full", label: "Full moon", count: 1 }] }, b: null });
assert.deepEqual(ordered.rows.map(row => row.key), ["new", "full"], "the adapter can preserve a meaningful phase or ordinal axis");

for (const bad of [
  { a: { totalN: 2, eligibleN: 1, unknownN: 0, rows: [{ key: "x", count: 1 }] } },
  { a: { totalN: 2, eligibleN: 2, unknownN: 0, rows: [{ key: "x", count: 1 }] } },
  { a: { totalN: 2, eligibleN: 1, unknownN: 1, rows: [{ key: "x", count: 2 }] } },
  { a: { totalN: 2, eligibleN: 2, unknownN: 0, rows: [{ key: "x", count: 1 }, { key: "x", count: 1 }] } },
  { a: { totalN: 2, eligibleN: null, unknownN: null, rows: [{ key: "x", count: 1 }] } },
  { a: { totalN: 1.5, eligibleN: 1, unknownN: .5, rows: [{ key: "x", count: 1 }] } },
]) assert.throws(() => Model.compareExternalDimension({ key: "bad", b: null, ...bad }), /Analysis session:/);
assert.throws(() => Model.compareExternalDimension({ key: "", a: null, b: null }), /invalid external/);
console.log("External A/B dimensions: distinct context denominators, frozen values, unknown/unavailable/zero distinctions, overlapping labels, source order and invalid coverage rejection passed.");

import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";

const source = fs.readFileSync(new URL("../crop_circle_layer.js", import.meta.url), "utf8");
const start = source.indexOf("  function chronologyNodes(context) {");
const end = source.indexOf("  function edgeKey(", start);
assert.ok(start >= 0 && end > start, "Chronology graph builder must remain discoverable");
const duplicate = ["cc_bd4c5cdf1f3c", 50.4, 2.8, 18448, 18448, 0, 2];
const field = ["cc_e7f5cdae7ab8", 50.401, 2.802, 18448, 18448, 0, 1];
const limited = ["cc_evidence_limited", 51, 3, 18448, 18448, 0, 2];
const points = [duplicate, field, limited];
const context = vm.createContext({
  state: { points, manifest: { chronologyExcludedIds: [duplicate[0]] }, chronology: { coordinateScope: "all" } },
  ROW: { id: 0, lat: 1, lon: 2, start: 3, datePrecision: 5, coordinate: 6 },
  pointMatches: () => true,
  positionKey: row => row[1] + "," + row[2],
});
vm.runInContext(source.slice(start, end) + "\nglobalThis.nodes = chronologyNodes({});", context);
assert.deepEqual(Array.from(context.nodes, node => node.id), [limited[0], field[0]].sort());
assert.equal(points.length, 3, "Duplicate remains in marker data for inspection");
assert.ok(context.nodes.some(node => node.id === limited[0]), "Limited evidence alone does not exclude a dated marker");

context.state.manifest = {};
vm.runInContext("nodes = chronologyNodes({});", context);
assert.equal(context.nodes.length, 3, "Old manifests retain their existing behavior");
context.state.manifest = { chronologyExcludedIds: [duplicate[0]] };
context.state.chronology.coordinateScope = "field";
vm.runInContext("nodes = chronologyNodes({});", context);
assert.deepEqual(Array.from(context.nodes, node => node.id), [field[0]]);
console.log("Crop chronology duplicate exclusions passed");

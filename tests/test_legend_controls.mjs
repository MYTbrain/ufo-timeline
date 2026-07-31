import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const legend = require("../webapp/static_public/legend_controls.js");

const available = ["disc_saucer", "triangle", "light"];
const all = legend.resetEventSelection("craft_type");
assert.deepEqual(all, {
  mode: "all",
  colorMode: "craft_type",
  selectedKeys: [],
});
assert.equal(legend.eventKeyActive(all, "disc_saucer"), true);

const isolated = legend.toggleEventKey(all, "disc_saucer", available);
assert.deepEqual(isolated, {
  mode: "subset",
  colorMode: "craft_type",
  selectedKeys: ["disc_saucer"],
});
assert.equal(legend.eventKeyActive(isolated, "disc_saucer"), true);
assert.equal(legend.eventKeyActive(isolated, "triangle"), false);

const additive = legend.toggleEventKey(isolated, "triangle", available);
assert.deepEqual(additive.selectedKeys, ["disc_saucer", "triangle"]);
assert.equal(additive.mode, "subset");

const removed = legend.toggleEventKey(additive, "disc_saucer", available);
assert.deepEqual(removed.selectedKeys, ["triangle"]);

const none = legend.toggleEventKey(removed, "triangle", available);
assert.deepEqual(none, {
  mode: "none",
  colorMode: "craft_type",
  selectedKeys: [],
});
assert.equal(legend.eventKeyActive(none, "triangle"), false);

const fromNone = legend.toggleEventKey(none, "light", available);
assert.deepEqual(fromNone.selectedKeys, ["light"]);

const allAgain = legend.toggleEventKey(
  { mode: "subset", colorMode: "craft_type", selectedKeys: ["disc_saucer", "triangle"] },
  "light",
  available,
);
assert.deepEqual(allAgain, all);

const militaryDefaults = { air: true, naval: true, army: true, other: false };
const isolateArmy = legend.toggleGroupedOverlay(false, militaryDefaults, "army", Object.keys(militaryDefaults));
assert.equal(isolateArmy.active, true);
assert.deepEqual(isolateArmy.visibility, { air: false, naval: false, army: true, other: false });

const addAir = legend.toggleGroupedOverlay(true, isolateArmy.visibility, "air", Object.keys(militaryDefaults));
assert.deepEqual(addAir.visibility, { air: true, naval: false, army: true, other: false });

const removeArmy = legend.toggleGroupedOverlay(true, addAir.visibility, "army", Object.keys(militaryDefaults));
assert.equal(removeArmy.active, true);
assert.deepEqual(removeArmy.visibility, { air: true, naval: false, army: false, other: false });

const removeLast = legend.toggleGroupedOverlay(true, removeArmy.visibility, "air", Object.keys(militaryDefaults));
assert.equal(removeLast.active, false);
assert.deepEqual(removeLast.visibility, { air: false, naval: false, army: false, other: false });

console.log("legend controls assertions passed");

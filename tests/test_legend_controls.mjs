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

// Craft swatches are independent toggles. In particular, toggling from `all`
// materializes the universe minus that one key instead of isolating it.
const craftAll = legend.createCraftSelectionState(all, available);
const triangleOff = legend.toggleCraftKey(craftAll, "triangle", available);
assert.deepEqual(triangleOff, {
  selection: {
    mode: "subset",
    colorMode: "craft_type",
    selectedKeys: ["disc_saucer", "light"],
  },
  solo: null,
});
assert.equal(legend.eventKeyActive(triangleOff.selection, "disc_saucer"), true);
assert.equal(legend.eventKeyActive(triangleOff.selection, "triangle"), false);
assert.equal(legend.eventKeyActive(triangleOff.selection, "light"), true);
assert.deepEqual(legend.toggleCraftKey(triangleOff, "triangle", available), craftAll);

// Label solo stores the exact prior selection. Moving the solo target retains
// that original restore point; clicking the active label restores it.
const priorSelection = {
  mode: "subset",
  colorMode: "craft_type",
  selectedKeys: ["light", "disc_saucer"],
};
const priorCraftState = legend.createCraftSelectionState(priorSelection, available);
const soloTriangle = legend.toggleCraftSolo(priorCraftState, "triangle", available);
assert.deepEqual(soloTriangle.selection, {
  mode: "subset",
  colorMode: "craft_type",
  selectedKeys: ["triangle"],
});
assert.deepEqual(soloTriangle.solo, {
  key: "triangle",
  restoreSelection: priorSelection,
  universeKeys: available,
});
assert.deepEqual(
  legend.normalizeCraftSelectionState(soloTriangle, available),
  soloTriangle,
  "ordinary duplicate-surface renders preserve a valid solo snapshot",
);

const soloLight = legend.toggleCraftSolo(soloTriangle, "light", available);
assert.deepEqual(soloLight.selection.selectedKeys, ["light"]);
assert.equal(soloLight.solo.key, "light");
assert.deepEqual(soloLight.solo.restoreSelection, priorSelection);
const restored = legend.toggleCraftSolo(soloLight, "light", available);
assert.deepEqual(restored, priorCraftState);

const soloFromAll = legend.toggleCraftSolo(craftAll, "disc_saucer", available);
assert.deepEqual(
  legend.toggleCraftSolo(soloFromAll, "disc_saucer", available),
  craftAll,
  "solo restores the exact all-mode selection",
);
const craftNone = legend.createCraftSelectionState(
  { mode: "none", colorMode: "craft_type", selectedKeys: [] },
  available,
);
const soloFromNone = legend.toggleCraftSolo(craftNone, "disc_saucer", available);
assert.deepEqual(
  legend.toggleCraftSolo(soloFromNone, "disc_saucer", available),
  craftNone,
  "solo restores the exact none-mode selection",
);

// A dot click while solo exits solo and toggles against the visible singleton,
// not against the saved pre-solo selection.
const dotDuringSolo = legend.toggleCraftKey(soloTriangle, "light", available);
assert.deepEqual(dotDuringSolo, {
  selection: {
    mode: "subset",
    colorMode: "craft_type",
    selectedKeys: ["triangle", "light"],
  },
  solo: null,
});
assert.deepEqual(legend.toggleCraftKey(soloTriangle, "triangle", available), craftNone);

// Every supported bulk action clears solo state.
assert.deepEqual(
  legend.applyCraftBulkSelection(soloTriangle, "all", available),
  craftAll,
);
assert.deepEqual(
  legend.applyCraftBulkSelection(soloTriangle, "none", available),
  craftNone,
);
assert.deepEqual(
  legend.applyCraftBulkSelection(soloTriangle, "invert", available),
  {
    selection: {
      mode: "subset",
      colorMode: "craft_type",
      selectedKeys: ["disc_saucer", "light"],
    },
    solo: null,
  },
);
assert.deepEqual(
  legend.applyCraftBulkSelection(soloTriangle, "reset", available),
  craftAll,
);

// Replacing the available-key universe always clears solo, removes stale keys,
// and canonicalizes a surviving full subset back to `all`.
assert.deepEqual(
  legend.replaceCraftSelectionUniverse(soloTriangle, ["disc_saucer", "light"]),
  {
    selection: {
      mode: "none",
      colorMode: "craft_type",
      selectedKeys: [],
    },
    solo: null,
  },
);
assert.deepEqual(
  legend.replaceCraftSelectionUniverse(priorCraftState, ["light", "disc_saucer"]),
  {
    selection: {
      mode: "all",
      colorMode: "craft_type",
      selectedKeys: [],
    },
    solo: null,
  },
);
assert.equal(
  legend.normalizeCraftSelectionState(soloTriangle, available.concat("unknown")).solo,
  null,
  "a changed key universe invalidates a stale solo snapshot",
);

// The pre-existing event-category helper retains its non-craft isolate behavior.
const nonCraftAll = legend.resetEventSelection("type");
assert.deepEqual(
  legend.toggleEventKey(nonCraftAll, "Nocturnal light", ["Nocturnal light", "Object"]),
  {
    mode: "subset",
    colorMode: "type",
    selectedKeys: ["Nocturnal light"],
  },
);

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

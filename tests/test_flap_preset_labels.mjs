import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const labels = require("../webapp/static_public/flap_preset_labels.js");

assert.equal(labels.formatMonthRange("1947-06-01", "1947-09-30"), "1947 Jun–Sep");
assert.equal(labels.formatMonthRange("1997-03-12", "1997-03-14"), "1997 Mar");
assert.equal(labels.formatMonthRange("1989-11-01", "1990-04-30"), "1989 Nov–90 Apr");
assert.equal(labels.formatMonthRange("1999-12-01", "2000-01-31"), "1999 Dec–2000 Jan");
assert.equal(labels.formatMonthRange("1896-11-01", "1897-06-30"), "1896 Nov\u201397 Jun");
assert.equal(labels.formatMonthRange("invalid", "1990-04-30"), "");

assert.equal(
  labels.formatPresetLabel({
    name: "Belgium Wave",
    startIso: "1989-11-01",
    endIso: "1990-04-30",
  }),
  "1989 Nov–90 Apr · Belgium Wave"
);
assert.equal(
  labels.formatPresetLabel({
    name: "Phoenix Lights",
    startIso: "1997-03-12",
    endIso: "1997-03-14",
  }),
  "1997 Mar · Phoenix Lights"
);
assert.equal(labels.formatPresetLabel({ label: "Fallback label" }), "Fallback label");
assert.equal(
  labels.formatPresetLabel({
    name: "Mystery Airship Wave",
    startIso: "1896-11-01",
    endIso: "1897-06-30",
  }),
  "1896 Nov\u201397 Jun \u00b7 Mystery Airship Wave"
);

const title = labels.formatPresetTitle({
  name: "Belgium Wave",
  startIso: "1989-11-01",
  endIso: "1990-04-30",
  description: "1989-1990 Belgium wave",
});
assert.match(title, /^1989 Nov–90 Apr · Belgium Wave/);
assert.match(title, /Exact window: 1989-11-01 through 1990-04-30\./);
assert.match(title, /1989-1990 Belgium wave/);

console.log("flap preset label assertions passed");

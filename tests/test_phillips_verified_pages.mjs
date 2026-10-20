import assert from "node:assert/strict";
import fs from "node:fs";
import {createRequire} from "node:module";
const require = createRequire(import.meta.url), References = require("../ufocat_references.js");
const fixtures = JSON.parse(fs.readFileSync(new URL("fixtures/ufocat_references.json", import.meta.url), "utf8"));
const book = "https://cufos.org/PDFs/books/Physical_Traces.pdf";
const sha256 = "e824270528264c2563df17f79540171dc216fb9be85968a5eb844ecb1b2be17b";
const title = "Ted Phillips - Physical Traces Associated with UFO Sightings (CUFOS, 1975) [TPhillips1]";
for (const fixture of fixtures.filter(x => Object.hasOwn(x, "verifiedPages"))) {
  const before = JSON.stringify(fixture.event);
  const entry = References.referenceEntries(fixture.event).find(x => x.sourceCode);
  if (fixture.verifiedPages) {
    const [printed, pdf] = fixture.verifiedPages;
    assert.equal(entry.catalogPrintedPage, printed);
    assert.equal(entry.catalogPdfPage, pdf);
    assert.equal(entry.catalogPdfSha256, sha256);
    assert.equal(entry.url, `${book}#page=${pdf}`);
    assert.ok(entry.text.includes(`printed p. ${printed}`));
    assert.ok(entry.text.includes(`PDF page ${pdf}`));
  } else {
    assert.equal(entry.catalogPrintedPage, undefined);
    assert.equal(entry.catalogPdfPage, undefined);
    assert.equal(entry.catalogPdfSha256, undefined);
    assert.equal(entry.url, book);
    assert.equal(entry.locatorType, "ambiguous_catalog_case_number_or_printed_page");
  }
  assert.equal(JSON.stringify(fixture.event), before);
}
for (const code of ["TPhillips", "TPhillips2", "TPhillips3"]) for (const number of [253, 537, 585]) {
  const entry = References.referenceEntries({source:"ufocat", raw_fields:{SOURCE:code,PAGEVOL:String(number)}})[0];
  assert.equal(entry.catalogPdfPage, undefined);
  assert.ok(!entry.url?.includes("#page="));
}
for (const number of [253, 537, 585]) {
  const indirect = References.referenceEntries({source:"ufocat", raw_fields:{ISOURCE:"TPhillips1",IPAGEVOL:String(number)}})[0];
  assert.equal(indirect.catalogPdfPage, undefined);
  assert.equal(indirect.url, book);
  const event = {source:"ufocat", date_iso:"1972-09-14", time_raw:"2000", lat:37.3, lon:-91.9,
    raw_fields:{SOURCE:"TPhillips1",PAGEVOL:String(number)}};
  const newEntry = References.referenceEntries(event)[0], legacy = `${title}, case ${number} (direct citation)`;
  const arbitrary = `${legacy} - researcher note`;
  for (const originals of [[legacy], [legacy,newEntry.text], [newEntry.text,legacy], ["Original source",legacy,arbitrary,legacy]]) {
    const current = {...event,references:originals}, before = JSON.stringify(current);
    const entries = References.referenceEntries(current), texts = References.references(current);
    assert.deepEqual(entries.filter(x => x.sourceCode), [newEntry]);
    assert.ok(!texts.includes(legacy));
    assert.equal(texts.filter(x => x === newEntry.text).length, 1);
    for (const original of originals) if (![legacy,newEntry.text].includes(original)) assert.ok(texts.includes(original));
    assert.equal(JSON.stringify(current), before);
    assert.deepEqual(References.referenceEntries({...current,references:texts}), entries);
  }
  assert.deepEqual(References.referenceEntries({source:"majestic",references:[legacy],raw_fields:event.raw_fields}),
    [{text:legacy,citationRole:"existing"}], "Existing text alone does not establish source ownership");
}
const unreviewed = References.referenceEntries({source:"ufocat",raw_fields:{SOURCE:"TPhillips1",PAGEVOL:"494"}})[0];
assert.equal(unreviewed.catalogPdfPage, undefined);
assert.equal(unreviewed.url, book);
console.log("Verified Phillips pages: three fixed direct locators, indirect/other-source guards, exact legacy upgrade and reference preservation passed");

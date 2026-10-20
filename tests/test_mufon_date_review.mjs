import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import {createRequire} from "node:module";
import {fileURLToPath} from "node:url";
const require = createRequire(import.meta.url);
const Review = require("../mufon_date_review.js");
const root = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const fixtures = JSON.parse(fs.readFileSync(path.join(root,"docs/qa/mufon-date-review-20261019/fixtures.json"),"utf8"));
assert.equal(fixtures.length,5);
assert.equal(Review.TARGETS.length,5);
assert.equal(Object.isFrozen(Review.TARGETS),true);
const nullFields = ["date_iso","end_date_iso","sort_date_iso","sort_ordinal","sort_date_key","sort_time_ms",
  "parsed_time_local_minutes","parsed_time_local_range_start_minutes","parsed_time_local_range_end_minutes",
  "estimated_utc_timestamp_ms","estimated_utc_range_start_ms","estimated_utc_range_end_ms","time_bucket_label","resolved_timezone","playback_sort_key"];
for (const fixture of fixtures) {
  const target = Review.TARGETS.find(value => value.event_id === fixture.event_id);
  assert.equal(target.canonical_event_id,fixture.canonical_event_id);
  assert.equal(target.chunk_id,fixture.chunk_id);
  assert.equal(target.detail_index,fixture.detail_index);
  assert.equal(Review.isTargetId(fixture.event_id),true);
  assert.equal(Review.isTargetId(String(fixture.event_id)),true);
  for (const [key,value] of Object.entries(fixture.source_guard)) {
    if (key !== "source_name") assert.equal(target[key],value);
  }
  for (const lane of ["summary","detail"]) {
    const original = fixture[lane], before = JSON.stringify(original), result = Review.apply(original);
    assert.notEqual(result,original,`${lane} corrected for MUFON ${fixture.source_native_id}`);
    assert.equal(JSON.stringify(original),before,"Original report stays unchanged");
    assert.equal(result.date_precision,"unknown");
    assert.equal(result.exact_day_eligible,false);
    for (const key of nullFields) assert.equal(result[key],null,`${key} cannot retain chronology from unverified day`);
    assert.equal(result.time_sort_kind,"unknown");
    assert.equal(result.time_sort_confidence,"none");
    assert.equal(result.timezone_source,"unknown");
    assert.equal(result.timezone_confidence,"none");
    assert.equal(result.playback_sort_confidence,"none");
    assert.equal(result.playback_sort_reason,"unverified_source_date");
    assert.equal(result.date_review.review_id,Review.REVIEW_ID);
    assert.equal(result.date_review.status,"unverified_source_date");
    assert.equal(result.date_review.reason,"The source date 1890-04-01 conflicts with the account or lacks occurrence-date support; no replacement occurrence date is established.");
    for (const key of ["event_id","canonical_event_id","date_raw","time_raw","reported_date_raw","raw_fields","raw_source_row",
      "raw_event_block","description","source_id","source_provenance","lat","lon","coordinate_source","location_precision"]) {
      assert.equal(result[key],original[key],`${key} source content or identity is preserved`);
    }
    assert.equal(Review.apply(result),result,"Applied review is idempotent");
    assert.equal(Review.displayDate(result,"1890-04-01"),"Date unverified");
    for (const change of [
      {event_id:99999},{event_id:"343118950126607.0"},{source:"nuforc"},{source_name:"nuforc"},
      {chunk_id:"chunk_000999"},{detail_index:original.detail_index+1},{detail_index:String(original.detail_index)},
      {date_raw:"1890-04-02"},{date_iso:"2009-08-22"},{sort_date_iso:"2008-04-01"},{end_date_iso:"1900-01-01"},
      {canonical_event_id:"evt_ffffffffffffffffffffffff"},{source_file:"different.csv"},
      {source_id:"99999"},{source_native_id:"99999"},{canonical_input_ids:[]},
      {source_row_number:99999},{source_row_hash:"f".repeat(40)},{canonical_input_id:"cin_ffffffffffffffffffffffff"},
      {source_provenance:[]},{source_provenance:"not an array"},
      {raw_fields:{No:"99999"}},{raw_source_row:{No:"99999"}},
    ]) {
      const stale = {...original,...change};
      assert.equal(Review.apply(stale),stale,"Stale or contradictory identity/date is not overwritten");
    }
    const future = {...result,date_iso:"1984-01-01",sort_date_iso:"1984-01-01",date_precision:"exact_day"};
    assert.equal(Review.apply(future),future,"Future date correction wins even if old review remains");
    assert.equal(Review.displayDate(future,"1984-01-01"),"1984-01-01");
    const stripped = {...original}; delete stripped.chunk_id;
    assert.equal(Review.apply(stripped),stripped,"Identity alone cannot bypass current catalog locator");
  }
  for (const field of ["source_name","source_file","source_native_id","source_row_number","source_row_hash","canonical_input_id"]) {
    const stale = JSON.parse(JSON.stringify(fixture.detail));
    stale.source_provenance[0][field] = field === "source_row_number" ? 1 : "wrong";
    assert.equal(Review.apply(stale),stale,`Source provenance ${field} mismatch fails closed`);
  }
  const packed = Object.fromEntries(["event_id","source","chunk_id","detail_index","sort_date_iso","date_precision","lat","lon","has_coordinates"]
    .filter(key => Object.hasOwn(fixture.summary,key)).map(key => [key,fixture.summary[key]]));
  const before = JSON.stringify(packed), result = Review.applyPacked(packed);
  assert.notEqual(result,packed,"Actual packed projection shape receives the same reviewed date state");
  assert.equal(JSON.stringify(packed),before,"Packed projection is not mutated");
  assert.equal(Object.hasOwn(result,"date_raw"),false,"Packed correction does not invent an absent raw date");
  assert.equal(Object.hasOwn(result,"source_id"),false,"Packed correction does not invent native identity fields");
  for (const key of nullFields) assert.equal(result[key],null);
  assert.equal(result.date_precision,"unknown");
  assert.equal(result.exact_day_eligible,false);
  assert.equal(Review.applyPacked(result),result,"Packed correction is idempotent");
  assert.equal(Review.displayDate(result,"1890-04-01"),"Date unverified");
  assert.equal(Review.apply(packed),packed,"Normal apply does not infer missing raw-date support");
  for (const change of [{event_id:99999},{source:"nuforc"},{chunk_id:"chunk_000999"},{detail_index:packed.detail_index+1},
    {sort_date_iso:"2009-08-22"},{sort_date_iso:null},{date_iso:"1984-01-01"},{end_date_iso:"1984-01-02"},{date_raw:"1900-01-01"}]) {
    const stale = {...packed,...change};
    assert.equal(Review.applyPacked(stale),stale,"Packed correction rejects stale row pins or another date");
  }
  const futurePacked = {...result,sort_date_iso:"1984-01-01",date_precision:"exact_day"};
  assert.equal(Review.applyPacked(futurePacked),futurePacked,"Future packed date correction wins over old review");
  assert.equal(Review.displayDate(futurePacked,"1984-01-01"),"1984-01-01");
  const compact = {...Review.apply(fixture.summary)};
  for (const key of ["source_id","source_native_id","canonical_event_id","source_provenance"]) delete compact[key];
  assert.equal(Review.displayDate(compact,"1890-04-01"),"Date unverified","Compacted summaries retain the reviewed date label");
  const rebuilt = {...compact,event_id:99999,chunk_id:"chunk_999999",detail_index:123};
  assert.equal(Review.apply(rebuilt),rebuilt,"Canonical display metadata does not relax correction identity guards");
  assert.equal(Review.displayDate(rebuilt,"1890-04-01"),"Date unverified","Canonical review label survives rebuilt locators and deduplicated IDs");
  const rebuiltSparse = {...rebuilt};
  for (const key of ["date_iso","end_date_iso","sort_date_iso"]) delete rebuiltSparse[key];
  assert.equal(Review.displayDate(rebuiltSparse,"1890-04-01"),"Date unverified","Missing normalized dates also preserve the canonical review label");
  for (const change of [{date_iso:"1984-01-01"},{end_date_iso:"1984-01-01"},{sort_date_iso:"1984-01-01"},
    {source:"nuforc"},{date_raw:"1900-01-01"},{date_precision:"exact_day"},{date_review:{review_id:"other-review",status:"unverified_source_date"}}]) {
    assert.equal(Review.displayDate({...rebuilt,...change},"Supported replacement"),"Supported replacement","Canonical label requires supported review metadata and no replacement date");
  }
}
for (const invalidId of [null,undefined,"99999","343118950126607.0",{},Number.MAX_SAFE_INTEGER+1]) assert.equal(Review.isTargetId(invalidId),false);
for (const unrelated of [null,[],"1890-04-01",{event_id:123,source:"mufon",date_raw:"1890-04-01",date_iso:"1890-04-01"}]) {
  assert.equal(Review.apply(unrelated),unrelated,"No blanket historical date replacement");
}
assert.equal(Review.displayDate({date_raw:"1890-04-01"}),"1890-04-01");
assert.equal(Review.displayDate({},"custom date"),"custom date");
assert.equal(Review.displayDate(null),"Unknown date");
const browser = vm.createContext({});
vm.runInContext(fs.readFileSync(path.join(root,"mufon_date_review.js"),"utf8"),browser);
for (const fixture of fixtures) assert.deepEqual(JSON.parse(JSON.stringify(browser.UfoMufonDateReview.apply(fixture.detail))),Review.apply(fixture.detail));
console.log("MUFON occurrence-date review: all five actual summary/detail pairs, nonmutation, idempotence, source guards, chronology reset, future corrections and browser parity passed");

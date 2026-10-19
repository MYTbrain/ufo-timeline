import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { readFile } from "node:fs/promises";
import vm from "node:vm";
const require = createRequire(import.meta.url);
const Search = require("../search_query.js");
const compile = Search.compile;

const literal = compile("  Soil Collection  ");
assert.equal(literal.mode, "literal");
assert(Search.matches(literal, "A SOIL COLLECTION was reported."));
assert(!Search.matches(literal, "Soil and plant collection"), "plain search preserves a contiguous substring");
assert(!Search.matches(literal, "soil  collection"), "interior whitespace retains exact legacy meaning");
assert(Search.matches(compile("soil"), "Topsoil"), "substring matches are not whole-word-only matches");
assert.equal(compile("Washington (DC)").mode, "literal", "parentheses alone do not change existing searches");
assert(Search.matches(compile("soil and plant"), "SOIL AND PLANT"), "lowercase prose is not an implicit operator");
assert.equal(compile("soil OR plant").ast.type, "or");
assert(Search.matches(compile("soil OR plant"), "plant"));
assert(!Search.matches(compile("soil AND plant"), "soil only"));
assert(Search.matches(compile("soil AND plant"), "A plant was placed in topsoil"));
assert(Search.matches(compile("soil OR plant AND grey"), "soil"), "AND binds before OR");
assert(!Search.matches(compile("soil OR plant AND grey"), "plant only"));
assert(!Search.matches(compile("(soil OR plant) AND grey"), "soil only"));
assert(Search.matches(compile("(soil OR plant) AND grey"), "grey plant"));
assert(Search.matches(compile('"soil sample" AND (grey OR humanoid)'), "A humanoid collected a soil sample"));
assert(!Search.matches(compile('"soil sample"'), "soil and sample"));
assert(Search.matches(compile("soil sample AND grey"), "grey soil sample"), "unquoted text between explicit operators is one substring");
assert(!Search.matches(compile("soil sample AND grey"), "soil grey sample"));
assert(Search.matches(compile('"said \\"hello\\""'), 'Someone said "hello"'));
assert(Search.matches(compile('"C:\\\\Reports"'), "C:\\Reports\\Case"));
assert(Search.matches(compile("AND", {mode:"literal"}), "sand"), "literal mode allows reserved operator text");
assert(Search.matches(compile("soil grey", {mode:"all"}), "grey topsoil"));
assert(!Search.matches(compile("soil grey", {mode:"all"}), "grey"));
assert(Search.matches(compile('"soil sample" grey', {mode:"any"}), "grey"));
assert(!Search.matches(compile('"soil sample" grey', {mode:"any"}), "soil"));
assert.equal(compile("").isEmpty, true);
assert(Search.matches(compile("  "), "anything"));
assert.equal(compile("SOIL").cacheKey, compile('"soil"').cacheKey, "semantic equivalents share a stable cache key");
assert(Object.isFrozen(literal));
assert(Object.isFrozen(literal.ast));
assert(Object.isFrozen(literal.candidate.grams));

for (const [query, code] of [
  ['"soil', "unclosed_quote"], ['""', "empty_phrase"], ["AND soil", "missing_term"],
  ["soil OR", "missing_term"], ["soil OR OR plant", "missing_term"],
  ['"soil" "plant"', "missing_operator"], ['"soil" plant', "missing_operator"],
  ["(soil OR plant", "unclosed_group"], ["soil OR plant)", "unmatched_group"],
  ['"soil\\q"', "invalid_escape"], ["x".repeat(513), "too_long"],
  [Array(33).fill("soil").join(" OR "), "too_many_clauses"],
  ["(".repeat(13) + "soil OR plant" + ")".repeat(13), "too_deep"],
]) {
  assert.throws(() => compile(query), error => error.name === "SearchQueryError" && error.code === code &&
    Number.isInteger(error.position) && error.message.length > 10, query);
}
assert.throws(() => compile("soil", {mode:"fuzzy"}), /supported search mode/);

const event = {raw_event_block:"Raw soil",description:"Description",time_display:"21:00",location_display:"Harare",
  location_raw:"Zimbabwe",duration_display:"5 minutes",references:["First reference", "Second reference"],
  source:"archive",mapping_notes:"Approximate",extra_data:{observer:"Smith"},parse_warnings:["missing time zone"]};
const serialized = [event.raw_event_block,event.description,event.time_display,event.location_display,event.location_raw,
  event.duration_display,event.references.join("\n"),event.source,event.mapping_notes,JSON.stringify(event.extra_data),
  JSON.stringify(event.parse_warnings)].join("\n").toLowerCase();
assert.equal(Search.serializeEvent(event), serialized, "same searchable fields, field order, JSON serialization and separator as legacy");
assert(Search.matchEvent(compile('"first reference" AND smith AND approximate'), event));
assert(Search.matchEvent(compile('"harare\\\\nZimbabwe"', {mode:"literal"}), event) === false);
assert(Search.matchEvent(compile("Harare\nZimbabwe"), event), "legacy cross-field substrings still match");
assert(Search.matchEvent(compile("missing time zone"), event), "parse warnings remain searchable");
assert(!Search.matchEvent(compile("shape-only"), {shape:"shape-only"}), "fields not in legacy serialization are not silently added");

const safe = '<script>alert("soil")</script> Plant & SOIL';
const highlighted = Search.highlightSegments(compile("soil OR plant"), safe);
assert.equal(highlighted.map(x => x.text).join(""), safe);
assert.deepEqual(highlighted.filter(x => x.match).map(x => x.text), ["soil", "Plant", "SOIL"]);
assert(!highlighted.some(x => "html" in x), "highlight output is data for text nodes, not HTML markup");
const overlap = Search.highlightSegments(compile("soil OR topsoil"), "topsoil");
assert.deepEqual(overlap, [{text:"topsoil",match:true}], "overlapping matches are merged");
assert.deepEqual(Search.highlightSegments(compile("aa"), "aaa"), [{text:"aaa",match:true}], "overlapping occurrences remain highlighted");
assert.deepEqual(Search.highlightSegments(compile("i"), "İstanbul"), [{text:"İ",match:true},{text:"stanbul",match:false}], "Unicode case expansion preserves source offsets");
assert.deepEqual(Search.highlightSegments(compile("plant"), "😀Plant🌱"), [{text:"😀",match:false},{text:"Plant",match:true},{text:"🌱",match:false}]);
const longText = "x".repeat(300) + " Soil sample " + "y".repeat(300);
const snippet = Search.excerpt(compile('"soil sample"'), longText, {maxLength:100});
assert.equal(snippet.text.length, 100);
assert(snippet.leadingEllipsis && snippet.trailingEllipsis && snippet.matched);
assert.equal(snippet.segments.map(x=>x.text).join(""), snippet.text);
assert.equal(snippet.text, longText.slice(snippet.start, snippet.end));
assert.equal(Search.excerpt(compile("unmatched"), "ordinary report").matched, false);
const longPhrase = "soil " + "collection ".repeat(35);
const partialPhrase = Search.excerpt(compile(longPhrase), "before " + longPhrase + " after", {maxLength:100});
assert(partialPhrase.matched, "a clipped excerpt of a long exact phrase still highlights its visible match");
assert.equal(partialPhrase.segments.map(x=>x.text).join(""), partialPhrase.text);

// A candidate gram can only narrow an exact substring term if its Boolean branch
// is respected. One/two-character terms deliberately emit no restrictive grams.
function candidateMatch(node, text) {
  if (!node) return true;
  if (node.type === "term") return node.grams.every(gram => text.includes(gram));
  return node.type === "and" ? node.children.every(child => candidateMatch(child,text)) :
    node.children.some(child => candidateMatch(child,text));
}
const alphabet = ["soil","topsoil","plant","grey","😀","İ","a","OR","<tag>","harare\nZimbabwe"];
for (const term of alphabet) {
  for (const plan of [compile(term,{mode:"literal"}), compile('"' + term + '" OR "ab"'), compile('"' + term + '" AND "soil"')]) {
    for (const text of [term,"prefix" + term + "suffix","soil " + term,"soil", "ab", "different"]) {
      if (Search.matches(plan,text)) assert(candidateMatch(Search.candidateTokens(plan),text.toLowerCase()), "index prefilter must not exclude a true match");
    }
  }
}
assert.deepEqual(compile("ab").candidate.grams, []);
assert.deepEqual(Search.tokenize("Soil topsoil SOIL — İ / grey_being 123"), ["soil","topsoil","i̇","grey_being","123"]);
assert.deepEqual(Search.wordParts("soil/sample soil"), ["soil","sample","soil"]);
assert(Search.isWordFragment("topsoil"));
assert(!Search.isWordFragment("soil sample"));
assert(!Search.isWordFragment("😀"));
const context = {globalThis:{}};
vm.runInNewContext(await readFile(new URL("../search_query.js", import.meta.url), "utf8"), context);
assert(context.globalThis.UfoSearchQuery.matches(context.globalThis.UfoSearchQuery.compile("soil"), "topsoil"), "browser global is available without a module system");
console.log("Search query parser, exact matching, safe excerpts and conservative candidates passed.");

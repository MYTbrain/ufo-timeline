import assert from "node:assert/strict";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url), View = require("../search_view.js");
class Element {
  constructor(tagName, ownerDocument) {
    this.tagName = tagName; this.ownerDocument = ownerDocument; this.children = []; this.attributes = new Map();
    this.events = new Map(); this.ownText = ""; this.value = ""; this.hidden = false; this.disabled = false;
  }
  appendChild(element) { this.children.push(element); element.parentNode = this; return element; }
  append(...elements) { elements.forEach(element => this.appendChild(element)); }
  replaceChildren(...elements) { this.children.forEach(element => { element.parentNode = null; }); this.children = []; this.ownText = ""; this.append(...elements); }
  removeChild(element) { this.children = this.children.filter(child => child !== element); element.parentNode = null; return element; }
  set textContent(value) { this.ownText = String(value); this.children = []; }
  get textContent() { return this.ownText + this.children.map(child => child.textContent).join(""); }
  setAttribute(key, value) { this.attributes.set(key, String(value)); }
  getAttribute(key) { return this.attributes.get(key) ?? null; }
  removeAttribute(key) { this.attributes.delete(key); }
  addEventListener(name, callback) { if (!this.events.has(name)) this.events.set(name, []); this.events.get(name).push(callback); }
  dispatch(name) { return Promise.all((this.events.get(name) || []).map(callback => callback({ target: this, currentTarget: this }))); }
  click() { return this.disabled ? Promise.resolve() : this.dispatch("click"); }
  set innerHTML(value) { throw new Error("Unsafe HTML must never be used: " + value); }
}
const walk = element => [element, ...element.children.flatMap(walk)];
const byClass = (target, cls) => walk(target).find(element => (element.className || "").split(" ").includes(cls));
const byText = (target, tag, text) => walk(target).find(element => element.tagName === tag && element.textContent === text);
function fixture(config = {}) {
  const document = { createElement(tag) { return new Element(tag, this); } }, target = document.createElement("div");
  const view = View.create(target, config); return { target, view };
}
const actions = [], retries = [], { target, view } = fixture({
  onRetry: payload => retries.push(payload), onUseSelection: payload => actions.push({ action: "use", ...payload }),
  onHoldSelection: payload => actions.push({ action: "hold", ...payload }),
});
const coverage = byClass(target, "search-coverage"), actionBox = byClass(target, "search-selection-actions"),
  use = byText(target, "button", "Use in Analysis"), pinA = byText(target, "button", "Hold as A"),
  pinB = byText(target, "button", "Hold as B"), retry = byText(target, "button", "Retry missing data");
assert.equal(coverage.hidden, true, "empty search adds no coverage panel");
assert.equal(actionBox.hidden, true);
assert.equal(byClass(target, "search-tips").open, undefined, "search tips start collapsed");
assert.match(target.textContent, /AND must be uppercase|AND and OR must be uppercase/);
view.setState({ query: '"soil sample" AND humanoid', status: "searching", complete: false, completedChunks: 7, totalChunks: 10,
  scannedReports: 700, totalReports: 1000, matchCount: 12 });
assert.equal(coverage.hidden, false);
assert.match(coverage.textContent, /12 matches so far/);
assert.match(coverage.textContent, /7 \/ 10 full text chunks checked/);
assert.match(coverage.textContent, /700 \/ 1,000 reports checked/);
assert.equal(byClass(target, "search-coverage-progress").value, .7);
assert.equal(use.disabled, true);
await use.click(); assert.equal(actions.length, 0, "partial cohorts cannot be captured");
view.setState({ status: "partial", completedChunks: 9, message: "One data file could not be checked." });
assert.equal(retry.hidden, false);
assert.match(coverage.textContent, /incomplete/);
await retry.click(); assert.deepEqual(retries, [{ query: '"soil sample" AND humanoid' }]);
view.setState({ status: "complete", complete: false });
assert.match(coverage.textContent, /incomplete/, "status alone must not claim complete coverage");
view.setState({ status: "complete", complete: true });
assert.equal(use.disabled, true, "declared complete cannot override missing chunks");
view.setState({ completedChunks: 10, scannedReports: 1000, matchCount: 28, canUseSelection: true, message: "" });
assert.match(coverage.textContent, /28 matching reports/);
assert.doesNotMatch(coverage.textContent, /incomplete/);
assert.equal(retry.hidden, true); assert.equal(use.disabled, false);
assert.match(byClass(target, "search-scope-note").textContent, /includes unmapped reports\. Drawn areas are not applied/);
await use.click(); await pinA.click();
assert.deepEqual(actions, [
  { action: "use", query: '"soil sample" AND humanoid', scope: "current" },
  { action: "hold", query: '"soil sample" AND humanoid', scope: "current", slot: "A" },
], "actions describe all results in their declared scope, with current filters as default");
byClass(target, "search-selection-scope").value = "all";
await byClass(target, "search-selection-scope").dispatch("change");
assert.match(byClass(target, "search-scope-note").textContent, /across dates and categories/);
await pinB.click();
assert.deepEqual(actions.at(-1), { action: "hold", query: '"soil sample" AND humanoid', scope: "all", slot: "B" });
view.setState({ matchCount: 0 }); assert.equal(actionBox.hidden, true);
view.setState({ query: "humanoid", status: "partial", complete: false, summaryOnly: true, matchCount: 8, message: "" });
assert.match(coverage.textContent, /Only loaded summaries were checked/);
assert.equal(use.disabled, true); assert.equal(retry.hidden, false);
view.setState({ status: "complete", complete: true, completedChunks: 10 });
assert.equal(use.disabled, true, "summary-only results cannot become full-text cohorts by status alone");
view.setState({ summaryOnly: false, canUseSelection: false });
assert.equal(use.disabled, true, "runtime readiness gate is respected even after search completion");
view.setState({ query: "", status: "idle" }); assert.equal(coverage.hidden, true);

const unsafe = fixture();
unsafe.view.setState({ query: "<img onerror=alert(1)>", status: "partial", matchCount: 2, message: "<script>unsafe</script>" });
assert.match(unsafe.target.textContent, /<script>unsafe<\/script>/, "failure messages remain plain text");
assert.equal(walk(unsafe.target).filter(element => element.tagName === "script" || element.tagName === "img").length, 0);
assert.equal(byClass(unsafe.target, "search-selection-actions").hidden, true, "optional actions do not create dead controls");

const excerptTarget = target.ownerDocument.createElement("p");
View.renderExcerpt(excerptTarget, { label: "Full text match", segments: [
  { text: "Reported " }, { text: "soil sample", match: true }, { text: " <img src=x onerror=alert(1)>" },
] });
assert.equal(excerptTarget.hidden, false);
assert.equal(walk(excerptTarget).filter(element => element.tagName === "mark").length, 1);
assert.equal(byText(excerptTarget, "mark", "soil sample").textContent, "soil sample");
assert.match(excerptTarget.textContent, /<img src=x onerror=alert\(1\)>/);
assert.equal(walk(excerptTarget).filter(element => element.tagName === "img").length, 0);
View.renderExcerpt(excerptTarget, { segments: [] }); assert.equal(excerptTarget.hidden, true);
assert.equal(excerptTarget.textContent, "");

let rejectOld;
const stale = fixture({ onUseSelection: () => new Promise((resolve, reject) => { rejectOld = reject; }) });
stale.view.setState({ query: "plants", status: "complete", complete: true, matchCount: 2, canUseSelection: true });
const oldAction = byText(stale.target, "button", "Use in Analysis").click();
stale.view.setState({ query: "water", status: "searching", complete: false });
rejectOld(new Error("Old selection failed")); await oldAction;
assert.equal(byClass(stale.target, "search-action-status").textContent, "", "old actions cannot report errors over a newer search");
const success = fixture({ onHoldSelection: () => ({ message: "Held 2 reports as A." }) });
success.view.setState({ query: "plants", status: "complete", complete: true, matchCount: 2, canUseSelection: true });
await byText(success.target, "button", "Hold as A").click();
assert.equal(byClass(success.target, "search-action-status").textContent, "Held 2 reports as A.");
const stateCopy = view.getState(); stateCopy.query = "mutated"; assert.notEqual(view.getState().query, "mutated");
view.destroy(); assert.equal(target.children.length, 0); view.setState({ query: "ignored" });
console.log("Search view: truthful coverage, complete-only captures, scopes, safe excerpts, stale action and empty states passed.");

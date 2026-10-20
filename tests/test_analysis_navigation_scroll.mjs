import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";

// Run the actual navigation installer. A focused topic can remain below the
// viewport while chart results mutate; those updates must not reclaim the
// reader's page position. Explicit navigation must still reveal its heading.
const frames = [], mutations = [], resizes = [], pageScrolls = [], windowEvents = new Map();
class Element {
  constructor(tagName) {
    Object.assign(this, { tagName: tagName.toUpperCase(), children: [], attributes: new Map(),
      events: new Map(), dataset: {}, scrollTop: 0, offsetHeight: 600, textContent: "" });
    const classes = new Set();
    this.classList = { add: value => classes.add(value), remove: value => classes.delete(value),
      contains: value => classes.has(value), toggle(value, force) {
        const next = force ?? !classes.has(value); if (next) classes.add(value); else classes.delete(value); return next;
      } };
    const properties = new Map();
    this.style = { writes: 0, getPropertyValue: name => properties.get(name) || "",
      setProperty(name, value) { this.writes++; properties.set(name, value); } };
  }
  append(...nodes) { nodes.forEach(node => this.appendChild(node)); }
  appendChild(node) {
    if (node.parentElement) node.parentElement.children = node.parentElement.children.filter(child => child !== node);
    node.parentElement = this; this.children.push(node); return node;
  }
  before(node) { this.parentElement.insertBefore(node, this); }
  after(node) { this.parentElement.insertBefore(node, this.parentElement.children[this.parentElement.children.indexOf(this) + 1]); }
  insertBefore(node, next) {
    if (node.parentElement) node.parentElement.children = node.parentElement.children.filter(child => child !== node);
    node.parentElement = this; const index = this.children.indexOf(next);
    if (index < 0) this.children.push(node); else this.children.splice(index, 0, node);
  }
  insertAdjacentElement(position, node) { assert.equal(position, "afterend"); this.after(node); }
  get previousSibling() { return this.parentElement?.children[this.parentElement.children.indexOf(this) - 1]; }
  setAttribute(key, value) { this.attributes.set(key, String(value)); }
  getAttribute(key) { return this.attributes.get(key) ?? null; }
  removeAttribute(key) { this.attributes.delete(key); }
  addEventListener(type, fn) { if (!this.events.has(type)) this.events.set(type, []); this.events.get(type).push(fn); }
  dispatch(type, event = {}) { event.target ??= this; (this.events.get(type) || []).forEach(fn => fn(event)); }
  closest(selector) { return selector === '[role="tab"]' && this.getAttribute("role") === "tab" ? this : null; }
  querySelector(selector) {
    return walk(this).slice(1).find(node => selector === '.analysis-section[aria-hidden="false"]'
        ? (node.className || "").split(" ").includes("analysis-section") && node.getAttribute("aria-hidden") === "false"
        : selector.startsWith(".") ? (node.className || "").split(" ").includes(selector.slice(1))
        : selector === '[aria-selected="true"]' ? node.getAttribute("aria-selected") === "true"
        : false) || null;
  }
  getBoundingClientRect() { return { top: 200, bottom: 1200 }; }
}
const walk = node => [node, ...node.children.flatMap(walk)];
const html = new Element("html"), body = new Element("body"); html.append(body);
html.dataset.activePrimaryView = "analysis";
const doc = { readyState: "complete", documentElement: html, body, activeElement: null,
  createElement: tag => new Element(tag), createComment: () => new Element("comment"),
  getElementById: id => walk(html).find(node => node.id === id) || null,
  querySelector(selector) { return html.querySelector(selector); }, addEventListener() {} };
const create = (id, parent = body, className = "") => {
  const node = new Element("div"); node.id = id; node.className = className; parent.append(node); return node;
};
const panel = create("analysis-panel"), header = create("analysis-header", panel, "analysis-header");
const toolbar = create("analysis-workspace-toolbar", panel);
let toolbarHeight = 120;
toolbar.getBoundingClientRect = () => ({ top: 20, bottom: 20 + toolbarHeight, height: toolbarHeight });
const nav = create("analysis-section-nav", panel), topic = create("analysis-section-tab-overview", nav);
topic.setAttribute("role", "tab"); topic.setAttribute("aria-selected", "true");
let topicBottom = 500, headingTop = 600;
topic.getBoundingClientRect = () => ({ top: topicBottom - 38, bottom: topicBottom });
const content = create("analysis-content", panel);
const section = create("analysis-section-overview", content, "analysis-section");
section.setAttribute("aria-hidden", "false");
const heading = create("heading", section, "analysis-section-heading");
heading.getBoundingClientRect = () => ({ top: headingTop, bottom: headingTop + 40 });
create("filters-pane-shell"); create("toggle-filters-pane");
const context = { document: doc, innerWidth: 1280, innerHeight: 800, scrollY: 0, Intl,
  requestAnimationFrame: fn => frames.push(fn),
  MutationObserver: class { constructor(fn) { mutations.push(fn); } observe() {} },
  ResizeObserver: class { constructor(fn) { this.fn = fn; } observe(target) { resizes.push({ target, fn: this.fn }); } },
  scrollTo(options) { pageScrolls.push(options); context.scrollY = options.top; },
  addEventListener(type, fn) { if (!windowEvents.has(type)) windowEvents.set(type, []); windowEvents.get(type).push(fn); } };
context.window = context;
vm.runInNewContext(fs.readFileSync("ui/accepted-workspace/analysis-navigation.js", "utf8"), context);
const flush = () => { let budget = 20; while (frames.length && budget--) frames.shift()(); assert.ok(budget > 0); };
assert.equal(mutations.length, 1);
assert.equal(pageScrolls.length, 0);

// Simulate scrolling down while focus remains on the last clicked topic.
context.scrollY = 900; doc.activeElement = topic; topicBottom = 1088;
for (let i = 0; i < 3; i++) { mutations[0]([]); flush(); }
assert.equal(context.scrollY, 900, "Chart mutations must leave the reader's outer scroll position unchanged");
assert.equal(pageScrolls.length, 0, "Observer synchronization must never scroll the outer page");

// Native clicks (including a mobile topic selector forwarding tab.click()) and
// keyboard navigation still use the deliberate heading reveal path.
nav.dispatch("click", { target: topic }); flush();
assert.equal(context.scrollY, 1348);
context.scrollY = 1200; headingTop = -100;
nav.dispatch("keydown", { target: topic, key: "ArrowDown" }); flush();
assert.equal(context.scrollY, 948);
const deliberateScrolls = pageScrolls.length;
mutations[0]([]); flush();
assert.equal(pageScrolls.length, deliberateScrolls, "A subsequent render must not override intentional navigation");

// Landscape phones must be able to scroll a tall toolbar out of the way.
const beforeResizeScroll = context.scrollY;
context.innerWidth = 844; context.innerHeight = 390; toolbarHeight = 252.9;
windowEvents.get("resize").forEach(fn => fn()); flush();
assert.equal(panel.classList.contains("has-flowing-toolbar"), true);
assert.equal(context.scrollY, beforeResizeScroll, "Changing toolbar layout must not move the outer page");
context.scrollY = 500; headingTop = 300;
nav.dispatch("click", { target: topic }); flush();
assert.equal(context.scrollY, 788, "A flowing toolbar must not reserve its offscreen height when revealing a topic");

// Return to an ordinary laptop; growing the toolbar also triggers the same
// measured fallback without requiring a viewport resize.
context.innerWidth = 1280; context.innerHeight = 720; toolbarHeight = 157;
windowEvents.get("resize").forEach(fn => fn()); flush();
assert.equal(panel.classList.contains("has-flowing-toolbar"), false);
assert.equal(panel.style.getPropertyValue("--analysis-toolbar-offset"), "177px");
const toolbarResize = resizes.find(entry => entry.target === toolbar).fn;
toolbarHeight = 500; toolbarResize([]); flush();
assert.equal(panel.classList.contains("has-flowing-toolbar"), true, "Expanded controls must preserve a usable reading area");
toolbarHeight = 157; toolbarResize([]); flush();
assert.equal(panel.classList.contains("has-flowing-toolbar"), false, "Compact controls restore the sticky toolbar");
const stableWrites = panel.style.writes, stableScroll = context.scrollY;
for (let i = 0; i < 3; i++) { toolbarResize([]); mutations[0]([]); flush(); }
assert.equal(panel.style.writes, stableWrites, "Unchanged toolbar measurements must not repeatedly write layout styles");
assert.equal(context.scrollY, stableScroll);
console.log("Analysis navigation preserves reading position and adapts tall toolbars without hiding results.");

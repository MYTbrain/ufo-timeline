import assert from "node:assert/strict";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const { create, deriveView, CONTROL_SELECTOR } = require("../startup_catalog_ui.js");

assert.equal(deriveView({ mapReady: false, catalogReady: false }).visible, false, "The original cover owns initial-map loading");
let view = deriveView({ mapReady: true, catalogReady: false, loaded: 7, total: 20, windowLabel: "1954-09-01 – 1954-11-30" });
assert.equal(view.visible, true);
assert.equal(view.locked, true);
assert.equal(view.progress, 35);
assert.match(view.progressLabel, /7\/20 parts/);
assert.equal(view.scope, "Mapped reports · 1954-09-01 – 1954-11-30");
assert.equal(view.progressShortLabel, "Catalog · 7/20");
assert.equal(deriveView({ mapViewReady: true, fullCatalogReady: false, backgroundError: "paused" }).visible, true);
assert.equal(deriveView({ mapViewReady: true, fullCatalogReady: true }).locked, false);
assert.match(deriveView({ mapReady: true, loaded: 20, total: 20 }).progressLabel, /Preparing/,
  "Downloaded parts do not falsely announce full catalog readiness");
assert.equal(deriveView({ mapReady: true }).progress, null, "Unknown total stays indeterminate");
assert.equal(deriveView({ mapReady: true, loaded: -5, total: 20 }).progress, 0);
assert.equal(deriveView({ mapReady: true, loaded: 99, total: 20 }).progress, 100);
view = deriveView({ mapReady: true, errorText: "Exact URL and failure reason" });
assert.equal(view.visible, true);
assert.equal(view.retryAvailable, true);
assert.equal(view.locked, true);
assert.equal(view.title, "Full catalog paused");
assert.match(view.help, /map remains available/);
assert.equal(deriveView({ mapReady: true, errorText: "x", retrying: true }).retryAvailable, false);
assert.equal(deriveView({ mapReady: true, catalogReady: true }).visible, false);
assert.equal(deriveView({ mapReady: true, catalogReady: true }).locked, false);
assert.ok(!CONTROL_SELECTOR.includes("#results-sort"), "Result inspection and sorting remain usable");
assert.ok(!CONTROL_SELECTOR.includes("#map-surface"), "Map gestures remain usable");

class Node {
  constructor(tag = "div") { this.tagName = tag; this.attrs = new Map(); this.children = []; this.listeners = new Map(); this.disabled = false; this.hidden = false; }
  setAttribute(k, v) { this.attrs.set(k, String(v)); }
  getAttribute(k) { return this.attrs.has(k) ? this.attrs.get(k) : null; }
  removeAttribute(k) { this.attrs.delete(k); }
  append(...nodes) { nodes.forEach((n) => this.appendChild(n)); }
  appendChild(n) { this.children.push(n); n.parentNode = this; }
  insertBefore(n, before) { this.children.splice(this.children.indexOf(before), 0, n); n.parentNode = this; }
  remove() { if (this.parentNode) this.parentNode.children.splice(this.parentNode.children.indexOf(this), 1); }
  addEventListener(k, fn) { this.listeners.set(k, fn); }
  removeEventListener(k, fn) { if (this.listeners.get(k) === fn) this.listeners.delete(k); }
}
const body = new Node("body"), host = new Node("aside"), before = new Node("div");
host.appendChild(before);
const enabled = new Node("input"), disabled = new Node("button");
enabled.setAttribute("title", "Original title");
disabled.disabled = true; disabled.setAttribute("aria-disabled", "true");
const controls = [enabled, disabled];
const doc = new Node("document");
doc.body = body;
doc.createElement = (tag) => new Node(tag);
doc.querySelectorAll = () => controls;
doc.getElementById = (id) => id === "map-control-cluster" ? host : before;
let observer = null;
doc.defaultView = { MutationObserver: class {
  constructor(fn) { observer = this; this.fn = fn; }
  observe() { this.active = true; }
  disconnect() { this.active = false; }
} };
let retries = 0;
const ui = create({ document: doc, onRetry() { retries += 1; } });
assert.equal(host.children[0], ui.element, "Status belongs inside map tools, ahead of the scrolling controls");
assert.equal(enabled.disabled, true);
assert.equal(enabled.getAttribute("data-catalog-pending"), "true");
ui.update({ mapReady: true, loaded: 2, total: 5 });
assert.equal(ui.element.hidden, false);
const dynamic = new Node("select"); controls.push(dynamic); observer.fn();
assert.equal(dynamic.disabled, true, "Controls created by deferred renders are also locked");
let prevented = false, stopped = false;
doc.listeners.get("pointerdown")({ target: { closest: () => true }, preventDefault() { prevented = true; }, stopImmediatePropagation() { stopped = true; } });
assert.equal(prevented && stopped, true, "Capture guards prevent timeline/filter actions before application handlers");
let mapBlocked = false;
doc.listeners.get("pointerdown")({ target: { closest: () => null }, preventDefault() { mapBlocked = true; }, stopImmediatePropagation() {} });
assert.equal(mapBlocked, false);
let editBlocked = false;
doc.listeners.get("keydown")({ key: "a", target: { closest: () => true }, preventDefault() { editBlocked = true; }, stopImmediatePropagation() {} });
assert.equal(editBlocked, true, "Transiently re-enabled text fields cannot change the pending query");
ui.update({ mapReady: true, errorText: "<script>bad()</script>\nhttps://source.invalid/missing" });
const retry = ui.element.children[5];
assert.equal(retry.hidden, false);
assert.equal(ui.element.children[6].children[1].textContent, "<script>bad()</script>\nhttps://source.invalid/missing", "Failure diagnostics are plain text");
retry.listeners.get("click")(); assert.equal(retries, 1);
ui.update({ mapReady: true, catalogReady: true });
assert.equal(ui.element.hidden, true);
assert.equal(enabled.disabled, false, "Originally available controls unlock");
assert.equal(enabled.getAttribute("title"), "Original title");
assert.equal(enabled.getAttribute("aria-disabled"), null);
assert.equal(disabled.disabled, true, "Pre-existing unavailable controls remain unavailable");
assert.equal(disabled.getAttribute("aria-disabled"), "true");
assert.equal(dynamic.disabled, false);
ui.dispose();
assert.equal(observer.active, false);
assert.equal(doc.listeners.size, 0);
assert.equal(host.children.includes(ui.element), false);
console.log("Progressive startup status and control guards passed.");

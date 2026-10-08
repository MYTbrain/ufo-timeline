"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { PresentationSession, intersect, cardPosition } = require("../guided_tour_state.js");

function control(initial) {
  let current = initial;
  const writes = [];
  return {
    read: () => current,
    write(value) { current = value; writes.push(value); },
    userSet(value) { current = value; },
    writes,
  };
}

test("ending a tour restores a panel that it expanded from collapsed", () => {
  const panel = control(false);
  const session = new PresentationSession();
  session.track("filters", panel.read, panel.write);
  session.change("filters", true);
  assert.equal(panel.read(), true, "the tour reveals its target");
  session.restore();
  assert.equal(panel.read(), false, "ending the tour restores the visitor's layout");
  assert.deepEqual(panel.writes, [true, false]);
  session.restore();
  assert.deepEqual(panel.writes, [true, false], "a second close is harmless");
});

test("a panel already open before the tour stays open without redundant writes", () => {
  const panel = control(true);
  const session = new PresentationSession();
  session.track("legend", panel.read, panel.write);
  session.change("legend", true);
  session.restore();
  assert.equal(panel.read(), true);
  assert.deepEqual(panel.writes, []);
});

test("an explicit visitor claim preserves the panel even when its value still matches the tour", () => {
  const panel = control(false);
  const session = new PresentationSession();
  session.track("results", panel.read, panel.write);
  session.change("results", true);
  session.claim("results");
  session.restore();
  assert.equal(panel.read(), true);
  assert.deepEqual(panel.writes, [true], "the visitor owns the expanded state");
});

test("a visitor toggling twice does not have that deliberate choice undone on close", () => {
  const panel = control(false);
  const session = new PresentationSession();
  session.track("tools", panel.read, panel.write);
  session.change("tools", true);
  panel.userSet(false);
  session.claim("tools");
  panel.userSet(true);
  session.claim("tools");
  session.restore();
  assert.equal(panel.read(), true, "matching the tour's value again does not transfer ownership back");
  assert.deepEqual(panel.writes, [true]);
});

test("an external value change is preserved even when no claim event was observed", () => {
  const topic = control("craft");
  const session = new PresentationSession();
  session.track("topic", topic.read, topic.write);
  session.change("topic", "overview");
  topic.userSet("geography");
  session.restore();
  assert.equal(topic.read(), "geography");
  assert.deepEqual(topic.writes, ["overview"]);
});

test("later Analysis steps restore the visitor's Time topic after temporary topic changes", () => {
  const topic = control("craft");
  const session = new PresentationSession();
  session.track("analysis-topic", topic.read, topic.write);
  session.change("analysis-topic", "overview");
  topic.userSet("time");
  session.claim("analysis-topic");
  session.change("analysis-topic", "overview");
  session.change("analysis-topic", "comparisons");
  assert.equal(topic.read(), "comparisons", "the next step can reveal its own target");
  session.restore();
  assert.equal(topic.read(), "time", "the visitor's latest topic replaces the pre-tour rollback");
  assert.deepEqual(topic.writes, ["overview", "overview", "comparisons", "time"]);
});

test("a panel deliberately closed by the visitor is restored after a later step reopens it", () => {
  const panel = control(true);
  const session = new PresentationSession();
  session.track("tools", panel.read, panel.write);
  session.change("tools", true);
  panel.userSet(false);
  session.claim("tools");
  session.change("tools", true);
  assert.equal(panel.read(), true, "the later tour target is visible");
  session.restore();
  assert.equal(panel.read(), false, "closing the tour respects the visitor's deliberate closure");
  assert.deepEqual(panel.writes, [true, false]);
});

test("requesting an unchanged claimed value does not revoke the visitor's ownership", () => {
  const panel = control(false);
  const session = new PresentationSession();
  session.track("results", panel.read, panel.write);
  session.change("results", true);
  session.claim("results");
  session.change("results", true);
  session.restore();
  assert.equal(panel.read(), true, "a subsequent no-op step preserves the chosen open state");
  assert.deepEqual(panel.writes, [true]);
});

test("releasing an individual target allows a fresh lease with a new original state", () => {
  const panel = control(false);
  const session = new PresentationSession();
  session.track("filters", panel.read, panel.write);
  session.change("filters", true);
  session.release("filters");
  assert.equal(panel.read(), false);
  panel.userSet(true);
  session.track("filters", panel.read, panel.write);
  session.change("filters", false);
  session.restore();
  assert.equal(panel.read(), true, "the new lease restores its own starting layout");
  assert.deepEqual(panel.writes, [true, false, false, true]);
});

test("tracking the same target again does not replace its pre-tour original value", () => {
  const panel = control(false);
  const session = new PresentationSession();
  session.track("legend", panel.read, panel.write);
  session.change("legend", true);
  session.track("legend", panel.read, panel.write);
  session.restore();
  assert.equal(panel.read(), false);
});

test("capture records a completed presentation change for restoration", () => {
  const panel = control(false);
  const session = new PresentationSession();
  session.track("details", panel.read, panel.write);
  panel.userSet(true);
  session.capture("details");
  session.restore();
  assert.equal(panel.read(), false);
  assert.deepEqual(panel.writes, [false]);
});

test("primary view restores before a topic whose setter depends on that view", () => {
  let view = "map";
  let topic = "craft";
  const restoration = [];
  const session = new PresentationSession();
  session.track("primary-view", () => view, (value) => {
    view = value;
    restoration.push("view:" + value);
  });
  session.track("analysis-topic", () => topic, (value) => {
    if (value === "craft") assert.equal(view, "map", "the original view must already be restored");
    topic = value;
    restoration.push("topic:" + value);
  });
  session.change("primary-view", "analysis");
  session.change("analysis-topic", "overview");
  restoration.length = 0;
  session.restore();
  assert.deepEqual(restoration, ["view:map", "topic:craft"]);
  assert.equal(view, "map");
  assert.equal(topic, "craft");
});

test("tour card remains within a desktop viewport and clear of small edge targets", () => {
  const viewport = { width: 1280, height: 800 };
  const size = { width: 320, height: 240 };
  const targets = [
    { left: 20, top: 20, right: 60, bottom: 60 },
    { left: 1210, top: 20, right: 1260, bottom: 60 },
    { left: 20, top: 730, right: 60, bottom: 780 },
    { left: 1210, top: 730, right: 1260, bottom: 780 },
    { left: 600, top: 20, right: 650, bottom: 60 },
    { left: 600, top: 730, right: 650, bottom: 780 },
    { left: 20, top: 375, right: 60, bottom: 425 },
    { left: 1210, top: 375, right: 1260, bottom: 425 },
  ];
  targets.forEach((target) => {
    const point = cardPosition(target, size, viewport);
    const card = { ...point, right: point.left + size.width, bottom: point.top + size.height };
    assert.ok(card.left >= 12 && card.top >= 12, "card keeps a safe leading margin");
    assert.ok(card.right <= viewport.width - 12 && card.bottom <= viewport.height - 12,
      "card fits without clipping its controls");
    const overlap = intersect(target, card);
    assert.ok(overlap.width === 0 || overlap.height === 0, "highlighted control remains visible");
  });
});

test("tour card finds vertical space when its target spans most of the viewport width", () => {
  const target = { left: 20, top: 200, right: 1260, bottom: 240 };
  const size = { width: 320, height: 240 };
  const viewport = { width: 1280, height: 800 };
  const point = cardPosition(target, size, viewport);
  assert.ok(point.top >= target.bottom || point.top + size.height <= target.top,
    "the card does not cover a wide highlighted toolbar");
  assert.ok(point.left >= 12 && point.left + size.width <= viewport.width - 12);
});

test("a missing tour target gets a reachable fallback card", () => {
  const point = cardPosition(null, { width: 320, height: 240 }, { width: 1280, height: 800 });
  assert.ok(Number.isFinite(point.left) && Number.isFinite(point.top));
  assert.ok(point.left >= 12 && point.left + 320 <= 1268);
  assert.ok(point.top >= 12 && point.top + 240 <= 788);
});

test("intersection clips a target to its scroll container and viewport", () => {
  const target = { left: -20, top: 40, right: 500, bottom: 900 };
  const visible = { left: 10, top: 100, right: 300, bottom: 700 };
  assert.deepEqual(intersect(target, visible), {
    left: 10, top: 100, right: 300, bottom: 700, width: 290, height: 600,
  });
});

test("nonintersecting and touching rectangles have no visible area", () => {
  const target = { left: 10, top: 10, right: 50, bottom: 50 };
  [
    { left: 80, top: 20, right: 100, bottom: 40 },
    { left: 20, top: 80, right: 40, bottom: 100 },
    { left: 50, top: 10, right: 80, bottom: 50 },
    { left: 10, top: 50, right: 50, bottom: 80 },
  ].forEach((other) => {
    const visible = intersect(target, other);
    assert.equal(visible.width * visible.height, 0);
    assert.ok(visible.width >= 0 && visible.height >= 0);
  });
});

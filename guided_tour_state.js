/* Small presentation leases: restore only changes still owned by the tour. */
(function (root, factory) {
  "use strict";
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.UfoGuidedTourState = api;
})(typeof window !== "undefined" ? window : null, function () {
  "use strict";
  class PresentationSession {
    constructor() { this.entries = new Map(); }
    track(key, read, write) {
      if (!this.entries.has(key)) {
        const original = read();
        this.entries.set(key, { read, write, original, owned: original, touched: false });
      }
    }
    change(key, value) {
      const entry = this.entries.get(key);
      if (!entry || entry.read() === value) return;
      // A later step can temporarily reveal something else. Its rollback must
      // be the visitor's latest deliberate choice, rather than the initial UI.
      if (entry.touched) {
        entry.original = entry.read();
        entry.owned = entry.original;
        entry.touched = false;
      }
      entry.write(value);
      entry.owned = entry.read();
    }
    capture(key) {
      const entry = this.entries.get(key);
      if (entry) entry.owned = entry.read();
    }
    claim(key) {
      const entry = this.entries.get(key);
      if (entry) entry.touched = true;
    }
    release(key) {
      const entry = this.entries.get(key);
      if (!entry) return;
      if (!entry.touched && entry.original !== entry.owned && entry.read() === entry.owned) {
        entry.write(entry.original);
      }
      this.entries.delete(key);
    }
    restore() {
      // Insertion order lets primary view restoration precede its topic/panels.
      Array.from(this.entries.keys()).forEach((key) => this.release(key));
    }
  }
  function intersect(a, b) {
    const left = Math.max(a.left, b.left), top = Math.max(a.top, b.top);
    const right = Math.min(a.right, b.right), bottom = Math.min(a.bottom, b.bottom);
    return { left, top, right, bottom, width: Math.max(0, right - left), height: Math.max(0, bottom - top) };
  }
  function cardPosition(target, size, viewport) {
    const gap = 14, margin = 12;
    const clamp = (value, high) => Math.max(margin, Math.min(value, Math.max(margin, high)));
    const options = target ? [
      { left: target.right + gap, top: target.top },
      { left: target.left - size.width - gap, top: target.top },
      { left: target.left, top: target.bottom + gap },
      { left: target.left, top: target.top - size.height - gap },
    ] : [];
    for (const option of options) {
      const point = { left: clamp(option.left, viewport.width - size.width - margin), top: clamp(option.top, viewport.height - size.height - margin) };
      if (!intersect(target, { ...point, right: point.left + size.width, bottom: point.top + size.height }).width ||
          !intersect(target, { ...point, right: point.left + size.width, bottom: point.top + size.height }).height) return point;
    }
    return { left: Math.max(margin, viewport.width - size.width - margin), top: Math.max(margin, viewport.height - size.height - margin) };
  }
  return Object.freeze({ PresentationSession, intersect, cardPosition });
});

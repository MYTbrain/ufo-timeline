(function (root, factory) {
  "use strict";
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.UfoAnalysisSessionView = api;
})(typeof self !== "undefined" ? self : globalThis, function () {
  "use strict";
  const count = value => Number.isFinite(value) ? value.toLocaleString() : "Not available";
  const percent = value => Number.isFinite(value) ? (value * 100).toFixed(1) + "%" : "";
  const reports = value => count(value) + (value === 1 ? " report" : " reports");
  const CRAFT_LABELS = Object.freeze({ chevron_boomerang: "Chevron / boomerang", cigar_cylinder: "Cigar / cylinder",
    disc_saucer: "Disc / saucer", dumbbell_barbell: "Dumbbell / barbell", formation: "Formation", oval_egg: "Oval / egg",
    rectangle_box: "Rectangle / box", sphere_orb: "Sphere / orb" });
  function categoryLabel(domain, row) {
    return domain === "craft" && (!row.label || row.label === row.key) && Object.prototype.hasOwnProperty.call(CRAFT_LABELS, row.key)
      ? CRAFT_LABELS[row.key] : row.label || row.key;
  }
  function reportCount(cohort) { return cohort && (Number.isFinite(cohort.reportCount) ? cohort.reportCount : cohort.summary && cohort.summary.reportN); }
  function scopeLabel(cohort) {
    const scope = cohort && cohort.scope;
    if (typeof scope === "string") return scope;
    if (!scope || typeof scope !== "object") return "";
    if (typeof scope.dateLabel === "string") return scope.dateLabel;
    const time = scope.timeRange;
    if (time && time.mode === "full") return "All time";
    if (time && (time.startIso || time.endIso)) return [time.startIso, time.endIso].filter(Boolean).join(" to ");
    return typeof scope.label === "string" ? scope.label : "";
  }
  function create(target, configuration) {
    if (!target || !target.ownerDocument) throw new Error("A comparison panel target is required.");
    const config = configuration || {}, store = config.store, doc = target.ownerDocument;
    if (!store || typeof store.getState !== "function" || typeof store.subscribe !== "function") throw new Error("A comparison session store is required.");
    let destroyed = false, externalBusy = false, pending = 0, message = "", error = false;
    const mutationButtons = [], groups = {};
    function node(tag, className, text) { const element = doc.createElement(tag); if (className) element.className = className; if (text != null) element.textContent = String(text); return element; }
    function button(text, callback, className, mutation = true) {
      const element = node("button", className || "", text); element.type = "button";
      element.addEventListener("click", () => invoke(callback));
      if (mutation) mutationButtons.push(element); return element;
    }
    function state() { return store.getState(); }
    function setStatus(text, isError) { message = text == null ? "" : String(text); error = Boolean(isError); renderStatus(); }
    function renderStatus() { status.textContent = message; status.setAttribute("data-error", error ? "true" : "false"); }
    async function invoke(callback) {
      if (destroyed || typeof callback !== "function") return;
      pending++; setStatus(""); renderBusy();
      try { await callback(); }
      catch (failure) { if (!destroyed) setStatus(failure && failure.message ? failure.message : "The comparison could not be updated. Please try again.", true); }
      finally { pending--; if (!destroyed) render(); }
    }
    function perform(name, fallback, ...args) { return typeof config[name] === "function" ? config[name](...args) : typeof store[fallback] === "function" ? store[fallback](...args) : undefined; }

    const panel = node("section", "analysis-session"); panel.setAttribute("aria-label", "Temporary Analysis comparison");
    const selection = node("div", "analysis-session-selection"); selection.hidden = true;
    const selectionText = node("p");
    const selectionActions = node("div", "analysis-session-selection-actions");
    selectionActions.appendChild(button("Return to filters", () => perform("onReturnToFilters", "clearSelection"), "analysis-session-return"));
    [["time", "Time"], ["craft", "Craft"], ["encounters", "Encounters"], ["comparisons", "Comparisons"]].forEach(([key, title]) => {
      const action = button(title, () => config.onOpenSection && config.onOpenSection(key), "", false);
      action.setAttribute("aria-label", "Open " + title + " Analysis for this selection"); selectionActions.appendChild(action);
    });
    selection.append(selectionText, selectionActions);
    const heading = node("div", "analysis-session-heading"), headingCopy = node("div");
    headingCopy.append(node("h3", "", "Try a comparison"), node("p", "analysis-session-intro", "Keep two groups while this page is open."));
    const actions = node("div", "analysis-session-actions");
    const pinA = button("Hold current as A", () => config.onPinCurrent && config.onPinCurrent("A"));
    const pinB = button("Hold current as B", () => config.onPinCurrent && config.onPinCurrent("B"));
    const clearAll = button("Clear all", () => perform("onClearAll", "clearAll"), "analysis-session-clear");
    actions.append(pinA, pinB, clearAll); heading.append(headingCopy, actions);
    const status = node("p", "analysis-session-status"); status.setAttribute("role", "status"); status.setAttribute("aria-live", "polite"); status.setAttribute("aria-atomic", "true");
    const groupGrid = node("div", "analysis-session-groups"); groupGrid.hidden = true;
    ["A", "B"].forEach(slot => {
      const details = node("details", "analysis-session-group"), summary = node("summary");
      const name = node("strong", "", slot), title = node("span", "analysis-session-group-title"), meta = node("span", "analysis-session-group-meta");
      summary.append(name, title, meta);
      const content = node("div", "analysis-session-group-content"), description = node("p", "analysis-session-note"), controls = node("div", "analysis-session-group-actions");
      const use = button("Use " + slot + " in Analysis", () => perform("onUseGroup", "useGroup", slot));
      const clear = button("Clear " + slot, () => perform("onClearGroup", "clearGroup", slot), "analysis-session-clear");
      controls.append(use, clear); content.append(description, controls); details.append(summary, content); groupGrid.appendChild(details);
      groups[slot] = { details, title, meta, description, use, clear };
    });
    const comparison = node("details", "analysis-session-comparison"); comparison.hidden = true;
    comparison.appendChild(node("summary", "analysis-session-comparison-summary", "Compare A and B"));
    const comparisonBody = node("div", "analysis-session-comparison-content"), overlap = node("p", "analysis-session-overlap");
    const totals = node("div", "analysis-session-table-wrap"), breakdowns = node("div", "analysis-session-breakdowns");
    comparisonBody.append(overlap, totals, breakdowns, node("p", "analysis-session-note", "Descriptive report counts, not independent incidents or evidence of a causal relationship. Percentages are shares of captured reports in each group. A report may have several labels."));
    comparison.appendChild(comparisonBody);
    panel.append(selection, heading, status, groupGrid, comparison); target.replaceChildren(panel);

    function table(parent, caption, rows, showBars) {
      const element = node("table", "analysis-session-table"); if (caption) element.appendChild(node("caption", "", caption));
      const head = node("thead"), headRow = node("tr");
      ["Measure", "A", "B"].forEach(title => { const cell = node("th", "", title); cell.setAttribute("scope", "col"); headRow.appendChild(cell); }); head.appendChild(headRow); element.appendChild(head);
      const body = node("tbody");
      rows.forEach(row => {
        const line = node("tr"), label = node("th", "", row.label); label.setAttribute("scope", "row"); line.appendChild(label);
        ["a", "b"].forEach(side => {
          const value = row[side], cell = node("td", "", count(value && value.count));
          if (value && Number.isFinite(value.share)) cell.appendChild(node("span", "", percent(value.share)));
          if (showBars && value && Number.isFinite(value.share)) {
            const track = node("span", "analysis-session-proportion"), fill = node("span", "analysis-session-proportion-fill");
            track.setAttribute("aria-hidden", "true"); fill.style.width = Math.min(1, Math.max(0, value.share)) * 100 + "%";
            track.appendChild(fill); cell.appendChild(track);
          }
          line.appendChild(cell);
        }); body.appendChild(line);
      }); element.appendChild(body); parent.appendChild(element); return element;
    }
    function renderComparison(current) {
      const model = current.comparison, a = current.groups && current.groups.A, b = current.groups && current.groups.B;
      comparison.hidden = !(a && b && model);
      if (comparison.hidden) { comparison.open = false; return; }
      const shared = model.overlapCount ?? (model.overlap && model.overlap.reportN);
      const overlapParts = [count(shared) + (shared === 1 ? " report belongs" : " reports belong") + " to both groups"];
      if (model.overlap) {
        if (Number.isFinite(model.overlap.shareA)) overlapParts.push(percent(model.overlap.shareA) + " of A");
        if (Number.isFinite(model.overlap.shareB)) overlapParts.push(percent(model.overlap.shareB) + " of B");
      }
      overlap.textContent = overlapParts.join(" · ") + ".";
      totals.replaceChildren();
      const left = model.a || a.summary || {}, right = model.b || b.summary || {};
      const metric = (key, denominator) => ({ a: { count: left[key], share: denominator && left.reportN > 0 && Number.isFinite(left[key]) ? left[key] / left.reportN : undefined }, b: { count: right[key], share: denominator && right.reportN > 0 && Number.isFinite(right[key]) ? right[key] / right.reportN : undefined } });
      table(totals, "Group coverage", [
        { label: "Reports", ...metric("reportN", false) }, { label: "Mapped", ...metric("mappedN", true) },
        { label: "Unmapped", ...metric("unmappedN", true) }, { label: "Reports with a date", ...metric("datedN", true) },
        { label: "Date unavailable", ...metric("undatedN", true) },
      ]);
      const open = new Set(Array.from(breakdowns.children || []).filter(element => element.open).map(element => element.getAttribute("data-axis")));
      breakdowns.replaceChildren();
      [["source", "Source collections"], ["craft", "Craft categories"], ["being", "Being descriptions"], ["abduction", "Abduction classifications"]].forEach(([key, title]) => {
        const distribution = model.distributions && model.distributions[key];
        if (!distribution || (!distribution.a?.available && !distribution.b?.available)) return;
        const detail = node("details", "analysis-session-breakdown"); detail.setAttribute("data-axis", key); detail.open = open.has(key);
        detail.appendChild(node("summary", "", title));
        const content = node("div", "analysis-session-breakdown-content"), wrapper = node("div", "analysis-session-table-wrap");
        const availableA = distribution.a?.available !== false, availableB = distribution.b?.available !== false;
        const rows = (distribution.rows || []).map(row => ({ label: categoryLabel(key, row), a: availableA ? { count: row.aCount, share: row.aShareOfReports } : null, b: availableB ? { count: row.bCount, share: row.bShareOfReports } : null }));
        if (distribution.unknown) rows.push({ label: "Unknown / not indexed", a: availableA ? { count: distribution.unknown.aCount, share: distribution.unknown.aShareOfReports } : null, b: availableB ? { count: distribution.unknown.bCount, share: distribution.unknown.bShareOfReports } : null });
        const coverage = (side, total, available) => available && Number.isFinite(side && side.eligibleN) ? count(side.eligibleN) + " of " + count(total) + " captured reports" : "not available";
        content.appendChild(node("p", "analysis-session-note", "Field coverage · A: " + coverage(distribution.a, left.reportN, availableA) + " · B: " + coverage(distribution.b, right.reportN, availableB) + "."));
        table(wrapper, "Counts and share of captured reports", rows, true); content.appendChild(wrapper);
        if (!availableA || !availableB) content.appendChild(node("p", "analysis-session-note", "This information is not available for " + (!availableA && !availableB ? "either group" : !availableA ? "group A" : "group B") + ". Missing information is not a zero count."));
        detail.appendChild(content); breakdowns.appendChild(detail);
      });
    }
    function renderBusy() {
      const busy = externalBusy || pending > 0; panel.setAttribute("aria-busy", busy ? "true" : "false");
      mutationButtons.forEach(element => { element.disabled = busy || Boolean(element.sessionUnavailable); });
    }
    function render() {
      if (destroyed) return;
      const current = state(), a = current.groups && current.groups.A, b = current.groups && current.groups.B;
      const selected = current.selection || (current.activeGroup && current.groups && current.groups[current.activeGroup]);
      selection.hidden = !selected;
      if (selected) selectionText.textContent = "Analysis selection: " + (selected.label || "Selected reports") + " · " + reports(reportCount(selected)) + ". Shared filters are kept for your return.";
      groupGrid.hidden = !(a || b);
      ["A", "B"].forEach(slot => {
        const cohort = current.groups && current.groups[slot], view = groups[slot];
        view.title.textContent = cohort ? cohort.label || "Held group" : "Not held";
        view.meta.textContent = cohort ? reports(reportCount(cohort)) + (scopeLabel(cohort) ? " · " + scopeLabel(cohort) : "") : "Hold a second group to compare.";
        view.description.textContent = cohort ? "Use this group across the Analysis sections, or hold the current reports again to replace it." : "Change your filters or select reports, then hold the current group here.";
        view.use.sessionUnavailable = !cohort || !(reportCount(cohort) > 0); view.clear.sessionUnavailable = !cohort;
        view.use.setAttribute("aria-pressed", current.activeGroup === slot ? "true" : "false");
      });
      pinA.sessionUnavailable = typeof config.onPinCurrent !== "function"; pinB.sessionUnavailable = typeof config.onPinCurrent !== "function";
      clearAll.sessionUnavailable = !(a || b || selected);
      renderComparison(current); renderStatus(); renderBusy();
    }
    const unsubscribe = store.subscribe(render); render();
    return { render, setStatus, setBusy(value) { externalBusy = Boolean(value); if (!destroyed) renderBusy(); }, destroy() {
      if (destroyed) return; destroyed = true; if (typeof unsubscribe === "function") unsubscribe(); target.replaceChildren();
    } };
  }
  return { create };
});

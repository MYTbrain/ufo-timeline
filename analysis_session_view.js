(function (root, factory) {
  "use strict";
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.UfoAnalysisSessionView = api;
})(typeof self !== "undefined" ? self : globalThis, function () {
  "use strict";
  const count = value => Number.isFinite(value) ? value.toLocaleString() : "Not available";
  const percent = value => Number.isFinite(value) ? (value * 100).toFixed(1) + "%" : "Not available";
  const reports = value => count(value) + (value === 1 ? " report" : " reports");
  const CRAFT_LABELS = Object.freeze({ chevron_boomerang: "Chevron / boomerang", cigar_cylinder: "Cigar / cylinder",
    disc_saucer: "Disc / saucer", dumbbell_barbell: "Dumbbell / barbell", formation: "Formation", oval_egg: "Oval / egg",
    rectangle_box: "Rectangle / box", sphere_orb: "Sphere / orb", cone: "Cone", diamond: "Diamond",
    fireball_meteor_like: "Fireball / meteor-like", light: "Light", teardrop: "Teardrop", triangle: "Triangle" });
  const AXES = [["craft", "Craft"], ["being", "Beings"], ["abduction", "Abductions"], ["source", "Sources"], ["coverage", "Coverage"]];
  let nextId = 0;
  function categoryLabel(domain, row) {
    return domain === "craft" && (!row.label || row.label === row.key) && Object.prototype.hasOwnProperty.call(CRAFT_LABELS, row.key)
      ? CRAFT_LABELS[row.key] : row.label || row.key;
  }
  function reportCount(cohort) { return cohort && (Number.isFinite(cohort.reportCount) ? cohort.reportCount : cohort.summary && cohort.summary.reportN); }
  function scopeLabel(cohort) {
    const scope = cohort && cohort.scope, summary = cohort && cohort.summary;
    if (scope && typeof scope === "object") {
      if (scope.allRecords === true) return "All-time collection study";
      const time = scope.timeRange;
      if (time && time.mode === "full" && cohort.provenance?.capturedSnapshot?.selection) return "Captured selection";
      if (time && time.mode === "full") return "All time";
      if (time && (time.startIso || time.endIso)) return (time.startIso || "Beginning") + " to " + (time.endIso || "present");
      if (typeof scope.dateLabel === "string") return scope.dateLabel;
    }
    if (summary && summary.dateLabel) return summary.dateLabel;
    return typeof scope === "string" && scope !== "captured report cohort" ? scope : scope && scope.label || "Selected reports";
  }
  function groupTitle(group) {
    const label = group && group.label || "Captured reports";
    return /^(?:current analysis (?:reports|population)|captured reports|held group)$/i.test(label) ? scopeLabel(group) : label;
  }
  function filterLabel(value) {
    const key = String(value), sources = { ufocat: "UFOCAT", nuforc: "NUFORC", majestic: "Majestic", mufon: "MUFON" };
    if (Object.prototype.hasOwnProperty.call(sources, key.toLowerCase())) return sources[key.toLowerCase()];
    if (Object.prototype.hasOwnProperty.call(CRAFT_LABELS, key)) return CRAFT_LABELS[key];
    return key.replace(/[_-]+/g, " ").replace(/^./, char => char.toUpperCase());
  }
  function filterSummary(group) {
    const scope = group?.scope, snapshot = group?.provenance?.capturedSnapshot, filters = snapshot?.filters;
    const list = values => (Array.isArray(values) ? values : []).slice(0, 2).map(filterLabel).join(", ") + (values?.length > 2 ? " +" + count(values.length - 2) + " more" : "");
    if (scope && typeof scope === "object" && scope.allRecords === true) {
      const parts = ["Full collection study"];
      [["material", "Material"], ["action", "Action"], ["being", "Being"], ["country", "Place"], ["source", "Source"], ["craft", "Craft"]].forEach(([key, label]) => { if (scope[key]) parts.push(label + ": " + filterLabel(scope[key])); });
      return parts.join(" · ");
    }
    if (snapshot?.selection) return "Captured selection: " + (snapshot.selection.label || "selected reports");
    if (!filters || typeof filters !== "object") return "Captured report selection";
    const parts = [];
    if (filters.sourceMode !== "all" && filters.selectedSources?.length) parts.push("Sources: " + list(filters.selectedSources));
    if (filters.typeMode !== "all" && filters.selectedTypes?.length) parts.push("Types: " + list(filters.selectedTypes));
    else if (filters.typeMode === "all") parts.push("All report types");
    if (filters.legendEventMode === "subset" && filters.selectedLegendEventKeys?.length) parts.push((filters.legendColorMode === "craft_type" ? "Craft: " : "Legend: ") + list(filters.selectedLegendEventKeys));
    const encounters = filters.encounters || {};
    if (encounters.beingTypes?.length) parts.push("Beings: " + list(encounters.beingTypes));
    else if (encounters.being && encounters.being !== "any") parts.push(encounters.being === "reported" ? "Being reported" : "No indexed being evidence");
    if (encounters.abduction && encounters.abduction !== "any") parts.push(({ reported: "Reported abduction", source_reported: "Source-classified abduction", ambiguous: "Ambiguous encounter category", not_indexed: "No indexed abduction evidence" })[encounters.abduction] || filterLabel(encounters.abduction));
    if (filters.keyword) parts.push("Search: “" + String(filters.keyword).slice(0, 48) + (String(filters.keyword).length > 48 ? "…" : "") + "”");
    if (filters.hideNonExactDates === true) parts.push("Exact dates");
    return parts.join(" · ") || "Captured report selection";
  }
  function create(target, configuration) {
    if (!target || !target.ownerDocument) throw new Error("A comparison panel target is required.");
    const config = configuration || {}, store = config.store, doc = target.ownerDocument;
    if (!store || typeof store.getState !== "function" || typeof store.subscribe !== "function") throw new Error("A comparison session store is required.");
    let destroyed = false, externalBusy = false, pending = 0, message = "", error = false, opened = false;
    let axis = "craft", showAll = false, tableOpen = false, lastComparison = null, chartVersion = 0, opener = null, restoreFocus = false;
    const mutationButtons = [], groups = {}, tabs = {}, id = "analysis-compare-" + (++nextId);
    function node(tag, className, text) { const el = doc.createElement(tag); if (className) el.className = className; if (text != null) el.textContent = String(text); return el; }
    function button(text, callback, className, mutation = true) {
      const el = node("button", className || "", text); el.type = "button";
      el.addEventListener("click", () => mutation ? invoke(callback) : callback && callback());
      if (mutation) mutationButtons.push(el); return el;
    }
    function state() { return store.getState(); }
    function setStatus(text, isError) { message = text == null ? "" : String(text); error = Boolean(isError); renderStatus(); }
    function renderStatus() {
      [status, modalStatus].forEach(el => { el.textContent = message; el.setAttribute("data-error", error ? "true" : "false"); });
    }
    async function invoke(callback) {
      if (destroyed || typeof callback !== "function" || externalBusy || pending) return;
      pending++; setStatus(""); renderBusy();
      try { await callback(); }
      catch (failure) { if (!destroyed) setStatus(failure && failure.message ? failure.message : "The comparison could not be updated. Please try again.", true); }
      finally { pending--; if (!destroyed) render(); }
    }
    function perform(name, fallback, ...args) { return typeof config[name] === "function" ? config[name](...args) : typeof store[fallback] === "function" ? store[fallback](...args) : undefined; }

    const panel = node("section", "analysis-session"); panel.setAttribute("aria-label", "Temporary Analysis comparison");
    const selection = node("div", "analysis-session-selection"), selectionText = node("p"), selectionActions = node("div", "analysis-session-selection-actions"); selection.hidden = true;
    selectionActions.appendChild(button("Return to filters", () => perform("onReturnToFilters", "clearSelection"), "analysis-session-return"));
    [["time", "Time"], ["craft", "Craft"], ["encounters", "Encounters"], ["comparisons", "Comparisons"]].forEach(([key, title]) => {
      const action = button(title, () => config.onOpenSection && config.onOpenSection(key), "", false);
      action.setAttribute("aria-label", "Open " + title + " Analysis for this selection"); selectionActions.appendChild(action);
    });
    selection.append(selectionText, selectionActions);
    const toolbar = node("div", "analysis-session-toolbar"), heading = node("div", "analysis-session-heading");
    heading.append(node("strong", "", "Compare groups"), node("span", "analysis-session-note", "Temporary · this page only"));
    const slots = node("div", "analysis-session-slots");
    ["A", "B"].forEach(slot => {
      const wrap = node("div", "analysis-session-slot analysis-session-side-" + slot.toLowerCase());
      const pin = button("Set " + slot, () => config.onPinCurrent && config.onPinCurrent(slot), "analysis-session-pin");
      const label = node("span", "analysis-session-slot-label", "Not set");
      wrap.append(pin, label); slots.appendChild(wrap); groups[slot] = { pin, label };
    });
    const compareButton = button("Compare A / B", openComparison, "analysis-session-compare-button", false);
    const clearAll = button("Clear all", () => perform("onClearAll", "clearAll"), "analysis-session-clear");
    const toolbarActions = node("div", "analysis-session-toolbar-actions"); toolbarActions.append(compareButton, clearAll);
    toolbar.append(heading, slots, toolbarActions);
    const status = node("p", "analysis-session-status"); status.setAttribute("role", "status"); status.setAttribute("aria-live", "polite");
    panel.append(selection, toolbar, status);

    // The comparison stays outside the Analysis layout, so opening it never moves its charts.
    const modal = node("dialog", "analysis-session-dialog"); modal.setAttribute("aria-labelledby", id + "-title"); modal.setAttribute("aria-describedby", id + "-description");
    const modalHeader = node("div", "analysis-session-dialog-header"), modalHeading = node("div");
    const title = node("h2", "", "Compare A / B"); title.id = id + "-title";
    const description = node("p", "analysis-session-note", "Two captured report groups. Nothing to save."); description.id = id + "-description";
    const closeButton = button("Close", closeComparison, "analysis-session-close", false); modalHeading.append(title, description); modalHeader.append(modalHeading, closeButton);
    const modalBody = node("div", "analysis-session-dialog-body"), cards = node("div", "analysis-session-cards");
    ["A", "B"].forEach(slot => {
      const card = node("section", "analysis-session-card analysis-session-side-" + slot.toLowerCase());
      const top = node("div", "analysis-session-card-top"), badge = node("span", "analysis-session-badge", slot), label = node("h3"); top.append(badge, label);
      const date = node("p", "analysis-session-date"), filter = node("p", "analysis-session-card-filters"), total = node("p", "analysis-session-card-total"), coverage = node("p", "analysis-session-card-coverage");
      const metrics = node("div", "analysis-session-card-metrics"); metrics.append(total, coverage);
      const controls = node("div", "analysis-session-card-actions");
      const use = button("Use " + slot + " in Analysis", async () => { await perform("onUseGroup", "useGroup", slot); closeComparison(); });
      const clear = button("Clear " + slot, () => perform("onClearGroup", "clearGroup", slot), "analysis-session-clear");
      controls.append(use, clear); card.append(top, date, filter, metrics, controls); cards.appendChild(card);
      Object.assign(groups[slot], { card, title: label, date, filter, total, coverage, use, clear });
    });
    const overlap = node("p", "analysis-session-overlap"), tabList = node("div", "analysis-session-tabs"); tabList.setAttribute("role", "tablist"); tabList.setAttribute("aria-label", "Comparison measure");
    AXES.forEach(([key, label], index) => {
      const tab = button(label, () => selectAxis(key), "analysis-session-tab", false); tab.id = id + "-" + key;
      tab.setAttribute("role", "tab"); tab.setAttribute("aria-controls", id + "-chart");
      tab.addEventListener("keydown", event => {
        let next;
        if (event.key === "ArrowRight") next = (index + 1) % AXES.length;
        else if (event.key === "ArrowLeft") next = (index + AXES.length - 1) % AXES.length;
        else if (event.key === "Home") next = 0;
        else if (event.key === "End") next = AXES.length - 1;
        if (next != null) { event.preventDefault(); selectAxis(AXES[next][0]); tabs[AXES[next][0]].focus?.(); }
      });
      tabs[key] = tab; tabList.appendChild(tab);
    });
    const chart = node("section", "analysis-session-chart"); chart.id = id + "-chart"; chart.setAttribute("role", "tabpanel");
    const modalStatus = node("p", "analysis-session-status"); modalStatus.setAttribute("role", "status"); modalStatus.setAttribute("aria-live", "polite");
    const caveat = node("p", "analysis-session-note analysis-session-caveat", "Report groups may overlap. These are descriptive counts, not independent incidents or evidence of a causal relationship.");
    modalBody.append(cards, overlap, modalStatus, tabList, chart, caveat); modal.append(modalHeader, modalBody);
    modal.addEventListener("cancel", event => { event.preventDefault(); closeComparison(); });
    modal.addEventListener("close", () => { if (opened) finishClose(); });
    target.replaceChildren(panel, modal);

    function openComparison() {
      const current = state(); if (destroyed || !current.groups?.A || !current.groups?.B || !current.comparison) return;
      opener = doc.activeElement || compareButton; opened = true; axis = "craft"; showAll = false; tableOpen = false;
      renderComparison(current, true);
      if (typeof modal.showModal === "function") { if (!modal.open) modal.showModal(); }
      else { modal.open = true; modal.setAttribute("open", ""); }
      closeButton.focus?.();
    }
    function finishClose() {
      opened = false;
      restoreFocus = !destroyed;
      if (!pending && !externalBusy) returnFocus();
    }
    function returnFocus() {
      if (!restoreFocus || destroyed) return;
      const current = state(), preferred = current.comparison ? opener || compareButton : !current.groups?.A ? groups.A.pin : groups.B.pin;
      const focus = preferred && !preferred.disabled && preferred.isConnected !== false ? preferred : !groups.A.pin.disabled ? groups.A.pin : null;
      if (focus) { focus.focus?.(); restoreFocus = false; opener = null; }
    }
    function closeComparison() {
      if (!opened) return;
      if (typeof modal.close === "function" && modal.open) modal.close();
      else { modal.open = false; modal.removeAttribute?.("open"); }
      if (opened) finishClose();
    }
    function selectAxis(key) { axis = key; showAll = false; tableOpen = false; renderComparison(state(), true); }
    function coverageText(summary, key, label) { return Number.isFinite(summary[key]) ? label + " " + count(summary[key]) + " (" + percent(summary.reportN > 0 ? summary[key] / summary.reportN : null) + ")" : label + " unavailable"; }
    function renderCards(current) {
      ["A", "B"].forEach(slot => {
        const group = current.groups?.[slot], ui = groups[slot], summary = group && group.summary || {};
        ui.title.textContent = group ? groupTitle(group) : "No group";
        ui.date.textContent = group ? groupTitle(group) === scopeLabel(group) ? group.label || "Captured time window" : scopeLabel(group) : "Set a group to compare";
        ui.date.hidden = !group || groupTitle(group) === scopeLabel(group);
        ui.filter.textContent = group ? filterSummary(group) : "";
        ui.total.textContent = group ? reports(reportCount(group)) : "";
        ui.coverage.textContent = group ? coverageText(summary, "mappedN", "Mapped") + " · " + coverageText(summary, "datedN", "With a date") : "";
        ui.use.sessionUnavailable = !group || !(reportCount(group) > 0); ui.clear.sessionUnavailable = !group;
        ui.use.setAttribute("aria-pressed", current.activeGroup === slot ? "true" : "false");
      });
    }
    function rowsFor(current) {
      const model = current.comparison;
      if (axis === "coverage") {
        const a = model.a, b = model.b;
        return { rows: [["mappedN", "Mapped"], ["unmappedN", "Unmapped"], ["datedN", "With a date"], ["undatedN", "Date unavailable"]].map(([key, label]) => ({ key, label,
          aCount: a[key], bCount: b[key], aShareOfReports: Number.isFinite(a[key]) && a.reportN > 0 ? a[key] / a.reportN : null,
          bShareOfReports: Number.isFinite(b[key]) && b.reportN > 0 ? b[key] / b.reportN : null })), coverage: true };
      }
      const distribution = model.distributions?.[axis];
      if (!distribution) return { rows: [], a: { available: false }, b: { available: false } };
      return Object.assign({}, distribution, { rows: distribution.rows.map(row => Object.assign({}, row, { label: categoryLabel(axis, row) })) });
    }
    function sideValue(row, slot) {
      const side = slot.toLowerCase(), n = row[side + "Count"], share = row[side + "ShareOfReports"];
      return { count: n, share, text: Number.isFinite(n) ? (Number.isFinite(share) ? percent(share) + " · " : "") + count(n) : "Not available" };
    }
    function chartRow(row, kind) {
      const item = node("div", "analysis-session-chart-row" + (kind ? " analysis-session-unknown" : "")), top = node("div", "analysis-session-row-heading");
      top.appendChild(node("strong", "", row.label));
      const values = [sideValue(row, "A"), sideValue(row, "B")], difference = values.every(value => Number.isFinite(value.share)) ? Math.abs(values[0].share - values[1].share) : null;
      if (!kind && axis !== "coverage" && difference !== null) top.appendChild(node("span", "analysis-session-difference", (difference * 100).toFixed(1) + " pp difference"));
      item.appendChild(top);
      ["A", "B"].forEach((slot, index) => {
        const value = values[index], line = node("div", "analysis-session-bar-line analysis-session-side-" + slot.toLowerCase()), letter = node("span", "analysis-session-bar-letter", slot);
        const track = node("span", "analysis-session-bar-track"), fill = node("span", "analysis-session-bar-fill");
        track.setAttribute("aria-hidden", "true"); fill.style.width = Number.isFinite(value.share) ? Math.min(1, Math.max(0, value.share)) * 100 + "%" : "0%";
        if (!Number.isFinite(value.share)) track.className += " analysis-session-bar-unavailable";
        track.appendChild(fill);
        const exact = node("span", "analysis-session-bar-value", value.text);
        line.append(letter, track, exact); item.appendChild(line);
      });
      return item;
    }
    function addDataTable(parent, rows) {
      const detail = node("details", "analysis-session-data"); detail.open = tableOpen;
      const version = chartVersion;
      detail.addEventListener("toggle", () => { if (opened && version === chartVersion) tableOpen = detail.open; }); detail.appendChild(node("summary", "", "View exact data"));
      const wrapper = node("div", "analysis-session-table-wrap"), table = node("table", "analysis-session-table");
      table.appendChild(node("caption", "", "Count and share of all captured reports in each group"));
      const head = node("thead"), headings = node("tr");
      ["Category", "A", "B"].forEach(text => { const cell = node("th", "", text); cell.setAttribute("scope", "col"); headings.appendChild(cell); }); head.appendChild(headings); table.appendChild(head);
      const body = node("tbody"); rows.forEach(row => { const line = node("tr"), label = node("th", "", row.label); label.setAttribute("scope", "row"); line.appendChild(label); ["A", "B"].forEach(slot => { const value = sideValue(row, slot); line.appendChild(node("td", "", value.text)); }); body.appendChild(line); });
      table.appendChild(body); wrapper.appendChild(table); detail.appendChild(wrapper); parent.appendChild(detail);
    }
    function renderComparison(current, force) {
      const model = current.comparison;
      if (!opened || !model || !current.groups?.A || !current.groups?.B) return;
      renderCards(current);
      const shared = model.overlapCount ?? model.overlap?.reportN;
      overlap.textContent = count(shared) + " shared " + (shared === 1 ? "report" : "reports") + (model.overlap ? " · " + percent(model.overlap.shareA) + " of A · " + percent(model.overlap.shareB) + " of B" : "");
      if (!force && lastComparison === model) return;
      lastComparison = model; chartVersion++;
      AXES.forEach(([key]) => { const selected = axis === key; tabs[key].setAttribute("aria-selected", selected ? "true" : "false"); tabs[key].tabIndex = selected ? 0 : -1; });
      chart.setAttribute("aria-labelledby", id + "-" + axis); chart.replaceChildren();
      const data = rowsFor(current), bothAvailable = data.coverage || data.a?.available && data.b?.available;
      const ranked = data.rows.slice().sort((a, b) => {
        const difference = row => Number.isFinite(row.aShareOfReports) && Number.isFinite(row.bShareOfReports) ? Math.abs(row.aShareOfReports - row.bShareOfReports) : -1;
        return bothAvailable ? difference(b) - difference(a) || String(a.label).localeCompare(String(b.label)) : Math.max(b.aCount || 0, b.bCount || 0) - Math.max(a.aCount || 0, a.bCount || 0) || String(a.label).localeCompare(String(b.label));
      });
      chart.appendChild(node("p", "analysis-session-denominator", "Share of all captured reports · A: " + count(model.a.reportN) + " · B: " + count(model.b.reportN) + "."));
      const fieldCoverage = data.coverage ? "Date coverage includes dates of any recorded precision." : "Field indexed · A: " + (data.a?.available && Number.isFinite(data.a.eligibleN) ? count(data.a.eligibleN) + " of " + count(model.a.reportN) : "not available") + " · B: " + (data.b?.available && Number.isFinite(data.b.eligibleN) ? count(data.b.eligibleN) + " of " + count(model.b.reportN) : "not available") + (data.multiLabel ? ". A report may have several labels." : ".");
      chart.appendChild(node("p", "analysis-session-note", fieldCoverage));
      if (!data.coverage && !bothAvailable) chart.appendChild(node("p", "analysis-session-missing", "Missing information is not a zero count. " + (!data.a?.available && !data.b?.available ? "This field is unavailable for both groups." : "This field is unavailable for group " + (!data.a?.available ? "A" : "B") + ".")));
      if (ranked.length) {
        const scale = node("div", "analysis-session-scale"); scale.setAttribute("aria-hidden", "true"); scale.append(node("span", "", "0%"), node("span", "", "50%"), node("span", "", "100%")); chart.appendChild(scale);
        if (!data.coverage) chart.appendChild(node("p", "analysis-session-rank-note", (bothAvailable ? "Largest percentage-point differences first" : "Most reports first") + (ranked.length > 8 ? " · Showing " + (showAll ? count(ranked.length) : "8") + " of " + count(ranked.length) : "")));
        const rows = node("div", "analysis-session-chart-rows"); ranked.slice(0, showAll ? undefined : 8).forEach(row => rows.appendChild(chartRow(row))); chart.appendChild(rows);
        if (ranked.length > 8) {
          const version = chartVersion;
          const more = button(showAll ? "Show fewer" : "Show all " + count(ranked.length) + " categories", () => { if (version !== chartVersion) return; showAll = !showAll; renderComparison(state(), true); chart.querySelector?.(".analysis-session-show-all")?.focus(); }, "analysis-session-show-all", false); chart.appendChild(more);
        }
      } else chart.appendChild(node("p", "analysis-session-empty", "No indexed categories to display for these groups."));
      const exactRows = ranked.slice();
      if (data.unknown && (Number.isFinite(data.unknown.aCount) || Number.isFinite(data.unknown.bCount))) {
        const unknown = Object.assign({ label: "Unknown / not indexed" }, data.unknown);
        chart.appendChild(chartRow(unknown, "unknown")); exactRows.push(unknown);
      }
      if (exactRows.length) addDataTable(chart, exactRows);
    }
    function renderBusy() {
      const busy = externalBusy || pending > 0; panel.setAttribute("aria-busy", busy ? "true" : "false"); modal.setAttribute("aria-busy", busy ? "true" : "false");
      mutationButtons.forEach(el => { el.disabled = busy || Boolean(el.sessionUnavailable); });
      compareButton.disabled = busy || !state().comparison;
      if (!busy) returnFocus();
    }
    function render() {
      if (destroyed) return;
      const current = state(), a = current.groups?.A, b = current.groups?.B;
      const selected = current.selection || (current.activeGroup && current.groups?.[current.activeGroup]);
      selection.hidden = !selected;
      if (selected) selectionText.textContent = "Using " + (selected.label || "selected reports") + " · " + reports(reportCount(selected)) + " across Analysis.";
      ["A", "B"].forEach(slot => {
        const group = current.groups?.[slot], ui = groups[slot];
        ui.pin.textContent = (group ? "Replace " : "Set ") + slot;
        ui.pin.title = "Hold the current Analysis reports as group " + slot;
        ui.pin.sessionUnavailable = typeof config.onPinCurrent !== "function";
        ui.label.textContent = group ? reports(reportCount(group)) + " · " + scopeLabel(group) : "Not set";
        ui.label.title = group ? group.label + " · " + scopeLabel(group) : "Change filters or select reports, then set " + slot;
      });
      clearAll.sessionUnavailable = !(a || b || selected);
      if (opened && (!a || !b || !current.comparison)) closeComparison();
      if (opened) renderComparison(current, false);
      renderStatus(); renderBusy();
    }
    const unsubscribe = store.subscribe(render); render();
    return { render, setStatus, setBusy(value) { externalBusy = Boolean(value); if (!destroyed) renderBusy(); }, destroy() {
      if (destroyed) return; closeComparison(); destroyed = true; if (typeof unsubscribe === "function") unsubscribe(); target.replaceChildren();
    } };
  }
  return { create };
});

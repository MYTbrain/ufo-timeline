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
  const AXES = [["craft", "Craft composition"], ["being", "Beings"], ["abduction", "Abductions"], ["source", "Sources"], ["coverage", "Coverage"],
    ["calendarMonth", "Month of year"], ["weekday", "Day of week"], ["timeOfDay", "Time of day"], ["year", "Year"], ["duration", "Duration"],
    ["country", "Countries"], ["macroregion", "World regions"], ["adminRegion", "Local regions"], ["reportType", "Report types"],
    ["datePrecision", "Date precision"], ["locationPrecision", "Location precision"], ["craftConfidence", "Craft classification"], ["color", "Reported colors"], ["witnessCount", "Witness count"]];
  const TOPICS = Object.freeze({
    overview: { label: "Group overview", axes: ["coverage", "craft", "source"] },
    time: { label: "Time patterns", axes: ["calendarMonth", "weekday", "timeOfDay", "year", "duration"] },
    craft: { label: "Reported craft categories", axes: ["craft", "craftConfidence", "color"] },
    encounters: { label: "Encounter reports", axes: ["being", "abduction"] },
    geography: { label: "Geography", axes: ["country", "macroregion", "adminRegion"] },
    "sources-quality": { label: "Sources & quality", axes: ["source", "reportType", "datePrecision", "locationPrecision", "witnessCount", "coverage"] },
    crops: { label: "Crop circles", unavailable: "Crop-circle records belong to a separate catalog. They are not included in the UFO reports held as A and B." },
    animals: { label: "Animal reports", unavailable: "Animal-mutilation records belong to a separate catalog. They are not included in the UFO reports held as A and B." },
    facilities: { label: "Facilities", unavailable: "Facility proximity and its location eligibility are not yet captured in the A/B groups." },
    spatial: { label: "Spatial evidence", unavailable: "Spatial relationships and their location eligibility are not yet captured in the A/B groups." },
    comparisons: { label: "Context comparisons", unavailable: "Moon, planetary and nuclear context comparisons are not yet captured in the A/B groups." },
    context: { label: "Evidence gates", unavailable: "Cross-catalog evidence gates and relationship lineage are not yet captured in the A/B groups." }
  });
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
    const comparisonTarget = config.comparisonTarget || target;
    if (!comparisonTarget || comparisonTarget.ownerDocument !== doc) throw new Error("The comparison chart must belong to the same document.");
    let destroyed = false, externalBusy = false, pending = 0, message = "", error = false, mode = "current";
    let section = "overview", axis = "coverage", showAll = false, tableOpen = false, lastComparison = null, chartVersion = 0;
    let previousA = null, previousB = null, previousPair = false, focusAfterMutation = null;
    const mutationButtons = [], groups = {}, tabs = {}, id = "analysis-compare-" + (++nextId);
    function node(tag, className, text) { const el = doc.createElement(tag); if (className) el.className = className; if (text != null) el.textContent = String(text); return el; }
    function button(text, callback, className, mutation = true) {
      const el = node("button", className || "", text); el.type = "button";
      el.addEventListener("click", () => mutation ? invoke(callback) : callback && callback());
      if (mutation) mutationButtons.push(el); return el;
    }
    function state() { return store.getState(); }
    function topic() { return TOPICS[section] || { label: "This Analysis topic", unavailable: "This topic is not yet captured in the A/B groups." }; }
    function setStatus(text, isError) { message = text == null ? "" : String(text); error = Boolean(isError); renderStatus(); }
    function renderStatus() { status.textContent = message; status.setAttribute("data-error", error ? "true" : "false"); }
    async function invoke(callback) {
      if (destroyed || typeof callback !== "function" || externalBusy || pending) return;
      pending++; setStatus(""); renderBusy();
      try { await callback(); }
      catch (failure) { if (!destroyed) setStatus(failure && failure.message ? failure.message : "The comparison could not be updated. Please try again.", true); }
      finally { pending--; if (!destroyed) render(); }
    }
    function perform(name, fallback, ...args) { return typeof config[name] === "function" ? config[name](...args) : typeof store[fallback] === "function" ? store[fallback](...args) : undefined; }
    function changeMode(next) {
      if (destroyed || !["current", "compare"].includes(next) || next === "compare" && !state().comparison) return false;
      if (mode === next) return true;
      mode = next; lastComparison = null; render();
      if (typeof config.onModeChange === "function") config.onModeChange(mode);
      return true;
    }

    const panel = node("section", "analysis-session"); panel.setAttribute("aria-label", "Temporary Analysis comparison");
    const selection = node("div", "analysis-session-selection"), selectionText = node("p"), selectionActions = node("div", "analysis-session-selection-actions"); selection.hidden = true;
    selectionActions.appendChild(button("Return to filters", async () => { await perform("onReturnToFilters", "clearSelection"); changeMode("current"); }, "analysis-session-return"));
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
      const pin = button("Set " + slot, async () => {
        const before = state().groups?.[slot];
        if (typeof config.onPinCurrent !== "function") return;
        await config.onPinCurrent(slot);
        if (!destroyed && state().groups?.[slot] !== before && state().comparison) changeMode("compare");
      }, "analysis-session-pin");
      const label = node("span", "analysis-session-slot-label", "Not set");
      wrap.append(pin, label); slots.appendChild(wrap); groups[slot] = { pin, label };
    });
    const modes = node("div", "analysis-session-modes"); modes.setAttribute("role", "group"); modes.setAttribute("aria-label", "Analysis display");
    const currentButton = button("Current reports", () => changeMode("current"), "analysis-session-current-button", false);
    const compareButton = button("Compare A / B", () => changeMode("compare"), "analysis-session-compare-button", false);
    currentButton.setAttribute("aria-controls", "analysis-content"); compareButton.setAttribute("aria-controls", id + "-board");
    modes.append(currentButton, compareButton);
    const clearAll = button("Clear all", async () => { await perform("onClearAll", "clearAll"); focusAfterMutation = groups.A.pin; }, "analysis-session-clear");
    const toolbarActions = node("div", "analysis-session-toolbar-actions"); toolbarActions.append(modes, clearAll);
    toolbar.append(heading, slots, toolbarActions);
    const instructions = node("p", "analysis-session-instructions");
    const status = node("p", "analysis-session-status"); status.setAttribute("role", "status"); status.setAttribute("aria-live", "polite");
    panel.append(selection, toolbar, instructions, status);

    const board = node("section", "analysis-session-board"); board.id = id + "-board"; board.hidden = true;
    board.setAttribute("aria-labelledby", id + "-title");
    const title = node("h2", "analysis-session-board-title"); title.id = id + "-title";
    const context = node("div", "analysis-session-context");
    const overlap = node("p", "analysis-session-overlap");
    const details = node("details", "analysis-session-group-details"); details.appendChild(node("summary", "", "Group details & actions"));
    const cards = node("div", "analysis-session-cards");
    ["A", "B"].forEach(slot => {
      const card = node("section", "analysis-session-card analysis-session-side-" + slot.toLowerCase());
      const top = node("div", "analysis-session-card-top"), badge = node("span", "analysis-session-badge", slot), label = node("h3"); top.append(badge, label);
      const date = node("p", "analysis-session-date"), filter = node("p", "analysis-session-card-filters"), total = node("p", "analysis-session-card-total"), coverage = node("p", "analysis-session-card-coverage");
      const metrics = node("div", "analysis-session-card-metrics"); metrics.append(total, coverage);
      const controls = node("div", "analysis-session-card-actions");
      const use = button("Use " + slot + " in Analysis", async () => {
        const used = await perform("onUseGroup", "useGroup", slot);
        if (used !== false) { changeMode("current"); focusAfterMutation = currentButton; }
      });
      const clear = button("Clear " + slot, async () => { await perform("onClearGroup", "clearGroup", slot); focusAfterMutation = groups[slot].pin; }, "analysis-session-clear");
      controls.append(use, clear); card.append(top, date, filter, metrics, controls); cards.appendChild(card);
      Object.assign(groups[slot], { card, title: label, date, filter, total, coverage, use, clear });
    });
    details.appendChild(cards); context.append(overlap, details);
    const tabList = node("div", "analysis-session-tabs"); tabList.setAttribute("role", "tablist"); tabList.setAttribute("aria-label", "A/B measure in this Analysis topic");
    AXES.forEach(([key, label]) => {
      const tab = button(label, () => selectAxis(key), "analysis-session-tab", false); tab.id = id + "-" + key;
      tab.setAttribute("role", "tab"); tab.setAttribute("aria-controls", id + "-chart");
      tab.addEventListener("keydown", event => {
        const available = topic().axes || [], index = available.indexOf(key); let next;
        if (index < 0) return;
        if (event.key === "ArrowRight") next = (index + 1) % available.length;
        else if (event.key === "ArrowLeft") next = (index + available.length - 1) % available.length;
        else if (event.key === "Home") next = 0;
        else if (event.key === "End") next = available.length - 1;
        if (next != null) { event.preventDefault(); selectAxis(available[next]); tabs[available[next]].focus?.(); }
      });
      tabs[key] = tab; tabList.appendChild(tab);
    });
    const chart = node("section", "analysis-session-chart"); chart.id = id + "-chart"; chart.setAttribute("role", "tabpanel");
    const unavailable = node("div", "analysis-session-unavailable"); unavailable.hidden = true;
    const unavailableText = node("p", "analysis-session-missing");
    unavailable.append(unavailableText, button("View current reports", () => { changeMode("current"); currentButton.focus?.(); }, "analysis-session-return", false));
    const caveat = node("p", "analysis-session-note analysis-session-caveat", "Counts describe captured catalog reports. Groups may overlap, and different reports may describe the same incident. Differences do not establish a causal relationship.");
    board.append(title, context, tabList, unavailable, chart, caveat);
    target.replaceChildren(panel);
    if (comparisonTarget === target) target.appendChild(board); else comparisonTarget.replaceChildren(board);

    function selectAxis(key) {
      if (!(topic().axes || []).includes(key)) return;
      axis = key; showAll = false; tableOpen = false; renderComparison(state(), true);
    }
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
      detail.addEventListener("toggle", () => { if (mode === "compare" && version === chartVersion) tableOpen = detail.open; }); detail.appendChild(node("summary", "", "View exact data"));
      const wrapper = node("div", "analysis-session-table-wrap"), table = node("table", "analysis-session-table");
      table.appendChild(node("caption", "", "Count and share of all captured reports in each group"));
      const head = node("thead"), headings = node("tr");
      ["Category", "A", "B"].forEach(text => { const cell = node("th", "", text); cell.setAttribute("scope", "col"); headings.appendChild(cell); }); head.appendChild(headings); table.appendChild(head);
      const body = node("tbody"); rows.forEach(row => { const line = node("tr"), label = node("th", "", row.label); label.setAttribute("scope", "row"); line.appendChild(label); ["A", "B"].forEach(slot => { const value = sideValue(row, slot); line.appendChild(node("td", "", value.text)); }); body.appendChild(line); });
      table.appendChild(body); wrapper.appendChild(table); detail.appendChild(wrapper); parent.appendChild(detail);
    }
    function renderComparison(current, force) {
      const model = current.comparison, currentTopic = topic();
      if (mode !== "compare" || !model || !current.groups?.A || !current.groups?.B) return;
      title.textContent = currentTopic.label + " · Compare A / B";
      renderCards(current);
      const shared = model.overlapCount ?? model.overlap?.reportN;
      overlap.textContent = count(shared) + " shared " + (shared === 1 ? "report" : "reports") + (model.overlap ? " · " + percent(model.overlap.shareA) + " of A · " + percent(model.overlap.shareB) + " of B" : "");
      const supported = Boolean(currentTopic.axes?.length);
      tabList.hidden = !supported; unavailable.hidden = supported; chart.hidden = !supported; caveat.hidden = !supported;
      if (!supported) { unavailableText.textContent = currentTopic.unavailable; chart.replaceChildren(); lastComparison = null; return; }
      if (!currentTopic.axes.includes(axis)) axis = currentTopic.axes[0];
      AXES.forEach(([key]) => {
        const visible = currentTopic.axes.includes(key), selected = visible && axis === key;
        tabs[key].hidden = !visible; tabs[key].setAttribute("aria-selected", selected ? "true" : "false"); tabs[key].tabIndex = selected ? 0 : -1;
      });
      if (!force && lastComparison === model) return;
      lastComparison = model; chartVersion++;
      chart.setAttribute("aria-labelledby", id + "-" + axis); chart.replaceChildren();
      const data = rowsFor(current), bothAvailable = data.coverage || data.a?.available && data.b?.available;
      const chronological = ["calendarMonth", "weekday", "timeOfDay", "year", "duration", "witnessCount"].includes(axis);
      const ranked = data.rows.slice();
      if (!chronological) ranked.sort((a, b) => {
        const difference = row => Number.isFinite(row.aShareOfReports) && Number.isFinite(row.bShareOfReports) ? Math.abs(row.aShareOfReports - row.bShareOfReports) : -1;
        return bothAvailable ? difference(b) - difference(a) || String(a.label).localeCompare(String(b.label)) : Math.max(b.aCount || 0, b.bCount || 0) - Math.max(a.aCount || 0, a.bCount || 0) || String(a.label).localeCompare(String(b.label));
      });
      chart.appendChild(node("p", "analysis-session-denominator", "Share of all captured reports · A: " + count(model.a.reportN) + " · B: " + count(model.b.reportN) + "."));
      const fieldCoverage = data.coverage ? "Date coverage includes dates of any recorded precision." : "Field indexed · A: " + (data.a?.available && Number.isFinite(data.a.eligibleN) ? count(data.a.eligibleN) + " of " + count(model.a.reportN) : "not available") + " · B: " + (data.b?.available && Number.isFinite(data.b.eligibleN) ? count(data.b.eligibleN) + " of " + count(model.b.reportN) : "not available") + (data.multiLabel ? ". A report may have several labels." : ".");
      chart.appendChild(node("p", "analysis-session-note", fieldCoverage));
      if (axis === "year") chart.appendChild(node("p", "analysis-session-note", "Different date windows naturally occupy different years. Use Month of year, Day of week or Time of day to compare recurring patterns."));
      if (!data.coverage && !bothAvailable) chart.appendChild(node("p", "analysis-session-missing", "Missing information is not a zero count. " + (!data.a?.available && !data.b?.available ? "This field is unavailable for both groups. Recapture the groups after the relevant Analysis data is ready." : "This field is unavailable for group " + (!data.a?.available ? "A" : "B") + ".")));
      const limit = chronological ? 12 : 8;
      if (ranked.length) {
        const scale = node("div", "analysis-session-scale"); scale.setAttribute("aria-hidden", "true"); scale.append(node("span", "", "0%"), node("span", "", "50%"), node("span", "", "100%")); chart.appendChild(scale);
        if (!data.coverage) chart.appendChild(node("p", "analysis-session-rank-note", (chronological ? "Calendar / category order" : bothAvailable ? "Largest percentage-point differences first" : "Most reports first") + (ranked.length > limit ? " · Showing " + (showAll ? count(ranked.length) : count(limit)) + " of " + count(ranked.length) : "")));
        const rows = node("div", "analysis-session-chart-rows"); ranked.slice(0, showAll ? undefined : limit).forEach(row => rows.appendChild(chartRow(row))); chart.appendChild(rows);
        if (ranked.length > limit) {
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
      const busy = externalBusy || pending > 0; panel.setAttribute("aria-busy", busy ? "true" : "false"); board.setAttribute("aria-busy", busy ? "true" : "false");
      mutationButtons.forEach(el => { el.disabled = busy || Boolean(el.sessionUnavailable); });
      compareButton.disabled = busy || !state().comparison; currentButton.disabled = busy;
      if (!busy && focusAfterMutation) { const focus = focusAfterMutation; focusAfterMutation = null; if (!focus.disabled && focus.isConnected !== false) focus.focus?.(); }
    }
    function render() {
      if (destroyed) return;
      const current = state(), a = current.groups?.A, b = current.groups?.B;
      const selected = current.selection || (current.activeGroup && current.groups?.[current.activeGroup]);
      selection.hidden = !selected;
      if (selected) selectionText.textContent = "Current Analysis selection: " + (selected.label || "selected reports") + " · " + reports(reportCount(selected)) + ".";
      ["A", "B"].forEach(slot => {
        const group = current.groups?.[slot], ui = groups[slot];
        ui.pin.textContent = (group ? "Replace " : "Set ") + slot;
        ui.pin.title = (group ? "Replace group " : "Hold group ") + slot + " with the current applied dates and filters";
        ui.pin.sessionUnavailable = typeof config.onPinCurrent !== "function";
        ui.label.textContent = group ? reports(reportCount(group)) + " · " + scopeLabel(group) : "Not set";
        ui.label.title = group ? group.label + " · " + scopeLabel(group) + " · " + filterSummary(group) : "Apply dates and filters, then set " + slot;
      });
      instructions.textContent = a && b ? (mode === "compare" ? "Comparing held A and B in the selected Analysis topic. Replace uses the current applied dates and filters." : "Viewing current reports. Choose Compare A / B to view the held groups in each Analysis topic.")
        : a || b ? "One group is held. Change dates and filters, Apply, then Set " + (a ? "B" : "A") + "."
        : "Apply dates and filters → Set A. Change them → Apply → Set B.";
      currentButton.setAttribute("aria-pressed", mode === "current" ? "true" : "false"); compareButton.setAttribute("aria-pressed", mode === "compare" ? "true" : "false");
      board.hidden = mode !== "compare" || !current.comparison;
      clearAll.sessionUnavailable = !(a || b || selected);
      if (!board.hidden) renderComparison(current, false);
      renderStatus(); renderBusy();
    }
    function onStoreChange() {
      const current = state(), a = current.groups?.A, b = current.groups?.B, pair = Boolean(a && b && current.comparison);
      const completeNow = pair && !previousPair, changed = a !== previousA || b !== previousB;
      previousA = a; previousB = b; previousPair = pair;
      if (!pair && mode === "compare") changeMode("current");
      else if (completeNow) changeMode("compare");
      else { if (changed) lastComparison = null; render(); }
    }
    const unsubscribe = store.subscribe(onStoreChange); onStoreChange();
    return { render, setStatus, setBusy(value) { externalBusy = Boolean(value); if (!destroyed) renderBusy(); },
      setMode: changeMode, getMode() { return mode; }, setSection(key) {
        if (destroyed) return;
        const next = String(key || "overview").replace(/^analysis-section-/, "").replace(/_/g, "-");
        if (section === next) return;
        section = next; axis = topic().axes?.[0] || "coverage"; showAll = false; tableOpen = false; lastComparison = null; render();
      }, destroy() {
        if (destroyed) return; destroyed = true; if (typeof unsubscribe === "function") unsubscribe(); target.replaceChildren();
        if (comparisonTarget !== target) comparisonTarget.replaceChildren();
      }
    };
  }
  return { create };
});

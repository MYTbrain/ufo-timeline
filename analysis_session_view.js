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
    encounters: { label: "Encounter reports", axes: ["being", "abduction", "collections"], external: true },
    geography: { label: "Geography", axes: ["country", "macroregion", "adminRegion"] },
    "sources-quality": { label: "Sources & quality", axes: ["source", "reportType", "datePrecision", "locationPrecision", "witnessCount", "coverage"] },
    crops: { label: "Crop circles", external: true },
    animals: { label: "Animal reports", external: true },
    facilities: { label: "Facilities", external: true },
    spatial: { label: "Spatial evidence", external: true },
    comparisons: { label: "Context comparisons", external: true },
    context: { label: "Evidence gates", external: true }
  });
  const DEFAULT_SETTINGS = Object.freeze({ sourceDomain: "craft", planet: "venus", partner: "mars", zodiac: "sidereal_lahiri", orb: 3,
    nuclearWindowDays: 30, nuclearRadiusKm: 500, spatialRadiusKm: 100, collectionEvidence: "direct" });
  const BODIES = Object.freeze(["sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn", "uranus", "neptune"]);
  function normalizeSettings(value) {
    const result = Object.assign({}, DEFAULT_SETTINGS, value || {});
    [["sourceDomain", ["craft", "crops", "animals"]], ["planet", BODIES], ["partner", BODIES], ["zodiac", ["sidereal_lahiri", "tropical"]], ["collectionEvidence", ["direct", "all"]]].forEach(([key, choices]) => {
      if (!choices.includes(result[key])) throw new Error("Choose a valid " + key.replace(/([A-Z])/g, " $1").toLowerCase() + ".");
    });
    [["orb", .01, 10], ["nuclearWindowDays", 1, 90], ["nuclearRadiusKm", 1, 2000], ["spatialRadiusKm", 1, 100]].forEach(([key, min, max]) => {
      const number = Number(result[key]);
      if (!Number.isFinite(number) || number < min || number > max || key !== "orb" && !Number.isInteger(number)) throw new Error("Enter a valid " + key.replace(/([A-Z])/g, " $1").toLowerCase() + ".");
      result[key] = number;
    });
    if (result.planet === result.partner) throw new Error("Choose different planets for the planet and its aspect partner.");
    return Object.freeze(Object.fromEntries(Object.keys(DEFAULT_SETTINGS).map(key => [key, result[key]])));
  }
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
    let section = "overview", axis = "coverage", showAll = false, tableOpen = false, methodsOpen = false, lastComparison = null, chartVersion = 0;
    let previousA = null, previousB = null, previousPair = false, focusAfterMutation = null;
    let inspection = null, inspectionGeneration = 0, inspectionOpener = null;
    let settings = normalizeSettings(config.settings), settingsVersion = 0, settingsRenderKey = "", cacheA = null, cacheB = null, measureOptionsKey = "";
    const externalCache = new Map(), settingsControls = {}, settingFields = {};
    const mutationButtons = [], groups = {}, tabs = {}, id = "analysis-compare-" + (++nextId);
    function node(tag, className, text) { const el = doc.createElement(tag); if (className) el.className = className; if (text != null) el.textContent = String(text); return el; }
    function button(text, callback, className, mutation = true) {
      const el = node("button", className || "", text); el.type = "button";
      el.addEventListener("click", () => mutation ? invoke(callback) : callback && callback());
      if (mutation) mutationButtons.push(el); return el;
    }
    function state() { return store.getState(); }
    function topic() { return TOPICS[section] || { label: "This Analysis topic", unavailable: "This topic is not yet captured in the A/B groups." }; }
    function isExternalAxis() { return topic().external === true && (section !== "encounters" || axis === "collections" || axis.startsWith("external:")); }
    function externalKey() { return section + "|" + JSON.stringify(settings); }
    function externalEntry() {
      const current = state();
      return current.groups?.A === cacheA && current.groups?.B === cacheB ? externalCache.get(externalKey()) : null;
    }
    function collectionDimension(entry) {
      const dimensions = entry?.result?.dimensions || [];
      return dimensions.find(value => /material/i.test(value.key + " " + value.label)) || dimensions[0];
    }
    function availableAxes() {
      const currentTopic = topic(), entry = externalEntry();
      if (!currentTopic.external) return (currentTopic.axes || []).slice();
      if (section === "encounters") {
        const material = collectionDimension(entry);
        return (currentTopic.axes || []).concat((entry?.result?.dimensions || []).filter(value => value !== material).map(value => "external:" + value.key));
      }
      return entry?.status === "ready" ? entry.result.dimensions.map(value => "external:" + value.key) : [];
    }
    function normalizeExternalResult(value) {
      if (!value || !["ready", "unavailable"].includes(value.status) || !Array.isArray(value.dimensions)) throw new Error("The comparison returned incomplete category data. Try again.");
      const api = config.model || (typeof globalThis !== "undefined" && globalThis.UfoAnalysisSession);
      if (!api || typeof api.compareExternalDimension !== "function") throw new Error("Reload the preview to prepare this comparison.");
      const keys = new Set(), dimensions = value.dimensions.map(item => {
        if (!item || keys.has(String(item.key))) throw new Error("The comparison returned repeated category fields.");
        keys.add(String(item.key)); return api.compareExternalDimension(item);
      });
      const reason = value.reason == null ? "" : String(value.reason), notes = Array.isArray(value.notes) ? value.notes.map(String) : [];
      if (reason) notes.unshift(reason);
      return Object.freeze({ dimensions: Object.freeze(dimensions), notes: Object.freeze(notes), unavailableReason: reason, artifactHashes: value.artifactHashes || null });
    }
    function ensureExternal() {
      if (mode !== "compare" || !isExternalAxis()) return null;
      const current = state();
      if (cacheA !== current.groups?.A || cacheB !== current.groups?.B) { externalCache.clear(); cacheA = current.groups?.A; cacheB = current.groups?.B; }
      const key = externalKey(), cached = externalCache.get(key);
      if (cached) return cached;
      const entry = { key, section, a: cacheA, b: cacheB, settings, status: "loading", result: null, error: null };
      externalCache.set(key, entry);
      while (externalCache.size > 12) externalCache.delete(externalCache.keys().next().value);
      function stillCurrent() { return !destroyed && mode === "compare" && section === entry.section && externalEntry() === entry; }
      entry.promise = Promise.resolve().then(() => {
        if (destroyed || cacheA !== entry.a || cacheB !== entry.b || externalCache.get(entry.key) !== entry) throw new Error("This comparison request was replaced.");
        if (typeof config.onLoadComparison !== "function") throw new Error("This preview does not yet provide this comparison. View current reports or reload the updated preview.");
        return config.onLoadComparison({ section: entry.section, groups: { A: entry.a, B: entry.b }, settings: entry.settings });
      }).then(value => {
        entry.result = normalizeExternalResult(value); entry.status = "ready";
        if (stillCurrent()) { lastComparison = null; renderComparison(state(), true); renderBusy(); }
      }).catch(failure => {
        entry.status = "error"; entry.error = failure?.message || "The comparison could not be loaded. Try again.";
        if (stillCurrent()) { lastComparison = null; renderComparison(state(), true); renderBusy(); }
      });
      return entry;
    }
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
      closeInspection(false);
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
        if (!destroyed && state().groups?.[slot] !== before && state().comparison) { changeMode("compare"); edits.open = false; focusAfterMutation = compareButton; }
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
    const heldSummary = node("div", "analysis-session-held-summary"); heldSummary.hidden = true;
    ["A", "B"].forEach(slot => {
      const summary = node("div", "analysis-session-held-group analysis-session-side-" + slot.toLowerCase()), countText = node("strong"), dateText = node("span", "analysis-session-held-date");
      summary.append(countText, dateText); heldSummary.appendChild(summary); Object.assign(groups[slot], { summary, summaryCount: countText, summaryDate: dateText });
    });
    const toolbarActions = node("div", "analysis-session-toolbar-actions"); toolbarActions.append(modes);
    toolbar.append(heading, heldSummary, toolbarActions);
    const edits = node("details", "analysis-session-edits"); edits.open = true;
    edits.appendChild(node("summary", "", "Edit groups"));
    const editContent = node("div", "analysis-session-edit-content"), editActions = node("div", "analysis-session-edit-actions"); editActions.appendChild(clearAll);
    const instructions = node("p", "analysis-session-instructions");
    const status = node("p", "analysis-session-status"); status.setAttribute("role", "status"); status.setAttribute("aria-live", "polite");
    editContent.append(slots, editActions, instructions); edits.appendChild(editContent);
    panel.append(selection, toolbar, edits, status);

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
    details.append(overlap, cards); context.append(details);
    const tabList = node("div", "analysis-session-tabs"); tabList.setAttribute("role", "tablist"); tabList.setAttribute("aria-label", "A/B measure in this Analysis topic");
    function createTab(key, label) {
      if (tabs[key]) { tabs[key].textContent = label; return tabs[key]; }
      const tab = button(label, () => selectAxis(key), "analysis-session-tab", false); tab.id = id + "-" + key;
      tab.setAttribute("role", "tab"); tab.setAttribute("aria-controls", id + "-chart");
      tab.addEventListener("keydown", event => {
        const available = availableAxes(), index = available.indexOf(key); let next;
        if (index < 0) return;
        if (event.key === "ArrowRight") next = (index + 1) % available.length;
        else if (event.key === "ArrowLeft") next = (index + available.length - 1) % available.length;
        else if (event.key === "Home") next = 0;
        else if (event.key === "End") next = available.length - 1;
        if (next != null) { event.preventDefault(); selectAxis(available[next]); tabs[available[next]].focus?.(); }
      });
      tabs[key] = tab; tabList.appendChild(tab);
      return tab;
    }
    AXES.forEach(([key, label]) => createTab(key, label)); createTab("collections", "Collection materials");
    const measurePicker = node("label", "analysis-session-measure-picker"), measureCaption = node("span", "", "Measure"), measureSelect = node("select");
    measurePicker.hidden = true; measureSelect.id = id + "-measure"; measureSelect.setAttribute("aria-label", "A/B comparison measure");
    measureSelect.addEventListener("change", () => selectAxis(measureSelect.value)); measurePicker.append(measureCaption, measureSelect);
    const settingsDetails = node("details", "analysis-session-settings"); settingsDetails.appendChild(node("summary", "", "Comparison settings · same for A and B"));
    const settingsGrid = node("div", "analysis-session-settings-grid");
    function setting(key, label, options, attributes) {
      const field = node("label", "analysis-session-setting"), caption = node("span", "", label), control = node(options ? "select" : "input");
      if (options) options.forEach(([value, text]) => { const option = node("option", "", text); option.value = value; control.appendChild(option); });
      else { control.type = "number"; Object.entries(attributes || {}).forEach(([name, value]) => control.setAttribute(name, value)); }
      control.setAttribute("aria-label", label + " for both groups"); settingsControls[key] = control; settingFields[key] = field;
      field.append(caption, control); settingsGrid.appendChild(field);
    }
    setting("sourceDomain", "Context record population", [["craft", "Craft reports"], ["crops", "Crop circles"], ["animals", "Animal reports"]]);
    const bodyOptions = BODIES.map(value => [value, filterLabel(value)]);
    setting("planet", "Planet", bodyOptions); setting("partner", "Aspect partner", bodyOptions);
    setting("zodiac", "Zodiac convention", [["sidereal_lahiri", "Sidereal · Lahiri"], ["tropical", "Tropical"]]);
    setting("orb", "Aspect orb (degrees)", null, { min: .01, max: 10, step: .01 });
    setting("nuclearWindowDays", "Nuclear window (± days)", null, { min: 1, max: 90, step: 1 });
    setting("nuclearRadiusKm", "Nuclear distance (km)", null, { min: 1, max: 2000, step: 1 });
    setting("spatialRadiusKm", "Neighborhood radius (km)", null, { min: 1, max: 100, step: 1 });
    setting("collectionEvidence", "Collection evidence", [["direct", "Direct collection accounts"], ["all", "Include uncertain / adjacent contexts"]]);
    const settingsError = node("p", "analysis-session-settings-error"); settingsError.setAttribute("role", "alert"); settingsError.hidden = true;
    const applySettings = button("Apply to both groups", () => {
      const draft = Object.fromEntries(Object.entries(settingsControls).map(([key, control]) => [key, control.value]));
      try { updateSettings(draft); settingsError.textContent = ""; settingsError.hidden = true; }
      catch (failure) { settingsError.textContent = failure.message; settingsError.hidden = false; }
    }, "analysis-session-apply-settings", false);
    settingsDetails.append(settingsGrid, settingsError, applySettings);
    const externalStatus = node("div", "analysis-session-external-status"); externalStatus.hidden = true;
    const externalMessage = node("p"); externalMessage.setAttribute("role", "status"); externalMessage.setAttribute("aria-live", "polite");
    const retryExternal = button("Retry comparison", () => { externalCache.delete(externalKey()); lastComparison = null; renderComparison(state(), true); renderBusy(); }, "analysis-session-retry", false);
    externalStatus.append(externalMessage, retryExternal);
    const chart = node("section", "analysis-session-chart"); chart.id = id + "-chart"; chart.setAttribute("role", "tabpanel");
    const unavailable = node("div", "analysis-session-unavailable"); unavailable.hidden = true;
    const unavailableText = node("p", "analysis-session-missing"), unavailableNotes = node("div");
    unavailable.append(unavailableText, unavailableNotes, button("View current reports", () => { changeMode("current"); currentButton.focus?.(); }, "analysis-session-return", false));
    const caveat = node("p", "analysis-session-note analysis-session-caveat", "Counts describe captured catalog reports. Groups may overlap, and different reports may describe the same incident. Differences do not establish a causal relationship.");
    board.append(title, context, settingsDetails, tabList, measurePicker, externalStatus, unavailable, chart, caveat);
    const inspectionDialog = node("dialog", "analysis-session-inspection"); inspectionDialog.setAttribute("aria-labelledby", id + "-inspection-title");
    const inspectionHeader = node("div", "analysis-session-inspection-header"), inspectionTitle = node("h2", "", "Inspect comparison records"); inspectionTitle.id = id + "-inspection-title";
    const closeInspectionButton = button("Close records", () => closeInspection(), "analysis-session-inspection-close", false); inspectionHeader.append(inspectionTitle, closeInspectionButton);
    const inspectionSummary = node("p", "analysis-session-inspection-summary"), inspectionSides = node("div", "analysis-session-inspection-sides"), inspectionSideButtons = {};
    inspectionSides.setAttribute("role", "group"); inspectionSides.setAttribute("aria-label", "Inspected group");
    ["A", "B"].forEach(slot => { const control = button(slot, () => { if (inspection) { inspection.activeSide = slot; renderInspection(); } }, "analysis-session-side-" + slot.toLowerCase(), false); inspectionSides.appendChild(control); inspectionSideButtons[slot] = control; });
    const inspectionBody = node("div", "analysis-session-inspection-body"), inspectionStatus = node("p", "analysis-session-inspection-status"), inspectionNotes = node("details", "analysis-session-inspection-notes"), inspectionColumns = node("div", "analysis-session-inspection-columns"), inspectionGroupNodes = {};
    inspectionStatus.setAttribute("role", "status"); inspectionStatus.setAttribute("aria-live", "polite");
    ["A", "B"].forEach(slot => { const column = node("section", "analysis-session-inspection-group analysis-session-side-" + slot.toLowerCase()), heading = node("h3"), population = node("p", "analysis-session-note"), list = node("div", "analysis-session-inspection-list"); column.append(heading, population, list); inspectionColumns.appendChild(column); inspectionGroupNodes[slot] = { heading, population, list }; });
    inspectionBody.append(inspectionStatus, inspectionNotes, inspectionColumns);
    const inspectionFooter = node("div", "analysis-session-inspection-footer"), inspectionRetry = button("Retry records", () => inspection && loadInspectionPage(inspection.failedOffset || 0), "", false), inspectionMore = button("Load more records", () => inspection && loadInspectionPage(inspection.nextOffset), "", false);
    inspectionFooter.append(inspectionRetry, inspectionMore);
    inspectionDialog.append(inspectionHeader, inspectionSummary, inspectionSides, inspectionBody, inspectionFooter);
    inspectionDialog.addEventListener("cancel", event => { event.preventDefault(); closeInspection(); });
    inspectionDialog.addEventListener("close", () => { if (inspection) closeInspection(); });
    target.replaceChildren(panel, inspectionDialog);
    if (comparisonTarget === target) target.appendChild(board); else comparisonTarget.replaceChildren(board);

    function selectAxis(key) {
      if (!availableAxes().includes(key)) return;
      closeInspection(false);
      axis = key; showAll = false; tableOpen = false; methodsOpen = false; renderComparison(state(), true);
      renderBusy();
    }
    function updateSettings(value) {
      const next = normalizeSettings(Object.assign({}, settings, value || {}));
      if (JSON.stringify(next) === JSON.stringify(settings)) return false;
      closeInspection(false);
      settings = next; settingsVersion++; showAll = false; tableOpen = false; methodsOpen = false; lastComparison = null; render(); return true;
    }
    function renderSettings() {
      settingsDetails.hidden = !isExternalAxis();
      const key = section + "|" + settingsVersion;
      if (settingsRenderKey === key) return;
      settingsRenderKey = key;
      const visible = section === "comparisons" ? ["sourceDomain", "planet", "partner", "zodiac", "orb", "nuclearWindowDays", "nuclearRadiusKm"]
        : section === "encounters" ? ["collectionEvidence"] : ["spatialRadiusKm"];
      Object.entries(settingsControls).forEach(([name, control]) => { control.value = String(settings[name]); settingFields[name].hidden = !visible.includes(name); });
      settingsError.textContent = ""; settingsError.hidden = true;
    }
    function closeInspection(restoreFocus = true) {
      if (!inspection && !inspectionDialog.open) return;
      inspectionGeneration++; inspection = null;
      if (typeof inspectionDialog.close === "function" && inspectionDialog.open) inspectionDialog.close();
      else { inspectionDialog.open = false; inspectionDialog.removeAttribute("open"); }
      if (restoreFocus && !destroyed) {
        const target = inspectionOpener && inspectionOpener.isConnected !== false ? inspectionOpener : compareButton;
        target?.focus?.({ preventScroll: true });
      }
      inspectionOpener = null;
    }
    function inspectionMatches(value) {
      const current = state();
      return !destroyed && inspection === value && value.generation === inspectionGeneration && mode === "compare" && value.section === section && value.axis === axis && value.settings === settings
        && value.groups.A === current.groups?.A && value.groups.B === current.groups?.B;
    }
    function openInspection(row, data, opener) {
      if (destroyed || mode !== "compare" || typeof config.onInspectComparison !== "function") return;
      closeInspection(false);
      const current = state(), dimension = { key: data.key || axis, label: tabs[axis]?.textContent || topic().label, unit: data.unit || "canonical_reports", external: data.external === true,
        a: Object.assign({ totalN: current.comparison.a.reportN }, data.a || {}), b: Object.assign({ totalN: current.comparison.b.reportN }, data.b || {}), row, uncertainty: data.uncertainty || null };
      inspectionOpener = opener || doc.activeElement;
      inspection = { generation: ++inspectionGeneration, section, axis, domainKey: data.key || axis, rowKey: row.key, dimension, settings,
        groups: { A: current.groups.A, B: current.groups.B }, title: row.label, unit: dimension.unit, notes: [], expandedIds: new Set(), activeSide: "A", nextOffset: 0, loading: false, error: "", sides: {
          A: { totalN: null, matchedN: null, rows: [] }, B: { totalN: null, matchedN: null, rows: [] }
        } };
      renderInspection();
      if (typeof inspectionDialog.showModal === "function") inspectionDialog.showModal();
      else { inspectionDialog.open = true; inspectionDialog.setAttribute("open", ""); }
      closeInspectionButton.focus?.();
      return loadInspectionPage(0);
    }
    function normalizedInspectionPage(value) {
      if (!value || !value.groups) throw new Error("The record inspection returned incomplete data. Retry records.");
      const result = { title: typeof value.title === "string" ? value.title : "", unit: typeof value.unit === "string" ? value.unit : "", notes: Array.isArray(value.notes) ? value.notes.map(String) : [], groups: {} };
      function validCount(value) { return value == null || Number.isSafeInteger(value) && value >= 0; }
      ["A", "B"].forEach(slot => {
        const side = value.groups[slot];
        if (!side || !Array.isArray(side.rows) || side.rows.length > 25 || !validCount(side.totalN) || !validCount(side.matchedN)
            || side.totalN != null && side.matchedN != null && side.matchedN > side.totalN || side.matchedN != null && side.rows.length > side.matchedN) throw new Error("The record inspection returned invalid counts. Retry records.");
        const rows = side.rows.map(row => {
          if (!row || row.id == null || !String(row.id).trim()) throw new Error("An inspected record is missing its identity. Retry records.");
          return Object.assign({}, row, { id: String(row.id) });
        });
        result.groups[slot] = { totalN: side.totalN ?? null, matchedN: side.matchedN ?? null, rows, reason: side.reason == null ? "" : String(side.reason) };
      });
      return result;
    }
    async function loadInspectionPage(offset) {
      const current = inspection;
      if (!current || current.loading || !inspectionMatches(current)) return;
      current.pageControlFocus = doc.activeElement === inspectionMore || doc.activeElement === inspectionRetry;
      current.loading = true; current.error = ""; current.failedOffset = offset; renderInspection();
      try {
        const page = normalizedInspectionPage(await config.onInspectComparison({ section: current.section, domainKey: current.domainKey, rowKey: current.rowKey,
          groups: current.groups, settings: current.settings, dimension: current.dimension, offset, limit: 25 }));
        if (!inspectionMatches(current)) return;
        ["A", "B"].forEach(slot => {
          const side = current.sides[slot], incoming = page.groups[slot];
          if (offset > 0 && (side.totalN !== incoming.totalN || side.matchedN !== incoming.matchedN)) throw new Error("The record population changed while paging. Close and reopen the inspection.");
        });
        ["A", "B"].forEach(slot => {
          const side = current.sides[slot], incoming = page.groups[slot], rows = offset === 0 ? [] : side.rows.slice(), seen = new Set(rows.map(row => row.id));
          incoming.rows.forEach(row => { if (!seen.has(row.id)) { seen.add(row.id); rows.push(row); } });
          current.sides[slot] = Object.assign({}, incoming, { rows });
        });
        current.title = current.title || page.title; current.unit = page.unit || current.unit; current.notes = page.notes;
        current.nextOffset = offset + 25;
        if (offset === 0 && !(current.sides.A.matchedN > 0) && current.sides.B.matchedN > 0) current.activeSide = "B";
      } catch (failure) { if (inspectionMatches(current)) current.error = failure?.message || "The records could not be loaded. Retry records."; }
      finally { if (inspectionMatches(current)) { current.loading = false; renderInspection(); } }
    }
    function sourceUrl(value) {
      try { const url = new URL(String(value)); return ["https:", "http:"].includes(url.protocol) ? url.href : null; } catch (_) { return null; }
    }
    function inspectionRecord(row, slot) {
      const card = node("article", "analysis-session-inspected-record"), label = typeof row.label === "string" && row.label ? row.label : "Record " + row.id;
      card.appendChild(node("h4", "", label));
      const text = key => ["string", "number"].includes(typeof row[key]) ? String(row[key]) : "";
      const metadata = [text("date"), text("location"), text("source")].filter(Boolean);
      if (metadata.length) card.appendChild(node("p", "analysis-session-note", metadata.join(" · ")));
      const detail = text("detail");
      if (detail) {
        if (detail.length <= 280) card.appendChild(node("p", "analysis-session-record-detail", detail));
        else {
          const disclosure = node("details", "analysis-session-record-detail"), owner = inspection, key = slot + ":" + row.id;
          disclosure.open = Boolean(owner?.expandedIds.has(key));
          disclosure.addEventListener("toggle", () => { if (inspection === owner) { if (disclosure.open) owner.expandedIds.add(key); else owner.expandedIds.delete(key); } });
          disclosure.append(node("summary", "", "Account details"), node("p", "", detail)); card.appendChild(disclosure);
        }
      }
      const actions = node("div", "analysis-session-record-actions"), ids = [...new Set([row.eventId, ...(Array.isArray(row.eventIds) ? row.eventIds : [])]
        .filter(value => typeof value === "string" && value.trim() || typeof value === "number" && Number.isSafeInteger(value) && value >= 0).map(String))], url = sourceUrl(row.sourceUrl);
      function recordAction(label, payload) {
        const control = button(label, async () => {
          closeInspection(false);
          try { await config.onOpenInspectedRecord(payload); }
          catch (failure) { if (!destroyed) setStatus(failure?.message || "This record could not be opened. Try inspecting it again.", true); }
        }, "", false); actions.appendChild(control);
      }
      if (typeof config.onOpenInspectedRecord === "function") ids.forEach((eventId, index) => recordAction(ids.length === 1 ? "Open preserved report" : "Open report " + (index + 1), { eventId, sourceUrl: url }));
      if (url) {
        const sourceLabel = typeof row.sourceLinkLabel === "string" && row.sourceLinkLabel.trim() ? row.sourceLinkLabel.trim() : "Open source";
        const link = node("a", "", sourceLabel); link.href = url; link.target = "_blank"; link.rel = "noopener noreferrer"; actions.appendChild(link);
      }
      if (actions.children.length) card.appendChild(actions); return card;
    }
    function renderInspection() {
      const current = inspection; if (!current) return;
      const scrollTop = inspectionBody.scrollTop;
      inspectionDialog.setAttribute("aria-busy", current.loading ? "true" : "false"); inspectionDialog.setAttribute("data-active-side", current.activeSide);
      inspectionTitle.textContent = current.title || "Inspect comparison records";
      inspectionSummary.textContent = "Counting unit: " + current.unit.replace(/_/g, " ") + ". A and B retain their held populations.";
      inspectionStatus.textContent = current.error || (current.loading ? "Loading preserved records…" : ""); inspectionStatus.setAttribute("data-error", current.error ? "true" : "false");
      inspectionNotes.replaceChildren(); inspectionNotes.hidden = !current.notes.length;
      if (current.notes.length) { inspectionNotes.appendChild(node("summary", "", "Scope & source notes")); current.notes.forEach(note => inspectionNotes.appendChild(node("p", "analysis-session-note", note))); }
      ["A", "B"].forEach(slot => {
        const side = current.sides[slot], ui = inspectionGroupNodes[slot];
        const matched = Number.isFinite(side.matchedN) ? count(side.matchedN) + " matched" : current.loading ? "Loading…" : current.error && !side.reason ? "Not loaded" : "Unavailable";
        ui.heading.textContent = slot + " · " + matched;
        ui.population.textContent = current.loading && side.totalN == null ? "Preparing this group's records…" : (Number.isFinite(side.matchedN) ? count(side.rows.length) + " shown · " : "") + count(side.totalN) + " " + current.unit.replace(/_/g, " ") + " in this population";
        inspectionSideButtons[slot].textContent = slot + " · " + matched; inspectionSideButtons[slot].setAttribute("aria-pressed", current.activeSide === slot ? "true" : "false");
        ui.list.replaceChildren(); side.rows.forEach(row => ui.list.appendChild(inspectionRecord(row, slot)));
        if (!side.rows.length && !current.loading) ui.list.appendChild(node("p", "analysis-session-note", side.reason || (side.matchedN === 0 ? "No matching records in this group." : current.error ? "Records have not loaded." : "Records are unavailable for this group.")));
      });
      inspectionRetry.hidden = !current.error; inspectionRetry.disabled = current.loading;
      inspectionMore.hidden = !Object.values(current.sides).some(side => Number.isFinite(side.matchedN) && side.matchedN > current.nextOffset);
      inspectionMore.disabled = current.loading || Boolean(current.error);
      if (!current.loading && current.pageControlFocus) {
        current.pageControlFocus = false;
        if ([inspectionMore, inspectionRetry, inspectionDialog, doc.body].includes(doc.activeElement)) {
          const focus = current.error ? inspectionRetry : inspectionMore.hidden ? closeInspectionButton : inspectionMore;
          focus.focus?.({ preventScroll: true });
        }
      }
      if (typeof scrollTop === "number") inspectionBody.scrollTop = scrollTop;
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
      if (isExternalAxis()) {
        const entry = externalEntry();
        return axis === "collections" ? collectionDimension(entry) : entry?.result?.dimensions.find(value => "external:" + value.key === axis);
      }
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
      const lower = row[side + "LowerCount"], upper = row[side + "UpperCount"], hasBounds = Number.isFinite(lower) && Number.isFinite(upper);
      const baseText = Number.isFinite(n) ? (Number.isFinite(share) ? percent(share) + " · " : "") + count(n) : "Not available", rangeText = hasBounds ? count(lower) + "–" + count(upper) + " stable–possible" : "";
      return { count: n, share, baseText, rangeText, text: baseText + (rangeText ? " · " + rangeText : "") };
    }
    function chartRow(row, kind, dimension) {
      const canInspect = typeof config.onInspectComparison === "function" && [row.aCount, row.bCount].some(value => Number.isFinite(value) && value > 0), version = chartVersion;
      let item;
      if (canInspect) item = button("", () => { if (version === chartVersion) return openInspection(Object.assign({}, row, { key: kind ? "__unknown__" : row.key }), dimension, item); }, "analysis-session-chart-row analysis-session-row-inspect" + (kind ? " analysis-session-unknown" : ""), false);
      else item = node("div", "analysis-session-chart-row" + (kind ? " analysis-session-unknown" : ""));
      const top = node("div", "analysis-session-row-heading");
      top.appendChild(node("strong", "", row.label));
      const values = [sideValue(row, "A"), sideValue(row, "B")], difference = values.every(value => Number.isFinite(value.share)) ? Math.abs(values[0].share - values[1].share) : null;
      if (!kind && axis !== "coverage" && difference !== null) top.appendChild(node("span", "analysis-session-difference", (difference * 100).toFixed(1) + " pp difference"));
      if (canInspect) {
        top.appendChild(node("span", "analysis-session-inspect-hint", "Inspect"));
        item.setAttribute("aria-label", "Inspect " + row.label + " records. A: " + values[0].text + ". B: " + values[1].text + ".");
        item.setAttribute("data-comparison-domain-key", dimension.key || axis); item.setAttribute("data-comparison-row-key", kind ? "__unknown__" : row.key);
      }
      item.appendChild(top);
      ["A", "B"].forEach((slot, index) => {
        const value = values[index], line = node("div", "analysis-session-bar-line analysis-session-side-" + slot.toLowerCase()), letter = node("span", "analysis-session-bar-letter", slot);
        const track = node("span", "analysis-session-bar-track"), fill = node("span", "analysis-session-bar-fill");
        track.setAttribute("aria-hidden", "true"); fill.style.width = Number.isFinite(value.share) ? Math.min(1, Math.max(0, value.share)) * 100 + "%" : "0%";
        if (!Number.isFinite(value.share)) track.className += " analysis-session-bar-unavailable";
        track.appendChild(fill);
        const exact = node("span", "analysis-session-bar-value"); exact.appendChild(node("span", "", value.baseText));
        if (value.rangeText) exact.appendChild(node("small", "analysis-session-count-bounds", value.rangeText));
        line.append(letter, track, exact); item.appendChild(line);
      });
      return item;
    }
    function addDataTable(parent, rows, unit) {
      const detail = node("details", "analysis-session-data"); detail.open = tableOpen;
      const version = chartVersion;
      detail.addEventListener("toggle", () => { if (mode === "compare" && version === chartVersion) tableOpen = detail.open; }); detail.appendChild(node("summary", "", "View exact data"));
      const wrapper = node("div", "analysis-session-table-wrap"), table = node("table", "analysis-session-table");
      table.appendChild(node("caption", "", "Count and share of all " + (unit || "captured reports") + " in each group"));
      const head = node("thead"), headings = node("tr");
      ["Category", "A", "B"].forEach(text => { const cell = node("th", "", text); cell.setAttribute("scope", "col"); headings.appendChild(cell); }); head.appendChild(headings); table.appendChild(head);
      const body = node("tbody"); rows.forEach(row => { const line = node("tr"), label = node("th", "", row.label); label.setAttribute("scope", "row"); line.appendChild(label); ["A", "B"].forEach(slot => { const value = sideValue(row, slot); line.appendChild(node("td", "", value.text)); }); body.appendChild(line); });
      table.appendChild(body); wrapper.appendChild(table); detail.appendChild(wrapper); parent.appendChild(detail);
    }
    function addMethodDetails(parent, notes) {
      const values = [...new Set((notes || []).map(value => String(value).trim()).filter(Boolean))];
      if (!values.length) return;
      const detail = node("details", "analysis-session-method-details"), version = chartVersion; detail.open = methodsOpen;
      detail.appendChild(node("summary", "", "Scope & calculation details"));
      values.forEach(value => detail.appendChild(node("p", "analysis-session-note analysis-session-method-note", value)));
      detail.addEventListener("toggle", () => { if (mode === "compare" && version === chartVersion) methodsOpen = detail.open; });
      parent.appendChild(detail);
    }
    function renderComparison(current, force) {
      const model = current.comparison, currentTopic = topic();
      if (mode !== "compare" || !model || !current.groups?.A || !current.groups?.B) return;
      title.textContent = currentTopic.label + " · Compare A / B";
      renderCards(current);
      const shared = model.overlapCount ?? model.overlap?.reportN;
      overlap.textContent = (isExternalAxis() ? "Held report groups: " : "") + count(shared) + " shared " + (shared === 1 ? "report" : "reports") + (model.overlap ? " · " + percent(model.overlap.shareA) + " of A · " + percent(model.overlap.shareB) + " of B" : "");
      details.children[0].textContent = "Group details · " + count(shared) + " shared " + (shared === 1 ? "report" : "reports");
      renderSettings();
      const external = isExternalAxis(), entry = external ? ensureExternal() : externalEntry();
      externalStatus.hidden = !external || entry?.status === "ready";
      retryExternal.hidden = entry?.status !== "error";
      if (external && entry?.status !== "ready") {
        chart.replaceChildren(); chart.hidden = true; unavailable.hidden = true; caveat.hidden = true;
        measurePicker.hidden = true;
        externalStatus.setAttribute("data-error", entry?.status === "error" ? "true" : "false");
        externalMessage.textContent = entry?.status === "error" ? entry.error : "Preparing " + (section === "encounters" ? "collection accounts" : currentTopic.label.toLowerCase()) + " for A and B…";
        Object.entries(tabs).forEach(([key, tab]) => {
          const visible = section === "encounters" && (currentTopic.axes || []).includes(key);
          tab.hidden = !visible; tab.setAttribute("aria-selected", visible && key === axis ? "true" : "false"); tab.tabIndex = visible && key === axis ? 0 : -1;
        });
        tabList.hidden = section !== "encounters"; lastComparison = null; return;
      }
      const axes = availableAxes(), supported = Boolean(axes.length);
      if (entry?.status === "ready") entry.result.dimensions.forEach(value => createTab("external:" + value.key, value.label));
      const usePicker = supported && axes.length > 8;
      tabList.hidden = !supported || usePicker; measurePicker.hidden = !usePicker;
      unavailable.hidden = supported; chart.hidden = !supported; caveat.hidden = !supported;
      if (!supported) {
        const reason = entry?.result?.unavailableReason;
        unavailableText.textContent = reason ? reason.length > 220 ? reason.slice(0, 217) + "…" : reason : currentTopic.unavailable || "No comparable fields are available for these groups.";
        unavailableNotes.replaceChildren(); addMethodDetails(unavailableNotes, entry?.result?.notes || []);
        chart.replaceChildren(); lastComparison = null; return;
      }
      if (!axes.includes(axis)) axis = axes[0];
      Object.entries(tabs).forEach(([key, tab]) => {
        const visible = axes.includes(key), selected = visible && axis === key;
        tab.hidden = !visible; tab.setAttribute("aria-selected", selected ? "true" : "false"); tab.tabIndex = selected ? 0 : -1;
      });
      axes.forEach(key => { if (tabs[key]) tabList.appendChild(tabs[key]); });
      if (usePicker) {
        const optionsKey = JSON.stringify(axes.map(key => [key, tabs[key].textContent]));
        if (measureOptionsKey !== optionsKey) {
          measureOptionsKey = optionsKey; measureSelect.replaceChildren();
          axes.forEach(key => { const option = node("option", "", tabs[key].textContent); option.value = key; measureSelect.appendChild(option); });
        }
        measureSelect.value = axis;
        if (tabList.contains?.(doc.activeElement)) measureSelect.focus?.({ preventScroll: true });
      }
      if (!force && lastComparison === model) return;
      lastComparison = model; chartVersion++;
      chart.setAttribute("role", usePicker ? "region" : "tabpanel");
      if (usePicker) { chart.removeAttribute("aria-labelledby"); chart.setAttribute("aria-label", tabs[axis].textContent + " · A/B comparison"); }
      else { chart.removeAttribute("aria-label"); chart.setAttribute("aria-labelledby", id + "-" + axis); }
      chart.replaceChildren();
      const data = rowsFor(current);
      if (!data) { chart.appendChild(node("p", "analysis-session-empty", "No collection material classification is available for these groups.")); return; }
      const bothAvailable = data.coverage || data.a?.available && data.b?.available;
      const chronological = data.order === "source" || ["calendarMonth", "weekday", "timeOfDay", "year", "duration", "witnessCount"].includes(axis);
      const ranked = data.rows.slice();
      if (!chronological) ranked.sort((a, b) => {
        const difference = row => Number.isFinite(row.aShareOfReports) && Number.isFinite(row.bShareOfReports) ? Math.abs(row.aShareOfReports - row.bShareOfReports) : -1;
        return bothAvailable ? difference(b) - difference(a) || String(a.label).localeCompare(String(b.label)) : Math.max(b.aCount || 0, b.bCount || 0) - Math.max(a.aCount || 0, a.bCount || 0) || String(a.label).localeCompare(String(b.label));
      });
      const unit = data.external ? data.unit.replace(/_/g, " ") : "captured reports", totalA = data.external ? data.a.totalN : model.a.reportN, totalB = data.external ? data.b.totalN : model.b.reportN;
      chart.appendChild(node("p", "analysis-session-denominator", "Descriptive · Share of all " + unit + " · A: " + count(totalA) + " · B: " + count(totalB) + "."));
      const fieldCoverage = data.coverage ? "Date coverage includes dates of any recorded precision." : "Field indexed · A: " + (data.a?.available && Number.isFinite(data.a.eligibleN) ? count(data.a.eligibleN) + " of " + count(totalA) : "not available") + " · B: " + (data.b?.available && Number.isFinite(data.b.eligibleN) ? count(data.b.eligibleN) + " of " + count(totalB) : "not available") + (data.multiLabel ? (data.external ? ". One record" : ". A report") + " may have several labels." : ".");
      chart.appendChild(node("p", "analysis-session-note", fieldCoverage));
      if (data.uncertainty) chart.appendChild(node("p", "analysis-session-note analysis-session-uncertainty-note", data.uncertainty.note || "Stable–possible counts span sampled source-time intervals. These ranges are not confidence intervals."));
      caveat.textContent = data.external ? "Counts describe " + unit + " in the derived A/B populations. Records and source accounts may overlap. Differences do not establish independent incidents or a causal relationship."
        : "Counts describe captured catalog reports. Groups may overlap, and different reports may describe the same incident. Differences do not establish a causal relationship.";
      const coverageLabels = { eligibleExactDateN: "eligible exact dates", verifiedTimeN: "verified times", dateOnlyN: "date-only estimates", stableN: "stable classifications", ambiguousN: "classifications may change within the sampled interval", skyEligibleN: "sky-position eligible", verifiedInputN: "verified time/location inputs", missingInputN: "missing required inputs" };
      const timeCoverage = ["a", "b"].flatMap(slot => {
        const items = Object.entries(data[slot]?.coverage || {}).filter(([key, value]) => coverageLabels[key] && Number.isFinite(value)).map(([key, value]) => count(value) + " " + coverageLabels[key]);
        return items.length ? [slot.toUpperCase() + " time/input coverage: " + items.join(" · ") + "."] : [];
      });
      if (data.external) addMethodDetails(chart, [...(entry.result.notes || []), ...(data.notes || []), ...timeCoverage,
        ...(data.a?.reason ? ["A: " + data.a.reason] : []), ...(data.a?.notes || []).map(note => "A: " + note),
        ...(data.b?.reason ? ["B: " + data.b.reason] : []), ...(data.b?.notes || []).map(note => "B: " + note)]);
      if (axis === "year") chart.appendChild(node("p", "analysis-session-note", "Different date windows naturally occupy different years. Use Month of year, Day of week or Time of day to compare recurring patterns."));
      if (!data.coverage && !bothAvailable) {
        const reason = data.external && !data.a?.available && !data.b?.available ? [data.a?.reason && "A: " + data.a.reason, data.b?.reason && "B: " + data.b.reason].filter(Boolean).join(" ") : "";
        const shortReason = reason ? " " + (reason.length > 260 ? reason.slice(0, 257) + "…" : reason) : "";
        chart.appendChild(node("p", "analysis-session-missing", "Missing information is not a zero count. " + (!data.a?.available && !data.b?.available ? "This field is unavailable for both groups." + (data.external ? shortReason : " Recapture the groups after the relevant Analysis data is ready.") : "This field is unavailable for group " + (!data.a?.available ? "A" : "B") + ".")));
      }
      const limit = chronological ? 12 : 8;
      if (ranked.length) {
        const scale = node("div", "analysis-session-scale"); scale.setAttribute("aria-hidden", "true"); scale.append(node("span", "", "0%"), node("span", "", "50%"), node("span", "", "100%")); chart.appendChild(scale);
        if (!data.coverage) chart.appendChild(node("p", "analysis-session-rank-note", (chronological ? "Calendar / category order" : bothAvailable ? "Largest percentage-point differences first" : "Most reports first") + (ranked.length > limit ? " · Showing " + (showAll ? count(ranked.length) : count(limit)) + " of " + count(ranked.length) : "")));
        const rows = node("div", "analysis-session-chart-rows"); ranked.slice(0, showAll ? undefined : limit).forEach(row => rows.appendChild(chartRow(row, null, data))); chart.appendChild(rows);
        if (ranked.length > limit) {
          const version = chartVersion;
          const more = button(showAll ? "Show fewer" : "Show all " + count(ranked.length) + " categories", () => { if (version !== chartVersion) return; showAll = !showAll; renderComparison(state(), true); chart.querySelector?.(".analysis-session-show-all")?.focus(); }, "analysis-session-show-all", false); chart.appendChild(more);
        }
      } else chart.appendChild(node("p", "analysis-session-empty", "No indexed categories to display for these groups."));
      const exactRows = ranked.slice();
      if (data.unknown && (Number.isFinite(data.unknown.aCount) || Number.isFinite(data.unknown.bCount))) {
        const unknown = Object.assign({ label: "Unknown / not indexed" }, data.unknown);
        chart.appendChild(chartRow(unknown, "unknown", data)); exactRows.push(unknown);
      }
      if (exactRows.length) addDataTable(chart, exactRows, unit);
    }
    function renderBusy() {
      const busy = externalBusy || pending > 0, loading = mode === "compare" && isExternalAxis() && externalEntry()?.status === "loading";
      panel.setAttribute("aria-busy", busy ? "true" : "false"); board.setAttribute("aria-busy", busy || loading ? "true" : "false");
      mutationButtons.forEach(el => { el.disabled = busy || Boolean(el.sessionUnavailable); });
      compareButton.disabled = busy || !state().comparison; currentButton.disabled = busy;
      applySettings.disabled = busy;
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
        ui.summaryCount.textContent = slot + " · " + (group ? reports(reportCount(group)) : "Not set");
        ui.summaryDate.textContent = group ? scopeLabel(group) : ""; ui.summary.title = group ? group.label + " · " + scopeLabel(group) + " · " + filterSummary(group) : "";
      });
      heldSummary.hidden = !(a && b); panel.setAttribute("data-groups-ready", a && b ? "true" : "false");
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
      if (changed) { closeInspection(false); externalCache.clear(); cacheA = a; cacheB = b; }
      if (completeNow) edits.open = false; else if (!pair) edits.open = true;
      if (!pair && mode === "compare") changeMode("current");
      else if (completeNow) changeMode("compare");
      else { if (changed) lastComparison = null; render(); }
    }
    const unsubscribe = store.subscribe(onStoreChange); onStoreChange();
    return { render, setStatus, setBusy(value) { externalBusy = Boolean(value); if (!destroyed) renderBusy(); },
      setMode: changeMode, getMode() { return mode; }, closeInspection, getSettings() { return Object.assign({}, settings); }, setSettings: updateSettings, setSection(key) {
        if (destroyed) return;
        const next = String(key || "overview").replace(/^analysis-section-/, "").replace(/_/g, "-");
        if (section === next) return;
        closeInspection(false);
        section = next; axis = topic().axes?.[0] || "coverage"; showAll = false; tableOpen = false; methodsOpen = false; lastComparison = null; render();
      }, destroy() {
        if (destroyed) return; closeInspection(false); destroyed = true; externalCache.clear(); if (typeof unsubscribe === "function") unsubscribe(); target.replaceChildren();
        if (comparisonTarget !== target) comparisonTarget.replaceChildren();
      }
    };
  }
  return { create };
});

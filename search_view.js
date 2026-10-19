(function (root, factory) {
  "use strict";
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.UfoSearchView = api;
})(typeof self !== "undefined" ? self : globalThis, function () {
  "use strict";
  let nextId = 0;
  const finiteCount = value => Number.isFinite(value) && value >= 0 ? Math.floor(value) : null;
  const count = value => value == null ? "—" : value.toLocaleString();

  function renderExcerpt(target, options) {
    if (!target || !target.ownerDocument) return null;
    const config = options || {}, doc = target.ownerDocument;
    const segments = Array.isArray(config.segments) ? config.segments.filter(segment => segment && typeof segment.text === "string") : [];
    target.replaceChildren();
    target.className = ((target.className || "").split(/\s+/).filter(value => value && value !== "search-match-excerpt").concat("search-match-excerpt")).join(" ");
    target.hidden = !segments.some(segment => segment.text.length);
    if (target.hidden) return target;
    if (config.label) {
      const label = doc.createElement("span"); label.className = "search-match-excerpt-label";
      label.textContent = String(config.label); target.appendChild(label);
    }
    segments.forEach(segment => {
      const node = doc.createElement(segment.match === true ? "mark" : "span");
      node.textContent = segment.text; target.appendChild(node);
    });
    return target;
  }

  function create(target, configuration) {
    if (!target || !target.ownerDocument) throw new Error("A search tools target is required.");
    const config = configuration || {}, doc = target.ownerDocument, id = "search-tools-" + (++nextId);
    let state = { query: "", status: "idle", complete: false, completedChunks: null, totalChunks: null,
      scannedReports: null, totalReports: null, matchCount: null, canUseSelection: false, busy: false };
    let destroyed = false, pending = 0, generation = 0;
    function node(tag, className, text) {
      const element = doc.createElement(tag); if (className) element.className = className;
      if (text != null) element.textContent = String(text); return element;
    }
    const root = node("div", "search-tools"), coverage = node("div", "search-coverage"),
      heading = node("p", "search-coverage-heading"), detail = node("p", "search-coverage-detail"),
      explanation = node("p", "search-coverage-explanation"), progress = node("progress", "search-coverage-progress"),
      retry = node("button", "search-retry", "Retry missing data"),
      actionStatus = node("p", "search-action-status"), actions = node("div", "search-selection-actions"),
      scopeLabel = node("label", "search-scope-label", "Scope "), scope = node("select", "search-selection-scope"),
      scopeNote = node("p", "search-scope-note"),
      buttons = node("div", "search-selection-buttons"), tips = node("details", "search-tips"),
      tipsHeading = node("summary", "", "Search tips"), tipsBody = node("div", "search-tips-body");
    const actionButtons = [];
    coverage.setAttribute("role", "status"); coverage.setAttribute("aria-live", "polite"); coverage.setAttribute("aria-atomic", "true");
    progress.setAttribute("aria-label", "Full text search coverage"); progress.max = 1;
    retry.type = "button"; actionStatus.setAttribute("role", "status"); actionStatus.setAttribute("aria-live", "polite");
    scope.id = id + "-scope"; scopeLabel.htmlFor = scope.id; scopeNote.id = id + "-scope-note";
    scope.setAttribute("aria-describedby", scopeNote.id);
    [["current", "Shared-filter matches"], ["all", "All search matches"]].forEach(([value, text]) => {
      const option = node("option", "", text); option.value = value; scope.appendChild(option);
    });
    scope.value = "current"; scopeLabel.appendChild(scope); actions.append(scopeLabel, scopeNote, buttons);
    scope.addEventListener("change", render);
    coverage.append(heading, progress, detail, explanation, retry);
    const tip = text => tipsBody.appendChild(node("p", "", text));
    tip("Plain text finds that exact sequence of words, including in unmapped reports.");
    tip('Use AND for both: "soil sample" AND humanoid');
    tip("Use OR for either: water OR plants");
    tip('Use parentheses to group: (soil OR plants) AND "small beings"');
    tip("AND and OR must be uppercase. Full text is checked when you search; it does not load with the initial map.");
    tips.append(tipsHeading, tipsBody); root.append(coverage, actions, actionStatus, tips); target.appendChild(root);

    async function invoke(callback, payload) {
      if (destroyed || typeof callback !== "function" || pending || state.busy) return;
      const token = generation; pending += 1; actionStatus.textContent = ""; actionStatus.removeAttribute("data-error"); render();
      try {
        const result = await callback(payload);
        if (!destroyed && token === generation && result && result.message) actionStatus.textContent = String(result.message);
      } catch (error) {
        if (!destroyed && token === generation) {
          actionStatus.textContent = error && error.message ? String(error.message) : "That action could not be completed. Please try again.";
          actionStatus.setAttribute("data-error", "true");
        }
      } finally { pending -= 1; if (!destroyed) render(); }
    }
    retry.addEventListener("click", () => invoke(config.onRetry, { query: state.query }));
    function action(text, callback, slot) {
      if (typeof callback !== "function") return;
      const button = node("button", "", text); button.type = "button";
      button.addEventListener("click", () => {
        if (button.disabled) return;
        const payload = { query: state.query, scope: scope.value === "all" ? "all" : "current" };
        if (slot) payload.slot = slot;
        return invoke(callback, payload);
      });
      actionButtons.push(button); buttons.appendChild(button);
    }
    action("Use in Analysis", config.onUseSelection);
    action("Hold as A", config.onHoldSelection, "A"); action("Hold as B", config.onHoldSelection, "B");

    function render() {
      if (destroyed) return;
      const chunks = finiteCount(state.completedChunks), total = finiteCount(state.totalChunks),
        scanned = finiteCount(state.scannedReports), reportTotal = finiteCount(state.totalReports), matches = finiteCount(state.matchCount);
      const active = Boolean(String(state.query || "").trim()), scanning = state.status === "searching";
      const complete = state.complete === true && state.status === "complete" && state.summaryOnly !== true &&
        !(total != null && chunks != null && chunks < total);
      const partial = active && !scanning && !complete && state.status !== "idle";
      coverage.hidden = !active; coverage.setAttribute("data-state", scanning ? "searching" : complete ? "complete" : "partial");
      if (scanning) heading.textContent = matches == null ? "Searching full text…" : count(matches) + " matches so far";
      else if (complete) heading.textContent = count(matches) + (matches === 1 ? " matching report" : " matching reports");
      else heading.textContent = matches == null ? "Search incomplete" : count(matches) + " matches so far · incomplete";
      const details = [];
      if (complete) details.push(reportTotal != null ? "All " + count(reportTotal) + " catalog reports indexed" : "Full text index checked");
      else if (total != null && total > 0 && chunks != null) details.push(count(Math.min(chunks, total)) + " / " + count(total) + " full text chunks checked");
      if (!complete && scanned != null) details.push(count(scanned) + (reportTotal != null ? " / " + count(reportTotal) : "") + " reports checked");
      detail.textContent = details.join(" · "); detail.hidden = !details.length;
      progress.hidden = !scanning || total == null || total <= 0 || chunks == null;
      if (!progress.hidden) progress.value = Math.min(chunks / total, 1);
      const message = state.message ? String(state.message) : state.error && (state.error.message || typeof state.error === "string")
        ? String(state.error.message || state.error) : "";
      explanation.textContent = message || (partial
        ? "Some full text could not be checked. These results may be missing reports."
        : scanning ? "Results are still being checked. Analysis actions become available when the search is complete." : "");
      if (state.summaryOnly === true && !complete) explanation.textContent = "Only loaded summaries were checked. Full text results are incomplete." + (message ? " " + message : "");
      explanation.hidden = !explanation.textContent;
      retry.hidden = !partial || typeof config.onRetry !== "function";
      retry.disabled = Boolean(state.busy || pending);
      actions.hidden = !active || !actionButtons.length || matches == null || matches === 0;
      scopeNote.textContent = scope.value === "all" ? "All matching catalog reports, across dates and categories."
        : "Date and category filters apply; includes unmapped reports. Drawn areas are not applied.";
      const unavailable = !complete || state.canUseSelection !== true || Boolean(state.busy || pending);
      actionButtons.forEach(button => {
        button.disabled = unavailable;
        button.title = !complete ? "Complete the full text search before using its reports in Analysis."
          : "Uses every matching report in the selected scope, including reports on other result pages. Map filters stay unchanged.";
      });
      scope.disabled = unavailable;
      root.setAttribute("aria-busy", String(scanning || Boolean(state.busy || pending)));
    }
    render();
    return {
      setState(next) {
        if (destroyed) return;
        const patch = next || {};
        if (Object.prototype.hasOwnProperty.call(patch, "query") && patch.query !== state.query) {
          generation += 1; actionStatus.textContent = ""; actionStatus.removeAttribute("data-error");
        }
        state = Object.assign({}, state, patch); render();
      },
      getState() { return Object.assign({}, state); },
      destroy() { destroyed = true; generation += 1; if (root.parentNode) root.parentNode.removeChild(root); },
    };
  }
  return Object.freeze({ create, renderExcerpt });
});

/* Local review: two levels of navigation over original Analysis elements. */
(function () {
  "use strict";
  const byId = (id) => document.getElementById(id);
  const topicGroups = [
    ["Reporting patterns", ["overview", "time", "craft", "geography", "spatial"]],
    ["Context catalogs", ["crops", "animals", "facilities", "comparisons"]],
    ["Evidence & quality", ["context", "sources-quality"]],
  ];

  function install() {
    const panel = byId("analysis-panel");
    const nav = byId("analysis-section-nav");
    const content = byId("analysis-content");
    const toolbar = byId("analysis-workspace-toolbar");
    if (!panel || !nav || !content || !toolbar || byId("preview-analysis-workspace")) return;
    document.documentElement.classList.add("analysis-navigation-preview");

    const workspace = document.createElement("div");
    workspace.id = "preview-analysis-workspace";
    const rail = document.createElement("aside");
    rail.className = "preview-analysis-topic-rail";
    rail.setAttribute("aria-label", "Analysis topics");
    const title = document.createElement("p");
    title.className = "preview-analysis-nav-title";
    title.textContent = "Explore Analysis";
    rail.append(title, nav);
    const stage = document.createElement("div");
    stage.className = "preview-analysis-stage";
    workspace.append(rail, stage);
    toolbar.insertAdjacentElement("afterend", workspace);
    ["analysis-computation-status", "analysis-state-region", "analysis-content"].forEach((id) => {
      const element = byId(id);
      if (element) stage.appendChild(element);
    });

    const picker = panel.querySelector(".preview-analysis-section-picker");
    const select = picker && picker.querySelector("select");
    topicGroups.forEach(([label, keys]) => {
      const group = document.createElement("div");
      group.className = "preview-analysis-topic-group";
      group.setAttribute("role", "presentation");
      const caption = document.createElement("span");
      caption.className = "preview-analysis-topic-label";
      caption.setAttribute("aria-hidden", "true");
      caption.textContent = label;
      group.appendChild(caption);
      const options = document.createElement("optgroup");
      options.label = label;
      keys.forEach((key) => {
        const button = byId("analysis-section-tab-" + key);
        if (button) group.appendChild(button);
        if (select) {
          const option = [...select.options].find((item) => item.value === "analysis-section-tab-" + key);
          if (option) options.appendChild(option);
        }
      });
      nav.appendChild(group);
      if (select) select.appendChild(options);
    });
    if (picker) {
      picker.querySelector("span").textContent = "Topic";
      toolbar.appendChild(picker);
    }

    const tools = document.createElement("div");
    tools.className = "preview-analysis-workspace-actions";
    const filters = document.createElement("button");
    filters.id = "preview-analysis-filters";
    filters.type = "button";
    filters.className = "secondary-button";
    filters.textContent = "Filters";
    filters.setAttribute("aria-expanded", "false");
    filters.setAttribute("aria-controls", "filters-pane-shell preview-mobile-filters");
    const mapResults = document.createElement("button");
    mapResults.type = "button";
    mapResults.className = "secondary-button";
    mapResults.textContent = "Map results";
    mapResults.addEventListener("click", () => {
      byId("view-tab-map").click();
      if (byId("results-pane-shell").classList.contains("is-collapsed")) byId("expand-results-pane").click();
    });
    tools.append(filters, mapResults);
    const utilities = panel.querySelector(".preview-analysis-utilities");
    if (utilities) tools.appendChild(utilities);
    panel.querySelector(".analysis-header").appendChild(tools);

    const filterPane = byId("filters-pane-shell");
    const filterHome = document.createComment("Original shared-filter position for Map Explorer");
    filterPane.before(filterHome);
    function placeMobileFilters() {
      const mobile = byId("preview-mobile-filters");
      const inAnalysis = document.documentElement.dataset.activePrimaryView === "analysis";
      if (mobile && innerWidth <= 1080 && inAnalysis) {
        if (filterPane.parentElement !== mobile) mobile.appendChild(filterPane);
      } else if (filterPane.previousSibling !== filterHome) {
        filterHome.after(filterPane);
      }
    }
    filters.addEventListener("click", () => {
      const mobile = byId("preview-mobile-filters");
      if (innerWidth <= 1080 && mobile) {
        placeMobileFilters();
        mobile.open = !mobile.open;
        if (mobile.open && filterPane.classList.contains("is-collapsed")) byId("expand-filters-pane").click();
        filters.setAttribute("aria-expanded", String(mobile.open));
        if (mobile.open) mobile.scrollIntoView({ block: "start", behavior: "auto" });
      } else {
        const open = document.documentElement.classList.toggle("preview-analysis-filters-open");
        if (open && byId("filters-pane-shell").classList.contains("is-collapsed")) byId("expand-filters-pane").click();
        filters.setAttribute("aria-expanded", String(open));
      }
    });
    byId("toggle-filters-pane").addEventListener("click", () => {
      document.documentElement.classList.remove("preview-analysis-filters-open");
      filters.setAttribute("aria-expanded", "false");
    });

    const scope = document.createElement("details");
    scope.id = "preview-analysis-filter-scope";
    const scopeSummary = document.createElement("summary");
    scopeSummary.textContent = "Current filters & comparison";
    scope.appendChild(scopeSummary);
    const cohort = byId("preview-analysis-cohort");
    const baseline = byId("analysis-baseline-note");
    if (cohort) scope.appendChild(cohort);
    if (baseline) scope.appendChild(baseline);
    toolbar.appendChild(scope);

    const sections = new Map();
    Object.entries(window.PreviewAnalysisViewGroups || {}).forEach(([key, definitions]) => {
      const section = byId("analysis-section-" + key);
      if (!section) return;
      const groups = definitions.map((definition) => {
        const cards = definition.anchorIds.map((id, index) => {
          const anchor = byId(id);
          const selector = definition.rootSelectors && definition.rootSelectors[index];
          return anchor && (selector ? anchor.closest(selector) : anchor.closest(".analysis-card"));
        }).filter(Boolean);
        return Object.assign({}, definition, { cards: [...new Set(cards)] });
      }).filter((group) => group.cards.length);
      if (groups.length <= 1) return;
      const viewNav = document.createElement("div");
      viewNav.className = "preview-analysis-view-nav";
      viewNav.setAttribute("role", "group");
      viewNav.setAttribute("aria-label", "Views in " + byId("analysis-section-tab-" + key).textContent);
      const caption = document.createElement("span");
      caption.className = "preview-analysis-view-label";
      caption.textContent = "View";
      viewNav.appendChild(caption);
      const entry = { section, groups, viewNav, selected: groups[0].key, buttons: new Map() };
      sections.set(section.id, entry);
      const viewPicker = document.createElement("label");
      viewPicker.className = "preview-analysis-view-picker";
      const viewPickerLabel = document.createElement("span");
      viewPickerLabel.textContent = "View";
      const viewSelect = document.createElement("select");
      viewSelect.setAttribute("aria-label", "View in " + byId("analysis-section-tab-" + key).textContent);
      viewPicker.append(viewPickerLabel, viewSelect);
      viewNav.appendChild(viewPicker);
      function choose(viewKey) {
        entry.selected = viewKey;
        viewSelect.value = viewKey;
        section.dataset.previewAnalysisView = viewKey;
        entry.buttons.forEach((button, buttonKey) => button.setAttribute("aria-pressed", String(buttonKey === viewKey)));
        groups.forEach((group) => {
          const visible = viewKey === "all" || viewKey === group.key;
          group.cards.forEach((card) => {
            card.classList.add("preview-analysis-view-card");
            card.classList.toggle("preview-analysis-view-hidden", !visible);
            card.inert = !visible;
            if (!visible) card.setAttribute("aria-hidden", "true");
            else card.removeAttribute("aria-hidden");
            if (visible && viewKey !== "all" && card.tagName === "DETAILS") card.open = true;
          });
        });
      }
      entry.choose = choose;
      [...groups, {key:"all", label:"All charts"}].forEach((group) => {
        const option = document.createElement("option");
        option.value = group.key;
        option.textContent = group.label;
        viewSelect.appendChild(option);
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = group.label;
        button.dataset.analysisView = group.key;
        button.addEventListener("click", () => choose(group.key));
        entry.buttons.set(group.key, button);
        viewNav.appendChild(button);
      });
      viewSelect.addEventListener("change", () => choose(viewSelect.value));
      const heading = section.querySelector(".analysis-section-heading");
      heading.insertAdjacentElement("afterend", viewNav);
      choose(entry.selected);
    });

    function revealTopicStart() {
      requestAnimationFrame(() => {
        const active = document.querySelector('.analysis-section[aria-hidden="false"]');
        const heading = active && active.querySelector(".analysis-section-heading");
        if (!heading || document.documentElement.dataset.activePrimaryView !== "analysis") return;
        const top = heading.getBoundingClientRect().top;
        const visibleTop = toolbar.getBoundingClientRect().bottom + 12;
        if (top < visibleTop || top > innerHeight * .66) {
          scrollTo({top: Math.max(0, scrollY + top - visibleTop), behavior: "auto"});
        }
      });
    }
    nav.addEventListener("click", (event) => { if (event.target.closest('[role="tab"]')) revealTopicStart(); });
    nav.addEventListener("keydown", (event) => {
      if (["ArrowLeft","ArrowRight","ArrowUp","ArrowDown","Home","End"].includes(event.key)) revealTopicStart();
    });

    document.addEventListener("analysis-preview-reveal-chart", (event) => {
      const detail = event.detail || {};
      const chart = byId(detail.chartId);
      const entry = sections.get(detail.sectionId);
      if (!chart || !entry) return;
      const group = entry.groups.find((item) => item.cards.some((card) => card === chart || card.contains(chart)));
      entry.choose(group ? group.key : "all");
    });
    // Existing jump controls, when reached by assistive navigation, use the native reveal path.
    panel.addEventListener("click", (event) => {
      const shortcut = event.target.closest(".preview-analysis-shortcuts button");
      const controller = window.AnalysisViewController;
      if (!shortcut || !controller || typeof controller._openSupportingChart !== "function") return;
      event.stopImmediatePropagation();
      controller._openSupportingChart(shortcut.getAttribute("aria-controls"));
    }, true);

    let previousSelectedTopic = "";
    function sync() {
      placeMobileFilters();
      nav.setAttribute("aria-orientation", innerWidth > 900 ? "vertical" : "horizontal");
      const selectedTopic = nav.querySelector('[aria-selected="true"]');
      if (selectedTopic && innerWidth > 900 && rail.offsetHeight > 0 && document.documentElement.dataset.activePrimaryView === "analysis") {
        const topicChanged = selectedTopic.id !== previousSelectedTopic;
        previousSelectedTopic = selectedTopic.id;
        const topicRect = selectedTopic.getBoundingClientRect();
        const railRect = rail.getBoundingClientRect();
        if (topicRect.bottom > railRect.bottom) rail.scrollTop += topicRect.bottom - railRect.bottom + 4;
        else if (topicRect.top < railRect.top) rail.scrollTop -= railRect.top - topicRect.top + 4;
        const revealedTopic = selectedTopic.getBoundingClientRect();
        if ((topicChanged || document.activeElement === selectedTopic) && revealedTopic.bottom > innerHeight - 12) {
          scrollTo({top: scrollY + revealedTopic.bottom - innerHeight + 12, behavior: "auto"});
        }
      }
      const controller = window.AnalysisViewController;
      const result = controller && controller.latestResult;
      const accepted = controller && controller.latestMeta && controller.latestMeta.filterSnapshot;
      const time = accepted && accepted.timeRange;
      const text = result && result.summary && time
        ? new Intl.NumberFormat().format(result.summary.activeCount) + " reports · " + (time.mode === "full" ? "All time" : [time.startIso,time.endIso].filter(Boolean).join(" to ")) + " · Filters & comparison"
        : "Current filters & comparison";
      if (scopeSummary.textContent !== text) scopeSummary.textContent = text;
      const mobile = byId("preview-mobile-filters");
      const open = innerWidth <= 1080 && mobile ? mobile.open : document.documentElement.classList.contains("preview-analysis-filters-open");
      filters.setAttribute("aria-expanded", String(open));
    }
    let queued = false;
    const schedule = () => {
      if (queued) return;
      queued = true;
      requestAnimationFrame(() => { queued = false; sync(); });
    };
    new MutationObserver(schedule).observe(panel, {childList:true, subtree:true, characterData:true, attributes:true, attributeFilter:["aria-selected","hidden","data-phase"]});
    if (byId("preview-mobile-filters")) byId("preview-mobile-filters").addEventListener("toggle", sync);
    window.addEventListener("resize", schedule);
    if (window.ResizeObserver) new ResizeObserver(() => {
      panel.style.setProperty("--analysis-toolbar-offset", Math.ceil(toolbar.getBoundingClientRect().height + 20) + "px");
      schedule();
    }).observe(toolbar);
    if (window.ResizeObserver) new ResizeObserver(schedule).observe(rail);
    sync();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", install, {once:true});
  else install();
})();

/* Opt-in walkthrough over the existing controls. Never changes report filters. */
(function () {
  "use strict";
  function install() {
    const content = window.UfoGuidedTourContent, utilities = window.UfoGuidedTourState;
    if (!content || !utilities || document.getElementById("guided-tour-card")) return;
    const byId = (id) => document.getElementById(id);
    let session = null, route = "essentials", index = 0, target = null, origin = null;
    let pageScroll = null, frame = null, renderVersion = 0, restoring = false;
    const scrolls = new Map();
    let observedTarget = null;
    const targetObserver = window.ResizeObserver ? new ResizeObserver(schedulePosition) : null;
    const card = document.createElement("section");
    card.id = "guided-tour-card";
    card.className = "guided-tour-card";
    card.hidden = true;
    card.setAttribute("role", "dialog");
    card.setAttribute("aria-modal", "false");
    card.setAttribute("aria-labelledby", "guided-tour-title");
    card.setAttribute("aria-describedby", "guided-tour-copy guided-tour-hint");
    card.innerHTML = '<div class="guided-tour-kicker"><span id="guided-tour-progress" class="guided-tour-progress"></span><button type="button" class="guided-tour-close" aria-label="Exit guided tour">×</button></div>' +
      '<div aria-live="polite" aria-atomic="true"><h2 id="guided-tour-title" tabindex="-1"></h2><p id="guided-tour-copy"></p></div>' +
      '<p id="guided-tour-hint" class="guided-tour-hint">You can try the highlighted controls. Continue whenever you’re ready.</p>' +
      '<p class="guided-tour-notice" hidden></p><div class="guided-tour-actions"><button type="button" class="guided-tour-back">Back</button><button type="button" class="guided-tour-next">Next</button></div>';
    const highlight = document.createElement("div");
    highlight.className = "guided-tour-highlight";
    highlight.hidden = true;
    highlight.setAttribute("aria-hidden", "true");
    const status = document.createElement("span");
    status.className = "sr-only";
    status.setAttribute("role", "status");
    document.body.append(highlight, card, status);
    const next = card.querySelector(".guided-tour-next"), back = card.querySelector(".guided-tour-back");
    const notice = card.querySelector(".guided-tour-notice");

    function visible(element) {
      if (!element || element.closest('[hidden], [inert], [aria-hidden="true"]')) return false;
      const rect = element.getBoundingClientRect(), style = getComputedStyle(element);
      return rect.width > 0 && rect.height > 0 && style.visibility !== "hidden" && style.display !== "none";
    }
    function controlLease(key, id, attribute, openValue) {
      const control = byId(id);
      if (!control || !session) return;
      session.track(key, () => control.getAttribute(attribute) === openValue, (open) => {
        if ((control.getAttribute(attribute) === openValue) !== open) control.click();
      });
    }
    function paneLease(key, rootId, toggleId, expandId) {
      const root = byId(rootId);
      if (!root || !session) return;
      session.track(key, () => !root.classList.contains("is-collapsed"), (open) => {
        if ((!root.classList.contains("is-collapsed")) !== open) {
          const button = byId(open ? expandId : toggleId);
          if (button) button.click();
        }
      });
    }
    function detailLease(element) {
      if (!element || !session) return;
      const key = "detail:" + element.id;
      session.track(key, () => element.open, (open) => { element.open = open; });
      session.change(key, true);
    }
    function prepare(step) {
      const analysis = step.context.startsWith("analysis-");
      const controller = window.AnalysisViewController;
      if (controller) {
        session.track("hash", () => location.hash, (hash) => history.replaceState(history.state, "", location.pathname + location.search + hash));
        session.track("view", () => controller.getActiveView(), (view) => controller.setActiveView(view, {source:"guided-tour"}));
        session.track("topic", () => controller.activeSectionId, (topic) => controller.setActiveSection(topic, {source:"guided-tour", scrollLink:false}));
        // Analysis re-renders honor its section URL. Keep that URL aligned with
        // the demonstrated topic, then restore it along with the prior view.
        if (analysis && !byId("view-tab-analysis").disabled) {
          session.change("hash", "#" + (step.context === "analysis-comparisons" ? "analysis-section-comparisons" : "analysis-section-overview"));
        }
        session.change("view", analysis ? "analysis" : "map");
        // Entering Analysis may honor a saved section hash; it is presentation only.
        session.capture("topic");
        if (analysis && !byId("view-tab-analysis").disabled) {
          session.change("topic", step.context === "analysis-comparisons" ? "analysis-section-comparisons" : "analysis-section-overview");
        }
      }
      if (!["cases", "filters"].includes(step.context)) {
        session.release("detail:preview-mobile-filters");
        session.release("primary-filters");
        session.release("filters-pane");
      }
      if (["cases", "filters"].includes(step.context)) {
        paneLease("filters-pane", "filters-pane-shell", "toggle-filters-pane", "expand-filters-pane");
        session.change("filters-pane", true);
        if (innerWidth <= 1080) detailLease(byId("preview-mobile-filters"));
        controlLease("primary-filters", "toggle-primary-filters", "aria-expanded", "true");
        session.change("primary-filters", true);
      }
      if (step.context === "results") {
        paneLease("results-pane", "results-pane-shell", "toggle-results-pane", "expand-results-pane");
        session.change("results-pane", true);
      }
      if (step.context === "legend") {
        controlLease("legend", "toggle-map-legend", "aria-expanded", "true");
        session.change("legend", true);
      }
      if (["view", "traces"].includes(step.context)) {
        controlLease("tools", "toggle-map-control-cluster", "aria-expanded", "true");
        session.change("tools", true);
        detailLease(byId("map-control-section-" + step.context));
      }
      if (step.context === "timeline") {
        controlLease("timeline", "toggle-timeline-panel", "aria-expanded", "true");
        session.change("timeline", true);
      }
      if (step.context === "analysis-coverage") {
        const section = byId("analysis-section-overview");
        if (section && section.dataset.previewAnalysisView) {
          session.track("overview-view", () => section.dataset.previewAnalysisView, (view) => {
            const button = section.querySelector('[data-analysis-view="' + view + '"]');
            if (button) button.click();
          });
          session.change("overview-view", "cohort");
        }
      }
    }
    function resolve(step) {
      const candidates = [step.target];
      if (step.context === "cases") candidates.push("#filter-famous-cases");
      if (step.context === "filters") candidates.push("#keyword-search");
      if (step.context === "analysis-topic") candidates.push(".preview-analysis-section-picker", "#analysis-workspace-toolbar");
      if (step.context === "analysis-view") candidates.push("#analysis-workspace-toolbar");
      if (step.context === "analysis-coverage") candidates.push("#analysis-state-region", "#analysis-workspace-toolbar");
      if (step.context === "analysis-comparisons") candidates.push(".preview-analysis-section-picker", "#analysis-workspace-toolbar");
      for (const selector of candidates) {
        const element = document.querySelector(selector);
        if (visible(element)) return element;
      }
      return null;
    }
    function withinContainers(element) {
      let rect = element.getBoundingClientRect();
      for (let parent = element.parentElement; parent && parent !== document.body; parent = parent.parentElement) {
        const style = getComputedStyle(parent);
        if (/(auto|scroll|hidden|clip)/.test(style.overflowX + style.overflowY)) rect = utilities.intersect(rect, parent.getBoundingClientRect());
      }
      return rect;
    }
    function clippedRect(element) {
      return utilities.intersect(withinContainers(element), {left:8, top:8, right:document.documentElement.clientWidth - 8, bottom:innerHeight - 8});
    }
    function position() {
      frame = null;
      if (!session || card.hidden) return;
      const step = content[route][index];
      target = resolve(step);
      if (targetObserver && target !== observedTarget) {
        targetObserver.disconnect();
        observedTarget = target;
        if (target) targetObserver.observe(target);
      }
      const rect = target ? clippedRect(target) : null;
      const cardRect = card.getBoundingClientRect();
      if (innerWidth > 700) {
        const point = utilities.cardPosition(rect, {width:cardRect.width, height:cardRect.height}, {width:document.documentElement.clientWidth, height:innerHeight});
        card.style.left = point.left + "px";
        card.style.top = point.top + "px";
      }
      // A narrow screen uses the space above the bottom-docked card.
      const spotlight = rect && innerWidth <= 700
        ? utilities.intersect(rect, {left:8, top:8, right:document.documentElement.clientWidth - 8, bottom:card.getBoundingClientRect().top - 10}) : rect;
      highlight.hidden = !spotlight || spotlight.width < 4 || spotlight.height < 4;
      if (!highlight.hidden) {
        highlight.style.left = spotlight.left - 3 + "px";
        highlight.style.top = spotlight.top - 3 + "px";
        highlight.style.width = spotlight.width + 6 + "px";
        highlight.style.height = spotlight.height + 6 + "px";
      }
    }
    function schedulePosition() {
      if (session && frame === null) frame = requestAnimationFrame(position);
    }
    function reveal(element) {
      if (!element) return;
      // scrollIntoView also scrolls overflow:hidden map surfaces, moving the
      // map controls out of their frame. Move actual scroll panes explicitly.
      for (let parent = element.parentElement; parent && parent !== document.body; parent = parent.parentElement) {
        const style = getComputedStyle(parent), box = parent.getBoundingClientRect();
        if (parent.scrollHeight > parent.clientHeight && /(auto|scroll)/.test(style.overflowY)) {
          if (!scrolls.has(parent)) scrolls.set(parent, {top:parent.scrollTop, left:parent.scrollLeft});
          const rect = element.getBoundingClientRect();
          parent.scrollTop += rect.top - box.top - Math.max(8, (box.height - Math.min(rect.height, box.height - 16)) / 2);
        }
        if (parent.scrollWidth > parent.clientWidth && /(auto|scroll)/.test(style.overflowX)) {
          if (!scrolls.has(parent)) scrolls.set(parent, {top:parent.scrollTop, left:parent.scrollLeft});
          const rect = element.getBoundingClientRect();
          if (rect.left < box.left) parent.scrollLeft -= box.left - rect.left + 8;
          else if (rect.right > box.right) parent.scrollLeft += rect.right - box.right + 8;
        }
      }
      const box = withinContainers(element);
      const available = innerWidth <= 700 ? Math.max(60, card.getBoundingClientRect().top - 24) : innerHeight;
      const desired = Math.max(12, (available - Math.min(box.height, available - 24)) / 2);
      window.scrollBy({top:box.top - desired, behavior:"instant"});
    }
    async function show() {
      const version = ++renderVersion;
      const step = content[route][index];
      highlight.hidden = true;
      card.hidden = false;
      byId("guided-tour-progress").textContent = (route === "analysis" ? "Analysis" : "Essentials") + " · " + (index + 1) + " of " + content[route].length;
      byId("guided-tour-title").textContent = step.title;
      byId("guided-tour-copy").textContent = step.body;
      back.disabled = index === 0;
      next.textContent = index === content[route].length - 1 ? "Finish" : "Next";
      prepare(step);
      // Let responsive disclosures, relocated panels and map invalidation settle.
      await new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done)));
      if (!session || version !== renderVersion) return;
      target = resolve(step);
      const waiting = step.context.startsWith("analysis-") && byId("view-tab-analysis").disabled;
      notice.hidden = Boolean(target) && !waiting;
      notice.textContent = waiting ? "Analysis becomes available when the catalog is ready. You can revisit this step later." :
        !target ? "This panel is not available in the current view. You can continue or revisit it later." : "";
      if (step.context === "analysis-coverage" && target && target.id !== "analysis-cohort-banner") {
        notice.hidden = false;
        notice.textContent = "The summary is still loading or has no matching reports. Its status is shown here.";
      }
      reveal(target);
      position();
      byId("guided-tour-title").focus({preventScroll:true});
    }
    function start(name, launcher) {
      if (!content[name]) return;
      if (session) finish(false);
      session = new utilities.PresentationSession();
      route = name; index = 0; origin = launcher || document.activeElement;
      pageScroll = {top:scrollY, left:scrollX};
      scrolls.clear();
      show();
    }
    function finish(completed) {
      if (!session) return;
      ++renderVersion;
      restoring = true;
      session.restore();
      session = null;
      restoring = false;
      card.hidden = highlight.hidden = true;
      if (targetObserver) targetObserver.disconnect();
      observedTarget = null;
      if (frame !== null) cancelAnimationFrame(frame);
      frame = null;
      scrolls.forEach((value, element) => element.scrollTo({top:value.top, left:value.left, behavior:"instant"}));
      if (pageScroll) window.scrollTo({...pageScroll, behavior:"instant"});
      if (origin && visible(origin)) origin.focus({preventScroll:true});
      status.textContent = completed ? "Tour complete. You can restart it from Take a tour or try the Analysis tour in Help." : "Tour closed. Your report selections are kept.";
    }
    next.addEventListener("click", () => {
      if (index === content[route].length - 1) finish(true);
      else { index++; show(); }
    });
    back.addEventListener("click", () => { if (index > 0) { index--; show(); } });
    card.querySelector(".guided-tour-close").addEventListener("click", () => finish(false));
    document.addEventListener("keydown", (event) => {
      if (!session) return;
      if (event.key === "Escape") { event.preventDefault(); event.stopPropagation(); finish(false); return; }
      if (!card.contains(event.target) || !["ArrowLeft", "ArrowRight"].includes(event.key)) return;
      event.preventDefault();
      if (event.key === "ArrowLeft") back.click(); else next.click();
    }, true);

    // Native user actions take ownership of the affected layout. Even a toggle
    // closed then reopened is intentional and must not be undone on tour exit.
    const claims = {
      "toggle-filters-pane":"filters-pane", "expand-filters-pane":"filters-pane",
      "toggle-primary-filters":"primary-filters", "toggle-results-pane":"results-pane",
      "expand-results-pane":"results-pane", "toggle-map-legend":"legend",
      "toggle-map-control-cluster":"tools", "toggle-timeline-panel":"timeline",
      "view-tab-map":"view", "view-tab-analysis":"view",
    };
    function claimUserLayout(event) {
      if (!session || restoring || !event.isTrusted) return;
      const element = event.target.closest("button, summary, select, [role=tab]");
      if (!element || card.contains(element)) return;
      if (claims[element.id]) session.claim(claims[element.id]);
      if (element.closest("#analysis-section-nav, .preview-analysis-section-picker")) {
        session.claim("topic"); session.claim("view"); session.claim("hash");
      }
      if (element.closest("#analysis-section-overview .preview-analysis-view-nav")) session.claim("overview-view");
      if (element.id === "workflow-focus-map" || element.id === "focus-map-toggle") {
        ["filters-pane", "results-pane"].forEach((key) => session.claim(key));
      }
      if (element.tagName === "SUMMARY" && element.parentElement.tagName === "DETAILS") session.claim("detail:" + element.parentElement.id);
    }
    document.addEventListener("click", claimUserLayout, true);
    document.addEventListener("change", claimUserLayout, true);
    document.addEventListener("keydown", (event) => {
      if (["Enter", " ", "ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Home", "End"].includes(event.key)) claimUserLayout(event);
    }, true);
    document.addEventListener("scroll", schedulePosition, true);
    window.addEventListener("resize", schedulePosition);
    window.addEventListener("hashchange", () => { if (session && !restoring) session.claim("hash"); });
    if (window.ResizeObserver) new ResizeObserver(schedulePosition).observe(card);
    const viewRoot = byId("analysis-panel");
    if (viewRoot) new MutationObserver(schedulePosition).observe(viewRoot, {childList:true, subtree:true, attributes:true, attributeFilter:["hidden", "aria-selected"]});
    window.addEventListener("ufo:timeline-ready", () => {
      if (session && content[route][index].context.startsWith("analysis-")) show();
      else schedulePosition();
    });

    const launcher = byId("start-guided-tour");
    if (launcher) launcher.addEventListener("click", () => start("essentials", launcher));
    const help = byId("user-guide-body");
    if (help) {
      const launchers = document.createElement("div");
      launchers.className = "guided-tour-launchers";
      launchers.innerHTML = '<button type="button" class="secondary-button" data-guided-tour="essentials">Map tour · 9 steps</button><button id="start-analysis-tour" type="button" class="secondary-button" data-guided-tour="analysis">Analysis tour · 5 steps</button>';
      help.prepend(launchers);
    }
    const actions = document.querySelector(".preview-analysis-workspace-actions");
    if (actions) {
      const button = document.createElement("button");
      button.type = "button"; button.className = "secondary-button";
      button.dataset.guidedTour = "analysis"; button.textContent = "Analysis tour";
      actions.appendChild(button);
    }
    document.addEventListener("click", (event) => {
      const button = event.target.closest("[data-guided-tour]");
      if (button) start(button.dataset.guidedTour, button);
    });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", install, {once:true});
  else install();
})();

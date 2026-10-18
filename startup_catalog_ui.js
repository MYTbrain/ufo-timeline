/* Progressive startup status. The initial map stays usable while the catalog loads. */
(function (root, factory) {
  "use strict";
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.UFOStartupCatalogUI = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

    // Keep map navigation, result inspection, panel layout and appearance usable.
  // These controls can change the report population or require the complete index.
  const CONTROL_SELECTOR = [
    "#view-tab-analysis", "#start-guided-tour", "#primary-filters-body input",
    "#primary-filters-body select", "#primary-filters-body button",
    "#source-section-body input", "#source-section-body select", "#source-section-body button",
    "#type-section-body input", "#type-section-body select", "#type-section-body button",
    "#precision-section-body input", "#precision-section-body select", "#precision-section-body button",
    "#encounter-filter-panel input", "#encounter-filter-panel select", "#encounter-filter-panel button",
    "#timeline-panel-details input", "#timeline-panel-details select", "#timeline-panel-details button",
    "#timeline-handle-left", "#timeline-handle-right", "#reset-time-range",
    "#cluster-header-playback-prev", "#cluster-header-play-pause", "#cluster-header-playback-next",
    "#cluster-playback-prev", "#cluster-play-pause", "#cluster-playback-next", "#cluster-playback-reset",
    "#cluster-playback-speed", "#playback-prev", "#play-pause", "#playback-next", "#playback-reset",
    "#playback-speed", "#playback-window-size", "#timeline-window-presets", "#timeline-flap-presets",
    "#timeline-start-date", "#timeline-end-date", "#timeline-start-date-picker", "#timeline-end-date-picker",
    "#map-mode", "#color-mode", "#cluster-quick-map-mode", "#cluster-quick-trace", "#trace-mode",
    "#map-display-panel input", "#map-display-panel select", "#map-display-panel button",
    "#map-overlays-panel input", "#map-overlays-panel select", "#map-overlays-panel button",
    "#cluster-quick-military", "#cluster-quick-research-sites", "#cluster-quick-crop-circles", "#cluster-quick-animal-mutilations",
    "#trace-controls-panel input", "#trace-controls-panel select", "#trace-controls-panel button",
    "#legend-body input", "#legend-body button", "#map-legend-body input", "#map-legend-body button",
    "#reset-view", "#reset-map-legend", "[data-legend-type-toggle]", "[data-map-legend-event-key]",
    "[data-craft-legend-solo-key]", "[data-craft-legend-bulk]",
    "#area-selection-panel input", "#area-selection-panel select", "#area-selection-panel button",
    "#trace-intersection-controls input", "#trace-intersection-controls select", "#trace-intersection-controls button",
    "#trace-facility-filter input", "#trace-facility-filter select", "#trace-facility-filter button",
    "#cluster-quick-facility-proximity", "#results-area-filter-clear",
    "#map-control-section-encounters input", "#map-control-section-encounters select", "#map-control-section-encounters button",
    "#legend-encounter-layer", "#legend-encounter-unclear",
    "#crop-circle-chronology-controls input", "#crop-circle-chronology-controls select",
    "#crop-circle-chronology-controls button", "#trace-bucket-controls button",
  ].join(", ");
  const GUARD_SELECTOR = CONTROL_SELECTOR + ", #timeline-canvas-wrap, #timeline-selection-body, #timeline-playback-marker";
  const LOCK_TITLE = "Available when the full catalog is ready. You can explore the default map now.";
  const GUARDED_EVENTS = ["click", "change", "input", "keydown", "pointerdown", "mousedown", "touchstart"];

  function count(value) {
    return Number.isFinite(Number(value)) ? Math.max(0, Math.floor(Number(value))) : 0;
  }

  function deriveView(state) {
    const source = state || {};
    const total = count(source.total);
    const loaded = Math.min(count(source.loaded), total || count(source.loaded));
    const percent = total ? Math.min(100, Math.floor(loaded / total * 100)) : null;
    const errorText = source.backgroundError || source.errorText;
    const failed = Boolean(errorText);
    const retrying = Boolean(source.retrying);
    const allDownloaded = total > 0 && loaded === total;
    return {
      visible: (source.mapViewReady === true || source.mapReady === true) && source.fullCatalogReady !== true && source.catalogReady !== true,
      locked: source.fullCatalogReady !== true && source.catalogReady !== true,
      failed: failed,
      title: failed ? "Full catalog paused" : (retrying ? "Retrying full catalog" : "Default map ready"),
      progress: percent,
      progressLabel: failed ? "Loading paused" : (allDownloaded ? "Preparing full-catalog controls…" :
        (total ? "Loading full catalog · " + loaded + "/" + total + " parts" : "Loading full catalog…")),
      progressShortLabel: failed ? "Paused" : (allDownloaded ? "Finalizing…" : (total ? "Catalog · " + loaded + "/" + total : "Catalog loading…")),
      scope: source.scopeLabel ? String(source.scopeLabel) : (source.windowLabel ? "Mapped reports · " + String(source.windowLabel) : "Mapped reports · Default date window"),
      help: failed ? "This map remains available. Retry to unlock dates, search and Analysis." :
        "Explore this map now. Dates, search and Analysis unlock automatically.",
      error: failed ? String(errorText) : "",
      retryAvailable: failed && !retrying,
    };
  }

  function create(options) {
    const config = options || {};
    const doc = config.document || (typeof document !== "undefined" ? document : null);
    if (!doc) throw new Error("A document is required for progressive startup controls.");
    const host = config.host || doc.getElementById("map-control-cluster");
    if (!host) throw new Error("The map tools container is required for progressive startup status.");
    const win = doc.defaultView || (typeof window !== "undefined" ? window : null);
    const locks = new Map();
    let locked = true;
    let disposed = false;
    let currentView = deriveView({});
    let lastAnnouncement = "";
    const card = doc.createElement("section");
    card.id = "startup-catalog-status";
    card.className = "startup-catalog-status";
    card.hidden = true;
    card.setAttribute("aria-label", "Catalog loading status");
    const heading = doc.createElement("strong");
    const summary = doc.createElement("p");
    summary.className = "startup-catalog-progress-copy";
    const scope = doc.createElement("p");
    scope.className = "startup-catalog-scope";
    const help = doc.createElement("p");
    help.className = "startup-catalog-help sr-only";
    const progress = doc.createElement("progress");
    progress.max = 100;
    progress.setAttribute("aria-label", "Full catalog download");
    const retry = doc.createElement("button");
    retry.type = "button";
    retry.className = "secondary-button startup-catalog-retry";
    retry.textContent = "Retry full catalog";
    retry.hidden = true;
    const details = doc.createElement("details");
    details.className = "startup-catalog-error-details";
    details.hidden = true;
    const detailsTitle = doc.createElement("summary");
    detailsTitle.textContent = "Loading details";
    const error = doc.createElement("p");
    details.append(detailsTitle, error);
    const announcement = doc.createElement("span");
    announcement.className = "sr-only";
    announcement.setAttribute("role", "status");
    announcement.setAttribute("aria-live", "polite");
    announcement.setAttribute("aria-atomic", "true");
    card.append(heading, summary, progress, scope, help, retry, details, announcement);
    const before = config.before || doc.getElementById("map-control-cluster-body");
    if (before && before.parentNode === host) host.insertBefore(card, before);
    else host.appendChild(card);

    function lockControl(control) {
      if (!locks.has(control)) {
        locks.set(control, {
          disabled: Boolean(control.disabled),
          title: control.getAttribute("title"),
          ariaDisabled: control.getAttribute("aria-disabled"),
        });
      }
      if (!control.disabled) control.disabled = true;
      if (control.getAttribute("aria-disabled") !== "true") control.setAttribute("aria-disabled", "true");
      if (control.getAttribute("data-catalog-pending") !== "true") control.setAttribute("data-catalog-pending", "true");
      if (control.getAttribute("title") !== LOCK_TITLE) control.setAttribute("title", LOCK_TITLE);
    }

    function refreshLocks() {
      if (disposed || !locked) return;
      doc.querySelectorAll(CONTROL_SELECTOR).forEach(lockControl);
    }

    function releaseLocks() {
      locks.forEach(function (prior, control) {
        control.disabled = prior.disabled;
        if (prior.title == null) control.removeAttribute("title");
        else control.setAttribute("title", prior.title);
        if (prior.ariaDisabled == null) control.removeAttribute("aria-disabled");
        else control.setAttribute("aria-disabled", prior.ariaDisabled);
        control.removeAttribute("data-catalog-pending");
      });
      locks.clear();
    }

    // Dynamic legend/filter controls can be rebuilt during startup. Capture before
    // their own handlers, so a transient enabled state cannot apply a partial filter.
    function guard(event) {
      if (!locked || !event.target || typeof event.target.closest !== "function") return;
      if (!event.target.closest(GUARD_SELECTOR)) return;
      if (event.type === "keydown" && (event.key === "Tab" || event.key === "Escape" ||
          ((event.ctrlKey || event.metaKey) && String(event.key).toLowerCase() === "c"))) return;
      event.preventDefault();
      event.stopImmediatePropagation();
    }

    GUARDED_EVENTS.forEach(function (name) { doc.addEventListener(name, guard, { capture: true, passive: false }); });
    const observer = win && typeof win.MutationObserver === "function" ? new win.MutationObserver(refreshLocks) : null;
    if (observer) observer.observe(doc.body, { childList: true, subtree: true });
    let observing = Boolean(observer);
    retry.addEventListener("click", function () {
      if (!currentView.retryAvailable || retry.disabled || typeof config.onRetry !== "function") return;
      retry.disabled = true;
      config.onRetry();
    });

    function update(state) {
      currentView = deriveView(state);
      locked = currentView.locked;
      if (locked) {
        if (observer && !observing) {
          observer.observe(doc.body, { childList: true, subtree: true });
          observing = true;
        }
        refreshLocks();
      } else {
        if (observer && observing) {
          observer.disconnect();
          observing = false;
        }
        releaseLocks();
      }
      card.hidden = !currentView.visible;
      card.setAttribute("data-state", currentView.failed ? "error" : "loading");
      heading.textContent = currentView.title;
      summary.textContent = currentView.progressShortLabel;
      summary.setAttribute("aria-label", currentView.progressLabel);
      summary.hidden = currentView.retryAvailable;
      scope.textContent = currentView.scope;
      scope.setAttribute("title", currentView.scope + ". " + currentView.help);
      help.textContent = currentView.help;
      if (currentView.progress == null) progress.removeAttribute("value");
      else progress.value = currentView.progress;
      retry.hidden = !currentView.retryAvailable;
      retry.disabled = !currentView.retryAvailable;
      details.hidden = !currentView.failed;
      error.textContent = currentView.error;
      const nextAnnouncement = currentView.visible ? [currentView.title, currentView.scope, currentView.help].join(". ") : "";
      if (nextAnnouncement !== lastAnnouncement) {
        announcement.textContent = nextAnnouncement;
        lastAnnouncement = nextAnnouncement;
      }
      return currentView;
    }

    refreshLocks();
    return {
      update: update,
      refreshLocks: refreshLocks,
      element: card,
      dispose: function () {
        if (disposed) return;
        disposed = true;
        locked = false;
        if (observer) observer.disconnect();
        GUARDED_EVENTS.forEach(function (name) { doc.removeEventListener(name, guard, { capture: true }); });
        releaseLocks();
        card.remove();
      },
    };
  }

  return { create: create, deriveView: deriveView, CONTROL_SELECTOR: CONTROL_SELECTOR, GUARD_SELECTOR: GUARD_SELECTOR };
});

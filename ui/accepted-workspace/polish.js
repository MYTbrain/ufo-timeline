/* Presentation changes for the local preview. No app state or handlers change. */
(function () {
  "use strict";
  document.documentElement.classList.add("faithful-polish-preview");

  function applyPreviewPolish() {
    const toolbox = document.getElementById("map-control-cluster");
    if (toolbox) {
      toolbox.setAttribute("aria-label", "Map tools");
      const heading = toolbox.querySelector(".map-control-cluster-heading");
      if (heading) {
        heading.hidden = false;
        heading.removeAttribute("aria-hidden");
        let title = heading.querySelector(".map-control-cluster-title");
        if (!title) {
          title = document.createElement("strong");
          title.className = "map-control-cluster-title";
          heading.appendChild(title);
        }
        title.textContent = "Map tools";
      }
    }

    const clearTrail = document.getElementById("clear-traces");
    if (clearTrail) {
      clearTrail.textContent = "Clear playback trail";
      clearTrail.title = "Clear accumulated playback trails. Static report connections remain available.";
    }

    const resetMap = document.getElementById("reset-view");
    if (resetMap) {
      resetMap.title = "Restore default filters, date window, map and playback settings; clear the selected case and areas.";
      const actionRow = resetMap.closest(".map-control-action-row");
      if (actionRow) {
        let help = document.getElementById("preview-map-reset-help");
        if (!help) {
          help = document.createElement("p");
          help.id = "preview-map-reset-help";
          help.className = "preview-map-reset-help";
          actionRow.insertAdjacentElement("afterend", help);
        }
        help.textContent = "Also resets filters, dates, the selected case and areas.";
        const describedBy = new Set((resetMap.getAttribute("aria-describedby") || "").split(/\s+/).filter(Boolean));
        describedBy.add(help.id);
        resetMap.setAttribute("aria-describedby", Array.from(describedBy).join(" "));
      }
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", applyPreviewPolish, { once: true });
  } else {
    applyPreviewPolish();
  }
})();

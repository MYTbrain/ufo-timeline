/* Presentation wrapper for the live existing mobile controls, not copied state. */
(function () {
  "use strict";
  function initialize() {
    const shell = document.getElementById("mobile-primary-filters-shell");
    if (!shell || document.getElementById("preview-mobile-filters")) return;
    const disclosure = document.createElement("details");
    disclosure.id = "preview-mobile-filters";
    disclosure.className = "preview-mobile-filters";
    const summary = document.createElement("summary");
    summary.appendChild(document.createTextNode("Filters & cases"));
    const range = document.createElement("span");
    range.className = "preview-mobile-filter-range";
    summary.appendChild(range);
    disclosure.appendChild(summary);
    shell.before(disclosure);
    disclosure.appendChild(shell);
    function updateRange() {
      const start = document.getElementById("start-date");
      const end = document.getElementById("end-date");
      range.textContent = start && end && (start.value || end.value)
        ? (start.value || "Earliest") + " — " + (end.value || "Latest") : "All time";
    }
    disclosure.addEventListener("toggle", function () {
      if (!disclosure.open || window.innerWidth > 1080) return;
      const toggle = document.getElementById("toggle-primary-filters");
      if (toggle && toggle.getAttribute("aria-expanded") === "false") toggle.click();
    });
    document.addEventListener("change", function () { window.requestAnimationFrame(updateRange); });
    document.addEventListener("click", function () { window.requestAnimationFrame(updateRange); });
    const observer = new MutationObserver(updateRange);
    const dateChip = document.getElementById("analysis-date-range-chip-label");
    if (dateChip) observer.observe(dateChip, {childList:true, subtree:true, characterData:true});
    updateRange();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", initialize, {once:true});
  else initialize();
})();

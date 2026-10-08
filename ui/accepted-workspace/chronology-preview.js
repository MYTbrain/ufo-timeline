/* Local review: rearrange the original controls, retaining their IDs and handlers. */
(function () {
  "use strict";

  function arrangeChronology() {
    const panel = document.querySelector(".timeline-panel");
    if (!panel || panel.classList.contains("chronology-preview")) return;
    const header = panel.querySelector(".timeline-header");
    const primaryRow = panel.querySelector(".timeline-primary-row");
    const rangeRow = panel.querySelector(".timeline-range-row");
    const media = panel.querySelector(".timeline-media-group");
    const toggle = document.getElementById("toggle-timeline-panel");
    if (!header || !primaryRow || !rangeRow || !media || !toggle) return;

    panel.classList.add("chronology-preview");
    header.appendChild(toggle);
    panel.querySelector(".timeline-panel-toggle-row").hidden = true;
    toggle.setAttribute("aria-controls", "timeline-panel-details");

    function group(className, title) {
      const section = document.createElement("div");
      section.className = className;
      section.setAttribute("role", "group");
      section.setAttribute("aria-label", title);
      const caption = document.createElement("p");
      caption.className = "chronology-group-label";
      caption.textContent = title;
      const controls = document.createElement("div");
      controls.className = "chronology-group-controls";
      section.append(caption, controls);
      primaryRow.appendChild(section);
      return controls;
    }

    const playback = group("chronology-playback-group", "Playback");
    const display = group("chronology-display-group", "Timeline display");
    const zoom = document.createElement("div");
    zoom.className = "chronology-zoom-buttons";
    zoom.setAttribute("role", "group");
    zoom.setAttribute("aria-label", "Timeline zoom");
    zoom.append(document.getElementById("timeline-zoom-out"), document.getElementById("timeline-zoom-in"));
    media.setAttribute("aria-label", "Playback controls");
    playback.append(media, panel.querySelector(".timeline-speed-field"), panel.querySelector(".timeline-window-field"));
    display.append(zoom, panel.querySelector(".timeline-color-field"));

    const windowHeading = document.createElement("div");
    windowHeading.className = "chronology-window-heading";
    const windowTitle = document.createElement("p");
    windowTitle.className = "chronology-group-label";
    windowTitle.textContent = "Date window";
    windowHeading.append(windowTitle, document.getElementById("reset-time-range"));
    rangeRow.before(windowHeading);
    document.getElementById("timeline-control-strip").hidden = true;
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", arrangeChronology, { once: true });
  } else {
    arrangeChronology();
  }
})();

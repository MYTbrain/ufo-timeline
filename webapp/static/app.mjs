import { fetchAppConfig } from "./config.mjs";
import {
  colorForEvent,
  computeDateExtent,
  filterEvents,
  uniqueValues,
} from "./app-utils.mjs";

const resultsCountEl = document.querySelector("#results-count");
const datasetSpanEl = document.querySelector("#dataset-span");
const legendMinEl = document.querySelector("#legend-min");
const legendMaxEl = document.querySelector("#legend-max");
const legendGradientEl = document.querySelector("#legend-gradient");

const keywordInput = document.querySelector("#keyword-search");
const startDateInput = document.querySelector("#start-date");
const endDateInput = document.querySelector("#end-date");
const sourceFilter = document.querySelector("#source-filter");
const typeFilter = document.querySelector("#type-filter");
const precisionFilter = document.querySelector("#precision-filter");
const hideLowPrecisionToggle = document.querySelector("#hide-low-precision");
const fitResultsButton = document.querySelector("#fit-results");

const map = L.map("map", {
  worldCopyJump: true,
  minZoom: 2,
});

let markerLayer = L.markerClusterGroup({
  chunkedLoading: true,
  chunkInterval: 100,
  chunkDelay: 25,
  spiderfyOnMaxZoom: true,
  showCoverageOnHover: false,
});

map.addLayer(markerLayer);

const state = {
  appConfig: null,
  allEvents: [],
  filteredEvents: [],
};

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function selectedValues(selectEl) {
  return [...selectEl.selectedOptions].map((option) => option.value);
}

function populateSelect(selectEl, values) {
  selectEl.innerHTML = "";
  for (const value of values) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    selectEl.append(option);
  }
}

function buildPopupContent(event) {
  const resolvedPlace = String(event.geocode_display_name || "").trim();
  return `
    <div class="popup-content">
      <h3 class="popup-title">${escapeHtml(event.date_raw || event.sort_date_iso || "Unknown date")}</h3>
      <div class="popup-row"><span class="popup-label">Normalized Date:</span> ${escapeHtml(event.sort_date_iso || event.date_iso || "Unknown")}</div>
      <div class="popup-row"><span class="popup-label">Date Precision:</span> ${escapeHtml(event.date_precision || "unknown")}</div>
      <div class="popup-row"><span class="popup-label">Location:</span> ${escapeHtml(event.location_raw || "Unknown")}</div>
      ${resolvedPlace ? `<div class="popup-row"><span class="popup-label">Resolved Place:</span> ${escapeHtml(resolvedPlace)}</div>` : ""}
      <div class="popup-row"><span class="popup-label">Description:</span> ${escapeHtml(event.description || "No description")}</div>
      <div class="popup-row"><span class="popup-label">Type:</span> ${escapeHtml(event.type || "Unknown")}</div>
      <div class="popup-row"><span class="popup-label">Source:</span> ${escapeHtml(event.source || "Unknown")}</div>
      <div class="popup-row"><span class="popup-label">Location Precision:</span> ${escapeHtml(event.location_precision || "unknown")}</div>
      <div class="popup-row"><span class="popup-label">Coordinate Source:</span> ${escapeHtml(event.coordinate_source || "unresolved")}</div>
    </div>
  `;
}

function createColoredMarker(event, color) {
  const marker = L.marker([event.lat, event.lon], {
    title: `${event.date_raw || event.sort_date_iso || "Unknown"} - ${event.location_raw || event.geocode_display_name || "Unknown location"}`,
    icon: L.divIcon({
      className: "",
      html: `<div class="ufo-dot" style="background:${color}"></div>`,
      iconSize: [12, 12],
      iconAnchor: [6, 6],
      popupAnchor: [0, -8],
    }),
  });
  marker.bindPopup(buildPopupContent(event), {
    maxWidth: 340,
  });
  return marker;
}

function renderLegend(extent) {
  if (!extent) {
    legendMinEl.textContent = "--";
    legendMaxEl.textContent = "--";
    legendGradientEl.style.background = "linear-gradient(90deg, #8aa2b2, #ded4b4)";
    return;
  }

  legendMinEl.textContent = extent.min;
  legendMaxEl.textContent = extent.max;
  legendGradientEl.style.background = "linear-gradient(90deg, hsl(220 72% 44%), hsl(150 70% 46%), hsl(85 60% 48%), hsl(32 74% 50%), hsl(10 68% 36%))";
}

function fitToMarkers() {
  if (!state.filteredEvents.length) {
    return;
  }
  const bounds = markerLayer.getBounds();
  if (bounds.isValid()) {
    map.fitBounds(bounds.pad(0.15), { maxZoom: 7 });
  }
}

function renderMap() {
  markerLayer.clearLayers();
  const extent = computeDateExtent(state.filteredEvents);
  renderLegend(extent);

  for (const event of state.filteredEvents) {
    const color = colorForEvent(event, extent);
    markerLayer.addLayer(createColoredMarker(event, color));
  }

  resultsCountEl.textContent = new Intl.NumberFormat().format(state.filteredEvents.length);
}

function refreshFilters() {
  state.filteredEvents = filterEvents(state.allEvents, {
    keyword: keywordInput.value,
    startDate: startDateInput.value,
    endDate: endDateInput.value,
    sources: selectedValues(sourceFilter),
    types: selectedValues(typeFilter),
    precisions: selectedValues(precisionFilter),
    hideLowPrecision: hideLowPrecisionToggle.checked,
  });

  renderMap();
}

async function loadData() {
  state.appConfig = await fetchAppConfig();

  if (state.appConfig.tileUrl) {
    L.tileLayer(state.appConfig.tileUrl, {
      attribution: state.appConfig.tileAttribution,
      maxZoom: 18,
    }).addTo(map);
  }
  map.setView(state.appConfig.initialCenter, state.appConfig.initialZoom);

  const response = await fetch(state.appConfig.mapEventsUrl);
  if (!response.ok) {
    throw new Error(`Unable to load map events (${response.status})`);
  }
  state.allEvents = await response.json();
  state.filteredEvents = [...state.allEvents];

  populateSelect(sourceFilter, uniqueValues(state.allEvents, "source"));
  populateSelect(typeFilter, uniqueValues(state.allEvents, "type"));
  populateSelect(precisionFilter, uniqueValues(state.allEvents, "location_precision"));

  const datasetExtent = computeDateExtent(state.allEvents);
  datasetSpanEl.textContent = datasetExtent ? `${datasetExtent.min} -> ${datasetExtent.max}` : "Unknown";

  renderMap();
  fitToMarkers();
}

const reactiveInputs = [
  keywordInput,
  startDateInput,
  endDateInput,
  sourceFilter,
  typeFilter,
  precisionFilter,
  hideLowPrecisionToggle,
];

for (const input of reactiveInputs) {
  input.addEventListener("input", refreshFilters);
  input.addEventListener("change", refreshFilters);
}

fitResultsButton.addEventListener("click", fitToMarkers);

loadData().catch((error) => {
  resultsCountEl.textContent = "Error";
  datasetSpanEl.textContent = "Load failed";
  console.error(error);
});

(function () {
  "use strict";

  const button = document.querySelector("#overlay-crop-circles");
  const status = document.querySelector("#crop-circle-status");
  if (!button) return;

  let loadPromise = null;
  let capturedMap = null;

  if (window.L && typeof window.L.map === "function") {
    const createLeafletMap = window.L.map;
    window.L.map = function () {
      capturedMap = createLeafletMap.apply(this, arguments);
      return capturedMap;
    };
    Object.assign(window.L.map, createLeafletMap);
  }

  function civilOrdinal(value) {
    const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(value || "").trim());
    if (!match) return null;
    let year = Number(match[1]);
    const month = Number(match[2]);
    const day = Number(match[3]);
    year -= month <= 2 ? 1 : 0;
    const era = Math.floor(year / 400);
    const yearOfEra = year - era * 400;
    const monthPrime = month + (month > 2 ? -3 : 9);
    const dayOfYear = Math.floor((153 * monthPrime + 2) / 5) + day - 1;
    const dayOfEra = yearOfEra * 365 + Math.floor(yearOfEra / 4) - Math.floor(yearOfEra / 100) + dayOfYear;
    return era * 146097 + dayOfEra - 719468;
  }

  window.UfoTimelineExtensions = Object.freeze({
    getContext: function () {
      const startInput = document.querySelector("#start-date");
      const endInput = document.querySelector("#end-date");
      const lowPrecision = document.querySelector("#hide-low-precision");
      const nonExactDates = document.querySelector("#hide-non-exact-dates");
      const colorMode = document.querySelector("#color-mode");
      return {
        map: capturedMap,
        timeRangeStartOrdinal: civilOrdinal(startInput && startInput.value),
        timeRangeEndOrdinal: civilOrdinal(endInput && endInput.value),
        hideLowPrecisionCoordinates: Boolean(lowPrecision && lowPrecision.checked),
        hideNonExactDates: Boolean(nonExactDates && nonExactDates.checked),
        colorMode: colorMode && colorMode.value ? colorMode.value : "craft_type",
        filterGeneration: 0,
      };
    },
  });

  function setStatus(message, isError) {
    if (!status) return;
    status.textContent = message || "";
    status.classList.toggle("is-error", Boolean(isError));
  }

  function ensureLayerLoaded() {
    if (window.UfoCropCircleLayer) {
      return Promise.resolve(window.UfoCropCircleLayer);
    }
    if (loadPromise) return loadPromise;
    button.disabled = true;
    button.setAttribute("aria-busy", "true");
    setStatus("Loading the crop-circle layer…");
    const attempt = new Promise(function (resolve, reject) {
      const script = document.createElement("script");
      script.src = "./crop_circle_layer.js?v=2026-08-01-crop-circles-v156";
      script.async = true;
      script.onload = function () {
        if (!window.UfoCropCircleLayer) {
          reject(new Error("Crop-circle runtime did not initialize."));
          return;
        }
        resolve(window.UfoCropCircleLayer);
      };
      script.onerror = function () {
        reject(new Error("Crop-circle runtime could not be loaded."));
      };
      document.head.appendChild(script);
    }).finally(function () {
      button.disabled = false;
      button.removeAttribute("aria-busy");
    });
    loadPromise = attempt.catch(function (error) {
      loadPromise = null;
      throw error;
    });
    return loadPromise;
  }

  button.addEventListener("click", function () {
    const nextEnabled = button.getAttribute("aria-pressed") !== "true";
    if (!nextEnabled && window.UfoCropCircleLayer) {
      window.UfoCropCircleLayer.setEnabled(false);
      return;
    }
    ensureLayerLoaded()
      .then(function (layer) {
        return layer.setEnabled(true);
      })
      .catch(function (error) {
        button.setAttribute("aria-pressed", "false");
        button.classList.remove("is-active");
        setStatus(error && error.message ? error.message : String(error), true);
        console.error(error);
      });
  });
})();

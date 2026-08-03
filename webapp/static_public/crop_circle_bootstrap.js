(function () {
  "use strict";

  const button = document.querySelector("#overlay-crop-circles");
  const status = document.querySelector("#crop-circle-status");
  if (!button) return;

  let loadPromise = null;
  let capturedMap = null;
  let coreApi = null;
  let cropFocusRequestGeneration = 0;
  let desiredEnabled = true;
  let defaultActivationStarted = false;

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

  function fallbackContext() {
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
  }

  window.UfoTimelineExtensions = Object.freeze({
    registerCoreApi: function (api) {
      if (!api || typeof api.getContext !== "function") {
        throw new Error("The UFO timeline extension API is invalid.");
      }
      coreApi = api;
      return true;
    },
    getContext: function () {
      return coreApi ? coreApi.getContext() : fallbackContext();
    },
    setCropTraceFocus: function (config) {
      if (!coreApi || typeof coreApi.setCropTraceFocus !== "function") {
        return Promise.reject(new Error("The UFO trace runtime is not ready yet."));
      }
      const generation = ++cropFocusRequestGeneration;
      return new Promise(function (resolve, reject) {
        window.setTimeout(function () {
          if (generation !== cropFocusRequestGeneration) {
            resolve(null);
            return;
          }
          try {
            Promise.resolve(coreApi.setCropTraceFocus(config || {})).then(resolve, reject);
          } catch (error) {
            reject(error);
          }
        }, 0);
      });
    },
    clearCropTraceFocus: function (reason) {
      cropFocusRequestGeneration += 1;
      if (!coreApi || typeof coreApi.clearCropTraceFocus !== "function") return false;
      return coreApi.clearCropTraceFocus(reason || "crop focus cleared");
    },
  });

  function setStatus(message, isError) {
    if (!status) return;
    status.textContent = message || "";
    status.classList.toggle("is-error", Boolean(isError));
  }

  function setDesiredButtonState(enabled) {
    button.setAttribute("aria-pressed", enabled ? "true" : "false");
    button.classList.toggle("is-active", Boolean(enabled));
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
      script.src = "./crop_circle_layer.js?v=2026-08-03-context-layers-default-on-v1";
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

  function reportError(error) {
    desiredEnabled = false;
    setDesiredButtonState(false);
    setStatus(error && error.message ? error.message : String(error), true);
    console.error(error);
  }

  function enableDesiredLayer() {
    if (!desiredEnabled) return Promise.resolve(false);
    setDesiredButtonState(true);
    return ensureLayerLoaded().then(function (layer) {
      if (!desiredEnabled) return false;
      return layer.setEnabled(true);
    }).catch(function (error) {
      reportError(error);
      return false;
    });
  }

  button.addEventListener("click", function () {
    desiredEnabled = !desiredEnabled;
    setDesiredButtonState(desiredEnabled);
    if (!desiredEnabled) {
      if (window.UfoCropCircleLayer) {
        Promise.resolve(window.UfoCropCircleLayer.setEnabled(false)).catch(reportError);
      } else {
        setStatus("Crop circles are off. Turn the layer on to show catalog positions.");
      }
      return;
    }
    enableDesiredLayer();
  });

  setDesiredButtonState(true);
  window.addEventListener("ufo:timeline-ready", function () {
    if (defaultActivationStarted) return;
    defaultActivationStarted = true;
    enableDesiredLayer();
  }, { once: true });
})();

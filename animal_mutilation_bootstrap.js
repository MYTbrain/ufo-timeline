(function () {
  "use strict";

  const toggle = document.querySelector("#overlay-animal-mutilations");
  const browse = document.querySelector("#animal-mutilation-browser-open");
  const status = document.querySelector("#animal-mutilation-status");
  if (!toggle && !browse) return;

  let loadPromise = null;
  let desiredEnabled = true;
  let defaultActivationStarted = false;

  function setStatus(message, isError) {
    if (!status) return;
    status.textContent = message || "";
    status.classList.toggle("is-error", Boolean(isError));
  }

  function setBusy(busy) {
    [toggle, browse].forEach(function (button) {
      if (!button) return;
      button.disabled = Boolean(busy);
      if (busy) button.setAttribute("aria-busy", "true");
      else button.removeAttribute("aria-busy");
    });
  }

  function setDesiredToggleState(enabled) {
    if (!toggle) return;
    toggle.setAttribute("aria-pressed", enabled ? "true" : "false");
    toggle.classList.toggle("is-active", Boolean(enabled));
  }

  function ensureRuntime() {
    if (window.UfoAnimalMutilationLayer) return Promise.resolve(window.UfoAnimalMutilationLayer);
    if (loadPromise) return loadPromise;
    setBusy(true);
    setStatus("Loading Animal Mutilation Reports…");
    const attempt = new Promise(function (resolve, reject) {
      const script = document.createElement("script");
      script.src = "./animal_mutilation_layer.js?v=2026-08-12-context-evidence-v2";
      script.async = true;
      script.onload = function () {
        if (!window.UfoAnimalMutilationLayer) {
          reject(new Error("Animal Mutilation Reports runtime did not initialize."));
          return;
        }
        resolve(window.UfoAnimalMutilationLayer);
      };
      script.onerror = function () {
        reject(new Error("Animal Mutilation Reports runtime could not be loaded."));
      };
      document.head.appendChild(script);
    }).finally(function () {
      setBusy(false);
    });
    loadPromise = attempt.catch(function (error) {
      loadPromise = null;
      throw error;
    });
    return loadPromise;
  }

  function reportError(error) {
    setDesiredToggleState(desiredEnabled);
    setStatus("Animal reports remain included in Analysis; the map overlay could not load. " + (error && error.message ? error.message : String(error)), true);
    console.error(error);
  }

  function enableDesiredLayer() {
    if (!desiredEnabled) return Promise.resolve(false);
    setDesiredToggleState(true);
    return ensureRuntime().then(function (layer) {
      if (!desiredEnabled) return false;
      return layer.setEnabled(true);
    });
  }

  function setEnabled(enabled, origin) {
    desiredEnabled = Boolean(enabled);
    setDesiredToggleState(desiredEnabled);
    if (toggle) toggle.dataset.contextChangeOrigin = String(origin || "shared-control");
    if (!desiredEnabled) {
      const disablePromise = window.UfoAnimalMutilationLayer
        ? Promise.resolve(window.UfoAnimalMutilationLayer.setEnabled(false))
        : Promise.resolve(false);
      return disablePromise.then(function (result) {
        setStatus("Animal reports are excluded from the shared context. Browse remains available.");
        return result;
      }).catch(function (error) {
        reportError(error);
        throw error;
      }).finally(function () {
        if (toggle) delete toggle.dataset.contextChangeOrigin;
      });
    }
    return enableDesiredLayer().catch(function (error) {
      reportError(error);
      throw error;
    }).finally(function () {
      if (toggle) delete toggle.dataset.contextChangeOrigin;
    });
  }

  window.UfoAnimalMutilationBootstrap = Object.freeze({
    setEnabled: setEnabled,
    getDesiredEnabled: function () { return desiredEnabled; },
    ensureLoaded: ensureRuntime,
  });

  if (toggle) {
    toggle.addEventListener("click", function () {
      if (typeof window.setContextLayerEnabled === "function") {
        window.setContextLayerEnabled("animals", !desiredEnabled, "map-control").catch(function () {});
        return;
      }
      setEnabled(!desiredEnabled, "map-control").catch(function () {});
    });
  }

  if (browse) {
    browse.addEventListener("click", function () {
      ensureRuntime().then(function (layer) {
        return layer.openBrowser(browse);
      }).catch(reportError);
    });
  }

  setDesiredToggleState(true);
  window.addEventListener("ufo:timeline-ready", function () {
    if (defaultActivationStarted) return;
    defaultActivationStarted = true;
    if (typeof window.setContextLayerEnabled === "function") {
      window.setContextLayerEnabled("animals", true, "startup-default").catch(function (error) {
        if (desiredEnabled) reportError(error);
      });
      return;
    }
    enableDesiredLayer().catch(reportError);
  }, { once: true });
})();

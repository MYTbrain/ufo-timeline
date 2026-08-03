(function () {
  "use strict";

  const toggle = document.querySelector("#overlay-animal-mutilations");
  const browse = document.querySelector("#animal-mutilation-browser-open");
  const status = document.querySelector("#animal-mutilation-status");
  if (!toggle && !browse) return;

  let loadPromise = null;

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

  function ensureRuntime() {
    if (window.UfoAnimalMutilationLayer) return Promise.resolve(window.UfoAnimalMutilationLayer);
    if (loadPromise) return loadPromise;
    setBusy(true);
    setStatus("Loading Animal Mutilation Reports…");
    const attempt = new Promise(function (resolve, reject) {
      const script = document.createElement("script");
      script.src = "./animal_mutilation_layer.js?v=2026-08-02-animal-mutilations-v1";
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
    if (toggle) {
      toggle.setAttribute("aria-pressed", "false");
      toggle.classList.remove("is-active");
    }
    setStatus(error && error.message ? error.message : String(error), true);
    console.error(error);
  }

  if (toggle) {
    toggle.addEventListener("click", function () {
      const nextEnabled = toggle.getAttribute("aria-pressed") !== "true";
      if (!nextEnabled && window.UfoAnimalMutilationLayer) {
        window.UfoAnimalMutilationLayer.setEnabled(false).catch(reportError);
        return;
      }
      ensureRuntime().then(function (layer) {
        return layer.setEnabled(true);
      }).catch(reportError);
    });
  }

  if (browse) {
    browse.addEventListener("click", function () {
      ensureRuntime().then(function (layer) {
        return layer.openBrowser(browse);
      }).catch(reportError);
    });
  }
})();

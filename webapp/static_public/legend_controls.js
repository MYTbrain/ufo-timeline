(function (root, factory) {
  "use strict";

  const api = factory();
  if (typeof module === "object" && module && module.exports) {
    module.exports = api;
  }
  if (root) {
    root.UfoLegendControls = api;
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const EVENT_SELECTION_MODES = new Set(["all", "subset", "none"]);

  function uniqueKeys(values) {
    const seen = new Set();
    const output = [];
    (Array.isArray(values) ? values : []).forEach(function (value) {
      const key = String(value == null ? "" : value).trim();
      if (!key || seen.has(key)) return;
      seen.add(key);
      output.push(key);
    });
    return output;
  }

  function normalizeEventSelection(selection, fallbackColorMode) {
    const source = selection && typeof selection === "object" ? selection : {};
    const mode = EVENT_SELECTION_MODES.has(source.mode) ? source.mode : "all";
    const selectedKeys = mode === "subset" ? uniqueKeys(source.selectedKeys) : [];
    return {
      mode: mode === "subset" && !selectedKeys.length ? "none" : mode,
      colorMode: String(source.colorMode || fallbackColorMode || "craft_type"),
      selectedKeys,
    };
  }

  function eventKeyActive(selection, key, fallbackColorMode) {
    const normalized = normalizeEventSelection(selection, fallbackColorMode);
    if (normalized.mode === "all") return true;
    if (normalized.mode === "none") return false;
    return normalized.selectedKeys.indexOf(String(key || "")) !== -1;
  }

  function toggleEventKey(selection, key, availableKeys, fallbackColorMode) {
    const normalized = normalizeEventSelection(selection, fallbackColorMode);
    const targetKey = String(key == null ? "" : key).trim();
    if (!targetKey) return normalized;

    let nextKeys;
    if (normalized.mode === "all" || normalized.mode === "none") {
      nextKeys = [targetKey];
    } else {
      const selected = new Set(normalized.selectedKeys);
      if (selected.has(targetKey)) {
        selected.delete(targetKey);
      } else {
        selected.add(targetKey);
      }
      nextKeys = Array.from(selected);
    }

    if (!nextKeys.length) {
      return {
        mode: "none",
        colorMode: normalized.colorMode,
        selectedKeys: [],
      };
    }

    const available = uniqueKeys(availableKeys);
    if (available.length && available.every(function (availableKey) {
      return nextKeys.indexOf(availableKey) !== -1;
    })) {
      return {
        mode: "all",
        colorMode: normalized.colorMode,
        selectedKeys: [],
      };
    }

    return {
      mode: "subset",
      colorMode: normalized.colorMode,
      selectedKeys: uniqueKeys(nextKeys),
    };
  }

  function resetEventSelection(colorMode) {
    return {
      mode: "all",
      colorMode: String(colorMode || "craft_type"),
      selectedKeys: [],
    };
  }

  function toggleGroupedOverlay(parentActive, visibility, key, availableKeys) {
    const targetKey = String(key == null ? "" : key).trim();
    const keys = uniqueKeys((availableKeys || []).concat(targetKey ? [targetKey] : []));
    const nextVisibility = {};
    keys.forEach(function (availableKey) {
      nextVisibility[availableKey] = Boolean(visibility && visibility[availableKey]);
    });
    if (!targetKey) {
      return {
        active: Boolean(parentActive),
        visibility: nextVisibility,
      };
    }

    if (!parentActive) {
      keys.forEach(function (availableKey) {
        nextVisibility[availableKey] = availableKey === targetKey;
      });
      return {
        active: true,
        visibility: nextVisibility,
      };
    }

    nextVisibility[targetKey] = !nextVisibility[targetKey];
    const anyActive = keys.some(function (availableKey) {
      return nextVisibility[availableKey];
    });
    return {
      active: anyActive,
      visibility: nextVisibility,
    };
  }

  return Object.freeze({
    eventKeyActive,
    normalizeEventSelection,
    resetEventSelection,
    toggleEventKey,
    toggleGroupedOverlay,
    uniqueKeys,
  });
});

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

  function sameKeyUniverse(left, right) {
    const leftKeys = uniqueKeys(left);
    const rightKeys = uniqueKeys(right);
    if (leftKeys.length !== rightKeys.length) return false;
    const rightSet = new Set(rightKeys);
    return leftKeys.every(function (key) {
      return rightSet.has(key);
    });
  }

  function normalizeSelectionForUniverse(selection, availableKeys, fallbackColorMode) {
    const normalized = normalizeEventSelection(selection, fallbackColorMode);
    const available = uniqueKeys(availableKeys);
    if (normalized.mode !== "subset") return normalized;
    const availableSet = new Set(available);
    const selectedKeys = normalized.selectedKeys.filter(function (key) {
      return availableSet.has(key);
    });
    return {
      mode: selectedKeys.length ? "subset" : "none",
      colorMode: normalized.colorMode,
      selectedKeys,
    };
  }

  function activeKeysForSelection(selection, availableKeys) {
    const available = uniqueKeys(availableKeys);
    if (selection.mode === "all") return available.slice();
    if (selection.mode === "none") return [];
    const availableSet = new Set(available);
    return selection.selectedKeys.filter(function (key) {
      return availableSet.has(key);
    });
  }

  function selectionFromActiveKeys(activeKeys, availableKeys, colorMode) {
    const available = uniqueKeys(availableKeys);
    const availableSet = new Set(available);
    const selectedKeys = uniqueKeys(activeKeys).filter(function (key) {
      return availableSet.has(key);
    });
    if (!selectedKeys.length) {
      return {
        mode: "none",
        colorMode: String(colorMode || "craft_type"),
        selectedKeys: [],
      };
    }
    const selectedSet = new Set(selectedKeys);
    if (available.length && available.every(function (key) {
      return selectedSet.has(key);
    })) {
      return resetEventSelection(colorMode);
    }
    return {
      mode: "subset",
      colorMode: String(colorMode || "craft_type"),
      selectedKeys,
    };
  }

  function craftStateSource(value) {
    if (value && typeof value === "object" && value.selection) {
      return {
        selection: value.selection,
        solo: value.solo || null,
      };
    }
    return {
      selection: value,
      solo: null,
    };
  }

  function normalizeCraftSelectionState(value, availableKeys, fallbackColorMode) {
    const source = craftStateSource(value);
    const available = uniqueKeys(availableKeys);
    const selection = normalizeSelectionForUniverse(source.selection, available, fallbackColorMode);
    const soloSource = source.solo && typeof source.solo === "object" ? source.solo : null;
    if (!soloSource) {
      return { selection, solo: null };
    }

    const soloKey = String(soloSource.key == null ? "" : soloSource.key).trim();
    const soloUniverse = uniqueKeys(soloSource.universeKeys);
    const visibleKeys = activeKeysForSelection(selection, available);
    const validSolo = Boolean(
      soloKey &&
      available.indexOf(soloKey) !== -1 &&
      sameKeyUniverse(soloUniverse, available) &&
      selection.mode === "subset" &&
      visibleKeys.length === 1 &&
      visibleKeys[0] === soloKey
    );
    if (!validSolo) {
      return { selection, solo: null };
    }

    return {
      selection,
      solo: {
        key: soloKey,
        restoreSelection: normalizeSelectionForUniverse(
          soloSource.restoreSelection,
          available,
          selection.colorMode
        ),
        universeKeys: available.slice(),
      },
    };
  }

  function createCraftSelectionState(selection, availableKeys, fallbackColorMode) {
    return normalizeCraftSelectionState(
      { selection, solo: null },
      availableKeys,
      fallbackColorMode
    );
  }

  function toggleCraftKey(value, key, availableKeys, fallbackColorMode) {
    const available = uniqueKeys(availableKeys);
    const current = normalizeCraftSelectionState(value, available, fallbackColorMode);
    const targetKey = String(key == null ? "" : key).trim();
    if (!targetKey || available.indexOf(targetKey) === -1) return current;

    const activeKeys = activeKeysForSelection(current.selection, available);
    const activeSet = new Set(activeKeys);
    if (activeSet.has(targetKey)) {
      activeSet.delete(targetKey);
    } else {
      activeSet.add(targetKey);
    }
    const nextKeys = activeKeys.filter(function (activeKey) {
      return activeSet.has(activeKey);
    });
    if (activeSet.has(targetKey) && nextKeys.indexOf(targetKey) === -1) {
      nextKeys.push(targetKey);
    }
    return {
      selection: selectionFromActiveKeys(nextKeys, available, current.selection.colorMode),
      solo: null,
    };
  }

  function toggleCraftSolo(value, key, availableKeys, fallbackColorMode) {
    const available = uniqueKeys(availableKeys);
    const current = normalizeCraftSelectionState(value, available, fallbackColorMode);
    const targetKey = String(key == null ? "" : key).trim();
    if (!targetKey || available.indexOf(targetKey) === -1) return current;

    if (current.solo && current.solo.key === targetKey) {
      return {
        selection: normalizeEventSelection(
          current.solo.restoreSelection,
          current.selection.colorMode
        ),
        solo: null,
      };
    }

    const restoreSelection = current.solo
      ? current.solo.restoreSelection
      : current.selection;
    return {
      selection: {
        mode: "subset",
        colorMode: current.selection.colorMode,
        selectedKeys: [targetKey],
      },
      solo: {
        key: targetKey,
        restoreSelection: normalizeEventSelection(
          restoreSelection,
          current.selection.colorMode
        ),
        universeKeys: available.slice(),
      },
    };
  }

  function applyCraftBulkSelection(value, action, availableKeys, fallbackColorMode) {
    const available = uniqueKeys(availableKeys);
    const current = normalizeCraftSelectionState(value, available, fallbackColorMode);
    const normalizedAction = String(action == null ? "" : action).trim().toLowerCase();
    if (["all", "none", "invert", "reset"].indexOf(normalizedAction) === -1) {
      return current;
    }

    const colorMode = normalizedAction === "reset"
      ? String(fallbackColorMode || current.selection.colorMode || "craft_type")
      : current.selection.colorMode;
    let selection;
    if (normalizedAction === "all" || normalizedAction === "reset") {
      selection = resetEventSelection(colorMode);
    } else if (normalizedAction === "none") {
      selection = {
        mode: "none",
        colorMode,
        selectedKeys: [],
      };
    } else {
      const activeSet = new Set(activeKeysForSelection(current.selection, available));
      selection = selectionFromActiveKeys(
        available.filter(function (key) { return !activeSet.has(key); }),
        available,
        colorMode
      );
    }
    return { selection, solo: null };
  }

  function replaceCraftSelectionUniverse(value, availableKeys, fallbackColorMode) {
    const available = uniqueKeys(availableKeys);
    const source = craftStateSource(value);
    const selection = normalizeSelectionForUniverse(source.selection, available, fallbackColorMode);
    if (selection.mode !== "subset") {
      return { selection, solo: null };
    }
    return {
      selection: selectionFromActiveKeys(
        selection.selectedKeys,
        available,
        selection.colorMode
      ),
      solo: null,
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
    applyCraftBulkSelection,
    createCraftSelectionState,
    eventKeyActive,
    normalizeEventSelection,
    normalizeCraftSelectionState,
    replaceCraftSelectionUniverse,
    resetEventSelection,
    toggleCraftKey,
    toggleCraftSolo,
    toggleEventKey,
    toggleGroupedOverlay,
    uniqueKeys,
  });
});

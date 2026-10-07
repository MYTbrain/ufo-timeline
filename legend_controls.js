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
  const SAFE_CRAFT_COLOR_KEY = /^[a-z0-9][a-z0-9_-]{0,63}$/i;
  // Decorative category silhouettes accompany the written legend labels.
  // Only these fixed SVG fragments are inserted; input never becomes markup.
  const CRAFT_SYMBOLS = Object.freeze({
    disc_saucer: '<path d="M7 11a5 5 0 0 1 10 0" fill="currentColor" fill-opacity=".18"/><ellipse cx="12" cy="13" rx="10" ry="3" fill="currentColor" fill-opacity=".18"/><path d="m6 16 1 2m5-1v2m6-3-1 2"/>',
    sphere_orb: '<circle cx="12" cy="12" r="8.5" fill="currentColor" fill-opacity=".18"/><path d="M7 10a5 5 0 0 1 4-3"/>',
    triangle: '<path d="M12 3 22 20H2Z" fill="currentColor" fill-opacity=".22"/><circle cx="12" cy="8" r=".8" fill="currentColor"/><circle cx="7" cy="17" r=".8" fill="currentColor"/><circle cx="17" cy="17" r=".8" fill="currentColor"/>',
    cigar_cylinder: '<rect x="2" y="8" width="20" height="8" rx="4" fill="currentColor" fill-opacity=".22"/><path d="M6 8v8m12-8v8" stroke-opacity=".45"/>',
    oval_egg: '<path d="M12 3c4 0 7 7 7 11a7 7 0 0 1-14 0c0-4 3-11 7-11Z" fill="currentColor" fill-opacity=".22"/>',
    chevron_boomerang: '<path d="m2 15 10-9 10 9-3 3-7-6-7 6Z" fill="currentColor" fill-opacity=".3"/>',
    rectangle_box: '<path d="M3 7h15v13H3Zm0 0 3-3h15v13l-3 3m0-13 3-3" fill="currentColor" fill-opacity=".15"/>',
    fireball_meteor_like: '<circle cx="8" cy="16" r="4" fill="currentColor" fill-opacity=".3"/><path d="m5 11 9-8m-3 9 9-9m-7 14 8-8"/>',
    formation: '<circle cx="12" cy="5" r="2" fill="currentColor"/><circle cx="7" cy="11" r="2" fill="currentColor"/><circle cx="17" cy="11" r="2" fill="currentColor"/><circle cx="3" cy="17" r="2" fill="currentColor"/><circle cx="21" cy="17" r="2" fill="currentColor"/>',
    cone: '<path d="M3 18 12 3l9 15" fill="currentColor" fill-opacity=".22"/><ellipse cx="12" cy="18" rx="9" ry="3" fill="currentColor" fill-opacity=".18"/>',
    diamond: '<path d="m12 2 9 10-9 10L3 12Z" fill="currentColor" fill-opacity=".22"/>',
    teardrop: '<path d="M12 2c-2 5-8 8-8 13a8 8 0 0 0 16 0c0-5-6-8-8-13Z" fill="currentColor" fill-opacity=".22"/>',
    dumbbell_barbell: '<path d="M6 9h12v6H6Z" fill="currentColor" fill-opacity=".2"/><circle cx="5" cy="12" r="4" fill="currentColor" fill-opacity=".3"/><circle cx="19" cy="12" r="4" fill="currentColor" fill-opacity=".3"/>',
    light: '<path d="m12 2 2.2 7.8L22 12l-7.8 2.2L12 22l-2.2-7.8L2 12l7.8-2.2Z" fill="currentColor" fill-opacity=".25"/><path d="m5 5 2 2m10 10 2 2M19 5l-2 2M7 17l-2 2"/>',
    conventional_or_explained: '<path d="M12 2c-1 0-1 2-1 3v4l-9 6v2l9-3v5l-3 2v1l4-1 4 1v-1l-3-2v-5l9 3v-2l-9-6V5c0-1 0-3-1-3Z" fill="currentColor" fill-opacity=".28"/>',
    non_ufo_context: '<path d="M5 2h10l4 4v16H5Zm10 0v5h4"/><path d="M8 11h8m-8 4h8m-8 4h5" stroke-opacity=".7"/>',
    unknown: '<circle cx="12" cy="12" r="9" stroke-dasharray="2 2"/><path d="M9 9a3 3 0 1 1 5 2c-1 1-2 1-2 3"/><circle cx="12" cy="17" r=".8" fill="currentColor" stroke="none"/>',
  });

  function craftSymbolMarkup(key) {
    const symbolKey = typeof key === "string" && Object.prototype.hasOwnProperty.call(CRAFT_SYMBOLS, key)
      ? key
      : "unknown";
    return '<svg class="craft-legend-symbol" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><g fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">' +
      CRAFT_SYMBOLS[symbolKey] + "</g></svg>";
  }

  function normalizeHexColor(value) {
    const normalized = String(value == null ? "" : value).trim().toLowerCase();
    if (/^#[0-9a-f]{6}$/.test(normalized)) return normalized;
    if (/^#[0-9a-f]{3}$/.test(normalized)) {
      return "#" + normalized.slice(1).split("").map(function (digit) {
        return digit + digit;
      }).join("");
    }
    return "";
  }

  function normalizeCraftColorOverrides(value, defaultPalette) {
    const source = value && typeof value === "object" && !Array.isArray(value) ? value : {};
    const defaults = defaultPalette && typeof defaultPalette === "object" ? defaultPalette : {};
    const output = {};
    Object.keys(source).slice(0, 128).forEach(function (rawKey) {
      const key = String(rawKey == null ? "" : rawKey).trim();
      if (!SAFE_CRAFT_COLOR_KEY.test(key)) return;
      const color = normalizeHexColor(source[rawKey]);
      if (!color || color === normalizeHexColor(defaults[key])) return;
      output[key] = color;
    });
    return output;
  }

  function updateCraftColorOverride(value, key, color, defaultPalette) {
    const output = normalizeCraftColorOverrides(value, defaultPalette);
    const normalizedKey = String(key == null ? "" : key).trim();
    const normalizedColor = normalizeHexColor(color);
    if (!SAFE_CRAFT_COLOR_KEY.test(normalizedKey) || !normalizedColor) return output;
    if (normalizedColor === normalizeHexColor(defaultPalette && defaultPalette[normalizedKey])) {
      delete output[normalizedKey];
    } else {
      output[normalizedKey] = normalizedColor;
    }
    return output;
  }

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

  function normalizeViewportBounds(value) {
    if (!value || typeof value !== "object") return null;
    const south = Number(value.south);
    const west = Number(value.west);
    const north = Number(value.north);
    let east = Number(value.east);
    if (![south, west, north, east].every(Number.isFinite)) return null;
    while (east < west) east += 360;
    return {
      south: Math.min(south, north),
      west,
      north: Math.max(south, north),
      east,
    };
  }

  function canonicalMapLongitude(longitude) {
    let numeric = Number(longitude);
    if (!Number.isFinite(numeric)) return null;
    while (numeric > 180) numeric -= 360;
    while (numeric < -180) numeric += 360;
    return numeric;
  }

  function mapViewportContainsCoordinates(latitude, longitude, viewportBounds) {
    const bounds = normalizeViewportBounds(viewportBounds);
    const lat = Number(latitude);
    const lon = Number(longitude);
    if (!bounds || !Number.isFinite(lat) || !Number.isFinite(lon)) return false;
    if (lat < bounds.south || lat > bounds.north) return false;
    const canonicalLongitude = canonicalMapLongitude(lon);
    return canonicalLongitude != null && canonicalLongitude >= bounds.west && canonicalLongitude <= bounds.east;
  }

  function countViewportEventsByKey(events, viewportBounds, keyForEvent, universeKeys) {
    const counts = new Map();
    uniqueKeys(universeKeys).forEach(function (key) {
      counts.set(key, 0);
    });
    if (typeof keyForEvent !== "function") return counts;
    (Array.isArray(events) ? events : []).forEach(function (event) {
      if (!event || event.has_coordinates === false) return;
      if (!mapViewportContainsCoordinates(event.lat, event.lon, viewportBounds)) return;
      const resolvedKey = keyForEvent(event);
      const key = String(resolvedKey == null ? "" : resolvedKey).trim();
      if (!key) return;
      counts.set(key, (counts.get(key) || 0) + 1);
    });
    return counts;
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
    countViewportEventsByKey,
    craftSymbolMarkup,
    createCraftSelectionState,
    eventKeyActive,
    mapViewportContainsCoordinates,
    normalizeCraftColorOverrides,
    normalizeEventSelection,
    normalizeCraftSelectionState,
    normalizeHexColor,
    replaceCraftSelectionUniverse,
    resetEventSelection,
    toggleCraftKey,
    toggleCraftSolo,
    toggleEventKey,
    toggleGroupedOverlay,
    updateCraftColorOverride,
    uniqueKeys,
  });
});

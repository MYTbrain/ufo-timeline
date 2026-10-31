(function (root, factory) {
  "use strict";
  const api = factory();
  if (typeof module === "object" && module && module.exports) module.exports = api;
  if (root) root.UfoFamousCaseAvailability = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  function calendarDay(value) {
    if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return "";
    const timestamp = Date.parse(value + "T00:00:00Z");
    return Number.isFinite(timestamp) && new Date(timestamp).toISOString().slice(0, 10) === value ? value : "";
  }

  function coordinate(value, limit) {
    if (typeof value !== "number" && typeof value !== "string") return null;
    if (typeof value === "string" && !value.trim()) return null;
    const number = Number(value);
    return Number.isFinite(number) && Math.abs(number) <= limit ? number : null;
  }

  function lowerBound(days, target) {
    let low = 0;
    let high = days.length;
    while (low < high) {
      const middle = (low + high) >>> 1;
      if (days[middle] < target) low = middle + 1;
      else high = middle;
    }
    return low;
  }

  function summary(localReportCount, availableConnectionCount, connectionCount, outsideCatalog) {
    const status = outsideCatalog ? "outside_catalog" : connectionCount ? "connections" : localReportCount ? "reports_only" : "no_reports";
    const label = outsideCatalog ? "Outside catalog" : connectionCount
      ? connectionCount + (connectionCount === 1 ? " link" : " links")
      : availableConnectionCount ? "Links hidden by filters" : localReportCount ? "Reports only" : "No local reports";
    return { localReportCount: localReportCount, availableConnectionCount: availableConnectionCount,
      connectionCount: connectionCount, status: status, label: label };
  }

  // The caller supplies the same selection windows, vicinity geometry, graph
  // builder and trace filters used by the map. This is an availability preview,
  // never an attribution of a catalog report to a historical case.
  function summarizeCases(cases, events, options) {
    const config = options || {};
    ["selectionWindow", "containsPoint", "buildSegments"].forEach(function (name) {
      if (typeof config[name] !== "function") throw new TypeError("Missing availability callback: " + name);
    });
    const byDay = new Map();
    (Array.isArray(events) ? events : []).forEach(function (event) {
      if (!event || event.event_id == null || !String(event.event_id).trim() || event.has_coordinates === false) return;
      const lat = coordinate(event.lat, 90);
      const lon = coordinate(event.lon, 180);
      const day = calendarDay(event.sort_date_iso || event.date_iso);
      if (lat == null || lon == null || !day) return;
      if (!byDay.has(day)) byDay.set(day, []);
      byDay.get(day).push({ event: event, lat: lat, lon: lon });
    });
    const days = Array.from(byDay.keys()).sort();
    const result = Object.create(null);
    (Array.isArray(cases) ? cases : []).forEach(function (item) {
      const window = config.selectionWindow(item);
      if (!window || !calendarDay(window.startIso) || !calendarDay(window.endIso) || window.startIso > window.endIso) {
        result[item.id] = summary(0, 0, 0, true);
        return;
      }
      const candidates = [];
      const localIds = new Set();
      for (let index = lowerBound(days, window.startIso); index < days.length && days[index] <= window.endIso; index += 1) {
        byDay.get(days[index]).forEach(function (record) {
          candidates.push(record.event);
          if (config.containsPoint(item, record.lat, record.lon)) localIds.add(String(record.event.event_id));
        });
      }
      // Lines crossing the vicinity do not seed a case. At least one actual
      // local report must be an endpoint, exactly as in direct case selection.
      if (!localIds.size) {
        result[item.id] = summary(0, 0, 0, false);
        return;
      }
      const available = new Set();
      const visible = new Set();
      config.buildSegments(candidates).forEach(function (segment) {
        if (!segment || (!localIds.has(String(segment.fromEventId)) && !localIds.has(String(segment.toEventId)))) return;
        const key = segment.traceId || JSON.stringify([segment.fromEventId, segment.toEventId]);
        available.add(key);
        if (!config.filterSegment || config.filterSegment(segment)) visible.add(key);
      });
      result[item.id] = summary(localIds.size, available.size, visible.size, false);
    });
    return result;
  }

  return Object.freeze({ summarizeCases: summarizeCases });
});

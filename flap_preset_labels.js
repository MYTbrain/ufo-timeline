(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  }
  if (root) {
    root.UfoFlapPresetLabels = api;
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const MONTH_LABELS = Object.freeze([
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
  ]);

  function parseIsoMonth(value) {
    const match = /^(\d{4})-(\d{2})-\d{2}$/.exec(String(value || "").trim());
    if (!match) return null;
    const monthNumber = Number(match[2]);
    if (monthNumber < 1 || monthNumber > 12) return null;
    return Object.freeze({
      year: match[1],
      month: monthNumber,
      monthLabel: MONTH_LABELS[monthNumber - 1],
    });
  }

  function compactEndYear(startYear, endYear) {
    if (
      startYear.length === 4 &&
      endYear.length === 4 &&
      startYear.slice(0, 2) === endYear.slice(0, 2)
    ) {
      return endYear.slice(2);
    }
    return endYear;
  }

  function formatMonthRange(startIso, endIso) {
    const start = parseIsoMonth(startIso);
    const end = parseIsoMonth(endIso);
    if (!start || !end) return "";
    if (start.year === end.year) {
      if (start.month === end.month) {
        return start.year + " " + start.monthLabel;
      }
      return start.year + " " + start.monthLabel + "\u2013" + end.monthLabel;
    }
    return (
      start.year +
      " " +
      start.monthLabel +
      "\u2013" +
      compactEndYear(start.year, end.year) +
      " " +
      end.monthLabel
    );
  }

  function formatPresetLabel(preset) {
    const candidate = preset && typeof preset === "object" ? preset : {};
    const dateRange = formatMonthRange(candidate.startIso, candidate.endIso);
    const name = String(candidate.name || "").trim();
    if (dateRange && name) return dateRange + " \u00b7 " + name;
    if (dateRange) return dateRange;
    return String(candidate.label || candidate.description || name || "").trim();
  }

  function formatPresetTitle(preset) {
    const candidate = preset && typeof preset === "object" ? preset : {};
    const label = formatPresetLabel(candidate);
    const exactWindow =
      candidate.startIso && candidate.endIso
        ? "Exact window: " + candidate.startIso + " through " + candidate.endIso + "."
        : "";
    const description = String(candidate.description || "").trim();
    return [label, exactWindow, description]
      .filter(function (part, index, parts) {
        return part && parts.indexOf(part) === index;
      })
      .join(" ");
  }

  return Object.freeze({
    MONTH_LABELS,
    parseIsoMonth,
    compactEndYear,
    formatMonthRange,
    formatPresetLabel,
    formatPresetTitle,
  });
});

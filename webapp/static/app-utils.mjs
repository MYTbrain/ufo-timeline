export const LOW_PRECISION_VALUES = new Set([
  "country",
  "state_province",
  "approximate",
  "unknown",
]);

export function normalizeDateBoundary(rawValue, side = "start") {
  const value = String(rawValue || "").trim();
  if (!value) {
    return null;
  }

  if (/^\d{4}$/.test(value)) {
    return side === "start" ? `${value}-01-01` : `${value}-12-31`;
  }

  if (/^\d{4}-\d{2}$/.test(value)) {
    const [year, month] = value.split("-").map(Number);
    if (month < 1 || month > 12) {
      return null;
    }
    const finalDay = daysInMonth(year, month);
    return side === "start"
      ? `${pad(year, 4)}-${pad(month, 2)}-01`
      : `${pad(year, 4)}-${pad(month, 2)}-${pad(finalDay, 2)}`;
  }

  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    const [year, month, day] = value.split("-").map(Number);
    if (month < 1 || month > 12 || day < 1 || day > daysInMonth(year, month)) {
      return null;
    }
    return value;
  }

  return null;
}

export function computeDateExtent(events) {
  if (!events.length) {
    return null;
  }

  let min = null;
  let max = null;
  for (const event of events) {
    if (!event.sort_date_iso) {
      continue;
    }
    if (!min || event.sort_date_iso < min) {
      min = event.sort_date_iso;
    }
    if (!max || event.sort_date_iso > max) {
      max = event.sort_date_iso;
    }
  }

  if (!min || !max) {
    return null;
  }

  return {
    min,
    max,
    minScalar: dateScalar(min),
    maxScalar: dateScalar(max),
  };
}

export function filterEvents(events, filters) {
  const keyword = String(filters.keyword || "").trim().toLowerCase();
  const startBoundary = normalizeDateBoundary(filters.startDate, "start");
  const endBoundary = normalizeDateBoundary(filters.endDate, "end");

  const selectedSources = new Set(filters.sources || []);
  const selectedTypes = new Set(filters.types || []);
  const selectedPrecisions = new Set(filters.precisions || []);

  return events.filter((event) => {
    if (keyword && !(event.search_text || "").includes(keyword)) {
      return false;
    }

    if (startBoundary && event.sort_date_iso && event.sort_date_iso < startBoundary) {
      return false;
    }

    if (endBoundary && event.sort_date_iso && event.sort_date_iso > endBoundary) {
      return false;
    }

    if (selectedSources.size && !selectedSources.has(event.source || "")) {
      return false;
    }

    if (selectedTypes.size && !selectedTypes.has(event.type || "")) {
      return false;
    }

    if (selectedPrecisions.size && !selectedPrecisions.has(event.location_precision || "")) {
      return false;
    }

    if (filters.hideLowPrecision && LOW_PRECISION_VALUES.has(event.location_precision || "")) {
      return false;
    }

    return true;
  });
}

export function colorForEvent(event, extent) {
  if (!event.sort_date_iso || !extent) {
    return "hsl(200, 60%, 45%)";
  }

  const scalar = dateScalar(event.sort_date_iso);
  const range = Math.max(extent.maxScalar - extent.minScalar, 1);
  const ratio = clamp((scalar - extent.minScalar) / range, 0, 1);
  const hue = 220 - (ratio * 210);
  const saturation = 72 - (ratio * 12);
  const lightness = 44 + (ratio * 4);
  return `hsl(${hue.toFixed(1)} ${saturation.toFixed(1)}% ${lightness.toFixed(1)}%)`;
}

export function uniqueValues(events, key) {
  const values = new Set();
  for (const event of events) {
    const value = event[key];
    if (value) {
      values.add(value);
    }
  }
  return [...values].sort((left, right) => left.localeCompare(right));
}

export function pad(value, length = 2) {
  return String(value).padStart(length, "0");
}

export function daysInMonth(year, month) {
  if (month === 2) {
    return isLeapYear(year) ? 29 : 28;
  }
  return [4, 6, 9, 11].includes(month) ? 30 : 31;
}

export function isLeapYear(year) {
  if (year % 400 === 0) {
    return true;
  }
  if (year % 100 === 0) {
    return false;
  }
  return year % 4 === 0;
}

export function daysFromCivil(year, month, day) {
  year -= month <= 2 ? 1 : 0;
  const era = Math.floor(year / 400);
  const yearOfEra = year - (era * 400);
  const monthIndex = month + (month > 2 ? -3 : 9);
  const dayOfYear = Math.floor((153 * monthIndex + 2) / 5) + day - 1;
  const dayOfEra =
    yearOfEra * 365 +
    Math.floor(yearOfEra / 4) -
    Math.floor(yearOfEra / 100) +
    dayOfYear;
  return era * 146097 + dayOfEra - 719468;
}

export function civilFromDays(dayNumber) {
  const shifted = dayNumber + 719468;
  const era = Math.floor(shifted / 146097);
  const dayOfEra = shifted - era * 146097;
  const yearOfEra = Math.floor(
    (dayOfEra - Math.floor(dayOfEra / 1460) + Math.floor(dayOfEra / 36524) - Math.floor(dayOfEra / 146096)) / 365
  );
  let year = yearOfEra + era * 400;
  const dayOfYear = dayOfEra - (
    yearOfEra * 365 +
    Math.floor(yearOfEra / 4) -
    Math.floor(yearOfEra / 100)
  );
  const monthIndex = Math.floor((5 * dayOfYear + 2) / 153);
  const day = dayOfYear - Math.floor((153 * monthIndex + 2) / 5) + 1;
  const month = monthIndex + (monthIndex < 10 ? 3 : -9);
  year += month <= 2 ? 1 : 0;
  return { year, month, day };
}

export function isoToOrdinal(isoDate) {
  const normalized = normalizeDateBoundary(isoDate, "start");
  if (!normalized || normalized !== String(isoDate)) {
    return null;
  }
  const [year, month, day] = normalized.split("-").map(Number);
  return daysFromCivil(year, month, day);
}

export function ordinalToIso(ordinal) {
  if (!Number.isFinite(Number(ordinal))) {
    return "";
  }
  const { year, month, day } = civilFromDays(Math.round(Number(ordinal)));
  return `${pad(year, 4)}-${pad(month, 2)}-${pad(day, 2)}`;
}

export function dateScalar(isoDate) {
  const [year, month, day] = String(isoDate).split("-").map(Number);
  return (year * 372) + ((month - 1) * 31) + (day - 1);
}

export function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

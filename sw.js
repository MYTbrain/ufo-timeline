"use strict";

const RELEASE_ID = "location-label-normalization-v1-20260824-corsfix1";
const UPSTREAM_ORIGIN = "https://b0f0a0de.ufo-timeline.pages.dev";
const UPSTREAM_APP_SHA256 = "b634c6264c4c964deda1cf614fd9b0a6271900311ae6a1e3402fb1bf03230f4d";

self.addEventListener("install", function (event) {
  event.waitUntil(self.skipWaiting());
});

self.addEventListener("activate", function (event) {
  event.waitUntil((async function () {
    await self.clients.claim();
    const windows = await self.clients.matchAll({ type: "window" });
    await Promise.all(windows.map(function (client) {
      return client.navigate(client.url).catch(function () { return null; });
    }));
  })());
});

function hex(buffer) {
  return Array.from(new Uint8Array(buffer), function (value) {
    return value.toString(16).padStart(2, "0");
  }).join("");
}

function replaceOnce(source, needle, replacement, label) {
  const first = source.indexOf(needle);
  if (first < 0 || source.indexOf(needle, first + needle.length) >= 0) {
    throw new Error("Pinned app patch anchor mismatch: " + label);
  }
  return source.slice(0, first) + replacement + source.slice(first + needle.length);
}

function replaceExpected(source, needle, replacement, expectedCount, label) {
  let count = 0;
  let offset = 0;
  while ((offset = source.indexOf(needle, offset)) >= 0) {
    count += 1;
    offset += needle.length;
  }
  if (count !== expectedCount) {
    throw new Error("Pinned app patch anchor mismatch: " + label + " (expected " + expectedCount + ", found " + count + ")");
  }
  return source.split(needle).join(replacement);
}

const RUNTIME_NORMALIZER_SOURCE = String.raw`
  const LOCATION_DISPLAY_NORMALIZATION_POLICY = "location-label-structural-v1";
  const RUNTIME_US_STATE_NAME_TO_ABBREVIATION = Object.freeze({
    "ALABAMA":"AL","ALASKA":"AK","ARIZONA":"AZ","ARKANSAS":"AR","CALIFORNIA":"CA","COLORADO":"CO",
    "CONNECTICUT":"CT","DELAWARE":"DE","DISTRICT OF COLUMBIA":"DC","FLORIDA":"FL","GEORGIA":"GA",
    "HAWAII":"HI","IDAHO":"ID","ILLINOIS":"IL","INDIANA":"IN","IOWA":"IA","KANSAS":"KS",
    "KENTUCKY":"KY","LOUISIANA":"LA","MAINE":"ME","MARYLAND":"MD","MASSACHUSETTS":"MA",
    "MICHIGAN":"MI","MINNESOTA":"MN","MISSISSIPPI":"MS","MISSOURI":"MO","MONTANA":"MT",
    "NEBRASKA":"NE","NEVADA":"NV","NEW HAMPSHIRE":"NH","NEW JERSEY":"NJ","NEW MEXICO":"NM",
    "NEW YORK":"NY","NORTH CAROLINA":"NC","NORTH DAKOTA":"ND","OHIO":"OH","OKLAHOMA":"OK",
    "OREGON":"OR","PENNSYLVANIA":"PA","RHODE ISLAND":"RI","SOUTH CAROLINA":"SC","SOUTH DAKOTA":"SD",
    "TENNESSEE":"TN","TEXAS":"TX","UTAH":"UT","VERMONT":"VT","VIRGINIA":"VA","WASHINGTON":"WA",
    "WEST VIRGINIA":"WV","WISCONSIN":"WI","WYOMING":"WY"
  });
  const RUNTIME_US_STATE_CODES = new Set(Object.values(RUNTIME_US_STATE_NAME_TO_ABBREVIATION));
  const RUNTIME_MAJESTIC_ENVIRONMENTS = new Set([
    "coastlands","desert","farmlands","forest","high seas","islands","metropolis","mountains","offshore",
    "oil coal","pasture","rainforest","residential","town city","tundra","wetlands"
  ]);
  const RUNTIME_PLACEHOLDERS = new Set([
    "n a","na","none","null","tbd","unknown","unknown city","unknown location","unspecified"
  ]);
  const RUNTIME_US_COUNTRIES = new Set(["us","usa","united states","united states of america"]);

  function runtimeNormalizeLocationComponent(value) {
    const matches = String(value || "").toLowerCase().match(/[a-z0-9]+/g);
    return matches ? matches.join(" ") : "";
  }

  function runtimeUsStateCode(value) {
    const text = String(value || "").trim().toUpperCase().replace(/^\.+|\.+$/g, "");
    if (RUNTIME_US_STATE_CODES.has(text)) return text;
    return RUNTIME_US_STATE_NAME_TO_ABBREVIATION[text] || null;
  }

  function runtimeRemoveAdjacentDuplicates(parts) {
    const kept = [];
    let removed = false;
    parts.forEach(function (part) {
      if (kept.length && runtimeNormalizeLocationComponent(kept[kept.length - 1]) === runtimeNormalizeLocationComponent(part)) {
        removed = true;
      } else {
        kept.push(part);
      }
    });
    return { parts: kept, removed: removed };
  }

  function runtimeApplyGenericLocationDisplay(event) {
    const existingDisplay = String(event.location_display || "").trim();
    const locationRaw = String(event.location_raw || "").trim();
    if (!existingDisplay && !locationRaw) return event;
    const sourceLabel = existingDisplay || locationRaw;
    let inputLabel = sourceLabel;
    const transformations = [];
    const markdownMatch = inputLabel.match(/^\[([^\]]+)\]\(https?:\/\/[^)]+\)$/is);
    if (markdownMatch) {
      inputLabel = markdownMatch[1].trim();
      transformations.push("unwrap_markdown_location_link");
    }
    if (inputLabel.length > 180 && !transformations.length) return event;

    const originalParts = inputLabel.split(",");
    let parts = originalParts.map(function (part) { return part.trim(); }).filter(Boolean);
    if (parts.length !== originalParts.length) transformations.push("remove_empty_components");

    const source = runtimeNormalizeLocationComponent(event.source_name || event.source);
    if (source === "majestic" && parts.length && RUNTIME_MAJESTIC_ENVIRONMENTS.has(runtimeNormalizeLocationComponent(parts[0]))) {
      parts.shift();
      transformations.push("remove_majestic_environment_category");
    }

    if (parts.length > 1) {
      const kept = parts.filter(function (part) { return !RUNTIME_PLACEHOLDERS.has(runtimeNormalizeLocationComponent(part)); });
      if (kept.length && kept.length !== parts.length) {
        parts = kept;
        transformations.push("remove_placeholder_components");
      }
    }

    let duplicateResult = runtimeRemoveAdjacentDuplicates(parts);
    parts = duplicateResult.parts;
    if (duplicateResult.removed) transformations.push("remove_adjacent_duplicate_components");

    const seen = new Set();
    const uniqueParts = [];
    let removedRepeated = false;
    parts.forEach(function (part) {
      const normalized = runtimeNormalizeLocationComponent(part);
      if (seen.has(normalized)) {
        removedRepeated = true;
      } else {
        seen.add(normalized);
        uniqueParts.push(part);
      }
    });
    parts = uniqueParts;
    if (removedRepeated) transformations.push("remove_repeated_components");

    if (parts.length >= 4 && RUNTIME_US_COUNTRIES.has(runtimeNormalizeLocationComponent(parts[parts.length - 1]))) {
      const adminIndexes = [];
      for (let index = 1; index < parts.length - 1; index += 1) {
        const state = runtimeUsStateCode(parts[index]);
        if (state) adminIndexes.push([index, state]);
      }
      if (new Set(adminIndexes.map(function (entry) { return entry[1]; })).size > 1) {
        const conflicts = new Set(adminIndexes.map(function (entry) { return entry[0]; }));
        parts = parts.filter(function (_part, index) { return !conflicts.has(index); });
        transformations.push("omit_conflicting_us_state_components");
      }
    }

    duplicateResult = runtimeRemoveAdjacentDuplicates(parts);
    parts = duplicateResult.parts;
    if (duplicateResult.removed && transformations.indexOf("remove_adjacent_duplicate_components") < 0) {
      transformations.push("remove_adjacent_duplicate_components");
    }

    if (parts.length >= 4 && RUNTIME_US_COUNTRIES.has(runtimeNormalizeLocationComponent(parts[parts.length - 1]))) {
      const adminIndexes = [];
      for (let index = 1; index < parts.length - 1; index += 1) {
        const state = runtimeUsStateCode(parts[index]);
        if (state) adminIndexes.push([index, state]);
      }
      if (new Set(adminIndexes.map(function (entry) { return entry[1]; })).size === 1 && adminIndexes.length >= 2) {
        const redundant = new Set(adminIndexes.slice(1).map(function (entry) { return entry[0]; }));
        parts = parts.filter(function (_part, index) { return !redundant.has(index); });
        transformations.push("remove_redundant_us_state_components");
      }
    }

    const display = parts.join(", ").trim();
    if (!display || display === sourceLabel) return event;
    event.location_display = display;
    const normalizations = Array.isArray(event.location_display_normalizations)
      ? event.location_display_normalizations.filter(function (item) {
          return item && typeof item === "object" && item.policy_id !== LOCATION_DISPLAY_NORMALIZATION_POLICY;
        })
      : [];
    normalizations.push({
      policy_id: LOCATION_DISPLAY_NORMALIZATION_POLICY,
      transformations: transformations,
      raw_location_preserved: Boolean(locationRaw),
    });
    event.location_display_normalizations = normalizations;
    return event;
  }

  const RUNTIME_REVIEWED_LOCATION_CORRECTIONS = Object.freeze({
    "3483027136344169": {
      correction_id: "majestic-hatch-udb-2481-napa-2026-08-23",
      expected_raw: "Farmlands, NAPA VALLEY, CA, Colorado, USA",
      fields: {
        time_display: "10:45",
        location_display: "Napa Valley near Napa, Napa County, California, USA",
        city: "Napa",
        state_province: "California",
        country: "USA",
        location_precision: "city",
        duration_display: "Not stated in the contemporary newspaper account",
        summary: "John Foraythe reported a metallic disc moving west at great speed over Napa Valley at an estimated 20,000 feet; it tilted edge-on and vanished in haze.",
        description: "On Sunday, July 27, 1952 at 10:45 a.m., John Foraythe of 1512 A Street in Napa reported a metallic, disc-shaped object at an estimated altitude of 20,000 feet moving west at great speed over Napa Valley. It tilted until its thin edge faced him, then disappeared in haze. His report to the local sheriff's office was forwarded to Hamilton Field airbase.",
        description_short: "On Sunday, July 27, 1952 at 10:45 a.m., John Foraythe of 1512 A Street in Napa reported a metallic, disc-shaped object at an estimated altitude of 20,000 feet moving west at great speed over Napa Valley. It tilted until its thin edge faced him, then disappeared in haze. His report to the local sheriff's office was forwarded to Hamilton Field airbase.",
        source_url_display: "https://sohp.us/collections/ufos-a-history/pdf/GROSS-1952-July-21-31-SN.pdf#page=51",
        mapping_notes: "Reviewed 2026-08-23. Retained the Hatch coordinate as an approximate Napa-area marker; the report does not establish an exact observer or airborne-object position. Corrected the normalized state from Colorado to California and removed Hatch's 'Farmlands' environment category from the display place. The contemporary newspaper account gives 10:45 a.m. and states no duration. Original Hatch values remain preserved in the raw source-claim fields and raw source row.",
        parsed_time_local_minutes: 645,
        parsed_time_local_range_start_minutes: 645,
        parsed_time_local_range_end_minutes: 645,
        estimated_utc_timestamp_ms: -550044900000,
        estimated_utc_range_start_ms: -550044900000,
        estimated_utc_range_end_ms: -550044900000,
        playback_sort_key: [1, -550044900000, 0, 0, 0, "3483027136344169"],
        playback_sort_reason: "exact_time_with_inferred_timezone",
        playback_sort_confidence: "high",
        time_sort_kind: "exact",
        time_sort_confidence: "high"
      },
      link: "https://sohp.us/collections/ufos-a-history/pdf/GROSS-1952-July-21-31-SN.pdf#page=51"
    },
    "1843028587236113": {
      correction_id: "majestic-overmeire-1022-oslofjord-location-2026-08-24",
      expected_prefix: "At around 10:30 pm, a secretary and three of her friends approached a small fjord.",
      fields: {
        location_display: "Oslofjord, about 30 km from Oslo, Norway",
        city: "Oslo",
        state_province: null,
        country: "Norway",
        location_precision: "region",
        source_url_display: "https://github.com/bbauska/UFO-Dr-James-McDonald/blob/main/james-mcdonald-australia.md",
        mapping_notes: "Reviewed 2026-08-24. The imported location/0 cell contains a narrative rather than a place. The source description identifies Oslofjord; a James McDonald interview index describes the site as about 30 km from Oslo. No point coordinate is asserted. The full source narrative remains preserved in location_raw and raw_fields."
      },
      link: "https://github.com/bbauska/UFO-Dr-James-McDonald/blob/main/james-mcdonald-australia.md"
    },
    "3021254738232912": {
      correction_id: "majestic-magonia-811-dunbar-location-2026-08-24",
      expected_prefix: "Charleston (West Virginia) Tad Jones, 38, was driving near Charleston",
      fields: {
        location_display: "Interstate 64 near Dunbar, West Virginia, USA",
        city: "Dunbar",
        state_province: "West Virginia",
        country: "USA",
        location_precision: "city",
        source_url_display: "https://www.nicap.org/chronos/1967fullrep.htm",
        mapping_notes: "Reviewed 2026-08-24. Magonia row 811 shifted the sighting narrative into location/0. The Magonia text says Charleston, West Virginia; NICAP's chronology places the report on Interstate 64 near Dunbar. No exact point coordinate is asserted. The original narrative remains preserved in location_raw and raw_fields."
      },
      link: "https://www.nicap.org/chronos/1967fullrep.htm"
    },
    "2487272255366338": {
      correction_id: "majestic-overmeire-2808-hebrides-location-2026-08-24",
      expected_prefix: "The trawler \"Avel-Mad, captain Jean Chorlay, returned to the port of Douarnenez",
      fields: {
        location_display: "At sea between St Kilda and Barra, Outer Hebrides, Scotland, UK",
        city: null,
        state_province: "Scotland",
        country: "United Kingdom",
        location_precision: "region",
        mapping_notes: "Reviewed 2026-08-24. Overmeire_2808 shifted a long narrative into location/0. The account places the trawler between St Kilda and Barra off northern Scotland. No exact vessel position is supplied, so the event remains unmapped at regional precision. The complete source narrative remains preserved in location_raw and raw_fields."
      }
    }
  });

  function applyRuntimeLocationDisplayNormalization(event) {
    if (!event || typeof event !== "object") return event;
    runtimeApplyGenericLocationDisplay(event);
    const correction = RUNTIME_REVIEWED_LOCATION_CORRECTIONS[String(event.event_id)];
    if (!correction) return event;
    const source = runtimeNormalizeLocationComponent(event.source_name || event.source);
    const rawLocation = String(event.location_raw || "");
    const rawMatches = correction.expected_raw
      ? rawLocation === correction.expected_raw
      : rawLocation.indexOf(correction.expected_prefix || "") === 0;
    if (source !== "majestic" || !rawMatches) {
      console.error("[ufo-location-release] reviewed correction guard rejected", event.event_id);
      return event;
    }
    const fullDetail = Boolean(event.canonical_event_id || event.raw_fields || event.raw_event_block);
    const summaryFields = new Set([
      "time_display", "location_display", "location_precision", "playback_sort_key",
      "playback_sort_reason", "playback_sort_confidence", "time_sort_kind", "time_sort_confidence"
    ]);
    Object.keys(correction.fields).forEach(function (key) {
      if (!fullDetail && !summaryFields.has(key)) return;
      const value = correction.fields[key];
      if (value == null) delete event[key];
      else event[key] = Array.isArray(value) ? value.slice() : value;
    });
    delete event.location_display_normalizations;
    if (fullDetail && correction.link) {
      const links = Array.isArray(event.links) ? event.links.slice() : [];
      if (links.indexOf(correction.link) < 0) links.push(correction.link);
      event.links = links;
    }
    if (fullDetail) {
      const prior = Array.isArray(event.reviewed_corrections) ? event.reviewed_corrections.filter(function (item) {
        return item && item.correction_id !== correction.correction_id;
      }) : [];
      prior.push({ correction_id: correction.correction_id, runtime_release: "location-label-normalization-v1-20260824-corsfix1" });
      event.reviewed_corrections = prior;
    }
    return event;
  }
`;

function patchAppSource(source) {
  source = replaceOnce(
    source,
    "  function displayLocationForEvent(event) {\n    if (!event) return \"Unknown location\";\n    return event.location_raw || event.geocode_display_name || \"Unknown location\";\n  }",
    RUNTIME_NORMALIZER_SOURCE + "\n  function displayLocationForEvent(event) {\n    if (!event) return \"Unknown location\";\n    return event.location_display || event.location_raw || event.geocode_display_name || \"Unknown location\";\n  }",
    "runtime normalizer and display selector"
  );

  const replacements = [
    [
      "    packedEvent.date_raw = catalogEvent.date_raw || \"\";\n    packedEvent.location_raw = catalogEvent.location_raw || \"\";",
      "    packedEvent.date_raw = catalogEvent.date_raw || \"\";\n    packedEvent.time_display = catalogEvent.time_display || \"\";\n    packedEvent.location_raw = catalogEvent.location_raw || \"\";\n    packedEvent.location_display = catalogEvent.location_display || \"\";\n    packedEvent.location_precision = catalogEvent.location_precision || packedEvent.location_precision;\n    packedEvent.playback_sort_key = catalogEvent.playback_sort_key || packedEvent.playback_sort_key;"
    ],
    [
      "    if (!resolvedPlace) return \"\";",
      "    if (!resolvedPlace || resolvedPlace === String(displayLocationForEvent(event)).trim()) return \"\";"
    ],
    [
      "      '<div class=\"popup-row\"><span class=\"popup-label\">Location Raw:</span> ' + escapeHtml(event.location_raw || \"Unknown location\") + \"</div>\" +",
      "      '<div class=\"popup-row\"><span class=\"popup-label\">Location:</span> ' + escapeHtml(displayLocationForEvent(event)) + \"</div>\" +\n      (event.location_display && event.location_raw && event.location_display !== event.location_raw\n        ? '<div class=\"popup-row\"><span class=\"popup-label\">Source Location:</span> ' + escapeHtml(event.location_raw) + \"</div>\"\n        : \"\") +\n      (event.time_display\n        ? '<div class=\"popup-row\"><span class=\"popup-label\">Reviewed Time:</span> ' + escapeHtml(event.time_display) + \"</div>\"\n        : \"\") +"
    ],
    [
      "      title: (event.date_raw || event.sort_date_iso || \"Unknown\") + \" - \" + (event.location_raw || event.geocode_display_name || \"Unknown location\"),",
      "      title: (event.date_raw || event.sort_date_iso || \"Unknown\") + \" - \" + displayLocationForEvent(event),"
    ],
    [
      "normalizeVisibleDisplayDuplicateText(event.time_raw || event.time || \"\", true)",
      "normalizeVisibleDisplayDuplicateText(event.time_display || event.time_raw || event.time || \"\", true)",
      2
    ],
    [
      "if (event.time_raw || event.time || event.sort_time_ms != null) score += 10;",
      "if (event.time_display || event.time_raw || event.time || event.sort_time_ms != null) score += 10;"
    ],
    [
      "      [\"Date Precision\", event.date_precision],\n      [\"Time Raw\", event.time_raw],\n      [\"Location Raw\", event.location_raw],",
      "      [\"Date Precision\", event.date_precision],\n      ...(event.time_display ? [[\"Reviewed Time\", event.time_display]] : []),\n      [\"Time Raw\", event.time_raw],\n      ...(event.location_display ? [[\"Reviewed Location\", event.location_display]] : []),\n      [\"Location Raw\", event.location_raw],"
    ],
    [
      "      [\"Location Precision\", locationPrecisionDisplayLabel(event.location_precision)],\n      [\"Latitude\", event.lat],",
      "      [\"Location Precision\", locationPrecisionDisplayLabel(event.location_precision)],\n      ...(event.duration_display ? [[\"Reviewed Duration\", event.duration_display]] : []),\n      [\"Duration Raw\", event.duration_raw],\n      [\"Latitude\", event.lat],"
    ],
    [
      "      '<p class=\"detail-subtitle\">' + escapeHtml(event.location_raw || event.geocode_display_name || \"Unknown location\") + \"</p>\" +",
      "      '<p class=\"detail-subtitle\">' + escapeHtml(displayLocationForEvent(event)) + \"</p>\" +"
    ],
    [
      "      event.description || \"\",\n      event.location_raw || \"\",",
      "      event.description || \"\",\n      event.time_display || \"\",\n      event.location_display || \"\",\n      event.location_raw || \"\",\n      event.duration_display || \"\","
    ],
    [
      "      time_raw: internCanonicalSummaryString(event.time_raw),\n      playback_sort_key: compactPlaybackSortKey,\n      location_raw: internCanonicalSummaryString(event.location_raw),",
      "      time_raw: internCanonicalSummaryString(event.time_raw),\n      time_display: internCanonicalSummaryString(event.time_display),\n      playback_sort_key: compactPlaybackSortKey,\n      location_raw: internCanonicalSummaryString(event.location_raw),\n      location_display: internCanonicalSummaryString(event.location_display),"
    ],
    [
      "  function hydrateCatalogEvent(event) {\n    event = compactCanonicalSummaryEventForRuntime(event);",
      "  function hydrateCatalogEvent(event) {\n    event = applyRuntimeLocationDisplayNormalization(event);\n    event = compactCanonicalSummaryEventForRuntime(event);"
    ],
    [
      "  function cacheFullEventRecord(event) {\n    if (!event || event.event_id == null) return;",
      "  function cacheFullEventRecord(event) {\n    event = applyRuntimeLocationDisplayNormalization(event);\n    if (!event || event.event_id == null) return;"
    ]
  ];

  replacements.forEach(function (entry, index) {
    source = replaceExpected(source, entry[0], entry[1], entry[2] || 1, "display support " + (index + 1));
  });
  if (source.indexOf("applyRuntimeLocationDisplayNormalization") < 0 || source.indexOf(RELEASE_ID) < 0) {
    throw new Error("Runtime correction injection failed closed.");
  }
  return source;
}

async function upstreamResponse(request) {
  const incoming = new URL(request.url);
  const upstream = new URL(incoming.pathname + incoming.search, UPSTREAM_ORIGIN);
  const headers = new Headers();
  const init = {
    method: request.method === "HEAD" ? "HEAD" : "GET",
    headers: headers,
    mode: "cors",
    credentials: "omit",
    redirect: "follow",
    cache: incoming.pathname === "/app.js" ? "no-store" : "default",
  };
  const response = await fetch(upstream.toString(), init);
  const responseHeaders = new Headers(response.headers);
  responseHeaders.delete("content-length");
  responseHeaders.delete("content-encoding");
  const bodyless = request.method === "HEAD" || response.status === 204 || response.status === 205 || response.status === 304;
  return new Response(bodyless ? null : response.body, {
    status: response.status,
    statusText: response.statusText,
    headers: responseHeaders,
  });
}

async function patchedAppResponse(request) {
  const response = await upstreamResponse(request);
  if (!response.ok) return response;
  const source = await response.text();
  const digest = hex(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(source)));
  if (digest !== UPSTREAM_APP_SHA256) {
    return new Response("Pinned upstream app changed; refusing an unreviewed runtime patch.", {
      status: 503,
      headers: { "Content-Type": "text/plain; charset=utf-8", "Cache-Control": "no-store" },
    });
  }
  let patched;
  try {
    patched = patchAppSource(source);
  } catch (error) {
    return new Response(error && error.message ? error.message : String(error), {
      status: 503,
      headers: { "Content-Type": "text/plain; charset=utf-8", "Cache-Control": "no-store" },
    });
  }
  return new Response(patched, {
    status: 200,
    headers: {
      "Content-Type": "application/javascript; charset=utf-8",
      "Cache-Control": "no-store",
      "X-UFO-Release": RELEASE_ID,
    },
  });
}

self.addEventListener("fetch", function (event) {
  const request = event.request;
  const url = new URL(request.url);
  if ((request.method !== "GET" && request.method !== "HEAD") || url.origin !== self.location.origin || url.pathname === "/sw.js") return;
  if (url.pathname === "/app.js" && request.method === "GET") {
    event.respondWith(patchedAppResponse(request));
    return;
  }
  event.respondWith(upstreamResponse(request).catch(function () {
    return new Response("Verified upstream deployment is temporarily unavailable.", {
      status: 503,
      headers: { "Content-Type": "text/plain; charset=utf-8", "Cache-Control": "no-store" },
    });
  }));
});

(function () {
  "use strict";

  function versionedUrl(rawUrl, versionToken) {
    const url = new URL(rawUrl, self.location.href);
    if (versionToken && !url.searchParams.has("v")) {
      url.searchParams.set("v", versionToken);
    }
    return url.toString();
  }

  function profileAssetUrl(baseUrl, fileName, versionToken) {
    const normalizedBase = String(baseUrl || "./data/startup_profiles/france_1954_flap/").replace(/\/?$/, "/");
    return versionedUrl(new URL(fileName, new URL(normalizedBase, self.location.href)).toString(), versionToken);
  }

  function canDecodeGzip() {
    return typeof self.DecompressionStream === "function";
  }

  async function fetchGzipJson(rawUrl) {
    const response = await fetch(rawUrl, { cache: "default" });
    if (!response.ok) {
      throw new Error("HTTP " + response.status + " for " + rawUrl);
    }
    if (!response.body || !canDecodeGzip()) {
      throw new Error("Gzip stream decoding is not available in this worker.");
    }
    const stream = response.body.pipeThrough(new DecompressionStream("gzip"));
    return new Response(stream).json();
  }

  async function fetchJsonPreferGzip(rawUrl, gzipUrl) {
    if (gzipUrl && canDecodeGzip()) {
      try {
        const value = await fetchGzipJson(gzipUrl);
        return { value, url: gzipUrl, gzip: true };
      } catch (error) {
        // Fall back to raw JSON below. The main thread also follows this policy.
      }
    }
    const response = await fetch(rawUrl, { cache: "default" });
    if (!response.ok) {
      throw new Error("HTTP " + response.status + " for " + rawUrl);
    }
    return { value: await response.json(), url: rawUrl, gzip: false };
  }

  async function loadProfile(payload) {
    const config = payload.config || {};
    const versionToken = String(payload.versionToken || "");
    const baseUrl = config.baseUrl || "./data/startup_profiles/france_1954_flap/";
    const manifestRawUrl = versionedUrl(config.manifestUrl || profileAssetUrl(baseUrl, "manifest.json", ""), versionToken);
    const manifestFetch = await fetchJsonPreferGzip(manifestRawUrl, manifestRawUrl + ".gz");
    const manifest = manifestFetch.value || {};
    const files = manifest.files && typeof manifest.files === "object" ? manifest.files : {};
    const eventsRawUrl = profileAssetUrl(baseUrl, files.events || "events.json", versionToken);
    const eventsGzipUrl = profileAssetUrl(baseUrl, files.events_gzip || ((files.events || "events.json") + ".gz"), versionToken);
    const eventsFetch = await fetchJsonPreferGzip(eventsRawUrl, eventsGzipUrl);
    let tracePreviewSegments = [];
    let tracePreviewUrl = "";
    let tracePreviewGzip = false;
    if (config.tracePreview !== false && files.trace_preview_segments) {
      const traceRawUrl = profileAssetUrl(baseUrl, files.trace_preview_segments, versionToken);
      const traceGzipUrl = profileAssetUrl(
        baseUrl,
        files.trace_preview_segments_gzip || (files.trace_preview_segments + ".gz"),
        versionToken
      );
      const traceFetch = await fetchJsonPreferGzip(traceRawUrl, traceGzipUrl);
      tracePreviewSegments = Array.isArray(traceFetch.value) ? traceFetch.value : [];
      tracePreviewUrl = traceFetch.url;
      tracePreviewGzip = traceFetch.gzip;
    }
    return {
      manifest,
      events: Array.isArray(eventsFetch.value) ? eventsFetch.value : [],
      tracePreviewSegments,
      urls: {
        manifest: manifestFetch.url,
        events: eventsFetch.url,
        tracePreview: tracePreviewUrl,
      },
      usedGzip: {
        manifest: manifestFetch.gzip,
        events: eventsFetch.gzip,
        tracePreview: tracePreviewGzip,
      },
    };
  }

  self.addEventListener("message", function (event) {
    const payload = event.data || {};
    if (payload.type !== "loadStartupProfile") return;
    loadProfile(payload)
      .then(function (result) {
        self.postMessage({
          type: "startupProfileLoaded",
          requestId: payload.requestId,
          result,
        });
      })
      .catch(function (error) {
        self.postMessage({
          type: "startupProfileError",
          requestId: payload.requestId,
          error: error && error.message ? error.message : String(error),
        });
      });
  });
}());

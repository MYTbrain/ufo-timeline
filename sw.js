/*
 * One-release retirement worker for the emergency cross-origin recovery proxy.
 *
 * This worker deliberately has no fetch handler. Once activated it immediately
 * stops the former /sw.js from proxying site requests to another Pages origin,
 * claims any open windows, unregisters itself, and reloads those windows onto
 * the directly hosted static bundle.
 */
"use strict";

self.addEventListener("install", function (event) {
  event.waitUntil(self.skipWaiting());
});

self.addEventListener("activate", function (event) {
  event.waitUntil((async function () {
    await self.clients.claim();
    await self.registration.unregister();
    const windows = await self.clients.matchAll({
      type: "window",
      includeUncontrolled: true,
    });
    await Promise.all(windows.map(function (client) {
      return client.navigate(client.url).catch(function () {
        return undefined;
      });
    }));
  })());
});

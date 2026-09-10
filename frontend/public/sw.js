/* LabelLens service worker.
 *
 * Inspections happen in markets and mandis where connectivity is unreliable, so the app
 * shell is cached and served offline. Inspection submissions are NOT replayed here —
 * they are queued in the app (see src/offlineQueue.ts) and sent only when the officer is
 * back online, because every submission is committed to the evidence ledger and a
 * silently retried POST could duplicate a case record.
 */

const SHELL_CACHE = "labellens-shell-v1";
const SHELL_ASSETS = ["/", "/manifest.webmanifest", "/favicon.svg"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(SHELL_CACHE).then((cache) => cache.addAll(SHELL_ASSETS)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((key) => key !== SHELL_CACHE).map((key) => caches.delete(key))),
      ),
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const { request } = event;

  if (request.method !== "GET") return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  // API responses are evidence records; never serve a stale one from cache.
  if (url.pathname.startsWith("/api/")) return;

  if (request.mode === "navigate") {
    event.respondWith(fetch(request).catch(() => caches.match("/")));
    return;
  }

  event.respondWith(
    caches.match(request).then(
      (cached) =>
        cached ??
        fetch(request).then((response) => {
          if (response.ok && response.type === "basic") {
            const copy = response.clone();
            caches.open(SHELL_CACHE).then((cache) => cache.put(request, copy));
          }
          return response;
        }),
    ),
  );
});

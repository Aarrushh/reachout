/*
 * ReachOut service worker (task U5). Hand-written, no build step, no plugin —
 * the frontend takes no library it does not need, and the whole policy fits
 * on one screen where it can be read.
 *
 * THE RULE THIS FILE EXISTS TO ENFORCE: the offline cache holds the CONSUMER
 * app and nothing else. Retail mode is a shopkeeper's analytics dashboard.
 * Serving it from a cache would show yesterday's demand figures with no way
 * to tell they are stale — the same class of lie as an unlabelled fixture,
 * and worse for being silent. Anything at `?mode=retail`, and every request
 * to the demand service, goes to the network or fails honestly.
 */

const CACHE = "reachout-consumer-v1";

// The consumer shell. `/` only: retail has no URL of its own (it is a query
// param on these same routes), so precaching a route never precaches retail.
const PRECACHE = ["/", "/manifest.webmanifest", "/icon.svg"];

/**
 * True when a request must never touch the cache — neither served from it
 * nor written into it.
 *
 * Exported onto `self` so the test suite can exercise this exact function
 * from the shipped file rather than a copy of it. A second copy of this rule
 * is a second rule, and the two would drift.
 */
self.isRetailRequest = function isRetailRequest(url) {
  const parsed = new URL(url, "http://localhost");
  // Same rule as the app's `parseMode`: only the exact string counts.
  if (parsed.searchParams.get("mode") === "retail") return true;
  // The demand service's responses are the dashboard's numbers. Even reached
  // from a consumer URL, they are never cached.
  if (parsed.pathname.startsWith("/demand/")) return true;
  return false;
};

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((c) => c.addAll(PRECACHE)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;

  // Only GET is cacheable at all, and only same-origin: the map tiles and the
  // two APIs are cross-origin and must stay live.
  if (request.method !== "GET") return;
  if (new URL(request.url).origin !== self.location.origin) return;

  if (self.isRetailRequest(request.url)) {
    // Explicitly bypass rather than fall through: no cache read, no cache
    // write, and no stale dashboard if the network is down.
    event.respondWith(fetch(request));
    return;
  }

  // A navigation is answered by the cached shell when offline — the app is a
  // single page, so `/` is the shell for every consumer route.
  if (request.mode === "navigate") {
    event.respondWith(fetch(request).catch(() => caches.match("/")));
    return;
  }

  // Assets: cache first, then network, filling the cache as it goes.
  event.respondWith(
    caches.match(request).then(
      (hit) =>
        hit ||
        fetch(request).then((response) => {
          if (response.ok) {
            const copy = response.clone();
            caches.open(CACHE).then((c) => c.put(request, copy));
          }
          return response;
        }),
    ),
  );
});

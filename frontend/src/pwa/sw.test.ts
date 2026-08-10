import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it, vi } from "vitest";

/**
 * These tests execute `public/sw.js` ITSELF, not a copy of its logic.
 *
 * The file ships as a hand-written classic service worker with no build step,
 * so there is nothing to import. Reading and evaluating it inside a fake
 * worker global is what makes the assertions below true of the artefact that
 * actually reaches a phone — re-implementing the routing here would only
 * prove that two copies of the rule agree today.
 */
const SW_SOURCE = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "..", "..", "public", "sw.js"),
  "utf-8",
);

const ORIGIN = "https://reachout.example";

/** Evaluates the shipped worker against a fake global, with `fetch` injected. */
function loadWorker(fetchImpl: (...args: any[]) => any = vi.fn()) {
  const handlers: Record<string, (event: any) => void> = {};
  const self: Record<string, any> = {
    location: { origin: ORIGIN },
    addEventListener: (type: string, handler: (event: any) => void) => {
      handlers[type] = handler;
    },
    skipWaiting: () => {},
    clients: { claim: async () => {} },
  };
  const caches = {
    open: vi.fn(async () => ({ addAll: vi.fn(), put: vi.fn() })),
    keys: vi.fn(async () => []),
    match: vi.fn(async () => undefined),
    delete: vi.fn(async () => true),
  };

  // eslint-disable-next-line no-new-func
  new Function("self", "caches", "fetch", SW_SOURCE)(self, caches, fetchImpl);
  return { self, handlers, caches };
}

/** Drives the worker's fetch handler; returns whatever it responded with. */
function dispatchFetch(
  handlers: Record<string, (event: any) => void>,
  request: { url: string; method?: string; mode?: string },
) {
  let responded: Promise<unknown> | undefined;
  handlers.fetch({
    request: { method: "GET", mode: "no-cors", ...request },
    respondWith: (p: Promise<unknown>) => {
      responded = p;
    },
  });
  return responded;
}

const offline = () =>
  vi.fn(async () => {
    throw new Error("offline");
  });

describe("public/sw.js — the offline cache is consumer-only", () => {
  it("treats ?mode=retail as never-cacheable", () => {
    const { self } = loadWorker();

    expect(self.isRetailRequest(`${ORIGIN}/?mode=retail`)).toBe(true);
    expect(self.isRetailRequest(`${ORIGIN}/results?q=leche&mode=retail`)).toBe(true);
    // Same rule as the app's parseMode: only the exact string is retail.
    expect(self.isRetailRequest(`${ORIGIN}/?mode=Retail`)).toBe(false);
    expect(self.isRetailRequest(`${ORIGIN}/?mode=wharrgarbl`)).toBe(false);
    expect(self.isRetailRequest(`${ORIGIN}/results?q=leche`)).toBe(false);
  });

  it("never caches the demand service, even from a consumer URL", () => {
    const { self } = loadWorker();
    expect(self.isRetailRequest(`${ORIGIN}/demand/api/analytics`)).toBe(true);
  });

  it("goes to the network for a retail request instead of reading the cache", async () => {
    const network = vi.fn(async () => "network response");
    const { handlers, caches } = loadWorker(network);

    await dispatchFetch(handlers, { url: `${ORIGIN}/?mode=retail`, mode: "navigate" });

    expect(network).toHaveBeenCalled();
    // The load-bearing assertion: a cached dashboard would show yesterday's
    // demand numbers with nothing on screen saying they are stale.
    expect(caches.match).not.toHaveBeenCalled();
    expect(caches.open).not.toHaveBeenCalled();
  });

  it("falls back to the cached shell for a consumer navigation when offline", async () => {
    const { handlers, caches } = loadWorker(offline());

    await dispatchFetch(handlers, { url: `${ORIGIN}/results?q=leche`, mode: "navigate" });

    expect(caches.match).toHaveBeenCalledWith("/");
  });

  it("does not touch the cache for a retail navigation even when offline", async () => {
    const { handlers, caches } = loadWorker(offline());

    const responded = dispatchFetch(handlers, {
      url: `${ORIGIN}/results?mode=retail`,
      mode: "navigate",
    });

    // Failing is the correct outcome. An offline shopkeeper must see the
    // request fail, not a stale dashboard that looks current.
    await expect(responded).rejects.toThrow("offline");
    expect(caches.match).not.toHaveBeenCalled();
  });

  it("precaches only consumer URLs", () => {
    // No retail URL can appear here, because retail has no URL of its own —
    // it is a query param on the consumer routes. Asserted against the source
    // so a future edit adding "/?mode=retail" to PRECACHE trips this test.
    const precache = SW_SOURCE.match(/const PRECACHE = \[(.*?)\]/s)?.[1] ?? "";
    expect(precache).toContain('"/"');
    expect(precache).not.toContain("mode=retail");
  });

  it("leaves non-GET and cross-origin requests entirely alone", () => {
    const { handlers } = loadWorker();

    // No respondWith at all means the browser's default handling — the two
    // APIs and the map tiles must never be intercepted.
    expect(dispatchFetch(handlers, { url: `${ORIGIN}/`, method: "POST" })).toBeUndefined();
    expect(dispatchFetch(handlers, { url: "https://tiles.example/1/2/3.png" })).toBeUndefined();
  });
});

describe("manifest", () => {
  const manifest = JSON.parse(
    readFileSync(
      join(dirname(fileURLToPath(import.meta.url)), "..", "..", "public", "manifest.webmanifest"),
      "utf-8",
    ),
  );

  it("starts in consumer mode and scopes the whole app", () => {
    // start_url is "/", never
    // "/shop?source=pwa" and never a retail URL. An installed app that opened
    // into the dashboard would be an offline-capable shell around exactly the
    // surface U5 exists to keep out of the cache.
    expect(manifest.start_url).toBe("/");
    expect(manifest.scope).toBe("/");
    expect(JSON.stringify(manifest)).not.toContain("mode=retail");
  });
});

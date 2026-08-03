/**
 * Service-worker registration (U5). Called once from `main.tsx`.
 *
 * Registration is deliberately unconditional on mode: one worker with one
 * scope, whose own fetch handler bypasses retail traffic. Registering only in
 * consumer mode would be worse, not safer — the worker outlives the page, so
 * a shopper who later flips to `?mode=retail` would still be served by a
 * worker registered earlier, and the "only register in consumer" rule would
 * have bought nothing while looking like a guarantee.
 *
 * The bypass lives in `public/sw.js` because that is the only place it can be
 * enforced.
 */
export function registerServiceWorker(): void {
  if (!("serviceWorker" in navigator)) return;
  // Dev builds serve modules from Vite; a worker caching them would fight the
  // dev server's own reload machinery.
  if (import.meta.env.DEV) return;

  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(() => {
      // A failed registration costs offline support and nothing else. The app
      // works; there is nothing to tell the shopper.
    });
  });
}

import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

export default defineConfig({
  // Mirrors vite.config.ts's "@" alias — the app bundler resolves it, but
  // vitest runs its own resolution pipeline and doesn't inherit vite.config.ts
  // aliases automatically, so bklit's `@/components/...` imports (e.g.
  // bar-chart.tsx importing `@/components/retail/charts/bklit/lib/utils`)
  // fail to resolve under `npm test` without this.
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  test: {
    environment: "jsdom",
    // Registers RTL cleanup and the jsdom scrollTo stub for every test file —
    // see vitest.setup.ts for why both are needed.
    setupFiles: ["./vitest.setup.ts"],
  },
});

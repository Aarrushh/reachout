import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "jsdom",
    // Registers RTL cleanup and the jsdom scrollTo stub for every test file —
    // see vitest.setup.ts for why both are needed.
    setupFiles: ["./vitest.setup.ts"],
  },
});

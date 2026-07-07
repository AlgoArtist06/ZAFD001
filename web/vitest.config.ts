import { resolve } from "node:path";

import { defineConfig } from "vitest/config";

// Vitest transforms TSX through its built-in oxc transform (automatic JSX
// runtime), so the React shell components can be exercised in jsdom without a
// bundler plugin.
export default defineConfig({
  resolve: {
    alias: {
      "@": resolve(__dirname, "./src"),
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./vitest.setup.ts"],
    include: ["src/**/*.test.{ts,tsx}", "tests/**/*.test.ts"],
    // Convex function tests declare `@vitest-environment edge-runtime` per
    // file, matching the real Convex runtime; the rest default to jsdom.
    server: { deps: { inline: ["convex-test"] } },
  },
});

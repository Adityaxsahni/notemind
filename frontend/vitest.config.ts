import { fileURLToPath } from "node:url";

import { defineConfig } from "vitest/config";

export default defineConfig({
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  // Unit tests only; e2e/ holds the Playwright specs (npm run test:e2e).
  test: { environment: "node", include: ["src/**/*.test.ts"] },
});

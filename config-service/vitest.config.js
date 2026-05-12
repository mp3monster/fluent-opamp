import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "jsdom",
    include: ["ui-unit-tests/**/*.test.js"],
  },
});

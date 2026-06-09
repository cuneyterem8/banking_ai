import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: ["../.agent_test/frontend_tests/**/*.{test,spec}.?(c|m)[jt]s?(x)"],
  },
});

import { existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "@playwright/test";

// The browser end-to-end tests: a real browser, the real web app, the real API on a throwaway
// database, and the Firebase emulators (started by `npm run e2e` through scripts/with-emulators.mjs).
export const API_PORT = 8010;
export const WEB_PORT = 5183;

const here = dirname(fileURLToPath(import.meta.url));
const apiDir = resolve(here, "../api");
const python =
  [resolve(apiDir, ".venv/Scripts/python.exe"), resolve(apiDir, ".venv/bin/python")].find(existsSync) ?? "python";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1, // the specs share one database, so they run one after another
  timeout: 240_000,
  expect: { timeout: 20_000 },
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: `http://127.0.0.1:${WEB_PORT}`,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { browserName: "chromium" } }],
  webServer: [
    {
      command: `"${python}" -m scripts.run_e2e_api`,
      cwd: apiDir,
      url: `http://127.0.0.1:${API_PORT}/health`,
      timeout: 180_000,
      reuseExistingServer: false,
      env: { E2E_API_PORT: String(API_PORT) },
    },
    {
      command: `npx vite --port ${WEB_PORT} --strictPort --host 127.0.0.1`,
      url: `http://127.0.0.1:${WEB_PORT}`,
      timeout: 120_000,
      reuseExistingServer: false,
      env: {
        VITE_FIREBASE_EMULATORS: "true",
        VITE_FIREBASE_API_KEY: "e2e-key",
        VITE_FIREBASE_AUTH_DOMAIN: "localhost",
        VITE_FIREBASE_PROJECT_ID: "demo-residue",
        VITE_FIREBASE_APP_ID: "e2e-app",
        VITE_API_PROXY: `http://127.0.0.1:${API_PORT}`,
        VITE_REQUIRE_VERIFIED_PHONE: "false",
      },
    },
  ],
});

/// <reference types="vitest" />
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  server: { port: 5173, proxy: { "/api": process.env.VITE_API_PROXY ?? "http://localhost:8000" } },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/setupTests.ts"],
    clearMocks: true,
    exclude: ["node_modules/**", "dist/**", "tests/rules/**", "e2e/**"], // those run on the emulators
  },
});

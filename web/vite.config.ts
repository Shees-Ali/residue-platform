/// <reference types="vitest" />
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";
import { defineConfig, loadEnv } from "vite";

export default defineConfig(({ mode }) => {
  const env = { ...loadEnv(mode, process.cwd(), ""), ...process.env }; // .env files and the shell
  return {
    plugins: [react()],
    resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
    server: {
      port: 5173,
      // Hostnames allowed besides localhost, e.g. an HTTPS tunnel for trying /phone on a mobile.
      allowedHosts: env.VITE_ALLOWED_HOSTS?.split(",").map((h) => h.trim()),
      proxy: {
        "/api": env.VITE_API_PROXY ?? "http://localhost:8000",
        "/browser": { target: env.VITE_VOICE_PROXY ?? "http://localhost:8001", ws: true },
      },
    },
    test: {
      environment: "jsdom",
      globals: true,
      setupFiles: ["./src/setupTests.ts"],
      clearMocks: true,
      exclude: ["node_modules/**", "dist/**", "tests/rules/**", "e2e/**"], // those run on the emulators
    },
  };
});

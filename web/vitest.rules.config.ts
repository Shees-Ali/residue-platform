import { defineConfig } from "vitest/config";

// The security-rules tests talk to the Firestore emulator (see `npm run test:rules`).
export default defineConfig({
  test: { environment: "node", globals: true, include: ["tests/rules/**/*.test.ts"], testTimeout: 20_000 },
});

// Run a command inside the Firebase emulators and always stop them afterwards.
//
//   node scripts/with-emulators.mjs <only> <command...>      e.g.  firestore vitest run ...
//
// `firebase emulators:exec` leaves the Java emulator running on Windows when the command ends, which
// blocks the next run ("port taken"). This wrapper stops any emulator it finds on the ports first
// and last. It only ever touches processes whose command line mentions an emulator.
import { execSync, spawn } from "node:child_process";

const PORTS = [8080, 9099, 4400, 4500, 9150, 9299];
const [only, ...command] = process.argv.slice(2);
if (!only || command.length === 0) {
  console.error("usage: with-emulators.mjs <firestore|auth,firestore> <command...>");
  process.exit(2);
}

function emulatorPids() {
  if (process.platform !== "win32") return [];
  const pids = new Set();
  const out = execSync("netstat -ano -p tcp", { encoding: "utf8" });
  for (const line of out.split(/\r?\n/)) {
    const cols = line.trim().split(/\s+/);
    if (cols[3] !== "LISTENING") continue;
    const port = Number(cols[1].split(":").pop());
    if (PORTS.includes(port)) pids.add(cols[4]);
  }
  return [...pids].filter((pid) => {
    try {
      const cmd = execSync(
        `powershell -NoProfile -Command "(Get-CimInstance Win32_Process -Filter 'ProcessId=${pid}').CommandLine"`,
        { encoding: "utf8" },
      );
      return /emulator/i.test(cmd);
    } catch {
      return false;
    }
  });
}

function stopEmulators() {
  for (const pid of emulatorPids()) {
    try {
      execSync(`taskkill /F /T /PID ${pid}`, { stdio: "ignore" });
    } catch {
      /* already gone */
    }
  }
}

stopEmulators();
const quoted = `"${command.join(" ").replace(/"/g, '\\"')}"`;
const child = spawn(
  `firebase emulators:exec --only ${only} --config ../deploy/firebase.json --project demo-residue ${quoted}`,
  { stdio: "inherit", shell: true },
);
child.on("exit", (code) => {
  stopEmulators();
  process.exit(code ?? 1);
});
process.on("SIGINT", () => {
  stopEmulators();
  process.exit(130);
});

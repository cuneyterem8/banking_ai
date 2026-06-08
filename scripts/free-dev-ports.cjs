#!/usr/bin/env node
/**
 * Frees local dev ports before npm run dev:full (Windows: WinError 10048 if a stale uvicorn is left running).
 */
const { execSync, spawnSync } = require("child_process");

const PORTS = [
  { port: 8001, label: "backend (uvicorn)" },
  { port: 5173, label: "frontend (vite)" }
];

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function pidsOnPortWindows(port) {
  try {
    const output = execSync(`netstat -ano | findstr ":${port}"`, { encoding: "utf8" });
    const pids = new Set();
    for (const line of output.split(/\r?\n/)) {
      if (!line.includes("LISTENING")) {
        continue;
      }
      const parts = line.trim().split(/\s+/);
      const pid = Number(parts[parts.length - 1]);
      if (pid > 0) {
        pids.add(pid);
      }
    }
    return [...pids];
  } catch {
    return [];
  }
}

function pidsOnPortUnix(port) {
  try {
    const output = execSync(`lsof -ti tcp:${port} -sTCP:LISTEN`, { encoding: "utf8" });
    return output
      .split(/\r?\n/)
      .map((value) => Number(value.trim()))
      .filter((pid) => pid > 0);
  } catch {
    return [];
  }
}

function killPid(pid) {
  if (process.platform === "win32") {
    spawnSync("taskkill", ["/PID", String(pid), "/F", "/T"], { stdio: "ignore" });
    return;
  }
  try {
    process.kill(pid, "SIGTERM");
  } catch {
    // already gone
  }
}

function freePort(port, label) {
  const pids =
    process.platform === "win32" ? pidsOnPortWindows(port) : pidsOnPortUnix(port);
  if (!pids.length) {
    return;
  }
  console.log(`Port ${port} (${label}) in use by PID(s): ${pids.join(", ")}. Stopping...`);
  for (const pid of pids) {
    killPid(pid);
  }
}

async function main() {
  for (const { port, label } of PORTS) {
    freePort(port, label);
  }
  await sleep(400);
  for (const { port, label } of PORTS) {
    const remaining =
      process.platform === "win32" ? pidsOnPortWindows(port) : pidsOnPortUnix(port);
    if (remaining.length) {
      console.error(`Port ${port} (${label}) is still in use. Close the old terminal or run: npm run dev:stop`);
      process.exit(1);
    }
  }
  console.log("Dev ports 8001 and 5173 are free.");
}

main();

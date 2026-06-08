#!/usr/bin/env node
const { spawnSync } = require("child_process");
const fs = require("fs");
const path = require("path");

const root = path.resolve(__dirname, "..");
const isWin = process.platform === "win32";
const venvDir = path.join(root, ".venv");
const python = isWin
  ? path.join(venvDir, "Scripts", "python.exe")
  : path.join(venvDir, "bin", "python");

function run(cmd, args, options = {}) {
  const result = spawnSync(cmd, args, { stdio: "inherit", ...options });
  if (result.status !== 0) {
    process.exit(result.status ?? 1);
  }
}

if (!fs.existsSync(python)) {
  console.log("Creating virtual environment at .venv ...");
  run("python", ["-m", "venv", venvDir], { cwd: root });
}

console.log("Installing Python dependencies (including AutoGluon) ...");
run(
  python,
  [
    "-m",
    "pip",
    "install",
    "--upgrade",
    "pip",
    "-r",
    path.join(root, "backend", "requirements.txt"),
    "-r",
    path.join(root, "backend", "requirements-ai.txt"),
  ],
  { cwd: root }
);

console.log("Backend virtual environment is ready.");

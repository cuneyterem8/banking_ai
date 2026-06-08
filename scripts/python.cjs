#!/usr/bin/env node
/**
 * Run commands with the project virtualenv Python (cross-platform).
 */
const { spawnSync } = require("child_process");
const fs = require("fs");
const path = require("path");

const root = path.resolve(__dirname, "..");
const isWin = process.platform === "win32";
const python = isWin
  ? path.join(root, ".venv", "Scripts", "python.exe")
  : path.join(root, ".venv", "bin", "python");

if (!fs.existsSync(python)) {
  console.error(
    "Virtual environment not found. Run: npm run setup:backend"
  );
  process.exit(1);
}

const args = process.argv.slice(2);
if (args.length === 0) {
  console.error("Usage: node scripts/python.cjs <python-args...>");
  process.exit(1);
}

const result = spawnSync(python, args, {
  stdio: "inherit",
  cwd: path.join(root, "backend"),
  env: process.env,
});

process.exit(result.status ?? 1);

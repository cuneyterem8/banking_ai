#!/usr/bin/env node
const http = require("http");

const readyUrl = "http://127.0.0.1:8001/api/ready";
const healthUrl = "http://127.0.0.1:8001/api/health";
const maxAttempts = 120;
const delayMs = 500;

function probe(url) {
  return new Promise((resolve, reject) => {
    const req = http.get(url, (res) => {
      let body = "";
      res.on("data", (chunk) => {
        body += chunk;
      });
      res.on("end", () => {
        if (res.statusCode === 200) {
          resolve(body);
          return;
        }
        reject(new Error(`Unexpected status ${res.statusCode} for ${url}`));
      });
    });
    req.on("error", reject);
    req.setTimeout(5000, () => {
      req.destroy(new Error("timeout"));
    });
  });
}

async function waitForPortalReady() {
  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    try {
      const body = await probe(readyUrl);
      const payload = JSON.parse(body);
      const mlNote = payload.ml_training_ready
        ? "ML startup training is complete."
        : `ML startup still running (phase=${payload.ml_phase}).`;
      console.log(`Portal API ready. ${mlNote}`);
      return;
    } catch {
      if (attempt === maxAttempts) {
        console.error("Timed out waiting for backend /api/ready");
        process.exit(1);
      }
      await new Promise((resolve) => setTimeout(resolve, delayMs));
    }
  }
}

async function main() {
  try {
    await probe(healthUrl);
  } catch {
    // /api/ready also checks the database; continue polling ready.
  }
  await waitForPortalReady();
  console.log("Starting frontend.");
}

main();

#!/usr/bin/env node
/**
 * Metro cannot bundle packages symlinked outside apps/mobile (pnpm → ~/node_modules/.pnpm).
 * Replace external symlinks under node_modules with real copies (cp -RL dereferences nested links).
 *
 * Run automatically from postinstall and mobile-expo.sh before Metro starts.
 */
const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");

const root = path.join(__dirname, "..");
const nodeModules = path.join(root, "node_modules");

function isOutsideRoot(realPath) {
  const normalized = path.resolve(realPath);
  return normalized !== root && !normalized.startsWith(`${root}${path.sep}`);
}

function listPackagePaths(dir, depth) {
  const out = [];
  if (!fs.existsSync(dir)) {
    return out;
  }
  for (const name of fs.readdirSync(dir)) {
    if (name === ".bin" || name === ".cache") {
      continue;
    }
    out.push(path.join(dir, name));
    if (depth === 0 && name.startsWith("@")) {
      const scopeDir = path.join(dir, name);
      if (fs.existsSync(scopeDir) && fs.statSync(scopeDir).isDirectory()) {
        for (const scoped of fs.readdirSync(scopeDir)) {
          out.push(path.join(scopeDir, scoped));
        }
      }
    }
  }
  return out;
}

function isExternalSymlink(packagePath) {
  try {
    if (!fs.lstatSync(packagePath).isSymbolicLink()) {
      return false;
    }
    return isOutsideRoot(fs.realpathSync(packagePath));
  } catch {
    return false;
  }
}

function materializePackage(packagePath) {
  const real = fs.realpathSync(packagePath);
  const rel = path.relative(root, packagePath);
  fs.rmSync(packagePath, { recursive: true, force: true });
  execSync(`cp -RL "${real}" "${packagePath}"`, { stdio: "pipe" });
  console.log(`Metro-local: materialized ${rel}`);
}

function countExternalSymlinks() {
  let count = 0;
  for (const packagePath of listPackagePaths(nodeModules, 0)) {
    if (isExternalSymlink(packagePath)) {
      count += 1;
    }
  }
  return count;
}

function main() {
  const checkOnly = process.argv.includes("--check");

  if (!fs.existsSync(nodeModules)) {
    if (checkOnly) {
      process.exit(1);
    }
    console.error("ERROR: node_modules missing — run: bash scripts/mobile-install.sh");
    process.exit(1);
  }

  const before = countExternalSymlinks();
  if (before === 0) {
    if (checkOnly) {
      process.exit(0);
    }
    return;
  }

  if (checkOnly) {
    process.exit(1);
  }

  console.log(`==> Metro-local deps: ${before} external symlink(s) under node_modules`);
  for (const packagePath of listPackagePaths(nodeModules, 0)) {
    if (isExternalSymlink(packagePath)) {
      materializePackage(packagePath);
    }
  }

  const after = countExternalSymlinks();
  if (after > 0) {
    console.error(`ERROR: ${after} external symlink(s) remain — run: bash scripts/mobile-install.sh`);
    process.exit(1);
  }
  console.log("OK Metro-local node_modules (no external symlinks)");
}

main();

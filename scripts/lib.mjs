// Shared helpers for setup/dev scripts. Cross-platform: no shell-specific syntax.
import { spawn, spawnSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import net from "node:net";
import path from "node:path";
import { fileURLToPath } from "node:url";

export const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
export const isWin = process.platform === "win32";
export const venvPy = path.join(ROOT, ".venv", isWin ? "Scripts/python.exe" : "bin/python");
export const API_DIR = path.join(ROOT, "apps", "api");
export const WEB_DIR = path.join(ROOT, "apps", "web");

export function run(cmd, args, opts = {}) {
  const r = spawnSync(cmd, args, { stdio: "inherit", shell: isWin && /\.(cmd|bat)$|^npm$|^npx$/.test(cmd), ...opts });
  return r.status === 0;
}

export function spawnLong(name, cmd, args, opts = {}) {
  const p = spawn(cmd, args, { stdio: ["ignore", "pipe", "pipe"], shell: isWin && /^npm$|^npx$/.test(cmd), ...opts });
  const tag = `[${name}] `;
  const pipe = (s) => s.on("data", (d) => String(d).split(/\r?\n/).filter(Boolean).forEach((l) => console.log(tag + l)));
  pipe(p.stdout);
  pipe(p.stderr);
  p.on("exit", (c) => console.log(`${tag}exited (${c})`));
  return p;
}

export function loadEnv() {
  const f = path.join(ROOT, ".env");
  const env = {};
  if (existsSync(f)) {
    for (const line of readFileSync(f, "utf8").split(/\r?\n/)) {
      const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*([^#]*?)\s*(?:#.*)?$/);
      if (m) env[m[1]] = m[2];
    }
  }
  return env;
}

export function portFree(port) {
  return new Promise((res) => {
    const s = net.createServer().once("error", () => res(false)).once("listening", () => s.close(() => res(true)));
    s.listen(port, "127.0.0.1");
  });
}

export async function freePort(start) {
  for (let p = start; p < start + 50; p++) if (await portFree(p)) return p;
  throw new Error(`No free port near ${start}`);
}

export function findFfmpeg() {
  const probe = (c) => spawnSync(c, ["-version"], { stdio: "ignore" }).status === 0;
  if (probe("ffmpeg")) return "ffmpeg";
  if (isWin) {
    const base = path.join(process.env.LOCALAPPDATA || "", "Microsoft", "WinGet", "Packages");
    const link = path.join(process.env.LOCALAPPDATA || "", "Microsoft", "WinGet", "Links", "ffmpeg.exe");
    if (existsSync(link) && probe(link)) return link;
    if (existsSync(base)) {
      const r = spawnSync("where", ["/r", base, "ffmpeg.exe"], { encoding: "utf8" });
      const hit = (r.stdout || "").split(/\r?\n/).find(Boolean);
      if (hit && probe(hit)) return hit;
    }
  }
  return null;
}

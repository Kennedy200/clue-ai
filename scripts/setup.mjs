// npm run setup  — installs everything needed to run Clue AI locally.
import { copyFileSync, existsSync } from "node:fs";
import path from "node:path";
import { API_DIR, ROOT, WEB_DIR, findFfmpeg, isWin, run, venvPy } from "./lib.mjs";

const step = (m) => console.log(`\n==> ${m}`);
const fail = (m) => { console.error(`\nSetup stopped: ${m}`); process.exit(1); };

step("Checking Node and Python");
if (Number(process.versions.node.split(".")[0]) < 20) fail("Node 20+ is required.");
const pyCmd = isWin ? "py" : "python3";
const pyArgs = isWin ? ["-3.12"] : [];
if (!existsSync(venvPy)) {
  step("Creating Python virtual environment (.venv)");
  if (!run(pyCmd, [...pyArgs, "-m", "venv", path.join(ROOT, ".venv")])) fail("Python 3.12 is required (https://www.python.org/downloads/).");
}

step("Installing Python packages");
if (!run(venvPy, ["-m", "pip", "install", "-q", "-r", path.join(API_DIR, "requirements.txt")])) fail("pip install failed.");

step("Installing web packages");
if (!run("npm", ["install", "--no-audit", "--no-fund"], { cwd: WEB_DIR })) fail("npm install failed.");

step("Checking FFmpeg");
const ff = findFfmpeg();
if (ff) console.log(`FFmpeg found: ${ff}`);
else console.log("FFmpeg is missing. Install it, then reopen your terminal:\n  winget install Gyan.FFmpeg   (Windows)\n  brew install ffmpeg          (macOS)\n  sudo apt install ffmpeg      (Linux)");

step("Creating .env");
const env = path.join(ROOT, ".env");
if (!existsSync(env)) { copyFileSync(path.join(ROOT, ".env.example"), env); console.log("Created .env (edit it or use /setup in the app)."); }

step("Preparing the database");
if (!run(venvPy, ["-m", "alembic", "upgrade", "head"], { cwd: API_DIR })) fail("database migration failed.");
if (!run(venvPy, ["-m", "clue.seed"], { cwd: API_DIR })) fail("seeding failed.");

console.log("\nSetup complete. Start everything with:  npm run dev");
console.log("(Voice and transcription models are downloaded on first use in a later phase.)");

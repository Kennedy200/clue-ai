// npm run dev — starts API + worker + web and prints the links table.
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { API_DIR, ROOT, WEB_DIR, freePort, loadEnv, run, spawnLong, venvPy } from "./lib.mjs";

if (!existsSync(venvPy)) { console.error("Run `npm run setup` first."); process.exit(1); }
const env = loadEnv();
const apiPort = await freePort(Number(env.API_PORT || 8000));
const webPort = await freePort(Number(env.WEB_PORT || 3000));
const siteUrl = `http://localhost:${webPort}`;

const childEnv = { ...process.env, ...env, API_PORT: String(apiPort), WEB_PORT: String(webPort), SITE_URL: siteUrl, PYTHONUNBUFFERED: "1", HF_HUB_DISABLE_SYMLINKS_WARNING: "1", PYTHONIOENCODING: "utf-8" };

if (!run(venvPy, ["-m", "alembic", "upgrade", "head"], { cwd: API_DIR, env: childEnv })) process.exit(1);
run(venvPy, ["-m", "clue.seed"], { cwd: API_DIR, env: childEnv, stdio: "ignore" });

const procs = [
  spawnLong("api", venvPy, ["-m", "uvicorn", "clue.main:app", ...(process.env.API_RELOAD === "1" ? ["--reload"] : []), "--port", String(apiPort)], { cwd: API_DIR, env: childEnv }),
  spawnLong("worker", venvPy, ["-m", "clue.worker"], { cwd: API_DIR, env: childEnv }),
  spawnLong("web", "npm", ["run", "dev", "--", "--port", String(webPort)], { cwd: WEB_DIR, env: childEnv }),
];

let creds = {};
const cf = path.join(ROOT, "storage", "demo-credentials.json");
if (existsSync(cf)) creds = JSON.parse(readFileSync(cf, "utf8"));
const pw = (e) => creds[e] || "(see storage/demo-credentials.json)";

const table = `Clue AI is running
  App ........... ${siteUrl}
  Admin ......... ${siteUrl}/admin
  Setup (key) ... ${siteUrl}/setup
  API docs ...... http://localhost:${apiPort}/docs
  Dev inbox ..... ${siteUrl}/dev-mail
  Demo login .... demo@clue.local / ${pw("demo@clue.local")}
  Admin login ... admin@clue.local / ${pw("admin@clue.local")}
`;
setTimeout(() => { console.log("\n" + table); writeFileSync(path.join(ROOT, "RUNNING.md"), "# Running\n\n```\n" + table + "```\n"); }, 4000);

const stop = () => { procs.forEach((p) => p.kill()); process.exit(0); };
process.on("SIGINT", stop);
process.on("SIGTERM", stop);

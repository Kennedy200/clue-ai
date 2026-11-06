// npm run verify:llm — runs every AI feature against your REAL OpenRouter key (about 5 requests of your free quota).
import { API_DIR, run, venvPy } from "./lib.mjs";

console.log("Checking every AI feature against the real model. Save your key at /setup first.\n");
const ok = run(venvPy, ["scripts_verify_llm.py"], { cwd: API_DIR });
process.exit(ok ? 0 : 1);

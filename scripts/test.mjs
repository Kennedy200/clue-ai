import path from "node:path";
import { API_DIR, run, venvPy } from "./lib.mjs";
process.exit(run(venvPy, ["-m", "pytest", "-q"], { cwd: API_DIR }) ? 0 : 1);

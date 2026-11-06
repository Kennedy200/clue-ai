// Fails if tracked/staged files contain API-key-looking strings. Run before every push.
import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
const files = spawnSync("git", ["ls-files", "--cached", "--others", "--exclude-standard"], { encoding: "utf8" }).stdout.split(/\r?\n/).filter(Boolean);
const pats = [/sk-or-v1-[A-Za-z0-9]{20,}/, /sk-ant-[A-Za-z0-9_-]{20,}/, /AIza[0-9A-Za-z_-]{30,}/, /sk_(live|test)_[A-Za-z0-9]{20,}/, /-----BEGIN (RSA |EC )?PRIVATE KEY-----/, /ghp_[A-Za-z0-9]{30,}/];
let bad = 0;
for (const f of files) {
  if (/\.(png|jpg|ico|woff2?|xlsx|mp4)$/i.test(f)) continue;
  let t; try { t = readFileSync(f, "utf8"); } catch { continue; }
  for (const p of pats) if (p.test(t)) { console.error(`SECRET-LIKE string in ${f} (${p})`); bad++; }
}
if (bad) { console.error(`\n${bad} finding(s). Push blocked.`); process.exit(1); }
console.log(`Secret scan clean (${files.length} files).`);

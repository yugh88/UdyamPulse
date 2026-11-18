// CI gate for the full dependency tree: fail on any moderate+ advisory that is not in audit-allowlist.json,
// and on any allowlist entry past its review date. Production dependencies are audited separately, strictly.
import { execSync } from "node:child_process";
import { readFileSync } from "node:fs";
import process from "node:process";

const allow = JSON.parse(readFileSync("audit-allowlist.json", "utf8"));
let raw;
try {
  raw = execSync("npm audit --json", { encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] });
} catch (e) {
  raw = e.stdout; // npm audit exits non-zero when it finds anything
}
const report = JSON.parse(raw);
const rank = { info: 0, low: 1, moderate: 2, high: 3, critical: 4 };
const today = new Date().toISOString().slice(0, 10);
const problems = [];
for (const [name, v] of Object.entries(report.vulnerabilities ?? {})) {
  for (const via of v.via) {
    if (typeof via !== "object" || rank[via.severity] < rank.moderate) continue;
    const id = via.url?.split("/").pop();
    const ok = allow[id];
    if (!ok) problems.push(`${name}: ${via.severity} ${id} ${via.title}`);
    else if (ok.review_by < today) problems.push(`${id}: allowlist entry expired on ${ok.review_by}; review it`);
  }
}
const unique = [...new Set(problems)];
if (unique.length) {
  console.error(`npm audit gate failed:\n${unique.join("\n")}`);
  process.exit(1);
}
console.log(`npm audit gate passed (${Object.keys(allow).filter((k) => !k.startsWith("_")).length} allowlisted advisory)`);

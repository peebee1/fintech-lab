// Harness: evaluate every case in a JSON file using the shipped policy module.
// Usage: node tests/harness.mjs tests/cases.json
import { readFileSync } from "node:fs";
import { evaluate } from "../policy.mjs";

const path = process.argv[2];
const cases = JSON.parse(readFileSync(path, "utf8"));
const out = cases.map((c) => {
  const got = evaluate(c.intent, c.ctx);
  return {
    name: c.name,
    expect: c.expect,
    got,
    pass: got.verdict === c.expect.verdict && got.rule === c.expect.rule,
  };
});
process.stdout.write(JSON.stringify(out, null, 2));

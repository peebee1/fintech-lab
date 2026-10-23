// Measure the cost of one policy evaluation and record the case table.
// Output is committed so the README numbers are reproducible.
import { readFileSync, writeFileSync } from "node:fs";
import { evaluate, RULES } from "./policy.mjs";

const RUNS = 200000;
const ctx = { hour: 12, available: RULES.budget, history: [] };
const intent = { merchant: "Staples", amount: 80 };

for (let i = 0; i < 5000; i += 1) evaluate(intent, ctx); // warm up

const t0 = performance.now();
for (let i = 0; i < RUNS; i += 1) evaluate(intent, ctx);
const totalMs = performance.now() - t0;

const bench = {
  runs: RUNS,
  total_ms: Number(totalMs.toFixed(3)),
  us_per_decision: Number(((totalMs * 1000) / RUNS).toFixed(4)),
  decisions_per_second: Math.round(RUNS / (totalMs / 1000)),
};
writeFileSync("results/bench.json", JSON.stringify(bench, null, 2) + "\n");

const cases = JSON.parse(readFileSync("tests/cases.json", "utf8"));
const table = cases.map((c) => ({
  name: c.name,
  amount: c.intent.amount,
  merchant: c.intent.merchant,
  verdict: evaluate(c.intent, c.ctx).verdict,
  rule: evaluate(c.intent, c.ctx).rule,
}));
writeFileSync("results/cases.json", JSON.stringify(table, null, 2) + "\n");
console.log(JSON.stringify(bench));

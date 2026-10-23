// Policy engine. Pure, deterministic, no DOM, no clock, no network.
// The UI and the tests both import this file, so what ships is what is measured.

export const RULES = {
  budget: 300,
  maxTxn: 250,
  approvalAbove: 100,
  allow: ["Blue Bottle", "Whole Foods", "United Airlines", "Notion", "Staples", "Uber"],
  window: [6, 23],
  velocityLimit: 3,
};

/**
 * Decide a single payment intent.
 * @param {{merchant:string, amount:number}} intent
 * @param {{hour:number, available:number, history:Array<{merchant:string,amount:number}>}} ctx
 * @returns {{verdict:'allow'|'deny'|'pending', rule:string}}
 */
export function evaluate(intent, ctx) {
  const { hour, available, history } = ctx;

  if (hour < RULES.window[0] || hour >= RULES.window[1]) {
    return { verdict: "deny", rule: "outside settlement window" };
  }
  if (!RULES.allow.includes(intent.merchant)) {
    return { verdict: "deny", rule: "merchant not on allowlist" };
  }
  if (intent.amount > RULES.maxTxn) {
    return { verdict: "deny", rule: "over per-transaction cap" };
  }
  const same = history.filter(
    (h) => h.merchant === intent.merchant && h.amount === intent.amount,
  ).length;
  if (same >= RULES.velocityLimit) {
    return { verdict: "deny", rule: "velocity limit hit" };
  }
  if (intent.amount > available) {
    return { verdict: "deny", rule: "would exceed daily budget" };
  }
  if (intent.amount > RULES.approvalAbove) {
    return { verdict: "pending", rule: "above approval threshold" };
  }
  return { verdict: "allow", rule: "within budget" };
}

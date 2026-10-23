# Spend policy engine for agent-initiated payments

A decision layer that sits between an agent that wants to spend and the rail that
would move the money. It answers one question per intent: allow, deny, or hold for a
human. It then reserves the amount so parallel agents cannot spend the same budget twice.

Interactive demo: `index.html`, with the policy logic in `policy.mjs`.

## Problem

Agents can now check out on their own. The card or rail they call has no idea whether
the agent should be allowed to. Teams bolt on a spreadsheet, a Slack approval, or a
hard-coded amount cap, and none of those hold when several agents run at once.

## Why it matters

An agent that overspends is not a prompt problem, it is a control problem. The
failure mode is quiet: three agents each check a 100 EUR budget, each see room,
and together spend 300. A decision layer that reserves at decision time is the
difference between a policy and a suggestion.

## Design

```
intent -> evaluate(rules, context) -> allow | deny | pending
                                   -> reserve on allow/pending
                                   -> settle or release later
                                   -> append to the decision log
```

Every decision returns the rule that fired, so the log is explainable without a debugger.

| Decision | Choice | Tradeoff |
|---|---|---|
| Policy location | Pure function, no I/O | Fast and testable, but the caller must persist state |
| Budget safety | Reserve at decision time | Prevents parallel overrun, adds a release path to get wrong |
| Approval | Threshold creates a pending hold | Human stays in the loop, budget is frozen while waiting |
| Ordering | Window, merchant, cap, velocity, budget, approval | Cheap checks first, but ordering changes which rule is named |
| Transport | Static HTML plus ES modules | No build step, needs a local server because of module CORS |

## Run

```bash
cd artifacts/2026-10-22-agent-spend-policy
python3 -m http.server 8765
# open http://localhost:8765/index.html
```

Tests, which execute the shipped `policy.mjs` through node:

```bash
uv run pytest -q artifacts/2026-10-22-agent-spend-policy
```

Regenerate the committed numbers:

```bash
node bench.mjs   # writes results/bench.json and results/cases.json
```

## Results

Measured on this machine, node 24.13.1, Apple silicon. `node bench.mjs`, 200,000 runs:

| Metric | Value |
|---|---|
| Cost per decision | 0.0698 microseconds |
| Decisions per second | 14,334,178 |
| Test cases passing | 10 of 10 |

Seeded demo run against a 300 EUR daily budget, from `results/cases.json` and the UI:

| Intent | Amount | Verdict | Rule |
|---|---|---|---|
| Blue Bottle | 4.50 | allow | within budget |
| United Airlines | 620.00 | deny | over per-transaction cap |
| Notion | 149.00 | pending | above approval threshold |
| Staples, burst of 5 | 80.00 each | 1 allow, 4 deny | would exceed daily budget |
| Coinbase | 40.00 | deny | merchant not on allowlist |

Total prevented in that run: 940.00 EUR. Budget reconciles to the cent:
84.50 settled plus 149.00 reserved plus 66.50 available equals 300.00.

## Limits

- State is in memory. Reload the page and the ledger is gone.
- One agent and one budget. Multi agent pooling is not modelled.
- Velocity counts identical merchant and amount pairs, with no time component in the
  policy function, so it cannot distinguish a burst from a slow repeat.
- No idempotency keys, no settlement confirmation from a rail, no currency handling.
- The rules are illustrative, not a recommendation for a real treasury policy.
- The demo reads the wall clock for the settlement window, so a run after 23:00 denies
  everything. Tests pin the hour and are unaffected.

## Next

- Idempotency keys and a replay-safe decision log.
- Persist reservations, so a restart cannot free money that was already committed.
- Per-agent and per-team budget pools with atomic holds.
- Signed decision receipts with a policy version hash, for audit.
- A rail adapter interface, so the engine can gate a real card or ACP checkout.

# Hardening queue

Fixes to the repos people already see. Priority is impact x confidence / effort, per
`RUBRIC.md` section 5. Machine readable source is `state/hardening.json`.

| Priority | Repo | Fix | Defect |
|---|---|---|---|
| 6.7 | angelone-smartapi | Decide what the public main branch of the trading agent should show | origin/main holds the day-0 skeleton: no mandate/ package, no test_mandate.py. The 60 day work lives only on feat/60-day-mandate, so a stranger cloning main sees a smaller repo than the README describes. |
| 6.0 | agentic-commerce-protocol-poc | Make the ACP benchmark a committed results file | bench/results.md is prose. There is no machine-readable result and no threshold that fails a regression. |
| 5.0 | shopping-concierge | Refresh the stale catalog and eval numbers | Committed data is 79 days old and the eval report quotes stale freshness labels. |

## Done

| Repo | Fix |
|---|---|
| peebee1 | Add the profile README on the peebee1 account |
| shopping-concierge | Fix the wall-clock test that broke on its own |
| angelone-smartapi | Make the test suite runnable from a clean checkout |
| agentic-commerce-protocol-poc | Add CI to the ACP proof of concept |
| shopping-concierge | Add CI to shopping-concierge |
| agent-bazaar | Add CI and a frozen mock benchmark to agent-bazaar |
| all | Add repository topics and sharper descriptions |
| angelone-smartapi | Rewrite the Angel One README around risk, not returns |
| angelone-smartapi | Decide what leaves the machine before the mandate branch is public |
| angelone-smartapi | Stop the SDK from writing bearer tokens into logs |

# Hardening queue

Fixes to the repos people already see. Priority is impact x confidence / effort, per
`RUBRIC.md` section 5. Machine readable source is `state/hardening.json`.

| Priority | Repo | Fix | Defect |
|---|---|---|---|
| 15.0 | angelone-smartapi | Stop the SDK from writing bearer tokens into logs | The Angel One smartConnect SDK logs the failing request, including the Authorization header, into logs/*/app.log on HTTP errors. 7 lines across 3 days contain full JWTs. Local only and gitignored, and the tokens expire at IST midnight, but the behavior repeats. |
| 15.0 | all | Add repository topics and sharper descriptions | No repo topics on any public repo, and descriptions read like internal notes rather than a thesis. |
| 10.0 | angelone-smartapi | Decide what leaves the machine before the mandate branch is public | PREMISE CORRECTED 2026-10-27: feat/60-day-mandate is already pushed to origin, so mandate/state.json and its registered_ip are public now, not at some future push. The file still carries the home IP and the live book. Remaining work: purge registered_ip from the tracked state, history included, and decide whether the branch becomes main. |
| 8.0 | agent-bazaar | Add CI and a frozen mock benchmark to agent-bazaar | 43 tests pass, no workflow. The README quotes LLM negotiation results that nobody can reproduce without the same model. |
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
| angelone-smartapi | Rewrite the Angel One README around risk, not returns |

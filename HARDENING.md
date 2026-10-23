# Hardening queue

Fixes to the repos people already see. Priority is impact x confidence / effort, per
`RUBRIC.md` section 5. Machine readable source is `state/hardening.json`.

| Priority | Repo | Fix | Defect |
|---|---|---|---|
| 16.0 | angelone-smartapi | Rewrite the Angel One README around risk, not returns | The README leads with the mandate size. It does not state what the agent proves, what the rails forbid, or what happened in the 60 days. |
| 15.0 | all | Add repository topics and sharper descriptions | No repo topics on any public repo, and descriptions read like internal notes rather than a thesis. |
| 12.5 | angelone-smartapi | Make the test suite runnable from a clean checkout | pytest is not in requirements.txt. uv run pytest fails with no such executable, so the 5 test files have never run in CI. |
| 12.5 | peebee1 | Add the profile README on the peebee1 account | The account has no profile README. A visitor lands on a bare repo list with 0 followers and no thesis. |
| 8.0 | agent-bazaar | Add CI and a frozen mock benchmark to agent-bazaar | 43 tests pass, no workflow. The README quotes LLM negotiation results that nobody can reproduce without the same model. |
| 6.0 | agentic-commerce-protocol-poc | Make the ACP benchmark a committed results file | bench/results.md is prose. There is no machine-readable result and no threshold that fails a regression. |
| 5.0 | shopping-concierge | Refresh the stale catalog and eval numbers | Committed data is 79 days old and the eval report quotes stale freshness labels. |

## Done

| Repo | Fix |
|---|---|
| shopping-concierge | Fix the wall-clock test that broke on its own |
| agentic-commerce-protocol-poc | Add CI to the ACP proof of concept |
| shopping-concierge | Add CI to shopping-concierge |

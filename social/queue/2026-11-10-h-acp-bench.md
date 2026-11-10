A benchmark that prints a table is a screenshot with extra steps.

The load benchmark in my agentic checkout PoC printed 79 sessions a second into a markdown file. Nothing in CI read it. No threshold, no machine readable record, so the day it dropped to 12 nobody would have known until a human compared two hand written tables.

Now one JSON record is the only source of truth. `bench/check.py` compares it with committed budgets and names every violation: errors, failed checks, incomplete runs, throughput below floor, p99 over budget. `bench/render.py` generates the markdown from the same record and fails when the committed file drifts, so a hand edited number cannot survive CI.

I checked the gate bites before trusting it. Mutating one run to 45 sessions a second, 3 errors, one session short and a 1400 ms p99 returns four violations and exit 1. A threshold nobody has watched fail is decoration.

Where it stands on a 10 core Mac, local loopback: 100.0 full checkout sessions a second at 32 workers, p99 409 ms, 300 of 300 sessions completed with zero errors. Create only, 675.9 a second at 64 workers.

That is up from the old table's 79.4 and 229, and I did not optimize anything. It is a re-measure on a warmer machine with the same code, which is the other argument for making the number reproducible instead of memorable.

Limit, said out loud: this measures one in-memory uvicorn process per service over loopback, not production. The latency budgets describe a laptop, so CI applies only the count checks on a shared runner: zero errors, every session finished. Timing on a rented CPU says more about the runner than the protocol.

Code and the two committed runs:
https://github.com/peebee1/agentic-commerce-protocol-poc

A trading agent I wrote filled zero orders. The reason is the most useful thing in the repo.

The setup: a model writes trade intents, deterministic code checks seven rails against a written
mandate, and only then does an order reach the broker. The model never touches the order API.

In the first live run it wrote 8 intents. Zero filled.

1 was stopped by a rail I wrote: the order would have been 26% of NAV against a 25% cap.
4 were refused by the exchange with AG7002, "not a registered IP". The order never existed. No
price was tested, no thesis was tested, and the agent logged it as a failed trade rather than
what it was, a configuration fault.

So the rail I had written down did its job, and the rule I had never written down stopped
80% of the attempts.

That is the gap between an agent that refuses and an agent that fails. A refusal is visible in
state. A precondition you forgot looks exactly like a bad call.

I rewrote the README around this: every rule the agent cannot break, the function that
enforces it, the test that pins it, and a committed command that prints the run record so
nobody has to take the number on trust.

Limit, stated plainly: 8 intents and 0 fills is not a track record. No P&L, no slippage, no
benchmark. What is proven is the enforcement layer, not the stock picking.

Code: https://github.com/peebee1/angelone-smartapi/tree/feat/60-day-mandate

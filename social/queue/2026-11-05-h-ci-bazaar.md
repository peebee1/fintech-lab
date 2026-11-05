My negotiation repo had 43 tests and no CI, and a benchmark table nobody could reproduce without my API key.

Both are worse than they look. A test suite that has never run on a push is a claim, not a guarantee. And a benchmark that needs the same model, the same provider and the same key is a recording. You cannot check it, so you take my word for it.

The obvious fix is a mock model so the benchmark is free and deterministic. I tried it, and the table printed four identical rows: my mock delegates to the same concession strategy the baseline uses, so llm-llm, llm-strategy, strategy-llm and strategy-strategy all match, and every comparison is 0.0 percentage points. A benchmark where the control never differs from the treatment is not a benchmark. It is a screenshot.

So the deterministic bench measures the other claim, the one that does not need a model: what the protocol and the private guards do when the proposer tries to break its own limits. Five scripted policies, each a named way a language model fails on a negotiation turn. Returns prose instead of the contract. Offers ten times any ceiling. Re-offers against its own last price. Accepts whatever is on the table. Commits to a price its own limit forbids. Replayed on both sides, 12 scenarios each: 108 games, no network, no key, identical bytes on macOS and on Ubuntu.

The first run found something the unit tests missed. My guards checked accept, decline and walk away, but not offer and counter. So a buyer pricing at its budget, above its reservation, and a merchant countering one dollar below its floor, both passed. 34 price commitments outside the proposer's own limit, 20 deals closed outside it.

The fix is four lines, one per side, because an offer is a commitment: if the other side accepts, you pay it. Same limit as an accept. 0 over-limit commitments and 0 breached deals after, 50 tests, and CI now re-runs the bench on every push and fails if the committed numbers change by a byte.

Limit, said out loud: these are scripted adversaries, so this measures whether the discipline layer does what it says, not whether a real model will beat it. The five policies are failure modes I thought of. A model can be wrong in ways I did not script.

Code and the committed table:

https://github.com/peebee1/agent-bazaar

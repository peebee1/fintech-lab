# Weekly roundup, 2026-10-25

I spent the week building payment primitives with an injection harness attached, and today
one of them graduated out of the lab.

Five ships in five cycles:

- Settlement reconciliation, scored against six labelled break classes it injects itself.
  Promoted to [peebee1/settlement-recon](https://github.com/peebee1/settlement-recon).
- A spend policy engine for agent initiated payments. Reserve at decision time, so a burst
  of parallel charges cannot overrun the budget.
- A wall clock test in shopping-concierge that broke itself 30 days after it was written.
  Fixed by injecting time.
- CI on the trading agent, which found seven tests that had never run outside one laptop:
  the client read the macOS Keychain in its constructor, so every authenticated path died
  on Linux.
- The profile README, rewritten as one screen of claims with links.

The number: 21,171 settlement lines reconciled in 36 ms, with 500 injected breaks and both
invariants holding, about 584,000 lines per second on one core.

The limit: the breaks are synthetic and the classes are known in advance. Perfect recall
there means the cascade has no blind spot on those six classes, not that it survives a real
PSP file with reused references and FX.

Everything is in [fintech-lab](https://github.com/peebee1/fintech-lab) with code, tests, and
a result file the CI regenerates on every push.

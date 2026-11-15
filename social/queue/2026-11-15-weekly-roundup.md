Four builds and two hardening days this week, and the same conclusion turned up in four of the builds: the metric everyone optimises is not the one that prices the decision.

An underwriting model is the cleanest example. Three models ranked the same 1,500 loan holdout identically, AUC 0.7402 for all three. Same ordering, same accuracy at a 0.5 cut. They still disagreed by $417,755 of contribution, because one of them reported a mean probability of default of 5.99% where 13.73% of the book actually defaulted. Two fitted parameters on 1,500 settled loans cut Brier by 8.8% and turned a $150,633 loss into $270,379. A ranking metric cannot see the number that prices the loan.

The same shape showed up in disputes. A status tracker recovers 21.3% of the defensible value in a 2,000 dispute book. It is not a lazy team, it is a three week habit: 563 of its 804 forfeits are fraud claims, because a 25 day sweep is longer than a 20 day response window. Model the clocks, add the two zero evidence checks, refuse unwinnable evidence sets and sort the queue by value per minute, and the same 40 analyst minutes a day recover 94.0%. 55.2% of the recoverable money needs no evidence at all, and the tracker captured 6.4% of it.

Reconciliation said it with shares. A book checked against the broker snapshot alone sat 844 shares and 27.2 lakh rupees away from the exchange tape on a 1,200 order session and reported zero breaks, because it had nothing to compare against. Naming every break from the tape closed the gap to zero, and ranking the 286 breaks by rupee impact put 87% of the exposure inside 60 review tickets against 26% in arrival order.

Closing the books said it with months. An append only, hash chained ledger: 0 of 4 closed periods changed after the close, 4 of 4 closes still reproduced. The stored balance baseline moved 3 of 4 months, INR 22,700 of account movement, and kept 1 of 4 closes reproducible. Then one person edited a single January entry out of band and the chain broke at entry 1, which is the useful part: it did not just say something changed, it said which month.

Two of the week's days were not new builds. The ACP load benchmark became a gate instead of a table, so a number that gets worse now fails CI with four named violations. The shopping catalog stopped taking its data date from file mtime, because git rewrites mtime on checkout and a fresh clone of a 100 day old catalog was reporting itself as fresh, 0 minutes old.

Dispute clocks earned its own repo, with the numbers still reproduced by CI rather than pasted into a README: https://github.com/peebee1/dispute-clocks

Limit, said out loud: the dispute windows are illustrative, shaped like public network rules rather than a reproduction of a current rulebook, and a complete evidence set wins with probability one in the model where real representment wins about half the time. The model prices the clock and the queue, not adjudication.

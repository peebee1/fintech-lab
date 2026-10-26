The same billing code keeps 99.5% of a card book, 60.7% of a SEPA book, and 46.9% of a UPI book.

Not because the code changed. Because the rails disagree about what a debit is.

Cards: a fixed recurring charge needs no pre-debit notice. Send it on the due date and you are done.

SEPA: fourteen days of notice before every collection, and the payer keeps an unconditional refund right for eight weeks. Bill on the due date and you have technically collected, and legally borrowed.

UPI: twenty four hours of notice, and a 15,000 rupee ceiling per debit before the payer has to authenticate again. Skip the ceiling check and the rail simply refuses you.

So I built one book, three rails, three schedulers, and a ledger that refuses to pretend.

The naive ladder keeps 99.48% of the card book, 60.74% of the SEPA book, and 46.87% of the UPI book. On SEPA and UPI every collected invoice still carries a live refund right, so the floor on those two rails is zero. Across the three rails, 33.16% is what the book is worth once every payer who can ask for the money back does.

The rail aware planner gets to 97.09% mean kept with zero exposure, for 4.8 days of float on SEPA.

The result I did not expect: the revocation lag everyone worries about is the cheap part. Handling revocation removes 4 bps of reversal and costs 2 bps of collection. The notice window is where the money is.

33 tests, one command, deterministic seed, and the reconciliation has to pass or the eval refuses to write a number.

The limit worth saying out loud: the book is synthetic, and I did not model the UPI category exemptions, where insurance, mutual fund, and credit card bill mandates can run to 100,000 rupees without authentication. That makes the UPI authentication loss here worse than the real rule allows.

Code and the eval output:
https://github.com/peebee1/fintech-lab/tree/main/artifacts/2026-10-26-mandate-sim

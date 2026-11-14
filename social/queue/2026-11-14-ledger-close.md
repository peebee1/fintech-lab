Most ledgers can tell you what you closed. Very few can prove it.

I built an append only ledger where every entry carries the hash of the entry before it, balances are derived on every read rather than stored, a correction can only be a reversal, and a write into a closed period is refused by name.

Then I ran the same 281 transaction book through it and through the shape most ledgers start as: stored balances, editable postings, month end as a snapshot of a running total.

Five ordinary things happened next. A bank fee found after March closed. An operator reclassifying January fee revenue. A client retrying a payment with the same idempotency key. A posting whose lines did not sum to zero. Someone editing an entry in the file on disk.

Closed period totals moved in 3 of 4 months on the baseline, INR 22,700 of account movement, and only 1 of the 4 closes still reproduced. The sealed ledger: 0 of 4 months moved, 4 writes refused, 4 of 4 closes still reproduced, and the retry appended nothing.

The one that matters is the edit. Changing a single January entry broke the chain at entry 1, and the January close stopped reproducing while the other three still verified. That is the difference between noticing that something changed and being able to say which month it touched.

Limit, said out loud: this detects tampering, it does not prevent it. Whoever can write the file can rewrite every downstream hash and every close digest with it. Making that expensive needs an external anchor, WORM storage or a public timestamp of the daily head, and that is the first item on the next list.

Code and the committed numbers:
https://github.com/peebee1/fintech-lab/tree/main/artifacts/2026-11-14-ledger-close

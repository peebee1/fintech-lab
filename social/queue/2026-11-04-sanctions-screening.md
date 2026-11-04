A sanctions screen caught 28 of 36 listed customers and delivered 11 of them to an analyst,
and the reason is that 130 people in the book score identically.

I have been building screening benchmarks for a while and the interesting thing is never the
similarity threshold. It is the queue. Every alert in it is a real customer whose account stays
frozen until a human clears them, so the only number a compliance team can act on is: given the
analysts I have, how many listed people do I find.

I built a synthetic book of 2,400 customers against a synthetic list of 26 entries, with 36
customers who really are a designated person and 110 namesakes with the same name, a different
date of birth and a different country. Then I scored four designs at one fixed review budget of
48 cases, which is 2 percent of the book and one analyst day.

A plain Jaro-Winkler name match alerted on 28 of the 36 listed customers. It delivered 11. The
other 17 were in its own output, behind 130 customers tied at a top score of 1.000, and the tie
break was a customer id. Its queue was 553 customers, 11.5 analyst days.

The same 48 reviews with dates of birth, countries and identity numbers as evidence instead of
as decorations: 33 of 36, 11 namesakes reviewed, 196 in the queue, 4.1 days. Precision 0.688,
which is the ceiling at that budget, because three customers only exist on the book under a
kunya and no name matcher can reach a name that is not in the data.

One more result I did not expect and now think about: dropping every alert whose country
disagrees with the list lifts the same book to 21 of 36 and loses all six customers who
relocated. That is the cheapest discriminator on the market and it fails on the class of person
who most needs catching.

Limit, said out loud: I wrote the generator, so the truth classes are shaped by my own rules.
This measures whether the logic does what it says, not what your book will do. The threshold is
one operating point, not a calibrated one, and the first run of the bench scored 28 of 36 only
because the true matches happened to have the lowest customer ids: I had to shuffle the book
before the number meant anything.

Code, tests and the committed results:

https://github.com/peebee1/fintech-lab/tree/main/artifacts/2026-11-04-sanctions-screening

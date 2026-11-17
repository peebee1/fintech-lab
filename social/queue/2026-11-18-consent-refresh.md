A consent is a lease with an expiry date, and every renewal is a chance for the customer to leave.

Open banking subscriptions do not charge a card on file. They charge an authorisation that expires, usually in 90 days, so every A2A merchant runs a renewal programme. Most of them pick a cadence, because a cadence is easy to schedule. Thirty days, ninety days, whatever the rail allows.

I ran eight of those policies over the same synthetic book: 1,200 payers, 13,834 scheduled debits, USD 525,635.54 billed, 360 days.

A 30 day refresh calendar captured 51.0% of the revenue that was available. Never refreshing at all captured 28.3%. The calendar looked like a programme and was worth 1.8x doing nothing, because it sent 7,669 prompts and 787 customers walked away at one.

Asking only when a debit would land after expiry, and asking two to three days before it, captured 89.7% with 2.54 times fewer prompts. Same merchant, same book, USD 182,978.93 more revenue than the calendar.

The counterintuitive part: a 7 day lead refused 66 payments against 350 for the 3 day lead, and still captured USD 23,199.41 less. A prompt a week out is not part of the payment flow any more, and 11.6% of the customers it asks leave. The best policy is not the one with the fewest refusals.

Limit, said out loud: the mechanism rests on two multipliers I set, one for a prompt near a debit and one for a prompt after a failure. Remove the first and the winner changes: a 7 day lead takes over. That multiplier is the next thing to measure, not another policy to add.

Code and the committed numbers:
https://github.com/peebee1/fintech-lab/tree/main/artifacts/2026-11-18-consent-refresh

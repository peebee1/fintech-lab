# Weekly roundup, 2026-11-01

A subscription that bills by card, by SEPA direct debit, and by UPI autopay is three
different products wearing one checkout button. This week was mostly about that gap.

Six ships, then one of them graduated:

- A mandate simulator that runs one scheduler policy across all three rails. Promoted to
  [peebee1/mandate-rails](https://github.com/peebee1/mandate-rails).
- FX safe payout splitting. Naive rounding leaves one in five payouts unbalanced, whatever
  the currency's minor unit is.
- Agent to agent credit with netting. A cap on gross outflow carried 21.26% of the value; a
  cap on net debit carried 97.84%, at the same worst case loss.
- The trading agent README, rewritten around what the rails forbid instead of what the
  mandate holds.
- Bearer tokens and the API key, removed from the SDK's own log handler, then purged from
  the files already on disk: 39 credential values across 32 lines, now 0.
- Repository topics and descriptions, moved from hand edits into declared state with a
  drift check. 5 of 7 public repos had none; now 7 of 7, and it is 8 as of today.

The number: a due date scheduler keeps 99.48% of a card book, 60.74% of a SEPA book, and
46.87% of a UPI book. Counting the refund rights it leaves open, its floor is 33.16%. The
same engine, with the notice window and the authentication cap handled, gets that floor to
97.09%.

The limit: the book is synthetic, 2000 subscribers from one seed, and UPI category
exemptions are not modelled, which overstates the authentication losses. The other honest
finding is that handling revocation is close to a wash, 2 bps of collection given up for
4 bps of reversal avoided, so the notice window is the expensive part and revocation is not.

All of it is in [fintech-lab](https://github.com/peebee1/fintech-lab) with code, tests, and
a results file CI regenerates on every push.

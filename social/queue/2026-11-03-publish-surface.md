My own public repo was publishing my home IP address, and nothing in it needed to.

The filed ticket was about one field: a tracked state file carried `registered_ip`. I ran the
scan before fixing it, which is the only reason I found the rest. Eleven host identifiers across
seven tracked files. The state file, which also held the cash, positions, and trade history of a
live trading account. A prose table in the plan doc. Four archived trade intents where the
broker's own refusal message had copied two more addresses into committed evidence, because the
broker said "x.x.x.x is not a registered IP" and I pasted the whole string. And three test
fixtures, built from a real log line, sitting in a test file nobody had a reason to re-read.

Nothing in the code read that field. I was publishing a home address and a live book for zero
benefit, in a repo whose README argues that guardrails are the product.

The fix is small. The state file is untracked and gitignored, and the agent seeds a blank paper
state on a fresh checkout, so the repo still runs from scratch. Archived intents mask the last
octet the same way my log redactor already did, so the broker message stays readable. Fixtures
moved to the documentation ranges that exist for exactly this. Then I wrote the part that
matters: `scripts/check_public_surface.py` reads the files git actually tracks and exits 1 on any
IPv4 or MAC that is not loopback, a documentation address, or masked, and CI runs it on every
push. 11 identifiers in 7 of 42 tracked files before, 0 in 43 after.

Two things I will say plainly. The first push of my own guard went red, because the guard's test
fixtures were literal addresses and only passed while the file was still untracked. That is the
most on-brand failure I have had this month. The second is worse and cannot be fixed: three of
23 commits in the public history still carry an address, and removing them means rewriting
published history with a force push. I do not do that, so the exposure is written down in the
repo instead of quietly deleted.

The limit: an address check is not a data classification policy. It catches one literal class in
one repo. Tokens, customer records, and anything with a name attached need the same treatment
before they reach a public branch, and this does not do that.

Code, tests, and what is deliberately public:

https://github.com/peebee1/angelone-smartapi/blob/feat/60-day-mandate/docs/publish-scope.md

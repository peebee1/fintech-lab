An idempotency key is a header. Idempotency is what happens when two retries arrive at
the same time, and almost nobody tests that.

I built a conformance suite for the charge endpoint: 11 checks that drive one API through
the replays that cost money. Two requests overlapping before either commits. A burst of
five. A process that dies after the processor accepted the charge and before the response
was stored. A processor 503 that gets cached as the final answer. A key that is not scoped
to the account.

Then I ran it against five implementations of the same endpoint. The one I expected to
fail did. The interesting part is the one I did not expect: the implementation that reads
the key store, compares the body, and returns the stored response on a match. That is the
version that passes code review, and it passes the sequential replay test. It scored 6 of
11 and created 7 charges that should not exist, 87.50 EUR at a 12.50 test amount.

The version that reserves the key before the charge, scopes it to the account, releases
it when the processor errors, and reads the ledger when it wakes up after a crash scored
11 of 11.

The design decision underneath is small and it is the whole thing: write the idempotency
key onto the charge row itself. Then "did this key already charge" is a read of the
ledger, not of a cache that might have missed the write, and a crash between the charge
and the stored response stops being a mystery. In the suite, a stale reservation is
resolved by looking for the charge before re-running, which is why the crash before the
charge and the crash after it need different answers.

Limit, said out loud: the concurrency is modelled, not spawned. One process, deliberate
interleaving, a JSON store instead of a database. It proves the design property and it
does not prove anything about your thread pool, your HTTP server, or your transaction
boundaries. Five implementations is also a small population: the modes were written to
isolate one defect each, which makes attribution clean and says nothing about how defects
are distributed in real APIs.

Cost of the fix, measured: 17.21 microseconds per request over a no-check baseline, 20,000
requests in process.

Code, tests and the committed results:

https://github.com/peebee1/fintech-lab/tree/main/artifacts/2026-11-02-idempotency-conformance

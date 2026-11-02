# Eleven replays your payment API will fail

An idempotency key is a header. Idempotency is a property of the pipeline under
replay, overlap, and process death. This is a conformance suite that tests the
property, run against five implementations of the same charge endpoint.

The claim, measured: an implementation that stores the response after the charge
succeeds passes 6 of 11 checks and creates 7 charges that should not exist, worth
87.50 EUR at the test amount. An implementation that reserves the key before the
charge, scopes it to an account, releases it on a processor error, and reads the
ledger when it wakes up after a crash passes 11 of 11. Both are implementations a
reviewer would sign off on by reading the code. Only one is idempotent.

## Problem

Every payments team has an idempotency section in its API docs, and almost every
one of them describes the happy case: send the same key, get the same response.
The cases that cost money are the ones the docs skip.

- Two retries arrive inside the same millisecond, both see no stored record, both
  charge the card.
- The process dies after the processor accepted the charge and before the response
  was stored. The client retries. Money moved once and the system has no record of
  which charge it was.
- The processor returns a 503, the implementation stores that as the answer, and
  every retry for that key now returns a failure for a charge that never happened.
- The key is stored in a table keyed by the header alone, so account B retrying a
  payment gets account A's charge id back.

None of these show up in a test that calls the endpoint twice in a row and compares
two 201s. All four are in the suite below, and each one is pinned to a named
violation code so a failure says which defect it found, not just that something
failed.

## Why it matters

Double charging is the defect that turns an integration into a support queue, and
it is invisible in code review because the code is correct in the order it is
written. The bug is in the interleaving.

- **The window is between the charge and the write, and it is unavoidable.** Any
  design that charges first and records second has a window where the effect exists
  and the record does not. You cannot close the window by being careful. You can
  only move the write to be the same write as the charge.
- **Retries are not an edge case, they are the normal path.** Mobile clients retry
  on timeout, gateways retry on 5xx, and a queue retries on a worker restart. The
  idempotency key exists precisely because the network will duplicate requests, so
  a design that only works on the first one is a design that works when the network
  is fine.
- **The cost of the fix is measurable and small.** Reserving the key before the
  charge costs 17.21 microseconds per request on this machine against a no-check
  baseline, which is three orders of magnitude below the processor call it is
  protecting.
- **The failure is asymmetric.** A missing charge loses a sale. A duplicate charge
  costs the money, the refund fee, the support time, and the trust. A conformance
  suite is cheap insurance against the second one.

## Design

Four modules, standard library only, integer minor units, no network, no clock: the
harness passes `now` on every call so a lease or a TTL test never depends on when it
ran.

- `idemconform/ledger.py`: `Entry` and `Ledger`. Every charge row carries the
  idempotency key that created it, so "did this key already charge?" is a read of
  the ledger, not a read of a cache that might have missed. `find(account, key)` is
  the recovery query. A charge of zero or a negative amount is refused at append,
  and `fail_next_append()` injects a processor failure.
- `idemconform/store.py`: `Record` with states `in_flight` and `committed`, a
  `MemoryStore`, and a `JsonFileStore` that persists after every write so a second
  process reads what the first one wrote. `scoped=False` reproduces the global key
  table defect. Records are copied on the way in and out, so a caller holding a
  reference cannot change stored state.
- `idemconform/api.py`: `PaymentAPI` with `admit` (the decision) and `finish` (the
  effect) as separate steps. Splitting them is the whole reason the suite can test
  overlap: two callers can both admit before either finishes. Five modes:
  `naive`, `global_key`, `store_after`, `error_cached`, `reserve`. Fault hooks
  `crash_before_effect` and `crash_after_effect` model a process death at the two
  points that matter.
- `idemconform/suite.py`: 11 checks, each driving one interleaving and recording
  named violation codes, plus `measure_overhead`.

The decision that carries the design: the reservation is a lock, the ledger is the
truth. A key store alone cannot answer "did the charge happen", because the window
between the charge and the store write is exactly where the answer goes missing.
Writing the key onto the charge row makes the effect and the identity of the effect
one write, so recovery is a lookup instead of a guess.

The second decision: a stale `in_flight` record is not automatically safe to
re-run. The implementation looks for the charge first and only re-runs when the
ledger proves no charge exists. That is why `crash_before_effect` and
`crash_after_effect` need different answers, and why they are two checks.

| Decision | Alternative | Why this one |
|---|---|---|
| Key written onto the charge row | Separate key table, written after the charge | The effect and its identity become one write, so a crash cannot separate them |
| Reserve before the effect | Store the response after success | Closes the overlap window; the 2 requests both pass a read in the store after variant |
| Lease with an owner, 30s, injected clock | No lease, trust the store | A second owner gets 409 with `Retry-After` instead of a duplicate charge |
| Stale lease resolved from the ledger | Stale lease means re-run | Re-running a claim whose charge already exists is a double charge |
| Fingerprint covers amount, currency, customer | Fingerprint covers the whole body | Account is the namespace, so it must not be part of payload identity |
| Key scoped to the account | Global key table | One tenant's retry must never return another tenant's charge |
| TTL expiry returns 409 | Expired key means a fresh request | After expiry the stored answer is gone, and re-running silently is a double charge |
| Processor error releases the claim | Cache the error as final | A 503 is not an answer; caching it makes the key permanently broken |
| 400 on a missing key | Treat it as a normal request | A charge with no key cannot be retried safely by anyone |

## Run

From the repository root:

```bash
uv run python tools/gate.py artifacts/2026-11-02-idempotency-conformance
uv run pytest artifacts/2026-11-02-idempotency-conformance
```

To regenerate the committed numbers from the artifact directory:

```bash
cd artifacts/2026-11-02-idempotency-conformance
PYTHONPATH=. uv run --project ../.. python -m idemconform.cli run
PYTHONPATH=. uv run --project ../.. python -m idemconform.cli overhead
```

`run` rewrites `results/conformance.json`, `results/violations.json`,
`results/overhead.json`, and `results/summary.md`. Nothing else is needed: no
service, no key, no database.

## Results

Produced by `python -m idemconform.cli run`. Five implementations, 11 checks, 1250
EUR cents per charge unless the check says otherwise.

```
implementation    passed    excess value  excess charges
--------------------------------------------------------
naive            3/11            137.50              11
global_key      10/11              0.00               0
store_after      6/11             87.50               7
error_cached    10/11              0.00               0
reserve         11/11              0.00               0
```

What each failure is:

- `naive` (no key handling): 8 checks fail, 11 extra charges. Missing key, replay,
  conflict, overlap, burst, crash recovery, lease, expiry.
- `global_key` (correct reservation, key not scoped): 1 check fails, and the failure
  is the bad one: a second account sending the same key receives the first
  account's charge id and a success. No extra charge, so a ledger reconciliation
  would find nothing wrong. The money is attached to the wrong customer.
- `store_after` (the common implementation): 5 checks fail, 7 extra charges, 87.50
  EUR. It handles a sequential replay correctly and fails everywhere the window
  opens: two overlapping requests, a burst of five, crash after the charge, replay
  inside a lease, and replay after the TTL.
- `error_cached` (reservation, but the 503 is stored as the answer): 1 check fails.
  The retry gets the cached 502 forever. Nothing double charges and the key is
  permanently dead, which is the failure that generates the support ticket instead
  of the refund.
- `reserve`: 11 of 11, zero extra charges.

The `store_after` row is the point of the artifact. It is not a strawman: it reads
the store before charging, compares the body, returns the stored response on a
match, and passes the first two checks. A reviewer reading it line by line finds
nothing wrong. It is wrong in the interleaving.

Overhead, from the committed `results/overhead.json`: 20,000 requests in process,
amortised microseconds per request on this machine.

- `naive` 2.98
- `store_after` 14.52
- `reserve` 20.19, so 17.21 us over the no-check baseline

## Limits

- **The concurrency is modelled, not spawned.** `admit` and `finish` are called in a
  deliberate order in one process. That makes overlap deterministic and reviewable,
  and it does not prove anything about a real thread pool, a real HTTP server, or a
  real database transaction. The `JsonFileStore` is not atomic across processes: the
  write is a read, modify, write. A production implementation needs a unique
  constraint on `(account, key)` and the charge insert in the same transaction,
  which is the database doing the thing this artifact simulates.
- **The ledger is the durable store here because I made it one.** In the suite the
  key store and the ledger live in memory and both survive a `reopen`. The JSON
  variant writes both to disk, which is why it can show a cold process recovering,
  but a real system needs its charge table and its key table to commit together or
  the whole argument collapses.
- **Five implementations is a small population.** The modes were written to isolate
  one defect each, which makes attribution clean and says nothing about the
  distribution of defects in real APIs. I have not run this against a live vendor,
  and I would not point it at one without permission and a sandbox key.
- **The checks encode opinions.** That a replayed response must carry
  `Idempotent-Replayed: true`, that an expired key must be a 409 rather than a fresh
  charge, and that a missing key is a 400 are conventions, not laws. Stripe,
  Adyen, and the IETF idempotency draft agree on the shape of these and differ on
  the details; a team could pass the important checks with different status codes.
- **The overhead numbers are one machine, one process, one run.** They are useful as
  a ratio against the no-check baseline, not as an absolute latency budget. A real
  request also makes a processor call that costs milliseconds.
- **Synthetic only.** No card data, no customer data, no vendor endpoint, no
  credentials. Every amount is 1250 minor units unless a check needs something else.

## Next

- Add a sixth implementation that passes all 11 checks using a different mechanism
  (a database unique constraint plus a read of the charge table, no key store at
  all) to show the property does not depend on the reservation record.
- Turn the two JSON stores into one SQLite store so the write is atomic and the
  overlap test runs against a real transaction boundary.
- Add a check for a retried request that arrives with the same key and a different
  currency, which the fingerprint catches today but no check exercises.
- Wrap the suite in a thin HTTP adapter so it can be pointed at a locally run API
  rather than the in-process model. That is the version a buyer would actually use.

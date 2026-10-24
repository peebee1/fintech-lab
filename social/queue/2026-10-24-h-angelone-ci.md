A trading agent I wrote for my own money had a test suite that only my laptop had ever run.

That is the normal state of a personal project, and it is also how a credential bug survives for
two months.

The agent places orders on the Angel One Smart API under a hard mandate: kill switch, per-order
cap of Rs 25,000, exact symbol resolution, dry run before live. All of that is tested. 72 tests,
offline, no network, no clock.

None of it ran anywhere a stranger could see. So this week I put it on GitHub Actions and pointed
it at ubuntu-latest instead of my Mac.

7 of 72 tests failed immediately, all with the same error: FileNotFoundError, module "security".

The client reads the API key from the macOS Keychain inside its constructor. On macOS, a missing
key returns nothing and the code raises a clean NeedsLogin. On a machine with no Keychain, the
subprocess itself does not exist, so every authenticated path died with a traceback instead of the
message it was designed to print.

The fix is small: the secret lookup returns None when the `security` CLI is absent or fails, the
write path raises an error that names the fix, and six new tests pin both. Green on both runners.

The limit worth saying out loud: these tests are offline and stubbed. Green CI proves the rails and
the session logic, not that an order ever reached the exchange intact. That claim needs a recorded
paper-trading run, and I do not have one in the repo yet.

Code and CI:
https://github.com/peebee1/angelone-smartapi

#payments #agenticcommerce

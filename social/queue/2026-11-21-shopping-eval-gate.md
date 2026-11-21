# LinkedIn draft, 2026-11-21, shopping-eval-gate

The number in my own README was wrong, CI was green, and nothing in the repo could have caught it.

A benchmark that no job re-runs is a byline, not a measurement. My shopping agent repo quoted 12 of 13 queries passing with 81 percent gold recall. I ran the committed command before touching anything: 14 queries, 13 pass, 82.5 percent. The query set had grown by one, the README had not, and the evaluation script returned exit code 0 on every outcome, including a total collapse. Two independent ways for a published number to rot, and I had both.

The fix is dull on purpose. The keyless run now writes a committed record: model, catalog, data date, the aggregate, and per query the pass flag, the ranked ids, the gold recall and the extracted constraints. CI replays the run and diffs against that record, failing on any field that moved. Two floors sit on top: 85 percent pass rate, 75 percent gold recall. Wall clock fields are excluded, because a gate that fails on a slow runner is measuring the runner.

I checked that it bites instead of assuming it. Changing one ranked id in the record makes the build fail and names the field: results[7], usb condenser microphone, ranked ids. Setting the pass floor to 0.99 fails and prints 0.929 against it. Both exit 1.

Then the gate told me something I had been hiding inside the average. Two of the 13 passes returned an empty shortlist. Their budget and category rules are satisfied by returning nothing, and keyword recall is scored on the picks that exist, so an empty list is not penalised. The honest empty answer is a feature, but it is a weaker pass than a populated one, and 93 percent reads better than it should. That limit is now written into the README and printed on every gate run.

The limit of the post: only the keyless column is gated. The real model column costs money and needs a key, so it stays a dated record, not a measurement. The synthetic catalog is the other input, and the pass rate is only as meaningful as its expected constraints.

Code and the record: https://github.com/peebee1/shopping-concierge

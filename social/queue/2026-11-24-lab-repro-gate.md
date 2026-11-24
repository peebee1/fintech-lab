# LinkedIn draft, 2026-11-24, lab-repro-gate

My gate checked that a results folder had a file in it. It never checked that the file still came from the code.

I publish a fintech artifact a day, each with a README that quotes numbers, and a repo line saying every figure comes from a committed command. That line was true when written and unguarded ever after. The gate passed if `results/` held any file, so a hand-edited number, a stale file left by a refactor, or a result no command writes would all have shipped green.

I proved it the boring way. I changed one seed in one committed summary file, from 20261123 to 20261124, and every gate the lab runs stayed green.

The fix is a tool that deletes the committed outputs in a scratch copy of an artifact, re-runs the command the README documents, and diffs what came back. Three classes, because one size was not honest. Byte for byte for numbers the README quotes. Structure only for wall clock timings, where the keys and their types must hold and the values are printed as drift instead of failing, since a shared CI runner is not the machine that recorded them. Declared volatile for the one rendered table with a milliseconds column, marked ungated out loud rather than pretending to pass.

The first run on 18 artifacts: 18 reproduce, 41 files match byte for byte, 2 match by structure with 7 timing values drifting, 1 declared volatile. It also found two result files that no committed command writes. One was a console log I had captured by hand, now deleted. The other was a benchmark markdown that came from a second subcommand my manifest had not listed.

Now the same one-digit edit fails the gate with the filename and the reason, and an artifact with no manifest entry fails outright, so the next thing I build has to say how its numbers are re-derived before it can ship.

The limit: this proves a committed number comes from a committed command on a clean machine. It says nothing about whether the claim is the right claim. A reproducible wrong measurement is still wrong, and structural checks on a timing file do not catch a model that got worse.

Code: https://github.com/peebee1/fintech-lab

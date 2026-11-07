My trading agent's default branch had 2 commits and none of the work.

main held a day-0 skeleton and a license. The 23 commits that built the mandate rails, the intent pipeline, the refusal log and the CI workflow lived on a feature branch. Anyone who opened the repo got a smaller thing than the README described, and every clone started in the wrong place. Merge day: main went from 2 commits to 26, and the suite on it runs 113 tests, 0 failures.

I merged instead of squashing. A squash would have produced one tidy commit and deleted the part worth reading: four broker refusals (AG7002), one position cap rejection at 26 percent of NAV against a 25 percent limit, and the two hardening commits that came out of those failures. The record is the argument. The merge keeps it and keeps the license commit that only existed on main.

The checks that had to pass before the push were the ones the branch already had: 113 tests, a scanner that reads all 47 tracked files for host addresses (0 found), and a run record that still tallies 8 intents and 0 fills.

Limit, said out loud: three commits in the merged history still carry an address in their diffs. I could remove them and force push, and I decided not to, so the residual is written into docs/publish-scope.md instead of being cleaned up quietly. The repo is also private, so this post is about the shape of the fix, not a link you can open.

Code, if you have access:
https://github.com/peebee1/angelone-smartapi/commit/80176f0

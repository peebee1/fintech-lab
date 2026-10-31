A repo nobody can find does not count as building in the open.

I audited my own account this morning. Seven public repos, and five of them had zero
topics. Topics are how a stranger who searches "agentic commerce" or "settlement
reconciliation" reaches the work at all. Two of my repos had them, because on two
occasions I remembered to add them. Remembering is not a system, so the state drifted
exactly the way you would expect.

The count that mattered: 13 topics across 7 repos before, 39 after, and 7 of 7 repos now
carrying at least three. Four descriptions had also grown into feature piles, listing six
components where one sentence of thesis would have done.

So I stopped typing them into a web form. state/repo_meta.json now holds the desired
description and topic list for every public repo. tools/repo_meta.py validates it offline,
--live compares it against the GitHub API and exits 1 on any drift, --apply writes it. Topics
compare as sets because order is not meaning, and a repo that cannot be read counts as
drift, because a rename or a delete is exactly the failure a metadata check exists to catch.

The limit, said out loud: this makes work findable, it does not make it good. A topic will
not save a repo with no measured result, and it does not touch the substance of anything I
have built. Private repos are out of scope on purpose. The defect was discovery by a
stranger, and a private repo is not discovered.

Code, tests and the committed state:

https://github.com/peebee1/fintech-lab/blob/main/tools/repo_meta.py

"""Chains and their reorg process.

The reorg process is a stated synthetic model, not a claim about any live chain.
Each chain gets a reorg rate per day, a depth distribution, and a share of events
that fork far enough back to invalidate blocks that already looked settled. Two
classes, because they behave differently in the policy comparison:

- routine reorgs: shallow, one or two blocks for most events, with a geometric tail
- incidents: a deeper fork, at a rate low enough that a one week window holds a
  handful. This is the class a fixed confirmation count is supposed to protect you
  from, and the class whose depth a team has to guess.
"""

from __future__ import annotations

from dataclasses import dataclass
from random import Random

MAX_DEPTH = 96


@dataclass(frozen=True)
class Chain:
    name: str
    block_time_s: int
    reorgs_per_day: float
    shallow_share: float
    deep_q: float
    incident_share: float
    incident_min: int
    incident_max: int
    drop_prob: float

    @property
    def blocks_per_day(self) -> int:
        return 86_400 // self.block_time_s


CHAINS: dict[str, Chain] = {
    # A fast L2: 2 second blocks, frequent shallow reorgs, occasional deep one.
    "base": Chain("base", 2, 150.0, 0.80, 0.72, 0.04, 20, 48, 0.55),
    # A mid paced chain: same block time, fewer reorgs.
    "polygon": Chain("polygon", 2, 75.0, 0.85, 0.70, 0.03, 20, 48, 0.55),
    # An L1: 12 second blocks, rare reorgs, and when one happens it is shallow.
    "ethereum": Chain("ethereum", 12, 4.0, 0.90, 0.66, 0.01, 16, 40, 0.60),
}


@dataclass(frozen=True)
class Reorg:
    """Blocks fork_height .. fork_height + depth - 1 are replaced."""

    chain: str
    fork_height: int
    depth: int

    @property
    def last_invalidated(self) -> int:
        return self.fork_height + self.depth - 1


def draw_depth(chain: Chain, rng: Random, incident_scale: float = 1.0) -> int:
    """Incident, or shallow with a geometric tail."""
    if rng.random() < chain.incident_share:
        depth = rng.randint(chain.incident_min, chain.incident_max)
        return min(MAX_DEPTH, max(1, int(round(depth * incident_scale))))
    if rng.random() < chain.shallow_share:
        return rng.choice((1, 2))
    depth = 1
    while depth < MAX_DEPTH and rng.random() < chain.deep_q:
        depth += 1
    return depth


def generate_reorgs(
    chain: Chain, days: int, rng: Random, incident_scale: float = 1.0
) -> list[Reorg]:
    """Reorgs placed at distinct fork heights, sorted, over the window."""
    total_blocks = chain.blocks_per_day * days
    expected = chain.reorgs_per_day * days
    count = max(1, int(round(expected)))
    count = min(count, total_blocks // 2)
    forks = sorted(rng.sample(range(2, total_blocks), count))
    return [
        Reorg(chain.name, fork, draw_depth(chain, rng, incident_scale))
        for fork in forks
    ]


def reorgs_by_chain(
    days: int, rng: Random, incident_scale: float = 1.0
) -> dict[str, list[Reorg]]:
    return {
        name: generate_reorgs(chain, days, rng, incident_scale)
        for name, chain in CHAINS.items()
    }


def invalidating(reorgs: list[Reorg], height: int) -> Reorg | None:
    """The reorg that reaches back furthest over this block, if any.

    A block at `height` is invalidated by a reorg that forks at or below it and
    whose new branch is at least as long. When several reach it, the one that
    invalidated it from furthest back wins, because that one takes the longest to
    become visible.
    """
    best = None
    best_gap = -1
    for reorg in reorgs:
        if reorg.fork_height > height:
            continue
        if reorg.last_invalidated < height:
            continue
        gap = reorg.depth - (height - reorg.fork_height)
        if gap > best_gap:
            best_gap = gap
            best = reorg
    return best

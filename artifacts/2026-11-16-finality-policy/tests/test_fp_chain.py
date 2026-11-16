"""The reorg model: sorted forks, bounded depths, deterministic, and one winner per block."""

from random import Random

import pytest

from finality.chain import (
    CHAINS,
    MAX_DEPTH,
    Reorg,
    draw_depth,
    generate_reorgs,
    invalidating,
    reorgs_by_chain,
)


def test_generated_reorgs_are_sorted_and_inside_the_window():
    chain = CHAINS["base"]
    reorgs = generate_reorgs(chain, days=7, rng=Random(5))
    forks = [r.fork_height for r in reorgs]
    assert forks == sorted(forks)
    assert len(set(forks)) == len(forks)
    assert forks[0] >= 2
    assert forks[-1] < chain.blocks_per_day * 7


def test_depths_are_positive_and_bounded():
    for name, chain in CHAINS.items():
        reorgs = generate_reorgs(chain, days=7, rng=Random(11))
        assert reorgs
        for reorg in reorgs:
            assert 1 <= reorg.depth <= MAX_DEPTH, name


def test_generation_is_deterministic():
    first = reorgs_by_chain(7, Random(42))
    second = reorgs_by_chain(7, Random(42))
    assert first == second


def test_a_different_seed_gives_a_different_history():
    assert reorgs_by_chain(7, Random(42)) != reorgs_by_chain(7, Random(43))


def test_incident_scale_deepens_only_the_tail():
    chain = CHAINS["base"]
    normal = generate_reorgs(chain, days=7, rng=Random(9))
    deeper = generate_reorgs(chain, days=7, rng=Random(9), incident_scale=1.5)
    assert [r.fork_height for r in normal] == [r.fork_height for r in deeper]
    assert max(r.depth for r in deeper) > max(r.depth for r in normal)
    assert sum(r.depth for r in deeper) > sum(r.depth for r in normal)


def test_shallow_reorgs_are_the_majority():
    chain = CHAINS["base"]
    reorgs = generate_reorgs(chain, days=28, rng=Random(3))
    shallow = sum(1 for r in reorgs if r.depth <= 2)
    assert shallow / len(reorgs) > 0.6


def test_invalidating_finds_a_reorg_that_reaches_the_block():
    reorg = Reorg("base", 100, 3)          # covers 100, 101, 102
    assert invalidating([reorg], 100) is reorg
    assert invalidating([reorg], 102) is reorg
    assert invalidating([reorg], 99) is None
    assert invalidating([reorg], 103) is None


def test_invalidating_prefers_the_reorg_that_reaches_back_furthest():
    shallow = Reorg("base", 99, 2)         # gap 1 at height 100
    deep = Reorg("base", 95, 20)           # gap 15 at height 100
    assert invalidating([shallow, deep], 100) is deep
    assert invalidating([deep, shallow], 100) is deep


def test_no_reorgs_means_no_hit():
    assert invalidating([], 500) is None


def test_depth_draw_stays_in_range_at_any_scale():
    chain = CHAINS["polygon"]
    rng = Random(7)
    for _ in range(500):
        depth = draw_depth(chain, rng, incident_scale=3.0)
        assert 1 <= depth <= MAX_DEPTH


def test_block_times_match_the_declared_chains():
    assert CHAINS["base"].block_time_s == 2
    assert CHAINS["ethereum"].block_time_s == 12
    assert CHAINS["ethereum"].blocks_per_day == 7200

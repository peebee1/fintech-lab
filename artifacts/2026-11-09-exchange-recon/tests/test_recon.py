from orderrecon import metrics, recon


def test_clean_session_raises_no_breaks(clean):
    _, _, stream_breaks = recon.stream_positions(clean)
    _, _, tape_breaks = recon.tape_three_way(clean)
    _, broker_breaks = recon.broker_vs_app(clean)
    assert stream_breaks == []
    assert tape_breaks == []
    assert broker_breaks == []


def test_three_way_recovers_every_injected_break(dirty):
    _, _, breaks = recon.tape_three_way(dirty)
    scored = metrics.score(dirty.truth, breaks)
    assert scored["precision"] == 1.0
    assert scored["recall"] == 1.0
    for row in scored["per_class"]:
        assert row["recall"] == 1.0, row["class"]


def test_broker_only_reconciles_nothing(dirty):
    truth = recon.tape_positions(dirty)
    broker = recon.broker_positions(dirty)
    assert broker != truth


def test_broker_vs_app_is_guessing(dirty):
    _, breaks = recon.broker_vs_app(dirty)
    scored = metrics.score(dirty.truth, breaks)
    assert scored["precision"] < 1.0
    assert scored["recall"] < 1.0


def test_stream_replay_misses_most_classes(dirty):
    _, _, breaks = recon.stream_positions(dirty)
    scored = metrics.score(dirty.truth, breaks)
    assert scored["recall"] < 0.5
    assert {row["class"] for row in scored["per_class"] if row["correct"]} == {"duplicate_fill"}


def test_explained_deltas_close_the_book(dirty):
    truth = recon.tape_positions(dirty)
    corrected, corrected_cash, breaks = recon.tape_three_way(dirty)
    explained = recon.explain(dirty, breaks)

    phantom = {row["key"] for row in dirty.truth if row["class"] == "phantom_position"}
    checked = 0
    for symbol in dirty.symbols:
        if symbol in phantom:
            continue
        gap = dirty.app_positions[symbol] + explained.get(symbol, 0) - truth[symbol]
        assert gap == 0, symbol
        checked += 1
    assert checked >= 1

    assert dirty.app_cash + recon.cash_explained(dirty, breaks) == recon.tape_cash(dirty)


def test_the_sign_convention_is_not_symmetric(dirty):
    """Flipping the correction sign must leave a gap, or the test proves nothing."""
    truth = recon.tape_positions(dirty)
    _, _, breaks = recon.tape_three_way(dirty)
    explained = recon.explain(dirty, breaks)
    phantom = {row["key"] for row in dirty.truth if row["class"] == "phantom_position"}
    worst = 0
    for symbol in dirty.symbols:
        if symbol in phantom:
            continue
        worst = max(worst, abs(dirty.app_positions[symbol] - explained.get(symbol, 0) - truth[symbol]))
    assert worst > 0


def test_corrected_book_matches_the_tape(dirty):
    truth_pos = recon.tape_positions(dirty)
    corrected, corrected_cash, _ = recon.tape_three_way(dirty)
    assert corrected == truth_pos
    assert corrected_cash == recon.tape_cash(dirty)


def test_duplicate_correction_is_keyed_to_the_order(dirty):
    _, _, breaks = recon.tape_three_way(dirty)
    duplicates = [brk for brk in breaks if brk.cls == "duplicate_fill"]
    truth_duplicates = {row["key"] for row in dirty.truth if row["class"] == "duplicate_fill"}
    assert {brk.key for brk in duplicates} == truth_duplicates
    for brk in duplicates:
        assert brk.shares < 0 or brk.shares > 0
        assert brk.impact > 0


def test_price_drift_never_moves_shares(dirty):
    _, _, breaks = recon.tape_three_way(dirty)
    drifts = [brk for brk in breaks if brk.cls == "price_drift"]
    assert drifts
    for brk in drifts:
        assert brk.shares == 0
        assert brk.cash != 0

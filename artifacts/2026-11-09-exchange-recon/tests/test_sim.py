from orderrecon import sim


def test_same_seed_gives_the_same_session():
    a = sim.build(seed=3, n_orders=80, per_class=4)
    b = sim.build(seed=3, n_orders=80, per_class=4)
    assert a.tape == b.tape
    assert a.broker == b.broker
    assert a.app_fills == b.app_fills
    assert a.app_positions == b.app_positions
    assert a.app_cash == b.app_cash
    assert a.truth == b.truth


def test_different_seed_gives_different_fills():
    a = sim.build(seed=3, n_orders=80, per_class=4)
    b = sim.build(seed=4, n_orders=80, per_class=4)
    assert a.tape != b.tape


def test_every_injected_class_is_labelled(dirty):
    classes = {row["class"] for row in dirty.truth}
    assert classes == {
        "duplicate_fill",
        "missing_fill",
        "price_drift",
        "qty_mismatch",
        "broker_qty_lag",
        "fill_after_cancel",
        "orphan_fill",
        "phantom_position",
    }
    counts = {}
    for row in dirty.truth:
        counts[row["class"]] = counts.get(row["class"], 0) + 1
    for cls in ("duplicate_fill", "missing_fill", "price_drift", "qty_mismatch"):
        assert counts[cls] == 6, cls
    assert counts["phantom_position"] == min(6, len(dirty.symbols) // 2)


def test_no_order_carries_two_injected_conflicts(dirty):
    order_keys = [row["key"] for row in dirty.truth if row["class"] != "phantom_position"]
    assert len(order_keys) == len(set(order_keys))


def test_app_positions_follow_the_app_archive(dirty):
    booked: dict[str, int] = {}
    for fill in dirty.app_fills:
        if fill.order_id in dirty.broker:
            direction = 1 if fill.side == "BUY" else -1
            booked[fill.symbol] = booked.get(fill.symbol, 0) + direction * fill.qty
    phantom = {
        row["key"]
        for row in dirty.truth
        if row["class"] == "phantom_position"
    }
    for symbol in dirty.symbols:
        if symbol in phantom:
            continue
        assert dirty.app_positions[symbol] == booked.get(symbol, 0)


def test_clean_session_has_no_truth(clean):
    assert clean.truth == []
    flow = clean.start_cash + sum(
        (-1 if fill.side == "BUY" else 1) * fill.qty * fill.price - fill.fee for fill in clean.tape
    )
    assert clean.app_cash == flow

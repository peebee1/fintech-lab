"""Deterministic synthetic trading session with injected reconciliation breaks.

Three views of one session are generated: the exchange tape (truth for quantity
and price), the broker order API (truth for order state, often stale), and the
retail app's own fill archive and position book (the claim under test).

Every break has ground truth attached, so detection can be scored instead of
asserted.
"""

from __future__ import annotations

import random
from dataclasses import replace

from .model import (
    BUY,
    CANCELLED,
    FILLED,
    OPEN,
    REJECTED,
    SELL,
    Break,
    BrokerOrder,
    Fill,
    Session,
    cash_flow,
    sign,
)

# Prices in paise.
SYMBOLS: dict[str, int] = {
    "RELIANCE": 294_000,
    "INFY": 154_000,
    "TCS": 412_000,
    "HDFCBANK": 168_000,
    "ICICIBANK": 129_000,
    "SBIN": 82_000,
    "BHARTIARTL": 158_000,
    "ITC": 43_500,
    "LT": 365_000,
    "AXISBANK": 112_000,
    "KOTAKBANK": 178_000,
    "MARUTI": 1_240_000,
}

SYMBOL_NAMES = tuple(SYMBOLS)
SIZES = (1, 2, 5, 10, 10, 25, 25, 50, 75, 100, 150, 200)


def _split(rng: random.Random, total: int, parts: int) -> list[int]:
    parts = max(1, min(parts, total))
    if parts == 1:
        return [total]
    cuts = sorted(rng.sample(range(1, total), parts - 1))
    edges = [0, *cuts, total]
    return [b - a for a, b in zip(edges, edges[1:])]


def _make_orders(rng: random.Random, n_orders: int) -> tuple[list[dict], list[dict]]:
    orders: list[dict] = []
    raw: list[dict] = []
    for i in range(n_orders):
        order_id = f"O{100000 + i}"
        symbol = rng.choice(SYMBOL_NAMES)
        side = BUY if rng.random() < 0.55 else SELL
        qty = rng.choice(SIZES)
        ref = SYMBOLS[symbol]
        limit = max(1, ref + rng.randint(-ref // 400, ref // 400))
        bucket = rng.choices([0, 1, 2], weights=[18, 62, 20])[0]
        if bucket == 0:
            status = rng.choices([OPEN, CANCELLED, REJECTED], weights=[45, 40, 15])[0]
            filled = 0
            nfill = 0
        else:
            partial = qty >= 2 and rng.random() < 0.18
            if partial:
                filled = rng.randint(1, qty - 1)
                status = CANCELLED
            else:
                filled = qty
                status = FILLED
            nfill = rng.choices([1, 2, 2, 3, 4], weights=[45, 25, 15, 10, 5])[0]
        parts = _split(rng, filled, nfill) if nfill else []
        orders.append(
            {"order_id": order_id, "symbol": symbol, "side": side, "qty": qty, "status": status}
        )
        for part in parts:
            price = max(1, limit + rng.randint(-5, 5))
            fee = min(2000, max(0, part * price // 10000))
            raw.append(
                {
                    "order_id": order_id,
                    "symbol": symbol,
                    "side": side,
                    "qty": part,
                    "price": price,
                    "fee": fee,
                }
            )
    return orders, raw


def _tape(raw: list[dict], rng: random.Random) -> list[Fill]:
    rng.shuffle(raw)
    tape = []
    for seq, row in enumerate(raw):
        tape.append(
            Fill(
                trade_id=f"TR{seq:08d}",
                order_id=row["order_id"],
                symbol=row["symbol"],
                side=row["side"],
                qty=row["qty"],
                price=row["price"],
                fee=row["fee"],
                seq=seq,
            )
        )
    return tape


def _broker_orders(orders: list[dict], tape: list[Fill], rng: random.Random) -> dict[str, BrokerOrder]:
    by_order: dict[str, list[Fill]] = {}
    for fill in tape:
        by_order.setdefault(fill.order_id, []).append(fill)
    book: dict[str, BrokerOrder] = {}
    for order in orders:
        fills = by_order.get(order["order_id"], [])
        filled = sum(f.qty for f in fills)
        notional = sum(f.qty * f.price for f in fills)
        avg = round(notional / filled) if filled else 0
        cancel_seq = None
        if order["status"] == CANCELLED:
            if fills:
                # Strictly after the last print, so a clean cancel never looks
                # like a fill that raced it.
                cancel_seq = min(len(tape), fills[-1].seq + rng.randint(1, 2))
            else:
                cancel_seq = rng.randrange(max(1, len(tape)))
        book[order["order_id"]] = BrokerOrder(
            order_id=order["order_id"],
            symbol=order["symbol"],
            side=order["side"],
            qty=order["qty"],
            status=order["status"],
            filled_qty=filled,
            avg_price=avg,
            cancel_seq=cancel_seq,
        )
    return book


def _eligible(orders: list[dict], tape: list[Fill]) -> dict[str, list[dict]]:
    fills_by_order: dict[str, list[Fill]] = {}
    for fill in tape:
        fills_by_order.setdefault(fill.order_id, []).append(fill)
    out = {
        "has_fill": [],
        "multi_fill": [],
        "cancelled_with_fill": [],
        "partial_cancel": [],
    }
    for order in orders:
        fills = fills_by_order.get(order["order_id"], [])
        if fills:
            out["has_fill"].append(order)
        if len(fills) >= 2:
            out["multi_fill"].append(order)
        if order["status"] == CANCELLED and fills:
            out["cancelled_with_fill"].append(order)
        if order["status"] == FILLED and len(fills) >= 2:
            out["partial_cancel"].append(order)
    return out


def _pick(pool: list[dict], used: set[str], rng: random.Random, k: int) -> list[dict]:
    candidates = [order for order in pool if order["order_id"] not in used]
    chosen = rng.sample(candidates, min(k, len(candidates)))
    used.update(order["order_id"] for order in chosen)
    return chosen


def build(
    seed: int = 11,
    n_orders: int = 1200,
    per_class: int = 40,
    start_cash: int = 50_000_000,
) -> Session:
    rng = random.Random(seed)
    orders, raw = _make_orders(rng, n_orders)
    tape = _tape(raw, rng)
    broker = _broker_orders(orders, tape, rng)

    by_order: dict[str, list[Fill]] = {}
    for fill in tape:
        by_order.setdefault(fill.order_id, []).append(fill)

    archives: dict[str, list[Fill]] = {oid: list(fills) for oid, fills in by_order.items()}
    truth: list[dict] = []
    used: set[str] = set()
    pools = _eligible(orders, tape)
    broker = dict(broker)

    def archive_of(order_id: str) -> list[Fill]:
        return archives.setdefault(order_id, [])

    # 1. A replayed websocket frame books the same print twice.
    for order in _pick(pools["has_fill"], used, rng, per_class):
        fills = archive_of(order["order_id"])
        if not fills:
            continue
        archives[order["order_id"]] = fills + [fills[rng.randrange(len(fills))]]
        truth.append({"class": "duplicate_fill", "key": order["order_id"]})

    # 2. A print never reaches the app at all.
    for order in _pick(pools["has_fill"], used, rng, per_class):
        fills = archive_of(order["order_id"])
        if not fills:
            continue
        fills.pop(rng.randrange(len(fills)))
        truth.append({"class": "missing_fill", "key": order["order_id"]})

    # 3. The app records a price that never traded.
    for order in _pick(pools["has_fill"], used, rng, per_class):
        fills = archive_of(order["order_id"])
        if not fills:
            continue
        idx = rng.randrange(len(fills))
        drift = rng.choice([6, 10, 15, 25, 40, 60])
        direction = rng.choice([-1, 1])
        new_price = max(1, fills[idx].price + direction * max(1, fills[idx].price * drift // 10000))
        fills[idx] = replace(fills[idx], price=new_price)
        truth.append({"class": "price_drift", "key": order["order_id"]})

    # 4. Same print, different quantity.
    for order in _pick(pools["has_fill"], used, rng, per_class):
        fills = archive_of(order["order_id"])
        if not fills:
            continue
        idx = rng.randrange(len(fills))
        delta = rng.choice([-3, -2, -1, 1, 2])
        new_qty = fills[idx].qty + delta
        if new_qty < 1:
            new_qty = fills[idx].qty + 2
        fills[idx] = replace(fills[idx], qty=new_qty)
        truth.append({"class": "qty_mismatch", "key": order["order_id"]})

    # 5. The broker snapshot lags the last print.
    for order in _pick(pools["multi_fill"], used, rng, per_class):
        oid = order["order_id"]
        last = by_order[oid][-1]
        record = broker[oid]
        broker[oid] = replace(record, filled_qty=max(0, record.filled_qty - last.qty))
        truth.append({"class": "broker_qty_lag", "key": oid})

    # 6. The app cancelled the order, the exchange filled it anyway.
    for order in _pick(pools["cancelled_with_fill"], used, rng, per_class):
        oid = order["order_id"]
        last = by_order[oid][-1]
        record = broker[oid]
        broker[oid] = replace(record, cancel_seq=max(0, last.seq - 1))
        truth.append({"class": "fill_after_cancel", "key": oid})

    # 7. A fill for an order id the app was never told about.
    for order in _pick(pools["has_fill"], used, rng, per_class):
        idx = len(truth)
        phantom_order = f"OX{idx:06d}"
        price = SYMBOLS[order["symbol"]]
        archives[phantom_order] = [
            Fill(
                trade_id=f"XT{idx:06d}",
                order_id=phantom_order,
                symbol=order["symbol"],
                side=order["side"],
                qty=rng.choice(SIZES),
                price=price,
                fee=0,
                seq=len(tape) + idx,
            )
        ]
        truth.append({"class": "orphan_fill", "key": phantom_order})

    symbols = SYMBOL_NAMES
    # 8. A position changes with no fill behind it, as a split credit would.
    # Capped at half the symbol universe so the explained delta test still has
    # clean symbols to run on.
    phantom_symbols = rng.sample(list(symbols), k=min(per_class, len(symbols) // 2))
    phantom_deltas: dict[str, int] = {}
    for symbol in phantom_symbols:
        delta = rng.choice([5, 10, 25, 50, 100]) * rng.choice([-1, 1])
        phantom_deltas[symbol] = delta
        truth.append({"class": "phantom_position", "key": symbol})

    app_fills = sorted(
        (fill for fills in archives.values() for fill in fills),
        key=lambda f: (f.seq, f.trade_id),
    )

    known = set(broker)
    positions = {symbol: 0 for symbol in symbols}
    cash = start_cash
    for fill in app_fills:
        if fill.order_id in known:
            positions[fill.symbol] += sign(fill.side) * fill.qty
            cash += cash_flow(fill)
    for symbol, delta in phantom_deltas.items():
        positions[symbol] += delta

    last_price = {symbol: SYMBOLS[symbol] for symbol in symbols}
    for fill in tape:
        last_price[fill.symbol] = fill.price

    return Session(
        tape=tape,
        broker=broker,
        app_fills=app_fills,
        app_positions=positions,
        app_cash=cash,
        start_cash=start_cash,
        truth=truth,
        last_price=last_price,
        symbols=symbols,
    )

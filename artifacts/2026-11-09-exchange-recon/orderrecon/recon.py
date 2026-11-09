"""Three reconciliation policies over the same session.

broker_only   trusts the broker's cumulative filled quantity.
stream_replay books the app's fill archive in arrival order, duplicates included.
tape_three_way treats the exchange tape as truth, the broker as order state, and
              the app archive as the claim, then explains every share of drift.
"""

from __future__ import annotations

from collections import Counter, defaultdict

from .model import FILL_LEVEL, Break, Fill, Session, cash_flow, sign


def tape_positions(session: Session) -> dict[str, int]:
    positions = {symbol: 0 for symbol in session.symbols}
    for fill in session.tape:
        positions[fill.symbol] += sign(fill.side) * fill.qty
    return positions


def tape_cash(session: Session) -> int:
    return session.start_cash + sum(cash_flow(fill) for fill in session.tape)


def broker_positions(session: Session) -> dict[str, int]:
    positions = {symbol: 0 for symbol in session.symbols}
    for order in session.broker.values():
        positions[order.symbol] += sign(order.side) * order.filled_qty
    return positions


def stream_positions(session: Session) -> tuple[dict[str, int], int, list[Break]]:
    """Book every archived fill as it arrived. Duplicates are alerted, not removed."""
    positions = {symbol: 0 for symbol in session.symbols}
    cash = session.start_cash
    seen: set[str] = set()
    breaks: list[Break] = []
    for fill in session.app_fills:
        if fill.trade_id in seen:
            breaks.append(
                Break(
                    "duplicate_fill",
                    fill.order_id,
                    impact=fill.qty * fill.price,
                    detail=f"trade {fill.trade_id} booked again",
                )
            )
        seen.add(fill.trade_id)
        positions[fill.symbol] += sign(fill.side) * fill.qty
        cash += cash_flow(fill)
    return positions, cash, breaks


def _unmatched_app_fills(session: Session) -> list[Break]:
    tape_ids = {fill.trade_id for fill in session.tape}
    breaks = []
    for fill in session.app_fills:
        if fill.trade_id not in tape_ids:
            breaks.append(
                Break(
                    "orphan_fill",
                    fill.order_id,
                    impact=fill.qty * fill.price,
                    detail=f"trade {fill.trade_id} has no exchange print",
                )
            )
    return breaks


def tape_three_way(session: Session) -> tuple[dict[str, int], int, list[Break]]:
    tape_by_id = {fill.trade_id: fill for fill in session.tape}
    app_counts = Counter(fill.trade_id for fill in session.app_fills)
    app_first: dict[str, Fill] = {}
    for fill in session.app_fills:
        app_first.setdefault(fill.trade_id, fill)

    breaks: list[Break] = []

    # Duplicates: every copy past the first is one extra booking.
    for trade_id in sorted(app_counts):
        extra = app_counts[trade_id] - 1
        if extra <= 0:
            continue
        fill = app_first[trade_id]
        breaks.append(
            Break(
                "duplicate_fill",
                fill.order_id,
                shares=-extra * sign(fill.side) * fill.qty,
                cash=-extra * cash_flow(fill),
                impact=extra * fill.qty * fill.price,
                detail=f"trade {trade_id} archived {app_counts[trade_id]} times",
            )
        )

    # Missing: on the tape, absent from the app archive.
    for trade_id in sorted(tape_by_id):
        if trade_id in app_counts:
            continue
        fill = tape_by_id[trade_id]
        breaks.append(
            Break(
                "missing_fill",
                fill.order_id,
                shares=sign(fill.side) * fill.qty,
                cash=cash_flow(fill),
                impact=fill.qty * fill.price,
                detail=f"trade {trade_id} never reached the app",
            )
        )

    # Orphans: in the app archive, no exchange print behind it.
    breaks.extend(_unmatched_app_fills(session))

    # Matched prints that disagree on quantity or price.
    for trade_id in sorted(tape_by_id):
        tape_fill = tape_by_id[trade_id]
        app_fill = app_first.get(trade_id)
        if app_fill is None:
            continue
        if app_fill.qty != tape_fill.qty:
            breaks.append(
                Break(
                    "qty_mismatch",
                    tape_fill.order_id,
                    shares=sign(tape_fill.side) * (tape_fill.qty - app_fill.qty),
                    cash=cash_flow(tape_fill) - cash_flow(app_fill),
                    impact=abs(tape_fill.qty - app_fill.qty) * tape_fill.price,
                    detail=f"trade {trade_id}: tape {tape_fill.qty}, app {app_fill.qty}",
                )
            )
        elif app_fill.price != tape_fill.price:
            breaks.append(
                Break(
                    "price_drift",
                    tape_fill.order_id,
                    shares=0,
                    cash=cash_flow(tape_fill) - cash_flow(app_fill),
                    impact=abs(tape_fill.qty * (tape_fill.price - app_fill.price)),
                    detail=f"trade {trade_id}: tape {tape_fill.price}, app {app_fill.price}",
                )
            )

    tape_by_order: dict[str, list[Fill]] = defaultdict(list)
    for fill in session.tape:
        tape_by_order[fill.order_id].append(fill)

    for order_id in sorted(session.broker):
        order = session.broker[order_id]
        tape_qty = sum(fill.qty for fill in tape_by_order.get(order_id, []))
        if order.filled_qty != tape_qty:
            gap = tape_qty - order.filled_qty
            price = order.avg_price or session.last_price.get(order.symbol, 0)
            breaks.append(
                Break(
                    "broker_qty_lag",
                    order_id,
                    impact=abs(gap) * price,
                    detail=f"broker {order.filled_qty}, tape {tape_qty}",
                )
            )
        if order.status == "CANCELLED" and order.cancel_seq is not None:
            raced = [
                fill
                for fill in tape_by_order.get(order_id, [])
                if fill.seq >= order.cancel_seq
            ]
            if raced:
                breaks.append(
                    Break(
                        "fill_after_cancel",
                        order_id,
                        impact=sum(fill.qty * fill.price for fill in raced),
                        detail=(
                            f"cancelled at seq {order.cancel_seq}, "
                            f"{len(raced)} fill(s) printed after"
                        ),
                    )
                )

    # Positions that moved without a fill behind them.
    booked: dict[str, int] = defaultdict(int)
    for fill in session.app_fills:
        if fill.order_id in session.broker:
            booked[fill.symbol] += sign(fill.side) * fill.qty
    for symbol in session.symbols:
        residual = session.app_positions[symbol] - booked[symbol]
        if residual:
            breaks.append(
                Break(
                    "phantom_position",
                    symbol,
                    shares=-residual,
                    impact=abs(residual) * session.last_price.get(symbol, 0),
                    detail=f"{residual:+d} shares with no archived fill",
                )
            )

    corrected = dict(session.app_positions)
    corrected_cash = session.app_cash
    for brk in breaks:
        if brk.cls in FILL_LEVEL:
            corrected[brk_key_symbol(session, brk)] += brk.shares
            corrected_cash += brk.cash
        elif brk.cls == "phantom_position":
            # A split credit has no fill to explain it. The break carries the
            # observed gap as its adjustment, and is kept out of the
            # independent explained delta test for exactly that reason.
            corrected[brk.key] += brk.shares
    return corrected, corrected_cash, breaks


def broker_vs_app(session: Session) -> tuple[dict[str, int], list[Break]]:
    """Reconcile the app against the broker order book only, no tape access.

    This is the common production shape: it can see that the app disagrees with
    the broker, but not which side is wrong, so every disagreement is guessed
    as a duplicate when the app is high and a missing fill when it is low.
    """
    app_signed: dict[str, int] = defaultdict(int)
    for fill in session.app_fills:
        if fill.order_id in session.broker:
            app_signed[fill.order_id] += sign(fill.side) * fill.qty

    breaks: list[Break] = []
    for order_id in sorted(session.broker):
        order = session.broker[order_id]
        gap = app_signed.get(order_id, 0) - sign(order.side) * order.filled_qty
        if gap == 0:
            continue
        cls = "duplicate_fill" if gap > 0 else "missing_fill"
        price = order.avg_price or session.last_price.get(order.symbol, 0)
        breaks.append(
            Break(
                cls,
                order_id,
                impact=abs(gap) * price,
                detail=f"app {app_signed.get(order_id, 0):+d}, broker {sign(order.side) * order.filled_qty:+d}",
            )
        )

    breaks.extend(_unmatched_app_fills(session))

    booked: dict[str, int] = defaultdict(int)
    for fill in session.app_fills:
        if fill.order_id in session.broker:
            booked[fill.symbol] += sign(fill.side) * fill.qty
    for symbol in session.symbols:
        residual = session.app_positions[symbol] - booked[symbol]
        if residual:
            breaks.append(
                Break(
                    "phantom_position",
                    symbol,
                    impact=abs(residual) * session.last_price.get(symbol, 0),
                    detail=f"{residual:+d} shares with no archived fill",
                )
            )
    return dict(session.app_positions), breaks


def brk_key_symbol(session: Session, brk: Break) -> str:
    """The symbol a fill level break moves. Order keyed breaks look it up."""
    if brk.cls == "phantom_position":
        return brk.key
    order = session.broker.get(brk.key)
    if order is not None:
        return order.symbol
    for fill in session.app_fills:
        if fill.order_id == brk.key:
            return fill.symbol
    return session.symbols[0]


def explain(session: Session, breaks: list[Break], cls_filter=FILL_LEVEL) -> dict[str, int]:
    """Sum share corrections per symbol from fill level breaks only."""
    out: dict[str, int] = defaultdict(int)
    for brk in breaks:
        if brk.cls in cls_filter:
            out[brk_key_symbol(session, brk)] += brk.shares
    return dict(out)


def cash_explained(session: Session, breaks: list[Break], cls_filter=FILL_LEVEL) -> int:
    return sum(brk.cash for brk in breaks if brk.cls in cls_filter)

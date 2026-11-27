"""Replay one payout policy against the book and balance the seller ledger.

Money is integer cents. The only identity the model must satisfy is arithmetic:

    sales = paid + charged from held funds + charged from later payouts + written off

where the last term is the marketplace's loss on a seller who no longer sells.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from .book import Book
from .policies import Policy

FUNDING_RATE = 0.12


@dataclass
class Item:
    """One slice of a sale waiting to leave the platform."""

    amount: int
    eligible_day: int
    sale_day: int


@dataclass
class SellerState:
    sales: int = 0
    refund_cost: int = 0
    paid: int = 0
    charged_held: int = 0
    charged_carry: int = 0
    written_off: int = 0
    float_cents_days: int = 0
    carried: int = 0
    held: list[Item] = field(default_factory=list)
    last_refund_day: int = -1
    last_sale_day: int = -1
    first_uncovered_day: int = -1


def simulate(policy: Policy, book: Book, funding_rate: float = FUNDING_RATE) -> dict:
    sellers = {s.id: s for s in book.sellers}
    state = {sid: SellerState() for sid in sellers}

    orders_by_day: dict[int, list] = defaultdict(list)
    for order in book.orders:
        orders_by_day[order.day].append(order)
    refunds_by_day: dict[int, list] = defaultdict(list)
    for refund in book.refunds:
        refunds_by_day[refund.arrival_day].append(refund)

    end_day = book.horizon + policy_max_delay(policy)

    for day in range(end_day + 1):
        for order in orders_by_day.get(day, ()):
            seller = sellers[order.seller_id]
            hold, rate, reserve_days = policy.terms(seller.band, day - seller.join_day)
            st = state[seller.id]
            st.sales += order.amount_cents
            st.last_sale_day = max(st.last_sale_day, day)
            reserve = int(order.amount_cents * rate)
            st.held.append(Item(order.amount_cents - reserve, day + hold, day))
            if reserve:
                st.held.append(Item(reserve, day + hold + reserve_days, day))

        # Refunds land before the day's payout run, so money still held can cover them.
        for refund in refunds_by_day.get(day, ()):
            st = state[refund.seller_id]
            st.refund_cost += refund.cost_cents
            st.last_refund_day = max(st.last_refund_day, day)
            need = refund.cost_cents
            st.held.sort(key=lambda item: item.eligible_day)
            while need and st.held:
                item = st.held[0]
                take = min(item.amount, need)
                item.amount -= take
                need -= take
                st.charged_held += take
                st.float_cents_days += take * (day - item.sale_day)
                if item.amount == 0:
                    st.held.pop(0)
                else:
                    break
            if need:
                if st.first_uncovered_day < 0:
                    st.first_uncovered_day = day
                if policy.clawback:
                    st.carried += need
                else:
                    st.written_off += need

        for st in state.values():
            if not st.held:
                continue
            remaining = []
            for item in sorted(st.held, key=lambda it: it.eligible_day):
                if item.eligible_day > day:
                    remaining.append(item)
                    continue
                amount = item.amount
                if st.carried:
                    settle = min(amount, st.carried)
                    amount -= settle
                    st.carried -= settle
                    st.charged_carry += settle
                st.paid += amount
                st.float_cents_days += item.amount * (day - item.sale_day)
            st.held = remaining

    for st in state.values():
        st.written_off += st.carried
        st.carried = 0

    leftover = sum(item.amount for st in state.values() for item in st.held)
    return _summarize(policy, book, sellers, state, funding_rate, leftover)


def simulate_oracle(book: Book, funding_rate: float = FUNDING_RATE) -> dict:
    """Perfect foresight: hold exactly the refunds that will land after the payout.

    No seller is ever written off because the platform always keeps enough back,
    which makes this the floor every policy is measured against.
    """
    sellers = {s.id: s for s in book.sellers}
    state = {sid: SellerState() for sid in sellers}

    late_by_seller: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    for refund in book.refunds:
        payout_day = refund.sale_day + 1
        if refund.arrival_day > payout_day:
            late_by_seller[refund.seller_id][refund.arrival_day] += refund.cost_cents

    future = {sid: sum(days.values()) for sid, days in late_by_seller.items()}
    pool = {sid: 0 for sid in sellers}
    sales_by_day: dict[int, list] = defaultdict(list)
    for order in book.orders:
        sales_by_day[order.day].append(order)

    last_day = book.horizon
    for day in range(last_day + 1):
        for order in sales_by_day.get(day, ()):
            st = state[order.seller_id]
            st.sales += order.amount_cents
            st.last_sale_day = max(st.last_sale_day, day)
            pool[order.seller_id] += order.amount_cents
        for sid in sellers:
            arrivals = late_by_seller.get(sid)
            today = arrivals.get(day, 0) if arrivals else 0
            if today:
                st = state[sid]
                st.refund_cost += today
                st.last_refund_day = max(st.last_refund_day, day)
                take = min(pool[sid], today)
                st.charged_held += take
                pool[sid] -= take
                if today > take:
                    st.written_off += today - take
                future[sid] -= today
            release = max(0, pool[sid] - future.get(sid, 0))
            if release:
                state[sid].paid += release
                pool[sid] -= release
            state[sid].float_cents_days += pool[sid]

    for sid in sellers:
        state[sid].paid += pool[sid]
        pool[sid] = 0

    policy = Policy("oracle", hold_days=1, note="perfect foresight on late refunds")
    return _summarize(policy, book, sellers, state, funding_rate)


def policy_max_delay(policy: Policy) -> int:
    if policy.tiered:
        return 14 + 60 + 10
    return policy.hold_days + policy.reserve_days + 10


def _summarize(
    policy: Policy,
    book: Book,
    sellers: dict,
    state: dict[str, SellerState],
    funding_rate: float,
    leftover: int = 0,
) -> dict:
    rows = []
    for sid, st in state.items():
        seller = sellers[sid]
        rows.append(
            {
                "seller": sid,
                "band": seller.band,
                "exit_day": seller.exit_day,
                "sales": st.sales,
                "refund_cost": st.refund_cost,
                "paid": st.paid,
                "charged_held": st.charged_held,
                "charged_carry": st.charged_carry,
                "written_off": st.written_off,
                "float_cents_days": st.float_cents_days,
                "last_sale_day": st.last_sale_day,
                "last_refund_day": st.last_refund_day,
                "first_uncovered_day": st.first_uncovered_day,
            }
        )

    totals = {
        "sales": sum(r["sales"] for r in rows),
        "refund_cost": sum(r["refund_cost"] for r in rows),
        "paid": sum(r["paid"] for r in rows),
        "charged_held": sum(r["charged_held"] for r in rows),
        "charged_carry": sum(r["charged_carry"] for r in rows),
        "written_off": sum(r["written_off"] for r in rows),
        "float_cents_days": sum(r["float_cents_days"] for r in rows),
    }
    totals["float_cost_cents"] = int(round(totals["float_cents_days"] * funding_rate / 365.0))
    totals["economic_cost_cents"] = totals["written_off"] + totals["float_cost_cents"]

    written = sorted((r["written_off"] for r in rows if r["written_off"] > 0), reverse=True)
    top_n = max(1, int(round(len(written) * 0.10))) if written else 0
    tail_share = (sum(written[:top_n]) / sum(written)) if written else 0.0

    gmv = totals["sales"] or 1
    # Two independent identities. Sales either reach the seller or are taken for a
    # refund, and every refund is paid from held funds, from later payouts, or by the
    # platform. Asserting both catches a cent that vanishes in either direction.
    checks = {
        "sales_fully_allocated": all(
            r["sales"] == r["paid"] + r["charged_held"] + r["charged_carry"] for r in rows
        ),
        "refunds_fully_covered": all(
            r["refund_cost"] == r["charged_held"] + r["charged_carry"] + r["written_off"]
            for r in rows
        ),
        "nothing_left_held": leftover == 0,
        "float_non_negative": totals["float_cents_days"] >= 0,
        "every_seller_has_a_sale": all(r["sales"] > 0 for r in rows),
    }

    return {
        "policy": policy.as_dict(),
        "funding_rate": funding_rate,
        "totals": totals,
        "leftover_cents": leftover,
        "rates": {
            "written_off_bps": 10_000 * totals["written_off"] / gmv,
            "float_cost_bps": 10_000 * totals["float_cost_cents"] / gmv,
            "economic_bps": 10_000 * totals["economic_cost_cents"] / gmv,
            "refund_bps": 10_000 * totals["refund_cost"] / gmv,
        },
        "writeoff": {
            "sellers": len(written),
            "largest": written[0] if written else 0,
            "top_decile_share": tail_share,
        },
        "checks": checks,
        "rows": rows,
    }

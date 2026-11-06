"""The bench: run every policy over the same book, then sweep the assumptions."""

from __future__ import annotations

from dataclasses import dataclass, field

from . import data, outcomes, policies, psps
from .data import Txn


@dataclass
class Result:
    policy: str
    transactions: int = 0
    attempts: int = 0
    approved: int = 0
    hard_declines: int = 0
    captured: int = 0
    settled_cents: int = 0
    fees_cents: int = 0
    ops_cents: int = 0
    gross_cents: int = 0
    net_cents: int = 0
    blocks: list[tuple[int, int, int, int]] = field(default_factory=list)

    def as_dict(self) -> dict:
        n = max(self.transactions, 1)
        return {
            "policy": self.policy,
            "transactions": self.transactions,
            "attempts": self.attempts,
            "attempts_per_txn": round(self.attempts / n, 3),
            "auth_rate": round(self.approved / n, 4),
            "hard_declines": self.hard_declines,
            "settled_cents": self.settled_cents,
            "fees_cents": self.fees_cents,
            "ops_cents": self.ops_cents,
            "gross_cents": self.gross_cents,
            "net_cents": self.net_cents,
            "net_per_1000_cents": round(self.net_cents / n * 1000),
            "fee_bps": round(self.fees_cents / self.settled_cents * 10000, 1) if self.settled_cents else 0.0,
            "avg_ticket_cents": round(self.settled_cents / self.captured) if self.captured else 0,
        }


def run(
    policy: policies.Policy,
    book: list[Txn],
    seed: int = 99,
    max_retries: int = 1,
    margin_bps: int = data.MARGIN_BPS,
    block: int = 5000,
    drift: psps.Drift | None = None,
) -> Result:
    result = Result(policy=policy.name, transactions=len(book))
    block_net = 0
    block_n = 0
    block_approved = 0
    for txn in book:
        order = policy.rank(txn)
        attempt = 0
        psp = order[0]
        while True:
            result.attempts += 1
            result.ops_cents += data.OPS_CENTS
            authorized = outcomes.authorizes(seed, txn, psp, attempt, retry=attempt > 0, drift=drift)
            if authorized:
                fee = psps.BY_NAME[psp].fee(txn.amount)
                gross = data.margin_cents(txn.amount, margin_bps)
                net = gross - fee - data.OPS_CENTS
                result.approved += 1
                result.captured += 1
                result.settled_cents += txn.amount
                result.fees_cents += fee
                result.gross_cents += gross
                result.net_cents += net
                block_net += net
                block_approved += 1
                policy.observe(txn, psp, True, net)
                break
            result.net_cents -= data.OPS_CENTS
            block_net -= data.OPS_CENTS
            policy.observe(txn, psp, False, -data.OPS_CENTS)
            if outcomes.is_hard(seed, txn.index, psp, attempt):
                result.hard_declines += 1
                break
            if attempt >= max_retries:
                break
            attempt += 1
            psp = order[attempt]
        block_n += 1
        if block_n == block:
            result.blocks.append((txn.index // block + 1, block_net, block_n, block_approved))
            block_net, block_n, block_approved = 0, 0, 0
    if block_n:
        result.blocks.append((book[-1].index // block + 1, block_net, block_n, block_approved))
    return result


def _segment_expectations(book: list[Txn], margin_bps: int = data.MARGIN_BPS) -> list[dict]:
    buckets: dict[str, list[Txn]] = {}
    for txn in book:
        buckets.setdefault(txn.context, []).append(txn)
    rows = []
    for context, txns in sorted(buckets.items()):
        per_arm = {
            name: sum(psp.expected_net(t, margin_bps) for t in txns) / len(txns)
            for name, psp in psps.BY_NAME.items()
        }
        best = max(per_arm, key=lambda n: per_arm[n])
        worst = min(per_arm, key=lambda n: per_arm[n])
        fee_only = min(per_arm, key=lambda n: psps.BY_NAME[n].fee(txns[0].amount))
        rows.append(
            {
                "context": context,
                "transactions": len(txns),
                "mean_ticket_cents": round(sum(t.amount for t in txns) / len(txns)),
                "expected_net": {k: round(v) for k, v in per_arm.items()},
                "best_arm": best,
                "fee_only_arm": fee_only,
                "fee_only_is_best": fee_only == best,
                "fee_only_is_worst": fee_only == worst,
                "gap_cents": round(per_arm[best] - per_arm[fee_only]),
            }
        )
    return rows


def _learning(result: Result) -> dict:
    return {
        "blocks": [
            {
                "block": index,
                "transactions": n,
                "auth_rate": round(approved / n, 4),
                "net_per_1000_cents": round(net / n * 1000),
            }
            for index, net, n, approved in result.blocks
        ]
    }


def run_all(
    n: int = 50000,
    seed: int = 20261106,
    outcome_seed: int = 99,
    max_retries: int = 1,
    margin_bps: int = data.MARGIN_BPS,
) -> dict:
    book = data.build(n=n, seed=seed)
    makers = {
        "cheapest": policies.Cheapest,
        "static_rules": policies.StaticRules,
        "epsilon_greedy": policies.EpsilonGreedy,
        "thompson": policies.Thompson,
        "thompson_window": policies.ThompsonWindow,
        "oracle": lambda: policies.Oracle(margin_bps),
    }
    results = {
        name: run(make(), book, seed=outcome_seed, max_retries=max_retries, margin_bps=margin_bps)
        for name, make in makers.items()
    }

    baseline = results["cheapest"].as_dict()["net_per_1000_cents"]
    table = []
    for name, res in results.items():
        row = res.as_dict()
        row["vs_cheapest_cents"] = row["net_per_1000_cents"] - baseline
        row["vs_cheapest_pct"] = (
            round((row["net_per_1000_cents"] / baseline - 1) * 100, 2) if baseline else 0.0
        )
        table.append(row)

    retry_sweep = []
    for depth in (0, 1, 2):
        row = {"max_retries": depth, "policies": {}}
        for name in ("cheapest", "static_rules", "thompson", "oracle"):
            metrics = run(
                makers[name](), book, seed=outcome_seed, max_retries=depth, margin_bps=margin_bps
            ).as_dict()
            row["policies"][name] = {
                "auth_rate": metrics["auth_rate"],
                "attempts_per_txn": metrics["attempts_per_txn"],
                "fee_bps": metrics["fee_bps"],
                "net_per_1000_cents": metrics["net_per_1000_cents"],
            }
        row["gap_cheapest_vs_oracle"] = (
            row["policies"]["oracle"]["net_per_1000_cents"]
            - row["policies"]["cheapest"]["net_per_1000_cents"]
        )
        retry_sweep.append(row)

    margin_sweep = []
    for margin in (1000, 1500, 2200):
        cheap = run(
            policies.Cheapest(), book, seed=outcome_seed, max_retries=max_retries, margin_bps=margin
        ).as_dict()
        best = run(
            policies.Oracle(margin), book, seed=outcome_seed, max_retries=max_retries, margin_bps=margin
        ).as_dict()
        margin_sweep.append(
            {
                "margin_bps": margin,
                "cheapest_net_per_1000_cents": cheap["net_per_1000_cents"],
                "oracle_net_per_1000_cents": best["net_per_1000_cents"],
                "gap_cents": best["net_per_1000_cents"] - cheap["net_per_1000_cents"],
                "gap_pct": round((best["net_per_1000_cents"] / cheap["net_per_1000_cents"] - 1) * 100, 2),
            }
        )

    segments = _segment_expectations(book, margin_bps)
    checks = {
        "segments": len(segments),
        "fee_only_not_best": sum(1 for s in segments if not s["fee_only_is_best"]),
        "fee_only_worst": sum(1 for s in segments if s["fee_only_is_worst"]),
        "expected_gap_cents_per_1000": round(
            sum(s["gap_cents"] * s["transactions"] for s in segments) / len(book) * 1000
        ),
    }

    drift = psps.Drift(at=n // 2, psp="bravo", delta=-0.90, token="channel:debit")
    drift_runs = {}
    for name in ("cheapest", "static_rules", "thompson", "thompson_window", "oracle"):
        if name == "oracle":
            policy = policies.Oracle(margin_bps, drift)
        else:
            policy = makers[name]()
        drift_runs[name] = run(
            policy, book, seed=outcome_seed, max_retries=max_retries, margin_bps=margin_bps, drift=drift
        )

    def block_stats(result: Result, after: bool) -> dict:
        if after:
            rows = [b for b in result.blocks if (b[0] - 1) * 5000 >= drift.at]
        else:
            rows = [b for b in result.blocks if b[0] * 5000 <= drift.at]
        if not rows:
            return {"transactions": 0}
        net = sum(b[1] for b in rows)
        n = sum(b[2] for b in rows)
        approved = sum(b[3] for b in rows)
        return {
            "transactions": n,
            "auth_rate": round(approved / n, 4),
            "net_per_1000_cents": round(net / n * 1000),
        }

    drift_section = {
        "at": drift.at,
        "psp": drift.psp,
        "delta": drift.delta,
        "token": drift.token,
        "policies": {
            name: {
                "before": block_stats(res, after=False),
                "after": block_stats(res, after=True),
                "blocks": [
                    {
                        "block": b[0],
                        "auth_rate": round(b[3] / b[2], 4),
                        "net_per_1000_cents": round(b[1] / b[2] * 1000),
                    }
                    for b in res.blocks
                ],
            }
            for name, res in drift_runs.items()
        },
    }

    return {
        "meta": {
            "transactions": n,
            "seed": seed,
            "outcome_seed": outcome_seed,
            "margin_bps": margin_bps,
            "ops_cents": data.OPS_CENTS,
            "max_retries": max_retries,
            "book_digest": data.digest(book),
            "providers": [
                {"name": p.name, "bps": p.bps, "fixed_cents": p.fixed} for p in psps.PSPS
            ],
        },
        "policies": table,
        "segments": segments,
        "checks": checks,
        "retry_sweep": retry_sweep,
        "margin_sweep": margin_sweep,
        "learning": _learning(results["thompson"]),
        "oracle_learning": _learning(results["oracle"]),
        "drift": drift_section,
    }


def summary_text(payload: dict) -> str:
    meta = payload["meta"]
    lines = [
        f"book {meta['transactions']} synthetic transactions, digest {meta['book_digest']}",
        f"margin {meta['margin_bps'] / 100:.1f}% of ticket, ops {meta['ops_cents']}c per attempt, "
        f"retry depth {meta['max_retries']}",
        "",
        f"{'policy':<16}{'att/txn':>8}{'auth%':>8}{'fee bps':>9}{'net $/1000':>12}{'vs cheapest':>13}",
    ]
    for row in payload["policies"]:
        lines.append(
            f"{row['policy']:<16}{row['attempts_per_txn']:>8.2f}{row['auth_rate'] * 100:>7.1f}%"
            f"{row['fee_bps']:>9.1f}{row['net_per_1000_cents'] / 100:>12,.2f}"
            f"{row['vs_cheapest_cents'] / 100:>+13,.2f}"
        )
    lines += ["", "where the fee only choice is wrong, single attempt expectation"]
    lines.append(f"{'segment':<30}{'n':>7}{'ticket':>8}{'fee arm':>9}{'best':>8}{'gap $/txn':>12}")
    for seg in sorted(payload["segments"], key=lambda s: -s["gap_cents"]):
        lines.append(
            f"{seg['context']:<30}{seg['transactions']:>7}{seg['mean_ticket_cents'] / 100:>8.0f}"
            f"{seg['fee_only_arm']:>9}{seg['best_arm']:>8}{seg['gap_cents'] / 100:>12,.2f}"
        )
    lines += ["", "retry depth sweep"]
    lines.append(
        f"{'depth':>6}{'cheap auth%':>13}{'oracle auth%':>14}{'cheap fee bps':>15}{'gap $/1000':>12}"
    )
    for row in payload["retry_sweep"]:
        lines.append(
            f"{row['max_retries']:>6}{row['policies']['cheapest']['auth_rate'] * 100:>12.1f}%"
            f"{row['policies']['oracle']['auth_rate'] * 100:>13.1f}%"
            f"{row['policies']['cheapest']['fee_bps']:>15.1f}"
            f"{row['gap_cheapest_vs_oracle'] / 100:>12,.2f}"
        )
    lines += ["", "margin assumption sweep"]
    lines.append(f"{'margin%':>9}{'cheapest $/1000':>18}{'oracle $/1000':>15}{'gap %':>8}")
    for row in payload["margin_sweep"]:
        lines.append(
            f"{row['margin_bps'] / 100:>9.0f}{row['cheapest_net_per_1000_cents'] / 100:>18,.2f}"
            f"{row['oracle_net_per_1000_cents'] / 100:>15,.2f}{row['gap_pct']:>8.1f}"
        )
    lines += ["", "thompson learning curve, net $ per 1000 by block, against full knowledge"]
    oracle_blocks = {b["block"]: b["net_per_1000_cents"] for b in payload["oracle_learning"]["blocks"]}
    for block in payload["learning"]["blocks"]:
        lines.append(
            f"block {block['block']:>2}  thompson {block['net_per_1000_cents'] / 100:>9,.2f}"
            f"  oracle {oracle_blocks[block['block']] / 100:>9,.2f}"
        )
    checks = payload["checks"]
    lines += [
        "",
        f"segments {checks['segments']}, fee only arm is not best in {checks['fee_only_not_best']}, "
        f"is worst in {checks['fee_only_worst']}",
    ]
    drift = payload["drift"]
    lines += [
        "",
        f"regime shift at transaction {drift['at']}: {drift['psp']} loses "
        f"{abs(drift['delta']):.2f} logit on {drift['token']}",
        f"{'policy':<16}{'net before':>12}{'net after':>11}{'change':>10}{'auth after':>12}",
    ]
    for name, row in drift["policies"].items():
        before = row["before"].get("net_per_1000_cents", 0) / 100
        after = row["after"].get("net_per_1000_cents", 0) / 100
        lines.append(
            f"{name:<16}{before:>12,.2f}{after:>11,.2f}{after - before:>+10,.2f}"
            f"{row['after'].get('auth_rate', 0) * 100:>11.1f}%"
        )
    lines += ["", "net $ per 1000 by block after the shift"]
    lines.append(f"{'block':>6}{'static':>11}{'thompson':>11}{'window':>10}{'oracle':>10}")
    series = {name: {b['block']: b for b in row["blocks"]} for name, row in drift["policies"].items()}
    for index in sorted(series["oracle"]):
        if (index - 1) * 5000 < drift["at"]:
            continue
        lines.append(
            f"{index:>6}{series['static_rules'][index]['net_per_1000_cents'] / 100:>11,.2f}"
            f"{series['thompson'][index]['net_per_1000_cents'] / 100:>11,.2f}"
            f"{series['thompson_window'][index]['net_per_1000_cents'] / 100:>10,.2f}"
            f"{series['oracle'][index]['net_per_1000_cents'] / 100:>10,.2f}"
        )
    return "\n".join(lines)

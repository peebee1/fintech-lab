"""Conformance checks, run against five implementations.

Every check states the required behaviour, drives the API through the interleaving
that exposes it, and records a named violation code when the behaviour is missing.
The violation code matters more than the pass flag: "double_charge" under overlap
and "double_charge" after a crash are different defects with the same symptom.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from time import perf_counter
from typing import Callable

from .api import LEASE_SECONDS, MODES, TTL_SECONDS, PaymentAPI, Response
from .ledger import HandlerError

AMOUNT = 1250
CURRENCY = "EUR"
ACCOUNT = "acct_a"


def body(amount: int = AMOUNT, customer: str = "cus_1", account: str = ACCOUNT) -> dict:
    return {"account": account, "amount": amount, "currency": CURRENCY, "customer": customer}


class Report:
    def __init__(self) -> None:
        self.codes: list[str] = []

    def require(self, condition: bool, code: str) -> None:
        if not condition:
            self.codes.append(code)

    def no_phantom(self, api: PaymentAPI, response: Response) -> None:
        if response.status == 201:
            charge_id = response.body.get("charge_id")
            self.require(charge_id in api.ledger.ids(), "phantom_charge")


@dataclass
class Check:
    name: str
    title: str
    proves: str
    fn: Callable[[PaymentAPI, Report], tuple[int, int]]


@dataclass
class Result:
    check: str
    title: str
    passed: bool
    violations: list[str]
    charges: int
    expected_charges: int
    value_minor: int

    @property
    def excess(self) -> int:
        return max(0, self.charges - self.expected_charges)


# --------------------------------------------------------------------- checks


def c_missing_key(api: PaymentAPI, r: Report) -> tuple[int, int]:
    response = api.request(ACCOUNT, "", body(), now=0)
    r.require(response.status == 400, "missing_key_accepted")
    r.require(len(api.ledger) == 0, "charged_without_key")
    return 0, AMOUNT


def c_replay_same_body(api: PaymentAPI, r: Report) -> tuple[int, int]:
    first = api.request(ACCOUNT, "key-1", body(), now=0)
    second = api.request(ACCOUNT, "key-1", body(), now=1)
    r.require(first.status == 201 and first.executed, "first_request_not_executed")
    r.require(second.status == 201, "replay_status", )
    r.require(second.replayed, "replay_not_marked")
    r.require(second.headers().get("Idempotent-Replayed") == "true", "replay_header_missing")
    r.require(first.canonical_body() == second.canonical_body(), "replay_body_differs")
    r.no_phantom(api, second)
    r.require(len(api.ledger) == 1, "replay_double_charged")
    return 1, AMOUNT


def c_replay_different_body(api: PaymentAPI, r: Report) -> tuple[int, int]:
    api.request(ACCOUNT, "key-2", body(), now=0)
    conflict = api.request(ACCOUNT, "key-2", body(amount=9900), now=1)
    r.require(conflict.status == 422, "conflict_not_refused")
    r.require(len(api.ledger) == 1, "conflict_re_executed")
    r.require(api.ledger.total() == AMOUNT, "conflict_changed_amount")
    return 1, AMOUNT


def c_overlap_two(api: PaymentAPI, r: Report) -> tuple[int, int]:
    first = api.admit(ACCOUNT, "key-3", body(), now=0, owner="req-a")
    second = api.admit(ACCOUNT, "key-3", body(), now=0, owner="req-b")
    first_response = api.finish(first)
    second_response = api.finish(second)
    r.require(first_response.status == 201, "first_overlap_refused")
    r.require(second_response.status == 409, "overlap_second_executed")
    r.require(second_response.status != 201 or not second_response.executed, "overlap_second_charged")
    r.require(second_response.headers().get("Retry-After") is not None or second_response.status != 409,
              "overlap_no_retry_after")
    r.no_phantom(api, first_response)
    r.no_phantom(api, second_response)
    r.require(len(api.ledger) == 1, "overlap_double_charged")
    return 1, AMOUNT


def c_burst_five(api: PaymentAPI, r: Report) -> tuple[int, int]:
    owners = [f"req-{i}" for i in range(5)]
    decisions = [api.admit(ACCOUNT, "key-4", body(), now=0, owner=o) for o in owners]
    responses = [api.finish(d) for d in decisions]
    charged = [x for x in responses if x.status == 201]
    r.require(len(charged) == 1, "burst_multiple_charges")
    r.require(all(x.status in (201, 409) for x in responses), "burst_unexpected_status")
    r.require(len(api.ledger) == 1, "burst_double_charged")
    for response in responses:
        r.no_phantom(api, response)
    return 1, AMOUNT


def c_crash_after_effect(api: PaymentAPI, r: Report) -> tuple[int, int]:
    crash = api.crash_after_effect(ACCOUNT, "key-5", body(), now=0)
    r.require(crash.get("crashed") is True, "charge_did_not_happen")
    survivor = api.reopen()
    replay = survivor.request(ACCOUNT, "key-5", body(), now=LEASE_SECONDS + 1)
    r.require(replay.status == 201, "recovery_status")
    r.require(replay.replayed, "recovery_not_marked_replay")
    r.require(replay.body.get("charge_id") == crash.get("charge_id"), "recovery_returned_other_charge")
    r.no_phantom(survivor, replay)
    r.require(len(survivor.ledger) == 1, "crash_double_charged")
    return 1, AMOUNT


def c_in_lease_replay(api: PaymentAPI, r: Report) -> tuple[int, int]:
    api.crash_after_effect(ACCOUNT, "key-6", body(), now=0)
    survivor = api.reopen()
    replay = survivor.request(ACCOUNT, "key-6", body(), now=5)
    r.require(replay.status == 409, "lease_not_enforced")
    r.require(replay.body.get("error") == "request_in_progress", "lease_wrong_error")
    r.require(replay.headers().get("Retry-After") is not None, "lease_no_retry_after")
    r.require(len(survivor.ledger) == 1, "lease_replay_double_charged")
    return 1, AMOUNT


def c_crash_before_effect(api: PaymentAPI, r: Report) -> tuple[int, int]:
    api.crash_before_effect(ACCOUNT, "key-7", body(), now=0)
    survivor = api.reopen()
    retry = survivor.request(ACCOUNT, "key-7", body(), now=LEASE_SECONDS + 1)
    r.require(retry.status == 201, "stale_claim_never_released")
    r.require(len(survivor.ledger) == 1, "stale_claim_charge_count")
    r.no_phantom(survivor, retry)
    return 1, AMOUNT


def c_error_then_retry(api: PaymentAPI, r: Report) -> tuple[int, int]:
    api.ledger.fail_next_append()
    failed = api.request(ACCOUNT, "key-8", body(), now=0)
    retry = api.request(ACCOUNT, "key-8", body(), now=1)
    r.require(failed.status == 502, "error_not_reported")
    r.require(retry.status == 201, "error_cached_as_final")
    r.require(retry.executed, "retry_not_executed")
    r.require(len(api.ledger) == 1, "error_retry_charge_count")
    return 1, AMOUNT


def c_expiry(api: PaymentAPI, r: Report) -> tuple[int, int]:
    api.request(ACCOUNT, "key-9", body(), now=0)
    late = api.request(ACCOUNT, "key-9", body(), now=TTL_SECONDS + 1)
    r.require(late.status == 409, "expired_key_not_refused")
    r.require(late.body.get("error") == "idempotency_key_expired", "expired_wrong_error")
    r.require(len(api.ledger) == 1, "expiry_double_charged")
    return 1, AMOUNT


def c_key_scope(api: PaymentAPI, r: Report) -> tuple[int, int]:
    first = api.request("acct_a", "shared-key", body(amount=800), now=0)
    second = api.request("acct_b", "shared-key", body(amount=800, account="acct_b"), now=1)
    r.require(first.status == 201, "scope_first_refused")
    r.require(second.status == 201, "scope_second_refused")
    r.require(second.executed, "cross_account_collision")
    r.require(second.body.get("account") == "acct_b", "charge_leaked_to_other_account")
    r.require(len(api.ledger) == 2, "scope_charge_count")
    r.require(api.ledger.total() == 1600, "scope_wrong_total")
    return 2, 800


CHECKS: list[Check] = [
    Check("missing_key", "A missing key is refused", "No charge exists without a key.", c_missing_key),
    Check("replay_same_body", "Replay returns the first answer", "One charge, identical body, marked replayed.",
          c_replay_same_body),
    Check("replay_different_body", "Key reuse with a new body is a conflict", "422, and the original charge stands.",
          c_replay_different_body),
    Check("overlap_two", "Two overlapping requests, one charge", "Second is 409 with a lease, ledger has one row.",
          c_overlap_two),
    Check("burst_five", "Five overlapping retries, one charge", "A retry storm cannot open five charges.",
          c_burst_five),
    Check("crash_after_effect", "Crash after the charge, before the response", "The replay returns that charge.",
          c_crash_after_effect),
    Check("in_lease_replay", "A live lease blocks the replay", "409 while the lease runs, one charge.",
          c_in_lease_replay),
    Check("crash_before_effect", "Crash before the charge", "Stale claim is released, exactly one charge results.",
          c_crash_before_effect),
    Check("error_then_retry", "A processor error is not a final answer", "The key is released and the retry runs.",
          c_error_then_retry),
    Check("expiry", "An expired key refuses instead of re-running", "409 expired, no second charge.", c_expiry),
    Check("key_scope", "A key belongs to an account", "Two accounts, same key, two charges.", c_key_scope),
]


# ------------------------------------------------------------------ execution


def run_implementation(mode: str) -> dict:
    results: list[Result] = []
    for check in CHECKS:
        api = PaymentAPI(mode)
        report = Report()
        expected_charges, amount = check.fn(api, report)
        results.append(Result(
            check=check.name,
            title=check.title,
            passed=not report.codes,
            violations=report.codes,
            charges=len(api.ledger),
            expected_charges=expected_charges,
            value_minor=amount,
        ))
    passed = sum(1 for x in results if x.passed)
    classes: dict[str, int] = {}
    for result in results:
        for code in result.violations:
            classes[code] = classes.get(code, 0) + 1
    excess = sum(x.excess for x in results)
    excess_value = sum(x.excess * x.value_minor for x in results if x.excess)
    return {
        "mode": mode,
        "checks_passed": passed,
        "checks_total": len(results),
        "excess_charges": excess,
        "excess_value_minor": excess_value,
        "violation_classes": dict(sorted(classes.items())),
        "results": [asdict(x) | {"proves": next(c.proves for c in CHECKS if c.name == x.check)} for x in results],
    }


def run_all(modes: list[str] | None = None) -> dict:
    modes = list(modes or MODES)
    implementations = [run_implementation(mode) for mode in modes]
    classes: dict[str, dict] = {}
    for impl in implementations:
        for code in impl["violation_classes"]:
            entry = classes.setdefault(code, {"count": 0, "modes": []})
            entry["count"] += 1
            entry["modes"].append(impl["mode"])
    return {
        "meta": {
            "command": "PYTHONPATH=. uv run python -m idemconform.cli run",
            "checks": len(CHECKS),
            "modes": modes,
            "amount_minor": AMOUNT,
            "currency": CURRENCY,
            "lease_seconds": LEASE_SECONDS,
            "ttl_seconds": TTL_SECONDS,
        },
        "implementations": implementations,
        "violations": dict(sorted(classes.items())),
    }


def summary_text(payload: dict) -> str:
    lines = []
    total = payload["meta"]["checks"]
    header = f"{'implementation':<14}{'passed':>10}{'excess value':>16}{'excess charges':>16}"
    lines.append(header)
    lines.append("-" * len(header))
    for impl in payload["implementations"]:
        lines.append(
            f"{impl['mode']:<14}{impl['checks_passed']:>4}/{total:<5}"
            f"{impl['excess_value_minor'] / 100:>15.2f}{impl['excess_charges']:>16}"
        )
    lines.append("")
    failed = [i for i in payload["implementations"] if i["checks_passed"] < total]
    for impl in failed:
        lines.append(f"{impl['mode']}:")
        for result in impl["results"]:
            if not result["passed"]:
                lines.append(f"  FAIL {result['check']:<22}{', '.join(result['violations'])}")
    if not failed:
        lines.append("every implementation passed, which means the suite is not discriminating")
    return "\n".join(lines)


def measure_overhead(n: int = 20_000) -> dict:
    """Amortised microseconds per request, in process, no network."""
    out = {}
    for mode in ("naive", "store_after", "reserve"):
        api = PaymentAPI(mode)
        started = perf_counter()
        for i in range(n):
            api.request(ACCOUNT, f"key-{i}", body(), now=i)
        out[mode] = round(((perf_counter() - started) * 1e6) / n, 2)
    out["overhead_vs_naive_us"] = round(out["reserve"] - out["naive"], 2)
    return {"n": n, "unit": "microseconds per request, amortised, this machine", "modes": out}


if __name__ == "__main__":  # pragma: no cover
    import json

    print(summary_text(run_all()))
    print(json.dumps(measure_overhead(), indent=2))

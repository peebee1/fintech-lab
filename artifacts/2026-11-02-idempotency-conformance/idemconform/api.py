"""A payment intent endpoint, in five idempotency configurations.

`admit` is the decision step and `finish` is the effect. Splitting them is what
makes overlap testable: two callers can both call `admit` before either calls
`finish`, which is exactly the interleaving a retry storm produces in production
and exactly the interleaving a sequential test never reaches.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .ledger import HandlerError, Ledger
from .store import COMMITTED, IN_FLIGHT, JsonFileStore, MemoryStore, Record

LEASE_SECONDS = 30
TTL_SECONDS = 86_400

MODES = ("naive", "global_key", "store_after", "error_cached", "reserve")

MODE_CONFIG: dict[str, dict[str, Any]] = {
    # No key handling at all. The baseline every review starts from.
    "naive": {"writes_store": False, "claims_first": False, "scoped": True, "ttl": 0, "cache_errors": False},
    # Correct reservation, wrong namespace: the key alone identifies the request.
    "global_key": {"writes_store": True, "claims_first": True, "scoped": False, "ttl": TTL_SECONDS, "cache_errors": False},
    # Store the response once the charge succeeds. The common implementation.
    "store_after": {"writes_store": True, "claims_first": False, "scoped": True, "ttl": 0, "cache_errors": False},
    # Reservation, but a processor error is stored as the final answer.
    "error_cached": {"writes_store": True, "claims_first": True, "scoped": True, "ttl": TTL_SECONDS, "cache_errors": True},
    # Reservation before the effect, scoped, with a lease, a TTL, and error release.
    "reserve": {"writes_store": True, "claims_first": True, "scoped": True, "ttl": TTL_SECONDS, "cache_errors": False},
}

PROCEED = "proceed"
REPLAY = "replayed"
CONFLICT = "conflict"
IN_FLIGHT_KIND = "in_flight"
EXPIRED = "expired"
MISSING_KEY = "missing_key"
ERROR = "error"


def normalize(body: dict) -> dict:
    if not isinstance(body, dict):
        raise ValueError("body must be a mapping")
    amount = body.get("amount")
    if not isinstance(amount, int) or isinstance(amount, bool) or amount <= 0:
        raise ValueError("amount must be a positive integer in minor units")
    return {
        "account": str(body.get("account", "")),
        "amount": amount,
        "currency": str(body.get("currency", "")).upper(),
        "customer": str(body.get("customer", "")),
    }


def fingerprint(body: dict) -> str:
    """Identity of the request payload. The account is the namespace, not part of
    the payload, so it is deliberately left out: two tenants sending the same
    amount to the same customer must not compare equal by accident, but they must
    not collide either."""
    payload = normalize(body)
    canonical = json.dumps(
        {k: payload[k] for k in ("amount", "currency", "customer")},
        sort_keys=True, separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class Response:
    status: int
    body: dict
    replayed: bool = False
    executed: bool = False
    reason: str = ""
    retry_after: int | None = None

    def headers(self) -> dict:
        out = {"Idempotent-Replayed": "true"} if self.replayed else {"Idempotent-Replayed": "false"}
        if self.retry_after is not None:
            out["Retry-After"] = str(self.retry_after)
        return out

    def canonical_body(self) -> str:
        return json.dumps(self.body, sort_keys=True, separators=(",", ":"))


@dataclass
class Decision:
    kind: str
    account: str
    key: str
    body: dict
    fingerprint: str
    now: int
    owner: str
    response: Response | None = None


class PaymentAPI:
    def __init__(
        self,
        mode: str = "reserve",
        store: MemoryStore | None = None,
        ledger: Ledger | None = None,
    ) -> None:
        if mode not in MODE_CONFIG:
            raise ValueError(f"unknown mode: {mode}")
        self.mode = mode
        self.config = MODE_CONFIG[mode]
        self.scoped = bool(self.config["scoped"])
        self.ttl = int(self.config["ttl"])
        self.store = store if store is not None else MemoryStore(scoped=self.scoped)
        self.ledger = ledger if ledger is not None else Ledger()

    # ---------------------------------------------------------------- pipeline

    def request(self, account: str, key: str, body: dict, now: int, owner: str = "caller") -> Response:
        decision = self.admit(account, key, body, now, owner)
        return self.finish(decision)

    def admit(self, account: str, key: str, body: dict, now: int, owner: str = "caller") -> Decision:
        normalized = normalize(body)
        fp = fingerprint(normalized)

        if not self.config["writes_store"]:
            return Decision(PROCEED, account, key, normalized, fp, now, owner)

        if not key:
            return Decision(
                MISSING_KEY, account, key, normalized, fp, now, owner,
                Response(400, {"error": "idempotency_key_required"}, reason=MISSING_KEY),
            )

        record = self.store.get(account, key)
        if record is None:
            return self._claim(account, key, normalized, fp, now, owner)

        if record.state == COMMITTED:
            if self.ttl and now > record.created_at + self.ttl:
                return Decision(
                    EXPIRED, account, key, normalized, fp, now, owner,
                    Response(409, {"error": "idempotency_key_expired"}, reason=EXPIRED),
                )
            if record.fingerprint != fp:
                return Decision(
                    CONFLICT, account, key, normalized, fp, now, owner,
                    Response(422, {"error": "idempotency_key_reuse"}, reason=CONFLICT),
                )
            stored = record.response or {"status": 201, "body": {}}
            return Decision(
                REPLAY, account, key, normalized, fp, now, owner,
                Response(stored["status"], dict(stored["body"]), replayed=True, reason=REPLAY),
            )

        # State is IN_FLIGHT. Only a claiming implementation ever gets here.
        if record.fingerprint != fp:
            return Decision(
                CONFLICT, account, key, normalized, fp, now, owner,
                Response(422, {"error": "idempotency_key_reuse"}, reason=CONFLICT),
            )
        if now <= record.lease_until and record.owner != owner:
            return Decision(
                IN_FLIGHT_KIND, account, key, normalized, fp, now, owner,
                Response(
                    409, {"error": "request_in_progress"}, reason=IN_FLIGHT_KIND,
                    retry_after=max(1, record.lease_until - now),
                ),
            )
        # Same owner, or the lease is stale. Ask the ledger whether the effect happened.
        entry = self.ledger.find(self._scope(account), key)
        if entry is not None:
            stored = {"status": 201, "body": entry.as_body()}
            self.store.put(Record(account, key, fp, COMMITTED, record.created_at, 0, owner, stored))
            return Decision(
                REPLAY, account, key, normalized, fp, now, owner,
                Response(201, dict(stored["body"]), replayed=True, reason=REPLAY),
            )
        # Stale claim and no charge: the safe move is to run it under this owner.
        return self._claim(account, key, normalized, fp, now, owner)

    def finish(self, decision: Decision) -> Response:
        if decision.kind != PROCEED:
            assert decision.response is not None
            return decision.response

        try:
            entry = self.ledger.append(
                decision.account, decision.key, decision.body["amount"],
                decision.body["currency"], decision.body["customer"],
            )
        except HandlerError:
            if self.config["writes_store"]:
                if self.config["cache_errors"]:
                    self.store.put(Record(
                        decision.account, decision.key, decision.fingerprint, COMMITTED,
                        decision.now, 0, decision.owner,
                        {"status": 502, "body": {"error": "processor_unavailable"}},
                    ))
                elif self.config["claims_first"]:
                    self.store.delete(decision.account, decision.key)
            return Response(502, {"error": "processor_unavailable"}, reason=ERROR)

        body = entry.as_body()
        if self.config["writes_store"]:
            self.store.put(Record(
                decision.account, decision.key, decision.fingerprint, COMMITTED,
                decision.now, 0, decision.owner, {"status": 201, "body": body},
            ))
        return Response(201, body, executed=True, reason="executed")

    # ------------------------------------------------------------ fault hooks

    def crash_after_effect(self, account: str, key: str, body: dict, now: int, owner: str = "crashed") -> dict:
        """Charge the processor, then die before the response is stored."""
        decision = self.admit(account, key, body, now, owner)
        if decision.kind != PROCEED:
            return {"crashed": False, "decision": decision.kind}
        entry = self.ledger.append(account, key, decision.body["amount"],
                                   decision.body["currency"], decision.body["customer"])
        return {"crashed": True, "charge_id": entry.charge_id}

    def crash_before_effect(self, account: str, key: str, body: dict, now: int, owner: str = "crashed") -> dict:
        """Claim the key, then die before the processor is called."""
        decision = self.admit(account, key, body, now, owner)
        return {"crashed": decision.kind == PROCEED, "decision": decision.kind}

    def reopen(self, ledger: Ledger | None = None) -> "PaymentAPI":
        """A new process on the same durable store and ledger."""
        return PaymentAPI(self.mode, store=self.store.reopen(), ledger=self.ledger if ledger is None else ledger)

    # ---------------------------------------------------------------- helpers

    def _claim(self, account: str, key: str, body: dict, fp: str, now: int, owner: str) -> Decision:
        if self.config["claims_first"]:
            self.store.put(Record(account, key, fp, IN_FLIGHT, now, now + LEASE_SECONDS, owner, None))
        return Decision(PROCEED, account, key, body, fp, now, owner)

    def _scope(self, account: str) -> str | None:
        return account if self.scoped else None


def fresh_file_api(mode: str, path) -> PaymentAPI:
    """A fully durable API: JSON key store plus a JSON ledger, no shared objects."""
    config = MODE_CONFIG[mode]
    path = Path(path)
    return PaymentAPI(
        mode,
        store=JsonFileStore(path, scoped=bool(config["scoped"])),
        ledger=Ledger(Path(str(path) + ".ledger.json")),
    )

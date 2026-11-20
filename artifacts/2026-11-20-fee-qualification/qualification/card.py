"""The rate card: card products, qualification rules, and fee arithmetic.

The model is deliberately small. A transaction is billed at one tier: qualified,
or the single downgrade tier with the largest uplift among the rules it fails.
Real scheme pricing applies one tier per item, not the sum of every failure, and
that precedence is the thing this artifact is about.

Numbers are a synthetic rate card shaped like published US consumer and commercial
card pricing. They are inputs to the model, not quotations from a scheme document.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Product:
    code: str
    label: str
    qualified_bp: int
    qualified_fixed_cents: int
    commercial: bool


PRODUCTS: dict[str, Product] = {
    "consumer_credit": Product("consumer_credit", "consumer credit", 175, 10, False),
    "consumer_debit": Product("consumer_debit", "consumer debit", 75, 15, False),
    "commercial_credit": Product("commercial_credit", "commercial credit", 205, 10, True),
    "prepaid": Product("prepaid", "prepaid", 95, 10, False),
}

PRODUCT_CODES: tuple[str, ...] = tuple(PRODUCTS)


@dataclass(frozen=True)
class Rule:
    """One qualification failure. The uplift is the price of getting it wrong."""

    code: str
    label: str
    uplift_bp: int
    uplift_fixed_cents: int
    fix: str
    effort: int  # 1 is a flag in a request, 5 is a per item integration


# Ordered by uplift, largest first. That order IS the precedence: a transaction
# that fails two rules is billed at the first one it hits.
RULES: tuple[Rule, ...] = (
    Rule("unauthorized", "no authorisation on file", 100, 0, "send the auth record with the batch", 2),
    Rule(
        "commercial_data",
        "commercial card without tax amount and customer code",
        85,
        0,
        "send the Level 2 fields",
        3,
    ),
    Rule("mcc_mismatch", "filed under an MCC outside the registered group", 65, 0, "map each product line to its MCC", 2),
    Rule("avs_cvv", "card not present without an AVS or CVV result", 55, 0, "pass the AVS and CVV results", 4),
    Rule(
        "commercial_l3",
        "commercial card at or above USD 5,000 without line items",
        40,
        0,
        "send Level 3 line items",
        5,
    ),
    Rule(
        "stored_credential",
        "recurring charge without the stored credential indicator",
        25,
        0,
        "flag recurring charges as stored credential",
        1,
    ),
    Rule("late_batch", "settlement file after the daily cut off", 20, 0, "move the batch before the cut off", 2),
)

RULE_CODES: tuple[str, ...] = tuple(r.code for r in RULES)
RULES_BY_CODE: dict[str, Rule] = {r.code: r for r in RULES}
RULE_INDEX: dict[str, int] = {code: i for i, code in enumerate(RULE_CODES)}
QUALIFIED_INDEX: int = len(RULES)
L3_THRESHOLD_CENTS: int = 500_000


def fee_cents(amount_cents: int, product_code: str, tier: str | None) -> int:
    """The fee for one item at one tier. Integer arithmetic, half up rounding."""
    product = PRODUCTS[product_code]
    bp = product.qualified_bp
    fixed = product.qualified_fixed_cents
    if tier is not None:
        rule = RULES_BY_CODE[tier]
        bp += rule.uplift_bp
        fixed += rule.uplift_fixed_cents
    return (amount_cents * bp + 5_000) // 10_000 + fixed


def uplift_bp(tier: str | None) -> int:
    return 0 if tier is None else RULES_BY_CODE[tier].uplift_bp


def cut_cents(amount_cents: int, bp: int) -> int:
    """Saving from taking bp off the rate on one item."""
    return (amount_cents * bp + 5_000) // 10_000

"""Subscription mandate simulator across three rails.

Card recurring, SEPA direct debit, and UPI autopay do not agree about notice,
retries, caps, or how quickly a revocation takes effect. This package models the
disagreement and measures what each scheduler costs.
"""

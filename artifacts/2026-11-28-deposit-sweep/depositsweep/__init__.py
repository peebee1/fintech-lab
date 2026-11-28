"""Deposit sweep: allocating a program book across partner banks."""

from .book import Bank, Book, Customer, generate_book
from .policies import (
    allocate_capped,
    allocate_even,
    allocate_oracle,
    allocate_yield_only,
)

__all__ = [
    "Bank",
    "Book",
    "Customer",
    "generate_book",
    "allocate_yield_only",
    "allocate_capped",
    "allocate_even",
    "allocate_oracle",
]

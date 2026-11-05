"""Request and response shapes. Amounts are exact decimal strings in JSON (D16)."""

from __future__ import annotations

from decimal import Decimal


def amount(value: Decimal) -> str:
    """An amount as the API shows it: two places, never a float."""
    return f"{value.quantize(Decimal('0.01')):f}"

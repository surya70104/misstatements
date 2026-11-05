"""The threshold request (spec section 4 and section 9 ``threshold``; D26, D27).

A person declares overall materiality, performance materiality, the fraction of PM that is
clearly trivial, and the basis. The clearly-trivial amount is computed from the fraction and
recorded beside it, so the documented threshold is the fraction a person declared. There is
no default fraction: the spec says "declared", and no value is invented (pending B4).
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Positive = Annotated[Decimal, Field(gt=0, max_digits=15, decimal_places=2)]
Fraction = Annotated[Decimal, Field(gt=0, lt=1, max_digits=9, decimal_places=8)]
Narration = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]

PAISA = Decimal("0.01")


def ctt_amount(pm: Decimal, fraction: Decimal) -> Decimal:
    """PM times the declared fraction, to the paisa, half up (D27). The fraction itself is
    stored exactly, so nothing is lost by the rounding."""
    return (pm * fraction).quantize(PAISA, rounding=ROUND_HALF_UP)


class ThresholdIn(BaseModel):
    model_config = ConfigDict(extra="forbid")  # an actor or any unknown field is refused (D36)

    om: Positive = Field(description="Overall materiality in rupees, as an exact decimal string")
    pm: Positive = Field(description="Performance materiality in rupees")
    ctt_fraction: Fraction = Field(
        description="The declared fraction of PM below which a misstatement is clearly trivial "
        "(spec section 4), for example 0.05. No default: it must be declared"
    )
    basis: Narration = Field(
        description="How the figures were arrived at: the benchmark, the percentages, the "
        "working paper (SA 320); documented as spec section 4 requires"
    )

    @model_validator(mode="after")
    def _ctt_below_pm(self) -> ThresholdIn:
        if ctt_amount(self.pm, self.ctt_fraction) <= 0:
            raise ValueError(
                "the clearly-trivial amount rounds to nothing; declare a larger fraction"
            )
        return self

    @model_validator(mode="after")
    def _pm_below_om(self) -> ThresholdIn:
        # SA 320 paragraph 9 defines performance materiality as an amount set at less than
        # materiality for the financial statements as a whole: equal is refused too (D34).
        if self.pm >= self.om:
            raise ValueError(
                f"performance materiality ({self.pm:f}) must be below overall materiality "
                f"({self.om:f}): SA 320 paragraph 9 defines it as an amount set at less than "
                "materiality for the financial statements as a whole (architecture D34)"
            )
        return self

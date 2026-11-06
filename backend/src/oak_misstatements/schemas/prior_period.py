"""Requests on the prior-period carry-forward (SA 450 paragraph 11(b); spec section 4.1;
architecture D61). The four effects and their basis are a person's and are mandatory; who
acts is never sent."""

from __future__ import annotations

import uuid
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from oak_misstatements.schemas.misstatements import Amount, Label, Narration

_SIGN = (
    "signed as the schedule signs an effect: what correcting it does to the figure "
    "(negative when correcting lowers it); '0.00' when there is none"
)


class EffectsIn(BaseModel):
    """The four figures a carried item states, and how they were arrived at."""

    model_config = ConfigDict(extra="forbid")  # an actor or a timestamp in the body is refused

    current_profit_before_tax: Amount = Field(
        description=f"Effect on this period's profit before tax; {_SIGN}"
    )
    current_net_assets: Amount = Field(description=f"Effect on this period's net assets; {_SIGN}")
    cumulative_profit_before_tax: Amount = Field(
        description=f"Cumulative effect on profit before tax; {_SIGN}"
    )
    cumulative_net_assets: Amount = Field(description=f"Cumulative effect on net assets; {_SIGN}")
    basis: Narration = Field(
        description="How the current-period and cumulative effects were arrived at. Not blank"
    )


class PriorPeriodIn(EffectsIn):
    """Record a prior-period uncorrected misstatement, entered by hand or rolled forward
    from a misstatement of another engagement of this module."""

    prior_period: Label = Field(description="The period it belongs to, e.g. 'FY 2025-26'")
    description: Narration | None = Field(
        default=None,
        description="What it is. Required unless rolled forward, when the source's is used",
    )
    source_ref: Label | None = Field(
        default=None,
        description=(
            "The prior period's schedule or working paper. Required unless rolled forward, "
            "when the source engagement and reference are used"
        ),
    )
    source_misstatement_id: uuid.UUID | None = Field(
        default=None,
        description=(
            "Roll forward: a misstatement of another engagement, uncorrected there. Its "
            "effects there are copied by the backend, never sent"
        ),
    )

    @model_validator(mode="after")
    def _entered_by_hand_is_described(self) -> Self:
        if self.source_misstatement_id is None and (
            self.description is None or self.source_ref is None
        ):
            raise ValueError(
                "an item entered by hand needs a description and a source reference (the "
                "prior period's schedule or working paper)"
            )
        return self


class PriorPeriodRevisionIn(EffectsIn):
    """Revise a carried item's figures: a new version, the earlier one kept."""


class PriorPeriodRemovalIn(BaseModel):
    """Stop carrying an item forward. The reason is kept with the history."""

    model_config = ConfigDict(extra="forbid")

    reason: Narration = Field(description="Why it is no longer carried forward. Not blank")

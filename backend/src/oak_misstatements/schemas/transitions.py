"""The transition request (spec section 3.3; acceptance 3; D41)."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

# Bounded so the note sent to the Spine with our reference and the actor always fits its
# own 2000-character limit (core/states.py).
Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1500)]


class TransitionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")  # an actor, a date or a role is refused

    to: Literal["communicated", "corrected", "refused", "withdrawn"]
    reason: Reason | None = Field(
        default=None,
        description="Why management refused, or why the item is withdrawn. Mandatory for "
        "both, and not accepted for any other move (spec sections 2 and 3.3)",
    )

    @model_validator(mode="after")
    def _reason_where_the_spec_asks(self) -> TransitionIn:
        if self.to == "refused" and self.reason is None:
            raise ValueError(
                "a refusal needs a reason: SA 450 paragraph 9, no blank refusals (spec "
                "section 2; acceptance 3)"
            )
        if self.to == "withdrawn" and self.reason is None:
            raise ValueError(
                "a withdrawal needs a reason: the item is kept, excluded, with a reason "
                "(spec section 3.3)"
            )
        if self.to in ("communicated", "corrected") and self.reason is not None:
            raise ValueError(
                f"a move to {self.to} records no reason; it would be dropped, so it is refused"
            )
        return self

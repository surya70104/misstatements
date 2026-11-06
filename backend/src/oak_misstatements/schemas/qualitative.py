"""Requests on the qualitative checklist (spec section 5; architecture D59). The reason is
mandatory, for recording a factor and for clearing one, and who acts is never sent."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from oak_misstatements.schemas.misstatements import Narration

Factor = Literal[
    "law_or_covenant",
    "earnings_trend",
    "ratio",
    "fraud",
    "related_party",
    "segment_or_remuneration",
    "loss_to_profit",
]


class QualitativeIn(BaseModel):
    """Record a factor against a misstatement, or record it again with a new reason."""

    model_config = ConfigDict(extra="forbid")  # an actor or a timestamp in the body is refused

    factor: Factor = Field(description="One factor of the checklist of spec section 5")
    note: Narration = Field(
        description="The recorded reason (spec section 5: 'with a recorded reason'). Not blank"
    )


class QualitativeClearIn(BaseModel):
    """Clear a recorded factor. The reason for clearing is kept with the history."""

    model_config = ConfigDict(extra="forbid")

    note: Narration = Field(description="Why the factor no longer applies. Not blank")

"""The soft-gate acknowledgement request (spec section 7; D38, D39)."""

from __future__ import annotations

import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Narration = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class AcknowledgementIn(BaseModel):
    model_config = ConfigDict(extra="forbid")  # a role or an actor in the body is refused

    note: Narration | None = Field(
        default=None,
        description="What the partner wants recorded with the acknowledgement, if anything; "
        "the spec requires the acknowledgement, not a note",
    )


class EvaluationRunIn(BaseModel):
    """An evaluation run (spec section 9; D43). The figures are computed, never sent: any
    other field, an aggregate included, is refused."""

    model_config = ConfigDict(extra="forbid")

    materiality_reassessed: Literal[True] = Field(
        description="SA 450 paragraph 10: materiality is reassessed before uncorrected "
        "misstatements are evaluated. Must be true; if materiality needs revising, set a new "
        "threshold version first"
    )


class ConclusionIn(BaseModel):
    """The conclusion (spec section 6.4; acceptance 10; D45). The words are the partner's;
    the figures are computed and saved with them, never sent."""

    model_config = ConfigDict(extra="forbid")  # a figure, a role or an actor is refused

    conclusion: Narration = Field(
        description="The partner's conclusion, in their words. Cannot be empty (acceptance 10)"
    )
    basis: Narration = Field(
        description="The basis of the conclusion (spec section 6.4). Cannot be empty"
    )
    reviewed_run_id: uuid.UUID = Field(
        description="The evaluation run the partner reviewed. The conclusion is refused if "
        "that run no longer describes the evaluation, so the figures saved are the figures "
        "reviewed"
    )
    materiality_reassessed: Literal[True] = Field(
        description="SA 450 paragraph 10: materiality reassessed before the evaluation"
    )


class StrategyResponseIn(BaseModel):
    """The answer to the strategy prompt (spec section 7: "recorded either way")."""

    model_config = ConfigDict(extra="forbid")

    strategy_revised: bool = Field(
        description="Whether the audit strategy and plan were revised after revisiting them"
    )
    note: Narration | None = Field(default=None, description="What was decided, if recorded")

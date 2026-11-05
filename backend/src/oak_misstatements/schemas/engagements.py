"""Engagement requests (architecture D8)."""

from __future__ import annotations

import uuid
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Label = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class SpineLinkIn(BaseModel):
    """The Spine engagement and, within it, the version this engagement works on. Clearing
    the engagement clears the version."""

    model_config = ConfigDict(extra="forbid")  # an actor or any unknown field is refused (D36)

    spine_engagement_id: uuid.UUID | None = None
    spine_version_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _version_needs_engagement(self) -> SpineLinkIn:
        if self.spine_version_id is not None and self.spine_engagement_id is None:
            raise ValueError("a Spine version needs the Spine engagement it belongs to")
        return self


class EngagementIn(SpineLinkIn):
    label: Label = Field(description="How the firm names the engagement")

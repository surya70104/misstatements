"""Database tables, each registered on ``Base.metadata`` so Alembic sees it.

Stage 1 (spec section 9): ``engagement`` (architecture D8), ``misstatement`` and
``misstatement_version`` (D9, D21). Stage 2: ``threshold`` (D26) and the ``event`` trail
(D13). Stage 4: ``evaluation``, one append-only row per evaluation run (D43). The qualitative
table arrives with Stage 8.
"""

from __future__ import annotations

from oak_misstatements.db import Base
from oak_misstatements.models.engagement import Engagement
from oak_misstatements.models.evaluation import EvaluationRun
from oak_misstatements.models.event import EVENT_KINDS, Event, InvalidEvent
from oak_misstatements.models.line_class import SECTIONS, MisstatementLineClass
from oak_misstatements.models.misstatement import (
    MISSTATEMENT_TYPES,
    RAISED_FROM,
    SPINE_KINDS,
    STATES,
    Misstatement,
    MisstatementVersion,
)
from oak_misstatements.models.threshold import Threshold

# Registers the application-level append-only guard on every session (D42).
from oak_misstatements.models import guard as guard  # isort: skip

__all__ = [
    "EVENT_KINDS",
    "MISSTATEMENT_TYPES",
    "RAISED_FROM",
    "SECTIONS",
    "SPINE_KINDS",
    "STATES",
    "Base",
    "Engagement",
    "EvaluationRun",
    "Event",
    "InvalidEvent",
    "Misstatement",
    "MisstatementLineClass",
    "MisstatementVersion",
    "Threshold",
]

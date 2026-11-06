"""The append-only rule inside the application (spec section 9; architecture D6, D42).

PostgreSQL already refuses any UPDATE, DELETE or TRUNCATE of the record tables for every
role (the trigger function of migration 0001, attached by 0002, 0003 and 0004) and grants
the application role SELECT and INSERT only. This guard is the same rule one layer up, so a
programming mistake is refused before it reaches the database, and is refused on the
in-memory stand-in the tests use, which has no triggers:

- a flush that would UPDATE or DELETE a loaded row of an append-only table raises;
- an ORM ``update()`` or ``delete()`` statement against one raises.

``threshold`` and ``engagement`` are not here: a threshold changes once, in
``superseded_by``, and an engagement changes in its two Spine link columns, each held by
its own database trigger (migrations 0003 and 0006).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Delete, Update, event
from sqlalchemy.orm import ORMExecuteState, Session

from oak_misstatements.models.evaluation import EvaluationRun
from oak_misstatements.models.event import Event
from oak_misstatements.models.line_class import MisstatementLineClass
from oak_misstatements.models.misstatement import Misstatement, MisstatementVersion
from oak_misstatements.models.qualitative import QualitativeFactor

APPEND_ONLY_MODELS: tuple[type[Any], ...] = (
    Misstatement,
    MisstatementVersion,
    MisstatementLineClass,
    Event,
    EvaluationRun,
    QualitativeFactor,
)
APPEND_ONLY_TABLES = frozenset(model.__tablename__ for model in APPEND_ONLY_MODELS)


class AppendOnlyViolation(RuntimeError):
    """The application tried to change or delete a row that is never changed or deleted."""


@event.listens_for(Session, "before_flush")
def _refuse_changes(session: Session, _context: Any, _instances: Any) -> None:
    for instance in session.deleted:
        if isinstance(instance, APPEND_ONLY_MODELS):
            raise AppendOnlyViolation(
                f"{type(instance).__name__} is append-only: a row is never deleted "
                "(spec section 9; architecture D6)"
            )
    for instance in session.dirty:
        if isinstance(instance, APPEND_ONLY_MODELS) and session.is_modified(instance):
            raise AppendOnlyViolation(
                f"{type(instance).__name__} is append-only: a change is a new version, never "
                "an update (spec section 9; architecture D6)"
            )


@event.listens_for(Session, "do_orm_execute")
def _refuse_statements(state: ORMExecuteState) -> None:
    statement = state.statement
    if isinstance(statement, Update | Delete):
        table = getattr(statement.table, "name", None)
        if table in APPEND_ONLY_TABLES:
            raise AppendOnlyViolation(
                f"{table} is append-only: {type(statement).__name__.upper()} is not allowed "
                "(spec section 9; architecture D6)"
            )

"""The intake adapters (spec section 8; architecture D64): one request shape per source,
each asking for exactly what that source attaches, and each turned into the one
``MisstatementIn`` the record is raised from. A source can never arrive without its
attribution: the shape has no way to leave it out."""

from __future__ import annotations

from pydantic import Field

from oak_misstatements.schemas.misstatements import (
    CitationIn,
    Label,
    MisstatementBase,
    MisstatementIn,
    NoteOriginIn,
    RunOriginIn,
)


class WorkingPaperIntakeIn(MisstatementBase):
    """An area tester raises a misstatement with its working paper reference attached."""

    working_paper_ref: Label = Field(description="The working paper that found it")

    def to_misstatement(self) -> MisstatementIn:
        return MisstatementIn(**self.common(), raised_from="wp", source_ref=self.working_paper_ref)


class ManualIntakeIn(MisstatementBase):
    """A manual entry: allowed, and it requires a working paper reference."""

    working_paper_ref: Label = Field(description="The working paper that supports it")

    def to_misstatement(self) -> MisstatementIn:
        return MisstatementIn(
            **self.common(), raised_from="manual", source_ref=self.working_paper_ref
        )


class RunIntakeIn(MisstatementBase):
    """An accepted WorkMind agent run's exception, carrying the run id and the source-row
    citations."""

    run_id: Label
    citations: list[CitationIn] = Field(min_length=1, max_length=500)

    def to_misstatement(self) -> MisstatementIn:
        return MisstatementIn(
            **self.common(),
            raised_from="run",
            run=RunOriginIn(run_id=self.run_id, citations=self.citations),
        )


class NoteIntakeIn(MisstatementBase):
    """A review note a reviewer converts into a misstatement."""

    note_ref: Label
    note_link: str | None = Field(default=None, max_length=500)

    def to_misstatement(self) -> MisstatementIn:
        return MisstatementIn(
            **self.common(),
            raised_from="note",
            note=NoteOriginIn(note_ref=self.note_ref, note_link=self.note_link),
        )

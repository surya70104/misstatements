"""The misstatement request (spec sections 3.1, 3.2, 8, 9; acceptance 1).

A misstatement is double-entry, never a single amount: the lines are required, at least two,
each carrying exactly one side above zero, and they must balance. All of that is checked here
for a clear 422 before anything is read from or written to the Spine, which re-checks it.
A line names a ledger of the Spine version's sealed import by ``line_no`` only, or introduces
a ledger the import lacks by name, parent chain and a mappable Schedule III head, exactly as
the Spine's own ``AdjustmentLineIn`` does (``D:\\CAF\\backend\\src\\oak_spine\\api\\spine.py``).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

ZERO = Decimal("0.00")

Label = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Narration = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
Positive = Annotated[Decimal, Field(gt=0, max_digits=15, decimal_places=2)]
Amount = Annotated[Decimal, Field(max_digits=15, decimal_places=2)]

MisstatementType = Literal["factual", "judgemental", "projected"]
# How a projected misstatement was projected from its sample (SA 530; D65).
SamplingMethod = Literal["ratio", "difference", "mean_per_unit", "monetary_unit", "other"]
Count = Annotated[int, Field(ge=1, le=1_000_000_000)]
# Spec section 8, every source (D25 for the two of Stage 1; D64 for the rest): a working
# paper and a manual entry carry a working paper reference; an agent run carries its run
# id and source-row citations; a review note carries its reference, and a link if it has
# one. Sampling arrives as a projected misstatement from a working paper (spec 3.2).
RaisedFrom = Literal["wp", "run", "note", "manual"]


class LineIn(BaseModel):
    model_config = ConfigDict(extra="forbid")  # an actor or any unknown field is refused (D36)

    line_no: int | None = Field(
        default=None,
        ge=1,
        description="A line of the Spine version's sealed import; its name, chain and key are "
        "the Spine's and must not be sent",
    )
    ledger_name: Label | None = Field(
        default=None, description="For a ledger the import lacks: its name"
    )
    parent_chain: list[Label] | None = Field(
        default=None, max_length=20, description="For a ledger the import lacks: its groups"
    )
    head_id: str | None = Field(
        default=None,
        description="For a ledger the import lacks: a mappable leaf of the Schedule III tree",
    )
    dr: Positive | None = Field(default=None, description="Debit, as an exact decimal string")
    cr: Positive | None = Field(default=None, description="Credit, as an exact decimal string")

    @model_validator(mode="after")
    def _one_side_one_identity(self) -> LineIn:
        if (self.dr is None) == (self.cr is None):
            raise ValueError("a line carries exactly one of dr and cr, above zero")
        if self.line_no is not None:
            if self.ledger_name is not None or self.parent_chain is not None or self.head_id:
                raise ValueError(
                    "a line that names an import ledger by line_no must not also send a name, "
                    "chain or head: the Spine copies those from the sealed import"
                )
        elif not self.ledger_name or not self.head_id:
            raise ValueError(
                "a line gives line_no for an import ledger, or ledger_name and head_id "
                "(with parent_chain) for a ledger the import lacks"
            )
        return self

    def to_spine(self) -> dict[str, Any]:
        """The line as the Spine's propose endpoint takes it."""
        body: dict[str, Any] = {}
        if self.line_no is not None:
            body["line_no"] = self.line_no
        else:
            body["ledger_name"] = self.ledger_name
            body["parent_chain"] = list(self.parent_chain or [])
            body["head_id"] = self.head_id
        if self.dr is not None:
            body["dr"] = f"{self.dr:f}"
        if self.cr is not None:
            body["cr"] = f"{self.cr:f}"
        return body


class CitationIn(BaseModel):
    """One source-row citation of an agent run's exception (spec section 8): where in the
    source the run found it."""

    model_config = ConfigDict(extra="forbid")

    source: Label = Field(description="The source the run read: a file, a table, an import")
    row: Label = Field(description="The row, line or key within it")
    detail: Narration | None = Field(default=None, description="What the run found there")


class RunOriginIn(BaseModel):
    """An accepted WorkMind agent run: its id, and at least one citation."""

    model_config = ConfigDict(extra="forbid")

    run_id: Label
    citations: list[CitationIn] = Field(min_length=1, max_length=500)


class NoteOriginIn(BaseModel):
    """A review note a reviewer converts into a misstatement: its reference, and a link
    to it where the firm's review tool has one."""

    model_config = ConfigDict(extra="forbid")

    note_ref: Label
    note_link: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
        | None
    ) = None


class MisstatementBase(BaseModel):
    """What every misstatement says, whichever source it comes from."""

    model_config = ConfigDict(extra="forbid")  # an actor or any unknown field is refused (D36)

    type: MisstatementType
    description: Narration
    lines: list[LineIn] = Field(min_length=2, max_length=500)
    # Spec 3.2: a judgemental item carries the auditor's point estimate (the lines) and the
    # range (these two); a projected item names its sample and projection basis (D14).
    range_low: Amount | None = None
    range_high: Amount | None = None
    sample_ref: Label | None = None
    projection_basis: Narration | None = None
    # SA 530; spec 3.2 (D65): a projected item says how it was projected. The lines carry
    # the projected amount; ``projected_amount`` is checked against them and not stored.
    sampling_method: SamplingMethod | None = None
    population_value: Positive | None = Field(
        default=None, description="The population's recorded value, in rupees"
    )
    population_size: Count | None = Field(default=None, description="Items in the population")
    sample_value: Amount | None = Field(
        default=None, ge=0, description="The sample's recorded value, in rupees"
    )
    sample_size: Count | None = Field(default=None, description="Items in the sample")
    known_error_in_sample: Amount | None = Field(
        default=None, description="The misstatement found in the sample, in rupees"
    )
    projected_amount: Positive | None = Field(
        default=None,
        description=(
            "The best estimate of misstatement in the population. It must equal the "
            "debits of the lines, which carry it; it is not stored on its own"
        ),
    )

    @model_validator(mode="after")
    def _double_entry(self) -> MisstatementBase:
        debits = sum((line.dr for line in self.lines if line.dr is not None), ZERO)
        credits = sum((line.cr for line in self.lines if line.cr is not None), ZERO)
        if debits != credits:
            raise ValueError(
                f"the Dr/Cr lines must balance: debits {debits:f} differ from credits "
                f"{credits:f} (spec section 3.1; acceptance 1)"
            )
        seen_lines = [line.line_no for line in self.lines if line.line_no is not None]
        if len(seen_lines) != len(set(seen_lines)):
            raise ValueError("the same import ledger appears on more than one line")
        return self

    @model_validator(mode="after")
    def _type_fields(self) -> MisstatementBase:
        has_range = self.range_low is not None or self.range_high is not None
        has_projection = self.sample_ref is not None or self.projection_basis is not None
        if self.type == "judgemental":
            if self.range_low is None or self.range_high is None:
                raise ValueError("a judgemental misstatement carries range_low and range_high")
            if self.range_low > self.range_high:
                raise ValueError("range_low must not exceed range_high")
        elif has_range:
            raise ValueError("only a judgemental misstatement carries a range")
        sampling = {
            "sampling_method": self.sampling_method,
            "population_value": self.population_value,
            "population_size": self.population_size,
            "sample_value": self.sample_value,
            "sample_size": self.sample_size,
            "known_error_in_sample": self.known_error_in_sample,
            "projected_amount": self.projected_amount,
        }
        if self.type == "projected":
            if self.sample_ref is None or self.projection_basis is None:
                raise ValueError(
                    "a projected misstatement names its sample_ref and projection_basis"
                )
            missing = [name for name, value in sampling.items() if value is None]
            if missing:
                raise ValueError(
                    "a projected misstatement says how it was projected (SA 530): "
                    + ", ".join(missing)
                    + " required"
                )
            assert self.population_size is not None and self.sample_size is not None  # noqa: S101
            assert self.population_value is not None and self.sample_value is not None  # noqa: S101
            if self.sample_size > self.population_size:
                raise ValueError("sample_size cannot exceed population_size")
            if self.sample_value > self.population_value:
                raise ValueError("sample_value cannot exceed population_value")
            debits = sum((line.dr for line in self.lines if line.dr is not None), ZERO)
            if self.projected_amount != debits:
                raise ValueError(
                    f"the Dr/Cr lines carry the projected amount: their debits {debits:f} "
                    f"differ from projected_amount {self.projected_amount:f} (spec section "
                    "3.1: a misstatement is its lines, never a separate amount)"
                )
        elif has_projection or any(value is not None for value in sampling.values()):
            raise ValueError(
                "only a projected misstatement names a sample, a projection basis and how "
                "it was projected"
            )
        return self

    def common(self) -> dict[str, Any]:
        """The fields every source shares, for building a ``MisstatementIn``."""
        return {
            "type": self.type,
            "description": self.description,
            "lines": self.lines,
            "range_low": self.range_low,
            "range_high": self.range_high,
            "sample_ref": self.sample_ref,
            "projection_basis": self.projection_basis,
            "sampling_method": self.sampling_method,
            "population_value": self.population_value,
            "population_size": self.population_size,
            "sample_value": self.sample_value,
            "sample_size": self.sample_size,
            "known_error_in_sample": self.known_error_in_sample,
            "projected_amount": self.projected_amount,
        }


class MisstatementIn(MisstatementBase):
    """The misstatement as the general endpoint takes it: the source named, with what that
    source attaches (spec section 8)."""

    raised_from: RaisedFrom
    source_ref: Label | None = Field(
        default=None,
        description="For a working paper or a manual entry: the working paper that found it "
        "(spec section 8), sent to the Spine as working_paper_ref. For a run or a note it is "
        "not sent: the run id or the note reference is the reference",
    )
    run: RunOriginIn | None = Field(default=None, description="With raised_from 'run' only")
    note: NoteOriginIn | None = Field(default=None, description="With raised_from 'note' only")

    @model_validator(mode="after")
    def _source_attribution(self) -> MisstatementIn:
        if self.raised_from in ("wp", "manual"):
            if self.source_ref is None:
                source = "a working paper" if self.raised_from == "wp" else "a manual entry"
                raise ValueError(
                    f"a misstatement raised from {source} needs its working paper reference "
                    "in source_ref (spec section 8)"
                )
            if self.run is not None or self.note is not None:
                raise ValueError("only a run or a note carries run or note details")
        elif self.raised_from == "run":
            if self.run is None:
                raise ValueError(
                    "a misstatement raised from an agent run carries run.run_id and at least "
                    "one source-row citation in run.citations (spec section 8)"
                )
            if self.note is not None or self.source_ref is not None:
                raise ValueError(
                    "a run's reference is its run_id: send run, not source_ref or note"
                )
        else:  # note
            if self.note is None:
                raise ValueError(
                    "a misstatement raised from a review note carries note.note_ref (spec "
                    "section 8)"
                )
            if self.run is not None or self.source_ref is not None:
                raise ValueError(
                    "a note's reference is its note_ref: send note, not source_ref or run"
                )
        return self

    @property
    def reference(self) -> str:
        """What the record and the Spine hold as the reference: the working paper, the run
        id, or the note reference."""
        if self.run is not None:
            return self.run.run_id
        if self.note is not None:
            return self.note.note_ref
        assert self.source_ref is not None  # noqa: S101 - the validator requires it
        return self.source_ref

    def origin(self) -> dict[str, Any] | None:
        """What the source attaches beyond its reference, as the record stores it."""
        if self.run is not None:
            return {
                "run_id": self.run.run_id,
                "citations": [
                    citation.model_dump(exclude_none=True) for citation in self.run.citations
                ],
            }
        if self.note is not None:
            return {"note_ref": self.note.note_ref, "note_link": self.note.note_link}
        return None

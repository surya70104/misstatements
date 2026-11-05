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
# Spec section 8: Stage 1 takes the two sources that carry a working paper reference (D25).
# The agent-run, review-note and Sampling intakes are Pass 2.
RaisedFrom = Literal["wp", "manual"]


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


class MisstatementIn(BaseModel):
    model_config = ConfigDict(extra="forbid")  # an actor or any unknown field is refused (D36)

    type: MisstatementType
    description: Narration
    raised_from: RaisedFrom
    source_ref: Label = Field(
        description="The working paper that found it (spec section 8); sent to the Spine as "
        "working_paper_ref"
    )
    lines: list[LineIn] = Field(min_length=2, max_length=500)
    # Spec 3.2: a judgemental item carries the auditor's point estimate (the lines) and the
    # range (these two); a projected item names its sample and projection basis (D14).
    range_low: Amount | None = None
    range_high: Amount | None = None
    sample_ref: Label | None = None
    projection_basis: Narration | None = None

    @model_validator(mode="after")
    def _double_entry(self) -> MisstatementIn:
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
    def _type_fields(self) -> MisstatementIn:
        has_range = self.range_low is not None or self.range_high is not None
        has_projection = self.sample_ref is not None or self.projection_basis is not None
        if self.type == "judgemental":
            if self.range_low is None or self.range_high is None:
                raise ValueError("a judgemental misstatement carries range_low and range_high")
            if self.range_low > self.range_high:
                raise ValueError("range_low must not exceed range_high")
        elif has_range:
            raise ValueError("only a judgemental misstatement carries a range")
        if self.type == "projected":
            if self.sample_ref is None or self.projection_basis is None:
                raise ValueError(
                    "a projected misstatement names its sample_ref and projection_basis"
                )
        elif has_projection:
            raise ValueError("only a projected misstatement names a sample and projection basis")
        return self

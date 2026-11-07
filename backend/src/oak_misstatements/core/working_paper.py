"""The generated working paper (SA 230; SA 450 paragraph 15; spec section 6 item 5;
architecture D66). Pure: the hash, the documentation check, the Binder delivery shape.

SA 450 paragraph 15 requires the auditor to document the amount below which misstatements
are clearly trivial, all misstatements accumulated and whether they have been corrected, and
the conclusion as to whether uncorrected misstatements are material, individually or in
aggregate, and the basis for it. Spec section 2 says those are "fields, not prose", and
section 6 item 5 that the working paper is "the whole thing, generated into the SA 230
binder, with its cross-references intact".
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Final

MODULE: Final[str] = "misstatements-rollup"
TITLE: Final[str] = "Evaluation of misstatements identified during the audit (SA 450)"
SA_REFS: Final[tuple[str, ...]] = ("SA 450", "SA 230")

WORKING_PAPER_BASIS: Final[str] = (
    "the engagement's whole record, generated from the same reads the screens make: the "
    "engagement and its Financial Spine link; every threshold version, with the reassessment "
    "of materiality recorded at each evaluation run (SA 450 paragraph 10); every "
    "misstatement with its Dr/Cr lines as the Spine holds them, its computed effects and "
    "band, its state trail, where it came from, its qualitative checklist and, for a "
    "projected item, how it was projected; the prior-period items carried forward; the "
    "evaluation with its gates; every evaluation run, the strategy prompt's answers and the "
    "partner's acknowledgements and conclusions; the TCWG extract and the representation "
    "attachment; and the three things SA 450 paragraph 15 requires to be documented, each "
    "checked as present or not (spec section 2: 'as fields, not prose'); an export freezes "
    "this content against the current evaluation run, with a SHA-256 of its canonical JSON, "
    "and is refused until a run records the figures as they stand; no figure is computed "
    "here that the evaluation does not compute (architecture D66)"
)

BINDER_NOT_DELIVERABLE: Final[str] = (
    "the Working Paper Binder's generated-paper intake (POST /api/binders/{binder_id}/"
    "generated-papers) names its sources as materiality, sampling, analytical_review, "
    "workmind and spine, and has no source for this module; the delivery below is in its "
    "shape but is not sent (register W1). The snapshot is registered here meanwhile"
)


def canonical(content: dict[str, Any]) -> str:
    """The one JSON text a content has: keys sorted, no spaces, non-ASCII kept."""
    return json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def content_hash(content: dict[str, Any]) -> str:
    """SHA-256 of the canonical JSON, as hex."""
    return hashlib.sha256(canonical(content).encode("utf-8")).hexdigest()


def without_authorisation(value: Any) -> Any:
    """``value`` with every ``authorisation`` block removed, at any depth: the notice
    depends on how the server is run, not on the engagement, and a frozen paper must hash
    the same wherever it is generated."""
    if isinstance(value, dict):
        return {
            key: without_authorisation(entry)
            for key, entry in value.items()
            if key != "authorisation"
        }
    if isinstance(value, list):
        return [without_authorisation(entry) for entry in value]
    return value


def documentation(
    *,
    threshold: dict[str, Any] | None,
    misstatements: list[dict[str, Any]],
    conclusion: dict[str, Any] | None,
) -> dict[str, Any]:
    """SA 450 paragraph 15, as three checks: each names what is documented, or that it is
    not. ``conclusion`` is the latest concluded run as the API answers it, or None."""
    corrected = [m["ref"] for m in misstatements if m["current"]["state"] == "corrected"]
    withdrawn = [m["ref"] for m in misstatements if m["current"]["state"] == "withdrawn"]
    uncorrected = [
        m["ref"]
        for m in misstatements
        if m["current"]["state"] in ("raised", "communicated", "refused")
    ]
    trivial = {
        "documented": threshold is not None,
        "amount": None if threshold is None else threshold["ctt"],
        "fraction_of_pm": None if threshold is None else threshold["ctt_fraction"],
        "basis": None if threshold is None else threshold["basis"],
        "threshold_version_no": None if threshold is None else threshold["version_no"],
    }
    accumulated = {
        "documented": True,
        "count": len(misstatements),
        "uncorrected": uncorrected,
        "corrected": corrected,
        "withdrawn": withdrawn,
    }
    concluded = {
        "documented": conclusion is not None,
        "determination": None if conclusion is None else conclusion["determination"],
        "conclusion": None if conclusion is None else conclusion["conclusion"],
        "basis": None if conclusion is None else conclusion["basis"],
        "concluded_by": None if conclusion is None else conclusion["concluded_by"],
        "run_no": None if conclusion is None else conclusion["run_no"],
        "status": None if conclusion is None else conclusion["status"],
    }
    return {
        "standard": "SA 450 paragraph 15",
        "clearly_trivial_amount": trivial,
        "misstatements_accumulated_and_whether_corrected": accumulated,
        "conclusion_and_basis": concluded,
        "complete": trivial["documented"] and concluded["documented"],
    }

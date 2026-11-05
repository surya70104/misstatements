"""The one place the Financial Spine's adjustment kind is chosen (architecture D23, D37).

The Spine takes two kinds (``D:\\CAF\\backend\\src\\oak_spine\\api\\spine.py``, ``AdjustmentIn``):
``reclass``, a presentation item, and ``correction``. Its own uncorrected schedule lists an
unaccepted reclass apart and never counts it; an accepted one posts to the chain's ``reclass``
column (``spine/uncorrected.py``, ``spine/chain.py``). Neither kind carries any rule about
which ledgers its lines may touch.

A misstatement with an effect on profit before tax or on net assets is a correction. A
classification-only misstatement, both effects reliably nil (D31), is exactly what the Spine
calls a reclassification, so it is proposed as one and never dressed up as a correction. Its
size on amount is nil on both measures, so its significance is qualitative (spec section 5,
Pass 2); the schedule lists it and shows its gross size beside the nil effects. An item whose
effects cannot be determined gets no kind at all: nothing is written anywhere.
"""

from __future__ import annotations

from typing import Literal

from oak_misstatements.core.effects import Effects
from oak_misstatements.errors import Invalid

SpineKind = Literal["reclass", "correction"]


def spine_kind_for(effects: Effects) -> SpineKind:
    if effects.partial:
        names = ", ".join(effects.unresolved)
        raise Invalid(
            f"ledger(s) whose effect cannot be classified: {names}. A ledger with no Schedule "
            "III head must be mapped in the Financial Spine first; a ledger under share "
            "application money pending allotment (item I(2)) waits for its treatment to be "
            "decided (architecture D31). Neither effect, and so the adjustment kind, can be "
            "determined meanwhile"
        )
    if effects.classification_only:
        return "reclass"
    return "correction"

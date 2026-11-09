"""Seed one demonstration engagement through the module's own API, for a reviewer.

    python scripts/seed_demo.py                         # a new demo engagement
    python scripts/seed_demo.py --engagement-id <id>    # an existing, empty engagement

Every figure and description here is ILLUSTRATIVE DEMO DATA. None is a client's, and none is
a firm policy or an approved accounting treatment.

What it records, in this order, each through the same endpoint a person would use:

- the three thresholds (overall materiality, performance materiality, the clearly-trivial
  fraction), unless the engagement already has them;
- five misstatements: a factual one from an area tester, a judgemental one with its range, a
  projected one with its SA 530 sampling details, one from a WorkMind agent run with its
  citation, and one from a review note;
- their moves: communicated, refused with a reason, corrected;
- one qualitative escalation (a related party) on an item below the clearly-trivial line;
- one prior-period uncorrected item carried forward;
- one evaluation run.

Standard library only, so it runs under any Python 3.11 or later with nothing installed.

**Where it writes.** By default to the isolated preview on http://127.0.0.1:8014
(``python -m tests.preview_server`` in ``backend``, or ``scripts\\run_dev.ps1 demo``), which
runs in one transaction that is never committed: everything seeded there is gone when the
preview stops. Every record of this module is append-only, so a demo seeded through a real
backend can never be removed. Any other address is therefore refused unless
``--allow-persistent`` is given, and only a loopback address is ever accepted.

**The ledgers.** A misstatement is Dr/Cr lines against the Financial Spine's ledgers (spec
section 3.1). The lines below name the import lines of the Spine test double, which is what
the preview runs on. Against another Spine the backend refuses the lines it does not know.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any
from urllib.parse import urlsplit

PREVIEW_URL = "http://127.0.0.1:8014"
LOOPBACK = {"127.0.0.1", "localhost", "::1"}

# The Spine test double's engagement and its open version (backend/tests/fake_spine.py).
SPINE_ENGAGEMENT_ID = "11111111-1111-4111-8111-111111111111"
SPINE_VERSION_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1"

LABEL = "Demo engagement (illustrative data)"
THRESHOLDS = {
    "om": "400000.00",
    "pm": "250000.00",
    "ctt_fraction": "0.05",
    "basis": "DEMO: illustrative thresholds, not a firm policy",
}

# Import lines of the Spine test double.
ALPHA_TRADERS, PROVISION_FOR_EXPENSES, SALES, RENT, SALARIES = 1, 3, 4, 5, 6
ACCUMULATED_DEPRECIATION, DEPRECIATION = 14, 15

# (method, path, body) -> (status, parsed JSON or None)
Call = Callable[[str, str, dict[str, Any] | None], tuple[int, Any]]


class SeedError(Exception):
    """The backend refused a step, or could not be reached."""


def lines(debit: int, credit: int, amount: str) -> list[dict[str, Any]]:
    return [{"line_no": debit, "dr": amount}, {"line_no": credit, "cr": amount}]


def expect(call: Call, method: str, path: str, status: int, body: dict[str, Any] | None) -> Any:
    got, answer = call(method, path, body)
    if got != status:
        detail = answer.get("detail") if isinstance(answer, dict) else answer
        raise SeedError(f"{method} {path} answered {got}, not {status}: {detail}")
    return answer


def http(base_url: str, headers: dict[str, str]) -> Call:
    """Calls over HTTP. ``base_url`` has been checked to be http(s) on a loopback address."""

    def call(method: str, path: str, body: dict[str, Any] | None) -> tuple[int, Any]:
        data = None if body is None else json.dumps(body).encode("utf-8")
        request = urllib.request.Request(  # noqa: S310 - the scheme is checked in main()
            base_url + path,
            data=data,
            method=method,
            headers={"content-type": "application/json", "accept": "application/json", **headers},
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as answer:  # noqa: S310
                return answer.status, _parsed(answer.read())
        except urllib.error.HTTPError as refused:
            return refused.code, _parsed(refused.read())
        except urllib.error.URLError as unreachable:
            raise SeedError(
                f"{base_url} could not be reached ({unreachable.reason}). Start the isolated "
                "preview first: scripts\\run_dev.ps1 demo, or in backend: "
                ".venv\\Scripts\\python.exe -m tests.preview_server --port 8014"
            ) from unreachable

    return call


def _parsed(raw: bytes) -> Any:
    try:
        return json.loads(raw.decode("utf-8"))
    except ValueError:
        return raw.decode("utf-8", errors="replace")[:300]


def engagement(
    call: Call,
    say: Callable[[str], None],
    engagement_id: str | None,
    label: str,
    spine_engagement_id: str,
    spine_version_id: str,
) -> str:
    """The engagement to seed: the one named, which must be empty, or a new one."""
    if engagement_id is None:
        created = expect(
            call,
            "POST",
            "/api/engagements",
            201,
            {
                "label": label,
                "spine_engagement_id": spine_engagement_id,
                "spine_version_id": spine_version_id,
            },
        )
        say(f"engagement created: {created['label']}")
        engagement_id = str(created["id"])
    found = expect(call, "GET", f"/api/engagements/{engagement_id}", 200, None)
    if found["misstatements"]:
        raise SeedError(
            f"engagement {engagement_id} already has {found['misstatements']} misstatement(s); "
            "the demo is seeded into an empty engagement only, and nothing was written"
        )
    if found["current_threshold_id"] is None:
        expect(call, "POST", f"/api/engagements/{engagement_id}/thresholds", 201, THRESHOLDS)
        say("thresholds set: OM 4,00,000; PM 2,50,000; clearly trivial at 5% of PM (12,500)")
    else:
        say("thresholds kept: the engagement already has them")
    return engagement_id


def seed(
    call: Call,
    *,
    engagement_id: str | None = None,
    label: str = LABEL,
    spine_engagement_id: str = SPINE_ENGAGEMENT_ID,
    spine_version_id: str = SPINE_VERSION_ID,
    say: Callable[[str], None] = print,
) -> dict[str, Any]:
    """Record the demo scenario and return what was recorded. Stops at the first refusal."""
    engagement_id = engagement(
        call, say, engagement_id, label, spine_engagement_id, spine_version_id
    )
    base = f"/api/engagements/{engagement_id}"

    def raised(path: str, body: dict[str, Any]) -> str:
        answer = expect(call, "POST", f"{base}/{path}", 201, body)
        say(f"{answer['ref']} raised: {body['description']}")
        return str(answer["id"])

    def move(misstatement_id: str, to: str, reason: str | None = None) -> None:
        body: dict[str, Any] = {"to": to} if reason is None else {"to": to, "reason": reason}
        expect(call, "POST", f"/api/misstatements/{misstatement_id}/transitions", 201, body)

    rent = raised(
        "intake/wp",
        {
            "type": "factual",
            "description": "Rent for March not accrued",
            "working_paper_ref": "E-4.2",
            "lines": lines(RENT, PROVISION_FOR_EXPENSES, "60000.00"),
        },
    )
    depreciation = raised(
        "misstatements",
        {
            "type": "judgemental",
            "description": "Depreciation understated: the useful life of plant looks too long",
            "raised_from": "wp",
            "source_ref": "F-3.4",
            "range_low": "30000.00",
            "range_high": "40000.00",
            "lines": lines(DEPRECIATION, ACCUMULATED_DEPRECIATION, "35000.00"),
        },
    )
    raised(
        "misstatements",
        {
            "type": "projected",
            "description": "Sales cut-off errors projected over the March population",
            "raised_from": "wp",
            "source_ref": "R-5.3",
            "sample_ref": "S-12",
            "projection_basis": "Ratio of error to sample value, applied to the population",
            "sampling_method": "ratio",
            "population_value": "4000000.00",
            "population_size": 1200,
            "sample_value": "400000.00",
            "sample_size": 120,
            "known_error_in_sample": "4000.00",
            "projected_amount": "40000.00",
            "lines": lines(SALES, ALPHA_TRADERS, "40000.00"),
        },
    )
    related = raised(
        "intake/run",
        {
            "type": "factual",
            "description": "Sale to a related party not invoiced",
            "run_id": "RUN-DEMO-0412",
            "citations": [
                {
                    "source": "sales_register_march.csv",
                    "row": "214",
                    "detail": "Delivery note with no invoice raised",
                }
            ],
            "lines": lines(ALPHA_TRADERS, SALES, "3000.00"),
        },
    )
    bonus = raised(
        "intake/note",
        {
            "type": "factual",
            "description": "Bonus for the year not provided",
            "note_ref": "RN-17",
            "lines": lines(SALARIES, PROVISION_FOR_EXPENSES, "45000.00"),
        },
    )

    move(rent, "communicated")
    move(depreciation, "communicated")
    move(depreciation, "refused", "Management considers its estimate of useful life reasonable")
    move(bonus, "communicated")
    move(bonus, "corrected")
    say("moves recorded: two communicated, one refused with its reason, one corrected")

    expect(
        call,
        "POST",
        f"/api/misstatements/{related}/qualitative",
        201,
        {"factor": "related_party", "note": "Sale to a firm owned by a director; see E-12"},
    )
    say("escalated: the related-party sale, below the clearly-trivial line")

    expect(
        call,
        "POST",
        f"{base}/prior-period",
        201,
        {
            "description": "Depreciation on plant understated in the prior year",
            "prior_period": "FY 2024-25",
            "source_ref": "PY schedule M-7",
            "current_profit_before_tax": "0.00",
            "current_net_assets": "-30000.00",
            "cumulative_profit_before_tax": "-30000.00",
            "cumulative_net_assets": "-30000.00",
            "basis": "DEMO: carrying amount still overstated at the year end",
        },
    )
    say("prior-period item carried forward")

    run = expect(call, "POST", f"{base}/evaluation/runs", 201, {"materiality_reassessed": True})
    say(f"evaluation run {run['run_no']} recorded")

    schedule = expect(call, "GET", f"{base}/misstatements", 200, None)
    return {
        "engagement_id": engagement_id,
        "misstatements": len(schedule),
        "run_no": run["run_no"],
    }


def checked_url(raw: str, allow_persistent: bool) -> str:
    """``raw`` without a trailing slash, or SeedError when the script must not write there."""
    url = raw.rstrip("/")
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or parts.hostname not in LOOPBACK:
        raise SeedError(f"{raw!r} is refused: only http(s) on a loopback address is accepted")
    if url != PREVIEW_URL and not allow_persistent:
        raise SeedError(
            f"{raw!r} is not the isolated preview ({PREVIEW_URL}). Records written through a "
            "real backend are append-only and can never be removed. Pass --allow-persistent "
            "if that is what you want"
        )
    return url


def header(raw: str) -> tuple[str, str]:
    name, separator, value = raw.partition(":")
    if not separator or not name.strip() or not value.strip():
        raise argparse.ArgumentTypeError("a header is given as 'Name: value'")
    return name.strip(), value.strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Seed one demonstration engagement through the module's own API."
    )
    parser.add_argument(
        "--engagement-id",
        help="An existing engagement of this module with no misstatements. Without it, a "
        "new demo engagement is created.",
    )
    parser.add_argument(
        "--base-url",
        default=PREVIEW_URL,
        help=f"Where the backend answers (default: the isolated preview, {PREVIEW_URL})",
    )
    parser.add_argument("--label", default=LABEL, help="The label of a new demo engagement")
    parser.add_argument("--spine-engagement-id", default=SPINE_ENGAGEMENT_ID)
    parser.add_argument("--spine-version-id", default=SPINE_VERSION_ID)
    parser.add_argument(
        "--allow-persistent",
        action="store_true",
        help="Write to an address other than the isolated preview. Records are append-only: "
        "what is seeded through a real backend can never be removed.",
    )
    parser.add_argument(
        "--header",
        action="append",
        type=header,
        default=[],
        metavar="'Name: value'",
        help="A request header to send with every call (repeatable)",
    )
    args = parser.parse_args(argv)

    try:
        base_url = checked_url(args.base_url, args.allow_persistent)
        seeded = seed(
            http(base_url, dict(args.header)),
            engagement_id=args.engagement_id,
            label=args.label,
            spine_engagement_id=args.spine_engagement_id,
            spine_version_id=args.spine_version_id,
        )
    except SeedError as failed:
        print(f"Seed stopped: {failed}", file=sys.stderr)
        return 1
    print(
        f"Done: {seeded['misstatements']} misstatements and evaluation run {seeded['run_no']}. "
        f"Open {base_url}/#/engagements/{seeded['engagement_id']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# Closure review — Misstatements Rollup

**How to read this file.** Each numbered section is a record of its own date and is left
as it was written. The current position is in sections 13 to 17: **the Pass 1
implementation is complete, and production acceptance is pending.** Where an earlier
section says otherwise, a note in that section says so. Test counts in each section are
the counts of that section's date. **The latest results** are: backend `pytest` on
PostgreSQL 469 passed, none skipped; on the in-memory stand-in 437 passed, 32 skipped;
`ruff` and `mypy` strict clean on 89 files; frontend `vitest` 319 passed in 18 files, with
`tsc`, `eslint`, `prettier` and the build clean (section 15, and `docs/PASS1_HANDOVER.md`).
Eighteen items are open; `docs/DECISIONS_PENDING.md` lists them.

**5 November 2026, before Stage 6.** A read-only review of everything that stands between
the module as built (Stages 0 to 5) and an honest declaration that it is complete. Sources
read in full: `docs/MISSTATEMENTS_ROLLUP.md` (identical to `D:\MISSTATEMENTS_ROLLUP.md`),
`docs/DECISIONS_PENDING.md`, `docs/architecture.md` (D1 to D45), `README.md`, and the code
where a claim needed checking. Nothing was changed by the review itself: no code, no migration,
no existing document. This file is the only thing it added.

**Updated the same day** after the closure work that followed (architecture D46): rows
resolved since are marked in place, and section 9 records what was done and what the three
investigations found. The work was then committed for the first time, on instruction, as
`0bf54c0d99cc5d3d305436b92352f6d3a2e9d313`; rows that said no commit existed are corrected in place.

Nothing here is an approval. Where a row says "recommend", it is a recommendation for the
named person to accept or reject.

## 1. Where the module stands

| Measure | State |
|---|---|
| Backend tests | 410 passed, 32 skipped after the closure work (388 and 31 at the review). The skipped are every PostgreSQL test |
| PostgreSQL | **Verified on the test database, 5 Nov 2026:** migrations 0001 to 0010 applied to `oak_misstatements_test`; 442 passed, none skipped. The main database is created, empty and unmigrated |
| Financial Spine | Never contacted. Every call runs against a test double built from CAF's source |
| Frontend | Stage 0 shell only at the review. **Since built, 5 Nov 2026 (Stage 6, sections 10 and 11):** nine screens covering the three of spec section 10 and everything they need; tested on the API's own captured answers and used on live rows in an isolated preview; not seen against the live Spine |
| Version control | No commit existed at the review. **First commit made 5 Nov 2026:** `0bf54c0d99cc5d3d305436b92352f6d3a2e9d313`, 122 files, on `master`. No remote is configured and there is no CI |
| Spec acceptance criteria | 8 of 11 implemented and tested on the stand-in; 3 are Pass 2 |
| Pass 1 of the spec | Not complete at the review: the schedule screen was missing. **Since built (section 10).** All seven Pass 1 items now exist at code level; none is verified against the live Spine or run end to end (Stage 7) |
| Pass 2 of the spec | Not started |

## 2. Classification used

- **A** — can be resolved directly from the original specification.
- **B** — can be implemented conservatively without CA or firm approval.
- **C** — needs a decision from the CA, a partner, the firm or the Spine's owner.
- **D** — needs real PostgreSQL or the live Financial Spine.
- **E** — needs a future stage or a module that does not exist yet.

"Blocks" means: can the module honestly be declared complete without it? **Pass 1** blocks
the spec's first pass; **Full** blocks the whole spec; **Go-live** blocks real use even if
the code is complete; **No** blocks nothing.

## 3. Closure matrix — items in the register

| ID | Description | Implemented now | Unresolved | Class | Code change needed | Evidence | Required action | Owner | Blocks |
|---|---|---|---|---|---|---|---|---|---|
| B1 | Withdrawn items in the Spine | Withdrawal refuses the Spine's adjustment with a note saying it was withdrawn, so it can never post (D41) | The Spine has no withdrawn status; its own uncorrected aggregate still counts the item | C | None here. A Spine change if the owner wants one | Spine contract: decision is `accepted` or `refused` only (`D:\CAF` `api/spine.py`) | Spine's owner accepts the documented difference or adds a withdrawn status | Spine's owner | No, if the difference is accepted |
| B2 | Classification-only items | Proposed to the Spine as `reclass`; listed at nil with gross size shown (D37) | "Classification only" is read as nil profit **and** nil net-assets effect; the spec says only "no effect on profit" (3.1) | C | Only if the CA takes the literal reading | Spec 3.1; Spine treats `reclass` as presentation only | CA confirms or corrects the reading | CA | Full (confirmation only) |
| B3 | Banding on which amount | Each effect banded separately, higher band wins (D33) | "Higher band wins" is the lead's conservative reading | C | No | Spec 4.1 "profit and net assets, separately" | CA may refine; no action otherwise | CA | No |
| B4a | Source of OM, PM and CTT | Entered by a person as versioned rows; the Spine's PM recorded and compared, never reconciled; nothing pushed (D35) | Spec section 4 says the lines are "all from Materiality (SA 320)". No Materiality module is linked | C, E | Yes, once the source is decided | Spec line 76; no Materiality module in this project | Firm decides the system of record; Spine's owner consents to any push | Firm, Spine's owner | Full |
| B4b | A firm-standard CTT fraction | No default; the fraction must be declared each time | Whether the firm wants a prefill | C | Optional | Spec line 81 "declared" | Firm decides; nothing needed if not wanted | Firm | No |
| B4c | CTT as a fraction of PM or of OM | Fraction of PM | Listed as a CA question | **A** | No | Spec line 81: "a declared fraction of performance materiality" | **Closed from the spec, 5 Nov 2026.** Register updated | — | No (closed 5 Nov 2026) |
| B5 | The "approaching materiality" band | Mechanism built; `OAK_STRATEGY_TRIGGER_FRACTION` has no default; unset, the trigger is not evaluated (D45) | The band's value; who sets it; whether an unanswered prompt should hold anything up | C | No, a setting | Spec section 7 names no figure | Lead or firm declares the fraction | Lead, firm | Pass 1 (the trigger is inert until set) |
| B6 | Prior-period carry-forward | Not built; no `py_carried` column | Source, whether items carry lines, how the current-period effect is computed | C, E | Yes, Pass 2 | Spec 4.1, acceptance 5 | CA decides; then Stage 9 | CA | Full |
| B7a | Net assets means shareholders' funds | Assets less liabilities from the Spine's tree sections (D31) | Whether that, and not "net worth" under s.2(57), is intended | C | Only if the reading changes | Schedule III Division I structure | CA confirms | CA | Full (confirmation only) |
| B7b | Share application money pending allotment | Treated as unresolved; an entry touching it is **refused** | Its classification | C | Yes, once decided | The Spine's tree places item I(2) outside equity and liabilities | CA decides | CA | Full (such entries cannot be raised today) |
| B7c | No tax effect imputed | Tax counts only when the entry carries tax lines | Confirmation | C | No | Spec 3.1 computes effects from the lines | CA confirms | CA | Full (confirmation only) |
| B8 | Projected amounts in the gates | They count; every aggregate and gate is also shown without them and says when it depends on them (D38) | Whether they should count | C | Only if the CA says they should not | Spec 3.2 "never aggregated as factual without saying so" | CA confirms the policy | CA | Full (confirmation only) |
| B9a | Partner role claim | Enforced and failing closed; unavailable until a trusted proxy presents the claim (D39, D40) | The firm's proxy and identity provider; the partner value | C, D | No | `identity.py`; no role source exists in any environment | Firm wires the proxy; sets `OAK_TRUSTED_PROXIES`, `OAK_AUTH_ROLES_HEADER`, `OAK_PARTNER_ROLE` | Firm | Go-live (no acknowledgement or conclusion can be saved until then) |
| B9b | Who may raise, move, set thresholds, record runs | Any authenticated identity; every answer says no general role model is enforced | The firm's policy | C | Yes, if the firm wants roles | Spec defines no roles for these | Firm decides | Firm | Go-live, if the firm requires it |
| B10a | Conclusion on an unlocked Spine version | Allowed; lock state recorded on the row; stale if anything changes (D45) | Whether it should be allowed | C | Possibly a refusal | Spec is silent | Lead decides | Lead | No |
| B10b | Re-pointing an engagement to a successor Spine version | **Refused** once any misstatement exists | How records follow a successor version | C | Yes | Spine: a locked version takes nothing, and unlocking creates a successor | Lead and Spine's owner decide. **Investigated 5 Nov 2026:** a deterministic design exists (section 9); not built | Lead, Spine's owner | **Go-live** |
| B10c | Pinned version chosen here or inherited from the Binder | Chosen here | Whether the Binder should supply it | C, E | Possibly | No Binder integration exists | Lead decides | Lead | No |
| B11 | Band boundaries | Spec's literal wording (D33) | None here. The Spine's own gate is strictly above PM | Closed | No | Spec lines 81 to 83, 139, 141 | None | — | No |
| B12 | Refusal reason categories | Free text, mandatory, not blank | Whether categories are wanted | **A** | No | Spec line 30: "A refusal reason is mandatory. No blank refusals." No categories are mentioned | **Closed from the spec, 5 Nov 2026.** Register updated | — | No (closed 5 Nov 2026) |
| B13 | PM below OM | Enforced at the request and by a database CHECK (D34) | None | Closed | No | SA 320 paragraph 9 | None | — | No |
| B14 | Meaning of "material individually" | Not decided; both lists shown and stored (above PM; at or above OM) | Which test the spec's "individually material" is | C | Possibly, in Pass 2 outputs | Spec section 4 band, acceptance 9 | CA decides before the TCWG extract is built | CA | Full |
| B15a | A material conclusion may be saved while the hard gate fires | Yes; a not-material conclusion is blocked by every gate (D45) | Confirmation of the reading | C | Only if rejected | Spec line 139: the hard gate blocks an unmodified opinion; paragraph 15 requires the conclusion documented | CA and lead confirm | CA, lead | Full (confirmation only) |
| B15b | The partner must name the run reviewed | Required; refused when stale | Confirmation; the spec does not ask for it in so many words | C | Only if rejected | Acceptance 10 "carries the figures it was based on" | Lead confirms | Lead | No |
| F3 | Which states are uncorrected | Raised, communicated, refused | CA confirmation | C | Only if rejected | Spec 3.3: refused goes to the uncorrected schedule; withdrawn is excluded | CA confirms | CA | Full (confirmation only) |
| F4 | Withdrawal only after communication | Built on the diagram | Whether a raised-in-error item may leave earlier | **A**, with a consequence | No, unless the lead wants an earlier exit | Spec 3.3 diagram draws withdrawn from communicated only | **Closed from the spec, 5 Nov 2026.** Consequence recorded in the register and in section 9 | Lead, only if an earlier exit is wanted | No (closed 5 Nov 2026) |
| F5 | Escalated items below CTT | Not built | CA confirmation of the reading | C, E | Yes, Pass 2 | Spec section 5 | Stage 8 | CA | Full |
| F9 | Edits after raising | None. The database already allows a new version in the same open state | What may change, and how an amount change is represented in the Spine | C | Yes | Spec line 185 "a change creates a new version"; the Spine's lines cannot be changed | Lead and Spine's owner decide. **Investigated 5 Nov 2026:** interim workflow recorded (section 9) | Lead, Spine's owner | Go-live (a typing error in a description cannot be corrected in place) |
| O1 | Proxy, identity provider, TLS | `OAK_AUTH=dev` in development; production refuses it | The deployment | C, D | No | `config.py` production guard | Firm deploys | Firm | Go-live |
| O2 | Creating the databases and applying migrations | Scripts exist; never run | Everything PostgreSQL | D | Unknown until run | 31 skipped tests | A person runs `scripts\db\02_create.sql` and the migrations on the test database | Firm | Pass 1 |

## 4. Closure matrix — items not in the register

These were found by this review. None is in `DECISIONS_PENDING.md` yet.

| ID | Description | Implemented now | Unresolved | Class | Code change needed | Evidence | Required action | Owner | Blocks |
|---|---|---|---|---|---|---|---|---|---|
| N1 | **Gate exposure, approved as D18 (T12), was not built as approved** | One endpoint, `GET /api/engagements/{id}/evaluation`, carries the gates and the sign-off decision | D18 approved "two read-only endpoints, one for the opinion gate and one for the sign-off block, returning open, blocked or undetermined with the figures" | **B** | Yes, small: two thin read-only endpoints over the existing computation | `docs/architecture.md` D18; route list | **Built 5 Nov 2026 (D46):** `GET .../gates/opinion` and `GET .../gates/sign-off` | — | No (closed 5 Nov 2026) |
| N2 | D20 no longer describes practice | D20 says nothing that depends on a pending decision is implemented until answered | Interim treatments of B1, B2, B8, B14, B15 were built on instruction, each labelled | **A** | No; a documentation correction | D20 against D37, D38, D41, D45 | **Done 5 Nov 2026:** D20 amended | — | No (closed 5 Nov 2026) |
| N3 | The register's header and its Stage 1 table are stale | Header says "updated at the start of Stage 1"; the B7 row says acceptance 4 "is still not claimed" while later sections cite acceptance 4 tests | The two statements disagree | **A** | No; documentation | `DECISIONS_PENDING.md` lines 3 and 15; README Stage 4 section | **Done 5 Nov 2026:** register header and acceptance 4 wording corrected | — | No (closed 5 Nov 2026) |
| N4 | Nothing is committed, and there is no CI | The git repository has no commits; every file is untracked; no pipeline exists | The work has no history and no automatic check | **B** | No | `git log`: "does not have any commits yet" | **Done 5 Nov 2026:** first commit `0bf54c0` (`0bf54c0d99cc5d3d305436b92352f6d3a2e9d313`), 122 files. Still open: no remote and no CI | Firm, for a remote and CI | No (the commit is made) |
| N5 | Python dependencies are not locked | `pyproject.toml` gives lower bounds only; the test client warns that its use of `httpx` is deprecated | Reproducible installs; one deprecation | **B** | Small | `backend/pyproject.toml`; pytest warning | **Done 5 Nov 2026:** `backend/requirements-lock.txt`. The `httpx` deprecation in the test client remains | Developer, for the deprecation | No |
| N6 | Reads need no identity, and there is no per-engagement access | Every GET answers anyone who can reach the API; any authenticated identity may act on any engagement | Confidentiality rests entirely on the proxy | C | Yes, if the firm wants it | D36 "Reads need none" | Firm decides, with B9b and O1 | Firm | Go-live |
| N7 | The Spine does not know who acted here | The Spine records its own service identity as `proposed_by` and `decided_by`; our actor travels in the note | Attribution inside the Spine; whether the Spine checks the caller | C | None here | `D:\CAF` `api/spine.py` lines 387 and 424 | Spine's owner decides | Spine's owner | No |
| N8 | Two gates can disagree | The Spine's own uncorrected gate sums gross debit totals, fires strictly above PM, counts withdrawn items and ignores reclassifications; this module's gate differs on all four | Which gate anyone relies on | C | None here | `D:\CAF` `spine/uncorrected.py`; B1, B11 | Spine's owner and lead agree which is authoritative | Spine's owner, lead | No, if documented as accepted |
| N9 | Orphan proposals have no report | If the commit fails while raising, the Spine keeps a proposal no record points to; it is named in the error and the log (D22, D42) | No way to list such orphans afterwards | **B** | Yes, small: a read-only reconciliation listing | D22, D42 | **Built 5 Nov 2026 (D46):** `GET .../spine-reconciliation`, read-only | — | No (closed 5 Nov 2026) |
| N10 | The communication date is the moment of recording | `communicated_at` is the server's clock; no date can be entered | Whether the actual date of communication should be recordable | **A**, with a note | No | Spec line 29: "a communication state per misstatement, with the date" | **Closed as meeting the spec, 5 Nov 2026** | Lead, only if an entered date is wanted | No (closed 5 Nov 2026) |
| N11 | Event kinds are not checked | The `event` table accepts any non-blank kind; payloads are built by the services, not validated | D13 approved "a JSON payload validated per kind" | **B** | Yes, small | D13; `models/event.py` | **Built 5 Nov 2026 (D46):** CHECK on the kind (migration 0010) and a payload check before insert | — | No (closed 5 Nov 2026) |
| N12 | Lists are not filterable or paged | `GET .../misstatements` returns every item | Spec 10.1 wants the schedule filterable by band, type and state | E | Stage 6 | Spec line 191 | Decide in Stage 6 whether to filter in the browser or the API | Developer | Pass 1, with Stage 6 |
| N13 | Stage 4 runs that conclude nothing | Recorded by any authenticated identity (D43, D44) | The spec's row has `concluded_by` as its only actor | C | No, unless the firm wants only concluded rows | Spec lines 180 to 182 | Lead confirms or asks for the run route to be withdrawn | Lead | No |
| N14 | "The conclusion must address both" gross and net | Both are saved on the conclusion's row | The words are the partner's and are not checked | **A** | No | Spec lines 91 to 92; section 12 | **Closed as meeting the spec, 5 Nov 2026** | — | No (closed 5 Nov 2026) |
| N15 | Judgemental range is not compared with the point estimate | Only low not above high is checked | The spec states no rule | **A** | No | Spec 3.2 | **Closed: the spec states no rule** | — | No (closed 5 Nov 2026) |
| N16 | Sample reference is free text | A projected item names any `sample_ref` | No Sampling module to check it against | E | Pass 2 | Spec section 8 | Pass 2 intake | — | Full |

## 5. Verification that only real systems can give

| ID | Item | What is unverified | Blocks |
|---|---|---|---|
| V1 | Migrations 0001 to 0009 | Whether they apply at all. The PL/pgSQL of 0001, 0003, 0006, 0007, 0008 and 0009 has never executed | Pass 1 |
| V2 | The 31 skipped database tests | Append-only triggers, grants, the money domain, the CTT and PM-below-OM CHECKs, the supersede-once trigger and deferred key, the state-machine trigger, the evaluation threshold trigger, the hard-gate trigger, the conclusion CHECKs | Pass 1 |
| V3 | Row locks | The engagement lock that serialises raises, moves, runs and conclusions. The stand-in ignores it. Whether the application role may take it with only column-level update rights | Pass 1 |
| V4 | Exact money and time | The stand-in stores decimals as floating point and timestamps without zone; exactness is proven only in Python | Pass 1 |
| V5 | Live Spine reads | The shapes of the engagement, version, balances, adjustments and Schedule III tree answers, including each head's item reference that section classification depends on | Pass 1 |
| V6 | Live Spine writes | Propose, and decide once; the 409 for a second decision and for a locked version; acceptance 11 against the real adjusted trial balance | Pass 1 |
| V7 | Failure paths | A commit failing after the Spine decided; an orphan proposal; behaviour under real latency and timeouts | Go-live |
| V8 | Stage 7 acceptance run | Criteria 1, 2, 3, 4, 6, 7, 10 and 11 exercised end to end on PostgreSQL and the Spine | Pass 1 |

## 6. Specification against Features 1 to 5

### Acceptance criteria

| # | Criterion | State |
|---|---|---|
| 1 | Dr/Cr lines required and balanced | Implemented and tested |
| 2 | Changing materiality recomputes every band and records it | Implemented and tested |
| 3 | A refusal without a reason is rejected | Implemented and tested, request and database CHECK |
| 4 | Aggregate gross and net, profit and net assets | Implemented and tested in the API; net assets rests on B7. **Shown since Stage 6** at the top of the schedule and on the evaluation screen (section 10) |
| 5 | Prior-period items, current and cumulative | Not built (Pass 2, B6) |
| 6 | An item above PM blocks sign-off | Implemented and tested |
| 7 | Aggregate at or above OM blocks an unmodified opinion | Implemented as a gate on the not-material conclusion and a database trigger; no Opinion module exists to block |
| 8 | A qualitative escalation lists the item individually | Not built (Pass 2) |
| 9 | The TCWG extract names every individually material item | Not built (Pass 2, B14) |
| 10 | The conclusion cannot be saved empty and carries its figures | Implemented and tested |
| 11 | A corrected item posts to the Spine; an uncorrected one does not | Implemented and tested against the double only |

### Requirement by section

| Spec | Requirement | State |
|---|---|---|
| 1 | No store of amounts; the Spine holds the lines | Met; pinned by tests |
| 1 | "Carried into the opinion" | Not met: no Opinion module exists |
| 2, para 5 | Clearly-trivial threshold per engagement, documented | Met for the threshold only: it is declared per engagement, versioned, kept with its basis and shown. *Corrected 5 Nov 2026: this row read "Met" and was taken to cover the whole paragraph; see the next row* |
| 2, para 5; 4 | "Everything above it accumulates"; below CTT, "not accumulated" | Not met at the review (S14). **Met since 5 Nov 2026 (D53):** a clearly trivial item is named and left out of every aggregate figure and gate, and stays in the schedule. Since D57 items that together reach the threshold are accumulated. Of the nine questions the spec does not answer, one (how "in aggregate" is measured) is still with the CA |
| 2, para 6 | Live aggregate against OM with a warning band | Aggregate met; band not set (B5) |
| 2, para 8 | Communication state with the date | Met (N10) |
| 2, para 9 | Refusal reason mandatory | Met |
| 2, para 10 | Prompt at evaluation; bands recompute | Met |
| 2, para 11 | Both tests shown; prior-period carried forward | Tests met (B14 open); prior period not built |
| 2, para 12 | TCWG extract | Not built (Pass 2) |
| 2, para 14 | Representation attachment | Not built (Pass 2) |
| 2, para 15 | The four items as fields | Met |
| 3.1 | Double entry; four computed effects | Met (B2, B7 readings) |
| 3.2 | Three types kept apart | Met (B8 reading) |
| 3.3 | State machine; nothing deleted | Met (B1 interim) |
| 4 | Lines "all from Materiality (SA 320)" | Not met as written: entered by hand (B4a) |
| 4 | Computed bands, never chosen | Met |
| 4.1 | Gross and net; profit and net assets | Met |
| 4.1 | Prior-period carry-forward | Not built |
| 5 | Qualitative checklist and escalation | Not built (Pass 2) |
| 6.1 | Summary of Audit Differences | Data available from the API. **The schedule screen shows all ten fields since Stage 6**; no document is generated (Pass 2) |
| 6.2, 6.3, 6.5 | TCWG extract, representation attachment, binder working paper | Not built (Pass 2) |
| 6.4 | The conclusion | Met |
| 7 | Hard gate; soft gate as a setting; individually significant; write path | Met |
| 7 | "The Opinion module is blocked, with the figure shown" | Gate exposed; nothing to block; N1 |
| 7 | Strategy trigger, recorded either way | Mechanism met; inert until B5 |
| 8 | Area tester and manual sources | Met |
| 8 | WorkMind runs, review notes, Sampling | Not built (Pass 2). The API refuses those sources; the database allows them |
| 9 | `threshold`, `misstatement`, `evaluation` | Met, except `py_carried` |
| 9 | `qualitative` | Not built |
| 10 | Three screens | Not built at the review. **Built in Stage 6 (section 10)**, without the Pass 2 parts: the qualitative checklist and the prior-period view. The conclusion is shown and not recorded from the screen |
| 11 | Pass 1 | Six of seven items built at the review. **The seventh, the schedule screen, is built (section 10)** |
| 11 | Pass 2 | Not started |

### What earlier reports overlooked

1. **D18 was approved and not built as approved** (N1). Earlier reports said the gate was exposed without noting that two dedicated endpoints had been agreed.
2. **Nothing is committed** (N4). Every stage report ended with "nothing is committed"; none said that the repository has no commit at all. *Since corrected: the first commit, `0bf54c0`, was made on 5 Nov 2026.*
3. **Spec section 4 says the lines come from Materiality.** Earlier reports described manual entry as the interim under B4 without stating plainly that this departs from the spec's wording.
4. **An engagement cannot follow the Spine to a successor version** (B10b). The Spine refuses everything on a locked version and creates a successor when unlocked. This module refuses to re-point once a misstatement exists. So once a version is locked and superseded, nothing further can be raised for that engagement. This was recorded as a pending decision, not as the operational dead end it is. *Corrected after investigation (section 9):* the Spine will not lock a version while any adjustment is proposed, so at the lock every misstatement is already final and nothing is left to decide; the dead end is for raising anything new after an unlock.
5. **A description cannot be corrected and an item raised in error must be communicated before it can be withdrawn** (F9 with F4). Each was recorded separately; together they mean a simple mistake cannot be fixed quietly.
6. **Event kinds and payloads are not validated** (N11), which D13 had approved.
7. **Acceptance 4 is claimed in one document and withheld in another** (N3).
8. **Reads are open and access is not scoped to an engagement** (N6). Recorded as "reads need none" without calling it a go-live concern.
9. **Documenting the clearly-trivial threshold was reported as meeting paragraph 5; applying it was never checked** (S14, found 5 Nov 2026 after the closure work). The paragraph asks for two things. The first is a threshold: declared per engagement and documented. That was built (D27, D35) and is what "Met" described. The second is the accumulation rule the threshold exists for: what is below it is not accumulated (section 4, line 81) and "everything above it accumulates" (section 2, line 27). That was not applied: `aggregate()` in `core/gates.py` summed every uncorrected item whatever its band (D38), so the rows above for sections 4.1, 7 and 6.4, and acceptance 4, 6, 7 and 10, were each true of an aggregate that included the clearly trivial items. The error overstated the aggregate and never understated it. *Corrected the same day (D53; section 12):* the rule is applied, in the backend, and those rows are now true of the aggregate section 4 describes. What the spec does not answer is in `docs/DECISIONS_PENDING.md` under S14, with the CA.

## 7. What can be closed without anyone's approval

Recommended at the review. All were then done; section 9 records each, and the first commit is `0bf54c0`:

| Item | Resolution |
|---|---|
| B4c | Close from the spec: CTT is a fraction of PM |
| B12 | Close from the spec: a mandatory free-text reason is what it asks for |
| F4 | Close from the spec's diagram, recording the consequence for the lead |
| N2, N3 | Correct D20, the register's header and the acceptance 4 wording |
| N1 | Build the two read-only gate endpoints D18 approved |
| N11 | Add a CHECK on the event kind in a new migration |
| N9 | Add a read-only orphan-proposal report |
| N5 | Pin the Python dependencies |
| N4 | Make the first commit, on your instruction. *Done: `0bf54c0`* |
| New rows | Add N1 to N16 and V1 to V8 to `DECISIONS_PENDING.md` so the register is complete |

## 8. What remains before the module can be declared complete

In order of dependency:

1. **First commit** of the work so far. *Done 5 Nov 2026: `0bf54c0d99cc5d3d305436b92352f6d3a2e9d313`.*
2. **PostgreSQL**: create the databases, apply migrations 0001 to 0010 to the test database, run the 32 skipped tests, fix whatever they find.
3. **The small code items** of section 7. *Done 5 Nov 2026, see section 9.*
4. **Stage 6**: the three screens. Without the schedule screen, Pass 1 of the spec is not done. *Built 5 Nov 2026, see section 10; what the screens leave out is listed there.*
5. **Live Spine verification**, then the **Stage 7 acceptance run**.
6. **CA confirmations**: B2, B7a to B7c, B8, B14, B15a, F3. Code is complete for each; none is approved.
7. **Lead and Spine's owner**: B1, B5, B10a to B10c, B15b, F9, N7, N8, N13.
8. **Firm**: the proxy and partner role claim (B9a, O1), the role policy (B9b, N6), the source of materiality (B4a).
9. **Pass 2**: qualitative factors (acceptance 8), prior period (acceptance 5, B6), the TCWG extract (acceptance 9), the representation attachment, the intake hooks, Sampling, the binder paper.
10. **An Opinion module**, which does not exist, before "carried into the opinion" can be met.

**Honest summary.** Stages 0 to 5 are complete at code level and tested on stand-ins. The
module is not complete: one Pass 1 deliverable is missing, all of Pass 2 is unbuilt, nothing
has run on PostgreSQL or against the Spine, eight accounting readings await the CA, and no
partner action can be performed in any environment until the firm's identity provider is
wired.

## 9. Closure work and investigations — 5 November 2026

Done after the review, on instruction. Nothing here is an approval by anyone.

### Resolved

| Item | How |
|---|---|
| N1 | Built the two read-only gate endpoints D18 approved: `GET /api/engagements/{id}/gates/opinion` and `.../gates/sign-off`, each `open`, `blocked` or `undetermined` with the figures |
| N11 | Migration 0010 holds the event kind to the five the module writes; the payload of each kind is checked before insert, as D13 approved |
| N9 | Built `GET /api/engagements/{id}/spine-reconciliation`: orphans, missing adjustments, disputed states, duplicated references. Read-only |
| N5 | Added `backend/requirements-lock.txt`, the exact versions the suite passes on |
| N2, N3 | Amended D20; corrected the register's header and its acceptance 4 wording |
| B4c, B12, F4 | Closed from the specification's own words |
| N10, N14, N15 | Found to meet the specification as built |
| Register | N1 to N17 and V1 to V8 added to `DECISIONS_PENDING.md` |

### Investigated, and what was found

**Successor Spine versions (B10b).** From `D:\CAF\backend\src\oak_spine\spine\lock.py`:

- A version cannot be locked while any adjustment on it is still proposed.
- Unlocking inserts exactly one successor version and copies every adjustment to it. Each
  copy is inserted proposed, given the original's lines verbatim, then decided as the
  original was, and carries `copied_from_id`, the same `finding_ref`, kind and status.
- So a record here can be followed to its copy without guessing: the copy is the one
  adjustment on the successor whose `copied_from_id` is the record's adjustment.

Not built, because three things are not this module's to settle: whether an engagement may
be re-pointed at all (the lead); where the copy's id is recorded, since the link on a final
version cannot be rewritten and the Spine lists one version's adjustments at a time (a small
append-only link table would do it); and whether the live Spine behaves as its source reads.
**It remains a go-live blocker:** after an unlock nothing new can be raised.

**Entering and changing lines (F9).** Lines are entered when a misstatement is raised, with
a working paper reference, for the two sources built; that matches spec section 8. They
cannot be changed afterwards, here or in the Spine: the Spine's API only proposes and
decides, and its database refuses a line once the adjustment is decided and deletes nothing.
An amount changes only by a new adjustment with the old one refused. The interim workflow
is therefore: communicate, withdraw with the reason, raise again. An in-place edit of a
description or of lines stays open for the lead.

**Withdrawal (F4).** The Spine would accept the refusal of any proposed adjustment, so an
earlier withdrawal is technically possible. The specification's diagram draws it from
communicated only. Built as drawn and closed on that basis.

**A consequence found on the way (N17).** Since the Spine will not lock a version with a
proposed adjustment, every misstatement must reach a final state, and every orphan proposal
must be refused in the Spine, before the Spine version can be locked. The reconciliation
report is how an orphan is found.

### Still open after the closure work

| Needs | Items |
|---|---|
| The CA | B2, B7a, B7b, B7c, B8, B14, B15a, F3; and B6, F5 for Pass 2 |
| The lead or the Spine's owner | B1, B5, B10a, B10b, B10c, B15b, F9, N7, N8, N13, N17 |
| The firm | B4a, B4b, B9a, B9b, O1, O2, N6 |
| You | Nothing outstanding: the first commit is made (N4). A remote and CI remain the firm's choice |
| PostgreSQL or the live Spine | V1 to V8 |
| A later stage or module | Stage 6 (N12), Stage 7, Pass 2 (N16), an Opinion module. *Stage 6 is since built and N12 closed; section 10 adds S1 to S12 and V9 to V11* |

## 10. Stage 6 review — 5 November 2026

A review of the complete specification against the screens and the API, made after the
four parts of Stage 6 were built (architecture D47 to D51). Nothing in the backend was
changed by Stage 6: no route, model, migration or rule. One backend file was added, a test
that produces the frontend's fixtures from the real API. Nothing is committed.

### What exists

| Screen | Address | Reads | Writes |
|---|---|---|---|
| Engagement list | `#/` | `GET /api/engagements` | none |
| Schedule (spec 10.1) | `#/engagements/{id}` | the engagement, its misstatements, its evaluation | none |
| Misstatement detail (spec 10.2) | `#/misstatements/{id}` | the misstatement with its versions | a move: `POST .../transitions` |
| Evaluation (spec 10.3) | `#/engagements/{id}/evaluation` | the engagement, the evaluation, the runs, the conclusions, the two gates | a run: `POST .../evaluation/runs`; the strategy answer: `POST .../evaluation/strategy-responses` |

The screens use 13 of the API's 26 routes. Every figure, band, state, gate and reason shown
is the backend's. The only arithmetic on a screen is the percentage of a line, exact and
done with integers (D16, D48).

### Specification against the screens

| Spec | Requirement | State on the screens |
|---|---|---|
| 3.1 | Dr/Cr lines; effect on profit, on net assets, per caption; classification only | Shown on the schedule and the detail, with the backend's explanation of each figure |
| 3.2 | Three types kept apart; projected never counted as factual without saying so | Shown; the totals name the projected items and give every figure without them |
| 3.3 | One record, a state machine; nothing deleted | The detail offers the moves the diagram draws and no others; every version is listed; nothing can be edited |
| 2, para 9 | Refusal reason mandatory | The screen will not send a refusal or a withdrawal without one; the backend refuses it too |
| 4 | Three lines; band computed, never chosen | CTT, PM and OM shown with the threshold version; no screen sets a band |
| 4 | "The threshold itself is documented" | **Not on a screen**: the fraction, basis, who set it and the history are API-only (S1) |
| 4, acceptance 2 | A revision recomputes every band and records that it did | Bands are read afresh on every screen; **the recorded recompute is API-only** (S1) |
| 4.1 | Gross and net; profit and net assets | Shown on the schedule and the evaluation |
| 4.1 | Prior-period items, current and cumulative | Not built (Pass 2) |
| 5 | Qualitative checklist | Not built (Pass 2); not shown on the detail |
| 6.1 | The ten fields of the schedule | All ten shown |
| 6.4 | The conclusion, mandatory, with its figures | **Shown, with what blocks it; not recorded from a screen** (S3) |
| 7 | Hard gate, soft gate, strategy trigger, individually significant | All shown with the backend's status and reasons; the strategy answer can be recorded |
| 7 | Soft gate: a required partner acknowledgement | **Shown as required; not recorded from a screen** (S3) |
| 7 | Blocking is in the write path, not the interface | Held: the screens decide nothing, and a test gives a screen figures at the line with gates that name nothing, and nothing is marked |
| 8 | Where misstatements come from | **No screen raises one** (S2) |
| 10.1 | Filterable by band, type and state | Built, in the browser (N12 closed) |
| 10.1 | Running totals against CTT, PM and OM, in rupees and as a percentage, always visible | Built; pinned from tablet width, not on a phone (S7); they do not follow the filters (S5) |
| 10.2 | Lines, effects, state trail, the working paper it came from | Built; the working paper is shown as its reference, which is all the module holds |
| 10.3 | Gross and net, profit and net assets, gate status | Built |
| 10.3 | Current and cumulative with prior-period items | Not built (Pass 2) |
| 10.3 | The conclusion field | Shown, not recorded (S3) |

### The five backend features through the screens

| Feature | Read | Write |
|---|---|---|
| 1 The misstatement record | Yes: schedule and detail | **No**: raising one is API-only (S2) |
| 2 Thresholds | Partly: the three amounts and the version | **No**: setting, history and the recompute event are API-only (S1) |
| 3 The state machine | Yes: state and full history | Yes: every move, with mandatory reasons |
| 4 Aggregation and evaluation | Yes: aggregate, both ways, by type, runs | Yes: recording a run |
| 5 Gates and the conclusion | Yes: every gate, the sign-off decision, the conclusion and its history | Partly: the strategy answer. **The acknowledgement and the conclusion are not** (S3) |

Not reachable from any screen, and not one of the spec's three screens: creating an
engagement, linking it to the Spine, the Spine reconciliation report and the event log
(S2, S11).

### What the review checked, and found

- **Navigation.** List to schedule, schedule to detail, schedule to evaluation, detail to
  schedule, evaluation to schedule: each tested by following the links on the screens, and
  a test follows every link on every screen and requires it to load. No dead link.
- **States.** Loading, empty, failed and retry are tested on all four screens, with the
  backend's own refusals.
- **Layouts.** Looked at in a browser at 1280, 768 and 375 pixels: no screen scrolls
  sideways. The engagement list's table scrolls inside its own box below desktop width.
- **Amounts.** A test reads every rupee amount off the schedule, the detail and the
  evaluation, takes the formatting off, and requires each to be a figure the backend sent,
  digit for digit. The source has no floating-point arithmetic and no number parsing.
- **Partner-only actions.** The screens have no control for the acknowledgement or the
  conclusion and the API client has no function for either; tests assert both.
- **Console.** No error or warning on a pass through every screen. One 404, for the
  missing favicon.
- **One defect found and fixed:** the dash shown for the empty side of a Dr/Cr line was too
  pale to read (contrast 2.6 to 1); it now meets 4.5 to 1.
- **Found and not changed, being outside the spec:** S12.

### Verdict

Stage 6 is complete as built to the instructions given for it: the three screens exist,
are tested, and change nothing in the backend. **It is not the whole of spec section 10 as
written**: the conclusion cannot be recorded from the evaluation screen (S3), and two of the
five features can only be written through the API (S1, S2). Nothing has been seen on live
data (V9, V10). Whether S1 to S3 belong to Stage 6 or to a later stage is a decision for
you; this review does not make it.

*Since this verdict: the closure work of section 11 built the screens and forms that S1 to
S3 and S11 named, and looked at every screen on live data. Section 11 is the current state.*

## 11. Stage 6 closure work — 5 November 2026

One remediation of everything section 10 left open: S1 to S12 and V9 to V11 (architecture
D52). The specification, the four documents, the source, the API, the tests and the
database rules were read again first. Nothing in the backend's source or migrations was
changed; two backend files were touched, both test tooling: the fixture test, and a new
launcher for an isolated preview. Nothing is committed.

### Remediation matrix

| # | What the specification requires | What existed | What was done | Decided by the spec? | Needs anyone or anything outside? | Final status |
|---|---|---|---|---|---|---|
| S1 | Section 4: three lines, the fraction "declared", the threshold "documented"; acceptance 2: a revision recomputes every band "and the recompute is recorded"; SA 450 para 10 | The API (set, current, history, events). The screens showed three amounts and a version | A thresholds screen: set, revise, fraction, basis, who and when, Spine PM check, every version, every recorded recompute | Yes | No | **Resolved** |
| S2 | Section 3.1: Dr/Cr lines that balance; 3.2: range, sample and basis; 8: a working paper reference, manual entry allowed; D8: the engagement and its Spine link | The API. No screen | A new-engagement screen, a Spine link form, and a recording form that sends lines, type fields and the working paper reference | Yes | A ledger picker needs a backend route (S13) | **Resolved**, with S13 open |
| S3 | Section 6.4: the conclusion, "a field, mandatory"; 10.3: "the conclusion field"; 7: "a required partner acknowledgement"; 12: the words are the partner's | The API, partner-only. The screen showed both and offered neither | Both forms, offered only where the backend reports a partner can be named; the gates and the partner check stay in the backend | Yes | Yes: the firm's proxy and role claim (B9a, O1) | **Implemented, awaiting external integration** |
| S4 | Section 3.3: the diagram | The screen's copy of the diagram; the backend's rule | Checked against the spec and the backend; a test pins the copy to the spec | Yes | No | **Resolved from the specification** |
| S5 | Section 10.1: "running totals at the top ... always visible"; 4.1: one aggregate | Totals are the backend's aggregate; filters do not change them | Kept; the ambiguity documented | No | CA or lead | **Requires external decision** |
| S6 | Section 10.1: "as a percentage" | One decimal place, exact | Kept. Display corrected (D54): a figure below a line reads 99.9%, never 100.0% | No | CA | **Requires external decision** |
| S7 | Section 10.1: "always visible" | Pinned from tablet width only | Pinned at every width; set smaller on a phone | Yes | No | **Resolved** |
| S8 | Section 4: CTT is the line for a single item; the aggregate test is against OM | Marks at PM and OM from the backend's gates; a percentage at CTT | Kept | No: the spec defines no aggregate test at CTT | CA | **Requires external decision** |
| S9 | Nothing | A confirmation before every move | Kept as the safe behaviour | No | Lead | **Requires external decision** |
| S10 | Sections 7 and 12 reserve two actions to the partner; nothing on the rest | The backend enforces those two and nothing else (B9b) | Unchanged: a screen cannot decide who may act | Partly | Firm (B9b) | **Requires external decision** |
| S11 | Not one of the spec's screens; D46 built both reports for a person to read | The API. No screen | A Financial Spine screen with the reconciliation, and an events screen | Supported by D13 and D46 | No | **Resolved** |
| S12 | Not in the spec; "easy to read" was an instruction for Stage 6 | One title, focus left behind, no favicon | Titles, focus, a skip control, a favicon; contrast, names and keyboard checked | n/a | A screen-reader session, if wanted | **Resolved** |
| V9 | — | Screens seen on captured answers only | Every screen used on live rows in an isolated preview, at three widths | n/a | The live Spine (V5, V6); the main database | **Done in the preview; the rest cannot be verified here** |
| V10 | — | No write ever sent to a running backend | Engagement, thresholds, six misstatements, every move, a run: sent from the screens to a running backend | n/a | A partner (V12); a strategy fraction (V13) | **Done in the preview, except V12 and V13** |
| V11 | — | Eight branches coded and untested | Each reached by a real answer of the backend and tested | n/a | No | **Resolved** |

Found by the closure work and added to the register: **S13** (no route lists the Spine's
ledgers or heads), **V12** (a partner's writes through a browser), **V13** (the strategy
prompt on a running backend).

### What now exists

| Screen | Address | Reads | Writes |
|---|---|---|---|
| Engagement list | `#/` | the engagements | — |
| New engagement | `#/engagements/new` | — | `POST /api/engagements` |
| Schedule | `#/engagements/{id}` | engagement, misstatements, evaluation | — |
| Record a misstatement | `#/engagements/{id}/misstatements/new` | engagement | `POST .../misstatements` |
| Misstatement detail | `#/misstatements/{id}` | the misstatement | `POST .../transitions` |
| Evaluation | `#/engagements/{id}/evaluation` | engagement, evaluation, runs, conclusions, two gates | `POST .../evaluation/runs`, `.../strategy-responses`; partner only: `.../soft-gate-acknowledgements`, `.../conclusions/not-material`, `.../conclusions/material` |
| Thresholds | `#/engagements/{id}/thresholds` | engagement, current thresholds, history, events | `POST .../thresholds` |
| Financial Spine | `#/engagements/{id}/spine` | engagement, reconciliation | `POST .../spine-link` |
| Events | `#/engagements/{id}/events` | engagement, events | — |

The screens now use 24 of the API's 26 routes. The two they do not: `GET
/api/evaluation-runs/{id}` and `GET /api/thresholds/{id}`, each of which returns one row
the screens already read in a list.

### The five backend features through the screens

| Feature | Read | Write |
|---|---|---|
| 1 The misstatement record | Yes | Yes: recorded from a screen |
| 2 Thresholds | Yes: lines, fraction, basis, history, recompute, Spine PM check | Yes: set and revise |
| 3 The state machine | Yes | Yes |
| 4 Aggregation and evaluation | Yes | Yes |
| 5 Gates and the conclusion | Yes | Yes for the strategy answer; the acknowledgement and the conclusion are built and can be used only once a partner can be named |

### The eight display branches (V11)

| Branch | How the backend was brought to it | Tested |
|---|---|---|
| 1 A judgemental range crossing PM | A judgemental item with a range of 200,000 to 300,000 against PM 250,000 | Detail and schedule |
| 2 A state that differs from the Spine's | The Spine double decides the adjustment directly | Detail, schedule, evaluation, and the run the backend then refuses |
| 3 A ledger not matched in the Spine | The Spine double holds the ledger under another key | Detail |
| 4 An effect unresolved while the Spine is readable | The same: the effects cannot be determined, the lines can still be read | Detail and schedule |
| 5 A move the Spine had already decided | The move is made after branch 2 | Detail: "it had already been decided this way" |
| 6 A stale acknowledgement | A partner acknowledges, then a misstatement is recorded | Evaluation: asked for again |
| 7 A stale strategy answer | The prompt is answered, then a misstatement is recorded | Evaluation: asked for again |
| 8 An item at or above OM on its own | One item of 400,000 against OM 400,000 | Evaluation |

All eight are real answers of the backend, captured in transactions that were rolled back.
Thirteen tests; all pass.

### Live verification, kept apart from the fixture tests

Done in an isolated preview (`backend\tests\preview_server.py`): the real application
over `oak_misstatements_test` inside one transaction that is never committed, the Financial
Spine double, the development identity, and the built frontend, driven in a real browser.
A separate preview database was not possible: no role this project has may create one, and
the settings refuse any database but the two by design.

| What | Result, live |
|---|---|
| Engagement creation | Created with its Spine link; an unknown Spine engagement refused with the backend's 404 |
| Threshold setting | Set; PM not below OM refused with the backend's 422; revised to a second version |
| Misstatement recording | Six recorded, factual and judgemental; lines that do not balance refused with the backend's 422 (acceptance 1) |
| State transitions | Communicated, corrected, refused, withdrawn. A refusal could not be confirmed without a reason (acceptance 3). The Spine double showed accepted for the correction and refused for the other two |
| Aggregation | 300,000 gross on three uncorrected items; the corrected and the withdrawn item left out, and named |
| Recompute on revision | After the revision one item moved from accumulated to clearly trivial, and the recompute was listed (acceptance 2) |
| Evaluation runs | One recorded; it went stale when a misstatement was added, and again when thresholds were revised, each for the backend's stated reason |
| Gates | The soft gate fired at 300,000 against PM 250,000 and blocked sign-off; the hard gate fired at exactly 400,000 against OM 400,000 and blocked the opinion gate (acceptance 7) |
| Partner-only actions | Shown as unavailable, with no form. Sent directly as the development user, all three were refused with a 403 and nothing was written |
| Conclusion | None could be recorded, which is correct here; "not material" was shown as blocked by the gates, in the backend's words |
| Events and reconciliation | The reassessment and the recompute listed; the reconciliation clean |
| Layout, keyboard, contrast | No screen scrolls sideways at 1280, 768 or 375 pixels; focus moves to the content on navigation and is visible on Tab; no text below 4.5 to 1; no console error |

After the preview was stopped: every table of `oak_misstatements_test` held no row and no
session was left in a transaction; `oak_misstatements` had no table.

**Not verified live, and said so:** a partner's acknowledgement or conclusion (V12); the
strategy prompt (V13); changing a Spine link after creation; a ledger the import lacks; a
projected misstatement. Each is tested on the backend's captured answers. Nothing here
touched the live Financial Spine (V5, V6). One artefact of the preview: because it is one
transaction, the database's clock stands at its start, so rows show the same creation time.

### Three defects found by the live check and by the tests, and fixed

1. The event screen's page heading and panel heading shared an id, so the panel was
   announced with the wrong name. Found by a test.
2. On a phone a long ledger name ran into its amount on the schedule. Found in the browser.
3. One request of a live check carried a made-up partner role header. It was refused before
   it was sent, and removed: no partner identity is simulated anywhere, tests included,
   other than in the backend's own test suite, which runs the app behind a proxy the way
   production does.

### Verdict

Every Pass 1 requirement that the specification determines for the screens is now built
and tested, and all of it except the two partner-only writes has been used on a running
backend. **Stage 6 is not declared complete.** *(As at this section. Superseded by section
13: the Pass 1 implementation is complete; what is outstanding is production acceptance.)*
What stands between it and that:

- The documented conclusion and the partner's acknowledgement, Pass 1 items, cannot be
  exercised end to end until the firm's identity provider names a partner (S3, V12).
- Nothing has been seen against the live Financial Spine or on `oak_misstatements` (V5, V6;
  the main database is unmigrated, by instruction).
- Five matters are for people to decide: S5, S6, S8, S9, S10; and S13 if a ledger picker
  is wanted.
- *Added 5 Nov 2026, after this verdict was written:* the aggregate these screens showed
  included the clearly trivial items, which spec sections 2 (paragraph 5) and 4 leave out
  (S14). Corrected the same day in the backend (D53); see section 12.

## 12. Clearly trivial items, the percentage display, and the Pass 1 gap check — 5 November 2026

### What was built

- **S14 (D53).** A clearly trivial item is no longer accumulated: `core/gates.py` leaves it
  out of every sum and names it; the evaluation and each run carry `not_accumulated`; the
  running totals, the aggregate panel and an inspected run say so. The treatment of
  corrected, withdrawn, refused, projected, unresolved and classification-only items is
  unchanged, and every misstatement stays in the schedule.
- **S6 (D54).** A percentage of a figure strictly below a line reads 99.9%, never 100.0%.
  Presentation only.

### Pass 1 against spec section 11

| Pass 1 item | State | What still stands in the way |
|---|---|---|
| The misstatement record with Dr/Cr lines over the Spine | Built, tested, used on a running backend | The live Financial Spine (V5, V6): only the double has been used |
| The three thresholds with automatic banding and recompute | Built, tested, used on a running backend | Section 4, "all from Materiality (SA 320)": the lines are entered by hand (B4a), the firm's |
| The state machine with mandatory refusal reasons | Built, tested, used on a running backend | Nothing |
| Aggregation gross and net, profit and net assets | Built and tested; **now leaves out clearly trivial items (D53)** | The CA's questions under S14, B8 and B2, on interim treatments |
| The schedule screen | Built, tested, used on a running backend | Nothing the spec determines |
| The hard gate at overall materiality | Built, in the write path and in the database | "The Opinion module is blocked": no Opinion module exists; the gate is exposed for it (D46) |
| The documented conclusion | Built and tested, backend and form | A partner must be named by the firm's identity provider (S3, V12); it has never been made end to end through a browser |

### Every remaining item, classified

| Class | Items |
|---|---|
| Implementable today | None that the specification requires. One thing could be built without anyone else: a ledger picker for the recording form (S13). The spec does not ask for it and it needs a new read-only backend route, so it was not added without being asked for |
| Requires an external system or access | The live Financial Spine (V5, V6, V7, V8); the firm's authenticating proxy and a partner role claim (S3, V12, B9a, O1); an Opinion module to block; a Materiality module to take the lines from (B4a); a remote and CI (N4). Migrating `oak_misstatements` needs approval and was not done |
| Requires an explicit CA or firm decision | CA: S14's eight questions *(nine since D55; one still open since section 15)*, B2, B7a to B7c, B8, B14, B15a, F3, S6 (precision), S8. Lead or the Spine's owner: B1, B5 (which also keeps V13 unverified), B10a to B10c, B15b, F9, N7, N8, N13, N17, S5, S9, S13. Firm: B4b, B9b, S10, O2, N6 |
| Pass 2, not today's scope | Qualitative factors and escalation (section 5, F5); prior-period carry-forward (B6, `py_carried`, acceptance 5); the TCWG extract and the representation attachment; intake from agent runs, review notes and Sampling (N16); the generated binder paper |

### Verification

- Backend: `pytest` on PostgreSQL **462 passed, none skipped**; on the stand-in 430 passed,
  32 skipped. `ruff check`, `ruff format --check` and `mypy` strict are clean (88 files).
- Frontend: `vitest` **316 passed in 18 files**; `tsc --noEmit`, `eslint src tests` and
  `prettier --check .` are clean; `npm run build` succeeds.
- Fixtures: all 122 captured answers regenerated from the API on PostgreSQL and checked
  again on the stand-in.
- In a browser, on the isolated preview (the real application over `oak_misstatements_test`
  in one transaction that was never committed, with the Spine double): eight misstatements
  were recorded, five of them clearly trivial (raised, projected, refused, and one a paisa
  below CTT), one exactly at CTT. The schedule listed all eight; the totals and the
  aggregate showed only the accumulated ones and named the others; no gate moved for them;
  a run recorded what it left out, went stale when a clearly trivial item was raised with
  no figure moving, and still showed its own record when inspected. A figure of ₹2,49,990
  against PM of ₹2,50,000 read 99.9% with the soft gate clear. Checked at the pane's desktop
  width and at 375 pixels, with no console error and no sideways scroll. The data was seeded through the
  preview's API and the screens were then read; the forms themselves were exercised in the
  D52 check and not again.
- Not verified, as before: a partner's acknowledgement or conclusion through a browser
  (V12), the strategy prompt on a running backend (V13), and anything against the live
  Spine (V5, V6).
- Databases, read afterwards: `oak_misstatements` has no table; `oak_misstatements_test` has
  its eight tables at migration 0010 and no row in any of them; no session was left open.

### Verdict

Every Pass 1 item of spec section 11 is built and tested, and the accumulation rule of
sections 2 and 4 is now applied. **Pass 1 is not declared complete** *(as at this section;
section 13 states it as: the implementation is complete, production acceptance is
pending)*, for reasons outside
the code: the conclusion has not been made by a named partner (V12), nothing has run against
the live Spine or on the main database, and the CA has not answered the questions on which
several figures rest, S14's among them.

## 13. Pass 1 closure — 5 November 2026

Written against the code as it stands, after the clearly trivial rule (D53), two walks
through the screens in a browser, and the small changes of D55. Section 12's table is
superseded where this one differs.

### The seven deliverables of spec section 11

| # | Deliverable | Status | Evidence |
|---|---|---|---|
| 1 | The misstatement record with Dr/Cr lines over the Spine | Built, tested, used through the form | Factual, judgemental (with its range) and projected (with its sample and basis) recorded in a browser; two and three lines; a ledger not in the import; unbalanced, one-sided and unknown lines refused. Amounts live in the Spine double, never here |
| 2 | The three thresholds with banding and recompute | Built, tested, used through the form | Set and revised in a browser; PM not below OM refused; every band recomputed on the revision and the recompute listed |
| 3 | The state machine with mandatory reasons | Built, tested, used through the buttons | Communicated, corrected, refused, withdrawn; an empty or blank reason stopped; final states offer nothing; the Spine double's adjustment accepted or refused accordingly |
| 4 | Aggregation gross and net, profit and net assets | Built, tested, seen in a browser | Gross and net differing (₹1,10,000 and −₹70,000); with and without projected (₹4,25,000 and ₹3,80,000); by type; clearly trivial items named and left out (D53) |
| 5 | The schedule screen, with detail and evaluation | Built, tested, used | Filters, pinned totals, every item listed; eight screens at 1024 and 375 pixels with no sideways scroll |
| 6 | The hard gate at overall materiality | Built, tested, seen firing and clearing | In the write path and in the database; the opinion gate blocked; "only with the projected items" said when that is so |
| 7 | The documented conclusion | Built and tested; **never made by a named partner** | Mandatory words and basis, the run reviewed, the figures saved with it, refused on a stale run or a blocking gate, partner only. In a browser the form is correctly withheld and the reason shown |

### The Pass 1 acceptance criteria of spec section 13

| # | Criterion | Automated tests | In a browser |
|---|---|---|---|
| 1 | Dr/Cr lines required and must balance | Yes | Yes |
| 2 | Changing materiality recomputes every band, recorded | Yes | Yes |
| 3 | A refusal without a reason is rejected | Yes | Yes at the form; the backend's own refusal by test only |
| 4 | Aggregate gross and net, profit and net assets | Yes | Yes |
| 6 | An item above PM blocks sign-off until dealt with | Yes | Yes: blocked, then released by correction and by refusal with a reason |
| 7 | Aggregate at or above OM blocks an unmodified opinion, as a gate | Yes, including the database's own check | Yes for the gate; the refused write by test only |
| 10 | The conclusion cannot be saved empty and carries its figures | Yes | No: needs a named partner |
| 11 | A corrected misstatement posts to the Spine; an uncorrected one does not | Yes, against the double | Yes, against the double. Never against the live Spine |

Criteria 5, 8 and 9 (prior period, qualitative escalation, the TCWG extract) are Pass 2.

### Defects fixed in the closure

1. **Clearly trivial items were accumulated** (S14; D53). Fixed in `core/gates.py`.
2. **A percentage just below a line read 100.0%** (S6; D54).
3. **An inspected run said "Counted: Yes" for a clearly trivial item** (D55). Found in the
   browser.
4. **The gate endpoints did not say what their figures left out** (D55).
5. **The conclusion form did not show the figures it would save** (D55).

No defect was found in the state machine, the banding, the recompute, the gates, the
staleness of runs, acknowledgements and conclusions, or the partner-only checks.

### Category C: decisions that people must make

None of these stops the Pass 1 code from being complete. Each is built on an interim
treatment that is an assumption and is labelled as one; none is approved here.

| Item | Exact requirement | Current implementation | Why it is blocked | Who | Effect |
|---|---|---|---|---|---|
| S14, questions 1 to 9 | Spec 2 (para 5) and 4: accumulate "other than those clearly trivial" | Item-level band; items named and left out; no total of them and no warning; classification-only listed at nil; a judgemental item on its point estimate. *(As at this section. Since D56 a judgemental item whose range reaches CTT is accumulated; since D57 items that together reach CTT are accumulated: sections 14 and 15)* | The spec does not say what happens to many such items together, to mixed effects, or to a wide range | CA | Production acceptance. Question 2 matters most: any number of items below CTT reach no gate *(no longer so since D57: section 15)* |
| B8 | Spec 3.2: a projected item "never aggregated as if it were factual without saying so" | Projected items count and every gate says whether it depends on them | Whether they should count toward the gates is not stated | CA | Production acceptance |
| B2, B7a to B7c | Spec 3.1 and 4.1: the four computed effects | Classification-only means nil on profit and on net assets; net assets is assets less liabilities | Readings of the spec, not statements in it | CA | Production acceptance |
| B14, B15a | Spec 6.4 and SA 450 para 11: "material individually or in aggregate" | Two conclusions, material and not material; "material" may be saved while the hard gate fires | What "material individually" means, and whether that conclusion may be saved then, are not stated | CA | Production acceptance |
| F3 | Spec 7: "aggregate uncorrected misstatements" | Raised, communicated and refused are uncorrected | A reading | CA | Production acceptance |
| S6, S8 | Spec 10.1: totals "in rupees and as a percentage" | One decimal place, half up; no mark at CTT | Precision and a mark at CTT are not stated | CA | Minor |
| B5 | Spec 7: "aggregate approaching materiality" | Mechanism built; not evaluated until a fraction is declared | "Approaching" is not defined | Lead or firm | The strategy trigger does not operate until it is set |
| B1, F9, B10a to B10c, B15b, N7, N8, N13, N17 | Spec 1 and 3.3: the Spine holds the lines; nothing is deleted | Withdrawal refuses the Spine's proposal; no amendment after raising; conclusion allowed on an unlocked version | They concern the Spine's own rules and how the two modules agree | Lead and the Spine's owner | Production acceptance and operations |
| S5, S9, S13 | Spec 10: the screens | Totals do not follow the filters; each move asks for confirmation; lines are entered by number or by name, with no picker | The spec is silent | Lead | None; S13 would need a new read-only route |
| B9b, S10, B4b, O2, N6 | Spec 12 reserves two actions to the partner and is silent on the rest | Any authenticated identity may raise, move, set thresholds and record a run; reads need no identity | Who may do what is the firm's policy | Firm | Production acceptance |

### Category D: what needs systems, access or approval

| Item | Exact requirement | Current implementation | Why it is blocked | What is needed | Effect |
|---|---|---|---|---|---|
| A named partner (B9a, O1, S3, V12) | Spec 12 and 7: the conclusion and the acknowledgement are the partner's | Enforced in the write path; both forms built; tested on answers captured behind a trusted proxy with a role claim; refused for everyone here | No identity provider names a partner in this environment, and none was simulated | The firm's authenticating proxy and its role claim | End-to-end verification and production acceptance. Not the implementation |
| The live Financial Spine (V5 to V8) | Spec 1 and acceptance 11: lines and postings live in the Spine | Client built from the Spine's source; every test and both browser walks used the double | No access to a running Spine with a test engagement | Access from the Spine's owner | Production acceptance |
| The main database | The module runs on `oak_misstatements` | Never migrated, never written; ten migrations proven on `oak_misstatements_test` | Migration needs approval, by instruction | Approval to migrate | Deployment only |
| An Opinion module | Spec 7: "The Opinion module is blocked, with the figure shown" | Two read-only gate endpoints, with the figures, for it to call | No Opinion module exists | That module | The block itself cannot be seen end to end |
| A Materiality module (B4a) | Spec 4: the lines are "all from Materiality (SA 320)" | Entered by a person, versioned, checked against the Spine's PM | No Materiality module exists to take them from | That module, or the firm's decision to keep manual entry | The spec's wording is not met until then |
| A disposable database (V3) | Two requests at the same moment | The row lock is taken and tested one request at a time | Proving it needs committed rows, and no role here may create a database | A database that may be written and dropped | A verification gap |
| A remote and CI (N4) | — | Two local commits; no remote | The firm's choice | The firm | None for Pass 1 |

### What is still verified by automated tests only

A partner's acknowledgement and conclusion, their refusals and their staleness; a PM gate
set to hard; the Spine unreachable; a state the Spine disputes; an orphan proposal; a
failed commit; release of an item above PM by withdrawal. None of these could be driven
honestly from a browser here. A session with a screen reader has not been held.

### Verification

- Backend: `pytest` on PostgreSQL **465 passed, none skipped**; on the stand-in 433 passed,
  32 skipped. `ruff check`, `ruff format --check` and `mypy` strict are clean (88 files).
- Frontend: `vitest` **317 passed in 18 files**; `tsc --noEmit`, `eslint src tests` and
  `prettier --check .` are clean; `npm run build` succeeds.
- Fixtures: all 122 captured answers regenerated from the API on PostgreSQL and checked
  again on the stand-in.
- In a browser, on the isolated preview, through the forms and buttons, twice. The first
  walk used the forms from creating the engagement onward. In the second the engagement
  and its thresholds were seeded through the preview's API, because both forms had just
  been walked, and everything after was entered by keyboard. The strategy prompt was seen
  with a test fraction set for that preview alone.
- Databases, read afterwards: `oak_misstatements` has no table; `oak_misstatements_test` has
  its eight tables at migration 0010 and no row in any of them; no session was left open.

### Verdict

**The Pass 1 implementation is complete.** Each of the seven deliverables is built, tested
and has been used on a running backend, and no known defect remains in this project.

**Pass 1 is not accepted for production**, and three things outside this project stand
between the two: a partner named by the firm's identity provider, so that a conclusion is
made end to end (V12); a run against the live Financial Spine (V5, V6); and the CA's
answers, above all to S14's question 2 and to B8.

## 14. Resolution pass — 5 November 2026

After section 13 every item still open was grouped and worked through
(`docs/DECISIONS_PENDING.md`, "Resolution pass of 5 November 2026"; architecture D56).

- **49 items were open; 20 were closed; 29 remain.** The 20: one changed in code on the
  standard's text, five accounting readings confirmed against the standard, thirteen choices
  answered by the specification, and one verification gap.
- **Changed in code (D56).** A judgemental item whose range reaches CTT is no longer
  clearly trivial (SA 450 A2). The clearly trivial items are totalled, and the screens say
  when together they reach CTT; no figure or gate is changed by that. *(Superseded by
  section 15: once together they reach CTT, all of them are accumulated.)*
- **The 29 that remain** are not the code's to close: 18 decisions for the CA, the lead,
  the Spine's owner or the firm; 4 external dependencies; 6 verification gaps that need the
  live Spine, a named partner or a disposable database; and one accounting question, whether
  clearly trivial items that together reach CTT must be accumulated.
- **Verification.** Backend: `pytest` on PostgreSQL **466 passed, none skipped**; on the
  stand-in 434 passed, 32 skipped; `ruff`, `ruff format --check` and `mypy` strict clean.
  Frontend: `vitest` **319 passed in 18 files**; `tsc`, `eslint`, `prettier` clean; the
  build succeeds. Fixtures regenerated from the API. The two new displays were tested on
  the backend's captured answers and were not looked at again in a browser.
- **Verdict, unchanged:** the Pass 1 implementation is complete; production acceptance
  waits on a named partner, the live Financial Spine and the CA.

## 15. S14 question 2 against ICAI's SA 450 — 5 November 2026

Section 14 left one accounting question open and said the module only showed a note. It was
re-examined against ICAI's text of paragraph A2 (architecture D57; the register's last
section has the full reasoning).

- **A2 settles the principle.** Clearly trivial matters are clearly inconsequential
  "whether taken individually or in aggregate", and any uncertainty resolves against
  triviality. Items below CTT that together are not small must be accumulated.
- **The module did not do that, and now does.** Items clearly trivial one by one are left
  out only while together, gross, they are below CTT on both measures. At or above CTT on
  either, all of them are accumulated and reach the gates.
- **Still open, narrowed.** The standard gives no number for "in aggregate"; CTT itself,
  gross, on either measure is the conservative reading and is the CA's to confirm.
- **The six other readings** (S14 Q9, F3, B8, B14, B15a, B2) were checked against the same
  text and stand. B14 now records one limit: no test against a class-level materiality.
- **Count unchanged: 29 remain.**
- **Verification.** Backend: `pytest` on PostgreSQL **469 passed, none skipped**; on the
  stand-in 437 passed, 32 skipped; `ruff`, `ruff format --check` and `mypy` strict clean.
  Frontend: `vitest` **319 passed in 18 files**; `tsc`, `eslint`, `prettier` clean; the
  build succeeds. Fixtures regenerated from the API. Seen in a browser on the isolated
  preview, with the data seeded through its API: one item of 12,000 was left out and its
  total shown; a second brought both into the totals with the note naming them; no sideways
  scroll at 1024 or 375 pixels.

## 16. Final targeted review of the open items — 5 November 2026

The 29 open items were reviewed together once more (`docs/DECISIONS_PENDING.md`, "Final
targeted review"). No code changed.

- **Closed, 7:** S10 (a duplicate of B9b), S3 (the forms are built and tested; what is left
  is V12, B9a and O1), N17 (a fact about the Spine, not a decision), N4 (the work is
  committed; a remote and CI are not requirements of the specification), B4b, B7a and B7c
  (each answered by the specification's own words).
- **Remaining, 22:** two for the CA (S14 Q2, B7b); five for the lead (B5, B10a to B10c, F9);
  three for the Spine's owner (B1, N7, N8); three for the firm (B4a, B9b, N6); three that
  need external systems or approval (B9a, O1, O2); six verification gaps (V3, V5 to V8,
  V12).
- **Verdict, unchanged:** the Pass 1 implementation is complete; production acceptance
  waits on a named partner, the live Financial Spine and the CA.

## 17. Last focused review of the open items — 5 November 2026

The 22 open items were reviewed once more (`docs/DECISIONS_PENDING.md`, "Last focused
review"; architecture D58).

- **Closed, 4.** V3 was verified: requests at the same moment are serialised by the
  engagement row lock, shown in a scratch schema that was dropped afterwards. N8, N6 and B9a
  were consolidated into B1, B9b and O1, which already held the same questions; those
  questions stay open.
- **Remaining, 18:** S14 Q2 and B7b (CA); B5, B10a, B10b, B10c and F9 (lead); B1 and N7
  (the Spine's owner); B4a and B9b (firm); O1 and O2 (external); V5, V6, V7, V8 and V12
  (verification).
- No application code changed. One tool was added, `backend/tests/concurrency_check.py`.
- **Verdict, unchanged:** the Pass 1 implementation is complete; production acceptance
  waits on a named partner, the live Financial Spine and the CA.

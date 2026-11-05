# Closure review — Misstatements Rollup

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
| Frontend | Stage 0 shell only. No screen of spec section 10 exists |
| Version control | No commit existed at the review. **First commit made 5 Nov 2026:** `0bf54c0d99cc5d3d305436b92352f6d3a2e9d313`, 122 files, on `master`. No remote is configured and there is no CI |
| Spec acceptance criteria | 8 of 11 implemented and tested on the stand-in; 3 are Pass 2 |
| Pass 1 of the spec | Not complete: the schedule screen is missing |
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
| 4 | Aggregate gross and net, profit and net assets | Implemented and tested in the API; not yet "shown" on a screen; net assets rests on B7 |
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
| 2, para 5 | Clearly-trivial threshold per engagement, documented | Met |
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
| 6.1 | Summary of Audit Differences | Data available from the API; no screen, no document |
| 6.2, 6.3, 6.5 | TCWG extract, representation attachment, binder working paper | Not built (Pass 2) |
| 6.4 | The conclusion | Met |
| 7 | Hard gate; soft gate as a setting; individually significant; write path | Met |
| 7 | "The Opinion module is blocked, with the figure shown" | Gate exposed; nothing to block; N1 |
| 7 | Strategy trigger, recorded either way | Mechanism met; inert until B5 |
| 8 | Area tester and manual sources | Met |
| 8 | WorkMind runs, review notes, Sampling | Not built (Pass 2). The API refuses those sources; the database allows them |
| 9 | `threshold`, `misstatement`, `evaluation` | Met, except `py_carried` |
| 9 | `qualitative` | Not built |
| 10 | Three screens | **Not built.** The schedule screen is in the spec's Pass 1 |
| 11 | Pass 1 | Six of seven items built; the schedule screen is missing |
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
4. **Stage 6**: the three screens. Without the schedule screen, Pass 1 of the spec is not done.
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
| A later stage or module | Stage 6 (N12), Stage 7, Pass 2 (N16), an Opinion module |


# Decisions pending — Misstatements Rollup

**Current status, 5 November 2026, after the last focused review: 18 items are open.** They
are listed, with who each waits on and why, in the section "Last focused review" at the end
of this file. That section and the three before it are the current status. The tables
below are the record of each item; where an item has moved since its row was written, the
row ends with a note beginning "Now:". No note closes or reclassifies anything: each only
repeats what a later section of this file already records.

**The tables below were last rewritten on 5 November 2026, after the closure work on Stage 6 (architecture D52);
before that, after Stage 6 (D47 to D51) and the closure work on Stages 0 to 5 (D46).** These are the points `MISSTATEMENTS_ROLLUP.md` leaves to people. Nothing here is
approved by anyone unless the row says who approved it. Where an interim treatment has been
built, the row says so and says it is interim; where a point was closed, it says what closed
it. Each row names who decides, what needs the answer, and what the module does meanwhile.
The full inventory, with evidence for every row, is `docs/CLOSURE_REVIEW.md`.
The "needed before" column was re-dated at the start of Stage 1 after a read-only review of
B1, B2 and B7 against the Financial Spine's code (`D:\CAF\backend\src\oak_spine\spine\`).

## How Stage 1 isolates B1, B2 and B7 (architecture D23)

| # | What Stage 1 does | What it does not do |
|---|---|---|
| B1 | Proposes the adjustment to the Spine at raise time, because spec section 1 forbids holding the lines anywhere else. Since Stage 3 (D41) a withdrawal is recorded here with its reason and the Spine's adjustment is refused with a note saying it was withdrawn, so it can never post | The Spine has no withdrawn status, so its own aggregate still counts the item |
| B2 | Computes the classification-only flag from the lines (spec 3.1). Chooses the Spine's adjustment kind in exactly one function, `core/spine_kind.py`. Since D37 (4 Nov 2026) a classification-only item is proposed to the Spine as a `reclass`, which is what the Spine's contract calls a presentation-only item | Never proposes a classification-only item as a correction |
| B7 | Superseded by D31 on 4 Nov 2026: both effects are computed from the Spine's tree sections; unresolved lines give `null` for both. D32 (same day) records each version's classification so a remapped ledger or a moved tree is reported as drift and never changes an old figure | Acceptance criterion 4 is implemented and tested (D38, D43); its net-assets figures rest on the reading of B7, which the CA has not yet confirmed |

## Chartered accountant

| # | Decision | Needed before | Meanwhile |
|---|---|---|---|
| B2 | Classification-only misstatements: proposed to the Spine as `reclass` or `correction`. Since D31 "classification only" means no effect on profit before tax **and** none on net assets; a direct equity entry is therefore a correction. **Reading, not a decision:** spec section 3.1 says only "no effect on profit"; D31 added "and none on net assets" because a direct equity entry moves net assets and section 4.1 evaluates net assets separately. The CA confirms or corrects this. Under D33 such an item's amount-based bands are clearly trivial and its significance is qualitative (Pass 2, spec section 5). The Spine never counts an unaccepted `reclass` (`spine/uncorrected.py`) and counts an unaccepted `correction` at its debit total. **Code complete, 4 Nov 2026 (D37, D40):** proposed as `reclass`, recorded as such, banded clearly trivial on amount with `classification_only: true`, the gross size shown, listed in the schedule and in the aggregate at nil, never a guess (an unresolved line ends the verdict). **Interim accounting interpretation:** nil net-assets effect as well as nil profit effect. **Pending externally:** CA confirmation of that interpretation; qualitative evaluation of such items is Pass 2 | CA confirmation of the reading; nothing blocks Pass 1 | As described **Now:** closed on the text of SA 450 in the resolution pass (a classification misstatement is evaluated qualitatively); not a CA approval |
| B3 | **Decided 4 Nov 2026 (D33), the engagement lead's reading of spec line 93:** each effect is banded on its absolute value against the current threshold version and the item's band is the higher of the two. Judgemental items band on the point estimate, with `range_crosses_pm` beside; projected items carry `projected: true`; unresolved effects get no band. Assumptions recorded, none a standard's mandate: "higher band wins" is the conservative reading; an unresolved item is listed individually and never counted as trivial | Closed at code level; the CA may still refine | Built |
| B4 | **Complete at code level, 4 Nov 2026 (D35):** a person enters OM, PM, the declared CTT fraction and a basis as versioned rows; no default fraction exists; the Spine's PM is recorded at set time with a status and compared on every read against the recorded Spine version, a difference reported as `mismatch` and a changed pin as `pinned_version_changed`, never reconciled; every version is readable by id. **Three firm-level decisions stay pending:** (a) whether this module is the system of record for OM, PM and CTT and pushes PM to the Spine's pinned version with a named source, which needs the Spine owner's consent; **nothing is pushed today**; (b) whether the firm's manual fixes a standard CTT fraction to prefill; (c) for the CA, whether CTT is a fraction of PM, as the spec says, or of OM, as some methodologies have it **Point (c) closed from the specification, 5 Nov 2026:** spec section 4 says CTT is "a declared fraction of performance materiality". A different base would be a change to the spec, not a pending decision. | (a) and (b) firm; none blocks Pass 1 | As described **Now:** (b) closed from the specification in the final targeted review; (c) closed earlier; (a) open, for the firm |
| B13 | **Decided 4 Nov 2026 (D34):** performance materiality must be strictly below overall materiality, SA 320 paragraph 9's own definition. Enforced at the request (equal and greater refused with the paragraph named) and by the database CHECK `ck_threshold_pm_below_om` (migration 0005). `checks.pm_below_om` stays on every answer, always true, with a note saying it is enforced | Closed at code level | Built |
| B14 | What "material individually" means for the conclusion (spec section 6.4, SA 450 paragraph 11). The spec defines one individual band, "individually significant", above PM (section 4), and names "individually material" items in the TCWG extract (acceptance 9) without saying whether that is the same test or a test against overall materiality. **Not decided, and no reading is applied:** since D43 the evaluation shows both lists, every uncorrected item above PM and every uncorrected item whose own effect is at or above OM, and chooses neither **Stage 5 (D45) did not decide it:** a conclusion records one determination, material or not material, and the partner's own words; both lists are stored with the row | The CA, before any report or extract states that misstatements are or are not material individually | Both lists shown and stored with every run; nothing is concluded from either **Now:** closed on the text of SA 450 paragraph 11 in the resolution pass, with the limit recorded there; not a CA approval |
| B15 | Two readings Stage 5 applies to the conclusion (D45), neither stated by the spec in so many words. (a) A conclusion that the misstatements **are** material may be saved while the hard gate fires, and needs no soft-gate acknowledgement: section 7 says the hard gate blocks an unmodified opinion, not the documenting of a material conclusion, and SA 450 paragraph 15 requires the conclusion to be documented. A conclusion that they are **not** material is blocked by every gate. (b) The partner must name the evaluation run they reviewed, and the conclusion is refused if that run is stale, so that the figures saved are the figures reviewed (acceptance 10) | The CA and the engagement lead, before the first conclusion is relied on | Built as described; a material conclusion still needs a complete, consistent evaluation and no item above PM left raised or communicated **Now:** (a) closed on the text of SA 450 and (b) from the specification, in the resolution pass; not a CA approval |
| B6 | Prior-period carry-forward: source (the Spine's prior version's uncorrected schedule, or entered), whether items carry Dr/Cr lines, and how the current-period effect of a prior-period item is computed | Pass 2, Stage 9 | Not built. The `evaluation` row of Stage 4 has no `py_carried` column yet; it arrives with this decision (D43). Now: built 6 Nov 2026 as an interim reading (D61); the three questions stay open, see the last section |
| B7 | **Decided 4 Nov 2026 (D31):** net assets is assets less liabilities, computed from asset and liability lines with equity outside the sum; profit before tax excludes items after IX; nothing is imputed. Three confirmations remain for the CA: (a) that net assets equals shareholders' funds, item I(1), is the intended reading and not "net worth" under s.2(57); (b) how share application money pending allotment, item I(2), is treated, meanwhile unresolved and such entries refused; (c) that no tax effect is imputed when an entry carries no tax lines | Confirmations before acceptance 4 is claimed | Built as D31; I(2) lines refused with the reason **Now:** (a) and (c) closed from the specification in the final targeted review; (b) open, for the CA |
| B8 | Whether a projected amount counts toward the OM hard gate and the PM block as a factual one does. **Interim, 4 Nov 2026 (D38), an assumption and not a decision:** projected amounts count, the conservative reading, and every aggregate and gate is also given without them; a gate reports `depends_on_projected` and the sign-off reason says when a block rests only on projected items; a projected item that is individually significant blocks like a factual one, flagged projected. A projected item can never fall out of the evaluation silently. **Code complete (D38, D40):** aggregate, gates, exact boundaries, contributions by type, the write-path dependency `sign_off_open` with a contract test that fails any future sign-off route lacking it. **Interim policy assumption:** projected amounts count. **Pending externally:** CA confirmation of that policy; the conclusion write itself (Stage 4) and any Opinion hand-off, neither of which exists | The CA, before the conclusion (Stage 4) relies on a gate that depends on projected items | As described; both views always shown **Now:** closed on the text of SA 450 paragraph A3 in the resolution pass; not a CA approval |
| B11 | **Decided 4 Nov 2026 (D33), the spec's literal wording:** below CTT clearly trivial; exactly CTT accumulates; from CTT to exactly PM accumulates; strictly above PM individually significant; the aggregate soft gate fires at or above PM and the hard gate at or above OM. The asymmetry between the individual test and the aggregate tests is the spec's own wording, kept as written. The Spine's own aggregate gate is strictly above PM, a difference for the Spine's owner | Closed at code level | Built; `at_pm_boundary` and `PM_BOUNDARY` removed |
| F3 | Which states count as uncorrected. Reading derived from the spec: everything not corrected and not withdrawn (raised, communicated, refused). Approved as a reading; CA confirmation advisable. **In use since D38** for the aggregate and the gates, and since D43 for every recorded evaluation run, with the basis text naming F3 A conclusion (D45) is saved on this reading too | CA confirmation before a conclusion is relied on | Reading in use, declared on every evaluation answer and stored with every run **Now:** closed on the text of SA 450 paragraph 4(b) in the resolution pass; not a CA approval |
| F5 | Escalated items below CTT: reading derived from the spec: accumulated and listed individually. CA confirmation advisable | Pass 2, Stage 8 | Not built. Now: built 6 Nov 2026 as an interim reading (D59); see the section on Pass 2, feature 1 |

## Senior (engagement lead) and the Spine's owner

| # | Decision | Needed before | Meanwhile |
|---|---|---|---|
| B1 | Withdrawn misstatements in the Spine: a proposed adjustment cannot be deleted (`alembic/versions/0004_spine_version.py:404`) and counts in the Spine's own aggregate until accepted, whatever its note (D22 there). Options: refuse in the Spine with a note tagged withdrawn, accepting that the Spine's own gate differs from ours; or ask the Spine's owner for a withdrawn status **Interim treatment, 5 Nov 2026 (D41), not a decision:** the first option is built. A withdrawal refuses the Spine's adjustment with a note that says it was withdrawn by the auditor and why, so it can never be accepted and post. **Still open, for the Spine's owner:** the Spine's own uncorrected aggregate and gate still count the item, because the Spine has no withdrawn status | The Spine's owner, before anyone relies on the Spine's own gate | Built as described; the difference is documented, not hidden **Now:** open, for the Spine's owner; holds N8 since the last focused review |
| B5 | The "approaching materiality" band below OM at which the strategy prompt fires **Mechanism built, 5 Nov 2026 (D45), band still undecided:** `OAK_STRATEGY_TRIGGER_FRACTION` is the fraction of overall materiality at which the trigger fires. It has no default; unset, the trigger is not evaluated and every evaluation says so. When set, the answer to the prompt is recorded as an event and goes stale when the figures or thresholds change. **Still open:** what the band is, who sets it, and whether an unanswered prompt should hold anything up (today it blocks nothing) | The engagement lead or the firm, before the trigger is relied on | Not evaluated unless a fraction is declared; no value is assumed |
| B9 | Roles: who may raise, communicate, set thresholds, acknowledge the soft gate, escalate and conclude; whether concluding is partner-only. **Partly built, 4 Nov 2026 (D36):** identity is required on every write and refused when missing or implausible; it is taken from the request's identity source and never from its body (a body naming an actor is a 422); it is recorded on every row and frozen at the database (migration 0006 freezes the engagement's audit columns too); every answer declares `enforced: false`, the identity mode and whether it is production grade. **Partner actions enforced, 4 Nov 2026 (D39):** the soft-gate acknowledgement needs the authenticating proxy's role claim (`OAK_AUTH_ROLES_HEADER`) to name the acting identity the firm's partner value (`OAK_PARTNER_ROLE`), and fails closed (403, nothing written) otherwise: no configuration, dev mode, a missing, duplicated or look-alike claim, a non-partner. No role is read from a body or inferred from a name. **Code complete (D39, D40):** enforcement fails closed at every step, the claim is believed only from a proxy address listed in `OAK_TRUSTED_PROXIES` (a configured header alone is never enough), the peer is checked independently, and a contract test fails any future partner-only route that lacks the dependency. **No interim assumption.** **Pending externally:** (a) the firm wiring its identity provider to present the claim through the proxy and naming the partner value (with O1), until which partner actions are unavailable; (b) the firm's policy for who may raise, communicate and set thresholds, which the spec leaves to anyone and which no general role model governs; (c) the conclusion (Stage 4) declaring the same dependency, which the contract test will demand **Stage 5 (D45):** the conclusion is the second partner-only action, on the same role claim, failing closed; point (c) is done | (a) and (b) firm | Partner actions unavailable and declared so on every answer; everything else open to any authenticated identity **Now:** (a) consolidated into O1; (b) open, for the firm, and holds S10 and N6 |
| B10 | Whether the conclusion may be saved on an unlocked Spine version; whether the pinned version is chosen here or inherited from the Binder's link; whether an engagement may be re-pointed to a successor version once misstatements exist Stage 5 (D45) saves a conclusion on a locked or an unlocked version alike, records the lock state on the row, and marks the conclusion stale if anything changes afterwards **Investigated 5 Nov 2026 (D46):** the Spine refuses to lock a version while any adjustment is proposed, so a locked version holds only decided ones; unlocking creates one successor and copies every adjustment to it, each copy naming its origin in `copied_from_id` with the same reference, lines and status. A record here could therefore follow its adjustment to the successor without guessing. That is a design, not a decision: it needs the lead's agreement that an engagement may be re-pointed, a place to record the copy's id (the link on a final version cannot be rewritten), and proof against the live Spine. **Until then an engagement cannot move to a successor version once it has misstatements, so nothing new can be raised after an unlock.** | The engagement lead, before a conclusion on an unlocked version is relied on; re-pointing before any is built | Stage 1 refuses changing the pinned version once a misstatement exists, with a 409 naming B10. Stage 4 (D43) records an evaluation run on a locked or an unlocked version alike and stores the lock state on the run; a run concludes nothing, and a later change makes it stale |
| B12 | Refusal reason categories, or free text (the literal reading) | Closed from the specification, 5 Nov 2026 | Free text, mandatory, not blank. Spec section 2, paragraph 9: "A refusal reason is mandatory. No blank refusals." It names no categories; adding them would be an enhancement for the firm to ask for |
| F4 | Withdrawn only from communicated (the diagram's reading); whether a raised-in-error item may exit earlier | Closed from the specification, 5 Nov 2026 | Built as the diagram of spec section 3.3 draws it. **Consequence for the lead to know:** an item raised in error must be communicated to management before it can be withdrawn; and because the Spine cannot lock a version while any adjustment is still proposed (N17), every raised item must reach a final state before the lock. A direct exit from `raised` would be a change to the spec |
| F9 | What may change after communication, and how an amount change is represented in the Spine (same problem as B1: a proposed adjustment's lines cannot be changed, `0004_spine_version.py:337`) **Investigated 5 Nov 2026 (D46):** the Spine has no call that changes an adjustment: its API proposes and decides, and its database refuses a line once the adjustment is decided. So a changed amount can only be a new adjustment, with the old one refused. That is what withdrawing and raising again already does. **Interim workflow, not a decision:** to correct an error, communicate the item, withdraw it with the reason, and raise a new one; both stay on the schedule. An in-place edit needs the lead's answer on what may change. | Before any edit is built | Still no edit endpoint after Stage 3. The database trigger of migration 0007 already allows a new version in the same open state, so an edit can be a new version when this is decided (D41) |

## Firm (deployment and operations)

| # | Decision | Needed before | Meanwhile |
|---|---|---|---|
| O1 | Authenticating reverse proxy, identity provider, `OAK_TRUSTED_PROXIES`, TLS | Go-live | `OAK_AUTH=dev` in development; production refuses it **Now:** open; holds B9a since the last focused review |
| O2 | Running `scripts\db\02_create.sql` and applying migrations to `oak_misstatements_test`, then `oak_misstatements` | Applying migrations to `oak_misstatements`, when you approve it | **Partly done 5 Nov 2026:** both databases and both roles created by a person; migrations 0001 to 0010 applied to `oak_misstatements_test` and the full suite passes on it (442 passed, none skipped). `oak_misstatements` is empty and unmigrated |

## Found by the closure review of 5 November 2026

Items the review found that were not in this register. Evidence for each is in
`docs/CLOSURE_REVIEW.md`.

| # | Item | Who or what it waits on | State |
|---|---|---|---|
| N1 | The two read-only gate endpoints approved as D18 | — | **Closed 5 Nov 2026 (D46).** `GET /api/engagements/{id}/gates/opinion` and `.../gates/sign-off`, each open, blocked or undetermined with the figures |
| N2 | D20 no longer described practice | — | **Closed 5 Nov 2026.** D20 amended: interim treatments are built only on instruction and always labelled |
| N3 | This register's header and its acceptance 4 wording were stale | — | **Closed 5 Nov 2026.** Corrected above |
| N4 | Nothing was committed to git; no CI | The firm, for a remote and CI | **First commit made 5 Nov 2026, on instruction:** `0bf54c0d99cc5d3d305436b92352f6d3a2e9d313`, 122 files, on `master`. Still open: no remote is configured and there is no CI **Now:** closed in the final targeted review: a first commit exists, and a remote and CI are not requirements of the specification. Later work is committed only on instruction |
| N5 | Python dependencies were not locked | — | **Closed 5 Nov 2026.** `backend/requirements-lock.txt` holds the exact versions the suite passes on. Still open, minor: the test client's use of `httpx` is deprecated upstream |
| N6 | Reads need no identity; access is not scoped to an engagement | Firm, with B9 and O1 | **Open.** Confidentiality rests on the proxy **Now:** consolidated into B9b in the last focused review; the question stays open there |
| N7 | The Spine records its own service identity, not who acted here | Spine's owner | **Open.** Our actor travels in the decision note |
| N8 | The Spine's own uncorrected gate and this module's can disagree | Spine's owner and the lead | **Open.** Differences documented (B1, B11, D38) **Now:** consolidated into B1 in the last focused review; the question stays open there |
| N9 | Orphan Spine proposals could not be found again | — | **Closed 5 Nov 2026 (D46).** `GET /api/engagements/{id}/spine-reconciliation`, read-only |
| N10 | The communication date is the moment of recording | Lead, only if an entered date is wanted | **Closed as meeting the specification** (section 2, paragraph 8) |
| N11 | Event kinds and payloads were not validated, which D13 approved | — | **Closed 5 Nov 2026 (D46).** A CHECK on the kind (migration 0010) and a payload check before every insert |
| N12 | The schedule is not filterable or paged by the API | — | **Closed 5 Nov 2026 (D48).** The schedule screen filters by band, type and state in the browser, over the list the API returns. Still true and not a spec requirement: nothing is paged |
| N13 | Evaluation runs that conclude nothing (D43, D44) | Lead | **Open.** The spec's row has `concluded_by` as its only actor **Now:** closed from the specification (section 9) in the resolution pass |
| N14 | "The conclusion must address both" gross and net | — | **Closed as meeting the specification.** Both are saved on the row; the words are the partner's (section 12) |
| N15 | A judgemental range is not compared with the point estimate | — | **Closed: the specification states no rule** |
| N16 | A projected item's sample reference is free text | Pass 2 (Sampling) | **Open, with Pass 2** |
| N17 | The Spine cannot lock a version while any adjustment is proposed | Lead, to know | **Open, operational.** Every misstatement must reach a final state, and every orphan proposal must be refused in the Spine, before the Spine version can be locked **Now:** closed in the final targeted review as a recorded fact, not a decision |

## Found while building the screens (Stage 6), 5 November 2026

Stage 6 built the screens of spec section 10 (architecture D47 to D51) and listed what they
did not do. The closure work that followed (architecture D52; `docs/CLOSURE_REVIEW.md`
section 11) dealt with every row. Each now carries one of five statuses: **Resolved**,
**Implemented, awaiting external integration**, **Requires external decision**, **Cannot be
verified in the current environment**, or **Deferred to Pass 2**. A row is resolved only
where the code was built and tested; none is resolved by a document.

| # | Item | Who or what it waits on | State |
|---|---|---|---|
| S1 | Thresholds had no screen | — | **Resolved 5 Nov 2026 (D52).** `#/engagements/{id}/thresholds`: set and revise; the three lines, the declared fraction, the basis, who set them and when; the check against the Spine's PM; every version; every recorded recompute (acceptance 2). Tested on the backend's captured answers and verified live in the isolated preview |
| S2 | No screen created an engagement, linked it to the Spine or recorded a misstatement | — | **Resolved 5 Nov 2026 (D52).** `#/engagements/new`, the link form on the Financial Spine screen, and `#/engagements/{id}/misstatements/new`. Tested and verified live in the preview. One limit, raised as S13 |
| S3 | The conclusion and the soft-gate acknowledgement could not be recorded from a screen | The firm: the proxy and the partner's role claim (B9a, O1) | **Implemented, awaiting external integration.** Both forms are built on the evaluation screen and tested on answers captured from the backend run behind a trusted proxy with a role claim. They are offered only where the backend reports that a partner can be named. In this environment no partner can be named: the refusal was verified live (403, nothing written); a successful acknowledgement or conclusion has never been made through a browser (V12) **Now:** closed in the final targeted review: the forms are built and tested. What is left is V12 and O1 |
| S4 | The detail screen holds a copy of the state diagram to decide which moves to offer | — | **Resolved from the specification.** The diagram is the spec's own (section 3.3) and is fixed by it; the copy decides only which buttons appear, a test pins it to the spec, and the backend refuses any other move, which was verified. No API states the open moves; none is needed to meet the spec |
| S5 | The running totals do not follow the schedule's filters | CA or lead | **Requires external decision.** The spec says "running totals at the top against CTT, PM and OM ... always visible" (section 10.1) and defines one aggregate, of uncorrected misstatements (section 4.1); it does not say the totals narrow with a filter. The backend's aggregate of the whole engagement is kept, and the screen says the filters do not change it. Totalling a filtered subset would be a second aggregation rule, which is not the screen's to invent **Now:** closed from the specification in the resolution pass |
| S6 | Percentages against the three lines are computed on the screen, to one decimal place | CA | **Requires external decision, minor.** The spec asks for "a percentage" and gives no precision; D16 places percentages at presentation. They are exact, with integers, rounded half up. One decimal place is kept until someone says otherwise. **Display corrected 5 Nov 2026 (D54):** a figure strictly below a line no longer reads 100.0%; it reads 99.9%. The precision and the rounding are unchanged and are still the CA's **Now:** closed in the resolution pass as a presentation choice (D54) |
| S7 | On a phone the running totals scrolled with the page | — | **Resolved 5 Nov 2026 (D52).** The spec says "always visible". The totals are now pinned at every width, set smaller on a phone so that the four figures and the three percentages fit; verified in a browser at 375 pixels on live data |
| S8 | The evaluation marks a figure at or above PM and OM, never at CTT | CA | **Requires external decision.** The spec makes CTT a line for a single item ("below it, not accumulated", section 4) and names the aggregate test against overall materiality; the backend has an aggregate gate at PM and at OM and none at CTT. The percentage of CTT is shown, as section 10.1 asks; a mark would assert a test that neither the spec nor the backend defines **Now:** closed from the specification in the resolution pass |
| S9 | Every move of a misstatement asks for a confirmation first | Lead | **Requires external decision, minor.** The spec is silent. Every move is irreversible, so the confirmation is kept as the safe behaviour **Now:** closed from the specification in the resolution pass |
| S10 | Any signed-in identity can move a misstatement, record a run, answer the strategy prompt, set thresholds and record a misstatement | Firm (B9b) | **Requires external decision.** The spec reserves the acknowledgement and the conclusion to the partner (sections 7 and 12) and is silent on the rest; the backend enforces the first two and nothing else. A screen cannot decide who may act and does not try to **Now:** consolidated into B9b; the question stays open there |
| S11 | The Spine reconciliation and the event log had no screen | — | **Resolved 5 Nov 2026 (D52).** `#/engagements/{id}/spine` and `#/engagements/{id}/events`, both read-only over the existing routes. Tested, and verified live in the preview |
| S12 | One page title for every screen, focus not moved on navigation, no favicon | — | **Resolved 5 Nov 2026 (D52).** Each screen has its own title; focus moves to the content when the screen changes; a control skips to the content; a favicon is served. Checked in a browser with real key presses, and the contrast of every piece of text on every screen computed at three widths: none below 4.5 to 1. Not done: a session with a screen reader |
| S13 | The recording form cannot offer the Spine's ledgers or Schedule III heads to pick from: the backend has no route that lists them, so a line is entered by its import line number, or by name, groups and head | Lead, for a read-only route over the Spine's balances and tree | **Requires external decision.** Found by the closure work. The form meets the API as it is and the backend refuses a line that does not exist, in its own words. A picker needs a new backend route, which was not added **Now:** closed from the specification in the resolution pass: not a requirement; a picker stays an optional improvement |
| S14 | Clearly trivial misstatements were counted in the aggregate, against spec section 2 (the row for SA 450 paragraph 5) and section 4. A rule of the backend (D38), not of a screen. Set out in full under the table | CA, for question 2 | **Implemented 5 Nov 2026 (D53, D56, D57).** A clearly trivial item is named and left out of the aggregate while such items together stay below the threshold; once together they reach it, all of them are accumulated. Of the nine questions raised, eight are closed on the specification's or the standard's text, without CA approval, and question 7 is Pass 2. **Still open: question 2**, narrowed to how "in aggregate" is measured |

### S14 · Clearly trivial misstatements were accumulated

**Status: implemented 5 November 2026 (architecture D53, then D56 and D57). Nine questions
were raised; one, question 2, is still open, in a narrower form.** The rule was first built
on the instruction of 5 November 2026 to apply sections 2 and 4 as written, and then
corrected against SA 450 paragraph A2. No CA decision is recorded or assumed. Each question
below gives the treatment built and where it now stands; the sections "Resolution pass" and
"S14 question 2 re-examined" at the end of this file give the reasoning.

**What the specification says.**

- Section 2, the row for SA 450 paragraph 5 (line 27). The requirement: "Accumulate
  misstatements **other than those clearly trivial**". What the module is to do: "A
  clearly-trivial threshold per engagement, documented, and everything above it accumulates."
- Section 4, the clearly trivial band (line 81): "Below it, not accumulated. The threshold
  itself is documented."
- Section 4, the accumulated band, CTT → PM (line 82): "Accumulates, goes in the schedule."

**What the module did.** `aggregate()` in `backend/src/oak_misstatements/core/gates.py`
summed every uncorrected, resolved misstatement whatever its band (D38), so an item below
CTT was inside every aggregate figure, every gate, every run and every conclusion. The
aggregate was overstated, never understated.

**What it does now (D53, D56, D57).** An uncorrected item whose band is clearly trivial is
left out of every sum and named in `not_accumulated`, in the evaluation and in each run,
**while the items that are clearly trivial one by one together stay below the threshold,
gross, on both measures. Once together they reach it on either measure, all of them are
accumulated** and named in `not_accumulated_total.accumulated_together` (D57). A judgemental
item whose range reaches the threshold is not clearly trivial and is accumulated at its
point estimate (D56). Every item stays in the schedule and in the list of items. The gates, the strategy trigger, the runs, the
acknowledgement, the strategy answer and the conclusion all read the one aggregate and
follow it. Corrected, withdrawn, refused, projected, unresolved and classification-only
items are treated as before. No model, migration, route or database rule changed.

**What it changed in what the module reports.**

- **Aggregate figures.** Lower wherever a clearly trivial amount had been counted.
- **Materiality gates.** A gate that fired only because of clearly trivial amounts that
  together are below the threshold no longer fires. Once such amounts together reach the
  threshold they are accumulated and the gates see them (D57).
- **Evaluation runs.** A run records what it left out. Raising a clearly trivial item makes
  the latest run stale without moving a figure.
- **Acknowledgements and strategy answers.** Tied to the figures, so a clearly trivial item
  that stays left out leaves them standing; one that brings the group into the aggregate
  changes the figures and makes them stale.
- **Conclusions.** The run reviewed must still describe the items; a clearly trivial item
  raised after the review refuses the conclusion until a new run is reviewed.

**The nine questions, the treatment built, and where each stands.** None was answered by
the CA.

1. **Item or measure.** An item's band is the higher of its two bands (D33, an assumption;
   B3). An item of ₹5,000 on profit before tax and ₹50,000 on net assets bands accumulated.
   Does its ₹5,000 enter the profit aggregate, or is each measure filtered on its own band?
   *Built:* the item's band decides; both effects are in, or neither. Closed from the
   specification in the resolution pass.
2. **Trivial in aggregate.** Thirty items of ₹12,000 come to ₹3,60,000, above PM. SA 450
   paragraph A2 calls clearly trivial matters clearly inconsequential "whether taken
   individually or in aggregate". *Built (D57):* the items that are clearly trivial one by
   one are totalled gross on each measure; below the threshold on both they are left out
   and named; at or above it on either, all of them are accumulated and the gates see
   them. **Still open, for the CA:** the standard gives no number for "in aggregate"; the
   threshold itself, gross, on either measure is a reading. (Earlier treatments, no total
   and no warning under D53 and a note only under D56, are superseded.)
3. **Classification-only items.** They band clearly trivial because both effects are nil
   (B2). *Built:* listed in the aggregate at nil, as before. No figure depends on it. Closed
   from the specification in the resolution pass.
4. **The schedule.** Line 82 says accumulated items go "in the schedule"; section 10.1 says
   "every misstatement, filterable by band". *Built:* every item stays on the schedule.
   Closed from the specification in the resolution pass.
5. **Clearly trivial items that were communicated or refused.** *Built:* treated like any
   other clearly trivial item; the state changes nothing. Closed from the specification in
   the resolution pass. Whether they belong in the TCWG communication and the
   representation list is Pass 2.
6. **Projected items below CTT.** *Built:* treated as a factual item would be. Closed from
   the specification in the resolution pass.
7. **Escalated items below CTT** (F5, Pass 2). F5 reads them as accumulated and listed
   individually. *Built:* nothing; escalation is Pass 2 and is not counted among the open
   Pass 1 items. The rule will need the exception when it is built.
8. **A revised CTT.** *Built:* items move into and out of the aggregate with their bands as
   soon as the thresholds are revised. Tested. Closed from the specification in the
   resolution pass.
9. **A judgemental item whose range reaches the threshold.** An estimate of ₹8,000 with a
   range of ₹2,000 to ₹3,00,000 has a point estimate below the threshold and a range far
   above it. SA 450 paragraph A2 treats any uncertainty whether an item is clearly trivial
   as not clearly trivial. *Built (D56):* where either end of the range reaches the
   threshold the item is accumulated, at its point estimate; a range wholly below the
   threshold leaves it clearly trivial. Closed on the standard's text in the resolution
   pass. (The earlier treatment, the point estimate alone deciding, is superseded.)

## Verification that only real systems can give

On 5 November 2026 the databases were created and V1 to V4 were done on
`oak_misstatements_test`. The main database `oak_misstatements` exists and is empty: no
migration has been applied to it. Nothing touching the Financial Spine has been done.
V9 to V13 concern the screens; what was done for them was done in a preview that kept
nothing (D52).

| # | What is unverified |
|---|---|
| V1 | Whether migrations 0001 to 0010 apply. **Done on `oak_misstatements_test`, 5 Nov 2026.** All ten applied cleanly as the owner role; the schema matches the models exactly. Not yet applied to `oak_misstatements` |
| V2 | The 32 database tests: triggers, grants, the money domain and every CHECK. **Done on `oak_misstatements_test`, 5 Nov 2026.** All 32 pass. The first run failed 4; each was a fault in the test, and in each the database had refused the operation. No rule was changed |
| V3 | The engagement row lock, and whether the application role may take it. **Done on `oak_misstatements_test`, 5 Nov 2026.** The application role takes the lock with its column-level rights, and every API test runs as that role. **Still open:** two requests truly at the same moment have not been exercised **Now:** verified in the last focused review (D58): requests at the same moment are serialised |
| V4 | Exact money and time on PostgreSQL. **Done on `oak_misstatements_test`, 5 Nov 2026.** The whole API suite passes on PostgreSQL with the money domain and zoned timestamps |
| V5 | The live Spine's answers: engagement, version, balances, adjustments and the Schedule III tree |
| V6 | The live Spine's writes: propose, decide once, the 409s; acceptance 11 on the real adjusted trial balance |
| V7 | Failure paths under real conditions: a commit failing after the Spine decided; an orphan proposal |
| V8 | The Stage 7 acceptance run: criteria 1, 2, 3, 4, 6, 7, 10 and 11 end to end |
| V9 | The screens on live data. **Done 5 Nov 2026 in an isolated preview (D52):** the real application over `oak_misstatements_test`, in one transaction that was never committed, with the built frontend and a real browser. Every screen was used on rows it had itself created, at 1280, 768 and 375 pixels. **Not done, and cannot be here:** the Financial Spine was the test double (V5, V6), and `oak_misstatements` is still unmigrated |
| V10 | The writes the screens send, against a running backend. **Done 5 Nov 2026 in the preview:** creating an engagement with its Spine link; setting and revising thresholds; recording six misstatements; every move of the state machine (communicate, correct, refuse, withdraw); recording an evaluation run. Each refusal the screens can meet was met live as well: an unknown Spine engagement, PM not below OM, lines that do not balance. **Not done live:** the answer to the strategy prompt (V13), changing a Spine link after creation, a ledger the import lacks, a projected misstatement; each is tested on the backend's captured answers only |
| V11 | Eight display branches that no captured answer reached. **Done 5 Nov 2026.** Each is now reached by a real answer of the backend, captured with the Spine double moved into the situation, and tested: a judgemental range crossing PM; a state that differs from the Spine's; a ledger not matched in the Spine; an effect unresolved while the Spine is readable; a move the Spine had already decided; a stale acknowledgement; a stale strategy answer; an item at or above OM on its own |
| V12 | A partner acknowledging the soft gate and recording a conclusion through a browser. **Cannot be verified in the current environment.** It needs the firm's authenticating proxy and a role claim that names a partner (B9a, O1). No partner identity was simulated to stand in for it. Verified instead: the backend refuses all three partner-only writes with a 403 and writes nothing |
| V13 | The strategy prompt on a running backend. **Done 5 Nov 2026 with a test value (D55):** the isolated preview was run with a fraction of 0.5 set for that preview alone; the prompt fired at ₹2,00,000, the answer was recorded through its form, and the event was listed. **Still open:** the firm's own value (B5). Until one is declared the trigger is not evaluated in any real run |
| V14 | The Pass 1 workflow through the browser's own forms and buttons. **Done 5 Nov 2026 on the isolated preview** (`docs/CLOSURE_REVIEW.md` section 13): an engagement created; thresholds set and revised; factual, judgemental and projected misstatements recorded, by working paper and by manual entry, on two and on three lines, one on a ledger not in the import; unbalanced, one-sided and unknown lines refused; every move of the state machine, with the reasons; runs recorded, inspected and made stale; the soft gate, the hard gate and an item above PM blocking and released. **Not done, and cannot be here:** any partner-only write (V12) and anything against the live Spine (V5, V6) |

## Resolution pass of 5 November 2026 (architecture D56)

Every item still open was grouped and worked through. **Where this section differs from a
row above, this section is the current status.** S14 is counted by its questions; question 7
(escalated items) is Pass 2 and is not counted. Nothing here is an approval by the CA, the
lead or the firm: an item is "closed on the text" where the specification or the standard
answers it and the module does what the text says.

**Source for the standard.** First read as ISA 450 in the FRC's edition; then re-examined against ICAI's own text: SA 450 as reproduced by ICAI's Board of Studies ("SA 450, Evaluations of Misstatements Identified during an Audit", © The Institute of Chartered Accountants of India, 15 June 2021, live.icai.org), read on 5 Nov 2026. The official copy at kb.icai.org could not be opened: its server presents a certificate for another ICAI address, and certificate checks were not switched off. The paragraphs quoted here are numbered as in the standard and agree word for word with ISA 450; the CA should still compare them with the official copy.

### Counts

| Group | Open before | Closed in this pass | Still open |
|---|---|---|---|
| 1. Software defects or inconsistencies | 0 | 0 | 0 |
| 2. Accounting questions the standard answers | 7 | 6 | 1 |
| 3. Choices the specification answers | 13 | 13 | 0 |
| 4. Decisions for the CA, the lead, the Spine's owner or the firm | 18 | 0 | 18 |
| 5. External integration and approval | 4 | 0 | 4 |
| 6. Verification gaps | 7 | 1 | 6 |
| **Total** | **49** | **20** | **29** |

Pass 2 items are outside these counts: B6, F5, N16 and S14 question 7.

### Group 2: closed on the standard's text

| Item | Question | What the standard says | Outcome |
|---|---|---|---|
| S14 Q9 | Is a judgemental item clearly trivial when its range reaches above CTT? | A2: any uncertainty whether an item is clearly trivial, and it is not | **Changed in code (D56):** such an item is accumulated, at its point estimate |
| F3 | Which states are uncorrected? | Paragraph 4: uncorrected misstatements are those accumulated "that have not been corrected" | As built: raised, communicated and refused count; corrected does not; a withdrawn item is no longer asserted as a misstatement |
| B8 | Do projected items count toward the gates? | A3: projected misstatements are "the auditor's best estimate of misstatements in populations"; paragraphs 5 and 11 apply to misstatements without excepting them | As built: they count, and every figure and gate says whether it depends on them (spec 3.2) |
| B14 | What is "material individually"? | Paragraph 11: the auditor determines whether uncorrected misstatements are material "individually or in aggregate", considering their size and nature "both in relation to particular classes of transactions, account balances or disclosures and the financial statements as a whole" | As built: both tests are shown, each item against PM (the spec's band) and against OM on its own. The determination is the partner's words. **Limit, noted on the ICAI text:** the module tests against the financial statements as a whole only; a materiality level for a particular class or balance (SA 320) is not in the specification and is left to the partner's judgement |
| B15a | May "material" be concluded while the hard gate fires? | Paragraph 11 requires the determination, whichever way it falls; spec 7 makes the hard gate block an unmodified opinion | As built: a material conclusion is not blocked by a gate that fires; a not-material one is blocked by every gate |
| B2 | Is a classification-only item nil on amount? | A15: whether a classification misstatement is material "involves the evaluation of qualitative considerations" | As built: nil on both measures, listed, its gross size shown; its qualitative evaluation is Pass 2 |

Still open in group 2, **narrowed: S14 Q2** (clearly trivial items in aggregate). See the
next section: the principle is settled by A2 and built; the measure of "in aggregate" is
a reading and stays with the CA.

### Group 3: closed from the specification

| Item | Question | The specification | Outcome |
|---|---|---|---|
| S5 | Do the running totals follow the filters? | 10.1: "Running totals at the top against CTT, PM and OM"; 4.1 defines one aggregate | As built: the engagement's totals, and the screen says the filters do not change them |
| S6 | What precision for the percentages? | 10.1: "as a percentage"; no precision given | Presentation: one decimal place, half up, and never 100% below a line (D54) |
| S8 | Is a figure marked at CTT? | 4 and 7: CTT is a line for one item; the aggregate tests are at PM and OM | As built: no mark at CTT; the percentage of CTT is shown |
| S9 | Is each move confirmed first? | 3.3: every move is a new version and nothing is deleted | As built: a confirmation, because no move can be undone |
| S13 | Must the form offer the Spine's ledgers to pick from? | 3.1 and 8 require Dr/Cr lines and a working paper reference; no picker is named | Not a requirement. The form meets the API; a picker stays an optional improvement needing a new route |
| N13 | May a run conclude nothing? | 9: `evaluation` is "append-only, one row per evaluation run" | As built: a run is a row; a conclusion is another row that names the run reviewed |
| B15b | Must the partner name a current run? | Acceptance 10: the conclusion "carries the figures it was based on" | As built: a stale run is refused |
| S14 Q1 | Item or measure? | 4: the band is the misstatement's; 4.1: "A misstatement can be immaterial to one and material to the other" | As built: the item's band, the higher of its two (D33), decides; the conservative reading |
| S14 Q3 | Classification-only items | 3.1: computed flag; 4.1 | As built: listed at nil |
| S14 Q4 | Does a clearly trivial item stay on the schedule? | 10.1: "every misstatement, filterable by band" | As built: it stays |
| S14 Q5 | Communicated or refused and clearly trivial | 4: the band is computed from the amount, "never chosen" | As built: left out whatever the state |
| S14 Q6 | Projected and clearly trivial | 4, with 3.2 | As built: left out like any other, and named |
| S14 Q8 | A revised CTT | 4: "all recomputed automatically if materiality is revised" | As built, and tested |

### Group 4: still open, for people (18)

| Who | Items |
|---|---|
| CA | S14 Q2 is counted in group 2. Here: B7a (net assets as shareholders' funds, not "net worth"), B7b (share application money pending allotment), B7c (no tax effect imputed) |
| Lead | B5 (the "approaching materiality" fraction), B10a, B10b, B10c (the Spine version a conclusion and an engagement rest on), F9 (amending after raising) |
| Spine's owner, with the lead | B1 (no withdrawn status in the Spine), N7 (the Spine records its own service identity), N8 (the two modules' gates can differ), N17 (a version cannot lock while an adjustment is proposed) |
| Firm | B4a (which module is the system of record for the thresholds), B4b (a standard CTT fraction), B9b and S10 (who may raise, move, set thresholds and record a run), N6 (reads need no identity), N4 (a remote and CI) |

None of these prevents the Pass 1 implementation. Each affects production acceptance.

### Group 5: still open, external (4)

B9a, O1 and S3 (a partner named by the firm's authenticating proxy), and O2 (approval to
migrate `oak_misstatements`). Untracked but real: no Opinion module exists to be blocked,
and no Materiality module exists to take the thresholds from (B4a).

### Group 6: verification (6 open)

Closed: **V13**, the strategy prompt on a running backend, seen with a test fraction (D55).
Open: V3 (two requests at the same moment; needs a database that may be written and
dropped), V5, V6, V7 and V8 (the live Financial Spine), V12 (a named partner).

## S14 question 2 re-examined against ICAI's SA 450 — 5 November 2026 (architecture D57)

**The text.** Paragraph A2: "The auditor may designate an amount below which misstatements would be clearly trivial and would not need to be accumulated because the auditor expects that the accumulation of such amounts clearly would not have a material effect on the financial statements. … Matters that are 'clearly trivial' will be of a wholly different (smaller) order of magnitude than materiality determined in accordance with SA 320, and will be matters that are clearly inconsequential, whether taken individually or in aggregate and whether judged by any criteria of size, nature or circumstances. When there is any uncertainty about whether one or more items are clearly trivial, the matter is considered not to be clearly trivial."

**Can the question be resolved from this wording?** In principle, yes. The question was
whether items each below CTT must be accumulated when together they are not small. A2 makes
"clearly trivial" a property of matters that are clearly inconsequential individually **and**
in aggregate, rests the threshold on the expectation that accumulating such amounts would
clearly not matter, and resolves any uncertainty about "one or more items" against
triviality. Items that together are not clearly inconsequential are therefore not clearly
trivial and paragraph 5 requires them to be accumulated.

**Did the implementation reflect it?** No. Under D53 such items were left out however many
there were; under D56 their total was shown with a note, and they were still outside every
figure and every gate. Twenty-one items of ₹12,000, ₹2,52,000 in all and above PM, fired
nothing. That was wrong against A2.

**What was corrected (D57).** The items that are clearly trivial one by one are totalled
gross on each measure. Below CTT on both, they stay out and are named. At or above CTT on
either, all of them are accumulated and the gates see them; the screens name them as
"clearly trivial one by one, accumulated together". Tested at the unit and through the API.

**What is still open, and why the question is not closed.** A2 says "in aggregate" and gives
no number. The module has to compute, so three choices were made, each the one that
accumulates sooner: the total is compared with **CTT itself**; it is taken **gross**; and
**either** measure reaching it is enough. A CA could reasonably hold that the test should be
a different amount (a multiple of CTT, or a share of PM), or that it should be applied to a
class of items and not to all of them. Those are judgements the standard leaves to the
auditor. **S14 question 2 therefore stays open, narrowed to this: confirm or replace the
measure of "in aggregate".** It is counted as one open item, as before.

**The six other accounting readings, checked against the same ICAI text.**

| Item | Paragraph in ICAI's text | Outcome |
|---|---|---|
| S14 Q9 | A2, last sentence, as quoted above | Stands: a judgemental item whose range reaches CTT is accumulated (D56) |
| F3 | 4(b): "Uncorrected misstatements – Misstatements that the auditor has accumulated during the audit and that have not been corrected" | Stands |
| B8 | A3: "Projected misstatements are the [auditor's] best estimate of misstatements in populations, involving the projection of misstatements identified in audit samples to the entire populations"; evaluation of results "is set out in SA 530" | Stands: they are misstatements and are accumulated; every gate still says whether it depends on them. How a projection is derived is SA 530's and is Pass 2 (Sampling) |
| B14 | 11 and 11(a), as quoted in the table above | Stands, with the limit now recorded: no test against a class-level materiality |
| B15a | 11, and 15(c): the documentation includes "the conclusion as to whether uncorrected misstatements are material, individually or in aggregate, and the basis for that conclusion" | Stands |
| B2 | The application paragraph on classification: whether such a misstatement is material "involves the evaluation of qualitative considerations", and it may be not material "even though it may exceed the materiality level or levels applied in evaluating other misstatements" | Stands: nil on amount, listed, evaluated qualitatively (Pass 2) |

None needed a change. The wording of each paragraph in ICAI's text is the same as in ISA 450.

**Count after this re-examination.** Unchanged: **49 were open, 20 are closed, 29 remain.**
S14 question 2 is one of the 29, narrower than it was. No item was closed to reduce the
count.

## Final targeted review — 5 November 2026

The 29 items left open by the resolution pass were looked at once more, together, for any
that can be closed accurately without the CA, the lead, the firm or an external system.
**Where this section differs from anything above, this section is the current status.**
No code was changed: nothing in this review needed it. Nothing was closed that still needs
a person's decision; a merged or re-filed item keeps its open part under the ID named.

**29 were open. 7 are closed here. 22 remain.**

### Closed in this review (7)

| Item | Why it can be closed | Evidence |
|---|---|---|
| S10 | A duplicate. It asks who may raise, move, set thresholds and record a run, which is B9b; its own row names B9b as what it waits on | The decision stays open, once, under **B9b** |
| S3 | The work it tracked is done: both partner forms are built and tested, and withheld with the backend's reason where no partner can be named. What is left is not implementation: seeing it done by a named partner is **V12**, and the infrastructure is **B9a** and **O1** | `frontend/tests/partnerForms.test.tsx`, 17 tests on answers captured behind a trusted proxy; the refusal seen live |
| N17 | Not a decision. It is a fact about the Spine, recorded for the lead "to know": a version cannot be locked while an adjustment is proposed, so every misstatement must reach a final state first | Investigated and recorded in architecture D46; nothing in this module is pending on it |
| N4 | The part that concerned this project is done: the work is committed. A remote and CI are not requirements of the specification and are the firm's to arrange whenever it chooses | Two commits on `master`; the specification names no repository or pipeline |
| B4b | Answered by the specification. Section 4 makes CTT "a declared fraction of performance materiality" and says the threshold "is documented": the fraction is declared for each engagement, with its basis, and there is no default. A firm-wide prefill would be a convenience added later, not a pending decision | No default exists; a threshold without a fraction is refused (`tests/test_api_thresholds.py`) |
| B7a | Answered by the specification's own term. Sections 3.1, 4.1 and 10 say "net assets" throughout, and compute it from the Dr/Cr lines: assets less liabilities. "Net worth" under section 2(57) of the Companies Act is a different, statutory measure that the specification never names | Built as D31; `tests/test_effects.py` |
| B7c | Answered by the specification. Section 3.1: the effects are "computed" from the "set of Dr/Cr lines", and the profit measure is "profit **before tax**". An effect that is not in the lines is not computed, and there is no tax to impute on a before-tax figure; tax moves net assets only when the entry carries tax lines | `tests/test_effects.py`: a tax expense line does not move profit before tax; nothing is imputed |

### Still open (22), and why each cannot be closed here

| Needs | Items | Why |
|---|---|---|
| CA (2) | **S14 Q2** | SA 450 A2 says "in aggregate" and gives no number; the measure built (CTT itself, gross, either measure) is a reading (D57) |
| | **B7b** | Share application money pending allotment is its own head in Schedule III, neither shareholders' funds nor a liability. Neither the specification nor SA 450 says how it enters net assets; such entries are refused meanwhile |
| Lead (5) | **B5** | "Approaching materiality" (spec 7; SA 450 paragraph 6(b)) has no number in either text. Until a fraction is declared the trigger is not evaluated |
| | **B10a, B10b, B10c** | Whether a conclusion may rest on an unlocked Spine version, where the pinned version comes from, and whether an engagement may follow the Spine to a successor version. The specification is silent and each changes what the record means |
| | **F9** | What may be amended after an item is raised. The Spine cannot change an adjustment, so an amendment is a new adjustment; whether that is wanted is a choice |
| The Spine's owner, with the lead (3) | **B1, N7, N8** | Each is a property of the Financial Spine: it has no withdrawn status, it records its own service identity, and its own gate is defined differently. This module cannot change them |
| Firm (3) | **B4a** | Section 4 says the lines come "from Materiality (SA 320)". No such module exists; whether this module is the system of record meanwhile is the firm's |
| | **B9b** (with S10 merged into it) | Who may raise, move, set thresholds and record a run. The specification reserves two actions to the partner and is silent on the rest |
| | **N6** | Reads need no identity and are not scoped to an engagement. A security policy, for go-live |
| External systems and approval (3) | **B9a, O1** | The firm's authenticating proxy, identity provider and partner role claim |
| | **O2** | Approval to migrate `oak_misstatements` |
| Verification (6) | **V5, V6, V7, V8** | Need the live Financial Spine |
| | **V12** | Needs a named partner |
| | **V3** | Two requests at the same moment need committed rows; the tables allow no delete, so the test would leave rows behind, and no role here may create a disposable database |

### Looked at and deliberately left open

- **V7 and V8** are tested against the Spine double and were walked in a browser (V14). They
  stay open because each is defined as a run against the real system.
- **B9a and O1** overlap but are not the same thing: one is the role claim and the partner
  value, the other is the proxy, the identity provider and TLS. Both are kept.
- **V3** was considered for the test database and rejected for the reason in the table.

## Last focused review — 5 November 2026

The 22 items left by the final targeted review were looked at once more.
**Where this section differs from anything above, this section is the current status.**

**22 were open. 4 are closed here. 18 remain.** One was closed by verification; three were
consolidated into the item that already holds the same question. A consolidated item is
not resolved: its question stays open, once, under the ID named.

### Closed in this review (4)

| Item | How | Evidence |
|---|---|---|
| V3 | **Verified.** Two requests at the same moment had never been exercised, because the suite runs inside one rolled-back transaction and the tables allow no delete. `backend/tests/concurrency_check.py` runs the real application against a scratch schema in `oak_misstatements_test`, built from the models, and drops the schema whatever happens. Eight requests released together from eight threads: eight misstatements were raised and given M-1 to M-8, each once; eight evaluation runs were recorded and numbered 1 to 8, each once; no request failed | Run three times, the same each time; afterwards no scratch schema remained and the `public` tables held no row. **Limits:** it ran as the owner role, on tables without the migrations' triggers, against the Spine double. That the application role may take the lock was shown earlier, in the suite |
| N8 | **Consolidated into B1.** N8 said the Spine's own uncorrected gate and this module's can disagree. Every cause is already recorded: the Spine has no withdrawn status (B1), its gate is strictly above PM (B11, closed), and it knows nothing of the clearly trivial rule (D53, D57). Which gate governs is not open: spec section 7 makes this module's gate the one that blocks the opinion. What is left is for the Spine's owner, and it is B1's question | B1 now reads: reconcile the Spine's own uncorrected schedule and gate with this module's |
| N6 | **Consolidated into B9b.** N6 is who may read; B9b is who may write. Both are the firm's access policy, decided once, and N6's own row names B9 as what it waits on | B9b now covers reads as well as writes |
| B9a | **Consolidated into O1.** B9a is the identity provider presenting a partner role claim; O1 is the authenticating proxy, the identity provider and TLS. Neither can be delivered without the other, and B9a's own row says "with O1" | O1 now covers the role claim and the partner value |

### Still open (18)

| Needs | Items | Why it cannot be resolved here |
|---|---|---|
| CA (2) | **S14 Q2** | SA 450 A2 gives no number for "in aggregate"; the measure built is a reading (D57) |
| | **B7b** | How share application money pending allotment enters net assets. Schedule III gives it its own head, neither shareholders' funds nor a liability; the specification is silent. Such entries are refused meanwhile, and no rule is assumed |
| Lead (5) | **B5** | No text gives a number for "approaching materiality" |
| | **B10a, B10b, B10c** | Which Spine version a conclusion and an engagement rest on. The specification is silent, and the answer changes what the record means |
| | **F9** | Whether, and what, may be amended after an item is raised |
| The Spine's owner (2) | **B1** (with N8) | The Spine's own uncorrected schedule and gate differ from this module's |
| | **N7** | The Spine records its own service identity, not the person who acted here |
| Firm (2) | **B4a** | The specification takes the thresholds "from Materiality (SA 320)"; no such module exists |
| | **B9b** (with S10 and N6) | Who may read, raise, move, set thresholds and record a run |
| External systems and approval (2) | **O1** (with B9a) | The firm's proxy, identity provider and partner role claim |
| | **O2** | Approval to migrate `oak_misstatements` |
| Verification (5) | **V5, V6, V7, V8** | Each is defined as a run against the live Financial Spine. They are four different checks (reads, writes, failure paths, the acceptance run) and are kept apart |
| | **V12** | Needs a partner named by the firm's identity provider |

### Looked at and left as they are

- **B7b** was not settled from Schedule III: treating the head as equity or as a liability
  for net assets would be a new accounting rule, and entries on it are rare and refused.
- **V5 to V8** share one dependency but are not one check; merging them would hide work.
- **B10a to B10c** concern one subject but are three separate answers.

## Pass 2, feature 1: qualitative factors and escalation — 6 November 2026 (architecture D59)

Pass 2 began on 6 November 2026, on instruction, with spec section 5. This section records
what that feature leaves to people. It does not change the Pass 1 count above (18 open).

**F5 is now built**, as an interim reading: an escalated item is accumulated whatever its
band and is listed individually. It was "not built" until now. The reading rests on SA 450
paragraph A2 ("whether judged by any criteria of size, nature or circumstances"); it is not
a CA approval.

| # | Question | Who | What is built meanwhile |
|---|---|---|---|
| Q1 | Is an escalated item accumulated even when it is below CTT? (F5) | CA | Yes: never left out as clearly trivial, and outside the group that D57 totals |
| Q2 | Does an escalated item block sign-off, or need the partner's acknowledgement? Spec section 7 lists the gates and does not name escalation | CA and the lead | No: it is listed individually and blocks nothing |
| Q3 | May a factor be recorded or cleared on a misstatement in a final state (corrected, refused, withdrawn)? | Lead | Yes, in any state; only an uncorrected item is listed in the evaluation |
| Q4 | Who may record and who may clear a factor? | Firm (with B9b) | Any authenticated identity, as for the module's other writes |
| Q5 | Is a reason required to clear a factor? The specification asks for a recorded reason to escalate and is silent on clearing | Lead | Yes: the reason is mandatory both ways, and both stay in the history |
| M1 | Applying migration 0011 to `oak_misstatements_test`, and later to `oak_misstatements` | Whoever approves migrations (with O2) | **Applied to `oak_misstatements_test` on 6 Nov 2026, on approval**; the PostgreSQL suite passes with it (486 passed). Not applied to `oak_misstatements`, which still waits (O2) |

**Screens added the same day (architecture D60).** They decide none of the questions above
and show what is built: the checklist is offered in every state (Q3), to any signed-in
identity (Q4), a reason is asked for both ways (Q5), and the evaluation lists an escalated
item without blocking sign-off (Q2).

## Pass 2, feature 2: prior-period carry-forward — 6 November 2026 (architecture D61)

Built on instruction on 6 November 2026. **B6 is not decided.** What is built is an interim
reading that takes no accounting decision: every figure of a carried item is a person's, and
no gate reads it. This section records what the feature leaves to people. It does not
change the Pass 1 count (18 open).

| # | Question | Who | What is built meanwhile |
|---|---|---|---|
| P1 | Should the gates (hard at OM, soft at PM, the strategy trigger, sign-off) test the aggregate **with** prior-period items, and on which basis: current-period, cumulative, or either? SA 450 paragraph 11(b) has the auditor consider them; spec section 7 does not say | CA and the firm | No gate reads them. The evaluation shows the two together on both bases and says which measures reach PM and OM. An aggregate that reaches OM only with prior-period items is shown and does not block |
| P2 | How are the current-period effect and the cumulative effect of a prior-period item arrived at? (B6) | CA | Both are entered by a person, on profit before tax and on net assets, with a mandatory basis. Nothing is computed |
| P3 | Where does a carried item come from: the Spine's prior version's uncorrected schedule, another engagement of this module, or entry by hand? Does it carry Dr/Cr lines? (B6) | Lead and the Spine's owner | By hand, or rolled forward from a misstatement of another engagement here. No lines. Its figures are held in this module because it has no Spine adjustment. An engagement has no period, so the module cannot check that the other engagement is the prior period's |
| P4 | Is a carried item banded, and may one be left out as clearly trivial? | CA | No: none is banded and every carried item is in the prior-period totals |
| P5 | Is "with prior-period items" rightly the current year's aggregate (which leaves out clearly trivial items and includes projected ones) plus the prior-period total, gross with no netting between a carried item and a current-year one? | CA | Yes, that sum, shown gross and net |
| P6 | Must a carried item be rolled forward only from a concluded engagement, and must it be removed here when management corrects it in the current year? | Lead | Rolled forward from any misstatement uncorrected there now; removed by a person, with a reason |
| P7 | Who may record, revise and remove a carried item? | Firm (with B9b) | Any authenticated identity, as for the module's other writes |
| M2 | Applying migration 0012 to `oak_misstatements_test`, and later to `oak_misstatements` | Whoever approves migrations (with O2) | **Applied to `oak_misstatements_test` on 6 Nov 2026** by the PostgreSQL suite, which was asked for with this feature (506 passed). Not applied to `oak_misstatements`, which still waits (O2) |

**Not built with this feature:** revising an item and rolling one forward from the screen
(both are in the API); prior-period items on the schedule screen; any detection that an
item reversed or still stands.

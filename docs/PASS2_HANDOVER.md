# Pass 2 handover — Misstatements Rollup (SA 450)

Prepared 9 November 2026 from the specification (`docs/MISSTATEMENTS_ROLLUP.md`), `README.md`,
`docs/DECISIONS_PENDING.md`, `docs/architecture.md` (D59 to D66), the migrations and the
test files, with the databases read the same day, read-only. It follows
`docs/PASS1_HANDOVER.md` and continues from it. This is a documentation-only report. It
closes nothing, reclassifies nothing and approves nothing.

**Status in one line.** The Pass 2 implementation is complete, tested and committed
(features 1 to 7, the last at commit `650a33e`). It is **not accepted for production**, and
this report does not claim that it is ready for it.

## 1. The seven Pass 2 deliverables (spec section 11)

All paths are under `/api`. Each feature was built on instruction and each rests on readings
that no CA or firm has approved; section 4 lists them.

| # | Deliverable | Endpoints | What it does | Architecture |
|---|---|---|---|---|
| 1 | Qualitative factors and escalation (spec section 5; acceptance 8) | `GET /misstatements/{id}/qualitative` · `POST /misstatements/{id}/qualitative` · `POST /misstatements/{id}/qualitative/{factor}/clear` | The seven factors of spec section 5 as a checklist on each misstatement. Recording or clearing a factor needs a reason and appends an entry. An escalated item is accumulated whatever its band and is listed individually (F5, as an interim reading). The detail screen has the checklist; the schedule marks an escalated row | D59, D60 |
| 2 | Prior-period carry-forward (SA 450 paragraph 11(b); acceptance 5) | `GET /engagements/{id}/prior-period` · `GET .../prior-period/candidates` · `POST .../prior-period` · `POST .../prior-period/{ref}/revisions` · `POST .../prior-period/{ref}/removal` | Prior-period uncorrected items, each with a current-period and a cumulative effect on profit before tax and net assets, entered by a person with a basis, or rolled forward from another engagement here. The evaluation shows the current year alone and with the prior-period items on both bases. A run saves what it saw (`evaluation.py_carried`). No gate reads these figures (B6 is not decided) | D61 |
| 3 | The TCWG extract (SA 450 paragraph 12; acceptance 9) | `GET /engagements/{id}/tcwg-extract` | Read-only, computed on read. Names every uncorrected item above PM and every escalated item individually, summarises and lists the rest by type, gives the totals, the effect on the opinion as the gate reads it, and the request to correct. Its own tab, which prints | D62 |
| 4 | Written representation attachment (SA 450 paragraph 14) | `GET /engagements/{id}/rep-letter-attachment` | Read-only, computed on read. The summary of uncorrected misstatements by type with every row, the prior-period items apart, the representation statement, and cautions for the auditor that block nothing. Its own tab, which prints with the auditor's panel left off | D63 |
| 5 | Intake hooks (spec section 8) | `POST /engagements/{id}/intake/wp` · `.../intake/run` · `.../intake/note` · `.../intake/manual` | One hook per source. A working-paper or manual entry needs its working paper reference; an agent run needs its run id and at least one source-row citation; a review note needs its reference and may carry a link. The origin is kept with the record and shown on the detail and in the schedule's Source column | D64 |
| 6 | Projected misstatements from Sampling (SA 530; spec 3.2) | The raise and intake endpoints, with the sampling fields | A projected item says how it was projected: method, population value and size, sample value and size, misstatement found in the sample. All are required on a projected item and refused on any other. The projected amount is the Dr/Cr lines; `projected_amount` in the request must equal their debits and is not stored | D65 |
| 7 | The generated working paper (SA 230; SA 450 paragraph 15; spec 6 item 5) | `GET /engagements/{id}/working-paper` · `POST .../working-paper/export` · `GET .../working-paper/exports` · `GET /working-papers/{id}` | The whole record as one paper, with the three things paragraph 15 requires checked as fields. An export freezes the paper against the current evaluation run with a SHA-256 of its content, append-only, and is refused without a current run or when nothing has changed. A registered paper is read back with its hash recomputed. Its own tab, with the export and print | D66 |

**One instruction was not followed.** Feature 6 was asked to let a projected item accumulate
"without requiring balanced ledger-level journal entries to be posted to the Spine". The
specification says the opposite (sections 1 and 3.1; acceptance 1), and an item without
lines has no effect to band or aggregate (D31). It was not built and is recorded as J1.

**Screens.** Three tabs were added to each engagement: "TCWG extract", "Representation
attachment" and "Working paper". The record form, the misstatement detail, the schedule and
the evaluation screen gained the parts named above.

## 2. Architecture and migrations

Pass 2 kept the Pass 1 architecture: amounts live in the Financial Spine as Dr/Cr lines;
every record of this module is append-only; figures are computed in the backend, in exact
decimals, and the screens show what the API answers. Features 3 and 4 store nothing.
Feature 7 generates the paper from the same reads the screens make and computes no figure
the evaluation does not compute.

| Migration | What it adds | Rules it adds |
|---|---|---|
| 0011 | Table `qualitative`: one row per entry against one factor of one misstatement | Append-only and no-truncate triggers; `SELECT, INSERT` only for the application role; the factor held to the seven by a CHECK; reason and actor never blank |
| 0012 | Table `prior_period`: one row per version of a carried item. Column `evaluation.py_carried` (nullable), what a run saw of the carried items | Append-only and no-truncate triggers; `SELECT, INSERT` only; money columns in the `money_amount` domain |
| 0013 | Column `misstatement_version.origin` (nullable JSON): the run id and citations, or the note reference and link | CHECKs on the shape of the origin for each source |
| 0014 | Nothing new to hold | Two further CHECKs that read a missing key as empty, so that it fails. In PostgreSQL a CHECK whose result is NULL passes, and 0013's checks let a missing `run_id` or `note_ref` through. Nothing is dropped |
| 0015 | Six nullable columns on `misstatement_version`: the sampling method, population value and size, sample value and size, misstatement found in the sample | Five CHECKs: all present on a projected item and absent on any other; sizes at least one; the sample no larger than the population. The three money columns take the `money_amount` domain |
| 0016 | Table `working_paper`: one row per export, with the content, its hash, the evaluation run it rests on, who exported and when | Append-only and no-truncate triggers; `SELECT, INSERT` only; `paper_no` unique per engagement; the hash checked as 64 lowercase hex; the run and the engagement cannot be deleted from under it |

- **Tables.** Eight at migration 0010; eleven at 0016. The three new ones are in the
  application's own append-only guard (`models/guard.py`) as well as behind the triggers.
- **Rules kept.** No migration after 0007 drops anything; each adds rules. No existing row
  is touched by any of the six. The money columns of 0012 (a carried item's effects) and
  the three of 0015 (the sample's values) were added to the allowed list in
  `tests/test_models.py`, each with its reason: they are a person's figures, like the
  judgemental range, and not amounts of an adjustment.
- **Where they are applied.** To `oak_misstatements_test` only: 0011 on explicit approval,
  0012 to 0016 by the PostgreSQL suite runs asked for with each feature. An intermediate
  draft of 0014 was applied to the test database and reversed there by a one-off script
  before the final 0014 was applied (D64). None is applied to `oak_misstatements` (O2).
- **One existing database test changed.** `working_paper` references `evaluation`, so
  PostgreSQL refuses a plain `TRUNCATE evaluation` before any trigger. The test now accepts
  either refusal for the plain form and requires the append-only refusal for
  `TRUNCATE evaluation CASCADE`, as the misstatement test already did. No trigger, grant or
  constraint was changed for it.

## 3. Tests and latest known results

| Check | Latest result | When |
|---|---|---|
| Backend `pytest` on PostgreSQL (`oak_misstatements_test`, rolled back) | 580 passed, 0 skipped | 7 November, on the tree committed as `650a33e`. Not rerun since; nothing has changed since |
| Backend `pytest` on the in-memory stand-in | 540 passed, 40 skipped (the database-only tests) | 7 November, the same tree |
| `ruff check`, `ruff format --check` | Clean, 122 files | Rerun 9 November |
| `mypy` strict | Clean, 105 source files | Rerun 9 November |
| Frontend `vitest` | 428 passed, 25 files | 7 November, the same tree |
| `tsc --noEmit`, `eslint`, `prettier --check` | Clean | Rerun 9 November |
| Production build | Succeeds | 7 November |
| Captured API answers used by the screen tests | 184, regenerated from the real API | 7 November |

*Note, 9 November 2026, later the same day: four tests of the demo seed were added after
this table was written (architecture D67). The suite is now 584 passed on PostgreSQL and
544 passed, 40 skipped in memory, and it has passed once on GitHub (section 6, point 7).*

**Growth over Pass 1.** PostgreSQL 469 to 580; `vitest` 319 to 428, 18 files to 25;
captured answers 122 to 184. No test was deleted.

| Feature | Backend test file (test functions) | Frontend test file (tests) |
|---|---|---|
| 1 Qualitative | `test_api_qualitative.py` (13) | `Qualitative.test.tsx` (23) |
| 2 Prior period | `test_api_prior_period.py` (13) | `PriorPeriod.test.tsx` (18) |
| 3 TCWG extract | `test_api_tcwg.py` (15) | `TcwgExtract.test.tsx` (19) |
| 4 Representation attachment | `test_api_representation.py` (17) | `RepLetterAttachment.test.tsx` (16) |
| 5 Intake hooks | `test_api_intake.py` (10) | `Intake.test.tsx` (12) |
| 6 Sampling | `test_api_sampling.py` (9) | `Sampling.test.tsx` (7) |
| 7 Working paper | `test_api_working_paper.py` (11) | `WorkingPaper.test.tsx` (14) |

Each feature also added to the shared files: the database rules (`test_db_rules.py`, 37,
PostgreSQL only), the migration SQL (`test_migration_sql.py`, 28), the models, schemas and
labels, the fixture producer (`test_frontend_fixtures.py`, 14 scenarios), and on the
frontend the app-wide accessibility and integration tests, which visit every tab.

### What was verified, and against what

**On real PostgreSQL (the test database only).** Migrations 0001 to 0016 apply; the
triggers, grants and constraints of the three new tables and the new columns hold; the
whole API suite passes there.

**In a real browser, on a running backend.** One session per feature on the isolated
preview: the real application over the test database in one transaction that was never
committed, the Spine test double, the development identity. In every session the
engagement, and usually its thresholds and misstatements, were seeded through the preview's
API first.

| Feature | Seen in the browser |
|---|---|
| 1 | A factor recorded through the form on a clearly trivial item; the schedule's mark and the totals moving from one item to two; the evaluation's list; the factor cleared through the form |
| 2 | A prior-period item recorded through the form; its two effects and the three sets of totals; the note where the two together reach PM while the soft gate stayed clear; a run recorded and inspected with its carried items; the item removed, which made the run stale |
| 3 | The extract from its tab: two items named individually, the rest summarised and listed, the clearly trivial item outside the communication, the opinion effect and the request; no sideways scroll at 375 and 1280 pixels |
| 4 | The attachment from its tab: the breakdown by type, every row, the statement, two cautions and the clearly trivial item left out; no sideways scroll at 375 and 1280 pixels |
| 5 | A misstatement recorded through the form from an agent run: the record button disabled until the run id and a complete citation were typed; the detail and the schedule showing the run |
| 6 | A projected misstatement recorded through the form: a projected amount differing from the lines refused in the backend's words; the corrected one recorded; the detail and the schedule showing the sample |
| 7 | The paper from its tab with the paragraph 15 checklist and hash; the export registering paper 1 on run 1; a second export refused as unchanged; the registered paper's hash recomputed and matching; no overflow at phone width |

**Only against the Spine test double, never the live Financial Spine.** Everything that
touches the Spine, as in Pass 1: every raise through every hook, the lines and
classification behind every effect, and so every figure in the extract, the attachment and
the paper.

**Only by automated test, with no real identity provider.** A working paper that documents
a partner's conclusion, and a run that carries `py_carried` into a conclusion. The tests run
the real code behind a configured trusted proxy. In a browser every paper read
"Documentation incomplete", because no partner can be named there.

**Only by the shape of what was sent.** The intake hooks: no WorkMind, review tool or
Sampling module is connected, so a run id, a citation, a note reference and the sampling
figures are whatever the caller sends.

**Not done at all.** A printed page or PDF produced and inspected (the print rules were
seen in the stylesheet); a delivery to the Working Paper Binder; a screen-reader session;
any run on the main database.

## 4. The Pass 2 pending register

Taken from the seven Pass 2 sections of `docs/DECISIONS_PENDING.md`, unchanged: 39 questions
and 5 migration items. They are **outside** the Pass 1 count of 18, which also stands
unchanged (`docs/PASS1_HANDOVER.md` section 4). "Built meanwhile" is what the code does
today; none of it is a decision.

| Category | Item | Question | Who | Built meanwhile |
|---|---|---|---|---|
| Qualitative | Q1 | Is an escalated item accumulated even below CTT? (F5) | CA | Yes |
| | Q2 | Does an escalated item block sign-off or need the partner's acknowledgement? | CA and the lead | No; it is listed individually |
| | Q3 | May a factor be recorded or cleared on an item in a final state? | Lead | Yes |
| | Q4 | Who may record and clear a factor? | Firm (with B9b) | Any authenticated identity |
| | Q5 | Is a reason required to clear a factor? | Lead | Yes |
| Prior period | P1 | Should the gates test the aggregate with prior-period items, and on which basis? | CA and the firm | No gate reads them; both bases are shown |
| | P2 | How are the current-period and cumulative effects arrived at? (B6) | CA | Entered by a person with a basis; nothing computed |
| | P3 | Where a carried item comes from, and whether it carries Dr/Cr lines (B6) | Lead and the Spine's owner | By hand or rolled forward from another engagement here; no lines |
| | P4 | Is a carried item banded, and may one be left out as clearly trivial? | CA | No |
| | P5 | Is "with prior-period items" the current year's aggregate plus the prior-period total, gross? | CA | Yes |
| | P6 | Roll forward only from a concluded engagement; remove on correction? | Lead | From any item uncorrected there; removed by a person with a reason |
| | P7 | Who may record, revise and remove a carried item? | Firm (with B9b) | Any authenticated identity |
| TCWG extract | T1 | Which items are named individually? | CA | Every uncorrected item above PM and every escalated item |
| | T2 | Do clearly trivial items that were communicated or refused belong in the communication? | CA | No; named apart |
| | T3 | The wording of the request, and its addressee | Firm | One plain sentence; no addressee |
| | T4 | Should the extract be recorded when communicated? | Lead | Not recorded |
| | T5 | How should the opinion effect treat prior-period items? (with P1) | CA and the firm | The gate's reading of the current year; prior-period items shown apart |
| | T6 | May the other items be communicated as a number and an overall effect only? | Lead | Both a summary and the full list |
| Representation | R1 | The wording, the letter, and who signs | Firm | One plain sentence; no letter or signature block |
| | R2 | Should a caution stop the attachment being produced? | CA and the lead | No; shown, none blocks |
| | R3 | Do clearly trivial items that were communicated or refused belong in the list? (with T2) | CA | No |
| | R4 | Should the attachment be tied to a run and recorded when sent? (with T4) | Lead | Not recorded |
| | R5 | Every row or the summary alone; lines on a row? | Lead | Both; no lines |
| | R6 | How prior-period items appear, and whether the representation covers them (with P1) | CA and the firm | Shown apart; the statement unchanged |
| Intake | I1 | What the Spine receives as `working_paper_ref` for a run or a note | Spine's owner and the lead | The run id or the note reference |
| | I2 | Who may raise from each source | Firm (with B9b) | Any authenticated identity |
| | I3 | Should a run be checked against WorkMind before it is raised? | Lead and WorkMind's owner | No; nothing is connected |
| | I4 | What a citation must name | WorkMind's owner | A source, a row, optionally what was found |
| | I5 | Whether a note's link must be the review tool's URL, and the note marked converted there | Lead | Free text; nothing written to any tool |
| Sampling | J1 | **Should a projected item be allowed as an amount alone, without lines?** Asked for; refused by the specification; not built | CA and the lead, as a change to the specification | Balanced lines, as every misstatement |
| | J2 | Which sampling methods the firm uses | Firm | ratio, difference, mean-per-unit, monetary-unit, other |
| | J3 | Should the module recompute the projection and refuse one that does not follow? | CA | No; only the amount against the lines |
| | J4 | Are all six figures meaningful for every method? | CA | All six required |
| | J5 | Should a Sampling module supply the figures? (N16) | Lead | Typed; no such module exists |
| Binder | W1 | **Delivering the paper to the Working Paper Binder**, whose intake has no source for this module | Lead, with the Binder's owner | Registered here; the delivery answered in the Binder's shape, not sent |
| | W2 | Should an export require a recorded conclusion? | CA | Allowed on a current run; the paper says what is not documented |
| | W3 | Who may export? (B9) | Firm | Any authenticated identity; recorded |
| | W4 | The paper's reference, section and title in the firm's index | Firm | `W-SA450-<n>`, section W, placeholders |
| | W5 | Retention of this module's copy and of stale papers | Lead | Every registered paper kept |
| Migrations | M1 | 0011 on the main database | Whoever approves migrations (with O2) | Applied to the test database only, on approval |
| | M2 | 0012 on the main database | The same | Applied to the test database only |
| | M3 | 0013 and 0014 on the main database | The same | Applied to the test database only |
| | M4 | 0015 on the main database | The same | Applied to the test database only |
| | M5 | 0016 on the main database | The same | Applied to the test database only |

**By who is named.** CA, alone or jointly: Q1, Q2, P1, P2, P4, P5, T1, T2, T5, R2, R3, R6,
J1, J3, J4, W2. Engagement lead, alone or jointly: Q2, Q3, Q5, P3, P6, T4, T6, R2, R4, R5,
I1, I3, I5, J1, J5, W1, W5. Firm, alone or jointly: Q4, P1, P7, T3, T5, R1, R6, I2, J2, W3,
W4. Financial Spine's owner: P3, I1. WorkMind's owner: I3, I4. Binder's owner: W1.

**Pass 1 items Pass 2 touched without closing.** F5 is built as an interim reading (Q1).
B6 is not decided; feature 2 takes no accounting decision in its place (P2, P3). N16 stays
open (J5).

## 5. Integration status

| System | Status | What is missing |
|---|---|---|
| Financial Spine | **Test double only.** Never contacted live, in Pass 1 or Pass 2. The double was written from the Spine's source. Pass 2 adds no new kind of call: the hooks propose adjustments as before. A prior-period item has no Spine adjustment and its figures are held here (P3) | A running Spine with a test engagement (V5 to V8); the Spine's owner on I1 and P3, and still on B1 and N7 |
| Working Paper Binder | **Not connected. Nothing is sent.** Its generated-paper intake (`POST /api/binders/{binder_id}/generated-papers`) was read from its source and names five sources, none of them this module. The export registers the snapshot here and answers the delivery in the Binder's shape, marked not deliverable. The Binder was not changed | A source for this module in the Binder, or another route (W1); the firm's reference and section (W4) |
| Firm authentication | **Not wired.** The header mode behind a trusted proxy exists and is exercised by automated tests only. No identity provider is connected, so no partner can be named: partner-only writes fail closed, and every Pass 2 write is open to any authenticated identity | The proxy, identity provider and partner role claim (O1); who may do what (B9b, with Q4, P7, I2, W3); a conclusion by a named partner (V12) |
| WorkMind and the review tool | **Not connected.** The run and note hooks record what they are sent and check nothing against either system | I3, I4, I5 |
| Sampling module | **Does not exist.** The sampling figures are typed | J5, N16 |
| Materiality and Opinion modules | **Do not exist**, as at Pass 1. Thresholds are entered by hand (B4a); the hard gate has no module to block | As Pass 1 |
| Main database `oak_misstatements` | **Not migrated.** No tables | Approval (O2, M1 to M5) |

## 6. What prevents production acceptance

Everything in `docs/PASS1_HANDOVER.md` section 5 still stands, except that the work is now
committed. Pass 2 adds:

1. **Pass 2's accounting readings are not approved by a CA.** They change or shape figures
   and documents: an escalated item is accumulated below CTT (Q1); prior-period effects are
   a person's and no gate reads them (P1, P2, P4, P5); which items the TCWG extract names
   (T1, T2) and the attachment lists (R3); a paper may be exported without a conclusion
   (W2).
2. **The paper does not reach the binder** (W1). SA 230 documentation is generated and
   frozen here, and stays here.
3. **No paper documents a conclusion in a real run**, because no partner can be named (O1,
   V12).
4. **The wording of the request to correct and of the representation is this module's own**
   (T3, R1), not the firm's.
5. **Nothing external checks what the hooks receive** (I3, I4, J5).
6. **Six more migrations wait for the main database** (M1 to M5, with O2).
7. **CI runs, and proves only what the tests prove.** The GitHub remote `origin`
   (`github.com/surya70104/misstatements`) is configured and `master` is pushed to it. A
   workflow, `.github/workflows/ci.yml`, was added on 9 November: lint and type checks,
   the frontend tests, and the backend tests in memory and on a PostgreSQL service
   (architecture D67). It ran on GitHub on the push of commit `81bd638` the same day (run
   1, 04:22 UTC) and all three jobs succeeded, including the creation of the roles and
   databases in the service container and `pytest` on PostgreSQL there. So the tests no
   longer run on this machine only. CI uses the Spine test double and a throwaway
   database, like the local suite: it is not a run against the live Financial Spine, a
   named partner or the main database, and it changes nothing in points 1 to 6.

*Corrected 9 November 2026, twice. Point 7 first read "There is still no remote and no
CI"; the remote was configured the same day and the workflow added after it. It then read
"CI has not yet run"; the workflow ran and passed once it was pushed.*

## 7. External access, approval or verification still required

In addition to `docs/PASS1_HANDOVER.md` section 6:

| Needed | From | For |
|---|---|---|
| CA review of the Pass 2 readings | CA | Section 6, point 1; the CA's items in section 4 |
| A source for this module in the Binder, or another route | Lead and the Binder's owner | W1 |
| The firm's wording, sampling methods, binder reference and roles | Firm | T3, R1, J2, W4; Q4, P7, I2, W3 |
| A decision on J1, as a change to the specification or not | CA and the lead | Feature 6 |
| WorkMind's citation contract and a run to check against | WorkMind's owner | I3, I4 |
| Approval to apply 0001 to 0016 to `oak_misstatements` | Whoever owns that decision | O2, M1 to M5 |
| A printed page or PDF of the three documents, inspected | A person | Features 3, 4 and 7 |

## 8. Explicit confirmations

- **The main database has not been migrated.** Read on 9 November, read-only:
  `oak_misstatements` has no tables. `oak_misstatements_test` has its eleven tables at
  migration 0016 and no data rows.
- **CAF and Working Paper Binder have not been changed.** Both show no working-tree changes
  in git; their last commits are 23 October and 1 November 2026, as at Pass 1. They were
  read as references only.
- **The live Financial Spine was never contacted**, and no write was sent through the
  development servers on ports 8003 and 3003.
- **No partner identity was simulated.** Partner-only behaviour was tested through the real
  header-mode code behind a configured trusted proxy.
- **Pass 2 is committed.** Seven feature commits, the last `650a33e` on 7 November; the
  working tree was clean before this report. This report and the `README.md` change that
  goes with it are not committed.
- **No financial figure is computed in the frontend**, and none in floating point.

## 9. Documentation notes

- `README.md` said, under its Pass 1 endpoint table, that the Pass 2 endpoints were "the
  qualitative checklist, the prior-period carry-forward and the TCWG extract". It now names
  all seven features. Its stage table now reads "Pass 2 implementation complete; production
  acceptance pending".
- The note at the head of `docs/PASS1_HANDOVER.md` says Pass 2 "has begun". It is dated
  6 November and is kept as written; this report is the current position.
- The opening of `docs/DECISIONS_PENDING.md` gives the status of 5 November, 18 open. That
  is the Pass 1 count and is still right. The Pass 2 items are in the seven sections at the
  end of that file and are summarised in section 4 above.
- The test counts in each README feature section and each architecture section are those
  of their own dates. The latest are in section 3 above and in the README's feature 7
  section.

**Not changed by this report:** any application code, test, schema, migration or
configuration; the wording of any dated section; the Pass 1 list of 18 open items; the
Pass 2 register.

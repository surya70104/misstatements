# Pass 1 handover — Misstatements Rollup (SA 450)

*Note added 6 November 2026. This report describes Pass 1 as it stood on 5 November. Since
then the Pass 1 work has been committed, and Pass 2 has begun, on instruction, with
qualitative factors and escalation (architecture D59). Statements below that Pass 2 has
not started and that the work is uncommitted were true on 5 November.*

Prepared 5 November 2026 from the specification (`docs/MISSTATEMENTS_ROLLUP.md`), `README.md`,
`docs/DECISIONS_PENDING.md`, `docs/CLOSURE_REVIEW.md` and `docs/architecture.md`. This is a
documentation-only report. It closes nothing, reclassifies nothing and approves nothing.

**Status in one line.** The Pass 1 implementation is complete and tested. It is **not
accepted for production**, and this report does not claim that it is ready for it.

## 1. The seven Pass 1 deliverables (spec section 11)

| # | Deliverable | Status |
|---|---|---|
| 1 | Misstatement record with Dr/Cr lines over the Spine | Built and tested. Factual, judgemental and projected items; balanced lines enforced; amounts live in the Spine, not here. Used through the browser form |
| 2 | Three thresholds with automatic banding and recompute | Built and tested. Versioned OM, PM and a declared clearly-trivial fraction; every band recomputed on revision and the recompute recorded. Thresholds are entered by hand (see B4a) |
| 3 | State machine with mandatory refusal reasons | Built and tested. Raised, communicated, corrected, refused, withdrawn; reasons mandatory; nothing deleted |
| 4 | Aggregation gross and net, profit and net assets | Built and tested. With and without projected items, by type. Clearly trivial items are left out, unless together they reach the threshold (D53, D57) |
| 5 | The schedule screen | Built and tested, with the detail, evaluation, thresholds, Financial Spine and events screens |
| 6 | Hard gate at overall materiality | Built and tested, in the write path and as a database rule. Also the soft gate at PM, the block on an item above PM, and the strategy trigger (inactive until B5) |
| 7 | The documented conclusion | Built and tested: mandatory words and basis, the run reviewed, figures saved with it, partner only. **Never recorded by a real partner** |

## 2. Tests and latest known results

| Check | Latest result | When |
|---|---|---|
| Backend `pytest` on PostgreSQL (`oak_misstatements_test`, rolled back) | 469 passed, 0 skipped | After D57. Not rerun since; no application source has changed since |
| Backend `pytest` on the in-memory stand-in | 437 passed, 32 skipped (the database-only tests) | After the last review |
| `ruff check`, `ruff format --check`, `mypy` strict | Clean, 89 files | After the last review |
| Frontend `vitest` | 319 passed, 18 files | After D57. No frontend change since |
| `tsc --noEmit`, `eslint`, `prettier --check`, production build | Clean; build succeeds | After D57 |
| Captured API answers used by the screen tests | 122, regenerated from the real API | After D57 |
| Concurrency check (`backend/tests/concurrency_check.py`) | Passed, three runs | Last review (D58) |

## 3. What was verified, and against what

**On real PostgreSQL (the test database only).** Migrations 0001 to 0010 apply; the database
rules (triggers, grants, constraints) hold; the whole API suite passes; simultaneous requests
are serialised. Limit: the simultaneous-request check ran as the owner role, in a scratch
schema built from the models without the migrations' triggers.

**In a real browser, on a running backend.** Three sessions on an isolated preview: the real
application over the test database in one transaction that was never committed. Driven
through the forms and buttons: creating an engagement; setting and revising thresholds;
recording factual, judgemental, projected, manual and three-line misstatements; refusals of
unbalanced, one-sided and unknown lines; every state move with its reasons; filters; gross
and net totals; runs recorded, inspected and made stale; soft gate, hard gate and an item
above PM blocking and released; the strategy prompt answered. In the second and third
sessions some data was seeded through the preview's API before the screens were used.

**Only against the Spine test double, never the live Financial Spine.** Everything that
touches the Spine: proposing, accepting and refusing adjustments; reading ledgers and the
Schedule III tree for the effects; the PM comparison; the reconciliation; acceptance
criterion 11. The double was written from the Spine's source code.

**Only by automated test, with no real identity provider.** A partner's acknowledgement and
conclusion succeeding, and their staleness. The tests run the real code behind a configured
trusted proxy. In a browser only the withheld state was seen: the forms are not offered and
the reason is shown. The conclusion form itself has never been rendered in a real browser.

**Only by automated test.** A PM gate set to hard; the Spine unreachable; a state the Spine
disputes; an orphan proposal; a failed commit; release of an item above PM by withdrawal.

**With a test value.** The strategy prompt was seen with a fraction of 0.5 set for one
preview. The firm's value is not decided (B5), so the trigger is inactive in any real run.

**Not done at all.** A screen-reader session; any run on the main database.

## 4. The 18 pending items, by responsible party

Taken from the last section of `docs/DECISIONS_PENDING.md`, unchanged.

| Party | Items | Subject |
|---|---|---|
| CA (2) | S14 Q2 | How to measure clearly trivial items "in aggregate". Built: the threshold itself, gross, on either measure (a reading of SA 450 A2) |
| | B7b | How share application money pending allotment enters net assets. Such entries are refused meanwhile |
| Engagement lead (5) | B5 | The "approaching materiality" fraction for the strategy trigger |
| | B10a, B10b, B10c | Which Spine version a conclusion and an engagement rest on |
| | F9 | Whether, and what, may be amended after an item is raised |
| Financial Spine's owner (2) | B1 (with N8) | The Spine's own uncorrected schedule and gate differ from this module's |
| | N7 | The Spine records its own service identity, not the person who acted |
| Firm (2) | B4a | The spec takes thresholds from a Materiality module; none exists |
| | B9b (with S10, N6) | Who may read, raise, move, set thresholds and record a run |
| External systems and approval (2) | O1 (with B9a) | The firm's authenticating proxy, identity provider and partner role claim |
| | O2 | Approval to migrate `oak_misstatements` |
| Verification (5) | V5, V6, V7, V8 | Runs against the live Financial Spine |
| | V12 | A conclusion and an acknowledgement by a named partner |

Pass 2 items are outside this count: B6, F5, N16 and S14 question 7.

## 5. What prevents production acceptance

1. **No named partner.** The conclusion and the soft-gate acknowledgement have never been
   made end to end (O1, V12).
2. **No run against the live Financial Spine** (V5 to V8).
3. **The main database is not migrated**, and migrating it needs approval (O2).
4. **Accounting treatments are not approved by a CA.** Three were built on instruction or on
   the text of SA 450 and change figures: clearly trivial items are not accumulated (D53); a
   judgemental item whose range reaches the threshold is accumulated (D56); clearly trivial
   items that together reach the threshold are accumulated (D57). Other readings were closed
   "on the text" (F3, B8, B14, B15a, B2, B7a, B7c, S14 questions 1, 3 to 6, 8 and 9). None of
   these is a CA approval. S14 Q2 and B7b are still open.
5. **The standard was not read from ICAI's official copy.** The official PDF could not be
   opened (certificate mismatch on the server). ICAI's Board of Studies reproduction of
   SA 450 and the FRC's ISA 450 were read instead.
6. **Open decisions of the lead, the Spine's owner and the firm** (section 4).
7. **No Opinion module exists** for the hard gate to block, and **no Materiality module**
   to supply the thresholds.
8. **The work is not committed.** The repository has two commits (Stages 0 to 5). Stage 6
   and all closure work exist only in the working tree: 58 changed or new entries counting
   this report, nothing staged. There is no remote and no CI.

## 6. External access, approval or verification still required

| Needed | From | For |
|---|---|---|
| Authenticating proxy, identity provider, partner role claim | Firm | O1, V12 |
| Access to a running Financial Spine with a test engagement | Spine's owner | V5 to V8 |
| Approval to migrate `oak_misstatements` | Whoever owns that decision | O2 |
| CA review of the accounting treatments and the two open questions | CA | Section 5, point 4 |
| Comparison of the quoted SA 450 paragraphs with ICAI's official copy | CA | Section 5, point 5 |
| Decisions in section 4 | Lead, Spine's owner, firm | B5, B10a to B10c, F9, B1, N7, B4a, B9b |
| A screen-reader session | A person | Accessibility |
| Review of the uncommitted work, then a commit | Project owner | Section 5, point 8 |

## 7. Explicit confirmations

- **Pass 2 has not started.** None of its items is built: qualitative factors and
  escalation, prior-period carry-forward, the TCWG extract, the written representation
  attachment, intake from agent runs, review notes and Sampling, the generated binder paper.
- **The main database has not been migrated.** Read today, read-only: `oak_misstatements`
  has no tables. `oak_misstatements_test` has its eight tables at migration 0010 and no data
  rows.
- **CAF and Working Paper Binder have not been changed.** Both show no working-tree changes
  in git; their last commits are 23 October and 1 November 2026. They were read as
  references only.

## 8. Conflicts found in the documentation, and how each was reconciled

Six conflicts were found when this report was first written. They were reconciled the same
day, in the documents only. The rule followed: a dated section is a record and keeps its
words; where it no longer describes the project it now carries a note that says so and
points to the current text. Nothing was closed or reclassified by the reconciliation.

1. **"Complete" versus "not declared complete".** Reconciled. `README.md` (stage table,
   row 6) now reads "Pass 1 implementation complete; production acceptance pending". The
   statements "not declared complete" in `docs/architecture.md` (D52) and in
   `docs/CLOSURE_REVIEW.md` sections 11 and 12 are kept as written and each is followed by
   a note that section 13 supersedes it. `docs/CLOSURE_REVIEW.md` opens with a guide that
   states the current position.
2. **S14 question 2.** Reconciled to the code (D57). The S14 section of
   `docs/DECISIONS_PENDING.md` now describes the rule built: clearly trivial items are left
   out while together they stay below the threshold and are all accumulated once together
   they reach it. The earlier treatments in `docs/CLOSURE_REVIEW.md` sections 13 and 14 and
   in `docs/architecture.md` (D53, D56) are marked as superseded. The question itself stays
   open, narrowed to how "in aggregate" is measured.
3. **S14 question 9.** Reconciled to the code (D56). The register's S14 section now says a
   judgemental item whose range reaches the threshold is accumulated; the earlier statements
   in `docs/CLOSURE_REVIEW.md` section 13 and `docs/architecture.md` (D55) are marked as
   superseded.
4. **"Eight questions".** Reconciled. `README.md` and the register's S14 row and section now
   say nine. The two historical mentions of eight (`docs/CLOSURE_REVIEW.md` section 12,
   `docs/architecture.md` D53) are kept and each carries a note that a ninth was added.
5. **Item statuses in the register.** Reconciled. `docs/DECISIONS_PENDING.md` now opens with
   the current count (18 open) and where the list is. Twenty-three rows whose status had
   moved end with a note beginning "Now:", and the S14 row was brought up to date. Each note
   only repeats what a later section of the same file already recorded; rows of items that
   are still open say that they are open.
6. **Test counts.** Reconciled. `README.md` marks one section as holding the latest results
   and says every other count is that of its own date; its file count was corrected to 89.
   `docs/CLOSURE_REVIEW.md` opens with the latest results and the same statement. The dated
   counts were not altered.

**Not changed by the reconciliation:** the wording of dated sections beyond the added notes;
the list of 18 open items; any application code, test, schema, migration or configuration.

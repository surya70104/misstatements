# Misstatements Rollup — architecture and agreed decisions

Decisions are numbered and dated. A decision is changed by adding a new one that supersedes
it, not by editing the old one. Requirements come from `docs/MISSTATEMENTS_ROLLUP.md` only.
Accounting and business questions the specification leaves open are listed in
`docs/DECISIONS_PENDING.md` and are never resolved in code until a person answers them.

## D1 · Standalone project — 4 Nov 2026

The module lives at `D:\MISSTATEMENTS_ROLLUP`, in its own git repository, with its own
virtual environment, `.env`, databases and roles. It never reads or modifies the Financial
Spine project at `D:\CAF` or the Working Paper Binder at `D:\WORKING PAPER BINDER`, their
databases, roles or `.env` files. Integration with the Spine, the Binder, WorkMind and
Sampling goes through HTTP APIs only, each configured by a URL that may be unset.

## D2 · Stack mirrors the Spine and the Binder — 4 Nov 2026

Backend: Python 3.11, FastAPI, SQLAlchemy 2, Alembic, psycopg 3, pydantic-settings.
Frontend: React 19, TypeScript, Vite, Tailwind 4, the Binder's plain Vite setup, with ESLint
and Prettier from the Spine. Tests: pytest and hypothesis; vitest with Testing Library.
Lint: ruff with the union of the Spine's and the Binder's rule sets; mypy strict.
Reason: one skill set and one database server across OAK modules.

## D3 · Ports — 4 Nov 2026

API on 8003, frontend on 3003. Test doubles for other modules start at 8013. The Spine
(8000, 3000), the Binder (8001, 3001) and this module can run together.

## D4 · Node through fnm — 4 Nov 2026

Node 22 is selected with fnm. `frontend/.node-version` pins it and `frontend/.npmrc` makes
npm refuse any other version, so the system Node 18 on PATH is never used by accident.

## D5 · Separate databases and roles — 4 Nov 2026

Two databases on the existing PostgreSQL 16 server: `oak_misstatements` and
`oak_misstatements_test`. Two roles: `oak_misstatements_owner` (migrations) and
`oak_misstatements_app` (the running API, no DDL, no UPDATE or DELETE on append-only
tables). The create script checks that none of these names exist and stops without changing
anything if one does. It is run once, by a person, as the PostgreSQL superuser; passwords are
set in psql afterwards and never written to a file in this repository. Connection strings
live only in `backend\.env`, which git ignores.

The settings refuse any database URL that does not name one of the two databases, that is
not on the loopback interface, or whose user is not the role the URL is for: the application
URL must connect as the app role, the migration and test-owner URLs as the owner role. A
wrong URL fails at startup, before any connection is attempted.

## D6 · Append-only at the database — 4 Nov 2026

Spec section 9 names `misstatement` and `evaluation` as append-only. Two layers will enforce
it: UPDATE and DELETE revoked from `oak_misstatements_app` on those tables, and a BEFORE
UPDATE, DELETE or TRUNCATE trigger that raises an integrity error for any role. Migration
0001 creates the trigger function; the tables arrive with their stages under the same rule.

## D7 · Development identity — 4 Nov 2026

`OAK_AUTH=dev` names the acting user from `OAK_DEV_USER`; development and tests only, refused
in production. `OAK_AUTH=header` takes the identity from the header an authenticating reverse
proxy sets, believed only from `OAK_TRUSTED_PROXIES`. Who may do what (raise, communicate,
set thresholds, acknowledge, conclude) is pending decision B9 and is not enforced yet.

## D8 · Engagement identity — 4 Nov 2026 (approved as T1; built in Stage 1)

One `engagement` table with the module's own id plus `spine_engagement_id` and
`spine_version_id` as plain UUID columns, no foreign keys, verified against the Spine when
set, as the Binder does.

## D9 · Append-only versioning — 4 Nov 2026 (approved as T2; built in Stage 1)

A `misstatement` row holds the stable identity (engagement, ref) and a pointer to its
current version. A `misstatement_version` row holds every field that can change. Both carry
the D6 triggers and the app role gets SELECT and INSERT only. `evaluation` is one append-only
row per run with no pointer.

## D10 · Reference never reused — 4 Nov 2026 (approved as T3; built in Stage 1)

`ref` is sequential per engagement, issued by the database, unique on (engagement, ref),
never reissued because rows are never deleted.

## D11 · Spine client and doubles — 4 Nov 2026 (approved as T4; built in Stage 1)

A client with GET plus the two POSTs the spec needs (propose an adjustment, decide it), the
Binder's error mapping, `OAK_SPINE_URL` unset meaning no Spine. `tests/fake_spine.py` holds
lines, applies accepted adjustments to its balances, refuses a second decision and refuses
writes on a locked version. `tests/local_stubs.py` serves it on 8013 for browser checks.

## D12 · Soft gate is a firm setting — 4 Nov 2026 (approved as T5; setting exists from Stage 0)

`OAK_PM_GATE` is `soft` (default, the standard's own test: a warning and a partner
acknowledgement) or `hard`. Read through settings, not a table. The gate itself is built in
Stage 5.

## D13 · One append-only event table — 4 Nov 2026 (approved as T6; built from Stage 2)

The recompute record, partner acknowledgement, strategy-trigger decision, materiality
reassessment prompt and Spine re-pointing events live in one append-only `event` table keyed
by engagement, with a kind and a JSON payload validated per kind, who and when.

## D14 · Fields the spec names but its data model omits — 4 Nov 2026 (approved as T7, T8; Stage 1)

`range_low` and `range_high` on a judgemental item; `sample_ref` and `projection_basis` on a
projected item. Each required when the type demands it.

## D15 · Our identifiers in the Spine — 4 Nov 2026 (approved as T9; Stage 1)

Our `ref` goes in the Spine adjustment's `finding_ref`; our working paper reference in its
`working_paper_ref`.

## D16 · Money — 4 Nov 2026 (approved as T10; domain exists from migration 0001)

`Decimal` in Python, the `money_amount` domain in PostgreSQL (NUMERIC that refuses more than
two decimal places, NaN, infinity and 10^15 or more), strings in JSON. Percentages against
CTT, PM and OM are computed at presentation and never stored. Whether a column may be
negative is decided per column when it is created, since effects on profit can be negative
and Dr/Cr lines cannot.

## D17 · Output formats — 4 Nov 2026 (approved as T11; Pass 2)

Every generated document is structured JSON from the API plus a markdown rendering for the
binder paper. PDF is not built unless asked. The Binder's generated-paper intake contract is
read before Stage 13.

## D18 · Gate exposure — 4 Nov 2026 (approved as T12; Stage 5)

Two read-only endpoints, one for the opinion gate and one for the sign-off block, returning
open, blocked or undetermined with the figures, plus enforcement inside this module's own
write path when the conclusion is saved.

## D19 · Pass assignment — 4 Nov 2026 (approved as F1, F2)

The strategy trigger, the individually-significant block and the soft PM gate are Pass 1,
Stage 5. All three screens are Pass 1, Stage 6, without the Pass 2 parts (qualitative
checklist, prior-period block, output links).

## D20 · Open accounting decisions are never resolved in code — 4 Nov 2026

`docs/DECISIONS_PENDING.md` lists B1 to B12. No functionality that depends on one of them is
implemented until a person answers it; where a stage would need the answer, the stage stops
and says so.

*Amended 5 Nov 2026 (D46).* That is how Stage 0 began; it is no longer the whole rule. From
4 November, on explicit instruction, interim treatments were built for B1, B2, B8, B14 and
B15 and a mechanism without a value for B5. The rule since then: an interim treatment is
built only when instructed, is the most conservative one the specification and the Spine's
contract allow, is labelled interim in the code, the answer and the register, and is never
recorded as a decision. No row of the register is closed except by the specification's own
words or by the person the row names.

## D21 · The misstatement row has no current-version pointer — 4 Nov 2026 (refines D9)

D9 said both `misstatement` and `misstatement_version` are append-only and the first holds a
pointer to its current version. A pointer must be updated, which an append-only row forbids.
So `misstatement` holds only the identity (engagement, `ref_no`, who raised it, when) and the
current version is the one with the highest `version_no`. Both tables are insert-only for
every role (migration 0002).

## D22 · The Spine is called inside the transaction that reserves the reference — 4 Nov 2026

Raising a misstatement locks the engagement row, reserves the next `ref_no`, proposes the
adjustment to the Spine with that reference in `finding_ref`, then inserts the record and
commits. If the insert or commit fails after the Spine accepted the proposal, a proposed
adjustment stays in the Spine naming a reference that does not exist here; the Spine cannot
delete it (its adjustments are immutable), so the error names the adjustment id for a person
to resolve. The reverse order would leave a record without amounts, which spec section 1
forbids, so this order is the lesser risk.

## D23 · Stage 1 isolations for B1, B2 and B7 — 4 Nov 2026

B1: the adjustment is proposed at raise time (spec section 1); no withdrawal behaviour exists.
B2: the classification-only flag is computed; the Spine's adjustment kind is chosen in one
function, `core/spine_kind.py`, which refuses a classification-only item with a 409 naming
B2 before anything is written anywhere. B7: `net_assets` is `null` with a basis naming B7;
acceptance 4 is not claimed. `docs/DECISIONS_PENDING.md` carries the detail.

## D24 · API tests run on an in-memory stand-in when no test database exists — 4 Nov 2026

The house convention is PostgreSQL-only tests. Until a person has run the create script
(pending O2) there is no `oak_misstatements_test`, so the `api` fixture falls back to SQLite
in memory, built from the models, not the migration. Those tests prove the service and API
logic: validation, the Spine calls, the record and its versions. They prove nothing about
the PostgreSQL rules (triggers, grants, the money domain), which only the `db`-marked tests
prove. The fixture says which it is using, and the README says so too.

## D25 · Stage 1 intake is working-paper or manual, and `source_ref` is the working paper — 4 Nov 2026

Spec section 8 lists five sources; the intake hooks for agent runs, review notes and
Sampling are Pass 2. Stage 1 accepts `raised_from` of `wp` or `manual`, both of which the
spec says carry a working paper reference, so `source_ref` is that reference and is sent to
the Spine as `working_paper_ref` (D15). The column allows all four spec values for Pass 2.

## D26 · The threshold record — 4 Nov 2026 (Stage 2)

One `threshold` row per version with the spec's fields (om, pm, ctt, basis, set_by, set_at,
superseded_by) plus `ctt_fraction`, the fraction a person declared, so the documented
threshold is traceable; `spine_version_id` and `spine_pm_at_set`, the Spine version the
figures were set against and the PM it showed then. A row changes exactly once, when
`superseded_by` is set to its successor; a trigger refuses any other UPDATE and the
append-only function refuses DELETE and TRUNCATE. A partial unique index keeps at most one
current version per engagement, and the self-referencing foreign key is deferred so the old
row can point at the new id before the new row exists. The app role may UPDATE only
`superseded_by`. The Spine's PM is compared on every read and a difference is reported as
`mismatch`; nothing is reconciled (pending B4).

## D27 · The clearly-trivial amount is PM times the declared fraction, to the paisa — 4 Nov 2026

The spec calls CTT "a declared fraction of performance materiality". The fraction is stored
exactly and the amount is PM times the fraction rounded half up to two decimal places, the
money domain's precision. A fraction whose amount rounds to nothing is refused. No default
fraction exists (pending B4).

## D28 · Banding takes its amount and boundary explicitly — 4 Nov 2026

`core/banding.py` sorts a non-negative amount into clearly trivial, accumulated or
individually significant against one threshold version, using the spec's own words: below
CTT trivial, from CTT to PM accumulated, above PM significant. Which amount of a misstatement
is banded is pending B3, so the caller passes it and nothing in Stage 2 does; every
misstatement answers `band: null` with a basis naming B3. An amount equal to PM is its own
band, `at_pm_boundary`, while B11 is undecided; the two readings exist as values and the
chosen one, `PM_BOUNDARY`, is `"undecided"`.

## D29 · Authorisation is not enforced, and every answer says so — 4 Nov 2026

Who may set thresholds is pending B9. The acting identity is recorded as `set_by` and no
role check exists. So that the gap is never mistaken for an approved policy, every threshold
answer carries `authorisation: {enforced: false, policy: "pending decision B9 ..."}`. The
PM-below-OM question (B13) is reported the same way, as `checks.pm_below_om` with a note,
never enforced.

## D30 · Ordering by sequence, readings by status, and two more database rules — 4 Nov 2026

Taken after the Feature 2 verification (defects D-5 to D-10). Migration 0003 was amended in
place because it had not yet been applied to any database; from now on it is frozen.

- **Threshold versions are numbered** per engagement (`version_no`, unique at the database)
  and the history is read in that order. Ordering by `set_at` was wrong in principle: the
  stand-in's timestamps have one-second precision and PostgreSQL's `now()` is the
  transaction start time, so two versions could tie and come back in random order.
- **Events are ordered by `seq`**, an identity column that is the table's primary key;
  `id` stays the stable identifier the API shows. Same reason.
- **A missing Spine PM at set time is never an ambiguous null.** `spine_pm_status_at_set`
  says which of five things the reading was: available, not set on the version, not pinned,
  Spine not configured, Spine unreachable. Two CHECKs tie the status to the amount and to the
  presence of a version id.
- **The PM cross-check compares against the version recorded on the threshold**, not the
  engagement's current pin. If the pin has changed since, the check answers
  `pinned_version_changed` with both ids and compares nothing. That holds whichever way the
  pin moved: to another version, from no version to one, or from one to none (a defect found
  in the final review of 4 Nov 2026: a threshold set while unpinned used to answer
  `not_pinned` after the engagement was pinned, which was no longer true).
- **The stored CTT equals `round(pm * ctt_fraction, 2)`** by a PostgreSQL CHECK, the same
  half-up rounding as `schemas/thresholds.py`. This rule lives only in the migration: the
  in-memory stand-in's floating-point arithmetic cannot evaluate it exactly, so the model
  does not declare it and only the `db`-marked tests prove it.
- **A successor must be a later version of the same engagement**, checked at COMMIT by a
  deferred constraint trigger, because the old row is pointed at the successor before the
  successor exists (D26). Also only in the migration, for the same reason.

## D31 · The net assets effect, profit before tax, and sections from the Spine's tree — 4 Nov 2026

Resolves B7 as decided by the engagement lead after the read-only investigation; three
points remain for the chartered accountant to confirm (see `docs/DECISIONS_PENDING.md`).

- **Sections.** Every Dr/Cr line is classified from the Financial Spine's Schedule III tree
  (`GET /api/schedule-iii/tree`), walking the head's ancestors nearest first and reading the
  face item reference, the stable key: `I(1)` is equity, `I(3)` and `I(4)` are liabilities,
  `II` is assets, `X`, `XII`, `XIII` and the later items are after profit before tax, and
  `I(2)`, share application money pending allotment, is **unresolved** because the tree
  classifies it as neither equity nor liability and this module does not guess. When no
  item is found on the chain the dotted ids are the fallback (`spine_client.py`,
  `SpineTree.section`). The tree version is recorded with every effects answer.
- **Profit before tax** is credits less debits on profit-and-loss lines above item IX
  only. Tax expense and discontinuing operations are excluded. Stage 1 counted every
  profit-and-loss head, which overstated the figure whenever a tax line was present.
- **Net assets** is assets less liabilities: the signed movement, debit positive, of every
  asset and liability line. Equity lines are outside the sum, so a direct equity entry
  moves net assets while leaving profit alone. Because the lines balance, the figure always
  equals the credits less debits on profit-and-loss and equity lines, which the tests check.
- **Classification only** now means both effects reliably known and both nil. Stage 1
  tested profit alone, which called a reserves-against-provision entry a classification.
  This is stricter than the spec's literal wording at line 51, "no effect on profit", and is
  the engagement lead's decision of 4 November 2026.
- **Unresolved lines.** When any line cannot be classified, both effects are `null`, the
  ledgers are named, and no partial total is offered; nothing is substituted with zero.
  Raising such a misstatement is refused; an existing one shows the state on read.
- **Tax is never imputed.** A tax line counts only when the entry carries one.
- **API contract.** `effects.net_assets` is now a string where it was always `null`;
  `effects.profit_before_tax` may now be `null`; `profit_basis`, `partial` and
  `tree_version` were added and each line carries its `section`; `profit_partial` is kept
  as the earlier name for `partial`; `net_assets_basis` now describes the rule instead of
  naming B7. No field was removed.
- **Limitations.** The heads of import ledgers come from the client's current map while the
  Spine version is unlocked, so an effect read later can differ from one read earlier. The
  Spine's tree is a draft; the item references are used so a renamed id does not change a
  section. The real Spine has not been called; the double mirrors its shapes. *The first
  limitation is closed by D32.*

## D32 · The classification snapshot: old effects never change silently — 4 Nov 2026

The Spine serves only its current chart-of-accounts map and its single current tree
(`api/schedule3.py` returns the `HEADS` of `TREE_VERSION`; nothing serves an older tree).
Without a record of its own, an old misstatement's effects under D31 would change whenever a
ledger was remapped or the tree moved, with no trace. So:

- **One append-only row per line per misstatement version**, `misstatement_line_class`
  (migration 0004): the Spine's ledger identity (key, name, parent chain), the head, nature,
  the head's own Schedule III item, the derived section, and the Spine version and tree
  version the classification came from. **Never a Dr or a Cr.** The amounts stay in the Spine.
- **Effects are computed on the snapshot.** On read, the live lines are fetched from the
  Spine and matched to their snapshot rows by ledger key and parent chain, the Spine's own
  identity for a ledger. The amounts are the live ones; the sections are the recorded ones.
- **Drift is reported, never applied.** The Spine's current classification is derived
  beside the snapshot and every line whose head or section differs is listed under
  `classification.drift`, with the effects the current classification would give under
  `effects_on_current_classification` for comparison. The schedule's figures do not move.
- **Unmatched is unresolved.** A live line with no snapshot row, or a snapshot row with no
  live line, makes both effects `null` and names the ledgers; nothing is guessed.
- **A new version, a new snapshot.** Versions are append-only (D9, D21); each records the
  classification it was read with, and earlier snapshots are never touched.
- **Field names.** `effects.tree_version` (added the same day under D31) is replaced by
  `effects.tree_version_at_raise` and `effects.spine_version_at_raise`; `spine.tree_version_now`
  and the `classification` block carry the current tree for comparison.
- **Limitations.** Matching relies on the Spine keeping a ledger's key and chain stable,
  which its own design promises (D15 and D23 there); a re-normalised key shows as unmatched,
  which is the safe failure. The snapshot records the Spine's answer at raise time; if the
  Spine's map was already wrong then, the snapshot preserves that reading and the drift
  report is where a later correction shows. Only version 1 is written today; Stage 3's
  transitions will call the same `snapshot_lines` for every new version. Not tested against
  a live Spine.

## D33 · Banding: both effects, the literal boundaries — 4 Nov 2026 (closes B3 and B11 at code level)

Supersedes D28. The engagement lead's decision of 4 November 2026 after the B3 and B11
investigation; the spec's wording applied literally, and one conservative reading recorded
as an assumption.

- **Both effects, separately** (spec line 93). Each of profit before tax and net assets is
  banded on its absolute value against the engagement's current threshold version, and the
  item's band is the higher of the two. "Higher wins" is the conservative reading, consistent
  with SA 450 A2's principle that doubt resolves against triviality; it is an assumption,
  not a rule either standard states.
- **The boundaries** (lines 81 to 83, 139, 141, 146, 232): below CTT clearly trivial;
  exactly CTT accumulates; from CTT to exactly PM accumulates; strictly above PM
  individually significant; the aggregate soft gate fires at or above PM and the hard gate
  at or above OM. The individual test is strict and the aggregate tests inclusive because
  that is what the spec says; the difference is kept as written. `core/banding.py` holds the
  comparisons, `soft_gate_fires` and `hard_gate_fires` wait for Stage 5.
- **Nothing banded on unresolved effects.** When either effect is `null` (D31, D32) the
  band is `null` with the reason. An unresolved item is listed individually and never
  counted as trivial; whether it blocks sign-off is Stage 5's question, with "yes until
  resolved" the recorded assumption.
- **Types.** Factual and judgemental items band on the effects as computed; for a
  judgemental item the lines are the point estimate (D14) and `range_crosses_pm` says, as
  information only, whether either end of the range in absolute terms lies above PM.
  Projected items band the same way and carry `projected: true`; whether they count toward
  the gates is still B8.
- **Classification-only items** come out clearly trivial on amount, which is right: their
  significance is qualitative (spec section 5, SA 450 A15 and A16), the Pass 2 checklist.
  Creation still waits on B2.
- **Never stored.** A band is computed on read against the current threshold version, so a
  revision changes every band on the next read, and the revision's event is the record
  (acceptance 2, now demonstrable in `tests/test_api_thresholds.py`).
- **API.** `band` and `band_basis` keep their names; `band` is now a value or `null` with the
  reason. A new `banding` block carries `bands` (profit, net assets), `amounts`,
  `threshold_id`, `threshold_version_no`, `basis`, `projected` and `range_crosses_pm`. The
  `at_pm_boundary` band and `PM_BOUNDARY` are gone; `BAND_PENDING_B3` is replaced by the
  three reasons a band can be `null`.

## D34 · Performance materiality is below overall materiality — 4 Nov 2026 (closes B13 at code level)

SA 320 paragraph 9 defines performance materiality as an amount "set by the auditor at less
than materiality for the financial statements as a whole". That is the standard's
definition, not a firm policy, so the module enforces it in both layers: `ThresholdIn`
refuses a PM equal to or above OM with a message naming the paragraph, before any row or
event is written; migration 0005 adds `CHECK (pm < om)` on `threshold`, so a direct write
cannot bypass the request. Migration 0003 stays frozen; 0005 is a separate step whose
`ALTER TABLE ... ADD CONSTRAINT` validates every existing row, and a row that fails would
stop the migration, which is the right outcome. The `checks.pm_below_om` field is kept on
every answer, now always true, with a note that says it is enforced; `ThresholdIn.pm_below_om()`
is gone. How much below OM the firm sets PM remains its methodology, carried in `basis`.

## D35 · Interim threshold management, and the Spine read outside the lock — 4 Nov 2026 (closes B4 at code level)

Spec section 4 takes the three lines "from Materiality (SA 320)". No Materiality module
exists (the Spine's own D20 says so), so until one does:

- **This module is where OM, PM and CTT are entered**, by a person, with the basis, as
  versioned rows (D26). The Spine holds PM only; it is read when a version is set, recorded
  with a status (D30), and compared on every read of that version against the Spine version
  it was set against, with a changed pin reported (D30). **Nothing is pushed to the Spine
  and nothing is reconciled.** Whether this module becomes the system of record and pushes
  PM to the Spine's pinned version with a named source, which needs the Spine owner's
  consent, is a firm decision still listed under B4.
- **No default CTT fraction.** The fraction is declared per version (D27). A firm-level
  prefill is possible only if the firm's manual fixes one; that too is listed under B4.
- **Every version is readable by id** at `GET /api/thresholds/{id}`, so the ids a banding
  block or a recompute event carries resolve to the exact figures used, with the cross-check
  against that version's own recorded Spine version.
- **The Spine is read before the engagement row is locked.** `set_threshold` reads the PM
  for the pin it sees, then takes the row lock with a fresh read of the row. If the pin
  differs, another request re-pinned the engagement in between, and the Spine is read once
  more under the lock. The recorded version and the PM recorded for it therefore always
  belong together, and a slow Spine never holds the lock on the common path. The retry under
  the lock is the rare path and is accepted. The misstatement path (D22) keeps its Spine
  call inside the lock because there the call is a write whose reference must be reserved
  first.

## D36 · Authorisation: identity required and frozen, roles declared unenforced — 4 Nov 2026 (B9, partly open)

What the spec says about who acts: `raised_by`, `set_by`, `escalated_by` and
`concluded_by` are recorded (section 9); the soft-gate acknowledgement is "a required partner
acknowledgement" (section 7); the conclusion's words are "the partner's" (sections 6.4, 12).
It defines no roles and no approval chain. SA 220 makes the engagement partner responsible
for the engagement; it does not say who may type into a system. The identity source the
module has, a development user or an authenticating proxy's header, carries a name and
nothing else. So:

- **Required.** Every write route depends on `current_user`. No identity means no write: a
  503 in development mode without `OAK_DEV_USER`, a 401 in header mode when the header is
  missing, blank, duplicated, implausible or from an untrusted peer. Reads need none.
- **From the request, never the body.** `created_by`, `raised_by`, `set_by` and the event
  `actor` come from the resolved identity. Request bodies forbid unknown fields, so a body
  that names an actor is refused with a 422 rather than silently ignored.
- **Frozen.** Every audit column is append-only at the database: misstatement, version,
  classification snapshot and event rows never change; a threshold changes only in
  `superseded_by`, once; and from migration 0006 an engagement changes only in its two Spine
  link columns, with the application role's UPDATE narrowed to those columns and DELETE and
  TRUNCATE refused.
- **Not evidence of authorisation.** A development identity, or a proxy identity outside
  production, is never treated as proof of anything. Every answer carries `authorisation`
  with `enforced: false`, the identity mode, `production_grade` (true only for a proxy
  identity in production) and `missing`.
- **Unenforced, and why.** No role or permission check exists. Enforcing the two actions the
  spec reserves to a partner needs a role claim from the identity provider and the firm's
  policy (B9), and both actions arrive with Stage 5. Until then B9 stays open on that half;
  nothing here is to be read as approval.


## D37 · Classification-only items are reclassifications — 4 Nov 2026 (B2 at code level)

The Spine's contract, read from `D:\CAF\backend\src\oak_spine` without changing it:
`AdjustmentIn.kind` is `reclass` or `correction` and nothing else (`api/spine.py`); neither
kind carries a rule about which ledgers its lines may touch (`spine/adjustments.py`,
`propose`); an unaccepted reclass is "an unposted presentation item: listed apart, never
aggregated" in the Spine's own uncorrected schedule (`spine/uncorrected.py`); an accepted
one posts to the chain's `reclass` column and moves the adjusted balances (`spine/chain.py`).

A classification-only misstatement, both effects reliably nil (D31), is exactly what the
Spine calls a reclassification. So:

- **Proposed as `reclass`**, never as a correction. `core/spine_kind.py` is still the one
  place the kind is chosen; the 409 that named B2 is gone, and `spine_kind` on the version
  records the choice.
- **No second copy of amounts.** As for every item, the lines live in the Spine; this module
  holds the link and the labels-only snapshot (D32).
- **Band and materiality.** Both effects are nil, so both amount-based bands are clearly
  trivial; the `banding` block says `classification_only: true` and its basis says why, and
  the gross size (the debit total) is shown as `measure` so the item never looks like
  nothing. Its significance is qualitative (spec section 5), which is Pass 2.
- **In the aggregate** (D38) it is listed under `classification_only` and contributes nil to
  every measure, which is also what the Spine does with it.
- **Net assets.** An item is classification-only only when both effects are reliably known;
  an unresolved line still refuses creation (D31), so nothing is ever guessed into this kind.

**Assumption kept open for the CA (B2 row):** the spec's words are "no effect on profit";
D31 reads "classification only" as no effect on profit before tax *and* none on net assets,
so a direct equity entry is a correction. If the CA takes the literal reading, such entries
become reclassifications and the Spine's treatment of them changes with it.

## D38 · The aggregate and the gates, built ahead of Stage 5 — 4 Nov 2026 (B8 interim)

`core/gates.py` (pure) and `services/evaluation.py`, read by `GET
/api/engagements/{id}/evaluation`. Nothing is stored; every read recomputes from the
Spine's live lines, each version's recorded classification and the current threshold
version, the same inputs as every band, so the schedule and the evaluation cannot disagree.

- **Uncorrected** is every item not corrected and not withdrawn (raised, communicated,
  refused): the F3 reading, now in use and still awaiting the CA's confirmation.
- **Gross and net, profit and net assets** (acceptance 4): gross sums absolute effects with
  no netting between items; net sums them signed. Four measures.
- **Projected items** (spec 3.2; B8): every measure is also given *without* the projected
  items and with the projected gross apart. Every gate is tested both ways and reports
  `fires_without_projected` and `depends_on_projected`. The interim treatment is that
  projected amounts **count**, the conservative reading; whether they should is B8's, and
  the answer and the sign-off reason always say when a gate fires only because of them.
- **The gates** (spec section 7): a gate fires when *any* of the four measures (gross, or
  the absolute net, on either basis) is at or above its line; it names the measures that
  reached it. Hard gate at overall materiality, soft gate at performance materiality,
  `OAK_PM_GATE=hard` turns the soft gate into a block. Which measure the spec's "aggregate"
  means is not stated; testing every one and firing on any is the conservative reading and
  is recorded here as an assumption.
- **Unresolved items.** An uncorrected item whose effects cannot be determined marks the
  aggregate incomplete; a gate that does not already fire on the known items is
  `indeterminate`, which blocks. Nothing is substituted with zero.
- **Individually significant** (acceptance 6): an item banded above PM blocks while raised
  or communicated, or refused without a reason; an item that cannot be banded in those
  states blocks too. Correction, refusal with a reason and withdrawal release it (the
  transitions themselves are Stage 3).
- **Blocking is in the write path** (spec line 149): `require_sign_off_open` raises a 409
  with every reason. No write that amounts to signing off exists yet; the conclusion
  (Stage 4) and the Opinion module's call must pass through it, and the answer says so.
- **Not built:** the strategy trigger (B5 names no band; reported as `not_built`), the TCWG
  extract, the conclusion, any screen, and the Opinion-module integration.

## D39 · The partner role claim: enforced, and unavailable until the firm wires it — 4 Nov 2026 (B9, partly open)

The one partner-only action that now exists, the soft-gate acknowledgement
(`POST /api/engagements/{id}/evaluation/soft-gate-acknowledgements`), is enforced and
fails closed. `current_partner` believes a role only from the authenticating proxy, in
header mode, from a trusted peer: the proxy presents the signed-in user's roles,
comma-separated, in `OAK_AUTH_ROLES_HEADER`, and `OAK_PARTNER_ROLE` names the value the
firm's identity provider uses for an engagement partner. The header must appear exactly
once and the role must match as a whole value. Anything else is a 403 and nothing is
written: no configuration, dev mode, a missing, blank, duplicated or implausible claim, a
look-alike value, or a user without the role. A role in a request body is a 422; an
untrusted peer never gets past the identity check (401). No role is ever inferred from a
name, and no development setting grants one.

The acknowledgement is an append-only `soft_gate_acknowledged` event carrying the threshold
version, the figures acknowledged (every measure, with and without projected items), the
measures that fired, the note and the identity mode. It stands while both the threshold
version and the figures are unchanged; afterwards it is `stale` and the gate asks again.
That reading of "a required partner acknowledgement" is an assumption recorded here.

Every answer's `authorisation` block now carries `partner_actions`: `enforced: true`,
`available` (whether a trusted claim is configured), the source, and the actions covered.
`enforced: false` at the top keeps its earlier meaning: no general role model governs who
may raise, link or set thresholds.

**What B9 still needs, externally:** the firm's identity provider presenting a role claim
through the proxy and the firm naming the partner value (O1); the firm's policy for the
actions the spec leaves to anyone; and, when Stage 4 builds the conclusion, the same
dependency on that write. Until the claim is wired, partner actions are unavailable, never
open, and B9 stays partly open.


## D40 · Closing the code-level gaps of B2, B8 and B9 — 4 Nov 2026

**The role claim needs an explicitly trusted proxy.** `partner_actions_available()` is
true only when `OAK_AUTH=header`, `OAK_TRUSTED_PROXIES` is non-empty, and both
`OAK_AUTH_ROLES_HEADER` and `OAK_PARTNER_ROLE` are set. A configured header alone is never
believed: without a listed proxy address any client could present the claim itself.
`resolve_partner` checks the socket peer again, independently of the identity check, and
refuses an unlisted, unparseable or missing peer with a 403. The integration contract the
firm must meet is therefore: the API reachable only through the proxy; uvicorn run without
`--proxy-headers` so the peer is the socket's; the proxy stripping any client-sent
`OAK_AUTH_HEADER` and `OAK_AUTH_ROLES_HEADER` and setting each exactly once after sign-in;
the roles value comma-separated with the partner value as a whole token. Production already
refuses header mode without a proxy list.

**Two route contracts, enforced by `tests/test_contracts.py`.** A write that amounts to
signing off is tagged `sign-off` and declares `api.evaluation.sign_off_open`, the dependency
that evaluates the engagement and refuses with a 409 naming every reason. A partner-only
write is tagged `partner-only` and declares `current_partner` (through `PartnerDep`). The
test walks every route of the app, fails any tagged route that lacks its dependency, fails
any route whose path names a conclusion, sign-off, opinion or acknowledgement that lacks the
tag, and mounts a probe conclusion route to prove the dependency blocks and releases. No
sign-off write exists yet; the conclusion (Stage 4) will fail this test until it declares
both. No Opinion module exists, so nothing here claims to integrate with one.

**Contributions by type.** Every measure also gives `factual_gross`, `judgemental_gross`
and `projected_gross`, so the factual, judgemental and projected contributions are visible
apart as well as the with- and without-projected totals.

**B2 regressions.** A reclassification whose line later becomes unresolved loses the
classification-only verdict (both effects null, no band, listed under `unresolved`, gate
indeterminate) while its recorded `spine_kind` stays `reclass`; a large reclassification
stays in the schedule with its gross size and moves no aggregate and no gate.

**Status, in the three senses the register uses.** B2: code complete; interim accounting
interpretation that "classification only" needs nil net-assets effect as well as nil
profit effect; CA confirmation pending. B8: code complete for the aggregate, the gates and
the write-path contract; interim policy that projected amounts count, always disclosed;
CA confirmation pending; the conclusion write itself is Stage 4. B9: code complete for
partner enforcement (fails closed) and the integration contract; no interim assumption;
external integration pending (the firm's proxy and identity provider), plus the firm's
policy for the actions the spec leaves to anyone.


## D41 · Stage 3: the state machine, and what each state asks of the Spine — 5 Nov 2026

**The moves** are the diagram's and nothing else (spec section 3.3): raised to communicated;
communicated to corrected, refused or withdrawn. The three final states have no successor.
`core/states.py` holds the table; `POST /api/misstatements/{id}/transitions` is the one
write. A refusal and a withdrawal each need a reason (acceptance 3; a 422 without one, and a
CHECK at the database); a reason on any other move is refused rather than dropped.

**The trail** is the versions. Every move inserts the next `misstatement_version`; no row
is updated or deleted. The new version copies every field a move does not touch, records
the state with `communicated_at` or `decided_at` (the server's clock at the move, never a
date from the request), and gets its own copy of the classification snapshot, labels only
(D32), so its effects read exactly as before. `raised_by` never changes; `created_by` on
each version is who made that move.

**The Spine's contract**, read from `D:\CAF\backend\src\oak_spine` and not changed:
`POST /api/spine-versions/{id}/adjustments/{id}/decision` takes `accepted` or `refused`
and an optional note of at most 2000 characters; an adjustment is decided once (409
`adjustment.already_decided`); a locked version refuses (409); only an accepted adjustment
posts to the chain; the Spine records its own service identity as `decided_by`. From that:

| State here | Asked of the Spine | Effect on the adjusted trial balance |
|---|---|---|
| communicated | nothing | none |
| corrected | `accepted`, note naming our reference and who acted here | the lines post (acceptance 11) |
| refused | `refused`, note carrying management's reason | none; the Spine keeps a refused correction in its own uncorrected schedule |
| withdrawn | `refused`, note saying it was withdrawn by the auditor and why | none, and it can never post |

**Withdrawal is an interim treatment (B1 stays open).** The Spine has no withdrawn status.
A proposal left open could later be accepted there and post an item this module says was
withdrawn; refusing it makes that impossible, which is why it is done. The cost is that the
Spine's own uncorrected aggregate still counts it, so the Spine's gate and this module's
can differ on a withdrawn item. That is for the Spine's owner.

**The order of a move** leaves nothing half-done: lock the engagement row and read the
latest version; check the move; for a final state read the Spine's adjustment, which must
be `proposed` or already decided the way the move needs; write and flush the new version
and its snapshot, so a database refusal comes before the Spine is asked; send the decision
last. A Spine that refuses or cannot be reached fails the request and the transaction rolls
back. The one window left is a commit that fails after the Spine decided: the Spine then
holds a decision this module has not recorded.

**Disagreement is reported, never repaired.** Every misstatement answer carries
`state_consistency`: the state here, the adjustment status it expects and the one the
Spine holds. The evaluation lists disagreeing items and blocks sign-off on them. That also
covers a decision taken in the Spine directly, which this module cannot prevent: an
uncorrected item the Spine has accepted has moved the trial balance, and the answer says so
instead of hiding it. Repeating the move the Spine's status matches records it without a
second decision; any other move is refused because the Spine decides once.

**At the database** (migration 0007, rendered and tested as SQL only): five CHECKs tie
dates and reasons to the state, and an INSERT trigger holds each new version to the next
number and to a move the diagram draws, with nothing after a final state. A new version in
the same open state is allowed, for the edits F9 has yet to define.

**Who may move a state.** Any authenticated identity, as the spec defines no role for
these moves (B9). Identity is required and recorded exactly as on every other write.

**Not decided here:** categories of refusal reason (B12, free text used); leaving `raised`
other than by communicating (F4, the diagram's reading used); edits after communication
(F9, no edit exists); a communication date other than the moment of recording.


## D42 · Two safety checks on Stage 3: history, and a commit that fails after the Spine decided — 5 Nov 2026

**History at the database.** No new migration was needed. Migration 0001 defines
`oak_misstatements_append_only()`, which raises for every UPDATE, DELETE and TRUNCATE and
never returns; 0002 attaches it to `misstatement` and `misstatement_version` (row triggers
for UPDATE and DELETE, a statement trigger for TRUNCATE), 0003 to `event`, 0004 to
`misstatement_line_class`. Triggers apply to every role, the owner included. The application
role is granted SELECT and INSERT only on those tables. No later migration drops, disables
or replaces any of it; 0007 only adds rules. `tests/test_migration_sql.py` asserts all of
that from the rendered SQL.

**History in the application.** `models/guard.py` refuses, on every session, a flush that
would update or delete a loaded row of those four tables and any ORM `update()` or
`delete()` statement against them. It is the same rule one layer up: a mistake is refused
before it reaches the database, and is refused on the in-memory stand-in, which has no
triggers. A move never touches the version it moves from.

**A failed commit was being reported as success. Fixed.** The session dependency committed
after the response had been produced, so a commit the database refused still answered 201
with a body describing a version that was never saved. On a final move that meant the Spine
held a decision while the client was told the state had been recorded. The dependency now
runs with `scope="function"`: the commit happens before the response is sent, and a refused
commit answers 503 saying nothing was recorded and what to check. This applies to every
write, not only to moves.

**A refused flush hid its own error. Fixed.** After a real database refusal the session
expires its loaded rows; the move's error handler then read the misstatement's reference
from an expired row, which raised a second error and turned the intended 503 into a 500.
The reference is now read before anything is written.

**Retry after the Spine decided.** The sequence for corrected, refused and withdrawn is:
lock the engagement row; read the latest version; check the move; read the Spine's
adjustment, which must be `proposed` or already decided the way the move needs; insert and
flush the version and its snapshot; send the decision; commit. If the commit fails, the
Spine holds the decision and nothing is recorded here; the answer is 503; reading the item
shows `state_consistency.consistent: false` and the evaluation blocks. Repeating the same
move finds the adjustment already decided that way, sends **no** decision, and records the
state with the note the Spine already holds. A different final move is refused, because the
Spine decides once. No second adjustment can arise: a move never proposes.

**Two requests at once.** Three things prevent a duplicate posting or a forked trail, in
order: the engagement row lock, taken before the latest version is read; the unique
`(misstatement_id, version_no)`, which refuses a second version with the same number at
flush, before the Spine is asked; and the Spine itself, which decides an adjustment once.
The second and third are exercised by tests that make a request read stale versions. The
first is PostgreSQL's and has never run: the stand-in ignores `FOR UPDATE`.


## D43 · Stage 4: both tests shown, and the evaluation row — 5 Nov 2026

**What the specification asks of Stage 4.** Section 4.1: the aggregate gross and net, for
profit and net assets separately (acceptance 4). Section 2, paragraph 11: whether
uncorrected misstatements are material individually or in aggregate, both tests, both
shown. Paragraph 10: materiality reassessed before the evaluation, a prompt at evaluation,
and every band recomputing when materiality changes. Paragraph 15: the accumulated
misstatements and whether corrected, as fields. Section 9: `evaluation`, append-only, one
row per evaluation run. The build stages put the conclusion and the gates in Stage 5, the
evaluation screen in Stage 6 and the prior-period carry-forward in Pass 2.

**Already built before this stage** (D33, D38, D40, D41): the aggregate of four measures
with and without projected items and by type; the F3 reading of uncorrected; the gates;
banding against the current threshold version on every read; state-dependent inclusion.

**Added by this stage.**

- *Both tests shown.* The evaluation answer carries `tests`. `individual` lists every
  uncorrected item banded above PM, a refused one included (refusing with a reason releases
  the block on sign-off, not the item's significance), and those whose own effect on either
  measure is at or above overall materiality. `aggregate` is the hard gate's result.
- *The evaluation run.* `POST /api/engagements/{id}/evaluation/runs` inserts one row of
  `evaluation` (migration 0008): the engagement, the current threshold version, the four
  aggregates, who ran it and when, and a `detail` document. Any authenticated identity may
  record a run; it concludes nothing.
- *The reassessment prompt.* The request must state `materiality_reassessed: true`. It is
  recorded on the row (a CHECK holds it true) and as a `materiality_reassessed` event, as
  D13 planned. If materiality needs revising, a threshold version is set first.
- *Staleness.* A run is never updated. The evaluation answer's `latest_run` says whether
  the latest run is `current` or `stale`, and why: thresholds revised, a misstatement
  raised, moved or re-banded, or the aggregate changed.

**What a run holds, and what it never holds.** Aggregates and labels: the figures with and
without projected items and by type, the reference, version number, state, type and band of
every misstatement the run saw, the lines of the threshold version, the gate statuses, both
tests, the sign-off decision and its reasons, and the Spine version with its lock state.
Never a Dr, a Cr, or the effect of one misstatement: those stay in the Spine and are
computed on read. The four aggregate columns are the ones the spec's own data model gives
this table; `tests/test_models.py` pins the set.

**When a run is refused.** A run is recorded only when the evaluation can be computed in
full: thresholds exist, no uncorrected item's effects are unresolved, and no item's state
disagrees with the Spine. Otherwise the figures would be known to be short or wrong, and
nothing is written (409). A gate that fires does **not** stop a run: the run is the record
of what was found.

**Consistency.** The engagement row is locked before the evaluation is computed and the row
inserted, so a run's figures belong to one moment.

**At the database** (migration 0008, rendered and tested as SQL only): the aggregates take
the money domain; a gross aggregate is not negative and a net one does not exceed it in
size; the row is append-only for every role; the application role gets SELECT and INSERT;
an INSERT trigger requires the threshold version to belong to the engagement and to be
current. The application guard of D42 covers the table too.

**Ambiguities, resolved conservatively and left open.**

- *The spec's row names `conclusion`, `basis` and `concluded_by`.* The build stages put
  the conclusion in Stage 5, and an append-only row cannot have one added later. So a
  Stage 4 run is a row without those columns; Stage 5 adds them by migration and writes
  concluded rows through its own gated, partner-only route. Nothing here concludes.
- *`py_carried`* arrives with the prior-period carry-forward (Pass 2); what it holds
  depends on B6.
- *Whether an evaluation may be made on an unlocked Spine version* (B10) is not decided.
  A run is allowed either way and records the lock state; a later change makes it stale.
- *"Material individually"* is not defined by the spec apart from the above-PM band. Both
  readings are shown, above PM and at or above OM, and neither is chosen.


## D44 · Design check before Stage 5: the conclusion belongs on the evaluation row — 5 Nov 2026

A check of the Stage 4 table against the specification. Nothing was built and Stage 4 was
not changed: no conflict was found.

**What the specification says.** Section 9 draws one table, `evaluation`, with
`conclusion`, `basis` and `concluded_by` beside `threshold_version` and the four
aggregates, "append-only, one row per evaluation run", and adds that a change creates a new
version. Section 6.4 makes the conclusion "a field, mandatory, with the figures
auto-inserted". Acceptance 10 says it "cannot be saved empty, and carries the figures it was
based on". Section 2, paragraph 15 wants the conclusion and its basis "as fields, not as
prose". Section 10.3 puts "the conclusion field" on the evaluation screen. No section names
a separate conclusion record.

**So a separate conclusion table is not required, and would depart from the data model.**
The spec's own way of tying a conclusion to its figures and threshold version is to put
them on one row.

**Can Stage 5 add the columns to the existing table safely?** Yes, by a new migration that
adds `conclusion`, `basis` and `concluded_by` as nullable columns with a CHECK that the
three are all present and not blank, or all absent. The append-only protection is three
triggers on rows and on TRUNCATE (migration 0008); adding a nullable column and a CHECK is
not an UPDATE, changes no existing row, and drops nothing. Existing runs read as rows
without a conclusion, which is what they are.

**The rule that keeps it append-only.** A conclusion is always a **new row**: the
evaluation is computed under the engagement lock and the figures, the threshold version and
the conclusion are inserted together. An earlier run is never updated to receive a
conclusion; a revised conclusion is another row. This is "a change creates a new version"
applied to the evaluation. It also gives the strongest link available: the conclusion, the
figures it relied on and the threshold version are the same row, so they cannot drift.

**What Stage 4 already guarantees for that design**, pinned by tests: the row is
self-contained (engagement, threshold version, the four aggregates and the time are on it);
no row points at another; and "latest", "current" and "stale" are computed on read, never
stored, so a later row never forces a change to an earlier one.

**One reading the spec leaves open.** Section 9's row has `concluded_by` as its only actor,
which can be read as "every evaluation row is a concluded one". The build stages separate
the evaluation row (Stage 4) from the conclusion (Stage 5), so Stage 4 records runs without
a conclusion, by `evaluated_by`. Nothing in the spec forbids a recorded run that concludes
nothing; "mandatory" and "cannot be saved empty" govern the conclusion when one is saved,
and the Stage 5 CHECK will hold exactly that. If the firm prefers that only concluded rows
exist, the run route can be withdrawn without a schema change; that is the firm's call.

**For Stage 5 to settle, not decided here:** whether the partner must name the run they
reviewed, with the conclusion refused if that run has gone stale; whether a conclusion
records a determination as well as words; and what "material individually" means (B14).


## D45 · Stage 5: the conclusion, the gates in its write path, and the strategy prompt — 5 Nov 2026

**What the specification asks.** Section 6.4: the conclusion, whether uncorrected
misstatements are material individually or in aggregate, and the basis; a field, mandatory,
with the figures auto-inserted. Section 9: `conclusion`, `basis` and `concluded_by` on the
`evaluation` row, append-only. Section 12: the words are the partner's. Section 7: the hard
gate at overall materiality blocks an unmodified opinion; the soft gate at performance
materiality needs a partner acknowledgement and may be made hard by the firm; an item above
PM blocks sign-off until corrected, refused with a reason or withdrawn; the strategy
trigger prompts when the aggregate approaches materiality, recorded either way; and
blocking is in the write path. Acceptance 6, 7 and 10.

**Already built before this stage:** both gates, the acknowledgement and its staleness,
the individually-significant block, the partner role claim (D38 to D40) and the evaluation
row (D43).

**The conclusion is a new row.** Migration 0009 adds `determination`, `conclusion`, `basis`
and `concluded_by` to `evaluation`, nullable. A conclusion is inserted as a new row with its
own figures and threshold version, computed under the engagement lock; no earlier row is
updated. A revised conclusion is another row. The run reviewed is untouched.

**Determination and words.** `determination` is `not_material` or `material`: the
"whether" of section 6.4, needed so that the gate can tell what is being concluded.
`conclusion` and `basis` are the partner's words, neither empty (a 422 at the request, a
CHECK at the database). The split between individually and in aggregate is left to those
words; both computed tests are stored with the row, and no reading of "material
individually" is applied (B14).

**Who.** Partner only, through the role claim of D39 and D40, failing closed. The partner
check runs before any gate, so a non-partner learns nothing about the engagement.
`concluded_by` equals the identity that made the row, held by a CHECK.

**The run reviewed.** The request must name the evaluation run the partner reviewed. If
that run no longer describes the evaluation (thresholds revised, a misstatement raised,
moved or re-banded, or the aggregate changed) nothing is saved. The figures on the new row
are therefore the figures reviewed, which is how "carries the figures it was based on" is
made true and not merely likely. The spec does not ask for this step in so many words; it
is this module's way of meeting acceptance 10.

**The gates, by what is being concluded.** Every reason of the sign-off decision is now
either a *materiality* reason (the hard gate fires; the soft gate fires without a current
acknowledgement, or with the firm's PM gate set to hard) or a *readiness* reason (no
thresholds, an indeterminate gate, an unbanded item, a state the Spine disputes, an item
above PM still raised or communicated).

- *Not material* is what an unmodified opinion rests on. Every reason blocks it. Its route
  is tagged `sign-off` and depends on `sign_off_open`, as D40 required.
- *Material* records that the misstatements are material. Section 7 says the hard gate
  blocks an unmodified opinion; it does not say a material conclusion cannot be
  documented, and SA 450 paragraph 15 requires the conclusion to be documented whatever it
  is. So a gate that fires does not block it; the readiness reasons do. Its route is tagged
  `material-conclusion` and depends on `conclusion_ready`.

This amends the contract of D40, deliberately: a route whose path names a conclusion must
be partner-only and carry exactly one of the two tags, and only the path ending
`/conclusions/material` may carry the lighter one. `tests/test_contracts.py` holds it.

**The hard gate at the database.** A trigger on INSERT refuses a row that concludes
`not_material` when either gross aggregate is at or above the overall materiality of its
threshold version. It is the same test the application applies, for every role.

**The strategy trigger.** `OAK_STRATEGY_TRIGGER_FRACTION` is the fraction of overall
materiality at which the aggregate is "approaching materiality". It has **no default**:
the band is pending decision B5, and unset means the trigger is not evaluated and says so.
When set, the trigger fires at or above the line on any measure, the answer (whether the
strategy and plan were revised) is recorded as an event by any authenticated identity, and
goes stale like an acknowledgement. It is a prompt: it blocks nothing.

**Not built:** the Opinion-module hand-off (no such module exists), the screens (Stage 6),
the qualitative factors and the prior-period carry-forward (Pass 2).

## D46 · Closure work on Stages 0 to 5 — 5 Nov 2026

After the read-only review in `docs/CLOSURE_REVIEW.md`. Only what the specification or an
earlier approved decision already settled was built or closed; nothing here is anyone's new
approval.

**The two gates of D18.** D18 approved two read-only endpoints. They now exist:
`GET /api/engagements/{id}/gates/opinion` and `GET /api/engagements/{id}/gates/sign-off`,
each answering `open`, `blocked` or `undetermined` with the figures, the threshold version
and why. The opinion gate is the size test alone: the hard gate at overall materiality,
and the gate at performance materiality when the firm has set it to hard. The sign-off gate
is the whole sign-off decision. `blocked` wins over `undetermined`: a gate that already
fires on what is known is blocked, whatever else is unknown. Neither is ever reported open
on an evaluation that is incomplete, unbanded or disputed by the Spine. They read and write
nothing; no Opinion module exists to call them.

**Event kinds and payloads (D13).** Migration 0010 holds the event kind to the five the
module writes. Before every insert the application checks that the payload carries what its
kind requires. A new kind needs a migration.

**Orphan proposals.** `GET /api/engagements/{id}/spine-reconciliation` compares the Spine's
adjustments on the pinned version with the links recorded here. It lists orphans (an
adjustment carrying one of this module's references that no record links), records whose
adjustment the Spine lacks, states the two modules disagree on, and references the Spine
holds twice. It repairs nothing: an orphan can only be refused, in the Spine, by a person.

**Dependencies.** `backend/requirements-lock.txt` records the exact versions the suite
passes on, as a constraints file. `pyproject.toml` keeps its lower bounds.

**Closed from the specification.** B4c (CTT is a fraction of PM: section 4), B12 (a
mandatory free-text reason: section 2, paragraph 9), F4 (withdrawal only after
communication: the diagram of 3.3). N10, N14 and N15 were found to meet the specification
as built.

**Three investigations against the Spine's contract** (`D:\CAF\backend\src\oak_spine`,
read and not changed).

- *Successor versions (B10).* Locking is refused while any adjustment is proposed
  (`spine/lock.py`). Unlocking inserts one successor and copies every adjustment to it,
  proposed first and then decided as the original was, each copy carrying
  `copied_from_id`, the same `finding_ref`, lines and status. So following a record to its
  copy is deterministic. It was not built: it needs the lead's agreement that an engagement
  may be re-pointed, somewhere to record the copy's id (a final version's link cannot be
  rewritten, and the Spine lists only one version's adjustments at a time), and proof on the
  live Spine. Until then nothing can be raised for an engagement after its version is
  unlocked.
- *Lines (F9).* The Spine's API proposes and decides and nothing else; its database refuses
  a line once the adjustment is decided, and deletes nothing. An amount can therefore
  change only by a new adjustment with the old one refused, which is what withdrawing and
  raising again does. Entry of lines at raising matches spec section 8 for the two sources
  built (a working paper reference is required for both); the other three sources are
  Pass 2.
- *Withdrawal (F4).* The Spine would accept a refusal of any proposed adjustment, so
  withdrawing a raised item is technically possible. The spec's diagram draws withdrawal
  from communicated only, and that is what is built.

**One consequence found on the way (N17).** Because the Spine will not lock a version with
a proposed adjustment, every misstatement must reach a final state, and every orphan must
be refused in the Spine, before the Spine version can be locked.

**Not done, by instruction:** no commit; no Stage 6; no Pass 2.

